import unittest

import pandas as pd

from backtests.wavecount.build_wavecount_soft_quality_policy_256 import (
    KEY_FALSE_POSITIVE_ID,
    build_bucket_changes,
    build_low_prominence_false_positive_diagnostics,
    build_phase256_policy_scores,
)


class TestWaveCountSoftQualityPolicy256(unittest.TestCase):
    def _sample_scores(self):
        return pd.DataFrame(
            [
                {
                    "candidate_id": KEY_FALSE_POSITIVE_ID,
                    "source_scope": "h4_d1",
                    "symbol": "XAGUSD.r",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "review_category": "impulse",
                    "final_soft_quality_bucket": "usable_provisional_structure",
                    "final_soft_quality_score": 84,
                    "prominence_policy_label": "low_prominence_vs_window",
                    "scale_fit_label": "too_small_for_timeframe",
                    "should_downgrade_to_auxiliary": True,
                    "context_must_not_rescue_bad_count": False,
                    "chart_path": "",
                },
                {
                    "candidate_id": "h4_minor_low",
                    "source_scope": "h4_d1",
                    "symbol": "AUDJPY.r",
                    "timeframe": "H4",
                    "swing_degree": "minor",
                    "review_category": "impulse",
                    "final_soft_quality_bucket": "ambiguous_structure",
                    "final_soft_quality_score": 60,
                    "prominence_policy_label": "better_as_lower_tf_substructure",
                    "scale_fit_label": "better_as_lower_tf_substructure",
                    "should_downgrade_to_auxiliary": True,
                    "context_must_not_rescue_bad_count": False,
                    "chart_path": "",
                },
                {
                    "candidate_id": "h1_aux_low",
                    "source_scope": "h1_h4",
                    "symbol": "AUS200",
                    "timeframe": "H1",
                    "swing_degree": "intermediate",
                    "review_category": "impulse",
                    "final_soft_quality_bucket": "auxiliary_substructure",
                    "final_soft_quality_score": 58,
                    "prominence_policy_label": "better_as_lower_tf_substructure",
                    "scale_fit_label": "better_as_lower_tf_substructure",
                    "should_downgrade_to_auxiliary": True,
                    "context_must_not_rescue_bad_count": False,
                    "chart_path": "",
                },
                {
                    "candidate_id": "already_excluded",
                    "source_scope": "h4_d1",
                    "symbol": "AUS200",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "review_category": "impulse",
                    "final_soft_quality_bucket": "exclude_from_guided_search",
                    "final_soft_quality_score": 24,
                    "prominence_policy_label": "low_prominence_vs_window",
                    "scale_fit_label": "too_small_for_timeframe",
                    "should_downgrade_to_auxiliary": True,
                    "context_must_not_rescue_bad_count": True,
                    "chart_path": "",
                },
            ]
        )

    def test_key_false_positive_moves_to_watchlist(self):
        risks = pd.DataFrame([{"candidate_id": KEY_FALSE_POSITIVE_ID}])
        out = build_phase256_policy_scores(self._sample_scores(), risks).set_index("candidate_id")
        self.assertEqual(out.loc[KEY_FALSE_POSITIVE_ID, "phase256_policy_bucket"], "visual_watchlist_low_prominence")
        self.assertEqual(out.loc[KEY_FALSE_POSITIVE_ID, "phase256_ready_for_expansion"], "watchlist_only")
        self.assertLess(out.loc[KEY_FALSE_POSITIVE_ID, "phase256_score"], out.loc[KEY_FALSE_POSITIVE_ID, "final_soft_quality_score"])

    def test_minor_low_prominence_becomes_auxiliary_low_prominence(self):
        out = build_phase256_policy_scores(self._sample_scores(), pd.DataFrame()).set_index("candidate_id")
        self.assertEqual(out.loc["h4_minor_low", "phase256_policy_bucket"], "auxiliary_low_prominence_substructure")
        self.assertEqual(out.loc["h4_minor_low", "phase256_ready_for_expansion"], "auxiliary_only")

    def test_h1_h4_low_prominence_stays_auxiliary_only(self):
        out = build_phase256_policy_scores(self._sample_scores(), pd.DataFrame()).set_index("candidate_id")
        self.assertEqual(out.loc["h1_aux_low", "phase256_policy_bucket"], "auxiliary_low_prominence_substructure")
        self.assertEqual(out.loc["h1_aux_low", "phase256_ready_for_expansion"], "auxiliary_only")

    def test_already_excluded_stays_excluded(self):
        out = build_phase256_policy_scores(self._sample_scores(), pd.DataFrame()).set_index("candidate_id")
        self.assertEqual(out.loc["already_excluded", "phase256_policy_bucket"], "exclude_from_guided_search")
        self.assertEqual(out.loc["already_excluded", "phase256_ready_for_expansion"], "no")

    def test_low_prominence_diagnostics_only_reports_non_excluded(self):
        diagnostics = build_low_prominence_false_positive_diagnostics(
            self._sample_scores(),
            pd.DataFrame(),
            pd.DataFrame([{"candidate_id": KEY_FALSE_POSITIVE_ID}]),
        )
        ids = set(diagnostics["candidate_id"])
        self.assertIn(KEY_FALSE_POSITIVE_ID, ids)
        self.assertIn("h1_aux_low", ids)
        self.assertNotIn("already_excluded", ids)

    def test_bucket_changes_reports_derivative_policy_changes(self):
        out = build_phase256_policy_scores(self._sample_scores(), pd.DataFrame([{"candidate_id": KEY_FALSE_POSITIVE_ID}]))
        changes = build_bucket_changes(out)
        self.assertIn(KEY_FALSE_POSITIVE_ID, set(changes["candidate_id"]))
        self.assertIn("h4_minor_low", set(changes["candidate_id"]))


if __name__ == "__main__":
    unittest.main()
