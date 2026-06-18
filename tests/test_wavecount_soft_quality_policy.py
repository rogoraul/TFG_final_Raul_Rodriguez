import unittest

import pandas as pd

from backtests.wavecount.build_wavecount_soft_quality_policy import (
    build_phase255_recommendation,
    build_structural_quality_scores,
    classify_ema_htf_policy,
    classify_ewo_policy,
    classify_prominence_policy,
)


class TestWaveCountSoftQualityPolicy(unittest.TestCase):
    def test_prominence_policy_marks_aus200_style_low_prominence_as_soft_penalty(self):
        row = pd.Series(
            {
                "candidate_id": "impulse_exp252_index_aus200_h4_intermediate_impulse_020",
                "scale_fit_label": "too_small_for_timeframe",
                "prominence_vs_window": 0.449,
                "duration_vs_window": 0.073,
                "relative_structure_size": "medium_small",
                "swing_degree": "intermediate",
                "matches_guided_impulse_profile": "near_miss",
            }
        )

        policy = classify_prominence_policy(row)

        self.assertEqual(policy["prominence_policy_label"], "low_prominence_vs_window")
        self.assertLess(policy["prominence_score_delta"], 0)
        self.assertTrue(policy["should_downgrade_to_auxiliary"])
        self.assertTrue(policy["should_exclude_for_low_prominence"])
        self.assertIn("duration_vs_window < 0.08", policy["prominence_policy_reason"])

    def test_ewo_policy_keeps_support_contextual_and_svm_future_only(self):
        row = pd.Series(
            {
                "ewo_helpfulness": "supports_wave_role",
                "momentum_matches_direction": True,
                "end_ltf_ewo_5_35_direction": "rising",
            }
        )

        policy = classify_ewo_policy(row)

        self.assertEqual(policy["ewo_policy_label"], "relative_wave_role_support")
        self.assertEqual(policy["ewo_soft_support"], "supports")
        self.assertTrue(policy["ewo_svm_future_feature_candidate"])

    def test_ema_htf_policy_does_not_rescue_bad_count(self):
        row = pd.Series(
            {
                "ema_htf_helpfulness": "supports_context",
                "trend_context_label": "impulse_with_htf",
                "end_ltf_price_vs_ema_band": "above_band",
                "visual_expansion_status": "false_positive_risk",
                "matches_guided_impulse_profile": "no",
            }
        )

        policy = classify_ema_htf_policy(row)

        self.assertTrue(policy["context_must_not_rescue_bad_count"])
        self.assertLess(policy["ema_htf_score_delta"], 8)

    def test_structural_quality_separates_primary_auxiliary_and_excluded(self):
        frame = pd.DataFrame(
            [
                {
                    "candidate_id": "h4_good",
                    "source_scope": "h4_d1",
                    "review_category": "impulse",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "matches_guided_impulse_profile": "yes",
                    "visual_expansion_status": "strong_match",
                    "scale_fit_label": "acceptable_for_timeframe",
                    "ewo_helpfulness": "supports_wave_role",
                    "ema_htf_helpfulness": "supports_context",
                },
                {
                    "candidate_id": "h1_aux",
                    "source_scope": "h1_h4",
                    "review_category": "impulse",
                    "timeframe": "H1",
                    "swing_degree": "intermediate",
                    "matches_h1_h4_aux_profile": "yes_aux",
                    "visual_aux_status": "good_aux_structure",
                    "scale_fit_label": "acceptable_for_timeframe",
                    "ewo_helpfulness": "supports_wave_role",
                    "ema_htf_helpfulness": "supports_context",
                },
                {
                    "candidate_id": "h4_bad",
                    "source_scope": "h4_d1",
                    "review_category": "impulse",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "matches_guided_impulse_profile": "near_miss",
                    "visual_expansion_status": "false_positive_risk",
                    "scale_fit_label": "too_small_for_timeframe",
                    "duration_vs_window": 0.05,
                    "ewo_helpfulness": "supports_wave_role",
                    "ema_htf_helpfulness": "misleading",
                },
            ]
        )

        scores = build_structural_quality_scores(frame).set_index("candidate_id")

        self.assertEqual(scores.loc["h4_good", "final_soft_quality_bucket"], "high_quality_structure")
        self.assertEqual(scores.loc["h1_aux", "final_soft_quality_bucket"], "auxiliary_substructure")
        self.assertEqual(scores.loc["h4_bad", "final_soft_quality_bucket"], "exclude_from_guided_search")

    def test_phase255_recommendation_references_counts(self):
        scores = pd.DataFrame(
            {
                "final_soft_quality_bucket": [
                    "high_quality_structure",
                    "usable_provisional_structure",
                    "auxiliary_substructure",
                    "exclude_from_guided_search",
                ]
            }
        )

        recommendation = build_phase255_recommendation(scores)

        self.assertEqual(len(recommendation), 3)
        self.assertIn("1 high_quality", recommendation.iloc[0]["evidence_summary"])


if __name__ == "__main__":
    unittest.main()
