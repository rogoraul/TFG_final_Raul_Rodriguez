from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDED_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "05_guided_profile"

DEFAULT_PHASE250_DIR = GUIDED_ROOT / "phase2_5_0_guided_context_score_2026-05-24"
DEFAULT_PHASE251_DIR = GUIDED_ROOT / "phase2_5_1_guided_impulse_profile_2026-05-24"
DEFAULT_PHASE252_DIR = GUIDED_ROOT / "phase2_5_2_h4_d1_expansion_2026-05-24"
DEFAULT_PHASE252B_DIR = GUIDED_ROOT / "phase2_5_2b_h1_h4_aux_2026-05-24"
DEFAULT_PHASE253_DIR = GUIDED_ROOT / "phase2_5_3_descriptive_stats_2026-05-24"
DEFAULT_PHASE254_DIR = GUIDED_ROOT / "phase2_5_4_soft_quality_policy_2026-05-24"
DEFAULT_PHASE255_DIR = GUIDED_ROOT / "phase2_5_5_soft_policy_visual_audit_2026-05-24"
DEFAULT_PHASE256_DIR = GUIDED_ROOT / "phase2_5_6_soft_policy_weight_adjustment_2026-05-24"
DEFAULT_PHASE256B_DIR = GUIDED_ROOT / "phase2_5_6b_market_group_bias_audit_2026-05-24"
DEFAULT_PHASE257_DIR = GUIDED_ROOT / "phase2_5_7_market_stratified_expansion_2026-05-24"
DEFAULT_PHASE258_DIR = GUIDED_ROOT / "phase2_5_8_prominence_normalization_audit_2026-05-24"
DEFAULT_PHASE259_DIR = GUIDED_ROOT / "phase2_5_9_robust_prominence_policy_trial_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_10_guided_profile_closure_2026-05-24"

PHASE256_BUCKETS = (
    "high_quality_structure",
    "usable_provisional_structure",
    "visual_watchlist_low_prominence",
    "auxiliary_substructure",
    "auxiliary_low_prominence_substructure",
    "ambiguous_structure",
    "experimental_only",
    "exclude_from_guided_search",
)


