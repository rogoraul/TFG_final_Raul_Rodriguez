from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import (
    DEFAULT_HIGHER_TIMEFRAME,
    DEFAULT_SOURCE_CSV,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAME,
    load_source_ohlc,
)
from backtests.tfg.build_wavecount_live_parameter_review import markdown_table
from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_pivots import detect_causal_pivots
from backtests.wavecount.wavecount_structure import StructuralPivotConfig, build_structural_pivots


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_current_hypothesis_v0_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_CURRENT_HYPOTHESIS_V0.md")

CURRENT_WAVE_COLUMNS = [
    "hypothesis_id",
    "generated_at",
    "as_of_bar_time",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "source",
    "data_origin",
    "structure_family",
    "direction",
    "estimated_current_wave",
    "confirmed_wave_context",
    "next_wave_hypothesis",
    "hypothesis_status",
    "freshness_status",
    "wave_stability_status",
    "wave_confidence_bucket",
    "display_policy",
    "raw_pivot_count",
    "tentative_pivot_count",
    "confirmed_pivot_count",
    "structural_pivot_count",
    "persistent_structural_pivot_count",
    "superseded_pivot_count",
    "uses_tentative_pivot",
    "tentative_pivots_treated_as_confirmed",
    "last_tentative_pivot_at",
    "last_confirmed_pivot_at",
    "confirmation_lag_bars",
    "lookahead_safe",
    "evidence_window_start",
    "evidence_window_end",
    "current_price",
    "invalidation_level",
    "distance_to_invalidation_pct",
    "dashboard_warning",
    "is_read_only",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
    "method_version",
    "source_artifacts",
    "notes",
    "payload_json",
]

PHASE_ORDER = [
    "possible_wave1",
    "possible_wave2",
    "possible_wave3_candidate",
    "possible_wave3_active",
    "possible_wave4",
    "possible_wave5_candidate",
    "possible_wave5_active",
    "completed_impulse_candidate",
]

CORRECTION_ORDER = [
    "possible_waveA",
    "possible_waveB",
    "possible_waveC_candidate",
    "possible_waveC_active",
    "completed_abc_candidate",
]

NEXT_PHASE = {
    "possible_wave1": "possible_wave2",
    "possible_wave2": "possible_wave3_candidate",
    "possible_wave3_candidate": "possible_wave3_active",
    "possible_wave3_active": "possible_wave4",
    "possible_wave4": "possible_wave5_candidate",
    "possible_wave5_candidate": "possible_wave5_active",
    "possible_wave5_active": "completed_impulse_candidate",
    "completed_impulse_candidate": "possible_waveA",
    "possible_waveA": "possible_waveB",
    "possible_waveB": "possible_waveC_candidate",
    "possible_waveC_candidate": "possible_waveC_active",
    "possible_waveC_active": "completed_abc_candidate",
    "completed_abc_candidate": "possible_wave1",
    "unknown": "not_available",
    "ambiguous": "manual_review",
    "invalidated": "not_available",
    "not_available": "not_available",
}


@dataclass(frozen=True)
class CurrentWaveHypothesisConfig:
    source_csv: Path = DEFAULT_SOURCE_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    timeframe: str = DEFAULT_TIMEFRAME
    higher_timeframe: str = DEFAULT_HIGHER_TIMEFRAME
    max_symbols: int = 4
    as_of_bar_time: str | None = None
    structure_family: str = "impulse"
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
    max_fresh_lag_bars: int = 4
    max_acceptable_lag_bars: int = 8
    allow_completed_impulse_without_persistence: bool = False


