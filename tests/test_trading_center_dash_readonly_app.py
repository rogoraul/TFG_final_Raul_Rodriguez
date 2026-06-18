from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_center.dash_readonly_app import (
    build_dash_data,
    create_app,
    write_dash_artifacts,
)


def _dashboard_contract_source() -> str:
    source_paths = [
        Path("trading_center/dash_readonly_app.py"),
        Path("trading_center/dashboard/layout.py"),
        Path("trading_center/dashboard/market.py"),
        Path("trading_center/dashboard/correlations.py"),
        Path("trading_center/dashboard/mt5_bot.py"),
        Path("trading_center/dashboard/weavecount.py"),
        Path("trading_center/dashboard/screener.py"),
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def _collect_component_ids(component: object) -> list[str]:
    ids: list[str] = []
    component_id = getattr(component, "id", None)
    if isinstance(component_id, str):
        ids.append(component_id)
    children = getattr(component, "children", None)
    if children is None:
        return ids
    if isinstance(children, (list, tuple)):
        for child in children:
            ids.extend(_collect_component_ids(child))
    else:
        ids.extend(_collect_component_ids(children))
    return ids


def _find_component_by_id(component: object, component_id: str) -> object | None:
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            found = _find_component_by_id(child, component_id)
            if found is not None:
                return found
        return None
    return _find_component_by_id(children, component_id)


def test_mt5_shadow_tab_is_visible_in_navigation() -> None:
    pytest.importorskip("dash")
    app = create_app(build_dash_data(), disable_auto_refresh=True)
    tabs = _find_component_by_id(app.layout, "main-tabs")

    values = [getattr(child, "value", "") for child in getattr(tabs, "children", [])]
    labels = [getattr(child, "label", "") for child in getattr(tabs, "children", [])]

    assert "mt5_shadow" in values
    assert "MT5 Bot" in labels
    assert "MT5 Shadow" not in labels


def test_auto_refresh_can_be_disabled_in_layout() -> None:
    pytest.importorskip("dash")
    app = create_app(build_dash_data(), disable_auto_refresh=True)
    interval_component = _find_component_by_id(app.layout, "tc-auto-refresh-interval")

    assert interval_component is not None
    assert getattr(interval_component, "disabled", False) is True


def test_dash_audit_artifacts_keep_fail_closed_flags(tmp_path: Path) -> None:
    data = build_dash_data()
    output_dir = tmp_path / "dash"

    write_dash_artifacts(output_dir, data)

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["dash_app_implemented"] is True
    assert run_meta["dash_app_readonly"] is True
    assert run_meta["artifact_first"] is True
    assert run_meta["sql_real_read"] is False
    assert run_meta["sql_real_written"] is False
    assert run_meta["ddl_executed"] is False
    assert run_meta["db_connected"] is False
    assert run_meta["telegram_connected"] is False
    assert run_meta["telegram_secret_inputs_present"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["orders_sent"] == 0
    assert run_meta["signals_generated"] is False
    assert run_meta["backtests_executed"] is False
    assert run_meta["wavecount_used_as_filter"] is False
    assert run_meta["operational_buttons_present"] is False
    assert run_meta["universe_symbols"] >= 60
    assert run_meta["universe_current_snapshot_symbols"] == 27
    assert run_meta["market_radar_source_status"] in {"available", "missing_or_empty"}
    assert run_meta["trend_aligned_count"] >= 0
    assert run_meta["counter_extreme_count"] >= 0
    assert run_meta["correlation_source_status"] in {"available", "missing_or_empty"}
    assert run_meta["correlation_rows"] >= 0
    assert run_meta["correlation_returns_rows"] >= 0
    assert run_meta["correlation_returns_based"] in {True, False}
    assert run_meta["screener_unified_source_status"] in {"available", "missing_or_empty"}
    assert run_meta["screener_setups_rows"] >= 0
    assert run_meta["screener_chart_layers_rows"] >= 0
    assert run_meta["ai_analyst_dash_integration_available"] is True
    assert run_meta["ai_analyst_model_called"] is False
    assert run_meta["ai_analyst_network_call_allowed"] is False
    assert (output_dir / "tables/dash_app_contract_audit.csv").exists()
    assert (output_dir / "tables/dash_app_safety_audit.csv").exists()
    assert (output_dir / "tables/dash_app_source_audit.csv").exists()
    assert (output_dir / "tables/dash_market_radar_audit.csv").exists()
    assert (output_dir / "tables/dash_correlation_audit.csv").exists()
    assert (output_dir / "tables/dash_screener_unified_audit.csv").exists()
    assert (output_dir / "tables/dash_ai_analyst_audit.csv").exists()


def test_dash_app_layout_has_no_secret_input_ids() -> None:
    pytest.importorskip("dash")
    app = create_app(build_dash_data())

    ids = _collect_component_ids(app.layout)
    source = _dashboard_contract_source()

    assert "tc-data" in ids
    assert "tc-manifest-state" in ids
    assert "tc-auto-refresh-interval" in ids
    assert "refresh-status-panel" in ids
    assert "Dash escuchando cambios" in source
    assert "Panel cargado" in source
    assert "Datos publicados" in source
    assert "Refresh OK" in source
    assert "Auto-refresh activo" not in source
    assert "Ultima carga" not in source
    assert 'html.Span(f"Manifest' not in source
    assert 'html.Span(f"Estado {decision}' not in source
    assert "main-tabs" in ids
    assert "section-nav" in source
    assert "vertical=True" in source
    assert "brand-mark" not in source
    assert "status-pill" not in source
    assert "lock-chip" not in source
    assert "lock-panel" not in source
    assert "Correlaciones calculadas sobre retornos" not in source
    assert "Resumen de mercado:" not in source
    assert "Mercado" in source
    assert "Screener" in source
    assert "Correlacion" in source
    assert "WeaveCount" in source
    assert 'dcc.Tab(label="Estrategias"' not in source
    assert 'value="watchlist"' not in source
    assert "Estudios" not in source
    assert 'dcc.Tab(label="Activo"' not in source
    assert 'dcc.Tab(label="Sistema"' not in source
    assert 'dcc.Tab(label="Limites"' not in source
    assert 'def detail_tab' not in source
    assert 'def system_tab' not in source
    assert 'def limits_tab' not in source
    assert "asset-select" not in source
    assert "asset-detail-cards" not in source
    assert "detail-toolbar" not in source
    assert "detail-grid" not in source
    assert "detail-card" not in source
    assert "source-audit-table" not in source
    assert "security-flags-table" not in source
    assert "telegram-status-table" not in source
    assert "bot-status-table" not in source
    assert "sql-runtime-status-table" not in source
    assert source.index('dcc.Tab(label="Mercado"') < source.index('dcc.Tab(label="Correlacion"')
    assert source.index('dcc.Tab(label="Correlacion"') < source.index('dcc.Tab(label="WeaveCount"')
    assert source.index('dcc.Tab(label="WeaveCount"') < source.index('dcc.Tab(label="Screener"')
    assert "corr-timeframe" in source
    assert "corr-asset" in source
    assert "corr-other-asset" in source
    assert "corr-metric" in source
    assert "corr-matrix-assets" in source
    assert "corr-view" in source
    assert '"pearson"' in source
    assert "EURUSD" in source
    assert "Base" in source
    assert "Rolling" in source
    assert 'dcc.Tab(label="Parcial"' not in source
    assert "retornos close-to-close" in source
    assert "LOWESS" in source
    assert '"type": "scatter"' in source
    assert "scattergl" not in source
    assert '"template": "plotly_dark"' in source
    assert '"plot_bgcolor": "#07100f"' in source
    assert '"hoverlabel"' in source
    assert '"bgcolor": "#0d1b1a"' in source
    assert '"bordercolor": "#5ce0ca"' in source
    assert "PLOTLY_HOVERLABEL" in source
    assert ".hoverlayer .hovertext rect" in source
    assert ".js-plotly-plot g.hovertext path" in source
    assert "fill-opacity: 1 !important" in source
    assert "Distancia" in source
    assert "corr-rolling-pair-graph" in source
    assert "Evolucion rolling" in source
    assert "correlation-matrix-graph" in source
    assert "corr-pair-scatter" in source
    assert "Activos con setup a revisar" in source
    assert "trend alignment queda como contexto" in source
    assert "screener-highlighted-setups" in source
    assert "Matriz por activo" not in source
    assert "screener-asset-matrix" not in source
    assert "screener-modal" in source
    assert "screener_setup_figure" in source
    assert "setups a revisar" in source
    assert "prioriza que grafico revisar" not in source
    assert "timing_state" in source
    assert "Distancia/toque:" in source
    assert "Ultimo toque:" not in source
    assert "Vigente" in source
    assert "Cautela:" in source
    assert "Tarde o invalidado:" not in source
    assert "Barras desde toque:" not in source
    assert "Pendiente" not in source
    assert "wave-modal-meta compact" in source
    assert "screener-signal-list" in source
    assert "screener-signal-row" in source
    assert "screener-card-grid" not in source
    assert "screener-matrix-row" not in source
    assert "screener-modal-info-stack" in source
    assert "ai-analyst-toggle" in ids
    assert "ai-analyst-panel" in ids
    assert "ai-analyst-context" in ids
    assert "ai-analyst-screener-controls" in ids
    assert "ai-analyst-wave-controls" in ids
    assert "ai-analyst-correlation-controls" in ids
    assert "ai-analyst-correlation-select" in ids
    assert "ai-analyst-market-controls" in ids
    assert "ai-analyst-setup-state" in ids
    assert "ai-analyst-setup-select" in ids
    assert "ai-analyst-wave-select" in ids
    assert "ai-analyst-run" in ids
    assert "ai-analyst-run-codex" in ids
    assert "ai-analyst-run-codex-macro" in ids
    assert "ai-analyst-progress" in ids
    assert "ai-analyst-report-download" in ids
    assert "Preparar paquete" in source
    assert "Analizar con Codex local" in source
    assert "Codex + macro" in source
    assert "Descargar informe PDF" in source
    assert "Descargar diagnostico PDF" in source
    assert "ai_analyst_review_report.pdf" in source
    assert "Codex manual" in source
    assert "run_ai_analyst_controlled_review" in source
    assert "Mercado se incluye siempre como contexto base" in source
    assert "Tipo de analisis" in source
    assert "Caso WeaveCount" in source
    assert "Mercado" in source
    assert "Correlacion" in source
    assert "WeaveCount" in source
    assert "paquete contextual pendiente" not in source
    assert "paquete reproducible" in source
    data = build_dash_data()
    screener_rows = data.get("screener_setups_rows", [])
    assert screener_rows
    assert all(str(row.get("can_execute_order", "")).lower() in {"", "false"} for row in screener_rows)
    assert "trade_ready" not in source
    assert "artifact H1/H4/D1" not in source
    assert "universe-table" not in source
    assert "Distribuciones" not in source
    assert "Alineacion H1/H4/D1" not in source
    assert "radar-hero" in source
    assert "Fuerza del universo" in source
    assert "Volatilidad" in source
    assert "Exceso vs mediana" in source
    assert "Carencia vs mediana" in source
    assert "Lectura de mercado" in source
    assert "Alineacion limpia" in source
    assert "Alineacion tactica" in source
    assert "Movimiento del universo" in source
    assert "radar-insight-grid" in source
    assert "reading-row" in source
    assert "pressure-bar" in source
    assert 'def screener_tab' in source
    assert "vol-rank-row" in source
    assert "vol-card" not in source
    assert "radar-table" not in source
    assert "overview-trend-alignment-table" not in source
    assert "overview-counter-extreme-table" not in source
    assert "screener-search" in source
    assert "screener-quality-min" in source
    assert "screener-review-state" in source
    assert "screener_review_state_options" in source
    assert "watch-search" not in source
    assert "watch-table" not in source
    assert "wave-search" in source
    assert "wave-quality" in source
    assert "wave-direction" in source
    assert "wave-count-tabs" in source
    assert "wave-count-content" in source
    assert "wave-horizontal-list" in source
    assert "flex-wrap: wrap;" in source
    assert "scroll-snap-type: x proximity" not in source
    assert "wave-case-item" in source
    assert "wave-modal" in source
    assert "wavecount_chart_data_uri" in source
    assert 'rsplit(".", 1)' in source
    assert "confianza:" not in source
    assert "frescura:" not in source
    assert "wave-table" not in source
    assert "Onda {item['number']}" in source
    assert "filter_wavecount_number_rows" in source
    assert "wavecount_quality_options" in source
    assert "wavecount_direction_options" in source
    forbidden = ("token", "chat", "secret", "api_key", "password", "telegram-token", "telegram-chat")
    assert not any(any(term in component_id.lower() for term in forbidden) for component_id in ids)


def test_dash_module_does_not_import_db_mt5_or_telegram_clients() -> None:
    source = _dashboard_contract_source()

    forbidden = [
        "mysql.connector",
        "MetaTrader5",
        "requests",
        "urllib.request",
        "telegram.",
        "Bot(",
        "html.Button",
    ]
    for token in forbidden:
        assert token not in source
