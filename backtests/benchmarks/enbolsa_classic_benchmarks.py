from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.common.backtest_matrix_config import TEMPORAL_SPLITS, get_account_config
from backtests.common.position_sizing import SYMBOL_SPEC_COLUMN_MAP, apply_risk_position_sizing
from backtests.common.trade_analysis import DEFAULT_METRIC_COLUMNS, metrics_from_trades, summarize_periods


SYMBOL_SPEC_COLUMNS = tuple(SYMBOL_SPEC_COLUMN_MAP.values())

CLASSIC_BENCHMARK_STRATEGIES = OrderedDict((
    ("rsi_3tf_mean_reversion", {
        "family": "rsi_mean_reversion",
        "atr_stop_mult": 1.5,
        "risk_fraction": 1.0,
    }),
    ("rsi_3tf_momentum_reentry", {
        "family": "rsi_momentum_reentry",
        "atr_stop_mult": 1.5,
        "target_rr": 2.0,
        "risk_fraction": 1.0,
    }),
    ("ma_cross_3tf_trend", {
        "family": "ma_cross_trend",
        "atr_stop_mult": 1.5,
        "min_rr_before_signal_exit": 1.0,
        "risk_fraction": 1.0,
    }),
    ("bb_3tf_pullback_reentry", {
        "family": "bb_pullback_reentry",
        "atr_stop_mult": 1.5,
        "target_rr": 1.5,
        "risk_fraction": 1.0,
    }),
))

DEFAULT_TF_STACKS = {
    ("M30", "H1"): ("M30", "H1", "H4"),
    ("H1", "H4"): ("H1", "H4", "D1"),
    ("H4", "D1"): ("H4", "D1"),
}


def _safe_float(value, default=np.nan):
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rsi(close, length=14):
    close = pd.Series(close, copy=False).astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / int(length), min_periods=int(length), adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / int(length), min_periods=int(length), adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    no_losses = avg_loss.eq(0.0) & avg_gain.gt(0.0)
    no_gains = avg_gain.eq(0.0) & avg_loss.gt(0.0)
    flat = avg_gain.eq(0.0) & avg_loss.eq(0.0)
    rsi = rsi.mask(no_losses, 100.0)
    rsi = rsi.mask(no_gains, 0.0)
    rsi = rsi.mask(flat, 50.0)
    return rsi


def _atr(df, length=14):
    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce") if "high" in df.columns else close
    low = pd.to_numeric(df["low"], errors="coerce") if "low" in df.columns else close
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / int(length), min_periods=int(length), adjust=False).mean()


def _add_base_indicators(df):
    frame = df.copy()
    close = pd.to_numeric(frame["close"], errors="coerce")
    frame["RSI_14"] = _rsi(close, 14)
    frame["ATR_14"] = _atr(frame, 14)
    frame["SMA20"] = close.rolling(20, min_periods=20).mean()
    frame["SMA50"] = close.rolling(50, min_periods=50).mean()
    frame["SMA200"] = close.rolling(200, min_periods=200).mean()
    bb_mid = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std(ddof=0)
    frame["BB_MID_20_2"] = bb_mid
    frame["BB_UPPER_20_2"] = bb_mid + (2.0 * bb_std)
    frame["BB_LOWER_20_2"] = bb_mid - (2.0 * bb_std)
    frame["TREND_BULLISH"] = (close > frame["SMA200"]) & (frame["SMA50"] > frame["SMA200"])
    frame["TREND_BEARISH"] = (close < frame["SMA200"]) & (frame["SMA50"] < frame["SMA200"])
    return frame


def resolve_tf_stack(timeframe_ltf, timeframe_htf, tf_stack=None):
    if tf_stack is not None:
        return tuple(tf_stack)
    return DEFAULT_TF_STACKS.get((timeframe_ltf, timeframe_htf), (timeframe_ltf, timeframe_htf))


def _raw_tf_has_data(raw_tf_map, tf, symbols):
    for symbol in symbols:
        df = (raw_tf_map.get(tf) or {}).get(symbol)
        if df is not None and not df.empty:
            return True
    return False


