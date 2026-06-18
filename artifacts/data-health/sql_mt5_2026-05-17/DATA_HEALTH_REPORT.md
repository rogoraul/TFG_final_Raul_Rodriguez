# SQL/MT5 Data Health Audit - 2026-05-17

## Resumen

- Pares auditados: 170.
- Pares con consulta resumen OK: 170.
- Pares con datos OHLCV: 170.
- Hallazgos importantes: 0.
- Hallazgos menores: 136.
- Pendientes/no bloqueantes: 170.
- Timeout SQL solicitado: 15000 ms.
- `MAX_EXECUTION_TIME` soportado por la sesion: True.

## Alcance

- Grupos foco: Forex Majors, Metals.
- Timeframes: M15, M30, H1, H4, D1.
- No se han reejecutado backtests ni recalculado senales.
- No se han modificado estrategias ni artifacts canonicos.
- Las comprobaciones se ejecutan por simbolo/timeframe para evitar agregaciones globales pesadas.

## Lectura metodologica

- La existencia del indice unico `symbol/timeframe/time` se usa como prueba principal contra duplicados.
- La ultima vela se evalua contra la hora local de auditoria, no contra MT5 conectado; por tanto es una comprobacion prudente, no una certificacion de servidor live.
- Los gaps largos se clasifican como `session_or_weekend`; los gaps cortos requieren revision porque pueden ser festivos o huecos reales.
- La auditoria no interpreta calidad de estrategia; solo valida la base OHLCV.

## Archivos generados

- `tables/symbol_control.csv`
- `tables/price_symbols.csv`
- `tables/price_timeframes.csv`
- `tables/pair_health.csv`
- `tables/gap_examples.csv`
- `tables/group_coverage.csv`
- `tables/group_timeframe_summary.csv`
- `tables/suffix_consistency.csv`
- `tables/issues.csv`
- `tables/query_log.csv`
- `run_meta.json`

## Hallazgos

- **pendiente/no bloqueante** `vigencia_live` `AUDCAD.r M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDCAD.r M15`: gaps cortos/anomalos: 9 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDCAD.r M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDCAD.r M30`: gaps cortos/anomalos: 8 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDCAD.r H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDCAD.r H1`: gaps cortos/anomalos: 5 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDCAD.r H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDCAD.r H4`: gaps cortos/anomalos: 4 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDCAD.r D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `AUDJPY.r M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDJPY.r M15`: gaps cortos/anomalos: 9 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDJPY.r M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDJPY.r M30`: gaps cortos/anomalos: 8 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDJPY.r H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDJPY.r H1`: gaps cortos/anomalos: 5 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDJPY.r H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDJPY.r H4`: gaps cortos/anomalos: 4 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDJPY.r D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `AUDNZD.r M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDNZD.r M15`: gaps cortos/anomalos: 11 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDNZD.r M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDNZD.r M30`: gaps cortos/anomalos: 9 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDNZD.r H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDNZD.r H1`: gaps cortos/anomalos: 5 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDNZD.r H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDNZD.r H4`: gaps cortos/anomalos: 4 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDNZD.r D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `AUDUSD.r M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDUSD.r M15`: gaps cortos/anomalos: 8 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDUSD.r M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDUSD.r M30`: gaps cortos/anomalos: 8 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDUSD.r H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDUSD.r H1`: gaps cortos/anomalos: 5 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDUSD.r H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUDUSD.r H4`: gaps cortos/anomalos: 4 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUDUSD.r D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `CADCHF.r M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `CADCHF.r M15`: gaps cortos/anomalos: 15 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `CADCHF.r M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `CADCHF.r M30`: gaps cortos/anomalos: 14 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- ... 266 hallazgos adicionales en `tables/issues.csv`.

## Cobertura por grupo

- `Forex Majors`: M15=27/27, M30=27/27, H1=27/27, H4=27/27, D1=27/27
- `Metals`: M15=7/7, M30=7/7, H1=7/7, H4=7/7, D1=7/7

## Resumen por grupo/timeframe

- `Forex Majors D1`: 27 simbolos, 55187 filas, rango 1999-12-28 00:00:00 -> 2026-03-16 00:00:00, gaps cortos=0, gaps sesion/calendario=11125.
- `Forex Majors H1`: 27 simbolos, 1096984 filas, rango 2009-09-22 08:00:00 -> 2026-03-17 09:00:00, gaps cortos=228, gaps sesion/calendario=9213.
- `Forex Majors H4`: 27 simbolos, 327360 filas, rango 1999-12-28 00:00:00 -> 2026-03-17 04:00:00, gaps cortos=184, gaps sesion/calendario=10961.
- `Forex Majors M15`: 27 simbolos, 2789284 filas, rango 2022-01-18 17:15:00 -> 2026-03-17 10:00:00, gaps cortos=332, gaps sesion/calendario=5859.
- `Forex Majors M30`: 27 simbolos, 1782398 filas, rango 2018-01-10 19:00:00 -> 2026-03-17 09:30:00, gaps cortos=281, gaps sesion/calendario=7481.
- `Metals D1`: 7 simbolos, 12988 filas, rango 2013-01-25 00:00:00 -> 2026-03-16 00:00:00, gaps cortos=0, gaps sesion/calendario=2649.
- `Metals H1`: 7 simbolos, 208248 filas, rango 2013-01-25 00:00:00 -> 2026-03-17 09:00:00, gaps cortos=10248, gaps sesion/calendario=2749.
- `Metals H4`: 7 simbolos, 58175 filas, rango 2013-01-25 00:00:00 -> 2026-03-17 04:00:00, gaps cortos=3146, gaps sesion/calendario=2749.
- `Metals M15`: 7 simbolos, 664005 filas, rango 2021-10-19 06:00:00 -> 2026-03-17 10:00:00, gaps cortos=5979, gaps sesion/calendario=1503.
- `Metals M30`: 7 simbolos, 408191 filas, rango 2013-01-25 00:00:00 -> 2026-03-17 09:30:00, gaps cortos=14142, gaps sesion/calendario=2749.

## Consultas mas lentas

- `pair_summary_AUDUSD.r_M15`: 2.2973s, status=ok
- `pair_summary_GBPCAD.r_M15`: 2.2651s, status=ok
- `pair_summary_EURCHF.r_M15`: 2.2361s, status=ok
- `pair_summary_CADCHF.r_M15`: 2.2326s, status=ok
- `pair_summary_XPDUSD_M15`: 2.1152s, status=ok

## Conclusion

La auditoria queda reproducible por codigo. Para avanzar a watcher continuo, Telegram o MT5 dry-run, el punto clave es revisar los hallazgos de `tables/issues.csv`, especialmente cobertura, vigencia live y gaps cortos.
