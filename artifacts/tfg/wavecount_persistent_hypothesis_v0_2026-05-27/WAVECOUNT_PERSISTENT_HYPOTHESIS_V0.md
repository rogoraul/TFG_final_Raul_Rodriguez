# WaveCount Persistent Hypothesis v0

Fecha: 2026-05-27

## Decision

Decision: `persistent_hypothesis_v0_needs_more_review`.

Esta fase redisenia `current_wave_hypothesis_v0` sin tocar SQL real ni
operativa. La idea es que una onda actual no dependa solo del numero de pivotes
del ultimo corte: primero se registran pivotes causales, luego se exige
persistencia entre cortes y por ultimo se madura la hipotesis de onda por
eventos.

No es backtest, no mide rentabilidad, no genera senales, no filtra ENBOLSA y no
conecta MT5.

## Hipotesis Latest Por Activo

| symbol | timeframe | estimated_current_wave | confirmed_wave_context | freshness_status | wave_stability_status | display_policy | persistent_pivot_count | candidate_pivot_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | possible_wave5_active | possible_wave5_active | fresh_estimate | provisional | show_with_warning | 10 | 1 |
| GBPUSD.r | H4 | possible_wave5_active | possible_wave5_active | fresh_estimate | provisional | show_with_warning | 8 | 2 |
| US500 | H4 | possible_wave5_active | possible_wave5_active | fresh_estimate | provisional | show_with_warning | 14 | 1 |
| XAUUSD.r | H4 | possible_wave5_active | possible_wave5_active | fresh_estimate | provisional | show_with_warning | 7 | 2 |

## Comparacion Contra Current Wave Hypothesis v0

| symbol | timeframe | current_wave_hypothesis_estimated | persistent_estimated_current_wave | current_display_policy | persistent_display_policy | current_confirmed_context | persistent_confirmed_context | comparison_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | ambiguous | possible_wave5_active | manual_review_only | show_with_warning | ambiguous | possible_wave5_active | persistent_model_less_restrictive |
| GBPUSD.r | H4 | ambiguous | possible_wave5_active | manual_review_only | show_with_warning | ambiguous | possible_wave5_active | persistent_model_less_restrictive |
| US500 | H4 | ambiguous | possible_wave5_active | manual_review_only | show_with_warning | ambiguous | possible_wave5_active | persistent_model_less_restrictive |
| XAUUSD.r | H4 | ambiguous | possible_wave5_active | manual_review_only | show_with_warning | ambiguous | possible_wave5_active | persistent_model_less_restrictive |

## Resumen De Pivotes

| symbol | pivot_role | count |
| --- | --- | --- |
| EURUSD.r | candidate_pivot | 1 |
| EURUSD.r | persistent_pivot | 10 |
| EURUSD.r | rejected_pivot | 6 |
| GBPUSD.r | candidate_pivot | 2 |
| GBPUSD.r | persistent_pivot | 8 |
| GBPUSD.r | rejected_pivot | 5 |
| US500 | candidate_pivot | 1 |
| US500 | persistent_pivot | 14 |
| US500 | rejected_pivot | 2 |
| XAUUSD.r | candidate_pivot | 2 |
| XAUUSD.r | persistent_pivot | 7 |
| XAUUSD.r | rejected_pivot | 4 |

## Contrato De Display

| display_policy | meaning | bot_allowed |
| --- | --- | --- |
| displayable_in_dashboard | Persistent wave context is stable enough to show as read-only context. | False |
| show_with_warning | Useful but provisional, late or candidate-driven. | False |
| manual_review_only | Ambiguous or unstable; only manual study views. | False |
| not_displayable | Insufficient context. | False |

## Riesgos

| severity | risk | description | recommendation |
| --- | --- | --- | --- |
| info | lookahead_guard | Anti look-ahead checks passed. | Keep as hard guardrail. |
| low | manual_review_latest | 0 latest hypotheses remain manual_review_only. | Do not show as clean dashboard context. |
| info | warning_display_latest | 4 latest hypotheses can be shown only with warning. | Keep warning badges and no bot access. |
| info | displayable_latest | 0 latest hypotheses are displayable read-only context. | Require visual review before dashboard. |
| medium | wave5_dominance | 4 latest hypotheses are wave5/completed-style states. | Treat as suspicious until visual review confirms the persistent cycle framing. |
| info | persistent_pivots | 39 pivots reached persistence. | If low, adjust persistence/event semantics before dashboard. |

## Interpretacion

- `candidate_pivot` y `provisional_pivot` pueden orientar una estimacion, pero
  no cuentan como pivotes persistentes.
- `persistent_pivot` requiere sobrevivir al menos 2
  cortes.
- `completed_impulse_candidate` no se declara por simple cantidad de pivotes.
- Si hay supersedencias recientes o alternancia rota, la hipotesis queda
  `ambiguous`/`manual_review_only`.
- Cualquier fila mantiene `can_generate_signal=false`, `can_filter_trade=false`
  y `can_execute_order=false`.

## Pendiente Antes De SQL/Dashboard

- Revision visual de los casos que queden `show_with_warning` o
  `displayable_in_dashboard`.
- Ajustar, si procede, los umbrales de persistencia sin usar PnL.
- Si sigue predominando `manual_review_only`, valorar una maquina de estados
  mas profunda o limitar WaveCount a pestana manual.
