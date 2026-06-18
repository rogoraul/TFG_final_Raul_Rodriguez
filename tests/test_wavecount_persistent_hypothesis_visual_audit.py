import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_persistent_hypothesis_visual_audit import (
    PersistentVisualAuditConfig,
    build_persistent_visual_audit,
)


class WaveCountPersistentHypothesisVisualAuditTests(unittest.TestCase):
    def test_visual_audit_generates_outputs_from_minimal_artifacts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "persistent"
            current_dir = root / "current"
            grid_dir = root / "grid"
            output_dir = root / "visual_audit"
            doc_path = root / "visual_audit.md"
            source_csv = root / "source_ohlc.csv"
            self._write_minimal_inputs(input_dir, current_dir, grid_dir, source_csv)

            result = build_persistent_visual_audit(
                PersistentVisualAuditConfig(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    current_dir=current_dir,
                    grid_v2_dir=grid_dir,
                    source_csv=source_csv,
                    generate_charts=False,
                )
            )

            for filename in [
                "contract_security_audit.csv",
                "wave5_dominance_audit.csv",
                "visual_wave_audit.csv",
                "wave_transition_diagnosis.csv",
                "model_comparison_audit.csv",
                "design_diagnosis.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_PERSISTENT_HYPOTHESIS_VISUAL_AUDIT.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            wave5 = pd.read_csv(output_dir / "wave5_dominance_audit.csv")
            design = pd.read_csv(output_dir / "design_diagnosis.csv")

            self.assertEqual(result.decision, "needs_cycle_reset_rules")
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertIn("risk", wave5.columns)
            self.assertIn("diagnosis", design.columns)
            self.assertTrue(doc_path.exists())

    @staticmethod
    def _write_minimal_inputs(input_dir: Path, current_dir: Path, grid_dir: Path, source_csv: Path) -> None:
        input_dir.mkdir(parents=True, exist_ok=True)
        current_dir.mkdir(parents=True, exist_ok=True)
        grid_dir.mkdir(parents=True, exist_ok=True)
        hypotheses = pd.DataFrame(
            [
                {
                    "hypothesis_id": "h1",
                    "generated_at": "2026-05-27T00:00:00Z",
                    "symbol": "TEST",
                    "market_group": "Test",
                    "timeframe": "H4",
                    "higher_timeframe": "D1",
                    "cut_number": 1,
                    "as_of_bar_time": "2026-01-02T00:00:00",
                    "estimated_current_wave": "possible_wave5_active",
                    "confirmed_wave_context": "possible_wave5_active",
                    "next_wave_hypothesis": "completed_impulse_candidate",
                    "hypothesis_status": "forming",
                    "freshness_status": "fresh_estimate",
                    "wave_stability_status": "provisional",
                    "display_policy": "show_with_warning",
                    "invalidation_level": "",
                    "distance_to_invalidation_pct": "",
                    "last_persistent_pivot_at": "2026-01-01T00:00:00",
                    "last_candidate_pivot_at": "2026-01-01T12:00:00",
                    "persistent_pivot_count": 7,
                    "candidate_pivot_count": 1,
                    "superseded_pivot_count": 0,
                    "wave_event": "initial_hypothesis",
                    "wave_event_reason": "persistent_pivots=7",
                    "lookahead_safe": True,
                    "is_read_only": True,
                    "can_generate_signal": False,
                    "can_filter_trade": False,
                    "can_execute_order": False,
                    "source": "test",
                    "data_origin": "test_fixture",
                    "method_version": "test",
                    "notes": "test",
                    "payload_json": "{}",
                }
            ]
        )
        hypotheses.to_csv(input_dir / "persistent_wave_hypothesis.csv", index=False)
        (input_dir / "persistent_wave_hypothesis.json").write_text(json.dumps(hypotheses.to_dict(orient="records")), encoding="utf-8")
        pd.DataFrame(
            [
                {
                    "pivot_uid": f"p{i}",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "pivot_type": "high" if i % 2 else "low",
                    "pivot_extreme_time": f"2026-01-01T0{i}:00:00",
                    "pivot_detected_at": f"2026-01-01T0{i}:00:00",
                    "pivot_price": 100 + i,
                    "pivot_role": "persistent_pivot" if i < 7 else "candidate_pivot",
                    "first_seen_at": "2026-01-01T00:00:00",
                    "last_seen_at": "2026-01-02T00:00:00",
                    "accepted_at": "2026-01-01T00:00:00" if i < 7 else "",
                    "superseded_at": "",
                    "superseded_by": "",
                    "persistence_cuts": 2 if i < 7 else 1,
                    "is_persistent": i < 7,
                    "is_current_candidate": i >= 7,
                    "rejection_reason": "",
                    "lookahead_safe": True,
                }
                for i in range(8)
            ]
        ).to_csv(input_dir / "persistent_pivots.csv", index=False)
        pd.DataFrame([{"pivot_uid": "p1", "symbol": "TEST", "timeframe": "H4", "cut_number": 1, "as_of_bar_time": "2026-01-02T00:00:00", "event_type": "persistent_seen", "pivot_type": "high", "pivot_detected_at": "2026-01-01T01:00:00", "lookahead_safe": True}]).to_csv(input_dir / "pivot_events.csv", index=False)
        pd.DataFrame([{"hypothesis_id": "h1", "symbol": "TEST", "timeframe": "H4", "cut_number": 1, "as_of_bar_time": "2026-01-02T00:00:00", "estimated_current_wave": "possible_wave5_active", "confirmed_wave_context": "possible_wave5_active", "wave_event": "initial_hypothesis", "wave_event_reason": "persistent_pivots=7", "display_policy": "show_with_warning"}]).to_csv(input_dir / "wave_events.csv", index=False)
        pd.DataFrame([{"hypothesis_id": "h1", "symbol": "TEST", "timeframe": "H4", "cut_number": 1, "as_of_bar_time": "2026-01-02T00:00:00", "bars_total": 2, "bars_used": 2, "bars_after_as_of_ignored": 0, "latest_pivot_detected_at": "2026-01-01T01:00:00", "latest_pivot_detected_at_lte_as_of": True, "lookahead_safe": True}]).to_csv(input_dir / "anti_lookahead_audit.csv", index=False)
        pd.DataFrame([{"hypothesis_id": "h1", "symbol": "TEST", "timeframe": "H4", "cut_number": 1, "persistent_pivots": 7, "candidate_pivots": 1, "superseded_recent": 0, "pivot_set_hash": "p1", "pivot_set_changed": False, "estimated_current_wave": "possible_wave5_active", "display_policy": "show_with_warning"}]).to_csv(input_dir / "stability_audit.csv", index=False)
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "cut_number": 1, "as_of_bar_time": "2026-01-02T00:00:00", "previous_phase": "not_applicable", "current_phase": "possible_wave5_active", "transition_type": "initial_cut", "pivot_set_changed": False, "display_policy": "show_with_warning"}]).to_csv(input_dir / "transition_audit.csv", index=False)
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "current_wave_hypothesis_estimated": "ambiguous", "persistent_estimated_current_wave": "possible_wave5_active", "current_display_policy": "manual_review_only", "persistent_display_policy": "show_with_warning", "current_confirmed_context": "ambiguous", "persistent_confirmed_context": "possible_wave5_active", "comparison_note": "persistent_model_less_restrictive"}]).to_csv(input_dir / "comparison_vs_current_wave_hypothesis.csv", index=False)
        pd.DataFrame([{"severity": "medium", "risk": "wave5_dominance", "description": "synthetic", "recommendation": "synthetic"}]).to_csv(input_dir / "issues_or_risks.csv", index=False)
        (input_dir / "run_meta.json").write_text(json.dumps({"safety": {"real_sql_executed": False, "ddl_executed": False, "mt5_connected": False, "backtests_executed": False, "signals_generated": False}}), encoding="utf-8")
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "estimated_current_wave": "ambiguous", "confirmed_wave_context": "ambiguous", "display_policy": "manual_review_only"}]).to_csv(current_dir / "current_wave_hypothesis.csv", index=False)
        pd.DataFrame([{"config_name": "time_mid_c", "completed_impulse_pct": 0.5}, {"config_name": "time_hard_b", "completed_impulse_pct": 0.5}]).to_csv(grid_dir / "config_comparison_v2.csv", index=False)
        pd.DataFrame([{"example_id": "TEST_H4", "group": "Test", "symbol": "TEST", "timeframe": "H4", "timestamp": "2026-01-01T00:00:00", "open": 100, "high": 101, "low": 99, "close": 100}]).to_csv(source_csv, index=False)


if __name__ == "__main__":
    unittest.main()
