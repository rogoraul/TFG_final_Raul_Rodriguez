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
from .wavecount_h4_d1_gallery import H4_D1_VISUAL_REVIEW_SPECS
from .wavecount_partial123 import Partial123Config, diagnose_partial123_candidate_row, partial123_config_to_dict
from .wavecount_visual_review_gallery import DEFAULT_VISUAL_REVIEW_SPECS, VisualReviewSpec, _build_source_tables


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_H1_M30_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"
DEFAULT_H4_D1_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
DEFAULT_MANUAL_FEEDBACK_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_manual_feedback_h1_m30_2026-05-21"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_partial123_2026-05-21"


MANUAL_PARTIAL_IDS = {
    "partial_123_index_aus200_h1_intermediate_partial123_001": {
        "manual_interpretation": "No es una onda 1-2-3 valida; necesita continuidad coherente hacia 4-5 o no invalidarse enseguida.",
        "manual_final_label": "partial_123_too_lax",
    },
    "partial_123_forex_audjpy_h1_minor_partial123_007": {
        "manual_interpretation": "No debe mantenerse como parcial util solo por tener tres swings alternantes.",
        "manual_final_label": "partial_123_too_lax",
    },
    "partial_123_metals_xagusd_h1_minor_partial123_002": {
        "manual_interpretation": "Parece mas bien una onda 4-5 previa; el punto 0 no deberia empezar ahi y tras el 3 se cancela.",
        "manual_final_label": "belongs_to_prior_wave_45",
    },
}


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
    candidates_path = phase_dir / "tables" / "visual_review_candidates.csv"
    windows_path = phase_dir / "tables" / "source_windows.csv"
    candidates = pd.read_csv(candidates_path)
    source_windows = pd.read_csv(windows_path)
    specs = _scenario_specs(source_windows, fallback_specs)
    source_tables = _build_source_tables(specs, PivotConfig())
    candidates["scenario"] = scenario
    candidates["phase_dir"] = str(phase_dir)
    candidates["chart_path_absolute"] = candidates["chart_path"].apply(lambda value: str((phase_dir / str(value)).resolve()))
    degree_pivots = source_tables["degree_pivots"].copy()
    degree_pivots["scenario"] = scenario
    return {
        "candidates": candidates,
        "degree_pivots": degree_pivots,
        "source_windows": source_windows.assign(scenario=scenario),
    }


def _load_manual_feedback(manual_feedback_dir: Path) -> pd.DataFrame:
    path = manual_feedback_dir / "tables" / "partial_123_issues.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame["scenario"] = "h1_m30"
    return frame


def _diagnose_partials(candidates: pd.DataFrame, degree_pivots: pd.DataFrame, config: Partial123Config) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    partials = candidates[candidates["review_category"] == "partial_123"].copy()
    for _, row in partials.iterrows():
        scenario = str(row.get("scenario", ""))
        scenario_pivots = degree_pivots[degree_pivots["scenario"] == scenario].copy()
        diagnosis = diagnose_partial123_candidate_row(row, scenario_pivots, config=config)
        diagnosis["scenario"] = scenario
        diagnosis["candidate_order"] = int(row.get("candidate_order", 0))
        diagnosis["chart_path"] = row.get("chart_path", "")
        diagnosis["chart_path_absolute"] = row.get("chart_path_absolute", "")
        if diagnosis["candidate_id"] in MANUAL_PARTIAL_IDS:
            diagnosis.update(MANUAL_PARTIAL_IDS[diagnosis["candidate_id"]])
        else:
            diagnosis["manual_interpretation"] = ""
            diagnosis["manual_final_label"] = ""
        rows.append(diagnosis)
    diagnostics = pd.DataFrame(rows)
    if diagnostics.empty:
        return diagnostics
    return diagnostics.sort_values(["scenario", "candidate_order"]).reset_index(drop=True)


