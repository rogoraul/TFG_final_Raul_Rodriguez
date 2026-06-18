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


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PHASE23_H4_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
DEFAULT_H4_AUDIT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_4_h4_d1_visual_audit_2026-05-20"
DEFAULT_WAVE5_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_1_wave5_endpoint_2026-05-21"
DEFAULT_PARTIAL123_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_partial123_2026-05-21"
DEFAULT_DEGREE_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_3_degree_calibration_2026-05-23"
DEFAULT_ABC_FIX_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_abc_fix_2026-05-20"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_4_h4_d1_visual_closure_2026-05-23"


USER_BEST_EXAMPLE_FEEDBACK: dict[int, dict[str, str]] = {
    2: {"user_label": "dudoso", "user_note": "El usuario lo marca como dudoso."},
    3: {"user_label": "bien", "user_note": "El usuario lo marca como bien."},
    4: {"user_label": "bien", "user_note": "El usuario lo marca como bien."},
    5: {"user_label": "bien", "user_note": "El usuario lo marca como bien."},
    6: {"user_label": "bien", "user_note": "El usuario lo marca como bien."},
    7: {"user_label": "mal", "user_note": "Onda 3 muy pequena; degradar."},
    8: {"user_label": "dudoso", "user_note": "El usuario lo marca como dudoso."},
    9: {"user_label": "dudoso", "user_note": "El usuario lo marca como dudoso."},
    10: {"user_label": "bien", "user_note": "El usuario lo marca como bien."},
    11: {"user_label": "bien", "user_note": "El usuario lo marca como bien."},
    12: {"user_label": "hard_invalid_correct", "user_note": "Mal como impulso, correcto que sea invalido."},
    13: {"user_label": "ignore_phase24", "user_note": "Pertenece a Fase 2.4/contexto; no se usa para cerrar Fase 2.3."},
}


PARTIAL_VISUAL_REVIEW: dict[str, dict[str, Any]] = {
    "013_partial_123_forex_audjpy_h4_intermediate_partial123_002.png": {
        "status": "should_downgrade",
        "score": 2,
        "partial123": "invalidated_after_3",
        "decision": "exclude_from_phase25_rules",
        "note": "Bajista pequeno dentro de arranque alcista posterior claro; sin continuidad bajista.",
    },
    "014_partial_123_metals_xagusd_h4_intermediate_partial123_001.png": {
        "status": "visually_defensible",
        "score": 4,
        "partial123": "valid_partial_123",
        "decision": "keep_as_good_example",
        "note": "Buen 1-2-3 alcista con onda 3 visible y continuacion posterior.",
    },
    "015_partial_123_index_aus200_h4_intermediate_partial123_006.png": {
        "status": "not_usable_for_methodology",
        "score": 1,
        "partial123": "invalidated_after_3",
        "decision": "exclude_from_phase25_rules",
        "note": "1-2-3 bajista comprimido; despues del 3 revierte en subida prolongada.",
    },
    "016_partial_123_forex_audjpy_h4_intermediate_partial123_005.png": {
        "status": "excellent_example",
        "score": 5,
        "partial123": "valid_partial_123",
        "decision": "keep_as_good_example",
        "note": "Estructura alcista limpia y proporcional; 3 desplaza con claridad.",
    },
    "017_partial_123_forex_audjpy_h4_minor_partial123_002.png": {
        "status": "should_downgrade",
        "score": 2,
        "partial123": "invalidated_after_3",
        "decision": "exclude_from_phase25_rules",
        "note": "Lectura menor absorbida por reversion alcista amplia.",
    },
    "018_partial_123_metals_xagusd_h4_minor_partial123_001.png": {
        "status": "visually_defensible",
        "score": 4,
        "partial123": "valid_partial_123",
        "decision": "keep_as_ambiguous_example",
        "note": "Valido como subestructura minor, no como lectura principal.",
    },
    "019_partial_123_index_aus200_h4_minor_partial123_005.png": {
        "status": "visually_defensible",
        "score": 4,
        "partial123": "valid_partial_123",
        "decision": "keep_as_ambiguous_example",
        "note": "Desplazamiento claro, pero compacto; mejor como subestructura.",
    },
    "020_partial_123_forex_audjpy_h4_minor_partial123_005.png": {
        "status": "visually_defensible",
        "score": 4,
        "partial123": "valid_partial_123",
        "decision": "keep_as_ambiguous_example",
        "note": "Compacto pero util como subestructura minor.",
    },
    "021_partial_123_forex_audjpy_h4_major_partial123_003.png": {
        "status": "visually_defensible",
        "score": 4,
        "partial123": "valid_partial_123",
        "decision": "keep_as_good_example",
        "note": "Major legible como contexto o grado superior operable.",
    },
    "022_partial_123_metals_xagusd_h4_major_partial123_003.png": {
        "status": "excellent_example",
        "score": 5,
        "partial123": "valid_partial_123",
        "decision": "keep_as_good_example",
        "note": "Major muy solido, con onda 3 amplia y continuacion fuerte.",
    },
    "023_partial_123_index_aus200_h4_major_partial123_006.png": {
        "status": "not_usable_for_methodology",
        "score": 1,
        "partial123": "invalidated_after_3",
        "decision": "exclude_from_phase25_rules",
        "note": "Bajista debil invalidado por subida posterior a nuevos maximos.",
    },
    "024_partial_123_forex_audjpy_h4_major_partial123_005.png": {
        "status": "excellent_example",
        "score": 5,
        "partial123": "valid_partial_123",
        "decision": "keep_as_good_example",
        "note": "Muy buen 1-2-3 alcista de grado superior.",
    },
}


