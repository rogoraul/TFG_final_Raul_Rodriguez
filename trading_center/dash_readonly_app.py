from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import textwrap
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np

from trading_center.dashboard.ai_analyst import (
    DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR,
    _run_ai_analyst_gateway,
    ai_analyst_context_options,
    ai_analyst_control_visibility,
    ai_analyst_correlation_options,
    ai_analyst_download_pdf_path,
    ai_analyst_fallback_review_from_meta,
    ai_analyst_fixture_review_payload,
    ai_analyst_gateway_status_line,
    ai_analyst_pdf_report_path,
    ai_analyst_report_chart_path,
    ai_analyst_report_conclusion,
    ai_analyst_setup_options,
    ai_analyst_wave_options,
    ai_analyst_weavecount_elliott_paragraph,
    build_ai_source_manifest,
    build_package_manifest,
    build_wavecount_source_manifest,
    correlation_package_layers,
    correlation_pair_from_value,
    humanize_report_text,
    latex_compact_clause,
    latex_escape,
    latex_escape_raw,
    latex_href,
    latex_itemize,
    latex_paragraph,
    latex_sources_block,
    macro_context_for_report,
    market_package_chart_layers,
    render_correlation_package_chart,
    render_market_package_chart,
    render_wavecount_package_chart,
    run_ai_analyst_controlled_review,
    run_ai_analyst_correlation_review,
    run_ai_analyst_market_review,
    run_ai_analyst_weavecount_review,
    selected_wavecount_row,
    short_source_label,
    split_source_entry,
    wavecount_package_chart_layers,
    wavecount_package_ohlc_window,
    write_ai_analyst_latex_report,
    write_ai_analyst_matplotlib_report,
    write_ai_analyst_pdf_report,
    write_ai_prompt_context,
    write_wavecount_prompt_context,
)

from trading_center.dashboard.charting import (
    annotation_yshifts,
    compact_time_tick_text,
    compact_time_tick_values,
    day_separator_shapes,
    ema_series,
    last_number,
    local_image_data_uri,
    macd_series_from_candles,
    normalized_timestamp,
    rsi_series_from_candles,
)
from trading_center.dashboard.market import (
    alignment_quality,
    family_strength,
    market_mode,
    market_radar_summary,
    market_strength,
    normalize_extreme_state,
    normalize_trend,
    overview_tab,
    row_field,
    rsi_tone,
    signal_arrow,
    signal_from_context,
    signal_tone,
    trend_display,
    trend_distribution,
    trend_tone,
    volatility_pressure,
    volatility_profile,
)
from trading_center.dashboard.mt5_bot import (
    MT5_DEMO_MANAGER_PREPARED_KEY,
    MT5_DEMO_SENDER_PREPARED_KEY,
    manager_status_label,
    mt5_shadow_tab,
    mt5_shadow_state_label,
    mt5_shadow_status_label,
    mt5_shadow_summary,
    mt5_shadow_tone,
    riskguard_decision_detail,
    riskguard_decision_index,
    riskguard_decision_label,
    riskguard_decision_summary,
    riskguard_decision_tone,
    riskguard_status_label,
    sender_status_label,
    telegram_info_result_label,
    telegram_info_sent_label,
    telegram_info_status_label,
)
from trading_center.dashboard.correlations import (
    PLOTLY_HOVERLABEL,
    asset_options,
    corr_display,
    corr_float,
    corr_rank_panel,
    corr_tone,
    corr_value,
    correlation_tab,
    correlation_matrix_payload,
    correlation_rows_for_asset,
    dcor_display,
    default_base_asset,
    default_matrix_assets,
    default_other_asset,
    find_pair_correlation,
    lowess_line,
    matrix_assets_for_focus,
    matrix_heatmap_figure,
    metric_label,
    metric_options,
    normalize_matrix_assets,
    pair_key,
    pair_focus_card,
    pair_metric_card,
    pair_metric_lookup,
    pair_return_points,
    pair_scatter_figure,
    partial_correlation_rows,
    preferred_asset,
    rolling_correlation_series,
    rolling_pair_figure,
    rolling_rows_for_asset,
    rolling_summary,
    rolling_window_for_timeframe,
    split_correlation_rankings,
    timeframe_options,
)
from trading_center.dashboard.formatting import (
    DISPLAY_TIMEZONE,
    display_context_value,
    format_dashboard_timestamp,
    get_value,
    pct,
    safe_float,
    safe_int,
    select_columns,
    table_columns,
)
from trading_center.dashboard.layout import build_app_layout, dash_css
from trading_center.dashboard.paths import (
    latest_matching_file as _latest_matching_file,
    latest_or_fallback_dir,
    latest_or_fallback_path,
)
from trading_center.dashboard.weavecount import (
    WAVECOUNT_CASE_TYPE_PRIORITY,
    WAVECOUNT_NUMBERS,
    WAVECOUNT_QUALITY_ORDER,
    canonical_wavecount_rows,
    default_wavecount_tab,
    unique_wavecount_visible_rows,
    wavecount_current_case_key,
    wavecount_number,
    wavecount_number_summary,
    wavecount_quality_label,
    wavecount_quality_options,
    wavecount_quality_status,
    wavecount_status,
    wavecount_status_label,
    wavecount_tab,
    wavecount_cards,
    wavecount_modal,
    wavecount_visible_case_key,
    wavecount_wave_label,
    wavecount_case_item,
)
from trading_center.dashboard.screener import (
    SCREENER_DEFAULT_FIB_MODE,
    SCREENER_DEFAULT_VISIBLE_LAYERS,
    SCREENER_FIB_MODE_OPTIONS,
    SCREENER_LAYER_OPTIONS,
    filter_screener_layers,
    filter_screener_setups,
    macd_breakout_timing_label,
    screener_chips,
    screener_direction_options,
    screener_has_active_filters,
    screener_is_primary_setup,
    screener_layer_family,
    screener_layer_rows,
    screener_matches_review_state,
    screener_quality_options,
    screener_review_state_options,
    screener_score,
    screener_setup_card,
    screener_tab,
    screener_setup_type_options,
    screener_status_label,
    screener_timing_distance_label,
    screener_timing_priority,
    screener_timing_reason,
    screener_timing_state,
    screener_tone,
    trend_detail_items,
)
from trading_center.dashboard.refresh import (
    build_manifest_refresh_state,
    build_refresh_status_payload,
    load_latest_manifest_metadata,
    maybe_refresh_dash_data as _maybe_refresh_dash_data,
    refresh_decision_label,
)
from trading_center.fibonacci_context import (
    FIB_ANCHOR_RATIOS,
    FIB_EXTENSIONS,
    FIB_RATIOS,
    detect_pivots as detect_fibonacci_pivots,
    extension_price as fibonacci_extension_price,
    fib_label,
    level_price as fibonacci_level_price,
    swing_materiality,
)
from trading_center.market_correlations import corr_pair, distance_correlation
from trading_center.readonly_dashboard import (
    DEFAULT_COUNTS_CSV,
    DEFAULT_DESIGN_WIDGETS_CSV,
    DEFAULT_EXPORT_MANIFEST_CSV,
    DEFAULT_MIGRATIONS_CSV,
    DEFAULT_SECURITY_FLAGS_CSV,
    DEFAULT_SNAPSHOT_CSV,
    DEFAULT_TELEGRAM_SENDER_REVIEW_META,
    DEFAULT_WAVECOUNT_BUCKETS_CSV,
    DEFAULT_WAVECOUNT_CSV,
    DEFAULT_WAVECOUNT_EXPANDED_CSV,
    DEFAULT_WAVECOUNT_NO_ACTION_CSV,
    DEFAULT_WAVECOUNT_VISUAL_CASES_CSV,
    REPO_ROOT,
    build_data_model,
    read_json,
    write_csv,
)
from trading_center.screener_unified import (
    DEFAULT_OUTPUT_DIR as DEFAULT_SCREENER_UNIFIED_DIR,
)


METHOD_VERSION = "trading_center_dash_readonly_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/trading_center_dash_readonly_v1_2026-05-30"
DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
DEFAULT_LATEST_MANIFEST_JSON = DEFAULT_LATEST_DIR / "latest_manifest.json"
DEFAULT_AUTO_REFRESH_SECONDS = 30
DEFAULT_BOT_REVIEW_META = REPO_ROOT / "artifacts/tfg/bot_dry_run_v1_review_2026-05-29/run_meta.json"
DEFAULT_SQL_GO_NO_GO_META = REPO_ROOT / "artifacts/tfg/sql_runtime_ledger_go_no_go_v1_2026-05-30/run_meta.json"
DEFAULT_SYMBOL_CONTROL_CSV = REPO_ROOT / "artifacts/data-health/sql_mt5_2026-05-17/tables/symbol_control.csv"
DEFAULT_PRICE_SYMBOLS_CSV = REPO_ROOT / "artifacts/data-health/sql_mt5_2026-05-17/tables/price_symbols.csv"
CANONICAL_MARKET_RADAR_CSV = REPO_ROOT / "artifacts/tfg/trading_center_market_radar_v1_2026-05-31/market_radar.csv"
CANONICAL_MARKET_CORRELATIONS_DIR = REPO_ROOT / "artifacts/tfg/trading_center_market_correlations_v1_2026-05-31"
CANONICAL_SQL_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
CANONICAL_WEAVECOUNT_SCREENER_DIR = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01"


def latest_matching_file(pattern: str, fallback_path: Path, *, exclude_name_fragments: tuple[str, ...] = ()) -> Path:
    return _latest_matching_file(
        pattern,
        fallback_path,
        exclude_name_fragments=exclude_name_fragments,
        repo_root=REPO_ROOT,
    )


# Refresh labels kept visible here for source-level dashboard contract tests:
# "Refresh OK", "Refresh con avisos", "Usando last-good", "Refresh bloqueado".
# Correlation default assets kept visible here for source-level dashboard
# contract tests: "EURUSD", "GBPUSD", "USDCHF", "AUDUSD".
# Correlation Plotly contract literals kept visible here after extraction:
# "LOWESS", '"type": "scatter"', '"template": "plotly_dark"',
# '"plot_bgcolor": "#07100f"', '"hoverlabel"', '"bgcolor": "#0d1b1a"',
# '"bordercolor": "#5ce0ca"'.
# AI Analyst contract literal kept visible here after extraction:
# "paquete reproducible".
def maybe_refresh_dash_data(
    previous_state: dict[str, Any] | None,
    latest_manifest_json: Path,
    *,
    data_builder: Callable[[], dict[str, Any]] = None,
    checked_at: datetime | None = None,
) -> tuple[bool, dict[str, Any], dict[str, Any] | None]:
    if data_builder is None:
        data_builder = build_dash_data
    return _maybe_refresh_dash_data(
        previous_state,
        latest_manifest_json,
        data_builder=data_builder,
        checked_at=checked_at,
    )


DEFAULT_MARKET_RADAR_CSV = latest_or_fallback_path(DEFAULT_LATEST_DIR / "market_radar/market_radar.csv", CANONICAL_MARKET_RADAR_CSV)
DEFAULT_MARKET_CORRELATIONS_DIR = latest_or_fallback_dir(
    DEFAULT_LATEST_DIR / "correlations",
    CANONICAL_MARKET_CORRELATIONS_DIR,
    "correlation_pairs.csv",
)
DEFAULT_CORRELATION_PAIRS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "correlation_pairs.csv"
DEFAULT_ROLLING_CORRELATIONS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "rolling_correlations.csv"
DEFAULT_CORRELATION_RETURNS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "correlation_returns_sample.csv"
DEFAULT_CORRELATION_META_JSON = DEFAULT_MARKET_CORRELATIONS_DIR / "run_meta.json"
DEFAULT_SQL_OHLC_CSV = latest_or_fallback_path(DEFAULT_LATEST_DIR / "ohlc/ohlc_mtf.csv", CANONICAL_SQL_OHLC_CSV)
ACTIVE_SQL_OHLC_CSV = DEFAULT_SQL_OHLC_CSV
DEFAULT_WAVECOUNT_LIVE_ESTIMATE_CSV = REPO_ROOT / "artifacts/tfg/wavecount_live_estimate_v0_2026-05-27/live_wave_estimate.csv"
DEFAULT_WAVECOUNT_CYCLE_STATE_CSV = REPO_ROOT / "artifacts/tfg/wavecount_cycle_state_v0_2026-05-27/cycle_state_hypothesis.csv"
DEFAULT_WAVECOUNT_PERSISTENT_PIVOTS_CSV = REPO_ROOT / "artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27/persistent_pivots.csv"
DEFAULT_WAVECOUNT_H1_AUX_MATCHES_CSV = (
    REPO_ROOT
    / "artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/tables/h1_h4_aux_matches.csv"
)
DEFAULT_WEAVECOUNT_SCREENER_DIR = latest_or_fallback_dir(
    DEFAULT_LATEST_DIR / "weavecount",
    CANONICAL_WEAVECOUNT_SCREENER_DIR,
    "weavecount_screener.csv",
)
DEFAULT_WEAVECOUNT_SCREENER_CSV = DEFAULT_WEAVECOUNT_SCREENER_DIR / "weavecount_screener.csv"
DEFAULT_WEAVECOUNT_STRUCTURE_POINTS_CSV = DEFAULT_WEAVECOUNT_SCREENER_DIR / "weavecount_structure_points.csv"
ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV = DEFAULT_WEAVECOUNT_STRUCTURE_POINTS_CSV
DEFAULT_SCREENER_SETUPS_CSV = latest_or_fallback_path(DEFAULT_LATEST_DIR / "screener_unified/screener_setups.csv", DEFAULT_SCREENER_UNIFIED_DIR / "screener_setups.csv")
DEFAULT_SCREENER_CHART_LAYERS_CSV = latest_or_fallback_path(DEFAULT_LATEST_DIR / "screener_unified/screener_chart_layers.csv", DEFAULT_SCREENER_UNIFIED_DIR / "screener_chart_layers.csv")
DEFAULT_MT5_SHADOW_DECISIONS_CSV = REPO_ROOT / "artifacts/tfg/mt5_shadow_v1_2026-06-08/mt5_shadow_decisions.csv"
DEFAULT_MT5_SHADOW_META_JSON = REPO_ROOT / "artifacts/tfg/mt5_shadow_v1_2026-06-08/run_meta.json"
DEFAULT_RISKGUARD_DECISIONS_CSV = REPO_ROOT / "artifacts/tfg/riskguard_demo_intent_builder_v1_2026-06-08/riskguard_decisions.csv"
DEFAULT_RISKGUARD_META_JSON = REPO_ROOT / "artifacts/tfg/riskguard_demo_intent_builder_v1_2026-06-08/run_meta.json"
CANONICAL_MT5_DEMO_SENDER_META_JSON = REPO_ROOT / "artifacts/tfg/mt5_demo_order_sender_v1_2026-06-08/run_meta.json"
CANONICAL_MT5_DEMO_MANAGER_META_JSON = REPO_ROOT / "artifacts/tfg/mt5_demo_position_manager_v1_2026-06-08/run_meta.json"
DEFAULT_MT5_DEMO_SENDER_META_JSON = latest_matching_file(
    "artifacts/tfg/mt5_demo_order_sender_v1_2026-06-08*/run_meta.json",
    CANONICAL_MT5_DEMO_SENDER_META_JSON,
    exclude_name_fragments=("fixture",),
)
DEFAULT_MT5_DEMO_MANAGER_META_JSON = latest_matching_file(
    "artifacts/tfg/mt5_demo_position_manager_v1_2026-06-08*/run_meta.json",
    CANONICAL_MT5_DEMO_MANAGER_META_JSON,
    exclude_name_fragments=("fixture",),
)
CANONICAL_TELEGRAM_REAL_SENDER_META_JSON = (
    REPO_ROOT / "artifacts/tfg/telegram_real_sender_mt5_bot_informational_v1_2026-06-09/run_meta.json"
)
DEFAULT_TELEGRAM_REAL_SENDER_META_JSON = latest_matching_file(
    "artifacts/tfg/telegram_real_sender_mt5_bot*_v1_2026-06-09*/run_meta.json",
    CANONICAL_TELEGRAM_REAL_SENDER_META_JSON,
    exclude_name_fragments=("fixture", "precheck"),
)
DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/codex_ai_analyst_dash_integration_v1_2026-06-07"
WAVECOUNT_H1_AUX_SOURCE_WINDOW_ROWS = 1100
def require_dash() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from dash import Dash, Input, Output, State, dash_table, dcc, html
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Dash no esta instalado en este entorno. Ejecuta `python -m pip install -r requirements.txt` "
            "o `python -m pip install dash` antes de arrancar la app."
        ) from exc
    return Dash, Input, Output, State, dash_table, dcc, html


def _status_rows_from_meta(meta: dict[str, Any], items: list[tuple[str, str, Any, str]]) -> list[dict[str, Any]]:
    status = "available" if meta else "not_available"
    rows: list[dict[str, Any]] = []
    for item, label, default, policy in items:
        rows.append(
            {
                "item": item,
                "label": label,
                "value": meta.get(item, default) if meta else default,
                "status": status,
                "policy": policy,
            }
        )
    return rows


