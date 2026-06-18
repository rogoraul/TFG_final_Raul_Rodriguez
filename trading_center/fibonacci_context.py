from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "trading_center_fibonacci_context_v1"
DEFAULT_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/trading_center_fibonacci_context_v1_2026-06-02"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TRADING_CENTER_FIBONACCI_CONTEXT_V1.md"
SOURCE_GROUPS = {"Forex Majors", "Metals", "Index"}
SOURCE_TIMEFRAMES = {"H1", "H4"}
FIB_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIB_ANCHOR_RATIOS = [0.0, 1.0]
FIB_EXTENSIONS = [1.272, 1.618]

CONTEXT_FIELDNAMES = [
    "symbol",
    "market_group",
    "timeframe",
    "swing_direction",
    "swing_start_time",
    "swing_end_time",
    "swing_start_price",
    "swing_end_price",
    "swing_range_pct",
    "swing_bars",
    "swing_tr_multiple",
    "materiality_status",
    "pivot_count",
    "swing_quality",
    "swing_reason",
    "nearest_fib_level",
    "nearest_fib_ratio",
    "nearest_fib_distance_pct",
    "fibonacci_context",
    "fibonacci_status",
    "source_ohlc",
    "is_signal",
    "is_study_only",
    "can_execute_order",
    "would_send_to_mt5",
    "would_send_telegram_order",
]

LEVEL_FIELDNAMES = [
    "symbol",
    "market_group",
    "timeframe",
    "swing_direction",
    "fib_ratio",
    "fib_label",
    "fib_price",
    "distance_pct",
    "is_nearest",
    "source_method",
]

