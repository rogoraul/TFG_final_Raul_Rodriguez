import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backtests.tfg.build_sql_operational_core_artifacts import run
from trading_center.snapshot_schema import SNAPSHOT_COLUMNS, base_row
from trading_center.sql_admin import sha256_text, split_sql_statements
from trading_center.sql_loader import build_parser, load_snapshot_artifacts_to_store
from trading_center.sql_schema import (
    CORE_TABLES,
    CORE_VIEWS,
    DEFERRED_TABLES,
    RUN_KIND_POLICY,
    assert_no_deferred_tables_in_ddl,
    load_core_ddl,
    load_core_tables_ddl,
    load_core_views_ddl,
)
from trading_center.sql_store import InMemoryOperationalStore


class SqlOperationalCoreTests(unittest.TestCase):
    def test_core_ddl_contains_only_allowed_tables(self):
        ddl = load_core_tables_ddl()

        for table in CORE_TABLES:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", ddl)
        assert_no_deferred_tables_in_ddl(ddl)
        for table in DEFERRED_TABLES:
            self.assertNotIn(table, ddl)

    def test_security_defaults_are_fail_closed_in_ddl(self):
        ddl = load_core_tables_ddl()

        self.assertIn("is_read_only TINYINT(1) NOT NULL DEFAULT 1", ddl)
        self.assertIn("can_execute_order TINYINT(1) NOT NULL DEFAULT 0", ddl)
        self.assertIn("wavecount_should_filter_trade TINYINT(1) NOT NULL DEFAULT 0", ddl)
        self.assertIn("bot_enabled TINYINT(1) NOT NULL DEFAULT 0", ddl)
        self.assertIn("mode VARCHAR(32) NOT NULL DEFAULT 'off'", ddl)
        self.assertIn("mt5_enabled TINYINT(1) NOT NULL DEFAULT 0", ddl)
        self.assertIn("live_enabled TINYINT(1) NOT NULL DEFAULT 0", ddl)
        self.assertIn("kill_switch_enabled TINYINT(1) NOT NULL DEFAULT 1", ddl)
        self.assertIn("side VARCHAR(32) NOT NULL DEFAULT 'not_available'", ddl)

    def test_snapshot_runs_contains_cutover_and_origin_columns(self):
        ddl = load_core_tables_ddl()

        self.assertIn("run_kind VARCHAR(32) NOT NULL DEFAULT 'bootstrap_current'", ddl)
        self.assertIn("data_origin VARCHAR(64) NOT NULL DEFAULT 'live_context_snapshot_v0'", ddl)
        self.assertIn("is_operational TINYINT(1) NOT NULL DEFAULT 1", ddl)
        self.assertIn("cutover_at DATETIME(6) NULL", ddl)
        self.assertIn("source_snapshot_id VARCHAR(96) NULL", ddl)

    def test_operational_views_exclude_backfill_and_test_runs(self):
        ddl = load_core_views_ddl()

        self.assertIn("runs.is_operational = 1", ddl)
        self.assertIn("runs.run_kind IN ('bootstrap_current', 'live_observed')", ddl)
        self.assertNotIn("historical_backfill')", ddl)
        self.assertNotIn("test_fixture')", ddl)

    def test_minimal_views_exist(self):
        ddl = load_core_views_ddl()

        for view in CORE_VIEWS:
            self.assertIn(f"CREATE OR REPLACE VIEW {view}", ddl)

    def test_full_core_ddl_does_not_include_deferred_tables(self):
        assert_no_deferred_tables_in_ddl(load_core_ddl())

    def test_loader_is_idempotent_for_current_snapshot_artifacts(self):
        snapshot_dir = Path("artifacts/tfg/live_context_snapshot_v0")
        if not snapshot_dir.exists():
            self.skipTest("live_context_snapshot_v0 artifacts are not available")

        store = InMemoryOperationalStore()
        first = load_snapshot_artifacts_to_store(snapshot_dir, store, run_kind="bootstrap_current")
        second = load_snapshot_artifacts_to_store(snapshot_dir, store, run_kind="bootstrap_current")

        self.assertGreater(first.snapshot_rows, 0)
        self.assertEqual(first.run_kind, "bootstrap_current")
        self.assertTrue(first.is_operational)
        self.assertTrue(first.hard_flags_validated)
        self.assertEqual(second.inserted["snapshot_runs"], 0)
        self.assertEqual(second.inserted["live_context_snapshot_rows"], 0)
        self.assertEqual(second.inserted["signal_events"], 0)
        self.assertEqual(second.inserted["data_health_snapshot"], 0)
        self.assertEqual(len(store.snapshot_runs), 1)
        self.assertEqual(len(store.snapshot_rows), first.snapshot_rows)
        self.assertEqual(len(store.signal_events), first.signal_events)

    def test_loader_blocks_can_execute_order_true_before_normalization(self):
        with TemporaryDirectory() as tmp:
            snapshot_dir = Path(tmp)
            self._write_snapshot_dir(
                snapshot_dir,
                [
                    base_row(
                        snapshot_id="dangerous_snapshot",
                        generated_at="2026-05-25T00:00:00",
                        symbol="EURUSD.r",
                        timeframe_ltf="H1",
                        timeframe_htf="H4",
                        setup_id="danger",
                        signal_state="entry_ready_new",
                        can_execute_order=True,
                    )
                ],
            )

            with self.assertRaisesRegex(ValueError, "can_execute_order=true"):
                load_snapshot_artifacts_to_store(snapshot_dir, InMemoryOperationalStore())

    def test_loader_classifies_allowed_run_kinds(self):
        expected = {
            "bootstrap_current": True,
            "live_observed": True,
            "historical_backfill": False,
            "test_fixture": False,
        }
        self.assertEqual(set(expected), set(RUN_KIND_POLICY))

        for run_kind, is_operational in expected.items():
            with self.subTest(run_kind=run_kind):
                with TemporaryDirectory() as tmp:
                    snapshot_dir = Path(tmp)
                    self._write_snapshot_dir(
                        snapshot_dir,
                        [
                            base_row(
                                snapshot_id=f"snapshot_{run_kind}",
                                generated_at="2026-05-26T00:00:00",
                                symbol="EURUSD.r",
                                timeframe_ltf="H1",
                                timeframe_htf="H4",
                                setup_id=run_kind,
                                signal_state="watching_setup",
                            )
                        ],
                    )
                    store = InMemoryOperationalStore()

                    result = load_snapshot_artifacts_to_store(
                        snapshot_dir,
                        store,
                        run_kind=run_kind,
                        data_origin="test_fixture" if run_kind == "test_fixture" else "live_context_snapshot_v0",
                        cutover_at="2026-05-26T00:00:00",
                    )
                    run = store.snapshot_runs[f"snapshot_{run_kind}"]

                    self.assertEqual(result.run_kind, run_kind)
                    self.assertEqual(result.is_operational, is_operational)
                    self.assertEqual(run["run_kind"], run_kind)
                    self.assertEqual(run["is_operational"], is_operational)
                    self.assertEqual(run["cutover_at"], "2026-05-26 00:00:00")

    def test_loader_rejects_unknown_run_kind(self):
        with TemporaryDirectory() as tmp:
            snapshot_dir = Path(tmp)
            self._write_snapshot_dir(
                snapshot_dir,
                [
                    base_row(
                        snapshot_id="snapshot_unknown_kind",
                        generated_at="2026-05-26T00:00:00",
                        symbol="EURUSD.r",
                        timeframe_ltf="H1",
                        timeframe_htf="H4",
                    )
                ],
            )

            with self.assertRaisesRegex(ValueError, "Unknown run_kind"):
                load_snapshot_artifacts_to_store(snapshot_dir, InMemoryOperationalStore(), run_kind="old_backtest")

    def test_loader_preserves_unstable_fields_in_payload_json(self):
        snapshot_dir = Path("artifacts/tfg/live_context_snapshot_v0")
        if not snapshot_dir.exists():
            self.skipTest("live_context_snapshot_v0 artifacts are not available")

        store = InMemoryOperationalStore()
        load_snapshot_artifacts_to_store(snapshot_dir, store)

        row = next(iter(store.snapshot_rows.values()))
        payload = json.loads(row["payload_json"])
        self.assertIn("wavecount_notes", payload)
        self.assertIn("notes", payload)
        self.assertIn("candidate_risk_pct", payload)

    def test_loader_does_not_duplicate_signal_events_by_dedup_key(self):
        with TemporaryDirectory() as tmp:
            snapshot_dir = Path(tmp)
            self._write_snapshot_dir(
                snapshot_dir,
                [
                    base_row(
                        snapshot_id="snapshot_a",
                        generated_at="2026-05-25T00:00:00",
                        symbol="EURUSD.r",
                        timeframe_ltf="H1",
                        timeframe_htf="H4",
                        side="BUY",
                        setup_id="42",
                        signal_state="watching_setup",
                        telegram_dedup_key="dedup-42",
                    )
                ],
            )
            store = InMemoryOperationalStore()

            first = load_snapshot_artifacts_to_store(snapshot_dir, store)
            second = load_snapshot_artifacts_to_store(snapshot_dir, store)

            self.assertEqual(first.signal_events, 1)
            self.assertEqual(first.inserted["signal_events"], 1)
            self.assertEqual(second.inserted["signal_events"], 0)
            self.assertEqual(len(store.signal_events), 1)

    def test_artifact_builder_writes_core_report_without_real_sql(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "sql_core"

            meta = run(output_dir=output_dir, docs_path=None)

            self.assertFalse(meta["real_sql_executed"])
            self.assertFalse(meta["database_connected"])
            self.assertTrue((output_dir / "SQL_OPERATIONAL_CORE_V0.md").exists())
            self.assertTrue((output_dir / "tables" / "core_tables.csv").exists())
            self.assertTrue((output_dir / "tables" / "core_views.csv").exists())
            self.assertTrue((output_dir / "tables" / "deferred_tables.csv").exists())
            self.assertTrue((output_dir / "run_meta.json").exists())

    def test_real_db_loader_requires_explicit_apply_flag(self):
        parser = build_parser()

        dry_run = parser.parse_args(["--snapshot-dir", "x", "--dry-run"])
        default = parser.parse_args(["--snapshot-dir", "x"])
        apply = parser.parse_args(["--snapshot-dir", "x", "--apply-local-db"])

        self.assertTrue(dry_run.dry_run)
        self.assertFalse(dry_run.apply_local_db)
        self.assertFalse(default.dry_run)
        self.assertFalse(default.apply_local_db)
        self.assertTrue(apply.apply_local_db)

    def test_sql_statement_splitter_and_checksum_are_stable(self):
        sql_text = "CREATE SCHEMA IF NOT EXISTS x; USE x; SELECT 'a;b';"

        statements = split_sql_statements(sql_text)

        self.assertEqual(statements, ["CREATE SCHEMA IF NOT EXISTS x", "USE x", "SELECT 'a;b'"])
        self.assertEqual(sha256_text("abc"), sha256_text("abc"))
        self.assertNotEqual(sha256_text("abc"), sha256_text("abcd"))

    def _write_snapshot_dir(self, snapshot_dir: Path, rows):
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(rows).reindex(columns=SNAPSHOT_COLUMNS)
        frame.to_csv(snapshot_dir / "live_context_snapshot.csv", index=False)
        (snapshot_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "snapshot_id": rows[0]["snapshot_id"],
                    "generated_at": rows[0]["generated_at"],
                    "version": "live_context_snapshot_v0",
                    "limitations": [],
                }
            ),
            encoding="utf-8",
        )
        pd.DataFrame(
            [
                {
                    "name": "synthetic_snapshot",
                    "path": str(snapshot_dir / "live_context_snapshot.csv"),
                    "exists": True,
                    "rows": len(rows),
                    "role": "test",
                }
            ]
        ).to_csv(snapshot_dir / "source_inventory.csv", index=False)


if __name__ == "__main__":
    unittest.main()
