from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtests.menendez.menendez_config import get_context_config


@dataclass
class SegmentInfo:
    seg_id: int
    direction: int
    start_pos: int
    end_pos: int
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    start_close: float
    end_close: float
    low: float
    high: float
    low_time: pd.Timestamp
    high_time: pd.Timestamp


def _true_run_lengths(mask):
    mask = pd.Series(mask, copy=False)
    mask = mask.where(mask.notna(), False).astype(bool)
    groups = (~mask).cumsum()
    return mask.groupby(groups).cumsum().where(mask, 0).astype(int)


def _line_value(start_pos, start_price, end_pos, end_price, target_pos):
    if end_pos == start_pos:
        return float(end_price)
    slope = (float(end_price) - float(start_price)) / float(end_pos - start_pos)
    return float(start_price) + slope * float(target_pos - start_pos)


def _safe_int(value, default=0):
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=np.nan):
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_finite_number(value):
    try:
        return np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _bool_series(value, index):
    if isinstance(value, pd.Series):
        series = value.reindex(index)
    else:
        series = pd.Series(value, index=index)
    series = series.where(series.notna(), False)
    return series.astype(bool)


def _string_series(value, index):
    if isinstance(value, pd.Series):
        series = value.reindex(index)
    else:
        series = pd.Series(value, index=index)
    series = series.where(series.notna(), "")
    return series.astype(str)


def _close_vs_level(close_value, level_value, tolerance=1e-12):
    if not (_is_finite_number(close_value) and _is_finite_number(level_value)):
        return 0
    delta = float(close_value) - float(level_value)
    if abs(delta) <= tolerance:
        return 0
    return 1 if delta > 0 else -1


