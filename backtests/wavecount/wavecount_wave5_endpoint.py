from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .wavecount_counts import _normalise_pivots


@dataclass(frozen=True)
class Wave5EndpointConfig:
    """Diagnostic configuration for Phase 2.3.1 wave-5 endpoint review.

    This is not a trading rule. It checks whether a six-swing impulse candidate
    closes wave 5 before an immediately later structural extreme in the same
    direction. The post-count inspection is explicitly diagnostic and must not
    be interpreted as information available at the original count time.
    """

    post_count_pivots: int = 4
    min_extension_vs_wave5: float = 0.25
    min_extension_vs_wave1: float = 0.10

    def __post_init__(self) -> None:
        if self.post_count_pivots < 0:
            raise ValueError("post_count_pivots must be >= 0")
        if self.min_extension_vs_wave5 < 0:
            raise ValueError("min_extension_vs_wave5 must be >= 0")
        if self.min_extension_vs_wave1 < 0:
            raise ValueError("min_extension_vs_wave1 must be >= 0")


def _direction_from_types(types: list[str]) -> str | None:
    if types == ["low", "high", "low", "high", "low", "high"]:
        return "bullish"
    if types == ["high", "low", "high", "low", "high", "low"]:
        return "bearish"
    return None


def _price(row: pd.Series) -> float:
    return float(row["pivot_extreme_price"])


def _more_extreme(direction: str, price: float, reference: float) -> bool:
    if direction == "bullish":
        return price > reference
    if direction == "bearish":
        return price < reference
    return False


def _wave5_exceeds_wave3(direction: str, p5: float, p3: float) -> bool:
    return _more_extreme(direction, p5, p3)


def _material_extension(extension_abs: float, wave1_length: float, wave5_length: float, config: Wave5EndpointConfig) -> bool:
    wave5_threshold = wave5_length * config.min_extension_vs_wave5
    wave1_threshold = wave1_length * config.min_extension_vs_wave1
    return extension_abs >= max(wave5_threshold, 1e-12) or extension_abs >= max(wave1_threshold, 1e-12)


def _sort_pivots(pivots: pd.DataFrame) -> pd.DataFrame:
    if pivots.empty:
        return pivots.copy()
    frame = pivots.copy()
    for column in ["pivot_extreme_time", "pivot_detected_at", "structural_detected_at"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    frame["structural_pivot_id"] = pd.to_numeric(frame["structural_pivot_id"], errors="coerce")
    frame["pivot_extreme_price"] = pd.to_numeric(frame["pivot_extreme_price"], errors="coerce")
    return frame.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]).reset_index(drop=True)


def _future_same_direction_extreme(
    *,
    future: pd.DataFrame,
    direction: str,
    pivot_type: str,
    wave5_price: float,
) -> pd.Series | None:
    same_type = future[future["pivot_type"] == pivot_type].copy()
    if same_type.empty:
        return None
    same_type = same_type[same_type["pivot_extreme_price"].apply(lambda value: _more_extreme(direction, float(value), wave5_price))]
    if same_type.empty:
        return None
    if direction == "bullish":
        return same_type.sort_values("pivot_extreme_price", ascending=False).iloc[0]
    return same_type.sort_values("pivot_extreme_price", ascending=True).iloc[0]


