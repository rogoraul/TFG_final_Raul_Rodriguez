import unittest
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from backtests.common.position_sizing import (
    apply_risk_position_sizing,
    attach_symbol_spec_columns,
    calculate_lot_size_for_risk,
)


class TestPositionSizing(unittest.TestCase):
    def test_calculate_lot_size_for_risk(self):
        sizing = calculate_lot_size_for_risk(
            balance=10000.0,
            risk_per_trade=0.01,
            leg_fraction=0.5,
            entry_price=107.64,
            stop_price=100.0,
            symbol_spec={
                "point_size": 0.01,
                "trade_tick_size": 0.01,
                "trade_tick_value": 1.0,
                "trade_tick_value_loss": 1.0,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
            },
        )

        self.assertTrue(sizing["executed"])
        self.assertAlmostEqual(sizing["risk_amount"], 50.0)
        self.assertAlmostEqual(sizing["lots"], 0.06)

    def test_apply_risk_position_sizing_adds_cash_fields(self):
        index = pd.date_range("2025-01-01", periods=2, freq="h")
        trades = pd.DataFrame({
            "symbol": ["EURUSD.r", "EURUSD.r"],
            "strategy": ["fib_limit", "fib_limit"],
            "entry_rule": ["fib_limit", "fib_limit"],
            "direction": [1, 1],
            "setup_id": [1, 1],
            "tp_mult": [1.0, 1.618],
            "size_fraction": [0.5, 0.5],
            "entry_time": [index[0], index[0]],
            "exit_time": [index[1], index[1]],
            "entry_price": [107.64, 107.64],
            "stop_price": [100.0, 100.0],
            "exit_price": [127.64, 140.0],
            "exit_reason": ["TP", "TP"],
            "return_pct": [18.58, 30.06],
            "weighted_return": [0.0, 0.0],
            "pnl": [0.0, 0.0],
        })
        trades = attach_symbol_spec_columns(trades, {
            "digits": 2,
            "point_size": 0.01,
            "trade_tick_size": 0.01,
            "trade_tick_value": 1.0,
            "trade_tick_value_profit": 1.0,
            "trade_tick_value_loss": 1.0,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01,
        })

        sized = apply_risk_position_sizing(
            trades,
            account_config={
                "initial_capital": 10000.0,
                "risk_per_trade": 0.01,
                "skip_if_below_min_volume": True,
            },
        )

        self.assertEqual(len(sized), 2)
        self.assertIn("lots", sized.columns)
        self.assertIn("pnl_money", sized.columns)
        self.assertIn("commission_total", sized.columns)
        self.assertTrue(np.allclose(sized["lots"].to_numpy(), [0.06, 0.06]))
        self.assertAlmostEqual(float(sized["commission_total"].sum()), 0.72, places=2)
        self.assertAlmostEqual(float(sized["pnl_money_gross"].sum()), 314.16, places=2)
        self.assertAlmostEqual(float(sized["pnl_money"].sum()), 313.44, places=2)
        self.assertTrue((sized["balance_before_entry"] == 10000.0).all())

    def test_index_has_zero_commission_in_fpmarkets_raw_model(self):
        index = pd.date_range("2025-01-01", periods=1, freq="h")
        trades = pd.DataFrame({
            "symbol": ["GER40"],
            "strategy": ["macd_breakout"],
            "entry_rule": ["macd_breakout"],
            "direction": [1],
            "setup_id": [1],
            "tp_mult": [1.0],
            "size_fraction": [1.0],
            "entry_time": [index[0]],
            "exit_time": [index[0]],
            "entry_price": [100.0],
            "stop_price": [90.0],
            "exit_price": [110.0],
            "exit_reason": ["TP"],
            "return_pct": [10.0],
            "weighted_return": [0.0],
            "pnl": [0.0],
        })
        trades = attach_symbol_spec_columns(trades, {
            "digits": 1,
            "point_size": 0.1,
            "trade_tick_size": 0.1,
            "trade_tick_value": 1.0,
            "trade_tick_value_profit": 1.0,
            "trade_tick_value_loss": 1.0,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01,
        })

        sized = apply_risk_position_sizing(trades)
        self.assertEqual(len(sized), 1)
        self.assertAlmostEqual(float(sized["commission_total"].iloc[0]), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()

