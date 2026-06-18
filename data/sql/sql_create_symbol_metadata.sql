CREATE TABLE IF NOT EXISTS symbol_metadata (
    symbol VARCHAR(64) NOT NULL,
    digits INT NOT NULL,
    point_size DECIMAL(20,10) NOT NULL,
    trade_tick_size DECIMAL(20,10) NULL,
    trade_tick_value DECIMAL(20,10) NULL,
    trade_tick_value_profit DECIMAL(20,10) NULL,
    trade_tick_value_loss DECIMAL(20,10) NULL,
    trade_contract_size DECIMAL(20,10) NULL,
    volume_min DECIMAL(20,10) NULL,
    volume_max DECIMAL(20,10) NULL,
    volume_step DECIMAL(20,10) NULL,
    currency_base VARCHAR(16) NULL,
    currency_profit VARCHAR(16) NULL,
    currency_margin VARCHAR(16) NULL,
    trade_mode INT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'MT5',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol),
    KEY idx_symbol_metadata_updated_at (updated_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
