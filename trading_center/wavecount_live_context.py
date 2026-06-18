from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from trading_center.wavecount_live_schema import (
    WAVECOUNT_LIVE_COLUMNS,
    base_wavecount_live_row,
    normalize_wavecount_live_frame,
    schema_frame,
    validate_hard_flags,
)
from trading_center.wavecount_live_store import write_wavecount_live_artifacts


DEFAULT_FIXTURE_DIR = Path("tests/fixtures/wavecount_live_context")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_context_v0_fixture_prototype")

IMPULSE_PHASES = {
    "possible_wave1",
    "possible_wave2",
    "possible_wave3_candidate",
    "possible_wave3_active",
    "possible_wave4",
    "possible_wave5_candidate",
    "possible_wave5_active",
    "completed_impulse_candidate",
}

CORRECTION_PHASES = {
    "possible_waveA",
    "possible_waveB",
    "possible_waveC_candidate",
    "possible_waveC_active",
    "completed_abc_candidate",
}

NEXT_PHASE = {
    "possible_wave1": "possible_wave2",
    "possible_wave2": "possible_wave3_candidate",
    "possible_wave3_candidate": "possible_wave3_active",
    "possible_wave3_active": "possible_wave4",
    "possible_wave4": "possible_wave5_candidate",
    "possible_wave5_candidate": "possible_wave5_active",
    "possible_wave5_active": "completed_impulse_candidate",
    "completed_impulse_candidate": "possible_waveA",
    "possible_waveA": "possible_waveB",
    "possible_waveB": "possible_waveC_candidate",
    "possible_waveC_candidate": "possible_waveC_active",
    "possible_waveC_active": "completed_abc_candidate",
    "completed_abc_candidate": "possible_wave1",
    "unknown": "not_available",
    "ambiguous": "manual_review",
    "invalidated": "not_available",
    "not_available": "not_available",
}


@dataclass(frozen=True)
class WaveCountLiveContextConfig:
    fixture_dir: Path = DEFAULT_FIXTURE_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    as_of_bar_time: str | None = None


@dataclass(frozen=True)
class WaveCountLiveContextResult:
    contexts: pd.DataFrame
    fixture_inventory: pd.DataFrame
    anti_lookahead_audit: pd.DataFrame
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_wavecount_live_context(
    config: WaveCountLiveContextConfig | None = None,
) -> WaveCountLiveContextResult:
    config = config or WaveCountLiveContextConfig()
    cases = load_fixture_cases(config.fixture_dir)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for case in cases:
        row, audit = classify_fixture_case(case, generated_at=generated_at, as_of_override=config.as_of_bar_time)
        rows.append(row)
        audit_rows.append(audit)
        inventory_rows.append(_inventory_row(case, row, audit))

    contexts = normalize_wavecount_live_frame(pd.DataFrame(rows, columns=WAVECOUNT_LIVE_COLUMNS))
    validate_hard_flags(contexts)
    fixture_inventory = pd.DataFrame(inventory_rows)
    anti_lookahead_audit = pd.DataFrame(audit_rows)
    run_meta = _run_meta(
        generated_at=generated_at,
        contexts=contexts,
        fixture_inventory=fixture_inventory,
        anti_lookahead_audit=anti_lookahead_audit,
    )
    written = write_wavecount_live_artifacts(
        contexts,
        config.output_dir,
        run_meta=run_meta,
        schema=schema_frame(),
        fixture_inventory=fixture_inventory,
        anti_lookahead_audit=anti_lookahead_audit,
    )
    return WaveCountLiveContextResult(
        contexts=contexts,
        fixture_inventory=fixture_inventory,
        anti_lookahead_audit=anti_lookahead_audit,
        run_meta=run_meta,
        written_files=written,
    )


def load_fixture_cases(fixture_dir: str | Path) -> list[dict[str, Any]]:
    fixture_path = Path(fixture_dir)
    if not fixture_path.exists():
        raise FileNotFoundError(f"fixture_dir does not exist: {fixture_path}")
    cases: list[dict[str, Any]] = []
    for path in sorted(fixture_path.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload.get("fixtures", payload) if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            raise ValueError(f"fixture file must contain a list or fixtures list: {path}")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"fixture entry must be an object in {path}")
            case = dict(entry)
            case["_source_path"] = str(path)
            cases.append(case)
    if not cases:
        raise ValueError(f"no fixture json files found in {fixture_path}")
    return cases


