from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .wavecount_config import PivotConfig
from .wavecount_counts_gallery import _plot_candles, _plot_structural_chain
from .wavecount_degrees import DEFAULT_SWING_DEGREES
from .wavecount_gallery import fetch_recent_ohlc
from .wavecount_h4_d1_gallery import H4_D1_VISUAL_REVIEW_SPECS
from .wavecount_visual_review_gallery import DEFAULT_VISUAL_REVIEW_SPECS, VisualReviewSpec, _build_source_tables


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE23_H1_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"
DEFAULT_PHASE23_H4_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
DEFAULT_MANUAL_FEEDBACK_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_manual_feedback_h1_m30_2026-05-21"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_3_degree_calibration_2026-05-23"


DEGREE_ORDER = ("minor", "intermediate", "major")
DEGREE_COLORS = {
    "minor": "#0077BB",
    "intermediate": "#EE7733",
    "major": "#111827",
}


SELECTED_CHART_EXAMPLES = (
    "index_aus200_h1",
    "forex_audjpy_h1",
    "metals_xagusd_h1",
    "forex_eurjpy_m30",
    "forex_audjpy_h4",
    "index_aus200_h4",
    "metals_xagusd_h4",
    "index_hk50_h4",
)


def _as_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _scenario_specs(source_windows: pd.DataFrame, fallback: tuple[VisualReviewSpec, ...]) -> tuple[VisualReviewSpec, ...]:
    rows: list[VisualReviewSpec] = []
    for _, row in source_windows.iterrows():
        if str(row.get("status", "")) != "ok":
            continue
        rows.append(
            VisualReviewSpec(
                example_id=str(row["example_id"]),
                group=str(row["group"]),
                symbol=str(row["symbol"]),
                timeframe=str(row["timeframe"]),
                rows=int(row["rows"]),
            )
        )
    return tuple(rows) or fallback


def _load_scenario(scenario: str, phase_dir: Path, fallback_specs: tuple[VisualReviewSpec, ...]) -> dict[str, pd.DataFrame]:
    windows = pd.read_csv(phase_dir / "tables" / "source_windows.csv")
    specs = _scenario_specs(windows, fallback_specs)
    source = _build_source_tables(specs, PivotConfig())
    degree_pivots = source["degree_pivots"].copy()
    source_windows = source["source_windows"].copy()
    degree_pivots["scenario"] = scenario
    source_windows["scenario"] = scenario
    spec_rows = pd.DataFrame([spec.__dict__ for spec in specs])
    spec_rows["scenario"] = scenario
    return {
        "degree_pivots": degree_pivots,
        "source_windows": source_windows,
        "specs": spec_rows,
    }


def _build_degree_metrics(degree_pivots: pd.DataFrame, source_windows: pd.DataFrame) -> pd.DataFrame:
    if degree_pivots.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    window_lookup = source_windows.set_index(["scenario", "example_id"]).to_dict("index")
    for (scenario, example_id, degree), group in degree_pivots.groupby(["scenario", "example_id", "swing_degree"], dropna=False):
        group = group.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"])
        first = group.iloc[0]
        window = window_lookup.get((scenario, example_id), {})
        rows_count = int(window.get("rows", 0) or 0)
        pivots = len(group)
        density = (pivots / rows_count * 100.0) if rows_count else 0.0
        leg_abs = pd.to_numeric(group.get("leg_move_abs", pd.Series(dtype=float)), errors="coerce").dropna()
        leg_atr = pd.to_numeric(group.get("leg_move_atr", pd.Series(dtype=float)), errors="coerce").dropna()
        bars = pd.to_numeric(group.get("bars_from_previous", pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                "scenario": scenario,
                "example_id": example_id,
                "group": first.get("group", ""),
                "symbol": first.get("symbol", ""),
                "timeframe": first.get("timeframe", ""),
                "swing_degree": degree,
                "source_rows": rows_count,
                "pivot_count": pivots,
                "pivot_density_per_100_bars": density,
                "median_leg_abs": float(leg_abs.median()) if not leg_abs.empty else 0.0,
                "mean_leg_abs": float(leg_abs.mean()) if not leg_abs.empty else 0.0,
                "median_leg_atr": float(leg_atr.median()) if not leg_atr.empty else 0.0,
                "mean_leg_atr": float(leg_atr.mean()) if not leg_atr.empty else 0.0,
                "median_bars_from_previous": float(bars.median()) if not bars.empty else 0.0,
                "mean_bars_from_previous": float(bars.mean()) if not bars.empty else 0.0,
                "degree_min_leg_atr_multiplier": float(first.get("degree_min_leg_atr_multiplier", 0.0)),
                "degree_min_leg_relative_move_pct": float(first.get("degree_min_leg_relative_move_pct", 0.0)),
                "degree_min_leg_bars": float(first.get("degree_min_leg_bars", 0.0)),
            }
        )
    return pd.DataFrame(rows).sort_values(["scenario", "example_id", "swing_degree"]).reset_index(drop=True)


