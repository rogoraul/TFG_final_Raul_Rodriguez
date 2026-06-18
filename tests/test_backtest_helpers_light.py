import os
import sys
import types
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

stub_name = "backtests.enbolsa.backtest_loader"
previous_loader_module = sys.modules.get(stub_name)
stub_loader = types.ModuleType("backtests.enbolsa.backtest_loader")
stub_loader.cargar_portfolios_matriz = lambda *args, **kwargs: {}
sys.modules[stub_name] = stub_loader

from backtests.common.backtest_matrix_config import (
    DEFAULT_STRATEGIES,
    get_context_config,
    get_strategy_definitions,
)
from backtests.enbolsa.backtest_pipeline import (
    extraer_operaciones_resultado,
    extraer_trades_resultado,
    extraer_ventana_trade,
    generar_auditoria_riesgo,
    resumir_portfolio_cargado,
)

if previous_loader_module is None:
    sys.modules.pop(stub_name, None)
else:
    sys.modules[stub_name] = previous_loader_module


class TestBacktestHelpersLight(unittest.TestCase):
    def test_get_strategy_definitions_returns_deep_copies(self):
        defs_a = get_strategy_definitions()
        defs_b = get_strategy_definitions()

        defs_a["combined_split"]["legs"][0]["risk_fraction"] = 0.25

        self.assertEqual(defs_b["combined_split"]["legs"][0]["risk_fraction"], 0.5)
        self.assertEqual(DEFAULT_STRATEGIES["combined_split"]["legs"][0]["risk_fraction"], 0.5)

    def test_get_context_config_aplica_zigzag_por_grupo(self):
        self.assertAlmostEqual(get_context_config(group_name="Forex Majors")["zigzag_deviation"], 0.005)
        self.assertEqual(get_context_config(group_name="Forex Majors")["zigzag_mode"], "expanding_atr_median")
        self.assertAlmostEqual(get_context_config(group_name="Forex Majors")["zigzag_atr_multiplier"], 2.5)
        self.assertAlmostEqual(get_context_config(group_name="Forex Majors")["zigzag_floor"], 0.0035)
        self.assertAlmostEqual(get_context_config(group_name="Forex Majors")["zigzag_ceiling"], 0.0100)
        self.assertAlmostEqual(get_context_config(group_name="Metals")["zigzag_deviation"], 0.010)
        self.assertEqual(get_context_config(group_name="Metals")["zigzag_mode"], "expanding_atr_median")
        self.assertAlmostEqual(get_context_config(group_name="Metals")["zigzag_atr_multiplier"], 2.5)
        self.assertAlmostEqual(get_context_config(group_name="Metals")["zigzag_floor"], 0.006)
        self.assertAlmostEqual(get_context_config(group_name="Metals")["zigzag_ceiling"], 0.012)
        self.assertAlmostEqual(get_context_config(group_name="Index")["zigzag_deviation"], 0.0075)
        self.assertEqual(get_context_config(group_name="Index")["zigzag_mode"], "expanding_atr_median")
        self.assertAlmostEqual(get_context_config(group_name="Index")["zigzag_atr_multiplier"], 2.5)
        self.assertAlmostEqual(get_context_config(group_name="Index")["zigzag_floor"], 0.005)
        self.assertAlmostEqual(get_context_config(group_name="Index")["zigzag_ceiling"], 0.020)
        self.assertAlmostEqual(
            get_context_config(group_name="Metals", context_config={"zigzag_deviation": 0.012})["zigzag_deviation"],
            0.012,
        )

    def _build_resultado(self):
        trades = pd.DataFrame({
            "symbol": ["EURUSD.r", "EURUSD.r"],
            "strategy": ["fib_limit", "fib_limit"],
            "entry_rule": ["fib_limit", "fib_limit"],
            "direction": [1, 1],
            "setup_id": [1, 1],
            "tp_mult": [1.0, 1.618],
            "size_fraction": [0.5, 0.5],
            "entry_time": pd.to_datetime(["2025-01-01 01:00:00", "2025-01-01 01:00:00"]),
            "exit_time": pd.to_datetime(["2025-01-01 03:00:00", "2025-01-01 05:00:00"]),
            "entry_price": [107.64, 107.64],
            "stop_price": [100.0, 100.0],
            "exit_price": [127.64, 140.00],
            "exit_reason": ["TP", "TP"],
            "return_pct": [18.58, 30.06],
            "weighted_return": [0.0108, 0.0160],
            "pnl": [108.0, 160.32],
            "balance_before_entry": [10000.0, 10000.0],
            "risk_amount": [50.0, 50.0],
            "stop_distance": [7.64, 7.64],
            "loss_per_lot": [764.0, 764.0],
            "lots_raw": [0.0654, 0.0654],
            "lots": [0.06, 0.06],
            "ticks_moved": [2000.0, 3236.0],
            "tick_value_used": [1.0, 1.0],
            "pnl_money": [120.0, 194.16],
            "timeframe_ltf": ["M30", "M30"],
            "timeframe_htf": ["H1", "H1"],
            "freq": ["30min", "30min"],
            "SYMBOL_TRADE_TICK_SIZE": [0.01, 0.01],
        })
        trades.attrs["initial_capital"] = 10000.0
        return {"trades": {"fib_limit": trades}}

    def _build_portfolio(self):
        index = pd.date_range("2025-01-01 00:00:00", periods=6, freq="h")
        df = pd.DataFrame(index=index)
        df["open"] = [108, 108, 110, 115, 125, 132]
        df["high"] = [109, 111, 112, 121, 134, 141]
        df["low"] = [106, 107, 109, 114, 124, 130]
        df["close"] = [108, 109, 110, 118, 130, 140]
        df["spread_price"] = 0.0
        df["TENDENCIA_ESTRUCTURAL_H1"] = 1
        df["LONG_SETUP_ID"] = 1
        df["LONG_SETUP_ACTIVE"] = True
        df["LONG_SETUP_AGE"] = [0, 1, 2, 3, 4, 5]
        df["LONG_W1_START_PRICE"] = 100.0
        df["LONG_W1_END_PRICE"] = 120.0
        df["LONG_W1_SIZE"] = 20.0
        df["LONG_W2_EXTREME_PRICE"] = [108.0, 107.64, 107.0, 107.0, 107.0, 107.0]
        df["LONG_W2_RETR_PCT"] = [0.60, 0.618, 0.65, 0.65, 0.65, 0.65]
        df["LONG_W2_SWING_PRICE"] = [np.nan, np.nan, 107.0, 107.0, 107.0, 107.0]
        df["LONG_W2_VALID_80"] = True
        df["LONG_W2_INVALIDATED"] = False
        df["LONG_FIB_LEVEL_0.5"] = 110.0
        df["LONG_FIB_LEVEL_0.618"] = 107.64
        df["LONG_FIB_LEVEL_0.8"] = 104.0
        df["LONG_W2_TRENDLINE_BROKEN"] = [False, False, True, False, False, False]
        df["LONG_TARGET_1.0"] = [128.0, 127.64, 127.0, 127.0, 127.0, 127.0]
        df["LONG_TARGET_1.618"] = [140.36, 140.0, 139.36, 139.36, 139.36, 139.36]
        df["MACD_CROSS_LONG"] = [False, False, True, False, False, False]
        return {"EURUSD.r": df, "GBPUSD.r": df.iloc[:3].copy()}

    def test_generar_auditoria_riesgo_y_extraer_trades(self):
        resultado = self._build_resultado()

        trades = extraer_trades_resultado(resultado, strategy="fib_limit", symbol="EURUSD.r")
        operaciones = extraer_operaciones_resultado(resultado, strategy="fib_limit", symbol="EURUSD.r")
        audit = generar_auditoria_riesgo(resultado, strategy="fib_limit")

        self.assertEqual(len(trades), 2)
        self.assertEqual(len(operaciones), 1)
        self.assertEqual(int(operaciones["legs"].iloc[0]), 2)
        self.assertAlmostEqual(float(operaciones["lots_total"].iloc[0]), 0.12, places=6)
        self.assertIn("W1_START_PRICE", operaciones.columns)
        self.assertIn("FIB_LEVEL_0.618", operaciones.columns)
        self.assertEqual(len(audit), 2)
        self.assertTrue(np.allclose(audit["risk_gap"].to_numpy(), [-4.16, -4.16]))
        self.assertTrue(np.allclose(audit["pnl_formula_diff"].to_numpy(), 0.0))

    def test_resumir_portfolio_y_extraer_ventana_trade(self):
        resultado = self._build_resultado()
        portfolio = self._build_portfolio()

        resumen = resumir_portfolio_cargado(portfolio)
        self.assertEqual(list(resumen["Activo"]), ["EURUSD.r", "GBPUSD.r"])
        self.assertEqual(list(resumen["Velas"]), [6, 3])

        ventana = extraer_ventana_trade(
            portfolio,
            resultado,
            trade_index=0,
            strategy="fib_limit",
            symbol="EURUSD.r",
            bars_before=1,
            bars_after=1,
        )

        self.assertIn("TRADE_ENTRY", ventana.columns)
        self.assertIn("TRADE_EXIT", ventana.columns)
        self.assertIn("LONG_FIB_LEVEL_0.5", ventana.columns)
        self.assertIn("LONG_W2_RETR_PCT", ventana.columns)
        self.assertTrue(ventana["TRADE_ENTRY"].any())
        self.assertTrue(ventana["TRADE_STOP_PRICE"].notna().all())


if __name__ == "__main__":
    unittest.main()

