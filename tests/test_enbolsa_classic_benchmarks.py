import importlib.util
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "backtests"
    / "benchmarks"
    / "enbolsa_classic_benchmarks.py"
)
spec = importlib.util.spec_from_file_location("enbolsa_classic_benchmarks_shadow", MODULE_PATH)
benchmarks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmarks)
sys.modules["enbolsa_classic_benchmarks"] = benchmarks


RUNNER_PATH = (
    Path(__file__).resolve().parents[1]
    / "backtests"
    / "benchmarks"
    / "run_enbolsa_benchmark_comparison.py"
)
MERGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "backtests"
    / "benchmarks"
    / "merge_partials.py"
)


def _load_runner_module():
    loader_stub = types.ModuleType("backtests.enbolsa.backtest_loader")
    loader_stub.cargar_portfolios_matriz = lambda *args, **kwargs: {}
    pipeline_stub = types.ModuleType("backtests.enbolsa.backtest_pipeline")
    pipeline_stub.ejecutar_comparativa = lambda *args, **kwargs: {"trades": {}}
    sys.modules.setdefault("backtests.enbolsa.backtest_loader", loader_stub)
    sys.modules.setdefault("backtests.enbolsa.backtest_pipeline", pipeline_stub)
    if str(RUNNER_PATH.parent) not in sys.path:
        sys.path.insert(0, str(RUNNER_PATH.parent))
    runner_spec = importlib.util.spec_from_file_location("run_enbolsa_benchmark_comparison_shadow", RUNNER_PATH)
    runner = importlib.util.module_from_spec(runner_spec)
    runner_spec.loader.exec_module(runner)
    return runner


def _load_merge_module():
    if str(MERGE_PATH.parent) not in sys.path:
        sys.path.insert(0, str(MERGE_PATH.parent))
    merge_spec = importlib.util.spec_from_file_location("merge_partials_shadow", MERGE_PATH)
    merge = importlib.util.module_from_spec(merge_spec)
    merge_spec.loader.exec_module(merge)
    return merge


def _trend_frame(index, start=1.0, step=0.001):
    close = start + np.arange(len(index)) * step
    frame = pd.DataFrame(index=index)
    frame["open"] = close - 0.0005
    frame["high"] = close + 0.001
    frame["low"] = close - 0.001
    frame["close"] = close
    frame["spread_price"] = 0.0001
    return frame


def _signal_frame():
    index = pd.date_range("2025-01-01", periods=10, freq="30min")
    close = np.array([1.1000, 1.1002, 1.1004, 1.1006, 1.1008, 1.1010, 1.1012, 1.1014, 1.1016, 1.1018])
    frame = pd.DataFrame(index=index)
    frame["open"] = close
    frame["high"] = close + 0.0008
    frame["low"] = close - 0.0008
    frame["close"] = close
    frame["spread_price"] = 0.0001
    frame["ATR_14"] = 0.0005
    frame["RSI_14"] = [45, 39, 48, 51, 52, 55, 58, 61, 63, 65]
    frame["SMA20"] = close
    frame["SMA50"] = close - 0.0001
    frame["SMA200"] = close - 0.001
    frame["BB_LOWER_20_2"] = close - 0.002
    frame["BB_UPPER_20_2"] = close + 0.002
    frame["ALIGN_3TF_BULLISH"] = True
    frame["ALIGN_3TF_BEARISH"] = False
    frame.loc[index[5], "high"] = 1.1030
    return frame


def _base_indicator_frame(periods=8, freq="30min", close_start=100.0):
    index = pd.date_range("2025-01-01", periods=periods, freq=freq)
    close = close_start + np.arange(periods) * 0.2
    frame = pd.DataFrame(index=index)
    frame["open"] = close
    frame["high"] = close + 0.4
    frame["low"] = close - 0.4
    frame["close"] = close
    frame["spread_price"] = 0.0
    frame["ATR_14"] = 1.0
    frame["RSI_14"] = 50.0
    frame["SMA20"] = close
    frame["SMA50"] = close
    frame["SMA200"] = close - 10.0
    frame["BB_LOWER_20_2"] = close - 2.0
    frame["BB_UPPER_20_2"] = close + 2.0
    frame["ALIGN_3TF_BULLISH"] = True
    frame["ALIGN_3TF_BEARISH"] = False
    return frame


