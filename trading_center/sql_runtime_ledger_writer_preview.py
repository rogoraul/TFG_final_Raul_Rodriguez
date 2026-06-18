from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_PREFLIGHT_DIR = Path("artifacts/tfg/sql_runtime_ledger_preflight_v1_2026-05-29")
DEFAULT_DESIGN_DIR = Path("artifacts/tfg/sql_runtime_ledger_writer_design_v1_2026-05-30")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/sql_runtime_ledger_writer_preview_v1_2026-05-30")
DEFAULT_DOC_PATH = Path("docs/SQL_RUNTIME_LEDGER_WRITER_PREVIEW_V1.md")

ACCEPTED_FILE = "accepted_for_future_write.csv"
BLOCKED_FILE = "blocked_from_future_write.csv"
PREFLIGHT_ROWS_FILE = "preflight_rows.csv"
RUN_META_FILE = "run_meta.json"
DB_TARGET_ENV = "SQL_RUNTIME_LEDGER_DB_TARGET"

ATTEMPT_COLUMNS = [
    "write_attempt_id",
    "cycle_id",
    "event_id",
    "dry_run_event_id",
    "row_index",
    "idempotency_key",
    "payload_hash",
    "preflight_decision",
    "writer_decision",
    "writer_reason",
    "block_reasons",
    "warning_reasons",
    "sql_write_requested",
    "sql_write_executed",
    "db_connected",
    "rows_inserted",
    "rows_updated",
    "rows_deleted",
    "can_execute_order",
    "would_send_to_mt5",
    "would_send_telegram_order",
    "is_simulation",
    "wavecount_used_as_filter",
    "schema_version",
    "write_mode",
    "source_artifacts",
]


@dataclass(frozen=True)
class SqlRuntimeLedgerWriterPreviewOptions:
    schema_version: str = "sql_runtime_ledger_v1"
    write_mode: str = "preview"
    sql_write_enabled: bool = False
    manual_confirmation: bool = False
    check_db_target: bool = False
    existing_ledger_csv: Path | None = None
    max_rows_per_run: int | None = None
    allow_empty_input: bool = False
    fixture_mode: bool = False


@dataclass(frozen=True)
class SqlRuntimeLedgerWriterPreviewConfig:
    preflight_dir: Path = DEFAULT_PREFLIGHT_DIR
    design_dir: Path = DEFAULT_DESIGN_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_root: Path = Path(".")


@dataclass(frozen=True)
class SqlRuntimeLedgerWriterPreviewResult:
    decision: str
    write_attempts: list[dict[str, Any]]
    would_insert_rows: list[dict[str, Any]]
    skipped_duplicate_rows: list[dict[str, Any]]
    blocked_before_write: list[dict[str, Any]]
    run_meta: dict[str, Any]


