import unittest

import pandas as pd

from backtests.wavecount.build_wavecount_h1_h4_aux_expansion import (
    _aux_near_miss_reason,
    _aux_profile_match,
    _scale_fit_label,
)


def _row(**overrides):
    data = {
        "review_category": "impulse",
        "timeframe": "H1",
        "swing_degree": "intermediate",
        "trend_context_label": "impulse_with_htf",
        "context_score": 80,
        "htf_lookahead_safe": True,
        "htf_direction_match": True,
        "htf_direction_conflict": False,
        "ltf_direction_match": True,
        "momentum_matches_direction": True,
        "end_ltf_price_vs_ema_band": "above_band",
    }
    data.update(overrides)
    return pd.Series(data)


class TestWaveCountH1H4AuxExpansion(unittest.TestCase):
    def test_h1_intermediate_impulse_can_match_aux_profile(self):
        result = _aux_profile_match(_row())

        self.assertEqual(result["matches_h1_h4_aux_profile"], "yes_aux")
        self.assertGreaterEqual(result["aux_profile_match_score"], 85)

    def test_h1_context_conflict_is_near_miss_aux(self):
        row = _row(trend_context_label="conflict_with_htf", htf_direction_match=False, htf_direction_conflict=True)
        result = _aux_profile_match(row)
        combined = pd.concat([row, pd.Series(result)])

        self.assertEqual(result["matches_h1_h4_aux_profile"], "near_miss_aux")
        self.assertEqual(_aux_near_miss_reason(combined), "context_conflict")

    def test_minor_h1_impulse_is_aux_near_miss_substructure(self):
        row = _row(swing_degree="minor")
        result = _aux_profile_match(row)
        combined = pd.concat([row, pd.Series(result)])

        self.assertEqual(result["matches_h1_h4_aux_profile"], "near_miss_aux")
        self.assertEqual(_aux_near_miss_reason(combined), "minor_substructure")

    def test_short_h4_duration_is_too_small_for_timeframe(self):
        label = _scale_fit_label(_row(timeframe="H4"), prominence=0.45, duration=0.07, source_scope="h4_d1")

        self.assertEqual(label, "too_small_for_timeframe")


if __name__ == "__main__":
    unittest.main()
