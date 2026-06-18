import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trading_center.wavecount_state_machine import STATE_MACHINE_COLUMNS, StateMachineConfig, build_state_machine


class WaveCountStateMachineTests(unittest.TestCase):
    def test_state_machine_uses_guards_latest_close_and_safety_flags(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cycle_dir = root / "cycle"
            persistent_dir = root / "persistent"
            output_dir = root / "state_machine"
            doc_path = root / "state_machine.md"
            source_csv = root / "source.csv"
            cycle_dir.mkdir()
            persistent_dir.mkdir()
            self._write_cycle_inputs(cycle_dir)
            self._write_persistent_inputs(persistent_dir)
            self._write_source(source_csv)

            result = build_state_machine(
                StateMachineConfig(
                    cycle_dir=cycle_dir,
                    persistent_dir=persistent_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    source_csv=source_csv,
                    generate_charts=False,
                    fresh_lag_bars=24,
                    acceptable_lag_bars=60,
                )
            )

            for filename in [
                "wave_state_machine_hypothesis.csv",
                "wave_state_machine_hypothesis.json",
                "wave_state_transitions.csv",
                "state_guard_audit.csv",
                "freshness_invalidation_audit.csv",
                "comparison_vs_cycle_state.csv",
                "dashboard_display_contract.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_STATE_MACHINE_V0.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            hypotheses = pd.read_csv(output_dir / "wave_state_machine_hypothesis.csv")
            records = json.loads((output_dir / "wave_state_machine_hypothesis.json").read_text(encoding="utf-8"))
            guard = pd.read_csv(output_dir / "state_guard_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(list(hypotheses.columns), STATE_MACHINE_COLUMNS)
            self.assertEqual(len(hypotheses), len(records))
            invalid = hypotheses[hypotheses["symbol"] == "BADSTART"].iloc[0]
            valid = hypotheses[hypotheses["symbol"] == "VALIDSHORT"].iloc[0]
            self.assertEqual(invalid["estimated_current_wave"], "invalidated")
            self.assertEqual(invalid["display_policy"], "manual_review_only")
            self.assertIn("invalid_cycle_start", invalid["transition_blockers"])
            self.assertEqual(valid["estimated_current_wave"], "possible_wave3_active")
            self.assertEqual(valid["display_policy"], "show_with_warning")
            self.assertIn("late_cycle_context", valid["transition_blockers"])
            self.assertTrue(guard["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["is_read_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["can_generate_signal"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(hypotheses["can_filter_trade"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(hypotheses["can_execute_order"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertEqual(result.decision, "wave_state_machine_v0_warning_only")
            self.assertTrue(doc_path.exists())

    @staticmethod
    def _write_cycle_inputs(cycle_dir: Path) -> None:
        rows = [
            cycle_row("BADSTART", "cycle_BADSTART_H4_current", "bad_1", "bad_3", "2026-01-01T00:00:00", "2026-01-10T00:00:00"),
            cycle_row("VALIDSHORT", "cycle_VALIDSHORT_H4_current", "short_1", "short_3", "2026-01-01T00:00:00", "2026-01-10T00:00:00"),
        ]
        pd.DataFrame(rows).to_csv(cycle_dir / "cycle_state_hypothesis.csv", index=False)
        pd.DataFrame(
            [
                {"hypothesis_id": row["hypothesis_id"], "symbol": row["symbol"], "timeframe": row["timeframe"], "lookahead_safe": True}
                for row in rows
            ]
        ).to_csv(cycle_dir / "anti_lookahead_audit.csv", index=False)
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
        rows = []
        rows.extend(
            pivot_rows(
                "BADSTART",
                "bad",
                ["high", "low", "high"],
                [120.0, 110.0, 125.0],
                "2026-01-01T00:00:00",
            )
        )
        rows.extend(
            pivot_rows(
                "VALIDSHORT",
                "short",
                ["high", "low", "high"],
                [120.0, 105.0, 115.0],
                "2026-01-01T00:00:00",
            )
        )
        pd.DataFrame(rows).to_csv(persistent_dir / "persistent_pivots.csv", index=False)

    @staticmethod
    def _write_source(path: Path) -> None:
        rows = []
        for symbol, close in [("BADSTART", 100.0), ("VALIDSHORT", 95.0)]:
            for index in range(3):
                timestamp = pd.Timestamp("2026-03-01T00:00:00") + pd.Timedelta(hours=4 * index)
                rows.append(
                    {
                        "example_id": f"{symbol}_H4",
                        "group": "Test",
                        "symbol": symbol,
                        "timeframe": "H4",
                        "timestamp": timestamp.isoformat(),
                        "open": close + 1.0,
                        "high": close + 2.0,
                        "low": close - 2.0,
                        "close": close,
                    }
                )
        pd.DataFrame(rows).to_csv(path, index=False)


def cycle_row(symbol: str, cycle_id: str, start_uid: str, end_uid: str, start_time: str, last_time: str) -> dict:
    return {
        "hypothesis_id": f"cycle_state_{symbol}",
        "generated_at": "2026-05-27T00:00:00Z",
        "symbol": symbol,
        "market_group": "Test",
        "timeframe": "H4",
        "higher_timeframe": "D1",
        "as_of_bar_time": "2026-03-01T08:00:00",
        "cycle_id": cycle_id,
        "cycle_status": "reset_candidate",
        "cycle_family": "impulse",
        "cycle_start_pivot_uid": start_uid,
        "cycle_end_pivot_uid": end_uid,
        "cycle_pivot_count": 3,
        "cycle_start_time": start_time,
        "cycle_last_pivot_time": last_time,
        "cycle_reset_reason": "total_persistent_pivots_gt_6",
        "previous_cycle_id": f"cycle_{symbol}_previous",
        "estimated_current_wave": "possible_wave3_active",
        "confirmed_wave_context": "possible_wave3_active",
        "next_wave_hypothesis": "possible_wave4",
        "wave_event": "cycle_reset_candidate",
        "wave_event_reason": "total_persistent_pivots_gt_6",
        "freshness_status": "provisional_estimate",
        "wave_stability_status": "provisional",
        "display_policy": "show_with_warning",
        "invalidation_level": 100.0,
        "distance_to_invalidation_pct": 1.0,
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


def pivot_rows(symbol: str, prefix: str, pivot_types: list[str], prices: list[float], start_time: str) -> list[dict]:
    rows = []
    for index, (pivot_type, price) in enumerate(zip(pivot_types, prices), start=1):
        timestamp = pd.Timestamp(start_time) + pd.Timedelta(days=index)
        rows.append(
            {
                "pivot_uid": f"{prefix}_{index}",
                "symbol": symbol,
                "timeframe": "H4",
                "pivot_type": pivot_type,
                "pivot_extreme_time": timestamp.isoformat(),
                "pivot_detected_at": (timestamp + pd.Timedelta(hours=4)).isoformat(),
                "pivot_price": price,
                "pivot_role": "persistent_pivot",
                "is_persistent": True,
                "lookahead_safe": True,
            }
        )
    return rows


if __name__ == "__main__":
    unittest.main()
