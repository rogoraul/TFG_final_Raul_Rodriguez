# Trading Center Dash Read-only V1

Fecha: 2026-05-30

Decision: `trading_center_dash_readonly_v1_ready_for_local_review`.

## Resultado

Se implementa una app Dash local para uso real de revision de mercado. La app
carga CSV/JSON auditados, incluido el radar M15/H1/H4/D1 y la capa de
correlaciones por retornos generadas desde artifacts. Ofrece tabs, filtros,
radar visual, correlacion por timeframe y Screener unificado sin conectar SQL en
caliente. La seccion WeaveCount organiza el estudio por recuadros Onda 1-5 y
una lista horizontal de casos clicables que abren el grafico de velas/trazado
del caso cuando existe contexto de grafico, manteniendo el uso study-only. La
antigua superficie Estrategias queda absorbida por Screener: arriba aparecen
setups destacados con calidad visual 1-5; el detalle se consulta en un modal
vertical al hacer clic y la matriz por activo ya no se renderiza en la UI. La
integracion AI Analyst anade un boton flotante read-only que prepara paquetes
reproducibles del setup seleccionado y valida una salida fixture mediante el
gateway controlado; no llama modelos reales ni abre red.

## Limites

- No escribe SQL.
- No conecta DB.
- No ejecuta DDL.
- No conecta MT5.
- No conecta Telegram.
- No pide token ni chat id.
- No genera senales.
- No ejecuta backtests.
- No usa WaveCount como filtro.
- AI Analyst queda en modo fixture/controlado: model_called=false.

## Datos

- snapshot_rows=54
- watchlist_rows=54
- universe_symbols=60
- universe_current_snapshot_symbols=27
- market_radar_rows=60
- trend_aligned_count=32
- counter_extreme_count=13
- correlation_rows=7080
- correlation_rolling_rows=28320
- correlation_returns_rows=167748
- correlation_timeframes=D1, H1, H4, M15
- wavecount_rows=94
- screener_setups_rows=27
- screener_chart_layers_rows=428
- ai_analyst_call_mode=fixture
- ai_analyst_model_called=False

## Uso

```powershell
python -m trading_center.dash_readonly_app --port 8050
```

Abrir:

`http://127.0.0.1:8050/`
