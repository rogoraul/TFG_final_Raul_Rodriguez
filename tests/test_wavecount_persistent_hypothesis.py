import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_structure import StructuralPivotConfig
from trading_center.wavecount_persistent_hypothesis import (
    PERSISTENT_HYPOTHESIS_COLUMNS,
    PersistentHypothesisConfig,
    build_persistent_hypothesis,
)


class WaveCountPersistentHypothesisTests(unittest.TestCase):
    def test_persistent_hypothesis_generates_safe_non_operational_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_ohlc.csv"
            output_dir = root / "persistent_hypothesis"
            doc_path = root / "persistent_hypothesis.md"
            self._write_source(source)

            result = build_persistent_hypothesis(
                PersistentHypothesisConfig(
                    source_csv=source,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    current_hypothesis_csv=root / "missing_current.csv",
                    symbols=("TEST",),
                    timeframe="H4",
                    higher_timeframe="D1",
                    max_symbols=1,
                    cut_count=4,
                    min_bars_first_cut=24,
                    min_persistence_cuts=2,
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
                "persistent_wave_hypothesis.csv",
                "persistent_wave_hypothesis.json",
                "persistent_pivots.csv",
                "pivot_events.csv",
                "wave_events.csv",
                "anti_lookahead_audit.csv",
                "stability_audit.csv",
                "transition_audit.csv",
                "comparison_vs_current_wave_hypothesis.csv",
                "dashboard_display_contract.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_PERSISTENT_HYPOTHESIS_V0.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            hypotheses = pd.read_csv(output_dir / "persistent_wave_hypothesis.csv")
            records = json.loads((output_dir / "persistent_wave_hypothesis.json").read_text(encoding="utf-8"))
            pivots = pd.read_csv(output_dir / "persistent_pivots.csv")
            anti = pd.read_csv(output_dir / "anti_lookahead_audit.csv")
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(len(hypotheses), len(records))
            self.assertEqual(set(PERSISTENT_HYPOTHESIS_COLUMNS), set(hypotheses.columns))
            self.assertIn("estimated_current_wave", hypotheses.columns)
            self.assertIn("confirmed_wave_context", hypotheses.columns)
            self.assertTrue((pivots.loc[pivots["pivot_role"].isin(["candidate_pivot", "provisional_pivot"]), "is_persistent"].astype(str).str.lower() == "false").all())
            persistent_rows = pivots[pivots["is_persistent"].astype(str).str.lower().isin(["true", "1"])]
            if not persistent_rows.empty:
                self.assertGreaterEqual(persistent_rows["persistence_cuts"].astype(int).min(), 2)
            self.assertNotIn("completed_impulse_candidate", set(hypotheses["estimated_current_wave"]))
            self.assertTrue(anti["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["lookahead_safe"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["is_read_only"].astype(str).str.lower().isin(["true", "1"]).all())
            self.assertTrue(hypotheses["can_generate_signal"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(hypotheses["can_filter_trade"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertTrue(hypotheses["can_execute_order"].astype(str).str.lower().isin(["false", "0"]).all())
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())
            self.assertGreaterEqual(len(result.persistent_pivots), 1)

    @staticmethod
    def _write_source(path: Path) -> None:
        start = pd.Timestamp("2026-01-01T00:00:00")
        rows = []
        for index in range(96):
            timestamp = start + pd.Timedelta(hours=4 * index)
            wave = math.sin(index / 3.0) * 4.0
            trend = index * 0.04
            close = 100.0 + trend + wave
            rows.append(
                {
                    "example_id": "TEST_H4",
                    "group": "Test",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "timestamp": timestamp.isoformat(),
                    "open": close - 0.25,
                    "high": close + 0.8,
                    "low": close - 0.8,
                    "close": close,
                }
            )
        pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
