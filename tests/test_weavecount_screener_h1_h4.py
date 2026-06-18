from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from trading_center.weavecount_screener_h1_h4 import (
    DEFAULT_OUTPUT_DIR,
    SOURCE_GROUPS,
    SOURCE_TIMEFRAMES,
    build_weavecount_screener,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def test_weavecount_screener_artifact_covers_target_universe() -> None:
    rows = _read_csv(DEFAULT_OUTPUT_DIR / "weavecount_screener.csv")

    assert len(rows) == 94
    assert sorted({row["market_group"] for row in rows}) == sorted(SOURCE_GROUPS)
    assert sorted({row["timeframe"] for row in rows}) == sorted(SOURCE_TIMEFRAMES)
    assert len({row["symbol"] for row in rows}) == 47
    assert {row["timeframe"]: sum(1 for item in rows if item["timeframe"] == row["timeframe"]) for row in rows} == {
        "H1": 47,
        "H4": 47,
    }
    assert not any(row["market_group"] in {"Forex Exotic", "Crypto", "Commodities"} for row in rows)


def test_weavecount_screener_keeps_study_only_safety_flags() -> None:
    rows = _read_csv(DEFAULT_OUTPUT_DIR / "weavecount_screener.csv")
    run_meta = json.loads((DEFAULT_OUTPUT_DIR / "run_meta.json").read_text(encoding="utf-8"))

    assert {row["is_study_only"] for row in rows} == {"True"}
    assert {row["is_signal"] for row in rows} == {"False"}
    assert {row["wavecount_used_as_filter"] for row in rows} == {"False"}
    assert {row["can_execute_order"] for row in rows} == {"False"}
    assert run_meta["weavecount_screener_implemented"] is True
    assert run_meta["artifact_first"] is True
    assert run_meta["source_groups"] == list(SOURCE_GROUPS)
    assert run_meta["source_timeframes"] == list(SOURCE_TIMEFRAMES)
    assert run_meta["symbol_timeframe_expected"] == 94
    assert run_meta["symbol_timeframes_evaluated"] == 94
    assert run_meta["study_only"] is True
    assert run_meta["is_signal"] is False
    assert run_meta["wavecount_used_as_filter"] is False
    assert run_meta["can_execute_order_any_true"] is False
    assert run_meta["sql_real_written"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["telegram_connected"] is False


def test_weavecount_screener_outputs_points_and_segments_for_candidates() -> None:
    rows = _read_csv(DEFAULT_OUTPUT_DIR / "weavecount_screener.csv")
    points = _read_csv(DEFAULT_OUTPUT_DIR / "weavecount_structure_points.csv")
    segments = _read_csv(DEFAULT_OUTPUT_DIR / "weavecount_chart_segments.csv")
    case_ids = {row["case_id"] for row in rows if row["count_label"] != "no_clear_count"}
    w2_case_ids = {row["case_id"] for row in rows if row["count_label"] == "W2?"}

    assert case_ids
    assert {row["count_label"] for row in rows} <= {"W1", "W2", "W3", "W4", "W5", "W1?", "W2?", "W3?", "W4?", "W5?", "no_clear_count"}
    assert {row["quality_status"] for row in rows} <= {"fuerte", "media", "debil"}
    assert all(row["quality_status"] for row in rows)
    assert all(row["quality_score"] for row in rows)
    assert all(row["quality_reason"] for row in rows)
    assert any(row["count_label"].endswith("?") for row in rows)
    assert {row["case_id"] for row in points}.issubset(case_ids)
    assert {row["case_id"] for row in segments}.issubset(case_ids)
    assert any(row["segment_kind"] == "current" for row in segments)
    assert w2_case_ids
    assert all(row["activation_level"] for row in rows if row["case_id"] in w2_case_ids)
    assert all(row["invalidation_level"] for row in rows if row["case_id"] in w2_case_ids)
    assert w2_case_ids.issubset({row["case_id"] for row in segments if row["segment_kind"] == "current"})


def test_weavecount_screener_does_not_force_count_when_structure_is_missing(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1)
    rows = []
    for index in range(80):
        timestamp = start + timedelta(hours=index)
        rows.append(
            {
                "market_group": "Forex Majors",
                "symbol": "TEST.r",
                "timeframe": "H1",
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
            }
        )
    csv_path = tmp_path / "flat_ohlc.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    result = build_weavecount_screener(csv_path, window_bars=80)

    assert result["screener"][0]["count_label"] == "no_clear_count"
    assert result["screener"][0]["confidence_status"] == "no_clear"
    assert result["structure_points"] == []
    assert result["chart_segments"] == []
