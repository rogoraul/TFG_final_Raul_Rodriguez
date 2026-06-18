from __future__ import annotations

from typing import Any

import pandas as pd


SNAPSHOT_COLUMNS = [
    "snapshot_id",
    "generated_at",
    "symbol",
    "market_group",
    "strategy",
    "timeframe_ltf",
    "timeframe_htf",
    "last_closed_bar_time",
    "data_freshness_status",
    "signal_state",
    "side",
    "setup_id",
    "entry",
    "sl",
    "tp1",
    "tp2",
    "setup_age",
    "missing_confirmation",
    "enbolsa_reason",
    "has_order_intent",
    "order_intent_id",
    "intent_status",
    "riskguard_status",
    "riskguard_reason",
    "riskguard_detail",
    "candidate_risk_pct",
    "projected_total_risk_pct",
    "projected_symbol_risk_pct",
    "projected_currency_gross_risk_pct",
    "projected_currency_net_risk_pct",
    "wavecount_available",
    "wavecount_primary_timeframe",
    "wavecount_aux_timeframe",
    "wavecount_structure_type",
    "wavecount_wave_role",
    "wavecount_degree",
    "wavecount_policy_bucket",
    "wavecount_context_status",
    "wavecount_should_filter_trade",
    "wavecount_notes",
    "dashboard_priority",
    "dashboard_group",
    "needs_user_attention",
    "display_status",
    "telegram_should_notify",
    "telegram_message_type",
    "telegram_dedup_key",
    "dry_run_eligible",
    "dry_run_reason",
    "dry_run_action",
    "is_read_only",
    "can_execute_order",
    "source_files",
    "notes",
]


BOOLEAN_COLUMNS = [
    "has_order_intent",
    "wavecount_available",
    "wavecount_should_filter_trade",
    "needs_user_attention",
    "telegram_should_notify",
    "dry_run_eligible",
    "is_read_only",
    "can_execute_order",
]


DEFAULT_ROW: dict[str, Any] = {
    "snapshot_id": "",
    "generated_at": "",
    "symbol": "not_available",
    "market_group": "not_available",
    "strategy": "enbolsa:macd_breakout",
    "timeframe_ltf": "not_available",
    "timeframe_htf": "not_available",
    "last_closed_bar_time": "not_available",
    "data_freshness_status": "not_available",
    "signal_state": "no_signal",
    "side": "not_available",
    "setup_id": "not_available",
    "entry": "not_available",
    "sl": "not_available",
    "tp1": "not_available",
    "tp2": "not_available",
    "setup_age": "not_available",
    "missing_confirmation": "none",
    "enbolsa_reason": "not_available",
    "has_order_intent": False,
    "order_intent_id": "not_applicable",
    "intent_status": "not_applicable",
    "riskguard_status": "not_evaluated",
    "riskguard_reason": "not_available",
    "riskguard_detail": "not_available",
    "candidate_risk_pct": "not_available",
    "projected_total_risk_pct": "not_available",
    "projected_symbol_risk_pct": "not_available",
    "projected_currency_gross_risk_pct": "not_available",
    "projected_currency_net_risk_pct": "not_available",
    "wavecount_available": False,
    "wavecount_primary_timeframe": "not_available",
    "wavecount_aux_timeframe": "not_available",
    "wavecount_structure_type": "not_available",
    "wavecount_wave_role": "not_available",
    "wavecount_degree": "not_available",
    "wavecount_policy_bucket": "not_available",
    "wavecount_context_status": "not_available",
    "wavecount_should_filter_trade": False,
    "wavecount_notes": "not_available",
    "dashboard_priority": "low",
    "dashboard_group": "not_available",
    "needs_user_attention": False,
    "display_status": "not_available",
    "telegram_should_notify": False,
    "telegram_message_type": "none",
    "telegram_dedup_key": "not_applicable",
    "dry_run_eligible": False,
    "dry_run_reason": "not_implemented",
    "dry_run_action": "none",
    "is_read_only": True,
    "can_execute_order": False,
    "source_files": "",
    "notes": "",
}


def base_row(**overrides: Any) -> dict[str, Any]:
    row = dict(DEFAULT_ROW)
    row.update(overrides)
    return row


def normalize_snapshot_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column, value in DEFAULT_ROW.items():
        if column not in normalized.columns:
            normalized[column] = value
    normalized = normalized.reindex(columns=SNAPSHOT_COLUMNS)
    for column in BOOLEAN_COLUMNS:
        normalized[column] = normalized[column].map(_to_bool)
    normalized["is_read_only"] = True
    normalized["can_execute_order"] = False
    normalized["wavecount_should_filter_trade"] = False
    return normalized


def empty_snapshot_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=SNAPSHOT_COLUMNS)


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "accepted", "si"}
