from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .wavecount_config import PivotConfig
from .wavecount_h4_d1_gallery import H4_D1_VISUAL_REVIEW_SPECS
from .wavecount_visual_review_gallery import DEFAULT_VISUAL_REVIEW_SPECS, VisualReviewSpec, _build_source_tables
from .wavecount_wave5_endpoint import Wave5EndpointConfig, diagnose_candidate_row, wave5_endpoint_config_to_dict


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_H1_M30_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"
DEFAULT_H4_D1_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
DEFAULT_MANUAL_FEEDBACK_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_manual_feedback_h1_m30_2026-05-21"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_1_wave5_endpoint_2026-05-21"


WAVE5_RELEVANT_MANUAL_TYPES = {
    "premature_wave5_completion",
    "good_reference",
    "truncated_fifth_candidate",
    "acceptable_near_miss",
}


def _as_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _scenario_specs(source_windows: pd.DataFrame, fallback: tuple[VisualReviewSpec, ...]) -> tuple[VisualReviewSpec, ...]:
    if source_windows.empty:
        return fallback
    rows = []
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
    candidates_path = phase_dir / "tables" / "visual_review_candidates.csv"
    windows_path = phase_dir / "tables" / "source_windows.csv"
    if not candidates_path.exists():
        raise FileNotFoundError(candidates_path)
    if not windows_path.exists():
        raise FileNotFoundError(windows_path)
    candidates = pd.read_csv(candidates_path)
    source_windows = pd.read_csv(windows_path)
    specs = _scenario_specs(source_windows, fallback_specs)
    source_tables = _build_source_tables(specs, PivotConfig())
    candidates["scenario"] = scenario
    candidates["phase_dir"] = str(phase_dir)
    candidates["chart_path_absolute"] = candidates["chart_path"].apply(lambda value: str((phase_dir / str(value)).resolve()))
    source_tables["degree_pivots"]["scenario"] = scenario
    return {
        "candidates": candidates,
        "degree_pivots": source_tables["degree_pivots"],
        "source_windows": source_windows.assign(scenario=scenario),
    }


def _load_manual_feedback(manual_feedback_dir: Path) -> pd.DataFrame:
    path = manual_feedback_dir / "tables" / "manual_feedback_cases.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame["scenario"] = "h1_m30"
    return frame


