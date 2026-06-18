from __future__ import annotations

import json
import csv
from pathlib import Path

from trading_center.fibonacci_context import main
from trading_center.readonly_dashboard import write_csv


def _ohlc_fixture(path: Path) -> None:
    rows = []
    closes = [
        1.1000,
        1.1040,
        1.1080,
        1.1120,
        1.0980,
        1.0940,
        1.0900,
        1.0860,
        1.0820,
        1.0860,
        1.0900,
        1.0940,
        1.0980,
        1.1020,
        1.1060,
        1.1100,
        1.1140,
        1.1180,
        1.1220,
        1.1260,
        1.1300,
        1.1280,
        1.1260,
        1.1240,
    ]
    for index, close in enumerate(closes):
        rows.append(
            {
                "market_group": "Forex Majors",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "timestamp": f"2026-03-17 {index:02d}:00:00",
                "open": f"{close - 0.001:.5f}",
                "high": f"{close + 0.002:.5f}",
                "low": f"{close - 0.002:.5f}",
                "close": f"{close:.5f}",
            }
        )
    write_csv(path, rows)


def test_fibonacci_context_cli_generates_readonly_artifacts(tmp_path: Path) -> None:
    ohlc = tmp_path / "ohlc.csv"
    output_dir = tmp_path / "fib"
    _ohlc_fixture(ohlc)

    main(["--ohlc-csv", str(ohlc), "--output-dir", str(output_dir), "--doc-path", str(tmp_path / "doc.md")])

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    context = (output_dir / "fibonacci_context.csv").read_text(encoding="utf-8")
    levels = (output_dir / "fibonacci_levels.csv").read_text(encoding="utf-8")
    layers = (output_dir / "fibonacci_chart_layers.csv").read_text(encoding="utf-8")

    assert run_meta["fibonacci_context_implemented"] is True
    assert run_meta["artifact_first"] is True
    assert run_meta["is_signal"] is False
    assert run_meta["sql_real_written"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["telegram_connected"] is False
    assert run_meta["orders_sent"] == 0
    assert run_meta["signals_generated"] is False
    assert "EURUSD.r" in context
    assert "Fib 0" in levels
    assert "Fib 100" in levels
    assert "Fib 38.2" in levels
    assert "Fib 61.8" in layers
    layer_rows = list(csv.DictReader((output_dir / "fibonacci_chart_layers.csv").open(encoding="utf-8")))
    assert not any(row["label"] == "Fib ext 1" for row in layer_rows)
    assert "#c793ff" in layers
    rows = list(csv.DictReader((output_dir / "fibonacci_context.csv").open(encoding="utf-8")))
    assert rows
    assert rows[0]["materiality_status"] == "passed"
    assert int(rows[0]["swing_bars"]) >= 10
    assert all(row["is_signal"] == "False" for row in rows)
    assert all(row["can_execute_order"] == "False" for row in rows)


def test_fibonacci_rejects_tiny_recent_swings(tmp_path: Path) -> None:
    ohlc = tmp_path / "ohlc.csv"
    output_dir = tmp_path / "fib"
    rows = []
    closes = [1.1000, 1.1004, 1.1008, 1.1012, 1.1009, 1.1005, 1.1001, 1.1006, 1.1010, 1.1007, 1.1003, 1.1008]
    for index, close in enumerate(closes):
        rows.append(
            {
                "market_group": "Forex Majors",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "timestamp": f"2026-03-17 {index:02d}:00:00",
                "open": f"{close - 0.0001:.5f}",
                "high": f"{close + 0.0002:.5f}",
                "low": f"{close - 0.0002:.5f}",
                "close": f"{close:.5f}",
            }
        )
    write_csv(ohlc, rows)

    main(["--ohlc-csv", str(ohlc), "--output-dir", str(output_dir), "--doc-path", str(tmp_path / "doc.md")])

    context_rows = list(csv.DictReader((output_dir / "fibonacci_context.csv").open(encoding="utf-8")))
    assert context_rows[0]["fibonacci_status"] == "no_clear_swing"
    assert context_rows[0]["materiality_status"] == "failed"


def test_fibonacci_empty_requires_allow_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    output_dir = tmp_path / "fib"
    write_csv(empty, [])

    main(["--ohlc-csv", str(empty), "--output-dir", str(output_dir), "--allow-empty", "--doc-path", str(tmp_path / "doc.md")])

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["contexts_count"] == 0
    assert run_meta["sql_real_written"] is False
