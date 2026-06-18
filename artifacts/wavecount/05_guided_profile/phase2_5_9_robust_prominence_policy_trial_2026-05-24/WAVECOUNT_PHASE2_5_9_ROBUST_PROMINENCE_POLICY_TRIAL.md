# WaveCount Phase 2.5.9 - Robust Prominence Policy Trial

Fase metodologica candidata. No sustituye la politica 2.5.6, no recalcula conteos base y no genera senales.

## Decision

- recommendation: `adopt_robust_prominence_as_diagnostic_only`
- phase256_remains_official: `True`
- total_upgrades: `0`
- metals_upgrades: `0`

## Buckets candidatos

| phase259_candidate_bucket | count |
| --- | --- |
| candidate_exclude_from_guided_search | 138 |
| candidate_usable_provisional_structure | 8 |
| candidate_auxiliary_low_prominence_substructure | 7 |
| candidate_auxiliary_substructure | 4 |
| candidate_visual_watchlist_low_prominence | 3 |
| candidate_high_quality_structure | 1 |
| candidate_experimental_only | 1 |

## Diagnosticos de prominencia

| phase259_prominence_diagnostic | count |
| --- | --- |
| not_applicable | 66 |
| insufficient_prominence_context | 54 |
| robust_prominence_confirmed | 26 |
| window_distorted_low_prominence | 13 |
| true_low_prominence | 3 |

## Cambios por grupo

| resolved_market_group | total_candidates | unchanged | upgrades | downgrades | changed_total | changed_pct | exclude_to_watchlist | candidate_watchlist | candidate_high_quality |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Forex Majors | 72 | 72 | 0 | 0 | 0 | 0.0 | 0 | 1 | 1 |
| Index | 45 | 45 | 0 | 0 | 0 | 0.0 | 0 | 0 | 0 |
| Metals | 45 | 45 | 0 | 0 | 0 | 0.0 | 0 | 2 | 0 |

## Lectura

- Ningun excluido puede subir directamente a `candidate_high_quality_structure`.
- Las mejoras por ventana robusta se limitan a watchlist/revision.
- H1/H4 sigue como auxiliar aunque la metrica robusta mejore.
- 2.5.6 sigue siendo la politica oficial.
