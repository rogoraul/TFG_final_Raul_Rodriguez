import unittest

import pandas as pd

from backtests.wavecount.wavecount_wave5_endpoint import (
    Wave5EndpointConfig,
    diagnose_candidate_row,
    diagnose_wave5_endpoint,
)


def _structural_pivots(items, *, example_id="synthetic", degree="intermediate"):
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
                "reason": "synthetic structural pivot",
                "leg_move_abs": None,
                "leg_move_pct": None,
                "leg_move_atr": None,
                "bars_from_previous": None,
                "replacement_of_raw_pivot_id": None,
                "structural_pivot_id": idx,
                "previous_structural_pivot_id": idx - 1 if idx > 1 else None,
                "swing_degree": degree,
                "degree_min_leg_atr_multiplier": 3.0,
                "degree_min_leg_relative_move_pct": 0.003,
                "degree_min_leg_bars": 6,
            }
        )
    return pd.DataFrame(rows)


class TestWaveCountWave5Endpoint(unittest.TestCase):
    def test_clean_wave5_endpoint_remains_provisional_candidate(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
                ("low", 128.0, 60, 62),
                ("high", 134.0, 70, 72),
            ]
        )

        result = diagnose_wave5_endpoint(pivots.iloc[:6], pivots)

        self.assertEqual(result["wave5_endpoint_status"], "clean_or_unresolved_wave5_endpoint")
        self.assertEqual(result["proposed_endpoint_classification"], "candidate_impulse_provisional")
        self.assertFalse(result["future_more_extreme_found"])

    def test_wave5_continuation_is_marked_premature(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
                ("low", 130.0, 60, 62),
                ("high", 145.0, 70, 72),
            ]
        )

        result = diagnose_wave5_endpoint(pivots.iloc[:6], pivots)

        self.assertEqual(result["wave5_endpoint_status"], "premature_wave5_completion")
        self.assertEqual(result["proposed_endpoint_classification"], "premature_wave5_completion")
        self.assertTrue(result["future_more_extreme_found"])
        self.assertEqual(result["post_wave5_extreme_pivot_id"], 8)

    def test_truncated_fifth_is_not_clean_impulse(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 123.0, 52, 54),
                ("low", 118.0, 60, 62),
            ]
        )

        result = diagnose_wave5_endpoint(pivots.iloc[:6], pivots)

        self.assertEqual(result["wave5_endpoint_status"], "truncated_fifth_candidate")
        self.assertEqual(result["proposed_endpoint_classification"], "truncated_fifth_candidate")
        self.assertFalse(result["wave5_exceeds_wave3"])

    def test_candidate_row_keeps_count_detection_causal(self):
        pivots = _structural_pivots(
            [
                ("high", 130.0, 0, 2),
                ("low", 120.0, 8, 10),
                ("high", 126.0, 16, 18),
                ("low", 110.0, 28, 30),
                ("high", 118.0, 40, 42),
                ("low", 101.0, 52, 54),
                ("high", 106.0, 60, 62),
                ("low", 96.0, 70, 72),
            ]
        )
        row = pd.Series(
            {
                "candidate_id": "impulse_synthetic_intermediate_impulse_001",
                "source_id": "synthetic_intermediate_impulse_001",
                "review_category": "impulse",
                "example_id": "synthetic",
                "group": "Test",
                "symbol": "TEST",
                "timeframe": "H1",
                "swing_degree": "intermediate",
                "direction": "bearish",
                "diagnostic_status": "strict_candidate_impulse",
                "start_pivot_id": 1,
                "end_pivot_id": 6,
            }
        )

        result = diagnose_candidate_row(row, pivots, config=Wave5EndpointConfig())

        self.assertEqual(result["wave5_endpoint_status"], "premature_wave5_completion")
        self.assertEqual(result["count_detected_at"], pivots.iloc[:6]["structural_detected_at"].max())
        self.assertGreater(pd.Timestamp(result["post_wave5_extreme_detected_at"]), result["count_detected_at"])


if __name__ == "__main__":
    unittest.main()