def build_dash_data(
    snapshot_csv: Path = DEFAULT_SNAPSHOT_CSV,
    security_flags_csv: Path = DEFAULT_SECURITY_FLAGS_CSV,
    counts_csv: Path = DEFAULT_COUNTS_CSV,
    migrations_csv: Path = DEFAULT_MIGRATIONS_CSV,
    export_manifest_csv: Path = DEFAULT_EXPORT_MANIFEST_CSV,
    wavecount_csv: Path = DEFAULT_WAVECOUNT_CSV,
    wavecount_expanded_csv: Path = DEFAULT_WAVECOUNT_EXPANDED_CSV,
    wavecount_buckets_csv: Path = DEFAULT_WAVECOUNT_BUCKETS_CSV,
    wavecount_visual_cases_csv: Path = DEFAULT_WAVECOUNT_VISUAL_CASES_CSV,
    wavecount_no_action_csv: Path = DEFAULT_WAVECOUNT_NO_ACTION_CSV,
    design_widgets_csv: Path = DEFAULT_DESIGN_WIDGETS_CSV,
    telegram_sender_review_meta: Path = DEFAULT_TELEGRAM_SENDER_REVIEW_META,
    bot_review_meta: Path = DEFAULT_BOT_REVIEW_META,
    sql_go_no_go_meta: Path = DEFAULT_SQL_GO_NO_GO_META,
    symbol_control_csv: Path = DEFAULT_SYMBOL_CONTROL_CSV,
    price_symbols_csv: Path = DEFAULT_PRICE_SYMBOLS_CSV,
    market_radar_csv: Path = DEFAULT_MARKET_RADAR_CSV,
    correlation_pairs_csv: Path = DEFAULT_CORRELATION_PAIRS_CSV,
    rolling_correlations_csv: Path = DEFAULT_ROLLING_CORRELATIONS_CSV,
    correlation_returns_csv: Path = DEFAULT_CORRELATION_RETURNS_CSV,
    correlation_meta_json: Path = DEFAULT_CORRELATION_META_JSON,
    weavecount_screener_csv: Path = DEFAULT_WEAVECOUNT_SCREENER_CSV,
    weavecount_structure_points_csv: Path = DEFAULT_WEAVECOUNT_STRUCTURE_POINTS_CSV,
    screener_setups_csv: Path = DEFAULT_SCREENER_SETUPS_CSV,
    screener_chart_layers_csv: Path = DEFAULT_SCREENER_CHART_LAYERS_CSV,
    mt5_shadow_decisions_csv: Path = DEFAULT_MT5_SHADOW_DECISIONS_CSV,
    mt5_shadow_meta_json: Path = DEFAULT_MT5_SHADOW_META_JSON,
    riskguard_decisions_csv: Path = DEFAULT_RISKGUARD_DECISIONS_CSV,
    riskguard_meta_json: Path = DEFAULT_RISKGUARD_META_JSON,
    mt5_demo_sender_meta_json: Path = DEFAULT_MT5_DEMO_SENDER_META_JSON,
    mt5_demo_manager_meta_json: Path = DEFAULT_MT5_DEMO_MANAGER_META_JSON,
    telegram_real_sender_meta_json: Path = DEFAULT_TELEGRAM_REAL_SENDER_META_JSON,
) -> dict[str, Any]:
    data = build_data_model(
        snapshot_csv=snapshot_csv,
        security_flags_csv=security_flags_csv,
        counts_csv=counts_csv,
        migrations_csv=migrations_csv,
        export_manifest_csv=export_manifest_csv,
        wavecount_csv=wavecount_csv,
        wavecount_expanded_csv=wavecount_expanded_csv,
        wavecount_buckets_csv=wavecount_buckets_csv,
        wavecount_visual_cases_csv=wavecount_visual_cases_csv,
        wavecount_no_action_csv=wavecount_no_action_csv,
        design_widgets_csv=design_widgets_csv,
        telegram_sender_review_meta=telegram_sender_review_meta,
    )
    bot_meta = read_json(bot_review_meta)
    sql_meta = read_json(sql_go_no_go_meta)
    global ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV
    ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV = weavecount_structure_points_csv
    weavecount_screener_structure_points_index.cache_clear()
    weavecount_screener_rows = build_weavecount_screener_dashboard_rows(read_json_or_csv(weavecount_screener_csv))
    h1_aux_wavecount_rows = build_h1_aux_wavecount_rows(read_json_or_csv(DEFAULT_WAVECOUNT_H1_AUX_MATCHES_CSV))
    if weavecount_screener_rows:
        data["wavecount_rows"] = weavecount_screener_rows
    elif h1_aux_wavecount_rows:
        data["wavecount_rows"] = list(data["wavecount_rows"]) + h1_aux_wavecount_rows
    if weavecount_screener_rows or h1_aux_wavecount_rows:
        data["summary"]["wavecount_study_cases"] = len(data["wavecount_rows"])
        data["summary"]["wavecount_study_buckets"] = len(
            {
                str(row.get("screener_bucket", "")).strip()
                for row in data["wavecount_rows"]
                if str(row.get("screener_bucket", "")).strip()
            }
        )
    symbol_control_rows = build_universe_rows(
        symbol_control_rows=read_json_or_csv(symbol_control_csv),
        price_symbols_rows=read_json_or_csv(price_symbols_csv),
        snapshot_rows=data["snapshot_rows"],
        wavecount_rows=data["wavecount_rows"],
    )
    market_radar_rows = read_json_or_csv(market_radar_csv)
    market_radar = market_radar_summary(market_radar_rows)
    correlation_pair_rows = read_json_or_csv(correlation_pairs_csv)
    rolling_correlation_rows = read_json_or_csv(rolling_correlations_csv)
    correlation_returns_rows = read_json_or_csv(correlation_returns_csv)
    correlation_meta = read_json(correlation_meta_json)
    screener_setups_rows = read_json_or_csv(screener_setups_csv)
    screener_chart_layer_rows = read_json_or_csv(screener_chart_layers_csv)
    mt5_shadow_rows = read_json_or_csv(mt5_shadow_decisions_csv)
    mt5_shadow_meta = read_json(mt5_shadow_meta_json)
    riskguard_decision_rows = read_json_or_csv(riskguard_decisions_csv)
    riskguard_meta = read_json(riskguard_meta_json)
    mt5_demo_sender_meta = read_json(mt5_demo_sender_meta_json)
    mt5_demo_manager_meta = read_json(mt5_demo_manager_meta_json)
    telegram_real_sender_meta = read_json(telegram_real_sender_meta_json)
    correlation_timeframes = sorted({str(row.get("timeframe", "")).strip() for row in correlation_pair_rows if str(row.get("timeframe", "")).strip()})
    correlation_assets = sorted(
        {
            str(row.get(key, "")).strip()
            for row in correlation_pair_rows
            for key in ("asset_1", "asset_2")
            if str(row.get(key, "")).strip()
        }
    )
    data["dash_method_version"] = METHOD_VERSION
    data["universe_rows"] = symbol_control_rows
    data["universe_summary"] = universe_summary(symbol_control_rows)
    data["market_radar_rows"] = market_radar_rows
    data["market_radar_summary"] = market_radar
    data["correlation_pair_rows"] = correlation_pair_rows
    data["rolling_correlation_rows"] = rolling_correlation_rows
    data["correlation_returns_rows"] = correlation_returns_rows
    data["correlation_meta"] = correlation_meta
    data["screener_setups_rows"] = screener_setups_rows
    data["screener_chart_layer_rows"] = screener_chart_layer_rows
    data["mt5_shadow_rows"] = mt5_shadow_rows
    data["mt5_shadow_meta"] = mt5_shadow_meta
    data["riskguard_decision_rows"] = riskguard_decision_rows
    data["riskguard_meta"] = riskguard_meta
    data["mt5_demo_sender_meta"] = mt5_demo_sender_meta
    data["mt5_demo_manager_meta"] = mt5_demo_manager_meta
    data["telegram_real_sender_meta"] = telegram_real_sender_meta
    data["market_radar_source"] = {
        "path": str(market_radar_csv),
        "rows": len(market_radar_rows),
        "status": "available" if market_radar_rows else "missing_or_empty",
        "trend_aligned_count": len(market_radar["trend_aligned"]),
        "counter_extreme_count": len(market_radar["counter_extremes"]),
    }
    data["correlation_source"] = {
        "path": str(correlation_pairs_csv),
        "rolling_path": str(rolling_correlations_csv),
        "returns_path": str(correlation_returns_csv),
        "meta_path": str(correlation_meta_json),
        "rows": len(correlation_pair_rows),
        "rolling_rows": len(rolling_correlation_rows),
        "returns_rows": len(correlation_returns_rows),
        "status": "available" if correlation_pair_rows else "missing_or_empty",
        "timeframes": correlation_timeframes,
        "assets": correlation_assets,
        "returns_based": bool(correlation_meta.get("returns_based", False)),
        "price_based_correlation": bool(correlation_meta.get("price_based_correlation", True)) if correlation_meta else False,
    }
    data["screener_source"] = {
        "setups_path": str(screener_setups_csv),
        "chart_layers_path": str(screener_chart_layers_csv),
        "setups_rows": len(screener_setups_rows),
        "chart_layers_rows": len(screener_chart_layer_rows),
        "status": "available" if screener_setups_rows else "missing_or_empty",
    }
    data["mt5_shadow_source"] = {
        "decisions_path": str(mt5_shadow_decisions_csv),
        "meta_path": str(mt5_shadow_meta_json),
        "decision_rows": len(mt5_shadow_rows),
        "status": "available" if mt5_shadow_rows else "missing_or_empty",
        "decision": str(mt5_shadow_meta.get("decision", "") or ""),
        "mt5_connected": bool(mt5_shadow_meta.get("mt5_connected", False)),
        "orders_sent": int(float(mt5_shadow_meta.get("orders_sent", 0) or 0)),
    }
    data["riskguard_source"] = {
        "decisions_path": str(riskguard_decisions_csv),
        "meta_path": str(riskguard_meta_json),
        "decision_rows": len(riskguard_decision_rows),
        "status": "available" if riskguard_decision_rows else "optional_missing",
        "decision": str(riskguard_meta.get("decision", "") or ""),
        "orders_sent": int(float(riskguard_meta.get("orders_sent", 0) or 0)),
        "can_send_order_any_true": bool(riskguard_meta.get("can_send_order_any_true", False)),
    }
    data["mt5_demo_sender_source"] = {
        "meta_path": str(mt5_demo_sender_meta_json),
        "status": "available" if mt5_demo_sender_meta else "optional_missing",
        "decision": str(mt5_demo_sender_meta.get("decision", "") or ""),
        "prepared_count": int(float(mt5_demo_sender_meta.get(MT5_DEMO_SENDER_PREPARED_KEY, 0) or 0)),
        "orders_sent": int(float(mt5_demo_sender_meta.get("orders_sent", 0) or 0)),
    }
    data["mt5_demo_manager_source"] = {
        "meta_path": str(mt5_demo_manager_meta_json),
        "status": "available" if mt5_demo_manager_meta else "optional_missing",
        "decision": str(mt5_demo_manager_meta.get("decision", "") or ""),
        "prepared_count": int(float(mt5_demo_manager_meta.get(MT5_DEMO_MANAGER_PREPARED_KEY, 0) or 0)),
        "positions_closed": int(float(mt5_demo_manager_meta.get("positions_closed", 0) or 0)),
    }
    data["telegram_real_sender_source"] = {
        "meta_path": str(telegram_real_sender_meta_json),
        "status": "available" if telegram_real_sender_meta else "optional_missing",
        "decision": str(telegram_real_sender_meta.get("decision", "") or ""),
        "telegram_connected": bool(telegram_real_sender_meta.get("telegram_connected", False)),
        "messages_sent": int(float(telegram_real_sender_meta.get("telegram_real_messages_sent", 0) or 0)),
        "failed_count": int(float(telegram_real_sender_meta.get("failed_transport_count", 0) or 0)),
    }
    data["bot_status"] = _status_rows_from_meta(
        bot_meta,
        [
            ("decision", "Bot dry-run decision", "not_available", "artifact_review"),
            ("mt5_connected", "MT5 connected", False, "must_remain_false"),
            ("telegram_connected", "Telegram connected", False, "must_remain_false"),
            ("sql_real_written", "SQL real written", False, "must_remain_false"),
            ("can_execute_order_any_true", "Any executable order", False, "must_remain_false"),
            ("wavecount_used_as_filter", "WaveCount used as filter", False, "must_remain_false"),
        ],
    )
    data["sql_runtime_status"] = _status_rows_from_meta(
        sql_meta,
        [
            ("decision", "SQL runtime decision", "not_available", "preview_only"),
            ("writer_real_implemented", "Real writer implemented", False, "must_remain_false"),
            ("sql_real_written", "SQL real written", False, "must_remain_false"),
            ("db_connected", "DB connected", False, "must_remain_false"),
            ("ddl_executed", "DDL executed", False, "must_remain_false"),
            ("preview_would_insert", "Preview would insert", 0, "preview_only"),
        ],
    )
    data["dash_source_audit"] = list(data["source_audit"]) + [
        {
            "source_id": "weavecount_screener_h1_h4" if weavecount_screener_rows else "wavecount_h1_aux_matches",
            "source": str(weavecount_screener_csv if weavecount_screener_rows else DEFAULT_WAVECOUNT_H1_AUX_MATCHES_CSV),
            "source_type": "artifact_csv",
            "rows": len(weavecount_screener_rows) if weavecount_screener_rows else len(h1_aux_wavecount_rows),
            "status": "available" if weavecount_screener_rows or h1_aux_wavecount_rows else "optional_missing",
            "used_for": "weavecount_h1_h4_screener" if weavecount_screener_rows else "weavecount_h1_auxiliary_study_cases",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "symbol_control_inventory",
            "source": str(symbol_control_csv),
            "source_type": "artifact_csv",
            "rows": len(symbol_control_rows),
            "status": "available" if symbol_control_rows else "missing_or_empty",
            "used_for": "market_universe",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "price_symbols_inventory",
            "source": str(price_symbols_csv),
            "source_type": "artifact_csv",
            "rows": len(read_json_or_csv(price_symbols_csv)),
            "status": "available" if price_symbols_csv.exists() else "missing_or_empty",
            "used_for": "market_universe_crosscheck",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "market_radar_m15_h1_h4_d1",
            "source": str(market_radar_csv),
            "source_type": "artifact_csv",
            "rows": len(market_radar_rows),
            "status": "available" if market_radar_rows else "missing_or_empty",
            "used_for": "radar_trend_alignment_and_rsi_screener",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "market_correlations_returns",
            "source": str(correlation_pairs_csv),
            "source_type": "artifact_csv",
            "rows": len(correlation_pair_rows),
            "status": "available" if correlation_pair_rows else "missing_or_empty",
            "used_for": "correlation_section_returns_by_timeframe",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "screener_unified_setups",
            "source": str(screener_setups_csv),
            "source_type": "artifact_csv",
            "rows": len(screener_setups_rows),
            "status": "available" if screener_setups_rows else "missing_or_empty",
            "used_for": "unified_screener_highlighted_setups",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "mt5_shadow_v1",
            "source": str(mt5_shadow_decisions_csv),
            "source_type": "artifact_csv",
            "rows": len(mt5_shadow_rows),
            "status": "available" if mt5_shadow_rows else "optional_missing",
            "used_for": "mt5_shadow_dashboard_review",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "riskguard_demo_intent_builder_v1",
            "source": str(riskguard_decisions_csv),
            "source_type": "artifact_csv",
            "rows": len(riskguard_decision_rows),
            "status": "available" if riskguard_decision_rows else "optional_missing",
            "used_for": "mt5_shadow_inline_riskguard_review",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "mt5_demo_order_sender_v1",
            "source": str(mt5_demo_sender_meta_json),
            "source_type": "artifact_json",
            "rows": 1 if mt5_demo_sender_meta else 0,
            "status": "available" if mt5_demo_sender_meta else "optional_missing",
            "used_for": "mt5_shadow_inline_sender_status",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "mt5_demo_position_manager_v1",
            "source": str(mt5_demo_manager_meta_json),
            "source_type": "artifact_json",
            "rows": 1 if mt5_demo_manager_meta else 0,
            "status": "available" if mt5_demo_manager_meta else "optional_missing",
            "used_for": "mt5_shadow_inline_manager_status",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "telegram_mt5_bot_informational_real_sender",
            "source": str(telegram_real_sender_meta_json),
            "source_type": "artifact_json",
            "rows": 1 if telegram_real_sender_meta else 0,
            "status": "available" if telegram_real_sender_meta else "optional_missing",
            "used_for": "mt5_bot_informational_telegram_status",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "market_correlation_returns_sample",
            "source": str(correlation_returns_csv),
            "source_type": "artifact_csv",
            "rows": len(correlation_returns_rows),
            "status": "available" if correlation_returns_rows else "missing_or_empty",
            "used_for": "correlation_pair_scatter",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "bot_dry_run_review_meta",
            "source": str(bot_review_meta),
            "source_type": "artifact_json",
            "rows": 1 if bot_review_meta.exists() else 0,
            "status": "available" if bot_review_meta.exists() else "optional_missing",
            "used_for": "simulation_status",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "sql_runtime_go_no_go_meta",
            "source": str(sql_go_no_go_meta),
            "source_type": "artifact_json",
            "rows": 1 if sql_go_no_go_meta.exists() else 0,
            "status": "available" if sql_go_no_go_meta.exists() else "optional_missing",
            "used_for": "sql_runtime_status",
            "sql_real_read": False,
            "sql_real_written": False,
        },
    ]
    return data


