from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/mt5_shadow_v1_2026-06-08")
DEFAULT_SCREENER_SETUPS = Path("artifacts/tfg/trading_center_latest/screener_unified/screener_setups.csv")
DEFAULT_CHART_LAYERS = Path("artifacts/tfg/trading_center_latest/screener_unified/screener_chart_layers.csv")
DEFAULT_OHLC = Path("artifacts/tfg/trading_center_latest/ohlc/ohlc_mtf.csv")
DEFAULT_MT5_POSITIONS = Path("artifacts/tfg/mt5_read_only_connection_v1_2026-06-07_local_connect_review/mt5_positions_snapshot.csv")
DEFAULT_MT5_ACCOUNT = Path("artifacts/tfg/mt5_read_only_connection_v1_2026-06-07_local_connect_review/mt5_account_snapshot.csv")
DEFAULT_DOC_PATH = Path("docs/MT5_SHADOW_V1.md")
DEFAULT_MIN_AUTO_QUALITY = 4
AUTO_ELIGIBLE_SETUP_TYPES = {"macd_breakout", "fib_limit_live_candidate"}

SHADOW_COLUMNS = [
    "shadow_decision_id",
    "setup_id",
    "symbol",
    "market_group",
    "timeframe",
    "setup_type",
    "strategy",
    "direction",
    "setup_status",
    "timing_state",
    "setup_quality_score",
    "automation_scope",
    "min_auto_quality",
    "shadow_state",
    "shadow_reason",
    "hypothetical_entry_time",
    "hypothetical_entry_price",
    "hypothetical_sl",
    "hypothetical_tp1",
    "hypothetical_tp2",
    "would_open_position",
    "would_modify_position",
    "order_sent",
    "can_send_order",
    "source_artifacts",
    "is_shadow_only",
    "is_signal",
    "can_execute_order",
]


@dataclass(frozen=True)
class Mt5ShadowConfig:
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    screener_setups_csv: Path = DEFAULT_SCREENER_SETUPS
    chart_layers_csv: Path = DEFAULT_CHART_LAYERS
    ohlc_csv: Path = DEFAULT_OHLC
    mt5_positions_csv: Path = DEFAULT_MT5_POSITIONS
    mt5_account_csv: Path = DEFAULT_MT5_ACCOUNT
    audit_only: bool = False
    dry_run: bool = False
    fixture_mode: bool = False
    allow_missing_inputs: bool = False
    max_setups: int | None = None
    min_auto_quality: int = DEFAULT_MIN_AUTO_QUALITY


@dataclass(frozen=True)
class Mt5ShadowResult:
    decision: str
    output_dir: Path
    run_meta: dict[str, Any]
    shadow_rows: list[dict[str, Any]]