def _load_raw_tf_map(symbols, timeframes, base_timeframe=None):
    from data.sql.sql_funcs import cargar_datos_close_batch

    raw = {}
    requested_stack = tuple(dict.fromkeys(timeframes))
    effective_stack = requested_stack
    for tf in requested_stack:
        raw[tf] = {} if tf == base_timeframe else cargar_datos_close_batch(symbols, tf)
    return raw, effective_stack


def _align_trend_series(base_index, trend_frame, prefix, shift=True):
    if trend_frame is None or trend_frame.empty:
        aligned = pd.DataFrame(index=base_index)
        aligned[f"{prefix}_BULLISH"] = False
        aligned[f"{prefix}_BEARISH"] = False
        return aligned

    trend = trend_frame[["TREND_BULLISH", "TREND_BEARISH"]].copy()
    if shift:
        trend = trend.shift(1)
    trend = trend.reset_index().rename(columns={trend.index.name or "index": "time"})
    base = pd.DataFrame({"time": pd.Index(base_index)})
    merged = pd.merge_asof(
        base.sort_values("time"),
        trend.sort_values("time"),
        on="time",
        direction="backward",
    ).set_index("time")
    merged.index = base_index
    merged = merged.infer_objects(copy=False).fillna(False).astype(bool)
    merged = merged.rename(columns={
        "TREND_BULLISH": f"{prefix}_BULLISH",
        "TREND_BEARISH": f"{prefix}_BEARISH",
    })
    return merged


def _close_only_to_ohlc(frame):
    if frame is None or frame.empty:
        return frame
    if {"open", "high", "low", "close"}.issubset(frame.columns):
        return frame
    result = frame.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    for column in ("open", "high", "low"):
        if column not in result.columns:
            result[column] = close
    return result


def prepare_3tf_benchmark_portfolio(portfolio, timeframe_ltf, timeframe_htf, tf_stack=None, raw_tf_map=None):
    symbols = list((portfolio or {}).keys())
    stack = resolve_tf_stack(timeframe_ltf, timeframe_htf, tf_stack=tf_stack)
    if raw_tf_map is None:
        raw_tf_map, effective_stack = _load_raw_tf_map(symbols, stack, base_timeframe=timeframe_ltf)
    else:
        effective_stack = stack
    prepared = {}

    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            continue
        frame = _add_base_indicators(df.sort_index())
        trend_flags = []
        for tf in effective_stack:
            if tf == timeframe_ltf:
                trend_tf = frame
                aligned = _align_trend_series(frame.index, trend_tf, tf, shift=False)
            else:
                raw_df = (raw_tf_map.get(tf) or {}).get(symbol)
                raw_df = _close_only_to_ohlc(raw_df)
                trend_tf = _add_base_indicators(raw_df.sort_index()) if raw_df is not None and not raw_df.empty else pd.DataFrame()
                aligned = _align_trend_series(frame.index, trend_tf, tf, shift=True)
            frame = frame.join(aligned, how="left")
            trend_flags.append((f"{tf}_BULLISH", f"{tf}_BEARISH"))

        bullish_cols = [bull for bull, _ in trend_flags]
        bearish_cols = [bear for _, bear in trend_flags]
        frame["ALIGN_3TF_BULLISH"] = frame[bullish_cols].fillna(False).all(axis=1)
        frame["ALIGN_3TF_BEARISH"] = frame[bearish_cols].fillna(False).all(axis=1)
        frame.attrs["tf_stack"] = stack
        frame.attrs["tf_stack_effective"] = effective_stack
        prepared[symbol] = frame
    return prepared