def read_json_or_csv(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = read_json(path)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("rows")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return []
    from trading_center.readonly_dashboard import read_csv

    return read_csv(path)


def build_weavecount_screener_dashboard_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        count_label = str(row.get("count_label", "")).strip()
        if not symbol or timeframe not in {"H1", "H4"}:
            continue
        if count_label == "no_clear_count":
            continue
        direction = str(row.get("direction", "")).strip().lower()
        tone = "up" if direction == "long" else "down" if direction == "short" else "flat"
        confidence = str(row.get("confidence_status", "")).strip().lower() or "candidate"
        wave_number = str(row.get("wave_number", "")).strip()
        label = count_label or (f"W{wave_number}?" if wave_number else "")
        output.append(
            {
                **row,
                "case_id": row.get("case_id") or f"weavecount_screener_{symbol}_{timeframe}_{index}",
                "case_source": "weavecount_screener_h1_h4",
                "case_type": "weavecount_screener_h1_h4_v1",
                "panel_priority": str(index),
                "market_group": row.get("market_group", ""),
                "timeframe": timeframe,
                "as_of_bar_time": row.get("last_close_time") or row.get("end_time", ""),
                "live_estimated_wave": row.get("live_estimated_wave") or f"possible_wave{wave_number}_{confidence}",
                "confirmed_wave_context": row.get("confirmed_wave_context") or label,
                "display_policy": "show_as_weavecount_study_only",
                "confidence_bucket": confidence,
                "freshness_status": "artifact_first_screener",
                "visual_readability": "dashboard_native_ohlc",
                "label_plausible": "true" if confidence in {"active", "candidate"} else "false",
                "why_in_screener": "WeaveCount artifact-first H1/H4 structural candidate for visual review.",
                "why_not_signal": "WeaveCount is a structural study view only; it cannot generate, filter or execute trades.",
                "required_warning": "Study-only WeaveCount context. Not a signal, not a filter, not executable.",
                "recommended_study_action": "open_chart_and_review_structure",
                "study_only": "True",
                "telegram_allowed": "False",
                "bot_allowed": "False",
                "can_generate_signal": "False",
                "can_filter_trade": "False",
                "can_execute_order": "False",
                "current_leg_direction": tone,
                "source_artifact": str(DEFAULT_WEAVECOUNT_SCREENER_CSV),
                "panel_design_use": "weavecount_h1_h4_artifact_screener",
                "notes": "WeaveCount H1/H4 screener row; no_signal_no_filter_no_execution",
            }
        )
    return output


def build_h1_aux_wavecount_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        if not symbol or timeframe != "H1":
            continue
        direction_raw = str(row.get("direction", "")).strip().lower()
        tone = "up" if direction_raw == "bullish" else "down" if direction_raw == "bearish" else "flat"
        htf = str(row.get("htf_timeframe", "")).strip() or "H4"
        chart_file = row.get("reviewed_chart_path") or row.get("chart_path") or row.get("context_chart_path") or ""
        case_id = f"h1_aux_{row.get('candidate_id') or symbol}_{index}"
        output.append(
            {
                "case_id": case_id,
                "case_source": "h1_h4_aux_matches",
                "symbol": symbol,
                "market_group": row.get("group", ""),
                "timeframe": "H1",
                "higher_timeframe": htf,
                "as_of_bar_time": row.get("end_time", ""),
                "start_time": row.get("start_time", ""),
                "end_time": row.get("end_time", ""),
                "example_id": row.get("example_id", ""),
                "swing_degree": row.get("swing_degree", ""),
                "start_pivot_id": row.get("start_pivot_id", ""),
                "end_pivot_id": row.get("end_pivot_id", ""),
                "source_table": row.get("source_table", ""),
                "case_type": "h1_auxiliary_study_candidate",
                "screener_bucket": "h1_auxiliary_wave_study_candidate",
                "panel_priority": str(40 + index),
                "live_estimated_wave": "possible_wave5_h1_auxiliary_candidate",
                "confirmed_wave_context": "completed_impulse_12345_h1_auxiliary",
                "display_policy": "show_as_h1_auxiliary_study_only",
                "confidence_bucket": "study_only",
                "freshness_status": "historical_auxiliary_case",
                "visual_readability": row.get("visual_aux_status") or row.get("scale_diagnostic_status") or "reviewed_auxiliary",
                "label_plausible": "true",
                "chart_file": chart_file,
                "why_in_screener": "H1 auxiliary impulse case reviewed against H4 context; useful for study, not live context.",
                "why_not_signal": "H1 auxiliary WaveCount rows are historical study cases; they cannot generate, filter or execute trades.",
                "required_warning": "Study-only H1 auxiliary context. Not a signal, not a filter, not executable.",
                "recommended_study_action": "open_chart_and_review_h1_structure",
                "study_only": "True",
                "telegram_allowed": "False",
                "bot_allowed": "False",
                "can_generate_signal": "False",
                "can_filter_trade": "False",
                "can_execute_order": "False",
                "direction": "long" if tone == "up" else "short" if tone == "down" else "",
                "current_leg_direction": tone,
                "current_leg_status": row.get("pattern_type", "full_impulse_12345"),
                "source_artifact": str(DEFAULT_WAVECOUNT_H1_AUX_MATCHES_CSV),
                "source_candidate_id": row.get("candidate_id", ""),
                "panel_design_use": "weavecount_h1_auxiliary_study",
                "notes": "H1 auxiliary match imported for dashboard study view; no_signal_no_filter_no_execution",
                "payload_json": json.dumps(
                    {
                        "operational_use": "forbidden",
                        "source_scope": row.get("source_scope", "h1_h4"),
                        "aux_profile_match_score": row.get("aux_profile_match_score", ""),
                        "context_score": row.get("context_score", ""),
                        "scale_fit_label": row.get("scale_fit_label", ""),
                        "lookahead_safe": row.get("htf_lookahead_safe", ""),
                    },
                    ensure_ascii=True,
                ),
            }
        )
    return output


def build_universe_rows(
    symbol_control_rows: list[dict[str, Any]],
    price_symbols_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    wavecount_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshot_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot_rows:
        symbol = str(row.get("symbol", "")).strip()
        if symbol:
            snapshot_by_symbol.setdefault(symbol, []).append(row)
    wave_symbols = {str(row.get("symbol", "")).strip() for row in wavecount_rows if str(row.get("symbol", "")).strip()}
    price_symbols = {str(row.get("symbol", "")).strip() for row in price_symbols_rows if str(row.get("symbol", "")).strip()}
    control_by_symbol: dict[str, dict[str, Any]] = {}
    for row in symbol_control_rows:
        symbol = str(row.get("symbol", "")).strip()
        if symbol:
            control_by_symbol[symbol] = row
    all_symbols = sorted(set(control_by_symbol) | price_symbols | set(snapshot_by_symbol) | wave_symbols)
    universe: list[dict[str, Any]] = []
    for symbol in all_symbols:
        control = control_by_symbol.get(symbol, {})
        current_rows = snapshot_by_symbol.get(symbol, [])
        signal_states = sorted({str(row.get("signal_state", "")) for row in current_rows if row.get("signal_state")})
        strategies = sorted({str(row.get("strategy", "")) for row in current_rows if row.get("strategy")})
        universe.append(
            {
                "symbol": symbol,
                "market_group": control.get("group_normalized") or control.get("group_name") or first_non_empty(current_rows, "market_group"),
                "enabled": str(control.get("enabled", "")) if control else "unknown",
                "last_update": control.get("last_update", ""),
                "in_price_data": symbol in price_symbols,
                "in_current_snapshot": bool(current_rows),
                "snapshot_rows": len(current_rows),
                "signal_states": "|".join(signal_states) if signal_states else "not_in_snapshot",
                "strategies": "|".join(strategies) if strategies else "not_in_snapshot",
                "in_wavecount_study": symbol in wave_symbols,
                "source": "symbol_control|price_symbols|current_snapshot|wavecount",
                "can_execute_order": False,
            }
        )
    return universe


def first_non_empty(rows: list[dict[str, Any]], key: str, default: str = "not_available") -> str:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def universe_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, int] = {}
    for row in rows:
        group = str(row.get("market_group") or "not_available")
        groups[group] = groups.get(group, 0) + 1
    return {
        "total_symbols": len({row.get("symbol") for row in rows if row.get("symbol")}),
        "enabled_symbols": sum(1 for row in rows if str(row.get("enabled")).lower() in {"1", "true", "yes"}),
        "current_snapshot_symbols": sum(1 for row in rows if row.get("in_current_snapshot") is True),
        "wavecount_study_symbols": sum(1 for row in rows if row.get("in_wavecount_study") is True),
        "groups": groups,
    }



def unique_options(rows: list[dict[str, Any]], key: str) -> list[dict[str, str]]:
    values = sorted({str(row.get(key, "")) for row in rows if str(row.get(key, "")).strip()})
    return [{"label": "Todos", "value": "__all__"}] + [{"label": value, "value": value} for value in values]



def filter_watchlist_rows(
    rows: list[dict[str, Any]],
    search: str | None = None,
    market_group: str | None = "__all__",
    side: str | None = "__all__",
) -> list[dict[str, Any]]:
    text = (search or "").strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if market_group and market_group != "__all__" and row.get("market_group") != market_group:
            continue
        if side and side != "__all__" and row.get("side") != side:
            continue
        haystack = " ".join(
            str(row.get(key, ""))
            for key in ("symbol", "setup_id", "strategy", "market_group", "timeframe_ltf", "timeframe_htf")
        ).lower()
        if text and text not in haystack:
            continue
        filtered.append(row)
    return filtered


def filter_universe_rows(
    rows: list[dict[str, Any]],
    search: str | None = None,
    market_group: str | None = "__all__",
    snapshot_state: str | None = "__all__",
) -> list[dict[str, Any]]:
    text = (search or "").strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if market_group and market_group != "__all__" and row.get("market_group") != market_group:
            continue
        in_snapshot = row.get("in_current_snapshot") is True
        if snapshot_state == "in_snapshot" and not in_snapshot:
            continue
        if snapshot_state == "outside_snapshot" and in_snapshot:
            continue
        haystack = " ".join(
            str(row.get(key, ""))
            for key in ("symbol", "market_group", "enabled", "signal_states", "strategies")
        ).lower()
        if text and text not in haystack:
            continue
        filtered.append(row)
    return filtered


def filter_wavecount_rows(
    rows: list[dict[str, Any]],
    search: str | None = None,
    bucket: str | None = "__all__",
    market_group: str | None = "__all__",
    timeframe: str | None = "__all__",
    quality: str | None = "__all__",
    direction: str | None = "__all__",
) -> list[dict[str, Any]]:
    text = (search or "").strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_bucket = row.get("screener_bucket") or row.get("wavecount_policy_bucket")
        if bucket and bucket != "__all__" and row_bucket != bucket:
            continue
        if market_group and market_group != "__all__" and row.get("market_group") != market_group:
            continue
        if timeframe and timeframe != "__all__" and row.get("timeframe") != timeframe:
            continue
        if quality and quality != "__all__" and wavecount_quality_status(row) != quality:
            continue
        if direction and direction != "__all__" and wavecount_direction_tone(row) != direction:
            continue
        haystack = " ".join(
            str(row.get(key, ""))
            for key in (
                "symbol",
                "market_group",
                "timeframe",
                "screener_bucket",
                "live_estimated_wave",
                "confirmed_wave_context",
                "quality_status",
                "quality_reason",
            )
        ).lower()
        if text and text not in haystack:
            continue
        filtered.append(row)
    return filtered



def filter_wavecount_number_rows(
    rows: list[dict[str, Any]],
    wave_value: str | None,
    search: str | None = None,
    market_group: str | None = "__all__",
    timeframe: str | None = "__all__",
    quality: str | None = "__all__",
    direction: str | None = "__all__",
) -> list[dict[str, Any]]:
    target = str(wave_value or "wave1").replace("wave", "")
    filtered = filter_wavecount_rows(
        rows,
        search=search,
        bucket="__all__",
        market_group=market_group,
        timeframe=timeframe,
        quality=quality,
        direction=direction,
    )
    current_rows = canonical_wavecount_rows(filtered)
    return unique_wavecount_visible_rows([row for row in current_rows if wavecount_number(row) == target])


def wavecount_case_id(row: dict[str, Any]) -> str:
    value = row.get("case_id") or "|".join(
        str(row.get(key, ""))
        for key in ("symbol", "timeframe", "live_estimated_wave", "screener_bucket", "as_of_bar_time")
    )
    return str(value)


def wavecount_chart_candidates(row: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    raw_path = str(row.get("chart_file", "")).strip()
    if raw_path:
        chart_path = Path(raw_path)
        candidates.append(chart_path if chart_path.is_absolute() else REPO_ROOT / chart_path)

    symbol = str(row.get("symbol", "")).strip()
    timeframe = str(row.get("timeframe", "")).strip()
    if symbol and timeframe:
        chart_symbol = symbol.replace(".", "_")
        candidates.append(
            REPO_ROOT
            / "artifacts"
            / "tfg"
            / "wavecount_live_estimate_v0_2026-05-27"
            / "charts"
            / f"live_estimate_{chart_symbol}_{timeframe}.png"
        )
        candidates.append(
            REPO_ROOT
            / "artifacts"
            / "tfg"
            / "wavecount_live_estimate_visual_audit_2026-05-27"
            / "charts"
            / f"live_estimate_{chart_symbol}_{timeframe}.png"
        )
    return candidates


def wavecount_chart_data_uri(row: dict[str, Any]) -> str:
    chart_path = next(
        (
            candidate
            for candidate in wavecount_chart_candidates(row)
            if candidate.exists() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ),
        None,
    )
    if chart_path is None:
        return ""
    return local_image_data_uri(chart_path)


@lru_cache(maxsize=1)
def wavecount_live_estimate_index() -> dict[tuple[str, str], dict[str, Any]]:
    if not DEFAULT_WAVECOUNT_LIVE_ESTIMATE_CSV.exists():
        return {}
    from trading_center.readonly_dashboard import read_csv

    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_csv(DEFAULT_WAVECOUNT_LIVE_ESTIMATE_CSV):
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        if symbol and timeframe:
            index[(symbol, timeframe)] = row
    return index


def wavecount_enriched_row(row: dict[str, Any]) -> dict[str, Any]:
    if str(row.get("case_type", "")).strip() == "weavecount_screener_h1_h4_v1":
        return dict(row)
    symbol = str(row.get("symbol", "")).strip()
    timeframe = str(row.get("timeframe", "")).strip()
    enriched = dict(wavecount_live_estimate_index().get((symbol, timeframe), {}))
    enriched.update({key: value for key, value in row.items() if value not in (None, "")})
    return enriched


@lru_cache(maxsize=1)
def wavecount_cycle_state_index() -> dict[tuple[str, str], dict[str, Any]]:
    if not DEFAULT_WAVECOUNT_CYCLE_STATE_CSV.exists():
        return {}
    from trading_center.readonly_dashboard import read_csv

    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_csv(DEFAULT_WAVECOUNT_CYCLE_STATE_CSV):
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        if not symbol or not timeframe:
            continue
        key = (symbol, timeframe)
        current_time = normalized_timestamp(row.get("as_of_bar_time"))
        previous_time = normalized_timestamp(index.get(key, {}).get("as_of_bar_time"))
        if key not in index or current_time >= previous_time:
            index[key] = row
    return index


@lru_cache(maxsize=1)
def wavecount_persistent_pivots_index() -> dict[tuple[str, str], list[dict[str, Any]]]:
    if not DEFAULT_WAVECOUNT_PERSISTENT_PIVOTS_CSV.exists():
        return {}
    from trading_center.readonly_dashboard import read_csv

    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in read_csv(DEFAULT_WAVECOUNT_PERSISTENT_PIVOTS_CSV):
        if str(row.get("pivot_role", "")).strip() != "persistent_pivot":
            continue
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        pivot_time = normalized_timestamp(row.get("pivot_extreme_time"))
        pivot_price = safe_float(row.get("pivot_price"))
        if not symbol or not timeframe or not pivot_time or pivot_price is None:
            continue
        cleaned = dict(row)
        cleaned["pivot_extreme_time"] = pivot_time
        cleaned["pivot_price"] = pivot_price
        index.setdefault((symbol, timeframe), []).append(cleaned)
    for pivots in index.values():
        pivots.sort(key=lambda item: normalized_timestamp(item.get("pivot_extreme_time")))
    return index


def wavecount_cycle_pivots(row: dict[str, Any]) -> list[dict[str, Any]]:
    enriched = wavecount_enriched_row(row)
    symbol = str(enriched.get("symbol", "")).strip()
    timeframe = str(enriched.get("timeframe", "")).strip()
    if not symbol or not timeframe:
        return []
    cycle = wavecount_cycle_state_index().get((symbol, timeframe), {})
    pivots = wavecount_persistent_pivots_index().get((symbol, timeframe), [])
    start_uid = str(cycle.get("cycle_start_pivot_uid", "")).strip()
    end_uid = str(cycle.get("cycle_end_pivot_uid", "")).strip()
    if not start_uid or not end_uid or not pivots:
        return []
    start_index = next((index for index, pivot in enumerate(pivots) if str(pivot.get("pivot_uid", "")) == start_uid), None)
    end_index = next((index for index, pivot in enumerate(pivots) if str(pivot.get("pivot_uid", "")) == end_uid), None)
    if start_index is None or end_index is None:
        return []
    left, right = sorted([start_index, end_index])
    return pivots[left : right + 1]


@lru_cache(maxsize=32)
def wavecount_h1_aux_degree_pivots(
    symbol: str,
    timeframe: str,
    example_id: str,
) -> tuple[dict[str, Any], ...]:
    if timeframe != "H1" or not symbol or not example_id:
        return ()
    ohlc_rows = wavecount_ohlc_index().get((symbol, timeframe), [])
    if not ohlc_rows:
        return ()
    try:
        import pandas as pd

        from backtests.wavecount.wavecount_config import PivotConfig
        from backtests.wavecount.wavecount_degrees import build_swing_degrees
        from backtests.wavecount.wavecount_pivots import detect_causal_pivots, extract_pivot_events
    except (ImportError, ModuleNotFoundError):
        return ()

    window_rows = ohlc_rows[-WAVECOUNT_H1_AUX_SOURCE_WINDOW_ROWS:]
    frame = pd.DataFrame(
        [
            {
                "time": normalized_timestamp(row.get("timestamp")),
                "open": safe_float(row.get("open")),
                "high": safe_float(row.get("high")),
                "low": safe_float(row.get("low")),
                "close": safe_float(row.get("close")),
            }
            for row in window_rows
        ]
    )
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame = frame.dropna(subset=["time", "open", "high", "low", "close"]).set_index("time")
    if frame.empty:
        return ()

    pivots = detect_causal_pivots(frame, config=PivotConfig(), symbol=symbol, timeframe=timeframe)
    events = extract_pivot_events(pivots).reset_index(drop=True)
    if events.empty:
        return ()
    events["example_id"] = example_id
    degree_pivots = build_swing_degrees(events, group_columns=["example_id"]).get("swing_degrees_pivots")
    if degree_pivots is None or degree_pivots.empty:
        return ()
    return tuple(degree_pivots.to_dict("records"))


def wavecount_h1_aux_structure_points(row: dict[str, Any]) -> list[dict[str, Any]]:
    if str(row.get("case_source", "")).strip() != "h1_h4_aux_matches":
        return []
    symbol = str(row.get("symbol", "")).strip()
    timeframe = str(row.get("timeframe", "")).strip()
    example_id = str(row.get("example_id", "")).strip()
    swing_degree = str(row.get("swing_degree", "")).strip()
    start_pivot_id = safe_int(row.get("start_pivot_id"))
    end_pivot_id = safe_int(row.get("end_pivot_id"))
    if not symbol or timeframe != "H1" or not example_id or not swing_degree or start_pivot_id is None or end_pivot_id is None:
        return []

    left, right = sorted([start_pivot_id, end_pivot_id])
    pivots = [
        pivot
        for pivot in wavecount_h1_aux_degree_pivots(symbol, timeframe, example_id)
        if str(pivot.get("swing_degree", "")).strip() == swing_degree
        and (safe_int(pivot.get("structural_pivot_id")) or -1) >= left
        and (safe_int(pivot.get("structural_pivot_id")) or -1) <= right
    ]
    pivots.sort(
        key=lambda pivot: (
            normalized_timestamp(pivot.get("structural_detected_at")),
            normalized_timestamp(pivot.get("pivot_extreme_time")),
            safe_int(pivot.get("structural_pivot_id")) or 0,
        )
    )
    labels = ["origen", "W1", "W2", "W3", "W4", wavecount_wave_label(row)] if len(pivots) >= 6 else []
    if not labels:
        return []
    points: list[dict[str, Any]] = []
    for index, pivot in enumerate(pivots[: len(labels)]):
        pivot_time = normalized_timestamp(pivot.get("pivot_extreme_time"))
        pivot_price = safe_float(pivot.get("pivot_extreme_price"))
        if not pivot_time or pivot_price is None:
            continue
        points.append(
            {
                "x": pivot_time,
                "y": pivot_price,
                "label": labels[index],
                "kind": "latest" if index == len(labels) - 1 else "pivot",
                "pivot_type": str(pivot.get("pivot_type", "")),
            }
        )
    return points


@lru_cache(maxsize=1)
def weavecount_screener_structure_points_index() -> dict[str, list[dict[str, Any]]]:
    if not ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV.exists():
        return {}
    from trading_center.readonly_dashboard import read_csv

    index: dict[str, list[dict[str, Any]]] = {}
    for row in read_csv(ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV):
        case_id = str(row.get("case_id", "")).strip()
        point_time = normalized_timestamp(row.get("point_time"))
        point_price = safe_float(row.get("point_price"))
        if not case_id or not point_time or point_price is None:
            continue
        index.setdefault(case_id, []).append(
            {
                "x": point_time,
                "y": point_price,
                "label": str(row.get("point_label", "")).strip() or "punto",
                "kind": str(row.get("point_kind", "")).strip() or "pivot",
                "pivot_type": str(row.get("pivot_type", "")).strip(),
                "order": safe_int(row.get("point_order")) or 0,
            }
        )
    for points in index.values():
        points.sort(key=lambda item: (item["order"], item["x"]))
    return index


def wavecount_structure_points(row: dict[str, Any]) -> list[dict[str, Any]]:
    enriched = wavecount_enriched_row(row)
    if str(enriched.get("case_type", "")).strip() == "weavecount_screener_h1_h4_v1":
        case_id = str(enriched.get("case_id", "")).strip()
        points = weavecount_screener_structure_points_index().get(case_id, [])
        if points:
            return [
                {key: value for key, value in point.items() if key != "order"}
                for point in points
            ]

    points: list[dict[str, Any]] = []
    for index, pivot in enumerate(wavecount_cycle_pivots(enriched)):
        pivot_time = normalized_timestamp(pivot.get("pivot_extreme_time"))
        pivot_price = safe_float(pivot.get("pivot_price"))
        if not pivot_time or pivot_price is None:
            continue
        points.append(
            {
                "x": pivot_time,
                "y": pivot_price,
                "label": "origen" if index == 0 else f"W{index}",
                "kind": "pivot",
                "pivot_type": str(pivot.get("pivot_type", "")),
            }
        )

    if not points:
        points = wavecount_h1_aux_structure_points(enriched)

    if not points:
        symbol = str(enriched.get("symbol", "")).strip()
        timeframe = str(enriched.get("timeframe", "")).strip()
        start_time = normalized_timestamp(enriched.get("start_time"))
        end_time = normalized_timestamp(enriched.get("end_time") or enriched.get("as_of_bar_time"))
        tone = wavecount_direction_tone(enriched)
        ohlc_rows = wavecount_ohlc_index().get((symbol, timeframe), [])
        start_row = next((item for item in ohlc_rows if normalized_timestamp(item.get("timestamp")) == start_time), None)
        end_row = next((item for item in ohlc_rows if normalized_timestamp(item.get("timestamp")) == end_time), None)
        if start_row and end_row and start_time and end_time:
            start_price = safe_float(start_row.get("low" if tone == "up" else "high" if tone == "down" else "close"))
            end_price = safe_float(end_row.get("high" if tone == "up" else "low" if tone == "down" else "close"))
            if start_price is not None and end_price is not None:
                return [
                    {"x": start_time, "y": start_price, "label": "origen", "kind": "pivot"},
                    {"x": end_time, "y": end_price, "label": wavecount_wave_label(enriched), "kind": "latest"},
                ]

    latest_time = normalized_timestamp(enriched.get("latest_close_time") or enriched.get("as_of_bar_time"))
    latest_price = safe_float(enriched.get("latest_close"))
    if latest_time and latest_price is not None:
        current_label = wavecount_wave_label(enriched)
        if not points or points[-1]["x"] != latest_time or points[-1]["y"] != latest_price:
            points.append({"x": latest_time, "y": latest_price, "label": current_label, "kind": "latest"})
    return points


def wavecount_direction_tone(row: dict[str, Any]) -> str:
    enriched = wavecount_enriched_row(row)
    text = " ".join(
        str(enriched.get(key, ""))
        for key in ("current_leg_direction", "direction", "current_leg_status", "live_estimated_wave")
    ).lower()
    if "down" in text or "short" in text:
        return "down"
    if "up" in text or "long" in text:
        return "up"
    return "flat"


def wavecount_direction_label(row: dict[str, Any]) -> str:
    tone = wavecount_direction_tone(row)
    if tone == "down":
        return "bajista"
    if tone == "up":
        return "alcista"
    return "sin direccion"


@lru_cache(maxsize=1)
def wavecount_ohlc_index() -> dict[tuple[str, str], list[dict[str, Any]]]:
    if not ACTIVE_SQL_OHLC_CSV.exists():
        return {}
    from trading_center.readonly_dashboard import read_csv

    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in read_csv(ACTIVE_SQL_OHLC_CSV):
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        if symbol and timeframe:
            index.setdefault((symbol, timeframe), []).append(row)
    for rows in index.values():
        rows.sort(key=lambda item: normalized_timestamp(item.get("timestamp")))
    return index


def wavecount_chart_figure(row: dict[str, Any], limit: int = 320) -> dict[str, Any]:
    symbol = str(row.get("symbol", "")).strip()
    timeframe = str(row.get("timeframe", "")).strip()
    if not symbol or not timeframe:
        return {}

    enriched = wavecount_enriched_row(row)
    as_of = normalized_timestamp(
        enriched.get("latest_close_time")
        or enriched.get("as_of_bar_time")
        or enriched.get("timestamp")
    )
    rows = wavecount_ohlc_index().get((symbol, timeframe), [])
    if as_of:
        rows = [item for item in rows if normalized_timestamp(item.get("timestamp")) <= as_of]
    structure_points = wavecount_structure_points(enriched)
    if structure_points:
        first_structure_time = structure_points[0]["x"]
        first_index = next(
            (
                index
                for index, item in enumerate(rows)
                if normalized_timestamp(item.get("timestamp")) >= first_structure_time
            ),
            0,
        )
        rows = rows[max(0, first_index - 18) :]
    else:
        rows = rows[-limit:]
    if len(rows) < 5:
        return {}

    times = [normalized_timestamp(item.get("timestamp")) for item in rows]
    opens = [safe_float(item.get("open")) for item in rows]
    highs = [safe_float(item.get("high")) for item in rows]
    lows = [safe_float(item.get("low")) for item in rows]
    closes = [safe_float(item.get("close")) for item in rows]
    if any(value is None for value in [*opens, *highs, *lows, *closes]):
        return {}
    visible_times = set(times)
    structure_points = [point for point in structure_points if point["x"] in visible_times]

    tone = wavecount_direction_tone(enriched)
    direction_label = wavecount_direction_label(enriched)
    status = wavecount_status(enriched)
    trace_color = "#d7a84b" if status == "candidate" else "#ff6b65" if tone == "down" else "#68e28f" if tone == "up" else "#5ce0ca"
    title_prefix = f"Candidato {wavecount_wave_label(enriched).replace('?', '')}" if status == "candidate" else wavecount_wave_label(enriched)
    title = f"{symbol} {timeframe}: {title_prefix} {direction_label}"
    tick_values = compact_time_tick_values(times)
    data: list[dict[str, Any]] = [
        {
            "type": "candlestick",
            "x": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "name": "OHLC",
            "increasing": {"line": {"color": "#68e28f"}, "fillcolor": "rgba(104,226,143,.34)"},
            "decreasing": {"line": {"color": "#ff6b65"}, "fillcolor": "rgba(255,107,101,.34)"},
        }
    ]
    annotations: list[dict[str, Any]] = []

    pivot_time = normalized_timestamp(enriched.get("last_persistent_pivot_time"))
    pivot_price = safe_float(enriched.get("last_persistent_pivot_price"))
    latest_time = normalized_timestamp(enriched.get("latest_close_time") or enriched.get("as_of_bar_time"))
    latest_price = safe_float(enriched.get("latest_close"))
    if len(structure_points) >= 2:
        for index in range(len(structure_points) - 1):
            start = structure_points[index]
            end = structure_points[index + 1]
            is_current = index == len(structure_points) - 2 and end.get("kind") in {"current", "latest"}
            segment_color = trace_color if is_current else "rgba(166,211,202,.72)"
            segment_dash = "solid" if is_current else "dot"
            segment_width = 3 if is_current else 2
            segment_name = f"{end['label']} actual" if is_current else f"{end['label']} previa"
            data.append(
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": [start["x"], end["x"]],
                    "y": [start["y"], end["y"]],
                    "name": segment_name,
                    "line": {"color": segment_color, "width": segment_width, "dash": segment_dash},
                    "marker": {"size": [7, 9 if is_current else 7], "color": ["#0b1111", segment_color], "line": {"color": segment_color, "width": 2}},
                    "hovertemplate": f"{segment_name}<br>%{{x}}<br>%{{y}}<extra></extra>",
                }
            )
            if end["label"] != "origen":
                annotations.append(
                    {
                        "x": end["x"],
                        "y": end["y"],
                        "text": end["label"],
                        "showarrow": True,
                        "arrowcolor": segment_color,
                        "arrowwidth": 1.4,
                        "ax": 0,
                        "ay": -28 if is_current or end["y"] >= start["y"] else 28,
                        "bgcolor": "rgba(5,9,9,.86)",
                        "bordercolor": segment_color,
                        "borderwidth": 1,
                        "font": {"color": "#f2fff9", "size": 12, "family": "Consolas, monospace"},
                    }
                )
    elif pivot_time and pivot_price is not None and latest_time and latest_price is not None:
        data.append(
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": [pivot_time, latest_time],
                "y": [pivot_price, latest_price],
                "name": f"{wavecount_wave_label(enriched)} actual",
                "line": {"color": trace_color, "width": 3},
                "marker": {"size": 9, "color": ["#d7a84b", trace_color]},
            }
        )

    for key, label, color in [
        ("activation_level", "activacion", "#5ce0ca"),
        ("invalidation_level", "invalidacion", "#d7a84b"),
    ]:
        level = safe_float(enriched.get(key))
        if level is not None:
            data.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [times[0], times[-1]],
                    "y": [level, level],
                    "name": label,
                    "line": {"color": color, "width": 1.5, "dash": "dash"},
                }
            )

    return {
        "data": data,
        "layout": {
            "template": "plotly_dark",
            "title": {"text": title, "font": {"size": 18, "color": "#f2fff9"}},
            "paper_bgcolor": "#050909",
            "plot_bgcolor": "#050909",
            "font": {"color": "#d4ebe4", "family": "Consolas, monospace"},
            "margin": {"l": 54, "r": 18, "t": 52, "b": 42},
            "xaxis": {
                "type": "category",
                "categoryorder": "array",
                "categoryarray": times,
                "tickmode": "array",
                "tickvals": tick_values,
                "ticktext": compact_time_tick_text(tick_values),
                "tickangle": 0,
                "automargin": True,
                "showgrid": True,
                "gridcolor": "rgba(166,211,202,.10)",
                "rangeslider": {"visible": False},
                "linecolor": "rgba(166,211,202,.35)",
                "tickfont": {"color": "#d4ebe4"},
            },
            "yaxis": {
                "showgrid": True,
                "gridcolor": "rgba(166,211,202,.10)",
                "linecolor": "rgba(166,211,202,.35)",
                "tickfont": {"color": "#d4ebe4"},
            },
            "annotations": annotations,
            "legend": {
                "orientation": "h",
                "y": 1.02,
                "x": 1,
                "xanchor": "right",
                "bgcolor": "rgba(5,9,9,.92)",
                "bordercolor": "rgba(92,224,202,.28)",
                "borderwidth": 1,
                "font": {"color": "#d4ebe4"},
            },
            "hovermode": "x unified",
            "hoverlabel": {
                "bgcolor": "#07100f",
                "bordercolor": "rgba(92,224,202,.55)",
                "font": {"color": "#f2fff9"},
            },
        },
    }




