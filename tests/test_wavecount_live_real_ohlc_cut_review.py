import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import (
    RealOhlcCutReviewConfig,
    build_real_ohlc_cut_review,
)


class WaveCountLiveRealOhlcCutReviewTests(unittest.TestCase):
    def test_real_ohlc_cut_review_outputs_are_safe_and_causal(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_ohlc.csv"
            output_dir = root / "review"
            doc_path = root / "review_doc.md"
            self._write_source(source)

            result = build_real_ohlc_cut_review(
                RealOhlcCutReviewConfig(
                    source_csv=source,
                    output_dir=output_dir,
                    doc_path=doc_path,
                    symbols=("TEST",),
                    timeframe="H4",
                    higher_timeframe="D1",
                    cut_count=3,
                    min_bars_first_cut=24,
                    max_symbols=1,
                    generate_charts=False,
                )
            )

            for filename in [
                "wavecount_live_context.csv",
                "wavecount_live_context.json",
                "run_meta.json",
                "schema.csv",
                "source_ohlc_inventory.csv",
                "cut_inventory.csv",
                "anti_lookahead_audit.csv",
                "detected_pivots.csv",
                "structural_pivots.csv",
                "label_transition_audit.csv",
                "pivot_stability_audit.csv",
                "issues_or_risks.csv",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

            contexts = result.contexts
            audit = result.anti_lookahead_audit
            csv_rows = pd.read_csv(output_dir / "wavecount_live_context.csv")
            json_rows = json.loads((output_dir / "wavecount_live_context.json").read_text(encoding="utf-8"))
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

            self.assertEqual(len(contexts), 3)
            self.assertEqual(len(csv_rows), len(json_rows))
            self.assertTrue((contexts["data_origin"] == "real_ohlc_local_artifact").all())
            self.assertTrue(contexts["is_read_only"].all())
            self.assertFalse(contexts["can_generate_signal"].any())
            self.assertFalse(contexts["can_filter_trade"].any())
            self.assertFalse(contexts["can_execute_order"].any())
            self.assertTrue(audit["lookahead_safe"].all())
            self.assertTrue(audit["detected_at_lte_as_of"].all())
            self.assertTrue(audit["evidence_window_end_lte_as_of"].all())
            self.assertTrue(audit["pivot_detected_at_lte_as_of"].all())
            self.assertGreater(audit["bars_after_as_of_ignored"].astype(int).sum(), 0)
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
