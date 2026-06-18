from __future__ import annotations

from typing import Any

import numpy as np

from trading_center.market_correlations import corr_pair, distance_correlation


def metric_options() -> list[dict[str, str]]:
    return [
        {"label": "Pearson", "value": "pearson"},
        {"label": "Spearman", "value": "spearman"},
        {"label": "Kendall", "value": "kendall"},
        {"label": "Distancia", "value": "dcor"},
    ]


def timeframe_options(source: dict[str, Any]) -> list[dict[str, str]]:
    values = source.get("timeframes") or ["M15", "H1", "H4", "D1"]
    return [{"label": str(value), "value": str(value)} for value in values]


def asset_options(source: dict[str, Any]) -> list[dict[str, str]]:
    values = source.get("assets") or []
    return [{"label": str(value), "value": str(value)} for value in values]


def preferred_asset(values: list[str], preferred_roots: tuple[str, ...], fallback_index: int = 0) -> str | None:
    normalized = [str(value) for value in values]
    for root in preferred_roots:
        for candidate in (root, f"{root}.r"):
            if candidate in normalized:
                return candidate
        for value in normalized:
            if value.upper().startswith(root.upper()):
                return value
    if normalized:
        return normalized[min(fallback_index, len(normalized) - 1)]
    return None


def default_base_asset(source: dict[str, Any]) -> str | None:
    return preferred_asset(list(source.get("assets") or []), ("EURUSD",))


def default_other_asset(source: dict[str, Any], base_asset: str | None) -> str | None:
    values = [str(value) for value in source.get("assets") or [] if str(value) != str(base_asset)]
    preferred = preferred_asset(values, ("GBPUSD", "USDCHF", "AUDUSD"), fallback_index=0)
    return preferred


def default_matrix_assets(source: dict[str, Any], limit: int = 8) -> list[str]:
    values = [str(value) for value in source.get("assets") or [] if str(value)]
    preferred_roots = (
        "EURUSD",
        "GBPUSD",
        "USDCHF",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "NZDUSD",
        "XAUUSD",
        "BTCUSD",
        "ETHUSD",
        "US500",
        "EUR50",
    )
    assets: list[str] = []
    for root in preferred_roots:
        selected = preferred_asset([value for value in values if value not in assets], (root,))
        if selected and selected not in assets:
            assets.append(selected)
        if len(assets) >= limit:
            return assets[:limit]
    for value in values:
        if value not in assets:
            assets.append(value)
        if len(assets) >= limit:
            break
    return assets[:limit]


def normalize_matrix_assets(selected: Any, source: dict[str, Any], limit: int = 18) -> list[str]:
    available = [str(value) for value in source.get("assets") or [] if str(value)]
    if isinstance(selected, str):
        raw_values = [selected]
    elif isinstance(selected, list):
        raw_values = [str(value) for value in selected if str(value)]
    else:
        raw_values = []
    assets: list[str] = []
    for value in raw_values:
        if value in available and value not in assets:
            assets.append(value)
        if len(assets) >= limit:
            break
    if len(assets) < 2:
        assets = default_matrix_assets(source, limit=min(limit, 12))
    return assets[:limit]


def metric_label(metric_name: str) -> str:
    labels = {
        "pearson": "Pearson",
        "spearman": "Spearman",
        "kendall": "Kendall",
        "dcor": "Distancia",
    }
    return labels.get(metric_name, metric_name)


def corr_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def corr_value(row: dict[str, Any], metric_name: str) -> float | None:
    return corr_float(row.get(metric_name))


def corr_tone(value: float | None, metric_name: str = "") -> str:
    if value is None:
        return "muted"
    if metric_name == "dcor":
        if value >= 0.7:
            return "hot"
        if value <= 0.25:
            return "quiet"
        return "muted"
    if value >= 0.35:
        return "up"
    if value <= -0.35:
        return "down"
    return "muted"


def corr_display(value: float | None) -> str:
    return "n/d" if value is None else f"{value:+.2f}"


