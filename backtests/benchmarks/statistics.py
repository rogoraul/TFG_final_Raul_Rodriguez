from __future__ import annotations

import pandas as pd

from backtests.common.trade_analysis import bootstrap_trade_metrics, extract_trades_from_result


def bootstrap_por_estrategia(resultado, metrics=None, n_boot=500, seed=42):
    rows = []
    trade_book = resultado.get("trades", resultado) if isinstance(resultado, dict) else resultado
    if isinstance(trade_book, pd.DataFrame):
        trade_book = {"strategy": trade_book}

    for strategy_name, trades in (trade_book or {}).items():
        if trades is None or trades.empty:
            continue
        boot = bootstrap_trade_metrics(trades, metrics=metrics, n_boot=n_boot, seed=seed)
        if boot.empty:
            continue
        boot["strategy"] = strategy_name
        rows.append(boot)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def comparar_resultados_bootstrap(resultados_por_nombre, metrics=None, n_boot=500, seed=42):
    rows = []
    for result_name, resultado in (resultados_por_nombre or {}).items():
        trades = extract_trades_from_result(resultado)
        if trades.empty:
            continue
        boot = bootstrap_trade_metrics(trades, metrics=metrics, n_boot=n_boot, seed=seed)
        if boot.empty:
            continue
        boot["result_name"] = result_name
        rows.append(boot)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
