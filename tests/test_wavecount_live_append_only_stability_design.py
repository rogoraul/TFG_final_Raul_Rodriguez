import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_append_only_stability_design import (
    AppendOnlyStabilityDesignConfig,
    build_append_only_stability_design,
)


class WaveCountLiveAppendOnlyStabilityDesignTests(unittest.TestCase):
    def test_design_generator_writes_required_artifacts_without_sql(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            visual_dir = root / "visual"
            grid_dir = root / "grid"
            output_dir = root / "append_only"
            doc_path = root / "append_only.md"
            self._write_minimal_evidence(visual_dir, grid_dir)

            result = build_append_only_stability_design(
                AppendOnlyStabilityDesignConfig(
                    output_dir=output_dir,
                    doc_path=doc_path,
                    visual_audit_dir=visual_dir,
                    grid_v2_dir=grid_dir,
                )
            )

            for filename in [
                "stability_state_model.csv",
                "context_identity_fields.csv",
                "append_only_policy.csv",
                "sql_future_tables.csv",
                "sql_future_views.csv",
                "integration_contracts.csv",
                "staging_entry_criteria.csv",
                "do_not_do_yet.csv",
                "open_decisions.csv",
            ]:
                self.assertTrue((output_dir / "tables" / filename).exists(), filename)
            self.assertTrue((output_dir / "WAVECOUNT_LIVE_APPEND_ONLY_STABILITY_DESIGN.md").exists())
            self.assertTrue((output_dir / "run_meta.json").exists())
            self.assertTrue(doc_path.exists())

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(result.run_meta["recommended_model"], "B_append_only_events_plus_revision_links")
            self.assertFalse(meta["real_sql_executed"])
            self.assertFalse(meta["ddl_executed"])
            self.assertFalse(meta["mt5_connected"])
            self.assertFalse(meta["backtests_executed"])
            self.assertFalse(meta["signals_generated"])

    @staticmethod
    def _write_minimal_evidence(visual_dir: Path, grid_dir: Path) -> None:
        visual_dir.mkdir(parents=True, exist_ok=True)
        grid_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {
                    "decision": "needs_append_only_stability_model",
                    "preferred_next_config": "time_hard_b",
                    "time_hard_b_visual_status": "late_but_readable",
                    "time_hard_a_visual_status": "borderline_less_extreme",
                    "candidate_live_readability_config_v0": False,
                    "sql_staging_allowed": False,
                    "dashboard_allowed": False,
                    "signals_allowed": False,
                    "next_review": "broader_time_hard_b_review_with_append_only_stability",
                    "rationale": "synthetic",
                }
            ]
        ).to_csv(visual_dir / "decision_summary.csv", index=False)
        pd.DataFrame(
            [
                {
                    "question": "Can label changes be accepted as live evolution?",
                    "answer": "yes_but_only_append_only",
                    "implication": "synthetic",
                    "recommended_fields": "prior_context_id",
                }
            ]
        ).to_csv(visual_dir / "append_only_implications.csv", index=False)
        pd.DataFrame(
            [
                {
                    "config_name": "time_hard_b",
                    "symbol": "TEST",
                    "market_group": "Test",
                    "cut_number": 1,
                    "as_of_bar_time": "2026-01-01T00:00:00",
                    "structure_phase": "possible_wave2",
                    "detected_pivots": 2,
                    "structural_pivots": 2,
                    "late_confirmation": True,
                    "unstable_pivots": True,
                    "transition_type": "initial_cut",
                    "problem_type": "unstable_pivots;late_confirmation",
                    "severity": "high",
                    "interpretation": "synthetic",
                }
            ]
        ).to_csv(visual_dir / "problem_cut_audit.csv", index=False)
        pd.DataFrame(
            [
                {
                    "config_name": "time_hard_b",
                    "visual_verdict": "best_visual_readability_but_too_late_and_unstable",
                    "lag_acceptability": "not_acceptable",
                    "sql_blocker": True,
                }
            ]
        ).to_csv(visual_dir / "focused_config_comparison.csv", index=False)
        pd.DataFrame(
            [
                {
                    "config_name": "time_hard_b",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "cut_number": 1,
                    "transition_type": "initial_cut",
                }
            ]
        ).to_csv(grid_dir / "label_transition_by_config.csv", index=False)
        pd.DataFrame(
            [
                {
                    "config_name": "time_hard_b",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "cut_number": 1,
                    "unstable_pivots": True,
                }
            ]
        ).to_csv(grid_dir / "pivot_stability_by_config.csv", index=False)


if __name__ == "__main__":
    unittest.main()
