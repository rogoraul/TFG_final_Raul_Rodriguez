# RiskGuard demo intent builder v1

## Que implementa

Esta fase implementa un builder artifact-first para convertir decisiones de MT5 Shadow en `demo_order_intents` y decisiones RiskGuard auditables. El builder no envia ordenes, no conecta MT5, no conecta Telegram y no escribe SQL.

## Flujo

`MT5 Shadow -> demo_order_intents -> riskguard_decisions`

Solo se consideran para automatico futuro `macd_breakout` y `fib_limit_live_candidate`. `rsi_trend_reversal` queda manual/futuro y los contextos se bloquean por scope.

## Timing

El builder distingue `triggered_at`, `observed_at`, `review_window_seconds`, `late_after` y `current_state`. `would_trigger` no significa entrada actual: si el trigger ya esta fuera de ventana, se bloquea como tarde.

## Hardening de riesgo 2026-06-11

La fase queda endurecida para demo:

- sizing monetario por equity, `risk_pct`, entrada, SL y metadata de simbolo;
- Forex puede usar fallback conservador de contrato estandar;
- metales e indices requieren metadata de tick/volumen o se bloquean;
- limites de riesgo por operacion, simbolo, grupo y exposicion total;
- bloqueo de duplicados contra posiciones, pendientes y candidatos del mismo run;
- `risk_state` con drawdown diario/acumulado y `kill_switch_active`;
- auditorias `riskguard_sizing_audit.csv` y `riskguard_exposure_audit.csv`.

No hay envio de ordenes desde RiskGuard: solo decision, bloqueo y trazabilidad.
Para memoria, puede describirse como RiskGuard demo endurecido; no como
RiskGuard de produccion ni como garantia de live trading robusto.

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

Intents generados: 3
Decisiones RiskGuard: 9
Aceptados para intent demo: 2
Bloqueados: 7

Hardening activo: `True`

## Issues

- no_runtime_issues: RiskGuard intent builder completed without runtime issues.
