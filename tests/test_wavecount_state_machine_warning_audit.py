import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_state_machine_warning_audit import WarningAuditConfig, build_warning_audit


class WaveCountStateMachineWarningAuditTests(unittest.TestCase):
    def test_warning_audit_classifies_late_context_as_study_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            persistent_dir = root / "persistent"
            output_dir = root / "audit"
            doc_path = root / "audit.md"
            source_csv = root / "source.csv"
            state_dir.mkdir()
            persistent_dir.mkdir()
            self._write_state_machine_inputs(state_dir)
            self._write_persistent_inputs(persistent_dir)
            self._write_source(source_csv)

            result = build_warning_audit(
                WarningAuditConfig(
                    state_machine_dir=state_dir,
                    persistent_dir=persistent_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    source_csv=source_csv,
                    generate_charts=False,
                    max_main_dashboard_lag_bars=60,
                    max_study_panel_lag_bars=240,
                )
            )

            for filename in [
                "warning_case_audit.csv",
                "warning_visual_audit.csv",
                "freshness_gate_audit.csv",
                "dashboard_policy_decision.csv",
                "model_limitations.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_STATE_MACHINE_WARNING_AUDIT.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            policy = pd.read_csv(output_dir / "dashboard_policy_decision.csv")
            freshness = pd.read_csv(output_dir / "freshness_gate_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(result.decision, "late_wave_context_study_panel_only")
            self.assertFalse(policy.loc[0, "main_dashboard_current_wave_allowed"])
            self.assertTrue(policy.loc[0, "study_panel_allowed"])
            self.assertFalse(policy.loc[0, "telegram_allowed"])
            self.assertFalse(policy.loc[0, "bot_allowed"])
            self.assertEqual(freshness.loc[0, "freshness_gate"], "study_panel_candidate")
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())

    @staticmethod
    def _write_state_machine_inputs(state_dir: Path) -> None:
        hypothesis = {
            "state_machine_id": "wave_state_machine_TEST_H4",
            "generated_at": "2026-05-27T00:00:00Z",
            "symbol": "TEST",
            "market_group": "Test",
            "timeframe": "H4",
            "higher_timeframe": "D1",
            "as_of_bar_time": "2026-03-17T04:00:00",
            "cycle_id": "cycle_TEST_current",
            "cycle_status": "reset_candidate",
            "cycle_family": "impulse",
            "state_machine_state": "cycle_possible_wave3_active",
            "estimated_current_wave": "possible_wave3_active",
            "confirmed_wave_context": "possible_wave3_active_late",
            "next_wave_hypothesis": "possible_wave4",
            "transition_path": "cycle_forming_wave1->cycle_possible_wave2->cycle_possible_wave3_active",
            "transition_blockers": "late_cycle_context",
            "cycle_start_valid": True,
            "latest_close_confirms_active": True,
            "latest_close_time": "2026-03-17T04:00:00",
            "latest_close": 95.0,
            "activation_level": 100.0,
            "invalidation_level": 120.0,
            "distance_to_invalidation_pct": 26.3158,
            "context_freshness_status": "late",
            "freshness_status": "confirmed_late",
            "wave_stability_status": "confirmed_late",
            "display_policy": "show_with_warning",
            "manual_review_reason": "late_cycle_context",
            "lookahead_safe": True,
            "is_read_only": True,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
            "source": "test",
            "data_origin": "test_fixture",
            "method_version": "test",
            "notes": "synthetic",
            "payload_json": json.dumps({"direction": "short"}),
        }
        pd.DataFrame([hypothesis]).to_csv(state_dir / "wave_state_machine_hypothesis.csv", index=False)
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "event": "latest_close_activation"}]).to_csv(
            state_dir / "wave_state_transitions.csv", index=False
        )
        pd.DataFrame(
            [
                {
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "as_of_bar_time": "2026-03-17T04:00:00",
                    "cycle_start_valid": True,
                    "structure_alternates": True,
                    "latest_close_safe": True,
                    "latest_close_confirms_active": True,
                    "invalidated": False,
                    "transition_blockers": "late_cycle_context",
                    "lookahead_safe": True,
                }
            ]
        ).to_csv(state_dir / "state_guard_audit.csv", index=False)
        pd.DataFrame(
            [
                {
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "as_of_bar_time": "2026-03-17T04:00:00",
                    "cycle_last_pivot_time": "2026-02-10T04:00:00",
                    "latest_close_time": "2026-03-17T04:00:00",
                    "lag_h4_bars_since_last_cycle_pivot": 210.0,
                    "context_freshness_status": "late",
                    "display_policy": "show_with_warning",
                    "interpretation": "late",
                }
            ]
        ).to_csv(state_dir / "freshness_invalidation_audit.csv", index=False)
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "comparison_note": "state_machine_keeps_context"}]).to_csv(
            state_dir / "comparison_vs_cycle_state.csv", index=False
        )
        (state_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "safety": {
                        "real_sql_executed": False,
                        "ddl_executed": False,
                        "mt5_connected": False,
                        "backtests_executed": False,
                        "signals_generated": False,
                        "dashboard_implemented": False,
                        "telegram_implemented": False,
                        "bot_implemented": False,
                    }
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_persistent_inputs(persistent_dir: Path) -> None:
        pd.DataFrame(
            [
                {
                    "pivot_uid": "pivot_1",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "pivot_type": "high",
                    "pivot_extreme_time": "2026-01-01T00:00:00",
                    "pivot_detected_at": "2026-01-01T04:00:00",
                    "pivot_price": 120.0,
                    "pivot_role": "persistent_pivot",
                    "is_persistent": True,
                }
            ]
        ).to_csv(persistent_dir / "persistent_pivots.csv", index=False)

    @staticmethod
    def _write_source(path: Path) -> None:
        pd.DataFrame(
            [
                {
                    "example_id": "TEST_H4",
                    "group": "Test",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "timestamp": "2026-03-17T04:00:00",
                    "open": 96.0,
                    "high": 98.0,
                    "low": 94.0,
                    "close": 95.0,
                }
            ]
        ).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
