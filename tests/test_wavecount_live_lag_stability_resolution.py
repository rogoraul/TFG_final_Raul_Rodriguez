import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_lag_stability_resolution import (
    LagStabilityResolutionConfig,
    build_lag_stability_resolution,
)


class WaveCountLiveLagStabilityResolutionTests(unittest.TestCase):
    def test_lag_stability_resolution_generates_non_operational_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_ohlc.csv"
            output_dir = root / "lag_stability"
            doc_path = root / "lag_stability.md"
            self._write_source(source)

            result = build_lag_stability_resolution(
                LagStabilityResolutionConfig(
                    source_csv=source,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    symbols=("TEST",),
                    timeframe="H4",
                    higher_timeframe="D1",
                    cut_count=3,
                    min_bars_first_cut=24,
                    max_symbols=1,
                    config_names=("time_hard_a", "time_hard_b", "time_mid_c"),
                    generate_charts=False,
                )
            )

            for filename in [
                "lag_diagnostics.csv",
                "stability_diagnostics.csv",
                "lag_stability_parameter_grid.csv",
                "lag_stability_config_comparison.csv",
                "lag_stability_market_group.csv",
                "lag_stability_candidate_evaluation.csv",
                "lag_stability_visual_review.csv",
                "decision_summary.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_LIVE_LAG_STABILITY_RESOLUTION.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            decision = pd.read_csv(output_dir / "decision_summary.csv")
            comparison = pd.read_csv(output_dir / "lag_stability_config_comparison.csv")
            candidate_eval = pd.read_csv(output_dir / "lag_stability_candidate_evaluation.csv")

            self.assertEqual(len(result.parameter_grid), 3)
            self.assertEqual(set(comparison["config_name"]), {"time_hard_a", "time_hard_b", "time_mid_c"})
            self.assertIn("decision", decision.columns)
            self.assertIn("category", candidate_eval.columns)
            self.assertFalse(bool(decision.iloc[0]["sql_staging_allowed"]))
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
            wave = math.sin(index / 4.0) * 3.0
            trend = index * 0.05
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
