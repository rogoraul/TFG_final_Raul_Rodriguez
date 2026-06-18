from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_center.scheduler_refresh_integration import calculate_expected_slot, execute, parse_args


MADRID = ZoneInfo("Europe/Madrid")


def write_ohlc(path: Path, now: datetime, *, stale: str | None = None, missing: tuple[str, ...] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    times = {
        "M15": calculate_expected_slot(now, "M15"),
        "H1": calculate_expected_slot(now, "H1"),
        "H4": calculate_expected_slot(now, "H4"),
        "D1": calculate_expected_slot(now, "D1"),
    }
    for tf, ts in times.items():
        if tf in missing:
            continue
        if stale == tf:
            ts = now - {"M15": timedelta(hours=2), "H1": timedelta(hours=8), "H4": timedelta(days=1), "D1": timedelta(days=5)}[tf]
        for symbol in ("EURUSD.r", "GBPUSD.r"):
            rows.append(
                {
                    "market_group": "Forex Majors",
                    "symbol": symbol,
                    "timeframe": tf,
                    "timestamp": ts.isoformat(),
                    "open": "1.0",
                    "high": "1.1",
                    "low": "0.9",
                    "close": "1.05",
                }
            )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def meta(path: Path) -> dict:
    return json.loads((path / "run_meta.json").read_text(encoding="utf-8"))


def test_slot_m15_1003_to_1000() -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    assert calculate_expected_slot(now, "M15") == datetime(2026, 6, 5, 10, 0, tzinfo=MADRID)


def test_slot_h1_h4_d1() -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    assert calculate_expected_slot(now, "H1") == datetime(2026, 6, 5, 10, 0, tzinfo=MADRID)
    assert calculate_expected_slot(now, "H4") == datetime(2026, 6, 5, 8, 0, tzinfo=MADRID)
    assert calculate_expected_slot(now, "D1") == datetime(2026, 6, 5, 0, 0, tzinfo=MADRID)


def test_cli_audit_only_generates_handoff(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    out = tmp_path / "out"
    write_ohlc(ohlc, now)
    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(out), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args)

    assert (out / "scheduler_handoff_status.csv").exists()
    assert (out / "scheduler_handoff_status.json").exists()
    assert all(field in result.handoff_rows[0] for field in ("data_refresh_run_id", "expected_slot_time", "last_closed_candle_time", "is_ready_for_trading_center"))
    assert meta(out)["scheduler_refresh_integration_implemented"] is True


def test_m15_fresh_allows_ready(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    result = execute(parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    m15 = next(row for row in result.handoff_rows if row["timeframe"] == "M15")
    assert m15["process_status"] == "completed"
    assert m15["is_ready_for_trading_center"] is True


def test_m15_stale_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now, stale="M15")
    result = execute(parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    m15 = next(row for row in result.handoff_rows if row["timeframe"] == "M15")
    assert m15["process_status"] == "blocked"
    assert m15["is_ready_for_trading_center"] is False


def test_higher_timeframes_unchanged_valid_do_not_block(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    rows = list(csv.DictReader(ohlc.open(newline="", encoding="utf-8")))
    for row in rows:
        if row["timeframe"] == "H1":
            row["timestamp"] = (now - timedelta(hours=1)).isoformat()
        if row["timeframe"] == "H4":
            row["timestamp"] = (now - timedelta(hours=4)).isoformat()
        if row["timeframe"] == "D1":
            row["timestamp"] = (now - timedelta(days=1)).isoformat()
    with ohlc.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    result = execute(parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    for tf in ("H1", "H4", "D1"):
        row = next(item for item in result.handoff_rows if item["timeframe"] == tf)
        assert row["process_status"] == "unchanged_valid"
        assert row["is_ready_for_trading_center"] is True


def test_d1_friday_close_is_valid_on_monday_morning(tmp_path: Path) -> None:
    now = datetime(2026, 6, 8, 10, 10, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    rows = list(csv.DictReader(ohlc.open(newline="", encoding="utf-8")))
    for row in rows:
        if row["timeframe"] == "D1":
            row["timestamp"] = datetime(2026, 6, 5, 0, 0, tzinfo=MADRID).isoformat()
    with ohlc.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    result = execute(parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    d1 = next(row for row in result.handoff_rows if row["timeframe"] == "D1")
    assert d1["process_status"] == "unchanged_valid"
    assert d1["is_ready_for_trading_center"] is True


def test_h1_stale_real_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now, stale="H1")
    result = execute(parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    h1 = next(row for row in result.handoff_rows if row["timeframe"] == "H1")
    assert h1["process_status"] == "blocked"
    assert h1["blocking_reason"] == "timeframe_stale_real"


def test_event_without_run_id_is_controlled(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    result = execute(parse_args(["--trigger", "event", "--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    assert all(row["data_refresh_run_id"] == "missing_event_run_id" for row in result.handoff_rows)


def test_dry_run_does_not_invoke_orchestrator_by_default(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    result = execute(parse_args(["--dry-run", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    assert result.run_meta["orchestrator_invoked"] is False
    assert result.run_meta["sql_real_written"] is False
    assert result.run_meta["mt5_connected"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["signals_generated"] is False
    assert result.run_meta["backtests_executed"] is False


def test_invoke_orchestrator_audit_only(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    result = execute(
        parse_args(
            [
                "--audit-only",
                "--invoke-orchestrator",
                "--orchestrator-mode",
                "audit-only",
                "--ohlc-artifact",
                str(ohlc),
                "--output-dir",
                str(tmp_path / "out"),
                "--scheduler-now",
                now.isoformat(),
                "--doc-path",
                str(tmp_path / "doc.md"),
            ]
        )
    )
    assert result.run_meta["orchestrator_invoked"] is True
    assert result.run_meta["orchestrator_mode"] == "audit-only"
    assert result.orchestrator_rows[0]["exit_code"] == 0
    assert result.orchestrator_rows[0]["refresh_executed"] is False


def test_run_meta_fail_closed(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    execute(parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--scheduler-now", now.isoformat(), "--doc-path", str(tmp_path / "doc.md")]))
    data = meta(tmp_path / "out")
    assert data["scheduler_service_implemented"] is False
    assert data["background_loop_implemented"] is False
    assert data["uses_open_candles"] is False
    assert data["db_connected"] is False
    assert data["orders_sent"] == 0
