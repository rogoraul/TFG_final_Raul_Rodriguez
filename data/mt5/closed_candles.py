from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping

import pandas as pd


TIMEFRAME_MINUTES_BY_NAME = {
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


def _normalise_time(value: Any) -> pd.Timestamp:
    """Return a timezone-naive pandas timestamp for candle-open comparisons."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        return timestamp.tz_localize(None)
    return timestamp


def _normalise_server_time(value: Any) -> pd.Timestamp:
    """Convert an MT5 tick timestamp or datetime-like value into a timestamp."""
    if isinstance(value, (int, float)):
        return pd.to_datetime(value, unit="s")
    return _normalise_time(value)


def resolve_timeframe_minutes(timeframe: Any, timeframe_minutes_map: Mapping | None = None) -> int | None:
    """Resolve an MT5 timeframe constant or label to minutes, if known."""
    if timeframe_minutes_map and timeframe in timeframe_minutes_map:
        return int(timeframe_minutes_map[timeframe])
    key = str(timeframe or "").upper()
    return TIMEFRAME_MINUTES_BY_NAME.get(key)


def remove_open_candles_with_server_time(
    df,
    timeframe,
    server_time,
    *,
    symbol: str = "",
    timeframe_label: str | None = None,
    timeframe_minutes_map: Mapping | None = None,
    verbose: bool = True,
):
    """Return only candles closed according to MT5 server time.

    Args:
        df: DataFrame with at least a ``time`` candle-open column.
        timeframe: MT5 timeframe constant or canonical label.
        server_time: Current MT5 server time, either as epoch seconds or a
            datetime-like value.

    Returns:
        The original frame when the last candle is closed, or a frame without
        the last row when that candle is still open.
    """
    if df is None or len(df) == 0:
        return df
    if "time" not in df.columns:
        raise ValueError("DataFrame must include a 'time' column.")

    period_minutes = resolve_timeframe_minutes(timeframe, timeframe_minutes_map)
    label = timeframe_label or str(timeframe)
    if period_minutes is None:
        if verbose:
            print(f"[!] Timeframe {label} no reconocido, no se filtrara ultima vela")
        return df

    last_candle_time = _normalise_time(df.iloc[-1]["time"])
    candle_close_time = last_candle_time + timedelta(minutes=int(period_minutes))
    server_timestamp = _normalise_server_time(server_time)

    if server_timestamp < candle_close_time:
        if verbose:
            symbol_text = f"{symbol}-" if symbol else ""
            print(
                f"[FILTER] Vela abierta detectada en {symbol_text}{label}: "
                f"{last_candle_time.strftime('%Y-%m-%d %H:%M')} "
                f"(cierra {candle_close_time.strftime('%H:%M')}, "
                f"servidor {server_timestamp.strftime('%H:%M')}). Eliminando..."
            )
        return df.iloc[:-1]
    return df