def _build_position(symbol, timestamp, row, row_pos, strategy_name, direction, stop_distance, target_rr, exit_mode, reason, risk_fraction):
    spread_price = _safe_float(row.get("spread_price"), 0.0)
    close = _safe_float(row.get("close"))
    if not np.isfinite(close) or not np.isfinite(stop_distance) or stop_distance <= 0:
        return None

    entry_price = close + spread_price if direction == 1 else close
    stop_price = entry_price - stop_distance if direction == 1 else entry_price + stop_distance
    target_price = np.nan
    if target_rr is not None:
        target_distance = stop_distance * float(target_rr)
        target_price = entry_price + target_distance if direction == 1 else entry_price - target_distance

    position = {
        "symbol": symbol,
        "strategy": strategy_name,
        "entry_rule": strategy_name,
        "direction": int(direction),
        "setup_id": row_pos + 1,
        "entry_time": timestamp,
        "entry_price": float(entry_price),
        "stop_price": float(stop_price),
        "target_price": float(target_price) if np.isfinite(target_price) else np.nan,
        "target_extension": float(target_rr) if target_rr is not None else np.nan,
        "tp_mult": float(target_rr) if target_rr is not None else 0.0,
        "target_source": "FIXED_RR" if target_rr is not None else "SIGNAL_EXIT",
        "size_fraction": float(risk_fraction),
        "spread_price": spread_price,
        "active_from_pos": row_pos + 1,
        "exit_mode": exit_mode,
        "entry_signal_reason": reason,
        "BM_ATR_USED": _safe_float(row.get("ATR_14")),
        "BM_ALIGN_3TF_BULLISH": bool(row.get("ALIGN_3TF_BULLISH", False)),
        "BM_ALIGN_3TF_BEARISH": bool(row.get("ALIGN_3TF_BEARISH", False)),
    }
    for column_name in SYMBOL_SPEC_COLUMNS:
        position[column_name] = row.get(column_name, np.nan)
    return position


def _close_position(position, timestamp, exit_price, exit_reason):
    closed = dict(position)
    closed["exit_time"] = pd.Timestamp(timestamp)
    closed["exit_price"] = float(exit_price)
    closed["exit_reason"] = str(exit_reason)
    closed.pop("active_from_pos", None)
    return closed


def _signal_exit_price(position, row):
    close = _safe_float(row.get("close"))
    spread_price = _safe_float(row.get("spread_price"), 0.0)
    return close if position["direction"] == 1 else close + spread_price


def _check_stop_or_target(position, row, timestamp):
    spread_price = _safe_float(row.get("spread_price"), 0.0)
    low = _safe_float(row.get("low"))
    high = _safe_float(row.get("high"))
    if position["direction"] == 1:
        if low <= position["stop_price"]:
            return _close_position(position, timestamp, position["stop_price"], "SL")
        if np.isfinite(position.get("target_price", np.nan)) and high >= position["target_price"]:
            return _close_position(position, timestamp, position["target_price"], "TP")
        return None

    ask_high = high + spread_price
    ask_low = low + spread_price
    if ask_high >= position["stop_price"]:
        return _close_position(position, timestamp, position["stop_price"], "SL")
    if np.isfinite(position.get("target_price", np.nan)) and ask_low <= position["target_price"]:
        return _close_position(position, timestamp, position["target_price"], "TP")
    return None


def _opposite_ma_cross(row):
    sma20 = _safe_float(row.get("SMA20"))
    sma50 = _safe_float(row.get("SMA50"))
    prev_sma20 = _safe_float(row.get("_PREV_SMA20"))
    prev_sma50 = _safe_float(row.get("_PREV_SMA50"))
    cross_down = sma20 < sma50 and prev_sma20 >= prev_sma50
    cross_up = sma20 > sma50 and prev_sma20 <= prev_sma50
    return cross_down, cross_up


def _series_values(frame, column, default=np.nan, dtype=float):
    if column in frame.columns:
        return frame[column].to_numpy(dtype=dtype, copy=False)
    return np.full(len(frame), default, dtype=dtype)


def _previous_values(values):
    prev = np.empty_like(values)
    prev[0] = np.nan
    prev[1:] = values[:-1]
    return prev


