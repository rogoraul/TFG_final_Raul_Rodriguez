import json
from pathlib import Path

import pandas as pd

from trading_center.bot_dry_run import (
    BotDryRunConfig,
    BotDryRunOptions,
    build_bot_dry_run,
    evaluate_snapshot,
)


def test_default_config_blocks_all_rows_and_keeps_fail_closed_flags(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [_entry_ready_row(riskguard_status="riskguard_accepted")])

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md")
    )

    assert result.decision == "bot_dry_run_v1_artifact_ledger_ready_for_review"
    assert {row["dry_run_decision"] for row in result.ledger_rows} == {"dry_run_blocked_by_config"}
    assert {row["dry_run_reason"] for row in result.ledger_rows} == {"bot_enabled_false"}
    _assert_hard_flags(result.ledger_rows)
    assert result.run_meta["bot_enabled"] is False
    assert result.run_meta["bot_mode"] == "off"
    assert result.run_meta["mt5_connected"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["sql_real_written"] is False
    assert result.run_meta["signals_generated"] is False
    assert result.run_meta["backtests_executed"] is False
    assert result.run_meta["wavecount_used_as_filter"] is False


def test_watchlist_snapshot_generates_no_action_when_dry_run_enabled(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [_watching_row()])

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1),
    )

    assert result.ledger_rows[0]["dry_run_decision"] == "dry_run_no_action"
    assert result.ledger_rows[0]["would_create_order_intent"] is False
    _assert_hard_flags(result.ledger_rows)


def test_stale_entry_ready_row_is_blocked_by_data(tmp_path: Path) -> None:
    snapshot = _write_snapshot(
        tmp_path,
        [_entry_ready_row(riskguard_status="riskguard_accepted", data_freshness_status="stale")],
    )

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1),
    )

    assert result.ledger_rows[0]["dry_run_decision"] == "dry_run_blocked_by_data"
    assert "freshness_not_acceptable" in result.ledger_rows[0]["dry_run_reason"]


def test_entry_ready_with_missing_levels_is_blocked_by_data(tmp_path: Path) -> None:
    row = _entry_ready_row(riskguard_status="riskguard_accepted")
    row["tp2"] = ""
    snapshot = _write_snapshot(tmp_path, [row])

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1),
    )

    assert result.ledger_rows[0]["dry_run_decision"] == "dry_run_blocked_by_data"
    assert "missing_or_invalid_levels" in result.ledger_rows[0]["dry_run_reason"]


def test_riskguard_rejected_blocks_simulated_intent(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [_entry_ready_row(riskguard_status="riskguard_rejected")])

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1),
    )

    assert result.ledger_rows[0]["dry_run_decision"] == "dry_run_blocked_by_riskguard"
    assert result.ledger_rows[0]["would_create_order_intent"] is False
    _assert_hard_flags(result.ledger_rows)


def test_riskguard_accepted_entry_ready_creates_simulated_intent(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [_entry_ready_row(riskguard_status="riskguard_accepted")])

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, fixture_mode=True),
    )

    row = result.ledger_rows[0]
    assert row["dry_run_decision"] == "dry_run_order_intent"
    assert row["would_create_order_intent"] is True
    assert row["is_simulation"] is True
    _assert_hard_flags(result.ledger_rows)


def test_max_intents_is_respected(tmp_path: Path) -> None:
    snapshot = _write_snapshot(
        tmp_path,
        [
            _entry_ready_row(symbol="EURUSD.r", setup_id="1", riskguard_status="riskguard_accepted"),
            _entry_ready_row(symbol="GBPUSD.r", setup_id="2", riskguard_status="riskguard_accepted"),
        ],
    )

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, fixture_mode=True),
    )

    decisions = [row["dry_run_decision"] for row in result.ledger_rows]
    assert decisions == ["dry_run_order_intent", "dry_run_blocked_by_config"]
    assert result.ledger_rows[1]["dry_run_reason"] == "max_intents_exceeded"


def test_wavecount_fields_do_not_change_decision() -> None:
    base = _entry_ready_row(riskguard_status="riskguard_accepted")
    altered = dict(base)
    altered["wavecount_context_status"] = "conflicting_context"
    altered["wavecount_policy_bucket"] = "active_wave_study_candidate"
    altered["wavecount_notes"] = "changed_wavecount_context"
    options = BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, fixture_mode=True)

    first = evaluate_snapshot(pd.DataFrame([base]), options=options, generated_at="now", source_artifacts="fixture")
    second = evaluate_snapshot(pd.DataFrame([altered]), options=options, generated_at="now", source_artifacts="fixture")

    assert first[0]["dry_run_decision"] == second[0]["dry_run_decision"]
    assert first[0]["would_create_order_intent"] == second[0]["would_create_order_intent"]
    payload = json.loads(second[0]["payload_json"])
    assert payload["checks"]["wavecount_used_as_filter"] is False


def test_empty_snapshot_generates_empty_ledger_without_side_effects(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [])

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1),
    )

    assert result.ledger_rows == []
    assert (tmp_path / "out" / "dry_run_decision_ledger.csv").exists()
    assert (tmp_path / "out" / "dry_run_decision_ledger.json").exists()
    assert result.run_meta["can_execute_order_any_true"] is False
    assert any(issue["issue_id"] == "snapshot_empty" for issue in result.issues_or_risks)


