import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trading_center.wavecount_live_estimate import LIVE_ESTIMATE_COLUMNS
from trading_center.wavecount_study_screener import SCREENER_COLUMNS, StudyScreenerConfig, build_study_screener


class WaveCountStudyScreenerTests(unittest.TestCase):
    def test_study_screener_orders_candidates_without_operational_flags(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            live_dir = root / "live"
            visual_dir = root / "visual"
            output_dir = root / "screener"
            doc_path = root / "screener.md"
            live_dir.mkdir()
            visual_dir.mkdir()
            self._write_live_estimate(live_dir)
            self._write_visual_audit(visual_dir)

            result = build_study_screener(
                StudyScreenerConfig(
                    live_estimate_dir=live_dir,
                    visual_audit_dir=visual_dir,
                    output_dir=output_dir,
                    doc_path=doc_path,
                )
            )

            for filename in [
                "wavecount_study_screener.csv",
                "wavecount_study_screener.json",
                "screener_scoring_audit.csv",
                "display_contract.csv",
                "screener_sections.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_STUDY_SCREENER_V0.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            screener = pd.read_csv(output_dir / "wavecount_study_screener.csv")
            records = json.loads((output_dir / "wavecount_study_screener.json").read_text(encoding="utf-8"))
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(list(screener.columns), SCREENER_COLUMNS)
            self.assertEqual(len(screener), len(records))
            self.assertEqual(result.decision, "study_screener_v0_ready_for_broader_review")
            self.assertEqual(screener.iloc[0]["symbol"], "ACTIVE")
            self.assertEqual(screener.iloc[0]["screener_bucket"], "active_wave_study_candidate")
            self.assertEqual(screener.iloc[1]["screener_bucket"], "candidate_wave_watch")
            self.assertEqual(screener.iloc[2]["screener_bucket"], "invalidated_old_context")
            self.assertTrue(screener["is_read_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(screener["study_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(screener["show_in_main_dashboard"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(screener["telegram_allowed"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(screener["bot_allowed"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(screener["can_generate_signal"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(screener["can_filter_trade"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(screener["can_execute_order"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())

    def _write_live_estimate(self, root: Path) -> None:
        rows = [
            self._estimate("ACTIVE", "possible_wave3_active", "medium", "show_live_estimate_with_warning"),
            self._estimate("WATCH", "possible_wave3_candidate", "low", "show_live_estimate_with_warning"),
            self._estimate("OLD", "invalidated", "low", "manual_review_only"),
        ]
        frame = pd.DataFrame(rows).reindex(columns=LIVE_ESTIMATE_COLUMNS)
        frame.to_csv(root / "live_wave_estimate.csv", index=False)
        (root / "live_wave_estimate.json").write_text(json.dumps(frame.to_dict(orient="records"), indent=2), encoding="utf-8")
        (root / "run_meta.json").write_text(
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

    def _write_visual_audit(self, root: Path) -> None:
        pd.DataFrame(
            [
                self._visual("ACTIVE", "readable", "true"),
                self._visual("WATCH", "borderline", "unclear"),
                self._visual("OLD", "readable", "true"),
            ]
        ).to_csv(root / "visual_live_estimate_audit.csv", index=False)
        pd.DataFrame(
            [
                {
                    "decision": "live_estimate_study_panel_only",
                    "sql_dashboard_allowed_now": False,
                    "next_step": "synthetic",
                }
            ]
        ).to_csv(root / "decision_summary.csv", index=False)

    def _estimate(self, symbol: str, wave: str, confidence: str, display: str) -> dict:
        return {
            "estimate_id": f"estimate_{symbol}",
            "generated_at": "2026-05-27T00:00:00Z",
            "symbol": symbol,
            "market_group": "Synthetic",
            "timeframe": "H4",
            "higher_timeframe": "D1",
            "as_of_bar_time": "2026-03-17T04:00:00",
            "source": "wavecount_live_estimate_v0",
            "confirmed_wave_context": f"{wave}_late" if wave != "invalidated" else "invalidated",
            "live_estimated_wave": wave,
            "next_wave_hypothesis": "not_available",
            "structure_family": "impulse" if wave != "invalidated" else "unknown",
            "direction": "short" if symbol == "ACTIVE" else "long",
            "current_leg_status": "impulse_attempt" if wave.endswith("active") else "breakout_attempt",
            "confidence_bucket": confidence,
            "freshness_status": "live_estimate_from_close",
            "display_policy": display,
            "latest_close": 100.0,
            "activation_level": 101.0,
            "invalidation_level": 90.0,
            "distance_to_activation_pct": 1.0,
            "distance_to_invalidation_pct": 10.0,
            "why_this_label": "synthetic label",
            "why_not_higher_confidence": "synthetic warning",
            "requires_manual_review": display == "manual_review_only",
            "lookahead_safe": True,
            "is_read_only": True,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
            "method_version": "wavecount_live_estimate_v0",
            "payload_json": json.dumps({"operational_use": "forbidden"}),
        }

    def _visual(self, symbol: str, readability: str, plausible: str) -> dict:
        return {
            "symbol": symbol,
            "timeframe": "H4",
            "chart_file": f"{symbol}.png",
            "live_estimated_wave": "synthetic",
            "confirmed_wave_context": "synthetic",
            "current_leg_status": "synthetic",
            "visual_readability": readability,
            "label_plausible": plausible,
            "activation_level_plausible": "true",
            "invalidation_level_plausible": "true",
            "display_policy_ok": "true",
            "manual_notes": "synthetic",
        }


if __name__ == "__main__":
    unittest.main()
