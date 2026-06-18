from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_center.artifact_refresh_orchestrator import execute, parse_args, promote_latest_artifacts


def write_ohlc(path: Path, now: datetime, *, timeframes: tuple[str, ...] = ("M15", "H1", "H4", "D1"), stale: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    offsets = {
        "M15": timedelta(minutes=15),
        "H1": timedelta(hours=1),
        "H4": timedelta(hours=4),
        "D1": timedelta(days=1),
    }
    rows = []
    for tf in timeframes:
        ts = now - (timedelta(days=4) if stale == tf else offsets[tf])
        rows.append(
            {
                "market_group": "Forex Majors",
                "symbol": "EURUSD.r",
                "timeframe": tf,
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
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


def test_cli_audit_only_generates_artifacts(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    out = tmp_path / "out"
    write_ohlc(ohlc, now)

    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(out), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)

    assert (out / "tables/trigger_audit.csv").exists()
    assert (out / "tables/timeframe_freshness_audit.csv").exists()
    assert result.run_meta["refresh_decision"] == "refresh_allowed"
    assert result.run_meta["refresh_executed"] is False
    assert meta(out)["sql_real_written"] is False


def test_dry_run_does_not_regenerate_downstream(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    out = tmp_path / "out"
    write_ohlc(ohlc, now)

    args = parse_args(["--dry-run", "--ohlc-artifact", str(ohlc), "--output-dir", str(out), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)

    assert result.run_meta["refresh_decision"] == "refresh_allowed"
    assert result.run_meta["refresh_executed"] is False
    assert any(row["component"] == "market_correlations" and row["status"] == "skipped_slow_analytics_last_good" for row in result.dependency_rows)
    assert any(row["component"] == "weavecount_screener_h1_h4" and row["status"] == "skipped_hourly_analytics_last_good" for row in result.dependency_rows)
    assert all(
        row["status"] in {"planned_dry_run", "skipped_slow_analytics_last_good", "skipped_hourly_analytics_last_good"}
        for row in result.dependency_rows
    )
    dash_command = next(row["command"] for row in result.dependency_rows if row["component"] == "dash_readonly_audit")
    assert "--wavecount-csv" in dash_command
    assert "generated" in dash_command
    assert "trading_center_market_correlations_v1_2026-05-31" in dash_command
    assert "weavecount_screener_h1_h4_v1_2026-06-01" in dash_command
    screener_command = next(row["command"] for row in result.dependency_rows if row["component"] == "screener_unified")
    assert "--macd-breakout-enriched-csv" in screener_command
    assert "--macd-breakout-chart-layers-csv" in screener_command
    assert "macd_breakout" in screener_command
    assert any(row["component"] == "macd_breakout_watcher" and row["status"] == "skipped_hourly_analytics_last_good" for row in result.dependency_rows)
    assert any(row["component"] == "macd_breakout_enrichment" and row["status"] == "skipped_hourly_analytics_last_good" for row in result.dependency_rows)


def test_include_slow_analytics_regenerates_correlations_in_plan(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    out = tmp_path / "out"
    write_ohlc(ohlc, now)

    args = parse_args(
        [
            "--dry-run",
            "--include-slow-analytics",
            "--ohlc-artifact",
            str(ohlc),
            "--output-dir",
            str(out),
            "--doc-path",
            str(tmp_path / "doc.md"),
        ]
    )
    result = execute(args, now=now)

    correlation_row = next(row for row in result.dependency_rows if row["component"] == "market_correlations")
    assert correlation_row["status"] == "planned_dry_run"
    assert correlation_row["refresh_lane"] == "slow_daily"
    dash_command = next(row["command"] for row in result.dependency_rows if row["component"] == "dash_readonly_audit")
    assert str(out / "generated" / "market_correlations" / "correlation_pairs.csv") in dash_command
    assert result.run_meta["include_slow_analytics"] is True
    assert result.run_meta["market_correlations_refresh_mode"] == "regenerate"


def test_include_hourly_analytics_regenerates_weavecount_in_plan(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    out = tmp_path / "out"
    write_ohlc(ohlc, now)

    args = parse_args(
        [
            "--dry-run",
            "--include-hourly-analytics",
            "--ohlc-artifact",
            str(ohlc),
            "--output-dir",
            str(out),
            "--doc-path",
            str(tmp_path / "doc.md"),
        ]
    )
    result = execute(args, now=now)

    weavecount_row = next(row for row in result.dependency_rows if row["component"] == "weavecount_screener_h1_h4")
    macd_watcher_row = next(row for row in result.dependency_rows if row["component"] == "macd_breakout_watcher")
    macd_enrichment_row = next(row for row in result.dependency_rows if row["component"] == "macd_breakout_enrichment")
    assert weavecount_row["status"] == "planned_dry_run"
    assert weavecount_row["refresh_lane"] == "hourly"
    assert macd_watcher_row["status"] == "planned_dry_run"
    assert macd_watcher_row["refresh_lane"] == "hourly"
    assert "trading_center.macd_breakout_watcher_combined" in macd_watcher_row["module"]
    assert "--tf-pairs H1:H4,H4:D1" in macd_watcher_row["command"]
    assert macd_enrichment_row["status"] == "planned_dry_run"
    assert macd_enrichment_row["refresh_lane"] == "hourly"
    assert str(out / "generated" / "macd_breakout_watcher" / "snapshot.csv") in macd_enrichment_row["command"]
    dash_command = next(row["command"] for row in result.dependency_rows if row["component"] == "dash_readonly_audit")
    screener_command = next(row["command"] for row in result.dependency_rows if row["component"] == "screener_unified")
    assert str(out / "generated" / "weavecount_screener_h1_h4" / "weavecount_screener.csv") in dash_command
    assert str(out / "generated" / "macd_breakout_enrichment" / "macd_breakout_enriched_setups.csv") in screener_command
    assert str(out / "generated" / "macd_breakout_enrichment" / "macd_breakout_chart_layers.csv") in screener_command
    assert result.run_meta["include_hourly_analytics"] is True
    assert result.run_meta["weavecount_refresh_mode"] == "regenerate"
    assert result.run_meta["macd_breakout_refresh_mode"] == "regenerate"
    assert "macd_breakout_watcher" in result.run_meta["hourly_refresh_components"]
    assert "macd_breakout_enrichment" in result.run_meta["hourly_refresh_components"]


def test_latest_promotion_copies_passed_and_preserves_skipped_components(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    ohlc = tmp_path / "ohlc_mtf.csv"
    ohlc.write_text(
        "symbol,timeframe,timestamp,open,high,low,close\nEURUSD.r,M15,2026-06-05 10:00:00,1,1,1,1\n",
        encoding="utf-8",
    )
    generated = output_dir / "generated"
    for component, filename in {
        "market_radar": "market_radar.csv",
        "fibonacci_context": "fibonacci_context.csv",
        "screener_unified": "screener_setups.csv",
        "dash_audit": "run_meta.json",
    }.items():
        path = generated / component / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("k,v\n", encoding="utf-8")
    existing_weavecount = latest_dir / "weavecount" / "weavecount_screener.csv"
    existing_weavecount.parent.mkdir(parents=True, exist_ok=True)
    existing_weavecount.write_text("old,weavecount\n", encoding="utf-8")
    dependency_rows = [
        {"component": "market_radar", "status": "passed"},
        {"component": "market_correlations", "status": "skipped_slow_analytics_last_good"},
        {"component": "weavecount_screener_h1_h4", "status": "skipped_hourly_analytics_last_good"},
        {"component": "fibonacci_context", "status": "passed"},
        {"component": "screener_unified", "status": "passed"},
        {"component": "dash_readonly_audit", "status": "passed"},
    ]

    rows, manifest = promote_latest_artifacts(
        latest_dir,
        output_dir,
        ohlc,
        "refresh_allowed",
        False,
        False,
        dependency_rows,
        datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc),
    )

    assert (latest_dir / "ohlc" / "ohlc_mtf.csv").exists()
    assert (latest_dir / "market_radar" / "market_radar.csv").exists()
    assert (latest_dir / "fibonacci_context" / "fibonacci_context.csv").exists()
    assert (latest_dir / "screener_unified" / "screener_setups.csv").exists()
    assert existing_weavecount.read_text(encoding="utf-8") == "old,weavecount\n"
    assert (latest_dir / "latest_manifest.json").exists()
    statuses = {row["component"]: row["promotion_status"] for row in rows}
    assert statuses["weavecount"] == "preserved_last_good"
    assert statuses["correlations"] in {"missing_last_good", "bootstrapped_last_good"}
    assert "screener_unified" in manifest["promoted_components"]
    assert "correlations" not in manifest["preserved_last_good_components"]
    assert "late, invalidated, stale and distance" in manifest["setup_validity_policy"]


def test_latest_promotion_dry_run_does_not_write_latest(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    latest_dir = tmp_path / "latest"
    ohlc = tmp_path / "ohlc_mtf.csv"
    ohlc.write_text("x\n", encoding="utf-8")

    rows, manifest = promote_latest_artifacts(
        latest_dir,
        output_dir,
        ohlc,
        "refresh_allowed",
        True,
        False,
        [{"component": "market_radar", "status": "planned_dry_run"}],
        datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc),
    )

    assert not latest_dir.exists()
    assert manifest["promoted_components"] == []
    assert {row["promotion_status"] for row in rows} <= {"not_promoted", "missing_last_good"}


def test_missing_ohlc_blocks_or_uses_last_good(tmp_path: Path) -> None:
    out = tmp_path / "out"
    args = parse_args(["--audit-only", "--ohlc-artifact", str(tmp_path / "missing.csv"), "--output-dir", str(out), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc))

    assert result.run_meta["refresh_decision"] == "use_last_good_artifacts"
    assert result.run_meta["last_good_artifact_used"] is True
    assert result.run_meta["ohlc_schema_valid"] is False


def test_invalid_schema_blocks(tmp_path: Path) -> None:
    ohlc = tmp_path / "bad.csv"
    ohlc.write_text("symbol,timeframe,close\nEURUSD.r,M15,1.0\n", encoding="utf-8")
    out = tmp_path / "out"
    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(out), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc))

    assert result.run_meta["refresh_decision"] == "use_last_good_artifacts"
    assert result.run_meta["ohlc_schema_valid"] is False


def test_missing_required_timeframe_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now, timeframes=("M15", "H1", "D1"))
    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)

    assert result.run_meta["required_timeframes_present"] is False
    assert result.run_meta["refresh_decision"] == "use_last_good_artifacts"


def test_warning_allowed_and_strict_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 45, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    # Make M15 warning but not blocked.
    rows = list(csv.DictReader(ohlc.open(newline="", encoding="utf-8")))
    rows[0]["timestamp"] = (now - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
    with ohlc.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "allowed"), "--doc-path", str(tmp_path / "doc1.md")])
    allowed = execute(args, now=now)
    assert allowed.run_meta["refresh_decision"] == "refresh_allowed_with_warnings"

    strict_args = parse_args(["--audit-only", "--strict-freshness", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "strict"), "--doc-path", str(tmp_path / "doc2.md")])
    strict = execute(strict_args, now=now)
    assert strict.run_meta["refresh_decision"] == "use_last_good_artifacts"


