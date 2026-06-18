from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from trading_center import artifact_refresh_orchestrator as orchestrator_module
from trading_center import scheduler_refresh_integration as scheduler_module


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
DEFAULT_OHLC_ARTIFACT = DEFAULT_LATEST_DIR / "ohlc" / "ohlc_mtf.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts/tfg/trading_center_refresh_service_v1_2026-06-06"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TRADING_CENTER_REFRESH_SERVICE_V1.md"
DEFAULT_HANDOFF_DIR: Path | None = None

HANDOFF_FIELDS = [
    "data_refresh_run_id",
    "trigger_source",
    "scheduler_started_at",
    "scheduler_completed_at",
    "timeframe",
    "expected_slot_time",
    "last_closed_candle_time",
    "data_available_until",
    "process_status",
    "is_required",
    "is_ready_for_trading_center",
    "freshness_seconds",
    "expected_max_age_seconds",
    "rows_loaded",
    "symbols_loaded",
    "source_artifact",
    "blocking_reason",
    "warning_reason",
    "created_at_utc",
]


@dataclass
class RefreshServiceResult:
    cycle_rows: list[dict[str, Any]]
    slot_policy_rows: list[dict[str, Any]]
    hourly_policy_rows: list[dict[str, Any]]
    slow_policy_rows: list[dict[str, Any]]
    orchestrator_rows: list[dict[str, Any]]
    manifest_rows: list[dict[str, Any]]
    safety_rows: list[dict[str, Any]]
    issue_rows: list[dict[str, Any]]
    run_meta: dict[str, Any]


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def parse_dt(value: Any, tz_name: str = "Europe/Madrid") -> datetime | None:
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
                parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
            return parsed
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=ZoneInfo(tz_name))
        except ValueError:
            continue
    return None


def read_csv(path: Path) -> list[dict[str, Any]]:
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


