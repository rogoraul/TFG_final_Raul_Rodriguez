import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_cycle_state_visual_audit import (
    CycleStateVisualAuditConfig,
    build_cycle_state_visual_audit,
)


class WaveCountCycleStateVisualAuditTests(unittest.TestCase):
    def test_cycle_state_visual_audit_generates_non_operational_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cycle_dir = root / "cycle"
            persistent_dir = root / "persistent"
            output_dir = root / "audit"
            doc_path = root / "audit.md"
            cycle_dir.mkdir()
            persistent_dir.mkdir()
            self._write_cycle_inputs(cycle_dir)
            self._write_persistent_inputs(persistent_dir)

            result = build_cycle_state_visual_audit(
                CycleStateVisualAuditConfig(
                    cycle_dir=cycle_dir,
                    persistent_dir=persistent_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    source_csv=root / "missing_ohlc.csv",
                    generate_charts=False,
                )
            )

            for filename in [
                "contract_security_audit.csv",
                "cycle_reset_visual_audit.csv",
                "cycle_reset_diagnosis.csv",
                "wave3_relabel_audit.csv",
                "staleness_audit.csv",
                "model_comparison_audit.csv",
                "design_diagnosis.csv",
                "issues_or_risks.csv",
                "decision_summary.csv",
                "run_meta.json",
                "WAVECOUNT_CYCLE_STATE_VISUAL_AUDIT.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            decision = pd.read_csv(output_dir / "decision_summary.csv")
            wave3 = pd.read_csv(output_dir / "wave3_relabel_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(decision.loc[0, "decision"], "needs_wave_state_machine")
            self.assertEqual(result.decision, "needs_wave_state_machine")
            self.assertTrue(wave3["tail3_forces_wave3_risk"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())

    @staticmethod
    def _write_cycle_inputs(cycle_dir: Path) -> None:
        as_of = "2026-03-17T04:00:00"
        cycle_row = {
            "hypothesis_id": "cycle_state_v0_TEST_H4",
            "generated_at": "2026-05-27T00:00:00Z",
            "symbol": "TEST",
            "market_group": "Test",
            "timeframe": "H4",
            "higher_timeframe": "D1",
            "as_of_bar_time": as_of,
            "cycle_id": "cycle_TEST_H4_current",
            "cycle_status": "reset_candidate",
            "cycle_family": "impulse",
            "cycle_start_pivot_uid": "pivot_5",
            "cycle_end_pivot_uid": "pivot_7",
            "cycle_pivot_count": 3,
            "cycle_start_time": "2026-01-01T00:00:00",
            "cycle_last_pivot_time": "2026-01-10T00:00:00",
            "cycle_reset_reason": "total_persistent_pivots_gt_6;cycle_tail_re_evaluated",
            "previous_cycle_id": "cycle_TEST_H4_previous",
            "estimated_current_wave": "possible_wave3_active",
            "confirmed_wave_context": "possible_wave3_active",
            "next_wave_hypothesis": "possible_wave4",
            "wave_event": "cycle_reset_candidate",
            "wave_event_reason": "total_persistent_pivots_gt_6",
            "freshness_status": "provisional_estimate",
            "wave_stability_status": "provisional",
            "display_policy": "show_with_warning",
            "invalidation_level": 100,
            "distance_to_invalidation_pct": 1,
            "lookahead_safe": True,
            "is_read_only": True,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
            "source": "test",
            "data_origin": "test_fixture",
            "method_version": "test",
            "notes": "synthetic",
            "payload_json": "{}",
        }
        pd.DataFrame([cycle_row]).to_csv(cycle_dir / "cycle_state_hypothesis.csv", index=False)
        (cycle_dir / "cycle_state_hypothesis.json").write_text(json.dumps([cycle_row]), encoding="utf-8")
        pd.DataFrame(
            [
                {"cycle_id": "cycle_TEST_H4_previous", "symbol": "TEST", "timeframe": "H4", "cycle_status": "completed_candidate", "cycle_family": "impulse", "cycle_pivot_count": 4},
                {"cycle_id": "cycle_TEST_H4_current", "symbol": "TEST", "timeframe": "H4", "cycle_status": "reset_candidate", "cycle_family": "impulse", "cycle_pivot_count": 3},
            ]
        ).to_csv(cycle_dir / "cycle_registry.csv", index=False)
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "event": "pivot_accepted"}]).to_csv(cycle_dir / "cycle_transitions.csv", index=False)
        pd.DataFrame(
            [
                {
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "as_of_bar_time": as_of,
                    "previous_cycle_id": "cycle_TEST_H4_previous",
                    "new_cycle_id": "cycle_TEST_H4_current",
                    "total_persistent_pivots": 7,
                    "current_cycle_pivots": 3,
                    "reset_reason": "total_persistent_pivots_gt_6",
                    "lookahead_safe": True,
                }
            ]
        ).to_csv(cycle_dir / "cycle_reset_audit.csv", index=False)
        pd.DataFrame([{"symbol": "TEST", "timeframe": "H4", "from_state": "cycle_possible_wave2", "to_state": "cycle_possible_wave3_active"}]).to_csv(
            cycle_dir / "wave_state_machine_audit.csv", index=False
        )
        pd.DataFrame(
            [
                {
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "persistent_estimated_current_wave": "possible_wave5_active",
                    "cycle_estimated_current_wave": "possible_wave3_active",
                    "persistent_display_policy": "show_with_warning",
                    "cycle_display_policy": "show_with_warning",
                    "persistent_pivot_count": 7,
                    "cycle_pivot_count": 3,
                    "cycle_status": "reset_candidate",
                    "wave5_reduced": True,
                    "comparison_note": "cycle_reset_reduced_wave5",
                }
            ]
        ).to_csv(cycle_dir / "comparison_vs_persistent_hypothesis.csv", index=False)
        pd.DataFrame([{"hypothesis_id": "cycle_state_v0_TEST_H4", "symbol": "TEST", "timeframe": "H4", "lookahead_safe": True}]).to_csv(
            cycle_dir / "anti_lookahead_audit.csv", index=False
        )
        (cycle_dir / "run_meta.json").write_text(
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
        pivot_types = ["low", "high", "low", "high", "high", "low", "high"]
        prices = [100, 110, 102, 112, 115, 105, 118]
        rows = []
        for index, (pivot_type, price) in enumerate(zip(pivot_types, prices), start=1):
            timestamp = pd.Timestamp("2025-12-01T00:00:00") + pd.Timedelta(days=index)
            rows.append(
                {
                    "pivot_uid": f"pivot_{index}",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "pivot_type": pivot_type,
                    "pivot_extreme_time": timestamp.isoformat(),
                    "pivot_detected_at": (timestamp + pd.Timedelta(hours=4)).isoformat(),
                    "pivot_price": price,
                    "pivot_role": "persistent_pivot",
                    "is_persistent": True,
                }
            )
        pd.DataFrame(rows).to_csv(persistent_dir / "persistent_pivots.csv", index=False)
        pd.DataFrame(
            [
                {
                    "hypothesis_id": "persistent_TEST_H4",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "estimated_current_wave": "possible_wave5_active",
                    "persistent_pivot_count": 7,
                }
            ]
        ).to_csv(persistent_dir / "persistent_wave_hypothesis.csv", index=False)


if __name__ == "__main__":
    unittest.main()
