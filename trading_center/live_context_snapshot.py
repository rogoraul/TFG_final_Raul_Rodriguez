"""Build the read-only live context snapshot consumed by Trading Center."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from trading_center.snapshot_schema import SNAPSHOT_COLUMNS, base_row, normalize_snapshot_frame
from trading_center.snapshot_store import write_snapshot_artifacts


DEFAULT_WATCHER_DIR = Path("artifacts/live-signal-watcher/enbolsa_macd_breakout_v0")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/live_context_snapshot_v0")
DEFAULT_CONTRACT_PATH = Path("artifacts/tfg/operational_integration_design_2026-05-25/tables/live_context_snapshot_contract.csv")
DEFAULT_WAVECOUNT_POLICY_DIR = Path("artifacts/wavecount/05_guided_profile/phase2_5_6_soft_policy_weight_adjustment_2026-05-24")
DEFAULT_WAVECOUNT_ROBUST_DIR = Path("artifacts/wavecount/05_guided_profile/phase2_5_9_robust_prominence_policy_trial_2026-05-24")
DEFAULT_WAVECOUNT_CLOSURE_DIR = Path("artifacts/wavecount/05_guided_profile/phase2_5_10_guided_profile_closure_2026-05-24")


@dataclass(frozen=True)
class LiveContextSnapshotConfig:
    """Input/output artifact locations for one snapshot build."""
    watcher_dir: Path = DEFAULT_WATCHER_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    contract_path: Path = DEFAULT_CONTRACT_PATH
    wavecount_policy_dir: Path = DEFAULT_WAVECOUNT_POLICY_DIR
    wavecount_robust_dir: Path = DEFAULT_WAVECOUNT_ROBUST_DIR
    wavecount_closure_dir: Path = DEFAULT_WAVECOUNT_CLOSURE_DIR


@dataclass(frozen=True)
class LiveContextSnapshotResult:
    """Snapshot build result plus written artifact paths."""
    snapshot: pd.DataFrame
    run_meta: dict[str, Any]
    source_inventory: pd.DataFrame
    schema: pd.DataFrame
    written_files: dict[str, Path]


def build_live_context_snapshot(config: LiveContextSnapshotConfig | None = None) -> LiveContextSnapshotResult:
    """Build and persist a normalized read-only live context snapshot."""
    config = config or LiveContextSnapshotConfig()
    repo_root = _repo_root()
    watcher_dir = _resolve(repo_root, config.watcher_dir)
    output_dir = _resolve(repo_root, config.output_dir)
    contract_path = _resolve(repo_root, config.contract_path)
    policy_dir = _resolve(repo_root, config.wavecount_policy_dir)
    robust_dir = _resolve(repo_root, config.wavecount_robust_dir)
    closure_dir = _resolve(repo_root, config.wavecount_closure_dir)

    generated_at = datetime.now().isoformat(timespec="seconds")
    snapshot_id = f"live_context_snapshot_v0_{generated_at.replace(':', '').replace('-', '')}"

    watcher = _load_watcher_outputs(watcher_dir)
    schema = _read_csv(contract_path)
    wavecount = _load_wavecount_context(policy_dir, robust_dir)
    closure_policy = _read_csv(closure_dir / "tables" / "phase25_final_policy_matrix.csv")
    source_inventory = _build_source_inventory(
        watcher_dir=watcher_dir,
        contract_path=contract_path,
        policy_dir=policy_dir,
        robust_dir=robust_dir,
        closure_dir=closure_dir,
        watcher=watcher,
        schema=schema,
        wavecount_policy_rows=len(wavecount.policy_frame),
        wavecount_robust_rows=len(wavecount.robust_frame),
        wavecount_closure_rows=len(closure_policy),
    )

    source_files = ";".join(
        str(path) for path in source_inventory.loc[source_inventory["exists"], "path"].tolist()
    )
    snapshot_frame = _assemble_snapshot(
        watcher=watcher,
        wavecount=wavecount,
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        source_files=source_files,
    )
    normalized = normalize_snapshot_frame(snapshot_frame)

    run_meta = {
        "generated_at": generated_at,
        "snapshot_id": snapshot_id,
        "version": "live_context_snapshot_v0",
        "rows": int(len(normalized)),
        "rows_with_order_intent": int(normalized["has_order_intent"].sum()) if not normalized.empty else 0,
        "rows_with_riskguard": int((normalized["riskguard_status"] != "not_evaluated").sum()) if not normalized.empty else 0,
        "rows_with_wavecount_available": int(normalized["wavecount_available"].sum()) if not normalized.empty else 0,
        "flags": {
            "is_read_only": True,
            "can_execute_order": False,
            "wavecount_should_filter_trade": False,
        },
        "sources": source_inventory.to_dict(orient="records"),
        "limitations": [
            "Consumes existing read-only watcher outputs; it does not run the watcher.",
            "WaveCount 2.5.6 is used as official context; 2.5.9 is diagnostic only.",
            "Missing WaveCount context never blocks or promotes ENBOLSA rows.",
            "RiskGuard is represented as diagnostic context and never grants execution permission.",
        ],
    }
    written = write_snapshot_artifacts(
        normalized,
        output_dir,
        run_meta=run_meta,
        schema=schema if not schema.empty else pd.DataFrame({"column": SNAPSHOT_COLUMNS}),
        source_inventory=source_inventory,
    )
    return LiveContextSnapshotResult(
        snapshot=normalized,
        run_meta=run_meta,
        source_inventory=source_inventory,
        schema=schema,
        written_files=written,
    )


@dataclass(frozen=True)
class WatcherOutputs:
    """Loaded watcher artifacts used as the snapshot source."""
    snapshot: pd.DataFrame
    watchlist: pd.DataFrame
    order_intents: pd.DataFrame
    riskguard_decisions: pd.DataFrame
    run_meta: dict[str, Any]
    files: dict[str, Path]


@dataclass(frozen=True)
class WaveCountContext:
    """WaveCount context tables indexed for snapshot enrichment."""
    policy_frame: pd.DataFrame
    robust_frame: pd.DataFrame
    official_by_symbol: dict[str, dict[str, Any]]
    aux_timeframe_by_symbol: dict[str, str]
    robust_note_by_symbol: dict[str, str]


def _load_watcher_outputs(watcher_dir: Path) -> WatcherOutputs:
    files = {
        "snapshot": watcher_dir / "snapshot.csv",
        "watchlist": watcher_dir / "watchlist.csv",
        "order_intents": watcher_dir / "order_intents.csv",
        "riskguard_decisions": watcher_dir / "riskguard_decisions.csv",
        "run_meta": watcher_dir / "run_meta.json",
    }
    return WatcherOutputs(
        snapshot=_read_csv(files["snapshot"]),
        watchlist=_read_csv(files["watchlist"]),
        order_intents=_read_csv(files["order_intents"]),
        riskguard_decisions=_read_csv(files["riskguard_decisions"]),
        run_meta=_read_json(files["run_meta"]),
        files=files,
    )


def _load_wavecount_context(policy_dir: Path, robust_dir: Path) -> WaveCountContext:
    policy_frame = _read_csv(policy_dir / "tables" / "phase256_policy_scores.csv")
    robust_frame = _read_csv(robust_dir / "tables" / "phase259_candidate_policy_scores.csv")
    official_by_symbol = _select_official_wavecount_rows(policy_frame)
    aux_timeframe_by_symbol = _select_aux_timeframes(policy_frame)
    robust_note_by_symbol = _select_robust_notes(robust_frame)
    return WaveCountContext(
        policy_frame=policy_frame,
        robust_frame=robust_frame,
        official_by_symbol=official_by_symbol,
        aux_timeframe_by_symbol=aux_timeframe_by_symbol,
        robust_note_by_symbol=robust_note_by_symbol,
    )


def _assemble_snapshot(
    *,
    watcher: WatcherOutputs,
    wavecount: WaveCountContext,
    snapshot_id: str,
    generated_at: str,
    source_files: str,
) -> pd.DataFrame:
    if watcher.snapshot.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    watchlist_by_key = {
        _row_key(row): row.to_dict()
        for _, row in watcher.watchlist.iterrows()
    }
    intents_by_event = {
        _text(row.get("event_key")): row.to_dict()
        for _, row in watcher.order_intents.iterrows()
        if _text(row.get("event_key"))
    }
    decisions_by_key = {
        _decision_key(row): row.to_dict()
        for _, row in watcher.riskguard_decisions.iterrows()
    }

    rows: list[dict[str, Any]] = []
    for _, row in watcher.snapshot.iterrows():
        raw = row.to_dict()
        event_key = _text(raw.get("event_key"))
        intent = intents_by_event.get(event_key, {})
        decision = decisions_by_key.get(_decision_key(raw), {})
        watchlist_row = watchlist_by_key.get(_row_key(raw), {})
        symbol = _text(raw.get("symbol"), "not_available")
        signal_state = _text(raw.get("signal_state"), "no_signal")
        has_order_intent = bool(intent)
        riskguard_status, riskguard_reason, riskguard_detail = _riskguard_status(raw, intent)
        projected = _projected_risk_values(decision, symbol)
        side = _text(raw.get("side"), "not_available")
        wave = _wavecount_values(symbol, wavecount, side=side)

        rows.append(base_row(
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            symbol=symbol,
            market_group=_text(raw.get("Group") or raw.get("group") or wave.get("market_group"), "not_available"),
            strategy=_text(raw.get("strategy"), "enbolsa:macd_breakout"),
            timeframe_ltf=_text(raw.get("timeframe_ltf"), "not_available"),
            timeframe_htf=_text(raw.get("timeframe_htf"), "not_available"),
            last_closed_bar_time=_text(raw.get("timestamp"), "not_available"),
            data_freshness_status=_freshness_status(raw),
            signal_state=signal_state,
            side=side,
            setup_id=_text(raw.get("setup_id"), "not_available"),
            entry=_first_available(intent.get("entry"), raw.get("entry")),
            sl=_first_available(intent.get("sl"), raw.get("sl")),
            tp1=_first_available(intent.get("tp1"), raw.get("tp1")),
            tp2=_first_available(intent.get("tp2"), raw.get("tp2")),
            setup_age=_first_available(raw.get("setup_age"), "not_available"),
            missing_confirmation=_missing_confirmation(raw, watchlist_row),
            enbolsa_reason=_text(raw.get("reason"), "none"),
            has_order_intent=has_order_intent,
            order_intent_id=event_key if has_order_intent else "not_applicable",
            intent_status=_intent_status(signal_state, has_order_intent, riskguard_status),
            riskguard_status=riskguard_status,
            riskguard_reason=riskguard_reason,
            riskguard_detail=riskguard_detail,
            candidate_risk_pct=_first_available(intent.get("risk_pct"), raw.get("risk_pct")),
            projected_total_risk_pct=projected["projected_total_risk_pct"],
            projected_symbol_risk_pct=projected["projected_symbol_risk_pct"],
            projected_currency_gross_risk_pct=projected["projected_currency_gross_risk_pct"],
            projected_currency_net_risk_pct=projected["projected_currency_net_risk_pct"],
            wavecount_available=wave["wavecount_available"],
            wavecount_primary_timeframe=wave["wavecount_primary_timeframe"],
            wavecount_aux_timeframe=wave["wavecount_aux_timeframe"],
            wavecount_structure_type=wave["wavecount_structure_type"],
            wavecount_wave_role=wave["wavecount_wave_role"],
            wavecount_degree=wave["wavecount_degree"],
            wavecount_policy_bucket=wave["wavecount_policy_bucket"],
            wavecount_context_status=wave["wavecount_context_status"],
            wavecount_should_filter_trade=False,
            wavecount_notes=wave["wavecount_notes"],
            dashboard_priority=_dashboard_priority(signal_state, riskguard_status),
            dashboard_group=_dashboard_group(signal_state),
            needs_user_attention=_needs_user_attention(signal_state, riskguard_status),
            display_status=_display_status(signal_state, riskguard_status),
            telegram_should_notify=_telegram_should_notify(signal_state, has_order_intent),
            telegram_message_type=_telegram_message_type(signal_state, riskguard_status, has_order_intent),
            telegram_dedup_key=event_key if has_order_intent else "not_applicable",
            dry_run_eligible=_dry_run_eligible(signal_state, riskguard_status),
            dry_run_reason=_dry_run_reason(signal_state, riskguard_status),
            dry_run_action=_dry_run_action(signal_state, riskguard_status),
            is_read_only=True,
            can_execute_order=False,
            source_files=source_files,
            notes=_row_notes(signal_state, wave),
        ))
    return pd.DataFrame(rows)


def _select_official_wavecount_rows(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    selected: dict[str, dict[str, Any]] = {}
    for symbol, group in frame.groupby("symbol", dropna=True):
        ordered = group.copy()
        ordered["_rank"] = ordered.apply(_wavecount_rank, axis=1)
        best = ordered.sort_values("_rank").iloc[0].drop(labels=["_rank"]).to_dict()
        selected[_text(symbol)] = best
    return selected


def _select_aux_timeframes(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    aux = frame[frame.get("source_scope", "") == "h1_h4"] if "source_scope" in frame.columns else pd.DataFrame()
    result: dict[str, str] = {}
    for symbol, group in aux.groupby("symbol", dropna=True):
        timeframes = sorted({_text(value) for value in group.get("timeframe", []) if _text(value)})
        if timeframes:
            result[_text(symbol)] = "|".join(timeframes)
    return result


def _select_robust_notes(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    notes: dict[str, str] = {}
    for symbol, group in frame.groupby("symbol", dropna=True):
        preferred = group.copy()
        preferred["_rank"] = preferred.apply(_robust_rank, axis=1)
        row = preferred.sort_values("_rank").iloc[0]
        diagnostic = _text(row.get("phase259_prominence_diagnostic"), "not_available")
        bucket = _text(row.get("phase259_candidate_bucket"), "not_available")
        notes[_text(symbol)] = f"phase259_diagnostic={diagnostic}; phase259_candidate_bucket={bucket}"
    return notes


def _wavecount_rank(row: pd.Series) -> tuple[int, int, int, int, int, float]:
    source_rank = {"h4_d1": 0, "h1_h4": 5}.get(_text(row.get("source_scope")), 9)
    timeframe_rank = {"H4": 0, "H1": 5}.get(_text(row.get("timeframe")), 9)
    degree_rank = {"intermediate": 0, "major": 1, "minor": 2}.get(_text(row.get("swing_degree")), 9)
    review_rank = {"impulse": 0, "partial_123": 2, "near_miss": 3, "abc": 4, "hard_invalid": 5}.get(
        _text(row.get("review_category")),
        9,
    )
    bucket_rank = {
        "high_quality_structure": 0,
        "usable_provisional_structure": 1,
        "visual_watchlist_low_prominence": 2,
        "auxiliary_substructure": 3,
        "auxiliary_low_prominence_substructure": 4,
        "experimental_only": 5,
        "exclude_from_guided_search": 6,
    }.get(_text(row.get("phase256_policy_bucket")), 9)
    score = -_safe_float(row.get("phase256_score"), default=0.0)
    return (source_rank, timeframe_rank, degree_rank, review_rank, bucket_rank, score)


def _robust_rank(row: pd.Series) -> tuple[int, int, int, int]:
    timeframe_rank = {"H4": 0, "H1": 5}.get(_text(row.get("timeframe")), 9)
    degree_rank = {"intermediate": 0, "major": 1, "minor": 2}.get(_text(row.get("swing_degree")), 9)
    review_rank = {"impulse": 0, "partial_123": 2, "near_miss": 3, "abc": 4, "hard_invalid": 5}.get(
        _text(row.get("review_category")),
        9,
    )
    diagnostic_rank = {"robust_prominence_confirmed": 0, "window_distorted_low_prominence": 1, "true_low_prominence": 2}.get(
        _text(row.get("phase259_prominence_diagnostic")),
        9,
    )
    return (timeframe_rank, degree_rank, review_rank, diagnostic_rank)


def _wavecount_values(symbol: str, wavecount: WaveCountContext, side: str = "") -> dict[str, Any]:
    official = wavecount.official_by_symbol.get(symbol)
    robust_note = wavecount.robust_note_by_symbol.get(symbol, "")
    if not official:
        notes = "no_official_phase256_context"
        if robust_note:
            notes += f"; diagnostic_only_phase259_available; {robust_note}"
        return {
            "market_group": "not_available",
            "wavecount_available": False,
            "wavecount_primary_timeframe": "not_available",
            "wavecount_aux_timeframe": wavecount.aux_timeframe_by_symbol.get(symbol, "not_available"),
            "wavecount_structure_type": "not_available",
            "wavecount_wave_role": "not_available",
            "wavecount_degree": "not_available",
            "wavecount_policy_bucket": "not_available",
            "wavecount_context_status": "not_available",
            "wavecount_notes": notes,
        }

    bucket = _text(official.get("phase256_policy_bucket"), "not_available")
    review_category = _text(official.get("review_category"), "unknown")
    notes = [
        f"candidate_id={_text(official.get('candidate_id'), 'not_available')}",
        f"policy_source=phase2_5_6",
    ]
    for column in ("phase256_adjustment_reason", "policy_warnings", "phase256_prominence_action"):
        value = _text(official.get(column))
        if value:
            notes.append(f"{column}={value}")
    direction = _text(official.get("direction"))
    if direction:
        notes.append(f"wavecount_direction={direction}")
    if robust_note:
        notes.append(robust_note)

    return {
        "market_group": _text(official.get("group"), "not_available"),
        "wavecount_available": True,
        "wavecount_primary_timeframe": _text(official.get("timeframe"), "not_available")
        if _text(official.get("source_scope")) == "h4_d1"
        else "not_available",
        "wavecount_aux_timeframe": wavecount.aux_timeframe_by_symbol.get(symbol, "not_available"),
        "wavecount_structure_type": review_category,
        "wavecount_wave_role": "abc_context" if review_category == "abc" else "unknown",
        "wavecount_degree": _text(official.get("swing_degree"), "not_available"),
        "wavecount_policy_bucket": bucket,
        "wavecount_context_status": _wavecount_context_status(bucket, official, side),
        "wavecount_notes": "; ".join(notes),
    }


def _wavecount_context_status(bucket: str, row: Mapping[str, Any], side: str = "") -> str:
    if _wavecount_direction_conflicts(row.get("direction"), side):
        return "conflicting_context"
    if _truthy(row.get("htf_conflict_warning")):
        return "conflicting_context"
    if bucket in {"high_quality_structure", "usable_provisional_structure", "auxiliary_substructure"}:
        return "supports_context"
    if bucket in {"visual_watchlist_low_prominence", "auxiliary_low_prominence_substructure"}:
        return "low_prominence_watchlist"
    if bucket:
        return "neutral_context"
    return "not_available"


def _wavecount_direction_conflicts(direction: object, side: object) -> bool:
    direction_text = _text(direction).lower()
    side_text = _text(side).upper()
    if direction_text == "bullish" and side_text == "SELL":
        return True
    if direction_text == "bearish" and side_text == "BUY":
        return True
    return False


def _riskguard_status(raw: Mapping[str, Any], intent: Mapping[str, Any]) -> tuple[str, str, str]:
    if not intent and _text(raw.get("signal_state")) != "entry_ready_new":
        return "not_evaluated", "not_available", "not_available"
    source = intent if intent else raw
    accepted_value = source.get("riskguard_accepted")
    if _is_missing(accepted_value):
        return "not_evaluated", "not_available", "not_available"
    if _truthy(accepted_value):
        status = "riskguard_accepted"
    else:
        status = "riskguard_rejected"
    return (
        status,
        _text(source.get("riskguard_reason"), "not_available"),
        _text(source.get("riskguard_detail"), "not_available"),
    )


def _projected_risk_values(decision: Mapping[str, Any], symbol: str) -> dict[str, Any]:
    projected = _parse_mapping(decision.get("projected"))
    if not projected:
        return {
            "projected_total_risk_pct": "not_available",
            "projected_symbol_risk_pct": "not_available",
            "projected_currency_gross_risk_pct": "not_available",
            "projected_currency_net_risk_pct": "not_available",
        }
    symbol_pct = _parse_mapping(projected.get("symbol_open_risk_pct")).get(symbol, "not_available")
    gross_values = []
    net_values = []
    currency_exposure = _parse_mapping(projected.get("currency_exposure"))
    for exposure in currency_exposure.values():
        exposure_map = _parse_mapping(exposure)
        gross_values.append(_safe_float(exposure_map.get("gross_risk_pct"), default=None))
        net_values.append(_safe_float(exposure_map.get("abs_net_risk_pct"), default=None))
    gross_values = [value for value in gross_values if value is not None]
    net_values = [value for value in net_values if value is not None]
    return {
        "projected_total_risk_pct": _first_available(projected.get("total_open_risk_pct"), "not_available"),
        "projected_symbol_risk_pct": _first_available(symbol_pct, "not_available"),
        "projected_currency_gross_risk_pct": max(gross_values) if gross_values else "not_available",
        "projected_currency_net_risk_pct": max(net_values) if net_values else "not_available",
    }


def _intent_status(signal_state: str, has_order_intent: bool, riskguard_status: str) -> str:
    if signal_state == "ready_stale":
        return "stale"
    if signal_state == "ready_already_seen":
        return "already_seen"
    if not has_order_intent:
        return "not_applicable"
    if riskguard_status == "riskguard_accepted":
        return "riskguard_accepted"
    if riskguard_status == "riskguard_rejected":
        return "riskguard_rejected"
    return "diagnostic_only"


def _dry_run_eligible(signal_state: str, riskguard_status: str) -> bool:
    return signal_state == "entry_ready_new" and riskguard_status == "riskguard_accepted"


def _dry_run_reason(signal_state: str, riskguard_status: str) -> str:
    if signal_state == "entry_ready_new" and riskguard_status == "riskguard_accepted":
        return "diagnostic_intent_accepted_by_riskguard"
    if signal_state == "entry_ready_new" and riskguard_status == "riskguard_rejected":
        return "diagnostic_intent_rejected_by_riskguard"
    if signal_state == "ready_stale":
        return "stale_signal_not_eligible"
    if signal_state == "ready_already_seen":
        return "already_seen_not_eligible"
    if signal_state == "watching_setup":
        return "watching_setup_no_entry"
    return "not_applicable"


def _dry_run_action(signal_state: str, riskguard_status: str) -> str:
    if signal_state == "entry_ready_new" and riskguard_status == "riskguard_accepted":
        return "would_accept"
    if signal_state == "entry_ready_new" and riskguard_status == "riskguard_rejected":
        return "would_reject"
    if signal_state == "watching_setup":
        return "watch_only"
    return "none"


def _dashboard_priority(signal_state: str, riskguard_status: str) -> str:
    if signal_state == "entry_ready_new":
        return "high"
    if riskguard_status == "riskguard_rejected":
        return "high"
    if signal_state in {"ready_stale", "ready_already_seen", "watching_setup"}:
        return "medium"
    return "low"


def _dashboard_group(signal_state: str) -> str:
    if signal_state == "entry_ready_new":
        return "fresh_intents"
    if signal_state == "watching_setup":
        return "watchlist"
    if signal_state in {"ready_stale", "ready_already_seen"}:
        return "blocked_or_seen"
    return "background"


def _needs_user_attention(signal_state: str, riskguard_status: str) -> bool:
    return signal_state == "entry_ready_new" or riskguard_status == "riskguard_rejected"


def _display_status(signal_state: str, riskguard_status: str) -> str:
    if signal_state == "entry_ready_new":
        return riskguard_status
    if signal_state == "watching_setup":
        return "watching"
    if signal_state == "ready_stale":
        return "stale"
    if signal_state == "ready_already_seen":
        return "already_seen"
    return signal_state or "no_signal"


def _telegram_should_notify(signal_state: str, has_order_intent: bool) -> bool:
    return bool(has_order_intent and signal_state == "entry_ready_new")


def _telegram_message_type(signal_state: str, riskguard_status: str, has_order_intent: bool) -> str:
    if not has_order_intent:
        return "none"
    if riskguard_status == "riskguard_rejected":
        return "risk_block"
    if signal_state == "entry_ready_new":
        return "new_diagnostic_intent"
    return "none"


def _freshness_status(raw: Mapping[str, Any]) -> str:
    latest = raw.get("latest_closed_bar")
    if _truthy(latest):
        return "latest_closed_bar"
    if _is_missing(latest):
        return "not_available"
    return "historical_bar"


def _missing_confirmation(raw: Mapping[str, Any], watchlist_row: Mapping[str, Any]) -> str:
    value = watchlist_row.get("missing_confirmation")
    if not _is_missing(value):
        return _text(value)
    reason = _text(raw.get("reason"))
    if reason == "waiting_for_trendline_and_macd_confirmation":
        return "trendline_break_or_macd_cross_within_memory"
    return "none"


def _row_notes(signal_state: str, wave: Mapping[str, Any]) -> str:
    notes = ["read_only_snapshot_v0"]
    if signal_state in {"ready_stale", "ready_already_seen"}:
        notes.append("not_eligible_for_dry_run")
    if not wave.get("wavecount_available"):
        notes.append("wavecount_missing_does_not_block")
    return "; ".join(notes)


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        _text(row.get("symbol")),
        _text(row.get("side")),
        _text(row.get("setup_id")),
        _text(row.get("timestamp")),
        _text(row.get("timeframe_ltf")),
        _text(row.get("timeframe_htf")),
    )


def _decision_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        _text(row.get("strategy")),
        _text(row.get("symbol")),
        _text(row.get("side")),
        _text(row.get("setup_id")),
        _text(row.get("timestamp")),
    )


def _build_source_inventory(
    *,
    watcher_dir: Path,
    contract_path: Path,
    policy_dir: Path,
    robust_dir: Path,
    closure_dir: Path,
    watcher: WatcherOutputs,
    schema: pd.DataFrame,
    wavecount_policy_rows: int,
    wavecount_robust_rows: int,
    wavecount_closure_rows: int,
) -> pd.DataFrame:
    rows = [
        _source_row("watcher_snapshot", watcher.files["snapshot"], len(watcher.snapshot), "required"),
        _source_row("watcher_watchlist", watcher.files["watchlist"], len(watcher.watchlist), "optional_context"),
        _source_row("watcher_order_intents", watcher.files["order_intents"], len(watcher.order_intents), "optional_context"),
        _source_row("watcher_riskguard_decisions", watcher.files["riskguard_decisions"], len(watcher.riskguard_decisions), "optional_context"),
        _source_row("watcher_run_meta", watcher.files["run_meta"], 1 if watcher.run_meta else 0, "metadata"),
        _source_row("snapshot_contract", contract_path, len(schema), "contract"),
        _source_row("wavecount_policy_256", policy_dir / "tables" / "phase256_policy_scores.csv", wavecount_policy_rows, "official_context"),
        _source_row("wavecount_robust_259", robust_dir / "tables" / "phase259_candidate_policy_scores.csv", wavecount_robust_rows, "diagnostic_only"),
        _source_row("wavecount_closure_2510", closure_dir / "tables" / "phase25_final_policy_matrix.csv", wavecount_closure_rows, "documentation"),
        _source_row("watcher_dir", watcher_dir, 0, "input_dir"),
    ]
    return pd.DataFrame(rows)


def _source_row(name: str, path: Path, rows: int, role: str) -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "rows": rows,
        "role": role,
    }


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _parse_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if _is_missing(value):
        return {}
    text = str(value).strip()
    if not text:
        return {}
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _resolve(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _first_available(*values: object) -> object:
    for value in values:
        if not _is_missing(value):
            return value
    return "not_available"


def _text(value: object, default: str = "") -> str:
    if _is_missing(value):
        return default
    return str(value).strip()


def _safe_float(value: object, default: float | None = 0.0) -> float | None:
    if _is_missing(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if _is_missing(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "accepted", "si"}


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build live_context_snapshot_v0 from read-only TFG artifacts.")
    parser.add_argument("--watcher-dir", default=str(DEFAULT_WATCHER_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--contract-path", default=str(DEFAULT_CONTRACT_PATH))
    parser.add_argument("--wavecount-policy-dir", default=str(DEFAULT_WAVECOUNT_POLICY_DIR))
    parser.add_argument("--wavecount-robust-dir", default=str(DEFAULT_WAVECOUNT_ROBUST_DIR))
    parser.add_argument("--wavecount-closure-dir", default=str(DEFAULT_WAVECOUNT_CLOSURE_DIR))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = build_live_context_snapshot(
        LiveContextSnapshotConfig(
            watcher_dir=Path(args.watcher_dir),
            output_dir=Path(args.output_dir),
            contract_path=Path(args.contract_path),
            wavecount_policy_dir=Path(args.wavecount_policy_dir),
            wavecount_robust_dir=Path(args.wavecount_robust_dir),
            wavecount_closure_dir=Path(args.wavecount_closure_dir),
        )
    )
    print(
        f"live_context_snapshot rows={len(result.snapshot)} "
        f"output={result.written_files['csv']}"
    )


if __name__ == "__main__":
    main()
