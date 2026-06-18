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

DEFAULT_PHASE258_DIR = GUIDED_ROOT / "phase2_5_8_prominence_normalization_audit_2026-05-24"
DEFAULT_PHASE257_DIR = GUIDED_ROOT / "phase2_5_7_market_stratified_expansion_2026-05-24"
DEFAULT_PHASE256_DIR = GUIDED_ROOT / "phase2_5_6_soft_policy_weight_adjustment_2026-05-24"
DEFAULT_PHASE256B_DIR = GUIDED_ROOT / "phase2_5_6b_market_group_bias_audit_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_9_robust_prominence_policy_trial_2026-05-24"

MIN_SYMBOL_FAMILY_SIZE = 5
LOW_PROMINENCE_THRESHOLD = 0.18
LOW_PERCENTILE_THRESHOLD = 0.25
NORMAL_PERCENTILE_THRESHOLD = 0.50
ROBUST_IMPROVEMENT_RATIO = 1.50

BASELINE_BUCKETS = (
    "high_quality_structure",
    "usable_provisional_structure",
    "visual_watchlist_low_prominence",
    "auxiliary_substructure",
    "auxiliary_low_prominence_substructure",
    "ambiguous_structure",
    "experimental_only",
    "exclude_from_guided_search",
)

CANDIDATE_BUCKETS = tuple(f"candidate_{bucket}" for bucket in BASELINE_BUCKETS)
BUCKET_RANK = {bucket: index for index, bucket in enumerate(BASELINE_BUCKETS)}
INCLUDED_GROUPS = ("Forex Majors", "Index", "Metals")


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


