from __future__ import annotations

from typing import Any

from trading_center.dashboard.formatting import display_context_value, get_value


SCREENER_LAYER_OPTIONS = [
    {"label": "Dia previo", "value": "previous_day"},
    {"label": "Pivots R2/R3/S2/S3", "value": "pivots"},
    {"label": "Fibonacci", "value": "fibonacci"},
    {"label": "Setup fib_limit", "value": "fib_limit"},
    {"label": "Setup macd_breakout", "value": "macd_breakout"},
    {"label": "Setup RSI", "value": "rsi_setup"},
    {"label": "Niveles redondos", "value": "round_levels"},
    {"label": "WeaveCount", "value": "weavecount"},
]
SCREENER_DEFAULT_VISIBLE_LAYERS = ["previous_day", "pivots", "fib_limit", "macd_breakout", "rsi_setup"]
SCREENER_FIB_MODE_OPTIONS = [
    {"label": "Corto", "value": "short"},
    {"label": "Medio", "value": "medium"},
    {"label": "Amplio", "value": "wide"},
    {"label": "Macro", "value": "macro"},
]
SCREENER_DEFAULT_FIB_MODE = "wide"


def _dash_app_attr(name: str) -> Any:
    from trading_center import dash_readonly_app

    return getattr(dash_readonly_app, name)


def unique_options(rows: list[dict[str, Any]], key: str) -> list[dict[str, str]]:
    return _dash_app_attr("unique_options")(rows, key)


