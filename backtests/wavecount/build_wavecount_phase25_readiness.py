from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_H4_CLOSURE_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_4_h4_d1_visual_closure_2026-05-23"
)
DEFAULT_CONTEXT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_2_context_quality_audit_2026-05-23"
)
DEFAULT_ABC_QUALITY_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_3_abc_quality_audit_2026-05-23"
)
DEFAULT_CONTEXTUAL_CORRECTIONS_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_4_contextual_corrections_2026-05-24"
)
DEFAULT_WAVE5_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_1_wave5_endpoint_2026-05-21"
DEFAULT_PARTIAL123_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_partial123_2026-05-21"
DEFAULT_DEGREE_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_3_degree_calibration_2026-05-23"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_5_pre_phase25_closure_2026-05-24"
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
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


def _resolve_repo_path(value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    return REPO_ROOT / raw


def _counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    return {str(k): int(v) for k, v in frame[column].fillna("missing").value_counts().to_dict().items()}


def _metric(frame: pd.DataFrame, name: str) -> str:
    if frame.empty or "metric" not in frame.columns or "value" not in frame.columns:
        return ""
    rows = frame[frame["metric"].astype(str) == name]
    if rows.empty:
        return ""
    return _string(rows.iloc[0]["value"])


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
            _string(row.get("component")),
            _string(row.get("example_type")),
            _string(row.get("candidate_id")),
            _string(row.get("policy")),
            _string(row.get("phase25_policy")),
        ]
        title_bits = [bit for bit in bits if bit]
        lines.append(f"## {idx + 1}. {' | '.join(title_bits) if title_bits else 'fila'}")
        for column in (
            "methodological_reason",
            "reason",
            "notes",
            "risk_if_used_wrong",
            "required_next_step",
        ):
            value = _string(row.get(column))
            if value:
                lines.extend(["", value])
        for column in row.index:
            if "path" not in column.lower():
                continue
            value = _string(row.get(column))
            if not value or not value.lower().endswith(".png"):
                continue
            path = _resolve_repo_path(value)
            lines.extend(["", f"![{path.name}]({path.resolve().as_posix()})"])
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _matrix_rows(
    *,
    h4_closure: pd.DataFrame,
    degree_readiness: pd.DataFrame,
    context_readiness: pd.DataFrame,
    correction_policy: pd.DataFrame,
    wave5_summary: pd.DataFrame,
    partial_summary: pd.DataFrame,
    abc_policy: pd.DataFrame,
) -> list[dict[str, Any]]:
    h4_decisions = _counts(h4_closure, "final_phase23_decision")
    degree_policy = _counts(h4_closure, "degree_policy")
    correction_counts = _counts(correction_policy, "contextual_policy")
    abc_counts = _counts(abc_policy, "phase25_abc_policy")

    def row(
        component: str,
        source_phase: str,
        status: str,
        phase25_policy: str,
        primary_timeframe_policy: str,
        degree_policy_value: str,
        can_rule: str,
        can_context: str,
        experimental: str,
        excluded: str,
        reason: str,
        risk: str,
        next_step: str,
    ) -> dict[str, Any]:
        return {
            "component": component,
            "source_phase": source_phase,
            "status": status,
            "phase25_policy": phase25_policy,
            "primary_timeframe_policy": primary_timeframe_policy,
            "degree_policy": degree_policy_value,
            "can_be_used_as_rule": can_rule,
            "can_be_used_as_soft_context": can_context,
            "should_remain_experimental": experimental,
            "should_be_excluded": excluded,
            "methodological_reason": reason,
            "risk_if_used_wrong": risk,
            "required_next_step": next_step,
        }

    return [
        row(
            "H4/D1 count-only",
            "2.3.4",
            "ready_for_phase25_design",
            "primary_visual_base",
            "H4 primary with D1 context",
            "intermediate primary; major context",
            "yes_soft_rule",
            "yes",
            "no",
            "no",
            f"H4/D1 closure exists with decisions {h4_decisions}. It is the cleanest visual scale.",
            "Using downgraded or ambiguous H4 counts as clean rules.",
            "Use only keep/good or explicit ambiguous labels in guided search.",
        ),
        row(
            "H1/H4 auxiliary",
            "2.4.2 / 2.3.3",
            "auxiliary_only",
            "case_bank_and_substructure",
            "auxiliary below H4",
            "intermediate auxiliary",
            "no",
            "yes",
            "no",
            "no",
            "Useful for substructure and failure-bank, but less stable than H4/D1.",
            "Promoting low timeframe microstructure to primary Elliott structure.",
            "Keep separate from H4/D1 decisions.",
        ),
        row(
            "M30/H1 auxiliary",
            "2.4.2 / 2.3.3",
            "microstructure_auxiliary",
            "microstructure_only",
            "not primary",
            "minor/intermediate only as substructure",
            "no",
            "yes_limited",
            "yes",
            "no",
            "Manual review found many micro/lateral cases. It is useful mainly to expose failure modes.",
            "Over-reading small noisy swings as full Elliott waves.",
            "Use for diagnostics, not for Phase 2.5 primary rules.",
        ),
        row(
            "intermediate degree",
            "1.6 / 2.3.3",
            "preferred",
            "primary_degree",
            "H4/D1 primary; H1/H4 auxiliary",
            "intermediate",
            "yes_soft_rule",
            "yes",
            "no",
            "no",
            "Degree calibration selected intermediate as best compromise, especially on H4/D1.",
            "Treating it as exact objective Elliott degree rather than visual scale.",
            "Use as default degree in Phase 2.5 prototype.",
        ),
        row(
            "major degree",
            "1.6 / 2.3.3",
            "context_or_higher_degree",
            "higher_degree_context",
            "context for H4/D1",
            "major",
            "no",
            "yes",
            "no",
            "no",
            f"Major is useful as context, but degree overlap remains {degree_policy}.",
            "Assuming every major count is more valid than intermediate by construction.",
            "Use as context or higher-degree candidate with explicit label.",
        ),
        row(
            "minor degree",
            "1.6 / 2.3.3",
            "substructure_only",
            "substructure_or_failure_bank",
            "not primary",
            "minor",
            "no",
            "yes_limited",
            "yes",
            "no",
            "Often too micro for principal Elliott count, though it can show internal waves.",
            "Letting minor dominate the main WaveCount state.",
            "Keep as substructure with microstructure warning.",
        ),
        row(
            "clean impulses",
            "2.3.4",
            "usable",
            "candidate_rule_input",
            "H4/D1 primary",
            "intermediate preferred",
            "yes_soft_rule",
            "yes",
            "no",
            "no",
            "Clean/defensible impulses are the strongest WaveCount input after visual closure.",
            "Turning visual quality into profitability claim or signal.",
            "Feed to Phase 2.5 as candidate structure, not trade signal.",
        ),
        row(
            "provisional impulses",
            "2.3.1 / 2.3.4",
            "usable_with_uncertainty",
            "provisional_context",
            "H4/D1 primary",
            "intermediate or higher-degree subwave",
            "no",
            "yes",
            "no",
            "no",
            f"Wave 5 diagnostics diagnosed {_metric(wave5_summary, 'diagnosed_candidates')} candidates and showed endpoint uncertainty should not invalidate aggressively.",
            "Closing wave 5 too early or invalidating good subwaves too aggressively.",
            "Carry endpoint uncertainty and higher-degree subwave labels.",
        ),
        row(
            "partial 1-2-3",
            "2.3.2",
            "provisional_only",
            "context_only",
            "H4/D1 preferred; lower TF auxiliary",
            "intermediate preferred",
            "no",
            "yes",
            "no",
            "no",
            f"Partial audit diagnosed {_metric(partial_summary, 'diagnosed_partial_candidates')} candidates; partials must stay provisional.",
            "Treating three alternating swings as a complete impulse or entry signal.",
            "Require wave-3 displacement and post-3 diagnostics in Phase 2.5.",
        ),
        row(
            "wave5 endpoint uncertainty",
            "2.3.1",
            "diagnostic_ready",
            "uncertainty_label",
            "all visual timeframes",
            "all degrees",
            "no",
            "yes",
            "no",
            "no",
            "It captures whether a local impulse may continue or belong to a higher-degree wave.",
            "Reading uncertainty as failure instead of provisionality.",
            "Keep as diagnostic label, not hard invalidation.",
        ),
        row(
            "ABC visual quality",
            "2.4.3",
            "limited",
            "manual_or_experimental",
            "H4/D1 preferred",
            "intermediate preferred",
            "no",
            "yes_limited",
            "yes",
            "no",
            f"Visual ABC quality alone gave {abc_counts}; isolated ABC is insufficient.",
            "Accepting a clean 0-A-B-C as correction without knowing what it corrects.",
            "Use only after contextual correction policy.",
        ),
        row(
            "ABC contextual correction",
            "2.4.4",
            "usable_limited",
            "soft_context_only",
            "H4/D1 preferred; H1 auxiliary examples",
            "intermediate preferred",
            "no",
            "yes",
            "yes_limited",
            "no",
            f"Contextual correction policy produced {correction_counts}; only parent/context-supported corrections are usable.",
            "Letting context rescue visually bad ABC or treating unknown-parent ABC as rules.",
            "Require parent/context field before any Phase 2.5 use.",
        ),
        row(
            "EMA 50/150 context",
            "2.4.2",
            "ready_as_soft_context",
            "soft_quality_filter",
            "H4 with D1 context",
            "not degree-specific",
            "yes_soft_rule",
            "yes",
            "no",
            "no",
            "EMAs help regime, transition and ambiguity; price inside band should raise ambiguity.",
            "Using EMA alignment as hard acceptance/rejection of counts.",
            "Use as score/penalty, never as standalone validation.",
        ),
        row(
            "EWO 5-35 context",
            "2.4.2",
            "ready_as_soft_context",
            "momentum_role_support",
            "H4 with D1 context",
            "not degree-specific",
            "yes_soft_rule",
            "yes",
            "no",
            "no",
            "EWO helps wave-role interpretation: wave 3 expansion, wave 5 loss/divergence, corrections.",
            "Treating EWO as signal or forcing labels from oscillator shape.",
            "Use as explanatory feature, not hard rule.",
        ),
        row(
            "HTF/D1 context",
            "2.4.2",
            "ready_as_soft_context",
            "regime_context",
            "D1 for H4",
            "major/intermediate context",
            "yes_soft_rule",
            "yes",
            "no",
            "no",
            "D1 helps distinguish impulse, correction and transition, but can lag.",
            "Using HTF to rescue downgraded counts or reject valid transitions.",
            "Use conflict labels: transition, explainable conflict, suspicious conflict.",
        ),
        row(
            "correction alternation",
            "2.4.4",
            "future_soft_note",
            "not_ready_as_rule",
            "requires comparable wave 2 and 4 context",
            "higher-degree context required",
            "no",
            "yes_limited",
            "yes",
            "no",
            "Alternation is meaningful only when wave 2 and wave 4 are both contextualized.",
            "Applying alternation without confirmed comparable corrections.",
            "Leave as note until correction model is redesigned.",
        ),
        row(
            "complex corrections",
            "2.4.4",
            "future_work",
            "exclude_from_phase25_rules",
            "not applicable",
            "not applicable",
            "no",
            "no",
            "yes",
            "yes",
            "Zigzag/flat/triangle/combination taxonomy is not implemented yet.",
            "Pretending simple ABC covers all Elliott corrections.",
            "Separate redesign after Phase 2.5 prototype if needed.",
        ),
    ]