def _build_position_fast(
    symbol,
    timestamp,
    row_pos,
    strategy_name,
    direction,
    stop_distance,
    target_rr,
    exit_mode,
    reason,
    risk_fraction,
    close,
    spread_price,
    atr,
    bullish,
    bearish,
    symbol_spec_values,
):
    if not np.isfinite(close) or not np.isfinite(stop_distance) or stop_distance <= 0:
        return None

    entry_price = close + spread_price if direction == 1 else close
    stop_price = entry_price - stop_distance if direction == 1 else entry_price + stop_distance
    target_price = np.nan
    if target_rr is not None:
        target_distance = stop_distance * float(target_rr)
        target_price = entry_price + target_distance if direction == 1 else entry_price - target_distance

    position = {
        "symbol": symbol,
        "strategy": strategy_name,
        "entry_rule": strategy_name,
        "direction": int(direction),
        "setup_id": row_pos + 1,
        "entry_time": timestamp,
        "entry_price": float(entry_price),
        "stop_price": float(stop_price),
        "target_price": float(target_price) if np.isfinite(target_price) else np.nan,
        "target_extension": float(target_rr) if target_rr is not None else np.nan,
        "tp_mult": float(target_rr) if target_rr is not None else 0.0,
        "target_source": "FIXED_RR" if target_rr is not None else "SIGNAL_EXIT",
        "size_fraction": float(risk_fraction),
        "spread_price": float(spread_price),
        "active_from_pos": row_pos + 1,
        "exit_mode": exit_mode,
        "entry_signal_reason": reason,
        "BM_ATR_USED": float(atr) if np.isfinite(atr) else np.nan,
        "BM_ALIGN_3TF_BULLISH": bool(bullish),
        "BM_ALIGN_3TF_BEARISH": bool(bearish),
    }
    for column_name in SYMBOL_SPEC_COLUMNS:
        position[column_name] = symbol_spec_values.get(column_name, np.nan)
    return position


