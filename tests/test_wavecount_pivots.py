import unittest

import pandas as pd

from backtests.wavecount import PivotConfig, detect_causal_pivots


def _ohlc_frame(highs, lows=None, closes=None):
    index = pd.date_range("2026-01-01", periods=len(highs), freq="h")
    lows = lows if lows is not None else [value - 1.0 for value in highs]
    closes = closes if closes is not None else [(high + low) / 2 for high, low in zip(highs, lows)]
    opens = closes
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        },
        index=index,
    )


class TestWaveCountPivots(unittest.TestCase):
    def test_confirmed_high_appears_only_after_latency(self):
        frame = _ohlc_frame(
            highs=[1.2, 2.2, 5.2, 3.2, 2.2, 1.2],
            lows=[0.8, 1.8, 4.2, 2.8, 1.8, 0.8],
        )
        config = PivotConfig(
            left_bars=1,
            confirmation_bars=2,
            atr_period=2,
            min_atr_multiplier=0.1,
            min_relative_move_pct=0.0,
            min_bars_between_pivots=1,
        )

        pivots = detect_causal_pivots(frame, config=config, symbol="TEST", timeframe="H1")
        confirmed_highs = pivots[pivots["pivot_state"] == "confirmed_high"]

        self.assertEqual(len(confirmed_highs), 1)
        event = confirmed_highs.iloc[0]
        self.assertEqual(event["pivot_extreme_time"], frame.index[2])
        self.assertEqual(event["pivot_detected_at"], frame.index[4])
        self.assertGreater(event["pivot_detected_at"], event["pivot_extreme_time"])

        before_detection = pivots.loc[: frame.index[3]]
        self.assertNotIn("confirmed_high", set(before_detection["pivot_state"]))

    def test_confirmed_low_appears_only_after_latency(self):
        frame = _ohlc_frame(
            highs=[5.2, 4.2, 2.2, 3.2, 4.2, 5.2],
            lows=[4.8, 3.8, 0.8, 2.8, 3.8, 4.8],
        )
        config = PivotConfig(
            left_bars=1,
            confirmation_bars=2,
            atr_period=2,
            min_atr_multiplier=0.1,
            min_relative_move_pct=0.0,
            min_bars_between_pivots=1,
        )

        pivots = detect_causal_pivots(frame, config=config)
        confirmed_lows = pivots[pivots["pivot_state"] == "confirmed_low"]

        self.assertEqual(len(confirmed_lows), 1)
        event = confirmed_lows.iloc[0]
        self.assertEqual(event["pivot_extreme_time"], frame.index[2])
        self.assertEqual(event["pivot_detected_at"], frame.index[4])
        self.assertGreater(event["pivot_detected_at"], event["pivot_extreme_time"])

        before_detection = pivots.loc[: frame.index[3]]
        self.assertNotIn("confirmed_low", set(before_detection["pivot_state"]))

    def test_detected_at_is_never_before_extreme_time_for_confirmed_pivots(self):
        frame = _ohlc_frame(
            highs=[1, 3, 2, 5, 3, 1, 2, 4, 2, 1],
            lows=[0, 1, 0.5, 3, 1.5, 0.2, 0.8, 2, 0.5, 0.1],
        )
        config = PivotConfig(
            left_bars=1,
            confirmation_bars=2,
            atr_period=2,
            min_atr_multiplier=0.1,
            min_relative_move_pct=0.0,
            min_bars_between_pivots=1,
        )

        pivots = detect_causal_pivots(frame, config=config)
        confirmed = pivots[pivots["is_confirmed"]]

        self.assertFalse(confirmed.empty)
        self.assertTrue((confirmed["pivot_detected_at"] >= confirmed["pivot_extreme_time"]).all())

    def test_flat_micro_range_is_ambiguous_not_confirmed(self):
        frame = _ohlc_frame(
            highs=[1.0001, 1.0001, 1.0001, 1.0001, 1.0001],
            lows=[1.0000, 1.0000, 1.0000, 1.0000, 1.0000],
            closes=[1.00005] * 5,
        )
        config = PivotConfig(
            left_bars=1,
            confirmation_bars=1,
            atr_period=2,
            min_atr_multiplier=10.0,
            min_relative_move_pct=0.5,
        )

        pivots = detect_causal_pivots(frame, config=config)

        self.assertNotIn("confirmed_high", set(pivots["pivot_state"]))
        self.assertNotIn("confirmed_low", set(pivots["pivot_state"]))
        self.assertIn("ambiguous_noise", set(pivots["pivot_state"]))

    def test_short_series_cannot_confirm_before_enough_future_bars_close(self):
        frame = _ohlc_frame(
            highs=[1.0, 4.0, 2.0],
            lows=[0.5, 3.5, 1.5],
        )
        config = PivotConfig(left_bars=1, confirmation_bars=3)

        pivots = detect_causal_pivots(frame, config=config)

        self.assertNotIn("confirmed_high", set(pivots["pivot_state"]))
        self.assertNotIn("confirmed_low", set(pivots["pivot_state"]))


if __name__ == "__main__":
    unittest.main()
