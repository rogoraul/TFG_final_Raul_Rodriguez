from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE250_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_0_guided_context_score_2026-05-24"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_5_1_guided_impulse_profile_2026-05-24"
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
    return text in {"true", "1", "yes", "y", "si"}


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
    for index, row in frame.iterrows():
        label = " | ".join(
            bit
            for bit in [
                _string(row.get("candidate_id")),
                _string(row.get("matches_guided_impulse_profile")),
                _string(row.get("phase252_candidate_action")),
            ]
            if bit
        )
        lines.append(f"## {index + 1}. {label or 'fila'}")
        for column in (
            "guided_profile_reasons",
            "guided_profile_failures",
            "phase252_reason",
            "notes",
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


def _seed_profile(seeds: pd.DataFrame) -> pd.DataFrame:
    if seeds.empty:
        rows = [
            {
                "profile_name": "guided_h4_intermediate_impulse_profile",
                "seed_count": 0,
                "criterion": "no_seed_candidates",
                "seed_values": "",
                "policy": "blocked",
                "weight": 0,
                "notes": "No seeds found in Phase 2.5.0.",
            }
        ]
        return pd.DataFrame(rows)

    def values(column: str) -> str:
        if column not in seeds.columns:
            return ""
        return "|".join(sorted({_string(v) for v in seeds[column].dropna().tolist() if _string(v)}))

    profile_name = "guided_h4_intermediate_impulse_profile"
    seed_count = len(seeds)
    rows = [
        ("timeframe_policy", values("timeframe_policy"), "required_soft_gate", 15, "Use H4/D1 as primary scale."),
        ("timeframe", values("timeframe"), "required_soft_gate", 8, "H4 candles are the seed timeframe."),
        ("swing_degree", values("swing_degree"), "required_soft_gate", 15, "Intermediate is the seed degree."),
        ("structure_type", values("structure_type"), "required_soft_gate", 18, "Seeds are impulse structures."),
        ("phase25_allowed_use", values("phase25_allowed_use"), "required_soft_gate", 10, "Seeds are candidate structures, not signals."),
        ("final_phase23_decision", values("final_phase23_decision"), "required_soft_gate", 10, "Seeds were already visually approved."),
        ("guided_quality_bucket", values("guided_quality_bucket"), "required_soft_gate", 10, "Seeds are high-quality context."),
        ("context_review_status", values("context_review_status"), "soft_context", 8, "Context must not be misleading or rescue a bad count."),
        ("ema_context_label", values("ema_context_label"), "soft_context", 5, "EMA should support or at least not mislead."),
        ("htf_ltf_alignment_label", values("htf_ltf_alignment_label"), "soft_context", 5, "HTF can align or explain conflict."),
        ("ewo_role_support", values("ewo_role_support"), "soft_context", 6, "EWO should support wave role or momentum."),
        ("wave5_diagnostic", values("wave5_diagnostic"), "soft_context", 3, "Wave 5 can be acceptable or explicitly provisional."),
    ]
    return pd.DataFrame(
        [
            {
                "profile_name": profile_name,
                "seed_count": seed_count,
                "criterion": criterion,
                "seed_values": seed_values,
                "policy": policy,
                "weight": weight,
                "notes": notes,
            }
            for criterion, seed_values, policy, weight, notes in rows
        ]
    )


def _profile_match(row: pd.Series) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    failures: list[str] = []
    critical_failures: list[str] = []

    def add(condition: bool, points: int, reason: str, failure: str, *, critical: bool = False) -> None:
        nonlocal score
        if condition:
            score += points
            reasons.append(reason)
        else:
            failures.append(failure)
            if critical:
                critical_failures.append(failure)

    structure = _string(row.get("structure_type"))
    timeframe_policy = _string(row.get("timeframe_policy"))
    timeframe = _string(row.get("timeframe")).upper()
    degree = _string(row.get("swing_degree"))
    allowed_use = _string(row.get("phase25_allowed_use"))
    phase23 = _string(row.get("final_phase23_decision"))
    bucket = _string(row.get("guided_quality_bucket"))
    context_review = _string(row.get("context_review_status"))
    ema_label = _string(row.get("ema_context_label"))
    htf_label = _string(row.get("htf_ltf_alignment_label"))
    ewo_support = _string(row.get("ewo_role_support"))
    wave5 = _string(row.get("wave5_diagnostic")) or _string(row.get("wave5_endpoint_status"))
    quality_score = _number(row.get("guided_quality_score"), 0)
    context_must_not_rescue = _boolish(row.get("context_must_not_rescue_bad_count"))

    add(structure == "impulse", 18, "structure=impulse", f"not impulse ({structure})", critical=True)
    add(timeframe_policy == "primary_h4_d1", 15, "primary H4/D1 policy", f"not H4/D1 primary ({timeframe_policy})")
    add(timeframe == "H4", 8, "timeframe=H4", f"timeframe is {timeframe or 'missing'}")
    add(degree == "intermediate", 15, "degree=intermediate", f"degree is {degree or 'missing'}")
    add(allowed_use == "candidate_structure", 10, "allowed as candidate_structure", f"allowed_use={allowed_use}")
    add(phase23 == "keep_as_good_example", 10, "2.3.4 keep_as_good_example", f"phase23_decision={phase23}")
    add(bucket == "high_quality_context" and quality_score >= 75, 10, "high quality score/bucket", f"score/bucket={quality_score}/{bucket}")
    add(
        context_review not in {"context_should_not_rescue_count", "context_misleading", "context_conflicts_suspicious"}
        and not context_must_not_rescue,
        8,
        "context does not rescue or mislead",
        f"context risk={context_review or context_must_not_rescue}",
        critical=context_review == "context_should_not_rescue_count" or context_must_not_rescue,
    )
    add(
        ema_label not in {"ema_noisy_or_misleading"} and "misleading" not in ema_label,
        5,
        f"EMA acceptable ({ema_label})",
        f"EMA problematic ({ema_label})",
    )
    add(
        htf_label not in {"conflict_suspicious"},
        5,
        f"HTF acceptable ({htf_label})",
        f"HTF suspicious ({htf_label})",
    )
    add(
        ewo_support in {"supports_wave_role", "partially_supports"},
        6,
        f"EWO compatible ({ewo_support})",
        f"EWO not supportive ({ewo_support})",
    )
    add(
        wave5 in {"clean_or_acceptable", "endpoint_uncertain", "premature_wave5_completion", "truncated_fifth_candidate", "", "not_applicable"},
        3,
        f"wave5 documented ({wave5 or 'not_available'})",
        f"wave5 problematic ({wave5})",
    )

    score = min(100, score)
    context_blocks_yes = context_review in {"context_misleading", "context_conflicts_suspicious"} or htf_label == "conflict_suspicious"
    if allowed_use == "exclude" or bucket == "exclude":
        critical_failures.append("excluded by Phase 2.5.0")

    if critical_failures:
        match = "no"
    elif (
        score >= 90
        and structure == "impulse"
        and timeframe_policy == "primary_h4_d1"
        and degree == "intermediate"
        and not context_blocks_yes
    ):
        match = "yes"
    elif score >= 55 and structure == "impulse":
        match = "near_miss"
    else:
        match = "no"

    return {
        "matches_guided_impulse_profile": match,
        "guided_profile_match_score": score,
        "guided_profile_reasons": "; ".join(reasons),
        "guided_profile_failures": "; ".join(failures),
        "guided_profile_critical_failures": "; ".join(critical_failures),
    }


def _near_miss_reason(row: pd.Series) -> str:
    if _string(row.get("matches_guided_impulse_profile")) != "near_miss":
        return ""
    degree = _string(row.get("swing_degree"))
    timeframe_policy = _string(row.get("timeframe_policy"))
    htf = _string(row.get("htf_ltf_alignment_label"))
    ewo = _string(row.get("ewo_role_support"))
    ema = _string(row.get("ema_context_label"))
    failures = _string(row.get("guided_profile_failures"))
    if degree == "major":
        return "higher_degree_context"
    if degree == "minor":
        return "minor_substructure"
    if timeframe_policy != "primary_h4_d1":
        return "auxiliary_timeframe"
    if "HTF suspicious" in failures or htf == "conflict_suspicious":
        return "context_conflict"
    if "EWO not supportive" in failures or ewo in {"unclear", "contradicts", "not_available"}:
        return "ewo_not_clear"
    if "EMA problematic" in failures or "misleading" in ema:
        return "ema_not_clear"
    return "soft_rule_gap"


def _phase252_action(row: pd.Series) -> dict[str, str]:
    match = _string(row.get("matches_guided_impulse_profile"))
    near_reason = _string(row.get("near_miss_reason"))
    structure = _string(row.get("structure_type"))
    degree = _string(row.get("swing_degree"))
    bucket = _string(row.get("guided_quality_bucket"))
    allowed = _string(row.get("phase25_allowed_use"))

    if match == "yes":
        return {
            "phase252_candidate_action": "keep_as_seed_example",
            "phase252_reason": "Defines the minimal H4/D1 intermediate guided impulse profile.",
        }
    if match == "near_miss":
        if near_reason in {"higher_degree_context", "minor_substructure", "auxiliary_timeframe"}:
            return {
                "phase252_candidate_action": "manual_review_before_expansion",
                "phase252_reason": f"Near-miss because {near_reason}; useful context but not base profile.",
            }
        return {
            "phase252_candidate_action": "manual_review_before_expansion",
            "phase252_reason": f"Near-miss due to {near_reason or 'soft rule gap'}. Do not force into seed set.",
        }
    if structure == "invalid_or_negative" or allowed == "exclude" or bucket == "exclude":
        return {
            "phase252_candidate_action": "use_as_negative_example",
            "phase252_reason": "Excluded or negative candidate confirms the profile should not rescue bad counts.",
        }
    if structure in {"partial_123", "abc_correction"}:
        return {
            "phase252_candidate_action": "exclude_from_expansion",
            "phase252_reason": "Not part of the base impulse profile; keep as context branch.",
        }
    if degree in {"major", "minor"}:
        return {
            "phase252_candidate_action": "manual_review_before_expansion",
            "phase252_reason": "Different degree from base profile; keep as context/substructure.",
        }
    return {
        "phase252_candidate_action": "exclude_from_expansion",
        "phase252_reason": "Does not match the minimal guided impulse profile.",
    }


def _write_report(output_dir: Path, seeds: pd.DataFrame, matches: pd.DataFrame, run_meta: dict[str, Any]) -> None:
    match_counts = _counts(matches, "matches_guided_impulse_profile")
    action_counts = _counts(matches, "phase252_candidate_action")
    lines = [
        "# WaveCount Fase 2.5.1 - Perfil de impulso guiado",
        "",
        "## Resumen",
        "",
        "Esta fase formaliza un perfil minimo de impulso H4/D1 `intermediate` usando los candidatos `ready_for_phase251_search=yes` de Fase 2.5.0.",
        "",
        "No busca en SQL, no recalcula pivotes, no cambia conteos base y no genera senales.",
        "",
        "## Seeds",
        "",
    ]
    if seeds.empty:
        lines.append("No hay seeds disponibles.")
    else:
        for _, row in seeds.iterrows():
            lines.append(
                f"- `{_string(row.get('candidate_id'))}`: score {_string(row.get('guided_quality_score'))}, "
                f"EWO `{_string(row.get('ewo_role_support'))}`, contexto `{_string(row.get('context_review_status'))}`."
            )
    lines.extend(["", "## Resultado de aplicacion", ""])
    for key, count in match_counts.items():
        lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Accion propuesta para 2.5.2", ""])
    for key, count in action_counts.items():
        lines.append(f"- `{key}`: {count}")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "El perfil guiado minimo es coherente como prototipo metodologico: selecciona solo impulsos H4/D1 `intermediate` ya validados por 2.5.0 y deja major/minor/auxiliares como contexto o subestructura.",
            "",
            "No debe convertirse en senal ni filtro operativo. Una futura Fase 2.5.2 podria expandir la busqueda H4/D1 con galeria especifica de matches y near-misses.",
            "",
            "## Run meta",
            "",
            "```json",
            json.dumps(run_meta, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_5_1_GUIDED_IMPULSE_PROFILE.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def build_guided_impulse_profile(*, phase250_dir: Path, output_dir: Path) -> dict[str, Any]:
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    candidates = _read_csv(phase250_dir / "tables" / "guided_context_candidates.csv")
    readiness = _read_csv(phase250_dir / "tables" / "phase251_search_readiness.csv")
    best_examples = _read_csv(phase250_dir / "tables" / "guided_context_best_examples.csv")
    exclusions = _read_csv(phase250_dir / "tables" / "guided_context_exclusions.csv")

    if not readiness.empty and "candidate_id" in readiness.columns:
        readiness_cols = [
            col
            for col in [
                "candidate_id",
                "ready_for_phase251_search",
                "phase251_reason",
                "suggested_next_search_mode",
            ]
            if col in readiness.columns
        ]
        candidates = candidates.drop(columns=[col for col in readiness_cols if col != "candidate_id" and col in candidates.columns])
        candidates = candidates.merge(readiness[readiness_cols].drop_duplicates("candidate_id"), on="candidate_id", how="left")

    seeds = candidates[candidates["ready_for_phase251_search"].astype(str).eq("yes")].copy()
    profile = _seed_profile(seeds)
    match_frame = candidates.copy()
    profile_match = match_frame.apply(_profile_match, axis=1, result_type="expand")
    match_frame = pd.concat([match_frame, profile_match], axis=1)
    match_frame["near_miss_reason"] = match_frame.apply(_near_miss_reason, axis=1)
    actions = match_frame.apply(_phase252_action, axis=1, result_type="expand")
    match_frame = pd.concat([match_frame, actions], axis=1)

    near_misses = match_frame[match_frame["matches_guided_impulse_profile"].eq("near_miss")].copy()
    exclusions_check = match_frame[
        (match_frame["matches_guided_impulse_profile"].eq("no"))
        & (
            match_frame["guided_quality_bucket"].astype(str).eq("exclude")
            | match_frame["phase25_allowed_use"].astype(str).eq("exclude")
            | match_frame["structure_type"].astype(str).eq("invalid_or_negative")
        )
    ].copy()
    phase252_plan = match_frame[
        [
            "candidate_id",
            "structure_type",
            "timeframe_policy",
            "swing_degree",
            "matches_guided_impulse_profile",
            "guided_profile_match_score",
            "phase252_candidate_action",
            "phase252_reason",
            "chart_path",
        ]
    ].copy()
    best_profile = match_frame[
        match_frame["matches_guided_impulse_profile"].isin(["yes", "near_miss"])
    ].copy()
    best_profile = best_profile.sort_values(
        ["matches_guided_impulse_profile", "guided_profile_match_score", "guided_quality_score"],
        ascending=[False, False, False],
    )
    user_review = match_frame[
        match_frame["matches_guided_impulse_profile"].eq("near_miss")
        | match_frame["phase252_candidate_action"].eq("manual_review_before_expansion")
    ].copy()

    outputs = {
        "guided_impulse_seed_profile": profile,
        "guided_impulse_profile_matches": match_frame,
        "guided_impulse_near_misses": near_misses,
        "guided_impulse_exclusions_check": exclusions_check,
        "phase252_expansion_plan": phase252_plan,
        "guided_impulse_best_examples": best_profile.head(40),
        "guided_impulse_user_review_if_any": user_review.head(60),
    }
    for name, frame in outputs.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    image_refs = [
        _string(value)
        for frame in (match_frame, best_profile, user_review)
        if "chart_path" in frame.columns
        for value in frame["chart_path"].dropna().tolist()
        if _string(value).lower().endswith(".png")
    ]
    missing_images = sorted({path for path in image_refs if not _resolve_repo_path(path).exists()})

    seed_check = {
        "seed_count": int(len(seeds)),
        "all_seed_impulses": bool(seeds["structure_type"].astype(str).eq("impulse").all()) if not seeds.empty else False,
        "all_seed_h4_d1": bool(seeds["timeframe_policy"].astype(str).eq("primary_h4_d1").all()) if not seeds.empty else False,
        "all_seed_intermediate": bool(seeds["swing_degree"].astype(str).eq("intermediate").all()) if not seeds.empty else False,
    }
    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "source_dir": _rel_to_repo(phase250_dir),
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "seed_check": seed_check,
        "match_counts": _counts(match_frame, "matches_guided_impulse_profile"),
        "near_miss_reason_counts": _counts(match_frame, "near_miss_reason"),
        "phase252_action_counts": _counts(match_frame, "phase252_candidate_action"),
        "phase250_best_examples_loaded": int(len(best_examples)),
        "phase250_exclusions_loaded": int(len(exclusions)),
        "missing_image_refs": missing_images,
        "no_base_counts_modified": True,
        "no_strategy_changes": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, seeds, match_frame, run_meta)
    return run_meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.1 guided impulse profile.")
    parser.add_argument("--phase250-dir", type=Path, default=DEFAULT_PHASE250_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_meta = build_guided_impulse_profile(phase250_dir=args.phase250_dir, output_dir=args.output_dir)
    print(json.dumps(run_meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
