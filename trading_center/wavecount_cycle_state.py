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
    beyond,
    distance_to_invalidation,
    float_or_blank,
    safe_id,
    timestamp_text,
    to_bool,
    validate_payload,
)


DEFAULT_INPUT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_cycle_state_v0_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_CYCLE_STATE_V0.md")

CYCLE_STATE_COLUMNS = [
    "hypothesis_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "as_of_bar_time",
    "cycle_id",
    "cycle_status",
    "cycle_family",
    "cycle_start_pivot_uid",
    "cycle_end_pivot_uid",
    "cycle_pivot_count",
    "cycle_start_time",
    "cycle_last_pivot_time",
    "cycle_reset_reason",
    "previous_cycle_id",
    "estimated_current_wave",
    "confirmed_wave_context",
    "next_wave_hypothesis",
    "wave_event",
    "wave_event_reason",
    "freshness_status",
    "wave_stability_status",
    "display_policy",
    "invalidation_level",
    "distance_to_invalidation_pct",
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
class CycleStateConfig:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_csv: Path = DEFAULT_SOURCE_CSV
    max_cycle_pivots: int = 6
    active_tail_pivots: int = 3
    generate_charts: bool = True


@dataclass(frozen=True)
class CycleStateResult:
    hypotheses: pd.DataFrame
    cycle_registry: pd.DataFrame
    cycle_transitions: pd.DataFrame
    cycle_reset_audit: pd.DataFrame
    wave_state_machine_audit: pd.DataFrame
    comparison: pd.DataFrame
    anti_lookahead_audit: pd.DataFrame
    dashboard_display_contract: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_cycle_state(config: CycleStateConfig | None = None) -> CycleStateResult:
    config = config or CycleStateConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)

    rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    reset_rows: list[dict[str, Any]] = []
    machine_rows: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []

    latest = latest_hypotheses(sources["hypotheses"])
    for _, latest_row in latest.iterrows():
        symbol = str(latest_row["symbol"])
        timeframe = str(latest_row["timeframe"])
        pivots = pivots_for_symbol(sources["pivots"], symbol, timeframe)
        row, registry, transitions, reset, machine, anti = classify_symbol_cycle(
            config=config,
            generated_at=generated_at,
            latest_row=latest_row,
            pivots=pivots,
        )
        rows.append(row)
        registry_rows.extend(registry)
        transition_rows.extend(transitions)
        reset_rows.extend(reset)
        machine_rows.extend(machine)
        anti_rows.append(anti)

    hypotheses = normalize_hypotheses(pd.DataFrame(rows))
    registry = pd.DataFrame(registry_rows)
    transitions = pd.DataFrame(transition_rows)
    reset_audit = pd.DataFrame(reset_rows)
    machine = pd.DataFrame(machine_rows)
    anti = pd.DataFrame(anti_rows)
    comparison = build_comparison(sources["hypotheses"], hypotheses)
    dashboard_contract = dashboard_display_contract_frame()
    issues = build_issues_or_risks(hypotheses, reset_audit, comparison, anti)
    decision = decide_next_step(hypotheses, reset_audit, comparison, anti)
    run_meta = build_run_meta(generated_at, config, hypotheses, registry, reset_audit, anti, decision)
    written = write_outputs(
        config=config,
        hypotheses=hypotheses,
        registry=registry,
        transitions=transitions,
        reset_audit=reset_audit,
        machine=machine,
        comparison=comparison,
        anti=anti,
        dashboard_contract=dashboard_contract,
        issues=issues,
        run_meta=run_meta,
    )
    if config.generate_charts:
        write_charts(config, hypotheses, registry, sources["ohlc"])
    write_docs(config, hypotheses, registry, reset_audit, machine, comparison, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_CYCLE_STATE_V0.md"
    return CycleStateResult(
        hypotheses=hypotheses,
        cycle_registry=registry,
        cycle_transitions=transitions,
        cycle_reset_audit=reset_audit,
        wave_state_machine_audit=machine,
        comparison=comparison,
        anti_lookahead_audit=anti,
        dashboard_display_contract=dashboard_contract,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: CycleStateConfig) -> dict[str, Any]:
    required = {
        "hypotheses": config.input_dir / "persistent_wave_hypothesis.csv",
        "pivots": config.input_dir / "persistent_pivots.csv",
        "anti": config.input_dir / "anti_lookahead_audit.csv",
        "run_meta": config.input_dir / "run_meta.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing cycle state inputs: {missing}")
    return {
        "hypotheses": pd.read_csv(required["hypotheses"]),
        "pivots": pd.read_csv(required["pivots"]),
        "anti": pd.read_csv(required["anti"]),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
        "ohlc": load_source_ohlc(config.source_csv) if config.source_csv.exists() else pd.DataFrame(),
    }


def latest_hypotheses(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.sort_values(["symbol", "timeframe", "cut_number"]).groupby(["symbol", "timeframe"], as_index=False).tail(1)


def pivots_for_symbol(pivots: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
    part = pivots[
        (pivots["symbol"].astype(str) == symbol)
        & (pivots["timeframe"].astype(str) == timeframe)
        & (pivots["pivot_role"].astype(str) == "persistent_pivot")
    ].copy()
    part["pivot_extreme_time"] = pd.to_datetime(part["pivot_extreme_time"], errors="coerce")
    part["pivot_detected_at"] = pd.to_datetime(part["pivot_detected_at"], errors="coerce")
    part["pivot_price"] = pd.to_numeric(part["pivot_price"], errors="coerce")
    return part.dropna(subset=["pivot_extreme_time", "pivot_detected_at", "pivot_price"]).sort_values(
        ["pivot_extreme_time", "pivot_detected_at", "pivot_type"]
    )


def classify_symbol_cycle(
    *,
    config: CycleStateConfig,
    generated_at: str,
    latest_row: pd.Series,
    pivots: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    symbol = str(latest_row["symbol"])
    timeframe = str(latest_row["timeframe"])
    as_of = pd.Timestamp(latest_row["as_of_bar_time"])
    market_group = str(latest_row.get("market_group", ""))
    higher_timeframe = str(latest_row.get("higher_timeframe", ""))
    total_pivots = int(len(pivots))
    reset_needed = total_pivots > config.max_cycle_pivots
    current = pivots.tail(config.active_tail_pivots).copy() if reset_needed else pivots.copy()
    previous = pivots.iloc[: max(0, total_pivots - len(current))].copy() if reset_needed else pd.DataFrame()
    previous_cycle_id = cycle_id(symbol, timeframe, "previous", previous) if not previous.empty else ""
    current_cycle_id = cycle_id(symbol, timeframe, "current", current)
    direction = infer_direction(current)
    current_price = float(current.iloc[-1]["pivot_price"]) if not current.empty else 0.0
    estimated = estimate_cycle_wave(current, direction, reset_needed)
    confirmed = estimate_cycle_wave(current[current["pivot_detected_at"] <= as_of], direction, reset_needed)
    status = cycle_status(current, reset_needed)
    family = cycle_family(current, reset_needed)
    freshness = "provisional_estimate" if reset_needed else "fresh_estimate"
    stability = "provisional" if reset_needed else "stable_enough_for_display"
    display = "show_with_warning" if estimated not in {"unknown", "ambiguous"} else "manual_review_only"
    reset_reason = cycle_reset_reason(total_pivots, current, reset_needed, config)
    invalidation = invalidation_level(current, direction, estimated)
    row = {
        "hypothesis_id": f"cycle_state_v0_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}",
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": market_group,
        "timeframe": timeframe,
        "higher_timeframe": higher_timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "cycle_id": current_cycle_id,
        "cycle_status": status,
        "cycle_family": family,
        "cycle_start_pivot_uid": first_value(current, "pivot_uid"),
        "cycle_end_pivot_uid": last_value(current, "pivot_uid"),
        "cycle_pivot_count": int(len(current)),
        "cycle_start_time": timestamp_text(current["pivot_extreme_time"].min()) if not current.empty else "",
        "cycle_last_pivot_time": timestamp_text(current["pivot_extreme_time"].max()) if not current.empty else "",
        "cycle_reset_reason": reset_reason,
        "previous_cycle_id": previous_cycle_id,
        "estimated_current_wave": estimated,
        "confirmed_wave_context": confirmed,
        "next_wave_hypothesis": NEXT_PHASE.get(estimated, "not_available"),
        "wave_event": "cycle_reset_candidate" if reset_needed else "cycle_state_updated",
        "wave_event_reason": reset_reason if reset_needed else "cycle_within_pivot_limit",
        "freshness_status": freshness,
        "wave_stability_status": stability,
        "display_policy": display,
        "invalidation_level": float_or_blank(invalidation),
        "distance_to_invalidation_pct": distance_to_invalidation(current_price, invalidation),
        "lookahead_safe": bool((current["pivot_detected_at"] <= as_of).all()) if not current.empty else True,
        "is_read_only": True,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "source": "wavecount_cycle_state_v0",
        "data_origin": "persistent_hypothesis_artifacts",
        "method_version": "wavecount_cycle_state_v0",
        "notes": "cycle reset context only; no_signal_no_filter_no_execution",
        "payload_json": json.dumps(
            {
                "total_persistent_pivots": total_pivots,
                "current_cycle_pivots": current["pivot_uid"].astype(str).tolist() if not current.empty else [],
                "previous_cycle_pivots": previous["pivot_uid"].astype(str).tolist() if not previous.empty else [],
                "operational_use": "forbidden",
            },
            sort_keys=True,
            default=str,
        ),
    }
    registry = []
    if not previous.empty:
        registry.append(cycle_registry_row(previous_cycle_id, symbol, timeframe, previous, "completed_candidate", "impulse", "", ""))
    registry.append(cycle_registry_row(current_cycle_id, symbol, timeframe, current, status, family, reset_reason, previous_cycle_id))
    transitions = state_machine_transitions(symbol, timeframe, as_of, current, estimated, reset_needed)
    reset_rows = []
    if reset_needed:
        reset_rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "as_of_bar_time": as_of.isoformat(),
                "previous_cycle_id": previous_cycle_id,
                "new_cycle_id": current_cycle_id,
                "total_persistent_pivots": total_pivots,
                "current_cycle_pivots": int(len(current)),
                "reset_reason": reset_reason,
                "lookahead_safe": row["lookahead_safe"],
            }
        )
    machine = [
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "as_of_bar_time": as_of.isoformat(),
            "from_state": transition["from_state"],
            "to_state": transition["to_state"],
            "event": transition["event"],
            "reason": transition["reason"],
            "pivot_uid": transition["pivot_uid"],
            "lookahead_safe": transition["lookahead_safe"],
        }
        for transition in transitions
    ]
    anti = {
        "hypothesis_id": row["hypothesis_id"],
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "max_pivot_detected_at": timestamp_text(current["pivot_detected_at"].max()) if not current.empty else "",
        "pivot_detected_at_lte_as_of": row["lookahead_safe"],
        "lookahead_safe": row["lookahead_safe"],
    }
    return row, registry, transitions, reset_rows, machine, anti


def cycle_id(symbol: str, timeframe: str, label: str, pivots: pd.DataFrame) -> str:
    if pivots.empty:
        return f"cycle_{safe_id(symbol)}_{timeframe}_{label}_empty"
    start = safe_id(timestamp_text(pivots["pivot_extreme_time"].min()))
    end = safe_id(timestamp_text(pivots["pivot_extreme_time"].max()))
    return f"cycle_{safe_id(symbol)}_{timeframe}_{label}_{start}_{end}"


def cycle_registry_row(
    identifier: str,
    symbol: str,
    timeframe: str,
    pivots: pd.DataFrame,
    status: str,
    family: str,
    reset_reason: str,
    previous_cycle_id: str,
) -> dict[str, Any]:
    return {
        "cycle_id": identifier,
        "symbol": symbol,
        "timeframe": timeframe,
        "cycle_status": status,
        "cycle_family": family,
        "cycle_start_pivot_uid": first_value(pivots, "pivot_uid"),
        "cycle_end_pivot_uid": last_value(pivots, "pivot_uid"),
        "cycle_pivot_count": int(len(pivots)),
        "cycle_start_time": timestamp_text(pivots["pivot_extreme_time"].min()) if not pivots.empty else "",
        "cycle_last_pivot_time": timestamp_text(pivots["pivot_extreme_time"].max()) if not pivots.empty else "",
        "cycle_reset_reason": reset_reason,
        "previous_cycle_id": previous_cycle_id,
    }


def state_machine_transitions(
    symbol: str,
    timeframe: str,
    as_of: pd.Timestamp,
    pivots: pd.DataFrame,
    estimated: str,
    reset_needed: bool,
) -> list[dict[str, Any]]:
    transitions = []
    state = "cycle_forming_wave1"
    for index, (_, pivot) in enumerate(pivots.iterrows(), start=1):
        next_state = state_from_count(index, estimated if index == len(pivots) else "")
        transitions.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "as_of_bar_time": as_of.isoformat(),
                "from_state": state,
                "to_state": next_state,
                "event": "cycle_reset_applied" if reset_needed and index == 1 else "pivot_accepted",
                "reason": "current_cycle_tail_after_reset" if reset_needed and index == 1 else "persistent_pivot_matures_state",
                "pivot_uid": pivot.get("pivot_uid", ""),
                "lookahead_safe": bool(pd.Timestamp(pivot.get("pivot_detected_at")) <= as_of),
            }
        )
        state = next_state
    return transitions


