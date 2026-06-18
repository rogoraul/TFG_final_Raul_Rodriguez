import unittest

import pandas as pd

from backtests.wavecount import CountConfig, build_candidate_counts


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


def _first_count(frame, pattern_type):
    counts = build_candidate_counts(frame, config=CountConfig())["candidate_counts"]
    subset = counts[counts["pattern_type"] == pattern_type]
    assert not subset.empty
    return subset.iloc[0], counts


class TestWaveCountCounts(unittest.TestCase):
    def test_valid_bullish_impulse_candidate(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
            ]
        )

        row, _ = _first_count(pivots, "impulse")

        self.assertEqual(row["count_state"], "candidate_impulse")
        self.assertEqual(row["direction"], "bullish")
        self.assertAlmostEqual(row["wave2_retrace_of_wave1"], 0.6)
        self.assertAlmostEqual(row["wave3_extension_of_wave1"], 2.1)

    def test_valid_bearish_impulse_candidate(self):
        pivots = _structural_pivots(
            [
                ("high", 120.0, 0, 2),
                ("low", 110.0, 8, 10),
                ("high", 116.0, 16, 18),
                ("low", 100.0, 28, 30),
                ("high", 108.0, 40, 42),
                ("low", 92.0, 52, 54),
            ]
        )

        row, _ = _first_count(pivots, "impulse")

        self.assertEqual(row["count_state"], "candidate_impulse")
        self.assertEqual(row["direction"], "bearish")

    def test_valid_bullish_abc_candidate(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 116.0, 28, 30),
            ]
        )

        row, _ = _first_count(pivots, "abc")

        self.assertEqual(row["count_state"], "candidate_abc")
        self.assertEqual(row["direction"], "bullish")
        self.assertAlmostEqual(row["abc_b_retrace_of_a"], 0.6)
        self.assertAlmostEqual(row["abc_c_vs_a"], 1.2)

    def test_valid_abc_has_exactly_four_ordered_leg_points(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 116.0, 28, 30),
            ]
        )

        result = build_candidate_counts(pivots)
        row = result["candidate_counts"][result["candidate_counts"]["pattern_type"] == "abc"].iloc[0]
        legs = result["count_legs"][result["count_legs"]["count_id"] == row["count_id"]].sort_values("point_order")

        self.assertEqual(len(legs), 4)
        self.assertEqual(list(legs["point_order"]), [0, 1, 2, 3])
        self.assertEqual(list(legs["point_label"]), ["0", "A", "B", "C"])
        times = list(pd.to_datetime(legs["pivot_extreme_time"]))
        detections = list(pd.to_datetime(legs["structural_detected_at"]))
        self.assertTrue(all(times[index] < times[index + 1] for index in range(3)))
        self.assertTrue(all(detections[index] <= detections[index + 1] for index in range(3)))
        self.assertGreaterEqual(row["count_detected_at"], detections[-1])

    def test_valid_bearish_abc_candidate(self):
        pivots = _structural_pivots(
            [
                ("high", 120.0, 0, 2),
                ("low", 110.0, 8, 10),
                ("high", 116.0, 16, 18),
                ("low", 104.0, 28, 30),
            ]
        )

        row, _ = _first_count(pivots, "abc")

        self.assertEqual(row["count_state"], "candidate_abc")
        self.assertEqual(row["direction"], "bearish")

    def test_abc_with_visual_time_reversal_is_ambiguous(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 7, 18),
                ("high", 116.0, 28, 30),
            ]
        )

        row, _ = _first_count(pivots, "abc")

        self.assertEqual(row["count_state"], "ambiguous_count")
        self.assertIn("strict visual time order", row["reason"])

    def test_abc_invalidates_when_b_breaks_origin(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 99.0, 16, 18),
                ("high", 116.0, 28, 30),
            ]
        )

        row, _ = _first_count(pivots, "abc")

        self.assertEqual(row["count_state"], "invalidated_count")
        self.assertIn("B leg breaks ABC origin", row["reason"])

    def test_abc_small_c_leg_is_ambiguous_not_clean(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 109.0, 16, 18),
                ("high", 113.0, 28, 30),
            ]
        )

        row, _ = _first_count(pivots, "abc")

        self.assertEqual(row["count_state"], "ambiguous_count")
        self.assertIn("ABC is too compressed", row["reason"])

    def test_count_ids_are_unique_across_swing_degrees(self):
        minor = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 116.0, 28, 30),
            ],
            degree="minor",
        )
        intermediate = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 116.0, 28, 30),
            ],
            degree="intermediate",
        )

        result_minor = build_candidate_counts(minor, config=CountConfig(primary_degree="minor"))
        result_intermediate = build_candidate_counts(intermediate, config=CountConfig(primary_degree="intermediate"))
        count_ids = list(result_minor["candidate_counts"]["count_id"]) + list(result_intermediate["candidate_counts"]["count_id"])

        self.assertEqual(len(count_ids), len(set(count_ids)))

    def test_invalidates_when_wave_2_breaks_origin(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 99.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
            ]
        )

        row, _ = _first_count(pivots, "impulse")

        self.assertEqual(row["count_state"], "invalidated_count")
        self.assertIn("wave 2 breaks wave 1 origin", row["reason"])

    def test_invalidates_when_wave_3_does_not_exceed_wave_1(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 109.0, 28, 30),
                ("low", 106.0, 40, 42),
                ("high", 114.0, 52, 54),
            ]
        )

        row, _ = _first_count(pivots, "impulse")

        self.assertEqual(row["count_state"], "invalidated_count")
        self.assertIn("wave 3 does not exceed wave 1 extreme", row["reason"])

    def test_marks_wave_4_overlap_as_ambiguous_without_other_hard_invalidations(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 109.0, 40, 42),
                ("high", 130.0, 52, 54),
            ]
        )

        row, _ = _first_count(pivots, "impulse")

        self.assertEqual(row["count_state"], "ambiguous_count")
        self.assertIn("wave 4 overlaps wave 1 territory", row["reason"])

    def test_wave_4_overlap_does_not_hide_hard_invalidations(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 99.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 109.0, 40, 42),
                ("high", 130.0, 52, 54),
            ]
        )

        row, _ = _first_count(pivots, "impulse")

        self.assertEqual(row["count_state"], "invalidated_count")
        self.assertIn("wave 2 breaks wave 1 origin", row["reason"])
        self.assertIn("wave 4 overlaps wave 1 territory", row["reason"])

    def test_count_detected_at_never_precedes_used_structural_detection(self):
        pivots = _structural_pivots(
            [
                ("low", 100.0, 0, 2),
                ("high", 110.0, 8, 10),
                ("low", 104.0, 16, 18),
                ("high", 125.0, 28, 30),
                ("low", 115.0, 40, 42),
                ("high", 136.0, 52, 54),
            ]
        )

        result = build_candidate_counts(pivots)
        counts = result["candidate_counts"]

        self.assertTrue((counts["count_detected_at"] >= counts["max_structural_detected_at_used"]).all())
        self.assertTrue(counts["lookahead_safe"].all())


if __name__ == "__main__":
    unittest.main()
