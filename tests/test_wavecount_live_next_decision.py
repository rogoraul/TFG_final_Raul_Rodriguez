import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_next_decision import (
    WaveCountLiveNextDecisionConfig,
    build_wavecount_live_next_decision,
)


class WaveCountLiveNextDecisionTests(unittest.TestCase):
    def test_next_decision_generates_artifacts_without_operational_side_effects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            lag_dir = root / "lag"
            append_dir = root / "append"
            visual_dir = root / "visual"
            output_dir = root / "out"
            doc_path = root / "next_decision.md"
            self._write_inputs(lag_dir, append_dir, visual_dir)

            result = build_wavecount_live_next_decision(
                WaveCountLiveNextDecisionConfig(
                    lag_resolution_dir=lag_dir,
                    append_only_dir=append_dir,
                    visual_audit_dir=visual_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                )
            )

            for filename in [
                "strategic_diagnosis.csv",
                "continuation_options.csv",
                "recommendation_matrix.csv",
                "redesign_path_if_needed.csv",
                "late_context_path.csv",
                "park_wavecount_path.csv",
                "roadmap_implications.csv",
                "do_not_do_yet.csv",
                "open_decisions.csv",
            ]:
                self.assertTrue((output_dir / "tables" / filename).exists(), filename)

            self.assertTrue((output_dir / "WAVECOUNT_LIVE_NEXT_DECISION.md").exists())
            self.assertTrue((output_dir / "run_meta.json").exists())
            self.assertTrue(doc_path.exists())
            self.assertEqual(result.recommendation, "hybrid_late_context_plus_enbolsa_platform")

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])

    @staticmethod
    def _write_inputs(lag_dir: Path, append_dir: Path, visual_dir: Path) -> None:
        lag_dir.mkdir(parents=True)
        (append_dir / "tables").mkdir(parents=True)
        visual_dir.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "decision": "late_context_only",
                    "selected_config": "time_mid_c",
                    "selected_category": "late_context_only",
                    "best_score": 48.1,
                    "late_confirmation_pct": 0.825,
                    "unstable_pivots_pct": 0.425,
                    "too_noisy_pct": 0.125,
                    "visual_rows": 12,
                    "sql_staging_allowed": False,
                    "dashboard_allowed": False,
                    "signals_allowed": False,
                    "rationale": "late context only",
                }
            ]
        ).to_csv(lag_dir / "decision_summary.csv", index=False)
        pd.DataFrame(
            [
                {
                    "config_name": "time_mid_c",
                    "rank": 1,
                    "detected_pivots_total": 1381,
                    "structural_pivots_total": 237,
                    "too_noisy_cuts": 5,
                    "unstable_pivot_cuts": 17,
                    "late_confirmation_cuts": 33,
                    "completed_impulse_pct": 0.525,
                    "anti_lookahead_passed": True,
                    "hard_flags_fail_closed": True,
                    "score": 48.1,
                    "late_cut_pct": 0.825,
                    "unstable_cut_pct": 0.425,
                    "noise_cut_pct": 0.125,
                },
                {
                    "config_name": "baseline_actual",
                    "rank": 2,
                    "detected_pivots_total": 4008,
                    "structural_pivots_total": 1181,
                    "too_noisy_cuts": 40,
                    "unstable_pivot_cuts": 9,
                    "late_confirmation_cuts": 37,
                    "completed_impulse_pct": 0.9,
                    "anti_lookahead_passed": True,
                    "hard_flags_fail_closed": True,
                    "score": -20.0,
                    "late_cut_pct": 0.925,
                    "unstable_cut_pct": 0.225,
                    "noise_cut_pct": 1.0,
                },
            ]
        ).to_csv(lag_dir / "lag_stability_config_comparison.csv", index=False)
        pd.DataFrame(
            [
                {
                    "config_name": "time_mid_c",
                    "rank": 1,
                    "category": "late_context_only",
                    "failed_criteria": "late_confirmation_not_below_50pct",
                }
            ]
        ).to_csv(lag_dir / "lag_stability_candidate_evaluation.csv", index=False)
        pd.DataFrame(
            [
                {
                    "question": "Can provisional labels be shown?",
                    "answer": "yes_after_stability_model",
                    "implication": "Only with warnings.",
                    "recommended_fields": "display_policy",
                }
            ]
        ).to_csv(visual_dir / "append_only_implications.csv", index=False)
        pd.DataFrame(
            [
                {
                    "decision_id": "max_lag_threshold",
                    "question": "What lag is acceptable?",
                    "why_it_matters": "Needed before dashboard.",
                }
            ]
        ).to_csv(append_dir / "tables" / "open_decisions.csv", index=False)


if __name__ == "__main__":
    unittest.main()
