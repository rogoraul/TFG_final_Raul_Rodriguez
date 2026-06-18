from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_structure import StructuralPivotConfig
from trading_center.wavecount_live_context import classify_fixture_case
from trading_center.wavecount_live_ohlc import prepare_ohlc_case, WaveCountLiveOhlcConfig
from trading_center.wavecount_live_schema import (
    WAVECOUNT_LIVE_COLUMNS,
    normalize_wavecount_live_frame,
    schema_frame,
    validate_hard_flags,
)


DEFAULT_SOURCE_CSV = Path(
    "artifacts/wavecount/05_guided_profile/"
    "phase2_5_2_h4_d1_expansion_2026-05-24/"
    "diagnostic_phase2_4_h4_d1_expanded/tables/wavecount_context.csv"
)
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_context_v0_real_ohlc_cut_review_2026-05-26")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_CONTEXT_V0_REAL_OHLC_CUT_REVIEW.md")
DEFAULT_SYMBOLS = ("EURUSD.r", "GBPUSD.r", "US500", "XAUUSD.r")
DEFAULT_TIMEFRAME = "H4"
DEFAULT_HIGHER_TIMEFRAME = "D1"


@dataclass(frozen=True)
class RealOhlcCutReviewConfig:
    source_csv: Path = DEFAULT_SOURCE_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    timeframe: str = DEFAULT_TIMEFRAME
    higher_timeframe: str = DEFAULT_HIGHER_TIMEFRAME
    cut_count: int = 10
    min_bars_first_cut: int = 40
    max_symbols: int = 4
    generate_charts: bool = True
    pivot_config: PivotConfig = PivotConfig()
    structural_config: StructuralPivotConfig = StructuralPivotConfig()


