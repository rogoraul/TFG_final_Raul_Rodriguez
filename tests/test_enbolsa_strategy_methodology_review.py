from __future__ import annotations

import json
from pathlib import Path

from trading_center.enbolsa_strategy_methodology_review import main
from trading_center.readonly_dashboard import read_csv


def test_enbolsa_strategy_methodology_review_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "review"
    doc_path = tmp_path / "doc.md"

    run_meta = main(["--output-dir", str(output_dir), "--doc-path", str(doc_path)])

    assert run_meta["strategy_modified"] is False
    assert run_meta["fib_limit_modified"] is False
    assert run_meta["macd_breakout_modified"] is False
    assert run_meta["backtests_executed"] is False
    assert run_meta["signals_generated"] is False
    assert (output_dir / "tables" / "enbolsa_strategy_rule_contract.csv").exists()
    assert (output_dir / "tables" / "enbolsa_strategy_claim_policy.csv").exists()
    assert doc_path.exists()


def test_macd_breakout_is_not_fibonacci_entry(tmp_path: Path) -> None:
    output_dir = tmp_path / "review"
    doc_path = tmp_path / "doc.md"
    main(["--output-dir", str(output_dir), "--doc-path", str(doc_path)])

    rows = read_csv(output_dir / "tables" / "enbolsa_strategy_rule_contract.csv")
    by_rule = {row["entry_rule"]: row for row in rows}

    assert by_rule["macd_breakout"]["uses_fibonacci_entry"] == "False"
    assert by_rule["macd_breakout"]["uses_macd_cross"] == "True"
    assert by_rule["fib_limit"]["uses_fibonacci_entry"] == "True"
    assert by_rule["fib_limit"]["entry_trigger"] == "touch_0_618_retracement"


def test_run_meta_keeps_external_side_effects_blocked(tmp_path: Path) -> None:
    output_dir = tmp_path / "review"
    doc_path = tmp_path / "doc.md"
    main(["--output-dir", str(output_dir), "--doc-path", str(doc_path)])

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))

    assert run_meta["sql_real_written"] is False
    assert run_meta["ddl_executed"] is False
    assert run_meta["db_connected"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["telegram_connected"] is False
    assert run_meta["orders_sent"] == 0
