# SQL/MT5 Data Health Audit - 2026-05-17

## Resumen

- Pares auditados: 65.
- Pares con consulta resumen OK: 65.
- Pares con datos OHLCV: 65.
- Hallazgos importantes: 0.
- Hallazgos menores: 52.
- Pendientes/no bloqueantes: 65.
- Timeout SQL solicitado: 15000 ms.
- `MAX_EXECUTION_TIME` soportado por la sesion: True.

## Alcance

- Grupos foco: Index.
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

- **pendiente/no bloqueante** `vigencia_live` `AUS200 M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUS200 M15`: gaps cortos/anomalos: 1397 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUS200 M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUS200 M30`: gaps cortos/anomalos: 6797 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUS200 H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUS200 H1`: gaps cortos/anomalos: 2324 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUS200 H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `AUS200 H4`: gaps cortos/anomalos: 423 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `AUS200 D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `CHINA50 M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `CHINA50 M15`: gaps cortos/anomalos: 909 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `CHINA50 M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `CHINA50 M30`: gaps cortos/anomalos: 1693 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `CHINA50 H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `CHINA50 H1`: gaps cortos/anomalos: 1247 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `CHINA50 H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `CHINA50 H4`: gaps cortos/anomalos: 277 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `CHINA50 D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `EURO50 M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `EURO50 M15`: gaps cortos/anomalos: 981 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `EURO50 M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `EURO50 M30`: gaps cortos/anomalos: 1239 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `EURO50 H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `EURO50 H1`: gaps cortos/anomalos: 1229 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `EURO50 H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `EURO50 H4`: gaps cortos/anomalos: 3 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `EURO50 D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `FRA40 M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `FRA40 M15`: gaps cortos/anomalos: 950 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `FRA40 M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `FRA40 M30`: gaps cortos/anomalos: 1244 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `FRA40 H1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `FRA40 H1`: gaps cortos/anomalos: 1237 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `FRA40 H4`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `FRA40 H4`: gaps cortos/anomalos: 351 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `FRA40 D1`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **pendiente/no bloqueante** `vigencia_live` `GER40 M15`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `GER40 M15`: gaps cortos/anomalos: 1004 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- **pendiente/no bloqueante** `vigencia_live` `GER40 M30`: datos stale para live Recomendacion: actualizar SQL antes de watcher continuo o Telegram.
- **menor** `gaps` `GER40 M30`: gaps cortos/anomalos: 900 Recomendacion: revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales.
- ... 77 hallazgos adicionales en `tables/issues.csv`.

## Cobertura por grupo

- `Index`: M15=13/13, M30=13/13, H1=13/13, H4=13/13, D1=13/13

## Resumen por grupo/timeframe

- `Index D1`: 13 simbolos, 20264 filas, rango 2014-01-22 00:00:00 -> 2026-03-16 00:00:00, gaps cortos=0, gaps sesion/calendario=4217.
- `Index H1`: 13 simbolos, 416464 filas, rango 2014-01-22 00:00:00 -> 2026-03-17 09:00:00, gaps cortos=16423, gaps sesion/calendario=4172.
- `Index H4`: 13 simbolos, 112454 filas, rango 2014-01-22 00:00:00 -> 2026-03-17 04:00:00, gaps cortos=3166, gaps sesion/calendario=4172.
- `Index M15`: 13 simbolos, 1228556 filas, rango 2021-05-26 09:00:00 -> 2026-03-17 10:00:00, gaps cortos=12820, gaps sesion/calendario=3007.
- `Index M30`: 13 simbolos, 814701 filas, rango 2016-10-05 15:00:00 -> 2026-03-17 09:30:00, gaps cortos=21842, gaps sesion/calendario=4015.

## Consultas mas lentas

- `pair_summary_AUS200_M15`: 7.0691s, status=ok
- `pair_summary_AUS200_M30`: 5.6825s, status=ok
- `pair_summary_GER40_M15`: 5.5965s, status=ok
- `pair_summary_CHINA50_M15`: 5.2879s, status=ok
- `pair_summary_EURO50_M15`: 4.9527s, status=ok

## Conclusion

La auditoria queda reproducible por codigo. Para avanzar a watcher continuo, Telegram o MT5 dry-run, el punto clave es revisar los hallazgos de `tables/issues.csv`, especialmente cobertura, vigencia live y gaps cortos.
