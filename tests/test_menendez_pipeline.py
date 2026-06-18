import unittest

import numpy as np
import pandas as pd

from backtests.menendez.menendez_context import MenendezContextAnalyzer, SegmentInfo
from backtests.menendez.menendez_indicators import MenendezIndicatorEngine
from backtests.menendez.menendez_pipeline import (
    construir_signal_funnel,
    construir_screener_rows,
    construir_order_intents,
    extraer_operaciones_resultado,
    extraer_indicator_snapshot,
    extraer_ventana_trade,
    generar_auditoria_riesgo,
    resumir_embudo_senales,
    simular_estrategia_portfolio,
)
from backtests.common.position_sizing import attach_symbol_spec_columns


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


def _context_frame_valid_long():
    index = pd.date_range("2025-01-01", periods=10, freq="30min")
    df = pd.DataFrame(index=index)
    df["open"] = [100, 102, 102.5, 101.8, 102, 108, 111, 108, 109, 112]
    df["high"] = [103, 103, 102.8, 102.0, 108, 112, 111, 108, 110, 114]
    df["low"] = [100, 101.5, 101.2, 101.0, 102, 107, 108, 106.5, 108, 111]
    df["close"] = [102, 102.5, 101.8, 101.5, 108, 111, 108.5, 107.0, 109.0, 113.0]
    df["spread_price"] = 0.0

    df["PSAR_POLARITY"] = [1, 1, -1, -1, 1, 1, -1, -1, 1, 1]
    df["PSAR_FLIP_LONG"] = [False, False, False, False, True, False, False, False, True, False]
    df["PSAR_FLIP_SHORT"] = [False, False, True, False, False, False, True, False, False, False]
    df["H4_ATTRACTOR_DIR"] = 1
    df["H4_MACD_NEUTRAL"] = False
    df["H4_STANDBY"] = False
    df["H4_PSAR_FLIP_EVENT"] = False
    df["H4_PSAR_FLIP_COUNT_WINDOW"] = 0
    df["H4_PSAR_LATERAL"] = False
    df["H4_ATTRACTOR_TREND_OK"] = True
    df["H4_ATTRACTOR_MACD_OK"] = True
    df["H4_MACD_ZLR_RELEVANT"] = False
    df["MACD_HIST"] = [0.002, 0.002, -0.001, -0.001, 0.002, 0.003, -0.0005, 0.0005, 0.002, 0.003]
    df["SMA_21"] = [101.0, 101.5, 101.8, 102.0, 103.0, 105.0, 107.6, 107.2, 108.0, 109.5]
    df["SMA_50"] = [99.5, 100.0, 100.4, 100.8, 101.5, 103.0, 106.9, 106.8, 107.2, 108.0]
    df["STOCH_K"] = [60, 55, 45, 35, 70, 75, 18, 15, 25, 60]
    df["STOCH_D"] = [58, 54, 44, 34, 68, 72, 20, 18, 20, 45]
    df["STOCH_CROSS_UP"] = [False, False, False, False, False, False, False, False, True, False]
    df["STOCH_CROSS_DOWN"] = False
    df["BB_UPPER"] = [120] * len(df)
    df["BB_LOWER"] = [90] * len(df)
    df["D_PIVOT"] = [108] * len(df)
    df["D_R1"] = [112.5] * len(df)
    df["D_R2"] = [116.0] * len(df)
    df["W_PIVOT"] = [109] * len(df)
    df["W_R1"] = [114] * len(df)
    df["W_R2"] = [118] * len(df)
    df["W_S1"] = [98] * len(df)
    df["W_S2"] = [95] * len(df)
    df["D_S1"] = [99] * len(df)
    df["D_S2"] = [97] * len(df)
    return df


def _pipeline_frame():
    index = pd.date_range("2025-01-01", periods=5, freq="30min")
    df = pd.DataFrame(index=index)
    df["open"] = [1.1000, 1.1010, 1.1015, 1.1025, 1.1030]
    df["high"] = [1.1010, 1.1020, 1.1040, 1.1045, 1.1040]
    df["low"] = [1.0995, 1.1008, 1.1010, 1.1020, 1.1020]
    df["close"] = [1.1005, 1.1015, 1.1030, 1.1035, 1.1030]
    df["spread_price"] = [0.0, 0.0001, 0.0001, 0.0001, 0.0001]
    df = attach_symbol_spec_columns(df, _base_symbol_spec())

    default_bool = False
    for col in (
        "ENTRY_READY", "FAN_BREAKOUT", "MACD_TRIGGER", "STOCH_TRIGGER",
        "H4_MACD_NEUTRAL", "H4_STANDBY", "H4_PSAR_FLIP_EVENT", "H4_PSAR_LATERAL",
        "H4_MACD_ZLR_BULL", "H4_MACD_ZLR_BEAR", "H4_MACD_ZLR_RELEVANT",
        "H4_ATTRACTOR_TREND_OK", "H4_ATTRACTOR_MACD_OK", "X_POSSIBLE_COMPOSITE",
    ):
        df[col] = default_bool

    for col in (
        "H4_ATTRACTOR_DIR", "ENTRY_DIR", "BASE_CHANNEL_STATE", "DECEL_CHANNEL_STATE",
        "FRACTAL_SEGMENT_COUNT", "SETUP_DIR", "X_SEGMENT_COUNT", "H4_PSAR_FLIP_COUNT_WINDOW",
    ):
        df[col] = 0

    for col in (
        "W_ID", "X_ID", "RETRACE_RATIO", "SL_PRICE", "TP_PRICE", "RR_RATIO",
        "TARGET_0.854", "TARGET_1.0", "TARGET_1.236", "TARGET_1.618",
        "W_START_PRICE", "W_END_PRICE", "X_EXTREME_PRICE", "SETUP_ID", "TARGET_EXTENSION",
        "X_EP_DISTANCE_SMA21", "X_EP_DISTANCE_SMA50",
    ):
        df[col] = np.nan

    df["FRACTAL_EQUIVALENT_CLASS"] = "OTHER"
    df["TP_SOURCE"] = ""
    df["W_START"] = pd.NaT
    df["W_END"] = pd.NaT
    df["X_END"] = pd.NaT
    df["W_EP_TIME"] = pd.NaT
    df["X_EP_TIME"] = pd.NaT

    df.loc[index[1], "ENTRY_READY"] = True
    df.loc[index[1], "ENTRY_DIR"] = 1
    df.loc[index[1], "H4_ATTRACTOR_DIR"] = 1
    df.loc[index[1], "H4_ATTRACTOR_TREND_OK"] = True
    df.loc[index[1], "H4_ATTRACTOR_MACD_OK"] = True
    df.loc[index[1], "H4_MACD_ZLR_RELEVANT"] = True
    df.loc[index[1], "SL_PRICE"] = 1.1000
    df.loc[index[1], "TP_PRICE"] = 1.1040
    df.loc[index[1], "RR_RATIO"] = 1.56
    df.loc[index[1], "SETUP_ID"] = 7
    df.loc[index[1], "TP_SOURCE"] = "D_R1"
    df.loc[index[1], "X_SEGMENT_COUNT"] = 3
    df.loc[index[1], "X_POSSIBLE_COMPOSITE"] = True
    return df


