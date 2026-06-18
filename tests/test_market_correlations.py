from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_center.market_correlations import (
    MarketCorrelationConfig,
    build_market_correlations,
    compute_returns,
    distance_correlation,
)


def _write_ohlc(path: Path) -> None:
    records = []
    symbols = {
        "EURUSD.r": 100.0,
        "GBPUSD.r": 120.0,
        "USDCHF.r": 90.0,
    }
    for timeframe, freq in {"M15": "15min", "H1": "1h"}.items():
        timestamps = pd.date_range("2026-01-01 00:00:00", periods=90, freq=freq)
        for symbol, base in symbols.items():
            for index, timestamp in enumerate(timestamps):
                drift = index * (0.15 if symbol != "USDCHF.r" else -0.12)
                close = base + drift + (index % 5) * 0.01
                records.append(
                    {
                        "market_group": "Forex Majors",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": timestamp.isoformat(),
                        "open": close - 0.03,
                        "high": close + 0.08,
                        "low": close - 0.08,
                        "close": close,
                    }
                )
    pd.DataFrame(records).to_csv(path, index=False)


def test_compute_returns_uses_log_returns_not_prices(tmp_path: Path) -> None:
    source = tmp_path / "ohlc.csv"
    _write_ohlc(source)
    frame = pd.read_csv(source)

    returns = compute_returns(frame, "H1")

    assert "EURUSD.r" in returns.columns
    assert returns["EURUSD.r"].abs().max() < 0.01
    assert len(returns) == 89


def test_build_market_correlations_outputs_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "ohlc.csv"
    output_dir = tmp_path / "correlations"
    doc_path = tmp_path / "CORR.md"
    _write_ohlc(source)

    result = build_market_correlations(
        MarketCorrelationConfig(
            source_ohlc_csv=source,
            output_dir=output_dir,
            doc_path=doc_path,
            timeframes=("M15", "H1"),
            min_observations=20,
            dcor_max_observations=50,
        )
    )

    assert result.run_meta["returns_based"] is True
    assert result.run_meta["returns_sample_rows"] > 0
    assert result.run_meta["price_based_correlation"] is False
    assert result.run_meta["sql_real_written"] is False
    assert result.run_meta["db_connected"] is False
    assert result.run_meta["mt5_connected"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["signals_generated"] is False
    assert set(result.pair_correlations["timeframe"]) == {"M15", "H1"}
    assert {"pearson", "spearman", "kendall", "dcor"}.issubset(result.pair_correlations.columns)
    assert set(result.rolling_correlations["metric"]) == {"pearson", "spearman", "kendall", "dcor"}
    assert (output_dir / "correlation_pairs.csv").exists()
    assert (output_dir / "correlation_pairs.json").exists()
    assert (output_dir / "rolling_correlations.csv").exists()
    assert (output_dir / "correlation_returns_sample.csv").exists()
    assert (output_dir / "tables/correlation_timeframe_summary.csv").exists()
    assert doc_path.exists()


def test_distance_correlation_detects_dependency() -> None:
    x = pd.Series(range(30), dtype=float).to_numpy()
    y = x * x

    assert distance_correlation(x, y) > 0.8


def test_market_correlations_module_has_no_runtime_connectors() -> None:
    source = Path("trading_center/market_correlations.py").read_text(encoding="utf-8")

    forbidden = [
        "mysql.connector",
        "MetaTrader5",
        "requests",
        "urllib.request",
        "telegram.",
        "Bot(",
        "create_engine",
    ]
    for token in forbidden:
        assert token not in source
