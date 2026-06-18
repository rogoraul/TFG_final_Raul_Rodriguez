"""Swing-quality gate used to audit `fib_limit` and `macd_breakout` setups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


QUALITY_GATE_VERSION = "enbolsa_swing_quality_v1"


@dataclass(frozen=True)
class SwingQualityThresholds:
    """Thresholds used to decide whether W1/W2 structure is material enough."""
    w1_min_atr_multiple: float = 2.5
    w1_min_price_pct: float = 0.75
    w1_min_bars: int = 6
    w2_min_retr_pct: float = 0.20
    w2_max_retr_pct: float = 0.80


GROUP_PRICE_PCT_FLOOR = {
    "Forex Majors": 0.75,
    "Metals": 1.00,
    "Index": 0.80,
}

TIMEFRAME_MIN_BARS = {
    ("M30", "H1"): 8,
    ("H1", "H4"): 6,
    ("H4", "D1"): 5,
}


def resolve_thresholds(
    group: str | None = None,
    timeframe_ltf: str | None = None,
    timeframe_htf: str | None = None,
) -> SwingQualityThresholds:
    """Resolve group/timeframe-specific thresholds with conservative defaults."""
    return SwingQualityThresholds(
        w1_min_price_pct=GROUP_PRICE_PCT_FLOOR.get(group or "", SwingQualityThresholds.w1_min_price_pct),
        w1_min_bars=TIMEFRAME_MIN_BARS.get((timeframe_ltf or "", timeframe_htf or ""), SwingQualityThresholds.w1_min_bars),
    )


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _safe_int(value: Any) -> int:
    value_float = _safe_float(value)
    return int(value_float) if np.isfinite(value_float) else 0


def _prefix(direction: int) -> str:
    return "LONG" if int(direction) == 1 else "SHORT"


def evaluate_swing_quality_values(
    *,
    w1_size: float,
    w1_start: float,
    w1_bars: int,
    atr: float,
    w2_retr_pct: float,
    w2_swing: float,
    invalidated: bool,
    thresholds: SwingQualityThresholds | None = None,
) -> dict[str, Any]:
    """Evaluate W1/W2 quality metrics and return audit-ready fields."""
    thresholds = thresholds or SwingQualityThresholds()
    reasons: list[str] = []

    w1_size_abs = abs(_safe_float(w1_size))
    w1_start_abs = abs(_safe_float(w1_start))
    atr_value = _safe_float(atr)
    w2_retr_value = _safe_float(w2_retr_pct)
    w2_swing_value = _safe_float(w2_swing)
    w1_bars_int = _safe_int(w1_bars)

    w1_price_pct = (w1_size_abs / w1_start_abs * 100.0) if w1_start_abs > 0 else np.nan
    w1_atr_multiple = (w1_size_abs / atr_value) if atr_value > 0 else np.nan

    w1_pass = True
    if not np.isfinite(w1_size_abs) or w1_size_abs <= 0:
        w1_pass = False
        reasons.append("w1_missing_or_flat")
    if np.isfinite(w1_atr_multiple) and w1_atr_multiple < thresholds.w1_min_atr_multiple:
        w1_pass = False
        reasons.append("w1_below_atr_multiple")
    if not np.isfinite(w1_price_pct) or w1_price_pct < thresholds.w1_min_price_pct:
        w1_pass = False
        reasons.append("w1_below_price_pct")
    if w1_bars_int < thresholds.w1_min_bars:
        w1_pass = False
        reasons.append("w1_too_few_bars")

    w2_pass = True
    if invalidated:
        w2_pass = False
        reasons.append("w2_invalidated")
    if not np.isfinite(w2_swing_value):
        w2_pass = False
        reasons.append("w2_swing_missing")
    if not np.isfinite(w2_retr_value):
        w2_pass = False
        reasons.append("w2_retr_missing")
    elif w2_retr_value < thresholds.w2_min_retr_pct:
        w2_pass = False
        reasons.append("w2_retr_too_shallow")
    elif w2_retr_value > thresholds.w2_max_retr_pct:
        w2_pass = False
        reasons.append("w2_retr_too_deep")

    swing_quality_pass = bool(w1_pass and w2_pass)
    return {
        "swing_quality_pass": swing_quality_pass,
        "swing_quality_reason": "pass" if swing_quality_pass else ";".join(reasons),
        "w1_quality_status": "pass" if w1_pass else "blocked",
        "w2_quality_status": "pass" if w2_pass else "blocked",
        "w1_atr_multiple": w1_atr_multiple,
        "w1_price_pct": w1_price_pct,
        "w1_bars": w1_bars_int,
        "w2_retr_pct": w2_retr_value,
        "quality_gate_version": QUALITY_GATE_VERSION,
        "threshold_w1_min_atr_multiple": thresholds.w1_min_atr_multiple,
        "threshold_w1_min_price_pct": thresholds.w1_min_price_pct,
        "threshold_w1_min_bars": thresholds.w1_min_bars,
        "threshold_w2_min_retr_pct": thresholds.w2_min_retr_pct,
        "threshold_w2_max_retr_pct": thresholds.w2_max_retr_pct,
    }


def evaluate_swing_quality_row(
    row: pd.Series | dict[str, Any],
    direction: int,
    thresholds: SwingQualityThresholds | None = None,
) -> dict[str, Any]:
    """Evaluate swing quality for one setup row and direction."""
    prefix = _prefix(direction)
    getter = row.get
    return evaluate_swing_quality_values(
        w1_size=_safe_float(getter(f"{prefix}_W1_SIZE", np.nan)),
        w1_start=_safe_float(getter(f"{prefix}_W1_START_PRICE", np.nan)),
        w1_bars=_safe_int(getter(f"{prefix}_W1_BARS", 0)),
        atr=_safe_float(getter("ATR", np.nan)),
        w2_retr_pct=_safe_float(getter(f"{prefix}_W2_RETR_PCT", np.nan)),
        w2_swing=_safe_float(getter(f"{prefix}_W2_SWING_PRICE", np.nan)),
        invalidated=bool(getter(f"{prefix}_W2_INVALIDATED", False)),
        thresholds=thresholds,
    )


def annotate_swing_quality_columns(
    df: pd.DataFrame,
    group: str | None = None,
    timeframe_ltf: str | None = None,
    timeframe_htf: str | None = None,
) -> pd.DataFrame:
    """Annotate a DataFrame with long/short swing-quality audit columns."""
    thresholds = resolve_thresholds(group, timeframe_ltf, timeframe_htf)
    output = df.copy()
    for direction, prefix in ((1, "LONG"), (-1, "SHORT")):
        rows = [evaluate_swing_quality_row(row, direction, thresholds) for _, row in output.iterrows()]
        if not rows:
            continue
        for column in [
            "swing_quality_pass",
            "swing_quality_reason",
            "w1_quality_status",
            "w2_quality_status",
            "w1_atr_multiple",
            "w1_price_pct",
            "w1_bars",
            "w2_retr_pct",
        ]:
            output[f"{prefix}_{column.upper()}"] = [row[column] for row in rows]
    output["QUALITY_GATE_VERSION"] = QUALITY_GATE_VERSION
    return output
