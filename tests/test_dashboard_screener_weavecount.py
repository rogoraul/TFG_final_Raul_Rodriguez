from __future__ import annotations

import json
import base64
from pathlib import Path

import pytest

from trading_center.dash_readonly_app import (
    DEFAULT_LATEST_MANIFEST_JSON,
    _run_ai_analyst_gateway,
    ai_analyst_download_pdf_path,
    ai_analyst_gateway_status_line,
    build_h1_aux_wavecount_rows,
    build_manifest_refresh_state,
    build_refresh_status_payload,
    build_weavecount_screener_dashboard_rows,
    build_dash_data,
    build_dash_data_from_args,
    ai_analyst_correlation_options,
    ai_analyst_context_options,
    ai_analyst_control_visibility,
    ai_analyst_report_conclusion,
    ai_analyst_setup_options,
    ai_analyst_wave_options,
    correlation_rows_for_asset,
    dash_css,
    default_matrix_assets,
    dynamic_fibonacci_layers,
    lowess_line,
    load_latest_manifest_metadata,
    maybe_refresh_dash_data,
    matrix_assets_for_focus,
    mt5_shadow_state_label,
    mt5_shadow_status_label,
    mt5_shadow_summary,
    latest_or_fallback_dir,
    latest_or_fallback_path,
    normalize_matrix_assets,
    pair_return_points,
    create_app,
    filter_screener_setups,
    filter_universe_rows,
    filter_watchlist_rows,
    filter_wavecount_number_rows,
    filter_wavecount_rows,
    format_dashboard_timestamp,
    market_radar_summary,
    partial_correlation_rows,
    parse_args,
    refresh_decision_label,
    riskguard_decision_index,
    riskguard_decision_detail,
    riskguard_decision_label,
    riskguard_decision_summary,
    riskguard_status_label,
    rolling_correlation_series,
    rolling_rows_for_asset,
    rolling_window_for_timeframe,
    run_ai_analyst_correlation_review,
    run_ai_analyst_controlled_review,
    run_ai_analyst_market_review,
    run_ai_analyst_weavecount_review,
    screener_default_visible_layers,
    screener_layer_price_by_type,
    screener_layer_family,
    screener_layer_options_for,
    screener_score,
    screener_setup_figure,
    selected_wavecount_row,
    sender_status_label,
    manager_status_label,
    telegram_info_result_label,
    telegram_info_sent_label,
    telegram_info_status_label,
    wavecount_chart_data_uri,
    wavecount_chart_figure,
    wavecount_case_id,
    wavecount_direction_label,
    wavecount_number,
    wavecount_number_summary,
    wavecount_quality_status,
    wavecount_status,
    wavecount_structure_points,
    wavecount_wave_label,
    write_ai_analyst_pdf_report,
    write_dash_artifacts,
)

def test_watchlist_filter_is_readonly_data_filter() -> None:
    rows = [
        {"symbol": "EURUSD.r", "market_group": "Forex Majors", "side": "BUY", "strategy": "macd_breakout"},
        {"symbol": "US500", "market_group": "Index", "side": "SELL", "strategy": "fib_limit"},
    ]

    assert [row["symbol"] for row in filter_watchlist_rows(rows, search="eur")] == ["EURUSD.r"]
    assert [row["symbol"] for row in filter_watchlist_rows(rows, market_group="Index")] == ["US500"]
    assert [row["symbol"] for row in filter_watchlist_rows(rows, side="BUY")] == ["EURUSD.r"]


def test_universe_filter_distinguishes_snapshot_from_full_inventory() -> None:
    rows = [
        {"symbol": "EURUSD.r", "market_group": "Forex Majors", "in_current_snapshot": True},
        {"symbol": "US500", "market_group": "Index", "in_current_snapshot": False},
        {"symbol": "XAUUSD.r", "market_group": "Metals", "in_current_snapshot": False},
    ]

    assert [row["symbol"] for row in filter_universe_rows(rows, market_group="Index")] == ["US500"]
    assert [row["symbol"] for row in filter_universe_rows(rows, snapshot_state="in_snapshot")] == ["EURUSD.r"]
    assert [row["symbol"] for row in filter_universe_rows(rows, snapshot_state="outside_snapshot")] == ["US500", "XAUUSD.r"]


