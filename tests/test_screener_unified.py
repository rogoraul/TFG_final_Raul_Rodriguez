from __future__ import annotations

import json
import csv
from pathlib import Path

from trading_center.readonly_dashboard import write_csv
from trading_center.screener_unified import (
    ALLOWED_TIMING_STATES,
    fib_limit_timing_fields,
    main,
    rsi_trend_reversal_timing,
    trend_compatibility_for_setup,
)


def _fixture_files(tmp_path: Path) -> dict[str, Path]:
    market = tmp_path / "market_radar.csv"
    ohlc = tmp_path / "ohlc_mtf.csv"
    weave = tmp_path / "weavecount.csv"
    snapshot = tmp_path / "snapshot.csv"
    macd_enriched = tmp_path / "macd_breakout_enriched_setups.csv"
    macd_layers = tmp_path / "macd_breakout_chart_layers.csv"
    fibonacci = tmp_path / "fibonacci_context.csv"
    fibonacci_layers = tmp_path / "fibonacci_chart_layers.csv"
    fib_review = tmp_path / "fib_limit_visual_case_review.csv"
    fib_sample = tmp_path / "fib_limit_visual_sample_selection.csv"
    fib_chart = tmp_path / "fib_limit_review.png"
    fib_chart.write_bytes(b"\x89PNG\r\n\x1a\n")
    write_csv(
        market,
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "as_of": "2026-03-17T10:00:00",
                "m15_trend": "bullish",
                "h1_trend": "bullish",
                "h4_trend": "bullish",
                "d1_trend": "mixed",
                "h1_rsi_signal": "bullish_oversold",
                "atr_pct_h1_ratio": "1.05",
            },
            {
                "symbol": "US500",
                "market_group": "Index",
                "as_of": "2026-03-17T10:00:00",
                "m15_trend": "mixed",
                "h1_trend": "mixed",
                "h4_trend": "mixed",
                "d1_trend": "mixed",
                "atr_pct_h1_ratio": "2.10",
            },
        ],
    )
    write_csv(
        ohlc,
        [
            {"symbol": "EURUSD.r", "market_group": "Forex Majors", "timeframe": "H1", "timestamp": "2026-03-16 08:00:00", "open": "1.10", "high": "1.105", "low": "1.095", "close": "1.100"},
            {"symbol": "EURUSD.r", "market_group": "Forex Majors", "timeframe": "H1", "timestamp": "2026-03-16 09:00:00", "open": "1.10", "high": "1.106", "low": "1.096", "close": "1.104"},
            {"symbol": "EURUSD.r", "market_group": "Forex Majors", "timeframe": "H1", "timestamp": "2026-03-17 09:00:00", "open": "1.104", "high": "1.108", "low": "1.101", "close": "1.105"},
            {"symbol": "EURUSD.r", "market_group": "Forex Majors", "timeframe": "M15", "timestamp": "2026-03-17 09:45:00", "open": "1.104", "high": "1.106", "low": "1.103", "close": "1.105"},
            {"symbol": "US500", "market_group": "Index", "timeframe": "H1", "timestamp": "2026-03-17 09:00:00", "open": "5000", "high": "5010", "low": "4990", "close": "5001"},
        ],
    )
    write_csv(
        weave,
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "count_label": "W2?",
                "quality_status": "media",
                "quality_score": "3",
            }
        ],
    )
    write_csv(
        snapshot,
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "strategy": "enbolsa:macd_breakout",
                "timeframe_ltf": "H1",
                "side": "BUY",
                "signal_state": "watching_setup",
            }
        ],
    )
    write_csv(
        macd_enriched,
        [
            {
                "enrichment_id": "enrich-eurusd-long",
                "generated_at": "2026-03-17T10:00:00",
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "setup_id": "101",
                "side": "BUY",
                "signal_state": "watching_setup",
                "watcher_reason": "fixture_recent_breakout_and_macd",
                "setup_active": "True",
                "setup_age": "1",
                "w1_start_time": "2026-03-16 08:00:00",
                "w1_end_time": "2026-03-17 08:00:00",
                "w1_start_price": "1.095",
                "w1_end_price": "1.110",
                "w2_swing_time": "2026-03-17 09:00:00",
                "w2_swing_price": "1.103",
                "breakout_level": "1.106",
                "breakout_level_type": "regression_trendline_break",
                "last_breakout_time": "2026-03-17 09:00:00",
                "bars_since_breakout": "1",
                "macd_cross_state": "recent",
                "last_macd_cross_time": "2026-03-17 09:00:00",
                "bars_since_macd_cross": "1",
                "macd_memory_bars": "5",
                "sl_study": "1.103",
                "tp1_study": "1.112",
                "tp2_study": "1.119",
                "invalidated": "False",
                "late": "False",
                "timing_state": "entry_review",
                "timing_priority": "1",
                "timing_reason": "ruptura y cruce MACD recientes dentro de memoria; revisar el grafico ahora",
                "missing_context_reason": "",
                "source_snapshot": str(snapshot),
                "source_watchlist": "",
                "source_ohlc": str(ohlc),
                "is_signal": "False",
                "is_study_only": "True",
                "can_execute_order": "False",
                "would_send_to_mt5": "False",
                "would_send_telegram_order": "False",
            },
            {
                "enrichment_id": "enrich-eurusd-h4-long",
                "generated_at": "2026-03-17T10:00:00",
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H4",
                "setup_id": "202",
                "side": "BUY",
                "signal_state": "watching_setup",
                "watcher_reason": "fixture_h4_recent_breakout_and_macd",
                "setup_active": "True",
                "setup_age": "1",
                "w1_start_time": "2026-03-14 08:00:00",
                "w1_end_time": "2026-03-16 08:00:00",
                "w1_start_price": "1.090",
                "w1_end_price": "1.120",
                "w2_swing_time": "2026-03-17 08:00:00",
                "w2_swing_price": "1.104",
                "breakout_level": "1.111",
                "breakout_level_type": "regression_trendline_break",
                "last_breakout_time": "2026-03-17 08:00:00",
                "bars_since_breakout": "1",
                "macd_cross_state": "recent",
                "last_macd_cross_time": "2026-03-17 08:00:00",
                "bars_since_macd_cross": "1",
                "macd_memory_bars": "5",
                "sl_study": "1.104",
                "tp1_study": "1.130",
                "tp2_study": "1.148",
                "invalidated": "False",
                "late": "False",
                "timing_state": "entry_review",
                "timing_priority": "1",
                "timing_reason": "ruptura y cruce MACD H4 recientes dentro de memoria; revisar el grafico ahora",
                "missing_context_reason": "",
                "source_snapshot": str(snapshot),
                "source_watchlist": "",
                "source_ohlc": str(ohlc),
                "is_signal": "False",
                "is_study_only": "True",
                "can_execute_order": "False",
                "would_send_to_mt5": "False",
                "would_send_telegram_order": "False",
            }
        ],
    )
    write_csv(
        macd_layers,
        [
            {
                "layer_id": "enrich-eurusd-long|macd_w1_leg",
                "enrichment_id": "enrich-eurusd-long",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "layer_type": "macd_w1_leg",
                "label": "W1 estudio",
                "x0": "2026-03-16 08:00:00",
                "x1": "2026-03-17 08:00:00",
                "y0": "1.095",
                "y1": "1.110",
                "price": "",
                "timestamp": "",
                "style": "line:#58e6d3",
                "source_field": "w1_start_price|w1_end_price",
                "is_study_only": "True",
            },
            {
                "layer_id": "enrich-eurusd-long|macd_breakout_level",
                "enrichment_id": "enrich-eurusd-long",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "layer_type": "macd_breakout_level",
                "label": "Ruptura estudio",
                "x0": "2026-03-17 08:00:00",
                "x1": "2026-03-17 10:00:00",
                "y0": "1.106",
                "y1": "1.106",
                "price": "1.106",
                "timestamp": "",
                "style": "dash:#ffd166",
                "source_field": "breakout_level",
                "is_study_only": "True",
            },
            {
                "layer_id": "enrich-eurusd-long|macd_cross_marker",
                "enrichment_id": "enrich-eurusd-long",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "layer_type": "macd_cross_marker",
                "label": "Cruce MACD",
                "x0": "",
                "x1": "",
                "y0": "",
                "y1": "",
                "price": "1.105",
                "timestamp": "2026-03-17 09:00:00",
                "style": "marker:#ffe082",
                "source_field": "last_macd_cross_time",
                "is_study_only": "True",
            },
        ],
    )
    write_csv(
        fibonacci,
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "swing_direction": "bullish",
                "swing_start_time": "2026-03-16 08:00:00",
                "swing_end_time": "2026-03-17 09:00:00",
                "swing_start_price": "1.095",
                "swing_end_price": "1.110",
                "nearest_fib_level": "Fib 61.8",
                "nearest_fib_ratio": "0.618",
                "nearest_fib_distance_pct": "0.04",
                "fibonacci_context": "cerca Fib 61.8 (0.04%)",
                "fibonacci_status": "fib_near_price",
                "swing_quality": "media",
                "is_signal": "False",
                "is_study_only": "True",
                "can_execute_order": "False",
                "would_send_to_mt5": "False",
                "would_send_telegram_order": "False",
            }
        ],
    )
    write_csv(
        fibonacci_layers,
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "layer_type": "fibonacci_0_0",
                "label": "Fib 0",
                "price": "1.110",
                "start_time": "2026-03-16 08:00:00",
                "end_time": "2026-03-17 09:00:00",
                "color": "#d7a84b",
                "style": "solid",
                "source": "fibonacci_context_v1",
                "is_operational": "False",
            },
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "layer_type": "fibonacci_1_0",
                "label": "Fib 100",
                "price": "1.095",
                "start_time": "2026-03-16 08:00:00",
                "end_time": "2026-03-17 09:00:00",
                "color": "#d7a84b",
                "style": "solid",
                "source": "fibonacci_context_v1",
                "is_operational": "False",
            },
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "layer_type": "fibonacci_0_618",
                "label": "Fib 61.8",
                "price": "1.103",
                "start_time": "2026-03-16 08:00:00",
                "end_time": "2026-03-17 09:00:00",
                "color": "#c793ff",
                "style": "dash",
                "source": "fibonacci_context_v1",
                "is_operational": "False",
            },
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "layer_type": "fibonacci_1_272",
                "label": "Fib ext 1.272",
                "price": "1.116",
                "start_time": "2026-03-16 08:00:00",
                "end_time": "2026-03-17 09:00:00",
                "color": "#8f6bd1",
                "style": "dot",
                "source": "fibonacci_context_v1",
                "is_operational": "False",
            }
        ],
    )
    write_csv(
        fib_review,
        [
            {
                "case_id": "fib_sq_fixture_001",
                "symbol": "EURUSD.r",
                "group": "Forex Majors",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "direction": "1",
                "visual_classification": "visually_defensible",
                "visual_rationale": "W1 1.20%; 4.00 ATR; 25 barras; W2 retr 0.62",
                "w1_size_pct": "1.20",
                "w1_atr_multiple": "4.0",
                "w1_bars": "25",
                "w2_retr_pct": "0.62",
                "chart_file": str(fib_chart),
            }
        ],
    )
    write_csv(
        fib_sample,
        [
            {
                "case_id": "fib_sq_fixture_001",
                "symbol": "EURUSD.r",
                "Group": "Forex Majors",
                "direction": "1",
                "setup_id": "fixture",
                "entry_time": "2026-03-17 08:00:00",
                "entry_price": "1.103",
                "stop_price": "1.095",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "W1_START_PRICE": "1.095",
                "W1_END_PRICE": "1.110",
                "W1_SIZE": "0.015",
                "W1_BARS": "25",
                "W2_EXTREME_PRICE": "1.101",
                "W2_RETR_PCT": "0.62",
                "W2_SWING_PRICE": "1.101",
                "FIB_LEVEL_0.618": "1.103",
                "TARGET_1.0": "1.116",
                "TARGET_1.618": "1.124",
                "last_exit_time": "2026-03-17 12:00:00",
            }
        ],
    )
    return {
        "market": market,
        "ohlc": ohlc,
        "weave": weave,
        "snapshot": snapshot,
        "macd_enriched": macd_enriched,
        "macd_layers": macd_layers,
        "fibonacci": fibonacci,
        "fibonacci_layers": fibonacci_layers,
        "fib_review": fib_review,
        "fib_sample": fib_sample,
    }


