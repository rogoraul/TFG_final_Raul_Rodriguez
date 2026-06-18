import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_visual_manual_audit import (
    VisualManualAuditConfig,
    build_visual_manual_audit,
)


class WaveCountLiveVisualManualAuditTests(unittest.TestCase):
    def test_visual_manual_audit_generates_outputs_without_operational_side_effects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "grid_v2"
            output_dir = root / "visual_audit"
            doc_path = root / "visual_audit.md"
            self._write_minimal_grid_v2(input_dir)

            result = build_visual_manual_audit(
                VisualManualAuditConfig(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    focused_configs=("baseline_actual", "time_hard_a", "time_hard_b"),
                    visual_configs=("baseline_actual", "time_hard_a", "time_hard_b"),
                )
            )

            for filename in [
                "visual_chart_audit.csv",
                "problem_cut_audit.csv",
                "focused_config_comparison.csv",
                "append_only_implications.csv",
                "decision_summary.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_LIVE_VISUAL_MANUAL_AUDIT.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            decision = pd.read_csv(output_dir / "decision_summary.csv")

            self.assertTrue(doc_path.exists())
            self.assertEqual(result.decision, decision.iloc[0]["decision"])
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])

    @staticmethod
    def _write_minimal_grid_v2(input_dir: Path) -> None:
        input_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / "charts").mkdir()
        comparison_rows = [
            {
                "config_name": "time_hard_b",
                "cuts": 2,
                "bars_used_total": 100,
                "detected_pivots_total": 8,
                "structural_pivots_total": 4,
                "detected_pivots_per_100_bars": 8.0,
                "structural_pivots_per_100_bars": 4.0,
                "too_noisy_cuts": 0,
                "too_sparse_cuts": 0,
                "unstable_pivot_cuts": 1,
                "late_confirmation_cuts": 2,
                "phase_change_count": 1,
                "phase_change_pct_non_initial": 1.0,
                "abrupt_transition_count": 0,
                "completed_impulse_count": 1,
                "completed_impulse_pct": 0.5,
                "unknown_pct": 0.0,
                "ambiguous_pct": 0.0,
                "invalidated_pct": 0.0,
                "median_confirmation_lag_bars": 10,
                "max_confirmation_lag_bars": 12,
                "anti_lookahead_passed": True,
                "hard_flags_fail_closed": True,
                "config_family": "time_filter",
                "detected_reduction_vs_baseline_pct": 0.7,
                "structural_reduction_vs_baseline_pct": 0.8,
                "detected_reduction_vs_v1_best_pct": 0.4,
                "structural_reduction_vs_v1_best_pct": 0.1,
                "noise_cut_pct": 0.0,
                "sparse_cut_pct": 0.0,
                "unstable_cut_pct": 0.5,
                "late_cut_pct": 1.0,
                "score": 50,
                "candidate_pass": False,
                "rank": 1,
            },
            {
                "config_name": "time_hard_a",
                "cuts": 2,
                "bars_used_total": 100,
                "detected_pivots_total": 10,
                "structural_pivots_total": 5,
                "detected_pivots_per_100_bars": 10.0,
                "structural_pivots_per_100_bars": 5.0,
                "too_noisy_cuts": 1,
                "too_sparse_cuts": 0,
                "unstable_pivot_cuts": 0,
                "late_confirmation_cuts": 2,
                "phase_change_count": 1,
                "phase_change_pct_non_initial": 1.0,
                "abrupt_transition_count": 0,
                "completed_impulse_count": 1,
                "completed_impulse_pct": 0.5,
                "unknown_pct": 0.0,
                "ambiguous_pct": 0.0,
                "invalidated_pct": 0.0,
                "median_confirmation_lag_bars": 8,
                "max_confirmation_lag_bars": 10,
                "anti_lookahead_passed": True,
                "hard_flags_fail_closed": True,
                "config_family": "time_filter",
                "detected_reduction_vs_baseline_pct": 0.5,
                "structural_reduction_vs_baseline_pct": 0.6,
                "detected_reduction_vs_v1_best_pct": 0.2,
                "structural_reduction_vs_v1_best_pct": 0.0,
                "noise_cut_pct": 0.5,
                "sparse_cut_pct": 0.0,
                "unstable_cut_pct": 0.0,
                "late_cut_pct": 1.0,
                "score": 45,
                "candidate_pass": False,
                "rank": 2,
            },
            {
                "config_name": "baseline_actual",
                "cuts": 2,
                "bars_used_total": 100,
                "detected_pivots_total": 20,
                "structural_pivots_total": 10,
                "detected_pivots_per_100_bars": 20.0,
                "structural_pivots_per_100_bars": 10.0,
                "too_noisy_cuts": 2,
                "too_sparse_cuts": 0,
                "unstable_pivot_cuts": 0,
                "late_confirmation_cuts": 2,
                "phase_change_count": 0,
                "phase_change_pct_non_initial": 0.0,
                "abrupt_transition_count": 0,
                "completed_impulse_count": 2,
                "completed_impulse_pct": 1.0,
                "unknown_pct": 0.0,
                "ambiguous_pct": 0.0,
                "invalidated_pct": 0.0,
                "median_confirmation_lag_bars": 3,
                "max_confirmation_lag_bars": 5,
                "anti_lookahead_passed": True,
                "hard_flags_fail_closed": True,
                "config_family": "baseline",
                "detected_reduction_vs_baseline_pct": 0.0,
                "structural_reduction_vs_baseline_pct": 0.0,
                "detected_reduction_vs_v1_best_pct": 0.0,
                "structural_reduction_vs_v1_best_pct": 0.0,
                "noise_cut_pct": 1.0,
                "sparse_cut_pct": 0.0,
                "unstable_cut_pct": 0.0,
                "late_cut_pct": 1.0,
                "score": 0,
                "candidate_pass": False,
                "rank": 3,
            },
        ]
        pd.DataFrame(comparison_rows).to_csv(input_dir / "config_comparison_v2.csv", index=False)
        pd.DataFrame(
            [
                {"config_name": row["config_name"], "config_family": row["config_family"], "score": row["score"], "rank": row["rank"], "candidate_pass": False, "failed_criteria": "late_confirmation_above_50pct", "candidate_label": "not_candidate"}
                for row in comparison_rows
            ]
        ).to_csv(input_dir / "candidate_evaluation.csv", index=False)
        pd.DataFrame(
            [
                {"config_name": "time_hard_b", "market_group": "Forex Majors", "cuts": 2, "bars_used_total": 100, "detected_pivots_total": 8, "structural_pivots_total": 4, "detected_pivots_per_100_bars": 8, "structural_pivots_per_100_bars": 4, "too_noisy_cuts": 0, "too_noisy_pct": 0, "unstable_pivot_cuts": 1, "unstable_pct": 0.5, "completed_impulse_pct": 0.5, "unknown_pct": 0, "ambiguous_pct": 0}
            ]
        ).to_csv(input_dir / "market_group_sensitivity.csv", index=False)
        pd.DataFrame(
            [
                {"config_name": "time_hard_b", "cut_id": "TEST_H4_cut01", "symbol": "TEST", "timeframe": "H4", "cut_number": 1, "as_of_bar_time": "2026-01-01T00:00:00", "bars_used": 40, "detected_pivots": 4, "structural_pivots": 2, "new_structural_pivots_vs_previous_cut": 2, "disappeared_structural_pivots_vs_previous_cut": 0, "confirmed_pivots": 4, "median_confirmation_lag_bars": 10, "max_confirmation_lag_bars": 10, "alternates_high_low": True, "too_noisy": False, "too_sparse": False, "unstable_pivots": False, "late_confirmation": True, "over_sensitive": False, "needs_visual_review": True},
                {"config_name": "time_hard_b", "cut_id": "TEST_H4_cut02", "symbol": "TEST", "timeframe": "H4", "cut_number": 2, "as_of_bar_time": "2026-01-02T00:00:00", "bars_used": 60, "detected_pivots": 4, "structural_pivots": 2, "new_structural_pivots_vs_previous_cut": 1, "disappeared_structural_pivots_vs_previous_cut": 1, "confirmed_pivots": 4, "median_confirmation_lag_bars": 10, "max_confirmation_lag_bars": 12, "alternates_high_low": True, "too_noisy": False, "too_sparse": False, "unstable_pivots": True, "late_confirmation": True, "over_sensitive": False, "needs_visual_review": True},
            ]
        ).to_csv(input_dir / "pivot_stability_by_config.csv", index=False)
        pd.DataFrame(
            [
                {"config_name": "time_hard_b", "symbol": "TEST", "timeframe": "H4", "cut_number": 1, "as_of_bar_time": "2026-01-01T00:00:00", "previous_structure_phase": "", "structure_phase": "possible_wave2", "phase_changed": False, "rank_delta": "", "transition_type": "initial_cut", "churn_count_to_date": 0, "ambiguous_count_to_date": 0, "invalidated_count_to_date": 0, "wave3_candidate_evidence_ok": True, "wave5_active_evidence_ok": True, "needs_manual_review": False},
                {"config_name": "time_hard_b", "symbol": "TEST", "timeframe": "H4", "cut_number": 2, "as_of_bar_time": "2026-01-02T00:00:00", "previous_structure_phase": "possible_wave2", "structure_phase": "completed_impulse_candidate", "phase_changed": True, "rank_delta": 6, "transition_type": "abrupt_reclassification", "churn_count_to_date": 1, "ambiguous_count_to_date": 0, "invalidated_count_to_date": 0, "wave3_candidate_evidence_ok": True, "wave5_active_evidence_ok": True, "needs_manual_review": True},
            ]
        ).to_csv(input_dir / "label_transition_by_config.csv", index=False)
        pd.DataFrame([{"config_name": "time_hard_b", "rows": 2, "lookahead_safe_all": True, "detected_at_lte_as_of_all": True, "evidence_window_end_lte_as_of_all": True, "pivot_detected_at_lte_as_of_all": True, "future_pivots_used_total": 0, "bars_after_as_of_ignored": 0}]).to_csv(input_dir / "anti_lookahead_by_config.csv", index=False)
        pd.DataFrame([{"selected_config": "time_hard_b", "recommended_action": "needs_more_real_ohlc_review", "rationale": "synthetic", "sql_staging_allowed": False, "dashboard_allowed": False, "signals_allowed": False}]).to_csv(input_dir / "recommended_next_action.csv", index=False)
        pd.DataFrame([{"severity": "medium", "risk": "synthetic", "description": "synthetic", "recommendation": "synthetic"}]).to_csv(input_dir / "issues_or_risks.csv", index=False)
        pd.DataFrame([{"chart_file": str(input_dir / "charts" / "time_hard_b_TEST_H4_20260102T000000.png"), "manual_review_label": "needs_manual_review", "notes": "synthetic"}]).to_csv(input_dir / "chart_review.csv", index=False)
        (input_dir / "run_meta.json").write_text(json.dumps({"safety": {"real_sql_executed": False}}), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
