USE trading_ops;

CREATE OR REPLACE VIEW v_live_context_latest AS
SELECT
  rows_core.*,
  runs.run_kind,
  runs.data_origin,
  runs.is_operational,
  runs.cutover_at,
  runs.source_snapshot_id
FROM live_context_snapshot_rows rows_core
JOIN snapshot_runs runs
  ON runs.snapshot_id = rows_core.snapshot_id
WHERE runs.status = 'completed'
  AND runs.is_operational = 1
  AND runs.run_kind IN ('bootstrap_current', 'live_observed')
  AND runs.generated_at = (
    SELECT MAX(latest_runs.generated_at)
    FROM snapshot_runs latest_runs
    WHERE latest_runs.status = 'completed'
      AND latest_runs.is_operational = 1
      AND latest_runs.run_kind IN ('bootstrap_current', 'live_observed')
  );

CREATE OR REPLACE VIEW v_data_health_latest AS
SELECT
  health.*,
  runs.run_kind,
  runs.data_origin,
  runs.is_operational,
  runs.cutover_at,
  runs.source_snapshot_id
FROM data_health_snapshot health
JOIN snapshot_runs runs
  ON runs.snapshot_id = health.snapshot_id
WHERE runs.status = 'completed'
  AND runs.is_operational = 1
  AND runs.run_kind IN ('bootstrap_current', 'live_observed')
  AND runs.generated_at = (
    SELECT MAX(latest_runs.generated_at)
    FROM snapshot_runs latest_runs
    WHERE latest_runs.status = 'completed'
      AND latest_runs.is_operational = 1
      AND latest_runs.run_kind IN ('bootstrap_current', 'live_observed')
  );

CREATE OR REPLACE VIEW v_dashboard_trading_center AS
SELECT
  latest.snapshot_id,
  latest.generated_at,
  latest.run_kind,
  latest.data_origin,
  latest.is_operational,
  latest.cutover_at,
  latest.source_snapshot_id,
  latest.symbol,
  latest.market_group,
  latest.strategy,
  registry.family AS strategy_family,
  registry.status AS strategy_status,
  latest.timeframe_ltf,
  latest.timeframe_htf,
  latest.last_closed_bar_time,
  latest.data_freshness_status,
  health.freshness_status AS health_freshness_status,
  latest.signal_state,
  latest.side,
  latest.setup_id,
  latest.entry,
  latest.sl,
  latest.tp1,
  latest.tp2,
  latest.has_order_intent,
  latest.order_intent_id,
  latest.intent_status,
  latest.riskguard_status,
  latest.riskguard_reason,
  latest.riskguard_detail,
  latest.wavecount_available,
  latest.wavecount_policy_bucket,
  latest.wavecount_context_status,
  latest.dry_run_eligible,
  latest.is_read_only,
  latest.can_execute_order,
  latest.wavecount_should_filter_trade,
  latest.payload_json
FROM v_live_context_latest latest
LEFT JOIN strategy_registry registry
  ON registry.strategy_id = latest.strategy
LEFT JOIN v_data_health_latest health
  ON health.symbol = latest.symbol
 AND health.timeframe = latest.timeframe_ltf;

CREATE OR REPLACE VIEW v_dashboard_watchlist AS
SELECT *
FROM v_dashboard_trading_center
WHERE signal_state = 'watching_setup';

CREATE OR REPLACE VIEW v_signal_events_latest AS
SELECT
  events.*,
  runs.run_kind,
  runs.data_origin,
  runs.is_operational,
  runs.cutover_at,
  runs.source_snapshot_id
FROM signal_events events
JOIN snapshot_runs runs
  ON runs.snapshot_id = events.snapshot_id
WHERE runs.status = 'completed'
  AND runs.is_operational = 1
  AND runs.run_kind IN ('bootstrap_current', 'live_observed')
  AND runs.generated_at = (
    SELECT MAX(latest_runs.generated_at)
    FROM snapshot_runs latest_runs
    WHERE latest_runs.status = 'completed'
      AND latest_runs.is_operational = 1
      AND latest_runs.run_kind IN ('bootstrap_current', 'live_observed')
  );

CREATE OR REPLACE VIEW v_bot_config_active AS
SELECT *
FROM bot_config
WHERE is_active = 1
ORDER BY created_at DESC
LIMIT 1;

CREATE OR REPLACE VIEW v_risk_config_active AS
SELECT *
FROM risk_config
WHERE is_active = 1
ORDER BY created_at DESC
LIMIT 1;
