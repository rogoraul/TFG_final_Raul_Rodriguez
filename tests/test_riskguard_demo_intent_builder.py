import json
from pathlib import Path

from trading_center import riskguard_demo_intent_builder as builder
from trading_center.riskguard_demo_intent_builder import RiskGuardIntentBuilderConfig, execute


OBSERVED = builder.parse_time("2026-06-08T10:30:00")


def test_cli_fixture_generates_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "out"

    exit_code = builder.main(["--fixture-mode", "--output-dir", str(out), "--observed-at", "2026-06-08T10:30:00"])

    assert exit_code == 0
    assert (out / "demo_order_intents.csv").exists()
    assert (out / "riskguard_decisions.csv").exists()
    assert (out / "tables" / "eligibility_audit.csv").exists()
    assert json.loads((out / "run_meta.json").read_text(encoding="utf-8"))["riskguard_demo_intent_builder_implemented"] is True


def test_fixture_macd_and_fib_can_be_eligible(tmp_path: Path) -> None:
    result = execute(RiskGuardIntentBuilderConfig(output_dir=tmp_path / "out", fixture_mode=True, observed_at=OBSERVED))

    accepted = [row for row in result.decision_rows if row["riskguard_decision"] == "accepted_for_demo_intent"]
    accepted_types = {row["setup_type"] for row in accepted}

    assert "macd_breakout" in accepted_types
    assert "fib_limit_live_candidate" in accepted_types
    assert result.run_meta["accepted_for_demo_intent_count"] == 2
    assert all(row["sizing_status"] == "calculated" for row in accepted)
    assert (tmp_path / "out" / "riskguard_sizing_audit.csv").exists()
    assert (tmp_path / "out" / "riskguard_exposure_audit.csv").exists()


def test_rsi_trend_reversal_is_blocked_by_automatic_scope(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("rsi1", "rsi_trend_reversal", "would_trigger")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_setup_scope"
    assert result.intent_rows == []


def test_context_items_are_blocked_by_scope(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("ctx1", "previous_day_high_low_candidate", "would_trigger")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_setup_scope"


def test_low_quality_blocks_candidate(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("low1", "macd_breakout", "would_trigger", quality=2)])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_low_quality"
    assert result.intent_rows == []


def test_would_wait_does_not_generate_accepted_intent(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("wait1", "macd_breakout", "would_wait", entry_time="")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_waiting_confirmation"
    assert result.intent_rows == []


def test_late_setup_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("late1", "macd_breakout", "would_trigger", entry_time="2026-06-08T08:00:00")],
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_late_setup"


def test_invalidated_setup_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("invalid1", "fib_limit_live_candidate", "invalidated")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_invalidated_setup"


def test_missing_entry_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("missing_entry", "macd_breakout", "would_trigger", entry_price="")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_missing_entry"


def test_missing_sl_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("missing_sl", "macd_breakout", "would_trigger", sl="")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_missing_sl"


def test_missing_tp_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(tmp_path, [shadow("missing_tp", "fib_limit_live_candidate", "would_trigger", tp1="")])

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_missing_tp"
    assert len(result.intent_rows) == 1


def test_strict_mt5_snapshot_blocks_when_missing(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("strict1", "macd_breakout", "would_trigger")],
        strict_mt5_snapshot=True,
        write_account=False,
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_missing_mt5_snapshot"


def test_snapshot_duplicate_position_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("dup1", "macd_breakout", "would_trigger", symbol="EURUSD.r")],
        positions_text="symbol,direction,volume\nEURUSD.r,long,0.1\n",
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_existing_position"


def test_index_without_symbol_metadata_blocks_sizing(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [
            shadow(
                "idx_no_meta",
                "fib_limit_live_candidate",
                "would_trigger",
                symbol="US100",
                entry_price="19400",
                sl="19300",
                tp1="19600",
            )
        ],
        metadata_text="symbol,trade_tick_size,trade_tick_value_loss,volume_min,volume_step,volume_max\n",
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_missing_symbol_metadata"
    assert result.decision_rows[0]["sizing_status"] == "blocked"


def test_risk_pct_above_limit_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("risk_high", "macd_breakout", "would_trigger", risk_pct="1.0")],
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_risk_pct_limit"


def test_total_exposure_limit_blocks(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("exposure_total", "macd_breakout", "would_trigger")],
        max_total_open_risk_pct=0.10,
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_total_exposure_limit"
    assert result.decision_rows[0]["exposure_status"] == "blocked"


def test_missing_risk_state_blocks_otherwise_valid_candidate(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("risk_state_missing", "macd_breakout", "would_trigger")],
        write_risk_state=False,
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_missing_risk_state"


def test_kill_switch_blocks_candidate(tmp_path: Path) -> None:
    result = execute_with_shadow(
        tmp_path,
        [shadow("kill_switch", "macd_breakout", "would_trigger")],
        risk_state_text="kill_switch_active,daily_realized_pnl,cumulative_realized_pnl\ntrue,0,0\n",
    )

    assert result.decision_rows[0]["riskguard_decision"] == "blocked_by_kill_switch"
    assert result.decision_rows[0]["kill_switch_active"] is True


