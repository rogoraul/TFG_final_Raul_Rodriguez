# WaveCount Phase 2.5.7 Market-Stratified Expansion

Generated at: 2026-05-24T20:49:47

## Scope

Expansion descriptiva estratificada por grupo de mercado. No genera senales, no ejecuta backtests y no cambia la politica 2.5.6.

## Included groups

- Forex Majors
- Index
- Metals

SQL also contains Commodities, Crypto and Forex Exotic, but they remain out of scope because WaveCount 2.5.6 has no evidence there.

## Results

- New H4/D1 diagnostic candidates: 54
- Combined policy rows: 162
- Visual gallery rows: 20
- Missing image refs: 0

## Decision

- Phase 2.5.8 recommendation: `open_group_percentile_normalization_phase`
- Reason: La prominencia por ventana difiere bastante entre grupos; conviene normalizacion por percentiles antes de endurecer umbrales.

## Methodological guardrails

- Do not compare raw scores across market groups as fully normalized.
- Prominence remains offline/visual-window based and is not live-ready.
- EWO, EMA and HTF remain soft context, not signals or hard filters.
- H4/D1 intermediate remains the primary base; H1/H4 remains auxiliary.

## Tables

- `tables/phase257_expansion_scope.csv`
- `tables/phase257_expanded_candidates.csv`
- `tables/phase257_policy_scores.csv`
- `tables/phase257_bucket_distribution_by_group.csv`
- `tables/phase257_prominence_percentiles_by_group.csv`
- `tables/phase257_prominence_percentiles_by_symbol.csv`
- `tables/phase257_ewo_by_group.csv`
- `tables/phase257_ema_htf_by_group.csv`
- `tables/phase257_visual_gallery_selection.csv`
- `tables/phase257_visual_review.csv`
- `tables/phase257_group_bias_risks.csv`
- `tables/phase258_recommendation.csv`
- `tables/user_review_if_any.csv`
