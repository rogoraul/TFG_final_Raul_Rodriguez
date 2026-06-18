from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_READINESS_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_5_pre_phase25_closure_2026-05-24"
)
DEFAULT_H4_CLOSURE_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_4_h4_d1_visual_closure_2026-05-23"
)
DEFAULT_CONTEXT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_2_context_quality_audit_2026-05-23"
)
DEFAULT_CORRECTIONS_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_4_contextual_corrections_2026-05-24"
)
DEFAULT_WAVE5_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_1_wave5_endpoint_2026-05-21"
DEFAULT_PARTIAL123_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_partial123_2026-05-21"
DEFAULT_DEGREE_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_3_degree_calibration_2026-05-23"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_0_guided_context_score_2026-05-24"
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


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
    text = _string(value).strip().lower()
    return text in {"true", "1", "yes", "y", "si", "sí"}


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


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        label_bits = [
            _string(row.get("candidate_id")),
            _string(row.get("structure_type")),
            _string(row.get("guided_quality_bucket")),
            _string(row.get("phase25_allowed_use")),
        ]
        label = " | ".join(bit for bit in label_bits if bit) or f"fila {idx + 1}"
        lines.append(f"## {idx + 1}. {label}")
        for col in (
            "score_reasons",
            "score_penalties",
            "ewo_role_reasons",
            "phase251_reason",
            "notes",
        ):
            value = _string(row.get(col))
            if value:
                lines.extend(["", value])
        for col in row.index:
            if "path" not in col.lower():
                continue
            value = _string(row.get(col))
            if not value.lower().endswith(".png"):
                continue
            path = _resolve_repo_path(value)
            lines.extend(["", f"![{path.name}]({path.resolve().as_posix()})"])
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    return {str(k): int(v) for k, v in frame[column].fillna("missing").value_counts().to_dict().items()}


