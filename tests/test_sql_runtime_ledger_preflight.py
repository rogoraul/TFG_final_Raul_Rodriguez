import csv
import json
from pathlib import Path

from trading_center.sql_runtime_ledger_preflight import (
    REQUIRED_LEDGER_COLUMNS,
    SqlRuntimeLedgerPreflightConfig,
    SqlRuntimeLedgerPreflightOptions,
    build_sql_runtime_ledger_preflight,
    main,
)


def test_cli_generates_artifacts(tmp_path: Path) -> None:
    ledger_dir = _write_ledger_dir(tmp_path, [_ledger_row()])
    design_dir = _write_design_dir(tmp_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--ledger-dir",
            str(ledger_dir),
            "--design-dir",
            str(design_dir),
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(tmp_path / "doc.md"),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "preflight_rows.csv").exists()
    assert (output_dir / "preflight_rows.json").exists()
    assert (output_dir / "accepted_for_future_write.csv").exists()
    assert (output_dir / "blocked_from_future_write.csv").exists()
    assert (output_dir / "tables" / "schema_validation_audit.csv").exists()
    assert (output_dir / "tables" / "no_db_write_audit.csv").exists()
    assert (output_dir / "SQL_RUNTIME_LEDGER_PREFLIGHT_V1.md").exists()


def test_csv_json_ledger_counts_match(tmp_path: Path) -> None:
    result = _run(tmp_path, [_ledger_row()])

    assert result.run_meta["ledger_rows"] == 1
    assert result.run_meta["future_write_candidates_count"] == 1
    assert result.run_meta["blocked_count"] == 0


def test_csv_json_ledger_count_mismatch_blocks(tmp_path: Path) -> None:
    ledger_dir = _write_ledger_dir(tmp_path, [_ledger_row()])
    (ledger_dir / "dry_run_decision_ledger.json").write_text("[]", encoding="utf-8")
    result = _run_with_dirs(tmp_path, ledger_dir, _write_design_dir(tmp_path))

    assert result.blocked_rows
    assert "missing_schema_or_columns" in result.blocked_rows[0]["block_reasons"]


def test_missing_required_column_blocks(tmp_path: Path) -> None:
    row = _ledger_row()
    ledger_dir = _write_ledger_dir(tmp_path, [row], columns=[column for column in REQUIRED_LEDGER_COLUMNS if column != "symbol"])
    result = _run_with_dirs(tmp_path, ledger_dir, _write_design_dir(tmp_path))

    assert result.blocked_rows
    assert "missing_schema_or_columns" in result.blocked_rows[0]["block_reasons"]


def test_invalid_payload_json_blocks(tmp_path: Path) -> None:
    row = _ledger_row(payload_json="{invalid")
    result = _run(tmp_path, [row])

    assert result.blocked_rows
    assert "invalid_payload_json" in result.blocked_rows[0]["block_reasons"]


def test_can_execute_order_true_blocks(tmp_path: Path) -> None:
    row = _ledger_row(can_execute_order=True, safety_updates={"can_execute_order": True})
    result = _run(tmp_path, [row])

    assert "can_execute_order_invalid" in result.blocked_rows[0]["block_reasons"]


def test_would_send_to_mt5_true_blocks(tmp_path: Path) -> None:
    row = _ledger_row(would_send_to_mt5=True, safety_updates={"would_send_to_mt5": True})
    result = _run(tmp_path, [row])

    assert "would_send_to_mt5_invalid" in result.blocked_rows[0]["block_reasons"]


def test_would_send_telegram_order_true_blocks(tmp_path: Path) -> None:
    row = _ledger_row(
        would_send_telegram_order=True,
        safety_updates={"would_send_telegram_order": True},
    )
    result = _run(tmp_path, [row])

    assert "would_send_telegram_order_invalid" in result.blocked_rows[0]["block_reasons"]


def test_is_simulation_false_blocks(tmp_path: Path) -> None:
    row = _ledger_row(is_simulation=False, safety_updates={"is_simulation": False})
    result = _run(tmp_path, [row])

    assert "is_simulation_invalid" in result.blocked_rows[0]["block_reasons"]


def test_wavecount_used_as_filter_true_blocks(tmp_path: Path) -> None:
    row = _ledger_row(check_updates={"wavecount_used_as_filter": True})
    result = _run(tmp_path, [row])

    assert "wavecount_used_as_filter_invalid" in result.blocked_rows[0]["block_reasons"]


