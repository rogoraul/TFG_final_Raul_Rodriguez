from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .wavecount_counts import _normalise_pivots


@dataclass(frozen=True)
class Partial123Config:
    """Diagnostic configuration for Phase 2.3.2 partial 1-2-3 review.

    The diagnostics are deliberately conservative. They do not create signals
    and they do not change the base WaveCount candidate selection.
    """

    post_3_pivots: int = 3
    min_wave3_extension_of_wave1: float = 0.8
    min_wave3_breakout_vs_wave1: float = 0.15
    max_wave2_retrace_warning: float = 0.95

    def __post_init__(self) -> None:
        if self.post_3_pivots < 0:
            raise ValueError("post_3_pivots must be >= 0")
        if self.min_wave3_extension_of_wave1 < 0:
            raise ValueError("min_wave3_extension_of_wave1 must be >= 0")
        if self.min_wave3_breakout_vs_wave1 < 0:
            raise ValueError("min_wave3_breakout_vs_wave1 must be >= 0")
        if self.max_wave2_retrace_warning <= 0:
            raise ValueError("max_wave2_retrace_warning must be > 0")


def _partial_direction_from_types(types: list[str]) -> str | None:
    if types == ["low", "high", "low", "high"]:
        return "bullish"
    if types == ["high", "low", "high", "low"]:
        return "bearish"
    return None


def _price(row: pd.Series) -> float:
    return float(row["pivot_extreme_price"])


def _safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return np.nan
    return numerator / denominator


def _sort_pivots(pivots: pd.DataFrame) -> pd.DataFrame:
    if pivots.empty:
        return pivots.copy()
    frame = pivots.copy()
    for column in ["pivot_extreme_time", "pivot_detected_at", "structural_detected_at"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    frame["structural_pivot_id"] = pd.to_numeric(frame["structural_pivot_id"], errors="coerce")
    frame["pivot_extreme_price"] = pd.to_numeric(frame["pivot_extreme_price"], errors="coerce")
    return frame.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]).reset_index(drop=True)


def _breaks_origin(direction: str, p0: float, p2: float) -> bool:
    if direction == "bullish":
        return p2 <= p0
    return p2 >= p0


def _wave3_exceeds_wave1(direction: str, p1: float, p3: float) -> bool:
    if direction == "bullish":
        return p3 > p1
    return p3 < p1


def _wave3_breakout_abs(direction: str, p1: float, p3: float) -> float:
    if direction == "bullish":
        return max(p3 - p1, 0.0)
    return max(p1 - p3, 0.0)


def _post_3_invalidates(direction: str, post_3: pd.DataFrame, p2: float) -> tuple[bool, pd.Series | None]:
    if post_3.empty:
        return False, None
    for _, row in post_3.iterrows():
        price = _price(row)
        if direction == "bullish" and price <= p2:
            return True, row
        if direction == "bearish" and price >= p2:
            return True, row
    return False, None


def _post_3_confirms(direction: str, post_3: pd.DataFrame, p3: float) -> tuple[bool, pd.Series | None]:
    if post_3.empty:
        return False, None
    for _, row in post_3.iterrows():
        price = _price(row)
        if direction == "bullish" and price > p3:
            return True, row
        if direction == "bearish" and price < p3:
            return True, row
    return False, None


def _prior_same_type_more_extreme(direction: str, prior: pd.DataFrame, origin_type: str, p0: float) -> tuple[bool, pd.Series | None]:
    same_type = prior[prior["pivot_type"] == origin_type].copy()
    if same_type.empty:
        return False, None
    if direction == "bullish":
        more_extreme = same_type[same_type["pivot_extreme_price"] < p0]
        if more_extreme.empty:
            return False, None
        return True, more_extreme.sort_values("pivot_extreme_price", ascending=True).iloc[0]
    more_extreme = same_type[same_type["pivot_extreme_price"] > p0]
    if more_extreme.empty:
        return False, None
    return True, more_extreme.sort_values("pivot_extreme_price", ascending=False).iloc[0]


