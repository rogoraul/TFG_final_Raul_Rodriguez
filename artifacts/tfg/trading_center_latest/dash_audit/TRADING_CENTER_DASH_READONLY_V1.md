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
reproducibles y mantiene fixture como accion por defecto. Si el usuario pulsa
`Analizar con Codex local`, el panel llama al gateway `codex_cli` con sandbox
read-only y auditoria. La accion separada `Codex + macro` activa
`--macro-web-research` para que Codex local pueda consultar internet y
documentar riesgo macro/noticias con fuentes; este modo tambien es manual y no
conecta MT5, Telegram ni SQL.
Mientras se ejecuta un analisis, el panel muestra estado de progreso y bloquea
visualmente los tres botones de accion para evitar doble ejecucion accidental.
Cada review validada genera `ai_analyst_review_report.pdf`, descargable desde
el propio panel como informe redactado read-only. La pestana `MT5 Shadow`
consume `mt5_shadow_decisions.csv` y `run_meta.json` para mostrar que habria
hecho el modo shadow con los setups actuales, siempre como auditoria hipotetica:
no conecta MT5, no envia ordenes y no modifica posiciones.

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
- AI Analyst queda con fixture por defecto y Codex local solo bajo gate manual.

## Datos

- snapshot_rows=54
- watchlist_rows=54
- universe_symbols=60
- universe_current_snapshot_symbols=27
- market_radar_rows=60
- trend_aligned_count=29
- counter_extreme_count=5
- correlation_rows=7080
- correlation_rolling_rows=28320
- correlation_returns_rows=167748
- correlation_timeframes=D1, H1, H4, M15
- wavecount_rows=94
- screener_setups_rows=118
- screener_chart_layers_rows=2771
- mt5_shadow_source_status=available
- mt5_shadow_decision_rows=1
- ai_analyst_call_mode=fixture_default_codex_cli_manual_codex_macro_manual
- ai_analyst_model_called=False

## Uso

```powershell
python -m trading_center.dash_readonly_app --port 8050
```

Abrir:

`http://127.0.0.1:8050/`