def test_dry_run_order_intent_without_riskguard_accepted_blocks(tmp_path: Path) -> None:
    row = _ledger_row(
        dry_run_decision="dry_run_order_intent",
        riskguard_status="riskguard_rejected",
        riskguard_reason="risk_limit",
        would_create_order_intent=True,
    )
    result = _run(tmp_path, [row])

    assert "riskguard_not_accepted_for_intent" in result.blocked_rows[0]["block_reasons"]


def test_duplicate_idempotency_key_same_hash_does_not_block(tmp_path: Path) -> None:
    row = _ledger_row()
    result = _run(tmp_path, [row, dict(row)])

    assert result.run_meta["future_write_candidates_count"] == 2
    assert result.run_meta["blocked_count"] == 0
    assert any("duplicate_same_hash" in row["warning_reasons"] for row in result.preflight_rows)


def test_duplicate_idempotency_key_different_hash_blocks(tmp_path: Path) -> None:
    first = _ledger_row()
    second = _ledger_row(dry_run_reason="changed_reason")
    result = _run(tmp_path, [first, second])

    assert result.run_meta["idempotency_conflicts_count"] == 1
    assert any("idempotency_conflict" in row["block_reasons"] for row in result.blocked_rows)


def test_ddl_sql_txt_without_warning_blocks(tmp_path: Path) -> None:
    result = _run(tmp_path, [_ledger_row()], design_dir=_write_design_dir(tmp_path, warning=False))

    assert result.blocked_rows
    assert "ddl_draft_invalid" in result.blocked_rows[0]["block_reasons"]


def test_executable_sql_present_blocks(tmp_path: Path) -> None:
    result = _run(tmp_path, [_ledger_row()], design_dir=_write_design_dir(tmp_path, executable_sql=True))

    assert result.blocked_rows
    assert "ddl_draft_invalid" in result.blocked_rows[0]["block_reasons"]


def test_no_db_sql_mt5_or_telegram_side_effect_flags(tmp_path: Path) -> None:
    result = _run(tmp_path, [_ledger_row()])
    meta = result.run_meta

    assert meta["sql_runtime_ledger_preflight_implemented"] is True
    assert meta["sql_runtime_ledger_writer_implemented"] is False
    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["db_connected"] is False
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False
    assert meta["backtests_executed"] is False


def test_empty_ledger_requires_allow_empty_ledger(tmp_path: Path) -> None:
    blocked = _run(tmp_path, [])
    allowed = _run(tmp_path / "allowed", [], options=SqlRuntimeLedgerPreflightOptions(allow_empty_ledger=True))

    assert blocked.decision == "sql_runtime_ledger_preflight_v1_blocked_by_contract"
    assert allowed.decision == "sql_runtime_ledger_preflight_v1_ready_for_writer_design"
    assert allowed.run_meta["ledger_rows"] == 0


def test_runtime_mode_not_dry_run_blocks(tmp_path: Path) -> None:
    result = _run(tmp_path, [_ledger_row()], options=SqlRuntimeLedgerPreflightOptions(runtime_mode="live"))

    assert "runtime_mode_not_dry_run" in result.blocked_rows[0]["block_reasons"]


def test_source_artifact_missing_is_warning_by_default_and_blocked_in_strict_mode(tmp_path: Path) -> None:
    row = _ledger_row(source_artifacts="artifacts/tfg/old_missing/path.csv")
    warning_result = _run(tmp_path / "warn", [row])
    strict_result = _run(
        tmp_path / "strict",
        [row],
        options=SqlRuntimeLedgerPreflightOptions(strict_artifacts=True),
    )

    assert warning_result.accepted_rows
    assert "source_artifact_historical_path_not_found" in warning_result.accepted_rows[0]["warning_reasons"]
    assert strict_result.blocked_rows
    assert "source_artifact_missing" in strict_result.blocked_rows[0]["block_reasons"]


def _run(
    root: Path,
    rows: list[dict[str, object]],
    *,
    options: SqlRuntimeLedgerPreflightOptions | None = None,
    design_dir: Path | None = None,
):
    ledger_dir = _write_ledger_dir(root, rows)
    return _run_with_dirs(root, ledger_dir, design_dir or _write_design_dir(root), options=options)


def _run_with_dirs(
    root: Path,
    ledger_dir: Path,
    design_dir: Path,
    *,
    options: SqlRuntimeLedgerPreflightOptions | None = None,
):
    return build_sql_runtime_ledger_preflight(
        SqlRuntimeLedgerPreflightConfig(
            ledger_dir=ledger_dir,
            design_dir=design_dir,
            output_dir=root / "out",
            doc_path=root / "doc.md",
        ),
        options or SqlRuntimeLedgerPreflightOptions(),
    )