def test_screener_unified_filters_and_chart_are_readonly() -> None:
    rows = [
        {
            "setup_id": "a",
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "macd_breakout",
            "setup_status": "ready_for_chart_review",
            "timing_state": "entry_review",
            "direction": "long",
            "setup_quality_score": "4",
            "confluence_count": "3",
            "timing_priority": "5",
            "can_execute_order": "False",
        },
        {
            "setup_id": "b",
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "setup_type": "round_level_candidate",
            "setup_status": "needs_review",
            "timing_state": "watching",
            "direction": "short",
            "setup_quality_score": "2",
            "confluence_count": "1",
            "timing_priority": "7",
            "can_execute_order": "False",
        },
    ]
    filtered = filter_screener_setups(rows, search="macd", setup_type="macd_breakout", timeframe="H1", group="Forex Majors", min_quality=3, direction="long")

    assert [row["symbol"] for row in filtered] == ["EURUSD.r"]
    assert screener_score(filtered[0]) == 4
    assert filtered[0]["can_execute_order"] == "False"


def test_screener_filters_sort_by_timing_priority_before_quality() -> None:
    rows = [
        {
            "setup_id": "late-high-quality",
            "symbol": "ZZZ",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "fib_limit_live_candidate",
            "setup_status": "late_context",
            "timing_state": "late",
            "direction": "long",
            "setup_quality_score": "5",
            "confluence_count": "4",
            "timing_priority": "7",
            "can_execute_order": "False",
        },
        {
            "setup_id": "review-lower-quality",
            "symbol": "AAA",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "fib_limit_live_candidate",
            "setup_status": "ready_for_chart_review",
            "timing_state": "entry_review",
            "direction": "long",
            "setup_quality_score": "3",
            "confluence_count": "2",
            "timing_priority": "1",
            "can_execute_order": "False",
        },
    ]

    filtered = filter_screener_setups(
        rows,
        search=None,
        setup_type="__all__",
        timeframe="__all__",
        group="__all__",
        min_quality=1,
        direction="__all__",
        review_state="__all__",
    )

    assert [row["setup_id"] for row in filtered] == ["review-lower-quality", "late-high-quality"]


def test_screener_state_filter_keeps_group_filters_reviewable_by_default() -> None:
    rows = [
        {
            "setup_id": "reviewable",
            "symbol": "NZDCHF.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "macd_breakout",
            "setup_status": "ready_for_chart_review",
            "timing_state": "entry_review",
            "direction": "long",
            "setup_quality_score": "3",
            "confluence_count": "2",
            "timing_priority": "1",
        },
        {
            "setup_id": "watching",
            "symbol": "GBPCHF.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "previous_day_high_low_candidate",
            "setup_status": "needs_review",
            "timing_state": "watching",
            "direction": "neutral",
            "setup_quality_score": "2",
            "confluence_count": "1",
            "timing_priority": "4",
        },
        {
            "setup_id": "missing",
            "symbol": "EURCAD.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "macd_breakout",
            "setup_status": "context_incomplete",
            "timing_state": "missing_context",
            "direction": "short",
            "setup_quality_score": "2",
            "confluence_count": "1",
            "timing_priority": "8",
        },
    ]

    default_filtered = filter_screener_setups(
        rows,
        search=None,
        setup_type="__all__",
        timeframe="__all__",
        group="Forex Majors",
        min_quality=1,
        direction="__all__",
    )
    watching_filtered = filter_screener_setups(
        rows,
        search=None,
        setup_type="__all__",
        timeframe="__all__",
        group="Forex Majors",
        min_quality=1,
        direction="__all__",
        review_state="watching",
    )
    no_context_filtered = filter_screener_setups(
        rows,
        search=None,
        setup_type="__all__",
        timeframe="__all__",
        group="Forex Majors",
        min_quality=1,
        direction="__all__",
        review_state="no_context",
    )

    assert [row["setup_id"] for row in default_filtered] == ["reviewable"]
    assert [row["setup_id"] for row in watching_filtered] == ["watching"]
    assert [row["setup_id"] for row in no_context_filtered] == ["missing"]


