from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .wavecount_structure import StructuralPivotConfig, build_structural_pivots_by_group


@dataclass(frozen=True)
class SwingDegreeSpec:
    """Swing degree configuration for WaveCount Phase 1.6."""

    name: str
    config: StructuralPivotConfig

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("degree name must not be empty")


DEFAULT_SWING_DEGREES = (
    SwingDegreeSpec(
        "minor",
        StructuralPivotConfig(
            min_leg_atr_multiplier=2.0,
            min_leg_relative_move_pct=0.002,
            min_leg_bars=4,
        ),
    ),
    SwingDegreeSpec(
        "intermediate",
        StructuralPivotConfig(
            min_leg_atr_multiplier=3.0,
            min_leg_relative_move_pct=0.003,
            min_leg_bars=6,
        ),
    ),
    SwingDegreeSpec(
        "major",
        StructuralPivotConfig(
            min_leg_atr_multiplier=5.0,
            min_leg_relative_move_pct=0.005,
            min_leg_bars=10,
        ),
    ),
)


def _add_degree_columns(frame: pd.DataFrame, spec: SwingDegreeSpec) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["swing_degree"] = spec.name
    result["degree_min_leg_atr_multiplier"] = spec.config.min_leg_atr_multiplier
    result["degree_min_leg_relative_move_pct"] = spec.config.min_leg_relative_move_pct
    result["degree_min_leg_bars"] = spec.config.min_leg_bars
    return result


def build_swing_degrees(
    raw_pivots: pd.DataFrame,
    degree_specs: Iterable[SwingDegreeSpec] | None = None,
    group_columns: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build structural pivots for several visual swing degrees.

    This is a comparison layer only. It does not count Elliott waves and it does
    not define trading signals.
    """

    specs = tuple(degree_specs or DEFAULT_SWING_DEGREES)
    group_columns = group_columns or ["example_id"]
    structural_frames = []
    discarded_frames = []
    summary_frames = []

    for spec in specs:
        result = build_structural_pivots_by_group(
            raw_pivots,
            config=spec.config,
            group_columns=group_columns,
        )
        structural_frames.append(_add_degree_columns(result["structural_pivots"], spec))
        discarded_frames.append(_add_degree_columns(result["discarded_minor_pivots"], spec))
        summary_frames.append(_add_degree_columns(result["structure_summary"], spec))

    structural = (
        pd.concat([frame for frame in structural_frames if not frame.empty], ignore_index=True)
        if structural_frames
        else pd.DataFrame()
    )
    discarded = (
        pd.concat([frame for frame in discarded_frames if not frame.empty], ignore_index=True)
        if discarded_frames
        else pd.DataFrame()
    )
    summary = (
        pd.concat([frame for frame in summary_frames if not frame.empty], ignore_index=True)
        if summary_frames
        else pd.DataFrame()
    )
    return {
        "swing_degrees_pivots": structural,
        "swing_degrees_discarded": discarded,
        "swing_degrees_summary": summary,
    }


def degree_count_table(
    summary: pd.DataFrame,
    *,
    value_column: str = "structural_pivots",
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    return summary.pivot_table(
        index="example_id",
        columns="swing_degree",
        values=value_column,
        aggfunc="sum",
        fill_value=0,
    )


def is_monotonic_by_degree(
    summary: pd.DataFrame,
    degree_order: tuple[str, ...] = ("minor", "intermediate", "major"),
) -> bool:
    counts = degree_count_table(summary)
    if counts.empty:
        return True
    for degree in degree_order:
        if degree not in counts.columns:
            counts[degree] = 0
    ordered = counts[list(degree_order)]
    for left, right in zip(degree_order, degree_order[1:]):
        if not (ordered[right] <= ordered[left]).all():
            return False
    return True