INVALIDATION_VISUAL_REVIEW: dict[str, dict[str, Any]] = {
    "046_hard_invalid_forex_audjpy_h4_intermediate_impulse_001.png": {
        "score": 5,
        "note": "Invalidez clara por estructura temprana; 4 invade territorio de 1.",
    },
    "047_hard_invalid_metals_xagusd_h4_intermediate_impulse_001.png": {
        "score": 4,
        "note": "Invalidez plausible por 3 corta y 5 dominante.",
    },
    "048_hard_invalid_index_aus200_h4_intermediate_impulse_001.png": {
        "score": 5,
        "note": "Invalidez nitida: 2 bajo origen y 4 invade zona de 1.",
    },
    "049_hard_invalid_forex_audjpy_h4_minor_impulse_001.png": {
        "score": 5,
        "note": "Caso limpio de impulso invalido en grado menor.",
    },
    "050_hard_invalid_metals_xagusd_h4_minor_impulse_002.png": {
        "score": 4,
        "note": "Zona compacta, pero ruptura/origen y proporciones justifican invalidez.",
    },
    "051_hard_invalid_index_aus200_h4_minor_impulse_001.png": {
        "score": 5,
        "note": "Muy claro: 2 bajo origen, 4 solapa y 5 queda corta.",
    },
    "052_hard_invalid_forex_audjpy_h4_major_impulse_001.png": {
        "score": 5,
        "note": "Invalidez fuerte aunque la onda 5 sea un nuevo extremo.",
    },
    "053_hard_invalid_metals_xagusd_h4_major_impulse_001.png": {
        "score": 5,
        "note": "Secuencia 1-3-5 no sostiene impulso; 3 debil y 4 invade territorio.",
    },
    "054_hard_invalid_index_aus200_h4_major_impulse_001.png": {
        "score": 5,
        "note": "Hard invalid claro por origen y solape.",
    },
}


ABC_VISUAL_REVIEW: dict[str, dict[str, Any]] = {
    "025_abc_forex_audjpy_h4_abc_002.png": {"score": 3, "note": "ABC legible pero legacy; usar fix ABC, no como cierre Fase 2.3."},
    "026_abc_metals_xagusd_h4_abc_003.png": {"score": 2, "note": "Legacy sobrecargado; no usar como evidencia limpia."},
    "027_abc_index_aus200_h4_abc_006.png": {"score": 3, "note": "Patron local razonable, pero legacy con duplicaciones."},
    "028_abc_forex_audjpy_h4_abc_005.png": {"score": 2, "note": "Legacy sobreajustado con diagonales cruzadas."},
    "029_abc_index_aus200_h4_abc_005.png": {"score": 3, "note": "Compacto, pero ABC debe revisarse desde fix."},
    "030_abc_forex_audjpy_h4_abc_009.png": {"score": 2, "note": "Legacy largo y cruzado; no aisla ABC dominante."},
    "031_abc_forex_eurjpy_h4_abc_004.png": {"score": 2, "note": "Legacy con abanico de lineas; no limpio."},
    "032_abc_forex_eurusd_h4_abc_002.png": {"score": 2, "note": "Legacy con varias ABC simultaneas."},
    "033_abc_forex_audjpy_h4_abc_003.png": {"score": 3, "note": "Mas limpio que la media, pero se mantiene experimental."},
    "034_abc_forex_audjpy_h4_abc_013.png": {"score": 2, "note": "Legacy saturado sobre tendencia."},
    "035_abc_forex_eurjpy_h4_abc_003.png": {"score": 2, "note": "Solapes fuertes entre candidatos."},
    "036_abc_forex_eurusd_h4_abc_003.png": {"score": 2, "note": "Cluster inicial; patron mayor posible pero no cierre limpio."},
}