def _write_ledger_dir(root: Path, rows: list[dict[str, object]], columns: list[str] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.csv"
    source.write_text("source\nok\n", encoding="utf-8")
    normalized = []
    for row in rows:
        current = dict(row)
        if not current.get("source_artifacts"):
            current["source_artifacts"] = str(source)
        normalized.append(current)
    ledger_dir = root / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    selected_columns = columns or REQUIRED_LEDGER_COLUMNS
    with (ledger_dir / "dry_run_decision_ledger.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=selected_columns, extrasaction="ignore")
        writer.writeheader()
        for row in normalized:
            writer.writerow(row)
    (ledger_dir / "dry_run_decision_ledger.json").write_text(
        json.dumps(normalized, indent=2),
        encoding="utf-8",
    )
    (ledger_dir / "run_meta.json").write_text("{}", encoding="utf-8")
    return ledger_dir


def _write_design_dir(root: Path, *, warning: bool = True, executable_sql: bool = False) -> Path:
    design_dir = root / "design"
    tables = design_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "sql_runtime_ledger_field_contract.csv").write_text(
        "field_name,source_field,target_entity,target_column,data_type_suggested,required,nullable,validation,safety_note\n"
        "idempotency_key,future_generated,runtime_decision_event,idempotency_key,varchar,yes,no,key,dedup\n"
        "payload_hash,future_generated,runtime_decision_event,payload_hash,char,yes,no,hash,hash\n"
        "schema_version,future_generated,all,schema_version,varchar,yes,no,version,version\n",
        encoding="utf-8",
    )
    for name in [
        "sql_runtime_preflight_contract.csv",
        "sql_runtime_safety_policy.csv",
        "sql_runtime_append_only_policy.csv",
    ]:
        (tables / name).write_text("name,status\nplaceholder,pass\n", encoding="utf-8")
    warning_line = "-- NO EJECUTAR. DISENO DOCUMENTAL.\n" if warning else "-- DRAFT ONLY.\n"
    (design_dir / "SQL_RUNTIME_LEDGER_V1_DDL_DRAFT.sql.txt").write_text(
        warning_line + "-- commented draft\n",
        encoding="utf-8",
    )
    if executable_sql:
        (design_dir / "SQL_RUNTIME_LEDGER_V1_DDL_DRAFT.sql").write_text("create table unsafe(id int);\n", encoding="utf-8")
    return design_dir


def _ledger_row(**overrides: object) -> dict[str, object]:
    safety_updates = overrides.pop("safety_updates", {})
    check_updates = overrides.pop("check_updates", {})
    safety = {
        "would_send_to_mt5": False,
        "would_send_telegram_order": False,
        "can_execute_order": False,
        "is_simulation": True,
        "wavecount_used_as_filter": False,
    }
    safety.update(safety_updates)  # type: ignore[arg-type]
    checks = {
        "config_pass": False,
        "signal_state_pass": False,
        "freshness_pass": False,
        "riskguard_pass": False,
        "filters_pass": False,
        "max_intents_pass": False,
        "wavecount_used_as_filter": False,
    }
    checks.update(check_updates)  # type: ignore[arg-type]
    row: dict[str, object] = {
        "dry_run_event_id": "dryrun_fixture_1",
        "generated_at": "2026-05-29T10:00:00",
        "snapshot_id": "snapshot_test",
        "symbol": "EURUSD.r",
        "market_group": "Forex Majors",
        "timeframe": "H1",
        "higher_timeframe": "H4",
        "setup_id": "setup_1",
        "strategy": "enbolsa:macd_breakout",
        "signal_state": "watching_setup",
        "side": "BUY",
        "entry": "",
        "sl": "",
        "tp1": "",
        "tp2": "",
        "riskguard_status": "not_evaluated",
        "riskguard_reason": "not_available",
        "dry_run_decision": "dry_run_blocked_by_config",
        "dry_run_reason": "bot_enabled_false",
        "would_create_order_intent": False,
        "would_send_to_mt5": safety["would_send_to_mt5"],
        "would_send_telegram_order": safety["would_send_telegram_order"],
        "can_execute_order": safety["can_execute_order"],
        "is_simulation": safety["is_simulation"],
        "wavecount_context_summary": "wavecount_context_status=not_available",
        "source_artifacts": "",
        "payload_json": json.dumps(
            {
                "checks": checks,
                "options": {"bot_enabled": False, "mode": "off"},
                "safety_flags": safety,
            },
            sort_keys=True,
        ),
    }
    row.update(overrides)
    return row
