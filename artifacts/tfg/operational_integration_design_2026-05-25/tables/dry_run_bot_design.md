# Dry Run Bot Design

| design_area | specification | v1_guardrail |
| --- | --- | --- |
| input | Read live_context_snapshot rows with has_order_intent=true. | No strategy recalculation. |
| decision | Use intent_status and RiskGuard projection to record would_accept/would_reject/watch_only. | No WaveCount filtering in v1. |
| state | Maintain dry-run open-position ledger independent of MT5. | No real broker positions. |
| logs | Persist dry_run_decisions.csv/jsonl with snapshot_id, order_intent_id, decision, reason and source fields. | No hidden decisions. |
| audit | Every would_accept must include RiskGuard accepted reason and can_execute_order=false. | No order_send. |
| closure | Replay two or more snapshots without MT5 and produce stable deterministic decisions. | No live/demo/shadow. |
