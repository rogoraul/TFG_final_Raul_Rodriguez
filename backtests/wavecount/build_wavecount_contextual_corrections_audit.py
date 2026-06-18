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
DEFAULT_ABC_AUDIT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_3_abc_quality_audit_2026-05-23"
DEFAULT_H4_CLOSURE_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_4_h4_d1_visual_closure_2026-05-23"
DEFAULT_CONTEXT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_2_context_quality_audit_2026-05-23"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_4_contextual_corrections_2026-05-24"


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _bool_string(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return _string(value)


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
            wrapped.extend(textwrap.wrap(line, width=155) or [""])
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
            _string(row.get("candidate_id")),
            _string(row.get("correction_role")),
            _string(row.get("contextual_policy")),
        ]
        label = " | ".join(bit for bit in label_bits if bit)
        lines.append(f"## {label}")
        notes = _string(row.get("notes"))
        if notes:
            lines.extend(["", notes])
        for column in image_columns:
            value = _string(row.get(column))
            if not value:
                continue
            path = _resolve_repo_path(value)
            lines.extend(["", f"![{label}]({path.resolve().as_posix()})"])
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _minutes_for_timeframe(timeframe: str) -> int:
    return {"M30": 30, "H1": 60, "H4": 240, "D1": 1440}.get(timeframe.upper(), 60)