def diagnose_wave5_endpoint(
    points: pd.DataFrame,
    degree_pivots: pd.DataFrame,
    *,
    config: Wave5EndpointConfig | None = None,
) -> dict[str, Any]:
    """Diagnose whether an impulse candidate closes wave 5 too early.

    `points` must contain the six structural pivots used by the impulse
    candidate. `degree_pivots` must contain the full structural sequence for the
    same example and swing degree.
    """

    config = config or Wave5EndpointConfig()
    points = _sort_pivots(points)
    degree_pivots = _sort_pivots(degree_pivots)

    base: dict[str, Any] = {
        "wave5_endpoint_status": "not_impulse_like",
        "proposed_endpoint_classification": "ambiguous_count",
        "diagnostic_uses_post_count_pivots": False,
        "post_count_pivots_checked": 0,
        "future_more_extreme_found": False,
        "post_wave5_extreme_pivot_id": np.nan,
        "post_wave5_extreme_time": "",
        "post_wave5_extreme_detected_at": "",
        "post_wave5_extreme_price": np.nan,
        "post_wave5_extension_abs": np.nan,
        "post_wave5_extension_vs_wave5": np.nan,
        "post_wave5_extension_vs_wave1": np.nan,
        "wave5_exceeds_wave3": False,
        "causal_note": "",
    }

    if len(points) != 6:
        base["causal_note"] = f"expected six impulse pivots, got {len(points)}"
        return base

    types = list(points["pivot_type"])
    direction = _direction_from_types(types)
    if direction is None:
        base["causal_note"] = "six-point window is not an alternating impulse pattern"
        return base

    p0, p1, _p2, p3, p4, p5 = [_price(row) for _, row in points.iterrows()]
    wave1_length = abs(p1 - p0)
    wave5_length = abs(p5 - p4)
    count_detected_at = pd.to_datetime(points["structural_detected_at"]).max()
    last_pivot_id = float(points.iloc[-1]["structural_pivot_id"])
    wave5_pivot_type = str(points.iloc[-1]["pivot_type"])
    wave5_extends = _wave5_exceeds_wave3(direction, p5, p3)

    base.update(
        {
            "wave5_exceeds_wave3": bool(wave5_extends),
            "count_detected_at": count_detected_at,
            "wave1_length": wave1_length,
            "wave5_length": wave5_length,
        }
    )

    future = degree_pivots[
        (pd.to_numeric(degree_pivots["structural_pivot_id"], errors="coerce") > last_pivot_id)
        & (pd.to_datetime(degree_pivots["structural_detected_at"], errors="coerce") > count_detected_at)
    ].copy()
    future = _sort_pivots(future).head(config.post_count_pivots)
    base["post_count_pivots_checked"] = int(len(future))
    base["diagnostic_uses_post_count_pivots"] = bool(len(future) > 0)

    if not wave5_extends:
        base["wave5_endpoint_status"] = "truncated_fifth_candidate"
        base["proposed_endpoint_classification"] = "truncated_fifth_candidate"
        base["causal_note"] = (
            "Wave 5 does not exceed wave 3. Keep as truncation/near-miss, "
            "not as a clean impulse."
        )
        return base

    future_extreme = _future_same_direction_extreme(
        future=future,
        direction=direction,
        pivot_type=wave5_pivot_type,
        wave5_price=p5,
    )
    if future_extreme is not None:
        future_price = _price(future_extreme)
        extension_abs = abs(future_price - p5)
        extension_vs_wave5 = extension_abs / wave5_length if wave5_length > 1e-12 else np.nan
        extension_vs_wave1 = extension_abs / wave1_length if wave1_length > 1e-12 else np.nan
        base.update(
            {
                "future_more_extreme_found": True,
                "post_wave5_extreme_pivot_id": int(future_extreme["structural_pivot_id"]),
                "post_wave5_extreme_time": future_extreme["pivot_extreme_time"],
                "post_wave5_extreme_detected_at": future_extreme["structural_detected_at"],
                "post_wave5_extreme_price": future_price,
                "post_wave5_extension_abs": extension_abs,
                "post_wave5_extension_vs_wave5": extension_vs_wave5,
                "post_wave5_extension_vs_wave1": extension_vs_wave1,
            }
        )
        if _material_extension(extension_abs, wave1_length, wave5_length, config):
            base["wave5_endpoint_status"] = "premature_wave5_completion"
            base["proposed_endpoint_classification"] = "premature_wave5_completion"
            base["causal_note"] = (
                "A later confirmed structural pivot makes a materially more extreme "
                "wave-5 endpoint. This is a post-count diagnostic, so live code "
                "should treat the original impulse as provisional until confirmation."
            )
            return base

    base["wave5_endpoint_status"] = "clean_or_unresolved_wave5_endpoint"
    base["proposed_endpoint_classification"] = "candidate_impulse_provisional"
    base["causal_note"] = (
        "No material later same-direction structural extreme was found inside "
        "the diagnostic horizon. The clean impulse remains provisional, not a "
        "trading signal."
    )
    return base


def diagnose_candidate_row(
    row: pd.Series,
    degree_pivots: pd.DataFrame,
    *,
    config: Wave5EndpointConfig | None = None,
) -> dict[str, Any]:
    """Diagnose one visual-review impulse/near-miss candidate row."""

    config = config or Wave5EndpointConfig()
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
    diagnosis = diagnose_wave5_endpoint(points, subset, config=config)

    original_status = str(row.get("diagnostic_status", ""))
    proposed = diagnosis["proposed_endpoint_classification"]
    if original_status == "soft_impulse_near_miss" and proposed == "candidate_impulse_provisional":
        proposed = "ambiguous_count"
    if original_status == "hard_invalid_impulse":
        proposed = "invalidated_count"

    return {
        "candidate_id": row.get("candidate_id", ""),
        "source_id": row.get("source_id", ""),
        "review_category": row.get("review_category", ""),
        "example_id": row.get("example_id", ""),
        "group": row.get("group", ""),
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "swing_degree": row.get("swing_degree", ""),
        "direction": row.get("direction", ""),
        "diagnostic_status": original_status,
        "start_pivot_id": start_id,
        "end_pivot_id": end_id,
        "count_detected_at": diagnosis.get("count_detected_at", ""),
        "wave5_endpoint_status": diagnosis["wave5_endpoint_status"],
        "proposed_endpoint_classification": proposed,
        "wave5_exceeds_wave3": diagnosis["wave5_exceeds_wave3"],
        "future_more_extreme_found": diagnosis["future_more_extreme_found"],
        "post_count_pivots_checked": diagnosis["post_count_pivots_checked"],
        "post_wave5_extreme_pivot_id": diagnosis["post_wave5_extreme_pivot_id"],
        "post_wave5_extreme_time": diagnosis["post_wave5_extreme_time"],
        "post_wave5_extreme_detected_at": diagnosis["post_wave5_extreme_detected_at"],
        "post_wave5_extreme_price": diagnosis["post_wave5_extreme_price"],
        "post_wave5_extension_abs": diagnosis["post_wave5_extension_abs"],
        "post_wave5_extension_vs_wave5": diagnosis["post_wave5_extension_vs_wave5"],
        "post_wave5_extension_vs_wave1": diagnosis["post_wave5_extension_vs_wave1"],
        "diagnostic_uses_post_count_pivots": diagnosis["diagnostic_uses_post_count_pivots"],
        "causal_note": diagnosis["causal_note"],
    }


def wave5_endpoint_config_to_dict(config: Wave5EndpointConfig | None = None) -> dict[str, Any]:
    return asdict(config or Wave5EndpointConfig())
