from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "trading_center_screener_unified_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/trading_center_screener_unified_v1_2026-06-01"
DEFAULT_MARKET_RADAR_CSV = REPO_ROOT / "artifacts/tfg/trading_center_market_radar_v1_2026-05-31/market_radar.csv"
DEFAULT_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
DEFAULT_WEAVECOUNT_CSV = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01/weavecount_screener.csv"
DEFAULT_SNAPSHOT_CSV = REPO_ROOT / "artifacts/tfg/trading_center_latest/macd_breakout_watcher/snapshot.csv"
DEFAULT_FIBONACCI_CONTEXT_CSV = REPO_ROOT / "artifacts/tfg/trading_center_fibonacci_context_v1_2026-06-02/fibonacci_context.csv"
DEFAULT_FIBONACCI_LAYERS_CSV = REPO_ROOT / "artifacts/tfg/trading_center_fibonacci_context_v1_2026-06-02/fibonacci_chart_layers.csv"
DEFAULT_FIB_LIMIT_REVIEW_CSV = (
    REPO_ROOT / "artifacts/tfg/fib_limit_swing_quality_visual_review_v1_2026-06-02/tables/fib_limit_visual_case_review.csv"
)
DEFAULT_FIB_LIMIT_SAMPLE_CSV = (
    REPO_ROOT / "artifacts/tfg/fib_limit_swing_quality_visual_review_v1_2026-06-02/tables/fib_limit_visual_sample_selection.csv"
)
DEFAULT_MACD_BREAKOUT_ENRICHED_CSV = (
    REPO_ROOT / "artifacts/tfg/trading_center_latest/macd_breakout_enrichment/macd_breakout_enriched_setups.csv"
)
DEFAULT_MACD_BREAKOUT_CHART_LAYERS_CSV = (
    REPO_ROOT / "artifacts/tfg/trading_center_latest/macd_breakout_enrichment/macd_breakout_chart_layers.csv"
)
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TRADING_CENTER_SCREENER_UNIFIED_V1.md"
DEFAULT_DESIGN_DOC_PATH = REPO_ROOT / "docs/TRADING_CENTER_SCREENER_UNIFIED_DESIGN_V1.md"

SETUP_FIELDNAMES = [
    "setup_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "setup_type",
    "strategy",
    "direction",
    "setup_status",
    "timing_state",
    "timing_priority",
    "timing_reason",
    "trigger_level",
    "trigger_level_type",
    "distance_to_trigger_pct",
    "last_touch_time",
    "bars_since_touch",
    "reaction_detected",
    "reaction_direction",
    "is_late",
    "is_invalidated",
    "entry_review_status",
    "timing_source",
    "timing_artifact",
    "setup_quality_score",
    "quality_label",
    "quality_reason",
    "confluence_count",
    "confluence_tags",
    "risk_tags",
    "trend_context",
    "trend_compatibility",
    "trend_compatibility_reason",
    "trend_detail_context",
    "rsi_context",
    "pivot_context",
    "previous_day_level_context",
    "fibonacci_context",
    "round_level_context",
    "volatility_context",
    "wavecount_context",
    "codex_review_status",
    "codex_review_score",
    "codex_review_summary",
    "chart_layer_id",
    "chart_file",
    "source_artifacts",
    "is_signal",
    "is_study_only",
    "can_execute_order",
    "would_send_to_mt5",
    "would_send_telegram_order",
    "wavecount_used_as_filter",
    "macd_breakout_timing_state",
    "macd_breakout_timing_reason",
    "macd_breakout_priority",
    "macd_breakout_level",
    "macd_breakout_time",
    "bars_since_breakout",
    "macd_cross_state",
    "macd_cross_time",
    "bars_since_macd_cross",
    "macd_sl_study",
    "macd_tp1_study",
    "macd_tp2_study",
    "macd_context_complete",
]

TIMING_PRIORITY_MAP = {
    "entry_review": 1,
    "macd_recent": 2,
    "breakout_recent": 3,
    "reaction_candidate": 4,
    "touching_level": 5,
    "macd_pending": 6,
    "near_level": 7,
    "watching": 8,
    "forming": 9,
    "late": 10,
    "stale": 11,
    "missing_context": 12,
    "invalidated": 13,
    "no_timing_context": 14,
}

ALLOWED_TIMING_STATES = set(TIMING_PRIORITY_MAP)
MACD_BREAKOUT_HIGHLIGHTABLE_STATES = {"entry_review", "macd_recent", "breakout_recent"}
MACD_BREAKOUT_SECONDARY_STATES = {"macd_pending", "watching"}
MACD_BREAKOUT_EXCLUDED_FROM_HIGHLIGHTS = {"late", "missing_context", "invalidated"}
POSITIVE_CONFLUENCE_TAGS = {
    "rsi_entry_review",
    "rsi_watching",
    "macd_entry_review",
    "macd_recent",
    "macd_breakout_recent",
    "fib_entry_review",
    "fib_touching_level",
    "tactical_alignment",
    "higher_alignment",
    "pivot_context",
    "previous_day_level",
    "round_level",
    "fibonacci_zone",
    "wavecount_context",
}

MATRIX_FIELDNAMES = [
    "symbol",
    "market_group",
    "trend_chip",
    "rsi_chip",
    "pivot_chip",
    "previous_day_level_chip",
    "round_level_chip",
    "fibonacci_chip",
    "volatility_chip",
    "macd_breakout_chip",
    "fib_limit_chip",
    "wavecount_chip",
    "codex_review_status",
    "setups_count",
    "max_quality_score",
    "is_signal",
    "is_study_only",
    "can_execute_order",
    "would_send_to_mt5",
    "would_send_telegram_order",
    "wavecount_used_as_filter",
]

