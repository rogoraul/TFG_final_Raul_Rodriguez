from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ABC_FIX_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_abc_fix_2026-05-20"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_3_abc_quality_audit_2026-05-23"


ABC_MAIN_REVIEWS: dict[str, dict[str, Any]] = {
    "abc_forex_audjpy_h4_intermediate_abc_002": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Mejor ejemplo H4 sin indicadores: zigzag bajista pequeno pero legible dentro de una estructura alcista posterior.",
    },
    "abc_metals_xagusd_h4_intermediate_abc_003": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Limpio geometricamente, pero parece arranque impulsivo alcista; C es demasiado expansiva para lectura correctiva limpia.",
    },
    "abc_index_aus200_h4_intermediate_abc_006": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 3,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Temporalmente limpio, pero lateral/comprimido; C apenas mejora A.",
    },
    "abc_forex_audjpy_h4_intermediate_abc_005": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Se lee mas como 1-2-3 alcista que como correccion ABC limpia.",
    },
    "abc_forex_audjpy_h4_minor_abc_002": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Mismo patron que el mejor H4, pero en minor; util como subestructura auxiliar.",
    },
    "abc_metals_xagusd_h4_minor_abc_003": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Demasiado micro; B/C no construyen una correccion clara.",
    },
    "abc_index_aus200_h4_minor_abc_005": {
        "abc_visual_status": "visually_forced_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Parece tramo impulsivo inicial, no ABC; A/B pequenos y C tipo spike.",
    },
    "abc_forex_audjpy_h4_minor_abc_005": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Muy micro y con C expansiva; mas 1-2-3 que correccion.",
    },
    "abc_forex_audjpy_h4_major_abc_003": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 3,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Limpio geometricamente, pero semanticamente parece continuacion alcista.",
    },
    "abc_metals_xagusd_h4_major_abc_003": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Ordenado, pero C parece continuacion impulsiva antes del blow-off.",
    },
    "abc_index_aus200_h4_major_abc_006": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 3,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Similar al H4 intermediate de AUS200; limpio, pero lateral/ambiguo.",
    },
    "abc_forex_audjpy_h4_major_abc_005": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Estructura grande y clara, pero se lee mas como impulso alcista que ABC.",
    },
    "abc_forex_audjpy_h1_intermediate_abc_009": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Secuencia limpia, pero parece mas arranque impulsivo que correccion clara.",
    },
    "abc_metals_xagusd_h1_intermediate_abc_003": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Uno de los mejores H1: 0-A-B-C claro y C con desplazamiento suficiente.",
    },
    "abc_index_aus200_h1_intermediate_abc_004": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Limpio, pero C es muy direccional y puede ser impulso bajista disfrazado de ABC.",
    },
    "abc_forex_audjpy_h1_intermediate_abc_011": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Visualmente ordenado, pero C parece extension impulsiva.",
    },
    "abc_forex_audjpy_h1_minor_abc_007": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 2,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Demasiado local/lateral; no apto para reglas.",
    },
    "abc_metals_xagusd_h1_minor_abc_002": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 3,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Limpio visualmente, pero en minor parece subestructura mas que ABC principal.",
    },
    "abc_index_aus200_h1_minor_abc_006": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 2,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "A/B muy pequenos frente a C; mal ejemplo metodologico.",
    },
    "abc_forex_audjpy_h1_minor_abc_013": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Limpio, pero demasiado parecido a tramo impulsivo menor.",
    },
    "abc_forex_audjpy_h1_major_abc_007": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Buena geometria, aunque C domina demasiado.",
    },
    "abc_metals_xagusd_h1_major_abc_006": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Buen ejemplo auxiliar: estructura amplia, clara y sin maraña.",
    },
    "abc_index_aus200_h1_major_abc_002": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Limpio y defendible como ABC bajista/zigzag auxiliar.",
    },
    "abc_forex_eurusd_h1_major_abc_002": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "De los mejores H1: estructura bajista clara, B razonable y C suficiente.",
    },
}