def state_from_count(count: int, estimated: str = "") -> str:
    if estimated:
        mapping = {
            "possible_wave1": "cycle_forming_wave1",
            "possible_wave2": "cycle_possible_wave2",
            "possible_wave3_candidate": "cycle_possible_wave3_candidate",
            "possible_wave3_active": "cycle_possible_wave3_active",
            "possible_wave4": "cycle_possible_wave4",
            "possible_wave5_candidate": "cycle_possible_wave5_candidate",
            "possible_wave5_active": "cycle_possible_wave5_active",
            "ambiguous": "cycle_ambiguous",
        }
        return mapping.get(estimated, "cycle_ambiguous")
    if count <= 1:
        return "cycle_forming_wave1"
    if count == 2:
        return "cycle_possible_wave2"
    if count == 3:
        return "cycle_possible_wave3_candidate"
    if count == 4:
        return "cycle_possible_wave4"
    if count == 5:
        return "cycle_possible_wave5_candidate"
    return "cycle_mature_needs_reset"


def estimate_cycle_wave(pivots: pd.DataFrame, direction: str, reset_needed: bool) -> str:
    count = len(pivots)
    if count == 0:
        return "unknown"
    if not structure_alternates(pivots):
        return "ambiguous"
    if count == 1:
        return "possible_wave1"
    if count == 2:
        return "possible_wave2"
    if count == 3:
        current_price = float(pivots.iloc[-1]["pivot_price"])
        reference = float(pivots.iloc[1]["pivot_price"])
        return "possible_wave3_active" if beyond(current_price, reference, direction) else "possible_wave3_candidate"
    if count == 4:
        return "possible_wave4"
    if count == 5 and not reset_needed:
        return "possible_wave5_candidate"
    if reset_needed:
        return "possible_wave3_candidate" if count <= 3 else "ambiguous"
    return "ambiguous"