def _input_policy_rows() -> list[dict[str, str]]:
    return [
        {
            "input": "H4/D1",
            "policy": "primary",
            "phase25_use": "Base timeframe stack for guided search prototype.",
            "notes": "H4 count-only first; D1 only as soft context.",
        },
        {
            "input": "H1/H4",
            "policy": "auxiliary",
            "phase25_use": "Substructure and robustness checks.",
            "notes": "Do not let it outweigh H4/D1.",
        },
        {
            "input": "M30/H1",
            "policy": "microstructure_auxiliary",
            "phase25_use": "Failure-bank and internal structure only.",
            "notes": "Manual review showed more micro/lateral noise.",
        },
        {
            "input": "intermediate",
            "policy": "primary_degree",
            "phase25_use": "Default swing degree.",
            "notes": "Best visual compromise from degree calibration.",
        },
        {
            "input": "major",
            "policy": "context_or_higher_degree",
            "phase25_use": "Context and optional higher-degree candidate.",
            "notes": "Can be operable as a higher degree, but not automatically superior.",
        },
        {
            "input": "minor",
            "policy": "substructure_only",
            "phase25_use": "Internal wave structure and diagnostics.",
            "notes": "Not primary for main WaveCount state.",
        },
    ]


def _rule_candidate_rows() -> list[dict[str, str]]:
    return [
        {
            "rule_candidate": "h4_d1_intermediate_primary",
            "rule_type": "structure_selection",
            "strength": "soft_default",
            "use_in_phase25": "yes",
            "reason": "H4/D1 intermediate has the clearest visual balance.",
            "must_not_do": "Do not treat as trading signal.",
        },
        {
            "rule_candidate": "htf_alignment_soft_filter",
            "rule_type": "context_score",
            "strength": "soft",
            "use_in_phase25": "yes",
            "reason": "D1 helps regime reading but can lag.",
            "must_not_do": "Do not reject all counter-HTF corrections.",
        },
        {
            "rule_candidate": "ema_band_ambiguity_penalty",
            "rule_type": "context_score",
            "strength": "soft",
            "use_in_phase25": "yes",
            "reason": "Inside EMA 50/150 band often marks transition or unclear structure.",
            "must_not_do": "Do not invalidate solely because price is in the band.",
        },
        {
            "rule_candidate": "ewo_wave3_momentum_support",
            "rule_type": "momentum_context",
            "strength": "soft",
            "use_in_phase25": "yes",
            "reason": "EWO can support wave 3 expansion interpretation.",
            "must_not_do": "Do not label waves from EWO alone.",
        },
        {
            "rule_candidate": "ewo_wave5_divergence_warning",
            "rule_type": "momentum_context",
            "strength": "soft",
            "use_in_phase25": "yes",
            "reason": "Momentum loss can explain wave 5 or truncation risk.",
            "must_not_do": "Do not force a top/bottom from divergence.",
        },
        {
            "rule_candidate": "abc_requires_parent_context",
            "rule_type": "correction_policy",
            "strength": "soft_gate",
            "use_in_phase25": "yes",
            "reason": "ABC without parent/context is not a strong correction.",
            "must_not_do": "Do not accept isolated 0-A-B-C as clean Elliott correction.",
        },
        {
            "rule_candidate": "partial123_provisional_only",
            "rule_type": "state_policy",
            "strength": "soft_gate",
            "use_in_phase25": "yes",
            "reason": "Partial 1-2-3 can describe current structure but is incomplete.",
            "must_not_do": "Do not turn partials into signals.",
        },
        {
            "rule_candidate": "wave5_endpoint_uncertainty",
            "rule_type": "state_policy",
            "strength": "soft",
            "use_in_phase25": "yes",
            "reason": "Endpoint uncertainty should preserve provisionality.",
            "must_not_do": "Do not degrade good local counts automatically.",
        },
    ]


