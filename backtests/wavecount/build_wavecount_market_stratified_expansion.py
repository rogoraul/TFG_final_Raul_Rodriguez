from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from backtests.wavecount.build_wavecount_guided_impulse_expansion import (
    _near_miss_reason,
    _phase253_action,
    _profile_match_expanded,
    _visual_review_status,
)
from backtests.wavecount.build_wavecount_h1_h4_aux_expansion import _prominence_metrics
from backtests.wavecount.build_wavecount_soft_quality_policy import build_structural_quality_scores
from backtests.wavecount.build_wavecount_soft_quality_policy_256 import build_phase256_policy_scores
from backtests.wavecount.wavecount_context_gallery import build_context_gallery
from backtests.wavecount.wavecount_visual_review_gallery import VisualReviewSpec, build_visual_review_gallery


REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDED_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "05_guided_profile"
DEFAULT_PHASE256_DIR = GUIDED_ROOT / "phase2_5_6_soft_policy_weight_adjustment_2026-05-24"
DEFAULT_PHASE256B_DIR = GUIDED_ROOT / "phase2_5_6b_market_group_bias_audit_2026-05-24"
DEFAULT_PHASE252B_DIR = GUIDED_ROOT / "phase2_5_2b_h1_h4_aux_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_7_market_stratified_expansion_2026-05-24"

INCLUDED_GROUPS = ("Forex Majors", "Index", "Metals")
EXCLUDED_SQL_GROUPS = ("Commodities", "Crypto", "Forex Exotic")
PHASE256_BUCKETS = (
    "high_quality_structure",
    "usable_provisional_structure",
    "visual_watchlist_low_prominence",
    "auxiliary_substructure",
    "auxiliary_low_prominence_substructure",
    "ambiguous_structure",
    "experimental_only",
    "exclude_from_guided_search",
)


@dataclass(frozen=True)
class ExpansionConfig:
    max_h4_symbols_per_group: int = 6
    h4_ltf_rows: int = 1100
    htf_rows: int = 520
    include_existing_phase256: bool = True


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


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for idx, row in frame.iterrows():
        label = (
            _string(row.get("candidate_id"))
            or _string(row.get("resolved_market_group"))
            or _string(row.get("phase258_recommendation"))
            or f"fila {idx + 1}"
        )
        lines.append(f"## {idx + 1}. {label}")
        for column in (
            "resolved_market_group",
            "phase257_policy_bucket",
            "phase257_visual_verdict",
            "market_group_bias_risk",
            "phase258_recommendation",
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


def _slug(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "")
        .replace("-", "_")
    )


def _safe_symbol(value: str) -> str:
    return _slug(value).replace("_r", "r")


def _add_missing_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out