def test_dynamic_fibonacci_modes_can_select_different_visual_swings() -> None:
    candles = []
    closes = [
        1.2200,
        1.2150,
        1.2100,
        1.2050,
        1.2000,
        1.1950,
        1.1900,
        1.1850,
        1.1800,
        1.1750,
        1.1700,
        1.1680,
        1.1700,
        1.1740,
        1.1780,
        1.1820,
        1.1860,
        1.1900,
        1.1940,
        1.1980,
        1.2020,
        1.2060,
        1.2100,
        1.2140,
        1.2120,
        1.2100,
        1.2080,
        1.2060,
        1.2040,
        1.2020,
        1.2000,
        1.1980,
        1.1960,
        1.1940,
        1.1920,
        1.1900,
        1.1910,
        1.1920,
        1.1930,
        1.1940,
        1.1950,
        1.1960,
        1.1970,
        1.1980,
    ]
    for index, close in enumerate(closes):
        candles.append(
            {
                "timestamp": f"2026-03-{1 + index // 24:02d} {index % 24:02d}:00:00",
                "open": close,
                "high": close + 0.0012,
                "low": close - 0.0012,
                "close": close,
            }
        )

    mode_layers = {
        mode: dynamic_fibonacci_layers("EURUSD.r", "Forex Majors", "H1", candles, mode)
        for mode in ["short", "medium", "wide", "macro"]
    }

    assert all(mode_layers.values())
    fib_100_prices = {
        mode: next(layer for layer in layers if layer["label"] == "Fib 100")["price"]
        for mode, layers in mode_layers.items()
    }
    assert len(set(fib_100_prices.values())) >= 2
    assert fib_100_prices["short"] != fib_100_prices["macro"]
    assert all(layer["is_operational"] is False for layers in mode_layers.values() for layer in layers)


def test_dynamic_fibonacci_macro_can_use_non_adjacent_pivots() -> None:
    candles = []
    closes = [
        1.2050,
        1.2180,
        1.2320,
        1.2420,
        1.2360,
        1.2280,
        1.2200,
        1.2120,
        1.2080,
        1.2000,
        1.1920,
        1.1840,
        1.1760,
        1.1680,
        1.1600,
        1.1560,
        1.1620,
        1.1680,
        1.1740,
        1.1800,
        1.1860,
        1.1920,
        1.1980,
        1.2040,
        1.2100,
        1.2160,
        1.2200,
        1.2180,
        1.2160,
        1.2140,
        1.2120,
        1.2100,
        1.2080,
        1.2060,
        1.2040,
        1.2020,
        1.2000,
        1.1980,
        1.1960,
        1.1980,
        1.2000,
        1.2020,
        1.2040,
        1.2060,
        1.1980,
        1.1860,
        1.1740,
        1.1620,
        1.1500,
        1.1380,
        1.1300,
        1.1360,
        1.1420,
        1.1480,
        1.1540,
        1.1600,
    ]
    for index, close in enumerate(closes):
        candles.append(
            {
                "timestamp": f"2026-03-{1 + index // 24:02d} {index % 24:02d}:00:00",
                "open": close,
                "high": close + 0.001,
                "low": close - 0.001,
                "close": close,
            }
        )

    wide_layers = dynamic_fibonacci_layers("EURUSD.r", "Forex Majors", "H1", candles, "wide")
    macro_layers = dynamic_fibonacci_layers("EURUSD.r", "Forex Majors", "H1", candles, "macro")

    assert wide_layers
    assert macro_layers
    wide_prices = {layer["label"]: float(layer["price"]) for layer in wide_layers if layer["label"] in {"Fib 0", "Fib 100"}}
    macro_prices = {layer["label"]: float(layer["price"]) for layer in macro_layers if layer["label"] in {"Fib 0", "Fib 100"}}
    wide_range = abs(wide_prices["Fib 0"] - wide_prices["Fib 100"])
    macro_range = abs(macro_prices["Fib 0"] - macro_prices["Fib 100"])
    assert macro_range > wide_range


