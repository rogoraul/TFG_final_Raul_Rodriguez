# Bot Dry-Run V1

Fecha: 2026-05-29

Decision: `bot_dry_run_v1_artifact_ledger_ready_for_review`.

## Resumen

`bot_dry_run_v1` implementa un simulador artifact-first. Lee un snapshot CSV/export ya validado, evalua reglas de configuracion, datos y RiskGuard, y genera un ledger local con decisiones dry-run.

No conecta MT5, no envia ordenes, no conecta Telegram, no escribe SQL real, no crea DDL, no ejecuta backtests y no genera senales nuevas.

## Resultado Del Run Actual

- Snapshot rows: `54`
- Ledger rows: `54`
- Distribucion de decisiones: `{"dry_run_blocked_by_config": 54}`
- Simulated intents: `0`
- `can_execute_order_any_true=false`
- `wavecount_used_as_filter=false`

Con la configuracion por defecto, `bot_enabled=false` y `mode=off`, el sistema queda fail-closed. Si se habilita explicitamente `--bot-enabled --mode dry_run`, las filas `watching_setup` siguen siendo `dry_run_no_action`.

## Decisiones Soportadas

- `dry_run_blocked_by_config`: bot deshabilitado, modo incorrecto, MT5/live activado, filtros no permitidos o max intents superado.
- `dry_run_no_action`: contexto de vigilancia o sin `entry_ready_new`.
- `dry_run_blocked_by_data`: datos stale/missing o niveles invalidos en una fila `entry_ready_new`.
- `dry_run_blocked_by_riskguard`: fila `entry_ready_new` sin `riskguard_accepted`.
- `dry_run_order_intent`: simulacion permitida por config, datos frescos y RiskGuard aceptado.

## Ledger

El ledger se guarda en:

- `dry_run_decision_ledger.csv`
- `dry_run_decision_ledger.json`

Todos los registros mantienen:

- `can_execute_order=false`
- `would_send_to_mt5=false`
- `would_send_telegram_order=false`
- `is_simulation=true`

## WaveCount

WaveCount solo se copia como contexto informativo en `wavecount_context_summary`. No participa en filtros, RiskGuard, seleccion de filas ni decision final.

## Telegram Y MT5

Telegram command bot queda pendiente y no existe en esta fase. Telegram outbound podria consumir resumenes futuros, pero no recibe ordenes ni aprobaciones. MT5 sigue fuera de alcance: no hay adapter, conexion, cuenta ni broker.

## Riesgos Documentados

- `current_snapshot_watch_only` (info): Current real snapshot has only watching_setup rows; no simulated order intent should be created.
- `bot_disabled_default` (info): Default bot_enabled=false keeps the artifact run fail-closed.

## Siguiente Paso

Revisar `bot_dry_run_v1` con foco en ledger, defaults fail-closed, fixtures positivos y separacion frente a MT5/Telegram/SQL runtime. No avanzar a SQL ledger runtime, Telegram command bot ni MT5 sin fases separadas.
