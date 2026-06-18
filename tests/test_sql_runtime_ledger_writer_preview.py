import csv
import json
from pathlib import Path

from trading_center.sql_runtime_ledger_writer_preview import (
    ATTEMPT_COLUMNS,
    SqlRuntimeLedgerWriterPreviewConfig,
    SqlRuntimeLedgerWriterPreviewOptions,
    build_sql_runtime_ledger_writer_preview,
    main,
)


def test_cli_generates_artifacts(tmp_path: Path) -> None:
    preflight_dir = _write_preflight_dir(tmp_path, [_preflight_row()])
    design_dir = _write_design_dir(tmp_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--preflight-dir",
            str(preflight_dir),
            "--design-dir",
            str(design_dir),
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "write_attempts.csv").exists()
    assert (output_dir / "write_attempts.json").exists()
    assert (output_dir / "would_insert_rows.csv").exists()
    assert (output_dir / "blocked_before_write.csv").exists()
    assert (output_dir / "tables" / "no_sql_write_audit.csv").exists()
    assert (output_dir / "SQL_RUNTIME_LEDGER_WRITER_PREVIEW_V1.md").exists()


def test_default_preview_does_not_connect_or_write(tmp_path: Path) -> None:
    result = _run(tmp_path, [_preflight_row()])
    meta = result.run_meta

    assert meta["db_connected"] is False
    assert meta["sql_real_written"] is False
    assert meta["sql_write_executed"] is False
    assert meta["rows_inserted"] == 0
    assert meta["rows_updated"] == 0
    assert meta["rows_deleted"] == 0
    assert len(result.would_insert_rows) == 1


def test_loads_only_accepted_as_insert_candidates_and_respects_blocked(tmp_path: Path) -> None:
    accepted = _preflight_row(dry_run_event_id="accepted_1")
    blocked = _preflight_row(dry_run_event_id="blocked_1", preflight_status="blocked_from_future_write")
    result = _run(tmp_path, [accepted], blocked_rows=[blocked])

    assert len(result.would_insert_rows) == 1
    assert len(result.blocked_before_write) == 1
    assert "preflight_not_accepted" in result.blocked_before_write[0]["block_reasons"]


def test_can_execute_order_true_blocks(tmp_path: Path) -> None:
    row = _preflight_row(can_execute_order="true")
    result = _run(tmp_path, [row])

    assert result.blocked_before_write
    assert "unsafe_execution_flag" in result.blocked_before_write[0]["block_reasons"]


def test_would_send_to_mt5_true_blocks(tmp_path: Path) -> None:
    row = _preflight_row(would_send_to_mt5="true")
    result = _run(tmp_path, [row])

    assert "mt5_side_effect_flag" in result.blocked_before_write[0]["block_reasons"]


def test_would_send_telegram_order_true_blocks(tmp_path: Path) -> None:
    row = _preflight_row(would_send_telegram_order="true")
    result = _run(tmp_path, [row])

    assert "telegram_order_flag" in result.blocked_before_write[0]["block_reasons"]


def test_is_simulation_false_blocks(tmp_path: Path) -> None:
    row = _preflight_row(is_simulation="false")
    result = _run(tmp_path, [row])

    assert "not_simulation" in result.blocked_before_write[0]["block_reasons"]


def test_wavecount_used_as_filter_true_blocks(tmp_path: Path) -> None:
    row = _preflight_row(wavecount_used_as_filter="true")
    result = _run(tmp_path, [row])

    assert "wavecount_filter_violation" in result.blocked_before_write[0]["block_reasons"]


def test_schema_mismatch_blocks(tmp_path: Path) -> None:
    preflight_dir = _write_preflight_dir(tmp_path, [_preflight_row()], schema_version="other_schema")
    result = _run_with_dirs(tmp_path, preflight_dir, _write_design_dir(tmp_path))

    assert "schema_version_mismatch" in result.blocked_before_write[0]["block_reasons"]


def test_append_only_without_manual_confirmation_blocks(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [_preflight_row()],
        options=SqlRuntimeLedgerWriterPreviewOptions(write_mode="append_only", sql_write_enabled=True),
    )

    assert "missing_manual_confirmation" in result.blocked_before_write[0]["block_reasons"]


