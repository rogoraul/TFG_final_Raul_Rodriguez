from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtests.enbolsa.backtest_pipeline import _entry_signal, _make_position
from backtests.enbolsa.swing_quality import SwingQualityThresholds, evaluate_swing_quality_values
from trading_center.enbolsa_swing_quality import main


def test_small_w1_blocks_quality_gate() -> None:
    result = evaluate_swing_quality_values(
        w1_size=0.002,
        w1_start=1.2000,
        w1_bars=3,
        atr=0.0015,
        w2_retr_pct=0.45,
        w2_swing=1.2050,
        invalidated=False,
        thresholds=SwingQualityThresholds(w1_min_atr_multiple=2.5, w1_min_price_pct=0.75, w1_min_bars=6),
    )

    assert result["swing_quality_pass"] is False
    assert "w1_below_atr_multiple" in result["swing_quality_reason"]
    assert "w1_below_price_pct" in result["swing_quality_reason"]
    assert "w1_too_few_bars" in result["swing_quality_reason"]


def test_good_w1_w2_passes_quality_gate() -> None:
    result = evaluate_swing_quality_values(
        w1_size=0.018,
        w1_start=1.2000,
        w1_bars=12,
        atr=0.004,
        w2_retr_pct=0.50,
        w2_swing=1.2090,
        invalidated=False,
        thresholds=SwingQualityThresholds(w1_min_atr_multiple=2.5, w1_min_price_pct=0.75, w1_min_bars=6),
    )

    assert result["swing_quality_pass"] is True
    assert result["swing_quality_reason"] == "pass"


def test_fib_limit_quality_gate_blocks_entry_when_enabled() -> None:
    row = pd.Series(
        {
            "TENDENCIA_ESTRUCTURAL_H4": 1,
            "low": 1.101,
            "high": 1.115,
            "spread_price": 0.0,
            "ATR": 0.004,
            "LONG_SETUP_ID": 1,
            "LONG_SETUP_ACTIVE": True,
            "LONG_SETUP_AGE": 2,
            "LONG_W1_START_PRICE": 1.100,
            "LONG_W1_END_PRICE": 1.106,
            "LONG_W1_SIZE": 0.006,
            "LONG_W1_BARS": 2,
            "LONG_W2_RETR_PCT": 0.50,
            "LONG_W2_SWING_PRICE": 1.103,
            "LONG_W2_INVALIDATED": False,
            "LONG_W2_VALID_80": True,
            "LONG_FIB_LEVEL_0.618": 1.102,
        }
    )

    assert _entry_signal(row, 1, "fib_limit", "TENDENCIA_ESTRUCTURAL_H4") is True
    assert _entry_signal(row, 1, "fib_limit", "TENDENCIA_ESTRUCTURAL_H4", swing_quality_gate_enabled=True) is False


def test_macd_breakout_position_still_uses_close_not_fibonacci() -> None:
    row = pd.Series(
        {
            "close": 1.2500,
            "spread_price": 0.0001,
            "ATR": 0.003,
            "LONG_SETUP_ID": 7,
            "LONG_SETUP_ACTIVE": True,
            "LONG_SETUP_AGE": 5,
            "LONG_W1_START_PRICE": 1.2000,
            "LONG_W1_END_PRICE": 1.2300,
            "LONG_W1_SIZE": 0.0300,
            "LONG_W1_BARS": 12,
            "LONG_W2_EXTREME_PRICE": 1.2200,
            "LONG_W2_RETR_PCT": 0.33,
            "LONG_W2_SWING_PRICE": 1.2200,
            "LONG_W2_INVALIDATED": False,
            "LONG_FIB_LEVEL_0.618": 1.2115,
            "LONG_TARGET_1.0": 1.2500,
            "LONG_TARGET_1.618": 1.2685,
        }
    )

    position = _make_position(
        "EURUSD.r",
        pd.Timestamp("2026-01-01"),
        row,
        1,
        {
            "strategy_name": "enbolsa_swing_quality:macd_breakout",
            "entry_rule": "macd_breakout",
            "tp_mult": 1.0,
            "size_fraction": 1.0,
            "swing_quality_gate_enabled": True,
        },
    )

    assert position is not None
    assert position["entry_price"] == 1.2501
    assert position["entry_price"] != row["LONG_FIB_LEVEL_0.618"]
    assert position["SWING_QUALITY_PASS"] is True


def test_swing_quality_cli_generates_audit_without_backtests(tmp_path: Path) -> None:
    output_dir = tmp_path / "swing_quality"
    doc_path = tmp_path / "doc.md"
    run_meta = main(["--output-dir", str(output_dir), "--doc-path", str(doc_path), "--visual-examples-per-rule", "1"])

    assert run_meta["enbolsa_swing_quality_implemented"] is True
    assert run_meta["enbolsa_v1_preserved"] is True
    assert run_meta["riskguard_modified"] is False
    assert run_meta["full_backtests_executed"] is False
    assert run_meta["benchmark_comparisons_executed"] is False
    assert run_meta["signals_generated"] is False
    assert (output_dir / "enbolsa_swing_quality_screening.csv").exists()
    assert (output_dir / "tables" / "enbolsa_swing_quality_thresholds.csv").exists()
    assert doc_path.exists()
