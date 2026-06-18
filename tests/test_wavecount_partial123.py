import unittest

import pandas as pd

from backtests.wavecount.wavecount_partial123 import (
    Partial123Config,
    diagnose_partial123,
    diagnose_partial123_candidate_row,
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


class TestWaveCountPartial123(unittest.TestCase):
    def test_valid_partial_123_with_post_3_confirmation(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 118.0, 40, 42),
                ("high", 132.0, 52, 54),
            ]
        )

        result = diagnose_partial123(pivots.iloc[:4], pivots)

        self.assertEqual(result["partial123_status"], "valid_partial_123")
        self.assertEqual(result["live_state"], "partial_123_provisional")
        self.assertTrue(result["post_3_confirms"])

    def test_wave_2_breaking_origin_is_not_valid_partial(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 99.0, 16, 18),
                ("high", 124.0, 28, 30),
            ]
        )

        result = diagnose_partial123(pivots.iloc[:4], pivots)

        self.assertEqual(result["partial123_status"], "ambiguous_partial")
        self.assertEqual(result["live_state"], "invalid_partial_123")
        self.assertTrue(result["origin_break"])

    def test_weak_wave_3_is_too_lax(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 111.0, 28, 30),
                ("low", 106.0, 40, 42),
            ]
        )

        result = diagnose_partial123(pivots.iloc[:4], pivots)

        self.assertEqual(result["partial123_status"], "partial_123_too_lax")
        self.assertTrue(result["wave3_too_weak"])

    def test_post_3_break_of_wave_2_invalidates_retrospectively(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 103.0, 40, 42),
            ]
        )

        result = diagnose_partial123(pivots.iloc[:4], pivots)

        self.assertEqual(result["partial123_status"], "invalidated_after_3")
        self.assertEqual(result["live_state"], "partial_123_provisional_then_invalidated")
        self.assertTrue(result["post_3_invalidates"])

    def test_without_post_3_context_partial_stays_provisional(self):
        pivots = _structural_pivots(
            [
                ("high", 120.0, 0, 2),
                ("low", 110.0, 8, 10),
                ("high", 116.0, 16, 18),
                ("low", 100.0, 28, 30),
            ]
        )

        result = diagnose_partial123(pivots.iloc[:4], pivots)

        self.assertEqual(result["partial123_status"], "partial_123_provisional")
        self.assertEqual(result["live_state"], "partial_123_provisional")

    def test_candidate_row_keeps_partial_detected_at_causal(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 103.0, 40, 42),
            ]
        )
        row = pd.Series(
            {
                "candidate_id": "partial_123_synthetic_intermediate_partial123_001",
                "source_id": "synthetic_intermediate_partial123_001",
                "review_category": "partial_123",
                "example_id": "synthetic",
                "group": "Test",
                "symbol": "TEST",
                "timeframe": "H1",
                "swing_degree": "intermediate",
                "direction": "bullish",
                "diagnostic_status": "partial_123_candidate",
                "start_pivot_id": 1,
                "end_pivot_id": 4,
            }
        )

        result = diagnose_partial123_candidate_row(row, pivots, config=Partial123Config())

        self.assertEqual(result["partial_detected_at"], pivots.iloc[:4]["structural_detected_at"].max())
        self.assertGreater(pd.Timestamp(result["post_3_event_detected_at"]), result["partial_detected_at"])
        self.assertEqual(result["partial123_status"], "invalidated_after_3")


if __name__ == "__main__":
    unittest.main()
