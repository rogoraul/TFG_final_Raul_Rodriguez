import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_structure import StructuralPivotConfig
from trading_center.wavecount_current_hypothesis import (
    CURRENT_WAVE_COLUMNS,
    CurrentWaveHypothesisConfig,
    build_current_wave_hypothesis,
)


class CurrentWaveHypothesisTests(unittest.TestCase):
    def test_current_wave_hypothesis_generates_safe_contract(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_ohlc.csv"
            output_dir = root / "current_wave_hypothesis"
            doc_path = root / "current_wave_hypothesis.md"
            as_of_bar_time = self._write_source(source)

            result = build_current_wave_hypothesis(
                CurrentWaveHypothesisConfig(
                    source_csv=source,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    symbols=("TEST",),
                    timeframe="H4",
                    higher_timeframe="D1",
                    max_symbols=1,
                    as_of_bar_time=as_of_bar_time,
                    pivot_config=PivotConfig(
                        left_bars=2,
                        confirmation_bars=2,
                        atr_period=4,
                        min_atr_multiplier=0.0,
                        min_relative_move_pct=0.0,
                        min_bars_between_pivots=1,
                        candidate_lookback_bars=3,
                    ),
                    structural_config=StructuralPivotConfig(
                        min_leg_atr_multiplier=0.0,
                        min_leg_relative_move_pct=0.0,
                        min_leg_bars=0,
                    ),
                )
            )

            for filename in [
                "current_wave_hypothesis.csv",
                "current_wave_hypothesis.json",
                "run_meta.json",
                "schema.csv",
                "hypothesis_state_model.csv",
                "pivot_role_model.csv",
                "anti_lookahead_audit.csv",
                "stability_audit.csv",
                "dashboard_display_contract.csv",
                "issues_or_risks.csv",
                "WAVECOUNT_CURRENT_HYPOTHESIS_V0.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            frame = pd.read_csv(output_dir / "current_wave_hypothesis.csv")
            records = json.loads((output_dir / "current_wave_hypothesis.json").read_text(encoding="utf-8"))
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            anti = pd.read_csv(output_dir / "anti_lookahead_audit.csv")

            self.assertEqual(len(frame), len(records))
            self.assertEqual(set(CURRENT_WAVE_COLUMNS), set(frame.columns))
            self.assertIn("estimated_current_wave", frame.columns)
            self.assertIn("confirmed_wave_context", frame.columns)
            self.assertIn("freshness_status", frame.columns)
            self.assertIn("wave_stability_status", frame.columns)
            self.assertTrue(frame["is_read_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(frame["can_generate_signal"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(frame["can_filter_trade"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(frame["can_execute_order"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(frame["tentative_pivots_treated_as_confirmed"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertNotEqual(frame.iloc[0]["estimated_current_wave"], "completed_impulse_candidate")
            self.assertTrue(anti["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertGreater(int(anti.iloc[0]["bars_after_as_of_ignored"]), 0)
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())
            self.assertIn(result.decision, set(meta["decision"] for _ in [0]))

    @staticmethod
    def _write_source(path: Path) -> str:
        start = pd.Timestamp("2026-01-01T00:00:00")
        rows = []
        as_of_bar_time = ""
        for index in range(90):
            timestamp = start + pd.Timedelta(hours=4 * index)
            wave = math.sin(index / 3.0) * 5.0
            trend = index * 0.03
            close = 100.0 + trend + wave
            if index == 72:
                as_of_bar_time = timestamp.isoformat()
            rows.append(
                {
                    "example_id": "TEST_H4",
                    "group": "Test",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "timestamp": timestamp.isoformat(),
                    "open": close - 0.2,
                    "high": close + 0.9,
                    "low": close - 0.9,
                    "close": close,
                }
            )
        pd.DataFrame(rows).to_csv(path, index=False)
        return as_of_bar_time


if __name__ == "__main__":
    unittest.main()