@dataclass(frozen=True)
class CurrentWaveHypothesisResult:
    hypotheses: pd.DataFrame
    schema: pd.DataFrame
    hypothesis_state_model: pd.DataFrame
    pivot_role_model: pd.DataFrame
    anti_lookahead_audit: pd.DataFrame
    stability_audit: pd.DataFrame
    dashboard_display_contract: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_current_wave_hypothesis(
    config: CurrentWaveHypothesisConfig | None = None,
) -> CurrentWaveHypothesisResult:
    config = config or CurrentWaveHypothesisConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source = load_source_ohlc(config.source_csv)
    selected = select_series(source, config)

    rows: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    for (market_group, symbol, timeframe), series in selected.items():
        row, anti, stability = build_series_hypothesis(
            config=config,
            generated_at=generated_at,
            market_group=market_group,
            symbol=symbol,
            timeframe=timeframe,
            series=series,
        )
        rows.append(row)
        anti_rows.append(anti)
        stability_rows.append(stability)

    hypotheses = normalize_hypothesis_frame(pd.DataFrame(rows))
    anti = pd.DataFrame(anti_rows)
    stability = pd.DataFrame(stability_rows)
    schema = schema_frame()
    state_model = hypothesis_state_model_frame()
    pivot_model = pivot_role_model_frame()
    dashboard_contract = dashboard_display_contract_frame()
    issues = build_issues_or_risks(hypotheses, anti, stability)
    decision = decide_next_step(hypotheses, anti, stability, issues)
    run_meta = build_run_meta(
        generated_at=generated_at,
        config=config,
        hypotheses=hypotheses,
        anti=anti,
        stability=stability,
        decision=decision,
    )
    written = write_outputs(
        config=config,
        hypotheses=hypotheses,
        schema=schema,
        state_model=state_model,
        pivot_model=pivot_model,
        anti=anti,
        stability=stability,
        dashboard_contract=dashboard_contract,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(
        config=config,
        hypotheses=hypotheses,
        state_model=state_model,
        pivot_model=pivot_model,
        dashboard_contract=dashboard_contract,
        issues=issues,
        decision=decision,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_CURRENT_HYPOTHESIS_V0.md"
    return CurrentWaveHypothesisResult(
        hypotheses=hypotheses,
        schema=schema,
        hypothesis_state_model=state_model,
        pivot_role_model=pivot_model,
        anti_lookahead_audit=anti,
        stability_audit=stability,
        dashboard_display_contract=dashboard_contract,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def select_series(source: pd.DataFrame, config: CurrentWaveHypothesisConfig) -> dict[tuple[str, str, str], pd.DataFrame]:
    frame = source[source["timeframe"].astype(str).str.upper() == config.timeframe.upper()].copy()
    preferred = [symbol for symbol in config.symbols if symbol in set(frame["symbol"])]
    if len(preferred) < min(config.max_symbols, len(config.symbols)):
        for _, item in frame.groupby(["market_group", "symbol"], dropna=False).size().reset_index(name="rows").iterrows():
            symbol = str(item["symbol"])
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
        raise ValueError("no usable OHLC series selected for current_wave_hypothesis_v0")
    return selected


def build_series_hypothesis(
    *,
    config: CurrentWaveHypothesisConfig,
    generated_at: str,
    market_group: str,
    symbol: str,
    timeframe: str,
    series: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    as_of = pd.Timestamp(config.as_of_bar_time) if config.as_of_bar_time else pd.Timestamp(series["time"].max())
    bars_all = normalise_ohlc(series)
    bars_used = bars_all[bars_all["time"] <= as_of].copy()
    ohlc = bars_used.set_index("time")[["open", "high", "low", "close"]]
    raw = detect_causal_pivots(ohlc, config.pivot_config, symbol=symbol, timeframe=timeframe) if not ohlc.empty else pd.DataFrame()
    events = raw[raw["pivot_state"] != "no_pivot"].copy() if not raw.empty else pd.DataFrame()
    confirmed = events[events["is_confirmed"].astype(bool)].copy() if not events.empty else pd.DataFrame()
    structural_result = build_structural_pivots(confirmed, config.structural_config) if not confirmed.empty else empty_structural_result()
    structural = structural_result["structural_pivots"].copy()
    discarded = structural_result["discarded_minor_pivots"].copy()
    tentative = tentative_pivots_after_last_structural(events, structural)
    current_price = float(bars_used.iloc[-1]["close"]) if not bars_used.empty else None
    direction = infer_direction(bars_used)
    confirmed_context_raw = confirmed_wave_context(structural, current_price, direction, config.structure_family, config)
    estimated_wave_raw = estimated_current_wave(
        structural=structural,
        tentative=tentative,
        current_price=current_price,
        direction=direction,
        family=config.structure_family,
        config=config,
    )
    max_lag = max_confirmation_lag(structural)
    unstable = is_unstable(events, structural, discarded)
    confirmed_context = demote_unstable_context(confirmed_context_raw, unstable, structural)
    estimated_wave = demote_unstable_context(estimated_wave_raw, unstable, structural)
    freshness = freshness_status(estimated_wave, confirmed_context, tentative, max_lag, unstable, config)
    stability_status = wave_stability_status(events, structural, discarded, unstable)
    display = display_policy(freshness, stability_status, estimated_wave)
    confidence = confidence_bucket(estimated_wave, confirmed_context, tentative, structural, unstable)
    invalidation = invalidation_level(structural, direction, estimated_wave)
    lookahead_safe = anti_lookahead_safe(bars_used, events, as_of)
    hypothesis_id = f"current_wave_hypothesis_v0_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}"
    payload = {
        "pivot_config": asdict(config.pivot_config),
        "structural_config": asdict(config.structural_config),
        "raw_pivot_states": events["pivot_state"].value_counts().to_dict() if not events.empty else {},
        "tentative_pivot_ids": tentative.index.astype(str).tolist() if not tentative.empty else [],
        "confirmed_wave_context_raw": confirmed_context_raw,
        "estimated_current_wave_raw": estimated_wave_raw,
        "confirmed_wave_context": confirmed_context,
        "estimated_current_wave": estimated_wave,
        "operational_use": "forbidden",
    }
    row = {
        "hypothesis_id": hypothesis_id,
        "generated_at": generated_at,
        "as_of_bar_time": as_of.isoformat(),
        "symbol": symbol,
        "market_group": market_group,
        "timeframe": timeframe,
        "higher_timeframe": config.higher_timeframe,
        "source": "current_wave_hypothesis_v0",
        "data_origin": "local_ohlc_artifact",
        "structure_family": config.structure_family,
        "direction": direction,
        "estimated_current_wave": estimated_wave,
        "confirmed_wave_context": confirmed_context,
        "next_wave_hypothesis": NEXT_PHASE.get(estimated_wave, "not_available"),
        "hypothesis_status": hypothesis_status(freshness, stability_status),
        "freshness_status": freshness,
        "wave_stability_status": stability_status,
        "wave_confidence_bucket": confidence,
        "display_policy": display,
        "raw_pivot_count": int(len(events)),
        "tentative_pivot_count": int(len(tentative)),
        "confirmed_pivot_count": int(len(confirmed)),
        "structural_pivot_count": int(len(structural)),
        "persistent_structural_pivot_count": int(len(structural)),
        "superseded_pivot_count": int(len(discarded)),
        "uses_tentative_pivot": bool(not tentative.empty and estimated_wave != confirmed_context),
        "tentative_pivots_treated_as_confirmed": False,
        "last_tentative_pivot_at": timestamp_text(tentative["pivot_detected_at"].max()) if not tentative.empty else "",
        "last_confirmed_pivot_at": timestamp_text(structural["pivot_detected_at"].max()) if not structural.empty else "",
        "confirmation_lag_bars": int(max_lag),
        "lookahead_safe": lookahead_safe,
        "evidence_window_start": timestamp_text(bars_used["time"].min()) if not bars_used.empty else "",
        "evidence_window_end": timestamp_text(bars_used["time"].max()) if not bars_used.empty else "",
        "current_price": float_or_blank(current_price),
        "invalidation_level": float_or_blank(invalidation),
        "distance_to_invalidation_pct": distance_to_invalidation(current_price, invalidation),
        "dashboard_warning": dashboard_warning(freshness, stability_status, estimated_wave),
        "is_read_only": True,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "method_version": "current_wave_hypothesis_v0",
        "source_artifacts": str(config.source_csv),
        "notes": "estimated current wave is read-only context; no_signal_no_filter_no_execution",
        "payload_json": json.dumps(payload, sort_keys=True, default=str),
    }
    anti = {
        "hypothesis_id": hypothesis_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "bars_total": int(len(bars_all)),
        "bars_used": int(len(bars_used)),
        "bars_after_as_of_ignored": int(len(bars_all) - len(bars_used)),
        "latest_event_detected_at": timestamp_text(events["pivot_detected_at"].max()) if not events.empty else "",
        "latest_event_detected_at_lte_as_of": True
        if events.empty
        else bool(pd.Timestamp(events["pivot_detected_at"].max()) <= as_of),
        "evidence_window_end_lte_as_of": True if bars_used.empty else bool(pd.Timestamp(bars_used["time"].max()) <= as_of),
        "lookahead_safe": lookahead_safe,
    }
    stability = {
        "hypothesis_id": hypothesis_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of_bar_time": as_of.isoformat(),
        "raw_pivots": int(len(events)),
        "tentative_pivots": int(len(tentative)),
        "confirmed_pivots": int(len(confirmed)),
        "structural_pivots": int(len(structural)),
        "discarded_or_superseded_pivots": int(len(discarded)),
        "raw_to_structural_ratio": round(float(len(events)) / max(float(len(structural)), 1.0), 4),
        "unstable_flag": bool(unstable),
        "wave_stability_status": stability_status,
        "freshness_status": freshness,
        "estimated_current_wave": estimated_wave,
        "confirmed_wave_context": confirmed_context,
        "manual_review_required": stability_status == "manual_review_required",
    }
    return row, anti, stability


def normalise_ohlc(series: pd.DataFrame) -> pd.DataFrame:
    frame = series.copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)


def empty_structural_result() -> dict[str, pd.DataFrame]:
    return {
        "structural_pivots": pd.DataFrame(),
        "discarded_minor_pivots": pd.DataFrame(),
        "structure_summary": pd.DataFrame(),
    }


def tentative_pivots_after_last_structural(events: pd.DataFrame, structural: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    candidates = events[events["is_candidate"].astype(bool)].copy() if "is_candidate" in events.columns else pd.DataFrame()
    if candidates.empty:
        return candidates
    if structural.empty:
        return candidates.tail(1)
    last_confirmed_at = pd.Timestamp(structural["pivot_detected_at"].max())
    return candidates[pd.to_datetime(candidates["pivot_detected_at"], errors="coerce") >= last_confirmed_at].tail(1)


def confirmed_wave_context(
    structural: pd.DataFrame,
    current_price: float | None,
    direction: str,
    family: str,
    config: CurrentWaveHypothesisConfig,
) -> str:
    if structural.empty:
        return "unknown"
    count = len(structural)
    if family == "correction":
        return correction_phase_from_count(count, structural, current_price, direction, config)
    return impulse_phase_from_count(count, structural, current_price, direction, config)


def estimated_current_wave(
    *,
    structural: pd.DataFrame,
    tentative: pd.DataFrame,
    current_price: float | None,
    direction: str,
    family: str,
    config: CurrentWaveHypothesisConfig,
) -> str:
    confirmed = confirmed_wave_context(structural, current_price, direction, family, config)
    if structural.empty:
        return "possible_wave1" if family == "impulse" and not tentative.empty else confirmed
    if family == "correction":
        return estimate_correction_wave(structural, tentative, current_price, direction, config)
    return estimate_impulse_wave(structural, tentative, current_price, direction, config)


def impulse_phase_from_count(
    count: int,
    structural: pd.DataFrame,
    current_price: float | None,
    direction: str,
    config: CurrentWaveHypothesisConfig,
) -> str:
    if count <= 1:
        return "possible_wave1"
    if count == 2:
        return "possible_wave2"
    if count == 3:
        wave1_extreme = float(structural.iloc[1]["pivot_extreme_price"])
        return "possible_wave3_active" if beyond(current_price, wave1_extreme, direction) else "possible_wave3_candidate"
    if count == 4:
        return "possible_wave4"
    if count == 5:
        wave3_extreme = float(structural.iloc[3]["pivot_extreme_price"])
        return "possible_wave5_active" if beyond(current_price, wave3_extreme, direction) else "possible_wave5_candidate"
    if config.allow_completed_impulse_without_persistence and structure_alternates(structural):
        return "completed_impulse_candidate"
    return "possible_wave5_active"


def correction_phase_from_count(
    count: int,
    structural: pd.DataFrame,
    current_price: float | None,
    direction: str,
    config: CurrentWaveHypothesisConfig,
) -> str:
    if count <= 1:
        return "possible_waveA"
    if count == 2:
        return "possible_waveB"
    if count == 3:
        wave_a_extreme = float(structural.iloc[1]["pivot_extreme_price"])
        return "possible_waveC_active" if beyond(current_price, wave_a_extreme, direction) else "possible_waveC_candidate"
    return "completed_abc_candidate" if config.allow_completed_impulse_without_persistence else "possible_waveC_active"


def estimate_impulse_wave(
    structural: pd.DataFrame,
    tentative: pd.DataFrame,
    current_price: float | None,
    direction: str,
    config: CurrentWaveHypothesisConfig,
) -> str:
    count = len(structural)
    confirmed = impulse_phase_from_count(count, structural, current_price, direction, config)
    if count == 1 and not tentative.empty:
        return "possible_wave2"
    if count == 2:
        wave1_extreme = float(structural.iloc[1]["pivot_extreme_price"]) if len(structural) > 1 else float(structural.iloc[0]["pivot_extreme_price"])
        return "possible_wave3_active" if beyond(current_price, wave1_extreme, direction) else "possible_wave3_candidate"
    if count == 3 and not tentative.empty:
        return "possible_wave4"
    if count == 4:
        wave3_extreme = float(structural.iloc[3]["pivot_extreme_price"]) if len(structural) > 3 else float(structural.iloc[-1]["pivot_extreme_price"])
        return "possible_wave5_active" if beyond(current_price, wave3_extreme, direction) else "possible_wave5_candidate"
    if count >= 5:
        return "possible_wave5_active"
    return confirmed


def estimate_correction_wave(
    structural: pd.DataFrame,
    tentative: pd.DataFrame,
    current_price: float | None,
    direction: str,
    config: CurrentWaveHypothesisConfig,
) -> str:
    count = len(structural)
    if count == 1 and not tentative.empty:
        return "possible_waveB"
    if count == 2:
        wave_a_extreme = float(structural.iloc[1]["pivot_extreme_price"]) if len(structural) > 1 else float(structural.iloc[0]["pivot_extreme_price"])
        return "possible_waveC_active" if beyond(current_price, wave_a_extreme, direction) else "possible_waveC_candidate"
    if count >= 3:
        return "possible_waveC_active"
    return correction_phase_from_count(count, structural, current_price, direction, config)


def infer_direction(bars: pd.DataFrame) -> str:
    if len(bars) < 2:
        return "long"
    sample = bars.tail(min(len(bars), 80))
    return "long" if float(sample.iloc[-1]["close"]) >= float(sample.iloc[0]["close"]) else "short"


def beyond(current_price: float | None, reference_price: float, direction: str) -> bool:
    if current_price is None:
        return False
    return current_price < reference_price if direction == "short" else current_price > reference_price


def max_confirmation_lag(structural: pd.DataFrame) -> int:
    if structural.empty or "confirmation_lag_bars" not in structural.columns:
        return 0
    values = pd.to_numeric(structural["confirmation_lag_bars"], errors="coerce").dropna()
    return int(values.max()) if not values.empty else 0


def demote_unstable_context(state: str, unstable: bool, structural: pd.DataFrame) -> str:
    if not unstable:
        return state
    if len(structural) >= 5 or state in {"possible_wave5_candidate", "possible_wave5_active", "completed_impulse_candidate"}:
        return "ambiguous"
    return state


def is_unstable(events: pd.DataFrame, structural: pd.DataFrame, discarded: pd.DataFrame) -> bool:
    if structural.empty:
        return False
    raw_to_structural = float(len(events)) / max(float(len(structural)), 1.0)
    replacements = 0
    if not discarded.empty and "reason" in discarded.columns:
        replacements = int(discarded["reason"].astype(str).str.contains("superseded|same-type", case=False, regex=True).sum())
    return raw_to_structural > 7.5 or replacements >= 2 or not structure_alternates(structural)


def structure_alternates(structural: pd.DataFrame) -> bool:
    if structural.empty or "pivot_type" not in structural.columns or len(structural) < 2:
        return True
    values = structural["pivot_type"].astype(str).tolist()
    return all(left != right for left, right in zip(values, values[1:]))


def freshness_status(
    estimated: str,
    confirmed: str,
    tentative: pd.DataFrame,
    max_lag: int,
    unstable: bool,
    config: CurrentWaveHypothesisConfig,
) -> str:
    if estimated in {"unknown", "not_available"}:
        return "stale"
    if unstable:
        return "manual_review_required"
    if not tentative.empty and estimated != confirmed:
        return "provisional_estimate"
    if max_lag <= config.max_fresh_lag_bars:
        return "fresh_estimate"
    if max_lag <= config.max_acceptable_lag_bars:
        return "confirmed_late"
    return "confirmed_late"


def wave_stability_status(events: pd.DataFrame, structural: pd.DataFrame, discarded: pd.DataFrame, unstable: bool) -> str:
    if structural.empty:
        return "insufficient_context"
    if unstable:
        return "manual_review_required"
    if not discarded.empty:
        return "provisional"
    return "stable_enough_for_display"


def confidence_bucket(estimated: str, confirmed: str, tentative: pd.DataFrame, structural: pd.DataFrame, unstable: bool) -> str:
    if estimated in {"unknown", "not_available", "ambiguous"}:
        return "low"
    if unstable:
        return "manual_review"
    if not tentative.empty and estimated != confirmed:
        return "low_provisional"
    if len(structural) >= 3:
        return "medium"
    return "low"


def display_policy(freshness: str, stability_status: str, estimated: str) -> str:
    if estimated in {"unknown", "not_available"}:
        return "not_displayable"
    if stability_status == "manual_review_required" or freshness == "manual_review_required":
        return "manual_review_only"
    if freshness in {"provisional_estimate", "confirmed_late"}:
        return "show_with_warning"
    return "displayable_in_dashboard"


def hypothesis_status(freshness: str, stability_status: str) -> str:
    if stability_status == "manual_review_required" or freshness == "manual_review_required":
        return "manual_review_required"
    if freshness == "provisional_estimate":
        return "provisional"
    if freshness == "confirmed_late":
        return "confirmed_late"
    if freshness == "stale":
        return "stale"
    return "forming"


def invalidation_level(structural: pd.DataFrame, direction: str, estimated: str) -> float | None:
    if structural.empty or estimated in {"unknown", "not_available"}:
        return None
    if direction == "short":
        highs = structural[structural["pivot_type"] == "high"]
        return float(highs.iloc[-1]["pivot_extreme_price"]) if not highs.empty else None
    lows = structural[structural["pivot_type"] == "low"]
    return float(lows.iloc[-1]["pivot_extreme_price"]) if not lows.empty else None


def anti_lookahead_safe(bars_used: pd.DataFrame, events: pd.DataFrame, as_of: pd.Timestamp) -> bool:
    if not bars_used.empty and bool((pd.to_datetime(bars_used["time"]) > as_of).any()):
        return False
    if not events.empty and bool((pd.to_datetime(events["pivot_detected_at"], errors="coerce") > as_of).any()):
        return False
    return True


def dashboard_warning(freshness: str, stability_status: str, estimated: str) -> str:
    if estimated in {"unknown", "not_available"}:
        return "not_enough_context"
    if stability_status == "manual_review_required":
        return "unstable_pivots_manual_review"
    if freshness == "provisional_estimate":
        return "estimated_from_tentative_pivot"
    if freshness == "confirmed_late":
        return "confirmed_late_not_fresh"
    return "read_only_context"


def distance_to_invalidation(current_price: float | None, level: float | None) -> str | float:
    if current_price is None or level is None or current_price == 0:
        return ""
    return round(abs(current_price - level) / abs(current_price), 6)


def normalize_hypothesis_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in CURRENT_WAVE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=CURRENT_WAVE_COLUMNS)
    for column in ["is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order", "lookahead_safe", "uses_tentative_pivot", "tentative_pivots_treated_as_confirmed"]:
        normalized[column] = normalized[column].map(to_bool)
    normalized["is_read_only"] = True
    normalized["can_generate_signal"] = False
    normalized["can_filter_trade"] = False
    normalized["can_execute_order"] = False
    normalized["tentative_pivots_treated_as_confirmed"] = False
    normalized["payload_json"] = normalized["payload_json"].map(validate_payload)
    validate_hard_flags(normalized)
    return normalized


def validate_hard_flags(frame: pd.DataFrame) -> None:
    if not frame["is_read_only"].map(to_bool).all():
        raise ValueError("is_read_only=false is forbidden")
    for column in ["can_generate_signal", "can_filter_trade", "can_execute_order"]:
        if frame[column].map(to_bool).any():
            raise ValueError(f"{column}=true is forbidden")
    if frame["tentative_pivots_treated_as_confirmed"].map(to_bool).any():
        raise ValueError("tentative pivots must not be treated as confirmed")


def schema_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "column_name": column,
                "required": True,
                "purpose": schema_purpose(column),
            }
            for column in CURRENT_WAVE_COLUMNS
        ]
    )


