from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import data.mt5.trading_center_refresh_hook as hook_module
from data.mt5.trading_center_refresh_hook import (
    TradingCenterRefreshHookConfig,
    execute_trading_center_refresh_hook,
    maybe_run_trading_center_refresh_after_ingest,
    parse_args,
)


MADRID = ZoneInfo("Europe/Madrid")


def write_fixture_ohlc(path: Path, timestamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for timeframe in ("M15", "H1", "H4", "D1"):
        for symbol in ("EURUSD.r", "GBPUSD.r"):
            rows.append(
                {
                    "market_group": "Forex Majors",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "timestamp": timestamp.isoformat(),
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


def test_hook_desactivado_no_refresca(tmp_path: Path) -> None:
    result = execute_trading_center_refresh_hook(
        ["M15"],
        config=TradingCenterRefreshHookConfig(enabled=False, output_root=tmp_path / "out"),
        scheduler_now=datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
    )

    assert result.run_meta["hook_skipped"] is True
    assert result.ohlc_artifact is None
    assert (result.output_dir / "run_meta.json").exists()


def test_hook_exporta_handoff_y_lanza_refresh_handoff_driven(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    scheduler_now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)

    def sql_extractor(config):
        ohlc = config.output_dir / "ohlc_mtf.csv"
        write_fixture_ohlc(ohlc, scheduler_now)
        return SimpleNamespace(run_meta={"decision": "sql_market_data_readonly_ready_for_market_radar"})

    def refresh_runner(args):
        calls["refresh_args"] = args
        return SimpleNamespace(
            run_meta={
                "decision": "trading_center_refresh_service_and_dash_autorefresh_v1_ready_for_live_local_review",
                "service_mode": args.service_mode,
                "slots_processed": 1,
            }
        )

    result = execute_trading_center_refresh_hook(
        ["M15"],
        config=TradingCenterRefreshHookConfig(
            enabled=True,
            dry_run=True,
            output_root=tmp_path / "out",
            latest_dir=tmp_path / "latest",
        ),
        scheduler_now=scheduler_now,
        sql_extractor=sql_extractor,
        refresh_runner=refresh_runner,
    )

    refresh_args = calls["refresh_args"]
    assert refresh_args.service_mode == "handoff-driven"
    assert refresh_args.handoff_dir == result.handoff_dir
    assert refresh_args.ohlc_artifact == result.ohlc_artifact
    assert refresh_args.dry_run is True
    assert result.run_meta["hook_enabled"] is True
    assert result.run_meta["slots_processed"] == 1
    assert (result.handoff_dir / "scheduler_handoff_status.csv").exists()


def test_hook_puede_usar_ohlc_precalculado_sin_sql(tmp_path: Path) -> None:
    scheduler_now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc_mtf.csv"
    write_fixture_ohlc(ohlc, scheduler_now)
    refresh_calls: list[object] = []

    result = execute_trading_center_refresh_hook(
        ["H1", "H4", "D1"],
        config=TradingCenterRefreshHookConfig(
            enabled=True,
            audit_only=True,
            skip_sql_extract=True,
            ohlc_artifact=ohlc,
            output_root=tmp_path / "out",
            latest_dir=tmp_path / "latest",
        ),
        scheduler_now=scheduler_now,
        refresh_runner=lambda args: refresh_calls.append(args)
        or SimpleNamespace(run_meta={"decision": "ok", "service_mode": args.service_mode, "slots_processed": 1}),
    )

    assert result.ohlc_artifact == ohlc
    assert refresh_calls[0].audit_only is True
    assert result.run_meta["updated_timeframes"] == ["H1", "H4", "D1"]


def test_maybe_hook_no_tumba_scheduler_si_falla(tmp_path: Path, monkeypatch) -> None:
    def bad_sql_extractor(_config):
        raise RuntimeError("boom")

    monkeypatch.setattr(hook_module, "extract_sql_market_data", bad_sql_extractor)

    safe_result = maybe_run_trading_center_refresh_after_ingest(
        ["M15"],
        scheduler_now=datetime(2026, 6, 6, 10, 3, tzinfo=MADRID),
        config=TradingCenterRefreshHookConfig(enabled=True, output_root=tmp_path / "safe"),
    )
    assert safe_result.run_meta["hook_blocked"] is True
    assert safe_result.run_meta["exception_class"] == "RuntimeError"


def test_run_meta_json_flags_fail_closed(tmp_path: Path) -> None:
    scheduler_now = datetime(2026, 6, 6, 10, 3, tzinfo=MADRID)
    ohlc = tmp_path / "ohlc_mtf.csv"
    write_fixture_ohlc(ohlc, scheduler_now)
    result = execute_trading_center_refresh_hook(
        ["M15"],
        config=TradingCenterRefreshHookConfig(
            enabled=True,
            skip_sql_extract=True,
            ohlc_artifact=ohlc,
            output_root=tmp_path / "out",
            latest_dir=tmp_path / "latest",
        ),
        scheduler_now=scheduler_now,
        refresh_runner=lambda args: SimpleNamespace(run_meta={"decision": "ok", "service_mode": args.service_mode, "slots_processed": 1}),
    )
    meta = json.loads((result.output_dir / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["telegram_connected"] is False
    assert meta["signals_generated"] is False
    assert meta["backtests_executed"] is False


def test_hook_cli_parsea_timeframes_y_flags(tmp_path: Path) -> None:
    args = parse_args(["--enable", "--dry-run", "--timeframes", "M15,H1,H4", "--output-root", str(tmp_path / "out")])

    assert args.enable is True
    assert args.dry_run is True
    assert args.timeframes == "M15,H1,H4"