def test_wavecount_filter_does_not_create_operational_flags() -> None:
    rows = [
        {
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "screener_bucket": "active_wave_study_candidate",
            "live_estimated_wave": "possible_wave3_active",
            "can_filter_trade": "False",
            "can_execute_order": "False",
        },
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H4",
            "screener_bucket": "needs_chart_review",
            "live_estimated_wave": "possible_wave5_active",
            "can_filter_trade": "False",
            "can_execute_order": "False",
        },
    ]

    filtered = filter_wavecount_rows(rows, bucket="active_wave_study_candidate")
    wave3 = filter_wavecount_number_rows(rows, "wave3")
    summary = wavecount_number_summary(rows)

    assert len(filtered) == 1
    assert filtered[0]["symbol"] == "US500"
    assert filtered[0]["can_filter_trade"] == "False"
    assert filtered[0]["can_execute_order"] == "False"
    assert wavecount_number(rows[0]) == "3"
    assert [row["symbol"] for row in wave3] == ["US500"]
    assert {item["number"]: item["count"] for item in summary}["5"] == 1


def test_wavecount_can_filter_h1_auxiliary_cases() -> None:
    aux_rows = build_h1_aux_wavecount_rows(
        [
            {
                "candidate_id": "aux_audjpy_h1",
                "group": "Forex Majors",
                "symbol": "AUDJPY.r",
                "timeframe": "H1",
                "direction": "bullish",
                "end_time": "2026-01-30 17:00:00",
                "pattern_type": "full_impulse_12345",
            }
        ]
    )
    rows = [
        {
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "screener_bucket": "active_wave_study_candidate",
            "live_estimated_wave": "possible_wave3_active",
        },
        *aux_rows,
    ]

    h1_wave5 = filter_wavecount_number_rows(rows, "wave5", timeframe="H1")

    assert len(h1_wave5) == 1
    assert h1_wave5[0]["symbol"] == "AUDJPY.r"
    assert h1_wave5[0]["can_execute_order"] == "False"
    assert h1_wave5[0]["can_filter_trade"] == "False"
    assert wavecount_wave_label(h1_wave5[0]) == "W5?"
    assert wavecount_direction_label(h1_wave5[0]) == "alcista"


def test_weavecount_screener_rows_are_primary_dashboard_source() -> None:
    data = build_dash_data()
    rows = data["wavecount_rows"]

    assert len(rows) == 94
    assert {row["case_type"] for row in rows} == {"weavecount_screener_h1_h4_v1"}
    assert {row["timeframe"] for row in rows} == {"H1", "H4"}
    assert sorted({row["market_group"] for row in rows}) == ["Forex Majors", "Index", "Metals"]
    assert len({row["symbol"] for row in rows}) == 47
    assert all(row["can_execute_order"] == "False" for row in rows)
    assert all(row["can_filter_trade"] == "False" for row in rows)
    assert {wavecount_quality_status(row) for row in rows} <= {"fuerte", "media", "debil"}
    assert all(row.get("quality_status") for row in rows)
    assert any(row["count_label"] == "W3?" for row in rows)


