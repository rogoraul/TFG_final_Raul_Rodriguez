# RiskGuard demo intent builder v1

## Que implementa

Esta fase implementa un builder artifact-first para convertir decisiones de MT5 Shadow en `demo_order_intents` y decisiones RiskGuard auditables. El builder no envia ordenes, no conecta MT5, no conecta Telegram y no escribe SQL.

## Flujo

`MT5 Shadow -> demo_order_intents -> riskguard_decisions`

Solo se consideran para automatico futuro `macd_breakout` y `fib_limit_live_candidate`. `rsi_trend_reversal` queda manual/futuro y los contextos se bloquean por scope.

## Timing

El builder distingue `triggered_at`, `observed_at`, `review_window_seconds`, `late_after` y `current_state`. `would_trigger` no significa entrada actual: si el trigger ya esta fuera de ventana, se bloquea como tarde.

## Seguridad

- `demo_order_sender_implemented=false`
- `order_send_available=false`
- `orders_sent=0`
- `mt5_orders_sent=0`
- `can_send_order_any_true=false`
- `order_sent_any_true=false`
- `telegram_connected=false`

## Resultado

Decision: `riskguard_demo_intent_builder_v1_ready_for_dashboard_review`

Intents generados: 0
Decisiones RiskGuard: 5
Aceptados para intent demo: 0
Bloqueados: 5

## Issues

- no_accepted_intents: All candidate rows were blocked or non-eligible.