def diagnose_partial123(
    points: pd.DataFrame,
    degree_pivots: pd.DataFrame,
    *,
    config: Partial123Config | None = None,
) -> dict[str, Any]:
    """Diagnose whether a partial 1-2-3 is useful or too lax."""

    config = config or Partial123Config()
    points = _sort_pivots(points)
    degree_pivots = _sort_pivots(degree_pivots)
    base: dict[str, Any] = {
        "partial123_status": "ambiguous_partial",
        "live_state": "partial_123_provisional",
        "post_partial_diagnostic_detected_at": "",
        "post_3_pivots_checked": 0,
        "post_3_invalidates": False,
        "post_3_confirms": False,
        "post_3_event_pivot_id": np.nan,
        "post_3_event_time": "",
        "post_3_event_detected_at": "",
        "post_3_event_price": np.nan,
        "possible_prior_wave_45_context": False,
        "prior_more_extreme_origin_pivot_id": np.nan,
        "wave3_too_weak": False,
        "origin_break": False,
        "causal_note": "",
    }

    if len(points) != 4:
        base["causal_note"] = f"expected four partial pivots, got {len(points)}"
        return base

    types = list(points["pivot_type"])
    direction = _partial_direction_from_types(types)
    if direction is None:
        base["causal_note"] = "four-point window is not an alternating 1-2-3 pattern"
        return base

    p0, p1, p2, p3 = [_price(row) for _, row in points.iterrows()]
    w1 = abs(p1 - p0)
    w2 = abs(p2 - p1)
    w3 = abs(p3 - p2)
    retr2 = _safe_ratio(w2, w1)
    ext3 = _safe_ratio(w3, w1)
    breakout = _wave3_breakout_abs(direction, p1, p3)
    breakout_vs_wave1 = _safe_ratio(breakout, w1)
    partial_detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    last_pivot_id = float(points.iloc[-1]["structural_pivot_id"])

    base.update(
        {
            "direction": direction,
            "partial_detected_at": partial_detected_at,
            "wave1_length": w1,
            "wave2_retrace_of_wave1": retr2,
            "wave3_length": w3,
            "wave3_extension_of_wave1": ext3,
            "wave3_breakout_abs": breakout,
            "wave3_breakout_vs_wave1": breakout_vs_wave1,
        }
    )

    if _breaks_origin(direction, p0, p2):
        base["origin_break"] = True
        base["partial123_status"] = "ambiguous_partial"
        base["live_state"] = "invalid_partial_123"
        base["causal_note"] = "Wave 2 breaks the 1-2-3 origin."
        return base

    if not _wave3_exceeds_wave1(direction, p1, p3):
        base["wave3_too_weak"] = True
        base["partial123_status"] = "partial_123_too_lax"
        base["live_state"] = "ambiguous_partial"
        base["causal_note"] = "Wave 3 does not exceed wave 1 extreme."
        return base

    if (
        ext3 < config.min_wave3_extension_of_wave1
        or breakout_vs_wave1 < config.min_wave3_breakout_vs_wave1
        or retr2 > config.max_wave2_retrace_warning
    ):
        base["wave3_too_weak"] = True

    prior = degree_pivots[pd.to_numeric(degree_pivots["structural_pivot_id"], errors="coerce") < float(points.iloc[0]["structural_pivot_id"])].copy()
    has_prior_context, prior_origin = _prior_same_type_more_extreme(direction, prior, str(points.iloc[0]["pivot_type"]), p0)
    base["possible_prior_wave_45_context"] = bool(has_prior_context)
    if prior_origin is not None:
        base["prior_more_extreme_origin_pivot_id"] = int(prior_origin["structural_pivot_id"])

    post_3 = degree_pivots[
        (pd.to_numeric(degree_pivots["structural_pivot_id"], errors="coerce") > last_pivot_id)
        & (pd.to_datetime(degree_pivots["structural_detected_at"], errors="coerce") > partial_detected_at)
    ].copy()
    post_3 = _sort_pivots(post_3).head(config.post_3_pivots)
    base["post_3_pivots_checked"] = int(len(post_3))
    if not post_3.empty:
        base["post_partial_diagnostic_detected_at"] = pd.to_datetime(post_3["structural_detected_at"]).max()

    invalidated, invalidating_row = _post_3_invalidates(direction, post_3, p2)
    confirmed, confirming_row = _post_3_confirms(direction, post_3, p3)
    base["post_3_invalidates"] = bool(invalidated)
    base["post_3_confirms"] = bool(confirmed)

    event = invalidating_row if invalidating_row is not None else confirming_row
    if event is not None:
        base.update(
            {
                "post_3_event_pivot_id": int(event["structural_pivot_id"]),
                "post_3_event_time": event["pivot_extreme_time"],
                "post_3_event_detected_at": event["structural_detected_at"],
                "post_3_event_price": _price(event),
            }
        )

    if invalidated:
        base["partial123_status"] = "invalidated_after_3"
        base["live_state"] = "partial_123_provisional_then_invalidated"
        base["causal_note"] = "Post-3 structural pivot breaks wave 2; use only as retrospective diagnostic."
    elif base["wave3_too_weak"]:
        base["partial123_status"] = "partial_123_too_lax"
        base["live_state"] = "ambiguous_partial"
        base["causal_note"] = "Wave 3 displacement or breakout is too weak for a useful partial 1-2-3."
    elif has_prior_context and not confirmed:
        base["partial123_status"] = "belongs_to_prior_wave_45"
        base["live_state"] = "ambiguous_partial"
        base["causal_note"] = "A prior same-type pivot is more extreme; this may be the end of a previous 4-5 structure."
    elif confirmed:
        base["partial123_status"] = "valid_partial_123"
        base["live_state"] = "partial_123_provisional"
        base["causal_note"] = "Post-3 structure confirms continuation, but this remains context only, not a signal."
    else:
        base["partial123_status"] = "partial_123_provisional"
        base["live_state"] = "partial_123_provisional"
        base["causal_note"] = "No immediate post-3 invalidation; keep as provisional context only."

    return base


