# WaveCount Phase 2.3 Manual Feedback H1/M30

Fecha: 2026-05-21

## Resumen

Se incorporan las observaciones manuales del usuario sobre Fase 2.3 H1/M30.
No se cambian reglas ni se regeneran conteos. Esta fase convierte la revision
visual en evidencia metodologica para decidir ajustes futuros.

- casos revisados por el usuario: 12
- casos a degradar: 9
- casos a conservar o conservar con cautela: 3
- problemas de endpoint de onda 5: 4
- problemas de partial 1-2-3: 3
- problemas de calibracion de grado: 2

## Lectura Metodologica

La revision confirma que el motor puede encontrar estructuras utiles, pero la
muestra H1/M30 es sensible a cierres prematuros de onda 5, parciales demasiado
laxos y grados que no siempre se diferencian visualmente. Por tanto, Fase 2.3
H1/M30 debe quedar como muestra auxiliar y banco de casos, no como base unica
para reglas operativas.

## Casos A Conservar

- `impulse_forex_audjpy_h1_intermediate_impulse_009`: Esta muy bien y corrige el problema del anterior. Accion: `keep_as_good_example`.
- `near_miss_forex_audjpy_h1_intermediate_impulse_011`: Mas o menos bien; revisar regla de onda 5 que no excede onda 3. Accion: `keep_as_near_miss_not_clean_impulse`.
- `near_miss_index_aus200_h1_intermediate_impulse_008`: El usuario lo ve bien. Accion: `keep_as_ambiguous_or_near_miss_example`.

## Casos A Degradar

- `impulse_forex_audjpy_h1_minor_impulse_013`: `premature_wave5_completion`. La onda 5 termina un poco mas adelante.
- `impulse_index_aus200_h1_minor_impulse_006`: `premature_wave5_completion`. La onda 5 termina pronto.
- `impulse_index_aus200_h1_intermediate_impulse_004`: `degree_not_discriminative`. No se ve realmente diferencia respecto al anterior en la construccion de ondas.
- `impulse_forex_eurjpy_m30_intermediate_impulse_005`: `premature_wave5_completion`. La onda 5 deberia terminar en la bajada siguiente.
- `impulse_index_aus200_h1_major_impulse_002`: `degree_not_discriminative`. Es major pero no se ve diferencia clara respecto a otros grados.
- `partial_123_index_aus200_h1_intermediate_partial123_001`: `partial_123_too_lax`. No es una onda 1-2-3 valida; los parciales deben dejar continuidad coherente hacia 4-5.
- `partial_123_forex_audjpy_h1_minor_partial123_007`: `partial_123_too_lax`. Esta mal.
- `partial_123_metals_xagusd_h1_minor_partial123_002`: `structure_belongs_to_prior_wave_45`. Esta mal; parece mas bien onda 4 y 5 que 1-2-3, el 0 no empieza ahi y despues del 3 se cancelaria.
- `near_miss_metals_xagusd_h1_minor_impulse_002`: `visual_shape_invalid`. Conteo mal por la forma.

## Reglas Candidatas

- Onda 5: no cerrar impulso limpio si el extremo visual natural queda mas adelante.
- Quinta truncada: puede existir, pero debe quedar como `near_miss`,
  `truncated_fifth_candidate` o `ambiguous_count`, no como impulso limpio.
- Parcial 1-2-3: no basta con tres swings alternantes; debe haber desplazamiento
  claro de onda 3 y no invalidacion inmediata posterior.
- Grados: `major` e `intermediate` deben diferenciarse visualmente de `minor`.

## ABC

- enlaces ABC legacy detectados en el indice Fase 2.3: 12
- decision: Do not use Phase 2.3 H1/M30 ABC links as current ABC evidence; use phase2_abc_fix_2026-05-20 until corrected ABC is integrated.

## Decision

No se debe avanzar a Fase 2.5 usando H1/M30 como evidencia principal hasta
formalizar los ajustes anteriores. H4/D1 parece una base visual mas robusta
para ondas amplias, mientras H1/M30 queda como muestra auxiliar para detectar
fallos finos y calibrar reglas.
