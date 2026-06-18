from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE23_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"
DEFAULT_REAUDIT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_4_visual_reaudit_2026-05-19"
DEFAULT_ABC_FIX_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_abc_fix_2026-05-20"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_manual_feedback_h1_m30_2026-05-21"


@dataclass(frozen=True)
class ManualObservation:
    filename: str
    user_observation: str
    issue_type: str
    manual_assessment: str
    recommended_action: str
    rule_implication: str


OBSERVATIONS: tuple[ManualObservation, ...] = (
    ManualObservation(
        "003_impulse_index_aus200_h1_minor_impulse_006.png",
        "La onda 5 termina pronto.",
        "premature_wave5_completion",
        "downgrade",
        "degrade_to_ambiguous_or_negative",
        "El cierre de onda 5 no debe darse por completo si el extremo estructural natural aparece despues.",
    ),
    ManualObservation(
        "007_impulse_index_aus200_h1_intermediate_impulse_004.png",
        "No se ve realmente diferencia respecto al anterior en la construccion de ondas.",
        "degree_not_discriminative",
        "downgrade",
        "flag_degree_calibration",
        "El grado intermediate no debe replicar visualmente un minor sin aportar escala estructural.",
    ),
    ManualObservation(
        "008_impulse_forex_eurjpy_m30_intermediate_impulse_005.png",
        "La onda 5 deberia terminar en la bajada siguiente.",
        "premature_wave5_completion",
        "downgrade",
        "degrade_to_ambiguous_or_negative",
        "Si el movimiento continua claramente en la misma direccion, el conteo no debe cerrar la onda 5 antes.",
    ),
    ManualObservation(
        "010_impulse_index_aus200_h1_major_impulse_002.png",
        "Es major pero no se ve diferencia clara respecto a otros grados.",
        "degree_not_discriminative",
        "downgrade",
        "flag_degree_calibration",
        "El grado major necesita swings visiblemente mas amplios que minor/intermediate.",
    ),
    ManualObservation(
        "015_partial_123_index_aus200_h1_intermediate_partial123_001.png",
        "No es una onda 1-2-3 valida; los parciales deben dejar continuidad coherente hacia 4-5.",
        "partial_123_too_lax",
        "downgrade",
        "degrade_partial_to_false_candidate",
        "Un 1-2-3 no debe aceptarse solo por tres pivotes alternantes si no hay desplazamiento claro y continuidad.",
    ),
    ManualObservation(
        "039_near_miss_index_aus200_h1_intermediate_impulse_008.png",
        "El usuario lo ve bien.",
        "acceptable_near_miss",
        "keep",
        "keep_as_ambiguous_or_near_miss_example",
        "Un near-miss puede ser metodologicamente util si la estructura es legible aunque no sea impulso limpio.",
    ),
    ManualObservation(
        "001_impulse_forex_audjpy_h1_minor_impulse_013.png",
        "La onda 5 termina un poco mas adelante.",
        "premature_wave5_completion",
        "downgrade",
        "mark_as_premature_completion",
        "El motor necesita distinguir impulso cerrado de wave_5_in_progress o cierre prematuro.",
    ),
    ManualObservation(
        "005_impulse_forex_audjpy_h1_intermediate_impulse_009.png",
        "Esta muy bien y corrige el problema del anterior.",
        "good_reference",
        "keep",
        "keep_as_good_example",
        "Este caso puede servir como referencia positiva para calibrar endpoint de onda 5 y escala intermediate.",
    ),
    ManualObservation(
        "017_partial_123_forex_audjpy_h1_minor_partial123_007.png",
        "Esta mal.",
        "partial_123_too_lax",
        "downgrade",
        "degrade_partial_to_false_candidate",
        "Los parciales minor con escaso breakout tras onda 2 deben degradarse.",
    ),
    ManualObservation(
        "018_partial_123_metals_xagusd_h1_minor_partial123_002.png",
        "Esta mal; parece mas bien onda 4 y 5 que 1-2-3, el 0 no empieza ahi y despues del 3 se cancelaria.",
        "structure_belongs_to_prior_wave_45",
        "downgrade",
        "degrade_partial_to_false_candidate",
        "El motor debe detectar si el supuesto 1-2-3 pertenece a una estructura previa o queda invalidado inmediatamente.",
    ),
    ManualObservation(
        "037_near_miss_forex_audjpy_h1_intermediate_impulse_011.png",
        "Mas o menos bien; revisar regla de onda 5 que no excede onda 3.",
        "truncated_fifth_candidate",
        "keep_with_caution",
        "keep_as_near_miss_not_clean_impulse",
        "La onda 5 que no supera onda 3 puede existir como truncamiento, pero no debe ser impulso limpio.",
    ),
    ManualObservation(
        "041_near_miss_metals_xagusd_h1_minor_impulse_002.png",
        "Conteo mal por la forma.",
        "visual_shape_invalid",
        "downgrade",
        "degrade_to_false_or_ambiguous",
        "Aunque las reglas geometricas permitan el caso, la forma visual debe penalizarse con fuerza.",
    ),
)


