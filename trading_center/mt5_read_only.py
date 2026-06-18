from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/mt5_read_only_connection_v1_2026-06-07")
DEFAULT_DOC_PATH = Path("docs/MT5_READ_ONLY_CONNECTION_V1.md")
READ_ONLY_ENV = "MT5_READ_ONLY_ENABLED"
TRADING_DISABLED_ENV = "MT5_TRADING_DISABLED"

ACCOUNT_COLUMNS = [
    "account_id_hash",
    "account_label",
    "broker_name_sanitized",
    "server_name_sanitized",
    "currency",
    "balance",
    "equity",
    "margin",
    "free_margin",
    "margin_level",
    "open_positions_count",
    "pending_orders_count",
    "floating_pnl",
    "closed_pnl_day",
    "read_timestamp_utc",
    "mt5_connected",
    "read_only",
    "can_send_order",
]

POSITION_COLUMNS = [
    "position_id_hash",
    "symbol",
    "direction",
    "volume",
    "open_time",
    "open_price",
    "current_price",
    "sl",
    "tp",
    "floating_pnl",
    "pnl_pct_equity",
    "magic_number",
    "comment_sanitized",
    "source",
    "can_modify_position",
    "can_send_order",
]

PENDING_COLUMNS = [
    "pending_order_id_hash",
    "symbol",
    "direction",
    "volume",
    "open_time",
    "price_open",
    "sl",
    "tp",
    "magic_number",
    "comment_sanitized",
    "source",
    "can_modify_order",
    "can_send_order",
]


@dataclass(frozen=True)
class Mt5ReadOnlyConfig:
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    audit_only: bool = False
    fixture_mode: bool = False
    connect: bool = False
    include_history: bool = False
    history_days: int = 7
    account_label: str = "mt5_read_only"
    allow_missing_mt5: bool = False


@dataclass(frozen=True)
class Mt5ReadOnlyResult:
    decision: str
    output_dir: Path
    run_meta: dict[str, Any]
    account_rows: list[dict[str, Any]]
    position_rows: list[dict[str, Any]]
    pending_order_rows: list[dict[str, Any]]


