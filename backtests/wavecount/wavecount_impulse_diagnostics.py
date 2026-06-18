from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .wavecount_counts import CountConfig, _normalise_pivots


@dataclass(frozen=True)
class ImpulseDiagnosticsConfig:
    """Configuration for WaveCount Phase 2.2 impulse diagnostics.

    This is diagnostic only. It does not create signals and it does not relax
    the production candidate-count rules.
    """

    degrees: tuple[str, ...] = ("minor", "intermediate", "major")
    max_wave2_retrace_warning: float = 0.95
    max_wave4_retrace_warning: float = 0.95

    def __post_init__(self) -> None:
        if not self.degrees:
            raise ValueError("at least one swing degree is required")


def _direction_from_types(types: list[str]) -> str | None:
    if types == ["low", "high", "low", "high", "low", "high"]:
        return "bullish"
    if types == ["high", "low", "high", "low", "high", "low"]:
        return "bearish"
    return None


def _partial_direction_from_types(types: list[str]) -> str | None:
    if types == ["low", "high", "low", "high"]:
        return "bullish"
    if types == ["high", "low", "high", "low"]:
        return "bearish"
    return None


def _safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return np.nan
    return numerator / denominator


def _price(row: pd.Series) -> float:
    return float(row["pivot_extreme_price"])


def _joined(items: list[str]) -> str:
    return " | ".join(items)


def evaluate_impulse_window(
    points: pd.DataFrame,
    *,
    window_id: str,
    config: ImpulseDiagnosticsConfig | None = None,
) -> dict[str, Any]:
    config = config or ImpulseDiagnosticsConfig()
    first = points.iloc[0]
    last = points.iloc[-1]
    types = list(points["pivot_type"])
    direction = _direction_from_types(types)
    hard_reasons: list[str] = []
    soft_reasons: list[str] = []
    metrics: dict[str, Any] = {
        "wave1_length": np.nan,
        "wave2_retrace_of_wave1": np.nan,
        "wave3_length": np.nan,
        "wave3_extension_of_wave1": np.nan,
        "wave4_retrace_of_wave3": np.nan,
        "wave5_length": np.nan,
        "wave5_extension_of_wave1": np.nan,
        "wave5_extension_of_wave3": np.nan,
    }

    if direction is None:
        status = "not_impulse_pattern"
        soft_reasons.append("six-point window is not an alternating impulse pattern")
    else:
        p0, p1, p2, p3, p4, p5 = [_price(row) for _, row in points.iterrows()]
        w1 = abs(p1 - p0)
        w2 = abs(p2 - p1)
        w3 = abs(p3 - p2)
        w4 = abs(p4 - p3)
        w5 = abs(p5 - p4)
        retr2 = _safe_ratio(w2, w1)
        retr4 = _safe_ratio(w4, w3)
        ext3 = _safe_ratio(w3, w1)
        ext5_w1 = _safe_ratio(w5, w1)
        ext5_w3 = _safe_ratio(w5, w3)
        metrics.update(
            {
                "wave1_length": w1,
                "wave2_retrace_of_wave1": retr2,
                "wave3_length": w3,
                "wave3_extension_of_wave1": ext3,
                "wave4_retrace_of_wave3": retr4,
                "wave5_length": w5,
                "wave5_extension_of_wave1": ext5_w1,
                "wave5_extension_of_wave3": ext5_w3,
            }
        )

        if direction == "bullish":
            if p2 <= p0:
                hard_reasons.append("wave 2 breaks wave 1 origin")
            if p3 <= p1:
                hard_reasons.append("wave 3 does not exceed wave 1 extreme")
            if p4 <= p1:
                soft_reasons.append("wave 4 overlaps wave 1 territory")
            if p5 <= p3:
                soft_reasons.append("wave 5 fails to exceed wave 3 extreme")
        else:
            if p2 >= p0:
                hard_reasons.append("wave 2 breaks wave 1 origin")
            if p3 >= p1:
                hard_reasons.append("wave 3 does not exceed wave 1 extreme")
            if p4 >= p1:
                soft_reasons.append("wave 4 overlaps wave 1 territory")
            if p5 >= p3:
                soft_reasons.append("wave 5 fails to exceed wave 3 extreme")

        if w3 < min(w1, w5):
            hard_reasons.append("wave 3 is shorter than both wave 1 and wave 5")
        if retr2 > config.max_wave2_retrace_warning:
            soft_reasons.append("wave 2 retracement is visually too deep")
        if retr4 > config.max_wave4_retrace_warning:
            soft_reasons.append("wave 4 retracement is visually too deep")

        if hard_reasons:
            status = "hard_invalid_impulse"
        elif soft_reasons:
            status = "soft_impulse_near_miss"
        else:
            status = "strict_candidate_impulse"

    count_detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    return {
        "window_id": window_id,
        "example_id": first.get("example_id", ""),
        "group": first.get("group", ""),
        "symbol": first.get("symbol", ""),
        "timeframe": first.get("timeframe", ""),
        "example_type": first.get("example_type", ""),
        "swing_degree": first.get("swing_degree", ""),
        "diagnostic_type": "full_impulse_12345",
        "diagnostic_status": status,
        "direction": direction or "",
        "start_pivot_id": int(first["structural_pivot_id"]),
        "end_pivot_id": int(last["structural_pivot_id"]),
        "start_time": first["pivot_extreme_time"],
        "end_time": last["pivot_extreme_time"],
        "count_detected_at": count_detected_at,
        "max_structural_detected_at_used": count_detected_at,
        "lookahead_safe": bool(count_detected_at >= pd.to_datetime(points["structural_detected_at"]).max()),
        "hard_reasons": _joined(hard_reasons),
        "soft_reasons": _joined(soft_reasons),
        "failure_reasons": _joined(hard_reasons + soft_reasons),
        "possible_diagonal": bool("wave 4 overlaps wave 1 territory" in soft_reasons and not hard_reasons),
        "possible_truncation": bool("wave 5 fails to exceed wave 3 extreme" in soft_reasons and not hard_reasons),
        **metrics,
    }


