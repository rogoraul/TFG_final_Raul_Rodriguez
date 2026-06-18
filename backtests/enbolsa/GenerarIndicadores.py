"""Indicator engine reused by the historical setup formalization."""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


class GeneradorIndicadores:
    """Generate technical indicators used by the classic setup pipeline.

    Parameters are kept injectable so benchmark experiments can vary them
    without changing the rest of the pipeline.
    """

    def __init__(
        self,
        rsi_len=14,
        atr_len=14,
        ewo_fast=5,
        ewo_slow=35,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        macd_signal_mode='ema',
        ma_short=50,
        ma_long=150,
        ma_type='sma',
        stoch_k=14,
        stoch_d=3,
        stoch_smooth=3,
    ):
        """Store indicator parameters for later DataFrame enrichment."""
        self.rsi_len = rsi_len
        self.atr_len = atr_len
        self.ewo_fast = ewo_fast
        self.ewo_slow = ewo_slow
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.ma_type = ma_type
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.macd_signal_mode = macd_signal_mode.lower()
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d
        self.stoch_smooth = stoch_smooth

    def aplicar_todo(self, df_original: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of OHLC data enriched with all configured indicators."""
        df = df_original.copy()

        df.ta.rsi(length=self.rsi_len, append=True)
        cols_rsi = [c for c in df.columns if c.startswith('RSI_')]
        if cols_rsi:
            df.rename(columns={cols_rsi[0]: 'RSI'}, inplace=True)

        df.ta.true_range(append=True)
        df['ATR'] = ta.sma(df['TRUERANGE_1'], length=self.atr_len)
        df.drop(columns=['TRUERANGE_1'], inplace=True)

        mid_price = (df['high'] + df['low']) / 2
        df['EWO'] = ta.sma(mid_price, length=self.ewo_fast) - ta.sma(mid_price, length=self.ewo_slow)

        macd_line = df.ta.ema(length=self.macd_fast) - df.ta.ema(length=self.macd_slow)
        df['MACD_LINE'] = macd_line
        if self.macd_signal_mode == 'sma':
            df['MACD_SIGNAL'] = ta.sma(macd_line, length=self.macd_signal)
        else:
            df['MACD_SIGNAL'] = ta.ema(macd_line, length=self.macd_signal)

        df['MACD_HISTOGRAMA'] = df['MACD_LINE'] - df['MACD_SIGNAL']
        df['MACD_CROSS_LONG'] = (
            (df['MACD_LINE'] > df['MACD_SIGNAL']) &
            (df['MACD_LINE'].shift(1) <= df['MACD_SIGNAL'].shift(1))
        ).fillna(False)
        df['MACD_CROSS_SHORT'] = (
            (df['MACD_LINE'] < df['MACD_SIGNAL']) &
            (df['MACD_LINE'].shift(1) >= df['MACD_SIGNAL'].shift(1))
        ).fillna(False)

        if self.ma_type == 'sma':
            df.ta.sma(length=self.ma_short, append=True)
            df.ta.sma(length=self.ma_long, append=True)
        elif self.ma_type == 'wma':
            df.ta.wma(length=self.ma_short, append=True)
            df.ta.wma(length=self.ma_long, append=True)
        elif self.ma_type == 'ema':
            df.ta.ema(length=self.ma_short, append=True)
            df.ta.ema(length=self.ma_long, append=True)
        else:
            print(f"Tipo '{self.ma_type}' no reconocido. Usando SMA.")
            df.ta.sma(length=self.ma_short, append=True)
            df.ta.sma(length=self.ma_long, append=True)

        df.ta.stoch(
            k=self.stoch_k,
            d=self.stoch_d,
            smooth_k=self.stoch_smooth,
            mamode='sma',
            append=True,
        )
        cols_k = [c for c in df.columns if c.startswith('STOCHk')]
        if cols_k:
            df.rename(columns={cols_k[0]: 'STOCH_K'}, inplace=True)

        return df

    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate only RSI using the current RSI length."""
        return df.ta.rsi(length=self.rsi_len)
