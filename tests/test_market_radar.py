from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_center.market_radar import (
    MarketRadarConfig,
    alignment_state,
    build_market_radar,
    dashboard_bucket_for,
    extreme_state,
)


def _write_context(path: Path, symbol: str, timeframe: str, rows: int, trend: str, htf_trend: str) -> None:
    start = pd.Timestamp("2026-01-01 00:00:00")
    step = "1h" if timeframe == "H1" else "4h"
    timestamps = pd.date_range(start=start, periods=rows, freq=step)
    base = 100.0
    records = []
    for index, timestamp in enumerate(timestamps):
        close = base + index * 0.1
        records.append(
            {
                "group": "Forex Majors",
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": timestamp.isoformat(),
                "open": close - 0.05,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "trend_state": trend,
                "htf_trend_state": htf_trend,
                "htf_context_source_time": timestamp.isoformat(),
            }
        )
    pd.DataFrame(records).to_csv(path, index=False)


def _write_ohlc_mtf(path: Path, symbol: str, rows: int = 180) -> None:
    records = []
    starts = {
        "M15": ("15min", 100.0),
        "H1": ("1h", 110.0),
        "H4": ("4h", 120.0),
        "D1": ("1D", 130.0),
    }
    for timeframe, (freq, base) in starts.items():
        timestamps = pd.date_range("2026-01-01 00:00:00", periods=rows, freq=freq)
        for index, timestamp in enumerate(timestamps):
            close = base + index * 0.1
            records.append(
                {
                    "market_group": "Forex Majors",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "timestamp": timestamp.isoformat(),
                    "open": close - 0.05,
                    "high": close + 0.2,
                    "low": close - 0.2,
                    "close": close,
                    "tick_volume": 100,
                    "spread": 1,
                    "real_volume": 0,
                }
            )
    pd.DataFrame(records).to_csv(path, index=False)


def test_alignment_and_counter_extreme_cases_are_separate() -> None:
    assert alignment_state("bullish", "bullish", "bullish") == "bullish_aligned_h1_h4_d1"
    assert alignment_state("bearish", "bearish", "bearish") == "bearish_aligned_h1_h4_d1"
    assert alignment_state("bullish", "bearish", "bullish") == "not_aligned_h1_h4_d1"
    assert dashboard_bucket_for("bullish_aligned_h1_h4_d1", "", "bullish_oversold", "") == "counter_extreme"
    assert dashboard_bucket_for("bearish_aligned_h1_h4_d1", "", "bearish_overbought", "") == "counter_extreme"
    assert dashboard_bucket_for("bullish_aligned_h1_h4_d1", "", "", "") == "trend_aligned"


def test_extreme_state_uses_rsi_and_stoch_thresholds() -> None:
    config = MarketRadarConfig()

    assert extreme_state({"RSI": "75", "STOCH_K": "30", "STOCH_D": "30"}, config) == "overbought"
    assert extreme_state({"RSI": "50", "STOCH_K": "10", "STOCH_D": "12"}, config) == "oversold"
    assert extreme_state({"RSI": "50", "STOCH_K": "45", "STOCH_D": "47"}, config) == "neutral"


def test_build_market_radar_from_fixture_contexts(tmp_path: Path) -> None:
    h1_context = tmp_path / "h1_context.csv"
    h4_context = tmp_path / "h4_context.csv"
    symbol_control = tmp_path / "symbol_control.csv"
    output_dir = tmp_path / "radar"
    doc_path = tmp_path / "MARKET_RADAR_DOC.md"

    _write_context(h1_context, "EURUSD.r", "H1", rows=180, trend="bullish", htf_trend="bullish")
    _write_context(h4_context, "EURUSD.r", "H4", rows=80, trend="bullish", htf_trend="bullish")
    pd.DataFrame([{"symbol": "EURUSD.r", "group_normalized": "Forex Majors", "enabled": True}]).to_csv(
        symbol_control, index=False
    )

    result = build_market_radar(
        MarketRadarConfig(
            source_ohlc_csv=None,
            h1_context_csv=h1_context,
            h4_context_csv=h4_context,
            symbol_control_csv=symbol_control,
            output_dir=output_dir,
            doc_path=doc_path,
        )
    )

    assert result.run_meta["market_radar_rows"] == 1
    assert result.run_meta["sql_real_read"] is False
    assert result.run_meta["db_connected"] is False
    assert result.run_meta["mt5_connected"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["signals_generated"] is False
    assert result.run_meta["wavecount_used_as_filter"] is False
    assert result.market_radar.iloc[0]["alignment_state"] == "bullish_aligned_h1_h4_d1"
    assert "m15_trend" in result.market_radar.columns
    assert "h1_rsi_signal" in result.market_radar.columns
    assert "h4_rsi_signal" in result.market_radar.columns
    assert not bool(result.market_radar.iloc[0]["can_execute_order"])
    assert (output_dir / "market_radar.csv").exists()
    assert (output_dir / "market_radar.json").exists()
    assert (output_dir / "tables/source_coverage_audit.csv").exists()
    assert (output_dir / "tables/indicator_engine_audit.csv").exists()
    assert doc_path.exists()


def test_build_market_radar_from_sql_readonly_ohlc_artifact(tmp_path: Path) -> None:
    source_ohlc = tmp_path / "ohlc_mtf.csv"
    symbol_control = tmp_path / "symbol_control.csv"
    output_dir = tmp_path / "radar"
    doc_path = tmp_path / "MARKET_RADAR_DOC.md"

    _write_ohlc_mtf(source_ohlc, "EURUSD.r")
    pd.DataFrame([{"symbol": "EURUSD.r", "group_normalized": "Forex Majors", "enabled": True}]).to_csv(
        symbol_control, index=False
    )

    result = build_market_radar(
        MarketRadarConfig(
            source_ohlc_csv=source_ohlc,
            symbol_control_csv=symbol_control,
            output_dir=output_dir,
            doc_path=doc_path,
        )
    )

    row = result.market_radar.iloc[0]
    assert result.run_meta["source_mode"] == "sql_readonly_ohlc_artifact"
    assert result.run_meta["sql_real_read"] is False
    assert result.run_meta["source_sql_readonly_artifact"] is True
    assert row["m15_trend"] == "bullish"
    assert row["h1_trend"] == "bullish"
    assert row["h4_trend"] == "bullish"
    assert row["d1_trend"] == "bullish"
    assert row["alignment_state"] == "bullish_aligned_h1_h4_d1"
    assert "rsi_m15" in result.market_radar.columns
    assert "atr_pct_h1_median" in result.market_radar.columns
    assert "atr_pct_h1_ratio" in result.market_radar.columns
    assert "atr_pct_h1_sample_count" in result.market_radar.columns
    assert float(row["atr_pct_h1_ratio"]) > 0


def test_market_radar_module_has_no_runtime_connectors() -> None:
    source = Path("trading_center/market_radar.py").read_text(encoding="utf-8")

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
