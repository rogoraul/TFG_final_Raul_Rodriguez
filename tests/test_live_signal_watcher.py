import unittest

import numpy as np
import pandas as pd

from backtests.common.riskguard import OpenPosition, RiskGuard, RiskGuardConfig
from backtests.enbolsa.live_signal_watcher import (
    LiveSignalWatcherConfig,
    SeenSignalRegistry,
    build_macd_breakout_snapshot,
)


def _watcher_df():
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    df = pd.DataFrame(index=index)
    df["open"] = [108.0, 109.0, 110.0, 111.0]
    df["high"] = [109.0, 110.0, 111.0, 116.0]
    df["low"] = [107.0, 108.0, 109.0, 110.0]
    df["close"] = [108.0, 109.0, 110.0, 112.0]
    df["spread_price"] = 0.10
    df["TENDENCIA_ESTRUCTURAL_H4"] = 1
    df["SYMBOL_CURRENCY_BASE"] = "EUR"
    df["SYMBOL_CURRENCY_PROFIT"] = "USD"

    for prefix in ("LONG", "SHORT"):
        df[f"{prefix}_SETUP_ID"] = 0
        df[f"{prefix}_SETUP_ACTIVE"] = False
        df[f"{prefix}_SETUP_AGE"] = 0
        df[f"{prefix}_W1_START_PRICE"] = np.nan
        df[f"{prefix}_W1_END_PRICE"] = np.nan
        df[f"{prefix}_W1_SIZE"] = np.nan
        df[f"{prefix}_W2_EXTREME_PRICE"] = np.nan
        df[f"{prefix}_W2_RETR_PCT"] = np.nan
        df[f"{prefix}_W2_SWING_PRICE"] = np.nan
        df[f"{prefix}_W2_VALID_80"] = False
        df[f"{prefix}_W2_INVALIDATED"] = False
        df[f"{prefix}_FIB_LEVEL_0.5"] = np.nan
        df[f"{prefix}_FIB_LEVEL_0.618"] = np.nan
        df[f"{prefix}_FIB_LEVEL_0.8"] = np.nan
        df[f"{prefix}_FIB_TOUCH_618"] = False
        df[f"{prefix}_W2_TRENDLINE_BROKEN"] = False
        df[f"{prefix}_TARGET_1.0"] = np.nan
        df[f"{prefix}_TARGET_1.618"] = np.nan

    df["MACD_CROSS_LONG"] = False
    df["MACD_CROSS_SHORT"] = False

    df["LONG_SETUP_ID"] = 7
    df["LONG_SETUP_ACTIVE"] = True
    df["LONG_SETUP_AGE"] = [1, 2, 3, 4]
    df["LONG_W1_START_PRICE"] = 100.0
    df["LONG_W1_END_PRICE"] = 120.0
    df["LONG_W1_SIZE"] = 20.0
    df["LONG_W2_EXTREME_PRICE"] = 107.0
    df["LONG_W2_RETR_PCT"] = 0.65
    df["LONG_W2_SWING_PRICE"] = 107.0
    df["LONG_W2_VALID_80"] = True
    df["LONG_W2_INVALIDATED"] = False
    df["LONG_FIB_LEVEL_0.5"] = 110.0
    df["LONG_FIB_LEVEL_0.618"] = 107.64
    df["LONG_FIB_LEVEL_0.8"] = 104.0
    df["LONG_TARGET_1.0"] = 127.0
    df["LONG_TARGET_1.618"] = 139.36
    return df


