# Bot Dry-Run V1 Review

Fecha: 2026-05-29

Decision: `bot_dry_run_v1_review_passed`.

## Resumen

Se audita `bot_dry_run_v1` tras la implementacion artifact-first. La revision confirma que el modulo genera ledger local, mantiene defaults fail-closed y no tiene superficie de ejecucion accidental.

No se conecta MT5, no se conecta Telegram, no se escribe SQL real, no se ejecutan backtests y no se generan senales nuevas.

## Ledger Y Contrato

- Ledger default: `54` filas.
- CSV/JSON: mismo numero de filas.
- `payload_json`: valido en todas las filas.
- `dry_run_event_id`: unico en todas las filas.
- Columnas minimas del contrato: presentes.

## Default Fail-Closed

El run real default mantiene:

- `bot_enabled=false`.
- `mode=off`.
- Distribucion: `{"dry_run_blocked_by_config": 54}`.
- `can_execute_order=false` en todas las filas.
- `would_send_to_mt5=false` en todas las filas.
- `would_send_telegram_order=false` en todas las filas.

Este comportamiento es correcto: bloquea por configuracion antes de interpretar cualquier fila como simulable.

## Simulacion Enabled Sobre Snapshot Real

Se ejecuto una segunda simulacion con `--bot-enabled --mode dry_run --max-intents 5` sobre el snapshot real. Resultado:

- Distribucion: `{"dry_run_no_action": 54}`.
- Intents simulados: `0`.

Esto confirma que el snapshot actual, al estar compuesto por `watching_setup`, no crea intents ni siquiera con el bot dry-run habilitado.

## Tests Y Fixtures

Validacion ejecutada:

- `python -m py_compile trading_center\bot_dry_run.py`.
- `pytest tests\test_bot_dry_run.py tests\test_live_context_snapshot.py -q` -> `20 passed`.

Los fixtures cubren default bloqueado, hard flags, stale data, RiskGuard rejected, RiskGuard accepted como simulated intent, `max_intents`, snapshot vacio, payload JSON y WaveCount no filtro.

## WaveCount

WaveCount se conserva solo como contexto en `wavecount_context_summary`. La auditoria y los tests confirman que cambiar campos WaveCount no cambia `dry_run_decision` y que `wavecount_used_as_filter=false`.

## Limites Telegram/MT5/SQL

- No existe Telegram command bot en esta fase.
- No hay mensajes u ordenes Telegram.
- No hay MT5 adapter ni conexion.
- No hay SQL writes ni DDL.
- No se crea ledger SQL runtime.
- El ledger sigue siendo artifact-first.

## Riesgos Residuales

- SQL runtime ledger sigue pendiente y requiere fase separada.
- El snapshot real no tiene `entry_ready_new`; los intents positivos solo estan probados con fixtures.
- Telegram command bot read-only sigue pendiente como fase separada.

## Siguiente Paso

La fase queda aprobada para conservar `bot_dry_run_v1` como artifact-only. El siguiente paso recomendado es decidir si se revisa/refina la plataforma v2 o si se disena una fase SQL runtime ledger separada. No pasar aun a MT5 ni a Telegram command bot.