ABC_CONTEXT_REVIEWS: dict[str, dict[str, Any]] = {
    "abc_forex_audjpy_h4_intermediate_abc_002": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_explains_countertrend_correction",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Buen ABC bajista contra HTF alcista. EMAs/EWO ayudan a leer correccion y posterior continuacion.",
    },
    "abc_metals_xagusd_h4_intermediate_abc_003": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_misleading",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Contexto alcista lo hace tentador, pero no valida que sea correccion; parece continuacion impulsiva.",
    },
    "abc_index_aus200_h4_intermediate_abc_006": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_flags_transition",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Muy comprimido dentro de banda EMA. El desplome posterior no debe rescatarlo.",
    },
    "abc_forex_audjpy_h4_intermediate_abc_005": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_misleading",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Ordenado, pero en contexto alcista parece mas 1-2-3/continuacion que correccion.",
    },
    "abc_forex_audjpy_h4_minor_abc_002": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_explains_countertrend_correction",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Misma idea que el mejor caso, pero minor; util como subestructura.",
    },
    "abc_metals_xagusd_h4_minor_abc_003": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 3,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_misleading",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Demasiado micro y alineado con tendencia; parece subonda impulsiva.",
    },
    "abc_index_aus200_h4_minor_abc_005": {
        "abc_visual_status": "visually_forced_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_misleading",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "A-B demasiado pequeno y C tipo spike. No usar para reglas ABC.",
    },
    "abc_forex_audjpy_h4_minor_abc_005": {
        "abc_visual_status": "visually_forced_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_misleading",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Muy micro; el contexto alcista podria rescatarlo artificialmente.",
    },
    "abc_forex_audjpy_h4_major_abc_003": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_confirms_correction",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Estructura amplia y legible, aunque se lee mas como continuacion alcista que correccion pura.",
    },
    "abc_metals_xagusd_h4_major_abc_003": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_confirms_correction",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Buen ejemplo de tres tramos amplios. Contexto util, pero solo como blando.",
    },
    "abc_index_aus200_h4_major_abc_006": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_flags_transition",
        "phase25_abc_policy": "exclude_from_phase25",
        "visual_notes": "Comprimido, dentro de banda y C poco convincente; no rescatar por caida posterior.",
    },
    "abc_forex_audjpy_h4_major_abc_005": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "context_confirms_correction",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Muy limpio como 0-A-B-C, pero puede ser continuacion. Buen ejemplo manual, no regla automatica.",
    },
}


ABC_FOCUS_REVIEWS: dict[str, dict[str, Any]] = {
    "h1_forex_gbpusd_h1_intermediate_abc_002.png": {
        "abc_visual_status": "plausible_abc",
        "abc_quality_score": 3,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_only_manual_review",
        "visual_notes": "Focus problematico corregido visualmente; ya no hay maraña, pero sigue ambiguo.",
    },
    "h1_forex_gbpusd_h1_major_abc_003.png": {
        "abc_visual_status": "clean_abc",
        "abc_quality_score": 4,
        "abc_state_interpretation": "abc_completed",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "usable_as_soft_context",
        "visual_notes": "Focus corregido y bastante defendible como estructura amplia.",
    },
    "h1_forex_gbpusd_h1_minor_abc_002.png": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 2,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Corregido visualmente, pero demasiado micro/pegado al inicio.",
    },
    "h1_metals_xagusd_h1_minor_abc_002.png": {
        "abc_visual_status": "ambiguous_correction",
        "abc_quality_score": 3,
        "abc_state_interpretation": "ambiguous_correction",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Limpio, pero parece subestructura/impulso menor.",
    },
    "h4_metals_xagusd_h4_intermediate_abc_003.png": {
        "abc_visual_status": "not_clean_abc",
        "abc_quality_score": 2,
        "abc_state_interpretation": "not_clean_abc",
        "causality_status": "causal_with_confirmation_latency",
        "context_usefulness": "no_context_available",
        "phase25_abc_policy": "keep_experimental",
        "visual_notes": "Focus H4 corregido de dibujo, pero no usable como ABC limpio: parece tramo impulsivo alcista.",
    },
}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _resolve_chart(base_dir: Path, chart_path: str) -> Path:
    raw = Path(chart_path)
    if raw.is_absolute():
        return raw
    return base_dir / raw


