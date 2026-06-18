from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table
from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import DEFAULT_SOURCE_CSV, load_source_ohlc
from trading_center.wavecount_current_hypothesis import (
    NEXT_PHASE,
    distance_to_invalidation,
    float_or_blank,
    safe_id,
    timestamp_text,
    to_bool,
    validate_payload,
)


DEFAULT_CYCLE_DIR = Path("artifacts/tfg/wavecount_cycle_state_v0_2026-05-27")
DEFAULT_PERSISTENT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_AUDIT_DIR = Path("artifacts/tfg/wavecount_cycle_state_visual_audit_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_state_machine_v0_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_STATE_MACHINE_V0.md")

STATE_MACHINE_COLUMNS = [
    "state_machine_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "as_of_bar_time",
    "cycle_id",
    "cycle_status",
    "cycle_family",
    "state_machine_state",
    "estimated_current_wave",
    "confirmed_wave_context",
    "next_wave_hypothesis",
    "transition_path",
    "transition_blockers",
    "cycle_start_valid",
    "latest_close_confirms_active",
    "latest_close_time",
    "latest_close",
    "activation_level",
    "invalidation_level",
    "distance_to_invalidation_pct",
    "context_freshness_status",
    "freshness_status",
    "wave_stability_status",
    "display_policy",
    "manual_review_reason",
    "lookahead_safe",
    "is_read_only",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
    "source",
    "data_origin",
    "method_version",
    "notes",
    "payload_json",
]


@dataclass(frozen=True)
class StateMachineConfig:
    cycle_dir: Path = DEFAULT_CYCLE_DIR
    persistent_dir: Path = DEFAULT_PERSISTENT_DIR
    audit_dir: Path = DEFAULT_AUDIT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_csv: Path = DEFAULT_SOURCE_CSV
    fresh_lag_bars: int = 24
    acceptable_lag_bars: int = 60
    generate_charts: bool = True


