import unittest

import pandas as pd

from backtests.wavecount.wavecount_context import (
    WaveContextConfig,
    align_htf_context,
    calculate_ewo_5_35,
    calculate_wave_context,
    classify_ema_alignment,
    classify_transition,
)


def _ohlc(values, *, start="2026-01-01", freq="h"):
    index = pd.date_range(start, periods=len(values), freq=freq)
    frame = pd.DataFrame(index=index)
    frame["open"] = values
    frame["high"] = [value + 0.5 for value in values]
    frame["low"] = [value - 0.5 for value in values]
    frame["close"] = values
    return frame


class TestWaveCountContext(unittest.TestCase):
    def test_classifies_ema_alignment(self):
        self.assertEqual(classify_ema_alignment(105.0, 100.0, 105.0), "bullish_alignment")
        self.assertEqual(classify_ema_alignment(95.0, 100.0, 100.0), "bearish_alignment")
        self.assertEqual(classify_ema_alignment(100.001, 100.0, 100.0, min_separation_pct=0.001), "mixed_or_unclear")

    def test_classifies_transition(self):
        self.assertEqual(classify_transition("bearish_alignment", "bullish_alignment"), "bullish_transition")
        self.assertEqual(classify_transition("bullish_alignment", "bearish_alignment"), "bearish_transition")
        self.assertEqual(classify_transition("bullish_alignment", "bullish_alignment"), "no_transition")

    def test_calculates_ema_context_columns(self):
        frame = _ohlc(list(range(1, 180)))

        context = calculate_wave_context(frame, symbol="TEST", timeframe="H1", example_id="example")

        self.assertIn("ema_50", context.columns)
        self.assertIn("ema_150", context.columns)
        self.assertIn("ewo_5_35", context.columns)
        self.assertIn("transition_state", context.columns)
        self.assertEqual(context.iloc[-1]["ema_alignment"], "bullish_alignment")

    def test_calculates_local_ewo_as_sma_mid_5_35(self):
        values = list(range(1, 50))
        frame = _ohlc(values)
        config = WaveContextConfig(ewo_method="sma_mid")

        ewo = calculate_ewo_5_35(frame, config)
        mid = (frame["high"] + frame["low"]) / 2.0
        expected = mid.rolling(5, min_periods=5).mean() - mid.rolling(35, min_periods=35).mean()

        self.assertAlmostEqual(ewo.iloc[-1], expected.iloc[-1])

    def test_aligns_htf_context_without_lookahead(self):
        ltf = calculate_wave_context(_ohlc([100 + i for i in range(12)], freq="30min"), timeframe="M30", example_id="example")
        htf = calculate_wave_context(_ohlc([100, 101, 102, 103], freq="h"), timeframe="H1", example_id="example")

        aligned = align_htf_context(ltf, htf, htf_timeframe="H1")
        row_after_first_htf_close = aligned[pd.to_datetime(aligned["timestamp"]) == pd.Timestamp("2026-01-01 01:30:00")].iloc[0]

        self.assertEqual(pd.Timestamp(row_after_first_htf_close["htf_context_source_time"]), pd.Timestamp("2026-01-01 00:00:00"))
        self.assertTrue(aligned["htf_lookahead_safe"].all())


if __name__ == "__main__":
    unittest.main()
