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
DEFAULT_PHASE250_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_0_guided_context_score_2026-05-24"
)
DEFAULT_PHASE251_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_1_guided_impulse_profile_2026-05-24"
)
DEFAULT_PHASE252_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_2_guided_impulse_expansion_2026-05-24"
)
DEFAULT_PHASE252B_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_2b_h1_h4_aux_expansion_2026-05-24"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_3_descriptive_stats_2026-05-24"
)

PALETTE = {
    "yes": "#2f855a",
    "yes_aux": "#2f855a",
    "near_miss": "#d69e2e",
    "near_miss_aux": "#d69e2e",
    "no": "#718096",
    "problem": "#c53030",
    "context": "#2b6cb0",
    "experimental": "#805ad5",
    "neutral": "#4a5568",
    "ready_for_soft_rule": "#2f855a",
    "ready_as_context_only": "#2b6cb0",
    "auxiliary_only": "#d69e2e",
    "exclude": "#c53030",
}


EXPECTED_TABLES = (
    ("2.5.0", "guided_context_candidates.csv", "principal_context"),
    ("2.5.0", "guided_quality_summary.csv", "summary"),
    ("2.5.0", "ewo_role_context.csv", "diagnostic_ewo"),
    ("2.5.0", "ema_htf_context_policy.csv", "diagnostic_context"),
    ("2.5.0", "phase251_search_readiness.csv", "readiness"),
    ("2.5.1", "guided_impulse_profile_matches.csv", "profile_application"),
    ("2.5.1", "guided_impulse_near_misses.csv", "profile_near_miss"),
    ("2.5.1", "guided_impulse_exclusions_check.csv", "profile_exclusion"),
    ("2.5.2", "guided_impulse_expanded_candidates.csv", "principal_h4_d1"),
    ("2.5.2", "guided_impulse_expanded_matches.csv", "principal_h4_d1"),
    ("2.5.2", "guided_impulse_expanded_near_misses.csv", "principal_h4_d1"),
    ("2.5.2", "guided_impulse_expanded_negatives.csv", "principal_h4_d1"),
    ("2.5.2", "visual_expansion_review.csv", "principal_h4_d1_review"),
    ("2.5.2", "ewo_expansion_review.csv", "summary_ewo"),
    ("2.5.2", "ema_htf_expansion_review.csv", "summary_context"),
    ("2.5.2", "profile_false_positive_risks.csv", "risk"),
    ("2.5.2b", "h1_h4_aux_candidates.csv", "auxiliary_h1_h4"),
    ("2.5.2b", "h1_h4_aux_matches.csv", "auxiliary_h1_h4"),
    ("2.5.2b", "h1_h4_aux_near_misses.csv", "auxiliary_h1_h4"),
    ("2.5.2b", "h1_h4_aux_negatives.csv", "auxiliary_h1_h4"),
    ("2.5.2b", "prominence_diagnostics.csv", "diagnostic_prominence"),
    ("2.5.2b", "h4_suspicious_scale_cases.csv", "diagnostic_prominence"),
    ("2.5.2b", "aus200_h4_case_review.csv", "specific_case"),
    ("2.5.2b", "visual_aux_review.csv", "auxiliary_h1_h4_review"),
    ("2.5.2b", "ewo_aux_review.csv", "summary_ewo"),
    ("2.5.2b", "ema_htf_aux_review.csv", "summary_context"),
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


def _value_counts(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=["label", "case_count", "share_pct"])
    counts = frame[column].fillna("missing").replace("", "missing").value_counts(dropna=False)
    total = int(counts.sum())
    return pd.DataFrame(
        [
            {
                "label": str(label),
                "case_count": int(count),
                "share_pct": round((int(count) / total * 100.0) if total else 0.0, 2),
            }
            for label, count in counts.items()
        ]
    )


def _add_metric_counts(frame: pd.DataFrame, scope: str, metric: str, column: str) -> pd.DataFrame:
    counts = _value_counts(frame, column)
    if counts.empty:
        return counts.assign(scope=scope, metric=metric)[["scope", "metric", "label", "case_count", "share_pct"]]
    counts.insert(0, "metric", metric)
    counts.insert(0, "scope", scope)
    return counts[["scope", "metric", "label", "case_count", "share_pct"]]


def _path_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if "path" in column.lower()]


def _image_refs(frame: pd.DataFrame) -> list[str]:
    refs: list[str] = []
    for column in _path_columns(frame):
        for value in frame[column].dropna().tolist():
            text = _string(value)
            if text.lower().endswith(".png"):
                refs.append(text)
    return refs


