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


DEFAULT_STATE_MACHINE_DIR = Path("artifacts/tfg/wavecount_state_machine_v0_2026-05-27")
DEFAULT_CYCLE_DIR = Path("artifacts/tfg/wavecount_cycle_state_v0_2026-05-27")
DEFAULT_PERSISTENT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_estimate_v0_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_ESTIMATE_V0.md")

LIVE_ESTIMATE_COLUMNS = [
    "estimate_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "as_of_bar_time",
    "source",
    "confirmed_wave_context",
    "live_estimated_wave",
    "next_wave_hypothesis",
    "structure_family",
    "direction",
    "current_leg_direction",
    "current_leg_status",
    "last_persistent_pivot_type",
    "last_persistent_pivot_price",
    "last_persistent_pivot_time",
    "latest_close",
    "latest_close_time",
    "move_from_last_pivot_pct",
    "retracement_from_previous_leg_pct",
    "activation_level",
    "invalidation_level",
    "distance_to_activation_pct",
    "distance_to_invalidation_pct",
    "confidence_bucket",
    "freshness_status",
    "display_policy",
    "why_this_label",
    "why_not_higher_confidence",
    "requires_manual_review",
    "lookahead_safe",
    "is_read_only",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
    "method_version",
    "notes",
    "payload_json",
]


@dataclass(frozen=True)
class LiveEstimateConfig:
    state_machine_dir: Path = DEFAULT_STATE_MACHINE_DIR
    cycle_dir: Path = DEFAULT_CYCLE_DIR
    persistent_dir: Path = DEFAULT_PERSISTENT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_csv: Path = DEFAULT_SOURCE_CSV
    flat_move_pct: float = 0.10
    pullback_warning_pct: float = 25.0
    generate_charts: bool = True


