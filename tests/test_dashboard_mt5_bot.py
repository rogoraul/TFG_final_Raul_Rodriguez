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

def test_mt5_shadow_summary_counts_states() -> None:
    rows = [
        {"shadow_state": "would_wait", "automation_scope": "auto_candidate"},
        {"shadow_state": "would_wait", "automation_scope": "auto_candidate"},
        {"shadow_state": "would_skip_context_only", "automation_scope": "context_only"},
        {"shadow_state": "blocked", "automation_scope": "below_min_quality"},
    ]

    summary = mt5_shadow_summary(rows)

    assert summary["total"] == 4
    assert summary["would_wait"] == 2
    assert summary["would_skip_context_only"] == 1
    assert summary["blocked"] == 1
    assert summary["auto_candidate"] == 2
    assert summary["context_only"] == 1
    assert summary["below_min_quality"] == 1


def test_mt5_shadow_status_labels_are_human_readable() -> None:
    assert mt5_shadow_status_label("mt5_shadow_v1_ready_for_local_shadow_review") == "Shadow listo"
    assert riskguard_status_label("riskguard_demo_intent_builder_v1_ready_for_dashboard_review") == "RiskGuard listo"
    assert sender_status_label({"orders_sent": 1}) == "Orden demo enviada"
    assert manager_status_label({"positions_closed": 1}) == "Cierre validado"
    assert telegram_info_status_label({"telegram_connected": True, "telegram_real_messages_sent": 1}) == "Telegram info ON"
    assert telegram_info_sent_label({"telegram_real_messages_sent": 1}) == "1 aviso enviado"
    assert telegram_info_result_label({"decision": "telegram_real_sender_v1_real_send_executed"}) == "ultimo envio OK"
    assert telegram_info_status_label({}) == "Telegram info OFF"
    assert mt5_shadow_state_label("would_wait") == "esperando"


def test_riskguard_waiting_confirmation_label_is_not_stale() -> None:
    assert riskguard_decision_label("blocked_by_waiting_confirmation") == "bloqueado: falta confirmacion"
    assert riskguard_decision_detail("blocked_by_waiting_confirmation") == "esperando cierre que confirme el setup"
    assert riskguard_decision_label("blocked_by_stale_data") == "bloqueado: datos no vigentes"


def test_riskguard_decision_index_matches_setup_id() -> None:
    rows = [
        {"setup_id": "setup-1", "riskguard_decision": "blocked_by_late_setup"},
        {"setup_id": "setup-2", "riskguard_decision": "blocked_by_waiting_confirmation"},
    ]

    index = riskguard_decision_index(rows)

    assert index["setup-2"]["riskguard_decision"] == "blocked_by_waiting_confirmation"


def test_riskguard_decision_summary_counts_reviewed_blocked_and_late() -> None:
    rows = [
        {"riskguard_decision": "blocked_by_late_setup"},
        {"riskguard_decision": "blocked_by_late_setup"},
        {"riskguard_decision": "blocked_by_waiting_confirmation"},
        {"riskguard_decision": "accepted_for_demo_intent"},
    ]

    summary = riskguard_decision_summary(rows)

    assert summary["reviewed"] == 4
    assert summary["blocked"] == 3
    assert summary["late"] == 2
    assert summary["waiting"] == 1
    assert summary["accepted"] == 1
