from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class CompressedTimeAxis:
    """Map real timestamps to consecutive candle positions for visual review.

    The real timestamps stay in the data tables. This helper only changes the
    plotted x coordinate so weekends and market closures do not create visual
    gaps between consecutive candles.
    """

    timestamps: tuple[pd.Timestamp, ...]
    x_values: tuple[float, ...]
    time_to_x: dict[pd.Timestamp, float]

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "CompressedTimeAxis":
        timestamps = tuple(pd.to_datetime(frame.index, errors="coerce"))
        x_values = tuple(float(index) for index in range(len(timestamps)))
        time_to_x = {timestamp: x_value for timestamp, x_value in zip(timestamps, x_values) if not pd.isna(timestamp)}
        return cls(timestamps=timestamps, x_values=x_values, time_to_x=time_to_x)

    def to_x(self, timestamp: object) -> float | None:
        parsed = pd.to_datetime(timestamp, errors="coerce")
        if pd.isna(parsed):
            return None
        return self.time_to_x.get(pd.Timestamp(parsed))

    def to_x_series(self, timestamps: Iterable[object]) -> pd.Series:
        index = getattr(timestamps, "index", None)
        return pd.Series([self.to_x(timestamp) for timestamp in timestamps], index=index, dtype="float64")

    def format_axis(self, ax, *, max_ticks: int = 8, label_format: str = "%Y-%m-%d\n%H:%M") -> None:
        if not self.timestamps:
            return
        if len(self.timestamps) <= max_ticks:
            tick_positions = list(range(len(self.timestamps)))
        else:
            tick_positions = sorted({int(round(value)) for value in np.linspace(0, len(self.timestamps) - 1, max_ticks)})
        labels = [self.timestamps[position].strftime(label_format) for position in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(labels)
        ax.set_xlim(-0.5, len(self.timestamps) - 0.5)


def build_compressed_time_axis(frame: pd.DataFrame) -> CompressedTimeAxis:
    return CompressedTimeAxis.from_frame(frame)


def compressed_candle_width() -> float:
    return 0.62
