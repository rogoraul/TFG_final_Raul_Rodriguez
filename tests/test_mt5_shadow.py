import json
from pathlib import Path

from trading_center import mt5_shadow
from trading_center.mt5_shadow import Mt5ShadowConfig, execute


def test_fixture_generates_shadow_decisions(tmp_path: Path) -> None:
    result = execute(Mt5ShadowConfig(output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md", fixture_mode=True))
    out = tmp_path / "out"

    assert (out / "mt5_shadow_decisions.csv").exists()
    assert (out / "mt5_shadow_decisions.json").exists()
    assert (out / "tables" / "fill_simulation_audit.csv").exists()
    assert (out / "tables" / "excluded_from_automation_audit.csv").exists()
    assert result.run_meta["mt5_shadow_implemented"] is True
    assert result.run_meta["would_trigger_count"] == 1
    assert result.run_meta["late_count"] == 1
    assert result.run_meta["would_skip_count"] == 0
    assert result.run_meta["shadow_decisions_count"] == 2
    assert result.run_meta["setups_excluded_from_shadow_decisions_count"] == 1
    assert result.run_meta["automation_scope_eligible_count"] == 2
    assert result.run_meta["automation_scope_context_only_count"] == 1


def test_artifact_first_inputs_are_loaded(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    ohlc = tmp_path / "ohlc.csv"
    positions = tmp_path / "positions.csv"
    account = tmp_path / "account.csv"
    layers = tmp_path / "layers.csv"
    setups.write_text(
        "setup_id,symbol,market_group,timeframe,setup_type,strategy,direction,setup_status,setup_quality_score,timing_state,trigger_level,is_late,is_invalidated,source_artifacts\n"
        "s1,EURUSD.r,Forex Majors,H1,fib_limit_live_candidate,fib_limit,long,ready_for_chart_review,5,entry_review,1.1,False,False,test\n",
        encoding="utf-8",
    )
    ohlc.write_text(
        "market_group,symbol,timeframe,timestamp,open,high,low,close\n"
        "Forex Majors,EURUSD.r,H1,2026-06-08 10:00:00,1.09,1.11,1.08,1.105\n",
        encoding="utf-8",
    )
    positions.write_text("symbol,direction,volume,can_modify_position,can_send_order\n", encoding="utf-8")
    account.write_text("account_id_hash,equity,read_only\nhash,10000,True\n", encoding="utf-8")
    layers.write_text("setup_id,layer_type,label,price\ns1,fibonacci,Fib 61.8,1.1\n", encoding="utf-8")

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=ohlc,
            mt5_positions_csv=positions,
            mt5_account_csv=account,
            chart_layers_csv=layers,
        )
    )

    assert result.run_meta["setups_loaded"] == 1
    assert result.shadow_rows[0]["shadow_state"] == "would_trigger"
    assert result.shadow_rows[0]["order_sent"] is False
    assert result.shadow_rows[0]["can_send_order"] is False


def test_missing_ohlc_marks_no_price_data_when_allowed(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    setups.write_text(
        "setup_id,symbol,market_group,timeframe,setup_type,strategy,direction,setup_quality_score,timing_state,trigger_level,is_late,is_invalidated\n"
        "s1,EURUSD.r,Forex Majors,H1,fib_limit_live_candidate,fib_limit,long,5,entry_review,1.1,False,False\n",
        encoding="utf-8",
    )

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=tmp_path / "missing_ohlc.csv",
            allow_missing_inputs=True,
        )
    )

    assert result.shadow_rows[0]["shadow_state"] == "no_price_data"
    assert result.run_meta["no_price_data_count"] == 1


def test_existing_readonly_position_blocks_duplicate_symbol(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    ohlc = tmp_path / "ohlc.csv"
    positions = tmp_path / "positions.csv"
    setups.write_text(
        "setup_id,symbol,market_group,timeframe,setup_type,strategy,direction,setup_quality_score,timing_state,trigger_level,is_late,is_invalidated\n"
        "s1,EURUSD.r,Forex Majors,H1,fib_limit_live_candidate,fib_limit,long,5,entry_review,1.1,False,False\n",
        encoding="utf-8",
    )
    ohlc.write_text(
        "market_group,symbol,timeframe,timestamp,open,high,low,close\n"
        "Forex Majors,EURUSD.r,H1,2026-06-08 10:00:00,1.09,1.11,1.08,1.105\n",
        encoding="utf-8",
    )
    positions.write_text("symbol,direction,volume,can_modify_position,can_send_order\nEURUSD.r,long,0.1,False,False\n", encoding="utf-8")

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=ohlc,
            mt5_positions_csv=positions,
            allow_missing_inputs=True,
        )
    )

    assert result.shadow_rows[0]["shadow_state"] == "blocked"
    assert "duplicate_exposure" in result.shadow_rows[0]["shadow_reason"]


def test_timestamp_reference_does_not_fallback_to_old_ohlc(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    ohlc = tmp_path / "ohlc.csv"
    setups.write_text(
        "setup_id,generated_at,symbol,market_group,timeframe,setup_type,strategy,direction,setup_quality_score,timing_state,trigger_level,is_late,is_invalidated\n"
        "s1,2026-06-08T10:00:00+00:00,EURUSD.r,Forex Majors,H1,fib_limit_live_candidate,fib_limit,long,5,entry_review,1.1,False,False\n",
        encoding="utf-8",
    )
    ohlc.write_text(
        "market_group,symbol,timeframe,timestamp,open,high,low,close\n"
        "Forex Majors,EURUSD.r,H1,2026-06-07 09:00:00,1.09,1.11,1.08,1.105\n",
        encoding="utf-8",
    )

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=ohlc,
            allow_missing_inputs=True,
        )
    )

    assert result.shadow_rows[0]["shadow_state"] == "would_wait"
    assert result.shadow_rows[0]["shadow_reason"] == "no_closed_ohlc_after_fib_reference_time"


