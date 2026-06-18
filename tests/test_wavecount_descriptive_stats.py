import unittest

import pandas as pd

from backtests.wavecount.build_wavecount_descriptive_stats import (
    build_classification_stats,
    build_phase254_readiness_matrix,
    build_prominence_stats,
)


class TestWaveCountDescriptiveStats(unittest.TestCase):
    def test_classification_stats_count_h4_and_h1_profiles(self):
        h4 = pd.DataFrame(
            {
                "matches_guided_impulse_profile": ["yes", "near_miss", "no", "no"],
                "visual_expansion_status": ["strong_match", "near_miss_useful", "not_usable", "not_usable"],
                "near_miss_reason": ["", "minor_substructure", "", ""],
                "phase253_candidate_action": ["keep_as_seed_example", "manual_review", "exclude", "exclude"],
                "swing_degree": ["intermediate", "minor", "major", "intermediate"],
            }
        )
        h1 = pd.DataFrame(
            {
                "matches_h1_h4_aux_profile": ["yes_aux", "near_miss_aux", "no"],
                "visual_aux_status": ["good_aux_structure", "useful_lower_tf_substructure", "not_usable"],
                "aux_near_miss_reason": ["", "higher_degree_context", ""],
                "scale_fit_label": ["acceptable_for_timeframe", "better_as_lower_tf_substructure", "not_applicable"],
                "swing_degree": ["intermediate", "major", "minor"],
            }
        )

        h4_stats, h1_stats = build_classification_stats(h4, h1)

        h4_yes = h4_stats[
            h4_stats["metric"].eq("profile_class") & h4_stats["label"].eq("yes")
        ]["case_count"].iloc[0]
        h1_yes = h1_stats[
            h1_stats["metric"].eq("profile_class") & h1_stats["label"].eq("yes_aux")
        ]["case_count"].iloc[0]
        self.assertEqual(int(h4_yes), 1)
        self.assertEqual(int(h1_yes), 1)

    def test_prominence_stats_extract_problem_cases(self):
        prominence = pd.DataFrame(
            {
                "source_scope": ["h4_d1", "h1_h4"],
                "timeframe": ["H4", "H1"],
                "swing_degree": ["intermediate", "intermediate"],
                "scale_fit_label": ["too_small_for_timeframe", "acceptable_for_timeframe"],
                "prominence_vs_window": [0.12, 0.45],
                "duration_vs_window": [0.05, 0.2],
                "move_prominence_vs_window": [0.09, 0.32],
            }
        )

        stats, problems = build_prominence_stats(prominence)

        self.assertEqual(len(stats), 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems.iloc[0]["scale_fit_label"], "too_small_for_timeframe")

    def test_readiness_matrix_keeps_h4_primary_and_h1_auxiliary(self):
        h4 = pd.DataFrame({"matches_guided_impulse_profile": ["yes", "near_miss", "no"]})
        h1 = pd.DataFrame({"matches_h1_h4_aux_profile": ["yes_aux", "near_miss_aux", "no"]})
        prominence_problems = pd.DataFrame({"candidate_id": ["a"]})
        ewo_stats = pd.DataFrame({"ewo_label": ["supports_wave_role"], "case_count": [2]})
        ema_stats = pd.DataFrame({"context_label": ["supports_context"], "case_count": [3]})

        readiness = build_phase254_readiness_matrix(h4, h1, prominence_problems, ewo_stats, ema_stats)

        h4_status = readiness[readiness["component"].eq("H4/D1 intermediate profile")]["ready_status"].iloc[0]
        h1_status = readiness[readiness["component"].eq("H1/H4 auxiliary profile")]["ready_status"].iloc[0]
        prominence_status = readiness[readiness["component"].eq("prominence/size penalty")]["ready_status"].iloc[0]
        self.assertEqual(h4_status, "ready_for_soft_rule")
        self.assertEqual(h1_status, "auxiliary_only")
        self.assertEqual(prominence_status, "ready_for_soft_rule")


if __name__ == "__main__":
    unittest.main()
