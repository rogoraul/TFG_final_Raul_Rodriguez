from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from backtests.wavecount.wavecount_context_gallery import build_context_gallery
from backtests.wavecount.wavecount_h4_d1_gallery import H4_D1_VISUAL_REVIEW_SPECS
from backtests.wavecount.wavecount_visual_review_gallery import VisualReviewSpec, build_visual_review_gallery


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE251_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_1_guided_impulse_profile_2026-05-24"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_2_guided_impulse_expansion_2026-05-24"
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


def _boolish(value: Any) -> bool:
    return _string(value).strip().lower() in {"true", "1", "yes", "y", "si"}


def _rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _resolve_repo_path(value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    return REPO_ROOT / raw


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        bits = [
            _string(row.get("candidate_id")),
            _string(row.get("matches_guided_impulse_profile")),
            _string(row.get("visual_expansion_status")),
            _string(row.get("phase253_candidate_action")),
        ]
        lines.append(f"## {idx + 1}. {' | '.join(bit for bit in bits if bit) or 'fila'}")
        for column in (
            "guided_profile_reasons",
            "guided_profile_failures",
            "visual_notes",
            "phase253_reason",
        ):
            value = _string(row.get(column))
            if value:
                lines.extend(["", value])
        for column in row.index:
            if "path" not in column.lower():
                continue
            value = _string(row.get(column))
            if value.lower().endswith(".png"):
                path = _resolve_repo_path(value)
                lines.extend(["", f"![{path.name}]({path.resolve().as_posix()})"])
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    return {str(k): int(v) for k, v in frame[column].fillna("missing").value_counts().to_dict().items()}


def _expanded_specs(rows: int) -> tuple[VisualReviewSpec, ...]:
    return tuple(
        VisualReviewSpec(
            f"exp252_{spec.example_id}",
            spec.group,
            spec.symbol,
            spec.timeframe,
            rows,
        )
        for spec in H4_D1_VISUAL_REVIEW_SPECS
    )


def _profile_match_expanded(row: pd.Series) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    failures: list[str] = []
    critical: list[str] = []

    def add(condition: bool, points: int, reason: str, failure: str, *, critical_failure: bool = False) -> None:
        nonlocal score
        if condition:
            score += points
            reasons.append(reason)
        else:
            failures.append(failure)
            if critical_failure:
                critical.append(failure)

    category = _string(row.get("review_category"))
    timeframe = _string(row.get("timeframe")).upper()
    degree = _string(row.get("swing_degree"))
    trend = _string(row.get("trend_context_label"))
    context_score = _number(row.get("context_score"))
    htf_safe = _boolish(row.get("htf_lookahead_safe"))
    htf_match = _boolish(row.get("htf_direction_match"))
    htf_conflict = _boolish(row.get("htf_direction_conflict")) or trend == "conflict_with_htf"
    ltf_match = _boolish(row.get("ltf_direction_match"))
    momentum_match = _boolish(row.get("momentum_matches_direction"))
    inside_band = _string(row.get("end_ltf_price_vs_ema_band")) == "inside_band"
    transition_match = _boolish(row.get("transition_matches_direction"))

    add(category == "impulse", 24, "structure=impulse", f"not impulse ({category})", critical_failure=True)
    add(timeframe == "H4", 14, "timeframe=H4", f"timeframe={timeframe or 'missing'}")
    add(degree == "intermediate", 18, "degree=intermediate", f"degree={degree or 'missing'}")
    add(htf_safe, 10, "HTF lookahead safe", "HTF lookahead unsafe", critical_failure=True)
    add(context_score >= 60, 10, f"context_score={context_score}", f"context_score={context_score}")
    add(not htf_conflict, 8, f"HTF not suspicious ({trend})", f"HTF conflict ({trend})")
    add(htf_match or trend in {"impulse_with_htf", "correction_against_htf"}, 6, "HTF/context interpretable", "HTF/context unclear")
    add(ltf_match, 5, "LTF EMA direction supports count", "LTF EMA direction does not support count")
    add(momentum_match, 7, "EWO/momentum supports count direction", "EWO/momentum does not support count direction")
    add(not inside_band, 3, "price outside EMA band", "price inside EMA band adds ambiguity")
    if transition_match:
        score += 3
        reasons.append("transition supports candidate direction")

    score = min(100, score)
    if category in {"hard_invalid", "abc", "partial_123"}:
        critical.append(f"{category} not part of impulse expansion profile")

    if critical:
        match = "no"
    elif score >= 85 and category == "impulse" and timeframe == "H4" and degree == "intermediate" and not htf_conflict:
        match = "yes"
    elif score >= 55 and category == "impulse" and timeframe == "H4":
        match = "near_miss"
    else:
        match = "no"

    return {
        "matches_guided_impulse_profile": match,
        "guided_profile_match_score": score,
        "guided_profile_reasons": "; ".join(reasons),
        "guided_profile_failures": "; ".join(failures),
        "guided_profile_critical_failures": "; ".join(dict.fromkeys(critical)),
    }


def _near_miss_reason(row: pd.Series) -> str:
    if _string(row.get("matches_guided_impulse_profile")) != "near_miss":
        return ""
    degree = _string(row.get("swing_degree"))
    trend = _string(row.get("trend_context_label"))
    if degree == "minor":
        return "minor_substructure"
    if degree == "major":
        return "higher_degree_context"
    if _boolish(row.get("htf_direction_conflict")) or trend == "conflict_with_htf":
        return "context_conflict"
    if not _boolish(row.get("momentum_matches_direction")):
        return "ewo_not_clear"
    if _string(row.get("end_ltf_price_vs_ema_band")) == "inside_band":
        return "ema_band_ambiguity"
    return "soft_rule_gap"


def _ewo_helpfulness(row: pd.Series) -> str:
    if _string(row.get("review_category")) != "impulse":
        return "unclear"
    direction = _string(row.get("end_ltf_ewo_5_35_direction"))
    if _boolish(row.get("momentum_matches_direction")):
        return "supports_wave_role"
    if direction in {"positive", "negative"}:
        return "supports_momentum_only"
    if direction == "flat_or_unknown":
        return "unclear"
    return "misleading"


def _ema_htf_helpfulness(row: pd.Series) -> str:
    trend = _string(row.get("trend_context_label"))
    if _boolish(row.get("htf_direction_match")) and _boolish(row.get("ltf_direction_match")):
        return "supports_context"
    if "transition" in trend or _boolish(row.get("transition_matches_direction")):
        return "explains_transition"
    if trend == "correction_against_htf":
        return "explains_correction"
    if trend == "conflict_with_htf" or _boolish(row.get("htf_direction_conflict")):
        return "misleading"
    return "neutral"


def _visual_review_status(row: pd.Series) -> dict[str, Any]:
    match = _string(row.get("matches_guided_impulse_profile"))
    near_reason = _string(row.get("near_miss_reason"))
    category = _string(row.get("review_category"))
    context_score = _number(row.get("context_score"))
    ewo = _ewo_helpfulness(row)
    ema_htf = _ema_htf_helpfulness(row)

    if match == "yes" and context_score >= 75 and ewo == "supports_wave_role":
        status = "strong_match"
        quality = 5
        decision = "keep_profile"
    elif match == "yes":
        status = "acceptable_match"
        quality = 4
        decision = "keep_but_mark_provisional"
    elif match == "near_miss" and near_reason in {"minor_substructure", "higher_degree_context", "soft_rule_gap"}:
        status = "near_miss_useful"
        quality = 3
        decision = "keep_but_mark_provisional"
    elif match == "near_miss" and near_reason in {"context_conflict", "ewo_not_clear", "ema_band_ambiguity"}:
        status = "false_positive_risk" if near_reason == "context_conflict" else "near_miss_too_weak"
        quality = 2
        decision = "downgrade_to_near_miss"
    elif category == "hard_invalid":
        status = "good_negative_example"
        quality = 4
        decision = "exclude"
    elif category in {"partial_123", "abc"}:
        status = "not_usable"
        quality = 2
        decision = "exclude"
    elif match == "no":
        status = "not_usable"
        quality = 2
        decision = "exclude"
    else:
        status = "context_misleading"
        quality = 2
        decision = "needs_rule_review"

    if ema_htf == "misleading" and match in {"yes", "near_miss"}:
        status = "context_misleading" if match == "yes" else status
        quality = min(quality, 2)
        decision = "needs_rule_review" if match == "yes" else decision

    return {
        "visual_expansion_status": status,
        "visual_quality_score": quality,
        "ewo_helpfulness": ewo,
        "ema_htf_helpfulness": ema_htf,
        "profile_decision_after_visual_review": decision,
        "visual_notes": _visual_notes(row, status, ewo, ema_htf),
    }


def _visual_notes(row: pd.Series, status: str, ewo: str, ema_htf: str) -> str:
    bits = [
        f"profile={_string(row.get('matches_guided_impulse_profile'))}",
        f"near_miss={_string(row.get('near_miss_reason')) or 'none'}",
        f"context={_string(row.get('trend_context_label'))}",
        f"EWO={ewo}",
        f"EMA/HTF={ema_htf}",
        f"status={status}",
    ]
    return "; ".join(bits)


def _phase253_action(row: pd.Series) -> dict[str, str]:
    match = _string(row.get("matches_guided_impulse_profile"))
    visual = _string(row.get("visual_expansion_status"))
    if match == "yes" and visual in {"strong_match", "acceptable_match"}:
        return {
            "phase253_candidate_action": "expand_h4_d1_search",
            "phase253_reason": "Profile match remains coherent in expanded H4/D1 sample.",
        }
    if match == "near_miss":
        return {
            "phase253_candidate_action": "manual_review_before_expansion",
            "phase253_reason": f"Near-miss retained for visual/manual review ({_string(row.get('near_miss_reason'))}).",
        }
    if visual == "good_negative_example":
        return {
            "phase253_candidate_action": "use_as_negative_example",
            "phase253_reason": "Clear negative helps test that profile does not rescue bad counts.",
        }
    return {
        "phase253_candidate_action": "exclude_from_expansion",
        "phase253_reason": "Outside the base guided impulse profile.",
    }


def _copy_chart(row: pd.Series, source_context_dir: Path, output_dir: Path) -> str:
    category = _string(row.get("matches_guided_impulse_profile"))
    visual = _string(row.get("visual_expansion_status"))
    if category == "yes":
        folder = "matches"
    elif category == "near_miss":
        folder = "near_misses"
    elif visual in {"context_misleading", "false_positive_risk"}:
        folder = "context_misleading"
    else:
        folder = "negatives"

    source_value = _string(row.get("source_context_chart_path"))
    source = _resolve_repo_path(source_value) if source_value else Path()
    if not source.exists():
        return ""
    filename = f"{int(row.get('candidate_order', 0)):03d}_{_string(row.get('candidate_id'))}.png".replace(":", "-")
    destination = output_dir / "charts" / folder / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return _rel_to_repo(destination)


def _write_contact_sheet(frame: pd.DataFrame, output_path: Path, *, title_column: str = "candidate_id") -> None:
    if frame.empty or "reviewed_chart_path" not in frame.columns:
        return
    rows = frame[frame["reviewed_chart_path"].astype(str).str.endswith(".png", na=False)].head(24).copy()
    if rows.empty:
        return

    thumb_w = 520
    thumb_h = 300
    label_h = 56
    pad = 16
    cols = 2
    sheet_rows = (len(rows) + cols - 1) // cols
    sheet = Image.new(
        "RGB",
        (cols * thumb_w + (cols + 1) * pad, sheet_rows * (thumb_h + label_h) + (sheet_rows + 1) * pad),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        small = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    for idx, (_, row) in enumerate(rows.iterrows()):
        col = idx % cols
        rr = idx // cols
        x = pad + col * (thumb_w + pad)
        y = pad + rr * (thumb_h + label_h + pad)
        path = _resolve_repo_path(_string(row.get("reviewed_chart_path")))
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
        draw.text((x, y), _string(row.get(title_column))[:78], fill=(20, 20, 20), font=font)
        subtitle = (
            f"{_string(row.get('matches_guided_impulse_profile'))} | "
            f"{_string(row.get('visual_expansion_status'))} | "
            f"{_string(row.get('near_miss_reason'))}"
        )
        draw.text((x, y + 24), subtitle[:90], fill=(80, 80, 80), font=small)
        bx = x + (thumb_w - image.width) // 2
        by = y + label_h + (thumb_h - image.height) // 2
        sheet.paste(image, (bx, by))
        draw.rectangle((x, y + label_h, x + thumb_w, y + label_h + thumb_h), outline=(210, 210, 210), width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def _summarise_reviews(frame: pd.DataFrame, output_dir: Path) -> dict[str, pd.DataFrame]:
    matches = frame[frame["matches_guided_impulse_profile"].eq("yes")].copy()
    near_misses = frame[frame["matches_guided_impulse_profile"].eq("near_miss")].copy()
    negatives = frame[frame["matches_guided_impulse_profile"].eq("no")].copy()
    false_risks = frame[
        frame["visual_expansion_status"].isin(["false_positive_risk", "context_misleading"])
        | frame["near_miss_reason"].eq("context_conflict")
    ].copy()

    ewo_review = (
        frame.groupby(["ewo_helpfulness", "matches_guided_impulse_profile"], dropna=False)
        .size()
        .reset_index(name="case_count")
    )
    ema_review = (
        frame.groupby(["ema_htf_helpfulness", "matches_guided_impulse_profile"], dropna=False)
        .size()
        .reset_index(name="case_count")
    )
    rule_candidates = pd.DataFrame(
        [
            {
                "rule_candidate": "h4_d1_intermediate_required",
                "policy": "keep_as_soft_gate",
                "evidence": "Matches concentrate on H4/D1 intermediate; other degrees are near-miss/context.",
                "must_not_be_hard_signal": True,
            },
            {
                "rule_candidate": "ewo_supports_but_does_not_label",
                "policy": "soft_context",
                "evidence": "EWO is useful when it supports role/momentum, but unclear/misleading cases remain.",
                "must_not_be_hard_signal": True,
            },
            {
                "rule_candidate": "ema_htf_context_cannot_rescue",
                "policy": "soft_context",
                "evidence": "Context conflicts are kept as near-miss or risk, not as strong matches.",
                "must_not_be_hard_signal": True,
            },
            {
                "rule_candidate": "inside_ema_band_ambiguity_penalty",
                "policy": "soft_penalty",
                "evidence": "Inside EMA band should increase ambiguity, not invalidate automatically.",
                "must_not_be_hard_signal": True,
            },
        ]
    )
    phase253 = pd.DataFrame(
        [
            {
                "recommendation": "controlled_h4_d1_expansion_can_continue",
                "status": "conditional_yes",
                "reason": "Use matches as seeds and near-misses/negatives as validation gallery; do not generate signals.",
                "next_phase": "phase2_5_3_descriptive_offline_statistics",
            },
            {
                "recommendation": "keep_ewo_as_soft_context",
                "status": "yes",
                "reason": "EWO helps interpret momentum/role but should not label waves alone.",
                "next_phase": "optional_feature_analysis_or_future_svm",
            },
            {
                "recommendation": "keep_ema_htf_as_soft_context",
                "status": "yes",
                "reason": "HTF/EMA alignment helps, but conflicts can be transition/lag and must not be hard filters.",
                "next_phase": "phase2_5_3_context_stability",
            },
        ]
    )
    user_review = pd.concat(
        [
            matches,
            near_misses[near_misses["near_miss_reason"].isin(["context_conflict", "ewo_not_clear", "ema_band_ambiguity"])],
            false_risks,
        ],
        ignore_index=True,
    ).drop_duplicates("candidate_id")

    return {
        "guided_impulse_expanded_matches": matches,
        "guided_impulse_expanded_near_misses": near_misses,
        "guided_impulse_expanded_negatives": negatives,
        "visual_expansion_review": frame,
        "ewo_expansion_review": ewo_review,
        "ema_htf_expansion_review": ema_review,
        "profile_false_positive_risks": false_risks,
        "profile_rule_candidates": rule_candidates,
        "phase253_recommendation": phase253,
        "user_must_review_if_any": user_review,
    }


def _write_report(output_dir: Path, run_meta: dict[str, Any]) -> None:
    lines = [
        "# WaveCount Fase 2.5.2 - Expansion controlada del impulso guiado",
        "",
        "## Resumen",
        "",
        "Esta fase amplia de forma acotada la muestra H4/D1 para comprobar si el perfil 2.5.1 aguanta fuera de sus tres seeds.",
        "",
        "No genera senales, no ejecuta backtests, no cambia estrategias y no modifica los conteos/artifacts previos.",
        "",
        "## Alcance",
        "",
        f"- expansion: `{run_meta['expansion_scope']}`",
        f"- simbolos: {run_meta['symbols']}",
        f"- filas H4 por simbolo: {run_meta['ltf_rows_per_symbol']}",
        f"- filas D1 para contexto: {run_meta['htf_rows']}",
        "",
        "## Resultado",
        "",
    ]
    for key, value in run_meta["match_counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "Near-misses:", ""])
    for key, value in run_meta["near_miss_reason_counts"].items():
        if key:
            lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Lectura",
            "",
            "El perfil se mantiene como filtro metodologico conservador: los matches fuertes son pocos, los near-misses quedan separados por grado/contexto/EWO/EMA y los negativos no se rescatan.",
            "",
            "EWO 5-35 ayuda como lectura de momentum/rol de onda, pero no etiqueta ondas por si solo. EMAs 50/150 y D1/HTF ayudan como contexto de regimen/transicion, pero no deben invalidar ni rescatar automaticamente.",
            "",
            "## Cierre",
            "",
            "Fase 2.5.3 puede plantearse como expansion historica/descriptiva offline si se mantiene esta separacion entre estructura visual, contexto blando y no-senal.",
            "",
            "## Run meta",
            "",
            "```json",
            json.dumps(run_meta, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_5_2_GUIDED_IMPULSE_EXPANSION.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def build_guided_impulse_expansion(
    *,
    phase251_dir: Path = DEFAULT_PHASE251_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    ltf_rows: int = 900,
    htf_rows: int = 520,
) -> dict[str, Any]:
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    specs = _expanded_specs(ltf_rows)
    phase23_dir = output_dir / "diagnostic_phase2_3_h4_d1_expanded"
    phase24_dir = output_dir / "diagnostic_phase2_4_h4_d1_expanded"

    phase23_meta = build_visual_review_gallery(output_dir=phase23_dir, specs=specs)
    phase24_meta = build_context_gallery(input_dir=phase23_dir, output_dir=phase24_dir, htf_rows=htf_rows, specs=specs)

    candidates = _read_csv(phase24_dir / "tables" / "candidate_context.csv")
    if candidates.empty:
        raise RuntimeError("expanded candidate_context.csv is empty")

    candidates = candidates.copy()
    original_chart_path = candidates["chart_path"].copy() if "chart_path" in candidates.columns else pd.Series([""] * len(candidates))
    original_context_chart_path = (
        candidates["context_chart_path"].copy()
        if "context_chart_path" in candidates.columns
        else pd.Series([""] * len(candidates))
    )
    candidates["source_count_chart_path"] = original_chart_path.apply(
        lambda value: _rel_to_repo(phase23_dir / _string(value)) if _string(value) else ""
    )
    candidates["source_context_chart_path"] = original_context_chart_path.apply(
        lambda value: _rel_to_repo(phase24_dir / _string(value)) if _string(value) else ""
    )
    candidates["chart_path"] = candidates["source_context_chart_path"]
    candidates["context_chart_path"] = candidates["source_context_chart_path"]
    profile = candidates.apply(_profile_match_expanded, axis=1, result_type="expand")
    candidates = pd.concat([candidates, profile], axis=1)
    candidates["near_miss_reason"] = candidates.apply(_near_miss_reason, axis=1)
    visual = candidates.apply(_visual_review_status, axis=1, result_type="expand")
    candidates = pd.concat([candidates, visual], axis=1)
    actions = candidates.apply(_phase253_action, axis=1, result_type="expand")
    candidates = pd.concat([candidates, actions], axis=1)
    candidates["should_enter_visual_gallery"] = candidates["matches_guided_impulse_profile"].isin(["yes", "near_miss"]) | candidates[
        "review_category"
    ].isin(["hard_invalid"])

    candidates["reviewed_chart_path"] = candidates.apply(lambda row: _copy_chart(row, phase24_dir, output_dir), axis=1)

    scope = pd.DataFrame(
        [
            {
                "expansion_scope": "controlled_h4_d1_windows",
                "symbols": "|".join(spec.symbol for spec in specs),
                "timeframe": "H4",
                "htf_timeframe": "D1",
                "ltf_rows_per_symbol": ltf_rows,
                "htf_rows": htf_rows,
                "source": "existing SQL OHLCV via WaveCount gallery helpers",
                "rules_changed": False,
                "signals_generated": False,
                "notes": "Controlled diagnostic regeneration in a new artifact folder; prior artifacts are not overwritten.",
            }
        ]
    )

    tables: dict[str, pd.DataFrame] = {"expansion_scope": scope, "guided_impulse_expanded_candidates": candidates}
    tables.update(_summarise_reviews(candidates, output_dir))

    for name, frame in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    _write_contact_sheet(tables["guided_impulse_expanded_matches"], output_dir / "charts" / "matches_contact_sheet.png")
    _write_contact_sheet(tables["guided_impulse_expanded_near_misses"], output_dir / "charts" / "near_misses_contact_sheet.png")
    _write_contact_sheet(tables["guided_impulse_expanded_negatives"], output_dir / "charts" / "negatives_contact_sheet.png")
    _write_contact_sheet(tables["profile_false_positive_risks"], output_dir / "charts" / "context_misleading_contact_sheet.png")

    image_refs = [
        _string(value)
        for frame in tables.values()
        if "reviewed_chart_path" in frame.columns
        for value in frame["reviewed_chart_path"].dropna().tolist()
        if _string(value).endswith(".png")
    ]
    missing = sorted({path for path in image_refs if not _resolve_repo_path(path).exists()})

    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "phase251_dir": _rel_to_repo(phase251_dir),
        "expansion_scope": "controlled_h4_d1_windows",
        "symbols": [spec.symbol for spec in specs],
        "ltf_rows_per_symbol": ltf_rows,
        "htf_rows": htf_rows,
        "phase23_meta": {
            "charts_ok": len([row for row in phase23_meta.get("charts", []) if row.get("status") == "ok"]),
            "output_dir": _rel_to_repo(phase23_dir),
        },
        "phase24_meta": {
            "charts_ok": len([row for row in phase24_meta.get("charts", []) if row.get("status") == "ok"]),
            "output_dir": _rel_to_repo(phase24_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "match_counts": _counts(candidates, "matches_guided_impulse_profile"),
        "near_miss_reason_counts": _counts(candidates, "near_miss_reason"),
        "visual_status_counts": _counts(candidates, "visual_expansion_status"),
        "ewo_helpfulness_counts": _counts(candidates, "ewo_helpfulness"),
        "ema_htf_helpfulness_counts": _counts(candidates, "ema_htf_helpfulness"),
        "missing_image_refs": missing,
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_previous_artifacts_modified": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, run_meta)
    return run_meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.2 guided impulse expansion.")
    parser.add_argument("--phase251-dir", type=Path, default=DEFAULT_PHASE251_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ltf-rows", type=int, default=900)
    parser.add_argument("--htf-rows", type=int, default=520)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_meta = build_guided_impulse_expansion(
        phase251_dir=args.phase251_dir,
        output_dir=args.output_dir,
        ltf_rows=args.ltf_rows,
        htf_rows=args.htf_rows,
    )
    print(json.dumps(run_meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
