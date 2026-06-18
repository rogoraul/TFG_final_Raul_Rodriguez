# WaveCount Live Estimate Visual Audit

Fecha: 2026-05-27

## Decision

Decision: `live_estimate_study_panel_only`.

Esta auditoria revisa si `wavecount_live_estimate_v0` mejora la lectura viva de
onda por activo sin convertir WaveCount en senal, filtro o ejecucion. No se toca
SQL real, no se implementa dashboard, no se generan senales, no se ejecutan
backtests y no se conecta MT5.

## Contrato Y Seguridad

| check_name | status | observed | severity |
| --- | --- | --- | --- |
| csv_json_row_count_match | pass | csv=4;json=4 | info |
| expected_columns_present | pass | all expected columns present | info |
| payload_json_valid | pass | True | info |
| why_this_label_present | pass | non-empty why_this_label | info |
| why_not_higher_confidence_present | pass | non-empty why_not_higher_confidence | info |
| lookahead_safe_all_true | pass | True | info |
| latest_close_not_after_as_of | pass | True | info |
| hard_flag_is_read_only | pass | True | info |
| hard_flag_can_generate_signal | pass | True | info |
| hard_flag_can_filter_trade | pass | True | info |
| hard_flag_can_execute_order | pass | True | info |
| run_meta_real_sql_executed | pass | False | info |
| run_meta_ddl_executed | pass | False | info |
| run_meta_mt5_connected | pass | False | info |
| run_meta_backtests_executed | pass | False | info |
| run_meta_signals_generated | pass | False | info |
| run_meta_dashboard_implemented | pass | False | info |
| run_meta_telegram_implemented | pass | False | info |
| run_meta_bot_implemented | pass | False | info |

## Auditoria Visual

| symbol | timeframe | chart_file | live_estimated_wave | confirmed_wave_context | current_leg_status | visual_readability | label_plausible | activation_level_plausible | invalidation_level_plausible | display_policy_ok | manual_notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | artifacts\tfg\wavecount_live_estimate_v0_2026-05-27\charts\live_estimate_EURUSD_r_H4.png | invalidated | invalidated | failed_breakout | readable | true | true | true | true | Latest close is beyond the invalidation level for the stale long context; manual-only is appropriate. Future wording should distinguish invalidated_old_context from a fresh bearish wave. |
| GBPUSD.r | H4 | artifacts\tfg\wavecount_live_estimate_v0_2026-05-27\charts\live_estimate_GBPUSD_r_H4.png | invalidated | invalidated | failed_breakout | readable | true | true | true | true | Latest close is beyond the invalidation level for the stale long context; manual-only is appropriate. Future wording should distinguish invalidated_old_context from a fresh bearish wave. |
| US500 | H4 | artifacts\tfg\wavecount_live_estimate_v0_2026-05-27\charts\live_estimate_US500_H4.png | possible_wave3_active | possible_wave3_active_late | impulse_attempt | readable | true | true | true | true | Short live leg is visually legible and latest close is below activation. Plausible as possible_wave3_active, but only as study-panel context because the confirmed cycle is late. |
| XAUUSD.r | H4 | artifacts\tfg\wavecount_live_estimate_v0_2026-05-27\charts\live_estimate_XAUUSD_r_H4.png | possible_wave3_candidate | possible_wave3_candidate_late | breakout_attempt | borderline | unclear | true | true | true | Bounce from the last low is visible, but activation is still far away. possible_wave3_candidate is acceptable only as low-confidence study context, not as a strong current-wave label. |

## US500

| symbol | timeframe | live_estimated_wave | latest_close | activation_level | activation_crossed | current_leg_direction | current_leg_status | confirmed_wave_context | visual_label_plausible | could_be_plain_down_leg | should_keep_active | should_downgrade_to_candidate | should_manual_review_only | recommendation | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US500 | H4 | possible_wave3_active | 6691.47 | 6734.22 | True | down | impulse_attempt | possible_wave3_active_late | true | True | True | False | False | Keep possible_wave3_active as provisional study-panel label; do not show as fresh main-dashboard current wave. | Latest close is clearly below activation for a short context and the leg is visually coherent, but late_cycle_context remains the limiting caveat. |

## XAUUSD.r

