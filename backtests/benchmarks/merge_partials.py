"""Merge completed benchmark partials into the canonical final report set."""

from __future__ import annotations

import argparse
import glob
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

from enbolsa_classic_benchmarks import write_tables
from run_enbolsa_benchmark_comparison import (
    _aggregate_block_metrics,
    _block_metrics_from_trade_log,
    _block_period_metrics_from_trade_log,
    _trade_pool_by_dimension,
    _write_charts,
    _write_legacy_alias_report,
    _write_report,
)


TIME_COLUMNS = ("entry_time", "exit_time")
NUMERIC_COLUMNS = (
    "direction",
    "entry_price",
    "exit_price",
    "stop_price",
    "target_price",
    "tp_mult",
    "size_fraction",
    "spread_price",
    "pnl",
    "pnl_money",
    "weighted_return",
    "risk_amount",
    "balance_before_entry",
    "balance_after_exit",
    "commission",
    "volume",
)


def _expand_trade_log_paths(patterns):
    """Resolve files/directories/globs into unique `trade_log.csv` paths."""
    paths = []
    seen = set()
    for pattern in patterns:
        matches = glob.glob(str(pattern), recursive=True)
        if not matches:
            matches = [str(pattern)]
        for match in matches:
            path = Path(match)
            candidates = []
            if path.is_dir():
                candidates.append(path / "tables" / "trade_log.csv")
            elif path.name == "trade_log.csv":
                candidates.append(path)
            for candidate in candidates:
                if candidate.is_file():
                    resolved = candidate.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        paths.append(candidate)
    return sorted(paths, key=lambda value: str(value))


def _coerce_trade_log(frame):
    """Coerce known trade-log time and numeric columns before aggregation."""
    result = frame.copy()
    for column in TIME_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    if "pnl_money" not in result.columns and "pnl" in result.columns:
        result["pnl_money"] = result["pnl"]
    if "source_family" not in result.columns and "strategy" in result.columns:
        result["source_family"] = result["strategy"].astype(str).str.split(":", n=1).str[0]
    return result


def _read_trade_logs(paths):
    """Read and concatenate partial trade logs."""
    frames = []
    for path in paths:
        try:
            frame = pd.read_csv(path, low_memory=False)
        except pd.errors.EmptyDataError:
            continue
        if frame.empty:
            continue
        frame = _coerce_trade_log(frame)
        frame["partial_source"] = Path(path).parent.parent.name
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _read_sp500_context(paths):
    """Read optional S&P 500 context tables placed next to trade logs."""
    frames = []
    for trade_log_path in paths:
        context_path = Path(trade_log_path).with_name("sp500_buy_hold_context.csv")
        if not context_path.is_file():
            continue
        try:
            frame = pd.read_csv(context_path, low_memory=False)
        except pd.errors.EmptyDataError:
            continue
        if frame.empty:
            continue
        frame["partial_source"] = Path(trade_log_path).parent.parent.name
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _sanitize_related_reports(artifacts_root, canonical_report):
    """Rewrite non-canonical benchmark reports as aliases to the final report."""
    root = Path(artifacts_root)
    canonical = Path(canonical_report).resolve()
    rows = []
    for report_path in sorted(root.rglob("BENCHMARKS_ENBOLSA_REPORT.md")):
        resolved = report_path.resolve()
        if resolved == canonical:
            rows.append({
                "report_path": str(report_path),
                "status": "canonical",
                "action": "kept",
                "canonical_report": str(canonical_report),
            })
            continue
        _write_legacy_alias_report(report_path, canonical_report)
        rows.append({
            "report_path": str(report_path),
            "status": "non_canonical",
            "action": "rewritten_as_alias",
            "canonical_report": str(canonical_report),
        })
    return pd.DataFrame(rows)


def merge_partials(patterns, output_root, initial_capital=None):
    """Merge benchmark partial artifacts without re-simulating strategies."""
    trade_log_paths = _expand_trade_log_paths(patterns)
    if not trade_log_paths:
        raise FileNotFoundError(f"No se encontraron trade_log.csv para: {patterns}")

    output = Path(output_root)
    tables_dir = output / "tables"
    charts_dir = output / "charts"
    reports_dir = output / "reports"
    account_config = get_account_config()
    capital = float(initial_capital if initial_capital is not None else account_config["initial_capital"])

    trade_log = _read_trade_logs(trade_log_paths)
    trade_log.attrs["initial_capital"] = capital
    block_metrics = _block_metrics_from_trade_log(trade_log, initial_capital=capital)
    block_period_metrics = _block_period_metrics_from_trade_log(trade_log, initial_capital=capital)
    aggregate_by_strategy = _aggregate_block_metrics(block_metrics)
    aggregate_by_group = _aggregate_block_metrics(block_metrics, dimensions=("Group",))
    aggregate_by_tf_pair = _aggregate_block_metrics(block_metrics, dimensions=("TFPair",))
    trade_pool_global = _trade_pool_by_dimension(trade_log)
    trade_pool_by_group = _trade_pool_by_dimension(trade_log, dimensions=("Group",))
    trade_pool_by_asset = _trade_pool_by_dimension(trade_log, dimensions=("symbol",))
    sp500_context = _read_sp500_context(trade_log_paths)

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
        initial_capital=capital,
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
        source_note="Consolidado desde parciales sin re-simular. Cada parcial conserva su cuenta independiente.",
    )
    report_audit = _sanitize_related_reports(output.parent, report)
    written_tables.update(write_tables({"report_audit": report_audit}, tables_dir))

    return {
        "trade_log_paths": trade_log_paths,
        "block_metrics": block_metrics,
        "aggregate_by_strategy": aggregate_by_strategy,
        "aggregate_by_group": aggregate_by_group,
        "aggregate_by_tf_pair": aggregate_by_tf_pair,
        "block_period_metrics": block_period_metrics,
        "trade_pool_global": trade_pool_global,
        "trade_pool_by_group": trade_pool_by_group,
        "trade_pool_by_asset": trade_pool_by_asset,
        "trade_log": trade_log,
        "tables": written_tables,
        "charts": charts,
        "report": report,
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Consolida partials de benchmark-significance sin re-simular.")
    parser.add_argument("patterns", nargs="+", help="Directorios partial-* o rutas a tables/trade_log.csv.")
    parser.add_argument(
        "--output-root",
        default="artifacts/benchmark-significance/enbolsa/final",
        help="Directorio destino para tablas, graficos e informe consolidados.",
    )
    parser.add_argument("--initial-capital", type=float, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = merge_partials(args.patterns, args.output_root, initial_capital=args.initial_capital)
    print("Partials:")
    for path in result["trade_log_paths"]:
        print(f"- {path}")
    print("Tablas:")
    for name, path in result["tables"].items():
        print(f"- {name}: {path}")
    print("Graficos:")
    for name, path in result["charts"].items():
        print(f"- {name}: {path}")
    print(f"Informe: {result['report']}")
    return result


if __name__ == "__main__":
    main()
