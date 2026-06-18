from __future__ import annotations

import re
from typing import Any

from trading_center.dashboard.formatting import get_value, safe_float


WAVECOUNT_NUMBERS = ("1", "2", "3", "4", "5")
WAVECOUNT_QUALITY_ORDER = ("fuerte", "media", "debil")
WAVECOUNT_CASE_TYPE_PRIORITY = {
    "weavecount_screener_h1_h4_v1": 0,
    "current_screener_row": 0,
    "state_machine_late_or_invalidated_context": 1,
    "cycle_reset_case": 2,
    "persistent_latest_case": 3,
    "progressive_cut_forming": 4,
    "progressive_cut_provisional": 5,
    "progressive_cut_confirmed": 6,
    "lag_stability_visual_case": 7,
}


def _dash_app_attr(name: str) -> Any:
    from trading_center import dash_readonly_app

    return getattr(dash_readonly_app, name)


def wavecount_case_id(row: dict[str, Any]) -> str:
    return _dash_app_attr("wavecount_case_id")(row)


def wavecount_chart_data_uri(row: dict[str, Any]) -> str:
    return _dash_app_attr("wavecount_chart_data_uri")(row)


def wavecount_chart_figure(row: dict[str, Any], limit: int = 320) -> dict[str, Any]:
    return _dash_app_attr("wavecount_chart_figure")(row, limit=limit)


def wavecount_direction_tone(row: dict[str, Any]) -> str:
    return _dash_app_attr("wavecount_direction_tone")(row)


def wavecount_direction_label(row: dict[str, Any]) -> str:
    return _dash_app_attr("wavecount_direction_label")(row)


def wavecount_enriched_row(row: dict[str, Any]) -> dict[str, Any]:
    return _dash_app_attr("wavecount_enriched_row")(row)


def unique_options(rows: list[dict[str, Any]], key: str) -> list[dict[str, str]]:
    return _dash_app_attr("unique_options")(rows, key)


def wavecount_number(row: dict[str, Any]) -> str:
    explicit = str(row.get("wave_number", "")).strip()
    if explicit in WAVECOUNT_NUMBERS:
        return explicit
    haystack = " ".join(
        str(row.get(key, ""))
        for key in (
            "count_label",
            "live_estimated_wave",
            "confirmed_wave_context",
            "screener_bucket",
            "case_type",
            "notes",
        )
    ).lower()
    match = re.search(r"(?:wave|onda)\s*([1-5])|(?:wave|onda)([1-5])", haystack)
    if not match:
        return ""
    return match.group(1) or match.group(2) or ""


def wavecount_status(row: dict[str, Any]) -> str:
    confidence = str(row.get("confidence_status", "")).strip().lower()
    if confidence == "active":
        return "active"
    if confidence == "candidate":
        return "candidate"
    if confidence in {"no_clear", "study", "study_only"}:
        return "study"
    live = str(row.get("live_estimated_wave", "")).strip().lower()
    context = str(row.get("confirmed_wave_context", "")).strip().lower()
    bucket = str(row.get("screener_bucket", "")).strip().lower()
    haystack = " ".join([live, context, bucket])
    if "active" in live and "candidate" not in live:
        return "active"
    if "active" in context and "candidate" not in context:
        return "active"
    if any(token in haystack for token in ("candidate", "watch", "forming", "possible_wave")):
        return "candidate"
    return "study"


def wavecount_status_label(row: dict[str, Any]) -> str:
    status = wavecount_status(row)
    if status == "active":
        return "activa"
    if status == "candidate":
        return "candidata"
    return "estudio"


def wavecount_quality_status(row: dict[str, Any]) -> str:
    explicit = str(row.get("quality_status", "")).strip().lower()
    if explicit in WAVECOUNT_QUALITY_ORDER:
        return explicit
    status = wavecount_status(row)
    try:
        points = int(float(row.get("structure_points_count") or 0))
    except (TypeError, ValueError):
        points = 0
    has_levels = bool(str(row.get("activation_level", "")).strip()) and bool(str(row.get("invalidation_level", "")).strip())
    if status == "active" and points >= 5:
        return "fuerte"
    if status == "candidate" and points >= 4 and has_levels:
        return "media"
    return "debil"


def wavecount_quality_label(row: dict[str, Any]) -> str:
    status = wavecount_quality_status(row)
    return {"fuerte": "fuerte", "media": "media", "debil": "debil"}.get(status, "debil")


def wavecount_quality_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"label": "Todas", "value": "__all__"}] + [
        {"label": value.capitalize(), "value": value}
        for value in WAVECOUNT_QUALITY_ORDER
    ]


