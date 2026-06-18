import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trading_center.wavecount_live_estimate import (
    LIVE_ESTIMATE_COLUMNS,
    LiveEstimateConfig,
    build_live_estimate,
)


class WaveCountLiveEstimateTests(unittest.TestCase):
    def test_live_estimate_generates_safe_provisional_contract(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state_machine"
            cycle_dir = root / "cycle"
            persistent_dir = root / "persistent"
            output_dir = root / "live_estimate"
            doc_path = root / "live_estimate.md"
            source_csv = root / "source_ohlc.csv"
            state_dir.mkdir()
            cycle_dir.mkdir()
            persistent_dir.mkdir()

            self._write_state_machine(state_dir)
            self._write_cycle_state(cycle_dir)
            self._write_persistent_pivots(persistent_dir)
            self._write_source(source_csv)

            result = build_live_estimate(
                LiveEstimateConfig(
                    state_machine_dir=state_dir,
                    cycle_dir=cycle_dir,
                    persistent_dir=persistent_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    source_csv=source_csv,
                    generate_charts=False,
                )
            )

            for filename in [
                "live_wave_estimate.csv",
                "live_wave_estimate.json",
                "current_leg_audit.csv",
                "estimate_rule_audit.csv",
                "anti_lookahead_audit.csv",
                "confidence_warning_audit.csv",
                "comparison_vs_state_machine.csv",
                "dashboard_display_contract.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_LIVE_ESTIMATE_V0.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            frame = pd.read_csv(output_dir / "live_wave_estimate.csv")
            records = json.loads((output_dir / "live_wave_estimate.json").read_text(encoding="utf-8"))
            rules = pd.read_csv(output_dir / "estimate_rule_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(list(frame.columns), LIVE_ESTIMATE_COLUMNS)
            self.assertEqual(len(frame), len(records))
            self.assertIn("live_estimated_wave", frame.columns)
            self.assertIn("confirmed_wave_context", frame.columns)
            self.assertIn("current_leg_direction", frame.columns)
            self.assertIn("current_leg_status", frame.columns)
            self.assertTrue(frame["why_this_label"].astype(str).str.len().gt(0).all())
            self.assertTrue(frame["why_not_higher_confidence"].astype(str).str.len().gt(0).all())

            invalid = frame[frame["symbol"] == "INVALID"].iloc[0]
            active = frame[frame["symbol"] == "ACTIVE"].iloc[0]
            candidate = frame[frame["symbol"] == "CANDIDATE"].iloc[0]
            pullback = frame[frame["symbol"] == "PULLBACK"].iloc[0]

            self.assertEqual(invalid["live_estimated_wave"], "invalidated")
            self.assertEqual(invalid["display_policy"], "manual_review_only")
            self.assertEqual(active["live_estimated_wave"], "possible_wave3_active")
            self.assertEqual(active["current_leg_status"], "impulse_attempt")
            self.assertEqual(float(active["latest_close"]), 122.0)
            self.assertEqual(candidate["live_estimated_wave"], "possible_wave3_candidate")
            self.assertEqual(candidate["display_policy"], "show_live_estimate_with_warning")
            self.assertEqual(pullback["live_estimated_wave"], "possible_wave3_active")
            self.assertEqual(pullback["current_leg_status"], "pullback")
            self.assertIn("pullback", str(pullback["why_not_higher_confidence"]))

            self.assertTrue(frame["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(frame["is_read_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(frame["can_generate_signal"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(frame["can_filter_trade"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(frame["can_execute_order"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(rules["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertEqual(result.decision, "live_estimate_v0_promising_for_visual_review")
            self.assertTrue(doc_path.exists())

    def _write_state_machine(self, root: Path) -> None:
        rows = [
            self._state_row("INVALID", "possible_wave3_candidate", "long", activation=120.0, invalidation=90.0),
            self._state_row("ACTIVE", "possible_wave3_candidate", "long", activation=120.0, invalidation=90.0),
            self._state_row("CANDIDATE", "possible_wave3_candidate", "long", activation=120.0, invalidation=90.0),
            self._state_row("PULLBACK", "possible_wave3_active", "long", activation=140.0, invalidation=90.0),
        ]
        pd.DataFrame(rows).to_csv(root / "wave_state_machine_hypothesis.csv", index=False)
        (root / "run_meta.json").write_text(
            json.dumps(
                {
                    "safety": {
                        "real_sql_executed": False,
                        "ddl_executed": False,
                        "mt5_connected": False,
                        "backtests_executed": False,
                        "signals_generated": False,
                    }
                }
            ),
            encoding="utf-8",
        )

    def _state_row(self, symbol: str, wave: str, direction: str, *, activation: float, invalidation: float) -> dict:
        return {
            "state_machine_id": f"state_{symbol}",
            "generated_at": "2026-05-27T00:00:00Z",
            "symbol": symbol,
            "market_group": "Synthetic",
            "timeframe": "H4",
            "higher_timeframe": "D1",
            "as_of_bar_time": "2026-01-05T00:00:00",
            "cycle_id": f"cycle_{symbol}",
            "estimated_current_wave": wave,
            "confirmed_wave_context": f"{wave}_late",
            "next_wave_hypothesis": "not_available",
            "activation_level": activation,
            "invalidation_level": invalidation,
            "display_policy": "show_with_warning",
            "transition_blockers": "late_cycle_context",
            "payload_json": json.dumps({"direction": direction}),
        }

    def _write_cycle_state(self, root: Path) -> None:
        rows = []
        for symbol in ["INVALID", "ACTIVE", "CANDIDATE", "PULLBACK"]:
            rows.append(
                {
                    "cycle_id": f"cycle_{symbol}",
                    "symbol": symbol,
                    "timeframe": "H4",
                    "higher_timeframe": "D1",
                    "as_of_bar_time": "2026-01-05T00:00:00",
                    "cycle_start_pivot_uid": f"{symbol}_p1",
                    "cycle_end_pivot_uid": f"{symbol}_p3",
                }
            )
        pd.DataFrame(rows).to_csv(root / "cycle_state_hypothesis.csv", index=False)

    def _write_persistent_pivots(self, root: Path) -> None:
        rows = []
        pivot_sets = {
            "INVALID": [("low", 100.0), ("high", 115.0), ("low", 95.0)],
            "ACTIVE": [("low", 100.0), ("high", 112.0), ("low", 104.0)],
            "CANDIDATE": [("low", 100.0), ("high", 112.0), ("low", 104.0)],
            "PULLBACK": [("high", 110.0), ("low", 100.0), ("high", 130.0)],
        }
        times = ["2026-01-01T00:00:00", "2026-01-02T00:00:00", "2026-01-03T00:00:00"]
        for symbol, pivots in pivot_sets.items():
            for index, ((pivot_type, price), time_text) in enumerate(zip(pivots, times), start=1):
                rows.append(
                    {
                        "pivot_uid": f"{symbol}_p{index}",
                        "symbol": symbol,
                        "timeframe": "H4",
                        "pivot_type": pivot_type,
                        "pivot_extreme_time": time_text,
                        "pivot_detected_at": time_text,
                        "pivot_price": price,
                        "pivot_role": "persistent_pivot",
                        "is_persistent": True,
                        "lookahead_safe": True,
                    }
                )
        pd.DataFrame(rows).to_csv(root / "persistent_pivots.csv", index=False)

    def _write_source(self, path: Path) -> None:
        latest = {
            "INVALID": 80.0,
            "ACTIVE": 122.0,
            "CANDIDATE": 112.0,
            "PULLBACK": 120.0,
        }
        rows = []
        for symbol, close in latest.items():
            rows.append(self._ohlc_row(symbol, "2026-01-04T20:00:00", close - 1.0))
            rows.append(self._ohlc_row(symbol, "2026-01-05T00:00:00", close))
            rows.append(self._ohlc_row(symbol, "2026-01-05T04:00:00", 999.0))
        pd.DataFrame(rows).to_csv(path, index=False)

    def _ohlc_row(self, symbol: str, timestamp: str, close: float) -> dict:
        return {
            "example_id": f"{symbol}_{timestamp}",
            "group": "Synthetic",
            "symbol": symbol,
            "timeframe": "H4",
            "timestamp": timestamp,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        }


if __name__ == "__main__":
    unittest.main()
