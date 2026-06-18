from __future__ import annotations

import json
import py_compile
from pathlib import Path

import pandas as pd

from trading_center import macd_breakout_enrichment as enrich


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _fixture_files(tmp_path: Path) -> dict[str, Path]:
    watcher_dir = tmp_path / "watcher"
    output_dir = tmp_path / "out"
    doc_path = tmp_path / "doc.md"
    snapshot = watcher_dir / "snapshot.csv"
    watchlist = watcher_dir / "watchlist.csv"
    ohlc = tmp_path / "ohlc_mtf.csv"

    write_csv(
        snapshot,
        [
            {
                "Group": "Forex Majors",
                "strategy": "enbolsa:macd_breakout",
                "symbol": "EURUSD.r",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "timestamp": "2026-03-17 09:00:00",
                "latest_closed_bar": True,
                "direction": 1,
                "side": "BUY",
                "setup_id": 101,
                "setup_active": True,
                "setup_age": 4,
                "raw_condition_ready": False,
                "fresh_signal": False,
                "already_seen": False,
                "entry_ready": False,
                "signal_state": "watching_setup",
                "reason": "waiting_for_trendline_and_macd_confirmation",
                "event_key": "",
                "entry": "",
                "sl": "",
                "tp1": "",
                "tp2": "",
                "risk_pct": "",
                "risk_amount": "",
                "w2_swing": 1.1010,
                "target_1_0": 1.1120,
                "target_1_618": 1.1190,
                "riskguard_accepted": False,
                "riskguard_reason": "",
                "riskguard_detail": "",
                "riskguard_message": "",
            },
            {
                "Group": "Forex Majors",
                "strategy": "enbolsa:macd_breakout",
                "symbol": "EURUSD.r",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "timestamp": "2026-03-17 09:00:00",
                "latest_closed_bar": True,
                "direction": -1,
                "side": "SELL",
                "setup_id": 102,
                "setup_active": True,
                "setup_age": 3,
                "raw_condition_ready": False,
                "fresh_signal": False,
                "already_seen": False,
                "entry_ready": False,
                "signal_state": "watching_setup",
                "reason": "setup_invalidated",
                "event_key": "",
                "entry": "",
                "sl": "",
                "tp1": "",
                "tp2": "",
                "risk_pct": "",
                "risk_amount": "",
                "w2_swing": "",
                "target_1_0": 1.0940,
                "target_1_618": 1.0880,
                "riskguard_accepted": False,
                "riskguard_reason": "",
                "riskguard_detail": "",
                "riskguard_message": "",
            },
            {
                "Group": "Forex Majors",
                "strategy": "enbolsa:macd_breakout",
                "symbol": "GBPUSD.r",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "timestamp": "2026-03-17 09:00:00",
                "latest_closed_bar": True,
                "direction": 1,
                "side": "BUY",
                "setup_id": 103,
                "setup_active": True,
                "setup_age": 2,
                "raw_condition_ready": False,
                "fresh_signal": False,
                "already_seen": False,
                "entry_ready": False,
                "signal_state": "watching_setup",
                "reason": "missing_w2_swing",
                "event_key": "",
                "entry": "",
                "sl": "",
                "tp1": "",
                "tp2": "",
                "risk_pct": "",
                "risk_amount": "",
                "w2_swing": "",
                "target_1_0": 1.2870,
                "target_1_618": 1.2920,
                "riskguard_accepted": False,
                "riskguard_reason": "",
                "riskguard_detail": "",
                "riskguard_message": "",
            },
        ],
    )
    write_csv(
        watchlist,
        [
            {
                "Group": "Forex Majors",
                "strategy": "enbolsa:macd_breakout",
                "symbol": "EURUSD.r",
                "side": "BUY",
                "setup_id": 101,
                "timestamp": "2026-03-17 09:00:00",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "watch_state": "watching_confirmation",
                "missing_confirmation": "trendline_break_or_macd_cross_within_memory",
                "w2_swing": 1.1010,
                "target_1_0": 1.1120,
                "target_1_618": 1.1190,
                "setup_age": 4,
                "event_key": "",
            }
        ],
    )

    h1_rows = []
    data = [
        ("2026-03-17 00:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
        ("2026-03-17 01:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
        ("2026-03-17 02:00:00", 1.1015, 1.1050, 1.1010, 1.1045),
        ("2026-03-17 03:00:00", 1.1045, 1.1060, 1.1020, 1.1025),
        ("2026-03-17 04:00:00", 1.1025, 1.1030, 1.1010, 1.1010),
        ("2026-03-17 05:00:00", 1.1010, 1.1020, 1.1005, 1.1015),
        ("2026-03-17 06:00:00", 1.1015, 1.1035, 1.1010, 1.1030),
        ("2026-03-17 07:00:00", 1.1030, 1.1065, 1.1025, 1.1060),
        ("2026-03-17 08:00:00", 1.1060, 1.1090, 1.1055, 1.1085),
        ("2026-03-17 09:00:00", 1.1085, 1.1110, 1.1080, 1.1105),
    ]
    for ts, o, h, l, c in data:
        h1_rows.append({"market_group": "Forex Majors", "symbol": "EURUSD.r", "timeframe": "H1", "timestamp": ts, "open": o, "high": h, "low": l, "close": c, "tick_volume": 1, "spread": 1, "real_volume": 0})
        h1_rows.append({"market_group": "Forex Majors", "symbol": "GBPUSD.r", "timeframe": "H1", "timestamp": ts, "open": o + 0.18, "high": h + 0.18, "low": l + 0.18, "close": c + 0.18, "tick_volume": 1, "spread": 1, "real_volume": 0})
    h4_rows = [
        {"market_group": "Forex Majors", "symbol": "EURUSD.r", "timeframe": "H4", "timestamp": "2026-03-16 20:00:00", "open": 1.0980, "high": 1.1040, "low": 1.0970, "close": 1.1030, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "EURUSD.r", "timeframe": "H4", "timestamp": "2026-03-17 00:00:00", "open": 1.1030, "high": 1.1060, "low": 1.1005, "close": 1.1020, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "EURUSD.r", "timeframe": "H4", "timestamp": "2026-03-17 04:00:00", "open": 1.1020, "high": 1.1090, "low": 1.1010, "close": 1.1085, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "EURUSD.r", "timeframe": "H4", "timestamp": "2026-03-17 08:00:00", "open": 1.1085, "high": 1.1110, "low": 1.1080, "close": 1.1105, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "GBPUSD.r", "timeframe": "H4", "timestamp": "2026-03-16 20:00:00", "open": 1.2780, "high": 1.2840, "low": 1.2770, "close": 1.2830, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "GBPUSD.r", "timeframe": "H4", "timestamp": "2026-03-17 00:00:00", "open": 1.2830, "high": 1.2860, "low": 1.2805, "close": 1.2820, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "GBPUSD.r", "timeframe": "H4", "timestamp": "2026-03-17 04:00:00", "open": 1.2820, "high": 1.2890, "low": 1.2810, "close": 1.2885, "tick_volume": 1, "spread": 0, "real_volume": 0},
        {"market_group": "Forex Majors", "symbol": "GBPUSD.r", "timeframe": "H4", "timestamp": "2026-03-17 08:00:00", "open": 1.2885, "high": 1.2910, "low": 1.2880, "close": 1.2905, "tick_volume": 1, "spread": 0, "real_volume": 0},
    ]
    write_csv(ohlc, h1_rows + h4_rows)
    return {
        "watcher_dir": watcher_dir,
        "snapshot": snapshot,
        "watchlist": watchlist,
        "ohlc": ohlc,
        "output_dir": output_dir,
        "doc_path": doc_path,
    }


def test_cli_generates_artifacts_and_fail_closed_run_meta(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    rc = enrich.main(
        [
            "--watcher-dir",
            str(files["watcher_dir"]),
            "--ohlc-csv",
            str(files["ohlc"]),
            "--output-dir",
            str(files["output_dir"]),
            "--doc-path",
            str(files["doc_path"]),
            "--fixture-mode",
        ]
    )
    assert rc == 0
    out = files["output_dir"]
    assert (out / "macd_breakout_enriched_setups.csv").exists()
    assert (out / "macd_breakout_enriched_setups.json").exists()
    assert (out / "macd_breakout_chart_layers.csv").exists()
    assert (out / "run_meta.json").exists()
    assert files["doc_path"].exists()
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["macd_breakout_strategy_modified"] is False
    assert meta["fib_limit_modified"] is False
    assert meta["backtests_executed"] is False
    assert meta["sql_real_written"] is False
    assert meta["db_connected"] is False
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False
    assert meta["is_signal_any_true"] is False
    assert meta["can_execute_order_any_true"] is False


def test_enriched_rows_keep_fail_closed_flags_and_state_precedence(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    config = enrich.EnrichmentConfig(
        watcher_dir=files["watcher_dir"],
        snapshot_csv=files["snapshot"],
        watchlist_csv=files["watchlist"],
        ohlc_csv=files["ohlc"],
        output_dir=files["output_dir"],
        doc_path=files["doc_path"],
        memory_bars=5,
        fixture_mode=True,
    )
    result = enrich.build_outputs(config)
    frame = result["enriched"]
    assert len(frame) == 3
    assert not frame["is_signal"].any()
    assert frame["is_study_only"].all()
    assert not frame["can_execute_order"].any()
    invalidated = frame.loc[frame["watcher_reason"] == "setup_invalidated"].iloc[0]
    assert invalidated["timing_state"] == "invalidated"
    missing = frame.loc[frame["watcher_reason"] == "missing_w2_swing"].iloc[0]
    assert missing["timing_state"] == "missing_context"
    waiting = frame.loc[frame["watcher_reason"] == "waiting_for_trendline_and_macd_confirmation"].iloc[0]
    assert waiting["timing_state"] in {"watching", "macd_pending", "breakout_recent", "macd_recent", "entry_review", "late", "missing_context"}
    assert waiting["timing_state"] != "invalidated"


def test_layers_skip_missing_structure_and_keep_study_levels(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    config = enrich.EnrichmentConfig(
        watcher_dir=files["watcher_dir"],
        snapshot_csv=files["snapshot"],
        watchlist_csv=files["watchlist"],
        ohlc_csv=files["ohlc"],
        output_dir=files["output_dir"],
        doc_path=files["doc_path"],
        memory_bars=5,
        fixture_mode=True,
    )
    result = enrich.build_outputs(config)
    layers = result["layers"]
    assert not layers.empty
    assert (layers["is_study_only"] == True).all()  # noqa: E712
    missing_id = result["enriched"].loc[result["enriched"]["watcher_reason"] == "missing_w2_swing", "enrichment_id"].iloc[0]
    missing_layers = layers.loc[layers["enrichment_id"] == missing_id]
    assert "macd_w2_retracement" not in set(missing_layers["layer_type"])
    assert "macd_w1_leg" not in set(missing_layers["layer_type"])
    waiting_id = result["enriched"].loc[result["enriched"]["watcher_reason"] == "waiting_for_trendline_and_macd_confirmation", "enrichment_id"].iloc[0]
    waiting_layers = layers.loc[layers["enrichment_id"] == waiting_id]
    assert {"macd_sl_study", "macd_tp1_study", "macd_tp2_study"}.issubset(set(waiting_layers["layer_type"]))


def test_py_compile_module(tmp_path: Path) -> None:
    compiled = tmp_path / "compiled.pyc"
    py_compile.compile(
        str(Path(__file__).resolve().parents[1] / "trading_center" / "macd_breakout_enrichment.py"),
        cfile=str(compiled),
        doraise=True,
    )
    assert compiled.exists()


def test_timing_rules_entry_review_and_late() -> None:
    state = enrich._timing_from_fields(
        invalidated=False,
        missing_context_reason="",
        breakout_pos=9,
        macd_cross_pos=8,
        current_pos=10,
        memory_bars=5,
        raw_condition_ready=False,
        setup_active=True,
        breakout_level=1.1,
        current_close=1.11,
    )
    assert state[0] == "entry_review"
    late = enrich._timing_from_fields(
        invalidated=False,
        missing_context_reason="",
        breakout_pos=1,
        macd_cross_pos=2,
        current_pos=10,
        memory_bars=5,
        raw_condition_ready=False,
        setup_active=True,
        breakout_level=1.1,
        current_close=1.11,
    )
    assert late[0] == "late"


def test_breakout_trendline_matches_breakout_level() -> None:
    highs = pd.Series([1.205, 1.180, 1.160, 1.140, 1.170, 1.190])
    start, end, projection = enrich._compute_breakout_trendline(highs, 0, 4, 1, projection_pos=5)
    level = enrich._compute_breakout_level(highs, 0, 4, 1)
    assert pd.notna(start)
    assert pd.notna(end)
    assert pd.notna(projection)
    assert end == level
    assert start > end
    assert projection < end


def test_breakout_trendline_uses_lows_for_short_side() -> None:
    lows = pd.Series([1.100, 1.120, 1.140, 1.160, 1.130, 1.110])
    start, end, projection = enrich._compute_breakout_trendline(lows, 0, 4, -1, projection_pos=5)
    assert pd.notna(start)
    assert pd.notna(end)
    assert pd.notna(projection)
    assert start < end
    assert projection > end


def test_directrix_layer_uses_late_style_when_timing_is_late() -> None:
    record = {
        "enrichment_id": "macd_breakout_enrichment_v1|EURUSD.r|H1|BUY|101",
        "symbol": "EURUSD.r",
        "timeframe": "H1",
        "side": "BUY",
        "generated_at": "2026-03-17 09:00:00",
        "w1_start_time": "2026-03-17 00:00:00",
        "w1_end_time": "2026-03-17 03:00:00",
        "w1_start_price": 1.2,
        "w1_end_price": 1.12,
        "w2_swing_time": "2026-03-17 05:00:00",
        "w2_swing_price": 1.16,
        "directrix_start_time": "2026-03-17 03:00:00",
        "directrix_end_time": "2026-03-17 08:00:00",
        "directrix_start_price": 1.16,
        "directrix_end_price": 1.13,
        "breakout_level": 1.13,
        "sl_study": "",
        "tp1_study": "",
        "tp2_study": "",
        "last_macd_cross_time": "",
        "last_breakout_time": "",
        "timing_state": "late",
    }
    layers = enrich._build_layers(record, 1.14)
    directrix = [layer for layer in layers if layer["layer_type"] == "macd_w2_directrix"]
    assert len(directrix) == 1
    assert directrix[0]["label"] == "Reg W2 highs tardia"
    assert str(directrix[0]["style"]).startswith("dot:")
    assert directrix[0]["source_field"] == "w2_high_regression_projected"


def test_timing_rules_precedence_invalidated_and_missing_context() -> None:
    invalidated = enrich._timing_from_fields(
        invalidated=True,
        missing_context_reason="",
        breakout_pos=9,
        macd_cross_pos=8,
        current_pos=10,
        memory_bars=5,
        raw_condition_ready=True,
        setup_active=True,
        breakout_level=1.1,
        current_close=1.11,
    )
    assert invalidated[0] == "invalidated"
    missing = enrich._timing_from_fields(
        invalidated=False,
        missing_context_reason="missing_w2_swing",
        breakout_pos=9,
        macd_cross_pos=8,
        current_pos=10,
        memory_bars=5,
        raw_condition_ready=True,
        setup_active=True,
        breakout_level=1.1,
        current_close=1.11,
    )
    assert missing[0] == "missing_context"
