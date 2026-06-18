# SQL Operational Core Closure V1

Fecha: 2026-05-28

Decision: `sql_operational_closure_ready_for_dashboard_design`.

## Resultado

Se consulto SQL real local en modo lectura contra `trading_ops`. No se ejecuto
DDL, no se cargo historico, no se recargo el snapshot y no se implementaron
dashboard, Telegram, bot ni MT5.

## Secciones V1.1

- `S01_context_audit`: los docs/artifacts base existen; el core v0 ya tenia
  verificacion previa y export.
- `S02_scope_safety`: la fase se mantuvo en cierre/verificacion SQL.
- `S03_contract_inputs`: schema, vistas, loader, store y configuracion local
  fueron revisados sin imprimir secretos.
- `S04_main_tasks`: se consultaron conteos, migraciones, distribuciones y flags.
- `S05_outputs_docs`: se crearon artifacts de cierre y export desde SQL.
- `S06_validation_closure`: queda validado por artifacts y `git diff --check`.

## Conteos SQL

| metric | value |
| --- | --- |
| snapshot_runs | 1 |
| live_context_snapshot_rows | 54 |
| snapshot_source_inventory | 10 |
| signal_events | 54 |
| data_health_snapshot | 27 |
| v_live_context_latest | 54 |
| v_dashboard_trading_center | 54 |
| v_dashboard_watchlist | 54 |
| v_signal_events_latest | 54 |
| v_data_health_latest | 27 |

## Seguridad

| check | value |
| --- | --- |
| can_execute_order_true | 0 |
| wavecount_should_filter_trade_true | 0 |
| non_read_only_rows | 0 |
| visible_backfill_or_test_rows | 0 |
| snapshot_runs_historical_or_test_operational | 0 |

La carga visible sigue siendo `bootstrap_current` con `is_operational=1`.

## Migraciones

- `001_create_operational_core`: registrada.
- `002_create_operational_core_views`: registrada.

## Export

Se genero export desde `trading_ops.v_live_context_latest` en:

`artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/`

Filas exportadas: 54.

## Incidencias

`export_latest_snapshot` fallo al invocarse con `output_dir` relativo por el
calculo de `relative_to(REPO_ROOT)`. Se repitio con ruta absoluta y el export
salio correctamente. Es una incidencia menor de utilidad, no del SQL.

## Siguiente Paso

Ejecutar `P02_design_trading_center_readonly_v1`.

