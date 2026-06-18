# WaveCount Fase 2.3.2 - Parciales 1-2-3

Fecha: 2026-05-21

## Objetivo

Diagnosticar parciales 1-2-3 demasiado laxos sin tocar ABC, grados, estrategias ni senales.

## Diagnostico

La seleccion base acepta ventanas de cuatro structural pivots alternantes. Hasta ahora no revisaba con suficiente detalle si la onda 3 desplazaba visualmente, si el parcial quedaba invalidado justo despues del 3 o si el supuesto 0 podia pertenecer a una estructura 4-5 previa.

- parciales diagnosticados: 24
- escenarios: {'h1_m30': 12, 'h4_d1': 12}
- estados: {'invalidated_after_3': 10, 'valid_partial_123': 5, 'partial_123_too_lax': 4, 'belongs_to_prior_wave_45': 3, 'partial_123_provisional': 2}
- casos manuales: 3
- casos reclasificados/alertados: 17
- tiempo de ejecucion: 31.51s

## Reglas candidatas

### wave3_must_displace_visibly

- proposito: avoid accepting 1-2-3 where wave 3 barely exceeds wave 1
- estado: implemented_as_diagnostic
- evidencia: 4
- nota anti look-ahead: uses only the four pivots already required for partial detection

### post_3_invalidates_partial

- proposito: flag partial 1-2-3 when immediate post-3 structure breaks wave 2
- estado: implemented_as_retrospective_diagnostic
- evidencia: 10
- nota anti look-ahead: post-3 pivots are future relative to partial_detected_at and only usable after latency/confirmation

### possible_prior_wave_45_context

- proposito: warn when the origin may be a higher low/high inside a prior structure instead of a fresh 0 point
- estado: implemented_as_soft_context
- evidencia: 7
- nota anti look-ahead: uses prior structural pivots only

### partial_123_is_not_signal

- proposito: keep valid partials as provisional context toward 4-5, never as execution signal
- estado: documented
- evidencia: 7
- nota anti look-ahead: live state remains provisional until later confirmation

## Cierre

Los casos 015, 017 y 018 confirman que habia parciales demasiado laxos. Esta fase no cambia la seleccion base; anade diagnostico y reclasificacion metodologica para no usarlos como ejemplos positivos sin revision.

El siguiente paso puede ser revisar calibracion de grados o pasar la misma lectura a H4/D1 antes de Fase 2.5.