def _merge_prominence_values(scores: pd.DataFrame, prominence: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return scores.copy()
    wanted = [
        "candidate_id",
        "prominence_vs_window",
        "duration_vs_window",
        "relative_structure_size",
        "scale_fit_label",
    ]
    available = [column for column in wanted if column in prominence.columns]
    if len(available) <= 1:
        return scores.copy()
    merged = scores.merge(prominence[available].drop_duplicates("candidate_id"), on="candidate_id", how="left", suffixes=("", "_metric"))
    for column in wanted[1:]:
        metric = f"{column}_metric"
        if metric in merged:
            if column in merged:
                merged[column] = merged[column].where(merged[column].notna() & merged[column].astype(str).ne(""), merged[metric])
            else:
                merged[column] = merged[metric]
            merged = merged.drop(columns=[metric])
    return merged


def choose_symbols_by_market_group(
    sql_symbol_timeframes: pd.DataFrame,
    mapping: pd.DataFrame,
    *,
    max_symbols_per_group: int,
) -> pd.DataFrame:
    """Pick a balanced H4/D1 symbol set using SQL inventory, with artifact symbols first."""
    if sql_symbol_timeframes.empty:
        return pd.DataFrame(columns=["resolved_market_group", "symbol", "selection_rank", "selection_reason"])

    h4 = sql_symbol_timeframes[sql_symbol_timeframes["timeframe"].astype(str).eq("H4")]
    d1 = sql_symbol_timeframes[sql_symbol_timeframes["timeframe"].astype(str).eq("D1")]
    available = h4.merge(
        d1[["symbol", "sql_market_group", "rows_count"]],
        on=["symbol", "sql_market_group"],
        how="inner",
        suffixes=("_h4", "_d1"),
    )
    available = available[available["sql_market_group"].isin(INCLUDED_GROUPS)].copy()
    available["enabled"] = available.get("enabled", 1)
    available = available[available["enabled"].fillna(1).astype(int).eq(1)]

    artifact_symbols = set(
        mapping[
            mapping.get("artifact_market_group", pd.Series(dtype=str)).fillna("").astype(str).ne("")
            & mapping.get("resolved_market_group", pd.Series(dtype=str)).isin(INCLUDED_GROUPS)
        ]
        .get("symbol", pd.Series(dtype=str))
        .dropna()
        .astype(str)
    )

    rows: list[dict[str, Any]] = []
    for group in INCLUDED_GROUPS:
        part = available[available["sql_market_group"].eq(group)].copy()
        part["is_artifact_symbol"] = part["symbol"].astype(str).isin(artifact_symbols)
        part = part.sort_values(["is_artifact_symbol", "symbol"], ascending=[False, True]).head(max_symbols_per_group)
        for rank, (_, row) in enumerate(part.iterrows(), start=1):
            rows.append(
                {
                    "resolved_market_group": group,
                    "symbol": _string(row.get("symbol")),
                    "timeframe": "H4",
                    "htf_timeframe": "D1",
                    "rows_h4": int(_number(row.get("rows_count_h4"))),
                    "rows_d1": int(_number(row.get("rows_count_d1"))),
                    "selection_rank": rank,
                    "selection_reason": "existing_wavecount_symbol" if _boolish(row.get("is_artifact_symbol")) else "sql_available_balance_fill",
                }
            )
    return pd.DataFrame(rows)


def build_h4_d1_specs(symbol_selection: pd.DataFrame, ltf_rows: int) -> tuple[VisualReviewSpec, ...]:
    specs: list[VisualReviewSpec] = []
    for _, row in symbol_selection.iterrows():
        group = _string(row.get("resolved_market_group"))
        symbol = _string(row.get("symbol"))
        spec_id = f"exp257_{_slug(group)}_{_safe_symbol(symbol)}_h4"
        specs.append(VisualReviewSpec(spec_id, group, symbol, "H4", ltf_rows))
    return tuple(specs)


def build_expansion_scope(
    symbol_selection: pd.DataFrame,
    sql_categories: pd.DataFrame,
    config: ExpansionConfig,
) -> pd.DataFrame:
    rows = []
    available_groups = sorted(sql_categories.get("sql_market_group", pd.Series(dtype=str)).dropna().astype(str).tolist())
    for group in INCLUDED_GROUPS:
        selected = symbol_selection[symbol_selection["resolved_market_group"].eq(group)]
        rows.append(
            {
                "expansion_scope": "controlled_h4_d1_by_market_group",
                "resolved_market_group": group,
                "included": True,
                "symbols_included": "|".join(selected["symbol"].astype(str).tolist()),
                "symbol_count": int(len(selected)),
                "timeframe": "H4",
                "htf_timeframe": "D1",
                "max_symbols_per_group": config.max_h4_symbols_per_group,
                "ltf_rows_per_symbol": config.h4_ltf_rows,
                "htf_rows": config.htf_rows,
                "generation_mode": "new_diagnostic_h4_d1_plus_existing_h1_h4_auxiliary",
                "notes": "Grupo representado en WaveCount 2.5.6; expansion descriptiva offline.",
            }
        )
    for group in EXCLUDED_SQL_GROUPS:
        rows.append(
            {
                "expansion_scope": "controlled_h4_d1_by_market_group",
                "resolved_market_group": group,
                "included": False,
                "symbols_included": "",
                "symbol_count": 0,
                "timeframe": "",
                "htf_timeframe": "",
                "max_symbols_per_group": config.max_h4_symbols_per_group,
                "ltf_rows_per_symbol": "",
                "htf_rows": "",
                "generation_mode": "not_included",
                "notes": (
                    "Existe en SQL pero no tiene evidencia WaveCount 2.5.6; no se extrapolan conclusiones."
                    if group in available_groups
                    else "No presente en SQL inventory revisado."
                ),
            }
        )
    return pd.DataFrame(rows)


def generate_h4_d1_diagnostic_sample(
    *,
    symbol_selection: pd.DataFrame,
    output_dir: Path,
    config: ExpansionConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    specs = build_h4_d1_specs(symbol_selection, config.h4_ltf_rows)
    if not specs:
        return pd.DataFrame(), pd.DataFrame(), {"charts_ok": 0, "specs": []}

    phase23_dir = output_dir / "diagnostic_phase2_3_h4_d1_stratified"
    phase24_dir = output_dir / "diagnostic_phase2_4_h4_d1_stratified"
    phase23_meta = build_visual_review_gallery(output_dir=phase23_dir, specs=specs)
    phase24_meta = build_context_gallery(
        input_dir=phase23_dir,
        output_dir=phase24_dir,
        htf_rows=config.htf_rows,
        specs=specs,
    )
    candidates = _read_csv(phase24_dir / "tables" / "candidate_context.csv")
    context = _read_csv(phase24_dir / "tables" / "wavecount_context.csv")
    if candidates.empty:
        return candidates, context, {"charts_ok": 0, "specs": [item.example_id for item in specs]}

    candidates = candidates.copy()
    original_chart = candidates["chart_path"].copy() if "chart_path" in candidates else pd.Series([""] * len(candidates))
    original_context = (
        candidates["context_chart_path"].copy()
        if "context_chart_path" in candidates
        else pd.Series([""] * len(candidates))
    )
    candidates["source_count_chart_path"] = original_chart.apply(
        lambda value: _rel_to_repo(phase23_dir / _string(value)) if _string(value) else ""
    )
    candidates["source_context_chart_path"] = original_context.apply(
        lambda value: _rel_to_repo(phase24_dir / _string(value)) if _string(value) else ""
    )
    candidates["chart_path"] = candidates["source_context_chart_path"]
    candidates["context_chart_path"] = candidates["source_context_chart_path"]
    candidates["source_scope"] = "h4_d1"
    candidates["expansion_origin"] = "new_controlled_h4_d1_by_market_group"
    candidates["diagnostic_only"] = True

    profile = candidates.apply(_profile_match_expanded, axis=1, result_type="expand")
    candidates = pd.concat([candidates, profile], axis=1)
    candidates["near_miss_reason"] = candidates.apply(_near_miss_reason, axis=1)
    visual = candidates.apply(_visual_review_status, axis=1, result_type="expand")
    candidates = pd.concat([candidates, visual], axis=1)
    actions = candidates.apply(_phase253_action, axis=1, result_type="expand")
    candidates = pd.concat([candidates, actions], axis=1)
    candidates["should_enter_visual_gallery"] = True

    prominence = _prominence_metrics(candidates, context, source_scope="h4_d1")
    candidates = _merge_prominence_values(candidates, prominence)
    meta = {
        "phase23_charts_ok": len([row for row in phase23_meta.get("charts", []) if row.get("status") == "ok"]),
        "phase24_charts_ok": len([row for row in phase24_meta.get("charts", []) if row.get("status") == "ok"]),
        "specs": [item.example_id for item in specs],
        "candidate_rows": int(len(candidates)),
        "context_rows": int(len(context)),
        "phase23_dir": _rel_to_repo(phase23_dir),
        "phase24_dir": _rel_to_repo(phase24_dir),
    }
    return candidates, prominence, meta


def apply_phase256_policy_to_new_candidates(h4_candidates: pd.DataFrame) -> pd.DataFrame:
    if h4_candidates.empty:
        return pd.DataFrame()
    quality = build_structural_quality_scores(h4_candidates)
    return build_phase256_policy_scores(quality, pd.DataFrame())


def prepare_existing_scores(
    scores_with_group: pd.DataFrame,
    prominence_diagnostics: pd.DataFrame,
) -> pd.DataFrame:
    existing = scores_with_group.copy()
    existing["expansion_origin"] = "reused_phase256_existing_policy"
    existing["diagnostic_only"] = True
    return _merge_prominence_values(existing, prominence_diagnostics)


def add_market_group_fields(scores: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return scores.copy()
    fields = [
        "symbol",
        "sql_market_group",
        "artifact_market_group",
        "resolved_market_group",
        "mapping_confidence",
        "category_source",
        "symbol_in_sql",
    ]
    available = [column for column in fields if column in mapping.columns]
    merged = scores.merge(mapping[available].drop_duplicates("symbol"), on="symbol", how="left")
    if "resolved_market_group" not in merged:
        merged["resolved_market_group"] = merged.get("group", "unknown_market_group")
    merged["resolved_market_group"] = merged["resolved_market_group"].fillna(merged.get("group", "unknown_market_group"))
    merged["mapping_confidence"] = merged.get("mapping_confidence", "unknown").fillna("unknown")
    return merged


def build_phase257_policy_scores(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    out = scores.copy()
    out["phase257_policy_bucket"] = out["phase256_policy_bucket"]
    out["phase257_score"] = out["phase256_score"]
    out["phase257_policy_reasons"] = out.get("phase256_adjustment_reason", "").fillna("").astype(str)
    out["phase257_policy_warnings"] = out.get("policy_warnings", "").fillna("").astype(str)
    out["phase257_ready_for_next_step"] = out.get("phase256_ready_for_expansion", "").fillna("").astype(str)
    return out


def build_bucket_distribution_by_group(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if scores.empty:
        return pd.DataFrame()
    for group, part in scores.groupby("resolved_market_group", dropna=False):
        row: dict[str, Any] = {
            "resolved_market_group": _string(group),
            "candidate_count": int(len(part)),
            "h4_d1_count": int(part.get("source_scope", pd.Series(dtype=str)).astype(str).eq("h4_d1").sum()),
            "h1_h4_count": int(part.get("source_scope", pd.Series(dtype=str)).astype(str).eq("h1_h4").sum()),
            "unique_symbols": int(part.get("symbol", pd.Series(dtype=str)).nunique()),
        }
        for bucket in PHASE256_BUCKETS:
            count = int(part.get("phase257_policy_bucket", pd.Series(dtype=str)).astype(str).eq(bucket).sum())
            row[bucket] = count
            row[f"{bucket}_pct"] = round(count / len(part) * 100, 2) if len(part) else 0.0
        for degree in ("minor", "intermediate", "major"):
            row[f"{degree}_count"] = int(part.get("swing_degree", pd.Series(dtype=str)).astype(str).eq(degree).sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("resolved_market_group").reset_index(drop=True)


def _numeric_stats(part: pd.DataFrame, column: str) -> dict[str, Any]:
    values = pd.to_numeric(part.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    if values.empty:
        return {
            f"{column}_count": 0,
            f"{column}_mean": "",
            f"{column}_median": "",
            f"{column}_p10": "",
            f"{column}_p25": "",
            f"{column}_p75": "",
            f"{column}_p90": "",
            f"{column}_min": "",
            f"{column}_max": "",
        }
    return {
        f"{column}_count": int(len(values)),
        f"{column}_mean": round(float(values.mean()), 6),
        f"{column}_median": round(float(values.median()), 6),
        f"{column}_p10": round(float(values.quantile(0.10)), 6),
        f"{column}_p25": round(float(values.quantile(0.25)), 6),
        f"{column}_p75": round(float(values.quantile(0.75)), 6),
        f"{column}_p90": round(float(values.quantile(0.90)), 6),
        f"{column}_min": round(float(values.min()), 6),
        f"{column}_max": round(float(values.max()), 6),
    }


def build_prominence_percentiles(
    scores: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    rows = []
    for keys, part in scores.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {column: _string(value) for column, value in zip(group_columns, keys)}
        row["candidate_count"] = int(len(part))
        for column in ("prominence_vs_window", "duration_vs_window"):
            row.update(_numeric_stats(part, column))
        row["low_prominence_count"] = int(
            part.get("prominence_policy_label", pd.Series(dtype=str))
            .astype(str)
            .isin(["low_prominence_vs_window", "better_as_lower_tf_substructure"])
            .sum()
        )
        row["too_small_for_timeframe_count"] = int(
            part.get("scale_fit_label", pd.Series(dtype=str)).astype(str).eq("too_small_for_timeframe").sum()
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)


def _label_counts(part: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in part:
        return {}
    return {str(key or "blank"): int(value) for key, value in part[column].fillna("").astype(str).value_counts().items()}


def build_context_distribution_by_group(
    scores: pd.DataFrame,
    *,
    label_columns: list[str],
    score_column: str,
) -> pd.DataFrame:
    rows = []
    if scores.empty:
        return pd.DataFrame()
    for group, part in scores.groupby("resolved_market_group", dropna=False):
        row: dict[str, Any] = {
            "resolved_market_group": _string(group),
            "candidate_count": int(len(part)),
        }
        if score_column in part:
            values = pd.to_numeric(part[score_column], errors="coerce").dropna()
            row[f"{score_column}_mean"] = round(float(values.mean()), 4) if not values.empty else ""
        for column in label_columns:
            for label, count in _label_counts(part, column).items():
                row[f"{column}_{label}"] = count
        rows.append(row)
    return pd.DataFrame(rows).sort_values("resolved_market_group").reset_index(drop=True)


def select_visual_gallery(scores: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    selected: list[pd.Series] = []
    reasons: list[str] = []
    seen: set[str] = set()

    def add(part: pd.DataFrame, reason: str, *, ascending: bool = False) -> None:
        if part.empty:
            return
        sort_column = "phase257_score" if "phase257_score" in part else "phase256_score"
        ordered = part.sort_values(sort_column, ascending=ascending)
        for _, candidate in ordered.iterrows():
            cid = _string(candidate.get("candidate_id"))
            if cid and cid not in seen and _has_existing_chart(candidate):
                selected.append(candidate)
                reasons.append(reason)
                seen.add(cid)
                return

    for group, part in scores.groupby("resolved_market_group", dropna=False):
        add(part[part["phase257_policy_bucket"].eq("high_quality_structure")], "best_high_quality")
        add(part[part["phase257_policy_bucket"].eq("usable_provisional_structure")], "best_usable_provisional")
        add(part[part["phase257_policy_bucket"].eq("visual_watchlist_low_prominence")], "watchlist_low_prominence")
        add(part[part["phase257_policy_bucket"].eq("auxiliary_low_prominence_substructure")], "auxiliary_low_prominence")
        add(part[part["phase257_policy_bucket"].eq("exclude_from_guided_search")], "excluded_near_threshold")
        add(part[part.get("ewo_soft_support", pd.Series(dtype=str)).astype(str).eq("supports")], "ewo_support_case")
        add(
            part[
                part.get("ema_htf_policy_label", pd.Series(dtype=str))
                .fillna("")
                .astype(str)
                .str.contains("misleading|conflict", case=False, regex=True)
            ],
            "ema_htf_conflict_or_misleading",
        )
        add(
            part[
                part.get("prominence_policy_label", pd.Series(dtype=str))
                .astype(str)
                .isin(["low_prominence_vs_window", "better_as_lower_tf_substructure"])
            ],
            "low_prominence_case",
        )

    rows = []
    for idx, (row, reason) in enumerate(zip(selected, reasons), start=1):
        copied = copy_chart_to_group_folder(row, output_dir, idx)
        rows.append(
            {
                "selection_order": idx,
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": _string(row.get("resolved_market_group")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "htf_timeframe": _string(row.get("htf_timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "source_scope": _string(row.get("source_scope")),
                "phase257_policy_bucket": _string(row.get("phase257_policy_bucket")),
                "phase257_score": _number(row.get("phase257_score")),
                "selection_reason": reason,
                "prominence_policy_label": _string(row.get("prominence_policy_label")),
                "scale_fit_label": _string(row.get("scale_fit_label")),
                "ewo_policy_label": _string(row.get("ewo_policy_label")),
                "ema_htf_policy_label": _string(row.get("ema_htf_policy_label")),
                "chart_path": copied or _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def _has_existing_chart(row: pd.Series) -> bool:
    for column in ("chart_path", "reviewed_chart_path", "context_chart_path", "source_context_chart_path"):
        value = _string(row.get(column))
        if value.lower().endswith(".png") and _resolve_repo_path(value).exists():
            return True
    return False


def copy_chart_to_group_folder(row: pd.Series, output_dir: Path, index: int) -> str:
    source_value = (
        _string(row.get("chart_path"))
        or _string(row.get("reviewed_chart_path"))
        or _string(row.get("context_chart_path"))
        or _string(row.get("source_context_chart_path"))
    )
    if not source_value:
        return ""
    source = _resolve_repo_path(source_value)
    if not source.exists():
        return source_value
    group_slug = _slug(_string(row.get("resolved_market_group")) or _string(row.get("group")) or "unknown")
    dest_dir = output_dir / "charts" / "by_market_group" / group_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{index:03d}_{_string(row.get('candidate_id'))}.png".replace(":", "-")
    if not dest.exists():
        shutil.copy2(source, dest)
    return _rel_to_repo(dest)


def build_visual_review(selection: pd.DataFrame, distribution: pd.DataFrame, percentiles: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame()
    dist_map = distribution.set_index("resolved_market_group").to_dict("index") if not distribution.empty else {}
    percentile_map = percentiles.set_index("resolved_market_group").to_dict("index") if not percentiles.empty else {}
    rows = []
    for _, row in selection.iterrows():
        group = _string(row.get("resolved_market_group"))
        bucket = _string(row.get("phase257_policy_bucket"))
        selection_reason = _string(row.get("selection_reason"))
        group_dist = dist_map.get(group, {})
        group_pct = percentile_map.get(group, {})
        exclusion_pct = _number(group_dist.get("exclude_from_guided_search_pct"))
        prom_median = _number(group_pct.get("prominence_vs_window_median"), -1)
        prom_label = _string(row.get("prominence_policy_label"))
        ema_label = _string(row.get("ema_htf_policy_label"))
        ewo_label = _string(row.get("ewo_policy_label"))

        if prom_label == "low_prominence_vs_window":
            verdict = "needs_percentile_normalization" if prom_median >= 0 and prom_median < 0.16 else "policy_correct"
            prom_verdict = "low_prominence_confirmed"
            risk = "medium"
            quality = 2
        elif bucket == "exclude_from_guided_search":
            verdict = "policy_correct"
            prom_verdict = "not_applicable"
            risk = "low" if exclusion_pct < 90 else "medium"
            quality = 2
        elif bucket in {"high_quality_structure", "usable_provisional_structure"}:
            verdict = "policy_correct"
            prom_verdict = "prominence_ok" if prom_label not in {"low_prominence_vs_window", "better_as_lower_tf_substructure"} else "prominence_threshold_questionable"
            risk = "low"
            quality = 4 if bucket == "usable_provisional_structure" else 5
        elif bucket.startswith("auxiliary"):
            verdict = "group_specific_behavior" if _string(row.get("source_scope")) == "h1_h4" else "policy_correct"
            prom_verdict = "needs_group_percentile" if "low_prominence" in bucket else "not_applicable"
            risk = "medium"
            quality = 3
        else:
            verdict = "not_enough_evidence"
            prom_verdict = "not_applicable"
            risk = "unknown"
            quality = 2

        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": group,
                "selection_reason": selection_reason,
                "phase257_policy_bucket": bucket,
                "phase257_visual_verdict": verdict,
                "market_group_bias_risk": risk,
                "visual_quality_score": quality,
                "prominence_verdict": prom_verdict,
                "ewo_verdict": _ewo_verdict(ewo_label),
                "ema_htf_verdict": _ema_htf_verdict(ema_label),
                "notes": "Visual gallery selected for manual/agent audit; verdict is methodological and non-operational.",
                "chart_path": _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def _ewo_verdict(label: str) -> str:
    if "support" in label:
        return "ewo_supports"
    if "misleading" in label or "contradict" in label:
        return "ewo_misleading"
    if not label:
        return "not_applicable"
    return "ewo_unclear"


def _ema_htf_verdict(label: str) -> str:
    if "support" in label or "with_htf" in label:
        return "ema_htf_supports"
    if "conflict" in label:
        return "ema_htf_conflict_explains_case"
    if "misleading" in label:
        return "ema_htf_misleading"
    if not label:
        return "not_applicable"
    return "not_applicable"


def build_group_bias_risks(distribution: pd.DataFrame, percentiles: pd.DataFrame, sql_categories: pd.DataFrame) -> pd.DataFrame:
    rows = []
    represented = set(distribution.get("resolved_market_group", pd.Series(dtype=str)).dropna().astype(str))
    sql_groups = set(sql_categories.get("sql_market_group", pd.Series(dtype=str)).dropna().astype(str))
    unrepresented = sorted(group for group in sql_groups if group and group not in represented)
    if unrepresented:
        rows.append(
            {
                "risk": "sql_group_unrepresented_in_wavecount_phase257",
                "where_seen": ", ".join(unrepresented),
                "impact": "No extrapolar conclusiones de WaveCount a estos grupos.",
                "market_group_bias_risk": "medium",
                "mitigation": "Mantener fuera de 2.5.7 y abrir auditoria separada si se usan.",
            }
        )
    if not distribution.empty and "exclude_from_guided_search_pct" in distribution:
        spread = float(distribution["exclude_from_guided_search_pct"].max() - distribution["exclude_from_guided_search_pct"].min())
        rows.append(
            {
                "risk": "phase257_exclusion_distribution_differs_by_group",
                "where_seen": "phase257_policy_bucket by resolved_market_group",
                "impact": f"Spread de exclusiones entre grupos: {spread:.2f} puntos porcentuales.",
                "market_group_bias_risk": "medium" if spread >= 20 else "low",
                "mitigation": "Reportar estratificado; no comparar scores brutos como normalizados.",
            }
        )
    if not percentiles.empty and "prominence_vs_window_median" in percentiles:
        values = pd.to_numeric(percentiles["prominence_vs_window_median"], errors="coerce").dropna()
        if not values.empty:
            spread = float(values.max() - values.min())
            rows.append(
                {
                    "risk": "prominence_distribution_differs_by_group",
                    "where_seen": "phase257_prominence_percentiles_by_group",
                    "impact": f"Spread de mediana de prominencia entre grupos: {spread:.4f}.",
                    "market_group_bias_risk": "medium" if spread >= 0.10 else "low",
                    "mitigation": "Abrir percentiles por grupo/simbolo si se endurece la politica.",
                }
            )
    return pd.DataFrame(rows)


def build_phase258_recommendation(
    distribution: pd.DataFrame,
    percentiles: pd.DataFrame,
    risks: pd.DataFrame,
) -> pd.DataFrame:
    exclusion_spread = 0.0
    if not distribution.empty and "exclude_from_guided_search_pct" in distribution:
        exclusion_spread = float(distribution["exclude_from_guided_search_pct"].max() - distribution["exclude_from_guided_search_pct"].min())
    prominence_spread = 0.0
    if not percentiles.empty and "prominence_vs_window_median" in percentiles:
        values = pd.to_numeric(percentiles["prominence_vs_window_median"], errors="coerce").dropna()
        prominence_spread = float(values.max() - values.min()) if not values.empty else 0.0

    if prominence_spread >= 0.10:
        recommendation = "open_group_percentile_normalization_phase"
        reason = "La prominencia por ventana difiere bastante entre grupos; conviene normalizacion por percentiles antes de endurecer umbrales."
    elif exclusion_spread >= 20:
        recommendation = "keep_phase256_with_market_group_reporting"
        reason = "La distribucion de buckets difiere por grupo; mantener reporte estratificado antes de ampliar mas."
    else:
        recommendation = "keep_phase256_with_market_group_reporting"
        reason = "La politica 2.5.6 aguanta descriptivamente, con advertencia de no comparar scores brutos entre mercados."

    return pd.DataFrame(
        [
            {
                "phase258_recommendation": recommendation,
                "policy_decision": "do_not_change_phase256_policy_in_257",
                "exclusion_pct_spread": round(exclusion_spread, 2),
                "prominence_median_spread": round(prominence_spread, 6),
                "risk_rows": int(len(risks)),
                "reason": reason,
                "do_not_do": "no signals, no backtests, no strategy filters, no SVM, no hard EMA/EWO/HTF rules",
            }
        ]
    )


def build_user_review(selection: pd.DataFrame, visual_review: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame(columns=["must_review", "candidate_id", "reason", "chart_path"])
    review = selection.merge(
        visual_review[["candidate_id", "phase257_visual_verdict", "market_group_bias_risk"]],
        on="candidate_id",
        how="left",
    )
    mask = (
        review["selection_reason"].astype(str).isin(["watchlist_low_prominence", "ema_htf_conflict_or_misleading"])
        | review["phase257_visual_verdict"].astype(str).isin(["possibly_too_strict", "possibly_too_lenient", "needs_percentile_normalization"])
        | review["market_group_bias_risk"].astype(str).isin(["high", "unknown"])
    )
    out = review[mask].copy()
    if out.empty:
        return pd.DataFrame(
            [
                {
                    "must_review": False,
                    "candidate_id": "",
                    "reason": "No blocking manual review before 2.5.8 if next phase remains descriptive/non-operational.",
                    "chart_path": "",
                }
            ]
        )
    out["must_review"] = False
    out["reason"] = "Optional review if using this chart as thesis example or changing prominence policy."
    return out[["must_review", "candidate_id", "resolved_market_group", "selection_reason", "reason", "chart_path"]]


def validate_image_refs(tables: dict[str, pd.DataFrame]) -> list[str]:
    missing: set[str] = set()
    for frame in tables.values():
        for column in frame.columns:
            if "path" not in column.lower():
                continue
            for value in frame[column].dropna().astype(str):
                if value.lower().endswith(".png") and not _resolve_repo_path(value).exists():
                    missing.add(value)
    return sorted(missing)


def write_report(output_dir: Path, meta: dict[str, Any]) -> None:
    rec = meta.get("phase258_recommendation", {})
    lines = [
        "# WaveCount Phase 2.5.7 Market-Stratified Expansion",
        "",
        f"Generated at: {meta['generated_at']}",
        "",
        "## Scope",
        "",
        "Expansion descriptiva estratificada por grupo de mercado. No genera senales, no ejecuta backtests y no cambia la politica 2.5.6.",
        "",
        "## Included groups",
        "",
        "- Forex Majors",
        "- Index",
        "- Metals",
        "",
        "SQL also contains Commodities, Crypto and Forex Exotic, but they remain out of scope because WaveCount 2.5.6 has no evidence there.",
        "",
        "## Results",
        "",
        f"- New H4/D1 diagnostic candidates: {meta['new_h4_candidate_rows']}",
        f"- Combined policy rows: {meta['rows'].get('phase257_policy_scores', 0)}",
        f"- Visual gallery rows: {meta['rows'].get('phase257_visual_gallery_selection', 0)}",
        f"- Missing image refs: {len(meta.get('missing_image_refs', []))}",
        "",
        "## Decision",
        "",
        f"- Phase 2.5.8 recommendation: `{rec.get('phase258_recommendation', '')}`",
        f"- Reason: {rec.get('reason', '')}",
        "",
        "## Methodological guardrails",
        "",
        "- Do not compare raw scores across market groups as fully normalized.",
        "- Prominence remains offline/visual-window based and is not live-ready.",
        "- EWO, EMA and HTF remain soft context, not signals or hard filters.",
        "- H4/D1 intermediate remains the primary base; H1/H4 remains auxiliary.",
        "",
        "## Tables",
        "",
    ]
    for name in meta.get("rows", {}):
        lines.append(f"- `tables/{name}.csv`")
    (output_dir / "WAVECOUNT_PHASE2_5_7_MARKET_STRATIFIED_EXPANSION.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def build_market_stratified_expansion(
    *,
    phase256_dir: Path = DEFAULT_PHASE256_DIR,
    phase256b_dir: Path = DEFAULT_PHASE256B_DIR,
    phase252b_dir: Path = DEFAULT_PHASE252B_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: ExpansionConfig = ExpansionConfig(),
) -> dict[str, Any]:
    started = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    scores256 = _read_csv(phase256_dir / "tables" / "phase256_policy_scores.csv")
    scores256_group = _read_csv(phase256b_dir / "tables" / "phase256_scores_with_market_group.csv")
    sql_categories = _read_csv(phase256b_dir / "tables" / "sql_market_categories.csv")
    sql_symbol_tf = _read_csv(phase256b_dir / "tables" / "sql_symbol_timeframe_inventory.csv")
    mapping = _read_csv(phase256b_dir / "tables" / "market_group_mapping_evidence.csv")
    prominence_diagnostics = _read_csv(phase252b_dir / "tables" / "prominence_diagnostics.csv")

    symbol_selection = choose_symbols_by_market_group(
        sql_symbol_tf,
        mapping,
        max_symbols_per_group=config.max_h4_symbols_per_group,
    )
    scope = build_expansion_scope(symbol_selection, sql_categories, config)
    h4_raw, h4_prominence, generation_meta = generate_h4_d1_diagnostic_sample(
        symbol_selection=symbol_selection,
        output_dir=output_dir,
        config=config,
    )
    h4_policy = apply_phase256_policy_to_new_candidates(h4_raw)
    h4_policy = _merge_prominence_values(h4_policy, h4_prominence)
    h4_policy = add_market_group_fields(h4_policy, mapping)
    h4_policy["expansion_origin"] = "new_controlled_h4_d1_by_market_group"
    h4_policy["diagnostic_only"] = True

    existing = prepare_existing_scores(scores256_group if not scores256_group.empty else scores256, prominence_diagnostics)
    combined = pd.concat([h4_policy, existing], ignore_index=True, sort=False) if config.include_existing_phase256 else h4_policy
    combined = combined[combined.get("resolved_market_group", pd.Series(dtype=str)).isin(INCLUDED_GROUPS)].copy()
    combined = _add_missing_columns(
        combined,
        [
            "resolved_market_group",
            "source_scope",
            "symbol",
            "timeframe",
            "htf_timeframe",
            "swing_degree",
            "phase256_policy_bucket",
            "phase256_score",
            "prominence_policy_label",
            "scale_fit_label",
            "ewo_policy_label",
            "ewo_soft_support",
            "ema_htf_policy_label",
            "ema_htf_soft_support",
            "chart_path",
        ],
    )
    policy_scores = build_phase257_policy_scores(combined)

    distribution = build_bucket_distribution_by_group(policy_scores)
    prom_group = build_prominence_percentiles(policy_scores, ["resolved_market_group"])
    prom_symbol = build_prominence_percentiles(policy_scores, ["resolved_market_group", "symbol", "timeframe", "swing_degree"])
    ewo_by_group = build_context_distribution_by_group(
        policy_scores,
        label_columns=["ewo_policy_label", "ewo_soft_support", "ewo_helpfulness"],
        score_column="ewo_score_delta",
    )
    ema_htf_by_group = build_context_distribution_by_group(
        policy_scores,
        label_columns=["ema_htf_policy_label", "ema_htf_soft_support", "ema_htf_helpfulness"],
        score_column="ema_htf_score_delta",
    )
    selection = select_visual_gallery(policy_scores, output_dir)
    visual_review = build_visual_review(selection, distribution, prom_group)
    risks = build_group_bias_risks(distribution, prom_group, sql_categories)
    phase258 = build_phase258_recommendation(distribution, prom_group, risks)
    user_review = build_user_review(selection, visual_review)

    tables = {
        "phase257_expansion_scope": scope,
        "phase257_expanded_candidates": policy_scores,
        "phase257_policy_scores": policy_scores,
        "phase257_bucket_distribution_by_group": distribution,
        "phase257_prominence_percentiles_by_group": prom_group,
        "phase257_prominence_percentiles_by_symbol": prom_symbol,
        "phase257_ewo_by_group": ewo_by_group,
        "phase257_ema_htf_by_group": ema_htf_by_group,
        "phase257_visual_gallery_selection": selection,
        "phase257_visual_review": visual_review,
        "phase257_group_bias_risks": risks,
        "phase258_recommendation": phase258,
        "user_review_if_any": user_review,
    }
    for name, frame in tables.items():
        csv_path = tables_dir / f"{name}.csv"
        _write_csv(frame, csv_path)
        _write_markdown_index(csv_path, name.replace("_", " ").title())

    missing_refs = validate_image_refs(tables)
    rec = phase258.iloc[0].to_dict() if not phase258.empty else {}
    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase256_dir": _rel_to_repo(phase256_dir),
            "phase256b_dir": _rel_to_repo(phase256b_dir),
            "phase252b_dir": _rel_to_repo(phase252b_dir),
        },
        "config": {
            "max_h4_symbols_per_group": config.max_h4_symbols_per_group,
            "h4_ltf_rows": config.h4_ltf_rows,
            "htf_rows": config.htf_rows,
            "include_existing_phase256": config.include_existing_phase256,
        },
        "generation_meta": generation_meta,
        "new_h4_candidate_rows": int(len(h4_policy)),
        "existing_phase256_rows": int(len(existing)),
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        "included_groups": list(INCLUDED_GROUPS),
        "excluded_sql_groups": list(EXCLUDED_SQL_GROUPS),
        "phase258_recommendation": rec,
        "missing_image_refs": missing_refs,
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_backtests_executed": True,
        "no_base_rules_changed": True,
        "no_previous_counts_recalculated": True,
        "phase256_policy_changed": False,
        "elapsed_seconds": round(perf_counter() - started, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(output_dir, run_meta)
    return run_meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.7 market-stratified expansion.")
    parser.add_argument("--phase256-dir", type=Path, default=DEFAULT_PHASE256_DIR)
    parser.add_argument("--phase256b-dir", type=Path, default=DEFAULT_PHASE256B_DIR)
    parser.add_argument("--phase252b-dir", type=Path, default=DEFAULT_PHASE252B_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-h4-symbols-per-group", type=int, default=6)
    parser.add_argument("--h4-ltf-rows", type=int, default=1100)
    parser.add_argument("--htf-rows", type=int, default=520)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_market_stratified_expansion(
        phase256_dir=args.phase256_dir,
        phase256b_dir=args.phase256b_dir,
        phase252b_dir=args.phase252b_dir,
        output_dir=args.output_dir,
        config=ExpansionConfig(
            max_h4_symbols_per_group=args.max_h4_symbols_per_group,
            h4_ltf_rows=args.h4_ltf_rows,
            htf_rows=args.htf_rows,
        ),
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
