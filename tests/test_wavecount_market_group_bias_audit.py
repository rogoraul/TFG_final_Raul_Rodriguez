from pathlib import Path

import pandas as pd

from backtests.wavecount.build_wavecount_market_group_bias_audit import (
    build_bucket_distribution,
    build_market_group_mapping,
    build_policy_recommendation,
    build_prominence_by_market_group,
    join_scores_with_market_group,
)


def _scores() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": "impulse_exp252_forex_audjpy_h4_intermediate_impulse_001",
                "group": "Forex Majors",
                "symbol": "AUDJPY.r",
                "source_scope": "h4_d1",
                "timeframe": "H4",
                "swing_degree": "intermediate",
                "phase256_policy_bucket": "high_quality_structure",
                "prominence_policy_label": "acceptable_for_timeframe",
                "phase256_score": 90,
            },
            {
                "candidate_id": "impulse_exp252_metals_xagusd_h4_intermediate_impulse_002",
                "group": "Metals",
                "symbol": "XAGUSD.r",
                "source_scope": "h4_d1",
                "timeframe": "H4",
                "swing_degree": "intermediate",
                "phase256_policy_bucket": "visual_watchlist_low_prominence",
                "prominence_policy_label": "low_prominence_vs_window",
                "phase256_score": 44,
            },
            {
                "candidate_id": "impulse_aux252b_index_aus200_h1_intermediate_impulse_007",
                "group": "Index",
                "symbol": "AUS200",
                "source_scope": "h1_h4",
                "timeframe": "H1",
                "swing_degree": "intermediate",
                "phase256_policy_bucket": "auxiliary_low_prominence_substructure",
                "prominence_policy_label": "better_as_lower_tf_substructure",
                "phase256_score": 52,
            },
        ]
    )


def test_mapping_prefers_sql_explicit_group():
    symbol_control = pd.DataFrame(
        [
            {"symbol": "AUDJPY.r", "sql_market_group": "Forex Majors", "enabled": 1},
            {"symbol": "XAGUSD.r", "sql_market_group": "Metals", "enabled": 1},
        ]
    )
    symbol_tf = pd.DataFrame(
        [
            {"symbol": "AUDJPY.r", "timeframe": "H4"},
            {"symbol": "XAGUSD.r", "timeframe": "H4"},
        ]
    )

    mapping = build_market_group_mapping(_scores(), symbol_control, symbol_tf)
    row = mapping[mapping["symbol"].eq("XAGUSD.r")].iloc[0]

    assert row["resolved_market_group"] == "Metals"
    assert row["mapping_confidence"] == "sql_explicit"
    assert row["category_source"] == "symbol_control.group"


def test_mapping_uses_artifact_group_when_sql_missing():
    mapping = build_market_group_mapping(_scores(), pd.DataFrame(), pd.DataFrame())
    row = mapping[mapping["symbol"].eq("AUS200")].iloc[0]

    assert row["resolved_market_group"] == "Index"
    assert row["mapping_confidence"] == "artifact_prefix"


def test_join_scores_adds_market_group_fields():
    mapping = pd.DataFrame(
        [
            {
                "symbol": "AUDJPY.r",
                "sql_market_group": "Forex Majors",
                "artifact_market_group": "Forex Majors",
                "resolved_market_group": "Forex Majors",
                "mapping_confidence": "sql_explicit",
                "category_source": "symbol_control.group",
                "symbol_in_sql": True,
                "notes": "",
            }
        ]
    )
    joined = join_scores_with_market_group(_scores().iloc[[0]], mapping)

    assert joined.iloc[0]["resolved_market_group"] == "Forex Majors"
    assert joined.iloc[0]["symbol_in_sql"] == True


def test_bucket_distribution_counts_phase256_buckets():
    mapping = pd.DataFrame(
        [
            {
                "symbol": "AUDJPY.r",
                "sql_market_group": "Forex Majors",
                "artifact_market_group": "Forex Majors",
                "resolved_market_group": "Forex Majors",
                "mapping_confidence": "sql_explicit",
                "category_source": "symbol_control.group",
                "symbol_in_sql": True,
                "notes": "",
            },
            {
                "symbol": "XAGUSD.r",
                "sql_market_group": "Metals",
                "artifact_market_group": "Metals",
                "resolved_market_group": "Metals",
                "mapping_confidence": "sql_explicit",
                "category_source": "symbol_control.group",
                "symbol_in_sql": True,
                "notes": "",
            },
            {
                "symbol": "AUS200",
                "sql_market_group": "Index",
                "artifact_market_group": "Index",
                "resolved_market_group": "Index",
                "mapping_confidence": "sql_explicit",
                "category_source": "symbol_control.group",
                "symbol_in_sql": True,
                "notes": "",
            },
        ]
    )
    joined = join_scores_with_market_group(_scores(), mapping)
    distribution = build_bucket_distribution(joined)
    metals = distribution[distribution["resolved_market_group"].eq("Metals")].iloc[0]

    assert metals["visual_watchlist_low_prominence"] == 1
    assert metals["low_prominence_rows"] == 1


def test_prominence_stats_are_grouped_by_market_group():
    mapping = pd.DataFrame(
        [
            {
                "symbol": "XAGUSD.r",
                "sql_market_group": "Metals",
                "artifact_market_group": "Metals",
                "resolved_market_group": "Metals",
                "mapping_confidence": "sql_explicit",
                "category_source": "symbol_control.group",
                "symbol_in_sql": True,
                "notes": "",
            }
        ]
    )
    scores = join_scores_with_market_group(_scores()[_scores()["symbol"].eq("XAGUSD.r")], mapping)
    prominence = pd.DataFrame(
        [
            {
                "candidate_id": "impulse_exp252_metals_xagusd_h4_intermediate_impulse_002",
                "prominence_vs_window": 0.05,
                "duration_vs_window": 0.03,
                "scale_fit_label": "too_small_for_timeframe",
                "prominence_policy_label": "low_prominence_vs_window",
            }
        ]
    )
    stats = build_prominence_by_market_group(scores, prominence)

    assert stats.iloc[0]["resolved_market_group"] == "Metals"
    assert stats.iloc[0]["too_small_for_timeframe_count"] == 1


def test_policy_recommendation_warns_when_sql_groups_are_unrepresented():
    distribution = pd.DataFrame(
        [
            {"resolved_market_group": "Forex Majors", "exclude_from_guided_search_pct": 40.0},
            {"resolved_market_group": "Metals", "exclude_from_guided_search_pct": 60.0},
        ]
    )
    prominence = pd.DataFrame()
    sql_categories = pd.DataFrame(
        [
            {"sql_market_group": "Forex Majors"},
            {"sql_market_group": "Metals"},
            {"sql_market_group": "Crypto"},
        ]
    )

    recommendation = build_policy_recommendation(distribution, prominence, sql_categories)

    assert recommendation.iloc[0]["policy_recommendation"] == "keep_global_policy_with_group_warning"
    assert recommendation.iloc[0]["must_normalize_before_phase257"] == False
