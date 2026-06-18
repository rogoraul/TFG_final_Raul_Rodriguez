import unittest

import pandas as pd

from backtests.wavecount.build_wavecount_soft_policy_visual_audit import (
    REQUIRED_AUS200_ID,
    build_exclusion_bucket_audit,
    build_exclusion_ratio_diagnostics,
    build_false_negative_risks,
    build_visual_audit_selection,
    build_visual_policy_case_review,
)


class TestWaveCountSoftPolicyVisualAudit(unittest.TestCase):
    def _sample_scores(self):
        return pd.DataFrame(
            [
                {
                    "candidate_id": "high",
                    "source_scope": "h4_d1",
                    "final_soft_quality_bucket": "high_quality_structure",
                    "final_soft_quality_score": 100,
                    "prominence_policy_label": "acceptable_for_timeframe",
                    "ewo_policy_label": "relative_wave_role_support",
                    "ema_htf_policy_label": "ema_htf_context_support",
                    "policy_warnings": "",
                    "chart_path": "",
                    "visual_expansion_status": "strong_match",
                },
                {
                    "candidate_id": REQUIRED_AUS200_ID,
                    "source_scope": "h4_d1",
                    "final_soft_quality_bucket": "exclude_from_guided_search",
                    "final_soft_quality_score": 24,
                    "prominence_policy_label": "low_prominence_vs_window",
                    "ewo_policy_label": "relative_wave_role_support",
                    "ema_htf_policy_label": "ema_htf_correction_context",
                    "policy_warnings": "context_must_not_rescue_bad_count",
                    "chart_path": "",
                    "visual_expansion_status": "false_positive_risk",
                    "swing_degree": "intermediate",
                    "matches_guided_impulse_profile": "near_miss",
                },
                {
                    "candidate_id": "h1_watch",
                    "source_scope": "h1_h4",
                    "final_soft_quality_bucket": "exclude_from_guided_search",
                    "final_soft_quality_score": 49,
                    "prominence_policy_label": "ambiguous_scale",
                    "ewo_policy_label": "relative_wave_role_support",
                    "ema_htf_policy_label": "ema_htf_context_support",
                    "policy_warnings": "",
                    "chart_path": "",
                    "visual_aux_status": "good_aux_structure",
                    "swing_degree": "intermediate",
                    "matches_h1_h4_aux_profile": "no",
                },
                {
                    "candidate_id": "kept_low_prominence",
                    "source_scope": "h4_d1",
                    "final_soft_quality_bucket": "usable_provisional_structure",
                    "final_soft_quality_score": 84,
                    "prominence_policy_label": "low_prominence_vs_window",
                    "ewo_policy_label": "relative_wave_role_support",
                    "ema_htf_policy_label": "ema_htf_context_support",
                    "policy_warnings": "count is too small",
                    "chart_path": "",
                    "visual_expansion_status": "strong_match",
                    "swing_degree": "intermediate",
                    "matches_guided_impulse_profile": "yes",
                },
            ]
        )

    def test_ratio_diagnostics_reports_excluded_share(self):
        diagnostics = build_exclusion_ratio_diagnostics(self._sample_scores())
        row = diagnostics[
            diagnostics["diagnostic_scope"].eq("global")
            & diagnostics["metric"].eq("excluded_rows")
        ].iloc[0]
        self.assertEqual(int(row["case_count"]), 2)

    def test_selection_includes_high_quality_and_required_aus200(self):
        selected = build_visual_audit_selection(self._sample_scores(), output_dir=__import__("pathlib").Path("."))
        ids = set(selected["candidate_id"])
        self.assertIn("high", ids)
        self.assertIn(REQUIRED_AUS200_ID, ids)

    def test_visual_review_marks_false_positive_exclusion_valid(self):
        selected = build_visual_audit_selection(self._sample_scores(), output_dir=__import__("pathlib").Path("."))
        reviews = build_visual_policy_case_review(selected).set_index("candidate_id")
        self.assertEqual(reviews.loc[REQUIRED_AUS200_ID, "exclusion_reason_validity"], "valid_exclusion")

    def test_false_negative_risks_catch_watchlist_candidates(self):
        selected = build_visual_audit_selection(self._sample_scores(), output_dir=__import__("pathlib").Path("."))
        reviews = build_visual_policy_case_review(selected)
        risks = build_false_negative_risks(reviews)
        self.assertIn("h1_watch", set(risks["candidate_id"]))

    def test_kept_h4_low_prominence_is_flagged_as_too_lenient(self):
        selected = build_visual_audit_selection(self._sample_scores(), output_dir=__import__("pathlib").Path("."))
        reviews = build_visual_policy_case_review(selected).set_index("candidate_id")
        self.assertEqual(reviews.loc["kept_low_prominence", "visual_policy_verdict"], "policy_too_lenient")
        self.assertEqual(reviews.loc["kept_low_prominence", "recommended_policy_adjustment"], "increase_prominence_penalty")

    def test_exclusion_bucket_audit_has_near_threshold_group(self):
        selected = build_visual_audit_selection(self._sample_scores(), output_dir=__import__("pathlib").Path("."))
        reviews = build_visual_policy_case_review(selected)
        audit = build_exclusion_bucket_audit(self._sample_scores(), reviews)
        self.assertIn("near_threshold_excluded", set(audit["exclusion_group"]))


if __name__ == "__main__":
    unittest.main()
