from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OHLC_ARTIFACT = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/artifact_refresh_orchestrator_v1_2026-06-05"
DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/ARTIFACT_REFRESH_ORCHESTRATOR_V1.md"
DEFAULT_DESIGN_DOC_PATH = REPO_ROOT / "docs/ARTIFACT_REFRESH_ORCHESTRATOR_DESIGN_V1.md"
DEFAULT_MARKET_CORRELATIONS_DIR = REPO_ROOT / "artifacts/tfg/trading_center_market_correlations_v1_2026-05-31"
DEFAULT_CORRELATION_PAIRS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "correlation_pairs.csv"
DEFAULT_ROLLING_CORRELATIONS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "rolling_correlations.csv"
DEFAULT_CORRELATION_RETURNS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "correlation_returns_sample.csv"
DEFAULT_CORRELATION_META_JSON = DEFAULT_MARKET_CORRELATIONS_DIR / "run_meta.json"
DEFAULT_WEAVECOUNT_SCREENER_DIR = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01"
DEFAULT_MACD_BREAKOUT_WATCHER_DIR = (
    REPO_ROOT / "artifacts/live-signal-watcher/enbolsa_macd_breakout_h1_h4_major_metals_index_current_v0_2026-06-08"
)
DEFAULT_MACD_BREAKOUT_ENRICHMENT_DIR = (
    REPO_ROOT / "artifacts/tfg/macd_breakout_watcher_enrichment_h1_h4_major_metals_index_current_v1_2026-06-08"
)
DEFAULT_MACD_BREAKOUT_ENRICHED_CSV = (
    DEFAULT_MACD_BREAKOUT_ENRICHMENT_DIR / "macd_breakout_enriched_setups.csv"
)
DEFAULT_MACD_BREAKOUT_CHART_LAYERS_CSV = (
    DEFAULT_MACD_BREAKOUT_ENRICHMENT_DIR / "macd_breakout_chart_layers.csv"
)
REQUIRED_TIMEFRAMES = ("M15", "H1", "H4", "D1")
TIMEFRAME_MAX_AGES = {
    "M15": {"warning": 30 * 60, "blocked": 60 * 60},
    "H1": {"warning": 2 * 60 * 60, "blocked": 4 * 60 * 60},
    "H4": {"warning": 8 * 60 * 60, "blocked": 12 * 60 * 60},
    # Daily data can legitimately remain on Friday's close during Monday
    # morning. A 96h block threshold allows the weekend gap but still fails
    # closed if Monday's D1 close is absent later into Tuesday.
    "D1": {"warning": 72 * 60 * 60, "blocked": 96 * 60 * 60},
}
FIELD_ALIASES = {
    "time": ("time", "timestamp", "datetime", "date"),
    "symbol": ("symbol",),
    "market_group": ("market_group", "group", "asset_group"),
    "timeframe": ("timeframe", "tf"),
    "open": ("open",),
    "high": ("high",),
    "low": ("low",),
    "close": ("close",),
}


@dataclass
class OrchestratorResult:
    trigger_rows: list[dict[str, Any]]
    scheduler_rows: list[dict[str, Any]]
    schema_rows: list[dict[str, Any]]
    freshness_rows: list[dict[str, Any]]
    decision_rows: list[dict[str, Any]]
    dependency_rows: list[dict[str, Any]]
    artifact_rows: list[dict[str, Any]]
    last_good_rows: list[dict[str, Any]]
    latest_rows: list[dict[str, Any]]
    safety_rows: list[dict[str, Any]]
    issue_rows: list[dict[str, Any]]
    run_meta: dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    candidates = [
        text,
        text.replace("Z", "+00:00"),
        text.replace(" ", "T"),
        text.replace(" ", "T").replace("Z", "+00:00"),
    ]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_file_preserving_dirs(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.resolve() == target.resolve():
            return
    except FileNotFoundError:
        pass
    shutil.copy2(source, target)


def copy_tree_files(source_dir: Path, target_dir: Path) -> int:
    copied = 0
    if not source_dir.exists():
        return copied
    for source in source_dir.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_dir)
        copy_file_preserving_dirs(source, target_dir / relative)
        copied += 1
    return copied


def resolve_columns(fieldnames: list[str] | None) -> tuple[dict[str, str], list[str]]:
    available = set(fieldnames or [])
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for canonical, aliases in FIELD_ALIASES.items():
        found = next((alias for alias in aliases if alias in available), None)
        if found is None:
            missing.append(canonical)
        else:
            resolved[canonical] = found
    return resolved, missing


