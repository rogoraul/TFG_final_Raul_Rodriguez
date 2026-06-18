# Trading Center Market Radar V1

Fecha: 2026-05-31

Decision: `market_radar_v1_ready_for_dashboard_summary`.

## Resultado

Se genera `market_radar.csv` como artifact informativo para alimentar el
Resumen del Trading Center Dash.

El radar cruza:

- tendencia M15/H1/H4 y H1/H4/D1 cuando existe fuente para cada timeframe;
- RSI y Stoch calculados con `backtests.enbolsa.GenerarIndicadores`;
- ATR% actual y mediana propia por activo para ranking de exceso/carencia de
  volatilidad;
- alineacion de tendencia para el radar visual;
- `Screener RSI` para RSI extremo dentro del contexto de timeframes superiores.

## Datos

- filas radar: 60
- simbolos con radar: 60
- alineados: 23
- lecturas Screener RSI: 0
- source_mode: `sql_readonly_ohlc_artifact`

Campos de volatilidad:

- `atr_pct_h1`: ATR H1 actual en porcentaje sobre precio.
- `atr_pct_h1_median`: mediana de ATR% H1 del propio activo en la ventana
  disponible.
- `atr_pct_h1_ratio`: `atr_pct_h1 / atr_pct_h1_median`; se usa para rankear
  exceso o carencia de volatilidad sin comparar familias por escala bruta.
- `atr_pct_h1_sample_count`: numero de lecturas validas usadas.

El radar puede consumir el artifact SQL read-only `ohlc_mtf.csv` con M15/H1/H4/D1
para cubrir todo el universo disponible en `price_data`. Si ese artifact no existe,
mantiene fallback a los contextos H1/H4 y H4/D1 ya auditados sin inventar lecturas
para los timeframes que falten.

## Seguridad

- No conecta SQL.
- No escribe SQL.
- No conecta MT5.
- No conecta Telegram.
- No genera senales.
- No ejecuta backtests.
- No usa WaveCount como filtro.

## Uso

```powershell
python -m trading_center.market_radar
```
