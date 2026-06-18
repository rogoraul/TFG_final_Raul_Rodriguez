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
DEFAULT_PHASE252_DIR = GUIDED_ROOT / "phase2_5_2_h4_d1_expansion_2026-05-24"
DEFAULT_PHASE252B_DIR = GUIDED_ROOT / "phase2_5_2b_h1_h4_aux_2026-05-24"
DEFAULT_PHASE253_DIR = GUIDED_ROOT / "phase2_5_3_descriptive_stats_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_4_soft_quality_policy_2026-05-24"


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


def _safe_column(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series([default] * len(frame), index=frame.index)


def _join_notes(items: list[str]) -> str:
    return "; ".join(item for item in items if item)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        name = (
            _string(row.get("candidate_id"))
            or _string(row.get("component"))
            or _string(row.get("risk"))
            or f"fila {idx + 1}"
        )
        lines.append(f"## {idx + 1}. {name}")
        for column in (
            "source_scope",
            "symbol",
            "timeframe",
            "swing_degree",
            "structural_quality_policy",
            "final_soft_quality_bucket",
            "prominence_policy_label",
            "ewo_policy_label",
            "ema_htf_policy_label",
            "ready_status",
            "phase255_recommended_scope",
            "risk",
            "mitigation",
            "notes",
            "policy_reasons",
            "policy_warnings",
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


def classify_prominence_policy(row: pd.Series) -> dict[str, Any]:
    label = _string(row.get("scale_fit_label")) or "not_available"
    prominence = _number(row.get("prominence_vs_window"), default=-1.0)
    duration = _number(row.get("duration_vs_window"), default=-1.0)
    relative = _string(row.get("relative_structure_size"))
    degree = _string(row.get("swing_degree"))
    profile_class = _string(row.get("matches_guided_impulse_profile")) or _string(
        row.get("matches_h1_h4_aux_profile")
    )

    policy = "prominence_not_applicable"
    delta = 0
    warning = ""
    downgrade = False
    exclude = False
    reasons: list[str] = []

    if label == "acceptable_for_timeframe":
        policy = "acceptable_for_timeframe"
        delta = 4
        reasons.append("structure size is acceptable for the reviewed timeframe")
    elif label == "too_small_for_timeframe":
        policy = "low_prominence_vs_window"
        delta = -16
        warning = "count is too small or short relative to visible window"
        downgrade = True
        reasons.append("too_small_for_timeframe from prominence diagnostics")
    elif label == "better_as_lower_tf_substructure":
        policy = "better_as_lower_tf_substructure"
        delta = -10
        warning = "better handled as lower-timeframe substructure"
        downgrade = True
        reasons.append("diagnostic suggests lower timeframe / substructure")
    elif label == "ambiguous_scale":
        policy = "ambiguous_scale"
        delta = -7
        warning = "scale is ambiguous"
        reasons.append("scale diagnostic is ambiguous")
    elif label == "too_large_or_too_coarse":
        policy = "too_large_or_too_coarse"
        delta = -7
        warning = "structure may be too coarse for candidate search"
        reasons.append("too coarse / too large for the selected profile")
    elif label in {"not_applicable", "", "nan", "not_available"}:
        policy = "prominence_not_applicable"
        delta = 0
        reasons.append("no prominence penalty available for this structure")
    else:
        policy = label
        delta = -4
        warning = f"unclassified prominence label: {label}"
        reasons.append(warning)

    # Soft threshold candidates, not hard invalidation rules.
    threshold_notes: list[str] = []
    if prominence >= 0 and prominence < 0.18:
        threshold_notes.append("soft_threshold_candidate: prominence_vs_window < 0.18")
        delta -= 4
    if duration >= 0 and duration < 0.08:
        threshold_notes.append("soft_threshold_candidate: duration_vs_window < 0.08")
        delta -= 4
    if relative in {"small", "medium_small"} and label != "acceptable_for_timeframe":
        threshold_notes.append(f"relative_structure_size={relative}")

    # Low prominence alone is not enough to exclude. It becomes exclusion when
    # the profile was already a near miss / false positive risk.
    if policy == "low_prominence_vs_window" and profile_class in {"near_miss", "no"} and duration >= 0 and duration < 0.08:
        exclude = True

    if degree == "minor" and policy in {"better_as_lower_tf_substructure", "low_prominence_vs_window"}:
        downgrade = True

    reason = _join_notes(reasons + threshold_notes)
    return {
        "prominence_policy_label": policy,
        "prominence_score_delta": int(delta),
        "prominence_warning": warning,
        "should_downgrade_to_auxiliary": downgrade,
        "should_exclude_for_low_prominence": exclude,
        "prominence_policy_reason": reason,
    }


def classify_ewo_policy(row: pd.Series) -> dict[str, Any]:
    label = _string(row.get("ewo_helpfulness")) or _string(row.get("ewo_role_support")) or "not_available"
    direction = _string(row.get("end_ltf_ewo_5_35_direction"))
    slope = _number(row.get("end_ltf_ewo_5_35_slope"))
    momentum_match = _boolish(row.get("momentum_matches_direction"))
    category = _string(row.get("review_category"))
    failures = _string(row.get("guided_profile_failures")) or _string(row.get("aux_profile_failures"))

    if label == "supports_wave_role":
        policy = "relative_wave_role_support"
        support = "supports"
        delta = 8
        warning = ""
    elif label == "supports_momentum_only":
        policy = "momentum_context_only"
        support = "partial"
        delta = 4
        warning = "EWO supports momentum but not full wave role"
    elif label in {"unclear", "not_available", "", "nan"}:
        policy = "ewo_unclear_or_unavailable"
        support = "unclear"
        delta = 0
        warning = "EWO context is unclear or unavailable"
    elif label == "misleading":
        policy = "ewo_misleading_warning"
        support = "misleading"
        delta = -10
        warning = "EWO could mislead if used as filter"
    else:
        policy = "ewo_context_only"
        support = "partial"
        delta = 1
        warning = ""

    reasons = [f"input_label={label}"]
    if momentum_match:
        reasons.append("momentum_matches_direction=True")
    if direction:
        reasons.append(f"end_ewo_direction={direction}")
    if slope:
        reasons.append(f"end_ewo_slope={slope:.4g}")
    if category == "impulse" and "momentum does not support" in failures:
        delta -= 3
        warning = warning or "EWO/momentum does not support count direction"

    return {
        "ewo_policy_label": policy,
        "ewo_soft_support": support,
        "ewo_score_delta": int(delta),
        "ewo_warning": warning,
        "ewo_role_reason": _join_notes(reasons),
        "ewo_svm_future_feature_candidate": policy in {"relative_wave_role_support", "momentum_context_only"},
    }


def classify_ema_htf_policy(row: pd.Series) -> dict[str, Any]:
    label = _string(row.get("ema_htf_helpfulness")) or "not_available"
    trend = _string(row.get("trend_context_label"))
    band = _string(row.get("end_ltf_price_vs_ema_band"))
    htf_conflict = _boolish(row.get("htf_direction_conflict")) or trend == "conflict_with_htf"
    htf_match = _boolish(row.get("htf_direction_match"))
    ltf_match = _boolish(row.get("ltf_direction_match"))
    visual_status = _string(row.get("visual_expansion_status")) or _string(row.get("visual_aux_status"))
    profile_class = _string(row.get("matches_guided_impulse_profile")) or _string(
        row.get("matches_h1_h4_aux_profile")
    )

    if label == "supports_context":
        policy = "ema_htf_context_support"
        support = "supports"
        delta = 8
    elif label == "explains_transition":
        policy = "ema_htf_transition_support"
        support = "supports_transition"
        delta = 7
    elif label == "explains_correction":
        policy = "ema_htf_correction_context"
        support = "contextual"
        delta = 4
    elif label == "neutral":
        policy = "ema_htf_neutral"
        support = "neutral"
        delta = 0
    elif label == "misleading":
        policy = "ema_htf_misleading_warning"
        support = "misleading"
        delta = -12
    else:
        policy = "ema_htf_unclear"
        support = "unclear"
        delta = -1

    warnings: list[str] = []
    if band == "inside_band":
        warnings.append("price_inside_ema_band_adds_ambiguity")
        delta -= 4
    if htf_conflict:
        warnings.append("htf_conflict_warning")
        delta -= 6
    if visual_status in {"false_positive_risk", "context_misleading", "not_usable"} and label in {
        "supports_context",
        "explains_correction",
        "explains_transition",
    }:
        warnings.append("context_must_not_rescue_bad_count")
        delta -= 8
    if profile_class == "no" and label in {"supports_context", "explains_correction", "explains_transition"}:
        warnings.append("context_support_on_no_profile_is_not_validation")

    reasons = [
        f"input_label={label}",
        f"trend_context_label={trend or 'missing'}",
        f"ema_band={band or 'missing'}",
        f"htf_match={htf_match}",
        f"ltf_match={ltf_match}",
    ]
    return {
        "ema_htf_policy_label": policy,
        "ema_htf_soft_support": support,
        "ema_htf_score_delta": int(delta),
        "ema_band_warning": "price_inside_ema_band_adds_ambiguity" if band == "inside_band" else "",
        "htf_conflict_warning": "htf_conflict_warning" if htf_conflict else "",
        "context_must_not_rescue_bad_count": "context_must_not_rescue_bad_count" in warnings,
        "ema_htf_policy_reason": _join_notes(reasons + warnings),
    }


def _base_score(row: pd.Series) -> tuple[int, list[str], list[str]]:
    source_scope = _string(row.get("source_scope"))
    category = _string(row.get("review_category"))
    timeframe = _string(row.get("timeframe")).upper()
    degree = _string(row.get("swing_degree"))
    h4_match = _string(row.get("matches_guided_impulse_profile"))
    h1_match = _string(row.get("matches_h1_h4_aux_profile"))
    visual = _string(row.get("visual_expansion_status")) or _string(row.get("visual_aux_status"))
    score = 20
    reasons: list[str] = []
    warnings: list[str] = []

    if category == "impulse":
        score += 12
        reasons.append("structure=impulse")
    elif category == "partial_123":
        score -= 12
        warnings.append("partial_123_is_provisional_context_only")
    elif category == "abc":
        score -= 18
        warnings.append("abc_requires_parent_context")
    elif category:
        score -= 20
        warnings.append(f"{category}_not_primary_profile")

    if source_scope == "h4_d1":
        score += 12
        reasons.append("H4/D1 primary scope")
    elif source_scope == "h1_h4":
        score += 3
        warnings.append("H1/H4 is auxiliary, not primary")

    if timeframe == "H4":
        score += 8
    elif timeframe == "H1":
        score += 2
    elif timeframe == "M30":
        score -= 6
        warnings.append("M30 is microstructure only")

    if degree == "intermediate":
        score += 10
        reasons.append("degree=intermediate")
    elif degree == "major":
        score += 3
        warnings.append("major is higher-degree context")
    elif degree == "minor":
        score -= 4
        warnings.append("minor is substructure")

    if h4_match == "yes":
        score += 18
        reasons.append("H4/D1 profile match=yes")
    elif h4_match == "near_miss":
        score += 6
        warnings.append("H4/D1 near_miss stays provisional")
    elif h4_match == "no":
        score -= 16
        warnings.append("H4/D1 profile match=no")

    if h1_match == "yes_aux":
        score += 9
        reasons.append("H1/H4 auxiliary match=yes_aux")
    elif h1_match == "near_miss_aux":
        score += 2
        warnings.append("H1/H4 near_miss_aux")
    elif h1_match == "no":
        score -= 10
        warnings.append("H1/H4 profile match=no")

    visual_deltas = {
        "strong_match": 12,
        "acceptable_match": 8,
        "near_miss_useful": 4,
        "good_aux_structure": 8,
        "useful_lower_tf_substructure": 4,
        "near_miss_too_weak": -8,
        "good_negative_example": -12,
        "false_positive_risk": -22,
        "context_misleading": -18,
        "too_micro_even_for_h1": -15,
        "too_noisy": -14,
        "not_usable": -25,
    }
    if visual in visual_deltas:
        delta = visual_deltas[visual]
        score += delta
        if delta >= 0:
            reasons.append(f"visual_status={visual}")
        else:
            warnings.append(f"visual_status={visual}")

    return score, reasons, warnings


def classify_structural_quality(row: pd.Series) -> dict[str, Any]:
    score, reasons, warnings = _base_score(row)
    prom = classify_prominence_policy(row)
    ewo = classify_ewo_policy(row)
    ema = classify_ema_htf_policy(row)

    score += int(prom["prominence_score_delta"])
    score += int(ewo["ewo_score_delta"])
    score += int(ema["ema_htf_score_delta"])
    score = max(0, min(100, score))

    if prom["prominence_warning"]:
        warnings.append(_string(prom["prominence_warning"]))
    if ewo["ewo_warning"]:
        warnings.append(_string(ewo["ewo_warning"]))
    if ema["ema_band_warning"]:
        warnings.append(_string(ema["ema_band_warning"]))
    if ema["htf_conflict_warning"]:
        warnings.append(_string(ema["htf_conflict_warning"]))
    if ema["context_must_not_rescue_bad_count"]:
        warnings.append("context_must_not_rescue_bad_count")

    source_scope = _string(row.get("source_scope"))
    h4_match = _string(row.get("matches_guided_impulse_profile"))
    h1_match = _string(row.get("matches_h1_h4_aux_profile"))
    visual = _string(row.get("visual_expansion_status")) or _string(row.get("visual_aux_status"))
    category = _string(row.get("review_category"))

    hard_exclude = (
        visual in {"false_positive_risk", "not_usable", "context_misleading"}
        or h4_match == "no"
        or (h1_match == "no" and source_scope == "h1_h4")
        or bool(prom["should_exclude_for_low_prominence"])
    )
    if category in {"abc", "partial_123"}:
        bucket = "experimental_only" if score >= 35 else "exclude_from_guided_search"
    elif hard_exclude and score < 55:
        bucket = "exclude_from_guided_search"
    elif source_scope == "h1_h4" and score >= 45:
        bucket = "auxiliary_substructure"
    elif score >= 78 and h4_match == "yes" and not warnings:
        bucket = "high_quality_structure"
    elif score >= 62 and h4_match in {"yes", "near_miss"}:
        bucket = "usable_provisional_structure"
    elif score >= 42:
        bucket = "ambiguous_structure"
    elif score >= 30:
        bucket = "experimental_only"
    else:
        bucket = "exclude_from_guided_search"

    if bucket == "high_quality_structure":
        policy = "high_quality_structure"
        ready = "yes"
    elif bucket == "usable_provisional_structure":
        policy = "usable_provisional_structure"
        ready = "yes_with_manual_spot_check"
    elif bucket == "auxiliary_substructure":
        policy = "auxiliary_substructure"
        ready = "auxiliary_only"
    elif bucket == "ambiguous_structure":
        policy = "ambiguous_structure"
        ready = "manual_review"
    elif bucket == "experimental_only":
        policy = "experimental_only"
        ready = "no"
    else:
        policy = "exclude_from_guided_search"
        ready = "no"

    reason_text = _join_notes(
        reasons
        + [
            _string(prom["prominence_policy_reason"]),
            _string(ewo["ewo_role_reason"]),
            _string(ema["ema_htf_policy_reason"]),
        ]
    )
    warning_text = _join_notes(warnings)
    output = {
        **prom,
        **ewo,
        **ema,
        "structural_quality_policy": policy,
        "final_soft_quality_score": int(score),
        "final_soft_quality_bucket": bucket,
        "policy_reasons": reason_text,
        "policy_warnings": warning_text,
        "ready_for_next_expansion": ready,
    }
    return output


def build_soft_quality_policy_matrix(readiness: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    if readiness.empty:
        readiness = pd.DataFrame(
            [
                {
                    "component": "H4/D1 intermediate profile",
                    "ready_status": "ready_for_soft_rule",
                    "evidence_summary": "missing readiness table; default to documented policy",
                    "risk_if_used_wrong": "could be treated as signal",
                    "recommended_phase254_action": "formalize as non-operational profile",
                }
            ]
        )
    rec_map = {}
    if not recommendations.empty and "component" in recommendations.columns:
        rec_map = recommendations.set_index("component").to_dict("index")

    policy_map = {
        "H4/D1 intermediate profile": ("primary_soft_profile", "H4/D1 remains primary; no trading output"),
        "H1/H4 auxiliary profile": ("auxiliary_zoom_profile", "H1/H4 remains auxiliary/substructure"),
        "prominence/size penalty": ("soft_penalty", "penalize low prominence without hard invalidation"),
        "EWO role support": ("context_only", "relative momentum / wave-role context"),
        "EMA/HTF context": ("context_only", "regime, transition and ambiguity context"),
        "ABC contextual": ("experimental_context", "only with parent/context; isolated ABC excluded"),
        "partial 1-2-3": ("provisional_context", "never a signal; always provisional"),
        "major context": ("higher_degree_context", "context or higher-degree structure"),
        "minor substructure": ("substructure_only", "not primary; avoid microcounting"),
    }
    rows: list[dict[str, Any]] = []
    for _, row in readiness.iterrows():
        component = _string(row.get("component"))
        phase254_policy, reason = policy_map.get(component, ("documented_context", "kept as documented context"))
        rec = rec_map.get(component, {})
        rows.append(
            {
                "component": component,
                "ready_status": _string(row.get("ready_status")),
                "phase254_policy": phase254_policy,
                "can_be_soft_rule": _string(row.get("ready_status")) == "ready_for_soft_rule",
                "context_only": _string(row.get("ready_status")) in {"ready_as_context_only", "auxiliary_only"},
                "experimental": _string(row.get("ready_status")) == "experimental",
                "excluded": _string(row.get("ready_status")) == "exclude",
                "evidence_summary": _string(row.get("evidence_summary")),
                "risk_if_used_wrong": _string(row.get("risk_if_used_wrong")),
                "phase254_action": _string(rec.get("phase254_action")) or _string(row.get("recommended_phase254_action")),
                "policy_reason": reason,
                "must_remain_non_operational": True,
            }
        )
    return pd.DataFrame(rows)


def _merge_prominence(frame: pd.DataFrame, prominence: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    if prominence.empty or "candidate_id" not in prominence.columns:
        return frame
    prominence_cols = [
        "candidate_id",
        "prominence_vs_window",
        "duration_vs_window",
        "relative_structure_size",
        "scale_fit_label",
        "scale_notes",
    ]
    available = [column for column in prominence_cols if column in prominence.columns]
    prom = prominence[available].drop_duplicates("candidate_id")
    merged = frame.merge(prom, on="candidate_id", how="left", suffixes=("", "_prominence"))
    for column in ("prominence_vs_window", "duration_vs_window", "relative_structure_size", "scale_fit_label", "scale_notes"):
        prom_col = f"{column}_prominence"
        if prom_col in merged.columns:
            if column in merged.columns:
                merged[column] = merged[column].where(merged[column].notna() & merged[column].astype(str).ne(""), merged[prom_col])
            else:
                merged[column] = merged[prom_col]
            merged = merged.drop(columns=[prom_col])
    return merged


def _combined_candidates(h4: pd.DataFrame, h1: pd.DataFrame, prominence: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not h4.empty:
        tmp = h4.copy()
        tmp["source_scope"] = "h4_d1"
        frames.append(tmp)
    if not h1.empty:
        tmp = h1.copy()
        tmp["source_scope"] = "h1_h4"
        frames.append(tmp)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = _merge_prominence(combined, prominence)
    return combined


def build_prominence_soft_policy(combined: pd.DataFrame, aus200_case: pd.DataFrame) -> pd.DataFrame:
    if combined.empty:
        return pd.DataFrame()
    rows = []
    for _, row in combined.iterrows():
        policy = classify_prominence_policy(row)
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "prominence_vs_window": row.get("prominence_vs_window"),
                "duration_vs_window": row.get("duration_vs_window"),
                "relative_structure_size": _string(row.get("relative_structure_size")),
                "scale_fit_label": _string(row.get("scale_fit_label")) or "not_available",
                **policy,
                "is_aus200_required_case": _string(row.get("candidate_id"))
                == "impulse_exp252_index_aus200_h4_intermediate_impulse_020",
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
            }
        )
    out = pd.DataFrame(rows)
    if not aus200_case.empty and "candidate_id" in aus200_case.columns:
        required_id = "impulse_exp252_index_aus200_h4_intermediate_impulse_020"
        if required_id not in set(out["candidate_id"]):
            row = aus200_case.iloc[0]
            policy = classify_prominence_policy(row)
            out = pd.concat(
                [
                    out,
                    pd.DataFrame(
                        [
                            {
                                "candidate_id": required_id,
                                "source_scope": "h4_d1",
                                "symbol": _string(row.get("symbol")),
                                "timeframe": _string(row.get("timeframe")),
                                "swing_degree": _string(row.get("swing_degree")),
                                "prominence_vs_window": row.get("prominence_vs_window"),
                                "duration_vs_window": row.get("duration_vs_window"),
                                "relative_structure_size": _string(row.get("relative_structure_size")),
                                "scale_fit_label": _string(row.get("scale_fit_label")),
                                **policy,
                                "is_aus200_required_case": True,
                                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
    return out


def build_ewo_soft_policy(combined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in combined.iterrows():
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "review_category": _string(row.get("review_category")),
                "ewo_helpfulness": _string(row.get("ewo_helpfulness")),
                "end_ltf_ewo_5_35": row.get("end_ltf_ewo_5_35"),
                "end_ltf_ewo_5_35_slope": row.get("end_ltf_ewo_5_35_slope"),
                "end_ltf_ewo_5_35_direction": _string(row.get("end_ltf_ewo_5_35_direction")),
                "momentum_matches_direction": row.get("momentum_matches_direction"),
                **classify_ewo_policy(row),
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_ema_htf_soft_policy(combined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in combined.iterrows():
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "trend_context_label": _string(row.get("trend_context_label")),
                "ema_htf_helpfulness": _string(row.get("ema_htf_helpfulness")),
                "end_ltf_price_vs_ema_band": _string(row.get("end_ltf_price_vs_ema_band")),
                "htf_timeframe": _string(row.get("htf_timeframe")),
                "htf_ema_alignment": _string(row.get("htf_ema_alignment")),
                "htf_price_vs_ema_band": _string(row.get("htf_price_vs_ema_band")),
                **classify_ema_htf_policy(row),
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_structural_quality_scores(combined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in combined.iterrows():
        quality = classify_structural_quality(row)
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "group": _string(row.get("group")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "direction": _string(row.get("direction")),
                "review_category": _string(row.get("review_category")),
                "matches_guided_impulse_profile": _string(row.get("matches_guided_impulse_profile")),
                "matches_h1_h4_aux_profile": _string(row.get("matches_h1_h4_aux_profile")),
                "visual_expansion_status": _string(row.get("visual_expansion_status")),
                "visual_aux_status": _string(row.get("visual_aux_status")),
                "near_miss_reason": _string(row.get("near_miss_reason")) or _string(row.get("aux_near_miss_reason")),
                "scale_fit_label": _string(row.get("scale_fit_label")) or "not_available",
                "ewo_helpfulness": _string(row.get("ewo_helpfulness")),
                "ema_htf_helpfulness": _string(row.get("ema_htf_helpfulness")),
                "chart_path": _string(row.get("reviewed_chart_path")) or _string(row.get("chart_path")),
                **quality,
            }
        )
    return pd.DataFrame(rows)


def build_structural_quality_summary(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame(columns=["scope", "metric", "label", "case_count", "share_pct"])
    rows: list[dict[str, Any]] = []
    for scope, part in scores.groupby("source_scope", dropna=False):
        total = len(part)
        for metric in ("final_soft_quality_bucket", "structural_quality_policy", "prominence_policy_label", "ewo_policy_label", "ema_htf_policy_label"):
            if metric not in part.columns:
                continue
            counts = part[metric].fillna("missing").replace("", "missing").value_counts()
            for label, count in counts.items():
                rows.append(
                    {
                        "scope": scope,
                        "metric": metric,
                        "label": label,
                        "case_count": int(count),
                        "share_pct": round(float(count / total * 100.0), 2) if total else 0.0,
                    }
                )
    return pd.DataFrame(rows)


def build_risk_register(scores: pd.DataFrame, context_misleading: pd.DataFrame) -> pd.DataFrame:
    def count_contains(column: str, text: str) -> int:
        if scores.empty or column not in scores.columns:
            return 0
        return int(scores[column].astype(str).str.contains(text, case=False, na=False).sum())

    risks = [
        {
            "risk": "low_prominence_or_too_small_for_timeframe",
            "where_seen": f"{count_contains('prominence_policy_label', 'low_prominence|lower_tf|ambiguous_scale')} candidate rows; AUS200 H4 is the explicit example.",
            "impact": "Can create visually tiny H4 structures that look like subwaves rather than primary Elliott counts.",
            "mitigation": "Apply soft prominence/duration penalty and downgrade to auxiliary or exclude only with supporting visual/context risk.",
            "phase_after_254_action": "Use as soft penalty in Phase 2.5.5 expansion, not as hard invalidation.",
        },
        {
            "risk": "microcounts",
            "where_seen": f"{count_contains('policy_warnings', 'minor is substructure|M30 is microstructure')} rows with micro/substructure warnings.",
            "impact": "Can overfit Elliott labels inside noise or lateral movement.",
            "mitigation": "Keep minor/M30 as substructure or negative evidence.",
            "phase_after_254_action": "Do not promote M30/H1 to primary base.",
        },
        {
            "risk": "ewo_misleading",
            "where_seen": f"{count_contains('ewo_policy_label', 'misleading')} EWO misleading rows.",
            "impact": "Momentum can support a move without identifying wave role.",
            "mitigation": "Use relative EWO as context only; no absolute thresholds; no autonomous labels.",
            "phase_after_254_action": "Keep EWO+SVM as future experimental research.",
        },
        {
            "risk": "ema_htf_lag_or_conflict",
            "where_seen": f"{count_contains('policy_warnings', 'htf_conflict|inside_ema_band')} rows with HTF conflict or EMA band ambiguity.",
            "impact": "HTF can arrive late or make transitions look contradictory.",
            "mitigation": "Classify transition/conflict instead of invalidating automatically.",
            "phase_after_254_action": "Use HTF/EMA only as soft context in expansion.",
        },
        {
            "risk": "context_rescues_bad_count",
            "where_seen": f"{count_contains('policy_warnings', 'context_must_not_rescue_bad_count')} rows flagged; {len(context_misleading)} contextual misleading cases from 2.5.3.",
            "impact": "Indicator agreement can hide a visually weak count.",
            "mitigation": "Visual count decision remains upstream; context cannot rescue no/false-positive cases.",
            "phase_after_254_action": "Audit false positives in any broader expansion.",
        },
        {
            "risk": "abc_without_parent",
            "where_seen": "ABC remains experimental unless contextual parent is known.",
            "impact": "Impulses can be mislabeled as corrections.",
            "mitigation": "Keep ABC out of impulse profile; only contextual correction with parent can be soft context.",
            "phase_after_254_action": "Do not implement complex correction taxonomy yet.",
        },
        {
            "risk": "partial123_too_lax",
            "where_seen": "Prior Phase 2.3.2 found partials can be weak, lateral or immediately invalidated.",
            "impact": "Three alternating swings can be mistaken for a live structure.",
            "mitigation": "Keep partial 1-2-3 provisional and require visual displacement / post-3 checks.",
            "phase_after_254_action": "Do not use partials as profile seeds.",
        },
        {
            "risk": "major_minor_misuse",
            "where_seen": f"{count_contains('policy_warnings', 'major is higher-degree|minor is substructure')} rows with degree warnings.",
            "impact": "Major can be too coarse; minor can be too micro.",
            "mitigation": "Use intermediate as primary, major as context/higher degree, minor as substructure.",
            "phase_after_254_action": "Keep degree policy unchanged until a separate recalibration phase.",
        },
        {
            "risk": "confusing_scoring_with_signal",
            "where_seen": "All 2.5.x scoring artifacts.",
            "impact": "Could be misread as probability or trading filter.",
            "mitigation": "State clearly that scores are methodological quality labels only.",
            "phase_after_254_action": "No signals, no backtests and no MT5 integration from WaveCount.",
        },
    ]
    return pd.DataFrame(risks)


def build_phase255_recommendation(scores: pd.DataFrame) -> pd.DataFrame:
    high = int(scores["final_soft_quality_bucket"].eq("high_quality_structure").sum()) if not scores.empty else 0
    usable = int(scores["final_soft_quality_bucket"].eq("usable_provisional_structure").sum()) if not scores.empty else 0
    auxiliary = int(scores["final_soft_quality_bucket"].eq("auxiliary_substructure").sum()) if not scores.empty else 0
    excluded = int(scores["final_soft_quality_bucket"].eq("exclude_from_guided_search").sum()) if not scores.empty else 0
    return pd.DataFrame(
        [
            {
                "phase255_recommended_scope": "controlled_h4_d1_historical_expansion",
                "phase255_inputs": "structural_quality_scores high_quality_structure and usable_provisional_structure from H4/D1",
                "phase255_do_not_do": "do not generate signals, do not run backtests, do not optimize by returns",
                "phase255_validation_needed": "selective visual gallery for high scores, low-prominence false positives and context conflicts",
                "evidence_summary": f"{high} high_quality, {usable} usable provisional, {excluded} excluded.",
                "priority": "high",
            },
            {
                "phase255_recommended_scope": "keep_h1_h4_auxiliary_zoom",
                "phase255_inputs": "H1/H4 auxiliary_substructure rows only",
                "phase255_do_not_do": "do not merge H1/H4 with primary H4/D1 seeds",
                "phase255_validation_needed": "use H1/H4 only to explain substructure and low-prominence H4 cases",
                "evidence_summary": f"{auxiliary} auxiliary_substructure rows.",
                "priority": "medium",
            },
            {
                "phase255_recommended_scope": "false_positive_gallery",
                "phase255_inputs": "exclude_from_guided_search and ambiguous_structure rows with policy_warnings",
                "phase255_do_not_do": "do not relax rules to increase match count",
                "phase255_validation_needed": "spot-check low prominence, context_must_not_rescue_bad_count and EWO misleading cases",
                "evidence_summary": "Use negatives to stress-test the soft policy.",
                "priority": "medium",
            },
        ]
    )


def build_user_review(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    mask = (
        scores["candidate_id"].eq("impulse_exp252_index_aus200_h4_intermediate_impulse_020")
        | scores["final_soft_quality_bucket"].isin(["ambiguous_structure", "experimental_only"])
        | scores["policy_warnings"].astype(str).str.contains("context_must_not_rescue|low|htf_conflict|misleading", case=False, na=False)
    )
    cols = [
        "candidate_id",
        "source_scope",
        "symbol",
        "timeframe",
        "swing_degree",
        "final_soft_quality_bucket",
        "final_soft_quality_score",
        "policy_warnings",
        "chart_path",
    ]
    return scores.loc[mask, [column for column in cols if column in scores.columns]].head(20)


def _validate_image_refs(tables: dict[str, pd.DataFrame]) -> list[str]:
    missing: set[str] = set()
    for frame in tables.values():
        for column in frame.columns:
            if "path" not in column.lower():
                continue
            for value in frame[column].dropna().astype(str):
                if value.lower().endswith(".png") and not _resolve_repo_path(value).exists():
                    missing.add(value)
    return sorted(missing)


def _write_report(output_dir: Path, meta: dict[str, Any]) -> None:
    lines = [
        "# WaveCount Phase 2.5.4 Soft Quality Policy",
        "",
        f"Generated at: {meta['generated_at']}",
        "",
        "## Scope",
        "",
        "Formaliza reglas blandas de calidad estructural usando artifacts vigentes bajo `05_guided_profile/`.",
        "No recalcula pivotes, no recalcula conteos, no genera senales y no ejecuta backtests.",
        "",
        "## Decisions",
        "",
        "- H4/D1 `intermediate` sigue como base principal.",
        "- H1/H4 queda como auxiliar / zoom de subestructura.",
        "- M30/H1 se mantiene como microestructura, no base principal.",
        "- Prominencia/tamano pasa a penalizacion blanda, no invalidacion automatica.",
        "- EWO 5-35 se usa como apoyo relativo de momentum/rol de onda, no como etiqueta autonoma.",
        "- EMAs 50/150 y HTF se usan como contexto blando de regimen/transicion/ambiguedad.",
        "- ABC aislado no entra como regla fuerte; solo correccion contextual con padre razonable.",
        "",
        "## Summary",
        "",
        f"- Candidate rows scored: {meta['rows'].get('structural_quality_scores', 0)}",
        f"- High quality structures: {meta['bucket_counts'].get('high_quality_structure', 0)}",
        f"- Usable provisional structures: {meta['bucket_counts'].get('usable_provisional_structure', 0)}",
        f"- Auxiliary substructures: {meta['bucket_counts'].get('auxiliary_substructure', 0)}",
        f"- Excluded from guided search: {meta['bucket_counts'].get('exclude_from_guided_search', 0)}",
        "",
        "## AUS200 H4",
        "",
        meta.get("aus200_policy_note", "AUS200 H4 required case not found."),
        "",
        "## Next",
        "",
        "Fase 2.5.5 puede ampliar de forma descriptiva H4/D1 aplicando esta politica blanda,",
        "con galeria selectiva de altos scores, near-misses y falsos positivos. No debe pasar aun a senales.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_5_4_SOFT_QUALITY_POLICY.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def build_soft_quality_policy(
    phase250_dir: Path = DEFAULT_PHASE250_DIR,
    phase252_dir: Path = DEFAULT_PHASE252_DIR,
    phase252b_dir: Path = DEFAULT_PHASE252B_DIR,
    phase253_dir: Path = DEFAULT_PHASE253_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    start = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    readiness = _read_csv(phase253_dir / "tables" / "phase254_readiness_matrix.csv")
    recommendations = _read_csv(phase253_dir / "tables" / "phase254_recommendations.csv")
    prominence_stats = _read_csv(phase253_dir / "tables" / "prominence_stats.csv")
    prominence_problem_cases = _read_csv(phase253_dir / "tables" / "prominence_problem_cases.csv")
    ewo_stats = _read_csv(phase253_dir / "tables" / "ewo_stats.csv")
    ema_htf_stats = _read_csv(phase253_dir / "tables" / "ema_htf_stats.csv")
    context_misleading = _read_csv(phase253_dir / "tables" / "context_misleading_cases.csv")

    h4_review = _read_csv(phase252_dir / "tables" / "visual_expansion_review.csv")
    h4_ewo_review = _read_csv(phase252_dir / "tables" / "ewo_expansion_review.csv")
    h4_ema_review = _read_csv(phase252_dir / "tables" / "ema_htf_expansion_review.csv")
    h4_false_positive = _read_csv(phase252_dir / "tables" / "profile_false_positive_risks.csv")

    h1_review = _read_csv(phase252b_dir / "tables" / "visual_aux_review.csv")
    prominence_diagnostics = _read_csv(phase252b_dir / "tables" / "prominence_diagnostics.csv")
    h4_suspicious = _read_csv(phase252b_dir / "tables" / "h4_suspicious_scale_cases.csv")
    h1_ewo_review = _read_csv(phase252b_dir / "tables" / "ewo_aux_review.csv")
    h1_ema_review = _read_csv(phase252b_dir / "tables" / "ema_htf_aux_review.csv")
    aus200_case = _read_csv(phase252b_dir / "tables" / "aus200_h4_case_review.csv")

    combined = _combined_candidates(h4_review, h1_review, prominence_diagnostics)
    matrix = build_soft_quality_policy_matrix(readiness, recommendations)
    prominence_policy = build_prominence_soft_policy(combined, aus200_case)
    ewo_policy = build_ewo_soft_policy(combined)
    ema_policy = build_ema_htf_soft_policy(combined)
    scores = build_structural_quality_scores(combined)
    summary = build_structural_quality_summary(scores)
    risk_register = build_risk_register(scores, context_misleading)
    phase255 = build_phase255_recommendation(scores)
    user_review = build_user_review(scores)

    # Keep source summaries in meta for traceability without rewriting source tables.
    input_summary = {
        "phase254_readiness_matrix": int(len(readiness)),
        "phase254_recommendations": int(len(recommendations)),
        "prominence_stats": int(len(prominence_stats)),
        "prominence_problem_cases": int(len(prominence_problem_cases)),
        "ewo_stats": int(len(ewo_stats)),
        "ema_htf_stats": int(len(ema_htf_stats)),
        "context_misleading_cases": int(len(context_misleading)),
        "h4_visual_expansion_review": int(len(h4_review)),
        "h4_ewo_expansion_review": int(len(h4_ewo_review)),
        "h4_ema_htf_expansion_review": int(len(h4_ema_review)),
        "h4_false_positive_risks": int(len(h4_false_positive)),
        "h1_visual_aux_review": int(len(h1_review)),
        "prominence_diagnostics": int(len(prominence_diagnostics)),
        "h4_suspicious_scale_cases": int(len(h4_suspicious)),
        "h1_ewo_aux_review": int(len(h1_ewo_review)),
        "h1_ema_htf_aux_review": int(len(h1_ema_review)),
        "aus200_h4_case_review": int(len(aus200_case)),
    }

    tables = {
        "soft_quality_policy_matrix": matrix,
        "prominence_soft_policy": prominence_policy,
        "ewo_soft_policy": ewo_policy,
        "ema_htf_soft_policy": ema_policy,
        "structural_quality_scores": scores,
        "structural_quality_summary": summary,
        "soft_policy_risk_register": risk_register,
        "phase255_recommendation": phase255,
        "user_review_if_any": user_review,
    }
    for name, frame in tables.items():
        csv_path = tables_dir / f"{name}.csv"
        _write_csv(frame, csv_path)
        _write_markdown_index(csv_path, name)

    missing_refs = _validate_image_refs(tables)
    bucket_counts = (
        scores["final_soft_quality_bucket"].fillna("missing").value_counts().to_dict()
        if not scores.empty and "final_soft_quality_bucket" in scores.columns
        else {}
    )
    aus200_note = "AUS200 H4 required case not found."
    if not scores.empty:
        aus200 = scores[scores["candidate_id"].eq("impulse_exp252_index_aus200_h4_intermediate_impulse_020")]
        if not aus200.empty:
            row = aus200.iloc[0]
            aus200_note = (
                f"`{row['candidate_id']}` queda como `{row['final_soft_quality_bucket']}` "
                f"con `{row['prominence_policy_label']}` y score {row['final_soft_quality_score']}. "
                "Se trata como ejemplo de baja prominencia/contexto conflictivo, no como seed fuerte."
            )

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase250_dir": _rel_to_repo(phase250_dir),
            "phase252_dir": _rel_to_repo(phase252_dir),
            "phase252b_dir": _rel_to_repo(phase252b_dir),
            "phase253_dir": _rel_to_repo(phase253_dir),
        },
        "source_rows": input_summary,
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "bucket_counts": {str(k): int(v) for k, v in bucket_counts.items()},
        "aus200_policy_note": aus200_note,
        "missing_output_image_refs": missing_refs,
        "uses_reorganized_phase25_paths": all(
            "artifacts\\wavecount\\05_guided_profile" in _rel_to_repo(path)
            or "artifacts/wavecount/05_guided_profile" in _rel_to_repo(path)
            for path in (phase250_dir, phase252_dir, phase252b_dir, phase253_dir, output_dir)
        ),
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_backtests_executed": True,
        "no_base_rules_changed": True,
        "no_pivots_recalculated": True,
        "no_counts_recalculated": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, meta)
    return meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.4 soft structural quality policy.")
    parser.add_argument("--phase250-dir", type=Path, default=DEFAULT_PHASE250_DIR)
    parser.add_argument("--phase252-dir", type=Path, default=DEFAULT_PHASE252_DIR)
    parser.add_argument("--phase252b-dir", type=Path, default=DEFAULT_PHASE252B_DIR)
    parser.add_argument("--phase253-dir", type=Path, default=DEFAULT_PHASE253_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_soft_quality_policy(
        phase250_dir=args.phase250_dir,
        phase252_dir=args.phase252_dir,
        phase252b_dir=args.phase252b_dir,
        phase253_dir=args.phase253_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