def _soft_context_rows() -> list[dict[str, str]]:
    return [
        {
            "feature": "ema_50_150_alignment",
            "source_phase": "2.4.2",
            "use": "regime and transition context",
            "policy": "soft_context",
            "notes": "Useful when aligned with visually good count; dangerous as hard filter.",
        },
        {
            "feature": "price_vs_ema_band",
            "source_phase": "2.4.2",
            "use": "ambiguity penalty",
            "policy": "soft_context",
            "notes": "Inside band increases uncertainty.",
        },
        {
            "feature": "ewo_5_35_direction_slope",
            "source_phase": "2.4.2",
            "use": "momentum role reading",
            "policy": "soft_context",
            "notes": "Supports wave 3/wave 5/correction interpretation.",
        },
        {
            "feature": "d1_htf_state",
            "source_phase": "2.4.2",
            "use": "parent regime context",
            "policy": "soft_context",
            "notes": "Can explain countertrend corrections and transitions.",
        },
        {
            "feature": "abc_parent_context",
            "source_phase": "2.4.4",
            "use": "correction role hypothesis",
            "policy": "soft_context_with_manual_review",
            "notes": "Only usable when parent/context is clear enough.",
        },
    ]


def _exclusion_rows() -> list[dict[str, str]]:
    return [
        {
            "excluded_item": "ABC without parent/context as strong correction",
            "reason": "A clean 0-A-B-C can be an impulse/subimpulse if it does not correct a known movement.",
            "phase25_policy": "exclude_as_rule",
        },
        {
            "excluded_item": "complex corrections taxonomy",
            "reason": "Zigzag, flat, triangle, combination and alternation are not implemented rigorously yet.",
            "phase25_policy": "future_work",
        },
        {
            "excluded_item": "operational signals/trading filters",
            "reason": "WaveCount is still visual/structural context, not a strategy.",
            "phase25_policy": "out_of_scope",
        },
        {
            "excluded_item": "M30/H1 as primary WaveCount base",
            "reason": "Too much microstructure and lateral noise relative to H4/D1.",
            "phase25_policy": "auxiliary_only",
        },
        {
            "excluded_item": "hard EMA/EWO/HTF filters",
            "reason": "Context can help but must not rescue bad counts or reject valid transitions.",
            "phase25_policy": "soft_only",
        },
    ]