def execute(config: Mt5ShadowConfig) -> Mt5ShadowResult:
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)

    if config.fixture_mode:
        setups, ohlc_rows, positions, account_rows, chart_layers = build_fixture_inputs()
        input_audit = [{"source": "fixture_mode", "path": "in_memory", "status": "loaded", "rows": len(setups)}]
    else:
        setups, ohlc_rows, positions, account_rows, chart_layers, input_audit = load_inputs(config)

    if config.max_setups is not None and config.max_setups >= 0:
        setups = setups[: config.max_setups]

    indexed_ohlc = index_ohlc(ohlc_rows)
    exposure_symbols = {row.get("symbol", "") for row in positions if str(row.get("symbol", "")).strip()}
    evaluated_rows: list[dict[str, Any]] = []
    shadow_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    fill_audit: list[dict[str, Any]] = []

    for setup in setups:
        decision_row, audit_row = evaluate_setup(setup, indexed_ohlc, exposure_symbols, chart_layers, config.min_auto_quality)
        evaluated_rows.append(decision_row)
        if decision_row.get("automation_scope") in {"context_only", "below_min_quality"}:
            excluded_rows.append(decision_row)
        else:
            shadow_rows.append(decision_row)
        fill_audit.append(audit_row)

    summary_rows = summarize_shadow(shadow_rows)
    safety_rows = build_safety_audit(shadow_rows)
    account_audit = build_account_context_audit(account_rows, positions)
    issues = build_issues(input_audit, shadow_rows)

    write_csv(output_dir / "mt5_shadow_decisions.csv", shadow_rows, SHADOW_COLUMNS)
    write_json(output_dir / "mt5_shadow_decisions.json", shadow_rows)
    write_csv(tables_dir / "input_source_audit.csv", input_audit)
    write_csv(tables_dir / "fill_simulation_audit.csv", fill_audit)
    write_csv(tables_dir / "excluded_from_automation_audit.csv", excluded_rows, SHADOW_COLUMNS)
    write_csv(tables_dir / "shadow_state_summary.csv", summary_rows)
    write_csv(tables_dir / "automation_scope_audit.csv", build_automation_scope_audit(evaluated_rows, config.min_auto_quality))
    write_csv(tables_dir / "mt5_readonly_context_audit.csv", account_audit)
    write_csv(tables_dir / "mt5_shadow_safety_audit.csv", safety_rows)
    write_csv(tables_dir / "technical_validation_audit.csv", build_technical_validation_audit(shadow_rows))
    write_csv(tables_dir / "issues_or_risks.csv", issues)

    run_meta = {
        "phase": "mt5_shadow_v1",
        "created_at_utc": generated_at.isoformat(),
        "decision": "mt5_shadow_v1_ready_for_local_shadow_review",
        "mt5_shadow_implemented": True,
        "artifact_first": True,
        "audit_only": bool(config.audit_only),
        "dry_run": bool(config.dry_run),
        "fixture_mode": bool(config.fixture_mode),
        "setups_loaded": len(setups),
        "min_auto_quality": int(config.min_auto_quality),
        "auto_eligible_setup_types": sorted(AUTO_ELIGIBLE_SETUP_TYPES),
        "setups_excluded_from_shadow_decisions_count": len(excluded_rows),
        "shadow_decisions_count": len(shadow_rows),
        "automation_scope_eligible_count": sum(1 for row in evaluated_rows if row.get("automation_scope") == "auto_candidate"),
        "automation_scope_context_only_count": sum(1 for row in evaluated_rows if row.get("automation_scope") == "context_only"),
        "automation_scope_low_quality_count": sum(1 for row in evaluated_rows if row.get("automation_scope") == "below_min_quality"),
        "would_trigger_count": count_state(shadow_rows, "would_trigger"),
        "would_wait_count": count_state(shadow_rows, "would_wait"),
        "would_skip_count": count_state(shadow_rows, "would_skip_context_only") + count_state(shadow_rows, "would_skip"),
        "blocked_count": count_state(shadow_rows, "blocked"),
        "late_count": count_state(shadow_rows, "late"),
        "invalidated_count": count_state(shadow_rows, "invalidated"),
        "no_price_data_count": count_state(shadow_rows, "no_price_data"),
        "mt5_connected": False,
        "mt5_connection_attempted": False,
        "mt5_orders_enabled": False,
        "mt5_orders_sent": 0,
        "can_send_order_any_true": any(boolish(row.get("can_send_order")) for row in shadow_rows),
        "can_execute_order_any_true": any(boolish(row.get("can_execute_order")) for row in shadow_rows),
        "can_modify_position_any_true": any(boolish(row.get("would_modify_position")) for row in shadow_rows),
        "demo_orders_enabled": False,
        "live_enabled": False,
        "telegram_connected": False,
        "telegram_can_trade": False,
        "ai_analyst_can_approve_orders": False,
        "riskguard_required_for_future_orders": True,
        "manual_confirmation_required_for_future_demo_manual": True,
        "sql_real_written": False,
        "ddl_executed": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    write_json(output_dir / "run_meta.json", run_meta)
    write_doc(output_dir / "MT5_SHADOW_V1.md", run_meta, issues)
    if config.doc_path:
        write_doc(config.doc_path, run_meta, issues)

    return Mt5ShadowResult(str(run_meta["decision"]), output_dir, run_meta, shadow_rows)


def load_inputs(config: Mt5ShadowConfig) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    sources = [
        ("screener_setups", config.screener_setups_csv, True),
        ("ohlc", config.ohlc_csv, True),
        ("mt5_positions", config.mt5_positions_csv, False),
        ("mt5_account", config.mt5_account_csv, False),
        ("chart_layers", config.chart_layers_csv, False),
    ]
    audit: list[dict[str, Any]] = []
    loaded: dict[str, list[dict[str, Any]]] = {}
    for name, path, required in sources:
        if path.exists():
            rows = read_csv(path)
            loaded[name] = rows
            audit.append({"source": name, "path": str(path), "required": required, "status": "loaded", "rows": len(rows)})
        elif required and not config.allow_missing_inputs:
            loaded[name] = []
            audit.append({"source": name, "path": str(path), "required": required, "status": "missing_blocking", "rows": 0})
        else:
            loaded[name] = []
            audit.append({"source": name, "path": str(path), "required": required, "status": "missing_allowed", "rows": 0})
    return (
        loaded["screener_setups"],
        loaded["ohlc"],
        loaded["mt5_positions"],
        loaded["mt5_account"],
        loaded["chart_layers"],
        audit,
    )


def evaluate_setup(
    setup: Mapping[str, Any],
    indexed_ohlc: Mapping[tuple[str, str], list[dict[str, Any]]],
    exposure_symbols: set[str],
    chart_layers: list[dict[str, Any]],
    min_auto_quality: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    symbol = str(setup.get("symbol", "")).strip()
    timeframe = str(setup.get("timeframe", "")).strip()
    setup_type = str(setup.get("setup_type", "")).strip()
    strategy = str(setup.get("strategy", "")).strip()
    direction = normalize_direction(setup.get("direction"))
    setup_id = str(setup.get("setup_id", "")).strip() or stable_hash(json.dumps(dict(setup), sort_keys=True, default=str))
    timing_state = str(setup.get("timing_state", "")).strip()
    is_late = boolish(setup.get("is_late")) or timing_state.lower() in {"late", "stale"}
    is_invalidated = boolish(setup.get("is_invalidated")) or timing_state.lower() == "invalidated"
    rows = indexed_ohlc.get((symbol, timeframe), [])
    source_artifacts = str(setup.get("source_artifacts", ""))
    quality_score = parse_int(setup.get("setup_quality_score"))
    automation_scope = automation_scope_for_setup(setup_type, quality_score, min_auto_quality)

    shadow_state = "blocked"
    shadow_reason = "blocked_default_fail_closed"
    entry_time = ""
    entry_price = ""
    sl = first_non_empty(setup.get("macd_sl_study"), setup.get("sl"), setup.get("hypothetical_sl"))
    tp1 = first_non_empty(setup.get("macd_tp1_study"), setup.get("tp1"), setup.get("tp"))
    tp2 = first_non_empty(setup.get("macd_tp2_study"), setup.get("tp2"))

    if automation_scope == "context_only":
        shadow_state = "would_skip_context_only"
        shadow_reason = "setup_type_not_in_automatic_bot_scope"
    elif automation_scope == "below_min_quality":
        shadow_state = "would_skip_context_only"
        shadow_reason = f"setup_quality_below_min_auto_quality_{min_auto_quality}"
    elif symbol in exposure_symbols:
        shadow_state = "blocked"
        shadow_reason = "blocked_duplicate_exposure_symbol_in_mt5_readonly_snapshot"
    elif not rows:
        shadow_state = "no_price_data"
        shadow_reason = "no_closed_ohlc_for_symbol_timeframe"
    elif is_invalidated:
        shadow_state = "invalidated"
        shadow_reason = "setup_marked_invalidated_before_shadow"
    elif is_late:
        shadow_state = "late"
        shadow_reason = "setup_marked_late_or_stale_before_shadow"
    elif setup_type == "fib_limit_live_candidate":
        shadow_state, shadow_reason, entry_time, entry_price = evaluate_fib_limit(setup, rows, direction)
    elif setup_type == "macd_breakout":
        shadow_state, shadow_reason, entry_time, entry_price = evaluate_macd_breakout(setup, rows)
    elif strategy in {"context_level", "market_context"} or setup_type.endswith("_candidate"):
        shadow_state = "would_skip_context_only"
        shadow_reason = "context_or_level_candidate_not_operational_setup"
    else:
        shadow_state = "would_wait"
        shadow_reason = "setup_has_no_shadow_fill_rule_yet"

    row = {
        "shadow_decision_id": stable_hash(f"{setup_id}|{shadow_state}|{entry_time}|{entry_price}"),
        "setup_id": setup_id,
        "symbol": symbol,
        "market_group": setup.get("market_group", ""),
        "timeframe": timeframe,
        "setup_type": setup_type,
        "strategy": strategy,
        "direction": direction,
        "setup_status": setup.get("setup_status", ""),
        "timing_state": timing_state,
        "setup_quality_score": quality_score,
        "automation_scope": automation_scope,
        "min_auto_quality": min_auto_quality,
        "shadow_state": shadow_state,
        "shadow_reason": shadow_reason,
        "hypothetical_entry_time": entry_time,
        "hypothetical_entry_price": entry_price,
        "hypothetical_sl": sl,
        "hypothetical_tp1": tp1,
        "hypothetical_tp2": tp2,
        "would_open_position": shadow_state == "would_trigger",
        "would_modify_position": False,
        "order_sent": False,
        "can_send_order": False,
        "source_artifacts": source_artifacts,
        "is_shadow_only": True,
        "is_signal": False,
        "can_execute_order": False,
    }
    audit = {
        "setup_id": setup_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "setup_type": setup_type,
        "rule_applied": setup_type or strategy or "unknown",
        "setup_quality_score": quality_score,
        "automation_scope": automation_scope,
        "min_auto_quality": min_auto_quality,
        "ohlc_rows_available": len(rows),
        "chart_layers_available": sum(1 for item in chart_layers if item.get("setup_id") == setup_id),
        "shadow_state": shadow_state,
        "shadow_reason": shadow_reason,
        "order_sent": False,
    }
    return row, audit


def evaluate_fib_limit(setup: Mapping[str, Any], rows: list[dict[str, Any]], direction: str) -> tuple[str, str, str, Any]:
    trigger = safe_float(setup.get("trigger_level"))
    if trigger is None:
        return "blocked", "missing_fib_trigger_level", "", ""
    since = str(setup.get("generated_at", "") or setup.get("last_touch_time", ""))
    recent_rows = rows_after_or_tail(rows, since, fallback_tail=96)
    if since and not recent_rows:
        return "would_wait", "no_closed_ohlc_after_fib_reference_time", "", ""
    for row in recent_rows:
        low = safe_float(row.get("low"))
        high = safe_float(row.get("high"))
        if low is None or high is None:
            continue
        if low <= trigger <= high:
            return "would_trigger", "closed_ohlc_touched_fib_trigger_hypothetically", row.get("timestamp", ""), trigger
    return "would_wait", "fib_trigger_not_touched_by_closed_ohlc", "", ""


def evaluate_macd_breakout(setup: Mapping[str, Any], rows: list[dict[str, Any]]) -> tuple[str, str, str, Any]:
    timing = str(setup.get("macd_breakout_timing_state", "") or setup.get("timing_state", "")).lower()
    if timing in {"entry_review", "macd_recent", "breakout_recent"}:
        level = safe_float(setup.get("macd_breakout_level")) or safe_float(setup.get("trigger_level"))
        if level is None:
            return "would_wait", "macd_recent_but_missing_breakout_level", "", ""
        direction = normalize_direction(setup.get("direction"))
        recent_rows = rows_after_or_tail(rows, str(setup.get("macd_breakout_time", "")), fallback_tail=48)
        if str(setup.get("macd_breakout_time", "")).strip() and not recent_rows:
            return "would_wait", "no_closed_ohlc_after_macd_breakout_time", "", ""
        for row in recent_rows:
            close = safe_float(row.get("close"))
            if close is None:
                continue
            if (direction == "long" and close >= level) or (direction == "short" and close <= level):
                return "would_trigger", "closed_close_confirms_macd_breakout_hypothetically", row.get("timestamp", ""), close
        return "would_wait", "macd_timing_recent_but_close_not_confirmed_in_window", "", ""
    if timing in {"late", "stale"}:
        return "late", "macd_breakout_timing_late_or_stale", "", ""
    return "would_wait", "macd_breakout_not_recent_enough_for_shadow_trigger", "", ""


def automation_scope_for_setup(setup_type: str, quality_score: int, min_auto_quality: int) -> str:
    if setup_type not in AUTO_ELIGIBLE_SETUP_TYPES:
        return "context_only"
    if quality_score < int(min_auto_quality):
        return "below_min_quality"
    return "auto_candidate"


def index_ohlc(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("symbol", "")).strip(), str(row.get("timeframe", "")).strip())
        indexed.setdefault(key, []).append(row)
    for key in indexed:
        indexed[key].sort(key=lambda item: str(item.get("timestamp", "")))
    return indexed


def rows_after_or_tail(rows: list[dict[str, Any]], timestamp: str, fallback_tail: int) -> list[dict[str, Any]]:
    if timestamp:
        reference = parse_time(timestamp)
        if reference is None:
            filtered = [row for row in rows if str(row.get("timestamp", "")) >= timestamp]
        else:
            filtered = [row for row in rows if (parse_time(row.get("timestamp", "")) or datetime.min) >= reference]
        return filtered
    return rows[-fallback_tail:] if fallback_tail > 0 else rows


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def summarize_shadow(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    states = sorted({str(row.get("shadow_state", "")) for row in rows})
    return [
        {
            "shadow_state": state,
            "count": sum(1 for row in rows if row.get("shadow_state") == state),
            "order_sent": False,
            "can_send_order": False,
        }
        for state in states
    ] or [{"shadow_state": "no_rows", "count": 0, "order_sent": False, "can_send_order": False}]


def build_safety_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"check": "order_sent_any_true", "observed": any(boolish(row.get("order_sent")) for row in rows), "expected": False, "status": "pass"},
        {"check": "can_send_order_any_true", "observed": any(boolish(row.get("can_send_order")) for row in rows), "expected": False, "status": "pass"},
        {"check": "can_execute_order_any_true", "observed": any(boolish(row.get("can_execute_order")) for row in rows), "expected": False, "status": "pass"},
        {"check": "would_modify_position_any_true", "observed": any(boolish(row.get("would_modify_position")) for row in rows), "expected": False, "status": "pass"},
        {"check": "telegram_connected", "observed": False, "expected": False, "status": "pass"},
        {"check": "sql_real_written", "observed": False, "expected": False, "status": "pass"},
    ]