def _diagnose_scenario(candidates: pd.DataFrame, degree_pivots: pd.DataFrame, config: Wave5EndpointConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    impulse_like = candidates[candidates["review_category"].isin(["impulse", "near_miss"])].copy()
    for _, row in impulse_like.iterrows():
        scenario = str(row.get("scenario", ""))
        scenario_pivots = degree_pivots[degree_pivots["scenario"] == scenario].copy()
        diagnosis = diagnose_candidate_row(row, scenario_pivots, config=config)
        diagnosis["scenario"] = scenario
        diagnosis["candidate_order"] = int(row.get("candidate_order", 0))
        diagnosis["chart_path"] = row.get("chart_path", "")
        diagnosis["chart_path_absolute"] = row.get("chart_path_absolute", "")
        rows.append(diagnosis)
    diagnostics = pd.DataFrame(rows)
    if diagnostics.empty:
        return diagnostics
    return diagnostics.sort_values(["scenario", "candidate_order"]).reset_index(drop=True)


def _join_manual_cases(diagnostics: pd.DataFrame, manual_feedback: pd.DataFrame) -> pd.DataFrame:
    if diagnostics.empty or manual_feedback.empty:
        return pd.DataFrame()
    wave5_manual = manual_feedback[manual_feedback["issue_type"].isin(WAVE5_RELEVANT_MANUAL_TYPES)].copy()
    if wave5_manual.empty:
        return pd.DataFrame()
    merged = wave5_manual.merge(
        diagnostics,
        on=["candidate_id", "scenario"],
        how="left",
        suffixes=("_manual", ""),
    )
    ordered = [
        "candidate_order",
        "candidate_id",
        "filename",
        "scenario",
        "symbol",
        "timeframe",
        "swing_degree",
        "direction",
        "issue_type",
        "manual_assessment",
        "recommended_action",
        "user_observation",
        "diagnostic_status",
        "wave5_endpoint_status",
        "proposed_endpoint_classification",
        "future_more_extreme_found",
        "post_wave5_extreme_time",
        "post_wave5_extension_vs_wave5",
        "post_wave5_extension_vs_wave1",
        "causal_note",
        "chart_path_absolute",
    ]
    return merged[[column for column in ordered if column in merged.columns]].sort_values("candidate_order").reset_index(drop=True)


def _cases_reclassified(diagnostics: pd.DataFrame, manual_cases: pd.DataFrame) -> pd.DataFrame:
    if diagnostics.empty:
        return diagnostics
    relevant = diagnostics[
        diagnostics["wave5_endpoint_status"].isin(["premature_wave5_completion", "truncated_fifth_candidate"])
    ].copy()
    if not manual_cases.empty:
        manual_ids = set(manual_cases["candidate_id"].astype(str))
        manual_diag = diagnostics[diagnostics["candidate_id"].astype(str).isin(manual_ids)].copy()
        relevant = pd.concat([relevant, manual_diag], ignore_index=True)
    if relevant.empty:
        return relevant
    relevant = relevant.drop_duplicates(subset=["scenario", "candidate_id"]).sort_values(["scenario", "candidate_order"]).reset_index(drop=True)
    return relevant


def _rule_candidates(diagnostics: pd.DataFrame, manual_cases: pd.DataFrame) -> pd.DataFrame:
    premature_count = int((diagnostics["wave5_endpoint_status"] == "premature_wave5_completion").sum()) if not diagnostics.empty else 0
    truncation_count = int((diagnostics["wave5_endpoint_status"] == "truncated_fifth_candidate").sum()) if not diagnostics.empty else 0
    manual_premature = int((manual_cases["issue_type"] == "premature_wave5_completion").sum()) if not manual_cases.empty and "issue_type" in manual_cases.columns else 0
    return pd.DataFrame(
        [
            {
                "rule_candidate": "post_count_material_wave5_extension",
                "purpose": "degrade clean impulse when wave 5 is followed by a materially more extreme same-direction structural pivot",
                "status": "implemented_as_diagnostic",
                "evidence_count": premature_count,
                "manual_evidence_count": manual_premature,
                "recommended_future_state": "premature_wave5_completion or wave_5_in_progress",
                "hard_or_soft": "soft_until_more_manual_review",
                "anti_lookahead_note": "uses future pivots only for retrospective diagnosis; live code must keep the count provisional until later pivots confirm the endpoint",
            },
            {
                "rule_candidate": "truncated_fifth_separation",
                "purpose": "separate wave 5 failing to exceed wave 3 from clean impulse candidates",
                "status": "implemented_as_diagnostic",
                "evidence_count": truncation_count,
                "manual_evidence_count": int((manual_cases["issue_type"] == "truncated_fifth_candidate").sum()) if not manual_cases.empty and "issue_type" in manual_cases.columns else 0,
                "recommended_future_state": "truncated_fifth_candidate",
                "hard_or_soft": "soft_methodological_label",
                "anti_lookahead_note": "depends only on the six confirmed pivots used by the original window",
            },
            {
                "rule_candidate": "clean_impulse_is_provisional",
                "purpose": "avoid treating a just-detected impulse as final or tradable",
                "status": "documented",
                "evidence_count": int((diagnostics["proposed_endpoint_classification"] == "candidate_impulse_provisional").sum()) if not diagnostics.empty else 0,
                "manual_evidence_count": 0,
                "recommended_future_state": "candidate_impulse_provisional",
                "hard_or_soft": "documentation_guard",
                "anti_lookahead_note": "keeps real-time state honest without reading future bars",
            },
        ]
    )


def _summary(diagnostics: pd.DataFrame, reclassified: pd.DataFrame, manual_cases: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append({"metric": "diagnosed_candidates", "value": int(len(diagnostics))})
    rows.append({"metric": "reclassified_or_manual_cases", "value": int(len(reclassified))})
    rows.append({"metric": "manual_wave5_cases", "value": int(len(manual_cases))})
    if not diagnostics.empty:
        for status, count in diagnostics["wave5_endpoint_status"].value_counts().items():
            rows.append({"metric": f"endpoint_status_{status}", "value": int(count)})
        for scenario, count in diagnostics["scenario"].value_counts().items():
            rows.append({"metric": f"scenario_{scenario}", "value": int(count)})
    return pd.DataFrame(rows)


def _write_annotated_chart(row: pd.Series, output_path: Path) -> bool:
    source = Path(str(row.get("chart_path_absolute", "")))
    if not source.exists():
        return False
    image = plt.imread(source)
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(image)
    ax.axis("off")
    title = (
        f"{row.get('candidate_id', '')} | {row.get('wave5_endpoint_status', '')} | "
        f"{row.get('proposed_endpoint_classification', '')}"
    )
    note = str(row.get("causal_note", ""))
    if len(note) > 170:
        note = note[:167] + "..."
    fig.suptitle(title, fontsize=11, fontweight="bold")
    fig.text(0.02, 0.02, note, fontsize=9, color="#111827")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=130)
    plt.close(fig)
    return True


def _write_review_charts(output_dir: Path, cases: pd.DataFrame) -> pd.DataFrame:
    if cases.empty:
        return pd.DataFrame()
    rows = []
    for _, row in cases.iterrows():
        filename = f"{row.get('scenario', 'scenario')}_{int(row.get('candidate_order', 0)):03d}_{row.get('candidate_id', 'candidate')}.png"
        safe_name = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in filename)
        output_path = output_dir / "charts" / "before_after" / safe_name
        status = "ok" if _write_annotated_chart(row, output_path) else "missing_source"
        rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "scenario": row.get("scenario", ""),
                "status": status,
                "source_chart_path": row.get("chart_path_absolute", ""),
                "diagnostic_chart_path": _as_rel(output_path) if status == "ok" else "",
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    output_dir: Path,
    diagnostics: pd.DataFrame,
    reclassified: pd.DataFrame,
    manual_cases: pd.DataFrame,
    rule_candidates: pd.DataFrame,
    elapsed_seconds: float,
) -> None:
    endpoint_counts = diagnostics["wave5_endpoint_status"].value_counts().to_dict() if not diagnostics.empty else {}
    scenario_counts = diagnostics["scenario"].value_counts().to_dict() if not diagnostics.empty else {}
    premature_manual = (
        manual_cases[manual_cases["issue_type"] == "premature_wave5_completion"]["candidate_id"].astype(str).tolist()
        if not manual_cases.empty and "issue_type" in manual_cases.columns
        else []
    )
    lines = [
        "# WaveCount Fase 2.3.1 - Endpoint de onda 5",
        "",
        "Fecha: 2026-05-21",
        "",
        "## Objetivo",
        "",
        "Revisar si algunos impulsos de Fase 2.3 cierran la onda 5 demasiado pronto.",
        "Esta fase no genera senales, no cambia estrategias y no modifica artifacts canonicos de benchmark.",
        "",
        "## Diagnostico",
        "",
        "La seleccion actual de impulsos en Fase 2.3 viene de ventanas consecutivas de seis structural pivots.",
        "La evaluacion original solo usa esos seis pivots, por lo que es causal respecto al conteo, pero no detecta si el extremo natural de onda 5 aparece unos pivotes confirmados despues.",
        "",
        f"- candidatos diagnosticados: {len(diagnostics)}",
        f"- candidatos por escenario: {scenario_counts}",
        f"- estados endpoint: {endpoint_counts}",
        f"- casos re-clasificados o revisados por evidencia manual: {len(reclassified)}",
        f"- casos manuales de onda 5 usados: {len(manual_cases)}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Decision Metodologica",
        "",
        "- `candidate_impulse` limpio debe entenderse como provisional hasta que el extremo de onda 5 quede confirmado por estructura posterior suficiente.",
        "- Si aparece un structural pivot posterior mas extremo en la misma direccion con desplazamiento material, el caso se marca como `premature_wave5_completion`.",
        "- Si la onda 5 no supera la onda 3, el caso se separa como `truncated_fifth_candidate` o near-miss, no como impulso limpio.",
        "- El diagnostico post-conteo usa pivotes posteriores solo para auditoria retrospectiva; una futura version live debe esperar confirmacion y exponer incertidumbre.",
        "",
        "## Evidencia Manual",
        "",
        f"- casos manuales de quinta prematura: {premature_manual}",
        "",
        "## Reglas Candidatas",
        "",
    ]
    for _, row in rule_candidates.iterrows():
        lines.extend(
            [
                f"### {row['rule_candidate']}",
                "",
                f"- proposito: {row['purpose']}",
                f"- estado: {row['status']}",
                f"- evidencia: {row['evidence_count']}",
                f"- nota anti look-ahead: {row['anti_lookahead_note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Salidas",
            "",
            "- `tables/wave5_endpoint_diagnostics.csv`",
            "- `tables/wave5_cases_reclassified.csv`",
            "- `tables/wave5_rule_candidates.csv`",
            "- `tables/manual_cases_wave5_review.csv`",
            "- `charts/before_after/` con copias anotadas de casos clave",
            "",
            "## Cierre",
            "",
            "El problema de cierre prematuro es real en la muestra H1/M30 revisada manualmente.",
            "La fase queda cerrada como diagnostico/reclasificacion aislada. El siguiente bloque natural es atacar parciales `1-2-3`, manteniendo ABC separado en la fase de fix.",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_3_1_WAVE5_ENDPOINT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_wave5_endpoint_artifacts(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    h1_m30_dir: Path = DEFAULT_H1_M30_DIR,
    h4_d1_dir: Path = DEFAULT_H4_D1_DIR,
    manual_feedback_dir: Path = DEFAULT_MANUAL_FEEDBACK_DIR,
    config: Wave5EndpointConfig | None = None,
) -> dict[str, Any]:
    config = config or Wave5EndpointConfig()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()

    h1 = _load_scenario("h1_m30", h1_m30_dir, DEFAULT_VISUAL_REVIEW_SPECS)
    h4 = _load_scenario("h4_d1", h4_d1_dir, H4_D1_VISUAL_REVIEW_SPECS)
    candidates = pd.concat([h1["candidates"], h4["candidates"]], ignore_index=True)
    degree_pivots = pd.concat([h1["degree_pivots"], h4["degree_pivots"]], ignore_index=True)
    manual_feedback = _load_manual_feedback(manual_feedback_dir)

    diagnostics = _diagnose_scenario(candidates, degree_pivots, config)
    manual_cases = _join_manual_cases(diagnostics, manual_feedback)
    reclassified = _cases_reclassified(diagnostics, manual_cases)
    rules = _rule_candidates(diagnostics, manual_cases)
    summary = _summary(diagnostics, reclassified, manual_cases)

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(tables_dir / "wave5_endpoint_diagnostics.csv", index=False)
    reclassified.to_csv(tables_dir / "wave5_cases_reclassified.csv", index=False)
    rules.to_csv(tables_dir / "wave5_rule_candidates.csv", index=False)
    manual_cases.to_csv(tables_dir / "manual_cases_wave5_review.csv", index=False)
    summary.to_csv(tables_dir / "wave5_endpoint_summary.csv", index=False)

    chart_rows = _write_review_charts(output_dir, reclassified)
    if not chart_rows.empty:
        chart_rows.to_csv(tables_dir / "wave5_diagnostic_charts.csv", index=False)

    elapsed = perf_counter() - start
    _write_report(output_dir, diagnostics, reclassified, manual_cases, rules, elapsed)

    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "output_dir": str(output_dir),
        "inputs": {
            "h1_m30_dir": str(h1_m30_dir),
            "h4_d1_dir": str(h4_d1_dir),
            "manual_feedback_dir": str(manual_feedback_dir),
        },
        "config": wave5_endpoint_config_to_dict(config),
        "rows": {
            "diagnostics": len(diagnostics),
            "reclassified": len(reclassified),
            "manual_cases": len(manual_cases),
            "rule_candidates": len(rules),
            "diagnostic_charts": len(chart_rows),
        },
        "notes": [
            "Diagnostic only; no strategies, signals, backtests or MT5 execution were changed.",
            "Post-count pivots are used only for retrospective audit of premature wave-5 endpoint risk.",
        ],
        "outputs": {
            "wave5_endpoint_diagnostics": "tables/wave5_endpoint_diagnostics.csv",
            "wave5_cases_reclassified": "tables/wave5_cases_reclassified.csv",
            "wave5_rule_candidates": "tables/wave5_rule_candidates.csv",
            "manual_cases_wave5_review": "tables/manual_cases_wave5_review.csv",
            "report": "WAVECOUNT_PHASE2_3_1_WAVE5_ENDPOINT_REPORT.md",
        },
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.3.1 wave-5 endpoint diagnostics.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--h1-m30-dir", type=Path, default=DEFAULT_H1_M30_DIR)
    parser.add_argument("--h4-d1-dir", type=Path, default=DEFAULT_H4_D1_DIR)
    parser.add_argument("--manual-feedback-dir", type=Path, default=DEFAULT_MANUAL_FEEDBACK_DIR)
    parser.add_argument("--post-count-pivots", type=int, default=Wave5EndpointConfig.post_count_pivots)
    parser.add_argument("--min-extension-vs-wave5", type=float, default=Wave5EndpointConfig.min_extension_vs_wave5)
    parser.add_argument("--min-extension-vs-wave1", type=float, default=Wave5EndpointConfig.min_extension_vs_wave1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = Wave5EndpointConfig(
        post_count_pivots=args.post_count_pivots,
        min_extension_vs_wave5=args.min_extension_vs_wave5,
        min_extension_vs_wave1=args.min_extension_vs_wave1,
    )
    meta = build_wave5_endpoint_artifacts(
        output_dir=args.output_dir,
        h1_m30_dir=args.h1_m30_dir,
        h4_d1_dir=args.h4_d1_dir,
        manual_feedback_dir=args.manual_feedback_dir,
        config=config,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
