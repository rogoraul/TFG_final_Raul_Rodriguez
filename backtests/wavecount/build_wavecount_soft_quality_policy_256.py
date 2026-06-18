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
DEFAULT_PHASE255_DIR = GUIDED_ROOT / "phase2_5_5_soft_policy_visual_audit_2026-05-24"
DEFAULT_PHASE252B_DIR = GUIDED_ROOT / "phase2_5_2b_h1_h4_aux_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_6_soft_policy_weight_adjustment_2026-05-24"

KEY_FALSE_POSITIVE_ID = "impulse_exp252_metals_xagusd_h4_intermediate_impulse_002"

PHASE256_BUCKETS = {
    "high_quality_structure",
    "usable_provisional_structure",
    "visual_watchlist_low_prominence",
    "auxiliary_substructure",
    "auxiliary_low_prominence_substructure",
    "ambiguous_structure",
    "experimental_only",
    "exclude_from_guided_search",
}


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
    return _string(value).strip().lower() in {"true", "1", "yes", "y"}


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
        name = _string(row.get("candidate_id")) or _string(row.get("phase256_policy_bucket")) or f"fila {idx + 1}"
        lines.append(f"## {idx + 1}. {name}")
        for column in (
            "phase256_policy_bucket",
            "previous_bucket",
            "new_bucket",
            "phase256_prominence_action",
            "phase256_adjustment_reason",
            "post_adjustment_visual_status",
            "phase257_recommendation",
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


def _copy_chart(row: pd.Series, output_dir: Path, idx: int) -> str:
    value = _string(row.get("chart_path")) or _string(row.get("reviewed_chart_path"))
    if not value:
        return ""
    src = _resolve_repo_path(value)
    if not src.exists():
        return value
    dest_dir = output_dir / "charts" / "rechecked"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{idx:03d}_{src.name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return _rel_to_repo(dest)


def _is_low_prominence(row: pd.Series) -> bool:
    prom = _string(row.get("prominence_policy_label"))
    scale = _string(row.get("scale_fit_label"))
    return (
        prom in {"low_prominence_vs_window", "better_as_lower_tf_substructure"}
        or scale in {"too_small_for_timeframe", "better_as_lower_tf_substructure"}
        or _boolish(row.get("should_downgrade_to_auxiliary"))
    )


def build_low_prominence_false_positive_diagnostics(
    scores: pd.DataFrame,
    visual_reviews: pd.DataFrame,
    false_positive_risks: pd.DataFrame,
) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    review_map = visual_reviews.set_index("candidate_id").to_dict("index") if "candidate_id" in visual_reviews else {}
    false_positive_ids = set(false_positive_risks.get("candidate_id", pd.Series(dtype=str)).dropna().astype(str))
    rows: list[dict[str, Any]] = []
    for _, row in scores.iterrows():
        if not _is_low_prominence(row):
            continue
        if _string(row.get("final_soft_quality_bucket")) == "exclude_from_guided_search":
            continue
        cid = _string(row.get("candidate_id"))
        review = review_map.get(cid, {})
        rows.append(
            {
                "candidate_id": cid,
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "review_category": _string(row.get("review_category")),
                "previous_bucket": _string(row.get("final_soft_quality_bucket")),
                "previous_score": _number(row.get("final_soft_quality_score")),
                "prominence_policy_label": _string(row.get("prominence_policy_label")),
                "scale_fit_label": _string(row.get("scale_fit_label")),
                "should_downgrade_to_auxiliary": _boolish(row.get("should_downgrade_to_auxiliary")),
                "ewo_policy_label": _string(row.get("ewo_policy_label")),
                "ema_htf_policy_label": _string(row.get("ema_htf_policy_label")),
                "context_must_not_rescue_bad_count": _boolish(row.get("context_must_not_rescue_bad_count")),
                "visual_policy_verdict_255": _string(review.get("visual_policy_verdict")),
                "recommended_policy_adjustment_255": _string(review.get("recommended_policy_adjustment")),
                "is_phase255_false_positive_risk": cid in false_positive_ids,
                "chart_path": _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def _phase256_decision(row: pd.Series, false_positive_ids: set[str]) -> dict[str, Any]:
    old_bucket = _string(row.get("final_soft_quality_bucket"))
    cid = _string(row.get("candidate_id"))
    source_scope = _string(row.get("source_scope"))
    degree = _string(row.get("swing_degree"))
    review_category = _string(row.get("review_category"))
    score = _number(row.get("final_soft_quality_score"))
    low_prominence = _is_low_prominence(row)
    is_false_positive = cid in false_positive_ids
    context_rescue = _boolish(row.get("context_must_not_rescue_bad_count"))

    new_bucket = old_bucket if old_bucket in PHASE256_BUCKETS else "experimental_only"
    score_delta = 0
    action = "no_change"
    reason = "No 2.5.6 prominence adjustment required."
    ready = "yes" if old_bucket in {"high_quality_structure", "usable_provisional_structure"} else "no"

    if old_bucket == "exclude_from_guided_search":
        new_bucket = "exclude_from_guided_search"
        ready = "no"
        action = "keep"
        reason = "Already excluded by 2.5.4; 2.5.5 did not find false-negative exclusions in the selected sample."
    elif source_scope == "h4_d1" and low_prominence and review_category == "impulse":
        if degree == "intermediate":
            new_bucket = "visual_watchlist_low_prominence"
            score_delta = -40 if is_false_positive else -30
            action = "downgrade_to_watchlist"
            ready = "watchlist_only"
            reason = (
                "H4/D1 intermediate impulse is too small for the visible window; EWO/EMA/HTF cannot keep it as "
                "a provisional seed. 2.5.5 visual audit flagged this as too lenient."
                if is_false_positive
                else "H4/D1 intermediate low-prominence impulse is kept only as non-operational watchlist."
            )
            if context_rescue:
                new_bucket = "exclude_from_guided_search"
                action = "exclude_low_prominence"
                ready = "no"
                reason += " Context also must not rescue this count."
        elif degree in {"minor", "major"}:
            new_bucket = "auxiliary_low_prominence_substructure"
            score_delta = -12
            action = "downgrade_to_auxiliary_low_prominence"
            ready = "auxiliary_only"
            reason = "H4/D1 low-prominence minor/major structure is useful only as substructure/context, not as primary seed."
        else:
            new_bucket = "visual_watchlist_low_prominence"
            score_delta = -20
            action = "downgrade_to_watchlist"
            ready = "watchlist_only"
            reason = "Low-prominence H4/D1 structure moved to non-operational watchlist."
    elif source_scope == "h1_h4" and low_prominence and review_category == "impulse":
        new_bucket = "auxiliary_low_prominence_substructure"
        score_delta = -6
        action = "downgrade_to_auxiliary_low_prominence"
        ready = "auxiliary_only"
        reason = "H1/H4 remains auxiliary; low-prominence cases are explicitly separated from primary H4/D1 profile."
    elif old_bucket == "auxiliary_substructure":
        ready = "auxiliary_only"
        action = "keep"
        reason = "Auxiliary bucket remains separated from primary guided search."
    elif old_bucket in {"ambiguous_structure", "experimental_only"}:
        ready = "manual_review" if old_bucket == "ambiguous_structure" else "no"
        action = "keep"
        reason = "Ambiguous/experimental structure remains non-operational."

    phase256_score = max(0, min(100, round(score + score_delta, 2)))
    return {
        "phase256_policy_bucket": new_bucket,
        "phase256_score": phase256_score,
        "phase256_score_delta": score_delta,
        "phase256_adjustment_reason": reason,
        "phase256_prominence_action": action,
        "phase256_ready_for_expansion": ready,
        "phase256_from_phase255_false_positive": is_false_positive,
    }


def build_phase256_policy_scores(scores: pd.DataFrame, false_positive_risks: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    false_positive_ids = set(false_positive_risks.get("candidate_id", pd.Series(dtype=str)).dropna().astype(str))
    rows = []
    for _, row in scores.iterrows():
        rows.append({**row.to_dict(), **_phase256_decision(row, false_positive_ids)})
    return pd.DataFrame(rows)


def build_bucket_changes(policy_scores: pd.DataFrame) -> pd.DataFrame:
    if policy_scores.empty:
        return pd.DataFrame()
    rows = []
    changed = policy_scores[
        policy_scores["final_soft_quality_bucket"].astype(str).ne(policy_scores["phase256_policy_bucket"].astype(str))
        | pd.to_numeric(policy_scores["phase256_score_delta"], errors="coerce").fillna(0).ne(0)
    ].copy()
    for _, row in changed.iterrows():
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "source_scope": _string(row.get("source_scope")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "previous_bucket": _string(row.get("final_soft_quality_bucket")),
                "new_bucket": _string(row.get("phase256_policy_bucket")),
                "previous_score": _number(row.get("final_soft_quality_score")),
                "new_score": _number(row.get("phase256_score")),
                "score_delta": _number(row.get("phase256_score_delta")),
                "change_from_phase255": _boolish(row.get("phase256_from_phase255_false_positive")),
                "requires_manual_review": _string(row.get("phase256_ready_for_expansion")) in {"watchlist_only", "manual_review"},
                "change_reason": _string(row.get("phase256_adjustment_reason")),
                "chart_path": _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_visual_recheck(bucket_changes: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    if bucket_changes.empty:
        return pd.DataFrame()
    rows = []
    for idx, (_, row) in enumerate(bucket_changes.iterrows(), start=1):
        cid = _string(row.get("candidate_id"))
        new_bucket = _string(row.get("new_bucket"))
        if cid == KEY_FALSE_POSITIVE_ID:
            status = "adjustment_correct"
            notes = "XAGUSD H4 no se ve bien como estructura H4/D1 principal; watchlist/exclusion no operativo corrige 2.5.4."
        elif _string(row.get("source_scope")) == "h4_d1":
            status = "adjustment_correct"
            notes = "H4/D1 de baja prominencia se separa como subestructura/watchlist antes de expansion."
        elif new_bucket == "auxiliary_low_prominence_substructure":
            status = "adjustment_correct"
            notes = "H1/H4 queda separado como auxiliar de baja prominencia, no como base principal."
        else:
            status = "manual_review_needed"
            notes = "Cambio de bucket derivado de prominencia; revisar si se usa en una galeria posterior."
        rows.append(
            {
                **row.to_dict(),
                "post_adjustment_visual_status": status,
                "visual_recheck_notes": notes,
                "reviewed_chart_path": _copy_chart(row, output_dir, idx),
            }
        )
    return pd.DataFrame(rows)


def build_phase257_recommendation(policy_scores: pd.DataFrame, bucket_changes: pd.DataFrame) -> pd.DataFrame:
    watchlist = int(policy_scores["phase256_policy_bucket"].astype(str).eq("visual_watchlist_low_prominence").sum()) if not policy_scores.empty else 0
    changed = int(len(bucket_changes))
    return pd.DataFrame(
        [
            {
                "phase257_recommendation": "descriptive_expansion_with_phase256_policy",
                "reason": (
                    "2.5.6 corrects low-prominence kept cases without relaxing exclusions. "
                    "Next phase can expand descriptively using phase256 buckets."
                ),
                "changed_cases": changed,
                "watchlist_cases": watchlist,
                "inputs": "phase256_policy_scores.csv; phase254_vs_phase256_bucket_changes.csv; phase256_visual_recheck.csv",
                "do_not_do": "do not generate signals, do not backtest, do not optimize returns, do not promote watchlist to entries",
                "validation_needed": "spot-check watchlist and low-prominence auxiliary cases if they become examples in the thesis",
            }
        ]
    )


def build_user_review_if_any(visual_recheck: pd.DataFrame) -> pd.DataFrame:
    if visual_recheck.empty:
        return pd.DataFrame()
    rows = []
    for _, row in visual_recheck.iterrows():
        if _string(row.get("candidate_id")) == KEY_FALSE_POSITIVE_ID:
            rows.append(
                {
                    "review_reason": "key_false_positive_corrected",
                    "candidate_id": _string(row.get("candidate_id")),
                    "phase256_policy_bucket": _string(row.get("new_bucket")),
                    "post_adjustment_visual_status": _string(row.get("post_adjustment_visual_status")),
                    "notes": _string(row.get("visual_recheck_notes")),
                    "reviewed_chart_path": _string(row.get("reviewed_chart_path")),
                }
            )
    return pd.DataFrame(rows)


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
        "# WaveCount Phase 2.5.6 Soft Policy Weight Adjustment",
        "",
        f"Generated at: {meta['generated_at']}",
        "",
        "## Scope",
        "",
        "Ajuste conservador de buckets/pesos de prominencia despues de la auditoria visual 2.5.5.",
        "No genera senales, no ejecuta backtests y no cambia pivotes, conteos ni estrategias.",
        "",
        "## Results",
        "",
        f"- Total scored rows: {meta['total_scores']}",
        f"- Changed bucket/score rows: {meta['changed_cases']}",
        f"- Watchlist low-prominence rows: {meta['watchlist_cases']}",
        f"- Auxiliary low-prominence rows: {meta['auxiliary_low_prominence_cases']}",
        f"- Excluded rows: {meta['excluded_rows']}",
        "",
        "## Key Decision",
        "",
        meta["decision_summary"],
        "",
        "## Tables",
        "",
        "- `tables/low_prominence_false_positive_diagnostics.csv`",
        "- `tables/phase256_policy_scores.csv`",
        "- `tables/phase254_vs_phase256_bucket_changes.csv`",
        "- `tables/phase256_watchlist_cases.csv`",
        "- `tables/phase256_exclusions.csv`",
        "- `tables/phase256_visual_recheck.csv`",
        "- `tables/phase257_recommendation.csv`",
        "- `tables/user_review_if_any.csv`",
    ]
    (output_dir / "WAVECOUNT_PHASE2_5_6_SOFT_POLICY_WEIGHT_ADJUSTMENT.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def build_soft_policy_weight_adjustment_256(
    phase254_dir: Path = DEFAULT_PHASE254_DIR,
    phase255_dir: Path = DEFAULT_PHASE255_DIR,
    phase252b_dir: Path = DEFAULT_PHASE252B_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    start = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    scores = _read_csv(phase254_dir / "tables" / "structural_quality_scores.csv")
    prominence = _read_csv(phase254_dir / "tables" / "prominence_soft_policy.csv")
    visual_reviews = _read_csv(phase255_dir / "tables" / "visual_policy_case_review.csv")
    false_positive = _read_csv(phase255_dir / "tables" / "policy_false_positive_risks.csv")
    weight_candidates = _read_csv(phase255_dir / "tables" / "weight_adjustment_candidates.csv")
    phase256_recommendation_in = _read_csv(phase255_dir / "tables" / "phase256_recommendation.csv")
    prominence_diagnostics = _read_csv(phase252b_dir / "tables" / "prominence_diagnostics.csv")
    h4_suspicious = _read_csv(phase252b_dir / "tables" / "h4_suspicious_scale_cases.csv")

    low_diag = build_low_prominence_false_positive_diagnostics(scores, visual_reviews, false_positive)
    policy_scores = build_phase256_policy_scores(scores, false_positive)
    bucket_changes = build_bucket_changes(policy_scores)
    watchlist = policy_scores[policy_scores["phase256_policy_bucket"].eq("visual_watchlist_low_prominence")].copy()
    exclusions = policy_scores[policy_scores["phase256_policy_bucket"].eq("exclude_from_guided_search")].copy()
    visual_recheck = build_visual_recheck(bucket_changes, output_dir)
    phase257 = build_phase257_recommendation(policy_scores, bucket_changes)
    user_review = build_user_review_if_any(visual_recheck)

    tables = {
        "low_prominence_false_positive_diagnostics": low_diag,
        "phase256_policy_scores": policy_scores,
        "phase254_vs_phase256_bucket_changes": bucket_changes,
        "phase256_watchlist_cases": watchlist,
        "phase256_exclusions": exclusions,
        "phase256_visual_recheck": visual_recheck,
        "phase257_recommendation": phase257,
        "user_review_if_any": user_review,
    }
    for name, frame in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name)

    missing_refs = _validate_image_refs(tables)
    total_scores = int(len(policy_scores))
    excluded = int(policy_scores["phase256_policy_bucket"].eq("exclude_from_guided_search").sum()) if total_scores else 0
    watchlist_count = int(policy_scores["phase256_policy_bucket"].eq("visual_watchlist_low_prominence").sum()) if total_scores else 0
    aux_low = int(policy_scores["phase256_policy_bucket"].eq("auxiliary_low_prominence_substructure").sum()) if total_scores else 0
    key_row = policy_scores[policy_scores["candidate_id"].astype(str).eq(KEY_FALSE_POSITIVE_ID)]
    key_bucket = _string(key_row.iloc[0].get("phase256_policy_bucket")) if not key_row.empty else ""
    decision_summary = (
        f"{KEY_FALSE_POSITIVE_ID} deja de ser `usable_provisional_structure` y pasa a `{key_bucket}`. "
        "`exclude_from_guided_search` se mantiene estable; el ajuste no relaja la politica, solo separa "
        "baja prominencia en watchlist/subestructura auxiliar no operativa."
    )
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase254_dir": _rel_to_repo(phase254_dir),
            "phase255_dir": _rel_to_repo(phase255_dir),
            "phase252b_dir": _rel_to_repo(phase252b_dir),
            "scores": int(len(scores)),
            "prominence_rows": int(len(prominence)),
            "visual_review_rows": int(len(visual_reviews)),
            "false_positive_rows": int(len(false_positive)),
            "weight_candidate_rows": int(len(weight_candidates)),
            "phase256_recommendation_input_rows": int(len(phase256_recommendation_in)),
            "prominence_diagnostics_rows": int(len(prominence_diagnostics)),
            "h4_suspicious_rows": int(len(h4_suspicious)),
        },
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "total_scores": total_scores,
        "changed_cases": int(len(bucket_changes)),
        "watchlist_cases": watchlist_count,
        "auxiliary_low_prominence_cases": aux_low,
        "excluded_rows": excluded,
        "key_false_positive_id": KEY_FALSE_POSITIVE_ID,
        "key_false_positive_phase256_bucket": key_bucket,
        "missing_output_image_refs": missing_refs,
        "decision_summary": decision_summary,
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
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.6 soft policy weight adjustment.")
    parser.add_argument("--phase254-dir", type=Path, default=DEFAULT_PHASE254_DIR)
    parser.add_argument("--phase255-dir", type=Path, default=DEFAULT_PHASE255_DIR)
    parser.add_argument("--phase252b-dir", type=Path, default=DEFAULT_PHASE252B_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_soft_policy_weight_adjustment_256(
        phase254_dir=args.phase254_dir,
        phase255_dir=args.phase255_dir,
        phase252b_dir=args.phase252b_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