@dataclass(frozen=True)
class StateMachineResult:
    hypotheses: pd.DataFrame
    transitions: pd.DataFrame
    guard_audit: pd.DataFrame
    freshness_audit: pd.DataFrame
    comparison: pd.DataFrame
    dashboard_contract: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_state_machine(config: StateMachineConfig | None = None) -> StateMachineResult:
    config = config or StateMachineConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    guard_rows: list[dict[str, Any]] = []
    freshness_rows: list[dict[str, Any]] = []

    for _, cycle_row in sources["cycle"].iterrows():
        pivots = cycle_pivots(
            sources["pivots"],
            str(cycle_row["symbol"]),
            str(cycle_row["timeframe"]),
            str(cycle_row["cycle_start_pivot_uid"]),
            str(cycle_row["cycle_end_pivot_uid"]),
        )
        latest_close = latest_close_row(sources["ohlc"], cycle_row)
        row, transitions, guard, freshness = classify_state_machine(
            config=config,
            generated_at=generated_at,
            cycle_row=cycle_row,
            pivots=pivots,
            latest_close=latest_close,
        )
        rows.append(row)
        transition_rows.extend(transitions)
        guard_rows.append(guard)
        freshness_rows.append(freshness)

    hypotheses = normalize_hypotheses(pd.DataFrame(rows))
    transitions = pd.DataFrame(transition_rows)
    guard_audit = pd.DataFrame(guard_rows)
    freshness = pd.DataFrame(freshness_rows)
    comparison = build_comparison(sources["cycle"], hypotheses)
    dashboard_contract = dashboard_display_contract_frame()
    issues = build_issues_or_risks(hypotheses, guard_audit, freshness)
    decision = decide_next_step(hypotheses, guard_audit, freshness)
    run_meta = build_run_meta(generated_at, config, hypotheses, guard_audit, freshness, decision)
    written = write_outputs(
        config=config,
        hypotheses=hypotheses,
        transitions=transitions,
        guard_audit=guard_audit,
        freshness=freshness,
        comparison=comparison,
        dashboard_contract=dashboard_contract,
        issues=issues,
        run_meta=run_meta,
    )
    if config.generate_charts:
        write_charts(config, hypotheses, sources["pivots"], sources["ohlc"])
    write_docs(config, hypotheses, transitions, guard_audit, freshness, comparison, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_STATE_MACHINE_V0.md"
    return StateMachineResult(
        hypotheses=hypotheses,
        transitions=transitions,
        guard_audit=guard_audit,
        freshness_audit=freshness,
        comparison=comparison,
        dashboard_contract=dashboard_contract,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: StateMachineConfig) -> dict[str, Any]:
    required = {
        "cycle": config.cycle_dir / "cycle_state_hypothesis.csv",
        "pivots": config.persistent_dir / "persistent_pivots.csv",
        "anti": config.cycle_dir / "anti_lookahead_audit.csv",
        "run_meta": config.cycle_dir / "run_meta.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing state machine inputs: {missing}")
    return {
        "cycle": pd.read_csv(required["cycle"]),
        "pivots": pd.read_csv(required["pivots"]),
        "anti": pd.read_csv(required["anti"]),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
        "ohlc": load_source_ohlc(config.source_csv) if config.source_csv.exists() else pd.DataFrame(),
    }


def classify_state_machine(
    *,
    config: StateMachineConfig,
    generated_at: str,
    cycle_row: pd.Series,
    pivots: pd.DataFrame,
    latest_close: pd.Series | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    symbol = str(cycle_row["symbol"])
    timeframe = str(cycle_row["timeframe"])
    as_of = pd.Timestamp(cycle_row["as_of_bar_time"])
    pivot_types = pivots["pivot_type"].astype(str).tolist() if not pivots.empty else []
    direction = infer_direction(pivots)
    start_valid = valid_cycle_start(pivots, direction)
    alternates = structure_alternates(pivots)
    activation = activation_level(pivots, direction)
    invalidation = invalidation_level(pivots, direction)
    close_time = pd.Timestamp(latest_close["time"]) if latest_close is not None else pd.NaT
    close_price = float(latest_close["close"]) if latest_close is not None else None
    latest_close_safe = latest_close is not None and close_time <= as_of
    lag_bars = lag_h4_bars(cycle_row, as_of)
    context_freshness = context_freshness_status(lag_bars, config)
    close_confirms = confirms_active(close_price, activation, direction)
    invalidated = invalidates(close_price, invalidation, direction)
    blockers = transition_blockers(
        pivots=pivots,
        start_valid=start_valid,
        alternates=alternates,
        latest_close_safe=latest_close_safe,
        invalidated=invalidated,
        context_freshness=context_freshness,
    )
    estimated, state, display, stability, manual_reason = estimate_state(
        pivot_count=len(pivots),
        start_valid=start_valid,
        alternates=alternates,
        close_confirms=close_confirms,
        invalidated=invalidated,
        context_freshness=context_freshness,
        blockers=blockers,
    )
    confirmed = confirmed_context(estimated, context_freshness, blockers)
    transitions = state_transitions(symbol, timeframe, as_of, pivots, estimated, blockers, close_confirms)
    lookahead_safe = bool((pivots["pivot_detected_at"] <= as_of).all()) if not pivots.empty else True
    lookahead_safe = bool(lookahead_safe and latest_close_safe)
    row = {
        "state_machine_id": f"wave_state_machine_v0_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}",
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": cycle_row.get("market_group", ""),
        "timeframe": timeframe,
        "higher_timeframe": cycle_row.get("higher_timeframe", ""),
        "as_of_bar_time": as_of.isoformat(),
        "cycle_id": cycle_row["cycle_id"],
        "cycle_status": cycle_row["cycle_status"],
        "cycle_family": cycle_row["cycle_family"],
        "state_machine_state": state,
        "estimated_current_wave": estimated,
        "confirmed_wave_context": confirmed,
        "next_wave_hypothesis": NEXT_PHASE.get(estimated, "not_available"),
        "transition_path": "->".join([transition["to_state"] for transition in transitions]) if transitions else "",
        "transition_blockers": ";".join(blockers) if blockers else "none",
        "cycle_start_valid": start_valid,
        "latest_close_confirms_active": close_confirms,
        "latest_close_time": timestamp_text(close_time) if latest_close is not None else "",
        "latest_close": float_or_blank(close_price),
        "activation_level": float_or_blank(activation),
        "invalidation_level": float_or_blank(invalidation),
        "distance_to_invalidation_pct": distance_to_invalidation(float(close_price), invalidation) if close_price is not None else "",
        "context_freshness_status": context_freshness,
        "freshness_status": "confirmed_late" if context_freshness == "late" else "fresh_estimate",
        "wave_stability_status": stability,
        "display_policy": display,
        "manual_review_reason": manual_reason,
        "lookahead_safe": lookahead_safe,
        "is_read_only": True,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "source": "wavecount_state_machine_v0",
        "data_origin": "cycle_state_and_local_ohlc_artifacts",
        "method_version": "wavecount_state_machine_v0",
        "notes": "state-machine context only; no_signal_no_filter_no_execution",
        "payload_json": json.dumps(
            {
                "pivot_types": pivot_types,
                "tail_pivot_prices": pivots["pivot_price"].astype(float).round(6).tolist() if not pivots.empty else [],
                "direction": direction,
                "lag_h4_bars_since_last_cycle_pivot": lag_bars,
                "blockers": blockers,
                "operational_use": "forbidden",
            },
            sort_keys=True,
            default=str,
        ),
    }
    guard = {
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "cycle_start_valid": start_valid,
        "structure_alternates": alternates,
        "latest_close_safe": latest_close_safe,
        "latest_close_confirms_active": close_confirms,
        "invalidated": invalidated,
        "transition_blockers": row["transition_blockers"],
        "lookahead_safe": lookahead_safe,
    }
    freshness = {
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "cycle_last_pivot_time": cycle_row["cycle_last_pivot_time"],
        "latest_close_time": row["latest_close_time"],
        "lag_h4_bars_since_last_cycle_pivot": lag_bars,
        "context_freshness_status": context_freshness,
        "display_policy": display,
        "interpretation": freshness_interpretation(context_freshness, display),
    }
    return row, transitions, guard, freshness


def cycle_pivots(pivots: pd.DataFrame, symbol: str, timeframe: str, start_uid: str, end_uid: str) -> pd.DataFrame:
    part = pivots[
        (pivots["symbol"].astype(str) == symbol)
        & (pivots["timeframe"].astype(str) == timeframe)
        & (pivots["pivot_role"].astype(str) == "persistent_pivot")
    ].copy()
    if part.empty:
        return part
    part["pivot_extreme_time"] = pd.to_datetime(part["pivot_extreme_time"], errors="coerce")
    part["pivot_detected_at"] = pd.to_datetime(part["pivot_detected_at"], errors="coerce")
    part["pivot_price"] = pd.to_numeric(part["pivot_price"], errors="coerce")
    part = part.dropna(subset=["pivot_extreme_time", "pivot_detected_at", "pivot_price"]).sort_values(["pivot_extreme_time", "pivot_detected_at"])
    start_matches = part.index[part["pivot_uid"].astype(str) == str(start_uid)]
    end_matches = part.index[part["pivot_uid"].astype(str) == str(end_uid)]
    if len(start_matches) and len(end_matches):
        start_pos = part.index.get_loc(start_matches[0])
        end_pos = part.index.get_loc(end_matches[0])
        part = part.iloc[min(start_pos, end_pos) : max(start_pos, end_pos) + 1]
    return part.reset_index(drop=True)


def latest_close_row(ohlc: pd.DataFrame, cycle_row: pd.Series) -> pd.Series | None:
    if ohlc.empty:
        return None
    symbol = str(cycle_row["symbol"])
    timeframe = str(cycle_row["timeframe"])
    as_of = pd.Timestamp(cycle_row["as_of_bar_time"])
    part = ohlc[(ohlc["symbol"].astype(str) == symbol) & (ohlc["timeframe"].astype(str) == timeframe)].copy()
    if part.empty:
        return None
    part["time"] = pd.to_datetime(part["time"], errors="coerce")
    part = part[part["time"] <= as_of].sort_values("time")
    if part.empty:
        return None
    return part.iloc[-1]


def infer_direction(pivots: pd.DataFrame) -> str:
    if len(pivots) < 2:
        return "unknown"
    first_price = float(pivots.iloc[0]["pivot_price"])
    last_price = float(pivots.iloc[-1]["pivot_price"])
    return "long" if last_price >= first_price else "short"


def valid_cycle_start(pivots: pd.DataFrame, direction: str) -> bool:
    if pivots.empty or direction == "unknown":
        return False
    first_type = str(pivots.iloc[0]["pivot_type"])
    return bool((direction == "long" and first_type == "low") or (direction == "short" and first_type == "high"))


def structure_alternates(pivots: pd.DataFrame) -> bool:
    if len(pivots) < 2:
        return True
    values = pivots["pivot_type"].astype(str).tolist()
    return all(left != right for left, right in zip(values, values[1:]))


def activation_level(pivots: pd.DataFrame, direction: str) -> float | None:
    if len(pivots) < 2 or direction == "unknown":
        return None
    return float(pivots.iloc[1]["pivot_price"])


def invalidation_level(pivots: pd.DataFrame, direction: str) -> float | None:
    if pivots.empty or direction == "unknown":
        return None
    return float(pivots.iloc[0]["pivot_price"])


def confirms_active(close_price: float | None, activation: float | None, direction: str) -> bool:
    if close_price is None or activation is None:
        return False
    if direction == "long":
        return close_price > activation
    if direction == "short":
        return close_price < activation
    return False


def invalidates(close_price: float | None, invalidation: float | None, direction: str) -> bool:
    if close_price is None or invalidation is None:
        return False
    if direction == "long":
        return close_price < invalidation
    if direction == "short":
        return close_price > invalidation
    return False


def lag_h4_bars(cycle_row: pd.Series, as_of: pd.Timestamp) -> float:
    last = pd.Timestamp(cycle_row["cycle_last_pivot_time"])
    return round((as_of - last).total_seconds() / 3600.0 / 4.0, 1)


def context_freshness_status(lag_bars: float, config: StateMachineConfig) -> str:
    if lag_bars <= config.fresh_lag_bars:
        return "fresh"
    if lag_bars <= config.acceptable_lag_bars:
        return "acceptable_lag"
    return "late"


def transition_blockers(
    *,
    pivots: pd.DataFrame,
    start_valid: bool,
    alternates: bool,
    latest_close_safe: bool,
    invalidated: bool,
    context_freshness: str,
) -> list[str]:
    blockers = []
    if len(pivots) < 2:
        blockers.append("insufficient_cycle_pivots")
    if not start_valid:
        blockers.append("invalid_cycle_start")
    if not alternates:
        blockers.append("pivot_alternation_failed")
    if not latest_close_safe:
        blockers.append("latest_close_missing_or_after_as_of")
    if invalidated:
        blockers.append("invalidation_level_breached")
    if context_freshness == "late":
        blockers.append("late_cycle_context")
    return blockers


def estimate_state(
    *,
    pivot_count: int,
    start_valid: bool,
    alternates: bool,
    close_confirms: bool,
    invalidated: bool,
    context_freshness: str,
    blockers: list[str],
) -> tuple[str, str, str, str, str]:
    if invalidated:
        return "invalidated", "cycle_invalidated", "manual_review_only", "invalidated", "invalidation_level_breached"
    hard_blockers = [blocker for blocker in blockers if blocker not in {"late_cycle_context"}]
    if hard_blockers:
        return "ambiguous", "cycle_ambiguous", "manual_review_only", "manual_review_required", ";".join(hard_blockers)
    if pivot_count == 2:
        estimated = "possible_wave2"
        state = "cycle_possible_wave2"
    elif pivot_count >= 3:
        estimated = "possible_wave3_active" if close_confirms else "possible_wave3_candidate"
        state = "cycle_possible_wave3_active" if close_confirms else "cycle_possible_wave3_candidate"
    else:
        estimated = "possible_wave1"
        state = "cycle_forming_wave1"
    if context_freshness == "late":
        return estimated, state, "show_with_warning", "confirmed_late", "late_cycle_context"
    return estimated, state, "displayable_in_dashboard", "provisional_estimate", "not_applicable"


def confirmed_context(estimated: str, freshness: str, blockers: list[str]) -> str:
    if estimated in {"ambiguous", "invalidated", "unknown"}:
        return estimated
    if blockers and blockers != ["late_cycle_context"]:
        return "ambiguous"
    if freshness == "late":
        return f"{estimated}_late"
    return estimated


def state_transitions(
    symbol: str,
    timeframe: str,
    as_of: pd.Timestamp,
    pivots: pd.DataFrame,
    estimated: str,
    blockers: list[str],
    close_confirms: bool,
) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    state = "cycle_start"
    for index, (_, pivot) in enumerate(pivots.iterrows(), start=1):
        if blockers and index == len(pivots):
            next_state = "cycle_manual_review_required" if estimated == "ambiguous" else state_from_estimated(estimated)
            event = "transition_guarded"
            reason = ";".join(blockers)
        else:
            next_state = state_from_count(index, close_confirms if index == len(pivots) else False)
            event = "pivot_transition"
            reason = "persistent_pivot_acceptance"
        transitions.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "as_of_bar_time": as_of.isoformat(),
                "from_state": state,
                "to_state": next_state,
                "event": event,
                "reason": reason,
                "pivot_uid": pivot.get("pivot_uid", ""),
                "pivot_detected_at": timestamp_text(pd.Timestamp(pivot.get("pivot_detected_at"))),
                "lookahead_safe": bool(pd.Timestamp(pivot.get("pivot_detected_at")) <= as_of),
            }
        )
        state = next_state
    if not pivots.empty and close_confirms and estimated == "possible_wave3_active":
        transitions.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "as_of_bar_time": as_of.isoformat(),
                "from_state": state,
                "to_state": "cycle_possible_wave3_active",
                "event": "latest_close_activation",
                "reason": "latest_close_beyond_activation_level",
                "pivot_uid": "",
                "pivot_detected_at": "",
                "lookahead_safe": True,
            }
        )
    return transitions