def hypothesis_state_model_frame() -> pd.DataFrame:
    rows = []
    for state in PHASE_ORDER + CORRECTION_ORDER + ["unknown", "ambiguous", "invalidated", "not_available"]:
        rows.append(
            {
                "wave_state": state,
                "minimum_evidence": minimum_evidence(state),
                "can_use_tentative_pivot": state not in {"completed_impulse_candidate", "completed_abc_candidate", "invalidated"},
                "requires_confirmed_pivot": state in {"confirmed_wave_context", "completed_impulse_candidate", "completed_abc_candidate"},
                "dashboard_warning": "show_with_warning_if_provisional_or_late",
                "can_be_estimated_current_wave": state not in {"not_available"},
                "can_be_confirmed_wave_context": state not in {"ambiguous"},
                "operational_use": "forbidden",
            }
        )
    return pd.DataFrame(rows)


def pivot_role_model_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"pivot_role": "raw_pivot", "meaning": "Any causal pivot/candidate event emitted at detection time.", "may_drive_estimate": True, "may_confirm_wave": False},
            {"pivot_role": "tentative_pivot", "meaning": "Candidate pivot visible before confirmation latency completes.", "may_drive_estimate": True, "may_confirm_wave": False},
            {"pivot_role": "confirmed_pivot", "meaning": "Pivot confirmed causally at pivot_detected_at.", "may_drive_estimate": True, "may_confirm_wave": True},
            {"pivot_role": "persistent_structural_pivot", "meaning": "Confirmed pivot surviving structural compression.", "may_drive_estimate": True, "may_confirm_wave": True},
            {"pivot_role": "superseded_pivot", "meaning": "Pivot discarded/replaced by structural compression.", "may_drive_estimate": False, "may_confirm_wave": False},
        ]
    )


