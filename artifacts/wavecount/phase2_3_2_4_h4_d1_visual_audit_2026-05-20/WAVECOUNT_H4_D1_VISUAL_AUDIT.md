# WaveCount H4/D1 visual audit

Fecha: 2026-05-20

## Alcance

Se revisaron visualmente 54 graficos H4 de Fase 2.3 y 54 graficos H4/D1 de Fase 2.4.
La revision fue realizada por subagentes en bloques independientes y consolidada sin cambiar reglas, datos, pivotes, grados, EMAs/EWO ni estrategias.

## Resumen cuantitativo

- `phase2_3_reviewed_cases`: 54
- `phase2_4_reviewed_cases`: 54
- `user_must_review_rows`: 77
- `best_h4_examples_rows`: 22
- `phase2_3_status_visually_defensible`: 12
- `phase2_3_status_likely_false_candidate`: 11
- `phase2_3_status_excellent_example`: 10
- `phase2_3_status_hard_invalid_correct`: 9
- `phase2_3_status_ambiguous`: 8
- `phase2_3_status_plausible_but_needs_review`: 3
- `phase2_3_status_visually_forced`: 1
- `phase2_3_degree_minor`: 18
- `phase2_3_degree_intermediate`: 18
- `phase2_3_degree_major`: 18
- `phase2_3_category_impulse`: 12
- `phase2_3_category_partial_123`: 12
- `phase2_3_category_abc`: 12
- `phase2_3_category_near_miss`: 9
- `phase2_3_category_hard_invalid`: 9
- `phase2_4_d1_useful`: 27
- `phase2_4_d1_partially_useful`: 13
- `phase2_4_d1_conflict_explains_case`: 11
- `phase2_4_d1_conflict_suspicious`: 3
- `phase2_4_change_misleading_if_used_as_filter`: 12
- `phase2_4_change_flags_transition`: 11
- `phase2_4_change_confirms`: 10
- `phase2_4_change_downgrades_confidence`: 9
- `phase2_4_change_improves_confidence`: 5
- `phase2_4_change_reframes_as_correction`: 5
- `phase2_4_change_no_change`: 2

## Lectura metodologica

- H4 mejora claramente la lectura visual de impulsos y parciales `1-2-3` frente a M30/H1.
- `intermediate` y algunos `major` son los grados mas utiles para H4; `minor` puede funcionar, pero con mas riesgo de microestructura.
- Los ABC siguen siendo la parte mas debil: aparecen solapes, multiples rutas y etiquetas que fuerzan tendencia como correccion.
- D1/EMAs/EWO ayudan como contexto blando, especialmente para confirmar impulsos alcistas o detectar correcciones contra D1.
- El contexto no debe rescatar conteos visualmente malos ni hard invalidations.

## Mejores ejemplos candidatos

- `phase2_3_h4_count_only` order 002 `impulse_metals_xagusd_h4_minor_impulse_001`: Clean bullish 0-5 sequence with visible retracements and good Elliott readability.
- `phase2_3_h4_count_only` order 004 `impulse_forex_eurjpy_h4_minor_impulse_022`: Natural bullish five-wave structure before the later selloff.
- `phase2_3_h4_count_only` order 006 `impulse_metals_xagusd_h4_intermediate_impulse_007`: Strong broad bullish 1-2-3-4-5; one of the cleanest intermediate examples.
- `phase2_3_h4_count_only` order 008 `impulse_forex_eurusd_h4_intermediate_impulse_012`: Very clean bullish advance from a low, with five recognizable H4 legs.
- `phase2_3_h4_count_only` order 012 `impulse_forex_gbpusd_h4_major_impulse_012`: Good major bearish impulse with strong wave 3 and natural extended fifth.
- `phase2_3_h4_count_only` order 014 `partial_123_metals_xagusd_h4_intermediate_partial123_001`: Good bullish 1-2-3 launch on XAGUSD, natural as intermediate start.
- `phase2_3_h4_count_only` order 016 `partial_123_forex_audjpy_h4_intermediate_partial123_005`: Clean and proportional bullish 1-2-3; fits the later H4 trend.
- `phase2_3_h4_count_only` order 020 `partial_123_forex_audjpy_h4_minor_partial123_005`: Clean bullish sequence; wave 2 corrects without breaking and wave 3 extends naturally.
- `phase2_3_h4_count_only` order 021 `partial_123_forex_audjpy_h4_major_partial123_003`: Very good major 0-1-2-3; proportions, pivots and continuation fit well.
- `phase2_3_h4_count_only` order 024 `partial_123_forex_audjpy_h4_major_partial123_005`: Very clear major structure; waves 1, 2 and 3 respect an impulsive read.
- `phase2_3_h4_count_only` order 048 `hard_invalid_index_aus200_h4_intermediate_impulse_001`: Very clean hard invalid with origin-area breaks and oversized final leg.
- `phase2_3_h4_count_only` order 053 `hard_invalid_metals_xagusd_h4_major_impulse_001`: Textbook hard invalid: wave 3 cannot exceed wave 1 and wave 5 dominates.
- `phase2_4_h4_d1_context` order 002 `impulse_metals_xagusd_h4_minor_impulse_001`: Clean early bullish sequence inside aligned D1 trend with constructive EWO.
- `phase2_4_h4_d1_context` order 006 `impulse_metals_xagusd_h4_intermediate_impulse_007`: Strong aligned bullish impulse with rising EMAs and positive EWO.
- `phase2_4_h4_d1_context` order 010 `impulse_metals_xpdusd_h4_major_impulse_001`: Aligned bullish major impulse with supportive EMAs and EWO.
- `phase2_4_h4_d1_context` order 014 `partial_123_metals_xagusd_h4_intermediate_partial123_001`: Aligned bullish 1-2-3 early in a strong trend, supported by EMAs and EWO.
- `phase2_4_h4_d1_context` order 016 `partial_123_forex_audjpy_h4_intermediate_partial123_005`: Bullish partial aligns with D1 and EWO supports developing impulse.
- `phase2_4_h4_d1_context` order 018 `partial_123_metals_xagusd_h4_minor_partial123_001`: Minor bullish partial is consistent with D1 alignment, rising EMAs and positive EWO.
- `phase2_4_h4_d1_context` order 020 `partial_123_forex_audjpy_h4_minor_partial123_005`: Clean bullish launch; D1, EMAs and EWO confirm the phase 2.3 reading.
- `phase2_4_h4_d1_context` order 021 `partial_123_forex_audjpy_h4_major_partial123_003`: Major bullish 0-1-2-3 reads naturally; EWO supports momentum but is less decisive than D1/EMAs.
- `phase2_4_h4_d1_context` order 024 `partial_123_forex_audjpy_h4_major_partial123_005`: Strong bullish partial with wave 2 near EMA support and wave 3 into clear impulse.
- `phase2_4_h4_d1_context` order 043 `near_miss_forex_audjpy_h4_major_impulse_005`: Major near-miss is visually clean and coherent with D1/EMAs/EWO.

## Decision

H4/D1 es una base visual mas prometedora para WaveCount que M30/H1, sobre todo para impulsos y parciales.
Aun no conviene avanzar a Fase 2.5 hasta revisar los casos marcados en `user_must_review_h4_d1.csv`, especialmente ABC y hard invalidations con contexto D1 favorable.