IMPULSE_VISUAL_REVIEW: dict[str, dict[str, Any]] = {
    "001_impulse_forex_audjpy_h4_minor_impulse_005.png": {
        "status": "too_micro",
        "score": 3,
        "decision": "keep_as_ambiguous_example",
        "wave5": "clean_or_acceptable",
        "note": "Limpio pero pequeno frente al tramo H4 posterior; subonda, no ejemplo principal.",
    },
    "002_impulse_metals_xagusd_h4_minor_impulse_001.png": {
        "status": "too_micro",
        "score": 3,
        "decision": "keep_as_ambiguous_example",
        "wave5": "clean_or_acceptable",
        "note": "Impulso inicial razonable, pero absorbido por estructura alcista mayor.",
    },
    "003_impulse_index_hk50_h4_minor_impulse_012.png": {
        "status": "plausible_but_needs_review",
        "score": 3,
        "decision": "keep_as_ambiguous_example",
        "wave5": "clean_or_acceptable",
        "note": "Onda 3 desplaza, pero el grado minor no encaja del todo.",
    },
    "004_impulse_forex_eurjpy_h4_minor_impulse_022.png": {
        "status": "visually_forced",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "endpoint_uncertain",
        "note": "Conteo comprimido y zigzagueante; onda 3 no domina visualmente.",
    },
    "005_impulse_forex_eurusd_h4_intermediate_impulse_007.png": {
        "status": "visually_defensible",
        "score": 4,
        "decision": "keep_as_good_example",
        "wave5": "clean_or_acceptable",
        "note": "Impulso bajista defendible, escala H4 correcta.",
    },
    "006_impulse_metals_xagusd_h4_intermediate_impulse_007.png": {
        "status": "excellent_example",
        "score": 5,
        "decision": "keep_as_good_example",
        "wave5": "clean_or_acceptable",
        "note": "Muy buen ejemplo H4: onda 3 amplia y onda 5 natural.",
    },
    "007_impulse_index_aus200_h4_intermediate_impulse_015.png": {
        "status": "excellent_example",
        "score": 5,
        "decision": "keep_as_good_example",
        "wave5": "clean_or_acceptable",
        "note": "Estructura H4 limpia con onda 3 suficiente y 4-5 legibles.",
    },
    "008_impulse_forex_eurusd_h4_intermediate_impulse_012.png": {
        "status": "visually_defensible",
        "score": 4,
        "decision": "keep_as_good_example",
        "wave5": "clean_or_acceptable",
        "note": "Onda 3 clara; tramo algo corto pero defendible.",
    },
    "009_impulse_forex_eurusd_h4_major_impulse_011.png": {
        "status": "visually_forced",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "endpoint_uncertain",
        "note": "Conteo major irregular; 4-5 quedan forzadas.",
    },
    "010_impulse_metals_xpdusd_h4_major_impulse_001.png": {
        "status": "plausible_but_needs_review",
        "score": 3,
        "decision": "keep_as_ambiguous_example",
        "wave5": "endpoint_uncertain",
        "note": "Movimiento amplio pero final muy vertical/volatil; contexto, no ejemplo limpio.",
    },
    "011_impulse_index_aus200_h4_major_impulse_013.png": {
        "status": "visually_defensible",
        "score": 4,
        "decision": "keep_as_good_example",
        "wave5": "clean_or_acceptable",
        "note": "Bueno visualmente, pero similar al intermediate; tratar como contexto superior.",
    },
    "012_impulse_forex_gbpusd_h4_major_impulse_012.png": {
        "status": "plausible_but_needs_review",
        "score": 3,
        "decision": "keep_as_ambiguous_example",
        "wave5": "clean_or_acceptable",
        "note": "Tramo bajista amplio, pero ondas 1-2 son correctivas/laterales.",
    },
    "037_near_miss_forex_audjpy_h4_intermediate_impulse_002.png": {
        "status": "ambiguous",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Fallo de onda 5 y overlap de 4; ejemplo de descarte.",
    },
    "038_near_miss_metals_xagusd_h4_intermediate_impulse_003.png": {
        "status": "ambiguous",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Onda 3 clara, pero 5 falla; near-miss didactico.",
    },
    "039_near_miss_index_aus200_h4_intermediate_impulse_009.png": {
        "status": "ambiguous",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Hasta 3 es legible, pero 4 invade y 5 falla.",
    },
    "040_near_miss_forex_audjpy_h4_minor_impulse_002.png": {
        "status": "too_micro",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Microconteo con fallo de 5; no aporta como impulso principal.",
    },
    "041_near_miss_metals_xagusd_h4_minor_impulse_005.png": {
        "status": "too_micro",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Subtramo pequeno con fallo explicito.",
    },
    "042_near_miss_index_aus200_h4_minor_impulse_005.png": {
        "status": "visually_forced",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Zona correctiva menor; no salva la invalidez visual.",
    },
    "043_near_miss_forex_audjpy_h4_major_impulse_005.png": {
        "status": "ambiguous",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Movimiento amplio, pero fallo de 5 e invasion de 4.",
    },
    "044_near_miss_metals_xagusd_h4_major_impulse_003.png": {
        "status": "not_usable_for_methodology",
        "score": 1,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "El tramo 3-4 rompe la lectura por amplitud y violencia.",
    },
    "045_near_miss_index_aus200_h4_major_impulse_009.png": {
        "status": "ambiguous",
        "score": 2,
        "decision": "exclude_from_phase25_rules",
        "wave5": "truncated_fifth_candidate",
        "note": "Onda 3 clara, pero el final no confirma impulso.",
    },
}


def _as_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in value)


