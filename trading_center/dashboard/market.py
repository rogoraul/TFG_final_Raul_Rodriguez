from __future__ import annotations

from typing import Any

from trading_center.dashboard.formatting import pct, safe_float


def row_field(row: dict[str, Any], *names: str, default: str = "") -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return default


def normalize_trend(value: Any) -> str:
    text = str(value or "").strip().lower()
    bullish = {"bullish", "alcista", "up", "long", "buy", "1", "+1", "positive"}
    bearish = {"bearish", "bajista", "down", "short", "sell", "-1", "negative"}
    if text in bullish:
        return "bullish"
    if text in bearish:
        return "bearish"
    return text or "not_available"


def normalize_extreme_state(row: dict[str, Any]) -> str:
    state = row_field(
        row,
        "oscillator_state",
        "rsi_state",
        "extreme_state",
        "momentum_state",
        "overbought_oversold_state",
    ).lower()
    if state in {"overbought", "sobrecompra", "rsi_overbought", "stoch_overbought"}:
        return "overbought"
    if state in {"oversold", "sobreventa", "rsi_oversold", "stoch_oversold"}:
        return "oversold"
    rsi_text = row_field(row, "rsi_h1", "rsi", "rsi_value", "oscillator_value")
    try:
        rsi = float(rsi_text)
    except (TypeError, ValueError):
        return state or "neutral"
    if rsi >= 70:
        return "overbought"
    if rsi <= 30:
        return "oversold"
    return "neutral"


def trend_display(value: str) -> str:
    if value == "bullish":
        return "↑"
    if value == "bearish":
        return "↓"
    return "~"


def trend_tone(value: str) -> str:
    if value == "bullish":
        return "up"
    if value == "bearish":
        return "down"
    return "muted"


def signal_arrow(value: str) -> str:
    if str(value).startswith("bullish"):
        return "↑"
    if str(value).startswith("bearish"):
        return "↓"
    return ""


def signal_tone(value: str) -> str:
    if str(value).startswith("bullish"):
        return "up"
    if str(value).startswith("bearish"):
        return "down"
    return "muted"


def signal_from_context(trends: set[str], extreme: str) -> str:
    if trends == {"bearish"} and extreme == "overbought":
        return "bearish_overbought"
    if trends == {"bullish"} and extreme == "oversold":
        return "bullish_oversold"
    return ""


def rsi_tone(value: str) -> str:
    text = str(value).strip().split()[-1] if str(value).strip() else ""
    try:
        rsi = float(text)
    except ValueError:
        return ""
    if rsi > 70:
        return "high"
    if rsi < 30:
        return "low"
    return ""