def evaluate_partial_123_window(
    points: pd.DataFrame,
    *,
    window_id: str,
    config: ImpulseDiagnosticsConfig | None = None,
) -> dict[str, Any]:
    config = config or ImpulseDiagnosticsConfig()
    first = points.iloc[0]
    last = points.iloc[-1]
    types = list(points["pivot_type"])
    direction = _partial_direction_from_types(types)
    hard_reasons: list[str] = []
    soft_reasons: list[str] = []
    metrics: dict[str, Any] = {
        "wave1_length": np.nan,
        "wave2_retrace_of_wave1": np.nan,
        "wave3_length": np.nan,
        "wave3_extension_of_wave1": np.nan,
    }

    if direction is None:
        status = "not_partial_impulse_pattern"
        soft_reasons.append("four-point window is not an alternating 1-2-3 pattern")
    else:
        p0, p1, p2, p3 = [_price(row) for _, row in points.iterrows()]
        w1 = abs(p1 - p0)
        w2 = abs(p2 - p1)
        w3 = abs(p3 - p2)
        retr2 = _safe_ratio(w2, w1)
        ext3 = _safe_ratio(w3, w1)
        metrics.update(
            {
                "wave1_length": w1,
                "wave2_retrace_of_wave1": retr2,
                "wave3_length": w3,
                "wave3_extension_of_wave1": ext3,
            }
        )
        if direction == "bullish":
            if p2 <= p0:
                hard_reasons.append("wave 2 breaks wave 1 origin")
            if p3 <= p1:
                hard_reasons.append("wave 3 does not exceed wave 1 extreme")
        else:
            if p2 >= p0:
                hard_reasons.append("wave 2 breaks wave 1 origin")
            if p3 >= p1:
                hard_reasons.append("wave 3 does not exceed wave 1 extreme")
        if retr2 > config.max_wave2_retrace_warning:
            soft_reasons.append("wave 2 retracement is visually too deep")

        if hard_reasons:
            status = "partial_123_invalid"
        elif soft_reasons:
            status = "partial_123_ambiguous"
        else:
            status = "partial_123_candidate"

    detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    return {
        "partial_id": window_id,
        "example_id": first.get("example_id", ""),
        "group": first.get("group", ""),
        "symbol": first.get("symbol", ""),
        "timeframe": first.get("timeframe", ""),
        "example_type": first.get("example_type", ""),
        "swing_degree": first.get("swing_degree", ""),
        "diagnostic_type": "partial_impulse_123",
        "partial_status": status,
        "direction": direction or "",
        "start_pivot_id": int(first["structural_pivot_id"]),
        "end_pivot_id": int(last["structural_pivot_id"]),
        "start_time": first["pivot_extreme_time"],
        "end_time": last["pivot_extreme_time"],
        "partial_detected_at": detected_at,
        "max_structural_detected_at_used": detected_at,
        "lookahead_safe": bool(detected_at >= pd.to_datetime(points["structural_detected_at"]).max()),
        "hard_reasons": _joined(hard_reasons),
        "soft_reasons": _joined(soft_reasons),
        "failure_reasons": _joined(hard_reasons + soft_reasons),
        **metrics,
    }