def classify_fixture_case(
    case: dict[str, Any],
    *,
    generated_at: str,
    as_of_override: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    fixture_id = _text(case.get("fixture_id"), "unknown_fixture")
    as_of = _timestamp(as_of_override or case.get("as_of_bar_time"))
    if as_of is None:
        raise ValueError(f"fixture {fixture_id} is missing as_of_bar_time")

    bars_all = _normalise_bars(case.get("bars", []))
    bars = bars_all[bars_all["time"] <= as_of].copy() if not bars_all.empty else pd.DataFrame()
    pivots_all = _normalise_pivots(case.get("pivots", []))
    pivots = pivots_all[pivots_all["detected_at"] <= as_of].copy() if not pivots_all.empty else pd.DataFrame()

    current_price = _current_price(bars)
    phase = _classify_phase(case, pivots, current_price)
    family = _family_for_phase(phase, case)
    invalidation_level = _invalidation_level(case, pivots, phase)
    invalidated_by_price = _breached_invalidation(current_price, invalidation_level, _text(case.get("direction"), "long"), phase)
    if bool(case.get("force_invalidated", False)) or invalidated_by_price:
        phase = "invalidated"
        family = "unknown"

    status = _hypothesis_status(case, phase)
    if phase == "invalidated":
        status = "invalidated"
    if phase == "not_available":
        status = "expired"
    if phase == "ambiguous":
        status = "provisional"

    lookahead_safe = _lookahead_safe(as_of, bars_all, bars, pivots_all, pivots)
    first_bar = bars["time"].min() if not bars.empty else pd.NaT
    evidence_end = bars["time"].max() if not bars.empty else as_of
    last_pivot = pivots.iloc[-1].to_dict() if not pivots.empty else {}
    first_pivot = pivots.iloc[0].to_dict() if not pivots.empty else {}
    detected_at = _max_timestamp([last_pivot.get("detected_at"), evidence_end])
    pivot_confirmed_at = last_pivot.get("detected_at", pd.NaT)
    confirmation_lag_bars = _confirmation_lag_bars(last_pivot)
    wave_start_price = _float_or_blank(first_pivot.get("price"))
    wave_end_price = _float_or_blank(last_pivot.get("price"))
    distance_to_invalidation = _distance_pct(current_price, invalidation_level)
    target_zone_1, target_zone_2 = _target_zones(current_price, pivots, phase, _text(case.get("direction"), "long"))
    context_id = f"wavecount_live_v0_{fixture_id}_{as_of.strftime('%Y%m%dT%H%M%S')}"
    payload = _payload(case, bars, pivots, phase)

    row = base_wavecount_live_row(
        context_id=context_id,
        generated_at=generated_at,
        as_of_bar_time=as_of.isoformat(),
        symbol=_text(case.get("symbol"), "not_available"),
        market_group=_text(case.get("market_group"), "not_available"),
        timeframe=_text(case.get("timeframe"), "not_available"),
        higher_timeframe=_text(case.get("higher_timeframe"), "not_available"),
        data_origin="test_fixture",
        wavecount_live_available=phase not in {"not_available"},
        structure_family=family,
        structure_phase=phase,
        next_phase_hypothesis=NEXT_PHASE.get(phase, "not_available"),
        direction=_text(case.get("direction"), "not_available"),
        degree=_text(case.get("degree"), "not_available"),
        hypothesis_status=status,
        confidence_bucket=_confidence_bucket(phase, pivots, lookahead_safe),
        quality_bucket=_quality_bucket(case, phase),
        policy_bucket_256=_policy_bucket(case, phase),
        lookahead_safe=lookahead_safe,
        confirmation_lag_bars=confirmation_lag_bars,
        detected_at=_timestamp_text(detected_at),
        pivot_confirmed_at=_timestamp_text(pivot_confirmed_at),
        evidence_window_start=_timestamp_text(first_bar),
        evidence_window_end=_timestamp_text(evidence_end),
        wave_start_price=wave_start_price,
        wave_end_price=wave_end_price,
        current_price=_float_or_blank(current_price),
        invalidation_level=_float_or_blank(invalidation_level),
        distance_to_invalidation_pct=distance_to_invalidation,
        target_zone_1=target_zone_1,
        target_zone_2=target_zone_2,
        prominence_score=_float_or_blank(case.get("prominence_score", "")),
        ewo_state=_text(case.get("ewo_state"), "not_available"),
        ewo_divergence_status=_text(case.get("ewo_divergence_status"), "not_available"),
        ema_htf_context=_text(case.get("ema_htf_context"), "not_available"),
        trend_context=_text(case.get("trend_context"), "not_available"),
        volatility_context=_text(case.get("volatility_context"), "not_available"),
        enbolsa_alignment_status=_text(case.get("enbolsa_alignment_status"), "not_applicable"),
        matched_enbolsa_setup_id=_text(case.get("matched_enbolsa_setup_id"), ""),
        matched_enbolsa_signal_state=_text(case.get("matched_enbolsa_signal_state"), "not_available"),
        source_artifacts=_text(case.get("_source_path"), ""),
        notes=_notes(case, phase, lookahead_safe),
        payload_json=json.dumps(payload, sort_keys=True, default=str),
    )
    audit = {
        "fixture_id": fixture_id,
        "context_id": context_id,
        "as_of_bar_time": as_of.isoformat(),
        "bars_total": int(len(bars_all)),
        "bars_used": int(len(bars)),
        "bars_after_as_of_ignored": int(len(bars_all) - len(bars)),
        "pivots_total": int(len(pivots_all)),
        "pivots_used": int(len(pivots)),
        "pivots_after_as_of_ignored": int(len(pivots_all) - len(pivots)),
        "detected_at_lte_as_of": _timestamp(detected_at) <= as_of if not pd.isna(detected_at) else True,
        "evidence_window_end_lte_as_of": _timestamp(evidence_end) <= as_of if not pd.isna(evidence_end) else True,
        "lookahead_safe": lookahead_safe,
        "real_sql_executed": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
    }
    return row, audit


def _classify_phase(case: dict[str, Any], pivots: pd.DataFrame, current_price: float | None) -> str:
    if bool(case.get("no_context", False)):
        return "not_available"
    if bool(case.get("ambiguous", False)):
        return "ambiguous"
    if pivots.empty:
        return "unknown"

    family = _text(case.get("structure_family"), "impulse")
    direction = _text(case.get("direction"), "long")
    if family == "correction":
        return _classify_correction(pivots, current_price, direction)
    return _classify_impulse(pivots, current_price, direction)


def _classify_impulse(pivots: pd.DataFrame, current_price: float | None, direction: str) -> str:
    count = len(pivots)
    if count <= 1:
        return "possible_wave1"
    if count == 2:
        return "possible_wave2"
    if count == 3:
        wave1_extreme = float(pivots.iloc[1]["price"])
        return "possible_wave3_active" if _beyond(current_price, wave1_extreme, direction) else "possible_wave3_candidate"
    if count == 4:
        return "possible_wave4"
    if count == 5:
        wave3_extreme = float(pivots.iloc[3]["price"])
        return "possible_wave5_active" if _beyond(current_price, wave3_extreme, direction) else "possible_wave5_candidate"
    return "completed_impulse_candidate"


def _classify_correction(pivots: pd.DataFrame, current_price: float | None, direction: str) -> str:
    count = len(pivots)
    if count <= 1:
        return "possible_waveA"
    if count == 2:
        return "possible_waveB"
    if count == 3:
        wave_a_extreme = float(pivots.iloc[1]["price"])
        return "possible_waveC_active" if _beyond(current_price, wave_a_extreme, direction) else "possible_waveC_candidate"
    return "completed_abc_candidate"


def _normalise_bars(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["time", "close"])
    frame = pd.DataFrame(rows)
    if "time" not in frame.columns:
        raise ValueError("fixture bars require a time column")
    if "close" not in frame.columns:
        raise ValueError("fixture bars require a close column")
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["time", "close"]).sort_values("time").reset_index(drop=True)
    return frame


