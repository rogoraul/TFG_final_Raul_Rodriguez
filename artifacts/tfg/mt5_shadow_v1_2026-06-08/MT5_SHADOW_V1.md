# MT5 Shadow V1

Fecha: 2026-06-08

Decision: `mt5_shadow_v1_ready_for_local_shadow_review`

## Resumen

`mt5_shadow_v1` implementa una simulacion artifact-first entre setups del
Trading Center, OHLC cerrado y snapshots MT5 read-only. El objetivo es registrar
que habria ocurrido de forma hipotetica antes de disenar demo orders.

No conecta MT5, no envia ordenes, no modifica posiciones, no conecta Telegram y
no escribe SQL. `would_trigger` significa solo que el setup habria activado una
observacion shadow segun reglas de estudio; no es una orden ni permiso operativo.
El ambito de bot automatico queda limitado de forma conservadora a
`macd_breakout` y `fib_limit_live_candidate` con
`setup_quality_score >= 4`. RSI, niveles,
Fibonacci contextual y otros candidatos quedan como contexto de revision, no
como shadow candidates de bot. Esos casos excluidos se auditan en
`tables/excluded_from_automation_audit.csv`, pero no se publican en
`mt5_shadow_decisions.csv`.

## Resultado

- setups cargados: `97`
- decisiones shadow: `5`
- excluidos de decisiones shadow: `92`
- auto candidates: `5`
- context only: `3`
- below min quality: `89`
- would_trigger: `3`
- would_wait: `2`
- late: `0`
- invalidated: `0`
- no_price_data: `0`

## Seguridad

- `mt5_connected=false`
- `mt5_orders_sent=0`
- `can_send_order_any_true=false`
- `telegram_connected=false`
- `sql_real_written=false`
- `signals_generated=false`

## Incidencias

- `no_runtime_issues`: Shadow artifact generation completed without runtime issues.

## Siguiente paso

Revisar visualmente las decisiones shadow y, si encajan, disenar la fase de
shadow review/dashboard antes de cualquier demo order.
