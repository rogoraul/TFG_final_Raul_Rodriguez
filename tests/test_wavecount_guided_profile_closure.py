from pathlib import Path

import pandas as pd

from backtests.wavecount.build_wavecount_guided_profile_closure import (
    build_phase25_final_policy_matrix,
    build_phase25_future_path_recommendation,
    build_phase25_metals_decision,
    build_phase25_phase_inventory,
)


def test_phase_inventory_marks_256_official_and_259_diagnostic():
    phase_dirs = {
        "2.5.0": Path("p250"),
        "2.5.1": Path("p251"),
        "2.5.2": Path("p252"),
        "2.5.2b": Path("p252b"),
        "2.5.3": Path("p253"),
        "2.5.4": Path("p254"),
        "2.5.5": Path("p255"),
        "2.5.6": Path("p256"),
        "2.5.6b": Path("p256b"),
        "2.5.7": Path("p257"),
        "2.5.8": Path("p258"),
        "2.5.9": Path("p259"),
    }

    inventory = build_phase25_phase_inventory(phase_dirs)
    statuses = dict(zip(inventory["phase"], inventory["status"]))

    assert statuses["2.5.6"] == "official_policy"
    assert statuses["2.5.9"] == "diagnostic_support"
    assert statuses["2.5.2b"] == "auxiliary"


def test_final_policy_matrix_never_generates_signals_and_keeps_robust_diagnostic_only():
    matrix = build_phase25_final_policy_matrix()
    by_component = matrix.set_index("component")

    assert not matrix["can_generate_signal"].any()
    assert by_component.loc["visual prominence", "final_status"] == "official_policy"
    assert by_component.loc["robust prominence P5-P95", "final_status"] == "diagnostic_only"
    assert not bool(by_component.loc["robust prominence P5-P95", "can_affect_bucket_now"])
    assert by_component.loc["H4/D1 intermediate", "final_status"] == "official_policy"


def test_metals_decision_warns_without_excluding_whole_group():
    phase257 = pd.DataFrame(
        [
            {"candidate_id": "m1", "resolved_market_group": "Metals"},
            {"candidate_id": "f1", "resolved_market_group": "Forex Majors"},
        ]
    )
    phase258_metals = pd.DataFrame(
        [
            {"candidate_id": "m1", "metals_prominence_diagnosis": "visual_window_too_large_possible"},
            {"candidate_id": "m2", "metals_prominence_diagnosis": "metals_prominence_acceptable_in_this_case"},
        ]
    )
    phase259 = pd.DataFrame([{"candidate_id": "m1", "resolved_market_group": "Metals"}])

    decision = build_phase25_metals_decision(phase257, phase258_metals, phase259)
    row = decision.iloc[0]

    assert row["final_metals_status"] == "metals_supported_with_warning"
    assert "Do not exclude the whole Metals group" in row["notes"]
    assert "does not rescue" in row["robust_prominence_policy"]


def test_future_path_recommends_returning_to_tfg_core_after_unchanged_259():
    recommendation_259 = pd.DataFrame(
        [
            {
                "phase2510_recommendation": "adopt_robust_prominence_as_diagnostic_only",
                "reason": "Robust prominence does not change buckets.",
            }
        ]
    )

    future = build_phase25_future_path_recommendation(recommendation_259)
    primary = future[future["priority"].eq("primary_recommendation")].iloc[0]

    assert primary["path_option"] == "pause_wavecount_and_return_to_tfg_core"
    assert bool(primary["recommended"])
    assert "Do not turn WaveCount scoring" in primary["do_not_do"]