def execute(config: Mt5ReadOnlyConfig) -> Mt5ReadOnlyResult:
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    read_time = datetime.now(timezone.utc).replace(microsecond=0)

    connection_audit: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    mt5_connected = False
    connection_attempted = False
    terminal_info: Any = None
    account_info: Any = None
    positions: Sequence[Any] = []
    pending_orders: Sequence[Any] = []
    history_orders: Sequence[Any] = []
    history_deals: Sequence[Any] = []
    decision = "mt5_read_only_connection_v1_ready_for_local_readonly_review"

    if config.audit_only:
        connection_audit.append(
            {
                "check": "audit_only",
                "status": "passed",
                "reason": "audit_only_no_mt5_import_no_connection",
                "mt5_connection_attempted": False,
            }
        )
        account_rows, position_rows, pending_order_rows = build_empty_snapshots(config, read_time, mt5_connected=False)
    elif config.fixture_mode:
        connection_audit.append(
            {
                "check": "fixture_mode",
                "status": "passed",
                "reason": "fixture_snapshots_without_mt5_connection",
                "mt5_connection_attempted": False,
            }
        )
        account_rows, position_rows, pending_order_rows = build_fixture_snapshots(config, read_time)
    elif not config.connect:
        connection_audit.append(
            {
                "check": "connect_flag",
                "status": "blocked",
                "reason": "connect_flag_false_default_no_connection",
                "mt5_connection_attempted": False,
            }
        )
        issues.append(
            {
                "issue_id": "mt5_connection_not_attempted_default",
                "severity": "info",
                "description": "Default run does not connect to MT5; use audit-only, fixture-mode or explicit --connect with env gates.",
                "recommended_action": "Keep default fail-closed.",
            }
        )
        account_rows, position_rows, pending_order_rows = build_empty_snapshots(config, read_time, mt5_connected=False)
    else:
        gate_rows, gate_ok = evaluate_connection_gates()
        connection_audit.extend(gate_rows)
        connection_attempted = gate_ok
        if not gate_ok:
            decision = "mt5_read_only_connection_v1_blocked_by_mt5_environment"
            issues.append(
                {
                    "issue_id": "blocked_by_readonly_config",
                    "severity": "high",
                    "description": "MT5 connection was requested but read-only environment gates were not satisfied.",
                    "recommended_action": f"Set {READ_ONLY_ENV}=1 and {TRADING_DISABLED_ENV}=1 only when read-only review is intended.",
                }
            )
            account_rows, position_rows, pending_order_rows = build_empty_snapshots(config, read_time, mt5_connected=False)
        else:
            try:
                mt5 = import_mt5()
            except Exception as exc:  # pragma: no cover - covered with monkeypatch-friendly tests.
                decision = "mt5_read_only_connection_v1_blocked_by_mt5_environment"
                if not config.allow_missing_mt5:
                    issues.append(
                        {
                            "issue_id": "mt5_package_unavailable",
                            "severity": "high",
                            "description": f"MetaTrader5 package could not be imported: {exc.__class__.__name__}.",
                            "recommended_action": "Install/enable MT5 package only for read-only local review.",
                        }
                    )
                connection_audit.append(
                    {
                        "check": "mt5_import",
                        "status": "blocked",
                        "reason": exc.__class__.__name__,
                        "mt5_connection_attempted": False,
                    }
                )
                account_rows, position_rows, pending_order_rows = build_empty_snapshots(config, read_time, mt5_connected=False)
            else:
                try:
                    mt5_connected = bool(mt5.initialize())
                    connection_audit.append(
                        {
                            "check": "mt5_initialize",
                            "status": "passed" if mt5_connected else "blocked",
                            "reason": "connected_read_only" if mt5_connected else "initialize_returned_false",
                            "mt5_connection_attempted": True,
                        }
                    )
                    if mt5_connected:
                        terminal_info = safe_call(lambda: mt5.terminal_info())
                        account_info = safe_call(lambda: mt5.account_info())
                        positions = tuple(safe_call(lambda: mt5.positions_get()) or ())
                        pending_orders = tuple(safe_call(lambda: mt5.orders_get()) or ())
                        if config.include_history:
                            since = read_time - timedelta(days=max(1, int(config.history_days)))
                            history_orders = tuple(safe_call(lambda: mt5.history_orders_get(since, read_time)) or ())
                            history_deals = tuple(safe_call(lambda: mt5.history_deals_get(since, read_time)) or ())
                    account_rows, position_rows, pending_order_rows = build_real_snapshots(
                        config,
                        read_time,
                        terminal_info=terminal_info,
                        account_info=account_info,
                        positions=positions,
                        pending_orders=pending_orders,
                        mt5_connected=mt5_connected,
                    )
                finally:
                    safe_call(lambda: mt5.shutdown())

    exposure_rows = build_exposure_audit(position_rows)
    safety_rows = build_safety_audit(account_rows, position_rows, pending_order_rows)
    secret_rows = build_secret_handling_audit()
    dashboard_rows = build_dashboard_future_integration_audit(output_dir, account_rows, position_rows, pending_order_rows)
    issues.extend(build_runtime_issues(config, account_rows, position_rows, pending_order_rows, mt5_connected))
    if not issues:
        issues.append(
            {
                "issue_id": "no_runtime_issues",
                "severity": "info",
                "description": "No runtime issues detected in read-only artifact generation.",
                "recommended_action": "Proceed to local read-only review if needed.",
            }
        )

    write_csv(output_dir / "mt5_account_snapshot.csv", account_rows, ACCOUNT_COLUMNS)
    write_json(output_dir / "mt5_account_snapshot.json", account_rows)
    write_csv(output_dir / "mt5_positions_snapshot.csv", position_rows, POSITION_COLUMNS)
    write_json(output_dir / "mt5_positions_snapshot.json", position_rows)
    write_csv(output_dir / "mt5_pending_orders_snapshot.csv", pending_order_rows, PENDING_COLUMNS)
    write_json(output_dir / "mt5_pending_orders_snapshot.json", pending_order_rows)
    if config.include_history:
        write_json(output_dir / "mt5_history_orders_snapshot.json", [object_to_mapping(item) for item in history_orders])
        write_json(output_dir / "mt5_history_deals_snapshot.json", [object_to_mapping(item) for item in history_deals])
        write_csv(output_dir / "mt5_history_orders_snapshot.csv", [sanitize_history_row(item, "order") for item in history_orders])
        write_csv(output_dir / "mt5_history_deals_snapshot.csv", [sanitize_history_row(item, "deal") for item in history_deals])

    write_csv(tables_dir / "mt5_connection_policy_audit.csv", connection_audit)
    write_csv(tables_dir / "mt5_exposure_audit.csv", exposure_rows)
    write_csv(tables_dir / "mt5_readonly_safety_audit.csv", safety_rows)
    write_csv(tables_dir / "mt5_secret_handling_audit.csv", secret_rows)
    write_csv(tables_dir / "mt5_dashboard_future_integration_audit.csv", dashboard_rows)
    write_csv(tables_dir / "issues_or_risks.csv", issues)

    manifest = build_manifest(output_dir, read_time, mt5_connected, account_rows, position_rows, pending_order_rows)
    write_json(output_dir / "mt5_readonly_manifest.json", manifest)
    run_meta = build_run_meta(
        config,
        decision,
        read_time,
        mt5_connected=mt5_connected,
        connection_attempted=connection_attempted,
        account_rows=account_rows,
        position_rows=position_rows,
        pending_order_rows=pending_order_rows,
    )
    write_json(output_dir / "run_meta.json", run_meta)
    doc = render_markdown(decision, run_meta, manifest, issues)
    (output_dir / "MT5_READ_ONLY_CONNECTION_V1.md").write_text(doc, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(doc, encoding="utf-8")

    return Mt5ReadOnlyResult(decision, output_dir, run_meta, account_rows, position_rows, pending_order_rows)


def import_mt5() -> Any:
    import importlib

    return importlib.import_module("MetaTrader5")


def evaluate_connection_gates() -> tuple[list[dict[str, Any]], bool]:
    read_only_enabled = truthy(os.getenv(READ_ONLY_ENV))
    trading_disabled = truthy(os.getenv(TRADING_DISABLED_ENV))
    rows = [
        {
            "check": READ_ONLY_ENV,
            "status": "passed" if read_only_enabled else "blocked",
            "reason": "read_only_gate_enabled" if read_only_enabled else "missing_read_only_gate",
            "mt5_connection_attempted": False,
        },
        {
            "check": TRADING_DISABLED_ENV,
            "status": "passed" if trading_disabled else "blocked",
            "reason": "trading_disabled_gate_enabled" if trading_disabled else "missing_trading_disabled_gate",
            "mt5_connection_attempted": False,
        },
        {
            "check": "credentials_via_cli",
            "status": "passed",
            "reason": "cli_has_no_login_password_parameters",
            "mt5_connection_attempted": False,
        },
    ]
    return rows, read_only_enabled and trading_disabled


def build_empty_snapshots(config: Mt5ReadOnlyConfig, read_time: datetime, *, mt5_connected: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    account = {
        "account_id_hash": "not_connected",
        "account_label": config.account_label,
        "broker_name_sanitized": "not_connected",
        "server_name_sanitized": "not_connected",
        "currency": "",
        "balance": 0.0,
        "equity": 0.0,
        "margin": 0.0,
        "free_margin": 0.0,
        "margin_level": 0.0,
        "open_positions_count": 0,
        "pending_orders_count": 0,
        "floating_pnl": 0.0,
        "closed_pnl_day": 0.0,
        "read_timestamp_utc": read_time.isoformat(),
        "mt5_connected": mt5_connected,
        "read_only": True,
        "can_send_order": False,
    }
    return [account], [], []


def build_fixture_snapshots(config: Mt5ReadOnlyConfig, read_time: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    positions = [
        {
            "position_id_hash": stable_hash("fixture-position-1"),
            "symbol": "EURUSD.r",
            "direction": "long",
            "volume": 0.10,
            "open_time": "2026-06-07T08:00:00+00:00",
            "open_price": 1.085,
            "current_price": 1.087,
            "sl": 1.080,
            "tp": 1.095,
            "floating_pnl": 20.0,
            "pnl_pct_equity": 0.20,
            "magic_number": "fixture",
            "comment_sanitized": "fixture_read_only",
            "source": "mt5_read_only",
            "can_modify_position": False,
            "can_send_order": False,
        },
        {
            "position_id_hash": stable_hash("fixture-position-2"),
            "symbol": "XAUUSD.r",
            "direction": "short",
            "volume": 0.02,
            "open_time": "2026-06-07T09:00:00+00:00",
            "open_price": 2350.0,
            "current_price": 2345.0,
            "sl": 2365.0,
            "tp": 2320.0,
            "floating_pnl": 15.0,
            "pnl_pct_equity": 0.15,
            "magic_number": "fixture",
            "comment_sanitized": "fixture_read_only",
            "source": "mt5_read_only",
            "can_modify_position": False,
            "can_send_order": False,
        },
    ]
    pending_orders = [
        {
            "pending_order_id_hash": stable_hash("fixture-pending-1"),
            "symbol": "US100",
            "direction": "buy_limit",
            "volume": 0.01,
            "open_time": "2026-06-07T09:30:00+00:00",
            "price_open": 19000.0,
            "sl": 18800.0,
            "tp": 19300.0,
            "magic_number": "fixture",
            "comment_sanitized": "fixture_read_only",
            "source": "mt5_read_only",
            "can_modify_order": False,
            "can_send_order": False,
        }
    ]
    account = {
        "account_id_hash": stable_hash("fixture-account"),
        "account_label": config.account_label,
        "broker_name_sanitized": "fixture_broker",
        "server_name_sanitized": "fixture_server",
        "currency": "EUR",
        "balance": 10000.0,
        "equity": 10035.0,
        "margin": 250.0,
        "free_margin": 9785.0,
        "margin_level": 4014.0,
        "open_positions_count": len(positions),
        "pending_orders_count": len(pending_orders),
        "floating_pnl": sum(float(row["floating_pnl"]) for row in positions),
        "closed_pnl_day": 0.0,
        "read_timestamp_utc": read_time.isoformat(),
        "mt5_connected": False,
        "read_only": True,
        "can_send_order": False,
    }
    return [account], positions, pending_orders


def build_real_snapshots(
    config: Mt5ReadOnlyConfig,
    read_time: datetime,
    *,
    terminal_info: Any,
    account_info: Any,
    positions: Sequence[Any],
    pending_orders: Sequence[Any],
    mt5_connected: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    position_rows = [sanitize_position(item, account_equity=float_attr(account_info, "equity", 0.0)) for item in positions]
    pending_rows = [sanitize_pending_order(item) for item in pending_orders]
    account_rows = [
        {
            "account_id_hash": stable_hash(str(safe_attr(account_info, "login", "not_available"))),
            "account_label": config.account_label,
            "broker_name_sanitized": sanitize_text(safe_attr(account_info, "company", "not_available")),
            "server_name_sanitized": sanitize_text(safe_attr(account_info, "server", safe_attr(terminal_info, "name", "not_available"))),
            "currency": sanitize_text(safe_attr(account_info, "currency", "")),
            "balance": float_attr(account_info, "balance", 0.0),
            "equity": float_attr(account_info, "equity", 0.0),
            "margin": float_attr(account_info, "margin", 0.0),
            "free_margin": float_attr(account_info, "margin_free", 0.0),
            "margin_level": float_attr(account_info, "margin_level", 0.0),
            "open_positions_count": len(position_rows),
            "pending_orders_count": len(pending_rows),
            "floating_pnl": sum(float(row.get("floating_pnl", 0.0)) for row in position_rows),
            "closed_pnl_day": 0.0,
            "read_timestamp_utc": read_time.isoformat(),
            "mt5_connected": mt5_connected,
            "read_only": True,
            "can_send_order": False,
        }
    ]
    return account_rows, position_rows, pending_rows


def sanitize_position(item: Any, *, account_equity: float) -> dict[str, Any]:
    ticket = safe_attr(item, "ticket", safe_attr(item, "identifier", "not_available"))
    symbol = sanitize_text(safe_attr(item, "symbol", "not_available"))
    volume = float_attr(item, "volume", 0.0)
    profit = float_attr(item, "profit", 0.0)
    current_price = float_attr(item, "price_current", 0.0)
    direction = position_direction(safe_attr(item, "type", ""))
    return {
        "position_id_hash": stable_hash(str(ticket)),
        "symbol": symbol,
        "direction": direction,
        "volume": volume,
        "open_time": epoch_to_iso(safe_attr(item, "time", "")),
        "open_price": float_attr(item, "price_open", 0.0),
        "current_price": current_price,
        "sl": float_attr(item, "sl", 0.0),
        "tp": float_attr(item, "tp", 0.0),
        "floating_pnl": profit,
        "pnl_pct_equity": round((profit / account_equity) * 100, 6) if account_equity else 0.0,
        "magic_number": sanitize_text(safe_attr(item, "magic", "")),
        "comment_sanitized": sanitize_text(safe_attr(item, "comment", "")),
        "source": "mt5_read_only",
        "can_modify_position": False,
        "can_send_order": False,
    }


def sanitize_pending_order(item: Any) -> dict[str, Any]:
    ticket = safe_attr(item, "ticket", "not_available")
    return {
        "pending_order_id_hash": stable_hash(str(ticket)),
        "symbol": sanitize_text(safe_attr(item, "symbol", "not_available")),
        "direction": pending_direction(safe_attr(item, "type", "")),
        "volume": float_attr(item, "volume_initial", float_attr(item, "volume_current", 0.0)),
        "open_time": epoch_to_iso(safe_attr(item, "time_setup", safe_attr(item, "time", ""))),
        "price_open": float_attr(item, "price_open", 0.0),
        "sl": float_attr(item, "sl", 0.0),
        "tp": float_attr(item, "tp", 0.0),
        "magic_number": sanitize_text(safe_attr(item, "magic", "")),
        "comment_sanitized": sanitize_text(safe_attr(item, "comment", "")),
        "source": "mt5_read_only",
        "can_modify_order": False,
        "can_send_order": False,
    }


def sanitize_history_row(item: Any, kind: str) -> dict[str, Any]:
    mapping = object_to_mapping(item)
    return {
        f"{kind}_id_hash": stable_hash(str(mapping.get("ticket") or mapping.get("order") or mapping.get("position_id") or "")),
        "symbol": sanitize_text(mapping.get("symbol", "")),
        "time": epoch_to_iso(mapping.get("time", "")),
        "volume": safe_float(mapping.get("volume", mapping.get("volume_initial", 0.0))),
        "price": safe_float(mapping.get("price", mapping.get("price_open", 0.0))),
        "profit": safe_float(mapping.get("profit", 0.0)),
        "comment_sanitized": sanitize_text(mapping.get("comment", "")),
        "source": "mt5_read_only",
        "can_send_order": False,
    }


def build_exposure_audit(position_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not position_rows:
        return [
            {
                "scope": "portfolio",
                "key": "no_positions",
                "positions_count": 0,
                "long_volume": 0.0,
                "short_volume": 0.0,
                "net_volume": 0.0,
                "floating_pnl": 0.0,
                "status": "passed",
            }
        ]
    grouped: dict[str, dict[str, Any]] = {}
    for row in position_rows:
        symbol = str(row.get("symbol") or "not_available")
        item = grouped.setdefault(
            symbol,
            {
                "scope": "symbol",
                "key": symbol,
                "positions_count": 0,
                "long_volume": 0.0,
                "short_volume": 0.0,
                "net_volume": 0.0,
                "floating_pnl": 0.0,
                "status": "passed",
            },
        )
        volume = safe_float(row.get("volume"))
        if row.get("direction") == "short":
            item["short_volume"] += volume
            item["net_volume"] -= volume
        else:
            item["long_volume"] += volume
            item["net_volume"] += volume
        item["positions_count"] += 1
        item["floating_pnl"] += safe_float(row.get("floating_pnl"))
    return list(grouped.values())


def build_safety_audit(
    account_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    pending_order_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    all_can_send = [boolish(row.get("can_send_order")) for row in [*account_rows, *position_rows, *pending_order_rows]]
    can_modify_positions = [boolish(row.get("can_modify_position")) for row in position_rows]
    can_modify_orders = [boolish(row.get("can_modify_order")) for row in pending_order_rows]
    return [
        {"check": "can_send_order_all_false", "observed": any(all_can_send), "expected": False, "status": "passed" if not any(all_can_send) else "blocked"},
        {"check": "can_modify_position_all_false", "observed": any(can_modify_positions), "expected": False, "status": "passed" if not any(can_modify_positions) else "blocked"},
        {"check": "can_modify_order_all_false", "observed": any(can_modify_orders), "expected": False, "status": "passed" if not any(can_modify_orders) else "blocked"},
        {"check": "mt5_orders_sent", "observed": 0, "expected": 0, "status": "passed"},
        {"check": "telegram_connected", "observed": False, "expected": False, "status": "passed"},
        {"check": "sql_real_written", "observed": False, "expected": False, "status": "passed"},
    ]


def build_secret_handling_audit() -> list[dict[str, Any]]:
    return [
        {"check": "cli_password_parameter", "observed": False, "expected": False, "status": "passed", "note": "CLI has no password argument."},
        {"check": "cli_login_parameter", "observed": False, "expected": False, "status": "passed", "note": "CLI has no login argument."},
        {"check": "credentials_stored", "observed": False, "expected": False, "status": "passed", "note": "No credential artifact is written."},
        {"check": "account_id_hashed", "observed": True, "expected": True, "status": "passed", "note": "Account/position ids use sha256 prefix."},
        {"check": "broker_server_sanitized", "observed": True, "expected": True, "status": "passed", "note": "Broker/server fields are sanitized labels."},
    ]


def build_dashboard_future_integration_audit(
    output_dir: Path,
    account_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    pending_order_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "artifact": "mt5_readonly_manifest.json",
            "status": "planned_available",
            "path": str(output_dir / "mt5_readonly_manifest.json"),
            "connected": bool(account_rows and account_rows[0].get("mt5_connected")),
            "positions_count": len(position_rows),
            "pending_orders_count": len(pending_order_rows),
            "read_only": True,
            "dash_integration_implemented": False,
        }
    ]


def build_runtime_issues(
    config: Mt5ReadOnlyConfig,
    account_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    pending_order_rows: list[dict[str, Any]],
    mt5_connected: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if config.audit_only:
        issues.append({"issue_id": "audit_only_no_connection", "severity": "info", "description": "Audit-only run intentionally did not connect to MT5.", "recommended_action": "Use fixture or explicit read-only connection review."})
    if config.fixture_mode:
        issues.append({"issue_id": "fixture_not_real_account", "severity": "info", "description": "Fixture snapshots are synthetic and only validate artifact contracts.", "recommended_action": "Use --connect only in authorized local read-only review."})
    if not mt5_connected and config.connect:
        issues.append({"issue_id": "connect_requested_not_connected", "severity": "medium", "description": "Connection was requested but no MT5 read-only connection was established.", "recommended_action": "Review connection policy audit."})
    if any(boolish(row.get("can_send_order")) for row in [*account_rows, *position_rows, *pending_order_rows]):
        issues.append({"issue_id": "can_send_order_true", "severity": "critical", "description": "An output row can send orders, which violates read-only policy.", "recommended_action": "Block release."})
    return issues


def build_manifest(
    output_dir: Path,
    read_time: datetime,
    mt5_connected: bool,
    account_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    pending_order_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at_utc": read_time.isoformat(),
        "mt5_connected": mt5_connected,
        "read_only": True,
        "positions_count": len(position_rows),
        "pending_orders_count": len(pending_order_rows),
        "account_snapshot_csv": str(output_dir / "mt5_account_snapshot.csv"),
        "positions_snapshot_csv": str(output_dir / "mt5_positions_snapshot.csv"),
        "pending_orders_snapshot_csv": str(output_dir / "mt5_pending_orders_snapshot.csv"),
        "can_send_order_any_true": any(boolish(row.get("can_send_order")) for row in [*account_rows, *position_rows, *pending_order_rows]),
        "can_modify_position_any_true": any(boolish(row.get("can_modify_position")) for row in position_rows),
        "telegram_connected": False,
        "sql_real_written": False,
    }


def build_run_meta(
    config: Mt5ReadOnlyConfig,
    decision: str,
    read_time: datetime,
    *,
    mt5_connected: bool,
    connection_attempted: bool,
    account_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    pending_order_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "phase": "mt5_read_only_connection_v1",
        "decision": decision,
        "generated_at_utc": read_time.isoformat(),
        "mt5_readonly_connection_implemented": True,
        "mt5_mode": "read_only",
        "audit_only": config.audit_only,
        "fixture_mode": config.fixture_mode,
        "mt5_connected": mt5_connected,
        "mt5_connection_attempted": connection_attempted,
        "mt5_orders_enabled": False,
        "mt5_orders_sent": 0,
        "can_send_order_any_true": any(boolish(row.get("can_send_order")) for row in [*account_rows, *position_rows, *pending_order_rows]),
        "can_modify_position_any_true": any(boolish(row.get("can_modify_position")) for row in position_rows),
        "credentials_stored": False,
        "password_printed": False,
        "login_printed": False,
        "telegram_connected": False,
        "telegram_can_trade": False,
        "ai_analyst_can_approve_orders": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "account_rows": len(account_rows),
        "positions_count": len(position_rows),
        "pending_orders_count": len(pending_order_rows),
    }


def render_markdown(decision: str, run_meta: Mapping[str, Any], manifest: Mapping[str, Any], issues: list[dict[str, Any]]) -> str:
    return f"""# MT5 Read Only Connection V1

Fecha: 2026-06-07

Decision: `{decision}`

## Resumen

Se implementa una primera capa MT5 estrictamente read-only. La CLI puede
generar auditoria sin importar MT5, fixtures reproducibles para tests y, solo
si se autoriza con `--connect` y variables de entorno, snapshots read-only de
cuenta, posiciones y ordenes pendientes.

No existe superficie de envio, modificacion ni cierre de ordenes. Telegram,
SQL writes, senales, backtests y demo orders siguen fuera.

## Uso

Audit-only:

```powershell
python -m trading_center.mt5_read_only --output-dir artifacts/tfg/mt5_read_only_connection_v1_2026-06-07 --audit-only
```

Fixture:

```powershell
python -m trading_center.mt5_read_only --output-dir artifacts/tfg/mt5_read_only_connection_v1_2026-06-07 --fixture-mode
```

Conexion real read-only, solo si se autoriza:

```powershell
$env:{READ_ONLY_ENV}="1"
$env:{TRADING_DISABLED_ENV}="1"
python -m trading_center.mt5_read_only --connect
```

## Resultado Del Run

- mt5_connected: `{run_meta.get('mt5_connected')}`
- mt5_connection_attempted: `{run_meta.get('mt5_connection_attempted')}`
- positions_count: `{manifest.get('positions_count')}`
- pending_orders_count: `{manifest.get('pending_orders_count')}`
- can_send_order_any_true: `{run_meta.get('can_send_order_any_true')}`
- can_modify_position_any_true: `{run_meta.get('can_modify_position_any_true')}`

## Seguridad

- `mt5_orders_enabled=false`
- `mt5_orders_sent=0`
- `credentials_stored=false`
- `password_printed=false`
- `login_printed=false`
- `telegram_connected=false`
- `sql_real_written=false`
- `signals_generated=false`
- `backtests_executed=false`

## Artifacts

- `mt5_account_snapshot.csv/json`
- `mt5_positions_snapshot.csv/json`
- `mt5_pending_orders_snapshot.csv/json`
- `mt5_readonly_manifest.json`
- tablas de auditoria en `tables/`

## Incidencias

{chr(10).join(f"- `{item['issue_id']}`: {item['description']}" for item in issues)}

## Siguiente Paso

Revisar localmente la conexion read-only con MT5 abierto y cuenta autorizada.
Solo despues deberia disenarse `mt5_shadow_v1`; demo orders quedan bloqueadas
hasta una fase posterior con RiskGuard y confirmacion manual.
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MT5 read-only snapshots without any trading surface.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--audit-only", action="store_true", default=False)
    parser.add_argument("--fixture-mode", action="store_true", default=False)
    parser.add_argument("--connect", action="store_true", default=False)
    parser.add_argument("--history-days", type=int, default=7)
    parser.add_argument("--include-history", action="store_true", default=False)
    parser.add_argument("--account-label", default="mt5_read_only")
    parser.add_argument("--allow-missing-mt5", action="store_true", default=False)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> Mt5ReadOnlyConfig:
    return Mt5ReadOnlyConfig(
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        audit_only=bool(args.audit_only),
        fixture_mode=bool(args.fixture_mode),
        connect=bool(args.connect),
        include_history=bool(args.include_history),
        history_days=int(args.history_days),
        account_label=str(args.account_label),
        allow_missing_mt5=bool(args.allow_missing_mt5),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = execute(config_from_args(args))
    print(json.dumps({"decision": result.decision, "output_dir": str(result.output_dir)}, ensure_ascii=False))
    return 0


def write_csv(path: Path, rows: list[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(str(key))
        fieldnames = fields
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return truthy(value)


def stable_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def sanitize_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    blocked = ("password", "login", "account", "server=", "host=", "pwd")
    lowered = text.lower()
    if any(token in lowered for token in blocked):
        return "sanitized"
    return text[:80]


def safe_attr(item: Any, name: str, default: Any = None) -> Any:
    if item is None:
        return default
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def float_attr(item: Any, name: str, default: float = 0.0) -> float:
    return safe_float(safe_attr(item, name, default))


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def epoch_to_iso(value: Any) -> str:
    try:
        if value in ("", None):
            return ""
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(value or "")


def position_direction(value: Any) -> str:
    text = str(value).lower()
    if text in {"1", "sell", "short"}:
        return "short"
    return "long"


def pending_direction(value: Any) -> str:
    text = str(value).lower()
    mapping = {
        "2": "buy_limit",
        "3": "sell_limit",
        "4": "buy_stop",
        "5": "sell_stop",
        "6": "buy_stop_limit",
        "7": "sell_stop_limit",
    }
    return mapping.get(text, text or "pending")


def object_to_mapping(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        return dict(item)
    if hasattr(item, "_asdict"):
        return dict(item._asdict())
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    return {"value": str(item)}


def safe_call(func: Any) -> Any:
    try:
        return func()
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