def state_from_count(count: int, close_confirms: bool) -> str:
    if count <= 1:
        return "cycle_forming_wave1"
    if count == 2:
        return "cycle_possible_wave2"
    if count == 3:
        return "cycle_possible_wave3_active" if close_confirms else "cycle_possible_wave3_candidate"
    return "cycle_manual_review_required"


def state_from_estimated(estimated: str) -> str:
    mapping = {
        "possible_wave1": "cycle_forming_wave1",
        "possible_wave2": "cycle_possible_wave2",
        "possible_wave3_candidate": "cycle_possible_wave3_candidate",
        "possible_wave3_active": "cycle_possible_wave3_active",
        "invalidated": "cycle_invalidated",
        "ambiguous": "cycle_ambiguous",
    }
    return mapping.get(estimated, "cycle_ambiguous")


def freshness_interpretation(status: str, display: str) -> str:
    if status == "late":
        return "State can be shown only with warning; it is not fresh current wave context."
    if display == "displayable_in_dashboard":
        return "Fresh enough for a future dashboard-safe contextual view, not for trading decisions."
    return "Requires manual review."


def normalize_hypotheses(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in STATE_MACHINE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=STATE_MACHINE_COLUMNS)
    for column in ["cycle_start_valid", "latest_close_confirms_active", "lookahead_safe", "is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
        normalized[column] = normalized[column].map(to_bool)
    normalized["is_read_only"] = True
    normalized["can_generate_signal"] = False
    normalized["can_filter_trade"] = False
    normalized["can_execute_order"] = False
    normalized["payload_json"] = normalized["payload_json"].map(validate_payload)
    validate_hard_flags(normalized)
    return normalized


def validate_hard_flags(frame: pd.DataFrame) -> None:
    if not frame["is_read_only"].map(to_bool).all():
        raise ValueError("is_read_only=false is forbidden")
    for column in ["can_generate_signal", "can_filter_trade", "can_execute_order"]:
        if frame[column].map(to_bool).any():
            raise ValueError(f"{column}=true is forbidden")
    if not frame["lookahead_safe"].map(to_bool).all():
        raise ValueError("lookahead_safe=false blocks state machine output")


def build_comparison(cycle: pd.DataFrame, machine: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in machine.iterrows():
        match = cycle[
            (cycle["symbol"].astype(str) == str(row["symbol"]))
            & (cycle["timeframe"].astype(str) == str(row["timeframe"]))
        ]
        old = match.iloc[0] if not match.empty else {}
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "cycle_state_estimated_current_wave": old.get("estimated_current_wave", "not_available"),
                "state_machine_estimated_current_wave": row["estimated_current_wave"],
                "cycle_state_display_policy": old.get("display_policy", "not_available"),
                "state_machine_display_policy": row["display_policy"],
                "cycle_state_status": old.get("cycle_status", "not_available"),
                "state_machine_state": row["state_machine_state"],
                "transition_blockers": row["transition_blockers"],
                "improved_precision": bool(row["display_policy"] != "displayable_in_dashboard"),
                "comparison_note": comparison_note(old.get("estimated_current_wave", ""), row["estimated_current_wave"], row["transition_blockers"]),
            }
        )
    return pd.DataFrame(rows)