def _load_phase_tables(phase23_dir: Path, reaudit_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = pd.read_csv(phase23_dir / "tables" / "visual_review_candidates.csv")
    reaudit = pd.read_csv(reaudit_dir / "tables" / "phase2_3_visual_reaudit.csv")
    return candidates, reaudit


def _find_candidate_by_filename(candidates: pd.DataFrame, filename: str) -> pd.Series:
    matches = candidates[candidates["chart_path"].astype(str).str.endswith(filename)]
    if len(matches) != 1:
        raise ValueError(f"Expected one candidate for {filename}, found {len(matches)}")
    return matches.iloc[0]


def _lookup_reaudit(reaudit: pd.DataFrame, candidate_id: str) -> dict[str, Any]:
    matches = reaudit[reaudit["candidate_id"] == candidate_id]
    if matches.empty:
        return {}
    return matches.iloc[0].to_dict()


def _as_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _build_manual_cases(
    *,
    phase23_dir: Path,
    candidates: pd.DataFrame,
    reaudit: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for obs in OBSERVATIONS:
        candidate = _find_candidate_by_filename(candidates, obs.filename)
        prior = _lookup_reaudit(reaudit, str(candidate["candidate_id"]))
        chart_abs = phase23_dir / str(candidate["chart_path"])
        if not chart_abs.exists():
            raise FileNotFoundError(chart_abs)
        rows.append(
            {
                "candidate_order": int(candidate["candidate_order"]),
                "candidate_id": candidate["candidate_id"],
                "filename": obs.filename,
                "chart_path": candidate["chart_path"],
                "chart_path_absolute": str(chart_abs),
                "review_category": candidate["review_category"],
                "symbol": candidate["symbol"],
                "timeframe": candidate["timeframe"],
                "swing_degree": candidate["swing_degree"],
                "direction": candidate["direction"],
                "prior_visual_status": prior.get("visual_count_status", ""),
                "prior_visual_quality_score": prior.get("visual_quality_score", ""),
                "prior_degree_fit": prior.get("degree_fit", ""),
                "prior_suggested_action": prior.get("suggested_action", ""),
                "prior_notes": prior.get("visual_notes", ""),
                "user_observation": obs.user_observation,
                "issue_type": obs.issue_type,
                "manual_assessment": obs.manual_assessment,
                "recommended_action": obs.recommended_action,
                "rule_implication": obs.rule_implication,
            }
        )
    return pd.DataFrame(rows).sort_values("candidate_order").reset_index(drop=True)


def _rule_implications(cases: pd.DataFrame) -> pd.DataFrame:
    definitions = [
        {
            "rule_area": "wave5_endpoint",
            "triggered_by_issue_types": "premature_wave5_completion,truncated_fifth_candidate",
            "evidence_cases": _ids(cases, {"premature_wave5_completion", "truncated_fifth_candidate"}),
            "severity": "important",
            "recommendation": "Separar impulso limpio cerrado de wave_5_in_progress, premature_wave5_completion y truncated_fifth_candidate.",
            "hard_or_soft": "soft_until_formalized",
            "do_now": "document_only",
        },
        {
            "rule_area": "degree_calibration",
            "triggered_by_issue_types": "degree_not_discriminative",
            "evidence_cases": _ids(cases, {"degree_not_discriminative"}),
            "severity": "important",
            "recommendation": "Revisar umbrales minor/intermediate/major para que major/intermediate no repliquen conteos micro.",
            "hard_or_soft": "methodological_threshold",
            "do_now": "document_only",
        },
        {
            "rule_area": "partial_123_quality",
            "triggered_by_issue_types": "partial_123_too_lax,structure_belongs_to_prior_wave_45",
            "evidence_cases": _ids(cases, {"partial_123_too_lax", "structure_belongs_to_prior_wave_45"}),
            "severity": "important",
            "recommendation": "Exigir desplazamiento claro de onda 3, continuidad posterior razonable y no pertenecer a onda 4-5 previa.",
            "hard_or_soft": "soft_rule_candidate",
            "do_now": "document_only",
        },
        {
            "rule_area": "visual_shape_filter",
            "triggered_by_issue_types": "visual_shape_invalid",
            "evidence_cases": _ids(cases, {"visual_shape_invalid"}),
            "severity": "minor_to_important",
            "recommendation": "Penalizar formas que cumplen reglas numericas pero no son legibles sobre velas.",
            "hard_or_soft": "soft_rule_candidate",
            "do_now": "document_only",
        },
        {
            "rule_area": "positive_examples",
            "triggered_by_issue_types": "good_reference,acceptable_near_miss",
            "evidence_cases": _ids(cases, {"good_reference", "acceptable_near_miss"}),
            "severity": "supporting",
            "recommendation": "Usar estos casos como referencia visual, no como optimizacion de reglas.",
            "hard_or_soft": "reference_set",
            "do_now": "document_only",
        },
    ]
    return pd.DataFrame(definitions)


def _ids(cases: pd.DataFrame, issue_types: set[str]) -> str:
    return ";".join(cases.loc[cases["issue_type"].isin(issue_types), "candidate_id"].astype(str).tolist())


def _abc_legacy_note(phase23_dir: Path, abc_fix_dir: Path) -> dict[str, Any]:
    legacy_md = phase23_dir / "tables" / "visual_review_candidates.md"
    abc_fix_report = abc_fix_dir / "WAVECOUNT_ABC_FIX_REPORT.md"
    legacy_abc_links = 0
    if legacy_md.exists():
        legacy_abc_links = sum(1 for line in legacy_md.read_text(encoding="utf-8-sig").splitlines() if "charts/abc/" in line)
    return {
        "phase23_h1_m30_index": _as_rel(legacy_md),
        "legacy_abc_links_in_phase23_index": legacy_abc_links,
        "abc_fix_dir": _as_rel(abc_fix_dir),
        "abc_fix_report_exists": abc_fix_report.exists(),
        "decision": "Do not use Phase 2.3 H1/M30 ABC links as current ABC evidence; use phase2_abc_fix_2026-05-20 until corrected ABC is integrated.",
    }


def _write_report(output_dir: Path, cases: pd.DataFrame, rules: pd.DataFrame, abc_note: dict[str, Any]) -> None:
    wave5 = cases[cases["issue_type"].isin(["premature_wave5_completion", "truncated_fifth_candidate"])]
    partials = cases[cases["issue_type"].isin(["partial_123_too_lax", "structure_belongs_to_prior_wave_45"])]
    degree = cases[cases["issue_type"] == "degree_not_discriminative"]
    keep = cases[cases["manual_assessment"].isin(["keep", "keep_with_caution"])]
    downgrade = cases[cases["manual_assessment"] == "downgrade"]

    lines = [
        "# WaveCount Phase 2.3 Manual Feedback H1/M30",
        "",
        f"Fecha: {datetime.now().date().isoformat()}",
        "",
        "## Resumen",
        "",
        "Se incorporan las observaciones manuales del usuario sobre Fase 2.3 H1/M30.",
        "No se cambian reglas ni se regeneran conteos. Esta fase convierte la revision",
        "visual en evidencia metodologica para decidir ajustes futuros.",
        "",
        f"- casos revisados por el usuario: {len(cases)}",
        f"- casos a degradar: {len(downgrade)}",
        f"- casos a conservar o conservar con cautela: {len(keep)}",
        f"- problemas de endpoint de onda 5: {len(wave5)}",
        f"- problemas de partial 1-2-3: {len(partials)}",
        f"- problemas de calibracion de grado: {len(degree)}",
        "",
        "## Lectura Metodologica",
        "",
        "La revision confirma que el motor puede encontrar estructuras utiles, pero la",
        "muestra H1/M30 es sensible a cierres prematuros de onda 5, parciales demasiado",
        "laxos y grados que no siempre se diferencian visualmente. Por tanto, Fase 2.3",
        "H1/M30 debe quedar como muestra auxiliar y banco de casos, no como base unica",
        "para reglas operativas.",
        "",
        "## Casos A Conservar",
        "",
    ]
    if keep.empty:
        lines.append("- Ninguno.")
    else:
        for _, row in keep.iterrows():
            lines.append(f"- `{row['candidate_id']}`: {row['user_observation']} Accion: `{row['recommended_action']}`.")
    lines.extend(["", "## Casos A Degradar", ""])
    if downgrade.empty:
        lines.append("- Ninguno.")
    else:
        for _, row in downgrade.iterrows():
            lines.append(f"- `{row['candidate_id']}`: `{row['issue_type']}`. {row['user_observation']}")
    lines.extend(
        [
            "",
            "## Reglas Candidatas",
            "",
            "- Onda 5: no cerrar impulso limpio si el extremo visual natural queda mas adelante.",
            "- Quinta truncada: puede existir, pero debe quedar como `near_miss`,",
            "  `truncated_fifth_candidate` o `ambiguous_count`, no como impulso limpio.",
            "- Parcial 1-2-3: no basta con tres swings alternantes; debe haber desplazamiento",
            "  claro de onda 3 y no invalidacion inmediata posterior.",
            "- Grados: `major` e `intermediate` deben diferenciarse visualmente de `minor`.",
            "",
            "## ABC",
            "",
            f"- enlaces ABC legacy detectados en el indice Fase 2.3: {abc_note['legacy_abc_links_in_phase23_index']}",
            f"- decision: {abc_note['decision']}",
            "",
            "## Decision",
            "",
            "No se debe avanzar a Fase 2.5 usando H1/M30 como evidencia principal hasta",
            "formalizar los ajustes anteriores. H4/D1 parece una base visual mas robusta",
            "para ondas amplias, mientras H1/M30 queda como muestra auxiliar para detectar",
            "fallos finos y calibrar reglas.",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_3_MANUAL_FEEDBACK_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_manual_feedback(
    phase23_dir: Path = DEFAULT_PHASE23_DIR,
    reaudit_dir: Path = DEFAULT_REAUDIT_DIR,
    abc_fix_dir: Path = DEFAULT_ABC_FIX_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started_at = datetime.now()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    candidates, reaudit = _load_phase_tables(phase23_dir, reaudit_dir)
    cases = _build_manual_cases(phase23_dir=phase23_dir, candidates=candidates, reaudit=reaudit)
    rules = _rule_implications(cases)
    abc_note = _abc_legacy_note(phase23_dir, abc_fix_dir)

    cases_to_downgrade = cases[cases["manual_assessment"] == "downgrade"].copy()
    cases_to_keep = cases[cases["manual_assessment"].isin(["keep", "keep_with_caution"])].copy()
    degree_issues = cases[cases["issue_type"] == "degree_not_discriminative"].copy()
    partial_issues = cases[cases["issue_type"].isin(["partial_123_too_lax", "structure_belongs_to_prior_wave_45"])].copy()
    wave5_issues = cases[cases["issue_type"].isin(["premature_wave5_completion", "truncated_fifth_candidate"])].copy()

    cases.to_csv(tables_dir / "manual_feedback_cases.csv", index=False)
    rules.to_csv(tables_dir / "rule_implications.csv", index=False)
    cases_to_downgrade.to_csv(tables_dir / "cases_to_downgrade.csv", index=False)
    cases_to_keep.to_csv(tables_dir / "cases_to_keep.csv", index=False)
    degree_issues.to_csv(tables_dir / "degree_calibration_issues.csv", index=False)
    partial_issues.to_csv(tables_dir / "partial_123_issues.csv", index=False)
    wave5_issues.to_csv(tables_dir / "wave5_endpoint_issues.csv", index=False)

    _write_report(output_dir, cases, rules, abc_note)

    elapsed = (datetime.now() - started_at).total_seconds()
    meta = {
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "inputs": {
            "phase2_3_h1_m30": str(phase23_dir),
            "phase2_3_2_4_reaudit": str(reaudit_dir),
            "abc_fix": str(abc_fix_dir),
        },
        "counts": {
            "manual_feedback_cases": len(cases),
            "cases_to_downgrade": len(cases_to_downgrade),
            "cases_to_keep": len(cases_to_keep),
            "degree_calibration_issues": len(degree_issues),
            "partial_123_issues": len(partial_issues),
            "wave5_endpoint_issues": len(wave5_issues),
        },
        "abc_note": abc_note,
        "outputs": {
            "manual_feedback_cases": "tables/manual_feedback_cases.csv",
            "rule_implications": "tables/rule_implications.csv",
            "cases_to_downgrade": "tables/cases_to_downgrade.csv",
            "cases_to_keep": "tables/cases_to_keep.csv",
            "degree_calibration_issues": "tables/degree_calibration_issues.csv",
            "partial_123_issues": "tables/partial_123_issues.csv",
            "wave5_endpoint_issues": "tables/wave5_endpoint_issues.csv",
            "report": "WAVECOUNT_PHASE2_3_MANUAL_FEEDBACK_REPORT.md",
        },
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount H1/M30 manual feedback artifacts.")
    parser.add_argument("--phase23-dir", type=Path, default=DEFAULT_PHASE23_DIR)
    parser.add_argument("--reaudit-dir", type=Path, default=DEFAULT_REAUDIT_DIR)
    parser.add_argument("--abc-fix-dir", type=Path, default=DEFAULT_ABC_FIX_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_manual_feedback(
        phase23_dir=args.phase23_dir,
        reaudit_dir=args.reaudit_dir,
        abc_fix_dir=args.abc_fix_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