def test_weavecount_screener_dashboard_adapter_keeps_candidate_label() -> None:
    rows = build_weavecount_screener_dashboard_rows(
        [
            {
                "case_id": "case-a",
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "count_label": "W3?",
                "wave_number": "3",
                "confidence_status": "candidate",
                "direction": "long",
            },
            {
                "case_id": "case-b",
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "M15",
                "count_label": "W2?",
                "wave_number": "2",
            },
            {
                "case_id": "case-c",
                "symbol": "GBPUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H4",
                "count_label": "no_clear_count",
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0]["case_type"] == "weavecount_screener_h1_h4_v1"
    assert rows[0]["current_leg_direction"] == "up"
    assert rows[0]["can_execute_order"] == "False"
    assert wavecount_number(rows[0]) == "3"
    assert wavecount_status(rows[0]) == "candidate"
    assert wavecount_quality_status(rows[0]) == "debil"
    assert wavecount_wave_label(rows[0]) == "W3?"


def test_wavecount_filters_include_quality_and_direction() -> None:
    rows = [
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "count_label": "W2?",
            "wave_number": "2",
            "confidence_status": "candidate",
            "quality_status": "media",
            "direction": "long",
        },
        {
            "symbol": "EURCHF.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "count_label": "W2?",
            "wave_number": "2",
            "confidence_status": "candidate",
            "quality_status": "debil",
            "direction": "short",
        },
    ]

    assert [row["symbol"] for row in filter_wavecount_number_rows(rows, "wave2", quality="media")] == ["EURUSD.r"]
    assert [row["symbol"] for row in filter_wavecount_number_rows(rows, "wave2", direction="down")] == ["EURCHF.r"]


def test_wavecount_visible_cases_are_deduplicated() -> None:
    rows = [
        {
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "screener_bucket": "active_wave_study_candidate",
            "live_estimated_wave": "possible_wave3_active",
        },
        {
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "screener_bucket": "active_wave_study_candidate",
            "live_estimated_wave": "possible_wave3_active",
        },
        {
            "symbol": "XAUUSD.r",
            "market_group": "Metals",
            "timeframe": "H4",
            "screener_bucket": "active_wave_study_candidate",
            "live_estimated_wave": "possible_wave3_active",
            "current_leg_direction": "up",
        },
    ]

    wave3 = filter_wavecount_number_rows(rows, "wave3")
    summary = {item["number"]: item["count"] for item in wavecount_number_summary(rows)}

    assert [row["symbol"] for row in wave3] == ["US500", "XAUUSD.r"]
    assert summary["3"] == 2


def test_wavecount_uses_current_case_before_historical_audit_cases() -> None:
    rows = [
        {
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "screener_bucket": "active_wave_study_candidate",
            "live_estimated_wave": "possible_wave3_active",
            "case_type": "current_screener_row",
        },
        {
            "symbol": "US500",
            "market_group": "Index",
            "timeframe": "H4",
            "screener_bucket": "needs_chart_review",
            "live_estimated_wave": "possible_wave5_active",
            "case_type": "persistent_latest_case",
        },
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H4",
            "screener_bucket": "invalidated_old_context",
            "live_estimated_wave": "invalidated",
            "case_type": "current_screener_row",
        },
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H4",
            "screener_bucket": "needs_chart_review",
            "live_estimated_wave": "possible_wave3_active",
            "case_type": "cycle_reset_case",
        },
    ]

    summary = {item["number"]: item["count"] for item in wavecount_number_summary(rows)}

    assert [row["symbol"] for row in filter_wavecount_number_rows(rows, "wave3")] == ["US500"]
    assert filter_wavecount_number_rows(rows, "wave5") == []
    assert summary["3"] == 1
    assert summary["5"] == 0


def test_wavecount_chart_fallback_uses_existing_case_chart() -> None:
    src = wavecount_chart_data_uri({"symbol": "US500", "timeframe": "H4", "chart_file": ""})

    assert src.startswith("data:image/png;base64,")


def test_wavecount_chart_figure_uses_readonly_ohlc_and_trace() -> None:
    figure = wavecount_chart_figure({"symbol": "US500", "timeframe": "H4", "live_estimated_wave": "possible_wave3_active"})

    assert figure["data"][0]["type"] == "candlestick"
    assert figure["layout"]["xaxis"]["type"] == "category"
    assert figure["layout"]["xaxis"]["categoryarray"] == figure["data"][0]["x"]
    assert len(figure["layout"]["xaxis"]["tickvals"]) <= 7
    assert "<br>" in figure["layout"]["xaxis"]["ticktext"][0]
    trace = next(item for item in figure["data"] if item.get("name") == "W3 actual")
    assert trace["line"]["color"] == "#ff6b65"
    assert {item.get("name") for item in figure["data"]} >= {"W1 previa", "W2 previa", "W3 actual"}
    assert len(figure["data"][0]["x"]) > 170
    assert "W3 bajista" in figure["layout"]["title"]["text"]
    assert wavecount_direction_label({"symbol": "US500", "timeframe": "H4"}) == "bajista"
    points = wavecount_structure_points({"symbol": "US500", "timeframe": "H4", "live_estimated_wave": "possible_wave3_active"})
    assert [point["label"] for point in points] == ["origen", "W1", "W2", "W3"]


