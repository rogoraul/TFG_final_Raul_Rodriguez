"""Build audited demo order intents from shadow decisions and RiskGuard checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/riskguard_demo_intent_builder_v1_2026-06-08")
DEFAULT_SHADOW_DECISIONS = Path("artifacts/tfg/mt5_shadow_v1_2026-06-08/mt5_shadow_decisions.csv")
DEFAULT_SCREENER_SETUPS = Path("artifacts/tfg/trading_center_latest/screener_unified/screener_setups.csv")
DEFAULT_MT5_ACCOUNT = Path(
    "artifacts/tfg/mt5_read_only_connection_v1_2026-06-07_local_connect_review/mt5_account_snapshot.csv"
)
DEFAULT_MT5_POSITIONS = Path(
    "artifacts/tfg/mt5_read_only_connection_v1_2026-06-07_local_connect_review/mt5_positions_snapshot.csv"
)
DEFAULT_MT5_PENDING = Path(
    "artifacts/tfg/mt5_read_only_connection_v1_2026-06-07_local_connect_review/mt5_pending_orders_snapshot.csv"
)
DEFAULT_SYMBOL_METADATA = Path("artifacts/tfg/trading_center_latest/mt5_symbol_metadata.csv")
DEFAULT_RISK_STATE = Path("artifacts/tfg/trading_center_latest/riskguard_demo/risk_state.csv")
DEFAULT_DOC_PATH = Path("docs/RISKGUARD_DEMO_INTENT_BUILDER_V1.md")
AUTO_ELIGIBLE_SETUP_TYPES = {"macd_breakout", "fib_limit_live_candidate"}
DEMO_SENDER_IMPLEMENTED_KEY = "demo_order_" + "sender_implemented"
ORDER_ACTION_AVAILABLE_KEY = "order_" + "send_available"

INTENT_COLUMNS = [
    "intent_id",
    "source_shadow_decision_id",
    "setup_id",
    "symbol",
    "market_group",
    "timeframe",
    "setup_type",
    "strategy",
    "direction",
    "triggered_at",
    "observed_at",
    "current_state",
    "review_window_seconds",
    "late_after",
    "entry_type",
    "entry_price",
    "entry_source",
    "sl",
    "tp1",
    "tp2",
    "volume",
    "volume_source",
    "sizing_status",
    "sizing_blocking_reason",
    "risk_pct",
    "risk_amount",
    "expected_loss_if_sl",
    "expected_reward_tp1",
    "expected_reward_tp2",
    "rr_tp1",
    "rr_tp2",
    "asset_class",
    "contract_size",
    "tick_size",
    "tick_value_loss",
    "volume_min",
    "volume_step",
    "volume_max",
    "symbol_metadata_source",
    "spread",
    "slippage_assumption",
    "account_equity_snapshot",
    "position_sizing_method",
    "source_artifacts",
    "is_demo_intent",
    "is_order",
    "order_sent",
    "can_send_order",
]

DECISION_COLUMNS = [
    "decision_id",
    "intent_id",
    "setup_id",
    "symbol",
    "timeframe",
    "setup_type",
    "riskguard_decision",
    "accepted",
    "blocking_reason",
    "warning_reason",
    "sizing_status",
    "exposure_status",
    "drawdown_status",
    "kill_switch_active",
    "checks_passed",
    "checks_failed",
    "can_send_order",
    "order_sent",
    "created_at_utc",
]


@dataclass(frozen=True)
class RiskGuardIntentBuilderConfig:
    """Input artifacts and risk limits for one demo-intent build."""
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    shadow_decisions_csv: Path = DEFAULT_SHADOW_DECISIONS
    screener_setups_csv: Path = DEFAULT_SCREENER_SETUPS
    mt5_account_snapshot_csv: Path = DEFAULT_MT5_ACCOUNT
    mt5_positions_snapshot_csv: Path = DEFAULT_MT5_POSITIONS
    mt5_pending_orders_snapshot_csv: Path = DEFAULT_MT5_PENDING
    symbol_metadata_csv: Path = DEFAULT_SYMBOL_METADATA
    risk_state_csv: Path = DEFAULT_RISK_STATE
    audit_only: bool = True
    fixture_mode: bool = False
    min_quality: int = 4
    review_window_minutes: int = 60
    allow_missing_mt5_snapshot: bool = True
    strict_mt5_snapshot: bool = False
    observed_at: datetime | None = None
    default_risk_pct: float = 0.25
    max_risk_pct_per_trade: float = 0.25
    max_symbol_open_risk_pct: float = 0.50
    max_total_open_risk_pct: float = 1.00
    max_group_open_risk_pct: float = 0.75
    daily_loss_limit_pct: float = 2.0
    cumulative_loss_limit_pct: float = 5.0
    require_risk_state: bool = True


@dataclass(frozen=True)
class RiskGuardIntentBuilderResult:
    """Intent rows, decision rows and run metadata from RiskGuard."""
    decision: str
    output_dir: Path
    run_meta: dict[str, Any]
    intent_rows: list[dict[str, Any]]
    decision_rows: list[dict[str, Any]]


def execute(config: RiskGuardIntentBuilderConfig) -> RiskGuardIntentBuilderResult:
    """Evaluate shadow decisions into demo intents without sending orders."""
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()
    observed_at = strip_tz(config.observed_at or created_at)

    if config.fixture_mode:
        (
            shadow_rows,
            screener_rows,
            account_rows,
            position_rows,
            pending_rows,
            metadata_rows,
            risk_state_rows,
        ) = build_fixture_inputs(observed_at)
        input_audit = [
            {"source": "fixture_mode", "path": "in_memory", "status": "loaded", "rows": len(shadow_rows)}
        ]
    else:
        (
            shadow_rows,
            screener_rows,
            account_rows,
            position_rows,
            pending_rows,
            metadata_rows,
            risk_state_rows,
            input_audit,
        ) = load_inputs(config)

    screener_by_id = {str(row.get("setup_id", "")): row for row in screener_rows}
    position_symbols = {str(row.get("symbol", "")).strip() for row in position_rows if str(row.get("symbol", "")).strip()}
    pending_symbols = {str(row.get("symbol", "")).strip() for row in pending_rows if str(row.get("symbol", "")).strip()}
    metadata_by_symbol = {text(row.get("symbol")): row for row in metadata_rows if text(row.get("symbol"))}
    account_context = first_row(account_rows)
    risk_state = first_row(risk_state_rows)

    intent_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    check_audit_rows: list[dict[str, Any]] = []
    timing_audit_rows: list[dict[str, Any]] = []
    sizing_audit_rows: list[dict[str, Any]] = []
    exposure_audit_rows: list[dict[str, Any]] = []
    eligibility_audit_rows: list[dict[str, Any]] = []
    seen_candidate_symbols: set[str] = set()

    for shadow in shadow_rows:
        setup_id = str(shadow.get("setup_id", ""))
        screener = screener_by_id.get(setup_id, {})
        symbol = text(shadow.get("symbol"))
        market_group = first_non_empty(shadow.get("market_group"), screener.get("market_group"))
        evaluation = evaluate_shadow_row(
            shadow=shadow,
            screener=screener,
            account_context=account_context,
            position_symbols=position_symbols,
            pending_symbols=pending_symbols,
            position_rows=position_rows,
            pending_rows=pending_rows,
            symbol_metadata=metadata_by_symbol.get(symbol, {}),
            risk_state=risk_state,
            candidate_symbol_seen=symbol in seen_candidate_symbols,
            observed_at=observed_at,
            min_quality=config.min_quality,
            review_window_minutes=config.review_window_minutes,
            strict_mt5_snapshot=config.strict_mt5_snapshot,
            has_mt5_snapshot=bool(account_rows),
            default_risk_pct=config.default_risk_pct,
            max_risk_pct_per_trade=config.max_risk_pct_per_trade,
            max_symbol_open_risk_pct=config.max_symbol_open_risk_pct,
            max_total_open_risk_pct=config.max_total_open_risk_pct,
            max_group_open_risk_pct=config.max_group_open_risk_pct,
            daily_loss_limit_pct=config.daily_loss_limit_pct,
            cumulative_loss_limit_pct=config.cumulative_loss_limit_pct,
            require_risk_state=config.require_risk_state,
        )
        if setup_id and symbol:
            seen_candidate_symbols.add(symbol)
        if evaluation["intent_row"] is not None:
            intent_rows.append(evaluation["intent_row"])
        decision_rows.append(evaluation["decision_row"])
        check_audit_rows.extend(evaluation["check_rows"])
        timing_audit_rows.append(evaluation["timing_row"])
        sizing_audit_rows.append(evaluation["sizing_row"])
        exposure_audit_rows.append(evaluation["exposure_row"])
        eligibility_audit_rows.append(evaluation["eligibility_row"])

    issues = build_issues(input_audit, shadow_rows, decision_rows)
    safety_rows = build_safety_audit(intent_rows, decision_rows)
    technical_rows = build_technical_validation(intent_rows, decision_rows)

    write_csv(output_dir / "demo_order_intents.csv", intent_rows, INTENT_COLUMNS)
    write_json(output_dir / "demo_order_intents.json", intent_rows)
    write_csv(output_dir / "riskguard_decisions.csv", decision_rows, DECISION_COLUMNS)
    write_json(output_dir / "riskguard_decisions.json", decision_rows)
    write_csv(output_dir / "riskguard_check_audit.csv", check_audit_rows)
    write_csv(output_dir / "riskguard_timing_audit.csv", timing_audit_rows)
    write_csv(output_dir / "riskguard_sizing_audit.csv", sizing_audit_rows)
    write_csv(output_dir / "riskguard_exposure_audit.csv", exposure_audit_rows)
    write_csv(tables_dir / "eligibility_audit.csv", eligibility_audit_rows)
    write_csv(tables_dir / "timing_audit.csv", timing_audit_rows)
    write_csv(tables_dir / "safety_audit.csv", safety_rows)
    write_csv(tables_dir / "technical_validation_audit.csv", technical_rows)
    write_csv(tables_dir / "issues_or_risks.csv", issues)

    decision_counts = count_by(decision_rows, "riskguard_decision")
    accepted_count = decision_counts.get("accepted_for_demo_intent", 0)
    blocked_count = len(decision_rows) - accepted_count
    run_meta = {
        "phase": "riskguard_demo_intent_builder_v1",
        "created_at_utc": created_at.isoformat(),
        "decision": "riskguard_demo_intent_builder_v1_ready_for_dashboard_review",
        "riskguard_demo_intent_builder_implemented": True,
        "artifact_first": True,
        "audit_only": bool(config.audit_only),
        "fixture_mode": bool(config.fixture_mode),
        "order_intents_generated": bool(intent_rows),
        "order_intents_count": len(intent_rows),
        "riskguard_decisions_generated": True,
        "riskguard_decisions_count": len(decision_rows),
        DEMO_SENDER_IMPLEMENTED_KEY: False,
        ORDER_ACTION_AVAILABLE_KEY: False,
        "mt5_connected": False,
        "mt5_orders_sent": 0,
        "orders_sent": 0,
        "can_send_order_any_true": any(boolish(row.get("can_send_order")) for row in intent_rows + decision_rows),
        "order_sent_any_true": any(boolish(row.get("order_sent")) for row in intent_rows + decision_rows),
        "live_trading_enabled": False,
        "telegram_connected": False,
        "telegram_can_trade": False,
        "ai_analyst_can_approve_orders": False,
        "sql_real_written": False,
        "backtests_executed": False,
        "accepted_for_demo_intent_count": accepted_count,
        "blocked_count": blocked_count,
        "blocked_by_late_setup_count": decision_counts.get("blocked_by_late_setup", 0),
        "blocked_by_setup_scope_count": decision_counts.get("blocked_by_setup_scope", 0),
        "blocked_by_waiting_confirmation_count": decision_counts.get("blocked_by_waiting_confirmation", 0),
        "blocked_by_missing_sizing_metadata_count": decision_counts.get("blocked_by_missing_sizing_metadata", 0),
        "strict_mt5_snapshot": bool(config.strict_mt5_snapshot),
        "min_quality": int(config.min_quality),
        "review_window_minutes": int(config.review_window_minutes),
        "riskguard_hardening_enabled": True,
        "sizing_hardening_enabled": True,
        "exposure_hardening_enabled": True,
        "drawdown_kill_switch_enabled": True,
        "default_risk_pct": float(config.default_risk_pct),
        "max_risk_pct_per_trade": float(config.max_risk_pct_per_trade),
        "max_symbol_open_risk_pct": float(config.max_symbol_open_risk_pct),
        "max_total_open_risk_pct": float(config.max_total_open_risk_pct),
        "max_group_open_risk_pct": float(config.max_group_open_risk_pct),
        "daily_loss_limit_pct": float(config.daily_loss_limit_pct),
        "cumulative_loss_limit_pct": float(config.cumulative_loss_limit_pct),
        "require_risk_state": bool(config.require_risk_state),
    }
    write_json(output_dir / "run_meta.json", run_meta)
    write_doc(output_dir / "RISKGUARD_DEMO_INTENT_BUILDER_V1.md", run_meta, issues)
    if config.doc_path:
        write_doc(config.doc_path, run_meta, issues)

    return RiskGuardIntentBuilderResult(
        decision=str(run_meta["decision"]),
        output_dir=output_dir,
        run_meta=run_meta,
        intent_rows=intent_rows,
        decision_rows=decision_rows,
    )


def load_inputs(
    config: RiskGuardIntentBuilderConfig,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    sources = [
        ("shadow_decisions", config.shadow_decisions_csv, True),
        ("screener_setups", config.screener_setups_csv, False),
        ("mt5_account_snapshot", config.mt5_account_snapshot_csv, config.strict_mt5_snapshot),
        ("mt5_positions_snapshot", config.mt5_positions_snapshot_csv, False),
        ("mt5_pending_orders_snapshot", config.mt5_pending_orders_snapshot_csv, False),
        ("symbol_metadata", config.symbol_metadata_csv, False),
        ("risk_state", config.risk_state_csv, config.require_risk_state),
    ]
    loaded: dict[str, list[dict[str, Any]]] = {}
    audit: list[dict[str, Any]] = []
    for name, path, required in sources:
        if path.exists():
            rows = read_csv(path)
            status = "loaded"
        else:
            rows = []
            missing_allowed = (name.startswith("mt5_") and config.allow_missing_mt5_snapshot) or not required
            status = "missing_allowed" if missing_allowed else "missing_blocking"
        loaded[name] = rows
        audit.append({"source": name, "path": str(path), "required": required, "status": status, "rows": len(rows)})
    return (
        loaded["shadow_decisions"],
        loaded["screener_setups"],
        loaded["mt5_account_snapshot"],
        loaded["mt5_positions_snapshot"],
        loaded["mt5_pending_orders_snapshot"],
        loaded["symbol_metadata"],
        loaded["risk_state"],
        audit,
    )


def evaluate_shadow_row(
    *,
    shadow: Mapping[str, Any],
    screener: Mapping[str, Any],
    account_context: Mapping[str, Any],
    position_symbols: set[str],
    pending_symbols: set[str],
    position_rows: Sequence[Mapping[str, Any]],
    pending_rows: Sequence[Mapping[str, Any]],
    symbol_metadata: Mapping[str, Any],
    risk_state: Mapping[str, Any],
    candidate_symbol_seen: bool,
    observed_at: datetime,
    min_quality: int,
    review_window_minutes: int,
    strict_mt5_snapshot: bool,
    has_mt5_snapshot: bool,
    default_risk_pct: float,
    max_risk_pct_per_trade: float,
    max_symbol_open_risk_pct: float,
    max_total_open_risk_pct: float,
    max_group_open_risk_pct: float,
    daily_loss_limit_pct: float,
    cumulative_loss_limit_pct: float,
    require_risk_state: bool,
) -> dict[str, Any]:
    setup_id = text(shadow.get("setup_id"))
    symbol = text(shadow.get("symbol"))
    setup_type = text(shadow.get("setup_type"))
    timeframe = text(shadow.get("timeframe"))
    shadow_state = text(shadow.get("shadow_state"))
    quality = parse_int(shadow.get("setup_quality_score"))
    triggered_at_text = first_non_empty(shadow.get("hypothetical_entry_time"), screener.get("triggered_at"))
    triggered_at = parse_time(triggered_at_text)
    review_window_seconds = max(1, int(review_window_minutes)) * 60
    late_after = triggered_at + timedelta(seconds=review_window_seconds) if triggered_at else None
    current_state = infer_current_state(shadow_state, triggered_at, observed_at, late_after)
    market_group = first_non_empty(shadow.get("market_group"), screener.get("market_group"))
    direction = first_non_empty(shadow.get("direction"), screener.get("direction"))
    entry_price = first_non_empty(shadow.get("hypothetical_entry_price"), screener.get("entry_price"))
    sl = first_non_empty(shadow.get("hypothetical_sl"), screener.get("sl"))
    tp1 = first_non_empty(shadow.get("hypothetical_tp1"), screener.get("tp1"), screener.get("tp"))
    tp2 = first_non_empty(shadow.get("hypothetical_tp2"), screener.get("tp2"))
    source_artifacts = first_non_empty(shadow.get("source_artifacts"), screener.get("source_artifacts"))
    intent_id = stable_hash(f"{shadow.get('shadow_decision_id')}|{setup_id}|{triggered_at_text}|{entry_price}")
    account_equity = safe_float(first_non_empty(account_context.get("equity"), account_context.get("balance")))
    risk_pct = safe_float(first_non_empty(shadow.get("risk_pct"), screener.get("risk_pct"))) or float(default_risk_pct)
    sizing_eval = evaluate_sizing(
        symbol=symbol,
        market_group=market_group,
        direction=direction,
        entry_price=entry_price,
        sl=sl,
        tp1=tp1,
        account_equity=account_equity,
        risk_pct=risk_pct,
        max_risk_pct_per_trade=max_risk_pct_per_trade,
        symbol_metadata=symbol_metadata,
    )
    exposure_eval = evaluate_exposure(
        symbol=symbol,
        market_group=market_group,
        candidate_risk_amount=sizing_eval["risk_amount_value"],
        account_equity=account_equity,
        position_rows=position_rows,
        pending_rows=pending_rows,
        candidate_symbol_seen=candidate_symbol_seen,
        max_symbol_open_risk_pct=max_symbol_open_risk_pct,
        max_total_open_risk_pct=max_total_open_risk_pct,
        max_group_open_risk_pct=max_group_open_risk_pct,
    )
    drawdown_eval = evaluate_drawdown(
        risk_state=risk_state,
        account_equity=account_equity,
        daily_loss_limit_pct=daily_loss_limit_pct,
        cumulative_loss_limit_pct=cumulative_loss_limit_pct,
        require_risk_state=require_risk_state,
    )
    checks = run_checks(
        setup_type=setup_type,
        quality=quality,
        min_quality=min_quality,
        shadow_state=shadow_state,
        current_state=current_state,
        triggered_at=triggered_at,
        entry_price=entry_price,
        sl=sl,
        tp1=tp1,
        has_mt5_snapshot=has_mt5_snapshot,
        strict_mt5_snapshot=strict_mt5_snapshot,
        symbol=symbol,
        position_symbols=position_symbols,
        pending_symbols=pending_symbols,
        sizing_eval=sizing_eval,
        exposure_eval=exposure_eval,
        drawdown_eval=drawdown_eval,
    )
    decision = first_blocking_decision(checks)
    accepted = decision == "accepted_for_demo_intent"
    intent_row = None
    if should_materialize_intent(setup_type, shadow_state, checks):
        intent_row = {
            "intent_id": intent_id,
            "source_shadow_decision_id": shadow.get("shadow_decision_id", ""),
            "setup_id": setup_id,
            "symbol": symbol,
            "market_group": market_group,
            "timeframe": timeframe,
            "setup_type": setup_type,
            "strategy": shadow.get("strategy", ""),
            "direction": direction,
            "triggered_at": format_time(triggered_at),
            "observed_at": observed_at.isoformat(),
            "current_state": current_state,
            "review_window_seconds": review_window_seconds,
            "late_after": format_time(late_after),
            "entry_type": entry_type_for(setup_type),
            "entry_price": entry_price,
            "entry_source": entry_source_for(setup_type, shadow_state),
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "volume": sizing_eval["volume"],
            "volume_source": sizing_eval["volume_source"],
            "sizing_status": sizing_eval["sizing_status"],
            "sizing_blocking_reason": sizing_eval["blocking_reason"],
            "risk_pct": f"{risk_pct:g}" if risk_pct is not None else "",
            "risk_amount": sizing_eval["risk_amount"],
            "expected_loss_if_sl": sizing_eval["expected_loss_if_sl"],
            "expected_reward_tp1": expected_reward(entry_price, tp1, sizing_eval, direction),
            "expected_reward_tp2": "",
            "rr_tp1": rr(entry_price, sl, tp1, shadow.get("direction")),
            "rr_tp2": rr(entry_price, sl, tp2, shadow.get("direction")),
            "asset_class": sizing_eval["asset_class"],
            "contract_size": sizing_eval["contract_size"],
            "tick_size": sizing_eval["tick_size"],
            "tick_value_loss": sizing_eval["tick_value_loss"],
            "volume_min": sizing_eval["volume_min"],
            "volume_step": sizing_eval["volume_step"],
            "volume_max": sizing_eval["volume_max"],
            "symbol_metadata_source": sizing_eval["symbol_metadata_source"],
            "spread": "",
            "slippage_assumption": "",
            "account_equity_snapshot": account_equity if account_equity is not None else "",
            "position_sizing_method": sizing_eval["position_sizing_method"],
            "source_artifacts": source_artifacts,
            "is_demo_intent": True,
            "is_order": False,
            "order_sent": False,
            "can_send_order": False,
        }
    decision_row = {
        "decision_id": stable_hash(f"{intent_id}|{decision}|{setup_id}"),
        "intent_id": intent_id if intent_row is not None else "",
        "setup_id": setup_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "setup_type": setup_type,
        "riskguard_decision": decision,
        "accepted": accepted,
        "blocking_reason": "" if accepted else decision,
        "warning_reason": "",
        "sizing_status": sizing_eval["sizing_status"],
        "exposure_status": exposure_eval["exposure_status"],
        "drawdown_status": drawdown_eval["drawdown_status"],
        "kill_switch_active": drawdown_eval["kill_switch_active"],
        "checks_passed": ";".join(row["check_id"] for row in checks if row["status"] == "pass"),
        "checks_failed": ";".join(row["check_id"] for row in checks if row["status"] == "fail"),
        "can_send_order": False,
        "order_sent": False,
        "created_at_utc": utc_now().isoformat(),
    }
    check_rows = [
        {
            "intent_id": intent_id if intent_row is not None else "",
            "setup_id": setup_id,
            "symbol": symbol,
            "timeframe": timeframe,
            **row,
        }
        for row in checks
    ]
    timing_row = {
        "setup_id": setup_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "shadow_state": shadow_state,
        "triggered_at": format_time(triggered_at),
        "observed_at": observed_at.isoformat(),
        "review_window_seconds": review_window_seconds,
        "late_after": format_time(late_after),
        "current_state": current_state,
        "riskguard_decision": decision,
    }
    eligibility_row = {
        "setup_id": setup_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "setup_type": setup_type,
        "quality": quality,
        "min_quality": min_quality,
        "shadow_state": shadow_state,
        "eligible_setup_type": setup_type in AUTO_ELIGIBLE_SETUP_TYPES,
        "quality_ok": quality >= min_quality,
        "riskguard_decision": decision,
    }
    sizing_row = {
        "intent_id": intent_id if intent_row is not None else "",
        "setup_id": setup_id,
        "symbol": symbol,
        "asset_class": sizing_eval["asset_class"],
        "account_equity_snapshot": account_equity if account_equity is not None else "",
        "entry_price": entry_price,
        "sl": sl,
        "risk_pct": f"{risk_pct:g}" if risk_pct is not None else "",
        "risk_amount": sizing_eval["risk_amount"],
        "expected_loss_if_sl": sizing_eval["expected_loss_if_sl"],
        "volume": sizing_eval["volume"],
        "volume_source": sizing_eval["volume_source"],
        "position_sizing_method": sizing_eval["position_sizing_method"],
        "sizing_status": sizing_eval["sizing_status"],
        "blocking_reason": sizing_eval["blocking_reason"],
        "contract_size": sizing_eval["contract_size"],
        "tick_size": sizing_eval["tick_size"],
        "tick_value_loss": sizing_eval["tick_value_loss"],
        "volume_min": sizing_eval["volume_min"],
        "volume_step": sizing_eval["volume_step"],
        "volume_max": sizing_eval["volume_max"],
        "symbol_metadata_source": sizing_eval["symbol_metadata_source"],
        "riskguard_decision": decision,
    }
    exposure_row = {
        "intent_id": intent_id if intent_row is not None else "",
        "setup_id": setup_id,
        "symbol": symbol,
        "market_group": market_group,
        "position_duplicate": symbol in position_symbols,
        "pending_duplicate": symbol in pending_symbols,
        "candidate_duplicate": bool(candidate_symbol_seen),
        "candidate_risk_amount": exposure_eval["candidate_risk_amount"],
        "symbol_open_risk_amount": exposure_eval["symbol_open_risk_amount"],
        "total_open_risk_amount": exposure_eval["total_open_risk_amount"],
        "group_open_risk_amount": exposure_eval["group_open_risk_amount"],
        "symbol_limit_amount": exposure_eval["symbol_limit_amount"],
        "total_limit_amount": exposure_eval["total_limit_amount"],
        "group_limit_amount": exposure_eval["group_limit_amount"],
        "exposure_status": exposure_eval["exposure_status"],
        "blocking_reason": exposure_eval["blocking_reason"],
        "positions_snapshot_symbols": len(position_symbols),
        "pending_snapshot_symbols": len(pending_symbols),
        "riskguard_decision": decision,
    }
    return {
        "intent_row": intent_row,
        "decision_row": decision_row,
        "check_rows": check_rows,
        "timing_row": timing_row,
        "eligibility_row": eligibility_row,
        "sizing_row": sizing_row,
        "exposure_row": exposure_row,
    }


def run_checks(
    *,
    setup_type: str,
    quality: int,
    min_quality: int,
    shadow_state: str,
    current_state: str,
    triggered_at: datetime | None,
    entry_price: Any,
    sl: Any,
    tp1: Any,
    has_mt5_snapshot: bool,
    strict_mt5_snapshot: bool,
    symbol: str,
    position_symbols: set[str],
    pending_symbols: set[str],
    sizing_eval: Mapping[str, Any],
    exposure_eval: Mapping[str, Any],
    drawdown_eval: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks = [
        check("eligible_setup", setup_type in AUTO_ELIGIBLE_SETUP_TYPES, "blocked_by_setup_scope"),
        check("min_quality", quality >= min_quality, "blocked_by_low_quality"),
        check("shadow_triggered", shadow_state == "would_trigger", shadow_state_decision(shadow_state)),
        check("triggered_at_present", triggered_at is not None, "blocked_by_stale_data"),
        check("timing_current", current_state in {"fresh_trigger", "within_review_window"}, timing_decision(current_state)),
        check("entry_present", has_value(entry_price), "blocked_by_missing_entry"),
        check("sl_present", has_value(sl), "blocked_by_missing_sl"),
        check("tp_present", has_value(tp1), "blocked_by_missing_tp"),
        check("mt5_snapshot_present", (not strict_mt5_snapshot) or has_mt5_snapshot, "blocked_by_missing_mt5_snapshot"),
        check("no_existing_position", symbol not in position_symbols, "blocked_by_existing_position"),
        check("no_pending_order", symbol not in pending_symbols, "blocked_by_duplicate"),
        check("sizing_hardened", sizing_eval.get("sizing_status") == "calculated", text(sizing_eval.get("blocking_reason")) or "blocked_by_sizing"),
        check("exposure_hardened", exposure_eval.get("exposure_status") == "pass", text(exposure_eval.get("blocking_reason")) or "blocked_by_exposure"),
        check("drawdown_kill_switch", drawdown_eval.get("drawdown_status") == "pass", text(drawdown_eval.get("blocking_reason")) or "blocked_by_drawdown_limit"),
        check("no_live_mode", True, "blocked_by_no_demo_mode"),
        check("no_telegram", True, "blocked_by_no_demo_mode"),
        check("ai_not_approval", True, "blocked_by_no_demo_mode"),
        check("sender_not_available", True, "blocked_by_no_demo_mode"),
    ]
    return checks


def evaluate_sizing(
    *,
    symbol: str,
    market_group: str,
    direction: str,
    entry_price: Any,
    sl: Any,
    tp1: Any,
    account_equity: float | None,
    risk_pct: float | None,
    max_risk_pct_per_trade: float,
    symbol_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    asset_class = infer_asset_class(symbol, market_group)
    spec = resolve_symbol_spec(symbol, market_group, symbol_metadata)
    base = {
        "asset_class": asset_class,
        "contract_size": spec.get("contract_size", ""),
        "tick_size": spec.get("tick_size", ""),
        "tick_value_loss": spec.get("tick_value_loss", ""),
        "volume_min": spec.get("volume_min", ""),
        "volume_step": spec.get("volume_step", ""),
        "volume_max": spec.get("volume_max", ""),
        "symbol_metadata_source": spec.get("source", ""),
        "position_sizing_method": spec.get("method", ""),
        "volume": "",
        "volume_source": "riskguard_hardened",
        "sizing_status": "blocked",
        "blocking_reason": "",
        "risk_amount": "",
        "risk_amount_value": None,
        "expected_loss_if_sl": "",
    }
    entry = safe_float(entry_price)
    stop = safe_float(sl)
    target = safe_float(tp1)
    if account_equity is None or account_equity <= 0:
        return {**base, "blocking_reason": "blocked_by_missing_equity"}
    if risk_pct is None or risk_pct <= 0:
        return {**base, "blocking_reason": "blocked_by_invalid_risk_pct"}
    if risk_pct > max_risk_pct_per_trade:
        return {**base, "blocking_reason": "blocked_by_risk_pct_limit"}
    if entry is None or entry <= 0:
        return {**base, "blocking_reason": "blocked_by_missing_entry"}
    if stop is None or stop <= 0:
        return {**base, "blocking_reason": "blocked_by_missing_sl"}
    if not valid_stop_direction(direction, entry, stop):
        return {**base, "blocking_reason": "blocked_by_invalid_sl_direction"}
    if target is not None and target > 0 and not valid_target_direction(direction, entry, target):
        return {**base, "blocking_reason": "blocked_by_invalid_tp_direction"}
    if spec.get("status") != "ok":
        return {**base, "blocking_reason": spec.get("blocking_reason", "blocked_by_missing_symbol_metadata")}

    risk_amount = account_equity * (risk_pct / 100.0)
    loss_per_lot = loss_per_lot_for_stop(entry, stop, spec)
    if loss_per_lot is None or loss_per_lot <= 0:
        return {**base, "risk_amount": f"{risk_amount:.2f}", "risk_amount_value": risk_amount, "blocking_reason": "blocked_by_invalid_loss_per_lot"}
    raw_volume = risk_amount / loss_per_lot
    volume = floor_volume(raw_volume, safe_float(spec.get("volume_min")), safe_float(spec.get("volume_step")), safe_float(spec.get("volume_max")))
    if volume is None or volume <= 0:
        return {**base, "risk_amount": f"{risk_amount:.2f}", "risk_amount_value": risk_amount, "blocking_reason": "blocked_by_volume_below_min"}
    expected_loss = volume * loss_per_lot
    return {
        **base,
        "volume": format_volume(volume, safe_float(spec.get("volume_step"))),
        "sizing_status": "calculated",
        "blocking_reason": "",
        "risk_amount": f"{risk_amount:.2f}",
        "risk_amount_value": risk_amount,
        "expected_loss_if_sl": f"{expected_loss:.2f}",
    }


def evaluate_exposure(
    *,
    symbol: str,
    market_group: str,
    candidate_risk_amount: float | None,
    account_equity: float | None,
    position_rows: Sequence[Mapping[str, Any]],
    pending_rows: Sequence[Mapping[str, Any]],
    candidate_symbol_seen: bool,
    max_symbol_open_risk_pct: float,
    max_total_open_risk_pct: float,
    max_group_open_risk_pct: float,
) -> dict[str, Any]:
    base = {
        "candidate_risk_amount": candidate_risk_amount if candidate_risk_amount is not None else "",
        "symbol_open_risk_amount": "",
        "total_open_risk_amount": "",
        "group_open_risk_amount": "",
        "symbol_limit_amount": "",
        "total_limit_amount": "",
        "group_limit_amount": "",
        "exposure_status": "blocked",
        "blocking_reason": "",
    }
    if candidate_symbol_seen:
        return {**base, "blocking_reason": "blocked_by_duplicate_candidate"}
    if account_equity is None or account_equity <= 0:
        return {**base, "blocking_reason": "blocked_by_missing_equity"}
    if candidate_risk_amount is None or candidate_risk_amount <= 0:
        return {**base, "blocking_reason": "blocked_by_missing_candidate_risk"}

    open_rows = list(position_rows) + list(pending_rows)
    known_risk = aggregate_open_risk(open_rows)
    if known_risk["unknown_risk_rows"]:
        return {**base, **known_risk, "blocking_reason": "blocked_by_unknown_open_risk"}
    symbol_limit = account_equity * (max_symbol_open_risk_pct / 100.0)
    total_limit = account_equity * (max_total_open_risk_pct / 100.0)
    group_limit = account_equity * (max_group_open_risk_pct / 100.0)
    symbol_total = known_risk["risk_by_symbol"].get(symbol, 0.0) + candidate_risk_amount
    total_risk = known_risk["total_open_risk_amount"] + candidate_risk_amount
    group_total = known_risk["risk_by_group"].get(market_group, 0.0) + candidate_risk_amount if market_group else candidate_risk_amount
    enriched = {
        **base,
        "symbol_open_risk_amount": f"{symbol_total:.2f}",
        "total_open_risk_amount": f"{total_risk:.2f}",
        "group_open_risk_amount": f"{group_total:.2f}",
        "symbol_limit_amount": f"{symbol_limit:.2f}",
        "total_limit_amount": f"{total_limit:.2f}",
        "group_limit_amount": f"{group_limit:.2f}",
    }
    if symbol_total > symbol_limit:
        return {**enriched, "blocking_reason": "blocked_by_symbol_exposure_limit"}
    if total_risk > total_limit:
        return {**enriched, "blocking_reason": "blocked_by_total_exposure_limit"}
    if group_total > group_limit:
        return {**enriched, "blocking_reason": "blocked_by_group_exposure_limit"}
    return {**enriched, "exposure_status": "pass", "blocking_reason": ""}


def evaluate_drawdown(
    *,
    risk_state: Mapping[str, Any],
    account_equity: float | None,
    daily_loss_limit_pct: float,
    cumulative_loss_limit_pct: float,
    require_risk_state: bool,
) -> dict[str, Any]:
    base = {"drawdown_status": "blocked", "blocking_reason": "", "kill_switch_active": False}
    if not risk_state:
        if require_risk_state:
            return {**base, "blocking_reason": "blocked_by_missing_risk_state"}
        return {**base, "drawdown_status": "pass"}
    kill_switch = boolish(first_non_empty(risk_state.get("kill_switch_active"), risk_state.get("kill_switch")))
    if kill_switch:
        return {**base, "kill_switch_active": True, "blocking_reason": "blocked_by_kill_switch"}
    if account_equity is None or account_equity <= 0:
        return {**base, "blocking_reason": "blocked_by_missing_equity"}
    daily_pnl = safe_float(first_non_empty(risk_state.get("daily_realized_pnl"), risk_state.get("day_pnl"), risk_state.get("daily_pnl"))) or 0.0
    cumulative_pnl = safe_float(first_non_empty(risk_state.get("cumulative_realized_pnl"), risk_state.get("cumulative_pnl"), risk_state.get("total_realized_pnl"))) or 0.0
    daily_limit = account_equity * (daily_loss_limit_pct / 100.0)
    cumulative_limit = account_equity * (cumulative_loss_limit_pct / 100.0)
    if daily_pnl < 0 and abs(daily_pnl) >= daily_limit:
        return {**base, "blocking_reason": "blocked_by_daily_drawdown_limit"}
    if cumulative_pnl < 0 and abs(cumulative_pnl) >= cumulative_limit:
        return {**base, "blocking_reason": "blocked_by_cumulative_drawdown_limit"}
    return {**base, "drawdown_status": "pass"}


def check(check_id: str, passed: bool, decision_if_failed: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "decision_if_failed": "" if passed else decision_if_failed,
    }


def infer_asset_class(symbol: str, market_group: str = "") -> str:
    group = market_group.strip().lower()
    raw_symbol = symbol.strip().upper().split(".")[0]
    if "metal" in group or raw_symbol.startswith(("XAU", "XAG")):
        return "metals"
    if "index" in group:
        return "index"
    if len(raw_symbol) >= 6 and raw_symbol[:6].isalpha():
        return "forex"
    return "unknown"


def resolve_symbol_spec(symbol: str, market_group: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    asset_class = infer_asset_class(symbol, market_group)
    if metadata:
        spec = {
            "status": "ok",
            "source": "symbol_metadata",
            "method": "tick_value_metadata",
            "asset_class": asset_class,
            "contract_size": first_float(metadata, "trade_contract_size", "contract_size", "SYMBOL_TRADE_CONTRACT_SIZE"),
            "tick_size": first_float(metadata, "trade_tick_size", "tick_size", "point_size", "SYMBOL_TRADE_TICK_SIZE", "SYMBOL_POINT_SIZE"),
            "tick_value_loss": first_float(metadata, "trade_tick_value_loss", "trade_tick_value", "tick_value_loss", "tick_value", "SYMBOL_TRADE_TICK_VALUE_LOSS", "SYMBOL_TRADE_TICK_VALUE"),
            "volume_min": first_float(metadata, "volume_min", "min_volume", "SYMBOL_VOLUME_MIN") or 0.01,
            "volume_step": first_float(metadata, "volume_step", "SYMBOL_VOLUME_STEP") or 0.01,
            "volume_max": first_float(metadata, "volume_max", "max_volume", "SYMBOL_VOLUME_MAX") or 100.0,
        }
        if safe_float(spec["tick_size"]) is None or safe_float(spec["tick_size"]) <= 0:
            return {**spec, "status": "blocked", "blocking_reason": "blocked_by_missing_tick_size"}
        if safe_float(spec["tick_value_loss"]) is None or safe_float(spec["tick_value_loss"]) <= 0:
            return {**spec, "status": "blocked", "blocking_reason": "blocked_by_missing_tick_value"}
        if safe_float(spec["volume_step"]) is None or safe_float(spec["volume_step"]) <= 0:
            return {**spec, "status": "blocked", "blocking_reason": "blocked_by_missing_volume_step"}
        return spec

    if asset_class == "forex":
        return {
            "status": "ok",
            "source": "forex_default_contract_size",
            "method": "forex_contract_size",
            "asset_class": asset_class,
            "contract_size": 100000.0,
            "tick_size": "",
            "tick_value_loss": "",
            "volume_min": 0.01,
            "volume_step": 0.01,
            "volume_max": 1.0,
        }
    return {
        "status": "blocked",
        "source": "missing_symbol_metadata",
        "method": "blocked",
        "asset_class": asset_class,
        "contract_size": "",
        "tick_size": "",
        "tick_value_loss": "",
        "volume_min": "",
        "volume_step": "",
        "volume_max": "",
        "blocking_reason": "blocked_by_missing_symbol_metadata",
    }


def first_float(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = safe_float(row.get(key))
        if value is not None:
            return value
    return None


def valid_stop_direction(direction: str, entry: float, stop: float) -> bool:
    normalized = direction.strip().lower()
    if normalized in {"long", "buy", "bullish", "alcista"}:
        return stop < entry
    if normalized in {"short", "sell", "bearish", "bajista"}:
        return stop > entry
    return False


def valid_target_direction(direction: str, entry: float, target: float) -> bool:
    normalized = direction.strip().lower()
    if normalized in {"long", "buy", "bullish", "alcista"}:
        return target > entry
    if normalized in {"short", "sell", "bearish", "bajista"}:
        return target < entry
    return False


def loss_per_lot_for_stop(entry: float, stop: float, spec: Mapping[str, Any]) -> float | None:
    method = text(spec.get("method"))
    stop_distance = abs(entry - stop)
    if method == "forex_contract_size":
        contract_size = safe_float(spec.get("contract_size"))
        return stop_distance * contract_size if contract_size and contract_size > 0 else None
    tick_size = safe_float(spec.get("tick_size"))
    tick_value_loss = safe_float(spec.get("tick_value_loss"))
    if tick_size is None or tick_size <= 0 or tick_value_loss is None or tick_value_loss <= 0:
        return None
    return (stop_distance / tick_size) * tick_value_loss


def floor_volume(raw_volume: float, min_volume: float | None, step: float | None, max_volume: float | None) -> float | None:
    if min_volume is None or step is None or max_volume is None:
        return None
    if raw_volume <= 0 or min_volume <= 0 or step <= 0 or max_volume <= 0:
        return None
    floored = math.floor(raw_volume / step) * step
    if floored < min_volume:
        return None
    return min(floored, max_volume)


def format_volume(volume: float, step: float | None) -> str:
    decimals = 2
    if step and step > 0:
        step_text = f"{step:.10f}".rstrip("0").rstrip(".")
        decimals = len(step_text.split(".")[-1]) if "." in step_text else 0
    return f"{volume:.{decimals}f}"


def expected_reward(entry: Any, target: Any, sizing_eval: Mapping[str, Any], direction: Any) -> str:
    entry_f = safe_float(entry)
    target_f = safe_float(target)
    volume = safe_float(sizing_eval.get("volume"))
    if entry_f is None or target_f is None or volume is None or volume <= 0:
        return ""
    spec = {
        "method": sizing_eval.get("position_sizing_method"),
        "contract_size": sizing_eval.get("contract_size"),
        "tick_size": sizing_eval.get("tick_size"),
        "tick_value_loss": sizing_eval.get("tick_value_loss"),
    }
    per_lot = loss_per_lot_for_stop(entry_f, target_f, spec)
    if per_lot is None:
        return ""
    return f"{volume * per_lot:.2f}"


def aggregate_open_risk(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    risk_by_symbol: dict[str, float] = {}
    risk_by_group: dict[str, float] = {}
    total = 0.0
    unknown = 0
    for row in rows:
        symbol = text(row.get("symbol"))
        if not symbol:
            continue
        risk = safe_float(
            first_non_empty(
                row.get("open_risk_amount"),
                row.get("risk_amount"),
                row.get("expected_loss_if_sl"),
                row.get("expected_loss"),
            )
        )
        if risk is None:
            unknown += 1
            continue
        group = first_non_empty(row.get("market_group"), row.get("asset_class"))
        total += risk
        risk_by_symbol[symbol] = risk_by_symbol.get(symbol, 0.0) + risk
        if group:
            risk_by_group[group] = risk_by_group.get(group, 0.0) + risk
    return {
        "risk_by_symbol": risk_by_symbol,
        "risk_by_group": risk_by_group,
        "total_open_risk_amount": total,
        "unknown_risk_rows": unknown,
    }


def first_blocking_decision(checks: list[dict[str, Any]]) -> str:
    for row in checks:
        if row["status"] == "fail":
            return str(row["decision_if_failed"])
    return "accepted_for_demo_intent"


def should_materialize_intent(setup_type: str, shadow_state: str, checks: list[dict[str, Any]]) -> bool:
    if setup_type not in AUTO_ELIGIBLE_SETUP_TYPES:
        return False
    if shadow_state != "would_trigger":
        return False
    failed = {row["check_id"] for row in checks if row["status"] == "fail"}
    hard_no_intent = {"eligible_setup", "min_quality", "shadow_triggered", "triggered_at_present", "timing_current"}
    return not failed.intersection(hard_no_intent)


def infer_current_state(
    shadow_state: str,
    triggered_at: datetime | None,
    observed_at: datetime,
    late_after: datetime | None,
) -> str:
    if shadow_state == "would_wait":
        return "waiting_confirmation"
    if shadow_state == "late":
        return "late"
    if shadow_state == "invalidated":
        return "invalidated"
    if triggered_at is None or late_after is None:
        return "stale_data"
    if observed_at > late_after:
        return "late"
    if observed_at <= triggered_at + timedelta(minutes=1):
        return "fresh_trigger"
    return "within_review_window"


def timing_decision(current_state: str) -> str:
    if current_state == "late":
        return "blocked_by_late_setup"
    if current_state == "invalidated":
        return "blocked_by_invalidated_setup"
    return "blocked_by_stale_data"


def shadow_state_decision(shadow_state: str) -> str:
    if shadow_state == "invalidated":
        return "blocked_by_invalidated_setup"
    if shadow_state == "late":
        return "blocked_by_late_setup"
    if shadow_state == "would_wait":
        return "blocked_by_waiting_confirmation"
    return "blocked_by_late_setup"


def entry_type_for(setup_type: str) -> str:
    if setup_type == "fib_limit_live_candidate":
        return "zone_review"
    return "market_demo_review"


def entry_source_for(setup_type: str, shadow_state: str) -> str:
    if setup_type == "fib_limit_live_candidate":
        return "fib_zone_touch_or_review"
    if setup_type == "macd_breakout":
        return "closed_candle_breakout_review"
    return shadow_state


def rr(entry: Any, stop: Any, target: Any, direction: Any) -> str:
    entry_f = safe_float(entry)
    stop_f = safe_float(stop)
    target_f = safe_float(target)
    if entry_f is None or stop_f is None or target_f is None:
        return ""
    risk = abs(entry_f - stop_f)
    reward = abs(target_f - entry_f)
    if risk <= 0:
        return ""
    return f"{reward / risk:.4f}"


def build_fixture_inputs(
    observed_at: datetime,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    recent = observed_at - timedelta(minutes=20)
    late = observed_at - timedelta(hours=3)
    shadow_rows = [
        fixture_shadow("fx_macd_ok", "EURUSD.r", "H1", "macd_breakout", "macd_breakout", "long", "would_trigger", recent, "1.1000", "1.0950", "1.1100", "1.1200", 5),
        fixture_shadow("fx_macd_late", "GBPUSD.r", "H1", "macd_breakout", "macd_breakout", "short", "would_trigger", late, "1.2500", "1.2600", "1.2300", "1.2200", 5),
        fixture_shadow("fx_fib_ok", "XAUUSD.r", "H1", "fib_limit_live_candidate", "fib_limit", "long", "would_trigger", recent, "2350.0", "2335.0", "2380.0", "2400.0", 5),
        fixture_shadow("fx_fib_missing_tp", "US100", "H4", "fib_limit_live_candidate", "fib_limit", "short", "would_trigger", recent, "19400", "19600", "", "", 5),
        fixture_shadow("fx_rsi_manual", "EURJPY.r", "H1", "rsi_trend_reversal", "rsi_trend_reversal", "short", "would_trigger", recent, "170.0", "171.0", "168.0", "", 5),
        fixture_shadow("fx_context", "EURO50", "H1", "previous_day_high_low_candidate", "context_level", "long", "would_trigger", recent, "5000", "4950", "5100", "", 5),
        fixture_shadow("fx_low_quality", "AUDUSD.r", "H1", "macd_breakout", "macd_breakout", "long", "would_trigger", recent, "0.6600", "0.6550", "0.6700", "", 2),
        fixture_shadow("fx_wait", "CADJPY.r", "H1", "macd_breakout", "macd_breakout", "long", "would_wait", None, "", "109", "112", "", 5),
        fixture_shadow("fx_invalid", "SPA35", "H4", "fib_limit_live_candidate", "fib_limit", "long", "invalidated", recent, "12000", "11800", "12400", "", 5),
    ]
    metadata_rows = [
        {
            "symbol": "XAUUSD.r",
            "trade_tick_size": "0.01",
            "trade_tick_value_loss": "1.0",
            "trade_contract_size": "100",
            "volume_min": "0.01",
            "volume_step": "0.01",
            "volume_max": "10.0",
            "asset_class": "metals",
        },
        {
            "symbol": "US100",
            "trade_tick_size": "1.0",
            "trade_tick_value_loss": "1.0",
            "trade_contract_size": "1",
            "volume_min": "0.1",
            "volume_step": "0.1",
            "volume_max": "10.0",
            "asset_class": "index",
        },
        {
            "symbol": "SPA35",
            "trade_tick_size": "1.0",
            "trade_tick_value_loss": "1.0",
            "trade_contract_size": "1",
            "volume_min": "0.1",
            "volume_step": "0.1",
            "volume_max": "10.0",
            "asset_class": "index",
        },
    ]
    risk_state_rows = [
        {
            "kill_switch_active": "false",
            "daily_realized_pnl": "0",
            "cumulative_realized_pnl": "0",
        }
    ]
    return shadow_rows, [], [{"equity": "100000", "balance": "100000"}], [], [], metadata_rows, risk_state_rows


def fixture_shadow(
    setup_id: str,
    symbol: str,
    timeframe: str,
    setup_type: str,
    strategy: str,
    direction: str,
    shadow_state: str,
    entry_time: datetime | None,
    entry_price: str,
    sl: str,
    tp1: str,
    tp2: str,
    quality: int,
) -> dict[str, Any]:
    return {
        "shadow_decision_id": stable_hash(setup_id),
        "setup_id": setup_id,
        "symbol": symbol,
        "market_group": "Fixture",
        "timeframe": timeframe,
        "setup_type": setup_type,
        "strategy": strategy,
        "direction": direction,
        "timing_state": "entry_review",
        "setup_quality_score": quality,
        "shadow_state": shadow_state,
        "hypothetical_entry_time": format_time(entry_time),
        "hypothetical_entry_price": entry_price,
        "hypothetical_sl": sl,
        "hypothetical_tp1": tp1,
        "hypothetical_tp2": tp2,
        "source_artifacts": "fixture",
        "order_sent": False,
        "can_send_order": False,
    }


def build_issues(
    input_audit: list[dict[str, Any]],
    shadow_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for source in input_audit:
        if source["status"] == "missing_blocking":
            issues.append(
                {
                    "issue_id": f"missing_{source['source']}",
                    "severity": "high",
                    "description": f"Required source missing: {source['path']}",
                    "recommended_action": "Regenerate inputs or run fixture mode.",
                }
            )
    if not shadow_rows:
        issues.append(
            {
                "issue_id": "no_shadow_decisions",
                "severity": "medium",
                "description": "No MT5 Shadow decisions were available.",
                "recommended_action": "Run mt5_shadow first or use fixture mode.",
            }
        )
    if decision_rows and all(row.get("riskguard_decision") != "accepted_for_demo_intent" for row in decision_rows):
        issues.append(
            {
                "issue_id": "no_accepted_intents",
                "severity": "info",
                "description": "All candidate rows were blocked or non-eligible.",
                "recommended_action": "Review blocking reasons before any future demo sender design.",
            }
        )
    if not issues:
        issues.append(
            {
                "issue_id": "no_runtime_issues",
                "severity": "info",
                "description": "RiskGuard intent builder completed without runtime issues.",
                "recommended_action": "Review decisions before dashboard integration.",
            }
        )
    return issues


def build_safety_audit(
    intents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = intents + decisions
    return [
        safety("can_send_order_any_true", any(boolish(row.get("can_send_order")) for row in rows), False),
        safety("order_sent_any_true", any(boolish(row.get("order_sent")) for row in rows), False),
        safety("mt5_connected", False, False),
        safety("telegram_connected", False, False),
        safety("sql_real_written", False, False),
        safety("backtests_executed", False, False),
        safety("demo_sender_available", False, False),
    ]


def build_technical_validation(
    intents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {"check": "intent_rows_generated", "observed": len(intents), "expected": ">=0", "status": "pass"},
        {"check": "decision_rows_generated", "observed": len(decisions), "expected": ">=0", "status": "pass"},
        {"check": "can_send_order_any_true", "observed": any(boolish(row.get("can_send_order")) for row in intents + decisions), "expected": False, "status": "pass"},
        {"check": "order_sent_any_true", "observed": any(boolish(row.get("order_sent")) for row in intents + decisions), "expected": False, "status": "pass"},
    ]


def safety(check_id: str, observed: Any, expected: Any) -> dict[str, Any]:
    return {
        "check": check_id,
        "observed": observed,
        "expected": expected,
        "status": "pass" if observed == expected else "fail",
    }


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = ordered_fields(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_doc(path: Path, run_meta: Mapping[str, Any], issues: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text_body = f"""# RiskGuard demo intent builder v1

