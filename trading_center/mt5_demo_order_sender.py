"""Fail-closed demo order sender driven by audited RiskGuard intents."""

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


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/mt5_demo_order_sender_v1_2026-06-08")
DEFAULT_DOC_PATH = Path("docs/MT5_DEMO_ORDER_SENDER_V1.md")
DEFAULT_INTENTS = Path("artifacts/tfg/riskguard_demo_intent_builder_v1_2026-06-08/demo_order_intents.csv")
DEFAULT_DECISIONS = Path("artifacts/tfg/riskguard_demo_intent_builder_v1_2026-06-08/riskguard_decisions.csv")
DEFAULT_ACCOUNT = Path("artifacts/tfg/mt5_read_only_connection_v1_2026-06-07_local_connect_review/mt5_account_snapshot.csv")
DEFAULT_CONFIRMATIONS = Path("artifacts/tfg/mt5_demo_order_sender_v1_2026-06-08/manual_confirmations.csv")

SENDER_ENV = "MT5_DEMO_ORDER_SENDER_ENABLED"
DEMO_ENV = "MT5_DEMO_TRADING_ENABLED"
LIVE_BLOCK_ENV = "MT5_LIVE_TRADING_BLOCKED"

REQUEST_COLUMNS = [
    "request_id",
    "intent_id",
    "setup_id",
    "symbol",
    "timeframe",
    "setup_type",
    "direction",
    "order_type",
    "entry_type",
    "entry_price",
    "sl",
    "tp",
    "volume",
    "volume_source",
    "sizing_status",
    "risk_pct",
    "risk_amount",
    "manual_confirmation_id",
    "request_status",
    "send_requested",
    "order_sent",
    "created_at_utc",
]

RESULT_COLUMNS = [
    "result_id",
    "request_id",
    "intent_id",
    "symbol",
    "result_status",
    "mt5_retcode",
    "mt5_order_id_hash",
    "mt5_deal_id_hash",
    "error_message",
    "order_sent",
    "created_at_utc",
]

MT5_SUCCESS_RETCODES = {10008, 10009}


@dataclass(frozen=True)
class Mt5DemoOrderSenderConfig:
    """Configuration gates for a controlled demo-order sender run."""
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    intents_csv: Path = DEFAULT_INTENTS
    riskguard_decisions_csv: Path = DEFAULT_DECISIONS
    mt5_account_snapshot_csv: Path = DEFAULT_ACCOUNT
    manual_confirmations_csv: Path = DEFAULT_CONFIRMATIONS
    audit_only: bool = True
    dry_run: bool = False
    fixture_mode: bool = False
    connect: bool = False
    send_demo_orders: bool = False
    require_manual_confirmation: bool = True
    allow_missing_inputs: bool = False
    default_risk_pct: float = 0.25
    min_volume: float = 0.01
    volume_step: float = 0.01
    max_volume: float = 1.0
    contract_size: float = 100000.0
    allow_min_lot_fallback: bool = False


@dataclass(frozen=True)
class Mt5DemoOrderSenderResult:
    """Audit result for one demo-order sender run."""
    decision: str
    output_dir: Path
    run_meta: dict[str, Any]
    request_rows: list[dict[str, Any]]
    result_rows: list[dict[str, Any]]