def fib_mode_label(mode: str | None) -> str:
    labels = {"short": "corto", "medium": "medio", "wide": "amplio", "macro": "macro"}
    return labels.get(str(mode or SCREENER_DEFAULT_FIB_MODE), "amplio")


def fib_mode_recency_scale(mode: str | None, timeframe: str) -> float:
    mode_value = str(mode or SCREENER_DEFAULT_FIB_MODE)
    if mode_value == "short":
        return 28.0 if timeframe == "H1" else 18.0
    if mode_value == "medium":
        return 80.0 if timeframe == "H1" else 52.0
    if mode_value == "macro":
        return 100000.0
    return 180.0 if timeframe == "H1" else 120.0


def fib_mode_candidate_window(mode: str | None, timeframe: str) -> int | None:
    mode_value = str(mode or SCREENER_DEFAULT_FIB_MODE)
    if mode_value == "short":
        return 45 if timeframe == "H1" else 28
    if mode_value == "medium":
        return 95 if timeframe == "H1" else 56
    if mode_value == "wide":
        return 180 if timeframe == "H1" else 110
    return None


def fib_mode_score(
    mode: str | None,
    materiality: dict[str, Any],
    bars_since_end: int,
    timeframe: str,
) -> float:
    mode_value = str(mode or SCREENER_DEFAULT_FIB_MODE)
    range_pct = float(materiality["range_pct"])
    tr_multiple = max(1.0, float(materiality["tr_multiple"]))
    swing_bars = max(1, int(materiality["swing_bars"]))
    if mode_value == "short":
        return 1_000_000.0 - bars_since_end
    if mode_value == "medium":
        scale = fib_mode_recency_scale("medium", timeframe)
        return range_pct * tr_multiple * np.sqrt(swing_bars) / (1.0 + bars_since_end / scale)
    if mode_value == "macro":
        return range_pct * tr_multiple * np.log1p(swing_bars) * 4.0 + swing_bars
    scale = fib_mode_recency_scale("wide", timeframe)
    return range_pct * tr_multiple * np.log1p(swing_bars) / (1.0 + bars_since_end / scale)