def cycle_status(pivots: pd.DataFrame, reset_needed: bool) -> str:
    if pivots.empty:
        return "ambiguous"
    if reset_needed:
        return "reset_candidate"
    if len(pivots) >= 5:
        return "mature"
    if len(pivots) >= 3:
        return "active"
    return "forming"


def cycle_family(pivots: pd.DataFrame, reset_needed: bool) -> str:
    if pivots.empty:
        return "unknown"
    if reset_needed and len(pivots) == 3:
        return "impulse"
    if len(pivots) <= 5:
        return "impulse"
    return "unknown"


def cycle_reset_reason(total_pivots: int, current: pd.DataFrame, reset_needed: bool, config: CycleStateConfig) -> str:
    if not reset_needed:
        return "not_applicable"
    reasons = [f"total_persistent_pivots_gt_{config.max_cycle_pivots}", "cycle_tail_re_evaluated"]
    if len(current) <= config.active_tail_pivots:
        reasons.append("old_pivots_moved_to_previous_cycle")
    return ";".join(reasons)


def infer_direction(pivots: pd.DataFrame) -> str:
    if len(pivots) < 2:
        return "long"
    return "long" if float(pivots.iloc[-1]["pivot_price"]) >= float(pivots.iloc[0]["pivot_price"]) else "short"


