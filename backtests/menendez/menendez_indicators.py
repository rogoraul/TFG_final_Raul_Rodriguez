"""Indicator engine for the Menendez/Elliott experimental pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtests.menendez.menendez_config import get_indicator_config


def _ema(series, span):
    return pd.Series(series, copy=False).ewm(span=int(span), adjust=False).mean()


def _sma(series, length):
    return pd.Series(series, copy=False).rolling(int(length), min_periods=int(length)).mean()


def _rolling_std(series, length):
    return pd.Series(series, copy=False).rolling(int(length), min_periods=int(length)).std(ddof=0)


def _safe_slope(series):
    return pd.Series(series, copy=False).diff()


def _cross_up(fast, slow):
    fast = pd.Series(fast, copy=False)
    slow = pd.Series(slow, copy=False)
    return ((fast > slow) & (fast.shift(1) <= slow.shift(1))).fillna(False)


def _cross_down(fast, slow):
    fast = pd.Series(fast, copy=False)
    slow = pd.Series(slow, copy=False)
    return ((fast < slow) & (fast.shift(1) >= slow.shift(1))).fillna(False)


def _calculate_psar(high, low, close, step=0.02, max_step=0.2):
    """Calculate a causal Parabolic SAR series and flip flags."""
    high = pd.to_numeric(high, errors="coerce").to_numpy(dtype=float, copy=False)
    low = pd.to_numeric(low, errors="coerce").to_numpy(dtype=float, copy=False)
    close = pd.to_numeric(close, errors="coerce").to_numpy(dtype=float, copy=False)

    size = len(high)
    psar = np.full(size, np.nan, dtype=float)
    polarity = np.zeros(size, dtype=int)
    flip_long = np.zeros(size, dtype=bool)
    flip_short = np.zeros(size, dtype=bool)

    if size == 0:
        return psar, polarity, flip_long, flip_short
    if size == 1:
        psar[0] = low[0]
        polarity[0] = 1
        return psar, polarity, flip_long, flip_short

    bull = bool(close[1] >= close[0])
    psar[0] = low[0] if bull else high[0]
    ep = max(high[0], high[1]) if bull else min(low[0], low[1])
    af = float(step)
    polarity[0] = 1 if bull else -1

    for idx in range(1, size):
        prev_psar = psar[idx - 1]

        if bull:
            current_psar = prev_psar + af * (ep - prev_psar)
            if idx >= 2:
                current_psar = min(current_psar, low[idx - 1], low[idx - 2])
            else:
                current_psar = min(current_psar, low[idx - 1])

            if low[idx] < current_psar:
                bull = False
                current_psar = ep
                ep = low[idx]
                af = float(step)
                flip_short[idx] = True
            else:
                if high[idx] > ep:
                    ep = high[idx]
                    af = min(af + float(step), float(max_step))
        else:
            current_psar = prev_psar + af * (ep - prev_psar)
            if idx >= 2:
                current_psar = max(current_psar, high[idx - 1], high[idx - 2])
            else:
                current_psar = max(current_psar, high[idx - 1])

            if high[idx] > current_psar:
                bull = True
                current_psar = ep
                ep = high[idx]
                af = float(step)
                flip_long[idx] = True
            else:
                if low[idx] < ep:
                    ep = low[idx]
                    af = min(af + float(step), float(max_step))

        psar[idx] = current_psar
        polarity[idx] = 1 if bull else -1

    return psar, polarity, flip_long, flip_short


def _session_pivots(df, rule, prefix):
    """Calculate previous-session pivot levels and forward-fill them intraday."""
    ohlc = df.resample(rule).agg({
        "high": "max",
        "low": "min",
        "close": "last",
    })
    ohlc = ohlc.dropna(how="any")
    if ohlc.empty:
        return pd.DataFrame(index=df.index)

    piv = pd.DataFrame(index=ohlc.index)
    piv[f"{prefix}_PIVOT"] = (ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3.0
    piv[f"{prefix}_R1"] = (2.0 * piv[f"{prefix}_PIVOT"]) - ohlc["low"]
    piv[f"{prefix}_S1"] = (2.0 * piv[f"{prefix}_PIVOT"]) - ohlc["high"]
    piv[f"{prefix}_R2"] = piv[f"{prefix}_PIVOT"] + (ohlc["high"] - ohlc["low"])
    piv[f"{prefix}_S2"] = piv[f"{prefix}_PIVOT"] - (ohlc["high"] - ohlc["low"])
    piv = piv.shift(1)
    return piv.reindex(df.index, method="ffill")


class MenendezIndicatorEngine:
    """Build all indicators required by the Menendez strategy formalization."""

    def __init__(self, **overrides):
        """Load indicator config and apply optional parameter overrides."""
        config = get_indicator_config(overrides)
        self.psar_step = float(config["psar_step"])
        self.psar_max_step = float(config["psar_max_step"])
        self.sma_periods = tuple(int(period) for period in config["sma_periods"])
        self.macd_fast = int(config["macd_fast"])
        self.macd_slow = int(config["macd_slow"])
        self.macd_signal = int(config["macd_signal"])
        self.stoch_k = int(config["stoch_k"])
        self.stoch_d = int(config["stoch_d"])
        self.stoch_smooth = int(config["stoch_smooth"])
        self.bb_length = int(config["bb_length"])
        self.bb_std = float(config["bb_std"])

    def aplicar_todo(self, df_original):
        """Return a copy of OHLC data enriched with Menendez indicators."""
        df = df_original.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("El DataFrame debe usar DatetimeIndex para Menendez.")

        psar, polarity, flip_long, flip_short = _calculate_psar(
            df["high"],
            df["low"],
            df["close"],
            step=self.psar_step,
            max_step=self.psar_max_step,
        )
        df["PSAR"] = psar
        df["PSAR_POLARITY"] = polarity
        df["PSAR_FLIP_LONG"] = flip_long
        df["PSAR_FLIP_SHORT"] = flip_short

        for period in self.sma_periods:
            df[f"SMA_{period}"] = _sma(df["close"], period)

        if "SMA_200" not in df.columns:
            df["SMA_200"] = _sma(df["close"], 200)

        df["SMA_21_SLOPE"] = _safe_slope(df["SMA_21"])
        df["BULLISH_FAN"] = (
            (df["close"] > df["SMA_5"]) &
            (df["SMA_5"] > df["SMA_8"]) &
            (df["SMA_8"] > df["SMA_13"]) &
            (df["SMA_13"] > df["SMA_21"]) &
            (df["SMA_21_SLOPE"] > 0)
        ).fillna(False)
        df["BEARISH_FAN"] = (
            (df["close"] < df["SMA_5"]) &
            (df["SMA_5"] < df["SMA_8"]) &
            (df["SMA_8"] < df["SMA_13"]) &
            (df["SMA_13"] < df["SMA_21"]) &
            (df["SMA_21_SLOPE"] < 0)
        ).fillna(False)
        df["SMA_5_8_CROSS_UP"] = _cross_up(df["SMA_5"], df["SMA_8"])
        df["SMA_5_8_CROSS_DOWN"] = _cross_down(df["SMA_5"], df["SMA_8"])
        df["SMA_8_13_CROSS_UP"] = _cross_up(df["SMA_8"], df["SMA_13"])
        df["SMA_8_13_CROSS_DOWN"] = _cross_down(df["SMA_8"], df["SMA_13"])
        df["SMA_13_21_CROSS_UP"] = _cross_up(df["SMA_13"], df["SMA_21"])
        df["SMA_13_21_CROSS_DOWN"] = _cross_down(df["SMA_13"], df["SMA_21"])
        df["SMA_50_200_CROSS_UP"] = _cross_up(df["SMA_50"], df["SMA_200"])
        df["SMA_50_200_CROSS_DOWN"] = _cross_down(df["SMA_50"], df["SMA_200"])

        ema_fast = _ema(df["close"], self.macd_fast)
        ema_slow = _ema(df["close"], self.macd_slow)
        df["MACD_LINE"] = ema_fast - ema_slow
        df["MACD_SIGNAL"] = _ema(df["MACD_LINE"], self.macd_signal)
        df["MACD_HIST"] = df["MACD_LINE"] - df["MACD_SIGNAL"]

        lowest_low = pd.to_numeric(df["low"], errors="coerce").rolling(
            self.stoch_k,
            min_periods=self.stoch_k,
        ).min()
        highest_high = pd.to_numeric(df["high"], errors="coerce").rolling(
            self.stoch_k,
            min_periods=self.stoch_k,
        ).max()
        range_hl = (highest_high - lowest_low).replace(0.0, np.nan)
        raw_k = 100.0 * ((df["close"] - lowest_low) / range_hl)
        slow_k = raw_k.rolling(self.stoch_smooth, min_periods=self.stoch_smooth).mean()
        slow_d = slow_k.rolling(self.stoch_d, min_periods=self.stoch_d).mean()
        df["STOCH_K"] = slow_k
        df["STOCH_D"] = slow_d
        df["STOCH_CROSS_UP"] = (
            (df["STOCH_K"] > df["STOCH_D"]) &
            (df["STOCH_K"].shift(1) <= df["STOCH_D"].shift(1))
        ).fillna(False)
        df["STOCH_CROSS_DOWN"] = (
            (df["STOCH_K"] < df["STOCH_D"]) &
            (df["STOCH_K"].shift(1) >= df["STOCH_D"].shift(1))
        ).fillna(False)

        df["BB_MID"] = _sma(df["close"], self.bb_length)
        bb_std = _rolling_std(df["close"], self.bb_length) * self.bb_std
        df["BB_UPPER"] = df["BB_MID"] + bb_std
        df["BB_LOWER"] = df["BB_MID"] - bb_std

        daily_pivots = _session_pivots(df, "1D", "D")
        weekly_pivots = _session_pivots(df, "W-FRI", "W")
        for pivots in (daily_pivots, weekly_pivots):
            for column_name in pivots.columns:
                df[column_name] = pivots[column_name]

        return df