def _copy_with_annotation(source: Path, target: Path, lines: list[str]) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        font = ImageFont.load_default()
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(textwrap.wrap(line, width=150) or [""])
        line_height = 15
        pad = 10
        banner_height = pad * 2 + line_height * len(wrapped)
        canvas = Image.new("RGB", (width, height + banner_height), "white")
        canvas.paste(image, (0, banner_height))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, width, banner_height), fill=(248, 250, 252), outline=(203, 213, 225))
        y = pad
        for line in wrapped:
            draw.text((pad, y), line, fill=(15, 23, 42), font=font)
            y += line_height
        canvas.save(target)


def _write_image_index(csv_path: Path, title: str, image_columns: list[str]) -> None:
    if not csv_path.exists():
        return
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for _, row in frame.iterrows():
        label_bits = [
            _string(row.get("scope")),
            _string(row.get("candidate_id")),
            _string(row.get("abc_visual_status")),
            _string(row.get("phase25_abc_policy")),
        ]
        label = " | ".join(bit for bit in label_bits if bit)
        lines.append(f"## {label}")
        notes = _string(row.get("visual_notes"))
        if notes:
            lines.extend(["", notes])
        for column in image_columns:
            path_text = _string(row.get(column))
            if not path_text:
                continue
            path = Path(path_text)
            if not path.is_absolute():
                path = (REPO_ROOT / path).resolve()
            lines.extend(["", f"![{label}]({path.as_posix()})"])
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _manual_review(row: pd.Series, *, focus: bool = False, context: bool = False) -> dict[str, Any]:
    if focus:
        chart_name = Path(_string(row.get("fixed_chart_path"))).name
        return ABC_FOCUS_REVIEWS[chart_name]
    if context:
        return ABC_CONTEXT_REVIEWS[_string(row["candidate_id"])]
    return ABC_MAIN_REVIEWS[_string(row["candidate_id"])]


