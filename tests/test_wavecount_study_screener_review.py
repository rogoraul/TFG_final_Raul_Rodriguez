import json
from pathlib import Path

import pandas as pd

from trading_center.wavecount_study_screener import SCREENER_COLUMNS
from trading_center.wavecount_study_screener_review import (
    StudyScreenerReviewConfig,
    build_study_screener_review,
)


def test_study_screener_review_generates_artifacts_without_operational_flags(tmp_path: Path) -> None:
    current_dir = tmp_path / "current"
    current_dir.mkdir()
    _write_current_screener(current_dir)
    output_dir = tmp_path / "out"
    doc_path = tmp_path / "review.md"

    result = build_study_screener_review(
        StudyScreenerReviewConfig(
            current_screener_dir=current_dir,
            live_estimate_dir=tmp_path / "missing_live",
            live_estimate_audit_dir=tmp_path / "missing_audit",
            state_machine_dir=tmp_path / "missing_state",
            cycle_state_dir=tmp_path / "missing_cycle",
            persistent_dir=tmp_path / "missing_persistent",
            real_ohlc_dir=tmp_path / "missing_real",
            grid_v2_dir=tmp_path / "missing_grid",
            lag_stability_dir=tmp_path / "missing_lag",
            dashboard_review_dir=tmp_path / "missing_dashboard",
            output_dir=output_dir,
            doc_path=doc_path,
        )
    )

    for filename in [
        "current_screener_audit.csv",
        "available_wavecount_sources.csv",
        "expanded_screener.csv",
        "panel_bucket_readiness.csv",
        "warning_copy_audit.csv",
        "visual_case_inventory.csv",
        "dashboard_panel_requirements.csv",
        "issues_or_risks.csv",
    ]:
        assert (output_dir / "tables" / filename).exists(), filename
    assert (output_dir / "run_meta.json").exists()
    assert (output_dir / "WAVECOUNT_STUDY_SCREENER_REVIEW_V1.md").exists()
    assert doc_path.exists()

    meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    expanded = pd.read_csv(output_dir / "tables" / "expanded_screener.csv")
    buckets = pd.read_csv(output_dir / "tables" / "panel_bucket_readiness.csv")

    assert result.decision in {
        "wavecount_screener_study_only_minimal_panel",
        "wavecount_screener_needs_more_real_cases",
        "wavecount_screener_ready_for_panel_design",
    }
    assert len(expanded) == 3
    assert (expanded["study_only"].astype(str).str.lower() == "true").all()
    assert (expanded["telegram_allowed"].astype(str).str.lower() == "false").all()
    assert (expanded["bot_allowed"].astype(str).str.lower() == "false").all()
    assert (expanded["can_generate_signal"].astype(str).str.lower() == "false").all()
    assert (expanded["can_filter_trade"].astype(str).str.lower() == "false").all()
    assert (expanded["can_execute_order"].astype(str).str.lower() == "false").all()
    assert "active_wave_study_candidate" in set(buckets["screener_bucket"])
    assert "dashboard_panel_requirements.csv" in {path.name for path in (output_dir / "tables").glob("*.csv")}

    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["telegram_implemented"] is False
    assert meta["bot_implemented"] is False
    assert meta["mt5_connected"] is False
    assert meta["backtests_executed"] is False
    assert meta["signals_generated"] is False
    assert meta["wavecount_used_as_filter"] is False


def _write_current_screener(root: Path) -> None:
    rows = [
        _row("ACTIVE", "active_wave_study_candidate", "possible_wave3_active", 10, 72),
        _row("WATCH", "candidate_wave_watch", "possible_wave3_candidate", 20, 48),
        _row("OLD", "invalidated_old_context", "invalidated", 70, 20),
    ]
    frame = pd.DataFrame(rows).reindex(columns=SCREENER_COLUMNS)
    frame.to_csv(root / "wavecount_study_screener.csv", index=False)
    (root / "wavecount_study_screener.json").write_text(
        json.dumps(frame.to_dict(orient="records"), indent=2),
        encoding="utf-8",
    )


def _row(symbol: str, bucket: str, wave: str, rank: int, score: int) -> dict[str, object]:
    return {
        "screener_id": f"screen_{symbol}",
        "generated_at": "2026-05-28T00:00:00Z",
        "symbol": symbol,
        "market_group": "Synthetic",
        "timeframe": "H4",
        "higher_timeframe": "D1",
        "as_of_bar_time": "2026-03-17T04:00:00",
        "source": "test",
        "screener_bucket": bucket,
        "screener_rank": rank,
        "screener_score": score,
        "live_estimated_wave": wave,
        "confirmed_wave_context": wave if wave == "invalidated" else f"{wave}_late",
        "structure_family": "impulse",
        "direction": "long",
        "current_leg_status": "synthetic",
        "confidence_bucket": "low",
        "freshness_status": "study",
        "display_policy": "show_live_estimate_with_warning" if wave != "invalidated" else "manual_review_only",
        "visual_readability": "readable",
        "label_plausible": "true",
        "latest_close": 100.0,
        "activation_level": 101.0,
        "invalidation_level": 90.0,
        "distance_to_activation_pct": 1.0,
        "distance_to_invalidation_pct": 10.0,
        "display_badge": "study",
        "required_warning": "Study context only; not a signal, not a filter, not executable.",
        "recommended_study_action": "open_chart",
        "show_in_study_screener": True,
        "show_in_main_dashboard": False,
        "why_in_screener": "synthetic study row",
        "why_not_signal": "WaveCount is informational; not a signal and not a filter.",
        "is_read_only": True,
        "study_only": True,
        "telegram_allowed": False,
        "bot_allowed": False,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "method_version": "test",
        "payload_json": json.dumps({"operational_use": "forbidden"}),
    }