def test_screener_setup_figure_uses_readonly_ohlc_and_context_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    import trading_center.dash_readonly_app as dash_app

    candles = []
    for index in range(80):
        close = 1.10 + index * 0.0008 + (0.0015 if index % 9 == 0 else 0)
        candles.append(
            {
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "timestamp": f"2026-03-{1 + index // 24:02d} {index % 24:02d}:00:00",
                "open": f"{close - 0.0004:.5f}",
                "high": f"{close + 0.0010:.5f}",
                "low": f"{close - 0.0010:.5f}",
                "close": f"{close:.5f}",
            }
        )
    monkeypatch.setattr(dash_app, "screener_ohlc_index", lambda: {("EURUSD.r", "H1"): candles})
    row = {
        "setup_id": "setup-1",
        "symbol": "EURUSD.r",
        "timeframe": "H1",
        "setup_type": "macd_breakout",
        "setup_quality_score": "5",
    }
    layers = [
        {"setup_id": "setup-1", "label": "R2 previo", "price": "1.145", "color": "#80d8ff", "style": "dash"},
        {"setup_id": "setup-1", "label": "Nivel redondo superior", "price": "1.150", "color": "#a56cff", "style": "solid"},
        {"setup_id": "setup-1", "label": "Fib 61.8", "price": "1.140", "color": "#c793ff", "style": "dash"},
    ]
    figure = screener_setup_figure(row, layers)

    assert figure["data"][0]["type"] == "candlestick"
    assert figure["layout"]["xaxis"]["type"] == "category"
    assert figure["layout"]["template"] == "plotly_dark"
    assert figure["layout"]["plot_bgcolor"] == "#050909"
    assert figure["layout"]["height"] >= 1240
    assert figure["layout"]["xaxis"]["showgrid"] is False
    assert figure["layout"]["xaxis"]["anchor"] == "y3"
    assert figure["layout"]["yaxis"]["showgrid"] is False
    assert figure["layout"]["xaxis"]["tickangle"] == 0
    assert figure["layout"]["xaxis"]["tickmode"] == "array"
    assert figure["layout"]["xaxis"]["categoryarray"][-1].startswith("__future_pad_")
    assert figure["layout"]["yaxis"]["domain"][0] > figure["layout"]["yaxis2"]["domain"][1]
    assert figure["layout"]["yaxis2"]["domain"][0] > figure["layout"]["yaxis3"]["domain"][1]
    assert figure["layout"]["yaxis"]["domain"][1] - figure["layout"]["yaxis"]["domain"][0] >= 0.45
    assert figure["layout"]["yaxis2"]["domain"][1] - figure["layout"]["yaxis2"]["domain"][0] >= 0.14
    assert figure["layout"]["yaxis3"]["domain"][1] - figure["layout"]["yaxis3"]["domain"][0] >= 0.14
    assert figure["layout"]["yaxis2"]["range"] == [0, 100]
    assert figure["layout"]["hoverlabel"]["bgcolor"] == "#0d1b1a"
    assert row["setup_type"] in figure["layout"]["meta"]["title"]
    assert "annotations" in figure["layout"]
    default_layers = [layer for layer in layers if screener_layer_family(layer) in {"previous_day", "pivots"}]
    assert len(figure["layout"]["annotations"]) == len(default_layers) + 3
    if default_layers:
        assert figure["layout"]["annotations"][0]["text"] == default_layers[0]["label"]
        assert figure["layout"]["annotations"][0]["showarrow"] is False
        assert figure["layout"]["annotations"][0]["x"] == figure["layout"]["xaxis"]["categoryarray"][-1]
    assert not any(str(item["text"]).startswith("Nivel redondo") for item in figure["layout"]["annotations"])
    round_traces = [item for item in figure["data"] if str(item.get("name", "")).startswith("Nivel redondo")]
    assert not round_traces
    figure_with_rounds = screener_setup_figure(row, layers, visible_layers=["previous_day", "pivots", "round_levels", "fibonacci"])
    round_traces = [item for item in figure_with_rounds["data"] if str(item.get("name", "")).startswith("Nivel redondo")]
    assert round_traces
    assert all(item["line"]["color"] == "#a56cff" for item in round_traces)
    assert all(item["line"]["width"] == 1.0 for item in round_traces)
    assert all(item["line"]["dash"] == "solid" for item in round_traces)
    fib_traces = [item for item in figure_with_rounds["data"] if str(item.get("name", "")).startswith("Fib ")]
    assert fib_traces
    assert any(item["line"]["color"] == "#c793ff" for item in fib_traces)
    assert any(str(annotation["text"]).startswith("Fib ") for annotation in figure_with_rounds["layout"]["annotations"])
    figure_no_layers = screener_setup_figure(row, layers, visible_layers=[])
    assert not any(item.get("name") in {"R2 previo", "Nivel redondo superior", "Fib 61.8"} for item in figure_no_layers["data"])
    assert len(figure_no_layers["layout"]["annotations"]) == 3
    options = screener_layer_options_for(layers)
    assert {option["value"] for option in options} >= {"pivots", "round_levels", "fibonacci"}
    macd_options = screener_layer_options_for(
        [
            {
                "layer_type": "macd_breakout_level",
                "label": "Ruptura estudio",
                "source": "macd_breakout_enrichment_v1",
            }
        ]
    )
    assert {option["value"] for option in macd_options} == {"macd_breakout"}
    fib_limit_only_options = screener_layer_options_for(
        [
            {
                "layer_type": "fib_limit_live_fibonacci_0_618",
                "label": "Fib 61.8 estudio",
                "source": "fib_limit_live_detector_v1",
            }
        ]
    )
    fib_limit_values = {option["value"] for option in fib_limit_only_options}
    assert "fib_limit" in fib_limit_values
    assert "fibonacci" not in fib_limit_values
    assert screener_layer_price_by_type(
        [
            {
                "layer_type": "fib_limit_study_zone_618",
                "price": "1.2345",
            }
        ],
        "fib_limit_study_zone_618",
    ) == "1.2345"
    figure_with_swing = screener_setup_figure(
        row,
        [
            {
                "layer_type": "fib_limit_study_swing_0_100",
                "label": "Swing 0-100 estudio",
                "start_price": "1.10",
                "end_price": "1.20",
                "price": "1.20",
                "start_time": "2026-03-16 08:00:00",
                "end_time": "2026-03-17 09:00:00",
                "color": "#f4b740",
                "style": "solid",
                "source": "fib_limit_live_study_levels_v1",
            }
        ],
        visible_layers=["fib_limit"],
    )
    swing_trace = next(item for item in figure_with_swing["data"] if item.get("name") == "Swing 0-100 estudio")
    assert swing_trace["mode"] == "lines+markers+text"
    assert swing_trace["y"] == [1.10, 1.20]
    assert swing_trace["text"] == ["Fib 0", "Fib 100"]
    rsi_trace = next(item for item in figure["data"] if item.get("name") == "RSI 14")
    assert rsi_trace["yaxis"] == "y2"
    assert len(rsi_trace["x"]) == len(figure["data"][0]["x"])
    assert any(str(item["text"]).startswith("RSI ") and item["yref"] == "y2" for item in figure["layout"]["annotations"])
    macd_trace = next(item for item in figure["data"] if item.get("name") == "MACD 12-26")
    signal_trace = next(item for item in figure["data"] if item.get("name") == "Senal 9")
    assert macd_trace["yaxis"] == "y3"
    assert signal_trace["yaxis"] == "y3"
    assert len(macd_trace["x"]) == len(figure["data"][0]["x"])
    assert len(signal_trace["x"]) == len(figure["data"][0]["x"])
    assert any(item["text"] == "MACD" and item["yref"] == "y3" for item in figure["layout"]["annotations"])
    assert any(item["text"] == "Senal" and item["yref"] == "y3" for item in figure["layout"]["annotations"])
    assert any(shape.get("yref") == "paper" for shape in figure["layout"]["shapes"])
    assert any(shape.get("yref") == "y2" and shape.get("y0") == 70 for shape in figure["layout"]["shapes"])
    assert any(shape.get("yref") == "y2" and shape.get("y0") == 30 for shape in figure["layout"]["shapes"])
    assert any(shape.get("yref") == "y3" and shape.get("y0") == 0 for shape in figure["layout"]["shapes"])
    assert all(item.get("type") != "bar" for item in figure["data"])


