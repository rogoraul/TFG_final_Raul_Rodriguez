from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from trading_center import refresh_service, scheduler_refresh_integration
from trading_center.sql_market_data_readonly import (
    DEFAULT_BARS_PER_PAIR,
    DEFAULT_GROUPS,
    DEFAULT_TIMEFRAMES,
    SqlMarketDataReadonlyConfig,
    extract_sql_market_data,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts/tfg/live_hook"
DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
HOOK_ENV_VAR = "TRADING_CENTER_REFRESH_AFTER_INGEST"
DRY_RUN_ENV_VAR = "TRADING_CENTER_REFRESH_DRY_RUN"


@dataclass(frozen=True)
class TradingCenterRefreshHookConfig:
    enabled: bool = False
    dry_run: bool = False
    audit_only: bool = False
    output_root: Path = DEFAULT_OUTPUT_ROOT
    latest_dir: Path = DEFAULT_LATEST_DIR
    time_zone: str = "Europe/Madrid"
    bars_per_pair: int = DEFAULT_BARS_PER_PAIR
    groups: tuple[str, ...] = DEFAULT_GROUPS
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES
    ohlc_artifact: Path | None = None
    skip_sql_extract: bool = False


@dataclass(frozen=True)
class TradingCenterRefreshHookResult:
    hook_rows: list[dict[str, Any]]
    run_meta: dict[str, Any]
    output_dir: Path
    ohlc_artifact: Path | None
    handoff_dir: Path | None
    refresh_dir: Path | None


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "si"}


def config_from_env() -> TradingCenterRefreshHookConfig:
    return TradingCenterRefreshHookConfig(
        enabled=truthy(os.getenv(HOOK_ENV_VAR)),
        dry_run=truthy(os.getenv(DRY_RUN_ENV_VAR)),
    )


def normalise_timeframes(timeframes: Iterable[Any]) -> tuple[str, ...]:
    names: list[str] = []
    for item in timeframes:
        text = str(item or "").strip().upper()
        if not text:
            continue
        if text not in names:
            names.append(text)
    return tuple(names)


