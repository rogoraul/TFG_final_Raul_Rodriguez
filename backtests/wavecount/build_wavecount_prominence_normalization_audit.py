from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDED_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "05_guided_profile"

DEFAULT_PHASE257_DIR = GUIDED_ROOT / "phase2_5_7_market_stratified_expansion_2026-05-24"
DEFAULT_PHASE256_DIR = GUIDED_ROOT / "phase2_5_6_soft_policy_weight_adjustment_2026-05-24"
DEFAULT_PHASE256B_DIR = GUIDED_ROOT / "phase2_5_6b_market_group_bias_audit_2026-05-24"
DEFAULT_PHASE252B_DIR = GUIDED_ROOT / "phase2_5_2b_h1_h4_aux_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_8_prominence_normalization_audit_2026-05-24"

INCLUDED_GROUPS = ("Forex Majors", "Index", "Metals")
PROMINENCE_METRICS = (
    "prominence_vs_window",
    "visual_window_prominence",
    "robust_window_prominence_p05_p95",
    "robust_window_prominence_p10_p90",
    "last_n_bars_prominence_primary",
    "atr_normalized_count_size",
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


def _slug(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "")
        .replace("-", "_")
    )


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        label = (
            _string(row.get("candidate_id"))
            or _string(row.get("resolved_market_group"))
            or _string(row.get("decision"))
            or f"fila {idx + 1}"
        )
        lines.append(f"## {idx + 1}. {label}")
        for column in (
            "resolved_market_group",
            "source_scope",
            "timeframe",
            "swing_degree",
            "phase257_policy_bucket",
            "prominence_visual_verdict",
            "normalization_need",
            "decision",
            "notes",
        ):
            value = _string(row.get(column))
            if value:
                lines.append(f"- {column}: {value}")
        for column in row.index:
            if "path" not in column.lower():
                continue
            value = _string(row.get(column))
            if value.lower().endswith(".png"):
                path = _resolve_repo_path(value)
                lines.extend(["", f"![{path.name}]({path.resolve().as_posix()})"])
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _frame_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Sin filas."
    text = frame.fillna("").astype(str)
    columns = list(text.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in text.iterrows():
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _quantile_range(frame: pd.DataFrame, low_q: float, high_q: float) -> float:
    values = pd.concat(
        [
            pd.to_numeric(frame.get("low", pd.Series(dtype=float)), errors="coerce"),
            pd.to_numeric(frame.get("high", pd.Series(dtype=float)), errors="coerce"),
        ],
        ignore_index=True,
    ).dropna()
    if values.empty:
        return 0.0
    return float(values.quantile(high_q) - values.quantile(low_q))


def _price_range(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    high = pd.to_numeric(frame.get("high", pd.Series(dtype=float)), errors="coerce")
    low = pd.to_numeric(frame.get("low", pd.Series(dtype=float)), errors="coerce")
    if high.dropna().empty or low.dropna().empty:
        return 0.0
    return float(high.max() - low.min())


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator / denominator)


def _atr(frame: pd.DataFrame, window: int = 14) -> float | None:
    if frame.empty or not {"high", "low", "close"}.issubset(frame.columns):
        return None
    data = frame.copy()
    data["high"] = pd.to_numeric(data["high"], errors="coerce")
    data["low"] = pd.to_numeric(data["low"], errors="coerce")
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    prev_close = data["close"].shift(1)
    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - prev_close).abs(),
            (data["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    values = true_range.dropna().tail(window)
    if values.empty:
        return None
    return float(values.mean())


def _last_n_windows(timeframe: str) -> tuple[int, int, int]:
    return (240, 480, 960) if timeframe.upper() == "H1" else (120, 240, 480)


def _normalize_timestamp_column(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame.get(column, pd.Series(dtype=str)), errors="coerce")


def load_context_catalog(phase257_dir: Path, phase252b_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load H4/D1 and H1/H4 context catalogs without changing prior artifacts."""
    pieces: list[pd.DataFrame] = []
    context_pieces: list[pd.DataFrame] = []

    h4_base = phase257_dir / "diagnostic_phase2_4_h4_d1_stratified"
    h4_candidates = _read_csv(h4_base / "tables" / "candidate_context.csv")
    h4_context = _read_csv(h4_base / "tables" / "wavecount_context.csv")
    if not h4_candidates.empty:
        h4_candidates["source_scope"] = "h4_d1"
        pieces.append(h4_candidates)
    if not h4_context.empty:
        h4_context["source_scope"] = "h4_d1"
        context_pieces.append(h4_context)

    h1_base = phase252b_dir / "diagnostic_phase2_4_h1_h4_aux"
    h1_candidates = _read_csv(h1_base / "tables" / "candidate_context.csv")
    h1_context = _read_csv(h1_base / "tables" / "wavecount_context.csv")
    if not h1_candidates.empty:
        h1_candidates["source_scope"] = "h1_h4"
        pieces.append(h1_candidates)
    if not h1_context.empty:
        h1_context["source_scope"] = "h1_h4"
        context_pieces.append(h1_context)

    candidates = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    context = pd.concat(context_pieces, ignore_index=True) if context_pieces else pd.DataFrame()
    if not candidates.empty:
        for column in ("start_time", "end_time"):
            candidates[column] = _normalize_timestamp_column(candidates, column)
    if not context.empty:
        context["timestamp"] = _normalize_timestamp_column(context, "timestamp")
    return candidates, context


def compute_candidate_alternative_metrics(candidate: pd.Series, context: pd.DataFrame) -> dict[str, Any]:
    """Compute offline prominence diagnostics for one candidate and its OHLC context."""
    cid = _string(candidate.get("candidate_id"))
    example_id = _string(candidate.get("example_id"))
    timeframe = _string(candidate.get("timeframe"))
    start_time = pd.to_datetime(candidate.get("start_time"), errors="coerce")
    end_time = pd.to_datetime(candidate.get("end_time"), errors="coerce")
    base: dict[str, Any] = {
        "candidate_id": cid,
        "example_id": example_id,
        "metrics_available": False,
        "metrics_unavailable_reason": "",
        "visual_window_prominence": None,
        "last_n_bars_prominence_120": None,
        "last_n_bars_prominence_240": None,
        "last_n_bars_prominence_480": None,
        "last_n_bars_prominence_960": None,
        "last_n_bars_prominence_primary": None,
        "major_context_prominence": None,
        "major_context_status": "not_available",
        "robust_window_prominence_p05_p95": None,
        "robust_window_prominence_p10_p90": None,
        "atr_normalized_count_size": None,
        "robust_improvement_ratio_p05_p95": None,
        "last_n_improvement_ratio": None,
        "atr_14_at_end": None,
        "count_window_range_recomputed": None,
        "visible_window_range_recomputed": None,
        "robust_window_range_p05_p95": None,
        "robust_window_range_p10_p90": None,
        "count_bars_recomputed": 0,
        "visible_window_bars_recomputed": 0,
        "last_n_primary": "",
        "offline_metric_note": "offline_diagnostic_not_live_rule",
    }
    if context.empty:
        base["metrics_unavailable_reason"] = "context_table_empty"
        return base
    if not example_id or pd.isna(start_time) or pd.isna(end_time):
        base["metrics_unavailable_reason"] = "missing_example_or_times"
        return base
    example = context[context["example_id"].astype(str).eq(example_id)].copy()
    if example.empty:
        base["metrics_unavailable_reason"] = "example_context_not_found"
        return base
    example = example.sort_values("timestamp")
    segment = example[(example["timestamp"] >= start_time) & (example["timestamp"] <= end_time)].copy()
    if segment.empty:
        base["metrics_unavailable_reason"] = "candidate_segment_not_found"
        return base

    count_range = _price_range(segment)
    visible_range = _price_range(example)
    robust_range_05_95 = _quantile_range(example, 0.05, 0.95)
    robust_range_10_90 = _quantile_range(example, 0.10, 0.90)
    base.update(
        {
            "metrics_available": True,
            "metrics_unavailable_reason": "",
            "count_window_range_recomputed": count_range,
            "visible_window_range_recomputed": visible_range,
            "robust_window_range_p05_p95": robust_range_05_95,
            "robust_window_range_p10_p90": robust_range_10_90,
            "count_bars_recomputed": int(len(segment)),
            "visible_window_bars_recomputed": int(len(example)),
            "visual_window_prominence": _safe_ratio(count_range, visible_range),
            "robust_window_prominence_p05_p95": _safe_ratio(count_range, robust_range_05_95),
            "robust_window_prominence_p10_p90": _safe_ratio(count_range, robust_range_10_90),
        }
    )
    visual = _number(base["visual_window_prominence"], default=0.0)
    robust = _number(base["robust_window_prominence_p05_p95"], default=0.0)
    base["robust_improvement_ratio_p05_p95"] = _safe_ratio(robust, visual) if visual > 0 else None

    past = example[example["timestamp"] <= end_time].copy()
    windows = _last_n_windows(timeframe)
    last_values: dict[int, float | None] = {}
    for window in windows:
        denom = _price_range(past.tail(window))
        value = _safe_ratio(count_range, denom)
        last_values[window] = value
        base[f"last_n_bars_prominence_{window}"] = value
    primary_window = windows[1]
    base["last_n_primary"] = str(primary_window)
    base["last_n_bars_prominence_primary"] = last_values.get(primary_window)
    last_primary = _number(base["last_n_bars_prominence_primary"], default=0.0)
    base["last_n_improvement_ratio"] = _safe_ratio(last_primary, visual) if visual > 0 else None

    atr_value = _atr(past.tail(max(60, windows[0])), window=14)
    base["atr_14_at_end"] = atr_value
    base["atr_normalized_count_size"] = _safe_ratio(count_range, atr_value or 0.0) if atr_value else None
    return base


def build_alternative_metrics(scores: pd.DataFrame, candidates: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    candidate_map = candidates.set_index("candidate_id").to_dict("index") if "candidate_id" in candidates else {}
    rows: list[dict[str, Any]] = []
    for _, score_row in scores.iterrows():
        cid = _string(score_row.get("candidate_id"))
        candidate = pd.Series(candidate_map.get(cid, {}))
        metrics = compute_candidate_alternative_metrics(candidate, context)
        row = {
            "candidate_id": cid,
            "source_scope": _string(score_row.get("source_scope")),
            "resolved_market_group": _string(score_row.get("resolved_market_group")),
            "symbol": _string(score_row.get("symbol")),
            "timeframe": _string(score_row.get("timeframe")),
            "swing_degree": _string(score_row.get("swing_degree")),
            "review_category": _string(score_row.get("review_category")),
            "phase257_policy_bucket": _string(score_row.get("phase257_policy_bucket")),
            "phase257_score": _number(score_row.get("phase257_score")),
            "prominence_vs_window": _number(score_row.get("prominence_vs_window"), default=float("nan")),
            "duration_vs_window": _number(score_row.get("duration_vs_window"), default=float("nan")),
            "relative_structure_size": _string(score_row.get("relative_structure_size")),
            "scale_fit_label": _string(score_row.get("scale_fit_label")),
            "prominence_policy_label": _string(score_row.get("prominence_policy_label")),
            "chart_path": _string(score_row.get("chart_path")),
        }
        row.update(metrics)
        row["candidate_id"] = cid
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    for group_cols, source_col, target_col in (
        (["resolved_market_group", "source_scope", "timeframe", "swing_degree"], "visual_window_prominence", "group_percentile_prominence"),
        (["symbol", "source_scope", "timeframe", "swing_degree"], "visual_window_prominence", "symbol_percentile_prominence"),
        (["resolved_market_group", "source_scope", "timeframe", "swing_degree"], "robust_window_prominence_p05_p95", "group_percentile_robust_prominence"),
        (["symbol", "source_scope", "timeframe", "swing_degree"], "robust_window_prominence_p05_p95", "symbol_percentile_robust_prominence"),
    ):
        out[target_col] = out.groupby(group_cols)[source_col].rank(pct=True, method="average")
    return out


def _metric_summary(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return pd.DataFrame()
    working = frame.copy()
    for column in group_cols:
        if column not in working.columns:
            working[column] = ""
    grouped = working.groupby(group_cols, dropna=False)
    for keys, part in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {column: key for column, key in zip(group_cols, keys)}
        row["candidate_count"] = int(len(part))
        row["metrics_available_count"] = int(part.get("metrics_available", pd.Series(dtype=bool)).fillna(False).sum())
        row["low_prominence_count"] = int(part.get("prominence_policy_label", pd.Series(dtype=str)).astype(str).eq("low_prominence_vs_window").sum())
        row["too_small_for_timeframe_count"] = int(part.get("scale_fit_label", pd.Series(dtype=str)).astype(str).eq("too_small_for_timeframe").sum())
        for metric in PROMINENCE_METRICS:
            if metric not in part:
                continue
            values = pd.to_numeric(part[metric], errors="coerce").dropna()
            row[f"{metric}_count"] = int(len(values))
            row[f"{metric}_median"] = float(values.median()) if not values.empty else None
            row[f"{metric}_p10"] = float(values.quantile(0.10)) if not values.empty else None
            row[f"{metric}_p25"] = float(values.quantile(0.25)) if not values.empty else None
            row[f"{metric}_p75"] = float(values.quantile(0.75)) if not values.empty else None
            row[f"{metric}_p90"] = float(values.quantile(0.90)) if not values.empty else None
            row[f"{metric}_min"] = float(values.min()) if not values.empty else None
            row[f"{metric}_max"] = float(values.max()) if not values.empty else None
        rows.append(row)
    return pd.DataFrame(rows)


def build_prominence_aggregation_audit(metrics: pd.DataFrame) -> pd.DataFrame:
    levels = [
        ("group_only", ["resolved_market_group"]),
        ("group_source_scope", ["resolved_market_group", "source_scope"]),
        ("group_timeframe", ["resolved_market_group", "timeframe"]),
        ("group_degree", ["resolved_market_group", "swing_degree"]),
        ("group_timeframe_degree", ["resolved_market_group", "source_scope", "timeframe", "swing_degree"]),
        ("symbol_timeframe_degree", ["resolved_market_group", "symbol", "source_scope", "timeframe", "swing_degree"]),
        ("group_policy_bucket", ["resolved_market_group", "phase257_policy_bucket"]),
    ]
    pieces: list[pd.DataFrame] = []
    for level, columns in levels:
        summary = _metric_summary(metrics, columns)
        if summary.empty:
            continue
        summary.insert(0, "aggregation_level", level)
        summary["mixing_risk"] = (
            "high_mixes_scope_timeframe_or_degree"
            if level in {"group_only", "group_source_scope", "group_timeframe", "group_degree"}
            else "low_separates_scope_timeframe_degree"
        )
        pieces.append(summary)
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def _availability_reason(metrics_available: Any, unavailable_reason: Any) -> str:
    return "available" if bool(metrics_available) else _string(unavailable_reason) or "not_available"


def build_metals_h4_d1_audit(metrics: pd.DataFrame) -> pd.DataFrame:
    metals = metrics[
        metrics.get("resolved_market_group", pd.Series(dtype=str)).astype(str).eq("Metals")
        & metrics.get("source_scope", pd.Series(dtype=str)).astype(str).eq("h4_d1")
    ].copy()
    rows: list[dict[str, Any]] = []
    for _, row in metals.iterrows():
        visual = _number(row.get("visual_window_prominence"), _number(row.get("prominence_vs_window"), 0.0))
        robust = _number(row.get("robust_window_prominence_p05_p95"), 0.0)
        last_n = _number(row.get("last_n_bars_prominence_primary"), 0.0)
        robust_ratio = _number(row.get("robust_improvement_ratio_p05_p95"), 0.0)
        last_ratio = _number(row.get("last_n_improvement_ratio"), 0.0)
        if not bool(row.get("metrics_available")):
            diagnosis = "alternative_metrics_unavailable"
        elif visual < 0.08 and robust_ratio >= 1.5:
            diagnosis = "spike_or_robust_window_distortion_possible"
        elif visual < 0.08 and last_ratio >= 1.5:
            diagnosis = "visual_window_too_large_possible"
        elif visual < 0.08 and robust < 0.12 and last_n < 0.12:
            diagnosis = "true_low_prominence_likely"
        elif visual < 0.18:
            diagnosis = "metals_low_prominence_needs_percentile_context"
        else:
            diagnosis = "metals_prominence_acceptable_in_this_case"
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "review_category": _string(row.get("review_category")),
                "phase257_policy_bucket": _string(row.get("phase257_policy_bucket")),
                "metrics_status": _availability_reason(row.get("metrics_available"), row.get("metrics_unavailable_reason")),
                "prominence_vs_window": row.get("prominence_vs_window"),
                "visual_window_prominence": row.get("visual_window_prominence"),
                "robust_window_prominence_p05_p95": row.get("robust_window_prominence_p05_p95"),
                "last_n_bars_prominence_primary": row.get("last_n_bars_prominence_primary"),
                "atr_normalized_count_size": row.get("atr_normalized_count_size"),
                "group_percentile_prominence": row.get("group_percentile_prominence"),
                "symbol_percentile_prominence": row.get("symbol_percentile_prominence"),
                "metals_prominence_diagnosis": diagnosis,
                "chart_path": _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_group_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    summary = _metric_summary(metrics, ["resolved_market_group", "source_scope", "timeframe", "swing_degree"])
    if summary.empty:
        return summary
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        group = _string(row.get("resolved_market_group"))
        visual_median = _number(row.get("visual_window_prominence_median"), _number(row.get("prominence_vs_window_median"), 0.0))
        robust_median = _number(row.get("robust_window_prominence_p05_p95_median"), 0.0)
        atr_median = _number(row.get("atr_normalized_count_size_median"), 0.0)
        if group == "Metals" and visual_median < 0.08:
            interpretation = "metals_low_prominence_requires_normalization_audit"
        elif visual_median >= 0.18:
            interpretation = "global_prominence_temporarily_reasonable"
        else:
            interpretation = "borderline_needs_group_context"
        rows.append({**row.to_dict(), "comparison_interpretation": interpretation, "atr_median_available": atr_median > 0, "robust_median_available": robust_median > 0})
    return pd.DataFrame(rows)


def _copy_chart(row: pd.Series, output_dir: Path, idx: int) -> str:
    src_value = _string(row.get("chart_path"))
    if not src_value:
        return ""
    src = _resolve_repo_path(src_value)
    if not src.exists():
        return src_value
    group_dir = _slug(_string(row.get("resolved_market_group")) or "unknown")
    dest_dir = output_dir / "charts" / "prominence_review" / group_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{idx:03d}_{src.name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return _rel_to_repo(dest)


def _select_nearest(part: pd.DataFrame, metric: str, target: float) -> pd.DataFrame:
    values = pd.to_numeric(part.get(metric, pd.Series(dtype=float)), errors="coerce")
    available = part[values.notna()].copy()
    if available.empty:
        return available
    available["_distance"] = (pd.to_numeric(available[metric], errors="coerce") - target).abs()
    return available.sort_values("_distance").head(1).drop(columns=["_distance"])


def build_visual_selection(metrics: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()
    available = metrics[
        metrics.get("chart_path", pd.Series(dtype=str)).fillna("").astype(str).ne("")
        & metrics.get("chart_path", pd.Series(dtype=str)).map(lambda value: _resolve_repo_path(_string(value)).exists())
    ].copy()
    if available.empty:
        return pd.DataFrame()

    selected: list[pd.DataFrame] = []
    for group in INCLUDED_GROUPS:
        group_part = available[available["resolved_market_group"].astype(str).eq(group)].copy()
        if group_part.empty:
            continue
        h4 = group_part[group_part["source_scope"].astype(str).eq("h4_d1")].copy()
        primary = h4 if not h4.empty else group_part
        for degree in ("intermediate", "major", "minor"):
            degree_part = primary[primary["swing_degree"].astype(str).eq(degree)].copy()
            if degree_part.empty:
                continue
            by_visual = degree_part.sort_values("prominence_vs_window")
            selected.append(by_visual.head(1).assign(selection_reason=f"{group}_{degree}_low_visual_prominence"))
            selected.append(_select_nearest(degree_part, "prominence_vs_window", degree_part["prominence_vs_window"].median()).assign(selection_reason=f"{group}_{degree}_mid_visual_prominence"))
            selected.append(by_visual.tail(1).assign(selection_reason=f"{group}_{degree}_high_visual_prominence"))
        robust = group_part[pd.to_numeric(group_part.get("robust_improvement_ratio_p05_p95", pd.Series(dtype=float)), errors="coerce").fillna(0).ge(1.5)]
        if not robust.empty:
            selected.append(robust.sort_values("robust_improvement_ratio_p05_p95", ascending=False).head(1).assign(selection_reason=f"{group}_robust_window_improves"))
    metals_h1 = available[
        available["resolved_market_group"].astype(str).eq("Metals")
        & available["source_scope"].astype(str).eq("h1_h4")
    ].copy()
    if not metals_h1.empty:
        selected.append(metals_h1.sort_values("prominence_vs_window", ascending=False).head(2).assign(selection_reason="metals_h1_h4_possible_better_representation"))

    selection = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    if selection.empty:
        return selection
    selection = selection.drop_duplicates("candidate_id").head(30).copy()
    copied_paths: list[str] = []
    for idx, (_, row) in enumerate(selection.iterrows(), start=1):
        copied_paths.append(_copy_chart(row, output_dir, idx))
    selection["reviewed_chart_path"] = copied_paths
    columns = [
        "candidate_id",
        "selection_reason",
        "resolved_market_group",
        "source_scope",
        "symbol",
        "timeframe",
        "swing_degree",
        "review_category",
        "phase257_policy_bucket",
        "prominence_vs_window",
        "visual_window_prominence",
        "robust_window_prominence_p05_p95",
        "last_n_bars_prominence_primary",
        "atr_normalized_count_size",
        "group_percentile_prominence",
        "symbol_percentile_prominence",
        "chart_path",
        "reviewed_chart_path",
    ]
    return selection[[column for column in columns if column in selection.columns]]


def build_visual_review(selection: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in selection.iterrows():
        visual = _number(row.get("visual_window_prominence"), _number(row.get("prominence_vs_window"), 0.0))
        robust = _number(row.get("robust_window_prominence_p05_p95"), 0.0)
        last_n = _number(row.get("last_n_bars_prominence_primary"), 0.0)
        robust_ratio = _safe_ratio(robust, visual) if visual > 0 else None
        if visual < 0.08 and robust_ratio and robust_ratio >= 1.5:
            verdict = "spike_distorted_window"
            need = "robust_window"
        elif visual < 0.08 and last_n >= 0.12:
            verdict = "window_too_large"
            need = "causal_window_redesign"
        elif visual < 0.08:
            verdict = "true_low_prominence"
            need = "symbol_timeframe_percentile"
        elif visual < 0.18 and _string(row.get("resolved_market_group")) == "Metals":
            verdict = "acceptable_after_group_normalization"
            need = "group_percentile"
        elif _string(row.get("source_scope")) == "h1_h4" and _string(row.get("resolved_market_group")) == "Metals":
            verdict = "better_as_h1_h4_auxiliary"
            need = "none"
        else:
            verdict = "not_enough_evidence" if visual == 0 else "acceptable_after_group_normalization"
            need = "none" if visual >= 0.18 else "group_percentile"
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": _string(row.get("resolved_market_group")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "phase257_policy_bucket": _string(row.get("phase257_policy_bucket")),
                "prominence_visual_verdict": verdict,
                "normalization_need": need,
                "should_change_policy_now": "no_document_only",
                "visual_window_prominence": row.get("visual_window_prominence"),
                "robust_window_prominence_p05_p95": row.get("robust_window_prominence_p05_p95"),
                "last_n_bars_prominence_primary": row.get("last_n_bars_prominence_primary"),
                "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
                "notes": "Revisión visual asistida; la fase no cambia política 2.5.6.",
            }
        )
    return pd.DataFrame(rows)


def build_causal_window_feasibility() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "metric": "last_N_bars_window",
                "causal_feasibility": "causal_if_only_closed_past_bars",
                "live_ready_now": False,
                "requirements": "Definir N por timeframe y calcular solo con velas cerradas anteriores al count_detected_at.",
                "risk": "N arbitrario puede no representar el movimiento padre.",
            },
            {
                "metric": "last_confirmed_major_window",
                "causal_feasibility": "causal_if_major_uses_structural_detected_at",
                "live_ready_now": False,
                "requirements": "Necesita enlazar cada candidato con el último major confirmado sin mirar pivotes futuros.",
                "risk": "Si el major cambia con latencia, la ventana puede moverse.",
            },
            {
                "metric": "robust_window_p05_p95",
                "causal_feasibility": "causal_if_computed_on_past_window",
                "live_ready_now": False,
                "requirements": "Usar ventana pasada congelada y percentiles calculados solo con datos disponibles.",
                "risk": "Puede ocultar spikes que sí sean relevantes en metales.",
            },
            {
                "metric": "atr_normalized_count_size",
                "causal_feasibility": "causal_if_atr_uses_closed_past_bars",
                "live_ready_now": False,
                "requirements": "ATR por símbolo/timeframe con velas cerradas, sin vela en formación.",
                "risk": "ATR alto tras spike puede seguir penalizando estructuras legítimas.",
            },
            {
                "metric": "symbol_group_percentiles",
                "causal_feasibility": "usable_if_trained_offline_and_frozen",
                "live_ready_now": False,
                "requirements": "Calibrar percentiles offline por símbolo/timeframe/grado y congelarlos para uso diagnóstico.",
                "risk": "Muestra pequeña o cambios de régimen pueden sesgar percentiles.",
            },
            {
                "metric": "current_visual_window",
                "causal_feasibility": "not_live_ready",
                "live_ready_now": False,
                "requirements": "Sustituir por ventana causal antes de cualquier uso live.",
                "risk": "Mezcla futuro visual y rango completo del plot.",
            },
        ]
    )


def build_policy_recommendation(metrics: pd.DataFrame, metals_audit: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    metals_h4 = comparison[
        comparison.get("resolved_market_group", pd.Series(dtype=str)).astype(str).eq("Metals")
        & comparison.get("source_scope", pd.Series(dtype=str)).astype(str).eq("h4_d1")
    ].copy()
    metals_low = False
    if not metals_h4.empty:
        medians = pd.to_numeric(metals_h4.get("visual_window_prominence_median"), errors="coerce").dropna()
        metals_low = bool((medians < 0.08).any())
    robust_cases = 0
    if not metrics.empty and "robust_improvement_ratio_p05_p95" in metrics:
        robust_cases = int(pd.to_numeric(metrics["robust_improvement_ratio_p05_p95"], errors="coerce").fillna(0).ge(1.5).sum())
    true_low_metals = 0
    if not metals_audit.empty:
        true_low_metals = int(metals_audit["metals_prominence_diagnosis"].astype(str).eq("true_low_prominence_likely").sum())
    if metals_low and robust_cases:
        decision = "use_robust_window_prominence_next"
        next_metric = "robust_window_prominence_p05_p95 plus symbol/timeframe/degree percentiles"
    elif metals_low:
        decision = "use_symbol_timeframe_degree_percentiles_next"
        next_metric = "symbol_timeframe_degree_percentiles"
    else:
        decision = "keep_global_with_market_warning"
        next_metric = "global prominence with group reporting"
    notes = (
        "2.5.6 remains vigente: this phase only audits normalization. "
        "The current visual-window prominence is offline and not live-ready."
    )
    return pd.DataFrame(
        [
            {
                "decision": decision,
                "phase256_still_valid": True,
                "phase257_still_valid": True,
                "metals_low_after_scope_degree_split": metals_low,
                "robust_improvement_cases": robust_cases,
                "true_low_metals_cases": true_low_metals,
                "recommended_phase259_metric": next_metric,
                "should_change_policy_now": False,
                "manual_metals_review_before_policy_change": true_low_metals > 0,
                "notes": notes,
            }
        ]
    )


def _make_contact_sheet(image_paths: list[Path], output_path: Path, *, title: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    existing = [path for path in image_paths if path.exists()]
    if not existing:
        return
    thumbs: list[Image.Image] = []
    labels: list[str] = []
    for path in existing[:12]:
        image = Image.open(path).convert("RGB")
        image.thumbnail((480, 300))
        thumbs.append(image.copy())
        labels.append(path.name[:70])
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    width = cols * 520
    height = 60 + rows * 360
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        title_font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
        title_font = font
    draw.text((20, 18), title, fill="black", font=title_font)
    for i, image in enumerate(thumbs):
        x = (i % cols) * 520 + 20
        y = 60 + (i // cols) * 360
        sheet.paste(image, (x, y))
        draw.text((x, y + image.height + 8), labels[i], fill="black", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def build_report(
    output_dir: Path,
    aggregation: pd.DataFrame,
    metals_audit: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> None:
    decision = recommendation.iloc[0].to_dict() if not recommendation.empty else {}
    group_summary = aggregation[aggregation.get("aggregation_level", pd.Series(dtype=str)).astype(str).eq("group_timeframe_degree")]
    lines = [
        "# WaveCount Phase 2.5.8 - Prominence Normalization Audit",
        "",
        "Fase offline/descriptiva. No cambia la politica 2.5.6, no recalcula conteos base y no genera senales.",
        "",
        "## Decision",
        "",
        f"- decision: `{_string(decision.get('decision'))}`",
        f"- phase256_still_valid: `{decision.get('phase256_still_valid', True)}`",
        f"- recommended_phase259_metric: `{_string(decision.get('recommended_phase259_metric'))}`",
        "",
        "## Lectura metodologica",
        "",
        "- La prominencia agregada por grupo puede mezclar grados/timeframes; esta fase separa grupo, scope, timeframe, grado y simbolo.",
        "- La ventana visual completa sigue siendo una metrica offline, no live-ready.",
        "- Metals se audita aparte porque habia medianas H4/D1 claramente mas bajas que Forex Majors e Index.",
        "- EWO/EMAs/HTF no se convierten en reglas duras.",
        "",
        "## Tablas clave",
        "",
        "- `tables/prominence_aggregation_audit.csv`",
        "- `tables/prominence_alternative_metrics.csv`",
        "- `tables/metals_h4_d1_prominence_audit.csv`",
        "- `tables/prominence_policy_recommendation.csv`",
        "",
        "## Resumen grupo/timeframe/grado",
        "",
    ]
    if group_summary.empty:
        lines.append("Sin resumen disponible.")
    else:
        subset = group_summary[
            [
                column
                for column in (
                    "resolved_market_group",
                    "source_scope",
                    "timeframe",
                    "swing_degree",
                    "candidate_count",
                    "prominence_vs_window_median",
                    "visual_window_prominence_median",
                    "robust_window_prominence_p05_p95_median",
                    "atr_normalized_count_size_median",
                )
                if column in group_summary.columns
            ]
        ].head(24)
        lines.append(_frame_to_markdown(subset))
    lines.extend(
        [
            "",
            "## Metals H4/D1",
            "",
        ]
    )
    if metals_audit.empty:
        lines.append("Sin filas Metals H4/D1.")
    else:
        lines.append(
            _frame_to_markdown(
                metals_audit["metals_prominence_diagnosis"]
                .value_counts()
                .rename_axis("diagnosis")
                .reset_index(name="count")
            )
        )
    (output_dir / "WAVECOUNT_PHASE2_5_8_PROMINENCE_NORMALIZATION_AUDIT.md").write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )


def build_user_review_if_any(visual_review: pd.DataFrame, recommendation: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not visual_review.empty:
        needs = visual_review[
            visual_review.get("prominence_visual_verdict", pd.Series(dtype=str)).astype(str).isin(
                {"still_problematic", "not_enough_evidence"}
            )
        ]
        for _, row in needs.head(8).iterrows():
            rows.append(
                {
                    "candidate_id": _string(row.get("candidate_id")),
                    "review_reason": _string(row.get("prominence_visual_verdict")),
                    "priority": "low",
                    "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
                    "notes": "Solo revisar si se decide ajustar politica en 2.5.9.",
                }
            )
    if not rows:
        rows.append(
            {
                "candidate_id": "",
                "review_reason": "no_blocking_manual_review",
                "priority": "none",
                "reviewed_chart_path": "",
                "notes": "No hace falta revision manual para cerrar 2.5.8; la siguiente decision puede documentarse en 2.5.9.",
            }
        )
    return pd.DataFrame(rows)


def run(
    *,
    phase257_dir: Path = DEFAULT_PHASE257_DIR,
    phase256_dir: Path = DEFAULT_PHASE256_DIR,
    phase256b_dir: Path = DEFAULT_PHASE256B_DIR,
    phase252b_dir: Path = DEFAULT_PHASE252B_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    scores = _read_csv(phase257_dir / "tables" / "phase257_policy_scores.csv")
    phase256_scores = _read_csv(phase256_dir / "tables" / "phase256_policy_scores.csv")
    mapping = _read_csv(phase256b_dir / "tables" / "market_group_mapping_evidence.csv")
    sql_categories = _read_csv(phase256b_dir / "tables" / "sql_market_categories.csv")
    sql_symbol_timeframes = _read_csv(phase256b_dir / "tables" / "sql_symbol_timeframe_inventory.csv")
    prominence_252b = _read_csv(phase252b_dir / "tables" / "prominence_diagnostics.csv")
    candidates, context = load_context_catalog(phase257_dir, phase252b_dir)

    metrics = build_alternative_metrics(scores, candidates, context)
    aggregation = build_prominence_aggregation_audit(metrics)
    group_tf_degree = _metric_summary(metrics, ["resolved_market_group", "source_scope", "timeframe", "swing_degree"])
    symbol_tf_degree = _metric_summary(metrics, ["resolved_market_group", "symbol", "source_scope", "timeframe", "swing_degree"])
    metals_audit = build_metals_h4_d1_audit(metrics)
    comparison = build_group_comparison(metrics)
    visual_selection = build_visual_selection(metrics, output_dir)
    visual_review = build_visual_review(visual_selection)
    causal_feasibility = build_causal_window_feasibility()
    recommendation = build_policy_recommendation(metrics, metals_audit, comparison)
    user_review = build_user_review_if_any(visual_review, recommendation)

    outputs = {
        "prominence_aggregation_audit": aggregation,
        "prominence_by_group_timeframe_degree": group_tf_degree,
        "prominence_by_symbol_timeframe_degree": symbol_tf_degree,
        "prominence_alternative_metrics": metrics,
        "metals_h4_d1_prominence_audit": metals_audit,
        "forex_index_metals_comparison": comparison,
        "prominence_visual_selection": visual_selection,
        "prominence_visual_review": visual_review,
        "causal_window_feasibility": causal_feasibility,
        "prominence_policy_recommendation": recommendation,
        "user_review_if_any": user_review,
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        if any("path" in column.lower() for column in frame.columns) or name in {
            "prominence_policy_recommendation",
            "causal_window_feasibility",
        }:
            _write_markdown_index(path, name.replace("_", " ").title())

    for group in INCLUDED_GROUPS:
        rows = visual_selection[visual_selection.get("resolved_market_group", pd.Series(dtype=str)).astype(str).eq(group)]
        paths = [_resolve_repo_path(_string(path)) for path in rows.get("reviewed_chart_path", pd.Series(dtype=str)).dropna().astype(str) if _string(path)]
        _make_contact_sheet(
            paths,
            output_dir / "charts" / "prominence_review" / f"{_slug(group)}_contact_sheet.png",
            title=f"WaveCount 2.5.8 prominence review - {group}",
        )

    build_report(output_dir, aggregation, metals_audit, recommendation)

    run_meta = {
        "phase": "2.5.8",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase257_dir": _rel_to_repo(phase257_dir),
            "phase256_dir": _rel_to_repo(phase256_dir),
            "phase256b_dir": _rel_to_repo(phase256b_dir),
            "phase252b_dir": _rel_to_repo(phase252b_dir),
            "phase257_rows": int(len(scores)),
            "phase256_rows": int(len(phase256_scores)),
            "context_candidates_rows": int(len(candidates)),
            "context_ohlc_rows": int(len(context)),
            "mapping_rows": int(len(mapping)),
            "sql_category_rows": int(len(sql_categories)),
            "sql_symbol_timeframe_rows": int(len(sql_symbol_timeframes)),
            "phase252b_prominence_rows": int(len(prominence_252b)),
        },
        "rules_changed": False,
        "phase256_policy_changed": False,
        "signals_generated": False,
        "backtests_executed": False,
        "base_counts_recomputed": False,
        "notes": "Offline prominence normalization audit; no policy or signal changes.",
        "runtime_seconds": round(perf_counter() - started, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount phase 2.5.8 prominence normalization audit artifacts.")
    parser.add_argument("--phase257-dir", type=Path, default=DEFAULT_PHASE257_DIR)
    parser.add_argument("--phase256-dir", type=Path, default=DEFAULT_PHASE256_DIR)
    parser.add_argument("--phase256b-dir", type=Path, default=DEFAULT_PHASE256B_DIR)
    parser.add_argument("--phase252b-dir", type=Path, default=DEFAULT_PHASE252B_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = run(
        phase257_dir=args.phase257_dir,
        phase256_dir=args.phase256_dir,
        phase256b_dir=args.phase256b_dir,
        phase252b_dir=args.phase252b_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
