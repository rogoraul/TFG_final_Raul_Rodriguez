import pandas as pd

from backtests.wavecount.build_wavecount_robust_prominence_policy_trial import (
    add_prominence_diagnostics,
    apply_percentile_fallback,
    apply_phase259_candidate_policy,
)


def _base_row(**overrides):
    row = {
        "candidate_id": "c1",
        "source_scope": "h4_d1",
        "resolved_market_group": "Metals",
        "symbol": "XAGUSD.r",
        "timeframe": "H4",
        "swing_degree": "intermediate",
        "review_category": "impulse",
        "phase257_policy_bucket": "exclude_from_guided_search",
        "phase256_policy_bucket": "exclude_from_guided_search",
        "phase256_score": 40.0,
        "metrics_available": True,
        "visual_window_prominence": 0.05,
        "robust_window_prominence_p05_p95": 0.22,
        "robust_improvement_ratio_p05_p95": 4.4,
        "last_n_improvement_ratio": 3.0,
        "symbol_percentile_robust_prominence": 0.6,
        "group_percentile_robust_prominence": 0.6,
        "context_must_not_rescue_bad_count": False,
        "chart_path": "",
    }
    row.update(overrides)
    return row


def test_percentile_fallback_uses_group_when_symbol_family_is_small():
    rows = [_base_row(candidate_id=f"x{i}", symbol="XAGUSD.r", robust_window_prominence_p05_p95=0.1 + i / 100) for i in range(3)]
    rows += [_base_row(candidate_id=f"g{i}", symbol="XAGEUR.r", robust_window_prominence_p05_p95=0.2 + i / 100) for i in range(3)]
    data = pd.DataFrame(rows)

    out, families = apply_percentile_fallback(data, min_symbol_family_size=5)

    assert set(out["percentile_scope_used"]) == {"group_timeframe_degree"}
    assert out["percentile_family_size"].min() == 6
    assert set(families["percentile_scope"]) == {"symbol_timeframe_degree", "group_timeframe_degree"}


def test_prominence_diagnostics_distinguish_true_low_and_window_distorted():
    data = pd.DataFrame(
        [
            _base_row(candidate_id="distorted"),
            _base_row(
                candidate_id="true_low",
                visual_window_prominence=0.04,
                robust_window_prominence_p05_p95=0.06,
                robust_improvement_ratio_p05_p95=1.1,
                last_n_improvement_ratio=1.0,
                symbol_percentile_robust_prominence=0.1,
                group_percentile_robust_prominence=0.1,
            ),
        ]
    )
    data, _ = apply_percentile_fallback(data, min_symbol_family_size=1)
    out = add_prominence_diagnostics(data)

    diagnostics = dict(zip(out["candidate_id"], out["phase259_prominence_diagnostic"]))
    assert diagnostics["distorted"] == "window_distorted_low_prominence"
    assert diagnostics["true_low"] == "true_low_prominence"


def test_candidate_policy_caps_excluded_upgrade_at_watchlist():
    data = pd.DataFrame([_base_row(candidate_id="candidate")])
    data, _ = apply_percentile_fallback(data, min_symbol_family_size=1)
    data = add_prominence_diagnostics(data)

    out = apply_phase259_candidate_policy(data)
    row = out.iloc[0]

    assert row["phase259_candidate_bucket"] == "candidate_visual_watchlist_low_prominence"
    assert row["phase259_bucket_change_vs_256"] == "upgrade"
    assert row["phase259_ready_for_next_step"] == "watchlist_only"


def test_candidate_policy_does_not_rescue_context_risk():
    data = pd.DataFrame([_base_row(candidate_id="risk", context_must_not_rescue_bad_count=True)])
    data, _ = apply_percentile_fallback(data, min_symbol_family_size=1)
    data = add_prominence_diagnostics(data)

    out = apply_phase259_candidate_policy(data)
    row = out.iloc[0]

    assert row["phase259_candidate_bucket"] == "candidate_exclude_from_guided_search"
    assert row["phase259_bucket_change_vs_256"] == "unchanged"