def _manual_cases(diagnostics: pd.DataFrame, manual_feedback: pd.DataFrame) -> pd.DataFrame:
    if diagnostics.empty:
        return pd.DataFrame()
    manual_ids = set(MANUAL_PARTIAL_IDS)
    manual_diag = diagnostics[diagnostics["candidate_id"].isin(manual_ids)].copy()
    if manual_feedback.empty:
        return manual_diag
    feedback_cols = [
        "candidate_id",
        "issue_type",
        "manual_assessment",
        "recommended_action",
        "user_observation",
        "rule_implication",
    ]
    feedback = manual_feedback[[column for column in feedback_cols if column in manual_feedback.columns]].copy()
    merged = manual_diag.merge(feedback, on="candidate_id", how="left")
    return merged.sort_values("candidate_order").reset_index(drop=True)


def _reclassified_cases(diagnostics: pd.DataFrame, manual_cases: pd.DataFrame) -> pd.DataFrame:
    if diagnostics.empty:
        return diagnostics
    relevant_statuses = {"partial_123_too_lax", "belongs_to_prior_wave_45", "invalidated_after_3", "ambiguous_partial"}
    relevant = diagnostics[diagnostics["partial123_status"].isin(relevant_statuses)].copy()
    if not manual_cases.empty:
        relevant = pd.concat([relevant, manual_cases[diagnostics.columns.intersection(manual_cases.columns)]], ignore_index=True)
    if relevant.empty:
        return relevant
    return relevant.drop_duplicates(subset=["scenario", "candidate_id"]).sort_values(["scenario", "candidate_order"]).reset_index(drop=True)


def _rule_candidates(diagnostics: pd.DataFrame, manual_cases: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule_candidate": "wave3_must_displace_visibly",
                "purpose": "avoid accepting 1-2-3 where wave 3 barely exceeds wave 1",
                "status": "implemented_as_diagnostic",
                "evidence_count": int((diagnostics["partial123_status"] == "partial_123_too_lax").sum()) if not diagnostics.empty else 0,
                "manual_evidence_cases": ";".join(manual_cases.loc[manual_cases["manual_final_label"] == "partial_123_too_lax", "candidate_id"].astype(str).tolist()) if not manual_cases.empty else "",
                "hard_or_soft": "soft_until_more_manual_review",
                "anti_lookahead_note": "uses only the four pivots already required for partial detection",
            },
            {
                "rule_candidate": "post_3_invalidates_partial",
                "purpose": "flag partial 1-2-3 when immediate post-3 structure breaks wave 2",
                "status": "implemented_as_retrospective_diagnostic",
                "evidence_count": int((diagnostics["partial123_status"] == "invalidated_after_3").sum()) if not diagnostics.empty else 0,
                "manual_evidence_cases": "",
                "hard_or_soft": "diagnostic_not_live_filter",
                "anti_lookahead_note": "post-3 pivots are future relative to partial_detected_at and only usable after latency/confirmation",
            },
            {
                "rule_candidate": "possible_prior_wave_45_context",
                "purpose": "warn when the origin may be a higher low/high inside a prior structure instead of a fresh 0 point",
                "status": "implemented_as_soft_context",
                "evidence_count": int((diagnostics["possible_prior_wave_45_context"].astype(bool)).sum()) if not diagnostics.empty else 0,
                "manual_evidence_cases": ";".join(manual_cases.loc[manual_cases["manual_final_label"] == "belongs_to_prior_wave_45", "candidate_id"].astype(str).tolist()) if not manual_cases.empty else "",
                "hard_or_soft": "soft_context",
                "anti_lookahead_note": "uses prior structural pivots only",
            },
            {
                "rule_candidate": "partial_123_is_not_signal",
                "purpose": "keep valid partials as provisional context toward 4-5, never as execution signal",
                "status": "documented",
                "evidence_count": int((diagnostics["partial123_status"].isin(["valid_partial_123", "partial_123_provisional"])).sum()) if not diagnostics.empty else 0,
                "manual_evidence_cases": "",
                "hard_or_soft": "methodological_guard",
                "anti_lookahead_note": "live state remains provisional until later confirmation",
            },
        ]
    )