def dcor_display(value: float | None) -> str:
    return "n/d" if value is None else f"{value:.2f}"


def pair_key(asset_1: str, asset_2: str) -> tuple[str, str]:
    return tuple(sorted((str(asset_1), str(asset_2))))  # type: ignore[return-value]


def correlation_rows_for_asset(
    rows: list[dict[str, Any]],
    timeframe: str,
    asset: str,
    metric_name: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("timeframe")) != str(timeframe):
            continue
        left = str(row.get("asset_1", ""))
        right = str(row.get("asset_2", ""))
        if asset not in {left, right}:
            continue
        value = corr_value(row, metric_name)
        if value is None:
            continue
        other = right if left == asset else left
        output.append(
            {
                "asset": other,
                "pair": row.get("pair", f"{left} | {right}"),
                "value": value,
                "abs_value": abs(value),
                "obs": row.get("obs", ""),
                "sample_start": row.get("sample_start", ""),
                "sample_end": row.get("sample_end", ""),
                "tone": corr_tone(value, metric_name),
                "metric": metric_name,
            }
        )
    return output


def split_correlation_rankings(rows: list[dict[str, Any]], metric_name: str) -> dict[str, list[dict[str, Any]]]:
    if metric_name == "dcor":
        return {
            "strong": sorted(rows, key=lambda item: item["value"], reverse=True)[:8],
            "weak": sorted(rows, key=lambda item: item["value"])[:8],
        }
    return {
        "positive": sorted([row for row in rows if row["value"] > 0], key=lambda item: item["value"], reverse=True)[:8],
        "negative": sorted([row for row in rows if row["value"] < 0], key=lambda item: item["value"])[:8],
        "strong": sorted(rows, key=lambda item: item["abs_value"], reverse=True)[:8],
    }


def find_pair_correlation(rows: list[dict[str, Any]], timeframe: str, asset_1: str, asset_2: str, metric_name: str) -> dict[str, Any] | None:
    key = pair_key(asset_1, asset_2)
    for row in rows:
        if str(row.get("timeframe")) != str(timeframe):
            continue
        if pair_key(str(row.get("asset_1", "")), str(row.get("asset_2", ""))) != key:
            continue
        value = corr_value(row, metric_name)
        return {
            "pair": row.get("pair", f"{asset_1} | {asset_2}"),
            "value": value,
            "pearson": corr_float(row.get("pearson")),
            "spearman": corr_float(row.get("spearman")),
            "kendall": corr_float(row.get("kendall")),
            "dcor": corr_float(row.get("dcor")),
            "obs": row.get("obs", ""),
            "sample_start": row.get("sample_start", ""),
            "sample_end": row.get("sample_end", ""),
        }
    return None


def matrix_assets_for_focus(rows: list[dict[str, Any]], timeframe: str, asset: str, other_asset: str, metric_name: str, limit: int = 16) -> list[str]:
    focus_rows = correlation_rows_for_asset(rows, timeframe, asset, metric_name)
    ranked = sorted(focus_rows, key=lambda item: item["abs_value"], reverse=True)
    assets = [asset]
    if other_asset and other_asset != asset:
        assets.append(other_asset)
    for row in ranked:
        candidate = str(row.get("asset", ""))
        if candidate and candidate not in assets:
            assets.append(candidate)
        if len(assets) >= limit:
            break
    return assets


def correlation_matrix_payload(
    rows: list[dict[str, Any]],
    timeframe: str,
    assets: list[str],
    metric_name: str,
) -> dict[str, Any]:
    lookup = pair_metric_lookup(rows, timeframe, metric_name)
    z_values: list[list[float | None]] = []
    text_values: list[list[str]] = []
    for row_asset in assets:
        z_row: list[float | None] = []
        text_row: list[str] = []
        for col_asset in assets:
            if row_asset == col_asset:
                value = 1.0 if metric_name != "dcor" else 0.0
            else:
                value = lookup.get(pair_key(row_asset, col_asset))
            z_row.append(value)
            text_row.append("" if value is None else f"{value:.2f}")
        z_values.append(z_row)
        text_values.append(text_row)
    return {"assets": assets, "z": z_values, "text": text_values}