@dataclass(frozen=True)
class LiveEstimateResult:
    estimates: pd.DataFrame
    current_leg_audit: pd.DataFrame
    estimate_rule_audit: pd.DataFrame
    confidence_warning_audit: pd.DataFrame
    comparison: pd.DataFrame
    dashboard_contract: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_live_estimate(config: LiveEstimateConfig | None = None) -> LiveEstimateResult:
    config = config or LiveEstimateConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)

    rows: list[dict[str, Any]] = []
    leg_rows: list[dict[str, Any]] = []
    rule_rows: list[dict[str, Any]] = []
    confidence_rows: list[dict[str, Any]] = []

    for _, state_row in sources["state"].iterrows():
        cycle_row = matching_cycle_row(sources["cycle"], state_row)
        pivots = cycle_pivots(
            sources["pivots"],
            str(state_row["symbol"]),
            str(state_row["timeframe"]),
            str(cycle_row.get("cycle_start_pivot_uid", "")),
            str(cycle_row.get("cycle_end_pivot_uid", "")),
        )
        latest = latest_close_row(sources["ohlc"], state_row)
        row, leg, rule, confidence = classify_live_estimate(
            config=config,
            generated_at=generated_at,
            state_row=state_row,
            cycle_row=cycle_row,
            pivots=pivots,
            latest_close=latest,
        )
        rows.append(row)
        leg_rows.append(leg)
        rule_rows.append(rule)
        confidence_rows.append(confidence)

    estimates = normalize_estimates(pd.DataFrame(rows))
    current_leg = pd.DataFrame(leg_rows)
    rule_audit = pd.DataFrame(rule_rows)
    confidence = pd.DataFrame(confidence_rows)
    comparison = build_comparison(sources["state"], estimates)
    dashboard_contract = dashboard_display_contract_frame()
    issues = build_issues_or_risks(estimates, current_leg, confidence)
    decision = decide_next_step(estimates)
    run_meta = build_run_meta(generated_at, config, estimates, decision)
    written = write_outputs(
        config=config,
        estimates=estimates,
        current_leg=current_leg,
        rule_audit=rule_audit,
        confidence=confidence,
        comparison=comparison,
        dashboard_contract=dashboard_contract,
        issues=issues,
        run_meta=run_meta,
    )
    if config.generate_charts:
        write_charts(config, estimates, sources["pivots"], sources["ohlc"])
    write_docs(config, estimates, current_leg, rule_audit, confidence, comparison, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_ESTIMATE_V0.md"
    return LiveEstimateResult(
        estimates=estimates,
        current_leg_audit=current_leg,
        estimate_rule_audit=rule_audit,
        confidence_warning_audit=confidence,
        comparison=comparison,
        dashboard_contract=dashboard_contract,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: LiveEstimateConfig) -> dict[str, Any]:
    required = {
        "state": config.state_machine_dir / "wave_state_machine_hypothesis.csv",
        "cycle": config.cycle_dir / "cycle_state_hypothesis.csv",
        "pivots": config.persistent_dir / "persistent_pivots.csv",
        "run_meta": config.state_machine_dir / "run_meta.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing live estimate inputs: {missing}")
    return {
        "state": pd.read_csv(required["state"]),
        "cycle": pd.read_csv(required["cycle"]),
        "pivots": pd.read_csv(required["pivots"]),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
        "ohlc": load_source_ohlc(config.source_csv) if config.source_csv.exists() else pd.DataFrame(),
    }


def classify_live_estimate(
    *,
    config: LiveEstimateConfig,
    generated_at: str,
    state_row: pd.Series,
    cycle_row: pd.Series,
    pivots: pd.DataFrame,
    latest_close: pd.Series | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    symbol = str(state_row["symbol"])
    timeframe = str(state_row["timeframe"])
    as_of = pd.Timestamp(state_row["as_of_bar_time"])
    latest_time = pd.Timestamp(latest_close["time"]) if latest_close is not None else pd.NaT
    latest_price = float(latest_close["close"]) if latest_close is not None else None
    latest_safe = latest_close is not None and latest_time <= as_of
    payload = safe_payload(state_row.get("payload_json", "{}"))
    direction = str(payload.get("direction") or infer_direction(pivots))
    confirmed = str(state_row.get("confirmed_wave_context", "not_available"))
    state_wave = str(state_row.get("estimated_current_wave", "not_available"))
    activation = parse_optional_float(state_row.get("activation_level"))
    invalidation = parse_optional_float(state_row.get("invalidation_level"))
    invalidated = bool(state_wave == "invalidated" or invalidates(latest_price, invalidation, direction))
    last_pivot = pivots.iloc[-1] if not pivots.empty else None
    previous_pivot = pivots.iloc[-2] if len(pivots) >= 2 else None
    leg = current_leg_metrics(config, latest_price, latest_time, last_pivot, previous_pivot, direction)
    activation_crossed = confirms_activation(latest_price, activation, direction)
    live_wave, leg_status, confidence, freshness, display, manual, why, why_not = estimate_live_wave(
        state_wave=state_wave,
        confirmed=confirmed,
        invalidated=invalidated,
        activation_crossed=activation_crossed,
        direction=direction,
        leg=leg,
        latest_safe=latest_safe,
    )
    lookahead_safe = bool(latest_safe and (pivots["pivot_detected_at"] <= as_of).all()) if not pivots.empty else bool(latest_safe)
    row = {
        "estimate_id": f"wavecount_live_estimate_v0_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}",
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": state_row.get("market_group", ""),
        "timeframe": timeframe,
        "higher_timeframe": state_row.get("higher_timeframe", ""),
        "as_of_bar_time": as_of.isoformat(),
        "source": "wavecount_live_estimate_v0",
        "confirmed_wave_context": confirmed,
        "live_estimated_wave": live_wave,
        "next_wave_hypothesis": NEXT_PHASE.get(live_wave, "not_available"),
        "structure_family": structure_family(live_wave),
        "direction": direction,
        "current_leg_direction": leg["current_leg_direction"],
        "current_leg_status": leg_status,
        "last_persistent_pivot_type": str(last_pivot["pivot_type"]) if last_pivot is not None else "",
        "last_persistent_pivot_price": float_or_blank(float(last_pivot["pivot_price"])) if last_pivot is not None else "",
        "last_persistent_pivot_time": timestamp_text(pd.Timestamp(last_pivot["pivot_extreme_time"])) if last_pivot is not None else "",
        "latest_close": float_or_blank(latest_price),
        "latest_close_time": timestamp_text(latest_time) if latest_close is not None else "",
        "move_from_last_pivot_pct": leg["move_from_last_pivot_pct"],
        "retracement_from_previous_leg_pct": leg["retracement_from_previous_leg_pct"],
        "activation_level": float_or_blank(activation),
        "invalidation_level": float_or_blank(invalidation),
        "distance_to_activation_pct": distance_to_level_pct(latest_price, activation),
        "distance_to_invalidation_pct": distance_to_invalidation(float(latest_price), invalidation) if latest_price is not None else "",
        "confidence_bucket": confidence,
        "freshness_status": freshness,
        "display_policy": display,
        "why_this_label": why,
        "why_not_higher_confidence": why_not,
        "requires_manual_review": manual,
        "lookahead_safe": lookahead_safe,
        "is_read_only": True,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "method_version": "wavecount_live_estimate_v0",
        "notes": "live estimate from latest close; no_signal_no_filter_no_execution",
        "payload_json": json.dumps(
            {
                "state_machine_wave": state_wave,
                "state_machine_display_policy": state_row.get("display_policy", ""),
                "state_machine_blockers": state_row.get("transition_blockers", ""),
                "activation_crossed": activation_crossed,
                "invalidated": invalidated,
                "latest_close_safe": latest_safe,
                "operational_use": "forbidden",
            },
            sort_keys=True,
            default=str,
        ),
    }
    current_leg_row = {
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "current_leg_direction": row["current_leg_direction"],
        "current_leg_status": row["current_leg_status"],
        "last_persistent_pivot_type": row["last_persistent_pivot_type"],
        "last_persistent_pivot_price": row["last_persistent_pivot_price"],
        "last_persistent_pivot_time": row["last_persistent_pivot_time"],
        "latest_close": row["latest_close"],
        "latest_close_time": row["latest_close_time"],
        "move_from_last_pivot_pct": row["move_from_last_pivot_pct"],
        "retracement_from_previous_leg_pct": row["retracement_from_previous_leg_pct"],
        "lookahead_safe": lookahead_safe,
    }
    rule_row = {
        "symbol": symbol,
        "timeframe": timeframe,
        "state_machine_wave": state_wave,
        "live_estimated_wave": live_wave,
        "activation_crossed": activation_crossed,
        "invalidated": invalidated,
        "rule_applied": rule_name(live_wave, state_wave, invalidated, activation_crossed, leg_status),
        "why_this_label": why,
        "why_not_higher_confidence": why_not,
        "lookahead_safe": lookahead_safe,
    }
    confidence_row = {
        "symbol": symbol,
        "timeframe": timeframe,
        "live_estimated_wave": live_wave,
        "confidence_bucket": confidence,
        "freshness_status": freshness,
        "display_policy": display,
        "requires_manual_review": manual,
        "warning": why_not,
    }
    return row, current_leg_row, rule_row, confidence_row


def matching_cycle_row(cycle: pd.DataFrame, state_row: pd.Series) -> pd.Series:
    match = cycle[
        (cycle["symbol"].astype(str) == str(state_row["symbol"]))
        & (cycle["timeframe"].astype(str) == str(state_row["timeframe"]))
    ]
    if match.empty:
        return pd.Series(dtype=object)
    return match.iloc[0]


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


def latest_close_row(ohlc: pd.DataFrame, state_row: pd.Series) -> pd.Series | None:
    if ohlc.empty:
        return None
    as_of = pd.Timestamp(state_row["as_of_bar_time"])
    part = ohlc[
        (ohlc["symbol"].astype(str) == str(state_row["symbol"]))
        & (ohlc["timeframe"].astype(str) == str(state_row["timeframe"]))
    ].copy()
    if part.empty:
        return None
    part["time"] = pd.to_datetime(part["time"], errors="coerce")
    part = part[part["time"] <= as_of].sort_values("time")
    return part.iloc[-1] if not part.empty else None


def current_leg_metrics(
    config: LiveEstimateConfig,
    latest_price: float | None,
    latest_time: pd.Timestamp,
    last_pivot: pd.Series | None,
    previous_pivot: pd.Series | None,
    direction: str,
) -> dict[str, Any]:
    if latest_price is None or last_pivot is None:
        return {
            "current_leg_direction": "unknown",
            "move_from_last_pivot_pct": "",
            "retracement_from_previous_leg_pct": "",
        }
    last_price = float(last_pivot["pivot_price"])
    move_pct = signed_pct(latest_price, last_price)
    if abs(move_pct) < config.flat_move_pct:
        leg_direction = "flat"
    else:
        leg_direction = "up" if move_pct > 0 else "down"
    retracement = ""
    if previous_pivot is not None:
        previous_price = float(previous_pivot["pivot_price"])
        previous_leg = last_price - previous_price
        current_move = latest_price - last_price
        if previous_leg and current_move and ((previous_leg > 0 > current_move) or (previous_leg < 0 < current_move)):
            retracement = round(abs(current_move) / abs(previous_leg) * 100.0, 4)
        else:
            retracement = 0.0
    return {
        "current_leg_direction": leg_direction,
        "move_from_last_pivot_pct": round(move_pct, 4),
        "retracement_from_previous_leg_pct": retracement,
    }


def estimate_live_wave(
    *,
    state_wave: str,
    confirmed: str,
    invalidated: bool,
    activation_crossed: bool,
    direction: str,
    leg: dict[str, Any],
    latest_safe: bool,
) -> tuple[str, str, str, str, str, bool, str, str]:
    if not latest_safe:
        return (
            "not_available",
            "unknown",
            "low",
            "manual_review_required",
            "not_displayable",
            True,
            "latest close is missing or after as_of_bar_time",
            "no causal latest close available",
        )
    if invalidated or state_wave == "invalidated":
        return (
            "invalidated",
            "failed_breakout",
            "low",
            "manual_review_required",
            "manual_review_only",
            True,
            "latest close breached invalidation or state machine invalidated the cycle",
            "invalidated contexts cannot receive higher confidence",
        )

    leg_direction = str(leg["current_leg_direction"])
    retracement = parse_optional_float(leg.get("retracement_from_previous_leg_pct"))
    pullback = retracement is not None and retracement >= 15.0
    if state_wave == "possible_wave3_active" and not activation_crossed and pullback:
        return (
            "possible_wave3_active",
            "pullback",
            "medium",
            "live_estimate_from_close",
            "show_live_estimate_with_warning",
            False,
            "state machine had active wave3 and latest close shows pullback without invalidation",
            "pullback may later become wave4, but no invalidation/confirmed transition yet",
        )
    if activation_crossed and state_wave in {"possible_wave3_active", "possible_wave3_candidate"}:
        return (
            "possible_wave3_active",
            "impulse_attempt",
            "medium",
            "live_estimate_from_close",
            "show_live_estimate_with_warning",
            False,
            "latest close crossed activation in the inferred cycle direction",
            "confirmed context is still late and this is not an operational signal",
        )
    if state_wave in {"possible_wave3_active", "possible_wave3_candidate"}:
        return (
            "possible_wave3_candidate",
            "breakout_attempt" if leg_direction in {"up", "down"} else "range_or_noise",
            "low",
            "live_estimate_from_close",
            "show_live_estimate_with_warning",
            False,
            "latest close has not crossed activation but keeps a plausible wave3 attempt alive",
            "activation is not crossed; confidence remains low",
        )
    if state_wave in {"ambiguous", "not_available", "unknown"}:
        return (
            "ambiguous",
            "unknown",
            "low",
            "manual_review_required",
            "manual_review_only",
            True,
            "state machine did not provide a usable cycle context",
            "insufficient structural context",
        )
    return (
        state_wave,
        "unknown",
        "low",
        "live_estimate_from_close",
        "show_study_only",
        False,
        "state machine context carried forward with latest close available",
        "no specific live rule upgraded confidence",
    )


def confirms_activation(latest_price: float | None, activation: float | None, direction: str) -> bool:
    if latest_price is None or activation is None:
        return False
    if direction == "long":
        return latest_price > activation
    if direction == "short":
        return latest_price < activation
    return False


def invalidates(latest_price: float | None, invalidation: float | None, direction: str) -> bool:
    if latest_price is None or invalidation is None:
        return False
    if direction == "long":
        return latest_price < invalidation
    if direction == "short":
        return latest_price > invalidation
    return False


def infer_direction(pivots: pd.DataFrame) -> str:
    if len(pivots) < 2:
        return "unknown"
    return "long" if float(pivots.iloc[-1]["pivot_price"]) >= float(pivots.iloc[0]["pivot_price"]) else "short"


def structure_family(wave: str) -> str:
    if "waveA" in wave or "waveB" in wave or "waveC" in wave or "abc" in wave.lower():
        return "correction"
    if wave in {"invalidated", "ambiguous", "not_available", "unknown"}:
        return "unknown"
    return "impulse"


def signed_pct(value: float, reference: float) -> float:
    if reference == 0:
        return 0.0
    return (value - reference) / abs(reference) * 100.0


def distance_to_level_pct(value: float | None, level: float | None) -> float | str:
    if value is None or level is None or level == 0:
        return ""
    return round(abs(value - level) / abs(level) * 100.0, 6)


def parse_optional_float(value: Any) -> float | None:
    try:
        if value == "" or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_payload(value: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def rule_name(live_wave: str, state_wave: str, invalidated: bool, activation_crossed: bool, leg_status: str) -> str:
    if invalidated or live_wave == "invalidated":
        return "invalidation_guard"
    if state_wave == "possible_wave3_active" and leg_status == "pullback":
        return "wave3_pullback_without_phase_change"
    if activation_crossed:
        return "activation_crossed_live_estimate"
    if live_wave == "possible_wave3_candidate":
        return "activation_pending_candidate"
    return "state_machine_context_carried_forward"


def normalize_estimates(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in LIVE_ESTIMATE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=LIVE_ESTIMATE_COLUMNS)
    for column in ["requires_manual_review", "lookahead_safe", "is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
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
        raise ValueError("lookahead_safe=false blocks live estimate output")


def build_comparison(state: pd.DataFrame, estimates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in estimates.iterrows():
        match = state[
            (state["symbol"].astype(str) == str(row["symbol"]))
            & (state["timeframe"].astype(str) == str(row["timeframe"]))
        ]
        old = match.iloc[0] if not match.empty else {}
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "state_machine_wave": old.get("estimated_current_wave", "not_available"),
                "live_estimated_wave": row["live_estimated_wave"],
                "state_machine_display_policy": old.get("display_policy", "not_available"),
                "live_display_policy": row["display_policy"],
                "state_machine_confirmed_context": old.get("confirmed_wave_context", "not_available"),
                "confirmed_wave_context": row["confirmed_wave_context"],
                "changed_label": old.get("estimated_current_wave", "") != row["live_estimated_wave"],
                "comparison_note": comparison_note(old.get("estimated_current_wave", ""), row),
            }
        )
    return pd.DataFrame(rows)


def comparison_note(old_wave: str, row: pd.Series) -> str:
    if row["live_estimated_wave"] == "invalidated":
        return "live_estimate_keeps_invalidation"
    if row["display_policy"] == "show_live_estimate_with_warning":
        return "latest_close_adds_live_estimate"
    if row["display_policy"] == "manual_review_only":
        return "live_estimate_blocks_context"
    return "live_estimate_study_only"


def dashboard_display_contract_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"display_policy": "show_live_estimate_with_warning", "meaning": "Can be shown as provisional live wave context with warning.", "telegram_allowed": False, "bot_allowed": False},
            {"display_policy": "show_study_only", "meaning": "Can be shown only in study/manual context.", "telegram_allowed": False, "bot_allowed": False},
            {"display_policy": "manual_review_only", "meaning": "Requires human review; hide from default wave summary.", "telegram_allowed": False, "bot_allowed": False},
            {"display_policy": "not_displayable", "meaning": "No useful context.", "telegram_allowed": False, "bot_allowed": False},
        ]
    )