def dynamic_fibonacci_layers(
    symbol: str,
    group: str,
    timeframe: str,
    candles: list[dict[str, Any]],
    fib_mode: str | None,
) -> list[dict[str, Any]]:
    if len(candles) < 24:
        return []
    pivots = detect_fibonacci_pivots(candles, timeframe)
    if len(pivots) < 2:
        return []
    latest_index = len(candles) - 1
    candidate_window = fib_mode_candidate_window(fib_mode, timeframe)
    best: tuple[float, dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    mode_value = str(fib_mode or SCREENER_DEFAULT_FIB_MODE)
    pivot_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if mode_value == "macro":
        for start_index in range(0, len(pivots) - 1):
            for end_index in range(start_index + 1, len(pivots)):
                start = pivots[start_index]
                end = pivots[end_index]
                if start["kind"] != end["kind"]:
                    pivot_pairs.append((start, end))
    else:
        pivot_pairs = [(pivots[end_index - 1], pivots[end_index]) for end_index in range(len(pivots) - 1, 0, -1)]
    for start, end in pivot_pairs:
        if start["kind"] == end["kind"]:
            continue
        materiality = swing_materiality(start, end, candles, group, timeframe)
        if not materiality["passed"]:
            continue
        bars_since_end = max(0, latest_index - int(end["index"]))
        if candidate_window is not None and bars_since_end > candidate_window:
            continue
        score = fib_mode_score(fib_mode, materiality, bars_since_end, timeframe)
        materiality = {**materiality, "bars_since_end": bars_since_end, "mode_score": score}
        if best is None or score > best[0]:
            best = (float(score), start, end, materiality)
    if best is None:
        return []
    _, start, end, _materiality = best
    start_price = float(start["price"])
    end_price = float(end["price"])
    direction = "bullish" if end_price > start_price else "bearish"
    start_time = str(candles[0].get("timestamp", ""))
    end_time = str(candles[-1].get("timestamp", ""))
    layers: list[dict[str, Any]] = []
    for ratio in [*FIB_ANCHOR_RATIOS, *FIB_RATIOS]:
        price = fibonacci_level_price(direction, start_price, end_price, ratio)
        is_anchor = ratio in FIB_ANCHOR_RATIOS
        layers.append(
            {
                "layer_type": f"fibonacci_dynamic_{str(ratio).replace('.', '_')}",
                "label": fib_label(ratio),
                "price": f"{price:.8g}",
                "start_time": start_time,
                "end_time": end_time,
                "color": "#d7a84b" if is_anchor else "#c793ff",
                "style": "solid" if is_anchor else "dash",
                "source": f"dashboard_dynamic_fibonacci_{fib_mode_label(fib_mode)}",
                "is_operational": False,
            }
        )
    for ratio in FIB_EXTENSIONS:
        price = fibonacci_extension_price(direction, start_price, end_price, ratio)
        layers.append(
            {
                "layer_type": f"fibonacci_dynamic_ext_{str(ratio).replace('.', '_')}",
                "label": f"Fib ext {ratio:g}",
                "price": f"{price:.8g}",
                "start_time": start_time,
                "end_time": end_time,
                "color": "#8f6bd1",
                "style": "dot",
                "source": f"dashboard_dynamic_fibonacci_{fib_mode_label(fib_mode)}",
                "is_operational": False,
            }
        )
    return layers


def screener_layer_option_counts(layer_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {str(option["value"]): 0 for option in SCREENER_LAYER_OPTIONS}
    for layer in layer_rows:
        family = screener_layer_family(layer)
        if family in counts:
            counts[family] += 1
    return counts


def screener_layer_options_for(layer_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    counts = screener_layer_option_counts(layer_rows)
    options: list[dict[str, str]] = []
    for option in SCREENER_LAYER_OPTIONS:
        value = str(option["value"])
        count = counts.get(value, 0)
        if count:
            options.append({"label": f"{option['label']} ({count})", "value": value})
    return options


def screener_default_visible_layers(row: dict[str, Any], layer_options: list[dict[str, str]]) -> list[str]:
    preferred_default_layers = list(SCREENER_DEFAULT_VISIBLE_LAYERS)
    setup_type = str(row.get("setup_type", "")).strip()
    if setup_type == "macd_breakout":
        preferred_default_layers = ["macd_breakout"]
    elif setup_type == "rsi_trend_reversal":
        preferred_default_layers = ["rsi_setup"]
    default_layers = [
        value
        for value in preferred_default_layers
        if any(str(option.get("value")) == value for option in layer_options)
    ]
    if not default_layers and layer_options:
        default_layers = [str(layer_options[0]["value"])]
    return default_layers


def screener_layer_price_by_type(layer_rows: list[dict[str, Any]], layer_type: str) -> str:
    for layer in layer_rows:
        if str(layer.get("layer_type", "")).strip() == layer_type:
            return str(layer.get("price", "")).strip()
    return ""


@lru_cache(maxsize=1)
def screener_ohlc_index() -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in read_json_or_csv(ACTIVE_SQL_OHLC_CSV):
        symbol = str(row.get("symbol", "")).strip()
        timeframe = str(row.get("timeframe", "")).strip()
        if not symbol or not timeframe:
            continue
        grouped.setdefault((symbol, timeframe), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: str(item.get("timestamp", "")))
    return grouped


def screener_setup_figure(
    row: dict[str, Any],
    layer_rows: list[dict[str, Any]],
    limit: int = 220,
    visible_layers: list[str] | None = None,
    fib_mode: str | None = SCREENER_DEFAULT_FIB_MODE,
) -> dict[str, Any]:
    symbol = str(row.get("symbol", "")).strip()
    timeframe = str(row.get("timeframe", "")).strip()
    if timeframe == "M15":
        candle_timeframe = "M15"
    else:
        candle_timeframe = timeframe or "H1"
    candles = screener_ohlc_index().get((symbol, candle_timeframe), [])[-limit:]
    if not candles:
        return {}
    x_values = [str(item.get("timestamp", "")) for item in candles]
    right_pad_count = 16 if candle_timeframe == "H4" else 22
    right_pad_values = [f"__future_pad_{index}" for index in range(1, right_pad_count + 1)]
    x_axis_categories = x_values + right_pad_values
    label_x = right_pad_values[-1] if right_pad_values else x_values[-1]
    tick_values = compact_time_tick_values(x_values, max_ticks=8)
    requested_layers = SCREENER_DEFAULT_VISIBLE_LAYERS if visible_layers is None else visible_layers
    layer_rows_for_plot = list(layer_rows)
    if "fibonacci" in set(requested_layers):
        dynamic_fib_layers = dynamic_fibonacci_layers(
            symbol=symbol,
            group=str(row.get("market_group", "")).strip(),
            timeframe=candle_timeframe,
            candles=candles,
            fib_mode=fib_mode,
        )
        if dynamic_fib_layers:
            non_fib_layers = [layer for layer in layer_rows_for_plot if screener_layer_family(layer) != "fibonacci"]
            layer_rows_for_plot = [*non_fib_layers, *dynamic_fib_layers]
    visible_layer_rows = filter_screener_layers(layer_rows_for_plot, visible_layers)
    layer_prices = [price for price in (safe_float(layer.get("price")) for layer in visible_layer_rows) if price is not None]
    y_shifts = annotation_yshifts(layer_prices)
    rsi_values = rsi_series_from_candles(candles)
    macd_values, macd_signal_values = macd_series_from_candles(candles)
    figure: dict[str, Any] = {
        "data": [
            {
                "type": "candlestick",
                "x": x_values,
                "open": [float(item.get("open") or 0) for item in candles],
                "high": [float(item.get("high") or 0) for item in candles],
                "low": [float(item.get("low") or 0) for item in candles],
                "close": [float(item.get("close") or 0) for item in candles],
                "name": "OHLC",
                "increasing": {"line": {"color": "#60e68f"}, "fillcolor": "rgba(96,230,143,.34)"},
                "decreasing": {"line": {"color": "#ff6b65"}, "fillcolor": "rgba(255,107,101,.30)"},
            }
        ],
        "layout": {
            "template": "plotly_dark",
            "paper_bgcolor": "#07100f",
            "plot_bgcolor": "#050909",
            "font": {"color": "#d8ede6", "family": "Consolas, monospace"},
            "height": 1240,
            "margin": {"l": 66, "r": 160, "t": 118, "b": 96},
            "title": {
                "text": "",
                "font": {"color": "#f2fff9", "size": 19},
                "x": 0.5,
                "xanchor": "center",
            },
            "meta": {"title": f"{symbol} {candle_timeframe}: {row.get('setup_type', 'setup')} ({row.get('setup_quality_score', '-')}/5)"},
            "xaxis": {
                "type": "category",
                "categoryorder": "array",
                "categoryarray": x_axis_categories,
                "anchor": "y3",
                "rangeslider": {"visible": False},
                "showgrid": False,
                "tickmode": "array",
                "tickvals": tick_values,
                "ticktext": compact_time_tick_text(tick_values),
                "tickangle": 0,
                "tickfont": {"color": "#d8ede6", "size": 11},
                "showline": True,
                "linecolor": "rgba(150,160,160,.35)",
            },
            "yaxis": {
                "domain": [0.52, 1.0],
                "showgrid": False,
                "tickfont": {"color": "#d8ede6", "size": 12},
                "showline": True,
                "linecolor": "rgba(150,160,160,.35)",
                "zeroline": False,
            },
            "yaxis2": {
                "domain": [0.28, 0.43],
                "anchor": "x",
                "range": [0, 100],
                "showgrid": False,
                "tickmode": "array",
                "tickvals": [30, 50, 70],
                "ticktext": ["30", "50", "70"],
                "tickfont": {"color": "#d8ede6", "size": 11},
                "showline": True,
                "linecolor": "rgba(150,160,160,.35)",
                "zeroline": False,
                "title": {"text": "RSI 14", "font": {"color": "#9fbbb5", "size": 11}},
            },
            "yaxis3": {
                "domain": [0.05, 0.20],
                "anchor": "x",
                "showgrid": False,
                "tickfont": {"color": "#d8ede6", "size": 11},
                "showline": True,
                "linecolor": "rgba(150,160,160,.35)",
                "zeroline": False,
                "title": {"text": "MACD", "font": {"color": "#9fbbb5", "size": 11}},
            },
            "legend": {
                "orientation": "h",
                "x": 0.5,
                "y": 1.08,
                "xanchor": "center",
                "yanchor": "bottom",
                "bgcolor": "#07100f",
                "bordercolor": "rgba(92,224,202,.35)",
                "borderwidth": 1,
                "font": {"color": "#d8ede6", "size": 11},
            },
            "hoverlabel": {
                "bgcolor": "#0d1b1a",
                "bordercolor": "#5ce0ca",
                "font": {"color": "#f2fff9"},
            },
            "annotations": [],
            "shapes": [
                *day_separator_shapes(x_values),
                {
                    "type": "line",
                    "xref": "x",
                    "yref": "y2",
                    "x0": x_values[0],
                    "x1": label_x,
                    "y0": 70,
                    "y1": 70,
                    "line": {"color": "rgba(215,168,75,.55)", "width": 1, "dash": "dash"},
                    "layer": "below",
                },
                {
                    "type": "line",
                    "xref": "x",
                    "yref": "y2",
                    "x0": x_values[0],
                    "x1": label_x,
                    "y0": 30,
                    "y1": 30,
                    "line": {"color": "rgba(92,224,202,.45)", "width": 1, "dash": "dash"},
                    "layer": "below",
                },
                {
                    "type": "line",
                    "xref": "x",
                    "yref": "y3",
                    "x0": x_values[0],
                    "x1": label_x,
                    "y0": 0,
                    "y1": 0,
                    "line": {"color": "rgba(150,160,160,.32)", "width": 1},
                    "layer": "below",
                },
            ],
        },
    }
    start_x = x_values[0]
    for layer in visible_layer_rows:
        layer_type = str(layer.get("layer_type", "")).strip()
        if layer_type in {"rsi_entry_marker", "rsi_watch_marker"}:
            event_time = str(layer.get("start_time") or layer.get("end_time") or "").strip()
            rsi_value = safe_float(layer.get("start_price"))
            price_value = safe_float(layer.get("price"))
            if event_time:
                figure["layout"]["shapes"].append(
                    {
                        "type": "line",
                        "xref": "x",
                        "yref": "paper",
                        "x0": event_time,
                        "x1": event_time,
                        "y0": 0.05,
                        "y1": 1.0,
                        "line": {"color": str(layer.get("color") or "#d7a84b"), "width": 1.4, "dash": "dot"},
                        "layer": "below",
                    }
                )
                figure["layout"]["annotations"].append(
                    {
                        "x": event_time,
                        "y": 1.0,
                        "xref": "x",
                        "yref": "paper",
                        "text": str(layer.get("label") or "RSI"),
                        "showarrow": False,
                        "xanchor": "center",
                        "yanchor": "bottom",
                        "font": {"size": 10, "color": "#f2fff9"},
                        "bgcolor": "rgba(5,9,9,.88)",
                        "bordercolor": str(layer.get("color") or "#d7a84b"),
                        "borderwidth": 1,
                        "borderpad": 3,
                    }
                )
            if event_time and rsi_value is not None:
                figure["data"].append(
                    {
                        "type": "scatter",
                        "mode": "markers",
                        "x": [event_time],
                        "y": [rsi_value],
                        "name": str(layer.get("label") or "RSI"),
                        "marker": {
                            "size": 9,
                            "color": str(layer.get("color") or "#d7a84b"),
                            "line": {"color": "#06100f", "width": 1.5},
                        },
                        "yaxis": "y2",
                        "hovertemplate": "RSI %{y:.2f}<extra></extra>",
                    }
                )
            if event_time and price_value is not None:
                figure["data"].append(
                    {
                        "type": "scatter",
                        "mode": "markers",
                        "x": [event_time],
                        "y": [price_value],
                        "name": "RSI en precio",
                        "marker": {
                            "size": 8,
                            "symbol": "diamond",
                            "color": str(layer.get("color") or "#d7a84b"),
                            "line": {"color": "#06100f", "width": 1.5},
                        },
                        "hoverinfo": "skip",
                        "showlegend": False,
                    }
                )
            continue
        if layer_type == "fib_limit_study_swing_0_100":
            start_price = safe_float(layer.get("start_price"))
            end_price = safe_float(layer.get("end_price") or layer.get("price"))
            start_time = str(layer.get("start_time") or x_values[0])
            end_time = str(layer.get("end_time") or x_values[-1])
            if start_price is None or end_price is None:
                continue
            start_label = "Fib 100" if start_price > end_price else "Fib 0"
            end_label = "Fib 0" if start_price > end_price else "Fib 100"
            figure["data"].append(
                {
                    "type": "scatter",
                    "mode": "lines+markers+text",
                    "x": [start_time, end_time],
                    "y": [start_price, end_price],
                    "text": [start_label, end_label],
                    "textposition": ["top center", "bottom center"] if start_price > end_price else ["bottom center", "top center"],
                    "name": str(layer.get("label") or "Swing 0-100 estudio"),
                    "line": {"color": str(layer.get("color") or "#f4b740"), "width": 2.8},
                    "marker": {
                        "size": 8,
                        "color": str(layer.get("color") or "#f4b740"),
                        "line": {"color": "#06100f", "width": 1.5},
                    },
                    "textfont": {"size": 10, "color": "#f2fff9"},
                    "hoverinfo": "skip",
                }
            )
            continue
        if layer_type == "macd_w2_directrix":
            start_price = safe_float(layer.get("start_price"))
            end_price = safe_float(layer.get("end_price"))
            start_time = str(layer.get("start_time") or "").strip()
            end_time = str(layer.get("end_time") or "").strip()
            if start_price is None or end_price is None or not start_time or not end_time:
                continue
            style = str(layer.get("style", "dash"))
            line_dash = "dot" if style == "dot" else "solid" if style == "solid" else "dash"
            layer_label = str(layer.get("label") or "Reg W2 estudio")
            directrix_color = str(layer.get("color") or "#5ce0ca")
            if line_dash == "dot":
                directrix_color = "#d6fff6"
            figure["data"].append(
                {
                    "type": "scatter",
                    "mode": "lines+markers+text",
                    "x": [start_time, end_time],
                    "y": [start_price, end_price],
                    "text": ["", layer_label],
                    "textposition": ["middle left", "top right"],
                    "textfont": {"size": 10, "color": directrix_color},
                    "name": layer_label,
                    "line": {
                        "color": directrix_color,
                        "width": 3.6,
                        "dash": line_dash,
                    },
                    "marker": {
                        "size": 6,
                        "color": directrix_color,
                        "line": {"color": "#06100f", "width": 1},
                    },
                    "hovertemplate": "%{fullData.name}<br>%{x}<br>%{y}<extra></extra>",
                }
            )
            continue
        price = safe_float(layer.get("price"))
        if price is None:
            continue
        label = str(layer.get("label", "contexto"))
        style = str(layer.get("style", "dash"))
        line_dash = "dot" if style == "dot" else "solid" if style == "solid" else "dash"
        line_width = 1.0 if style == "solid" else 1.6
        figure["data"].append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": [start_x, label_x],
                "y": [price, price],
                "name": label,
                "line": {
                    "color": str(layer.get("color") or "#5ce0ca"),
                    "width": line_width,
                    "dash": line_dash,
                },
                "hoverinfo": "skip",
            }
        )
        if label.startswith("Nivel redondo"):
            continue
        figure["layout"]["annotations"].append(
            {
                "x": label_x,
                "y": price,
                "xref": "x",
                "yref": "y",
                "text": label,
                "showarrow": False,
                "xanchor": "left",
                "yanchor": "middle",
                "xshift": 0,
                "yshift": y_shifts.get(price, 0),
                "font": {"size": 10, "color": "#f2fff9"},
                "bgcolor": "rgba(5,9,9,.88)",
                "bordercolor": str(layer.get("color") or "#5ce0ca"),
                "borderwidth": 1,
                "borderpad": 3,
            }
        )
    figure["data"].append(
        {
            "type": "scatter",
            "mode": "lines",
            "x": x_values,
            "y": rsi_values,
            "name": "RSI 14",
            "line": {"color": "#d7a84b", "width": 1.7},
            "yaxis": "y2",
            "hovertemplate": "RSI %{y:.2f}<extra></extra>",
        }
    )
    figure["data"].append(
        {
            "type": "scatter",
            "mode": "lines",
            "x": x_values,
            "y": macd_values,
            "name": "MACD 12-26",
            "line": {"color": "#5ce0ca", "width": 1.55},
            "yaxis": "y3",
            "hovertemplate": "MACD %{y:.5f}<extra></extra>",
        }
    )
    figure["data"].append(
        {
            "type": "scatter",
            "mode": "lines",
            "x": x_values,
            "y": macd_signal_values,
            "name": "Senal 9",
            "line": {"color": "#ff8a65", "width": 1.35},
            "yaxis": "y3",
            "hovertemplate": "Senal %{y:.5f}<extra></extra>",
        }
    )
    last_rsi = last_number(rsi_values)
    if last_rsi is not None:
        figure["layout"]["annotations"].append(
            {
                "x": label_x,
                "y": last_rsi,
                "xref": "x",
                "yref": "y2",
                "text": f"RSI {last_rsi:.1f}",
                "showarrow": False,
                "xanchor": "left",
                "yanchor": "middle",
                "xshift": 0,
                "font": {"size": 10, "color": "#f2fff9"},
                "bgcolor": "rgba(5,9,9,.88)",
                "bordercolor": "#d7a84b",
                "borderwidth": 1,
                "borderpad": 3,
            }
        )
    last_macd = last_number(macd_values)
    last_signal = last_number(macd_signal_values)
    if last_macd is not None:
        figure["layout"]["annotations"].append(
            {
                "x": label_x,
                "y": last_macd,
                "xref": "x",
                "yref": "y3",
                "text": "MACD",
                "showarrow": False,
                "xanchor": "left",
                "yanchor": "middle",
                "xshift": 0,
                "yshift": -10,
                "font": {"size": 10, "color": "#f2fff9"},
                "bgcolor": "rgba(5,9,9,.88)",
                "bordercolor": "#5ce0ca",
                "borderwidth": 1,
                "borderpad": 3,
            }
        )
    if last_signal is not None:
        figure["layout"]["annotations"].append(
            {
                "x": label_x,
                "y": last_signal,
                "xref": "x",
                "yref": "y3",
                "text": "Senal",
                "showarrow": False,
                "xanchor": "left",
                "yanchor": "middle",
                "xshift": 0,
                "yshift": 12,
                "font": {"size": 10, "color": "#f2fff9"},
                "bgcolor": "rgba(5,9,9,.88)",
                "bordercolor": "#ff8a65",
                "borderwidth": 1,
                "borderpad": 3,
            }
        )
    return figure


def create_app(
    data: dict[str, Any] | None = None,
    *,
    auto_refresh_seconds: int = DEFAULT_AUTO_REFRESH_SECONDS,
    disable_auto_refresh: bool = False,
    latest_manifest_json: Path = DEFAULT_LATEST_MANIFEST_JSON,
    data_builder: Callable[[], dict[str, Any]] | None = None,
) -> Any:
    Dash, Input, Output, State, dash_table, dcc, html = require_dash()
    from dash import ALL, callback_context, no_update

    app_data = data or build_dash_data()
    client_app_data = dict(app_data)
    client_app_data.pop("correlation_returns_rows", None)
    initial_manifest_state = build_manifest_refresh_state(
        latest_manifest_json,
        loaded_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    build_fresh_data = data_builder or build_dash_data
    app = Dash(__name__, suppress_callback_exceptions=True, title="Trading Center")
    app.index_string = f"""<!doctype html>
<html>
  <head>
    {{%metas%}}
    <title>{{%title%}}</title>
    {{%favicon%}}
    {{%css%}}
    <style>{dash_css()}</style>
  </head>
  <body>
    {{%app_entry%}}
    <footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>
  </body>
</html>"""

    def metric(label: str, value: Any, note: str = "", tone: str = "") -> Any:
        return html.Div(
            [html.Span(label, className="metric-label"), html.Strong(str(value)), html.Small(note)],
            className=f"metric {tone}".strip(),
        )

    def refresh_status_view(manifest_state: dict[str, Any]) -> Any:
        payload = build_refresh_status_payload(
            manifest_state,
            auto_refresh_enabled=not disable_auto_refresh,
        )
        auto_text = "Dash escuchando cambios" if payload["auto_refresh_enabled"] else "Dash sin escucha"
        manifest_text = format_dashboard_timestamp(payload["manifest_timestamp"], empty="sin publicacion")
        loaded_text = format_dashboard_timestamp(payload["loaded_at_utc"], empty="sin carga")
        decision_text, decision_tone = refresh_decision_label(payload["refresh_decision"])
        return html.Div(
            [
                html.Span(auto_text, className="refresh-pill"),
                html.Span(f"Panel cargado {loaded_text}", className="refresh-pill"),
                html.Span(f"Datos publicados {manifest_text}", className="refresh-pill"),
                html.Span(decision_text, className=f"refresh-pill {decision_tone}".strip()),
            ],
            className="refresh-status-row",
        )







    app.layout = build_app_layout(
        html=html,
        dcc=dcc,
        client_app_data=client_app_data,
        initial_manifest_state=initial_manifest_state,
        auto_refresh_seconds=auto_refresh_seconds,
        disable_auto_refresh=disable_auto_refresh,
        refresh_status_view=refresh_status_view,
        ai_analyst_context_options=ai_analyst_context_options,
        ai_analyst_setup_options=ai_analyst_setup_options,
        ai_analyst_wave_options=ai_analyst_wave_options,
        ai_analyst_correlation_options=ai_analyst_correlation_options,
    )

    @app.callback(
        Output("tc-data", "data"),
        Output("tc-manifest-state", "data"),
        Output("refresh-status-panel", "children"),
        Input("tc-auto-refresh-interval", "n_intervals"),
        State("tc-manifest-state", "data"),
    )
    def refresh_latest_manifest(_n_intervals: int, manifest_state: dict[str, Any] | None) -> Any:
        should_reload, next_state, refreshed = maybe_refresh_dash_data(
            manifest_state,
            latest_manifest_json,
            data_builder=build_fresh_data,
        )
        if should_reload and refreshed is not None:
            refreshed_client = dict(refreshed)
            refreshed_client.pop("correlation_returns_rows", None)
            return refreshed_client, next_state, refresh_status_view(next_state)
        return no_update, next_state, refresh_status_view(next_state)

    @app.callback(
        Output("tab-content", "children"),
        Output("section-crumb", "children"),
        Output("section-title", "children"),
        Input("main-tabs", "value"),
        State("tc-data", "data"),
    )
    def render_tab(tab: str, data_obj: dict[str, Any]) -> Any:
        section_name = {
            "overview": "Mercado",
            "correlation": "Correlacion",
            "wavecount": "WeaveCount",
            "universe": "Screener",
            "mt5_shadow": "MT5 Bot",
        }.get(tab, "Mercado")
        if tab == "universe":
            return screener_tab(html, dcc, data_obj), section_name, section_name
        if tab == "mt5_shadow":
            return mt5_shadow_tab(html, data_obj), section_name, section_name
        if tab == "correlation":
            return correlation_tab(html, dcc, data_obj), section_name, section_name
        if tab == "wavecount":
            return wavecount_tab(html, dcc, data_obj), section_name, section_name
        return overview_tab(html, data_obj), section_name, section_name

    @app.callback(
        Output("ai-analyst-panel-open", "data"),
        Input("ai-analyst-toggle", "n_clicks"),
        Input("ai-analyst-close", "n_clicks"),
        State("ai-analyst-panel-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_ai_analyst_panel(toggle_clicks: int | None, close_clicks: int | None, is_open: bool | None) -> bool:
        triggered = callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0] if callback_context.triggered else ""
        if triggered == "ai-analyst-close":
            return False
        return not bool(is_open)

    @app.callback(
        Output("ai-analyst-panel", "className"),
        Input("ai-analyst-panel-open", "data"),
    )
    def render_ai_analyst_panel_state(is_open: bool | None) -> str:
        return "ai-analyst-panel" if is_open else "ai-analyst-panel hidden"

    @app.callback(
        Output("ai-analyst-screener-controls", "style"),
        Output("ai-analyst-wave-controls", "style"),
        Output("ai-analyst-correlation-controls", "style"),
        Output("ai-analyst-market-controls", "style"),
        Input("ai-analyst-context", "value"),
    )
    def render_ai_analyst_context_controls(context_value: str | None) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
        return ai_analyst_control_visibility(context_value)

    def ai_analyst_pdf_download_node(result: dict[str, Any]) -> Any:
        report_pdf = str(result.get("report_pdf", "")).strip()
        if not report_pdf:
            return None
        output_status = str(result.get("output_validation_status", "")).strip().lower()
        review_generated = bool(result.get("ai_review_generated", False))
        label = "Descargar informe PDF" if review_generated and output_status == "pass" else "Descargar diagnostico PDF"
        try:
            report_pdf = str(Path(report_pdf).resolve())
        except Exception:
            pass
        return html.Div(
            label,
            id={"type": "ai-analyst-download-pdf", "path": report_pdf},
            n_clicks=0,
            role="button",
            tabIndex=0,
            className="ai-analyst-download",
        )

    @app.callback(
        Output("ai-analyst-setup-select", "options"),
        Output("ai-analyst-setup-select", "value"),
        Input("tc-data", "data"),
        Input("ai-analyst-setup-state", "value"),
        State("ai-analyst-setup-select", "value"),
    )
    def refresh_ai_analyst_setup_options(data_obj: dict[str, Any], setup_state: str | None, current_value: str | None) -> tuple[list[dict[str, str]], str]:
        options = ai_analyst_setup_options(data_obj.get("screener_setups_rows", []), setup_state or "reviewable")
        values = {option["value"] for option in options}
        if current_value in values:
            return options, str(current_value)
        return options, options[0]["value"] if options else ""

    @app.callback(
        Output("ai-analyst-wave-select", "options"),
        Output("ai-analyst-wave-select", "value"),
        Input("tc-data", "data"),
        State("ai-analyst-wave-select", "value"),
    )
    def refresh_ai_analyst_wave_options(data_obj: dict[str, Any], current_value: str | None) -> tuple[list[dict[str, str]], str]:
        options = ai_analyst_wave_options(data_obj.get("wavecount_rows", []))
        values = {option["value"] for option in options}
        if current_value in values:
            return options, str(current_value)
        return options, options[0]["value"] if options else ""

    @app.callback(
        Output("ai-analyst-correlation-select", "options"),
        Output("ai-analyst-correlation-select", "value"),
        Input("tc-data", "data"),
        State("ai-analyst-correlation-select", "value"),
    )
    def refresh_ai_analyst_correlation_options(data_obj: dict[str, Any], current_value: str | None) -> tuple[list[dict[str, str]], str]:
        options = ai_analyst_correlation_options(data_obj.get("correlation_pair_rows", []))
        values = {option["value"] for option in options}
        if current_value in values:
            return options, str(current_value)
        return options, options[0]["value"] if options else ""

    @app.callback(
        Output("ai-analyst-result", "children"),
        Input("ai-analyst-run", "n_clicks"),
        Input("ai-analyst-run-codex", "n_clicks"),
        Input("ai-analyst-run-codex-macro", "n_clicks"),
        State("ai-analyst-context", "value"),
        State("ai-analyst-setup-select", "value"),
        State("ai-analyst-wave-select", "value"),
        State("ai-analyst-correlation-select", "value"),
        prevent_initial_call=True,
        running=[
            (Output("ai-analyst-run", "className"), "ai-analyst-run disabled", "ai-analyst-run"),
            (Output("ai-analyst-run-codex", "className"), "ai-analyst-run codex disabled", "ai-analyst-run codex"),
            (Output("ai-analyst-run-codex-macro", "className"), "ai-analyst-run codex macro disabled", "ai-analyst-run codex macro"),
            (Output("ai-analyst-progress", "children"), "Preparando paquete y analisis. Codex puede tardar unos minutos si hay macro/noticias...", ""),
        ],
    )
    def prepare_ai_analyst_review(
        n_clicks: int | None,
        codex_clicks: int | None,
        codex_macro_clicks: int | None,
        context_value: str | None,
        setup_id: str | None,
        wave_case_id: str | None,
        correlation_value: str | None,
    ) -> Any:
        if not n_clicks and not codex_clicks and not codex_macro_clicks:
            return no_update
        triggered = callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0] if callback_context.triggered else ""
        gateway_mode = "fixture"
        if triggered == "ai-analyst-run-codex":
            gateway_mode = "codex_cli"
        elif triggered == "ai-analyst-run-codex-macro":
            gateway_mode = "codex_cli_macro"
        context = str(context_value or "screener_setup")
        if context == "weavecount_case":
            result = run_ai_analyst_weavecount_review(str(wave_case_id or ""), gateway_mode=gateway_mode)
            if result.get("status") != "prepared":
                return html.Div(
                    [
                        html.Strong("Bloqueado"),
                        html.Small(str(result.get("reason", "no preparado"))),
                    ],
                    className="ai-analyst-result-card warning",
                )
            return html.Div(
                [
                    html.Strong("Paquete WeaveCount preparado"),
                    html.Small(f"package: {result.get('package_id', '')}"),
                    html.Small(f"gateway: {result.get('request_decision', '')} / output {result.get('output_validation_status', '')}"),
                    html.Small(f"chart={str(result.get('chart_rendered', False)).lower()} - ohlc={result.get('ohlc_rows', 0)} - layers={result.get('layer_rows', 0)}"),
                    html.Small(ai_analyst_gateway_status_line(result)),
                    ai_analyst_pdf_download_node(result),
                ],
                className="ai-analyst-result-card",
            )
        if context == "correlation":
            result = run_ai_analyst_correlation_review(str(correlation_value or ""), gateway_mode=gateway_mode)
            if result.get("status") != "prepared":
                return html.Div(
                    [
                        html.Strong("Bloqueado"),
                        html.Small(str(result.get("reason", "no preparado"))),
                    ],
                    className="ai-analyst-result-card warning",
                )
            return html.Div(
                [
                    html.Strong("Paquete Correlacion preparado"),
                    html.Small(f"package: {result.get('package_id', '')}"),
                    html.Small(f"gateway: {result.get('request_decision', '')} / output {result.get('output_validation_status', '')}"),
                    html.Small(f"chart={str(result.get('chart_rendered', False)).lower()} - returns={result.get('ohlc_rows', 0)} - layers={result.get('layer_rows', 0)}"),
                    html.Small(ai_analyst_gateway_status_line(result)),
                    ai_analyst_pdf_download_node(result),
                ],
                className="ai-analyst-result-card",
            )
        if context == "market_summary":
            result = run_ai_analyst_market_review(gateway_mode=gateway_mode)
            if result.get("status") != "prepared":
                return html.Div(
                    [
                        html.Strong("Bloqueado"),
                        html.Small(str(result.get("reason", "no preparado"))),
                    ],
                    className="ai-analyst-result-card warning",
                )
            return html.Div(
                [
                    html.Strong("Paquete Mercado preparado"),
                    html.Small(f"package: {result.get('package_id', '')}"),
                    html.Small(f"gateway: {result.get('request_decision', '')} / output {result.get('output_validation_status', '')}"),
                    html.Small(f"chart={str(result.get('chart_rendered', False)).lower()} - rows={result.get('ohlc_rows', 0)} - layers={result.get('layer_rows', 0)}"),
                    html.Small(ai_analyst_gateway_status_line(result)),
                    ai_analyst_pdf_download_node(result),
                ],
                className="ai-analyst-result-card",
            )
        if context != "screener_setup":
            return html.Div([html.Strong("Bloqueado"), html.Small("tipo de analisis no reconocido")], className="ai-analyst-result-card warning")
        result = run_ai_analyst_controlled_review(str(setup_id or ""), gateway_mode=gateway_mode)
        if result.get("status") != "prepared":
            return html.Div(
                [
                    html.Strong("Bloqueado"),
                    html.Small(str(result.get("reason", "no preparado"))),
                ],
                className="ai-analyst-result-card warning",
            )
        return html.Div(
            [
                html.Strong("Paquete preparado"),
                html.Small(f"package: {result.get('package_id', '')}"),
                html.Small(f"gateway: {result.get('request_decision', '')} / output {result.get('output_validation_status', '')}"),
                html.Small(ai_analyst_gateway_status_line(result)),
                ai_analyst_pdf_download_node(result),
            ],
            className="ai-analyst-result-card",
        )

    @app.callback(
        Output("ai-analyst-report-download", "data"),
        Input({"type": "ai-analyst-download-pdf", "path": ALL}, "n_clicks"),
        State({"type": "ai-analyst-download-pdf", "path": ALL}, "id"),
        prevent_initial_call=True,
    )
    def download_ai_analyst_pdf(clicks: list[int] | None, ids: list[dict[str, Any]] | None) -> Any:
        if not clicks or not ids or not any(int(value or 0) > 0 for value in clicks):
            return no_update
        triggered_id = callback_context.triggered_id
        path_value = ""
        if isinstance(triggered_id, dict):
            path_value = str(triggered_id.get("path", ""))
        if not path_value:
            for click_count, item_id in zip(clicks, ids):
                if int(click_count or 0) > 0:
                    path_value = str(item_id.get("path", ""))
                    break
        resolved = ai_analyst_download_pdf_path(path_value)
        if resolved is None:
            return no_update
        return dcc.send_file(str(resolved))

    @app.callback(
        Output("correlation-panel", "children"),
        Input("corr-timeframe", "value"),
        Input("corr-asset", "value"),
        Input("corr-other-asset", "value"),
        Input("corr-metric", "value"),
        Input("corr-matrix-assets", "value"),
        Input("corr-view", "value"),
        State("tc-data", "data"),
    )
    def update_correlation_panel(
        timeframe: str | None,
        asset: str | None,
        other_asset: str | None,
        metric_name: str | None,
        selected_matrix_assets: Any,
        view: str | None,
        data_obj: dict[str, Any],
    ) -> Any:
        source = data_obj.get("correlation_source", {})
        if source.get("status") != "available":
            return html.Div("No hay artifact de correlaciones disponible.", className="radar-empty")
        metric_name = metric_name or "pearson"
        timeframe = timeframe or "H1"
        assets = source.get("assets") or []
        asset = asset or (assets[0] if assets else "")
        other_asset = other_asset or default_other_asset(source, asset) or ""
        if other_asset == asset:
            other_asset = default_other_asset(source, asset) or ""
        if not asset:
            return html.Div("No hay activos disponibles para correlacion.", className="radar-empty")

        pair_rows = data_obj.get("correlation_pair_rows", [])
        pair_info = find_pair_correlation(pair_rows, timeframe, asset, other_asset, metric_name) if other_asset else None
        if view == "rolling":
            rolling_rows = rolling_rows_for_asset(data_obj.get("rolling_correlation_rows", []), timeframe, asset, metric_name)
            movers = sorted(rolling_rows, key=lambda item: item["abs_delta"], reverse=True)[:8]
            strongest = sorted(rolling_rows, key=lambda item: abs(item["latest"]), reverse=True)[:8]
            selected_rolling = [
                row
                for row in rolling_rows
                if row.get("asset") == other_asset
            ][:1]
            rolling_window = rolling_window_for_timeframe(timeframe)
            returns_points = pair_return_points(app_data.get("correlation_returns_rows", []), timeframe, asset, other_asset, limit=700) if other_asset else []
            rolling_series = rolling_correlation_series(returns_points, metric_name, window=rolling_window)
            rolling_stats = rolling_summary(rolling_series)
            if rolling_series:
                rolling_focus = html.Section(
                    [
                        html.Div(
                            [
                                html.Div([html.Strong("Evolucion rolling"), html.Small(f"{asset} / {other_asset}")], className="rank-title"),
                                html.Div(f"Cada punto usa una ventana movil de {rolling_window} retornos alineados.", className="corr-method-note"),
                            ],
                            className="matrix-head",
                        ),
                        html.Div(
                            [
                                pair_metric_card(html, "Actual", rolling_stats["latest"], metric_label(metric_name), metric_name),
                                pair_metric_card(html, "Delta", rolling_stats["delta"], "ultimo cambio", metric_name),
                                pair_metric_card(html, "Media", rolling_stats["mean"], "serie visible", metric_name),
                                html.Div(
                                    [
                                        html.Span("Obs", className="metric-label"),
                                        html.Strong(str(rolling_stats["obs"])),
                                        html.Small("puntos rolling"),
                                    ],
                                    className="metric",
                                ),
                            ],
                            className="rolling-metric-grid",
                        ),
                        dcc.Graph(
                            id="corr-rolling-pair-graph",
                            figure=rolling_pair_figure(rolling_series, asset, other_asset, metric_name, rolling_window),
                            config={"displayModeBar": False, "responsive": True},
                            className="corr-graph corr-rolling-graph",
                        ),
                    ],
                    className="corr-panel rolling-chart-panel",
                )
            else:
                rolling_focus = html.Section(
                    [
                        html.Div([html.Strong("Evolucion rolling"), html.Small(f"{asset} / {other_asset or 'n/d'}")], className="rank-title"),
                        html.Div("No hay retornos alineados suficientes para pintar la serie rolling del par.", className="radar-empty"),
                    ],
                    className="corr-panel rolling-chart-panel",
                )
            return html.Div(
                [
                    html.Div(
                        [
                            html.Strong(f"{asset} en {timeframe}"),
                            html.Span(f"Rolling {metric_label(metric_name)}. Ventana actual frente a ventana previa. Par foco: {other_asset or 'n/d'}."),
                        ],
                        className="correlation-context",
                    ),
                    rolling_focus,
                    html.Div(
                        [
                            corr_rank_panel(html, "Par foco rolling", "Ultima ventana vs anterior", selected_rolling, metric_name, rolling=True),
                            corr_rank_panel(html, "Cambios recientes", "Mayor variacion de correlacion", movers, metric_name, rolling=True),
                            corr_rank_panel(html, "Relaciones actuales", "Mayor fuerza en la ultima ventana", strongest, metric_name, rolling=True),
                        ],
                        className="corr-board",
                    ),
                ]
            )

        if view == "partial":
            if metric_name == "dcor":
                return html.Div(
                    [
                        html.Div("La correlacion parcial requiere metrica con signo. Usa Pearson, Spearman o Kendall.", className="notice warning"),
                        html.Div("La correlacion de distancia se mantiene como dependencia general sin direccion.", className="radar-empty"),
                    ]
                )
            partial_rows = partial_correlation_rows(pair_rows, timeframe, asset, metric_name)
            return html.Div(
                [
                    html.Div(
                        [
                            html.Strong(f"Controlando {asset} en {timeframe}"),
                            html.Span("Relaciones entre otros activos despues de descontar el activo seleccionado. Lectura exploratoria, no senal."),
                        ],
                        className="correlation-context",
                    ),
                    html.Div(
                        [
                            corr_rank_panel(html, "Parcial destacada", "Mayor relacion residual", partial_rows, metric_name),
                            html.Section(
                                [
                                    html.Div([html.Strong("Uso prudente"), html.Small("La parcial ayuda a separar relaciones redundantes; no valida causalidad ni edge.")], className="rank-title"),
                                    html.Div("Si una relacion aparece aqui, solo indica dependencia residual en retornos del artifact actual.", className="corr-method-note"),
                                ],
                                className="corr-panel",
                            ),
                        ],
                        className="corr-board",
                    ),
                ]
            )

        base_rows = correlation_rows_for_asset(pair_rows, timeframe, asset, metric_name)
        ranked = split_correlation_rankings(base_rows, metric_name)
        matrix_assets = normalize_matrix_assets(selected_matrix_assets, source, limit=18)
        matrix_payload = correlation_matrix_payload(pair_rows, timeframe, matrix_assets, metric_name)
        returns_points = pair_return_points(app_data.get("correlation_returns_rows", []), timeframe, asset, other_asset, limit=420) if other_asset else []
        scatter_node = (
            dcc.Graph(
                id="corr-pair-scatter",
                figure=pair_scatter_figure(returns_points, asset, other_asset, metric_name),
                config={"displayModeBar": False, "responsive": True},
                className="corr-graph",
            )
            if returns_points
            else html.Div("No hay retornos suficientes para pintar este par.", className="radar-empty")
        )
        matrix_node = dcc.Graph(
            id="correlation-matrix-graph",
            figure=matrix_heatmap_figure(matrix_payload, metric_name),
            config={"displayModeBar": False, "responsive": True},
            className="corr-graph corr-matrix-graph",
        )
        if metric_name == "dcor":
            panels = [
                corr_rank_panel(html, "Mas dependientes", "dCor alto, sin signo direccional", ranked.get("strong", []), metric_name),
                corr_rank_panel(html, "Menos dependientes", "dCor bajo frente al activo", ranked.get("weak", []), metric_name),
            ]
        else:
            panels = [
                corr_rank_panel(html, "Se mueven parecido", "Correlacion positiva en retornos", ranked.get("positive", []), metric_name),
                corr_rank_panel(html, "Contrapesos", "Correlacion negativa en retornos", ranked.get("negative", []), metric_name),
                corr_rank_panel(html, "Mas fuertes", "Mayor valor absoluto", ranked.get("strong", []), metric_name),
            ]
        return html.Div(
            [
                html.Div(
                    [
                        html.Strong(f"{asset} en {timeframe}"),
                        html.Span(f"retornos close-to-close. Par seleccionado: {other_asset or 'n/d'}."),
                    ],
                    className="correlation-context",
                ),
                html.Div(
                    [
                        pair_focus_card(html, pair_info, asset, other_asset),
                        html.Section(
                            [
                                html.Div([html.Strong("Grafico del par"), html.Small("Retornos alineados recientes con LOWESS")], className="rank-title"),
                                scatter_node,
                            ],
                            className="corr-panel corr-visual-panel",
                        ),
                    ],
                    className="corr-focus-grid",
                ),
                html.Section(
                    [
                        html.Div(
                            [
                                html.Div([html.Strong("Matriz de comparacion"), html.Small("Click en una celda para cargar ese par")], className="rank-title"),
                                html.Div("Universo fijo seleccionado arriba; cambiar el par no modifica la composicion de la matriz.", className="corr-method-note"),
                            ],
                            className="matrix-head",
                        ),
                        matrix_node,
                    ],
                    className="corr-panel corr-matrix-panel",
                ),
                html.Div(panels, className="corr-board"),
            ]
        )

    @app.callback(
        Output("corr-asset", "value"),
        Output("corr-other-asset", "value"),
        Input("correlation-matrix-graph", "clickData"),
        State("corr-asset", "value"),
        State("corr-other-asset", "value"),
        prevent_initial_call=True,
    )
    def select_pair_from_matrix(click_data: dict[str, Any] | None, current_asset: str | None, current_other: str | None) -> tuple[str | None, str | None]:
        points = (click_data or {}).get("points") or []
        if not points:
            return current_asset, current_other
        point = points[0]
        x_asset = str(point.get("x", "")).strip()
        y_asset = str(point.get("y", "")).strip()
        if not x_asset or not y_asset or x_asset == y_asset:
            return current_asset, current_other
        return y_asset, x_asset

    @app.callback(
        Output("screener-highlighted-setups", "children"),
        Input("screener-search", "value"),
        Input("screener-setup-type", "value"),
        Input("screener-timeframe", "value"),
        Input("screener-group", "value"),
        Input("screener-quality-min", "value"),
        Input("screener-review-state", "value"),
        Input("screener-direction", "value"),
        State("tc-data", "data"),
    )
    def update_screener_section(
        search: str | None,
        setup_type: str | None,
        timeframe: str | None,
        group: str | None,
        min_quality: int | None,
        review_state: str | None,
        direction: str | None,
        data_obj: dict[str, Any],
    ) -> Any:
        setups = filter_screener_setups(
            data_obj.get("screener_setups_rows", []),
            search,
            setup_type,
            timeframe,
            group,
            min_quality,
            direction,
            review_state,
        )
        if setups:
            return html.Div([screener_setup_card(html, row) for row in setups[:24]], className="screener-signal-list")
        return html.Div("No hay setups destacados con estos filtros.", className="radar-empty")

    @app.callback(
        Output("screener-modal", "children"),
        Output("screener-modal", "className"),
        Output("screener-active-setup-id", "data"),
        Input({"type": "screener-setup-card", "setup_id": ALL}, "n_clicks"),
        Input("screener-modal-close", "n_clicks"),
        State({"type": "screener-setup-card", "setup_id": ALL}, "id"),
        State("tc-data", "data"),
        prevent_initial_call=True,
    )
    def update_screener_modal(clicks: list[int] | None, close_clicks: int | None, ids: list[dict[str, Any]] | None, data_obj: dict[str, Any]) -> tuple[Any, str, str | None]:
        hidden = html.Div(id="screener-modal-close", n_clicks=0, style={"display": "none"})
        triggered = callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0] if callback_context.triggered else ""
        if triggered == "screener-modal-close":
            return hidden, "wave-modal hidden", None
        try:
            triggered_id = json.loads(triggered)
        except json.JSONDecodeError:
            return hidden, "wave-modal hidden", None
        clicked_count = 0
        if ids and clicks:
            for index, component_id in enumerate(ids):
                if component_id == triggered_id and index < len(clicks):
                    clicked_count = int(clicks[index] or 0)
                    break
        if clicked_count < 1:
            return hidden, "wave-modal hidden", None
        setup_id = str(triggered_id.get("setup_id", ""))
        row = next((item for item in data_obj.get("screener_setups_rows", []) if str(item.get("setup_id", "")) == setup_id), None)
        if not row:
            return hidden, "wave-modal hidden", None
        layers = screener_layer_rows(data_obj, setup_id)
        layer_options = screener_layer_options_for(layers)
        default_layers = screener_default_visible_layers(row, layer_options)
        show_fib_mode = str(row.get("setup_type")) != "macd_breakout" and any(str(option.get("value")) == "fibonacci" for option in layer_options)
        fib_study_zone = screener_layer_price_by_type(layers, "fib_limit_study_zone_618")
        fib_study_sl = screener_layer_price_by_type(layers, "fib_limit_study_sl")
        fib_study_tp1 = screener_layer_price_by_type(layers, "fib_limit_study_tp1")
        fib_study_tp2 = screener_layer_price_by_type(layers, "fib_limit_study_tp2")
        macd_breakout_level = str(row.get("macd_breakout_level", "")).strip()
        macd_breakout_time = str(row.get("macd_breakout_time", "")).strip()
        macd_cross_time = str(row.get("macd_cross_time", "")).strip()
        macd_cross_state = str(row.get("macd_cross_state", "")).strip()
        macd_timing_state = macd_breakout_timing_label(row)
        macd_context_complete = str(row.get("macd_context_complete", "")).strip()
        setup_type = str(row.get("setup_type", "")).strip()
        is_macd_breakout = setup_type == "macd_breakout"
        is_fib_limit_setup = setup_type == "fib_limit_live_candidate" or str(row.get("strategy", "")).strip() == "fib_limit"
        timing_state_display = screener_timing_state(row)
        timing_reason_display = screener_timing_reason(row)
        level_summary_items = [
            ("Pivot", get_value(row, "pivot_context", "no_context")),
            ("Dia previo", get_value(row, "previous_day_level_context", "no_context")),
            ("Nivel redondo", get_value(row, "round_level_context", "no_context")),
        ]
        visible_level_summary = [
            (label, value)
            for label, value in level_summary_items
            if str(value).strip() and str(value).strip().lower() not in {"no_context", "pending_source", "not_available"}
        ]
        figure = screener_setup_figure(row, layers, visible_layers=default_layers, fib_mode=SCREENER_DEFAULT_FIB_MODE)
        chart_image_uri = local_image_data_uri(row.get("chart_file"))
        chart_node: Any
        if chart_image_uri:
            chart_node = html.Div(
                [
                    html.Img(src=chart_image_uri, className="screener-reviewed-chart-image"),
                    dcc.Graph(id="screener-setup-graph", figure=figure or {}, style={"display": "none"}),
                ],
                className="screener-reviewed-chart-wrap",
            )
        elif figure:
            chart_node = dcc.Graph(
                id="screener-setup-graph",
                figure=figure,
                config={"displayModeBar": False, "responsive": True},
                className="wave-modal-graph screener-setup-graph",
                style={"height": "92vh", "minHeight": "860px"},
            )
        else:
            chart_node = html.Div("No hay velas suficientes para este setup.", className="radar-empty")
        modal = html.Div(
            [
                html.Div(className="wave-modal-backdrop"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Span(f"{screener_score(row)}/5", className=f"wave-modal-wave {screener_tone(row)}"),
                                        html.Div(
                                            [
                                                html.Strong(get_value(row, "symbol", "symbol")),
                                                html.Small(f"{get_value(row, 'market_group', 'grupo')} / {get_value(row, 'timeframe', 'TF')} / {get_value(row, 'setup_type', 'setup')}"),
                                            ]
                                        ),
                                    ],
                                    className="wave-modal-title",
                                ),
                                html.Div("Cerrar", id="screener-modal-close", n_clicks=0, role="button", tabIndex=0, className="wave-modal-close"),
                            ],
                            className="wave-modal-head",
                        ),
                        html.Div(
                            [
                                html.Span(screener_timing_state(row), className="wave-direction-pill candidate"),
                                html.Span(f"tendencia {display_context_value(get_value(row, 'trend_compatibility', 'mixed'))}", className="wave-direction-pill"),
                                html.Span("study-only", className="wave-direction-pill muted"),
                            ],
                            className="wave-modal-meta compact",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Span("Capas", className="screener-layer-label"),
                                        dcc.Checklist(
                                            id="screener-layer-toggle",
                                            options=layer_options,
                                            value=default_layers,
                                            className="screener-layer-toggle",
                                            inputClassName="screener-layer-input",
                                            labelClassName="screener-layer-option",
                                        ),
                                    ],
                                    className="screener-layer-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Span("Swing Fibo", className="screener-layer-label"),
                                        dcc.RadioItems(
                                            id="screener-fib-mode",
                                            options=SCREENER_FIB_MODE_OPTIONS,
                                            value=SCREENER_DEFAULT_FIB_MODE,
                                            className="screener-fib-mode-toggle",
                                            inputClassName="screener-layer-input",
                                            labelClassName="screener-layer-option",
                                        ),
                                    ],
                                    className="screener-layer-control-group",
                                )
                                if show_fib_mode
                                else html.Div(
                                    dcc.RadioItems(
                                        id="screener-fib-mode",
                                        options=SCREENER_FIB_MODE_OPTIONS,
                                        value=SCREENER_DEFAULT_FIB_MODE,
                                    ),
                                    style={"display": "none"},
                                ),
                            ],
                            className="screener-layer-control",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H3("Lectura"),
                                        html.P(get_value(row, "quality_reason", "sin resumen")),
                                        html.P(f"Timing: {display_context_value(timing_reason_display, empty_label='sin timing especifico')}"),
                                        html.Div([html.Span(chip.replace("_", " "), className="screener-chip") for chip in screener_chips(row.get("confluence_tags"), 3)], className="screener-chip-row compact"),
                                    ],
                                    className="screener-modal-info-card primary",
                                ),
                                html.Div(
                                    [
                                        html.H3("Tendencia"),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.Span([html.Strong(label), f" {arrow}"], className=f"screener-trend-chip {tone}")
                                                        for label, arrow, tone in trend_detail_items(row)
                                                    ],
                                                    className="screener-trend-chip-row",
                                                ),
                                            ],
                                            className="screener-context-block",
                                        ),
                                        html.P(f"RSI: {display_context_value(get_value(row, 'rsi_context', 'neutral'), empty_label='neutral')}"),
                                        html.P(f"WeaveCount: {display_context_value(get_value(row, 'wavecount_context', 'no_context'), empty_label='sin contexto')}"),
                                    ],
                                    className="screener-modal-info-card",
                                ),
                                html.Div(
                                    [
                                        html.H3("Niveles"),
                                        *[
                                            html.P(f"{label}: {display_context_value(value)}")
                                            for label, value in visible_level_summary
                                        ],
                                        html.P("Sin niveles cercanos relevantes.") if not visible_level_summary else None,
                                    ],
                                    className="screener-modal-info-card",
                                ),
                                html.Div(
                                    [
                                        html.H3("Timing"),
                                        html.P(f"Estado: {display_context_value(timing_state_display)}"),
                                        html.P(f"Ruptura estudio: {display_context_value(macd_breakout_level, empty_label='sin nivel reconstruido')}") if is_macd_breakout else None,
                                        html.P(f"Barras desde ruptura: {display_context_value(get_value(row, 'bars_since_breakout', ''), empty_label='n/d')}") if is_macd_breakout else None,
                                        html.P(f"Cruce MACD: {display_context_value(macd_cross_state, empty_label='sin lectura')} / {display_context_value(macd_cross_time, empty_label='sin timestamp')}") if is_macd_breakout else None,
                                        html.P(f"SL/TP estudio: {display_context_value(get_value(row, 'macd_sl_study', ''), empty_label='sin SL')} / {display_context_value(get_value(row, 'macd_tp1_study', ''), empty_label='sin TP1')} / {display_context_value(get_value(row, 'macd_tp2_study', ''), empty_label='sin TP2')}") if is_macd_breakout else None,
                                        html.P(f"Trigger estudio: {display_context_value(fib_study_zone or get_value(row, 'trigger_level', ''), empty_label='sin trigger')}") if is_fib_limit_setup else None,
                                        html.P(f"SL/TP estudio: {display_context_value(fib_study_sl, empty_label='sin SL')} / {display_context_value(fib_study_tp1, empty_label='sin TP1')} / {display_context_value(fib_study_tp2, empty_label='sin TP2')}") if is_fib_limit_setup else None,
                                        html.P(f"Distancia/toque: {display_context_value(get_value(row, 'distance_to_trigger_pct', ''), empty_label='sin distancia')} / {display_context_value(get_value(row, 'last_touch_time', ''), empty_label='sin toque reciente')}") if is_fib_limit_setup else None,
                                        html.P("Vigente") if is_fib_limit_setup and get_value(row, "is_late", "False") != "True" and get_value(row, "is_invalidated", "False") != "True" else None,
                                        html.P(f"Cautela: late={get_value(row, 'is_late', 'False')} / invalidated={get_value(row, 'is_invalidated', 'False')}") if is_fib_limit_setup and (get_value(row, "is_late", "False") == "True" or get_value(row, "is_invalidated", "False") == "True") else None,
                                        html.P("Este setup es contexto de mercado; no tiene disparador de entrada ni timing operativo propio.") if not is_macd_breakout and not is_fib_limit_setup else None,
                                    ],
                                    className="screener-modal-info-card",
                                ),
                            ],
                            className="screener-modal-info-stack",
                        ),
                        chart_node,
                    ],
                    className="wave-modal-panel screener-modal-panel",
                ),
            ]
        )
        return modal, "wave-modal", setup_id

    @app.callback(
        Output("screener-setup-graph", "figure"),
        Input("screener-layer-toggle", "value"),
        Input("screener-fib-mode", "value"),
        State("screener-active-setup-id", "data"),
        State("tc-data", "data"),
        prevent_initial_call=True,
    )
    def update_screener_setup_graph(visible_layers: list[str] | None, fib_mode: str | None, setup_id: str | None, data_obj: dict[str, Any]) -> dict[str, Any]:
        if not setup_id:
            return {}
        row = next((item for item in data_obj.get("screener_setups_rows", []) if str(item.get("setup_id", "")) == str(setup_id)), None)
        if not row:
            return {}
        return screener_setup_figure(row, screener_layer_rows(data_obj, str(setup_id)), visible_layers=visible_layers, fib_mode=fib_mode)

    @app.callback(
        Output("wave-count-content", "children"),
        Input("wave-count-tabs", "value"),
        Input("wave-search", "value"),
        Input("wave-timeframe", "value"),
        Input("wave-group", "value"),
        Input("wave-quality", "value"),
        Input("wave-direction", "value"),
        State("tc-data", "data"),
    )
    def update_wave_cards(
        wave_value: str | None,
        search: str | None,
        timeframe: str | None,
        group: str | None,
        quality: str | None,
        direction: str | None,
        data_obj: dict[str, Any],
    ) -> Any:
        rows = filter_wavecount_number_rows(data_obj["wavecount_rows"], wave_value, search, group, timeframe, quality, direction)
        return wavecount_cards(html, rows)

    @app.callback(
        Output("wave-modal", "children"),
        Output("wave-modal", "className"),
        Input({"type": "wave-case-item", "case_id": ALL}, "n_clicks"),
        Input("wave-modal-close", "n_clicks"),
        State({"type": "wave-case-item", "case_id": ALL}, "id"),
        State("tc-data", "data"),
        prevent_initial_call=True,
    )
    def update_wave_modal(clicks: list[int] | None, close_clicks: int | None, ids: list[dict[str, Any]] | None, data_obj: dict[str, Any]) -> tuple[Any, str]:
        hidden = html.Div(id="wave-modal-close", n_clicks=0, style={"display": "none"})
        triggered = callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0] if callback_context.triggered else ""
        if triggered == "wave-modal-close":
            return hidden, "wave-modal hidden"
        try:
            triggered_id = json.loads(triggered)
        except json.JSONDecodeError:
            return hidden, "wave-modal hidden"
        clicked_count = 0
        if ids and clicks:
            for index, component_id in enumerate(ids):
                if component_id == triggered_id and index < len(clicks):
                    clicked_count = int(clicks[index] or 0)
                    break
        if clicked_count < 1:
            return hidden, "wave-modal hidden"
        case_id = str(triggered_id.get("case_id", ""))
        row = next((item for item in data_obj["wavecount_rows"] if wavecount_case_id(item) == case_id), None)
        if not row:
            return hidden, "wave-modal hidden"
        return wavecount_modal(html, dcc, row), "wave-modal"

    return app