def _normalise_pivots(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["label", "pivot_type", "extreme_time", "detected_at", "price"])
    frame = pd.DataFrame(rows)
    required = ["label", "pivot_type", "extreme_time", "detected_at", "price"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"fixture pivots missing columns: {missing}")
    frame["extreme_time"] = pd.to_datetime(frame["extreme_time"], errors="coerce")
    frame["detected_at"] = pd.to_datetime(frame["detected_at"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["extreme_time", "detected_at", "price"]).sort_values(["detected_at", "extreme_time"]).reset_index(drop=True)
    return frame


def _run_meta(
    *,
    generated_at: str,
    contexts: pd.DataFrame,
    fixture_inventory: pd.DataFrame,
    anti_lookahead_audit: pd.DataFrame,
) -> dict[str, Any]:
    phase_distribution = contexts["structure_phase"].value_counts().sort_index().to_dict() if not contexts.empty else {}
    status_distribution = contexts["hypothesis_status"].value_counts().sort_index().to_dict() if not contexts.empty else {}
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_context_v0_fixture_prototype",
        "fixture_count": int(len(fixture_inventory)),
        "rows": int(len(contexts)),
        "structure_phase_distribution": {str(key): int(value) for key, value in phase_distribution.items()},
        "hypothesis_status_distribution": {str(key): int(value) for key, value in status_distribution.items()},
        "flags": {
            "is_read_only": True,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
        },
        "safety": {
            "real_sql_executed": False,
            "ddl_executed": False,
            "mt5_connected": False,
            "backtests_executed": False,
            "signals_generated": False,
            "dashboard_implemented": False,
            "telegram_implemented": False,
            "bot_implemented": False,
        },
        "anti_lookahead_passed": bool(anti_lookahead_audit["lookahead_safe"].all()) if not anti_lookahead_audit.empty else False,
        "limitations": [
            "Fixture-only prototype; it does not solve full Elliott counting.",
            "Pivot events are synthetic causal fixtures, not live market detector output.",
            "No SQL, MT5, backtest, dashboard, Telegram or bot integration is performed.",
            "WaveCount live labels are context hypotheses, not operational signals or filters.",
        ],
    }