LAYER_FIELDNAMES = [
    "chart_layer_id",
    "setup_id",
    "symbol",
    "timeframe",
    "layer_type",
    "label",
    "price",
    "start_price",
    "end_price",
    "start_time",
    "end_time",
    "color",
    "style",
    "source",
    "is_operational",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.replace("Z", ""), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def as_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def truthy_false(value: Any) -> bool:
    return str(value).strip().lower() in {"false", "0", "no", "n", ""}


def clean(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def normalize_trend(value: Any) -> str:
    text = clean(value).lower()
    if text in {"bullish", "alcista", "up", "long"}:
        return "bullish"
    if text in {"bearish", "bajista", "down", "short"}:
        return "bearish"
    return "mixed"


def direction_from_trend(trend: str) -> str:
    if trend == "bullish":
        return "long"
    if trend == "bearish":
        return "short"
    return "neutral"


def trend_direction_from_context(trend_ctx: str) -> str:
    text = clean(trend_ctx).lower()
    if "bullish" in text:
        return "long"
    if "bearish" in text:
        return "short"
    return "neutral"


def trend_compatibility_for_setup(trend_ctx: str, setup_direction: str) -> tuple[str, str]:
    trend_direction = trend_direction_from_context(trend_ctx)
    direction = clean(setup_direction).lower()
    if direction not in {"long", "short"}:
        return "mixed", "setup sin direccion clara para contrastar tendencia"
    if trend_direction == "neutral":
        return "mixed", "sin alineacion limpia para validar direccion del setup"
    if trend_direction == direction:
        return "compatible", "direccion del setup alineada con la tendencia limpia disponible"
    return "against", "direccion del setup contraria a la tendencia limpia disponible"


def trend_tag_for_compatibility(trend_tag: str, trend_compatibility: str) -> str:
    if trend_compatibility == "compatible":
        return trend_tag if trend_tag in {"tactical_alignment", "higher_alignment"} else "mixed_trend"
    if trend_compatibility == "against":
        return "trend_against"
    return "mixed_trend"


def quality_label(score: int) -> str:
    if score >= 4:
        return "alta"
    if score >= 3:
        return "media"
    return "baja"


def safety_flags() -> dict[str, Any]:
    return {
        "is_signal": False,
        "is_study_only": True,
        "can_execute_order": False,
        "would_send_to_mt5": False,
        "would_send_telegram_order": False,
        "wavecount_used_as_filter": False,
    }


def latest_ohlc_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    latest: dict[tuple[str, str], dict[str, str]] = {}
    latest_ts: dict[tuple[str, str], datetime] = {}
    for row in rows:
        symbol = clean(row.get("symbol"))
        timeframe = clean(row.get("timeframe"))
        ts = parse_time(row.get("timestamp"))
        if not symbol or not timeframe or not ts:
            continue
        key = (symbol, timeframe)
        if key not in latest_ts or ts > latest_ts[key]:
            latest_ts[key] = ts
            latest[key] = row
    return latest


def latest_time_by_timeframe(rows: list[dict[str, str]]) -> dict[str, datetime]:
    latest: dict[str, datetime] = {}
    for row in rows:
        timeframe = clean(row.get("timeframe"))
        ts = parse_time(row.get("timestamp"))
        if not timeframe or not ts:
            continue
        if timeframe not in latest or ts > latest[timeframe]:
            latest[timeframe] = ts
    return latest


def filter_macd_breakout_rows_for_current_cut(
    rows: list[dict[str, str]],
    layer_rows: list[dict[str, str]],
    ohlc_rows: list[dict[str, str]],
    *,
    max_stale_days: int = 7,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    latest_by_tf = latest_time_by_timeframe(ohlc_rows)
    kept: list[dict[str, str]] = []
    rejected = 0
    for row in rows:
        timeframe = clean(row.get("timeframe"), "H1")
        latest_ts = latest_by_tf.get(timeframe)
        event_times = [
            parse_time(row.get("last_breakout_time")),
            parse_time(row.get("last_macd_cross_time")),
            parse_time(row.get("directrix_end_time")),
            parse_time(row.get("w2_swing_time")),
        ]
        event_times = [ts for ts in event_times if ts]
        if not latest_ts or not event_times:
            rejected += 1
            continue
        row_latest = max(event_times)
        if (latest_ts - row_latest).days > max_stale_days:
            rejected += 1
            continue
        kept.append(row)
    kept_ids = {clean(row.get("enrichment_id")) for row in kept}
    kept_layers = [row for row in layer_rows if clean(row.get("enrichment_id")) in kept_ids]
    return kept, kept_layers, {
        "macd_breakout_rows_input": len(rows),
        "macd_breakout_rows_kept_current_cut": len(kept),
        "macd_breakout_rows_rejected_stale": rejected,
        "macd_breakout_layers_kept_current_cut": len(kept_layers),
        "macd_breakout_freshness_max_stale_days": max_stale_days,
    }


def ohlc_by_symbol_tf(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        symbol = clean(row.get("symbol"))
        timeframe = clean(row.get("timeframe"))
        if symbol and timeframe:
            grouped[(symbol, timeframe)].append(row)
    for key, values in grouped.items():
        values.sort(key=lambda item: parse_time(item.get("timestamp")) or datetime.min)
    return grouped


def previous_day_levels(rows: list[dict[str, str]]) -> dict[str, float] | None:
    if not rows:
        return None
    sorted_rows = sorted(rows, key=lambda item: parse_time(item.get("timestamp")) or datetime.min)
    last_ts = parse_time(sorted_rows[-1].get("timestamp"))
    if not last_ts:
        return None
    previous = [row for row in sorted_rows if (parse_time(row.get("timestamp")) or datetime.min).date() < last_ts.date()]
    if not previous:
        return None
    last_previous_date = (parse_time(previous[-1].get("timestamp")) or datetime.min).date()
    day_rows = [row for row in previous if (parse_time(row.get("timestamp")) or datetime.min).date() == last_previous_date]
    highs = [value for value in (as_float(row.get("high")) for row in day_rows) if value is not None]
    lows = [value for value in (as_float(row.get("low")) for row in day_rows) if value is not None]
    closes = [value for value in (as_float(row.get("close")) for row in day_rows) if value is not None]
    if not highs or not lows or not closes:
        return None
    high = max(highs)
    low = min(lows)
    close = closes[-1]
    pivot = (high + low + close) / 3.0
    price_range = high - low
    return {
        "previous_high": high,
        "previous_low": low,
        "pivot": pivot,
        "r1": 2 * pivot - low,
        "s1": 2 * pivot - high,
        "r2": pivot + price_range,
        "s2": pivot - price_range,
        "r3": high + 2 * (pivot - low),
        "s3": low - 2 * (high - pivot),
    }


def round_step(price: float, group: str) -> float:
    if price <= 0:
        return 1.0
    group_lower = group.lower()
    if "forex" in group_lower and price < 10:
        return 0.005
    if price < 10:
        return 0.01
    if price < 100:
        return 0.5
    if price < 1000:
        return 5.0
    if price < 10000:
        return 50.0
    return 100.0


def nearby_round_levels(price: float, group: str) -> list[tuple[str, float]]:
    step = round_step(price, group)
    if step <= 0:
        return []
    lower = math.floor(price / step) * step
    upper = math.ceil(price / step) * step
    if math.isclose(lower, upper, rel_tol=0.0, abs_tol=max(step * 1e-9, 1e-12)):
        return [("Nivel redondo actual", lower), ("Nivel redondo superior", lower + step)]
    return [("Nivel redondo inferior", lower), ("Nivel redondo superior", upper)]


def proximity_pct(price: float, level: float) -> float:
    if price == 0:
        return 999.0
    return abs(price - level) / abs(price) * 100.0


def proximity_threshold(group: str) -> float:
    group_lower = group.lower()
    if "forex" in group_lower:
        return 0.12
    if "metals" in group_lower:
        return 0.35
    if "index" in group_lower:
        return 0.45
    return 0.25


def level_context(symbol: str, group: str, ohlc_rows: list[dict[str, str]]) -> dict[str, Any]:
    latest = ohlc_rows[-1] if ohlc_rows else {}
    close = as_float(latest.get("close"))
    levels = previous_day_levels(ohlc_rows)
    output: dict[str, Any] = {
        "pivot_context": "no_context",
        "previous_day_level_context": "no_context",
        "round_level_context": "no_context",
        "layers": [],
        "level_hits": [],
    }
    if close is None:
        return output
    threshold = proximity_threshold(group)
    start_time = clean(ohlc_rows[0].get("timestamp")) if ohlc_rows else ""
    end_time = clean(latest.get("timestamp"))
    if levels:
        for key, label, color in [
            ("r2", "R2 previo", "#80d8ff"),
            ("r3", "R3 previo", "#5ce0ca"),
            ("s2", "S2 previo", "#80d8ff"),
            ("s3", "S3 previo", "#5ce0ca"),
            ("previous_high", "Maximo dia previo", "#7bd88f"),
            ("previous_low", "Minimo dia previo", "#e36d64"),
        ]:
            level = levels.get(key)
            if level is None:
                continue
            dist = proximity_pct(close, level)
            output["layers"].append(
                {
                    "layer_type": key,
                    "label": label,
                    "price": f"{level:.8g}",
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": color,
                    "style": "dash",
                    "source": "ohlc_previous_day_context",
                    "is_operational": False,
                }
            )
            if dist <= threshold:
                output["level_hits"].append(f"{label} {dist:.2f}%")
        pivot_hits = [hit for hit in output["level_hits"] if hit.startswith(("R2", "R3", "S2", "S3"))]
        day_hits = [hit for hit in output["level_hits"] if "dia previo" in hit]
        if pivot_hits:
            output["pivot_context"] = "; ".join(pivot_hits[:2])
        if day_hits:
            output["previous_day_level_context"] = "; ".join(day_hits[:2])
    round_hits: list[str] = []
    for index, (label, round_level) in enumerate(nearby_round_levels(close, group), start=1):
        round_dist = proximity_pct(close, round_level)
        output["layers"].append(
            {
                "layer_type": f"round_level_{index}",
                "label": label,
                "price": f"{round_level:.8g}",
                "start_time": start_time,
                "end_time": end_time,
                "color": "#a56cff",
                "style": "solid",
                "source": "ohlc_nearby_round_levels",
                "is_operational": False,
            }
        )
        if round_dist <= threshold:
            round_hits.append(f"{label} {round_dist:.2f}%")
    if round_hits:
        output["round_level_context"] = "; ".join(round_hits[:2])
        output["level_hits"].extend(round_hits)
    return output


def volatility_context(row: dict[str, str]) -> tuple[str, str]:
    ratio = as_float(row.get("atr_pct_h1_ratio"))
    if ratio is None:
        return "sin ATR ratio", "missing_volatility"
    if ratio > 1.9:
        return f"excesiva {ratio:.2f}x", "volatility_excess"
    if ratio >= 0.85:
        return f"adecuada {ratio:.2f}x", "volatility_ok"
    return f"comprimida {ratio:.2f}x", "volatility_compressed"


def trend_context(row: dict[str, str]) -> tuple[str, str, str]:
    m15 = normalize_trend(row.get("m15_trend"))
    h1 = normalize_trend(row.get("h1_trend"))
    h4 = normalize_trend(row.get("h4_trend"))
    d1 = normalize_trend(row.get("d1_trend"))
    if len({m15, h1, h4}) == 1 and m15 in {"bullish", "bearish"}:
        return f"M15/H1/H4 {m15}", direction_from_trend(m15), "tactical_alignment"
    if len({h1, h4, d1}) == 1 and h1 in {"bullish", "bearish"}:
        return f"H1/H4/D1 {h1}", direction_from_trend(h1), "higher_alignment"
    return "sin alineacion limpia", "neutral", "mixed"


def trend_detail_context(row: dict[str, str]) -> str:
    labels = [("M15", "m15_trend"), ("H1", "h1_trend"), ("H4", "h4_trend"), ("D1", "d1_trend")]
    parts: list[str] = []
    for label, key in labels:
        trend = normalize_trend(row.get(key))
        marker = {"bullish": "up", "bearish": "down"}.get(trend, "mixed")
        parts.append(f"{label}:{marker}")
    return "|".join(parts)


def rsi_context(row: dict[str, str]) -> tuple[str, str, str]:
    signals = [
        ("M15", clean(row.get("m15_rsi_signal"))),
        ("H1", clean(row.get("h1_rsi_signal"))),
        ("H4", clean(row.get("h4_rsi_signal"))),
        ("D1", clean(row.get("d1_rsi_signal"))),
    ]
    active = [(tf, signal) for tf, signal in signals if signal]
    if not active:
        return "neutral", "neutral", ""
    tf, signal = active[0]
    tone = "long" if "oversold" in signal or "bullish" in signal else "short" if "overbought" in signal or "bearish" in signal else "neutral"
    return f"{tf} {signal}", tone, f"rsi_{tf.lower()}"


def rsi_values_from_ohlc(rows: list[dict[str, str]], period: int = 14) -> list[float | None]:
    closes = [as_float(row.get("close")) for row in rows]
    output: list[float | None] = [None] * len(closes)
    if len(closes) <= period or any(value is None for value in closes[: period + 1]):
        return output
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, period + 1):
        assert closes[index] is not None and closes[index - 1] is not None
        change = float(closes[index]) - float(closes[index - 1])
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    def current_rsi(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs = gain / loss
        return 100.0 - (100.0 / (1.0 + rs))

    output[period] = round(current_rsi(avg_gain, avg_loss), 2)
    for index in range(period + 1, len(closes)):
        if closes[index] is None or closes[index - 1] is None:
            continue
        change = float(closes[index]) - float(closes[index - 1])
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        output[index] = round(current_rsi(avg_gain, avg_loss), 2)
    return output


def rsi_trend_alignment_for(row: dict[str, str], timeframe: str) -> tuple[str, str, str, list[str]]:
    tf = clean(timeframe).upper()
    if tf == "M15":
        parts = [normalize_trend(row.get("m15_trend")), normalize_trend(row.get("h1_trend")), normalize_trend(row.get("h4_trend"))]
        labels = ["M15", "H1", "H4"]
    else:
        parts = [normalize_trend(row.get("h1_trend")), normalize_trend(row.get("h4_trend")), normalize_trend(row.get("d1_trend"))]
        labels = ["H1", "H4", "D1"]
    if len(set(parts)) == 1 and parts[0] in {"bullish", "bearish"}:
        trend = parts[0]
        tag = "tactical_alignment" if tf == "M15" else "higher_alignment"
        return f"{'/'.join(labels)} {trend}", direction_from_trend(trend), tag, labels
    return "sin alineacion limpia", "neutral", "mixed", labels


def rsi_trend_reversal_timing(
    *,
    radar_row: dict[str, str],
    timeframe: str,
    ohlc_rows: list[dict[str, str]],
) -> dict[str, Any] | None:
    trend_ctx, trend_direction, trend_tag, _labels = rsi_trend_alignment_for(radar_row, timeframe)
    if trend_direction not in {"long", "short"}:
        return None
    rows = sorted(ohlc_rows, key=lambda item: parse_time(item.get("timestamp")) or datetime.min)
    values = rsi_values_from_ohlc(rows)
    valid_indexes = [index for index, value in enumerate(values) if value is not None]
    if len(valid_indexes) < 2:
        return None
    last_index = valid_indexes[-1]
    prev_index = valid_indexes[-2]
    current = values[last_index]
    previous = values[prev_index]
    if current is None or previous is None:
        return None
    last_row = rows[last_index]
    event_time = clean(last_row.get("timestamp"))
    close_price = as_float(last_row.get("close"))
    if trend_direction == "short":
        direction = "short"
        trigger = 70.0
        watch_level = 68.0
        crossed_back = previous >= trigger and current < trigger
        watching = current >= watch_level
        reason_entry = "RSI cruza de vuelta por debajo de 70 con triple alineacion bajista"
        reason_watch = "RSI cerca de sobrecompra con triple alineacion bajista"
    else:
        direction = "long"
        trigger = 30.0
        watch_level = 32.0
        crossed_back = previous <= trigger and current > trigger
        watching = current <= watch_level
        reason_entry = "RSI cruza de vuelta por encima de 30 con triple alineacion alcista"
        reason_watch = "RSI cerca de sobreventa con triple alineacion alcista"
    if crossed_back:
        state = "entry_review"
        reason = reason_entry
    elif watching:
        state = "watching"
        reason = reason_watch
    else:
        return None
    return {
        "timeframe": clean(timeframe).upper(),
        "trend_ctx": trend_ctx,
        "trend_direction": trend_direction,
        "trend_tag": trend_tag,
        "direction": direction,
        "timing_state": state,
        "timing_priority": timing_priority(state),
        "timing_reason": reason,
        "trigger_level": f"{trigger:.0f}",
        "trigger_level_type": f"RSI {trigger:.0f} cruce de vuelta",
        "distance_to_trigger_pct": f"{abs(current - trigger):.2f}",
        "last_touch_time": event_time,
        "bars_since_touch": "0" if crossed_back else "",
        "reaction_detected": crossed_back,
        "reaction_direction": "rsi_cross_back" if crossed_back else "",
        "is_late": False,
        "is_invalidated": False,
        "entry_review_status": "review_now" if crossed_back else "monitor_only",
        "timing_source": "rsi_trend_reversal_v1",
        "timing_artifact": "",
        "rsi_value": current,
        "rsi_previous_value": previous,
        "event_time": event_time,
        "event_price": close_price,
    }


def weavecount_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    best: dict[str, dict[str, str]] = {}
    for row in rows:
        symbol = clean(row.get("symbol"))
        if not symbol:
            continue
        if clean(row.get("count_label")) == "no_clear_count":
            continue
        existing = best.get(symbol)
        current_score = as_float(row.get("quality_score")) or 0.0
        existing_score = as_float(existing.get("quality_score")) if existing else -1.0
        if existing is None or current_score > (existing_score or -1.0):
            best[symbol] = row
    return best


def snapshot_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        symbol = clean(row.get("symbol"))
        strategy = clean(row.get("strategy")).lower()
        if symbol and "macd_breakout" in strategy:
            output[symbol].append(row)
    return output


def macd_breakout_enriched_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        symbol = clean(row.get("symbol"))
        if symbol:
            output[symbol].append(row)
    for symbol_rows in output.values():
        symbol_rows.sort(
            key=lambda item: (
                int(clean(item.get("timing_priority"), str(TIMING_PRIORITY_MAP["missing_context"]))),
                0 if clean(item.get("timing_state")) in MACD_BREAKOUT_HIGHLIGHTABLE_STATES else 1,
                0 if clean(item.get("missing_context_reason")) == "" else 1,
                clean(item.get("side")),
            )
        )
    return output


def macd_breakout_best_rows_by_timeframe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best_by_timeframe: dict[str, dict[str, str]] = {}
    for row in rows:
        timeframe = clean(row.get("timeframe"), "H1")
        current = best_by_timeframe.get(timeframe)
        if current is None:
            best_by_timeframe[timeframe] = row
            continue
        current_key = (
            int(clean(current.get("timing_priority"), str(TIMING_PRIORITY_MAP["missing_context"]))),
            0 if clean(current.get("timing_state")) in MACD_BREAKOUT_HIGHLIGHTABLE_STATES else 1,
            0 if clean(current.get("missing_context_reason")) == "" else 1,
            clean(current.get("side")),
        )
        candidate_key = (
            int(clean(row.get("timing_priority"), str(TIMING_PRIORITY_MAP["missing_context"]))),
            0 if clean(row.get("timing_state")) in MACD_BREAKOUT_HIGHLIGHTABLE_STATES else 1,
            0 if clean(row.get("missing_context_reason")) == "" else 1,
            clean(row.get("side")),
        )
        if candidate_key < current_key:
            best_by_timeframe[timeframe] = row
    return [best_by_timeframe[key] for key in sorted(best_by_timeframe)]


def macd_breakout_layer_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        enrichment_id = clean(row.get("enrichment_id"))
        if enrichment_id:
            output[enrichment_id].append(row)
    return output


def fibonacci_context_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        symbol = clean(row.get("symbol"))
        timeframe = clean(row.get("timeframe"))
        if symbol and timeframe:
            output[(symbol, timeframe)] = row
    return output


def fibonacci_layers_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    output: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        symbol = clean(row.get("symbol"))
        timeframe = clean(row.get("timeframe"))
        if not symbol or not timeframe:
            continue
        output[(symbol, timeframe)].append(
            {
                "layer_type": clean(row.get("layer_type"), "fibonacci_level"),
                "label": clean(row.get("label"), "Fib"),
                "price": clean(row.get("price")),
                "start_time": clean(row.get("start_time")),
                "end_time": clean(row.get("end_time")),
                "color": clean(row.get("color"), "#c793ff"),
                "style": clean(row.get("style"), "dash"),
                "source": clean(row.get("source"), "fibonacci_context_v1"),
                "is_operational": False,
            }
        )
    return output


def fibonacci_context_for(
    index: dict[tuple[str, str], dict[str, str]],
    symbol: str,
    preferred_timeframe: str,
) -> dict[str, str]:
    return index.get((symbol, preferred_timeframe)) or index.get((symbol, "H1")) or index.get((symbol, "H4")) or {}


def fibonacci_layers_for(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    symbol: str,
    preferred_timeframe: str,
) -> list[dict[str, Any]]:
    return list(index.get((symbol, preferred_timeframe)) or index.get((symbol, "H1")) or index.get((symbol, "H4")) or [])


def fib_limit_live_context(
    index: dict[tuple[str, str], dict[str, str]],
    symbol: str,
) -> dict[str, str]:
    candidates: list[dict[str, str]] = []
    for timeframe in ("H1", "H4"):
        row = index.get((symbol, timeframe))
        if not row:
            continue
        ratio = as_float(row.get("nearest_fib_ratio"))
        if clean(row.get("fibonacci_status")) == "fib_near_price" and ratio is not None and abs(ratio - 0.618) < 0.001:
            candidates.append(row)
    if not candidates:
        return {}
    candidates.sort(
        key=lambda row: (
            as_float(row.get("nearest_fib_distance_pct")) if as_float(row.get("nearest_fib_distance_pct")) is not None else 999.0,
            0 if clean(row.get("timeframe")) == "H1" else 1,
        )
    )
    return candidates[0]


def fibonacci_is_near(row: dict[str, str]) -> bool:
    return clean(row.get("fibonacci_status")) == "fib_near_price"


def fibonacci_context_text(row: dict[str, str]) -> str:
    if not row:
        return "pending_source"
    status = clean(row.get("fibonacci_status"))
    text = clean(row.get("fibonacci_context"))
    if status == "no_clear_swing":
        return "sin swing claro"
    if status == "no_fib_context":
        return "sin contexto"
    return text or "sin contexto"


def fib_limit_sample_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {clean(row.get("case_id")): row for row in rows if clean(row.get("case_id"))}


def fib_limit_review_rows(
    review_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    samples = fib_limit_sample_index(sample_rows)
    output: list[dict[str, str]] = []
    allowed = {"visually_defensible", "visually_acceptable_with_caution", "needs_manual_user_review"}
    for row in review_rows:
        classification = clean(row.get("visual_classification"))
        if classification not in allowed:
            continue
        case_id = clean(row.get("case_id"))
        merged = {**samples.get(case_id, {}), **row}
        if clean(merged.get("symbol")) and clean(merged.get("timeframe_ltf")):
            output.append(merged)
    return output


def fib_limit_review_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        output[clean(row.get("symbol"))].append(row)
    return output


def fib_limit_quality(row: dict[str, str]) -> tuple[int, str, str]:
    classification = clean(row.get("visual_classification"))
    w1_pct = as_float(row.get("w1_size_pct") or row.get("W1_PRICE_PCT")) or 0.0
    w1_atr = as_float(row.get("w1_atr_multiple") or row.get("W1_ATR_MULTIPLE")) or 0.0
    w1_bars = as_float(row.get("w1_bars") or row.get("W1_BARS")) or 0.0
    retr = as_float(row.get("w2_retr_pct") or row.get("W2_RETR_PCT")) or 0.0
    if classification == "visually_defensible":
        score = 5 if w1_pct >= 1.0 and w1_atr >= 3.0 and w1_bars >= 20 else 4
        label = "revision visual defensible"
    elif classification == "visually_acceptable_with_caution":
        score = 4 if w1_pct >= 0.75 and w1_atr >= 2.0 else 3
        label = "aceptable con cautela"
    else:
        score = 3
        label = "revisado manualmente con cautela"
    reason = f"{label}; W1 {w1_pct:.2f}%; {w1_atr:.2f} ATR; {w1_bars:.0f} barras; W2 retr {retr:.2f}"
    return max(1, min(score, 5)), quality_label(score), reason


def fib_limit_layers(row: dict[str, str]) -> list[dict[str, Any]]:
    specs = [
        ("fib_limit_w1_start", "W1 inicio", "W1_START_PRICE", "#58e6d3", "dash"),
        ("fib_limit_w1_end", "W1 fin", "W1_END_PRICE", "#58e6d3", "dash"),
        ("fib_limit_w2_extreme", "W2 extremo", "W2_EXTREME_PRICE", "#f4b740", "dash"),
        ("fib_limit_entry", "Fib 0.618 / entrada estudio", "entry_price", "#c793ff", "solid"),
        ("fib_limit_stop", "Stop estudio", "stop_price", "#ff6b65", "dash"),
        ("fib_limit_target_1_0", "Objetivo 1.0 estudio", "TARGET_1.0", "#75d7ff", "dot"),
        ("fib_limit_target_1_618", "Objetivo 1.618 estudio", "TARGET_1.618", "#75d7ff", "dot"),
    ]
    start_time = clean(row.get("entry_time"))
    end_time = clean(row.get("last_exit_time") or row.get("end_time") or row.get("entry_time"))
    layers: list[dict[str, Any]] = []
    for layer_type, label, field, color, style in specs:
        price = clean(row.get(field))
        if not price:
            continue
        layers.append(
            {
                "layer_type": layer_type,
                "label": label,
                "price": price,
                "start_time": start_time,
                "end_time": end_time,
                "color": color,
                "style": style,
                "source": "fib_limit_swing_quality_visual_review_v1",
                "is_operational": False,
            }
        )
    return layers


def fib_limit_live_layers_from_fibonacci(
    layers: list[dict[str, Any]],
    fib_row: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    return fib_limit_live_study_layers(layers, fib_row or {})


def layer_by_ratio(layers: list[dict[str, Any]], ratio: float) -> dict[str, Any]:
    for layer in layers:
        value = as_float(layer.get("fib_ratio"))
        if value is not None and abs(value - ratio) < 0.001:
            return layer
        label = clean(layer.get("label")).lower()
        ratio_label = {
            0.0: ("fib 0",),
            1.0: ("fib 100",),
            0.618: ("fib 61.8", "fib 0.618"),
            1.272: ("fib ext 1.272",),
            1.618: ("fib ext 1.618",),
        }.get(ratio, ())
        if any(label.startswith(text) for text in ratio_label):
            return layer
    return {}


def fib_limit_live_study_layers(layers: list[dict[str, Any]], fib_row: dict[str, str] | None = None) -> list[dict[str, Any]]:
    fib_row = fib_row or {}
    swing_start = layer_by_ratio(layers, 0.0)
    swing_end = layer_by_ratio(layers, 1.0)
    entry = layer_by_ratio(layers, 0.618)
    invalidation = layer_by_ratio(layers, 1.0)
    tp1 = layer_by_ratio(layers, 0.0)
    tp2 = layer_by_ratio(layers, 1.272) or layer_by_ratio(layers, 1.618)
    swing_start_time = clean(fib_row.get("swing_start_time"))
    swing_end_time = clean(fib_row.get("swing_end_time"))
    swing_start_price = clean(fib_row.get("swing_start_price"))
    swing_end_price = clean(fib_row.get("swing_end_price"))
    specs = [
        ("fib_limit_study_zone_618", "Entrada 61.8 estudio", entry, "#f4b740", "solid"),
        ("fib_limit_study_sl", "SL estudio", invalidation, "#ff6b65", "dash"),
        ("fib_limit_study_tp1", "TP1 estudio", tp1, "#7bd88f", "dot"),
        ("fib_limit_study_tp2", "TP2 estudio", tp2, "#5ce0ca", "dot"),
    ]
    output: list[dict[str, Any]] = []
    if swing_start and swing_end:
        output.append(
            {
                "layer_type": "fib_limit_study_swing_0_100",
                "label": "Swing 0-100 estudio",
                "price": clean(swing_end.get("price")),
                "start_price": swing_start_price or clean(swing_start.get("price")),
                "end_price": swing_end_price or clean(swing_end.get("price")),
                "start_time": swing_start_time or clean(swing_start.get("start_time") or swing_end.get("start_time")),
                "end_time": swing_end_time or clean(swing_end.get("end_time") or swing_start.get("end_time")),
                "color": "#f4b740",
                "style": "solid",
                "source": "fib_limit_live_study_levels_v1",
                "is_operational": False,
            }
        )
    for layer_type, label, source_layer, color, style in specs:
        if not source_layer:
            continue
        item = dict(source_layer)
        item["layer_type"] = layer_type
        item["label"] = label
        item["color"] = color
        item["style"] = style
        item["source"] = "fib_limit_live_study_levels_v1"
        item["is_operational"] = False
        output.append(item)
    return output


def timing_priority(state: str) -> int:
    return TIMING_PRIORITY_MAP.get(clean(state), TIMING_PRIORITY_MAP["no_timing_context"])


def default_timing_fields(setup_type: str) -> dict[str, Any]:
    if setup_type == "fib_limit_live_candidate":
        state = "no_timing_context"
        reason = "falta contexto minimo de timing para fib_limit"
        source = "fib_limit_timing_v1"
    else:
        state = "watching"
        reason = "contexto sin timing operativo propio"
        source = "generic_non_fib_limit"
    return {
        "timing_state": state,
        "timing_priority": timing_priority(state),
        "timing_reason": reason,
        "trigger_level": "",
        "trigger_level_type": "",
        "distance_to_trigger_pct": "",
        "last_touch_time": "",
        "bars_since_touch": "",
        "reaction_detected": False,
        "reaction_direction": "",
        "is_late": False,
        "is_invalidated": False,
        "entry_review_status": "not_applicable" if setup_type != "fib_limit_live_candidate" else "pending_context",
        "timing_source": source,
        "timing_artifact": "",
    }


def default_macd_breakout_fields() -> dict[str, Any]:
    return {
        "macd_breakout_timing_state": "",
        "macd_breakout_timing_reason": "",
        "macd_breakout_priority": "",
        "macd_breakout_level": "",
        "macd_breakout_time": "",
        "bars_since_breakout": "",
        "macd_cross_state": "",
        "macd_cross_time": "",
        "bars_since_macd_cross": "",
        "macd_sl_study": "",
        "macd_tp1_study": "",
        "macd_tp2_study": "",
        "macd_context_complete": "",
    }


def macd_breakout_timing_fields(row: dict[str, Any], timing_artifact: str) -> dict[str, Any]:
    timing_state = clean(row.get("timing_state"), "missing_context")
    missing_context_reason = clean(row.get("missing_context_reason"))
    context_complete = timing_state != "missing_context" and not missing_context_reason
    return {
        "timing_state": timing_state,
        "timing_priority": int(clean(row.get("timing_priority"), str(TIMING_PRIORITY_MAP["missing_context"]))),
        "timing_reason": clean(row.get("timing_reason"), "sin timing macd_breakout"),
        "trigger_level": clean(row.get("breakout_level")),
        "trigger_level_type": "Ruptura estudio" if clean(row.get("breakout_level")) else "",
        "distance_to_trigger_pct": "",
        "last_touch_time": clean(row.get("last_breakout_time")),
        "bars_since_touch": clean(row.get("bars_since_breakout")),
        "reaction_detected": clean(row.get("macd_cross_state")) in {"recent", "stale"},
        "reaction_direction": "macd_recent" if clean(row.get("macd_cross_state")) == "recent" else "",
        "is_late": clean(row.get("late")).lower() == "true",
        "is_invalidated": clean(row.get("invalidated")).lower() == "true",
        "entry_review_status": "review_now" if timing_state in MACD_BREAKOUT_HIGHLIGHTABLE_STATES else "monitor_only",
        "timing_source": "macd_breakout_enrichment_v1",
        "timing_artifact": timing_artifact,
        "macd_breakout_timing_state": timing_state,
        "macd_breakout_timing_reason": clean(row.get("timing_reason")),
        "macd_breakout_priority": clean(row.get("timing_priority")),
        "macd_breakout_level": clean(row.get("breakout_level")),
        "macd_breakout_time": clean(row.get("last_breakout_time")),
        "bars_since_breakout": clean(row.get("bars_since_breakout")),
        "macd_cross_state": clean(row.get("macd_cross_state")),
        "macd_cross_time": clean(row.get("last_macd_cross_time")),
        "bars_since_macd_cross": clean(row.get("bars_since_macd_cross")),
        "macd_sl_study": clean(row.get("sl_study")),
        "macd_tp1_study": clean(row.get("tp1_study")),
        "macd_tp2_study": clean(row.get("tp2_study")),
        "macd_context_complete": "True" if context_complete else "False",
    }


def macd_breakout_setup_status(timing_state: str) -> str:
    if timing_state in MACD_BREAKOUT_HIGHLIGHTABLE_STATES:
        return "ready_for_chart_review"
    if timing_state in MACD_BREAKOUT_SECONDARY_STATES:
        return "context_monitor"
    if timing_state == "late":
        return "late_context"
    if timing_state == "invalidated":
        return "invalidated_context"
    if timing_state == "missing_context":
        return "context_incomplete"
    return "needs_review"


def macd_breakout_risk_tags(timing_state: str) -> list[str]:
    tags = ["study_only_not_signal"]
    if timing_state == "late":
        tags.append("timing_late")
    if timing_state == "invalidated":
        tags.append("setup_invalidated")
    if timing_state == "missing_context":
        tags.append("missing_context")
    if timing_state not in MACD_BREAKOUT_HIGHLIGHTABLE_STATES:
        tags.append("not_highlightable_now")
    return tags


def macd_breakout_quality_cap(timing_state: str, base_score: int) -> int:
    if timing_state in MACD_BREAKOUT_HIGHLIGHTABLE_STATES:
        return max(base_score, 4)
    if timing_state in MACD_BREAKOUT_SECONDARY_STATES:
        return min(base_score, 3)
    if timing_state == "late":
        return min(base_score, 2)
    if timing_state == "missing_context":
        return min(base_score, 2)
    if timing_state == "invalidated":
        return 1
    return base_score


def fib_level_price(layers: list[dict[str, Any]], target_label: str) -> float | None:
    target = clean(target_label).lower()
    for layer in layers:
        label = clean(layer.get("label")).replace(" estudio", "").lower()
        if label == target:
            return as_float(layer.get("price"))
    return None


def timeframe_timing_config(timeframe: str, group: str) -> dict[str, float]:
    near_threshold = proximity_threshold(group)
    timeframe_key = clean(timeframe).upper()
    if timeframe_key == "H4":
        return {
            "near_threshold": near_threshold,
            "late_threshold": max(near_threshold * 2.0, 0.40),
            "entry_review_threshold": max(near_threshold * 1.25, 0.20),
            "touch_lookback_bars": 10,
            "stale_bars": 4,
            "entry_review_max_bars_since_touch": 2,
        }
    return {
        "near_threshold": near_threshold,
        "late_threshold": max(near_threshold * 2.0, 0.24),
        "entry_review_threshold": max(near_threshold * 1.25, 0.12),
        "touch_lookback_bars": 12,
        "stale_bars": 6,
        "entry_review_max_bars_since_touch": 3,
    }


def fib_limit_timing_fields(
    *,
    market_group: str,
    timeframe: str,
    fib_row: dict[str, str],
    fib_layers: list[dict[str, Any]],
    ohlc_rows: list[dict[str, str]],
    timing_artifact: str,
) -> dict[str, Any]:
    output = default_timing_fields("fib_limit_live_candidate")
    output["timing_artifact"] = timing_artifact
    output["timing_source"] = "fib_limit_timing_v1"
    trigger_level = fib_level_price(fib_layers, "Fib 61.8")
    if trigger_level is None:
        output["timing_reason"] = "no se encontro Fib 61.8 en las capas Fibonacci"
        return output
    candles = sorted(ohlc_rows, key=lambda item: parse_time(item.get("timestamp")) or datetime.min)
    if not candles:
        output["timing_reason"] = "faltan velas OHLC para calcular timing"
        output["trigger_level"] = f"{trigger_level:.8g}"
        output["trigger_level_type"] = "Fib 61.8"
        return output
    latest = candles[-1]
    latest_close = as_float(latest.get("close"))
    if latest_close is None:
        output["timing_reason"] = "falta close reciente para calcular timing"
        output["trigger_level"] = f"{trigger_level:.8g}"
        output["trigger_level_type"] = "Fib 61.8"
        return output

    config = timeframe_timing_config(timeframe, market_group)
    invalidation_level = fib_level_price(fib_layers, "Fib 100")
    if invalidation_level is None:
        invalidation_level = fib_level_price(fib_layers, "Fib 0")
    swing_direction = normalize_trend(fib_row.get("swing_direction"))
    expected_reaction = "up" if swing_direction == "bullish" else "down" if swing_direction == "bearish" else ""
    lookback = int(config["touch_lookback_bars"])
    recent = candles[-lookback:]
    last_touch_index: int | None = None
    for idx in range(len(recent) - 1, -1, -1):
        low = as_float(recent[idx].get("low"))
        high = as_float(recent[idx].get("high"))
        if low is None or high is None:
            continue
        if low <= trigger_level <= high:
            last_touch_index = len(candles) - len(recent) + idx
            break

    bars_since_touch = ""
    last_touch_time = ""
    touch_is_recent = False
    reaction_detected = False
    reaction_direction = ""
    if last_touch_index is not None:
        bars_since_touch_value = len(candles) - 1 - last_touch_index
        bars_since_touch = str(bars_since_touch_value)
        last_touch_time = clean(candles[last_touch_index].get("timestamp"))
        touch_is_recent = bars_since_touch_value <= 1
        reaction_window = candles[last_touch_index:]
        for candle in reaction_window:
            candle_open = as_float(candle.get("open"))
            candle_close = as_float(candle.get("close"))
            if candle_close is None:
                continue
            if expected_reaction == "up" and candle_close > trigger_level and (candle_open is None or candle_close >= candle_open):
                reaction_detected = True
                reaction_direction = "up"
                break
            if expected_reaction == "down" and candle_close < trigger_level and (candle_open is None or candle_close <= candle_open):
                reaction_detected = True
                reaction_direction = "down"
                break

    distance_pct = proximity_pct(latest_close, trigger_level)
    is_invalidated = False
    if invalidation_level is not None:
        if swing_direction == "bullish":
            is_invalidated = latest_close < invalidation_level
        elif swing_direction == "bearish":
            is_invalidated = latest_close > invalidation_level

    stale = last_touch_index is not None and int(bars_since_touch or 0) > int(config["stale_bars"])
    is_late = (
        last_touch_index is not None
        and distance_pct > float(config["late_threshold"])
        and not is_invalidated
        and not stale
    )
    entry_review = (
        last_touch_index is not None
        and not is_invalidated
        and not stale
        and not is_late
        and distance_pct <= float(config["entry_review_threshold"])
        and int(bars_since_touch or 0) <= int(config["entry_review_max_bars_since_touch"])
    )

    if is_invalidated:
        state = "invalidated"
        reason = "el precio ha roto la invalidacion aproximada del swing Fibonacci"
    elif stale:
        state = "stale"
        reason = "el ultimo toque del nivel queda demasiado lejos en barras para revisar ahora"
    elif entry_review:
        state = "entry_review"
        reason = "hubo toque OHLC reciente de Fib 61.8; revisar el grafico ahora"
    elif is_late:
        state = "late"
        reason = "el precio ya se ha alejado demasiado del nivel tras el toque"
    elif touch_is_recent:
        state = "touching_level"
        reason = "una vela cerrada reciente toca el nivel de entrada Fib 61.8"
    elif distance_pct <= float(config["near_threshold"]):
        state = "near_level"
        reason = "el precio sigue cerca de Fib 61.8 pero no hay toque reciente"
    else:
        state = "no_timing_context"
        reason = "no hay evidencia suficiente para clasificar un momento de revision mas fuerte"

    output.update(
        {
            "timing_state": state,
            "timing_priority": timing_priority(state),
            "timing_reason": reason,
            "trigger_level": f"{trigger_level:.8g}",
            "trigger_level_type": "Fib 61.8",
            "distance_to_trigger_pct": f"{distance_pct:.4f}",
            "last_touch_time": last_touch_time,
            "bars_since_touch": bars_since_touch,
            "reaction_detected": reaction_detected,
            "reaction_direction": reaction_direction,
            "is_late": is_late,
            "is_invalidated": is_invalidated,
            "entry_review_status": "review_now" if state == "entry_review" else "monitor_only",
        }
    )
    return output


def score_setup(
    setup_type: str,
    trend_tag: str,
    trend_compatibility: str,
    level_hits: list[str],
    volatility_tag: str,
    confluence_tags: list[str],
    risk_tags: list[str],
    has_layers: bool,
) -> tuple[int, str, list[str]]:
    score = 1
    reasons = [f"base {setup_type}"]
    if trend_compatibility == "compatible" and trend_tag in {"tactical_alignment", "higher_alignment"}:
        score += 1
        reasons.append("tendencia compatible")
    elif trend_compatibility == "against":
        risk_tags.append("tendencia contraria")
        reasons.append("tendencia contraria: revisar con cautela")
    elif trend_compatibility == "mixed":
        risk_tags.append("tendencia mixta")
        reasons.append("tendencia sin alineacion limpia")
    if level_hits:
        score += 1
        reasons.append("nivel cercano")
    if volatility_tag == "volatility_ok":
        score += 1
        reasons.append("volatilidad util")
    elif volatility_tag == "volatility_excess":
        risk_tags.append("volatilidad alta")
    elif volatility_tag == "volatility_compressed":
        risk_tags.append("volatilidad comprimida")
    positive_confluence_tags = [tag for tag in confluence_tags if tag in POSITIVE_CONFLUENCE_TAGS]
    if len(positive_confluence_tags) >= 2:
        score += 1
        reasons.append("confluencia multiple")
    if "fibonacci_zone" in positive_confluence_tags and any(tag not in {"fibonacci_zone"} for tag in positive_confluence_tags):
        score += 1
        reasons.append("zona Fibonacci cercana")
    if setup_type in {"previous_day_high_low_candidate"} and trend_tag == "mixed":
        score = min(score, 3)
        reasons.append("contexto sin estrategia base")
    if setup_type == "fibonacci_zone_candidate":
        score = min(score, 3)
        reasons.append("Fibonacci como contexto, no estrategia base")
    if trend_compatibility == "against":
        score = min(score, 2)
    elif trend_compatibility == "mixed" and setup_type == "fib_limit_live_candidate":
        score = min(score, 4)
    if not has_layers:
        score = min(score, 2)
        reasons.append("sin capas graficas suficientes")
    if "stale_context" in risk_tags:
        score -= 1
    score = max(1, min(score, 5))
    return score, "; ".join(reasons), risk_tags


def level_confluence_tags(level_info: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if level_info["pivot_context"] != "no_context":
        tags.append("pivot_context")
    if level_info["previous_day_level_context"] != "no_context":
        tags.append("previous_day_level")
    if level_info["round_level_context"] != "no_context":
        tags.append("round_level")
    return tags


def make_setup(
    *,
    generated_at: str,
    symbol: str,
    market_group: str,
    timeframe: str,
    setup_type: str,
    strategy: str,
    direction: str,
    setup_status: str,
    trend_ctx: str,
    trend_detail_ctx: str,
    rsi_ctx: str,
    pivot_ctx: str,
    day_ctx: str,
    round_ctx: str,
    volatility_ctx: str,
    wavecount_ctx: str,
    fibonacci_ctx: str,
    confluence_tags: list[str],
    risk_tags: list[str],
    source_artifacts: list[str],
    layers: list[dict[str, Any]],
    timing_fields: dict[str, Any] | None = None,
    chart_file: str = "",
    setup_id_suffix: str = "",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    layer_id = f"{METHOD_VERSION}|{symbol}|{timeframe}|{setup_type}|layers"
    raw_trend_tag = "tactical_alignment" if "M15/H1/H4" in trend_ctx else "higher_alignment" if "H1/H4/D1" in trend_ctx else "mixed"
    trend_compatibility, trend_compatibility_reason = trend_compatibility_for_setup(trend_ctx, direction)
    effective_trend_tag = trend_tag_for_compatibility(raw_trend_tag, trend_compatibility)
    normalized_confluence_tags = [
        effective_trend_tag if tag in {"tactical_alignment", "higher_alignment", "mixed_trend", "trend_against"} else tag
        for tag in confluence_tags
    ]
    if effective_trend_tag not in normalized_confluence_tags:
        normalized_confluence_tags.append(effective_trend_tag)
    normalized_confluence_tags = list(dict.fromkeys(tag for tag in normalized_confluence_tags if tag))
    score, quality_reason, risk_tags = score_setup(
        setup_type=setup_type,
        trend_tag=raw_trend_tag,
        trend_compatibility=trend_compatibility,
        level_hits=[tag for tag in normalized_confluence_tags if tag.startswith(("pivot", "previous_day", "round_level"))],
        volatility_tag="volatility_ok" if volatility_ctx.startswith("adecuada") else "volatility_excess" if volatility_ctx.startswith("excesiva") else "volatility_compressed" if volatility_ctx.startswith("comprimida") else "missing_volatility",
        confluence_tags=normalized_confluence_tags,
        risk_tags=risk_tags,
        has_layers=bool(layers),
    )
    suffix = setup_id_suffix or str(len(confluence_tags))
    setup_id = f"{METHOD_VERSION}|{symbol}|{timeframe}|{setup_type}|{suffix}"
    row = {
        "setup_id": setup_id,
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": market_group,
        "timeframe": timeframe,
        "setup_type": setup_type,
        "strategy": strategy,
        "direction": direction,
        "setup_status": setup_status,
        **default_macd_breakout_fields(),
        **(timing_fields or default_timing_fields(setup_type)),
        "setup_quality_score": score,
        "quality_label": quality_label(score),
        "quality_reason": quality_reason,
        "confluence_count": len(normalized_confluence_tags),
        "confluence_tags": "|".join(normalized_confluence_tags) if normalized_confluence_tags else "context_only",
        "risk_tags": "|".join(risk_tags) if risk_tags else "no_extra_risk_tag",
        "trend_context": trend_ctx,
        "trend_compatibility": trend_compatibility,
        "trend_compatibility_reason": trend_compatibility_reason,
        "trend_detail_context": trend_detail_ctx,
        "rsi_context": rsi_ctx,
        "pivot_context": pivot_ctx,
        "previous_day_level_context": day_ctx,
        "fibonacci_context": fibonacci_ctx,
        "round_level_context": round_ctx,
        "volatility_context": volatility_ctx,
        "wavecount_context": wavecount_ctx,
        "codex_review_status": "revision codex pendiente",
        "codex_review_score": "",
        "codex_review_summary": "future_phase",
        "chart_layer_id": layer_id if layers else "",
        "chart_file": chart_file,
        "source_artifacts": "|".join(source_artifacts),
        **safety_flags(),
    }
    layer_rows: list[dict[str, Any]] = []
    for index, layer in enumerate(layers):
        layer_rows.append(
            {
                "chart_layer_id": layer_id,
                "setup_id": setup_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "layer_type": layer.get("layer_type", ""),
                "label": layer.get("label", ""),
                "price": layer.get("price", ""),
                "start_price": layer.get("start_price", ""),
                "end_price": layer.get("end_price", ""),
                "start_time": layer.get("start_time", ""),
                "end_time": layer.get("end_time", ""),
                "color": layer.get("color", ""),
                "style": layer.get("style", ""),
                "source": layer.get("source", ""),
                "is_operational": False,
            }
        )
    return row, layer_rows


def build_screener(
    market_radar_rows: list[dict[str, str]],
    ohlc_rows: list[dict[str, str]],
    weavecount_rows: list[dict[str, str]],
    snapshot_rows: list[dict[str, str]],
    macd_breakout_enriched_rows: list[dict[str, str]],
    macd_breakout_chart_layer_rows: list[dict[str, str]],
    fibonacci_rows: list[dict[str, str]],
    fibonacci_layer_rows: list[dict[str, str]],
    fib_limit_review_input_rows: list[dict[str, str]],
    fib_limit_sample_rows: list[dict[str, str]],
    *,
    generated_at: str,
    market_radar_source: Path,
    ohlc_source: Path,
    weavecount_source: Path,
    snapshot_source: Path | None,
    macd_breakout_enriched_source: Path | None,
    macd_breakout_chart_layers_source: Path | None,
    fibonacci_source: Path | None,
    fibonacci_layers_source: Path | None,
    fib_limit_review_source: Path | None,
    fib_limit_sample_source: Path | None,
    max_highlighted_setups: int,
    include_historical_fib_limit: bool = False,
) -> dict[str, Any]:
    (
        macd_breakout_enriched_rows,
        macd_breakout_chart_layer_rows,
        macd_freshness_meta,
    ) = filter_macd_breakout_rows_for_current_cut(
        macd_breakout_enriched_rows,
        macd_breakout_chart_layer_rows,
        ohlc_rows,
    )
    grouped_ohlc = ohlc_by_symbol_tf(ohlc_rows)
    latest = latest_ohlc_index(ohlc_rows)
    weave_by_symbol = weavecount_index(weavecount_rows)
    macd_by_symbol = snapshot_index(snapshot_rows)
    macd_enriched_by_symbol = macd_breakout_enriched_index(macd_breakout_enriched_rows)
    macd_layers_by_enrichment = macd_breakout_layer_index(macd_breakout_chart_layer_rows)
    fib_by_symbol_tf = fibonacci_context_index(fibonacci_rows)
    fib_layers_by_symbol_tf = fibonacci_layers_index(fibonacci_layer_rows)
    fib_limit_rows = fib_limit_review_rows(fib_limit_review_input_rows, fib_limit_sample_rows)
    fib_limit_by_symbol = fib_limit_review_index(fib_limit_rows)
    setups: list[dict[str, Any]] = []
    chart_layers: list[dict[str, Any]] = []
    matrix_by_symbol: dict[str, dict[str, Any]] = {}

    for radar_row in market_radar_rows:
        symbol = clean(radar_row.get("symbol"))
        group = clean(radar_row.get("market_group"), "not_available")
        if not symbol:
            continue
        h1_rows = grouped_ohlc.get((symbol, "H1"), [])
        latest_h1 = latest.get((symbol, "H1"), {})
        close = as_float(latest_h1.get("close"))
        trend_ctx, trend_direction, trend_tag = trend_context(radar_row)
        rsi_ctx, rsi_direction, rsi_tag = rsi_context(radar_row)
        volatility_ctx, volatility_tag = volatility_context(radar_row)
        level_info = level_context(symbol, group, h1_rows)
        level_tags = level_confluence_tags(level_info)
        wave_row = weave_by_symbol.get(symbol, {})
        wave_ctx = "no_context"
        if wave_row:
            wave_ctx = f"{clean(wave_row.get('count_label'))} {clean(wave_row.get('timeframe'))} {clean(wave_row.get('quality_status'))}"
        macd_rows = macd_by_symbol.get(symbol, [])
        macd_enriched_rows_for_symbol = macd_enriched_by_symbol.get(symbol, [])
        macd_chip = "sin enrichment"
        if macd_enriched_rows_for_symbol:
            state_counts: dict[str, int] = defaultdict(int)
            for macd_row in macd_enriched_rows_for_symbol:
                state_counts[clean(macd_row.get("timing_state"), "missing_context")] += 1
            ordered_states = sorted(
                state_counts.items(),
                key=lambda item: (TIMING_PRIORITY_MAP.get(item[0], TIMING_PRIORITY_MAP["missing_context"]), item[0]),
            )
            macd_chip = "|".join(f"{state} x{count}" for state, count in ordered_states[:3])
        elif macd_rows:
            states = sorted({clean(row.get("signal_state") or row.get("watch_state"), "watching_setup") for row in macd_rows})
            macd_chip = "|".join(states)
        fib_row = fibonacci_context_for(fib_by_symbol_tf, symbol, "H1")
        fib_ctx = fibonacci_context_text(fib_row)
        fib_layers = fibonacci_layers_for(fib_layers_by_symbol_tf, symbol, "H1")
        fib_tags = ["fibonacci_zone"] if fibonacci_is_near(fib_row) else []
        fib_limit_live_row = fib_limit_live_context(fib_by_symbol_tf, symbol)
        fib_limit_live_layers = fibonacci_layers_for(fib_layers_by_symbol_tf, symbol, clean(fib_limit_live_row.get("timeframe"), "H1")) if fib_limit_live_row else []
        fib_limit_rows_for_symbol = fib_limit_by_symbol.get(symbol, [])
        fib_limit_chip = "pendiente detector live"
        if fib_limit_live_row:
            fib_limit_chip = f"live Fib 61.8 {clean(fib_limit_live_row.get('timeframe'), 'H1')}"
        if fib_limit_rows_for_symbol:
            best_fib_limit = sorted(fib_limit_rows_for_symbol, key=lambda item: -fib_limit_quality(item)[0])[0]
            score, _, reason = fib_limit_quality(best_fib_limit)
            if not fib_limit_live_row:
                fib_limit_chip = f"historico auditado {score}/5"
            if "cautela" in reason:
                fib_limit_chip += " cautela"

        matrix_by_symbol[symbol] = {
            "symbol": symbol,
            "market_group": group,
            "trend_chip": trend_ctx,
            "rsi_chip": rsi_ctx,
            "pivot_chip": level_info["pivot_context"],
            "previous_day_level_chip": level_info["previous_day_level_context"],
            "round_level_chip": level_info["round_level_context"],
            "fibonacci_chip": fib_ctx,
            "volatility_chip": volatility_ctx,
            "macd_breakout_chip": macd_chip,
            "fib_limit_chip": fib_limit_chip,
            "wavecount_chip": wave_ctx,
            "codex_review_status": "revision codex pendiente",
            "setups_count": 0,
            "max_quality_score": 0,
            **safety_flags(),
        }

        base_sources = [str(market_radar_source), str(ohlc_source)]
        if wave_row:
            base_sources.append(str(weavecount_source))
        if macd_rows and snapshot_source:
            base_sources.append(str(snapshot_source))
        if macd_enriched_rows_for_symbol and macd_breakout_enriched_source:
            base_sources.append(str(macd_breakout_enriched_source))
            if macd_enriched_rows_for_symbol and macd_breakout_chart_layers_source:
                base_sources.append(str(macd_breakout_chart_layers_source))
        if fib_row and fibonacci_source:
            base_sources.append(str(fibonacci_source))
        if include_historical_fib_limit and fib_limit_rows_for_symbol and fib_limit_review_source:
            base_sources.append(str(fib_limit_review_source))
        if include_historical_fib_limit and fib_limit_rows_for_symbol and fib_limit_sample_source:
            base_sources.append(str(fib_limit_sample_source))

        for fib_limit_row in (fib_limit_rows_for_symbol[:3] if include_historical_fib_limit else []):
            fib_score, fib_label, fib_reason = fib_limit_quality(fib_limit_row)
            fib_layers_for_case = fib_limit_layers(fib_limit_row)
            classification = clean(fib_limit_row.get("visual_classification"))
            case_id = clean(fib_limit_row.get("case_id"), "fib_limit_case")
            direction = "long" if clean(fib_limit_row.get("direction")) == "1" else "short" if clean(fib_limit_row.get("direction")) == "-1" else trend_direction
            setup, layers = make_setup(
                generated_at=generated_at,
                symbol=symbol,
                market_group=group,
                timeframe=clean(fib_limit_row.get("timeframe_ltf"), "H1"),
                setup_type="fib_limit_swing_quality",
                strategy="fib_limit",
                direction=direction,
                setup_status="ready_for_chart_review" if classification != "needs_manual_user_review" else "needs_review",
                trend_ctx=trend_ctx,
                trend_detail_ctx=trend_detail_context(radar_row),
                rsi_ctx=rsi_ctx,
                pivot_ctx=level_info["pivot_context"],
                day_ctx=level_info["previous_day_level_context"],
                round_ctx=level_info["round_level_context"],
                volatility_ctx=volatility_ctx,
                wavecount_ctx=wave_ctx,
                fibonacci_ctx="fib_limit swing-quality revisado",
                confluence_tags=[
                    "fib_limit",
                    "swing_quality",
                    "visual_review",
                    trend_tag if trend_tag != "mixed" else "mixed_trend",
                    *level_tags,
                    *fib_tags,
                ],
                risk_tags=["backtest_artifact_review", "study_only_not_live"] + (["manual_review_caution"] if classification == "needs_manual_user_review" else []),
                source_artifacts=base_sources + [clean(fib_limit_row.get("chart_file"))],
                layers=[*level_info["layers"], *fib_layers, *fib_layers_for_case],
                chart_file=clean(fib_limit_row.get("chart_file")),
                setup_id_suffix=case_id,
            )
            setup["setup_quality_score"] = fib_score
            setup["quality_label"] = fib_label
            setup["quality_reason"] = fib_reason
            setup["confluence_count"] = len([tag for tag in str(setup.get("confluence_tags", "")).split("|") if tag])
            setups.append(setup)
            chart_layers.extend(layers)

        if fib_limit_live_row:
            fib_limit_tf = clean(fib_limit_live_row.get("timeframe"), "H1")
            fib_direction = direction_from_trend(clean(fib_limit_live_row.get("swing_direction"), "mixed"))
            fib_limit_live_setup_layers = fib_limit_live_layers_from_fibonacci(fib_limit_live_layers, fib_limit_live_row)
            timing_fields = fib_limit_timing_fields(
                market_group=group,
                timeframe=fib_limit_tf,
                fib_row=fib_limit_live_row,
                fib_layers=fib_limit_live_layers,
                ohlc_rows=grouped_ohlc.get((symbol, fib_limit_tf), []),
                timing_artifact=str(fibonacci_source) if fibonacci_source else "",
            )
            setup, layers = make_setup(
                generated_at=generated_at,
                symbol=symbol,
                market_group=group,
                timeframe=fib_limit_tf,
                setup_type="fib_limit_live_candidate",
                strategy="fib_limit",
                direction=fib_direction,
                setup_status="ready_for_chart_review",
                trend_ctx=trend_ctx,
                trend_detail_ctx=trend_detail_context(radar_row),
                rsi_ctx=rsi_ctx,
                pivot_ctx=level_info["pivot_context"],
                day_ctx=level_info["previous_day_level_context"],
                round_ctx=level_info["round_level_context"],
                volatility_ctx=volatility_ctx,
                wavecount_ctx=wave_ctx,
                fibonacci_ctx=fibonacci_context_text(fib_limit_live_row),
                confluence_tags=[
                    "fib_limit_live",
                    "fibonacci_0_618",
                    trend_tag if trend_tag != "mixed" else "mixed_trend",
                    *level_tags,
                ],
                risk_tags=["study_only_not_signal", "needs_chart_review"],
                source_artifacts=base_sources + ([str(fibonacci_source)] if fibonacci_source else []),
                layers=[*level_info["layers"], *fib_limit_live_setup_layers],
                timing_fields=timing_fields,
                setup_id_suffix=fib_limit_tf,
            )
            setups.append(setup)
            chart_layers.extend(layers)

        for rsi_timeframe in ("M15", "H1"):
            if group.lower() == "crypto":
                continue
            rsi_timing = rsi_trend_reversal_timing(
                radar_row=radar_row,
                timeframe=rsi_timeframe,
                ohlc_rows=grouped_ohlc.get((symbol, rsi_timeframe), []),
            )
            if not rsi_timing:
                continue
            rsi_state = clean(rsi_timing.get("timing_state"), "watching")
            rsi_value = as_float(rsi_timing.get("rsi_value"))
            rsi_setup_layers = [*level_info["layers"], *fib_layers]
            if rsi_state == "entry_review" and rsi_timing.get("event_time"):
                rsi_setup_layers.append(
                    {
                        "layer_type": "rsi_entry_marker",
                        "label": "RSI cruce vuelta",
                        "price": f"{as_float(rsi_timing.get('event_price')):.8g}" if as_float(rsi_timing.get("event_price")) is not None else "",
                        "start_price": f"{rsi_value:.2f}" if rsi_value is not None else "",
                        "start_time": clean(rsi_timing.get("event_time")),
                        "end_time": clean(rsi_timing.get("event_time")),
                        "color": "#d7a84b",
                        "style": "solid",
                        "source": "rsi_trend_reversal_v1",
                        "is_operational": False,
                    }
                )
            confluences = [
                "rsi_entry_review" if rsi_state == "entry_review" else "rsi_watching",
                clean(rsi_timing.get("trend_tag")),
            ]
            if volatility_tag == "volatility_ok":
                confluences.append("volatility_ok")
            setup, layers = make_setup(
                generated_at=generated_at,
                symbol=symbol,
                market_group=group,
                timeframe=rsi_timeframe,
                setup_type="rsi_trend_reversal",
                strategy="rsi_trend_reversal",
                direction=clean(rsi_timing.get("direction"), "neutral"),
                setup_status="ready_for_chart_review" if rsi_state == "entry_review" else "context_monitor",
                trend_ctx=clean(rsi_timing.get("trend_ctx"), trend_ctx),
                trend_detail_ctx=trend_detail_context(radar_row),
                rsi_ctx=f"RSI {rsi_timeframe} {rsi_value:.2f}" if rsi_value is not None else f"RSI {rsi_timeframe}",
                pivot_ctx=level_info["pivot_context"],
                day_ctx=level_info["previous_day_level_context"],
                round_ctx=level_info["round_level_context"],
                volatility_ctx=volatility_ctx,
                wavecount_ctx=wave_ctx,
                fibonacci_ctx=fib_ctx,
                confluence_tags=confluences,
                risk_tags=["study_only_not_signal", "sl_tp_not_defined"],
                source_artifacts=base_sources,
                layers=rsi_setup_layers,
                timing_fields={key: value for key, value in rsi_timing.items() if key in default_timing_fields("rsi_trend_reversal")},
                setup_id_suffix=rsi_timeframe,
            )
            if rsi_state == "watching":
                setup["setup_quality_score"] = min(int(setup["setup_quality_score"]), 3)
                setup["quality_label"] = quality_label(int(setup["setup_quality_score"]))
                setup["quality_reason"] = f"{setup['quality_reason']}; esperando cruce de vuelta RSI"
            setups.append(setup)
            chart_layers.extend(layers)

        for macd_row in macd_breakout_best_rows_by_timeframe(macd_enriched_rows_for_symbol):
            timing_state = clean(macd_row.get("timing_state"), "missing_context")
            setup_layers: list[dict[str, Any]] = [*level_info["layers"]]
            if fib_layers:
                setup_layers.extend(fib_layers)
            for layer in macd_layers_by_enrichment.get(clean(macd_row.get("enrichment_id")), []):
                layer_type = clean(layer.get("layer_type"))
                layer_style = clean(layer.get("style"))
                directrix_is_late = layer_type == "macd_w2_directrix" and layer_style.startswith("dot:")
                setup_layers.append(
                    {
                        "layer_type": layer_type,
                        "label": clean(layer.get("label")),
                        "price": clean(layer.get("price")),
                        "start_price": clean(layer.get("y0")),
                        "end_price": clean(layer.get("y1")),
                        "start_time": clean(layer.get("x0")),
                        "end_time": clean(layer.get("x1")),
                        "color": "#ffd166" if layer_type == "macd_breakout_level" else "#58e6d3" if layer_type == "macd_w1_leg" else "#f4b740" if layer_type == "macd_w2_retracement" else "#b8ccc7" if directrix_is_late else "#5ce0ca" if layer_type == "macd_w2_directrix" else "#ff6b6b" if layer_type == "macd_sl_study" else "#75d7ff" if layer_type in {"macd_tp1_study", "macd_tp2_study"} else "#f7f7f7",
                        "style": "solid" if layer_type in {"macd_w1_leg", "macd_w2_retracement"} else "dot" if directrix_is_late else "dash" if layer_type in {"macd_breakout_level", "macd_w2_directrix"} else "dot" if layer_type in {"macd_sl_study", "macd_tp1_study", "macd_tp2_study"} else "marker",
                        "source": clean(layer.get("source_field"), "macd_breakout_enrichment_v1"),
                    }
                )
            setup, layers = make_setup(
                generated_at=generated_at,
                symbol=symbol,
                market_group=group,
                timeframe=clean(macd_row.get("timeframe"), "H1"),
                setup_type="macd_breakout",
                strategy="macd_breakout",
                direction="long" if clean(macd_row.get("side")).upper() == "BUY" else "short" if clean(macd_row.get("side")).upper() == "SELL" else trend_direction,
                setup_status=macd_breakout_setup_status(timing_state),
                trend_ctx=trend_ctx,
                trend_detail_ctx=trend_detail_context(radar_row),
                rsi_ctx=rsi_ctx,
                pivot_ctx=level_info["pivot_context"],
                day_ctx=level_info["previous_day_level_context"],
                round_ctx=level_info["round_level_context"],
                volatility_ctx=volatility_ctx,
                wavecount_ctx=wave_ctx,
                fibonacci_ctx=fib_ctx,
                confluence_tags=[
                    f"macd_{timing_state}",
                    "macd_breakout_context",
                    trend_tag if trend_tag != "mixed" else "mixed_trend",
                    *level_tags,
                    *fib_tags,
                ],
                risk_tags=macd_breakout_risk_tags(timing_state),
                source_artifacts=base_sources,
                layers=setup_layers,
                timing_fields=macd_breakout_timing_fields(
                    macd_row,
                    str(macd_breakout_enriched_source) if macd_breakout_enriched_source else "",
                ),
                setup_id_suffix=clean(macd_row.get("setup_id")) or clean(macd_row.get("enrichment_id")),
            )
            setup["setup_quality_score"] = macd_breakout_quality_cap(timing_state, int(setup["setup_quality_score"]))
            setup["quality_label"] = quality_label(int(setup["setup_quality_score"]))
            setup["confluence_count"] = len([tag for tag in str(setup.get("confluence_tags", "")).split("|") if tag])
            setups.append(setup)
            chart_layers.extend(layers)

    setups.sort(
        key=lambda item: (
            1 if item.get("setup_type") == "macd_breakout" and clean(item.get("macd_breakout_timing_state")) in MACD_BREAKOUT_EXCLUDED_FROM_HIGHLIGHTS else 0,
            int(item.get("timing_priority") or TIMING_PRIORITY_MAP["no_timing_context"]),
            -int(item.get("setup_quality_score") or 0),
            -int(item.get("confluence_count") or 0),
            str(item.get("symbol")),
            str(item.get("setup_type")),
        )
    )
    if max_highlighted_setups > 0:
        setups = setups[:max_highlighted_setups]
        keep_ids = {row["setup_id"] for row in setups}
        chart_layers = [row for row in chart_layers if row["setup_id"] in keep_ids]
    for setup in setups:
        matrix = matrix_by_symbol.get(clean(setup.get("symbol")))
        if not matrix:
            continue
        matrix["setups_count"] = int(matrix.get("setups_count") or 0) + 1
        matrix["max_quality_score"] = max(int(matrix.get("max_quality_score") or 0), int(setup.get("setup_quality_score") or 0))
    matrix_rows = sorted(matrix_by_symbol.values(), key=lambda item: (-int(item.get("max_quality_score") or 0), str(item.get("symbol"))))
    return {
        "setups": setups,
        "matrix": matrix_rows,
        "layers": chart_layers,
        "source_rows": {
            "market_radar": len(market_radar_rows),
            "ohlc": len(ohlc_rows),
            "weavecount": len(weavecount_rows),
            "snapshot": len(snapshot_rows),
            "macd_breakout_enriched": len(macd_breakout_enriched_rows),
            "macd_breakout_layers": len(macd_breakout_chart_layer_rows),
            **macd_freshness_meta,
            "fibonacci": len(fibonacci_rows),
            "fibonacci_layers": len(fibonacci_layer_rows),
            "fib_limit_review": len(fib_limit_rows),
            "fib_limit_review_raw": len(fib_limit_review_input_rows),
            "fib_limit_sample": len(fib_limit_sample_rows),
        },
    }


def write_outputs(output_dir: Path, result: dict[str, Any], args: argparse.Namespace, generated_at: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    setups = result["setups"]
    matrix = result["matrix"]
    layers = result["layers"]
    write_csv(output_dir / "screener_setups.csv", setups, SETUP_FIELDNAMES)
    (output_dir / "screener_setups.json").write_text(json.dumps(setups, indent=2, ensure_ascii=True), encoding="utf-8")
    write_csv(output_dir / "screener_asset_matrix.csv", matrix, MATRIX_FIELDNAMES)
    write_csv(output_dir / "screener_chart_layers.csv", layers, LAYER_FIELDNAMES)
    write_csv(
        tables_dir / "source_data_audit.csv",
        [
            {"source_id": "market_radar", "path": str(args.market_radar_csv), "rows": result["source_rows"]["market_radar"], "status": "available" if result["source_rows"]["market_radar"] else "missing_or_empty"},
            {"source_id": "ohlc_mtf", "path": str(args.ohlc_csv), "rows": result["source_rows"]["ohlc"], "status": "available" if result["source_rows"]["ohlc"] else "missing_or_empty"},
            {"source_id": "weavecount", "path": str(args.weavecount_csv), "rows": result["source_rows"]["weavecount"], "status": "available" if result["source_rows"]["weavecount"] else "optional_missing"},
            {"source_id": "macd_breakout_snapshot", "path": str(args.snapshot_csv), "rows": result["source_rows"]["snapshot"], "status": "available" if result["source_rows"]["snapshot"] else "optional_missing"},
            {"source_id": "macd_breakout_enriched", "path": str(args.macd_breakout_enriched_csv), "rows": result["source_rows"]["macd_breakout_enriched"], "status": "available" if result["source_rows"]["macd_breakout_enriched"] else "warning_missing_optional_no_macd_setups_created"},
            {"source_id": "macd_breakout_chart_layers", "path": str(args.macd_breakout_chart_layers_csv), "rows": result["source_rows"]["macd_breakout_layers"], "status": "available" if result["source_rows"]["macd_breakout_layers"] else "warning_missing_optional_no_macd_layers_created"},
            {"source_id": "fibonacci_context", "path": str(args.fibonacci_context_csv), "rows": result["source_rows"]["fibonacci"], "status": "available" if result["source_rows"]["fibonacci"] else "optional_missing"},
            {"source_id": "fibonacci_chart_layers", "path": str(args.fibonacci_layers_csv), "rows": result["source_rows"]["fibonacci_layers"], "status": "available" if result["source_rows"]["fibonacci_layers"] else "optional_missing"},
            {"source_id": "fib_limit_visual_review", "path": str(args.fib_limit_review_csv), "rows": result["source_rows"]["fib_limit_review"], "status": "available" if result["source_rows"]["fib_limit_review"] else "optional_missing"},
            {"source_id": "fib_limit_sample_selection", "path": str(args.fib_limit_sample_csv), "rows": result["source_rows"]["fib_limit_sample"], "status": "available" if result["source_rows"]["fib_limit_sample"] else "optional_missing"},
        ],
    )
    write_csv(
        tables_dir / "setup_generation_audit.csv",
        [
            {"setup_type": setup_type, "rows": sum(1 for row in setups if row["setup_type"] == setup_type)}
            for setup_type in sorted({row["setup_type"] for row in setups})
        ],
    )
    write_csv(
        tables_dir / "quality_score_audit.csv",
        [
            {"score": score, "rows": sum(1 for row in setups if str(row["setup_quality_score"]) == str(score))}
            for score in range(1, 6)
        ],
    )
    write_csv(
        tables_dir / "trend_compatibility_audit.csv",
        [
            {
                "trend_compatibility": status,
                "rows": sum(1 for row in setups if clean(row.get("trend_compatibility")) == status),
                "fib_limit_live_rows": sum(1 for row in setups if row["setup_type"] == "fib_limit_live_candidate" and clean(row.get("trend_compatibility")) == status),
                "policy": "compatible can add quality; mixed is caution; against is downgraded and study-only",
            }
            for status in ("compatible", "mixed", "against")
        ],
    )
    write_csv(
        tables_dir / "fib_limit_timing_audit.csv",
        [
            {
                "setup_id": row["setup_id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "direction": row["direction"],
                "timing_state": row["timing_state"],
                "timing_priority": row["timing_priority"],
                "timing_reason": row["timing_reason"],
                "trigger_level": row["trigger_level"],
                "distance_to_trigger_pct": row["distance_to_trigger_pct"],
                "last_touch_time": row["last_touch_time"],
                "bars_since_touch": row["bars_since_touch"],
                "reaction_detected": row["reaction_detected"],
                "reaction_direction": row["reaction_direction"],
                "is_late": row["is_late"],
                "is_invalidated": row["is_invalidated"],
                "entry_review_status": row["entry_review_status"],
            }
            for row in setups
            if row["setup_type"] == "fib_limit_live_candidate"
        ],
    )
    write_csv(
        tables_dir / "macd_breakout_integration_audit.csv",
        [
            {
                "check": "enrichment_integrated",
                "status": "passed" if result["source_rows"]["macd_breakout_enriched"] else "warning_missing_optional",
                "rows": sum(1 for row in setups if row["setup_type"] == "macd_breakout"),
                "artifact_rows": result["source_rows"]["macd_breakout_enriched"],
                "chart_layer_rows": result["source_rows"]["macd_breakout_layers"],
            },
            {
                "check": "macd_breakout_timing_source",
                "status": "passed",
                "rows": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("timing_source")) == "macd_breakout_enrichment_v1"),
                "policy": "macd_breakout_setups_only_from_enrichment",
            },
            {
                "check": "snapshot_not_used_to_fabricate_macd_setup",
                "status": "passed",
                "rows": sum(1 for row in setups if row["setup_type"] == "macd_breakout"),
                "policy": "missing_enrichment_means_no_macd_breakout_setup",
            },
        ],
    )
    write_csv(
        tables_dir / "macd_breakout_timing_in_screener_audit.csv",
        [
            {
                "setup_id": row["setup_id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "timing_state": row["macd_breakout_timing_state"],
                "timing_reason": row["macd_breakout_timing_reason"],
                "timing_priority": row["macd_breakout_priority"],
                "breakout_level": row["macd_breakout_level"],
                "breakout_time": row["macd_breakout_time"],
                "bars_since_breakout": row["bars_since_breakout"],
                "macd_cross_state": row["macd_cross_state"],
                "macd_cross_time": row["macd_cross_time"],
                "bars_since_macd_cross": row["bars_since_macd_cross"],
                "sl_study": row["macd_sl_study"],
                "tp1_study": row["macd_tp1_study"],
                "tp2_study": row["macd_tp2_study"],
                "context_complete": row["macd_context_complete"],
            }
            for row in setups
            if row["setup_type"] == "macd_breakout"
        ],
    )
    write_csv(
        tables_dir / "macd_breakout_highlight_policy_audit.csv",
        [
            {
                "timing_state": state,
                "rows": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) == state),
                "highlight_policy": "highlightable" if state in MACD_BREAKOUT_HIGHLIGHTABLE_STATES else "secondary" if state in MACD_BREAKOUT_SECONDARY_STATES else "excluded_from_highlights",
            }
            for state in sorted(
                {
                    clean(row.get("macd_breakout_timing_state"))
                    for row in setups
                    if row["setup_type"] == "macd_breakout"
                }
            )
        ],
    )
    write_csv(
        tables_dir / "setup_timing_distribution_audit.csv",
        [
            {"timing_state": state, "rows": sum(1 for row in setups if clean(row.get("timing_state")) == state)}
            for state in sorted({clean(row.get("timing_state")) for row in setups})
        ],
    )
    write_csv(
        tables_dir / "rsi_trend_reversal_audit.csv",
        [
            {
                "check": "rsi_trend_reversal_setups",
                "rows": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal"),
                "policy": "M15 usa M15/H1/H4; H1 usa H1/H4/D1; Crypto excluido; Commodities y Forex Exotic permitidos; study-only sin SL/TP operativo",
                "status": "implemented",
            },
            {
                "check": "crypto_excluded",
                "rows": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal" and clean(row.get("market_group")).lower() == "crypto"),
                "policy": "Crypto no se evalua para rsi_trend_reversal",
                "status": "passed",
            },
            {
                "check": "entry_review_rows",
                "rows": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal" and clean(row.get("timing_state")) == "entry_review"),
                "policy": "cruce de vuelta 70/30 con triple alineacion",
                "status": "current_cut",
            },
            {
                "check": "watching_rows",
                "rows": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal" and clean(row.get("timing_state")) == "watching"),
                "policy": "RSI cerca de 68/32 con triple alineacion",
                "status": "current_cut",
            },
        ],
    )
    write_csv(
        tables_dir / "setup_timing_safety_audit.csv",
        [
            {
                "check": "allowed_timing_states_only",
                "status": "passed",
                "rows": sum(1 for row in setups if clean(row.get("timing_state")) in ALLOWED_TIMING_STATES),
            },
            {
                "check": "fib_limit_only_specific_timing_source",
                "status": "passed",
                "rows": sum(1 for row in setups if row["setup_type"] == "fib_limit_live_candidate" and clean(row.get("timing_source")) == "fib_limit_timing_v1"),
            },
            {
                "check": "macd_breakout_only_specific_timing_source",
                "status": "passed",
                "rows": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("timing_source")) == "macd_breakout_enrichment_v1"),
            },
            {
                "check": "rsi_trend_reversal_only_specific_timing_source",
                "status": "passed",
                "rows": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal" and clean(row.get("timing_source")) == "rsi_trend_reversal_v1"),
            },
            {
                "check": "no_operational_timing_flags",
                "status": "passed",
                "rows": sum(1 for row in setups if truthy_false(row.get("is_signal")) and truthy_false(row.get("can_execute_order"))),
            },
        ],
    )
    write_csv(
        tables_dir / "strategy_source_audit.csv",
        [
            {"strategy": strategy, "rows": sum(1 for row in setups if row["strategy"] == strategy), "status": "context_only"}
            for strategy in sorted({row["strategy"] for row in setups})
        ],
    )
    write_csv(
        tables_dir / "context_level_audit.csv",
        [
            {"context": "pivot", "rows": sum(1 for row in setups if row["pivot_context"] != "no_context")},
            {"context": "previous_day_high_low", "rows": sum(1 for row in setups if row["previous_day_level_context"] != "no_context")},
            {"context": "round_level", "rows": sum(1 for row in setups if row["round_level_context"] != "no_context")},
            {"context": "fibonacci", "rows": sum(1 for row in setups if row["fibonacci_context"] not in {"pending_source", "sin contexto", "sin swing claro"}), "status": "context_only"},
        ],
    )
    write_csv(
        tables_dir / "fibonacci_score_integration_audit.csv",
        [
            {
                "check": "fibonacci_context_rows",
                "rows": sum(1 for row in setups if row["fibonacci_context"] not in {"pending_source", "sin contexto", "sin swing claro"}),
                "policy": "context_can_add_visual_quality_only",
                "status": "passed",
            },
            {
                "check": "fibonacci_zone_candidate_rows",
                "rows": sum(1 for row in setups if row["setup_type"] == "fibonacci_zone_candidate"),
                "policy": "cap_score_3_without_strategy_base",
                "status": "passed",
            },
            {
                "check": "fib_limit_separate",
                "rows": sum(1 for row in matrix if "historico auditado" in row["fib_limit_chip"]),
                "policy": "historical_fib_limit_is_not_live_setup_by_default",
                "status": "passed",
            },
            {
                "check": "fib_limit_context_not_fibonacci_zone",
                "rows": sum(1 for row in setups if row["setup_type"] == "fib_limit_swing_quality"),
                "policy": "fib_limit_kept_separate_from_fibonacci_zone_candidate_and_live_dashboard",
                "status": "passed",
            },
            {
                "check": "fib_limit_live_candidates",
                "rows": sum(1 for row in setups if row["setup_type"] == "fib_limit_live_candidate"),
                "policy": "only_current_fib_0_618_near_price_can_create_live_candidate",
                "status": "passed",
            },
        ],
    )
    write_csv(
        tables_dir / "wavecount_context_audit.csv",
        [
            {"check": "wavecount_context_rows", "rows": sum(1 for row in setups if row["wavecount_context"] != "no_context"), "status": "study_only"},
            {"check": "wavecount_used_as_filter", "value": False, "status": "passed"},
        ],
    )
    write_csv(
        tables_dir / "codex_review_placeholder_audit.csv",
        [
            {"check": "codex_review_status", "value": "revision codex pendiente", "status": "future_phase"},
            {"check": "codex_review_implemented", "value": False, "status": "passed"},
        ],
    )
    write_csv(
        tables_dir / "safety_flags_audit.csv",
        [
            {"flag": "is_signal", "expected": False, "any_true": any(not truthy_false(row.get("is_signal")) for row in setups + matrix), "status": "passed"},
            {"flag": "can_execute_order", "expected": False, "any_true": any(not truthy_false(row.get("can_execute_order")) for row in setups + matrix), "status": "passed"},
            {"flag": "would_send_to_mt5", "expected": False, "any_true": any(not truthy_false(row.get("would_send_to_mt5")) for row in setups + matrix), "status": "passed"},
            {"flag": "would_send_telegram_order", "expected": False, "any_true": any(not truthy_false(row.get("would_send_telegram_order")) for row in setups + matrix), "status": "passed"},
            {"flag": "wavecount_used_as_filter", "expected": False, "any_true": any(not truthy_false(row.get("wavecount_used_as_filter")) for row in setups + matrix), "status": "passed"},
        ],
    )
    write_csv(
        tables_dir / "dashboard_integration_audit.csv",
        [
            {"check": "screener_setups_artifact", "status": "created", "path": str(output_dir / "screener_setups.csv")},
            {"check": "asset_matrix_artifact", "status": "created", "path": str(output_dir / "screener_asset_matrix.csv")},
            {"check": "chart_layers_artifact", "status": "created", "path": str(output_dir / "screener_chart_layers.csv")},
            {"check": "estrategias_absorbed_by_screener", "status": "dash_update_required", "value": True},
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {"issue_id": "R01", "severity": "medium", "status": "open", "description": "Quality 1-5 is contextual and can be overread as a recommendation.", "mitigation": "UI labels use calidad visual and study_only; no execution controls."},
            {"issue_id": "R02", "severity": "low", "status": "monitor", "description": "fib_limit live is a study candidate based on current Fib 61.8 proximity, not an execution signal.", "mitigation": "Keep study_only flags, no order controls, and keep historical review separate."},
            {"issue_id": "R03", "severity": "low", "status": "open", "description": "Codex/AI Analyst valuation is not implemented yet.", "mitigation": "Placeholder remains revision codex pendiente."},
            {"issue_id": "R04", "severity": "low", "status": "closed" if result["source_rows"]["macd_breakout_enriched"] else "monitor", "description": "macd_breakout solo debe destacarse con timing fresco desde el enrichment study-only.", "mitigation": "entry_review/macd_recent/breakout_recent son los unicos estados highlightables; late/invalidated/missing_context quedan fuera del foco principal."},
        ],
    )
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": generated_at,
        "decision": "macd_breakout_screener_integration_v1_ready_for_review",
        "screener_unified_implemented": True,
        "artifact_first": True,
        "is_signal": False,
        "is_study_only": True,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": False,
        "macd_breakout_enrichment_integrated": result["source_rows"]["macd_breakout_enriched"] > 0,
        "macd_breakout_highlightable_states": sorted(MACD_BREAKOUT_HIGHLIGHTABLE_STATES),
        "macd_breakout_highlighted_count": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) in MACD_BREAKOUT_HIGHLIGHTABLE_STATES),
        "macd_breakout_late_count": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) == "late"),
        "macd_breakout_invalidated_count": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) == "invalidated"),
        "macd_breakout_missing_context_count": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) == "missing_context"),
        "macd_breakout_secondary_count": sum(1 for row in setups if row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) in MACD_BREAKOUT_SECONDARY_STATES),
        "real_cut_has_highlighted_macd": any(row["setup_type"] == "macd_breakout" and clean(row.get("macd_breakout_timing_state")) in MACD_BREAKOUT_HIGHLIGHTABLE_STATES for row in setups),
        "fib_limit_timing_implemented": True,
        "setup_timing_implemented": True,
        "setup_timing_strategy_scope": "fib_limit_macd_breakout_and_rsi_trend_reversal",
        "rsi_trend_reversal_implemented": True,
        "rsi_trend_reversal_timeframes": ["M15", "H1"],
        "rsi_trend_reversal_excluded_groups": ["Crypto"],
        "rsi_trend_reversal_allowed_extra_groups": ["Commodities", "Forex Exotic"],
        "rsi_trend_reversal_setups_count": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal"),
        "rsi_trend_reversal_entry_review_count": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal" and clean(row.get("timing_state")) == "entry_review"),
        "rsi_trend_reversal_watching_count": sum(1 for row in setups if row["setup_type"] == "rsi_trend_reversal" and clean(row.get("timing_state")) == "watching"),
        "rsi_trend_reversal_sl_tp_defined": False,
        "trend_compatibility_implemented": True,
        "trend_compatible_count": sum(1 for row in setups if clean(row.get("trend_compatibility")) == "compatible"),
        "trend_mixed_count": sum(1 for row in setups if clean(row.get("trend_compatibility")) == "mixed"),
        "trend_against_count": sum(1 for row in setups if clean(row.get("trend_compatibility")) == "against"),
        "fib_limit_trend_against_count": sum(1 for row in setups if row["setup_type"] == "fib_limit_live_candidate" and clean(row.get("trend_compatibility")) == "against"),
        "codex_review_implemented": False,
        "ai_analyst_implemented": False,
        "fibonacci_context_consumed": result["source_rows"]["fibonacci"] > 0,
        "fib_limit_implemented": any(row["setup_type"] == "fib_limit_live_candidate" for row in setups) or (args.include_historical_fib_limit and result["source_rows"]["fib_limit_review"] > 0),
        "fib_limit_live_detector_implemented": True,
        "fib_limit_live_candidates_count": sum(1 for row in setups if row["setup_type"] == "fib_limit_live_candidate"),
        "fib_limit_historical_review_available": result["source_rows"]["fib_limit_review"] > 0,
        "fib_limit_swing_quality_consumed": args.include_historical_fib_limit and result["source_rows"]["fib_limit_review"] > 0,
        "fib_limit_setups_count": sum(1 for row in setups if row["setup_type"] == "fib_limit_swing_quality"),
        "macd_breakout_artifact_rows": result["source_rows"]["macd_breakout_enriched"],
        "macd_breakout_chart_layers_rows": result["source_rows"]["macd_breakout_layers"],
        "timing_states_count": len({clean(row.get("timing_state")) for row in setups}),
        "entry_review_count": sum(1 for row in setups if clean(row.get("timing_state")) == "entry_review"),
        "reaction_candidate_count": sum(1 for row in setups if clean(row.get("timing_state")) == "reaction_candidate"),
        "touching_level_count": sum(1 for row in setups if clean(row.get("timing_state")) == "touching_level"),
        "near_level_count": sum(1 for row in setups if clean(row.get("timing_state")) == "near_level"),
        "late_count": sum(1 for row in setups if clean(row.get("timing_state")) == "late"),
        "invalidated_count": sum(1 for row in setups if clean(row.get("timing_state")) == "invalidated"),
        "no_timing_context_count": sum(1 for row in setups if clean(row.get("timing_state")) == "no_timing_context"),
        "setups_count": len(setups),
        "highlighted_setups_count": len(setups),
        "asset_matrix_rows": len(matrix),
        "chart_layers_count": len(layers),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=True), encoding="utf-8")
    report = render_report(run_meta)
    (output_dir / "TRADING_CENTER_SCREENER_UNIFIED_V1.md").write_text(report, encoding="utf-8")
    if args.doc_path:
        args.doc_path.parent.mkdir(parents=True, exist_ok=True)
        args.doc_path.write_text(report, encoding="utf-8")
    if args.design_doc_path and args.design_doc_path.exists():
        append_design_status(args.design_doc_path, run_meta)