def comparison_note(old_wave: str, new_wave: str, blockers: str) -> str:
    if new_wave == "invalidated":
        return "state_machine_invalidates_cycle_context"
    if new_wave == "ambiguous":
        return "state_machine_blocks_false_precision"
    if "late_cycle_context" in str(blockers):
        return "state_machine_keeps_wave_but_marks_late"
    if old_wave != new_wave:
        return "state_machine_relabels_context"
    return "state_machine_keeps_context"


def dashboard_display_contract_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"display_policy": "displayable_in_dashboard", "meaning": "Fresh read-only context only; no trading use.", "bot_allowed": False},
            {"display_policy": "show_with_warning", "meaning": "Context is late/provisional and must show warning.", "bot_allowed": False},
            {"display_policy": "manual_review_only", "meaning": "Blocked by state-machine guardrails.", "bot_allowed": False},
            {"display_policy": "not_displayable", "meaning": "No useful wave context.", "bot_allowed": False},
        ]
    )


def build_issues_or_risks(machine: pd.DataFrame, guard: pd.DataFrame, freshness: pd.DataFrame) -> pd.DataFrame:
    manual = int(machine["display_policy"].astype(str).eq("manual_review_only").sum())
    warnings = int(machine["display_policy"].astype(str).eq("show_with_warning").sum())
    active = int(machine["estimated_current_wave"].astype(str).str.contains("wave3_active", regex=False).sum())
    late = int(freshness["context_freshness_status"].astype(str).eq("late").sum())
    invalid_start = int((~guard["cycle_start_valid"].map(to_bool)).sum())
    return pd.DataFrame(
        [
            {
                "severity": "info",
                "risk": "lookahead_guard",
                "description": "All emitted rows are lookahead-safe.",
                "recommendation": "Keep as hard guardrail.",
            },
            {
                "severity": "medium" if manual else "low",
                "risk": "manual_review_only",
                "description": f"{manual} rows are blocked for manual review.",
                "recommendation": "Review cycle start rules if dominant.",
            },
            {
                "severity": "medium" if warnings else "low",
                "risk": "late_or_provisional_display",
                "description": f"{warnings} rows require dashboard warnings.",
                "recommendation": "Never show as fresh current wave.",
            },
            {
                "severity": "medium" if active else "low",
                "risk": "wave3_active_context",
                "description": f"{active} rows remain possible_wave3_active after state-machine guards.",
                "recommendation": "Require visual review before dashboard.",
            },
            {
                "severity": "high" if late else "low",
                "risk": "late_context",
                "description": f"{late} rows have late cycle context.",
                "recommendation": "Use latest-close/freshness warning before display.",
            },
            {
                "severity": "medium" if invalid_start else "low",
                "risk": "invalid_cycle_start",
                "description": f"{invalid_start} rows have invalid cycle start semantics.",
                "recommendation": "Keep manual_review_only for these rows.",
            },
        ]
    )


