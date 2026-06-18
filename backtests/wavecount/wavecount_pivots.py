"""Causal pivot detection primitives for WaveCount research artifacts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import numpy as np
import pandas as pd

from .wavecount_config import PivotConfig


PIVOT_STATES = (
    "no_pivot",
    "candidate_high",
    "candidate_low",
    "confirmed_high",
    "confirmed_low",
    "ambiguous_noise",
)


def _as_optional_iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _normalise_ohlc_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a clean DatetimeIndex OHLC frame or raise a contract error."""
    if frame is None or frame.empty:
        raise ValueError("frame must contain OHLC data")

    df = frame.copy()
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    required = ["open", "high", "low", "close"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"missing OHLC columns: {missing}")

    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=required)
    if df.empty:
        raise ValueError("frame has no valid OHLC rows after cleaning")
    return df


def compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute a causal ATR approximation from OHLC rows.

    The true range at row ``t`` uses only high/low/close values available at
    that row and the previous close. The rolling average is not centered.
    """

    if period < 1:
        raise ValueError("period must be >= 1")

    df = _normalise_ohlc_frame(frame)
    previous_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period, min_periods=1).mean()


def _empty_row(timestamp: pd.Timestamp, symbol: str, timeframe: str, config: PivotConfig) -> dict:
    """Build the default no-pivot row for one candle."""
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "timeframe": timeframe,
        "pivot_state": "no_pivot",
        "pivot_type": None,
        "pivot_extreme_time": pd.NaT,
        "pivot_detected_at": pd.NaT,
        "pivot_extreme_price": np.nan,
        "confirmation_lag_bars": config.confirmation_bars,
        "visibility_score": np.nan,
        "atr": np.nan,
        "lookahead_safe": True,
        "is_candidate": False,
        "is_confirmed": False,
        "is_ambiguous": False,
        "reason": "no visible pivot confirmed at this candle",
    }


def _set_pivot_row(rows: list[dict], detection_index: int, payload: dict) -> None:
    current_state = rows[detection_index]["pivot_state"]
    if current_state.startswith("confirmed_"):
        rows[detection_index].update(
            {
                "pivot_state": "ambiguous_noise",
                "pivot_type": "ambiguous",
                "pivot_extreme_time": pd.NaT,
                "pivot_detected_at": rows[detection_index]["timestamp"],
                "pivot_extreme_price": np.nan,
                "visibility_score": np.nan,
                "lookahead_safe": True,
                "is_candidate": False,
                "is_confirmed": False,
                "is_ambiguous": True,
                "reason": "multiple confirmed pivot candidates at the same detection candle",
            }
        )
        return
    rows[detection_index].update(payload)


def _visibility_score(
    df: pd.DataFrame,
    atr: pd.Series,
    extreme_index: int,
    detection_index: int,
    pivot_type: str,
    config: PivotConfig,
) -> tuple[float, bool, str]:
    window_start = max(0, extreme_index - config.left_bars)
    window = df.iloc[window_start : detection_index + 1]
    if window.empty:
        return 0.0, False, "empty visibility window"

    extreme_price = (
        float(df["high"].iloc[extreme_index])
        if pivot_type == "high"
        else float(df["low"].iloc[extreme_index])
    )
    opposite_price = (
        float(window["low"].min())
        if pivot_type == "high"
        else float(window["high"].max())
    )
    move = abs(extreme_price - opposite_price)
    atr_value = float(atr.iloc[detection_index]) if not pd.isna(atr.iloc[detection_index]) else 0.0
    close_value = abs(float(df["close"].iloc[detection_index]))
    atr_score = move / atr_value if atr_value > 0 else np.inf
    relative_score = move / close_value if close_value > 0 else 0.0

    atr_pass = atr_score >= config.min_atr_multiplier
    relative_pass = relative_score >= config.min_relative_move_pct
    visible = atr_pass or relative_pass
    reason = (
        f"visible move: atr_score={atr_score:.3f}, relative_score={relative_score:.5f}"
        if visible
        else f"move below visibility filters: atr_score={atr_score:.3f}, relative_score={relative_score:.5f}"
    )
    return float(max(atr_score if np.isfinite(atr_score) else 0.0, relative_score)), visible, reason


def _mark_candidate_states(
    df: pd.DataFrame,
    atr: pd.Series,
    rows: list[dict],
    config: PivotConfig,
) -> None:
    for row_index in range(config.left_bars, len(df)):
        if rows[row_index]["pivot_state"] != "no_pivot":
            continue

        lookback = max(config.left_bars, config.candidate_lookback_bars)
        start = max(0, row_index - lookback)
        recent = df.iloc[start : row_index + 1]
        if len(recent) < config.left_bars + 1:
            continue

        high_is_candidate = df["high"].iloc[row_index] >= recent["high"].max()
        low_is_candidate = df["low"].iloc[row_index] <= recent["low"].min()
        if not high_is_candidate and not low_is_candidate:
            continue

        local_range = float(recent["high"].max() - recent["low"].min())
        atr_value = float(atr.iloc[row_index]) if not pd.isna(atr.iloc[row_index]) else 0.0
        relative_range = local_range / abs(float(df["close"].iloc[row_index])) if df["close"].iloc[row_index] else 0.0
        visible = (
            (atr_value > 0 and local_range / atr_value >= config.min_atr_multiplier)
            or relative_range >= config.min_relative_move_pct
        )

        if high_is_candidate and low_is_candidate:
            state = "ambiguous_noise"
            pivot_type = "ambiguous"
            is_ambiguous = True
            reason = "current candle is both local high and local low candidate"
        elif not visible:
            state = "ambiguous_noise"
            pivot_type = "ambiguous"
            is_ambiguous = True
            reason = "candidate extreme below visibility filters"
        elif high_is_candidate:
            state = "candidate_high"
            pivot_type = "high"
            is_ambiguous = False
            reason = "potential local high, waiting for confirmation latency"
        else:
            state = "candidate_low"
            pivot_type = "low"
            is_ambiguous = False
            reason = "potential local low, waiting for confirmation latency"

        rows[row_index].update(
            {
                "pivot_state": state,
                "pivot_type": pivot_type,
                "pivot_extreme_time": df.index[row_index] if not is_ambiguous else pd.NaT,
                "pivot_detected_at": df.index[row_index],
                "pivot_extreme_price": (
                    float(df["high"].iloc[row_index])
                    if pivot_type == "high"
                    else float(df["low"].iloc[row_index])
                    if pivot_type == "low"
                    else np.nan
                ),
                "visibility_score": local_range / atr_value if atr_value > 0 else np.nan,
                "atr": atr_value,
                "is_candidate": not is_ambiguous,
                "is_confirmed": False,
                "is_ambiguous": is_ambiguous,
                "reason": reason,
            }
        )


def detect_causal_pivots(
    frame: pd.DataFrame,
    config: PivotConfig | None = None,
    *,
    symbol: str = "",
    timeframe: str = "",
) -> pd.DataFrame:
    """Detect causal WaveCount Phase 1 pivot states.

    Confirmed pivots are emitted at ``pivot_detected_at`` after the configured
    latency. The actual extreme candle remains available as
    ``pivot_extreme_time`` for charts and audit, but consumers must not treat it
    as a real-time event.
    """

    config = config or PivotConfig()
    df = _normalise_ohlc_frame(frame)
    atr = compute_atr(df, period=config.atr_period)

    rows = [_empty_row(pd.Timestamp(timestamp), symbol, timeframe, config) for timestamp in df.index]
    for row, atr_value in zip(rows, atr):
        row["atr"] = float(atr_value) if not pd.isna(atr_value) else np.nan

    last_confirmed_extreme_index: int | None = None
    max_extreme_index = len(df) - config.confirmation_bars
    for extreme_index in range(config.left_bars, max_extreme_index):
        detection_index = extreme_index + config.confirmation_bars
        window_start = extreme_index - config.left_bars
        window = df.iloc[window_start : detection_index + 1]
        high_value = float(df["high"].iloc[extreme_index])
        low_value = float(df["low"].iloc[extreme_index])

        high_values = window["high"].to_numpy(dtype=float)
        low_values = window["low"].to_numpy(dtype=float)
        center = config.left_bars
        is_high = (
            np.isclose(high_values[center], np.nanmax(high_values))
            and np.isclose(high_values, high_values[center]).sum() == 1
        )
        is_low = (
            np.isclose(low_values[center], np.nanmin(low_values))
            and np.isclose(low_values, low_values[center]).sum() == 1
        )

        if is_high and is_low:
            _set_pivot_row(
                rows,
                detection_index,
                {
                    "pivot_state": "ambiguous_noise",
                    "pivot_type": "ambiguous",
                    "pivot_extreme_time": pd.NaT,
                    "pivot_detected_at": df.index[detection_index],
                    "pivot_extreme_price": np.nan,
                    "visibility_score": np.nan,
                    "atr": float(atr.iloc[detection_index]),
                    "lookahead_safe": True,
                    "is_candidate": False,
                    "is_confirmed": False,
                    "is_ambiguous": True,
                    "reason": "same candle qualifies as high and low pivot",
                },
            )
            continue

        pivot_type = "high" if is_high else "low" if is_low else None
        if pivot_type is None:
            continue

        if (
            last_confirmed_extreme_index is not None
            and extreme_index - last_confirmed_extreme_index < config.min_bars_between_pivots
        ):
            _set_pivot_row(
                rows,
                detection_index,
                {
                    "pivot_state": "ambiguous_noise",
                    "pivot_type": "ambiguous",
                    "pivot_extreme_time": pd.NaT,
                    "pivot_detected_at": df.index[detection_index],
                    "pivot_extreme_price": np.nan,
                    "visibility_score": np.nan,
                    "atr": float(atr.iloc[detection_index]),
                    "lookahead_safe": True,
                    "is_candidate": False,
                    "is_confirmed": False,
                    "is_ambiguous": True,
                    "reason": "pivot too close to previous confirmed pivot",
                },
            )
            continue

        visibility, visible, visibility_reason = _visibility_score(
            df, atr, extreme_index, detection_index, pivot_type, config
        )
        if not visible:
            _set_pivot_row(
                rows,
                detection_index,
                {
                    "pivot_state": "ambiguous_noise",
                    "pivot_type": "ambiguous",
                    "pivot_extreme_time": pd.NaT,
                    "pivot_detected_at": df.index[detection_index],
                    "pivot_extreme_price": np.nan,
                    "visibility_score": visibility,
                    "atr": float(atr.iloc[detection_index]),
                    "lookahead_safe": True,
                    "is_candidate": False,
                    "is_confirmed": False,
                    "is_ambiguous": True,
                    "reason": visibility_reason,
                },
            )
            continue

        _set_pivot_row(
            rows,
            detection_index,
            {
                "pivot_state": f"confirmed_{pivot_type}",
                "pivot_type": pivot_type,
                "pivot_extreme_time": df.index[extreme_index],
                "pivot_detected_at": df.index[detection_index],
                "pivot_extreme_price": high_value if pivot_type == "high" else low_value,
                "visibility_score": visibility,
                "atr": float(atr.iloc[detection_index]),
                "lookahead_safe": True,
                "is_candidate": False,
                "is_confirmed": True,
                "is_ambiguous": False,
                "reason": visibility_reason,
            },
        )
        last_confirmed_extreme_index = extreme_index

    _mark_candidate_states(df, atr, rows, config)
    result = pd.DataFrame(rows).set_index("timestamp", drop=False)
    result["pivot_extreme_time"] = pd.to_datetime(result["pivot_extreme_time"], errors="coerce")
    result["pivot_detected_at"] = pd.to_datetime(result["pivot_detected_at"], errors="coerce")
    return result


def extract_pivot_events(pivot_frame: pd.DataFrame, states: Iterable[str] | None = None) -> pd.DataFrame:
    """Return rows that carry a pivot/candidate/ambiguous state."""

    wanted = set(states or [state for state in PIVOT_STATES if state != "no_pivot"])
    events = pivot_frame[pivot_frame["pivot_state"].isin(wanted)].copy()
    if events.empty:
        return events
    events["pivot_extreme_time_iso"] = events["pivot_extreme_time"].map(_as_optional_iso)
    events["pivot_detected_at_iso"] = events["pivot_detected_at"].map(_as_optional_iso)
    return events


def config_to_dict(config: PivotConfig) -> dict:
    return asdict(config)