def market_strength(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for key, label in [("m15_trend", "M15"), ("h1_trend", "H1"), ("h4_trend", "H4"), ("d1_trend", "D1")]:
        trends = [normalize_trend(row_field(row, key)) for row in rows]
        total = len(trends)
        bullish = sum(1 for value in trends if value == "bullish")
        bearish = sum(1 for value in trends if value == "bearish")
        neutral = max(total - bullish - bearish, 0)
        if bullish > bearish and bullish >= neutral:
            dominant = "alcista"
            tone = "up"
            dominant_pct = pct(bullish, total)
        elif bearish > bullish and bearish >= neutral:
            dominant = "bajista"
            tone = "down"
            dominant_pct = pct(bearish, total)
        else:
            dominant = "mixto"
            tone = "muted"
            dominant_pct = pct(neutral, total)
        output.append(
            {
                "timeframe": label,
                "total": total,
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral,
                "bullish_pct": pct(bullish, total),
                "bearish_pct": pct(bearish, total),
                "neutral_pct": pct(neutral, total),
                "dominant": dominant,
                "dominant_pct": dominant_pct,
                "tone": tone,
            }
        )
    return output


def market_mode(strength: list[dict[str, Any]]) -> dict[str, str]:
    by_tf = {row["timeframe"]: row for row in strength}
    h4 = by_tf.get("H4") or {}
    d1 = by_tf.get("D1") or {}
    h4_dom = h4.get("dominant", "mixto")
    d1_dom = d1.get("dominant", "mixto")
    if h4_dom == d1_dom and h4_dom in {"alcista", "bajista"}:
        return {"label": f"Fondo {h4_dom}", "detail": f"H4 y D1 dominan en modo {h4_dom}.", "tone": h4.get("tone", "muted")}
    if h4_dom in {"alcista", "bajista"}:
        return {"label": f"H4 {h4_dom}", "detail": f"D1 no acompana de forma clara; mercado mas tactico.", "tone": h4.get("tone", "muted")}
    return {"label": "Mercado mixto", "detail": "No hay dominio claro en los timeframes altos.", "tone": "muted"}


def volatility_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked: list[dict[str, Any]] = []
    for row in rows:
        atr_h1 = safe_float(row_field(row, "atr_pct_h1"))
        atr_median_h1 = safe_float(row_field(row, "atr_pct_h1_median"))
        atr_ratio_h1 = safe_float(row_field(row, "atr_pct_h1_ratio"))
        score = atr_ratio_h1
        if score is None:
            continue
        ranked.append(
            {
                "symbol": row_field(row, "symbol"),
                "market_group": row_field(row, "market_group", "group", default="not_available"),
                "atr_pct_h1": f"{atr_h1:.2f}" if atr_h1 is not None else "",
                "atr_pct_h1_median": f"{atr_median_h1:.2f}" if atr_median_h1 is not None else "",
                "atr_pct_h1_ratio": f"{atr_ratio_h1:.2f}" if atr_ratio_h1 is not None else "",
                "atr_pct_h1_sample_count": row_field(row, "atr_pct_h1_sample_count"),
                "score": score,
                "tone": "muted",
                "state": "normal",
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    total = len(ranked)
    if not total:
        return {"hot_assets": [], "quiet_assets": [], "summary": {"label": "Sin volatilidad", "detail": "No hay ATR% disponible.", "tone": "muted"}}
    hot_limit = max(1, int(round(total * 0.15)))
    warm_limit = max(hot_limit + 1, int(round(total * 0.35)))
    quiet_start = max(0, int(round(total * 0.8)))
    for index, item in enumerate(ranked):
        if index < hot_limit:
            item["state"] = "muy movido"
            item["tone"] = "hot"
        elif index < warm_limit:
            item["state"] = "activo"
            item["tone"] = "warm"
        elif index >= quiet_start:
            item["state"] = "tranquilo"
            item["tone"] = "quiet"
        else:
            item["state"] = "normal"
            item["tone"] = "muted"
    hot_assets = ranked[:6]
    quiet_assets = list(reversed(ranked[-6:]))
    summary = {
        "label": "ATR vs mediana",
        "detail": "Ranking normalizado por activo, no por familia de mercado.",
        "tone": "hot" if ranked else "muted",
    }
    return {"hot_assets": hot_assets, "quiet_assets": quiet_assets, "summary": summary}


def trend_distribution(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    trends = [normalize_trend(row_field(row, key)) for row in rows]
    total = len(trends)
    bullish = sum(1 for value in trends if value == "bullish")
    bearish = sum(1 for value in trends if value == "bearish")
    mixed = max(total - bullish - bearish, 0)
    if bullish > bearish and bullish >= mixed:
        dominant = "alcista"
        tone = "up"
        dominant_pct = pct(bullish, total)
    elif bearish > bullish and bearish >= mixed:
        dominant = "bajista"
        tone = "down"
        dominant_pct = pct(bearish, total)
    else:
        dominant = "mixto"
        tone = "muted"
        dominant_pct = pct(mixed, total)
    return {
        "total": total,
        "bullish": bullish,
        "bearish": bearish,
        "mixed": mixed,
        "bullish_pct": pct(bullish, total),
        "bearish_pct": pct(bearish, total),
        "mixed_pct": pct(mixed, total),
        "dominant": dominant,
        "dominant_pct": dominant_pct,
        "tone": tone,
    }


def family_strength(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family = row_field(row, "market_group", "group", default="Sin grupo")
        by_family.setdefault(family, []).append(row)
    output: list[dict[str, Any]] = []
    for family, family_rows in by_family.items():
        h1 = trend_distribution(family_rows, "h1_trend")
        h4 = trend_distribution(family_rows, "h4_trend")
        d1 = trend_distribution(family_rows, "d1_trend")
        output.append(
            {
                "family": family,
                "total": len(family_rows),
                "h1": h1,
                "h4": h4,
                "d1": d1,
                "tone": h4["tone"] if h4["tone"] != "muted" else d1["tone"],
                "dominant": h4["dominant"],
                "dominant_pct": h4["dominant_pct"],
            }
        )
    output.sort(key=lambda item: (-int(item["total"]), str(item["family"])))
    return output


def alignment_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    full = 0
    tactical = 0
    higher = 0
    m15_vs_d1_conflict = 0
    no_clear = 0
    for row in rows:
        m15 = normalize_trend(row_field(row, "m15_trend"))
        h1 = normalize_trend(row_field(row, "h1_trend"))
        h4 = normalize_trend(row_field(row, "h4_trend"))
        d1 = normalize_trend(row_field(row, "d1_trend"))
        m15_h1_h4 = {m15, h1, h4}
        h1_h4_d1 = {h1, h4, d1}
        all_four = {m15, h1, h4, d1}
        if all_four == {"bullish"} or all_four == {"bearish"}:
            full += 1
        elif m15_h1_h4 == {"bullish"} or m15_h1_h4 == {"bearish"}:
            tactical += 1
        elif h1_h4_d1 == {"bullish"} or h1_h4_d1 == {"bearish"}:
            higher += 1
        else:
            no_clear += 1
        if m15 in {"bullish", "bearish"} and d1 in {"bullish", "bearish"} and m15 != d1:
            m15_vs_d1_conflict += 1
    return {
        "total": total,
        "full_alignment": full,
        "tactical_alignment": tactical,
        "higher_alignment": higher,
        "m15_vs_d1_conflict": m15_vs_d1_conflict,
        "no_clear_alignment": no_clear,
        "full_pct": pct(full, total),
        "tactical_pct": pct(tactical, total),
        "higher_pct": pct(higher, total),
        "conflict_pct": pct(m15_vs_d1_conflict, total),
        "no_clear_pct": pct(no_clear, total),
    }


def volatility_pressure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ratios: list[tuple[dict[str, Any], float]] = []
    by_family: dict[str, dict[str, int]] = {}
    for row in rows:
        ratio = safe_float(row_field(row, "atr_pct_h1_ratio"))
        if ratio is None:
            continue
        ratios.append((row, ratio))
        family = row_field(row, "market_group", "group", default="Sin grupo")
        bucket = by_family.setdefault(family, {"family": family, "hot": 0, "normal": 0, "compressed": 0, "total": 0})
        bucket["total"] += 1
        if ratio > 1.5:
            bucket["hot"] += 1
        elif ratio < 0.75:
            bucket["compressed"] += 1
        else:
            bucket["normal"] += 1
    total = len(ratios)
    hot = sum(1 for _, ratio in ratios if ratio > 1.5)
    compressed = sum(1 for _, ratio in ratios if ratio < 0.75)
    normal = max(total - hot - compressed, 0)
    family_rows = list(by_family.values())
    for row in family_rows:
        row["hot_pct"] = pct(row["hot"], row["total"])
        row["compressed_pct"] = pct(row["compressed"], row["total"])
    family_rows.sort(key=lambda item: (-int(item["hot"]), -int(item["compressed"]), str(item["family"])))
    return {
        "total": total,
        "hot": hot,
        "normal": normal,
        "compressed": compressed,
        "hot_pct": pct(hot, total),
        "normal_pct": pct(normal, total),
        "compressed_pct": pct(compressed, total),
        "families": family_rows,
    }


def market_radar_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trend_aligned: list[dict[str, Any]] = []
    rsi_screener: list[dict[str, Any]] = []
    strength = market_strength(rows)
    for raw in rows:
        m15 = normalize_trend(row_field(raw, "m15_trend", "trend_m15", "M15_trend", "trend_M15"))
        h1 = normalize_trend(row_field(raw, "h1_trend", "trend_h1", "H1_trend", "trend_H1"))
        h4 = normalize_trend(row_field(raw, "h4_trend", "trend_h4", "H4_trend", "trend_H4"))
        d1 = normalize_trend(row_field(raw, "d1_trend", "trend_d1", "D1_trend", "trend_D1"))
        h1_h4_d1 = {h1, h4, d1}
        m15_h1_h4 = {m15, h1, h4}
        if h1_h4_d1 == {"bullish"} or m15_h1_h4 == {"bullish"}:
            alignment = "bullish_aligned"
            icon = "↑"
            tone = "up"
        elif h1_h4_d1 == {"bearish"} or m15_h1_h4 == {"bearish"}:
            alignment = "bearish_aligned"
            icon = "↓"
            tone = "down"
        else:
            alignment = ""
            icon = ""
            tone = "muted"
        extreme_state = normalize_extreme_state(raw)
        row = {
            "icon": row_field(raw, "icon", default=icon),
            "symbol": row_field(raw, "symbol"),
            "market_group": row_field(raw, "market_group", "group", default="not_available"),
            "h1": trend_display(h1),
            "h4": trend_display(h4),
            "d1": trend_display(d1),
            "m15": trend_display(m15),
            "m15_tone": trend_tone(m15),
            "h1_tone": trend_tone(h1),
            "h4_tone": trend_tone(h4),
            "d1_tone": trend_tone(d1),
            "extreme_state": extreme_state,
            "rsi": row_field(raw, "rsi_h1", "rsi", "rsi_value", default="not_available"),
            "rsi_tone": rsi_tone(row_field(raw, "rsi_h1", "rsi", "rsi_value", default="")),
            "as_of": row_field(raw, "as_of", "generated_at", "last_closed_bar_time", "timestamp", default="not_available"),
            "note": row_field(raw, "note", "radar_reason", "reason", default="trend_alignment"),
            "alignment": alignment,
            "tone": tone,
        }
        if alignment:
            trend_aligned.append(row)
        signals = {
            "m15": row_field(raw, "m15_rsi_signal"),
            "h1": row_field(raw, "h1_rsi_signal"),
            "h4": row_field(raw, "h4_rsi_signal"),
            "d1": row_field(raw, "d1_rsi_signal"),
        }
        if any(signals.values()):
            signal_row = dict(row)
            signal_row["m15"] = signal_arrow(signals["m15"])
            signal_row["h1"] = signal_arrow(signals["h1"])
            signal_row["h4"] = signal_arrow(signals["h4"])
            signal_row["d1"] = signal_arrow(signals["d1"])
            signal_row["m15_tone"] = signal_tone(signals["m15"])
            signal_row["h1_tone"] = signal_tone(signals["h1"])
            signal_row["h4_tone"] = signal_tone(signals["h4"])
            signal_row["d1_tone"] = signal_tone(signals["d1"])
            signal_row["rsi"] = row_field(raw, "rsi_signal_value", "rsi_h1", default="not_available")
            signal_row["rsi_tone"] = rsi_tone(signal_row["rsi"])
            signal_row["icon"] = signal_arrow(next(signal for signal in signals.values() if signal))
            signal_row["tone"] = signal_tone(next(signal for signal in signals.values() if signal))
            rsi_screener.append(signal_row)
    return {
        "trend_aligned": trend_aligned,
        "counter_extremes": rsi_screener,
        "rsi_screener": rsi_screener,
        "strength": strength,
        "market_mode": market_mode(strength),
        "volatility": volatility_profile(rows),
        "family_strength": family_strength(rows),
        "alignment_quality": alignment_quality(rows),
        "volatility_pressure": volatility_pressure(rows),
    }


def strength_meter(html: Any, row: dict[str, Any]) -> Any:
    bullish = int(row.get("bullish_pct", 0))
    bearish = int(row.get("bearish_pct", 0))
    neutral = max(0, 100 - bullish - bearish)
    return html.Div(
        [
            html.Div(
                [
                    html.Strong(row.get("timeframe", "")),
                    html.Span(f"{row.get('dominant', 'mixto')} {row.get('dominant_pct', 0)}%"),
                ],
                className="strength-head",
            ),
            html.Div(
                [
                    html.Span(className="strength-segment up", style={"width": f"{bullish}%"}),
                    html.Span(className="strength-segment muted", style={"width": f"{neutral}%"}),
                    html.Span(className="strength-segment down", style={"width": f"{bearish}%"}),
                ],
                className="strength-bar",
            ),
            html.Div(
                [
                    html.Span(f"^ {row.get('bullish', 0)}"),
                    html.Span(f"~ {row.get('neutral', 0)}"),
                    html.Span(f"v {row.get('bearish', 0)}"),
                ],
                className="strength-counts",
            ),
        ],
        className=f"strength-row {row.get('tone', 'muted')}",
    )

def tf_strip(html: Any, row: dict[str, Any]) -> Any:
    return html.Div(
        [
            html.Span([html.Em("M15"), html.B(row.get("m15", "~"))], className=f"tf-cell {row.get('m15_tone', 'muted')}"),
            html.Span([html.Em("H1"), html.B(row.get("h1", "~"))], className=f"tf-cell {row.get('h1_tone', 'muted')}"),
            html.Span([html.Em("H4"), html.B(row.get("h4", "~"))], className=f"tf-cell {row.get('h4_tone', 'muted')}"),
            html.Span([html.Em("D1"), html.B(row.get("d1", "~"))], className=f"tf-cell {row.get('d1_tone', 'muted')}"),
        ],
        className="tf-strip",
    )

def radar_asset_card(html: Any, row: dict[str, Any]) -> Any:
    rsi_text = row.get("rsi", "n/d") or "n/d"
    return html.Article(
        [
            html.Div(
                [
                    html.Span(row.get("icon", ""), className=f"asset-direction {row.get('tone', 'muted')}"),
                    html.Div([html.Strong(row.get("symbol", "")), html.Small(row.get("market_group", ""))]),
                ],
                className="asset-card-head",
            ),
            tf_strip(html, row),
            html.Div(
                [
                    html.Span("RSI", className="mini-label"),
                    html.Strong(rsi_text, className=f"rsi-value {row.get('rsi_tone', '')}"),
                ],
                className="asset-card-foot",
            ),
        ],
        className=f"asset-card {row.get('tone', 'muted')}",
    )

def volatility_rank_row(html: Any, row: dict[str, Any], index: int, mode: str) -> Any:
    suffix = "%" if row.get("atr_pct_h1") else ""
    ratio_suffix = "x" if row.get("atr_pct_h1_ratio") else ""
    ratio_label = "Exceso" if mode == "hot" else "Ratio"
    return html.Div(
        [
            html.Span(f"{index:02d}", className="rank-number"),
            html.Div([html.Strong(row.get("symbol", "")), html.Small(row.get("market_group", ""))], className="rank-symbol"),
            html.Div(
                [
                    html.Span([html.Em(ratio_label), html.B(f"{row.get('atr_pct_h1_ratio') or 'n/d'}{ratio_suffix}")]),
                    html.Span([html.Em("ATR"), html.B(f"{row.get('atr_pct_h1') or 'n/d'}{suffix}")]),
                ],
                className="rank-metrics",
            ),
        ],
        className=f"vol-rank-row {mode}",
    )

def reading_row(html: Any, label: str, value: Any, percentage: Any, tone: str, note: str) -> Any:
    return html.Div(
        [
            html.Div([html.Strong(label), html.Small(note)], className="reading-copy"),
            html.Div([html.B(str(value)), html.Em(f"{percentage}%")], className=f"reading-number {tone}"),
        ],
        className="reading-row",
    )

def pressure_bar(html: Any, pressure: dict[str, Any]) -> Any:
    hot = int(pressure.get("hot_pct", 0))
    compressed = int(pressure.get("compressed_pct", 0))
    normal = max(0, 100 - hot - compressed)
    return html.Div(
        [
            html.Span(className="pressure-segment hot", style={"width": f"{hot}%"}),
            html.Span(className="pressure-segment normal", style={"width": f"{normal}%"}),
            html.Span(className="pressure-segment quiet", style={"width": f"{compressed}%"}),
        ],
        className="pressure-bar",
    )

def alignment_reading(html: Any, quality: dict[str, Any]) -> Any:
    total = int(quality.get("total", 0) or 0)
    if total <= 0:
        return html.Div("Sin lectura disponible. Regenera el radar de mercado para ver alineaciones.", className="radar-empty")
    tactical_count = int(quality.get("tactical_alignment", 0) or 0) + int(quality.get("higher_alignment", 0) or 0)
    tactical_pct = pct(tactical_count, total)
    return html.Div(
        [
            reading_row(html, 
                "Alineacion limpia",
                quality.get("full_alignment", 0),
                quality.get("full_pct", 0),
                "up",
                "M15, H1, H4 y D1 apuntan igual.",
            ),
            reading_row(html, 
                "Alineacion tactica",
                tactical_count,
                tactical_pct,
                "muted",
                "Hay acuerdo parcial entre timeframes clave.",
            ),
            reading_row(html, 
                "Conflicto corto/largo",
                quality.get("m15_vs_d1_conflict", 0),
                quality.get("conflict_pct", 0),
                "down",
                "M15 va contra D1; requiere mas cuidado.",
            ),
        ],
        className="reading-list",
    )

def volatility_reading(html: Any, pressure: dict[str, Any]) -> Any:
    total = int(pressure.get("total", 0) or 0)
    if total <= 0:
        return html.Div("Sin lectura disponible. Falta ATR% frente a mediana propia.", className="radar-empty")
    return html.Div(
        [
            pressure_bar(html, pressure),
            html.Div(
                [
                    reading_row(html, 
                        "Movimiento alto",
                        pressure.get("hot", 0),
                        pressure.get("hot_pct", 0),
                        "hot",
                        "Por encima de 1.5x su ATR mediano.",
                    ),
                    reading_row(html, 
                        "Movimiento normal",
                        pressure.get("normal", 0),
                        pressure.get("normal_pct", 0),
                        "muted",
                        "Dentro de la zona habitual del activo.",
                    ),
                    reading_row(html, 
                        "Movimiento comprimido",
                        pressure.get("compressed", 0),
                        pressure.get("compressed_pct", 0),
                        "quiet",
                        "Por debajo de 0.75x su ATR mediano.",
                    ),
                ],
                className="reading-list",
            ),
        ]
    )



def asset_card_grid(html: Any, title: str, subtitle: str, rows: list[dict[str, Any]], empty_text: str, limit: int = 10) -> Any:
    content: Any
    if rows:
        content = html.Div([radar_asset_card(html, row) for row in rows[:limit]], className="asset-card-grid")
    else:
        content = html.Div(empty_text, className="radar-empty")
    return html.Section(
        [
            html.Div([html.H2(title), html.P(subtitle)], className="panel-heading"),
            content,
        ],
        className="radar-section",
    )

def overview_tab(html: Any, data_obj: dict[str, Any]) -> Any:
    radar = data_obj.get("market_radar_summary", {"trend_aligned": [], "counter_extremes": []})
    radar_source = data_obj.get("market_radar_source", {})
    strength = radar.get("strength", [])
    mode = radar.get("market_mode", {"label": "Sin lectura", "detail": "Mercado no disponible.", "tone": "muted"})
    volatility = radar.get("volatility", {"hot_assets": [], "quiet_assets": [], "summary": {}})
    quality = radar.get("alignment_quality", {})
    pressure = radar.get("volatility_pressure", {})
    trend_rows = radar.get("trend_aligned", [])
    rsi_rows = radar.get("rsi_screener", radar.get("counter_extremes", []))
    volatility_summary = volatility.get("summary", {})
    return html.Div(
        [
            html.Section(
                [
                    html.Div(
                        [
                            html.Span("Pulso", className="radar-kicker"),
                            html.H2(mode.get("label", "Sin lectura")),
                            html.P(mode.get("detail", "Mercado no disponible.")),
                        ],
                        className=f"pulse-card {mode.get('tone', 'muted')}",
                    ),
                    html.Div(
                        [
                            html.Span("Universo", className="radar-kicker"),
                            html.Strong(str(radar_source.get("rows", 0))),
                            html.Small(f"{len(trend_rows)} activos alineados"),
                        ],
                        className="pulse-stat",
                    ),
                    html.Div(
                        [
                            html.Span("Volatilidad", className="radar-kicker"),
                            html.Strong(volatility_summary.get("label", "Sin ATR")),
                            html.Small(volatility_summary.get("detail", "No hay ATR% disponible.")),
                        ],
                        className=f"pulse-stat {volatility_summary.get('tone', 'muted')}",
                    ),
                ],
                className="radar-hero",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div([html.H2("Fuerza del universo"), html.P("Distribucion alcista, mixta y bajista por timeframe.")], className="panel-heading"),
                            html.Div([strength_meter(html, row) for row in strength], className="strength-stack"),
                        ],
                        className="radar-section strength-panel",
                    ),
                    html.Div(
                        [
                            html.Div([html.H2("Volatilidad"), html.P("ATR H1 actual comparado contra la mediana propia de cada activo.")], className="panel-heading"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div([html.Strong("Mas movidos"), html.Small("Exceso vs mediana")], className="rank-title hot"),
                                            html.Div(
                                                [volatility_rank_row(html, row, index, "hot") for index, row in enumerate(volatility.get("hot_assets", [])[:6], start=1)]
                                                or [html.Div("Sin lecturas de volatilidad disponibles.", className="radar-empty")],
                                                className="vol-rank-list",
                                            ),
                                        ],
                                        className="vol-rank-panel",
                                    ),
                                    html.Div(
                                        [
                                            html.Div([html.Strong("Menos movidos"), html.Small("Carencia vs mediana")], className="rank-title quiet"),
                                            html.Div(
                                                [volatility_rank_row(html, row, index, "quiet") for index, row in enumerate(volatility.get("quiet_assets", [])[:6], start=1)]
                                                or [html.Div("Sin lecturas tranquilas disponibles.", className="radar-empty")],
                                                className="vol-rank-list",
                                            ),
                                        ],
                                        className="vol-rank-panel",
                                    ),
                                ],
                                className="vol-rank-grid",
                            ),
                        ],
                        className="radar-section volatility-panel",
                    ),
                ],
                className="radar-dashboard-grid",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div([html.H2("Lectura de mercado"), html.P("Resumen de alineacion, sin convertirlo en senal.")], className="panel-heading"),
                            alignment_reading(html, quality),
                        ],
                        className="radar-section reading-panel",
                    ),
                    html.Div(
                        [
                            html.Div([html.H2("Movimiento del universo"), html.P("ATR H1 contra la mediana propia de cada activo.")], className="panel-heading"),
                            volatility_reading(html, pressure),
                        ],
                        className="radar-section reading-panel",
                    ),
                ],
                className="radar-insight-grid",
            ),
        ]
    )
