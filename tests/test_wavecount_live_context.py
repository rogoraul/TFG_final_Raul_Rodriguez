import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trading_center.wavecount_live_context import (
    DEFAULT_FIXTURE_DIR,
    WaveCountLiveContextConfig,
    build_wavecount_live_context,
    classify_fixture_case,
    load_fixture_cases,
)
from trading_center.wavecount_live_schema import WAVECOUNT_LIVE_COLUMNS


class WaveCountLiveContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build_wavecount_live_context(
            WaveCountLiveContextConfig(
                fixture_dir=DEFAULT_FIXTURE_DIR,
                output_dir=Path("artifacts/tfg/wavecount_live_context_v0_fixture_prototype"),
            )
        )
        cls.contexts = cls.result.contexts
        cls.by_context = cls.contexts.set_index("context_id")
        cls.inventory = cls.result.fixture_inventory
        cls.audit = cls.result.anti_lookahead_audit

    def test_contract_columns_exist(self):
        self.assertEqual(list(self.contexts.columns), WAVECOUNT_LIVE_COLUMNS)

    def test_hard_flags_are_always_fail_closed(self):
        self.assertTrue(self.contexts["is_read_only"].all())
        self.assertFalse(self.contexts["can_generate_signal"].any())
        self.assertFalse(self.contexts["can_filter_trade"].any())
        self.assertFalse(self.contexts["can_execute_order"].any())

    def test_no_rows_use_future_bars_or_future_detection(self):
        self.assertTrue(self.audit["lookahead_safe"].all())
        self.assertTrue(self.audit["detected_at_lte_as_of"].all())
        self.assertTrue(self.audit["evidence_window_end_lte_as_of"].all())
        self.assertGreater(self.audit["bars_after_as_of_ignored"].astype(int).sum(), 0)

    def test_all_expected_fixture_phases_match_actual(self):
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

    def test_wave2_does_not_become_wave3_without_breakout_evidence(self):
        row = self._row_by_fixture("impulse_possible_wave2")
        self.assertEqual(row["structure_phase"], "possible_wave2")
        self.assertEqual(row["next_phase_hypothesis"], "possible_wave3_candidate")
        self.assertFalse(row["can_generate_signal"])

    def test_wave3_candidate_is_not_a_signal(self):
        row = self._row_by_fixture("impulse_wave3_candidate")
        self.assertEqual(row["structure_phase"], "possible_wave3_candidate")
        self.assertFalse(row["can_generate_signal"])
        self.assertFalse(row["can_filter_trade"])
        self.assertFalse(row["can_execute_order"])

    def test_wave5_active_does_not_filter_or_block(self):
        row = self._row_by_fixture("impulse_wave5_active")
        self.assertEqual(row["structure_phase"], "possible_wave5_active")
        self.assertFalse(row["can_filter_trade"])
        self.assertFalse(row["can_execute_order"])

    def test_abc_states_are_correction_family(self):
        rows = self.contexts[self.contexts["structure_phase"].isin(
            ["possible_waveA", "possible_waveB", "possible_waveC_candidate", "possible_waveC_active", "completed_abc_candidate"]
        )]
        self.assertFalse(rows.empty)
        self.assertTrue((rows["structure_family"] == "correction").all())

    def test_invalidated_and_ambiguous_states_are_explicit(self):
        invalidated = self._row_by_fixture("invalidated_wave2")
        ambiguous = self._row_by_fixture("ambiguous_low_prominence")

        self.assertEqual(invalidated["structure_phase"], "invalidated")
        self.assertEqual(invalidated["hypothesis_status"], "invalidated")
        self.assertEqual(ambiguous["structure_phase"], "ambiguous")
        self.assertEqual(ambiguous["confidence_bucket"], "manual_review")

    def test_csv_and_json_have_same_number_of_rows(self):
        output_dir = Path("artifacts/tfg/wavecount_live_context_v0_fixture_prototype")
        csv_rows = pd.read_csv(output_dir / "wavecount_live_context.csv")
        json_rows = json.loads((output_dir / "wavecount_live_context.json").read_text(encoding="utf-8"))

        self.assertEqual(len(csv_rows), len(json_rows))
        self.assertEqual(len(csv_rows), len(self.contexts))

    def test_cli_generates_fixture_only_outputs(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "wavecount_live"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "trading_center.wavecount_live_context",
                    "--fixture-dir",
                    str(DEFAULT_FIXTURE_DIR),
                    "--output-dir",
                    str(output_dir),
                    "--fixture-only",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn('"real_sql_executed": false', completed.stdout)
            self.assertTrue((output_dir / "wavecount_live_context.csv").exists())
            self.assertTrue((output_dir / "wavecount_live_context.json").exists())
            self.assertTrue((output_dir / "run_meta.json").exists())
            meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
            self.assertFalse(meta["safety"]["real_sql_executed"])
            self.assertFalse(meta["safety"]["mt5_connected"])
            self.assertFalse(meta["safety"]["backtests_executed"])
            self.assertFalse(meta["safety"]["signals_generated"])

    def test_tests_and_builder_do_not_require_sql_real(self):
        import trading_center.wavecount_live_context as module

        self.assertNotIn("sql_loader", module.__dict__)
        self.assertNotIn("mysql", Path(module.__file__).read_text(encoding="utf-8").lower())

    def test_classification_filters_future_pivots_before_as_of(self):
        case = {
            "fixture_id": "future_pivot_guard",
            "symbol": "FX_FUTURE",
            "timeframe": "H4",
            "higher_timeframe": "D1",
            "structure_family": "impulse",
            "direction": "long",
            "degree": "intermediate",
            "as_of_bar_time": "2026-02-01T08:00:00",
            "bars": [
                {"time": "2026-02-01T00:00:00", "close": 100.0},
                {"time": "2026-02-01T04:00:00", "close": 112.0},
                {"time": "2026-02-01T08:00:00", "close": 106.0},
            ],
            "pivots": [
                {"label": "origin", "pivot_type": "low", "extreme_time": "2026-02-01T00:00:00", "detected_at": "2026-02-01T04:00:00", "price": 100.0},
                {"label": "wave1", "pivot_type": "high", "extreme_time": "2026-02-01T04:00:00", "detected_at": "2026-02-01T08:00:00", "price": 112.0},
                {"label": "future_wave2", "pivot_type": "low", "extreme_time": "2026-02-01T08:00:00", "detected_at": "2026-02-01T12:00:00", "price": 105.0},
            ],
        }

        row, audit = classify_fixture_case(case, generated_at="2026-05-26T00:00:00Z")

        self.assertEqual(row["structure_phase"], "possible_wave2")
        self.assertEqual(audit["pivots_after_as_of_ignored"], 1)
        self.assertTrue(audit["lookahead_safe"])

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
