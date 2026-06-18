import unittest

import pandas as pd

from backtests.wavecount.wavecount_visual_review_gallery import _points_from_count_legs, _select_visual_candidates, _take_diverse


def _row(example_id, degree, index):
    return {
        "example_id": example_id,
        "group": "Test",
        "symbol": f"TEST{index}",
        "timeframe": "H1",
        "swing_degree": degree,
        "partial_id": f"{example_id}_{degree}_{index}",
        "partial_status": "partial_123_candidate",
        "partial_detected_at": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index),
    }


class TestWaveCountVisualReviewGallery(unittest.TestCase):
    def test_take_diverse_uses_partial_id_as_unique_key(self):
        frame = pd.DataFrame([_row("example", "intermediate", index) for index in range(3)])

        selected = _take_diverse(frame, limit=3, sort_columns=["partial_detected_at"])

        self.assertEqual(len(selected), 3)
        self.assertEqual(set(selected["partial_id"]), {"example_intermediate_0", "example_intermediate_1", "example_intermediate_2"})

    def test_select_visual_candidates_balances_partial_degrees(self):
        partials = pd.DataFrame(
            [_row("example", "intermediate", 1), _row("example", "minor", 2), _row("example", "major", 3)]
        )
        counts = pd.DataFrame(columns=["count_state", "swing_degree", "example_id", "group", "symbol", "timeframe", "count_detected_at"])
        impulses = pd.DataFrame(
            columns=["diagnostic_status", "swing_degree", "example_id", "group", "symbol", "timeframe", "count_detected_at"]
        )
        legs = pd.DataFrame()

        selected = _select_visual_candidates(counts, legs, impulses, partials)
        partial_selected = selected[selected["review_category"] == "partial_123"]

        self.assertEqual(set(partial_selected["swing_degree"]), {"intermediate", "minor", "major"})

    def test_abc_candidates_are_not_prelabelled_as_visually_good(self):
        counts = pd.DataFrame(
            [
                {
                    "count_id": "example_intermediate_abc_001",
                    "count_state": "candidate_abc",
                    "swing_degree": "intermediate",
                    "example_id": "example",
                    "group": "Test",
                    "symbol": "TEST",
                    "timeframe": "H1",
                    "count_detected_at": pd.Timestamp("2026-01-01"),
                    "direction": "bullish",
                    "pattern_type": "abc",
                }
            ]
        )
        partials = pd.DataFrame(columns=["partial_status", "swing_degree", "example_id", "group", "symbol", "timeframe"])
        impulses = pd.DataFrame(columns=["diagnostic_status", "swing_degree", "example_id", "group", "symbol", "timeframe"])

        selected = _select_visual_candidates(counts, pd.DataFrame(), impulses, partials)
        abc_selected = selected[selected["review_category"] == "abc"]

        self.assertEqual(abc_selected.iloc[0]["suggested_initial_label"], "ambiguous_but_interesting")

    def test_count_leg_points_are_filtered_by_swing_degree_for_legacy_duplicate_ids(self):
        rows = []
        for degree, offset in [("minor", 0), ("intermediate", 10)]:
            for order, label in enumerate(["0", "A", "B", "C"]):
                rows.append(
                    {
                        "count_id": "legacy_abc_001",
                        "point_order": order,
                        "point_label": label,
                        "swing_degree": degree,
                        "pivot_extreme_time": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=offset + order),
                        "pivot_extreme_price": 100 + offset + order,
                    }
                )
        legs = pd.DataFrame(rows)
        row = pd.Series({"source_id": "legacy_abc_001", "swing_degree": "intermediate", "review_category": "abc"})

        points = _points_from_count_legs(legs, row)

        self.assertEqual(len(points), 4)
        self.assertEqual(set(points["swing_degree"]), {"intermediate"})
        self.assertEqual(list(points["point_label"]), ["0", "A", "B", "C"])

    def test_abc_plot_points_reject_repeated_labels(self):
        legs = pd.DataFrame(
            [
                {
                    "count_id": "bad_abc",
                    "point_order": order,
                    "point_label": label,
                    "swing_degree": "intermediate",
                    "pivot_extreme_time": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=order),
                    "pivot_extreme_price": 100 + order,
                }
                for order, label in enumerate(["0", "A", "A", "C"])
            ]
        )
        row = pd.Series({"source_id": "bad_abc", "swing_degree": "intermediate", "review_category": "abc"})

        with self.assertRaises(ValueError):
            _points_from_count_legs(legs, row)


if __name__ == "__main__":
    unittest.main()