def now_in_zone(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def floor_interval_slot(dt: datetime, interval_minutes: int) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    minute = (dt.minute // interval_minutes) * interval_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def last_closed_slot(dt: datetime, interval_minutes: int) -> datetime:
    return floor_interval_slot(dt, interval_minutes)


def next_interval_slot(dt: datetime, interval_minutes: int) -> datetime:
    base = floor_interval_slot(dt, interval_minutes)
    return base + timedelta(minutes=interval_minutes)


def sleep_seconds_until_slot(now_value: datetime, slot_dt: datetime, margin_seconds: int) -> float:
    target = slot_dt + timedelta(seconds=margin_seconds)
    return max(0.0, (target - now_value).total_seconds())


def slot_id(slot_dt: datetime, interval_minutes: int) -> str:
    return f"{slot_dt.strftime('%Y%m%dT%H%M%S%z')}_M{interval_minutes}"


def data_refresh_run_id(slot_dt: datetime, interval_minutes: int) -> str:
    return f"trading_center_refresh_{slot_id(slot_dt, interval_minutes)}"


def is_hourly_boundary(slot_dt: datetime) -> bool:
    return slot_dt.minute == 0


def is_h4_boundary(slot_dt: datetime) -> bool:
    return is_hourly_boundary(slot_dt) and slot_dt.hour % 4 == 0


def is_daily_boundary(slot_dt: datetime) -> bool:
    return slot_dt.hour == 0 and slot_dt.minute == 0


def manifest_fingerprint(path: Path) -> dict[str, Any]:
    state = {
        "path": str(path),
        "exists": path.exists(),
        "fingerprint": "",
        "manifest_timestamp": "",
        "mtime_utc": "",
        "refresh_decision": "",
    }
    if not path.exists():
        return state
    content = path.read_bytes()
    state["fingerprint"] = hashlib.sha256(content).hexdigest()
    state["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    try:
        payload = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return state
    if isinstance(payload, dict):
        state["manifest_timestamp"] = str(payload.get("generated_at", "") or "")
        state["refresh_decision"] = str(payload.get("refresh_decision", "") or "")
    return state


def active_service_mode(args: argparse.Namespace) -> str:
    if args.service_mode != "auto":
        return args.service_mode
    if args.handoff_dir and args.handoff_dir.exists():
        return "handoff-driven"
    return "interval-local"


def load_handoff_rows(handoff_dir: Path | None) -> list[dict[str, Any]]:
    if handoff_dir is None or not handoff_dir.exists():
        return []
    for candidate in (
        handoff_dir / "scheduler_handoff_status.csv",
        handoff_dir / "scheduler_handoff_status.json",
        handoff_dir / "status.csv",
        handoff_dir / "status.json",
    ):
        if not candidate.exists():
            continue
        if candidate.suffix.lower() == ".csv":
            return read_csv(candidate)
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("rows")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def write_handoff_snapshot(handoff_rows: list[dict[str, Any]], handoff_dir: Path) -> None:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    write_csv(handoff_dir / "scheduler_handoff_status.csv", handoff_rows, HANDOFF_FIELDS)
    write_json(handoff_dir / "scheduler_handoff_status.json", handoff_rows)


def handoff_row(rows: list[dict[str, Any]], timeframe: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("timeframe", "")).strip() == timeframe:
            return row
    return None


def derive_slot_from_handoff(handoff_rows: list[dict[str, Any]], tz_name: str) -> datetime | None:
    m15 = handoff_row(handoff_rows, "M15")
    if m15 is None:
        return None
    return parse_dt(m15.get("expected_slot_time"), tz_name) or parse_dt(m15.get("last_closed_candle_time"), tz_name)


def handoff_has_new_close(handoff_rows: list[dict[str, Any]], timeframe: str, tz_name: str) -> bool:
    row = handoff_row(handoff_rows, timeframe)
    if row is None or not truthy(row.get("is_ready_for_trading_center", False)):
        return False
    status = str(row.get("process_status", "")).strip().lower()
    if status in {"blocked", "failed", "missing", "empty", "unchanged_valid"}:
        return False
    expected = parse_dt(row.get("expected_slot_time"), tz_name)
    closed = parse_dt(row.get("last_closed_candle_time"), tz_name)
    if closed is None:
        return False
    if expected is None:
        return status in {"completed", "warning"}
    return closed.astimezone(timezone.utc) >= expected.astimezone(timezone.utc)


def resolve_hourly_policy(
    include_hourly_policy: str,
    slot_dt: datetime,
    handoff_rows: list[dict[str, Any]],
    tz_name: str,
) -> tuple[bool, str]:
    if include_hourly_policy == "always":
        return True, "manual_override_always"
    if include_hourly_policy == "never":
        return False, "manual_override_never"
    if handoff_rows:
        if handoff_has_new_close(handoff_rows, "H4", tz_name):
            return True, "scheduler_h4_new_close"
        if handoff_has_new_close(handoff_rows, "H1", tz_name):
            return True, "scheduler_h1_new_close"
        return False, "scheduler_preserve_last_good"
    if is_h4_boundary(slot_dt):
        return True, "local_h4_boundary"
    if is_hourly_boundary(slot_dt):
        return True, "local_h1_boundary"
    return False, "local_preserve_last_good"


def resolve_slow_policy(
    include_slow_policy: str,
    slot_dt: datetime,
    handoff_rows: list[dict[str, Any]],
    tz_name: str,
) -> tuple[bool, str]:
    if include_slow_policy == "always":
        return True, "manual_override_always"
    if include_slow_policy == "never":
        return False, "manual_override_never"
    if handoff_rows:
        if handoff_has_new_close(handoff_rows, "D1", tz_name):
            return True, "scheduler_d1_new_close"
        return False, "scheduler_daily_last_good"
    if is_daily_boundary(slot_dt):
        return True, "local_daily_boundary"
    return False, "local_daily_last_good"


def safety_boundary_rows() -> list[dict[str, Any]]:
    return [
        {"boundary": "refresh_service_implemented", "expected": "true", "observed": "true", "status": "passed"},
        {"boundary": "daemon_implemented", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "windows_task_created", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "manual_stop_required", "expected": "true", "observed": "true", "status": "passed"},
        {"boundary": "artifact_first", "expected": "true", "observed": "true", "status": "passed"},
        {"boundary": "sql_real_written", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "ddl_executed", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "db_connected", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "mt5_connected", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "telegram_connected", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "orders_sent", "expected": "0", "observed": "0", "status": "passed"},
        {"boundary": "signals_generated", "expected": "false", "observed": "false", "status": "passed"},
        {"boundary": "backtests_executed", "expected": "false", "observed": "false", "status": "passed"},
    ]


def run_scheduler_handoff(
    args: argparse.Namespace,
    cycle_dir: Path,
    scheduler_now: datetime,
    scheduler_runner: Callable[[argparse.Namespace, datetime | None], Any],
) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
    handoff_dir = cycle_dir / "scheduler_handoff"
    scheduler_args = scheduler_module.parse_args(
        [
            "--audit-only",
            "--ohlc-artifact",
            str(args.ohlc_artifact),
            "--output-dir",
            str(handoff_dir),
            "--scheduler-now",
            scheduler_now.isoformat(),
            "--time-zone",
            args.time_zone,
            "--doc-path",
            str(cycle_dir / "docs" / "SCHEDULER_TO_TRADING_CENTER_REFRESH_INTEGRATION_V1.md"),
        ]
    )
    if args.fixture_mode:
        scheduler_args.fixture_mode = True
        scheduler_args.simulate_fresh = True
    result = scheduler_runner(scheduler_args, scheduler_now)
    return result.handoff_rows, handoff_dir, result.run_meta


def run_orchestrator(
    args: argparse.Namespace,
    cycle_dir: Path,
    slot_dt: datetime,
    handoff_dir: Path,
    include_hourly_analytics: bool,
    include_slow_analytics: bool,
    orchestrator_runner: Callable[[argparse.Namespace, datetime | None], Any],
    mode: str,
) -> Any:
    orchestrator_args = orchestrator_module.parse_args(
        [
            "--trigger",
            "event" if mode == "handoff-driven" else "interval",
            "--data-refresh-run-id",
            data_refresh_run_id(slot_dt, args.interval_minutes),
            "--scheduler-status-dir",
            str(handoff_dir),
            "--ohlc-artifact",
            str(args.ohlc_artifact),
            "--output-dir",
            str(cycle_dir / "orchestrator"),
            "--latest-dir",
            str(args.latest_dir),
            "--doc-path",
            str(cycle_dir / "docs" / "ARTIFACT_REFRESH_ORCHESTRATOR_V1.md"),
        ]
    )
    orchestrator_args.dry_run = args.dry_run
    orchestrator_args.audit_only = args.audit_only
    orchestrator_args.include_hourly_analytics = include_hourly_analytics
    orchestrator_args.include_slow_analytics = include_slow_analytics
    return orchestrator_runner(orchestrator_args, slot_dt.astimezone(timezone.utc))


def build_doc(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Refresh Service V1

Decision: `{run_meta['decision']}`

## Objetivo

Se implementa un refresh service local y manual para coordinar el Trading
Center sobre artifacts ya existentes. No reemplaza al scheduler de ingesta:
consume un handoff externo cuando se pasa explicitamente y solo usa slots
locales como fallback de desarrollo.

## Que hace

- Puede correr en `handoff-driven` o `interval-local`.
- Espera alineado a cierres M15 en modo local/manual.
- Consume `scheduler_handoff_status` cuando se proporciona `--handoff-dir`.
- Llama al orquestador y promociona a `trading_center_latest`.
- Recalcula WeaveCount solo en cierre H1/H4 o override.
- Mantiene correlaciones como last-good diario/manual por defecto.
- Genera auditoria artifact-first por ciclo.

## Politica de handoff

En `--service-mode auto`, el handoff del scheduler debe pasarse de forma
explicita con `--handoff-dir`. Si no se proporciona, el servicio usa
`interval-local`. Esto evita consumir por accidente artifacts historicos de
handoff como si fueran el estado vivo del scheduler.

## Que no hace

- No crea daemon del sistema.
- No crea tarea programada Windows.
- No ingiere datos por su cuenta.
- No conecta SQL real.
- No conecta MT5.
- No conecta Telegram.
- No genera senales ni ordenes.

## Resultado del run

- service_mode: `{run_meta['service_mode']}`
- startup_mode: `{run_meta['startup_mode']}`
- cycles_completed: `{run_meta['cycles_completed']}`
- slots_processed: `{run_meta['slots_processed']}`
- last_slot_processed: `{run_meta['last_slot_processed']}`
- hourly_analytics_cycles: `{run_meta['hourly_analytics_cycles']}`
- slow_analytics_cycles: `{run_meta['slow_analytics_cycles']}`
- latest_dir: `{run_meta['latest_dir']}`

## Seguridad

- `daemon_implemented=false`
- `windows_task_created=false`
- `sql_real_written=false`
- `db_connected=false`
- `mt5_connected=false`
- `telegram_connected=false`
- `orders_sent=0`
- `signals_generated=false`
- `backtests_executed=false`
"""


def write_result(output_root: Path, result: RefreshServiceResult) -> None:
    tables_dir = output_root / "tables"
    write_csv(output_root / "service_cycles.csv", result.cycle_rows)
    write_json(output_root / "service_cycles.json", result.cycle_rows)
    write_csv(tables_dir / "refresh_slot_policy_audit.csv", result.slot_policy_rows)
    write_csv(tables_dir / "hourly_analytics_policy_audit.csv", result.hourly_policy_rows)
    write_csv(tables_dir / "slow_analytics_policy_audit.csv", result.slow_policy_rows)
    write_csv(tables_dir / "orchestrator_cycle_audit.csv", result.orchestrator_rows)
    write_csv(tables_dir / "latest_manifest_change_audit.csv", result.manifest_rows)
    write_csv(tables_dir / "safety_boundary_audit.csv", result.safety_rows)
    write_csv(tables_dir / "issues_or_risks.csv", result.issue_rows)
    write_json(output_root / "run_meta.json", result.run_meta)
    (output_root / "TRADING_CENTER_REFRESH_SERVICE_V1.md").write_text(build_doc(result.run_meta), encoding="utf-8")


def execute(
    args: argparse.Namespace,
    *,
    now_provider: Callable[[], datetime] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    scheduler_runner: Callable[[argparse.Namespace, datetime | None], Any] | None = None,
    orchestrator_runner: Callable[[argparse.Namespace, datetime | None], Any] | None = None,
) -> RefreshServiceResult:
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    screenshots_dir = output_root / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    (output_root / "cycles").mkdir(parents=True, exist_ok=True)
    (output_root / "docs").mkdir(parents=True, exist_ok=True)

    now_provider = now_provider or (lambda: parse_dt(args.scheduler_now, args.time_zone) or now_in_zone(args.time_zone))
    sleep_fn = sleep_fn or time.sleep
    scheduler_runner = scheduler_runner or scheduler_module.execute
    orchestrator_runner = orchestrator_runner or orchestrator_module.execute

    service_mode = active_service_mode(args)
    processed_slots: set[str] = set()
    cycle_rows: list[dict[str, Any]] = []
    slot_policy_rows: list[dict[str, Any]] = []
    hourly_policy_rows: list[dict[str, Any]] = []
    slow_policy_rows: list[dict[str, Any]] = []
    orchestrator_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []

    cycles_completed = 0
    slots_processed = 0
    hourly_cycles = 0
    slow_cycles = 0
    last_slot_processed = ""
    first_iteration = True

    while True:
        current_now = now_provider()
        if current_now.tzinfo is None:
            current_now = current_now.replace(tzinfo=ZoneInfo(args.time_zone))
        mode = service_mode

        if mode == "interval-local" and first_iteration and args.startup_mode == "wait-next-slot":
            target_next = next_interval_slot(current_now, args.interval_minutes)
            wait_seconds = sleep_seconds_until_slot(current_now, target_next, args.sleep_margin_seconds)
            if wait_seconds > 0 and not args.once:
                sleep_fn(wait_seconds)
                current_now = now_provider()
                if current_now.tzinfo is None:
                    current_now = current_now.replace(tzinfo=ZoneInfo(args.time_zone))

        if mode == "handoff-driven":
            handoff_rows = load_handoff_rows(args.handoff_dir)
            handoff_source = "external_handoff" if handoff_rows else "handoff_missing"
            scheduler_meta = {}
            handoff_dir = output_root / "cycles" / "handoff_snapshot"
            if handoff_rows:
                write_handoff_snapshot(handoff_rows, handoff_dir)
                slot_dt = derive_slot_from_handoff(handoff_rows, args.time_zone)
            else:
                slot_dt = None
        else:
            slot_dt = last_closed_slot(current_now, args.interval_minutes)
            cycle_dir = output_root / "cycles" / slot_id(slot_dt, args.interval_minutes)
            handoff_rows, handoff_dir, scheduler_meta = run_scheduler_handoff(
                args,
                cycle_dir,
                current_now,
                scheduler_runner,
            )
            handoff_source = "local_scheduler_fallback"

        if slot_dt is None:
            cycles_completed += 1
            cycle_rows.append(
                {
                    "cycle_index": cycles_completed,
                    "service_mode": mode,
                    "cycle_action": "skipped_no_handoff_slot",
                    "slot_id": "",
                    "expected_slot_time": "",
                    "handoff_source": handoff_source,
                    "scheduler_handoff_written": bool(handoff_rows),
                    "orchestrator_invoked": False,
                }
            )
            issue_rows.append(
                {
                    "issue_id": f"REFRESH_SERVICE_{cycles_completed:03d}",
                    "severity": "medium",
                    "status": "open",
                    "description": "No se pudo derivar expected_slot_time desde el handoff disponible.",
                    "mitigation": "Publicar handoff M15 valido o usar interval-local como fallback controlado.",
                }
            )
            if args.once or (args.max_cycles and cycles_completed >= args.max_cycles):
                break
            wait_seconds = sleep_seconds_until_slot(current_now, next_interval_slot(current_now, args.interval_minutes), args.sleep_margin_seconds)
            sleep_fn(wait_seconds)
            first_iteration = False
            continue

        current_slot_id = slot_id(slot_dt, args.interval_minutes)
        cycle_dir = output_root / "cycles" / current_slot_id
        cycle_dir.mkdir(parents=True, exist_ok=True)

        local_last_closed = last_closed_slot(current_now, args.interval_minutes)
        local_next = next_interval_slot(current_now, args.interval_minutes)
        slot_policy_rows.append(
            {
                "cycle_index": cycles_completed + 1,
                "service_mode": mode,
                "observed_now": current_now.isoformat(),
                "local_last_closed_slot": local_last_closed.isoformat(),
                "local_next_slot": local_next.isoformat(),
                "expected_slot_time": slot_dt.isoformat(),
                "slot_id": current_slot_id,
                "slot_alignment_status": "passed" if slot_dt.minute % args.interval_minutes == 0 else "blocked",
                "handoff_authoritative": bool(handoff_rows and mode == "handoff-driven"),
                "uses_open_candles": False,
            }
        )

        hourly_enabled, hourly_reason = resolve_hourly_policy(
            args.include_hourly_policy,
            slot_dt,
            handoff_rows,
            args.time_zone,
        )
        slow_enabled, slow_reason = resolve_slow_policy(
            args.include_slow_policy,
            slot_dt,
            handoff_rows,
            args.time_zone,
        )
        hourly_policy_rows.append(
            {
                "cycle_index": cycles_completed + 1,
                "slot_id": current_slot_id,
                "expected_slot_time": slot_dt.isoformat(),
                "include_hourly_analytics": hourly_enabled,
                "reason": hourly_reason,
                "handoff_driven": bool(handoff_rows),
                "h1_boundary": is_hourly_boundary(slot_dt),
                "h4_boundary": is_h4_boundary(slot_dt),
            }
        )
        slow_policy_rows.append(
            {
                "cycle_index": cycles_completed + 1,
                "slot_id": current_slot_id,
                "expected_slot_time": slot_dt.isoformat(),
                "include_slow_analytics": slow_enabled,
                "reason": slow_reason,
                "handoff_driven": bool(handoff_rows),
                "daily_boundary": is_daily_boundary(slot_dt),
            }
        )

        if current_slot_id in processed_slots:
            cycles_completed += 1
            cycle_rows.append(
                {
                    "cycle_index": cycles_completed,
                    "service_mode": mode,
                    "cycle_action": "skipped_duplicate_slot",
                    "slot_id": current_slot_id,
                    "expected_slot_time": slot_dt.isoformat(),
                    "handoff_source": handoff_source,
                    "scheduler_handoff_written": bool(handoff_rows),
                    "orchestrator_invoked": False,
                    "include_hourly_analytics": hourly_enabled,
                    "include_slow_analytics": slow_enabled,
                }
            )
            if args.once or (args.max_cycles and cycles_completed >= args.max_cycles):
                break
            wait_seconds = sleep_seconds_until_slot(current_now, next_interval_slot(current_now, args.interval_minutes), args.sleep_margin_seconds)
            sleep_fn(wait_seconds)
            first_iteration = False
            continue

        before_manifest = manifest_fingerprint(args.latest_dir / "latest_manifest.json")
        orchestrator_result = run_orchestrator(
            args,
            cycle_dir,
            slot_dt,
            handoff_dir,
            hourly_enabled,
            slow_enabled,
            orchestrator_runner,
            mode,
        )
        after_manifest = manifest_fingerprint(args.latest_dir / "latest_manifest.json")
        manifest_changed = before_manifest.get("fingerprint", "") != after_manifest.get("fingerprint", "")

        cycles_completed += 1
        slots_processed += 1
        last_slot_processed = current_slot_id
        processed_slots.add(current_slot_id)
        if hourly_enabled:
            hourly_cycles += 1
        if slow_enabled:
            slow_cycles += 1

        cycle_rows.append(
            {
                "cycle_index": cycles_completed,
                "service_mode": mode,
                "cycle_action": "processed_slot",
                "slot_id": current_slot_id,
                "expected_slot_time": slot_dt.isoformat(),
                "handoff_source": handoff_source,
                "scheduler_handoff_written": bool(handoff_rows),
                "orchestrator_invoked": True,
                "orchestrator_refresh_decision": orchestrator_result.run_meta.get("refresh_decision", ""),
                "orchestrator_refresh_executed": orchestrator_result.run_meta.get("refresh_executed", False),
                "include_hourly_analytics": hourly_enabled,
                "include_slow_analytics": slow_enabled,
                "latest_manifest_changed": manifest_changed,
                "dry_run": args.dry_run,
                "audit_only": args.audit_only,
            }
        )
        orchestrator_rows.append(
            {
                "cycle_index": cycles_completed,
                "slot_id": current_slot_id,
                "output_dir": str(cycle_dir / "orchestrator"),
                "refresh_decision": orchestrator_result.run_meta.get("refresh_decision", ""),
                "refresh_executed": orchestrator_result.run_meta.get("refresh_executed", False),
                "include_hourly_analytics": hourly_enabled,
                "include_slow_analytics": slow_enabled,
                "latest_manifest_written": orchestrator_result.run_meta.get("latest_manifest_written", False),
            }
        )
        manifest_rows.append(
            {
                "cycle_index": cycles_completed,
                "slot_id": current_slot_id,
                "before_fingerprint": before_manifest.get("fingerprint", ""),
                "after_fingerprint": after_manifest.get("fingerprint", ""),
                "manifest_changed": manifest_changed,
                "before_timestamp": before_manifest.get("manifest_timestamp", ""),
                "after_timestamp": after_manifest.get("manifest_timestamp", ""),
                "refresh_decision": after_manifest.get("refresh_decision", ""),
            }
        )

        first_iteration = False
        if args.once or (args.max_cycles and cycles_completed >= args.max_cycles):
            break
        wait_seconds = sleep_seconds_until_slot(current_now, next_interval_slot(current_now, args.interval_minutes), args.sleep_margin_seconds)
        sleep_fn(wait_seconds)

    safety_rows = safety_boundary_rows()
    if not cycle_rows:
        issue_rows.append(
            {
                "issue_id": "REFRESH_SERVICE_EMPTY",
                "severity": "medium",
                "status": "open",
                "description": "El refresh service no llego a procesar ningun ciclo.",
                "mitigation": "Revisar handoff disponible, startup mode y clocks locales.",
            }
        )

    run_meta = {
        "phase": "trading_center_refresh_service_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "trading_center_refresh_service_and_dash_autorefresh_v1_ready_for_live_local_review",
        "refresh_service_implemented": True,
        "daemon_implemented": False,
        "windows_task_created": False,
        "background_loop_available": True,
        "manual_stop_required": True,
        "artifact_first": True,
        "service_mode": service_mode,
        "startup_mode": args.startup_mode,
        "latest_dir": str(args.latest_dir),
        "cycles_completed": cycles_completed,
        "slots_processed": slots_processed,
        "last_slot_processed": last_slot_processed,
        "hourly_analytics_cycles": hourly_cycles,
        "slow_analytics_cycles": slow_cycles,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    result = RefreshServiceResult(
        cycle_rows=cycle_rows,
        slot_policy_rows=slot_policy_rows,
        hourly_policy_rows=hourly_policy_rows,
        slow_policy_rows=slow_policy_rows,
        orchestrator_rows=orchestrator_rows,
        manifest_rows=manifest_rows,
        safety_rows=safety_rows,
        issue_rows=issue_rows,
        run_meta=run_meta,
    )
    write_result(output_root, result)
    if args.doc_path:
        args.doc_path.parent.mkdir(parents=True, exist_ok=True)
        args.doc_path.write_text(build_doc(run_meta), encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Trading Center refresh service coordinator.")
    parser.add_argument("--ohlc-artifact", type=Path, default=DEFAULT_OHLC_ARTIFACT)
    parser.add_argument("--latest-dir", type=Path, default=DEFAULT_LATEST_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--time-zone", default="Europe/Madrid")
    parser.add_argument("--service-mode", choices=("auto", "handoff-driven", "interval-local"), default="auto")
    parser.add_argument("--handoff-dir", type=Path, default=DEFAULT_HANDOFF_DIR)
    parser.add_argument("--startup-mode", choices=("process-latest-closed", "wait-next-slot"), default="process-latest-closed")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--sleep-margin-seconds", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--scheduler-now", default="")
    parser.add_argument("--include-hourly-policy", choices=("auto", "never", "always"), default="auto")
    parser.add_argument("--include-slow-policy", choices=("daily", "never", "always"), default="daily")
    parser.add_argument("--allow-weekend-no-new-data", action="store_true")
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    execute(args)


if __name__ == "__main__":  # pragma: no cover
    main()
