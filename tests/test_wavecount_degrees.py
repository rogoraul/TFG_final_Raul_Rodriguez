import unittest

import pandas as pd

from backtests.wavecount import build_swing_degrees, is_monotonic_by_degree


def _raw_pivots():
    rows = []
    pattern = [
        ("low", 100.0, 0, 2, 1.0),
        ("high", 104.0, 4, 6, 1.0),
        ("low", 101.0, 8, 10, 1.0),
        ("high", 111.0, 16, 18, 1.0),
        ("low", 104.0, 24, 26, 1.0),
        ("high", 119.0, 36, 38, 1.0),
        ("low", 108.0, 48, 50, 1.0),
    ]
    for idx, (pivot_type, price, extreme_hour, detected_hour, atr) in enumerate(pattern, start=1):
        rows.append(
            {
                "example_id": "synthetic",
                "group": "Test",
                "symbol": "TEST",
                "timeframe": "H1",
                "example_type": "unit",
                "timestamp": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=detected_hour),
                "pivot_state": f"confirmed_{pivot_type}",
                "pivot_type": pivot_type,
                "pivot_extreme_time": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=extreme_hour),
                "pivot_detected_at": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=detected_hour),
                "pivot_extreme_price": price,
                "confirmation_lag_bars": 2,
                "visibility_score": 4.0,
                "atr": atr,
                "lookahead_safe": True,
                "is_candidate": False,
                "is_confirmed": True,
                "is_ambiguous": False,
                "reason": f"synthetic {idx}",
            }
        )
    return pd.DataFrame(rows)


class TestWaveCountDegrees(unittest.TestCase):
    def test_generates_minor_intermediate_and_major_degrees(self):
        result = build_swing_degrees(_raw_pivots())
        pivots = result["swing_degrees_pivots"]

        self.assertEqual(set(pivots["swing_degree"]), {"minor", "intermediate", "major"})
        self.assertIn("degree_min_leg_atr_multiplier", pivots.columns)

    def test_degree_counts_are_monotonic(self):
        result = build_swing_degrees(_raw_pivots())
        summary = result["swing_degrees_summary"]

        self.assertTrue(is_monotonic_by_degree(summary))
        counts = summary.set_index("swing_degree")["structural_pivots"].to_dict()
        self.assertGreaterEqual(counts["minor"], counts["intermediate"])
        self.assertGreaterEqual(counts["intermediate"], counts["major"])

    def test_structural_detected_at_is_never_before_raw_detection_for_all_degrees(self):
        result = build_swing_degrees(_raw_pivots())
        pivots = result["swing_degrees_pivots"]

        self.assertTrue((pivots["structural_detected_at"] >= pivots["pivot_detected_at"]).all())


if __name__ == "__main__":
    unittest.main()