LAYER_FIELDNAMES = [
    "symbol",
    "market_group",
    "timeframe",
    "layer_type",
    "label",
    "price",
    "start_time",
    "end_time",
    "color",
    "style",
    "source",
    "is_operational",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def as_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


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


def proximity_pct(price: float, level: float) -> float:
    if price == 0:
        return 999.0
    return abs(price - level) / abs(price) * 100.0


def proximity_threshold(group: str) -> float:
    group_lower = group.lower()
    if "forex" in group_lower:
        return 0.08
    if "metals" in group_lower:
        return 0.24
    if "index" in group_lower:
        return 0.32
    return 0.28


def safety_flags() -> dict[str, bool]:
    return {
        "is_signal": False,
        "is_study_only": True,
        "can_execute_order": False,
        "would_send_to_mt5": False,
        "would_send_telegram_order": False,
    }


def group_ohlc(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        group = clean(row.get("market_group"))
        timeframe = clean(row.get("timeframe"))
        symbol = clean(row.get("symbol"))
        if group not in SOURCE_GROUPS or timeframe not in SOURCE_TIMEFRAMES or not symbol:
            continue
        grouped[(symbol, timeframe)].append(row)
    for values in grouped.values():
        values.sort(key=lambda item: parse_time(item.get("timestamp")) or datetime.min)
    return grouped


def recent_rows(rows: list[dict[str, str]], timeframe: str) -> list[dict[str, str]]:
    limit = 260 if timeframe == "H1" else 180
    return rows[-limit:]


def pivot_window(timeframe: str) -> int:
    return 3 if timeframe == "H1" else 2


def detect_pivots(rows: list[dict[str, str]], timeframe: str) -> list[dict[str, Any]]:
    window = pivot_window(timeframe)
    pivots: list[dict[str, Any]] = []
    if len(rows) < window * 2 + 6:
        return pivots
    highs = [as_float(row.get("high")) for row in rows]
    lows = [as_float(row.get("low")) for row in rows]
    for index in range(window, len(rows) - window):
        high = highs[index]
        low = lows[index]
        if high is None or low is None:
            continue
        local_highs = [value for value in highs[index - window : index + window + 1] if value is not None]
        local_lows = [value for value in lows[index - window : index + window + 1] if value is not None]
        if len(local_highs) < window * 2 + 1 or len(local_lows) < window * 2 + 1:
            continue
        ts = clean(rows[index].get("timestamp"))
        if high == max(local_highs) and local_highs.count(high) == 1:
            pivots.append({"index": index, "timestamp": ts, "price": high, "kind": "high"})
        if low == min(local_lows) and local_lows.count(low) == 1:
            pivots.append({"index": index, "timestamp": ts, "price": low, "kind": "low"})
    pivots.sort(key=lambda item: int(item["index"]))
    compressed: list[dict[str, Any]] = []
    for pivot in pivots:
        if not compressed or compressed[-1]["kind"] != pivot["kind"]:
            compressed.append(pivot)
            continue
        previous = compressed[-1]
        if pivot["kind"] == "high" and pivot["price"] > previous["price"]:
            compressed[-1] = pivot
        elif pivot["kind"] == "low" and pivot["price"] < previous["price"]:
            compressed[-1] = pivot
    return compressed


def minimum_swing_pct(group: str, timeframe: str) -> float:
    if "forex" in group.lower():
        return 0.35 if timeframe == "H1" else 0.55
    if "metals" in group.lower():
        return 0.9 if timeframe == "H1" else 1.25
    return 1.0 if timeframe == "H1" else 1.45


def minimum_swing_bars(timeframe: str) -> int:
    return 10 if timeframe == "H1" else 6


def minimum_swing_tr_multiple(group: str, timeframe: str) -> float:
    if "forex" in group.lower():
        return 3.0 if timeframe == "H1" else 2.5
    if "metals" in group.lower():
        return 3.25 if timeframe == "H1" else 2.75
    return 3.5 if timeframe == "H1" else 3.0


def true_ranges(rows: list[dict[str, str]]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for row in rows:
        high = as_float(row.get("high"))
        low = as_float(row.get("low"))
        close = as_float(row.get("close"))
        if high is None or low is None:
            if close is not None:
                previous_close = close
            continue
        candidates = [high - low]
        if previous_close is not None:
            candidates.append(abs(high - previous_close))
            candidates.append(abs(low - previous_close))
        ranges.append(max(value for value in candidates if value >= 0))
        if close is not None:
            previous_close = close
    return ranges


def median_value(values: list[float]) -> float | None:
    cleaned = sorted(value for value in values if value > 0 and not math.isnan(value) and not math.isinf(value))
    if not cleaned:
        return None
    middle = len(cleaned) // 2
    if len(cleaned) % 2:
        return cleaned[middle]
    return (cleaned[middle - 1] + cleaned[middle]) / 2.0


def swing_materiality(
    start: dict[str, Any],
    end: dict[str, Any],
    rows: list[dict[str, str]],
    group: str,
    timeframe: str,
) -> dict[str, Any]:
    start_price = float(start["price"])
    end_price = float(end["price"])
    range_abs = abs(end_price - start_price)
    range_pct = abs(end_price - start_price) / abs(start_price) * 100.0 if start_price else 0.0
    swing_bars = abs(int(end["index"]) - int(start["index"]))
    tr_median = median_value(true_ranges(rows))
    tr_multiple = range_abs / tr_median if tr_median and tr_median > 0 else 0.0
    pct_threshold = minimum_swing_pct(group, timeframe)
    bar_threshold = minimum_swing_bars(timeframe)
    tr_threshold = minimum_swing_tr_multiple(group, timeframe)
    passed = range_pct >= pct_threshold and swing_bars >= bar_threshold and tr_multiple >= tr_threshold
    return {
        "range_pct": range_pct,
        "swing_bars": swing_bars,
        "tr_multiple": tr_multiple,
        "pct_threshold": pct_threshold,
        "bar_threshold": bar_threshold,
        "tr_threshold": tr_threshold,
        "passed": passed,
    }


def select_swing(
    pivots: list[dict[str, Any]],
    rows: list[dict[str, str]],
    group: str,
    timeframe: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, dict[str, Any]]:
    threshold = minimum_swing_pct(group, timeframe)
    bars_threshold = minimum_swing_bars(timeframe)
    tr_threshold = minimum_swing_tr_multiple(group, timeframe)
    best_rejected: dict[str, Any] | None = None
    best_candidate: tuple[float, dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    latest_row_index = len(rows) - 1
    for end_index in range(len(pivots) - 1, 0, -1):
        end = pivots[end_index]
        start = pivots[end_index - 1]
        if start["kind"] == end["kind"]:
            continue
        if int(start["index"]) == int(end["index"]):
            continue
        start_price = float(start["price"])
        end_price = float(end["price"])
        if start_price <= 0:
            continue
        materiality = swing_materiality(start, end, rows, group, timeframe)
        if materiality["passed"]:
            bars_since_end = max(0, latest_row_index - int(end["index"]))
            recency_penalty = 1.0 + bars_since_end / (120.0 if timeframe == "H1" else 80.0)
            score = materiality["range_pct"] * max(1.0, materiality["tr_multiple"]) * math.log1p(materiality["swing_bars"]) / recency_penalty
            materiality = {**materiality, "bars_since_end": bars_since_end, "materiality_score": score}
            if best_candidate is None or score > best_candidate[0]:
                best_candidate = (score, start, end, materiality)
        if best_rejected is None or materiality["range_pct"] > best_rejected["range_pct"]:
            best_rejected = materiality
    if best_candidate is not None:
        _, start, end, materiality = best_candidate
        reason = (
            "swing reciente mas material "
            f"({materiality['range_pct']:.2f}%, {materiality['swing_bars']} velas, "
            f"{materiality['tr_multiple']:.2f}x TR, score {materiality['materiality_score']:.2f})"
        )
        return start, end, reason, materiality
    fallback = best_rejected or {
        "range_pct": 0.0,
        "swing_bars": 0,
        "tr_multiple": 0.0,
        "pct_threshold": threshold,
        "bar_threshold": bars_threshold,
        "tr_threshold": tr_threshold,
        "passed": False,
    }
    reason = (
        f"sin swing material: minimo {threshold:.2f}%, "
        f"{bars_threshold} velas, {tr_threshold:.2f}x TR; "
        f"mejor candidato {fallback['range_pct']:.2f}%, {fallback['swing_bars']} velas, "
        f"{fallback['tr_multiple']:.2f}x TR"
    )
    return None, None, reason, fallback


def level_price(direction: str, start_price: float, end_price: float, ratio: float) -> float:
    price_range = abs(end_price - start_price)
    if direction == "bullish":
        return end_price - price_range * ratio
    return end_price + price_range * ratio


def extension_price(direction: str, start_price: float, end_price: float, ratio: float) -> float:
    price_range = abs(end_price - start_price)
    if direction == "bullish":
        return start_price + price_range * ratio
    return start_price - price_range * ratio


def swing_quality(pivot_count: int, range_pct: float, nearest_distance: float, status: str) -> str:
    if status != "fib_near_price":
        return "media" if pivot_count >= 4 else "debil"
    if pivot_count >= 5 and range_pct >= 1.0 and nearest_distance <= 0.12:
        return "fuerte"
    if pivot_count >= 3:
        return "media"
    return "debil"


def fib_label(ratio: float) -> str:
    if ratio == 0.0:
        return "Fib 0"
    if ratio == 1.0:
        return "Fib 100"
    if ratio == 0.5:
        return "Fib 50"
    return f"Fib {ratio * 100:.1f}".replace(".0", "")


def evaluate_symbol_timeframe(symbol: str, timeframe: str, rows: list[dict[str, str]], source_ohlc: Path) -> dict[str, Any]:
    group = clean(rows[-1].get("market_group"), "not_available") if rows else "not_available"
    sliced = recent_rows(rows, timeframe)
    latest = sliced[-1] if sliced else {}
    close = as_float(latest.get("close"))
    pivots = detect_pivots(sliced, timeframe)
    start, end, reason, materiality = select_swing(pivots, sliced, group, timeframe)
    base = {
        "symbol": symbol,
        "market_group": group,
        "timeframe": timeframe,
        "source_ohlc": str(source_ohlc),
        **safety_flags(),
    }
    if close is None or not sliced:
        return {"context": {**base, "swing_direction": "not_available", "swing_start_time": "", "swing_end_time": "", "swing_start_price": "", "swing_end_price": "", "swing_range_pct": "", "swing_bars": "", "swing_tr_multiple": "", "materiality_status": "not_available", "pivot_count": len(pivots), "swing_quality": "debil", "swing_reason": "sin close disponible", "nearest_fib_level": "", "nearest_fib_ratio": "", "nearest_fib_distance_pct": "", "fibonacci_context": "sin contexto", "fibonacci_status": "no_fib_context"}, "levels": [], "layers": []}
    if start is None or end is None:
        return {"context": {**base, "swing_direction": "no_clear_swing", "swing_start_time": "", "swing_end_time": "", "swing_start_price": "", "swing_end_price": "", "swing_range_pct": f"{materiality['range_pct']:.4f}", "swing_bars": materiality["swing_bars"], "swing_tr_multiple": f"{materiality['tr_multiple']:.4f}", "materiality_status": "failed", "pivot_count": len(pivots), "swing_quality": "debil", "swing_reason": reason, "nearest_fib_level": "", "nearest_fib_ratio": "", "nearest_fib_distance_pct": "", "fibonacci_context": "sin swing claro", "fibonacci_status": "no_clear_swing"}, "levels": [], "layers": []}
    start_price = float(start["price"])
    end_price = float(end["price"])
    direction = "bullish" if end_price > start_price else "bearish"
    range_pct = abs(end_price - start_price) / abs(start_price) * 100.0 if start_price else 0.0
    levels: list[dict[str, Any]] = []
    for ratio in [*FIB_ANCHOR_RATIOS, *FIB_RATIOS]:
        price = level_price(direction, start_price, end_price, ratio)
        levels.append(
            {
                "symbol": symbol,
                "market_group": group,
                "timeframe": timeframe,
                "swing_direction": direction,
                "fib_ratio": ratio,
                "fib_label": fib_label(ratio),
                "fib_price": f"{price:.8g}",
                "distance_pct": f"{proximity_pct(close, price):.4f}",
                "is_nearest": False,
                "source_method": "confirmed_pivots_recent_swing",
            }
        )
    for ratio in FIB_EXTENSIONS:
        price = extension_price(direction, start_price, end_price, ratio)
        levels.append(
            {
                "symbol": symbol,
                "market_group": group,
                "timeframe": timeframe,
                "swing_direction": direction,
                "fib_ratio": ratio,
                "fib_label": f"Fib ext {ratio:g}",
                "fib_price": f"{price:.8g}",
                "distance_pct": f"{proximity_pct(close, price):.4f}",
                "is_nearest": False,
                "source_method": "confirmed_pivots_recent_swing",
            }
        )
    retracement_levels = [level for level in levels if float(level["fib_ratio"]) in FIB_RATIOS]
    nearest = min(retracement_levels, key=lambda item: float(item["distance_pct"]))
    nearest["is_nearest"] = True
    nearest_distance = float(nearest["distance_pct"])
    threshold = proximity_threshold(group)
    status = "fib_near_price" if nearest_distance <= threshold else "fib_context_available"
    context_text = f"cerca {nearest['fib_label']} ({nearest_distance:.2f}%)" if status == "fib_near_price" else f"contexto {nearest['fib_label']} ({nearest_distance:.2f}%)"
    quality = swing_quality(len(pivots), range_pct, nearest_distance, status)
    layers: list[dict[str, Any]] = []
    start_time = clean(sliced[0].get("timestamp"))
    end_time = clean(latest.get("timestamp"))
    for level in levels:
        ratio = float(level["fib_ratio"])
        is_extension = ratio in FIB_EXTENSIONS
        is_anchor = ratio in FIB_ANCHOR_RATIOS
        layers.append(
            {
                "symbol": symbol,
                "market_group": group,
                "timeframe": timeframe,
                "layer_type": f"fibonacci_{str(level['fib_ratio']).replace('.', '_')}",
                "label": level["fib_label"],
                "price": level["fib_price"],
                "start_time": start_time,
                "end_time": end_time,
                "color": "#d7a84b" if is_anchor else "#c793ff" if not is_extension else "#8f6bd1",
                "style": "solid" if is_anchor else "dot" if is_extension else "dash",
                "source": "fibonacci_context_v1",
                "is_operational": False,
            }
        )
    context = {
        **base,
        "swing_direction": direction,
        "swing_start_time": start["timestamp"],
        "swing_end_time": end["timestamp"],
        "swing_start_price": f"{start_price:.8g}",
        "swing_end_price": f"{end_price:.8g}",
        "swing_range_pct": f"{range_pct:.4f}",
        "swing_bars": materiality["swing_bars"],
        "swing_tr_multiple": f"{materiality['tr_multiple']:.4f}",
        "materiality_status": "passed",
        "pivot_count": len(pivots),
        "swing_quality": quality,
        "swing_reason": reason,
        "nearest_fib_level": nearest["fib_label"],
        "nearest_fib_ratio": nearest["fib_ratio"],
        "nearest_fib_distance_pct": f"{nearest_distance:.4f}",
        "fibonacci_context": context_text,
        "fibonacci_status": status,
    }
    return {"context": context, "levels": levels, "layers": layers}


def build_fibonacci_context(ohlc_rows: list[dict[str, str]], source_ohlc: Path) -> dict[str, Any]:
    grouped = group_ohlc(ohlc_rows)
    contexts: list[dict[str, Any]] = []
    levels: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    for (symbol, timeframe), rows in sorted(grouped.items()):
        result = evaluate_symbol_timeframe(symbol, timeframe, rows, source_ohlc)
        contexts.append(result["context"])
        levels.extend(result["levels"])
        layers.extend(result["layers"])
    return {
        "contexts": contexts,
        "levels": levels,
        "layers": layers,
        "source_rows": len(ohlc_rows),
        "evaluated": len(contexts),
        "symbols": len({row["symbol"] for row in contexts}),
        "groups": Counter(row["market_group"] for row in contexts),
        "timeframes": Counter(row["timeframe"] for row in contexts),
    }


def write_outputs(output_dir: Path, result: dict[str, Any], args: argparse.Namespace, generated_at: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    contexts = result["contexts"]
    levels = result["levels"]
    layers = result["layers"]
    write_csv(output_dir / "fibonacci_context.csv", contexts, CONTEXT_FIELDNAMES)
    (output_dir / "fibonacci_context.json").write_text(json.dumps(contexts, indent=2, ensure_ascii=True), encoding="utf-8")
    write_csv(output_dir / "fibonacci_levels.csv", levels, LEVEL_FIELDNAMES)
    write_csv(output_dir / "fibonacci_chart_layers.csv", layers, LAYER_FIELDNAMES)
    write_csv(
        tables_dir / "fibonacci_context_scope_policy.csv",
        [
            {"item": "is_context", "status": "required", "notes": "Zona visual calculada desde OHLC read-only."},
            {"item": "is_signal", "status": "blocked", "notes": "No genera compra/venta ni recomendacion."},
            {"item": "is_filter", "status": "blocked", "notes": "No filtra ejecucion ni ENBOLSA."},
        ],
    )
    write_csv(
        tables_dir / "fibonacci_source_universe_audit.csv",
        [
            {"source": str(args.ohlc_csv), "source_rows": result["source_rows"], "groups": "|".join(sorted(SOURCE_GROUPS)), "timeframes": "|".join(sorted(SOURCE_TIMEFRAMES)), "symbols": result["symbols"], "symbol_timeframes": result["evaluated"]},
        ],
    )
    write_csv(
        tables_dir / "fibonacci_swing_method_audit.csv",
        [
            {
                "method": "confirmed_pivots_best_recent_material_swing",
                "window_h1": 3,
                "window_h4": 2,
                "min_bars_h1": minimum_swing_bars("H1"),
                "min_bars_h4": minimum_swing_bars("H4"),
                "min_tr_multiple_forex_h1": minimum_swing_tr_multiple("Forex Majors", "H1"),
                "min_tr_multiple_forex_h4": minimum_swing_tr_multiple("Forex Majors", "H4"),
                "lookahead_policy": "only confirmed historical pivots; no future beyond loaded artifact",
                "no_clear_policy": "no_clear_swing",
            },
        ],
    )
    write_csv(
        tables_dir / "fibonacci_materiality_audit.csv",
        [
            {
                "materiality_status": status,
                "rows": sum(1 for row in contexts if row.get("materiality_status") == status),
                "policy": "passed rows can draw Fibonacci; failed rows remain context-free",
            }
            for status in ["passed", "failed", "not_available"]
        ],
    )
    write_csv(
        tables_dir / "fibonacci_level_audit.csv",
        [{"ratio": ratio, "kind": "anchor"} for ratio in FIB_ANCHOR_RATIOS]
        + [{"ratio": ratio, "kind": "retracement"} for ratio in FIB_RATIOS]
        + [{"ratio": ratio, "kind": "extension"} for ratio in FIB_EXTENSIONS],
    )
    write_csv(
        tables_dir / "fibonacci_near_price_audit.csv",
        [
            {"status": status, "rows": sum(1 for row in contexts if row["fibonacci_status"] == status)}
            for status in ["fib_near_price", "fib_context_available", "no_clear_swing", "no_fib_context"]
        ],
    )
    write_csv(
        tables_dir / "fibonacci_safety_flags_audit.csv",
        [
            {"flag": "is_signal", "any_true": any(row["is_signal"] for row in contexts), "status": "passed"},
            {"flag": "can_execute_order", "any_true": any(row["can_execute_order"] for row in contexts), "status": "passed"},
            {"flag": "would_send_to_mt5", "any_true": any(row["would_send_to_mt5"] for row in contexts), "status": "passed"},
            {"flag": "would_send_telegram_order", "any_true": any(row["would_send_telegram_order"] for row in contexts), "status": "passed"},
        ],
    )
    write_csv(
        tables_dir / "fibonacci_score_integration_audit.csv",
        [
            {"rule": "near_fibonacci_zone", "effect": "can_add_visual_quality", "limit": "context_only_no_signal"},
            {"rule": "no_clear_swing", "effect": "does_not_add_quality", "limit": "no_fabricated_zone"},
            {"rule": "fib_limit_boundary", "effect": "kept_separate", "limit": "fib_limit_implemented_false"},
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {"issue_id": "FIB01", "severity": "medium", "status": "open", "description": "Una zona Fibonacci puede leerse como entrada.", "mitigation": "Etiquetar como contexto visual; sin botones ni lenguaje operativo."},
            {"issue_id": "FIB02", "severity": "low", "status": "mitigated", "description": "El metodo de swing podia seleccionar tramos demasiado pequenos.", "mitigation": "Exigir rango minimo, velas minimas y multiple de true range antes de dibujar Fibonacci."},
            {"issue_id": "FIB03", "severity": "medium", "status": "open", "description": "La estrategia ENBOLSA usa otra logica de pivotes y debe auditarse aparte.", "mitigation": "Crear auditoria W1/ATR sin modificar estrategia."},
        ],
    )
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": generated_at,
        "decision": "trading_center_fibonacci_context_v1_ready_for_dashboard_review",
        "fibonacci_context_implemented": True,
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
        "fib_limit_implemented": False,
        "fibonacci_zone_context_implemented": True,
        "source_rows": result["source_rows"],
        "symbols_evaluated": result["symbols"],
        "symbol_timeframes_evaluated": result["evaluated"],
        "contexts_count": len(contexts),
        "levels_count": len(levels),
        "chart_layers_count": len(layers),
        "near_price_count": sum(1 for row in contexts if row["fibonacci_status"] == "fib_near_price"),
        "no_clear_swing_count": sum(1 for row in contexts if row["fibonacci_status"] == "no_clear_swing"),
        "material_swing_filter_enabled": True,
        "materiality_passed_count": sum(1 for row in contexts if row.get("materiality_status") == "passed"),
        "materiality_failed_count": sum(1 for row in contexts if row.get("materiality_status") == "failed"),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=True), encoding="utf-8")
    report = render_report(run_meta)
    (output_dir / "TRADING_CENTER_FIBONACCI_CONTEXT_V1.md").write_text(report, encoding="utf-8")
    if args.doc_path:
        args.doc_path.parent.mkdir(parents=True, exist_ok=True)
        args.doc_path.write_text(report, encoding="utf-8")


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Fibonacci Context V1

Fecha: 2026-06-02

Decision: `{run_meta['decision']}`.

## Resultado

Se implementa una capa Fibonacci artifact-first para enriquecer el modal del
Screener. La capa calcula pivotes confirmados recientes, selecciona el swing
alternante reciente mas material y genera niveles de retroceso/extension para
revision visual. Para evitar fibos sobre micro-swings, el tramo debe superar
umbrales de rango porcentual, numero minimo de velas y multiple de true range
reciente; entre los candidatos validos se prioriza el de mayor materialidad.
Tambien marca los anclajes `Fib 0` y `Fib 100` del swing para que el inicio y
el final de la medicion sean visibles en el grafico.

## Lectura correcta

- Fibonacci es contexto grafico, no senal.
- `fib_limit` sigue separado y no queda implementado en esta fase.
- `fibonacci_zone_candidate` es una zona de revision, no una orden ni un filtro.
- Si no hay swing suficiente se marca `no_clear_swing`.

## Cobertura

- symbols_evaluated={run_meta['symbols_evaluated']}
- symbol_timeframes_evaluated={run_meta['symbol_timeframes_evaluated']}
- near_price_count={run_meta['near_price_count']}
- no_clear_swing_count={run_meta['no_clear_swing_count']}
- materiality_passed_count={run_meta['materiality_passed_count']}
- materiality_failed_count={run_meta['materiality_failed_count']}
- chart_layers_count={run_meta['chart_layers_count']}

## Seguridad

- is_signal={run_meta['is_signal']}
- is_study_only={run_meta['is_study_only']}
- sql_real_written={run_meta['sql_real_written']}
- db_connected={run_meta['db_connected']}
- mt5_connected={run_meta['mt5_connected']}
- telegram_connected={run_meta['telegram_connected']}
- orders_sent={run_meta['orders_sent']}
- signals_generated={run_meta['signals_generated']}
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Trading Center Fibonacci context artifacts.")
    parser.add_argument("--ohlc-csv", type=Path, default=DEFAULT_OHLC_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--allow-empty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rows = read_csv(args.ohlc_csv)
    if not rows and not args.allow_empty:
        raise SystemExit("ohlc artifact is required unless --allow-empty is set")
    generated_at = utc_now()
    result = build_fibonacci_context(rows, args.ohlc_csv)
    write_outputs(args.output_dir, result, args, generated_at)


if __name__ == "__main__":
    main()