def trend_detail_items(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    raw = get_value(row, "trend_detail_context", "")
    markers = {"up": ("^", "up"), "down": ("v", "down"), "mixed": ("~", "muted")}
    output: list[tuple[str, str, str]] = []
    if raw:
        for part in raw.split("|"):
            if ":" not in part:
                continue
            label, marker = part.split(":", 1)
            arrow, tone = markers.get(marker, ("~", "muted"))
            output.append((label, arrow, tone))
    if output:
        return output
    trend = get_value(row, "trend_context", "")
    if trend.startswith("M15/H1/H4 "):
        marker = "up" if trend.endswith("bullish") else "down" if trend.endswith("bearish") else "mixed"
        arrow, tone = markers.get(marker, ("~", "muted"))
        return [(label, arrow, tone) for label in ["M15", "H1", "H4"]]
    if trend.startswith("H1/H4/D1 "):
        marker = "up" if trend.endswith("bullish") else "down" if trend.endswith("bearish") else "mixed"
        arrow, tone = markers.get(marker, ("~", "muted"))
        return [(label, arrow, tone) for label in ["H1", "H4", "D1"]]
    return []


def screener_setup_type_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    values = {
        "fib_limit_live_candidate",
        "macd_breakout",
        "rsi_trend_reversal",
    }
    values.update(str(row.get("setup_type", "")).strip() for row in rows if str(row.get("setup_type", "")).strip())
    labels = {
        "fib_limit_live_candidate": "fib_limit",
        "macd_breakout": "macd_breakout",
        "rsi_trend_reversal": "RSI",
        "previous_day_high_low_candidate": "Dia previo",
        "fibonacci_zone_candidate": "Fibonacci",
    }
    return [{"label": "Todos los setups", "value": "__all__"}] + [
        {"label": labels.get(value, value), "value": value}
        for value in sorted(values)
    ]


def screener_direction_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    values = sorted({str(row.get("direction", "")).strip() for row in rows if str(row.get("direction", "")).strip()})
    labels = {"long": "Alcista", "short": "Bajista", "neutral": "Neutral"}
    return [{"label": "Todas", "value": "__all__"}] + [{"label": labels.get(value, value), "value": value} for value in values]


def screener_quality_options() -> list[dict[str, Any]]:
    return [
        {"label": "Calidad minima", "value": 1},
        {"label": "2/5+", "value": 2},
        {"label": "3/5+", "value": 3},
        {"label": "4/5+", "value": 4},
        {"label": "5/5", "value": 5},
    ]


def screener_review_state_options() -> list[dict[str, str]]:
    return [
        {"label": "Revisables", "value": "reviewable"},
        {"label": "Watching", "value": "watching"},
        {"label": "Sin contexto", "value": "no_context"},
        {"label": "Todos", "value": "__all__"},
    ]


def screener_score(row: dict[str, Any]) -> int:
    try:
        return max(1, min(5, int(float(str(row.get("setup_quality_score", 1))))))
    except (TypeError, ValueError):
        return 1


def screener_is_primary_setup(row: dict[str, Any]) -> bool:
    return str(row.get("setup_status", "")).strip() == "ready_for_chart_review"


def screener_matches_review_state(row: dict[str, Any], review_state: str | None) -> bool:
    state = str(review_state or "reviewable").strip() or "reviewable"
    if state == "__all__":
        return True
    setup_status = str(row.get("setup_status", "")).strip()
    timing_state = screener_timing_state(row)
    if state == "reviewable":
        return screener_is_primary_setup(row)
    if state == "watching":
        return setup_status == "needs_review" or timing_state == "watching"
    if state == "no_context":
        return setup_status in {"context_incomplete", "late_context"} or timing_state in {"missing_context", "late", "invalidated"}
    return screener_is_primary_setup(row)


def screener_tone(row: dict[str, Any]) -> str:
    direction = str(row.get("direction", "")).strip().lower()
    if direction == "long":
        return "up"
    if direction == "short":
        return "down"
    return "muted"


def screener_status_label(row: dict[str, Any]) -> str:
    status = str(row.get("setup_status", "")).strip()
    labels = {
        "study_only": "study_only",
        "needs_review": "needs_review",
        "ready_for_chart_review": "ready_for_chart_review",
    }
    return labels.get(status, "needs_review")


def screener_chips(value: Any, limit: int = 5) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [chip for chip in text.split("|") if chip][:limit]


def screener_timing_state(row: dict[str, Any]) -> str:
    if str(row.get("setup_type", "")).strip() == "macd_breakout":
        return macd_breakout_timing_label(row)
    value = str(row.get("timing_state", "")).strip()
    return value or "watching"


def screener_timing_reason(row: dict[str, Any]) -> str:
    setup_type = str(row.get("setup_type", "")).strip()
    if setup_type == "macd_breakout":
        reason = str(row.get("macd_breakout_timing_reason") or row.get("timing_reason") or "").strip()
        return reason or "timing macd_breakout sin lectura"
    reason = str(row.get("timing_reason") or "").strip()
    if "timing especifico" in reason and "implementado" in reason:
        return "contexto para revisar; no tiene timing especifico de entrada"
    return reason or "sin timing especifico"


def screener_timing_priority(row: dict[str, Any]) -> int:
    try:
        return int(float(str(row.get("timing_priority", 10))))
    except (TypeError, ValueError):
        return 10


def screener_timing_distance_label(row: dict[str, Any]) -> str:
    value = str(row.get("distance_to_trigger_pct", "")).strip()
    if not value:
        return "dist. n/d"
    return f"dist. {value}%"


def macd_breakout_timing_label(row: dict[str, Any]) -> str:
    state = str(row.get("macd_breakout_timing_state") or row.get("timing_state") or "").strip()
    if state == "late":
        return "tarde"
    if state == "invalidated":
        return "invalidado"
    if state == "missing_context":
        return "sin contexto"
    return state or "watching"


def filter_screener_setups(
    rows: list[dict[str, Any]],
    search: str | None,
    setup_type: str | None,
    timeframe: str | None,
    group: str | None,
    min_quality: int | None,
    direction: str | None,
    review_state: str | None = "reviewable",
) -> list[dict[str, Any]]:
    query = str(search or "").strip().lower()
    min_score = int(min_quality or 1)
    output: list[dict[str, Any]] = []
    for row in rows:
        if not screener_matches_review_state(row, review_state):
            continue
        if query and query not in " ".join(str(value) for value in row.values()).lower():
            continue
        if setup_type and setup_type != "__all__" and row.get("setup_type") != setup_type:
            continue
        if timeframe and timeframe != "__all__" and row.get("timeframe") != timeframe:
            continue
        if group and group != "__all__" and row.get("market_group") != group:
            continue
        if direction and direction != "__all__" and row.get("direction") != direction:
            continue
        if screener_score(row) < min_score:
            continue
        output.append(row)
    output.sort(
        key=lambda item: (
            screener_timing_priority(item),
            -screener_score(item),
            -int(float(str(item.get("confluence_count") or 0))),
            str(item.get("symbol")),
        )
    )
    return output


def screener_has_active_filters(
    search: str | None,
    setup_type: str | None,
    timeframe: str | None,
    group: str | None,
    min_quality: int | None,
    direction: str | None,
    review_state: str | None = "reviewable",
) -> bool:
    return any(
        [
            bool(str(search or "").strip()),
            bool(setup_type and setup_type != "__all__"),
            bool(timeframe and timeframe != "__all__"),
            bool(group and group != "__all__"),
            bool(direction and direction != "__all__"),
            int(min_quality or 1) > 1,
            bool(review_state and review_state != "reviewable"),
        ]
    )


def screener_layer_rows(data_obj: dict[str, Any], setup_id: str) -> list[dict[str, Any]]:
    return [row for row in data_obj.get("screener_chart_layer_rows", []) if str(row.get("setup_id", "")) == setup_id]


def screener_layer_family(layer: dict[str, Any]) -> str:
    layer_type = str(layer.get("layer_type", "")).strip().lower()
    label = str(layer.get("label", "")).strip().lower()
    source = str(layer.get("source", "")).strip().lower()
    if layer_type.startswith("macd_") or "macd_breakout" in source or "ruptura estudio" in label or "cruce macd" in label:
        return "macd_breakout"
    if layer_type.startswith("rsi_") or "rsi_trend_reversal" in source:
        return "rsi_setup"
    if layer_type.startswith("fib_limit") or "fib_limit" in source:
        return "fib_limit"
    if layer_type.startswith("fibonacci") or label.startswith("fib") or "fibonacci" in source:
        return "fibonacci"
    if layer_type.startswith("round_level") or label.startswith("nivel redondo") or "round" in source:
        return "round_levels"
    if layer_type in {"r2", "r3", "s2", "s3"} or label.startswith(("r2", "r3", "s2", "s3")):
        return "pivots"
    if layer_type in {"previous_high", "previous_low"} or "dia previo" in label or "previous_day" in source:
        return "previous_day"
    if "wavecount" in layer_type or "wavecount" in label or "wavecount" in source:
        return "weavecount"
    return "context"


def filter_screener_layers(layer_rows: list[dict[str, Any]], visible_layers: list[str] | None) -> list[dict[str, Any]]:
    visible = set(SCREENER_DEFAULT_VISIBLE_LAYERS if visible_layers is None else visible_layers)
    return [layer for layer in layer_rows if screener_layer_family(layer) in visible]


def screener_setup_card(html: Any, row: dict[str, Any]) -> Any:
    tone = screener_tone(row)
    score = screener_score(row)
    chips = screener_chips(row.get("confluence_tags"), 4)
    timing_state = macd_breakout_timing_label(row) if str(row.get("setup_type")) == "macd_breakout" else screener_timing_state(row)
    return html.Div(
        [
            html.Span(f"{score}/5", className=f"screener-score {tone}"),
            html.Div(
                [
                    html.Strong(get_value(row, "symbol", "symbol")),
                    html.Small(f"{get_value(row, 'market_group', 'grupo')} / {get_value(row, 'timeframe', 'TF')}"),
                ],
                className="screener-row-asset",
            ),
            html.Div(
                [
                    html.Span(get_value(row, "setup_type", "setup").replace("_", " "), className="screener-setup-name"),
                    html.Span(timing_state.replace("_", " "), className="screener-row-pill"),
                    html.Span(display_context_value(get_value(row, "trend_compatibility", "mixed")).replace("_", " "), className="screener-row-pill muted"),
                ],
                className="screener-row-main",
            ),
            html.Div([html.Span(chip.replace("_", " "), className="screener-chip") for chip in chips], className="screener-row-chips"),
            html.Div(
                [
                    html.Span(screener_timing_distance_label(row), className="screener-mini-context"),
                    html.Span(screener_status_label(row).replace("_", " "), className="screener-status"),
                ],
                className="screener-row-end",
            ),
        ],
        id={"type": "screener-setup-card", "setup_id": row.get("setup_id")},
        n_clicks=0,
        role="button",
        tabIndex=0,
        title=get_value(row, "timing_reason", "sin timing"),
        className=f"screener-signal-row {tone}",
    )

def screener_tab(html: Any, dcc: Any, data_obj: dict[str, Any]) -> Any:
    setups = data_obj.get("screener_setups_rows", [])
    primary_setups = [row for row in setups if screener_is_primary_setup(row)]
    if not setups:
        return html.Div(
            [
                html.Section(
                    [
                        html.Div(
                            [
                                html.Span(
                                    "i",
                                    className="info-icon",
                                    style={"marginLeft": "0"},
                                    title="Setups para revisar con confluencias auditables. No son senales.",
                                ),
                                html.H2("Screener", className="visually-hidden"),
                            ],
                            className="panel-heading-title-row",
                        ),
                        html.Div(
                            "Faltan artifacts del Screener unificado. Ejecuta `python -m trading_center.screener_unified` y recarga.",
                            className="radar-empty",
                        ),
                    ],
                    className="screener-shell",
                )
            ]
        )
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
                                        title="Setups para revisar con confluencias auditables. No son senales.",
                                    ),
                                    html.H2("Screener", className="visually-hidden"),
                                ],
                                className="panel-heading-title-row",
                            ),
                            html.Div(
                                [
                                    html.Div([html.Strong(str(len(primary_setups))), html.Small("setups a revisar")], className="screener-stat"),
                                ],
                                className="screener-stat-grid",
                            ),
                        ],
                        className="screener-hero-copy",
                    ),
                    html.Div(id="screener-hero-top", className="screener-hero-top"),
                ],
                className="screener-hero",
            ),
            html.Div(
                [
                    html.Div(
                        [html.Span("Buscar"), dcc.Input(id="screener-search", type="search", placeholder="Simbolo, setup o confluencia", debounce=True)],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Tipo de setup"), dcc.Dropdown(id="screener-setup-type", options=screener_setup_type_options(setups), value="__all__", clearable=False)],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Timeframe"), dcc.Dropdown(id="screener-timeframe", options=unique_options(setups, "timeframe"), value="__all__", clearable=False, persistence=True, persistence_type="session")],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Grupo"), dcc.Dropdown(id="screener-group", options=unique_options(setups, "market_group"), value="__all__", clearable=False, persistence=True, persistence_type="session")],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Calidad minima"), dcc.Dropdown(id="screener-quality-min", options=screener_quality_options(), value=1, clearable=False)],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Estado"), dcc.Dropdown(id="screener-review-state", options=screener_review_state_options(), value="reviewable", clearable=False, persistence=True, persistence_type="session")],
                        className="control-cell",
                    ),
                    html.Div(
                        [html.Span("Direccion"), dcc.Dropdown(id="screener-direction", options=screener_direction_options(setups), value="__all__", clearable=False)],
                        className="control-cell",
                    ),
                ],
                className="toolbar screener-toolbar",
            ),
            html.Div([html.H2("Activos con setup a revisar"), html.P("Lista compacta: trend alignment queda como contexto, no como setup destacado.")], className="panel-heading"),
            html.Div(id="screener-highlighted-setups"),
            html.Div([html.Div(id="screener-modal-close", n_clicks=0, style={"display": "none"})], id="screener-modal", className="wave-modal hidden"),
        ]
    )