def _interpretation_rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "partial123_status": "valid_partial_123",
                "meaning": "visual 0-1-2-3 is coherent and later structure confirms continuation",
                "live_read": "partial_123_provisional",
                "use": "good methodology example, not signal",
            },
            {
                "partial123_status": "partial_123_provisional",
                "meaning": "structure is plausible but lacks post-3 confirmation",
                "live_read": "partial_123_provisional",
                "use": "watch/context only",
            },
            {
                "partial123_status": "partial_123_too_lax",
                "meaning": "wave 3 displacement, breakout or visual quality is too weak",
                "live_read": "ambiguous_partial",
                "use": "downgrade from useful candidate",
            },
            {
                "partial123_status": "belongs_to_prior_wave_45",
                "meaning": "the apparent 0 may belong to a previous structure rather than a fresh count",
                "live_read": "ambiguous_partial",
                "use": "manual review / negative example",
            },
            {
                "partial123_status": "invalidated_after_3",
                "meaning": "post-3 structure breaks wave 2 after latency",
                "live_read": "partial_123_provisional_then_invalidated",
                "use": "retrospective diagnostic",
            },
            {
                "partial123_status": "ambiguous_partial",
                "meaning": "not enough structure or conflicting evidence",
                "live_read": "ambiguous_partial",
                "use": "do not force count",
            },
        ]
    )


def _summary(diagnostics: pd.DataFrame, manual_cases: pd.DataFrame, reclassified: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"metric": "diagnosed_partial_candidates", "value": int(len(diagnostics))},
        {"metric": "manual_partial_cases", "value": int(len(manual_cases))},
        {"metric": "reclassified_cases", "value": int(len(reclassified))},
    ]
    if not diagnostics.empty:
        for status, count in diagnostics["partial123_status"].value_counts().items():
            rows.append({"metric": f"partial123_status_{status}", "value": int(count)})
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
    title = f"{row.get('candidate_id', '')} | {row.get('partial123_status', '')} | {row.get('live_state', '')}"
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


