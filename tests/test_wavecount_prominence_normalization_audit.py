import pandas as pd

from backtests.wavecount.build_wavecount_prominence_normalization_audit import (
    build_policy_recommendation,
    build_prominence_aggregation_audit,
    compute_candidate_alternative_metrics,
)


def test_compute_candidate_alternative_metrics_detects_spike_distorted_visual_window():
    timestamps = pd.date_range("2026-01-01", periods=20, freq="4h")
    context = pd.DataFrame(
        {
            "example_id": ["ex"] * 20,
            "timestamp": timestamps,
            "open": [100] * 20,
            "high": [101] * 20,
            "low": [99] * 20,
            "close": [100] * 20,
        }
    )
    context.loc[0, "high"] = 200
    candidate = pd.Series(
        {
            "candidate_id": "c1",
            "example_id": "ex",
            "timeframe": "H4",
            "start_time": timestamps[5],
            "end_time": timestamps[8],
        }
    )

    metrics = compute_candidate_alternative_metrics(candidate, context)

    assert metrics["metrics_available"] is True
    assert metrics["visual_window_prominence"] < metrics["robust_window_prominence_p05_p95"]
    assert metrics["robust_improvement_ratio_p05_p95"] > 1


def test_aggregation_audit_keeps_timeframe_and_degree_separated():
    metrics = pd.DataFrame(
        [
            {
                "resolved_market_group": "Metals",
                "source_scope": "h4_d1",
                "timeframe": "H4",
                "swing_degree": "intermediate",
                "phase257_policy_bucket": "exclude_from_guided_search",
                "prominence_vs_window": 0.04,
                "visual_window_prominence": 0.04,
                "metrics_available": True,
                "prominence_policy_label": "low_prominence_vs_window",
                "scale_fit_label": "too_small_for_timeframe",
            },
            {
                "resolved_market_group": "Metals",
                "source_scope": "h1_h4",
                "timeframe": "H1",
                "swing_degree": "major",
                "phase257_policy_bucket": "auxiliary_substructure",
                "prominence_vs_window": 0.30,
                "visual_window_prominence": 0.30,
                "metrics_available": True,
                "prominence_policy_label": "acceptable_for_timeframe",
                "scale_fit_label": "acceptable_for_timeframe",
            },
        ]
    )

    audit = build_prominence_aggregation_audit(metrics)
    split = audit[audit["aggregation_level"].eq("group_timeframe_degree")]

    assert len(split) == 2
    assert set(split["timeframe"]) == {"H4", "H1"}
    assert set(split["swing_degree"]) == {"intermediate", "major"}
    assert set(split["mixing_risk"]) == {"low_separates_scope_timeframe_degree"}


def test_policy_recommendation_prefers_symbol_percentiles_when_metals_stays_low():
    metrics = pd.DataFrame(
        [
            {"robust_improvement_ratio_p05_p95": 1.0},
            {"robust_improvement_ratio_p05_p95": 1.1},
        ]
    )
    metals_audit = pd.DataFrame(
        [{"metals_prominence_diagnosis": "true_low_prominence_likely"}]
    )
    comparison = pd.DataFrame(
        [
            {
                "resolved_market_group": "Metals",
                "source_scope": "h4_d1",
                "visual_window_prominence_median": 0.04,
            }
        ]
    )

    out = build_policy_recommendation(metrics, metals_audit, comparison)

    assert out.iloc[0]["decision"] == "use_symbol_timeframe_degree_percentiles_next"
    assert bool(out.iloc[0]["phase256_still_valid"]) is True
    assert bool(out.iloc[0]["should_change_policy_now"]) is False