def test_outputs_are_fail_closed(tmp_path: Path) -> None:
    result = execute(RiskGuardIntentBuilderConfig(output_dir=tmp_path / "out", fixture_mode=True, observed_at=OBSERVED))

    assert result.run_meta["can_send_order_any_true"] is False
    assert result.run_meta["order_sent_any_true"] is False
    assert all(row["can_send_order"] is False for row in result.intent_rows)
    assert all(row["order_sent"] is False for row in result.intent_rows)
    assert all(row["can_send_order"] is False for row in result.decision_rows)
    assert all(row["order_sent"] is False for row in result.decision_rows)


def test_module_has_no_execution_surface_literals() -> None:
    source = Path(builder.__file__).read_text(encoding="utf-8")

    assert "order_send" not in source
    assert "TRADE_ACTION_DEAL" not in source
    assert "TRADE_ACTION_PENDING" not in source
    assert "def send_order" not in source
    assert "def place_order" not in source


def test_run_meta_is_fail_closed(tmp_path: Path) -> None:
    result = execute(RiskGuardIntentBuilderConfig(output_dir=tmp_path / "out", fixture_mode=True, observed_at=OBSERVED))
    meta = result.run_meta

    assert meta["demo_order_sender_implemented"] is False
    assert meta["order_send_available"] is False
    assert meta["mt5_connected"] is False
    assert meta["mt5_orders_sent"] == 0
    assert meta["orders_sent"] == 0
    assert meta["telegram_connected"] is False
    assert meta["sql_real_written"] is False
    assert meta["backtests_executed"] is False


def execute_with_shadow(
    tmp_path: Path,
    rows: list[dict[str, object]],
    *,
    strict_mt5_snapshot: bool = False,
    write_account: bool = True,
    write_risk_state: bool = True,
    positions_text: str = "symbol,direction,volume\n",
    pending_text: str = "symbol,direction,volume\n",
    metadata_text: str = "symbol,trade_tick_size,trade_tick_value_loss,volume_min,volume_step,volume_max\n",
    risk_state_text: str = "kill_switch_active,daily_realized_pnl,cumulative_realized_pnl\nfalse,0,0\n",
    max_total_open_risk_pct: float = 1.0,
) -> builder.RiskGuardIntentBuilderResult:
    shadow_path = tmp_path / "shadow.csv"
    account_path = tmp_path / "account.csv"
    positions_path = tmp_path / "positions.csv"
    pending_path = tmp_path / "pending.csv"
    metadata_path = tmp_path / "metadata.csv"
    risk_state_path = tmp_path / "risk_state.csv"
    write_rows(shadow_path, rows)
    if write_account:
        account_path.write_text("equity,balance\n100000,100000\n", encoding="utf-8")
    positions_path.write_text(positions_text, encoding="utf-8")
    pending_path.write_text(pending_text, encoding="utf-8")
    metadata_path.write_text(metadata_text, encoding="utf-8")
    if write_risk_state:
        risk_state_path.write_text(risk_state_text, encoding="utf-8")
    return execute(
        RiskGuardIntentBuilderConfig(
            output_dir=tmp_path / "out",
            shadow_decisions_csv=shadow_path,
            mt5_account_snapshot_csv=account_path,
            mt5_positions_snapshot_csv=positions_path,
            mt5_pending_orders_snapshot_csv=pending_path,
            symbol_metadata_csv=metadata_path,
            risk_state_csv=risk_state_path,
            screener_setups_csv=tmp_path / "missing_screener.csv",
            strict_mt5_snapshot=strict_mt5_snapshot,
            max_total_open_risk_pct=max_total_open_risk_pct,
            observed_at=OBSERVED,
        )
    )


def shadow(
    setup_id: str,
    setup_type: str,
    shadow_state: str,
    *,
    symbol: str = "EURUSD.r",
    quality: int = 5,
    entry_time: str = "2026-06-08T10:10:00",
    entry_price: str = "1.1000",
    sl: str = "1.0950",
    tp1: str = "1.1100",
    tp2: str = "",
    risk_pct: str = "",
) -> dict[str, object]:
    return {
        "shadow_decision_id": f"sd_{setup_id}",
        "setup_id": setup_id,
        "symbol": symbol,
        "market_group": "Forex Majors",
        "timeframe": "H1",
        "setup_type": setup_type,
        "strategy": setup_type,
        "direction": "long",
        "timing_state": "entry_review",
        "setup_quality_score": quality,
        "shadow_state": shadow_state,
        "hypothetical_entry_time": entry_time,
        "hypothetical_entry_price": entry_price,
        "hypothetical_sl": sl,
        "hypothetical_tp1": tp1,
        "hypothetical_tp2": tp2,
        "risk_pct": risk_pct,
        "source_artifacts": "test",
    }


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(fieldnames) + "\n")
        for row in rows:
            handle.write(",".join(str(row.get(field, "")) for field in fieldnames) + "\n")