def test_rsi_modal_offers_context_layers_but_opens_with_rsi_only() -> None:
    layers = [
        {"layer_type": "previous_high", "label": "Maximo dia previo", "source": "ohlc_previous_day_context"},
        {"layer_type": "r2", "label": "R2 previo", "source": "ohlc_previous_day_context"},
        {"layer_type": "round_level_1", "label": "Nivel redondo superior", "source": "ohlc_nearby_round_levels"},
        {"layer_type": "fibonacci_0_618", "label": "Fib 61.8", "source": "fibonacci_context_v1"},
        {"layer_type": "rsi_entry_marker", "label": "RSI cruce vuelta", "source": "rsi_trend_reversal_v1"},
    ]
    options = screener_layer_options_for(layers)

    assert {option["value"] for option in options} >= {
        "previous_day",
        "pivots",
        "round_levels",
        "fibonacci",
        "rsi_setup",
    }
    assert screener_default_visible_layers({"setup_type": "rsi_trend_reversal"}, options) == ["rsi_setup"]


def test_wavecount_candidate_is_labeled_as_candidate_not_active_wave() -> None:
    row = {
        "symbol": "XAUUSD.r",
        "timeframe": "H4",
        "live_estimated_wave": "possible_wave3_candidate",
        "confirmed_wave_context": "possible_wave3_candidate_late",
        "current_leg_direction": "up",
    }
    figure = wavecount_chart_figure(row)
    trace = next(item for item in figure["data"] if item.get("name") == "W3? actual")

    assert wavecount_status(row) == "candidate"
    assert wavecount_wave_label(row) == "W3?"
    assert "Candidato W3 alcista" in figure["layout"]["title"]["text"]
    assert trace["line"]["color"] == "#d7a84b"


