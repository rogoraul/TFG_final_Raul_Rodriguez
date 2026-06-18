import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from backtests.enbolsa.backtest_loader import _attach_spread_price
from backtests.enbolsa.backtest_pipeline import (
    ejecutar_comparativa,
    ejecutar_matriz_backtest,
    extraer_ventana_trade,
    generar_auditoria_riesgo,
    resumir_portfolio_cargado,
    simular_estrategia_portfolio,
)
from backtests.common.position_sizing import attach_symbol_spec_columns


def _strategy_df():
    index = pd.date_range("2025-01-01", periods=6, freq="h")
    df = pd.DataFrame(index=index)
    df["open"] = [108.0, 108.0, 110.0, 115.0, 125.0, 132.0]
    df["high"] = [109.0, 111.0, 112.0, 121.0, 134.0, 135.0]
    df["low"] = [106.0, 107.0, 109.0, 114.0, 124.0, 130.0]
    df["close"] = [108.0, 109.0, 110.0, 118.0, 130.0, 133.0]
    df["spread_price"] = 0.0
    df["TENDENCIA_ESTRUCTURAL_H1"] = 1
    df = attach_symbol_spec_columns(df, {
        "digits": 2,
        "point_size": 0.01,
        "trade_tick_size": 0.01,
        "trade_tick_value": 1.0,
        "trade_tick_value_profit": 1.0,
        "trade_tick_value_loss": 1.0,
        "trade_contract_size": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "currency_profit": "USD",
    })

    for prefix in ("LONG", "SHORT"):
        df[f"{prefix}_SETUP_ID"] = 0
        df[f"{prefix}_SETUP_ACTIVE"] = False
        df[f"{prefix}_SETUP_AGE"] = 0
        df[f"{prefix}_W1_START_PRICE"] = np.nan
        df[f"{prefix}_W1_END_PRICE"] = np.nan
        df[f"{prefix}_W1_SIZE"] = np.nan
        df[f"{prefix}_W2_EXTREME_PRICE"] = np.nan
        df[f"{prefix}_W2_SWING_PRICE"] = np.nan
        df[f"{prefix}_W2_VALID_80"] = False
        df[f"{prefix}_W2_INVALIDATED"] = False
        df[f"{prefix}_FIB_LEVEL_0.618"] = np.nan
        df[f"{prefix}_FIB_TOUCH_618"] = False
        df[f"{prefix}_W2_TRENDLINE_BROKEN"] = False
        df[f"{prefix}_TARGET_1.0"] = np.nan
        df[f"{prefix}_TARGET_1.618"] = np.nan

    df["MACD_CROSS_LONG"] = False
    df["MACD_CROSS_SHORT"] = False

    df["LONG_SETUP_ID"] = 1
    df["LONG_SETUP_ACTIVE"] = True
    df["LONG_SETUP_AGE"] = [0, 1, 2, 3, 4, 5]
    df["LONG_W1_START_PRICE"] = 100.0
    df["LONG_W1_END_PRICE"] = 120.0
    df["LONG_W1_SIZE"] = 20.0
    df["LONG_W2_EXTREME_PRICE"] = [108.0, 107.64, 107.0, 107.0, 107.0, 107.0]
    df["LONG_W2_SWING_PRICE"] = [np.nan, np.nan, 107.0, 107.0, 107.0, 107.0]
    df["LONG_W2_VALID_80"] = True
    df["LONG_W2_INVALIDATED"] = False
    df["LONG_FIB_LEVEL_0.618"] = 107.64
    df["LONG_TARGET_1.0"] = [128.0, 127.64, 127.0, 127.0, 127.0, 127.0]
    df["LONG_TARGET_1.618"] = [140.36, 140.0, 139.36, 139.36, 139.36, 139.36]

    return df


