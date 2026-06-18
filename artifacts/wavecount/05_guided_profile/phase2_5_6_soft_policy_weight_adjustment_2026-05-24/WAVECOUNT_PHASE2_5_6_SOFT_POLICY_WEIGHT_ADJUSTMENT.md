# WaveCount Phase 2.5.6 Soft Policy Weight Adjustment

Generated at: 2026-05-24T19:31:01

## Scope

Ajuste conservador de buckets/pesos de prominencia despues de la auditoria visual 2.5.5.
No genera senales, no ejecuta backtests y no cambia pivotes, conteos ni estrategias.

## Results

- Total scored rows: 108
- Changed bucket/score rows: 8
- Watchlist low-prominence rows: 1
- Auxiliary low-prominence rows: 7
- Excluded rows: 90

## Key Decision

impulse_exp252_metals_xagusd_h4_intermediate_impulse_002 deja de ser `usable_provisional_structure` y pasa a `visual_watchlist_low_prominence`. `exclude_from_guided_search` se mantiene estable; el ajuste no relaja la politica, solo separa baja prominencia en watchlist/subestructura auxiliar no operativa.

## Tables

- `tables/low_prominence_false_positive_diagnostics.csv`
- `tables/phase256_policy_scores.csv`
- `tables/phase254_vs_phase256_bucket_changes.csv`
- `tables/phase256_watchlist_cases.csv`
- `tables/phase256_exclusions.csv`
- `tables/phase256_visual_recheck.csv`
- `tables/phase257_recommendation.csv`
- `tables/user_review_if_any.csv`
