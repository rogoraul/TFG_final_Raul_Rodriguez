import json
from pathlib import Path

import pandas as pd

from trading_center.telegram_informational import (
    TelegramInformationalConfig,
    build_no_action_audit,
    build_telegram_informational,
)


def test_telegram_informational_generates_dry_run_outputs_without_tokens(tmp_path: Path) -> None:
    source_root = _write_minimal_sources(tmp_path)
    output_dir = tmp_path / "out"
    doc_path = tmp_path / "docs" / "TELEGRAM_INFORMATIONAL_V1.md"

    result = build_telegram_informational(
        TelegramInformationalConfig(
            design_dir=source_root / "artifacts/tfg/telegram_informational_design_v1_2026-05-28",
            snapshot_csv=source_root
            / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv",
            security_flags_csv=source_root
            / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/security_flags_check.csv",
            dashboard_review_meta=source_root
            / "artifacts/tfg/trading_center_readonly_full_review_v1_2026-05-28/run_meta.json",
            wavecount_panel_meta=source_root / "artifacts/tfg/wavecount_study_panel_v1_2026-05-28/run_meta.json",
            output_dir=output_dir,
            doc_path=doc_path,
        ),
        include_wavecount_study=True,
        max_messages=20,
    )

    assert result.decision == "telegram_delivery_policy_fix_ready_for_sender_gate_design"
    assert (output_dir / "rendered_messages.csv").exists()
    assert (output_dir / "rendered_messages.json").exists()
    assert (output_dir / "tables" / "source_data_audit.csv").exists()
    assert (output_dir / "tables" / "no_action_message_audit.csv").exists()
    assert (output_dir / "tables" / "delivery_simulation_audit.csv").exists()
    assert (output_dir / "run_meta.json").exists()
    assert doc_path.exists()
    assert not (tmp_path / ".env").exists()

    messages = json.loads((output_dir / "rendered_messages.json").read_text(encoding="utf-8"))
    meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    no_action = pd.read_csv(output_dir / "tables" / "no_action_message_audit.csv")
    delivery = pd.read_csv(output_dir / "tables" / "delivery_simulation_audit.csv")

    assert messages
    assert {message["send_real"] for message in messages} == {False}
    assert all(message["safe_to_send"] for message in messages)
    assert "wavecount_study_digest" in {message["message_type"] for message in messages}
    wavecount_messages = [message for message in messages if message["message_type"] == "wavecount_study_digest"]
    assert wavecount_messages
    assert wavecount_messages[0]["contains_wavecount"] is True
    assert wavecount_messages[0]["wavecount_study_only"] is True
    assert "no es filtro" in wavecount_messages[0]["body"]

    assert (no_action["audit_status"] == "pass").all()
    assert (delivery["send_real"].astype(str).str.lower() == "false").all()
    assert "preview_allowed" in set(delivery["delivery_status"])
    assert _delivery_status(delivery, "platform_daily_summary") == "preview_allowed"
    assert _delivery_status(delivery, "watchlist_status_digest") == "preview_allowed"
    assert _delivery_status(delivery, "data_health_alert") == "omitted_no_condition"
    assert _delivery_status(delivery, "pipeline_error_notice") == "omitted_no_condition"
    assert _delivery_status(delivery, "manual_review_reminder") == "omitted_no_condition"
    assert _delivery_status(delivery, "riskguard_status_notice") == "omitted_no_condition"
    assert _delivery_status(delivery, "wavecount_study_digest") == "manual_only"

    assert meta["telegram_implemented"] is True
    assert meta["telegram_connected"] is False
    assert meta["telegram_real_messages_sent"] == 0
    assert meta["telegram_tokens_created"] is False
    assert meta["telegram_bot_created"] is False
    assert meta["dry_run_only"] is True
    assert meta["manual_preview"] is False
    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["bot_implemented"] is False
    assert meta["mt5_connected"] is False
    assert meta["backtests_executed"] is False
    assert meta["signals_generated"] is False
    assert meta["wavecount_used_as_filter"] is False


def test_telegram_informational_blocks_operational_wording() -> None:
    rows = build_no_action_audit(
        [
            {
                "message_id": "unsafe",
                "message_type": "watchlist_status_digest",
                "title": "Comprar ahora",
                "body": "Entrada recomendada y ejecutar orden.",
            }
        ]
    )

    assert rows[0]["safe_to_send"] is False
    assert rows[0]["audit_status"] == "blocked"
    assert "entrada" in rows[0]["blocked_patterns"] or "comprar" in rows[0]["blocked_patterns"]


def test_telegram_informational_keeps_wavecount_disabled_by_default(tmp_path: Path) -> None:
    source_root = _write_minimal_sources(tmp_path)
    output_dir = tmp_path / "out"

    result = build_telegram_informational(
        TelegramInformationalConfig(
            design_dir=source_root / "artifacts/tfg/telegram_informational_design_v1_2026-05-28",
            snapshot_csv=source_root
            / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv",
            security_flags_csv=source_root
            / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/security_flags_check.csv",
            dashboard_review_meta=source_root
            / "artifacts/tfg/trading_center_readonly_full_review_v1_2026-05-28/run_meta.json",
            wavecount_panel_meta=source_root / "artifacts/tfg/wavecount_study_panel_v1_2026-05-28/run_meta.json",
            output_dir=output_dir,
            doc_path=tmp_path / "doc.md",
        )
    )

    assert result.decision == "telegram_delivery_policy_fix_ready_for_sender_gate_design"
    assert "wavecount_study_digest" not in {message["message_type"] for message in result.rendered_messages}
    assert any(issue["issue_id"] == "wavecount_digest_disabled_by_default" for issue in result.issues_or_risks)


