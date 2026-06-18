from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from trading_center.refresh_service import (
    active_service_mode,
    execute,
    last_closed_slot,
    next_interval_slot,
    parse_args,
)


MADRID = ZoneInfo("Europe/Madrid")


def make_handoff_rows(
    slot_dt: datetime,
    *,
    h1_new: bool = False,
    h4_new: bool = False,
    d1_new: bool = False,
) -> list[dict[str, object]]:
    rows = []
    for timeframe in ("M15", "H1", "H4", "D1"):
        expected = slot_dt
        if timeframe == "H1":
            expected = slot_dt.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "H4":
            expected = slot_dt.replace(hour=(slot_dt.hour // 4) * 4, minute=0, second=0, microsecond=0)
        elif timeframe == "D1":
            expected = slot_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        new_close = {
            "M15": True,
            "H1": h1_new,
            "H4": h4_new,
            "D1": d1_new,
        }[timeframe]
        rows.append(
            {
                "timeframe": timeframe,
                "expected_slot_time": expected.isoformat(),
                "last_closed_candle_time": expected.isoformat(),
                "process_status": "completed" if new_close else "unchanged_valid",
                "is_ready_for_trading_center": True,
            }
        )
    return rows


def scheduler_stub(handoff_rows: list[dict[str, object]], calls: list[datetime]):
    def _runner(args, scheduler_now):
        calls.append(scheduler_now)
        return SimpleNamespace(handoff_rows=handoff_rows, run_meta={"scheduler_refresh_integration_implemented": True})

    return _runner


def orchestrator_stub(calls: list[dict[str, object]], latest_dir: Path | None = None):
    def _runner(args, now=None):
        calls.append(
            {
                "output_dir": args.output_dir,
                "dry_run": args.dry_run,
                "audit_only": args.audit_only,
                "include_hourly_analytics": args.include_hourly_analytics,
                "include_slow_analytics": args.include_slow_analytics,
            }
        )
        if latest_dir is not None:
            latest_dir.mkdir(parents=True, exist_ok=True)
            (latest_dir / "latest_manifest.json").write_text(
                json.dumps({"generated_at": "2026-06-06T10:00:00+00:00", "refresh_decision": "refresh_allowed"}),
                encoding="utf-8",
            )
        return SimpleNamespace(
            run_meta={
                "refresh_decision": "refresh_allowed",
                "refresh_executed": not args.dry_run and not args.audit_only,
                "latest_manifest_written": latest_dir is not None,
                "sql_real_written": False,
                "mt5_connected": False,
                "telegram_connected": False,
                "signals_generated": False,
                "backtests_executed": False,
            }
        )

    return _runner


def test_slot_m15_1003_to_1000() -> None:
    now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)
    assert last_closed_slot(now, 15) == datetime(2026, 6, 6, 10, 0, tzinfo=MADRID)


def test_next_slot_1003_to_1015() -> None:
    now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)
    assert next_interval_slot(now, 15) == datetime(2026, 6, 6, 10, 15, tzinfo=MADRID)


def test_auto_sin_handoff_explicito_usa_interval_local() -> None:
    args = parse_args([])

    assert args.handoff_dir is None
    assert active_service_mode(args) == "interval-local"


def test_auto_con_handoff_explicito_usa_handoff_driven(tmp_path: Path) -> None:
    handoff_dir = tmp_path / "handoff"
    handoff_dir.mkdir()
    args = parse_args(["--handoff-dir", str(handoff_dir)])

    assert active_service_mode(args) == "handoff-driven"