| symbol | timeframe | live_estimated_wave | latest_close | activation_level | activation_crossed | distance_to_activation_pct | current_leg_direction | current_leg_status | confirmed_wave_context | visual_label_plausible | could_be_noise_or_range | should_keep_candidate | should_downgrade_to_ambiguous | should_manual_review_only | recommendation | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| XAUUSD.r | H4 | possible_wave3_candidate | 5037.85 | 5596.89 | False | 9.988404 | up | breakout_attempt | possible_wave3_candidate_late | unclear | True | True | False | False | Keep possible_wave3_candidate only as low-confidence study-panel context. | Latest close has not crossed activation and the chart is borderline, but the bounce from the last persistent low is visible and invalidation is not breached. |

## Contextos Invalidados

| symbol | timeframe | latest_close | invalidation_level | direction | invalidation_breached | invalidation_source | display_policy | display_policy_ok | recommended_label_future | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | 1.1497 | 1.18079 | long | True | state_machine_and_latest_close | manual_review_only | True | invalidated_old_context | Manual-only is correct. The current output should be read as old long context invalidated, not as a new bearish WaveCount signal. |
| GBPUSD.r | H4 | 1.33114 | 1.35675 | long | True | state_machine_and_latest_close | manual_review_only | True | invalidated_old_context | Manual-only is correct. The current output should be read as old long context invalidated, not as a new bearish WaveCount signal. |

## Comparacion Contra State Machine

| symbol | timeframe | state_machine_wave | live_estimated_wave | state_machine_display_policy | live_display_policy | visual_label_plausible | improvement | new_risk | dashboard_future_should_show | telegram_allowed | bot_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | H4 | invalidated | invalidated | manual_review_only | manual_review_only | true | keeps_invalidated_context_manual_only | invalidated_old_context_may_be_misread_as_current_bearish_context | hide_from_default_current_wave_summary | False | False |
| GBPUSD.r | H4 | invalidated | invalidated | manual_review_only | manual_review_only | true | keeps_invalidated_context_manual_only | invalidated_old_context_may_be_misread_as_current_bearish_context | hide_from_default_current_wave_summary | False | False |
| US500 | H4 | possible_wave3_active | possible_wave3_active | show_with_warning | show_live_estimate_with_warning | true | latest_close_makes_active_candidate_distinction_more_explicit | late_context_can_feel_fresher_than_it_is | show_both_in_study_panel_only | False | False |
| XAUUSD.r | H4 | possible_wave3_candidate | possible_wave3_candidate | show_with_warning | show_live_estimate_with_warning | unclear | latest_close_makes_active_candidate_distinction_more_explicit | late_context_can_feel_fresher_than_it_is | show_both_in_study_panel_only | False | False |

## Decision Summary

| decision | us500_result | xauusd_result | invalidated_rows | visual_summary | sql_dashboard_allowed_now | next_step |
| --- | --- | --- | --- | --- | --- | --- |
| live_estimate_study_panel_only | Keep possible_wave3_active as provisional study-panel label; do not show as fresh main-dashboard current wave. | Keep possible_wave3_candidate only as low-confidence study-panel context. | 2 | EURUSD.r:readable/true; GBPUSD.r:readable/true; US500:readable/true; XAUUSD.r:borderline/unclear | False | Broaden real-OHLC visual review or design a study-panel contract; do not integrate into SQL/dashboard main view yet. |

## Riesgos

| severity | risk | description | recommendation |
| --- | --- | --- | --- |
| info | contract_or_security_failure | 0 blocking contract/security checks failed. | Block any integration if this is non-zero. |
| high | late_context_can_be_misread_as_current | US500 and XAUUSD.r remain derived from late confirmed context, even with latest-close estimate. | Use study-panel wording, not main-dashboard current-wave wording. |
| medium | unclear_label_plausibility | 1 labels are visually unclear or borderline. | Require broader real-OHLC review before SQL/dashboard. |
| medium | invalidated_old_context_wording | Invalidated rows may be read as fresh bearish context if wording is too terse. | Consider future label invalidated_old_context/no_current_wave_context. |
| info | non_operational_guard | Decision is live_estimate_study_panel_only; Telegram and bot remain forbidden. | Keep can_generate_signal/can_filter_trade/can_execute_order false. |

## Lectura

- US500 es visualmente plausible como `possible_wave3_active`, pero solo en
  panel de estudio con warning: no columna principal de onda actual.
- XAUUSD.r puede mantenerse como `possible_wave3_candidate` de baja confianza;
  no cruza activacion y queda borderline.
- EURUSD.r y GBPUSD.r deben seguir `manual_review_only`; mejor etiquetarlos en
  el futuro como `invalidated_old_context` o `no_current_wave_context`.
- La estimacion viva mejora la state machine porque explicita el tramo desde el
  ultimo pivote hasta el ultimo cierre, pero no elimina el problema de contexto
  tardio.