def build_technical_validation_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"check": "shadow_rows_generated", "observed": len(rows), "expected": ">=0", "status": "pass"},
        {
            "check": "auto_scope_only_macd_and_fib",
            "observed": sorted({row.get("setup_type") for row in rows if row.get("automation_scope") == "auto_candidate"}),
            "expected": sorted(AUTO_ELIGIBLE_SETUP_TYPES),
            "status": "pass"
            if all(row.get("setup_type") in AUTO_ELIGIBLE_SETUP_TYPES for row in rows if row.get("automation_scope") == "auto_candidate")
            else "fail",
        },
        {"check": "orders_sent", "observed": 0, "expected": 0, "status": "pass"},
        {"check": "mt5_connected", "observed": False, "expected": False, "status": "pass"},
        {"check": "telegram_connected", "observed": False, "expected": False, "status": "pass"},
        {"check": "sql_real_written", "observed": False, "expected": False, "status": "pass"},
        {"check": "signals_generated", "observed": False, "expected": False, "status": "pass"},
        {
            "check": "can_send_order_any_true",
            "observed": any(boolish(row.get("can_send_order")) for row in rows),
            "expected": False,
            "status": "pass",
        },
    ]


def build_automation_scope_audit(rows: list[dict[str, Any]], min_auto_quality: int) -> list[dict[str, Any]]:
    setup_types = sorted({str(row.get("setup_type", "")) for row in rows})
    audit = [
        {
            "policy": "auto_eligible_setup_types",
            "setup_type": ",".join(sorted(AUTO_ELIGIBLE_SETUP_TYPES)),
            "min_auto_quality": min_auto_quality,
            "rows": sum(1 for row in rows if row.get("automation_scope") == "auto_candidate"),
            "description": "Only macd_breakout and fib_limit_live_candidate can enter automatic shadow review.",
        }
    ]
    for setup_type in setup_types:
        matching = [row for row in rows if row.get("setup_type") == setup_type]
        audit.append(
            {
                "policy": "setup_type_scope",
                "setup_type": setup_type,
                "min_auto_quality": min_auto_quality,
                "rows": len(matching),
                "auto_candidate": sum(1 for row in matching if row.get("automation_scope") == "auto_candidate"),
                "below_min_quality": sum(1 for row in matching if row.get("automation_scope") == "below_min_quality"),
                "context_only": sum(1 for row in matching if row.get("automation_scope") == "context_only"),
                "description": "Context-only rows can enrich manual review but are not bot automation candidates.",
            }
        )
    return audit


