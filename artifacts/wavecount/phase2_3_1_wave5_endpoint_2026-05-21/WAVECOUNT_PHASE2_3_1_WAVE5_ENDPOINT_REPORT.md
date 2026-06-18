# WaveCount Fase 2.3.1 - Endpoint de onda 5

Fecha: 2026-05-21

## Objetivo

Revisar si algunos impulsos de Fase 2.3 cierran la onda 5 demasiado pronto.
Esta fase no genera senales, no cambia estrategias y no modifica artifacts canonicos de benchmark.

## Diagnostico

La seleccion actual de impulsos en Fase 2.3 viene de ventanas consecutivas de seis structural pivots.
La evaluacion original solo usa esos seis pivots, por lo que es causal respecto al conteo, pero no detecta si el extremo natural de onda 5 aparece unos pivotes confirmados despues.

- candidatos diagnosticados: 42
- candidatos por escenario: {'h1_m30': 21, 'h4_d1': 21}
- estados endpoint: {'truncated_fifth_candidate': 18, 'premature_wave5_completion': 13, 'clean_or_unresolved_wave5_endpoint': 11}
- casos re-clasificados o revisados por evidencia manual: 32
- casos manuales de onda 5 usados: 6
- tiempo de ejecucion: 126.29s

## Decision Metodologica

- `candidate_impulse` limpio debe entenderse como provisional hasta que el extremo de onda 5 quede confirmado por estructura posterior suficiente.
- Si aparece un structural pivot posterior mas extremo en la misma direccion con desplazamiento material, el caso se marca como `premature_wave5_completion`.
- Si la onda 5 no supera la onda 3, el caso se separa como `truncated_fifth_candidate` o near-miss, no como impulso limpio.
- El diagnostico post-conteo usa pivotes posteriores solo para auditoria retrospectiva; una futura version live debe esperar confirmacion y exponer incertidumbre.

## Evidencia Manual

- casos manuales de quinta prematura: ['impulse_forex_audjpy_h1_minor_impulse_013', 'impulse_index_aus200_h1_minor_impulse_006', 'impulse_forex_eurjpy_m30_intermediate_impulse_005']

## Reglas Candidatas

### post_count_material_wave5_extension

- proposito: degrade clean impulse when wave 5 is followed by a materially more extreme same-direction structural pivot
- estado: implemented_as_diagnostic
- evidencia: 13
- nota anti look-ahead: uses future pivots only for retrospective diagnosis; live code must keep the count provisional until later pivots confirm the endpoint

### truncated_fifth_separation

- proposito: separate wave 5 failing to exceed wave 3 from clean impulse candidates
- estado: implemented_as_diagnostic
- evidencia: 18
- nota anti look-ahead: depends only on the six confirmed pivots used by the original window

### clean_impulse_is_provisional

- proposito: avoid treating a just-detected impulse as final or tradable
- estado: documented
- evidencia: 11
- nota anti look-ahead: keeps real-time state honest without reading future bars

## Salidas

- `tables/wave5_endpoint_diagnostics.csv`
- `tables/wave5_cases_reclassified.csv`
- `tables/wave5_rule_candidates.csv`
- `tables/manual_cases_wave5_review.csv`
- `charts/before_after/` con copias anotadas de casos clave

## Cierre

El problema de cierre prematuro es real en la muestra H1/M30 revisada manualmente.
La fase queda cerrada como diagnostico/reclasificacion aislada. El siguiente bloque natural es atacar parciales `1-2-3`, manteniendo ABC separado en la fase de fix.