def test_screener_unified_cli_generates_fail_closed_artifacts(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    output_dir = tmp_path / "out"
    main(
        [
            "--market-radar-csv",
            str(files["market"]),
            "--ohlc-csv",
            str(files["ohlc"]),
            "--weavecount-csv",
            str(files["weave"]),
            "--snapshot-csv",
            str(files["snapshot"]),
            "--macd-breakout-enriched-csv",
            str(files["macd_enriched"]),
            "--macd-breakout-chart-layers-csv",
            str(files["macd_layers"]),
            "--fibonacci-context-csv",
            str(files["fibonacci"]),
            "--fibonacci-layers-csv",
            str(files["fibonacci_layers"]),
            "--fib-limit-review-csv",
            str(files["fib_review"]),
            "--fib-limit-sample-csv",
            str(files["fib_sample"]),
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
            "--design-doc-path",
            str(tmp_path / "missing_design.md"),
        ]
    )

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    setups = (output_dir / "screener_setups.csv").read_text(encoding="utf-8")
    matrix = (output_dir / "screener_asset_matrix.csv").read_text(encoding="utf-8")
    layers = (output_dir / "screener_chart_layers.csv").read_text(encoding="utf-8")
    matrix_rows = list(csv.DictReader((output_dir / "screener_asset_matrix.csv").read_text(encoding="utf-8").splitlines()))
    setup_rows = list(csv.DictReader((output_dir / "screener_setups.csv").read_text(encoding="utf-8").splitlines()))
    layer_rows = list(csv.DictReader((output_dir / "screener_chart_layers.csv").read_text(encoding="utf-8").splitlines()))
    fib_live_rows = [row for row in setup_rows if row["setup_type"] == "fib_limit_live_candidate"]
    fib_swing_rows = [row for row in layer_rows if row["layer_type"] == "fib_limit_study_swing_0_100"]

    assert run_meta["screener_unified_implemented"] is True
    assert run_meta["artifact_first"] is True
    assert run_meta["is_signal"] is False
    assert run_meta["sql_real_written"] is False
    assert run_meta["db_connected"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["telegram_connected"] is False
    assert run_meta["orders_sent"] == 0
    assert run_meta["signals_generated"] is False
    assert run_meta["wavecount_used_as_filter"] is False
    assert run_meta["fibonacci_context_consumed"] is True
    assert run_meta["fib_limit_implemented"] is True
    assert run_meta["fib_limit_live_detector_implemented"] is True
    assert run_meta["fib_limit_live_candidates_count"] >= 1
    assert run_meta["fib_limit_historical_review_available"] is True
    assert run_meta["fib_limit_swing_quality_consumed"] is False
    assert run_meta["fib_limit_setups_count"] == 0
    assert run_meta["fib_limit_timing_implemented"] is True
    assert run_meta["setup_timing_implemented"] is True
    assert run_meta["setup_timing_strategy_scope"] == "fib_limit_macd_breakout_and_rsi_trend_reversal"
    assert run_meta["rsi_trend_reversal_implemented"] is True
    assert run_meta["rsi_trend_reversal_sl_tp_defined"] is False
    assert run_meta["macd_breakout_enrichment_integrated"] is True
    assert run_meta["macd_breakout_highlighted_count"] >= 1
    assert "macd_breakout" in setups
    assert "trend_alignment" not in setups
    assert "pivot_reaction_candidate" not in setups
    assert "round_level_candidate" not in setups
    assert "previous_day_high_low_candidate" not in setups
    assert "rsi_extreme_with_context" not in setups
    assert "fibonacci_zone_candidate" not in setups
    assert "fib_limit" in matrix
    assert "fib_limit" in matrix
    assert next(row for row in matrix_rows if row["symbol"] == "EURUSD.r")["fib_limit_chip"].startswith("live Fib 61.8")
    assert "fib_limit_live_candidate" in setups
    assert "fib_limit_swing_quality" not in setups
    assert "fib_limit_review.png" not in setups
    assert "fib_limit_live_fibonacci_0_618" not in layers
    assert "fib_limit_study_swing_0_100" in layers
    assert "Swing 0-100 estudio" in layers
    assert "fib_limit_study_zone_618" in layers
    assert "Entrada 61.8 estudio" in layers
    assert "fib_limit_study_sl" in layers
    assert "SL estudio" in layers
    assert "fib_limit_study_tp1" in layers
    assert "TP1 estudio" in layers
    assert "fib_limit_study_tp2" in layers
    assert "TP2 estudio" in layers
    assert "Fib 61.8 estudio" not in layers
    assert "Fib 0.618 / entrada estudio" not in layers
    assert "Stop estudio" not in layers
    assert fib_swing_rows
    assert all(row["start_price"] and row["end_price"] for row in fib_swing_rows)
    assert all(row["start_time"] == "2026-03-16 08:00:00" and row["end_time"] == "2026-03-17 09:00:00" for row in fib_swing_rows)
    assert "cerca Fib 61.8" in setups
    assert "fibonacci_zone_context" not in setups
    assert "Fib 61.8" in matrix
    assert "Fib 61.8" in layers
    assert "fibonacci_context_v1" in layers
    assert "revision codex pendiente" in matrix
    assert "trend_detail_context" in setups.splitlines()[0]
    assert "trend_compatibility" in setups.splitlines()[0]
    assert "trend_compatibility_reason" in setups.splitlines()[0]
    assert "timing_state" in setups.splitlines()[0]
    assert "timing_priority" in setups.splitlines()[0]
    assert "trigger_level" in setups.splitlines()[0]
    assert "macd_breakout_timing_state" in setups.splitlines()[0]
    assert "macd_breakout_level" in setups.splitlines()[0]
    assert "M15:" in setups
    assert "R2 previo" in layers
    assert "R3 previo" in layers
    assert "S2 previo" in layers
    assert "S3 previo" in layers
    assert "Nivel redondo superior" in layers
    assert "Nivel redondo inferior" in layers or "Nivel redondo actual" in layers
    assert "#a56cff" in layers
    assert "solid" in layers
    assert "ohlc_nearby_round_levels" in layers
    assert "Pivot previo" not in layers
    assert "R1 previo" not in layers
    assert "S1 previo" not in layers
    assert "trade_ready" not in setups
    assert fib_live_rows
    assert all(row["timing_state"] in ALLOWED_TIMING_STATES for row in setup_rows)
    assert all(row["timing_priority"] for row in setup_rows)
    assert all(row["timing_source"] == "fib_limit_timing_v1" for row in fib_live_rows)
    macd_rows = [row for row in setup_rows if row["setup_type"] == "macd_breakout"]
    assert macd_rows
    assert all(row["timing_source"] == "macd_breakout_enrichment_v1" for row in macd_rows)
    assert any(row["macd_breakout_timing_state"] == "entry_review" for row in macd_rows)
    assert set(row["timeframe"] for row in macd_rows if row["symbol"] == "EURUSD.r").issubset({"H1", "H4"})
    assert any(row["timeframe"] == "H1" for row in macd_rows if row["symbol"] == "EURUSD.r")
    assert any(row["layer_type"] == "macd_breakout_level" for row in layer_rows)
    assert any(row["layer_type"] == "macd_w1_leg" for row in layer_rows)
    assert all(row["trigger_level_type"] == "Fib 61.8" for row in fib_live_rows)
    assert all(row["trigger_level"] for row in fib_live_rows)
    assert all(row["distance_to_trigger_pct"] for row in fib_live_rows)
    assert all(row["is_signal"] == "False" for row in fib_live_rows)
    assert all(row["can_execute_order"] == "False" for row in fib_live_rows)
    assert any(row["timing_state"] in {"touching_level", "entry_review"} for row in fib_live_rows)
    assert all(row["timing_source"] != "fib_limit_timing_v1" for row in setup_rows if row["setup_type"] != "fib_limit_live_candidate")
    assert all(row["trend_compatibility"] in {"compatible", "mixed", "against"} for row in setup_rows)
    assert all(row["trend_compatibility_reason"] for row in setup_rows)
    assert run_meta["trend_compatibility_implemented"] is True
    assert (output_dir / "tables" / "trend_compatibility_audit.csv").exists()
    assert (output_dir / "tables" / "rsi_trend_reversal_audit.csv").exists()


def test_rsi_trend_reversal_timing_detects_cross_back_with_triple_alignment() -> None:
    radar_row = {
        "m15_trend": "bearish",
        "h1_trend": "bearish",
        "h4_trend": "bearish",
        "d1_trend": "mixed",
    }
    closes = [1.00, 1.02, 1.04, 1.06, 1.08, 1.10, 1.12, 1.14, 1.16, 1.18, 1.20, 1.22, 1.24, 1.26, 1.28, 1.15]
    rows = [
        {
            "timestamp": f"2026-03-17 {index:02d}:00:00",
            "open": str(close),
            "high": str(close + 0.001),
            "low": str(close - 0.001),
            "close": str(close),
        }
        for index, close in enumerate(closes)
    ]

    timing = rsi_trend_reversal_timing(radar_row=radar_row, timeframe="M15", ohlc_rows=rows)

    assert timing is not None
    assert timing["timing_state"] == "entry_review"
    assert timing["direction"] == "short"
    assert timing["trigger_level"] == "70"
    assert timing["trigger_level_type"] == "RSI 70 cruce de vuelta"
    assert timing["timing_source"] == "rsi_trend_reversal_v1"


def test_rsi_trend_reversal_timing_requires_clean_alignment() -> None:
    radar_row = {
        "m15_trend": "bearish",
        "h1_trend": "bullish",
        "h4_trend": "bearish",
        "d1_trend": "mixed",
    }
    closes = [1.00, 1.02, 1.04, 1.06, 1.08, 1.10, 1.12, 1.14, 1.16, 1.18, 1.20, 1.22, 1.24, 1.26, 1.28, 1.15]
    rows = [
        {
            "timestamp": f"2026-03-17 {index:02d}:00:00",
            "open": str(close),
            "high": str(close + 0.001),
            "low": str(close - 0.001),
            "close": str(close),
        }
        for index, close in enumerate(closes)
    ]

    assert rsi_trend_reversal_timing(radar_row=radar_row, timeframe="M15", ohlc_rows=rows) is None


def test_rsi_trend_reversal_setup_carries_context_layers(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    output_dir = tmp_path / "out"
    write_csv(
        files["market"],
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "as_of": "2026-03-17T10:00:00",
                "m15_trend": "bullish",
                "h1_trend": "bullish",
                "h4_trend": "bullish",
                "d1_trend": "bullish",
                "h1_rsi_signal": "neutral",
                "atr_pct_h1_ratio": "1.05",
            }
        ],
    )
    closes = [1.30, 1.28, 1.26, 1.24, 1.22, 1.20, 1.18, 1.16, 1.14, 1.12, 1.10, 1.08, 1.06, 1.04, 1.02, 1.15]
    write_csv(
        files["ohlc"],
        [
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "timestamp": f"2026-03-{16 + index // 10:02d} {index % 10:02d}:00:00",
                "open": f"{close:.5f}",
                "high": f"{close + 0.001:.5f}",
                "low": f"{close - 0.001:.5f}",
                "close": f"{close:.5f}",
            }
            for index, close in enumerate(closes)
        ],
    )
    main(
        [
            "--market-radar-csv",
            str(files["market"]),
            "--ohlc-csv",
            str(files["ohlc"]),
            "--weavecount-csv",
            str(files["weave"]),
            "--snapshot-csv",
            str(files["snapshot"]),
            "--macd-breakout-enriched-csv",
            str(files["macd_enriched"]),
            "--macd-breakout-chart-layers-csv",
            str(files["macd_layers"]),
            "--fibonacci-context-csv",
            str(files["fibonacci"]),
            "--fibonacci-layers-csv",
            str(files["fibonacci_layers"]),
            "--fib-limit-review-csv",
            str(files["fib_review"]),
            "--fib-limit-sample-csv",
            str(files["fib_sample"]),
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
            "--design-doc-path",
            str(tmp_path / "missing_design.md"),
        ]
    )

    setup_rows = list(csv.DictReader((output_dir / "screener_setups.csv").read_text(encoding="utf-8").splitlines()))
    layer_rows = list(csv.DictReader((output_dir / "screener_chart_layers.csv").read_text(encoding="utf-8").splitlines()))
    rsi_setup = next(row for row in setup_rows if row["setup_type"] == "rsi_trend_reversal")
    rsi_layers = [row for row in layer_rows if row["setup_id"] == rsi_setup["setup_id"]]
    layer_types = {row["layer_type"] for row in rsi_layers}

    assert rsi_setup["timing_state"] == "entry_review"
    assert rsi_setup["is_signal"] == "False"
    assert rsi_setup["can_execute_order"] == "False"
    assert "rsi_entry_marker" in layer_types
    assert {"r2", "r3", "s2", "s3"} <= layer_types
    assert any(row["layer_type"].startswith("round_level") for row in rsi_layers)
    assert any(row["layer_type"].startswith("fibonacci") for row in rsi_layers)


