from __future__ import annotations

from typing import Any, Callable


def build_app_layout(
    *,
    html: Any,
    dcc: Any,
    client_app_data: dict[str, Any],
    initial_manifest_state: dict[str, Any],
    auto_refresh_seconds: int,
    disable_auto_refresh: bool,
    refresh_status_view: Callable[[dict[str, Any]], Any],
    ai_analyst_context_options: Callable[[], list[dict[str, Any]]],
    ai_analyst_setup_options: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    ai_analyst_wave_options: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    ai_analyst_correlation_options: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> Any:
    return html.Div(
        [
            dcc.Store(id="tc-data", data=client_app_data),
            dcc.Store(id="tc-manifest-state", data=initial_manifest_state),
            dcc.Store(id="screener-active-setup-id", data=None),
            dcc.Store(id="ai-analyst-panel-open", data=False),
            dcc.Interval(
                id="tc-auto-refresh-interval",
                interval=max(5, int(auto_refresh_seconds)) * 1000,
                n_intervals=0,
                disabled=disable_auto_refresh,
            ),
            html.Aside(
                    [
                        html.Div([html.Strong("Trading Center")], className="brand"),
                        html.Nav(
                            [
                            html.Div("Secciones", className="nav-title"),
                            dcc.Tabs(
                                id="main-tabs",
                                value="overview",
                                vertical=True,
                                className="section-tabs",
                                persistence=True,
                                persistence_type="session",
                                children=[
                                    dcc.Tab(label="Mercado", value="overview", className="section-tab", selected_className="section-tab-selected"),
                                    dcc.Tab(label="Correlacion", value="correlation", className="section-tab", selected_className="section-tab-selected"),
                                    dcc.Tab(label="WeaveCount", value="wavecount", className="section-tab", selected_className="section-tab-selected"),
                                    dcc.Tab(label="Screener", value="universe", className="section-tab", selected_className="section-tab-selected"),
                                    dcc.Tab(label="MT5 Bot", value="mt5_shadow", className="section-tab", selected_className="section-tab-selected"),
                                ],
                            ),
                        ],
                        className="section-nav",
                    ),
                ],
                className="sidebar",
            ),
            html.Main(
                [
                    html.Header(
                        [
                            html.Div(
                                [html.P("", id="section-crumb", className="eyebrow", style={"display": "none"}), html.H1("Mercado", id="section-title")],
                            ),
                            html.Div(refresh_status_view(initial_manifest_state), id="refresh-status-panel", className="refresh-status-shell"),
                        ],
                        className="topbar",
                    ),
                    html.Div(id="tab-content", className="content-panel"),
                ],
                className="content",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(className="ai-bot-antenna"),
                            html.Span(
                                [
                                    html.Span(className="ai-bot-eye"),
                                    html.Span(className="ai-bot-eye"),
                                ],
                                className="ai-bot-face",
                            ),
                            html.Span(className="ai-bot-mouth"),
                        ],
                        id="ai-analyst-toggle",
                        n_clicks=0,
                        role="button",
                        tabIndex=0,
                        className="ai-analyst-fab",
                        **{"aria-label": "Abrir AI Analyst"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div([html.Strong("AI Analyst"), html.Small("read-only")], className="ai-analyst-title"),
                                    html.Div("Cerrar", id="ai-analyst-close", n_clicks=0, role="button", tabIndex=0, className="ai-analyst-close"),
                                ],
                                className="ai-analyst-head",
                            ),
                            html.P("Prepara paquetes reproducibles. Por defecto no llama modelos; Codex local solo se ejecuta con el boton explicito.", className="ai-analyst-copy"),
                            html.Div(
                                [
                                    html.Span("Tipo de analisis"),
                                    dcc.Dropdown(
                                        id="ai-analyst-context",
                                        options=ai_analyst_context_options(),
                                        value="screener_setup",
                                        clearable=False,
                                    ),
                                ],
                                className="ai-analyst-control",
                            ),
                            html.Div("Mercado se incluye siempre como contexto base", className="ai-analyst-context-note"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span("Estado del setup"),
                                            dcc.Dropdown(
                                                id="ai-analyst-setup-state",
                                                options=[
                                                    {"label": "Revisables", "value": "reviewable"},
                                                    {"label": "Watching", "value": "watching"},
                                                    {"label": "Todos", "value": "__all__"},
                                                ],
                                                value="reviewable",
                                                clearable=False,
                                            ),
                                        ],
                                        className="ai-analyst-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Span("Setup"),
                                            dcc.Dropdown(
                                                id="ai-analyst-setup-select",
                                                options=ai_analyst_setup_options(client_app_data.get("screener_setups_rows", [])),
                                                value=(ai_analyst_setup_options(client_app_data.get("screener_setups_rows", [])) or [{"value": ""}])[0]["value"],
                                                clearable=False,
                                            ),
                                        ],
                                        className="ai-analyst-control",
                                    ),
                                ],
                                id="ai-analyst-screener-controls",
                                className="ai-analyst-control-group",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span("Caso WeaveCount"),
                                            dcc.Dropdown(
                                                id="ai-analyst-wave-select",
                                                options=ai_analyst_wave_options(client_app_data.get("wavecount_rows", [])),
                                                value=(ai_analyst_wave_options(client_app_data.get("wavecount_rows", [])) or [{"value": ""}])[0]["value"],
                                                clearable=False,
                                            ),
                                        ],
                                        className="ai-analyst-control",
                                    ),
                                ],
                                id="ai-analyst-wave-controls",
                                className="ai-analyst-control-group hidden",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span("Par de correlacion"),
                                            dcc.Dropdown(
                                                id="ai-analyst-correlation-select",
                                                options=ai_analyst_correlation_options(client_app_data.get("correlation_pair_rows", [])),
                                                value=(ai_analyst_correlation_options(client_app_data.get("correlation_pair_rows", [])) or [{"value": ""}])[0]["value"],
                                                clearable=False,
                                            ),
                                        ],
                                        className="ai-analyst-control",
                                    ),
                                ],
                                id="ai-analyst-correlation-controls",
                                className="ai-analyst-control-group hidden",
                            ),
                            html.Div(
                                [
                                    html.Div("Se preparara un paquete global con radar, tendencia, volatilidad y manifest latest.", className="ai-analyst-context-note muted"),
                                ],
                                id="ai-analyst-market-controls",
                                className="ai-analyst-control-group hidden",
                            ),
                            html.Div(
                                [
                                    html.Div("Preparar paquete", id="ai-analyst-run", n_clicks=0, role="button", tabIndex=0, className="ai-analyst-run"),
                                    html.Div("Analizar con Codex local", id="ai-analyst-run-codex", n_clicks=0, role="button", tabIndex=0, className="ai-analyst-run codex"),
                                    html.Div("Codex + macro", id="ai-analyst-run-codex-macro", n_clicks=0, role="button", tabIndex=0, className="ai-analyst-run codex macro"),
                                    html.Div("Codex manual", className="ai-analyst-safe-pill"),
                                ],
                                className="ai-analyst-actions",
                            ),
                            html.Div(id="ai-analyst-progress", className="ai-analyst-progress"),
                            html.Div(id="ai-analyst-result", className="ai-analyst-result"),
                            dcc.Download(id="ai-analyst-report-download"),
                        ],
                        id="ai-analyst-panel",
                        className="ai-analyst-panel hidden",
                    ),
                ],
                className="ai-analyst-shell",
            ),
        ],
        className="app-shell",
    )


