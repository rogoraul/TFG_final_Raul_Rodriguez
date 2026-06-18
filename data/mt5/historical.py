"""Historical MT5 candle downloader built on top of `get_data_mt5`."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from data.mt5.func_utils import get_data_mt5


def get_all_available_data(symbol: str, timeframe: int, days_per_chunk: int = 30) -> pd.DataFrame | None:
    """Download all available MT5 history by walking backwards in chunks.

    Args:
        symbol: MT5 symbol name.
        timeframe: MT5 timeframe constant.
        days_per_chunk: Number of days requested per MT5 call.

    Returns:
        Deduplicated, time-sorted DataFrame, or None when no candles are found.
    """
    date_to = datetime.now() + timedelta(days=1)
    all_data = []
    last_min_time = None

    while True:
        date_from = date_to - timedelta(days=days_per_chunk)
        df = get_data_mt5(symbol, timeframe, date_from, date_to)

        if df is None or df.empty:
            break

        min_time = df['time'].min()
        if last_min_time is not None and min_time == last_min_time:
            break
        last_min_time = min_time

        all_data.append(df)
        date_to = min_time - timedelta(seconds=1)
        if date_from.year < 2000:
            break

    if not all_data:
        return None

    return pd.concat(all_data).drop_duplicates("time").sort_values("time").reset_index(drop=True)
