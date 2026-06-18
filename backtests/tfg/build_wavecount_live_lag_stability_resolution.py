from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_grid_v2 import (
    config_family,
    market_group_sensitivity_rows,
)
from backtests.tfg.build_wavecount_live_parameter_review import (
    ParameterCandidate,
    anti_lookahead_row,
    concat_or_empty,
    filter_candidates,
    markdown_table,
    parameter_grid_frame,
    phase_distribution_rows,
    safe_id,
    summary_row,
)
from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import (
    DEFAULT_HIGHER_TIMEFRAME,
    DEFAULT_SOURCE_CSV,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAME,
    RealOhlcCutReviewConfig,
    build_real_ohlc_cut_review,
    load_source_ohlc,
)
from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_structure import StructuralPivotConfig


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_lag_stability_resolution_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_LAG_STABILITY_RESOLUTION.md")


@dataclass(frozen=True)
class LagStabilityResolutionConfig:
    source_csv: Path = DEFAULT_SOURCE_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    timeframe: str = DEFAULT_TIMEFRAME
    higher_timeframe: str = DEFAULT_HIGHER_TIMEFRAME
    cut_count: int = 10
    min_bars_first_cut: int = 40
    max_symbols: int = 4
    config_names: tuple[str, ...] | None = None
    generate_charts: bool = True