def _string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _frame_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Sin filas."
    text = frame.astype("object").where(pd.notna(frame), "").astype(str)
    columns = list(text.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in text.iterrows():
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    else:
        lines.append(_frame_to_markdown(frame))
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _value_counts_rows(frame: pd.DataFrame, column: str, *, phase: str, metric_prefix: str) -> list[dict[str, Any]]:
    if frame.empty or column not in frame.columns:
        return []
    counts = frame[column].fillna("missing").astype(str).value_counts(dropna=False)
    total = int(len(frame))
    rows: list[dict[str, Any]] = []
    for label, count in counts.items():
        rows.append(
            {
                "phase": phase,
                "metric": f"{metric_prefix}_{label}",
                "value": int(count),
                "share_pct": round((int(count) / total * 100) if total else 0.0, 2),
                "interpretation": f"Distribucion de {column} en {phase}.",
            }
        )
    return rows


def build_phase25_phase_inventory(phase_dirs: dict[str, Path]) -> pd.DataFrame:
    rows = [
        {
            "phase": "2.5.0",
            "objective": "Integrar decisiones previas en scoring/contexto guiado.",
            "artifact": _rel_to_repo(phase_dirs["2.5.0"]),
            "main_result": "Capa metodologica de calidad/contexto sin senales.",
            "decision": "Usar como base de trazabilidad, no como politica final.",
            "status": "superseded_by_later_phase",
        },
        {
            "phase": "2.5.1",
            "objective": "Formalizar perfil minimo de impulso H4/D1 intermediate.",
            "artifact": _rel_to_repo(phase_dirs["2.5.1"]),
            "main_result": "Semillas y near-misses del perfil guiado.",
            "decision": "Perfil util como antecedente, refinado despues.",
            "status": "superseded_by_later_phase",
        },
        {
            "phase": "2.5.2",
            "objective": "Expandir muestra H4/D1 de forma controlada.",
            "artifact": _rel_to_repo(phase_dirs["2.5.2"]),
            "main_result": "Matches, near-misses y negativos H4/D1.",
            "decision": "Base empirica inicial para politica blanda.",
            "status": "diagnostic_support",
        },
        {
            "phase": "2.5.2b",
            "objective": "Auditar H1/H4 auxiliar y baja prominencia.",
            "artifact": _rel_to_repo(phase_dirs["2.5.2b"]),
            "main_result": "H1/H4 queda como zoom/subestructura; no base principal.",
            "decision": "Auxiliar vigente.",
            "status": "auxiliary",
        },
        {
            "phase": "2.5.3",
            "objective": "Estadistica descriptiva offline del perfil.",
            "artifact": _rel_to_repo(phase_dirs["2.5.3"]),
            "main_result": "Readiness para formalizar politica blanda.",
            "decision": "Soporte descriptivo.",
            "status": "diagnostic_support",
        },
        {
            "phase": "2.5.4",
            "objective": "Formalizar politica blanda inicial.",
            "artifact": _rel_to_repo(phase_dirs["2.5.4"]),
            "main_result": "Buckets y pesos blandos iniciales.",
            "decision": "Superada por ajuste conservador 2.5.6.",
            "status": "superseded_by_later_phase",
        },
        {
            "phase": "2.5.5",
            "objective": "Auditar visualmente si 2.5.4 era demasiado estricta.",
            "artifact": _rel_to_repo(phase_dirs["2.5.5"]),
            "main_result": "El problema no era exceso de exclusiones, sino algun provisional demasiado pequeno.",
            "decision": "Soporte para ajuste 2.5.6.",
            "status": "diagnostic_support",
        },
        {
            "phase": "2.5.6",
            "objective": "Ajustar buckets/watchlist por baja prominencia.",
            "artifact": _rel_to_repo(phase_dirs["2.5.6"]),
            "main_result": "Politica oficial vigente del bloque 2.5.x.",
            "decision": "Mantener como politica oficial.",
            "status": "official_policy",
        },
        {
            "phase": "2.5.6b",
            "objective": "Auditar sesgo por grupo de mercado desde SQL/artifacts.",
            "artifact": _rel_to_repo(phase_dirs["2.5.6b"]),
            "main_result": "Forex Majors, Index y Metals representados; otros grupos SQL sin evidencia WaveCount 2.5.x.",
            "decision": "Reportar por grupo; no cambiar politica.",
            "status": "diagnostic_support",
        },
        {
            "phase": "2.5.7",
            "objective": "Expansion descriptiva estratificada por mercado.",
            "artifact": _rel_to_repo(phase_dirs["2.5.7"]),
            "main_result": "162 filas; politica 2.5.6 aguanta; Metals requiere advertencia.",
            "decision": "Valida como ampliacion descriptiva.",
            "status": "diagnostic_support",
        },
        {
            "phase": "2.5.8",
            "objective": "Auditar normalizacion de prominencia por grupo/simbolo/timeframe/grado.",
            "artifact": _rel_to_repo(phase_dirs["2.5.8"]),
            "main_result": "Ventana visual y spikes explican parte del problema, especialmente en Metals.",
            "decision": "Probar prominencia robusta como diagnostico.",
            "status": "diagnostic_support",
        },
        {
            "phase": "2.5.9",
            "objective": "Probar prominencia robusta P5-P95 y percentiles comparables.",
            "artifact": _rel_to_repo(phase_dirs["2.5.9"]),
            "main_result": "162/162 buckets unchanged; robust prominence no rescata conteos.",
            "decision": "Adoptar como diagnostico auxiliar; 2.5.6 sigue oficial.",
            "status": "diagnostic_support",
        },
    ]
    return pd.DataFrame(rows)


def build_phase25_final_policy_matrix() -> pd.DataFrame:
    rows = [
        ("H4/D1 intermediate", "official_policy", True, "Base principal; solo calidad estructural, no senal."),
        ("H4/D1 major", "soft_context", True, "Contexto superior y posible estructura de grado alto, no desplaza intermediate como base."),
        ("H4/D1 minor", "auxiliary_only", True, "Subestructura; riesgo de microconteo si se usa como base."),
        ("H1/H4", "auxiliary_only", True, "Zoom/subestructura util, no base principal del TFG."),
        ("M30/H1", "auxiliary_only", False, "Microestructura y banco de fallos; no alimentar busqueda principal."),
        ("clean impulses", "official_policy", True, "Impulsos defendibles pueden quedar como high quality o usable segun 2.5.6."),
        ("provisional impulses", "official_policy", True, "Provisionales si pasan escala/contexto, siempre sin senal."),
        ("partial 1-2-3", "soft_context", True, "Siempre provisional; nunca entrada ni filtro operativo."),
        ("wave5 endpoint uncertainty", "diagnostic_only", True, "No invalida automaticamente; documenta incertidumbre."),
        ("ABC/corrections", "experimental", False, "Solo contexto si hay padre; ABC aislado no es regla fuerte."),
        ("visual prominence", "official_policy", True, "Penalizacion blanda oficial en 2.5.6."),
        ("robust prominence P5-P95", "diagnostic_only", False, "Explica ventanas/spikes; no cambia buckets tras 2.5.9."),
        ("symbol/timeframe/degree percentiles", "diagnostic_only", False, "Utiles para comparar familias, no politica oficial."),
        ("EWO 5-35", "soft_context", True, "Apoyo relativo de momentum/rol de onda; no etiqueta ondas por si solo."),
        ("EMA 50/150", "soft_context", True, "Regimen/transicion/ambiguedad; no regla dura."),
        ("HTF/D1", "soft_context", True, "Contexto superior; no rescata conteos visualmente malos."),
        ("Metals", "diagnostic_only", False, "Soportado con advertencia; baja prominencia no se rescata por robustez."),
        ("Forex Majors", "diagnostic_only", False, "Grupo representado; reportar estratificado."),
        ("Index", "diagnostic_only", False, "Grupo representado; reportar estratificado."),
    ]
    return pd.DataFrame(
        [
            {
                "component": component,
                "final_status": status,
                "can_affect_bucket_now": can_affect,
                "can_generate_signal": False,
                "notes": notes,
            }
            for component, status, can_affect, notes in rows
        ]
    )


def build_phase25_final_results_summary(
    *,
    phase256_scores: pd.DataFrame,
    phase257_scores: pd.DataFrame,
    phase258_recommendation: pd.DataFrame,
    phase258_metals: pd.DataFrame,
    phase259_scores: pd.DataFrame,
    phase259_changes: pd.DataFrame,
    phase259_recommendation: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not phase256_scores.empty:
        rows.append(
            {
                "phase": "2.5.6",
                "metric": "total_candidates",
                "value": int(len(phase256_scores)),
                "share_pct": 100.0,
                "interpretation": "Politica oficial vigente.",
            }
        )
        rows.extend(
            _value_counts_rows(
                phase256_scores,
                "phase256_policy_bucket",
                phase="2.5.6",
                metric_prefix="bucket",
            )
        )
    if not phase257_scores.empty:
        rows.append(
            {
                "phase": "2.5.7",
                "metric": "total_candidates",
                "value": int(len(phase257_scores)),
                "share_pct": 100.0,
                "interpretation": "Expansion descriptiva estratificada por mercado.",
            }
        )
        rows.extend(
            _value_counts_rows(
                phase257_scores,
                "resolved_market_group",
                phase="2.5.7",
                metric_prefix="market_group",
            )
        )
    if not phase258_recommendation.empty:
        rec = phase258_recommendation.iloc[0]
        for metric in ("decision", "robust_improvement_cases", "true_low_metals_cases"):
            rows.append(
                {
                    "phase": "2.5.8",
                    "metric": metric,
                    "value": _string(rec.get(metric)),
                    "share_pct": "",
                    "interpretation": "Auditoria de normalizacion/prominencia.",
                }
            )
    if not phase258_metals.empty:
        rows.extend(
            _value_counts_rows(
                phase258_metals,
                "metals_prominence_diagnosis",
                phase="2.5.8",
                metric_prefix="metals_diagnosis",
            )
        )
    if not phase259_scores.empty:
        rows.append(
            {
                "phase": "2.5.9",
                "metric": "total_candidates",
                "value": int(len(phase259_scores)),
                "share_pct": 100.0,
                "interpretation": "Trial de prominencia robusta.",
            }
        )
        rows.extend(
            _value_counts_rows(
                phase259_scores,
                "phase259_prominence_diagnostic",
                phase="2.5.9",
                metric_prefix="prominence_diagnostic",
            )
        )
    if not phase259_changes.empty:
        rows.extend(
            _value_counts_rows(
                phase259_changes,
                "phase259_bucket_change_vs_256",
                phase="2.5.9",
                metric_prefix="bucket_change",
            )
        )
    if not phase259_recommendation.empty:
        rec = phase259_recommendation.iloc[0]
        rows.append(
            {
                "phase": "2.5.9",
                "metric": "recommendation",
                "value": _string(rec.get("phase2510_recommendation")),
                "share_pct": "",
                "interpretation": _string(rec.get("reason")),
            }
        )
    return pd.DataFrame(rows)


def build_phase25_metals_decision(
    phase257_scores: pd.DataFrame,
    phase258_metals: pd.DataFrame,
    phase259_scores: pd.DataFrame,
) -> pd.DataFrame:
    metals_257 = (
        phase257_scores[phase257_scores.get("resolved_market_group", pd.Series(dtype=str)).astype(str).eq("Metals")]
        if not phase257_scores.empty
        else pd.DataFrame()
    )
    metals_259 = (
        phase259_scores[phase259_scores.get("resolved_market_group", pd.Series(dtype=str)).astype(str).eq("Metals")]
        if not phase259_scores.empty
        else pd.DataFrame()
    )
    rows = [
        {
            "decision_scope": "Metals",
            "final_metals_status": "metals_supported_with_warning",
            "metals_total_phase257": int(len(metals_257)),
            "metals_total_phase259": int(len(metals_259)),
            "metals_h4_d1_low_prominence_cases": int(
                phase258_metals["metals_prominence_diagnosis"].astype(str).str.contains("visual_window_too_large|true_low", regex=True).sum()
            )
            if "metals_prominence_diagnosis" in phase258_metals
            else 0,
            "h4_d1_primary_policy": "Use only when 2.5.6 bucket permits; tiny H4/D1 structures remain watchlist or excluded.",
            "h1_h4_policy": "Auxiliary zoom/substructure, not a replacement for H4/D1 base.",
            "robust_prominence_policy": "Diagnostic-only; does not rescue small Metals counts.",
            "manual_review_need": "Optional before any larger Metals-specific expansion; not blocking this closure.",
            "notes": "Do not exclude the whole Metals group, but do not treat low-prominence Metals H4/D1 examples as strong seeds.",
        }
    ]
    return pd.DataFrame(rows)


def build_phase25_future_path_recommendation(phase259_recommendation: pd.DataFrame) -> pd.DataFrame:
    official_reason = "2.5.x is methodologically closed enough; no bucket changed in 2.5.9 and 2.5.6 remains official."
    if not phase259_recommendation.empty:
        reason = _string(phase259_recommendation.iloc[0].get("reason"))
        if reason:
            official_reason += f" {reason}"
    rows = [
        {
            "path_option": "pause_wavecount_and_return_to_tfg_core",
            "priority": "primary_recommendation",
            "recommended": True,
            "reason": official_reason,
            "do_next": "Use WaveCount findings in the academic writeup and return focus to ENBOLSA/TFG core.",
            "do_not_do": "Do not turn WaveCount scoring into entries, filters, MT5, Telegram or backtests.",
        },
        {
            "path_option": "prepare_academic_writeup_without_more_wavecount",
            "priority": "strong_alternative",
            "recommended": True,
            "reason": "The methodological narrative is now coherent and documented.",
            "do_next": "Draft the WaveCount section as exploratory structural analysis.",
            "do_not_do": "Do not claim empirical edge.",
        },
        {
            "path_option": "expand_descriptive_h4_d1_more_history",
            "priority": "optional_later",
            "recommended": False,
            "reason": "Only useful if more descriptive evidence is needed; it should remain offline and stratified.",
            "do_next": "Open a future Phase 2.6 descriptive expansion if the TFG needs more WaveCount material.",
            "do_not_do": "Do not optimize by profitability or generate signals.",
        },
        {
            "path_option": "manual_review_selected_cases_before_expansion",
            "priority": "conditional",
            "recommended": False,
            "reason": "Useful only before a Metals-specific or larger historical expansion.",
            "do_next": "Review selected Metals/watchlist cases if expansion is reopened.",
            "do_not_do": "Do not block the 2.5.x closure on this.",
        },
        {
            "path_option": "open_phase26_descriptive_expansion",
            "priority": "defer",
            "recommended": False,
            "reason": "Possible future path, but not needed before returning to TFG core.",
            "do_next": "Keep it as future work.",
            "do_not_do": "Do not make it operational.",
        },
    ]
    return pd.DataFrame(rows)


def build_phase25_final_risk_register() -> pd.DataFrame:
    rows = [
        ("confundir WaveCount con estrategia", "open_controlled", "alto", "Documentar que no genera edge ni senales.", "Mantener en memoria/TFG como analisis estructural."),
        ("convertir scoring en senal", "blocked", "alto", "can_generate_signal=false en toda la matriz.", "No conectar a Telegram/MT5/backtests."),
        ("sobreajustar prominencia", "controlled", "medio", "2.5.9 queda diagnostic-only; 2.5.6 no cambia.", "Solo revisar si se abre expansion descriptiva."),
        ("rescatar conteos pequenos por metrica robusta", "blocked", "alto", "Robust prominence no cambia buckets.", "Mantener watchlist/exclusion si visualmente son pequenos."),
        ("extrapolar Metals sin evidencia suficiente", "controlled", "medio", "Metals supported with warning.", "Estratificar futuras muestras y revisar casos pequenos."),
        ("comparar scores entre grupos sin normalizar", "controlled", "medio", "Reportar por grupo y no comparar score bruto como equivalente perfecto.", "Usar percentiles solo como diagnostico."),
        ("usar ABC aislado", "blocked", "alto", "ABC queda experimental/contextual con padre requerido.", "Redisenar correcciones si se quiere fortalecer ABC."),
        ("usar H1/H4 como base principal", "blocked", "medio", "H1/H4 queda auxiliary_only.", "Usarlo solo como zoom/subestructura."),
        ("usar EWO/EMA/HTF como reglas duras", "blocked", "alto", "Se mantienen como soft_context.", "No endurecer sin fase metodologica especifica."),
        ("llevar WaveCount a live/MT5 demasiado pronto", "blocked", "alto", "No live-ready; prominencia visual es offline.", "Investigar ventanas causales solo si se abre trabajo live futuro."),
    ]
    return pd.DataFrame(
        [
            {
                "risk": risk,
                "status": status,
                "impact": impact,
                "mitigation": mitigation,
                "future_action": future_action,
            }
            for risk, status, impact, mitigation, future_action in rows
        ]
    )


def build_phase25_academic_writeup_notes() -> pd.DataFrame:
    rows = [
        (
            "definition",
            "WaveCount se plantea como una capa exploratoria de lectura estructural del precio basada en pivotes causales, swings, grados y conteos candidatos.",
        ),
        (
            "negative_scope",
            "No es una estrategia de trading, no genera entradas, no filtra ENBOLSA y no se ha conectado a MT5 ni a backtests operativos.",
        ),
        (
            "method",
            "El desarrollo se separo por fases para evitar mezclar conteo puro, contexto tecnico, correcciones, scoring blando y diagnosticos de escala.",
        ),
        (
            "main_result",
            "La base metodologica defendible es H4/D1 con grado intermediate, major como contexto y H1/H4 como auxiliar.",
        ),
        (
            "context",
            "EWO, EMA 50/150 y HTF aportan lectura de momentum/regimen, pero solo como contexto blando.",
        ),
        (
            "limitations",
            "ABC y correcciones complejas siguen experimentales; Metals requiere advertencia por baja prominencia y ventanas/spikes.",
        ),
        (
            "future_work",
            "Antes de cualquier uso live haria falta una metrica causal de ventana y una validacion descriptiva mas amplia, siempre sin asumir edge.",
        ),
    ]
    return pd.DataFrame([{"section": section, "writeup_note": note} for section, note in rows])


def build_user_review_if_any() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "review_scope": "none_blocking",
                "should_user_review": False,
                "priority": "none",
                "reason": "2.5.10 is a closure/synthesis phase; no bucket, rule or strategy changed.",
                "optional_review": "Only review selected Metals/watchlist cases if a future descriptive expansion is reopened.",
            }
        ]
    )


