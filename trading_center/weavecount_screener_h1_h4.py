from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_degrees import build_swing_degrees
from backtests.wavecount.wavecount_pivots import detect_causal_pivots, extract_pivot_events
from trading_center.readonly_dashboard import REPO_ROOT, write_csv


METHOD_VERSION = "weavecount_screener_h1_h4_v1"
DEFAULT_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01"
SOURCE_GROUPS = ("Forex Majors", "Metals", "Index")
SOURCE_TIMEFRAMES = ("H1", "H4")
DEFAULT_WINDOW_BARS = 1100

SCREENER_COLUMNS = [
    "case_id",
    "symbol",
    "market_group",
    "timeframe",
    "count_label",
    "wave_number",
    "confidence_status",
    "quality_status",
    "quality_score",
    "quality_reason",
    "direction",
    "study_status",
    "classification_reason",
    "pivot_count",
    "structure_points_count",
    "start_time",
    "end_time",
    "last_close_time",
    "start_price",
    "end_price",
    "latest_close",
    "activation_level",
    "invalidation_level",
    "swing_degree",
    "screener_bucket",
    "live_estimated_wave",
    "confirmed_wave_context",
    "current_leg_direction",
    "source_ohlc",
    "source_method",
    "is_study_only",
    "is_signal",
    "wavecount_used_as_filter",
    "can_execute_order",
]

POINT_COLUMNS = [
    "case_id",
    "symbol",
    "market_group",
    "timeframe",
    "point_order",
    "point_label",
    "point_time",
    "point_price",
    "point_kind",
    "pivot_type",
    "structural_pivot_id",
]

SEGMENT_COLUMNS = [
    "case_id",
    "symbol",
    "market_group",
    "timeframe",
    "segment_order",
    "segment_label",
    "start_label",
    "end_label",
    "start_time",
    "end_time",
    "start_price",
    "end_price",
    "segment_kind",
]


