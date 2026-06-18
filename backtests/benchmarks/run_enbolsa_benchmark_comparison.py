from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from collections import OrderedDict
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtests.common.backtest_matrix_config import (
    DEFAULT_ASSET_GROUPS,
    DEFAULT_STRATEGIES,
    TEMPORAL_SPLITS,
    get_account_config,
    get_selected_groups,
    get_timeframe_pairs,
)
from backtests.common.trade_analysis import DEFAULT_METRIC_COLUMNS, metrics_from_trades, summarize_periods

from enbolsa_classic_benchmarks import (
    CLASSIC_BENCHMARK_STRATEGIES,
    ejecutar_classic_benchmarks_3tf,
    write_tables,
)


MAIN_ENBOLSA_STRATEGIES = OrderedDict(
    (name, DEFAULT_STRATEGIES[name])
    for name in ("fib_limit", "macd_breakout")
)
SECONDARY_ENBOLSA_STRATEGIES = OrderedDict(
    (name, DEFAULT_STRATEGIES[name])
    for name in ("combined_split",)
)


def _enbolsa_strategy_set(base_strategies, swing_quality_gate_enabled=False):
    strategies = OrderedDict((name, deepcopy(config)) for name, config in base_strategies.items())
    if not swing_quality_gate_enabled:
        return strategies
    for config in strategies.values():
        config["swing_quality_gate_enabled"] = True
        config["quality_gate_version"] = "enbolsa_swing_quality_v1"
        for leg in config.get("legs", ()):
            leg["swing_quality_gate_enabled"] = True
            leg["quality_gate_version"] = "enbolsa_swing_quality_v1"
    return strategies

TRADE_POOL_METRIC_COLUMNS = [
    "Trades",
    "WR%",
    "AvgWin%",
    "AvgLoss%",
    "R:R",
    "PF",
    "NetProfit",
    "Expectancy",
    "AvgR",
    "ExpectancyR",
]

BLOCK_AGGREGATE_COLUMNS = [
    "Blocks",
    "TotalTrades",
    "TotalNetProfit",
    "MeanReturn%",
    "MedianReturn%",
    "MinReturn%",
    "MaxReturn%",
    "StdReturn%",
    "PositiveBlocks",
    "PositiveBlockRate%",
    "MeanPF",
    "MedianPF",
    "MeanMaxDD%",
    "MedianMaxDD%",
    "MeanSharpe",
    "MedianSharpe",
    "MeanSortino",
    "MedianSortino",
    "MeanCalmar",
    "MedianCalmar",
    "MeanExposure%",
    "MedianExposure%",
    "MeanReturnOverDrawdown",
    "MedianReturnOverDrawdown",
    "MeanAvgR",
    "MedianAvgR",
]


def _parse_tf_pairs(values):
    if not values:
        return None
    pairs = OrderedDict()
    for value in values:
        ltf, htf = value.split(":", 1)
        pairs[ltf.strip()] = htf.strip()
    return pairs


def _prefixed_strategy_name(family, strategy):
    return f"{family}:{strategy}"


def _normalize_result_trades(result, family, group_name, timeframe_ltf, timeframe_htf):
    frames = []
    for strategy_name, trades in result.get("trades", {}).items():
        if trades is None or trades.empty:
            continue
        frame = trades.copy()
        frame["strategy"] = _prefixed_strategy_name(family, strategy_name)
        frame["source_family"] = family
        frame["Group"] = group_name
        frame["timeframe_ltf"] = timeframe_ltf
        frame["timeframe_htf"] = timeframe_htf
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _tf_pair_label(ltf, htf):
    return f"{ltf}:{htf}"


def _block_id(group_name, ltf, htf):
    clean_group = str(group_name).strip().lower().replace(" ", "-")
    return f"{clean_group}-{str(ltf).lower()}-{str(htf).lower()}"


def _first_nonempty(values, default=""):
    for value in values:
        if pd.notna(value) and str(value).strip():
            return str(value)
    return default