def _issue_label(row: pd.Series) -> str:
    if not bool(row["monotonic_ok"]):
        return "degree_count_monotonic_violation"
    issues = []
    if float(row["minor_density"]) >= 10.0:
        issues.append("degree_too_micro")
    if float(row["intermediate_vs_minor_ratio"]) >= 0.75:
        issues.append("degree_not_discriminative_intermediate_vs_minor")
    if float(row["major_vs_intermediate_ratio"]) >= 0.75:
        issues.append("degree_not_discriminative_major_vs_intermediate")
    if float(row["major_pivots"]) < 6:
        issues.append("degree_too_coarse_major")
    return "|".join(issues) if issues else "degree_reasonable"


def _build_discrimination_issues(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if metrics.empty:
        return pd.DataFrame()
    for (scenario, example_id), group in metrics.groupby(["scenario", "example_id"], dropna=False):
        counts = {degree: 0 for degree in DEGREE_ORDER}
        densities = {degree: 0.0 for degree in DEGREE_ORDER}
        meta = group.iloc[0]
        for _, row in group.iterrows():
            degree = str(row["swing_degree"])
            counts[degree] = int(row["pivot_count"])
            densities[degree] = float(row["pivot_density_per_100_bars"])
        minor = counts["minor"]
        intermediate = counts["intermediate"]
        major = counts["major"]
        row = {
            "scenario": scenario,
            "example_id": example_id,
            "group": meta.get("group", ""),
            "symbol": meta.get("symbol", ""),
            "timeframe": meta.get("timeframe", ""),
            "minor_pivots": minor,
            "intermediate_pivots": intermediate,
            "major_pivots": major,
            "minor_density": densities["minor"],
            "intermediate_density": densities["intermediate"],
            "major_density": densities["major"],
            "intermediate_vs_minor_ratio": (intermediate / minor) if minor else 0.0,
            "major_vs_intermediate_ratio": (major / intermediate) if intermediate else 0.0,
            "major_vs_minor_ratio": (major / minor) if minor else 0.0,
            "monotonic_ok": bool(major <= intermediate <= minor),
        }
        row["degree_issue"] = _issue_label(pd.Series(row))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["scenario", "degree_issue", "example_id"]).reset_index(drop=True)