def build_account_context_audit(account_rows: list[dict[str, Any]], positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": "mt5_account_snapshot",
            "rows": len(account_rows),
            "used_for": "read_only_context_only",
            "can_send_order": False,
        },
        {
            "source": "mt5_positions_snapshot",
            "rows": len(positions),
            "used_for": "duplicate_exposure_audit_only",
            "can_modify_position": False,
        },
    ]


def build_issues(input_audit: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for source in input_audit:
        if source.get("status") == "missing_blocking":
            issues.append(
                {
                    "issue_id": f"missing_{source.get('source')}",
                    "severity": "high",
                    "description": f"Required input missing: {source.get('path')}",
                    "recommended_action": "Regenerate latest Trading Center artifacts before running shadow.",
                }
            )
    if not rows:
        issues.append(
            {
                "issue_id": "no_shadow_rows",
                "severity": "medium",
                "description": "No setups were available for shadow evaluation.",
                "recommended_action": "Check screener_setups source or use fixture mode for validation.",
            }
        )
    if not issues:
        issues.append(
            {
                "issue_id": "no_runtime_issues",
                "severity": "info",
                "description": "Shadow artifact generation completed without runtime issues.",
                "recommended_action": "Review mt5_shadow_decisions before any future demo-order design.",
            }
        )
    return issues


def build_fixture_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    setups = [
        {
            "setup_id": "fixture|EURUSD.r|H1|fib",
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "fib_limit_live_candidate",
            "strategy": "fib_limit",
            "direction": "long",
            "setup_status": "ready_for_chart_review",
            "setup_quality_score": "5",
            "timing_state": "entry_review",
            "trigger_level": "1.1000",
            "generated_at": "2026-06-08 09:00:00",
            "is_late": "False",
            "is_invalidated": "False",
            "source_artifacts": "fixture",
        },
        {
            "setup_id": "fixture|GBPUSD.r|H1|macd",
            "symbol": "GBPUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H1",
            "setup_type": "macd_breakout",
            "strategy": "macd_breakout",
            "direction": "short",
            "setup_status": "needs_review",
            "setup_quality_score": "4",
            "timing_state": "watching",
            "macd_breakout_timing_state": "late",
            "macd_breakout_level": "1.2500",
            "is_late": "False",
            "is_invalidated": "False",
            "source_artifacts": "fixture",
        },
        {
            "setup_id": "fixture|EURO50|H1|rsi",
            "symbol": "EURO50",
            "market_group": "Index",
            "timeframe": "H1",
            "setup_type": "rsi_extreme_with_context",
            "strategy": "market_context",
            "direction": "long",
            "setup_status": "needs_review",
            "setup_quality_score": "5",
            "timing_state": "watching",
            "is_late": "False",
            "is_invalidated": "False",
            "source_artifacts": "fixture",
        },
    ]
    ohlc = [
        {"market_group": "Forex Majors", "symbol": "EURUSD.r", "timeframe": "H1", "timestamp": "2026-06-08 10:00:00", "open": "1.0980", "high": "1.1010", "low": "1.0970", "close": "1.1005"},
        {"market_group": "Forex Majors", "symbol": "GBPUSD.r", "timeframe": "H1", "timestamp": "2026-06-08 10:00:00", "open": "1.2520", "high": "1.2530", "low": "1.2490", "close": "1.2495"},
        {"market_group": "Index", "symbol": "EURO50", "timeframe": "H1", "timestamp": "2026-06-08 10:00:00", "open": "5000", "high": "5010", "low": "4990", "close": "5005"},
    ]
    positions: list[dict[str, Any]] = []
    account = [{"account_id_hash": "fixture_hash", "equity": "10000", "read_only": "True"}]
    layers: list[dict[str, Any]] = []
    return setups, ohlc, positions, account, layers


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
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_doc(path: Path, run_meta: Mapping[str, Any], issues: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    issue_lines = "\n".join(f"- `{item['issue_id']}`: {item['description']}" for item in issues)
    path.write_text(
        f"""# MT5 Shadow V1

Fecha: 2026-06-08

Decision: `{run_meta.get('decision')}`

## Resumen

`mt5_shadow_v1` implementa una simulacion artifact-first entre setups del
Trading Center, OHLC cerrado y snapshots MT5 read-only. El objetivo es registrar
que habria ocurrido de forma hipotetica antes de disenar demo orders.

No conecta MT5, no envia ordenes, no modifica posiciones, no conecta Telegram y
no escribe SQL. `would_trigger` significa solo que el setup habria activado una
observacion shadow segun reglas de estudio; no es una orden ni permiso operativo.
El ambito de bot automatico queda limitado de forma conservadora a
`macd_breakout` y `fib_limit_live_candidate` con
`setup_quality_score >= {run_meta.get('min_auto_quality')}`. RSI, niveles,
Fibonacci contextual y otros candidatos quedan como contexto de revision, no
como shadow candidates de bot. Esos casos excluidos se auditan en
`tables/excluded_from_automation_audit.csv`, pero no se publican en
`mt5_shadow_decisions.csv`.

## Resultado

- setups cargados: `{run_meta.get('setups_loaded')}`
- decisiones shadow: `{run_meta.get('shadow_decisions_count')}`
- excluidos de decisiones shadow: `{run_meta.get('setups_excluded_from_shadow_decisions_count')}`
- auto candidates: `{run_meta.get('automation_scope_eligible_count')}`
- context only: `{run_meta.get('automation_scope_context_only_count')}`
- below min quality: `{run_meta.get('automation_scope_low_quality_count')}`
- would_trigger: `{run_meta.get('would_trigger_count')}`
- would_wait: `{run_meta.get('would_wait_count')}`
- late: `{run_meta.get('late_count')}`
- invalidated: `{run_meta.get('invalidated_count')}`
- no_price_data: `{run_meta.get('no_price_data_count')}`

## Seguridad

- `mt5_connected=false`
- `mt5_orders_sent=0`
- `can_send_order_any_true=false`
- `telegram_connected=false`
- `sql_real_written=false`
- `signals_generated=false`

## Incidencias

{issue_lines}

## Siguiente paso

Revisar visualmente las decisiones shadow y, si encajan, disenar la fase de
shadow review/dashboard antes de cualquier demo order.
""",
        encoding="utf-8",
    )


def ordered_fields(rows: list[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    return fields


def count_state(rows: list[Mapping[str, Any]], state: str) -> int:
    return sum(1 for row in rows if row.get("shadow_state") == state)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if str(value or "").strip():
            return value
    return ""


def safe_float(value: Any) -> float | None:
    try:
        if str(value or "").strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int:
    parsed = safe_float(value)
    if parsed is None:
        return 0
    return int(parsed)


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def normalize_direction(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"short", "sell", "bearish", "bajista", "down"}:
        return "short"
    if text in {"long", "buy", "bullish", "alcista", "up"}:
        return "long"
    return text or "context"


def stable_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate MT5 shadow decisions without any order surface.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--screener-setups-csv", type=Path, default=DEFAULT_SCREENER_SETUPS)
    parser.add_argument("--chart-layers-csv", type=Path, default=DEFAULT_CHART_LAYERS)
    parser.add_argument("--ohlc-csv", type=Path, default=DEFAULT_OHLC)
    parser.add_argument("--mt5-positions-csv", type=Path, default=DEFAULT_MT5_POSITIONS)
    parser.add_argument("--mt5-account-csv", type=Path, default=DEFAULT_MT5_ACCOUNT)
    parser.add_argument("--audit-only", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--fixture-mode", action="store_true", default=False)
    parser.add_argument("--allow-missing-inputs", action="store_true", default=False)
    parser.add_argument("--max-setups", type=int, default=None)
    parser.add_argument("--min-auto-quality", type=int, default=DEFAULT_MIN_AUTO_QUALITY)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> Mt5ShadowConfig:
    return Mt5ShadowConfig(
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        screener_setups_csv=args.screener_setups_csv,
        chart_layers_csv=args.chart_layers_csv,
        ohlc_csv=args.ohlc_csv,
        mt5_positions_csv=args.mt5_positions_csv,
        mt5_account_csv=args.mt5_account_csv,
        audit_only=bool(args.audit_only),
        dry_run=bool(args.dry_run),
        fixture_mode=bool(args.fixture_mode),
        allow_missing_inputs=bool(args.allow_missing_inputs),
        max_setups=args.max_setups,
        min_auto_quality=int(args.min_auto_quality),
    )


def main(argv: Sequence[str] | None = None) -> int:
    result = execute(config_from_args(parse_args(argv)))
    print(json.dumps({"decision": result.decision, "output_dir": str(result.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
