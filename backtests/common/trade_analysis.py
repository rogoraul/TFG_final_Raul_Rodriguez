"""Shared trade-log metrics and slicing helpers for benchmark reports."""

from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd


DEFAULT_METRIC_COLUMNS = [
    "Trades",
    "WR%",
    "AvgWin%",
    "AvgLoss%",
    "R:R",
    "PF",
    "Return%",
    "Sharpe",
    "Sortino",
    "MaxDD%",
    "Calmar",
    "NetProfit",
    "Expectancy",
    "AvgR",
    "ExpectancyR",
    "Exposure%",
    "ReturnOverDrawdown",
]


def _safe_float(value, default=np.nan):
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _trade_book_to_frame(trade_book):
    frames = []
    for strategy_name, trades in (trade_book or {}).items():
        if trades is None or trades.empty:
            continue
        frame = trades.copy()
        if "strategy" not in frame.columns:
            frame["strategy"] = strategy_name
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def metrics_from_trades(trades):
    """Compute the canonical metric row for a trade DataFrame."""
    if trades is None or trades.empty:
        return {
            "Trades": 0,
            "WR%": 0.0,
            "AvgWin%": 0.0,
            "AvgLoss%": 0.0,
            "R:R": 0.0,
            "PF": 0.0,
            "Return%": 0.0,
            "Sharpe": 0.0,
            "Sortino": 0.0,
            "MaxDD%": 0.0,
            "Calmar": 0.0,
            "NetProfit": 0.0,
            "Expectancy": 0.0,
            "AvgR": 0.0,
            "ExpectancyR": 0.0,
            "Exposure%": 0.0,
            "ReturnOverDrawdown": 0.0,
        }

    pnl_col = "pnl_money" if "pnl_money" in trades.columns else "pnl"
    wins = trades[trades[pnl_col] > 0]
    losses = trades[trades[pnl_col] <= 0]
    n_trades = len(trades)
    wr = len(wins) / n_trades * 100.0
    avg_win = (
        wins["weighted_return"].mean() * 100.0
        if not wins.empty and "weighted_return" in wins.columns
        else 0.0
    )
    avg_loss = (
        losses["weighted_return"].mean() * 100.0
        if not losses.empty and "weighted_return" in losses.columns
        else 0.0
    )
    rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    gross_win = wins[pnl_col].sum()
    gross_loss = abs(losses[pnl_col].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else np.inf

    initial_capital = float(
        trades.attrs.get(
            "initial_capital",
            trades.get("balance_before_entry", pd.Series([10000.0])).iloc[0]
            if "balance_before_entry" in trades.columns else 10000.0
        )
    )
    event_pnl = trades.groupby("exit_time")[pnl_col].sum().sort_index()
    equity_before = initial_capital + event_pnl.cumsum().shift(1, fill_value=0.0)
    event_returns = (event_pnl / equity_before.replace(0.0, np.nan)).fillna(0.0)
    equity = initial_capital + event_pnl.cumsum()
    total_return = (
        ((equity.iloc[-1] / initial_capital) - 1.0) * 100.0
        if not equity.empty and initial_capital > 0
        else 0.0
    )

    if len(event_returns) > 1 and event_returns.std(ddof=0) > 0:
        sharpe = (event_returns.mean() / event_returns.std(ddof=0)) * sqrt(len(event_returns))
    else:
        sharpe = 0.0

    downside = event_returns[event_returns < 0]
    if len(downside) > 0 and downside.std(ddof=0) > 0:
        sortino = (event_returns.mean() / downside.std(ddof=0)) * sqrt(len(event_returns))
    else:
        sortino = 0.0

    if not equity.empty:
        rolling_peak = equity.cummax()
        drawdown = equity / rolling_peak - 1.0
        max_dd = abs(drawdown.min()) * 100.0
        days = max((equity.index[-1] - equity.index[0]).days, 1)
        years = days / 365.25
        final_growth = float((equity.iloc[-1] / initial_capital)) if initial_capital > 0 else np.nan
        if years > 0 and np.isfinite(final_growth):
            annual_return = final_growth ** (1 / years) - 1.0 if final_growth > 0 else -1.0
        else:
            annual_return = 0.0
        calmar = annual_return / abs(drawdown.min()) if drawdown.min() < 0 else 0.0
        return_over_drawdown = total_return / max_dd if max_dd > 0 else np.inf
    else:
        max_dd = 0.0
        calmar = 0.0
        return_over_drawdown = 0.0

    risk_amount = pd.to_numeric(trades.get("risk_amount"), errors="coerce")
    realized_r = pd.Series(dtype=float)
    if risk_amount is not None and not risk_amount.empty:
        valid_risk = risk_amount > 0
        realized_r = pd.Series(np.nan, index=trades.index, dtype=float)
        realized_r.loc[valid_risk] = pd.to_numeric(trades[pnl_col], errors="coerce").loc[valid_risk] / risk_amount.loc[valid_risk]

    expectancy = float(pd.to_numeric(trades[pnl_col], errors="coerce").mean()) if n_trades > 0 else 0.0
    avg_r = float(realized_r.mean()) if not realized_r.empty else 0.0
    expectancy_r = avg_r

    if {"entry_time", "exit_time"}.issubset(trades.columns):
        entry_times = pd.to_datetime(trades["entry_time"], errors="coerce")
        exit_times = pd.to_datetime(trades["exit_time"], errors="coerce")
        valid_times = entry_times.notna() & exit_times.notna()
        if bool(valid_times.any()):
            durations = (exit_times[valid_times] - entry_times[valid_times]).dt.total_seconds().clip(lower=0.0)
            span = (exit_times[valid_times].max() - entry_times[valid_times].min()).total_seconds()
            exposure = (durations.sum() / span) * 100.0 if span > 0 else 0.0
        else:
            exposure = 0.0
    else:
        exposure = 0.0

    return {
        "Trades": int(n_trades),
        "WR%": round(wr, 1),
        "AvgWin%": round(avg_win, 2),
        "AvgLoss%": round(avg_loss, 2),
        "R:R": round(rr, 2),
        "PF": round(pf, 2) if np.isfinite(pf) else np.inf,
        "Return%": round(total_return, 2),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2),
        "MaxDD%": round(max_dd, 2),
        "Calmar": round(calmar, 2),
        "NetProfit": round(float(pd.to_numeric(trades[pnl_col], errors="coerce").sum()), 2),
        "Expectancy": round(expectancy, 2),
        "AvgR": round(avg_r, 3),
        "ExpectancyR": round(expectancy_r, 3),
        "Exposure%": round(float(exposure), 2),
        "ReturnOverDrawdown": round(return_over_drawdown, 2) if np.isfinite(return_over_drawdown) else np.inf,
    }