def hook_run_id(timeframes: tuple[str, ...], scheduler_now: datetime) -> str:
    tf_part = "_".join(timeframes) if timeframes else "unknown_tf"
    return f"mt5_ingest_{tf_part}_{scheduler_now.strftime('%Y%m%dT%H%M%S%z')}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def execute_trading_center_refresh_hook(
    timeframes: Iterable[Any],
    *,
    config: TradingCenterRefreshHookConfig | None = None,
    scheduler_now: datetime | None = None,
    sql_extractor: Callable[[SqlMarketDataReadonlyConfig], Any] | None = None,
    scheduler_runner: Callable[[Any, datetime | None], Any] | None = None,
    refresh_runner: Callable[[Any], Any] | None = None,
) -> TradingCenterRefreshHookResult:
    config = config or config_from_env()
    scheduler_now = scheduler_now or datetime.now(ZoneInfo(config.time_zone))
    if scheduler_now.tzinfo is None:
        scheduler_now = scheduler_now.replace(tzinfo=ZoneInfo(config.time_zone))
    timeframes_tuple = normalise_timeframes(timeframes)
    run_id = hook_run_id(timeframes_tuple, scheduler_now)
    output_dir = config.output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    hook_rows: list[dict[str, Any]] = []
    ohlc_artifact: Path | None = config.ohlc_artifact
    handoff_dir: Path | None = None
    refresh_dir: Path | None = None
    sql_meta: dict[str, Any] = {}
    scheduler_meta: dict[str, Any] = {}
    refresh_meta: dict[str, Any] = {}

    if not config.enabled:
        hook_rows.append({"step": "hook_enabled", "status": "skipped", "reason": f"{HOOK_ENV_VAR}=false"})
        run_meta = build_run_meta(config, run_id, timeframes_tuple, sql_meta, scheduler_meta, refresh_meta, skipped=True)
        write_hook_outputs(output_dir, hook_rows, run_meta)
        return TradingCenterRefreshHookResult(hook_rows, run_meta, output_dir, None, None, None)

    if not timeframes_tuple:
        hook_rows.append({"step": "timeframes", "status": "blocked", "reason": "no_timeframes_provided"})
        run_meta = build_run_meta(config, run_id, timeframes_tuple, sql_meta, scheduler_meta, refresh_meta, blocked=True)
        write_hook_outputs(output_dir, hook_rows, run_meta)
        return TradingCenterRefreshHookResult(hook_rows, run_meta, output_dir, None, None, None)

    if config.skip_sql_extract:
        if ohlc_artifact is None:
            hook_rows.append({"step": "sql_readonly_extract", "status": "blocked", "reason": "skip_sql_extract_without_ohlc_artifact"})
            run_meta = build_run_meta(config, run_id, timeframes_tuple, sql_meta, scheduler_meta, refresh_meta, blocked=True)
            write_hook_outputs(output_dir, hook_rows, run_meta)
            return TradingCenterRefreshHookResult(hook_rows, run_meta, output_dir, None, None, None)
        hook_rows.append({"step": "sql_readonly_extract", "status": "skipped", "reason": "provided_ohlc_artifact", "path": str(ohlc_artifact)})
    else:
        sql_output_dir = output_dir / "sql_market_data_readonly"
        extractor = sql_extractor or extract_sql_market_data
        sql_result = extractor(
            SqlMarketDataReadonlyConfig(
                output_dir=sql_output_dir,
                timeframes=config.timeframes,
                groups=config.groups,
                bars_per_pair=config.bars_per_pair,
            )
        )
        sql_meta = dict(getattr(sql_result, "run_meta", {}) or {})
        ohlc_artifact = sql_output_dir / "ohlc_mtf.csv"
        hook_rows.append(
            {
                "step": "sql_readonly_extract",
                "status": "passed" if ohlc_artifact.exists() else "blocked",
                "reason": sql_meta.get("decision", ""),
                "path": str(ohlc_artifact),
            }
        )
        if not ohlc_artifact.exists():
            run_meta = build_run_meta(config, run_id, timeframes_tuple, sql_meta, scheduler_meta, refresh_meta, blocked=True)
            write_hook_outputs(output_dir, hook_rows, run_meta)
            return TradingCenterRefreshHookResult(hook_rows, run_meta, output_dir, ohlc_artifact, None, None)

    handoff_dir = output_dir / "scheduler_handoff"
    scheduler_args = scheduler_refresh_integration.parse_args(
        [
            "--trigger",
            "event",
            "--data-refresh-run-id",
            run_id,
            "--ohlc-artifact",
            str(ohlc_artifact),
            "--output-dir",
            str(handoff_dir),
            "--scheduler-now",
            scheduler_now.isoformat(),
            "--doc-path",
            str(output_dir / "docs" / "SCHEDULER_TO_TRADING_CENTER_REFRESH_INTEGRATION_V1.md"),
        ]
    )
    scheduler_result = (scheduler_runner or scheduler_refresh_integration.execute)(scheduler_args, scheduler_now)
    scheduler_meta = dict(getattr(scheduler_result, "run_meta", {}) or {})
    hook_rows.append(
        {
            "step": "scheduler_handoff",
            "status": "passed",
            "reason": scheduler_meta.get("decision", ""),
            "path": str(handoff_dir),
            "ready_rows": scheduler_meta.get("handoff_ready_rows", ""),
            "blocked_rows": scheduler_meta.get("handoff_blocked_rows", ""),
        }
    )

    refresh_dir = output_dir / "refresh_service"
    refresh_args_list = [
        "--service-mode",
        "handoff-driven",
        "--handoff-dir",
        str(handoff_dir),
        "--ohlc-artifact",
        str(ohlc_artifact),
        "--latest-dir",
        str(config.latest_dir),
        "--output-root",
        str(refresh_dir),
        "--once",
        "--scheduler-now",
        scheduler_now.isoformat(),
    ]
    if config.dry_run:
        refresh_args_list.append("--dry-run")
    if config.audit_only:
        refresh_args_list.append("--audit-only")
    refresh_args = refresh_service.parse_args(refresh_args_list)
    refresh_result = (refresh_runner or refresh_service.execute)(refresh_args)
    refresh_meta = dict(getattr(refresh_result, "run_meta", {}) or {})
    hook_rows.append(
        {
            "step": "trading_center_refresh",
            "status": "passed",
            "reason": refresh_meta.get("decision", ""),
            "path": str(refresh_dir),
            "service_mode": refresh_meta.get("service_mode", ""),
            "slots_processed": refresh_meta.get("slots_processed", ""),
        }
    )

    run_meta = build_run_meta(config, run_id, timeframes_tuple, sql_meta, scheduler_meta, refresh_meta)
    write_hook_outputs(output_dir, hook_rows, run_meta)
    return TradingCenterRefreshHookResult(hook_rows, run_meta, output_dir, ohlc_artifact, handoff_dir, refresh_dir)


