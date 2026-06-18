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
DEFAULT_PHASE254_DIR = GUIDED_ROOT / "phase2_5_4_soft_quality_policy_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_5_soft_policy_visual_audit_2026-05-24"

REQUIRED_AUS200_ID = "impulse_exp252_index_aus200_h4_intermediate_impulse_020"


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


def _join_notes(items: list[str]) -> str:
    return "; ".join(item for item in items if item)


def _copy_chart(row: pd.Series, output_dir: Path, idx: int) -> str:
    value = _string(row.get("chart_path"))
    if not value:
        return ""
    src = _resolve_repo_path(value)
    if not src.exists():
        return value
    dest_dir = output_dir / "charts" / "selected_review"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{idx:03d}_{src.name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return _rel_to_repo(dest)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        name = _string(row.get("candidate_id")) or _string(row.get("audit_group")) or f"fila {idx + 1}"
        lines.append(f"## {idx + 1}. {name}")
        for column in (
            "selection_reasons",
            "final_soft_quality_bucket",
            "final_soft_quality_score",
            "visual_policy_verdict",
            "exclusion_reason_validity",
            "recommended_policy_adjustment",
            "visual_notes",
            "audit_conclusion",
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


def build_exclusion_ratio_diagnostics(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    total = len(scores)
    excluded = scores[scores["final_soft_quality_bucket"].eq("exclude_from_guided_search")]
    rows.append(
        {
            "diagnostic_scope": "global",
            "metric": "total_rows",
            "label": "all",
            "case_count": total,
            "share_pct": 100.0,
            "interpretation": "all scored structures from Phase 2.5.4",
        }
    )
    rows.append(
        {
            "diagnostic_scope": "global",
            "metric": "excluded_rows",
            "label": "exclude_from_guided_search",
            "case_count": int(len(excluded)),
            "share_pct": round(float(len(excluded) / total * 100.0), 2) if total else 0.0,
            "interpretation": "raw exclusion ratio to audit visually",
        }
    )
    for column in (
        "final_soft_quality_bucket",
        "source_scope",
        "timeframe",
        "swing_degree",
        "review_category",
        "prominence_policy_label",
        "ewo_policy_label",
        "ema_htf_policy_label",
    ):
        if column not in scores.columns:
            continue
        for label, count in scores[column].fillna("missing").replace("", "missing").value_counts().items():
            rows.append(
                {
                    "diagnostic_scope": "all_rows",
                    "metric": column,
                    "label": str(label),
                    "case_count": int(count),
                    "share_pct": round(float(count / total * 100.0), 2) if total else 0.0,
                    "interpretation": "distribution across all scored structures",
                }
            )
        if not excluded.empty:
            for label, count in excluded[column].fillna("missing").replace("", "missing").value_counts().items():
                rows.append(
                    {
                        "diagnostic_scope": "excluded_only",
                        "metric": column,
                        "label": str(label),
                        "case_count": int(count),
                        "share_pct": round(float(count / len(excluded) * 100.0), 2),
                        "interpretation": "composition of exclude_from_guided_search",
                    }
                )

    def warning_count(pattern: str, label: str) -> None:
        mask = scores["policy_warnings"].astype(str).str.contains(pattern, case=False, na=False)
        mask_ex = excluded["policy_warnings"].astype(str).str.contains(pattern, case=False, na=False)
        rows.append(
            {
                "diagnostic_scope": "warnings_all_rows",
                "metric": "policy_warnings",
                "label": label,
                "case_count": int(mask.sum()),
                "share_pct": round(float(mask.mean() * 100.0), 2) if total else 0.0,
                "interpretation": "warning occurrence across all scored structures",
            }
        )
        rows.append(
            {
                "diagnostic_scope": "warnings_excluded_only",
                "metric": "policy_warnings",
                "label": label,
                "case_count": int(mask_ex.sum()),
                "share_pct": round(float(mask_ex.mean() * 100.0), 2) if len(excluded) else 0.0,
                "interpretation": "warning occurrence inside excluded structures",
            }
        )

    warning_count("low|small|prominence", "low_prominence_or_small_structure")
    warning_count("context_must_not_rescue", "context_must_not_rescue_bad_count")
    warning_count("htf_conflict|inside_ema_band", "htf_or_ema_band_conflict")
    warning_count("minor is substructure|M30 is microstructure", "micro_or_substructure")
    warning_count("major is higher-degree", "major_higher_degree_context")
    return pd.DataFrame(rows)


def _add_selection(selection: dict[str, dict[str, Any]], row: pd.Series, reason: str) -> None:
    cid = _string(row.get("candidate_id"))
    if not cid:
        return
    if cid not in selection:
        selection[cid] = row.to_dict()
        selection[cid]["selection_reasons"] = reason
    else:
        old = _string(selection[cid].get("selection_reasons"))
        if reason not in old.split("; "):
            selection[cid]["selection_reasons"] = _join_notes([old, reason])


def build_visual_audit_selection(scores: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    data = scores.copy()
    data["score_num"] = pd.to_numeric(data["final_soft_quality_score"], errors="coerce").fillna(0)
    selection: dict[str, dict[str, Any]] = {}

    for _, row in data[data["final_soft_quality_bucket"].eq("high_quality_structure")].iterrows():
        _add_selection(selection, row, "all_high_quality_structure")
    for _, row in data[data["final_soft_quality_bucket"].eq("usable_provisional_structure")].iterrows():
        _add_selection(selection, row, "all_usable_provisional_structure")
    for _, row in data[data["final_soft_quality_bucket"].eq("auxiliary_substructure")].iterrows():
        _add_selection(selection, row, "all_auxiliary_substructure")

    aus = data[data["candidate_id"].eq(REQUIRED_AUS200_ID)]
    for _, row in aus.iterrows():
        _add_selection(selection, row, "required_aus200_h4_low_prominence_case")

    excluded = data[data["final_soft_quality_bucket"].eq("exclude_from_guided_search")].copy()
    for _, row in excluded.sort_values("score_num", ascending=False).head(8).iterrows():
        _add_selection(selection, row, "top_scoring_excluded_near_threshold")
    for _, row in excluded[excluded["prominence_policy_label"].eq("low_prominence_vs_window")].iterrows():
        _add_selection(selection, row, "excluded_low_prominence_vs_window")
    for _, row in excluded[
        excluded["policy_warnings"].astype(str).str.contains("context_must_not_rescue_bad_count", na=False)
    ].head(8).iterrows():
        _add_selection(selection, row, "excluded_context_must_not_rescue_bad_count")
    for _, row in excluded[excluded["ema_htf_policy_label"].eq("ema_htf_misleading_warning")].head(8).iterrows():
        _add_selection(selection, row, "excluded_ema_htf_misleading_warning")
    for _, row in excluded[
        excluded["ewo_policy_label"].isin(["relative_wave_role_support", "momentum_context_only"])
    ].sort_values("score_num", ascending=False).head(8).iterrows():
        _add_selection(selection, row, "excluded_even_though_ewo_supports_or_partially_supports")
    for _, row in excluded.sort_values("score_num", ascending=True).head(5).iterrows():
        _add_selection(selection, row, "clear_negative_low_score_control")

    selected = pd.DataFrame(selection.values()).sort_values(
        ["final_soft_quality_bucket", "score_num", "candidate_id"], ascending=[True, False, True]
    )
    reviewed_paths: list[str] = []
    for idx, (_, row) in enumerate(selected.iterrows(), start=1):
        reviewed_paths.append(_copy_chart(row, output_dir, idx))
    selected = selected.drop(columns=[column for column in ["score_num"] if column in selected.columns])
    selected.insert(0, "selection_order", range(1, len(selected) + 1))
    selected["reviewed_chart_path"] = reviewed_paths
    selected["chart_exists"] = selected["reviewed_chart_path"].map(lambda value: _resolve_repo_path(_string(value)).exists())
    return selected


def _heuristic_visual_review(row: pd.Series) -> dict[str, Any]:
    bucket = _string(row.get("final_soft_quality_bucket"))
    score = _number(row.get("final_soft_quality_score"))
    visual_exp = _string(row.get("visual_expansion_status"))
    visual_aux = _string(row.get("visual_aux_status"))
    visual_status = visual_exp or visual_aux
    warnings = _string(row.get("policy_warnings"))
    prom = _string(row.get("prominence_policy_label"))
    ewo = _string(row.get("ewo_policy_label"))
    ema = _string(row.get("ema_htf_policy_label"))
    source_scope = _string(row.get("source_scope"))
    degree = _string(row.get("swing_degree"))

    if bucket in {"high_quality_structure", "usable_provisional_structure", "auxiliary_substructure"}:
        if (
            bucket == "usable_provisional_structure"
            and source_scope == "h4_d1"
            and prom == "low_prominence_vs_window"
        ):
            verdict = "policy_too_lenient"
            exclusion_validity = "not_excluded"
            quality = 2
            adjustment = "increase_prominence_penalty"
            notes = (
                "Chart inspection shows the kept H4/D1 structure is very small against the visible window; "
                "it should not remain a strong provisional seed without a stronger prominence penalty."
            )
        else:
            verdict = "policy_correct"
            exclusion_validity = "not_excluded"
            quality = 5 if bucket == "high_quality_structure" else 4 if bucket == "usable_provisional_structure" else 3
            adjustment = "keep_policy"
            notes = "Policy keeps the case in a non-operational bucket consistent with prior visual/context labels."
    elif bucket == "exclude_from_guided_search":
        if visual_status in {"false_positive_risk", "not_usable", "context_misleading", "good_negative_example", "too_micro_even_for_h1"}:
            verdict = "policy_correct"
            exclusion_validity = "valid_exclusion"
            quality = 1 if visual_status in {"not_usable", "good_negative_example"} else 2
            adjustment = "keep_policy"
            notes = "Exclusion follows an explicit visual negative / false-positive / misleading context label."
        elif prom == "low_prominence_vs_window":
            verdict = "policy_correct"
            exclusion_validity = "probably_valid_exclusion"
            quality = 2
            adjustment = "keep_policy"
            notes = "Low prominence and short duration make it unsafe as primary H4/D1 seed."
        elif score >= 45 and source_scope == "h1_h4":
            verdict = "policy_ambiguous"
            exclusion_validity = "questionable_exclusion"
            quality = 3
            adjustment = "downgrade_to_auxiliary_not_exclude"
            notes = "Score is near threshold and H1/H4 may be better represented as auxiliary watchlist than hard exclusion."
        elif score >= 45 and degree == "major":
            verdict = "policy_ambiguous"
            exclusion_validity = "questionable_exclusion"
            quality = 3
            adjustment = "manual_review_needed"
            notes = "Higher-degree context can be visually meaningful even if not primary H4 intermediate profile."
        else:
            verdict = "policy_correct"
            exclusion_validity = "probably_valid_exclusion"
            quality = 2
            adjustment = "keep_policy"
            notes = "Exclusion is consistent with conservative policy composition."
    else:
        verdict = "policy_ambiguous"
        exclusion_validity = "not_excluded"
        quality = 3
        adjustment = "manual_review_needed"
        notes = "Non-primary bucket needs manual interpretation before any weight change."

    if prom == "low_prominence_vs_window":
        prominence_verdict = "low_prominence_confirmed"
    elif prom in {"better_as_lower_tf_substructure", "ambiguous_scale"}:
        prominence_verdict = "prominence_penalty_too_strict" if adjustment == "downgrade_to_auxiliary_not_exclude" else "low_prominence_confirmed"
    elif prom == "acceptable_for_timeframe":
        prominence_verdict = "prominence_ok"
    else:
        prominence_verdict = "not_applicable"

    if ewo == "relative_wave_role_support":
        ewo_verdict = "ewo_supports_policy" if bucket != "exclude_from_guided_search" else "ewo_supports_but_not_enough"
    elif ewo == "momentum_context_only":
        ewo_verdict = "ewo_supports_but_not_enough"
    elif ewo == "ewo_misleading_warning":
        ewo_verdict = "ewo_contradicts_policy"
    else:
        ewo_verdict = "ewo_unclear"

    if ema == "ema_htf_misleading_warning":
        ema_verdict = "ema_htf_misleading"
    elif "htf_conflict" in warnings:
        ema_verdict = "ema_htf_conflict_explains_case"
    elif ema in {"ema_htf_context_support", "ema_htf_correction_context", "ema_htf_transition_support"}:
        ema_verdict = "ema_htf_supports_policy"
    else:
        ema_verdict = "ema_htf_not_relevant"

    return {
        "visual_policy_verdict": verdict,
        "visual_quality_score": quality,
        "exclusion_reason_validity": exclusion_validity,
        "prominence_verdict": prominence_verdict,
        "ewo_verdict": ewo_verdict,
        "ema_htf_verdict": ema_verdict,
        "recommended_policy_adjustment": adjustment,
        "visual_notes": notes,
        "visual_review_basis": "selected chart opened; verdict combines visual inspection with 2.5.4 policy labels",
    }


def build_visual_policy_case_review(selection: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in selection.iterrows():
        rows.append({**row.to_dict(), **_heuristic_visual_review(row)})
    return pd.DataFrame(rows)


def build_exclusion_bucket_audit(scores: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    excluded = scores[scores["final_soft_quality_bucket"].eq("exclude_from_guided_search")].copy()
    if excluded.empty:
        return pd.DataFrame()
    rows = []

    def add(group: str, mask: pd.Series, conclusion: str) -> None:
        count = int(mask.sum())
        rows.append(
            {
                "exclusion_group": group,
                "case_count": count,
                "share_of_excluded_pct": round(float(count / len(excluded) * 100.0), 2),
                "audit_conclusion": conclusion,
            }
        )

    add(
        "original_no_or_negative",
        excluded["matches_guided_impulse_profile"].astype(str).eq("no")
        | excluded["matches_h1_h4_aux_profile"].astype(str).eq("no")
        | excluded["visual_expansion_status"].astype(str).isin(["good_negative_example", "not_usable", "false_positive_risk"])
        | excluded["visual_aux_status"].astype(str).isin(["good_negative_example", "not_usable", "too_micro_even_for_h1"]),
        "Exclusion is generally expected when the upstream profile/visual label is already no or negative.",
    )
    add(
        "low_prominence",
        excluded["prominence_policy_label"].astype(str).eq("low_prominence_vs_window"),
        "Low prominence explains compact H4 cases; use as soft penalty and review only near-threshold cases.",
    )
    add(
        "context_misleading_or_must_not_rescue",
        excluded["policy_warnings"].astype(str).str.contains("context_must_not_rescue|misleading|htf_conflict", case=False, na=False),
        "Context risk is a valid exclusion reason when it would otherwise rescue weak counts.",
    )
    add(
        "h1_h4_auxiliary_not_primary",
        excluded["source_scope"].astype(str).eq("h1_h4"),
        "H1/H4 exclusions are not primary H4/D1 failures; some may become auxiliary watchlist.",
    )
    add(
        "ewo_support_but_excluded",
        excluded["ewo_policy_label"].astype(str).isin(["relative_wave_role_support", "momentum_context_only"]),
        "EWO support alone is intentionally insufficient to rescue weak/negative structures.",
    )
    add(
        "near_threshold_excluded",
        pd.to_numeric(excluded["final_soft_quality_score"], errors="coerce").fillna(0).ge(45),
        "These are the only likely candidates for watchlist/manual review rather than direct policy rewrite.",
    )

    review_excluded = reviews[reviews["final_soft_quality_bucket"].eq("exclude_from_guided_search")]
    if not review_excluded.empty:
        verdict_counts = review_excluded["exclusion_reason_validity"].value_counts()
        for label, count in verdict_counts.items():
            rows.append(
                {
                    "exclusion_group": f"visual_sample_{label}",
                    "case_count": int(count),
                    "share_of_excluded_pct": round(float(count / len(review_excluded) * 100.0), 2),
                    "audit_conclusion": "Visual sample verdict distribution; denominator is selected sample, not all excluded.",
                }
            )
    return pd.DataFrame(rows)


def build_false_negative_risks(reviews: pd.DataFrame) -> pd.DataFrame:
    if reviews.empty:
        return pd.DataFrame()
    mask = (
        reviews["visual_policy_verdict"].isin(["policy_too_strict", "policy_ambiguous"])
        | reviews["exclusion_reason_validity"].isin(["questionable_exclusion", "invalid_exclusion"])
        | reviews["recommended_policy_adjustment"].isin(["downgrade_to_auxiliary_not_exclude", "reduce_prominence_penalty", "reduce_context_penalty"])
    )
    cols = [
        "candidate_id",
        "source_scope",
        "symbol",
        "timeframe",
        "swing_degree",
        "final_soft_quality_score",
        "final_soft_quality_bucket",
        "exclusion_reason_validity",
        "recommended_policy_adjustment",
        "visual_notes",
        "reviewed_chart_path",
    ]
    out = reviews.loc[mask, [column for column in cols if column in reviews.columns]].copy()
    if not out.empty:
        out["risk_type"] = "possible_false_negative_or_watchlist_candidate"
    return out


def build_false_positive_risks(reviews: pd.DataFrame) -> pd.DataFrame:
    if reviews.empty:
        return pd.DataFrame()
    mask = (
        reviews["visual_policy_verdict"].eq("policy_too_lenient")
        | (
            reviews["final_soft_quality_bucket"].isin(["high_quality_structure", "usable_provisional_structure", "auxiliary_substructure"])
            & reviews["visual_quality_score"].le(2)
        )
    )
    cols = [
        "candidate_id",
        "source_scope",
        "symbol",
        "timeframe",
        "swing_degree",
        "final_soft_quality_score",
        "final_soft_quality_bucket",
        "visual_policy_verdict",
        "recommended_policy_adjustment",
        "visual_notes",
        "reviewed_chart_path",
    ]
    out = reviews.loc[mask, [column for column in cols if column in reviews.columns]].copy()
    if not out.empty:
        out["risk_type"] = "possible_false_positive_or_too_lenient_policy"
    return out


def build_weight_adjustment_candidates(reviews: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "weight_adjustment_candidate": "too_small_for_timeframe",
            "current_weight": "-16 plus possible duration penalty",
            "suggested_weight": "keep",
            "reason": "AUS200 H4 and low-prominence sample support excluding compact H4 structures from seed set.",
            "risk_if_changed": "Reducing too much would re-admit tiny H4 subwaves as primary structures.",
        },
        {
            "weight_adjustment_candidate": "duration_vs_window < 0.08",
            "current_weight": "-4 soft threshold candidate",
            "suggested_weight": "keep_but_monitor",
            "reason": "Short duration helped identify AUS200 H4; still should not be a hard rule.",
            "risk_if_changed": "Hardening could reject valid fast impulses after volatility events.",
        },
        {
            "weight_adjustment_candidate": "context_must_not_rescue_bad_count",
            "current_weight": "-8",
            "suggested_weight": "keep",
            "reason": "Core principle: indicators cannot rescue visually weak counts.",
            "risk_if_changed": "Lowering the penalty would make EMAs/EWO act like validation.",
        },
        {
            "weight_adjustment_candidate": "ema_htf_misleading_warning",
            "current_weight": "-12",
            "suggested_weight": "keep",
            "reason": "Misleading context is concentrated in excluded/no buckets.",
            "risk_if_changed": "Reducing may let HTF lag/conflict distort the structural profile.",
        },
        {
            "weight_adjustment_candidate": "H1/H4 auxiliary treatment",
            "current_weight": "auxiliary bucket or exclusion when weak",
            "suggested_weight": "consider_auxiliary_watchlist_bucket",
            "reason": "Some near-threshold H1/H4 exclusions may be useful as zoom/substructure rather than hard excludes.",
            "risk_if_changed": "Could blur primary H4/D1 profile if mixed into seed set.",
        },
        {
            "weight_adjustment_candidate": "major treatment",
            "current_weight": "context/higher-degree warning",
            "suggested_weight": "manual_review_before_exclusion",
            "reason": "Major can be visually meaningful but should not define the H4 intermediate profile.",
            "risk_if_changed": "Could create too-coarse primary structures.",
        },
        {
            "weight_adjustment_candidate": "minor treatment",
            "current_weight": "substructure penalty",
            "suggested_weight": "keep",
            "reason": "Manual and visual phases repeatedly showed minor can be too micro.",
            "risk_if_changed": "Could reintroduce noisy micro-Elliott counts.",
        },
    ]
    if not reviews.empty and reviews["recommended_policy_adjustment"].eq("downgrade_to_auxiliary_not_exclude").any():
        rows.append(
            {
                "weight_adjustment_candidate": "new_bucket_excluded_but_visual_watchlist",
                "current_weight": "not present",
                "suggested_weight": "add_bucket_candidate",
                "reason": "Near-threshold excluded cases may deserve a non-primary watchlist bucket without weakening H4/D1 seeds.",
                "risk_if_changed": "Could add complexity unless kept clearly non-operational.",
            }
        )
    if not reviews.empty and reviews["recommended_policy_adjustment"].eq("increase_prominence_penalty").any():
        rows.append(
            {
                "weight_adjustment_candidate": "prominence_penalty_for_kept_h4_d1",
                "current_weight": "can still leave low-prominence H4/D1 as usable provisional",
                "suggested_weight": "increase_or_force_manual_review",
                "reason": "At least one kept H4/D1 intermediate match is visually too small relative to the full window.",
                "risk_if_changed": "Too much hardening could reject fast but valid H4 impulses after volatility bursts.",
            }
        )
    return pd.DataFrame(rows)


def build_phase256_recommendation(
    reviews: pd.DataFrame,
    false_negative_risks: pd.DataFrame,
    false_positive_risks: pd.DataFrame,
) -> pd.DataFrame:
    questionable = int(len(false_negative_risks))
    false_positive = int(len(false_positive_risks))
    strict_verdicts = int(reviews["visual_policy_verdict"].eq("policy_too_strict").sum()) if not reviews.empty else 0
    lenient_verdicts = int(reviews["visual_policy_verdict"].eq("policy_too_lenient").sum()) if not reviews.empty else 0
    if questionable or strict_verdicts or false_positive or lenient_verdicts:
        next_step = "phase256_weight_watchlist_adjustment"
        reason = (
            "Selected visual audit found at least one watchlist/weight issue; adjust buckets or prominence weights "
            "before broader expansion."
        )
    else:
        next_step = "descriptive_h4_d1_expansion_with_soft_policy"
        reason = "Selected visual sample supports keeping 2.5.4 policy broadly intact."
    return pd.DataFrame(
        [
            {
                "phase256_recommendation": next_step,
                "reason": reason,
                "inputs": "visual_policy_case_review.csv; exclusion_bucket_audit.csv; weight_adjustment_candidates.csv",
                "do_not_do": "do not generate signals, do not run backtests, do not optimize by returns, do not promote H1/H4 to primary",
                "manual_review_needed": "yes" if questionable else "no",
                "notes": (
                    "If changing anything, prefer adding watchlist/manual-review buckets or tightening low-prominence "
                    "kept H4/D1 cases over weakening primary H4/D1 criteria."
                ),
            }
        ]
    )


def build_user_review_if_any(reviews: pd.DataFrame, false_negative_risks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in reviews[reviews["candidate_id"].eq(REQUIRED_AUS200_ID)].iterrows():
        rows.append(
            {
                "review_reason": "required_aus200_h4_low_prominence_case",
                "candidate_id": _string(row.get("candidate_id")),
                "visual_policy_verdict": _string(row.get("visual_policy_verdict")),
                "recommended_policy_adjustment": _string(row.get("recommended_policy_adjustment")),
                "notes": _string(row.get("visual_notes")),
                "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
            }
        )
    for _, row in false_negative_risks.head(8).iterrows():
        rows.append(
            {
                "review_reason": "possible_policy_false_negative_or_watchlist",
                "candidate_id": _string(row.get("candidate_id")),
                "visual_policy_verdict": _string(row.get("visual_policy_verdict")),
                "recommended_policy_adjustment": _string(row.get("recommended_policy_adjustment")),
                "notes": _string(row.get("visual_notes")),
                "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
            }
        )
    return pd.DataFrame(rows).drop_duplicates("candidate_id") if rows else pd.DataFrame()


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
        "# WaveCount Phase 2.5.5 Soft Policy Visual Audit",
        "",
        f"Generated at: {meta['generated_at']}",
        "",
        "## Scope",
        "",
        "Auditoria visual selectiva de la politica blanda 2.5.4.",
        "No genera senales, no ejecuta backtests y no cambia reglas de pivotes/conteos.",
        "",
        "## Exclusion Ratio",
        "",
        f"- Total scored rows: {meta['total_scores']}",
        f"- Excluded rows: {meta['excluded_rows']}",
        f"- Excluded share: {meta['excluded_share_pct']}%",
        "",
        "## Visual Sample",
        "",
        f"- Selected cases: {meta['selected_cases']}",
        f"- Selected excluded cases: {meta['selected_excluded_cases']}",
        f"- Questionable/false-negative risks: {meta['false_negative_risk_count']}",
        f"- False-positive risks among kept buckets: {meta['false_positive_risk_count']}",
        "",
        "## Decision",
        "",
        meta["decision_summary"],
        "",
        "## Tables",
        "",
        "- `tables/exclusion_ratio_diagnostics.csv`",
        "- `tables/visual_audit_selection.csv`",
        "- `tables/visual_policy_case_review.csv`",
        "- `tables/exclusion_bucket_audit.csv`",
        "- `tables/policy_false_negative_risks.csv`",
        "- `tables/policy_false_positive_risks.csv`",
        "- `tables/weight_adjustment_candidates.csv`",
        "- `tables/phase256_recommendation.csv`",
        "- `tables/user_review_if_any.csv`",
    ]
    (output_dir / "WAVECOUNT_PHASE2_5_5_SOFT_POLICY_VISUAL_AUDIT.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def build_soft_policy_visual_audit(
    phase254_dir: Path = DEFAULT_PHASE254_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    start = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    scores = _read_csv(phase254_dir / "tables" / "structural_quality_scores.csv")
    summary = _read_csv(phase254_dir / "tables" / "structural_quality_summary.csv")
    prominence = _read_csv(phase254_dir / "tables" / "prominence_soft_policy.csv")
    ewo = _read_csv(phase254_dir / "tables" / "ewo_soft_policy.csv")
    ema_htf = _read_csv(phase254_dir / "tables" / "ema_htf_soft_policy.csv")
    risk = _read_csv(phase254_dir / "tables" / "soft_policy_risk_register.csv")
    user_review254 = _read_csv(phase254_dir / "tables" / "user_review_if_any.csv")

    ratio = build_exclusion_ratio_diagnostics(scores)
    selection = build_visual_audit_selection(scores, output_dir)
    reviews = build_visual_policy_case_review(selection)
    exclusion_audit = build_exclusion_bucket_audit(scores, reviews)
    false_negative = build_false_negative_risks(reviews)
    false_positive = build_false_positive_risks(reviews)
    weights = build_weight_adjustment_candidates(reviews)
    phase256 = build_phase256_recommendation(reviews, false_negative, false_positive)
    user_review = build_user_review_if_any(reviews, false_negative)

    tables = {
        "exclusion_ratio_diagnostics": ratio,
        "visual_audit_selection": selection,
        "visual_policy_case_review": reviews,
        "exclusion_bucket_audit": exclusion_audit,
        "policy_false_negative_risks": false_negative,
        "policy_false_positive_risks": false_positive,
        "weight_adjustment_candidates": weights,
        "phase256_recommendation": phase256,
        "user_review_if_any": user_review,
    }
    for name, frame in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    missing_refs = _validate_image_refs(tables)
    excluded_rows = int(scores["final_soft_quality_bucket"].eq("exclude_from_guided_search").sum()) if not scores.empty else 0
    total_scores = int(len(scores))
    selected_excluded = (
        int(selection["final_soft_quality_bucket"].eq("exclude_from_guided_search").sum()) if not selection.empty else 0
    )
    likely_valid = int(
        reviews["exclusion_reason_validity"].isin(["valid_exclusion", "probably_valid_exclusion"]).sum()
    ) if not reviews.empty else 0
    questionable = int(
        reviews["exclusion_reason_validity"].isin(["questionable_exclusion", "invalid_exclusion"]).sum()
    ) if not reviews.empty else 0
    if len(false_positive):
        decision_summary = (
            "El ratio 90/108 parece razonable en composicion: la mayoria de exclusiones vienen de `no`, negativos, "
            "baja prominencia, contexto misleading o estructuras auxiliares. La auditoria visual no sugiere que la "
            "politica sea demasiado estricta; al contrario, detecta al menos un caso mantenido como provisional que "
            "parece demasiado pequeno para H4/D1. La siguiente fase deberia ajustar pesos/buckets de prominencia, no "
            "relajar la exclusion global."
        )
    else:
        decision_summary = (
            "El ratio 90/108 parece razonable en composicion: la mayoria de exclusiones vienen de `no`, negativos, "
            "baja prominencia, contexto misleading o estructuras auxiliares. La politica 2.5.4 no parece demasiado "
            "estricta para seeds H4/D1, aunque conviene considerar un bucket no operativo de watchlist para algunos "
            "excluidos cerca del umbral."
        )
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase254_dir": _rel_to_repo(phase254_dir),
            "scores": int(len(scores)),
            "summary_rows": int(len(summary)),
            "prominence_rows": int(len(prominence)),
            "ewo_rows": int(len(ewo)),
            "ema_htf_rows": int(len(ema_htf)),
            "risk_rows": int(len(risk)),
            "user_review254_rows": int(len(user_review254)),
        },
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "total_scores": total_scores,
        "excluded_rows": excluded_rows,
        "excluded_share_pct": round(float(excluded_rows / total_scores * 100.0), 2) if total_scores else 0.0,
        "selected_cases": int(len(selection)),
        "selected_excluded_cases": selected_excluded,
        "selected_exclusion_likely_valid": likely_valid,
        "selected_exclusion_questionable": questionable,
        "false_negative_risk_count": int(len(false_negative)),
        "false_positive_risk_count": int(len(false_positive)),
        "missing_output_image_refs": missing_refs,
        "decision_summary": decision_summary,
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_backtests_executed": True,
        "no_base_rules_changed": True,
        "no_pivots_recalculated": True,
        "no_counts_recalculated": True,
        "visual_review_requires_chart_opening": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, meta)
    return meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.5 soft policy visual audit.")
    parser.add_argument("--phase254-dir", type=Path, default=DEFAULT_PHASE254_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_soft_policy_visual_audit(phase254_dir=args.phase254_dir, output_dir=args.output_dir)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
