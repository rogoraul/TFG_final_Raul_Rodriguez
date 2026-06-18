# WaveCount Phase 2.5.6b Market Group Bias Audit

Generated at: 2026-05-24T19:59:12

## Scope

Auditoria conservadora de sesgo por grupo de mercado sobre la politica 2.5.6.
No genera senales, no ejecuta backtests y no cambia pivotes, conteos ni estrategias.

## SQL categories

- SQL groups found: Commodities, Crypto, Forex Exotic, Forex Majors, Index, Metals
- WaveCount represented groups: Forex Majors, Index, Metals

## Decision

- Policy recommendation: `keep_global_policy_with_group_warning`
- Percentile recommendation: `use_group_percentile_diagnostics`
- Can Phase 2.5.7 advance: `True`
- Must normalize before 2.5.7: `False`

## Tables

- `tables/sql_data_inventory.csv`
- `tables/sql_symbol_timeframe_inventory.csv`
- `tables/sql_market_categories.csv`
- `tables/market_group_mapping_evidence.csv`
- `tables/phase256_scores_with_market_group.csv`
- `tables/bucket_distribution_by_market_group.csv`
- `tables/prominence_by_market_group.csv`
- `tables/ewo_by_market_group.csv`
- `tables/ema_htf_by_market_group.csv`
- `tables/market_group_visual_selection.csv`
- `tables/market_group_visual_review.csv`
- `tables/market_group_bias_risks.csv`
- `tables/market_group_policy_recommendation.csv`