def pair_return_points(
    rows: list[dict[str, Any]],
    timeframe: str,
    asset_1: str,
    asset_2: str,
    limit: int = 420,
) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, float]] = {asset_1: {}, asset_2: {}}
    for row in rows:
        if str(row.get("timeframe")) != str(timeframe):
            continue
        symbol = str(row.get("symbol", ""))
        if symbol not in by_symbol:
            continue
        value = corr_float(row.get("log_return"))
        timestamp = str(row.get("timestamp", ""))
        if timestamp and value is not None:
            by_symbol[symbol][timestamp] = value
    common = sorted(set(by_symbol.get(asset_1, {})) & set(by_symbol.get(asset_2, {})))[-limit:]
    return [
        {
            "timestamp": timestamp,
            "x": by_symbol[asset_1][timestamp],
            "y": by_symbol[asset_2][timestamp],
        }
        for timestamp in common
    ]


def rolling_window_for_timeframe(timeframe: str) -> int:
    return {
        "M15": 96,
        "H1": 120,
        "H4": 90,
        "D1": 60,
    }.get(str(timeframe).upper(), 120)


def rolling_correlation_series(
    points: list[dict[str, Any]],
    metric_name: str,
    *,
    window: int,
) -> list[dict[str, Any]]:
    if len(points) < 8:
        return []
    min_periods = max(8, min(window, max(12, window // 2)))
    if metric_name == "dcor":
        min_periods = max(8, min(min_periods, 40))
    series: list[dict[str, Any]] = []
    for end_index in range(len(points)):
        start_index = max(0, end_index - window + 1)
        frame = points[start_index : end_index + 1]
        if len(frame) < min_periods:
            continue
        if metric_name == "dcor":
            frame = frame[-min(window, 80) :]
        x_values = np.asarray([float(point["x"]) for point in frame], dtype=float)
        y_values = np.asarray([float(point["y"]) for point in frame], dtype=float)
        value = distance_correlation(x_values, y_values) if metric_name == "dcor" else corr_pair(x_values, y_values, metric_name)
        if value == value:
            series.append(
                {
                    "timestamp": points[end_index]["timestamp"],
                    "value": float(value),
                }
            )
    return series


def rolling_summary(series: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(point["value"]) for point in series if point.get("value") is not None]
    if not values:
        return {
            "latest": None,
            "previous": None,
            "delta": None,
            "mean": None,
            "minimum": None,
            "maximum": None,
            "obs": 0,
        }
    latest = values[-1]
    previous = values[-2] if len(values) >= 2 else None
    return {
        "latest": latest,
        "previous": previous,
        "delta": latest - previous if previous is not None else None,
        "mean": sum(values) / len(values),
        "minimum": min(values),
        "maximum": max(values),
        "obs": len(values),
    }


def lowess_line(points: list[dict[str, Any]], fraction: float = 0.28, max_points: int = 180) -> tuple[list[float], list[float]] | None:
    if len(points) < 6:
        return None
    ordered = sorted((float(point["x"]), float(point["y"])) for point in points)
    if not ordered:
        return None
    n = len(ordered)
    window = max(6, min(n, int(n * fraction)))
    if n <= max_points:
        targets = ordered
    else:
        step = (n - 1) / (max_points - 1)
        indexes = sorted({round(index * step) for index in range(max_points)})
        targets = [ordered[index] for index in indexes]

    xs_all = [x for x, _ in ordered]
    smooth_x: list[float] = []
    smooth_y: list[float] = []
    for xi, _ in targets:
        distances = sorted(abs(x - xi) for x in xs_all)
        bandwidth = distances[min(window - 1, len(distances) - 1)]
        if bandwidth <= 1e-18:
            nearby = [y for x, y in ordered if abs(x - xi) <= 1e-18]
            yhat = sum(nearby) / len(nearby) if nearby else ordered[0][1]
        else:
            sw = swx = swy = swxx = swxy = 0.0
            for x, y in ordered:
                scaled = abs(x - xi) / bandwidth
                if scaled >= 1:
                    continue
                weight = (1 - scaled**3) ** 3
                sw += weight
                swx += weight * x
                swy += weight * y
                swxx += weight * x * x
                swxy += weight * x * y
            if sw <= 1e-18:
                continue
            denom = (sw * swxx) - (swx * swx)
            if abs(denom) <= 1e-18:
                yhat = swy / sw
            else:
                beta = ((sw * swxy) - (swx * swy)) / denom
                alpha = (swy - beta * swx) / sw
                yhat = alpha + beta * xi
        smooth_x.append(xi)
        smooth_y.append(yhat)
    return (smooth_x, smooth_y) if smooth_x and smooth_y else None


PLOTLY_HOVERLABEL = {
    "bgcolor": "#0d1b1a",
    "bordercolor": "#5ce0ca",
    "font": {"color": "#f2fffb", "family": "Consolas, monospace", "size": 12},
}


def pair_scatter_figure(points: list[dict[str, Any]], asset_1: str, asset_2: str, metric_name: str) -> dict[str, Any]:
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    labels = [point["timestamp"] for point in points]
    traces: list[dict[str, Any]] = [
        {
            "type": "scatter",
            "mode": "markers",
            "x": xs,
            "y": ys,
            "customdata": labels,
            "marker": {"size": 7, "color": "rgba(92,224,202,0.72)", "line": {"width": 1, "color": "rgba(7,16,15,0.9)"}},
            "hoverlabel": PLOTLY_HOVERLABEL,
            "hovertemplate": f"%{{customdata}}<br>{asset_1}: %{{x:.5f}}<br>{asset_2}: %{{y:.5f}}<extra></extra>",
        }
    ]
    line = lowess_line(points)
    if line is not None:
        line_x, line_y = line
        traces.append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": line_x,
                "y": line_y,
                "line": {"color": "rgba(215,168,75,0.96)", "width": 2.5},
                "hoverinfo": "skip",
                "name": "LOWESS",
            }
        )
    return {
        "data": traces,
        "layout": chart_layout(
            title=f"{asset_1} vs {asset_2}",
            x_title=f"{asset_1} retorno",
            y_title=f"{asset_2} retorno",
            height=420,
        ),
    }


def rolling_pair_figure(series: list[dict[str, Any]], asset_1: str, asset_2: str, metric_name: str, window: int) -> dict[str, Any]:
    x_values = [point["timestamp"] for point in series]
    y_values = [point["value"] for point in series]
    trace_color = "rgba(215,168,75,0.96)" if metric_name == "dcor" else "rgba(92,224,202,0.96)"
    fill_color = "rgba(215,168,75,0.12)" if metric_name == "dcor" else "rgba(92,224,202,0.12)"
    traces: list[dict[str, Any]] = [
        {
            "type": "scatter",
            "mode": "lines",
            "x": x_values,
            "y": y_values,
            "line": {"color": trace_color, "width": 2.4},
            "fill": "tozeroy" if metric_name != "dcor" else "tozeroy",
            "fillcolor": fill_color,
            "hoverlabel": PLOTLY_HOVERLABEL,
            "hovertemplate": f"{asset_1} / {asset_2}<br>%{{x}}<br>%{{y:.3f}}<extra></extra>",
        }
    ]
    y_axis = {
        "title": metric_label(metric_name),
        "range": [0, 1] if metric_name == "dcor" else [-1, 1],
        "gridcolor": "rgba(142,160,156,0.12)",
        "zeroline": True,
        "zerolinecolor": "rgba(142,160,156,0.32)",
        "tickfont": {"size": 10, "color": "#8ea09c"},
        "titlefont": {"size": 11, "color": "#8ea09c"},
    }
    return {
        "data": traces,
        "layout": {
            **chart_layout(
                title=f"Rolling {asset_1} vs {asset_2} · ventana {window}",
                x_title="timestamp",
                y_title=metric_label(metric_name),
                height=360,
            ),
            "yaxis": y_axis,
            "hovermode": "x unified",
        },
    }


def matrix_heatmap_figure(payload: dict[str, Any], metric_name: str) -> dict[str, Any]:
    z_values = payload.get("z", [])
    z_abs = [
        abs(float(value))
        for row in z_values
        for value in row
        if value not in (None, "")
    ]
    zmax = 1.0 if metric_name != "dcor" else max(0.4, min(1.0, max(z_abs, default=1.0)))
    zmin = -1.0 if metric_name != "dcor" else 0.0
    colorscale = (
        [[0.0, "#783b43"], [0.5, "#0c1c20"], [1.0, "#6edbc4"]]
        if metric_name != "dcor"
        else [[0.0, "#0c1c20"], [0.55, "#2c6c70"], [1.0, "#d7a84b"]]
    )
    heatmap = {
        "type": "heatmap",
        "z": z_values,
        "x": payload.get("assets", []),
        "y": payload.get("assets", []),
        "text": payload.get("text", []),
        "texttemplate": "%{text}",
        "hovertemplate": "%{y} | %{x}<br>%{z:.3f}<extra></extra>",
        "colorscale": colorscale,
        "zmin": zmin,
        "zmax": zmax,
        "xgap": 1,
        "ygap": 1,
        "colorbar": {"thickness": 10, "tickfont": {"size": 9, "color": "#8ea09c"}},
        "hoverlabel": PLOTLY_HOVERLABEL,
    }
    if metric_name != "dcor":
        heatmap["zmid"] = 0
    return {
        "data": [heatmap],
        "layout": chart_layout(title=f"Matriz {metric_label(metric_name)}", height=520),
    }


def chart_layout(title: str, x_title: str = "", y_title: str = "", height: int = 320) -> dict[str, Any]:
    return {
        "template": "plotly_dark",
        "height": height,
        "margin": {"l": 46, "r": 18, "t": 40, "b": 56},
        "paper_bgcolor": "#07100f",
        "plot_bgcolor": "#07100f",
        "font": {"color": "#e8f1ed", "family": "Consolas, monospace"},
        "title": {"text": title, "x": 0.02, "font": {"size": 13, "color": "#e8f1ed"}},
        "hoverlabel": PLOTLY_HOVERLABEL,
        "xaxis": {
            "title": x_title,
            "linecolor": "rgba(142,160,156,0.34)",
            "gridcolor": "rgba(142,160,156,0.12)",
            "zeroline": True,
            "zerolinecolor": "rgba(142,160,156,0.32)",
            "tickfont": {"size": 10, "color": "#8ea09c"},
            "titlefont": {"size": 11, "color": "#8ea09c"},
        },
        "yaxis": {
            "title": y_title,
            "linecolor": "rgba(142,160,156,0.34)",
            "gridcolor": "rgba(142,160,156,0.12)",
            "zeroline": True,
            "zerolinecolor": "rgba(142,160,156,0.32)",
            "tickfont": {"size": 10, "color": "#8ea09c"},
            "titlefont": {"size": 11, "color": "#8ea09c"},
            "autorange": "reversed" if not x_title and not y_title else True,
        },
        "showlegend": False,
        "hovermode": "closest",
    }


def rolling_rows_for_asset(
    rows: list[dict[str, Any]],
    timeframe: str,
    asset: str,
    metric_name: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("timeframe")) != str(timeframe) or str(row.get("metric")) != str(metric_name):
            continue
        left = str(row.get("asset_1", ""))
        right = str(row.get("asset_2", ""))
        if asset not in {left, right}:
            continue
        latest = corr_float(row.get("latest_corr"))
        previous = corr_float(row.get("previous_corr"))
        delta = corr_float(row.get("delta_prev"))
        if latest is None:
            continue
        other = right if left == asset else left
        output.append(
            {
                "asset": other,
                "pair": row.get("pair", f"{left} | {right}"),
                "latest": latest,
                "previous": previous,
                "delta": delta,
                "abs_delta": abs(delta) if delta is not None else 0.0,
                "obs": row.get("obs", ""),
                "window": row.get("window", ""),
                "tone": corr_tone(latest, metric_name),
                "metric": metric_name,
            }
        )
    return output


def pair_metric_lookup(rows: list[dict[str, Any]], timeframe: str, metric_name: str) -> dict[tuple[str, str], float]:
    lookup: dict[tuple[str, str], float] = {}
    for row in rows:
        if str(row.get("timeframe")) != str(timeframe):
            continue
        left = str(row.get("asset_1", ""))
        right = str(row.get("asset_2", ""))
        value = corr_value(row, metric_name)
        if left and right and value is not None:
            lookup[pair_key(left, right)] = value
    return lookup


def partial_correlation_rows(
    rows: list[dict[str, Any]],
    timeframe: str,
    conditioning_asset: str,
    metric_name: str,
) -> list[dict[str, Any]]:
    if metric_name == "dcor":
        return []
    lookup = pair_metric_lookup(rows, timeframe, metric_name)
    assets = sorted({asset for key in lookup for asset in key if asset != conditioning_asset})
    output: list[dict[str, Any]] = []
    for left_index, asset_1 in enumerate(assets):
        for asset_2 in assets[left_index + 1 :]:
            corr_ab = lookup.get(pair_key(asset_1, asset_2))
            corr_az = lookup.get(pair_key(asset_1, conditioning_asset))
            corr_bz = lookup.get(pair_key(asset_2, conditioning_asset))
            if corr_ab is None or corr_az is None or corr_bz is None:
                continue
            denom = ((1 - corr_az * corr_az) * (1 - corr_bz * corr_bz)) ** 0.5
            if denom <= 1e-9:
                continue
            value = (corr_ab - corr_az * corr_bz) / denom
            output.append(
                {
                    "asset": f"{asset_1} / {asset_2}",
                    "pair": f"{asset_1} | {asset_2}",
                    "value": max(-1.0, min(1.0, value)),
                    "abs_value": abs(value),
                    "control": conditioning_asset,
                    "tone": corr_tone(value, metric_name),
                    "metric": metric_name,
                }
            )
    return sorted(output, key=lambda item: item["abs_value"], reverse=True)[:12]


def corr_rank_row(html: Any, row: dict[str, Any], metric_name: str, rank: int, *, rolling: bool = False) -> Any:
    value = row.get("latest") if rolling else row.get("value")
    display = dcor_display(value) if metric_name == "dcor" else corr_display(value)
    delta = row.get("delta")
    delta_text = "" if delta in (None, "") else f"{delta:+.2f}"
    return html.Div(
        [
            html.Span(f"{rank:02d}", className="rank-number"),
            html.Div([html.Strong(row.get("asset", "")), html.Small(row.get("pair", ""))], className="rank-symbol"),
            html.Div(
                [
                    html.Span([html.Em(metric_label(metric_name)), html.B(display, className=f"corr-value {row.get('tone', 'muted')}")]),
                    html.Span([html.Em("Cambio"), html.B(delta_text or "n/d")]) if rolling else html.Span([html.Em("Obs"), html.B(str(row.get("obs", "n/d")))]),
                ],
                className="rank-metrics",
            ),
        ],
        className=f"corr-rank-row {row.get('tone', 'muted')}",
    )

def corr_rank_panel(html: Any, title: str, subtitle: str, rows: list[dict[str, Any]], metric_name: str, *, rolling: bool = False) -> Any:
    return html.Section(
        [
            html.Div([html.Strong(title), html.Small(subtitle)], className="rank-title"),
            html.Div(
                [corr_rank_row(html, row, metric_name, index, rolling=rolling) for index, row in enumerate(rows[:8], start=1)]
                or [html.Div("Sin relaciones suficientes para esta lectura.", className="radar-empty")],
                className="corr-rank-list",
            ),
        ],
        className="corr-panel",
    )

def pair_metric_card(html: Any, label: str, value: float | None, note: str, metric_name: str, extra_class: str = "") -> Any:
    display = dcor_display(value) if metric_name == "dcor" else corr_display(value)
    return html.Div(
        [html.Span(label, className="metric-label"), html.Strong(display), html.Small(note)],
        className=f"metric {corr_tone(value, metric_name)} {extra_class}".strip(),
    )

def pair_focus_card(html: Any, pair_info: dict[str, Any] | None, asset_1: str, asset_2: str) -> Any:
    return html.Section(
        [
            html.Div([html.Strong("Par seleccionado"), html.Small(f"{asset_1} / {asset_2}")], className="rank-title"),
            html.Div(
                [
                    pair_metric_card(html, "Pearson", pair_info.get("pearson") if pair_info else None, "lineal", "pearson"),
                    pair_metric_card(html, "Spearman", pair_info.get("spearman") if pair_info else None, "rangos", "spearman"),
                    pair_metric_card(html, "Kendall", pair_info.get("kendall") if pair_info else None, "concordancia", "kendall"),
                    pair_metric_card(html, "Distancia", pair_info.get("dcor") if pair_info else None, "dependencia", "dcor"),
                    html.Div(
                        [
                            html.Span("Obs", className="metric-label"),
                            html.Strong(pair_info.get("obs", "n/d") if pair_info else "n/d"),
                            html.Small("retornos alineados"),
                        ],
                        className="metric obs-wide",
                    ),
                ],
                className="pair-metric-grid",
            ),
        ],
        className="corr-panel pair-focus-card",
    )

def correlation_tab(html: Any, dcc: Any, data_obj: dict[str, Any]) -> Any:
    source = data_obj.get("correlation_source", {})
    tf_options = timeframe_options(source)
    assets = asset_options(source)
    default_tf = "H1" if any(option["value"] == "H1" for option in tf_options) else (tf_options[0]["value"] if tf_options else None)
    default_asset = default_base_asset(source)
    default_other = default_other_asset(source, default_asset)
    default_matrix = default_matrix_assets(source)
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                "i",
                                className="info-icon",
                                style={"marginLeft": "0"},
                                title="Relaciones entre activos por retornos, timeframe y coeficiente.",
                            ),
                            html.H2("Correlacion", className="visually-hidden"),
                        ],
                        className="panel-heading-title-row",
                    ),
                    html.Div(
                        [
                            html.Div([html.Span("Timeframe"), dcc.Dropdown(id="corr-timeframe", options=tf_options, value=default_tf, clearable=False)], className="control-cell"),
                            html.Div([html.Span("Activo base"), dcc.Dropdown(id="corr-asset", options=assets, value=default_asset, clearable=False)], className="control-cell"),
                            html.Div([html.Span("Comparar con"), dcc.Dropdown(id="corr-other-asset", options=assets, value=default_other, clearable=False)], className="control-cell"),
                            html.Div([html.Span("Coeficiente"), dcc.Dropdown(id="corr-metric", options=metric_options(), value="pearson", clearable=False)], className="control-cell"),
                            html.Div(
                                [
                                    html.Span("Activos de la matriz"),
                                    dcc.Dropdown(
                                        id="corr-matrix-assets",
                                        options=assets,
                                        value=default_matrix,
                                        multi=True,
                                        clearable=False,
                                        persistence=True,
                                        persistence_type="session",
                                    ),
                                ],
                                className="control-cell matrix-assets-cell",
                            ),
                        ],
                        className="correlation-controls",
                    ),
                ],
                className="correlation-head",
            ),
            dcc.Tabs(
                id="corr-view",
                value="base",
                className="mini-tabs",
                persistence=True,
                persistence_type="session",
                children=[
                    dcc.Tab(label="Base", value="base", className="mini-tab", selected_className="mini-tab-selected"),
                    dcc.Tab(label="Rolling", value="rolling", className="mini-tab", selected_className="mini-tab-selected"),
                ],
            ),
            html.Div(id="correlation-panel", className="correlation-panel"),
        ],
        className="correlation-shell",
    )