def _simulate_symbol(symbol, df, strategy_name, strategy_config):
    if df is None or df.empty:
        return []

    frame = df.sort_index()
    timestamps = frame.index.to_numpy()
    high_values = _series_values(frame, "high")
    low_values = _series_values(frame, "low")
    close_values = _series_values(frame, "close")
    spread_values = _series_values(frame, "spread_price", default=0.0)
    rsi_values = _series_values(frame, "RSI_14")
    prev_rsi_values = _previous_values(rsi_values)
    atr_values = _series_values(frame, "ATR_14")
    sma20_values = _series_values(frame, "SMA20")
    sma50_values = _series_values(frame, "SMA50")
    prev_sma20_values = _previous_values(sma20_values)
    prev_sma50_values = _previous_values(sma50_values)
    lower_values = _series_values(frame, "BB_LOWER_20_2")
    upper_values = _series_values(frame, "BB_UPPER_20_2")
    bullish_values = _series_values(frame, "ALIGN_3TF_BULLISH", default=False, dtype=bool)
    bearish_values = _series_values(frame, "ALIGN_3TF_BEARISH", default=False, dtype=bool)
    symbol_spec_arrays = {
        column_name: frame[column_name].to_numpy(copy=False)
        for column_name in SYMBOL_SPEC_COLUMNS
        if column_name in frame.columns
    }

    position = None
    closed = []
    state = {
        "long_armed": False,
        "short_armed": False,
        "long_inside_count": 0,
        "short_inside_count": 0,
    }

    family = strategy_config["family"]
    risk_fraction = strategy_config.get("risk_fraction", 1.0)
    atr_stop_mult = float(strategy_config.get("atr_stop_mult", 1.5))

    for row_pos, timestamp in enumerate(timestamps):
        high = high_values[row_pos]
        low = low_values[row_pos]
        close = close_values[row_pos]
        spread_price = spread_values[row_pos]
        rsi = rsi_values[row_pos]
        prev_rsi = prev_rsi_values[row_pos]
        sma20 = sma20_values[row_pos]
        sma50 = sma50_values[row_pos]
        prev_sma20 = prev_sma20_values[row_pos]
        prev_sma50 = prev_sma50_values[row_pos]
        cross_down = sma20 < sma50 and prev_sma20 >= prev_sma50
        cross_up = sma20 > sma50 and prev_sma20 <= prev_sma50

        if position is not None and row_pos >= int(position["active_from_pos"]):
            stop_or_target = None
            if position["direction"] == 1:
                if low <= position["stop_price"]:
                    stop_or_target = _close_position(position, timestamp, position["stop_price"], "SL")
                elif np.isfinite(position.get("target_price", np.nan)) and high >= position["target_price"]:
                    stop_or_target = _close_position(position, timestamp, position["target_price"], "TP")
            else:
                ask_high = high + spread_price
                ask_low = low + spread_price
                if ask_high >= position["stop_price"]:
                    stop_or_target = _close_position(position, timestamp, position["stop_price"], "SL")
                elif np.isfinite(position.get("target_price", np.nan)) and ask_low <= position["target_price"]:
                    stop_or_target = _close_position(position, timestamp, position["target_price"], "TP")

            if stop_or_target is not None:
                closed.append(stop_or_target)
                position = None
            elif position is not None:
                if position["exit_mode"] == "rsi_opposite":
                    if position["direction"] == 1:
                        position["exit_armed"] = bool(position.get("exit_armed", False) or rsi >= 70.0)
                        if position["exit_armed"] and prev_rsi >= 70.0 and rsi < 70.0:
                            exit_price = close if position["direction"] == 1 else close + spread_price
                            closed.append(_close_position(position, timestamp, exit_price, "RSI_EXIT"))
                            position = None
                    else:
                        position["exit_armed"] = bool(position.get("exit_armed", False) or rsi <= 30.0)
                        if position["exit_armed"] and prev_rsi <= 30.0 and rsi > 30.0:
                            exit_price = close if position["direction"] == 1 else close + spread_price
                            closed.append(_close_position(position, timestamp, exit_price, "RSI_EXIT"))
                            position = None
                elif position["exit_mode"] == "ma_cross_after_1r":
                    if position["direction"] == 1 and high >= position["entry_price"] + position["initial_risk_distance"]:
                        position["min_rr_reached"] = True
                    if position["direction"] == -1 and (low + spread_price) <= position["entry_price"] - position["initial_risk_distance"]:
                        position["min_rr_reached"] = True
                    if position.get("min_rr_reached") and ((position["direction"] == 1 and cross_down) or (position["direction"] == -1 and cross_up)):
                        exit_price = close if position["direction"] == 1 else close + spread_price
                        closed.append(_close_position(position, timestamp, exit_price, "MA_CROSS_EXIT"))
                        position = None

        if position is not None or row_pos >= len(frame) - 1:
            continue

        atr = atr_values[row_pos]
        risk_distance = atr * atr_stop_mult
        bullish = bool(bullish_values[row_pos])
        bearish = bool(bearish_values[row_pos])

        # If the alignment regime breaks before confirmation, invalidate the
        # pending setup and require a fresh arm inside the active regime.
        if not bullish:
            state["long_armed"] = False
            state["long_inside_count"] = 0
        if not bearish:
            state["short_armed"] = False
            state["short_inside_count"] = 0

        direction = 0
        target_rr = strategy_config.get("target_rr")
        exit_mode = "fixed_rr"
        reason = ""

        if family == "rsi_mean_reversion":
            if bullish and rsi <= 30.0:
                state["long_armed"] = True
            if bearish and rsi >= 70.0:
                state["short_armed"] = True
            if state["long_armed"] and bullish and prev_rsi <= 30.0 and rsi > 30.0:
                direction, target_rr, exit_mode, reason = 1, None, "rsi_opposite", "RSI_RECOVERY_3TF_LONG"
                state["long_armed"] = False
            elif state["short_armed"] and bearish and prev_rsi >= 70.0 and rsi < 70.0:
                direction, target_rr, exit_mode, reason = -1, None, "rsi_opposite", "RSI_REJECTION_3TF_SHORT"
                state["short_armed"] = False

        elif family == "rsi_momentum_reentry":
            if bullish and rsi <= 40.0:
                state["long_armed"] = True
            if bearish and rsi >= 60.0:
                state["short_armed"] = True
            if state["long_armed"] and bullish and prev_rsi > 50.0 and rsi > 50.0:
                direction, exit_mode, reason = 1, "fixed_rr", "RSI_MOMENTUM_REENTRY_LONG"
                state["long_armed"] = False
            elif state["short_armed"] and bearish and prev_rsi < 50.0 and rsi < 50.0:
                direction, exit_mode, reason = -1, "fixed_rr", "RSI_MOMENTUM_REENTRY_SHORT"
                state["short_armed"] = False

        elif family == "ma_cross_trend":
            if bullish and cross_up:
                direction, target_rr, exit_mode, reason = 1, None, "ma_cross_after_1r", "SMA20_50_CROSS_3TF_LONG"
            elif bearish and cross_down:
                direction, target_rr, exit_mode, reason = -1, None, "ma_cross_after_1r", "SMA20_50_CROSS_3TF_SHORT"

        elif family == "bb_pullback_reentry":
            lower = lower_values[row_pos]
            upper = upper_values[row_pos]
            if bullish and close < lower:
                state["long_armed"] = True
                state["long_inside_count"] = 0
            elif state["long_armed"] and bullish and lower <= close <= upper:
                state["long_inside_count"] += 1
                if state["long_inside_count"] >= 2:
                    direction, exit_mode, reason = 1, "fixed_rr", "BB_REENTRY_3TF_LONG"
                    state["long_armed"] = False
            else:
                state["long_inside_count"] = 0

            if bearish and close > upper:
                state["short_armed"] = True
                state["short_inside_count"] = 0
            elif state["short_armed"] and bearish and lower <= close <= upper:
                state["short_inside_count"] += 1
                if state["short_inside_count"] >= 2:
                    direction, exit_mode, reason = -1, "fixed_rr", "BB_REENTRY_3TF_SHORT"
                    state["short_armed"] = False
            else:
                state["short_inside_count"] = 0

        if direction == 0:
            continue

        symbol_spec_values = {
            column_name: values[row_pos]
            for column_name, values in symbol_spec_arrays.items()
        }
        position = _build_position_fast(
            symbol=symbol,
            timestamp=timestamp,
            row_pos=row_pos,
            strategy_name=strategy_name,
            direction=direction,
            stop_distance=risk_distance,
            target_rr=target_rr,
            exit_mode=exit_mode,
            reason=reason,
            risk_fraction=risk_fraction,
            close=close,
            spread_price=spread_price,
            atr=atr,
            bullish=bullish,
            bearish=bearish,
            symbol_spec_values=symbol_spec_values,
        )
        if position is not None:
            position["initial_risk_distance"] = float(risk_distance)
            position["min_rr_reached"] = False

    if position is not None and not frame.empty:
        last_timestamp = timestamps[-1]
        last_close = close_values[-1]
        last_spread = spread_values[-1]
        exit_price = last_close if position["direction"] == 1 else last_close + last_spread
        closed.append(_close_position(position, last_timestamp, exit_price, "EOD"))

    return closed