def test_trend_compatibility_for_setup_labels_directional_context() -> None:
    assert trend_compatibility_for_setup("M15/H1/H4 bullish", "long")[0] == "compatible"
    assert trend_compatibility_for_setup("H1/H4/D1 bearish", "long")[0] == "against"
    assert trend_compatibility_for_setup("sin alineacion limpia", "short")[0] == "mixed"


def test_screener_quality_score_stays_in_visual_range(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    output_dir = tmp_path / "out"
    main(
        [
            "--market-radar-csv",
            str(files["market"]),
            "--ohlc-csv",
            str(files["ohlc"]),
            "--weavecount-csv",
            str(files["weave"]),
            "--snapshot-csv",
            str(files["snapshot"]),
            "--macd-breakout-enriched-csv",
            str(files["macd_enriched"]),
            "--macd-breakout-chart-layers-csv",
            str(files["macd_layers"]),
            "--fibonacci-context-csv",
            str(files["fibonacci"]),
            "--fibonacci-layers-csv",
            str(files["fibonacci_layers"]),
            "--fib-limit-review-csv",
            str(files["fib_review"]),
            "--fib-limit-sample-csv",
            str(files["fib_sample"]),
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
            "--design-doc-path",
            str(tmp_path / "missing_design.md"),
        ]
    )
    rows = [
        line.split(",")
        for line in (output_dir / "screener_setups.csv").read_text(encoding="utf-8").splitlines()[1:]
        if line.strip()
    ]
    header = (output_dir / "screener_setups.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    score_index = header.index("setup_quality_score")

    assert rows
    assert all(1 <= int(float(row[score_index])) <= 5 for row in rows)


def test_screener_missing_trigger_or_ohlc_falls_back_to_no_timing_context(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    write_csv(files["fibonacci_layers"], [])
    output_dir = tmp_path / "out"
    main(
        [
            "--market-radar-csv",
            str(files["market"]),
            "--ohlc-csv",
            str(files["ohlc"]),
            "--weavecount-csv",
            str(files["weave"]),
            "--snapshot-csv",
            str(files["snapshot"]),
            "--macd-breakout-enriched-csv",
            str(files["macd_enriched"]),
            "--macd-breakout-chart-layers-csv",
            str(files["macd_layers"]),
            "--fibonacci-context-csv",
            str(files["fibonacci"]),
            "--fibonacci-layers-csv",
            str(files["fibonacci_layers"]),
            "--fib-limit-review-csv",
            str(files["fib_review"]),
            "--fib-limit-sample-csv",
            str(files["fib_sample"]),
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
            "--design-doc-path",
            str(tmp_path / "missing_design.md"),
        ]
    )

    rows = list(csv.DictReader((output_dir / "screener_setups.csv").read_text(encoding="utf-8").splitlines()))
    fib_live = next(row for row in rows if row["setup_type"] == "fib_limit_live_candidate")

    assert fib_live["timing_state"] == "no_timing_context"
    assert fib_live["timing_priority"] == "14"
    assert fib_live["trigger_level"] == ""
    assert fib_live["timing_reason"]


def test_fib_limit_timing_late_has_priority_over_reaction_candidate() -> None:
    timing = fib_limit_timing_fields(
        market_group="Forex Majors",
        timeframe="H1",
        fib_row={"swing_direction": "bullish"},
        fib_layers=[
            {"label": "Fib 61.8", "price": "1.1000"},
            {"label": "Fib 100", "price": "1.0900"},
        ],
        ohlc_rows=[
            {"timestamp": "2026-03-17 07:00:00", "open": "1.0990", "high": "1.1010", "low": "1.0985", "close": "1.1005"},
            {"timestamp": "2026-03-17 08:00:00", "open": "1.1005", "high": "1.1080", "low": "1.1002", "close": "1.1070"},
            {"timestamp": "2026-03-17 09:00:00", "open": "1.1070", "high": "1.1095", "low": "1.1060", "close": "1.1090"},
        ],
        timing_artifact="fixture",
    )

    assert timing["reaction_detected"] is True
    assert timing["is_late"] is True
    assert timing["timing_state"] == "late"
    assert timing["timing_priority"] == 10


def test_fib_limit_entry_review_uses_ohlc_touch_without_reaction_requirement() -> None:
    timing = fib_limit_timing_fields(
        market_group="Forex Majors",
        timeframe="H1",
        fib_row={"swing_direction": "bullish"},
        fib_layers=[
            {"label": "Fib 61.8", "price": "1.1000"},
            {"label": "Fib 100", "price": "1.0900"},
        ],
        ohlc_rows=[
            {"timestamp": "2026-03-17 07:00:00", "open": "1.1040", "high": "1.1050", "low": "1.0995", "close": "1.0998"},
            {"timestamp": "2026-03-17 08:00:00", "open": "1.1002", "high": "1.1004", "low": "1.0996", "close": "1.0999"},
        ],
        timing_artifact="fixture",
    )

    assert timing["reaction_detected"] is False
    assert timing["timing_state"] == "entry_review"
    assert timing["entry_review_status"] == "review_now"
    assert "toque OHLC" in timing["timing_reason"]


def test_screener_empty_input_requires_flag(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    empty = tmp_path / "empty.csv"
    write_csv(empty, [])

    main(
        [
            "--market-radar-csv",
            str(empty),
            "--ohlc-csv",
            str(empty),
            "--output-dir",
            str(output_dir),
            "--allow-empty",
            "--doc-path",
            str(tmp_path / "doc.md"),
            "--design-doc-path",
            str(tmp_path / "missing_design.md"),
        ]
    )

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["setups_count"] == 0
    assert run_meta["asset_matrix_rows"] == 0
    assert run_meta["sql_real_written"] is False


def test_screener_can_include_historical_fib_limit_only_when_explicit(tmp_path: Path) -> None:
    files = _fixture_files(tmp_path)
    output_dir = tmp_path / "out"
    main(
        [
            "--market-radar-csv",
            str(files["market"]),
            "--ohlc-csv",
            str(files["ohlc"]),
            "--weavecount-csv",
            str(files["weave"]),
            "--snapshot-csv",
            str(files["snapshot"]),
            "--macd-breakout-enriched-csv",
            str(files["macd_enriched"]),
            "--macd-breakout-chart-layers-csv",
            str(files["macd_layers"]),
            "--fibonacci-context-csv",
            str(files["fibonacci"]),
            "--fibonacci-layers-csv",
            str(files["fibonacci_layers"]),
            "--fib-limit-review-csv",
            str(files["fib_review"]),
            "--fib-limit-sample-csv",
            str(files["fib_sample"]),
            "--include-historical-fib-limit",
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
            "--design-doc-path",
            str(tmp_path / "missing_design.md"),
        ]
    )
    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    setups = (output_dir / "screener_setups.csv").read_text(encoding="utf-8")
    layers = (output_dir / "screener_chart_layers.csv").read_text(encoding="utf-8")

    assert run_meta["fib_limit_implemented"] is True
    assert run_meta["fib_limit_swing_quality_consumed"] is True
    assert run_meta["fib_limit_setups_count"] >= 1
    assert "fib_limit_swing_quality" in setups
    assert "fib_limit_review.png" in setups
    assert "Fib 0.618 / entrada estudio" in layers