def _normalise_times(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for col in ("start_time", "end_time"):
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
    return frame


def _parent_pool(h4_closure: pd.DataFrame, aux_context: pd.DataFrame) -> pd.DataFrame:
    keep_cols = [
        "candidate_id",
        "review_category",
        "symbol",
        "timeframe",
        "swing_degree",
        "direction",
        "start_time",
        "end_time",
        "visual_quality_score",
        "manual_visual_status",
        "visual_review_status",
        "final_phase23_decision",
        "context_review_status",
        "quality_filter_candidate",
        "phase25_rule_candidate",
        "degree_policy",
        "reviewed_chart_path",
    ]
    h4 = h4_closure[h4_closure["review_category"].isin(["impulse", "partial_123"])].copy()
    aux = aux_context[aux_context["review_category"].isin(["impulse", "partial_123"])].copy()
    for col in keep_cols:
        if col not in h4.columns:
            h4[col] = ""
        if col not in aux.columns:
            aux[col] = ""
    h4["parent_source"] = "h4_d1_visual_closure"
    aux["parent_source"] = "aux_context_quality"
    return pd.concat([h4[keep_cols + ["parent_source"]], aux[keep_cols + ["parent_source"]]], ignore_index=True)


def _find_parent(row: pd.Series, pool: pd.DataFrame) -> dict[str, Any]:
    start = pd.to_datetime(row.get("start_time"), errors="coerce")
    symbol = _string(row.get("symbol"))
    timeframe = _string(row.get("timeframe"))
    if pd.isna(start):
        return {"parent_context_status": "no_clear_parent", "parent_candidate_id": ""}

    candidates = pool[
        (pool["symbol"].astype(str) == symbol)
        & (pool["timeframe"].astype(str) == timeframe)
        & (pool["end_time"].notna())
        & (pool["end_time"] <= start)
    ].copy()
    if candidates.empty:
        return {"parent_context_status": "no_clear_parent", "parent_candidate_id": ""}

    candidates["gap_minutes"] = (start - candidates["end_time"]).dt.total_seconds() / 60.0
    candidates = candidates.sort_values(["end_time", "visual_quality_score"], ascending=[False, False])
    parent = candidates.iloc[0].to_dict()
    tf_minutes = _minutes_for_timeframe(timeframe)
    gap_bars = float(parent.get("gap_minutes", 0.0)) / tf_minutes if tf_minutes else 0.0
    parent["gap_bars"] = gap_bars
    parent["parent_context_status"] = "direct_parent_candidate" if gap_bars <= 3 else "distant_parent_candidate"
    return parent


def _context_lookup(context: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {str(row["candidate_id"]): row.to_dict() for _, row in context.iterrows()}


def _direction_vs_parent(abc_direction: str, parent_direction: str) -> str:
    if not abc_direction or not parent_direction:
        return "unknown_parent_direction"
    if abc_direction == parent_direction:
        return "with_parent"
    if {abc_direction, parent_direction} == {"bullish", "bearish"}:
        return "counter_parent"
    return "unknown_parent_direction"


def _htf_direction_from_context(context_row: dict[str, Any]) -> str:
    trend = _string(context_row.get("htf_trend_state")).lower()
    if "bullish" in trend:
        return "bullish"
    if "bearish" in trend:
        return "bearish"
    trend_label = _string(context_row.get("trend_context_label")).lower()
    if trend_label == "correction_against_htf":
        direction = _string(context_row.get("direction"))
        return "bearish" if direction == "bullish" else "bullish" if direction == "bearish" else ""
    if trend_label == "impulse_with_htf":
        return _string(context_row.get("direction"))
    return ""


def _parent_context(row: pd.Series, parent: dict[str, Any], context_row: dict[str, Any]) -> dict[str, Any]:
    abc_direction = _string(row.get("direction"))
    if parent.get("parent_context_status") in {"direct_parent_candidate", "distant_parent_candidate"}:
        parent_direction = _string(parent.get("direction"))
        return {
            "parent_context_status": parent["parent_context_status"],
            "parent_candidate_id": _string(parent.get("candidate_id")),
            "parent_wave_context": "prior_partial_123" if _string(parent.get("review_category")) == "partial_123" else "prior_full_impulse",
            "parent_direction": parent_direction,
            "parent_gap_bars": round(float(parent.get("gap_bars", 0.0)), 2),
            "abc_vs_parent_direction": _direction_vs_parent(abc_direction, parent_direction),
            "parent_notes": f"Parent from {_string(parent.get('parent_source'))}; category={_string(parent.get('review_category'))}; decision={_string(parent.get('final_phase23_decision')) or _string(parent.get('quality_filter_candidate'))}.",
        }

    htf_direction = _htf_direction_from_context(context_row)
    if htf_direction:
        return {
            "parent_context_status": "htf_regime_context_only",
            "parent_candidate_id": "",
            "parent_wave_context": "htf_regime_context",
            "parent_direction": htf_direction,
            "parent_gap_bars": "",
            "abc_vs_parent_direction": _direction_vs_parent(abc_direction, htf_direction),
            "parent_notes": f"Uses HTF regime only; trend_context_label={_string(context_row.get('trend_context_label'))}; htf_trend_state={_string(context_row.get('htf_trend_state'))}.",
        }

    return {
        "parent_context_status": "no_clear_parent",
        "parent_candidate_id": "",
        "parent_wave_context": "unknown_parent_context",
        "parent_direction": "",
        "parent_gap_bars": "",
        "abc_vs_parent_direction": "unknown_parent_direction",
        "parent_notes": "No same-symbol/timeframe prior impulse/partial and no usable HTF direction.",
    }


def _correction_role(row: pd.Series, parent_ctx: dict[str, Any]) -> str:
    visual = _string(row.get("abc_visual_status"))
    previous_policy = _string(row.get("phase25_abc_policy"))
    trend_label = _string(row.get("trend_context_label")).lower()
    vs_parent = parent_ctx["abc_vs_parent_direction"]
    parent_wave = parent_ctx["parent_wave_context"]

    if previous_policy == "exclude_from_phase25" or visual in {"not_clean_abc", "visually_forced_abc"}:
        if vs_parent == "counter_parent" and trend_label == "correction_against_htf":
            return "ambiguous_correction"
        return "not_a_correction_impulsive_sequence"
    if vs_parent == "with_parent":
        return "not_a_correction_impulsive_sequence"
    if vs_parent == "counter_parent":
        if parent_wave == "prior_partial_123":
            return "possible_wave4_correction"
        if parent_wave == "prior_full_impulse":
            return "possible_post_wave5_correction"
        if parent_wave == "htf_regime_context":
            return "standalone_countertrend_correction"
    if trend_label == "correction_against_htf" and visual in {"clean_abc", "plausible_abc"}:
        return "standalone_countertrend_correction"
    if previous_policy == "usable_as_soft_context" and parent_ctx["parent_context_status"] == "no_clear_parent":
        return "unknown_correction_role"
    return "unknown_correction_role"


def _correction_type(row: pd.Series, role: str, parent_ctx: dict[str, Any]) -> str:
    visual = _string(row.get("abc_visual_status"))
    notes = (_string(row.get("visual_notes")) + " " + _string(row.get("context_reason"))).lower()
    band = _string(row.get("end_ltf_price_vs_ema_band")).lower()
    if role == "not_a_correction_impulsive_sequence":
        return "not_a_correction"
    if visual in {"not_clean_abc", "visually_forced_abc"}:
        return "not_a_correction"
    if "lateral" in notes or "comprim" in notes or "inside_band" in band:
        return "flat_like" if role != "unknown_correction_role" else "ambiguous_correction"
    if role in {"possible_wave2_correction", "possible_wave4_correction", "possible_post_wave5_correction", "standalone_countertrend_correction"}:
        if visual in {"clean_abc", "plausible_abc"}:
            return "zigzag_like"
        return "ambiguous_correction"
    if visual == "ambiguous_correction":
        return "ambiguous_correction"
    return "not_classified"


def _alternation(role: str, parent_ctx: dict[str, Any]) -> tuple[str, str]:
    if role == "possible_wave4_correction":
        return (
            "unknown",
            "Possible wave-4 context, but current artifacts do not expose a comparable confirmed wave-2 correction for alternation.",
        )
    if role in {"possible_wave2_correction", "possible_post_wave5_correction"}:
        return ("not_applicable", "Alternation is only meaningful between wave 2 and wave 4.")
    return ("not_applicable", "No comparable wave-2/wave-4 pair in this contextual audit.")


def _contextual_policy(row: pd.Series, role: str, ctype: str, parent_ctx: dict[str, Any]) -> tuple[str, str, str]:
    previous = _string(row.get("phase25_abc_policy"))
    visual = _string(row.get("abc_visual_status"))
    score = int(row.get("abc_quality_score", 0))

    if role == "not_a_correction_impulsive_sequence" or ctype == "not_a_correction" or previous == "exclude_from_phase25":
        return ("exclude_not_correction", "no", "rejected")
    if parent_ctx["parent_context_status"] == "no_clear_parent":
        if previous == "usable_as_soft_context" and visual == "clean_abc":
            return ("manual_contextual_review_only", "no", "medium")
        return ("experimental_unknown_parent", "no", "weak")
    if role in {"possible_wave4_correction", "possible_post_wave5_correction", "standalone_countertrend_correction"}:
        if score >= 4 and previous == "usable_as_soft_context":
            return ("usable_contextual_correction", "yes", "strong")
        return ("manual_contextual_review_only", "no", "medium")
    if role == "ambiguous_correction":
        return ("manual_contextual_review_only", "no", "weak")
    return ("experimental_unknown_parent", "no", "weak")


def _make_reviewed_chart(row: dict[str, Any], output_dir: Path) -> str:
    source_value = _string(row.get("reviewed_chart_path")) or _string(row.get("source_chart_path"))
    source = _resolve_repo_path(source_value)
    prefix = _string(row.get("contextual_policy"))
    target = output_dir / "charts" / "reviewed" / f"{prefix}_{source.name}"
    lines = [
        f"{row['candidate_id']} | {row['timeframe']} {row['swing_degree']} | {row['correction_role']}",
        f"Parent: {row['parent_context_status']} | ABC vs parent: {row['abc_vs_parent_direction']} | type={row['correction_type_simple']}",
        f"Policy: {row['contextual_policy']} | quality={row['contextual_correction_quality']} | alternation={row['alternation_quality']}",
        row["notes"],
    ]
    _copy_with_annotation(source, target, lines)
    return _rel_to_repo(target)


def _copy_category_chart(row: dict[str, Any], output_dir: Path, folder: str) -> None:
    source = _resolve_repo_path(_string(row.get("reviewed_chart_path")))
    if not source.exists():
        return
    target = output_dir / "charts" / folder / source.name
    _copy_with_annotation(
        source,
        target,
        [
            f"{row['candidate_id']} | {row['correction_role']} | {row['contextual_policy']}",
            f"Parent={row['parent_context_status']} | vs_parent={row['abc_vs_parent_direction']}",
            row["notes"],
        ],
    )


def _build_contextual_rows(
    abc_quality: pd.DataFrame,
    abc_context: pd.DataFrame,
    parents: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    context_by_candidate = _context_lookup(abc_context)
    rows: list[dict[str, Any]] = []
    for _, row in _normalise_times(abc_quality).iterrows():
        candidate_id = _string(row.get("candidate_id"))
        context_row = context_by_candidate.get(candidate_id, {})
        parent = _find_parent(row, parents)
        parent_ctx = _parent_context(row, parent, context_row)
        merged = {**row.to_dict(), **{f"context_{k}": v for k, v in context_row.items()}}
        if context_row:
            for key in [
                "trend_context_label",
                "context_score",
                "context_reason",
                "htf_timeframe",
                "htf_trend_state",
                "htf_ema_alignment",
                "htf_price_vs_ema_band",
                "htf_lookahead_safe",
                "end_ltf_price_vs_ema_band",
            ]:
                merged[key] = context_row.get(key, merged.get(key, ""))
        role = _correction_role(pd.Series(merged), parent_ctx)
        ctype = _correction_type(pd.Series(merged), role, parent_ctx)
        alternation_quality, alternation_notes = _alternation(role, parent_ctx)
        policy, enter_phase25, contextual_quality = _contextual_policy(pd.Series(merged), role, ctype, parent_ctx)
        notes = (
            f"Previous={_string(row.get('phase25_abc_policy'))}; visual={_string(row.get('abc_visual_status'))}; "
            f"{parent_ctx['parent_notes']} Role is hypothesis, not signal."
        )
        record = {
            "candidate_id": candidate_id,
            "symbol": _string(row.get("symbol")),
            "timeframe": _string(row.get("timeframe")),
            "swing_degree": _string(row.get("swing_degree")),
            "abc_visual_status": _string(row.get("abc_visual_status")),
            "abc_quality_score": row.get("abc_quality_score", ""),
            "phase25_abc_policy_previous": _string(row.get("phase25_abc_policy")),
            "scope": _string(row.get("scope")),
            "parent_context_status": parent_ctx["parent_context_status"],
            "parent_candidate_id": parent_ctx["parent_candidate_id"],
            "parent_wave_context": parent_ctx["parent_wave_context"],
            "parent_direction": parent_ctx["parent_direction"],
            "parent_gap_bars": parent_ctx["parent_gap_bars"],
            "abc_direction": _string(row.get("direction")),
            "abc_vs_parent_direction": parent_ctx["abc_vs_parent_direction"],
            "correction_role": role,
            "correction_type_simple": ctype,
            "alternation_quality": alternation_quality,
            "alternation_notes": alternation_notes,
            "contextual_correction_quality": contextual_quality,
            "contextual_policy": policy,
            "should_enter_phase25_as_context": enter_phase25,
            "should_user_review": "yes" if policy in {"usable_contextual_correction", "manual_contextual_review_only", "exclude_not_correction"} else "no",
            "trend_context_label": _string(context_row.get("trend_context_label")),
            "context_score": context_row.get("context_score", ""),
            "htf_timeframe": _string(context_row.get("htf_timeframe")),
            "htf_trend_state": _string(context_row.get("htf_trend_state")),
            "htf_lookahead_safe": _bool_string(context_row.get("htf_lookahead_safe")) if context_row else "",
            "notes": notes,
            "source_chart_path": _string(row.get("source_chart_path")),
            "previous_reviewed_chart_path": _string(row.get("reviewed_chart_path")),
        }
        record["reviewed_chart_path"] = _make_reviewed_chart(record, output_dir)
        rows.append(record)

    frame = pd.DataFrame(rows)
    for _, r in frame.iterrows():
        row_dict = r.to_dict()
        if row_dict["contextual_policy"] == "usable_contextual_correction":
            _copy_category_chart(row_dict, output_dir, "good_contextual_corrections")
        if row_dict["contextual_policy"] in {"exclude_not_correction", "requires_correction_model_redesign"}:
            _copy_category_chart(row_dict, output_dir, "problematic_corrections")
    return frame


def _summary_rows(audit: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"metric": "contextual_corrections_rows", "value": int(len(audit))},
        {"metric": "usable_contextual_correction", "value": int((audit["contextual_policy"] == "usable_contextual_correction").sum())},
        {"metric": "manual_contextual_review_only", "value": int((audit["contextual_policy"] == "manual_contextual_review_only").sum())},
        {"metric": "experimental_unknown_parent", "value": int((audit["contextual_policy"] == "experimental_unknown_parent").sum())},
        {"metric": "exclude_not_correction", "value": int((audit["contextual_policy"] == "exclude_not_correction").sum())},
        {"metric": "direct_parent_candidate", "value": int((audit["parent_context_status"] == "direct_parent_candidate").sum())},
        {"metric": "distant_parent_candidate", "value": int((audit["parent_context_status"] == "distant_parent_candidate").sum())},
        {"metric": "htf_regime_context_only", "value": int((audit["parent_context_status"] == "htf_regime_context_only").sum())},
        {"metric": "no_clear_parent", "value": int((audit["parent_context_status"] == "no_clear_parent").sum())},
    ]
    for label, count in audit["correction_role"].value_counts().items():
        rows.append({"metric": f"correction_role_{label}", "value": int(count)})
    for label, count in audit["correction_type_simple"].value_counts().items():
        rows.append({"metric": f"correction_type_{label}", "value": int(count)})
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, audit: pd.DataFrame, summary: pd.DataFrame, elapsed: float) -> None:
    usable = int((audit["contextual_policy"] == "usable_contextual_correction").sum())
    manual = int((audit["contextual_policy"] == "manual_contextual_review_only").sum())
    unknown = int((audit["contextual_policy"] == "experimental_unknown_parent").sum())
    excluded = int((audit["contextual_policy"] == "exclude_not_correction").sum())
    lines = [
        "# WaveCount Fase 2.4.4 - correcciones contextuales",
        "",
        "Fecha: 2026-05-24",
        "",
        "## Alcance",
        "",
        "Se auditan los ABC corregidos como correcciones contextuales.",
        "No se cambian conteos, pivotes, grados, estrategias, senales ni backtests.",
        "",
        "## Resultado",
        "",
        f"- ABC revisados: {len(audit)}.",
        f"- Correcciones contextuales usables como contexto blando: {usable}.",
        f"- Solo revision manual contextual: {manual}.",
        f"- Experimentales por padre desconocido: {unknown}.",
        f"- Excluidos por no comportarse como correccion: {excluded}.",
        "",
        "## Decision metodologica",
        "",
        "ABC ya no se evalua aislado. Un `0-A-B-C` limpio solo puede mejorar su estado si existe padre razonable o contexto HTF que explique que corrige.",
        "La alternancia se registra como nota blanda y queda `unknown` o `not_applicable` cuando no hay una pareja onda 2/onda 4 comparable.",
        "Esta fase no implementa una taxonomia completa de zigzags, flats, triangulos o combinaciones.",
        "",
        "## Lectura para Fase 2.5",
        "",
        "Fase 2.5 puede consumir solo los casos `usable_contextual_correction` como contexto blando.",
        "Los casos `manual_contextual_review_only` y `experimental_unknown_parent` no deben automatizarse.",
        "Los casos `exclude_not_correction` no deben alimentar reglas.",
        "",
        "## Validacion",
        "",
        f"- Tiempo de ejecucion: {elapsed:.2f}s.",
        "- Las tablas tienen indices Markdown para abrir imagenes rapidamente.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_4_4_CONTEXTUAL_CORRECTIONS_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_contextual_corrections_audit(
    abc_audit_dir: Path = DEFAULT_ABC_AUDIT_DIR,
    h4_closure_dir: Path = DEFAULT_H4_CLOSURE_DIR,
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for folder in ["reviewed", "good_contextual_corrections", "problematic_corrections"]:
        (output_dir / "charts" / folder).mkdir(parents=True, exist_ok=True)

    abc_quality = _normalise_times(_read_csv(abc_audit_dir / "tables" / "abc_quality_audit.csv"))
    abc_context = _normalise_times(_read_csv(abc_audit_dir / "tables" / "abc_context_audit.csv"))
    h4_closure = _normalise_times(_read_csv(h4_closure_dir / "tables" / "h4_d1_visual_closure.csv"))
    aux_context = _normalise_times(_read_csv(context_dir / "tables" / "h1_h4_m30_h1_aux_context_audit.csv"))
    parents = _normalise_times(_parent_pool(h4_closure, aux_context))

    audit = _build_contextual_rows(abc_quality, abc_context, parents, output_dir)
    parent_context = audit[
        [
            "candidate_id",
            "parent_context_status",
            "parent_candidate_id",
            "parent_wave_context",
            "parent_direction",
            "parent_gap_bars",
            "abc_direction",
            "abc_vs_parent_direction",
            "notes",
            "reviewed_chart_path",
        ]
    ].copy()
    role = audit[
        [
            "candidate_id",
            "abc_visual_status",
            "phase25_abc_policy_previous",
            "correction_role",
            "contextual_correction_quality",
            "contextual_policy",
            "notes",
            "reviewed_chart_path",
        ]
    ].copy()
    ctype = audit[
        [
            "candidate_id",
            "correction_role",
            "correction_type_simple",
            "trend_context_label",
            "context_score",
            "notes",
            "reviewed_chart_path",
        ]
    ].copy()
    alternation = audit[
        [
            "candidate_id",
            "correction_role",
            "alternation_quality",
            "alternation_notes",
            "reviewed_chart_path",
        ]
    ].copy()
    policy = audit[
        [
            "candidate_id",
            "phase25_abc_policy_previous",
            "contextual_policy",
            "should_enter_phase25_as_context",
            "should_user_review",
            "notes",
            "reviewed_chart_path",
        ]
    ].copy()
    keep = audit[audit["contextual_policy"].eq("usable_contextual_correction")].copy()
    exclude = audit[audit["contextual_policy"].eq("exclude_not_correction")].copy()
    must_review = audit[audit["should_user_review"].eq("yes")].copy()
    summary = _summary_rows(audit)

    outputs = {
        "contextual_corrections_audit": audit,
        "correction_parent_context": parent_context,
        "correction_role_classification": role,
        "correction_type_classification": ctype,
        "correction_alternation_notes": alternation,
        "correction_phase25_policy": policy,
        "correction_examples_to_keep": keep,
        "correction_examples_to_exclude": exclude,
        "correction_user_must_review": must_review,
        "contextual_corrections_summary": summary,
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        _write_image_index(path, name.replace("_", " ").title(), ["reviewed_chart_path", "source_chart_path", "previous_reviewed_chart_path"])

    elapsed = perf_counter() - start
    _write_report(output_dir, audit, summary, elapsed)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "inputs": {
            "abc_audit_dir": _rel_to_repo(abc_audit_dir),
            "h4_closure_dir": _rel_to_repo(h4_closure_dir),
            "context_dir": _rel_to_repo(context_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "summary": {row["metric"]: int(row["value"]) for _, row in summary.iterrows()},
        "notes": [
            "No base WaveCount counts were recalculated or changed.",
            "ABC is evaluated with parent/context hypotheses, not as an isolated 0-A-B-C shape.",
            "Alternation is soft and mostly not_applicable/unknown because comparable wave-2/wave-4 pairs are not exposed.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.4.4 contextual corrections audit.")
    parser.add_argument("--abc-audit-dir", type=Path, default=DEFAULT_ABC_AUDIT_DIR)
    parser.add_argument("--h4-closure-dir", type=Path, default=DEFAULT_H4_CLOSURE_DIR)
    parser.add_argument("--context-dir", type=Path, default=DEFAULT_CONTEXT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_contextual_corrections_audit(
        abc_audit_dir=args.abc_audit_dir,
        h4_closure_dir=args.h4_closure_dir,
        context_dir=args.context_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