def _context_frame_valid_short():
    source = _context_frame_valid_long()
    anchor = 220.0
    df = pd.DataFrame(index=source.index)
    df["open"] = anchor - source["open"]
    df["high"] = anchor - source["low"]
    df["low"] = anchor - source["high"]
    df["close"] = anchor - source["close"]
    df["spread_price"] = source["spread_price"]
    df["PSAR_POLARITY"] = -source["PSAR_POLARITY"]
    df["H4_ATTRACTOR_DIR"] = -1
    df["H4_MACD_NEUTRAL"] = False
    df["H4_STANDBY"] = False
    df["H4_PSAR_FLIP_EVENT"] = False
    df["H4_PSAR_FLIP_COUNT_WINDOW"] = 0
    df["H4_PSAR_LATERAL"] = False
    df["H4_ATTRACTOR_STAGE"] = "H4_SHORT_READY"
    df["H4_ATTRACTOR_BLOCK_REASON"] = ""
    df["MACD_HIST"] = -source["MACD_HIST"]
    df["STOCH_K"] = 100.0 - source["STOCH_K"]
    df["STOCH_D"] = 100.0 - source["STOCH_D"]
    df["STOCH_CROSS_UP"] = source["STOCH_CROSS_DOWN"]
    df["STOCH_CROSS_DOWN"] = source["STOCH_CROSS_UP"]
    df["BB_UPPER"] = anchor - source["BB_LOWER"]
    df["BB_LOWER"] = anchor - source["BB_UPPER"]
    for col in ("D_PIVOT", "D_R1", "D_R2", "W_PIVOT", "W_R1", "W_R2", "W_S1", "W_S2", "D_S1", "D_S2"):
        df[col] = anchor - source[col]
    return df


def _context_frame_late_breakout():
    index = pd.date_range("2025-01-01", periods=12, freq="30min")
    df = pd.DataFrame(index=index)
    df["open"] = [100, 102, 102.5, 101.8, 102, 108, 111, 108, 106.8, 107.0, 107.5, 109.5]
    df["high"] = [103, 103, 102.8, 102.0, 108, 112, 111, 108, 107.2, 107.6, 108.4, 111.5]
    df["low"] = [100, 101.5, 101.2, 101.0, 102, 107, 108, 106.5, 106.2, 106.4, 106.9, 108.8]
    df["close"] = [102, 102.5, 101.8, 101.5, 108, 111, 108.5, 107.0, 106.9, 107.1, 107.8, 111.0]
    df["spread_price"] = 0.0
    df["PSAR_POLARITY"] = [1, 1, -1, -1, 1, 1, -1, -1, 1, 1, 1, 1]
    df["PSAR_FLIP_LONG"] = [False, False, False, False, True, False, False, False, True, False, False, False]
    df["PSAR_FLIP_SHORT"] = [False, False, True, False, False, False, True, False, False, False, False, False]
    df["H4_ATTRACTOR_DIR"] = 1
    df["H4_MACD_NEUTRAL"] = False
    df["H4_STANDBY"] = False
    df["H4_PSAR_FLIP_EVENT"] = False
    df["H4_PSAR_FLIP_COUNT_WINDOW"] = 0
    df["H4_PSAR_LATERAL"] = False
    df["H4_ATTRACTOR_TREND_OK"] = True
    df["H4_ATTRACTOR_MACD_OK"] = True
    df["H4_MACD_ZLR_RELEVANT"] = False
    df["H4_ATTRACTOR_STAGE"] = "H4_LONG_READY"
    df["H4_ATTRACTOR_BLOCK_REASON"] = ""
    df["MACD_HIST"] = [0.002, 0.002, -0.001, -0.001, 0.002, 0.003, -0.0005, -0.0002, -0.0001, 0.0002, 0.0004, 0.002]
    df["STOCH_K"] = [60, 55, 45, 35, 70, 75, 18, 15, 18, 19, 21, 45]
    df["STOCH_D"] = [58, 54, 44, 34, 68, 72, 20, 18, 19, 20, 20, 30]
    df["STOCH_CROSS_UP"] = [False] * 11 + [True]
    df["STOCH_CROSS_DOWN"] = False
    df["BB_UPPER"] = [120] * len(df)
    df["BB_LOWER"] = [90] * len(df)
    df["D_PIVOT"] = [108] * len(df)
    df["D_R1"] = [116.0] * len(df)
    df["D_R2"] = [120.0] * len(df)
    df["W_PIVOT"] = [109] * len(df)
    df["W_R1"] = [117] * len(df)
    df["W_R2"] = [121] * len(df)
    df["W_S1"] = [98] * len(df)
    df["W_S2"] = [95] * len(df)
    df["D_S1"] = [99] * len(df)
    df["D_S2"] = [97] * len(df)
    return df


