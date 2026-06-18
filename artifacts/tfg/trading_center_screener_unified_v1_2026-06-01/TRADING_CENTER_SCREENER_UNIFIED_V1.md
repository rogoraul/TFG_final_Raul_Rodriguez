# Trading Center Screener Unified V1

Fecha: 2026-06-01

Decision: `macd_breakout_screener_integration_v1_ready_for_review`.

## Resultado

Se implementa la seccion `Screener` como radar artifact-first de setups y
contexto. Absorbe la antigua superficie `Estrategias`: arriba muestra setups
destacados con calidad visual 1-5 y confluencias auditables. La matriz por
activo queda como artifact tecnico para auditoria, pero no se muestra en el Dash
porque duplicaba informacion de Mercado/WeaveCount y hacia el Screener demasiado
denso.

## Lectura correcta

- La calidad 1-5 mide claridad visual/contextual para revisar un grafico.
- No mide probabilidad, edge ni rentabilidad esperada.
- `trend_alignment` queda como informacion contextual; no se crea como setup
  destacado por si solo.
- `pivot_context` y `round_level` quedan como informacion extra de calidad y
  capas graficas; no se crean como setups destacados por si solos.
- Los niveles redondos se dibujan como dos niveles cercanos al ultimo precio:
  nivel inferior/actual y nivel superior, en linea morada fina y continua.
- `macd_breakout` se consume desde el enrichment artifact-first combinado para
  `Forex Majors`, `Metals` e `Index`, con una lectura por simbolo/timeframe en
  H1 y H4 cuando existe contexto reconstruido.
- `fib_limit` se muestra como setup live de estudio solo cuando el precio actual
  esta cerca de `Fib 61.8` en el contexto Fibonacci artifact-first. No es senal
  ni permiso operativo.
- El modal de `fib_limit` dibuja capas de estudio derivadas del mismo swing:
  `Entrada 61.8 estudio`, `SL estudio`, `TP1 estudio` y `TP2 estudio` cuando
  existen en el artifact. La entrada se muestra como toque OHLC del 61.8,
  coherente con el proxy de orden limitada/resting usado en el backtest. Son
  referencias visuales para revision manual, no instrucciones de ejecucion.
- Fibonacci contextual se consume desde `trading_center_fibonacci_context_v1`
  como capa visual y queda separado de `fib_limit`.
- Las zonas Fibonacci son contexto visual y pueden sumar calidad; no son senal
  ni filtro operativo.
- Codex/AI Analyst queda como `revision codex pendiente` para una fase futura.
- Los casos `fib_limit_swing_quality` pueden reconstruirse solo con el flag CLI
  `--include-historical-fib-limit`, pensado para auditoria, no para el Dash live.
- El modal muestra la tendencia desglosada por timeframe (`M15`, `H1`, `H4`,
  `D1`) para que se vea que marcos estan alineados o en conflicto.
- `trend_compatibility` separa setups `compatible`, `mixed` y `against`.
  Compatible puede sumar calidad visual; mixto queda con cautela; contra
  tendencia se degrada. No es senal ni permiso operativo.
- Los contextos vacios se muestran como `sin cercania` o `sin contexto`, no
  como codigos internos.
- En `macd_breakout`, el modal muestra la ruptura real reconstruida y una
  regresion W2 proyectada hasta la ultima vela para facilitar la lectura visual.
  La linea se ajusta sobre `highs` en largos y `lows` en cortos, y la ruptura se
  confirma por `close`. No es una directriz manual que una mechas exactas. La
  proyeccion no cambia el disparador, no convierte casos `late` en setups
  frescos y sigue siendo study-only.
- `rsi_trend_reversal` queda implementado como setup de estudio simple: M15
  exige alineacion `M15/H1/H4` y H1 exige `H1/H4/D1`. En tendencia bajista
  vigila sobrecompra y cruce de vuelta bajo 70; en tendencia alcista vigila
  sobreventa y cruce de vuelta sobre 30. `watching` usa 68/32 como zona de
  aproximacion. SL/TP quedan fuera del detector y pendientes de estudio.

## Seguridad

- is_signal=False
- is_study_only=True
- sql_real_written=False
- db_connected=False
- mt5_connected=False
- telegram_connected=False
- orders_sent=0
- signals_generated=False
- wavecount_used_as_filter=False

## Datos generados

- setups_count=114
- highlighted_setups_count=114
- asset_matrix_rows=60
- chart_layers_count=2714
- fib_limit_implemented=True
- fib_limit_live_detector_implemented=True
- fib_limit_live_candidates_count=3
- trend_compatibility_implemented=True
- trend_compatible_count=23
- trend_mixed_count=75
- trend_against_count=16
- fib_limit_trend_against_count=0
- fib_limit_historical_review_available=True
- fib_limit_swing_quality_consumed=False
- fib_limit_setups_count=0
- rsi_trend_reversal_implemented=True
- rsi_trend_reversal_setups_count=0
- rsi_trend_reversal_entry_review_count=0
- rsi_trend_reversal_watching_count=0
- rsi_trend_reversal_sl_tp_defined=False

## Validacion visual esperada

El paquete incluye screenshots de revision local del Dash:

- `screenshots/navigation_without_estrategias.png`;
- `screenshots/screener_overview.png`;
- `screenshots/screener_filters.png`;
- `screenshots/screener_modal.png`.