def diagnose_partial123_candidate_row(
    row: pd.Series,
    degree_pivots: pd.DataFrame,
    *,
    config: Partial123Config | None = None,
) -> dict[str, Any]:
    config = config or Partial123Config()
    pivots = _normalise_pivots(degree_pivots)
    subset = pivots[
        (pivots["example_id"] == row["example_id"])
        & (pivots["swing_degree"] == row["swing_degree"])
    ].copy()
    start_id = int(float(row["start_pivot_id"]))
    end_id = int(float(row["end_pivot_id"]))
    points = subset[
        (pd.to_numeric(subset["structural_pivot_id"], errors="coerce") >= start_id)
        & (pd.to_numeric(subset["structural_pivot_id"], errors="coerce") <= end_id)
    ].copy()
    diagnosis = diagnose_partial123(points, subset, config=config)
    return {
        "candidate_id": row.get("candidate_id", ""),
        "source_id": row.get("source_id", ""),
        "review_category": row.get("review_category", ""),
        "example_id": row.get("example_id", ""),
        "group": row.get("group", ""),
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "swing_degree": row.get("swing_degree", ""),
        "direction": diagnosis.get("direction", row.get("direction", "")),
        "diagnostic_status": row.get("diagnostic_status", ""),
        "start_pivot_id": start_id,
        "end_pivot_id": end_id,
        "partial_detected_at": diagnosis.get("partial_detected_at", ""),
        "post_partial_diagnostic_detected_at": diagnosis["post_partial_diagnostic_detected_at"],
        "partial123_status": diagnosis["partial123_status"],
        "live_state": diagnosis["live_state"],
        "origin_break": diagnosis["origin_break"],
        "wave3_too_weak": diagnosis["wave3_too_weak"],
        "post_3_invalidates": diagnosis["post_3_invalidates"],
        "post_3_confirms": diagnosis["post_3_confirms"],
        "post_3_pivots_checked": diagnosis["post_3_pivots_checked"],
        "post_3_event_pivot_id": diagnosis["post_3_event_pivot_id"],
        "post_3_event_time": diagnosis["post_3_event_time"],
        "post_3_event_detected_at": diagnosis["post_3_event_detected_at"],
        "post_3_event_price": diagnosis["post_3_event_price"],
        "possible_prior_wave_45_context": diagnosis["possible_prior_wave_45_context"],
        "prior_more_extreme_origin_pivot_id": diagnosis["prior_more_extreme_origin_pivot_id"],
        "wave1_length": diagnosis.get("wave1_length", np.nan),
        "wave2_retrace_of_wave1": diagnosis.get("wave2_retrace_of_wave1", np.nan),
        "wave3_length": diagnosis.get("wave3_length", np.nan),
        "wave3_extension_of_wave1": diagnosis.get("wave3_extension_of_wave1", np.nan),
        "wave3_breakout_vs_wave1": diagnosis.get("wave3_breakout_vs_wave1", np.nan),
        "causal_note": diagnosis["causal_note"],
    }


def partial123_config_to_dict(config: Partial123Config | None = None) -> dict[str, Any]:
    return asdict(config or Partial123Config())
