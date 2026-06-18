import unittest

import pandas as pd

from backtests.wavecount.wavecount_plotting import build_compressed_time_axis, compressed_candle_width


def _frame(index):
    return pd.DataFrame(
        {
            "open": [1.0 + i for i in range(len(index))],
            "high": [1.1 + i for i in range(len(index))],
            "low": [0.9 + i for i in range(len(index))],
            "close": [1.05 + i for i in range(len(index))],
        },
        index=pd.to_datetime(index),
    )


class TestWaveCountPlotting(unittest.TestCase):
    def test_maps_market_timestamps_to_consecutive_candle_indexes(self):
        frame = _frame(["2026-03-06 21:00", "2026-03-09 00:00", "2026-03-09 01:00"])

        axis = build_compressed_time_axis(frame)

        self.assertEqual(axis.to_x(pd.Timestamp("2026-03-06 21:00")), 0.0)
        self.assertEqual(axis.to_x(pd.Timestamp("2026-03-09 00:00")), 1.0)
        self.assertEqual(axis.to_x(pd.Timestamp("2026-03-09 01:00")), 2.0)

    def test_missing_timestamp_is_not_mapped_to_nearest_candle(self):
        frame = _frame(["2026-03-06 21:00", "2026-03-09 00:00"])

        axis = build_compressed_time_axis(frame)

        self.assertIsNone(axis.to_x(pd.Timestamp("2026-03-08 12:00")))

    def test_series_alignment_preserves_exact_candle_positions(self):
        frame = _frame(["2026-03-06 21:00", "2026-03-09 00:00", "2026-03-09 01:00"])
        axis = build_compressed_time_axis(frame)

        x_values = axis.to_x_series(pd.to_datetime(["2026-03-09 00:00", "2026-03-08 12:00", "2026-03-09 01:00"]))

        self.assertEqual(float(x_values.iloc[0]), 1.0)
        self.assertTrue(pd.isna(x_values.iloc[1]))
        self.assertEqual(float(x_values.iloc[2]), 2.0)

    def test_series_alignment_preserves_source_index(self):
        frame = _frame(["2026-03-06 21:00", "2026-03-09 00:00"])
        axis = build_compressed_time_axis(frame)
        timestamps = pd.Series(pd.to_datetime(["2026-03-06 21:00", "2026-03-09 00:00"]), index=[10, 11])

        x_values = axis.to_x_series(timestamps)

        self.assertEqual(list(x_values.index), [10, 11])
        self.assertEqual(float(x_values.loc[10]), 0.0)
        self.assertEqual(float(x_values.loc[11]), 1.0)

    def test_price_and_indicator_overlays_share_the_same_candle_axis(self):
        frame = _frame(["2026-03-06 21:00", "2026-03-09 00:00", "2026-03-09 01:00"])
        axis = build_compressed_time_axis(frame)
        pivot_time = pd.Timestamp("2026-03-09 00:00")
        context = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-03-06 21:00", "2026-03-09 00:00", "2026-03-09 01:00"]),
                "ema_50": [1.0, 1.5, 2.0],
                "ewo_5_35": [0.0, 0.2, -0.1],
            },
            index=[100, 101, 102],
        )

        indicator_x = axis.to_x_series(context["timestamp"])

        self.assertEqual(axis.to_x(pivot_time), float(indicator_x.loc[101]))
        self.assertEqual(list(indicator_x), [0.0, 1.0, 2.0])

    def test_uses_stable_compressed_candle_width(self):
        self.assertGreater(compressed_candle_width(), 0.0)
        self.assertLess(compressed_candle_width(), 1.0)


if __name__ == "__main__":
    unittest.main()