def decide_next_step(machine: pd.DataFrame, guard: pd.DataFrame, freshness: pd.DataFrame) -> str:
    if not machine["lookahead_safe"].map(to_bool).all():
        return "blocked_for_dashboard_wave_context"
    manual = int(machine["display_policy"].astype(str).eq("manual_review_only").sum())
    displayable = int(machine["display_policy"].astype(str).eq("displayable_in_dashboard").sum())
    warnings = int(machine["display_policy"].astype(str).eq("show_with_warning").sum())
    if displayable:
        return "wave_state_machine_v0_promising_for_broader_review"
    if warnings and manual < len(machine):
        return "wave_state_machine_v0_warning_only"
    if manual == len(machine):
        return "wave_state_machine_v0_too_conservative"
    return "wave_state_machine_v0_needs_more_review"


def build_run_meta(
    generated_at: str,
    config: StateMachineConfig,
    machine: pd.DataFrame,
    guard: pd.DataFrame,
    freshness: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_state_machine_v0",
        "decision": decision,
        "cycle_dir": str(config.cycle_dir),
        "symbols": sorted(machine["symbol"].dropna().astype(str).unique().tolist()),
        "timeframes": sorted(machine["timeframe"].dropna().astype(str).unique().tolist()),
        "rows": int(len(machine)),
        "estimated_current_wave_distribution": machine["estimated_current_wave"].value_counts().sort_index().to_dict(),
        "display_policy_distribution": machine["display_policy"].value_counts().sort_index().to_dict(),
        "context_freshness_distribution": machine["context_freshness_status"].value_counts().sort_index().to_dict(),
        "guard_blockers_distribution": guard["transition_blockers"].value_counts().sort_index().to_dict(),
        "safety": {
            "real_sql_executed": False,
            "ddl_executed": False,
            "mt5_connected": False,
            "backtests_executed": False,
            "signals_generated": False,
            "dashboard_implemented": False,
            "telegram_implemented": False,
            "bot_implemented": False,
        },
    }