class TestLiveSignalWatcher(unittest.TestCase):
    def test_snapshot_emits_new_current_macd_breakout_intent(self):
        df = _watcher_df()
        df.loc[df.index[-1], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[-1], "MACD_CROSS_LONG"] = True
        config = LiveSignalWatcherConfig(timeframe_ltf="H1", timeframe_htf="H4")

        result = build_macd_breakout_snapshot({"EURUSD.r": df}, config=config)

        intents = result["order_intents"]
        self.assertEqual(len(intents), 1)
        self.assertTrue(result["watchlist"].empty)
        self.assertEqual(intents["side"].iloc[0], "BUY")
        self.assertAlmostEqual(float(intents["entry"].iloc[0]), 112.10)
        self.assertAlmostEqual(float(intents["sl"].iloc[0]), 107.0)
        self.assertAlmostEqual(float(intents["tp1"].iloc[0]), 127.0)
        self.assertAlmostEqual(float(intents["tp2"].iloc[0]), 139.36)
        self.assertTrue(bool(intents["riskguard_accepted"].iloc[0]))

    def test_snapshot_does_not_emit_stale_condition_from_previous_bar(self):
        df = _watcher_df()
        df.loc[df.index[-2], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[-2], "MACD_CROSS_LONG"] = True
        config = LiveSignalWatcherConfig(timeframe_ltf="H1", timeframe_htf="H4")

        result = build_macd_breakout_snapshot({"EURUSD.r": df}, config=config)

        latest_long = result["snapshot"][
            (result["snapshot"]["symbol"] == "EURUSD.r")
            & (result["snapshot"]["side"] == "BUY")
        ].iloc[-1]
        self.assertTrue(bool(latest_long["raw_condition_ready"]))
        self.assertFalse(bool(latest_long["fresh_signal"]))
        self.assertEqual(latest_long["signal_state"], "ready_stale")
        self.assertTrue(result["order_intents"].empty)
        self.assertIn("event_key", result["order_intents"].columns)
        self.assertIn("accepted", result["riskguard_decisions"].columns)
        self.assertTrue(result["watchlist"].empty)

    def test_registry_prevents_duplicate_emission(self):
        df = _watcher_df()
        df.loc[df.index[-1], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[-1], "MACD_CROSS_LONG"] = True
        config = LiveSignalWatcherConfig(timeframe_ltf="H1", timeframe_htf="H4")
        first = build_macd_breakout_snapshot({"EURUSD.r": df}, config=config)
        event_key = first["order_intents"]["event_key"].iloc[0]

        result = build_macd_breakout_snapshot(
            {"EURUSD.r": df},
            config=config,
            registry=SeenSignalRegistry(initial_keys=[event_key]),
        )

        latest_long = result["snapshot"][
            (result["snapshot"]["symbol"] == "EURUSD.r")
            & (result["snapshot"]["side"] == "BUY")
        ].iloc[-1]
        self.assertEqual(latest_long["signal_state"], "ready_already_seen")
        self.assertTrue(result["order_intents"].empty)
        self.assertTrue(result["watchlist"].empty)

    def test_order_intent_carries_riskguard_rejection(self):
        df = _watcher_df()
        df.loc[df.index[-1], "LONG_W2_TRENDLINE_BROKEN"] = True
        df.loc[df.index[-1], "MACD_CROSS_LONG"] = True
        config = LiveSignalWatcherConfig(timeframe_ltf="H1", timeframe_htf="H4")
        guard = RiskGuard(RiskGuardConfig(
            initial_capital=10000.0,
            max_total_open_risk_pct=5.0,
            max_symbol_open_risk_pct=5.0,
            max_currency_gross_risk_pct=10.0,
            max_currency_net_risk_pct=10.0,
        ))
        open_positions = [
            OpenPosition("GBPUSD.r", 1, 100.0),
            OpenPosition("AUDJPY.r", 1, 100.0),
            OpenPosition("NZDCAD.r", 1, 100.0),
            OpenPosition("CADCHF.r", 1, 100.0),
            OpenPosition("USDCHF.r", 1, 100.0),
        ]

        result = build_macd_breakout_snapshot(
            {"EURUSD.r": df},
            config=config,
            riskguard=guard,
            open_positions=open_positions,
        )

        intents = result["order_intents"]
        self.assertEqual(len(intents), 1)
        self.assertFalse(bool(intents["riskguard_accepted"].iloc[0]))
        self.assertEqual(intents["riskguard_reason"].iloc[0], "total_open_risk_cap")

    def test_watchlist_keeps_only_live_pre_signal_setups(self):
        df = _watcher_df()
        config = LiveSignalWatcherConfig(timeframe_ltf="H1", timeframe_htf="H4")

        result = build_macd_breakout_snapshot({"EURUSD.r": df}, config=config)

        watchlist = result["watchlist"]
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(watchlist["symbol"].iloc[0], "EURUSD.r")
        self.assertEqual(watchlist["side"].iloc[0], "BUY")
        self.assertEqual(watchlist["watch_state"].iloc[0], "watching_confirmation")
        self.assertEqual(
            watchlist["missing_confirmation"].iloc[0],
            "trendline_break_or_macd_cross_within_memory",
        )
        self.assertAlmostEqual(float(watchlist["w2_swing"].iloc[0]), 107.0)
        self.assertAlmostEqual(float(watchlist["target_1_0"].iloc[0]), 127.0)
        self.assertAlmostEqual(float(watchlist["target_1_618"].iloc[0]), 139.36)
        self.assertIn("event_key", watchlist.columns)


if __name__ == "__main__":
    unittest.main()
