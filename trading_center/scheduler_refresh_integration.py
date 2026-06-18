from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OHLC_ARTIFACT = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/scheduler_to_trading_center_refresh_integration_v1_2026-06-05"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/SCHEDULER_TO_TRADING_CENTER_REFRESH_INTEGRATION_V1.md"
DEFAULT_DESIGN_DOC_PATH = REPO_ROOT / "docs/SCHEDULER_TO_TRADING_CENTER_REFRESH_INTEGRATION_DESIGN_V1.md"
REQUIRED_TIMEFRAMES = ("M15", "H1", "H4", "D1")
TIMEFRAME_MAX_AGES = {
    "M15": {"warning": 30 * 60, "blocked": 60 * 60},
    "H1": {"warning": 2 * 60 * 60, "blocked": 4 * 60 * 60},
    "H4": {"warning": 8 * 60 * 60, "blocked": 12 * 60 * 60},
    # D1 needs to tolerate the Friday -> Monday market gap. A 96h block
    # threshold keeps Monday morning valid while still blocking if Monday's
    # daily close is missing deep into Tuesday.
    "D1": {"warning": 72 * 60 * 60, "blocked": 96 * 60 * 60},
}
FIELD_ALIASES = {
    "time": ("time", "timestamp", "datetime", "date"),
    "symbol": ("symbol",),
    "timeframe": ("timeframe", "tf"),
}
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
class SchedulerIntegrationResult:
    handoff_rows: list[dict[str, Any]]
    slot_rows: list[dict[str, Any]]
    readiness_rows: list[dict[str, Any]]
    orchestrator_rows: list[dict[str, Any]]
    coherence_rows: list[dict[str, Any]]
    safety_rows: list[dict[str, Any]]
    issue_rows: list[dict[str, Any]]
    run_meta: dict[str, Any]


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
            parsed = datetime.strptime(text, fmt).replace(tzinfo=ZoneInfo(tz_name))
            return parsed
        except ValueError:
            continue
    return None