class TestPipelineEnbolsa(unittest.TestCase):
    def test_fib_limit_only_enters_once_per_setup(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        df.loc[df.index[2], "LONG_FIB_TOUCH_618"] = True

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "fib_limit",
            {"entry_rule": "fib_limit", "risk_fraction": 1.0, "tp_levels": (1.0, 1.618)},
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertEqual(len(trades), 2)
        self.assertTrue((trades["entry_rule"] == "fib_limit").all())
        self.assertTrue((trades["entry_time"] == df.index[1]).all())

    def test_long_fib_limit_fills_at_limit_price(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        df.loc[df.index[1], "spread_price"] = 0.12

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "fib_limit",
            {"entry_rule": "fib_limit", "risk_fraction": 1.0, "tp_levels": (1.0, 1.618)},
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertEqual(len(trades), 2)
        self.assertTrue(np.allclose(trades["entry_price"].to_numpy(), 107.64))

    def test_long_macd_breakout_entry_adds_spread_to_market_buy(self):
        df = _strategy_df()
        df.loc[df.index[2], "MACD_CROSS_LONG"] = True
        df.loc[df.index[2], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[2], "spread_price"] = 0.12

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "macd_breakout",
            {
                "entry_rule": "macd_breakout",
                "risk_fraction": 1.0,
                "confirmation_memory_bars": 1,
                "tp_levels": (1.0, 1.618),
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertEqual(len(trades), 2)
        self.assertTrue(np.allclose(trades["entry_price"].to_numpy(), 110.12))

    def test_long_fib_limit_requires_ask_to_reach_level(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        df.loc[df.index[1], "low"] = 107.60
        df.loc[df.index[1], "spread_price"] = 0.12

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "fib_limit",
            {"entry_rule": "fib_limit", "risk_fraction": 1.0, "tp_levels": (1.0, 1.618)},
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertTrue(trades.empty)

    def test_short_take_profit_uses_ask_side_for_exit(self):
        index = pd.date_range("2025-01-01", periods=3, freq="h")
        df = pd.DataFrame(index=index)
        df["open"] = [100.0, 100.0, 100.0]
        df["high"] = [101.0, 100.6, 100.2]
        df["low"] = [99.8, 99.95, 99.95]
        df["close"] = [100.0, 100.1, 99.8]
        df["spread_price"] = [0.0, 0.10, 0.10]
        df["TENDENCIA_ESTRUCTURAL_H1"] = -1

        for prefix in ("LONG", "SHORT"):
            df[f"{prefix}_SETUP_ID"] = 0
            df[f"{prefix}_SETUP_ACTIVE"] = False
            df[f"{prefix}_SETUP_AGE"] = 0
            df[f"{prefix}_W1_START_PRICE"] = np.nan
            df[f"{prefix}_W1_END_PRICE"] = np.nan
            df[f"{prefix}_W1_SIZE"] = np.nan
            df[f"{prefix}_W2_EXTREME_PRICE"] = np.nan
            df[f"{prefix}_W2_SWING_PRICE"] = np.nan
            df[f"{prefix}_W2_VALID_80"] = False
            df[f"{prefix}_W2_INVALIDATED"] = False
            df[f"{prefix}_FIB_LEVEL_0.618"] = np.nan
            df[f"{prefix}_FIB_TOUCH_618"] = False
            df[f"{prefix}_W2_TRENDLINE_BROKEN"] = False
            df[f"{prefix}_TARGET_1.0"] = np.nan
            df[f"{prefix}_TARGET_1.618"] = np.nan

        df["MACD_CROSS_LONG"] = False
        df["MACD_CROSS_SHORT"] = [False, True, False]
        df["SHORT_SETUP_ID"] = 7
        df["SHORT_SETUP_ACTIVE"] = True
        df["SHORT_SETUP_AGE"] = [1, 2, 3]
        df["SHORT_W1_START_PRICE"] = 102.0
        df["SHORT_W2_SWING_PRICE"] = [101.0, 101.0, 101.0]
        df["SHORT_W2_VALID_80"] = True
        df["SHORT_W2_INVALIDATED"] = False
        df["SHORT_W2_TRENDLINE_BROKEN"] = [False, True, False]
        df["SHORT_TARGET_1.0"] = [100.0, 100.0, 100.0]
        df["SHORT_TARGET_1.618"] = [99.0, 99.0, 99.0]

        trades = simular_estrategia_portfolio(
            {"GER40": df},
            "macd_breakout",
            {
                "entry_rule": "macd_breakout",
                "risk_fraction": 1.0,
                "confirmation_memory_bars": 1,
                "tp_levels": (1.0,),
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades["exit_reason"].iloc[0], "EOD")
        self.assertAlmostEqual(trades["exit_price"].iloc[0], 99.9)

    def test_attach_spread_price_converts_points_by_asset(self):
        samples = [
            ("EURUSD.r", [1.10001, 1.10021], 12, 0.00012),
            ("USDJPY.r", [150.123, 150.223], 15, 0.015),
            ("XAUUSD.r", [2350.12, 2351.34], 25, 0.25),
            ("GER40", [18500, 18510], 12, 1.2),
            ("GER40.r", [18500, 18510], 12, 1.2),
        ]

        for symbol, closes, spread_points, expected in samples:
            df = pd.DataFrame({
                "open": closes,
                "high": closes,
                "low": closes,
                "close": closes,
                "spread": [spread_points, spread_points],
            })
            converted = _attach_spread_price(df, symbol=symbol)
            self.assertTrue(np.allclose(converted["spread_price"].to_numpy(), expected))

    def test_attach_spread_price_prefers_symbol_metadata_when_available(self):
        df = pd.DataFrame({
            "open": [18500, 18510],
            "high": [18500, 18510],
            "low": [18500, 18510],
            "close": [18500, 18510],
            "spread": [4, 4],
        })

        converted = _attach_spread_price(
            df,
            symbol="GER40",
            symbol_meta={"digits": 2, "point_size": 0.25},
        )
        self.assertTrue(np.allclose(converted["spread_price"].to_numpy(), 1.0))

    def test_generar_auditoria_riesgo_reconstruye_formula(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        portfolio = {"EURUSD.r": df}

        resultado = ejecutar_comparativa(
            portfolio,
            estrategias=["fib_limit"],
            timeframe_ltf="M30",
            timeframe_htf="H1",
            return_details=True,
        )

        audit = generar_auditoria_riesgo(resultado, strategy="fib_limit")

        self.assertEqual(len(audit), 2)
        self.assertIn("commission_total", audit.columns)
        self.assertTrue(np.allclose(audit["pnl_formula_diff"].to_numpy(), 0.0))
        self.assertTrue(np.allclose(audit["pnl_net_diff"].to_numpy(), 0.0))
        self.assertTrue((audit["expected_loss_at_sl"] <= audit["risk_amount"] + 1e-9).all())
        self.assertTrue((audit["risk_pct_real"] > 0).all())

    def test_resumir_portfolio_cargado_y_ventana_trade(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        short_df = df.iloc[:3].copy()
        portfolio = {"EURUSD.r": df, "GBPUSD.r": short_df}

        resumen = resumir_portfolio_cargado(portfolio)
        self.assertEqual(list(resumen["Activo"]), ["EURUSD.r", "GBPUSD.r"])
        self.assertEqual(list(resumen["Velas"]), [6, 3])

        resultado = ejecutar_comparativa(
            {"EURUSD.r": df},
            estrategias=["fib_limit"],
            timeframe_ltf="M30",
            timeframe_htf="H1",
            return_details=True,
        )
        ventana = extraer_ventana_trade(
            {"EURUSD.r": df},
            resultado,
            trade_index=0,
            strategy="fib_limit",
            bars_before=1,
            bars_after=1,
        )

        self.assertIn("TRADE_ENTRY", ventana.columns)
        self.assertIn("TRADE_STOP_PRICE", ventana.columns)
        self.assertTrue(ventana["TRADE_ENTRY"].any())

    def test_macd_breakout_accepts_conditions_within_memory_window(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[2], "MACD_CROSS_LONG"] = True

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "macd_breakout",
            {
                "entry_rule": "macd_breakout",
                "risk_fraction": 1.0,
                "confirmation_memory_bars": 5,
                "tp_levels": (1.0, 1.618),
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertEqual(len(trades), 2)
        self.assertTrue((trades["entry_rule"] == "macd_breakout").all())
        self.assertTrue((trades["entry_time"] == df.index[2]).all())

    def test_risk_position_sizing_adds_real_lots_and_cash_pnl(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True

        result = ejecutar_comparativa(
            {"EURUSD.r": df},
            estrategias={
                "fib_limit": {
                    "entry_rule": "fib_limit",
                    "risk_fraction": 1.0,
                    "tp_levels": (1.0, 1.618),
                }
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
            account_config={
                "initial_capital": 10000.0,
                "risk_per_trade": 0.01,
                "skip_if_below_min_volume": True,
            },
            return_details=True,
        )

        trades = result["trades"]["fib_limit"]
        self.assertEqual(len(trades), 2)
        self.assertIn("lots", trades.columns)
        self.assertIn("pnl_money", trades.columns)
        self.assertTrue(np.allclose(trades["lots"].to_numpy(), 0.06))
        self.assertTrue((trades["balance_before_entry"] == 10000.0).all())

    def test_macd_breakout_rejects_conditions_outside_memory_window(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[4], "MACD_CROSS_LONG"] = True

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "macd_breakout",
            {
                "entry_rule": "macd_breakout",
                "risk_fraction": 1.0,
                "confirmation_memory_bars": 2,
                "tp_levels": (1.0, 1.618),
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertTrue(trades.empty)

    def test_macd_breakout_rejects_if_setup_invalidated_before_signal(self):
        df = _strategy_df()
        df.loc[df.index[2], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[2], "MACD_CROSS_LONG"] = True
        df.loc[df.index[2]:, "LONG_W2_INVALIDATED"] = True

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "macd_breakout",
            {
                "entry_rule": "macd_breakout",
                "risk_fraction": 1.0,
                "confirmation_memory_bars": 5,
                "tp_levels": (1.0, 1.618),
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertTrue(trades.empty)

    def test_combined_split_creates_fib_and_macd_legs(self):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        df.loc[df.index[2], "MACD_CROSS_LONG"] = True
        df.loc[df.index[2], "LONG_W2_TRENDLINE_BROKEN"] = True

        trades = simular_estrategia_portfolio(
            {"EURUSD.r": df},
            "combined_split",
            {
                "entry_rule": "combined_split",
                "risk_fraction": 1.0,
                "legs": (
                    {"entry_rule": "fib_limit", "risk_fraction": 0.5, "tp_levels": (1.0, 1.618)},
                    {"entry_rule": "macd_breakout", "risk_fraction": 0.5, "tp_levels": (1.0, 1.618)},
                ),
            },
            timeframe_ltf="M30",
            timeframe_htf="H1",
        )

        self.assertEqual(len(trades), 4)
        self.assertEqual(set(trades["entry_rule"]), {"fib_limit", "macd_breakout"})
        self.assertAlmostEqual(trades["size_fraction"].sum(), 1.0)

    @patch("backtests.enbolsa.backtest_pipeline.cargar_portfolios_matriz")
    def test_matrix_runner_aggregates_rows(self, mock_loader):
        df = _strategy_df()
        df.loc[df.index[1], "LONG_FIB_TOUCH_618"] = True
        df.loc[df.index[2], "MACD_CROSS_LONG"] = True
        df.loc[df.index[2], "LONG_W2_TRENDLINE_BROKEN"] = True

        mock_loader.return_value = {
            ("Forex Majors", "M30", "H1"): {"EURUSD.r": df}
        }

        summary = ejecutar_matriz_backtest(
            grupos=["Forex Majors"],
            tf_pairs={"M30": "H1"},
            verbose=False,
        )

        self.assertFalse(summary.empty)
        self.assertEqual(set(summary["Variante"]), {"fib_limit", "macd_breakout", "combined_split"})
        self.assertEqual(set(summary["Group"]), {"Forex Majors"})


if __name__ == "__main__":
    unittest.main()

