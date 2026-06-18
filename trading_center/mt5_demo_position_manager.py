"""Fail-closed demo position close manager with manual-confirmation gates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/mt5_demo_position_manager_v1_2026-06-08")
DEFAULT_DOC_PATH = Path("docs/MT5_DEMO_POSITION_MANAGER_V1.md")
DEFAULT_ACCOUNT = Path("artifacts/tfg/mt5_read_only_connection_v1_2026-06-08_autotrading_retest_after/mt5_account_snapshot.csv")
DEFAULT_POSITIONS = Path("artifacts/tfg/mt5_read_only_connection_v1_2026-06-08_autotrading_retest_after/mt5_positions_snapshot.csv")
DEFAULT_CONFIRMATIONS = Path("artifacts/tfg/mt5_demo_position_manager_v1_2026-06-08/manual_position_confirmations.csv")

MANAGER_ENV = "MT5_DEMO_POSITION_MANAGER_ENABLED"
DEMO_ENV = "MT5_DEMO_TRADING_ENABLED"
LIVE_BLOCK_ENV = "MT5_LIVE_TRADING_BLOCKED"
MT5_SUCCESS_RETCODES = {10008, 10009}

REQUEST_COLUMNS = [
    "request_id",
    "position_id_hash",
    "symbol",
    "direction",
    "volume",
    "action",
    "manual_confirmation_id",
    "request_status",
    "close_requested",
    "position_closed",
    "created_at_utc",
]

RESULT_COLUMNS = [
    "result_id",
    "request_id",
    "position_id_hash",
    "symbol",
    "result_status",
    "mt5_retcode",
    "mt5_order_id_hash",
    "mt5_deal_id_hash",
    "error_message",
    "position_closed",
    "created_at_utc",
]


@dataclass(frozen=True)
class Mt5DemoPositionManagerConfig:
    """Configuration gates for controlled demo-position close requests."""
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    mt5_account_snapshot_csv: Path = DEFAULT_ACCOUNT
    mt5_positions_snapshot_csv: Path = DEFAULT_POSITIONS
    manual_confirmations_csv: Path = DEFAULT_CONFIRMATIONS
    audit_only: bool = True
    dry_run: bool = False
    fixture_mode: bool = False
    connect: bool = False
    close_demo_positions: bool = False
    symbol: str = ""
    require_manual_confirmation: bool = True
    allow_missing_inputs: bool = False


@dataclass(frozen=True)
class Mt5DemoPositionManagerResult:
    """Audit result for one demo-position manager run."""
    decision: str
    output_dir: Path
    run_meta: dict[str, Any]
    request_rows: list[dict[str, Any]]
    result_rows: list[dict[str, Any]]


def execute(config: Mt5DemoPositionManagerConfig) -> Mt5DemoPositionManagerResult:
    """Prepare/execute demo close requests only when every gate passes."""
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()

    if config.fixture_mode:
        account_rows, position_rows, confirmation_rows = fixture_inputs(created_at)
        input_audit = [{"source": "fixture", "path": "in_memory", "rows": len(position_rows), "status": "loaded"}]
    else:
        account_rows, position_rows, confirmation_rows, input_audit = load_inputs(config)

    if config.symbol:
        position_rows = [row for row in position_rows if text(row.get("symbol")) == config.symbol]
    account = first_row(account_rows)
    env_rows, env_ok = evaluate_env_gates(config)
    account_rows_audit, account_ok = evaluate_account_gate(account)
    confirmations = {text(row.get("position_id_hash")): row for row in confirmation_rows if text(row.get("position_id_hash"))}
    symbol_counts = count_by_symbol(position_rows)

    request_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    preflight_rows: list[dict[str, Any]] = []

    for position in position_rows:
        confirmation = confirmations.get(text(position.get("position_id_hash")), {})
        actual_close_requested = config.close_demo_positions and config.connect and not config.audit_only and not config.dry_run
        checks = preflight_checks(
            position=position,
            confirmation=confirmation,
            require_manual_confirmation=config.require_manual_confirmation,
            account_ok=account_ok,
            env_ok=env_ok,
            close_requested=actual_close_requested,
            symbol_position_count=symbol_counts.get(text(position.get("symbol")), 0),
        )
        preflight_rows.extend(checks)
        blocking = first_blocking_reason(checks)
        if blocking:
            result_rows.append(blocked_result(position, blocking, created_at))
            continue
        request = build_close_request(position, confirmation, created_at, config.close_demo_positions)
        request_rows.append(request)
        if config.close_demo_positions and config.connect and not config.audit_only and not config.dry_run:
            result_rows.append(close_with_mt5(request, created_at))
        else:
            result_rows.append(not_closed_result(request, created_at, config))

    issues = issues_or_risks(input_audit, env_rows, account_rows_audit, request_rows, result_rows)
    safety_rows = safety_audit(config, request_rows, result_rows)
    write_csv(output_dir / "demo_position_close_requests.csv", request_rows, REQUEST_COLUMNS)
    write_json(output_dir / "demo_position_close_requests.json", request_rows)
    write_csv(output_dir / "demo_position_close_results.csv", result_rows, RESULT_COLUMNS)
    write_json(output_dir / "demo_position_close_results.json", result_rows)
    write_csv(tables_dir / "input_audit.csv", input_audit)
    write_csv(tables_dir / "preflight_audit.csv", preflight_rows)
    write_csv(tables_dir / "environment_gate_audit.csv", env_rows)
    write_csv(tables_dir / "account_gate_audit.csv", account_rows_audit)
    write_csv(tables_dir / "safety_audit.csv", safety_rows)
    write_csv(tables_dir / "issues_or_risks.csv", issues)

    closed_count = sum(1 for row in result_rows if boolish(row.get("position_closed")))
    decision = "mt5_demo_position_manager_v1_ready_for_manual_demo_review"
    if closed_count:
        decision = "mt5_demo_position_manager_v1_demo_position_closed_review_required"
    elif any(text(row.get("mt5_retcode")) == "10027" for row in result_rows):
        decision = "mt5_demo_position_manager_v1_blocked_by_terminal_autotrading"
    elif not position_rows:
        decision = "mt5_demo_position_manager_v1_no_positions_to_manage"
    run_meta = {
        "phase": "mt5_demo_position_manager_v1",
        "created_at_utc": created_at.isoformat(),
        "decision": decision,
        "mt5_demo_position_manager_implemented": True,
        "artifact_first": True,
        "audit_only": bool(config.audit_only),
        "dry_run": bool(config.dry_run),
        "fixture_mode": bool(config.fixture_mode),
        "connect_requested": bool(config.connect),
        "close_demo_positions_requested": bool(config.close_demo_positions),
        "manual_confirmation_required": bool(config.require_manual_confirmation),
        "environment_gates_passed": bool(env_ok),
        "account_demo_gate_passed": bool(account_ok),
        "positions_seen": len(position_rows),
        "close_requests_prepared": len(request_rows),
        "close_results_count": len(result_rows),
        "positions_closed": closed_count,
        "mt5_positions_closed": closed_count,
        "live_trading_enabled": False,
        "telegram_connected": False,
        "telegram_can_trade": False,
        "sql_real_written": False,
        "backtests_executed": False,
    }
    write_json(output_dir / "run_meta.json", run_meta)
    write_doc(output_dir / "MT5_DEMO_POSITION_MANAGER_V1.md", run_meta, issues)
    if config.doc_path:
        write_doc(config.doc_path, run_meta, issues)
    return Mt5DemoPositionManagerResult(decision, output_dir, run_meta, request_rows, result_rows)


def load_inputs(
    config: Mt5DemoPositionManagerConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    specs = [
        ("mt5_account_snapshot", config.mt5_account_snapshot_csv),
        ("mt5_positions_snapshot", config.mt5_positions_snapshot_csv),
        ("manual_confirmations", config.manual_confirmations_csv),
    ]
    loaded: dict[str, list[dict[str, Any]]] = {}
    audit: list[dict[str, Any]] = []
    for source_id, path in specs:
        if path.exists():
            rows = read_csv(path)
            loaded[source_id] = rows
            audit.append({"source": source_id, "path": str(path), "rows": len(rows), "status": "loaded"})
        else:
            loaded[source_id] = []
            status = "optional_missing" if config.allow_missing_inputs or source_id == "manual_confirmations" else "missing"
            audit.append({"source": source_id, "path": str(path), "rows": 0, "status": status})
    return loaded["mt5_account_snapshot"], loaded["mt5_positions_snapshot"], loaded["manual_confirmations"], audit


def fixture_inputs(created_at: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    position_id = "fixture-position-hash"
    account = {
        "account_label": "demo_fixture",
        "server_name_sanitized": "Fixture-Demo",
        "equity": "10000",
        "mt5_connected": "false",
        "read_only": "true",
    }
    position = {
        "position_id_hash": position_id,
        "symbol": "EURUSD.r",
        "direction": "long",
        "volume": "0.01",
        "open_price": "1.1000",
        "current_price": "1.1010",
        "sl": "1.0950",
        "tp": "1.1100",
        "can_modify_position": "false",
    }
    confirmation = {
        "manual_confirmation_id": "fixture-position-close-confirmation",
        "position_id_hash": position_id,
        "status": "confirmed",
        "confirmed_at": created_at.isoformat(),
        "expires_at": "",
    }
    return [account], [position], [confirmation]


def preflight_checks(
    *,
    position: Mapping[str, Any],
    confirmation: Mapping[str, Any],
    require_manual_confirmation: bool,
    account_ok: bool,
    env_ok: bool,
    close_requested: bool,
    symbol_position_count: int,
) -> list[dict[str, Any]]:
    return [
        check(position, "symbol_present", has_value(position.get("symbol")), "blocked_by_missing_symbol"),
        check(position, "volume_present", safe_float(position.get("volume")) > 0, "blocked_by_missing_volume"),
        check(position, "single_position_per_symbol", symbol_position_count <= 1, "blocked_by_multiple_positions_same_symbol"),
        check(position, "account_demo", account_ok, "blocked_by_no_demo_account"),
        check(position, "manual_confirmation", (not require_manual_confirmation) or text(confirmation.get("status")) == "confirmed", "blocked_by_missing_manual_confirmation"),
        check(position, "environment_gates", (not close_requested) or env_ok, "blocked_by_environment_gates"),
    ]


def count_by_symbol(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        symbol = text(row.get("symbol"))
        if symbol:
            counts[symbol] = counts.get(symbol, 0) + 1
    return counts


def check(position: Mapping[str, Any], check_id: str, passed: bool, decision_if_failed: str) -> dict[str, Any]:
    return {
        "position_id_hash": text(position.get("position_id_hash")),
        "symbol": text(position.get("symbol")),
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "decision_if_failed": "" if passed else decision_if_failed,
    }


def first_blocking_reason(checks: Sequence[Mapping[str, Any]]) -> str:
    for row in checks:
        if row.get("status") == "fail":
            return text(row.get("decision_if_failed"))
    return ""


def build_close_request(position: Mapping[str, Any], confirmation: Mapping[str, Any], created_at: datetime, close_requested: bool) -> dict[str, Any]:
    return {
        "request_id": "close-request-" + stable_hash({"position": position, "created_at": created_at.isoformat()})[:16],
        "position_id_hash": text(position.get("position_id_hash")),
        "symbol": text(position.get("symbol")),
        "direction": text(position.get("direction")),
        "volume": text(position.get("volume")),
        "action": "close_demo_position",
        "manual_confirmation_id": text(confirmation.get("manual_confirmation_id")),
        "request_status": "ready_to_close_demo" if close_requested else "prepared_dry_run",
        "close_requested": bool(close_requested),
        "position_closed": False,
        "created_at_utc": created_at.isoformat(),
    }


def blocked_result(position: Mapping[str, Any], reason: str, created_at: datetime) -> dict[str, Any]:
    return {
        "result_id": "close-result-" + stable_hash({"position": position, "reason": reason})[:16],
        "request_id": "",
        "position_id_hash": text(position.get("position_id_hash")),
        "symbol": text(position.get("symbol")),
        "result_status": reason,
        "mt5_retcode": "",
        "mt5_order_id_hash": "",
        "mt5_deal_id_hash": "",
        "error_message": reason,
        "position_closed": False,
        "created_at_utc": created_at.isoformat(),
    }


def not_closed_result(request: Mapping[str, Any], created_at: datetime, config: Mt5DemoPositionManagerConfig) -> dict[str, Any]:
    if config.audit_only:
        status = "not_closed_audit_only"
    elif config.dry_run:
        status = "not_closed_dry_run"
    elif not config.close_demo_positions:
        status = "not_closed_close_flag_false"
    else:
        status = "not_closed_preflight_only"
    return {
        "result_id": "close-result-" + stable_hash({"request": request, "status": status})[:16],
        "request_id": text(request.get("request_id")),
        "position_id_hash": text(request.get("position_id_hash")),
        "symbol": text(request.get("symbol")),
        "result_status": status,
        "mt5_retcode": "",
        "mt5_order_id_hash": "",
        "mt5_deal_id_hash": "",
        "error_message": "",
        "position_closed": False,
        "created_at_utc": created_at.isoformat(),
    }


def close_with_mt5(request: Mapping[str, Any], created_at: datetime) -> dict[str, Any]:
    try:
        mt5 = import_mt5()
        if not mt5.initialize():
            raise RuntimeError("mt5_initialize_failed")
        symbol = text(request.get("symbol"))
        positions = tuple(mt5.positions_get(symbol=symbol) or ())
        if not positions:
            raise RuntimeError("mt5_position_not_found")
        target_hash = text(request.get("position_id_hash"))
        matching_positions = [
            item
            for item in positions
            if readonly_ticket_hash(getattr(item, "ticket", getattr(item, "identifier", ""))) == target_hash
        ]
        if not matching_positions:
            raise RuntimeError("mt5_position_hash_not_found")
        if len(matching_positions) > 1:
            raise RuntimeError("mt5_position_hash_not_unique")
        target = matching_positions[0]
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError("mt5_tick_unavailable")
        is_long = int(getattr(target, "type", 0) or 0) == getattr(mt5, "POSITION_TYPE_BUY")
        order_type = getattr(mt5, "ORDER_TYPE_SELL") if is_long else getattr(mt5, "ORDER_TYPE_BUY")
        price = float(tick.bid if is_long else tick.ask)
        payload = {
            "action": getattr(mt5, "TRADE_ACTION_DEAL"),
            "symbol": symbol,
            "volume": float(getattr(target, "volume")),
            "type": order_type,
            "position": int(getattr(target, "ticket")),
            "price": price,
            "deviation": 20,
            "magic": 26060802,
            "comment": "TFG demo close",
        }
        if hasattr(mt5, "ORDER_TIME_GTC"):
            payload["type_time"] = getattr(mt5, "ORDER_TIME_GTC")
        if hasattr(mt5, "ORDER_FILLING_IOC"):
            payload["type_filling"] = getattr(mt5, "ORDER_FILLING_IOC")
        result = mt5.order_send(payload)
        retcode_value = int(getattr(result, "retcode", 0) or 0)
        retcode = str(retcode_value) if retcode_value else ""
        order_id = text(getattr(result, "order", ""))
        deal_id = text(getattr(result, "deal", ""))
        order_positive = order_id not in {"", "0"}
        deal_positive = deal_id not in {"", "0"}
        closed = retcode_value in MT5_SUCCESS_RETCODES and bool(order_positive or deal_positive)
        return {
            "result_id": "close-result-" + stable_hash({"request": request, "retcode": retcode, "order": order_id, "deal": deal_id})[:16],
            "request_id": text(request.get("request_id")),
            "position_id_hash": text(request.get("position_id_hash")),
            "symbol": symbol,
            "result_status": "closed_in_mt5_demo" if closed else f"mt5_close_rejected_retcode_{retcode or 'unknown'}",
            "mt5_retcode": retcode,
            "mt5_order_id_hash": hash_secret(order_id) if order_positive else "",
            "mt5_deal_id_hash": hash_secret(deal_id) if deal_positive else "",
            "error_message": "",
            "position_closed": closed,
            "created_at_utc": created_at.isoformat(),
        }
    except Exception as exc:  # pragma: no cover - real MT5 path is local/manual only.
        return {
            "result_id": "close-result-" + stable_hash({"request": request, "error": exc.__class__.__name__})[:16],
            "request_id": text(request.get("request_id")),
            "position_id_hash": text(request.get("position_id_hash")),
            "symbol": text(request.get("symbol")),
            "result_status": "mt5_close_failed",
            "mt5_retcode": "",
            "mt5_order_id_hash": "",
            "mt5_deal_id_hash": "",
            "error_message": f"{exc.__class__.__name__}: {exc}",
            "position_closed": False,
            "created_at_utc": created_at.isoformat(),
        }
    finally:
        try:
            mt5.shutdown()  # type: ignore[name-defined]
        except Exception:
            pass


def evaluate_env_gates(config: Mt5DemoPositionManagerConfig) -> tuple[list[dict[str, Any]], bool]:
    rows = [
        env_check(MANAGER_ENV, "1"),
        env_check(DEMO_ENV, "1"),
        env_check(LIVE_BLOCK_ENV, "1"),
        {"check": "close_flag", "expected": True, "observed": bool(config.close_demo_positions), "status": "pass" if config.close_demo_positions else "blocked"},
        {"check": "connect_flag", "expected": True, "observed": bool(config.connect), "status": "pass" if config.connect else "blocked"},
        {"check": "not_audit_only", "expected": True, "observed": not config.audit_only, "status": "pass" if not config.audit_only else "blocked"},
        {"check": "not_dry_run", "expected": True, "observed": not config.dry_run, "status": "pass" if not config.dry_run else "blocked"},
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def evaluate_account_gate(account: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    label = text(account.get("account_label")).lower()
    server = text(account.get("server_name_sanitized")).lower()
    mode = text(account.get("account_mode")).lower()
    is_demo = mode == "demo" or "demo" in label or "demo" in server
    rows = [{"check": "account_is_demo", "expected": True, "observed": is_demo, "status": "pass" if is_demo else "blocked"}]
    return rows, is_demo


def env_check(name: str, expected: str) -> dict[str, Any]:
    observed = os.environ.get(name, "")
    return {"check": name, "expected": expected, "observed": observed == expected, "status": "pass" if observed == expected else "blocked"}


def safety_audit(
    config: Mt5DemoPositionManagerConfig,
    request_rows: Sequence[Mapping[str, Any]],
    result_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {"check": "audit_default", "observed": bool(config.audit_only), "expected": True, "status": "pass" if config.audit_only else "review"},
        {"check": "positions_closed", "observed": sum(1 for row in result_rows if boolish(row.get("position_closed"))), "expected": 0 if not config.close_demo_positions else "manual_demo_only", "status": "pass" if not any(boolish(row.get("position_closed")) for row in result_rows) else "review_required"},
        {"check": "live_trading_enabled", "observed": False, "expected": False, "status": "pass"},
        {"check": "telegram_connected", "observed": False, "expected": False, "status": "pass"},
        {"check": "sql_real_written", "observed": False, "expected": False, "status": "pass"},
        {"check": "requests_prepared", "observed": len(request_rows), "expected": "audit", "status": "pass"},
    ]


def issues_or_risks(
    input_audit: Sequence[Mapping[str, Any]],
    env_rows: Sequence[Mapping[str, Any]],
    account_rows: Sequence[Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]],
    result_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if any(row.get("status") == "missing" for row in input_audit):
        issues.append({"issue_id": "missing_required_input", "severity": "high", "description": "Required account or position snapshot is missing.", "recommended_action": "Regenerate MT5 read-only snapshot."})
    if any(row.get("status") != "pass" for row in env_rows):
        issues.append({"issue_id": "environment_gates_closed", "severity": "info", "description": "Demo position management gates are closed.", "recommended_action": "Keep closed outside explicit local demo review."})
    if any(row.get("status") != "pass" for row in account_rows):
        issues.append({"issue_id": "demo_account_not_confirmed", "severity": "high", "description": "Account snapshot does not prove demo mode.", "recommended_action": "Use demo read-only snapshot."})
    if not request_rows:
        issues.append({"issue_id": "no_close_requests_prepared", "severity": "info", "description": "No position passed close preflight.", "recommended_action": "Review position snapshot and confirmation."})
    if any(boolish(row.get("position_closed")) for row in result_rows):
        issues.append({"issue_id": "demo_position_closed_review_required", "severity": "high", "description": "A demo position was closed and must be reviewed.", "recommended_action": "Audit MT5 result and account state."})
    if not issues:
        issues.append({"issue_id": "no_runtime_issues", "severity": "info", "description": "Position manager completed with fail-closed controls.", "recommended_action": "Proceed only with explicit demo review."})
    return issues


def import_mt5() -> Any:
    import MetaTrader5 as mt5  # type: ignore

    return mt5


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns or sorted({key for row in rows for key in row.keys()}))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_doc(path: Path, run_meta: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]) -> None:
    body = f"""# MT5 demo position manager v1