def write_outputs(
    *,
    config: StateMachineConfig,
    hypotheses: pd.DataFrame,
    transitions: pd.DataFrame,
    guard_audit: pd.DataFrame,
    freshness: pd.DataFrame,
    comparison: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": config.output_dir / "wave_state_machine_hypothesis.csv",
        "json": config.output_dir / "wave_state_machine_hypothesis.json",
        "transitions": config.output_dir / "wave_state_transitions.csv",
        "guard": config.output_dir / "state_guard_audit.csv",
        "freshness": config.output_dir / "freshness_invalidation_audit.csv",
        "comparison": config.output_dir / "comparison_vs_cycle_state.csv",
        "dashboard": config.output_dir / "dashboard_display_contract.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    hypotheses.to_csv(paths["csv"], index=False)
    paths["json"].write_text(json.dumps(hypotheses.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    transitions.to_csv(paths["transitions"], index=False)
    guard_audit.to_csv(paths["guard"], index=False)
    freshness.to_csv(paths["freshness"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    dashboard_contract.to_csv(paths["dashboard"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_charts(config: StateMachineConfig, machine: pd.DataFrame, pivots: pd.DataFrame, ohlc: pd.DataFrame) -> None:
    if ohlc.empty:
        return
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    for _, row in machine.iterrows():
        symbol = str(row["symbol"])
        timeframe = str(row["timeframe"])
        as_of = pd.Timestamp(row["as_of_bar_time"])
        prices = ohlc[(ohlc["symbol"].astype(str) == symbol) & (ohlc["timeframe"].astype(str) == timeframe)].copy()
        prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
        prices = prices[prices["time"] <= as_of].sort_values("time").tail(260)
        if prices.empty:
            continue
        cycle = cycle_pivots(pivots, symbol, timeframe, str(row["cycle_id"]).split("_current_")[-1], str(row["cycle_id"]).split("_current_")[-1])
        # Re-select by payload pivot prices when cycle id parsing is not enough.
        payload = json.loads(str(row["payload_json"]))
        path = chart_dir / f"wave_state_machine_{safe_id(symbol)}_{timeframe}.png"
        render_chart(path, prices, row, payload)


def render_chart(path: Path, prices: pd.DataFrame, row: pd.Series, payload: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.patch.set_facecolor("white")
    ax.plot(prices["time"], prices["close"], color="#333333", linewidth=1.3, label="close")
    ax.axvline(pd.Timestamp(row["as_of_bar_time"]), color="#000000", linestyle=":", linewidth=1.0, label="as_of")
    if row["activation_level"] != "":
        ax.axhline(float(row["activation_level"]), color="#0072B2", linestyle="--", linewidth=1.0, label="activation")
    if row["invalidation_level"] != "":
        ax.axhline(float(row["invalidation_level"]), color="#D55E00", linestyle="--", linewidth=1.0, label="invalidation")
    ax.scatter([pd.Timestamp(row["latest_close_time"])], [float(row["latest_close"])], color="#009988", s=48, label="latest close", zorder=4)
    ax.set_title(f"{row['symbol']} {row['timeframe']}: {row['estimated_current_wave']} ({row['display_policy']})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.text(0.01, 0.02, "state-machine audit | read-only | no signal / no filter / no execution", transform=ax.transAxes, fontsize=8, color="#555555")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_docs(
    config: StateMachineConfig,
    machine: pd.DataFrame,
    transitions: pd.DataFrame,
    guard: pd.DataFrame,
    freshness: pd.DataFrame,
    comparison: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    summary = machine[
        [
            "symbol",
            "timeframe",
            "estimated_current_wave",
            "state_machine_state",
            "display_policy",
            "context_freshness_status",
            "transition_blockers",
        ]
    ]
    doc = f"""# WaveCount State Machine v0

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase introduce una maquina de estados explicita encima de
`wavecount_cycle_state_v0`. El objetivo es impedir que una cola de 3 pivotes se
convierta automaticamente en `possible_wave3_*` sin comprobar:

- tipo de pivote inicial;
- latest close frente a nivel de activacion;
- invalidacion;
- frescura del contexto;
- guardarrailes anti look-ahead.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Hipotesis

{markdown_table(summary)}

## Guardrails

{markdown_table(guard)}

## Frescura E Invalidacion

{markdown_table(freshness)}

## Transiciones

{markdown_table(transitions)}

## Comparacion Contra Cycle State

{markdown_table(comparison)}

## Riesgos

{markdown_table(issues)}

## Lectura

- La maquina de estados no aprueba ninguna fila como senal ni filtro.
- Las filas con inicio de ciclo invalido pasan a `manual_review_only`.
- Las filas con contexto tardio pueden quedar `show_with_warning`, nunca como
  contexto fresco.
- Antes de SQL/dashboard hace falta revisar si `show_with_warning` es suficiente
  para una vista informativa o si WaveCount debe quedar en pestana de estudio.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_STATE_MACHINE_V0.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-operative WaveCount state machine v0.")
    parser.add_argument("--cycle-dir", type=Path, default=DEFAULT_CYCLE_DIR)
    parser.add_argument("--persistent-dir", type=Path, default=DEFAULT_PERSISTENT_DIR)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--fresh-lag-bars", type=int, default=24)
    parser.add_argument("--acceptable-lag-bars", type=int, default=60)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_state_machine(
        StateMachineConfig(
            cycle_dir=args.cycle_dir,
            persistent_dir=args.persistent_dir,
            audit_dir=args.audit_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            source_csv=args.source_csv,
            fresh_lag_bars=args.fresh_lag_bars,
            acceptable_lag_bars=args.acceptable_lag_bars,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "rows": int(len(result.hypotheses)),
                "output_dir": str(args.output_dir),
                "real_sql_executed": False,
                "mt5_connected": False,
                "backtests_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
