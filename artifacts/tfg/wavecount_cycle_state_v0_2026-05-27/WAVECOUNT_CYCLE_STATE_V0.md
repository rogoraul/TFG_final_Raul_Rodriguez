# WaveCount Cycle State v0

Fecha: 2026-05-27

## Decision

Decision: `cycle_state_v0_promising_for_visual_review`.

Esta fase introduce segmentacion de ciclo/reset para evitar que los pivotes
persistentes se acumulen indefinidamente hasta convertir todos los activos en
`possible_wave5_active`.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Por Que Se Introduce Ciclo/Reset

`wavecount_persistent_hypothesis_v0` resolvio parte de la ambiguedad inicial,
pero arrastro demasiados pivotes persistentes dentro de una unica secuencia. El
resultado fue una dominancia artificial de onda 5: 4/4 activos H4 terminaron
como `possible_wave5_active/show_with_warning`.

`wavecount_cycle_state_v0` no intenta demostrar que exista una onda 3 real. Su
objetivo es mas acotado: separar pivotes heredados de pivotes del ciclo actual
para que una lectura viva no madure por acumulacion historica indefinida.

## Reglas De Reset V0

- Si un activo acumula mas de 6 pivotes persistentes,
  los pivotes antiguos pasan a `previous_cycle_id`.
- El ciclo actual se reevalua con la cola reciente de
  3 pivotes persistentes.
- El estado queda `reset_candidate` y `show_with_warning`, no aprobado para
  uso operativo.
- La salida mantiene flags fail-closed:
  `can_generate_signal=false`, `can_filter_trade=false`,
  `can_execute_order=false`.
- La regla es deliberadamente simple y necesita revision visual posterior.

## Hipotesis Por Activo

| symbol | timeframe | cycle_status | cycle_family | cycle_pivot_count | estimated_current_wave | display_policy | cycle_reset_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | reset_candidate | impulse | 3 | possible_wave3_active | show_with_warning | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle |
| GBPUSD.r | H4 | reset_candidate | impulse | 3 | possible_wave3_active | show_with_warning | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle |
| US500 | H4 | reset_candidate | impulse | 3 | possible_wave3_candidate | show_with_warning | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle |
| XAUUSD.r | H4 | reset_candidate | impulse | 3 | possible_wave3_candidate | show_with_warning | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle |

## Resets

| symbol | timeframe | as_of_bar_time | previous_cycle_id | new_cycle_id | total_persistent_pivots | current_cycle_pivots | reset_reason | lookahead_safe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | 2026-03-17T04:00:00 | cycle_EURUSD_r_H4_previous_2025_08_27T12_00_00_2025_11_21T16_00_00 | cycle_EURUSD_r_H4_current_2025_12_24T04_00_00_2026_01_27T20_00_00 | 10 | 3 | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle | True |
| GBPUSD.r | H4 | 2026-03-17T04:00:00 | cycle_GBPUSD_r_H4_previous_2025_09_03T08_00_00_2025_11_20T04_00_00 | cycle_GBPUSD_r_H4_current_2026_01_06T08_00_00_2026_01_27T20_00_00 | 8 | 3 | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle | True |
| US500 | H4 | 2026-03-17T04:00:00 | cycle_US500_H4_previous_2025_08_20T16_00_00_2026_01_21T12_00_00 | cycle_US500_H4_current_2026_01_28T08_00_00_2026_02_11T16_00_00 | 14 | 3 | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle | True |
| XAUUSD.r | H4 | 2026-03-17T04:00:00 | cycle_XAUUSD_r_H4_previous_2025_08_20T04_00_00_2025_11_13T12_00_00 | cycle_XAUUSD_r_H4_current_2025_11_21T08_00_00_2026_02_17T16_00_00 | 7 | 3 | total_persistent_pivots_gt_6;cycle_tail_re_evaluated;old_pivots_moved_to_previous_cycle | True |

## Comparacion Contra Persistent Hypothesis

