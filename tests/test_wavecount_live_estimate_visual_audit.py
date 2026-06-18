import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_estimate_visual_audit import (
    LiveEstimateVisualAuditConfig,
    build_live_estimate_visual_audit,
)
from trading_center.wavecount_live_estimate import LIVE_ESTIMATE_COLUMNS


class WaveCountLiveEstimateVisualAuditTests(unittest.TestCase):
    def test_visual_audit_generates_outputs_without_operational_side_effects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "live_estimate"
            output_dir = root / "audit"
            doc_path = root / "audit.md"
            input_dir.mkdir()
            self._write_live_estimate_inputs(input_dir)

            result = build_live_estimate_visual_audit(
                LiveEstimateVisualAuditConfig(
                    input_dir=input_dir,
                    state_machine_dir=root / "missing_state",
                    warning_audit_dir=root / "missing_warning",
                    output_dir=output_dir,
                    doc_path=doc_path,
                    copy_charts=False,
                )
            )

            for filename in [
                "contract_security_audit.csv",
                "visual_live_estimate_audit.csv",
                "us500_wave3_active_audit.csv",
                "xauusd_wave3_candidate_audit.csv",
                "invalidated_context_audit.csv",
                "state_machine_vs_live_estimate_audit.csv",
                "decision_summary.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_LIVE_ESTIMATE_VISUAL_AUDIT.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            decision = pd.read_csv(output_dir / "decision_summary.csv")
            visual = pd.read_csv(output_dir / "visual_live_estimate_audit.csv")
            contract = pd.read_csv(output_dir / "contract_security_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(result.decision, "live_estimate_study_panel_only")
            self.assertEqual(decision.loc[0, "decision"], "live_estimate_study_panel_only")
            self.assertFalse(bool(decision.loc[0, "sql_dashboard_allowed_now"]))
            self.assertEqual(len(visual), 3)
            self.assertFalse((contract["status"] == "fail").any())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())

    def _write_live_estimate_inputs(self, input_dir: Path) -> None:
        rows = [
            self._estimate_row(
                "US500",
                "possible_wave3_active",
                "possible_wave3_active_late",
                "short",
                latest_close=95.0,
                activation=100.0,
                invalidation=120.0,
                display="show_live_estimate_with_warning",
            ),
            self._estimate_row(
                "XAUUSD.r",
                "possible_wave3_candidate",
                "possible_wave3_candidate_late",
                "long",
                latest_close=105.0,
                activation=130.0,
                invalidation=80.0,
                display="show_live_estimate_with_warning",
            ),
            self._estimate_row(
                "EURUSD.r",
                "invalidated",
                "invalidated",
                "long",
                latest_close=75.0,
                activation=100.0,
                invalidation=90.0,
                display="manual_review_only",
            ),
        ]
        frame = pd.DataFrame(rows).reindex(columns=LIVE_ESTIMATE_COLUMNS)
        frame.to_csv(input_dir / "live_wave_estimate.csv", index=False)
        (input_dir / "live_wave_estimate.json").write_text(
            json.dumps(frame.to_dict(orient="records"), indent=2, default=str),
            encoding="utf-8",
        )
        frame[
            [
                "symbol",
                "timeframe",
                "as_of_bar_time",
                "latest_close_time",
                "last_persistent_pivot_time",
                "lookahead_safe",
                "source",
                "method_version",
            ]
        ].assign(latest_close_not_after_as_of=True).to_csv(input_dir / "anti_lookahead_audit.csv", index=False)
        frame[
            [
                "symbol",
                "timeframe",
                "as_of_bar_time",
                "current_leg_direction",
                "current_leg_status",
                "last_persistent_pivot_type",
                "last_persistent_pivot_price",
                "last_persistent_pivot_time",
                "latest_close",
                "latest_close_time",
                "move_from_last_pivot_pct",
                "retracement_from_previous_leg_pct",
                "lookahead_safe",
            ]
        ].to_csv(input_dir / "current_leg_audit.csv", index=False)
        pd.DataFrame(
            [
                {
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "state_machine_wave": row["live_estimated_wave"],
                    "live_estimated_wave": row["live_estimated_wave"],
                    "activation_crossed": row["symbol"] == "US500",
                    "invalidated": row["live_estimated_wave"] == "invalidated",
                    "rule_applied": "synthetic",
                    "why_this_label": row["why_this_label"],
                    "why_not_higher_confidence": row["why_not_higher_confidence"],
                    "lookahead_safe": True,
                }
                for row in rows
            ]
        ).to_csv(input_dir / "estimate_rule_audit.csv", index=False)
        frame[
            [
                "symbol",
                "timeframe",
                "live_estimated_wave",
                "confidence_bucket",
                "freshness_status",
                "display_policy",
                "requires_manual_review",
            ]
        ].assign(warning=frame["why_not_higher_confidence"]).to_csv(input_dir / "confidence_warning_audit.csv", index=False)
        pd.DataFrame(
            [
                {
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "state_machine_wave": row["live_estimated_wave"],
                    "live_estimated_wave": row["live_estimated_wave"],
                    "state_machine_display_policy": "show_with_warning",
                    "live_display_policy": row["display_policy"],
                    "state_machine_confirmed_context": row["confirmed_wave_context"],
                    "confirmed_wave_context": row["confirmed_wave_context"],
                    "changed_label": False,
                    "comparison_note": "synthetic",
                }
                for row in rows
            ]
        ).to_csv(input_dir / "comparison_vs_state_machine.csv", index=False)
        pd.DataFrame([{"severity": "info", "risk": "synthetic", "description": "synthetic", "recommendation": "none"}]).to_csv(
            input_dir / "issues_or_risks.csv", index=False
        )
        (input_dir / "run_meta.json").write_text(
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

    def _estimate_row(
        self,
        symbol: str,
        live_wave: str,
        confirmed: str,
        direction: str,
        *,
        latest_close: float,
        activation: float,
        invalidation: float,
        display: str,
    ) -> dict:
        return {
            "estimate_id": f"estimate_{symbol}",
            "generated_at": "2026-05-27T00:00:00Z",
            "symbol": symbol,
            "market_group": "Synthetic",
            "timeframe": "H4",
            "higher_timeframe": "D1",
            "as_of_bar_time": "2026-03-17T04:00:00",
            "source": "wavecount_live_estimate_v0",
            "confirmed_wave_context": confirmed,
            "live_estimated_wave": live_wave,
            "next_wave_hypothesis": "not_available",
            "structure_family": "impulse" if live_wave != "invalidated" else "unknown",
            "direction": direction,
            "current_leg_direction": "down" if direction == "short" or live_wave == "invalidated" else "up",
            "current_leg_status": "impulse_attempt" if live_wave.endswith("active") else "breakout_attempt",
            "last_persistent_pivot_type": "high" if direction == "short" else "low",
            "last_persistent_pivot_price": 110.0,
            "last_persistent_pivot_time": "2026-02-01T00:00:00",
            "latest_close": latest_close,
            "latest_close_time": "2026-03-17T04:00:00",
            "move_from_last_pivot_pct": -5.0 if direction == "short" else 5.0,
            "retracement_from_previous_leg_pct": 20.0,
            "activation_level": activation,
            "invalidation_level": invalidation,
            "distance_to_activation_pct": 5.0,
            "distance_to_invalidation_pct": 10.0,
            "confidence_bucket": "medium" if live_wave.endswith("active") else "low",
            "freshness_status": "live_estimate_from_close",
            "display_policy": display,
            "why_this_label": "synthetic causal label",
            "why_not_higher_confidence": "synthetic warning",
            "requires_manual_review": display == "manual_review_only",
            "lookahead_safe": True,
            "is_read_only": True,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
            "method_version": "wavecount_live_estimate_v0",
            "notes": "synthetic",
            "payload_json": json.dumps({"direction": direction, "operational_use": "forbidden"}),
        }


if __name__ == "__main__":
    unittest.main()