def _inventory_row(case: dict[str, Any], row: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_id": _text(case.get("fixture_id"), "unknown_fixture"),
        "source_path": _text(case.get("_source_path"), ""),
        "symbol": row["symbol"],
        "timeframe": row["timeframe"],
        "as_of_bar_time": row["as_of_bar_time"],
        "expected_structure_phase": _text(case.get("expected_structure_phase"), "not_declared"),
        "actual_structure_phase": row["structure_phase"],
        "expected_matches_actual": _text(case.get("expected_structure_phase"), row["structure_phase"]) == row["structure_phase"],
        "bars_total": audit["bars_total"],
        "pivots_total": audit["pivots_total"],
    }


def _family_for_phase(phase: str, case: dict[str, Any]) -> str:
    if phase in IMPULSE_PHASES:
        return "impulse"
    if phase in CORRECTION_PHASES:
        return "correction"
    if phase == "not_available":
        return "unknown"
    if phase == "invalidated":
        return "unknown"
    return _text(case.get("structure_family"), "unknown")


def _hypothesis_status(case: dict[str, Any], phase: str) -> str:
    explicit = _text(case.get("hypothesis_status"), "")
    if explicit:
        return explicit
    if phase in {"possible_wave1", "possible_wave2", "possible_waveA", "possible_waveB"}:
        return "forming"
    if phase in {"completed_impulse_candidate", "completed_abc_candidate"}:
        return "confirmed"
    if phase == "not_available":
        return "expired"
    return "provisional"


def _confidence_bucket(phase: str, pivots: pd.DataFrame, lookahead_safe: bool) -> str:
    if phase in {"ambiguous"}:
        return "manual_review"
    if not lookahead_safe or phase in {"unknown", "not_available", "invalidated"}:
        return "low"
    if len(pivots) >= 5 or phase in {"possible_wave3_active", "possible_wave5_active", "possible_waveC_active"}:
        return "medium"
    return "low"


def _quality_bucket(case: dict[str, Any], phase: str) -> str:
    if phase in {"unknown", "ambiguous", "invalidated", "not_available"}:
        return "not_available"
    return _text(case.get("quality_bucket"), "fixture_provisional_structure")


def _policy_bucket(case: dict[str, Any], phase: str) -> str:
    if phase in {"unknown", "ambiguous", "invalidated", "not_available"}:
        return "not_available"
    return _text(case.get("policy_bucket_256"), "usable_provisional_structure")


def _invalidation_level(case: dict[str, Any], pivots: pd.DataFrame, phase: str) -> float | None:
    explicit = case.get("invalidation_level")
    if explicit not in (None, ""):
        return float(explicit)
    if pivots.empty or phase in {"unknown", "ambiguous", "not_available", "completed_impulse_candidate", "completed_abc_candidate"}:
        return None
    direction = _text(case.get("direction"), "long")
    if direction == "short":
        highs = pivots[pivots["pivot_type"] == "high"]
        if not highs.empty:
            return float(highs.iloc[-1]["price"])
    else:
        lows = pivots[pivots["pivot_type"] == "low"]
        if not lows.empty:
            return float(lows.iloc[-1]["price"])
    return float(pivots.iloc[0]["price"])