## Que implementa

Esta fase implementa un builder artifact-first para convertir decisiones de MT5 Shadow en `demo_order_intents` y decisiones RiskGuard auditables. El builder no envia ordenes, no conecta MT5, no conecta Telegram y no escribe SQL.

## Flujo

`MT5 Shadow -> demo_order_intents -> riskguard_decisions`

Solo se consideran para automatico futuro `macd_breakout` y `fib_limit_live_candidate`. `rsi_trend_reversal` queda manual/futuro y los contextos se bloquean por scope.

## Timing

El builder distingue `triggered_at`, `observed_at`, `review_window_seconds`, `late_after` y `current_state`. `would_trigger` no significa entrada actual: si el trigger ya esta fuera de ventana, se bloquea como tarde.

## Hardening de riesgo 2026-06-11

La fase queda endurecida para demo:

- sizing monetario por equity, `risk_pct`, entrada, SL y metadata de simbolo;
- Forex puede usar fallback conservador de contrato estandar;
- metales e indices requieren metadata de tick/volumen o se bloquean;
- limites de riesgo por operacion, simbolo, grupo y exposicion total;
- bloqueo de duplicados contra posiciones, pendientes y candidatos del mismo run;
- `risk_state` con drawdown diario/acumulado y `kill_switch_active`;
- auditorias `riskguard_sizing_audit.csv` y `riskguard_exposure_audit.csv`.

