from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CountConfig:
    """Configuration for WaveCount Phase 2 candidate counts.

    This layer only labels structural swing windows. It does not generate
    trading signals and it must not be used as an execution filter.
    """

    primary_degree: str = "intermediate"
    context_degree: str = "major"
    min_abc_c_vs_a: float = 0.5
    max_b_retrace: float = 1.0
    max_wave2_retrace_warning: float = 0.95
    max_wave4_retrace_warning: float = 0.95
    major_conflict_mode: str = "soft"

    def __post_init__(self) -> None:
        if not self.primary_degree:
            raise ValueError("primary_degree must not be empty")
        if not self.context_degree:
            raise ValueError("context_degree must not be empty")
        if self.min_abc_c_vs_a < 0:
            raise ValueError("min_abc_c_vs_a must be >= 0")
        if self.max_b_retrace <= 0:
            raise ValueError("max_b_retrace must be > 0")
        if self.major_conflict_mode not in {"soft", "invalidate"}:
            raise ValueError("major_conflict_mode must be 'soft' or 'invalidate'")


POINT_LABELS = {
    "impulse": ["0", "1", "2", "3", "4", "5"],
    "abc": ["0", "A", "B", "C"],
}


def _required_columns() -> list[str]:
    return [
        "example_id",
        "symbol",
        "timeframe",
        "swing_degree",
        "structural_pivot_id",
        "pivot_type",
        "pivot_extreme_time",
        "pivot_detected_at",
        "structural_detected_at",
        "pivot_extreme_price",
    ]