def dashboard_display_contract_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"display_policy": "displayable_in_dashboard", "meaning": "Readable current estimate with no major warning.", "required_badge": "read_only_context", "bot_allowed": False},
            {"display_policy": "show_with_warning", "meaning": "Useful context but provisional or late.", "required_badge": "warning", "bot_allowed": False},
            {"display_policy": "manual_review_only", "meaning": "Unstable context; show only in manual review/research views.", "required_badge": "manual_review", "bot_allowed": False},
            {"display_policy": "not_displayable", "meaning": "Not enough context to display as wave state.", "required_badge": "not_available", "bot_allowed": False},
        ]
    )


def build_issues_or_risks(hypotheses: pd.DataFrame, anti: pd.DataFrame, stability: pd.DataFrame) -> pd.DataFrame:
    rows = []
    lookahead_ok = bool(anti["lookahead_safe"].all()) if not anti.empty else False
    manual_count = int((hypotheses["display_policy"] == "manual_review_only").sum()) if not hypotheses.empty else 0
    provisional_count = int((hypotheses["freshness_status"] == "provisional_estimate").sum()) if not hypotheses.empty else 0
    late_count = int((hypotheses["freshness_status"] == "confirmed_late").sum()) if not hypotheses.empty else 0
    rows.append(
        {
            "severity": "blocking" if not lookahead_ok else "info",
            "risk": "lookahead_guard",
            "description": "Anti look-ahead checks passed." if lookahead_ok else "At least one hypothesis uses future data.",
            "recommendation": "Block until fixed." if not lookahead_ok else "Keep as hard guardrail.",
        }
    )
    rows.append(
        {
            "severity": "medium" if manual_count else "low",
            "risk": "manual_review_required",
            "description": f"{manual_count} hypotheses require manual review.",
            "recommendation": "Do not show manual-review rows as clean dashboard context.",
        }
    )
    rows.append(
        {
            "severity": "low",
            "risk": "provisional_estimates",
            "description": f"{provisional_count} hypotheses use tentative current-wave evidence.",
            "recommendation": "Show with warning; never treat as confirmation.",
        }
    )
    rows.append(
        {
            "severity": "medium" if late_count else "low",
            "risk": "confirmed_late_context",
            "description": f"{late_count} hypotheses are confirmed late.",
            "recommendation": "Separate confirmed_wave_context from estimated_current_wave.",
        }
    )
    return pd.DataFrame(rows)