def _text_or(value: object, fallback: str) -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value)
    if not text or text.lower() == "nan":
        return fallback
    return text


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _best_feedback_mapping(best_examples: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in best_examples.reset_index(drop=True).iterrows():
        row_number = int(index) + 1
        feedback = USER_BEST_EXAMPLE_FEEDBACK.get(row_number, {})
        rows.append(
            {
                "best_examples_row": row_number,
                "phase": row.get("phase", ""),
                "candidate_id": row.get("candidate_id", ""),
                "review_category": row.get("review_category", ""),
                "swing_degree": row.get("swing_degree", ""),
                "chart_path": row.get("chart_path", ""),
                "context_chart_path": row.get("context_chart_path", ""),
                "prior_status": row.get("visual_review_status", ""),
                "prior_score": row.get("visual_quality_score", ""),
                "user_label": feedback.get("user_label", ""),
                "user_note": feedback.get("user_note", ""),
                "used_for_phase23_closure": str(row.get("phase", "")) == "phase2_3_h4_count_only",
            }
        )
    return pd.DataFrame(rows)


def _join_diagnostics(
    candidates: pd.DataFrame,
    audit: pd.DataFrame,
    wave5: pd.DataFrame,
    partials: pd.DataFrame,
    degree_issues: pd.DataFrame,
    abc_fixed: pd.DataFrame,
    phase23_h4_dir: Path,
    abc_fix_dir: Path,
) -> pd.DataFrame:
    base = candidates.copy()
    base["scenario"] = "h4_d1"
    base["chart_path_absolute"] = base["chart_path"].apply(lambda value: str((phase23_h4_dir / str(value)).resolve()))
    audit_cols = [
        "candidate_id",
        "visual_review_status",
        "visual_quality_score",
        "swing_degree_fit",
        "suggested_action",
        "visual_notes",
    ]
    if not audit.empty:
        base = base.merge(audit[[column for column in audit_cols if column in audit.columns]], on="candidate_id", how="left")
    if not wave5.empty:
        wave5_h4 = wave5[wave5.get("scenario", "") == "h4_d1"].copy()
        wave5_cols = [
            "candidate_id",
            "wave5_endpoint_status",
            "proposed_endpoint_classification",
            "future_more_extreme_found",
            "post_wave5_extension_vs_wave5",
            "causal_note",
        ]
        base = base.merge(wave5_h4[[column for column in wave5_cols if column in wave5_h4.columns]], on="candidate_id", how="left")
    if not partials.empty:
        partials_h4 = partials[partials.get("scenario", "") == "h4_d1"].copy()
        partial_cols = [
            "candidate_id",
            "partial123_status",
            "live_state",
            "wave3_too_weak",
            "post_3_invalidates",
            "post_3_confirms",
            "possible_prior_wave_45_context",
            "causal_note",
        ]
        base = base.merge(
            partials_h4[[column for column in partial_cols if column in partials_h4.columns]],
            on="candidate_id",
            how="left",
            suffixes=("", "_partial123"),
        )
    if not degree_issues.empty:
        degree_h4 = degree_issues[degree_issues.get("scenario", "") == "h4_d1"].copy()
        base = base.merge(
            degree_h4[["example_id", "degree_issue"]],
            on="example_id",
            how="left",
        )
    if not abc_fixed.empty:
        fixed_h4 = abc_fixed[abc_fixed.get("phase", "") == "h4"].copy()
        fixed_h4 = fixed_h4[["source_id", "fixed_chart_path", "abc_interpretation"]].copy()
        fixed_h4["fixed_chart_path_absolute"] = fixed_h4["fixed_chart_path"].apply(
            lambda value: str((abc_fix_dir / str(value)).resolve()) if isinstance(value, str) and value else ""
        )
        base = base.merge(fixed_h4, on="source_id", how="left")
    return base


def _degree_policy(row: pd.Series) -> str:
    degree = str(row.get("swing_degree", ""))
    prior_fit = str(row.get("swing_degree_fit", ""))
    degree_issue = str(row.get("degree_issue", ""))
    review_category = str(row.get("review_category", ""))
    status = str(row.get("manual_visual_status", row.get("visual_review_status", "")))
    if "too_micro" in {prior_fit, status} or "degree_too_micro" in degree_issue:
        return "degree_too_micro"
    if "not_discriminative" in degree_issue and degree == "major":
        return "degree_not_discriminative"
    if "not_discriminative" in degree_issue and degree == "intermediate" and status in {"ambiguous", "plausible_but_needs_review", "should_downgrade"}:
        return "degree_not_discriminative"
    if degree == "minor":
        return "minor_substructure_only"
    if degree == "intermediate":
        return "intermediate_primary_candidate"
    if degree == "major" and review_category in {"impulse", "partial_123", "near_miss"} and status in {
        "excellent_example",
        "visually_defensible",
        "hard_invalid_correct",
    }:
        return "major_operable_higher_degree"
    if degree == "major":
        return "major_context"
    return "degree_too_coarse"


def _initial_status(row: pd.Series) -> tuple[str, int, str, str]:
    category = str(row.get("review_category", ""))
    filename = Path(str(row.get("chart_path", ""))).name
    prior_status = str(row.get("visual_review_status", "")) or "ambiguous"
    prior_score = int(float(row.get("visual_quality_score", 3) or 3))
    prior_notes = str(row.get("visual_notes", ""))
    decision = str(row.get("suggested_action", "keep_as_ambiguous_example"))

    if category == "partial_123" and filename in PARTIAL_VISUAL_REVIEW:
        review = PARTIAL_VISUAL_REVIEW[filename]
        return str(review["status"]), int(review["score"]), str(review["decision"]), str(review["note"])
    if category in {"impulse", "near_miss"} and filename in IMPULSE_VISUAL_REVIEW:
        review = IMPULSE_VISUAL_REVIEW[filename]
        return str(review["status"]), int(review["score"]), str(review["decision"]), str(review["note"])
    if category == "hard_invalid" and filename in INVALIDATION_VISUAL_REVIEW:
        review = INVALIDATION_VISUAL_REVIEW[filename]
        return "hard_invalid_correct", int(review["score"]), "keep_as_negative_example", str(review["note"])
    if category == "abc" and filename in ABC_VISUAL_REVIEW:
        review = ABC_VISUAL_REVIEW[filename]
        score = int(review["score"])
        status = "ambiguous" if score >= 3 else "not_usable_for_methodology"
        return status, score, "exclude_from_phase25_rules", str(review["note"])

    if prior_status == "likely_false_candidate":
        decision = "exclude_from_phase25_rules"
    elif prior_status == "hard_invalid_correct":
        decision = "keep_as_negative_example"
    elif prior_status in {"ambiguous", "plausible_but_needs_review", "visually_forced"}:
        decision = "keep_as_ambiguous_example"
    elif prior_status in {"excellent_example", "visually_defensible"}:
        decision = "keep_as_good_example"

    return prior_status, prior_score, decision, prior_notes


def _apply_user_feedback(row: pd.Series, feedback_by_candidate: dict[str, dict[str, str]]) -> tuple[str, int, str, str]:
    status = str(row["manual_visual_status"])
    score = int(row["visual_quality_score"])
    decision = str(row["final_phase23_decision"])
    note = str(row["visual_closure_notes"])
    feedback = feedback_by_candidate.get(str(row["candidate_id"]), {})
    label = feedback.get("user_label", "")
    if label == "bien":
        if status in {"not_usable_for_methodology", "likely_false_candidate", "should_downgrade"}:
            status = "plausible_but_needs_review"
            decision = "keep_as_ambiguous_example"
            score = max(score, 3)
        note = f"{note} User: bien."
    elif label == "dudoso":
        status = "plausible_but_needs_review"
        decision = "keep_as_ambiguous_example"
        score = min(score, 3)
        note = f"{note} User: dudoso."
    elif label == "mal":
        status = "should_downgrade"
        decision = "exclude_from_phase25_rules"
        score = min(score, 2)
        note = f"{note} User: mal; {feedback.get('user_note', '')}"
    elif label == "hard_invalid_correct":
        status = "hard_invalid_correct"
        decision = "keep_as_negative_example"
        score = max(score, 4)
        note = f"{note} User: correcto como invalido."
    return status, score, decision, note.strip()


def _classify_rows(frame: pd.DataFrame, feedback_mapping: pd.DataFrame) -> pd.DataFrame:
    feedback_phase23 = feedback_mapping[feedback_mapping["used_for_phase23_closure"].astype(str).str.lower() == "true"]
    feedback_by_candidate = {
        str(row["candidate_id"]): row.to_dict()
        for _, row in feedback_phase23.iterrows()
        if str(row.get("user_label", ""))
    }
    rows = []
    for _, source in frame.iterrows():
        row = source.to_dict()
        status, score, decision, note = _initial_status(source)
        filename = Path(str(row.get("chart_path", ""))).name
        row["manual_visual_status"] = status
        row["visual_quality_score"] = score
        row["final_phase23_decision"] = decision
        row["visual_closure_notes"] = note
        row["wave5_diagnostic"] = _text_or(row.get("wave5_endpoint_status"), "not_applicable")
        row["partial123_diagnostic"] = _text_or(row.get("partial123_status"), "not_applicable")
        if filename in IMPULSE_VISUAL_REVIEW:
            row["wave5_diagnostic"] = str(IMPULSE_VISUAL_REVIEW[filename].get("wave5", row["wave5_diagnostic"]))
        row["source_gallery_status"] = "legacy_abc_superseded_by_fix" if row.get("review_category") == "abc" else "phase23_h4_count_only_vigente_with_external_diagnostics"
        if row.get("review_category") == "abc":
            row["wave5_diagnostic"] = "not_applicable"
            row["partial123_diagnostic"] = "not_applicable"
            row["visual_closure_notes"] = f"{row['visual_closure_notes']} ABC se mantiene experimental y debe revisarse desde phase2_abc_fix."
        if row.get("review_category") in {"impulse", "near_miss"} and row["wave5_diagnostic"] in {
            "premature_wave5_completion",
            "truncated_fifth_candidate",
        }:
            if row["final_phase23_decision"] == "keep_as_good_example":
                row["final_phase23_decision"] = "keep_as_ambiguous_example"
            if row["manual_visual_status"] == "excellent_example":
                row["manual_visual_status"] = "visually_defensible"
            row["visual_closure_notes"] = (
                f"{row['visual_closure_notes']} Endpoint onda 5: {row['wave5_diagnostic']}; "
                "se conserva como provisional/ambiguous, no como regla dura."
            )
        partial_has_visual_override = filename in PARTIAL_VISUAL_REVIEW
        if (
            row.get("review_category") == "partial_123"
            and row["partial123_diagnostic"] in {
            "invalidated_after_3",
            "partial_123_too_lax",
            "belongs_to_prior_wave_45",
            }
            and (not partial_has_visual_override or row["final_phase23_decision"] == "exclude_from_phase25_rules")
        ):
            row["final_phase23_decision"] = "exclude_from_phase25_rules"
            if row["manual_visual_status"] not in {"not_usable_for_methodology", "should_downgrade"}:
                row["manual_visual_status"] = "should_downgrade"
                row["visual_quality_score"] = min(int(row["visual_quality_score"]), 2)
        elif (
            row.get("review_category") == "partial_123"
            and partial_has_visual_override
            and row["partial123_diagnostic"] in {"invalidated_after_3", "partial_123_too_lax", "belongs_to_prior_wave_45"}
        ):
            row["visual_closure_notes"] = (
                f"{row['visual_closure_notes']} Diagnostico mecanico {row['partial123_diagnostic']} no se aplica "
                "como downgrade duro porque la revision visual muestra continuidad o estructura defendible."
            )
        if row.get("review_category") == "hard_invalid":
            row["final_phase23_decision"] = "keep_as_negative_example"
            row["manual_visual_status"] = "hard_invalid_correct"
            row["wave5_diagnostic"] = row["wave5_diagnostic"] if row["wave5_diagnostic"] != "not_applicable" else "clean_or_acceptable"
        if row.get("review_category") == "near_miss" and row["final_phase23_decision"] == "keep_as_good_example":
            row["final_phase23_decision"] = "keep_as_ambiguous_example"
        row["degree_policy"] = _degree_policy(pd.Series(row))
        status, score, decision, note = _apply_user_feedback(pd.Series(row), feedback_by_candidate)
        row["manual_visual_status"] = status
        row["visual_quality_score"] = score
        row["final_phase23_decision"] = decision
        row["visual_closure_notes"] = note
        if row["manual_visual_status"] in {"not_usable_for_methodology", "likely_false_candidate", "should_downgrade"}:
            row["final_phase23_decision"] = "exclude_from_phase25_rules"
        rows.append(row)
    result = pd.DataFrame(rows).sort_values("candidate_order").reset_index(drop=True)
    result["requires_user_review"] = False
    result["user_review_reason"] = ""
    return result


def _choose_source_chart(row: pd.Series, phase23_h4_dir: Path, abc_fix_dir: Path) -> Path:
    if str(row.get("review_category", "")) == "abc" and isinstance(row.get("fixed_chart_path_absolute", ""), str):
        fixed = Path(str(row.get("fixed_chart_path_absolute", "")))
        if fixed.exists():
            return fixed
    return phase23_h4_dir / str(row.get("chart_path", ""))


def _annotate_chart(source: Path, output_path: Path, title: str, note: str) -> bool:
    if not source.exists():
        return False
    image = plt.imread(source)
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(image)
    ax.axis("off")
    if len(note) > 210:
        note = note[:207] + "..."
    fig.suptitle(title, fontsize=10.5, fontweight="bold")
    fig.text(0.02, 0.02, note, fontsize=8.5, color="#111827")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=130)
    plt.close(fig)
    return True