def _context_frame_composite_x_long():
    index = pd.date_range("2025-02-01", periods=10, freq="30min")
    df = pd.DataFrame(index=index)
    df["open"] = [100.0, 105.0, 111.0, 108.0, 107.0, 109.0, 110.5, 109.2, 109.1, 110.2]
    df["high"] = [106.0, 112.0, 111.5, 109.0, 109.5, 111.0, 110.8, 109.5, 110.5, 114.0]
    df["low"] = [99.5, 104.0, 107.0, 106.5, 106.5, 108.5, 109.0, 108.8, 108.9, 109.8]
    df["close"] = [105.0, 111.0, 108.0, 107.0, 109.0, 110.5, 109.2, 109.0, 110.2, 113.0]
    df["spread_price"] = 0.0

    df["PSAR_POLARITY"] = [1, 1, -1, -1, 1, 1, -1, -1, 1, 1]
    df["PSAR_FLIP_LONG"] = [False, False, False, False, True, False, False, False, True, False]
    df["PSAR_FLIP_SHORT"] = [False, False, True, False, False, False, True, False, False, False]
    df["H4_ATTRACTOR_DIR"] = 1
    df["H4_MACD_NEUTRAL"] = False
    df["H4_STANDBY"] = False
    df["H4_PSAR_FLIP_EVENT"] = False
    df["H4_PSAR_FLIP_COUNT_WINDOW"] = 0
    df["H4_PSAR_LATERAL"] = False
    df["H4_ATTRACTOR_TREND_OK"] = True
    df["H4_ATTRACTOR_MACD_OK"] = True
    df["H4_MACD_ZLR_RELEVANT"] = False
    df["H4_ATTRACTOR_STAGE"] = "H4_LONG_READY"
    df["H4_ATTRACTOR_BLOCK_REASON"] = ""
    df["MACD_HIST"] = [0.0020, 0.0020, -0.0010, -0.0008, 0.0002, 0.0004, -0.0009, -0.0005, 0.0015, 0.0022]
    df["SMA_21"] = [101.0, 103.0, 108.2, 107.1, 107.8, 108.6, 109.0, 108.9, 109.2, 110.0]
    df["SMA_50"] = [100.0, 102.0, 107.6, 107.0, 107.4, 108.0, 108.8, 108.7, 108.9, 109.4]
    df["STOCH_K"] = [60, 65, 30, 20, 35, 40, 22, 18, 26, 55]
    df["STOCH_D"] = [58, 62, 32, 24, 33, 38, 24, 20, 21, 40]
    df["STOCH_CROSS_UP"] = [False, False, False, False, False, False, False, False, True, False]
    df["STOCH_CROSS_DOWN"] = False
    df["BB_UPPER"] = [120.0] * len(df)
    df["BB_LOWER"] = [95.0] * len(df)
    df["D_PIVOT"] = [109.0] * len(df)
    df["D_R1"] = [114.5] * len(df)
    df["D_R2"] = [118.0] * len(df)
    df["W_PIVOT"] = [109.5] * len(df)
    df["W_R1"] = [115.0] * len(df)
    df["W_R2"] = [119.0] * len(df)
    df["W_S1"] = [102.0] * len(df)
    df["W_S2"] = [99.0] * len(df)
    df["D_S1"] = [103.0] * len(df)
    df["D_S2"] = [100.0] * len(df)
    return df


