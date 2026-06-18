import unittest

import numpy as np
import pandas as pd

from backtests.menendez.menendez_indicators import MenendezIndicatorEngine


def _build_indicator_frame(periods=260, freq="30min"):
    index = pd.date_range("2025-01-01", periods=periods, freq=freq)
    base = np.linspace(1.0800, 1.1800, periods)
    swing = np.sin(np.linspace(0, 24, periods)) * 0.0025
    close = base + swing
    open_ = close + np.cos(np.linspace(0, 24, periods)) * 0.0004
    high = np.maximum(open_, close) + 0.0012
    low = np.minimum(open_, close) - 0.0012
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        },
        index=index,
    )


def _ema_reference(series, span):
    return pd.Series(series, copy=False).ewm(span=span, adjust=False).mean()


def _psar_reference(high, low, close, step=0.02, max_step=0.2):
    high = pd.Series(high, copy=False).astype(float).to_numpy()
    low = pd.Series(low, copy=False).astype(float).to_numpy()
    close = pd.Series(close, copy=False).astype(float).to_numpy()

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

    is_bull = bool(close[1] >= close[0])
    psar[0] = low[0] if is_bull else high[0]
    extreme_point = max(high[0], high[1]) if is_bull else min(low[0], low[1])
    accel = float(step)
    polarity[0] = 1 if is_bull else -1

    for i in range(1, size):
        candidate = psar[i - 1] + accel * (extreme_point - psar[i - 1])
        if is_bull:
            floor = low[i - 1] if i == 1 else min(low[i - 1], low[i - 2])
            candidate = min(candidate, floor)
            if low[i] < candidate:
                is_bull = False
                candidate = extreme_point
                extreme_point = low[i]
                accel = float(step)
                flip_short[i] = True
            else:
                if high[i] > extreme_point:
                    extreme_point = high[i]
                    accel = min(accel + float(step), float(max_step))
        else:
            ceiling = high[i - 1] if i == 1 else max(high[i - 1], high[i - 2])
            candidate = max(candidate, ceiling)
            if high[i] > candidate:
                is_bull = True
                candidate = extreme_point
                extreme_point = high[i]
                accel = float(step)
                flip_long[i] = True
            else:
                if low[i] < extreme_point:
                    extreme_point = low[i]
                    accel = min(accel + float(step), float(max_step))

        psar[i] = candidate
        polarity[i] = 1 if is_bull else -1

    return psar, polarity, flip_long, flip_short


