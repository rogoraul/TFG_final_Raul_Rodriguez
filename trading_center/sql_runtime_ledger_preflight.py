from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_LEDGER_DIR = Path("artifacts/tfg/bot_dry_run_v1_2026-05-29")
DEFAULT_DESIGN_DIR = Path("artifacts/tfg/sql_runtime_ledger_design_v1_2026-05-29")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/sql_runtime_ledger_preflight_v1_2026-05-29")
DEFAULT_DOC_PATH = Path("docs/SQL_RUNTIME_LEDGER_PREFLIGHT_V1.md")

LEDGER_CSV = "dry_run_decision_ledger.csv"
LEDGER_JSON = "dry_run_decision_ledger.json"
DDL_DRAFT = "SQL_RUNTIME_LEDGER_V1_DDL_DRAFT.sql.txt"
EXECUTABLE_DDL = "SQL_RUNTIME_LEDGER_V1_DDL_DRAFT.sql"

REQUIRED_LEDGER_COLUMNS = [
    "dry_run_event_id",
    "generated_at",
    "snapshot_id",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "setup_id",
    "strategy",
    "signal_state",
    "side",
    "entry",
    "sl",
    "tp1",
    "tp2",
    "riskguard_status",
    "riskguard_reason",
    "dry_run_decision",
    "dry_run_reason",
    "would_create_order_intent",
    "would_send_to_mt5",
    "would_send_telegram_order",
    "can_execute_order",
    "is_simulation",
    "wavecount_context_summary",
    "source_artifacts",
    "payload_json",
]