def test_telegram_informational_manual_preview_can_render_conditional_messages(tmp_path: Path) -> None:
    source_root = _write_minimal_sources(tmp_path)
    output_dir = tmp_path / "out"

    build_telegram_informational(
        TelegramInformationalConfig(
            design_dir=source_root / "artifacts/tfg/telegram_informational_design_v1_2026-05-28",
            snapshot_csv=source_root
            / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv",
            security_flags_csv=source_root
            / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/security_flags_check.csv",
            dashboard_review_meta=source_root
            / "artifacts/tfg/trading_center_readonly_full_review_v1_2026-05-28/run_meta.json",
            wavecount_panel_meta=source_root / "artifacts/tfg/wavecount_study_panel_v1_2026-05-28/run_meta.json",
            output_dir=output_dir,
            doc_path=tmp_path / "doc.md",
        ),
        include_wavecount_study=True,
        manual_preview=True,
    )

    delivery = pd.read_csv(output_dir / "tables" / "delivery_simulation_audit.csv")
    assert _delivery_status(delivery, "data_health_alert") == "preview_allowed"
    assert _delivery_status(delivery, "pipeline_error_notice") == "preview_allowed"
    assert _delivery_status(delivery, "manual_review_reminder") == "preview_allowed"
    assert _delivery_status(delivery, "riskguard_status_notice") == "preview_allowed"
    assert _delivery_status(delivery, "wavecount_study_digest") == "preview_allowed"


def _write_minimal_sources(root: Path) -> Path:
    design_tables = root / "artifacts/tfg/telegram_informational_design_v1_2026-05-28/tables"
    sql_export = root / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql"
    sql_tables = root / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables"
    dashboard_dir = root / "artifacts/tfg/trading_center_readonly_full_review_v1_2026-05-28"
    wavecount_dir = root / "artifacts/tfg/wavecount_study_panel_v1_2026-05-28"
    for path in [design_tables, sql_export, sql_tables, dashboard_dir, wavecount_dir]:
        path.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(_message_type_rows()).to_csv(design_tables / "telegram_message_types.csv", index=False)
    pd.DataFrame(_delivery_rows()).to_csv(design_tables / "telegram_delivery_policy.csv", index=False)
    pd.DataFrame(
        [
            {"field": "telegram_enabled", "type": "bool", "default": "false", "meaning": "disabled"},
            {"field": "send_wavecount_study", "type": "bool", "default": "false", "meaning": "study optional"},
        ]
    ).to_csv(design_tables / "telegram_future_config_contract.csv", index=False)
    pd.DataFrame([{"message_type": row["message_type"], "template_short": "safe"} for row in _message_type_rows()]).to_csv(
        design_tables / "telegram_message_templates.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "row_id": 1,
                "snapshot_id": "snap_test",
                "generated_at": "2026-05-28 10:00:00",
                "symbol": "TEST",
                "market_group": "Synthetic",
                "timeframe_ltf": "H1",
                "data_freshness_status": "latest_closed_bar",
                "signal_state": "watching_setup",
                "riskguard_status": "not_evaluated",
                "is_read_only": 1,
                "can_execute_order": 0,
                "wavecount_should_filter_trade": 0,
                "run_kind": "bootstrap_current",
                "data_origin": "fixture",
            }
        ]
    ).to_csv(sql_export / "live_context_snapshot_from_sql.csv", index=False)

    pd.DataFrame(
        [
            {"check_name": "can_execute_order_true", "value": 0, "expected": 0, "status": "passed"},
            {"check_name": "wavecount_should_filter_trade_true", "value": 0, "expected": 0, "status": "passed"},
        ]
    ).to_csv(sql_tables / "security_flags_check.csv", index=False)

    (dashboard_dir / "run_meta.json").write_text(
        json.dumps({"decision": "readonly_platform_v1_ready_for_telegram_design"}),
        encoding="utf-8",
    )
    (wavecount_dir / "run_meta.json").write_text(
        json.dumps({"wavecount_rows": 4, "wavecount_buckets": 2, "wavecount_visual_cases": 1}),
        encoding="utf-8",
    )
    return root


def _delivery_status(frame: pd.DataFrame, message_type: str) -> str:
    row = frame.loc[frame["message_type"] == message_type].iloc[0]
    return str(row["delivery_status"])


def _message_type_rows() -> list[dict[str, object]]:
    return [
        {"message_type": "platform_daily_summary", "severity": "info", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "watchlist_status_digest", "severity": "info", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "data_health_alert", "severity": "warning", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "riskguard_status_notice", "severity": "warning", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "system_audit_notice", "severity": "info", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "pipeline_error_notice", "severity": "error", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "manual_review_reminder", "severity": "manual_review", "requires_deduplication": True, "v1_status": "included"},
        {"message_type": "wavecount_study_digest", "severity": "manual_review", "requires_deduplication": True, "v1_status": "optional_in_v1"},
    ]


def _delivery_rows() -> list[dict[str, object]]:
    return [
        {"message_type": row["message_type"], "cooldown_minutes": 120, "max_per_day": 8}
        for row in _message_type_rows()
    ]