def _normalise_pivots(pivots: pd.DataFrame) -> pd.DataFrame:
    if pivots is None or pivots.empty:
        return pd.DataFrame()
    missing = [column for column in _required_columns() if column not in pivots.columns]
    if missing:
        raise ValueError(f"missing structural pivot columns: {missing}")

    df = pivots.copy()
    for column in ["pivot_extreme_time", "pivot_detected_at", "structural_detected_at"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")
    df["pivot_extreme_price"] = pd.to_numeric(df["pivot_extreme_price"], errors="coerce")
    df["structural_pivot_id"] = pd.to_numeric(df["structural_pivot_id"], errors="coerce")
    df = df.dropna(
        subset=[
            "pivot_extreme_time",
            "pivot_detected_at",
            "structural_detected_at",
            "pivot_extreme_price",
            "structural_pivot_id",
        ]
    )
    df = df[df["pivot_type"].isin(["high", "low"])].copy()
    return df.sort_values(
        ["example_id", "swing_degree", "structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]
    ).reset_index(drop=True)


def _price(row: pd.Series) -> float:
    return float(row["pivot_extreme_price"])


def _time(row: pd.Series, column: str) -> pd.Timestamp:
    return pd.Timestamp(row[column])


def _direction_from_points(points: pd.DataFrame, pattern: str) -> str | None:
    types = list(points["pivot_type"])
    if pattern == "impulse":
        if types == ["low", "high", "low", "high", "low", "high"]:
            return "bullish"
        if types == ["high", "low", "high", "low", "high", "low"]:
            return "bearish"
    if pattern == "abc":
        if types == ["low", "high", "low", "high"]:
            return "bullish"
        if types == ["high", "low", "high", "low"]:
            return "bearish"
    return None


def _safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return np.nan
    return numerator / denominator


def _times_are_strictly_increasing(points: pd.DataFrame, column: str) -> bool:
    times = pd.to_datetime(points[column], errors="coerce").tolist()
    if any(pd.isna(item) for item in times):
        return False
    return all(times[index] < times[index + 1] for index in range(len(times) - 1))


def _times_are_non_decreasing(points: pd.DataFrame, column: str) -> bool:
    times = pd.to_datetime(points[column], errors="coerce").tolist()
    if any(pd.isna(item) for item in times):
        return False
    return all(times[index] <= times[index + 1] for index in range(len(times) - 1))


def _major_context(
    context_pivots: pd.DataFrame,
    example_id: str,
    count_detected_at: pd.Timestamp,
    direction: str | None,
) -> dict[str, Any]:
    if context_pivots.empty:
        return {
            "major_context_state": "missing",
            "major_context_direction": "",
            "major_context_alignment": "missing",
            "major_context_last_pivot_id": np.nan,
        }

    subset = context_pivots[
        (context_pivots["example_id"] == example_id)
        & (context_pivots["structural_detected_at"] <= count_detected_at)
    ].sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"])

    if len(subset) < 2:
        return {
            "major_context_state": "insufficient",
            "major_context_direction": "",
            "major_context_alignment": "unknown",
            "major_context_last_pivot_id": int(subset.iloc[-1]["structural_pivot_id"]) if len(subset) else np.nan,
        }

    prev = subset.iloc[-2]
    last = subset.iloc[-1]
    major_direction = "bullish" if _price(last) > _price(prev) else "bearish"
    if direction is None:
        alignment = "unknown"
    elif major_direction == direction:
        alignment = "aligned"
    else:
        alignment = "opposed"
    return {
        "major_context_state": "available",
        "major_context_direction": major_direction,
        "major_context_alignment": alignment,
        "major_context_last_pivot_id": int(last["structural_pivot_id"]),
    }


def _base_count_row(
    *,
    count_id: str,
    points: pd.DataFrame,
    pattern: str,
    direction: str | None,
    state: str,
    reasons: list[str],
    context: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    first = points.iloc[0]
    last = points.iloc[-1]
    count_detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    max_used_detection = count_detected_at
    return {
        "count_id": count_id,
        "example_id": first.get("example_id", ""),
        "group": first.get("group", ""),
        "symbol": first.get("symbol", ""),
        "timeframe": first.get("timeframe", ""),
        "example_type": first.get("example_type", ""),
        "swing_degree": first.get("swing_degree", ""),
        "pattern_type": pattern,
        "count_state": state,
        "direction": direction or "",
        "start_pivot_id": int(first["structural_pivot_id"]),
        "end_pivot_id": int(last["structural_pivot_id"]),
        "start_time": first["pivot_extreme_time"],
        "end_time": last["pivot_extreme_time"],
        "count_detected_at": count_detected_at,
        "max_structural_detected_at_used": max_used_detection,
        "lookahead_safe": bool(count_detected_at >= max_used_detection),
        "reason": "; ".join(reasons),
        **metrics,
        **context,
    }


def _append_point_rows(
    leg_rows: list[dict[str, Any]],
    *,
    count_id: str,
    points: pd.DataFrame,
    pattern: str,
    metrics_by_label: dict[str, dict[str, Any]],
) -> None:
    labels = POINT_LABELS[pattern]
    for idx, (_, point) in enumerate(points.iterrows()):
        label = labels[idx]
        leg_metrics = metrics_by_label.get(label, {})
        previous = points.iloc[idx - 1] if idx > 0 else None
        leg_rows.append(
            {
                "count_id": count_id,
                "point_order": idx,
                "point_label": label,
                "leg_label": leg_metrics.get("leg_label", ""),
                "example_id": point.get("example_id", ""),
                "symbol": point.get("symbol", ""),
                "timeframe": point.get("timeframe", ""),
                "swing_degree": point.get("swing_degree", ""),
                "structural_pivot_id": int(point["structural_pivot_id"]),
                "pivot_type": point["pivot_type"],
                "pivot_extreme_time": point["pivot_extreme_time"],
                "pivot_detected_at": point["pivot_detected_at"],
                "structural_detected_at": point["structural_detected_at"],
                "pivot_extreme_price": float(point["pivot_extreme_price"]),
                "leg_start_price": float(previous["pivot_extreme_price"]) if previous is not None else np.nan,
                "leg_end_price": float(point["pivot_extreme_price"]),
                "leg_length_abs": leg_metrics.get("leg_length_abs", np.nan),
                "ratio_name": leg_metrics.get("ratio_name", ""),
                "ratio_value": leg_metrics.get("ratio_value", np.nan),
            }
        )


def _evaluate_impulse(
    points: pd.DataFrame,
    *,
    count_id: str,
    config: CountConfig,
    context_pivots: pd.DataFrame,
    leg_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    direction = _direction_from_points(points, "impulse")
    reasons: list[str] = []
    metrics: dict[str, Any] = {}
    state = "candidate_impulse"

    if direction is None:
        state = "ambiguous_count"
        reasons.append("structural sequence does not alternate as an impulse pattern")
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
                "abc_a_length": np.nan,
                "abc_b_retrace_of_a": np.nan,
                "abc_c_length": np.nan,
                "abc_c_vs_a": np.nan,
            }
        )

        if w1 <= 0 or w3 <= 0 or w5 <= 0:
            state = "ambiguous_count"
            reasons.append("one or more impulse legs have zero length")

        if direction == "bullish":
            if p2 <= p0:
                state = "invalidated_count"
                reasons.append("wave 2 breaks wave 1 origin")
            if p3 <= p1:
                state = "invalidated_count"
                reasons.append("wave 3 does not exceed wave 1 extreme")
            if p4 <= p1:
                if state != "invalidated_count":
                    state = "ambiguous_count"
                reasons.append("wave 4 overlaps wave 1 territory")
            if p5 <= p3 and state != "invalidated_count":
                state = "ambiguous_count"
                reasons.append("wave 5 fails to exceed wave 3 extreme")
        else:
            if p2 >= p0:
                state = "invalidated_count"
                reasons.append("wave 2 breaks wave 1 origin")
            if p3 >= p1:
                state = "invalidated_count"
                reasons.append("wave 3 does not exceed wave 1 extreme")
            if p4 >= p1:
                if state != "invalidated_count":
                    state = "ambiguous_count"
                reasons.append("wave 4 overlaps wave 1 territory")
            if p5 >= p3 and state != "invalidated_count":
                state = "ambiguous_count"
                reasons.append("wave 5 fails to exceed wave 3 extreme")

        if w3 < min(w1, w5):
            state = "invalidated_count"
            reasons.append("wave 3 is shorter than both wave 1 and wave 5")

        if state == "candidate_impulse" and retr2 > config.max_wave2_retrace_warning:
            state = "ambiguous_count"
            reasons.append("wave 2 retracement is visually too deep")
        if state == "candidate_impulse" and retr4 > config.max_wave4_retrace_warning:
            state = "ambiguous_count"
            reasons.append("wave 4 retracement is visually too deep")

        if state == "candidate_impulse":
            reasons.append("basic impulse constraints satisfied")

        metrics_by_label = {
            "1": {"leg_label": "wave_1", "leg_length_abs": w1},
            "2": {"leg_label": "wave_2", "leg_length_abs": w2, "ratio_name": "wave2_retrace_of_wave1", "ratio_value": retr2},
            "3": {"leg_label": "wave_3", "leg_length_abs": w3, "ratio_name": "wave3_extension_of_wave1", "ratio_value": ext3},
            "4": {"leg_label": "wave_4", "leg_length_abs": w4, "ratio_name": "wave4_retrace_of_wave3", "ratio_value": retr4},
            "5": {"leg_label": "wave_5", "leg_length_abs": w5, "ratio_name": "wave5_extension_of_wave1", "ratio_value": ext5_w1},
        }
        _append_point_rows(leg_rows, count_id=count_id, points=points, pattern="impulse", metrics_by_label=metrics_by_label)

    count_detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    context = _major_context(context_pivots, str(points.iloc[0]["example_id"]), count_detected_at, direction)
    if (
        direction is not None
        and context["major_context_alignment"] == "opposed"
        and state == "candidate_impulse"
    ):
        if config.major_conflict_mode == "invalidate":
            state = "invalidated_count"
            reasons.append("candidate impulse conflicts with major context")
        else:
            reasons.append("major context is opposed; keep as candidate for manual review")

    if direction is None:
        _append_point_rows(leg_rows, count_id=count_id, points=points, pattern="impulse", metrics_by_label={})
    return _base_count_row(
        count_id=count_id,
        points=points,
        pattern="impulse",
        direction=direction,
        state=state,
        reasons=reasons,
        context=context,
        metrics=metrics,
    )


def _evaluate_abc(
    points: pd.DataFrame,
    *,
    count_id: str,
    config: CountConfig,
    context_pivots: pd.DataFrame,
    leg_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    direction = _direction_from_points(points, "abc")
    reasons: list[str] = []
    metrics: dict[str, Any] = {}
    state = "candidate_abc"

    if direction is None:
        state = "ambiguous_count"
        reasons.append("structural sequence does not alternate as an ABC pattern")
    else:
        if not _times_are_strictly_increasing(points, "pivot_extreme_time"):
            state = "ambiguous_count"
            reasons.append("ABC pivot extremes are not in strict visual time order")
        if not _times_are_non_decreasing(points, "structural_detected_at"):
            state = "ambiguous_count"
            reasons.append("ABC structural detections are not causal/non-decreasing")

        p0, p_a, p_b, p_c = [_price(row) for _, row in points.iterrows()]
        a_len = abs(p_a - p0)
        b_len = abs(p_b - p_a)
        c_len = abs(p_c - p_b)
        b_retrace = _safe_ratio(b_len, a_len)
        c_vs_a = _safe_ratio(c_len, a_len)
        metrics.update(
            {
                "wave1_length": np.nan,
                "wave2_retrace_of_wave1": np.nan,
                "wave3_length": np.nan,
                "wave3_extension_of_wave1": np.nan,
                "wave4_retrace_of_wave3": np.nan,
                "wave5_length": np.nan,
                "wave5_extension_of_wave1": np.nan,
                "wave5_extension_of_wave3": np.nan,
                "abc_a_length": a_len,
                "abc_b_retrace_of_a": b_retrace,
                "abc_c_length": c_len,
                "abc_c_vs_a": c_vs_a,
            }
        )

        if a_len <= 0 or c_len <= 0:
            state = "ambiguous_count"
            reasons.append("A or C leg has zero length")

        if direction == "bullish":
            if p_b <= p0:
                state = "invalidated_count"
                reasons.append("B leg breaks ABC origin")
            if p_c <= p_a:
                state = "ambiguous_count" if state != "invalidated_count" else state
                reasons.append("C leg does not exceed A extreme")
        else:
            if p_b >= p0:
                state = "invalidated_count"
                reasons.append("B leg breaks ABC origin")
            if p_c >= p_a:
                state = "ambiguous_count" if state != "invalidated_count" else state
                reasons.append("C leg does not exceed A extreme")

        if b_retrace > config.max_b_retrace:
            state = "invalidated_count"
            reasons.append("B retracement exceeds configured maximum")
        if c_vs_a < config.min_abc_c_vs_a:
            state = "ambiguous_count" if state != "invalidated_count" else state
            reasons.append("ABC is too compressed: C leg is small versus A")

        if state == "candidate_abc":
            reasons.append("basic ABC constraints satisfied")

        metrics_by_label = {
            "A": {"leg_label": "A", "leg_length_abs": a_len},
            "B": {"leg_label": "B", "leg_length_abs": b_len, "ratio_name": "abc_b_retrace_of_a", "ratio_value": b_retrace},
            "C": {"leg_label": "C", "leg_length_abs": c_len, "ratio_name": "abc_c_vs_a", "ratio_value": c_vs_a},
        }
        _append_point_rows(leg_rows, count_id=count_id, points=points, pattern="abc", metrics_by_label=metrics_by_label)

    count_detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    context = _major_context(context_pivots, str(points.iloc[0]["example_id"]), count_detected_at, direction)
    if direction is None:
        _append_point_rows(leg_rows, count_id=count_id, points=points, pattern="abc", metrics_by_label={})
    return _base_count_row(
        count_id=count_id,
        points=points,
        pattern="abc",
        direction=direction,
        state=state,
        reasons=reasons,
        context=context,
        metrics=metrics,
    )


def build_candidate_counts(
    structural_pivots: pd.DataFrame,
    config: CountConfig | None = None,
    group_columns: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build isolated Elliott candidate counts from structural swings.

    The function consumes structural pivots only. It never reads raw pivots,
    OHLCV, returns, trades, or future bars beyond the last swing used by each
    candidate.
    """

    config = config or CountConfig()
    group_columns = group_columns or ["example_id"]
    pivots = _normalise_pivots(structural_pivots)
    if pivots.empty:
        return {
            "candidate_counts": pd.DataFrame(),
            "count_legs": pd.DataFrame(),
            "count_summary": pd.DataFrame(),
        }

    primary = pivots[pivots["swing_degree"] == config.primary_degree].copy()
    context = pivots[pivots["swing_degree"] == config.context_degree].copy()
    count_rows: list[dict[str, Any]] = []
    leg_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for group_values, group_df in primary.groupby(group_columns, dropna=False, sort=False):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        group_df = group_df.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]).reset_index(drop=True)
        group_meta = {column: value for column, value in zip(group_columns, group_values)}
        example_id = str(group_df.iloc[0].get("example_id", group_values[0] if group_values else ""))

        for index in range(0, max(len(group_df) - 5, 0)):
            window = group_df.iloc[index : index + 6].copy()
            count_id = f"{example_id}_{config.primary_degree}_impulse_{index + 1:03d}"
            count_rows.append(
                _evaluate_impulse(
                    window,
                    count_id=count_id,
                    config=config,
                    context_pivots=context,
                    leg_rows=leg_rows,
                )
            )

        for index in range(0, max(len(group_df) - 3, 0)):
            window = group_df.iloc[index : index + 4].copy()
            count_id = f"{example_id}_{config.primary_degree}_abc_{index + 1:03d}"
            count_rows.append(
                _evaluate_abc(
                    window,
                    count_id=count_id,
                    config=config,
                    context_pivots=context,
                    leg_rows=leg_rows,
                )
            )

        if len(group_df) < 4:
            base = group_df.iloc[0] if len(group_df) else pd.Series(group_meta)
            count_rows.append(
                {
                    "count_id": f"{example_id}_no_count",
                    "example_id": base.get("example_id", example_id),
                    "group": base.get("group", ""),
                    "symbol": base.get("symbol", ""),
                    "timeframe": base.get("timeframe", ""),
                    "example_type": base.get("example_type", ""),
                    "swing_degree": config.primary_degree,
                    "pattern_type": "none",
                    "count_state": "no_count",
                    "direction": "",
                    "start_pivot_id": np.nan,
                    "end_pivot_id": np.nan,
                    "start_time": pd.NaT,
                    "end_time": pd.NaT,
                    "count_detected_at": pd.NaT,
                    "max_structural_detected_at_used": pd.NaT,
                    "lookahead_safe": True,
                    "reason": "not enough structural swings for ABC or impulse count",
                }
            )

    counts = pd.DataFrame(count_rows)
    legs = pd.DataFrame(leg_rows)
    if not counts.empty:
        counts = counts.sort_values(["example_id", "count_detected_at", "pattern_type", "count_id"]).reset_index(drop=True)
        for group_values, group_counts in counts.groupby(group_columns, dropna=False, sort=False):
            if not isinstance(group_values, tuple):
                group_values = (group_values,)
            row = {column: value for column, value in zip(group_columns, group_values)}
            row.update(
                {
                    "total_counts": len(group_counts),
                    "candidate_impulse": int((group_counts["count_state"] == "candidate_impulse").sum()),
                    "candidate_abc": int((group_counts["count_state"] == "candidate_abc").sum()),
                    "invalidated_count": int((group_counts["count_state"] == "invalidated_count").sum()),
                    "ambiguous_count": int((group_counts["count_state"] == "ambiguous_count").sum()),
                    "no_count": int((group_counts["count_state"] == "no_count").sum()),
                    "lookahead_violations": int((~group_counts["lookahead_safe"].astype(bool)).sum()),
                }
            )
            summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    return {
        "candidate_counts": counts,
        "count_legs": legs,
        "count_summary": summary,
    }


def count_config_to_dict(config: CountConfig) -> dict[str, Any]:
    return asdict(config)
