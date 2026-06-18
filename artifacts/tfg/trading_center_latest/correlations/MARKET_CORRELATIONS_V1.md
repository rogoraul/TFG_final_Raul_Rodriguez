# Trading Center Market Correlations V1

Fecha: 2026-05-31

Decision: `trading_center_market_correlations_v1_ready_for_dashboard`.

## Resultado

Se genera una capa artifact-first de correlacion para el Trading Center Dash.
La correlacion se calcula sobre retornos logaritmicos close-to-close, no sobre
precios brutos.

Artifacts principales:

- `correlation_pairs.csv`
- `correlation_pairs.json`
- `rolling_correlations.csv`
- `correlation_returns_sample.csv`
- `tables/correlation_timeframe_summary.csv`

## Metricas

- Pearson: relacion lineal de retornos.
- Spearman: relacion monotona por rangos; recomendada por defecto.
- Kendall: concordancia ordinal conservadora.
- dCor: dependencia general no lineal, sin signo direccional.

## Seguridad

- No conecta SQL.
- No escribe SQL.
- No conecta MT5.
- No conecta Telegram.
- No genera senales.
- No ejecuta ordenes.
- No ejecuta backtests.

## Datos

- timeframes: `M15, H1, H4, D1`
- pair_rows: 7080
- rolling_rows: 28320
- returns_sample_rows: 167748
- source: `artifacts\tfg\trading_center_sql_market_data_readonly_v1_2026-05-31\ohlc_mtf.csv`
