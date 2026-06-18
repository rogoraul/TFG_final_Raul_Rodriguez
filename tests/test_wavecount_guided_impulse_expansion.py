import unittest

import pandas as pd

from backtests.wavecount.build_wavecount_guided_impulse_expansion import (
    _near_miss_reason,
    _profile_match_expanded,
)


def _row(**overrides):
    data = {
        "review_category": "impulse",
        "timeframe": "H4",
        "swing_degree": "intermediate",
        "trend_context_label": "impulse_with_htf",
        "context_score": 85,
        "htf_lookahead_safe": True,
        "htf_direction_match": True,
        "htf_direction_conflict": False,
        "ltf_direction_match": True,
        "momentum_matches_direction": True,
        "end_ltf_price_vs_ema_band": "above_band",
        "transition_matches_direction": False,
    }
    data.update(overrides)
    return pd.Series(data)


class TestWaveCountGuidedImpulseExpansion(unittest.TestCase):
    def test_strong_h4_intermediate_impulse_matches_profile(self):
        result = _profile_match_expanded(_row())

        self.assertEqual(result["matches_guided_impulse_profile"], "yes")
        self.assertGreaterEqual(result["guided_profile_match_score"], 85)

    def test_context_conflict_is_near_miss_not_seed(self):
        row = _row(trend_context_label="conflict_with_htf", htf_direction_match=False, htf_direction_conflict=True)
        result = _profile_match_expanded(row)
        combined = pd.concat([row, pd.Series(result)])

        self.assertEqual(result["matches_guided_impulse_profile"], "near_miss")
        self.assertEqual(_near_miss_reason(combined), "context_conflict")

    def test_non_impulse_is_not_part_of_profile(self):
        result = _profile_match_expanded(_row(review_category="partial_123"))

        self.assertEqual(result["matches_guided_impulse_profile"], "no")
        self.assertIn("not part of impulse", result["guided_profile_critical_failures"])

    def test_minor_h4_impulse_is_near_miss_substructure(self):
        row = _row(swing_degree="minor")
        result = _profile_match_expanded(row)
        combined = pd.concat([row, pd.Series(result)])

        self.assertEqual(result["matches_guided_impulse_profile"], "near_miss")
        self.assertEqual(_near_miss_reason(combined), "minor_substructure")


if __name__ == "__main__":
    unittest.main()
