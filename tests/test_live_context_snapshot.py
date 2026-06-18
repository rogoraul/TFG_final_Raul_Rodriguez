import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from trading_center.live_context_snapshot import LiveContextSnapshotConfig, build_live_context_snapshot
from trading_center.snapshot_schema import SNAPSHOT_COLUMNS


class TestLiveContextSnapshot(unittest.TestCase):
    def test_generates_snapshot_without_order_intents_and_keeps_hard_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_dir = self._write_watcher_outputs(root, [
                self._watcher_row(signal_state="watching_setup", reason="waiting_for_trendline_and_macd_confirmation")
            ])

            result = build_live_context_snapshot(self._config(root, watcher_dir))

            self.assertEqual(len(result.snapshot), 1)
            self.assertTrue((root / "out" / "live_context_snapshot.csv").exists())
            self.assertTrue((root / "out" / "live_context_snapshot.json").exists())
            self.assertTrue((root / "out" / "run_meta.json").exists())
            for column in SNAPSHOT_COLUMNS:
                self.assertIn(column, result.snapshot.columns)
            row = result.snapshot.iloc[0]
            self.assertFalse(bool(row["has_order_intent"]))
            self.assertEqual(row["riskguard_status"], "not_evaluated")
            self.assertFalse(bool(row["can_execute_order"]))
            self.assertTrue(bool(row["is_read_only"]))
            self.assertFalse(bool(row["wavecount_should_filter_trade"]))
            self.assertEqual(row["dry_run_action"], "watch_only")

            payload = json.loads((root / "out" / "live_context_snapshot.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload), len(result.snapshot))

    def test_missing_wavecount_does_not_block_enbolsa_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_dir = self._write_watcher_outputs(root, [self._watcher_row(symbol="GBPJPY.r")])

            result = build_live_context_snapshot(self._config(root, watcher_dir))

            row = result.snapshot.iloc[0]
            self.assertFalse(bool(row["wavecount_available"]))
            self.assertEqual(row["wavecount_context_status"], "not_available")
            self.assertEqual(row["wavecount_wave_role"], "not_available")
            self.assertFalse(bool(row["can_execute_order"]))

    def test_ready_stale_is_not_dry_run_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_dir = self._write_watcher_outputs(root, [
                self._watcher_row(signal_state="ready_stale", reason="signal_started_on_previous_bar")
            ])

            result = build_live_context_snapshot(self._config(root, watcher_dir))

            row = result.snapshot.iloc[0]
            self.assertEqual(row["intent_status"], "stale")
            self.assertFalse(bool(row["dry_run_eligible"]))
            self.assertEqual(row["dry_run_action"], "none")
            self.assertFalse(bool(row["can_execute_order"]))

    def test_riskguard_rejection_is_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_key = "enbolsa:macd_breakout|EURUSD.r|H1:H4|BUY|42|2026-01-01T00:00:00"
            watcher_dir = self._write_watcher_outputs(
                root,
                [
                    self._watcher_row(
                        symbol="EURUSD.r",
                        signal_state="entry_ready_new",
                        event_key=event_key,
                        riskguard_accepted=False,
                        riskguard_reason="total_open_risk_cap",
                        riskguard_detail="total 6.00% > 5.00%",
                    )
                ],
                order_intents=[
                    {
                        "event_key": event_key,
                        "symbol": "EURUSD.r",
                        "timestamp": "2026-01-01 00:00:00",
                        "side": "BUY",
                        "entry": 1.1,
                        "sl": 1.0,
                        "tp1": 1.2,
                        "tp2": 1.3,
                        "risk_pct": 1.0,
                        "strategy": "enbolsa:macd_breakout",
                        "riskguard_accepted": False,
                        "riskguard_reason": "total_open_risk_cap",
                        "riskguard_detail": "total 6.00% > 5.00%",
                    }
                ],
                riskguard_decisions=[
                    {
                        "accepted": False,
                        "reason": "total_open_risk_cap",
                        "detail": "total 6.00% > 5.00%",
                        "strategy": "enbolsa:macd_breakout",
                        "symbol": "EURUSD.r",
                        "side": "BUY",
                        "setup_id": "42",
                        "timestamp": "2026-01-01 00:00:00",
                        "risk_amount": 100.0,
                        "risk_pct": 1.0,
                        "current": "{}",
                        "projected": json.dumps({
                            "total_open_risk_pct": 6.0,
                            "symbol_open_risk_pct": {"EURUSD.r": 1.0},
                            "currency_exposure": {
                                "EUR": {"gross_risk_pct": 1.0, "abs_net_risk_pct": 1.0},
                                "USD": {"gross_risk_pct": 3.5, "abs_net_risk_pct": 2.5},
                            },
                        }),
                    }
                ],
            )

            result = build_live_context_snapshot(self._config(root, watcher_dir))

            row = result.snapshot.iloc[0]
            self.assertTrue(bool(row["has_order_intent"]))
            self.assertEqual(row["intent_status"], "riskguard_rejected")
            self.assertEqual(row["riskguard_status"], "riskguard_rejected")
            self.assertEqual(row["riskguard_reason"], "total_open_risk_cap")
            self.assertEqual(float(row["projected_total_risk_pct"]), 6.0)
            self.assertEqual(float(row["projected_symbol_risk_pct"]), 1.0)
            self.assertEqual(float(row["projected_currency_gross_risk_pct"]), 3.5)
            self.assertEqual(float(row["projected_currency_net_risk_pct"]), 2.5)
            self.assertEqual(row["dry_run_action"], "would_reject")
            self.assertFalse(bool(row["can_execute_order"]))

    def test_riskguard_acceptance_never_enables_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_key = "enbolsa:macd_breakout|EURUSD.r|H1:H4|BUY|42|2026-01-01T00:00:00"
            watcher_dir = self._write_watcher_outputs(
                root,
                [
                    self._watcher_row(
                        symbol="EURUSD.r",
                        signal_state="entry_ready_new",
                        event_key=event_key,
                        riskguard_accepted=True,
                        riskguard_reason="accepted",
                        riskguard_detail="RiskGuard limits respected.",
                    )
                ],
                order_intents=[
                    {
                        "event_key": event_key,
                        "symbol": "EURUSD.r",
                        "timestamp": "2026-01-01 00:00:00",
                        "side": "BUY",
                        "entry": 1.1,
                        "sl": 1.0,
                        "tp1": 1.2,
                        "tp2": 1.3,
                        "risk_pct": 1.0,
                        "strategy": "enbolsa:macd_breakout",
                        "riskguard_accepted": True,
                        "riskguard_reason": "accepted",
                        "riskguard_detail": "RiskGuard limits respected.",
                    }
                ],
            )

            result = build_live_context_snapshot(self._config(root, watcher_dir))

            row = result.snapshot.iloc[0]
            self.assertEqual(row["intent_status"], "riskguard_accepted")
            self.assertEqual(row["riskguard_status"], "riskguard_accepted")
            self.assertEqual(row["dry_run_action"], "would_accept")
            self.assertTrue(bool(row["dry_run_eligible"]))
            self.assertFalse(bool(row["can_execute_order"]))
            self.assertTrue(bool(row["is_read_only"]))

    def test_wavecount_context_uses_official_policy_without_filtering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_dir = self._write_watcher_outputs(root, [self._watcher_row(symbol="AUDJPY.r")])
            policy_dir = root / "wavecount_256"
            (policy_dir / "tables").mkdir(parents=True)
            pd.DataFrame([
                {
                    "candidate_id": "candidate-audjpy",
                    "source_scope": "h4_d1",
                    "group": "Forex Majors",
                    "symbol": "AUDJPY.r",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "direction": "bullish",
                    "review_category": "impulse",
                    "phase256_policy_bucket": "high_quality_structure",
                    "phase256_score": 100,
                    "phase256_adjustment_reason": "no_change",
                    "policy_warnings": "",
                    "phase256_prominence_action": "no_change",
                }
            ]).to_csv(policy_dir / "tables" / "phase256_policy_scores.csv", index=False)

            result = build_live_context_snapshot(self._config(root, watcher_dir, policy_dir=policy_dir))

            row = result.snapshot.iloc[0]
            self.assertTrue(bool(row["wavecount_available"]))
            self.assertEqual(row["wavecount_primary_timeframe"], "H4")
            self.assertEqual(row["wavecount_degree"], "intermediate")
            self.assertEqual(row["wavecount_policy_bucket"], "high_quality_structure")
            self.assertEqual(row["wavecount_context_status"], "supports_context")
            self.assertFalse(bool(row["wavecount_should_filter_trade"]))
            self.assertFalse(bool(row["can_execute_order"]))

    def test_wavecount_excluded_bucket_remains_non_blocking_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_dir = self._write_watcher_outputs(root, [self._watcher_row(symbol="AUDJPY.r")])
            policy_dir = root / "wavecount_256"
            (policy_dir / "tables").mkdir(parents=True)
            pd.DataFrame([
                {
                    "candidate_id": "candidate-audjpy-excluded",
                    "source_scope": "h4_d1",
                    "group": "Forex Majors",
                    "symbol": "AUDJPY.r",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "direction": "bullish",
                    "review_category": "impulse",
                    "phase256_policy_bucket": "exclude_from_guided_search",
                    "phase256_score": 20,
                    "phase256_adjustment_reason": "excluded",
                    "policy_warnings": "",
                    "phase256_prominence_action": "keep",
                }
            ]).to_csv(policy_dir / "tables" / "phase256_policy_scores.csv", index=False)

            result = build_live_context_snapshot(self._config(root, watcher_dir, policy_dir=policy_dir))

            row = result.snapshot.iloc[0]
            self.assertTrue(bool(row["wavecount_available"]))
            self.assertEqual(row["wavecount_policy_bucket"], "exclude_from_guided_search")
            self.assertEqual(row["wavecount_context_status"], "neutral_context")
            self.assertEqual(row["dry_run_action"], "watch_only")
            self.assertFalse(bool(row["wavecount_should_filter_trade"]))
            self.assertFalse(bool(row["can_execute_order"]))

    def test_wavecount_direction_conflict_is_context_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_dir = self._write_watcher_outputs(root, [self._watcher_row(symbol="AUDJPY.r", side="SELL")])
            policy_dir = root / "wavecount_256"
            (policy_dir / "tables").mkdir(parents=True)
            pd.DataFrame([
                {
                    "candidate_id": "candidate-audjpy",
                    "source_scope": "h4_d1",
                    "group": "Forex Majors",
                    "symbol": "AUDJPY.r",
                    "timeframe": "H4",
                    "swing_degree": "intermediate",
                    "direction": "bullish",
                    "review_category": "impulse",
                    "phase256_policy_bucket": "high_quality_structure",
                    "phase256_score": 100,
                    "phase256_adjustment_reason": "no_change",
                    "policy_warnings": "",
                    "phase256_prominence_action": "no_change",
                }
            ]).to_csv(policy_dir / "tables" / "phase256_policy_scores.csv", index=False)

            result = build_live_context_snapshot(self._config(root, watcher_dir, policy_dir=policy_dir))

            row = result.snapshot.iloc[0]
            self.assertEqual(row["wavecount_context_status"], "conflicting_context")
            self.assertFalse(bool(row["wavecount_should_filter_trade"]))
            self.assertFalse(bool(row["can_execute_order"]))

    def test_current_repo_artifacts_generate_contract_stable_snapshot(self):
        watcher_dir = Path("artifacts/live-signal-watcher/enbolsa_macd_breakout_v0")
        contract_path = Path("artifacts/tfg/operational_integration_design_2026-05-25/tables/live_context_snapshot_contract.csv")
        if not watcher_dir.exists() or not contract_path.exists():
            self.skipTest("repo artifacts are not available")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_live_context_snapshot(LiveContextSnapshotConfig(output_dir=root / "out"))

            csv_path = root / "out" / "live_context_snapshot.csv"
            json_path = root / "out" / "live_context_snapshot.json"
            contract_columns = pd.read_csv(contract_path)["column"].tolist()
            csv_frame = pd.read_csv(csv_path)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(csv_frame.columns.tolist(), contract_columns)
            self.assertEqual(len(csv_frame), len(payload))
            self.assertEqual(int((csv_frame["can_execute_order"].astype(str).str.lower() == "true").sum()), 0)
            self.assertEqual(
                int((csv_frame["wavecount_should_filter_trade"].astype(str).str.lower() == "true").sum()),
                0,
            )

    def _config(self, root: Path, watcher_dir: Path, policy_dir: Path | None = None) -> LiveContextSnapshotConfig:
        contract_path = root / "contract.csv"
        pd.DataFrame({"column": SNAPSHOT_COLUMNS}).to_csv(contract_path, index=False)
        robust_dir = root / "wavecount_259"
        (robust_dir / "tables").mkdir(parents=True)
        pd.DataFrame(columns=[
            "symbol",
            "timeframe",
            "swing_degree",
            "review_category",
            "phase259_prominence_diagnostic",
            "phase259_candidate_bucket",
        ]).to_csv(robust_dir / "tables" / "phase259_candidate_policy_scores.csv", index=False)
        closure_dir = root / "wavecount_2510"
        (closure_dir / "tables").mkdir(parents=True)
        pd.DataFrame({"component": []}).to_csv(closure_dir / "tables" / "phase25_final_policy_matrix.csv", index=False)
        if policy_dir is None:
            policy_dir = root / "wavecount_256"
            (policy_dir / "tables").mkdir(parents=True)
            pd.DataFrame(columns=["symbol"]).to_csv(policy_dir / "tables" / "phase256_policy_scores.csv", index=False)
        return LiveContextSnapshotConfig(
            watcher_dir=watcher_dir,
            output_dir=root / "out",
            contract_path=contract_path,
            wavecount_policy_dir=policy_dir,
            wavecount_robust_dir=robust_dir,
            wavecount_closure_dir=closure_dir,
        )

    def _watcher_row(self, **overrides):
        row = {
            "Group": "Forex Majors",
            "strategy": "enbolsa:macd_breakout",
            "symbol": "EURUSD.r",
            "timeframe_ltf": "H1",
            "timeframe_htf": "H4",
            "timestamp": "2026-01-01 00:00:00",
            "latest_closed_bar": True,
            "direction": 1,
            "side": "BUY",
            "setup_id": "42",
            "setup_age": 3,
            "signal_state": "watching_setup",
            "reason": "waiting_for_trendline_and_macd_confirmation",
            "event_key": "",
            "entry": "",
            "sl": "",
            "tp1": "",
            "tp2": "",
            "risk_pct": "",
            "riskguard_accepted": "",
            "riskguard_reason": "",
            "riskguard_detail": "",
        }
        row.update(overrides)
        return row

    def _write_watcher_outputs(
        self,
        root: Path,
        snapshot_rows,
        order_intents=None,
        riskguard_decisions=None,
    ) -> Path:
        watcher_dir = root / "watcher"
        watcher_dir.mkdir()
        pd.DataFrame(snapshot_rows).to_csv(watcher_dir / "snapshot.csv", index=False)
        pd.DataFrame(columns=[
            "strategy",
            "symbol",
            "side",
            "setup_id",
            "timestamp",
            "timeframe_ltf",
            "timeframe_htf",
            "watch_state",
            "missing_confirmation",
            "w2_swing",
            "target_1_0",
            "target_1_618",
            "setup_age",
            "event_key",
        ]).to_csv(watcher_dir / "watchlist.csv", index=False)
        pd.DataFrame(order_intents or [], columns=[
            "event_key",
            "symbol",
            "timestamp",
            "side",
            "order_type",
            "entry",
            "sl",
            "tp",
            "tp1",
            "tp2",
            "risk_pct",
            "risk_amount",
            "strategy",
            "source",
            "riskguard_accepted",
            "riskguard_reason",
            "riskguard_detail",
            "riskguard_message",
        ]).to_csv(watcher_dir / "order_intents.csv", index=False)
        pd.DataFrame(riskguard_decisions or [], columns=[
            "accepted",
            "reason",
            "detail",
            "strategy",
            "symbol",
            "side",
            "setup_id",
            "timestamp",
            "risk_amount",
            "risk_pct",
            "current",
            "projected",
        ]).to_csv(watcher_dir / "riskguard_decisions.csv", index=False)
        (watcher_dir / "run_meta.json").write_text(
            json.dumps({"generated_at": "2026-01-01T00:00:00"}),
            encoding="utf-8",
        )
        return watcher_dir


if __name__ == "__main__":
    unittest.main()
