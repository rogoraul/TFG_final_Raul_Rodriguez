CREATE SCHEMA IF NOT EXISTS trading_ops
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE trading_ops;

CREATE TABLE IF NOT EXISTS schema_migrations (
  migration_id VARCHAR(128) NOT NULL,
  checksum VARCHAR(128) NULL,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  description TEXT NULL,
  PRIMARY KEY (migration_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS snapshot_runs (
  snapshot_id VARCHAR(96) NOT NULL,
  generated_at DATETIME(6) NOT NULL,
  snapshot_version VARCHAR(64) NOT NULL DEFAULT 'live_context_snapshot_v0',
  producer VARCHAR(128) NOT NULL DEFAULT 'trading_center.sql_loader',
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  run_kind VARCHAR(32) NOT NULL DEFAULT 'bootstrap_current',
  data_origin VARCHAR(64) NOT NULL DEFAULT 'live_context_snapshot_v0',
  is_operational TINYINT(1) NOT NULL DEFAULT 1,
  cutover_at DATETIME(6) NULL,
  source_snapshot_id VARCHAR(96) NULL,
  row_count INT NOT NULL DEFAULT 0,
  order_intent_count INT NOT NULL DEFAULT 0,
  riskguard_count INT NOT NULL DEFAULT 0,
  wavecount_available_count INT NOT NULL DEFAULT 0,
  is_read_only TINYINT(1) NOT NULL DEFAULT 1,
  can_execute_order TINYINT(1) NOT NULL DEFAULT 0,
  wavecount_should_filter_trade TINYINT(1) NOT NULL DEFAULT 0,
  notes TEXT NULL,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (snapshot_id),
  KEY idx_snapshot_runs_generated_at (generated_at),
  KEY idx_snapshot_runs_status (status),
  KEY idx_snapshot_runs_operational (is_operational, run_kind, generated_at),
  CHECK (is_read_only = 1),
  CHECK (can_execute_order = 0),
  CHECK (wavecount_should_filter_trade = 0),
  CHECK (run_kind IN ('bootstrap_current', 'live_observed', 'historical_backfill', 'test_fixture')),
  CHECK (
    (run_kind IN ('bootstrap_current', 'live_observed') AND is_operational = 1)
    OR (run_kind IN ('historical_backfill', 'test_fixture') AND is_operational = 0)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS live_context_snapshot_rows (
  row_id BIGINT NOT NULL AUTO_INCREMENT,
  snapshot_id VARCHAR(96) NOT NULL,
  generated_at DATETIME(6) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  market_group VARCHAR(64) NOT NULL DEFAULT 'not_available',
  strategy VARCHAR(96) NOT NULL DEFAULT 'macd_breakout',
  timeframe_ltf VARCHAR(16) NOT NULL,
  timeframe_htf VARCHAR(16) NOT NULL,
  last_closed_bar_time DATETIME(6) NULL,
  data_freshness_status VARCHAR(32) NOT NULL DEFAULT 'not_available',
  signal_state VARCHAR(32) NOT NULL DEFAULT 'no_signal',
  side VARCHAR(32) NOT NULL DEFAULT 'not_available',
  setup_id VARCHAR(96) NOT NULL DEFAULT 'not_available',
  entry DECIMAL(18,8) NULL,
  sl DECIMAL(18,8) NULL,
  tp1 DECIMAL(18,8) NULL,
  tp2 DECIMAL(18,8) NULL,
  has_order_intent TINYINT(1) NOT NULL DEFAULT 0,
  order_intent_id VARCHAR(192) NOT NULL DEFAULT 'not_applicable',
  intent_status VARCHAR(32) NOT NULL DEFAULT 'not_applicable',
  riskguard_status VARCHAR(32) NOT NULL DEFAULT 'not_evaluated',
  riskguard_reason TEXT NULL,
  riskguard_detail TEXT NULL,
  wavecount_available TINYINT(1) NOT NULL DEFAULT 0,
  wavecount_policy_bucket VARCHAR(64) NOT NULL DEFAULT 'not_available',
  wavecount_context_status VARCHAR(64) NOT NULL DEFAULT 'not_available',
  dry_run_eligible TINYINT(1) NOT NULL DEFAULT 0,
  is_read_only TINYINT(1) NOT NULL DEFAULT 1,
  can_execute_order TINYINT(1) NOT NULL DEFAULT 0,
  wavecount_should_filter_trade TINYINT(1) NOT NULL DEFAULT 0,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (row_id),
  UNIQUE KEY uq_snapshot_context_row (
    snapshot_id,
    symbol,
    strategy,
    timeframe_ltf,
    timeframe_htf,
    side,
    setup_id
  ),
  KEY idx_live_context_snapshot_id (snapshot_id),
  KEY idx_live_context_symbol (symbol),
  KEY idx_live_context_strategy (strategy),
  KEY idx_live_context_signal_state (signal_state),
  KEY idx_live_context_order_intent (has_order_intent, order_intent_id),
  CONSTRAINT fk_live_context_snapshot_runs
    FOREIGN KEY (snapshot_id) REFERENCES snapshot_runs(snapshot_id),
  CHECK (is_read_only = 1),
  CHECK (can_execute_order = 0),
  CHECK (wavecount_should_filter_trade = 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS snapshot_source_inventory (
  inventory_id BIGINT NOT NULL AUTO_INCREMENT,
  snapshot_id VARCHAR(96) NOT NULL,
  source_name VARCHAR(128) NOT NULL,
  source_path TEXT NOT NULL,
  source_role VARCHAR(64) NOT NULL,
  exists_flag TINYINT(1) NOT NULL DEFAULT 0,
  row_count INT NOT NULL DEFAULT 0,
  checksum VARCHAR(128) NULL,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (inventory_id),
  UNIQUE KEY uq_snapshot_source (snapshot_id, source_name),
  KEY idx_snapshot_source_snapshot_id (snapshot_id),
  CONSTRAINT fk_snapshot_source_runs
    FOREIGN KEY (snapshot_id) REFERENCES snapshot_runs(snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS strategy_registry (
  strategy_id VARCHAR(96) NOT NULL,
  family VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'inactive',
  can_generate_signals TINYINT(1) NOT NULL DEFAULT 0,
  can_enter_dry_run TINYINT(1) NOT NULL DEFAULT 0,
  can_execute_live TINYINT(1) NOT NULL DEFAULT 0,
  description TEXT NULL,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (strategy_id),
  KEY idx_strategy_registry_family (family),
  KEY idx_strategy_registry_status (status),
  CHECK (can_execute_live = 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS signal_events (
  signal_event_id BIGINT NOT NULL AUTO_INCREMENT,
  snapshot_id VARCHAR(96) NOT NULL,
  event_key VARCHAR(192) NOT NULL,
  dedup_key VARCHAR(192) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  strategy VARCHAR(96) NOT NULL,
  side VARCHAR(32) NOT NULL,
  signal_state VARCHAR(32) NOT NULL,
  order_intent_id VARCHAR(192) NOT NULL DEFAULT 'not_applicable',
  event_status VARCHAR(32) NOT NULL DEFAULT 'watching_setup',
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (signal_event_id),
  UNIQUE KEY uq_signal_events_dedup (dedup_key),
  KEY idx_signal_events_snapshot_id (snapshot_id),
  KEY idx_signal_events_symbol (symbol),
  KEY idx_signal_events_state (signal_state),
  CONSTRAINT fk_signal_events_snapshot_runs
    FOREIGN KEY (snapshot_id) REFERENCES snapshot_runs(snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS risk_config (
  risk_config_id BIGINT NOT NULL AUTO_INCREMENT,
  version VARCHAR(64) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 0,
  risk_per_trade_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
  max_total_open_risk_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
  max_symbol_open_risk_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
  max_currency_gross_risk_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
  max_currency_net_risk_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
  max_open_trades INT NOT NULL DEFAULT 0,
  kill_switch_enabled TINYINT(1) NOT NULL DEFAULT 1,
  notes TEXT NULL,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (risk_config_id),
  UNIQUE KEY uq_risk_config_version (version),
  KEY idx_risk_config_active (is_active),
  CHECK (kill_switch_enabled = 1 OR is_active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bot_config (
  bot_config_id BIGINT NOT NULL AUTO_INCREMENT,
  version VARCHAR(64) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 0,
  bot_enabled TINYINT(1) NOT NULL DEFAULT 0,
  mode VARCHAR(32) NOT NULL DEFAULT 'off',
  allowed_strategies_json JSON NULL,
  allowed_symbols_json JSON NULL,
  requires_manual_approval TINYINT(1) NOT NULL DEFAULT 1,
  mt5_enabled TINYINT(1) NOT NULL DEFAULT 0,
  live_enabled TINYINT(1) NOT NULL DEFAULT 0,
  notes TEXT NULL,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (bot_config_id),
  UNIQUE KEY uq_bot_config_version (version),
  KEY idx_bot_config_active (is_active),
  CHECK (bot_enabled = 0 OR mode IN ('watch_only', 'dry_run')),
  CHECK (mode IN ('off', 'watch_only', 'dry_run', 'shadow_future', 'demo_future', 'live_future')),
  CHECK (mt5_enabled = 0),
  CHECK (live_enabled = 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS data_health_snapshot (
  data_health_id BIGINT NOT NULL AUTO_INCREMENT,
  snapshot_id VARCHAR(96) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  timeframe VARCHAR(16) NOT NULL,
  last_closed_bar_time DATETIME(6) NULL,
  freshness_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
  source_name VARCHAR(64) NOT NULL DEFAULT 'live_context_snapshot_v0',
  missing_bars_count INT NOT NULL DEFAULT 0,
  notes TEXT NULL,
  payload_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (data_health_id),
  UNIQUE KEY uq_data_health_snapshot (snapshot_id, symbol, timeframe),
  KEY idx_data_health_snapshot_id (snapshot_id),
  KEY idx_data_health_symbol_timeframe (symbol, timeframe),
  CONSTRAINT fk_data_health_snapshot_runs
    FOREIGN KEY (snapshot_id) REFERENCES snapshot_runs(snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