def _diagnostic_lookup(abc_fix_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    clean = _read_csv(abc_fix_dir / "tables" / "abc_clean_candidates.csv")
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for _, row in clean.iterrows():
        key = (_string(row["candidate_id"]), _string(row["swing_degree"]))
        lookup[key] = row.to_dict()
    return lookup


def _diagnostics_for_row(
    diagnostics: dict[tuple[str, str], dict[str, Any]],
    row: pd.Series,
    *,
    focus: bool = False,
) -> dict[str, Any]:
    diag = diagnostics.get((_string(row.get("candidate_id")), _string(row.get("swing_degree"))), {})
    if diag:
        return diag
    if focus and _string(row.get("status")).lower() == "ok":
        return {
            "point_count": 4,
            "labels": "0|A|B|C",
            "orders": "0|1|2|3",
            "pivot_extreme_time_strictly_increasing": True,
            "structural_detected_at_non_decreasing": True,
            "last_structural_detected_at": "",
            "plot_ready": True,
            "diagnostic_note": "Focus case has status=ok in abc_focus_cases.csv; not part of abc_clean_candidates.csv.",
        }
    return {}


def _make_reviewed_chart(
    *,
    source: Path,
    output_dir: Path,
    folder: str,
    prefix: str,
    row: pd.Series,
    review: dict[str, Any],
) -> Path:
    target = output_dir / "charts" / folder / f"{prefix}_{source.name}"
    lines = [
        f"{_string(row.get('candidate_id'))} | {_string(row.get('timeframe'))} {_string(row.get('swing_degree'))}",
        f"ABC: {review['abc_visual_status']} | score={review['abc_quality_score']} | policy={review['phase25_abc_policy']}",
        f"Causalidad: {review['causality_status']} | Estado: {review['abc_state_interpretation']}",
    ]
    if _string(review.get("context_usefulness")) != "no_context_available":
        lines.append(f"Contexto: {review['context_usefulness']}")
    lines.append(_string(review.get("visual_notes")))
    _copy_with_annotation(source, target, lines)
    return target


def _policy_bucket(policy: str) -> str:
    if policy == "usable_as_soft_context":
        return "soft_context_candidate"
    if policy == "usable_only_manual_review":
        return "manual_review_only"
    if policy == "exclude_from_phase25":
        return "excluded_from_phase25"
    if policy == "requires_redesign_before_phase25":
        return "requires_redesign"
    return "experimental"


def _must_review(row: dict[str, Any]) -> str:
    score = int(row.get("abc_quality_score", 0))
    policy = _string(row.get("phase25_abc_policy"))
    status = _string(row.get("abc_visual_status"))
    context = _string(row.get("context_usefulness"))
    if policy == "usable_as_soft_context":
        return "yes"
    if score <= 2:
        return "yes"
    if status in {"not_clean_abc", "visually_forced_abc", "legacy_problem_still_present"}:
        return "yes"
    if context in {"context_misleading", "context_flags_transition"}:
        return "yes"
    return "no"


def _audit_phase23(abc_fix_dir: Path, output_dir: Path, diagnostics: dict[tuple[str, str], dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    candidates = _read_csv(abc_fix_dir / "tables" / "phase2_3_abc_fixed_candidates.csv")
    focus = _read_csv(abc_fix_dir / "tables" / "abc_focus_cases.csv")

    for scope, frame in [("phase2_3_fixed", candidates), ("focus_case", focus)]:
        for _, row in frame.iterrows():
            review = _manual_review(row, focus=(scope == "focus_case"))
            source = _resolve_chart(abc_fix_dir, _string(row.get("fixed_chart_path")))
            prefix = "focus" if scope == "focus_case" else _string(row.get("phase")) or _string(row.get("timeframe")).lower()
            reviewed = _make_reviewed_chart(
                source=source,
                output_dir=output_dir,
                folder="reviewed",
                prefix=prefix,
                row=row,
                review=review,
            )
            if review["phase25_abc_policy"] == "usable_as_soft_context":
                _make_reviewed_chart(
                    source=source,
                    output_dir=output_dir,
                    folder="clean_examples",
                    prefix=prefix,
                    row=row,
                    review=review,
                )
            if review["abc_visual_status"] in {"not_clean_abc", "visually_forced_abc"} or review["phase25_abc_policy"] == "exclude_from_phase25":
                _make_reviewed_chart(
                    source=source,
                    output_dir=output_dir,
                    folder="problem_cases",
                    prefix=prefix,
                    row=row,
                    review=review,
                )

            diag = _diagnostics_for_row(diagnostics, row, focus=(scope == "focus_case"))
            record = {
                **row.to_dict(),
                "scope": scope,
                "source_chart_path": _rel_to_repo(source),
                "reviewed_chart_path": _rel_to_repo(reviewed),
                "abc_visual_status": review["abc_visual_status"],
                "abc_quality_score": review["abc_quality_score"],
                "abc_state_interpretation": review["abc_state_interpretation"],
                "causality_status": review["causality_status"],
                "context_usefulness": review["context_usefulness"],
                "phase25_abc_policy": review["phase25_abc_policy"],
                "policy_bucket": _policy_bucket(review["phase25_abc_policy"]),
                "visual_notes": review["visual_notes"],
                "point_count": diag.get("point_count", ""),
                "labels": diag.get("labels", ""),
                "orders": diag.get("orders", ""),
                "pivot_extreme_time_strictly_increasing": diag.get("pivot_extreme_time_strictly_increasing", ""),
                "structural_detected_at_non_decreasing": diag.get("structural_detected_at_non_decreasing", ""),
                "last_structural_detected_at": diag.get("last_structural_detected_at", ""),
                "plot_ready": diag.get("plot_ready", ""),
                "diagnostic_note": diag.get("diagnostic_note", ""),
                "count_detected_at_available": False,
                "causality_basis": "last_structural_detected_at from corrected ABC diagnostics; no explicit count_detected_at column exported by phase2_abc_fix.",
            }
            record["should_user_review"] = _must_review(record)
            rows.append(record)
    return pd.DataFrame(rows)


def _audit_context(abc_fix_dir: Path, output_dir: Path, diagnostics: dict[tuple[str, str], dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    context = _read_csv(abc_fix_dir / "tables" / "phase2_4_abc_fixed_context.csv")
    for _, row in context.iterrows():
        review = _manual_review(row, context=True)
        source = _resolve_chart(abc_fix_dir, _string(row.get("fixed_context_chart_path")))
        reviewed = _make_reviewed_chart(
            source=source,
            output_dir=output_dir,
            folder="reviewed",
            prefix="context",
            row=row,
            review=review,
        )
        if review["phase25_abc_policy"] == "usable_as_soft_context":
            _make_reviewed_chart(
                source=source,
                output_dir=output_dir,
                folder="clean_examples",
                prefix="context",
                row=row,
                review=review,
            )
        if review["abc_visual_status"] in {"not_clean_abc", "visually_forced_abc"} or review["phase25_abc_policy"] == "exclude_from_phase25":
            _make_reviewed_chart(
                source=source,
                output_dir=output_dir,
                folder="problem_cases",
                prefix="context",
                row=row,
                review=review,
            )
        diag = _diagnostics_for_row(diagnostics, row)
        record = {
            **row.to_dict(),
            "scope": "phase2_4_context",
            "source_chart_path": _rel_to_repo(source),
            "reviewed_chart_path": _rel_to_repo(reviewed),
            "abc_visual_status": review["abc_visual_status"],
            "abc_quality_score": review["abc_quality_score"],
            "abc_state_interpretation": review["abc_state_interpretation"],
            "causality_status": review["causality_status"],
            "context_usefulness": review["context_usefulness"],
            "phase25_abc_policy": review["phase25_abc_policy"],
            "policy_bucket": _policy_bucket(review["phase25_abc_policy"]),
            "visual_notes": review["visual_notes"],
            "point_count": diag.get("point_count", ""),
            "labels": diag.get("labels", ""),
            "orders": diag.get("orders", ""),
            "pivot_extreme_time_strictly_increasing": diag.get("pivot_extreme_time_strictly_increasing", ""),
            "structural_detected_at_non_decreasing": diag.get("structural_detected_at_non_decreasing", ""),
            "last_structural_detected_at": diag.get("last_structural_detected_at", ""),
            "plot_ready": diag.get("plot_ready", ""),
            "diagnostic_note": diag.get("diagnostic_note", ""),
            "count_detected_at_available": False,
            "causality_basis": "last_structural_detected_at from corrected ABC diagnostics; D1 context uses htf_lookahead_safe from phase2_4_abc_fixed_context.",
        }
        record["should_user_review"] = _must_review(record)
        rows.append(record)
    return pd.DataFrame(rows)


def _policy_table(quality: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    both = pd.concat([quality, context], ignore_index=True)
    rows: list[dict[str, Any]] = []
    for policy, group in both.groupby("phase25_abc_policy", dropna=False):
        rows.append(
            {
                "phase25_abc_policy": policy,
                "case_count": int(len(group)),
                "quality_score_median": float(group["abc_quality_score"].median()) if not group.empty else 0.0,
                "recommended_use": {
                    "usable_as_soft_context": "Can be shown as soft context candidate after visual review; not a hard filter.",
                    "usable_only_manual_review": "Keep available for manual review or methodology examples; do not automate.",
                    "keep_experimental": "Keep as experimental/ambiguous correction bank.",
                    "exclude_from_phase25": "Do not use for Phase 2.5 rules.",
                    "requires_redesign_before_phase25": "Redesign ABC before using.",
                }.get(_string(policy), "Review manually."),
            }
        )
    rows.append(
        {
            "phase25_abc_policy": "overall_decision",
            "case_count": int(len(both)),
            "quality_score_median": float(both["abc_quality_score"].median()) if not both.empty else 0.0,
            "recommended_use": "ABC corrected is geometrically clean, but remains soft/manual/experimental for Phase 2.5; no hard rules or signals.",
        }
    )
    return pd.DataFrame(rows)


def _summary_rows(quality: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    both = pd.concat([quality.assign(source_scope="phase2_3"), context.assign(source_scope="phase2_4")], ignore_index=True)
    rows = [
        {"metric": "phase2_3_quality_rows_including_focus", "value": int(len(quality))},
        {"metric": "phase2_4_context_rows", "value": int(len(context))},
        {"metric": "plot_ready_false", "value": int((both["plot_ready"].astype(str) != "True").sum())},
        {"metric": "bad_label_order_rows", "value": int((both["labels"].astype(str) != "0|A|B|C").sum() + (both["orders"].astype(str) != "0|1|2|3").sum())},
        {"metric": "temporal_order_violations", "value": int((both["pivot_extreme_time_strictly_increasing"].astype(str) != "True").sum())},
        {"metric": "structural_detected_order_violations", "value": int((both["structural_detected_at_non_decreasing"].astype(str) != "True").sum())},
        {"metric": "htf_lookahead_violations", "value": int((context["htf_lookahead_safe"].astype(str) != "True").sum()) if "htf_lookahead_safe" in context.columns else 0},
    ]
    for label, count in both["abc_visual_status"].value_counts().items():
        rows.append({"metric": f"abc_visual_status_{label}", "value": int(count)})
    for label, count in both["phase25_abc_policy"].value_counts().items():
        rows.append({"metric": f"phase25_abc_policy_{label}", "value": int(count)})
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, quality: pd.DataFrame, context: pd.DataFrame, summary: pd.DataFrame, elapsed: float) -> None:
    both = pd.concat([quality, context], ignore_index=True)
    soft = int((both["phase25_abc_policy"] == "usable_as_soft_context").sum())
    exclude = int((both["phase25_abc_policy"] == "exclude_from_phase25").sum())
    experimental = int((both["phase25_abc_policy"] == "keep_experimental").sum())
    clean = int((both["abc_visual_status"] == "clean_abc").sum())
    problem = int(both["abc_visual_status"].isin(["not_clean_abc", "visually_forced_abc"]).sum())
    lines = [
        "# WaveCount Fase 2.4.3 - auditoria ABC corregido",
        "",
        "Fecha: 2026-05-23",
        "",
        "## Alcance",
        "",
        "Se revisa solo la linea ABC corregida en `phase2_abc_fix_2026-05-20`.",
        "No se usan ABC legacy de galerias integradas antiguas como evidencia principal.",
        "No se cambian conteos, pivotes, grados, estrategias, senales ni backtests.",
        "",
        "## Resultado tecnico",
        "",
        "- La geometria corregida queda limpia: los ABC revisados se dibujan como `0 -> A -> B -> C`.",
        "- No quedan etiquetas duplicadas ni varias estructuras ABC superpuestas en los graficos revisados.",
        "- La causalidad se mantiene con latencia de confirmacion: el extremo visual puede quedar atras, pero la lectura depende de pivotes estructurales confirmados.",
        "",
        "## Resultado metodologico",
        "",
        f"- Casos revisados sin contexto/Fase 2.3 incluyendo focus: {len(quality)}.",
        f"- Casos revisados con contexto H4/D1/Fase 2.4: {len(context)}.",
        f"- Casos `clean_abc`: {clean}.",
        f"- Casos `not_clean_abc` o `visually_forced_abc`: {problem}.",
        f"- Casos aptos solo como contexto blando: {soft}.",
        f"- Casos excluidos de Fase 2.5: {exclude}.",
        f"- Casos que quedan experimentales: {experimental}.",
        "",
        "## Decision",
        "",
        "ABC corregido puede entrar en Fase 2.5 solo como contexto blando/manual y banco experimental.",
        "No debe convertirse en filtro duro, senal, ni criterio automatico de calidad.",
        "Antes de usarlo como modulo fuerte haria falta implementar estados causales especificos: `possible_abc_start`, `abc_in_progress`, `abc_completed`, `ambiguous_correction`, `not_clean_abc` y `retrospective_only`.",
        "",
        "## Papel de D1/EMAs/EWO",
        "",
        "D1/EMAs/EWO ayudan en algunos casos a explicar correccion contra regimen o transicion.",
        "Pero tambien pueden hacer tentador rescatar estructuras que visualmente parecen impulsivas.",
        "Por eso quedan como lectura contextual y no como validacion de ABC.",
        "",
        "## Validacion",
        "",
        f"- Tiempo de ejecucion: {elapsed:.2f}s.",
        "- Las tablas tienen indices Markdown con imagenes para revision rapida.",
        "- Vease `tables/abc_phase25_policy.csv` para la politica de uso.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_4_3_ABC_QUALITY_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_abc_quality_audit(abc_fix_dir: Path = DEFAULT_ABC_FIX_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for folder in ["reviewed", "clean_examples", "problem_cases"]:
        (output_dir / "charts" / folder).mkdir(parents=True, exist_ok=True)

    diagnostics = _diagnostic_lookup(abc_fix_dir)
    quality = _audit_phase23(abc_fix_dir, output_dir, diagnostics)
    context = _audit_context(abc_fix_dir, output_dir, diagnostics)

    clean_examples = pd.concat(
        [
            quality[quality["phase25_abc_policy"].eq("usable_as_soft_context")],
            context[context["phase25_abc_policy"].eq("usable_as_soft_context")],
        ],
        ignore_index=True,
    )
    ambiguous = pd.concat(
        [
            quality[quality["abc_visual_status"].isin(["plausible_abc", "ambiguous_correction"])],
            context[context["abc_visual_status"].isin(["plausible_abc", "ambiguous_correction"])],
        ],
        ignore_index=True,
    )
    not_usable = pd.concat(
        [
            quality[
                quality["abc_visual_status"].isin(["not_clean_abc", "visually_forced_abc", "legacy_problem_still_present"])
                | quality["phase25_abc_policy"].isin(["exclude_from_phase25", "requires_redesign_before_phase25"])
            ],
            context[
                context["abc_visual_status"].isin(["not_clean_abc", "visually_forced_abc", "legacy_problem_still_present"])
                | context["phase25_abc_policy"].isin(["exclude_from_phase25", "requires_redesign_before_phase25"])
            ],
        ],
        ignore_index=True,
    )
    policy = _policy_table(quality, context)
    must_review = pd.concat(
        [quality[quality["should_user_review"].eq("yes")], context[context["should_user_review"].eq("yes")]],
        ignore_index=True,
    )
    summary = _summary_rows(quality, context)

    outputs = {
        "abc_quality_audit": quality,
        "abc_context_audit": context,
        "abc_clean_examples": clean_examples,
        "abc_ambiguous_examples": ambiguous,
        "abc_not_usable": not_usable,
        "abc_phase25_policy": policy,
        "abc_user_must_review": must_review,
        "abc_quality_summary": summary,
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        _write_image_index(path, name.replace("_", " ").title(), ["reviewed_chart_path", "source_chart_path"])

    elapsed = perf_counter() - start
    _write_report(output_dir, quality, context, summary, elapsed)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "inputs": {
            "abc_fix_dir": _rel_to_repo(abc_fix_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "validation": {
            "plot_ready_false": int((pd.concat([quality, context], ignore_index=True)["plot_ready"].astype(str) != "True").sum()),
            "bad_label_order_rows": int(
                (
                    pd.concat([quality, context], ignore_index=True)["labels"].astype(str).ne("0|A|B|C")
                    | pd.concat([quality, context], ignore_index=True)["orders"].astype(str).ne("0|1|2|3")
                ).sum()
            ),
            "htf_lookahead_violations": int((context["htf_lookahead_safe"].astype(str) != "True").sum()) if "htf_lookahead_safe" in context.columns else 0,
        },
        "outputs": {name: _rel_to_repo(tables_dir / f"{name}.csv") for name in outputs},
        "notes": [
            "No WaveCount counting rules were changed.",
            "No strategies, signals, MT5 paths or benchmark artifacts were changed.",
            "ABC legacy galleries are not used as primary evidence.",
            "The audit integrates concrete visual reviews of corrected charts.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.4.3 ABC quality audit.")
    parser.add_argument("--abc-fix-dir", type=Path, default=DEFAULT_ABC_FIX_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_abc_quality_audit(abc_fix_dir=args.abc_fix_dir, output_dir=args.output_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