def test_append_only_without_db_target_blocks_when_checked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SQL_RUNTIME_LEDGER_DB_TARGET", raising=False)
    result = _run(
        tmp_path,
        [_preflight_row()],
        options=SqlRuntimeLedgerWriterPreviewOptions(
            write_mode="append_only",
            sql_write_enabled=True,
            manual_confirmation=True,
            check_db_target=True,
        ),
    )

    assert "missing_db_target" in result.blocked_before_write[0]["block_reasons"]


def test_duplicate_same_key_hash_is_skipped(tmp_path: Path) -> None:
    row = _preflight_row()
    result = _run(tmp_path, [row, dict(row)])

    assert len(result.would_insert_rows) == 1
    assert len(result.skipped_duplicate_rows) == 1
    assert result.skipped_duplicate_rows[0]["writer_reason"] == "duplicate_same_hash"


def test_duplicate_same_key_different_hash_blocks(tmp_path: Path) -> None:
    first = _preflight_row()
    second = _preflight_row(payload_hash="different_hash")
    result = _run(tmp_path, [first, second])

    assert len(result.would_insert_rows) == 1
    assert len(result.blocked_before_write) == 1
    assert "idempotency_conflict" in result.blocked_before_write[0]["block_reasons"]


def test_existing_ledger_duplicate_same_hash_is_skipped(tmp_path: Path) -> None:
    row = _preflight_row()
    existing = _write_existing_ledger(tmp_path, [{"idempotency_key": row["idempotency_key"], "payload_hash": row["payload_hash"]}])
    result = _run(tmp_path, [row], options=SqlRuntimeLedgerWriterPreviewOptions(existing_ledger_csv=existing))

    assert not result.would_insert_rows
    assert len(result.skipped_duplicate_rows) == 1


def test_no_secret_values_are_written_when_db_target_checked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SQL_RUNTIME_LEDGER_DB_TARGET", "super-secret-target")
    result = _run(
        tmp_path,
        [_preflight_row()],
        options=SqlRuntimeLedgerWriterPreviewOptions(check_db_target=True),
    )
    output_text = (tmp_path / "out" / "tables" / "secret_handling_audit.csv").read_text(encoding="utf-8")

    assert result.run_meta["db_connected"] is False
    assert "super-secret-target" not in output_text


def test_no_db_mt5_or_telegram_imports() -> None:
    source = Path("trading_center/sql_runtime_ledger_writer_preview.py").read_text(encoding="utf-8")
    import_lines = "\n".join(line for line in source.splitlines() if line.startswith("import ") or line.startswith("from "))

    forbidden = ["mysql", "pymysql", "sqlalchemy", "sqlite3", "requests", "httpx", "telegram", "MetaTrader5"]
    assert not any(token in import_lines for token in forbidden)


def test_run_meta_keeps_fail_closed_flags(tmp_path: Path) -> None:
    result = _run(tmp_path, [_preflight_row()])
    meta = result.run_meta

    assert meta["sql_runtime_ledger_writer_preview_implemented"] is True
    assert meta["sql_runtime_ledger_writer_real_implemented"] is False
    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["db_connected"] is False
    assert meta["rows_inserted"] == 0
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False
    assert meta["backtests_executed"] is False


def test_empty_input_allowed_only_with_flag(tmp_path: Path) -> None:
    blocked = _run(tmp_path / "blocked", [])
    allowed = _run(
        tmp_path / "allowed",
        [],
        options=SqlRuntimeLedgerWriterPreviewOptions(allow_empty_input=True),
    )

    assert blocked.decision == "sql_runtime_ledger_writer_preview_v1_blocked_by_contract"
    assert allowed.decision == "sql_runtime_ledger_writer_preview_v1_ready_for_review"
    assert allowed.run_meta["write_attempts_count"] == 0


def _run(
    root: Path,
    accepted_rows: list[dict[str, object]],
    *,
    blocked_rows: list[dict[str, object]] | None = None,
    options: SqlRuntimeLedgerWriterPreviewOptions | None = None,
):
    preflight_dir = _write_preflight_dir(root, accepted_rows, blocked_rows=blocked_rows)
    return _run_with_dirs(root, preflight_dir, _write_design_dir(root), options=options)


