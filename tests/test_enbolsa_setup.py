import unittest

import numpy as np
import pandas as pd

from backtests.enbolsa.market_context import AnalizadorDeContexto


def _base_df():
    index = pd.date_range("2025-01-01", periods=6, freq="h")
    return pd.DataFrame({
        "open": [100, 103, 118, 115, 111, 105],
        "high": [101, 105, 121, 116, 112, 107],
        "low": [99, 102, 117, 112, 108, 99],
        "close": [100, 104, 119, 113, 109, 100],
        "PIVOT_TYPE": [-1, 0, 1, 0, 0, 0],
        "PIVOT_VALUE": [100.0, np.nan, 120.0, np.nan, np.nan, np.nan],
    }, index=index)


class TestSetupsEnbolsa(unittest.TestCase):
    def test_bullish_setup_stays_valid_to_80(self):
        analyzer = AnalizadorDeContexto()
        df = _base_df()
        df.loc[df.index[5], "low"] = 104.0
        df.loc[df.index[5], "close"] = 105.0

        out = analyzer.detectar_setups_enbolsa(df)
        row = out.iloc[-1]

        self.assertEqual(int(row["LONG_SETUP_ID"]), 1)
        self.assertAlmostEqual(row["LONG_W1_START_PRICE"], 100.0)
        self.assertAlmostEqual(row["LONG_W1_END_PRICE"], 120.0)
        self.assertAlmostEqual(row["LONG_W2_RETR_PCT"], 0.8, places=6)
        self.assertTrue(bool(row["LONG_W2_VALID_80"]))
        self.assertFalse(bool(row["LONG_W2_INVALIDATED"]))

    def test_bullish_setup_invalidates_when_origin_breaks(self):
        analyzer = AnalizadorDeContexto()
        df = _base_df()

        out = analyzer.detectar_setups_enbolsa(df)
        row = out.iloc[-1]

        self.assertTrue(bool(row["LONG_W2_INVALIDATED"]))
        self.assertFalse(bool(row["LONG_W2_VALID_80"]))

    def test_bearish_setup_is_mirrored(self):
        analyzer = AnalizadorDeContexto()
        index = pd.date_range("2025-01-01", periods=6, freq="h")
        df = pd.DataFrame({
            "open": [120, 118, 104, 107, 110, 115],
            "high": [121, 119, 105, 110, 113, 116],
            "low": [119, 117, 99, 106, 108, 114],
            "close": [120, 118, 100, 109, 112, 115],
            "PIVOT_TYPE": [1, 0, -1, 0, 0, 0],
            "PIVOT_VALUE": [120.0, np.nan, 100.0, np.nan, np.nan, np.nan],
        }, index=index)

        out = analyzer.detectar_setups_enbolsa(df)
        row = out.iloc[-1]

        self.assertEqual(int(row["SHORT_SETUP_ID"]), 1)
        self.assertAlmostEqual(row["SHORT_W1_START_PRICE"], 120.0)
        self.assertAlmostEqual(row["SHORT_W1_END_PRICE"], 100.0)
        self.assertTrue(row["SHORT_W2_RETR_PCT"] > 0)

    def test_long_w2_trendline_uses_highs_and_requires_close_break(self):
        analyzer = AnalizadorDeContexto()
        index = pd.date_range("2025-01-01", periods=6, freq="h")
        df = pd.DataFrame({
            "open": [100, 103, 110, 109, 110, 107],
            "high": [101, 104, 121, 116, 112, 130],
            "low": [99, 102, 117, 111, 107, 106],
            "close": [100, 103, 110, 109, 110, 108.5],
            "PIVOT_TYPE": [-1, 0, 1, 0, 0, 0],
            "PIVOT_VALUE": [100.0, np.nan, 120.0, np.nan, np.nan, np.nan],
        }, index=index)

        out = analyzer.detectar_setups_enbolsa(df)

        self.assertTrue(bool(out.iloc[-1]["LONG_W2_TRENDLINE_BROKEN"]))

        wick_only = df.copy()
        wick_only.loc[wick_only.index[-1], "close"] = 107.0
        out_wick = analyzer.detectar_setups_enbolsa(wick_only)

        self.assertFalse(bool(out_wick.iloc[-1]["LONG_W2_TRENDLINE_BROKEN"]))

    def test_short_w2_trendline_uses_lows_and_requires_close_break(self):
        analyzer = AnalizadorDeContexto()
        index = pd.date_range("2025-01-01", periods=6, freq="h")
        df = pd.DataFrame({
            "open": [120, 117, 110, 111, 110, 113],
            "high": [121, 119, 105, 112, 113, 114],
            "low": [119, 117, 99, 104, 108, 80],
            "close": [120, 117, 110, 111, 110, 111],
            "PIVOT_TYPE": [1, 0, -1, 0, 0, 0],
            "PIVOT_VALUE": [120.0, np.nan, 100.0, np.nan, np.nan, np.nan],
        }, index=index)

        out = analyzer.detectar_setups_enbolsa(df)

        self.assertTrue(bool(out.iloc[-1]["SHORT_W2_TRENDLINE_BROKEN"]))

        wick_only = df.copy()
        wick_only.loc[wick_only.index[-1], "close"] = 113.0
        out_wick = analyzer.detectar_setups_enbolsa(wick_only)

        self.assertFalse(bool(out_wick.iloc[-1]["SHORT_W2_TRENDLINE_BROKEN"]))


if __name__ == "__main__":
    unittest.main()