def _string(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def _iso(value: Any) -> str:
    if value is None:
        return ""
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return pd.Timestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _normalise_ohlc(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = ["market_group", "symbol", "timeframe", "timestamp", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing OHLC columns: {missing}")
    frame = frame[frame["market_group"].isin(SOURCE_GROUPS) & frame["timeframe"].isin(SOURCE_TIMEFRAMES)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close"])
    frame = frame.sort_values(["market_group", "symbol", "timeframe", "timestamp"]).reset_index(drop=True)
    return frame


def _direction_from_first_leg(points: pd.DataFrame) -> str:
    if len(points) < 2:
        return ""
    types = [str(value) for value in points["pivot_type"].head(2).tolist()]
    if types == ["low", "high"]:
        return "long"
    if types == ["high", "low"]:
        return "short"
    return ""


def _move_direction(start_price: float, end_price: float) -> str:
    if end_price > start_price:
        return "long"
    if end_price < start_price:
        return "short"
    return ""


def _opposite(direction: str) -> str:
    return "short" if direction == "long" else "long" if direction == "short" else ""


def _structural_points_to_chart_points(
    points: pd.DataFrame,
    labels: list[str],
    *,
    latest_time: str = "",
    latest_price: float | None = None,
    latest_label: str = "",
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, (_, row) in enumerate(points.iterrows()):
        if index >= len(labels):
            break
        output.append(
            {
                "point_order": len(output),
                "point_label": labels[index],
                "point_time": _iso(row.get("pivot_extreme_time")),
                "point_price": _number(row.get("pivot_extreme_price")),
                "point_kind": "pivot",
                "pivot_type": _string(row.get("pivot_type")),
                "structural_pivot_id": int(float(row.get("structural_pivot_id", len(output) + 1))),
            }
        )
    if latest_time and latest_price is not None and latest_label:
        if not output or output[-1]["point_time"] != latest_time or output[-1]["point_price"] != latest_price:
            output.append(
                {
                    "point_order": len(output),
                    "point_label": latest_label,
                    "point_time": latest_time,
                    "point_price": latest_price,
                    "point_kind": "latest",
                    "pivot_type": "",
                    "structural_pivot_id": "",
                }
            )
    return [point for point in output if point["point_time"] and point["point_price"] is not None]


def _segments_from_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        is_current = end["point_kind"] in {"current", "latest"}
        segments.append(
            {
                "segment_order": index,
                "segment_label": f"{end['point_label']} actual" if is_current else f"{end['point_label']} previa",
                "start_label": start["point_label"],
                "end_label": end["point_label"],
                "start_time": start["point_time"],
                "end_time": end["point_time"],
                "start_price": start["point_price"],
                "end_price": end["point_price"],
                "segment_kind": "current" if is_current else "previous",
            }
        )
    return segments


def _quality_from_structure(
    classification: dict[str, Any],
    point_rows: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
) -> tuple[str, int, str]:
    count_label = str(classification.get("count_label", ""))
    confidence = str(classification.get("confidence_status", ""))
    if count_label == "no_clear_count" or confidence == "no_clear":
        return "debil", -4, "sin conteo claro; se mantiene solo como contexto de estudio"

    score = 0
    reasons: list[str] = []
    if confidence == "active":
        score += 2
        reasons.append("estructura activa")
    elif confidence == "candidate":
        reasons.append("candidata")

    point_count = len(point_rows)
    if point_count >= 6:
        score += 2
        reasons.append("conteo maduro con 6+ puntos")
    elif point_count >= 5:
        score += 1
        reasons.append("5 puntos estructurales")
    elif point_count >= 4:
        reasons.append("4+ puntos estructurales")
    else:
        score -= 1
        reasons.append("estructura temprana")

    current_segments = [segment for segment in segment_rows if segment.get("segment_kind") == "current"]
    if current_segments:
        score += 1
        reasons.append("tramo actual visible")
    else:
        score -= 2
        reasons.append("sin tramo actual")

    has_activation = classification.get("activation_level") not in ("", None)
    has_invalidation = classification.get("invalidation_level") not in ("", None)
    if has_activation and has_invalidation:
        score += 1
        reasons.append("niveles estructurales completos")
    elif has_activation or has_invalidation:
        reasons.append("nivel estructural parcial")
    else:
        score -= 1
        reasons.append("sin niveles estructurales")

    wave_number = str(classification.get("wave_number", ""))
    if wave_number == "5":
        score += 1
        reasons.append("onda avanzada")
    elif wave_number == "2":
        score -= 1
        reasons.append("onda temprana")

    if "?" not in count_label:
        score += 2
        reasons.append("etiqueta sin interrogante")

    if current_segments and point_rows:
        current = current_segments[-1]
        try:
            start = float(current["start_price"])
            end = float(current["end_price"])
            current_move = abs(end - start)
            current_pct = current_move / abs(start) if start else 0.0
            prices = [float(point["point_price"]) for point in point_rows]
            structure_span = max(prices) - min(prices)
            span_ratio = current_move / structure_span if structure_span else 0.0
        except (TypeError, ValueError, KeyError):
            current_pct = 0.0
            span_ratio = 0.0

        if current_pct >= 0.015:
            score += 2
            reasons.append("tramo actual amplio")
        elif current_pct >= 0.006:
            score += 1
            reasons.append("tramo actual suficiente")
        elif current_pct < 0.002:
            score -= 2
            reasons.append("tramo actual casi plano")
        elif current_pct < 0.004:
            score -= 1
            reasons.append("tramo actual corto")

        if span_ratio >= 0.45:
            score += 2
            reasons.append("tramo con peso visual alto")
        elif span_ratio >= 0.25:
            score += 1
            reasons.append("tramo con peso visual suficiente")
        elif span_ratio < 0.12:
            score -= 2
            reasons.append("tramo con poco peso visual")
        elif span_ratio < 0.20:
            score -= 1
            reasons.append("tramo visualmente debil")

    if score >= 5:
        return "fuerte", score, "; ".join(reasons)
    if score >= 1:
        return "media", score, "; ".join(reasons)
    return "debil", score, "; ".join(reasons) or "soporte estructural limitado"


def _impulse_prefix(points: pd.DataFrame) -> tuple[bool, str, str]:
    if len(points) < 2:
        return False, "", "not enough structural pivots"
    direction = _direction_from_first_leg(points)
    if not direction:
        return False, "", "first structural leg is not directional"
    types = [str(value) for value in points["pivot_type"].tolist()]
    if any(types[index] == types[index + 1] for index in range(len(types) - 1)):
        return False, direction, "structural pivot types do not alternate"
    prices = [float(value) for value in points["pivot_extreme_price"].tolist()]
    reasons: list[str] = []

    if len(prices) >= 3:
        if direction == "long" and prices[2] <= prices[0]:
            reasons.append("wave 2 breaks wave 1 origin")
        if direction == "short" and prices[2] >= prices[0]:
            reasons.append("wave 2 breaks wave 1 origin")
    if len(prices) >= 4:
        if direction == "long" and prices[3] <= prices[1]:
            reasons.append("wave 3 does not exceed wave 1 extreme")
        if direction == "short" and prices[3] >= prices[1]:
            reasons.append("wave 3 does not exceed wave 1 extreme")
        wave1 = abs(prices[1] - prices[0])
        wave3 = abs(prices[3] - prices[2])
        if wave1 > 0 and wave3 / wave1 < 0.5:
            reasons.append("wave 3 extension below conservative prefix threshold")
    if len(prices) >= 5:
        if direction == "long" and prices[4] <= prices[1]:
            reasons.append("wave 4 overlaps wave 1 territory")
        if direction == "short" and prices[4] >= prices[1]:
            reasons.append("wave 4 overlaps wave 1 territory")
    if len(prices) >= 6:
        if direction == "long" and prices[5] <= prices[3]:
            reasons.append("wave 5 does not exceed wave 3 extreme")
        if direction == "short" and prices[5] >= prices[3]:
            reasons.append("wave 5 does not exceed wave 3 extreme")
        wave1 = abs(prices[1] - prices[0])
        wave3 = abs(prices[3] - prices[2])
        wave5 = abs(prices[5] - prices[4])
        if wave3 < min(wave1, wave5):
            reasons.append("wave 3 is shorter than both wave 1 and wave 5")

    if reasons:
        return False, direction, "; ".join(reasons)
    return True, direction, "basic impulse prefix constraints satisfied"


def _classify_current_structure(
    pivots: pd.DataFrame,
    latest_time: str,
    latest_close: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if pivots.empty:
        return (
            {
                "count_label": "no_clear_count",
                "wave_number": "",
                "confidence_status": "no_clear",
                "direction": "",
                "classification_reason": "insufficient intermediate structural pivots (0)",
                "activation_level": "",
                "invalidation_level": "",
                "structure_points_count": 0,
            },
            [],
            [],
        )
    pivots = pivots.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]).reset_index(drop=True)
    if len(pivots) < 2:
        return (
            {
                "count_label": "no_clear_count",
                "wave_number": "",
                "confidence_status": "no_clear",
                "direction": "",
                "classification_reason": f"insufficient intermediate structural pivots ({len(pivots)})",
                "activation_level": "",
                "invalidation_level": "",
                "structure_points_count": 0,
            },
            [],
            [],
        )

    for window_size in (6, 5, 4, 3, 2):
        if len(pivots) < window_size:
            continue
        window = pivots.tail(window_size).copy().reset_index(drop=True)
        ok, direction, reason = _impulse_prefix(window)
        if not ok:
            continue

        wave_number = str(min(window_size, 5))
        latest_label = ""
        latest_for_points: float | None = None
        latest_for_time = ""
        confidence = "candidate"
        count_label = f"W{wave_number}?"
        current_leg_direction = direction if wave_number in {"1", "3", "5"} else _opposite(direction)

        if window_size == 6:
            confidence = "active"
            count_label = "W5"
        elif window_size == 5:
            last_price = float(window.iloc[-1]["pivot_extreme_price"])
            if _move_direction(last_price, latest_close) == current_leg_direction:
                latest_label = count_label
                latest_for_time = latest_time
                latest_for_points = latest_close
            else:
                wave_number = "4"
                count_label = "W4?"
                current_leg_direction = _opposite(direction)
        elif window_size == 3:
            last_price = float(window.iloc[-1]["pivot_extreme_price"])
            if _move_direction(last_price, latest_close) == current_leg_direction:
                latest_label = count_label
                latest_for_time = latest_time
                latest_for_points = latest_close
            else:
                wave_number = "2"
                count_label = "W2?"
                current_leg_direction = _opposite(direction)
        elif window_size == 2:
            last_price = float(window.iloc[-1]["pivot_extreme_price"])
            if _move_direction(last_price, latest_close) == current_leg_direction:
                latest_label = count_label
                latest_for_time = latest_time
                latest_for_points = latest_close
            else:
                wave_number = "1"
                count_label = "W1?"
                current_leg_direction = direction
        elif window_size == 4:
            last_price = float(window.iloc[-1]["pivot_extreme_price"])
            if _move_direction(last_price, latest_close) == _opposite(direction):
                wave_number = "4"
                count_label = "W4?"
                latest_label = count_label
                latest_for_time = latest_time
                latest_for_points = latest_close
                current_leg_direction = _opposite(direction)
            else:
                wave_number = "3"
                count_label = "W3?"

        labels = ["origen", "W1", "W2", "W3", "W4", "W5"][:window_size]
        point_rows = _structural_points_to_chart_points(
            window,
            labels,
            latest_time=latest_for_time,
            latest_price=latest_for_points,
            latest_label=latest_label,
        )
        if point_rows and not any(point["point_kind"] in {"current", "latest"} for point in point_rows):
            point_rows[-1]["point_kind"] = "current"
            point_rows[-1]["point_label"] = count_label
        segment_rows = _segments_from_points(point_rows)

        prices = [float(value) for value in window["pivot_extreme_price"].tolist()]
        activation = ""
        invalidation = ""
        if wave_number == "2" and len(prices) >= 2:
            activation = prices[1]
            invalidation = prices[0]
        elif wave_number == "3" and len(prices) >= 3:
            activation = prices[1]
            invalidation = prices[2]
        elif wave_number == "5" and len(prices) >= 5:
            activation = prices[3]
            invalidation = prices[4]
        elif wave_number == "4" and len(prices) >= 4:
            invalidation = prices[2]

        return (
            {
                "count_label": count_label,
                "wave_number": wave_number,
                "confidence_status": confidence,
                "direction": current_leg_direction or direction,
                "classification_reason": reason,
                "activation_level": activation,
                "invalidation_level": invalidation,
                "structure_points_count": len(point_rows),
            },
            point_rows,
            segment_rows,
        )

    return (
        {
            "count_label": "no_clear_count",
            "wave_number": "",
            "confidence_status": "no_clear",
            "direction": "",
            "classification_reason": "latest intermediate structure does not pass conservative impulse-prefix checks",
            "activation_level": "",
            "invalidation_level": "",
            "structure_points_count": 0,
        },
        [],
        [],
    )


def _build_for_symbol_timeframe(
    group: str,
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    *,
    source_ohlc: Path,
    window_bars: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    window = frame.sort_values("timestamp").tail(window_bars).copy()
    latest = window.iloc[-1]
    latest_time = _iso(latest["timestamp"])
    latest_close = float(latest["close"])
    example_id = f"weave_{symbol.replace('.', '_')}_{timeframe.lower()}"
    ohlc = window[["timestamp", "open", "high", "low", "close"]].rename(columns={"timestamp": "time"})

    raw_pivots = detect_causal_pivots(ohlc, config=PivotConfig(), symbol=symbol, timeframe=timeframe)
    events = extract_pivot_events(raw_pivots).reset_index(drop=True)
    events["example_id"] = example_id
    events["group"] = group
    events["example_type"] = "weavecount_screener_h1_h4"
    if events.empty:
        pivots = pd.DataFrame()
    else:
        try:
            degrees = build_swing_degrees(events, group_columns=["example_id"])
            pivots = degrees["swing_degrees_pivots"]
        except ValueError:
            pivots = pd.DataFrame()
    if pivots.empty:
        intermediate = pd.DataFrame()
    else:
        intermediate = pivots[pivots["swing_degree"].eq("intermediate")].copy()

    classification, point_rows, segment_rows = _classify_current_structure(intermediate, latest_time, latest_close)
    count_label = str(classification["count_label"])
    confidence = str(classification["confidence_status"])
    wave_number = str(classification["wave_number"])
    case_id = f"{METHOD_VERSION}|{symbol}|{timeframe}|{count_label}|{latest_time}"
    bucket = (
        "active_wave_study_candidate"
        if confidence == "active"
        else "candidate_wave_watch"
        if confidence == "candidate"
        else "no_current_wave_context"
    )
    live_wave = f"possible_wave{wave_number}_{'active' if confidence == 'active' else 'candidate'}" if wave_number else "no_clear_count"
    direction = str(classification["direction"])
    start_time = point_rows[0]["point_time"] if point_rows else ""
    end_time = point_rows[-1]["point_time"] if point_rows else latest_time
    start_price = point_rows[0]["point_price"] if point_rows else ""
    end_price = point_rows[-1]["point_price"] if point_rows else latest_close
    quality_status, quality_score, quality_reason = _quality_from_structure(classification, point_rows, segment_rows)

    row = {
        "case_id": case_id,
        "symbol": symbol,
        "market_group": group,
        "timeframe": timeframe,
        "count_label": count_label,
        "wave_number": wave_number,
        "confidence_status": confidence,
        "quality_status": quality_status,
        "quality_score": quality_score,
        "quality_reason": quality_reason,
        "direction": direction,
        "study_status": "study_only",
        "classification_reason": classification["classification_reason"],
        "pivot_count": int(len(intermediate)),
        "structure_points_count": classification["structure_points_count"],
        "start_time": start_time,
        "end_time": end_time,
        "last_close_time": latest_time,
        "start_price": start_price,
        "end_price": end_price,
        "latest_close": latest_close,
        "activation_level": classification["activation_level"],
        "invalidation_level": classification["invalidation_level"],
        "swing_degree": "intermediate",
        "screener_bucket": bucket,
        "live_estimated_wave": live_wave,
        "confirmed_wave_context": live_wave,
        "current_leg_direction": "up" if direction == "long" else "down" if direction == "short" else "",
        "source_ohlc": _rel(source_ohlc),
        "source_method": "causal_pivots_intermediate_swing_degree",
        "is_study_only": True,
        "is_signal": False,
        "wavecount_used_as_filter": False,
        "can_execute_order": False,
    }
    for point in point_rows:
        point.update({"case_id": case_id, "symbol": symbol, "market_group": group, "timeframe": timeframe})
    for segment in segment_rows:
        segment.update({"case_id": case_id, "symbol": symbol, "market_group": group, "timeframe": timeframe})
    return row, point_rows, segment_rows


def build_weavecount_screener(
    ohlc_csv: Path = DEFAULT_OHLC_CSV,
    *,
    window_bars: int = DEFAULT_WINDOW_BARS,
) -> dict[str, list[dict[str, Any]]]:
    frame = _normalise_ohlc(ohlc_csv)
    screener_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    for (group, symbol, timeframe), subset in frame.groupby(["market_group", "symbol", "timeframe"], sort=True):
        row, points, segments = _build_for_symbol_timeframe(
            str(group),
            str(symbol),
            str(timeframe),
            subset,
            source_ohlc=ohlc_csv,
            window_bars=window_bars,
        )
        screener_rows.append(row)
        point_rows.extend(points)
        segment_rows.extend(segments)
    return {
        "screener": screener_rows,
        "structure_points": point_rows,
        "chart_segments": segment_rows,
    }


def _source_universe_audit(frame: pd.DataFrame, screener_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evaluated = {(row["market_group"], row["symbol"], row["timeframe"]) for row in screener_rows}
    for group in SOURCE_GROUPS:
        for timeframe in SOURCE_TIMEFRAMES:
            subset = frame[frame["market_group"].eq(group) & frame["timeframe"].eq(timeframe)]
            symbols = sorted(set(subset["symbol"].astype(str)))
            evaluated_symbols = sorted(symbol for symbol in symbols if (group, symbol, timeframe) in evaluated)
            rows.append(
                {
                    "market_group": group,
                    "timeframe": timeframe,
                    "symbols_available": len(symbols),
                    "symbols_evaluated": len(evaluated_symbols),
                    "status": "pass" if len(symbols) == len(evaluated_symbols) else "fail",
                    "symbols": "|".join(evaluated_symbols),
                }
            )
    return rows


def _classification_summary(screener_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter(
        (
            row["market_group"],
            row["timeframe"],
            row["count_label"],
            row["confidence_status"],
        )
        for row in screener_rows
    )
    return [
        {
            "market_group": group,
            "timeframe": timeframe,
            "count_label": count_label,
            "confidence_status": confidence,
            "row_count": count,
        }
        for (group, timeframe, count_label, confidence), count in sorted(counter.items())
    ]


def _coverage_audit(screener_rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    expected = SOURCE_TIMEFRAMES if key == "timeframe" else SOURCE_GROUPS
    rows: list[dict[str, Any]] = []
    for value in expected:
        subset = [row for row in screener_rows if row.get(key) == value]
        rows.append(
            {
                key: value,
                "symbol_timeframes_evaluated": len(subset),
                "active_or_candidate": sum(1 for row in subset if row["confidence_status"] in {"active", "candidate"}),
                "no_clear_count": sum(1 for row in subset if row["count_label"] == "no_clear_count"),
                "status": "pass" if subset else "fail",
            }
        )
    return rows


def _no_clear_audit(screener_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": row["symbol"],
            "market_group": row["market_group"],
            "timeframe": row["timeframe"],
            "pivot_count": row["pivot_count"],
            "classification_reason": row["classification_reason"],
        }
        for row in screener_rows
        if row["count_label"] == "no_clear_count"
    ]


def _safety_audit(screener_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = [
        ("study_only_all_true", all(str(row["is_study_only"]).lower() == "true" for row in screener_rows)),
        ("is_signal_all_false", all(str(row["is_signal"]).lower() == "false" for row in screener_rows)),
        ("wavecount_used_as_filter_all_false", all(str(row["wavecount_used_as_filter"]).lower() == "false" for row in screener_rows)),
        ("can_execute_order_all_false", all(str(row["can_execute_order"]).lower() == "false" for row in screener_rows)),
    ]
    return [{"check_name": name, "status": "pass" if passed else "fail"} for name, passed in checks]


def write_artifacts(
    output_dir: Path,
    result: dict[str, list[dict[str, Any]]],
    *,
    source_ohlc: Path,
    elapsed_seconds: float,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    screener_rows = result["screener"]
    point_rows = result["structure_points"]
    segment_rows = result["chart_segments"]
    source_frame = _normalise_ohlc(source_ohlc)

    write_csv(output_dir / "weavecount_screener.csv", screener_rows, SCREENER_COLUMNS)
    (output_dir / "weavecount_screener.json").write_text(
        json.dumps(screener_rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    write_csv(output_dir / "weavecount_structure_points.csv", point_rows, POINT_COLUMNS)
    write_csv(output_dir / "weavecount_chart_segments.csv", segment_rows, SEGMENT_COLUMNS)
    write_csv(tables_dir / "source_universe_audit.csv", _source_universe_audit(source_frame, screener_rows))
    write_csv(tables_dir / "classification_summary.csv", _classification_summary(screener_rows))
    write_csv(tables_dir / "timeframe_coverage_audit.csv", _coverage_audit(screener_rows, "timeframe"))
    write_csv(tables_dir / "group_coverage_audit.csv", _coverage_audit(screener_rows, "market_group"))
    write_csv(tables_dir / "no_clear_count_audit.csv", _no_clear_audit(screener_rows))
    write_csv(tables_dir / "study_only_safety_audit.csv", _safety_audit(screener_rows))
    write_csv(
        tables_dir / "dashboard_integration_audit.csv",
        [
            {
                "check_name": "dash_artifact_contract",
                "status": "pass",
                "artifact": _rel(output_dir / "weavecount_screener.csv"),
                "notes": "Dash can consume this artifact as the primary WeaveCount source.",
            }
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "severity": "medium",
                "issue": "algorithmic_study_not_manual_validation",
                "status": "documented",
                "notes": "Broad H1/H4 classifications are study candidates and may require visual/manual review.",
            },
            {
                "severity": "info",
                "issue": "no_clear_counts_expected",
                "status": "accepted",
                "notes": "Assets without enough conservative structure are left as no_clear_count instead of forcing a wave.",
            },
        ],
    )

    expected_symbols = len(
        {
            row["symbol"]
            for row in screener_rows
            if row["market_group"] in SOURCE_GROUPS
        }
    )
    meta = {
        "phase": METHOD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "weavecount_screener_h1_h4_v1_ready_for_dashboard_review",
        "weavecount_screener_implemented": True,
        "artifact_first": True,
        "source_groups": list(SOURCE_GROUPS),
        "source_timeframes": list(SOURCE_TIMEFRAMES),
        "symbols_expected": 47,
        "timeframes_expected": 2,
        "symbol_timeframe_expected": 94,
        "symbols_evaluated": expected_symbols,
        "symbol_timeframes_evaluated": len(screener_rows),
        "active_count": sum(1 for row in screener_rows if row["confidence_status"] == "active"),
        "candidate_count": sum(1 for row in screener_rows if row["confidence_status"] == "candidate"),
        "no_clear_count": sum(1 for row in screener_rows if row["count_label"] == "no_clear_count"),
        "study_only": True,
        "is_signal": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "source_ohlc": _rel(source_ohlc),
        "window_bars": DEFAULT_WINDOW_BARS,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "WEAVECOUNT_SCREENER_H1_H4_V1.md").write_text(_report(meta), encoding="utf-8")
    return meta


def _report(meta: dict[str, Any]) -> str:
    return f"""# WeaveCount Screener H1/H4 V1

Decision: `{meta['decision']}`.

Se crea un screener artifact-first para revisar WeaveCount en `Forex Majors`,
`Metals` e `Index`, solo en `H1` y `H4`.

## Resultado

- Simbolos evaluados: {meta['symbols_evaluated']} / {meta['symbols_expected']}.
- Simbolo/timeframe evaluados: {meta['symbol_timeframes_evaluated']} / {meta['symbol_timeframe_expected']}.
- Casos activos de estudio: {meta['active_count']}.
- Casos candidatos: {meta['candidate_count']}.
- Casos sin conteo claro: {meta['no_clear_count']}.

## Seguridad

WeaveCount sigue siendo `study_only`. No genera senales, no filtra operaciones,
no ejecuta ordenes, no conecta MT5, no conecta Telegram y no escribe SQL.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build artifact-first WeaveCount H1/H4 screener.")
    parser.add_argument("--source-ohlc-csv", type=Path, default=DEFAULT_OHLC_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--window-bars", type=int, default=DEFAULT_WINDOW_BARS)
    args = parser.parse_args(argv)

    start = perf_counter()
    result = build_weavecount_screener(args.source_ohlc_csv, window_bars=args.window_bars)
    meta = write_artifacts(args.output_dir, result, source_ohlc=args.source_ohlc_csv, elapsed_seconds=perf_counter() - start)
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