def _normalise_id_frame(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    frame = frame.copy()
    if "candidate_id" not in frame.columns:
        frame["candidate_id"] = ""
    frame["candidate_id"] = frame["candidate_id"].astype(str)
    frame["source_phase"] = prefix
    frame["source_candidate_id"] = frame["candidate_id"]
    return frame


def _timeframe_policy(timeframe: str, source_scope: str) -> str:
    if source_scope == "h4_d1" or timeframe.upper() == "H4":
        return "primary_h4_d1"
    if timeframe.upper() == "H1":
        return "auxiliary_h1_h4"
    if timeframe.upper() == "M30":
        return "microstructure_m30_h1"
    return "auxiliary_h1_h4"


def _structure_type(row: pd.Series, *, is_abc: bool = False) -> str:
    if is_abc:
        if _string(row.get("contextual_policy")) == "exclude_not_correction":
            return "invalid_or_negative"
        return "abc_correction"
    category = _string(row.get("review_category"))
    decision = _string(row.get("final_phase23_decision"))
    status = _string(row.get("manual_visual_status")) or _string(row.get("visual_review_status"))
    if decision in {"exclude_from_phase25_rules", "keep_as_negative_example"}:
        return "invalid_or_negative"
    if "invalid" in status or "false" in status or "not_usable" in status:
        return "invalid_or_negative"
    if category == "impulse":
        return "impulse"
    if category == "partial_123":
        return "partial_123"
    if category == "abc":
        return "abc_correction"
    return "ambiguous"


def _phase25_allowed_use(row: pd.Series, *, is_abc: bool = False) -> str:
    if is_abc:
        policy = _string(row.get("contextual_policy"))
        return {
            "usable_contextual_correction": "soft_context",
            "manual_contextual_review_only": "manual_review_only",
            "experimental_unknown_parent": "experimental",
            "exclude_not_correction": "exclude",
        }.get(policy, "experimental")

    category = _string(row.get("review_category"))
    decision = _string(row.get("final_phase23_decision"))
    degree = _string(row.get("swing_degree"))
    timeframe_policy = _string(row.get("timeframe_policy"))
    if decision in {"exclude_from_phase25_rules", "keep_as_negative_example"}:
        return "exclude"
    if category == "partial_123":
        if decision == "keep_as_good_example":
            return "soft_context"
        return "manual_review_only" if decision == "keep_as_ambiguous_example" else "experimental"
    if category == "impulse":
        if decision == "keep_as_good_example" and timeframe_policy == "primary_h4_d1" and degree == "intermediate":
            return "candidate_structure"
        if decision in {"keep_as_good_example", "keep_as_ambiguous_example"}:
            return "soft_context"
        return "manual_review_only"
    return "experimental"


def _ema_label(row: pd.Series) -> tuple[str, int, list[str]]:
    usefulness = _string(row.get("ema_usefulness")) or _string(row.get("ema_context_usefulness"))
    band = _string(row.get("end_ltf_price_vs_ema_band"))
    transition = _string(row.get("end_ltf_transition_state"))
    delta = 0
    notes: list[str] = []
    label = "ema_unclear"
    if usefulness in {"useful_quality_filter", "useful_trend_context", "useful"}:
        delta += 6 if usefulness == "useful_quality_filter" else 4
        label = "ema_supports_context"
        notes.append(usefulness)
    elif usefulness in {"partially_useful", "neutral"}:
        delta += 2 if usefulness == "partially_useful" else 0
        label = "ema_partial_or_neutral"
        notes.append(usefulness)
    elif usefulness in {"noisy", "misleading", "not_useful"}:
        delta -= 8 if usefulness == "misleading" else 4
        label = "ema_noisy_or_misleading"
        notes.append(usefulness)
    if band == "inside_band":
        delta -= 3
        notes.append("inside_ema_band_adds_ambiguity")
        if label == "ema_supports_context":
            label = "ema_supports_but_inside_band"
    if "transition" in transition and transition != "no_transition":
        delta += 3
        notes.append(f"transition={transition}")
        if label == "ema_unclear":
            label = "ema_transition_context"
    return label, delta, notes


def _htf_label(row: pd.Series) -> tuple[str, int, list[str]]:
    trend_label = _string(row.get("trend_context_label"))
    review = _string(row.get("context_review_status"))
    usefulness = _string(row.get("htf_usefulness")) or _string(row.get("d1_context_usefulness"))
    delta = 0
    notes: list[str] = []
    label = "unclear"
    if trend_label == "impulse_with_htf":
        label = "impulse_with_htf"
        delta += 6
    elif trend_label == "correction_against_htf":
        label = "correction_against_htf"
        delta += 4
    elif "transition" in trend_label:
        label = "transition_structure"
        delta += 3
    elif trend_label == "conflict_with_htf":
        label = "conflict_suspicious"
        delta -= 8
    if review == "context_conflicts_but_explains":
        label = "conflict_explained"
        delta += 2
    elif review == "context_flags_transition":
        label = "transition_structure"
        delta += 2
    elif review == "context_conflicts_suspicious":
        label = "conflict_suspicious"
        delta -= 8
    elif review == "context_misleading":
        label = "conflict_suspicious"
        delta -= 10
    if usefulness == "misleading_if_hard_filter":
        notes.append("htf_useful_only_if_soft")
    elif usefulness in {"useful_regime_filter", "useful_correction_context", "useful_transition_context", "useful"}:
        notes.append(usefulness)
    elif usefulness in {"misleading", "conflict_suspicious"}:
        delta -= 5
        notes.append(usefulness)
    return label, delta, notes


def _ewo_role(row: pd.Series) -> tuple[str, str, str, int]:
    candidate = _string(row.get("candidate_id"))
    category = _string(row.get("review_category"))
    rule = _string(row.get("phase25_rule_candidate"))
    usefulness = _string(row.get("ewo_usefulness")) or _string(row.get("ewo_context_usefulness"))
    direction = _string(row.get("end_ltf_ewo_5_35_direction"))
    slope = _number(row.get("end_ltf_ewo_5_35_slope"), 0.0)
    reasons: list[str] = []
    label = "ewo_role_context_unavailable"
    support = "not_available"
    penalty = 0

    if not any([rule, usefulness, direction]):
        return label, support, "No leg-level EWO information available in current artifacts.", penalty

    if "ewo_wave3_momentum_support" in rule:
        label = "ewo_wave3_momentum_support"
        support = "supports_wave_role"
        penalty = 0
        reasons.append("Existing 2.4.2 audit marked EWO as wave-3 momentum support.")
    elif "ewo_wave5_divergence_warning" in rule:
        label = "ewo_wave5_divergence_warning"
        support = "partially_supports"
        penalty = 0
        reasons.append("Existing 2.4.2 audit marked possible wave-5 momentum warning.")
    elif "ewo_correction_momentum_warning" in rule:
        label = "ewo_correction_momentum_warning"
        support = "partially_supports"
        penalty = 0
        reasons.append("Existing 2.4.2 audit marked correction momentum warning.")
    elif category == "partial_123":
        label = "ewo_partial123_momentum_context"
        support = "partially_supports" if "useful" in usefulness else "unclear"
        reasons.append("Partial 1-2-3 uses EWO only as provisional momentum context.")
    elif category == "impulse":
        label = "ewo_impulse_momentum_context"
        support = "partially_supports" if "useful" in usefulness else "unclear"
        reasons.append("Impulse has EWO context, but current artifacts do not expose per-leg thresholds.")
    else:
        label = "ewo_contextual_proxy"
        support = "unclear"
        reasons.append("EWO available only as end-of-candidate context.")

    if usefulness in {"useful_for_wave_role", "useful_for_momentum_phase", "useful_for_momentum_only"}:
        if support == "unclear":
            support = "partially_supports"
        if usefulness == "useful_for_wave_role" and support != "supports_wave_role":
            support = "supports_wave_role"
        reasons.append(usefulness)
    elif usefulness in {"noisy", "misleading"}:
        support = "contradicts" if usefulness == "misleading" else "unclear"
        penalty = 8 if usefulness == "misleading" else 4
        reasons.append(usefulness)
    elif usefulness == "unclear":
        support = "unclear"
        reasons.append("ewo_unclear")

    if direction:
        reasons.append(f"end_ewo_direction={direction}")
    if slope:
        reasons.append(f"end_ewo_slope={slope:.6g}")
    if "abc" in candidate:
        label = "ewo_correction_context_not_leg_level"
        if support == "supports_wave_role":
            support = "partially_supports"
        reasons.append("ABC correction lacks leg-level EWO thresholds in 2.5.0.")
    return label, support, "; ".join(reasons), penalty


def _score_candidate(row: pd.Series) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []
    penalties: list[str] = []

    timeframe_policy = _string(row.get("timeframe_policy"))
    degree = _string(row.get("swing_degree"))
    degree_policy = _string(row.get("degree_policy"))
    decision = _string(row.get("final_phase23_decision"))
    structure = _string(row.get("structure_type"))
    allowed_use = _string(row.get("phase25_allowed_use"))
    visual_status = _string(row.get("manual_visual_status")) or _string(row.get("visual_review_status"))
    visual_score = _number(row.get("visual_quality_score"), 3)

    if timeframe_policy == "primary_h4_d1":
        score += 12
        reasons.append("H4/D1 primary base")
    elif timeframe_policy == "auxiliary_h1_h4":
        score += 4
        reasons.append("H1/H4 auxiliary")
    elif timeframe_policy == "microstructure_m30_h1":
        score -= 10
        penalties.append("M30/H1 microstructure")

    if degree == "intermediate":
        score += 10
        reasons.append("intermediate primary degree")
    elif degree == "major":
        score += 5
        reasons.append("major as context/higher degree")
    elif degree == "minor":
        score -= 8
        penalties.append("minor substructure only")

    if "degree_not_discriminative" in degree_policy:
        score -= 8
        penalties.append("degree not discriminative")
    if "too_micro" in degree_policy or visual_status == "too_micro":
        score -= 8
        penalties.append("too micro for primary count")

    if decision == "keep_as_good_example":
        score += 20
        reasons.append("2.3.4 keep_as_good_example")
    elif decision == "keep_as_ambiguous_example":
        score += 5
        reasons.append("2.3.4 ambiguous but useful")
    elif decision == "keep_as_negative_example":
        score -= 20
        penalties.append("2.3.4 negative example")
    elif decision == "exclude_from_phase25_rules":
        score -= 45
        penalties.append("2.3.4 excluded from Phase 2.5")

    score += int((visual_score - 3) * 5)
    if visual_score >= 4:
        reasons.append(f"visual quality {visual_score:g}")
    elif visual_score <= 2:
        penalties.append(f"low visual quality {visual_score:g}")

    if structure == "impulse":
        score += 5
        reasons.append("impulse candidate")
    elif structure == "partial_123":
        penalties.append("partial 1-2-3 remains provisional")
    elif structure == "abc_correction":
        penalties.append("ABC requires contextual parent")
    elif structure == "invalid_or_negative":
        score -= 40
        penalties.append("invalid_or_negative structure")

    ema_label, ema_delta, ema_notes = _ema_label(row)
    htf_label, htf_delta, htf_notes = _htf_label(row)
    ewo_label, ewo_support, ewo_reasons, ewo_penalty = _ewo_role(row)
    score += ema_delta + htf_delta - ewo_penalty
    if ema_delta > 0:
        reasons.append(f"EMA context +{ema_delta}: {'; '.join(ema_notes)}")
    elif ema_delta < 0:
        penalties.append(f"EMA context {ema_delta}: {'; '.join(ema_notes)}")
    if htf_delta > 0:
        reasons.append(f"HTF context +{htf_delta}: {htf_label}; {'; '.join(htf_notes)}")
    elif htf_delta < 0:
        penalties.append(f"HTF context {htf_delta}: {htf_label}; {'; '.join(htf_notes)}")
    if ewo_support == "supports_wave_role":
        score += 8
        reasons.append("EWO supports wave role")
    elif ewo_support == "partially_supports":
        score += 4
        reasons.append("EWO partially supports role")
    elif ewo_support == "contradicts":
        score -= 8
        penalties.append("EWO contradicts or misleads")

    wave5 = _string(row.get("wave5_diagnostic")) or _string(row.get("wave5_endpoint_status"))
    if wave5 in {"clean_or_acceptable"}:
        score += 4
        reasons.append("wave5 clean/acceptable")
    elif wave5 in {"endpoint_uncertain", "premature_wave5_completion", "truncated_fifth_candidate"}:
        score -= 5
        penalties.append(f"wave5 provisional: {wave5}")

    partial = _string(row.get("partial123_diagnostic")) or _string(row.get("partial123_status"))
    if partial == "valid_partial_123":
        score += 6
        reasons.append("partial 1-2-3 visually valid")
    elif partial == "partial_123_provisional":
        score += 2
        reasons.append("partial 1-2-3 provisional")
    elif partial in {"partial_123_too_lax", "belongs_to_prior_wave_45"}:
        score -= 12
        penalties.append(partial)
    elif partial == "invalidated_after_3":
        score -= 20
        penalties.append("partial invalidated after 3")
    elif partial == "ambiguous_partial":
        score -= 5
        penalties.append("ambiguous partial")

    contextual_policy = _string(row.get("abc_contextual_policy")) or _string(row.get("contextual_policy"))
    if contextual_policy == "usable_contextual_correction":
        score += 12
        reasons.append("ABC has contextual parent/regime")
    elif contextual_policy == "manual_contextual_review_only":
        score -= 2
        penalties.append("ABC manual review only")
    elif contextual_policy == "experimental_unknown_parent":
        score -= 12
        penalties.append("ABC unknown parent")
    elif contextual_policy == "exclude_not_correction":
        score -= 45
        penalties.append("ABC excluded as not correction")

    context_review = _string(row.get("context_review_status"))
    if context_review == "context_should_not_rescue_count":
        score -= 25
        penalties.append("context must not rescue this count")
    elif context_review == "context_confirms_good_count":
        score += 8
        reasons.append("context confirms good count")
    elif context_review == "context_explains_ambiguity":
        score += 2
        reasons.append("context explains ambiguity")
    elif context_review in {"context_misleading", "context_conflicts_suspicious"}:
        score -= 12
        penalties.append(context_review)

    if _boolish(row.get("context_must_not_rescue_bad_count")):
        score -= 20
        penalties.append("context_must_not_rescue_bad_count")

    score_cap = 100
    quality_filter = _string(row.get("quality_filter_candidate"))
    if context_review in {"context_misleading", "context_conflicts_suspicious"}:
        score_cap = min(score_cap, 60)
        penalties.append("score capped because context is misleading/suspicious")
    if context_review == "context_should_not_rescue_count" or _boolish(row.get("context_must_not_rescue_bad_count")):
        score_cap = min(score_cap, 45)
        penalties.append("score capped because context must not rescue the count")
    if quality_filter in {"no_misleading", "no_too_noisy"}:
        score_cap = min(score_cap, 50)
        penalties.append(f"score capped by quality_filter_candidate={quality_filter}")

    forced_exclude = allowed_use == "exclude" or decision in {"exclude_from_phase25_rules", "keep_as_negative_example"}
    if contextual_policy == "exclude_not_correction" or structure == "invalid_or_negative":
        forced_exclude = True

    score = max(0, min(score_cap, int(round(score))))
    if forced_exclude:
        bucket = "exclude"
    elif allowed_use == "experimental" or score < 40:
        bucket = "experimental_only" if score >= 30 else "exclude"
    elif score >= 75:
        bucket = "high_quality_context"
    elif score >= 55:
        bucket = "usable_but_provisional"
    else:
        bucket = "ambiguous_context"

    return {
        "guided_quality_score": score,
        "guided_quality_bucket": bucket,
        "score_reasons": "; ".join(reasons),
        "score_penalties": "; ".join(penalties),
        "ewo_wave_role_label": ewo_label,
        "ewo_role_support": ewo_support,
        "ewo_role_reasons": ewo_reasons,
        "ewo_role_penalty": ewo_penalty,
        "ema_context_label": ema_label,
        "ema_context_score_delta": ema_delta,
        "htf_ltf_alignment_label": htf_label,
        "htf_context_score_delta": htf_delta,
    }


def _ready_for_phase251(row: pd.Series) -> dict[str, str]:
    bucket = _string(row.get("guided_quality_bucket"))
    structure = _string(row.get("structure_type"))
    allowed = _string(row.get("phase25_allowed_use"))
    timeframe_policy = _string(row.get("timeframe_policy"))
    degree = _string(row.get("swing_degree"))
    contextual_policy = _string(row.get("abc_contextual_policy"))

    if bucket == "exclude" or allowed == "exclude":
        return {
            "ready_for_phase251_search": "no",
            "phase251_reason": "Excluded by previous audit or guided score.",
            "suggested_next_search_mode": "do_not_search",
        }
    if bucket == "high_quality_context" and structure == "impulse" and timeframe_policy == "primary_h4_d1" and degree == "intermediate":
        return {
            "ready_for_phase251_search": "yes",
            "phase251_reason": "High-quality H4/D1 intermediate impulse context.",
            "suggested_next_search_mode": "search_h4_intermediate_impulse",
        }
    if structure == "abc_correction" and contextual_policy == "usable_contextual_correction":
        return {
            "ready_for_phase251_search": "manual_review",
            "phase251_reason": "ABC is usable only as contextual correction.",
            "suggested_next_search_mode": "search_h4_correction_context",
        }
    if degree == "major" and bucket in {"high_quality_context", "usable_but_provisional"}:
        return {
            "ready_for_phase251_search": "manual_review",
            "phase251_reason": "Major can guide higher-degree context but should not dominate automatically.",
            "suggested_next_search_mode": "search_higher_degree_major_context",
        }
    if timeframe_policy in {"auxiliary_h1_h4", "microstructure_m30_h1"} and bucket != "exclude":
        return {
            "ready_for_phase251_search": "manual_review",
            "phase251_reason": "Auxiliary timeframe/substructure only.",
            "suggested_next_search_mode": "search_auxiliary_substructure",
        }
    if bucket in {"usable_but_provisional", "ambiguous_context", "experimental_only"}:
        return {
            "ready_for_phase251_search": "manual_review",
            "phase251_reason": "Useful as context but requires review or remains experimental.",
            "suggested_next_search_mode": "do_not_search" if bucket == "experimental_only" else "search_auxiliary_substructure",
        }
    return {
        "ready_for_phase251_search": "no",
        "phase251_reason": "No clear Phase 2.5.1 search use.",
        "suggested_next_search_mode": "do_not_search",
    }


def _prepare_context_candidates(frame: pd.DataFrame, *, scope: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = _normalise_id_frame(frame, "2.4.2_context_quality")
    out["source_scope"] = scope
    out["timeframe_policy"] = out["timeframe"].map(lambda value: _timeframe_policy(_string(value), scope))
    out["structure_type"] = out.apply(_structure_type, axis=1)
    out["phase25_allowed_use"] = out.apply(_phase25_allowed_use, axis=1)
    out["context_must_not_rescue_bad_count"] = out["context_review_status"].astype(str).eq(
        "context_should_not_rescue_count"
    )
    return out


def _merge_diagnostics(frame: pd.DataFrame, wave5: pd.DataFrame, partial123: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if not wave5.empty:
        cols = [
            "candidate_id",
            "wave5_endpoint_status",
            "proposed_endpoint_classification",
            "future_more_extreme_found",
            "post_wave5_extension_vs_wave5",
        ]
        available = [col for col in cols if col in wave5.columns]
        if "candidate_id" in available:
            out = out.merge(wave5[available].drop_duplicates("candidate_id"), on="candidate_id", how="left", suffixes=("", "_diag"))
            for col in available:
                if col == "candidate_id":
                    continue
                diag_col = f"{col}_diag"
                if diag_col not in out.columns:
                    continue
                if col not in out.columns:
                    out[col] = out[diag_col]
                else:
                    out[col] = out[col].where(out[col].notna() & (out[col].astype(str) != ""), out[diag_col])
                out = out.drop(columns=[diag_col])
    if not partial123.empty:
        cols = [
            "candidate_id",
            "partial123_status",
            "live_state",
            "wave3_too_weak",
            "post_3_invalidates",
            "post_3_confirms",
            "manual_final_label",
        ]
        available = [col for col in cols if col in partial123.columns]
        if "candidate_id" in available:
            out = out.merge(partial123[available].drop_duplicates("candidate_id"), on="candidate_id", how="left", suffixes=("", "_diag"))
            for col in available:
                if col == "candidate_id":
                    continue
                diag_col = f"{col}_diag"
                if diag_col not in out.columns:
                    continue
                if col not in out.columns:
                    out[col] = out[diag_col]
                else:
                    out[col] = out[col].where(out[col].notna() & (out[col].astype(str) != ""), out[diag_col])
                out = out.drop(columns=[diag_col])
    return out


def _prepare_abc_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = _normalise_id_frame(frame, "2.4.4_contextual_corrections")
    out["source_scope"] = out["timeframe"].map(lambda value: "h4_d1" if _string(value).upper() == "H4" else "aux")
    out["review_category"] = "abc"
    out["direction"] = out.get("abc_direction", "")
    out["timeframe_policy"] = out["timeframe"].map(lambda value: _timeframe_policy(_string(value), "h4_d1" if _string(value).upper() == "H4" else "aux"))
    out["structure_type"] = out.apply(_structure_type, axis=1, is_abc=True)
    out["phase25_allowed_use"] = out.apply(_phase25_allowed_use, axis=1, is_abc=True)
    out["degree_policy"] = out["swing_degree"].map(
        lambda degree: {
            "intermediate": "intermediate_primary_candidate",
            "major": "major_context",
            "minor": "minor_substructure_only",
        }.get(_string(degree), "")
    )
    out["visual_quality_score"] = out.get("abc_quality_score", 3)
    out["final_phase23_decision"] = out["contextual_policy"].map(
        {
            "usable_contextual_correction": "keep_as_ambiguous_example",
            "manual_contextual_review_only": "keep_as_ambiguous_example",
            "experimental_unknown_parent": "keep_as_ambiguous_example",
            "exclude_not_correction": "exclude_from_phase25_rules",
        }
    )
    out["abc_contextual_policy"] = out["contextual_policy"]
    out["abc_parent_required"] = "yes"
    out["abc_parent_status"] = out.get("parent_context_status", "")
    out["abc_role_hypothesis"] = out.get("correction_role", "")
    out["abc_should_enter_phase25_context"] = out.get("should_enter_phase25_as_context", "")
    out["context_must_not_rescue_bad_count"] = out["contextual_policy"].astype(str).eq("exclude_not_correction")
    return out


def _unified_columns() -> list[str]:
    return [
        "source_phase",
        "source_candidate_id",
        "candidate_id",
        "structure_type",
        "review_category",
        "group",
        "symbol",
        "timeframe",
        "swing_degree",
        "direction",
        "timeframe_policy",
        "degree_policy",
        "phase25_allowed_use",
        "final_phase23_decision",
        "manual_visual_status",
        "visual_quality_score",
        "wave5_diagnostic",
        "wave5_endpoint_status",
        "proposed_endpoint_classification",
        "future_more_extreme_found",
        "post_wave5_extension_vs_wave5",
        "partial123_diagnostic",
        "partial123_status",
        "live_state",
        "wave3_too_weak",
        "post_3_invalidates",
        "post_3_confirms",
        "context_review_status",
        "trend_context_label",
        "context_score",
        "ema_usefulness",
        "ewo_usefulness",
        "htf_usefulness",
        "phase25_rule_candidate",
        "end_ltf_price_vs_ema_band",
        "end_ltf_transition_state",
        "end_ltf_ewo_5_35",
        "end_ltf_ewo_5_35_slope",
        "end_ltf_ewo_5_35_direction",
        "htf_timeframe",
        "htf_trend_state",
        "htf_lookahead_safe",
        "abc_contextual_policy",
        "abc_parent_required",
        "abc_parent_status",
        "abc_role_hypothesis",
        "abc_should_enter_phase25_context",
        "context_must_not_rescue_bad_count",
        "reviewed_chart_path",
        "reviewed_context_chart_path",
        "reviewed_chart_path_abc",
    ]


def _select_columns(frame: pd.DataFrame) -> pd.DataFrame:
    cols = _unified_columns()
    out = frame.copy()
    for col in cols:
        if col not in out.columns:
            out[col] = ""
    return out[cols]


def _summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in [
        "guided_quality_bucket",
        "phase25_allowed_use",
        "structure_type",
        "timeframe_policy",
        "swing_degree",
        "ready_for_phase251_search",
        "suggested_next_search_mode",
    ]:
        counts = _counts(frame, column)
        for value, count in counts.items():
            rows.append({"metric": column, "value": value, "count": count})
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, candidates: pd.DataFrame, run_meta: dict[str, Any]) -> None:
    bucket_counts = _counts(candidates, "guided_quality_bucket")
    phase251_counts = _counts(candidates, "ready_for_phase251_search")
    lines = [
        "# WaveCount Fase 2.5.0 - Guided Context Score",
        "",
        "## Resumen",
        "",
        "Esta fase aplica una capa de scoring/contexto sobre candidatos WaveCount existentes. No recalcula pivotes, no cambia conteos base y no genera senales.",
        "",
        "El `guided_quality_score` es una puntuacion metodologica de lectura estructural. No es probabilidad de ganar ni expectativa de rentabilidad.",
        "",
        "## Distribucion de calidad",
        "",
    ]
    for bucket, count in bucket_counts.items():
        lines.append(f"- `{bucket}`: {count}")
    lines.extend(["", "## Readiness 2.5.1", ""])
    for key, count in phase251_counts.items():
        lines.append(f"- `{key}`: {count}")
    lines.extend(
        [
            "",
            "## Politica aplicada",
            "",
            "- H4/D1 + `intermediate` es la base principal.",
            "- H1/H4 es auxiliar.",
            "- M30/H1 es microestructura/banco de fallos.",
            "- EMAs 50/150, D1/HTF y EWO 5-35 son contexto blando.",
            "- EWO se interpreta por comportamiento relativo/contextual, no por umbrales absolutos fijos.",
            "- ABC solo entra si tiene padre/contexto razonable.",
            "- Parciales 1-2-3 e incertidumbre de onda 5 son provisionales.",
            "",
            "## Cierre",
            "",
            "Fase 2.5.0 deja preparada la entrada para una Fase 2.5.1 de busqueda mas guiada, todavia sin senales. Los casos `high_quality_context` y algunos `usable_but_provisional` son los candidatos metodologicamente mas limpios.",
            "",
            "## Run meta",
            "",
            "```json",
            json.dumps(run_meta, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_5_0_GUIDED_CONTEXT_SCORE.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def build_guided_context_score(
    *,
    readiness_dir: Path,
    h4_closure_dir: Path,
    context_dir: Path,
    corrections_dir: Path,
    wave5_dir: Path,
    partial123_dir: Path,
    degree_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    readiness = _read_csv(readiness_dir / "tables" / "phase25_readiness_matrix.csv")
    h4_context = _read_csv(context_dir / "tables" / "h4_d1_context_quality_audit.csv")
    aux_context = _read_csv(context_dir / "tables" / "h1_h4_m30_h1_aux_context_audit.csv")
    abc_context = _read_csv(corrections_dir / "tables" / "contextual_corrections_audit.csv")
    wave5_diag = _read_csv(wave5_dir / "tables" / "wave5_endpoint_diagnostics.csv")
    partial_diag = _read_csv(partial123_dir / "tables" / "partial123_diagnostics.csv")

    h4_candidates = _merge_diagnostics(_prepare_context_candidates(h4_context, scope="h4_d1"), wave5_diag, partial_diag)
    aux_candidates = _merge_diagnostics(_prepare_context_candidates(aux_context, scope="aux"), wave5_diag, partial_diag)
    abc_candidates = _prepare_abc_candidates(abc_context)
    if "reviewed_chart_path" in abc_candidates.columns:
        abc_candidates["reviewed_chart_path_abc"] = abc_candidates["reviewed_chart_path"]

    candidates = pd.concat(
        [
            _select_columns(h4_candidates),
            _select_columns(aux_candidates),
            _select_columns(abc_candidates),
        ],
        ignore_index=True,
    )

    score_rows = candidates.apply(_score_candidate, axis=1, result_type="expand")
    candidates = pd.concat([candidates, score_rows], axis=1)
    phase251 = candidates.apply(_ready_for_phase251, axis=1, result_type="expand")
    candidates = pd.concat([candidates, phase251], axis=1)

    def chart_path(row: pd.Series) -> str:
        for col in ("reviewed_context_chart_path", "reviewed_chart_path_abc", "reviewed_chart_path"):
            value = _string(row.get(col))
            if value:
                return value
        return ""

    candidates["chart_path"] = candidates.apply(chart_path, axis=1)

    ewo_context = candidates[
        [
            "candidate_id",
            "structure_type",
            "timeframe_policy",
            "swing_degree",
            "ewo_wave_role_label",
            "ewo_role_support",
            "ewo_role_reasons",
            "ewo_role_penalty",
            "guided_quality_bucket",
            "chart_path",
        ]
    ].copy()
    ema_htf_policy = candidates[
        [
            "candidate_id",
            "structure_type",
            "timeframe_policy",
            "trend_context_label",
            "htf_ltf_alignment_label",
            "ema_context_label",
            "ema_context_score_delta",
            "htf_context_score_delta",
            "context_must_not_rescue_bad_count",
            "guided_quality_bucket",
            "chart_path",
        ]
    ].copy()
    abc_integration = candidates[candidates["source_phase"].astype(str).eq("2.4.4_contextual_corrections")][
        [
            "candidate_id",
            "timeframe_policy",
            "swing_degree",
            "abc_contextual_policy",
            "abc_parent_required",
            "abc_parent_status",
            "abc_role_hypothesis",
            "abc_should_enter_phase25_context",
            "guided_quality_score",
            "guided_quality_bucket",
            "phase25_allowed_use",
            "chart_path",
        ]
    ].copy()
    phase251_readiness = candidates[
        [
            "candidate_id",
            "structure_type",
            "timeframe_policy",
            "swing_degree",
            "guided_quality_score",
            "guided_quality_bucket",
            "ready_for_phase251_search",
            "phase251_reason",
            "suggested_next_search_mode",
            "chart_path",
        ]
    ].copy()
    exclusions = candidates[
        (candidates["guided_quality_bucket"] == "exclude") | (candidates["phase25_allowed_use"] == "exclude")
    ].copy()
    best = candidates[
        candidates["guided_quality_bucket"].isin(["high_quality_context", "usable_but_provisional"])
    ].copy()
    priority = {"primary_h4_d1": 0, "auxiliary_h1_h4": 1, "microstructure_m30_h1": 2}
    best["_timeframe_priority"] = best["timeframe_policy"].map(priority).fillna(9)
    best = best.sort_values(["_timeframe_priority", "guided_quality_score"], ascending=[True, False]).head(30)
    best = best.drop(columns=["_timeframe_priority"])
    user_review = candidates[
        (candidates["ready_for_phase251_search"] == "manual_review")
        | (candidates["phase25_allowed_use"].isin(["manual_review_only", "experimental"]))
        | (candidates["ewo_role_support"].isin(["contradicts", "unclear"]))
    ].copy()
    user_review = user_review.sort_values(["guided_quality_score"], ascending=False).head(40)

    outputs = {
        "guided_context_candidates": candidates,
        "guided_quality_summary": _summary(candidates),
        "ewo_role_context": ewo_context,
        "ema_htf_context_policy": ema_htf_policy,
        "abc_contextual_integration": abc_integration,
        "phase251_search_readiness": phase251_readiness,
        "guided_context_exclusions": exclusions,
        "guided_context_best_examples": best,
        "guided_context_user_review_if_any": user_review,
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    image_refs = [
        _string(value)
        for frame in (best, user_review, candidates)
        if "chart_path" in frame.columns
        for value in frame["chart_path"].dropna().tolist()
        if _string(value).lower().endswith(".png")
    ]
    missing_images = sorted({path for path in image_refs if not _resolve_repo_path(path).exists()})

    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "source_dirs": {
            "readiness": _rel_to_repo(readiness_dir),
            "h4_closure": _rel_to_repo(h4_closure_dir),
            "context": _rel_to_repo(context_dir),
            "corrections": _rel_to_repo(corrections_dir),
            "wave5": _rel_to_repo(wave5_dir),
            "partial123": _rel_to_repo(partial123_dir),
            "degree": _rel_to_repo(degree_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "guided_quality_bucket_counts": _counts(candidates, "guided_quality_bucket"),
        "phase251_readiness_counts": _counts(candidates, "ready_for_phase251_search"),
        "source_candidate_counts": {
            "h4_d1": int(len(h4_candidates)),
            "auxiliary": int(len(aux_candidates)),
            "abc_contextual": int(len(abc_candidates)),
        },
        "readiness_components_used": int(len(readiness)),
        "missing_image_refs": missing_images,
        "no_base_counts_modified": True,
        "no_strategy_changes": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, candidates, run_meta)
    return run_meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.0 guided context score.")
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument("--h4-closure-dir", type=Path, default=DEFAULT_H4_CLOSURE_DIR)
    parser.add_argument("--context-dir", type=Path, default=DEFAULT_CONTEXT_DIR)
    parser.add_argument("--corrections-dir", type=Path, default=DEFAULT_CORRECTIONS_DIR)
    parser.add_argument("--wave5-dir", type=Path, default=DEFAULT_WAVE5_DIR)
    parser.add_argument("--partial123-dir", type=Path, default=DEFAULT_PARTIAL123_DIR)
    parser.add_argument("--degree-dir", type=Path, default=DEFAULT_DEGREE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_meta = build_guided_context_score(
        readiness_dir=args.readiness_dir,
        h4_closure_dir=args.h4_closure_dir,
        context_dir=args.context_dir,
        corrections_dir=args.corrections_dir,
        wave5_dir=args.wave5_dir,
        partial123_dir=args.partial123_dir,
        degree_dir=args.degree_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(run_meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