def dash_css() -> str:
    return """
:root {
  --surface: #07100f;
  --panel: #101819;
  --panel-strong: #172527;
  --ink: #e8f1ed;
  --muted: #8ea09c;
  --line: #294346;
  --teal: #5ce0ca;
  --cyan: #80d8ff;
  --amber: #d7a84b;
  --red: #e36d64;
  --green: #7bd88f;
  --space: 16px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px) 0 0 / 100% 4px,
    linear-gradient(90deg, rgba(128,216,255,.035) 1px, transparent 1px) 0 0 / 48px 48px,
    linear-gradient(145deg, #07100f, #101516 54%, #070b0c);
  color: var(--ink);
  font-family: "Bahnschrift", "Aptos", "Segoe UI", sans-serif;
}
.hoverlayer .hovertext path,
.hoverlayer .hovertext rect,
.js-plotly-plot .hoverlayer .hovertext path,
.js-plotly-plot .hoverlayer .hovertext rect,
.js-plotly-plot g.hovertext path,
.js-plotly-plot g.hovertext rect {
  fill: #0d1b1a !important;
  fill-opacity: 1 !important;
  stroke: #5ce0ca !important;
  stroke-opacity: .8 !important;
}
.hoverlayer .hovertext text,
.hoverlayer .hovertext tspan,
.js-plotly-plot .hoverlayer .hovertext text,
.js-plotly-plot .hoverlayer .hovertext tspan,
.js-plotly-plot g.hovertext text,
.js-plotly-plot g.hovertext tspan {
  fill: #f2fffb !important;
  text-shadow: none !important;
}
.app-shell { min-height: 100vh; display: grid; grid-template-columns: 250px minmax(0, 1fr); }
.sidebar {
  min-height: 100vh;
  padding: 24px;
  border-right: 1px solid var(--line);
  background: linear-gradient(180deg, #111c1e, #081010);
  position: sticky;
  top: 0;
}
.brand {
  display: grid;
  gap: 5px;
  padding: 4px 0 4px 14px;
  border-left: 3px solid var(--teal);
}
.brand strong { display: block; font-size: 26px; line-height: 1.05; }
.brand small, .subtitle { color: var(--muted); }
.brand small { font-size: 13px; }
.subtitle { margin: 18px 0 28px; font-size: 14px; font-weight: 650; }
.section-nav { margin: 10px 0 28px; }
.nav-title {
  color: var(--amber);
  font-size: 13px;
  font-weight: 750;
  margin-bottom: 12px;
}
.section-tabs {
  display: grid;
  gap: 10px;
}
.section-tabs .tab,
.section-tabs .section-tab {
  display: block !important;
  width: 100% !important;
  min-height: 56px !important;
  padding: 16px 16px !important;
  border: 1px solid var(--line) !important;
  border-left: 4px solid transparent !important;
  background: rgba(255,255,255,.032) !important;
  color: #d9e7e3 !important;
  text-align: left !important;
  font-size: 15px !important;
  font-weight: 760 !important;
  letter-spacing: 0 !important;
  border-radius: 2px !important;
  line-height: 1.35 !important;
}
.section-tabs .tab:hover,
.section-tabs .section-tab:hover {
  background: rgba(128,216,255,.075) !important;
  color: var(--ink) !important;
}
.section-tabs .tab--selected,
.section-tabs .section-tab-selected {
  border-left-color: var(--amber) !important;
  border-color: var(--line) !important;
  background: rgba(92,224,202,.11) !important;
  color: #ffffff !important;
}
.content { padding: 24px; max-width: 1680px; width: 100%; }
.topbar { display: flex; justify-content: space-between; gap: 20px; align-items: end; margin-bottom: 20px; border-bottom: 1px solid var(--line); padding-bottom: 18px; }
.refresh-status-shell { margin-left: auto; }
.refresh-status-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.refresh-pill {
  border: 1px solid rgba(92, 224, 202, 0.16);
  background: rgba(10, 24, 24, 0.88);
  color: var(--ink-soft);
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 11px;
  letter-spacing: 0;
  white-space: nowrap;
}
.refresh-pill.muted { color: var(--muted); }
.refresh-pill.ok {
  color: #7df0a4;
  border-color: rgba(104,226,143,.30);
  background: rgba(104,226,143,.045);
}
.refresh-pill.warning {
  color: var(--amber);
  border-color: rgba(215,168,75,.32);
  background: rgba(215,168,75,.045);
}
.refresh-pill.danger {
  color: #ff8a84;
  border-color: rgba(255,107,101,.36);
  background: rgba(255,107,101,.045);
}
.eyebrow { margin: 0 0 4px; color: var(--teal); font-size: 13px; font-weight: 720; }
h1 { margin: 0; font-size: 34px; line-height: 1.1; }
h2 { margin: 0 0 12px; font-size: 16px; }
.content-panel, .panel, .metric {
  border: 1px solid var(--line);
  background: rgba(16,24,25,.96);
  border-radius: 3px;
}
.content-panel { padding: 18px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 14px; margin-bottom: 18px; }
.metric { padding: 16px; min-height: 112px; display: grid; align-content: space-between; }
.metric-label { color: var(--muted); text-transform: uppercase; font-size: 11px; font-weight: 900; }
.metric strong { font-size: 30px; color: var(--teal); }
.metric small { color: var(--muted); }
.metric.locked strong { color: var(--green); }
.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
.radar-hero { display: grid; grid-template-columns: minmax(280px, 1.6fr) minmax(190px, .7fr) minmax(230px, .8fr); gap: 14px; margin-bottom: 14px; }
.pulse-card, .pulse-stat, .radar-section {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(18,30,31,.98), rgba(9,15,16,.98));
  border-radius: 2px;
}
.pulse-card { padding: 20px; min-height: 140px; display: grid; align-content: space-between; }
.pulse-card h2 { margin: 4px 0 10px; font-size: 30px; color: var(--teal); }
.pulse-card p { margin: 0; color: #c4d3cf; line-height: 1.5; max-width: 620px; }
.pulse-card.up h2, .pulse-stat.up strong { color: var(--green); }
.pulse-card.down h2, .pulse-stat.down strong { color: var(--red); }
.pulse-stat { padding: 18px; display: grid; align-content: space-between; min-height: 140px; }
.pulse-stat strong { color: var(--teal); font-size: 28px; line-height: 1.1; }
.pulse-stat.hot strong { color: var(--amber); }
.pulse-stat small { color: var(--muted); line-height: 1.35; }
.radar-kicker { color: var(--amber); font-size: 11px; text-transform: uppercase; font-weight: 900; }
.radar-dashboard-grid { display: grid; grid-template-columns: minmax(300px, .82fr) minmax(0, 1.18fr); gap: 14px; align-items: stretch; margin-bottom: 14px; }
.three { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
.panel { padding: 16px; min-width: 0; }
.radar-section { padding: 16px; min-width: 0; margin-bottom: 14px; }
.radar-dashboard-grid > .radar-section { height: 100%; margin-bottom: 0; }
.strength-stack { display: grid; gap: 12px; }
.strength-row { display: grid; gap: 7px; }
.strength-head, .strength-counts { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.strength-head strong { color: var(--ink); font-size: 14px; }
.strength-head span, .strength-counts { color: var(--muted); font-size: 12px; font-weight: 760; }
.strength-row.up .strength-head span { color: var(--green); }
.strength-row.down .strength-head span { color: var(--red); }
.strength-bar { display: flex; width: 100%; height: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.025); }
.strength-segment { min-width: 1px; }
.strength-segment.up { background: linear-gradient(90deg, rgba(123,216,143,.55), rgba(123,216,143,.92)); }
.strength-segment.down { background: linear-gradient(90deg, rgba(227,109,100,.9), rgba(227,109,100,.52)); }
.strength-segment.muted { background: rgba(142,160,156,.2); }
.vol-rank-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.vol-rank-panel { border-top: 1px solid rgba(41,67,70,.86); padding-top: 10px; min-width: 0; }
.rank-title { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.rank-title strong { color: var(--ink); font-size: 13px; }
.rank-title.hot strong { color: var(--amber); }
.rank-title.quiet strong { color: var(--cyan); }
.rank-title small { color: var(--muted); font-size: 11px; }
.vol-rank-list { display: grid; gap: 5px; }
.vol-rank-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) minmax(112px, .55fr);
  align-items: center;
  gap: 9px;
  min-height: 42px;
  padding: 7px 8px;
  border: 1px solid rgba(41,67,70,.74);
  background: rgba(8,13,14,.54);
}
.vol-rank-row.hot { border-left: 3px solid var(--amber); }
.vol-rank-row.quiet { border-left: 3px solid var(--cyan); }
.rank-number { color: var(--muted); font-size: 11px; font-weight: 920; }
.rank-symbol strong { display: block; color: var(--ink); font-size: 13px; overflow-wrap: anywhere; }
.rank-symbol small { display: block; color: var(--muted); font-size: 10px; margin-top: 1px; }
.rank-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; justify-items: end; }
.rank-metrics span { display: grid; gap: 1px; color: var(--muted); font-size: 10px; text-align: right; }
.rank-metrics b { color: var(--teal); font-size: 12px; }
.vol-rank-row.hot .rank-metrics b { color: var(--amber); }
.vol-rank-row.quiet .rank-metrics b { color: var(--cyan); }
.radar-insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: stretch;
  margin-bottom: 14px;
}
.radar-insight-grid > .radar-section { height: 100%; margin-bottom: 0; }
.reading-panel { min-height: 240px; }
.reading-list { display: grid; gap: 9px; }
.reading-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 86px;
  gap: 14px;
  align-items: center;
  min-height: 62px;
  padding: 10px 12px;
  border: 1px solid rgba(41,67,70,.78);
  background: rgba(8,13,14,.52);
}
.reading-copy strong { display: block; color: var(--ink); font-size: 13px; margin-bottom: 3px; }
.reading-copy small { display: block; color: var(--muted); font-size: 11px; line-height: 1.35; }
.reading-number { display: grid; justify-items: end; gap: 2px; }
.reading-number b { color: var(--muted); font-size: 26px; line-height: 1; }
.reading-number em { color: var(--muted); font-style: normal; font-size: 11px; font-weight: 900; }
.reading-number.up b { color: var(--green); }
.reading-number.down b { color: var(--red); }
.reading-number.hot b { color: var(--amber); }
.reading-number.quiet b { color: var(--cyan); }
.pressure-bar {
  display: flex;
  height: 18px;
  border: 1px solid rgba(41,67,70,.8);
  background: rgba(255,255,255,.025);
  overflow: hidden;
  margin: 4px 0 12px;
}
.pressure-segment { min-width: 1px; }
.pressure-segment.hot { background: linear-gradient(90deg, rgba(215,168,75,.72), rgba(215,168,75,.98)); }
.pressure-segment.normal { background: rgba(92,224,202,.34); }
.pressure-segment.quiet { background: rgba(128,216,255,.62); }
.asset-card-grid { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 10px; }
.asset-card { border: 1px solid rgba(41,67,70,.9); background: rgba(8,13,14,.72); padding: 12px; display: grid; gap: 11px; min-height: 142px; }
.asset-card.up { border-color: rgba(123,216,143,.42); }
.asset-card.down { border-color: rgba(227,109,100,.42); }
.asset-card-head { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 9px; align-items: start; }
.asset-card-head strong { display: block; color: var(--ink); overflow-wrap: anywhere; }
.asset-card-head small { display: block; color: var(--muted); font-size: 11px; margin-top: 2px; }
.asset-direction { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid var(--line); font-weight: 950; }
.asset-direction.up { color: var(--green); border-color: rgba(123,216,143,.5); background: rgba(123,216,143,.08); }
.asset-direction.down { color: var(--red); border-color: rgba(227,109,100,.5); background: rgba(227,109,100,.08); }
.tf-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
.tf-cell { border: 1px solid rgba(41,67,70,.85); background: rgba(255,255,255,.025); padding: 6px 4px; display: grid; place-items: center; gap: 2px; min-height: 42px; }
.tf-cell em { font-style: normal; color: var(--muted); font-size: 10px; }
.tf-cell b { color: var(--muted); font-size: 15px; line-height: 1; }
.tf-cell.up b { color: var(--green); }
.tf-cell.down b { color: var(--red); }
.asset-card-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; border-top: 1px solid rgba(41,67,70,.72); padding-top: 9px; }
.mini-label { color: var(--muted); font-size: 11px; font-weight: 900; }
.radar-empty { color: var(--muted); border: 1px dashed rgba(142,160,156,.34); padding: 16px; font-size: 13px; background: rgba(255,255,255,.02); }
.screener-shell, .screener-hero {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(18,30,31,.96), rgba(7,16,15,.94));
  padding: 16px;
  margin-bottom: 14px;
}
.screener-hero {
  display: grid;
  grid-template-columns: minmax(260px, .75fr) minmax(0, 1.25fr);
  gap: 18px;
  align-items: start;
}
.screener-stat-grid { display: grid; grid-template-columns: minmax(120px, 180px); gap: 8px; }
.screener-stat {
  border: 1px solid rgba(41,67,70,.85);
  background: rgba(255,255,255,.025);
  padding: 10px;
  display: grid;
  gap: 4px;
}
.screener-stat strong { color: var(--teal); font-size: 24px; line-height: 1; }
.screener-stat small { color: var(--muted); font-size: 11px; font-weight: 820; }
.screener-toolbar { grid-template-columns: minmax(190px, 1.2fr) repeat(6, minmax(118px, .62fr)); }
.screener-signal-list {
  display: grid;
  gap: 2px;
  margin-bottom: 14px;
  border-top: 1px solid rgba(41,67,70,.72);
  border-bottom: 1px solid rgba(41,67,70,.72);
}
.screener-signal-row {
  border: 1px solid rgba(41,67,70,.9);
  border-left-width: 3px;
  background: rgba(6,13,14,.72);
  padding: 7px 9px;
  min-height: 42px;
  display: grid;
  grid-template-columns: 52px minmax(140px, .75fr) minmax(220px, 1fr) minmax(180px, 1fr) minmax(120px, auto);
  gap: 9px;
  align-items: center;
  cursor: pointer;
}
.screener-signal-row:hover {
  border-color: rgba(92,224,202,.72);
  background: rgba(18,31,32,.96);
}
.screener-signal-row.up { border-left-color: var(--green); }
.screener-signal-row.down { border-left-color: var(--red); }
.screener-row-asset { display: grid; gap: 1px; min-width: 0; }
.screener-row-asset strong { display: block; color: var(--ink); font-size: 16px; overflow-wrap: anywhere; line-height: 1.05; }
.screener-row-asset small { display: block; color: var(--muted); font-size: 10px; font-weight: 820; }
.screener-row-main { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; min-width: 0; }
.screener-row-chips { display: flex; flex-wrap: wrap; gap: 5px; min-width: 0; }
.screener-row-end { display: flex; gap: 7px; align-items: center; justify-content: flex-end; min-width: 0; }
.screener-score {
  width: 44px;
  min-width: 44px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(92,224,202,.52);
  color: var(--teal);
  background: rgba(92,224,202,.08);
  font-weight: 950;
  font-size: 14px;
}
.screener-score.up { border-color: rgba(123,216,143,.58); color: var(--green); background: rgba(123,216,143,.08); }
.screener-score.down { border-color: rgba(227,109,100,.58); color: var(--red); background: rgba(227,109,100,.08); }
.screener-setup-name { color: var(--ink); font-size: 11px; font-weight: 900; text-transform: uppercase; }
.screener-mini-context { color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
.shadow-hero,
.shadow-shell {
  border: 1px solid rgba(92,224,202,.28);
  background: rgba(11,25,24,.82);
  padding: 18px;
  margin-bottom: 14px;
}
.shadow-stat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.shadow-stat {
  border: 1px solid rgba(92,224,202,.24);
  background: rgba(2,12,12,.72);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.shadow-stat strong {
  color: var(--accent);
  font-size: 24px;
  line-height: 1;
}
.shadow-stat small,
.shadow-row-asset small { color: var(--muted); }
.shadow-safety-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.shadow-safety-chip,
.shadow-row-pill,
.shadow-state-pill {
  border: 1px solid rgba(92,224,202,.24);
  background: rgba(2,12,12,.68);
  color: var(--text);
  padding: 7px 9px;
  font-size: 12px;
  font-weight: 800;
}
.shadow-state-pill.candidate {
  color: var(--warn);
  border-color: rgba(215,168,75,.70);
}
.shadow-state-pill.muted,
.shadow-row-pill.muted { color: var(--muted); }
.shadow-state-pill.down {
  color: var(--red);
  border-color: rgba(255,107,107,.55);
}
.shadow-decision-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.shadow-decision-row {
  display: grid;
  grid-template-columns: minmax(170px, .9fr) minmax(260px, 1.1fr) minmax(260px, 1.4fr) auto;
  align-items: center;
  gap: 12px;
  border: 1px solid rgba(92,224,202,.18);
  background: rgba(5,17,17,.72);
  padding: 12px;
}
.shadow-decision-row.candidate { border-color: rgba(215,168,75,.42); }
.shadow-row-asset {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.shadow-row-asset strong { font-size: 18px; }
.shadow-row-main,
.shadow-row-end {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.shadow-row-reason {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.35;
}
.screener-status {
  border: 1px solid rgba(215,168,75,.45);
  color: var(--amber);
  padding: 4px 6px;
  font-size: 10px;
  font-weight: 820;
  justify-self: end;
  white-space: nowrap;
}
.screener-chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.screener-chip {
  border: 1px solid rgba(41,67,70,.88);
  background: rgba(255,255,255,.025);
  color: var(--teal);
  padding: 3px 6px;
  font-size: 10px;
  font-weight: 820;
}
.screener-row-pill {
  border: 1px solid rgba(92,224,202,.35);
  color: var(--teal);
  padding: 3px 6px;
  font-size: 10px;
  font-weight: 850;
}
.screener-row-pill.muted { border-color: rgba(166,211,202,.22); color: var(--muted); }
.screener-chip.muted { color: var(--muted); }
.screener-chip.risk { color: var(--amber); border-color: rgba(215,168,75,.38); }
.screener-modal-summary {
  color: #c5d4d0;
  border: 1px solid rgba(41,67,70,.8);
  background: rgba(255,255,255,.022);
  padding: 10px;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.4;
}
.screener-modal-panel {
  width: min(1380px, 94vw) !important;
}
.screener-modal-info-stack {
  display: grid;
  grid-template-columns: 1.25fr .9fr .85fr 1fr;
  gap: 7px;
  margin: 7px 0 8px;
}
.screener-modal-info-card {
  border: 1px solid rgba(41,67,70,.8);
  background: rgba(255,255,255,.02);
  padding: 8px 9px;
  display: grid;
  align-content: start;
  gap: 5px;
}
.screener-modal-info-card.primary {
  border-color: rgba(92,224,202,.42);
  background: rgba(92,224,202,.045);
}
.screener-modal-info-card h3 {
  margin: 0;
  color: var(--teal);
  font-size: 11px;
  text-transform: uppercase;
}
.screener-modal-info-card p {
  margin: 0;
  color: #c5d4d0;
  font-size: 11px;
  line-height: 1.28;
}
.screener-reviewed-chart-wrap {
  margin-top: 18px;
  border: 1px solid rgba(83, 229, 215, .28);
  background: #050909;
  padding: 10px;
}
.screener-reviewed-chart-image {
  display: block;
  width: 100%;
  max-height: 88vh;
  object-fit: contain;
  background: #050909;
}
.screener-layer-control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  padding: 7px 9px;
  border: 1px solid rgba(92,224,202,.24);
  background: rgba(8,18,17,.76);
}
.screener-layer-control-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.screener-layer-label {
  color: var(--muted);
  font-size: 10px;
  font-weight: 920;
  text-transform: uppercase;
}
.screener-layer-toggle,
.screener-fib-mode-toggle {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.screener-layer-toggle .dash-options-list-option,
.screener-fib-mode-toggle .dash-options-list-option {
  display: inline-flex;
  align-items: center;
  min-height: 25px;
  padding: 4px 7px;
  border: 1px solid rgba(92,224,202,.28);
  background: #07100f;
  color: var(--ink);
  font-size: 10px;
  font-weight: 880;
  cursor: pointer;
}
.screener-layer-toggle .dash-options-list-option:hover,
.screener-fib-mode-toggle .dash-options-list-option:hover {
  border-color: rgba(92,224,202,.62);
}
.screener-layer-toggle .dash-options-list-option.selected,
.screener-fib-mode-toggle .dash-options-list-option.selected {
  border-color: rgba(92,224,202,.72);
  color: var(--teal);
  background: rgba(92,224,202,.10);
}
.screener-layer-option {
  display: inline-flex;
  align-items: center;
}
.screener-layer-toggle .dash-options-list-option-wrapper,
.screener-fib-mode-toggle .dash-options-list-option-wrapper {
  display: none;
}
.screener-layer-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}
.screener-context-block {
  display: grid;
  gap: 7px;
  margin: 0;
}
.screener-context-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}
.screener-trend-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.screener-trend-chip {
  border: 1px solid rgba(41,67,70,.88);
  background: rgba(255,255,255,.025);
  color: var(--muted);
  padding: 5px 7px;
  font-size: 11px;
  font-weight: 850;
}
.screener-trend-chip.up {
  border-color: rgba(104,226,143,.42);
  color: #7df0a4;
}
.screener-trend-chip.down {
  border-color: rgba(255,107,101,.42);
  color: #ff8a84;
}
.ai-analyst-shell {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 60;
  pointer-events: none;
}
.ai-analyst-fab {
  pointer-events: auto;
  width: 58px;
  height: 58px;
  position: relative;
  display: grid;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(92,224,202,.82);
  border-radius: 50%;
  background:
    radial-gradient(circle at 34% 25%, rgba(92,224,202,.20), transparent 34%),
    linear-gradient(145deg, #0b1716 0%, #050909 68%);
  color: var(--teal);
  font-weight: 950;
  cursor: pointer;
  box-shadow:
    0 16px 34px rgba(0,0,0,.40),
    0 0 0 5px rgba(92,224,202,.055),
    inset 0 0 18px rgba(92,224,202,.08);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease, background .16s ease;
}
.ai-analyst-fab:hover,
.ai-analyst-fab:focus-visible {
  transform: translateY(-2px);
  border-color: rgba(92,224,202,1);
  box-shadow:
    0 20px 42px rgba(0,0,0,.48),
    0 0 0 6px rgba(92,224,202,.085),
    0 0 24px rgba(92,224,202,.16),
    inset 0 0 20px rgba(92,224,202,.11);
  outline: none;
}
.ai-bot-antenna {
  position: absolute;
  top: 8px;
  left: 50%;
  width: 11px;
  height: 11px;
  transform: translateX(-50%);
  border: 1px solid rgba(215,168,75,.95);
  border-radius: 50%;
  background: rgba(215,168,75,.18);
  box-shadow: 0 0 10px rgba(215,168,75,.20);
}
.ai-bot-antenna::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 10px;
  width: 1px;
  height: 8px;
  background: rgba(215,168,75,.70);
  transform: translateX(-50%);
}
.ai-bot-face {
  width: 34px;
  height: 26px;
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid rgba(92,224,202,.80);
  border-radius: 10px;
  background: rgba(92,224,202,.065);
  box-shadow: inset 0 0 16px rgba(92,224,202,.10);
}
.ai-bot-eye {
  width: 6px;
  height: 8px;
  border-radius: 999px;
  background: #5ce0ca;
  box-shadow: 0 0 8px rgba(92,224,202,.72);
}
.ai-bot-mouth {
  position: absolute;
  bottom: 13px;
  left: 50%;
  width: 15px;
  height: 2px;
  transform: translateX(-50%);
  background: rgba(215,168,75,.80);
  box-shadow: 0 0 8px rgba(215,168,75,.25);
}
.ai-analyst-panel {
  pointer-events: auto;
  position: absolute;
  right: 0;
  bottom: 68px;
  width: min(380px, calc(100vw - 30px));
  display: grid;
  gap: 12px;
  border: 1px solid rgba(92,224,202,.36);
  background: rgba(7,16,15,.98);
  padding: 14px;
  box-shadow: 0 18px 42px rgba(0,0,0,.44);
}
.ai-analyst-panel.hidden { display: none; }
.ai-analyst-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.ai-analyst-title {
  display: grid;
  gap: 2px;
  color: var(--ink);
}
.ai-analyst-title small {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0;
}
.ai-analyst-close,
.ai-analyst-run,
.ai-analyst-safe-pill {
  border: 1px solid rgba(92,224,202,.28);
  background: #07100f;
  color: var(--ink);
  padding: 8px 10px;
  font-size: 11px;
  font-weight: 900;
}
.ai-analyst-close,
.ai-analyst-run { cursor: pointer; }
.ai-analyst-run {
  color: var(--teal);
  border-color: rgba(92,224,202,.58);
}
.ai-analyst-run.disabled {
  opacity: .42;
  pointer-events: none;
  cursor: wait;
}
.ai-analyst-safe-pill {
  color: var(--amber);
  border-color: rgba(215,168,75,.38);
}
.ai-analyst-copy {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}
.ai-analyst-control {
  display: grid;
  gap: 6px;
}
.ai-analyst-control-group {
  display: grid;
  gap: 12px;
}
.ai-analyst-control label {
  color: var(--muted);
  font-size: 10px;
  font-weight: 920;
  text-transform: uppercase;
}
.ai-analyst-context-note {
  border: 1px solid rgba(215,168,75,.24);
  background: rgba(215,168,75,.045);
  color: var(--amber);
  padding: 7px 9px;
  font-size: 11px;
  font-weight: 850;
}
.ai-analyst-context-note.muted {
  border-color: rgba(166,211,202,.22);
  background: rgba(166,211,202,.035);
  color: var(--muted);
  line-height: 1.35;
}
.ai-analyst-control .Select-control,
.ai-analyst-control .Select-menu-outer {
  background: #07100f !important;
  border-color: rgba(92,224,202,.28) !important;
  color: var(--ink) !important;
}
.ai-analyst-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ai-analyst-progress {
  min-height: 18px;
  color: var(--amber);
  font-size: 11px;
  font-weight: 850;
}
.ai-analyst-result-card {
  display: grid;
  gap: 6px;
  border: 1px solid rgba(92,224,202,.28);
  background: rgba(92,224,202,.035);
  padding: 10px;
  color: #c5d4d0;
  font-size: 12px;
  line-height: 1.35;
}
.ai-analyst-result-card.warning {
  border-color: rgba(215,168,75,.46);
  background: rgba(215,168,75,.045);
}
.ai-analyst-result-card strong { color: var(--ink); }
.ai-analyst-download {
  width: fit-content;
  border: 1px solid rgba(92,224,202,.58);
  color: var(--teal);
  padding: 7px 9px;
  font-size: 11px;
  font-weight: 900;
  cursor: pointer;
}
.panel-heading { display: grid; gap: 4px; margin-bottom: 12px; }
.panel-heading h2 { margin: 0; }
.panel-heading p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.45; }
.panel-heading-title-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  border: 0;
  padding: 0;
  clip: rect(0, 0, 0, 0);
  clip-path: inset(50%);
  overflow: hidden;
  white-space: nowrap;
}
.info-icon {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #ffffff;
  background: radial-gradient(circle at 30% 30%, #8cc6ff, #3776ff 44%, #103ca5 100%);
  border: 1px solid #9fd1ff;
  font-size: 12px;
  font-weight: 900;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.28), 0 0 0 1px rgba(57, 123, 255, 0.52), 0 0 12px rgba(37, 98, 255, 0.55), 0 0 0 3px rgba(5, 17, 47, 0.65);
  line-height: 1;
  position: relative;
  cursor: help;
  transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease, border-color 0.16s ease;
}
.info-icon:hover {
  transform: translateY(-1px) scale(1.06);
  background: radial-gradient(circle at 30% 30%, #b0dcff, #4b89ff 44%, #2258ce 100%);
  border-color: #cde4ff;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.36), 0 0 0 1px rgba(90, 153, 255, 0.72), 0 0 18px rgba(118, 176, 255, 0.65), 0 0 0 3px rgba(8, 25, 63, 0.8);
}
.info-icon::after {
  content: attr(title);
  position: absolute;
  left: 50%;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  width: min(320px, 32vw);
  max-width: 320px;
  white-space: normal;
  padding: 8px 10px;
  border: 1px solid rgba(124, 186, 255, 0.55);
  border-radius: 7px;
  background: #0a1630;
  color: #edf7f3;
  font-size: 12px;
  line-height: 1.35;
  box-shadow: 0 8px 18px rgba(8, 16, 35, 0.55);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  z-index: 20;
}
.info-icon:hover::after { opacity: 1; visibility: visible; }
.info-icon::before {
  content: "";
  position: absolute;
  left: 50%;
  bottom: 100%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid #0a1630;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}
.info-icon:hover::before { opacity: 1; visibility: visible; }
.wave-hero {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(18,30,31,.98), rgba(9,15,16,.98));
  padding: 16px;
  margin-bottom: 14px;
}
.wave-count-tabs {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}
.wave-count-tabs .tab,
.wave-count-tabs .wave-count-tab {
  min-height: 76px !important;
  padding: 16px 14px !important;
  border: 1px solid rgba(41,67,70,.95) !important;
  background: rgba(255,255,255,.025) !important;
  color: #d9e7e3 !important;
  border-radius: 2px !important;
  font-size: 16px !important;
  font-weight: 880 !important;
  text-align: left !important;
  display: flex !important;
  align-items: center !important;
}
.wave-count-tabs .tab:hover,
.wave-count-tabs .wave-count-tab:hover {
  border-color: rgba(92,224,202,.55) !important;
  background: rgba(92,224,202,.07) !important;
}
.wave-count-tabs .tab--selected,
.wave-count-tabs .wave-count-tab-selected {
  color: #ffffff !important;
  border-color: rgba(92,224,202,.72) !important;
  background: linear-gradient(180deg, rgba(92,224,202,.16), rgba(92,224,202,.07)) !important;
  box-shadow: inset 0 -3px 0 rgba(92,224,202,.55);
}
.wave-toolbar { grid-template-columns: minmax(220px, 1.4fr) repeat(4, minmax(130px, .55fr)); }
.wave-group-stack {
  display: grid;
  gap: 12px;
}
.wave-case-group {
  border: 1px solid rgba(41,67,70,.82);
  background: rgba(6,13,14,.38);
  padding: 10px;
}
.wave-case-group.candidate {
  border-color: rgba(215,168,75,.34);
  background: rgba(215,168,75,.035);
}
.wave-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 9px;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0;
}
.wave-group-head strong { color: var(--ink); }
.wave-group-head.candidate strong { color: var(--amber); }
.wave-group-head span {
  border: 1px solid rgba(41,67,70,.9);
  padding: 3px 8px;
  color: var(--muted);
}
.wave-group-empty {
  color: var(--muted);
  font-size: 12px;
  border: 1px dashed rgba(142,160,156,.22);
  padding: 10px;
}
.wave-horizontal-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  overflow: visible;
  padding: 2px 2px 10px;
}
.wave-case-item {
  flex: 0 1 245px;
  max-width: 100%;
  border: 1px solid rgba(41,67,70,.9);
  background: rgba(6,13,14,.92);
  padding: 8px 10px;
  min-height: 52px;
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  white-space: nowrap;
}
.wave-case-item:hover {
  border-color: rgba(92,224,202,.65);
  background: rgba(23,39,40,.98);
}
.wave-case-item.candidate {
  border-color: rgba(215,168,75,.45);
  background: rgba(16,13,8,.72);
}
.wave-case-item.candidate:hover {
  border-color: rgba(215,168,75,.78);
  background: rgba(29,22,10,.92);
}
.wave-case-item strong { color: var(--ink); font-size: 16px; }
.wave-number-badge {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(92,224,202,.52);
  color: var(--teal);
  background: rgba(92,224,202,.08);
  font-weight: 950;
}
.wave-number-badge.down {
  border-color: rgba(255,107,101,.58);
  color: #ff8a84;
  background: rgba(255,107,101,.08);
}
.wave-number-badge.up {
  border-color: rgba(104,226,143,.58);
  color: #7df0a4;
  background: rgba(104,226,143,.08);
}
.wave-number-badge.candidate,
.wave-modal-wave.candidate {
  border-color: rgba(215,168,75,.72);
  color: var(--amber);
  background: rgba(215,168,75,.10);
}
.wave-case-tf {
  color: var(--muted);
  font-family: Consolas, monospace;
  font-size: 12px;
  font-weight: 850;
}
.wave-case-pill {
  border: 1px solid rgba(41,67,70,.88);
  background: rgba(255,255,255,.025);
  color: var(--teal);
  padding: 5px 7px;
  font-size: 10px;
  font-weight: 820;
}
.wave-case-pill.down,
.wave-direction-pill.down {
  border-color: rgba(255,107,101,.42);
  color: #ff8a84;
}
.wave-case-pill.up,
.wave-direction-pill.up {
  border-color: rgba(104,226,143,.42);
  color: #7df0a4;
}
.wave-case-status {
  border: 1px solid rgba(41,67,70,.88);
  background: rgba(255,255,255,.025);
  color: var(--muted);
  padding: 5px 7px;
  font-size: 10px;
  font-weight: 820;
}
.wave-case-status.active,
.wave-direction-pill.active {
  border-color: rgba(104,226,143,.42);
  color: #7df0a4;
}
.wave-case-status.candidate,
.wave-direction-pill.candidate {
  border-color: rgba(215,168,75,.55);
  color: var(--amber);
  background: rgba(215,168,75,.08);
}
.wave-case-quality {
  border: 1px solid rgba(41,67,70,.88);
  background: rgba(255,255,255,.025);
  color: var(--muted);
  padding: 5px 7px;
  font-size: 10px;
  font-weight: 820;
}
.wave-case-quality.fuerte,
.wave-direction-pill.quality.fuerte {
  border-color: rgba(104,226,143,.42);
  color: #7df0a4;
}
.wave-case-quality.media,
.wave-direction-pill.quality.media {
  border-color: rgba(215,168,75,.52);
  color: var(--amber);
}
.wave-case-quality.debil,
.wave-direction-pill.quality.debil {
  border-color: rgba(142,160,156,.34);
  color: var(--muted);
}
.wave-modal.hidden { display: none; }
.wave-modal {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
}
.wave-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(1,6,7,.78);
  backdrop-filter: blur(4px);
}
.wave-modal-panel {
  position: relative;
  z-index: 1;
  width: min(1180px, 94vw);
  max-height: 92vh;
  overflow: auto;
  border: 1px solid rgba(92,224,202,.55);
  background: linear-gradient(180deg, #101819, #07100f);
  box-shadow: 0 24px 80px rgba(0,0,0,.55);
  padding: 14px;
}
.wave-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(41,67,70,.86);
}
.wave-modal-title { display: flex; align-items: center; gap: 10px; }
.wave-modal-title strong { display: block; color: var(--ink); font-size: 22px; }
.wave-modal-title small { display: block; color: var(--muted); font-size: 12px; }
.wave-modal-wave {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(92,224,202,.6);
  color: var(--teal);
  font-weight: 950;
}
.wave-modal-close {
  border: 1px solid rgba(215,168,75,.58);
  color: var(--amber);
  padding: 9px 12px;
  font-weight: 850;
  cursor: pointer;
}
.wave-modal-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}
.wave-modal-meta.compact {
  gap: 6px;
  margin: 6px 0 7px;
}
.wave-modal-meta span {
  border: 1px solid rgba(41,67,70,.88);
  background: rgba(255,255,255,.025);
  color: var(--muted);
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 820;
}
.wave-modal-meta.compact span {
  padding: 4px 7px;
  font-size: 10px;
}
.wave-direction-pill.muted {
  color: var(--muted);
  border-color: rgba(41,67,70,.72);
  background: rgba(255,255,255,.018);
}
.screener-chip-row.compact {
  gap: 4px;
}
.screener-chip-row.compact .screener-chip {
  padding: 4px 6px;
  font-size: 9px;
}
.wave-modal-chart {
  display: block;
  width: 100%;
  max-height: 72vh;
  object-fit: contain;
  background: #050909;
  border: 1px solid rgba(41,67,70,.86);
}
.wave-modal-graph {
  width: 100%;
  background: #050909;
  border: 1px solid rgba(41,67,70,.86);
}
.screener-setup-graph {
  min-height: 860px;
}
.wave-modal-graph .legend text {
  fill: #d4ebe4 !important;
}
.correlation-shell { display: grid; gap: 14px; }
.correlation-head {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(18,30,31,.98), rgba(9,15,16,.98));
  padding: 16px;
}
.correlation-controls { display: grid; grid-template-columns: .65fr 1fr 1fr .75fr; gap: 12px; }
.matrix-assets-cell { grid-column: 1 / -1; }
.control-cell { display: grid; gap: 7px; min-width: 0; }
.control-cell > span { color: var(--muted); font-size: 11px; font-weight: 900; text-transform: uppercase; }
.mini-tabs { display: flex; gap: 8px; margin-bottom: 4px; }
.mini-tabs .tab,
.mini-tabs .mini-tab {
  min-height: 42px !important;
  padding: 11px 16px !important;
  border: 1px solid var(--line) !important;
  background: rgba(255,255,255,.025) !important;
  color: var(--muted) !important;
  font-weight: 800 !important;
  border-radius: 2px !important;
}
.mini-tabs .tab--selected,
.mini-tabs .mini-tab-selected {
  color: var(--ink) !important;
  border-color: rgba(92,224,202,.5) !important;
  background: rgba(92,224,202,.10) !important;
}
.correlation-panel { min-height: 260px; }
.correlation-context {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: baseline;
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(41,67,70,.78);
  background: rgba(8,13,14,.52);
}
.correlation-context strong { color: var(--teal); font-size: 16px; }
.correlation-context span { color: var(--muted); font-size: 12px; line-height: 1.4; }
.corr-board { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: start; }
.corr-focus-grid { display: grid; grid-template-columns: minmax(280px, .55fr) minmax(0, 1.45fr); gap: 12px; margin-bottom: 12px; align-items: stretch; }
.pair-metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
.pair-metric-grid .metric { min-height: 88px; padding: 12px; }
.pair-metric-grid .metric strong { font-size: 24px; }
.pair-metric-grid .metric.obs-wide { grid-column: span 2; }
.rolling-chart-panel { margin-bottom: 12px; }
.rolling-metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; margin: 10px 0 12px; }
.rolling-metric-grid .metric { min-height: 78px; padding: 11px; }
.rolling-metric-grid .metric strong { font-size: 22px; }
.metric.up strong { color: var(--green); }
.metric.down strong { color: var(--red); }
.metric.hot strong { color: var(--amber); }
.metric.quiet strong { color: var(--cyan); }
.corr-panel {
  border: 1px solid var(--line);
  background: rgba(8,13,14,.58);
  padding: 12px;
  min-width: 0;
}
.corr-visual-panel { min-height: 488px; }
.pair-focus-card { min-height: 488px; }
.corr-matrix-panel { margin-bottom: 12px; }
.matrix-head { display: flex; justify-content: space-between; gap: 12px; align-items: end; margin-bottom: 8px; }
.corr-graph { width: 100%; }
.corr-rank-list { display: grid; gap: 6px; }
.corr-rank-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) minmax(112px, .55fr);
  align-items: center;
  gap: 9px;
  min-height: 44px;
  padding: 7px 8px;
  border: 1px solid rgba(41,67,70,.74);
  background: rgba(255,255,255,.022);
}
.corr-rank-row.up { border-left: 3px solid var(--green); }
.corr-rank-row.down { border-left: 3px solid var(--red); }
.corr-rank-row.hot { border-left: 3px solid var(--amber); }
.corr-rank-row.quiet { border-left: 3px solid var(--cyan); }
.corr-value.up { color: var(--green); }
.corr-value.down { color: var(--red); }
.corr-value.hot { color: var(--amber); }
.corr-value.quiet { color: var(--cyan); }
.corr-method-note { color: #c4d3cf; line-height: 1.5; font-size: 13px; }
.tf-arrow { font-weight: 950; color: var(--muted); }
.tf-arrow.up { color: var(--green); }
.tf-arrow.down { color: var(--red); }
.rsi-value { font-weight: 900; color: #dfe9e6; }
.rsi-value.high { color: var(--green); }
.rsi-value.low { color: var(--red); }
.toolbar { display: grid; grid-template-columns: 1.5fr 1fr 1fr; gap: 12px; margin-bottom: 14px; }
input, .Select-control, .Select-menu-outer {
  background: #0b1213 !important;
  color: var(--ink) !important;
  border: 1px solid var(--line) !important;
  border-radius: 2px !important;
}
input { width: 100%; padding: 10px 12px; }
input:focus,
.Select.is-focused > .Select-control,
.Select-control:focus,
.Select-control:focus-within,
.dash-dropdown:focus,
.dash-dropdown:focus-within {
  border-color: rgba(92,224,202,.72) !important;
  box-shadow: 0 0 0 1px rgba(92,224,202,.28) !important;
  outline: none !important;
}
.Select-input > input:focus,
.dash-dropdown-search:focus {
  box-shadow: none !important;
  outline: none !important;
}
.Select-menu-outer {
  box-shadow: 0 18px 38px rgba(0,0,0,.55) !important;
  z-index: 9999 !important;
}
.Select-menu, .Select-option, .VirtualizedSelectOption {
  background: #0b1213 !important;
  color: var(--ink) !important;
}
.Select-option,
.VirtualizedSelectOption {
  border-bottom: 1px solid rgba(41,67,70,.65) !important;
  font-weight: 760;
}
.Select-option.is-focused,
.Select-option.is-selected,
.VirtualizedSelectFocusedOption {
  background: rgba(92,224,202,.12) !important;
  color: #f2fff9 !important;
}
.Select-input,
.Select-input > input {
  background: #050909 !important;
  color: var(--ink) !important;
}
.Select-input > input::placeholder { color: var(--muted) !important; }
.Select-value-label, .Select-placeholder, .VirtualizedSelectOption { color: var(--ink) !important; }
.Select--multi .Select-value {
  background: rgba(92,224,202,.10) !important;
  border: 1px solid rgba(92,224,202,.34) !important;
  color: var(--ink) !important;
}
.Select--multi .Select-value-icon {
  border-right: 1px solid rgba(92,224,202,.30) !important;
  color: var(--muted) !important;
}
.Select--multi .Select-value-icon:hover {
  background: rgba(255,107,101,.14) !important;
  color: var(--red) !important;
}
.Select-clear-zone, .Select-arrow-zone, .Select-arrow { color: var(--muted) !important; border-top-color: var(--muted) !important; }
.Select-menu-outer ::-webkit-scrollbar { width: 12px; }
.Select-menu-outer ::-webkit-scrollbar-track { background: #07100f; }
.Select-menu-outer ::-webkit-scrollbar-thumb { background: rgba(92,224,202,.36); border: 2px solid #07100f; }
button.dash-dropdown,
.dash-dropdown {
  width: 100%;
  min-height: 38px;
  background: #0b1213 !important;
  color: var(--ink) !important;
  border: 1px solid var(--line) !important;
  border-radius: 2px !important;
  font-weight: 760 !important;
}
.dash-dropdown-value,
.dash-dropdown-value-item,
.dash-dropdown-value-count,
.dash-dropdown-trigger-icon { color: var(--ink) !important; }
.dash-dropdown-value-count { color: var(--teal) !important; }
.dash-dropdown:hover { border-color: rgba(92,224,202,.55) !important; }
.dash-dropdown-content {
  background: #0b1213 !important;
  color: var(--ink) !important;
  border: 1px solid rgba(92,224,202,.45) !important;
  border-radius: 2px !important;
  box-shadow: 0 20px 42px rgba(0,0,0,.62) !important;
}
.dash-dropdown-search-container {
  background: #07100f !important;
  border-color: rgba(92,224,202,.52) !important;
}
.dash-dropdown-search {
  background: #050909 !important;
  color: var(--ink) !important;
  border-color: rgba(92,224,202,.42) !important;
}
.dash-dropdown-actions {
  background: #0b1213 !important;
  color: var(--teal) !important;
  border-bottom: 1px solid rgba(41,67,70,.72) !important;
}
.dash-dropdown-actions,
.dash-dropdown-actions * {
  color: var(--teal) !important;
}
.dash-options-list,
.dash-dropdown-options {
  background: #0b1213 !important;
  color: var(--ink) !important;
}
.dash-dropdown-option {
  background: #0b1213 !important;
  color: var(--ink) !important;
  border-bottom: 1px solid rgba(41,67,70,.58) !important;
  font-weight: 760 !important;
}
.dash-dropdown-option:hover,
.dash-dropdown-option[aria-selected="true"],
.dash-dropdown-option.selected {
  background: rgba(92,224,202,.12) !important;
  color: #f2fff9 !important;
}
.dash-dropdown-option input[type="checkbox"],
.dash-dropdown-option input[type="radio"] { accent-color: var(--teal); }
.dash-dropdown-content ::-webkit-scrollbar { width: 12px; }
.dash-dropdown-content ::-webkit-scrollbar-track { background: #07100f; }
.dash-dropdown-content ::-webkit-scrollbar-thumb { background: rgba(92,224,202,.36); border: 2px solid #07100f; }
.notice { padding: 12px; border: 1px solid var(--line); margin-bottom: 14px; }
.notice strong { margin-right: 6px; }
.notice.info { border-color: rgba(128,216,255,.42); color: var(--cyan); background: rgba(128,216,255,.06); }
.notice.warning { border-color: rgba(215,168,75,.5); color: var(--amber); background: rgba(215,168,75,.07); }
.compact-list { margin: 0; padding-left: 18px; color: #d8e5e1; }
@media (max-width: 980px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { min-height: auto; position: relative; }
  .topbar, .split, .radar-hero, .radar-dashboard-grid, .radar-insight-grid, .three, .toolbar, .screener-hero, .screener-toolbar, .screener-signal-row, .screener-modal-info-stack, .correlation-controls, .corr-board, .corr-focus-grid, .wave-toolbar, .shadow-stat-grid, .shadow-decision-row { grid-template-columns: 1fr; display: grid; }
  .asset-card-grid, .vol-rank-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric-grid, .pair-metric-grid, .rolling-metric-grid, .wave-count-tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .wave-case-item { flex-basis: 220px; }
}
@media (max-width: 620px) {
  .content { padding: 12px; }
  .metric-grid, .asset-card-grid, .vol-rank-grid, .reading-row, .pair-metric-grid, .rolling-metric-grid, .wave-count-tabs { grid-template-columns: 1fr; }
  .pair-metric-grid .metric.obs-wide { grid-column: auto; }
  .vol-rank-row, .corr-rank-row { grid-template-columns: 30px minmax(0, 1fr); }
  .correlation-context { display: grid; }
  .rank-metrics { grid-column: 2; justify-items: start; }
  .reading-number { justify-items: start; }
  .rank-metrics span { text-align: left; }
  .wave-case-item { flex-basis: 100%; }
  .wave-modal { padding: 10px; }
  h1 { font-size: 26px; }
}
"""