class TestMenendezIndicatorsValidation(unittest.TestCase):
    def test_sma_and_slope_match_reference(self):
        df = _build_indicator_frame()
        result = MenendezIndicatorEngine().aplicar_todo(df)

        sma21 = df["close"].rolling(21, min_periods=21).mean()
        sma50 = df["close"].rolling(50, min_periods=50).mean()
        sma200 = df["close"].rolling(200, min_periods=200).mean()
        slope21 = sma21.diff()

        pd.testing.assert_series_equal(result["SMA_21"], sma21, check_names=False)
        pd.testing.assert_series_equal(result["SMA_50"], sma50, check_names=False)
        pd.testing.assert_series_equal(result["SMA_200"], sma200, check_names=False)
        pd.testing.assert_series_equal(result["SMA_21_SLOPE"], slope21, check_names=False)

    def test_macd_matches_reference_formula(self):
        df = _build_indicator_frame()
        result = MenendezIndicatorEngine().aplicar_todo(df)

        ema_fast = _ema_reference(df["close"], 12)
        ema_slow = _ema_reference(df["close"], 26)
        macd_line = ema_fast - ema_slow
        signal = _ema_reference(macd_line, 9)
        hist = macd_line - signal

        pd.testing.assert_series_equal(result["MACD_LINE"], macd_line, check_names=False)
        pd.testing.assert_series_equal(result["MACD_SIGNAL"], signal, check_names=False)
        pd.testing.assert_series_equal(result["MACD_HIST"], hist, check_names=False)

    def test_stochastic_matches_reference_formula(self):
        df = _build_indicator_frame()
        result = MenendezIndicatorEngine().aplicar_todo(df)

        lowest_low = df["low"].rolling(14, min_periods=14).min()
        highest_high = df["high"].rolling(14, min_periods=14).max()
        raw_k = 100.0 * ((df["close"] - lowest_low) / (highest_high - lowest_low).replace(0.0, np.nan))
        slow_k = raw_k.rolling(3, min_periods=3).mean()
        slow_d = slow_k.rolling(3, min_periods=3).mean()
        cross_up = ((slow_k > slow_d) & (slow_k.shift(1) <= slow_d.shift(1))).fillna(False)
        cross_down = ((slow_k < slow_d) & (slow_k.shift(1) >= slow_d.shift(1))).fillna(False)

        pd.testing.assert_series_equal(result["STOCH_K"], slow_k, check_names=False)
        pd.testing.assert_series_equal(result["STOCH_D"], slow_d, check_names=False)
        pd.testing.assert_series_equal(result["STOCH_CROSS_UP"], cross_up, check_names=False)
        pd.testing.assert_series_equal(result["STOCH_CROSS_DOWN"], cross_down, check_names=False)

    def test_bollinger_matches_reference_formula(self):
        df = _build_indicator_frame()
        result = MenendezIndicatorEngine().aplicar_todo(df)

        mid = df["close"].rolling(20, min_periods=20).mean()
        std = df["close"].rolling(20, min_periods=20).std(ddof=0)
        upper = mid + 2.0 * std
        lower = mid - 2.0 * std

        pd.testing.assert_series_equal(result["BB_MID"], mid, check_names=False)
        pd.testing.assert_series_equal(result["BB_UPPER"], upper, check_names=False)
        pd.testing.assert_series_equal(result["BB_LOWER"], lower, check_names=False)

    def test_daily_and_weekly_pivots_use_previous_completed_session(self):
        df = _build_indicator_frame(periods=24 * 14, freq="1H")
        result = MenendezIndicatorEngine().aplicar_todo(df)

        first_day = df.iloc[:24]
        expected_daily_pivot = (first_day["high"].max() + first_day["low"].min() + first_day["close"].iloc[-1]) / 3.0
        second_day_timestamp = df.index[24]
        self.assertAlmostEqual(result.loc[second_day_timestamp, "D_PIVOT"], expected_daily_pivot, places=12)

        first_week = df.loc[: "2025-01-03 23:00:00"]
        expected_weekly_pivot = (
            first_week["high"].max() +
            first_week["low"].min() +
            first_week["close"].iloc[-1]
        ) / 3.0
        next_week_timestamp = pd.Timestamp("2025-01-10 00:00:00")
        self.assertAlmostEqual(result.loc[next_week_timestamp, "W_PIVOT"], expected_weekly_pivot, places=12)

    def test_psar_matches_independent_reference(self):
        df = _build_indicator_frame(periods=120)
        result = MenendezIndicatorEngine().aplicar_todo(df)

        ref_psar, ref_polarity, ref_flip_long, ref_flip_short = _psar_reference(
            df["high"],
            df["low"],
            df["close"],
            step=0.02,
            max_step=0.2,
        )

        np.testing.assert_allclose(result["PSAR"].to_numpy(), ref_psar, equal_nan=True)
        np.testing.assert_array_equal(result["PSAR_POLARITY"].to_numpy(), ref_polarity)
        np.testing.assert_array_equal(result["PSAR_FLIP_LONG"].to_numpy(), ref_flip_long)
        np.testing.assert_array_equal(result["PSAR_FLIP_SHORT"].to_numpy(), ref_flip_short)

    def test_fan_flags_match_reference_ordering(self):
        df = _build_indicator_frame()
        result = MenendezIndicatorEngine().aplicar_todo(df)

        bullish = (
            (df["close"] > result["SMA_5"]) &
            (result["SMA_5"] > result["SMA_8"]) &
            (result["SMA_8"] > result["SMA_13"]) &
            (result["SMA_13"] > result["SMA_21"]) &
            (result["SMA_21_SLOPE"] > 0)
        ).fillna(False)
        bearish = (
            (df["close"] < result["SMA_5"]) &
            (result["SMA_5"] < result["SMA_8"]) &
            (result["SMA_8"] < result["SMA_13"]) &
            (result["SMA_13"] < result["SMA_21"]) &
            (result["SMA_21_SLOPE"] < 0)
        ).fillna(False)

        pd.testing.assert_series_equal(result["BULLISH_FAN"], bullish, check_names=False)
        pd.testing.assert_series_equal(result["BEARISH_FAN"], bearish, check_names=False)

    def test_moving_average_crosses_match_reference(self):
        df = _build_indicator_frame()
        result = MenendezIndicatorEngine().aplicar_todo(df)

        cross_5_8_up = ((result["SMA_5"] > result["SMA_8"]) & (result["SMA_5"].shift(1) <= result["SMA_8"].shift(1))).fillna(False)
        cross_5_8_down = ((result["SMA_5"] < result["SMA_8"]) & (result["SMA_5"].shift(1) >= result["SMA_8"].shift(1))).fillna(False)
        cross_8_13_up = ((result["SMA_8"] > result["SMA_13"]) & (result["SMA_8"].shift(1) <= result["SMA_13"].shift(1))).fillna(False)
        cross_8_13_down = ((result["SMA_8"] < result["SMA_13"]) & (result["SMA_8"].shift(1) >= result["SMA_13"].shift(1))).fillna(False)
        cross_13_21_up = ((result["SMA_13"] > result["SMA_21"]) & (result["SMA_13"].shift(1) <= result["SMA_21"].shift(1))).fillna(False)
        cross_13_21_down = ((result["SMA_13"] < result["SMA_21"]) & (result["SMA_13"].shift(1) >= result["SMA_21"].shift(1))).fillna(False)
        cross_50_200_up = ((result["SMA_50"] > result["SMA_200"]) & (result["SMA_50"].shift(1) <= result["SMA_200"].shift(1))).fillna(False)
        cross_50_200_down = ((result["SMA_50"] < result["SMA_200"]) & (result["SMA_50"].shift(1) >= result["SMA_200"].shift(1))).fillna(False)

        pd.testing.assert_series_equal(result["SMA_5_8_CROSS_UP"], cross_5_8_up, check_names=False)
        pd.testing.assert_series_equal(result["SMA_5_8_CROSS_DOWN"], cross_5_8_down, check_names=False)
        pd.testing.assert_series_equal(result["SMA_8_13_CROSS_UP"], cross_8_13_up, check_names=False)
        pd.testing.assert_series_equal(result["SMA_8_13_CROSS_DOWN"], cross_8_13_down, check_names=False)
        pd.testing.assert_series_equal(result["SMA_13_21_CROSS_UP"], cross_13_21_up, check_names=False)
        pd.testing.assert_series_equal(result["SMA_13_21_CROSS_DOWN"], cross_13_21_down, check_names=False)
        pd.testing.assert_series_equal(result["SMA_50_200_CROSS_UP"], cross_50_200_up, check_names=False)
        pd.testing.assert_series_equal(result["SMA_50_200_CROSS_DOWN"], cross_50_200_down, check_names=False)


if __name__ == "__main__":
    unittest.main()
