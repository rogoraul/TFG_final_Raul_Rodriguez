# User Decisions Needed

| decision | needed_before_implementation | recommended_default | why_it_matters |
| --- | --- | --- | --- |
| approve_phase_1_first | True | Implement live_context_snapshot_v0 before dashboard. | Keeps all downstream consumers aligned. |
| dashboard_stack | True | Choose simple local dashboard stack when Phase 2 begins. | Affects implementation, not the contract. |
| telegram_channel_policy | True | Define recipient/channel and wording restrictions before Telegram v1. | Avoids operational ambiguity. |
| dry_run_position_source | True | Decide how dry-run ledger starts and resets. | RiskGuard needs open-position state. |
| wavecount_mapping_tolerance | False | Accept conservative no-context fallback for missing WaveCount. | Prevents forcing structural context. |