class TestEnbolsaClassicBenchmarksShadow(unittest.TestCase):
    def test_rsi_handles_extreme_and_flat_series(self):
        up = pd.Series(range(1, 40), dtype=float)
        down = pd.Series(range(40, 1, -1), dtype=float)
        flat = pd.Series([10.0] * 40)

        self.assertAlmostEqual(float(benchmarks._rsi(up, 14).iloc[-1]), 100.0, places=6)
        self.assertAlmostEqual(float(benchmarks._rsi(down, 14).iloc[-1]), 0.0, places=6)
        self.assertAlmostEqual(float(benchmarks._rsi(flat, 14).iloc[-1]), 50.0, places=6)

    def test_prepare_3tf_alignment_adds_flags_without_enbolsa_structure(self):
        m30 = _trend_frame(pd.date_range("2025-01-01", periods=260, freq="30min"))
        h1 = _trend_frame(pd.date_range("2024-12-20", periods=260, freq="1h"))
        h4 = _trend_frame(pd.date_range("2024-11-20", periods=260, freq="4h"))
        prepared = benchmarks.prepare_3tf_benchmark_portfolio(
            {"EURUSD.r": m30},
            timeframe_ltf="M30",
            timeframe_htf="H1",
            raw_tf_map={
                "M30": {"EURUSD.r": m30},
                "H1": {"EURUSD.r": h1},
                "H4": {"EURUSD.r": h4},
            },
        )
        frame = prepared["EURUSD.r"]
        self.assertIn("ALIGN_3TF_BULLISH", frame.columns)
        self.assertIn("M30_BULLISH", frame.columns)
        self.assertNotIn("LONG_W1_START_PRICE", frame.columns)

    def test_rsi_momentum_reentry_opens_and_closes_fixed_rr_trade(self):
        trades = benchmarks._simulate_symbol(
            "EURUSD.r",
            _signal_frame(),
            "rsi_3tf_momentum_reentry",
            benchmarks.CLASSIC_BENCHMARK_STRATEGIES["rsi_3tf_momentum_reentry"],
        )
        self.assertGreaterEqual(len(trades), 1)
        self.assertEqual(trades[0]["direction"], 1)
        self.assertIn(trades[0]["exit_reason"], {"TP", "EOD"})

    def test_rsi_momentum_reentry_invalidates_armed_state_when_trend_breaks(self):
        frame = _base_indicator_frame(periods=8)
        frame["RSI_14"] = [35.0, 38.0, 45.0, 48.0, 49.0, 51.0, 52.0, 53.0]
        frame["ALIGN_3TF_BULLISH"] = [True, True, False, False, False, True, True, True]
        frame["ALIGN_3TF_BEARISH"] = [False, False, True, True, True, False, False, False]
        trades = benchmarks._simulate_symbol(
            "EURUSD.r",
            frame,
            "rsi_3tf_momentum_reentry",
            benchmarks.CLASSIC_BENCHMARK_STRATEGIES["rsi_3tf_momentum_reentry"],
        )
        self.assertEqual(trades, [])

    def test_rsi_mean_reversion_bearish_closes_on_rsi_exit(self):
        frame = _base_indicator_frame(periods=6)
        frame["ALIGN_3TF_BULLISH"] = False
        frame["ALIGN_3TF_BEARISH"] = True
        frame["RSI_14"] = [55.0, 75.0, 65.0, 25.0, 35.0, 45.0]
        frame["high"] = frame["close"] + 0.2
        frame["low"] = frame["close"] - 0.2
        trades = benchmarks._simulate_symbol(
            "EURUSD.r",
            frame,
            "rsi_3tf_mean_reversion",
            benchmarks.CLASSIC_BENCHMARK_STRATEGIES["rsi_3tf_mean_reversion"],
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["direction"], -1)
        self.assertEqual(trades[0]["exit_reason"], "RSI_EXIT")

    def test_ma_cross_trend_closes_on_ma_cross_after_1r(self):
        frame = _base_indicator_frame(periods=6)
        frame["SMA20"] = [99.0, 101.0, 102.0, 99.0, 98.0, 97.0]
        frame["SMA50"] = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        frame.iloc[2, frame.columns.get_loc("high")] = frame.iloc[1]["close"] + 2.0
        frame["low"] = frame["close"] - 0.2
        trades = benchmarks._simulate_symbol(
            "EURUSD.r",
            frame,
            "ma_cross_3tf_trend",
            benchmarks.CLASSIC_BENCHMARK_STRATEGIES["ma_cross_3tf_trend"],
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["direction"], 1)
        self.assertEqual(trades[0]["exit_reason"], "MA_CROSS_EXIT")

    def test_bb_pullback_reentry_closes_on_tp(self):
        frame = _base_indicator_frame(periods=7)
        frame["close"] = [100.0, 96.0, 100.0, 100.5, 101.0, 103.5, 103.8]
        frame["open"] = frame["close"]
        frame["high"] = frame["close"] + 0.2
        frame["low"] = frame["close"] - 0.2
        frame["BB_LOWER_20_2"] = 98.0
        frame["BB_UPPER_20_2"] = 102.0
        frame.iloc[4, frame.columns.get_loc("high")] = 104.0
        trades = benchmarks._simulate_symbol(
            "EURUSD.r",
            frame,
            "bb_3tf_pullback_reentry",
            benchmarks.CLASSIC_BENCHMARK_STRATEGIES["bb_3tf_pullback_reentry"],
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["direction"], 1)
        self.assertEqual(trades[0]["exit_reason"], "TP")

    def test_bb_pullback_reentry_invalidates_armed_state_when_trend_breaks(self):
        frame = _base_indicator_frame(periods=8)
        frame["close"] = [100.0, 96.0, 96.5, 97.0, 97.5, 99.0, 100.0, 101.0]
        frame["open"] = frame["close"]
        frame["high"] = frame["close"] + 0.2
        frame["low"] = frame["close"] - 0.2
        frame["BB_LOWER_20_2"] = 98.0
        frame["BB_UPPER_20_2"] = 102.0
        frame["ALIGN_3TF_BULLISH"] = [True, True, False, False, False, True, True, True]
        frame["ALIGN_3TF_BEARISH"] = [False, False, True, True, True, False, False, False]
        trades = benchmarks._simulate_symbol(
            "EURUSD.r",
            frame,
            "bb_3tf_pullback_reentry",
            benchmarks.CLASSIC_BENCHMARK_STRATEGIES["bb_3tf_pullback_reentry"],
        )
        self.assertEqual(trades, [])

    def test_sp500_buy_hold_context_filters_index_aliases_only(self):
        runner = _load_runner_module()
        index = pd.date_range("2025-01-01", periods=2, freq="1D")
        us500 = pd.DataFrame({"close": [100.0, 110.0]}, index=index)
        spx = pd.DataFrame({"close": [200.0, 210.0]}, index=index)
        dax = pd.DataFrame({"close": [50.0, 70.0]}, index=index)
        context = runner._sp500_buy_hold_context({
            ("Index", "H1", "H4"): {
                "US500.cash": us500,
                "SPX500": spx,
                "DE40": dax,
            },
            ("Forex Majors", "H1", "H4"): {
                "US500_FX_TEST": us500,
            },
        })
        self.assertEqual(set(context["Activo"]), {"US500.cash", "SPX500"})
        self.assertTrue((context["Group"] == "Index").all())
        self.assertTrue((context["Benchmark"] == "sp500_buy_hold").all())

    def test_resolve_tf_stack_defaults(self):
        self.assertEqual(benchmarks.resolve_tf_stack("M30", "H1"), ("M30", "H1", "H4"))
        self.assertEqual(benchmarks.resolve_tf_stack("H1", "H4"), ("H1", "H4", "D1"))
        self.assertEqual(benchmarks.resolve_tf_stack("H4", "D1"), ("H4", "D1"))
        self.assertEqual(benchmarks.resolve_tf_stack("M15", "M30"), ("M15", "M30"))

    def test_runner_default_output_root_is_noncanonical_manual_run(self):
        runner = _load_runner_module()
        args = runner.build_parser().parse_args([])
        self.assertEqual(args.output_root, "artifacts/benchmark-significance/enbolsa/manual-run")

    def test_runner_exposes_swing_quality_gate_flag(self):
        runner = _load_runner_module()
        args = runner.build_parser().parse_args(["--enbolsa-swing-quality-gate"])
        self.assertTrue(args.enbolsa_swing_quality_gate)

    def test_write_charts_adds_trade_evolution_and_histogram_outputs(self):
        runner = _load_runner_module()
        block_metrics = pd.DataFrame([
            {"Variante": "enbolsa:macd_breakout", "BlockId": "forex-majors-h1-h4", "Group": "Forex Majors", "Return%": 20.0},
            {"Variante": "enbolsa:fib_limit", "BlockId": "forex-majors-h1-h4", "Group": "Forex Majors", "Return%": -10.0},
            {"Variante": "benchmark:ma_cross_3tf_trend", "BlockId": "metals-h1-h4", "Group": "Metals", "Return%": 12.0},
        ])
        block_period_metrics = pd.DataFrame([
            {"Periodo": "2019-2021", "Variante": "enbolsa:macd_breakout", "Return%": 15.0},
            {"Periodo": "2022-2024", "Variante": "enbolsa:macd_breakout", "Return%": 25.0},
            {"Periodo": "2019-2021", "Variante": "enbolsa:fib_limit", "Return%": -5.0},
            {"Periodo": "2022-2024", "Variante": "enbolsa:fib_limit", "Return%": 5.0},
        ])
        aggregate_global = pd.DataFrame([
            {"Variante": "enbolsa:macd_breakout", "MeanReturn%": 20.0, "MedianReturn%": 18.0, "MedianPF": 1.1},
            {"Variante": "enbolsa:fib_limit", "MeanReturn%": -10.0, "MedianReturn%": -8.0, "MedianPF": 0.95},
        ])
        aggregate_by_group = pd.DataFrame([
            {"Variante": "enbolsa:macd_breakout", "Group": "Forex Majors", "MeanReturn%": 20.0},
            {"Variante": "enbolsa:fib_limit", "Group": "Forex Majors", "MeanReturn%": -10.0},
        ])
        trade_pool_by_asset = pd.DataFrame([
            {"symbol": "EURUSD.r", "Variante": "enbolsa:macd_breakout", "NetProfit": 1000.0},
            {"symbol": "EURUSD.r", "Variante": "enbolsa:fib_limit", "NetProfit": -200.0},
        ])
        trade_log = pd.DataFrame([
            {"strategy": "enbolsa:macd_breakout", "exit_time": "2025-01-02", "pnl_money": 100.0, "risk_amount": 50.0},
            {"strategy": "enbolsa:macd_breakout", "exit_time": "2025-01-03", "pnl_money": -25.0, "risk_amount": 50.0},
            {"strategy": "enbolsa:fib_limit", "exit_time": "2025-01-02", "pnl_money": -50.0, "risk_amount": 50.0},
            {"strategy": "enbolsa:fib_limit", "exit_time": "2025-01-04", "pnl_money": 25.0, "risk_amount": 50.0},
        ])

        with TemporaryDirectory() as tmpdir:
            charts = runner._write_charts(
                block_metrics,
                block_period_metrics,
                aggregate_global,
                aggregate_by_group,
                trade_log,
                trade_pool_by_asset,
                tmpdir,
            )

            self.assertIn("lineas_r_acumulada_por_trade", charts)
            self.assertIn("histograma_densidad_returnpct_por_bloque", charts)
            self.assertTrue(Path(charts["lineas_r_acumulada_por_trade"]).is_file())
            self.assertTrue(Path(charts["histograma_densidad_returnpct_por_bloque"]).is_file())

    def test_prepare_h4_d1_uses_two_tf_without_lower_h1(self):
        h4 = _trend_frame(pd.date_range("2025-01-01", periods=260, freq="4h"))
        d1 = _trend_frame(pd.date_range("2024-05-01", periods=260, freq="1D"))
        prepared = benchmarks.prepare_3tf_benchmark_portfolio(
            {"EURUSD.r": h4},
            timeframe_ltf="H4",
            timeframe_htf="D1",
            raw_tf_map={
                "H4": {"EURUSD.r": h4},
                "D1": {"EURUSD.r": d1},
            },
        )
        frame = prepared["EURUSD.r"]
        self.assertEqual(frame.attrs["tf_stack_effective"], ("H4", "D1"))
        self.assertIn("H4_BULLISH", frame.columns)
        self.assertIn("D1_BULLISH", frame.columns)
        self.assertNotIn("H1_BULLISH", frame.columns)

    def test_block_aggregation_does_not_build_pseudo_portfolio(self):
        runner = _load_runner_module()
        base_columns = [
            "strategy", "source_family", "Group", "symbol", "timeframe_ltf", "timeframe_htf",
            "entry_time", "exit_time", "pnl_money", "weighted_return", "risk_amount",
            "balance_before_entry",
        ]
        trades = pd.DataFrame([
            ["enbolsa:fib_limit", "enbolsa", "Forex Majors", "EURUSD.r", "M30", "H1", "2025-01-01", "2025-01-02", 100.0, 0.010, 50.0, 10000.0],
            ["enbolsa:fib_limit", "enbolsa", "Metals", "XAUUSD.r", "H1", "H4", "2025-02-01", "2025-02-02", -20.0, -0.002, 50.0, 10000.0],
            ["benchmark:ma_cross_3tf_trend", "benchmark", "Forex Majors", "EURUSD.r", "M30", "H1", "2025-01-03", "2025-01-04", -40.0, -0.004, 40.0, 10000.0],
        ], columns=base_columns)

        block_metrics = runner._block_metrics_from_trade_log(trades, initial_capital=10000.0)
        aggregate = runner._aggregate_block_metrics(block_metrics)
        pool = runner._trade_pool_by_dimension(trades)

        fib_row = aggregate.set_index("Variante").loc["enbolsa:fib_limit"]
        self.assertEqual(int(fib_row["Blocks"]), 2)
        self.assertEqual(float(fib_row["TotalNetProfit"]), 80.0)
        self.assertEqual(float(fib_row["MeanReturn%"]), 0.4)
        self.assertNotEqual(float(fib_row["MeanReturn%"]), 0.8)
        self.assertNotIn("Sharpe", pool.columns)
        self.assertNotIn("MaxDD%", pool.columns)

    def test_merge_partials_returns_block_outputs_without_writing_test_artifacts(self):
        merge = _load_merge_module()
        base_columns = [
            "strategy", "source_family", "Group", "symbol", "timeframe_ltf", "timeframe_htf",
            "entry_time", "exit_time", "pnl_money", "weighted_return", "risk_amount",
            "balance_before_entry",
        ]
        synthetic = pd.DataFrame([
            ["enbolsa:fib_limit", "enbolsa", "Forex Majors", "EURUSD.r", "M30", "H1", "2025-01-01", "2025-01-02", 120.0, 0.012, 60.0, 10000.0],
            ["benchmark:ma_cross_3tf_trend", "benchmark", "Metals", "XAUUSD.r", "H1", "H4", "2025-01-03", "2025-01-04", -40.0, -0.004, 40.0, 10000.0],
            ["enbolsa:fib_limit", "enbolsa", "Metals", "XAUUSD.r", "H1", "H4", "2025-02-01", "2025-02-02", -20.0, -0.002, 50.0, 10000.0],
        ], columns=base_columns)

        merge._expand_trade_log_paths = lambda patterns: [Path("partial-a/tables/trade_log.csv")]
        merge._read_trade_logs = lambda paths: synthetic.copy()
        merge._read_sp500_context = lambda paths: pd.DataFrame()
        merge.write_tables = lambda tables, output_dir: {name: Path(output_dir) / f"{name}.csv" for name in tables}
        merge._write_charts = lambda *args, **kwargs: {"heatmap_returnpct_por_bloque": Path("chart.png")}
        merge._write_report = lambda output_path, *args, **kwargs: Path(output_path)
        merge._sanitize_related_reports = lambda artifacts_root, canonical_report: pd.DataFrame([{
            "report_path": str(canonical_report),
            "status": "canonical",
            "action": "kept",
            "canonical_report": str(canonical_report),
        }])

        result = merge.merge_partials(["ignored"], Path("unused-output"), initial_capital=10000.0)

        self.assertEqual(len(result["trade_log"]), 3)
        self.assertIn("block_metrics", result)
        self.assertIn("aggregate_by_strategy", result)
        self.assertIn("trade_pool_by_asset", result)
        fib_row = result["aggregate_by_strategy"].set_index("Variante").loc["enbolsa:fib_limit"]
        self.assertEqual(int(fib_row["Blocks"]), 2)
        self.assertEqual(float(fib_row["MeanReturn%"]), 0.5)
        self.assertIn("block_metrics", result["tables"])
        self.assertIn("trade_pool_by_asset", result["tables"])
        self.assertIn("report_audit", result["tables"])
        self.assertNotIn("equity_comparada", result["charts"])


if __name__ == "__main__":
    unittest.main()
