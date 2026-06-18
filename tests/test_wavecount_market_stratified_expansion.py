import pandas as pd

from backtests.wavecount.build_wavecount_market_stratified_expansion import (
    build_bucket_distribution_by_group,
    build_phase258_recommendation,
    build_prominence_percentiles,
    choose_symbols_by_market_group,
)


def _sql_symbol_tf() -> pd.DataFrame:
    rows = []
    for group, symbols in {
        "Forex Majors": ["AUDJPY.r", "EURUSD.r", "GBPUSD.r"],
        "Index": ["AUS200", "US500", "US30"],
        "Metals": ["XAGUSD.r", "XAUUSD.r", "XPTUSD"],
        "Crypto": ["BTCUSD"],
    }.items():
        for symbol in symbols:
            for timeframe in ("H4", "D1"):
                rows.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "rows_count": 1000,
                        "sql_market_group": group,
                        "enabled": 1,
                    }
                )
    return pd.DataFrame(rows)


def _mapping() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "AUDJPY.r",
                "artifact_market_group": "Forex Majors",
                "resolved_market_group": "Forex Majors",
                "mapping_confidence": "sql_explicit",
            },
            {
                "symbol": "AUS200",
                "artifact_market_group": "Index",
                "resolved_market_group": "Index",
                "mapping_confidence": "sql_explicit",
            },
            {
                "symbol": "XAGUSD.r",
                "artifact_market_group": "Metals",
                "resolved_market_group": "Metals",
                "mapping_confidence": "sql_explicit",
            },
        ]
    )


def test_choose_symbols_uses_only_represented_groups_and_prioritizes_artifact_symbols():
    selection = choose_symbols_by_market_group(_sql_symbol_tf(), _mapping(), max_symbols_per_group=2)

    assert set(selection["resolved_market_group"]) == {"Forex Majors", "Index", "Metals"}
    assert "BTCUSD" not in set(selection["symbol"])
    first_by_group = selection.sort_values("selection_rank").groupby("resolved_market_group").first()
    assert first_by_group.loc["Forex Majors", "symbol"] == "AUDJPY.r"
    assert first_by_group.loc["Index", "symbol"] == "AUS200"
    assert first_by_group.loc["Metals", "symbol"] == "XAGUSD.r"


def test_bucket_distribution_counts_phase257_buckets_by_group():
    scores = pd.DataFrame(
        [
            {"resolved_market_group": "Forex Majors", "source_scope": "h4_d1", "symbol": "AUDJPY.r", "swing_degree": "intermediate", "phase257_policy_bucket": "high_quality_structure"},
            {"resolved_market_group": "Forex Majors", "source_scope": "h1_h4", "symbol": "AUDJPY.r", "swing_degree": "minor", "phase257_policy_bucket": "auxiliary_substructure"},
            {"resolved_market_group": "Metals", "source_scope": "h4_d1", "symbol": "XAGUSD.r", "swing_degree": "intermediate", "phase257_policy_bucket": "exclude_from_guided_search"},
        ]
    )

    distribution = build_bucket_distribution_by_group(scores)
    forex = distribution[distribution["resolved_market_group"].eq("Forex Majors")].iloc[0]
    metals = distribution[distribution["resolved_market_group"].eq("Metals")].iloc[0]

    assert forex["high_quality_structure"] == 1
    assert forex["h1_h4_count"] == 1
    assert metals["exclude_from_guided_search_pct"] == 100.0


def test_prominence_percentiles_are_grouped_and_count_low_prominence():
    scores = pd.DataFrame(
        [
            {
                "resolved_market_group": "Index",
                "symbol": "AUS200",
                "timeframe": "H4",
                "swing_degree": "intermediate",
                "prominence_vs_window": 0.10,
                "duration_vs_window": 0.05,
                "prominence_policy_label": "low_prominence_vs_window",
                "scale_fit_label": "too_small_for_timeframe",
            },
            {
                "resolved_market_group": "Index",
                "symbol": "AUS200",
                "timeframe": "H4",
                "swing_degree": "intermediate",
                "prominence_vs_window": 0.30,
                "duration_vs_window": 0.20,
                "prominence_policy_label": "acceptable_for_timeframe",
                "scale_fit_label": "acceptable_for_timeframe",
            },
        ]
    )

    out = build_prominence_percentiles(scores, ["resolved_market_group"])

    assert out.iloc[0]["prominence_vs_window_count"] == 2
    assert out.iloc[0]["prominence_vs_window_median"] == 0.2
    assert out.iloc[0]["low_prominence_count"] == 1
    assert out.iloc[0]["too_small_for_timeframe_count"] == 1


def test_phase258_recommends_percentiles_when_prominence_spread_is_high():
    distribution = pd.DataFrame(
        [
            {"resolved_market_group": "Forex Majors", "exclude_from_guided_search_pct": 80.0},
            {"resolved_market_group": "Metals", "exclude_from_guided_search_pct": 82.0},
        ]
    )
    percentiles = pd.DataFrame(
        [
            {"resolved_market_group": "Forex Majors", "prominence_vs_window_median": 0.12},
            {"resolved_market_group": "Metals", "prominence_vs_window_median": 0.31},
        ]
    )

    recommendation = build_phase258_recommendation(distribution, percentiles, pd.DataFrame())

    assert recommendation.iloc[0]["phase258_recommendation"] == "open_group_percentile_normalization_phase"
