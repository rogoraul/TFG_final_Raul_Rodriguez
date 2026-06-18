from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PivotConfig:
    """Configuration for Phase 1 causal WaveCount pivots.

    The pivot is only emitted after ``confirmation_bars`` have closed. The
    extreme candle and the detection candle are therefore recorded separately.
    """

    left_bars: int = 3
    confirmation_bars: int = 3
    atr_period: int = 14
    min_atr_multiplier: float = 0.75
    min_relative_move_pct: float = 0.001
    min_bars_between_pivots: int = 2
    candidate_lookback_bars: int = 4

    def __post_init__(self) -> None:
        if self.left_bars < 1:
            raise ValueError("left_bars must be >= 1")
        if self.confirmation_bars < 1:
            raise ValueError("confirmation_bars must be >= 1")
        if self.atr_period < 1:
            raise ValueError("atr_period must be >= 1")
        if self.min_atr_multiplier < 0:
            raise ValueError("min_atr_multiplier must be >= 0")
        if self.min_relative_move_pct < 0:
            raise ValueError("min_relative_move_pct must be >= 0")
        if self.min_bars_between_pivots < 0:
            raise ValueError("min_bars_between_pivots must be >= 0")
        if self.candidate_lookback_bars < 1:
            raise ValueError("candidate_lookback_bars must be >= 1")