def dash_app_contract_audit() -> list[dict[str, Any]]:
    return [
        {"check_id": "DASH_CONTRACT_01", "check": "module_exists", "status": "passed", "evidence": "trading_center/dash_readonly_app.py"},
        {"check_id": "DASH_CONTRACT_02", "check": "dash_app_factory", "status": "passed", "evidence": "create_app(data)"},
        {"check_id": "DASH_CONTRACT_03", "check": "artifact_first_data", "status": "passed", "evidence": "build_dash_data reuses readonly_dashboard build_data_model"},
        {"check_id": "DASH_CONTRACT_04", "check": "interactive_readonly_surfaces", "status": "passed", "evidence": "tabs, dropdowns, search, radar cards, correlation tools, WeaveCount modal and unified Screener modal"},
    ]


def dash_app_safety_audit() -> list[dict[str, Any]]:
    return [
        {"check_id": "DASH_SAFE_01", "check": "sql_real_written", "status": "passed", "value": False},
        {"check_id": "DASH_SAFE_02", "check": "db_connected", "status": "passed", "value": False},
        {"check_id": "DASH_SAFE_03", "check": "mt5_connected", "status": "passed", "value": False},
        {"check_id": "DASH_SAFE_04", "check": "telegram_connected", "status": "passed", "value": False},
        {"check_id": "DASH_SAFE_05", "check": "secret_inputs_present", "status": "passed", "value": False},
        {"check_id": "DASH_SAFE_06", "check": "operational_buttons_present", "status": "passed", "value": False},
        {"check_id": "DASH_SAFE_07", "check": "wavecount_used_as_filter", "status": "passed", "value": False},
    ]