def test_no_procesa_dos_veces_el_mismo_slot(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)
    handoff = make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID))
    scheduler_calls: list[datetime] = []
    orchestrator_calls: list[dict[str, object]] = []
    args = parse_args(
        [
            "--output-root",
            str(output_root),
            "--latest-dir",
            str(latest_dir),
            "--service-mode",
            "interval-local",
            "--max-cycles",
            "2",
        ]
    )
    result = execute(
        args,
        now_provider=lambda: now,
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(handoff, scheduler_calls),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert result.run_meta["cycles_completed"] == 2
    assert result.run_meta["slots_processed"] == 1
    assert len(orchestrator_calls) == 1
    assert result.cycle_rows[1]["cycle_action"] == "skipped_duplicate_slot"


def test_once_ejecuta_un_ciclo_y_termina(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)
    handoff = make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID))
    orchestrator_calls: list[dict[str, object]] = []
    args = parse_args(
        [
            "--output-root",
            str(output_root),
            "--latest-dir",
            str(latest_dir),
            "--service-mode",
            "interval-local",
            "--once",
        ]
    )
    result = execute(
        args,
        now_provider=lambda: now,
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(handoff, []),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert result.run_meta["cycles_completed"] == 1
    assert len(orchestrator_calls) == 1


def test_max_cycles_2_termina_tras_dos_ciclos(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    now_values = [
        datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        datetime(2026, 6, 6, 10, 18, tzinfo=MADRID),
    ]
    iterator = iter(now_values)
    handoff_first = make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID))
    handoff_second = make_handoff_rows(datetime(2026, 6, 6, 10, 15, tzinfo=MADRID))
    handoffs = iter([handoff_first, handoff_second])
    orchestrator_calls: list[dict[str, object]] = []

    def scheduler_runner(args, scheduler_now):
        return SimpleNamespace(handoff_rows=next(handoffs), run_meta={})

    result = execute(
        parse_args(
            [
                "--output-root",
                str(output_root),
                "--latest-dir",
                str(latest_dir),
                "--service-mode",
                "interval-local",
                "--max-cycles",
                "2",
            ]
        ),
        now_provider=lambda: next(iterator, now_values[-1]),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_runner,
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert result.run_meta["cycles_completed"] == 2
    assert result.run_meta["slots_processed"] == 2
    assert len(orchestrator_calls) == 2


def test_cierre_h1_activa_hourly_analytics(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest"
    slot_dt = datetime(2026, 6, 6, 11, 0, tzinfo=MADRID)
    orchestrator_calls: list[dict[str, object]] = []
    result = execute(
        parse_args(["--output-root", str(tmp_path / "out"), "--latest-dir", str(latest_dir), "--once", "--service-mode", "interval-local"]),
        now_provider=lambda: datetime(2026, 6, 6, 11, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(slot_dt, h1_new=True), []),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert orchestrator_calls[0]["include_hourly_analytics"] is True
    assert result.hourly_policy_rows[0]["reason"] == "scheduler_h1_new_close"


def test_cierre_h4_activa_hourly_analytics(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest"
    slot_dt = datetime(2026, 6, 6, 12, 0, tzinfo=MADRID)
    orchestrator_calls: list[dict[str, object]] = []
    result = execute(
        parse_args(["--output-root", str(tmp_path / "out"), "--latest-dir", str(latest_dir), "--once", "--service-mode", "interval-local"]),
        now_provider=lambda: datetime(2026, 6, 6, 12, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(slot_dt, h4_new=True), []),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert orchestrator_calls[0]["include_hourly_analytics"] is True
    assert result.hourly_policy_rows[0]["reason"] == "scheduler_h4_new_close"


def test_m15_no_h1_h4_no_activa_hourly_analytics(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest"
    slot_dt = datetime(2026, 6, 6, 10, 15, tzinfo=MADRID)
    orchestrator_calls: list[dict[str, object]] = []
    result = execute(
        parse_args(["--output-root", str(tmp_path / "out"), "--latest-dir", str(latest_dir), "--once", "--service-mode", "interval-local"]),
        now_provider=lambda: datetime(2026, 6, 6, 10, 16, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(slot_dt), []),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert orchestrator_calls[0]["include_hourly_analytics"] is False
    assert result.hourly_policy_rows[0]["reason"] == "scheduler_preserve_last_good"


def test_correlaciones_quedan_last_good_por_defecto(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest"
    orchestrator_calls: list[dict[str, object]] = []
    execute(
        parse_args(["--output-root", str(tmp_path / "out"), "--latest-dir", str(latest_dir), "--once"]),
        now_provider=lambda: datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID)), []),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert orchestrator_calls[0]["include_slow_analytics"] is False


def test_include_slow_policy_always_activa_slow_analytics(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest"
    orchestrator_calls: list[dict[str, object]] = []
    execute(
        parse_args(
            [
                "--output-root",
                str(tmp_path / "out"),
                "--latest-dir",
                str(latest_dir),
                "--once",
                "--include-slow-policy",
                "always",
            ]
        ),
        now_provider=lambda: datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID)), []),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert orchestrator_calls[0]["include_slow_analytics"] is True


def test_genera_service_cycles_csv_y_json(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    execute(
        parse_args(["--output-root", str(output_root), "--latest-dir", str(latest_dir), "--once"]),
        now_provider=lambda: datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID)), []),
        orchestrator_runner=orchestrator_stub([], latest_dir=latest_dir),
    )

    assert (output_root / "service_cycles.csv").exists()
    assert (output_root / "service_cycles.json").exists()
    assert (output_root / "run_meta.json").exists()


def test_invoca_scheduler_y_orchestrator_en_dry_run_fixture(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    scheduler_calls: list[datetime] = []
    orchestrator_calls: list[dict[str, object]] = []
    execute(
        parse_args(
            [
                "--output-root",
                    str(output_root),
                    "--latest-dir",
                    str(latest_dir),
                    "--once",
                    "--dry-run",
                    "--fixture-mode",
                    "--service-mode",
                    "interval-local",
                ]
            ),
        now_provider=lambda: datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID)), scheduler_calls),
        orchestrator_runner=orchestrator_stub(orchestrator_calls),
    )

    assert len(scheduler_calls) == 1
    assert len(orchestrator_calls) == 1
    assert orchestrator_calls[0]["dry_run"] is True


def test_handoff_driven_respeta_handoff_real_y_no_recalcula_slot_local(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    handoff_dir = tmp_path / "handoff"
    handoff_dir.mkdir(parents=True)
    expected_slot = datetime(2026, 6, 6, 10, 15, tzinfo=MADRID)
    rows = make_handoff_rows(expected_slot, h1_new=True)
    with (handoff_dir / "scheduler_handoff_status.json").open("w", encoding="utf-8") as handle:
        json.dump(rows, handle)

    result = execute(
        parse_args(
            [
                "--output-root",
                str(output_root),
                "--latest-dir",
                str(latest_dir),
                "--service-mode",
                "handoff-driven",
                "--handoff-dir",
                str(handoff_dir),
                "--once",
            ]
        ),
        now_provider=lambda: datetime(2026, 6, 6, 10, 16, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub([], []),
        orchestrator_runner=orchestrator_stub([]),
    )

    assert result.slot_policy_rows[0]["handoff_authoritative"] is True
    assert result.cycle_rows[0]["expected_slot_time"] == expected_slot.isoformat()


def test_run_meta_fail_closed(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    execute(
        parse_args(["--output-root", str(output_root), "--latest-dir", str(latest_dir), "--once"]),
        now_provider=lambda: datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        sleep_fn=lambda _seconds: None,
        scheduler_runner=scheduler_stub(make_handoff_rows(datetime(2026, 6, 6, 10, 0, tzinfo=MADRID)), []),
        orchestrator_runner=orchestrator_stub([]),
    )
    meta = json.loads((output_root / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["refresh_service_implemented"] is True
    assert meta["daemon_implemented"] is False
    assert meta["windows_task_created"] is False
    assert meta["sql_real_written"] is False
    assert meta["db_connected"] is False
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False
    assert meta["backtests_executed"] is False
