# WaveCount Phase 2.5.10 - Guided Profile Closure

Cierre metodologico del bloque 2.5.x. No crea politica nueva, no recalcula conteos base, no genera senales y no ejecuta backtests.

## Decision central

- La politica oficial vigente sigue siendo Fase 2.5.6.
- Fase 2.5.9 queda como diagnostico auxiliar de prominencia robusta; no cambia buckets.
- H4/D1 `intermediate` sigue siendo base principal.
- H1/H4 queda como auxiliar/zoom.
- EWO, EMA/HTF y prominencia robusta no deben convertirse en reglas duras ni senales.

## Inventario de fases

| phase | status | decision |
| --- | --- | --- |
| 2.5.0 | superseded_by_later_phase | Usar como base de trazabilidad, no como politica final. |
| 2.5.1 | superseded_by_later_phase | Perfil util como antecedente, refinado despues. |
| 2.5.2 | diagnostic_support | Base empirica inicial para politica blanda. |
| 2.5.2b | auxiliary | Auxiliar vigente. |
| 2.5.3 | diagnostic_support | Soporte descriptivo. |
| 2.5.4 | superseded_by_later_phase | Superada por ajuste conservador 2.5.6. |
| 2.5.5 | diagnostic_support | Soporte para ajuste 2.5.6. |
| 2.5.6 | official_policy | Mantener como politica oficial. |
| 2.5.6b | diagnostic_support | Reportar por grupo; no cambiar politica. |
| 2.5.7 | diagnostic_support | Valida como ampliacion descriptiva. |
| 2.5.8 | diagnostic_support | Probar prominencia robusta como diagnostico. |
| 2.5.9 | diagnostic_support | Adoptar como diagnostico auxiliar; 2.5.6 sigue oficial. |

## Buckets oficiales 2.5.6

| metric | value | share_pct |
| --- | --- | --- |
| bucket_exclude_from_guided_search | 90 | 83.33 |
| bucket_auxiliary_low_prominence_substructure | 7 | 6.48 |
| bucket_usable_provisional_structure | 4 | 3.7 |
| bucket_auxiliary_substructure | 4 | 3.7 |
| bucket_high_quality_structure | 1 | 0.93 |
| bucket_visual_watchlist_low_prominence | 1 | 0.93 |
| bucket_experimental_only | 1 | 0.93 |

## Matriz de politica final

| component | final_status | can_affect_bucket_now | can_generate_signal |
| --- | --- | --- | --- |
| H4/D1 intermediate | official_policy | True | False |
| H4/D1 major | soft_context | True | False |
| H4/D1 minor | auxiliary_only | True | False |
| H1/H4 | auxiliary_only | True | False |
| M30/H1 | auxiliary_only | False | False |
| clean impulses | official_policy | True | False |
| provisional impulses | official_policy | True | False |
| partial 1-2-3 | soft_context | True | False |
| wave5 endpoint uncertainty | diagnostic_only | True | False |
| ABC/corrections | experimental | False | False |
| visual prominence | official_policy | True | False |
| robust prominence P5-P95 | diagnostic_only | False | False |
| symbol/timeframe/degree percentiles | diagnostic_only | False | False |
| EWO 5-35 | soft_context | True | False |
| EMA 50/150 | soft_context | True | False |
| HTF/D1 | soft_context | True | False |
| Metals | diagnostic_only | False | False |
| Forex Majors | diagnostic_only | False | False |
| Index | diagnostic_only | False | False |

## Metals

- estado: `metals_supported_with_warning`
- politica H4/D1: Use only when 2.5.6 bucket permits; tiny H4/D1 structures remain watchlist or excluded.
- politica H1/H4: Auxiliary zoom/substructure, not a replacement for H4/D1 base.

## Ruta recomendada

| path_option | reason | do_next | do_not_do |
| --- | --- | --- | --- |
| pause_wavecount_and_return_to_tfg_core | 2.5.x is methodologically closed enough; no bucket changed in 2.5.9 and 2.5.6 remains official. Robust prominence is useful diagnostically but does not change buckets in this sample. | Use WaveCount findings in the academic writeup and return focus to ENBOLSA/TFG core. | Do not turn WaveCount scoring into entries, filters, MT5, Telegram or backtests. |

## Riesgos principales

| risk | status | mitigation |
| --- | --- | --- |
| confundir WaveCount con estrategia | open_controlled | Documentar que no genera edge ni senales. |
| convertir scoring en senal | blocked | can_generate_signal=false en toda la matriz. |
| sobreajustar prominencia | controlled | 2.5.9 queda diagnostic-only; 2.5.6 no cambia. |
| rescatar conteos pequenos por metrica robusta | blocked | Robust prominence no cambia buckets. |
| extrapolar Metals sin evidencia suficiente | controlled | Metals supported with warning. |
| comparar scores entre grupos sin normalizar | controlled | Reportar por grupo y no comparar score bruto como equivalente perfecto. |
| usar ABC aislado | blocked | ABC queda experimental/contextual con padre requerido. |
| usar H1/H4 como base principal | blocked | H1/H4 queda auxiliary_only. |
| usar EWO/EMA/HTF como reglas duras | blocked | Se mantienen como soft_context. |
| llevar WaveCount a live/MT5 demasiado pronto | blocked | No live-ready; prominencia visual es offline. |
