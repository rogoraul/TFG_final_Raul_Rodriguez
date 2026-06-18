import unittest

import numpy as np
import pandas as pd

from backtests.common.position_sizing import attach_symbol_spec_columns
from backtests.benchmarks.simple_benchmarks import (
    ejecutar_benchmarks,
    preparar_portfolio_benchmarks,
)


def _base_symbol_spec():
    return {
        "digits": 5,
        "point_size": 0.00001,
        "trade_tick_size": 0.00001,
        "trade_tick_value": 1.0,
        "trade_tick_value_profit": 1.0,
        "trade_tick_value_loss": 1.0,
        "trade_contract_size": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "currency_profit": "USD",
    }


def _benchmark_frame():
    index = pd.date_range("2025-01-01", periods=200, freq="30min")
    base = np.linspace(1.0800, 1.1400, len(index))
    wave = np.sin(np.linspace(0, 18, len(index))) * 0.004
    close = base + wave
    df = pd.DataFrame(index=index)
    df["open"] = close - 0.0003
    df["high"] = close + 0.0012
    df["low"] = close - 0.0012
    df["close"] = close
    df["spread_price"] = 0.0001
    df["MACD_HIST"] = np.gradient(close)
    df["STOCH_CROSS_UP"] = False
    df["STOCH_CROSS_DOWN"] = False
    df.loc[df.index[60], "STOCH_CROSS_UP"] = True
    df.loc[df.index[120], "STOCH_CROSS_DOWN"] = True
    return attach_symbol_spec_columns(df, _base_symbol_spec())


class TestSimpleBenchmarks(unittest.TestCase):
    def test_preparar_portfolio_benchmarks_agrega_indicadores(self):
        prepared = preparar_portfolio_benchmarks({"EURUSD.r": _benchmark_frame()})
        df = prepared["EURUSD.r"]
        self.assertIn("ATR_14", df.columns)
        self.assertIn("RSI_14", df.columns)
        self.assertIn("SMA_FAST_20", df.columns)
        self.assertIn("SMA_SLOW_50", df.columns)

    def test_ejecutar_benchmarks_devuelve_bundle_compatible(self):
        result = ejecutar_benchmarks({"EURUSD.r": _benchmark_frame()}, return_details=True, parallel=False)
        self.assertIn("summary", result)
        self.assertIn("trade_log", result)
        self.assertIn("desgloses", result)
        self.assertIn("summary_metrics", result)


if __name__ == "__main__":
    unittest.main()