def _slug(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "")
        .replace("-", "_")
    )


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


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        label = (
            _string(row.get("candidate_id"))
            or _string(row.get("resolved_market_group"))
            or _string(row.get("phase2510_recommendation"))
            or f"fila {idx + 1}"
        )
        lines.append(f"## {idx + 1}. {label}")
        for column in (
            "resolved_market_group",
            "source_scope",
            "timeframe",
            "swing_degree",
            "phase256_policy_bucket",
            "phase259_candidate_bucket",
            "phase259_prominence_diagnostic",
            "phase259_visual_verdict",
            "phase2510_recommendation",
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


def _candidate_bucket_from_baseline(bucket: str) -> str:
    if bucket not in BASELINE_BUCKETS:
        return "candidate_experimental_only"
    return f"candidate_{bucket}"


def _baseline_bucket_from_candidate(candidate_bucket: str) -> str:
    if candidate_bucket.startswith("candidate_"):
        return candidate_bucket.replace("candidate_", "", 1)
    return candidate_bucket


def _bucket_change(old_bucket: str, candidate_bucket: str) -> str:
    new_bucket = _baseline_bucket_from_candidate(candidate_bucket)
    old_rank = BUCKET_RANK.get(old_bucket, BUCKET_RANK["experimental_only"])
    new_rank = BUCKET_RANK.get(new_bucket, BUCKET_RANK["experimental_only"])
    if old_rank == new_rank:
        return "unchanged"
    if new_rank < old_rank:
        return "upgrade"
    return "downgrade"


def _path_exists(value: Any) -> bool:
    text = _string(value)
    if not text or not text.lower().endswith(".png"):
        return False
    return _resolve_repo_path(text).exists()


def prepare_phase259_dataset(
    alternative_metrics: pd.DataFrame,
    phase257_scores: pd.DataFrame,
    phase256_scores: pd.DataFrame,
) -> pd.DataFrame:
    if alternative_metrics.empty:
        return pd.DataFrame()
    phase257_cols = [
        column
        for column in (
            "candidate_id",
            "direction",
            "phase256_policy_bucket",
            "phase256_score",
            "phase256_prominence_action",
            "phase256_ready_for_expansion",
            "phase256_adjustment_reason",
            "context_must_not_rescue_bad_count",
            "ema_htf_policy_label",
            "ewo_policy_label",
            "phase257_policy_warnings",
            "phase257_policy_reasons",
            "diagnostic_only",
            "expansion_origin",
        )
        if column in phase257_scores.columns
    ]
    exact_cols = [
        column
        for column in (
            "candidate_id",
            "phase256_policy_bucket",
            "phase256_score",
            "phase256_prominence_action",
            "phase256_ready_for_expansion",
        )
        if column in phase256_scores.columns
    ]
    out = alternative_metrics.copy()
    if phase257_cols:
        out = out.merge(
            phase257_scores[phase257_cols].drop_duplicates("candidate_id"),
            on="candidate_id",
            how="left",
            suffixes=("", "_phase257"),
        )
    if exact_cols:
        exact = phase256_scores[exact_cols].drop_duplicates("candidate_id").rename(
            columns={
                "phase256_policy_bucket": "phase256_policy_bucket_exact",
                "phase256_score": "phase256_score_exact",
                "phase256_prominence_action": "phase256_prominence_action_exact",
                "phase256_ready_for_expansion": "phase256_ready_for_expansion_exact",
            }
        )
        out = out.merge(exact, on="candidate_id", how="left")

    out["phase256_policy_bucket"] = out.get("phase256_policy_bucket_exact", pd.Series(index=out.index)).where(
        out.get("phase256_policy_bucket_exact", pd.Series(index=out.index)).notna(),
        out.get("phase256_policy_bucket", out.get("phase257_policy_bucket")),
    )
    out["phase256_score"] = out.get("phase256_score_exact", pd.Series(index=out.index)).where(
        out.get("phase256_score_exact", pd.Series(index=out.index)).notna(),
        out.get("phase256_score", out.get("phase257_score")),
    )
    for column in ("phase256_prominence_action", "phase256_ready_for_expansion"):
        exact_col = f"{column}_exact"
        if exact_col in out.columns:
            out[column] = out[exact_col].where(out[exact_col].notna(), out.get(column, ""))
    out["phase256_policy_source"] = out.get("phase256_policy_bucket_exact", pd.Series(index=out.index)).apply(
        lambda value: "phase256_exact" if _string(value) else "phase257_phase256_compatible_expansion"
    )
    out["phase256_policy_bucket"] = out["phase256_policy_bucket"].fillna(out.get("phase257_policy_bucket")).fillna(
        "experimental_only"
    )
    out["phase256_score"] = pd.to_numeric(out["phase256_score"], errors="coerce").fillna(
        pd.to_numeric(out.get("phase257_score", pd.Series(index=out.index)), errors="coerce")
    )
    return out


def apply_percentile_fallback(dataset: pd.DataFrame, min_symbol_family_size: int = MIN_SYMBOL_FAMILY_SIZE) -> tuple[pd.DataFrame, pd.DataFrame]:
    if dataset.empty:
        return dataset.copy(), pd.DataFrame()
    out = dataset.copy()
    out["robust_window_prominence_p05_p95"] = pd.to_numeric(out["robust_window_prominence_p05_p95"], errors="coerce")

    family_specs = [
        ("symbol_timeframe_degree", ["symbol", "source_scope", "timeframe", "swing_degree"]),
        ("group_timeframe_degree", ["resolved_market_group", "source_scope", "timeframe", "swing_degree"]),
    ]
    families: list[pd.DataFrame] = []
    for scope, cols in family_specs:
        part = out[out["robust_window_prominence_p05_p95"].notna()].copy()
        summary = (
            part.groupby(cols, dropna=False)["robust_window_prominence_p05_p95"]
            .agg(["count", "median", "min", "max"])
            .reset_index()
        )
        summary.insert(0, "percentile_scope", scope)
        summary = summary.rename(
            columns={
                "count": "family_size",
                "median": "robust_prominence_median",
                "min": "robust_prominence_min",
                "max": "robust_prominence_max",
            }
        )
        families.append(summary)
    family_table = pd.concat(families, ignore_index=True) if families else pd.DataFrame()

    symbol_size = (
        out.groupby(["symbol", "source_scope", "timeframe", "swing_degree"], dropna=False)["robust_window_prominence_p05_p95"]
        .transform(lambda s: int(s.notna().sum()))
        .fillna(0)
    )
    group_size = (
        out.groupby(["resolved_market_group", "source_scope", "timeframe", "swing_degree"], dropna=False)["robust_window_prominence_p05_p95"]
        .transform(lambda s: int(s.notna().sum()))
        .fillna(0)
    )
    out["symbol_timeframe_degree_family_size"] = symbol_size.astype(int)
    out["group_timeframe_degree_family_size"] = group_size.astype(int)

    symbol_pct = pd.to_numeric(out.get("symbol_percentile_robust_prominence"), errors="coerce")
    group_pct = pd.to_numeric(out.get("group_percentile_robust_prominence"), errors="coerce")
    use_symbol = out["symbol_timeframe_degree_family_size"].ge(min_symbol_family_size) & symbol_pct.notna()
    use_group = ~use_symbol & out["group_timeframe_degree_family_size"].gt(0) & group_pct.notna()
    out["percentile_scope_used"] = "not_available"
    out.loc[use_symbol, "percentile_scope_used"] = "symbol_timeframe_degree"
    out.loc[use_group, "percentile_scope_used"] = "group_timeframe_degree"
    out["robust_prominence_percentile"] = pd.NA
    out.loc[use_symbol, "robust_prominence_percentile"] = symbol_pct[use_symbol]
    out.loc[use_group, "robust_prominence_percentile"] = group_pct[use_group]
    out["percentile_family_size"] = 0
    out.loc[use_symbol, "percentile_family_size"] = out.loc[use_symbol, "symbol_timeframe_degree_family_size"]
    out.loc[use_group, "percentile_family_size"] = out.loc[use_group, "group_timeframe_degree_family_size"]
    out["percentile_confidence"] = "not_available"
    out.loc[use_symbol, "percentile_confidence"] = "good"
    out.loc[use_group, "percentile_confidence"] = "low_sample"
    return out, family_table


def classify_prominence(row: pd.Series) -> str:
    if not _boolish(row.get("metrics_available")):
        return "insufficient_prominence_context"
    review_category = _string(row.get("review_category"))
    if review_category not in {"impulse", "near_miss"}:
        return "not_applicable"
    visual = _number(row.get("visual_window_prominence"), _number(row.get("prominence_vs_window"), 0.0))
    robust = _number(row.get("robust_window_prominence_p05_p95"), 0.0)
    percentile = _number(row.get("robust_prominence_percentile"), default=-1.0)
    robust_ratio = _number(row.get("robust_improvement_ratio_p05_p95"), 0.0)
    last_ratio = _number(row.get("last_n_improvement_ratio"), 0.0)
    if visual < LOW_PROMINENCE_THRESHOLD and robust < LOW_PROMINENCE_THRESHOLD and 0 <= percentile < LOW_PERCENTILE_THRESHOLD:
        return "true_low_prominence"
    if visual < LOW_PROMINENCE_THRESHOLD and (
        robust >= LOW_PROMINENCE_THRESHOLD
        or robust_ratio >= ROBUST_IMPROVEMENT_RATIO
        or last_ratio >= ROBUST_IMPROVEMENT_RATIO
    ):
        return "window_distorted_low_prominence"
    if visual < LOW_PROMINENCE_THRESHOLD and robust < LOW_PROMINENCE_THRESHOLD and percentile >= NORMAL_PERCENTILE_THRESHOLD:
        return "symbol_normal_low_prominence"
    if robust >= LOW_PROMINENCE_THRESHOLD and percentile >= NORMAL_PERCENTILE_THRESHOLD:
        return "robust_prominence_confirmed"
    if visual < LOW_PROMINENCE_THRESHOLD:
        return "true_low_prominence"
    return "robust_prominence_confirmed" if robust >= LOW_PROMINENCE_THRESHOLD else "not_applicable"


def add_prominence_diagnostics(dataset: pd.DataFrame) -> pd.DataFrame:
    out = dataset.copy()
    out["phase259_prominence_diagnostic"] = out.apply(classify_prominence, axis=1)
    return out


def _has_context_rescue_risk(row: pd.Series) -> bool:
    warnings = " ".join(
        _string(row.get(column))
        for column in (
            "phase257_policy_warnings",
            "policy_warnings",
            "ema_htf_policy_label",
            "phase256_adjustment_reason",
        )
    ).lower()
    return _boolish(row.get("context_must_not_rescue_bad_count")) or "misleading" in warnings or "context_must_not_rescue" in warnings


def apply_phase259_candidate_policy(dataset: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in dataset.iterrows():
        old_bucket = _string(row.get("phase256_policy_bucket")) or _string(row.get("phase257_policy_bucket")) or "experimental_only"
        old_score = _number(row.get("phase256_score"), _number(row.get("phase257_score"), 0.0))
        diagnostic = _string(row.get("phase259_prominence_diagnostic"))
        source_scope = _string(row.get("source_scope"))
        degree = _string(row.get("swing_degree"))
        review_category = _string(row.get("review_category"))
        group = _string(row.get("resolved_market_group"))
        context_risk = _has_context_rescue_risk(row)
        candidate_bucket = _candidate_bucket_from_baseline(old_bucket)
        delta = 0.0
        ready = "yes" if old_bucket in {"high_quality_structure", "usable_provisional_structure"} else "no"
        reason = "Candidate policy keeps 2.5.6-compatible baseline bucket."
        warning = "2.5.9 is a candidate policy only; it does not replace 2.5.6."

        if diagnostic == "insufficient_prominence_context":
            ready = _string(row.get("phase256_ready_for_expansion")) or ready
            reason = "No OHLC context available; candidate policy preserves 2.5.6-compatible bucket."
        elif diagnostic == "true_low_prominence":
            delta = -8.0
            if old_bucket in {"high_quality_structure", "usable_provisional_structure"} and source_scope == "h4_d1":
                candidate_bucket = "candidate_visual_watchlist_low_prominence"
                ready = "watchlist_only"
                reason = "Robust and percentile metrics confirm low prominence; primary/provisional seed is downgraded to watchlist."
            elif old_bucket == "visual_watchlist_low_prominence":
                ready = "watchlist_only"
                reason = "Low prominence remains confirmed; watchlist is retained."
            else:
                reason = "Low prominence confirmed; no quality upgrade allowed."
        elif diagnostic in {"window_distorted_low_prominence", "symbol_normal_low_prominence"}:
            delta = 8.0 if diagnostic == "window_distorted_low_prominence" else 5.0
            if old_bucket == "exclude_from_guided_search" and source_scope == "h4_d1" and review_category in {"impulse", "near_miss"} and not context_risk:
                candidate_bucket = "candidate_visual_watchlist_low_prominence"
                ready = "watchlist_only"
                reason = (
                    "Robust/percentile prominence suggests the visual window may be unfair; excluded count can move only to non-operational watchlist."
                )
            elif old_bucket == "exclude_from_guided_search":
                reason = "Prominence improves, but exclusion is retained because structure/context is not safe to rescue."
            elif old_bucket == "visual_watchlist_low_prominence":
                ready = "watchlist_only"
                reason = "Window distortion supports watchlist, not a stronger bucket."
            else:
                reason = "Prominence diagnostic supports the existing bucket but does not create a signal."
        elif diagnostic == "robust_prominence_confirmed":
            delta = 3.0
            reason = "Robust prominence confirms existing scale; no automatic bucket upgrade is required."

        if source_scope == "h1_h4":
            if "low_prominence" in diagnostic and old_bucket not in {"exclude_from_guided_search", "experimental_only"}:
                candidate_bucket = "candidate_auxiliary_low_prominence_substructure"
                ready = "auxiliary_only"
            elif old_bucket in {"high_quality_structure", "usable_provisional_structure", "visual_watchlist_low_prominence"}:
                candidate_bucket = "candidate_auxiliary_substructure"
                ready = "auxiliary_only"
            reason += " H1/H4 remains auxiliary, not a primary base."

        if degree == "minor" and candidate_bucket in {"candidate_high_quality_structure", "candidate_usable_provisional_structure"}:
            candidate_bucket = "candidate_auxiliary_substructure"
            ready = "auxiliary_only"
            reason += " Minor degree is substructure."

        if degree == "major" and old_bucket == "exclude_from_guided_search" and candidate_bucket == "candidate_visual_watchlist_low_prominence":
            candidate_bucket = "candidate_auxiliary_substructure"
            ready = "auxiliary_only"
            reason += " Major is treated as context/higher degree, not primary rescue."

        if old_bucket == "exclude_from_guided_search" and candidate_bucket == "candidate_high_quality_structure":
            candidate_bucket = "candidate_visual_watchlist_low_prominence"
            ready = "watchlist_only"
            warning += " Excluded structures are capped below high quality."

        if group == "Metals" and diagnostic in {"window_distorted_low_prominence", "symbol_normal_low_prominence"}:
            warning += " Metals improvement remains diagnostic/watchlist until manual confirmation."

        candidate_score = max(0.0, min(100.0, old_score + delta))
        bucket_change = _bucket_change(old_bucket, candidate_bucket)
        rows.append(
            {
                **row.to_dict(),
                "phase259_candidate_bucket": candidate_bucket,
                "phase259_candidate_score": candidate_score,
                "phase259_score_delta_vs_256": round(candidate_score - old_score, 6),
                "phase259_bucket_change_vs_256": bucket_change,
                "phase259_policy_reason": reason,
                "phase259_policy_warning": warning,
                "phase259_ready_for_next_step": ready,
                "phase259_context_rescue_risk": context_risk,
            }
        )
    return pd.DataFrame(rows)


def build_bucket_changes(policy_scores: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in policy_scores.iterrows():
        old_bucket = _string(row.get("phase256_policy_bucket"))
        new_bucket = _string(row.get("phase259_candidate_bucket"))
        if not new_bucket:
            continue
        change = _string(row.get("phase259_bucket_change_vs_256"))
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": _string(row.get("resolved_market_group")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "review_category": _string(row.get("review_category")),
                "phase256_policy_bucket": old_bucket,
                "phase259_candidate_bucket": new_bucket,
                "phase259_bucket_change_vs_256": change,
                "phase256_score": row.get("phase256_score"),
                "phase259_candidate_score": row.get("phase259_candidate_score"),
                "phase259_score_delta_vs_256": row.get("phase259_score_delta_vs_256"),
                "phase259_prominence_diagnostic": _string(row.get("phase259_prominence_diagnostic")),
                "percentile_scope_used": _string(row.get("percentile_scope_used")),
                "robust_prominence_percentile": row.get("robust_prominence_percentile"),
                "phase259_policy_reason": _string(row.get("phase259_policy_reason")),
                "phase259_policy_warning": _string(row.get("phase259_policy_warning")),
                "chart_path": _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_changes_by_market_group(policy_scores: pd.DataFrame) -> pd.DataFrame:
    if policy_scores.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for group, part in policy_scores.groupby("resolved_market_group", dropna=False):
        total = len(part)
        changes = part["phase259_bucket_change_vs_256"].astype(str)
        rows.append(
            {
                "resolved_market_group": group,
                "total_candidates": total,
                "unchanged": int(changes.eq("unchanged").sum()),
                "upgrades": int(changes.eq("upgrade").sum()),
                "downgrades": int(changes.eq("downgrade").sum()),
                "changed_total": int(changes.ne("unchanged").sum()),
                "changed_pct": round(float(changes.ne("unchanged").sum() / total * 100.0), 4) if total else 0.0,
                "exclude_to_watchlist": int(
                    (
                        part["phase256_policy_bucket"].astype(str).eq("exclude_from_guided_search")
                        & part["phase259_candidate_bucket"].astype(str).eq("candidate_visual_watchlist_low_prominence")
                    ).sum()
                ),
                "candidate_watchlist": int(part["phase259_candidate_bucket"].astype(str).eq("candidate_visual_watchlist_low_prominence").sum()),
                "candidate_high_quality": int(part["phase259_candidate_bucket"].astype(str).eq("candidate_high_quality_structure").sum()),
            }
        )
    return pd.DataFrame(rows)


def _copy_chart(row: pd.Series, output_dir: Path, idx: int) -> str:
    src_value = _string(row.get("chart_path"))
    if not src_value:
        return ""
    src = _resolve_repo_path(src_value)
    if not src.exists():
        return src_value
    group_dir = _slug(_string(row.get("resolved_market_group")) or "unknown")
    dest_dir = output_dir / "charts" / "reviewed_changes" / group_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{idx:03d}_{src.name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return _rel_to_repo(dest)


def build_visual_review_selection(policy_scores: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    if policy_scores.empty:
        return pd.DataFrame()
    candidates = policy_scores.copy()
    candidates["has_chart"] = candidates["chart_path"].map(_path_exists)
    changed = candidates[candidates["phase259_bucket_change_vs_256"].astype(str).ne("unchanged")]
    selected = changed[changed["has_chart"]].copy()
    if len(selected) < 30:
        extras = candidates[
            candidates["has_chart"]
            & candidates["phase259_prominence_diagnostic"].astype(str).isin(
                {"window_distorted_low_prominence", "symbol_normal_low_prominence", "true_low_prominence"}
            )
        ].copy()
        selected = pd.concat([selected, extras], ignore_index=True)
    if len(selected) < 30:
        negatives = candidates[
            candidates["has_chart"]
            & candidates["phase256_policy_bucket"].astype(str).eq("exclude_from_guided_search")
            & candidates["phase259_bucket_change_vs_256"].astype(str).eq("unchanged")
        ].copy()
        selected = pd.concat([selected, negatives], ignore_index=True)
    if selected.empty:
        return pd.DataFrame()
    selected = selected.drop_duplicates("candidate_id").head(40).copy()
    selected["selection_reason"] = selected.apply(
        lambda row: "bucket_changed"
        if _string(row.get("phase259_bucket_change_vs_256")) != "unchanged"
        else _string(row.get("phase259_prominence_diagnostic")) or "negative_control",
        axis=1,
    )
    reviewed_paths: list[str] = []
    for idx, (_, row) in enumerate(selected.iterrows(), start=1):
        reviewed_paths.append(_copy_chart(row, output_dir, idx))
    selected["reviewed_chart_path"] = reviewed_paths
    columns = [
        "candidate_id",
        "selection_reason",
        "resolved_market_group",
        "source_scope",
        "symbol",
        "timeframe",
        "swing_degree",
        "review_category",
        "phase256_policy_bucket",
        "phase259_candidate_bucket",
        "phase259_bucket_change_vs_256",
        "phase259_prominence_diagnostic",
        "visual_window_prominence",
        "robust_window_prominence_p05_p95",
        "robust_prominence_percentile",
        "percentile_scope_used",
        "chart_path",
        "reviewed_chart_path",
    ]
    return selected[[column for column in columns if column in selected.columns]]


def build_visual_review(selection: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in selection.iterrows():
        change = _string(row.get("phase259_bucket_change_vs_256"))
        diagnostic = _string(row.get("phase259_prominence_diagnostic"))
        new_bucket = _string(row.get("phase259_candidate_bucket"))
        old_bucket = _string(row.get("phase256_policy_bucket"))
        if change == "upgrade" and new_bucket == "candidate_visual_watchlist_low_prominence" and diagnostic == "window_distorted_low_prominence":
            visual_verdict = "watchlist_reasonable"
            robust_verdict = "robust_metric_helpful"
            percentile_verdict = "percentile_helpful"
        elif change == "upgrade" and old_bucket == "exclude_from_guided_search":
            visual_verdict = "manual_review_needed"
            robust_verdict = "robust_metric_not_enough"
            percentile_verdict = "percentile_low_sample"
        elif diagnostic == "true_low_prominence":
            visual_verdict = "should_remain_excluded" if old_bucket == "exclude_from_guided_search" else "change_correct"
            robust_verdict = "robust_metric_not_enough"
            percentile_verdict = "percentile_helpful"
        elif diagnostic == "insufficient_prominence_context":
            visual_verdict = "manual_review_needed"
            robust_verdict = "metric_unavailable"
            percentile_verdict = "not_available"
        else:
            visual_verdict = "change_correct" if change != "unchanged" else "should_remain_excluded"
            robust_verdict = "robust_metric_helpful" if diagnostic in {"window_distorted_low_prominence", "robust_prominence_confirmed"} else "robust_metric_not_enough"
            percentile_verdict = "percentile_helpful" if _string(row.get("percentile_scope_used")) != "not_available" else "not_available"
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": _string(row.get("resolved_market_group")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "phase256_policy_bucket": old_bucket,
                "phase259_candidate_bucket": new_bucket,
                "phase259_bucket_change_vs_256": change,
                "phase259_prominence_diagnostic": diagnostic,
                "phase259_visual_verdict": visual_verdict,
                "robust_metric_verdict": robust_verdict,
                "percentile_verdict": percentile_verdict,
                "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
                "notes": "Heuristic visual audit selection; 2.5.9 remains a candidate policy trial.",
            }
        )
    return pd.DataFrame(rows)


def build_policy_risks(policy_scores: pd.DataFrame, visual_review: pd.DataFrame) -> pd.DataFrame:
    high_from_exclude = policy_scores[
        policy_scores["phase256_policy_bucket"].astype(str).eq("exclude_from_guided_search")
        & policy_scores["phase259_candidate_bucket"].astype(str).eq("candidate_high_quality_structure")
    ]
    upgrades = policy_scores[policy_scores["phase259_bucket_change_vs_256"].astype(str).eq("upgrade")]
    too_lenient = visual_review[visual_review.get("phase259_visual_verdict", pd.Series(dtype=str)).astype(str).eq("change_too_lenient")]
    rows = [
        {
            "risk": "excluded_count_promoted_to_high_quality",
            "risk_level": "high" if len(high_from_exclude) else "low",
            "case_count": int(len(high_from_exclude)),
            "mitigation": "Policy cap forbids direct jump from exclude to high quality.",
        },
        {
            "risk": "too_many_bucket_upgrades",
            "risk_level": "medium" if len(upgrades) > 20 else "low",
            "case_count": int(len(upgrades)),
            "mitigation": "Use visual review before adopting candidate policy.",
        },
        {
            "risk": "visual_review_too_lenient",
            "risk_level": "high" if len(too_lenient) else "low",
            "case_count": int(len(too_lenient)),
            "mitigation": "Do not adopt candidate policy if too-lenient cases appear.",
        },
        {
            "risk": "low_sample_symbol_percentiles",
            "risk_level": "medium",
            "case_count": int(policy_scores["percentile_confidence"].astype(str).eq("low_sample").sum()),
            "mitigation": "Fallback percentiles remain diagnostic until larger sample exists.",
        },
    ]
    return pd.DataFrame(rows)


def build_phase2510_recommendation(policy_scores: pd.DataFrame, changes_by_group: pd.DataFrame, visual_review: pd.DataFrame) -> pd.DataFrame:
    upgrades = int(policy_scores["phase259_bucket_change_vs_256"].astype(str).eq("upgrade").sum()) if not policy_scores.empty else 0
    high_from_exclude = int(
        (
            policy_scores["phase256_policy_bucket"].astype(str).eq("exclude_from_guided_search")
            & policy_scores["phase259_candidate_bucket"].astype(str).eq("candidate_high_quality_structure")
        ).sum()
    ) if not policy_scores.empty else 0
    too_lenient = int(visual_review.get("phase259_visual_verdict", pd.Series(dtype=str)).astype(str).eq("change_too_lenient").sum()) if not visual_review.empty else 0
    metals_upgrades = 0
    if not policy_scores.empty:
        metals_upgrades = int(
            (
                policy_scores["resolved_market_group"].astype(str).eq("Metals")
                & policy_scores["phase259_bucket_change_vs_256"].astype(str).eq("upgrade")
            ).sum()
        )
    if high_from_exclude or too_lenient:
        recommendation = "keep_phase256_policy"
        reason = "Candidate policy produced unsafe visual promotion risk."
    elif upgrades:
        recommendation = "adopt_robust_prominence_candidate_for_next_phase"
        reason = "Robust prominence creates capped watchlist improvements without replacing 2.5.6."
    else:
        recommendation = "adopt_robust_prominence_as_diagnostic_only"
        reason = "Robust prominence is useful diagnostically but does not change buckets in this sample."
    return pd.DataFrame(
        [
            {
                "phase2510_recommendation": recommendation,
                "phase256_remains_official": True,
                "phase259_candidate_policy_available": True,
                "total_candidates": int(len(policy_scores)),
                "total_upgrades": upgrades,
                "metals_upgrades": metals_upgrades,
                "excluded_to_high_quality": high_from_exclude,
                "visual_too_lenient_cases": too_lenient,
                "reason": reason,
                "do_not_do": "Do not convert robust prominence, EWO, EMA or HTF into signals or operative filters.",
            }
        ]
    )


def build_user_review_if_any(visual_review: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not visual_review.empty:
        needs = visual_review[
            visual_review["phase259_visual_verdict"].astype(str).isin({"manual_review_needed", "change_too_lenient"})
        ].copy()
        for _, row in needs.head(12).iterrows():
            rows.append(
                {
                    "candidate_id": _string(row.get("candidate_id")),
                    "review_reason": _string(row.get("phase259_visual_verdict")),
                    "priority": "medium" if _string(row.get("phase259_visual_verdict")) == "change_too_lenient" else "low",
                    "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
                    "notes": "Only needed before adopting 2.5.9 as active candidate policy.",
                }
            )
    if not rows:
        rows.append(
            {
                "candidate_id": "",
                "review_reason": "no_blocking_manual_review",
                "priority": "none",
                "reviewed_chart_path": "",
                "notes": "No imprescindible manual review before closing 2.5.9.",
            }
        )
    return pd.DataFrame(rows)


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
        labels.append(path.name[:72])
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 520, 60 + rows * 360), "white")
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
    policy_scores: pd.DataFrame,
    changes_by_group: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> None:
    rec = recommendation.iloc[0].to_dict() if not recommendation.empty else {}
    summary = (
        policy_scores["phase259_candidate_bucket"].value_counts().rename_axis("phase259_candidate_bucket").reset_index(name="count")
        if not policy_scores.empty
        else pd.DataFrame()
    )
    diagnostics = (
        policy_scores["phase259_prominence_diagnostic"].value_counts().rename_axis("phase259_prominence_diagnostic").reset_index(name="count")
        if not policy_scores.empty
        else pd.DataFrame()
    )
    lines = [
        "# WaveCount Phase 2.5.9 - Robust Prominence Policy Trial",
        "",
        "Fase metodologica candidata. No sustituye la politica 2.5.6, no recalcula conteos base y no genera senales.",
        "",
        "## Decision",
        "",
        f"- recommendation: `{_string(rec.get('phase2510_recommendation'))}`",
        f"- phase256_remains_official: `{rec.get('phase256_remains_official', True)}`",
        f"- total_upgrades: `{rec.get('total_upgrades', 0)}`",
        f"- metals_upgrades: `{rec.get('metals_upgrades', 0)}`",
        "",
        "## Buckets candidatos",
        "",
        _frame_to_markdown(summary),
        "",
        "## Diagnosticos de prominencia",
        "",
        _frame_to_markdown(diagnostics),
        "",
        "## Cambios por grupo",
        "",
        _frame_to_markdown(changes_by_group),
        "",
        "## Lectura",
        "",
        "- Ningun excluido puede subir directamente a `candidate_high_quality_structure`.",
        "- Las mejoras por ventana robusta se limitan a watchlist/revision.",
        "- H1/H4 sigue como auxiliar aunque la metrica robusta mejore.",
        "- 2.5.6 sigue siendo la politica oficial.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_5_9_ROBUST_PROMINENCE_POLICY_TRIAL.md").write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )


def run(
    *,
    phase258_dir: Path = DEFAULT_PHASE258_DIR,
    phase257_dir: Path = DEFAULT_PHASE257_DIR,
    phase256_dir: Path = DEFAULT_PHASE256_DIR,
    phase256b_dir: Path = DEFAULT_PHASE256B_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    alternative_metrics = _read_csv(phase258_dir / "tables" / "prominence_alternative_metrics.csv")
    phase257_scores = _read_csv(phase257_dir / "tables" / "phase257_policy_scores.csv")
    phase257_visual_review = _read_csv(phase257_dir / "tables" / "phase257_visual_review.csv")
    phase256_scores = _read_csv(phase256_dir / "tables" / "phase256_policy_scores.csv")
    phase256_watchlist = _read_csv(phase256_dir / "tables" / "phase256_watchlist_cases.csv")
    phase256_exclusions = _read_csv(phase256_dir / "tables" / "phase256_exclusions.csv")
    market_mapping = _read_csv(phase256b_dir / "tables" / "market_group_mapping_evidence.csv")
    sql_categories = _read_csv(phase256b_dir / "tables" / "sql_market_categories.csv")

    dataset = prepare_phase259_dataset(alternative_metrics, phase257_scores, phase256_scores)
    dataset, percentile_families = apply_percentile_fallback(dataset)
    diagnostics = add_prominence_diagnostics(dataset)
    policy_scores = apply_phase259_candidate_policy(diagnostics)
    bucket_changes = build_bucket_changes(policy_scores)
    changes_by_group = build_changes_by_market_group(policy_scores)
    metals_changes = bucket_changes[bucket_changes["resolved_market_group"].astype(str).eq("Metals")].copy() if not bucket_changes.empty else pd.DataFrame()
    visual_selection = build_visual_review_selection(policy_scores, output_dir)
    visual_review = build_visual_review(visual_selection)
    policy_risks = build_policy_risks(policy_scores, visual_review)
    recommendation = build_phase2510_recommendation(policy_scores, changes_by_group, visual_review)
    user_review = build_user_review_if_any(visual_review)

    outputs = {
        "phase259_prominence_dataset": dataset,
        "phase259_percentile_families": percentile_families,
        "phase259_prominence_diagnostics": diagnostics,
        "phase259_candidate_policy_scores": policy_scores,
        "phase256_vs_phase259_bucket_changes": bucket_changes,
        "phase259_changes_by_market_group": changes_by_group,
        "phase259_metals_changes": metals_changes,
        "phase259_visual_review_selection": visual_selection,
        "phase259_visual_review": visual_review,
        "phase259_policy_risks": policy_risks,
        "phase2510_recommendation": recommendation,
        "user_review_if_any": user_review,
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        if any("path" in column.lower() for column in frame.columns) or name in {
            "phase2510_recommendation",
            "phase259_changes_by_market_group",
            "phase259_policy_risks",
        }:
            _write_markdown_index(path, name.replace("_", " ").title())

    for group in INCLUDED_GROUPS:
        rows = visual_selection[visual_selection.get("resolved_market_group", pd.Series(dtype=str)).astype(str).eq(group)]
        paths = [_resolve_repo_path(_string(path)) for path in rows.get("reviewed_chart_path", pd.Series(dtype=str)).dropna().astype(str) if _string(path)]
        _make_contact_sheet(
            paths,
            output_dir / "charts" / "reviewed_changes" / f"{_slug(group)}_contact_sheet.png",
            title=f"WaveCount 2.5.9 robust prominence changes - {group}",
        )

    build_report(output_dir, policy_scores, changes_by_group, recommendation)

    run_meta = {
        "phase": "2.5.9",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase258_dir": _rel_to_repo(phase258_dir),
            "phase257_dir": _rel_to_repo(phase257_dir),
            "phase256_dir": _rel_to_repo(phase256_dir),
            "phase256b_dir": _rel_to_repo(phase256b_dir),
            "alternative_metrics_rows": int(len(alternative_metrics)),
            "phase257_rows": int(len(phase257_scores)),
            "phase257_visual_review_rows": int(len(phase257_visual_review)),
            "phase256_rows": int(len(phase256_scores)),
            "phase256_watchlist_rows": int(len(phase256_watchlist)),
            "phase256_exclusion_rows": int(len(phase256_exclusions)),
            "market_mapping_rows": int(len(market_mapping)),
            "sql_category_rows": int(len(sql_categories)),
        },
        "min_symbol_family_size": MIN_SYMBOL_FAMILY_SIZE,
        "low_prominence_threshold": LOW_PROMINENCE_THRESHOLD,
        "rules_changed": False,
        "phase256_policy_changed": False,
        "signals_generated": False,
        "backtests_executed": False,
        "base_counts_recomputed": False,
        "candidate_policy_only": True,
        "runtime_seconds": round(perf_counter() - started, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount phase 2.5.9 robust prominence policy trial artifacts.")
    parser.add_argument("--phase258-dir", type=Path, default=DEFAULT_PHASE258_DIR)
    parser.add_argument("--phase257-dir", type=Path, default=DEFAULT_PHASE257_DIR)
    parser.add_argument("--phase256-dir", type=Path, default=DEFAULT_PHASE256_DIR)
    parser.add_argument("--phase256b-dir", type=Path, default=DEFAULT_PHASE256B_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = run(
        phase258_dir=args.phase258_dir,
        phase257_dir=args.phase257_dir,
        phase256_dir=args.phase256_dir,
        phase256b_dir=args.phase256b_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