def test_h1_auxiliary_wavecount_chart_uses_ohlc_window() -> None:
    data = build_dash_data()
    h1_rows = filter_wavecount_number_rows(data["wavecount_rows"], "wave5", timeframe="H1")

    assert h1_rows
    structure_points = wavecount_structure_points(h1_rows[0])
    figure = wavecount_chart_figure(h1_rows[0])

    assert [point["label"] for point in structure_points] == ["origen", "W1", "W2", "W3", "W4", "W5?"]
    assert figure["data"][0]["type"] == "candlestick"
    assert figure["layout"]["xaxis"]["type"] == "category"
    assert "H1" in figure["layout"]["title"]["text"]
    assert {item.get("name") for item in figure["data"]} >= {"W1 previa", "W2 previa", "W3 previa", "W4 previa", "W5? actual"}


def test_dash_dropdown_menu_uses_dark_theme() -> None:
    css = dash_css()

    assert ".Select-menu, .Select-option, .VirtualizedSelectOption" in css
    assert ".Select-option.is-focused" in css
    assert ".dash-dropdown-content" in css
    assert ".dash-dropdown-option" in css
    assert "background: #0b1213 !important" in css
    assert ".Select-input > input" in css
    assert ".screener-layer-control" in css
    assert ".screener-layer-option" in css
    assert ".screener-layer-toggle .dash-options-list-option.selected" in css
    assert ".screener-layer-toggle .dash-options-list-option-wrapper" in css
    assert ".screener-fib-mode-toggle .dash-options-list-option.selected" in css
    assert "opacity: 0" in css
    assert ".screener-setup-graph" in css