@dataclass(frozen=True)
class LagStabilityResolutionResult:
    parameter_grid: pd.DataFrame
    config_comparison: pd.DataFrame
    market_group: pd.DataFrame
    candidate_evaluation: pd.DataFrame
    lag_diagnostics: pd.DataFrame
    stability_diagnostics: pd.DataFrame
    visual_review: pd.DataFrame
    decision_summary: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_lag_stability_resolution(
    config: LagStabilityResolutionConfig | None = None,
) -> LagStabilityResolutionResult:
    config = config or LagStabilityResolutionConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    candidates = filter_candidates(default_lag_stability_candidates(), config.config_names)
    if not candidates:
        raise ValueError("no lag/stability configs selected")

    parameter_grid = parameter_grid_frame(candidates)
    parameter_grid.insert(1, "config_family", parameter_grid["config_name"].map(lag_config_family))

    summary_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    pivot_frames: list[pd.DataFrame] = []
    transition_frames: list[pd.DataFrame] = []
    anti_rows: list[dict[str, Any]] = []
    market_frames: list[pd.DataFrame] = []
    lag_frames: list[pd.DataFrame] = []
    stability_frames: list[pd.DataFrame] = []
    config_results: dict[str, Any] = {}

    for candidate in candidates:
        run_dir = config.output_dir / "config_runs" / candidate.config_name
        result = build_real_ohlc_cut_review(
            RealOhlcCutReviewConfig(
                source_csv=config.source_csv,
                output_dir=run_dir,
                doc_path=run_dir / "WAVECOUNT_LIVE_CONTEXT_V0_REAL_OHLC_CUT_REVIEW.md",
                symbols=config.symbols,
                timeframe=config.timeframe,
                higher_timeframe=config.higher_timeframe,
                cut_count=config.cut_count,
                min_bars_first_cut=config.min_bars_first_cut,
                max_symbols=config.max_symbols,
                generate_charts=False,
                pivot_config=candidate.pivot_config,
                structural_config=candidate.structural_config,
            )
        )
        config_results[candidate.config_name] = result
        summary_rows.append(summary_row(candidate, result))
        phase_rows.extend(phase_distribution_rows(candidate.config_name, result.contexts))

        pivot = result.pivot_stability_audit.copy()
        pivot.insert(0, "config_name", candidate.config_name)
        pivot_frames.append(pivot)

        transitions = result.label_transition_audit.copy()
        transitions.insert(0, "config_name", candidate.config_name)
        transition_frames.append(transitions)

        anti_rows.append(anti_lookahead_row(candidate.config_name, result))
        market_frames.append(market_group_sensitivity_rows(candidate.config_name, result))
        lag_frames.append(build_lag_diagnostics_for_config(candidate, result))
        stability_frames.append(build_stability_diagnostics_for_config(candidate, result))

    config_comparison = build_lag_stability_config_comparison(pd.DataFrame(summary_rows))
    phase_distribution = pd.DataFrame(phase_rows)
    pivot_stability = concat_or_empty(pivot_frames)
    label_transition = concat_or_empty(transition_frames)
    anti_lookahead = pd.DataFrame(anti_rows)
    market_group = concat_or_empty(market_frames)
    lag_diagnostics = concat_or_empty(lag_frames)
    stability_diagnostics = concat_or_empty(stability_frames)
    candidate_evaluation = build_lag_stability_candidate_evaluation(config_comparison)
    visual_review = build_lag_stability_visual_review(config, config_results, config_comparison) if config.generate_charts else empty_visual_review()
    decision_summary = build_decision_summary(config_comparison, candidate_evaluation, market_group, visual_review)
    decision = str(decision_summary.iloc[0]["decision"])
    issues_or_risks = build_issues_or_risks(config_comparison, candidate_evaluation, decision_summary)
    run_meta = build_run_meta(
        generated_at=generated_at,
        config=config,
        candidates=candidates,
        config_comparison=config_comparison,
        candidate_evaluation=candidate_evaluation,
        decision_summary=decision_summary,
        decision=decision,
        visual_review=visual_review,
    )
    written = write_outputs(
        config=config,
        parameter_grid=parameter_grid,
        config_comparison=config_comparison,
        phase_distribution=phase_distribution,
        pivot_stability=pivot_stability,
        label_transition=label_transition,
        anti_lookahead=anti_lookahead,
        market_group=market_group,
        candidate_evaluation=candidate_evaluation,
        lag_diagnostics=lag_diagnostics,
        stability_diagnostics=stability_diagnostics,
        visual_review=visual_review,
        decision_summary=decision_summary,
        issues_or_risks=issues_or_risks,
        run_meta=run_meta,
    )
    write_docs(
        config=config,
        config_comparison=config_comparison,
        market_group=market_group,
        candidate_evaluation=candidate_evaluation,
        decision_summary=decision_summary,
        issues_or_risks=issues_or_risks,
        decision=decision,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_LAG_STABILITY_RESOLUTION.md"
    return LagStabilityResolutionResult(
        parameter_grid=parameter_grid,
        config_comparison=config_comparison,
        market_group=market_group,
        candidate_evaluation=candidate_evaluation,
        lag_diagnostics=lag_diagnostics,
        stability_diagnostics=stability_diagnostics,
        visual_review=visual_review,
        decision_summary=decision_summary,
        issues_or_risks=issues_or_risks,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def default_lag_stability_candidates() -> list[ParameterCandidate]:
    return [
        ParameterCandidate(
            config_name="baseline_actual",
            description="Noise reference from the first real-OHLC cut review.",
            pivot_config=PivotConfig(),
            structural_config=StructuralPivotConfig(),
        ),
        ParameterCandidate(
            config_name="very_conservative_diagnostic",
            description="Best diagnostic configuration from parameter review v1.",
            pivot_config=PivotConfig(
                left_bars=6,
                confirmation_bars=6,
                atr_period=20,
                min_atr_multiplier=2.25,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=7,
                candidate_lookback_bars=8,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=8.0,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=20,
            ),
        ),
        ParameterCandidate(
            config_name="time_hard_a",
            description="Grid v2 time-led candidate: less lag than time_hard_b, more noise.",
            pivot_config=PivotConfig(
                left_bars=8,
                confirmation_bars=8,
                atr_period=20,
                min_atr_multiplier=2.25,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=10,
                candidate_lookback_bars=10,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=8.0,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=28,
            ),
        ),
        ParameterCandidate(
            config_name="time_hard_b",
            description="Grid v2 visually clean candidate, but late and unstable.",
            pivot_config=PivotConfig(
                left_bars=10,
                confirmation_bars=10,
                atr_period=20,
                min_atr_multiplier=2.0,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=12,
                candidate_lookback_bars=12,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=7.5,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=34,
            ),
        ),
        ParameterCandidate(
            config_name="time_mid_a",
            description="Midpoint between time_hard_a and time_hard_b.",
            pivot_config=PivotConfig(
                left_bars=9,
                confirmation_bars=8,
                atr_period=20,
                min_atr_multiplier=2.15,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=11,
                candidate_lookback_bars=11,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=7.75,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=31,
            ),
        ),
        ParameterCandidate(
            config_name="time_mid_b",
            description="Faster confirmation while keeping wide spacing.",
            pivot_config=PivotConfig(
                left_bars=8,
                confirmation_bars=6,
                atr_period=20,
                min_atr_multiplier=2.25,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=11,
                candidate_lookback_bars=10,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=8.0,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=30,
            ),
        ),
        ParameterCandidate(
            config_name="time_mid_c",
            description="High left window with lower confirmation lag.",
            pivot_config=PivotConfig(
                left_bars=10,
                confirmation_bars=6,
                atr_period=20,
                min_atr_multiplier=2.1,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=12,
                candidate_lookback_bars=12,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=7.5,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=34,
            ),
        ),
        ParameterCandidate(
            config_name="time_mid_d",
            description="Lower structural leg duration with intermediate pivot settings.",
            pivot_config=PivotConfig(
                left_bars=9,
                confirmation_bars=7,
                atr_period=20,
                min_atr_multiplier=2.15,
                min_relative_move_pct=0.004,
                min_bars_between_pivots=11,
                candidate_lookback_bars=11,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=7.5,
                min_leg_relative_move_pct=0.012,
                min_leg_bars=26,
            ),
        ),
        ParameterCandidate(
            config_name="time_mid_e",
            description="Faster confirmation combined with harder structural compression.",
            pivot_config=PivotConfig(
                left_bars=8,
                confirmation_bars=6,
                atr_period=24,
                min_atr_multiplier=2.5,
                min_relative_move_pct=0.0045,
                min_bars_between_pivots=11,
                candidate_lookback_bars=11,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=9.5,
                min_leg_relative_move_pct=0.014,
                min_leg_bars=30,
            ),
        ),
    ]


def lag_config_family(config_name: str) -> str:
    if config_name.startswith("time_mid_"):
        return "time_mid_resolution"
    return config_family(config_name)


def build_lag_stability_config_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    if frame.empty:
        return frame
    frame["config_family"] = frame["config_name"].map(lag_config_family)
    for name in ["baseline_actual", "time_hard_a", "time_hard_b"]:
        reference = frame[frame["config_name"] == name].iloc[0] if name in set(frame["config_name"]) else frame.iloc[0]
        frame[f"detected_reduction_vs_{name}_pct"] = frame["detected_pivots_total"].map(
            lambda value, ref=reference: round(1.0 - float(value) / max(float(ref["detected_pivots_total"]), 1.0), 4)
        )
        frame[f"structural_reduction_vs_{name}_pct"] = frame["structural_pivots_total"].map(
            lambda value, ref=reference: round(1.0 - float(value) / max(float(ref["structural_pivots_total"]), 1.0), 4)
        )
    frame["noise_cut_pct"] = frame["too_noisy_cuts"] / frame["cuts"].clip(lower=1)
    frame["sparse_cut_pct"] = frame["too_sparse_cuts"] / frame["cuts"].clip(lower=1)
    frame["unstable_cut_pct"] = frame["unstable_pivot_cuts"] / frame["cuts"].clip(lower=1)
    frame["late_cut_pct"] = frame["late_confirmation_cuts"] / frame["cuts"].clip(lower=1)
    frame["score"] = frame.apply(lag_stability_score, axis=1)
    frame["category"] = frame.apply(lag_stability_category, axis=1)
    frame["candidate_for_more_review"] = frame["category"] == "current_context_candidate_for_more_review"
    frame["rank"] = frame["score"].rank(method="first", ascending=False).astype(int)
    return frame.sort_values(["rank", "config_name"]).reset_index(drop=True)


def lag_stability_score(row: pd.Series) -> float:
    score = 100.0
    score -= float(row["noise_cut_pct"]) * 30.0
    score -= float(row["unstable_cut_pct"]) * 28.0
    score -= float(row["late_cut_pct"]) * 25.0
    score -= float(row["sparse_cut_pct"]) * 22.0
    score -= float(row["phase_change_pct_non_initial"]) * 8.0
    score -= min(float(row["abrupt_transition_count"]) * 2.5, 12.0)
    score -= max(0.0, float(row["completed_impulse_pct"]) - 0.65) * 35.0
    score -= max(0.0, float(row["unknown_pct"]) - 0.45) * 25.0
    structural_per_100 = float(row["structural_pivots_per_100_bars"])
    if structural_per_100 > 2.8:
        score -= (structural_per_100 - 2.8) * 12.0
    if structural_per_100 < 0.55:
        score -= (0.55 - structural_per_100) * 24.0
    median_lag = numeric_or_zero(row.get("median_confirmation_lag_bars", 0))
    max_lag = numeric_or_zero(row.get("max_confirmation_lag_bars", 0))
    score -= max(0.0, median_lag - 6.0) * 1.6
    score -= max(0.0, max_lag - 16.0) * 0.9
    if not bool(row["anti_lookahead_passed"]):
        score -= 100.0
    if not bool(row["hard_flags_fail_closed"]):
        score -= 100.0
    return round(score, 4)


def lag_stability_category(row: pd.Series) -> str:
    if not bool(row["anti_lookahead_passed"]) or not bool(row["hard_flags_fail_closed"]):
        return "blocked_for_sql_staging"
    noise = float(row["noise_cut_pct"])
    unstable = float(row["unstable_cut_pct"])
    late = float(row["late_cut_pct"])
    sparse = float(row["sparse_cut_pct"])
    completed = float(row["completed_impulse_pct"])
    if noise <= 0.25 and unstable < 0.25 and late < 0.50 and sparse <= 0.35 and completed <= 0.65:
        return "current_context_candidate_for_more_review"
    if noise <= 0.25 and sparse <= 0.35 and completed <= 0.70 and late >= 0.50 and unstable <= 0.55:
        return "late_context_only"
    if unstable > 0.55 or float(row["abrupt_transition_count"]) >= 5:
        return "manual_review_only"
    if noise > 0.25:
        return "needs_pivot_logic_redesign"
    return "needs_more_real_ohlc_review"


def build_lag_diagnostics_for_config(candidate: ParameterCandidate, result: Any) -> pd.DataFrame:
    merged = merge_pivot_context_transition(result)
    rows: list[dict[str, Any]] = []
    for record in merged.to_dict(orient="records"):
        max_lag = numeric_or_zero(record.get("max_confirmation_lag_bars", 0))
        median_lag = numeric_or_zero(record.get("median_confirmation_lag_bars", 0))
        late = bool(record.get("late_confirmation", False))
        rows.append(
            {
                "config_name": candidate.config_name,
                "symbol": record.get("symbol", ""),
                "market_group": record.get("market_group", ""),
                "cut_number": record.get("cut_number", ""),
                "as_of_bar_time": record.get("as_of_bar_time", ""),
                "median_confirmation_lag_bars": record.get("median_confirmation_lag_bars", ""),
                "max_confirmation_lag_bars": record.get("max_confirmation_lag_bars", ""),
                "late_confirmation": late,
                "structure_phase": record.get("structure_phase", ""),
                "interpretation": lag_interpretation(candidate, median_lag, max_lag, late),
            }
        )
    return pd.DataFrame(rows)


def build_stability_diagnostics_for_config(candidate: ParameterCandidate, result: Any) -> pd.DataFrame:
    merged = merge_pivot_context_transition(result)
    rows: list[dict[str, Any]] = []
    for record in merged.to_dict(orient="records"):
        unstable = bool(record.get("unstable_pivots", False))
        disappeared = int(record.get("disappeared_structural_pivots_vs_previous_cut", 0) or 0)
        transition = str(record.get("transition_type", ""))
        rows.append(
            {
                "config_name": candidate.config_name,
                "symbol": record.get("symbol", ""),
                "market_group": record.get("market_group", ""),
                "cut_number": record.get("cut_number", ""),
                "as_of_bar_time": record.get("as_of_bar_time", ""),
                "unstable_pivots": unstable,
                "new_structural_pivots_vs_previous_cut": record.get("new_structural_pivots_vs_previous_cut", ""),
                "disappeared_structural_pivots_vs_previous_cut": disappeared,
                "transition_type": transition,
                "structure_phase": record.get("structure_phase", ""),
                "interpretation": stability_interpretation(unstable, disappeared, transition),
            }
        )
    return pd.DataFrame(rows)


def merge_pivot_context_transition(result: Any) -> pd.DataFrame:
    pivot = result.pivot_stability_audit.copy()
    if pivot.empty:
        return pivot
    contexts = result.contexts[
        ["symbol", "market_group", "timeframe", "as_of_bar_time", "structure_phase", "hypothesis_status"]
    ].copy()
    transitions = result.label_transition_audit[
        ["symbol", "timeframe", "as_of_bar_time", "transition_type", "phase_changed"]
    ].copy()
    merged = pivot.merge(contexts, on=["symbol", "timeframe", "as_of_bar_time"], how="left")
    merged = merged.merge(transitions, on=["symbol", "timeframe", "as_of_bar_time"], how="left")
    return merged


def lag_interpretation(candidate: ParameterCandidate, median_lag: float, max_lag: float, late: bool) -> str:
    pivot = candidate.pivot_config
    structural = candidate.structural_config
    if not late:
        return "Lag stays inside current diagnostic threshold; review noise and stability next."
    drivers = []
    if pivot.confirmation_bars >= 8:
        drivers.append("confirmation_bars")
    if pivot.left_bars >= 8:
        drivers.append("left_bars")
    if pivot.min_bars_between_pivots >= 10:
        drivers.append("min_bars_between_pivots")
    if structural.min_leg_bars >= 28:
        drivers.append("min_leg_bars")
    if not drivers:
        drivers.append("pivot confirmation and structural compression")
    return (
        f"Late context; median_lag={median_lag:g}, max_lag={max_lag:g}. "
        f"Likely drivers: {', '.join(drivers)}."
    )


def stability_interpretation(unstable: bool, disappeared: int, transition: str) -> str:
    if unstable and disappeared:
        if transition in {"abrupt_reclassification", "regression_or_reclassification"}:
            return "Pivot replacement coincides with label churn; current-context use should be blocked."
        return "Structural pivots changed versus prior cut; append-only supersession would be required."
    if transition in {"abrupt_reclassification", "regression_or_reclassification"}:
        return "Label changed abruptly even without disappeared pivots; manual review is required."
    return "No disappearing structural pivots detected in this cut."


def build_lag_stability_candidate_evaluation(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for record in comparison.to_dict(orient="records"):
        failures = []
        if not bool(record["anti_lookahead_passed"]):
            failures.append("anti_lookahead_failed")
        if not bool(record["hard_flags_fail_closed"]):
            failures.append("hard_flags_not_fail_closed")
        if float(record["noise_cut_pct"]) > 0.25:
            failures.append("too_noisy_above_25pct")
        if float(record["sparse_cut_pct"]) > 0.35:
            failures.append("too_sparse_above_35pct")
        if float(record["late_cut_pct"]) >= 0.50:
            failures.append("late_confirmation_not_below_50pct")
        if float(record["unstable_cut_pct"]) >= 0.25:
            failures.append("unstable_not_below_25pct")
        if float(record["completed_impulse_pct"]) > 0.65:
            failures.append("completed_impulse_dominant")
        rows.append(
            {
                "config_name": record["config_name"],
                "config_family": record["config_family"],
                "score": record["score"],
                "rank": record["rank"],
                "category": record["category"],
                "current_context_candidate_for_more_review": record["category"] == "current_context_candidate_for_more_review",
                "failed_criteria": ";".join(failures),
                "sql_staging_allowed": False,
                "signals_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def build_lag_stability_visual_review(
    config: LagStabilityResolutionConfig,
    config_results: dict[str, Any],
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    selected = selected_visual_configs(comparison)
    chart_rows = write_charts(config, config_results, selected)
    if not chart_rows:
        return empty_visual_review()
    return pd.DataFrame(chart_rows)


def selected_visual_configs(comparison: pd.DataFrame) -> list[str]:
    top_mid = (
        comparison[comparison["config_name"].astype(str).str.startswith("time_mid_")]
        .sort_values("rank")
        .head(2)["config_name"]
        .astype(str)
        .tolist()
    )
    return list(dict.fromkeys(["time_hard_a", "time_hard_b", *top_mid]))


def empty_visual_review() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "chart_file",
            "config_name",
            "symbol",
            "market_group",
            "timeframe",
            "cut_number",
            "manual_readability",
            "lag_visual_concern",
            "stability_visual_concern",
            "notes",
        ]
    )


def write_charts(
    config: LagStabilityResolutionConfig,
    config_results: dict[str, Any],
    selected_configs: list[str],
) -> list[dict[str, Any]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    source = load_source_ohlc(config.source_csv)
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    wanted_symbols = ["EURUSD.r", "US500", "XAUUSD.r"]
    for name in selected_configs:
        result = config_results.get(name)
        if result is None:
            continue
        merged = merge_pivot_context_transition(result)
        if merged.empty:
            continue
        representatives = select_visual_representatives(merged, wanted_symbols)
        for record in representatives.to_dict(orient="records"):
            symbol = str(record["symbol"])
            timeframe = str(record["timeframe"])
            as_of = pd.Timestamp(record["as_of_bar_time"])
            cut_id = str(record["cut_id"])
            series = source[(source["symbol"] == symbol) & (source["timeframe"] == timeframe) & (source["time"] <= as_of)].tail(180)
            pivots = (
                result.structural_pivots[result.structural_pivots.get("cut_id", "") == cut_id]
                if not result.structural_pivots.empty
                else pd.DataFrame()
            )
            if series.empty:
                continue
            fig, ax = plt.subplots(figsize=(11, 5))
            ax.plot(series["time"], series["close"], color="#1f2937", linewidth=1.4, label="close")
            if not pivots.empty:
                pivot_times = pd.to_datetime(pivots["pivot_extreme_time"], errors="coerce")
                pivot_prices = pd.to_numeric(pivots["pivot_extreme_price"], errors="coerce")
                pivot_types = pivots["pivot_type"].astype(str)
                colors = pivot_types.map({"high": "#cc3311", "low": "#0077bb"}).fillna("#666666")
                ax.scatter(pivot_times, pivot_prices, c=colors, s=32, zorder=3, label="structural pivots")
            ax.axvline(as_of, color="#ee7733", linestyle="--", linewidth=1.1, label="as_of")
            ax.set_title(f"{name}: {symbol} {timeframe} cut {record['cut_number']} {record['structure_phase']}")
            ax.grid(axis="y", alpha=0.25)
            ax.legend(loc="best")
            fig.autofmt_xdate()
            fig.tight_layout()
            path = chart_dir / f"{name}_{safe_id(symbol)}_{timeframe}_cut{int(record['cut_number']):02d}.png"
            fig.savefig(path, dpi=130)
            plt.close(fig)
            rows.append(
                {
                    "chart_file": str(path),
                    "config_name": name,
                    "symbol": symbol,
                    "market_group": record.get("market_group", ""),
                    "timeframe": timeframe,
                    "cut_number": record.get("cut_number", ""),
                    "manual_readability": visual_readability(record),
                    "lag_visual_concern": "high" if bool(record.get("late_confirmation", False)) else "moderate",
                    "stability_visual_concern": "high" if bool(record.get("unstable_pivots", False)) else "low",
                    "notes": "Lightweight chart review for lag/stability only; not edge validation.",
                }
            )
    return rows


def select_visual_representatives(frame: pd.DataFrame, wanted_symbols: list[str]) -> pd.DataFrame:
    rows = []
    for symbol in wanted_symbols:
        part = frame[frame["symbol"].astype(str) == symbol]
        if part.empty:
            continue
        problem = part[(part["unstable_pivots"].astype(bool)) | (part["late_confirmation"].astype(bool))]
        rows.append((problem if not problem.empty else part).tail(1).iloc[0])
    if not rows:
        rows = [row for _, row in frame.tail(3).iterrows()]
    return pd.DataFrame(rows).head(3)


def visual_readability(record: dict[str, Any]) -> str:
    if bool(record.get("too_noisy", False)):
        return "too_noisy"
    if bool(record.get("too_sparse", False)):
        return "too_sparse"
    if bool(record.get("late_confirmation", False)) and bool(record.get("unstable_pivots", False)):
        return "late_but_unstable"
    if bool(record.get("late_confirmation", False)):
        return "late_but_readable"
    return "readable"


def build_decision_summary(
    comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    market_group: pd.DataFrame,
    visual_review: pd.DataFrame,
) -> pd.DataFrame:
    current = candidate_evaluation[candidate_evaluation["category"] == "current_context_candidate_for_more_review"]
    best = comparison.iloc[0]
    if not current.empty:
        decision = "current_context_candidate_for_more_review"
        selected = str(current.sort_values("rank").iloc[0]["config_name"])
        rationale = "A focused intermediate configuration reduces lag/instability enough for another non-operative current-context review."
    elif str(best["category"]) == "late_context_only":
        decision = "late_context_only"
        selected = str(best["config_name"])
        rationale = "Best readable configuration still relies on late confirmation; it should be treated as confirmed-late context, not fresh current context."
    elif str(best["category"]) == "manual_review_only":
        decision = "manual_review_only"
        selected = str(best["config_name"])
        rationale = "Best configuration remains too unstable for current context and should stay in manual study."
    elif str(best["category"]) == "needs_pivot_logic_redesign":
        decision = "needs_pivot_logic_redesign"
        selected = str(best["config_name"])
        rationale = "Focused parameter changes do not solve the noise/lag/stability trade-off; pivot compression logic should be redesigned."
    else:
        decision = "needs_more_real_ohlc_review"
        selected = str(best["config_name"])
        rationale = "Metrics improve but not enough to decide current vs late context across the reviewed sample."
    return pd.DataFrame(
        [
            {
                "decision": decision,
                "selected_config": selected,
                "selected_category": str(best["category"]),
                "best_score": float(best["score"]),
                "late_confirmation_pct": float(best["late_cut_pct"]),
                "unstable_pivots_pct": float(best["unstable_cut_pct"]),
                "too_noisy_pct": float(best["noise_cut_pct"]),
                "visual_rows": int(len(visual_review)),
                "sql_staging_allowed": False,
                "dashboard_allowed": False,
                "signals_allowed": False,
                "rationale": rationale,
            }
        ]
    )


def build_issues_or_risks(
    comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    decision_summary: pd.DataFrame,
) -> pd.DataFrame:
    best = comparison.iloc[0]
    selected = str(decision_summary.iloc[0]["selected_config"])
    selected_eval = candidate_evaluation[candidate_evaluation["config_name"] == selected].iloc[0]
    rows = [
        {
            "severity": "info",
            "risk": "non_operational_review",
            "description": "Lag/stability resolution uses local OHLC cuts only; no backtest, no SQL and no signal generation.",
            "recommendation": "Keep WaveCount live out of dashboard/Telegram/bot until a category is accepted.",
        },
        {
            "severity": "medium" if float(best["late_cut_pct"]) >= 0.5 else "low",
            "risk": "late_confirmation",
            "description": f"Best config `{best['config_name']}` has late_confirmation in {best['late_cut_pct']:.1%} of cuts.",
            "recommendation": "If late remains high, display only as late/stale context.",
        },
        {
            "severity": "medium" if float(best["unstable_cut_pct"]) >= 0.25 else "low",
            "risk": "unstable_pivots",
            "description": f"Best config `{best['config_name']}` has unstable pivots in {best['unstable_cut_pct']:.1%} of cuts.",
            "recommendation": "Require append-only supersession metadata and manual review before SQL.",
        },
        {
            "severity": "medium" if float(best["noise_cut_pct"]) > 0.25 else "low",
            "risk": "remaining_noise",
            "description": f"Best config `{best['config_name']}` has too_noisy in {best['noise_cut_pct']:.1%} of cuts.",
            "recommendation": "Do not solve lag by accepting noisy pivots as current context.",
        },
        {
            "severity": "blocking" if str(selected_eval["category"]) not in {"current_context_candidate_for_more_review", "late_context_only"} else "medium",
            "risk": "category_limit",
            "description": f"Selected config `{selected}` category is `{selected_eval['category']}`.",
            "recommendation": "Current SQL/dashboard staging remains blocked in this phase.",
        },
    ]
    return pd.DataFrame(rows)


def build_run_meta(
    *,
    generated_at: str,
    config: LagStabilityResolutionConfig,
    candidates: list[ParameterCandidate],
    config_comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    decision_summary: pd.DataFrame,
    decision: str,
    visual_review: pd.DataFrame,
) -> dict[str, Any]:
    best = config_comparison.iloc[0].to_dict()
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_lag_stability_resolution",
        "source_csv": str(config.source_csv),
        "symbols": list(config.symbols),
        "timeframes": [config.timeframe],
        "config_count": len(candidates),
        "cut_count_per_config": config.cut_count * min(config.max_symbols, len(config.symbols)),
        "decision": decision,
        "best_config": best,
        "decision_summary": decision_summary.iloc[0].to_dict(),
        "candidate_evaluation": candidate_evaluation[["config_name", "rank", "category", "failed_criteria"]].to_dict(orient="records"),
        "visual_review_rows": int(len(visual_review)),
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
            "Parameter lag/stability review only; no PnL, no backtest and no signal generation.",
            "No defaults are changed in the WaveCount live engine.",
            "Any selected configuration is contextual and non-operative.",
        ],
    }


def write_outputs(
    *,
    config: LagStabilityResolutionConfig,
    parameter_grid: pd.DataFrame,
    config_comparison: pd.DataFrame,
    phase_distribution: pd.DataFrame,
    pivot_stability: pd.DataFrame,
    label_transition: pd.DataFrame,
    anti_lookahead: pd.DataFrame,
    market_group: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    lag_diagnostics: pd.DataFrame,
    stability_diagnostics: pd.DataFrame,
    visual_review: pd.DataFrame,
    decision_summary: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "lag_diagnostics": output_dir / "lag_diagnostics.csv",
        "stability_diagnostics": output_dir / "stability_diagnostics.csv",
        "lag_stability_parameter_grid": output_dir / "lag_stability_parameter_grid.csv",
        "lag_stability_config_comparison": output_dir / "lag_stability_config_comparison.csv",
        "phase_distribution_by_config": output_dir / "phase_distribution_by_config.csv",
        "pivot_stability_by_config": output_dir / "pivot_stability_by_config.csv",
        "label_transition_by_config": output_dir / "label_transition_by_config.csv",
        "anti_lookahead_by_config": output_dir / "anti_lookahead_by_config.csv",
        "lag_stability_market_group": output_dir / "lag_stability_market_group.csv",
        "lag_stability_candidate_evaluation": output_dir / "lag_stability_candidate_evaluation.csv",
        "lag_stability_visual_review": output_dir / "lag_stability_visual_review.csv",
        "decision_summary": output_dir / "decision_summary.csv",
        "issues_or_risks": output_dir / "issues_or_risks.csv",
        "run_meta": output_dir / "run_meta.json",
    }
    lag_diagnostics.to_csv(paths["lag_diagnostics"], index=False)
    stability_diagnostics.to_csv(paths["stability_diagnostics"], index=False)
    parameter_grid.to_csv(paths["lag_stability_parameter_grid"], index=False)
    config_comparison.to_csv(paths["lag_stability_config_comparison"], index=False)
    phase_distribution.to_csv(paths["phase_distribution_by_config"], index=False)
    pivot_stability.to_csv(paths["pivot_stability_by_config"], index=False)
    label_transition.to_csv(paths["label_transition_by_config"], index=False)
    anti_lookahead.to_csv(paths["anti_lookahead_by_config"], index=False)
    market_group.to_csv(paths["lag_stability_market_group"], index=False)
    candidate_evaluation.to_csv(paths["lag_stability_candidate_evaluation"], index=False)
    visual_review.to_csv(paths["lag_stability_visual_review"], index=False)
    decision_summary.to_csv(paths["decision_summary"], index=False)
    issues_or_risks.to_csv(paths["issues_or_risks"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    *,
    config: LagStabilityResolutionConfig,
    config_comparison: pd.DataFrame,
    market_group: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    decision_summary: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    decision: str,
) -> None:
    selected = str(decision_summary.iloc[0]["selected_config"])
    doc = f"""# WaveCount Live Lag/Stability Resolution

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Configuracion seleccionada para interpretar esta fase: `{selected}`.

Esta revision intenta resolver o acotar el trade-off entre lag e inestabilidad
de `wavecount_live_context_v0`. No es un backtest, no usa PnL, no genera
senales, no filtra ENBOLSA, no toca SQL real y no cambia defaults globales del
motor.

## Que Se Probo

Se comparan `baseline_actual`, `very_conservative_diagnostic`, `time_hard_a`,
`time_hard_b` y cinco configuraciones intermedias `time_mid_*`.

## Comparacion Lag/Estabilidad

{markdown_table(config_comparison)}

## Evaluacion De Categorias

{markdown_table(candidate_evaluation)}

## Sensibilidad Por Grupo De Mercado

{markdown_table(market_group)}

## Decision Summary

{markdown_table(decision_summary)}

## Riesgos

{markdown_table(issues_or_risks)}

## Interpretacion

- `current_context_candidate_for_more_review` no es una candidata operativa:
  solo permitiria otra revision tecnica no operativa.
- `late_context_only` significa que la lectura puede ser legible pero llega
  demasiado tarde para mostrarse como estado estructural fresco.
- `manual_review_only` limita WaveCount live a estudio visual/manual.
- `needs_pivot_logic_redesign` indica que los parametros no resuelven el
  problema principal y conviene redisenar compresion/estabilidad.

## Que Sigue Bloqueado

- SQL staging de WaveCount live.
- Dashboard con WaveCount live.
- Telegram y bot.
- MT5.
- Cualquier senal o filtro operativo basado en WaveCount.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_LAG_STABILITY_RESOLUTION.md").write_text(doc, encoding="utf-8")


def numeric_or_zero(value: Any) -> float:
    try:
        if value == "":
            return 0.0
        parsed = float(value)
        return 0.0 if pd.isna(parsed) else parsed
    except Exception:
        return 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve WaveCount live lag/stability trade-off without operational use.")
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--higher-timeframe", default=DEFAULT_HIGHER_TIMEFRAME)
    parser.add_argument("--cut-count", type=int, default=10)
    parser.add_argument("--min-bars-first-cut", type=int, default=40)
    parser.add_argument("--max-symbols", type=int, default=4)
    parser.add_argument("--config-names", default="")
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    symbols = tuple(symbol.strip() for symbol in args.symbols.split(",") if symbol.strip())
    config_names = tuple(name.strip() for name in args.config_names.split(",") if name.strip()) or None
    result = build_lag_stability_resolution(
        LagStabilityResolutionConfig(
            source_csv=args.source_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            symbols=symbols,
            timeframe=args.timeframe,
            higher_timeframe=args.higher_timeframe,
            cut_count=args.cut_count,
            min_bars_first_cut=args.min_bars_first_cut,
            max_symbols=args.max_symbols,
            config_names=config_names,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "selected_config": result.decision_summary.iloc[0]["selected_config"],
                "config_count": int(len(result.parameter_grid)),
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