def decide_next_step(hypotheses: pd.DataFrame, anti: pd.DataFrame, stability: pd.DataFrame, issues: pd.DataFrame) -> str:
    if (issues["severity"] == "blocking").any():
        return "blocked_for_dashboard_wave_context"
    if hypotheses.empty:
        return "late_context_only_still"
    estimated_present = bool((hypotheses["estimated_current_wave"] != "unknown").any())
    manual_pct = float((hypotheses["display_policy"] == "manual_review_only").mean())
    warning_pct = float((hypotheses["display_policy"] == "show_with_warning").mean())
    if estimated_present and manual_pct <= 0.5:
        return "current_wave_hypothesis_v0_promising" if warning_pct <= 0.75 else "current_wave_hypothesis_v0_needs_more_review"
    if estimated_present:
        return "current_wave_hypothesis_v0_needs_more_review"
    return "needs_deeper_pivot_redesign"


def build_run_meta(
    *,
    generated_at: str,
    config: CurrentWaveHypothesisConfig,
    hypotheses: pd.DataFrame,
    anti: pd.DataFrame,
    stability: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "current_wave_hypothesis_v0",
        "decision": decision,
        "source_csv": str(config.source_csv),
        "symbols": sorted(hypotheses["symbol"].dropna().unique().tolist()),
        "timeframes": sorted(hypotheses["timeframe"].dropna().unique().tolist()),
        "rows": int(len(hypotheses)),
        "estimated_current_wave_distribution": hypotheses["estimated_current_wave"].value_counts().sort_index().to_dict(),
        "confirmed_wave_context_distribution": hypotheses["confirmed_wave_context"].value_counts().sort_index().to_dict(),
        "freshness_status_distribution": hypotheses["freshness_status"].value_counts().sort_index().to_dict(),
        "display_policy_distribution": hypotheses["display_policy"].value_counts().sort_index().to_dict(),
        "anti_lookahead_passed": bool(anti["lookahead_safe"].all()) if not anti.empty else False,
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
        "limitations": [
            "Prototype only; no SQL, dashboard or operational use.",
            "estimated_current_wave is contextual and may be provisional.",
            "No edge, PnL or strategy validation is claimed.",
        ],
    }