def _manual_degree_evidence(manual_feedback_dir: Path) -> pd.DataFrame:
    evidence_rows: list[dict[str, Any]] = []
    degree_path = manual_feedback_dir / "tables" / "degree_calibration_issues.csv"
    if degree_path.exists():
        degree = pd.read_csv(degree_path)
        for _, row in degree.iterrows():
            evidence_rows.append(
                {
                    "source": "manual_feedback_degree_issues",
                    "candidate_id": row.get("candidate_id", ""),
                    "scenario": "h1_m30",
                    "symbol": row.get("symbol", ""),
                    "timeframe": row.get("timeframe", ""),
                    "swing_degree": row.get("swing_degree", ""),
                    "manual_label": row.get("issue_type", ""),
                    "manual_note": row.get("user_observation", ""),
                    "methodological_implication": row.get("rule_implication", ""),
                    "chart_path_absolute": row.get("chart_path_absolute", ""),
                }
            )
    partial_path = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_partial123_2026-05-21" / "tables" / "partial123_latest_manual_update_2026-05-22.csv"
    if partial_path.exists():
        partials = pd.read_csv(partial_path)
        for _, row in partials.iterrows():
            evidence_rows.append(
                {
                    "source": "manual_partial123_update",
                    "candidate_id": row.get("candidate_id", ""),
                    "scenario": "h1_m30",
                    "symbol": row.get("symbol", ""),
                    "timeframe": row.get("timeframe", ""),
                    "swing_degree": row.get("swing_degree", ""),
                    "manual_label": row.get("manual_visual_label", ""),
                    "manual_note": row.get("latest_user_interpretation", ""),
                    "methodological_implication": row.get("methodological_note", ""),
                    "chart_path_absolute": row.get("chart_path_absolute", ""),
                }
            )
    wave5_path = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_1_wave5_endpoint_2026-05-21" / "tables" / "wave5_manual_interpretation_update.csv"
    if wave5_path.exists():
        wave5 = pd.read_csv(wave5_path)
        for _, row in wave5.iterrows():
            if str(row.get("higher_degree_substructure_possible", "")).lower() != "true":
                continue
            evidence_rows.append(
                {
                    "source": "manual_wave5_interpretation",
                    "candidate_id": row.get("candidate_id", ""),
                    "scenario": "h1_m30",
                    "symbol": row.get("symbol", ""),
                    "timeframe": row.get("timeframe", ""),
                    "swing_degree": row.get("swing_degree", ""),
                    "manual_label": row.get("final_methodological_label", ""),
                    "manual_note": row.get("latest_user_interpretation", ""),
                    "methodological_implication": "Local count may be valid as higher-degree substructure.",
                    "chart_path_absolute": row.get("chart_path_absolute", ""),
                }
            )
    return pd.DataFrame(evidence_rows)


def _recommended_degree_policy(metrics: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "scope": "H1/M30",
            "primary_degree_recommendation": "intermediate_auxiliary",
            "context_degree": "major",
            "minor_use": "internal_detail_only",
            "status": "not_primary_for_phase_2_5",
            "reason": "manual review found too-micro/lateral counts and degree overlap in H1/M30; useful as case bank, not main Elliott base",
            "apply_threshold_change_now": False,
        },
        {
            "scope": "H4/D1",
            "primary_degree_recommendation": "intermediate",
            "context_degree": "major",
            "minor_use": "substructure_detail",
            "status": "preferred_phase_2_5_base",
            "reason": "larger timeframe gives broader swings; still needs visual review but is more aligned with Elliott structural reading",
            "apply_threshold_change_now": False,
        },
        {
            "scope": "global_thresholds",
            "primary_degree_recommendation": "keep_current_for_now",
            "context_degree": "major",
            "minor_use": "internal_detail_only",
            "status": "needs_experimental_recalibration_phase_if_changed",
            "reason": "thresholds are global and changing them would require regenerating Phase 1.6 and downstream galleries; audit should not mutate canonical artifacts",
            "apply_threshold_change_now": False,
        },
    ]
    return pd.DataFrame(rows)