def test_outputs_json_payloads_and_artifacts_are_valid(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [_entry_ready_row(riskguard_status="riskguard_accepted")])
    output_dir = tmp_path / "out"

    result = build_bot_dry_run(
        BotDryRunConfig(snapshot_csv=snapshot, output_dir=output_dir, doc_path=tmp_path / "doc.md"),
        BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, fixture_mode=True),
    )

    assert (output_dir / "dry_run_decision_ledger.csv").exists()
    assert (output_dir / "dry_run_decision_ledger.json").exists()
    assert (output_dir / "tables" / "source_data_audit.csv").exists()
    assert (output_dir / "tables" / "config_audit.csv").exists()
    assert (output_dir / "tables" / "decision_rule_audit.csv").exists()
    assert (output_dir / "tables" / "safety_flags_audit.csv").exists()
    assert (output_dir / "tables" / "wavecount_non_filter_audit.csv").exists()
    assert (output_dir / "tables" / "issues_or_risks.csv").exists()
    assert (output_dir / "run_meta.json").exists()
    assert (output_dir / "BOT_DRY_RUN_V1.md").exists()
    assert (tmp_path / "doc.md").exists()

    ledger_json = json.loads((output_dir / "dry_run_decision_ledger.json").read_text(encoding="utf-8"))
    assert len(ledger_json) == len(result.ledger_rows)
    for row in result.ledger_rows:
        json.loads(row["payload_json"])

    meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["bot_dry_run_implemented"] is True
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["signals_generated"] is False
    assert meta["backtests_executed"] is False
    assert meta["wavecount_used_as_filter"] is False


def test_mt5_live_and_telegram_command_options_block_rows(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, [_entry_ready_row(riskguard_status="riskguard_accepted")])

    for options, expected_reason in [
        (BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, mt5_enabled=True), "mt5_enabled_true"),
        (BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, live_enabled=True), "live_enabled_true"),
        (
            BotDryRunOptions(bot_enabled=True, mode="dry_run", max_intents=1, telegram_command_bot_enabled=True),
            "telegram_command_bot_enabled_true",
        ),
    ]:
        result = build_bot_dry_run(
            BotDryRunConfig(snapshot_csv=snapshot, output_dir=tmp_path / expected_reason, doc_path=tmp_path / f"{expected_reason}.md"),
            options,
        )
        assert result.ledger_rows[0]["dry_run_decision"] == "dry_run_blocked_by_config"
        assert result.ledger_rows[0]["dry_run_reason"] == expected_reason


def _assert_hard_flags(rows: list[dict[str, object]]) -> None:
    assert rows
    assert {row["can_execute_order"] for row in rows} == {False}
    assert {row["would_send_to_mt5"] for row in rows} == {False}
    assert {row["would_send_telegram_order"] for row in rows} == {False}
    assert {row["is_simulation"] for row in rows} == {True}


def _write_snapshot(root: Path, rows: list[dict[str, object]]) -> Path:
    path = root / "snapshot.csv"
    pd.DataFrame(rows, columns=_columns()).to_csv(path, index=False)
    return path


def _watching_row(**overrides: object) -> dict[str, object]:
    row = _base_row()
    row.update(
        {
            "signal_state": "watching_setup",
            "riskguard_status": "not_evaluated",
            "riskguard_reason": "not_available",
            "entry": "",
            "sl": "",
            "tp1": "",
            "tp2": "",
        }
    )
    row.update(overrides)
    return row


def _entry_ready_row(**overrides: object) -> dict[str, object]:
    row = _base_row()
    row.update(
        {
            "signal_state": "entry_ready_new",
            "riskguard_status": "riskguard_accepted",
            "riskguard_reason": "accepted",
            "entry": 1.1,
            "sl": 1.0,
            "tp1": 1.2,
            "tp2": 1.3,
        }
    )
    row.update(overrides)
    return row


def _base_row() -> dict[str, object]:
    return {
        "snapshot_id": "snapshot_test",
        "generated_at": "2026-05-29T10:00:00",
        "symbol": "EURUSD.r",
        "market_group": "Forex Majors",
        "strategy": "enbolsa:macd_breakout",
        "timeframe_ltf": "H1",
        "timeframe_htf": "H4",
        "last_closed_bar_time": "2026-05-29T08:00:00",
        "data_freshness_status": "latest_closed_bar",
        "side": "BUY",
        "setup_id": "setup_1",
        "riskguard_detail": "fixture",
        "wavecount_available": True,
        "wavecount_policy_bucket": "study_only",
        "wavecount_context_status": "supports_context",
        "wavecount_should_filter_trade": False,
        "wavecount_notes": "fixture context",
        "dry_run_eligible": False,
        "is_read_only": True,
        "can_execute_order": False,
    }


def _columns() -> list[str]:
    return [
        "snapshot_id",
        "generated_at",
        "symbol",
        "market_group",
        "strategy",
        "timeframe_ltf",
        "timeframe_htf",
        "last_closed_bar_time",
        "data_freshness_status",
        "signal_state",
        "side",
        "setup_id",
        "entry",
        "sl",
        "tp1",
        "tp2",
        "riskguard_status",
        "riskguard_reason",
        "riskguard_detail",
        "wavecount_available",
        "wavecount_policy_bucket",
        "wavecount_context_status",
        "wavecount_should_filter_trade",
        "wavecount_notes",
        "dry_run_eligible",
        "is_read_only",
        "can_execute_order",
    ]
