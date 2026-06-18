from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_center.enbolsa_strategy_visual_audit import CACHE_BY_PARTIAL_SOURCE, DEFAULT_CACHE_DIR, DEFAULT_TRADE_LOG_CSV, main


def test_enbolsa_strategy_visual_audit_cli_smoke(tmp_path: Path) -> None:
    if not DEFAULT_TRADE_LOG_CSV.exists():
        pytest.skip("Canonical ENBOLSA trade_log is not available")
    if not any((DEFAULT_CACHE_DIR / cache_name).exists() for cache_name in CACHE_BY_PARTIAL_SOURCE.values()):
        pytest.skip("Canonical ENBOLSA visual cache is not available")

    output_dir = tmp_path / "visual_audit"
    doc_path = tmp_path / "doc.md"
    run_meta = main(
        [
            "--output-dir",
            str(output_dir),
            "--doc-path",
            str(doc_path),
            "--max-small-per-rule",
            "1",
            "--max-normal-per-rule",
            "1",
        ]
    )

    assert run_meta["visual_audit_created"] is True
    assert run_meta["strategy_modified"] is False
    assert run_meta["backtests_executed"] is False
    assert run_meta["signals_generated"] is False
    assert run_meta["sql_real_written"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["telegram_connected"] is False
    assert run_meta["charts_created"] >= 1
    assert (output_dir / "tables" / "visual_case_inventory.csv").exists()
    assert (output_dir / "tables" / "w1_visual_reconstruction_audit.csv").exists()
    assert list((output_dir / "charts").glob("*.png"))
    assert doc_path.exists()

    persisted = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert persisted["orders_sent"] == 0
    assert persisted["ddl_executed"] is False
