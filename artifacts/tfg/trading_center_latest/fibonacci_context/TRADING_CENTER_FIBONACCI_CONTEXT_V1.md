# Trading Center Fibonacci Context V1

Fecha: 2026-06-02

Decision: `trading_center_fibonacci_context_v1_ready_for_dashboard_review`.

## Resultado

Se implementa una capa Fibonacci artifact-first para enriquecer el modal del
Screener. La capa calcula pivotes confirmados recientes, selecciona el swing
alternante reciente mas material y genera niveles de retroceso/extension para
revision visual. Para evitar fibos sobre micro-swings, el tramo debe superar
umbrales de rango porcentual, numero minimo de velas y multiple de true range
reciente; entre los candidatos validos se prioriza el de mayor materialidad.
Tambien marca los anclajes `Fib 0` y `Fib 100` del swing para que el inicio y
el final de la medicion sean visibles en el grafico.

## Lectura correcta

- Fibonacci es contexto grafico, no senal.
- `fib_limit` sigue separado y no queda implementado en esta fase.
- `fibonacci_zone_candidate` es una zona de revision, no una orden ni un filtro.
- Si no hay swing suficiente se marca `no_clear_swing`.

## Cobertura

- symbols_evaluated=47
- symbol_timeframes_evaluated=94
- near_price_count=41
- no_clear_swing_count=0
- materiality_passed_count=94
- materiality_failed_count=0
- chart_layers_count=846

## Seguridad

- is_signal=False
- is_study_only=True
- sql_real_written=False
- db_connected=False
- mt5_connected=False
- telegram_connected=False
- orders_sent=0
- signals_generated=False