def build_sql_runtime_ledger_writer_preview(
    config: SqlRuntimeLedgerWriterPreviewConfig | None = None,
    options: SqlRuntimeLedgerWriterPreviewOptions | None = None,
) -> SqlRuntimeLedgerWriterPreviewResult:
    config = config or SqlRuntimeLedgerWriterPreviewConfig()
    options = options or SqlRuntimeLedgerWriterPreviewOptions()
    generated_at = datetime.now().isoformat(timespec="seconds")
    root = config.source_root
    preflight_dir = _resolve(root, config.preflight_dir)
    design_dir = _resolve(root, config.design_dir)
    output_dir = _resolve(root, config.output_dir)
    doc_path = _resolve(root, config.doc_path)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    accepted_rows = _read_csv_rows(preflight_dir / ACCEPTED_FILE)
    blocked_rows = _read_csv_rows(preflight_dir / BLOCKED_FILE)
    preflight_rows = _read_csv_rows(preflight_dir / PREFLIGHT_ROWS_FILE) if (preflight_dir / PREFLIGHT_ROWS_FILE).exists() else []
    preflight_meta = _read_json_object(preflight_dir / RUN_META_FILE)
    design_audit = load_writer_design_contracts(design_dir)
    existing_entries = load_existing_ledger_entries(_resolve(root, options.existing_ledger_csv) if options.existing_ledger_csv else None)
    db_target_present = bool(os.environ.get(DB_TARGET_ENV)) if options.check_db_target else False

    write_attempts: list[dict[str, Any]] = []
    idempotency_audit: list[dict[str, Any]] = []
    schema_audit: list[dict[str, Any]] = []
    safety_audit: list[dict[str, Any]] = []
    seen_keys = dict(existing_entries)

    all_input_rows = [("accepted", row) for row in accepted_rows] + [("blocked", row) for row in blocked_rows]
    empty_input_block = not all_input_rows and not options.allow_empty_input

    for sequence_index, (input_status, row) in enumerate(all_input_rows):
        schema_result = validate_schema_version(row, preflight_meta, options, sequence_index)
        schema_audit.append(schema_result["audit"])
        safety_result = validate_safety_flags(row, sequence_index)
        safety_audit.extend(safety_result["audit"])
        idempotency_result = validate_writer_idempotency(row, sequence_index, seen_keys)
        idempotency_audit.append(idempotency_result["audit"])

        block_reasons: list[str] = []
        warning_reasons: list[str] = []
        writer_reasons: list[str] = []
        if input_status != "accepted" or _preflight_decision(row) != "accepted_for_future_write":
            block_reasons.append("preflight_not_accepted")
            writer_reasons.append("preflight_not_accepted")
        block_reasons.extend(schema_result["blocks"])
        block_reasons.extend(safety_result["blocks"])
        block_reasons.extend(idempotency_result["blocks"])
        warning_reasons.extend(idempotency_result["warnings"])
        writer_reasons.extend(schema_result["reasons"])
        writer_reasons.extend(safety_result["reasons"])
        writer_reasons.extend(idempotency_result["reasons"])
        config_blocks, config_reasons = writer_config_blocks(options, db_target_present)
        block_reasons.extend(config_blocks)
        writer_reasons.extend(config_reasons)
        if empty_input_block:
            block_reasons.append("empty_input_not_allowed")
            writer_reasons.append("empty_input_not_allowed")
        if options.max_rows_per_run is not None and len(accepted_rows) > options.max_rows_per_run:
            block_reasons.append("max_rows_per_run_exceeded")
            writer_reasons.append("max_rows_per_run_exceeded")

        if "duplicate_same_hash" in idempotency_result["warnings"] and not block_reasons:
            writer_decision = "preview_skipped_duplicate"
            writer_reason = "duplicate_same_hash"
        elif block_reasons:
            writer_decision = "blocked_before_write"
            writer_reason = ";".join(sorted(set(writer_reasons or block_reasons)))
        else:
            writer_decision = "preview_would_insert"
            writer_reason = "preview_only_no_sql_write"

        write_attempts.append(
            {
                "write_attempt_id": write_attempt_id(row, sequence_index),
                "cycle_id": "preview_cycle_" + hashlib.sha256(generated_at.encode("utf-8")).hexdigest()[:12],
                "event_id": event_id(row),
                "dry_run_event_id": _text(row.get("dry_run_event_id")),
                "row_index": _text(row.get("row_index"), str(sequence_index)),
                "idempotency_key": _text(row.get("idempotency_key")),
                "payload_hash": _text(row.get("payload_hash")),
                "preflight_decision": _preflight_decision(row),
                "writer_decision": writer_decision,
                "writer_reason": writer_reason,
                "block_reasons": ";".join(sorted(set(block_reasons))),
                "warning_reasons": ";".join(sorted(set(warning_reasons))),
                "sql_write_requested": str(options.sql_write_enabled and options.write_mode == "append_only").lower(),
                "sql_write_executed": "false",
                "db_connected": "false",
                "rows_inserted": 0,
                "rows_updated": 0,
                "rows_deleted": 0,
                "can_execute_order": _text(row.get("can_execute_order")),
                "would_send_to_mt5": _text(row.get("would_send_to_mt5")),
                "would_send_telegram_order": _text(row.get("would_send_telegram_order")),
                "is_simulation": _text(row.get("is_simulation")),
                "wavecount_used_as_filter": _text(row.get("wavecount_used_as_filter")),
                "schema_version": options.schema_version,
                "write_mode": options.write_mode,
                "source_artifacts": _text(row.get("source_artifacts")),
            }
        )

    if not all_input_rows and options.allow_empty_input:
        schema_audit.append(
            {
                "check": "empty_input_allowed",
                "status": "pass",
                "details": "No rows loaded and allow_empty_input=true.",
            }
        )
    elif empty_input_block:
        schema_audit.append(
            {
                "check": "empty_input_allowed",
                "status": "fail",
                "details": "No rows loaded and allow_empty_input=false.",
            }
        )

    would_insert_rows = [row for row in write_attempts if row["writer_decision"] == "preview_would_insert"]
    skipped_duplicate_rows = [row for row in write_attempts if row["writer_decision"] == "preview_skipped_duplicate"]
    blocked_before_write = [row for row in write_attempts if row["writer_decision"] == "blocked_before_write"]
    issues = build_issues_or_risks(
        accepted_rows,
        blocked_rows,
        would_insert_rows,
        skipped_duplicate_rows,
        blocked_before_write,
        options,
    )
    run_meta = build_run_meta(
        generated_at,
        accepted_rows,
        blocked_rows,
        write_attempts,
        would_insert_rows,
        skipped_duplicate_rows,
        blocked_before_write,
        options,
    )
    decision = (
        "sql_runtime_ledger_writer_preview_v1_blocked_by_contract"
        if empty_input_block
        else decide_phase_status(write_attempts)
    )
    run_meta["decision"] = decision

    _write_csv(output_dir / "write_attempts.csv", write_attempts, ATTEMPT_COLUMNS)
    (output_dir / "write_attempts.json").write_text(
        json.dumps(write_attempts, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_csv(output_dir / "would_insert_rows.csv", would_insert_rows, ATTEMPT_COLUMNS)
    _write_csv(output_dir / "skipped_duplicate_rows.csv", skipped_duplicate_rows, ATTEMPT_COLUMNS)
    _write_csv(output_dir / "blocked_before_write.csv", blocked_before_write, ATTEMPT_COLUMNS)
    _write_csv(tables_dir / "idempotency_write_audit.csv", idempotency_audit)
    _write_csv(tables_dir / "db_connection_audit.csv", build_db_connection_audit(options, db_target_present))
    _write_csv(tables_dir / "secret_handling_audit.csv", build_secret_handling_audit(options, db_target_present))
    _write_csv(tables_dir / "schema_version_audit.csv", schema_audit)
    _write_csv(tables_dir / "writer_config_audit.csv", build_writer_config_audit(options, design_audit))
    _write_csv(tables_dir / "safety_flags_writer_audit.csv", safety_audit)
    _write_csv(tables_dir / "no_sql_write_audit.csv", build_no_sql_write_audit())
    _write_csv(tables_dir / "issues_or_risks.csv", issues)
    (output_dir / RUN_META_FILE).write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    artifact_doc = render_markdown(run_meta, issues)
    (output_dir / "SQL_RUNTIME_LEDGER_WRITER_PREVIEW_V1.md").write_text(artifact_doc, encoding="utf-8")
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(artifact_doc, encoding="utf-8")

    return SqlRuntimeLedgerWriterPreviewResult(
        decision=decision,
        write_attempts=write_attempts,
        would_insert_rows=would_insert_rows,
        skipped_duplicate_rows=skipped_duplicate_rows,
        blocked_before_write=blocked_before_write,
        run_meta=run_meta,
    )


def load_writer_design_contracts(design_dir: Path) -> list[dict[str, Any]]:
    tables_dir = design_dir / "tables"
    contract_files = [
        "sql_writer_required_conditions.csv",
        "sql_writer_blocking_conditions.csv",
        "sql_writer_future_config_contract.csv",
        "sql_writer_audit_contract.csv",
    ]
    return [
        {
            "contract_file": name,
            "status": "pass" if (tables_dir / name).exists() else "fail",
            "rows": len(_read_csv_rows(tables_dir / name)) if (tables_dir / name).exists() else 0,
        }
        for name in contract_files
    ]


def load_existing_ledger_entries(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    rows = _read_csv_rows(path)
    entries: dict[str, str] = {}
    for row in rows:
        key = _text(row.get("idempotency_key"))
        payload_hash = _text(row.get("payload_hash"))
        if key and payload_hash:
            entries[key] = payload_hash
    return entries


def validate_schema_version(
    row: Mapping[str, Any],
    preflight_meta: Mapping[str, Any],
    options: SqlRuntimeLedgerWriterPreviewOptions,
    index: int,
) -> dict[str, Any]:
    expected = options.schema_version
    preflight_schema = _text(preflight_meta.get("schema_version"), expected)
    blocks: list[str] = []
    reasons: list[str] = []
    if preflight_schema != expected:
        blocks.append("schema_version_mismatch")
        reasons.append("schema_version_mismatch")
    if not _text(row.get("idempotency_key")) or not _text(row.get("payload_hash")):
        blocks.append("schema_version_mismatch")
        reasons.append("schema_version_mismatch")
    status = "pass" if not blocks else "fail"
    return {
        "blocks": blocks,
        "reasons": reasons,
        "audit": {
            "row_index": index,
            "dry_run_event_id": _text(row.get("dry_run_event_id")),
            "expected_schema_version": expected,
            "preflight_schema_version": preflight_schema,
            "idempotency_key_present": bool(_text(row.get("idempotency_key"))),
            "payload_hash_present": bool(_text(row.get("payload_hash"))),
            "status": status,
            "block_reasons": ";".join(blocks),
        },
    }


def validate_safety_flags(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    checks = [
        ("can_execute_order", False, _to_bool(row.get("can_execute_order")), "unsafe_execution_flag"),
        ("would_send_to_mt5", False, _to_bool(row.get("would_send_to_mt5")), "mt5_side_effect_flag"),
        (
            "would_send_telegram_order",
            False,
            _to_bool(row.get("would_send_telegram_order")),
            "telegram_order_flag",
        ),
        ("is_simulation", True, _to_bool(row.get("is_simulation")), "not_simulation"),
        ("wavecount_used_as_filter", False, _to_bool(row.get("wavecount_used_as_filter")), "wavecount_filter_violation"),
    ]
    blocks: list[str] = []
    reasons: list[str] = []
    audit: list[dict[str, Any]] = []
    for flag_name, expected, observed, block_reason in checks:
        passed = observed is expected
        if not passed:
            blocks.append(block_reason)
            reasons.append(block_reason)
        audit.append(
            {
                "row_index": index,
                "dry_run_event_id": _text(row.get("dry_run_event_id")),
                "flag_name": flag_name,
                "expected_value": str(expected).lower(),
                "observed_value": str(observed).lower(),
                "status": "pass" if passed else "fail",
                "block_reason": "" if passed else block_reason,
            }
        )
    return {"blocks": blocks, "reasons": reasons, "audit": audit}


def validate_writer_idempotency(
    row: Mapping[str, Any],
    index: int,
    seen_keys: dict[str, str],
) -> dict[str, Any]:
    key = _text(row.get("idempotency_key"))
    payload_hash = _text(row.get("payload_hash"))
    blocks: list[str] = []
    warnings: list[str] = []
    reasons: list[str] = []
    status = "pass"
    existing_hash = seen_keys.get(key, "")
    if not key or not payload_hash:
        blocks.append("idempotency_conflict")
        reasons.append("idempotency_conflict")
        status = "fail"
    elif existing_hash and existing_hash == payload_hash:
        warnings.append("duplicate_same_hash")
        reasons.append("duplicate_same_hash")
        status = "duplicate_same_hash"
    elif existing_hash and existing_hash != payload_hash:
        blocks.append("idempotency_conflict")
        reasons.append("idempotency_conflict")
        status = "conflict"
    else:
        seen_keys[key] = payload_hash
    return {
        "blocks": blocks,
        "warnings": warnings,
        "reasons": reasons,
        "audit": {
            "row_index": index,
            "dry_run_event_id": _text(row.get("dry_run_event_id")),
            "idempotency_key": key,
            "payload_hash": payload_hash,
            "existing_payload_hash_present": bool(existing_hash),
            "status": status,
            "block_reasons": ";".join(blocks),
            "warning_reasons": ";".join(warnings),
        },
    }


def writer_config_blocks(options: SqlRuntimeLedgerWriterPreviewOptions, db_target_present: bool) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    reasons: list[str] = []
    if options.write_mode not in {"preview", "append_only"}:
        blocks.append("write_mode_not_append_only")
        reasons.append("write_mode_not_append_only")
    if options.write_mode == "preview":
        reasons.append("preview_only_no_sql_write")
        return blocks, reasons
    if not options.sql_write_enabled:
        blocks.append("sql_write_disabled")
        reasons.append("sql_write_disabled")
    if not options.manual_confirmation:
        blocks.append("missing_manual_confirmation")
        reasons.append("missing_manual_confirmation")
    if options.check_db_target and not db_target_present:
        blocks.append("missing_db_target")
        reasons.append("missing_db_target")
    return blocks, reasons


def build_db_connection_audit(options: SqlRuntimeLedgerWriterPreviewOptions, db_target_present: bool) -> list[dict[str, Any]]:
    return [
        {"check": "db_target_checked", "status": "pass", "details": str(options.check_db_target).lower()},
        {"check": "db_target_present", "status": "pass" if db_target_present or not options.check_db_target else "warning", "details": str(db_target_present).lower()},
        {"check": "db_connected", "status": "pass", "details": "false"},
        {"check": "connection_attempted", "status": "pass", "details": "false"},
    ]


def build_secret_handling_audit(options: SqlRuntimeLedgerWriterPreviewOptions, db_target_present: bool) -> list[dict[str, Any]]:
    return [
        {"check": "db_target_source", "status": "pass", "details": "environment_boolean_check" if options.check_db_target else "not_checked"},
        {"check": "db_target_value_printed", "status": "pass", "details": "false"},
        {"check": "db_target_value_stored", "status": "pass", "details": "false"},
        {"check": "db_credentials_printed", "status": "pass", "details": "false"},
        {"check": "db_credentials_stored", "status": "pass", "details": "false"},
        {"check": "db_target_presence_boolean", "status": "pass", "details": str(db_target_present).lower()},
    ]


def build_writer_config_audit(
    options: SqlRuntimeLedgerWriterPreviewOptions,
    design_audit: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {"config_key": "write_mode", "observed_value": options.write_mode, "status": "pass" if options.write_mode == "preview" else "warning"},
        {"config_key": "sql_write_enabled", "observed_value": str(options.sql_write_enabled).lower(), "status": "pass" if not options.sql_write_enabled else "warning"},
        {"config_key": "manual_confirmation", "observed_value": str(options.manual_confirmation).lower(), "status": "pass" if not options.manual_confirmation else "warning"},
        {"config_key": "check_db_target", "observed_value": str(options.check_db_target).lower(), "status": "pass"},
        {"config_key": "max_rows_per_run", "observed_value": "" if options.max_rows_per_run is None else options.max_rows_per_run, "status": "pass"},
        {"config_key": "allow_empty_input", "observed_value": str(options.allow_empty_input).lower(), "status": "pass"},
        {"config_key": "fixture_mode", "observed_value": str(options.fixture_mode).lower(), "status": "pass"},
    ]
    for contract in design_audit:
        rows.append(
            {
                "config_key": "design_contract_" + str(contract["contract_file"]),
                "observed_value": contract["rows"],
                "status": contract["status"],
            }
        )
    return rows


def build_no_sql_write_audit() -> list[dict[str, Any]]:
    return [
        {"check": "sql_real_written", "status": "pass", "details": "false"},
        {"check": "sql_write_executed", "status": "pass", "details": "false"},
        {"check": "db_connected", "status": "pass", "details": "false"},
        {"check": "ddl_executed", "status": "pass", "details": "false"},
        {"check": "rows_inserted", "status": "pass", "details": "0"},
        {"check": "rows_updated", "status": "pass", "details": "0"},
        {"check": "rows_deleted", "status": "pass", "details": "0"},
        {"check": "mt5_connected", "status": "pass", "details": "false"},
        {"check": "telegram_connected", "status": "pass", "details": "false"},
    ]


def build_issues_or_risks(
    accepted_rows: Sequence[Mapping[str, Any]],
    blocked_rows: Sequence[Mapping[str, Any]],
    would_insert_rows: Sequence[Mapping[str, Any]],
    skipped_duplicate_rows: Sequence[Mapping[str, Any]],
    blocked_before_write: Sequence[Mapping[str, Any]],
    options: SqlRuntimeLedgerWriterPreviewOptions,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = [
        {
            "issue_id": "preview_only_no_sql_write",
            "severity": "info",
            "status": "accepted",
            "description": "Writer preview simulates write attempts but never connects DB or writes SQL.",
            "mitigation": "Keep rows_inserted=0 and db_connected=false.",
        }
    ]
    if accepted_rows:
        issues.append(
            {
                "issue_id": "future_candidates_present",
                "severity": "info",
                "status": "accepted",
                "description": f"{len(accepted_rows)} preflight rows are candidates for preview simulation.",
                "mitigation": "Do not interpret preview_would_insert as real SQL write approval.",
            }
        )
    if blocked_rows:
        issues.append(
            {
                "issue_id": "preflight_blocked_rows_present",
                "severity": "warning",
                "status": "controlled",
                "description": f"{len(blocked_rows)} rows remain blocked by preflight.",
                "mitigation": "Keep them in blocked_before_write.",
            }
        )
    if skipped_duplicate_rows:
        issues.append(
            {
                "issue_id": "duplicate_rows_skipped",
                "severity": "info",
                "status": "controlled",
                "description": f"{len(skipped_duplicate_rows)} duplicate rows were skipped in preview.",
                "mitigation": "Future writer should skip same-hash duplicates.",
            }
        )
    if blocked_before_write:
        issues.append(
            {
                "issue_id": "blocked_before_write_present",
                "severity": "warning",
                "status": "controlled",
                "description": f"{len(blocked_before_write)} write attempts were blocked before write.",
                "mitigation": "Inspect blocked_before_write.csv before any writer review.",
            }
        )
    if options.write_mode != "preview":
        issues.append(
            {
                "issue_id": "non_default_write_mode_used",
                "severity": "warning",
                "status": "controlled",
                "description": f"Preview module was run with write_mode={options.write_mode}.",
                "mitigation": "Still do not connect DB or write SQL in this phase.",
            }
        )
    return issues


def build_run_meta(
    generated_at: str,
    accepted_rows: Sequence[Mapping[str, Any]],
    preflight_blocked_rows: Sequence[Mapping[str, Any]],
    write_attempts: Sequence[Mapping[str, Any]],
    would_insert_rows: Sequence[Mapping[str, Any]],
    skipped_duplicate_rows: Sequence[Mapping[str, Any]],
    blocked_before_write: Sequence[Mapping[str, Any]],
    options: SqlRuntimeLedgerWriterPreviewOptions,
) -> dict[str, Any]:
    idempotency_conflicts = [row for row in blocked_before_write if "idempotency_conflict" in _text(row.get("block_reasons"))]
    return {
        "generated_at": generated_at,
        "phase": "sql_runtime_ledger_writer_preview_v1",
        "decision": "pending",
        "sql_runtime_ledger_writer_preview_implemented": True,
        "sql_runtime_ledger_writer_real_implemented": False,
        "sql_real_written": False,
        "sql_write_executed": False,
        "ddl_executed": False,
        "db_connected": False,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_deleted": 0,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "wavecount_used_as_filter": any(_to_bool(row.get("wavecount_used_as_filter")) for row in write_attempts),
        "can_execute_order_any_true": any(_to_bool(row.get("can_execute_order")) for row in write_attempts),
        "write_mode": options.write_mode,
        "sql_write_enabled": options.sql_write_enabled,
        "manual_confirmation": options.manual_confirmation,
        "check_db_target": options.check_db_target,
        "schema_version": options.schema_version,
        "accepted_input_count": len(accepted_rows),
        "preflight_blocked_input_count": len(preflight_blocked_rows),
        "write_attempts_count": len(write_attempts),
        "would_insert_count": len(would_insert_rows),
        "skipped_duplicate_count": len(skipped_duplicate_rows),
        "blocked_before_write_count": len(blocked_before_write),
        "idempotency_conflicts_count": len(idempotency_conflicts),
        "preview_would_insert_does_not_write_sql": True,
    }


def decide_phase_status(write_attempts: Sequence[Mapping[str, Any]]) -> str:
    block_text = ";".join(_text(row.get("block_reasons")) for row in write_attempts)
    safety_markers = [
        "unsafe_execution_flag",
        "mt5_side_effect_flag",
        "telegram_order_flag",
        "not_simulation",
        "wavecount_filter_violation",
    ]
    if any(marker in block_text for marker in safety_markers):
        return "sql_runtime_ledger_writer_preview_v1_blocked_by_safety"
    contract_markers = [
        "schema_version_mismatch",
        "idempotency_conflict",
        "preflight_not_accepted",
        "missing_manual_confirmation",
        "missing_db_target",
        "sql_write_disabled",
        "empty_input_not_allowed",
    ]
    if any(marker in block_text for marker in contract_markers):
        return "sql_runtime_ledger_writer_preview_v1_blocked_by_contract"
    return "sql_runtime_ledger_writer_preview_v1_ready_for_review"


def render_markdown(run_meta: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]) -> str:
    issue_lines = "\n".join(
        f"- `{issue['issue_id']}` ({issue['severity']}): {issue['description']}" for issue in issues
    )
    return f"""# SQL Runtime Ledger Writer Preview V1

Fecha: 2026-05-30

Decision: `{run_meta['decision']}`.

## Resumen

`sql_runtime_ledger_writer_preview_v1` simula el writer SQL append-only futuro
sin conectar base de datos y sin escribir SQL real. Consume los artifacts de
`sql_runtime_ledger_preflight_v1`, carga las filas aceptadas, respeta las filas
bloqueadas y genera auditoria de intentos de escritura.

## Resultado Del Preview

- Accepted input rows: `{run_meta['accepted_input_count']}`
- Preflight blocked input rows: `{run_meta['preflight_blocked_input_count']}`
- Write attempts: `{run_meta['write_attempts_count']}`
- `preview_would_insert`: `{run_meta['would_insert_count']}`
- `preview_skipped_duplicate`: `{run_meta['skipped_duplicate_count']}`
- `blocked_before_write`: `{run_meta['blocked_before_write_count']}`
- Idempotency conflicts: `{run_meta['idempotency_conflicts_count']}`
- Rows inserted: `0`

`preview_would_insert` no significa escritura real. Solo indica que la fila
seria candidata en una fase posterior si existiese writer append-only real,
DB target externo, DDL autorizado y confirmacion manual.

## Seguridad

- `sql_real_written=false`
- `sql_write_executed=false`
- `db_connected=false`
- `ddl_executed=false`
- `rows_inserted=0`
- `rows_updated=0`
- `rows_deleted=0`
- `mt5_connected=false`
- `telegram_connected=false`
- `orders_sent=0`
- `signals_generated=false`
- `backtests_executed=false`

## Idempotencia

El preview usa `idempotency_key` y `payload_hash` del preflight. Un duplicado
con la misma clave y el mismo hash se marca como `preview_skipped_duplicate`.
La misma clave con hash distinto se bloquea como `idempotency_conflict`.

## DB Target Y Secretos

El preview solo puede auditar presencia booleana opcional de DB target. No
imprime ni guarda valores de entorno, connection strings, usuario, host ni
password. No importa conectores DB.

## Riesgos

{issue_lines}

## Siguiente Paso

Revisar `sql_runtime_ledger_writer_preview_v1` antes de plantear cualquier
writer SQL real. No aprobar SQL writes, MT5 ni Telegram command bot todavia.
"""


def write_attempt_id(row: Mapping[str, Any], index: int) -> str:
    base = "|".join([_text(row.get("idempotency_key")), _text(row.get("payload_hash")), str(index)])
    return "write_preview_" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def event_id(row: Mapping[str, Any]) -> str:
    base = "|".join([_text(row.get("dry_run_event_id")), _text(row.get("idempotency_key"))])
    return "runtime_event_" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _preflight_decision(row: Mapping[str, Any]) -> str:
    return _text(row.get("preflight_decision")) or _text(row.get("preflight_status"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(fieldnames or _columns_from_rows(rows))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _columns_from_rows(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(str(key))
    return columns


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _resolve(root: Path, value: Path | None) -> Path:
    if value is None:
        raise ValueError("Cannot resolve None path.")
    return value if value.is_absolute() else root / value


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview SQL runtime ledger writer without DB writes.")
    parser.add_argument("--preflight-dir", type=Path, default=DEFAULT_PREFLIGHT_DIR)
    parser.add_argument("--design-dir", type=Path, default=DEFAULT_DESIGN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--schema-version", default="sql_runtime_ledger_v1")
    parser.add_argument("--write-mode", default="preview", choices=["preview", "append_only"])
    parser.add_argument("--sql-write-enabled", action="store_true")
    parser.add_argument("--manual-confirmation", action="store_true")
    parser.add_argument("--check-db-target", action="store_true")
    parser.add_argument("--existing-ledger-csv", type=Path, default=None)
    parser.add_argument("--max-rows-per-run", type=int, default=None)
    parser.add_argument("--allow-empty-input", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_sql_runtime_ledger_writer_preview(
        SqlRuntimeLedgerWriterPreviewConfig(
            preflight_dir=args.preflight_dir,
            design_dir=args.design_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        ),
        SqlRuntimeLedgerWriterPreviewOptions(
            schema_version=args.schema_version,
            write_mode=args.write_mode,
            sql_write_enabled=args.sql_write_enabled,
            manual_confirmation=args.manual_confirmation,
            check_db_target=args.check_db_target,
            existing_ledger_csv=args.existing_ledger_csv,
            max_rows_per_run=args.max_rows_per_run,
            allow_empty_input=args.allow_empty_input,
            fixture_mode=args.fixture_mode,
        ),
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "would_insert": len(result.would_insert_rows),
                "skipped_duplicate": len(result.skipped_duplicate_rows),
                "blocked_before_write": len(result.blocked_before_write),
                "rows_inserted": result.run_meta["rows_inserted"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
