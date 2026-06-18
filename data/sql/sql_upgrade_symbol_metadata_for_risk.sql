ALTER TABLE symbol_metadata
    ADD COLUMN IF NOT EXISTS trade_tick_size DECIMAL(20,10) NULL AFTER point_size,
    ADD COLUMN IF NOT EXISTS trade_tick_value DECIMAL(20,10) NULL AFTER trade_tick_size,
    ADD COLUMN IF NOT EXISTS trade_tick_value_profit DECIMAL(20,10) NULL AFTER trade_tick_value,
    ADD COLUMN IF NOT EXISTS trade_tick_value_loss DECIMAL(20,10) NULL AFTER trade_tick_value_profit,
    ADD COLUMN IF NOT EXISTS trade_contract_size DECIMAL(20,10) NULL AFTER trade_tick_value_loss,
    ADD COLUMN IF NOT EXISTS volume_min DECIMAL(20,10) NULL AFTER trade_contract_size,
    ADD COLUMN IF NOT EXISTS volume_max DECIMAL(20,10) NULL AFTER volume_min,
    ADD COLUMN IF NOT EXISTS volume_step DECIMAL(20,10) NULL AFTER volume_max,
    ADD COLUMN IF NOT EXISTS currency_base VARCHAR(16) NULL AFTER volume_step,
    ADD COLUMN IF NOT EXISTS currency_profit VARCHAR(16) NULL AFTER currency_base,
    ADD COLUMN IF NOT EXISTS currency_margin VARCHAR(16) NULL AFTER currency_profit,
    ADD COLUMN IF NOT EXISTS trade_mode INT NULL AFTER currency_margin;