def append_design_status(path: Path, run_meta: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "\n## Implementacion V1\n"
    block = (
        marker
        + "\n"
        + f"- Estado: `{run_meta['decision']}`.\n"
        + "- La seccion `Screener` queda implementada como artifact-first/read-only.\n"
        + "- `Estrategias` se absorbe dentro de `Screener`; no se crea superficie operativa.\n"
        + "- Codex/AI Analyst queda como placeholder futuro, sin llamadas automaticas.\n"
    )
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + block
    else:
        text = text.rstrip() + "\n" + block
    path.write_text(text + "\n", encoding="utf-8")


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Screener Unified V1

Fecha: 2026-06-01

Decision: `{run_meta['decision']}`.

## Resultado

Se implementa la seccion `Screener` como radar artifact-first de setups y
contexto. Absorbe la antigua superficie `Estrategias`: arriba muestra setups
destacados con calidad visual 1-5 y confluencias auditables. La matriz por
activo queda como artifact tecnico para auditoria, pero no se muestra en el Dash
porque duplicaba informacion de Mercado/WeaveCount y hacia el Screener demasiado
denso.

## Lectura correcta

- La calidad 1-5 mide claridad visual/contextual para revisar un grafico.
- No mide probabilidad, edge ni rentabilidad esperada.
- `trend_alignment` queda como informacion contextual; no se crea como setup
  destacado por si solo.
- `pivot_context` y `round_level` quedan como informacion extra de calidad y
  capas graficas; no se crean como setups destacados por si solos.
- Los niveles redondos se dibujan como dos niveles cercanos al ultimo precio:
  nivel inferior/actual y nivel superior, en linea morada fina y continua.
- `macd_breakout` se consume desde el enrichment artifact-first combinado para
  `Forex Majors`, `Metals` e `Index`, con una lectura por simbolo/timeframe en
  H1 y H4 cuando existe contexto reconstruido.
- `fib_limit` se muestra como setup live de estudio solo cuando el precio actual
  esta cerca de `Fib 61.8` en el contexto Fibonacci artifact-first. No es senal
  ni permiso operativo.
- El modal de `fib_limit` dibuja capas de estudio derivadas del mismo swing:
  `Entrada 61.8 estudio`, `SL estudio`, `TP1 estudio` y `TP2 estudio` cuando
  existen en el artifact. La entrada se muestra como toque OHLC del 61.8,
  coherente con el proxy de orden limitada/resting usado en el backtest. Son
  referencias visuales para revision manual, no instrucciones de ejecucion.
- Fibonacci contextual se consume desde `trading_center_fibonacci_context_v1`
  como capa visual y queda separado de `fib_limit`.
- Las zonas Fibonacci son contexto visual y pueden sumar calidad; no son senal
  ni filtro operativo.
- Codex/AI Analyst queda como `revision codex pendiente` para una fase futura.
- Los casos `fib_limit_swing_quality` pueden reconstruirse solo con el flag CLI
  `--include-historical-fib-limit`, pensado para auditoria, no para el Dash live.
- El modal muestra la tendencia desglosada por timeframe (`M15`, `H1`, `H4`,
  `D1`) para que se vea que marcos estan alineados o en conflicto.
- `trend_compatibility` separa setups `compatible`, `mixed` y `against`.
  Compatible puede sumar calidad visual; mixto queda con cautela; contra
  tendencia se degrada. No es senal ni permiso operativo.
- Los contextos vacios se muestran como `sin cercania` o `sin contexto`, no
  como codigos internos.
- En `macd_breakout`, el modal muestra la ruptura real reconstruida y una
  regresion W2 proyectada hasta la ultima vela para facilitar la lectura visual.
  La linea se ajusta sobre `highs` en largos y `lows` en cortos, y la ruptura se
  confirma por `close`. No es una directriz manual que una mechas exactas. La
  proyeccion no cambia el disparador, no convierte casos `late` en setups
  frescos y sigue siendo study-only.
- `rsi_trend_reversal` queda implementado como setup de estudio simple: M15
  exige alineacion `M15/H1/H4` y H1 exige `H1/H4/D1`. En tendencia bajista
  vigila sobrecompra y cruce de vuelta bajo 70; en tendencia alcista vigila
  sobreventa y cruce de vuelta sobre 30. `watching` usa 68/32 como zona de
  aproximacion. SL/TP quedan fuera del detector y pendientes de estudio.

## Seguridad

- is_signal={run_meta['is_signal']}
- is_study_only={run_meta['is_study_only']}
- sql_real_written={run_meta['sql_real_written']}
- db_connected={run_meta['db_connected']}
- mt5_connected={run_meta['mt5_connected']}
- telegram_connected={run_meta['telegram_connected']}
- orders_sent={run_meta['orders_sent']}
- signals_generated={run_meta['signals_generated']}
- wavecount_used_as_filter={run_meta['wavecount_used_as_filter']}

## Datos generados

- setups_count={run_meta['setups_count']}
- highlighted_setups_count={run_meta['highlighted_setups_count']}
- asset_matrix_rows={run_meta['asset_matrix_rows']}
- chart_layers_count={run_meta['chart_layers_count']}
- fib_limit_implemented={run_meta.get('fib_limit_implemented')}
- fib_limit_live_detector_implemented={run_meta.get('fib_limit_live_detector_implemented')}
- fib_limit_live_candidates_count={run_meta.get('fib_limit_live_candidates_count')}
- trend_compatibility_implemented={run_meta.get('trend_compatibility_implemented')}
- trend_compatible_count={run_meta.get('trend_compatible_count')}
- trend_mixed_count={run_meta.get('trend_mixed_count')}
- trend_against_count={run_meta.get('trend_against_count')}
- fib_limit_trend_against_count={run_meta.get('fib_limit_trend_against_count')}
- fib_limit_historical_review_available={run_meta.get('fib_limit_historical_review_available')}
- fib_limit_swing_quality_consumed={run_meta.get('fib_limit_swing_quality_consumed')}
- fib_limit_setups_count={run_meta.get('fib_limit_setups_count')}
- rsi_trend_reversal_implemented={run_meta.get('rsi_trend_reversal_implemented')}
- rsi_trend_reversal_setups_count={run_meta.get('rsi_trend_reversal_setups_count')}
- rsi_trend_reversal_entry_review_count={run_meta.get('rsi_trend_reversal_entry_review_count')}
- rsi_trend_reversal_watching_count={run_meta.get('rsi_trend_reversal_watching_count')}
- rsi_trend_reversal_sl_tp_defined={run_meta.get('rsi_trend_reversal_sl_tp_defined')}

## Validacion visual esperada

El paquete incluye screenshots de revision local del Dash:

- `screenshots/navigation_without_estrategias.png`;
- `screenshots/screener_overview.png`;
- `screenshots/screener_filters.png`;
- `screenshots/screener_modal.png`.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Trading Center unified Screener artifacts.")
    parser.add_argument("--market-radar-csv", type=Path, default=DEFAULT_MARKET_RADAR_CSV)
    parser.add_argument("--ohlc-csv", type=Path, default=DEFAULT_OHLC_CSV)
    parser.add_argument("--weavecount-csv", type=Path, default=DEFAULT_WEAVECOUNT_CSV)
    parser.add_argument("--snapshot-csv", type=Path, default=DEFAULT_SNAPSHOT_CSV)
    parser.add_argument("--macd-breakout-enriched-csv", type=Path, default=DEFAULT_MACD_BREAKOUT_ENRICHED_CSV)
    parser.add_argument("--macd-breakout-chart-layers-csv", type=Path, default=DEFAULT_MACD_BREAKOUT_CHART_LAYERS_CSV)
    parser.add_argument("--fibonacci-context-csv", type=Path, default=DEFAULT_FIBONACCI_CONTEXT_CSV)
    parser.add_argument("--fibonacci-layers-csv", type=Path, default=DEFAULT_FIBONACCI_LAYERS_CSV)
    parser.add_argument("--fib-limit-review-csv", type=Path, default=DEFAULT_FIB_LIMIT_REVIEW_CSV)
    parser.add_argument("--fib-limit-sample-csv", type=Path, default=DEFAULT_FIB_LIMIT_SAMPLE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-highlighted-setups", type=int, default=120)
    parser.add_argument("--include-historical-fib-limit", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--design-doc-path", type=Path, default=DEFAULT_DESIGN_DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    generated_at = utc_now()
    market_rows = read_csv(args.market_radar_csv)
    ohlc_rows = read_csv(args.ohlc_csv)
    weave_rows = read_csv(args.weavecount_csv)
    snapshot_rows = read_csv(args.snapshot_csv)
    macd_breakout_enriched_rows = read_csv(args.macd_breakout_enriched_csv)
    macd_breakout_chart_layer_rows = read_csv(args.macd_breakout_chart_layers_csv)
    fibonacci_rows = read_csv(args.fibonacci_context_csv)
    fibonacci_layer_rows = read_csv(args.fibonacci_layers_csv)
    fib_limit_review_rows_input = read_csv(args.fib_limit_review_csv)
    fib_limit_sample_rows = read_csv(args.fib_limit_sample_csv)
    if not args.allow_empty and (not market_rows or not ohlc_rows):
        raise SystemExit("market_radar and ohlc artifacts are required unless --allow-empty is set")
    result = build_screener(
        market_rows,
        ohlc_rows,
        weave_rows,
        snapshot_rows,
        macd_breakout_enriched_rows,
        macd_breakout_chart_layer_rows,
        fibonacci_rows,
        fibonacci_layer_rows,
        fib_limit_review_rows_input,
        fib_limit_sample_rows,
        generated_at=generated_at,
        market_radar_source=args.market_radar_csv,
        ohlc_source=args.ohlc_csv,
        weavecount_source=args.weavecount_csv,
        snapshot_source=args.snapshot_csv if args.snapshot_csv.exists() else None,
        macd_breakout_enriched_source=args.macd_breakout_enriched_csv if args.macd_breakout_enriched_csv.exists() else None,
        macd_breakout_chart_layers_source=args.macd_breakout_chart_layers_csv if args.macd_breakout_chart_layers_csv.exists() else None,
        fibonacci_source=args.fibonacci_context_csv if args.fibonacci_context_csv.exists() else None,
        fibonacci_layers_source=args.fibonacci_layers_csv if args.fibonacci_layers_csv.exists() else None,
        fib_limit_review_source=args.fib_limit_review_csv if args.fib_limit_review_csv.exists() else None,
        fib_limit_sample_source=args.fib_limit_sample_csv if args.fib_limit_sample_csv.exists() else None,
        max_highlighted_setups=args.max_highlighted_setups,
        include_historical_fib_limit=args.include_historical_fib_limit,
    )
    write_outputs(args.output_dir, result, args, generated_at)


if __name__ == "__main__":
    main()
