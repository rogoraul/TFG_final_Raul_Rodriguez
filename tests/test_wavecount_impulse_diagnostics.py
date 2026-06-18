import unittest

import pandas as pd

from backtests.wavecount import build_impulse_diagnostics
from backtests.wavecount.wavecount_impulse_diagnostics import evaluate_impulse_window, evaluate_partial_123_window


def _pivots(items, *, degree="intermediate", example_id="synthetic"):
    rows = []
    for idx, (pivot_type, price, extreme_hour, detected_hour) in enumerate(items, start=1):
        rows.append(
            {
                "example_id": example_id,
                "group": "Test",
                "symbol": "TEST",
                "timeframe": "H1",
                "example_type": "unit",
                "raw_pivot_id": idx,
                "structure_state": "structural_pivot",
                "pivot_type": pivot_type,
                "pivot_extreme_time": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=extreme_hour),
                "pivot_detected_at": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=detected_hour),
                "pivot_extreme_price": price,
                "atr": 1.0,
                "structural_detected_at": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=detected_hour),
                "reason": "synthetic",
                "structural_pivot_id": idx,
                "previous_structural_pivot_id": idx - 1 if idx > 1 else None,
                "swing_degree": degree,
            }
        )
    return pd.DataFrame(rows)


class TestWaveCountImpulseDiagnostics(unittest.TestCase):
    def test_detects_strict_impulse_window(self):
        pivots = _pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
            ]
        )

        row = evaluate_impulse_window(pivots, window_id="strict")

        self.assertEqual(row["diagnostic_status"], "strict_candidate_impulse")
        self.assertEqual(row["direction"], "bullish")
        self.assertTrue(row["lookahead_safe"])

    def test_detects_soft_near_miss_for_wave_4_overlap(self):
        pivots = _pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 109.0, 40, 42),
                ("high", 136.0, 52, 54),
            ]
        )

        row = evaluate_impulse_window(pivots, window_id="near")

        self.assertEqual(row["diagnostic_status"], "soft_impulse_near_miss")
        self.assertTrue(row["possible_diagonal"])

    def test_detects_hard_invalid_impulse(self):
        pivots = _pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 99.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
            ]
        )

        row = evaluate_impulse_window(pivots, window_id="hard")

        self.assertEqual(row["diagnostic_status"], "hard_invalid_impulse")
        self.assertIn("wave 2 breaks wave 1 origin", row["hard_reasons"])

    def test_detects_partial_123_candidate(self):
        pivots = _pivots(
            [
                ("high", 120.0, 0, 2),
                ("low", 110.0, 8, 10),
                ("high", 116.0, 16, 18),
                ("low", 100.0, 28, 30),
            ]
        )

        row = evaluate_partial_123_window(pivots, window_id="partial")

        self.assertEqual(row["partial_status"], "partial_123_candidate")
        self.assertEqual(row["direction"], "bearish")

    def test_builds_degree_tables(self):
        pivots = pd.concat(
            [
                _pivots(
                    [
                        ("low", 100.0, 0, 2),
                        ("high", 110.0, 8, 10),
                        ("low", 104.0, 16, 18),
                        ("high", 125.0, 28, 30),
                        ("low", 115.0, 40, 42),
                        ("high", 136.0, 52, 54),
                    ],
                    degree="intermediate",
                ),
                _pivots(
                    [
                        ("low", 100.0, 0, 2),
                        ("high", 105.0, 8, 10),
                        ("low", 101.0, 16, 18),
                        ("high", 106.0, 28, 30),
                    ],
                    degree="minor",
                ),
            ],
            ignore_index=True,
        )

        result = build_impulse_diagnostics(pivots)

        self.assertFalse(result["impulse_diagnostics"].empty)
        self.assertFalse(result["partial_impulses"].empty)
        self.assertFalse(result["degree_impulse_comparison"].empty)


if __name__ == "__main__":
    unittest.main()