def _breached_invalidation(current_price: float | None, invalidation_level: float | None, direction: str, phase: str) -> bool:
    if current_price is None or invalidation_level is None or phase in {"unknown", "ambiguous", "not_available"}:
        return False
    if direction == "short":
        return current_price > invalidation_level
    return current_price < invalidation_level


def _target_zones(current_price: float | None, pivots: pd.DataFrame, phase: str, direction: str) -> tuple[str | float, str | float]:
    if current_price is None or pivots.empty or phase in {"unknown", "ambiguous", "invalidated", "not_available"}:
        return "", ""
    leg = abs(float(pivots.iloc[-1]["price"]) - float(pivots.iloc[0]["price"]))
    if leg <= 0:
        return "", ""
    sign = -1.0 if direction == "short" else 1.0
    return round(current_price + sign * leg * 0.618, 6), round(current_price + sign * leg, 6)


def _payload(case: dict[str, Any], bars: pd.DataFrame, pivots: pd.DataFrame, phase: str) -> dict[str, Any]:
    expected = _text(case.get("expected_structure_phase"), "")
    return {
        "fixture_id": _text(case.get("fixture_id"), "unknown_fixture"),
        "expected_structure_phase": expected,
        "actual_structure_phase": phase,
        "expected_matches_actual": bool(not expected or expected == phase),
        "bars_used": int(len(bars)),
        "pivots_used": int(len(pivots)),
        "pivot_labels_used": pivots["label"].tolist() if "label" in pivots.columns else [],
        "fixture_only": True,
        "operational_use": "forbidden",
    }


def _notes(case: dict[str, Any], phase: str, lookahead_safe: bool) -> str:
    base = _text(case.get("notes"), "fixture-only structural context")
    guardrail = "lookahead_safe" if lookahead_safe else "lookahead_risk_detected"
    return f"{base}; phase={phase}; {guardrail}; no_signal_no_filter_no_execution"


def _lookahead_safe(
    as_of: pd.Timestamp,
    bars_all: pd.DataFrame,
    bars: pd.DataFrame,
    pivots_all: pd.DataFrame,
    pivots: pd.DataFrame,
) -> bool:
    if not bars.empty and bool((bars["time"] > as_of).any()):
        return False
    if not pivots.empty and bool((pivots["detected_at"] > as_of).any()):
        return False
    if not bars_all.empty and not bars.empty and bars["time"].max() > as_of:
        return False
    if not pivots_all.empty and not pivots.empty and pivots["detected_at"].max() > as_of:
        return False
    return True


def _current_price(bars: pd.DataFrame) -> float | None:
    if bars.empty:
        return None
    return float(bars.iloc[-1]["close"])


def _confirmation_lag_bars(pivot: dict[str, Any]) -> int:
    if not pivot:
        return 0
    if "confirmation_lag_bars" in pivot and not pd.isna(pivot["confirmation_lag_bars"]):
        return int(pivot["confirmation_lag_bars"])
    return 1


def _distance_pct(current_price: float | None, invalidation_level: float | None) -> str | float:
    if current_price is None or invalidation_level is None or current_price == 0:
        return ""
    return round(abs(current_price - invalidation_level) / abs(current_price), 6)


def _beyond(current_price: float | None, reference_price: float, direction: str) -> bool:
    if current_price is None:
        return False
    if direction == "short":
        return current_price < reference_price
    return current_price > reference_price


def _max_timestamp(values: list[Any]) -> pd.Timestamp | pd.NaT:
    timestamps = [_timestamp(value) for value in values]
    valid = [value for value in timestamps if value is not None and not pd.isna(value)]
    if not valid:
        return pd.NaT
    return max(valid)


def _timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    try:
        timestamp = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp


def _timestamp_text(value: Any) -> str:
    timestamp = _timestamp(value)
    if timestamp is None:
        return ""
    return timestamp.isoformat()


def _float_or_blank(value: Any) -> str | float:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if pd.isna(number):
        return ""
    return round(number, 6)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build fixture-only WaveCount live context v0 artifacts.")
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--as-of-bar-time", default=None)
    parser.add_argument("--fixture-only", action="store_true", help="Explicit guardrail flag; this command is fixture-only regardless.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_wavecount_live_context(
        WaveCountLiveContextConfig(
            fixture_dir=args.fixture_dir,
            output_dir=args.output_dir,
            as_of_bar_time=args.as_of_bar_time,
        )
    )
    print(
        json.dumps(
            {
                "rows": int(len(result.contexts)),
                "output_dir": str(args.output_dir),
                "real_sql_executed": False,
                "mt5_connected": False,
                "backtests_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
