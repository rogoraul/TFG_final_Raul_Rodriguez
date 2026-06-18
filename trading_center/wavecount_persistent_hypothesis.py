from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table
from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import (
    DEFAULT_HIGHER_TIMEFRAME,
    DEFAULT_SOURCE_CSV,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAME,
    load_source_ohlc,
    progressive_cut_indexes,
)
from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_pivots import detect_causal_pivots
from backtests.wavecount.wavecount_structure import StructuralPivotConfig, build_structural_pivots
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


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_PERSISTENT_HYPOTHESIS_V0.md")
DEFAULT_CURRENT_HYPOTHESIS_CSV = Path(
    "artifacts/tfg/wavecount_current_hypothesis_v0_2026-05-27/current_wave_hypothesis.csv"
)

PERSISTENT_HYPOTHESIS_COLUMNS = [
    "hypothesis_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "cut_number",
    "as_of_bar_time",
    "estimated_current_wave",
    "confirmed_wave_context",
    "next_wave_hypothesis",
    "hypothesis_status",
    "freshness_status",
    "wave_stability_status",
    "display_policy",
    "invalidation_level",
    "distance_to_invalidation_pct",
    "last_persistent_pivot_at",
    "last_candidate_pivot_at",
    "persistent_pivot_count",
    "candidate_pivot_count",
    "superseded_pivot_count",
    "wave_event",
    "wave_event_reason",
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

PIVOT_COLUMNS = [
    "pivot_uid",
    "symbol",
    "timeframe",
    "pivot_type",
    "pivot_extreme_time",
    "pivot_detected_at",
    "pivot_price",
    "pivot_role",
    "first_seen_at",
    "last_seen_at",
    "accepted_at",
    "superseded_at",
    "superseded_by",
    "persistence_cuts",
    "is_persistent",
    "is_current_candidate",
    "rejection_reason",
    "lookahead_safe",
]


@dataclass(frozen=True)
class PersistentHypothesisConfig:
    source_csv: Path = DEFAULT_SOURCE_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    current_hypothesis_csv: Path = DEFAULT_CURRENT_HYPOTHESIS_CSV
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    timeframe: str = DEFAULT_TIMEFRAME
    higher_timeframe: str = DEFAULT_HIGHER_TIMEFRAME
    max_symbols: int = 4
    cut_count: int = 10
    min_bars_first_cut: int = 40
    min_persistence_cuts: int = 2
    stable_tail_cuts: int = 2
    max_recent_superseded: int = 0
    max_fresh_lag_bars: int = 4
    max_acceptable_lag_bars: int = 8
    pivot_config: PivotConfig = PivotConfig(
        left_bars=10,
        confirmation_bars=6,
        atr_period=20,
        min_atr_multiplier=2.1,
        min_relative_move_pct=0.004,
        min_bars_between_pivots=12,
        candidate_lookback_bars=12,
    )
    structural_config: StructuralPivotConfig = StructuralPivotConfig(
        min_leg_atr_multiplier=7.5,
        min_leg_relative_move_pct=0.012,
        min_leg_bars=34,
    )


@dataclass(frozen=True)
class PersistentHypothesisResult:
    hypotheses: pd.DataFrame
    persistent_pivots: pd.DataFrame
    pivot_events: pd.DataFrame
    wave_events: pd.DataFrame
    anti_lookahead_audit: pd.DataFrame
    stability_audit: pd.DataFrame
    transition_audit: pd.DataFrame
    comparison_vs_current: pd.DataFrame
    dashboard_display_contract: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_persistent_hypothesis(
    config: PersistentHypothesisConfig | None = None,
) -> PersistentHypothesisResult:
    config = config or PersistentHypothesisConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source = load_source_ohlc(config.source_csv)
    selected = select_series(source, config)

    hypothesis_rows: list[dict[str, Any]] = []
    pivot_event_rows: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    final_registry_rows: list[dict[str, Any]] = []

    for (market_group, symbol, timeframe), series in selected.items():
        result = build_symbol_persistent_history(
            config=config,
            generated_at=generated_at,
            market_group=market_group,
            symbol=symbol,
            timeframe=timeframe,
            series=series,
        )
        hypothesis_rows.extend(result["hypotheses"])
        pivot_event_rows.extend(result["pivot_events"])
        anti_rows.extend(result["anti"])
        stability_rows.extend(result["stability"])
        transition_rows.extend(result["transitions"])
        final_registry_rows.extend(result["registry"])

    hypotheses = normalize_hypotheses(pd.DataFrame(hypothesis_rows))
    persistent_pivots = normalize_pivots(pd.DataFrame(final_registry_rows))
    pivot_events = pd.DataFrame(pivot_event_rows)
    wave_events = build_wave_events(hypotheses)
    anti = pd.DataFrame(anti_rows)
    stability = pd.DataFrame(stability_rows)
    transitions = pd.DataFrame(transition_rows)
    comparison = build_comparison_vs_current(config, hypotheses)
    dashboard_contract = dashboard_display_contract_frame()
    issues = build_issues_or_risks(hypotheses, persistent_pivots, anti, stability)
    decision = decide_next_step(hypotheses, issues)
    run_meta = build_run_meta(
        generated_at=generated_at,
        config=config,
        hypotheses=hypotheses,
        pivots=persistent_pivots,
        anti=anti,
        decision=decision,
    )
    written = write_outputs(
        config=config,
        hypotheses=hypotheses,
        pivots=persistent_pivots,
        pivot_events=pivot_events,
        wave_events=wave_events,
        anti=anti,
        stability=stability,
        transitions=transitions,
        comparison=comparison,
        dashboard_contract=dashboard_contract,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(
        config=config,
        hypotheses=hypotheses,
        pivots=persistent_pivots,
        comparison=comparison,
        dashboard_contract=dashboard_contract,
        issues=issues,
        decision=decision,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_PERSISTENT_HYPOTHESIS_V0.md"
    return PersistentHypothesisResult(
        hypotheses=hypotheses,
        persistent_pivots=persistent_pivots,
        pivot_events=pivot_events,
        wave_events=wave_events,
        anti_lookahead_audit=anti,
        stability_audit=stability,
        transition_audit=transitions,
        comparison_vs_current=comparison,
        dashboard_display_contract=dashboard_contract,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def select_series(source: pd.DataFrame, config: PersistentHypothesisConfig) -> dict[tuple[str, str, str], pd.DataFrame]:
    frame = source[source["timeframe"].astype(str).str.upper() == config.timeframe.upper()].copy()
    preferred = [symbol for symbol in config.symbols if symbol in set(frame["symbol"])]
    if len(preferred) < min(config.max_symbols, len(config.symbols)):
        grouped = frame.groupby(["market_group", "symbol"], dropna=False).size().reset_index(name="rows")
        for _, row in grouped.sort_values(["market_group", "symbol"]).iterrows():
            symbol = str(row["symbol"])
            if symbol not in preferred:
                preferred.append(symbol)
            if len(preferred) >= config.max_symbols:
                break
    selected: dict[tuple[str, str, str], pd.DataFrame] = {}
    for (group, symbol, timeframe), part in frame[frame["symbol"].isin(preferred[: config.max_symbols])].groupby(
        ["market_group", "symbol", "timeframe"],
        dropna=False,
    ):
        if len(part) >= 20:
            selected[(str(group), str(symbol), str(timeframe))] = part.sort_values("time").reset_index(drop=True)
    if not selected:
        raise ValueError("no usable OHLC series selected")
    return selected


def build_symbol_persistent_history(
    *,
    config: PersistentHypothesisConfig,
    generated_at: str,
    market_group: str,
    symbol: str,
    timeframe: str,
    series: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    bars_all = normalise_ohlc(series)
    cut_indexes = progressive_cut_indexes(len(bars_all), config.cut_count, config.min_bars_first_cut)
    registry: dict[str, dict[str, Any]] = {}
    hypotheses: list[dict[str, Any]] = []
    pivot_events: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    previous_phase = ""
    previous_pivot_hash = ""

    for cut_number, cut_index in enumerate(cut_indexes, start=1):
        as_of = pd.Timestamp(bars_all.iloc[cut_index]["time"])
        bars_used = bars_all[bars_all["time"] <= as_of].copy()
        structural, events = detect_structural_pivots(config, bars_used, symbol, timeframe)
        current_uids = update_pivot_registry(
            registry=registry,
            structural=structural,
            symbol=symbol,
            timeframe=timeframe,
            cut_number=cut_number,
            as_of=as_of,
            config=config,
        )
        pivot_events.extend(build_pivot_events(registry, current_uids, cut_number, as_of))
        active = active_persistent_sequence(registry, current_uids, as_of)
        candidates = current_candidate_sequence(registry, current_uids, config)
        superseded_recent = recent_superseded_count(registry, cut_number, config.stable_tail_cuts)
        current_price = float(bars_used.iloc[-1]["close"]) if not bars_used.empty else None
        direction = infer_direction(bars_used)
        row = classify_persistent_wave(
            config=config,
            generated_at=generated_at,
            market_group=market_group,
            symbol=symbol,
            timeframe=timeframe,
            cut_number=cut_number,
            as_of=as_of,
            active=active,
            candidates=candidates,
            current_price=current_price,
            direction=direction,
            superseded_recent=superseded_recent,
            previous_phase=previous_phase,
        )
        lookahead_safe = anti_lookahead_safe(bars_used, events, as_of)
        row["lookahead_safe"] = lookahead_safe
        hypotheses.append(row)
        anti_rows.append(
            {
                "hypothesis_id": row["hypothesis_id"],
                "symbol": symbol,
                "timeframe": timeframe,
                "cut_number": cut_number,
                "as_of_bar_time": as_of.isoformat(),
                "bars_total": int(len(bars_all)),
                "bars_used": int(len(bars_used)),
                "bars_after_as_of_ignored": int(len(bars_all) - len(bars_used)),
                "latest_pivot_detected_at": timestamp_text(events["pivot_detected_at"].max()) if not events.empty else "",
                "latest_pivot_detected_at_lte_as_of": True
                if events.empty
                else bool(pd.Timestamp(events["pivot_detected_at"].max()) <= as_of),
                "lookahead_safe": lookahead_safe,
            }
        )
        pivot_hash = pivot_set_hash(active)
        stability_rows.append(
            {
                "hypothesis_id": row["hypothesis_id"],
                "symbol": symbol,
                "timeframe": timeframe,
                "cut_number": cut_number,
                "persistent_pivots": int(len(active)),
                "candidate_pivots": int(len(candidates)),
                "superseded_recent": int(superseded_recent),
                "pivot_set_hash": pivot_hash,
                "pivot_set_changed": bool(previous_pivot_hash and previous_pivot_hash != pivot_hash),
                "estimated_current_wave": row["estimated_current_wave"],
                "display_policy": row["display_policy"],
            }
        )
        transition_rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "cut_number": cut_number,
                "as_of_bar_time": as_of.isoformat(),
                "previous_phase": previous_phase or "not_applicable",
                "current_phase": row["estimated_current_wave"],
                "transition_type": transition_type(previous_phase, row["estimated_current_wave"]),
                "pivot_set_changed": bool(previous_pivot_hash and previous_pivot_hash != pivot_hash),
                "display_policy": row["display_policy"],
            }
        )
        previous_phase = row["estimated_current_wave"]
        previous_pivot_hash = pivot_hash

    latest_cut = len(cut_indexes)
    registry_rows = [finalize_pivot_record(record, latest_cut) for record in registry.values()]
    return {
        "hypotheses": hypotheses,
        "pivot_events": pivot_events,
        "anti": anti_rows,
        "stability": stability_rows,
        "transitions": transition_rows,
        "registry": registry_rows,
    }


def detect_structural_pivots(
    config: PersistentHypothesisConfig,
    bars_used: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if bars_used.empty:
        return pd.DataFrame(), pd.DataFrame()
    ohlc = bars_used.set_index("time")[["open", "high", "low", "close"]]
    raw = detect_causal_pivots(ohlc, config.pivot_config, symbol=symbol, timeframe=timeframe)
    events = raw[raw["pivot_state"] != "no_pivot"].copy() if not raw.empty else pd.DataFrame()
    confirmed = events[events["is_confirmed"].astype(bool)].copy() if not events.empty else pd.DataFrame()
    if confirmed.empty:
        return pd.DataFrame(), events
    structural_result = build_structural_pivots(confirmed, config.structural_config)
    return structural_result["structural_pivots"].copy(), events


def update_pivot_registry(
    *,
    registry: dict[str, dict[str, Any]],
    structural: pd.DataFrame,
    symbol: str,
    timeframe: str,
    cut_number: int,
    as_of: pd.Timestamp,
    config: PersistentHypothesisConfig,
) -> set[str]:
    current_uids: set[str] = set()
    if not structural.empty:
        for _, pivot in structural.iterrows():
            uid = pivot_uid(symbol, timeframe, pivot)
            current_uids.add(uid)
            record = registry.setdefault(uid, make_pivot_record(uid, symbol, timeframe, pivot, as_of))
            record["last_seen_at"] = as_of.isoformat()
            record["last_seen_cut"] = cut_number
            record["seen_cuts"].add(cut_number)
            record["pivot_detected_at"] = timestamp_text(pivot.get("pivot_detected_at"))
            record["pivot_extreme_time"] = timestamp_text(pivot.get("pivot_extreme_time"))
            record["confirmation_lag_bars"] = int(float(pivot.get("confirmation_lag_bars", 0) or 0))
            if len(record["seen_cuts"]) >= config.min_persistence_cuts and not record["accepted_at"]:
                record["accepted_at"] = as_of.isoformat()
                record["accepted_cut"] = cut_number

    for uid, record in registry.items():
        if uid in current_uids:
            continue
        last_seen_cut = int(record.get("last_seen_cut", 0))
        if record.get("accepted_at") and not record.get("superseded_at") and last_seen_cut < cut_number:
            record["superseded_at"] = as_of.isoformat()
            record["superseded_cut"] = cut_number
        elif not record.get("accepted_at") and last_seen_cut < cut_number - 1:
            record["rejection_reason"] = "did_not_reach_persistence"
    return current_uids


def make_pivot_record(uid: str, symbol: str, timeframe: str, pivot: pd.Series, as_of: pd.Timestamp) -> dict[str, Any]:
    return {
        "pivot_uid": uid,
        "symbol": symbol,
        "timeframe": timeframe,
        "pivot_type": str(pivot.get("pivot_type", "")),
        "pivot_extreme_time": timestamp_text(pivot.get("pivot_extreme_time")),
        "pivot_detected_at": timestamp_text(pivot.get("pivot_detected_at")),
        "pivot_price": float_or_blank(pivot.get("pivot_extreme_price")),
        "first_seen_at": as_of.isoformat(),
        "last_seen_at": as_of.isoformat(),
        "accepted_at": "",
        "superseded_at": "",
        "superseded_by": "",
        "seen_cuts": set(),
        "accepted_cut": 0,
        "superseded_cut": 0,
        "last_seen_cut": 0,
        "confirmation_lag_bars": int(float(pivot.get("confirmation_lag_bars", 0) or 0)),
        "rejection_reason": "",
        "lookahead_safe": True,
    }


def build_pivot_events(
    registry: dict[str, dict[str, Any]],
    current_uids: set[str],
    cut_number: int,
    as_of: pd.Timestamp,
) -> list[dict[str, Any]]:
    rows = []
    for uid in sorted(current_uids):
        record = registry[uid]
        if record.get("accepted_cut") == cut_number:
            event_type = "persistent_accepted"
        elif record.get("accepted_at"):
            event_type = "persistent_seen"
        else:
            event_type = "candidate_seen"
        rows.append(
            {
                "pivot_uid": uid,
                "symbol": record["symbol"],
                "timeframe": record["timeframe"],
                "cut_number": cut_number,
                "as_of_bar_time": as_of.isoformat(),
                "event_type": event_type,
                "pivot_type": record["pivot_type"],
                "pivot_detected_at": record["pivot_detected_at"],
                "lookahead_safe": bool(pd.Timestamp(record["pivot_detected_at"]) <= as_of),
            }
        )
    for uid, record in registry.items():
        if record.get("superseded_cut") == cut_number:
            rows.append(
                {
                    "pivot_uid": uid,
                    "symbol": record["symbol"],
                    "timeframe": record["timeframe"],
                    "cut_number": cut_number,
                    "as_of_bar_time": as_of.isoformat(),
                    "event_type": "superseded",
                    "pivot_type": record["pivot_type"],
                    "pivot_detected_at": record["pivot_detected_at"],
                    "lookahead_safe": True,
                }
            )
    return rows


def active_persistent_sequence(registry: dict[str, dict[str, Any]], current_uids: set[str], as_of: pd.Timestamp) -> pd.DataFrame:
    records = []
    for uid in current_uids:
        record = registry[uid]
        if record.get("accepted_at") and not record.get("superseded_at"):
            records.append(record_to_row(record, "persistent_pivot", is_current_candidate=False))
    return sort_pivots(pd.DataFrame(records), as_of)


def current_candidate_sequence(
    registry: dict[str, dict[str, Any]],
    current_uids: set[str],
    config: PersistentHypothesisConfig,
) -> pd.DataFrame:
    records = []
    for uid in current_uids:
        record = registry[uid]
        if record.get("accepted_at"):
            continue
        role = "provisional_pivot" if len(record["seen_cuts"]) > 1 else "candidate_pivot"
        records.append(record_to_row(record, role, is_current_candidate=True))
    return sort_pivots(pd.DataFrame(records), pd.Timestamp.max)


def sort_pivots(frame: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["pivot_extreme_time_sort"] = pd.to_datetime(frame["pivot_extreme_time"], errors="coerce")
    frame["pivot_detected_at_sort"] = pd.to_datetime(frame["pivot_detected_at"], errors="coerce")
    frame = frame[frame["pivot_detected_at_sort"].isna() | (frame["pivot_detected_at_sort"] <= as_of)]
    return frame.sort_values(["pivot_extreme_time_sort", "pivot_detected_at_sort", "pivot_type"]).reset_index(drop=True)


def record_to_row(record: dict[str, Any], role: str, *, is_current_candidate: bool) -> dict[str, Any]:
    return {
        "pivot_uid": record["pivot_uid"],
        "symbol": record["symbol"],
        "timeframe": record["timeframe"],
        "pivot_type": record["pivot_type"],
        "pivot_extreme_time": record["pivot_extreme_time"],
        "pivot_detected_at": record["pivot_detected_at"],
        "pivot_price": record["pivot_price"],
        "pivot_role": role,
        "first_seen_at": record["first_seen_at"],
        "last_seen_at": record["last_seen_at"],
        "accepted_at": record["accepted_at"],
        "superseded_at": record["superseded_at"],
        "superseded_by": record["superseded_by"],
        "persistence_cuts": int(len(record["seen_cuts"])),
        "is_persistent": bool(role == "persistent_pivot"),
        "is_current_candidate": bool(is_current_candidate),
        "rejection_reason": record["rejection_reason"],
        "lookahead_safe": record["lookahead_safe"],
        "confirmation_lag_bars": int(record.get("confirmation_lag_bars", 0)),
    }


def finalize_pivot_record(record: dict[str, Any], latest_cut: int) -> dict[str, Any]:
    if record.get("accepted_at") and not record.get("superseded_at") and int(record.get("last_seen_cut", 0)) == latest_cut:
        role = "persistent_pivot"
        is_candidate = False
    elif record.get("accepted_at") and record.get("superseded_at"):
        role = "superseded_pivot"
        is_candidate = False
    elif int(record.get("last_seen_cut", 0)) == latest_cut:
        role = "provisional_pivot" if len(record["seen_cuts"]) > 1 else "candidate_pivot"
        is_candidate = True
    else:
        role = "rejected_pivot"
        is_candidate = False
        if not record.get("rejection_reason"):
            record["rejection_reason"] = "not_seen_in_latest_cut"
    return record_to_row(record, role, is_current_candidate=is_candidate)


def classify_persistent_wave(
    *,
    config: PersistentHypothesisConfig,
    generated_at: str,
    market_group: str,
    symbol: str,
    timeframe: str,
    cut_number: int,
    as_of: pd.Timestamp,
    active: pd.DataFrame,
    candidates: pd.DataFrame,
    current_price: float | None,
    direction: str,
    superseded_recent: int,
    previous_phase: str,
) -> dict[str, Any]:
    alternates = structure_alternates(active)
    persistent_count = int(len(active))
    candidate_count = int(len(candidates))
    max_lag = max_confirmation_lag(active)
    stable_enough = alternates and superseded_recent <= config.max_recent_superseded

    confirmed = phase_from_persistent_sequence(active, current_price, direction, stable_enough)
    estimated = estimate_with_candidates(confirmed, active, candidates, current_price, direction, stable_enough)
    freshness = compute_freshness(estimated, confirmed, candidate_count, max_lag, stable_enough, config)
    stability = compute_stability(active, candidates, stable_enough, superseded_recent)
    display = compute_display_policy(estimated, freshness, stability)
    wave_event = compute_wave_event(previous_phase, estimated, stability, candidate_count)
    event_reason = compute_wave_event_reason(
        active=active,
        candidates=candidates,
        stable_enough=stable_enough,
        superseded_recent=superseded_recent,
        max_lag=max_lag,
    )
    invalidation = invalidation_level(active, direction, estimated)
    payload = {
        "pivot_config": asdict(config.pivot_config),
        "structural_config": asdict(config.structural_config),
        "persistent_pivot_uids": active["pivot_uid"].tolist() if not active.empty else [],
        "candidate_pivot_uids": candidates["pivot_uid"].tolist() if not candidates.empty else [],
        "operational_use": "forbidden",
    }
    return {
        "hypothesis_id": f"persistent_wave_v0_{safe_id(symbol)}_{timeframe}_cut{cut_number:02d}_{as_of.strftime('%Y%m%dT%H%M%S')}",
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": market_group,
        "timeframe": timeframe,
        "higher_timeframe": config.higher_timeframe,
        "cut_number": cut_number,
        "as_of_bar_time": as_of.isoformat(),
        "estimated_current_wave": estimated,
        "confirmed_wave_context": confirmed,
        "next_wave_hypothesis": NEXT_PHASE.get(estimated, "not_available"),
        "hypothesis_status": hypothesis_status(freshness, stability),
        "freshness_status": freshness,
        "wave_stability_status": stability,
        "display_policy": display,
        "invalidation_level": float_or_blank(invalidation),
        "distance_to_invalidation_pct": distance_to_invalidation(current_price, invalidation),
        "last_persistent_pivot_at": timestamp_text(active["pivot_detected_at"].max()) if not active.empty else "",
        "last_candidate_pivot_at": timestamp_text(candidates["pivot_detected_at"].max()) if not candidates.empty else "",
        "persistent_pivot_count": persistent_count,
        "candidate_pivot_count": candidate_count,
        "superseded_pivot_count": int(superseded_recent),
        "wave_event": wave_event,
        "wave_event_reason": event_reason,
        "lookahead_safe": True,
        "is_read_only": True,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "source": "wavecount_persistent_hypothesis_v0",
        "data_origin": "local_ohlc_artifact_progressive_cuts",
        "method_version": "wavecount_persistent_hypothesis_v0",
        "notes": "persistent-pivot wave context only; no_signal_no_filter_no_execution",
        "payload_json": json.dumps(payload, sort_keys=True, default=str),
    }


def phase_from_persistent_sequence(
    active: pd.DataFrame,
    current_price: float | None,
    direction: str,
    stable_enough: bool,
) -> str:
    count = len(active)
    if count == 0:
        return "unknown"
    if not stable_enough:
        return "ambiguous"
    if count == 1:
        return "possible_wave1"
    if count == 2:
        return "possible_wave2"
    if count == 3:
        wave1_extreme = float(active.iloc[1]["pivot_price"])
        return "possible_wave3_active" if beyond(current_price, wave1_extreme, direction) else "possible_wave3_candidate"
    if count == 4:
        return "possible_wave4"
    if count == 5:
        wave3_extreme = float(active.iloc[3]["pivot_price"])
        return "possible_wave5_active" if beyond(current_price, wave3_extreme, direction) else "possible_wave5_candidate"
    if count >= 6 and stable_enough and not recent_density_is_excessive(active):
        return "possible_wave5_active"
    return "ambiguous"


def estimate_with_candidates(
    confirmed: str,
    active: pd.DataFrame,
    candidates: pd.DataFrame,
    current_price: float | None,
    direction: str,
    stable_enough: bool,
) -> str:
    if not stable_enough:
        return "ambiguous"
    if active.empty and not candidates.empty:
        return "possible_wave1"
    if candidates.empty:
        return confirmed
    count = len(active)
    if count == 1:
        return "possible_wave2"
    if count == 2:
        wave1_extreme = float(active.iloc[1]["pivot_price"]) if len(active) > 1 else float(active.iloc[0]["pivot_price"])
        return "possible_wave3_active" if beyond(current_price, wave1_extreme, direction) else "possible_wave3_candidate"
    if count == 3:
        return "possible_wave4"
    if count == 4:
        wave3_extreme = float(active.iloc[3]["pivot_price"]) if len(active) > 3 else float(active.iloc[-1]["pivot_price"])
        return "possible_wave5_active" if beyond(current_price, wave3_extreme, direction) else "possible_wave5_candidate"
    return confirmed


def compute_freshness(
    estimated: str,
    confirmed: str,
    candidate_count: int,
    max_lag: int,
    stable_enough: bool,
    config: PersistentHypothesisConfig,
) -> str:
    if estimated in {"unknown", "not_available"}:
        return "stale"
    if not stable_enough:
        return "manual_review_required"
    if candidate_count and estimated != confirmed:
        return "provisional_estimate"
    if max_lag <= config.max_fresh_lag_bars:
        return "fresh_estimate"
    return "confirmed_late" if max_lag > config.max_acceptable_lag_bars else "acceptable_lag"


def compute_stability(active: pd.DataFrame, candidates: pd.DataFrame, stable_enough: bool, superseded_recent: int) -> str:
    if active.empty and candidates.empty:
        return "insufficient_context"
    if not stable_enough:
        return "manual_review_required"
    if not candidates.empty:
        return "provisional"
    if superseded_recent:
        return "provisional"
    return "stable_enough_for_display"


def compute_display_policy(estimated: str, freshness: str, stability: str) -> str:
    if estimated in {"unknown", "not_available"}:
        return "not_displayable"
    if estimated == "ambiguous" or stability == "manual_review_required" or freshness == "manual_review_required":
        return "manual_review_only"
    if freshness in {"provisional_estimate", "confirmed_late", "acceptable_lag"} or stability == "provisional":
        return "show_with_warning"
    return "displayable_in_dashboard"


def hypothesis_status(freshness: str, stability: str) -> str:
    if stability == "manual_review_required" or freshness == "manual_review_required":
        return "manual_review_required"
    if freshness == "provisional_estimate":
        return "provisional"
    if freshness in {"confirmed_late", "acceptable_lag"}:
        return freshness
    if freshness == "stale":
        return "stale"
    return "forming"


def compute_wave_event(previous: str, current: str, stability: str, candidate_count: int) -> str:
    if stability == "manual_review_required":
        return "manual_review_required"
    if not previous:
        return "initial_hypothesis"
    if current != previous:
        return "wave_phase_changed"
    if candidate_count:
        return "candidate_pivot_seen"
    return "wave_phase_unchanged"


def compute_wave_event_reason(
    *,
    active: pd.DataFrame,
    candidates: pd.DataFrame,
    stable_enough: bool,
    superseded_recent: int,
    max_lag: int,
) -> str:
    parts = []
    if not stable_enough:
        parts.append("unstable_or_non_alternating_pivots")
    if superseded_recent:
        parts.append("recent_superseded_pivots")
    if not candidates.empty:
        parts.append("candidate_pivot_guides_estimate")
    if max_lag:
        parts.append(f"max_lag_bars={max_lag}")
    if not active.empty:
        parts.append(f"persistent_pivots={len(active)}")
    return ";".join(parts) if parts else "persistent_sequence_stable"


def normalise_ohlc(series: pd.DataFrame) -> pd.DataFrame:
    frame = series.copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)


def infer_direction(bars: pd.DataFrame) -> str:
    if len(bars) < 2:
        return "long"
    sample = bars.tail(min(len(bars), 80))
    return "long" if float(sample.iloc[-1]["close"]) >= float(sample.iloc[0]["close"]) else "short"


def structure_alternates(frame: pd.DataFrame) -> bool:
    if frame.empty or len(frame) < 2:
        return True
    values = frame["pivot_type"].astype(str).tolist()
    return all(left != right for left, right in zip(values, values[1:]))


def recent_density_is_excessive(frame: pd.DataFrame) -> bool:
    if len(frame) < 7:
        return False
    times = pd.to_datetime(frame["pivot_extreme_time"], errors="coerce").dropna()
    if len(times) < 7:
        return False
    span_days = max((times.max() - times.min()).days, 1)
    return len(frame) / span_days > 0.09


def max_confirmation_lag(frame: pd.DataFrame) -> int:
    if frame.empty or "confirmation_lag_bars" not in frame.columns:
        return 0
    values = pd.to_numeric(frame["confirmation_lag_bars"], errors="coerce").dropna()
    return int(values.max()) if not values.empty else 0


def invalidation_level(frame: pd.DataFrame, direction: str, estimated: str) -> float | None:
    if frame.empty or estimated in {"unknown", "not_available", "ambiguous"}:
        return None
    if direction == "short":
        highs = frame[frame["pivot_type"] == "high"]
        return float(highs.iloc[-1]["pivot_price"]) if not highs.empty else None
    lows = frame[frame["pivot_type"] == "low"]
    return float(lows.iloc[-1]["pivot_price"]) if not lows.empty else None


def anti_lookahead_safe(bars_used: pd.DataFrame, events: pd.DataFrame, as_of: pd.Timestamp) -> bool:
    if not bars_used.empty and bool((pd.to_datetime(bars_used["time"]) > as_of).any()):
        return False
    if not events.empty and bool((pd.to_datetime(events["pivot_detected_at"], errors="coerce") > as_of).any()):
        return False
    return True


def pivot_uid(symbol: str, timeframe: str, pivot: pd.Series) -> str:
    pivot_type = str(pivot.get("pivot_type", ""))
    extreme_time = timestamp_text(pivot.get("pivot_extreme_time"))
    price = float_or_blank(pivot.get("pivot_extreme_price"))
    return f"{safe_id(symbol)}_{timeframe}_{pivot_type}_{safe_id(extreme_time)}_{safe_id(str(price))}"


def pivot_set_hash(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "empty"
    return "|".join(frame["pivot_uid"].astype(str).tolist())


def recent_superseded_count(registry: dict[str, dict[str, Any]], cut_number: int, tail_cuts: int) -> int:
    count = 0
    lower = max(1, cut_number - tail_cuts + 1)
    for record in registry.values():
        superseded_cut = int(record.get("superseded_cut", 0) or 0)
        if lower <= superseded_cut <= cut_number:
            count += 1
    return count


def transition_type(previous: str, current: str) -> str:
    if not previous:
        return "initial_cut"
    if previous == current:
        return "stable"
    if current in {"ambiguous", "invalidated", "unknown"}:
        return "ambiguous_or_invalidated"
    return "phase_change"


def normalize_hypotheses(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in PERSISTENT_HYPOTHESIS_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=PERSISTENT_HYPOTHESIS_COLUMNS)
    for column in ["lookahead_safe", "is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
        normalized[column] = normalized[column].map(to_bool)
    normalized["is_read_only"] = True
    normalized["can_generate_signal"] = False
    normalized["can_filter_trade"] = False
    normalized["can_execute_order"] = False
    normalized["payload_json"] = normalized["payload_json"].map(validate_payload)
    validate_hard_flags(normalized)
    return normalized


def normalize_pivots(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in PIVOT_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=PIVOT_COLUMNS)
    for column in ["is_persistent", "is_current_candidate", "lookahead_safe"]:
        normalized[column] = normalized[column].map(to_bool)
    return normalized


def validate_hard_flags(frame: pd.DataFrame) -> None:
    if not frame["is_read_only"].map(to_bool).all():
        raise ValueError("is_read_only=false is forbidden")
    for column in ["can_generate_signal", "can_filter_trade", "can_execute_order"]:
        if frame[column].map(to_bool).any():
            raise ValueError(f"{column}=true is forbidden")
    if not frame["lookahead_safe"].map(to_bool).all():
        raise ValueError("lookahead_safe=false blocks persistent hypothesis output")


def build_wave_events(hypotheses: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "hypothesis_id",
        "symbol",
        "timeframe",
        "cut_number",
        "as_of_bar_time",
        "estimated_current_wave",
        "confirmed_wave_context",
        "wave_event",
        "wave_event_reason",
        "display_policy",
    ]
    return hypotheses[columns].copy() if not hypotheses.empty else pd.DataFrame(columns=columns)


def build_comparison_vs_current(config: PersistentHypothesisConfig, hypotheses: pd.DataFrame) -> pd.DataFrame:
    latest = (
        hypotheses.sort_values(["symbol", "timeframe", "cut_number"])
        .groupby(["symbol", "timeframe"], as_index=False)
        .tail(1)
    )
    if not config.current_hypothesis_csv.exists():
        return pd.DataFrame(
            [
                {
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "current_wave_hypothesis_estimated": "not_available",
                    "persistent_estimated_current_wave": row["estimated_current_wave"],
                    "current_display_policy": "not_available",
                    "persistent_display_policy": row["display_policy"],
                    "comparison_note": "current_wave_hypothesis artifact missing",
                }
                for _, row in latest.iterrows()
            ]
        )
    current = pd.read_csv(config.current_hypothesis_csv)
    rows = []
    for _, row in latest.iterrows():
        match = current[(current["symbol"] == row["symbol"]) & (current["timeframe"] == row["timeframe"])]
        current_row = match.iloc[0] if not match.empty else {}
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "current_wave_hypothesis_estimated": current_row.get("estimated_current_wave", "not_available"),
                "persistent_estimated_current_wave": row["estimated_current_wave"],
                "current_display_policy": current_row.get("display_policy", "not_available"),
                "persistent_display_policy": row["display_policy"],
                "current_confirmed_context": current_row.get("confirmed_wave_context", "not_available"),
                "persistent_confirmed_context": row["confirmed_wave_context"],
                "comparison_note": compare_display(
                    current_row.get("display_policy", "not_available"),
                    row["display_policy"],
                ),
            }
        )
    return pd.DataFrame(rows)


def compare_display(old: str, new: str) -> str:
    rank = {"not_available": 0, "not_displayable": 1, "manual_review_only": 2, "show_with_warning": 3, "displayable_in_dashboard": 4}
    if rank.get(str(new), 0) > rank.get(str(old), 0):
        return "persistent_model_less_restrictive"
    if rank.get(str(new), 0) < rank.get(str(old), 0):
        return "persistent_model_more_restrictive"
    return "same_display_class"


def dashboard_display_contract_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"display_policy": "displayable_in_dashboard", "meaning": "Persistent wave context is stable enough to show as read-only context.", "bot_allowed": False},
            {"display_policy": "show_with_warning", "meaning": "Useful but provisional, late or candidate-driven.", "bot_allowed": False},
            {"display_policy": "manual_review_only", "meaning": "Ambiguous or unstable; only manual study views.", "bot_allowed": False},
            {"display_policy": "not_displayable", "meaning": "Insufficient context.", "bot_allowed": False},
        ]
    )


def build_issues_or_risks(
    hypotheses: pd.DataFrame,
    pivots: pd.DataFrame,
    anti: pd.DataFrame,
    stability: pd.DataFrame,
) -> pd.DataFrame:
    latest = latest_hypotheses(hypotheses)
    lookahead_ok = bool(anti["lookahead_safe"].map(to_bool).all()) if not anti.empty else False
    manual_count = int((latest["display_policy"] == "manual_review_only").sum()) if not latest.empty else 0
    warning_count = int((latest["display_policy"] == "show_with_warning").sum()) if not latest.empty else 0
    displayable_count = int((latest["display_policy"] == "displayable_in_dashboard").sum()) if not latest.empty else 0
    wave5_count = int(latest["estimated_current_wave"].astype(str).str.contains("wave5|completed_impulse", regex=True).sum()) if not latest.empty else 0
    persistent_count = int(pivots["is_persistent"].map(to_bool).sum()) if not pivots.empty else 0
    return pd.DataFrame(
        [
            {
                "severity": "blocking" if not lookahead_ok else "info",
                "risk": "lookahead_guard",
                "description": "Anti look-ahead checks passed." if lookahead_ok else "At least one cut uses future data.",
                "recommendation": "Block until fixed." if not lookahead_ok else "Keep as hard guardrail.",
            },
            {
                "severity": "medium" if manual_count else "low",
                "risk": "manual_review_latest",
                "description": f"{manual_count} latest hypotheses remain manual_review_only.",
                "recommendation": "Do not show as clean dashboard context.",
            },
            {
                "severity": "info",
                "risk": "warning_display_latest",
                "description": f"{warning_count} latest hypotheses can be shown only with warning.",
                "recommendation": "Keep warning badges and no bot access.",
            },
            {
                "severity": "info",
                "risk": "displayable_latest",
                "description": f"{displayable_count} latest hypotheses are displayable read-only context.",
                "recommendation": "Require visual review before dashboard.",
            },
            {
                "severity": "medium" if wave5_count >= max(1, len(latest) // 2) else "low",
                "risk": "wave5_dominance",
                "description": f"{wave5_count} latest hypotheses are wave5/completed-style states.",
                "recommendation": "Treat as suspicious until visual review confirms the persistent cycle framing.",
            },
            {
                "severity": "medium" if persistent_count == 0 else "info",
                "risk": "persistent_pivots",
                "description": f"{persistent_count} pivots reached persistence.",
                "recommendation": "If low, adjust persistence/event semantics before dashboard.",
            },
        ]
    )


def decide_next_step(hypotheses: pd.DataFrame, issues: pd.DataFrame) -> str:
    if (issues["severity"] == "blocking").any():
        return "blocked_for_dashboard_wave_context"
    latest = latest_hypotheses(hypotheses)
    if latest.empty:
        return "persistent_hypothesis_v0_still_manual_only"
    displayable = int((latest["display_policy"] == "displayable_in_dashboard").sum())
    warnings = int((latest["display_policy"] == "show_with_warning").sum())
    manual = int((latest["display_policy"] == "manual_review_only").sum())
    wave5_pct = float(latest["estimated_current_wave"].astype(str).str.contains("wave5|completed_impulse", regex=True).mean())
    if wave5_pct >= 0.75:
        return "persistent_hypothesis_v0_needs_more_review"
    if displayable + warnings >= max(1, len(latest) // 2) and manual < len(latest):
        return "persistent_hypothesis_v0_promising_for_visual_review"
    if warnings:
        return "persistent_hypothesis_v0_needs_more_review"
    if manual == len(latest):
        return "persistent_hypothesis_v0_still_manual_only"
    return "needs_deeper_wave_state_machine"


def latest_hypotheses(hypotheses: pd.DataFrame) -> pd.DataFrame:
    if hypotheses.empty:
        return hypotheses
    return (
        hypotheses.sort_values(["symbol", "timeframe", "cut_number"])
        .groupby(["symbol", "timeframe"], as_index=False)
        .tail(1)
    )


def build_run_meta(
    *,
    generated_at: str,
    config: PersistentHypothesisConfig,
    hypotheses: pd.DataFrame,
    pivots: pd.DataFrame,
    anti: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    latest = latest_hypotheses(hypotheses)
    return {
        "generated_at": generated_at,
        "version": "wavecount_persistent_hypothesis_v0",
        "decision": decision,
        "source_csv": str(config.source_csv),
        "symbols": sorted(hypotheses["symbol"].dropna().unique().tolist()),
        "timeframes": sorted(hypotheses["timeframe"].dropna().unique().tolist()),
        "cuts": int(hypotheses["cut_number"].nunique()) if not hypotheses.empty else 0,
        "hypothesis_rows": int(len(hypotheses)),
        "persistent_pivots": int(pivots["is_persistent"].map(to_bool).sum()) if not pivots.empty else 0,
        "latest_estimated_current_wave_distribution": latest["estimated_current_wave"].value_counts().sort_index().to_dict(),
        "latest_display_policy_distribution": latest["display_policy"].value_counts().sort_index().to_dict(),
        "anti_lookahead_passed": bool(anti["lookahead_safe"].map(to_bool).all()) if not anti.empty else False,
        "flags": {
            "is_read_only": True,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
        },
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
    config: PersistentHypothesisConfig,
    hypotheses: pd.DataFrame,
    pivots: pd.DataFrame,
    pivot_events: pd.DataFrame,
    wave_events: pd.DataFrame,
    anti: pd.DataFrame,
    stability: pd.DataFrame,
    transitions: pd.DataFrame,
    comparison: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": output_dir / "persistent_wave_hypothesis.csv",
        "json": output_dir / "persistent_wave_hypothesis.json",
        "persistent_pivots": output_dir / "persistent_pivots.csv",
        "pivot_events": output_dir / "pivot_events.csv",
        "wave_events": output_dir / "wave_events.csv",
        "anti_lookahead_audit": output_dir / "anti_lookahead_audit.csv",
        "stability_audit": output_dir / "stability_audit.csv",
        "transition_audit": output_dir / "transition_audit.csv",
        "comparison": output_dir / "comparison_vs_current_wave_hypothesis.csv",
        "dashboard_display_contract": output_dir / "dashboard_display_contract.csv",
        "issues_or_risks": output_dir / "issues_or_risks.csv",
        "run_meta": output_dir / "run_meta.json",
    }
    hypotheses.to_csv(paths["csv"], index=False)
    paths["json"].write_text(json.dumps(hypotheses.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    pivots.to_csv(paths["persistent_pivots"], index=False)
    pivot_events.to_csv(paths["pivot_events"], index=False)
    wave_events.to_csv(paths["wave_events"], index=False)
    anti.to_csv(paths["anti_lookahead_audit"], index=False)
    stability.to_csv(paths["stability_audit"], index=False)
    transitions.to_csv(paths["transition_audit"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    dashboard_contract.to_csv(paths["dashboard_display_contract"], index=False)
    issues.to_csv(paths["issues_or_risks"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    *,
    config: PersistentHypothesisConfig,
    hypotheses: pd.DataFrame,
    pivots: pd.DataFrame,
    comparison: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    latest = latest_hypotheses(hypotheses)[
        [
            "symbol",
            "timeframe",
            "estimated_current_wave",
            "confirmed_wave_context",
            "freshness_status",
            "wave_stability_status",
            "display_policy",
            "persistent_pivot_count",
            "candidate_pivot_count",
        ]
    ]
    pivot_summary = (
        pivots.groupby(["symbol", "pivot_role"], dropna=False)
        .size()
        .reset_index(name="count")
        if not pivots.empty
        else pd.DataFrame(columns=["symbol", "pivot_role", "count"])
    )
    doc = f"""# WaveCount Persistent Hypothesis v0

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase redisenia `current_wave_hypothesis_v0` sin tocar SQL real ni
operativa. La idea es que una onda actual no dependa solo del numero de pivotes
del ultimo corte: primero se registran pivotes causales, luego se exige
persistencia entre cortes y por ultimo se madura la hipotesis de onda por
eventos.

No es backtest, no mide rentabilidad, no genera senales, no filtra ENBOLSA y no
conecta MT5.

## Hipotesis Latest Por Activo

{markdown_table(latest)}

## Comparacion Contra Current Wave Hypothesis v0

{markdown_table(comparison)}

## Resumen De Pivotes

{markdown_table(pivot_summary)}

## Contrato De Display

{markdown_table(dashboard_contract)}

## Riesgos

{markdown_table(issues)}

## Interpretacion

- `candidate_pivot` y `provisional_pivot` pueden orientar una estimacion, pero
  no cuentan como pivotes persistentes.
- `persistent_pivot` requiere sobrevivir al menos {config.min_persistence_cuts}
  cortes.
- `completed_impulse_candidate` no se declara por simple cantidad de pivotes.
- Si hay supersedencias recientes o alternancia rota, la hipotesis queda
  `ambiguous`/`manual_review_only`.
- Cualquier fila mantiene `can_generate_signal=false`, `can_filter_trade=false`
  y `can_execute_order=false`.

## Pendiente Antes De SQL/Dashboard

- Revision visual de los casos que queden `show_with_warning` o
  `displayable_in_dashboard`.
- Ajustar, si procede, los umbrales de persistencia sin usar PnL.
- Si sigue predominando `manual_review_only`, valorar una maquina de estados
  mas profunda o limitar WaveCount a pestana manual.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_PERSISTENT_HYPOTHESIS_V0.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-operative persistent wave hypotheses from local OHLC cuts.")
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--higher-timeframe", default=DEFAULT_HIGHER_TIMEFRAME)
    parser.add_argument("--max-symbols", type=int, default=4)
    parser.add_argument("--cut-count", type=int, default=10)
    parser.add_argument("--min-bars-first-cut", type=int, default=40)
    parser.add_argument("--min-persistence-cuts", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    symbols = tuple(symbol.strip() for symbol in args.symbols.split(",") if symbol.strip())
    result = build_persistent_hypothesis(
        PersistentHypothesisConfig(
            source_csv=args.source_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            symbols=symbols,
            timeframe=args.timeframe,
            higher_timeframe=args.higher_timeframe,
            max_symbols=args.max_symbols,
            cut_count=args.cut_count,
            min_bars_first_cut=args.min_bars_first_cut,
            min_persistence_cuts=args.min_persistence_cuts,
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