def test_rsi_context_is_not_auto_shadow_candidate(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    ohlc = tmp_path / "ohlc.csv"
    setups.write_text(
        "setup_id,symbol,market_group,timeframe,setup_type,strategy,direction,setup_quality_score,timing_state,trigger_level,is_late,is_invalidated\n"
        "s1,EURUSD.r,Forex Majors,H1,rsi_extreme_with_context,market_context,long,5,entry_review,1.1,False,False\n",
        encoding="utf-8",
    )
    ohlc.write_text(
        "market_group,symbol,timeframe,timestamp,open,high,low,close\n"
        "Forex Majors,EURUSD.r,H1,2026-06-08 10:00:00,1.09,1.11,1.08,1.105\n",
        encoding="utf-8",
    )

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=ohlc,
            allow_missing_inputs=True,
        )
    )

    excluded_path = tmp_path / "out" / "tables" / "excluded_from_automation_audit.csv"
    excluded = excluded_path.read_text(encoding="utf-8")

    assert result.shadow_rows == []
    assert "rsi_extreme_with_context" in excluded
    assert "setup_type_not_in_automatic_bot_scope" in excluded
    assert result.run_meta["automation_scope_eligible_count"] == 0
    assert result.run_meta["setups_excluded_from_shadow_decisions_count"] == 1


def test_low_quality_macd_is_excluded_from_auto_shadow(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    ohlc = tmp_path / "ohlc.csv"
    setups.write_text(
        "setup_id,symbol,market_group,timeframe,setup_type,strategy,direction,setup_quality_score,timing_state,macd_breakout_timing_state,macd_breakout_level,is_late,is_invalidated\n"
        "s1,EURUSD.r,Forex Majors,H1,macd_breakout,macd_breakout,long,2,entry_review,entry_review,1.1,False,False\n",
        encoding="utf-8",
    )
    ohlc.write_text(
        "market_group,symbol,timeframe,timestamp,open,high,low,close\n"
        "Forex Majors,EURUSD.r,H1,2026-06-08 10:00:00,1.09,1.11,1.08,1.105\n",
        encoding="utf-8",
    )

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=ohlc,
            allow_missing_inputs=True,
        )
    )

    excluded_path = tmp_path / "out" / "tables" / "excluded_from_automation_audit.csv"
    excluded = excluded_path.read_text(encoding="utf-8")

    assert result.shadow_rows == []
    assert "below_min_quality" in excluded
    assert "setup_quality_below_min_auto_quality_4" in excluded
    assert result.run_meta["automation_scope_low_quality_count"] == 1
    assert result.run_meta["setups_excluded_from_shadow_decisions_count"] == 1


def test_high_quality_macd_can_trigger_shadow_review(tmp_path: Path) -> None:
    setups = tmp_path / "setups.csv"
    ohlc = tmp_path / "ohlc.csv"
    setups.write_text(
        "setup_id,symbol,market_group,timeframe,setup_type,strategy,direction,setup_quality_score,timing_state,macd_breakout_timing_state,macd_breakout_level,is_late,is_invalidated\n"
        "s1,EURUSD.r,Forex Majors,H1,macd_breakout,macd_breakout,long,4,entry_review,entry_review,1.1,False,False\n",
        encoding="utf-8",
    )
    ohlc.write_text(
        "market_group,symbol,timeframe,timestamp,open,high,low,close\n"
        "Forex Majors,EURUSD.r,H1,2026-06-08 10:00:00,1.09,1.11,1.08,1.105\n",
        encoding="utf-8",
    )

    result = execute(
        Mt5ShadowConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            screener_setups_csv=setups,
            ohlc_csv=ohlc,
            allow_missing_inputs=True,
        )
    )

    assert result.shadow_rows[0]["automation_scope"] == "auto_candidate"
    assert result.shadow_rows[0]["shadow_state"] == "would_trigger"
    assert result.shadow_rows[0]["can_send_order"] is False


def test_run_meta_is_fail_closed(tmp_path: Path) -> None:
    out = tmp_path / "out"
    execute(Mt5ShadowConfig(output_dir=out, doc_path=tmp_path / "doc.md", fixture_mode=True))
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["mt5_connected"] is False
    assert meta["mt5_connection_attempted"] is False
    assert meta["mt5_orders_enabled"] is False
    assert meta["mt5_orders_sent"] == 0
    assert meta["can_send_order_any_true"] is False
    assert meta["can_execute_order_any_true"] is False
    assert meta["telegram_connected"] is False
    assert meta["sql_real_written"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False


def test_no_trading_tokens_exist_in_module_source() -> None:
    source = Path(mt5_shadow.__file__).read_text(encoding="utf-8")
    forbidden = [
        "order" + "_send",
        "TRADE_ACTION_" + "DEAL",
        "TRADE_ACTION_" + "PENDING",
        "position" + "_close",
    ]
    for token in forbidden:
        assert token not in source
