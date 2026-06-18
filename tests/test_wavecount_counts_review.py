import unittest

import pandas as pd

from backtests.wavecount import build_invalidations_review, build_rule_severity_summary
from backtests.wavecount.wavecount_counts_review import classify_reason


class TestWaveCountCountsReview(unittest.TestCase):
    def test_classifies_wave_2_origin_break_as_hard_invalid(self):
        result = classify_reason("wave 2 breaks wave 1 origin")

        self.assertEqual(result["rule_severity"], "hard_invalid")
        self.assertEqual(result["recommended_state"], "invalidated_count")
        self.assertFalse(result["possible_false_negative"])

    def test_classifies_wave_3_shortest_as_hard_invalid(self):
        result = classify_reason("wave 3 is shorter than both wave 1 and wave 5")

        self.assertEqual(result["rule_severity"], "hard_invalid")
        self.assertEqual(result["recommended_state"], "invalidated_count")

    def test_classifies_wave_4_overlap_as_soft_ambiguous(self):
        result = classify_reason("wave 4 overlaps wave 1 territory")

        self.assertEqual(result["rule_severity"], "soft_invalid_or_ambiguous")
        self.assertEqual(result["recommended_state"], "ambiguous_count")
        self.assertTrue(result["possible_false_negative"])

    def test_builds_review_and_summary(self):
        counts = pd.DataFrame(
            [
                {
                    "count_id": "hard",
                    "example_id": "synthetic",
                    "pattern_type": "impulse",
                    "count_state": "invalidated_count",
                    "reason": "wave 2 breaks wave 1 origin",
                },
                {
                    "count_id": "soft",
                    "example_id": "synthetic",
                    "pattern_type": "impulse",
                    "count_state": "invalidated_count",
                    "reason": "wave 4 overlaps wave 1 territory",
                },
            ]
        )

        review = build_invalidations_review(counts)
        summary = build_rule_severity_summary(review)

        self.assertEqual(len(review), 2)
        self.assertEqual(set(review["rule_severity"]), {"hard_invalid", "soft_invalid_or_ambiguous"})
        self.assertEqual(int(review["state_changed_by_review"].sum()), 1)
        self.assertIn("wave 4 overlaps wave 1 territory", set(summary["reason"]))


if __name__ == "__main__":
    unittest.main()
