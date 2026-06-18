import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trading_center.wavecount_live_ohlc import (
    DEFAULT_OHLC_FIXTURE_DIR,
    WaveCountLiveOhlcConfig,
    build_wavecount_live_ohlc,
)
from trading_center.wavecount_live_schema import WAVECOUNT_LIVE_COLUMNS


class WaveCountLiveOhlcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output_dir = Path("artifacts/tfg/wavecount_live_context_v0_ohlc_prototype")
        cls.result = build_wavecount_live_ohlc(
            WaveCountLiveOhlcConfig(
                fixture_dir=DEFAULT_OHLC_FIXTURE_DIR,
                output_dir=cls.output_dir,
            )
        )
        cls.contexts = cls.result.contexts
        cls.inventory = cls.result.fixture_inventory
        cls.audit = cls.result.anti_lookahead_audit
        cls.detected = cls.result.detected_pivots
        cls.structural = cls.result.structural_pivots

    def test_cli_ohlc_generates_outputs(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "wavecount_live_ohlc"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "trading_center.wavecount_live_ohlc",
                    "--fixture-dir",
                    str(DEFAULT_OHLC_FIXTURE_DIR),
                    "--output-dir",
                    str(output_dir),
                    "--ohlc-only",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn('"real_sql_executed": false', completed.stdout)
            for filename in [
                "wavecount_live_context.csv",
                "wavecount_live_context.json",
                "run_meta.json",
                "schema.csv",
                "fixture_inventory.csv",
                "anti_lookahead_audit.csv",
                "detected_pivots.csv",
                "structural_pivots.csv",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)

    def test_contract_columns_match_schema(self):
        self.assertEqual(list(self.contexts.columns), WAVECOUNT_LIVE_COLUMNS)

    def test_csv_and_json_have_same_number_of_rows(self):
        csv_rows = pd.read_csv(self.output_dir / "wavecount_live_context.csv")
        json_rows = json.loads((self.output_dir / "wavecount_live_context.json").read_text(encoding="utf-8"))

        self.assertEqual(len(csv_rows), len(json_rows))
        self.assertEqual(len(csv_rows), len(self.contexts))

    def test_future_bars_and_future_pivots_are_not_used(self):
        self.assertGreater(self.audit["bars_after_as_of_ignored"].astype(int).sum(), 0)
        self.assertTrue(self.audit["pivot_detected_at_lte_as_of"].all())
        self.assertTrue(self.audit["detected_at_lte_as_of"].all())
        self.assertTrue(self.audit["evidence_window_end_lte_as_of"].all())
        self.assertTrue(self.audit["lookahead_safe"].all())

    def test_pivot_extreme_time_is_not_detection_time(self):
        self.assertFalse(self.detected.empty)
        detected_at = pd.to_datetime(self.detected["pivot_detected_at"])
        extreme_time = pd.to_datetime(self.detected["pivot_extreme_time"])

        self.assertTrue((detected_at >= extreme_time).all())
        self.assertTrue((detected_at > extreme_time).any())
        self.assertFalse(self.audit["pivot_extreme_time_used_as_detection"].astype(str).str.lower().isin({"true", "1"}).any())

    def test_hard_flags_are_always_fail_closed(self):
        self.assertTrue(self.contexts["is_read_only"].all())
        self.assertFalse(self.contexts["can_generate_signal"].any())
        self.assertFalse(self.contexts["can_filter_trade"].any())
        self.assertFalse(self.contexts["can_execute_order"].any())

    def test_expected_fixture_phases_match_actual(self):
        self.assertTrue(self.inventory["expected_matches_actual"].all())
        expected = {
            "possible_wave1",
            "possible_wave2",
            "possible_wave3_candidate",
            "possible_wave3_active",
            "possible_wave4",
            "possible_wave5_candidate",
            "possible_wave5_active",
            "completed_impulse_candidate",
            "possible_waveA",
            "possible_waveB",
            "possible_waveC_candidate",
            "possible_waveC_active",
            "completed_abc_candidate",
            "unknown",
            "ambiguous",
            "invalidated",
            "not_available",
        }
        self.assertEqual(set(self.contexts["structure_phase"]), expected)

    def test_wave2_does_not_become_wave3_without_breakout(self):
        row = self._row_by_fixture("ohlc_possible_wave2")
        self.assertEqual(row["structure_phase"], "possible_wave2")
        self.assertEqual(row["next_phase_hypothesis"], "possible_wave3_candidate")
        self.assertFalse(row["can_generate_signal"])

    def test_wave3_candidate_and_active_are_distinct(self):
        candidate = self._row_by_fixture("ohlc_wave3_candidate")
        active = self._row_by_fixture("ohlc_wave3_active")

        self.assertEqual(candidate["structure_phase"], "possible_wave3_candidate")
        self.assertEqual(active["structure_phase"], "possible_wave3_active")
        self.assertFalse(candidate["can_generate_signal"])
        self.assertFalse(active["can_generate_signal"])

    def test_abc_is_correction_family(self):
        rows = self.contexts[self.contexts["structure_phase"].isin(
            ["possible_waveA", "possible_waveB", "possible_waveC_candidate", "possible_waveC_active", "completed_abc_candidate"]
        )]

        self.assertFalse(rows.empty)
        self.assertTrue((rows["structure_family"] == "correction").all())

    def test_invalidated_and_ambiguous_are_explicit(self):
        invalidated = self._row_by_fixture("ohlc_invalidated")
        ambiguous = self._row_by_fixture("ohlc_ambiguous")

        self.assertEqual(invalidated["structure_phase"], "invalidated")
        self.assertEqual(invalidated["hypothesis_status"], "invalidated")
        self.assertEqual(ambiguous["structure_phase"], "ambiguous")
        self.assertEqual(ambiguous["confidence_bucket"], "manual_review")

    def test_no_sql_real_or_backtests_are_required(self):
        import trading_center.wavecount_live_ohlc as module

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        self.assertNotIn("sql_loader", module.__dict__)
        self.assertNotIn("mysql", source)
        self.assertFalse(self.result.run_meta["safety"]["real_sql_executed"])
        self.assertFalse(self.result.run_meta["safety"]["ddl_executed"])
        self.assertFalse(self.result.run_meta["safety"]["mt5_connected"])
        self.assertFalse(self.result.run_meta["safety"]["backtests_executed"])
        self.assertFalse(self.result.run_meta["safety"]["signals_generated"])

    def _row_by_fixture(self, fixture_id):
        matches = [
            record
            for record in self.contexts.to_dict(orient="records")
            if json.loads(record["payload_json"])["fixture_id"] == fixture_id
        ]
        self.assertEqual(len(matches), 1, fixture_id)
        return matches[0]


if __name__ == "__main__":
    unittest.main()
