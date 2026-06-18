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

def test_latest_path_resolution_prefers_latest_when_available(tmp_path: Path) -> None:
    latest_file = tmp_path / "latest" / "market_radar.csv"
    fallback_file = tmp_path / "canonical" / "market_radar.csv"
    latest_file.parent.mkdir(parents=True)
    fallback_file.parent.mkdir(parents=True)
    latest_file.write_text("latest", encoding="utf-8")
    fallback_file.write_text("fallback", encoding="utf-8")

    assert latest_or_fallback_path(latest_file, fallback_file) == latest_file
    latest_file.unlink()
    assert latest_or_fallback_path(latest_file, fallback_file) == fallback_file


def test_latest_matching_file_can_ignore_fixture_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from trading_center import dash_readonly_app as app_module

    canonical = tmp_path / "canonical" / "run_meta.json"
    fixture = tmp_path / "artifacts" / "mt5_demo_order_sender_v1_2026-06-08_fixture" / "run_meta.json"
    real = tmp_path / "artifacts" / "mt5_demo_order_sender_v1_2026-06-08_real_send" / "run_meta.json"
    for path in (canonical, fixture, real):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    fixture.touch()
    real.touch()
    monkeypatch.setattr(app_module, "REPO_ROOT", tmp_path)

    selected = app_module.latest_matching_file(
        "artifacts/mt5_demo_order_sender_v1_2026-06-08*/run_meta.json",
        canonical,
        exclude_name_fragments=("fixture",),
    )

    assert selected == real


def test_latest_dir_resolution_requires_component_file(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest" / "weavecount"
    fallback_dir = tmp_path / "canonical" / "weavecount"
    latest_dir.mkdir(parents=True)
    fallback_dir.mkdir(parents=True)
    fallback_file = fallback_dir / "weavecount_screener.csv"
    fallback_file.write_text("fallback", encoding="utf-8")

    assert latest_or_fallback_dir(latest_dir, fallback_dir, "weavecount_screener.csv") == fallback_dir
    (latest_dir / "weavecount_screener.csv").write_text("latest", encoding="utf-8")
    assert latest_or_fallback_dir(latest_dir, fallback_dir, "weavecount_screener.csv") == latest_dir


def test_latest_manifest_metadata_reads_fingerprint_and_timestamp(tmp_path: Path) -> None:
    manifest = tmp_path / "latest_manifest.json"
    manifest.write_text(
        json.dumps({"generated_at": "2026-06-06T10:00:00+00:00", "refresh_decision": "refresh_allowed", "components": [{"component": "market_radar"}]}),
        encoding="utf-8",
    )

    metadata = load_latest_manifest_metadata(manifest)

    assert metadata["exists"] is True
    assert metadata["fingerprint"]
    assert metadata["manifest_timestamp"] == "2026-06-06T10:00:00+00:00"
    assert metadata["refresh_decision"] == "refresh_allowed"
    assert metadata["component_count"] == 1


def test_manifest_state_without_changes_does_not_force_reload(tmp_path: Path) -> None:
    manifest = tmp_path / "latest_manifest.json"
    manifest.write_text(json.dumps({"generated_at": "2026-06-06T10:00:00+00:00"}), encoding="utf-8")
    state = build_manifest_refresh_state(manifest)
    builder_calls: list[str] = []

    should_reload, next_state, refreshed = maybe_refresh_dash_data(
        state,
        manifest,
        data_builder=lambda: builder_calls.append("called") or {"summary": {"total_rows": 0}},
    )

    assert should_reload is False
    assert refreshed is None
    assert builder_calls == []
    assert next_state["fingerprint"] == state["fingerprint"]


def test_manifest_change_returns_updated_data(tmp_path: Path) -> None:
    manifest = tmp_path / "latest_manifest.json"
    manifest.write_text(json.dumps({"generated_at": "2026-06-06T10:00:00+00:00"}), encoding="utf-8")
    state = build_manifest_refresh_state(manifest)
    manifest.write_text(json.dumps({"generated_at": "2026-06-06T10:15:00+00:00"}), encoding="utf-8")

    should_reload, next_state, refreshed = maybe_refresh_dash_data(
        state,
        manifest,
        data_builder=lambda: {"summary": {"total_rows": 1}, "correlation_returns_rows": []},
    )

    assert should_reload is True
    assert refreshed is not None
    assert next_state["reload_reason"] == "manifest_changed"


def test_refresh_status_payload_reflects_auto_refresh_state() -> None:
    payload = build_refresh_status_payload(
        {
            "exists": True,
            "manifest_timestamp": "2026-06-06T10:15:00+00:00",
            "refresh_decision": "refresh_allowed",
            "loaded_at_utc": "2026-06-06T10:15:30+00:00",
        },
        auto_refresh_enabled=False,
    )

    assert payload["auto_refresh_enabled"] is False
    assert payload["manifest_exists"] is True
    assert payload["refresh_decision"] == "refresh_allowed"


def test_refresh_status_labels_are_human_readable() -> None:
    assert format_dashboard_timestamp("2026-06-06T23:12:49.968080+00:00") == "07 Jun 01:12"
    assert format_dashboard_timestamp("") == "sin datos"
    assert refresh_decision_label("refresh_allowed") == ("Refresh OK", "ok")
    assert refresh_decision_label("refresh_allowed_with_warnings") == ("Refresh con avisos", "warning")
    assert refresh_decision_label("use_last_good_artifacts") == ("Usando last-good", "warning")
    assert refresh_decision_label("refresh_blocked") == ("Refresh bloqueado", "danger")


def test_dash_cli_defaults_point_to_latest_manifest_and_auto_refresh() -> None:
    args = parse_args([])

    assert args.auto_refresh_seconds == 30
    assert args.disable_auto_refresh is False
    assert args.latest_manifest_json == DEFAULT_LATEST_MANIFEST_JSON


def test_build_dash_data_from_args_remains_artifact_first() -> None:
    args = parse_args(["--disable-auto-refresh"])
    data = build_dash_data_from_args(args)

    assert data["dash_method_version"] == "trading_center_dash_readonly_v1"
    assert data["market_radar_source"]["path"]
    assert data["correlation_source"]["path"]
    assert data["screener_source"]["setups_path"]
    assert "mt5_shadow_source" in data
    assert "mt5_shadow_rows" in data
    assert "riskguard_source" in data
    assert "riskguard_decision_rows" in data
    assert "mt5_demo_sender_source" in data
    assert "mt5_demo_manager_source" in data
    assert "telegram_real_sender_source" in data
    assert args.mt5_demo_manager_meta_json
    assert args.telegram_real_sender_meta_json
