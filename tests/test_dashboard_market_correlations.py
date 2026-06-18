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

def test_market_radar_summary_extracts_alignment_and_counter_extremes() -> None:
    rows = [
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "m15_trend": "bullish",
            "h1_trend": "bullish",
            "h4_trend": "bullish",
            "d1_trend": "bullish",
            "rsi_h1": "24",
            "h1_rsi_signal": "bullish_oversold",
            "atr_pct_h1": "0.42",
            "atr_pct_h1_median": "0.60",
            "atr_pct_h1_ratio": "0.70",
            "atr_pct_h1_sample_count": "2000",
        },
        {
            "symbol": "US500",
            "market_group": "Index",
            "m15_trend": "bearish",
            "h1_trend": "bearish",
            "h4_trend": "bearish",
            "d1_trend": "bearish",
            "oscillator_state": "overbought",
            "h1_rsi_signal": "bearish_overbought",
            "atr_pct_h1": "1.90",
            "atr_pct_h1_median": "0.80",
            "atr_pct_h1_ratio": "2.38",
            "atr_pct_h1_sample_count": "2000",
        },
        {
            "symbol": "XAUUSD.r",
            "market_group": "Metals",
            "h1_trend": "bullish",
            "h4_trend": "bearish",
            "d1_trend": "bullish",
            "rsi_h1": "50",
            "atr_pct_h1": "0.18",
            "atr_pct_h1_median": "0.50",
            "atr_pct_h1_ratio": "0.36",
            "atr_pct_h1_sample_count": "2000",
        },
    ]

    radar = market_radar_summary(rows)

    assert [row["symbol"] for row in radar["trend_aligned"]] == ["EURUSD.r", "US500"]
    assert [row["symbol"] for row in radar["counter_extremes"]] == ["EURUSD.r", "US500"]
    assert [row["timeframe"] for row in radar["strength"]] == ["M15", "H1", "H4", "D1"]
    assert radar["market_mode"]["label"] in {"Fondo alcista", "Fondo bajista", "H4 alcista", "H4 bajista", "Mercado mixto"}
    assert radar["volatility"]["hot_assets"][0]["symbol"] == "US500"
    assert {row["h1"] for row in radar["counter_extremes"]} == {"↑", "↓"}
    assert [row["family"] for row in radar["family_strength"]] == ["Forex Majors", "Index", "Metals"]
    assert radar["alignment_quality"]["full_alignment"] == 2
    assert radar["alignment_quality"]["no_clear_alignment"] == 1
    assert radar["alignment_quality"]["full_pct"] == 67
    assert radar["volatility_pressure"]["hot"] == 1
    assert radar["volatility_pressure"]["compressed"] == 2
    assert radar["volatility_pressure"]["hot_pct"] == 33


def test_correlation_helpers_filter_timeframe_asset_and_partial_view() -> None:
    pair_rows = [
        {"timeframe": "H1", "asset_1": "EURUSD.r", "asset_2": "GBPUSD.r", "spearman": "0.82", "obs": "120"},
        {"timeframe": "H1", "asset_1": "EURUSD.r", "asset_2": "USDCHF.r", "spearman": "-0.61", "obs": "120"},
        {"timeframe": "H1", "asset_1": "GBPUSD.r", "asset_2": "USDCHF.r", "spearman": "-0.44", "obs": "120"},
        {"timeframe": "H4", "asset_1": "EURUSD.r", "asset_2": "GBPUSD.r", "spearman": "0.20", "obs": "80"},
    ]
    rolling_rows = [
        {
            "timeframe": "H1",
            "asset_1": "EURUSD.r",
            "asset_2": "GBPUSD.r",
            "metric": "spearman",
            "latest_corr": "0.70",
            "previous_corr": "0.30",
            "delta_prev": "0.40",
            "window": "120",
        }
    ]
    return_rows = [
        {"timeframe": "H1", "symbol": "EURUSD.r", "timestamp": "2026-01-01 00:00:00", "log_return": "0.001"},
        {"timeframe": "H1", "symbol": "GBPUSD.r", "timestamp": "2026-01-01 00:00:00", "log_return": "0.002"},
        {"timeframe": "H1", "symbol": "EURUSD.r", "timestamp": "2026-01-01 01:00:00", "log_return": "-0.001"},
        {"timeframe": "H1", "symbol": "GBPUSD.r", "timestamp": "2026-01-01 01:00:00", "log_return": "-0.002"},
    ]

    base = correlation_rows_for_asset(pair_rows, "H1", "EURUSD.r", "spearman")
    rolling = rolling_rows_for_asset(rolling_rows, "H1", "EURUSD.r", "spearman")
    partial = partial_correlation_rows(pair_rows, "H1", "EURUSD.r", "spearman")
    matrix_assets = matrix_assets_for_focus(pair_rows, "H1", "EURUSD.r", "GBPUSD.r", "spearman", limit=3)
    fixed_matrix_assets = normalize_matrix_assets(["EURUSD.r", "GBPUSD.r", "USDCHF.r"], {"assets": ["EURUSD.r", "GBPUSD.r", "USDCHF.r"]})
    default_assets = default_matrix_assets({"assets": ["US500", "GBPUSD.r", "EURUSD.r", "USDCHF.r"]}, limit=3)
    return_points = pair_return_points(return_rows, "H1", "EURUSD.r", "GBPUSD.r")
    lowess = lowess_line(return_points + [{"x": 0.003, "y": 0.004, "timestamp": "x"}] * 4)
    rolling_points = [
        {"timestamp": f"2026-01-01 {index:02d}:00:00", "x": index / 1000, "y": index / 900}
        for index in range(24)
    ]
    rolling_series = rolling_correlation_series(rolling_points, "pearson", window=12)

    assert [row["asset"] for row in base] == ["GBPUSD.r", "USDCHF.r"]
    assert base[0]["tone"] == "up"
    assert base[1]["tone"] == "down"
    assert rolling[0]["asset"] == "GBPUSD.r"
    assert rolling[0]["delta"] == 0.4
    assert partial[0]["asset"] == "GBPUSD.r / USDCHF.r"
    assert matrix_assets[:2] == ["EURUSD.r", "GBPUSD.r"]
    assert fixed_matrix_assets == ["EURUSD.r", "GBPUSD.r", "USDCHF.r"]
    assert default_assets[:2] == ["EURUSD.r", "GBPUSD.r"]
    assert len(return_points) == 2
    assert return_points[0]["x"] == 0.001
    assert lowess is not None
    assert rolling_window_for_timeframe("H1") == 120
    assert rolling_series
    assert rolling_series[-1]["value"] > 0.99