def extract_trades_from_result(resultado, strategy=None, symbol=None, direction=None, exit_reason=None):
    """Extract and optionally filter a normalized trade log from a backtest result."""
    if isinstance(resultado, pd.DataFrame):
        trades = resultado.copy()
    elif isinstance(resultado, dict):
        trades = _trade_book_to_frame(resultado.get("trades", resultado))
    else:
        trades = pd.DataFrame()

    if trades.empty:
        return trades
    if strategy is not None:
        strategies = {strategy} if isinstance(strategy, str) else set(strategy)
        trades = trades[trades["strategy"].isin(strategies)]
    if symbol is not None:
        symbols = {symbol} if isinstance(symbol, str) else set(symbol)
        trades = trades[trades["symbol"].isin(symbols)]
    if direction is not None and "direction" in trades.columns:
        if isinstance(direction, str):
            normalized = direction.strip().lower()
            if normalized in {"long", "largo", "buy", "compra", "compras"}:
                direction = 1
            elif normalized in {"short", "corto", "sell", "venta", "ventas"}:
                direction = -1
            else:
                direction = None
        trades = trades[trades["direction"] == direction] if direction in {1, -1} else trades
    if exit_reason is not None and "exit_reason" in trades.columns:
        reasons = {exit_reason} if isinstance(exit_reason, str) else set(exit_reason)
        trades = trades[trades["exit_reason"].isin(reasons)]
    sort_cols = [col for col in ("entry_time", "exit_time", "symbol", "tp_mult") if col in trades.columns]
    return trades.sort_values(sort_cols).reset_index(drop=True) if sort_cols else trades.reset_index(drop=True)