def wavecount_direction_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    labels = {"up": "Alcista", "down": "Bajista", "flat": "Sin direccion"}
    present = {wavecount_direction_tone(row) for row in rows}
    return [{"label": "Todas", "value": "__all__"}] + [
        {"label": labels[value], "value": value}
        for value in ("up", "down", "flat")
        if value in present
    ]


def wavecount_wave_label(row: dict[str, Any]) -> str:
    count_label = str(row.get("count_label", "")).strip()
    if re.fullmatch(r"W[1-5]\??", count_label):
        return count_label
    number = wavecount_number(row) or "-"
    return f"W{number}?" if wavecount_status(row) == "candidate" else f"W{number}"


def wavecount_activation_gap_label(row: dict[str, Any]) -> str:
    enriched = wavecount_enriched_row(row)
    activation = safe_float(enriched.get("activation_level"))
    close = safe_float(enriched.get("latest_close"))
    if activation is None or close is None or close == 0:
        return ""
    gap = abs(activation - close) / abs(close) * 100
    return f"activacion {gap:.1f}%"


def wavecount_visible_case_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("symbol", "")).strip(),
        str(row.get("timeframe", "")).strip(),
        wavecount_number(row),
        wavecount_status(row),
    )


def wavecount_current_case_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("symbol", "")).strip(), str(row.get("timeframe", "")).strip())


def canonical_wavecount_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], tuple[int, int, dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = wavecount_current_case_key(row)
        if not all(key):
            continue
        priority = WAVECOUNT_CASE_TYPE_PRIORITY.get(str(row.get("case_type", "")).strip(), 99)
        current = selected.get(key)
        if current is None or (priority, index) < (current[0], current[1]):
            selected[key] = (priority, index, row)
    return [item[2] for item in sorted(selected.values(), key=lambda item: item[1])]


def unique_wavecount_visible_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = wavecount_visible_case_key(row)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def wavecount_number_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = {number: 0 for number in WAVECOUNT_NUMBERS}
    for row in unique_wavecount_visible_rows(canonical_wavecount_rows(rows)):
        number = wavecount_number(row)
        if number in counts:
            counts[number] += 1
    return [{"number": number, "value": f"wave{number}", "count": counts[number]} for number in WAVECOUNT_NUMBERS]


def default_wavecount_tab(rows: list[dict[str, Any]]) -> str:
    for item in wavecount_number_summary(rows):
        if item["count"]:
            return str(item["value"])
    return "wave1"


def wavecount_case_item(html: Any, row: dict[str, Any]) -> Any:
    tone = wavecount_direction_tone(row)
    status = wavecount_status(row)
    return html.Div(
        [
            html.Span(wavecount_wave_label(row), className=f"wave-number-badge {tone} {status}"),
            html.Strong(get_value(row, "symbol", "symbol")),
            html.Span(get_value(row, "timeframe", "TF"), className="wave-case-tf"),
            html.Span(wavecount_direction_label(row), className=f"wave-case-pill {tone}"),
            html.Span(wavecount_status_label(row), className=f"wave-case-status {status}"),
            html.Span(wavecount_quality_label(row), className=f"wave-case-quality {wavecount_quality_status(row)}"),
        ],
        id={"type": "wave-case-item", "case_id": wavecount_case_id(row)},
        n_clicks=0,
        role="button",
        tabIndex=0,
        className=f"wave-case-item {status}",
    )

def wavecount_tab(html: Any, dcc: Any, data_obj: dict[str, Any]) -> Any:
    rows = data_obj["wavecount_rows"]
    wave_summary = wavecount_number_summary(rows)
    return html.Div(
        [
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        "i",
                                        className="info-icon",
                                        style={"marginLeft": "0"},
                                        title="Conteo estructural por ondas. Es contexto de estudio, no una senal.",
                                    ),
                                    html.H2("WeaveCount", className="visually-hidden"),
                                ],
                                className="panel-heading-title-row",
                            ),
                        ],
                        className="panel-heading",
                    ),
                    dcc.Tabs(
                        id="wave-count-tabs",
                        value=default_wavecount_tab(rows),
                        className="wave-count-tabs",
                        children=[
                            dcc.Tab(
                                label=f"Onda {item['number']} ({item['count']})",
                                value=item["value"],
                                className="wave-count-tab",
                                selected_className="wave-count-tab-selected",
                            )
                            for item in wave_summary
                        ],
                    ),
                ],
                className="wave-hero",
            ),
            html.Div(
                [
                    html.Div(
                        [html.Span("Buscar"), dcc.Input(id="wave-search", type="search", placeholder="Buscar simbolo, onda o contexto", debounce=True)],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Timeframe"), dcc.Dropdown(id="wave-timeframe", options=unique_options(rows, "timeframe"), value="__all__", clearable=False, persistence=True, persistence_type="session")],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Grupo"), dcc.Dropdown(id="wave-group", options=unique_options(rows, "market_group"), value="__all__", clearable=False, persistence=True, persistence_type="session")],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Calidad"), dcc.Dropdown(id="wave-quality", options=wavecount_quality_options(rows), value="__all__", clearable=False)],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Direccion"), dcc.Dropdown(id="wave-direction", options=wavecount_direction_options(rows), value="__all__", clearable=False)],
                        className="control-cell",
                    ),
                ],
                className="toolbar wave-toolbar",
            ),
            html.Div(id="wave-count-content"),
            html.Div(
                [html.Div(id="wave-modal-close", n_clicks=0, style={"display": "none"})],
                id="wave-modal",
                className="wave-modal hidden",
            ),
        ]
    )


