from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from data.sql.sql_funcs import close_db, connect_db


REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDED_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "05_guided_profile"
DEFAULT_PHASE256_DIR = GUIDED_ROOT / "phase2_5_6_soft_policy_weight_adjustment_2026-05-24"
DEFAULT_PHASE254_DIR = GUIDED_ROOT / "phase2_5_4_soft_quality_policy_2026-05-24"
DEFAULT_OUTPUT_DIR = GUIDED_ROOT / "phase2_5_6b_market_group_bias_audit_2026-05-24"

SQL_TABLES_OF_INTEREST = ("price_data", "symbol_control", "symbol_metadata")
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
    for index, row in frame.iterrows():
        label = (
            _string(row.get("candidate_id"))
            or _string(row.get("symbol"))
            or _string(row.get("resolved_market_group"))
            or f"fila {index + 1}"
        )
        lines.append(f"## {index + 1}. {label}")
        for column in (
            "resolved_market_group",
            "phase256_policy_bucket",
            "selection_reason",
            "market_group_visual_verdict",
            "market_group_bias_risk",
            "policy_recommendation",
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


def _fetch_df(connection: Any, query: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description] if cursor.description else []
    finally:
        cursor.close()
    return pd.DataFrame(rows, columns=columns)


def _show_columns(connection: Any, table: str) -> list[str]:
    frame = _fetch_df(connection, f"SHOW COLUMNS FROM {table}")
    if frame.empty:
        return []
    return frame.iloc[:, 0].astype(str).tolist()


def _count_rows(connection: Any, table: str) -> int | None:
    frame = _fetch_df(connection, f"SELECT COUNT(*) AS row_count FROM {table}")
    if frame.empty:
        return None
    return int(frame.iloc[0]["row_count"])


def find_local_sqlite_files() -> pd.DataFrame:
    rows = []
    for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
        for path in REPO_ROOT.rglob(pattern):
            rows.append(
                {
                    "source_type": "local_sqlite_candidate",
                    "table_name": "",
                    "path": _rel_to_repo(path),
                    "row_count": "",
                    "columns": "",
                    "has_group_column": False,
                    "notes": "Local sqlite-like file found; WaveCount SQL loaders use MySQL price_data/symbol_control.",
                }
            )
    if not rows:
        rows.append(
            {
                "source_type": "local_sqlite_candidate",
                "table_name": "",
                "path": "",
                "row_count": "",
                "columns": "",
                "has_group_column": False,
                "notes": "No .db/.sqlite/.sqlite3 files found inside repo.",
            }
        )
    return pd.DataFrame(rows)


def load_sql_inventory() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    local_files = find_local_sqlite_files()
    connection = connect_db()
    if connection is None:
        data_inventory = pd.concat(
            [
                local_files,
                pd.DataFrame(
                    [
                        {
                            "source_type": "mysql",
                            "table_name": "",
                            "path": "",
                            "row_count": "",
                            "columns": "",
                            "has_group_column": False,
                            "notes": "MySQL connection unavailable; mapping must rely on repo/artifact evidence.",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        empty_symbol_tf = pd.DataFrame(
            columns=["symbol", "timeframe", "rows_count", "first_time", "last_time", "sql_market_group", "enabled"]
        )
        empty_categories = pd.DataFrame(
            columns=["sql_market_group", "enabled_symbols", "price_symbols_with_data", "artifact_symbols", "candidate_rows"]
        )
        empty_control = pd.DataFrame(columns=["symbol", "sql_market_group", "enabled", "last_update"])
        return data_inventory, empty_symbol_tf, empty_categories, empty_control

    try:
        tables = _fetch_df(connection, "SHOW TABLES")
        table_names = tables.iloc[:, 0].astype(str).tolist() if not tables.empty else []
        inventory_rows = []
        for table in table_names:
            columns = _show_columns(connection, table)
            row_count = _count_rows(connection, table) if table in SQL_TABLES_OF_INTEREST else ""
            inventory_rows.append(
                {
                    "source_type": "mysql",
                    "table_name": table,
                    "path": "trading_data",
                    "row_count": row_count,
                    "columns": ", ".join(columns),
                    "has_group_column": "group" in columns,
                    "notes": "Real MySQL table inspected by 2.5.6b.",
                }
            )
        data_inventory = pd.concat([local_files, pd.DataFrame(inventory_rows)], ignore_index=True)

        symbol_control = _fetch_df(
            connection,
            "SELECT symbol, `group` AS sql_market_group, enabled, last_update FROM symbol_control ORDER BY `group`, symbol",
        )
        if symbol_control.empty:
            symbol_control = pd.DataFrame(columns=["symbol", "sql_market_group", "enabled", "last_update"])

        symbol_tf = _fetch_df(
            connection,
            """
            SELECT pd.symbol, pd.timeframe, COUNT(*) AS rows_count, MIN(pd.time) AS first_time, MAX(pd.time) AS last_time,
                   sc.`group` AS sql_market_group, sc.enabled
            FROM price_data pd
            LEFT JOIN symbol_control sc ON sc.symbol = pd.symbol
            GROUP BY pd.symbol, pd.timeframe, sc.`group`, sc.enabled
            ORDER BY pd.symbol, pd.timeframe
            """,
        )
        if symbol_tf.empty:
            symbol_tf = pd.DataFrame(
                columns=["symbol", "timeframe", "rows_count", "first_time", "last_time", "sql_market_group", "enabled"]
            )

        categories = (
            symbol_control.groupby("sql_market_group", dropna=False)
            .agg(enabled_symbols=("symbol", lambda s: int(symbol_control.loc[s.index, "enabled"].astype(bool).sum())))
            .reset_index()
        )
        data_by_group = (
            symbol_tf.groupby("sql_market_group", dropna=False)["symbol"]
            .nunique()
            .reset_index(name="price_symbols_with_data")
        )
        categories = categories.merge(data_by_group, on="sql_market_group", how="left")
        categories["price_symbols_with_data"] = categories["price_symbols_with_data"].fillna(0).astype(int)
        categories["artifact_symbols"] = 0
        categories["candidate_rows"] = 0
        return data_inventory, symbol_tf, categories, symbol_control
    finally:
        close_db(connection)


def build_market_group_mapping(scores: pd.DataFrame, symbol_control: pd.DataFrame, symbol_tf: pd.DataFrame) -> pd.DataFrame:
    artifact_groups = {}
    artifact_prefixes = {}
    if not scores.empty and "symbol" in scores:
        for symbol, part in scores.groupby("symbol", dropna=False):
            groups = sorted({_string(value) for value in part.get("group", pd.Series(dtype=str)).dropna() if _string(value)})
            prefixes = sorted(
                {
                    _string(cid).split("_")[2]
                    for cid in part.get("candidate_id", pd.Series(dtype=str)).dropna()
                    if len(_string(cid).split("_")) > 2
                }
            )
            artifact_groups[_string(symbol)] = ", ".join(groups)
            artifact_prefixes[_string(symbol)] = ", ".join(prefixes)

    sql_groups = {}
    enabled_map = {}
    if not symbol_control.empty:
        for _, row in symbol_control.iterrows():
            sql_groups[_string(row.get("symbol"))] = _string(row.get("sql_market_group"))
            enabled_map[_string(row.get("symbol"))] = _string(row.get("enabled"))

    price_symbols = set(symbol_tf.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist())
    symbols = sorted(set(artifact_groups) | set(sql_groups) | price_symbols)
    rows = []
    for symbol in symbols:
        sql_group = sql_groups.get(symbol, "")
        artifact_group = artifact_groups.get(symbol, "")
        prefixes = artifact_prefixes.get(symbol, "")
        if sql_group:
            resolved = sql_group
            confidence = "sql_explicit"
            source = "symbol_control.group"
        elif artifact_group:
            resolved = artifact_group.split(", ")[0]
            confidence = "artifact_prefix"
            source = "artifact_group_or_candidate_prefix"
        else:
            resolved = "unknown_market_group"
            confidence = "unknown"
            source = "unknown"
        mismatch = bool(sql_group and artifact_group and sql_group != artifact_group)
        rows.append(
            {
                "symbol": symbol,
                "sql_market_group": sql_group,
                "artifact_market_group": artifact_group,
                "resolved_market_group": resolved,
                "mapping_confidence": confidence,
                "category_source": source,
                "symbol_in_sql": symbol in sql_groups or symbol in price_symbols,
                "symbol_enabled": enabled_map.get(symbol, ""),
                "artifact_candidate_prefixes": prefixes,
                "evidence": f"sql_group={sql_group or 'none'}; artifact_group={artifact_group or 'none'}; prefixes={prefixes or 'none'}",
                "notes": "SQL and artifact group differ; SQL kept as source of truth." if mismatch else "",
            }
        )
    return pd.DataFrame(rows)


def join_scores_with_market_group(scores: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
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
        "notes",
    ]
    merged = scores.merge(mapping[fields], on="symbol", how="left")
    merged["resolved_market_group"] = merged["resolved_market_group"].fillna("unknown_market_group")
    merged["mapping_confidence"] = merged["mapping_confidence"].fillna("unknown")
    merged["category_notes"] = merged["notes"].fillna("")
    return merged.drop(columns=["notes"])


def build_bucket_distribution(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if scores.empty:
        return pd.DataFrame()
    total_all = len(scores)
    for group, part in scores.groupby("resolved_market_group", dropna=False):
        row: dict[str, Any] = {
            "resolved_market_group": _string(group),
            "case_count": int(len(part)),
            "case_share_pct": round(len(part) / total_all * 100, 2) if total_all else 0.0,
            "h4_d1_count": int((part.get("source_scope", "") == "h4_d1").sum()),
            "h1_h4_count": int((part.get("source_scope", "") == "h1_h4").sum()),
        }
        for bucket in PHASE256_BUCKETS:
            count = int((part.get("phase256_policy_bucket", "") == bucket).sum())
            row[bucket] = count
            row[f"{bucket}_pct"] = round(count / len(part) * 100, 2) if len(part) else 0.0
        row["low_prominence_rows"] = int(
            part.get("prominence_policy_label", pd.Series(dtype=str)).isin(
                ["low_prominence_vs_window", "better_as_lower_tf_substructure"]
            ).sum()
        )
        row["low_prominence_pct"] = round(row["low_prominence_rows"] / len(part) * 100, 2) if len(part) else 0.0
        for degree in ("minor", "intermediate", "major"):
            row[f"{degree}_count"] = int((part.get("swing_degree", "") == degree).sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("resolved_market_group").reset_index(drop=True)


def _series_stats(part: pd.DataFrame, column: str) -> dict[str, Any]:
    values = pd.to_numeric(part.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    if values.empty:
        return {
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
        f"{column}_mean": round(float(values.mean()), 6),
        f"{column}_median": round(float(values.median()), 6),
        f"{column}_p10": round(float(values.quantile(0.10)), 6),
        f"{column}_p25": round(float(values.quantile(0.25)), 6),
        f"{column}_p75": round(float(values.quantile(0.75)), 6),
        f"{column}_p90": round(float(values.quantile(0.90)), 6),
        f"{column}_min": round(float(values.min()), 6),
        f"{column}_max": round(float(values.max()), 6),
    }


def build_prominence_by_market_group(scores: pd.DataFrame, prominence: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    numeric_cols = [
        "prominence_vs_window",
        "duration_vs_window",
        "relative_structure_size",
        "scale_fit_label",
        "prominence_policy_label",
        "phase256_prominence_action",
    ]
    base_cols = ["candidate_id", *[col for col in numeric_cols if col in prominence.columns]]
    merged = scores.merge(prominence[base_cols], on="candidate_id", how="left", suffixes=("", "_num"))
    for col in ("scale_fit_label", "prominence_policy_label"):
        alt = f"{col}_num"
        if alt in merged:
            merged[col] = merged[col].where(merged[col].astype(str).ne("") & merged[col].notna(), merged[alt])
    rows = []
    for group, part in merged.groupby("resolved_market_group", dropna=False):
        row: dict[str, Any] = {"resolved_market_group": _string(group), "case_count": int(len(part))}
        for column in ("prominence_vs_window", "duration_vs_window"):
            row.update(_series_stats(part, column))
        row["too_small_for_timeframe_count"] = int((part.get("scale_fit_label", "") == "too_small_for_timeframe").sum())
        row["low_prominence_vs_window_count"] = int(
            (part.get("prominence_policy_label", "") == "low_prominence_vs_window").sum()
        )
        row["better_as_lower_tf_substructure_count"] = int(
            (part.get("scale_fit_label", "") == "better_as_lower_tf_substructure").sum()
        )
        row["should_downgrade_to_auxiliary_count"] = int(
            part.get("should_downgrade_to_auxiliary", pd.Series(dtype=bool)).map(_boolish).sum()
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("resolved_market_group").reset_index(drop=True)


def build_label_distribution(
    scores: pd.DataFrame,
    *,
    label_columns: tuple[str, ...],
    score_column: str,
    output_prefix: str,
) -> pd.DataFrame:
    rows = []
    if scores.empty:
        return pd.DataFrame()
    for group, part in scores.groupby("resolved_market_group", dropna=False):
        row: dict[str, Any] = {
            "resolved_market_group": _string(group),
            "case_count": int(len(part)),
            f"{output_prefix}_score_mean": round(float(pd.to_numeric(part.get(score_column, 0), errors="coerce").fillna(0).mean()), 4)
            if score_column in part
            else "",
        }
        for column in label_columns:
            if column not in part:
                continue
            for label, count in part[column].fillna("").astype(str).value_counts().items():
                safe_label = label or "blank"
                row[f"{column}_{safe_label}"] = int(count)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("resolved_market_group").reset_index(drop=True)


def _copy_chart(row: pd.Series, output_dir: Path, index: int) -> str:
    value = _string(row.get("chart_path"))
    if not value:
        return ""
    src = _resolve_repo_path(value)
    if not src.exists():
        return value
    group = _string(row.get("resolved_market_group")).replace(" ", "_").lower() or "unknown"
    dest_dir = output_dir / "charts" / "selected_by_market_group"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{index:03d}_{group}_{src.name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return _rel_to_repo(dest)


def build_visual_selection(scores: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    selected: list[pd.Series] = []
    reasons: list[str] = []

    def add(part: pd.DataFrame, reason: str, ascending: bool = False) -> None:
        if part.empty:
            return
        ordered = part.sort_values("phase256_score", ascending=ascending) if "phase256_score" in part else part
        row = ordered.iloc[0]
        if _string(row.get("candidate_id")) in {_string(item.get("candidate_id")) for item in selected}:
            return
        selected.append(row)
        reasons.append(reason)

    for group, part in scores.groupby("resolved_market_group", dropna=False):
        add(part[part["phase256_policy_bucket"] == "high_quality_structure"], "best_high_quality")
        add(part[part["phase256_policy_bucket"] == "usable_provisional_structure"], "usable_or_provisional")
        add(part[part["phase256_policy_bucket"] == "visual_watchlist_low_prominence"], "watchlist_low_prominence")
        add(
            part[
                part["prominence_policy_label"].isin(
                    ["low_prominence_vs_window", "better_as_lower_tf_substructure"]
                )
            ],
            "low_prominence_representative",
        )
        add(part[part["phase256_policy_bucket"] == "exclude_from_guided_search"], "excluded_highest_score")
        add(part[part.get("ewo_soft_support", pd.Series(dtype=str)).astype(str).eq("supports")], "ewo_support_representative")
        add(
            part[
                part.get("ema_htf_policy_label", pd.Series(dtype=str))
                .fillna("")
                .astype(str)
                .str.contains("misleading|conflict", case=False, regex=True)
            ],
            "ema_htf_conflict_or_misleading",
        )

    rows = []
    for idx, (row, reason) in enumerate(zip(selected, reasons), start=1):
        copied = _copy_chart(row, output_dir, idx)
        rows.append(
            {
                "selection_order": idx,
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": _string(row.get("resolved_market_group")),
                "symbol": _string(row.get("symbol")),
                "timeframe": _string(row.get("timeframe")),
                "swing_degree": _string(row.get("swing_degree")),
                "source_scope": _string(row.get("source_scope")),
                "phase256_policy_bucket": _string(row.get("phase256_policy_bucket")),
                "phase256_score": _number(row.get("phase256_score")),
                "selection_reason": reason,
                "chart_path": copied or _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_visual_review(selection: pd.DataFrame, distribution: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame()
    distribution_map = distribution.set_index("resolved_market_group").to_dict("index") if not distribution.empty else {}
    rows = []
    for _, row in selection.iterrows():
        group = _string(row.get("resolved_market_group"))
        dist = distribution_map.get(group, {})
        case_count = int(_number(dist.get("case_count"), 0))
        exclusion_pct = _number(dist.get("exclude_from_guided_search_pct"), 0)
        low_prom_pct = _number(dist.get("low_prominence_pct"), 0)
        bucket = _string(row.get("phase256_policy_bucket"))
        reason = _string(row.get("selection_reason"))
        if case_count < 10:
            verdict = "not_enough_cases"
            risk = "unknown"
        elif low_prom_pct >= 35:
            verdict = "group_needs_separate_normalization"
            risk = "medium"
        elif exclusion_pct >= 90 and bucket != "exclude_from_guided_search":
            verdict = "possibly_too_lenient_for_group"
            risk = "medium"
        else:
            verdict = "policy_consistent_for_group"
            risk = "low"
        if bucket == "visual_watchlist_low_prominence":
            verdict = "policy_consistent_for_group"
            risk = "medium"
        rows.append(
            {
                "candidate_id": _string(row.get("candidate_id")),
                "resolved_market_group": group,
                "selection_reason": reason,
                "phase256_policy_bucket": bucket,
                "market_group_visual_verdict": verdict,
                "market_group_bias_risk": risk,
                "visual_review_basis": "Selected chart copied for visual audit; verdict combines 2.5.6b market stats and 2.5.5/2.5.6 policy evidence.",
                "notes": "Review before changing weights; do not compare raw scores across market groups as if fully normalized.",
                "chart_path": _string(row.get("chart_path")),
            }
        )
    return pd.DataFrame(rows)


def build_bias_risks(distribution: pd.DataFrame, prominence: pd.DataFrame, sql_categories: pd.DataFrame) -> pd.DataFrame:
    rows = []
    category_groups = set(sql_categories.get("sql_market_group", pd.Series(dtype=str)).dropna().astype(str))
    represented = set(distribution.get("resolved_market_group", pd.Series(dtype=str)).dropna().astype(str))
    unrepresented = sorted(group for group in category_groups if group and group not in represented)
    if unrepresented:
        rows.append(
            {
                "risk": "sql_groups_not_represented_in_wavecount_candidates",
                "where_seen": ", ".join(unrepresented),
                "impact": "WaveCount 2.5.6 evidence only covers a subset of available SQL market groups.",
                "market_group_bias_risk": "medium",
                "mitigation": "Do not generalize 2.5.6 policy to unrepresented groups without separate audit.",
            }
        )
    if not distribution.empty and "exclude_from_guided_search_pct" in distribution:
        spread = float(distribution["exclude_from_guided_search_pct"].max() - distribution["exclude_from_guided_search_pct"].min())
        rows.append(
            {
                "risk": "bucket_distribution_differs_by_market_group",
                "where_seen": "phase256_policy_bucket by resolved_market_group",
                "impact": f"Exclusion percentage spread across represented groups is {spread:.2f} percentage points.",
                "market_group_bias_risk": "medium" if spread >= 20 else "low",
                "mitigation": "Keep group-stratified reporting in 2.5.7; avoid treating score distribution as fully cross-market normalized.",
            }
        )
    if not prominence.empty and "prominence_vs_window_median" in prominence:
        values = pd.to_numeric(prominence["prominence_vs_window_median"], errors="coerce").dropna()
        if not values.empty:
            spread = float(values.max() - values.min())
            rows.append(
                {
                    "risk": "prominence_distribution_differs_by_market_group",
                    "where_seen": "prominence_vs_window median by group",
                    "impact": f"Median prominence spread across represented groups is {spread:.4f}.",
                    "market_group_bias_risk": "medium" if spread >= 0.10 else "low",
                    "mitigation": "Consider future group/symbol-timeframe percentile diagnostics before hardening thresholds.",
                }
            )
    return pd.DataFrame(rows)


def build_policy_recommendation(
    distribution: pd.DataFrame,
    prominence: pd.DataFrame,
    sql_categories: pd.DataFrame,
) -> pd.DataFrame:
    represented = set(distribution.get("resolved_market_group", pd.Series(dtype=str)).dropna().astype(str))
    sql_groups = set(sql_categories.get("sql_market_group", pd.Series(dtype=str)).dropna().astype(str))
    unrepresented = sorted(group for group in sql_groups if group and group not in represented)
    exclusion_spread = 0.0
    if not distribution.empty and "exclude_from_guided_search_pct" in distribution:
        exclusion_spread = float(distribution["exclude_from_guided_search_pct"].max() - distribution["exclude_from_guided_search_pct"].min())
    if unrepresented or exclusion_spread >= 20:
        policy = "keep_global_policy_with_group_warning"
        next_step = "2.5.7 can advance only with market-group stratified reporting; do not compare raw scores across groups as fully normalized."
        percentile = "use_group_percentile_diagnostics"
    else:
        policy = "keep_global_policy"
        next_step = "2.5.7 can advance with current policy and continue monitoring group distributions."
        percentile = "not_required_now"
    return pd.DataFrame(
        [
            {
                "policy_recommendation": policy,
                "percentile_recommendation": percentile,
                "can_phase257_advance": True,
                "must_normalize_before_phase257": False,
                "sql_groups_available": ", ".join(sorted(sql_groups)),
                "wavecount_groups_represented": ", ".join(sorted(represented)),
                "sql_groups_not_represented": ", ".join(unrepresented),
                "exclusion_pct_spread": round(exclusion_spread, 2),
                "notes": next_step,
            }
        ]
    )


def update_sql_category_counts(
    sql_categories: pd.DataFrame,
    mapping: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    if sql_categories.empty:
        return sql_categories
    artifact_symbols = (
        mapping[mapping["artifact_market_group"].astype(str).ne("")]
        .groupby("resolved_market_group")["symbol"]
        .nunique()
        .reset_index(name="artifact_symbols")
    )
    candidate_rows = scores.groupby("resolved_market_group").size().reset_index(name="candidate_rows") if not scores.empty else pd.DataFrame(columns=["resolved_market_group", "candidate_rows"])
    out = sql_categories.merge(
        artifact_symbols,
        left_on="sql_market_group",
        right_on="resolved_market_group",
        how="left",
        suffixes=("", "_calc"),
    )
    out["artifact_symbols"] = out["artifact_symbols_calc"].fillna(out.get("artifact_symbols", 0)).fillna(0).astype(int)
    out = out.drop(columns=[col for col in ("resolved_market_group", "artifact_symbols_calc") if col in out], errors="ignore")
    out = out.merge(candidate_rows, left_on="sql_market_group", right_on="resolved_market_group", how="left", suffixes=("", "_calc"))
    out["candidate_rows"] = out["candidate_rows_calc"].fillna(out.get("candidate_rows", 0)).fillna(0).astype(int)
    return out.drop(columns=[col for col in ("resolved_market_group", "candidate_rows_calc") if col in out], errors="ignore")


def build_report(
    output_dir: Path,
    *,
    sql_categories: pd.DataFrame,
    distribution: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> str:
    categories = ", ".join(sql_categories.get("sql_market_group", pd.Series(dtype=str)).dropna().astype(str).tolist())
    represented = ", ".join(distribution.get("resolved_market_group", pd.Series(dtype=str)).dropna().astype(str).tolist())
    rec = recommendation.iloc[0].to_dict() if not recommendation.empty else {}
    lines = [
        "# WaveCount Phase 2.5.6b Market Group Bias Audit",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "Auditoria conservadora de sesgo por grupo de mercado sobre la politica 2.5.6.",
        "No genera senales, no ejecuta backtests y no cambia pivotes, conteos ni estrategias.",
        "",
        "## SQL categories",
        "",
        f"- SQL groups found: {categories or 'none'}",
        f"- WaveCount represented groups: {represented or 'none'}",
        "",
        "## Decision",
        "",
        f"- Policy recommendation: `{rec.get('policy_recommendation', '')}`",
        f"- Percentile recommendation: `{rec.get('percentile_recommendation', '')}`",
        f"- Can Phase 2.5.7 advance: `{rec.get('can_phase257_advance', '')}`",
        f"- Must normalize before 2.5.7: `{rec.get('must_normalize_before_phase257', '')}`",
        "",
        "## Tables",
        "",
        "- `tables/sql_data_inventory.csv`",
        "- `tables/sql_symbol_timeframe_inventory.csv`",
        "- `tables/sql_market_categories.csv`",
        "- `tables/market_group_mapping_evidence.csv`",
        "- `tables/phase256_scores_with_market_group.csv`",
        "- `tables/bucket_distribution_by_market_group.csv`",
        "- `tables/prominence_by_market_group.csv`",
        "- `tables/ewo_by_market_group.csv`",
        "- `tables/ema_htf_by_market_group.csv`",
        "- `tables/market_group_visual_selection.csv`",
        "- `tables/market_group_visual_review.csv`",
        "- `tables/market_group_bias_risks.csv`",
        "- `tables/market_group_policy_recommendation.csv`",
    ]
    path = output_dir / "WAVECOUNT_PHASE2_5_6B_MARKET_GROUP_BIAS_AUDIT.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return _rel_to_repo(path)


def build_market_group_bias_audit(
    *,
    phase256_dir: Path = DEFAULT_PHASE256_DIR,
    phase254_dir: Path = DEFAULT_PHASE254_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started = perf_counter()
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    scores = _read_csv(phase256_dir / "tables" / "phase256_policy_scores.csv")
    prominence = _read_csv(phase254_dir / "tables" / "prominence_soft_policy.csv")
    data_inventory, symbol_tf, sql_categories, symbol_control = load_sql_inventory()
    mapping = build_market_group_mapping(scores, symbol_control, symbol_tf)
    scores_with_group = join_scores_with_market_group(scores, mapping)
    sql_categories = update_sql_category_counts(sql_categories, mapping, scores_with_group)

    distribution = build_bucket_distribution(scores_with_group)
    prominence_by_group = build_prominence_by_market_group(scores_with_group, prominence)
    ewo_by_group = build_label_distribution(
        scores_with_group,
        label_columns=("ewo_policy_label", "ewo_soft_support", "ewo_helpfulness"),
        score_column="ewo_score_delta",
        output_prefix="ewo",
    )
    ema_htf_by_group = build_label_distribution(
        scores_with_group,
        label_columns=("ema_htf_policy_label", "ema_htf_soft_support", "ema_htf_helpfulness"),
        score_column="ema_htf_score_delta",
        output_prefix="ema_htf",
    )
    selection = build_visual_selection(scores_with_group, output_dir)
    visual_review = build_visual_review(selection, distribution)
    risks = build_bias_risks(distribution, prominence_by_group, sql_categories)
    recommendation = build_policy_recommendation(distribution, prominence_by_group, sql_categories)
    user_review = pd.DataFrame(
        [
            {
                "must_review": False,
                "reason": "No blocking manual review required before 2.5.7 if reporting stays stratified by market group.",
                "recommended_user_action": "Optional review of selected market-group contact cases if changing weights later.",
            }
        ]
    )

    outputs = {
        "sql_data_inventory": data_inventory,
        "sql_symbol_timeframe_inventory": symbol_tf,
        "sql_market_categories": sql_categories,
        "market_group_mapping_evidence": mapping,
        "phase256_scores_with_market_group": scores_with_group,
        "bucket_distribution_by_market_group": distribution,
        "prominence_by_market_group": prominence_by_group,
        "ewo_by_market_group": ewo_by_group,
        "ema_htf_by_market_group": ema_htf_by_group,
        "market_group_visual_selection": selection,
        "market_group_visual_review": visual_review,
        "market_group_bias_risks": risks,
        "market_group_policy_recommendation": recommendation,
        "user_review_if_any": user_review,
    }
    for name, frame in outputs.items():
        csv_path = tables_dir / f"{name}.csv"
        _write_csv(frame, csv_path)
        _write_markdown_index(csv_path, name.replace("_", " ").title())

    report_path = build_report(
        output_dir,
        sql_categories=sql_categories,
        distribution=distribution,
        recommendation=recommendation,
    )
    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel_to_repo(Path(__file__)),
        "output_dir": _rel_to_repo(output_dir),
        "inputs": {
            "phase256_dir": _rel_to_repo(phase256_dir),
            "phase254_dir": _rel_to_repo(phase254_dir),
            "scores_rows": int(len(scores)),
            "sql_symbols": int(symbol_control["symbol"].nunique()) if not symbol_control.empty else 0,
            "sql_symbol_timeframe_rows": int(len(symbol_tf)),
            "sql_categories": sorted(sql_categories.get("sql_market_group", pd.Series(dtype=str)).dropna().astype(str).tolist()),
        },
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "report_path": report_path,
        "no_strategy_changes": True,
        "no_signals_generated": True,
        "no_backtests_executed": True,
        "no_base_rules_changed": True,
        "no_pivots_recalculated": True,
        "no_counts_recalculated": True,
        "elapsed_seconds": round(perf_counter() - started, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")
    return run_meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.5.6b market-group bias audit.")
    parser.add_argument("--phase256-dir", type=Path, default=DEFAULT_PHASE256_DIR)
    parser.add_argument("--phase254-dir", type=Path, default=DEFAULT_PHASE254_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    meta = build_market_group_bias_audit(
        phase256_dir=args.phase256_dir,
        phase254_dir=args.phase254_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
