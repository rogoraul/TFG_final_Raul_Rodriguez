from __future__ import annotations

import json
from typing import Any

import pandas as pd


WAVECOUNT_LIVE_COLUMNS = [
    "context_id",
    "generated_at",
    "as_of_bar_time",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "source",
    "data_origin",
    "wavecount_live_available",
    "structure_family",
    "structure_phase",
    "next_phase_hypothesis",
    "direction",
    "degree",
    "hypothesis_status",
    "confidence_bucket",
    "quality_bucket",
    "policy_bucket_256",
    "lookahead_safe",
    "confirmation_lag_bars",
    "detected_at",
    "pivot_confirmed_at",
    "evidence_window_start",
    "evidence_window_end",
    "wave_start_price",
    "wave_end_price",
    "current_price",
    "invalidation_level",
    "distance_to_invalidation_pct",
    "target_zone_1",
    "target_zone_2",
    "prominence_score",
    "ewo_state",
    "ewo_divergence_status",
    "ema_htf_context",
    "trend_context",
    "volatility_context",
    "enbolsa_alignment_status",
    "matched_enbolsa_setup_id",
    "matched_enbolsa_signal_state",
    "is_read_only",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
    "source_artifacts",
    "method_version",
    "notes",
    "payload_json",
]

BOOLEAN_COLUMNS = [
    "wavecount_live_available",
    "lookahead_safe",
    "is_read_only",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
]

ALLOWED_STRUCTURE_PHASES = {
    "possible_wave1",
    "possible_wave2",
    "possible_wave3_candidate",
    "possible_wave3_active",
    "possible_wave4",
    "possible_wave5_candidate",
    "possible_wave5_active",
    "completed_impulse_candidate",
    "possible_waveA",
    "possible_waveB",
    "possible_waveC_candidate",
    "possible_waveC_active",
    "completed_abc_candidate",
    "unknown",
    "ambiguous",
    "invalidated",
    "not_available",
}

ALLOWED_HYPOTHESIS_STATUSES = {
    "forming",
    "provisional",
    "confirmed",
    "invalidated",
    "expired",
}

DEFAULT_ROW: dict[str, Any] = {
    "context_id": "",
    "generated_at": "",
    "as_of_bar_time": "",
    "symbol": "not_available",
    "market_group": "not_available",
    "timeframe": "not_available",
    "higher_timeframe": "not_available",
    "source": "wavecount_live_context_v0",
    "data_origin": "test_fixture",
    "wavecount_live_available": False,
    "structure_family": "unknown",
    "structure_phase": "unknown",
    "next_phase_hypothesis": "not_available",
    "direction": "not_available",
    "degree": "not_available",
    "hypothesis_status": "forming",
    "confidence_bucket": "low",
    "quality_bucket": "not_available",
    "policy_bucket_256": "not_available",
    "lookahead_safe": True,
    "confirmation_lag_bars": 0,
    "detected_at": "",
    "pivot_confirmed_at": "",
    "evidence_window_start": "",
    "evidence_window_end": "",
    "wave_start_price": "",
    "wave_end_price": "",
    "current_price": "",
    "invalidation_level": "",
    "distance_to_invalidation_pct": "",
    "target_zone_1": "",
    "target_zone_2": "",
    "prominence_score": "",
    "ewo_state": "not_available",
    "ewo_divergence_status": "not_available",
    "ema_htf_context": "not_available",
    "trend_context": "not_available",
    "volatility_context": "not_available",
    "enbolsa_alignment_status": "not_applicable",
    "matched_enbolsa_setup_id": "",
    "matched_enbolsa_signal_state": "not_available",
    "is_read_only": True,
    "can_generate_signal": False,
    "can_filter_trade": False,
    "can_execute_order": False,
    "source_artifacts": "",
    "method_version": "wavecount_live_context_v0_fixture_prototype",
    "notes": "",
    "payload_json": "{}",
}


def base_wavecount_live_row(**overrides: Any) -> dict[str, Any]:
    row = dict(DEFAULT_ROW)
    row.update(overrides)
    return row


def normalize_wavecount_live_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column, value in DEFAULT_ROW.items():
        if column not in normalized.columns:
            normalized[column] = value
    normalized = normalized.reindex(columns=WAVECOUNT_LIVE_COLUMNS)
    for column in BOOLEAN_COLUMNS:
        normalized[column] = normalized[column].map(_to_bool)

    normalized["is_read_only"] = True
    normalized["can_generate_signal"] = False
    normalized["can_filter_trade"] = False
    normalized["can_execute_order"] = False
    normalized["lookahead_safe"] = normalized["lookahead_safe"].map(_to_bool)
    normalized["payload_json"] = normalized["payload_json"].map(_json_payload_text)
    _validate_values(normalized)
    return normalized


def schema_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "column_name": column,
                "required": True,
                "default": DEFAULT_ROW.get(column, ""),
            }
            for column in WAVECOUNT_LIVE_COLUMNS
        ]
    )


def validate_hard_flags(frame: pd.DataFrame) -> None:
    normalized = normalize_wavecount_live_frame(frame)
    if not normalized["is_read_only"].all():
        raise ValueError("is_read_only=false is forbidden")
    if normalized["can_generate_signal"].any():
        raise ValueError("can_generate_signal=true is forbidden")
    if normalized["can_filter_trade"].any():
        raise ValueError("can_filter_trade=true is forbidden")
    if normalized["can_execute_order"].any():
        raise ValueError("can_execute_order=true is forbidden")


def _validate_values(frame: pd.DataFrame) -> None:
    invalid_phases = set(frame["structure_phase"]) - ALLOWED_STRUCTURE_PHASES
    if invalid_phases:
        raise ValueError(f"Unknown structure_phase values: {sorted(invalid_phases)}")
    invalid_statuses = set(frame["hypothesis_status"]) - ALLOWED_HYPOTHESIS_STATUSES
    if invalid_statuses:
        raise ValueError(f"Unknown hypothesis_status values: {sorted(invalid_statuses)}")


def _json_payload_text(value: object) -> str:
    if value is None:
        return "{}"
    if isinstance(value, float) and pd.isna(value):
        return "{}"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    text = str(value).strip()
    if not text:
        return "{}"
    json.loads(text)
    return text


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si"}