def wavecount_cards(html: Any, rows: list[dict[str, Any]]) -> Any:
    if not rows:
        return html.Div(
            "No hay activos en este conteo para los filtros actuales.",
            className="radar-empty",
        )
    active_rows = [row for row in rows if wavecount_status(row) == "active"]
    candidate_rows = [row for row in rows if wavecount_status(row) == "candidate"]
    study_rows = [row for row in rows if wavecount_status(row) not in {"active", "candidate"}]

    def wave_group(title: str, group_rows: list[dict[str, Any]], status: str) -> Any:
        if not group_rows:
            return html.Div(
                [
                    html.Div([html.Strong(title), html.Span("0")], className=f"wave-group-head {status}"),
                    html.Div("Sin casos.", className="wave-group-empty"),
                ],
                className=f"wave-case-group {status}",
            )
        return html.Div(
            [
                html.Div([html.Strong(title), html.Span(str(len(group_rows)))], className=f"wave-group-head {status}"),
                html.Div([wavecount_case_item(html, row) for row in group_rows], className="wave-horizontal-list"),
            ],
            className=f"wave-case-group {status}",
        )

    groups = [
        wave_group("Activas", active_rows, "active"),
        wave_group("Candidatas", candidate_rows, "candidate"),
    ]
    if study_rows:
        groups.append(wave_group("Estudio", study_rows, "study"))
    return html.Div(groups, className="wave-group-stack")


def wavecount_modal(html: Any, dcc: Any, row: dict[str, Any]) -> Any:
    status = wavecount_status(row)
    activation_gap = wavecount_activation_gap_label(row) if status == "candidate" else ""
    chart_figure = wavecount_chart_figure(row)
    chart_node: Any
    if chart_figure:
        chart_node = dcc.Graph(
            figure=chart_figure,
            config={"displayModeBar": False, "responsive": True},
            className="wave-modal-graph",
            style={"height": "72vh"},
        )
    else:
        chart_src = wavecount_chart_data_uri(row)
        if chart_src:
            chart_node = html.Img(src=chart_src, className="wave-modal-chart")
        else:
            chart_node = html.Div("No hay grafico disponible para este caso.", className="radar-empty")
    return html.Div(
        [
            html.Div(className="wave-modal-backdrop"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(wavecount_wave_label(row), className=f"wave-modal-wave {status}"),
                                    html.Div(
                                        [
                                            html.Strong(get_value(row, "symbol", "symbol")),
                                            html.Small(f"{get_value(row, 'market_group', 'grupo')} / {get_value(row, 'timeframe', 'TF')}"),
                                        ]
                                    ),
                                ],
                                className="wave-modal-title",
                            ),
                            html.Div("Cerrar", id="wave-modal-close", n_clicks=0, role="button", tabIndex=0, className="wave-modal-close"),
                        ],
                        className="wave-modal-head",
                    ),
                    html.Div(
                        [
                            html.Span(wavecount_status_label(row), className=f"wave-direction-pill {status}"),
                            html.Span(wavecount_quality_label(row), className=f"wave-direction-pill quality {wavecount_quality_status(row)}"),
                            html.Span(wavecount_direction_label(row), className=f"wave-direction-pill {wavecount_direction_tone(row)}"),
                            *([html.Span(activation_gap, className="wave-direction-pill candidate")] if activation_gap else []),
                            html.Span(get_value(row, "live_estimated_wave", "sin contexto")),
                            html.Span(get_value(row, "screener_bucket", "sin bucket")),
                            html.Span("solo estudio"),
                        ],
                        className="wave-modal-meta",
                    ),
                    chart_node,
                ],
                className="wave-modal-panel",
            ),
        ]
    )