def _expand_failure_reasons(impulse_diagnostics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if impulse_diagnostics.empty:
        return pd.DataFrame()
    for _, row in impulse_diagnostics.iterrows():
        hard = [item.strip() for item in str(row.get("hard_reasons", "")).split("|") if item.strip()]
        soft = [item.strip() for item in str(row.get("soft_reasons", "")).split("|") if item.strip()]
        for reason in hard:
            rows.append(
                {
                    "example_id": row.get("example_id", ""),
                    "swing_degree": row.get("swing_degree", ""),
                    "diagnostic_status": row.get("diagnostic_status", ""),
                    "reason": reason,
                    "rule_type": "hard",
                    "window_id": row.get("window_id", ""),
                }
            )
        for reason in soft:
            rows.append(
                {
                    "example_id": row.get("example_id", ""),
                    "swing_degree": row.get("swing_degree", ""),
                    "diagnostic_status": row.get("diagnostic_status", ""),
                    "reason": reason,
                    "rule_type": "soft",
                    "window_id": row.get("window_id", ""),
                }
            )
        if not hard and not soft:
            rows.append(
                {
                    "example_id": row.get("example_id", ""),
                    "swing_degree": row.get("swing_degree", ""),
                    "diagnostic_status": row.get("diagnostic_status", ""),
                    "reason": "no failure",
                    "rule_type": "none",
                    "window_id": row.get("window_id", ""),
                }
            )
    expanded = pd.DataFrame(rows)
    if expanded.empty:
        return expanded
    return (
        expanded.groupby(["swing_degree", "diagnostic_status", "rule_type", "reason"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["swing_degree", "rule_type", "count", "reason"], ascending=[True, True, False, True])
        .reset_index(drop=True)
    )


def _degree_comparison(impulses: pd.DataFrame, partials: pd.DataFrame, pivots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if pivots.empty:
        return pd.DataFrame()
    for (example_id, degree), group_pivots in pivots.groupby(["example_id", "swing_degree"], dropna=False, sort=False):
        group_impulses = impulses[(impulses["example_id"] == example_id) & (impulses["swing_degree"] == degree)]
        group_partials = partials[(partials["example_id"] == example_id) & (partials["swing_degree"] == degree)]
        rows.append(
            {
                "example_id": example_id,
                "group": group_pivots.iloc[0].get("group", ""),
                "symbol": group_pivots.iloc[0].get("symbol", ""),
                "timeframe": group_pivots.iloc[0].get("timeframe", ""),
                "swing_degree": degree,
                "structural_pivots": len(group_pivots),
                "full_impulse_windows": len(group_impulses),
                "strict_candidate_impulse": int((group_impulses["diagnostic_status"] == "strict_candidate_impulse").sum()) if not group_impulses.empty else 0,
                "soft_impulse_near_miss": int((group_impulses["diagnostic_status"] == "soft_impulse_near_miss").sum()) if not group_impulses.empty else 0,
                "hard_invalid_impulse": int((group_impulses["diagnostic_status"] == "hard_invalid_impulse").sum()) if not group_impulses.empty else 0,
                "possible_diagonal": int(group_impulses["possible_diagonal"].sum()) if not group_impulses.empty else 0,
                "possible_truncation": int(group_impulses["possible_truncation"].sum()) if not group_impulses.empty else 0,
                "partial_windows": len(group_partials),
                "partial_123_candidate": int((group_partials["partial_status"] == "partial_123_candidate").sum()) if not group_partials.empty else 0,
                "partial_123_ambiguous": int((group_partials["partial_status"] == "partial_123_ambiguous").sum()) if not group_partials.empty else 0,
                "partial_123_invalid": int((group_partials["partial_status"] == "partial_123_invalid").sum()) if not group_partials.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def build_impulse_diagnostics(
    swing_degree_pivots: pd.DataFrame,
    config: ImpulseDiagnosticsConfig | None = None,
) -> dict[str, pd.DataFrame]:
    config = config or ImpulseDiagnosticsConfig()
    pivots = _normalise_pivots(swing_degree_pivots)
    pivots = pivots[pivots["swing_degree"].isin(config.degrees)].copy()
    if pivots.empty:
        empty = pd.DataFrame()
        return {
            "impulse_diagnostics": empty,
            "impulse_failure_reasons": empty,
            "degree_impulse_comparison": empty,
            "partial_impulses": empty,
        }

    impulse_rows: list[dict[str, Any]] = []
    partial_rows: list[dict[str, Any]] = []
    for (example_id, degree), group in pivots.groupby(["example_id", "swing_degree"], dropna=False, sort=False):
        group = group.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]).reset_index(drop=True)
        for index in range(0, max(len(group) - 5, 0)):
            window = group.iloc[index : index + 6].copy()
            window_id = f"{example_id}_{degree}_impulse_{index + 1:03d}"
            impulse_rows.append(evaluate_impulse_window(window, window_id=window_id, config=config))
        for index in range(0, max(len(group) - 3, 0)):
            window = group.iloc[index : index + 4].copy()
            partial_id = f"{example_id}_{degree}_partial123_{index + 1:03d}"
            partial_rows.append(evaluate_partial_123_window(window, window_id=partial_id, config=config))

    impulses = pd.DataFrame(impulse_rows)
    partials = pd.DataFrame(partial_rows)
    failures = _expand_failure_reasons(impulses)
    comparison = _degree_comparison(impulses, partials, pivots)
    return {
        "impulse_diagnostics": impulses,
        "impulse_failure_reasons": failures,
        "degree_impulse_comparison": comparison,
        "partial_impulses": partials,
    }


def diagnostics_config_to_dict(config: ImpulseDiagnosticsConfig | None = None) -> dict[str, Any]:
    return asdict(config or ImpulseDiagnosticsConfig())


def default_count_config_for_degree(degree: str) -> CountConfig:
    return CountConfig(primary_degree=degree)