def build_report(
    output_dir: Path,
    phase_inventory: pd.DataFrame,
    policy_matrix: pd.DataFrame,
    results_summary: pd.DataFrame,
    metals_decision: pd.DataFrame,
    future_path: pd.DataFrame,
    risks: pd.DataFrame,
) -> None:
    bucket_rows = results_summary[
        results_summary["metric"].astype(str).str.startswith("bucket_")
        & results_summary["phase"].astype(str).eq("2.5.6")
    ]
    future_primary = future_path[future_path["priority"].astype(str).eq("primary_recommendation")]
    metals = metals_decision.iloc[0].to_dict() if not metals_decision.empty else {}
    lines = [
        "# WaveCount Phase 2.5.10 - Guided Profile Closure",
        "",
        "Cierre metodologico del bloque 2.5.x. No crea politica nueva, no recalcula conteos base, no genera senales y no ejecuta backtests.",
        "",
        "## Decision central",
        "",
        "- La politica oficial vigente sigue siendo Fase 2.5.6.",
        "- Fase 2.5.9 queda como diagnostico auxiliar de prominencia robusta; no cambia buckets.",
        "- H4/D1 `intermediate` sigue siendo base principal.",
        "- H1/H4 queda como auxiliar/zoom.",
        "- EWO, EMA/HTF y prominencia robusta no deben convertirse en reglas duras ni senales.",
        "",
        "## Inventario de fases",
        "",
        _frame_to_markdown(phase_inventory[["phase", "status", "decision"]]),
        "",
        "## Buckets oficiales 2.5.6",
        "",
        _frame_to_markdown(bucket_rows[["metric", "value", "share_pct"]]),
        "",
        "## Matriz de politica final",
        "",
        _frame_to_markdown(policy_matrix[["component", "final_status", "can_affect_bucket_now", "can_generate_signal"]]),
        "",
        "## Metals",
        "",
        f"- estado: `{_string(metals.get('final_metals_status'))}`",
        f"- politica H4/D1: {_string(metals.get('h4_d1_primary_policy'))}",
        f"- politica H1/H4: {_string(metals.get('h1_h4_policy'))}",
        "",
        "## Ruta recomendada",
        "",
        _frame_to_markdown(future_primary[["path_option", "reason", "do_next", "do_not_do"]]),
        "",
        "## Riesgos principales",
        "",
        _frame_to_markdown(risks[["risk", "status", "mitigation"]]),
    ]
    (output_dir / "WAVECOUNT_PHASE2_5_10_GUIDED_PROFILE_CLOSURE.md").write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )


