# WaveCount ABC Fix - Fase 2.3/2.4

Fecha: 2026-05-20

## Diagnostico

El fallo principal era metodologico/representacional: los `count_id` de ABC se repetian entre grados `minor`, `intermediate` y `major`.
Las galerias filtraban `count_legs` solo por `count_id`, por lo que un grafico ABC podia dibujar tres candidatos superpuestos con etiquetas `0/A/B/C` repetidas.

- problemas antes: {'legacy_count_id_matched_multiple_swing_degrees': 24}
- ABC corregidos revisados despues: 24
- ABC no listos para plot despues: 0

## Correccion

- Los `count_id` de Fase 2 ahora incluyen el grado de swing.
- El plotting de ABC filtra tambien por `swing_degree` para ser compatible con artifacts antiguos.
- Un ABC para plot debe tener exactamente cuatro puntos `0 -> A -> B -> C` en orden temporal estricto.
- ABC deja de preetiquetarse como `visually_good_abc`; queda como `ambiguous_but_interesting` hasta revision visual.
- Se anade control causal: `count_detected_at` sigue siendo el maximo `structural_detected_at` usado.

## Regeneracion

- graficos ABC Fase 2.3 corregidos: 24
- graficos ABC Fase 2.4 H4/D1 corregidos: 12
- casos problematicos/focus corregidos: 5
- tiempo de ejecucion: 283.09s

## Decision

ABC queda corregido como candidato visual/estructural, no como senal. La lectura en tiempo real sigue siendo experimental: un extremo A/B/C puede estar atras en el grafico, pero solo se conoce cuando su `structural_detected_at` lo confirma.
Antes de usar ABC para Fase 2.5 hay que revisar la galeria corregida y separar estados futuros como `abc_in_progress`, `abc_completed`, `ambiguous_correction` y `not_clean_abc`.
