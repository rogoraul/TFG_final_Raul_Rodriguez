import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trading_center.wavecount_cycle_state import CYCLE_STATE_COLUMNS, CycleStateConfig, build_cycle_state


class WaveCountCycleStateTests(unittest.TestCase):
    def test_cycle_state_resets_long_persistent_sequence_without_operational_flags(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "persistent"
            output_dir = root / "cycle"
            doc_path = root / "cycle_state.md"
            input_dir.mkdir()
            self._write_persistent_inputs(input_dir)

            result = build_cycle_state(
                CycleStateConfig(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    source_csv=root / "missing_ohlc.csv",
                    generate_charts=False,
                    max_cycle_pivots=6,
                    active_tail_pivots=3,
                )
            )

            for filename in [
                "cycle_state_hypothesis.csv",
                "cycle_state_hypothesis.json",
                "cycle_registry.csv",
                "cycle_transitions.csv",
                "cycle_reset_audit.csv",
                "wave_state_machine_audit.csv",
                "comparison_vs_persistent_hypothesis.csv",
                "anti_lookahead_audit.csv",
                "dashboard_display_contract.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_CYCLE_STATE_V0.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            hypotheses = pd.read_csv(output_dir / "cycle_state_hypothesis.csv")
            records = json.loads((output_dir / "cycle_state_hypothesis.json").read_text(encoding="utf-8"))
            reset = pd.read_csv(output_dir / "cycle_reset_audit.csv")
            transitions = pd.read_csv(output_dir / "cycle_transitions.csv")
            machine = pd.read_csv(output_dir / "wave_state_machine_audit.csv")
            anti = pd.read_csv(output_dir / "anti_lookahead_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(len(hypotheses), len(records))
            self.assertEqual(list(hypotheses.columns), CYCLE_STATE_COLUMNS)
            self.assertEqual(hypotheses.loc[0, "cycle_status"], "reset_candidate")
            self.assertEqual(hypotheses.loc[0, "cycle_family"], "impulse")
            self.assertIn("cycle_id", hypotheses.columns)
            self.assertIn("estimated_current_wave", hypotheses.columns)
            self.assertNotEqual(hypotheses.loc[0, "estimated_current_wave"], "possible_wave5_active")
            self.assertNotEqual(hypotheses.loc[0, "estimated_current_wave"], "completed_impulse_candidate")
            self.assertEqual(int(hypotheses.loc[0, "cycle_pivot_count"]), 3)
            self.assertFalse(reset.empty)
            self.assertFalse(transitions.empty)
            self.assertFalse(machine.empty)
            self.assertTrue(anti["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["is_read_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["can_generate_signal"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(hypotheses["can_filter_trade"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(hypotheses["can_execute_order"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertEqual(result.decision, "cycle_state_v0_promising_for_visual_review")
            self.assertTrue(doc_path.exists())

    @staticmethod
    def _write_persistent_inputs(input_dir: Path) -> None:
        as_of = pd.Timestamp("2026-01-02T12:00:00")
        pd.DataFrame(
            [
                {
                    "hypothesis_id": "persistent_TEST_H4_latest",
                    "generated_at": "2026-01-02T00:00:00Z",
                    "symbol": "TEST",
                    "market_group": "Test",
                    "timeframe": "H4",
                    "higher_timeframe": "D1",
                    "cut_number": 1,
                    "as_of_bar_time": as_of.isoformat(),
                    "estimated_current_wave": "possible_wave5_active",
                    "confirmed_wave_context": "possible_wave5_candidate",
                    "next_wave_hypothesis": "completed_impulse_candidate",
                    "hypothesis_status": "provisional",
                    "freshness_status": "provisional_estimate",
                    "wave_stability_status": "provisional",
                    "display_policy": "show_with_warning",
                    "invalidation_level": 100.0,
                    "distance_to_invalidation_pct": 1.0,
                    "last_persistent_pivot_at": "2026-01-01T20:00:00",
                    "last_candidate_pivot_at": "",
                    "persistent_pivot_count": 7,
                    "candidate_pivot_count": 0,
                    "superseded_pivot_count": 0,
                    "wave_event": "wave_matured",
                    "wave_event_reason": "persistent_sequence_count",
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
            ]
        ).to_csv(input_dir / "persistent_wave_hypothesis.csv", index=False)

        pivot_rows = []
        pivot_types = ["low", "high", "low", "high", "low", "high", "low"]
        prices = [100, 105, 101, 108, 102, 107, 104]
        for index, (pivot_type, price) in enumerate(zip(pivot_types, prices), start=1):
            timestamp = pd.Timestamp("2026-01-01T00:00:00") + pd.Timedelta(hours=4 * index)
            detected = timestamp + pd.Timedelta(hours=4)
            pivot_rows.append(
                {
                    "pivot_uid": f"pivot_{index}",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "pivot_type": pivot_type,
                    "pivot_extreme_time": timestamp.isoformat(),
                    "pivot_detected_at": detected.isoformat(),
                    "pivot_price": price,
                    "pivot_role": "persistent_pivot",
                    "first_seen_at": detected.isoformat(),
                    "last_seen_at": as_of.isoformat(),
                    "accepted_at": detected.isoformat(),
                    "superseded_at": "",
                    "superseded_by": "",
                    "persistence_cuts": 2,
                    "is_persistent": True,
                    "is_current_candidate": False,
                    "rejection_reason": "",
                    "lookahead_safe": True,
                }
            )
        pd.DataFrame(pivot_rows).to_csv(input_dir / "persistent_pivots.csv", index=False)

        pd.DataFrame(
            [
                {
                    "hypothesis_id": "persistent_TEST_H4_latest",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "as_of_bar_time": as_of.isoformat(),
                    "lookahead_safe": True,
                }
            ]
        ).to_csv(input_dir / "anti_lookahead_audit.csv", index=False)
        (input_dir / "run_meta.json").write_text(
            json.dumps({"safety": {"real_sql_executed": False, "backtests_executed": False}}),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