def build_issues_or_risks(estimates: pd.DataFrame, current_leg: pd.DataFrame, confidence: pd.DataFrame) -> pd.DataFrame:
    manual = int(estimates["display_policy"].astype(str).eq("manual_review_only").sum())
    live = int(estimates["display_policy"].astype(str).eq("show_live_estimate_with_warning").sum())
    low_conf = int(estimates["confidence_bucket"].astype(str).eq("low").sum())
    return pd.DataFrame(
        [
            {
                "severity": "info",
                "risk": "lookahead_guard",
                "description": "All rows use latest close <= as_of_bar_time.",
                "recommendation": "Keep as hard guardrail.",
            },
            {
                "severity": "medium" if manual else "low",
                "risk": "manual_review_only",
                "description": f"{manual} rows require manual review.",
                "recommendation": "Do not show manual rows as live wave context.",
            },
            {
                "severity": "medium" if live else "low",
                "risk": "provisional_live_estimate",
                "description": f"{live} rows are provisional live estimates.",
                "recommendation": "Show only with warning; never use as signal/filter.",
            },
            {
                "severity": "medium" if low_conf else "low",
                "risk": "low_confidence",
                "description": f"{low_conf} rows have low confidence.",
                "recommendation": "Keep why_not_higher_confidence visible.",
            },
        ]
    )


