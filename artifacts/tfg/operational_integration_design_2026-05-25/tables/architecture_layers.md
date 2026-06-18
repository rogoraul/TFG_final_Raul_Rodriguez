# Architecture Layers

| layer | responsibility | producers | consumers | input_contracts | output_contracts | persistence | closure_criteria | prohibited |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| data_state | Report data freshness, latest closed bar and available symbol/timeframe coverage. | data/mt5, SQL, watcher run_meta | live_context_snapshot, dashboard | SQL/run_meta | data_state fields | CSV/JSON metadata | Freshness visible for every symbol. | No execution. |
| enbolsa_live_watcher | Produce ENBOLSA signal_state, watchlist and diagnostic order intents. | live_signal_watcher.py | live_context_snapshot | watcher snapshot/watchlist/order_intents | ENBOLSA state fields | CSV | Parity with watcher v0 states preserved. | No duplicate strategy logic. |
| risk_context | Evaluate candidate intents with RiskGuard and expose risk projections. | RiskGuard | live_context_snapshot, dry_run_bot, dashboard | CandidateSetup/OpenPosition | riskguard fields | CSV/JSON | Every intent has accepted/rejected/not_applicable reason. | No bypassing RiskGuard. |
| wavecount_context | Attach structural context from WaveCount 2.5.6/2.5.10. | WaveCount artifacts | snapshot, dashboard, statistics | phase256_policy_scores | wavecount fields | CSV | Context visible and explicitly non-filtering. | No WaveCount signals. |
| live_context_snapshot | Single source of truth for operational read-only state. | data_state, watcher, risk_context, wavecount_context | dashboard, Telegram, dry-run, statistics | component tables | unified contract | CSV and JSONL optional | All consumers read this contract. | No consumer recalculates strategy. |
| dashboard_read_only | Visualize snapshot, watchlist, risk, WaveCount and data health. | live_context_snapshot | human user | snapshot CSV/JSON | UI state only | local app | No execution controls, all states visible. | No trading buttons. |
| statistics_review | Study ENBOLSA outcomes by WaveCount context. | historical trades + WaveCount context + snapshots | reports/memory | trade_log, phase256 context | stats tables | CSV/plots | Descriptive study with no optimization. | No profitability tuning. |
| telegram_informative | Send deduplicated informative messages from snapshot. | live_context_snapshot | Telegram channel | snapshot rows | messages | logs | Rate-limited, non-operational wording. | No commands. |
| dry_run_bot | Simulate would_accept/would_reject decisions and persist audit log. | live_context_snapshot, RiskGuard | dry-run logs/dashboard | order intents enriched | dry-run decisions | CSV/JSONL | No MT5 calls; full audit trail. | No broker execution. |
| mt5_shadow_demo_live | Future execution path after dry-run. | future broker adapter | future | blocked | blocked |  | Out of v1 scope. | Blocked. |