def _phase25_readiness(metrics: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    h1 = issues[issues["scenario"] == "h1_m30"]
    h4 = issues[issues["scenario"] == "h4_d1"]
    return pd.DataFrame(
        [
            {
                "scenario": "h1_m30",
                "readiness": "auxiliary_only",
                "recommended_primary_degree": "intermediate_auxiliary",
                "use_in_phase_2_5": "case_bank_and_substructure_checks",
                "main_risk": "degree overlap, microstructure, lateral/corrective ranges",
                "issue_count": int((h1["degree_issue"] != "degree_reasonable").sum()) if not h1.empty else 0,
            },
            {
                "scenario": "h4_d1",
                "readiness": "preferred_base_with_manual_review",
                "recommended_primary_degree": "intermediate",
                "use_in_phase_2_5": "primary visual basis for guided search prototype",
                "main_risk": "major can still be context-only; intermediate must remain provisional",
                "issue_count": int((h4["degree_issue"] != "degree_reasonable").sum()) if not h4.empty else 0,
            },
        ]
    )


def _plot_degree_comparison(frame: pd.DataFrame, pivots: pd.DataFrame, spec: VisualReviewSpec, scenario: str, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=False)
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(axes[0], frame)
    example_pivots = pivots[pivots["example_id"] == spec.example_id].copy()
    for degree in DEGREE_ORDER:
        _plot_structural_chain(axes[0], frame, example_pivots, degree, DEGREE_COLORS[degree], f"{degree} swings", time_axis)
    axes[0].set_title(f"{spec.example_id} | {spec.symbol} {spec.timeframe} | {scenario} degree overlay", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("Price")
    axes[0].grid(axis="y", alpha=0.22)
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        unique = {}
        for handle, label in zip(handles, labels):
            unique.setdefault(label, handle)
        axes[0].legend(unique.values(), unique.keys(), loc="best", fontsize=9)

    counts = []
    for degree in DEGREE_ORDER:
        count = len(example_pivots[example_pivots["swing_degree"] == degree])
        counts.append(count)
    axes[1].bar(DEGREE_ORDER, counts, color=[DEGREE_COLORS[item] for item in DEGREE_ORDER], alpha=0.75)
    axes[1].set_ylabel("Structural pivots")
    axes[1].set_title("Pivot count by degree", fontsize=11)
    axes[1].grid(axis="y", alpha=0.2)
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)
    time_axis.format_axis(axes[0])
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _build_charts(output_dir: Path, specs: pd.DataFrame, degree_pivots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    selected = specs[specs["example_id"].isin(SELECTED_CHART_EXAMPLES)].copy()
    for _, row in selected.iterrows():
        spec = VisualReviewSpec(
            example_id=str(row["example_id"]),
            group=str(row["group"]),
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            rows=int(row["rows"]),
        )
        scenario = str(row["scenario"])
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            output_path = output_dir / "charts" / "degree_comparison" / f"{scenario}_{spec.example_id}_degree_comparison.png"
            _plot_degree_comparison(frame, degree_pivots[degree_pivots["scenario"] == scenario], spec, scenario, output_path)
            status = "ok"
            error = ""
        except Exception as exc:
            output_path = output_dir / "charts" / "degree_comparison" / f"{scenario}_{spec.example_id}_degree_comparison.png"
            status = "error"
            error = str(exc)
        rows.append(
            {
                "scenario": scenario,
                "example_id": spec.example_id,
                "symbol": spec.symbol,
                "timeframe": spec.timeframe,
                "status": status,
                "chart_path": _as_rel(output_path) if status == "ok" else "",
                "error": error,
            }
        )
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, metrics: pd.DataFrame, issues: pd.DataFrame, manual: pd.DataFrame, readiness: pd.DataFrame, elapsed: float) -> None:
    issue_counts = issues["degree_issue"].value_counts().to_dict() if not issues.empty else {}
    h1_policy = readiness[readiness["scenario"] == "h1_m30"].iloc[0].to_dict() if not readiness.empty else {}
    h4_policy = readiness[readiness["scenario"] == "h4_d1"].iloc[0].to_dict() if not readiness.empty else {}
    lines = [
        "# WaveCount Fase 2.3.3 - calibracion de grados",
        "",
        "Fecha: 2026-05-23",
        "",
        "## Objetivo",
        "",
        "Auditar si `minor`, `intermediate` y `major` estan visualmente diferenciados antes de Fase 2.5. No se cambian umbrales ni artifacts canonicos.",
        "",
        "## Configuracion actual",
        "",
        "| grado | min ATR | min movimiento relativo | min barras |",
        "|---|---:|---:|---:|",
    ]
    for spec in DEFAULT_SWING_DEGREES:
        lines.append(
            f"| `{spec.name}` | {spec.config.min_leg_atr_multiplier:.1f} | {spec.config.min_leg_relative_move_pct:.3f} | {spec.config.min_leg_bars} |"
        )
    lines.extend(
        [
            "",
            "Los umbrales son globales, no dependen de activo ni timeframe.",
            "",
            "## Resultado",
            "",
            f"- filas metricas grado/ejemplo: {len(metrics)}",
            f"- ejemplos con issues: {int((issues['degree_issue'] != 'degree_reasonable').sum()) if not issues.empty else 0}",
            f"- distribucion de issues: {issue_counts}",
            f"- evidencias manuales incorporadas: {len(manual)}",
            f"- tiempo de ejecucion: {elapsed:.2f}s",
            "",
            "## Decision",
            "",
            f"- H1/M30: {h1_policy.get('readiness', '')}; grado recomendado: {h1_policy.get('recommended_primary_degree', '')}.",
            f"- H4/D1: {h4_policy.get('readiness', '')}; grado recomendado: {h4_policy.get('recommended_primary_degree', '')}.",
            "- Mantener umbrales actuales por ahora. Si se cambian, debe abrirse una fase experimental separada y regenerar Fase 1.6/downstream sin sobrescribir canonico.",
            "- `minor` queda como detalle interno; `intermediate` como mejor base inicial; `major` como contexto superior.",
            "",
            "## Cierre",
            "",
            "H1/M30 debe quedar como auxiliar/case bank. H4/D1 debe ser la base principal candidata para Fase 2.5, con `intermediate` como grado primario y `major` como contexto.",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_3_3_DEGREE_CALIBRATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_degree_calibration_audit(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    h1_dir: Path = DEFAULT_PHASE23_H1_DIR,
    h4_dir: Path = DEFAULT_PHASE23_H4_DIR,
    manual_feedback_dir: Path = DEFAULT_MANUAL_FEEDBACK_DIR,
) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    h1 = _load_scenario("h1_m30", h1_dir, DEFAULT_VISUAL_REVIEW_SPECS)
    h4 = _load_scenario("h4_d1", h4_dir, H4_D1_VISUAL_REVIEW_SPECS)
    degree_pivots = pd.concat([h1["degree_pivots"], h4["degree_pivots"]], ignore_index=True)
    source_windows = pd.concat([h1["source_windows"], h4["source_windows"]], ignore_index=True)
    specs = pd.concat([h1["specs"], h4["specs"]], ignore_index=True)

    metrics = _build_degree_metrics(degree_pivots, source_windows)
    issues = _build_discrimination_issues(metrics)
    manual = _manual_degree_evidence(manual_feedback_dir)
    policy = _recommended_degree_policy(metrics, issues)
    readiness = _phase25_readiness(metrics, issues)
    charts = _build_charts(output_dir, specs, degree_pivots)

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(tables_dir / "degree_calibration_metrics.csv", index=False)
    issues.to_csv(tables_dir / "degree_discrimination_issues.csv", index=False)
    manual.to_csv(tables_dir / "manual_degree_evidence.csv", index=False)
    policy.to_csv(tables_dir / "recommended_degree_policy.csv", index=False)
    readiness.to_csv(tables_dir / "phase2_5_degree_readiness.csv", index=False)
    charts.to_csv(tables_dir / "degree_comparison_charts.csv", index=False)

    elapsed = perf_counter() - start
    _write_report(output_dir, metrics, issues, manual, readiness, elapsed)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "output_dir": str(output_dir),
        "inputs": {
            "h1_dir": str(h1_dir),
            "h4_dir": str(h4_dir),
            "manual_feedback_dir": str(manual_feedback_dir),
        },
        "rows": {
            "degree_calibration_metrics": len(metrics),
            "degree_discrimination_issues": len(issues),
            "manual_degree_evidence": len(manual),
            "recommended_degree_policy": len(policy),
            "phase2_5_degree_readiness": len(readiness),
            "degree_comparison_charts": len(charts),
        },
        "notes": [
            "Audit only; no thresholds, pivots, counts, strategies, signals, ABC rules, partial rules or wave-5 rules changed.",
            "H4/D1 is recommended as preferred Phase 2.5 base; H1/M30 remains auxiliary.",
        ],
        "outputs": {
            "degree_calibration_metrics": "tables/degree_calibration_metrics.csv",
            "degree_discrimination_issues": "tables/degree_discrimination_issues.csv",
            "manual_degree_evidence": "tables/manual_degree_evidence.csv",
            "recommended_degree_policy": "tables/recommended_degree_policy.csv",
            "phase2_5_degree_readiness": "tables/phase2_5_degree_readiness.csv",
            "degree_comparison_charts": "tables/degree_comparison_charts.csv",
            "report": "WAVECOUNT_PHASE2_3_3_DEGREE_CALIBRATION_REPORT.md",
        },
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.3.3 degree calibration audit.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--h1-dir", type=Path, default=DEFAULT_PHASE23_H1_DIR)
    parser.add_argument("--h4-dir", type=Path, default=DEFAULT_PHASE23_H4_DIR)
    parser.add_argument("--manual-feedback-dir", type=Path, default=DEFAULT_MANUAL_FEEDBACK_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_degree_calibration_audit(
        output_dir=args.output_dir,
        h1_dir=args.h1_dir,
        h4_dir=args.h4_dir,
        manual_feedback_dir=args.manual_feedback_dir,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