PREFLIGHT_COLUMNS = [
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


@dataclass(frozen=True)
class SqlRuntimeLedgerPreflightOptions:
    schema_version: str = "sql_runtime_ledger_v1"
    runtime_mode: str = "dry_run"
    write_mode: str = "preview"
    strict_artifacts: bool = False
    allow_empty_ledger: bool = False
    fixture_mode: bool = False


@dataclass(frozen=True)
class SqlRuntimeLedgerPreflightConfig:
    ledger_dir: Path = DEFAULT_LEDGER_DIR
    design_dir: Path = DEFAULT_DESIGN_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_root: Path = Path(".")


@dataclass(frozen=True)
class SqlRuntimeLedgerPreflightResult:
    decision: str
    preflight_rows: list[dict[str, Any]]
    accepted_rows: list[dict[str, Any]]
    blocked_rows: list[dict[str, Any]]
    run_meta: dict[str, Any]


def build_sql_runtime_ledger_preflight(
    config: SqlRuntimeLedgerPreflightConfig | None = None,
    options: SqlRuntimeLedgerPreflightOptions | None = None,
) -> SqlRuntimeLedgerPreflightResult:
    config = config or SqlRuntimeLedgerPreflightConfig()
    options = options or SqlRuntimeLedgerPreflightOptions()
    generated_at = datetime.now().isoformat(timespec="seconds")
    root = config.source_root
    ledger_dir = _resolve(root, config.ledger_dir)
    design_dir = _resolve(root, config.design_dir)
    output_dir = _resolve(root, config.output_dir)
    doc_path = _resolve(root, config.doc_path)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    csv_path = ledger_dir / LEDGER_CSV
    json_path = ledger_dir / LEDGER_JSON
    csv_rows = _read_csv_rows(csv_path)
    json_rows = _read_json_rows(json_path)
    design_contracts = load_design_contracts(design_dir)
    ddl_audit = build_ddl_draft_audit(design_dir, root=root)
    ddl_pass = all(row["status"] == "pass" for row in ddl_audit)

    schema_audit = build_schema_validation_audit(csv_rows, json_rows, design_contracts, options)
    schema_global_block = any(row["status"] == "fail" for row in schema_audit)
    empty_block = len(csv_rows) == 0 and not options.allow_empty_ledger
    if empty_block:
        schema_global_block = True
        schema_audit.append(
            {
                "check": "empty_ledger_allowed",
                "status": "fail",
                "details": "Ledger is empty and allow_empty_ledger=false.",
            }
        )

    preflight_rows: list[dict[str, Any]] = []
    payload_audit: list[dict[str, Any]] = []
    safety_audit: list[dict[str, Any]] = []
    riskguard_audit: list[dict[str, Any]] = []
    artifact_audit: list[dict[str, Any]] = []
    idempotency_audit: list[dict[str, Any]] = []
    idempotency_seen: dict[str, str] = {}

    for index, row in enumerate(csv_rows):
        payload_result = validate_payload(row, index)
        payload_audit.append(payload_result["audit"])
        safety_result = validate_safety_flags(row, payload_result["payload"], options, index)
        safety_audit.extend(safety_result["audit"])
        riskguard_result = validate_riskguard_trace(row, index)
        riskguard_audit.append(riskguard_result["audit"])
        artifact_result = validate_artifact_trace(row, index, root=root, strict=options.strict_artifacts)
        artifact_audit.append(artifact_result["audit"])
        idempotency_result = validate_idempotency(
            row,
            payload_result["payload"],
            options,
            index,
            idempotency_seen,
        )
        idempotency_audit.append(idempotency_result["audit"])

        block_reasons: list[str] = []
        warning_reasons: list[str] = []
        if schema_global_block:
            block_reasons.append("missing_schema_or_columns")
        if not ddl_pass:
            block_reasons.append("ddl_draft_invalid")
        for result in [payload_result, safety_result, riskguard_result, artifact_result, idempotency_result]:
            block_reasons.extend(result["blocks"])
            warning_reasons.extend(result["warnings"])

        preflight_status = "accepted_for_future_write" if not block_reasons else "blocked_from_future_write"
        preflight_rows.append(
            {
                "row_index": index,
                "dry_run_event_id": _text(row.get("dry_run_event_id")),
                "snapshot_id": _text(row.get("snapshot_id")),
                "symbol": _text(row.get("symbol")),
                "timeframe": _text(row.get("timeframe")),
                "setup_id": _text(row.get("setup_id")),
                "strategy": _text(row.get("strategy")),
                "dry_run_decision": _text(row.get("dry_run_decision")),
                "preflight_status": preflight_status,
                "block_reasons": ";".join(sorted(set(block_reasons))),
                "warning_reasons": ";".join(sorted(set(warning_reasons))),
                "schema_status": "fail" if schema_global_block else "pass",
                "payload_status": payload_result["status"],
                "safety_status": safety_result["status"],
                "riskguard_trace_status": riskguard_result["status"],
                "artifact_trace_status": artifact_result["status"],
                "idempotency_status": idempotency_result["status"],
                "ddl_status": "pass" if ddl_pass else "fail",
                "idempotency_key": idempotency_result["idempotency_key"],
                "payload_hash": idempotency_result["payload_hash"],
                "runtime_mode": options.runtime_mode,
                "write_mode": options.write_mode,
                "can_execute_order": _text(row.get("can_execute_order")),
                "would_send_to_mt5": _text(row.get("would_send_to_mt5")),
                "would_send_telegram_order": _text(row.get("would_send_telegram_order")),
                "is_simulation": _text(row.get("is_simulation")),
                "wavecount_used_as_filter": str(safety_result["wavecount_used_as_filter"]).lower(),
                "source_artifacts": _text(row.get("source_artifacts")),
            }
        )

    accepted_rows = [row for row in preflight_rows if row["preflight_status"] == "accepted_for_future_write"]
    blocked_rows = [row for row in preflight_rows if row["preflight_status"] == "blocked_from_future_write"]
    issues = build_issues_or_risks(csv_rows, accepted_rows, blocked_rows, schema_global_block, ddl_pass, options)
    no_db_write_audit = build_no_db_write_audit(options)
    decision = (
        "sql_runtime_ledger_preflight_v1_ready_for_writer_design"
        if not schema_global_block and ddl_pass and not any(row["idempotency_status"] == "conflict" for row in preflight_rows)
        else "sql_runtime_ledger_preflight_v1_blocked_by_contract"
    )
    run_meta = build_run_meta(
        generated_at,
        decision,
        csv_rows,
        preflight_rows,
        accepted_rows,
        blocked_rows,
        options,
    )

    _write_csv(output_dir / "preflight_rows.csv", preflight_rows, PREFLIGHT_COLUMNS)
    (output_dir / "preflight_rows.json").write_text(
        json.dumps(preflight_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_csv(output_dir / "accepted_for_future_write.csv", accepted_rows, PREFLIGHT_COLUMNS)
    _write_csv(output_dir / "blocked_from_future_write.csv", blocked_rows, PREFLIGHT_COLUMNS)
    _write_csv(tables_dir / "schema_validation_audit.csv", schema_audit)
    _write_csv(tables_dir / "payload_validation_audit.csv", payload_audit)
    _write_csv(tables_dir / "safety_flags_preflight_audit.csv", safety_audit)
    _write_csv(tables_dir / "riskguard_trace_audit.csv", riskguard_audit)
    _write_csv(tables_dir / "artifact_trace_audit.csv", artifact_audit)
    _write_csv(tables_dir / "idempotency_audit.csv", idempotency_audit)
    _write_csv(tables_dir / "ddl_draft_audit.csv", ddl_audit)
    _write_csv(tables_dir / "no_db_write_audit.csv", no_db_write_audit)
    _write_csv(tables_dir / "issues_or_risks.csv", issues)
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    artifact_doc = render_markdown(run_meta, issues)
    (output_dir / "SQL_RUNTIME_LEDGER_PREFLIGHT_V1.md").write_text(artifact_doc, encoding="utf-8")
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(artifact_doc, encoding="utf-8")

    return SqlRuntimeLedgerPreflightResult(
        decision=decision,
        preflight_rows=preflight_rows,
        accepted_rows=accepted_rows,
        blocked_rows=blocked_rows,
        run_meta=run_meta,
    )


def load_design_contracts(design_dir: Path) -> dict[str, list[dict[str, str]]]:
    tables = design_dir / "tables"
    contracts: dict[str, list[dict[str, str]]] = {}
    for name in [
        "sql_runtime_ledger_field_contract.csv",
        "sql_runtime_preflight_contract.csv",
        "sql_runtime_safety_policy.csv",
        "sql_runtime_append_only_policy.csv",
    ]:
        path = tables / name
        contracts[name] = _read_csv_rows(path) if path.exists() else []
    return contracts


def build_schema_validation_audit(
    csv_rows: Sequence[Mapping[str, Any]],
    json_rows: Sequence[Mapping[str, Any]],
    contracts: Mapping[str, Sequence[Mapping[str, str]]],
    options: SqlRuntimeLedgerPreflightOptions,
) -> list[dict[str, Any]]:
    columns = set(csv_rows[0].keys()) if csv_rows else set(REQUIRED_LEDGER_COLUMNS)
    missing = [column for column in REQUIRED_LEDGER_COLUMNS if column not in columns]
    dry_run_ids = [_text(row.get("dry_run_event_id")) for row in csv_rows]
    duplicate_ids = sorted({item for item in dry_run_ids if item and dry_run_ids.count(item) > 1})
    field_contract = contracts.get("sql_runtime_ledger_field_contract.csv", [])
    contract_fields = {row.get("field_name", "") for row in field_contract}
    missing_contract_fields = [field for field in ["idempotency_key", "payload_hash", "schema_version"] if field not in contract_fields]
    return [
        {
            "check": "required_columns_present",
            "status": "pass" if not missing else "fail",
            "details": "all required columns present" if not missing else "missing=" + ";".join(missing),
        },
        {
            "check": "csv_json_row_count_match",
            "status": "pass" if len(csv_rows) == len(json_rows) else "fail",
            "details": f"csv_rows={len(csv_rows)}; json_rows={len(json_rows)}",
        },
        {
            "check": "dry_run_event_id_unique",
            "status": "pass" if not duplicate_ids else "warning",
            "details": "unique" if not duplicate_ids else "duplicates=" + ";".join(duplicate_ids),
        },
        {
            "check": "payload_json_column_present",
            "status": "pass" if "payload_json" in columns else "fail",
            "details": "payload_json present" if "payload_json" in columns else "payload_json missing",
        },
        {
            "check": "design_field_contract_loaded",
            "status": "pass" if field_contract and not missing_contract_fields else "fail",
            "details": f"field_contract_rows={len(field_contract)}; missing_contract_fields={';'.join(missing_contract_fields)}",
        },
        {
            "check": "runtime_mode_contract",
            "status": "pass" if options.runtime_mode == "dry_run" else "fail",
            "details": f"runtime_mode={options.runtime_mode}",
        },
    ]


def validate_payload(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    blocks: list[str] = []
    warnings: list[str] = []
    payload: dict[str, Any] = {}
    try:
        parsed = json.loads(_text(row.get("payload_json")))
        if isinstance(parsed, dict):
            payload = parsed
        else:
            blocks.append("payload_json_not_object")
    except json.JSONDecodeError:
        blocks.append("invalid_payload_json")

    required_sections = ["safety_flags", "checks", "options"]
    missing_sections = [section for section in required_sections if section not in payload]
    if missing_sections:
        blocks.append("payload_missing_" + "_".join(missing_sections))

    status = "pass" if not blocks else "fail"
    return {
        "status": status,
        "payload": payload,
        "blocks": blocks,
        "warnings": warnings,
        "audit": {
            "row_index": index,
            "dry_run_event_id": _text(row.get("dry_run_event_id")),
            "status": status,
            "missing_sections": ";".join(missing_sections),
            "block_reasons": ";".join(blocks),
        },
    }


def validate_safety_flags(
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
    options: SqlRuntimeLedgerPreflightOptions,
    index: int,
) -> dict[str, Any]:
    blocks: list[str] = []
    warnings: list[str] = []
    audit: list[dict[str, Any]] = []
    payload_safety = payload.get("safety_flags") if isinstance(payload.get("safety_flags"), Mapping) else {}
    payload_checks = payload.get("checks") if isinstance(payload.get("checks"), Mapping) else {}

    checks = [
        ("can_execute_order", False, _to_bool(row.get("can_execute_order")) or _to_bool(payload_safety.get("can_execute_order"))),
        ("would_send_to_mt5", False, _to_bool(row.get("would_send_to_mt5")) or _to_bool(payload_safety.get("would_send_to_mt5"))),
        (
            "would_send_telegram_order",
            False,
            _to_bool(row.get("would_send_telegram_order")) or _to_bool(payload_safety.get("would_send_telegram_order")),
        ),
        ("is_simulation", True, _to_bool(row.get("is_simulation")) and _to_bool(payload_safety.get("is_simulation", True))),
    ]
    wavecount_used_as_filter = _to_bool(row.get("wavecount_used_as_filter")) or _to_bool(
        payload_safety.get("wavecount_used_as_filter")
    ) or _to_bool(payload_checks.get("wavecount_used_as_filter"))
    checks.append(("wavecount_used_as_filter", False, wavecount_used_as_filter))

    if options.runtime_mode != "dry_run":
        blocks.append("runtime_mode_not_dry_run")
        audit.append(
            {
                "row_index": index,
                "dry_run_event_id": _text(row.get("dry_run_event_id")),
                "flag_name": "runtime_mode",
                "expected_value": "dry_run",
                "observed_value": options.runtime_mode,
                "status": "fail",
            }
        )

    for flag_name, expected, observed in checks:
        passed = observed is expected
        if not passed:
            blocks.append(f"{flag_name}_invalid")
        audit.append(
            {
                "row_index": index,
                "dry_run_event_id": _text(row.get("dry_run_event_id")),
                "flag_name": flag_name,
                "expected_value": str(expected).lower(),
                "observed_value": str(observed).lower(),
                "status": "pass" if passed else "fail",
            }
        )

    status = "pass" if not blocks else "fail"
    return {
        "status": status,
        "blocks": blocks,
        "warnings": warnings,
        "audit": audit,
        "wavecount_used_as_filter": wavecount_used_as_filter,
    }


def validate_riskguard_trace(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    blocks: list[str] = []
    warnings: list[str] = []
    decision = _text(row.get("dry_run_decision"))
    status_value = _text(row.get("riskguard_status"))
    reason = _text(row.get("riskguard_reason"))
    applies = decision == "dry_run_order_intent"
    if applies and status_value != "riskguard_accepted":
        blocks.append("riskguard_not_accepted_for_intent")
    if applies and (not reason or reason == "not_available"):
        blocks.append("riskguard_reason_missing_for_intent")
    status = "pass" if not blocks else "fail"
    return {
        "status": status,
        "blocks": blocks,
        "warnings": warnings,
        "audit": {
            "row_index": index,
            "dry_run_event_id": _text(row.get("dry_run_event_id")),
            "dry_run_decision": decision,
            "riskguard_status": status_value,
            "riskguard_reason": reason,
            "applies": applies,
            "status": status,
            "block_reasons": ";".join(blocks),
        },
    }


def validate_artifact_trace(row: Mapping[str, Any], index: int, *, root: Path, strict: bool) -> dict[str, Any]:
    blocks: list[str] = []
    warnings: list[str] = []
    source_artifacts = _text(row.get("source_artifacts"))
    if not source_artifacts:
        blocks.append("source_artifacts_missing")
        artifact_status = "fail"
        exists = False
    else:
        parts = [part.strip() for part in source_artifacts.replace("|", ";").split(";") if part.strip()]
        exists_any = False
        historical_any = False
        for part in parts:
            candidate = _resolve(root, Path(part))
            if candidate.exists():
                exists_any = True
            elif "artifacts" in part.replace("\\", "/"):
                historical_any = True
        if exists_any:
            artifact_status = "pass"
            exists = True
        elif historical_any and not strict:
            artifact_status = "warning"
            exists = False
            warnings.append("source_artifact_historical_path_not_found")
        else:
            artifact_status = "fail"
            exists = False
            blocks.append("source_artifact_missing")
    return {
        "status": "pass" if artifact_status in {"pass", "warning"} and not blocks else "fail",
        "blocks": blocks,
        "warnings": warnings,
        "audit": {
            "row_index": index,
            "dry_run_event_id": _text(row.get("dry_run_event_id")),
            "source_artifacts": source_artifacts,
            "exists": exists,
            "strict_artifacts": strict,
            "status": artifact_status,
            "block_reasons": ";".join(blocks),
            "warning_reasons": ";".join(warnings),
        },
    }


def validate_idempotency(
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
    options: SqlRuntimeLedgerPreflightOptions,
    index: int,
    seen: dict[str, str],
) -> dict[str, Any]:
    blocks: list[str] = []
    warnings: list[str] = []
    key = idempotency_key(row, options)
    payload_hash = compute_payload_hash(row, payload, options)
    status = "pass"
    if not key:
        blocks.append("idempotency_key_error")
        status = "fail"
    elif key in seen and seen[key] == payload_hash:
        warnings.append("duplicate_same_hash")
        status = "duplicate_same_hash"
    elif key in seen and seen[key] != payload_hash:
        blocks.append("idempotency_conflict")
        status = "conflict"
    else:
        seen[key] = payload_hash
    return {
        "status": status,
        "idempotency_key": key,
        "payload_hash": payload_hash,
        "blocks": blocks,
        "warnings": warnings,
        "audit": {
            "row_index": index,
            "dry_run_event_id": _text(row.get("dry_run_event_id")),
            "idempotency_key": key,
            "payload_hash": payload_hash,
            "status": status,
            "block_reasons": ";".join(blocks),
            "warning_reasons": ";".join(warnings),
        },
    }


def build_ddl_draft_audit(design_dir: Path, *, root: Path) -> list[dict[str, Any]]:
    ddl_path = design_dir / DDL_DRAFT
    executable_path = design_dir / EXECUTABLE_DDL
    sql_ops_sql = _resolve(root, Path("sql/ops") / EXECUTABLE_DDL)
    sql_ops_txt = _resolve(root, Path("sql/ops") / DDL_DRAFT)
    text = ddl_path.read_text(encoding="utf-8") if ddl_path.exists() else ""
    return [
        {
            "check": "ddl_draft_exists_as_sql_txt",
            "status": "pass" if ddl_path.exists() else "fail",
            "details": str(ddl_path),
        },
        {
            "check": "ddl_warning_present",
            "status": "pass" if "NO EJECUTAR" in text else "fail",
            "details": "warning found" if "NO EJECUTAR" in text else "warning missing",
        },
        {
            "check": "no_executable_sql_in_design_dir",
            "status": "pass" if not executable_path.exists() else "fail",
            "details": str(executable_path),
        },
        {
            "check": "not_in_sql_ops",
            "status": "pass" if not sql_ops_sql.exists() and not sql_ops_txt.exists() else "fail",
            "details": "sql/ops checked",
        },
    ]


def build_no_db_write_audit(options: SqlRuntimeLedgerPreflightOptions) -> list[dict[str, Any]]:
    return [
        {"check": "write_mode", "status": "pass" if options.write_mode == "preview" else "fail", "details": options.write_mode},
        {"check": "sql_write_enabled", "status": "pass", "details": "false"},
        {"check": "db_connected", "status": "pass", "details": "false"},
        {"check": "ddl_executed", "status": "pass", "details": "false"},
        {"check": "writer_implemented", "status": "pass", "details": "false"},
        {"check": "mt5_connected", "status": "pass", "details": "false"},
        {"check": "telegram_connected", "status": "pass", "details": "false"},
    ]


def build_issues_or_risks(
    csv_rows: Sequence[Mapping[str, Any]],
    accepted_rows: Sequence[Mapping[str, Any]],
    blocked_rows: Sequence[Mapping[str, Any]],
    schema_global_block: bool,
    ddl_pass: bool,
    options: SqlRuntimeLedgerPreflightOptions,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not csv_rows:
        issues.append(
            {
                "issue_id": "ledger_empty",
                "severity": "warning" if options.allow_empty_ledger else "error",
                "description": "Ledger has no rows.",
                "handling": "Allowed only for fixture mode or explicit allow_empty_ledger.",
            }
        )
    if schema_global_block:
        issues.append(
            {
                "issue_id": "schema_global_block",
                "severity": "error",
                "description": "Schema validation failed.",
                "handling": "Fix ledger contract before future writer design.",
            }
        )
    if not ddl_pass:
        issues.append(
            {
                "issue_id": "ddl_draft_invalid",
                "severity": "error",
                "description": "DDL draft audit failed.",
                "handling": "Keep DDL non-executable and warning-protected.",
            }
        )
    if blocked_rows:
        issues.append(
            {
                "issue_id": "blocked_rows_present",
                "severity": "warning",
                "description": f"{len(blocked_rows)} rows are blocked from future write.",
                "handling": "Inspect blocked_from_future_write.csv before writer design.",
            }
        )
    if accepted_rows:
        issues.append(
            {
                "issue_id": "accepted_rows_preview_only",
                "severity": "info",
                "description": f"{len(accepted_rows)} rows are accepted only as future append-only candidates.",
                "handling": "No SQL write is approved by this phase.",
            }
        )
    issues.append(
        {
            "issue_id": "writer_not_implemented",
            "severity": "info",
            "description": "SQL writer remains intentionally unimplemented.",
            "handling": "Next phase may design writer, but not enable SQL writes automatically.",
        }
    )
    return issues


def build_run_meta(
    generated_at: str,
    decision: str,
    csv_rows: Sequence[Mapping[str, Any]],
    preflight_rows: Sequence[Mapping[str, Any]],
    accepted_rows: Sequence[Mapping[str, Any]],
    blocked_rows: Sequence[Mapping[str, Any]],
    options: SqlRuntimeLedgerPreflightOptions,
) -> dict[str, Any]:
    conflicts = [row for row in preflight_rows if row.get("idempotency_status") == "conflict"]
    return {
        "generated_at": generated_at,
        "phase": "sql_runtime_ledger_preflight_v1",
        "decision": decision,
        "sql_runtime_ledger_preflight_implemented": True,
        "sql_runtime_ledger_writer_implemented": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": any(_to_bool(row.get("can_execute_order")) for row in csv_rows),
        "write_mode": options.write_mode,
        "runtime_mode": options.runtime_mode,
        "schema_version": options.schema_version,
        "strict_artifacts": options.strict_artifacts,
        "allow_empty_ledger": options.allow_empty_ledger,
        "fixture_mode": options.fixture_mode,
        "ledger_rows": len(csv_rows),
        "preflight_rows": len(preflight_rows),
        "future_write_candidates_count": len(accepted_rows),
        "blocked_count": len(blocked_rows),
        "idempotency_conflicts_count": len(conflicts),
        "accepted_for_future_write_does_not_write_sql": True,
    }


def render_markdown(run_meta: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]) -> str:
    issue_lines = "\n".join(
        f"- `{issue['issue_id']}` ({issue['severity']}): {issue['description']}" for issue in issues
    )
    return f"""# SQL Runtime Ledger Preflight V1

Fecha: 2026-05-29

Decision: `{run_meta['decision']}`.

## Resumen

`sql_runtime_ledger_preflight_v1` implementa un validador artifact-first previo a cualquier escritura SQL runtime. Lee el ledger CSV/JSON del bot dry-run, valida schema, payload JSON, hard flags, RiskGuard, trazabilidad de artifacts, idempotencia y DDL draft.

La fase no implementa writer SQL, no conecta base de datos, no escribe SQL real, no aplica DDL, no conecta MT5 y no conecta Telegram.

## Resultado Del Run Actual

- Ledger rows: `{run_meta['ledger_rows']}`
- Accepted for future write: `{run_meta['future_write_candidates_count']}`
- Blocked from future write: `{run_meta['blocked_count']}`
- Idempotency conflicts: `{run_meta['idempotency_conflicts_count']}`
- Write mode: `{run_meta['write_mode']}`

`accepted_for_future_write` solo significa apto para una futura fase writer append-only si se habilita manualmente. No significa escritura actual ni aprobacion operativa.

## Validaciones

- Schema CSV/JSON y columnas obligatorias.
- `payload_json` parseable con `safety_flags`, `checks` y `options`.
- Hard flags: `can_execute_order=false`, `would_send_to_mt5=false`, `would_send_telegram_order=false`, `is_simulation=true`, `wavecount_used_as_filter=false`.
- RiskGuard trace obligatorio para `dry_run_order_intent`.
- DDL draft `.sql.txt` con warning `NO EJECUTAR`.
- Idempotency key y payload hash.

## Seguridad

- `sql_real_written=false`
- `ddl_executed=false`
- `db_connected=false`
- `mt5_connected=false`
- `telegram_connected=false`
- `orders_sent=0`
- `signals_generated=false`
- `backtests_executed=false`

## Riesgos

{issue_lines}

## Siguiente Paso

Disenar `sql_runtime_ledger_writer_v1` solo si se quiere avanzar, manteniendo writer deshabilitado por defecto y con una revision separada antes de cualquier SQL write real.
"""


def idempotency_key(row: Mapping[str, Any], options: SqlRuntimeLedgerPreflightOptions) -> str:
    parts = [
        options.schema_version,
        options.runtime_mode,
        _text(row.get("snapshot_id")),
        _text(row.get("symbol")),
        _text(row.get("setup_id")),
        _text(row.get("timeframe")),
        _text(row.get("strategy")),
        _text(row.get("dry_run_event_id")),
    ]
    if any(not part for part in parts):
        return ""
    return "rtledger:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def compute_payload_hash(
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
    options: SqlRuntimeLedgerPreflightOptions,
) -> str:
    normalized = {
        "schema_version": options.schema_version,
        "runtime_mode": options.runtime_mode,
        "dry_run_event_id": _text(row.get("dry_run_event_id")),
        "snapshot_id": _text(row.get("snapshot_id")),
        "symbol": _text(row.get("symbol")),
        "timeframe": _text(row.get("timeframe")),
        "setup_id": _text(row.get("setup_id")),
        "strategy": _text(row.get("strategy")),
        "dry_run_decision": _text(row.get("dry_run_decision")),
        "dry_run_reason": _text(row.get("dry_run_reason")),
        "safety": {
            "can_execute_order": _to_bool(row.get("can_execute_order")),
            "would_send_to_mt5": _to_bool(row.get("would_send_to_mt5")),
            "would_send_telegram_order": _to_bool(row.get("would_send_telegram_order")),
            "is_simulation": _to_bool(row.get("is_simulation")),
        },
        "payload_json": payload,
    }
    encoded = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list.")
    return [row if isinstance(row, dict) else {"value": row} for row in data]


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


def _resolve(root: Path, value: Path) -> Path:
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
    parser = argparse.ArgumentParser(description="Validate SQL runtime ledger preflight without DB writes.")
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_LEDGER_DIR)
    parser.add_argument("--design-dir", type=Path, default=DEFAULT_DESIGN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--schema-version", default="sql_runtime_ledger_v1")
    parser.add_argument("--runtime-mode", default="dry_run")
    parser.add_argument("--write-mode", default="preview")
    parser.add_argument("--strict-artifacts", action="store_true")
    parser.add_argument("--allow-empty-ledger", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_sql_runtime_ledger_preflight(
        SqlRuntimeLedgerPreflightConfig(
            ledger_dir=args.ledger_dir,
            design_dir=args.design_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        ),
        SqlRuntimeLedgerPreflightOptions(
            schema_version=args.schema_version,
            runtime_mode=args.runtime_mode,
            write_mode=args.write_mode,
            strict_artifacts=args.strict_artifacts,
            allow_empty_ledger=args.allow_empty_ledger,
            fixture_mode=args.fixture_mode,
        ),
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "accepted_for_future_write": len(result.accepted_rows),
                "blocked_from_future_write": len(result.blocked_rows),
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
