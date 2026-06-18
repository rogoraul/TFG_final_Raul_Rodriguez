# WaveCount compressed visual reaudit

Fecha: 2026-05-19

## Alcance

Se revisaron con subagentes los 54 graficos comprimidos de Fase 2.3 y los 54 graficos comprimidos de Fase 2.4.
Fase 2.3 evalua conteo visual sin indicadores. Fase 2.4 evalua si EMAs 50/150, EWO 5-35 y HTF/LTF ayudan o contradicen.

No se cambiaron reglas, datos, pivotes, grados, EMAs/EWO, estrategias ni backtests.

## Resultados

- `phase2_3_reviewed_cases`: 54
- `phase2_4_reviewed_cases`: 54
- `phase2_3_user_review_cases`: 31
- `phase2_4_user_review_cases`: 26
- `combined_user_review_rows`: 57
- `best_example_rows`: 11
- `phase2_3_status_excellent_example`: 13
- `phase2_3_status_visually_defensible`: 13
- `phase2_3_status_hard_invalid_correct`: 9
- `phase2_3_status_plausible_but_needs_review`: 8
- `phase2_3_status_ambiguous`: 4
- `phase2_3_status_visually_forced`: 3
- `phase2_3_status_too_coarse`: 2
- `phase2_3_status_likely_false_candidate`: 1
- `phase2_3_status_too_micro`: 1
- `phase2_4_status_context_confirms`: 14
- `phase2_4_status_context_explains_ambiguity`: 13
- `phase2_4_status_context_conflicts_but_useful`: 10
- `phase2_4_status_context_partially_supports`: 9
- `phase2_4_status_context_conflict_suspicious`: 4
- `phase2_4_status_context_misleading`: 4

## Mejores ejemplos propuestos

- `phase2_3_count_only` order 4 `impulse_forex_audjpy_h1_minor_impulse_015`: best clean bullish impulse without indicators
- `phase2_3_count_only` order 6 `impulse_metals_xauusd_h1_intermediate_impulse_013`: clean bearish intermediate impulse without indicators
- `phase2_3_count_only` order 9 `impulse_metals_xagusd_h1_major_impulse_009`: clean major bearish impulse without indicators
- `phase2_3_count_only` order 14 `partial_123_metals_xagusd_h1_intermediate_partial123_003`: clean bearish partial 1-2-3 without indicators
- `phase2_3_count_only` order 23 `partial_123_index_aus200_h1_major_partial123_002`: clean major bearish partial 1-2-3 without indicators
- `phase2_3_count_only` order 24 `partial_123_forex_eurusd_h1_major_partial123_002`: clean EURUSD major bearish partial 1-2-3 without indicators
- `phase2_4_context` order 8 `impulse_forex_eurjpy_m30_intermediate_impulse_005`: best context-confirmed bearish impulse with EMA/EWO/HTF
- `phase2_4_context` order 13 `partial_123_forex_audjpy_h1_intermediate_partial123_009`: clean context-confirmed bullish partial 1-2-3
- `phase2_4_context` order 20 `partial_123_forex_audjpy_h1_minor_partial123_013`: very clear context-confirmed bullish minor partial 1-2-3
- `phase2_4_context` order 24 `partial_123_forex_eurusd_h1_major_partial123_002`: clean context-confirmed bearish partial 1-2-3
- `phase2_4_context` order 43 `near_miss_forex_audjpy_h1_major_impulse_007`: best near-miss showing context supports direction without rescuing truncation

## Casos que debe revisar el usuario

`user_must_review_compressed.csv` contiene 57 filas priorizadas.
Prioridad practica: revisar primero high, despues medium. En Fase 2.3 revisar conteo puro; en Fase 2.4 revisar si contexto cambia la lectura.

## Decision

La Fase 2.3 comprimida debe revisarse primero. Los mejores ejemplos positivos salen de impulsos y parciales 1-2-3; los ABC siguen necesitando graficos aislados porque las etiquetas se solapan.
La Fase 2.4 comprimida confirma que EMAs/EWO/HTF son utiles como contexto blando, pero no deben rescatar conteos visualmente malos o invalidaciones duras.
