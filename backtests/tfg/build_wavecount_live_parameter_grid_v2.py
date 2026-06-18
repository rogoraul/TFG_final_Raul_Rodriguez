from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

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


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_parameter_grid_v2_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_PARAMETER_GRID_V2.md")


@dataclass(frozen=True)
class ParameterGridV2Config:
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
class ParameterGridV2Result:
    parameter_grid: pd.DataFrame
    config_comparison: pd.DataFrame
    phase_distribution: pd.DataFrame
    pivot_stability: pd.DataFrame
    label_transition: pd.DataFrame
    anti_lookahead: pd.DataFrame
    market_group_sensitivity: pd.DataFrame
    candidate_evaluation: pd.DataFrame
    recommended_next_action: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_parameter_grid_v2(config: ParameterGridV2Config | None = None) -> ParameterGridV2Result:
    config = config or ParameterGridV2Config()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    candidates = filter_candidates(default_parameter_grid_v2_candidates(), config.config_names)
    if not candidates:
        raise ValueError("no parameter grid v2 candidates selected")

    parameter_grid = parameter_grid_frame(candidates)
    parameter_grid = add_family_to_grid(parameter_grid)
    summary_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    pivot_frames: list[pd.DataFrame] = []
    transition_frames: list[pd.DataFrame] = []
    anti_rows: list[dict[str, Any]] = []
    sensitivity_frames: list[pd.DataFrame] = []
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

        pivot_stability = result.pivot_stability_audit.copy()
        pivot_stability.insert(0, "config_name", candidate.config_name)
        pivot_frames.append(pivot_stability)

        transitions = result.label_transition_audit.copy()
        transitions.insert(0, "config_name", candidate.config_name)
        transition_frames.append(transitions)

        anti_rows.append(anti_lookahead_row(candidate.config_name, result))
        sensitivity_frames.append(market_group_sensitivity_rows(candidate.config_name, result))

    parameter_summary = pd.DataFrame(summary_rows)
    config_comparison = build_config_comparison_v2(parameter_summary)
    phase_distribution = pd.DataFrame(phase_rows)
    pivot_stability = concat_or_empty(pivot_frames)
    label_transition = concat_or_empty(transition_frames)
    anti_lookahead = pd.DataFrame(anti_rows)
    market_group_sensitivity = concat_or_empty(sensitivity_frames)
    candidate_evaluation = build_candidate_evaluation(config_comparison)
    recommended_next_action = build_recommended_next_action(config_comparison, candidate_evaluation, market_group_sensitivity)
    issues_or_risks = build_issues_or_risks_v2(config_comparison, candidate_evaluation, market_group_sensitivity)
    decision = decide_final_v2(candidate_evaluation, issues_or_risks, market_group_sensitivity)
    run_meta = build_run_meta_v2(
        generated_at=generated_at,
        config=config,
        candidates=candidates,
        config_comparison=config_comparison,
        candidate_evaluation=candidate_evaluation,
        recommended_next_action=recommended_next_action,
        decision=decision,
    )
    written = write_outputs_v2(
        config=config,
        parameter_grid=parameter_grid,
        config_comparison=config_comparison,
        phase_distribution=phase_distribution,
        pivot_stability=pivot_stability,
        label_transition=label_transition,
        anti_lookahead=anti_lookahead,
        market_group_sensitivity=market_group_sensitivity,
        candidate_evaluation=candidate_evaluation,
        recommended_next_action=recommended_next_action,
        issues_or_risks=issues_or_risks,
        run_meta=run_meta,
    )
    if config.generate_charts:
        chart_files = write_grid_v2_charts(config, config_results, config_comparison)
        if chart_files:
            run_meta["chart_files"] = [str(path) for path in chart_files]
            (config.output_dir / "run_meta.json").write_text(
                json.dumps(run_meta, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            written["charts"] = config.output_dir / "charts"
    write_docs_v2(
        config=config,
        parameter_grid=parameter_grid,
        config_comparison=config_comparison,
        candidate_evaluation=candidate_evaluation,
        recommended_next_action=recommended_next_action,
        issues_or_risks=issues_or_risks,
        market_group_sensitivity=market_group_sensitivity,
        decision=decision,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_PARAMETER_GRID_V2.md"
    return ParameterGridV2Result(
        parameter_grid=parameter_grid,
        config_comparison=config_comparison,
        phase_distribution=phase_distribution,
        pivot_stability=pivot_stability,
        label_transition=label_transition,
        anti_lookahead=anti_lookahead,
        market_group_sensitivity=market_group_sensitivity,
        candidate_evaluation=candidate_evaluation,
        recommended_next_action=recommended_next_action,
        issues_or_risks=issues_or_risks,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def default_parameter_grid_v2_candidates() -> list[ParameterCandidate]:
    return [
        ParameterCandidate(
            config_name="baseline_actual",
            description="Baseline from the real OHLC cut review.",
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
            config_name="atr_hard_a",
            description="ATR-led filter: stronger raw and structural ATR thresholds.",
            pivot_config=PivotConfig(
                left_bars=6,
                confirmation_bars=6,
                atr_period=20,
                min_atr_multiplier=3.0,
                min_relative_move_pct=0.0045,
                min_bars_between_pivots=7,
                candidate_lookback_bars=8,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=10.0,
                min_leg_relative_move_pct=0.014,
                min_leg_bars=20,
            ),
        ),
        ParameterCandidate(
            config_name="atr_hard_b",
            description="ATR-led filter with wider ATR period and larger legs.",
            pivot_config=PivotConfig(
                left_bars=6,
                confirmation_bars=6,
                atr_period=28,
                min_atr_multiplier=3.5,
                min_relative_move_pct=0.005,
                min_bars_between_pivots=8,
                candidate_lookback_bars=9,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=12.0,
                min_leg_relative_move_pct=0.016,
                min_leg_bars=22,
            ),
        ),
        ParameterCandidate(
            config_name="time_hard_a",
            description="Time-led filter: wider pivot window and longer spacing.",
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
            description="Time-led diagnostic with high confirmation latency.",
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
            config_name="mixed_balanced_a",
            description="Mixed ATR/time filter, less extreme than the hard diagnostics.",
            pivot_config=PivotConfig(
                left_bars=7,
                confirmation_bars=7,
                atr_period=24,
                min_atr_multiplier=2.75,
                min_relative_move_pct=0.0045,
                min_bars_between_pivots=9,
                candidate_lookback_bars=9,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=9.0,
                min_leg_relative_move_pct=0.014,
                min_leg_bars=26,
            ),
        ),
        ParameterCandidate(
            config_name="mixed_balanced_b",
            description="Mixed filter with stricter relative and structural thresholds.",
            pivot_config=PivotConfig(
                left_bars=8,
                confirmation_bars=7,
                atr_period=24,
                min_atr_multiplier=3.0,
                min_relative_move_pct=0.0055,
                min_bars_between_pivots=10,
                candidate_lookback_bars=10,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=10.0,
                min_leg_relative_move_pct=0.017,
                min_leg_bars=30,
            ),
        ),
        ParameterCandidate(
            config_name="compression_hard_a",
            description="Compression-led filter: baseline raw pivots with stricter structural legs.",
            pivot_config=PivotConfig(),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=12.0,
                min_leg_relative_move_pct=0.018,
                min_leg_bars=28,
            ),
        ),
        ParameterCandidate(
            config_name="compression_hard_b",
            description="Compression-led filter starting from v1 diagnostic raw pivots.",
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
                min_leg_atr_multiplier=14.0,
                min_leg_relative_move_pct=0.02,
                min_leg_bars=32,
            ),
        ),
        ParameterCandidate(
            config_name="compression_hard_c",
            description="Very hard structural compression to test whether labels collapse.",
            pivot_config=PivotConfig(
                left_bars=7,
                confirmation_bars=7,
                atr_period=24,
                min_atr_multiplier=2.5,
                min_relative_move_pct=0.005,
                min_bars_between_pivots=8,
                candidate_lookback_bars=9,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=16.0,
                min_leg_relative_move_pct=0.024,
                min_leg_bars=40,
            ),
        ),
        ParameterCandidate(
            config_name="market_group_probe",
            description="Diagnostic middle ground to inspect whether one global setting is viable by market group.",
            pivot_config=PivotConfig(
                left_bars=8,
                confirmation_bars=8,
                atr_period=28,
                min_atr_multiplier=3.25,
                min_relative_move_pct=0.006,
                min_bars_between_pivots=10,
                candidate_lookback_bars=11,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=11.0,
                min_leg_relative_move_pct=0.018,
                min_leg_bars=34,
            ),
        ),
    ]


def add_family_to_grid(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.insert(1, "config_family", result["config_name"].map(config_family))
    return result


def config_family(config_name: str) -> str:
    if config_name == "baseline_actual":
        return "baseline"
    if config_name == "very_conservative_diagnostic":
        return "v1_best_diagnostic"
    if config_name.startswith("atr_"):
        return "atr_filter"
    if config_name.startswith("time_"):
        return "time_filter"
    if config_name.startswith("mixed_"):
        return "mixed_filter"
    if config_name.startswith("compression_"):
        return "structural_compression"
    if config_name.startswith("market_group_"):
        return "market_group_probe"
    return "other"


def build_config_comparison_v2(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    if frame.empty:
        return frame
    baseline = frame[frame["config_name"] == "baseline_actual"].iloc[0] if "baseline_actual" in set(frame["config_name"]) else frame.iloc[0]
    v1_best = (
        frame[frame["config_name"] == "very_conservative_diagnostic"].iloc[0]
        if "very_conservative_diagnostic" in set(frame["config_name"])
        else baseline
    )
    frame["config_family"] = frame["config_name"].map(config_family)
    frame["detected_reduction_vs_baseline_pct"] = frame["detected_pivots_total"].map(
        lambda value: round(1.0 - float(value) / max(float(baseline["detected_pivots_total"]), 1.0), 4)
    )
    frame["structural_reduction_vs_baseline_pct"] = frame["structural_pivots_total"].map(
        lambda value: round(1.0 - float(value) / max(float(baseline["structural_pivots_total"]), 1.0), 4)
    )
    frame["detected_reduction_vs_v1_best_pct"] = frame["detected_pivots_total"].map(
        lambda value: round(1.0 - float(value) / max(float(v1_best["detected_pivots_total"]), 1.0), 4)
    )
    frame["structural_reduction_vs_v1_best_pct"] = frame["structural_pivots_total"].map(
        lambda value: round(1.0 - float(value) / max(float(v1_best["structural_pivots_total"]), 1.0), 4)
    )
    frame["noise_cut_pct"] = frame["too_noisy_cuts"] / frame["cuts"].clip(lower=1)
    frame["sparse_cut_pct"] = frame["too_sparse_cuts"] / frame["cuts"].clip(lower=1)
    frame["unstable_cut_pct"] = frame["unstable_pivot_cuts"] / frame["cuts"].clip(lower=1)
    frame["late_cut_pct"] = frame["late_confirmation_cuts"] / frame["cuts"].clip(lower=1)
    frame["score"] = frame.apply(readability_score_v2, axis=1)
    frame["candidate_pass"] = frame.apply(candidate_pass_v2, axis=1)
    frame["rank"] = frame["score"].rank(method="first", ascending=False).astype(int)
    return frame.sort_values(["rank", "config_name"]).reset_index(drop=True)


def readability_score_v2(row: pd.Series) -> float:
    score = 100.0
    score -= float(row["noise_cut_pct"]) * 35.0
    score -= float(row["sparse_cut_pct"]) * 28.0
    score -= float(row["unstable_cut_pct"]) * 18.0
    score -= float(row["late_cut_pct"]) * 12.0
    score -= float(row["phase_change_pct_non_initial"]) * 10.0
    score -= min(float(row["abrupt_transition_count"]) * 2.0, 12.0)
    score -= max(0.0, float(row["completed_impulse_pct"]) - 0.6) * 32.0
    score -= max(0.0, float(row["unknown_pct"]) - 0.45) * 22.0
    score -= max(0.0, float(row["ambiguous_pct"]) - 0.35) * 16.0
    structural_per_100 = float(row["structural_pivots_per_100_bars"])
    if structural_per_100 > 2.8:
        score -= (structural_per_100 - 2.8) * 12.0
    if structural_per_100 < 0.55:
        score -= (0.55 - structural_per_100) * 24.0
    if not bool(row["anti_lookahead_passed"]):
        score -= 100.0
    if not bool(row["hard_flags_fail_closed"]):
        score -= 100.0
    return round(score, 4)


def candidate_pass_v2(row: pd.Series) -> bool:
    return bool(
        row["anti_lookahead_passed"]
        and row["hard_flags_fail_closed"]
        and float(row["noise_cut_pct"]) <= 0.25
        and float(row["sparse_cut_pct"]) <= 0.35
        and float(row["completed_impulse_pct"]) <= 0.65
        and float(row["late_cut_pct"]) <= 0.5
        and float(row["unknown_pct"]) <= 0.45
        and float(row["ambiguous_pct"]) <= 0.35
        and float(row["unstable_cut_pct"]) <= 0.25
        and float(row["structural_pivots_per_100_bars"]) <= 2.8
        and float(row["structural_pivots_per_100_bars"]) >= 0.55
    )


def market_group_sensitivity_rows(config_name: str, result: Any) -> pd.DataFrame:
    pivot = result.pivot_stability_audit.copy()
    contexts = result.contexts.copy()
    if pivot.empty:
        return pd.DataFrame()
    merged = pivot.merge(
        contexts[["symbol", "timeframe", "as_of_bar_time", "market_group", "structure_phase", "hypothesis_status"]],
        on=["symbol", "timeframe", "as_of_bar_time"],
        how="left",
    )
    rows = []
    for group, part in merged.groupby("market_group", dropna=False):
        bars_used = int(part["bars_used"].astype(int).sum())
        detected = int(part["detected_pivots"].astype(int).sum())
        structural = int(part["structural_pivots"].astype(int).sum())
        rows.append(
            {
                "config_name": config_name,
                "market_group": str(group),
                "cuts": int(len(part)),
                "bars_used_total": bars_used,
                "detected_pivots_total": detected,
                "structural_pivots_total": structural,
                "detected_pivots_per_100_bars": round(detected / bars_used * 100, 4) if bars_used else 0.0,
                "structural_pivots_per_100_bars": round(structural / bars_used * 100, 4) if bars_used else 0.0,
                "too_noisy_cuts": int(part["too_noisy"].astype(bool).sum()),
                "too_noisy_pct": round(float(part["too_noisy"].astype(bool).mean()), 4),
                "unstable_pivot_cuts": int(part["unstable_pivots"].astype(bool).sum()),
                "unstable_pct": round(float(part["unstable_pivots"].astype(bool).mean()), 4),
                "completed_impulse_pct": round(float((part["structure_phase"] == "completed_impulse_candidate").mean()), 4),
                "unknown_pct": round(float((part["structure_phase"] == "unknown").mean()), 4),
                "ambiguous_pct": round(float((part["structure_phase"] == "ambiguous").mean()), 4),
            }
        )
    return pd.DataFrame(rows)


def build_candidate_evaluation(comparison: pd.DataFrame) -> pd.DataFrame:
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
        if float(record["late_cut_pct"]) > 0.5:
            failures.append("late_confirmation_above_50pct")
        if float(record["completed_impulse_pct"]) > 0.65:
            failures.append("completed_impulse_dominant")
        if float(record["unknown_pct"]) > 0.45:
            failures.append("unknown_dominant")
        if float(record["ambiguous_pct"]) > 0.35:
            failures.append("ambiguous_dominant")
        if float(record["unstable_cut_pct"]) > 0.25:
            failures.append("unstable_above_25pct")
        structural_density = float(record["structural_pivots_per_100_bars"])
        if structural_density > 2.8:
            failures.append("structural_density_too_high")
        if structural_density < 0.55:
            failures.append("structural_density_too_low")
        rows.append(
            {
                "config_name": record["config_name"],
                "config_family": record["config_family"],
                "score": record["score"],
                "rank": record["rank"],
                "candidate_pass": not failures,
                "failed_criteria": ";".join(failures),
                "candidate_label": "candidate_live_readability_config_v0" if not failures else "not_candidate",
            }
        )
    return pd.DataFrame(rows)


def build_recommended_next_action(
    comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    market_group_sensitivity: pd.DataFrame,
) -> pd.DataFrame:
    passing = candidate_evaluation[candidate_evaluation["candidate_pass"].astype(bool)]
    best = comparison.iloc[0]
    if not passing.empty:
        action = "promote_candidate_to_manual_visual_review"
        rationale = "A configuration meets technical thresholds, but still requires manual chart review before SQL staging."
        selected = str(passing.sort_values("rank").iloc[0]["config_name"])
    else:
        selected = str(best["config_name"])
        if needs_market_group_specific_review(market_group_sensitivity, selected):
            action = "needs_market_group_specific_review"
            rationale = "The best global configuration behaves unevenly across market groups; inspect per-group settings before redesign."
        elif best["config_family"] == "structural_compression" and float(best["noise_cut_pct"]) > 0.25:
            action = "needs_pivot_compression_redesign"
            rationale = "Harder compression improves score but raw/noisy cuts remain above candidate threshold."
        elif float(best["noise_cut_pct"]) > 0.25:
            action = "needs_pivot_compression_redesign"
            rationale = "No parameter-only configuration reduces noisy cuts enough; compression semantics need redesign."
        else:
            action = "needs_more_real_ohlc_review"
            rationale = "Metrics improve but do not yet justify a stable global candidate."
    return pd.DataFrame(
        [
            {
                "selected_config": selected,
                "recommended_action": action,
                "rationale": rationale,
                "sql_staging_allowed": False if action != "promote_candidate_to_manual_visual_review" else False,
                "dashboard_allowed": False,
                "signals_allowed": False,
            }
        ]
    )


def needs_market_group_specific_review(market_group_sensitivity: pd.DataFrame, config_name: str) -> bool:
    part = market_group_sensitivity[market_group_sensitivity["config_name"] == config_name]
    if len(part) < 2:
        return False
    noise_range = float(part["too_noisy_pct"].max() - part["too_noisy_pct"].min())
    structural_range = float(part["structural_pivots_per_100_bars"].max() - part["structural_pivots_per_100_bars"].min())
    completed_range = float(part["completed_impulse_pct"].max() - part["completed_impulse_pct"].min())
    return noise_range >= 0.5 or structural_range >= 1.2 or completed_range >= 0.5


def build_issues_or_risks_v2(
    comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    market_group_sensitivity: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    best = comparison.iloc[0]
    baseline = comparison[comparison["config_name"] == "baseline_actual"].iloc[0]
    v1_best = (
        comparison[comparison["config_name"] == "very_conservative_diagnostic"].iloc[0]
        if "very_conservative_diagnostic" in set(comparison["config_name"])
        else comparison.iloc[0]
    )
    best_eval = candidate_evaluation[candidate_evaluation["config_name"] == best["config_name"]].iloc[0]
    rows.append(
        {
            "severity": "info",
            "risk": "baseline_reference",
            "description": (
                f"Baseline has {int(baseline['detected_pivots_total'])} raw pivots, "
                f"{int(baseline['structural_pivots_total'])} structural pivots and "
                f"{baseline['completed_impulse_pct']:.1%} completed impulse rows."
            ),
            "recommendation": "Use baseline only as a noise reference, never as live config.",
        }
    )
    rows.append(
        {
            "severity": "info",
            "risk": "v1_best_reference",
            "description": (
                f"V1 best `{v1_best['config_name']}` has {int(v1_best['detected_pivots_total'])} raw pivots, "
                f"{int(v1_best['structural_pivots_total'])} structural pivots and "
                f"{v1_best['noise_cut_pct']:.1%} noisy cuts."
            ),
            "recommendation": "Require clear improvement versus v1 best before any promotion.",
        }
    )
    rows.append(
        {
            "severity": "info" if bool(best_eval["candidate_pass"]) else "medium",
            "risk": "candidate_quality",
            "description": (
                f"Best v2 config `{best['config_name']}` score={best['score']}, "
                f"candidate_pass={bool(best_eval['candidate_pass'])}, failed={best_eval['failed_criteria']}."
            ),
            "recommendation": "Do not move to SQL/dashboard unless candidate_pass=true and visual review passes.",
        }
    )
    if float(best["noise_cut_pct"]) > 0.25:
        rows.append(
            {
                "severity": "medium",
                "risk": "remaining_noise",
                "description": f"Best config still has too_noisy in {best['noise_cut_pct']:.1%} of cuts.",
                "recommendation": "Prefer pivot compression redesign over more parameter tightening if this persists.",
            }
        )
    if float(best["sparse_cut_pct"]) > 0.35:
        rows.append(
            {
                "severity": "medium",
                "risk": "over_filtering",
                "description": f"Best config is too_sparse in {best['sparse_cut_pct']:.1%} of cuts.",
                "recommendation": "Avoid solving noise by making the context unreadably sparse.",
            }
        )
    if float(best["late_cut_pct"]) > 0.5:
        rows.append(
            {
                "severity": "medium",
                "risk": "late_confirmation",
                "description": f"Best config has late_confirmation in {best['late_cut_pct']:.1%} of cuts.",
                "recommendation": "Do not accept a noise fix that only works by delaying labels too much.",
            }
        )
    if needs_market_group_specific_review(market_group_sensitivity, str(best["config_name"])):
        rows.append(
            {
                "severity": "medium",
                "risk": "market_group_sensitivity",
                "description": "Best global config behaves unevenly across Forex/Index/Metals.",
                "recommendation": "Review whether one global configuration is realistic before SQL staging.",
            }
        )
    rows.append(
        {
            "severity": "medium",
            "risk": "visual_review_required",
            "description": "Charts are lightweight diagnostics only.",
            "recommendation": "Inspect representative pivots manually before promoting any config.",
        }
    )
    return pd.DataFrame(rows)


def decide_final_v2(
    candidate_evaluation: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    market_group_sensitivity: pd.DataFrame,
) -> str:
    if (issues_or_risks["severity"] == "blocking").any():
        return "blocked_for_sql_staging"
    if candidate_evaluation["candidate_pass"].astype(bool).any():
        return "candidate_live_readability_config_v0"
    best = candidate_evaluation.sort_values("rank").iloc[0]
    if needs_market_group_specific_review(market_group_sensitivity, str(best["config_name"])):
        return "needs_market_group_specific_review"
    risks = set(issues_or_risks.loc[issues_or_risks["severity"] == "medium", "risk"])
    if "remaining_noise" in risks or "over_filtering" in risks:
        return "needs_pivot_compression_redesign"
    return "needs_more_real_ohlc_review"


def build_run_meta_v2(
    *,
    generated_at: str,
    config: ParameterGridV2Config,
    candidates: list[ParameterCandidate],
    config_comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    recommended_next_action: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    best_name = str(candidate_evaluation.sort_values("rank").iloc[0]["config_name"])
    best = config_comparison[config_comparison["config_name"] == best_name].iloc[0].to_dict()
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_parameter_grid_v2",
        "source_csv": str(config.source_csv),
        "symbols": list(config.symbols),
        "timeframes": [config.timeframe],
        "config_count": len(candidates),
        "cut_count_per_config": config.cut_count * min(config.max_symbols, len(config.symbols)),
        "decision": decision,
        "best_config": best,
        "recommended_next_action": recommended_next_action.iloc[0].to_dict(),
        "comparison": config_comparison[["config_name", "config_family", "score", "rank", "candidate_pass"]].to_dict(orient="records"),
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
            "Parameter and compression review only; no PnL, no backtest and no signal generation.",
            "Any candidate would be technical readability only, not WaveCount 2.5.6 policy.",
            "Charts are lightweight diagnostics, not manual validation closure.",
        ],
    }


def write_outputs_v2(
    *,
    config: ParameterGridV2Config,
    parameter_grid: pd.DataFrame,
    config_comparison: pd.DataFrame,
    phase_distribution: pd.DataFrame,
    pivot_stability: pd.DataFrame,
    label_transition: pd.DataFrame,
    anti_lookahead: pd.DataFrame,
    market_group_sensitivity: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    recommended_next_action: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "parameter_grid_v2": output_dir / "parameter_grid_v2.csv",
        "config_comparison_v2": output_dir / "config_comparison_v2.csv",
        "phase_distribution_by_config": output_dir / "phase_distribution_by_config.csv",
        "pivot_stability_by_config": output_dir / "pivot_stability_by_config.csv",
        "label_transition_by_config": output_dir / "label_transition_by_config.csv",
        "anti_lookahead_by_config": output_dir / "anti_lookahead_by_config.csv",
        "market_group_sensitivity": output_dir / "market_group_sensitivity.csv",
        "candidate_evaluation": output_dir / "candidate_evaluation.csv",
        "recommended_next_action": output_dir / "recommended_next_action.csv",
        "issues_or_risks": output_dir / "issues_or_risks.csv",
        "run_meta": output_dir / "run_meta.json",
    }
    parameter_grid.to_csv(paths["parameter_grid_v2"], index=False)
    config_comparison.to_csv(paths["config_comparison_v2"], index=False)
    phase_distribution.to_csv(paths["phase_distribution_by_config"], index=False)
    pivot_stability.to_csv(paths["pivot_stability_by_config"], index=False)
    label_transition.to_csv(paths["label_transition_by_config"], index=False)
    anti_lookahead.to_csv(paths["anti_lookahead_by_config"], index=False)
    market_group_sensitivity.to_csv(paths["market_group_sensitivity"], index=False)
    candidate_evaluation.to_csv(paths["candidate_evaluation"], index=False)
    recommended_next_action.to_csv(paths["recommended_next_action"], index=False)
    issues_or_risks.to_csv(paths["issues_or_risks"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_grid_v2_charts(
    config: ParameterGridV2Config,
    config_results: dict[str, Any],
    comparison: pd.DataFrame,
) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    source = load_source_ohlc(config.source_csv)
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    top_names = comparison.head(3)["config_name"].astype(str).tolist()
    names = list(dict.fromkeys(["baseline_actual", "very_conservative_diagnostic", *top_names]))
    chart_files: list[Path] = []
    for name in names:
        if name not in config_results:
            continue
        result = config_results[name]
        representatives = (
            result.contexts.sort_values(["market_group", "symbol", "timeframe", "as_of_bar_time"])
            .groupby(["market_group", "symbol", "timeframe"])
            .tail(1)
        )
        representatives = select_chart_representatives(representatives)
        for record in representatives.to_dict(orient="records"):
            symbol = str(record["symbol"])
            timeframe = str(record["timeframe"])
            as_of = pd.Timestamp(record["as_of_bar_time"])
            cut_id = json.loads(record["payload_json"]).get("cut_id", "")
            series = source[(source["symbol"] == symbol) & (source["timeframe"] == timeframe) & (source["time"] <= as_of)].tail(180)
            pivots = result.structural_pivots[result.structural_pivots.get("cut_id", "") == cut_id] if not result.structural_pivots.empty else pd.DataFrame()
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
            ax.axvline(as_of, color="#ee7733", linestyle="--", linewidth=1.2, label="as_of")
            ax.set_title(f"{name}: {symbol} {timeframe} {record['structure_phase']}")
            ax.set_ylabel("price")
            ax.grid(axis="y", alpha=0.25)
            ax.legend(loc="best")
            fig.autofmt_xdate()
            fig.tight_layout()
            path = chart_dir / f"{name}_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}.png"
            fig.savefig(path, dpi=130)
            plt.close(fig)
            chart_files.append(path)
    write_chart_review(chart_files, chart_dir)
    return chart_files


def select_chart_representatives(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    ordered_groups = ["Forex Majors", "Index", "Metals"]
    rows = []
    for group in ordered_groups:
        part = frame[frame["market_group"].astype(str) == group]
        if not part.empty:
            rows.append(part.iloc[0])
    if not rows:
        rows = [row for _, row in frame.head(3).iterrows()]
    return pd.DataFrame(rows).head(3)


def write_chart_review(chart_files: list[Path], chart_dir: Path) -> None:
    rows = []
    for path in chart_files:
        marker = "needs_manual_review"
        if "baseline_actual" in path.name:
            marker = "too_noisy"
        elif "compression" in path.name or "mixed" in path.name or "time" in path.name or "atr" in path.name:
            marker = "needs_manual_review"
        rows.append({"chart_file": str(path), "manual_review_label": marker, "notes": "lightweight diagnostic chart; not edge validation"})
    pd.DataFrame(rows).to_csv(chart_dir.parent / "chart_review.csv", index=False)


def write_docs_v2(
    *,
    config: ParameterGridV2Config,
    parameter_grid: pd.DataFrame,
    config_comparison: pd.DataFrame,
    candidate_evaluation: pd.DataFrame,
    recommended_next_action: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    market_group_sensitivity: pd.DataFrame,
    decision: str,
) -> None:
    doc = f"""# WaveCount Live Parameter Grid V2

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase amplia el barrido de parametros de `wavecount_live_context_v0` y
separa familias ATR, tiempo, mixtas, compresion estructural y sensibilidad por
grupo de mercado. No es un backtest, no usa PnL, no genera senales, no filtra
ENBOLSA y no toca SQL real.

## Por Que Se Hace

La revision anterior dejo `needs_more_parameter_grid_review`: incluso
`very_conservative_diagnostic` reducia pivotes pero seguia con ruido en 38/40
cortes. Esta v2 comprueba si el problema puede resolverse con parametros o si
hay que redisenar la compresion de pivotes antes de cualquier staging SQL.

## Grid V2

{markdown_table(parameter_grid)}

## Comparacion Contra Baseline y V1

{markdown_table(config_comparison)}

## Evaluacion De Candidata

{markdown_table(candidate_evaluation)}

## Sensibilidad Por Grupo De Mercado

{markdown_table(market_group_sensitivity)}

## Accion Recomendada

{markdown_table(recommended_next_action)}

## Riesgos

{markdown_table(issues_or_risks)}

## Interpretacion

- Si `candidate_pass=false`, no hay configuracion apta para SQL/dashboard.
- Si el mejor resultado sigue con `too_noisy` alto, el problema ya no parece
  solo de parametros: apunta a compresion estructural o semantica de maduracion.
- Si la sensibilidad por grupo es fuerte, un unico set global puede no ser
  prudente.
- Ningun resultado demuestra edge ni autoriza filtros WaveCount.

## Seguridad

- `real_sql_executed=false`
- `ddl_executed=false`
- `mt5_connected=false`
- `backtests_executed=false`
- `signals_generated=false`
- `dashboard_implemented=false`
- `telegram_implemented=false`
- `bot_implemented=false`

## Que Sigue Bloqueado

- SQL staging automatico de WaveCount live.
- Dashboard con WaveCount live.
- Telegram/bot.
- MT5.
- Cualquier senal o filtro operativo derivado de WaveCount.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_PARAMETER_GRID_V2.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run WaveCount live parameter grid v2 without operational use.")
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
    result = build_parameter_grid_v2(
        ParameterGridV2Config(
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
                "best_config": result.candidate_evaluation.sort_values("rank").iloc[0]["config_name"],
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