def structure_alternates(frame: pd.DataFrame) -> bool:
    if frame.empty or len(frame) < 2:
        return True
    values = frame["pivot_type"].astype(str).tolist()
    return all(left != right for left, right in zip(values, values[1:]))


def invalidation_level(frame: pd.DataFrame, direction: str, estimated: str) -> float | None:
    if frame.empty or estimated in {"unknown", "ambiguous"}:
        return None
    if direction == "short":
        highs = frame[frame["pivot_type"].astype(str) == "high"]
        return float(highs.iloc[-1]["pivot_price"]) if not highs.empty else None
    lows = frame[frame["pivot_type"].astype(str) == "low"]
    return float(lows.iloc[-1]["pivot_price"]) if not lows.empty else None


def first_value(frame: pd.DataFrame, column: str) -> str:
    return str(frame.iloc[0][column]) if not frame.empty and column in frame.columns else ""


def last_value(frame: pd.DataFrame, column: str) -> str:
    return str(frame.iloc[-1][column]) if not frame.empty and column in frame.columns else ""


def build_comparison(persistent: pd.DataFrame, cycle: pd.DataFrame) -> pd.DataFrame:
    latest_persistent = latest_hypotheses(persistent)
    rows = []
    for _, row in cycle.iterrows():
        match = latest_persistent[
            (latest_persistent["symbol"].astype(str) == str(row["symbol"]))
            & (latest_persistent["timeframe"].astype(str) == str(row["timeframe"]))
        ]
        old = match.iloc[0] if not match.empty else {}
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "persistent_estimated_current_wave": old.get("estimated_current_wave", "not_available"),
                "cycle_estimated_current_wave": row["estimated_current_wave"],
                "persistent_display_policy": old.get("display_policy", "not_available"),
                "cycle_display_policy": row["display_policy"],
                "persistent_pivot_count": old.get("persistent_pivot_count", "not_available"),
                "cycle_pivot_count": row["cycle_pivot_count"],
                "cycle_status": row["cycle_status"],
                "wave5_reduced": bool("wave5" in str(old.get("estimated_current_wave", "")) and "wave5" not in str(row["estimated_current_wave"])),
                "comparison_note": "cycle_reset_reduced_wave5" if "wave5" not in str(row["estimated_current_wave"]) else "wave5_still_present",
            }
        )
    return pd.DataFrame(rows)