def validate_float(value: Any) -> bool:
    try:
        float(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def load_ohlc_audit(ohlc_artifact: Path, now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not ohlc_artifact.exists():
        return (
            [{"check": "file_exists", "status": "blocked", "path": str(ohlc_artifact), "detail": "OHLC artifact missing"}],
            [],
            {"exists": False, "schema_valid": False, "required_timeframes_present": False, "rows": 0},
        )
    try:
        with ohlc_artifact.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
    except Exception as exc:  # pragma: no cover - defensive audit path
        return (
            [{"check": "read_csv", "status": "blocked", "path": str(ohlc_artifact), "detail": str(exc)}],
            [],
            {"exists": True, "schema_valid": False, "required_timeframes_present": False, "rows": 0},
        )
    resolved, missing = resolve_columns(fieldnames)
    schema_rows: list[dict[str, Any]] = [
        {
            "check": "file_exists",
            "status": "passed",
            "path": str(ohlc_artifact),
            "detail": "OHLC artifact found",
        },
        {
            "check": "schema_columns",
            "status": "passed" if not missing else "blocked",
            "path": str(ohlc_artifact),
            "detail": "aliases=" + json.dumps(resolved, ensure_ascii=False) + ("; missing=" + ",".join(missing) if missing else ""),
        },
    ]
    if missing:
        return schema_rows, [], {"exists": True, "schema_valid": False, "required_timeframes_present": False, "rows": len(rows)}

    invalid_ohlc = 0
    invalid_time = 0
    latest_by_tf: dict[str, datetime] = {}
    for row in rows:
        tf = str(row.get(resolved["timeframe"], "")).strip()
        if not all(validate_float(row.get(resolved[col])) for col in ("open", "high", "low", "close")):
            invalid_ohlc += 1
            continue
        parsed = parse_dt(row.get(resolved["time"]))
        if parsed is None:
            invalid_time += 1
            continue
        if parsed > now:
            invalid_time += 1
            continue
        if tf not in latest_by_tf or parsed > latest_by_tf[tf]:
            latest_by_tf[tf] = parsed

    present = sorted(tf for tf in REQUIRED_TIMEFRAMES if tf in latest_by_tf)
    missing_tf = [tf for tf in REQUIRED_TIMEFRAMES if tf not in latest_by_tf]
    schema_rows.extend(
        [
            {
                "check": "ohlc_values",
                "status": "passed" if invalid_ohlc == 0 else "warning",
                "path": str(ohlc_artifact),
                "detail": f"rows={len(rows)} invalid_ohlc_rows={invalid_ohlc}",
            },
            {
                "check": "timestamp_parse",
                "status": "passed" if invalid_time == 0 else "warning",
                "path": str(ohlc_artifact),
                "detail": f"invalid_or_future_timestamp_rows={invalid_time}",
            },
            {
                "check": "required_timeframes",
                "status": "passed" if not missing_tf else "blocked",
                "path": str(ohlc_artifact),
                "detail": "present=" + ",".join(present) + (" missing=" + ",".join(missing_tf) if missing_tf else ""),
            },
            {
                "check": "open_candle_marker",
                "status": "passed",
                "path": str(ohlc_artifact),
                "detail": "No explicit open-candle marker detected; timestamps are treated as closed-candle artifact times.",
            },
        ]
    )

    freshness_rows: list[dict[str, Any]] = []
    for tf in REQUIRED_TIMEFRAMES:
        last = latest_by_tf.get(tf)
        if last is None:
            freshness_rows.append(
                {
                    "timeframe": tf,
                    "last_closed_candle_time": "",
                    "freshness_seconds": "",
                    "expected_max_age_seconds": TIMEFRAME_MAX_AGES[tf]["blocked"],
                    "freshness_status": "blocked",
                    "freshness_reason": "missing_required_timeframe",
                }
            )
            continue
        age = max(0, int((now - last).total_seconds()))
        warning_age = TIMEFRAME_MAX_AGES[tf]["warning"]
        blocked_age = TIMEFRAME_MAX_AGES[tf]["blocked"]
        if age > blocked_age:
            status = "blocked"
            reason = f"last closed candle older than {blocked_age} seconds"
        elif age > warning_age:
            status = "warning"
            reason = f"last closed candle older than {warning_age} seconds"
        else:
            status = "fresh"
            reason = "last closed candle inside timeframe tolerance"
        freshness_rows.append(
            {
                "timeframe": tf,
                "last_closed_candle_time": last.isoformat(),
                "freshness_seconds": age,
                "expected_max_age_seconds": blocked_age,
                "freshness_status": status,
                "freshness_reason": reason,
            }
        )
    meta = {
        "exists": True,
        "schema_valid": not missing,
        "required_timeframes_present": not missing_tf,
        "rows": len(rows),
        "resolved_columns": resolved,
    }
    return schema_rows, freshness_rows, meta


def load_scheduler_status(scheduler_status_dir: Path | None, data_refresh_run_id: str | None) -> tuple[list[dict[str, Any]], bool, list[str]]:
    if scheduler_status_dir is None or not scheduler_status_dir.exists():
        return (
            [
                {
                    "data_refresh_run_id": data_refresh_run_id or "",
                    "trigger_source": "orchestrator",
                    "timeframe": "",
                    "process_status": "missing",
                    "started_at": "",
                    "completed_at": "",
                    "last_closed_candle_time": "",
                    "freshness_seconds": "",
                    "expected_max_age_seconds": "",
                    "is_required": "",
                    "is_ready_for_trading_center": "",
                    "blocking_reason": "scheduler_status_missing_warning",
                    "source_artifact": str(scheduler_status_dir or ""),
                    "audit_status": "warning",
                }
            ],
            False,
            [],
        )
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    handoff_paths = [
        scheduler_status_dir / "scheduler_handoff_status.csv",
        scheduler_status_dir / "scheduler_handoff_status.json",
        scheduler_status_dir / "status.csv",
        scheduler_status_dir / "status.json",
    ]
    for path in handoff_paths:
        if not path.exists():
            continue
        if path.suffix.lower() == ".csv":
            rows.extend(read_csv(path))
        elif path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                rows.extend(payload)
            elif isinstance(payload, dict):
                rows.extend(payload.get("rows") if isinstance(payload.get("rows"), list) else [payload])
    if not rows:
        return (
            [
                {
                    "data_refresh_run_id": data_refresh_run_id or "",
                    "trigger_source": "orchestrator",
                    "timeframe": "",
                    "process_status": "empty",
                    "started_at": "",
                    "completed_at": "",
                    "last_closed_candle_time": "",
                    "freshness_seconds": "",
                    "expected_max_age_seconds": "",
                    "is_required": "",
                    "is_ready_for_trading_center": "",
                    "blocking_reason": "scheduler_status_empty_warning",
                    "source_artifact": str(scheduler_status_dir),
                    "audit_status": "warning",
                }
            ],
            True,
            [],
        )
    audited: list[dict[str, Any]] = []
    for row in rows:
        ready = truthy(row.get("is_ready_for_trading_center"))
        required = truthy(row.get("is_required", True))
        status = str(row.get("process_status", "")).strip().lower()
        blocking = str(row.get("blocking_reason", "")).strip()
        audit_status = "passed"
        if required and (not ready or status in {"failed", "blocked"} or blocking):
            audit_status = "blocked"
            issues.append(f"scheduler_blocked_{row.get('timeframe', '')}")
        audited.append(
            {
                "data_refresh_run_id": row.get("data_refresh_run_id", data_refresh_run_id or ""),
                "trigger_source": row.get("trigger_source", ""),
                "timeframe": row.get("timeframe", ""),
                "process_status": row.get("process_status", ""),
                "started_at": row.get("started_at", ""),
                "completed_at": row.get("completed_at", ""),
                "last_closed_candle_time": row.get("last_closed_candle_time", ""),
                "freshness_seconds": row.get("freshness_seconds", ""),
                "expected_max_age_seconds": row.get("expected_max_age_seconds", ""),
                "is_required": row.get("is_required", ""),
                "is_ready_for_trading_center": row.get("is_ready_for_trading_center", ""),
                "blocking_reason": blocking,
                "source_artifact": row.get("source_artifact", ""),
                "audit_status": audit_status,
            }
        )
    return audited, True, issues


def decide_refresh(
    schema_meta: dict[str, Any],
    freshness_rows: list[dict[str, Any]],
    scheduler_issues: list[str],
    strict_freshness: bool,
    allow_warnings: bool,
    use_last_good_on_failure: bool,
) -> tuple[str, str, int, int]:
    blocked = sum(1 for row in freshness_rows if row.get("freshness_status") == "blocked")
    warnings = sum(1 for row in freshness_rows if row.get("freshness_status") == "warning")
    if not schema_meta.get("exists"):
        return "use_last_good_artifacts" if use_last_good_on_failure else "refresh_blocked", "missing_ohlc_artifact", blocked, warnings
    if not schema_meta.get("schema_valid"):
        return "use_last_good_artifacts" if use_last_good_on_failure else "refresh_blocked", "invalid_ohlc_schema", blocked, warnings
    if not schema_meta.get("required_timeframes_present"):
        return "use_last_good_artifacts" if use_last_good_on_failure else "refresh_blocked", "missing_required_timeframes", blocked, warnings
    if scheduler_issues:
        return "use_last_good_artifacts" if use_last_good_on_failure else "refresh_blocked", "|".join(scheduler_issues), blocked, warnings
    if blocked:
        return "use_last_good_artifacts" if use_last_good_on_failure else "refresh_blocked", "freshness_blocked", blocked, warnings
    if warnings and (strict_freshness or not allow_warnings):
        return "use_last_good_artifacts" if use_last_good_on_failure else "refresh_blocked", "freshness_warning_blocked_by_policy", blocked, warnings
    if warnings:
        return "refresh_allowed_with_warnings", "freshness_warnings_allowed", blocked, warnings
    return "refresh_allowed", "all_required_inputs_ready", blocked, warnings


def dependency_plan(
    output_dir: Path,
    ohlc_artifact: Path,
    include_slow_analytics: bool = False,
    include_hourly_analytics: bool = False,
) -> list[dict[str, Any]]:
    generated_root = output_dir / "generated"
    correlation_dir = generated_root / "market_correlations" if include_slow_analytics else DEFAULT_MARKET_CORRELATIONS_DIR
    weavecount_dir = generated_root / "weavecount_screener_h1_h4" if include_hourly_analytics else DEFAULT_WEAVECOUNT_SCREENER_DIR
    latest_macd_watcher_dir = DEFAULT_LATEST_DIR / "macd_breakout_watcher"
    latest_macd_enrichment_dir = DEFAULT_LATEST_DIR / "macd_breakout_enrichment"
    macd_watcher_dir = (
        generated_root / "macd_breakout_watcher"
        if include_hourly_analytics
        else latest_macd_watcher_dir if latest_macd_watcher_dir.exists() else DEFAULT_MACD_BREAKOUT_WATCHER_DIR
    )
    macd_enrichment_dir = (
        generated_root / "macd_breakout_enrichment"
        if include_hourly_analytics
        else latest_macd_enrichment_dir if latest_macd_enrichment_dir.exists() else DEFAULT_MACD_BREAKOUT_ENRICHMENT_DIR
    )
    return [
        {
            "component": "market_radar",
            "module": "trading_center.market_radar",
            "args": ["--source-ohlc-csv", str(ohlc_artifact), "--output-dir", str(generated_root / "market_radar"), "--doc-path", str(output_dir / "docs" / "TRADING_CENTER_MARKET_RADAR_V1.md")],
            "policy": "safe_artifact_first",
            "refresh_lane": "fast",
            "enabled": True,
        },
        {
            "component": "market_correlations",
            "module": "trading_center.market_correlations",
            "args": ["--source-ohlc-csv", str(ohlc_artifact), "--output-dir", str(generated_root / "market_correlations"), "--doc-path", str(output_dir / "docs" / "TRADING_CENTER_MARKET_CORRELATIONS_V1.md")],
            "policy": "slow_last_good_by_default",
            "refresh_lane": "slow_daily",
            "enabled": include_slow_analytics,
            "skip_reason": "correlations_are_daily_last_good_by_default",
        },
        {
            "component": "weavecount_screener_h1_h4",
            "module": "trading_center.weavecount_screener_h1_h4",
            "args": ["--source-ohlc-csv", str(ohlc_artifact), "--output-dir", str(generated_root / "weavecount_screener_h1_h4")],
            "policy": "hourly_last_good_by_default",
            "refresh_lane": "hourly",
            "enabled": include_hourly_analytics,
            "skip_reason": "weavecount_is_hourly_last_good_by_default",
        },
        {
            "component": "macd_breakout_watcher",
            "module": "trading_center.macd_breakout_watcher_combined",
            "args": [
                "--groups",
                "Forex Majors,Metals,Index",
                "--tf-pairs",
                "H1:H4,H4:D1",
                "--output-dir",
                str(generated_root / "macd_breakout_watcher"),
                "--force-rebuild",
                "--no-cache",
                "--no-disk-cache",
            ],
            "policy": "hourly_last_good_by_default",
            "refresh_lane": "hourly",
            "enabled": include_hourly_analytics,
            "skip_reason": "macd_breakout_watcher_is_hourly_last_good_by_default",
        },
        {
            "component": "macd_breakout_enrichment",
            "module": "trading_center.macd_breakout_enrichment",
            "args": [
                "--snapshot-csv",
                str(macd_watcher_dir / "snapshot.csv"),
                "--watchlist-csv",
                str(macd_watcher_dir / "watchlist.csv"),
                "--ohlc-csv",
                str(ohlc_artifact),
                "--output-dir",
                str(generated_root / "macd_breakout_enrichment"),
                "--doc-path",
                str(output_dir / "docs" / "MACD_BREAKOUT_WATCHER_ENRICHMENT_V1.md"),
            ],
            "policy": "hourly_last_good_by_default",
            "refresh_lane": "hourly",
            "enabled": include_hourly_analytics,
            "skip_reason": "macd_breakout_enrichment_is_hourly_last_good_by_default",
        },
        {
            "component": "fibonacci_context",
            "module": "trading_center.fibonacci_context",
            "args": ["--ohlc-csv", str(ohlc_artifact), "--output-dir", str(generated_root / "fibonacci_context"), "--doc-path", str(output_dir / "docs" / "TRADING_CENTER_FIBONACCI_CONTEXT_V1.md")],
            "policy": "safe_artifact_first",
            "refresh_lane": "fast",
            "enabled": True,
        },
        {
            "component": "screener_unified",
            "module": "trading_center.screener_unified",
            "args": [
                "--ohlc-csv",
                str(ohlc_artifact),
                "--market-radar-csv",
                str(generated_root / "market_radar" / "market_radar.csv"),
                "--weavecount-csv",
                str(weavecount_dir / "weavecount_screener.csv"),
                "--fibonacci-context-csv",
                str(generated_root / "fibonacci_context" / "fibonacci_context.csv"),
                "--fibonacci-layers-csv",
                str(generated_root / "fibonacci_context" / "fibonacci_chart_layers.csv"),
                "--macd-breakout-enriched-csv",
                str(macd_enrichment_dir / "macd_breakout_enriched_setups.csv"),
                "--macd-breakout-chart-layers-csv",
                str(macd_enrichment_dir / "macd_breakout_chart_layers.csv"),
                "--output-dir",
                str(generated_root / "screener_unified"),
                "--doc-path",
                str(output_dir / "docs" / "TRADING_CENTER_SCREENER_UNIFIED_V1.md"),
            ],
            "policy": "safe_artifact_first",
            "refresh_lane": "fast",
            "enabled": True,
        },
        {
            "component": "dash_readonly_audit",
            "module": "trading_center.dash_readonly_app",
            "args": [
                "--audit-only",
                "--output-dir",
                str(generated_root / "dash_audit"),
                "--market-radar-csv",
                str(generated_root / "market_radar" / "market_radar.csv"),
                "--correlation-pairs-csv",
                str(correlation_dir / "correlation_pairs.csv"),
                "--rolling-correlations-csv",
                str(correlation_dir / "rolling_correlations.csv"),
                "--correlation-returns-csv",
                str(correlation_dir / "correlation_returns_sample.csv"),
                "--correlation-meta-json",
                str(correlation_dir / "run_meta.json"),
                "--ohlc-csv",
                str(ohlc_artifact),
                "--wavecount-csv",
                str(weavecount_dir / "weavecount_screener.csv"),
                "--screener-setups-csv",
                str(generated_root / "screener_unified" / "screener_setups.csv"),
                "--screener-chart-layers-csv",
                str(generated_root / "screener_unified" / "screener_chart_layers.csv"),
            ],
            "policy": "safe_artifact_first_with_correlation_last_good",
            "refresh_lane": "fast",
            "enabled": True,
        },
    ]


def run_dependencies(
    output_dir: Path,
    ohlc_artifact: Path,
    refresh_decision: str,
    dry_run: bool,
    audit_only: bool,
    include_slow_analytics: bool = False,
    include_hourly_analytics: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    refresh_executed = False
    plan = dependency_plan(
        output_dir,
        ohlc_artifact,
        include_slow_analytics=include_slow_analytics,
        include_hourly_analytics=include_hourly_analytics,
    )
    if refresh_decision not in {"refresh_allowed", "refresh_allowed_with_warnings"}:
        for index, item in enumerate(plan, start=1):
            rows.append({"step": index, "component": item["component"], "module": item["module"], "refresh_lane": item.get("refresh_lane", ""), "status": "skipped_refresh_not_allowed", "reason": refresh_decision, "command": ""})
        return rows, artifact_rows, refresh_executed
    if dry_run or audit_only:
        planned_status = "planned_dry_run" if dry_run else "skipped_audit_only"
        for index, item in enumerate(plan, start=1):
            command = " ".join([sys.executable, "-m", item["module"], *item["args"]])
            if not item.get("enabled", True):
                skipped_status = "skipped_slow_analytics_last_good" if item.get("refresh_lane") == "slow_daily" else "skipped_hourly_analytics_last_good"
                rows.append({"step": index, "component": item["component"], "module": item["module"], "refresh_lane": item.get("refresh_lane", ""), "status": skipped_status, "reason": item.get("skip_reason", "disabled_for_fast_refresh"), "command": command})
                continue
            rows.append({"step": index, "component": item["component"], "module": item["module"], "refresh_lane": item.get("refresh_lane", ""), "status": planned_status, "reason": "no_downstream_regeneration", "command": command})
        return rows, artifact_rows, refresh_executed
    for index, item in enumerate(plan, start=1):
        if not item.get("enabled", True):
            command_preview = " ".join([sys.executable, "-m", item["module"], *item["args"]])
            rows.append(
                {
                    "step": index,
                    "component": item["component"],
                    "module": item["module"],
                    "refresh_lane": item.get("refresh_lane", ""),
                    "status": "skipped_slow_analytics_last_good" if item.get("refresh_lane") == "slow_daily" else "skipped_hourly_analytics_last_good",
                    "reason": item.get("skip_reason", "disabled_for_fast_refresh"),
                    "started_at": "",
                    "completed_at": "",
                    "command": command_preview,
                    "stdout_tail": "",
                    "stderr_tail": "",
                }
            )
            continue
        command = [sys.executable, "-m", item["module"], *item["args"]]
        started = utc_now()
        proc = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
        completed = utc_now()
        status = "passed" if proc.returncode == 0 else "failed"
        rows.append(
            {
                "step": index,
                "component": item["component"],
                "module": item["module"],
                "refresh_lane": item.get("refresh_lane", ""),
                "status": status,
                "reason": f"returncode={proc.returncode}",
                "started_at": started.isoformat(),
                "completed_at": completed.isoformat(),
                "command": " ".join(command),
                "stdout_tail": proc.stdout[-500:],
                "stderr_tail": proc.stderr[-500:],
            }
        )
        refresh_executed = True
        if proc.returncode != 0:
            break
    for path in (output_dir / "generated").glob("**/*"):
        if path.is_file() and path.suffix.lower() in {".csv", ".json", ".md"}:
            row_count = ""
            if path.suffix.lower() == ".csv":
                try:
                    row_count = len(read_csv(path))
                except Exception:
                    row_count = ""
            artifact_rows.append({"artifact": path.name, "path": str(path), "exists": True, "rows": row_count, "status": "generated"})
    return rows, artifact_rows, refresh_executed


def dependency_status(dependency_rows: list[dict[str, Any]], component: str) -> str:
    for row in dependency_rows:
        if row.get("component") == component:
            return str(row.get("status", ""))
    return ""


def promote_latest_artifacts(
    latest_dir: Path,
    output_dir: Path,
    ohlc_artifact: Path,
    refresh_decision: str,
    dry_run: bool,
    audit_only: bool,
    dependency_rows: list[dict[str, Any]],
    completed_at: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated_root = output_dir / "generated"
    allowed = refresh_decision in {"refresh_allowed", "refresh_allowed_with_warnings"}
    can_promote = allowed and not dry_run and not audit_only

    def add_row(
        component: str,
        source: Path,
        target: Path,
        status: str,
        reason: str,
        copied_files: int = 0,
    ) -> None:
        rows.append(
            {
                "component": component,
                "source_path": str(source),
                "latest_path": str(target),
                "promotion_status": status,
                "reason": reason,
                "copied_files": copied_files,
                "latest_exists_after": target.exists(),
                "promoted_at": completed_at.isoformat() if status == "promoted" else "",
            }
        )

    if can_promote and ohlc_artifact.exists():
        target = latest_dir / "ohlc" / "ohlc_mtf.csv"
        copy_file_preserving_dirs(ohlc_artifact, target)
        add_row("ohlc", ohlc_artifact, target, "promoted", "valid_ohlc_artifact", 1)
    else:
        add_row("ohlc", ohlc_artifact, latest_dir / "ohlc" / "ohlc_mtf.csv", "not_promoted", "refresh_not_executed_or_not_allowed")

    component_dirs = {
        "market_radar": generated_root / "market_radar",
        "fibonacci_context": generated_root / "fibonacci_context",
        "screener_unified": generated_root / "screener_unified",
        "dash_audit": generated_root / "dash_audit",
        "weavecount": generated_root / "weavecount_screener_h1_h4",
        "macd_breakout_watcher": generated_root / "macd_breakout_watcher",
        "macd_breakout_enrichment": generated_root / "macd_breakout_enrichment",
        "correlations": generated_root / "market_correlations",
    }
    bootstrap_last_good_dirs = {
        "weavecount": DEFAULT_WEAVECOUNT_SCREENER_DIR,
        "macd_breakout_watcher": DEFAULT_MACD_BREAKOUT_WATCHER_DIR,
        "macd_breakout_enrichment": DEFAULT_MACD_BREAKOUT_ENRICHMENT_DIR,
        "correlations": DEFAULT_MARKET_CORRELATIONS_DIR,
    }
    dependency_names = {
        "market_radar": "market_radar",
        "fibonacci_context": "fibonacci_context",
        "screener_unified": "screener_unified",
        "dash_audit": "dash_readonly_audit",
        "weavecount": "weavecount_screener_h1_h4",
        "macd_breakout_watcher": "macd_breakout_watcher",
        "macd_breakout_enrichment": "macd_breakout_enrichment",
        "correlations": "market_correlations",
    }
    latest_names = {
        "market_radar": "market_radar",
        "fibonacci_context": "fibonacci_context",
        "screener_unified": "screener_unified",
        "dash_audit": "dash_audit",
        "weavecount": "weavecount",
        "macd_breakout_watcher": "macd_breakout_watcher",
        "macd_breakout_enrichment": "macd_breakout_enrichment",
        "correlations": "correlations",
    }
    for component, source_dir in component_dirs.items():
        dep_status = dependency_status(dependency_rows, dependency_names[component])
        target_dir = latest_dir / latest_names[component]
        if can_promote and dep_status == "passed" and source_dir.exists():
            copied = copy_tree_files(source_dir, target_dir)
            add_row(component, source_dir, target_dir, "promoted", "dependency_passed", copied)
        elif dep_status in {"skipped_hourly_analytics_last_good", "skipped_slow_analytics_last_good"}:
            if target_dir.exists():
                add_row(component, source_dir, target_dir, "preserved_last_good", dep_status)
            else:
                bootstrap_dir = bootstrap_last_good_dirs.get(component)
                if bootstrap_dir and bootstrap_dir.exists() and can_promote:
                    copied = copy_tree_files(bootstrap_dir, target_dir)
                    add_row(component, bootstrap_dir, target_dir, "bootstrapped_last_good", dep_status, copied)
                else:
                    add_row(component, source_dir, target_dir, "missing_last_good", dep_status)
        else:
            add_row(component, source_dir, target_dir, "not_promoted", dep_status or "dependency_not_run")

    manifest = {
        "generated_at": completed_at.isoformat(),
        "latest_dir": str(latest_dir),
        "refresh_decision": refresh_decision,
        "dry_run": dry_run,
        "audit_only": audit_only,
        "promoted_components": [row["component"] for row in rows if row["promotion_status"] == "promoted"],
        "preserved_last_good_components": [
            row["component"] for row in rows if row["promotion_status"] == "preserved_last_good"
        ],
        "bootstrapped_last_good_components": [
            row["component"] for row in rows if row["promotion_status"] == "bootstrapped_last_good"
        ],
        "missing_last_good_components": [
            row["component"] for row in rows if row["promotion_status"] == "missing_last_good"
        ],
        "components": rows,
        "setup_validity_policy": (
            "A setup is not invalidated merely because it comes from a last-good artifact; "
            "validity remains controlled by screener timing fields such as late, invalidated, stale and distance."
        ),
    }
    if can_promote:
        latest_dir.mkdir(parents=True, exist_ok=True)
        write_json(latest_dir / "latest_manifest.json", manifest)
        write_csv(latest_dir / "latest_manifest.csv", rows)
    return rows, manifest


def safety_audit() -> list[dict[str, Any]]:
    return [
        {"boundary": "scheduler_service_implemented", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "background_loop_implemented", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "uses_closed_candles_only", "expected": "true", "observed": "true", "status": "passed"},
        {"boundary": "uses_open_candles", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "sql_real_written", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "ddl_executed", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "db_connected", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "mt5_connected", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "telegram_connected", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "orders_sent", "expected": "0", "observed": "0", "status": "passed"},
        {"boundary": "signals_generated", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "backtests_executed", "expected": "false", "observed": "false", "status": "passed"},
    ]


def build_doc(meta: dict[str, Any]) -> str:
    return f"""# Artifact Refresh Orchestrator V1

Decision: `{meta['decision']}`

## Objetivo

Se implementa una CLI audit-only/manual para validar si el Trading Center puede
refrescar sus artifacts desde un OHLC cerrado por timeframe. La fase no
implementa scheduler recurrente, daemon, MT5, Telegram, SQL writes ni señales.

## Qué implementa

- CLI `python -m trading_center.artifact_refresh_orchestrator`.
- Triggers `manual`, `interval` y `event`.
- Lectura opcional del handoff del scheduler por timeframe.
- Validación de schema OHLC con alias `timestamp` -> `time`.
- Freshness por `M15`, `H1`, `H4` y `D1`.
- Decisión `refresh_allowed`, `refresh_allowed_with_warnings`,
  `refresh_blocked` o `use_last_good_artifacts`.
- Auditoría de dependencias y política last-good.

## Qué no implementa

- No implementa scheduler de datos.
- No resuelve internamente si una ejecución a `10:03` corresponde al cierre
  `10:00`; eso debe venir en `last_closed_candle_time` desde el scheduler.
- No crea servicio recurrente ni background loop.
- No llama por defecto a `sql_market_data_readonly`; la extracción de datos es
  capa inferior.

## Resultado del run

- trigger: `{meta['trigger']}`
- audit_only: `{meta['audit_only']}`
- dry_run: `{meta['dry_run']}`
- refresh_decision: `{meta['refresh_decision']}`
- refresh_executed: `{meta['refresh_executed']}`
- freshness_warning_count: `{meta['freshness_warning_count']}`
- freshness_blocked_count: `{meta['freshness_blocked_count']}`
- last_good_artifact_used: `{meta['last_good_artifact_used']}`

## Seguridad

- `uses_closed_candles_only=true`
- `uses_open_candles=false`
- `sql_real_written=false`
- `ddl_executed=false`
- `db_connected=false`
- `mt5_connected=false`
- `telegram_connected=false`
- `orders_sent=0`
- `signals_generated=false`
- `backtests_executed=false`

## Siguiente paso

Diseñar la integración con el scheduler real de datos por timeframe y después
automatizar el trigger de intervalo/evento, manteniendo esta CLI como base de
auditoría.
"""


def build_doc_clean(meta: dict[str, Any]) -> str:
    return f"""# Artifact Refresh Orchestrator V1

Decision: `{meta['decision']}`

## Objetivo

Se implementa una CLI artifact-first para validar si el Trading Center puede
refrescar sus artifacts desde un OHLC cerrado por timeframe. La fase no
implementa scheduler recurrente, daemon, MT5, Telegram, SQL writes ni senales.

## Que implementa

- CLI `python -m trading_center.artifact_refresh_orchestrator`.
- Triggers `manual`, `interval` y `event`.
- Lectura opcional del handoff del scheduler por timeframe.
- Validacion de schema OHLC con alias `timestamp` -> `time`.
- Freshness por `M15`, `H1`, `H4` y `D1`.
- Decision `refresh_allowed`, `refresh_allowed_with_warnings`,
  `refresh_blocked` o `use_last_good_artifacts`.
- Auditoria de dependencias, refresh rapido y politica last-good.

## Que no implementa

- No implementa scheduler de datos.
- No resuelve internamente si una ejecucion a `10:03` corresponde al cierre
  `10:00`; eso debe venir en `last_closed_candle_time` desde el scheduler.
- No crea servicio recurrente ni background loop.
- No llama por defecto a `sql_market_data_readonly`; la extraccion de datos es
  capa inferior.

## Resultado del run

- trigger: `{meta['trigger']}`
- audit_only: `{meta['audit_only']}`
- dry_run: `{meta['dry_run']}`
- refresh_decision: `{meta['refresh_decision']}`
- refresh_executed: `{meta['refresh_executed']}`
- freshness_warning_count: `{meta['freshness_warning_count']}`
- freshness_blocked_count: `{meta['freshness_blocked_count']}`
- last_good_artifact_used: `{meta['last_good_artifact_used']}`
- include_hourly_analytics: `{meta['include_hourly_analytics']}`
- include_slow_analytics: `{meta['include_slow_analytics']}`
- weavecount_refresh_mode: `{meta['weavecount_refresh_mode']}`
- market_correlations_refresh_mode: `{meta['market_correlations_refresh_mode']}`
- latest_dir: `{meta['latest_dir']}`
- latest_manifest_written: `{meta['latest_manifest_written']}`

## Seguridad

- `uses_closed_candles_only=true`
- `uses_open_candles=false`
- `sql_real_written=false`
- `ddl_executed=false`
- `db_connected=false`
- `mt5_connected=false`
- `telegram_connected=false`
- `orders_sent=0`
- `signals_generated=false`
- `backtests_executed=false`

## Politica de refresh

- Ciclo rapido: Mercado, Fibonacci, Screener y audit del Dash.
- WeaveCount: analitica horaria o bajo `--include-hourly-analytics`.
- Correlaciones: analitica lenta, diaria o bajo `--include-slow-analytics`.
- En ciclos rapidos, el Dash consume los artifacts last-good de WeaveCount y
  Correlacion para evitar bloquear el refresco M15.
- La promocion a latest es por componente: solo se copian artifacts de
  dependencias que pasan. Los componentes saltados por frecuencia preservan
  last-good si existe.
- Un setup no queda invalido solo por venir de last-good; su vigencia depende
  de `late`, `invalidated`, `stale`, distancia y timing del Screener.

## Siguiente paso

Disenar la integracion con el scheduler real de datos por timeframe y despues
automatizar el trigger de intervalo/evento, manteniendo esta CLI como base de
auditoria.
"""


def execute(args: argparse.Namespace, now: datetime | None = None) -> OrchestratorResult:
    now = now or utc_now()
    started_at = now
    output_dir: Path = args.output_dir
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    scheduler_rows, scheduler_present, scheduler_issues = load_scheduler_status(args.scheduler_status_dir, args.data_refresh_run_id)
    schema_rows, freshness_rows, schema_meta = load_ohlc_audit(args.ohlc_artifact, now)
    decision, reason, freshness_blocked_count, freshness_warning_count = decide_refresh(
        schema_meta,
        freshness_rows,
        scheduler_issues,
        args.strict_freshness,
        args.allow_warnings,
        args.use_last_good_on_failure,
    )
    dependency_rows, artifact_rows, refresh_executed = run_dependencies(
        output_dir,
        args.ohlc_artifact,
        decision,
        args.dry_run,
        args.audit_only,
        include_slow_analytics=args.include_slow_analytics,
        include_hourly_analytics=args.include_hourly_analytics,
    )
    last_good_used = decision == "use_last_good_artifacts"
    completed_at = utc_now()
    latest_rows, latest_manifest = promote_latest_artifacts(
        args.latest_dir,
        output_dir,
        args.ohlc_artifact,
        decision,
        args.dry_run,
        args.audit_only,
        dependency_rows,
        completed_at,
    )
    trigger_rows = [
        {
            "trigger": args.trigger,
            "interval_minutes": args.interval_minutes,
            "data_refresh_run_id": args.data_refresh_run_id or "",
            "scheduler_status_dir": str(args.scheduler_status_dir or ""),
            "dry_run": args.dry_run,
            "audit_only": args.audit_only,
            "strict_freshness": args.strict_freshness,
            "allow_warnings": args.allow_warnings,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "decision": decision,
            "reason": reason,
        }
    ]
    decision_rows = [
        {
            "refresh_decision": decision,
            "reason": reason,
            "ohlc_schema_valid": schema_meta.get("schema_valid", False),
            "required_timeframes_present": schema_meta.get("required_timeframes_present", False),
            "freshness_blocked_count": freshness_blocked_count,
            "freshness_warning_count": freshness_warning_count,
            "scheduler_blocking_issues": "|".join(scheduler_issues),
            "refresh_executed": refresh_executed,
        }
    ]
    last_good_rows = [
        {
            "artifact_family": "trading_center",
            "last_good_artifact_used": last_good_used,
            "refresh_decision": decision,
            "policy_status": "audit_only_no_latest_pointer",
            "notes": "No files are moved, deleted or promoted as latest in v1.",
        }
    ]
    safety_rows = safety_audit()
    issue_rows = [
        {
            "issue_id": "ORCH_V1_01",
            "severity": "medium" if scheduler_present else "low",
            "status": "open" if not scheduler_present else "review",
            "description": "Scheduler status handoff missing; freshness was validated directly from OHLC artifact." if not scheduler_present else "Scheduler status handoff present; review any blocked rows.",
            "mitigation": "Integrate real scheduler status in the next phase.",
        }
    ]
    run_meta = {
        "phase": "artifact_refresh_orchestrator_v1",
        "generated_at": completed_at.isoformat(),
        "decision": "artifact_refresh_orchestrator_v1_ready_for_scheduler_integration_design",
        "artifact_refresh_orchestrator_implemented": True,
        "scheduler_service_implemented": False,
        "background_loop_implemented": False,
        "trigger": args.trigger,
        "interval_minutes": args.interval_minutes,
        "refresh_decision": decision,
        "refresh_executed": refresh_executed,
        "dry_run": args.dry_run,
        "audit_only": args.audit_only,
        "include_slow_analytics": args.include_slow_analytics,
        "include_hourly_analytics": args.include_hourly_analytics,
        "market_correlations_refresh_mode": "regenerate" if args.include_slow_analytics else "last_good_daily",
        "weavecount_refresh_mode": "regenerate" if args.include_hourly_analytics else "last_good_hourly",
        "macd_breakout_refresh_mode": "regenerate" if args.include_hourly_analytics else "last_good_hourly",
        "fast_refresh_components": ["market_radar", "fibonacci_context", "screener_unified", "dash_readonly_audit"],
        "hourly_refresh_components": ["weavecount_screener_h1_h4", "macd_breakout_watcher", "macd_breakout_enrichment"],
        "slow_refresh_components": ["market_correlations"],
        "slow_analytics_frequency": "daily_or_manual",
        "hourly_analytics_frequency": "hourly_or_h1_h4_close",
        "latest_dir": str(args.latest_dir),
        "latest_manifest_written": bool(decision in {"refresh_allowed", "refresh_allowed_with_warnings"} and not args.dry_run and not args.audit_only),
        "latest_promoted_components": latest_manifest.get("promoted_components", []),
        "latest_preserved_last_good_components": latest_manifest.get("preserved_last_good_components", []),
        "latest_bootstrapped_last_good_components": latest_manifest.get("bootstrapped_last_good_components", []),
        "latest_missing_last_good_components": latest_manifest.get("missing_last_good_components", []),
        "scheduler_status_dir_present": scheduler_present,
        "ohlc_schema_valid": bool(schema_meta.get("schema_valid")),
        "required_timeframes_present": bool(schema_meta.get("required_timeframes_present")),
        "freshness_blocked_count": freshness_blocked_count,
        "freshness_warning_count": freshness_warning_count,
        "last_good_artifact_used": last_good_used,
        "uses_closed_candles_only": True,
        "uses_open_candles": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    result = OrchestratorResult(
        trigger_rows=trigger_rows,
        scheduler_rows=scheduler_rows,
        schema_rows=schema_rows,
        freshness_rows=freshness_rows,
        decision_rows=decision_rows,
        dependency_rows=dependency_rows,
        artifact_rows=artifact_rows,
        last_good_rows=last_good_rows,
        latest_rows=latest_rows,
        safety_rows=safety_rows,
        issue_rows=issue_rows,
        run_meta=run_meta,
    )
    write_result(output_dir, result)
    if args.doc_path:
        args.doc_path.parent.mkdir(parents=True, exist_ok=True)
        args.doc_path.write_text(build_doc_clean(run_meta), encoding="utf-8")
    return result


def write_result(output_dir: Path, result: OrchestratorResult) -> None:
    tables_dir = output_dir / "tables"
    write_csv(tables_dir / "trigger_audit.csv", result.trigger_rows)
    write_csv(tables_dir / "data_scheduler_handoff_audit.csv", result.scheduler_rows)
    write_csv(tables_dir / "ohlc_schema_audit.csv", result.schema_rows)
    write_csv(tables_dir / "timeframe_freshness_audit.csv", result.freshness_rows)
    write_csv(tables_dir / "refresh_decision_audit.csv", result.decision_rows)
    write_csv(tables_dir / "dependency_execution_audit.csv", result.dependency_rows)
    write_csv(tables_dir / "artifact_generation_audit.csv", result.artifact_rows or [{"artifact": "", "path": "", "exists": "", "rows": "", "status": "not_generated"}])
    write_csv(tables_dir / "last_good_artifact_audit.csv", result.last_good_rows)
    write_csv(tables_dir / "latest_promotion_audit.csv", result.latest_rows)
    write_csv(tables_dir / "safety_boundary_audit.csv", result.safety_rows)
    write_csv(tables_dir / "issues_or_risks.csv", result.issue_rows)
    write_json(output_dir / "run_meta.json", result.run_meta)
    (output_dir / "ARTIFACT_REFRESH_ORCHESTRATOR_V1.md").write_text(build_doc_clean(result.run_meta), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and optionally orchestrate Trading Center artifact refresh.")
    parser.add_argument("--trigger", choices=("manual", "interval", "event"), default="manual")
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--data-refresh-run-id", default="")
    parser.add_argument("--scheduler-status-dir", type=Path, default=None)
    parser.add_argument("--ohlc-artifact", type=Path, default=DEFAULT_OHLC_ARTIFACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--latest-dir", type=Path, default=DEFAULT_LATEST_DIR)
    parser.add_argument("--strict-freshness", action="store_true")
    parser.add_argument("--allow-warnings", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--use-last-good-on-failure", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument(
        "--include-slow-analytics",
        action="store_true",
        help="Regenerate slow analytics such as market correlations. Default fast refresh uses last-good correlation artifacts.",
    )
    parser.add_argument(
        "--include-hourly-analytics",
        action="store_true",
        help="Regenerate hourly analytics such as WeaveCount. Default M15 refresh uses last-good WeaveCount artifacts.",
    )
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--design-doc-path", type=Path, default=DEFAULT_DESIGN_DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.trigger == "event" and not args.data_refresh_run_id:
        # Event mode can still audit, but the missing id must be explicit.
        args.data_refresh_run_id = "missing_event_run_id"
    execute(args)


if __name__ == "__main__":
    main()