def execute(config: Mt5DemoOrderSenderConfig) -> Mt5DemoOrderSenderResult:
    """Build demo order requests and optionally send only when every gate passes."""
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()

    if config.fixture_mode:
        intent_rows, decision_rows, account_rows, confirmation_rows = fixture_inputs(created_at)
        input_audit = [{"source": "fixture", "path": "in_memory", "rows": len(intent_rows), "status": "loaded"}]
    else:
        intent_rows, decision_rows, account_rows, confirmation_rows, input_audit = load_inputs(config)

    decision_by_intent = {text(row.get("intent_id")): row for row in decision_rows if text(row.get("intent_id"))}
    confirmation_by_intent = {
        text(row.get("intent_id")): row for row in confirmation_rows if text(row.get("intent_id"))
    }
    account = first_row(account_rows)
    env_gate_rows, env_gate_ok = evaluate_env_gates(config)
    account_gate_rows, account_gate_ok = evaluate_account_gate(account)

    request_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    preflight_rows: list[dict[str, Any]] = []
    confirmation_audit_rows: list[dict[str, Any]] = []

    for intent in intent_rows:
        riskguard_decision = decision_by_intent.get(text(intent.get("intent_id")), {})
        confirmation = confirmation_by_intent.get(text(intent.get("intent_id")), {})
        actual_send_requested = config.send_demo_orders and config.connect and not config.audit_only and not config.dry_run
        sized_intent = apply_position_sizing(intent, account, config)
        checks = preflight_checks(
            intent=sized_intent,
            riskguard_decision=riskguard_decision,
            confirmation=confirmation,
            require_manual_confirmation=config.require_manual_confirmation,
            account_gate_ok=account_gate_ok,
            env_gate_ok=env_gate_ok,
            send_requested=actual_send_requested,
        )
        preflight_rows.extend(checks)
        confirmation_audit_rows.append(confirmation_audit(intent, confirmation, config.require_manual_confirmation))
        blocking = first_blocking_reason(checks)
        if blocking:
            result_rows.append(blocked_result(sized_intent, blocking, created_at))
            continue
        request = build_request(sized_intent, confirmation, created_at, config.send_demo_orders)
        request_rows.append(request)
        if config.send_demo_orders and config.connect and not config.audit_only and not config.dry_run:
            result_rows.append(send_with_mt5(request, created_at))
        else:
            result_rows.append(not_sent_result(request, created_at, config))

    safety_rows = safety_audit(config, request_rows, result_rows)
    issues = issues_or_risks(input_audit, env_gate_rows, account_gate_rows, request_rows, result_rows)

    write_csv(output_dir / "demo_order_requests.csv", request_rows, REQUEST_COLUMNS)
    write_json(output_dir / "demo_order_requests.json", request_rows)
    write_csv(output_dir / "demo_order_results.csv", result_rows, RESULT_COLUMNS)
    write_json(output_dir / "demo_order_results.json", result_rows)
    write_csv(tables_dir / "input_audit.csv", input_audit)
    write_csv(tables_dir / "preflight_audit.csv", preflight_rows)
    write_csv(tables_dir / "manual_confirmation_audit.csv", confirmation_audit_rows)
    write_csv(tables_dir / "environment_gate_audit.csv", env_gate_rows)
    write_csv(tables_dir / "account_gate_audit.csv", account_gate_rows)
    write_csv(tables_dir / "safety_audit.csv", safety_rows)
    write_csv(tables_dir / "issues_or_risks.csv", issues)

    sent_count = sum(1 for row in result_rows if boolish(row.get("order_sent")))
    prepared_count = len(request_rows)
    decision = "mt5_demo_order_sender_v1_ready_for_manual_demo_review"
    if sent_count:
        decision = "mt5_demo_order_sender_v1_demo_order_sent_review_required"
    elif any(text(row.get("mt5_retcode")) == "10027" for row in result_rows):
        decision = "mt5_demo_order_sender_v1_blocked_by_terminal_autotrading"
    elif not intent_rows:
        decision = "mt5_demo_order_sender_v1_no_intents_to_send"
    run_meta = {
        "phase": "mt5_demo_order_sender_v1",
        "created_at_utc": created_at.isoformat(),
        "decision": decision,
        "mt5_demo_order_sender_implemented": True,
        "artifact_first": True,
        "audit_only": bool(config.audit_only),
        "dry_run": bool(config.dry_run),
        "fixture_mode": bool(config.fixture_mode),
        "connect_requested": bool(config.connect),
        "send_demo_orders_requested": bool(config.send_demo_orders),
        "manual_confirmation_required": bool(config.require_manual_confirmation),
        "environment_gates_passed": bool(env_gate_ok),
        "account_demo_gate_passed": bool(account_gate_ok),
        "order_requests_prepared": prepared_count,
        "order_results_count": len(result_rows),
        "orders_sent": sent_count,
        "mt5_orders_sent": sent_count,
        "live_trading_enabled": False,
        "telegram_connected": False,
        "telegram_can_trade": False,
        "sql_real_written": False,
        "backtests_executed": False,
    }
    write_json(output_dir / "run_meta.json", run_meta)
    write_doc(output_dir / "MT5_DEMO_ORDER_SENDER_V1.md", run_meta, issues)
    if config.doc_path:
        write_doc(config.doc_path, run_meta, issues)
    return Mt5DemoOrderSenderResult(decision, output_dir, run_meta, request_rows, result_rows)