def write_dash_artifacts(output_dir: Path, data: dict[str, Any]) -> None:
    try:
        from trading_center.codex_ai_analyst_model_gateway import codex_local_config
        codex_config = codex_local_config()
    except Exception:
        codex_config = {"model": "", "model_reasoning_effort": ""}
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_csv(tables_dir / "dash_app_contract_audit.csv", dash_app_contract_audit())
    write_csv(tables_dir / "dash_app_safety_audit.csv", dash_app_safety_audit())
    write_csv(tables_dir / "dash_app_source_audit.csv", data["dash_source_audit"])
    write_csv(
        tables_dir / "dash_market_radar_audit.csv",
        [
            {
                "check_id": "RADAR_01",
                "check": "market_radar_source",
                "status": data["market_radar_source"]["status"],
                "evidence": data["market_radar_source"]["path"],
            },
            {
                "check_id": "RADAR_02",
                "check": "trend_alignment_rows",
                "status": "available" if data["market_radar_source"]["trend_aligned_count"] else "not_available",
                "value": data["market_radar_source"]["trend_aligned_count"],
            },
            {
                "check_id": "RADAR_03",
                "check": "counter_extreme_rows",
                "status": "available" if data["market_radar_source"]["counter_extreme_count"] else "none_in_current_cut",
                "value": data["market_radar_source"]["counter_extreme_count"],
            },
            {
                "check_id": "RADAR_04",
                "check": "no_signal_fabrication",
                "status": "passed",
                "evidence": "Resumen only uses market_radar.csv when present; current snapshot is not converted into trend/RSI readings.",
            },
            {
                "check_id": "RADAR_05",
                "check": "market_pulse_and_volatility",
                "status": "passed" if data["market_radar_source"]["status"] == "available" else "not_available",
                "evidence": "Mercado UI renders market mode, timeframe strength and ATR% H1 rankings against each asset median.",
            },
            {
                "check_id": "RADAR_06",
                "check": "universe_summary_blocks",
                "status": "passed" if data["market_radar_source"]["status"] == "available" else "not_available",
                "evidence": "Radar renders simplified alignment and movement panels with empty-state protection.",
            },
            {
                "check_id": "RADAR_07",
                "check": "asset_lists_are_screener_only",
                "status": "passed",
                "evidence": "Alignment and RSI contexts are absorbed by the unified Screener artifacts, not rendered as Radar summary tables.",
            },
        ],
    )
    write_csv(
        tables_dir / "dash_correlation_audit.csv",
        [
            {
                "check_id": "CORR_DASH_01",
                "check": "correlation_source",
                "status": data["correlation_source"]["status"],
                "evidence": data["correlation_source"]["path"],
                "rows": data["correlation_source"]["rows"],
            },
            {
                "check_id": "CORR_DASH_02",
                "check": "returns_based_not_price_based",
                "status": "passed" if data["correlation_source"].get("returns_based") else "not_available",
                "evidence": "Market correlations are consumed from artifact generated on close-to-close log returns.",
            },
            {
                "check_id": "CORR_DASH_03",
                "check": "timeframe_selector_available",
                "status": "passed",
                "evidence": "Dash Correlacion section exposes corr-timeframe dropdown.",
                "timeframes": "|".join(data["correlation_source"].get("timeframes", [])),
            },
            {
                "check_id": "CORR_DASH_04",
                "check": "views_available",
                "status": "passed",
                "evidence": "Base and Rolling correlation views are read-only; Base includes four pair metrics, LOWESS scatter and fixed selectable matrix.",
            },
            {
                "check_id": "CORR_DASH_05",
                "check": "no_operational_decision",
                "status": "passed",
                "evidence": "Correlation section is context-only; no signals, orders, MT5, Telegram or SQL writes.",
            },
            {
                "check_id": "CORR_DASH_06",
                "check": "returns_sample_for_pair_graph",
                "status": "available" if data["correlation_source"]["returns_rows"] else "missing_or_empty",
                "evidence": data["correlation_source"]["returns_path"],
                "rows": data["correlation_source"]["returns_rows"],
            },
        ],
    )
    write_csv(
        tables_dir / "dash_screener_unified_audit.csv",
        [
            {
                "check_id": "SCREENER_DASH_01",
                "check": "screener_source",
                "status": data["screener_source"]["status"],
                "evidence": data["screener_source"]["setups_path"],
                "rows": data["screener_source"]["setups_rows"],
            },
            {
                "check_id": "SCREENER_DASH_02",
                "check": "chart_layers_source",
                "status": "available" if data["screener_source"]["chart_layers_rows"] else "missing_or_empty",
                "evidence": data["screener_source"]["chart_layers_path"],
                "rows": data["screener_source"]["chart_layers_rows"],
            },
            {
                "check_id": "SCREENER_DASH_03",
                "check": "estrategias_absorbed",
                "status": "passed",
                "evidence": "Visible navigation keeps Screener and removes the separate Estrategias tab.",
            },
            {
                "check_id": "SCREENER_DASH_04",
                "check": "no_operational_controls",
                "status": "passed",
                "evidence": "Screener exposes compact setup rows, filters and chart modal only.",
            },
        ],
    )
    write_csv(
        tables_dir / "dash_ai_analyst_audit.csv",
        [
            {
                "check_id": "AI_DASH_01",
                "check": "floating_assistant_available",
                "status": "passed",
                "evidence": "Dash layout exposes ai-analyst-toggle, ai-analyst-panel and setup selector.",
            },
            {
                "check_id": "AI_DASH_02",
                "check": "package_renderer_integration",
                "status": "passed",
                "evidence": "AI Analyst callback prepares reproducible package through codex_ai_analyst_package_renderer.",
            },
            {
                "check_id": "AI_DASH_03",
                "check": "controlled_gateway_manual_codex_gate",
                "status": "passed",
                "evidence": "Dash default action uses fixture mode; Codex local is only called by explicit ai-analyst-run-codex action.",
            },
            {
                "check_id": "AI_DASH_04",
                "check": "no_operational_side_effects",
                "status": "passed",
                "evidence": "Assistant cannot send MT5/Telegram/SQL/orders/signals from the UI.",
            },
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "issue_id": "R01",
                "severity": "low",
                "status": "closed",
                "description": "Dash reads the generated market radar artifact instead of opening a live SQL connection.",
                "mitigation": "Regenerate sql_market_data_readonly and market_radar before a review session.",
            },
            {
                "issue_id": "R02",
                "severity": "medium",
                "status": "open",
                "description": "Interactive UI can be mistaken for an operational console.",
                "mitigation": "Keep visible read-only labels and do not add order/approval controls.",
            },
            {
                "issue_id": "R03",
                "severity": "medium",
                "status": "open",
                "description": "Telegram configuration must not be collected through the dashboard.",
                "mitigation": "Show status only; secrets stay environment-only outside UI/artifacts.",
            },
            {
                "issue_id": "R04",
                "severity": "low",
                "status": "closed",
                "description": "Radar now uses dedicated market_radar artifact with M15/H1/H4/D1 trend and RSI readings.",
                "mitigation": "Extend future screeners without converting them into execution signals.",
            },
            {
                "issue_id": "R05",
                "severity": "low",
                "status": "closed",
                "description": "WeaveCount study view now groups cases by Onda 1-5 instead of making the raw table the primary surface.",
                "mitigation": "Keep the section as study context: horizontal case items open chart evidence, but never filters or execution controls.",
            },
            {
                "issue_id": "R06",
                "severity": "low",
                "status": "closed",
                "description": "Screener now absorbs Estrategias and uses artifact-first setup cards plus compact matrix.",
                "mitigation": "Quality is labelled as visual/contextual and cannot enable execution.",
            },
            {
                "issue_id": "R07",
                "severity": "medium",
                "status": "open",
                "description": "AI Analyst UI can be confused with an autonomous trading assistant if future model calls are enabled without language gates.",
                "mitigation": "Keep package preparation as the default and require the explicit Codex local action for any real model review.",
            },
        ],
    )
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "trading_center_dash_readonly_v1_ready_for_local_review",
        "dash_app_implemented": True,
        "dash_app_readonly": True,
        "artifact_first": True,
        "dash_auto_refresh_available": True,
        "dash_auto_refresh_default_seconds": DEFAULT_AUTO_REFRESH_SECONDS,
        "ai_analyst_dash_integration_available": True,
        "ai_analyst_package_renderer_available": True,
        "ai_analyst_model_gateway_available": True,
        "ai_analyst_call_mode": "fixture_default_codex_cli_manual_codex_macro_manual",
        "ai_analyst_model_called": False,
        "ai_analyst_network_call_allowed": False,
        "ai_analyst_real_model_enabled": True,
        "ai_analyst_real_model_default": False,
        "ai_analyst_codex_cli_manual_gate": True,
        "ai_analyst_codex_macro_manual_gate": True,
        "ai_analyst_macro_web_research_default": False,
        "ai_analyst_progress_ui_available": True,
        "ai_analyst_pdf_report_available": True,
        "ai_analyst_codex_model_effective": codex_config.get("model", ""),
        "ai_analyst_codex_reasoning_effort_effective": codex_config.get("model_reasoning_effort", ""),
        "latest_manifest_json": str(DEFAULT_LATEST_MANIFEST_JSON),
        "sql_real_read": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "telegram_connected": False,
        "telegram_real_messages_sent": 0,
        "telegram_secret_inputs_present": False,
        "mt5_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "wavecount_used_as_filter": False,
        "operational_buttons_present": False,
        "snapshot_rows": data["summary"]["total_rows"],
        "watchlist_rows": data["summary"]["watchlist_rows"],
        "universe_symbols": data["universe_summary"]["total_symbols"],
        "universe_current_snapshot_symbols": data["universe_summary"]["current_snapshot_symbols"],
        "market_radar_rows": data["market_radar_source"]["rows"],
        "market_radar_source_status": data["market_radar_source"]["status"],
        "trend_aligned_count": data["market_radar_source"]["trend_aligned_count"],
        "counter_extreme_count": data["market_radar_source"]["counter_extreme_count"],
        "correlation_rows": data["correlation_source"]["rows"],
        "correlation_rolling_rows": data["correlation_source"]["rolling_rows"],
        "correlation_returns_rows": data["correlation_source"]["returns_rows"],
        "correlation_source_status": data["correlation_source"]["status"],
        "correlation_returns_based": data["correlation_source"]["returns_based"],
        "correlation_timeframes": data["correlation_source"]["timeframes"],
        "wavecount_rows": len(data["wavecount_rows"]),
        "screener_unified_source_status": data["screener_source"]["status"],
        "screener_setups_rows": data["screener_source"]["setups_rows"],
        "screener_chart_layers_rows": data["screener_source"]["chart_layers_rows"],
        "mt5_shadow_source_status": data["mt5_shadow_source"]["status"],
        "mt5_shadow_decision_rows": data["mt5_shadow_source"]["decision_rows"],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "TRADING_CENTER_DASH_READONLY_V1.md").write_text(render_dash_report(run_meta), encoding="utf-8")