def run(
    *,
    phase250_dir: Path = DEFAULT_PHASE250_DIR,
    phase251_dir: Path = DEFAULT_PHASE251_DIR,
    phase252_dir: Path = DEFAULT_PHASE252_DIR,
    phase252b_dir: Path = DEFAULT_PHASE252B_DIR,
    phase253_dir: Path = DEFAULT_PHASE253_DIR,
    phase254_dir: Path = DEFAULT_PHASE254_DIR,
    phase255_dir: Path = DEFAULT_PHASE255_DIR,
    phase256_dir: Path = DEFAULT_PHASE256_DIR,
    phase256b_dir: Path = DEFAULT_PHASE256B_DIR,
    phase257_dir: Path = DEFAULT_PHASE257_DIR,
    phase258_dir: Path = DEFAULT_PHASE258_DIR,
    phase259_dir: Path = DEFAULT_PHASE259_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    phase_dirs = {
        "2.5.0": phase250_dir,
        "2.5.1": phase251_dir,
        "2.5.2": phase252_dir,
        "2.5.2b": phase252b_dir,
        "2.5.3": phase253_dir,
        "2.5.4": phase254_dir,
        "2.5.5": phase255_dir,
        "2.5.6": phase256_dir,
        "2.5.6b": phase256b_dir,
        "2.5.7": phase257_dir,
        "2.5.8": phase258_dir,
        "2.5.9": phase259_dir,
    }
    phase256_scores = _read_csv(phase256_dir / "tables" / "phase256_policy_scores.csv")
    phase257_scores = _read_csv(phase257_dir / "tables" / "phase257_policy_scores.csv")
    phase258_recommendation = _read_csv(phase258_dir / "tables" / "prominence_policy_recommendation.csv")
    phase258_metals = _read_csv(phase258_dir / "tables" / "metals_h4_d1_prominence_audit.csv")
    phase259_scores = _read_csv(phase259_dir / "tables" / "phase259_candidate_policy_scores.csv")
    phase259_changes = _read_csv(phase259_dir / "tables" / "phase256_vs_phase259_bucket_changes.csv")
    phase259_recommendation = _read_csv(phase259_dir / "tables" / "phase2510_recommendation.csv")

    phase_inventory = build_phase25_phase_inventory(phase_dirs)
    policy_matrix = build_phase25_final_policy_matrix()
    results_summary = build_phase25_final_results_summary(
        phase256_scores=phase256_scores,
        phase257_scores=phase257_scores,
        phase258_recommendation=phase258_recommendation,
        phase258_metals=phase258_metals,
        phase259_scores=phase259_scores,
        phase259_changes=phase259_changes,
        phase259_recommendation=phase259_recommendation,
    )
    metals_decision = build_phase25_metals_decision(phase257_scores, phase258_metals, phase259_scores)
    future_path = build_phase25_future_path_recommendation(phase259_recommendation)
    risks = build_phase25_final_risk_register()
    writeup = build_phase25_academic_writeup_notes()
    user_review = build_user_review_if_any()

    outputs = {
        "phase25_phase_inventory": phase_inventory,
        "phase25_final_policy_matrix": policy_matrix,
        "phase25_final_results_summary": results_summary,
        "phase25_metals_decision": metals_decision,
        "phase25_future_path_recommendation": future_path,
        "phase25_final_risk_register": risks,
        "phase25_academic_writeup_notes": writeup,
        "user_review_if_any": user_review,
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name.replace("_", " ").title())

    build_report(output_dir, phase_inventory, policy_matrix, results_summary, metals_decision, future_path, risks)

    phase259_change_counts = (
        phase259_changes["phase259_bucket_change_vs_256"].astype(str).value_counts().to_dict()
        if "phase259_bucket_change_vs_256" in phase259_changes.columns
        else {}
    )
    run_meta = {
        "phase": "2.5.10",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {phase: _rel_to_repo(path) for phase, path in phase_dirs.items()},
        "input_rows": {
            "phase256_policy_scores": int(len(phase256_scores)),
            "phase257_policy_scores": int(len(phase257_scores)),
            "phase258_metals_h4_d1": int(len(phase258_metals)),
            "phase259_candidate_policy_scores": int(len(phase259_scores)),
            "phase259_bucket_changes": int(len(phase259_changes)),
        },
        "phase256_policy_changed": False,
        "rules_changed": False,
        "weights_changed": False,
        "signals_generated": False,
        "backtests_executed": False,
        "base_counts_recomputed": False,
        "phase259_bucket_change_counts": phase259_change_counts,
        "official_policy": "phase2_5_6_soft_policy_weight_adjustment_2026-05-24",
        "runtime_seconds": round(perf_counter() - started, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount phase 2.5.10 guided profile closure artifacts.")
    parser.add_argument("--phase250-dir", type=Path, default=DEFAULT_PHASE250_DIR)
    parser.add_argument("--phase251-dir", type=Path, default=DEFAULT_PHASE251_DIR)
    parser.add_argument("--phase252-dir", type=Path, default=DEFAULT_PHASE252_DIR)
    parser.add_argument("--phase252b-dir", type=Path, default=DEFAULT_PHASE252B_DIR)
    parser.add_argument("--phase253-dir", type=Path, default=DEFAULT_PHASE253_DIR)
    parser.add_argument("--phase254-dir", type=Path, default=DEFAULT_PHASE254_DIR)
    parser.add_argument("--phase255-dir", type=Path, default=DEFAULT_PHASE255_DIR)
    parser.add_argument("--phase256-dir", type=Path, default=DEFAULT_PHASE256_DIR)
    parser.add_argument("--phase256b-dir", type=Path, default=DEFAULT_PHASE256B_DIR)
    parser.add_argument("--phase257-dir", type=Path, default=DEFAULT_PHASE257_DIR)
    parser.add_argument("--phase258-dir", type=Path, default=DEFAULT_PHASE258_DIR)
    parser.add_argument("--phase259-dir", type=Path, default=DEFAULT_PHASE259_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = run(
        phase250_dir=args.phase250_dir,
        phase251_dir=args.phase251_dir,
        phase252_dir=args.phase252_dir,
        phase252b_dir=args.phase252b_dir,
        phase253_dir=args.phase253_dir,
        phase254_dir=args.phase254_dir,
        phase255_dir=args.phase255_dir,
        phase256_dir=args.phase256_dir,
        phase256b_dir=args.phase256b_dir,
        phase257_dir=args.phase257_dir,
        phase258_dir=args.phase258_dir,
        phase259_dir=args.phase259_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