def decide_next_step(estimates: pd.DataFrame) -> str:
    if not estimates["lookahead_safe"].map(to_bool).all():
        return "blocked_for_dashboard_wave_context"
    live = int(estimates["display_policy"].astype(str).eq("show_live_estimate_with_warning").sum())
    manual = int(estimates["display_policy"].astype(str).eq("manual_review_only").sum())
    ambiguous = int(estimates["live_estimated_wave"].astype(str).eq("ambiguous").sum())
    if live and manual < len(estimates):
        return "live_estimate_v0_promising_for_visual_review"
    if manual == len(estimates):
        return "live_estimate_v0_study_only"
    if ambiguous == len(estimates):
        return "live_estimate_v0_too_ambiguous"
    return "live_estimate_v0_needs_more_review"


def build_run_meta(generated_at: str, config: LiveEstimateConfig, estimates: pd.DataFrame, decision: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_estimate_v0",
        "decision": decision,
        "symbols": sorted(estimates["symbol"].dropna().astype(str).unique().tolist()),
        "timeframes": sorted(estimates["timeframe"].dropna().astype(str).unique().tolist()),
        "live_estimated_wave_distribution": estimates["live_estimated_wave"].value_counts().sort_index().to_dict(),
        "confidence_bucket_distribution": estimates["confidence_bucket"].value_counts().sort_index().to_dict(),
        "display_policy_distribution": estimates["display_policy"].value_counts().sort_index().to_dict(),
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
    config: LiveEstimateConfig,
    estimates: pd.DataFrame,
    current_leg: pd.DataFrame,
    rule_audit: pd.DataFrame,
    confidence: pd.DataFrame,
    comparison: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": config.output_dir / "live_wave_estimate.csv",
        "json": config.output_dir / "live_wave_estimate.json",
        "current_leg": config.output_dir / "current_leg_audit.csv",
        "rules": config.output_dir / "estimate_rule_audit.csv",
        "anti_lookahead": config.output_dir / "anti_lookahead_audit.csv",
        "confidence": config.output_dir / "confidence_warning_audit.csv",
        "comparison": config.output_dir / "comparison_vs_state_machine.csv",
        "dashboard": config.output_dir / "dashboard_display_contract.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    estimates.to_csv(paths["csv"], index=False)
    paths["json"].write_text(json.dumps(estimates.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    current_leg.to_csv(paths["current_leg"], index=False)
    rule_audit.to_csv(paths["rules"], index=False)
    estimates[
        [
            "symbol",
            "timeframe",
            "as_of_bar_time",
            "latest_close_time",
            "last_persistent_pivot_time",
            "lookahead_safe",
            "source",
            "method_version",
        ]
    ].assign(
        latest_close_not_after_as_of=lambda frame: pd.to_datetime(frame["latest_close_time"], errors="coerce")
        <= pd.to_datetime(frame["as_of_bar_time"], errors="coerce")
    ).to_csv(paths["anti_lookahead"], index=False)
    confidence.to_csv(paths["confidence"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    dashboard_contract.to_csv(paths["dashboard"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_charts(config: LiveEstimateConfig, estimates: pd.DataFrame, pivots: pd.DataFrame, ohlc: pd.DataFrame) -> None:
    if ohlc.empty:
        return
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    for _, row in estimates.iterrows():
        symbol = str(row["symbol"])
        timeframe = str(row["timeframe"])
        as_of = pd.Timestamp(row["as_of_bar_time"])
        prices = ohlc[(ohlc["symbol"].astype(str) == symbol) & (ohlc["timeframe"].astype(str) == timeframe)].copy()
        prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
        prices = prices[prices["time"] <= as_of].sort_values("time").tail(280)
        if prices.empty:
            continue
        symbol_pivots = pivots[
            (pivots["symbol"].astype(str) == symbol)
            & (pivots["timeframe"].astype(str) == timeframe)
            & (pivots["pivot_role"].astype(str) == "persistent_pivot")
        ].copy()
        symbol_pivots["pivot_extreme_time"] = pd.to_datetime(symbol_pivots["pivot_extreme_time"], errors="coerce")
        symbol_pivots["pivot_price"] = pd.to_numeric(symbol_pivots["pivot_price"], errors="coerce")
        path = chart_dir / f"live_estimate_{safe_id(symbol)}_{timeframe}.png"
        render_chart(path, prices, symbol_pivots, row)


def render_chart(path: Path, prices: pd.DataFrame, pivots: pd.DataFrame, row: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.patch.set_facecolor("white")
    ax.plot(prices["time"], prices["close"], color="#333333", linewidth=1.3, label="close")
    if not pivots.empty:
        ax.scatter(pivots["pivot_extreme_time"], pivots["pivot_price"], color="#999999", s=28, label="persistent pivots", zorder=3)
    if row["last_persistent_pivot_time"]:
        ax.scatter([pd.Timestamp(row["last_persistent_pivot_time"])], [float(row["last_persistent_pivot_price"])], color="#0072B2", s=58, label="last pivot", zorder=4)
        ax.plot([pd.Timestamp(row["last_persistent_pivot_time"]), pd.Timestamp(row["latest_close_time"])], [float(row["last_persistent_pivot_price"]), float(row["latest_close"])], color="#0072B2", linewidth=1.6, label="live leg", zorder=3)
    if row["activation_level"] != "":
        ax.axhline(float(row["activation_level"]), color="#0072B2", linestyle="--", linewidth=1.0, label="activation")
    if row["invalidation_level"] != "":
        ax.axhline(float(row["invalidation_level"]), color="#D55E00", linestyle="--", linewidth=1.0, label="invalidation")
    ax.scatter([pd.Timestamp(row["latest_close_time"])], [float(row["latest_close"])], color="#009988", s=54, label="latest close", zorder=5)
    ax.axvline(pd.Timestamp(row["as_of_bar_time"]), color="#000000", linestyle=":", linewidth=1.0, label="as_of")
    ax.set_title(f"{row['symbol']} {row['timeframe']}: {row['live_estimated_wave']} ({row['display_policy']})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.text(0.01, 0.02, "live estimate | read-only | no signal / no filter / no execution", transform=ax.transAxes, fontsize=8, color="#555555")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_docs(
    config: LiveEstimateConfig,
    estimates: pd.DataFrame,
    current_leg: pd.DataFrame,
    rule_audit: pd.DataFrame,
    confidence: pd.DataFrame,
    comparison: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    summary = estimates[
        [
            "symbol",
            "timeframe",
            "confirmed_wave_context",
            "live_estimated_wave",
            "current_leg_status",
            "confidence_bucket",
            "freshness_status",
            "display_policy",
        ]
    ]
    doc = f"""# WaveCount Live Estimate v0

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase cambia el enfoque: no intenta confirmar en vivo un conteo perfecto,
sino emitir una hipotesis viva, provisional y auditable usando el ultimo cierre
y el tramo actual desde el ultimo pivote persistente.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Diferencia Frente A State Machine

- `confirmed_wave_context` conserva el contexto confirmado/tardio.
- `live_estimated_wave` usa ultimo cierre y tramo actual.
- Cada etiqueta incluye `why_this_label` y `why_not_higher_confidence`.
- La salida puede ser visible solo como contexto provisional, nunca como senal.

## Resumen Por Activo

{markdown_table(summary)}

## Tramo Actual

{markdown_table(current_leg)}

## Reglas Aplicadas

{markdown_table(rule_audit)}

## Confianza Y Warnings

{markdown_table(confidence)}

## Comparacion Contra State Machine

{markdown_table(comparison)}

## Riesgos

{markdown_table(issues)}

## Lectura

- La capa genera hipotesis vivas por activo cuando hay ultimo cierre causal.
- Las hipotesis son provisionales y read-only.
- No hay Telegram, bot, filtro ni orden.
- Antes de SQL/dashboard hace falta una auditoria visual de las etiquetas vivas.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_ESTIMATE_V0.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-operative WaveCount live estimate v0.")
    parser.add_argument("--state-machine-dir", type=Path, default=DEFAULT_STATE_MACHINE_DIR)
    parser.add_argument("--cycle-dir", type=Path, default=DEFAULT_CYCLE_DIR)
    parser.add_argument("--persistent-dir", type=Path, default=DEFAULT_PERSISTENT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_live_estimate(
        LiveEstimateConfig(
            state_machine_dir=args.state_machine_dir,
            cycle_dir=args.cycle_dir,
            persistent_dir=args.persistent_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            source_csv=args.source_csv,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "rows": int(len(result.estimates)),
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