def _future_rows() -> list[dict[str, str]]:
    return [
        {
            "future_item": "correction_model_redesign",
            "priority": "medium_after_phase25",
            "description": "Implement zigzag, flat, triangle, combination, alternation and post-wave-5 roles.",
            "blocks_phase25": "no",
        },
        {
            "future_item": "visual_dashboard_layer",
            "priority": "later",
            "description": "Show WaveCount read-only after Phase 2.5 is stable.",
            "blocks_phase25": "no",
        },
        {
            "future_item": "descriptive_offline_statistics",
            "priority": "after_guided_search",
            "description": "Frequency, stability, invalidation rate and ambiguity by asset/timeframe.",
            "blocks_phase25": "no",
        },
        {
            "future_item": "telegram_informative_context",
            "priority": "much_later",
            "description": "Only informational after visual and descriptive validation.",
            "blocks_phase25": "no",
        },
    ]


def _risk_rows() -> list[dict[str, str]]:
    return [
        {
            "risk": "context_rescues_bad_count",
            "severity": "high",
            "mitigation": "A downgraded count cannot become good only because EMAs/EWO/HTF agree.",
        },
        {
            "risk": "abc_isolated_false_correction",
            "severity": "high",
            "mitigation": "Require parent/context and keep unknown-parent ABC experimental.",
        },
        {
            "risk": "degree_overconfidence",
            "severity": "medium",
            "mitigation": "Treat degree as visual scale, not objective market truth.",
        },
        {
            "risk": "low_timeframe_noise",
            "severity": "medium",
            "mitigation": "Keep H1/H4 and M30/H1 auxiliary.",
        },
        {
            "risk": "wave5_endpoint_overreaction",
            "severity": "medium",
            "mitigation": "Use provisional endpoint uncertainty, not automatic invalidation.",
        },
        {
            "risk": "turning_context_into_signal",
            "severity": "high",
            "mitigation": "Phase 2.5 remains no-signal and no-trading.",
        },
    ]