def _write_charts(frame: pd.DataFrame, output_dir: Path, phase23_h4_dir: Path, abc_fix_dir: Path) -> pd.DataFrame:
    rows = []
    for _, row in frame.iterrows():
        filename = _safe_name(f"{int(row['candidate_order']):03d}_{row['candidate_id']}.png")
        title = (
            f"{int(row['candidate_order']):03d} | {row['candidate_id']} | {row['manual_visual_status']} | "
            f"{row['final_phase23_decision']}"
        )
        note = (
            f"degree={row['degree_policy']} | wave5={row['wave5_diagnostic']} | "
            f"partial123={row['partial123_diagnostic']} | {row['visual_closure_notes']}"
        )
        source = _choose_source_chart(row, phase23_h4_dir, abc_fix_dir)
        reviewed_path = output_dir / "charts" / "reviewed" / filename
        reviewed_status = "ok" if _annotate_chart(source, reviewed_path, title, note) else "missing_source"
        problem_path = ""
        best_path = ""
        if row["final_phase23_decision"] in {"exclude_from_phase25_rules", "downgrade_from_best_examples", "inspect_user_only_if_needed"}:
            path = output_dir / "charts" / "problem_cases" / filename
            if _annotate_chart(source, path, title, note):
                problem_path = _as_rel(path)
        if row["final_phase23_decision"] in {"keep_as_good_example", "keep_as_negative_example"}:
            path = output_dir / "charts" / "best_final_examples" / filename
            if _annotate_chart(source, path, title, note):
                best_path = _as_rel(path)
        rows.append(
            {
                "candidate_id": row["candidate_id"],
                "candidate_order": row["candidate_order"],
                "reviewed_chart_status": reviewed_status,
                "source_chart_path": str(source),
                "reviewed_chart_path": _as_rel(reviewed_path) if reviewed_status == "ok" else "",
                "problem_chart_path": problem_path,
                "best_chart_path": best_path,
            }
        )
    return pd.DataFrame(rows)