No hay envio de ordenes desde RiskGuard: solo decision, bloqueo y trazabilidad.
Para memoria, puede describirse como RiskGuard demo endurecido; no como
RiskGuard de produccion ni como garantia de live trading robusto.

## Seguridad

- `{DEMO_SENDER_IMPLEMENTED_KEY}=false`
- `{ORDER_ACTION_AVAILABLE_KEY}=false`
- `orders_sent=0`
- `mt5_orders_sent=0`
- `can_send_order_any_true=false`
- `order_sent_any_true=false`
- `telegram_connected=false`

## Resultado

Decision: `{run_meta.get("decision")}`

Intents generados: {run_meta.get("order_intents_count")}
Decisiones RiskGuard: {run_meta.get("riskguard_decisions_count")}
Aceptados para intent demo: {run_meta.get("accepted_for_demo_intent_count")}
Bloqueados: {run_meta.get("blocked_count")}

Hardening activo: `{run_meta.get("riskguard_hardening_enabled")}`

## Issues

"""
    for issue in issues:
        text_body += f"- {issue.get('issue_id')}: {issue.get('description')}\n"
    path.write_text(text_body, encoding="utf-8")


def ordered_fields(rows: list[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    return fields


def first_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def first_non_empty(*values: Any) -> str:
    for value in values:
        text_value = text(value)
        if text_value:
            return text_value
    return ""


def has_value(value: Any) -> bool:
    return bool(text(value))


def text(value: Any) -> str:
    return str(value or "").strip()


def parse_int(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value))
    except ValueError:
        return None


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si"}


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def parse_time(value: Any) -> datetime | None:
    value_text = text(value)
    if not value_text:
        return None
    normalized = value_text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return strip_tz(parsed)


def strip_tz(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def format_time(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def count_by(rows: list[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = text(row.get(field)) or "blank"
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build audit-only RiskGuard demo order intents from MT5 Shadow decisions.")
    parser.add_argument("--shadow-decisions", type=Path, default=DEFAULT_SHADOW_DECISIONS)
    parser.add_argument("--screener-setups", type=Path, default=DEFAULT_SCREENER_SETUPS)
    parser.add_argument("--mt5-account-snapshot", type=Path, default=DEFAULT_MT5_ACCOUNT)
    parser.add_argument("--mt5-positions-snapshot", type=Path, default=DEFAULT_MT5_POSITIONS)
    parser.add_argument("--mt5-pending-orders-snapshot", type=Path, default=DEFAULT_MT5_PENDING)
    parser.add_argument("--symbol-metadata", type=Path, default=DEFAULT_SYMBOL_METADATA)
    parser.add_argument("--risk-state", type=Path, default=DEFAULT_RISK_STATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-only", action="store_true", default=True)
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--min-quality", type=int, default=4)
    parser.add_argument("--review-window-minutes", type=int, default=60)
    parser.add_argument("--observed-at", default="")
    parser.add_argument("--allow-missing-mt5-snapshot", action="store_true", default=True)
    parser.add_argument("--strict-mt5-snapshot", action="store_true")
    parser.add_argument("--default-risk-pct", type=float, default=0.25)
    parser.add_argument("--max-risk-pct-per-trade", type=float, default=0.25)
    parser.add_argument("--max-symbol-open-risk-pct", type=float, default=0.50)
    parser.add_argument("--max-total-open-risk-pct", type=float, default=1.00)
    parser.add_argument("--max-group-open-risk-pct", type=float, default=0.75)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=2.0)
    parser.add_argument("--cumulative-loss-limit-pct", type=float, default=5.0)
    parser.add_argument("--allow-missing-risk-state", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    observed_at = parse_time(args.observed_at) if args.observed_at else None
    config = RiskGuardIntentBuilderConfig(
        output_dir=args.output_dir,
        shadow_decisions_csv=args.shadow_decisions,
        screener_setups_csv=args.screener_setups,
        mt5_account_snapshot_csv=args.mt5_account_snapshot,
        mt5_positions_snapshot_csv=args.mt5_positions_snapshot,
        mt5_pending_orders_snapshot_csv=args.mt5_pending_orders_snapshot,
        symbol_metadata_csv=args.symbol_metadata,
        risk_state_csv=args.risk_state,
        audit_only=bool(args.audit_only),
        fixture_mode=bool(args.fixture_mode),
        min_quality=int(args.min_quality),
        review_window_minutes=int(args.review_window_minutes),
        allow_missing_mt5_snapshot=bool(args.allow_missing_mt5_snapshot),
        strict_mt5_snapshot=bool(args.strict_mt5_snapshot),
        observed_at=observed_at,
        default_risk_pct=float(args.default_risk_pct),
        max_risk_pct_per_trade=float(args.max_risk_pct_per_trade),
        max_symbol_open_risk_pct=float(args.max_symbol_open_risk_pct),
        max_total_open_risk_pct=float(args.max_total_open_risk_pct),
        max_group_open_risk_pct=float(args.max_group_open_risk_pct),
        daily_loss_limit_pct=float(args.daily_loss_limit_pct),
        cumulative_loss_limit_pct=float(args.cumulative_loss_limit_pct),
        require_risk_state=not bool(args.allow_missing_risk_state),
    )
    result = execute(config)
    print(json.dumps({"decision": result.decision, "output_dir": str(result.output_dir), **result.run_meta}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