def _normalise_trade_log_for_blocks(trade_log):
    result = trade_log.copy() if trade_log is not None else pd.DataFrame()
    if result.empty:
        return result
    if "source_family" not in result.columns and "strategy" in result.columns:
        result["source_family"] = result["strategy"].astype(str).str.split(":", n=1).str[0]
    for column in ("entry_time", "exit_time"):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def _block_metrics_from_trade_log(trade_log, initial_capital=10000.0):
    cols = [
        "Variante",
        "Family",
        "Group",
        "LTF",
        "HTF",
        "TFPair",
        "BlockId",
        "MetricScope",
        "TFStackEffective",
        "H4D1Mode",
        "PartialSource",
        *DEFAULT_METRIC_COLUMNS,
    ]
    trade_log = _normalise_trade_log_for_blocks(trade_log)
    if trade_log.empty:
        return pd.DataFrame(columns=cols)

    required = {"strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf"}
    if not required.issubset(trade_log.columns):
        missing = ", ".join(sorted(required.difference(trade_log.columns)))
        raise ValueError(f"El trade_log no contiene columnas de bloque requeridas: {missing}")

    rows = []
    group_cols = ["strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf"]
    for (strategy, family, group_name, ltf, htf), block in trade_log.groupby(group_cols, dropna=False, sort=True):
        scoped = block.copy()
        scoped.attrs["initial_capital"] = float(initial_capital)
        metrics = metrics_from_trades(scoped)
        tf_pair = _tf_pair_label(ltf, htf)
        stack = _first_nonempty(block.get("tf_stack_effective", pd.Series(dtype=object)).dropna().unique())
        partial_source = ",".join(
            sorted(str(value) for value in block.get("partial_source", pd.Series(dtype=object)).dropna().unique())
        )
        h4d1_mode = "degraded_2tf_h4_d1" if str(ltf) == "H4" and str(htf) == "D1" else "normal_stack"
        rows.append({
            "Variante": strategy,
            "Family": family,
            "Group": group_name,
            "LTF": ltf,
            "HTF": htf,
            "TFPair": tf_pair,
            "BlockId": _block_id(group_name, ltf, htf),
            "MetricScope": "block_portfolio",
            "TFStackEffective": stack,
            "H4D1Mode": h4d1_mode,
            "PartialSource": partial_source,
            **metrics,
        })
    return pd.DataFrame(rows)[cols]


def _block_period_metrics_from_trade_log(trade_log, initial_capital=10000.0):
    trade_log = _normalise_trade_log_for_blocks(trade_log)
    if trade_log.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf"]
    for (strategy, family, group_name, ltf, htf), block in trade_log.groupby(group_cols, dropna=False, sort=True):
        scoped = block.copy()
        scoped.attrs["initial_capital"] = float(initial_capital)
        periods = summarize_periods(scoped, TEMPORAL_SPLITS)
        if periods.empty:
            continue
        periods["Variante"] = strategy
        periods["Family"] = family
        periods["Group"] = group_name
        periods["LTF"] = ltf
        periods["HTF"] = htf
        periods["TFPair"] = _tf_pair_label(ltf, htf)
        periods["BlockId"] = _block_id(group_name, ltf, htf)
        periods["MetricScope"] = "block_period_portfolio"
        rows.append(periods)
    if not rows:
        return pd.DataFrame()
    cols = ["Variante", "Family", "Group", "LTF", "HTF", "TFPair", "BlockId", "Periodo", "MetricScope", *DEFAULT_METRIC_COLUMNS]
    return pd.concat(rows, ignore_index=True)[cols]