def load_inputs(
    config: Mt5DemoOrderSenderConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    sources = [
        ("demo_order_intents", config.intents_csv),
        ("riskguard_decisions", config.riskguard_decisions_csv),
        ("mt5_account_snapshot", config.mt5_account_snapshot_csv),
        ("manual_confirmations", config.manual_confirmations_csv),
    ]
    rows: dict[str, list[dict[str, Any]]] = {}
    audit: list[dict[str, Any]] = []
    for source_id, path in sources:
        if path.exists():
            loaded = read_csv(path)
            rows[source_id] = loaded
            audit.append({"source": source_id, "path": str(path), "rows": len(loaded), "status": "loaded"})
        else:
            rows[source_id] = []
            status = "optional_missing" if config.allow_missing_inputs or source_id == "manual_confirmations" else "missing"
            audit.append({"source": source_id, "path": str(path), "rows": 0, "status": status})
    return (
        rows["demo_order_intents"],
        rows["riskguard_decisions"],
        rows["mt5_account_snapshot"],
        rows["manual_confirmations"],
        audit,
    )


def fixture_inputs(created_at: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    intent_id = "fixture-intent-accepted"
    intent = {
        "intent_id": intent_id,
        "source_shadow_decision_id": "fixture-shadow",
        "setup_id": "fixture-setup",
        "symbol": "EURUSD.r",
        "market_group": "Forex Majors",
        "timeframe": "H1",
        "setup_type": "macd_breakout",
        "strategy": "macd_breakout",
        "direction": "bullish",
        "entry_type": "market_demo_review",
        "entry_price": "1.1000",
        "sl": "1.0950",
        "tp1": "1.1100",
        "tp2": "1.1150",
        "volume": "",
        "risk_pct": "0.25",
        "is_demo_intent": "true",
        "is_order": "false",
        "order_sent": "false",
        "can_send_order": "false",
    }
    decision = {
        "decision_id": "fixture-riskguard-decision",
        "intent_id": intent_id,
        "setup_id": "fixture-setup",
        "symbol": "EURUSD.r",
        "riskguard_decision": "accepted_for_demo_intent",
        "accepted": "true",
        "can_send_order": "false",
        "order_sent": "false",
    }
    account = {
        "account_label": "demo_fixture",
        "account_mode": "demo",
        "currency": "EUR",
        "equity": "10000",
        "mt5_connected": "false",
        "read_only": "true",
    }
    confirmation = {
        "manual_confirmation_id": "fixture-confirmation",
        "intent_id": intent_id,
        "status": "confirmed",
        "confirmed_at": created_at.isoformat(),
        "expires_at": "",
        "parameters_hash": stable_hash(intent),
    }
    return [intent], [decision], [account], [confirmation]


def preflight_checks(
    *,
    intent: Mapping[str, Any],
    riskguard_decision: Mapping[str, Any],
    confirmation: Mapping[str, Any],
    require_manual_confirmation: bool,
    account_gate_ok: bool,
    env_gate_ok: bool,
    send_requested: bool,
) -> list[dict[str, Any]]:
    checks = [
        check(intent, "is_demo_intent", boolish(intent.get("is_demo_intent")), "blocked_by_not_demo_intent"),
        check(intent, "riskguard_accepted", text(riskguard_decision.get("riskguard_decision")) == "accepted_for_demo_intent", "blocked_by_riskguard"),
        check(intent, "entry_present", has_value(intent.get("entry_price")), "blocked_by_missing_entry"),
        check(intent, "sl_present", has_value(intent.get("sl")), "blocked_by_missing_sl"),
        check(intent, "tp_present", has_value(intent.get("tp1")), "blocked_by_missing_tp"),
        check(intent, "volume_present", has_value(intent.get("volume")), "blocked_by_missing_volume"),
        check(intent, "sizing_status_ok", sizing_status_ok(intent), "blocked_by_sizing"),
        check(intent, "account_demo", account_gate_ok, "blocked_by_no_demo_account"),
        check(intent, "manual_confirmation", (not require_manual_confirmation) or text(confirmation.get("status")) == "confirmed", "blocked_by_missing_manual_confirmation"),
        check(intent, "environment_gates", (not send_requested) or env_gate_ok, "blocked_by_environment_gates"),
    ]
    return checks


def check(intent: Mapping[str, Any], check_id: str, passed: bool, decision_if_failed: str) -> dict[str, Any]:
    return {
        "intent_id": text(intent.get("intent_id")),
        "setup_id": text(intent.get("setup_id")),
        "symbol": text(intent.get("symbol")),
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "decision_if_failed": "" if passed else decision_if_failed,
    }


def first_blocking_reason(checks: Sequence[Mapping[str, Any]]) -> str:
    for row in checks:
        if row.get("status") == "fail":
            return text(row.get("decision_if_failed"))
    return ""


def build_request(intent: Mapping[str, Any], confirmation: Mapping[str, Any], created_at: datetime, send_requested: bool) -> dict[str, Any]:
    request = {
        "request_id": "demo-request-" + stable_hash({"intent": intent, "created_at": created_at.isoformat()})[:16],
        "intent_id": text(intent.get("intent_id")),
        "setup_id": text(intent.get("setup_id")),
        "symbol": text(intent.get("symbol")),
        "timeframe": text(intent.get("timeframe")),
        "setup_type": text(intent.get("setup_type")),
        "direction": text(intent.get("direction")),
        "order_type": order_type_for(text(intent.get("direction"))),
        "entry_type": text(intent.get("entry_type")),
        "entry_price": text(intent.get("entry_price")),
        "sl": text(intent.get("sl")),
        "tp": text(intent.get("tp1")),
        "volume": text(intent.get("volume")),
        "volume_source": text(intent.get("volume_source")),
        "sizing_status": text(intent.get("sizing_status")),
        "risk_pct": text(intent.get("risk_pct")),
        "risk_amount": text(intent.get("risk_amount")),
        "manual_confirmation_id": text(confirmation.get("manual_confirmation_id")),
        "request_status": "ready_to_send_demo" if send_requested else "prepared_dry_run",
        "send_requested": bool(send_requested),
        "order_sent": False,
        "created_at_utc": created_at.isoformat(),
    }
    return request


def apply_position_sizing(
    intent: Mapping[str, Any],
    account: Mapping[str, Any],
    config: Mt5DemoOrderSenderConfig,
) -> dict[str, Any]:
    sized = dict(intent)
    if has_value(sized.get("volume")) and safe_float(sized.get("volume")) > 0:
        if not has_value(sized.get("volume_source")):
            sized["volume_source"] = "intent_volume"
        if not has_value(sized.get("sizing_status")):
            sized["sizing_status"] = "provided_by_intent"
        return sized

    equity = safe_float(account.get("equity"))
    entry = safe_float(sized.get("entry_price"))
    sl = safe_float(sized.get("sl"))
    risk_pct = safe_float(sized.get("risk_pct")) or float(config.default_risk_pct)
    price_risk = abs(entry - sl)
    if equity > 0 and entry > 0 and sl > 0 and price_risk > 0 and risk_pct > 0:
        risk_amount = equity * (risk_pct / 100.0)
        raw_volume = risk_amount / (price_risk * float(config.contract_size))
        rounded_volume = round_volume(raw_volume, config.min_volume, config.volume_step, config.max_volume)
        if rounded_volume > 0:
            sized["volume"] = f"{rounded_volume:.2f}"
            sized["volume_source"] = "risk_pct_equity_entry_sl"
            sized["sizing_status"] = "calculated"
            sized["risk_pct"] = f"{risk_pct:g}"
            sized["risk_amount"] = f"{risk_amount:.2f}"
            return sized

    if config.allow_min_lot_fallback:
        sized["volume"] = f"{float(config.min_volume):.2f}"
        sized["volume_source"] = "min_lot_fallback"
        sized["sizing_status"] = "fallback_min_lot_missing_metadata"
        sized["risk_pct"] = text(sized.get("risk_pct")) or f"{risk_pct:g}"
        sized["risk_amount"] = text(sized.get("risk_amount"))
    else:
        sized["volume"] = ""
        sized["volume_source"] = "not_available"
        sized["sizing_status"] = "blocked_missing_sizing_metadata"
        sized["risk_pct"] = text(sized.get("risk_pct")) or f"{risk_pct:g}"
        sized["risk_amount"] = text(sized.get("risk_amount"))
    return sized


def sizing_status_ok(intent: Mapping[str, Any]) -> bool:
    status = text(intent.get("sizing_status")).lower()
    if status.startswith("blocked"):
        return False
    if status in {"", "not_available", "not_applicable", "failed"}:
        return False
    return True


def round_volume(raw_volume: float, min_volume: float, step: float, max_volume: float) -> float:
    if raw_volume <= 0 or min_volume <= 0 or step <= 0 or max_volume <= 0:
        return 0.0
    capped = min(max(raw_volume, min_volume), max_volume)
    steps = int((capped + 1e-12) / step)
    rounded = steps * step
    if rounded < min_volume:
        rounded = min_volume
    return round(min(rounded, max_volume), 2)


def blocked_result(intent: Mapping[str, Any], reason: str, created_at: datetime) -> dict[str, Any]:
    return {
        "result_id": "demo-result-" + stable_hash({"intent": intent, "reason": reason})[:16],
        "request_id": "",
        "intent_id": text(intent.get("intent_id")),
        "symbol": text(intent.get("symbol")),
        "result_status": reason,
        "mt5_retcode": "",
        "mt5_order_id_hash": "",
        "mt5_deal_id_hash": "",
        "error_message": reason,
        "order_sent": False,
        "created_at_utc": created_at.isoformat(),
    }


def not_sent_result(request: Mapping[str, Any], created_at: datetime, config: Mt5DemoOrderSenderConfig) -> dict[str, Any]:
    if config.audit_only:
        status = "not_sent_audit_only"
    elif config.dry_run:
        status = "not_sent_dry_run"
    elif not config.send_demo_orders:
        status = "not_sent_send_flag_false"
    elif not config.connect:
        status = "not_sent_connect_false"
    else:
        status = "not_sent_preflight_only"
    return {
        "result_id": "demo-result-" + stable_hash({"request": request, "status": status})[:16],
        "request_id": text(request.get("request_id")),
        "intent_id": text(request.get("intent_id")),
        "symbol": text(request.get("symbol")),
        "result_status": status,
        "mt5_retcode": "",
        "mt5_order_id_hash": "",
        "mt5_deal_id_hash": "",
        "error_message": "",
        "order_sent": False,
        "created_at_utc": created_at.isoformat(),
    }


def send_with_mt5(request: Mapping[str, Any], created_at: datetime) -> dict[str, Any]:
    try:
        mt5 = import_mt5()
        if not mt5.initialize():
            raise RuntimeError("mt5_initialize_failed")
        symbol = text(request.get("symbol"))
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError("mt5_tick_unavailable")
        is_buy = text(request.get("order_type")) == "buy"
        action_type = getattr(mt5, "ORDER_TYPE_BUY") if is_buy else getattr(mt5, "ORDER_TYPE_SELL")
        current_price = float(tick.ask if is_buy else tick.bid)
        payload = {
            "action": getattr(mt5, "TRADE_ACTION_DEAL"),
            "symbol": symbol,
            "volume": float(request.get("volume")),
            "type": action_type,
            "price": current_price,
            "sl": float(request.get("sl")),
            "tp": float(request.get("tp")),
            "deviation": 20,
            "magic": 26060801,
            "comment": "TFG demo sender",
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
        sent = retcode_value in MT5_SUCCESS_RETCODES and bool(order_positive or deal_positive)
        status = "sent_to_mt5_demo" if sent else f"mt5_order_rejected_retcode_{retcode or 'unknown'}"
        return {
            "result_id": "demo-result-" + stable_hash({"request": request, "retcode": retcode, "order": order_id, "deal": deal_id})[:16],
            "request_id": text(request.get("request_id")),
            "intent_id": text(request.get("intent_id")),
            "symbol": text(request.get("symbol")),
            "result_status": status,
            "mt5_retcode": retcode,
            "mt5_order_id_hash": hash_secret(order_id) if order_positive else "",
            "mt5_deal_id_hash": hash_secret(deal_id) if deal_positive else "",
            "error_message": "",
            "order_sent": sent,
            "created_at_utc": created_at.isoformat(),
        }
    except Exception as exc:  # pragma: no cover - real MT5 path is local/manual only.
        return {
            "result_id": "demo-result-" + stable_hash({"request": request, "error": exc.__class__.__name__})[:16],
            "request_id": text(request.get("request_id")),
            "intent_id": text(request.get("intent_id")),
            "symbol": text(request.get("symbol")),
            "result_status": "mt5_send_failed",
            "mt5_retcode": "",
            "mt5_order_id_hash": "",
            "mt5_deal_id_hash": "",
            "error_message": exc.__class__.__name__,
            "order_sent": False,
            "created_at_utc": created_at.isoformat(),
        }
    finally:
        try:
            mt5.shutdown()  # type: ignore[name-defined]
        except Exception:
            pass


def evaluate_env_gates(config: Mt5DemoOrderSenderConfig) -> tuple[list[dict[str, Any]], bool]:
    rows = [
        env_check(SENDER_ENV, "1"),
        env_check(DEMO_ENV, "1"),
        env_check(LIVE_BLOCK_ENV, "1"),
        {"check": "send_flag", "expected": True, "observed": bool(config.send_demo_orders), "status": "pass" if config.send_demo_orders else "blocked"},
        {"check": "connect_flag", "expected": True, "observed": bool(config.connect), "status": "pass" if config.connect else "blocked"},
        {"check": "not_audit_only", "expected": True, "observed": not config.audit_only, "status": "pass" if not config.audit_only else "blocked"},
        {"check": "not_dry_run", "expected": True, "observed": not config.dry_run, "status": "pass" if not config.dry_run else "blocked"},
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def evaluate_account_gate(account: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    mode = text(account.get("account_mode")).lower()
    label = text(account.get("account_label")).lower()
    server = text(account.get("server_name_sanitized")).lower()
    is_demo = mode == "demo" or "demo" in label or "demo" in server
    rows = [{"check": "account_is_demo", "expected": True, "observed": is_demo, "status": "pass" if is_demo else "blocked"}]
    return rows, is_demo


def env_check(name: str, expected: str) -> dict[str, Any]:
    observed = os.environ.get(name, "")
    return {"check": name, "expected": expected, "observed": observed == expected, "status": "pass" if observed == expected else "blocked"}


def confirmation_audit(intent: Mapping[str, Any], confirmation: Mapping[str, Any], required: bool) -> dict[str, Any]:
    status = text(confirmation.get("status")) or "missing"
    return {
        "intent_id": text(intent.get("intent_id")),
        "manual_confirmation_id": text(confirmation.get("manual_confirmation_id")),
        "required": bool(required),
        "status": status,
        "passed": (not required) or status == "confirmed",
    }


def safety_audit(
    config: Mt5DemoOrderSenderConfig,
    request_rows: Sequence[Mapping[str, Any]],
    result_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {"check": "audit_default", "observed": bool(config.audit_only), "expected": True, "status": "pass" if config.audit_only else "review"},
        {"check": "orders_sent", "observed": sum(1 for row in result_rows if boolish(row.get("order_sent"))), "expected": 0 if not config.send_demo_orders else "manual_demo_only", "status": "pass" if not any(boolish(row.get("order_sent")) for row in result_rows) else "review_required"},
        {"check": "live_trading_enabled", "observed": False, "expected": False, "status": "pass"},
        {"check": "telegram_connected", "observed": False, "expected": False, "status": "pass"},
        {"check": "sql_real_written", "observed": False, "expected": False, "status": "pass"},
        {"check": "requests_prepared", "observed": len(request_rows), "expected": "audit", "status": "pass"},
    ]


def issues_or_risks(
    input_audit: Sequence[Mapping[str, Any]],
    env_gate_rows: Sequence[Mapping[str, Any]],
    account_gate_rows: Sequence[Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]],
    result_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if any(row.get("status") == "missing" for row in input_audit):
        issues.append({"issue_id": "missing_required_input", "severity": "high", "description": "Required intent or RiskGuard input is missing.", "recommended_action": "Regenerate RiskGuard demo intent builder artifacts."})
    if any(row.get("status") != "pass" for row in env_gate_rows):
        issues.append({"issue_id": "environment_gates_closed", "severity": "info", "description": "Demo sending gates are closed; no order can be sent.", "recommended_action": "Keep closed outside explicit local demo review."})
    if any(row.get("status") != "pass" for row in account_gate_rows):
        issues.append({"issue_id": "demo_account_not_confirmed", "severity": "high", "description": "Account snapshot does not prove demo mode.", "recommended_action": "Use MT5 read-only snapshot from a demo account before sending."})
    if not request_rows:
        issues.append({"issue_id": "no_demo_requests_prepared", "severity": "info", "description": "No intent passed sender preflight.", "recommended_action": "Review RiskGuard decisions and confirmations."})
    if any(boolish(row.get("order_sent")) for row in result_rows):
        issues.append({"issue_id": "demo_order_sent_review_required", "severity": "high", "description": "A demo order was sent and must be reviewed.", "recommended_action": "Audit MT5 result and account state."})
    rejected = [row for row in result_rows if text(row.get("result_status")).startswith("mt5_order_rejected_retcode_")]
    if rejected:
        codes = sorted({text(row.get("mt5_retcode")) for row in rejected})
        issues.append({"issue_id": "mt5_order_rejected", "severity": "high", "description": f"MT5 rejected the demo order request with retcode(s): {', '.join(codes)}.", "recommended_action": "Review terminal trading permissions, symbol trade mode and broker retcode before retrying."})
    if not issues:
        issues.append({"issue_id": "no_runtime_issues", "severity": "info", "description": "Demo sender completed with fail-closed controls.", "recommended_action": "Proceed only with explicit demo review."})
    return issues


def import_mt5() -> Any:
    import MetaTrader5 as mt5  # type: ignore

    return mt5


def order_type_for(direction: str) -> str:
    direction = direction.lower()
    if direction in {"bullish", "long", "buy", "alcista"}:
        return "buy"
    if direction in {"bearish", "short", "sell", "bajista"}:
        return "sell"
    return "unknown"


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
    body = f"""# MT5 demo order sender v1

## Que implementa

Esta fase implementa un sender demo con preflight fail-closed. Lee intents
demo aceptados por RiskGuard, exige confirmacion manual, comprueba cuenta demo
y solo puede llamar a MT5 si se activan flags CLI y variables de entorno
explicitas. Por defecto no envia nada.

Flujo:

`RiskGuard demo intents -> confirmacion manual -> demo order request -> MT5 demo`

## Modos de ejecucion

Audit-only real actual:

```powershell
python -m trading_center.mt5_demo_order_sender --audit-only
```

Fixture/dry-run:

```powershell
python -m trading_center.mt5_demo_order_sender --fixture-mode --dry-run
```

Envio demo manual futuro, solo si hay intent aceptado, cuenta demo y
confirmacion manual:

```powershell
$env:{SENDER_ENV}="1"
$env:{DEMO_ENV}="1"
$env:{LIVE_BLOCK_ENV}="1"
python -m trading_center.mt5_demo_order_sender --connect --send-demo-orders
```

Sin esos gates, el sender bloquea. Esta fase no ejecuta ese comando.

## Resultado

- Decision: `{run_meta.get('decision')}`
- Requests preparados: {run_meta.get('order_requests_prepared')}
- Ordenes demo enviadas: {run_meta.get('orders_sent')}
- Audit-only: {run_meta.get('audit_only')}
- Dry-run: {run_meta.get('dry_run')}

## Seguridad

- Live trading: `false`
- Telegram: `false`
- SQL writes: `false`
- Backtests: `false`
- Confirmacion manual requerida: `{run_meta.get('manual_confirmation_required')}`
- Cuenta demo requerida: `true`
- RiskGuard accepted requerido: `true`
- Sizing no bloqueado requerido: `true`
- AI Analyst no aprueba ordenes

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed MT5 demo order sender.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--intents-csv", type=Path, default=DEFAULT_INTENTS)
    parser.add_argument("--riskguard-decisions-csv", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--mt5-account-snapshot-csv", type=Path, default=DEFAULT_ACCOUNT)
    parser.add_argument("--manual-confirmations-csv", type=Path, default=DEFAULT_CONFIRMATIONS)
    parser.add_argument("--audit-only", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--send-demo-orders", action="store_true")
    parser.add_argument("--no-manual-confirmation-required", action="store_true")
    parser.add_argument("--allow-missing-inputs", action="store_true")
    parser.add_argument("--default-risk-pct", type=float, default=0.25)
    parser.add_argument("--min-volume", type=float, default=0.01)
    parser.add_argument("--volume-step", type=float, default=0.01)
    parser.add_argument("--max-volume", type=float, default=1.0)
    parser.add_argument("--contract-size", type=float, default=100000.0)
    parser.add_argument("--allow-min-lot-fallback", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Mt5DemoOrderSenderConfig(
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        intents_csv=args.intents_csv,
        riskguard_decisions_csv=args.riskguard_decisions_csv,
        mt5_account_snapshot_csv=args.mt5_account_snapshot_csv,
        manual_confirmations_csv=args.manual_confirmations_csv,
        audit_only=bool(args.audit_only or not args.send_demo_orders),
        dry_run=bool(args.dry_run),
        fixture_mode=bool(args.fixture_mode),
        connect=bool(args.connect),
        send_demo_orders=bool(args.send_demo_orders),
        require_manual_confirmation=not bool(args.no_manual_confirmation_required),
        allow_missing_inputs=bool(args.allow_missing_inputs),
        default_risk_pct=float(args.default_risk_pct),
        min_volume=float(args.min_volume),
        volume_step=float(args.volume_step),
        max_volume=float(args.max_volume),
        contract_size=float(args.contract_size),
        allow_min_lot_fallback=bool(args.allow_min_lot_fallback),
    )
    result = execute(config)
    print(json.dumps(result.run_meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
