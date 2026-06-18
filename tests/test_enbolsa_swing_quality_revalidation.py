from pathlib import Path

import pandas as pd

from trading_center.enbolsa_swing_quality_revalidation import main


def _write_table(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _block_rows(trades: int, ret: float, strategy: str = "enbolsa:macd_breakout") -> list[dict]:
    return [
        {
            "Variante": strategy,
            "Family": "enbolsa",
            "Group": "Forex Majors",
            "LTF": "H1",
            "HTF": "H4",
            "TFPair": "H1:H4",
            "BlockId": "forex-majors-h1-h4",
            "MetricScope": "block_portfolio",
            "TFStackEffective": "H1,H4,D1",
            "H4D1Mode": "normal_stack",
            "PartialSource": "partial-forex-majors-h1-h4",
            "Trades": trades,
            "WR%": 50.0,
            "AvgWin%": 1.0,
            "AvgLoss%": -1.0,
            "R:R": 1.0,
            "PF": 1.2,
            "Return%": ret,
            "Sharpe": 0.4,
            "Sortino": 0.5,
            "MaxDD%": 5.0,
            "Calmar": 1.0,
            "NetProfit": ret * 100.0,
            "Exposure%": 10.0,
            "ReturnOverDrawdown": ret / 5.0,
            "AvgR": 0.1,
        },
        {
            "Variante": "benchmark:ma_cross_3tf_trend",
            "Family": "benchmark",
            "Group": "Forex Majors",
            "LTF": "H1",
            "HTF": "H4",
            "TFPair": "H1:H4",
            "BlockId": "forex-majors-h1-h4",
            "MetricScope": "block_portfolio",
            "TFStackEffective": "H1,H4,D1",
            "H4D1Mode": "normal_stack",
            "PartialSource": "partial-forex-majors-h1-h4",
            "Trades": 2,
            "WR%": 0.0,
            "AvgWin%": 0.0,
            "AvgLoss%": -1.0,
            "R:R": 0.0,
            "PF": 0.0,
            "Return%": -2.0,
            "Sharpe": -0.2,
            "Sortino": -0.2,
            "MaxDD%": 2.0,
            "Calmar": -1.0,
            "NetProfit": -200.0,
            "Exposure%": 5.0,
            "ReturnOverDrawdown": -1.0,
            "AvgR": -0.1,
        },
    ]


def _trade_rows(count: int, strategy: str = "enbolsa:macd_breakout") -> list[dict]:
    rows = []
    for idx in range(count):
        rows.append(
            {
                "strategy": strategy,
                "source_family": "enbolsa",
                "Group": "Forex Majors",
                "symbol": "EURUSD.r",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "entry_time": f"2025-01-{idx + 1:02d}",
                "exit_time": f"2025-01-{idx + 2:02d}",
                "pnl_money": 10.0,
                "weighted_return": 0.001,
                "risk_amount": 50.0,
                "balance_before_entry": 10000.0,
                "SWING_QUALITY_PASS": True,
                "SWING_QUALITY_REASON": "pass",
            }
        )
    return rows


def test_revalidation_builds_outputs_from_existing_tables(tmp_path: Path) -> None:
    v1 = tmp_path / "v1_final"
    sq_root = tmp_path / "sq_root"
    sq = sq_root / "final"
    output = tmp_path / "out"
    doc = tmp_path / "doc.md"

    _write_table(v1 / "tables/block_metrics.csv", _block_rows(10, 10.0))
    _write_table(sq / "tables/block_metrics.csv", _block_rows(7, 8.0))
    _write_table(v1 / "tables/trade_log.csv", _trade_rows(10))
    _write_table(sq / "tables/trade_log.csv", _trade_rows(7))

    result = main([
        "--skip-backtests",
        "--v1-final",
        str(v1),
        "--benchmark-root",
        str(sq_root),
        "--output-dir",
        str(output),
        "--doc-path",
        str(doc),
    ])

    assert result["run_meta"]["enbolsa_swing_quality_revalidated"] is True
    assert result["run_meta"]["canonical_artifacts_overwritten"] is False
    assert result["run_meta"]["mt5_connected"] is False
    assert result["run_meta"]["telegram_connected"] is False
    assert (output / "tables/v1_vs_swing_quality_comparison.csv").exists()
    assert (output / "tables/allowed_claims_after_revalidation.csv").exists()
    assert doc.exists()