def test_no_allow_warnings_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 45, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    rows = list(csv.DictReader(ohlc.open(newline="", encoding="utf-8")))
    rows[0]["timestamp"] = (now - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
    with ohlc.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    args = parse_args(["--audit-only", "--no-allow-warnings", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)
    assert result.run_meta["refresh_decision"] == "use_last_good_artifacts"


def test_stale_timeframe_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now, stale="M15")
    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)
    assert result.run_meta["freshness_blocked_count"] >= 1
    assert result.run_meta["refresh_decision"] == "use_last_good_artifacts"


def test_d1_friday_close_does_not_block_monday_morning(tmp_path: Path) -> None:
    now = datetime(2026, 6, 8, 8, 10, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    rows = list(csv.DictReader(ohlc.open(newline="", encoding="utf-8")))
    for row in rows:
        if row["timeframe"] == "D1":
            row["timestamp"] = "2026-06-05 00:00:00"
    with ohlc.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    args = parse_args(["--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)
    d1 = next(row for row in result.freshness_rows if row["timeframe"] == "D1")
    assert d1["freshness_status"] == "warning"
    assert result.run_meta["freshness_blocked_count"] == 0
    assert result.run_meta["refresh_decision"] == "refresh_allowed_with_warnings"


def test_scheduler_status_missing_warns_but_valid_ohlc_allows(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    args = parse_args(["--audit-only", "--scheduler-status-dir", str(tmp_path / "missing_status"), "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)
    assert result.run_meta["scheduler_status_dir_present"] is False
    assert result.run_meta["refresh_decision"] == "refresh_allowed"
    assert result.scheduler_rows[0]["blocking_reason"] == "scheduler_status_missing_warning"


def test_scheduler_blocked_timeframe_blocks(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    with (status_dir / "status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["data_refresh_run_id", "timeframe", "process_status", "is_required", "is_ready_for_trading_center", "blocking_reason"])
        writer.writeheader()
        writer.writerow({"data_refresh_run_id": "run1", "timeframe": "M15", "process_status": "failed", "is_required": "true", "is_ready_for_trading_center": "false", "blocking_reason": "scheduler_failed"})
    args = parse_args(["--audit-only", "--scheduler-status-dir", str(status_dir), "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    result = execute(args, now=now)
    assert result.run_meta["refresh_decision"] == "use_last_good_artifacts"


def test_scheduler_handoff_ignores_run_meta_json(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    with (status_dir / "scheduler_handoff_status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "data_refresh_run_id",
                "timeframe",
                "process_status",
                "is_required",
                "is_ready_for_trading_center",
                "blocking_reason",
            ],
        )
        writer.writeheader()
        for timeframe in ("M15", "H1", "H4", "D1"):
            writer.writerow(
                {
                    "data_refresh_run_id": "run1",
                    "timeframe": timeframe,
                    "process_status": "completed",
                    "is_required": "true",
                    "is_ready_for_trading_center": "true",
                    "blocking_reason": "",
                }
            )
    (status_dir / "run_meta.json").write_text(json.dumps({"phase": "scheduler", "timeframe": ""}), encoding="utf-8")

    args = parse_args(
        [
            "--audit-only",
            "--scheduler-status-dir",
            str(status_dir),
            "--ohlc-artifact",
            str(ohlc),
            "--output-dir",
            str(tmp_path / "out"),
            "--doc-path",
            str(tmp_path / "doc.md"),
        ]
    )
    result = execute(args, now=now)

    assert result.run_meta["refresh_decision"] == "refresh_allowed"
    assert {row["timeframe"] for row in result.scheduler_rows} == {"M15", "H1", "H4", "D1"}


def test_event_trigger_records_missing_run_id_and_fail_closed_flags(tmp_path: Path) -> None:
    now = datetime(2026, 6, 5, 10, 15, tzinfo=timezone.utc)
    ohlc = tmp_path / "ohlc.csv"
    write_ohlc(ohlc, now)
    args = parse_args(["--trigger", "event", "--audit-only", "--ohlc-artifact", str(ohlc), "--output-dir", str(tmp_path / "out"), "--doc-path", str(tmp_path / "doc.md")])
    # main() fills this in; direct execute keeps provided args, so mimic CLI behavior.
    args.data_refresh_run_id = "missing_event_run_id"
    result = execute(args, now=now)

    assert result.trigger_rows[0]["trigger"] == "event"
    assert result.trigger_rows[0]["data_refresh_run_id"] == "missing_event_run_id"
    assert result.run_meta["mt5_connected"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["signals_generated"] is False
    assert result.run_meta["backtests_executed"] is False
