"""Suite legacy de benchmarks simples.

Este modulo se conserva como helper ligero y por compatibilidad con tests
historicos del repo. La comparativa canonica del TFG para ENBOLSA se apoya en
``enbolsa_classic_benchmarks.py`` y en los runners asociados de esta carpeta.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from backtests.common.position_sizing import SYMBOL_SPEC_COLUMN_MAP, apply_risk_position_sizing
from backtests.common.trade_analysis import generate_result_breakdowns, metrics_from_trades, summarize_periods
from backtests.menendez.menendez_config import TEMPORAL_SPLITS, get_account_config


SYMBOL_SPEC_COLUMNS = tuple(SYMBOL_SPEC_COLUMN_MAP.values())

DEFAULT_BENCHMARK_STRATEGIES = OrderedDict((
    ("rsi_mean_reversion", {
        "family": "mean_reversion",
        "rsi_length": 14,
        "rsi_oversold": 30.0,
        "rsi_overbought": 70.0,
        "atr_length": 14,
        "atr_stop_mult": 1.5,
        "target_rr": 1.5,
        "risk_fraction": 1.0,
    }),
    ("sma_trend_follow", {
        "family": "trend_follow",
        "sma_fast": 20,
        "sma_slow": 50,
        "atr_length": 14,
        "atr_stop_mult": 1.75,
        "target_rr": 2.0,
        "risk_fraction": 1.0,
    }),
    ("macd_stoch_momentum", {
        "family": "momentum",
        "atr_length": 14,
        "atr_stop_mult": 1.4,
        "target_rr": 1.75,
        "risk_fraction": 1.0,
    }),
))


def _safe_float(value, default=np.nan):
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_max_workers(item_count, max_workers=None):
    if item_count <= 1:
        return 1
    if max_workers is not None:
        return max(1, min(int(max_workers), int(item_count)))
    cpu_count = os.cpu_count() or 1
    return max(1, min(int(item_count), int(cpu_count)))


def _ema(series, span):
    return pd.Series(series, copy=False).ewm(span=int(span), adjust=False).mean()


def _rsi(series, length):
    close = pd.Series(series, copy=False).astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / int(length), min_periods=int(length), adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / int(length), min_periods=int(length), adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(df, length):
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / int(length), min_periods=int(length), adjust=False).mean()


def preparar_portfolio_benchmarks(portfolio):
    prepared = {}
    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            continue
        frame = df.copy()
        frame["ATR_14"] = _atr(frame, 14)
        frame["RSI_14"] = _rsi(frame["close"], 14)
        frame["SMA_FAST_20"] = pd.to_numeric(frame["close"], errors="coerce").rolling(20, min_periods=20).mean()
        frame["SMA_SLOW_50"] = pd.to_numeric(frame["close"], errors="coerce").rolling(50, min_periods=50).mean()
        prepared[symbol] = frame
    return prepared


def _build_signal_frame(df, strategy_name, strategy_config):
    frame = df.copy()
    frame["BM_ENTRY_READY"] = False
    frame["BM_ENTRY_DIR"] = 0
    frame["BM_ENTRY_PRICE"] = np.nan
    frame["BM_SL_PRICE"] = np.nan
    frame["BM_TP_PRICE"] = np.nan
    frame["BM_SIGNAL_REASON"] = ""
    frame["BM_SIGNAL_NAME"] = strategy_name
    frame["BM_TARGET_RR"] = np.nan
    frame["BM_ATR_USED"] = np.nan

    spread_price = pd.to_numeric(frame.get("spread_price", 0.0), errors="coerce").fillna(0.0)
    close = pd.to_numeric(frame["close"], errors="coerce")
    atr_length = int(strategy_config.get("atr_length", 14))
    atr_col = f"ATR_{atr_length}"
    if atr_col not in frame.columns:
        frame[atr_col] = _atr(frame, atr_length)
    atr_values = pd.to_numeric(frame[atr_col], errors="coerce")
    atr_stop_mult = float(strategy_config.get("atr_stop_mult", 1.5))
    target_rr = float(strategy_config.get("target_rr", 1.5))

    if strategy_name == "rsi_mean_reversion":
        rsi_length = int(strategy_config.get("rsi_length", 14))
        rsi_col = f"RSI_{rsi_length}"
        if rsi_col not in frame.columns:
            frame[rsi_col] = _rsi(frame["close"], rsi_length)
        rsi = pd.to_numeric(frame[rsi_col], errors="coerce")
        oversold = float(strategy_config.get("rsi_oversold", 30.0))
        overbought = float(strategy_config.get("rsi_overbought", 70.0))
        long_mask = (rsi.shift(1) <= oversold) & (rsi > oversold)
        short_mask = (rsi.shift(1) >= overbought) & (rsi < overbought)
        reason_long = "RSI_RECOVERY_LONG"
        reason_short = "RSI_REJECTION_SHORT"
    elif strategy_name == "sma_trend_follow":
        fast_len = int(strategy_config.get("sma_fast", 20))
        slow_len = int(strategy_config.get("sma_slow", 50))
        fast_col = f"SMA_FAST_{fast_len}"
        slow_col = f"SMA_SLOW_{slow_len}"
        if fast_col not in frame.columns:
            frame[fast_col] = close.rolling(fast_len, min_periods=fast_len).mean()
        if slow_col not in frame.columns:
            frame[slow_col] = close.rolling(slow_len, min_periods=slow_len).mean()
        fast = pd.to_numeric(frame[fast_col], errors="coerce")
        slow = pd.to_numeric(frame[slow_col], errors="coerce")
        long_mask = (fast > slow) & (fast.shift(1) <= slow.shift(1)) & (slow.diff() > 0)
        short_mask = (fast < slow) & (fast.shift(1) >= slow.shift(1)) & (slow.diff() < 0)
        reason_long = "SMA_CROSS_LONG"
        reason_short = "SMA_CROSS_SHORT"
    elif strategy_name == "macd_stoch_momentum":
        macd_hist = pd.to_numeric(frame.get("MACD_HIST"), errors="coerce")
        stoch_up = pd.Series(frame.get("STOCH_CROSS_UP", False), index=frame.index).fillna(False).astype(bool)
        stoch_down = pd.Series(frame.get("STOCH_CROSS_DOWN", False), index=frame.index).fillna(False).astype(bool)
        long_mask = (macd_hist > 0) & (macd_hist.shift(1) <= 0) & stoch_up
        short_mask = (macd_hist < 0) & (macd_hist.shift(1) >= 0) & stoch_down
        reason_long = "MACD_STOCH_LONG"
        reason_short = "MACD_STOCH_SHORT"
    else:
        return frame

    risk_distance = atr_values * atr_stop_mult
    long_entry = close + spread_price
    short_entry = close
    long_sl = long_entry - risk_distance
    short_sl = short_entry + risk_distance
    long_tp = long_entry + (risk_distance * target_rr)
    short_tp = short_entry - (risk_distance * target_rr)

    frame.loc[long_mask, "BM_ENTRY_READY"] = True
    frame.loc[long_mask, "BM_ENTRY_DIR"] = 1
    frame.loc[long_mask, "BM_ENTRY_PRICE"] = long_entry[long_mask]
    frame.loc[long_mask, "BM_SL_PRICE"] = long_sl[long_mask]
    frame.loc[long_mask, "BM_TP_PRICE"] = long_tp[long_mask]
    frame.loc[long_mask, "BM_SIGNAL_REASON"] = reason_long
    frame.loc[long_mask, "BM_TARGET_RR"] = target_rr
    frame.loc[long_mask, "BM_ATR_USED"] = atr_values[long_mask]

    frame.loc[short_mask, "BM_ENTRY_READY"] = True
    frame.loc[short_mask, "BM_ENTRY_DIR"] = -1
    frame.loc[short_mask, "BM_ENTRY_PRICE"] = short_entry[short_mask]
    frame.loc[short_mask, "BM_SL_PRICE"] = short_sl[short_mask]
    frame.loc[short_mask, "BM_TP_PRICE"] = short_tp[short_mask]
    frame.loc[short_mask, "BM_SIGNAL_REASON"] = reason_short
    frame.loc[short_mask, "BM_TARGET_RR"] = target_rr
    frame.loc[short_mask, "BM_ATR_USED"] = atr_values[short_mask]
    return frame


def _build_position(symbol, timestamp, row, row_pos, strategy_name, strategy_config):
    direction = _safe_int(row.get("BM_ENTRY_DIR"), 0)
    entry_price = _safe_float(row.get("BM_ENTRY_PRICE"))
    stop_price = _safe_float(row.get("BM_SL_PRICE"))
    target_price = _safe_float(row.get("BM_TP_PRICE"))
    if not np.isfinite(entry_price) or not np.isfinite(stop_price) or not np.isfinite(target_price):
        return None
    if direction == 1 and stop_price >= entry_price:
        return None
    if direction == -1 and stop_price <= entry_price:
        return None

    position = {
        "strategy": strategy_name,
        "entry_rule": strategy_name,
        "symbol": symbol,
        "direction": direction,
        "setup_id": row_pos + 1,
        "entry_time": timestamp,
        "entry_price": float(entry_price),
        "stop_price": float(stop_price),
        "target_price": float(target_price),
        "target_extension": _safe_float(row.get("BM_TARGET_RR")),
        "tp_mult": _safe_float(row.get("BM_TARGET_RR")),
        "target_source": "FIXED_RR",
        "size_fraction": float(strategy_config.get("risk_fraction", 1.0)),
        "spread_price": _safe_float(row.get("spread_price"), 0.0),
        "timeframe_ltf": "M30",
        "timeframe_htf": "",
        "active_from_pos": row_pos + 1,
        "BM_SIGNAL_REASON": str(row.get("BM_SIGNAL_REASON", "") or ""),
        "BM_ATR_USED": _safe_float(row.get("BM_ATR_USED")),
        "BM_TARGET_RR": _safe_float(row.get("BM_TARGET_RR")),
    }
    for column_name in SYMBOL_SPEC_COLUMNS:
        position[column_name] = row.get(column_name, np.nan)
    return position


def _close_position(position, timestamp, exit_price, exit_reason):
    closed = dict(position)
    closed["exit_time"] = pd.Timestamp(timestamp)
    closed["exit_price"] = float(exit_price)
    closed["exit_reason"] = str(exit_reason)
    return closed


def _check_exit(position, row, timestamp):
    if position["direction"] == 1:
        if _safe_float(row.get("low")) <= position["stop_price"]:
            return _close_position(position, timestamp, position["stop_price"], "SL")
        if _safe_float(row.get("high")) >= position["target_price"]:
            return _close_position(position, timestamp, position["target_price"], "TP")
        return None

    spread_price = _safe_float(row.get("spread_price"), 0.0)
    ask_high = _safe_float(row.get("high")) + spread_price
    ask_low = _safe_float(row.get("low")) + spread_price
    if ask_high >= position["stop_price"]:
        return _close_position(position, timestamp, position["stop_price"], "SL")
    if ask_low <= position["target_price"]:
        return _close_position(position, timestamp, position["target_price"], "TP")
    return None


def _simulate_symbol(symbol, df, strategy_name, strategy_config):
    raw_trades = []
    if df is None or df.empty:
        return raw_trades

    signal_df = _build_signal_frame(df, strategy_name, strategy_config)
    position = None
    for row_pos, (timestamp, row) in enumerate(signal_df.iterrows()):
        if position is not None and row_pos >= int(position["active_from_pos"]):
            closed = _check_exit(position, row, timestamp)
            if closed is not None:
                raw_trades.append(closed)
                position = None

        if (
            position is None and
            row_pos < (len(signal_df) - 1) and
            bool(row.get("BM_ENTRY_READY", False))
        ):
            position = _build_position(symbol, timestamp, row, row_pos, strategy_name, strategy_config)

    if position is not None:
        last_timestamp = signal_df.index[-1]
        last_row = signal_df.iloc[-1]
        last_exit = _safe_float(last_row.get("close")) if position["direction"] == 1 else _safe_float(last_row.get("close")) + _safe_float(last_row.get("spread_price"), 0.0)
        raw_trades.append(_close_position(position, last_timestamp, last_exit, "EOD"))
    return raw_trades


def ejecutar_benchmarks(portfolio, strategies=None, account_config=None, return_details=False, parallel=True, max_workers=None):
    strategy_defs = OrderedDict((strategies or DEFAULT_BENCHMARK_STRATEGIES).items())
    prepared_portfolio = preparar_portfolio_benchmarks(portfolio)
    account_settings = get_account_config(account_config)
    summary_rows = []
    trade_book = {}
    split_rows = []
    portfolio_items = [(symbol, df) for symbol, df in prepared_portfolio.items() if df is not None and not df.empty]
    resolved_workers = _resolve_max_workers(len(portfolio_items), max_workers) if parallel else 1

    for strategy_name, strategy_config in strategy_defs.items():
        raw_trades = []
        if resolved_workers <= 1:
            for symbol, df in portfolio_items:
                raw_trades.extend(_simulate_symbol(symbol, df, strategy_name, strategy_config))
        else:
            with ThreadPoolExecutor(max_workers=resolved_workers, thread_name_prefix="benchmark-bt") as executor:
                futures = [
                    executor.submit(_simulate_symbol, symbol, df, strategy_name, strategy_config)
                    for symbol, df in portfolio_items
                ]
                for future in as_completed(futures):
                    raw_trades.extend(future.result())

        if raw_trades:
            trades = pd.DataFrame(raw_trades).sort_values(["entry_time", "exit_time", "symbol"]).reset_index(drop=True)
            trades = apply_risk_position_sizing(trades, account_config=account_settings)
        else:
            trades = pd.DataFrame(columns=[
                "strategy", "entry_rule", "symbol", "direction", "setup_id",
                "entry_time", "exit_time", "entry_price", "exit_price",
                "stop_price", "target_price", "tp_mult", "size_fraction",
            ])
        trade_book[strategy_name] = trades

        metricas = metrics_from_trades(trades)
        metricas["Variante"] = strategy_name
        metricas["LTF"] = "M30"
        metricas["HTF"] = ""
        summary_rows.append(metricas)

        period_df = summarize_periods(trades, TEMPORAL_SPLITS)
        if not period_df.empty:
            period_df["Variante"] = strategy_name
            split_rows.append(period_df)

    summary = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()
    if summary.empty:
        summary = pd.DataFrame(columns=["Variante", "LTF", "HTF"])
    if not return_details:
        return summary

    trade_log = pd.concat([frame for frame in trade_book.values() if frame is not None and not frame.empty], ignore_index=True) if any(not frame.empty for frame in trade_book.values()) else pd.DataFrame()
    return {
        "summary": summary,
        "summary_metrics": summary.copy(),
        "splits": pd.concat(split_rows, ignore_index=True) if split_rows else pd.DataFrame(),
        "trades": trade_book,
        "trade_log": trade_log,
        "desgloses": generate_result_breakdowns({"trades": trade_book}),
    }