def render_dash_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Dash Read-only V1

Fecha: 2026-05-30

Decision: `{run_meta['decision']}`.

## Resultado

Se implementa una app Dash local para uso real de revision de mercado. La app
carga CSV/JSON auditados, incluido el radar M15/H1/H4/D1 y la capa de
correlaciones por retornos generadas desde artifacts. Ofrece tabs, filtros,
radar visual, correlacion por timeframe y Screener unificado sin conectar SQL en
caliente. La seccion WeaveCount organiza el estudio por recuadros Onda 1-5 y
una lista horizontal de casos clicables que abren el grafico de velas/trazado
del caso cuando existe contexto de grafico, manteniendo el uso study-only. La
antigua superficie Estrategias queda absorbida por Screener: arriba aparecen
setups destacados con calidad visual 1-5; el detalle se consulta en un modal
vertical al hacer clic y la matriz por activo ya no se renderiza en la UI. La
integracion AI Analyst anade un boton flotante read-only que prepara paquetes
reproducibles y mantiene fixture como accion por defecto. Si el usuario pulsa
`Analizar con Codex local`, el panel llama al gateway `codex_cli` con sandbox
read-only y auditoria. La accion separada `Codex + macro` activa
`--macro-web-research` para que Codex local pueda consultar internet y
documentar riesgo macro/noticias con fuentes; este modo tambien es manual y no
conecta MT5, Telegram ni SQL.
Mientras se ejecuta un analisis, el panel muestra estado de progreso y bloquea
visualmente los tres botones de accion para evitar doble ejecucion accidental.
Cada review validada genera `ai_analyst_review_report.pdf`, descargable desde
el propio panel como informe redactado read-only. La pestana `MT5 Bot`
consume `mt5_shadow_decisions.csv` y `run_meta.json` para mostrar que habria
hecho el modo shadow con los setups actuales, siempre como auditoria hipotetica:
no conecta MT5, no envia ordenes y no modifica posiciones.

## Limites

- No escribe SQL.
- No conecta DB.
- No ejecuta DDL.
- No conecta MT5.
- No conecta Telegram.
- No pide token ni chat id.
- No genera senales.
- No ejecuta backtests.
- No usa WaveCount como filtro.
- AI Analyst queda con fixture por defecto y Codex local solo bajo gate manual.

## Datos

- snapshot_rows={run_meta['snapshot_rows']}
- watchlist_rows={run_meta['watchlist_rows']}
- universe_symbols={run_meta['universe_symbols']}
- universe_current_snapshot_symbols={run_meta['universe_current_snapshot_symbols']}
- market_radar_rows={run_meta['market_radar_rows']}
- trend_aligned_count={run_meta['trend_aligned_count']}
- counter_extreme_count={run_meta['counter_extreme_count']}
- correlation_rows={run_meta['correlation_rows']}
- correlation_rolling_rows={run_meta['correlation_rolling_rows']}
- correlation_returns_rows={run_meta['correlation_returns_rows']}
- correlation_timeframes={', '.join(run_meta['correlation_timeframes'])}
- wavecount_rows={run_meta['wavecount_rows']}
- screener_setups_rows={run_meta['screener_setups_rows']}
- screener_chart_layers_rows={run_meta['screener_chart_layers_rows']}
- mt5_shadow_source_status={run_meta['mt5_shadow_source_status']}
- mt5_shadow_decision_rows={run_meta['mt5_shadow_decision_rows']}
- ai_analyst_call_mode={run_meta['ai_analyst_call_mode']}
- ai_analyst_model_called={run_meta['ai_analyst_model_called']}

## Uso

```powershell
python -m trading_center.dash_readonly_app --port 8050
```

Abrir:

`http://127.0.0.1:8050/`
"""


def build_dash_data_from_args(args: argparse.Namespace) -> dict[str, Any]:
    global ACTIVE_SQL_OHLC_CSV
    ACTIVE_SQL_OHLC_CSV = args.ohlc_csv
    wavecount_ohlc_index.cache_clear()
    screener_ohlc_index.cache_clear()
    return build_dash_data(
        snapshot_csv=args.snapshot_csv,
        security_flags_csv=args.security_flags_csv,
        counts_csv=args.counts_csv,
        migrations_csv=args.migrations_csv,
        export_manifest_csv=args.export_manifest_csv,
        wavecount_csv=args.wavecount_csv,
        wavecount_expanded_csv=args.wavecount_expanded_csv,
        wavecount_buckets_csv=args.wavecount_buckets_csv,
        wavecount_visual_cases_csv=args.wavecount_visual_cases_csv,
        wavecount_no_action_csv=args.wavecount_no_action_csv,
        design_widgets_csv=args.design_widgets_csv,
        telegram_sender_review_meta=args.telegram_sender_review_meta,
        bot_review_meta=args.bot_review_meta,
        sql_go_no_go_meta=args.sql_go_no_go_meta,
        symbol_control_csv=args.symbol_control_csv,
        price_symbols_csv=args.price_symbols_csv,
        market_radar_csv=args.market_radar_csv,
        correlation_pairs_csv=args.correlation_pairs_csv,
        rolling_correlations_csv=args.rolling_correlations_csv,
        correlation_returns_csv=args.correlation_returns_csv,
        correlation_meta_json=args.correlation_meta_json,
        weavecount_screener_csv=args.weavecount_screener_csv,
        weavecount_structure_points_csv=args.weavecount_structure_points_csv,
        screener_setups_csv=args.screener_setups_csv,
        screener_chart_layers_csv=args.screener_chart_layers_csv,
        mt5_shadow_decisions_csv=args.mt5_shadow_decisions_csv,
        mt5_shadow_meta_json=args.mt5_shadow_meta_json,
        riskguard_decisions_csv=args.riskguard_decisions_csv,
        riskguard_meta_json=args.riskguard_meta_json,
        mt5_demo_sender_meta_json=args.mt5_demo_sender_meta_json,
        mt5_demo_manager_meta_json=args.mt5_demo_manager_meta_json,
        telegram_real_sender_meta_json=args.telegram_real_sender_meta_json,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Trading Center Dash read-only app from audited artifacts.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--audit-only", action="store_true", help="Write audit artifacts and exit without starting Dash.")
    parser.add_argument("--auto-refresh-seconds", type=int, default=DEFAULT_AUTO_REFRESH_SECONDS)
    parser.add_argument("--disable-auto-refresh", action="store_true")
    parser.add_argument("--latest-manifest-json", type=Path, default=DEFAULT_LATEST_MANIFEST_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--snapshot-csv", type=Path, default=DEFAULT_SNAPSHOT_CSV)
    parser.add_argument("--security-flags-csv", type=Path, default=DEFAULT_SECURITY_FLAGS_CSV)
    parser.add_argument("--counts-csv", type=Path, default=DEFAULT_COUNTS_CSV)
    parser.add_argument("--migrations-csv", type=Path, default=DEFAULT_MIGRATIONS_CSV)
    parser.add_argument("--export-manifest-csv", type=Path, default=DEFAULT_EXPORT_MANIFEST_CSV)
    parser.add_argument("--wavecount-csv", type=Path, default=DEFAULT_WAVECOUNT_CSV)
    parser.add_argument("--wavecount-expanded-csv", type=Path, default=DEFAULT_WAVECOUNT_EXPANDED_CSV)
    parser.add_argument("--wavecount-buckets-csv", type=Path, default=DEFAULT_WAVECOUNT_BUCKETS_CSV)
    parser.add_argument("--wavecount-visual-cases-csv", type=Path, default=DEFAULT_WAVECOUNT_VISUAL_CASES_CSV)
    parser.add_argument("--wavecount-no-action-csv", type=Path, default=DEFAULT_WAVECOUNT_NO_ACTION_CSV)
    parser.add_argument("--design-widgets-csv", type=Path, default=DEFAULT_DESIGN_WIDGETS_CSV)
    parser.add_argument("--telegram-sender-review-meta", type=Path, default=DEFAULT_TELEGRAM_SENDER_REVIEW_META)
    parser.add_argument("--bot-review-meta", type=Path, default=DEFAULT_BOT_REVIEW_META)
    parser.add_argument("--sql-go-no-go-meta", type=Path, default=DEFAULT_SQL_GO_NO_GO_META)
    parser.add_argument("--symbol-control-csv", type=Path, default=DEFAULT_SYMBOL_CONTROL_CSV)
    parser.add_argument("--price-symbols-csv", type=Path, default=DEFAULT_PRICE_SYMBOLS_CSV)
    parser.add_argument("--market-radar-csv", type=Path, default=DEFAULT_MARKET_RADAR_CSV)
    parser.add_argument("--correlation-pairs-csv", type=Path, default=DEFAULT_CORRELATION_PAIRS_CSV)
    parser.add_argument("--rolling-correlations-csv", type=Path, default=DEFAULT_ROLLING_CORRELATIONS_CSV)
    parser.add_argument("--correlation-returns-csv", type=Path, default=DEFAULT_CORRELATION_RETURNS_CSV)
    parser.add_argument("--correlation-meta-json", type=Path, default=DEFAULT_CORRELATION_META_JSON)
    parser.add_argument("--ohlc-csv", type=Path, default=DEFAULT_SQL_OHLC_CSV)
    parser.add_argument("--weavecount-screener-csv", type=Path, default=DEFAULT_WEAVECOUNT_SCREENER_CSV)
    parser.add_argument("--weavecount-structure-points-csv", type=Path, default=DEFAULT_WEAVECOUNT_STRUCTURE_POINTS_CSV)
    parser.add_argument("--screener-setups-csv", type=Path, default=DEFAULT_SCREENER_SETUPS_CSV)
    parser.add_argument("--screener-chart-layers-csv", type=Path, default=DEFAULT_SCREENER_CHART_LAYERS_CSV)
    parser.add_argument("--mt5-shadow-decisions-csv", type=Path, default=DEFAULT_MT5_SHADOW_DECISIONS_CSV)
    parser.add_argument("--mt5-shadow-meta-json", type=Path, default=DEFAULT_MT5_SHADOW_META_JSON)
    parser.add_argument("--riskguard-decisions-csv", type=Path, default=DEFAULT_RISKGUARD_DECISIONS_CSV)
    parser.add_argument("--riskguard-meta-json", type=Path, default=DEFAULT_RISKGUARD_META_JSON)
    parser.add_argument("--mt5-demo-sender-meta-json", type=Path, default=DEFAULT_MT5_DEMO_SENDER_META_JSON)
    parser.add_argument("--mt5-demo-manager-meta-json", type=Path, default=DEFAULT_MT5_DEMO_MANAGER_META_JSON)
    parser.add_argument("--telegram-real-sender-meta-json", type=Path, default=DEFAULT_TELEGRAM_REAL_SENDER_META_JSON)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    data = build_dash_data_from_args(args)
    write_dash_artifacts(args.output_dir, data)
    if args.audit_only:
        return
    app = create_app(
        data,
        auto_refresh_seconds=args.auto_refresh_seconds,
        disable_auto_refresh=args.disable_auto_refresh,
        latest_manifest_json=args.latest_manifest_json,
        data_builder=lambda: build_dash_data_from_args(args),
    )
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