def _best_examples(
    *,
    h4_closure: pd.DataFrame,
    context_confirms: pd.DataFrame,
    correction_keep: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    if not h4_closure.empty:
        good = h4_closure[
            h4_closure.get("final_phase23_decision", pd.Series(dtype=str)).astype(str).isin(
                ["keep_as_good_example"]
            )
        ].copy()
        if "visual_quality_score" in good.columns:
            good["_score_sort"] = pd.to_numeric(good["visual_quality_score"], errors="coerce").fillna(0)
            good = good.sort_values("_score_sort", ascending=False)
        for _, item in good.head(8).iterrows():
            rows.append(
                {
                    "example_type": "h4_d1_count_only",
                    "candidate_id": _string(item.get("candidate_id")),
                    "source_phase": "2.3.4",
                    "policy": "best_count_example",
                    "reason": _string(item.get("visual_closure_notes"))
                    or _string(item.get("visual_notes"))
                    or "Good H4/D1 visual example.",
                    "chart_path": _string(item.get("best_chart_path"))
                    or _string(item.get("reviewed_chart_path"))
                    or _string(item.get("source_chart_path")),
                }
            )

    if not context_confirms.empty:
        context = context_confirms.copy()
        if "visual_quality_score" in context.columns:
            context["_score_sort"] = pd.to_numeric(context["visual_quality_score"], errors="coerce").fillna(0)
            context = context.sort_values("_score_sort", ascending=False)
        for _, item in context.head(6).iterrows():
            rows.append(
                {
                    "example_type": "context_confirms_good_count",
                    "candidate_id": _string(item.get("candidate_id")),
                    "source_phase": "2.4.2",
                    "policy": "best_context_example",
                    "reason": _string(item.get("context_notes_integrated"))
                    or _string(item.get("context_notes"))
                    or "Context supports a visually good count.",
                    "chart_path": _string(item.get("reviewed_context_chart_path"))
                    or _string(item.get("context_chart_path")),
                }
            )

    if not correction_keep.empty:
        for _, item in correction_keep.head(6).iterrows():
            rows.append(
                {
                    "example_type": "contextual_correction",
                    "candidate_id": _string(item.get("candidate_id")),
                    "source_phase": "2.4.4",
                    "policy": _string(item.get("contextual_policy")) or "usable_contextual_correction",
                    "reason": _string(item.get("notes")) or "ABC has enough parent/context to remain soft context.",
                    "chart_path": _string(item.get("reviewed_chart_path")),
                }
            )

    return pd.DataFrame(rows)


def _user_review_rows(context_user_review: pd.DataFrame, correction_user_review: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not context_user_review.empty:
        for _, item in context_user_review.head(10).iterrows():
            rows.append(
                {
                    "review_reason": "context_quality_case",
                    "candidate_id": _string(item.get("candidate_id")),
                    "priority": _string(item.get("user_review_priority")) or "medium",
                    "notes": _string(item.get("context_notes_integrated"))
                    or _string(item.get("context_notes"))
                    or "Context case marked for review.",
                    "chart_path": _string(item.get("reviewed_context_chart_path"))
                    or _string(item.get("context_chart_path")),
                }
            )
    if not correction_user_review.empty:
        for _, item in correction_user_review.head(10).iterrows():
            rows.append(
                {
                    "review_reason": "contextual_correction_case",
                    "candidate_id": _string(item.get("candidate_id")),
                    "priority": "medium",
                    "notes": _string(item.get("notes")) or "Correction case marked for review.",
                    "chart_path": _string(item.get("reviewed_chart_path")),
                }
            )
    return pd.DataFrame(rows)


def _write_report(
    *,
    output_dir: Path,
    readiness: pd.DataFrame,
    best_examples: pd.DataFrame,
    run_meta: dict[str, Any],
) -> None:
    policy_counts = _counts(readiness, "phase25_policy")
    lines = [
        "# WaveCount Fase 2.4.5 - Cierre pre-Fase 2.5",
        "",
        "## Resumen ejecutivo",
        "",
        "WaveCount queda listo para disenar Fase 2.5 como busqueda guiada por contexto, todavia sin senales ni filtros operativos. La base principal debe ser H4/D1 con grado `intermediate`; `major` queda como contexto o grado superior, y `minor` como subestructura.",
        "",
        "La fase no recalcula pivotes, conteos ni senales. Solo consolida decisiones ya auditadas y crea una matriz de trazabilidad.",
        "",
        "## Politica sintetica",
        "",
    ]
    for policy, count in policy_counts.items():
        lines.append(f"- `{policy}`: {count} componentes.")
    lines.extend(
        [
            "",
            "## Decision pre-2.5",
            "",
            "- H4/D1 entra como base principal.",
            "- H1/H4 y M30/H1 quedan auxiliares.",
            "- EMAs 50/150, EWO 5-35 y HTF/D1 entran solo como contexto blando.",
            "- ABC no puede usarse aislado: necesita padre/contexto razonable.",
            "- Parciales 1-2-3 e incertidumbre de onda 5 se mantienen como estados provisionales, nunca senales.",
            "- Correcciones complejas y alternancia completa quedan como trabajo futuro.",
            "",
            "## Mejores ejemplos",
            "",
        ]
    )
    if best_examples.empty:
        lines.append("No se han seleccionado ejemplos destacados.")
    else:
        for _, row in best_examples.head(10).iterrows():
            lines.append(
                f"- `{_string(row.get('candidate_id'))}` ({_string(row.get('example_type'))}): "
                f"{_string(row.get('reason'))}"
            )
    lines.extend(
        [
            "",
            "## Validacion",
            "",
            "- Script de cierre ejecutado correctamente.",
            "- CSV principales generados.",
            "- No se han modificado conteos base ni artifacts anteriores.",
            "- No se han cambiado estrategias.",
            "",
            "## Archivos generados",
            "",
            "- `tables/phase25_readiness_matrix.csv`",
            "- `tables/phase25_inputs_policy.csv`",
            "- `tables/phase25_rule_candidates.csv`",
            "- `tables/phase25_soft_context_features.csv`",
            "- `tables/phase25_exclusions.csv`",
            "- `tables/phase25_future_work.csv`",
            "- `tables/phase25_best_examples.csv`",
            "- `tables/phase25_risk_register.csv`",
            "- `tables/phase25_user_review_if_any.csv`",
            "",
            "## Run meta",
            "",
            "```json",
            json.dumps(run_meta, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_4_5_PRE_PHASE25_CLOSURE.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def build_phase25_readiness(
    *,
    h4_closure_dir: Path,
    context_dir: Path,
    abc_quality_dir: Path,
    contextual_corrections_dir: Path,
    wave5_dir: Path,
    partial123_dir: Path,
    degree_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    start = perf_counter()
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    h4_closure = _read_csv(h4_closure_dir / "tables" / "h4_d1_visual_closure.csv")
    degree_readiness = _read_csv(degree_dir / "tables" / "phase2_5_degree_readiness.csv")
    context_readiness = _read_csv(context_dir / "tables" / "phase25_context_readiness.csv")
    context_rule_candidates = _read_csv(context_dir / "tables" / "context_rule_candidates.csv")
    context_confirms = _read_csv(context_dir / "tables" / "context_confirms_good_counts.csv")
    context_user_review = _read_csv(context_dir / "tables" / "user_must_review_context_cases.csv")
    abc_policy = _read_csv(abc_quality_dir / "tables" / "abc_phase25_policy.csv")
    correction_policy = _read_csv(contextual_corrections_dir / "tables" / "correction_phase25_policy.csv")
    correction_keep = _read_csv(contextual_corrections_dir / "tables" / "correction_examples_to_keep.csv")
    correction_user_review = _read_csv(
        contextual_corrections_dir / "tables" / "correction_user_must_review.csv"
    )
    wave5_summary = _read_csv(wave5_dir / "tables" / "wave5_endpoint_summary.csv")
    partial_summary = _read_csv(partial123_dir / "tables" / "partial123_summary.csv")

    readiness = pd.DataFrame(
        _matrix_rows(
            h4_closure=h4_closure,
            degree_readiness=degree_readiness,
            context_readiness=context_readiness,
            correction_policy=correction_policy,
            wave5_summary=wave5_summary,
            partial_summary=partial_summary,
            abc_policy=abc_policy,
        )
    )
    inputs = pd.DataFrame(_input_policy_rows())
    rule_candidates = pd.DataFrame(_rule_candidate_rows())
    soft_context = pd.DataFrame(_soft_context_rows())
    exclusions = pd.DataFrame(_exclusion_rows())
    future_work = pd.DataFrame(_future_rows())
    best_examples = _best_examples(
        h4_closure=h4_closure,
        context_confirms=context_confirms,
        correction_keep=correction_keep,
    )
    risk_register = pd.DataFrame(_risk_rows())
    user_review = _user_review_rows(context_user_review, correction_user_review)

    outputs = {
        "phase25_readiness_matrix": readiness,
        "phase25_inputs_policy": inputs,
        "phase25_rule_candidates": rule_candidates,
        "phase25_soft_context_features": soft_context,
        "phase25_exclusions": exclusions,
        "phase25_future_work": future_work,
        "phase25_best_examples": best_examples,
        "phase25_risk_register": risk_register,
        "phase25_user_review_if_any": user_review,
    }
    for name, frame in outputs.items():
        csv_path = tables_dir / f"{name}.csv"
        _write_csv(frame, csv_path)
        _write_markdown_index(csv_path, name)

    image_refs: list[str] = []
    for frame in (best_examples, user_review):
        if frame.empty or "chart_path" not in frame.columns:
            continue
        image_refs.extend([_string(value) for value in frame["chart_path"].dropna().tolist() if _string(value)])
    missing_images = [path for path in image_refs if path.lower().endswith(".png") and not _resolve_repo_path(path).exists()]

    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "source_dirs": {
            "h4_closure": _rel_to_repo(h4_closure_dir),
            "context": _rel_to_repo(context_dir),
            "abc_quality": _rel_to_repo(abc_quality_dir),
            "contextual_corrections": _rel_to_repo(contextual_corrections_dir),
            "wave5": _rel_to_repo(wave5_dir),
            "partial123": _rel_to_repo(partial123_dir),
            "degree": _rel_to_repo(degree_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "readiness_policy_counts": _counts(readiness, "phase25_policy"),
        "contextual_correction_policy_counts": _counts(correction_policy, "contextual_policy"),
        "missing_image_refs": missing_images,
        "elapsed_seconds": round(perf_counter() - start, 3),
        "no_base_counts_modified": True,
        "no_strategy_changes": True,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir=output_dir, readiness=readiness, best_examples=best_examples, run_meta=run_meta)
    return run_meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.4.5 pre-Phase 2.5 readiness closure.")
    parser.add_argument("--h4-closure-dir", type=Path, default=DEFAULT_H4_CLOSURE_DIR)
    parser.add_argument("--context-dir", type=Path, default=DEFAULT_CONTEXT_DIR)
    parser.add_argument("--abc-quality-dir", type=Path, default=DEFAULT_ABC_QUALITY_DIR)
    parser.add_argument("--contextual-corrections-dir", type=Path, default=DEFAULT_CONTEXTUAL_CORRECTIONS_DIR)
    parser.add_argument("--wave5-dir", type=Path, default=DEFAULT_WAVE5_DIR)
    parser.add_argument("--partial123-dir", type=Path, default=DEFAULT_PARTIAL123_DIR)
    parser.add_argument("--degree-dir", type=Path, default=DEFAULT_DEGREE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_meta = build_phase25_readiness(
        h4_closure_dir=args.h4_closure_dir,
        context_dir=args.context_dir,
        abc_quality_dir=args.abc_quality_dir,
        contextual_corrections_dir=args.contextual_corrections_dir,
        wave5_dir=args.wave5_dir,
        partial123_dir=args.partial123_dir,
        degree_dir=args.degree_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(run_meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