@dataclass(frozen=True)
class RealOhlcCutReviewResult:
    contexts: pd.DataFrame
    source_inventory: pd.DataFrame
    cut_inventory: pd.DataFrame
    anti_lookahead_audit: pd.DataFrame
    detected_pivots: pd.DataFrame
    structural_pivots: pd.DataFrame
    label_transition_audit: pd.DataFrame
    pivot_stability_audit: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_real_ohlc_cut_review(
    config: RealOhlcCutReviewConfig | None = None,
) -> RealOhlcCutReviewResult:
    config = config or RealOhlcCutReviewConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source = load_source_ohlc(config.source_csv)
    selected = select_series(source, config)

    rows: list[dict[str, Any]] = []
    cut_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    detected_frames: list[pd.DataFrame] = []
    structural_frames: list[pd.DataFrame] = []

    for series_key, series in selected.items():
        group, symbol, timeframe = series_key
        series = series.sort_values("time").reset_index(drop=True)
        cut_indexes = progressive_cut_indexes(len(series), config.cut_count, config.min_bars_first_cut)
        for cut_number, cut_index in enumerate(cut_indexes, start=1):
            as_of = pd.Timestamp(series.iloc[cut_index]["time"])
            cut_id = f"{_safe_id(symbol)}_{timeframe}_cut{cut_number:02d}"
            case = make_cut_case(
                cut_id=cut_id,
                group=group,
                symbol=symbol,
                timeframe=timeframe,
                higher_timeframe=config.higher_timeframe,
                as_of=as_of,
                series=series,
                source_path=config.source_csv,
            )
            prepared = prepare_ohlc_case(
                case,
                config=WaveCountLiveOhlcConfig(
                    fixture_dir=Path("."),
                    output_dir=config.output_dir,
                    pivot_config=config.pivot_config,
                    structural_config=config.structural_config,
                ),
            )
            row, base_audit = classify_fixture_case(prepared["classification_case"], generated_at=generated_at)
            row.update(
                {
                    "context_id": f"wavecount_live_v0_realcut_{cut_id}_{as_of.strftime('%Y%m%dT%H%M%S')}",
                    "source": "wavecount_live_context_v0_real_ohlc_cut_review",
                    "data_origin": "real_ohlc_local_artifact",
                    "method_version": "wavecount_live_context_v0_real_ohlc_cut_review",
                    "source_artifacts": str(config.source_csv),
                    "notes": (
                        "real OHLC local artifact cut review; "
                        f"symbol={symbol}; timeframe={timeframe}; cut={cut_number}; "
                        "no_signal_no_filter_no_execution"
                    ),
                    "payload_json": json.dumps(
                        real_cut_payload(prepared, row, cut_number, cut_index, config),
                        sort_keys=True,
                        default=str,
                    ),
                }
            )
            rows.append(row)
            audit_rows.append(real_lookahead_audit_row(prepared, base_audit, cut_number, cut_index))
            cut_rows.append(cut_inventory_row(prepared, row, cut_number, cut_index, len(series)))

            detected = prepared["detected_pivots"].copy()
            if not detected.empty:
                detected["cut_id"] = cut_id
                detected["cut_index"] = cut_number
                detected["as_of_bar_time"] = as_of.isoformat()
                detected_frames.append(detected)
            structural = prepared["structural_pivots"].copy()
            if not structural.empty:
                structural["cut_id"] = cut_id
                structural["cut_index"] = cut_number
                structural["as_of_bar_time"] = as_of.isoformat()
                structural_frames.append(structural)

    contexts = normalize_wavecount_live_frame(pd.DataFrame(rows, columns=WAVECOUNT_LIVE_COLUMNS))
    validate_hard_flags(contexts)
    cut_inventory = pd.DataFrame(cut_rows)
    anti_lookahead = pd.DataFrame(audit_rows)
    detected_pivots = concat_or_empty(detected_frames)
    structural_pivots = concat_or_empty(structural_frames)
    source_inventory = source_inventory_frame(config.source_csv, source, selected)
    label_transition = build_label_transition_audit(contexts, cut_inventory)
    pivot_stability = build_pivot_stability_audit(cut_inventory, detected_pivots, structural_pivots)
    issues = build_issues_or_risks(contexts, anti_lookahead, label_transition, pivot_stability)
    decision = decide_next_step(issues)
    run_meta = build_run_meta(
        generated_at=generated_at,
        config=config,
        contexts=contexts,
        source_inventory=source_inventory,
        cut_inventory=cut_inventory,
        anti_lookahead=anti_lookahead,
        detected_pivots=detected_pivots,
        decision=decision,
    )
    written = write_outputs(
        config=config,
        contexts=contexts,
        source_inventory=source_inventory,
        cut_inventory=cut_inventory,
        anti_lookahead=anti_lookahead,
        detected_pivots=detected_pivots,
        structural_pivots=structural_pivots,
        label_transition=label_transition,
        pivot_stability=pivot_stability,
        issues=issues,
        run_meta=run_meta,
    )
    chart_files = write_charts(config, source, contexts, structural_pivots) if config.generate_charts else []
    if chart_files:
        written["charts"] = config.output_dir / "charts"
        run_meta["chart_files"] = [str(path) for path in chart_files]
        (config.output_dir / "run_meta.json").write_text(
            json.dumps(run_meta, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    write_docs(
        config=config,
        run_meta=run_meta,
        source_inventory=source_inventory,
        cut_inventory=cut_inventory,
        label_transition=label_transition,
        pivot_stability=pivot_stability,
        issues=issues,
        decision=decision,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_CONTEXT_V0_REAL_OHLC_CUT_REVIEW.md"
    return RealOhlcCutReviewResult(
        contexts=contexts,
        source_inventory=source_inventory,
        cut_inventory=cut_inventory,
        anti_lookahead_audit=anti_lookahead,
        detected_pivots=detected_pivots,
        structural_pivots=structural_pivots,
        label_transition_audit=label_transition,
        pivot_stability_audit=pivot_stability,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def load_source_ohlc(source_csv: Path) -> pd.DataFrame:
    if not source_csv.exists():
        raise FileNotFoundError(f"source CSV does not exist: {source_csv}")
    usecols = [
        "example_id",
        "group",
        "symbol",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
    ]
    frame = pd.read_csv(source_csv, usecols=usecols)
    frame = frame.rename(columns={"timestamp": "time", "group": "market_group"})
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["time", "open", "high", "low", "close", "symbol", "timeframe"])
    return frame.sort_values(["market_group", "symbol", "timeframe", "time"]).reset_index(drop=True)


def select_series(
    source: pd.DataFrame,
    config: RealOhlcCutReviewConfig,
) -> dict[tuple[str, str, str], pd.DataFrame]:
    frame = source[source["timeframe"].astype(str).str.upper() == config.timeframe.upper()].copy()
    if frame.empty:
        raise ValueError(f"no rows found for timeframe={config.timeframe}")

    preferred = [symbol for symbol in config.symbols if symbol in set(frame["symbol"])]
    if len(preferred) < min(config.max_symbols, len(config.symbols)):
        for _, row in (
            frame.groupby(["market_group", "symbol"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values(["market_group", "symbol"])
            .iterrows()
        ):
            symbol = str(row["symbol"])
            if symbol not in preferred:
                preferred.append(symbol)
            if len(preferred) >= config.max_symbols:
                break

    selected_symbols = preferred[: config.max_symbols]
    selected: dict[tuple[str, str, str], pd.DataFrame] = {}
    for (group, symbol, timeframe), part in frame[frame["symbol"].isin(selected_symbols)].groupby(
        ["market_group", "symbol", "timeframe"],
        dropna=False,
    ):
        if len(part) >= max(20, min(config.min_bars_first_cut, len(part))):
            selected[(str(group), str(symbol), str(timeframe))] = part.copy()
    if not selected:
        raise ValueError("no usable OHLC series selected")
    return selected


def progressive_cut_indexes(row_count: int, cut_count: int, min_bars_first_cut: int) -> list[int]:
    if row_count < 20:
        return [row_count - 1]
    first = min(max(20, min_bars_first_cut), row_count - 1)
    if cut_count <= 1 or first >= row_count - 1:
        return [row_count - 1]
    raw = pd.Series([round(value) for value in np.linspace(first, row_count - 1, cut_count)])
    indexes = sorted({int(value) for value in raw if 0 <= int(value) < row_count})
    if indexes[-1] != row_count - 1:
        indexes.append(row_count - 1)
    return indexes


def make_cut_case(
    *,
    cut_id: str,
    group: str,
    symbol: str,
    timeframe: str,
    higher_timeframe: str,
    as_of: pd.Timestamp,
    series: pd.DataFrame,
    source_path: Path,
) -> dict[str, Any]:
    bars = [
        {
            "time": pd.Timestamp(row.time).isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        }
        for row in series.itertuples(index=False)
    ]
    return {
        "fixture_id": cut_id,
        "symbol": symbol,
        "market_group": group,
        "timeframe": timeframe,
        "higher_timeframe": higher_timeframe,
        "structure_family": "impulse",
        "direction": infer_direction(series, as_of),
        "degree": "intermediate",
        "as_of_bar_time": as_of.isoformat(),
        "bars": bars,
        "notes": "real OHLC local artifact cut review",
        "_source_path": str(source_path),
    }


def infer_direction(series: pd.DataFrame, as_of: pd.Timestamp) -> str:
    used = series[series["time"] <= as_of].tail(80)
    if len(used) < 2:
        return "long"
    return "long" if float(used.iloc[-1]["close"]) >= float(used.iloc[0]["close"]) else "short"


def real_cut_payload(
    prepared: dict[str, Any],
    row: dict[str, Any],
    cut_number: int,
    cut_index: int,
    config: RealOhlcCutReviewConfig,
) -> dict[str, Any]:
    return {
        "cut_id": prepared["fixture_id"],
        "cut_number": cut_number,
        "cut_index_zero_based": cut_index,
        "source_path": str(config.source_csv),
        "actual_structure_phase": row["structure_phase"],
        "bars_total": int(len(prepared["bars_all"])),
        "bars_used": int(len(prepared["bars_used"])),
        "bars_after_as_of_ignored": int(len(prepared["bars_all"]) - len(prepared["bars_used"])),
        "detected_pivots": int(len(prepared["detected_pivots"])),
        "structural_pivots": int(len(prepared["structural_pivots"])),
        "pivot_config": config.pivot_config.__dict__,
        "structural_config": config.structural_config.__dict__,
        "real_ohlc_cut_review": True,
        "operational_use": "forbidden",
    }


def real_lookahead_audit_row(
    prepared: dict[str, Any],
    base_audit: dict[str, Any],
    cut_number: int,
    cut_index: int,
) -> dict[str, Any]:
    structural = prepared["structural_pivots"]
    detected = prepared["detected_pivots"]
    as_of = pd.Timestamp(prepared["as_of_bar_time"])
    latest_detected = pd.NaT if structural.empty else pd.to_datetime(structural["pivot_detected_at"], errors="coerce").max()
    latest_extreme = pd.NaT if structural.empty else pd.to_datetime(structural["pivot_extreme_time"], errors="coerce").max()
    future_pivots = 0
    if not detected.empty and "pivot_detected_at" in detected.columns:
        future_pivots = int((pd.to_datetime(detected["pivot_detected_at"], errors="coerce") > as_of).sum())
    return {
        **base_audit,
        "cut_id": prepared["fixture_id"],
        "cut_number": cut_number,
        "cut_index_zero_based": cut_index,
        "bars_total": int(len(prepared["bars_all"])),
        "bars_used": int(len(prepared["bars_used"])),
        "bars_after_as_of_ignored": int(len(prepared["bars_all"]) - len(prepared["bars_used"])),
        "detected_pivots_total": int(len(detected)),
        "structural_pivots_used": int(len(structural)),
        "future_pivots_used": future_pivots,
        "latest_pivot_detected_at": "" if pd.isna(latest_detected) else pd.Timestamp(latest_detected).isoformat(),
        "latest_pivot_extreme_time": "" if pd.isna(latest_extreme) else pd.Timestamp(latest_extreme).isoformat(),
        "pivot_detected_at_lte_as_of": True if pd.isna(latest_detected) else pd.Timestamp(latest_detected) <= as_of,
        "pivot_confirmed_at_lte_as_of": True if pd.isna(latest_detected) else pd.Timestamp(latest_detected) <= as_of,
        "pivot_extreme_time_used_as_detection": False if pd.isna(latest_detected) or pd.isna(latest_extreme) else pd.Timestamp(latest_detected) == pd.Timestamp(latest_extreme),
    }


def cut_inventory_row(
    prepared: dict[str, Any],
    row: dict[str, Any],
    cut_number: int,
    cut_index: int,
    series_rows: int,
) -> dict[str, Any]:
    return {
        "cut_id": prepared["fixture_id"],
        "cut_number": cut_number,
        "cut_index_zero_based": cut_index,
        "symbol": row["symbol"],
        "market_group": row["market_group"],
        "timeframe": row["timeframe"],
        "higher_timeframe": row["higher_timeframe"],
        "as_of_bar_time": row["as_of_bar_time"],
        "series_rows": int(series_rows),
        "bars_used": int(len(prepared["bars_used"])),
        "bars_after_as_of_ignored": int(len(prepared["bars_all"]) - len(prepared["bars_used"])),
        "detected_pivots": int(len(prepared["detected_pivots"])),
        "structural_pivots": int(len(prepared["structural_pivots"])),
        "structure_phase": row["structure_phase"],
        "hypothesis_status": row["hypothesis_status"],
        "direction": row["direction"],
    }


def source_inventory_frame(
    source_csv: Path,
    source: pd.DataFrame,
    selected: dict[tuple[str, str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (group, symbol, timeframe), part in selected.items():
        times = pd.to_datetime(part["time"], errors="coerce")
        inferred_delta = infer_time_delta_minutes(times)
        rows.append(
            {
                "source_path": str(source_csv),
                "source_role": "local_real_ohlc_artifact",
                "symbol": symbol,
                "market_group": group,
                "timeframe": timeframe,
                "rows_selected": int(len(part)),
                "source_rows_total": int(len(source)),
                "start_time": times.min().isoformat(),
                "end_time": times.max().isoformat(),
                "inferred_bar_minutes": inferred_delta,
                "gap_count_estimate": estimate_gap_count(times, inferred_delta),
                "timestamps_closed_assumption": "artifact_timestamp_treated_as_closed_bar_time",
                "limitations": "Existing WaveCount context artifact; not downloaded, not broker-connected, not a performance sample.",
            }
        )
    return pd.DataFrame(rows)


def infer_time_delta_minutes(times: pd.Series) -> int:
    deltas = times.sort_values().diff().dropna()
    if deltas.empty:
        return 0
    return int(round(deltas.dt.total_seconds().median() / 60.0))


def estimate_gap_count(times: pd.Series, expected_minutes: int) -> int:
    if expected_minutes <= 0:
        return 0
    deltas = times.sort_values().diff().dropna().dt.total_seconds() / 60.0
    return int((deltas > expected_minutes * 1.5).sum())


def build_label_transition_audit(contexts: pd.DataFrame, cut_inventory: pd.DataFrame) -> pd.DataFrame:
    merged = cut_inventory.merge(
        contexts[["context_id", "symbol", "timeframe", "as_of_bar_time", "structure_family", "structure_phase", "hypothesis_status"]],
        on=["symbol", "timeframe", "as_of_bar_time", "structure_phase", "hypothesis_status"],
        how="left",
    )
    phase_rank = {
        "unknown": 0,
        "not_available": 0,
        "possible_wave1": 1,
        "possible_wave2": 2,
        "possible_wave3_candidate": 3,
        "possible_wave3_active": 4,
        "possible_wave4": 5,
        "possible_wave5_candidate": 6,
        "possible_wave5_active": 7,
        "completed_impulse_candidate": 8,
        "possible_waveA": 9,
        "possible_waveB": 10,
        "possible_waveC_candidate": 11,
        "possible_waveC_active": 12,
        "completed_abc_candidate": 13,
        "ambiguous": -1,
        "invalidated": -2,
    }
    rows: list[dict[str, Any]] = []
    for (_, _), part in merged.sort_values(["symbol", "timeframe", "cut_number"]).groupby(["symbol", "timeframe"], dropna=False):
        previous: dict[str, Any] | None = None
        churn = 0
        ambiguous_count = 0
        invalidated_count = 0
        for record in part.to_dict(orient="records"):
            phase = str(record["structure_phase"])
            if phase == "ambiguous":
                ambiguous_count += 1
            if phase == "invalidated":
                invalidated_count += 1
            previous_phase = "" if previous is None else str(previous["structure_phase"])
            phase_changed = previous is not None and previous_phase != phase
            if phase_changed:
                churn += 1
            rank_delta = None if previous is None else phase_rank.get(phase, 0) - phase_rank.get(previous_phase, 0)
            transition_type = classify_transition(previous_phase, phase, rank_delta)
            rows.append(
                {
                    "symbol": record["symbol"],
                    "timeframe": record["timeframe"],
                    "cut_number": record["cut_number"],
                    "as_of_bar_time": record["as_of_bar_time"],
                    "previous_structure_phase": previous_phase,
                    "structure_phase": phase,
                    "phase_changed": phase_changed,
                    "rank_delta": "" if rank_delta is None else rank_delta,
                    "transition_type": transition_type,
                    "churn_count_to_date": churn,
                    "ambiguous_count_to_date": ambiguous_count,
                    "invalidated_count_to_date": invalidated_count,
                    "wave3_candidate_evidence_ok": phase != "possible_wave3_candidate" or int(record["structural_pivots"]) >= 3,
                    "wave5_active_evidence_ok": phase != "possible_wave5_active" or int(record["structural_pivots"]) >= 5,
                    "needs_manual_review": transition_type in {"abrupt_reclassification", "ambiguous_or_invalidated"},
                }
            )
            previous = record
    return pd.DataFrame(rows)


def classify_transition(previous_phase: str, phase: str, rank_delta: int | None) -> str:
    if previous_phase == "":
        return "initial_cut"
    if previous_phase == phase:
        return "stable"
    if phase in {"ambiguous", "invalidated"} or previous_phase in {"ambiguous", "invalidated"}:
        return "ambiguous_or_invalidated"
    if rank_delta is not None and 0 < rank_delta <= 2:
        return "forward_progression"
    if rank_delta is not None and rank_delta < 0:
        return "regression_or_reclassification"
    return "abrupt_reclassification"


def build_pivot_stability_audit(
    cut_inventory: pd.DataFrame,
    detected_pivots: pd.DataFrame,
    structural_pivots: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    previous_keys: dict[tuple[str, str], set[str]] = {}
    for record in cut_inventory.sort_values(["symbol", "timeframe", "cut_number"]).to_dict(orient="records"):
        key = (str(record["symbol"]), str(record["timeframe"]))
        cut_id = str(record["cut_id"])
        detected = detected_pivots[detected_pivots.get("cut_id", "") == cut_id] if not detected_pivots.empty else pd.DataFrame()
        structural = structural_pivots[structural_pivots.get("cut_id", "") == cut_id] if not structural_pivots.empty else pd.DataFrame()
        current_keys = structural_key_set(structural)
        disappeared = len(previous_keys.get(key, set()) - current_keys)
        new_pivots = len(current_keys - previous_keys.get(key, set()))
        previous_keys[key] = current_keys
        lag_values = pd.to_numeric(structural.get("confirmation_lag_bars", pd.Series(dtype=float)), errors="coerce")
        if lag_values.empty and not structural.empty:
            lag_values = compute_lag_from_times(structural)
        alternates = structural_alternates(structural)
        bars_used = int(record["bars_used"])
        detected_count = int(len(detected))
        structural_count = int(len(structural))
        too_noisy = detected_count / max(bars_used, 1) > 0.08
        too_sparse = bars_used >= 300 and structural_count < 2
        unstable = disappeared > 0
        late = bool(not lag_values.empty and lag_values.max() > 6)
        over_sensitive = structural_count / max(bars_used, 1) > 0.035
        rows.append(
            {
                "cut_id": cut_id,
                "symbol": record["symbol"],
                "timeframe": record["timeframe"],
                "cut_number": record["cut_number"],
                "as_of_bar_time": record["as_of_bar_time"],
                "bars_used": bars_used,
                "detected_pivots": detected_count,
                "structural_pivots": structural_count,
                "new_structural_pivots_vs_previous_cut": new_pivots,
                "disappeared_structural_pivots_vs_previous_cut": disappeared,
                "confirmed_pivots": int(detected["is_confirmed"].astype(bool).sum()) if not detected.empty and "is_confirmed" in detected.columns else 0,
                "median_confirmation_lag_bars": "" if lag_values.empty else round(float(lag_values.median()), 3),
                "max_confirmation_lag_bars": "" if lag_values.empty else round(float(lag_values.max()), 3),
                "alternates_high_low": alternates,
                "too_noisy": too_noisy,
                "too_sparse": too_sparse,
                "unstable_pivots": unstable,
                "late_confirmation": late,
                "over_sensitive": over_sensitive,
                "needs_visual_review": True,
            }
        )
    return pd.DataFrame(rows)


def structural_key_set(frame: pd.DataFrame) -> set[str]:
    if frame.empty:
        return set()
    keys = []
    for row in frame.to_dict(orient="records"):
        keys.append(
            "|".join(
                [
                    str(row.get("pivot_type", "")),
                    str(pd.Timestamp(row.get("pivot_extreme_time")).isoformat()),
                    f"{float(row.get('pivot_extreme_price')):.8f}",
                ]
            )
        )
    return set(keys)


def compute_lag_from_times(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    timeframe = str(frame.iloc[0].get("timeframe", "H4")).upper()
    minutes = {"M30": 30, "H1": 60, "H4": 240, "D1": 1440}.get(timeframe, 240)
    detected = pd.to_datetime(frame["pivot_detected_at"], errors="coerce")
    extreme = pd.to_datetime(frame["pivot_extreme_time"], errors="coerce")
    return (detected - extreme).dt.total_seconds() / 60.0 / minutes


def structural_alternates(frame: pd.DataFrame) -> str:
    if frame.empty or len(frame) < 2 or "pivot_type" not in frame.columns:
        return "not_applicable"
    types = frame["pivot_type"].astype(str).tolist()
    return str(all(left != right for left, right in zip(types, types[1:])))


def build_issues_or_risks(
    contexts: pd.DataFrame,
    anti_lookahead: pd.DataFrame,
    label_transition: pd.DataFrame,
    pivot_stability: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    lookahead_ok = bool(anti_lookahead["lookahead_safe"].all()) and bool(anti_lookahead["pivot_detected_at_lte_as_of"].all())
    rows.append(
        {
            "severity": "blocking" if not lookahead_ok else "info",
            "risk": "lookahead_guard",
            "description": "Anti look-ahead checks passed." if lookahead_ok else "At least one cut violates anti look-ahead checks.",
            "recommendation": "Block integration until fixed." if not lookahead_ok else "Keep checks in any later SQL staging.",
        }
    )
    churn_rate = float(label_transition["phase_changed"].astype(bool).mean()) if not label_transition.empty else 0.0
    abrupt = int((label_transition["transition_type"] == "abrupt_reclassification").sum()) if not label_transition.empty else 0
    unstable = int(pivot_stability["unstable_pivots"].astype(bool).sum()) if not pivot_stability.empty else 0
    noisy = int(pivot_stability["too_noisy"].astype(bool).sum()) if not pivot_stability.empty else 0
    sparse = int(pivot_stability["too_sparse"].astype(bool).sum()) if not pivot_stability.empty else 0
    active_wave5 = int((contexts["structure_phase"] == "possible_wave5_active").sum()) if not contexts.empty else 0
    rows.extend(
        [
            {
                "severity": "medium" if churn_rate > 0.55 or abrupt > 0 else "low",
                "risk": "label_churn",
                "description": f"Phase changed in {churn_rate:.1%} of progressive cut rows; abrupt transitions={abrupt}.",
                "recommendation": "Review transitions manually before SQL staging.",
            },
            {
                "severity": "medium" if unstable else "low",
                "risk": "pivot_instability",
                "description": f"Structural pivots disappeared/replaced in {unstable} cut rows.",
                "recommendation": "Treat prior live rows as append-only; do not rewrite old labels.",
            },
            {
                "severity": "medium" if noisy else "low",
                "risk": "pivot_noise",
                "description": f"Too-noisy heuristic triggered in {noisy} cut rows.",
                "recommendation": "Review pivot parameters if this persists on broader data.",
            },
            {
                "severity": "medium" if sparse else "low",
                "risk": "pivot_sparsity",
                "description": f"Too-sparse heuristic triggered in {sparse} cut rows.",
                "recommendation": "Check whether structural thresholds are too strict for selected timeframe.",
            },
            {
                "severity": "low",
                "risk": "wave5_active_frequency",
                "description": f"`possible_wave5_active` appears in {active_wave5} rows.",
                "recommendation": "Do not interpret wave5 labels as exhaustion or trading filters.",
            },
            {
                "severity": "medium",
                "risk": "visual_review_required",
                "description": "Charts/tables are generated for a light manual review, but not a full visual audit.",
                "recommendation": "Before SQL/dashboard, inspect representative pivots manually.",
            },
        ]
    )
    return pd.DataFrame(rows)


def decide_next_step(issues: pd.DataFrame) -> str:
    if (issues["severity"] == "blocking").any():
        return "needs_pivot_logic_fix_before_sql"
    medium = set(issues.loc[issues["severity"] == "medium", "risk"])
    if {"pivot_noise", "pivot_sparsity"} & medium:
        return "needs_parameter_review_before_sql"
    if {"label_churn", "pivot_instability", "visual_review_required"} & medium:
        return "needs_more_real_ohlc_review"
    return "ready_for_sql_staging_design"


def build_run_meta(
    *,
    generated_at: str,
    config: RealOhlcCutReviewConfig,
    contexts: pd.DataFrame,
    source_inventory: pd.DataFrame,
    cut_inventory: pd.DataFrame,
    anti_lookahead: pd.DataFrame,
    detected_pivots: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_context_v0_real_ohlc_cut_review",
        "decision": decision,
        "source_csv": str(config.source_csv),
        "symbols": sorted(contexts["symbol"].dropna().unique().tolist()),
        "timeframes": sorted(contexts["timeframe"].dropna().unique().tolist()),
        "source_series": int(len(source_inventory)),
        "cut_count": int(len(cut_inventory)),
        "rows": int(len(contexts)),
        "structure_phase_distribution": {
            str(key): int(value)
            for key, value in contexts["structure_phase"].value_counts().sort_index().to_dict().items()
        },
        "hypothesis_status_distribution": {
            str(key): int(value)
            for key, value in contexts["hypothesis_status"].value_counts().sort_index().to_dict().items()
        },
        "bars_after_as_of_ignored": int(anti_lookahead["bars_after_as_of_ignored"].astype(int).sum()) if not anti_lookahead.empty else 0,
        "confirmed_pivots_used": int(detected_pivots["is_confirmed"].astype(bool).sum()) if not detected_pivots.empty and "is_confirmed" in detected_pivots.columns else 0,
        "pivot_config": config.pivot_config.__dict__,
        "structural_config": config.structural_config.__dict__,
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
        "anti_lookahead_passed": bool(anti_lookahead["lookahead_safe"].all()) if not anti_lookahead.empty else False,
        "limitations": [
            "Technical cut review over existing local OHLC artifacts; not a backtest and not edge evidence.",
            "Labels are structural hypotheses, not signals or filters.",
            "The selected source is an existing WaveCount context artifact, not a fresh broker/data pull.",
            "Higher-timeframe context remains metadata in this review.",
        ],
    }


def write_outputs(
    *,
    config: RealOhlcCutReviewConfig,
    contexts: pd.DataFrame,
    source_inventory: pd.DataFrame,
    cut_inventory: pd.DataFrame,
    anti_lookahead: pd.DataFrame,
    detected_pivots: pd.DataFrame,
    structural_pivots: pd.DataFrame,
    label_transition: pd.DataFrame,
    pivot_stability: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "csv": output_dir / "wavecount_live_context.csv",
        "json": output_dir / "wavecount_live_context.json",
        "run_meta": output_dir / "run_meta.json",
        "schema": output_dir / "schema.csv",
        "source_ohlc_inventory": output_dir / "source_ohlc_inventory.csv",
        "cut_inventory": output_dir / "cut_inventory.csv",
        "anti_lookahead_audit": output_dir / "anti_lookahead_audit.csv",
        "detected_pivots": output_dir / "detected_pivots.csv",
        "structural_pivots": output_dir / "structural_pivots.csv",
        "label_transition_audit": output_dir / "label_transition_audit.csv",
        "pivot_stability_audit": output_dir / "pivot_stability_audit.csv",
        "issues_or_risks": output_dir / "issues_or_risks.csv",
    }
    contexts.to_csv(paths["csv"], index=False)
    paths["json"].write_text(
        json.dumps(contexts.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    schema_frame().to_csv(paths["schema"], index=False)
    source_inventory.to_csv(paths["source_ohlc_inventory"], index=False)
    cut_inventory.to_csv(paths["cut_inventory"], index=False)
    anti_lookahead.to_csv(paths["anti_lookahead_audit"], index=False)
    detected_pivots.to_csv(paths["detected_pivots"], index=False)
    structural_pivots.to_csv(paths["structural_pivots"], index=False)
    label_transition.to_csv(paths["label_transition_audit"], index=False)
    pivot_stability.to_csv(paths["pivot_stability_audit"], index=False)
    issues.to_csv(paths["issues_or_risks"], index=False)

    # Mirror key CSVs under tables/ for quick artifact browsing.
    for key in [
        "source_ohlc_inventory",
        "cut_inventory",
        "anti_lookahead_audit",
        "label_transition_audit",
        "pivot_stability_audit",
        "issues_or_risks",
    ]:
        target = tables_dir / paths[key].name
        pd.read_csv(paths[key]).to_csv(target, index=False)
    return paths


def write_charts(
    config: RealOhlcCutReviewConfig,
    source: pd.DataFrame,
    contexts: pd.DataFrame,
    structural_pivots: pd.DataFrame,
) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    chart_files: list[Path] = []
    representative = contexts.sort_values(["symbol", "timeframe", "as_of_bar_time"]).groupby(["symbol", "timeframe"]).tail(1).head(3)
    for record in representative.to_dict(orient="records"):
        symbol = str(record["symbol"])
        timeframe = str(record["timeframe"])
        as_of = pd.Timestamp(record["as_of_bar_time"])
        cut_id = json.loads(record["payload_json"]).get("cut_id", "")
        series = source[(source["symbol"] == symbol) & (source["timeframe"] == timeframe) & (source["time"] <= as_of)].tail(180)
        pivots = structural_pivots[structural_pivots.get("cut_id", "") == cut_id] if not structural_pivots.empty else pd.DataFrame()
        if series.empty:
            continue
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(series["time"], series["close"], color="#1f2937", linewidth=1.5, label="close")
        if not pivots.empty:
            pivot_times = pd.to_datetime(pivots["pivot_extreme_time"], errors="coerce")
            pivot_prices = pd.to_numeric(pivots["pivot_extreme_price"], errors="coerce")
            pivot_types = pivots["pivot_type"].astype(str)
            colors = pivot_types.map({"high": "#cc3311", "low": "#0077bb"}).fillna("#666666")
            ax.scatter(pivot_times, pivot_prices, c=colors, s=36, zorder=3, label="structural pivots")
        ax.axvline(as_of, color="#ee7733", linestyle="--", linewidth=1.2, label="as_of")
        ax.set_title(f"{symbol} {timeframe} cut review: {record['structure_phase']}")
        ax.set_ylabel("price")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(loc="best")
        fig.autofmt_xdate()
        fig.tight_layout()
        path = chart_dir / f"{_safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        chart_files.append(path)
    return chart_files


def write_docs(
    *,
    config: RealOhlcCutReviewConfig,
    run_meta: dict[str, Any],
    source_inventory: pd.DataFrame,
    cut_inventory: pd.DataFrame,
    label_transition: pd.DataFrame,
    pivot_stability: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    title = "WaveCount Live Context v0 - Real OHLC Cut Review"
    source_rows = markdown_table(source_inventory)
    issue_rows = markdown_table(issues)
    phase_rows = pd.DataFrame(
        [
            {"structure_phase": key, "count": value}
            for key, value in run_meta["structure_phase_distribution"].items()
        ]
    )
    transition_summary = (
        label_transition["transition_type"]
        .value_counts()
        .sort_index()
        .rename_axis("transition_type")
        .reset_index(name="count")
        if not label_transition.empty
        else pd.DataFrame(columns=["transition_type", "count"])
    )
    pivot_summary = pd.DataFrame(
        [
            {
                "metric": "cuts",
                "value": len(pivot_stability),
            },
            {
                "metric": "unstable_pivot_rows",
                "value": int(pivot_stability["unstable_pivots"].astype(bool).sum()) if not pivot_stability.empty else 0,
            },
            {
                "metric": "too_noisy_rows",
                "value": int(pivot_stability["too_noisy"].astype(bool).sum()) if not pivot_stability.empty else 0,
            },
            {
                "metric": "too_sparse_rows",
                "value": int(pivot_stability["too_sparse"].astype(bool).sum()) if not pivot_stability.empty else 0,
            },
        ]
    )
    doc = f"""# {title}

Fecha: 2026-05-26

## Decision

Decision: `{decision}`.

Esta decision es tecnica y limitada. La revision usa OHLC local ya existente en
artifacts, genera cortes progresivos `as_of_bar_time` y audita pivotes/etiquetas.
No es un backtest, no demuestra edge, no genera senales y no autoriza filtros
WaveCount.

## Datos Revisados

Fuente principal:

`{config.source_csv}`

{source_rows}

## Cortes y Contrato

- Series seleccionadas: {run_meta['source_series']}.
- Cortes generados: {run_meta['cut_count']}.
- Filas del contrato: {run_meta['rows']}.
- CSV/JSON mantienen el contrato `wavecount_live_context_v0`.
- `data_origin=real_ohlc_local_artifact`.

Distribucion de fases:

{markdown_table(phase_rows)}

## Anti Look-Ahead

- `anti_lookahead_passed={run_meta['anti_lookahead_passed']}`.
- Velas ignoradas por estar despues del corte: {run_meta['bars_after_as_of_ignored']}.
- Pivotes confirmados usados: {run_meta['confirmed_pivots_used']}.
- Los pivotes se auditan por `pivot_detected_at`; `pivot_extreme_time` queda
  como referencia visual, no como evento operativo.

## Estabilidad de Etiquetas

{markdown_table(transition_summary)}

La estabilidad se interpreta como comportamiento estructural, no como
rendimiento posterior.

## Estabilidad de Pivotes

{markdown_table(pivot_summary)}

Los pivotes reales requieren revision visual/manual antes de cualquier staging
SQL. Los graficos ligeros, si se han podido generar, estan en `charts/`.

## Riesgos

{issue_rows}

## Que No Se Puede Concluir

- No se puede concluir que WaveCount aporte edge.
- No se puede concluir que mejore ENBOLSA.
- No se puede concluir que una posible onda 3 sea una senal.
- No se puede concluir que una onda 5 anticipe agotamiento operativo.
- No se puede pasar a dashboard/Telegram/bot/MT5 desde esta evidencia.

## Siguiente Paso

Segun la decision `{decision}`, el siguiente paso debe mantenerse no operativo:
si hay ruido, inestabilidad o necesidad visual, revisar parametros/pivotes con
mas cortes reales antes de disenar cualquier staging SQL.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (output_dir / "WAVECOUNT_LIVE_CONTEXT_V0_REAL_OHLC_CUT_REVIEW.md").write_text(doc, encoding="utf-8")


def markdown_table(frame: pd.DataFrame, max_rows: int = 40) -> str:
    if frame.empty:
        return "| empty |\n| --- |"
    view = frame.head(max_rows).copy()
    columns = [str(column) for column in view.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for record in view.to_dict(orient="records"):
        values = [markdown_cell(record.get(column, "")) for column in view.columns]
        lines.append("| " + " | ".join(values) + " |")
    if len(frame) > max_rows:
        lines.append("| " + " | ".join([f"... {len(frame) - max_rows} more rows"] + [""] * (len(columns) - 1)) + " |")
    return "\n".join(lines)


def markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def concat_or_empty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in str(value)).strip("_")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit WaveCount live context with real local OHLC progressive cuts.")
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--higher-timeframe", default=DEFAULT_HIGHER_TIMEFRAME)
    parser.add_argument("--cut-count", type=int, default=10)
    parser.add_argument("--min-bars-first-cut", type=int, default=40)
    parser.add_argument("--max-symbols", type=int, default=4)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    symbols = tuple(symbol.strip() for symbol in args.symbols.split(",") if symbol.strip())
    result = build_real_ohlc_cut_review(
        RealOhlcCutReviewConfig(
            source_csv=args.source_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            symbols=symbols,
            timeframe=args.timeframe,
            higher_timeframe=args.higher_timeframe,
            cut_count=args.cut_count,
            min_bars_first_cut=args.min_bars_first_cut,
            max_symbols=args.max_symbols,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "rows": int(len(result.contexts)),
                "cuts": int(len(result.cut_inventory)),
                "symbols": sorted(result.contexts["symbol"].unique().tolist()),
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
