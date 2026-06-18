from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


HARD_RULES = {
    "wave 2 breaks wave 1 origin",
    "wave 3 does not exceed wave 1 extreme",
    "wave 3 is shorter than both wave 1 and wave 5",
    "B leg breaks ABC origin",
    "B retracement exceeds configured maximum",
}

SOFT_RULES = {
    "wave 4 overlaps wave 1 territory",
    "wave 5 fails to exceed wave 3 extreme",
    "wave 2 retracement is visually too deep",
    "wave 4 retracement is visually too deep",
    "candidate impulse conflicts with major context",
    "major context is opposed; keep as candidate for manual review",
    "ABC is too compressed: C leg is small versus A",
    "C leg does not exceed A extreme",
    "A or C leg has zero length",
    "one or more impulse legs have zero length",
}


@dataclass(frozen=True)
class InvalidationReviewConfig:
    """Configuration for WaveCount Phase 2.1 invalidation review."""

    include_ambiguous: bool = True


def split_reasons(reason: str) -> list[str]:
    if not isinstance(reason, str) or not reason.strip():
        return []
    return [part.strip() for part in reason.split(";") if part.strip()]


def classify_reason(reason: str) -> dict[str, Any]:
    parts = split_reasons(reason)
    hard = [item for item in parts if item in HARD_RULES]
    soft = [item for item in parts if item in SOFT_RULES]
    unknown = [item for item in parts if item not in HARD_RULES and item not in SOFT_RULES]

    if hard:
        severity = "hard_invalid"
        recommended_state = "invalidated_count"
        possible_false_negative = False
        review_note = "hard rule present; invalidation is methodologically defensible"
    elif soft:
        severity = "soft_invalid_or_ambiguous"
        recommended_state = "ambiguous_count"
        possible_false_negative = True
        review_note = "only soft rules present; keep as ambiguous instead of invalidated"
    else:
        severity = "needs_manual_review"
        recommended_state = "ambiguous_count"
        possible_false_negative = True
        review_note = "reason is not classified; requires visual manual review"

    return {
        "rule_severity": severity,
        "hard_reasons": " | ".join(hard),
        "soft_reasons": " | ".join(soft),
        "unknown_reasons": " | ".join(unknown),
        "recommended_state": recommended_state,
        "possible_false_negative": possible_false_negative,
        "review_note": review_note,
    }


def build_invalidations_review(
    candidate_counts: pd.DataFrame,
    config: InvalidationReviewConfig | None = None,
) -> pd.DataFrame:
    config = config or InvalidationReviewConfig()
    if candidate_counts is None or candidate_counts.empty:
        return pd.DataFrame()

    states = ["invalidated_count"]
    if config.include_ambiguous:
        states.append("ambiguous_count")

    review = candidate_counts[candidate_counts["count_state"].isin(states)].copy()
    if review.empty:
        return review

    classifications = review["reason"].apply(classify_reason).apply(pd.Series)
    review = pd.concat([review.reset_index(drop=True), classifications.reset_index(drop=True)], axis=1)
    review["state_changed_by_review"] = review["count_state"] != review["recommended_state"]
    return review


def build_rule_severity_summary(review: pd.DataFrame) -> pd.DataFrame:
    if review is None or review.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for _, row in review.iterrows():
        for reason in split_reasons(row.get("reason", "")):
            if reason in HARD_RULES:
                severity = "hard_invalid"
            elif reason in SOFT_RULES:
                severity = "soft_invalid_or_ambiguous"
            else:
                severity = "needs_manual_review"
            rows.append(
                {
                    "reason": reason,
                    "rule_severity": severity,
                    "pattern_type": row.get("pattern_type", ""),
                    "original_state": row.get("count_state", ""),
                    "recommended_state": row.get("recommended_state", ""),
                    "count_id": row.get("count_id", ""),
                }
            )
    if not rows:
        return pd.DataFrame()
    expanded = pd.DataFrame(rows)
    return (
        expanded.groupby(["reason", "rule_severity", "pattern_type", "original_state", "recommended_state"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["rule_severity", "count", "reason"], ascending=[True, False, True])
        .reset_index(drop=True)
    )


def review_config_to_dict(config: InvalidationReviewConfig) -> dict[str, Any]:
    return asdict(config)
