from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BENCHMARKS_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS_DIR))

from backtests.common.backtest_matrix_config import get_account_config
from run_enbolsa_benchmark_comparison import _write_charts


def refresh_final_charts(final_root: str | Path = "artifacts/benchmark-significance/enbolsa/final"):
    root = Path(final_root)
    tables = root / "tables"
    charts = root / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    block_metrics = pd.read_csv(tables / "block_metrics.csv", low_memory=False)
    block_period_metrics = pd.read_csv(tables / "block_period_metrics.csv", low_memory=False)
    aggregate_by_strategy = pd.read_csv(tables / "aggregate_by_strategy.csv", low_memory=False)
    aggregate_by_group = pd.read_csv(tables / "aggregate_by_group.csv", low_memory=False)
    trade_pool_by_asset = pd.read_csv(tables / "trade_pool_by_asset.csv", low_memory=False)
    trade_log = pd.read_csv(tables / "trade_log.csv", low_memory=False)

    for column in ("entry_time", "exit_time"):
        if column in trade_log.columns:
            trade_log[column] = pd.to_datetime(trade_log[column], errors="coerce")

    stale = charts / "lineas_returnpct_medio_por_periodo.png"
    if stale.exists():
        stale.unlink()

    written = _write_charts(
        block_metrics=block_metrics,
        block_period_metrics=block_period_metrics,
        aggregate_global=aggregate_by_strategy,
        aggregate_by_group=aggregate_by_group,
        trade_log=trade_log,
        trade_pool_by_asset=trade_pool_by_asset,
        charts_dir=charts,
        initial_capital=get_account_config()["initial_capital"],
    )

    print("Graficos actualizados:")
    for name, path in written.items():
        print(f"- {name}: {path}")
    return written


if __name__ == "__main__":
    refresh_final_charts()
