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
from backtests.wavecount.wavecount_visual_review_gallery import VisualReviewSpec, build_visual_review_gallery


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE252_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_2_guided_impulse_expansion_2026-05-24"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_2b_h1_h4_aux_expansion_2026-05-24"
)


H1_H4_SPECS = (
    VisualReviewSpec("aux252b_forex_eurusd_h1", "Forex Majors", "EURUSD.r", "H1", 1100),
    VisualReviewSpec("aux252b_forex_gbpusd_h1", "Forex Majors", "GBPUSD.r", "H1", 1100),
    VisualReviewSpec("aux252b_forex_usdjpy_h1", "Forex Majors", "USDJPY.r", "H1", 1100),
    VisualReviewSpec("aux252b_forex_audjpy_h1", "Forex Majors", "AUDJPY.r", "H1", 1100),
    VisualReviewSpec("aux252b_forex_eurjpy_h1", "Forex Majors", "EURJPY.r", "H1", 1100),
    VisualReviewSpec("aux252b_forex_gbpjpy_h1", "Forex Majors", "GBPJPY.r", "H1", 1100),
    VisualReviewSpec("aux252b_metals_xauusd_h1", "Metals", "XAUUSD.r", "H1", 1100),
    VisualReviewSpec("aux252b_metals_xagusd_h1", "Metals", "XAGUSD.r", "H1", 1100),
    VisualReviewSpec("aux252b_metals_xptusd_h1", "Metals", "XPTUSD", "H1", 1100),
    VisualReviewSpec("aux252b_metals_xpdusd_h1", "Metals", "XPDUSD", "H1", 1100),
    VisualReviewSpec("aux252b_index_aus200_h1", "Index", "AUS200", "H1", 1100),
    VisualReviewSpec("aux252b_index_hk50_h1", "Index", "HK50", "H1", 1100),
    VisualReviewSpec("aux252b_index_us500_h1", "Index", "US500", "H1", 1100),
    VisualReviewSpec("aux252b_index_us30_h1", "Index", "US30", "H1", 1100),
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
            _string(row.get("matches_h1_h4_aux_profile")),
            _string(row.get("scale_fit_label")),
            _string(row.get("visual_aux_status")),
        ]
        lines.append(f"## {idx + 1}. {' | '.join(bit for bit in bits if bit) or 'fila'}")
        for column in (
            "aux_profile_reasons",
            "aux_profile_failures",
            "scale_notes",
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


def _aux_profile_match(row: pd.Series) -> dict[str, Any]:
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
    htf_conflict = _boolish(row.get("htf_direction_conflict")) or trend == "conflict_with_htf"
    htf_match = _boolish(row.get("htf_direction_match"))
    ltf_match = _boolish(row.get("ltf_direction_match"))
    momentum = _boolish(row.get("momentum_matches_direction"))
    inside_band = _string(row.get("end_ltf_price_vs_ema_band")) == "inside_band"

    add(category == "impulse", 24, "structure=impulse", f"not impulse ({category})", critical_failure=True)
    add(timeframe == "H1", 15, "timeframe=H1 auxiliary", f"timeframe={timeframe or 'missing'}")
    add(degree == "intermediate", 18, "degree=intermediate", f"degree={degree or 'missing'}")
    add(htf_safe, 10, "H4 context lookahead safe", "H4 context lookahead unsafe", critical_failure=True)
    add(context_score >= 55, 9, f"context_score={context_score}", f"context_score={context_score}")
    add(not htf_conflict, 8, f"HTF not suspicious ({trend})", f"HTF conflict ({trend})")
    add(htf_match or trend in {"impulse_with_htf", "correction_against_htf"}, 6, "H4 context interpretable", "H4 context unclear")
    add(ltf_match, 5, "H1 EMA direction supports count", "H1 EMA direction does not support count")
    add(momentum, 7, "EWO/momentum supports count direction", "EWO/momentum does not support count direction")
    add(not inside_band, 3, "price outside EMA band", "price inside EMA band adds ambiguity")

    score = min(score, 100)
    if category in {"hard_invalid", "abc", "partial_123"}:
        critical.append(f"{category} not part of H1/H4 impulse auxiliary profile")

    if critical:
        match = "no"
    elif score >= 85 and category == "impulse" and timeframe == "H1" and degree == "intermediate" and not htf_conflict:
        match = "yes_aux"
    elif score >= 55 and category == "impulse" and timeframe == "H1":
        match = "near_miss_aux"
    else:
        match = "no"

    return {
        "matches_h1_h4_aux_profile": match,
        "aux_profile_match_score": score,
        "aux_profile_reasons": "; ".join(reasons),
        "aux_profile_failures": "; ".join(failures),
        "aux_profile_critical_failures": "; ".join(dict.fromkeys(critical)),
    }


def _aux_near_miss_reason(row: pd.Series) -> str:
    if _string(row.get("matches_h1_h4_aux_profile")) != "near_miss_aux":
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


def _prominence_metrics(candidates: pd.DataFrame, context: pd.DataFrame, *, source_scope: str) -> pd.DataFrame:
    if candidates.empty or context.empty:
        return pd.DataFrame()
    ctx = context.copy()
    ctx["timestamp"] = pd.to_datetime(ctx["timestamp"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for _, row in candidates.iterrows():
        example_id = _string(row.get("example_id"))
        subset = ctx[ctx["example_id"].astype(str).eq(example_id)].copy()
        if subset.empty:
            continue
        start_time = pd.to_datetime(row.get("start_time"), errors="coerce")
        end_time = pd.to_datetime(row.get("end_time"), errors="coerce")
        segment = subset[(subset["timestamp"] >= start_time) & (subset["timestamp"] <= end_time)].copy()
        visible_range = _number(subset["high"].max() - subset["low"].min())
        segment_range = _number(segment["high"].max() - segment["low"].min()) if not segment.empty else 0.0
        close_start = _number(segment.iloc[0]["close"]) if not segment.empty else 0.0
        close_end = _number(segment.iloc[-1]["close"]) if not segment.empty else 0.0
        count_move_abs = abs(close_end - close_start)
        prominence = segment_range / visible_range if visible_range > 0 else 0.0
        move_prominence = count_move_abs / visible_range if visible_range > 0 else 0.0
        duration = len(segment) / len(subset) if len(subset) else 0.0
        label = _scale_fit_label(row, prominence, duration, source_scope)
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": source_scope,
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "review_category": _string(row.get("review_category")),
                "start_time": _string(row.get("start_time")),
                "end_time": _string(row.get("end_time")),
                "visible_window_range": visible_range,
                "count_window_range": segment_range,
                "count_move_abs": count_move_abs,
                "prominence_vs_window": round(prominence, 6),
                "move_prominence_vs_window": round(move_prominence, 6),
                "count_bars": int(len(segment)),
                "visible_window_bars": int(len(subset)),
                "duration_vs_window": round(duration, 6),
                "relative_structure_size": _relative_size_bucket(prominence, duration),
                "scale_fit_label": label,
                "scale_notes": _scale_notes(row, prominence, duration, label),
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def _scale_fit_label(row: pd.Series, prominence: float, duration: float, source_scope: str) -> str:
    if _string(row.get("review_category")) != "impulse":
        return "not_applicable"
    degree = _string(row.get("swing_degree"))
    if duration < 0.08 and source_scope == "h4_d1":
        return "too_small_for_timeframe"
    if duration < 0.06 and source_scope == "h1_h4":
        return "better_as_lower_tf_substructure"
    if prominence < 0.12:
        return "low_prominence_vs_window"
    if prominence > 0.78 and duration > 0.65:
        return "too_large_or_too_coarse"
    if degree == "minor" and prominence < 0.25:
        return "better_as_lower_tf_substructure"
    if 0.12 <= prominence < 0.20 or duration < 0.11:
        return "ambiguous_scale"
    return "acceptable_for_timeframe"


def _relative_size_bucket(prominence: float, duration: float) -> str:
    if prominence < 0.12 or duration < 0.06:
        return "small"
    if prominence < 0.25 or duration < 0.12:
        return "medium_small"
    if prominence > 0.75 or duration > 0.65:
        return "large"
    return "balanced"


def _scale_notes(row: pd.Series, prominence: float, duration: float, label: str) -> str:
    return (
        f"{label}: prominence={prominence:.3f}; duration={duration:.3f}; "
        f"degree={_string(row.get('swing_degree'))}; category={_string(row.get('review_category'))}"
    )


def _ewo_helpfulness(row: pd.Series) -> str:
    if _boolish(row.get("momentum_matches_direction")):
        return "supports_wave_role"
    direction = _string(row.get("end_ltf_ewo_5_35_direction"))
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


def _visual_aux(row: pd.Series) -> dict[str, Any]:
    match = _string(row.get("matches_h1_h4_aux_profile"))
    near = _string(row.get("aux_near_miss_reason"))
    scale = _string(row.get("scale_fit_label"))
    category = _string(row.get("review_category"))
    ewo = _ewo_helpfulness(row)
    ema = _ema_htf_helpfulness(row)

    if match == "yes_aux" and scale in {"acceptable_for_timeframe", "ambiguous_scale"}:
        status = "good_aux_structure"
        should = "yes_keep_h1_auxiliary"
    elif match == "yes_aux":
        status = "useful_lower_tf_substructure"
        should = "yes_keep_h1_auxiliary"
    elif match == "near_miss_aux" and near in {"minor_substructure", "higher_degree_context"}:
        status = "useful_lower_tf_substructure"
        should = "yes_keep_h1_auxiliary"
    elif match == "near_miss_aux" and near == "context_conflict":
        status = "context_conflict"
        should = "manual_review_needed"
    elif category == "hard_invalid":
        status = "good_negative_example"
        should = "no_context_only"
    elif scale in {"too_small_for_timeframe", "low_prominence_vs_window"}:
        status = "too_micro_even_for_h1"
        should = "yes_add_soft_prominence_penalty"
    elif category in {"partial_123", "abc"}:
        status = "not_usable"
        should = "no_context_only"
    else:
        status = "not_usable"
        should = "no_too_noisy"

    return {
        "visual_aux_status": status,
        "scale_diagnostic_status": _scale_diagnostic_status(row),
        "should_affect_phase25_profile": should,
        "ewo_helpfulness": ewo,
        "ema_htf_helpfulness": ema,
        "visual_notes": f"{status}; scale={scale}; EWO={ewo}; EMA/HTF={ema}; near={near or 'none'}",
    }


def _scale_diagnostic_status(row: pd.Series) -> str:
    scale = _string(row.get("scale_fit_label"))
    source_scope = _string(row.get("source_scope"))
    if source_scope == "h4_d1" and scale in {"too_small_for_timeframe", "low_prominence_vs_window"}:
        return "h4_too_small_confirmed"
    if source_scope == "h4_d1" and scale == "acceptable_for_timeframe":
        return "h4_scale_ok"
    if source_scope == "h1_h4" and scale in {"acceptable_for_timeframe", "ambiguous_scale"}:
        return "h1_better_representation"
    if scale == "not_applicable":
        return "not_enough_evidence"
    return "still_ambiguous"


def _copy_chart(row: pd.Series, output_dir: Path, folder: str) -> str:
    source = _resolve_repo_path(_string(row.get("source_context_chart_path")) or _string(row.get("chart_path")))
    if not source.exists():
        return ""
    filename = f"{int(row.get('candidate_order', 0)):03d}_{_string(row.get('candidate_id'))}.png".replace(":", "-")
    destination = output_dir / "charts" / folder / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return _rel_to_repo(destination)


def _write_contact_sheet(frame: pd.DataFrame, output_path: Path) -> None:
    if frame.empty or "reviewed_chart_path" not in frame.columns:
        return
    rows = frame[frame["reviewed_chart_path"].astype(str).str.endswith(".png", na=False)].head(24)
    if rows.empty:
        return
    thumb_w, thumb_h, label_h, pad, cols = 520, 300, 58, 16, 2
    sheet_rows = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * pad, sheet_rows * (thumb_h + label_h) + (sheet_rows + 1) * pad), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        small = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    for idx, (_, row) in enumerate(rows.iterrows()):
        col, rr = idx % cols, idx // cols
        x, y = pad + col * (thumb_w + pad), pad + rr * (thumb_h + label_h + pad)
        path = _resolve_repo_path(_string(row.get("reviewed_chart_path")))
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
        draw.text((x, y), _string(row.get("candidate_id"))[:82], fill=(20, 20, 20), font=font)
        subtitle = f"{_string(row.get('matches_h1_h4_aux_profile'))} | {_string(row.get('scale_fit_label'))} | {_string(row.get('visual_aux_status'))}"
        draw.text((x, y + 24), subtitle[:92], fill=(80, 80, 80), font=small)
        sheet.paste(image, (x + (thumb_w - image.width) // 2, y + label_h + (thumb_h - image.height) // 2))
        draw.rectangle((x, y + label_h, x + thumb_w, y + label_h + thumb_h), outline=(210, 210, 210), width=1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def _write_report(output_dir: Path, run_meta: dict[str, Any]) -> None:
    lines = [
        "# WaveCount Fase 2.5.2b - H1/H4 auxiliar y prominencia",
        "",
        "## Resumen",
        "",
        "Esta fase revisa H1/H4 como expansion auxiliar y anade diagnostico de escala/prominencia para detectar conteos demasiado pequenos para su timeframe.",
        "",
        "No genera senales, no cambia reglas base y no modifica estrategias.",
        "",
        "## Resultado H1/H4",
        "",
    ]
    for key, value in run_meta["aux_match_counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Prominencia", ""])
    for key, value in run_meta["scale_fit_counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## AUS200 H4",
            "",
            "El caso `impulse_exp252_index_aus200_h4_intermediate_impulse_020` queda documentado como caso de baja duracion relativa/prominencia temporal para H4 y conflicto de contexto. Debe mantenerse como near-miss/riesgo, no como seed.",
            "",
            "## Decision",
            "",
            "H1/H4 aporta como auxiliar y zoom de subestructura, pero no sustituye H4/D1 como base principal. El diagnostico de prominencia puede entrar como penalizacion blanda futura.",
            "",
            "## Run meta",
            "",
            "```json",
            json.dumps(run_meta, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_5_2B_H1_H4_AUX_EXPANSION.md").write_text("\n".join(lines), encoding="utf-8")


def build_h1_h4_aux_expansion(
    *,
    phase252_dir: Path = DEFAULT_PHASE252_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    htf_rows: int = 520,
) -> dict[str, Any]:
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    phase23_dir = output_dir / "diagnostic_phase2_3_h1_h4_aux"
    phase24_dir = output_dir / "diagnostic_phase2_4_h1_h4_aux"
    phase23_meta = build_visual_review_gallery(output_dir=phase23_dir, specs=H1_H4_SPECS)
    phase24_meta = build_context_gallery(input_dir=phase23_dir, output_dir=phase24_dir, htf_rows=htf_rows, specs=H1_H4_SPECS)

    aux = _read_csv(phase24_dir / "tables" / "candidate_context.csv")
    aux_context = _read_csv(phase24_dir / "tables" / "wavecount_context.csv")
    aux = aux.copy()
    original_chart = aux["chart_path"].copy() if "chart_path" in aux.columns else pd.Series([""] * len(aux))
    original_context = aux["context_chart_path"].copy() if "context_chart_path" in aux.columns else pd.Series([""] * len(aux))
    aux["source_count_chart_path"] = original_chart.apply(lambda value: _rel_to_repo(phase23_dir / _string(value)) if _string(value) else "")
    aux["source_context_chart_path"] = original_context.apply(lambda value: _rel_to_repo(phase24_dir / _string(value)) if _string(value) else "")
    aux["chart_path"] = aux["source_context_chart_path"]
    aux["context_chart_path"] = aux["source_context_chart_path"]
    aux["source_scope"] = "h1_h4"

    aux_match = aux.apply(_aux_profile_match, axis=1, result_type="expand")
    aux = pd.concat([aux, aux_match], axis=1)
    aux["aux_near_miss_reason"] = aux.apply(_aux_near_miss_reason, axis=1)
    aux_prom = _prominence_metrics(aux, aux_context, source_scope="h1_h4")
    aux = aux.merge(
        aux_prom[["candidate_id", "prominence_vs_window", "duration_vs_window", "relative_structure_size", "scale_fit_label", "scale_notes"]],
        on="candidate_id",
        how="left",
    )
    visual = aux.apply(_visual_aux, axis=1, result_type="expand")
    aux = pd.concat([aux, visual], axis=1)

    folder_map = {
        "yes_aux": "h1_h4_matches",
        "near_miss_aux": "h1_h4_near_misses",
        "no": "h1_h4_negatives",
    }
    aux["reviewed_chart_path"] = aux.apply(
        lambda row: _copy_chart(row, output_dir, folder_map.get(_string(row.get("matches_h1_h4_aux_profile")), "h1_h4_negatives")),
        axis=1,
    )

    h4_candidates = _read_csv(phase252_dir / "tables" / "guided_impulse_expanded_candidates.csv")
    h4_context = _read_csv(phase252_dir / "diagnostic_phase2_4_h4_d1_expanded" / "tables" / "wavecount_context.csv")
    h4_prom = _prominence_metrics(h4_candidates, h4_context, source_scope="h4_d1")
    h4_suspicious = h4_candidates.merge(
        h4_prom[["candidate_id", "prominence_vs_window", "duration_vs_window", "relative_structure_size", "scale_fit_label", "scale_notes"]],
        on="candidate_id",
        how="left",
    )
    h4_suspicious = h4_suspicious[
        h4_suspicious["scale_fit_label"].isin(["too_small_for_timeframe", "low_prominence_vs_window", "ambiguous_scale"])
        | h4_suspicious["candidate_id"].eq("impulse_exp252_index_aus200_h4_intermediate_impulse_020")
    ].copy()
    h4_suspicious["reviewed_chart_path"] = h4_suspicious.apply(lambda row: _copy_chart(row, output_dir, "h4_suspicious_scale"), axis=1)

    aus = h4_suspicious[h4_suspicious["candidate_id"].eq("impulse_exp252_index_aus200_h4_intermediate_impulse_020")].copy()
    if not aus.empty:
        aus["aus200_case_answer"] = (
            "Mantener como near_miss/riesgo: tramo de corta duracion relativa para H4, conflicto de contexto y mejor candidato a subestructura/zoom H1-H4."
        )
        aus["rule_candidate"] = "add_soft_prominence_duration_penalty"

    scope = pd.DataFrame(
        [
            {
                "expansion_scope": "h1_h4_auxiliary_windows",
                "symbols": "|".join(spec.symbol for spec in H1_H4_SPECS),
                "timeframe": "H1",
                "htf_timeframe": "H4",
                "ltf_rows_per_symbol": 1100,
                "htf_rows": htf_rows,
                "rules_changed": False,
                "signals_generated": False,
                "notes": "Auxiliary diagnostic only; H4/D1 remains primary.",
            }
        ]
    )

    matches = aux[aux["matches_h1_h4_aux_profile"].eq("yes_aux")].copy()
    near = aux[aux["matches_h1_h4_aux_profile"].eq("near_miss_aux")].copy()
    neg = aux[aux["matches_h1_h4_aux_profile"].eq("no")].copy()
    visual_review = aux.copy()
    ewo_review = aux.groupby(["ewo_helpfulness", "matches_h1_h4_aux_profile"], dropna=False).size().reset_index(name="case_count")
    ema_review = aux.groupby(["ema_htf_helpfulness", "matches_h1_h4_aux_profile"], dropna=False).size().reset_index(name="case_count")
    phase253 = pd.DataFrame(
        [
            {
                "recommendation": "keep_h1_h4_as_auxiliary_zoom",
                "status": "yes",
                "reason": "H1/H4 can represent lower-timeframe substructure but should not replace H4/D1.",
            },
            {
                "recommendation": "add_soft_prominence_penalty",
                "status": "yes_candidate",
                "reason": "Short duration / low prominence helps explain H4 counts that look too small.",
            },
            {
                "recommendation": "do_not_promote_aux_to_signal",
                "status": "required",
                "reason": "Auxiliary profile remains descriptive and non-operational.",
            },
        ]
    )
    user_review = pd.concat([matches.head(6), near.head(8), aus], ignore_index=True).drop_duplicates("candidate_id")

    tables = {
        "aux_expansion_scope": scope,
        "h1_h4_aux_candidates": aux,
        "h1_h4_aux_matches": matches,
        "h1_h4_aux_near_misses": near,
        "h1_h4_aux_negatives": neg,
        "prominence_diagnostics": pd.concat([aux_prom, h4_prom], ignore_index=True),
        "h4_suspicious_scale_cases": h4_suspicious,
        "aus200_h4_case_review": aus,
        "visual_aux_review": visual_review,
        "ewo_aux_review": ewo_review,
        "ema_htf_aux_review": ema_review,
        "phase253_aux_recommendation": phase253,
        "user_must_review_if_any": user_review,
    }
    for name, frame in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    _write_contact_sheet(matches, output_dir / "charts" / "h1_h4_matches_contact_sheet.png")
    _write_contact_sheet(near, output_dir / "charts" / "h1_h4_near_misses_contact_sheet.png")
    _write_contact_sheet(neg, output_dir / "charts" / "h1_h4_negatives_contact_sheet.png")
    _write_contact_sheet(h4_suspicious, output_dir / "charts" / "h4_suspicious_scale_contact_sheet.png")
    _write_contact_sheet(user_review, output_dir / "charts" / "comparisons" / "user_review_contact_sheet.png")

    image_refs = [
        _string(value)
        for frame in tables.values()
        if "reviewed_chart_path" in frame.columns
        for value in frame["reviewed_chart_path"].dropna().tolist()
        if _string(value).endswith(".png")
    ]
    missing = sorted({value for value in image_refs if not _resolve_repo_path(value).exists()})

    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "phase252_dir": _rel_to_repo(phase252_dir),
        "expansion_scope": "h1_h4_auxiliary_windows",
        "symbols": [spec.symbol for spec in H1_H4_SPECS],
        "ltf_rows_per_symbol": 1100,
        "htf_rows": htf_rows,
        "phase23_meta": {"charts_ok": len([row for row in phase23_meta.get("charts", []) if row.get("status") == "ok"])},
        "phase24_meta": {"charts_ok": len([row for row in phase24_meta.get("charts", []) if row.get("status") == "ok"])},
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "aux_match_counts": _counts(aux, "matches_h1_h4_aux_profile"),
        "aux_near_miss_reason_counts": _counts(aux, "aux_near_miss_reason"),
        "scale_fit_counts": _counts(tables["prominence_diagnostics"], "scale_fit_label"),
        "visual_aux_status_counts": _counts(aux, "visual_aux_status"),
        "aus200_h4_scale_label": _string(aus.iloc[0].get("scale_fit_label")) if not aus.empty else "missing",
        "missing_image_refs": missing,
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_base_rules_changed": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, run_meta)
    return run_meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.2b H1/H4 auxiliary expansion.")
    parser.add_argument("--phase252-dir", type=Path, default=DEFAULT_PHASE252_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--htf-rows", type=int, default=520)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_h1_h4_aux_expansion(phase252_dir=args.phase252_dir, output_dir=args.output_dir, htf_rows=args.htf_rows)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