def _write_markdown_index(csv_path: Path, title: str, path_columns: tuple[str, ...]) -> None:
    frame = pd.read_csv(csv_path)
    lines = [
        f"# {title}",
        "",
        f"CSV fuente: [{csv_path.name}]({csv_path.name})",
        "",
        "| fila | candidate_id | decision | imagenes |",
        "|---:|---|---|---|",
    ]
    for idx, row in frame.iterrows():
        links = []
        for column in path_columns:
            value = str(row.get(column, ""))
            if not value or value == "nan":
                continue
            path = Path(value)
            if path.is_absolute():
                try:
                    rel = path.relative_to(csv_path.parent)
                except ValueError:
                    rel = path
            else:
                absolute = REPO_ROOT / value
                try:
                    rel = absolute.relative_to(csv_path.parent)
                except ValueError:
                    rel = Path(value)
            links.append(f"[{column}](<{rel.as_posix()}>)")
        lines.append(
            f"| {idx + 2} | `{row.get('candidate_id', '')}` | `{row.get('final_phase23_decision', row.get('reviewed_chart_status', ''))}` | {' · '.join(links)} |"
        )
    csv_path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _aggregate_tables(closure: pd.DataFrame) -> dict[str, pd.DataFrame]:
    keep = closure[closure["final_phase23_decision"].isin(["keep_as_good_example", "keep_as_negative_example", "keep_as_ambiguous_example"])].copy()
    downgrade = closure[closure["manual_visual_status"].isin(["should_downgrade", "not_usable_for_methodology", "likely_false_candidate"])].copy()
    exclude = closure[closure["final_phase23_decision"] == "exclude_from_phase25_rules"].copy()
    degree_policy = (
        closure.groupby(["review_category", "swing_degree", "degree_policy"], dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(["review_category", "swing_degree", "degree_policy"])
    )
    readiness = pd.DataFrame(
        [
            {
                "scope": "phase2_3_h4_d1_count_only",
                "readiness": "ready_for_phase2_4_review",
                "primary_degree": "intermediate",
                "higher_degree_context": "major",
                "minor_use": "substructure_only",
                "h4_role": "preferred_visual_base",
                "abc_role": "experimental_pending_abc_fix_review",
                "phase25_note": "Do not use ABC or downgraded partials as Phase 2.5 rules; use H4/D1 intermediate plus major context.",
            }
        ]
    )
    user_must_review = closure[closure["requires_user_review"].astype(bool)].copy()
    return {
        "h4_d1_cases_to_keep": keep,
        "h4_d1_cases_to_downgrade": downgrade,
        "h4_d1_cases_to_exclude_from_phase25": exclude,
        "h4_d1_degree_policy": degree_policy,
        "h4_d1_phase25_readiness": readiness,
        "h4_d1_user_must_review_if_any": user_must_review,
    }


def _write_report(output_dir: Path, closure: pd.DataFrame, feedback: pd.DataFrame, elapsed: float) -> None:
    status_counts = closure["manual_visual_status"].value_counts().to_dict()
    decision_counts = closure["final_phase23_decision"].value_counts().to_dict()
    category_counts = closure["review_category"].value_counts().to_dict()
    lines = [
        "# WaveCount Fase 2.3.4 - cierre visual H4/D1",
        "",
        "Fecha: 2026-05-23",
        "",
        "## Objetivo",
        "",
        "Cerrar la revision visual H4/D1 de Fase 2.3 antes de revisar Fase 2.4 con contexto.",
        "No se cambian reglas, umbrales, pivotes, estrategias, ABC base ni senales.",
        "",
        "## Diagnostico",
        "",
        f"- casos H4/D1 revisados: {len(closure)}",
        f"- categorias: {category_counts}",
        f"- estados visuales finales: {status_counts}",
        f"- decisiones finales: {decision_counts}",
        f"- feedback manual mapeado desde best_h4_examples: {len(feedback[feedback['user_label'].astype(str) != ''])}",
        f"- tiempo de ejecucion: {elapsed:.2f}s",
        "",
        "## Decisiones",
        "",
        "- H4/D1 queda como escala visual preferente frente a H1/M30.",
        "- `intermediate` queda como grado primario para conteo H4.",
        "- `major` queda como contexto superior, aunque algunos casos major pueden ser operables como grado superior.",
        "- `minor` queda como subestructura, no como base principal.",
        "- Los hard invalid se conservan como ejemplos negativos correctos.",
        "- ABC no se usa para cerrar Fase 2.3; queda experimental y separado en `phase2_abc_fix_2026-05-20/`.",
        "- Los parciales invalidados tras el 3 o demasiado debiles se excluyen de reglas para Fase 2.5.",
        "",
        "## Cierre",
        "",
        "Fase 2.3 H4/D1 queda defendible como base visual para pasar a Fase 2.4. La siguiente revision debe usar D1/EMAs/EWO solo como contexto, sin rescatar conteos que esta fase haya degradado.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_3_4_H4_D1_VISUAL_CLOSURE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_h4_d1_visual_closure(
    *,
    phase23_h4_dir: Path = DEFAULT_PHASE23_H4_DIR,
    h4_audit_dir: Path = DEFAULT_H4_AUDIT_DIR,
    wave5_dir: Path = DEFAULT_WAVE5_DIR,
    partial123_dir: Path = DEFAULT_PARTIAL123_DIR,
    degree_dir: Path = DEFAULT_DEGREE_DIR,
    abc_fix_dir: Path = DEFAULT_ABC_FIX_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started = datetime.now()
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    candidates = _load_csv(phase23_h4_dir / "tables" / "visual_review_candidates.csv")
    audit = _load_csv(h4_audit_dir / "tables" / "phase2_3_h4_visual_audit.csv")
    best_examples = _load_csv(h4_audit_dir / "tables" / "best_h4_examples.csv")
    wave5 = _load_csv(wave5_dir / "tables" / "wave5_endpoint_diagnostics.csv")
    partials = _load_csv(partial123_dir / "tables" / "partial123_diagnostics.csv")
    degree_issues = _load_csv(degree_dir / "tables" / "degree_discrimination_issues.csv")
    abc_fixed = _load_csv(abc_fix_dir / "tables" / "phase2_3_abc_fixed_candidates.csv")

    feedback = _best_feedback_mapping(best_examples)
    joined = _join_diagnostics(candidates, audit, wave5, partials, degree_issues, abc_fixed, phase23_h4_dir, abc_fix_dir)
    closure = _classify_rows(joined, feedback)
    chart_index = _write_charts(closure, output_dir, phase23_h4_dir, abc_fix_dir)
    closure = closure.merge(chart_index, on=["candidate_id", "candidate_order"], how="left")

    output_tables = {"h4_d1_visual_closure": closure, "h4_d1_user_feedback_mapping": feedback}
    output_tables.update(_aggregate_tables(closure))

    for name, frame in output_tables.items():
        frame.to_csv(tables_dir / f"{name}.csv", index=False)

    _write_markdown_index(
        tables_dir / "h4_d1_visual_closure.csv",
        "WaveCount H4/D1 Fase 2.3.4 - cierre visual",
        ("reviewed_chart_path", "problem_chart_path", "best_chart_path"),
    )
    _write_markdown_index(
        tables_dir / "h4_d1_cases_to_keep.csv",
        "WaveCount H4/D1 Fase 2.3.4 - casos a conservar",
        ("reviewed_chart_path", "best_chart_path"),
    )
    _write_markdown_index(
        tables_dir / "h4_d1_cases_to_downgrade.csv",
        "WaveCount H4/D1 Fase 2.3.4 - casos degradados",
        ("reviewed_chart_path", "problem_chart_path"),
    )
    _write_markdown_index(
        tables_dir / "h4_d1_cases_to_exclude_from_phase25.csv",
        "WaveCount H4/D1 Fase 2.3.4 - excluir de reglas Fase 2.5",
        ("reviewed_chart_path", "problem_chart_path"),
    )

    elapsed = perf_counter() - start
    _write_report(output_dir, closure, feedback, elapsed)
    meta = {
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "output_dir": str(output_dir.resolve()),
        "inputs": {
            "phase23_h4_dir": str(phase23_h4_dir.resolve()),
            "h4_audit_dir": str(h4_audit_dir.resolve()),
            "wave5_dir": str(wave5_dir.resolve()),
            "partial123_dir": str(partial123_dir.resolve()),
            "degree_dir": str(degree_dir.resolve()),
            "abc_fix_dir": str(abc_fix_dir.resolve()),
        },
        "rows": {name: int(len(frame)) for name, frame in output_tables.items()},
        "notes": [
            "Audit/closure only; no strategy, threshold, pivot, count, ABC or signal rules changed.",
            "Phase 2.3 H4/D1 is closed as visual base for Phase 2.4 review.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount H4/D1 Phase 2.3.4 visual closure artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_h4_d1_visual_closure(output_dir=args.output_dir)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