def dashboard_display_contract_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"display_policy": "displayable_in_dashboard", "meaning": "Cycle state is stable and read-only.", "bot_allowed": False},
            {"display_policy": "show_with_warning", "meaning": "Cycle state is provisional/reset-derived.", "bot_allowed": False},
            {"display_policy": "manual_review_only", "meaning": "Cycle state is ambiguous or inconsistent.", "bot_allowed": False},
            {"display_policy": "not_displayable", "meaning": "No useful cycle context.", "bot_allowed": False},
        ]
    )


def build_issues_or_risks(cycle: pd.DataFrame, reset: pd.DataFrame, comparison: pd.DataFrame, anti: pd.DataFrame) -> pd.DataFrame:
    wave5_remaining = int(cycle["estimated_current_wave"].astype(str).str.contains("wave5|completed_impulse", regex=True).sum())
    reset_count = int(len(reset))
    ambiguous = int(cycle["estimated_current_wave"].astype(str).eq("ambiguous").sum())
    lookahead_ok = bool(anti["lookahead_safe"].map(to_bool).all()) if not anti.empty else False
    return pd.DataFrame(
        [
            {
                "severity": "blocking" if not lookahead_ok else "info",
                "risk": "lookahead_guard",
                "description": "Anti look-ahead checks passed." if lookahead_ok else "At least one cycle uses future pivots.",
                "recommendation": "Block until fixed." if not lookahead_ok else "Keep as hard guardrail.",
            },
            {
                "severity": "info",
                "risk": "cycle_resets",
                "description": f"{reset_count} cycle reset candidates generated.",
                "recommendation": "Review visually before dashboard.",
            },
            {
                "severity": "medium" if wave5_remaining else "low",
                "risk": "remaining_wave5",
                "description": f"{wave5_remaining} latest rows remain wave5/completed-style states.",
                "recommendation": "Do not advance if wave5 dominance remains.",
            },
            {
                "severity": "medium" if ambiguous else "low",
                "risk": "ambiguous_cycle_state",
                "description": f"{ambiguous} latest rows are ambiguous.",
                "recommendation": "If dominant, design deeper state machine.",
            },
        ]
    )