def write_outputs(
    *,
    config: CurrentWaveHypothesisConfig,
    hypotheses: pd.DataFrame,
    schema: pd.DataFrame,
    state_model: pd.DataFrame,
    pivot_model: pd.DataFrame,
    anti: pd.DataFrame,
    stability: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": output_dir / "current_wave_hypothesis.csv",
        "json": output_dir / "current_wave_hypothesis.json",
        "run_meta": output_dir / "run_meta.json",
        "schema": output_dir / "schema.csv",
        "hypothesis_state_model": output_dir / "hypothesis_state_model.csv",
        "pivot_role_model": output_dir / "pivot_role_model.csv",
        "anti_lookahead_audit": output_dir / "anti_lookahead_audit.csv",
        "stability_audit": output_dir / "stability_audit.csv",
        "dashboard_display_contract": output_dir / "dashboard_display_contract.csv",
        "issues_or_risks": output_dir / "issues_or_risks.csv",
    }
    hypotheses.to_csv(paths["csv"], index=False)
    paths["json"].write_text(json.dumps(hypotheses.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    schema.to_csv(paths["schema"], index=False)
    state_model.to_csv(paths["hypothesis_state_model"], index=False)
    pivot_model.to_csv(paths["pivot_role_model"], index=False)
    anti.to_csv(paths["anti_lookahead_audit"], index=False)
    stability.to_csv(paths["stability_audit"], index=False)
    dashboard_contract.to_csv(paths["dashboard_display_contract"], index=False)
    issues.to_csv(paths["issues_or_risks"], index=False)
    return paths


def write_docs(
    *,
    config: CurrentWaveHypothesisConfig,
    hypotheses: pd.DataFrame,
    state_model: pd.DataFrame,
    pivot_model: pd.DataFrame,
    dashboard_contract: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    phase_summary = hypotheses[
        [
            "symbol",
            "timeframe",
            "estimated_current_wave",
            "confirmed_wave_context",
            "freshness_status",
            "wave_stability_status",
            "display_policy",
            "dashboard_warning",
        ]
    ]
    doc = f"""# WaveCount Current Hypothesis v0

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase abre una capa nueva para responder mejor a la pregunta: "en que onda
esta este activo ahora?". La clave es separar `estimated_current_wave` de
`confirmed_wave_context`. La primera puede ser provisional y usar pivotes
tentativos; la segunda solo resume estructura confirmada tarde.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
filtra ENBOLSA, no se ejecutan backtests y no se conecta MT5.

## Hipotesis Por Activo

{markdown_table(phase_summary)}

## Cambio Frente A WaveCount Live Context v0

- `estimated_current_wave` es la lectura util para dashboard, siempre con
  warning si es provisional o tardia.
- `confirmed_wave_context` conserva la lectura confirmada tarde.
- Los pivotes tentativos pueden orientar la estimacion, pero nunca se tratan
  como confirmados.
- `completed_impulse_candidate` queda protegido: no se promueve solo por numero
  de pivotes si no hay persistencia suficiente.

## Modelo De Estados

{markdown_table(state_model)}

## Modelo De Pivotes

{markdown_table(pivot_model)}

## Contrato De Display

{markdown_table(dashboard_contract)}

## Riesgos

{markdown_table(issues)}

## Que Falta Antes De SQL/Dashboard

- Revisar visualmente las hipotesis actuales por simbolo.
- Definir si `show_with_warning` aparece en la primera version del dashboard o
  queda en una pestana de estudio.
- Si se quiere mas precision, abrir una fase acotada de persistencia de pivotes
  y maduracion por eventos.
- Mantener `can_generate_signal=false`, `can_filter_trade=false` y
  `can_execute_order=false`.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_CURRENT_HYPOTHESIS_V0.md").write_text(doc, encoding="utf-8")


def minimum_evidence(state: str) -> str:
    if state in {"possible_wave1", "possible_waveA"}:
        return "one visible pivot or early tentative pivot"
    if state in {"possible_wave2", "possible_waveB"}:
        return "opposite move after first structural pivot; tentative allowed"
    if state in {"possible_wave3_candidate", "possible_waveC_candidate"}:
        return "post-correction continuation candidate, before breakout"
    if state in {"possible_wave3_active", "possible_wave5_active", "possible_waveC_active"}:
        return "price extends beyond prior relevant extreme"
    if state in {"possible_wave4", "possible_wave5_candidate"}:
        return "confirmed or tentative pullback after prior impulse leg"
    if state in {"completed_impulse_candidate", "completed_abc_candidate"}:
        return "persistent sequence, clean alternation, not only pivot count"
    return "not enough or conflicting evidence"


def schema_purpose(column: str) -> str:
    purposes = {
        "estimated_current_wave": "Dashboard-facing wave estimate; may be provisional.",
        "confirmed_wave_context": "Confirmed-late structural context from causal pivots.",
        "freshness_status": "Whether estimate is fresh, provisional, late, stale or manual-review.",
        "wave_stability_status": "Whether pivots are stable enough for display.",
        "display_policy": "How dashboard may show the row.",
    }
    return purposes.get(column, "current_wave_hypothesis_v0 contract field")


def safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in str(value)).strip("_")


def timestamp_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return ""
    return timestamp.isoformat()


def float_or_blank(value: Any) -> str | float:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if pd.isna(number):
        return ""
    return round(number, 6)


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si"}


def validate_payload(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    text = "{}" if value is None else str(value).strip()
    if not text:
        text = "{}"
    json.loads(text)
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-operative current wave hypotheses for dashboard context study.")
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--higher-timeframe", default=DEFAULT_HIGHER_TIMEFRAME)
    parser.add_argument("--max-symbols", type=int, default=4)
    parser.add_argument("--as-of-bar-time", default=None)
    parser.add_argument("--structure-family", default="impulse")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    symbols = tuple(symbol.strip() for symbol in args.symbols.split(",") if symbol.strip())
    result = build_current_wave_hypothesis(
        CurrentWaveHypothesisConfig(
            source_csv=args.source_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            symbols=symbols,
            timeframe=args.timeframe,
            higher_timeframe=args.higher_timeframe,
            max_symbols=args.max_symbols,
            as_of_bar_time=args.as_of_bar_time,
            structure_family=args.structure_family,
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