def ejecutar_classic_benchmarks_3tf(
    portfolio,
    timeframe_ltf,
    timeframe_htf,
    strategies=None,
    account_config=None,
    tf_stack=None,
    raw_tf_map=None,
    group_name=None,
    return_details=False,
):
    strategy_defs = OrderedDict((strategies or CLASSIC_BENCHMARK_STRATEGIES).items())
    prepared = prepare_3tf_benchmark_portfolio(
        portfolio,
        timeframe_ltf=timeframe_ltf,
        timeframe_htf=timeframe_htf,
        tf_stack=tf_stack,
        raw_tf_map=raw_tf_map,
    )
    account_settings = get_account_config(account_config)
    trade_book = {}
    summary_rows = []
    split_rows = []

    for strategy_name, strategy_config in strategy_defs.items():
        raw_trades = []
        for symbol, df in prepared.items():
            raw_trades.extend(_simulate_symbol(symbol, df, strategy_name, strategy_config))

        if raw_trades:
            trades = pd.DataFrame(raw_trades).sort_values(["entry_time", "exit_time", "symbol"]).reset_index(drop=True)
            trades["timeframe_ltf"] = timeframe_ltf
            trades["timeframe_htf"] = timeframe_htf
            trades["tf_stack"] = ",".join(resolve_tf_stack(timeframe_ltf, timeframe_htf, tf_stack=tf_stack))
            effective_stack_values = {
                ",".join(tuple(df.attrs.get("tf_stack_effective", resolve_tf_stack(timeframe_ltf, timeframe_htf, tf_stack=tf_stack))))
                for df in prepared.values()
            }
            trades["tf_stack_effective"] = ",".join(sorted(effective_stack_values))
            if group_name is not None:
                trades["Group"] = group_name
            trades = apply_risk_position_sizing(trades, account_config=account_settings)
        else:
            trades = pd.DataFrame(columns=[
                "strategy", "entry_rule", "symbol", "direction", "setup_id",
                "entry_time", "exit_time", "entry_price", "exit_price",
                "stop_price", "target_price", "tp_mult", "size_fraction",
                "timeframe_ltf", "timeframe_htf", "Group",
            ])

        trade_book[strategy_name] = trades
        metrics = metrics_from_trades(trades)
        metrics["Variante"] = strategy_name
        metrics["Family"] = "benchmark"
        metrics["LTF"] = timeframe_ltf
        metrics["HTF"] = timeframe_htf
        metrics["Group"] = group_name
        summary_rows.append(metrics)

        periods = summarize_periods(trades, TEMPORAL_SPLITS)
        if not periods.empty:
            periods["Variante"] = strategy_name
            periods["Family"] = "benchmark"
            periods["LTF"] = timeframe_ltf
            periods["HTF"] = timeframe_htf
            periods["Group"] = group_name
            split_rows.append(periods)

    summary = pd.DataFrame(summary_rows)
    if summary.empty:
        summary = pd.DataFrame(columns=["Variante", "Family", "Group", "LTF", "HTF", *DEFAULT_METRIC_COLUMNS])
    else:
        summary = summary[["Variante", "Family", "Group", "LTF", "HTF", *DEFAULT_METRIC_COLUMNS]]

    if not return_details:
        return summary

    trade_log = pd.concat([t for t in trade_book.values() if t is not None and not t.empty], ignore_index=True) if any(not t.empty for t in trade_book.values()) else pd.DataFrame()
    return {
        "summary": summary,
        "splits": pd.concat(split_rows, ignore_index=True) if split_rows else pd.DataFrame(),
        "trades": trade_book,
        "trade_log": trade_log,
        "prepared_portfolio": prepared,
    }


def equity_curve_from_trades(trades, initial_capital=10000.0):
    if trades is None or trades.empty:
        return pd.Series(dtype=float)
    pnl = trades.groupby("exit_time")["pnl_money"].sum().sort_index()
    return float(initial_capital) + pnl.cumsum()


def drawdown_from_equity(equity):
    if equity is None or equity.empty:
        return pd.Series(dtype=float)
    return (equity / equity.cummax() - 1.0) * 100.0


def summarize_by_dimension(trade_log, dimension):
    if trade_log is None or trade_log.empty or dimension not in trade_log.columns:
        return pd.DataFrame(columns=["Variante", dimension, *DEFAULT_METRIC_COLUMNS])
    rows = []
    for (strategy, value), group in trade_log.groupby(["strategy", dimension], sort=True):
        metrics = metrics_from_trades(group)
        metrics["Variante"] = strategy
        metrics[dimension] = value
        rows.append(metrics)
    return pd.DataFrame(rows)[["Variante", dimension, *DEFAULT_METRIC_COLUMNS]]


def write_tables(tables, output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, df in tables.items():
        path = output / f"{name}.csv"
        (df if df is not None else pd.DataFrame()).to_csv(path, index=False)
        written[name] = path
    return written