def maybe_run_trading_center_refresh_after_ingest(
    timeframes: Iterable[Any],
    *,
    scheduler_now: datetime | None = None,
    config: TradingCenterRefreshHookConfig | None = None,
) -> TradingCenterRefreshHookResult:
    try:
        return execute_trading_center_refresh_hook(timeframes, config=config, scheduler_now=scheduler_now)
    except Exception as exc:  # pragma: no cover - protects live ingestion loop
        config = config or config_from_env()
        scheduler_now = scheduler_now or datetime.now(ZoneInfo(config.time_zone))
        run_id = hook_run_id(normalise_timeframes(timeframes), scheduler_now)
        output_dir = config.output_root / run_id
        row = {"step": "hook_exception", "status": "blocked", "reason": exc.__class__.__name__, "detail": str(exc)}
        run_meta = build_run_meta(config, run_id, normalise_timeframes(timeframes), {}, {}, {}, blocked=True, exception_class=exc.__class__.__name__)
        write_hook_outputs(output_dir, [row], run_meta)
        print(f"[WARN] Trading Center refresh hook failed: {exc.__class__.__name__}: {exc}")
        return TradingCenterRefreshHookResult([row], run_meta, output_dir, None, None, None)


def build_run_meta(
    config: TradingCenterRefreshHookConfig,
    run_id: str,
    timeframes: tuple[str, ...],
    sql_meta: dict[str, Any],
    scheduler_meta: dict[str, Any],
    refresh_meta: dict[str, Any],
    *,
    skipped: bool = False,
    blocked: bool = False,
    exception_class: str = "",
) -> dict[str, Any]:
    return {
        "phase": "scheduler_to_trading_center_live_hook_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "scheduler_to_trading_center_live_hook_v1_ready_for_local_live_review" if not skipped and not blocked else "scheduler_to_trading_center_live_hook_v1_not_executed",
        "hook_enabled": config.enabled,
        "hook_skipped": skipped,
        "hook_blocked": blocked,
        "exception_class": exception_class,
        "data_refresh_run_id": run_id,
        "updated_timeframes": list(timeframes),
        "sql_readonly_extract_decision": sql_meta.get("decision", ""),
        "scheduler_handoff_decision": scheduler_meta.get("decision", ""),
        "refresh_service_decision": refresh_meta.get("decision", ""),
        "refresh_service_mode": refresh_meta.get("service_mode", ""),
        "slots_processed": refresh_meta.get("slots_processed", 0),
        "latest_dir": str(config.latest_dir),
        "artifact_first": True,
        "scheduler_original_hook_integrated": True,
        "sql_real_written": False,
        "ddl_executed": False,
        "mt5_orders_sent": 0,
        "telegram_connected": False,
        "signals_generated": False,
        "backtests_executed": False,
    }


def write_hook_outputs(output_dir: Path, rows: list[dict[str, Any]], run_meta: dict[str, Any]) -> None:
    tables_dir = output_dir / "tables"
    write_csv(tables_dir / "scheduler_live_hook_audit.csv", rows)
    write_json(output_dir / "scheduler_live_hook_audit.json", rows)
    write_json(output_dir / "run_meta.json", run_meta)


def parse_csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split(",") if item.strip())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the optional MT5-ingest to Trading Center refresh hook once.")
    parser.add_argument("--timeframes", default="M15")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--latest-dir", type=Path, default=DEFAULT_LATEST_DIR)
    parser.add_argument("--scheduler-now", default="")
    parser.add_argument("--time-zone", default="Europe/Madrid")
    parser.add_argument("--ohlc-artifact", type=Path, default=None)
    parser.add_argument("--skip-sql-extract", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    scheduler_now = None
    if args.scheduler_now:
        scheduler_now = datetime.fromisoformat(args.scheduler_now)
        if scheduler_now.tzinfo is None:
            scheduler_now = scheduler_now.replace(tzinfo=ZoneInfo(args.time_zone))
    execute_trading_center_refresh_hook(
        parse_csv_tuple(args.timeframes),
        config=TradingCenterRefreshHookConfig(
            enabled=args.enable,
            dry_run=args.dry_run,
            audit_only=args.audit_only,
            output_root=args.output_root,
            latest_dir=args.latest_dir,
            time_zone=args.time_zone,
            ohlc_artifact=args.ohlc_artifact,
            skip_sql_extract=args.skip_sql_extract,
        ),
        scheduler_now=scheduler_now,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