def decide_next_step(cycle: pd.DataFrame, reset: pd.DataFrame, comparison: pd.DataFrame, anti: pd.DataFrame) -> str:
    lookahead_ok = bool(anti["lookahead_safe"].map(to_bool).all()) if not anti.empty else True
    if not lookahead_ok:
        return "blocked_for_dashboard_wave_context"
    wave5_remaining = int(cycle["estimated_current_wave"].astype(str).str.contains("wave5|completed_impulse", regex=True).sum())
    ambiguous = int(cycle["estimated_current_wave"].astype(str).eq("ambiguous").sum())
    warnings = int(cycle["display_policy"].astype(str).eq("show_with_warning").sum())
    reset_count = int(len(reset))
    if wave5_remaining == 0 and reset_count and ambiguous < len(cycle):
        return "cycle_state_v0_promising_for_visual_review" if warnings else "cycle_state_v0_needs_more_review"
    if ambiguous == len(cycle):
        return "cycle_state_v0_too_ambiguous"
    if wave5_remaining:
        return "cycle_state_v0_needs_more_review"
    return "needs_deeper_wave_state_machine"


def build_run_meta(
    generated_at: str,
    config: CycleStateConfig,
    cycle: pd.DataFrame,
    registry: pd.DataFrame,
    reset: pd.DataFrame,
    anti: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_cycle_state_v0",
        "decision": decision,
        "input_dir": str(config.input_dir),
        "symbols": sorted(cycle["symbol"].dropna().unique().tolist()),
        "timeframes": sorted(cycle["timeframe"].dropna().unique().tolist()),
        "cycles_detected": int(len(registry)),
        "estimated_current_wave_distribution": cycle["estimated_current_wave"].value_counts().sort_index().to_dict(),
        "cycle_status_distribution": cycle["cycle_status"].value_counts().sort_index().to_dict(),
        "display_policy_distribution": cycle["display_policy"].value_counts().sort_index().to_dict(),
        "reset_candidates": int(len(reset)),
        "anti_lookahead_passed": bool(anti["lookahead_safe"].map(to_bool).all()) if not anti.empty else False,
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


def normalize_hypotheses(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in CYCLE_STATE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=CYCLE_STATE_COLUMNS)
    for column in ["lookahead_safe", "is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
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
        raise ValueError("lookahead_safe=false blocks cycle state output")


def write_outputs(
    *,
    config: CycleStateConfig,
    hypotheses: pd.DataFrame,
    registry: pd.DataFrame,
    transitions: pd.DataFrame,
    reset_audit: pd.DataFrame,
    machine: pd.DataFrame,
    comparison: pd.DataFrame,
    anti: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": output_dir / "cycle_state_hypothesis.csv",
        "json": output_dir / "cycle_state_hypothesis.json",
        "cycle_registry": output_dir / "cycle_registry.csv",
        "cycle_transitions": output_dir / "cycle_transitions.csv",
        "cycle_reset_audit": output_dir / "cycle_reset_audit.csv",
        "wave_state_machine_audit": output_dir / "wave_state_machine_audit.csv",
        "comparison": output_dir / "comparison_vs_persistent_hypothesis.csv",
        "anti": output_dir / "anti_lookahead_audit.csv",
        "dashboard": output_dir / "dashboard_display_contract.csv",
        "issues": output_dir / "issues_or_risks.csv",
        "run_meta": output_dir / "run_meta.json",
    }
    hypotheses.to_csv(paths["csv"], index=False)
    paths["json"].write_text(json.dumps(hypotheses.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    registry.to_csv(paths["cycle_registry"], index=False)
    transitions.to_csv(paths["cycle_transitions"], index=False)
    reset_audit.to_csv(paths["cycle_reset_audit"], index=False)
    machine.to_csv(paths["wave_state_machine_audit"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    anti.to_csv(paths["anti"], index=False)
    dashboard_contract.to_csv(paths["dashboard"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_charts(config: CycleStateConfig, cycle: pd.DataFrame, registry: pd.DataFrame, ohlc: pd.DataFrame) -> None:
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    if ohlc.empty:
        return
    for _, row in cycle.iterrows():
        symbol = str(row["symbol"])
        timeframe = str(row["timeframe"])
        as_of = pd.Timestamp(row["as_of_bar_time"])
        prices = ohlc[(ohlc["symbol"].astype(str) == symbol) & (ohlc["timeframe"].astype(str) == timeframe)].copy()
        prices = prices[pd.to_datetime(prices["time"]) <= as_of].sort_values("time").tail(220)
        if prices.empty:
            continue
        pivots = registry[(registry["symbol"].astype(str) == symbol) & (registry["timeframe"].astype(str) == timeframe)].copy()
        path = chart_dir / f"cycle_state_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}.png"
        render_chart(path, prices, pivots, row)


def render_chart(path: Path, prices: pd.DataFrame, registry: pd.DataFrame, row: pd.Series) -> None:
    prices = prices.copy()
    prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    fig.patch.set_facecolor("white")
    ax.plot(prices["time"], prices["close"], color="#333333", linewidth=1.4, label="close")
    previous = registry[registry["cycle_id"].astype(str) == str(row["previous_cycle_id"])] if str(row["previous_cycle_id"]) else pd.DataFrame()
    current = registry[registry["cycle_id"].astype(str) == str(row["cycle_id"])]
    plot_cycle_markers(ax, previous, color="#999999", label="previous cycle")
    plot_cycle_markers(ax, current, color="#0072B2", label="current cycle")
    if str(row["cycle_status"]) == "reset_candidate" and str(row["cycle_start_time"]):
        ax.axvline(pd.Timestamp(row["cycle_start_time"]), color="#D55E00", linestyle="--", linewidth=1.2, label="reset")
    ax.set_title(f"{row['symbol']} {row['timeframe']} - {row['estimated_current_wave']} ({row['cycle_status']})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.text(0.01, 0.02, "read-only context | no signal / no filter / no execution", transform=ax.transAxes, fontsize=8, color="#555555")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_cycle_markers(ax: Any, cycle_rows: pd.DataFrame, *, color: str, label: str) -> None:
    if cycle_rows.empty:
        return
    for _, cycle in cycle_rows.iterrows():
        start = pd.Timestamp(cycle["cycle_start_time"]) if str(cycle.get("cycle_start_time", "")) else None
        end = pd.Timestamp(cycle["cycle_last_pivot_time"]) if str(cycle.get("cycle_last_pivot_time", "")) else None
        if start is not None:
            ax.scatter([start], [ax.get_ylim()[0]], color=color, s=40, marker="o", label=label)
        if end is not None:
            ax.scatter([end], [ax.get_ylim()[1]], color=color, s=40, marker="s")


def write_docs(
    config: CycleStateConfig,
    cycle: pd.DataFrame,
    registry: pd.DataFrame,
    reset: pd.DataFrame,
    machine: pd.DataFrame,
    comparison: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    summary = cycle[
        [
            "symbol",
            "timeframe",
            "cycle_status",
            "cycle_family",
            "cycle_pivot_count",
            "estimated_current_wave",
            "display_policy",
            "cycle_reset_reason",
        ]
    ]
    doc = f"""# WaveCount Cycle State v0

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase introduce segmentacion de ciclo/reset para evitar que los pivotes
persistentes se acumulen indefinidamente hasta convertir todos los activos en
`possible_wave5_active`.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Por Que Se Introduce Ciclo/Reset

`wavecount_persistent_hypothesis_v0` resolvio parte de la ambiguedad inicial,
pero arrastro demasiados pivotes persistentes dentro de una unica secuencia. El
resultado fue una dominancia artificial de onda 5: 4/4 activos H4 terminaron
como `possible_wave5_active/show_with_warning`.

`wavecount_cycle_state_v0` no intenta demostrar que exista una onda 3 real. Su
objetivo es mas acotado: separar pivotes heredados de pivotes del ciclo actual
para que una lectura viva no madure por acumulacion historica indefinida.

## Reglas De Reset V0

- Si un activo acumula mas de {config.max_cycle_pivots} pivotes persistentes,
  los pivotes antiguos pasan a `previous_cycle_id`.
- El ciclo actual se reevalua con la cola reciente de
  {config.active_tail_pivots} pivotes persistentes.
- El estado queda `reset_candidate` y `show_with_warning`, no aprobado para
  uso operativo.
- La salida mantiene flags fail-closed:
  `can_generate_signal=false`, `can_filter_trade=false`,
  `can_execute_order=false`.
- La regla es deliberadamente simple y necesita revision visual posterior.

## Hipotesis Por Activo

{markdown_table(summary)}

## Resets

{markdown_table(reset)}

## Comparacion Contra Persistent Hypothesis

{markdown_table(comparison)}

## Maquina De Estados

{markdown_table(machine.head(20))}

## Riesgos

{markdown_table(issues)}

## Interpretacion

- La dominancia `possible_wave5_active` baja en la comparacion contra el modelo
  persistente, pero esto no prueba que los nuevos estados sean correctos.
- Los estados `possible_wave3_active` y `possible_wave3_candidate` son hipotesis
  de ciclo actual, no senales ENBOLSA, no filtros RiskGuard y no ordenes.
- La capa sigue bloqueada para SQL/dashboard hasta una auditoria visual de
  ciclos/reset.
- Si la revision visual detecta resets falsos o ondas 3 artificiales, el
  siguiente paso seria una maquina de estados de onda mas profunda.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_CYCLE_STATE_V0.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-operative WaveCount cycle state/reset prototype.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--max-cycle-pivots", type=int, default=6)
    parser.add_argument("--active-tail-pivots", type=int, default=3)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_cycle_state(
        CycleStateConfig(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            source_csv=args.source_csv,
            max_cycle_pivots=args.max_cycle_pivots,
            active_tail_pivots=args.active_tail_pivots,
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
