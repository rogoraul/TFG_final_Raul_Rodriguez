# MT5 Post-Update Attempt - 2026-05-17

## Resultado

La actualizacion incremental SQL/MT5 no se ha ejecutado porque la ruta existente
`connect_mt5()` no pudo inicializar MetaTrader 5.

No se descargaron datos, no se insertaron velas y no se ejecuto la auditoria
post-update.

## Alcance preparado

- Grupos: `Forex Majors`, `Metals`, `Index`.
- Simbolos: 47.
- Timeframes: `M15`, `M30`, `H1`, `H4`, `D1`.
- Pares previstos: 235.
- Contexto: domingo 2026-05-17; no se esperaban velas nuevas de fin de semana.

## Evidencia

- `run_meta_update.json`: `status = mt5_connection_failed`.
- `logs/mt5_incremental_update_console.log`: muestra `No se pudo conectar a MetaTrader 5`.
- En el sistema se detecto un proceso `terminal64.exe`, pero el helper actual
  `mt5.initialize()` no logro conectarse a el.

## Decision

No se ha intentado una conexion alternativa con ruta explicita al terminal para
evitar cambiar de forma implicita la ruta operativa existente.

## Siguiente paso

Cuando MT5 este disponible desde Python, repetir:

```powershell
python -m data.sql.audit_data_health --output-dir artifacts/data-health/sql_mt5_2026-05-17 --groups "Forex Majors,Metals" --timeframes M15,M30,H1,H4,D1 --query-timeout-ms 15000 --max-gap-pair-rows 250000 --max-gap-examples-per-pair 3
```

Antes de reauditar, ejecutar de nuevo la actualizacion incremental. Si vuelve a
fallar `mt5.initialize()`, revisar de forma explicita la configuracion local de
MetaTrader5 para decidir si conviene parametrizar la ruta del terminal.