class TestMenendezPipeline(unittest.TestCase):
    def test_indicator_engine_adds_expected_columns(self):
        index = pd.date_range("2025-01-01", periods=80, freq="30min")
        df = pd.DataFrame(index=index)
        base = np.linspace(1.08, 1.12, len(index))
        df["open"] = base
        df["high"] = base + 0.0015
        df["low"] = base - 0.0015
        df["close"] = base + np.sin(np.linspace(0, 8, len(index))) * 0.0005

        result = MenendezIndicatorEngine().aplicar_todo(df)

        expected_cols = {
            "PSAR", "PSAR_POLARITY", "PSAR_FLIP_LONG", "PSAR_FLIP_SHORT",
            "SMA_5", "SMA_8", "SMA_13", "SMA_21", "SMA_50", "SMA_200", "SMA_21_SLOPE",
            "SMA_5_8_CROSS_UP", "SMA_5_8_CROSS_DOWN",
            "SMA_8_13_CROSS_UP", "SMA_8_13_CROSS_DOWN",
            "SMA_13_21_CROSS_UP", "SMA_13_21_CROSS_DOWN",
            "SMA_50_200_CROSS_UP", "SMA_50_200_CROSS_DOWN",
            "BULLISH_FAN", "BEARISH_FAN", "MACD_LINE", "MACD_SIGNAL", "MACD_HIST",
            "STOCH_K", "STOCH_D", "STOCH_CROSS_UP", "STOCH_CROSS_DOWN",
            "BB_UPPER", "BB_LOWER", "D_PIVOT", "W_PIVOT",
        }
        self.assertTrue(expected_cols.issubset(set(result.columns)))
        self.assertTrue(set(result["PSAR_POLARITY"].dropna().astype(int).unique()).issubset({-1, 1}))

    def test_htf_attractor_computes_standby_diagnostically_without_filtering_by_default(self):
        index = pd.date_range("2025-01-01", periods=15, freq="4h")
        df = pd.DataFrame(index=index)
        df["PSAR_POLARITY"] = 1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["SMA_21_SLOPE"] = 0.1
        df["MACD_HIST"] = [0.0002] * 13 + [0.002, 0.003]

        result = MenendezContextAnalyzer().calcular_atractor_htf(df)

        self.assertTrue(bool(result["STANDBY"].iloc[11]))
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[11]), 0)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[11]), "H4_MACD_NEUTRAL")
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 1)

    def test_htf_attractor_can_optionally_filter_with_standby_rule(self):
        index = pd.date_range("2025-01-01", periods=15, freq="4h")
        df = pd.DataFrame(index=index)
        df["PSAR_POLARITY"] = 1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["SMA_21_SLOPE"] = 0.1
        df["MACD_HIST"] = [0.0002] * 13 + [0.002, 0.003]

        result = MenendezContextAnalyzer(
            use_h4_standby_filter=True,
            macd_standby_bars=12,
        ).calcular_atractor_htf(df)

        self.assertTrue(bool(result["STANDBY"].iloc[11]))
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[11]), "H4_STANDBY")
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 1)

    def test_htf_attractor_marks_psar_lateral_diagnostically_without_blocking_by_default(self):
        index = pd.date_range("2025-01-01", periods=8, freq="4h")
        df = pd.DataFrame(index=index)
        df["close"] = [1.2000, 1.1990, 1.2010, 1.1985, 1.2020, 1.2015, 1.2030, 1.2040]
        df["SMA_200"] = [1.1900] * len(df)
        df["PSAR_POLARITY"] = [1, -1, 1, -1, 1, 1, 1, 1]
        df["PSAR_FLIP_LONG"] = [False, False, True, False, True, False, False, False]
        df["PSAR_FLIP_SHORT"] = [False, True, False, True, False, False, False, False]
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = True
        df["SMA_21_SLOPE"] = 0.01
        df["MACD_HIST"] = [0.0020] * len(df)

        result = MenendezContextAnalyzer(
            h4_trend_filter="sma200_primary",
        ).calcular_atractor_htf(df)

        self.assertTrue(bool(result["PSAR_LATERAL"].iloc[4]))
        self.assertTrue(bool(result["PSAR_LATERAL"].iloc[-1]))
        self.assertEqual(int(result["PSAR_FLIP_COUNT_WINDOW"].iloc[4]), 4)
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 1)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[-1]), "")

    def test_htf_attractor_can_block_lateral_psar_ranges_experimentally(self):
        index = pd.date_range("2025-01-01", periods=8, freq="4h")
        df = pd.DataFrame(index=index)
        df["close"] = [1.2000, 1.1990, 1.2010, 1.1985, 1.2020, 1.2015, 1.2030, 1.2040]
        df["SMA_200"] = [1.1900] * len(df)
        df["PSAR_POLARITY"] = [1, -1, 1, -1, 1, 1, 1, 1]
        df["PSAR_FLIP_LONG"] = [False, False, True, False, True, False, False, False]
        df["PSAR_FLIP_SHORT"] = [False, True, False, True, False, False, False, False]
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = True
        df["SMA_21_SLOPE"] = 0.01
        df["MACD_HIST"] = [0.0020] * len(df)

        result = MenendezContextAnalyzer(
            h4_trend_filter="sma200_primary",
            use_h4_psar_lateral_filter=True,
            psar_lateral_window_bars=8,
            psar_lateral_min_flips=3,
        ).calcular_atractor_htf(df)

        self.assertTrue(bool(result["PSAR_LATERAL"].iloc[-1]))
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 0)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[-1]), "H4_PSAR_LATERAL")

    def test_htf_attractor_can_use_sma200_position_as_trend_filter(self):
        index = pd.date_range("2025-01-01", periods=220, freq="4h")
        close = np.linspace(1.10, 1.30, len(index))
        df = pd.DataFrame(index=index)
        df["close"] = close
        df["PSAR_POLARITY"] = 1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["SMA_21_SLOPE"] = -0.01
        df["SMA_200"] = pd.Series(close, index=index).rolling(200, min_periods=200).mean()
        df["MACD_HIST"] = 0.002

        result = MenendezContextAnalyzer(h4_trend_filter="sma200_position").calcular_atractor_htf(df)
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 1)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[-1]), "")

    def test_htf_attractor_zlr_allows_zero_line_reversal_inside_neutral_zone(self):
        index = pd.date_range("2025-01-01", periods=3, freq="4h")
        df = pd.DataFrame(index=index)
        df["close"] = [1.1000, 1.1010, 1.1020]
        df["PSAR_POLARITY"] = 1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["SMA_21_SLOPE"] = 0.01
        df["MACD_HIST"] = [-0.0002, 0.0001, 0.0002]

        result = MenendezContextAnalyzer(
            use_zlr_as_macd_ok=True,
            zlr_memory_bars=1,
        ).calcular_atractor_htf(df)

        self.assertTrue(bool(result["MACD_NEUTRAL"].iloc[1]))
        self.assertTrue(bool(result["MACD_ZLR_BULL"].iloc[1]))
        self.assertTrue(bool(result["MACD_ZLR_RELEVANT"].iloc[1]))
        self.assertTrue(bool(result["ATTRACTOR_MACD_OK"].iloc[1]))
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[1]), 1)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[1]), "")

    def test_htf_attractor_sma200_primary_ignores_macd_neutral_and_sma21_slope(self):
        index = pd.date_range("2025-01-01", periods=3, freq="4h")
        df = pd.DataFrame(index=index)
        df["close"] = [1.2000, 1.2010, 1.2020]
        df["SMA_200"] = [1.1900, 1.1910, 1.1920]
        df["PSAR_POLARITY"] = 1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["SMA_21_SLOPE"] = -0.05
        df["MACD_HIST"] = [0.0002, 0.0002, 0.0002]

        result = MenendezContextAnalyzer(
            h4_trend_filter="sma200_primary",
            use_zlr_as_macd_ok=False,
        ).calcular_atractor_htf(df)

        self.assertTrue(bool(result["MACD_NEUTRAL"].iloc[-1]))
        self.assertFalse(bool(result["ATTRACTOR_MACD_OK"].iloc[-1]))
        self.assertTrue(bool(result["ATTRACTOR_TREND_OK"].iloc[-1]))
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 1)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[-1]), "")

    def test_htf_attractor_sma200_primary_reports_sma200_block_reason(self):
        index = pd.date_range("2025-01-01", periods=3, freq="4h")
        df = pd.DataFrame(index=index)
        df["close"] = [1.1800, 1.1810, 1.1820]
        df["SMA_200"] = [1.1900, 1.1910, 1.1920]
        df["PSAR_POLARITY"] = 1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["SMA_21_SLOPE"] = 0.05
        df["MACD_HIST"] = [0.0020, 0.0020, 0.0020]

        result = MenendezContextAnalyzer(
            h4_trend_filter="sma200_primary",
        ).calcular_atractor_htf(df)

        self.assertFalse(bool(result["ATTRACTOR_TREND_OK"].iloc[-1]))
        self.assertEqual(int(result["ATTRACTOR_DIR"].iloc[-1]), 0)
        self.assertEqual(str(result["ATTRACTOR_BLOCK_REASON"].iloc[-1]), "H4_SMA200_BULL_FILTER_MISSING")

    def test_context_marks_valid_long_entry_and_motor_equivalent(self):
        df = _context_frame_valid_long()
        result = MenendezContextAnalyzer().procesar_contexto_m30(df)

        row = result.iloc[8]
        self.assertTrue(bool(row["ENTRY_READY"]))
        self.assertEqual(int(row["ENTRY_DIR"]), 1)
        self.assertAlmostEqual(float(row["RETRACE_RATIO"]), 0.55, places=2)
        self.assertEqual(int(row["FRACTAL_SEGMENT_COUNT"]), 5)
        self.assertEqual(str(row["FRACTAL_EQUIVALENT_CLASS"]), "MOTOR_EQUIVALENT")
        self.assertEqual(str(row["TP_SOURCE"]), "D_R1")

    def test_context_uses_segment_extreme_point_and_audits_x_ma_support(self):
        df = _context_frame_valid_long()
        result = MenendezContextAnalyzer().procesar_contexto_m30(df)

        row = result.iloc[8]
        self.assertEqual(pd.Timestamp(row["W_EP_TIME"]), pd.Timestamp(df.index[5]))
        self.assertEqual(pd.Timestamp(row["X_EP_TIME"]), pd.Timestamp(df.index[7]))
        self.assertAlmostEqual(float(row["W_END_PRICE"]), 112.0, places=6)
        self.assertAlmostEqual(float(row["X_EXTREME_PRICE"]), 106.5, places=6)
        self.assertTrue(bool(row["X_TOUCH_SMA21"]))
        self.assertTrue(bool(row["X_TOUCH_SMA50"]))
        self.assertEqual(int(row["X_END_CLOSE_VS_SMA21"]), -1)
        self.assertEqual(int(row["X_END_CLOSE_VS_SMA50"]), 1)
        self.assertTrue(np.isfinite(float(row["X_EP_DISTANCE_SMA21"])))
        self.assertTrue(np.isfinite(float(row["X_EP_DISTANCE_SMA50"])))

    def test_context_marks_possible_composite_x_without_changing_faithful_setup(self):
        df = _context_frame_composite_x_long()
        result = MenendezContextAnalyzer(
            entry_primary_trigger_mode="fan_or_psar",
            entry_momentum_confirm_mode="macd_or_stoch",
        ).procesar_contexto_m30(df)

        row = result.iloc[8]
        self.assertTrue(bool(row["SETUP_CANDIDATE"]))
        self.assertEqual(int(row["X_SEGMENT_COUNT"]), 1)
        self.assertTrue(bool(row["X_POSSIBLE_COMPOSITE"]))
        self.assertEqual(float(row["X_ID"]), 4.0)
        self.assertEqual(pd.Timestamp(row["X_END"]), pd.Timestamp(df.index[7]))

    def test_context_composite_x_uses_full_group_consistently(self):
        df = _context_frame_composite_x_long()
        result = MenendezContextAnalyzer(
            use_composite_x=True,
            composite_x_max_segments=5,
            entry_primary_trigger_mode="fan_or_psar",
            entry_momentum_confirm_mode="macd_or_stoch",
        ).procesar_contexto_m30(df)

        row = result.iloc[8]
        self.assertTrue(bool(row["SETUP_CANDIDATE"]))
        self.assertEqual(int(row["X_SEGMENT_COUNT"]), 3)
        self.assertTrue(bool(row["X_POSSIBLE_COMPOSITE"]))
        self.assertEqual(float(row["X_ID"]), 2.0)
        self.assertEqual(pd.Timestamp(row["X_END"]), pd.Timestamp(df.index[7]))
        self.assertAlmostEqual(float(row["X_EXTREME_PRICE"]), 106.5, places=6)
        self.assertAlmostEqual(float(row["RETRACE_RATIO"]), 0.44, places=2)
        self.assertTrue(bool(row["X_TOUCH_SMA21"]))
        self.assertTrue(bool(row["X_TOUCH_SMA50"]))

    def test_context_composite_x_does_not_select_motor_count_five_by_default(self):
        base_time = pd.Timestamp("2025-03-01")

        def segment(seg_id, direction, low, high):
            start = base_time + pd.Timedelta(minutes=30 * seg_id)
            return SegmentInfo(
                seg_id=seg_id,
                direction=direction,
                start_pos=seg_id,
                end_pos=seg_id,
                start_time=start,
                end_time=start,
                start_close=(low + high) / 2,
                end_close=(low + high) / 2,
                low=low,
                high=high,
                low_time=start,
                high_time=start,
            )

        segments = [
            segment(0, 1, 100.0, 110.0),
            segment(1, -1, 106.0, 109.0),
            segment(2, 1, 107.0, 111.0),
            segment(3, -1, 105.0, 108.0),
            segment(4, 1, 106.0, 109.0),
            segment(5, -1, 104.0, 107.0),
            segment(6, 1, 106.0, 112.0),
        ]
        analyzer = MenendezContextAnalyzer(
            use_composite_x=True,
            composite_x_max_segments=5,
        )

        composite = analyzer._find_composite_x(segments, entry_idx=6, h4_dir=1)

        self.assertIsNotNone(composite)
        self.assertEqual(composite[-1], 3)

    def test_context_invalidates_when_retracement_exceeds_limit(self):
        df = _context_frame_valid_long()
        df.loc[df.index[7], "low"] = 105.5
        df.loc[df.index[7], "close"] = 105.8

        result = MenendezContextAnalyzer().procesar_contexto_m30(df)
        row = result.iloc[8]
        self.assertFalse(bool(row["ENTRY_READY"]))
        self.assertGreater(float(row["RETRACE_RATIO"]), 0.618)
        self.assertEqual(int(row["DECEL_CHANNEL_STATE"]), -1)
        self.assertEqual(str(row["BLOCK_REASON"]), "RETRACE_TOO_DEEP")

    def test_context_marks_valid_short_entry(self):
        df = _context_frame_valid_short()
        result = MenendezContextAnalyzer().procesar_contexto_m30(df)

        row = result.iloc[8]
        self.assertTrue(bool(row["ENTRY_READY"]))
        self.assertEqual(int(row["ENTRY_DIR"]), -1)
        self.assertEqual(str(row["SETUP_STATUS"]), "ENTRY_READY")
        self.assertEqual(str(row["FRACTAL_EQUIVALENT_CLASS"]), "MOTOR_EQUIVALENT")

    def test_context_blocks_when_fan_breakout_is_missing(self):
        df = _context_frame_valid_long()
        df.loc[df.index[8], "close"] = 100.0

        result = MenendezContextAnalyzer().procesar_contexto_m30(df)
        row = result.iloc[8]
        self.assertFalse(bool(row["ENTRY_READY"]))
        self.assertEqual(str(row["SETUP_STATUS"]), "WAIT_FAN_BREAKOUT")
        self.assertEqual(str(row["BLOCK_REASON"]), "FAN_BREAKOUT_MISSING")

    def test_context_can_capture_late_breakout_in_segment_mode(self):
        strict_result = MenendezContextAnalyzer(signal_memory_bars=2).procesar_contexto_m30(_context_frame_late_breakout())
        relaxed_result = MenendezContextAnalyzer(
            signal_memory_bars=2,
            candidate_window_mode="segment",
            candidate_window_max_bars=12,
        ).procesar_contexto_m30(_context_frame_late_breakout())

        self.assertEqual(int(strict_result["ENTRY_READY"].sum()), 0)
        self.assertEqual(str(strict_result.iloc[-1]["SETUP_STATUS"]), "HTF_READY")
        self.assertEqual(str(relaxed_result.iloc[-1]["SETUP_STATUS"]), "WAIT_RR")
        self.assertTrue(bool(relaxed_result.iloc[-1]["MACD_TRIGGER"]))
        self.assertTrue(bool(relaxed_result.iloc[-1]["STOCH_TRIGGER"]))

    def test_context_trigger_or_allows_psar_plus_single_momentum_confirmation(self):
        df = _context_frame_valid_long()
        df["PSAR_FLIP_LONG"] = False
        df["PSAR_FLIP_SHORT"] = False
        df.loc[df.index[8], "PSAR_FLIP_LONG"] = True
        df.loc[df.index[8], "close"] = 106.8
        df.loc[df.index[8], "MACD_HIST"] = 0.0003

        strict_result = MenendezContextAnalyzer().procesar_contexto_m30(df.copy())
        relaxed_result = MenendezContextAnalyzer(
            entry_primary_trigger_mode="fan_or_psar",
            entry_momentum_confirm_mode="macd_or_stoch",
        ).procesar_contexto_m30(df.copy())

        self.assertFalse(bool(strict_result.iloc[8]["ENTRY_READY"]))
        self.assertFalse(bool(strict_result.iloc[8]["MOMENTUM_CONFIRM"]) if "MOMENTUM_CONFIRM" in strict_result.columns else True)
        self.assertTrue(bool(relaxed_result.iloc[8]["PSAR_TRIGGER"]))
        self.assertTrue(bool(relaxed_result.iloc[8]["PRIMARY_TRIGGER"]))
        self.assertTrue(bool(relaxed_result.iloc[8]["STOCH_TRIGGER"]))
        self.assertFalse(bool(relaxed_result.iloc[8]["MACD_TRIGGER"]))
        self.assertTrue(bool(relaxed_result.iloc[8]["MOMENTUM_CONFIRM"]))
        self.assertTrue(bool(relaxed_result.iloc[8]["ENTRY_READY"]))

    def test_context_macd_memory_allows_recent_macd_confirmation(self):
        df = _context_frame_valid_long()
        df["STOCH_CROSS_UP"] = False
        df["STOCH_K"] = 55.0
        df["STOCH_D"] = 54.0
        df.loc[df.index[7], "MACD_HIST"] = 0.0022
        df.loc[df.index[8], "MACD_HIST"] = 0.0002

        base_result = MenendezContextAnalyzer(
            entry_primary_trigger_mode="fan_or_psar",
            entry_momentum_confirm_mode="macd_or_stoch",
            macd_memory_bars=1,
        ).procesar_contexto_m30(df.copy())
        memory_result = MenendezContextAnalyzer(
            entry_primary_trigger_mode="fan_or_psar",
            entry_momentum_confirm_mode="macd_or_stoch",
            macd_memory_bars=4,
        ).procesar_contexto_m30(df.copy())

        self.assertFalse(bool(base_result.iloc[8]["MACD_TRIGGER"]))
        self.assertFalse(bool(base_result.iloc[8]["ENTRY_READY"]))
        self.assertTrue(bool(memory_result.iloc[8]["MACD_TRIGGER"]))
        self.assertTrue(bool(memory_result.iloc[8]["MOMENTUM_CONFIRM"]))
        self.assertTrue(bool(memory_result.iloc[8]["ENTRY_READY"]))

    def test_context_can_exclude_bollinger_from_tp_cluster(self):
        df = _context_frame_valid_long()
        df["D_R1"] = 130.0
        df["D_R2"] = 135.0
        df["W_R1"] = 132.0
        df["W_R2"] = 138.0
        df["BB_UPPER"] = 112.0

        base_result = MenendezContextAnalyzer().procesar_contexto_m30(df.copy())
        no_bb_result = MenendezContextAnalyzer(tp_include_bollinger=False).procesar_contexto_m30(df.copy())

        self.assertEqual(str(base_result.iloc[8]["TP_SOURCE"]), "BB_UPPER")
        self.assertTrue(str(no_bb_result.iloc[8]["TP_SOURCE"]).startswith("FIB_"))

    def test_context_session_filter_can_block_valid_entry_outside_hours(self):
        df = _context_frame_valid_long()
        shifted_index = pd.date_range("2025-01-01 02:00:00", periods=len(df), freq="30min")
        df.index = shifted_index

        base_result = MenendezContextAnalyzer().procesar_contexto_m30(df.copy())
        session_result = MenendezContextAnalyzer(
            entry_primary_trigger_mode="fan_or_psar",
            entry_momentum_confirm_mode="macd_or_stoch",
            session_filter_enabled=True,
            session_start_hour_utc=7,
            session_end_hour_utc=17,
        ).procesar_contexto_m30(df.copy())

        self.assertTrue(bool(base_result.iloc[8]["ENTRY_READY"]))
        self.assertFalse(bool(session_result.iloc[8]["SESSION_OK"]))
        self.assertFalse(bool(session_result.iloc[8]["ENTRY_READY"]))
        self.assertEqual(str(session_result.iloc[8]["BLOCK_REASON"]), "SESSION_FILTER_BLOCKED")

    def test_pipeline_executes_tp_for_long_signal(self):
        df = _pipeline_frame()
        trades = simular_estrategia_portfolio({"EURUSD.r": df})

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades["exit_reason"].iloc[0], "TP")
        self.assertAlmostEqual(trades["entry_price"].iloc[0], 1.1016, places=7)
        self.assertAlmostEqual(trades["exit_price"].iloc[0], 1.1040, places=7)

    def test_pipeline_blocks_signal_when_rr_is_below_threshold(self):
        df = _pipeline_frame()
        df.loc[df.index[1], "RR_RATIO"] = 0.8
        trades = simular_estrategia_portfolio({"EURUSD.r": df})
        self.assertTrue(trades.empty)

    def test_pipeline_parallel_matches_serial(self):
        portfolio = {
            "EURUSD.r": _pipeline_frame(),
            "GBPUSD.r": _pipeline_frame(),
        }
        serial = simular_estrategia_portfolio(portfolio, parallel=False)
        parallel = simular_estrategia_portfolio(portfolio, parallel=True, max_workers=2)

        compare_cols = [
            "symbol", "entry_time", "exit_time", "entry_price", "exit_price",
            "stop_price", "target_price", "exit_reason", "lots", "pnl_money",
        ]
        pd.testing.assert_frame_equal(
            serial[compare_cols].reset_index(drop=True),
            parallel[compare_cols].reset_index(drop=True),
            check_dtype=False,
        )

    def test_resumir_embudo_senales_matches_processed_rows(self):
        processed = MenendezContextAnalyzer().procesar_contexto_m30(_context_frame_valid_long())
        summary = resumir_embudo_senales({"EURUSD.r": processed})
        funnel = construir_signal_funnel({"EURUSD.r": processed})

        row = summary[summary["Activo"] == "EURUSD.r"].iloc[0]
        total = summary[summary["Activo"] == "TOTAL"].iloc[0]

        self.assertEqual(int(row["Velas"]), len(processed))
        self.assertEqual(int(row["ENTRY_READY"]), int(processed["ENTRY_READY"].sum()))
        self.assertEqual(int(total["ENTRY_READY"]), int(processed["ENTRY_READY"].sum()))
        self.assertGreaterEqual(int(row["SETUP_ROWS"]), int(row["ENTRY_READY"]))
        self.assertIn("block_reasons", funnel)
        self.assertIn("status_distribution", funnel)

    def test_operaciones_y_ventana_trade_exponen_columnas_diagnosticas(self):
        portfolio = {"EURUSD.r": _pipeline_frame()}
        trades = simular_estrategia_portfolio(portfolio)
        result = {"trades": {"menendez_core": trades}}

        operaciones = extraer_operaciones_resultado(
            result,
            strategy="menendez_core",
            symbol="EURUSD.r",
        )
        ventana = extraer_ventana_trade(
            portfolio,
            result,
            trade_index=0,
            strategy="menendez_core",
            symbol="EURUSD.r",
            bars_before=1,
            bars_after=1,
        )

        self.assertEqual(len(operaciones), 1)
        self.assertIn("TP_SOURCE", operaciones.columns)
        self.assertIn("RR_RATIO", operaciones.columns)
        self.assertIn("X_SEGMENT_COUNT", operaciones.columns)
        self.assertIn("H4_PSAR_LATERAL", operaciones.columns)
        self.assertIn("H4_MACD_ZLR_RELEVANT", operaciones.columns)
        self.assertIn("TRADE_ENTRY", ventana.columns)
        self.assertIn("H4_PSAR_LATERAL", ventana.columns)
        self.assertIn("X_POSSIBLE_COMPOSITE", ventana.columns)
        self.assertIn("TRADE_TARGET_PRICE", ventana.columns)
        self.assertTrue(bool(ventana["TRADE_ENTRY"].any()))
        self.assertEqual(ventana.attrs["trade"]["symbol"], "EURUSD.r")

    def test_indicator_snapshot_expone_columnas_clave(self):
        df = _context_frame_valid_long().copy()
        df["PSAR"] = np.linspace(100.0, 110.0, len(df))
        df["PSAR_FLIP_LONG"] = False
        df["PSAR_FLIP_SHORT"] = False
        df["SMA_5"] = np.linspace(101.0, 111.0, len(df))
        df["SMA_8"] = np.linspace(100.5, 110.5, len(df))
        df["SMA_13"] = np.linspace(100.0, 110.0, len(df))
        df["SMA_21"] = np.linspace(99.5, 109.5, len(df))
        df["SMA_21_SLOPE"] = 0.1
        df["BULLISH_FAN"] = True
        df["BEARISH_FAN"] = False
        df["MACD_LINE"] = df["MACD_HIST"] + 0.001
        df["MACD_SIGNAL"] = 0.001
        df["BB_MID"] = 105.0
        df["H4_SOURCE_TIME"] = df.index.floor("4h")
        df["H4_ATTRACTOR_STAGE"] = "H4_LONG_READY"
        df["H4_ATTRACTOR_BLOCK_REASON"] = ""

        processed = MenendezContextAnalyzer().procesar_contexto_m30(df)
        snapshot = extraer_indicator_snapshot({"EURUSD.r": processed}, "EURUSD.r", setup_id=4, bars_before=1, bars_after=1)

        self.assertIn("PSAR", snapshot.columns)
        self.assertIn("SMA_21", snapshot.columns)
        self.assertIn("MACD_LINE", snapshot.columns)
        self.assertIn("SETUP_STATUS", snapshot.columns)
        self.assertIn("H4_ATTRACTOR_STAGE", snapshot.columns)
        self.assertIn("H4_PSAR_LATERAL", snapshot.columns)
        self.assertIn("H4_MACD_ZLR_RELEVANT", snapshot.columns)

    def test_generar_auditoria_riesgo_menendez_formula_consistente(self):
        portfolio = {"EURUSD.r": _pipeline_frame()}
        trades = simular_estrategia_portfolio(portfolio)
        result = {"trades": {"menendez_core": trades}}

        audit = generar_auditoria_riesgo(
            result,
            strategy="menendez_core",
            symbol="EURUSD.r",
        )

        self.assertEqual(len(audit), 1)
        self.assertIn("risk_pct_real", audit.columns)
        self.assertIn("expected_loss_at_sl", audit.columns)
        self.assertIn("X_SEGMENT_COUNT", audit.columns)
        self.assertIn("H4_PSAR_LATERAL", audit.columns)
        self.assertIn("H4_MACD_ZLR_RELEVANT", audit.columns)
        self.assertIn("pnl_formula_diff", audit.columns)
        self.assertIn("pnl_net_diff", audit.columns)
        self.assertTrue(np.allclose(audit["pnl_formula_diff"].to_numpy(), 0.0))
        self.assertTrue(np.allclose(audit["pnl_net_diff"].to_numpy(), 0.0))

    def test_screener_y_order_intents_reciclan_columnas_de_contexto(self):
        processed = MenendezContextAnalyzer().procesar_contexto_m30(_context_frame_valid_long())
        processed = attach_symbol_spec_columns(processed, _base_symbol_spec())
        screener = construir_screener_rows({"EURUSD.r": processed}, only_active=True)
        manual_ready = pd.DataFrame([{
            "symbol": "EURUSD.r",
            "timestamp": processed.index[8],
            "setup_state": "ENTRY_READY",
            "last_passed_stage": "ENTRY_READY",
            "entry_ready": True,
            "reason_block": "",
            "dir": 1,
            "entry": 109.0,
            "sl": 106.5,
            "tp": 112.5,
            "rr": 1.4,
            "h4_attractor_dir": 1,
        }])
        intents = construir_order_intents({"EURUSD.r": processed}, screener_rows=manual_ready)

        self.assertIn("setup_state", screener.columns)
        self.assertIn("reason_block", screener.columns)
        self.assertIn("x_segment_count", screener.columns)
        self.assertIn("h4_psar_lateral", screener.columns)
        self.assertIn("h4_macd_zlr_relevant", screener.columns)
        self.assertIn("latest_timestamp", screener.columns)
        self.assertIn("is_current", screener.columns)
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents["side"].iloc[0], "BUY")
        self.assertTrue(np.isfinite(float(intents["volume"].iloc[0])))

    def test_order_intents_default_no_usa_senal_historica_como_actual(self):
        processed = attach_symbol_spec_columns(_pipeline_frame(), _base_symbol_spec())
        historical = construir_screener_rows({"EURUSD.r": processed}, only_active=True)
        current = construir_screener_rows({"EURUSD.r": processed}, current_only=True)
        intents = construir_order_intents({"EURUSD.r": processed})

        self.assertEqual(pd.Timestamp(historical["timestamp"].iloc[0]), processed.index[1])
        self.assertFalse(bool(historical["is_current"].iloc[0]))
        self.assertEqual(pd.Timestamp(current["timestamp"].iloc[0]), processed.index[-1])
        self.assertTrue(bool(current["is_current"].iloc[0]))
        self.assertTrue(intents.empty)


if __name__ == "__main__":
    unittest.main()