def _write_report(output_dir: Path, diagnostics: pd.DataFrame, manual_cases: pd.DataFrame, reclassified: pd.DataFrame, rules: pd.DataFrame, elapsed: float) -> None:
    status_counts = diagnostics["partial123_status"].value_counts().to_dict() if not diagnostics.empty else {}
    scenario_counts = diagnostics["scenario"].value_counts().to_dict() if not diagnostics.empty else {}
    lines = [
        "# WaveCount Fase 2.3.2 - Parciales 1-2-3",
        "",
        "Fecha: 2026-05-21",
        "",
        "## Objetivo",
        "",
        "Diagnosticar parciales 1-2-3 demasiado laxos sin tocar ABC, grados, estrategias ni senales.",
        "",
        "## Diagnostico",
        "",
        "La seleccion base acepta ventanas de cuatro structural pivots alternantes. Hasta ahora no revisaba con suficiente detalle si la onda 3 desplazaba visualmente, si el parcial quedaba invalidado justo despues del 3 o si el supuesto 0 podia pertenecer a una estructura 4-5 previa.",
        "",
        f"- parciales diagnosticados: {len(diagnostics)}",
        f"- escenarios: {scenario_counts}",
        f"- estados: {status_counts}",
        f"- casos manuales: {len(manual_cases)}",
        f"- casos reclasificados/alertados: {len(reclassified)}",
        f"- tiempo de ejecucion: {elapsed:.2f}s",
        "",
        "## Reglas candidatas",
        "",
    ]
    for _, row in rules.iterrows():
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
            "## Cierre",
            "",
            "Los casos 015, 017 y 018 confirman que habia parciales demasiado laxos. Esta fase no cambia la seleccion base; anade diagnostico y reclasificacion metodologica para no usarlos como ejemplos positivos sin revision.",
            "",
            "El siguiente paso puede ser revisar calibracion de grados o pasar la misma lectura a H4/D1 antes de Fase 2.5.",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_3_2_PARTIAL123_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_partial123_artifacts(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    h1_m30_dir: Path = DEFAULT_H1_M30_DIR,
    h4_d1_dir: Path = DEFAULT_H4_D1_DIR,
    manual_feedback_dir: Path = DEFAULT_MANUAL_FEEDBACK_DIR,
    config: Partial123Config | None = None,
) -> dict[str, Any]:
    config = config or Partial123Config()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    h1 = _load_scenario("h1_m30", h1_m30_dir, DEFAULT_VISUAL_REVIEW_SPECS)
    h4 = _load_scenario("h4_d1", h4_d1_dir, H4_D1_VISUAL_REVIEW_SPECS)
    candidates = pd.concat([h1["candidates"], h4["candidates"]], ignore_index=True)
    degree_pivots = pd.concat([h1["degree_pivots"], h4["degree_pivots"]], ignore_index=True)
    manual_feedback = _load_manual_feedback(manual_feedback_dir)

    diagnostics = _diagnose_partials(candidates, degree_pivots, config)
    manual_cases = _manual_cases(diagnostics, manual_feedback)
    reclassified = _reclassified_cases(diagnostics, manual_cases)
    rule_candidates = _rule_candidates(diagnostics, manual_cases)
    interpretation = _interpretation_rules()
    summary = _summary(diagnostics, manual_cases, reclassified)

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(tables_dir / "partial123_diagnostics.csv", index=False)
    reclassified.to_csv(tables_dir / "partial123_cases_reclassified.csv", index=False)
    manual_cases.to_csv(tables_dir / "partial123_manual_cases_review.csv", index=False)
    rule_candidates.to_csv(tables_dir / "partial123_rule_candidates.csv", index=False)
    interpretation.to_csv(tables_dir / "partial123_interpretation_rules.csv", index=False)
    summary.to_csv(tables_dir / "partial123_summary.csv", index=False)
    chart_rows = _write_review_charts(output_dir, reclassified)
    chart_rows.to_csv(tables_dir / "partial123_diagnostic_charts.csv", index=False)

    elapsed = perf_counter() - start
    _write_report(output_dir, diagnostics, manual_cases, reclassified, rule_candidates, elapsed)
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
        "config": partial123_config_to_dict(config),
        "rows": {
            "diagnostics": len(diagnostics),
            "reclassified": len(reclassified),
            "manual_cases": len(manual_cases),
            "rule_candidates": len(rule_candidates),
            "diagnostic_charts": len(chart_rows),
        },
        "notes": [
            "Diagnostic only; no strategies, signals, backtests, ABC rules or swing degree calibration changed.",
            "Post-3 pivots are used only as retrospective diagnostics unless a future live state machine confirms them after latency.",
        ],
        "outputs": {
            "partial123_diagnostics": "tables/partial123_diagnostics.csv",
            "partial123_cases_reclassified": "tables/partial123_cases_reclassified.csv",
            "partial123_manual_cases_review": "tables/partial123_manual_cases_review.csv",
            "partial123_rule_candidates": "tables/partial123_rule_candidates.csv",
            "partial123_interpretation_rules": "tables/partial123_interpretation_rules.csv",
            "report": "WAVECOUNT_PHASE2_3_2_PARTIAL123_REPORT.md",
        },
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.3.2 partial 1-2-3 diagnostics.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--h1-m30-dir", type=Path, default=DEFAULT_H1_M30_DIR)
    parser.add_argument("--h4-d1-dir", type=Path, default=DEFAULT_H4_D1_DIR)
    parser.add_argument("--manual-feedback-dir", type=Path, default=DEFAULT_MANUAL_FEEDBACK_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_partial123_artifacts(
        output_dir=args.output_dir,
        h1_m30_dir=args.h1_m30_dir,
        h4_d1_dir=args.h4_d1_dir,
        manual_feedback_dir=args.manual_feedback_dir,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