def summarize_periods(trades, splits):
    rows = []
    for period_name, (start, end) in (splits or {}).items():
        period_trades = trades.copy()
        if start is not None:
            period_trades = period_trades[period_trades["entry_time"] >= pd.Timestamp(start)]
        if end is not None:
            period_trades = period_trades[period_trades["entry_time"] < pd.Timestamp(end)]
        metricas = metrics_from_trades(period_trades)
        metricas["Periodo"] = period_name
        rows.append(metricas)
    if not rows:
        return pd.DataFrame()
    cols = ["Periodo", *DEFAULT_METRIC_COLUMNS]
    return pd.DataFrame(rows)[cols]


def generate_result_breakdowns(resultado, top_n=8):
    trade_book = resultado.get("trades", resultado) if isinstance(resultado, dict) else resultado
    all_trades = _trade_book_to_frame(trade_book)
    metric_cols = DEFAULT_METRIC_COLUMNS
    empty_asset = pd.DataFrame(columns=["Variante", "Activo", *metric_cols])
    empty_exit = pd.DataFrame(columns=["Variante", "Salida", "Trades", "Pct%"])
    if all_trades.empty:
        return {
            "por_activo_estrategia": empty_asset,
            "top_activos": empty_asset.copy(),
            "bottom_activos": empty_asset.copy(),
            "salidas": empty_exit,
        }

    rows = []
    for (strategy_name, symbol), group in all_trades.groupby(["strategy", "symbol"], sort=True):
        metricas = metrics_from_trades(group)
        metricas["Variante"] = strategy_name
        metricas["Activo"] = symbol
        rows.append(metricas)

    por_activo = pd.DataFrame(rows)
    por_activo = por_activo[["Variante", "Activo", *metric_cols]].sort_values(
        ["Variante", "Return%", "PF", "Trades"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)

    top_rows = []
    bottom_rows = []
    for strategy_name, group in por_activo.groupby("Variante", sort=False):
        top_rows.append(group.head(top_n))
        bottom_rows.append(
            group.sort_values(["Return%", "PF", "Trades"], ascending=[True, True, False]).head(top_n)
        )

    salidas = (
        all_trades.groupby(["strategy", "exit_reason"])
        .size()
        .rename("Trades")
        .reset_index()
        .rename(columns={"strategy": "Variante", "exit_reason": "Salida"})
    )
    salidas["Pct%"] = (
        salidas["Trades"] / salidas.groupby("Variante")["Trades"].transform("sum") * 100.0
    ).round(1)
    salidas = salidas[["Variante", "Salida", "Trades", "Pct%"]].sort_values(
        ["Variante", "Trades"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return {
        "por_activo_estrategia": por_activo,
        "top_activos": pd.concat(top_rows, ignore_index=True) if top_rows else empty_asset.copy(),
        "bottom_activos": pd.concat(bottom_rows, ignore_index=True) if bottom_rows else empty_asset.copy(),
        "salidas": salidas if not salidas.empty else empty_exit,
    }


def bootstrap_trade_metrics(trades, metrics=None, n_boot=500, seed=42):
    metrics = list(metrics or ("WR%", "PF", "Return%", "MaxDD%", "AvgR", "ExpectancyR"))
    trades = trades.copy() if trades is not None else pd.DataFrame()
    if trades.empty:
        return pd.DataFrame(columns=["metric", "mean", "median", "p05", "p95", "samples"])

    rng = np.random.default_rng(seed)
    boot_rows = []
    for _ in range(int(n_boot)):
        sample_idx = rng.integers(0, len(trades), len(trades))
        sample = trades.iloc[sample_idx].copy()
        sample.attrs.update(trades.attrs)
        metric_row = metrics_from_trades(sample)
        boot_rows.append({metric: _safe_float(metric_row.get(metric)) for metric in metrics})

    boot_df = pd.DataFrame(boot_rows)
    rows = []
    for metric in metrics:
        series = pd.to_numeric(boot_df[metric], errors="coerce").dropna()
        if series.empty:
            continue
        rows.append({
            "metric": metric,
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "p05": round(float(series.quantile(0.05)), 4),
            "p95": round(float(series.quantile(0.95)), 4),
            "samples": int(len(series)),
        })
    return pd.DataFrame(rows)