## Que implementa

Gestion/cierre demo controlado para completar el ciclo minimo posterior al
sender demo. Lee snapshots MT5 read-only, exige cuenta demo y confirmacion
manual, y solo puede cerrar posiciones demo si se activan flags de CLI y
entorno.

## Comandos

Dry-run:

```powershell
python -m trading_center.mt5_demo_position_manager --dry-run --close-demo-positions --connect
```

Cierre demo manual:

```powershell
$env:{MANAGER_ENV}="1"
$env:{DEMO_ENV}="1"
$env:{LIVE_BLOCK_ENV}="1"
python -m trading_center.mt5_demo_position_manager --connect --close-demo-positions
```

## Resultado

- Decision: `{run_meta.get('decision')}`
- Posiciones vistas: {run_meta.get('positions_seen')}
- Requests preparados: {run_meta.get('close_requests_prepared')}
- Posiciones cerradas: {run_meta.get('positions_closed')}

## Seguridad

- Live trading: `false`
- Telegram: `false`
- SQL writes: `false`
- Backtests: `false`
- Confirmacion manual requerida: `{run_meta.get('manual_confirmation_required')}`
- Varias posiciones del mismo simbolo bloquean por ambiguedad: `true`

## Issues

{chr(10).join(f"- {row.get('issue_id')}: {row.get('description')}" for row in issues)}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def first_row(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return rows[0] if rows else {}


def text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def has_value(value: Any) -> bool:
    return text(value) not in {"", "nan", "None", "null"}


def boolish(value: Any) -> bool:
    return text(value).lower() in {"1", "true", "yes", "y", "si"}


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def readonly_ticket_hash(value: Any) -> str:
    """Mirror mt5_read_only.stable_hash(str(ticket)) for exact position matching."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed MT5 demo position manager.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--mt5-account-snapshot-csv", type=Path, default=DEFAULT_ACCOUNT)
    parser.add_argument("--mt5-positions-snapshot-csv", type=Path, default=DEFAULT_POSITIONS)
    parser.add_argument("--manual-confirmations-csv", type=Path, default=DEFAULT_CONFIRMATIONS)
    parser.add_argument("--audit-only", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--close-demo-positions", action="store_true")
    parser.add_argument("--symbol", default="")
    parser.add_argument("--no-manual-confirmation-required", action="store_true")
    parser.add_argument("--allow-missing-inputs", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Mt5DemoPositionManagerConfig(
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        mt5_account_snapshot_csv=args.mt5_account_snapshot_csv,
        mt5_positions_snapshot_csv=args.mt5_positions_snapshot_csv,
        manual_confirmations_csv=args.manual_confirmations_csv,
        audit_only=bool(args.audit_only or not args.close_demo_positions),
        dry_run=bool(args.dry_run),
        fixture_mode=bool(args.fixture_mode),
        connect=bool(args.connect),
        close_demo_positions=bool(args.close_demo_positions),
        symbol=str(args.symbol or ""),
        require_manual_confirmation=not bool(args.no_manual_confirmation_required),
        allow_missing_inputs=bool(args.allow_missing_inputs),
    )
    result = execute(config)
    print(json.dumps(result.run_meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