| symbol | timeframe | persistent_estimated_current_wave | cycle_estimated_current_wave | persistent_display_policy | cycle_display_policy | persistent_pivot_count | cycle_pivot_count | cycle_status | wave5_reduced | comparison_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | possible_wave5_active | possible_wave3_active | show_with_warning | show_with_warning | 10 | 3 | reset_candidate | True | cycle_reset_reduced_wave5 |
| GBPUSD.r | H4 | possible_wave5_active | possible_wave3_active | show_with_warning | show_with_warning | 8 | 3 | reset_candidate | True | cycle_reset_reduced_wave5 |
| US500 | H4 | possible_wave5_active | possible_wave3_candidate | show_with_warning | show_with_warning | 14 | 3 | reset_candidate | True | cycle_reset_reduced_wave5 |
| XAUUSD.r | H4 | possible_wave5_active | possible_wave3_candidate | show_with_warning | show_with_warning | 7 | 3 | reset_candidate | True | cycle_reset_reduced_wave5 |

## Maquina De Estados

| symbol | timeframe | as_of_bar_time | from_state | to_state | event | reason | pivot_uid | lookahead_safe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_forming_wave1 | cycle_reset_applied | current_cycle_tail_after_reset | EURUSD_r_H4_high_2025_12_24T04_00_00_1_18079 | True |
| EURUSD.r | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_possible_wave2 | pivot_accepted | persistent_pivot_matures_state | EURUSD_r_H4_low_2026_01_19T00_00_00_1_15725 | True |
| EURUSD.r | H4 | 2026-03-17T04:00:00 | cycle_possible_wave2 | cycle_possible_wave3_active | pivot_accepted | persistent_pivot_matures_state | EURUSD_r_H4_high_2026_01_27T20_00_00_1_20816 | True |
| GBPUSD.r | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_forming_wave1 | cycle_reset_applied | current_cycle_tail_after_reset | GBPUSD_r_H4_high_2026_01_06T08_00_00_1_35675 | True |
| GBPUSD.r | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_possible_wave2 | pivot_accepted | persistent_pivot_matures_state | GBPUSD_r_H4_low_2026_01_19T00_00_00_1_33343 | True |
| GBPUSD.r | H4 | 2026-03-17T04:00:00 | cycle_possible_wave2 | cycle_possible_wave3_active | pivot_accepted | persistent_pivot_matures_state | GBPUSD_r_H4_high_2026_01_27T20_00_00_1_38661 | True |
| US500 | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_forming_wave1 | cycle_reset_applied | current_cycle_tail_after_reset | US500_H4_high_2026_01_28T08_00_00_7017_68 | True |
| US500 | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_possible_wave2 | pivot_accepted | persistent_pivot_matures_state | US500_H4_low_2026_02_06T00_00_00_6734_22 | True |
| US500 | H4 | 2026-03-17T04:00:00 | cycle_possible_wave2 | cycle_possible_wave3_candidate | pivot_accepted | persistent_pivot_matures_state | US500_H4_high_2026_02_11T16_00_00_6995_45 | True |
| XAUUSD.r | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_forming_wave1 | cycle_reset_applied | current_cycle_tail_after_reset | XAUUSD_r_H4_low_2025_11_21T08_00_00_4022_51 | True |
| XAUUSD.r | H4 | 2026-03-17T04:00:00 | cycle_forming_wave1 | cycle_possible_wave2 | pivot_accepted | persistent_pivot_matures_state | XAUUSD_r_H4_high_2026_01_29T00_00_00_5596_89 | True |
| XAUUSD.r | H4 | 2026-03-17T04:00:00 | cycle_possible_wave2 | cycle_possible_wave3_candidate | pivot_accepted | persistent_pivot_matures_state | XAUUSD_r_H4_low_2026_02_17T16_00_00_4840_27 | True |

## Riesgos

| severity | risk | description | recommendation |
| --- | --- | --- | --- |
| info | lookahead_guard | Anti look-ahead checks passed. | Keep as hard guardrail. |
| info | cycle_resets | 4 cycle reset candidates generated. | Review visually before dashboard. |
| low | remaining_wave5 | 0 latest rows remain wave5/completed-style states. | Do not advance if wave5 dominance remains. |
| low | ambiguous_cycle_state | 0 latest rows are ambiguous. | If dominant, design deeper state machine. |

## Interpretacion

- La dominancia `possible_wave5_active` baja en la comparacion contra el modelo
  persistente, pero esto no prueba que los nuevos estados sean correctos.
- Los estados `possible_wave3_active` y `possible_wave3_candidate` son hipotesis
  de ciclo actual, no senales ENBOLSA, no filtros RiskGuard y no ordenes.
- La capa sigue bloqueada para SQL/dashboard hasta una auditoria visual de
  ciclos/reset.
- Si la revision visual detecta resets falsos o ondas 3 artificiales, el
  siguiente paso seria una maquina de estados de onda mas profunda.