class MenendezContextAnalyzer:
    def __init__(self, **overrides):
        config = get_context_config(overrides)
        self.retracement_min = float(config["retracement_min"])
        self.retracement_max = float(config["retracement_max"])
        self.macd_neutral_threshold = float(config["macd_neutral_threshold"])
        self.macd_standby_bars = int(config["macd_standby_bars"])
        self.use_h4_standby_filter = bool(config.get("use_h4_standby_filter", False))
        self.h4_trend_filter = str(config.get("h4_trend_filter", "sma21_slope") or "sma21_slope").strip().lower()
        self.macd_memory_bars = int(config.get("macd_memory_bars", 1) or 1)
        self.signal_memory_bars = int(config["signal_memory_bars"])
        self.candidate_window_mode = str(config.get("candidate_window_mode", "memory") or "memory").strip().lower()
        self.candidate_window_max_bars = int(config.get("candidate_window_max_bars", 0) or 0)
        self.stoch_memory_bars = int(config["stoch_memory_bars"])
        self.stoch_oversold = float(config["stoch_oversold"])
        self.stoch_overbought = float(config["stoch_overbought"])
        self.fan_breakout_tolerance = float(config["fan_breakout_tolerance"])
        self.min_rr = float(config["min_rr"])
        self.entry_primary_trigger_mode = str(
            config.get("entry_primary_trigger_mode", "fan_breakout") or "fan_breakout"
        ).strip().lower()
        self.entry_momentum_confirm_mode = str(
            config.get("entry_momentum_confirm_mode", "macd_and_stoch") or "macd_and_stoch"
        ).strip().lower()
        self.tp_include_bollinger = bool(config.get("tp_include_bollinger", True))
        self.session_filter_enabled = bool(config.get("session_filter_enabled", False))
        self.session_start_hour_utc = int(config.get("session_start_hour_utc", 7))
        self.session_end_hour_utc = int(config.get("session_end_hour_utc", 17))
        self.corrective_equivalents = tuple(int(x) for x in config["corrective_equivalents"])
        self.motor_equivalents = tuple(int(x) for x in config["motor_equivalents"])
        self.use_zlr_as_macd_ok = bool(config.get("use_zlr_as_macd_ok", True))
        self.zlr_memory_bars = max(1, int(config.get("zlr_memory_bars", 3) or 1))
        self.use_composite_x = bool(config.get("use_composite_x", False))
        self.composite_x_max_segments = max(1, int(config.get("composite_x_max_segments", 3) or 1))
        raw_composite_counts = config.get("composite_x_allowed_segment_counts", (3, 7, 11, 15))
        self.composite_x_allowed_segment_counts = self._normalize_composite_x_counts(raw_composite_counts)
        self.use_h4_psar_lateral_filter = bool(config.get("use_h4_psar_lateral_filter", False))
        self.psar_lateral_window_bars = max(1, int(config.get("psar_lateral_window_bars", 8) or 1))
        self.psar_lateral_min_flips = max(1, int(config.get("psar_lateral_min_flips", 3) or 1))

    @staticmethod
    def _normalize_composite_x_counts(raw_counts):
        if raw_counts is None:
            return (3,)
        if isinstance(raw_counts, str):
            raw_counts = raw_counts.split(",")
        counts = set()
        for value in raw_counts:
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count > 0 and count % 2 == 1:
                counts.add(count)
        return tuple(sorted(counts)) or (3,)

    def _resolve_h4_block_reason(self, row):
        polarity = _safe_int(row.get("PSAR_POLARITY"), 0)
        slope = _safe_float(row.get("SMA_21_SLOPE"))
        close_price = _safe_float(row.get("close"))
        sma_200 = _safe_float(row.get("SMA_200"))
        standby = bool(row.get("STANDBY", False))
        psar_lateral = bool(row.get("PSAR_LATERAL", False))
        macd_neutral = bool(row.get("MACD_NEUTRAL", False))
        bullish_fan = bool(row.get("BULLISH_FAN", False))
        bearish_fan = bool(row.get("BEARISH_FAN", False))

        if self.use_h4_standby_filter and standby:
            return "H4_STANDBY"
        if self.use_h4_psar_lateral_filter and psar_lateral:
            return "H4_PSAR_LATERAL"
        zlr_relevant = bool(row.get("MACD_ZLR_RELEVANT", False))
        if (
            macd_neutral
            and self.h4_trend_filter != "sma200_primary"
            and not (self.use_zlr_as_macd_ok and zlr_relevant)
        ):
            return "H4_MACD_NEUTRAL"
        if polarity == 1 and not bullish_fan:
            return "H4_BULLISH_FAN_MISSING"
        if polarity == -1 and not bearish_fan:
            return "H4_BEARISH_FAN_MISSING"
        if self.h4_trend_filter in ("sma200_position", "sma200_primary"):
            if not np.isfinite(sma_200):
                return "H4_SMA200_UNAVAILABLE"
            if polarity == 1 and (not np.isfinite(close_price) or close_price <= sma_200):
                return "H4_SMA200_BULL_FILTER_MISSING"
            if polarity == -1 and (not np.isfinite(close_price) or close_price >= sma_200):
                return "H4_SMA200_BEAR_FILTER_MISSING"
        elif self.h4_trend_filter == "none":
            pass
        else:
            if polarity == 1 and (not np.isfinite(slope) or slope <= 0):
                return "H4_SLOPE_NON_POSITIVE"
            if polarity == -1 and (not np.isfinite(slope) or slope >= 0):
                return "H4_SLOPE_NON_NEGATIVE"
        if polarity == 0:
            return "H4_PSAR_NEUTRAL"
        return "H4_NO_ALIGNMENT"

    def _resolve_h4_trend_ok(self, df):
        polarity = df["PSAR_POLARITY"].fillna(0).astype(int)
        if self.h4_trend_filter in ("sma200_position", "sma200_primary"):
            close_price = pd.to_numeric(df["close"], errors="coerce")
            sma_200 = pd.to_numeric(df.get("SMA_200"), errors="coerce")
            return np.where(
                polarity == 1,
                close_price > sma_200,
                np.where(
                    polarity == -1,
                    close_price < sma_200,
                    False,
                ),
            )
        return np.where(
            polarity == 1,
            pd.to_numeric(df["SMA_21_SLOPE"], errors="coerce") > 0,
            np.where(
                polarity == -1,
                pd.to_numeric(df["SMA_21_SLOPE"], errors="coerce") < 0,
                False,
            ),
        )

    def _resolve_candidate_window_end(self, current):
        if self.candidate_window_mode == "segment":
            candidate_end = current.end_pos
        else:
            candidate_end = current.start_pos + max(self.signal_memory_bars, 1) - 1
        if self.candidate_window_max_bars > 0:
            candidate_end = min(candidate_end, current.start_pos + self.candidate_window_max_bars - 1)
        return min(current.end_pos, candidate_end)

    def calcular_atractor_htf(self, df_original):
        df = df_original.copy()
        df["MACD_NEUTRAL"] = (df["MACD_HIST"].abs() < self.macd_neutral_threshold).fillna(False)
        neutral_runs = _true_run_lengths(df["MACD_NEUTRAL"])
        df["MACD_NEUTRAL_RUN"] = neutral_runs
        df["STANDBY"] = neutral_runs >= self.macd_standby_bars
        flip_long = _bool_series(df.get("PSAR_FLIP_LONG", False), df.index)
        flip_short = _bool_series(df.get("PSAR_FLIP_SHORT", False), df.index)
        df["PSAR_FLIP_EVENT"] = (flip_long | flip_short).astype(bool)
        df["PSAR_FLIP_COUNT_WINDOW"] = (
            df["PSAR_FLIP_EVENT"]
            .astype(int)
            .rolling(self.psar_lateral_window_bars, min_periods=1)
            .sum()
            .fillna(0)
            .astype(int)
        )
        df["PSAR_LATERAL"] = (
            df["PSAR_FLIP_COUNT_WINDOW"] >= self.psar_lateral_min_flips
        ).astype(bool)
        df["ATTRACTOR_PSAR_OK"] = df["PSAR_POLARITY"].fillna(0).astype(int).isin({-1, 1})
        df["ATTRACTOR_FAN_OK"] = np.where(
            df["PSAR_POLARITY"].fillna(0).astype(int) == 1,
            df["BULLISH_FAN"].fillna(False),
            np.where(
                df["PSAR_POLARITY"].fillna(0).astype(int) == -1,
                df["BEARISH_FAN"].fillna(False),
                False,
            ),
        )
        df["ATTRACTOR_SLOPE_OK"] = np.where(
            df["PSAR_POLARITY"].fillna(0).astype(int) == 1,
            pd.to_numeric(df["SMA_21_SLOPE"], errors="coerce") > 0,
            np.where(
                df["PSAR_POLARITY"].fillna(0).astype(int) == -1,
                pd.to_numeric(df["SMA_21_SLOPE"], errors="coerce") < 0,
                False,
            ),
        )
        df["ATTRACTOR_TREND_OK"] = self._resolve_h4_trend_ok(df)

        # ZLR (Zero Line Reversal): el histograma MACD cruza el cero.
        # Segun Menendez, este cruce es una señal de timing valida aunque el
        # histograma estuviera en zona neutral el bar anterior. Bloquear el
        # atractor en ese momento hace perder exactamente esas entradas.
        # zlr_memory_bars extiende la ventana ZLR N barras H4 hacia adelante
        # para que el atractor pueda activarse en los primeros bars tras el cruce,
        # no solo en el bar exacto del crossover.
        macd_hist_num = pd.to_numeric(df["MACD_HIST"], errors="coerce")
        macd_hist_prev = macd_hist_num.shift(1)
        zlr_bull_raw = ((macd_hist_prev < 0) & (macd_hist_num >= 0)).fillna(False)
        zlr_bear_raw = ((macd_hist_prev > 0) & (macd_hist_num <= 0)).fillna(False)
        if self.zlr_memory_bars > 1:
            df["MACD_ZLR_BULL"] = (
                zlr_bull_raw.rolling(self.zlr_memory_bars, min_periods=1).max().astype(bool)
            )
            df["MACD_ZLR_BEAR"] = (
                zlr_bear_raw.rolling(self.zlr_memory_bars, min_periods=1).max().astype(bool)
            )
        else:
            df["MACD_ZLR_BULL"] = zlr_bull_raw
            df["MACD_ZLR_BEAR"] = zlr_bear_raw
        psar_int = df["PSAR_POLARITY"].fillna(0).astype(int)
        df["MACD_ZLR_RELEVANT"] = (
            ((psar_int == 1) & df["MACD_ZLR_BULL"]) |
            ((psar_int == -1) & df["MACD_ZLR_BEAR"])
        ).fillna(False)

        macd_base_ok = ~df["MACD_NEUTRAL"].fillna(False)
        if self.use_zlr_as_macd_ok:
            df["ATTRACTOR_MACD_OK"] = macd_base_ok | df["MACD_ZLR_RELEVANT"].fillna(False)
        else:
            df["ATTRACTOR_MACD_OK"] = macd_base_ok

        attractor = np.zeros(len(df), dtype=int)
        macd_ok_series = df["ATTRACTOR_MACD_OK"].fillna(False).astype(bool)
        trend_ok_series = pd.Series(df["ATTRACTOR_TREND_OK"], index=df.index).fillna(False).astype(bool)
        # En modo sma200_primary la SMA200 es el unico filtro de tendencia madre;
        # el MACD pasa a ser diagnostico y no bloquea el atractor.
        if self.h4_trend_filter == "sma200_primary":
            long_mask = (
                (df["PSAR_POLARITY"] == 1) &
                df["BULLISH_FAN"].fillna(False) &
                trend_ok_series
            )
            short_mask = (
                (df["PSAR_POLARITY"] == -1) &
                df["BEARISH_FAN"].fillna(False) &
                trend_ok_series
            )
        else:
            long_mask = (
                (df["PSAR_POLARITY"] == 1) &
                df["BULLISH_FAN"].fillna(False) &
                trend_ok_series &
                macd_ok_series
            )
            short_mask = (
                (df["PSAR_POLARITY"] == -1) &
                df["BEARISH_FAN"].fillna(False) &
                trend_ok_series &
                macd_ok_series
            )
        if self.use_h4_psar_lateral_filter:
            lateral_ok = ~df["PSAR_LATERAL"].fillna(False)
            long_mask = long_mask & lateral_ok
            short_mask = short_mask & lateral_ok
        if self.use_h4_standby_filter:
            standby_mask = ~df["STANDBY"].fillna(False)
            long_mask = long_mask & standby_mask
            short_mask = short_mask & standby_mask
        attractor[long_mask.to_numpy()] = 1
        attractor[short_mask.to_numpy()] = -1
        df["ATTRACTOR_DIR"] = attractor
        df["ATTRACTOR_BLOCK_REASON"] = df.apply(self._resolve_h4_block_reason, axis=1)
        df.loc[df["ATTRACTOR_DIR"] == 1, "ATTRACTOR_BLOCK_REASON"] = ""
        df.loc[df["ATTRACTOR_DIR"] == -1, "ATTRACTOR_BLOCK_REASON"] = ""
        df["ATTRACTOR_STAGE"] = np.where(
            df["ATTRACTOR_DIR"] == 1,
            "H4_LONG_READY",
            np.where(
                df["ATTRACTOR_DIR"] == -1,
                "H4_SHORT_READY",
                "H4_BLOCKED",
            ),
        )
        return df

    def sincronizar_contexto_htf(self, df_ltf, df_htf):
        if not isinstance(df_ltf.index, pd.DatetimeIndex) or not isinstance(df_htf.index, pd.DatetimeIndex):
            raise TypeError("Se requiere DatetimeIndex en LTF y HTF.")

        cols = [
            "close",
            "ATTRACTOR_DIR",
            "MACD_NEUTRAL",
            "STANDBY",
            "ATTRACTOR_STAGE",
            "ATTRACTOR_BLOCK_REASON",
            "ATTRACTOR_PSAR_OK",
            "ATTRACTOR_FAN_OK",
            "ATTRACTOR_SLOPE_OK",
            "ATTRACTOR_TREND_OK",
            "ATTRACTOR_MACD_OK",
            "PSAR",
            "PSAR_POLARITY",
            "PSAR_FLIP_EVENT",
            "PSAR_FLIP_COUNT_WINDOW",
            "PSAR_LATERAL",
            "SMA_5",
            "SMA_8",
            "SMA_13",
            "SMA_21",
            "SMA_50",
            "SMA_200",
            "SMA_21_SLOPE",
            "SMA_5_8_CROSS_UP",
            "SMA_5_8_CROSS_DOWN",
            "SMA_8_13_CROSS_UP",
            "SMA_8_13_CROSS_DOWN",
            "SMA_13_21_CROSS_UP",
            "SMA_13_21_CROSS_DOWN",
            "SMA_50_200_CROSS_UP",
            "SMA_50_200_CROSS_DOWN",
            "MACD_LINE",
            "MACD_SIGNAL",
            "MACD_HIST",
            "MACD_ZLR_BULL",
            "MACD_ZLR_BEAR",
            "MACD_ZLR_RELEVANT",
            "BULLISH_FAN",
            "BEARISH_FAN",
        ]
        htf = df_htf[cols].copy()
        htf["SOURCE_TIME"] = htf.index
        htf = htf.shift(1)
        htf = htf.rename(columns={
            "close": "H4_CLOSE",
            "ATTRACTOR_DIR": "H4_ATTRACTOR_DIR",
            "MACD_NEUTRAL": "H4_MACD_NEUTRAL",
            "STANDBY": "H4_STANDBY",
            "ATTRACTOR_STAGE": "H4_ATTRACTOR_STAGE",
            "ATTRACTOR_BLOCK_REASON": "H4_ATTRACTOR_BLOCK_REASON",
            "ATTRACTOR_PSAR_OK": "H4_ATTRACTOR_PSAR_OK",
            "ATTRACTOR_FAN_OK": "H4_ATTRACTOR_FAN_OK",
            "ATTRACTOR_SLOPE_OK": "H4_ATTRACTOR_SLOPE_OK",
            "ATTRACTOR_TREND_OK": "H4_ATTRACTOR_TREND_OK",
            "ATTRACTOR_MACD_OK": "H4_ATTRACTOR_MACD_OK",
            "PSAR": "H4_PSAR",
            "PSAR_POLARITY": "H4_PSAR_POLARITY",
            "PSAR_FLIP_EVENT": "H4_PSAR_FLIP_EVENT",
            "PSAR_FLIP_COUNT_WINDOW": "H4_PSAR_FLIP_COUNT_WINDOW",
            "PSAR_LATERAL": "H4_PSAR_LATERAL",
            "SMA_5": "H4_SMA_5",
            "SMA_8": "H4_SMA_8",
            "SMA_13": "H4_SMA_13",
            "SMA_21": "H4_SMA_21",
            "SMA_50": "H4_SMA_50",
            "SMA_200": "H4_SMA_200",
            "SMA_21_SLOPE": "H4_SMA_21_SLOPE",
            "SMA_5_8_CROSS_UP": "H4_SMA_5_8_CROSS_UP",
            "SMA_5_8_CROSS_DOWN": "H4_SMA_5_8_CROSS_DOWN",
            "SMA_8_13_CROSS_UP": "H4_SMA_8_13_CROSS_UP",
            "SMA_8_13_CROSS_DOWN": "H4_SMA_8_13_CROSS_DOWN",
            "SMA_13_21_CROSS_UP": "H4_SMA_13_21_CROSS_UP",
            "SMA_13_21_CROSS_DOWN": "H4_SMA_13_21_CROSS_DOWN",
            "SMA_50_200_CROSS_UP": "H4_SMA_50_200_CROSS_UP",
            "SMA_50_200_CROSS_DOWN": "H4_SMA_50_200_CROSS_DOWN",
            "MACD_LINE": "H4_MACD_LINE",
            "MACD_SIGNAL": "H4_MACD_SIGNAL",
            "MACD_HIST": "H4_MACD_HIST",
            "MACD_ZLR_BULL": "H4_MACD_ZLR_BULL",
            "MACD_ZLR_BEAR": "H4_MACD_ZLR_BEAR",
            "MACD_ZLR_RELEVANT": "H4_MACD_ZLR_RELEVANT",
            "BULLISH_FAN": "H4_BULLISH_FAN",
            "BEARISH_FAN": "H4_BEARISH_FAN",
            "SOURCE_TIME": "H4_SOURCE_TIME",
        })

        ltf_reset = df_ltf.reset_index().rename(columns={df_ltf.index.name or "index": "time"})
        htf_reset = htf.reset_index().rename(columns={htf.index.name or "index": "time"})
        merged = pd.merge_asof(
            ltf_reset.sort_values("time"),
            htf_reset.sort_values("time"),
            on="time",
            direction="backward",
        )
        merged = merged.set_index("time")
        merged.index.name = df_ltf.index.name or "time"
        return merged

    def _build_segments(self, df):
        polarity = df["PSAR_POLARITY"].ffill().fillna(0).astype(int)
        if polarity.empty:
            return df, []

        segment_change = polarity.ne(polarity.shift(1))
        segment_ids = segment_change.cumsum().astype(int)
        df = df.copy()
        df["SEGMENT_ID"] = segment_ids

        segments = []
        for seg_id, seg_df in df.groupby("SEGMENT_ID", sort=True):
            direction = _safe_int(seg_df["PSAR_POLARITY"].iloc[0], 0)
            if direction == 0:
                continue
            start_idx = seg_df.index[0]
            end_idx = seg_df.index[-1]
            start_pos = int(df.index.get_loc(start_idx))
            end_pos = int(df.index.get_loc(end_idx))
            low_time = pd.Timestamp(seg_df["low"].idxmin())
            high_time = pd.Timestamp(seg_df["high"].idxmax())
            segments.append(SegmentInfo(
                seg_id=int(seg_id),
                direction=direction,
                start_pos=start_pos,
                end_pos=end_pos,
                start_time=pd.Timestamp(start_idx),
                end_time=pd.Timestamp(end_idx),
                start_close=_safe_float(seg_df["close"].iloc[0]),
                end_close=_safe_float(seg_df["close"].iloc[-1]),
                low=_safe_float(seg_df["low"].min()),
                high=_safe_float(seg_df["high"].max()),
                low_time=low_time,
                high_time=high_time,
            ))
        return df, segments

    def _classify_fractal_equivalent(self, count):
        count = int(count)
        if count in self.corrective_equivalents:
            return "CORRECTIVE_EQUIVALENT"
        if count in self.motor_equivalents:
            return "MOTOR_EQUIVALENT"
        return "OTHER"

    def _stoch_trigger(self, df, row_pos, direction):
        start_pos = max(0, row_pos - max(self.stoch_memory_bars, 1) + 1)
        window = df.iloc[start_pos:row_pos + 1]
        if direction == 1:
            if not bool(window["STOCH_CROSS_UP"].fillna(False).any()):
                return False
            lowest = np.nanmin([
                _safe_float(window["STOCH_K"].min()),
                _safe_float(window["STOCH_D"].min()),
            ])
            return np.isfinite(lowest) and lowest <= self.stoch_oversold

        if not bool(window["STOCH_CROSS_DOWN"].fillna(False).any()):
            return False
        highest = np.nanmax([
            _safe_float(window["STOCH_K"].max()),
            _safe_float(window["STOCH_D"].max()),
        ])
        return np.isfinite(highest) and highest >= self.stoch_overbought

    def _macd_trigger(self, df, row_pos, direction, setup_start_pos):
        transition_lookback = max(self.signal_memory_bars, self.macd_memory_bars, 1)
        window = df.iloc[max(setup_start_pos, row_pos - transition_lookback + 1):row_pos + 1]
        recent_window = df.iloc[max(setup_start_pos, row_pos - self.macd_memory_bars + 1):row_pos + 1]
        hist_window = pd.to_numeric(window["MACD_HIST"], errors="coerce")
        recent_hist = pd.to_numeric(recent_window["MACD_HIST"], errors="coerce")
        had_neutral = bool((hist_window.abs() <= self.macd_neutral_threshold).any())
        had_opposite = bool((hist_window <= 0).any()) if direction == 1 else bool((hist_window >= 0).any())

        if direction == 1:
            active_recent = bool((recent_hist > self.macd_neutral_threshold).any())
            return active_recent and (had_neutral or had_opposite)

        active_recent = bool((recent_hist < -self.macd_neutral_threshold).any())
        return active_recent and (had_neutral or had_opposite)

    def _psar_trigger(self, row, direction):
        if direction == 1:
            return bool(row.get("PSAR_FLIP_LONG", False))
        return bool(row.get("PSAR_FLIP_SHORT", False))

    def _resolve_primary_trigger(self, fan_breakout, psar_trigger):
        if self.entry_primary_trigger_mode == "fan_or_psar":
            return bool(fan_breakout or psar_trigger)
        return bool(fan_breakout)

    def _resolve_momentum_confirm(self, macd_trigger, stoch_trigger):
        if self.entry_momentum_confirm_mode == "macd_or_stoch":
            return bool(macd_trigger or stoch_trigger)
        return bool(macd_trigger and stoch_trigger)

    def _session_filter_ok(self, timestamp):
        if not self.session_filter_enabled:
            return True
        ts = pd.Timestamp(timestamp)
        hour = int(ts.hour)
        if self.session_start_hour_utc <= self.session_end_hour_utc:
            return self.session_start_hour_utc <= hour < self.session_end_hour_utc
        return hour >= self.session_start_hour_utc or hour < self.session_end_hour_utc

    def _pick_tp_cluster(self, row, direction, entry_price, fib_targets):
        candidates = []

        for ratio, price in fib_targets.items():
            if not np.isfinite(price):
                continue
            if direction == 1 and price > entry_price:
                candidates.append((price - entry_price, float(price), f"FIB_{ratio}"))
            elif direction == -1 and price < entry_price:
                candidates.append((entry_price - price, float(price), f"FIB_{ratio}"))

        if direction == 1:
            band_value = _safe_float(row.get("BB_UPPER"))
            pivot_cols = ("D_PIVOT", "D_R1", "D_R2", "W_PIVOT", "W_R1", "W_R2")
            if self.tp_include_bollinger and np.isfinite(band_value) and band_value > entry_price:
                candidates.append((band_value - entry_price, band_value, "BB_UPPER"))
        else:
            band_value = _safe_float(row.get("BB_LOWER"))
            pivot_cols = ("D_PIVOT", "D_S1", "D_S2", "W_PIVOT", "W_S1", "W_S2")
            if self.tp_include_bollinger and np.isfinite(band_value) and band_value < entry_price:
                candidates.append((entry_price - band_value, band_value, "BB_LOWER"))

        for column_name in pivot_cols:
            value = _safe_float(row.get(column_name))
            if not np.isfinite(value):
                continue
            if direction == 1 and value > entry_price:
                candidates.append((value - entry_price, value, column_name))
            elif direction == -1 and value < entry_price:
                candidates.append((entry_price - value, value, column_name))

        if not candidates:
            return np.nan, ""

        candidates.sort(key=lambda item: (item[0], item[2]))
        _, tp_price, source = candidates[0]
        return float(tp_price), source

    def _segment_touches_ma(self, df, segment, ma_column):
        if ma_column not in df.columns:
            return False
        seg_df = df.iloc[segment.start_pos:segment.end_pos + 1]
        ma = pd.to_numeric(seg_df[ma_column], errors="coerce")
        low = pd.to_numeric(seg_df["low"], errors="coerce")
        high = pd.to_numeric(seg_df["high"], errors="coerce")
        touch_mask = ma.notna() & low.notna() & high.notna() & (low <= ma) & (ma <= high)
        return bool(touch_mask.any())

    def _group_touches_ma(self, df, segments_group, ma_column):
        if ma_column not in df.columns or not segments_group:
            return False
        start_pos = int(segments_group[0].start_pos)
        end_pos = int(segments_group[-1].end_pos)
        group_df = df.iloc[start_pos:end_pos + 1]
        ma = pd.to_numeric(group_df[ma_column], errors="coerce")
        low = pd.to_numeric(group_df["low"], errors="coerce")
        high = pd.to_numeric(group_df["high"], errors="coerce")
        touch_mask = ma.notna() & low.notna() & high.notna() & (low <= ma) & (ma <= high)
        return bool(touch_mask.any())

    def _segment_ep_ma_distance(self, df, ep_time, ma_column, ep_price):
        if ma_column not in df.columns or ep_time not in df.index or not _is_finite_number(ep_price):
            return np.nan
        ma_value = _safe_float(df.at[ep_time, ma_column])
        if not _is_finite_number(ma_value):
            return np.nan
        return float(ep_price) - float(ma_value)

    def _find_composite_x(self, segments, entry_idx, h4_dir, min_segments=3):
        """Busca una X compuesta (multi-segmento ABC) antes de entry_idx.

        La agrupacion experimental exige que X:

        * sea un bloque contiguo inmediatamente anterior al segmento de entrada
        * empiece y termine contra `h4_dir`
        * pueda incluir rebotes internos a favor de `h4_dir` (ABC o complejas)

        Por defecto solo se evalua ABC de 3 segmentos. Las correcciones mas
        complejas deben declararse mediante equivalentes correctivos en
        `composite_x_allowed_segment_counts`. El recuento 5 no se admite por
        defecto porque pertenece a equivalentes motores dentro de la metodologia
        Menendez documentada en el proyecto.
        """
        if entry_idx < 2:
            return None

        min_segments = max(1, int(min_segments or 1))
        if min_segments % 2 == 0:
            min_segments += 1

        best = None
        max_segments = min(int(entry_idx), int(self.composite_x_max_segments))
        if max_segments % 2 == 0:
            max_segments -= 1

        candidate_counts = [
            count
            for count in self.composite_x_allowed_segment_counts
            if min_segments <= count <= max_segments
        ]

        for n in candidate_counts:
            group_start_idx = entry_idx - n
            w_idx = group_start_idx - 1
            if w_idx < 0:
                break
            impulse = segments[w_idx]
            if impulse.direction != h4_dir:
                continue

            group = segments[group_start_idx:entry_idx]
            if not group:
                continue
            if group[0].direction != -h4_dir or group[-1].direction != -h4_dir:
                continue

            if h4_dir == 1:
                group_extreme = min(s.low for s in group)
                group_ep_time = min(
                    ((s.low, s.low_time) for s in group), key=lambda t: t[0]
                )[1]
                if group_extreme >= float(impulse.high):
                    continue
            else:
                group_extreme = max(s.high for s in group)
                group_ep_time = max(
                    ((s.high, s.high_time) for s in group), key=lambda t: t[0]
                )[1]
                if group_extreme <= float(impulse.low):
                    continue

            best = (impulse, group, group_extreme, group_ep_time, n)

        return best

    def procesar_contexto_m30(self, df_original):
        df, segments = self._build_segments(df_original.copy())
        defaults_float = {
            "W_ID": np.nan,
            "X_ID": np.nan,
            "RETRACE_RATIO": np.nan,
            "SL_PRICE": np.nan,
            "TP_PRICE": np.nan,
            "RR_RATIO": np.nan,
            "PLANNED_ENTRY_PRICE": np.nan,
            "CORRECTION_LINE_PRICE": np.nan,
            "BASE_CHANNEL_LIMIT": np.nan,
            "TARGET_0.854": np.nan,
            "TARGET_1.0": np.nan,
            "TARGET_1.236": np.nan,
            "TARGET_1.618": np.nan,
            "W_START_PRICE": np.nan,
            "W_END_PRICE": np.nan,
            "X_EXTREME_PRICE": np.nan,
            "X_EP_DISTANCE_SMA21": np.nan,
            "X_EP_DISTANCE_SMA50": np.nan,
            "SETUP_ID": np.nan,
            "TARGET_EXTENSION": np.nan,
        }
        defaults_bool = {
            "HTF_GATE_OK": False,
            "SETUP_CANDIDATE": False,
            "RETRACE_OK": False,
            "FAN_BREAKOUT": False,
            "MACD_TRIGGER": False,
            "STOCH_TRIGGER": False,
            "PSAR_TRIGGER": False,
            "PRIMARY_TRIGGER": False,
            "MOMENTUM_CONFIRM": False,
            "SESSION_OK": False,
            "RR_OK": False,
            "ENTRY_READY": False,
            "X_TOUCH_SMA21": False,
            "X_TOUCH_SMA50": False,
            # Diagnostico estructural W-X. Ver seccion 4.3 de DOCUMENTACION_MENENDEZ.md
            # para la justificacion de la formalizacion mecanica simple.
            "X_POSSIBLE_COMPOSITE": False,
        }
        defaults_object = {
            "W_START": pd.NaT,
            "W_END": pd.NaT,
            "X_END": pd.NaT,
            "W_EP_TIME": pd.NaT,
            "X_EP_TIME": pd.NaT,
            "FRACTAL_EQUIVALENT_CLASS": "OTHER",
            "TP_SOURCE": "",
            "SETUP_STATUS": "NO_SETUP",
            "BLOCK_REASON": "",
            "LAST_PASSED_STAGE": "NO_STAGE",
        }
        defaults_int = {
            "M30_PSAR_POLARITY": 0,
            "FRACTAL_SEGMENT_COUNT": 0,
            "BASE_CHANNEL_STATE": 0,
            "DECEL_CHANNEL_STATE": 0,
            "ENTRY_DIR": 0,
            "SETUP_DIR": 0,
            "SETUP_AGE": 0,
            "X_END_CLOSE_VS_SMA21": 0,
            "X_END_CLOSE_VS_SMA50": 0,
            # En modo simple vale 1; en modo experimental de X compuesta puede
            # tomar valores > 1 y permite comparar ambas formalizaciones directamente.
            "X_SEGMENT_COUNT": 0,
        }

        for column_name, default_value in defaults_float.items():
            df[column_name] = default_value
        for column_name, default_value in defaults_bool.items():
            df[column_name] = default_value
        for column_name, default_value in defaults_object.items():
            df[column_name] = default_value
        for column_name, default_value in defaults_int.items():
            df[column_name] = default_value

        df["M30_PSAR_POLARITY"] = df["PSAR_POLARITY"].fillna(0).astype(int)
        h4_dir_series = pd.to_numeric(df.get("H4_ATTRACTOR_DIR"), errors="coerce").fillna(0).astype(int)
        h4_standby = _bool_series(df.get("H4_STANDBY", False), df.index)
        h4_block_reason = _string_series(df.get("H4_ATTRACTOR_BLOCK_REASON", ""), df.index)

        for time_index in df.index:
            h4_dir = int(h4_dir_series.loc[time_index])
            standby = bool(h4_standby.loc[time_index])
            if h4_dir != 0 and (not self.use_h4_standby_filter or not standby):
                df.at[time_index, "HTF_GATE_OK"] = True
                df.at[time_index, "SETUP_STATUS"] = "HTF_READY"
                df.at[time_index, "LAST_PASSED_STAGE"] = "HTF_READY"
            else:
                reason = str(h4_block_reason.loc[time_index] or "")
                if not reason:
                    reason = "H4_NO_ATTRACTOR"
                df.at[time_index, "SETUP_STATUS"] = "H4_BLOCKED"
                df.at[time_index, "BLOCK_REASON"] = reason
                df.at[time_index, "LAST_PASSED_STAGE"] = "H4_BLOCKED"

        prev_regime_dir = None
        regime_count = 0
        for segment in segments:
            h4_dir = _safe_int(df["H4_ATTRACTOR_DIR"].iloc[segment.start_pos], 0)
            if h4_dir == 0:
                regime_count = 0
            elif h4_dir != prev_regime_dir:
                regime_count = 1
            else:
                regime_count += 1

            seg_slice = slice(segment.start_pos, segment.end_pos + 1)
            df.iloc[seg_slice, df.columns.get_loc("FRACTAL_SEGMENT_COUNT")] = regime_count
            eq_class = self._classify_fractal_equivalent(regime_count) if regime_count > 0 else "OTHER"
            df.iloc[seg_slice, df.columns.get_loc("FRACTAL_EQUIVALENT_CLASS")] = eq_class
            prev_regime_dir = h4_dir

        # DECISION ARQUITECTONICA: X es exactamente un segmento PSAR M30 en la
        # formalizacion mecanica simple (use_composite_x=False, por defecto).
        # Patron detectado: impulse(W, h4_dir) -> correction(X, -h4_dir) -> current(h4_dir).
        # La simplificacion es deliberada y auditada (seccion 4.3 DOCUMENTACION_MENENDEZ.md).
        # Cuando use_composite_x=True (variante experimental_composite_x), X puede agrupar
        # segmentos PSAR correctivos admitidos por composite_x_allowed_segment_counts.
        for idx in range(2, len(segments)):
            current = segments[idx]
            row_pos = current.start_pos
            row = df.iloc[row_pos]

            h4_dir = _safe_int(row.get("H4_ATTRACTOR_DIR"), 0)
            if h4_dir == 0:
                continue
            if self.use_h4_standby_filter and bool(row.get("H4_STANDBY", False)):
                continue
            if current.direction != h4_dir:
                continue

            # --- Resolucion de W e X ---
            if self.use_composite_x:
                composite = self._find_composite_x(segments, idx, h4_dir)
                if composite is None:
                    continue
                impulse, x_group, x_extreme_price, x_ep_time, x_segment_count = composite
                diagnostic_composite = composite
            else:
                correction = segments[idx - 1]
                impulse = segments[idx - 2]
                if correction.direction != -h4_dir or impulse.direction != h4_dir:
                    continue
                x_group = [correction]
                x_segment_count = 1
                if h4_dir == 1:
                    x_extreme_price = float(correction.low)
                    x_ep_time = correction.low_time
                else:
                    x_extreme_price = float(correction.high)
                    x_ep_time = correction.high_time
                diagnostic_composite = self._find_composite_x(segments, idx, h4_dir, min_segments=3)

            x_start_seg = x_group[0]
            x_last_seg = x_group[-1]
            correction = x_start_seg

            if h4_dir == 1:
                w_start_price = float(impulse.low)
                w_end_price = float(impulse.high)
                w_ep_time = impulse.high_time
            else:
                w_start_price = float(impulse.high)
                w_end_price = float(impulse.low)
                w_ep_time = impulse.low_time

            wave_size = abs(w_end_price - w_start_price)
            if wave_size <= 0:
                continue

            # Diagnostico estructural: existe una X compuesta valida bajo las reglas
            # experimentales. En modo simple sirve para marcar setups donde la X
            # simple podria ser solo la parte final de una correccion mayor.
            x_possible_composite = (
                bool(diagnostic_composite is not None and diagnostic_composite[-1] > 1)
                if not self.use_composite_x
                else bool(x_segment_count > 1)
            )

            x_touch_sma21 = self._group_touches_ma(df, x_group, "SMA_21")
            x_touch_sma50 = self._group_touches_ma(df, x_group, "SMA_50")
            x_ep_distance_sma21 = self._segment_ep_ma_distance(df, x_ep_time, "SMA_21", x_extreme_price)
            x_ep_distance_sma50 = self._segment_ep_ma_distance(df, x_ep_time, "SMA_50", x_extreme_price)
            x_end_close = _safe_float(df.iloc[x_last_seg.end_pos].get("close"))
            x_end_sma21 = _safe_float(df.iloc[x_last_seg.end_pos].get("SMA_21"))
            x_end_sma50 = _safe_float(df.iloc[x_last_seg.end_pos].get("SMA_50"))
            x_end_close_vs_sma21 = _close_vs_level(x_end_close, x_end_sma21)
            x_end_close_vs_sma50 = _close_vs_level(x_end_close, x_end_sma50)

            retrace_ratio = abs(w_end_price - x_extreme_price) / wave_size
            invalidated = retrace_ratio > self.retracement_max
            valid_retrace = self.retracement_min <= retrace_ratio <= self.retracement_max

            fib_targets = {}
            for ratio in (0.854, 1.0, 1.236, 1.618):
                if h4_dir == 1:
                    fib_targets[ratio] = x_extreme_price + (wave_size * ratio)
                else:
                    fib_targets[ratio] = x_extreme_price - (wave_size * ratio)

            window_end = self._resolve_candidate_window_end(current)
            for candidate_pos in range(current.start_pos, window_end + 1):
                candidate_row = df.iloc[candidate_pos]
                current_close = _safe_float(candidate_row.get("close"))
                spread_price = _safe_float(candidate_row.get("spread_price"), 0.0)
                correction_line_price = _line_value(
                    x_start_seg.start_pos,
                    w_end_price,
                    x_last_seg.end_pos,
                    x_extreme_price,
                    candidate_pos,
                )

                if h4_dir == 1:
                    fan_breakout = np.isfinite(current_close) and current_close > (
                        correction_line_price + self.fan_breakout_tolerance
                    )
                    base_channel_limit = _line_value(
                        impulse.start_pos,
                        w_start_price,
                        x_last_seg.end_pos,
                        x_extreme_price,
                        candidate_pos,
                    )
                    base_channel_state = 1 if current_close >= base_channel_limit else -1
                else:
                    fan_breakout = np.isfinite(current_close) and current_close < (
                        correction_line_price - self.fan_breakout_tolerance
                    )
                    base_channel_limit = _line_value(
                        impulse.start_pos,
                        w_start_price,
                        x_last_seg.end_pos,
                        x_extreme_price,
                        candidate_pos,
                    )
                    base_channel_state = 1 if current_close <= base_channel_limit else -1

                decel_channel_state = -1 if invalidated else (1 if fan_breakout else 0)
                macd_trigger = self._macd_trigger(df, candidate_pos, h4_dir, correction.start_pos)
                stoch_trigger = self._stoch_trigger(df, candidate_pos, h4_dir)
                psar_trigger = self._psar_trigger(candidate_row, h4_dir)
                primary_trigger = self._resolve_primary_trigger(fan_breakout, psar_trigger)
                momentum_confirm = self._resolve_momentum_confirm(macd_trigger, stoch_trigger)
                session_ok = self._session_filter_ok(df.index[candidate_pos])
                planned_entry = current_close + spread_price if h4_dir == 1 else current_close
                sl_price = x_extreme_price
                tp_price, tp_source = self._pick_tp_cluster(candidate_row, h4_dir, planned_entry, fib_targets)
                rr_ratio = np.nan
                rr_ok = False

                if np.isfinite(planned_entry) and np.isfinite(sl_price) and np.isfinite(tp_price):
                    risk_distance = abs(planned_entry - sl_price)
                    reward_distance = abs(tp_price - planned_entry)
                    if risk_distance > 0:
                        rr_ratio = reward_distance / risk_distance
                        rr_ok = rr_ratio >= self.min_rr

                target_extension = np.nan
                if tp_source.startswith("FIB_"):
                    target_extension = _safe_float(tp_source.replace("FIB_", ""))

                entry_ready = (
                    valid_retrace and
                    (not invalidated) and
                    primary_trigger and
                    momentum_confirm and
                    session_ok and
                    rr_ok
                )

                setup_status = "ENTRY_READY"
                block_reason = ""
                last_passed_stage = "ENTRY_READY"
                if not valid_retrace:
                    setup_status = "SETUP_BLOCKED"
                    block_reason = "RETRACE_TOO_DEEP" if invalidated else "RETRACE_BELOW_MIN"
                    last_passed_stage = "TRIPLET_READY"
                elif not primary_trigger:
                    if self.entry_primary_trigger_mode == "fan_or_psar":
                        setup_status = "WAIT_PRIMARY_TRIGGER"
                        block_reason = "PRIMARY_TRIGGER_MISSING"
                    else:
                        setup_status = "WAIT_FAN_BREAKOUT"
                        block_reason = "FAN_BREAKOUT_MISSING"
                    last_passed_stage = "RETRACE_READY"
                elif not momentum_confirm:
                    if self.entry_momentum_confirm_mode == "macd_or_stoch":
                        setup_status = "WAIT_MOMENTUM_CONFIRM"
                        block_reason = "MOMENTUM_CONFIRM_MISSING"
                        last_passed_stage = "PRIMARY_TRIGGER_READY"
                    elif not macd_trigger:
                        setup_status = "WAIT_MACD_TRIGGER"
                        block_reason = "MACD_TRIGGER_MISSING"
                        last_passed_stage = "PRIMARY_TRIGGER_READY"
                    else:
                        setup_status = "WAIT_STOCH_TRIGGER"
                        block_reason = "STOCH_TRIGGER_MISSING"
                        last_passed_stage = "MACD_READY"
                elif not session_ok:
                    setup_status = "WAIT_SESSION"
                    block_reason = "SESSION_FILTER_BLOCKED"
                    last_passed_stage = "MOMENTUM_READY"
                elif not np.isfinite(tp_price):
                    setup_status = "WAIT_RR"
                    block_reason = "TP_UNAVAILABLE"
                    last_passed_stage = "MOMENTUM_READY"
                elif not rr_ok:
                    setup_status = "WAIT_RR"
                    block_reason = "RR_BELOW_MIN"
                    last_passed_stage = "MOMENTUM_READY"

                time_index = df.index[candidate_pos]
                df.at[time_index, "W_ID"] = float(impulse.seg_id)
                df.at[time_index, "X_ID"] = float(x_start_seg.seg_id)
                df.at[time_index, "W_START"] = impulse.start_time
                df.at[time_index, "W_END"] = impulse.end_time
                df.at[time_index, "X_END"] = x_last_seg.end_time
                df.at[time_index, "W_EP_TIME"] = w_ep_time
                df.at[time_index, "X_EP_TIME"] = x_ep_time
                df.at[time_index, "SETUP_CANDIDATE"] = True
                df.at[time_index, "RETRACE_OK"] = bool(valid_retrace and not invalidated)
                df.at[time_index, "RETRACE_RATIO"] = retrace_ratio
                df.at[time_index, "FAN_BREAKOUT"] = bool(fan_breakout)
                df.at[time_index, "BASE_CHANNEL_STATE"] = int(base_channel_state)
                df.at[time_index, "DECEL_CHANNEL_STATE"] = int(decel_channel_state)
                df.at[time_index, "MACD_TRIGGER"] = bool(macd_trigger)
                df.at[time_index, "STOCH_TRIGGER"] = bool(stoch_trigger)
                df.at[time_index, "PSAR_TRIGGER"] = bool(psar_trigger)
                df.at[time_index, "PRIMARY_TRIGGER"] = bool(primary_trigger)
                df.at[time_index, "MOMENTUM_CONFIRM"] = bool(momentum_confirm)
                df.at[time_index, "SESSION_OK"] = bool(session_ok)
                df.at[time_index, "RR_OK"] = bool(rr_ok)
                df.at[time_index, "X_TOUCH_SMA21"] = bool(x_touch_sma21)
                df.at[time_index, "X_TOUCH_SMA50"] = bool(x_touch_sma50)
                df.at[time_index, "X_EP_DISTANCE_SMA21"] = x_ep_distance_sma21
                df.at[time_index, "X_EP_DISTANCE_SMA50"] = x_ep_distance_sma50
                df.at[time_index, "X_END_CLOSE_VS_SMA21"] = int(x_end_close_vs_sma21)
                df.at[time_index, "X_END_CLOSE_VS_SMA50"] = int(x_end_close_vs_sma50)
                df.at[time_index, "X_SEGMENT_COUNT"] = int(x_segment_count)
                df.at[time_index, "X_POSSIBLE_COMPOSITE"] = bool(x_possible_composite)
                df.at[time_index, "SL_PRICE"] = sl_price
                df.at[time_index, "TP_PRICE"] = tp_price
                df.at[time_index, "TP_SOURCE"] = tp_source
                df.at[time_index, "RR_RATIO"] = rr_ratio
                df.at[time_index, "PLANNED_ENTRY_PRICE"] = planned_entry
                df.at[time_index, "CORRECTION_LINE_PRICE"] = correction_line_price
                df.at[time_index, "BASE_CHANNEL_LIMIT"] = base_channel_limit
                df.at[time_index, "TARGET_0.854"] = fib_targets[0.854]
                df.at[time_index, "TARGET_1.0"] = fib_targets[1.0]
                df.at[time_index, "TARGET_1.236"] = fib_targets[1.236]
                df.at[time_index, "TARGET_1.618"] = fib_targets[1.618]
                df.at[time_index, "W_START_PRICE"] = w_start_price
                df.at[time_index, "W_END_PRICE"] = w_end_price
                df.at[time_index, "X_EXTREME_PRICE"] = x_extreme_price
                df.at[time_index, "SETUP_STATUS"] = setup_status
                df.at[time_index, "BLOCK_REASON"] = block_reason
                df.at[time_index, "LAST_PASSED_STAGE"] = last_passed_stage
                df.at[time_index, "ENTRY_READY"] = bool(entry_ready)
                df.at[time_index, "ENTRY_DIR"] = int(h4_dir if entry_ready else 0)
                df.at[time_index, "SETUP_ID"] = float(x_start_seg.seg_id)
                df.at[time_index, "SETUP_DIR"] = int(h4_dir)
                df.at[time_index, "SETUP_AGE"] = int(candidate_pos - current.start_pos)
                df.at[time_index, "TARGET_EXTENSION"] = target_extension

        return df