def _run_with_dirs(
    root: Path,
    preflight_dir: Path,
    design_dir: Path,
    *,
    options: SqlRuntimeLedgerWriterPreviewOptions | None = None,
):
    return build_sql_runtime_ledger_writer_preview(
        SqlRuntimeLedgerWriterPreviewConfig(
            preflight_dir=preflight_dir,
            design_dir=design_dir,
            output_dir=root / "out",
            doc_path=root / "doc.md",
        ),
        options or SqlRuntimeLedgerWriterPreviewOptions(),
    )


def _write_preflight_dir(
    root: Path,
    accepted_rows: list[dict[str, object]],
    *,
    blocked_rows: list[dict[str, object]] | None = None,
    schema_version: str = "sql_runtime_ledger_v1",
) -> Path:
    preflight_dir = root / "preflight"
    preflight_dir.mkdir(parents=True, exist_ok=True)
    blocked = blocked_rows or []
    _write_csv(preflight_dir / "accepted_for_future_write.csv", accepted_rows, ATTEMPT_INPUT_COLUMNS)
    _write_csv(preflight_dir / "blocked_from_future_write.csv", blocked, ATTEMPT_INPUT_COLUMNS)
    _write_csv(preflight_dir / "preflight_rows.csv", accepted_rows + blocked, ATTEMPT_INPUT_COLUMNS)
    (preflight_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "decision": "sql_runtime_ledger_preflight_v1_ready_for_writer_design",
                "schema_version": schema_version,
                "write_mode": "preview",
                "sql_real_written": False,
                "db_connected": False,
                "ddl_executed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return preflight_dir


def _write_design_dir(root: Path) -> Path:
    design_dir = root / "design"
    tables = design_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    for name in [
        "sql_writer_required_conditions.csv",
        "sql_writer_blocking_conditions.csv",
        "sql_writer_future_config_contract.csv",
        "sql_writer_audit_contract.csv",
    ]:
        (tables / name).write_text("name,status\nplaceholder,pass\n", encoding="utf-8")
    (design_dir / "run_meta.json").write_text("{}", encoding="utf-8")
    return design_dir


def _write_existing_ledger(root: Path, rows: list[dict[str, object]]) -> Path:
    path = root / "existing_ledger.csv"
    _write_csv(path, rows, ["idempotency_key", "payload_hash"])
    return path


def _write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


ATTEMPT_INPUT_COLUMNS = [
    "row_index",
    "dry_run_event_id",
    "snapshot_id",
    "symbol",
    "timeframe",
    "setup_id",
    "strategy",
    "dry_run_decision",
    "preflight_status",
    "block_reasons",
    "warning_reasons",
    "schema_status",
    "payload_status",
    "safety_status",
    "riskguard_trace_status",
    "artifact_trace_status",
    "idempotency_status",
    "ddl_status",
    "idempotency_key",
    "payload_hash",
    "runtime_mode",
    "write_mode",
    "can_execute_order",
    "would_send_to_mt5",
    "would_send_telegram_order",
    "is_simulation",
    "wavecount_used_as_filter",
    "source_artifacts",
]


def _preflight_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "row_index": 0,
        "dry_run_event_id": "dryrun_fixture_1",
        "snapshot_id": "snapshot_test",
        "symbol": "EURUSD.r",
        "timeframe": "H1",
        "setup_id": "setup_1",
        "strategy": "enbolsa:macd_breakout",
        "dry_run_decision": "dry_run_no_action",
        "preflight_status": "accepted_for_future_write",
        "block_reasons": "",
        "warning_reasons": "",
        "schema_status": "pass",
        "payload_status": "pass",
        "safety_status": "pass",
        "riskguard_trace_status": "pass",
        "artifact_trace_status": "pass",
        "idempotency_status": "pass",
        "ddl_status": "pass",
        "idempotency_key": "rtledger:fixture_key",
        "payload_hash": "fixture_hash",
        "runtime_mode": "dry_run",
        "write_mode": "preview",
        "can_execute_order": "false",
        "would_send_to_mt5": "false",
        "would_send_telegram_order": "false",
        "is_simulation": "true",
        "wavecount_used_as_filter": "false",
        "source_artifacts": "artifacts/tfg/bot_dry_run_v1_2026-05-29/dry_run_decision_ledger.csv",
    }
    row.update(overrides)
    return row
