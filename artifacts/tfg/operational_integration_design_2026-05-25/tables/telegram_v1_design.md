# Telegram V1 Design

| message_type | event_source | payload_summary | deduplication | frequency_limit | forbidden_capability |
| --- | --- | --- | --- | --- | --- |
| fresh_signal | entry_ready_new with order intent | Signal fresh, RiskGuard status, WaveCount context badge, explicit read-only wording. | telegram_dedup_key + seen registry | Per symbol/setup event only once; session summary throttled. | No /buy, /sell, /close or order commands. |
| watchlist_summary | watching_setup | Top watchlist setups and missing confirmations. | snapshot_id + symbol/setup | At session boundaries or manual run summary. | No operational recommendation wording. |
| riskguard_rejection | riskguard_rejected | Rejected reason and projected risk. | order_intent_id | Once per intent. | No override command. |
| data_stale | stale data freshness | Symbols/timeframes stale. | symbol/timeframe/day | Limited frequency. | No attempt to reconnect MT5 from Telegram. |
| wavecount_context_note | significant context/warning attached to watched setup | WaveCount status as context only. | snapshot_id + candidate id | Only if tied to ENBOLSA watch/signal. | No WaveCount-only trade alert. |
