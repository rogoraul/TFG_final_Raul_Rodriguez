# MACD Breakout Watcher Enrichment V1

Fecha: 2026-06-08

Decision: `macd_breakout_watcher_enrichment_v1_ready_for_screener_integration`.

## Resultado

Se implementa `macd_breakout_watcher_enrichment_v1` como capa artifact-first
entre el watcher ENBOLSA y el futuro timing/capas del Screener. La fase no
modifica la estrategia, no ejecuta backtests y mantiene todas las flags
fail-closed.

## Conteos

- enriched_rows=188
- chart_layers_count=1581
- missing_context_count=38
- entry_review_count=2
- late_count=18
- invalidated_count=122

## Cobertura orientativa

- w1_start_time=188
- w2_swing_time=98
- breakout_level=142
- last_breakout_time=142
- last_macd_cross_time=117

## Lectura visual

- `breakout_level` y `last_breakout_time` mantienen el punto real de ruptura
  reconstruido con la logica interna de ENBOLSA.
- La capa `macd_w2_directrix` proyecta esa misma regresion hasta la ultima vela
  del snapshot para que el modal sea legible. Es regresion sobre `highs` en
  largos y sobre `lows` en cortos; no es una directriz manual que una mechas
  exactas. Esta proyeccion es visual y study-only; no modifica el disparador, no
  genera senal y no habilita operativa.
- Si el timing queda `late`, la linea se muestra como `Reg W2 highs/lows tardia`
  para separar una ruptura antigua de una revision fresca.

## Seguridad

- `strategy_modified=false`
- `fib_limit_modified=false`
- `backtests_executed=false`
- `sql_real_written=false`
- `db_connected=false`
- `mt5_connected=false`
- `telegram_connected=false`
- `orders_sent=0`
- `signals_generated=false`
