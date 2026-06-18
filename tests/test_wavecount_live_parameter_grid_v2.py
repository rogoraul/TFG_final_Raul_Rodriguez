import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_grid_v2 import (
    ParameterGridV2Config,
    build_parameter_grid_v2,
)


class WaveCountLiveParameterGridV2Tests(unittest.TestCase):
    def test_parameter_grid_v2_generates_outputs_without_operational_side_effects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_ohlc.csv"
            output_dir = root / "parameter_grid_v2"
            doc_path = root / "parameter_grid_v2.md"
            self._write_source(source)

            result = build_parameter_grid_v2(
                ParameterGridV2Config(
                    source_csv=source,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    symbols=("TEST",),
                    timeframe="H4",
                    higher_timeframe="D1",
                    cut_count=3,
                    min_bars_first_cut=24,
                    max_symbols=1,
                    config_names=("baseline_actual", "mixed_balanced_a"),
                    generate_charts=False,
                )
            )

            for filename in [
                "parameter_grid_v2.csv",
                "config_comparison_v2.csv",
                "phase_distribution_by_config.csv",
                "pivot_stability_by_config.csv",
                "label_transition_by_config.csv",
                "anti_lookahead_by_config.csv",
                "market_group_sensitivity.csv",
                "candidate_evaluation.csv",
                "recommended_next_action.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_LIVE_PARAMETER_GRID_V2.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            anti = pd.read_csv(output_dir / "anti_lookahead_by_config.csv")
            comparison = pd.read_csv(output_dir / "config_comparison_v2.csv")
            candidate_eval = pd.read_csv(output_dir / "candidate_evaluation.csv")

            self.assertEqual(len(result.parameter_grid), 2)
            self.assertEqual(set(comparison["config_name"]), {"baseline_actual", "mixed_balanced_a"})
            self.assertTrue(anti["lookahead_safe_all"].all())
            self.assertIn("candidate_pass", candidate_eval.columns)
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["ddl_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])
            self.assertTrue(doc_path.exists())

    @staticmethod
    def _write_source(path: Path) -> None:
        start = pd.Timestamp("2026-01-01T00:00:00")
        rows = []
        for index in range(96):
            timestamp = start + pd.Timedelta(hours=4 * index)
            wave = math.sin(index / 4.5) * 2.8
            trend = index * 0.06
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
