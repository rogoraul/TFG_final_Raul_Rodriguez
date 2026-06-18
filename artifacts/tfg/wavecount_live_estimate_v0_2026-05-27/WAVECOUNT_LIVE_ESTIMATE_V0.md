# WaveCount Live Estimate v0

Fecha: 2026-05-27

## Decision

Decision: `live_estimate_v0_promising_for_visual_review`.

Esta fase cambia el enfoque: no intenta confirmar en vivo un conteo perfecto,
sino emitir una hipotesis viva, provisional y auditable usando el ultimo cierre
y el tramo actual desde el ultimo pivote persistente.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Diferencia Frente A State Machine

- `confirmed_wave_context` conserva el contexto confirmado/tardio.
- `live_estimated_wave` usa ultimo cierre y tramo actual.
- Cada etiqueta incluye `why_this_label` y `why_not_higher_confidence`.
- La salida puede ser visible solo como contexto provisional, nunca como senal.

## Resumen Por Activo

| symbol | timeframe | confirmed_wave_context | live_estimated_wave | current_leg_status | confidence_bucket | freshness_status | display_policy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | invalidated | invalidated | failed_breakout | low | manual_review_required | manual_review_only |
| GBPUSD.r | H4 | invalidated | invalidated | failed_breakout | low | manual_review_required | manual_review_only |
| US500 | H4 | possible_wave3_active_late | possible_wave3_active | impulse_attempt | medium | live_estimate_from_close | show_live_estimate_with_warning |
| XAUUSD.r | H4 | possible_wave3_candidate_late | possible_wave3_candidate | breakout_attempt | low | live_estimate_from_close | show_live_estimate_with_warning |

## Tramo Actual

| symbol | timeframe | as_of_bar_time | current_leg_direction | current_leg_status | last_persistent_pivot_type | last_persistent_pivot_price | last_persistent_pivot_time | latest_close | latest_close_time | move_from_last_pivot_pct | retracement_from_previous_leg_pct | lookahead_safe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | 2026-03-17T04:00:00 | down | failed_breakout | high | 1.20816 | 2026-01-27T20:00:00 | 1.1497 | 2026-03-17T04:00:00 | -4.8388 | 114.8301 | True |
| GBPUSD.r | H4 | 2026-03-17T04:00:00 | down | failed_breakout | high | 1.38661 | 2026-01-27T20:00:00 | 1.33114 | 2026-03-17T04:00:00 | -4.0004 | 104.3061 | True |
| US500 | H4 | 2026-03-17T04:00:00 | down | impulse_attempt | high | 6995.45 | 2026-02-11T16:00:00 | 6691.47 | 2026-03-17T04:00:00 | -4.3454 | 116.3649 | True |
| XAUUSD.r | H4 | 2026-03-17T04:00:00 | up | breakout_attempt | low | 4840.27 | 2026-02-17T16:00:00 | 5037.85 | 2026-03-17T04:00:00 | 4.082 | 26.1135 | True |

## Reglas Aplicadas

| symbol | timeframe | state_machine_wave | live_estimated_wave | activation_crossed | invalidated | rule_applied | why_this_label | why_not_higher_confidence | lookahead_safe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | invalidated | invalidated | False | True | invalidation_guard | latest close breached invalidation or state machine invalidated the cycle | invalidated contexts cannot receive higher confidence | True |
| GBPUSD.r | H4 | invalidated | invalidated | False | True | invalidation_guard | latest close breached invalidation or state machine invalidated the cycle | invalidated contexts cannot receive higher confidence | True |
| US500 | H4 | possible_wave3_active | possible_wave3_active | True | False | activation_crossed_live_estimate | latest close crossed activation in the inferred cycle direction | confirmed context is still late and this is not an operational signal | True |
| XAUUSD.r | H4 | possible_wave3_candidate | possible_wave3_candidate | False | False | activation_pending_candidate | latest close has not crossed activation but keeps a plausible wave3 attempt alive | activation is not crossed; confidence remains low | True |

## Confianza Y Warnings

| symbol | timeframe | live_estimated_wave | confidence_bucket | freshness_status | display_policy | requires_manual_review | warning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | invalidated | low | manual_review_required | manual_review_only | True | invalidated contexts cannot receive higher confidence |
| GBPUSD.r | H4 | invalidated | low | manual_review_required | manual_review_only | True | invalidated contexts cannot receive higher confidence |
| US500 | H4 | possible_wave3_active | medium | live_estimate_from_close | show_live_estimate_with_warning | False | confirmed context is still late and this is not an operational signal |
| XAUUSD.r | H4 | possible_wave3_candidate | low | live_estimate_from_close | show_live_estimate_with_warning | False | activation is not crossed; confidence remains low |

## Comparacion Contra State Machine

| symbol | timeframe | state_machine_wave | live_estimated_wave | state_machine_display_policy | live_display_policy | state_machine_confirmed_context | confirmed_wave_context | changed_label | comparison_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | invalidated | invalidated | manual_review_only | manual_review_only | invalidated | invalidated | False | live_estimate_keeps_invalidation |
| GBPUSD.r | H4 | invalidated | invalidated | manual_review_only | manual_review_only | invalidated | invalidated | False | live_estimate_keeps_invalidation |
| US500 | H4 | possible_wave3_active | possible_wave3_active | show_with_warning | show_live_estimate_with_warning | possible_wave3_active_late | possible_wave3_active_late | False | latest_close_adds_live_estimate |
| XAUUSD.r | H4 | possible_wave3_candidate | possible_wave3_candidate | show_with_warning | show_live_estimate_with_warning | possible_wave3_candidate_late | possible_wave3_candidate_late | False | latest_close_adds_live_estimate |

## Riesgos

| severity | risk | description | recommendation |
| --- | --- | --- | --- |
| info | lookahead_guard | All rows use latest close <= as_of_bar_time. | Keep as hard guardrail. |
| medium | manual_review_only | 2 rows require manual review. | Do not show manual rows as live wave context. |
| medium | provisional_live_estimate | 2 rows are provisional live estimates. | Show only with warning; never use as signal/filter. |
| medium | low_confidence | 3 rows have low confidence. | Keep why_not_higher_confidence visible. |

## Lectura

- La capa genera hipotesis vivas por activo cuando hay ultimo cierre causal.
- Las hipotesis son provisionales y read-only.
- No hay Telegram, bot, filtro ni orden.
- Antes de SQL/dashboard hace falta una auditoria visual de las etiquetas vivas.
