# TFG Operational Integration Design v1

Especificacion maestra para integrar ENBOLSA, RiskGuard, WaveCount, dashboard, estadistica, Telegram y dry-run sin ejecucion real.

## Principio central

`live_context_snapshot` es la fuente unica de verdad. Dashboard, Telegram, estadistica y dry-run deben consumirlo o derivar de el, sin duplicar logica de estrategia.

## Que se implementa primero

- fase: `1_live_context_snapshot_v0`
- objetivo: Unify Watcher + RiskGuard + WaveCount context into CSV/JSON.
- cierre: All required columns exist; can_execute_order=false; no strategy changes.

## Componentes existentes

| component | current_status | role_in_v1 | gaps_for_v1 |
| --- | --- | --- | --- |
| Watcher ENBOLSA v0 | implemented_read_only | Primary producer of ENBOLSA signal_state/watchlist/order_intent context. | Needs unified snapshot_id, freshness normalization, enriched WaveCount context and stable current/open-position source for dry-run. |
| RiskGuard operativo | implemented_not_integrated | Only risk authority for intents and dry-run decisions. | Needs source of current dry-run/open positions; no broker state yet. |
| WaveCount 2.5.x | methodological_context_closed | Read-only structural context and statistical study variable. | Needs mapping from live symbol/timeframe to latest applicable structural context; no filtering allowed. |
| ENBOLSA final artifacts | closed_empirical_source | Statistical baseline and historical study source. | Historical join with WaveCount context is not implemented yet. |
| Menendez | methodological_closed_non_operational | Academic reference, not v1 operational feed. | Only enter platform if user explicitly reopens it. |
| MT5/data | data_ingestion_only | Data freshness/source health only. | No order_send, no positions_get, no broker adapter, no live execution contract. |

## Capas de arquitectura

| layer | responsibility | consumers | prohibited |
| --- | --- | --- | --- |
| data_state | Report data freshness, latest closed bar and available symbol/timeframe coverage. | live_context_snapshot, dashboard | No execution. |
| enbolsa_live_watcher | Produce ENBOLSA signal_state, watchlist and diagnostic order intents. | live_context_snapshot | No duplicate strategy logic. |
| risk_context | Evaluate candidate intents with RiskGuard and expose risk projections. | live_context_snapshot, dry_run_bot, dashboard | No bypassing RiskGuard. |
| wavecount_context | Attach structural context from WaveCount 2.5.6/2.5.10. | snapshot, dashboard, statistics | No WaveCount signals. |
| live_context_snapshot | Single source of truth for operational read-only state. | dashboard, Telegram, dry-run, statistics | No consumer recalculates strategy. |
| dashboard_read_only | Visualize snapshot, watchlist, risk, WaveCount and data health. | human user | No trading buttons. |
| statistics_review | Study ENBOLSA outcomes by WaveCount context. | reports/memory | No profitability tuning. |
| telegram_informative | Send deduplicated informative messages from snapshot. | Telegram channel | No commands. |
| dry_run_bot | Simulate would_accept/would_reject decisions and persist audit log. | dry-run logs/dashboard | No broker execution. |
| mt5_shadow_demo_live | Future execution path after dry-run. | future | Blocked. |

## Fases

| phase | objective | outputs | prohibited |
| --- | --- | --- | --- |
| 1_live_context_snapshot_v0 | Unify Watcher + RiskGuard + WaveCount context into CSV/JSON. | live_context_snapshot.csv/json; run_meta | No dashboard/Telegram/bot yet. |
| 2_dashboard_read_only_v1 | Build mandatory dashboard consuming snapshot. | local read-only UI | No recalculating strategy in UI. |
| 3_statistics_enbolsa_wavecount | Study ENBOLSA outcomes by WaveCount context. | descriptive tables/figures | No filter adoption automatically. |
| 4_telegram_informative | Send read-only messages from snapshot. | Telegram logs/messages | No trading commands. |
| 5_dry_run_bot | Simulate would_accept/would_reject decisions. | dry_run_decisions.csv/jsonl | No broker adapter. |
| 6_mt5_shadow_demo_future | Future MT5 shadow/demo after dry-run closure. | future broker logs | Blocked now. |

## No hacer todavia

| item | reason | policy |
| --- | --- | --- |
| generate_new_signals | No new strategy logic in design or v1 snapshot. | blocked |
| use_wavecount_as_filter | WaveCount is context/statistical variable only. | blocked |
| dashboard_recalculate_strategy | Dashboard must consume snapshot only. | blocked |
| telegram_trading_commands | Telegram v1 is informative only. | blocked |
| dry_run_connect_mt5 | Dry-run must avoid MT5 completely. | blocked |
| mt5_shadow_demo_live | Requires future phase after dry-run closure and explicit approval. | blocked |
| optimize_by_profitability | Statistics cannot tune thresholds by return. | blocked |
| include_menendez_operationally | Menendez remains methodological unless user reopens it. | defer |