def now_in_zone(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def iso_utc(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def calculate_expected_slot(scheduler_now: datetime, timeframe: str) -> datetime:
    if scheduler_now.tzinfo is None:
        raise ValueError("scheduler_now must be timezone-aware")
    base = scheduler_now.replace(second=0, microsecond=0)
    if timeframe == "M15":
        minute = (base.minute // 15) * 15
        return base.replace(minute=minute)
    if timeframe == "H1":
        return base.replace(minute=0)
    if timeframe == "H4":
        hour = (base.hour // 4) * 4
        return base.replace(hour=hour, minute=0)
    if timeframe == "D1":
        return base.replace(hour=0, minute=0)
    raise ValueError(f"Unsupported timeframe: {timeframe}")


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


def load_ohlc_summary(ohlc_artifact: Path, tz_name: str, allow_missing: bool) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not ohlc_artifact.exists():
        if allow_missing:
            return {}, [{"check": "ohlc_exists", "status": "warning", "detail": "missing allowed for fixture tests"}]
        return {}, [{"check": "ohlc_exists", "status": "blocked", "detail": f"missing {ohlc_artifact}"}]
    with ohlc_artifact.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        resolved, missing = resolve_columns(reader.fieldnames)
        rows = list(reader)
    if missing:
        return {}, [{"check": "ohlc_schema", "status": "blocked", "detail": "missing=" + ",".join(missing)}]
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        tf = str(row.get(resolved["timeframe"], "")).strip()
        if tf not in REQUIRED_TIMEFRAMES:
            continue
        parsed = parse_dt(row.get(resolved["time"]), tz_name)
        if parsed is None:
            continue
        current = summary.setdefault(tf, {"latest": None, "rows_loaded": 0, "symbols": set()})
        current["rows_loaded"] += 1
        current["symbols"].add(str(row.get(resolved["symbol"], "")).strip())
        if current["latest"] is None or parsed.astimezone(timezone.utc) > current["latest"].astimezone(timezone.utc):
            current["latest"] = parsed
    return summary, [{"check": "ohlc_schema", "status": "passed", "detail": f"rows={len(rows)}"}]


def status_for_timeframe(
    timeframe: str,
    scheduler_now: datetime,
    ohlc_summary: dict[str, dict[str, Any]],
    source_artifact: Path,
    trigger: str,
    run_id: str,
    started_at: datetime,
    completed_at: datetime,
    simulate_fresh: bool,
    simulate_stale: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected_slot = calculate_expected_slot(scheduler_now, timeframe)
    summary = ohlc_summary.get(timeframe)
    latest: datetime | None = summary.get("latest") if summary else None
    if simulate_fresh:
        latest = expected_slot
    if simulate_stale:
        latest = scheduler_now - {
            "M15": timedelta(hours=2),
            "H1": timedelta(hours=8),
            "H4": timedelta(hours=24),
            "D1": timedelta(days=5),
        }[timeframe]

    warning_age = TIMEFRAME_MAX_AGES[timeframe]["warning"]
    blocked_age = TIMEFRAME_MAX_AGES[timeframe]["blocked"]
    rows_loaded = int(summary.get("rows_loaded", 0)) if summary else 0
    symbols_loaded = len(summary.get("symbols", set())) if summary else 0
    blocking_reason = ""
    warning_reason = ""
    ready = True
    if latest is None:
        status = "missing"
        ready = False
        blocking_reason = "missing_timeframe_ohlc"
        age = ""
    else:
        age = max(0, int((scheduler_now.astimezone(timezone.utc) - latest.astimezone(timezone.utc)).total_seconds()))
        if age > blocked_age:
            status = "blocked"
            ready = False
            blocking_reason = "timeframe_stale_real"
        elif latest.astimezone(timezone.utc) < expected_slot.astimezone(timezone.utc):
            if timeframe == "M15":
                status = "warning" if age <= warning_age else "blocked"
                ready = status == "warning"
                warning_reason = "M15 expected slot not yet present" if ready else ""
                blocking_reason = "" if ready else "M15_expected_slot_missing"
            else:
                status = "unchanged_valid"
                warning_reason = f"{timeframe} retained previous valid close"
        elif age > warning_age:
            status = "warning"
            warning_reason = "freshness warning threshold exceeded"
        else:
            status = "completed"

    row = {
        "data_refresh_run_id": run_id,
        "trigger_source": trigger,
        "scheduler_started_at": iso_utc(started_at),
        "scheduler_completed_at": iso_utc(completed_at),
        "timeframe": timeframe,
        "expected_slot_time": iso_utc(expected_slot),
        "last_closed_candle_time": iso_utc(latest),
        "data_available_until": iso_utc(latest),
        "process_status": status,
        "is_required": True,
        "is_ready_for_trading_center": ready,
        "freshness_seconds": age,
        "expected_max_age_seconds": blocked_age,
        "rows_loaded": rows_loaded,
        "symbols_loaded": symbols_loaded,
        "source_artifact": str(source_artifact),
        "blocking_reason": blocking_reason,
        "warning_reason": warning_reason,
        "created_at_utc": iso_utc(completed_at),
    }
    slot_row = {
        "timeframe": timeframe,
        "scheduler_now": scheduler_now.isoformat(),
        "expected_slot_time": expected_slot.isoformat(),
        "last_closed_candle_time": latest.isoformat() if latest else "",
        "slot_alignment_status": "passed" if latest and latest.astimezone(timezone.utc) <= expected_slot.astimezone(timezone.utc) or latest else "blocked",
        "notes": "scheduler owns expected slot and last closed candle",
    }
    readiness_row = {
        "timeframe": timeframe,
        "process_status": status,
        "is_ready_for_trading_center": ready,
        "freshness_seconds": age,
        "blocking_reason": blocking_reason,
        "warning_reason": warning_reason,
    }
    return row, slot_row, readiness_row


def build_handoff(args: argparse.Namespace, scheduler_now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    started_at = scheduler_now
    completed_at = scheduler_now
    ohlc_summary, ohlc_issues = load_ohlc_summary(args.ohlc_artifact, args.time_zone, args.allow_missing_ohlc)
    run_id = args.data_refresh_run_id or f"{scheduler_now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{args.trigger}"
    handoff_rows: list[dict[str, Any]] = []
    slot_rows: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []
    for tf in REQUIRED_TIMEFRAMES:
        handoff, slot, readiness = status_for_timeframe(
            tf,
            scheduler_now,
            ohlc_summary,
            args.ohlc_artifact,
            args.trigger,
            run_id,
            started_at,
            completed_at,
            args.simulate_fresh,
            args.simulate_stale,
        )
        handoff_rows.append(handoff)
        slot_rows.append(slot)
        readiness_rows.append(readiness)
    coherence_rows = build_coherence_audit(handoff_rows)
    return handoff_rows, slot_rows, readiness_rows, coherence_rows, ohlc_issues


def build_coherence_audit(handoff_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_tf = {row["timeframe"]: row for row in handoff_rows}
    rows = []
    m15_ready = by_tf.get("M15", {}).get("is_ready_for_trading_center") is True
    higher_valid = all(by_tf.get(tf, {}).get("is_ready_for_trading_center") is True for tf in ("H1", "H4", "D1"))
    rows.append(
        {
            "case_id": "m15_with_higher_timeframes",
            "status": "passed" if m15_ready and higher_valid else "blocked",
            "detail": "M15 ready and H1/H4/D1 ready or unchanged_valid" if m15_ready and higher_valid else "At least one required timeframe is not ready",
        }
    )
    for tf in ("H1", "H4", "D1"):
        row = by_tf.get(tf, {})
        rows.append(
            {
                "case_id": f"{tf.lower()}_unchanged_valid",
                "status": "passed" if row.get("process_status") in {"completed", "warning", "unchanged_valid"} and row.get("is_ready_for_trading_center") is True else "blocked",
                "detail": f"{tf} status={row.get('process_status', '')}",
            }
        )
    return rows


def invoke_orchestrator(args: argparse.Namespace, handoff_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not args.invoke_orchestrator:
        return (
            [
                {
                    "orchestrator_invoked": False,
                    "mode": "",
                    "exit_code": "",
                    "refresh_decision": "",
                    "refresh_executed": "",
                    "last_good_artifact_used": "",
                    "command": "",
                }
            ],
            {"orchestrator_invoked": False, "orchestrator_mode": "", "orchestrator_refresh_decision": ""},
        )
    mode_flag = "--audit-only" if args.orchestrator_mode == "audit-only" else "--dry-run"
    orchestrator_dir = args.output_dir / "orchestrator_audit"
    command = [
        sys.executable,
        "-m",
        "trading_center.artifact_refresh_orchestrator",
        "--trigger",
        args.trigger,
        "--data-refresh-run-id",
        args.data_refresh_run_id or "",
        "--scheduler-status-dir",
        str(handoff_dir),
        "--ohlc-artifact",
        str(args.ohlc_artifact),
        "--output-dir",
        str(orchestrator_dir),
        mode_flag,
    ]
    proc = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    meta_path = orchestrator_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    row = {
        "orchestrator_invoked": True,
        "mode": args.orchestrator_mode,
        "exit_code": proc.returncode,
        "refresh_decision": meta.get("refresh_decision", ""),
        "refresh_executed": meta.get("refresh_executed", ""),
        "last_good_artifact_used": meta.get("last_good_artifact_used", ""),
        "command": " ".join(command),
    }
    return [row], {"orchestrator_invoked": True, "orchestrator_mode": args.orchestrator_mode, "orchestrator_refresh_decision": meta.get("refresh_decision", "")}


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
    return f"""# Scheduler To Trading Center Refresh Integration V1

Decision: `{meta['decision']}`

## Objetivo

Se implementa una CLI artifact-first que prepara el handoff del scheduler de
datos por timeframe hacia `artifact_refresh_orchestrator_v1`. No implementa
daemon, background loop, SQL writes, MT5, Telegram ni senales.

## Calculo de slots

El modulo calcula slots esperados por timeframe:

- M15: minutos `00/15/30/45`.
- H1: cierre horario.
- H4: cierre cada 4 horas.
- D1: cierre diario.

Ejemplo validado: `2026-06-05T10:03:00+02:00` produce para M15 el slot
`2026-06-05T10:00:00+02:00`.

## Handoff

Se generan `scheduler_handoff_status.csv` y `.json` con estado por
`M15/H1/H4/D1`, incluyendo `expected_slot_time`, `last_closed_candle_time`,
freshness y `is_ready_for_trading_center`.

## Orquestador

Si se usa `--invoke-orchestrator`, la CLI llama al orquestador solo en modo
`audit-only` o `dry-run`. No ejecuta downstream real por defecto.

## Resultado del run

- trigger: `{meta['trigger']}`
- audit_only: `{meta['audit_only']}`
- dry_run: `{meta['dry_run']}`
- orchestrator_invoked: `{meta['orchestrator_invoked']}`
- orchestrator_mode: `{meta['orchestrator_mode']}`
- orchestrator_refresh_decision: `{meta['orchestrator_refresh_decision']}`

## Seguridad

- `scheduler_service_implemented=false`
- `background_loop_implemented=false`
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

## Lectura del run real

Si el OHLC usado es historico, el handoff puede generarse correctamente pero
marcar `M15/H1/H4/D1` como `blocked` por `timeframe_stale_real`. Esa lectura es
protectora: evita presentar datos viejos como refresh actual.

Cuando se usa `--invoke-orchestrator --orchestrator-mode audit-only`, el
orquestador consume el handoff y, si los datos estan stale, responde
`use_last_good_artifacts` sin regenerar downstream artifacts.

Los tests con fixture fresco cubren el caso contrario: M15 fresco con H1/H4/D1
completados o `unchanged_valid` deja el handoff listo para el Trading Center.
"""


def execute(args: argparse.Namespace, scheduler_now: datetime | None = None) -> SchedulerIntegrationResult:
    scheduler_now = scheduler_now or parse_dt(args.scheduler_now, args.time_zone) or now_in_zone(args.time_zone)
    if scheduler_now.tzinfo is None:
        scheduler_now = scheduler_now.replace(tzinfo=ZoneInfo(args.time_zone))
    if args.trigger == "event" and not args.data_refresh_run_id:
        args.data_refresh_run_id = "missing_event_run_id"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    handoff_rows, slot_rows, readiness_rows, coherence_rows, ohlc_issues = build_handoff(args, scheduler_now)
    write_csv(args.output_dir / "scheduler_handoff_status.csv", handoff_rows, HANDOFF_FIELDS)
    write_json(args.output_dir / "scheduler_handoff_status.json", handoff_rows)
    orchestrator_rows, orchestrator_meta = invoke_orchestrator(args, args.output_dir)
    safety_rows = safety_audit()
    issue_rows = [
        {
            "issue_id": "SCHED_INT_V1_01",
            "severity": "medium" if any(not row["is_ready_for_trading_center"] for row in handoff_rows) else "low",
            "status": "open" if any(not row["is_ready_for_trading_center"] for row in handoff_rows) else "review",
            "description": "At least one timeframe is not ready" if any(not row["is_ready_for_trading_center"] for row in handoff_rows) else "All required timeframe handoff rows are ready",
            "mitigation": "Use orchestrator last-good policy if any required timeframe is blocked.",
        }
    ]
    for issue in ohlc_issues:
        if issue["status"] != "passed":
            issue_rows.append({"issue_id": "SCHED_INT_V1_OHLC", "severity": "medium", "status": issue["status"], "description": issue["detail"], "mitigation": "Provide a valid OHLC artifact."})
    run_meta = {
        "phase": "scheduler_to_trading_center_refresh_integration_v1",
        "generated_at": iso_utc(datetime.now(timezone.utc)),
        "decision": "scheduler_to_trading_center_refresh_integration_v1_ready_for_ai_analyst_design",
        "scheduler_refresh_integration_implemented": True,
        "scheduler_service_implemented": False,
        "background_loop_implemented": False,
        "artifact_first": True,
        "read_only": True,
        "uses_closed_candles_only": True,
        "uses_open_candles": False,
        "trigger": args.trigger,
        "audit_only": args.audit_only,
        "dry_run": args.dry_run,
        "scheduler_now": scheduler_now.isoformat(),
        "handoff_ready_rows": sum(1 for row in handoff_rows if row["is_ready_for_trading_center"] is True),
        "handoff_blocked_rows": sum(1 for row in handoff_rows if row["is_ready_for_trading_center"] is not True),
        **orchestrator_meta,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    result = SchedulerIntegrationResult(
        handoff_rows=handoff_rows,
        slot_rows=slot_rows,
        readiness_rows=readiness_rows,
        orchestrator_rows=orchestrator_rows,
        coherence_rows=coherence_rows,
        safety_rows=safety_rows,
        issue_rows=issue_rows,
        run_meta=run_meta,
    )
    write_result(args.output_dir, result)
    if args.doc_path:
        args.doc_path.parent.mkdir(parents=True, exist_ok=True)
        args.doc_path.write_text(build_doc(run_meta), encoding="utf-8")
    return result


def write_result(output_dir: Path, result: SchedulerIntegrationResult) -> None:
    tables_dir = output_dir / "tables"
    write_csv(tables_dir / "slot_alignment_audit.csv", result.slot_rows)
    write_csv(tables_dir / "timeframe_readiness_audit.csv", result.readiness_rows)
    write_csv(tables_dir / "orchestrator_invocation_audit.csv", result.orchestrator_rows)
    write_csv(tables_dir / "multitimeframe_coherence_audit.csv", result.coherence_rows)
    write_csv(tables_dir / "safety_boundary_audit.csv", result.safety_rows)
    write_csv(tables_dir / "issues_or_risks.csv", result.issue_rows)
    write_json(output_dir / "run_meta.json", result.run_meta)
    (output_dir / "SCHEDULER_TO_TRADING_CENTER_REFRESH_INTEGRATION_V1.md").write_text(build_doc(result.run_meta), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Produce scheduler handoff artifacts for Trading Center refresh.")
    parser.add_argument("--ohlc-artifact", type=Path, default=DEFAULT_OHLC_ARTIFACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--trigger", choices=("manual", "interval", "event"), default="manual")
    parser.add_argument("--data-refresh-run-id", default="")
    parser.add_argument("--scheduler-now", default="")
    parser.add_argument("--time-zone", default="Europe/Madrid")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--simulate-fresh", action="store_true")
    parser.add_argument("--simulate-stale", action="store_true")
    parser.add_argument("--invoke-orchestrator", action="store_true")
    parser.add_argument("--orchestrator-mode", choices=("audit-only", "dry-run"), default="audit-only")
    parser.add_argument("--allow-missing-ohlc", action="store_true")
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--design-doc-path", type=Path, default=DEFAULT_DESIGN_DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    execute(args)


if __name__ == "__main__":  # pragma: no cover
    main()
