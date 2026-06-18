from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_center.enbolsa_swing_materiality_audit import main
from trading_center.readonly_dashboard import write_csv


def test_enbolsa_materiality_audit_generates_artifacts_without_backtests(tmp_path: Path) -> None:
    trade_log = tmp_path / "trade_log.csv"
    output_dir = tmp_path / "audit"
    rows = [
        {
            "symbol": "EURUSD.r",
            "Group": "Forex Majors",
            "strategy": "ENBOLSA",
            "entry_rule": "fib_limit",
            "direction": "long",
            "setup_id": "s1",
            "entry_time": "2026-03-17 09:00:00",
            "timeframe_ltf": "M30",
            "timeframe_htf": "H1",
            "partial_source": "fixture",
            "W1_START_PRICE": "1.1000",
            "W1_SIZE": "0.0008",
            "BM_ATR_USED": "0.0010",
            "initial_risk_distance": "0.0012",
            "W2_RETR_PCT": "0.55",
        },
        {
            "symbol": "EURUSD.r",
            "Group": "Forex Majors",
            "strategy": "ENBOLSA",
            "entry_rule": "fib_limit",
            "direction": "long",
            "setup_id": "s1",
            "entry_time": "2026-03-17 09:00:00",
            "timeframe_ltf": "M30",
            "timeframe_htf": "H1",
            "partial_source": "fixture",
            "W1_START_PRICE": "1.1000",
            "W1_SIZE": "0.0008",
            "BM_ATR_USED": "0.0010",
            "initial_risk_distance": "0.0012",
            "W2_RETR_PCT": "0.55",
        },
        {
            "symbol": "XAUUSD.r",
            "Group": "Metals",
            "strategy": "ENBOLSA",
            "entry_rule": "macd_breakout",
            "direction": "short",
            "setup_id": "s2",
            "entry_time": "2026-03-18 10:00:00",
            "timeframe_ltf": "H1",
            "timeframe_htf": "H4",
            "partial_source": "fixture",
            "W1_START_PRICE": "2200",
            "W1_SIZE": "25",
            "BM_ATR_USED": "5",
            "initial_risk_distance": "8",
            "W2_RETR_PCT": "0.62",
        },
    ]
    write_csv(trade_log, rows)

    main(["--trade-log-csv", str(trade_log), "--output-dir", str(output_dir), "--doc-path", str(tmp_path / "doc.md")])

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    audited_rows = list(csv.DictReader((output_dir / "enbolsa_swing_materiality_rows.csv").open(encoding="utf-8")))
    assert run_meta["rows_audited"] == 2
    assert run_meta["backtests_executed"] is False
    assert run_meta["signals_generated"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["telegram_connected"] is False
    assert {row["materiality_bucket"] for row in audited_rows} == {"very_small", "large"}