def _missing_image_refs(frame: pd.DataFrame) -> list[str]:
    return sorted({value for value in _image_refs(frame) if not _resolve_repo_path(value).exists()})


def _phase_dir(phase: str, phase250_dir: Path, phase251_dir: Path, phase252_dir: Path, phase252b_dir: Path) -> Path:
    if phase == "2.5.0":
        return phase250_dir
    if phase == "2.5.1":
        return phase251_dir
    if phase == "2.5.2":
        return phase252_dir
    if phase == "2.5.2b":
        return phase252b_dir
    raise ValueError(f"unknown phase {phase}")


def build_dataset_inventory(
    phase250_dir: Path,
    phase251_dir: Path,
    phase252_dir: Path,
    phase252b_dir: Path,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for phase, table_name, role in EXPECTED_TABLES:
        path = _phase_dir(phase, phase250_dir, phase251_dir, phase252_dir, phase252b_dir) / "tables" / table_name
        frame = _read_csv(path)
        columns = list(frame.columns)
        refs = _image_refs(frame)
        missing = _missing_image_refs(frame)
        values = " ".join(frame.get(column, pd.Series(dtype=str)).astype(str).head(200).tolist() for column in [])
        rows.append(
            {
                "phase": phase,
                "table": table_name,
                "path": _rel_to_repo(path),
                "exists": path.exists(),
                "rows": int(len(frame)),
                "columns": int(len(columns)),
                "key_columns": "|".join(columns[:12]),
                "contains_image_paths": bool(refs),
                "image_ref_count": int(len(refs)),
                "missing_image_ref_count": int(len(missing)),
                "contains_h4_d1": bool(
                    ("timeframe" in frame.columns and frame["timeframe"].astype(str).eq("H4").any())
                    or ("htf_timeframe" in frame.columns and frame["htf_timeframe"].astype(str).eq("D1").any())
                    or "h4_d1" in role
                ),
                "contains_h1_h4": bool(
                    ("timeframe" in frame.columns and frame["timeframe"].astype(str).eq("H1").any())
                    or ("htf_timeframe" in frame.columns and frame["htf_timeframe"].astype(str).eq("H4").any())
                    or "h1_h4" in role
                ),
                "contains_abc_partial_negative": bool(
                    "structure_type" in frame.columns
                    and frame["structure_type"].astype(str).str.contains("abc|partial|invalid", case=False, na=False).any()
                ),
                "dataset_role": role,
                "legacy_status": "current_input",
            }
        )
    return pd.DataFrame(rows)


def _normalized_scope_frame(frame: pd.DataFrame, source_scope: str, profile_column: str, score_column: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    data["source_scope"] = source_scope
    data["profile_class"] = data.get(profile_column, pd.Series(["missing"] * len(data))).fillna("missing").astype(str)
    data["profile_score"] = pd.to_numeric(data.get(score_column, pd.Series([0] * len(data))), errors="coerce").fillna(0)
    return data


def build_classification_stats(h4: pd.DataFrame, h1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    h4_parts = [
        _add_metric_counts(h4, "h4_d1", "profile_class", "matches_guided_impulse_profile"),
        _add_metric_counts(h4, "h4_d1", "visual_status", "visual_expansion_status"),
        _add_metric_counts(h4, "h4_d1", "near_miss_reason", "near_miss_reason"),
        _add_metric_counts(h4, "h4_d1", "phase253_action", "phase253_candidate_action"),
        _add_metric_counts(h4, "h4_d1", "swing_degree", "swing_degree"),
    ]
    h1_parts = [
        _add_metric_counts(h1, "h1_h4", "profile_class", "matches_h1_h4_aux_profile"),
        _add_metric_counts(h1, "h1_h4", "visual_status", "visual_aux_status"),
        _add_metric_counts(h1, "h1_h4", "near_miss_reason", "aux_near_miss_reason"),
        _add_metric_counts(h1, "h1_h4", "scale_fit_label", "scale_fit_label"),
        _add_metric_counts(h1, "h1_h4", "swing_degree", "swing_degree"),
    ]
    return pd.concat(h4_parts, ignore_index=True), pd.concat(h1_parts, ignore_index=True)


def build_group_symbol_stats(h4: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat(
        [
            _normalized_scope_frame(h4, "h4_d1", "matches_guided_impulse_profile", "guided_profile_match_score"),
            _normalized_scope_frame(h1, "h1_h4", "matches_h1_h4_aux_profile", "aux_profile_match_score"),
        ],
        ignore_index=True,
    )
    if combined.empty:
        return pd.DataFrame()
    rows = []
    for keys, part in combined.groupby(["source_scope", "group", "symbol", "timeframe"], dropna=False):
        source_scope, group, symbol, timeframe = keys
        rows.append(
            {
                "source_scope": source_scope,
                "group": group,
                "symbol": symbol,
                "timeframe": timeframe,
                "candidate_count": int(len(part)),
                "yes_like_count": int(part["profile_class"].isin(["yes", "yes_aux"]).sum()),
                "near_miss_count": int(part["profile_class"].isin(["near_miss", "near_miss_aux"]).sum()),
                "no_count": int(part["profile_class"].eq("no").sum()),
                "avg_profile_score": round(float(part["profile_score"].mean()), 2),
                "ewo_support_count": int(part.get("ewo_helpfulness", pd.Series(dtype=str)).astype(str).str.contains("supports", na=False).sum()),
                "ema_htf_support_count": int(
                    part.get("ema_htf_helpfulness", pd.Series(dtype=str)).astype(str).str.contains("supports|explains", na=False).sum()
                ),
                "scale_problem_count": int(
                    part.get("scale_fit_label", pd.Series(dtype=str))
                    .astype(str)
                    .isin(["too_small_for_timeframe", "better_as_lower_tf_substructure", "ambiguous_scale"])
                    .sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_degree_stats(h4: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat(
        [
            _normalized_scope_frame(h4, "h4_d1", "matches_guided_impulse_profile", "guided_profile_match_score"),
            _normalized_scope_frame(h1, "h1_h4", "matches_h1_h4_aux_profile", "aux_profile_match_score"),
        ],
        ignore_index=True,
    )
    if combined.empty:
        return pd.DataFrame()
    rows = []
    for keys, part in combined.groupby(["source_scope", "timeframe", "swing_degree"], dropna=False):
        source_scope, timeframe, degree = keys
        rows.append(
            {
                "source_scope": source_scope,
                "timeframe": timeframe,
                "swing_degree": degree,
                "candidate_count": int(len(part)),
                "yes_like_count": int(part["profile_class"].isin(["yes", "yes_aux"]).sum()),
                "near_miss_count": int(part["profile_class"].isin(["near_miss", "near_miss_aux"]).sum()),
                "no_count": int(part["profile_class"].eq("no").sum()),
                "yes_like_share_pct": round(float(part["profile_class"].isin(["yes", "yes_aux"]).mean() * 100), 2),
                "avg_profile_score": round(float(part["profile_score"].mean()), 2),
            }
        )
    return pd.DataFrame(rows)


def build_prominence_stats(prominence: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if prominence.empty:
        return pd.DataFrame(), pd.DataFrame()
    data = prominence.copy()
    for column in ("prominence_vs_window", "duration_vs_window", "move_prominence_vs_window"):
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    rows = []
    for keys, part in data.groupby(["source_scope", "timeframe", "swing_degree", "scale_fit_label"], dropna=False):
        source_scope, timeframe, degree, label = keys
        rows.append(
            {
                "source_scope": source_scope,
                "timeframe": timeframe,
                "swing_degree": degree,
                "scale_fit_label": label,
                "case_count": int(len(part)),
                "prominence_mean": round(float(part["prominence_vs_window"].mean()), 4),
                "prominence_median": round(float(part["prominence_vs_window"].median()), 4),
                "duration_mean": round(float(part["duration_vs_window"].mean()), 4),
                "duration_median": round(float(part["duration_vs_window"].median()), 4),
            }
        )
    problem_labels = {
        "too_small_for_timeframe",
        "better_as_lower_tf_substructure",
        "ambiguous_scale",
        "low_prominence_vs_window",
    }
    problems = data[data["scale_fit_label"].astype(str).isin(problem_labels)].copy()
    return pd.DataFrame(rows), problems


def build_ewo_stats(h4: pd.DataFrame, h1: pd.DataFrame, ewo250: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, frame, profile_column in (
        ("h4_d1_expansion", h4, "matches_guided_impulse_profile"),
        ("h1_h4_auxiliary", h1, "matches_h1_h4_aux_profile"),
    ):
        if frame.empty or "ewo_helpfulness" not in frame.columns:
            continue
        grouped = frame.groupby(["ewo_helpfulness", profile_column], dropna=False).size().reset_index(name="case_count")
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "source_scope": scope,
                    "ewo_metric": "ewo_helpfulness",
                    "ewo_label": _string(row.get("ewo_helpfulness")),
                    "profile_class": _string(row.get(profile_column)),
                    "case_count": int(row.get("case_count")),
                }
            )
    if not ewo250.empty and "ewo_role_support" in ewo250.columns:
        grouped = ewo250.groupby(["ewo_role_support", "guided_quality_bucket"], dropna=False).size().reset_index(name="case_count")
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "source_scope": "phase2_5_0_all_candidates",
                    "ewo_metric": "ewo_role_support",
                    "ewo_label": _string(row.get("ewo_role_support")),
                    "profile_class": _string(row.get("guided_quality_bucket")),
                    "case_count": int(row.get("case_count")),
                }
            )
    return pd.DataFrame(rows)


def build_ema_htf_stats(h4: pd.DataFrame, h1: pd.DataFrame, context250: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, frame, profile_column in (
        ("h4_d1_expansion", h4, "matches_guided_impulse_profile"),
        ("h1_h4_auxiliary", h1, "matches_h1_h4_aux_profile"),
    ):
        if frame.empty or "ema_htf_helpfulness" not in frame.columns:
            continue
        grouped = frame.groupby(["ema_htf_helpfulness", profile_column], dropna=False).size().reset_index(name="case_count")
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "source_scope": scope,
                    "context_metric": "ema_htf_helpfulness",
                    "context_label": _string(row.get("ema_htf_helpfulness")),
                    "profile_class": _string(row.get(profile_column)),
                    "case_count": int(row.get("case_count")),
                }
            )
    if not context250.empty and "htf_ltf_alignment_label" in context250.columns:
        grouped = context250.groupby(["htf_ltf_alignment_label", "guided_quality_bucket"], dropna=False).size().reset_index(name="case_count")
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "source_scope": "phase2_5_0_all_candidates",
                    "context_metric": "htf_ltf_alignment_label",
                    "context_label": _string(row.get("htf_ltf_alignment_label")),
                    "profile_class": _string(row.get("guided_quality_bucket")),
                    "case_count": int(row.get("case_count")),
                }
            )
    return pd.DataFrame(rows)


def build_context_misleading_cases(h4: pd.DataFrame, h1: pd.DataFrame, false_positive_risks: pd.DataFrame) -> pd.DataFrame:
    frames = []
    if not h4.empty:
        mask = (
            h4.get("ema_htf_helpfulness", pd.Series([""] * len(h4))).astype(str).eq("misleading")
            | h4.get("visual_expansion_status", pd.Series([""] * len(h4))).astype(str).eq("context_misleading")
            | h4.get("visual_expansion_status", pd.Series([""] * len(h4))).astype(str).eq("false_positive_risk")
            | h4.get("near_miss_reason", pd.Series([""] * len(h4))).astype(str).eq("context_conflict")
        )
        tmp = h4[mask].copy()
        tmp["source_scope"] = "h4_d1"
        frames.append(tmp)
    if not h1.empty:
        mask = (
            h1.get("ema_htf_helpfulness", pd.Series([""] * len(h1))).astype(str).eq("misleading")
            | h1.get("visual_aux_status", pd.Series([""] * len(h1))).astype(str).eq("context_conflict")
            | h1.get("aux_near_miss_reason", pd.Series([""] * len(h1))).astype(str).eq("context_conflict")
        )
        tmp = h1[mask].copy()
        tmp["source_scope"] = "h1_h4"
        frames.append(tmp)
    if not false_positive_risks.empty:
        tmp = false_positive_risks.copy()
        tmp["source_scope"] = tmp.get("source_scope", "h4_d1_false_positive_risk")
        frames.append(tmp)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates("candidate_id")
    keep = [
        "source_scope",
        "candidate_id",
        "group",
        "symbol",
        "timeframe",
        "swing_degree",
        "matches_guided_impulse_profile",
        "matches_h1_h4_aux_profile",
        "near_miss_reason",
        "aux_near_miss_reason",
        "visual_expansion_status",
        "visual_aux_status",
        "ema_htf_helpfulness",
        "ewo_helpfulness",
        "reviewed_chart_path",
        "chart_path",
        "visual_notes",
    ]
    return out[[column for column in keep if column in out.columns]]


def build_user_review_table(context_misleading_cases: pd.DataFrame, prominence_problem_cases: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in context_misleading_cases.head(8).iterrows():
        rows.append(
            {
                "review_reason": "context_misleading_or_conflict",
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "profile_class": _string(row.get("matches_guided_impulse_profile"))
                or _string(row.get("matches_h1_h4_aux_profile")),
                "diagnostic_label": _string(row.get("visual_expansion_status"))
                or _string(row.get("visual_aux_status"))
                or _string(row.get("ema_htf_helpfulness")),
                "notes": _string(row.get("visual_notes")),
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
            }
        )
    for _, row in prominence_problem_cases.head(8).iterrows():
        rows.append(
            {
                "review_reason": "prominence_or_scale_problem",
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "profile_class": "",
                "diagnostic_label": _string(row.get("scale_fit_label")),
                "notes": _string(row.get("scale_notes")),
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "review_reason",
                "candidate_id",
                "source_scope",
                "symbol",
                "timeframe",
                "swing_degree",
                "profile_class",
                "diagnostic_label",
                "notes",
                "chart_path",
            ]
        )
    return pd.DataFrame(rows).drop_duplicates("candidate_id")


def build_phase254_readiness_matrix(
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    prominence_problems: pd.DataFrame,
    ewo_stats: pd.DataFrame,
    ema_htf_stats: pd.DataFrame,
) -> pd.DataFrame:
    h4_yes = int(h4.get("matches_guided_impulse_profile", pd.Series(dtype=str)).astype(str).eq("yes").sum())
    h4_near = int(h4.get("matches_guided_impulse_profile", pd.Series(dtype=str)).astype(str).eq("near_miss").sum())
    h1_yes = int(h1.get("matches_h1_h4_aux_profile", pd.Series(dtype=str)).astype(str).eq("yes_aux").sum())
    h1_near = int(h1.get("matches_h1_h4_aux_profile", pd.Series(dtype=str)).astype(str).eq("near_miss_aux").sum())
    scale_problem_count = int(len(prominence_problems))
    ewo_support = int(ewo_stats["case_count"][ewo_stats["ewo_label"].astype(str).str.contains("supports", na=False)].sum()) if not ewo_stats.empty else 0
    context_support = (
        int(ema_htf_stats["case_count"][ema_htf_stats["context_label"].astype(str).str.contains("supports|explains", na=False)].sum())
        if not ema_htf_stats.empty
        else 0
    )
    rows = [
        {
            "component": "H4/D1 intermediate profile",
            "ready_status": "ready_for_soft_rule",
            "evidence_summary": f"{h4_yes} yes, {h4_near} near-misses in controlled H4/D1 expansion.",
            "risk_if_used_wrong": "Could be misread as trading signal instead of structural quality filter.",
            "recommended_phase254_action": "formalize as primary descriptive profile with no execution output",
        },
        {
            "component": "H1/H4 auxiliary profile",
            "ready_status": "auxiliary_only",
            "evidence_summary": f"{h1_yes} yes_aux and {h1_near} near_miss_aux; useful as zoom/substructure.",
            "risk_if_used_wrong": "Could displace H4/D1 and reintroduce micro counts.",
            "recommended_phase254_action": "keep as auxiliary zoom and comparison layer",
        },
        {
            "component": "prominence/size penalty",
            "ready_status": "ready_for_soft_rule",
            "evidence_summary": f"{scale_problem_count} prominence/scale problem cases detected.",
            "risk_if_used_wrong": "A hard threshold could reject valid compact impulses.",
            "recommended_phase254_action": "add soft penalty, especially for too_small_for_timeframe and short duration",
        },
        {
            "component": "EWO role support",
            "ready_status": "ready_as_context_only",
            "evidence_summary": f"{ewo_support} rows show EWO support-like labels across reviewed sources.",
            "risk_if_used_wrong": "Absolute thresholds or autonomous labels would overfit momentum noise.",
            "recommended_phase254_action": "keep relative wave-role context; leave EWO+SVM as future experimental work",
        },
        {
            "component": "EMA/HTF context",
            "ready_status": "ready_as_context_only",
            "evidence_summary": f"{context_support} rows show support/explanation context labels.",
            "risk_if_used_wrong": "HTF lag could invalidate good transitions or rescue bad counts.",
            "recommended_phase254_action": "use as soft regime/ambiguity filter, not hard validation",
        },
        {
            "component": "ABC contextual",
            "ready_status": "experimental",
            "evidence_summary": "ABC requires parent context; isolated ABC remains unsafe.",
            "risk_if_used_wrong": "Impulses can be mislabeled as corrections.",
            "recommended_phase254_action": "keep out of impulse profile; use only contextual corrections with parent",
        },
        {
            "component": "partial 1-2-3",
            "ready_status": "ready_as_context_only",
            "evidence_summary": "Partials remain provisional and require post-3 quality checks.",
            "risk_if_used_wrong": "Three alternating swings can be noise or a prior 4-5.",
            "recommended_phase254_action": "allow only provisional context, not profile seeds",
        },
        {
            "component": "major context",
            "ready_status": "ready_as_context_only",
            "evidence_summary": "Major can be higher-degree operable context but is not the base profile.",
            "risk_if_used_wrong": "Too coarse for candidate search if treated as primary everywhere.",
            "recommended_phase254_action": "use to frame H4/D1 intermediate structures",
        },
        {
            "component": "minor substructure",
            "ready_status": "auxiliary_only",
            "evidence_summary": "Minor repeatedly appears as useful substructure/near-miss, not primary base.",
            "risk_if_used_wrong": "Can create micro-Elliott counts inside lateral movement.",
            "recommended_phase254_action": "keep as substructure or negative/near-miss evidence",
        },
    ]
    return pd.DataFrame(rows)


def build_phase254_recommendations(readiness: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in readiness.iterrows():
        rows.append(
            {
                "component": row["component"],
                "phase254_action": row["recommended_phase254_action"],
                "priority": "high"
                if row["component"] in {"H4/D1 intermediate profile", "prominence/size penalty", "EMA/HTF context"}
                else "medium",
                "must_remain_non_operational": True,
            }
        )
    rows.append(
        {
            "component": "manual review gate",
            "phase254_action": "manual review only for misleading context / low prominence examples, not for every candidate",
            "priority": "medium",
            "must_remain_non_operational": True,
        }
    )
    return pd.DataFrame(rows)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        name = _string(row.get("candidate_id")) or _string(row.get("component")) or f"fila {idx + 1}"
        lines.append(f"## {idx + 1}. {name}")
        for column in ("source_scope", "symbol", "timeframe", "swing_degree", "scale_fit_label", "ready_status", "evidence_summary", "notes"):
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


def _plot_bar(frame: pd.DataFrame, x_col: str, y_col: str, title: str, output_path: Path, color_col: str | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if frame.empty:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.text(0.5, 0.5, "Sin datos", ha="center", va="center")
        ax.axis("off")
        fig.savefig(output_path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        return
    plot = frame.copy()
    labels = plot[x_col].astype(str).tolist()
    values = pd.to_numeric(plot[y_col], errors="coerce").fillna(0).tolist()
    colors = [PALETTE.get(_string(value), PALETTE["context"]) for value in plot[color_col].tolist()] if color_col else PALETTE["context"]
    fig, ax = plt.subplots(figsize=(10, max(4, len(plot) * 0.35)))
    ax.barh(labels, values, color=colors)
    ax.set_title(title)
    ax.set_xlabel(y_col)
    ax.grid(axis="x", alpha=0.25)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_classification_summary(h4_stats: pd.DataFrame, h1_stats: pd.DataFrame, output_path: Path) -> None:
    h4_profile = h4_stats[h4_stats["metric"].eq("profile_class")].copy()
    h1_profile = h1_stats[h1_stats["metric"].eq("profile_class")].copy()
    h4_profile["scope_label"] = "H4/D1 " + h4_profile["label"].astype(str)
    h1_profile["scope_label"] = "H1/H4 " + h1_profile["label"].astype(str)
    data = pd.concat([h4_profile, h1_profile], ignore_index=True)
    data["color_key"] = data["label"].astype(str)
    _plot_bar(data, "scope_label", "case_count", "WaveCount 2.5.3 classification summary", output_path, "color_key")


def _plot_prominence(prominence_stats: pd.DataFrame, output_path: Path) -> None:
    if prominence_stats.empty:
        _plot_bar(prominence_stats, "scale_fit_label", "case_count", "Prominence diagnostics", output_path)
        return
    data = prominence_stats.groupby("scale_fit_label", dropna=False)["case_count"].sum().reset_index()
    data["color_key"] = data["scale_fit_label"].map(
        lambda value: "problem"
        if value in {"too_small_for_timeframe", "better_as_lower_tf_substructure", "ambiguous_scale"}
        else "yes"
        if value == "acceptable_for_timeframe"
        else "neutral"
    )
    _plot_bar(data.sort_values("case_count"), "scale_fit_label", "case_count", "Prominence / scale labels", output_path, "color_key")


def _plot_summary(frame: pd.DataFrame, label_col: str, title: str, output_path: Path) -> None:
    if frame.empty:
        _plot_bar(frame, label_col, "case_count", title, output_path)
        return
    data = frame.groupby(label_col, dropna=False)["case_count"].sum().reset_index().sort_values("case_count")
    data["color_key"] = data[label_col].map(
        lambda value: "yes"
        if "support" in str(value) or "explain" in str(value)
        else "problem"
        if "mislead" in str(value) or "conflict" in str(value)
        else "neutral"
    )
    _plot_bar(data, label_col, "case_count", title, output_path, "color_key")


def _write_report(output_dir: Path, meta: dict[str, Any]) -> None:
    lines = [
        "# WaveCount Phase 2.5.3 Descriptive Stats",
        "",
        f"Generated at: {meta['generated_at']}",
        "",
        "## Scope",
        "",
        "This phase consolidates descriptive statistics from WaveCount 2.5.0, 2.5.1, 2.5.2 and 2.5.2b.",
        "It does not generate signals, does not run backtests and does not change pivots, degrees or count rules.",
        "",
        "## Main Counts",
        "",
        f"- H4/D1 yes: {meta['h4_d1_counts'].get('yes', 0)}",
        f"- H4/D1 near_miss: {meta['h4_d1_counts'].get('near_miss', 0)}",
        f"- H4/D1 no: {meta['h4_d1_counts'].get('no', 0)}",
        f"- H1/H4 yes_aux: {meta['h1_h4_counts'].get('yes_aux', 0)}",
        f"- H1/H4 near_miss_aux: {meta['h1_h4_counts'].get('near_miss_aux', 0)}",
        f"- H1/H4 no: {meta['h1_h4_counts'].get('no', 0)}",
        "",
        "## Prominence",
        "",
        f"- Prominence problem cases: {meta['prominence_problem_cases']}",
        "- Recommendation: move prominence/size to a soft penalty candidate in Phase 2.5.4.",
        "",
        "## EWO / EMA / HTF",
        "",
        "- EWO remains useful as contextual momentum / wave-role support, not as autonomous wave label.",
        "- EMA 50/150 and HTF remain useful as soft context, not as hard validation.",
        "",
        "## Decision",
        "",
        "- H4/D1 intermediate remains the primary WaveCount base.",
        "- H1/H4 remains auxiliary / zoom / substructure.",
        "- Phase 2.5.4 should formalize soft prominence, EWO and EMA/HTF policies without creating signals.",
        "",
        "## Tables",
        "",
        "- `tables/dataset_inventory.csv`",
        "- `tables/classification_stats_h4_d1.csv`",
        "- `tables/classification_stats_h1_h4.csv`",
        "- `tables/prominence_stats.csv`",
        "- `tables/ewo_stats.csv`",
        "- `tables/ema_htf_stats.csv`",
        "- `tables/phase254_readiness_matrix.csv`",
        "",
        "## Charts",
        "",
        "- `charts/classification_summary.png`",
        "- `charts/prominence_distribution.png`",
        "- `charts/ewo_summary.png`",
        "- `charts/ema_htf_summary.png`",
        "- `charts/readiness_matrix.png`",
    ]
    (output_dir / "WAVECOUNT_PHASE2_5_3_DESCRIPTIVE_STATS.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def build_descriptive_stats(
    phase250_dir: Path = DEFAULT_PHASE250_DIR,
    phase251_dir: Path = DEFAULT_PHASE251_DIR,
    phase252_dir: Path = DEFAULT_PHASE252_DIR,
    phase252b_dir: Path = DEFAULT_PHASE252B_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    start = perf_counter()
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    h4 = _read_csv(phase252_dir / "tables" / "visual_expansion_review.csv")
    h1 = _read_csv(phase252b_dir / "tables" / "visual_aux_review.csv")
    h4_candidates = _read_csv(phase252_dir / "tables" / "guided_impulse_expanded_candidates.csv")
    h1_candidates = _read_csv(phase252b_dir / "tables" / "h1_h4_aux_candidates.csv")
    prominence = _read_csv(phase252b_dir / "tables" / "prominence_diagnostics.csv")
    h4_suspicious = _read_csv(phase252b_dir / "tables" / "h4_suspicious_scale_cases.csv")
    false_positive_risks = _read_csv(phase252_dir / "tables" / "profile_false_positive_risks.csv")
    ewo250 = _read_csv(phase250_dir / "tables" / "ewo_role_context.csv")
    context250 = _read_csv(phase250_dir / "tables" / "ema_htf_context_policy.csv")

    dataset_inventory = build_dataset_inventory(phase250_dir, phase251_dir, phase252_dir, phase252b_dir)
    h4_stats, h1_stats = build_classification_stats(h4, h1)
    group_symbol_stats = build_group_symbol_stats(h4, h1)
    degree_stats = build_degree_stats(h4, h1)
    prominence_stats, prominence_problem_cases = build_prominence_stats(prominence)
    if not h4_suspicious.empty:
        h4_suspicious = h4_suspicious.copy()
        h4_suspicious["source_from"] = "h4_suspicious_scale_cases"
        prominence_problem_cases = pd.concat([prominence_problem_cases, h4_suspicious], ignore_index=True, sort=False)
        if "candidate_id" in prominence_problem_cases.columns:
            prominence_problem_cases = prominence_problem_cases.drop_duplicates("candidate_id")
    ewo_stats = build_ewo_stats(h4, h1, ewo250)
    ema_htf_stats = build_ema_htf_stats(h4, h1, context250)
    context_misleading_cases = build_context_misleading_cases(h4, h1, false_positive_risks)
    readiness = build_phase254_readiness_matrix(h4, h1, prominence_problem_cases, ewo_stats, ema_htf_stats)
    recommendations = build_phase254_recommendations(readiness)
    user_review = build_user_review_table(context_misleading_cases, prominence_problem_cases)

    tables = {
        "dataset_inventory": dataset_inventory,
        "classification_stats_h4_d1": h4_stats,
        "classification_stats_h1_h4": h1_stats,
        "group_symbol_stats": group_symbol_stats,
        "degree_stats": degree_stats,
        "prominence_stats": prominence_stats,
        "prominence_problem_cases": prominence_problem_cases,
        "ewo_stats": ewo_stats,
        "ema_htf_stats": ema_htf_stats,
        "context_misleading_cases": context_misleading_cases,
        "phase254_readiness_matrix": readiness,
        "phase254_recommendations": recommendations,
        "user_review_if_any": user_review,
    }
    for name, frame in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    _plot_classification_summary(h4_stats, h1_stats, charts_dir / "classification_summary.png")
    _plot_prominence(prominence_stats, charts_dir / "prominence_distribution.png")
    _plot_summary(ewo_stats, "ewo_label", "EWO helpfulness / role support", charts_dir / "ewo_summary.png")
    _plot_summary(ema_htf_stats, "context_label", "EMA / HTF context labels", charts_dir / "ema_htf_summary.png")

    # Rebuild readiness chart with explicit numeric values after writing the CSV.
    readiness_chart = readiness.copy()
    readiness_chart["ready_numeric"] = readiness_chart["ready_status"].map(
        {
            "ready_for_soft_rule": 4,
            "ready_as_context_only": 3,
            "auxiliary_only": 2,
            "experimental": 1,
            "exclude": 0,
        }
    ).fillna(0)
    _plot_bar(readiness_chart, "component", "ready_numeric", "Phase 2.5.4 readiness", charts_dir / "readiness_matrix.png", "ready_status")

    missing_output_refs = sorted(
        {
            value
            for frame in tables.values()
            for value in _image_refs(frame)
            if not _resolve_repo_path(value).exists()
        }
    )
    h4_counts = h4.get("matches_guided_impulse_profile", pd.Series(dtype=str)).fillna("missing").value_counts().to_dict()
    h1_counts = h1.get("matches_h1_h4_aux_profile", pd.Series(dtype=str)).fillna("missing").value_counts().to_dict()
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase250_dir": _rel_to_repo(phase250_dir),
            "phase251_dir": _rel_to_repo(phase251_dir),
            "phase252_dir": _rel_to_repo(phase252_dir),
            "phase252b_dir": _rel_to_repo(phase252b_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "source_rows": {
            "h4_d1_candidates": int(len(h4_candidates)),
            "h4_d1_visual_review": int(len(h4)),
            "h1_h4_candidates": int(len(h1_candidates)),
            "h1_h4_visual_review": int(len(h1)),
        },
        "h4_d1_counts": {str(k): int(v) for k, v in h4_counts.items()},
        "h1_h4_counts": {str(k): int(v) for k, v in h1_counts.items()},
        "prominence_problem_cases": int(len(prominence_problem_cases)),
        "missing_input_image_refs": int(dataset_inventory["missing_image_ref_count"].sum()) if not dataset_inventory.empty else 0,
        "missing_output_image_refs": missing_output_refs,
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_backtests_executed": True,
        "no_base_rules_changed": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, meta)
    return meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.3 descriptive statistics.")
    parser.add_argument("--phase250-dir", type=Path, default=DEFAULT_PHASE250_DIR)
    parser.add_argument("--phase251-dir", type=Path, default=DEFAULT_PHASE251_DIR)
    parser.add_argument("--phase252-dir", type=Path, default=DEFAULT_PHASE252_DIR)
    parser.add_argument("--phase252b-dir", type=Path, default=DEFAULT_PHASE252B_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_descriptive_stats(
        phase250_dir=args.phase250_dir,
        phase251_dir=args.phase251_dir,
        phase252_dir=args.phase252_dir,
        phase252b_dir=args.phase252b_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