def _aggregate_block_metrics(block_metrics, dimensions=()):
    dimensions = tuple(dimensions or ())
    cols = ["Variante", "Family", *dimensions, "MetricScope", *BLOCK_AGGREGATE_COLUMNS]
    if block_metrics is None or block_metrics.empty:
        return pd.DataFrame(columns=cols)

    rows = []
    group_cols = ["Variante", *dimensions]
    for keys, group in block_metrics.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {"Variante": keys[0], "Family": _first_nonempty(group["Family"].unique()), "MetricScope": "block_aggregate"}
        for name, value in zip(dimensions, keys[1:]):
            row[name] = value

        returns = pd.to_numeric(group["Return%"], errors="coerce")
        pf = pd.to_numeric(group["PF"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        max_dd = pd.to_numeric(group["MaxDD%"], errors="coerce")
        sharpe = pd.to_numeric(group["Sharpe"], errors="coerce")
        sortino = pd.to_numeric(group["Sortino"], errors="coerce")
        calmar = pd.to_numeric(group["Calmar"], errors="coerce")
        exposure = pd.to_numeric(group["Exposure%"], errors="coerce")
        rod = pd.to_numeric(group["ReturnOverDrawdown"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        avg_r = pd.to_numeric(group["AvgR"], errors="coerce")

        row.update({
            "Blocks": int(len(group)),
            "TotalTrades": int(pd.to_numeric(group["Trades"], errors="coerce").fillna(0).sum()),
            "TotalNetProfit": round(float(pd.to_numeric(group["NetProfit"], errors="coerce").fillna(0).sum()), 2),
            "MeanReturn%": round(float(returns.mean()), 2) if returns.notna().any() else 0.0,
            "MedianReturn%": round(float(returns.median()), 2) if returns.notna().any() else 0.0,
            "MinReturn%": round(float(returns.min()), 2) if returns.notna().any() else 0.0,
            "MaxReturn%": round(float(returns.max()), 2) if returns.notna().any() else 0.0,
            "StdReturn%": round(float(returns.std(ddof=0)), 2) if returns.notna().any() else 0.0,
            "PositiveBlocks": int((returns > 0).sum()),
            "PositiveBlockRate%": round(float((returns > 0).mean() * 100.0), 1) if len(returns) else 0.0,
            "MeanPF": round(float(pf.mean()), 2) if pf.notna().any() else 0.0,
            "MedianPF": round(float(pf.median()), 2) if pf.notna().any() else 0.0,
            "MeanMaxDD%": round(float(max_dd.mean()), 2) if max_dd.notna().any() else 0.0,
            "MedianMaxDD%": round(float(max_dd.median()), 2) if max_dd.notna().any() else 0.0,
            "MeanSharpe": round(float(sharpe.mean()), 2) if sharpe.notna().any() else 0.0,
            "MedianSharpe": round(float(sharpe.median()), 2) if sharpe.notna().any() else 0.0,
            "MeanSortino": round(float(sortino.mean()), 2) if sortino.notna().any() else 0.0,
            "MedianSortino": round(float(sortino.median()), 2) if sortino.notna().any() else 0.0,
            "MeanCalmar": round(float(calmar.mean()), 2) if calmar.notna().any() else 0.0,
            "MedianCalmar": round(float(calmar.median()), 2) if calmar.notna().any() else 0.0,
            "MeanExposure%": round(float(exposure.mean()), 2) if exposure.notna().any() else 0.0,
            "MedianExposure%": round(float(exposure.median()), 2) if exposure.notna().any() else 0.0,
            "MeanReturnOverDrawdown": round(float(rod.mean()), 2) if rod.notna().any() else 0.0,
            "MedianReturnOverDrawdown": round(float(rod.median()), 2) if rod.notna().any() else 0.0,
            "MeanAvgR": round(float(avg_r.mean()), 3) if avg_r.notna().any() else 0.0,
            "MedianAvgR": round(float(avg_r.median()), 3) if avg_r.notna().any() else 0.0,
        })
        rows.append(row)
    return pd.DataFrame(rows)[cols]


def _trade_pool_by_dimension(trade_log, dimensions=()):
    dimensions = tuple(dimensions or ())
    cols = ["Variante", "Family", *dimensions, "MetricScope", *TRADE_POOL_METRIC_COLUMNS]
    trade_log = _normalise_trade_log_for_blocks(trade_log)
    if trade_log.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    group_cols = ["strategy", *dimensions]
    for keys, group in trade_log.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        metrics = metrics_from_trades(group)
        row = {
            "Variante": keys[0],
            "Family": _first_nonempty(group.get("source_family", pd.Series(dtype=object)).unique()),
            "MetricScope": "trade_pool",
        }
        for name, value in zip(dimensions, keys[1:]):
            row[name] = value
        for metric in TRADE_POOL_METRIC_COLUMNS:
            row[metric] = metrics.get(metric, 0.0)
        rows.append(row)
    return pd.DataFrame(rows)[cols]


def _trade_pool_cumulative_r(trade_log):
    trade_log = trade_log.copy() if trade_log is not None else pd.DataFrame()
    if trade_log.empty:
        return pd.DataFrame(columns=["Variante", "TradeNumber", "CumR"])

    pnl_col = "pnl_money" if "pnl_money" in trade_log.columns else "pnl"
    if pnl_col not in trade_log.columns or "risk_amount" not in trade_log.columns:
        return pd.DataFrame(columns=["Variante", "TradeNumber", "CumR"])

    frame = trade_log.copy()
    if "Variante" not in frame.columns or frame["Variante"].isna().all() or (frame["Variante"].astype(str).str.strip() == "").all():
        if "strategy" not in frame.columns:
            return pd.DataFrame(columns=["Variante", "TradeNumber", "CumR"])
        frame["Variante"] = frame["strategy"]
    frame[pnl_col] = pd.to_numeric(frame[pnl_col], errors="coerce")
    frame["risk_amount"] = pd.to_numeric(frame["risk_amount"], errors="coerce")
    frame = frame[frame["risk_amount"] > 0].copy()
    if frame.empty:
        return pd.DataFrame(columns=["Variante", "TradeNumber", "CumR"])

    time_col = "exit_time" if "exit_time" in frame.columns else "entry_time"
    if time_col in frame.columns:
        frame[time_col] = pd.to_datetime(frame[time_col], errors="coerce")
    else:
        frame[time_col] = pd.NaT

    frame["RealizedR"] = frame[pnl_col] / frame["risk_amount"]
    frame = frame.sort_values(["Variante", time_col], kind="stable").reset_index(drop=True)

    rows = []
    for strategy, group in frame.groupby("Variante", sort=True):
        ordered = group.reset_index(drop=True).copy()
        ordered["TradeNumber"] = np.arange(1, len(ordered) + 1)
        ordered["CumR"] = ordered["RealizedR"].cumsum()
        rows.append(ordered[["Variante", "TradeNumber", "CumR"]])
    if not rows:
        return pd.DataFrame(columns=["Variante", "TradeNumber", "CumR"])
    return pd.concat(rows, ignore_index=True)


def _write_charts(
    block_metrics,
    block_period_metrics,
    aggregate_global,
    aggregate_by_group,
    trade_log,
    trade_pool_by_asset,
    charts_dir,
    initial_capital=10000.0,
):
    charts_path = Path(charts_dir)
    charts_path.mkdir(parents=True, exist_ok=True)
    if block_metrics is None or block_metrics.empty:
        return {}

    written = {}
    heat = block_metrics.pivot_table(index="BlockId", columns="Variante", values="Return%", aggfunc="mean")
    if not heat.empty:
        plt.figure(figsize=(max(11, len(heat.columns) * 1.6), max(5, len(heat.index) * 0.45)))
        plt.imshow(heat.values, aspect="auto", cmap="RdYlGn")
        plt.colorbar(label="Return% por bloque")
        plt.xticks(range(len(heat.columns)), heat.columns, rotation=45, ha="right", fontsize=8)
        plt.yticks(range(len(heat.index)), heat.index, fontsize=8)
        plt.title("Return% por estrategia y bloque independiente")
        plt.tight_layout()
        path = charts_path / "heatmap_returnpct_por_bloque.png"
        plt.savefig(path, dpi=160)
        plt.close()
        written["heatmap_returnpct_por_bloque"] = path

    if aggregate_global is not None and not aggregate_global.empty:
        plot_df = aggregate_global.sort_values("MeanReturn%")
        y = np.arange(len(plot_df))
        height = 0.38
        plt.figure(figsize=(12, 6))
        plt.barh(y - height / 2, plot_df["MeanReturn%"], height=height, label="Media")
        plt.barh(y + height / 2, plot_df["MedianReturn%"], height=height, label="Mediana")
        plt.yticks(y, plot_df["Variante"], fontsize=8)
        plt.xlabel("Return% entre bloques")
        plt.title("Media y mediana de Return% por estrategia")
        plt.legend()
        plt.tight_layout()
        path = charts_path / "barras_media_mediana_returnpct.png"
        plt.savefig(path, dpi=160)
        plt.close()
        written["barras_media_mediana_returnpct"] = path

        pf_df = aggregate_global.sort_values("MedianPF")
        plt.figure(figsize=(11, 6))
        plt.barh(pf_df["Variante"], pf_df["MedianPF"])
        plt.xlabel("PF mediano entre bloques")
        plt.title("Profit Factor mediano por estrategia")
        plt.tight_layout()
        path = charts_path / "barras_median_pf.png"
        plt.savefig(path, dpi=160)
        plt.close()
        written["barras_median_pf"] = path

    cumulative_r = _trade_pool_cumulative_r(trade_log)
    if not cumulative_r.empty:
        plt.figure(figsize=(12, 6))
        for strategy, group in cumulative_r.groupby("Variante", sort=True):
            plt.plot(group["TradeNumber"], group["CumR"], linewidth=2, label=strategy)
        plt.axhline(0.0, color="black", linewidth=1, linestyle="--", alpha=0.7)
        plt.ylabel("R acumulada")
        plt.xlabel("Numero de trade")
        plt.title("Evolucion acumulada del rendimiento por trade")
        plt.legend(fontsize=8, loc="best")
        plt.tight_layout()
        path = charts_path / "lineas_r_acumulada_por_trade.png"
        plt.savefig(path, dpi=160)
        plt.close()
        written["lineas_r_acumulada_por_trade"] = path

    if aggregate_by_group is not None and not aggregate_by_group.empty:
        group_heat = aggregate_by_group.pivot_table(index="Group", columns="Variante", values="MeanReturn%", aggfunc="mean")
        if not group_heat.empty:
            plt.figure(figsize=(max(11, len(group_heat.columns) * 1.5), 5))
            plt.imshow(group_heat.values, aspect="auto", cmap="RdYlGn")
            plt.colorbar(label="MeanReturn%")
            plt.xticks(range(len(group_heat.columns)), group_heat.columns, rotation=45, ha="right", fontsize=8)
            plt.yticks(range(len(group_heat.index)), group_heat.index, fontsize=9)
            plt.title("Return% medio por grupo y estrategia")
            plt.tight_layout()
            path = charts_path / "heatmap_returnpct_por_grupo.png"
            plt.savefig(path, dpi=160)
            plt.close()
            written["heatmap_returnpct_por_grupo"] = path

    strategies = []
    data = []
    for strategy, group in block_metrics.groupby("Variante", sort=True):
        values = pd.to_numeric(group["Return%"], errors="coerce").dropna()
        if values.empty:
            continue
        strategies.append(strategy)
        data.append(values.to_numpy())
    if data:
        plt.figure(figsize=(12, max(5, len(data) * 0.55)))
        plt.boxplot(data, tick_labels=strategies, vert=False, showmeans=True)
        plt.xlabel("Return% por bloque")
        plt.title("Distribucion de Return% por estrategia")
        plt.tight_layout()
        path = charts_path / "distribucion_returnpct_por_estrategia.png"
        plt.savefig(path, dpi=160)
        plt.close()
        written["distribucion_returnpct_por_estrategia"] = path

        plt.figure(figsize=(12, 7))
        all_values = [values for values in data if len(values)]
        if all_values:
            bins = np.linspace(
                min(np.min(values) for values in all_values),
                max(np.max(values) for values in all_values),
                14,
            )
            for strategy, values in zip(strategies, data):
                plt.hist(
                    values,
                    bins=bins,
                    density=True,
                    histtype="step",
                    linewidth=1.8,
                    alpha=0.95,
                    label=strategy,
                )
            plt.axvline(0.0, color="black", linewidth=1, linestyle="--", alpha=0.7)
            plt.xlabel("Return% por bloque")
            plt.ylabel("Densidad aproximada")
            plt.title("Distribucion de Return% por bloque (histograma por estrategia)")
            plt.legend(fontsize=8, loc="best")
            plt.tight_layout()
            path = charts_path / "histograma_densidad_returnpct_por_bloque.png"
            plt.savefig(path, dpi=160)
            plt.close()
            written["histograma_densidad_returnpct_por_bloque"] = path

    if trade_pool_by_asset is not None and not trade_pool_by_asset.empty:
        asset_heat = trade_pool_by_asset.pivot_table(index="symbol", columns="Variante", values="NetProfit", aggfunc="sum", fill_value=0.0)
        if not asset_heat.empty:
            plt.figure(figsize=(max(10, len(asset_heat.columns) * 1.5), max(6, len(asset_heat.index) * 0.28)))
            plt.imshow(asset_heat.values, aspect="auto", cmap="RdYlGn")
            plt.colorbar(label="NetProfit trade-pool")
            plt.xticks(range(len(asset_heat.columns)), asset_heat.columns, rotation=45, ha="right", fontsize=8)
            plt.yticks(range(len(asset_heat.index)), asset_heat.index, fontsize=7)
            plt.title("Pool de trades: NetProfit por activo y estrategia")
            plt.tight_layout()
            path = charts_path / "heatmap_trade_pool_netprofit_activo_estrategia.png"
            plt.savefig(path, dpi=160)
            plt.close()
            written["heatmap_trade_pool_netprofit_activo_estrategia"] = path
    return written


def _table_or_message(df, columns=None, message="Sin datos."):
    if df is None or df.empty:
        return message
    frame = df.copy()
    if columns is not None:
        frame = frame[[column for column in columns if column in frame.columns]]
    return frame.to_string(index=False)


def _write_report(
    output_path,
    block_metrics,
    aggregate_global,
    aggregate_by_group,
    aggregate_by_tf_pair,
    trade_pool_global,
    trade_pool_by_group,
    trade_pool_by_asset,
    charts,
    sp500_context=None,
    source_note="",
):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if block_metrics is None or block_metrics.empty:
        body = "\n".join([
            "# Informe benchmarks ENBOLSA",
            "",
            "## Estado",
            "SIN DATOS.",
            "",
            "No se generaron resultados reales. Revisa conexion MySQL, universo, cache y dependencias del entorno.",
        ])
        output.write_text(body, encoding="utf-8")
        return output

    h4d1_blocks = block_metrics[block_metrics["TFPair"] == "H4:D1"]
    h4d1_status = (
        "Incluido como variante degradada 2TF (`H4,D1`) para los bloques: "
        + ", ".join(sorted(h4d1_blocks["BlockId"].unique()))
        if not h4d1_blocks.empty
        else "No incluido en esta salida."
    )
    chart_lines = "\n".join(f"- `{name}`: `{path}`" for name, path in charts.items()) or "Sin graficos."
    sp500_text = (
        _table_or_message(sp500_context, message="Sin contexto `sp500_buy_hold` disponible en esta salida.")
        if sp500_context is not None else "Sin contexto `sp500_buy_hold` disponible en esta salida."
    )

    global_cols = [
        "Variante", "Family", "Blocks", "TotalTrades", "TotalNetProfit",
        "MeanReturn%", "MedianReturn%", "MinReturn%", "MaxReturn%",
        "PositiveBlockRate%", "MedianPF", "MedianMaxDD%", "MedianSharpe",
        "MedianAvgR",
    ]
    group_cols = [
        "Variante", "Group", "Blocks", "TotalTrades", "TotalNetProfit",
        "MeanReturn%", "MedianReturn%", "PositiveBlockRate%", "MedianPF",
        "MedianMaxDD%",
    ]
    tf_cols = [
        "Variante", "TFPair", "Blocks", "TotalTrades", "TotalNetProfit",
        "MeanReturn%", "MedianReturn%", "PositiveBlockRate%", "MedianPF",
    ]
    block_cols = [
        "Variante", "Group", "TFPair", "BlockId", "Trades", "Return%",
        "PF", "MaxDD%", "Sharpe", "Sortino", "NetProfit", "AvgR",
        "TFStackEffective", "H4D1Mode",
    ]
    pool_cols = [
        "Variante", "Family", "Trades", "WR%", "PF", "NetProfit",
        "Expectancy", "AvgR", "ExpectancyR",
    ]
    asset_cols = [
        "Variante", "symbol", "Trades", "WR%", "PF", "NetProfit",
        "Expectancy", "AvgR", "ExpectancyR",
    ]

    body = "\n".join([
        "# Informe final canonico - benchmarks ENBOLSA",
        "",
        "## Objetivo",
        "Comparar `enbolsa:fib_limit` y `enbolsa:macd_breakout` frente a cuatro benchmarks clasicos bajo el mismo universo operativo ENBOLSA, sin mezclar bloques independientes como si fueran una unica cuenta.",
        "",
        "## Universo y comparabilidad",
        "Cada bloque `group x tf_pair` se simula de forma independiente con `initial_capital=10000`. Por ese motivo, las metricas de cartera (`Return%`, `Sharpe`, `Sortino`, `MaxDD%`, `Calmar`, `Exposure%`, `ReturnOverDrawdown`) son canonicas solo dentro de cada bloque.",
        "",
        "La salida global agrega distribuciones entre bloques: media, mediana, extremos, tasa de bloques positivos y sumas de trades/NetProfit de cuentas independientes. No representa una curva de equity global.",
        "",
        "## Estrategias comparadas",
        "- Principal ENBOLSA: `enbolsa:fib_limit`, `enbolsa:macd_breakout`.",
        "- Benchmarks principales: `benchmark:rsi_3tf_mean_reversion`, `benchmark:rsi_3tf_momentum_reentry`, `benchmark:ma_cross_3tf_trend`, `benchmark:bb_3tf_pullback_reentry`.",
        "- `combined_split` no forma parte de esta tabla principal salvo que se ejecute expresamente como referencia secundaria.",
        "- `sp500_buy_hold` se mantiene solo como contexto separado de indices.",
        "",
        "## Semantica de outputs",
        "- `block_metrics.csv`: tabla canonica por `strategy x group x tf_pair`; aqui si son validas las metricas de cartera.",
        "- `aggregate_by_strategy.csv`, `aggregate_by_group.csv`, `aggregate_by_tf_pair.csv`: agregaciones entre bloques independientes; resumen distribucional, no pseudo-cartera.",
        "- `trade_pool_*.csv`: pool de trades para frecuencia, PF, NetProfit, expectancy y R; no contiene Sharpe, Sortino, MaxDD ni curvas de capital.",
        "- Los graficos finales evitan equity/drawdown global y usan heatmaps, barras y distribuciones por bloque.",
        "",
        "## Estado de H4:D1",
        h4d1_status,
        "",
        "`H4:D1` no se presenta como stack 3TF normal: al no existir `W1` real en esta infraestructura, se etiqueta como `degraded_2tf_h4_d1` y su `TFStackEffective` esperado es `H4,D1` para los benchmarks.",
        "",
        "## Resultados globales agregados entre bloques",
        "```",
        _table_or_message(aggregate_global, global_cols),
        "```",
        "",
        "## Metricas canonicas completas por bloque",
        "```",
        _table_or_message(block_metrics.sort_values(["Group", "TFPair", "Variante"]), block_cols),
        "```",
        "",
        "## Resultados por grupo",
        "```",
        _table_or_message(aggregate_by_group.sort_values(["Group", "Variante"]), group_cols),
        "```",
        "",
        "## Resultados por pareja temporal",
        "```",
        _table_or_message(aggregate_by_tf_pair.sort_values(["TFPair", "Variante"]), tf_cols),
        "```",
        "",
        "## Pool de trades global",
        "Estas metricas resumen el conjunto de operaciones y no son metricas de cartera.",
        "",
        "```",
        _table_or_message(trade_pool_global, pool_cols),
        "```",
        "",
        "## Pool de trades por grupo",
        "```",
        _table_or_message(trade_pool_by_group.sort_values(["Group", "Variante"]), ["Variante", "Group", *pool_cols[2:]]),
        "```",
        "",
        "## Pool de trades por activo",
        "Tabla completa exportada en `tables/trade_pool_by_asset.csv`; se incluye completa aqui para trazabilidad del TFG.",
        "",
        "```",
        _table_or_message(trade_pool_by_asset.sort_values(["symbol", "Variante"]), asset_cols),
        "```",
        "",
        "## Contexto sp500_buy_hold",
        "```",
        sp500_text,
        "```",
        "",
        "## Graficos validos",
        chart_lines,
        "",
        "## Limitaciones",
        "- No se modela swap.",
        "- Los benchmarks son referencias clasicas simples, no estrategias optimizadas.",
        "- ENBOLSA `fib_limit` y `macd_breakout` pueden registrar varias patas por posicion; por eso las metricas de trade-pool no son equivalentes perfectos a posiciones completas.",
        "- `TotalNetProfit` suma resultados de bloques independientes; no debe leerse como saldo final de una cuenta unica.",
        "- `sp500_buy_hold` es contextual y no se mezcla con la matriz operativa.",
        "",
        "## Conclusion",
        "La comparacion defendible debe basarse primero en `block_metrics.csv` y despues en las agregaciones entre bloques. Cualquier lectura de equity global consolidada anterior queda sustituida por este informe.",
        "",
        "## Procedencia",
        source_note or "Salida generada desde los parciales reales disponibles.",
    ])
    output.write_text(body, encoding="utf-8")
    return output


def _write_legacy_alias_report(output_path, canonical_report):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join([
        "# Informe benchmarks ENBOLSA - NO CANONICO",
        "",
        "Este archivo queda conservado solo como artefacto parcial o historico.",
        "",
        f"Informe final canonico: `{canonical_report}`.",
        "",
        "No usar este fichero para conclusiones del TFG si contradice el informe final.",
    ])
    output.write_text(body, encoding="utf-8")
    return output


def _write_no_data_report(output_path, reason):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join([
        "# Informe benchmarks ENBOLSA",
        "",
        "## Estado",
        "SIN DATOS.",
        "",
        "No se generaron tablas ni graficos reales de la matriz completa. No se inventan resultados.",
        "",
        "## Motivo",
        str(reason),
        "",
        "## Conclusion provisional",
        "Sin datos reales no hay mejor/peor Return%, PF ni dispersion por grupo que reportar.",
    ])
    output.write_text(body, encoding="utf-8")
    return output


def _sp500_buy_hold_context(portfolios):
    rows = []
    aliases = ("US500", "SP500", "SPX500", "S&P500")
    for (group_name, timeframe_ltf, timeframe_htf), portfolio in (portfolios or {}).items():
        if str(group_name).lower() != "index":
            continue
        for symbol, df in (portfolio or {}).items():
            clean = str(symbol).upper().replace(".", "")
            if not any(alias in clean for alias in aliases):
                continue
            if df is None or df.empty or "close" not in df.columns:
                continue
            prices = pd.to_numeric(df["close"], errors="coerce").dropna()
            if prices.empty:
                continue
            start_price = float(prices.iloc[0])
            end_price = float(prices.iloc[-1])
            rows.append({
                "Benchmark": "sp500_buy_hold",
                "Group": group_name,
                "Activo": symbol,
                "LTF": timeframe_ltf,
                "HTF": timeframe_htf,
                "Inicio": prices.index[0],
                "Fin": prices.index[-1],
                "StartClose": start_price,
                "EndClose": end_price,
                "Return%": round(((end_price / start_price) - 1.0) * 100.0, 2) if start_price > 0 else 0.0,
                "Nota": "Contextual; no mezclado en tabla principal operativa",
            })
    return pd.DataFrame(rows)


def run(args):
    output_root = Path(args.output_root)
    tables_dir = output_root / "tables"
    charts_dir = output_root / "charts"
    reports_dir = output_root / "reports"
    account_config = get_account_config()
    groups = args.groups or list(DEFAULT_ASSET_GROUPS)
    tf_pairs = _parse_tf_pairs(args.tf_pairs)

    try:
        from backtests.enbolsa.backtest_loader import cargar_portfolio_multiactivo
        from backtests.enbolsa.backtest_pipeline import ejecutar_comparativa
        from data.sql.sql_funcs import get_symbols_by_group_normalized
    except ModuleNotFoundError as exc:
        report = _write_no_data_report(
            reports_dir / "BENCHMARKS_ENBOLSA_REPORT.md",
            f"Entorno incompleto: falta el modulo `{exc.name}` en el interprete de ejecucion.",
        )
        print(f"Informe sin datos: {report}")
        return {
            "summary": pd.DataFrame(),
            "by_group": pd.DataFrame(),
            "by_asset": pd.DataFrame(),
            "trade_log": pd.DataFrame(),
            "tables": {},
            "charts": {},
            "report": report,
        }

    all_trade_frames = []
    sp500_context_frames = []
    selected_groups = get_selected_groups(groups)
    groups_map = get_symbols_by_group_normalized(selected_groups)
    for group_name, symbols in groups_map.items():
        if not symbols:
            continue
        for timeframe_ltf, timeframe_htf in get_timeframe_pairs(tf_pairs).items():
            portfolio = cargar_portfolio_multiactivo(
                symbols,
                timeframe_ltf=timeframe_ltf,
                timeframe_htf=timeframe_htf,
                group_name=group_name,
                verbose=not args.quiet,
                use_cache=not args.no_cache,
                force_rebuild=args.force_rebuild,
                use_disk_cache=not args.no_disk_cache,
            )
            if not portfolio:
                continue

            enbolsa_main = ejecutar_comparativa(
                portfolio,
                estrategias=_enbolsa_strategy_set(
                    MAIN_ENBOLSA_STRATEGIES,
                    swing_quality_gate_enabled=args.enbolsa_swing_quality_gate,
                ),
                timeframe_ltf=timeframe_ltf,
                timeframe_htf=timeframe_htf,
                account_config=account_config,
                return_details=True,
            )
            all_trade_frames.append(_normalize_result_trades(enbolsa_main, "enbolsa", group_name, timeframe_ltf, timeframe_htf))

            if args.include_combined_split:
                enbolsa_secondary = ejecutar_comparativa(
                    portfolio,
                    estrategias=_enbolsa_strategy_set(
                        SECONDARY_ENBOLSA_STRATEGIES,
                        swing_quality_gate_enabled=args.enbolsa_swing_quality_gate,
                    ),
                    timeframe_ltf=timeframe_ltf,
                    timeframe_htf=timeframe_htf,
                    account_config=account_config,
                    return_details=True,
                )
                all_trade_frames.append(_normalize_result_trades(enbolsa_secondary, "enbolsa_secondary", group_name, timeframe_ltf, timeframe_htf))

            benchmarks = ejecutar_classic_benchmarks_3tf(
                portfolio,
                timeframe_ltf=timeframe_ltf,
                timeframe_htf=timeframe_htf,
                strategies=CLASSIC_BENCHMARK_STRATEGIES,
                account_config=account_config,
                group_name=group_name,
                return_details=True,
            )
            all_trade_frames.append(_normalize_result_trades(benchmarks, "benchmark", group_name, timeframe_ltf, timeframe_htf))
            sp500_frame = _sp500_buy_hold_context({(group_name, timeframe_ltf, timeframe_htf): portfolio})
            if not sp500_frame.empty:
                sp500_context_frames.append(sp500_frame)

    trade_log = pd.concat([f for f in all_trade_frames if f is not None and not f.empty], ignore_index=True) if any(f is not None and not f.empty for f in all_trade_frames) else pd.DataFrame()
    block_metrics = _block_metrics_from_trade_log(trade_log, initial_capital=account_config["initial_capital"])
    block_period_metrics = _block_period_metrics_from_trade_log(trade_log, initial_capital=account_config["initial_capital"])
    aggregate_by_strategy = _aggregate_block_metrics(block_metrics)
    aggregate_by_group = _aggregate_block_metrics(block_metrics, dimensions=("Group",))
    aggregate_by_tf_pair = _aggregate_block_metrics(block_metrics, dimensions=("TFPair",))
    trade_pool_global = _trade_pool_by_dimension(trade_log)
    trade_pool_by_group = _trade_pool_by_dimension(trade_log, dimensions=("Group",))
    trade_pool_by_asset = _trade_pool_by_dimension(trade_log, dimensions=("symbol",))
    sp500_context = pd.concat(sp500_context_frames, ignore_index=True) if sp500_context_frames else pd.DataFrame()

    written_tables = write_tables({
        "block_metrics": block_metrics,
        "aggregate_by_strategy": aggregate_by_strategy,
        "aggregate_by_group": aggregate_by_group,
        "aggregate_by_tf_pair": aggregate_by_tf_pair,
        "block_period_metrics": block_period_metrics,
        "trade_pool_global": trade_pool_global,
        "trade_pool_by_group": trade_pool_by_group,
        "trade_pool_by_asset": trade_pool_by_asset,
        "trade_log": trade_log,
        "sp500_buy_hold_context": sp500_context,
    }, tables_dir)
    charts = _write_charts(
        block_metrics,
        block_period_metrics,
        aggregate_by_strategy,
        aggregate_by_group,
        trade_log,
        trade_pool_by_asset,
        charts_dir,
        initial_capital=account_config["initial_capital"],
    )
    report = _write_report(
        reports_dir / "BENCHMARKS_ENBOLSA_REPORT.md",
        block_metrics,
        aggregate_by_strategy,
        aggregate_by_group,
        aggregate_by_tf_pair,
        trade_pool_global,
        trade_pool_by_group,
        trade_pool_by_asset,
        charts,
        sp500_context=sp500_context,
        source_note="Salida generada directamente por el runner; si contiene varios bloques, las agregaciones son entre bloques independientes.",
    )

    print("Tablas:")
    for name, path in written_tables.items():
        print(f"- {name}: {path}")
    print("Graficos:")
    for name, path in charts.items():
        print(f"- {name}: {path}")
    print(f"Informe: {report}")
    return {
        "block_metrics": block_metrics,
        "aggregate_by_strategy": aggregate_by_strategy,
        "aggregate_by_group": aggregate_by_group,
        "aggregate_by_tf_pair": aggregate_by_tf_pair,
        "trade_pool_global": trade_pool_global,
        "trade_pool_by_group": trade_pool_by_group,
        "trade_pool_by_asset": trade_pool_by_asset,
        "trade_log": trade_log,
        "tables": written_tables,
        "charts": charts,
        "report": report,
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Comparativa reproducible ENBOLSA vs benchmarks clasicos 3TF.")
    parser.add_argument("--groups", nargs="*", default=None)
    parser.add_argument("--tf-pairs", nargs="*", default=None, help="Pares tipo M30:H1 H1:H4 H4:D1")
    parser.add_argument("--output-root", default="artifacts/benchmark-significance/enbolsa/manual-run")
    parser.add_argument("--include-combined-split", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--no-disk-cache", action="store_true")
    parser.add_argument(
        "--enbolsa-swing-quality-gate",
        action="store_true",
        help="Activa el gate metodologico enbolsa_swing_quality_v1 solo para estrategias ENBOLSA.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
