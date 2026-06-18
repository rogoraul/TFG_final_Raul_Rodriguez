import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import (
    ParameterReviewConfig,
    build_parameter_review,
)


class WaveCountLiveParameterReviewTests(unittest.TestCase):
    def test_parameter_review_generates_comparative_outputs_safely(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_ohlc.csv"
            output_dir = root / "parameter_review"
            doc_path = root / "parameter_doc.md"
            self._write_source(source)

            result = build_parameter_review(
                ParameterReviewConfig(
                    source_csv=source,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    symbols=("TEST",),
                    timeframe="H4",
                    higher_timeframe="D1",
                    cut_count=3,
                    min_bars_first_cut=24,
                    max_symbols=1,
                    config_names=("baseline_actual", "conservative_b"),
                    generate_charts=False,
                )
            )

            for filename in [
                "parameter_grid.csv",
                "parameter_summary.csv",
                "config_comparison.csv",
                "phase_distribution_by_config.csv",
                "pivot_stability_by_config.csv",
                "label_transition_by_config.csv",
                "anti_lookahead_by_config.csv",
                "recommended_config.csv",
                "issues_or_risks.csv",
                "run_meta.json",
                "WAVECOUNT_LIVE_PARAMETER_REVIEW.md",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            anti = pd.read_csv(output_dir / "anti_lookahead_by_config.csv")
            comparison = pd.read_csv(output_dir / "config_comparison.csv")

            self.assertEqual(len(result.parameter_grid), 2)
            self.assertEqual(set(comparison["config_name"]), {"baseline_actual", "conservative_b"})
            self.assertTrue(anti["lookahead_safe_all"].all())
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
        for index in range(90):
            timestamp = start + pd.Timedelta(hours=4 * index)
            wave = math.sin(index / 4.0) * 2.5
            trend = index * 0.08
            close = 100.0 + trend + wave
            rows.append(
                {
                    "example_id": "TEST_H4",
                    "group": "Test",
                    "symbol": "TEST",
                    "timeframe": "H4",
                    "timestamp": timestamp.isoformat(),
                    "open": close - 0.2,
                    "high": close + 0.7,
                    "low": close - 0.7,
                    "close": close,
                }
            )
        pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
