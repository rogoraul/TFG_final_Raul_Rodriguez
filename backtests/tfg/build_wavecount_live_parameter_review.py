from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

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


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_parameter_review_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_PARAMETER_REVIEW.md")


@dataclass(frozen=True)
class ParameterCandidate:
    config_name: str
    description: str
    pivot_config: PivotConfig
    structural_config: StructuralPivotConfig


@dataclass(frozen=True)
class ParameterReviewConfig:
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
class ParameterReviewResult:
    parameter_grid: pd.DataFrame
    parameter_summary: pd.DataFrame
    config_comparison: pd.DataFrame
    phase_distribution: pd.DataFrame
    pivot_stability: pd.DataFrame
    label_transition: pd.DataFrame
    anti_lookahead: pd.DataFrame
    recommended_config: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_parameter_review(config: ParameterReviewConfig | None = None) -> ParameterReviewResult:
    config = config or ParameterReviewConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    candidates = filter_candidates(default_parameter_candidates(), config.config_names)
    if not candidates:
        raise ValueError("no parameter candidates selected")

    parameter_grid = parameter_grid_frame(candidates)
    summary_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    pivot_frames: list[pd.DataFrame] = []
    transition_frames: list[pd.DataFrame] = []
    anti_rows: list[dict[str, Any]] = []
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

    parameter_summary = pd.DataFrame(summary_rows)
    config_comparison = build_config_comparison(parameter_summary)
    phase_distribution = pd.DataFrame(phase_rows)
    pivot_stability_all = concat_or_empty(pivot_frames)
    label_transition_all = concat_or_empty(transition_frames)
    anti_lookahead = pd.DataFrame(anti_rows)
    recommended = recommended_config_frame(candidates, config_comparison)
    issues = build_issues_or_risks(config_comparison, recommended)
    decision = decide_final(issues, recommended)
    run_meta = run_meta_dict(
        generated_at=generated_at,
        config=config,
        candidates=candidates,
        config_comparison=config_comparison,
        recommended=recommended,
        decision=decision,
    )
    written = write_outputs(
        config=config,
        parameter_grid=parameter_grid,
        parameter_summary=parameter_summary,
        config_comparison=config_comparison,
        phase_distribution=phase_distribution,
        pivot_stability=pivot_stability_all,
        label_transition=label_transition_all,
        anti_lookahead=anti_lookahead,
        recommended_config=recommended,
        issues_or_risks=issues,
        run_meta=run_meta,
    )
    if config.generate_charts:
        chart_files = write_parameter_charts(config, config_results, recommended)
        if chart_files:
            run_meta["chart_files"] = [str(path) for path in chart_files]
            (config.output_dir / "run_meta.json").write_text(
                json.dumps(run_meta, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            written["charts"] = config.output_dir / "charts"
    write_docs(
        config=config,
        parameter_grid=parameter_grid,
        config_comparison=config_comparison,
        recommended_config=recommended,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_PARAMETER_REVIEW.md"
    return ParameterReviewResult(
        parameter_grid=parameter_grid,
        parameter_summary=parameter_summary,
        config_comparison=config_comparison,
        phase_distribution=phase_distribution,
        pivot_stability=pivot_stability_all,
        label_transition=label_transition_all,
        anti_lookahead=anti_lookahead,
        recommended_config=recommended,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def default_parameter_candidates() -> list[ParameterCandidate]:
    return [
        ParameterCandidate(
            config_name="baseline_actual",
            description="Current real-OHLC cut review settings.",
            pivot_config=PivotConfig(),
            structural_config=StructuralPivotConfig(),
        ),
        ParameterCandidate(
            config_name="conservative_a",
            description="Higher ATR/relative filters and larger structural legs.",
            pivot_config=PivotConfig(
                left_bars=3,
                confirmation_bars=3,
                atr_period=14,
                min_atr_multiplier=1.25,
                min_relative_move_pct=0.002,
                min_bars_between_pivots=3,
                candidate_lookback_bars=4,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=5.0,
                min_leg_relative_move_pct=0.006,
                min_leg_bars=10,
            ),
        ),
        ParameterCandidate(
            config_name="conservative_b",
            description="Wider causal pivot window and longer confirmation latency.",
            pivot_config=PivotConfig(
                left_bars=5,
                confirmation_bars=5,
                atr_period=14,
                min_atr_multiplier=1.0,
                min_relative_move_pct=0.0015,
                min_bars_between_pivots=5,
                candidate_lookback_bars=6,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=4.5,
                min_leg_relative_move_pct=0.005,
                min_leg_bars=12,
            ),
        ),
        ParameterCandidate(
            config_name="conservative_c",
            description="Combined ATR, relative move and minimum-bars filters.",
            pivot_config=PivotConfig(
                left_bars=4,
                confirmation_bars=4,
                atr_period=18,
                min_atr_multiplier=1.5,
                min_relative_move_pct=0.0025,
                min_bars_between_pivots=4,
                candidate_lookback_bars=6,
            ),
            structural_config=StructuralPivotConfig(
                min_leg_atr_multiplier=6.0,
                min_leg_relative_move_pct=0.008,
                min_leg_bars=14,
            ),
        ),
        ParameterCandidate(
            config_name="very_conservative_diagnostic",
            description="Hard diagnostic setting to test whether context collapses.",
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
    ]


def filter_candidates(candidates: list[ParameterCandidate], names: tuple[str, ...] | None) -> list[ParameterCandidate]:
    if not names:
        return candidates
    wanted = set(names)
    selected = [candidate for candidate in candidates if candidate.config_name in wanted]
    missing = wanted - {candidate.config_name for candidate in selected}
    if missing:
        raise ValueError(f"unknown parameter config names: {sorted(missing)}")
    return selected


def parameter_grid_frame(candidates: list[ParameterCandidate]) -> pd.DataFrame:
    rows = []
    for candidate in candidates:
        rows.append(
            {
                "config_name": candidate.config_name,
                "description": candidate.description,
                **{f"pivot_{key}": value for key, value in candidate.pivot_config.__dict__.items()},
                **{f"structural_{key}": value for key, value in candidate.structural_config.__dict__.items()},
            }
        )
    return pd.DataFrame(rows)


def summary_row(candidate: ParameterCandidate, result: Any) -> dict[str, Any]:
    contexts = result.contexts
    pivot_stability = result.pivot_stability_audit
    transitions = result.label_transition_audit
    anti = result.anti_lookahead_audit
    bars_used = int(pivot_stability["bars_used"].astype(int).sum()) if not pivot_stability.empty else 0
    detected_total = int(pivot_stability["detected_pivots"].astype(int).sum()) if not pivot_stability.empty else 0
    structural_total = int(pivot_stability["structural_pivots"].astype(int).sum()) if not pivot_stability.empty else 0
    cuts = int(len(pivot_stability))
    non_initial = transitions[transitions["transition_type"] != "initial_cut"] if not transitions.empty else transitions
    phase_counts = contexts["structure_phase"].value_counts().to_dict() if not contexts.empty else {}
    lag_median_values = pd.to_numeric(pivot_stability.get("median_confirmation_lag_bars", pd.Series(dtype=float)), errors="coerce")
    lag_max_values = pd.to_numeric(pivot_stability.get("max_confirmation_lag_bars", pd.Series(dtype=float)), errors="coerce")
    return {
        "config_name": candidate.config_name,
        "cuts": cuts,
        "bars_used_total": bars_used,
        "detected_pivots_total": detected_total,
        "structural_pivots_total": structural_total,
        "detected_pivots_per_100_bars": round(detected_total / bars_used * 100, 4) if bars_used else 0.0,
        "structural_pivots_per_100_bars": round(structural_total / bars_used * 100, 4) if bars_used else 0.0,
        "too_noisy_cuts": int(pivot_stability["too_noisy"].astype(bool).sum()) if not pivot_stability.empty else 0,
        "too_sparse_cuts": int(pivot_stability["too_sparse"].astype(bool).sum()) if not pivot_stability.empty else 0,
        "unstable_pivot_cuts": int(pivot_stability["unstable_pivots"].astype(bool).sum()) if not pivot_stability.empty else 0,
        "late_confirmation_cuts": int(pivot_stability["late_confirmation"].astype(bool).sum()) if not pivot_stability.empty else 0,
        "phase_change_count": int(non_initial["phase_changed"].astype(bool).sum()) if not non_initial.empty else 0,
        "phase_change_pct_non_initial": round(float(non_initial["phase_changed"].astype(bool).mean()), 4) if not non_initial.empty else 0.0,
        "abrupt_transition_count": int((transitions["transition_type"] == "abrupt_reclassification").sum()) if not transitions.empty else 0,
        "completed_impulse_count": int(phase_counts.get("completed_impulse_candidate", 0)),
        "completed_impulse_pct": round(float((contexts["structure_phase"] == "completed_impulse_candidate").mean()), 4) if not contexts.empty else 0.0,
        "unknown_pct": round(float((contexts["structure_phase"] == "unknown").mean()), 4) if not contexts.empty else 0.0,
        "ambiguous_pct": round(float((contexts["structure_phase"] == "ambiguous").mean()), 4) if not contexts.empty else 0.0,
        "invalidated_pct": round(float((contexts["structure_phase"] == "invalidated").mean()), 4) if not contexts.empty else 0.0,
        "median_confirmation_lag_bars": "" if lag_median_values.dropna().empty else round(float(lag_median_values.dropna().median()), 3),
        "max_confirmation_lag_bars": "" if lag_max_values.dropna().empty else round(float(lag_max_values.dropna().max()), 3),
        "anti_lookahead_passed": bool(anti["lookahead_safe"].all()) if not anti.empty else False,
        "hard_flags_fail_closed": bool(
            contexts["is_read_only"].all()
            and not contexts["can_generate_signal"].any()
            and not contexts["can_filter_trade"].any()
            and not contexts["can_execute_order"].any()
        ),
    }


def phase_distribution_rows(config_name: str, contexts: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for phase, count in contexts["structure_phase"].value_counts().sort_index().items():
        rows.append({"config_name": config_name, "metric": "structure_phase", "value": phase, "count": int(count)})
    for status, count in contexts["hypothesis_status"].value_counts().sort_index().items():
        rows.append({"config_name": config_name, "metric": "hypothesis_status", "value": status, "count": int(count)})
    return rows


def anti_lookahead_row(config_name: str, result: Any) -> dict[str, Any]:
    anti = result.anti_lookahead_audit
    return {
        "config_name": config_name,
        "rows": int(len(anti)),
        "lookahead_safe_all": bool(anti["lookahead_safe"].all()) if not anti.empty else False,
        "detected_at_lte_as_of_all": bool(anti["detected_at_lte_as_of"].all()) if not anti.empty else False,
        "evidence_window_end_lte_as_of_all": bool(anti["evidence_window_end_lte_as_of"].all()) if not anti.empty else False,
        "pivot_detected_at_lte_as_of_all": bool(anti["pivot_detected_at_lte_as_of"].all()) if "pivot_detected_at_lte_as_of" in anti.columns and not anti.empty else False,
        "future_pivots_used_total": int(anti.get("future_pivots_used", pd.Series(dtype=int)).astype(int).sum()) if not anti.empty else 0,
        "bars_after_as_of_ignored": int(anti.get("bars_after_as_of_ignored", pd.Series(dtype=int)).astype(int).sum()) if not anti.empty else 0,
    }


def build_config_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    if frame.empty:
        return frame
    baseline = frame[frame["config_name"] == "baseline_actual"].iloc[0] if "baseline_actual" in set(frame["config_name"]) else frame.iloc[0]
    frame["detected_reduction_vs_baseline_pct"] = frame["detected_pivots_total"].map(
        lambda value: round(1.0 - float(value) / max(float(baseline["detected_pivots_total"]), 1.0), 4)
    )
    frame["structural_reduction_vs_baseline_pct"] = frame["structural_pivots_total"].map(
        lambda value: round(1.0 - float(value) / max(float(baseline["structural_pivots_total"]), 1.0), 4)
    )
    frame["noise_cut_pct"] = frame["too_noisy_cuts"] / frame["cuts"].clip(lower=1)
    frame["sparse_cut_pct"] = frame["too_sparse_cuts"] / frame["cuts"].clip(lower=1)
    frame["unstable_cut_pct"] = frame["unstable_pivot_cuts"] / frame["cuts"].clip(lower=1)
    frame["score"] = frame.apply(readability_score, axis=1)
    frame["rank"] = frame["score"].rank(method="first", ascending=False).astype(int)
    frame["candidate_pass"] = frame.apply(candidate_pass, axis=1)
    return frame.sort_values(["rank", "config_name"]).reset_index(drop=True)


def readability_score(row: pd.Series) -> float:
    score = 100.0
    score -= float(row["noise_cut_pct"]) * 35.0
    score -= float(row["sparse_cut_pct"]) * 25.0
    score -= float(row["unstable_cut_pct"]) * 20.0
    score -= float(row["phase_change_pct_non_initial"]) * 10.0
    score -= min(float(row["abrupt_transition_count"]) * 2.0, 12.0)
    score -= abs(float(row["completed_impulse_pct"]) - 0.45) * 18.0
    score -= max(0.0, float(row["unknown_pct"]) - 0.35) * 20.0
    structural_per_100 = float(row["structural_pivots_per_100_bars"])
    if structural_per_100 > 4.5:
        score -= (structural_per_100 - 4.5) * 10.0
    if structural_per_100 < 0.6:
        score -= (0.6 - structural_per_100) * 20.0
    if not bool(row["anti_lookahead_passed"]):
        score -= 100.0
    if not bool(row["hard_flags_fail_closed"]):
        score -= 100.0
    return round(score, 4)


def candidate_pass(row: pd.Series) -> bool:
    return bool(
        row["anti_lookahead_passed"]
        and row["hard_flags_fail_closed"]
        and float(row["noise_cut_pct"]) <= 0.5
        and float(row["sparse_cut_pct"]) <= 0.5
        and float(row["completed_impulse_pct"]) <= 0.8
        and float(row["structural_pivots_per_100_bars"]) <= 5.0
        and float(row["structural_pivots_per_100_bars"]) >= 0.6
    )


def recommended_config_frame(candidates: list[ParameterCandidate], comparison: pd.DataFrame) -> pd.DataFrame:
    candidate_lookup = {candidate.config_name: candidate for candidate in candidates}
    passing = comparison[comparison["candidate_pass"].astype(bool)].copy()
    selected = passing.iloc[0] if not passing.empty else comparison.iloc[0]
    candidate = candidate_lookup[str(selected["config_name"])]
    return pd.DataFrame(
        [
            {
                "config_name": candidate.config_name,
                "recommendation_type": "candidate_live_readability_config_v0" if bool(selected["candidate_pass"]) else "diagnostic_best_available_not_candidate",
                "score": selected["score"],
                "candidate_pass": bool(selected["candidate_pass"]),
                "rationale": recommendation_rationale(selected),
                **{f"pivot_{key}": value for key, value in candidate.pivot_config.__dict__.items()},
                **{f"structural_{key}": value for key, value in candidate.structural_config.__dict__.items()},
            }
        ]
    )


def recommendation_rationale(row: pd.Series) -> str:
    if bool(row["candidate_pass"]):
        return (
            "Best readability score among passing configurations; reduces pivot density without collapsing context, "
            "keeps anti-lookahead and hard safety flags."
        )
    return (
        "Best diagnostic score, but it does not meet candidate thresholds; more review or pivot logic redesign may be needed."
    )


def build_issues_or_risks(comparison: pd.DataFrame, recommended: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    best = comparison.iloc[0]
    baseline = comparison[comparison["config_name"] == "baseline_actual"].iloc[0] if "baseline_actual" in set(comparison["config_name"]) else comparison.iloc[-1]
    rows.append(
        {
            "severity": "info",
            "risk": "root_cause",
            "description": (
                "The excess comes from raw causal pivot density and remains visible after structural compression; "
                f"baseline detected {int(baseline['detected_pivots_total'])} pivots and {int(baseline['structural_pivots_total'])} structural pivots."
            ),
            "recommendation": "Treat completed impulse labels as over-mature when pivot density is high.",
        }
    )
    rows.append(
        {
            "severity": "info" if bool(best["candidate_pass"]) else "medium",
            "risk": "candidate_quality",
            "description": (
                f"Best config `{best['config_name']}` score={best['score']}, "
                f"candidate_pass={bool(best['candidate_pass'])}."
            ),
            "recommendation": "Do not use for SQL/dashboard unless candidate_pass=true and visual review is acceptable.",
        }
    )
    if float(best["noise_cut_pct"]) > 0.5:
        rows.append(
            {
                "severity": "medium",
                "risk": "remaining_noise",
                "description": f"Best config still has too_noisy in {best['noise_cut_pct']:.1%} of cuts.",
                "recommendation": "Open a wider grid or redesign pivot compression before SQL staging.",
            }
        )
    if float(best["completed_impulse_pct"]) > 0.8:
        rows.append(
            {
                "severity": "medium",
                "risk": "over_mature_labels",
                "description": f"Best config still has completed_impulse_candidate in {best['completed_impulse_pct']:.1%} of rows.",
                "recommendation": "Avoid claiming live phase resolution until label maturation is constrained.",
            }
        )
    if float(best["sparse_cut_pct"]) > 0.5:
        rows.append(
            {
                "severity": "medium",
                "risk": "over_filtering",
                "description": f"Best config is too sparse in {best['sparse_cut_pct']:.1%} of cuts.",
                "recommendation": "Reduce structural thresholds or add more intermediate configurations.",
            }
        )
    rows.append(
        {
            "severity": "medium",
            "risk": "visual_review_required",
            "description": "Charts are generated for selected configurations, but this is not a full visual audit.",
            "recommendation": "Inspect representative Forex/Index/Metals charts before promoting any config.",
        }
    )
    return pd.DataFrame(rows)


def decide_final(issues: pd.DataFrame, recommended: pd.DataFrame) -> str:
    if (issues["severity"] == "blocking").any():
        return "blocked_for_sql_staging"
    if bool(recommended.iloc[0]["candidate_pass"]):
        return "candidate_live_readability_config_v0"
    remaining = set(issues.loc[issues["severity"] == "medium", "risk"])
    if {"remaining_noise", "over_mature_labels", "over_filtering"} & remaining:
        return "needs_more_parameter_grid_review"
    return "needs_pivot_logic_redesign"


def run_meta_dict(
    *,
    generated_at: str,
    config: ParameterReviewConfig,
    candidates: list[ParameterCandidate],
    config_comparison: pd.DataFrame,
    recommended: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_parameter_review",
        "source_csv": str(config.source_csv),
        "symbols": list(config.symbols),
        "timeframes": [config.timeframe],
        "config_count": len(candidates),
        "cut_count_per_config": config.cut_count * min(config.max_symbols, len(config.symbols)),
        "decision": decision,
        "recommended_config": recommended.iloc[0].to_dict() if not recommended.empty else {},
        "comparison": config_comparison[["config_name", "score", "rank", "candidate_pass"]].to_dict(orient="records"),
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
            "Parameter review only; no PnL, no backtest and no signal generation.",
            "Candidate config, if any, is technical and not WaveCount 2.5.6 policy.",
            "Visual charts are lightweight diagnostics, not manual validation closure.",
        ],
    }


def write_outputs(
    *,
    config: ParameterReviewConfig,
    parameter_grid: pd.DataFrame,
    parameter_summary: pd.DataFrame,
    config_comparison: pd.DataFrame,
    phase_distribution: pd.DataFrame,
    pivot_stability: pd.DataFrame,
    label_transition: pd.DataFrame,
    anti_lookahead: pd.DataFrame,
    recommended_config: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "parameter_grid": output_dir / "parameter_grid.csv",
        "parameter_summary": output_dir / "parameter_summary.csv",
        "config_comparison": output_dir / "config_comparison.csv",
        "phase_distribution_by_config": output_dir / "phase_distribution_by_config.csv",
        "pivot_stability_by_config": output_dir / "pivot_stability_by_config.csv",
        "label_transition_by_config": output_dir / "label_transition_by_config.csv",
        "anti_lookahead_by_config": output_dir / "anti_lookahead_by_config.csv",
        "recommended_config": output_dir / "recommended_config.csv",
        "issues_or_risks": output_dir / "issues_or_risks.csv",
        "run_meta": output_dir / "run_meta.json",
    }
    parameter_grid.to_csv(paths["parameter_grid"], index=False)
    parameter_summary.to_csv(paths["parameter_summary"], index=False)
    config_comparison.to_csv(paths["config_comparison"], index=False)
    phase_distribution.to_csv(paths["phase_distribution_by_config"], index=False)
    pivot_stability.to_csv(paths["pivot_stability_by_config"], index=False)
    label_transition.to_csv(paths["label_transition_by_config"], index=False)
    anti_lookahead.to_csv(paths["anti_lookahead_by_config"], index=False)
    recommended_config.to_csv(paths["recommended_config"], index=False)
    issues_or_risks.to_csv(paths["issues_or_risks"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_parameter_charts(config: ParameterReviewConfig, config_results: dict[str, Any], recommended: pd.DataFrame) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    source = load_source_ohlc(config.source_csv)
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    names = ["baseline_actual", str(recommended.iloc[0]["config_name"])]
    names = list(dict.fromkeys(name for name in names if name in config_results))
    chart_files: list[Path] = []
    for name in names:
        result = config_results[name]
        representatives = (
            result.contexts.sort_values(["symbol", "timeframe", "as_of_bar_time"])
            .groupby(["symbol", "timeframe"])
            .tail(1)
            .head(3)
        )
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
    return chart_files


def write_docs(
    *,
    config: ParameterReviewConfig,
    parameter_grid: pd.DataFrame,
    config_comparison: pd.DataFrame,
    recommended_config: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    run_meta: dict[str, Any],
    decision: str,
) -> None:
    title = "WaveCount Live Parameter Review"
    output_dir = config.output_dir
    best = recommended_config.iloc[0]
    doc = f"""# {title}

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase revisa parametros de pivotes sobre OHLC local ya artifactado. No es
un backtest, no usa PnL, no genera senales, no filtra ENBOLSA y no toca SQL.

## Motivo

La revision real OHLC anterior dejo `needs_parameter_review_before_sql`: el
pipeline era causal, pero detectaba demasiados pivotes y maduraba casi todo a
`completed_impulse_candidate`. Esta revision prueba configuraciones discretas
para mejorar legibilidad estructural sin reabrir WaveCount 2.5.x.

## Configuraciones Probadas

{markdown_table(parameter_grid)}

## Comparacion

{markdown_table(config_comparison)}

## Recomendacion

{markdown_table(recommended_config)}

En esta ejecucion no queda aprobada una candidata tecnica. La mejor
configuracion es diagnostica y sirve para orientar el siguiente barrido, no para
pasar a SQL/dashboard. Si una ejecucion futura declara
`candidate_live_readability_config_v0`, seguira sin sustituir la politica
oficial 2.5.6, sin demostrar edge y sin permitir uso operativo.

## Riesgos

{markdown_table(issues_or_risks)}

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

## Siguiente Paso

Usar la decision `{decision}` como frontera. Si hay candidata, revisarla con
graficos/casos adicionales antes de cualquier staging SQL. Si no hay candidata,
ampliar grid o redisenar la logica de pivotes.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (output_dir / "WAVECOUNT_LIVE_PARAMETER_REVIEW.md").write_text(doc, encoding="utf-8")


def markdown_table(frame: pd.DataFrame, max_rows: int = 80) -> str:
    if frame.empty:
        return "| empty |\n| --- |"
    view = frame.head(max_rows).copy()
    columns = [str(column) for column in view.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for record in view.to_dict(orient="records"):
        lines.append("| " + " | ".join(markdown_cell(record.get(column, "")) for column in view.columns) + " |")
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


def safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in str(value)).strip("_")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review WaveCount live pivot parameters without operational use.")
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
    result = build_parameter_review(
        ParameterReviewConfig(
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
                "recommended_config": result.recommended_config.iloc[0]["config_name"],
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
