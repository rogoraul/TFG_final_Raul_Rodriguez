# WaveCount Fase 2.3.1 - Ajuste de interpretacion

Fecha: 2026-05-21

Esta actualizacion no cambia reglas, pivotes, conteos ni estrategias. Solo corrige la lectura metodologica del diagnostico de endpoint de onda 5.

## Decision

`premature_wave5_completion` no significa automaticamente conteo malo. Debe leerse como incertidumbre de endpoint, provisionalidad o posible subestructura de grado superior.

## Casos revisados

### impulse_forex_audjpy_h1_minor_impulse_013

- interpretacion: Se ve bien como conteo local. La onda 5 podria terminar algo mas arriba, y las cinco ondas podrian ser una onda 1 mayor o parte de una 1-2-3 mayor.
- etiqueta metodologica final: `candidate_impulse_provisional_with_endpoint_uncertainty`
- posible subonda de grado mayor: True
- accion: `keep_as_local_example_with_higher_degree_note`

### impulse_index_aus200_h1_minor_impulse_006

- interpretacion: Podria estar bien como minor. Visualmente tambien encaja como onda 1-2 y arranque de una tercera mayor; no debe tratarse como conteo malo automaticamente.
- etiqueta metodologica final: `possible_higher_degree_subwave`
- posible subonda de grado mayor: True
- accion: `keep_as_ambiguous_higher_degree_example`

### impulse_forex_audjpy_h1_intermediate_impulse_009

- interpretacion: Esta bien y debe mantenerse como buen ejemplo.
- etiqueta metodologica final: `candidate_impulse_provisional_good_example`
- posible subonda de grado mayor: False
- accion: `keep_as_good_example`

### impulse_forex_eurjpy_m30_intermediate_impulse_005

- interpretacion: Se ve bien. Puede considerarse que la onda 5 termina ahi o que recoge toda la bajada; no debe penalizarse agresivamente.
- etiqueta metodologica final: `candidate_impulse_provisional_with_endpoint_uncertainty`
- posible subonda de grado mayor: True
- accion: `keep_as_valid_but_provisional`

### near_miss_forex_audjpy_h1_intermediate_impulse_011

- interpretacion: Visualmente gusta. Puede no exceder onda 3 porque el grafico se corta; no debe etiquetarse como truncamiento definitivo sin esa limitacion.
- etiqueta metodologica final: `near_miss_with_window_cut_uncertainty`
- posible subonda de grado mayor: True
- accion: `keep_as_near_miss_with_limitation`

### near_miss_index_aus200_h1_intermediate_impulse_008

- interpretacion: Esta bien / aceptable como near-miss.
- etiqueta metodologica final: `acceptable_near_miss`
- posible subonda de grado mayor: False
- accion: `keep_as_near_miss_example`

## Regla de lectura

La fase queda como capa de incertidumbre sobre endpoint de onda 5, no como detector agresivo de conteos malos. Los conteos visualmente validos pueden mantenerse como ejemplos locales/provisionales aunque el endpoint sea incierto.
