from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.wavecount.wavecount_config import PivotConfig
from backtests.wavecount.wavecount_pivots import detect_causal_pivots
from backtests.wavecount.wavecount_structure import StructuralPivotConfig, build_structural_pivots
from trading_center.wavecount_live_context import classify_fixture_case
from trading_center.wavecount_live_schema import (
    WAVECOUNT_LIVE_COLUMNS,
    normalize_wavecount_live_frame,
    schema_frame,
    validate_hard_flags,
)
from trading_center.wavecount_live_store import write_wavecount_live_artifacts


DEFAULT_OHLC_FIXTURE_DIR = Path("tests/fixtures/wavecount_live_ohlc")
DEFAULT_OHLC_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_context_v0_ohlc_prototype")


@dataclass(frozen=True)
class WaveCountLiveOhlcConfig:
    fixture_dir: Path = DEFAULT_OHLC_FIXTURE_DIR
    output_dir: Path = DEFAULT_OHLC_OUTPUT_DIR
    as_of_bar_time: str | None = None
    pivot_config: PivotConfig = PivotConfig(
        left_bars=1,
        confirmation_bars=1,
        atr_period=3,
        min_atr_multiplier=0.0,
        min_relative_move_pct=0.0,
        min_bars_between_pivots=1,
        candidate_lookback_bars=2,
    )
    structural_config: StructuralPivotConfig = StructuralPivotConfig(
        min_leg_atr_multiplier=0.0,
        min_leg_relative_move_pct=0.0,
        min_leg_bars=0,
    )


@dataclass(frozen=True)
class WaveCountLiveOhlcResult:
    contexts: pd.DataFrame
    fixture_inventory: pd.DataFrame
    anti_lookahead_audit: pd.DataFrame
    detected_pivots: pd.DataFrame
    structural_pivots: pd.DataFrame
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_wavecount_live_ohlc(
    config: WaveCountLiveOhlcConfig | None = None,
) -> WaveCountLiveOhlcResult:
    config = config or WaveCountLiveOhlcConfig()
    cases = load_ohlc_fixture_cases(config.fixture_dir)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    detected_frames: list[pd.DataFrame] = []
    structural_frames: list[pd.DataFrame] = []

    for case in cases:
        prepared = prepare_ohlc_case(case, config=config)
        row, audit = classify_fixture_case(
            prepared["classification_case"],
            generated_at=generated_at,
            as_of_override=config.as_of_bar_time,
        )
        row.update(
            {
                "method_version": "wavecount_live_context_v0_ohlc_prototype",
                "source_artifacts": str(prepared["source_path"]),
                "payload_json": json.dumps(_payload(prepared, row), sort_keys=True, default=str),
                "notes": _notes(prepared, row),
            }
        )
        rows.append(row)
        audit_rows.append(_audit_row(prepared, audit))
        inventory_rows.append(_inventory_row(prepared, row))
        if not prepared["detected_pivots"].empty:
            detected_frames.append(prepared["detected_pivots"])
        if not prepared["structural_pivots"].empty:
            structural_frames.append(prepared["structural_pivots"])

    contexts = normalize_wavecount_live_frame(pd.DataFrame(rows, columns=WAVECOUNT_LIVE_COLUMNS))
    validate_hard_flags(contexts)
    fixture_inventory = pd.DataFrame(inventory_rows)
    anti_lookahead_audit = pd.DataFrame(audit_rows)
    detected_pivots = pd.concat(detected_frames, ignore_index=True) if detected_frames else pd.DataFrame()
    structural_pivots = pd.concat(structural_frames, ignore_index=True) if structural_frames else pd.DataFrame()
    run_meta = _run_meta(
        generated_at=generated_at,
        contexts=contexts,
        fixture_inventory=fixture_inventory,
        anti_lookahead_audit=anti_lookahead_audit,
        detected_pivots=detected_pivots,
    )
    written = write_wavecount_live_artifacts(
        contexts,
        config.output_dir,
        run_meta=run_meta,
        schema=schema_frame(),
        fixture_inventory=fixture_inventory,
        anti_lookahead_audit=anti_lookahead_audit,
    )
    output_dir = Path(config.output_dir)
    detected_path = output_dir / "detected_pivots.csv"
    structural_path = output_dir / "structural_pivots.csv"
    detected_pivots.to_csv(detected_path, index=False)
    structural_pivots.to_csv(structural_path, index=False)
    written["detected_pivots"] = detected_path
    written["structural_pivots"] = structural_path
    return WaveCountLiveOhlcResult(
        contexts=contexts,
        fixture_inventory=fixture_inventory,
        anti_lookahead_audit=anti_lookahead_audit,
        detected_pivots=detected_pivots,
        structural_pivots=structural_pivots,
        run_meta=run_meta,
        written_files=written,
    )


def load_ohlc_fixture_cases(fixture_dir: str | Path) -> list[dict[str, Any]]:
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


def prepare_ohlc_case(case: dict[str, Any], *, config: WaveCountLiveOhlcConfig) -> dict[str, Any]:
    fixture_id = _text(case.get("fixture_id"), "unknown_fixture")
    as_of = _timestamp(config.as_of_bar_time or case.get("as_of_bar_time"))
    if as_of is None:
        raise ValueError(f"fixture {fixture_id} is missing as_of_bar_time")

    bars_all = _normalise_ohlc(case.get("bars", []))
    bars_used = bars_all[bars_all["time"] <= as_of].copy() if not bars_all.empty else pd.DataFrame()
    detected = _detect_pivots_for_case(case, bars_used, config)
    structural = _structural_pivots_for_case(case, detected, config)
    classification_case = _classification_case(case, bars_all, structural, as_of)
    return {
        "fixture_id": fixture_id,
        "source_path": case.get("_source_path", ""),
        "as_of_bar_time": as_of,
        "bars_all": bars_all,
        "bars_used": bars_used,
        "detected_pivots": detected,
        "structural_pivots": structural,
        "classification_case": classification_case,
    }


def _detect_pivots_for_case(case: dict[str, Any], bars_used: pd.DataFrame, config: WaveCountLiveOhlcConfig) -> pd.DataFrame:
    if bars_used.empty or bool(case.get("no_context", False)):
        return pd.DataFrame()
    symbol = _text(case.get("symbol"), "")
    timeframe = _text(case.get("timeframe"), "")
    ohlc = bars_used.set_index("time")[["open", "high", "low", "close"]].copy()
    raw = detect_causal_pivots(ohlc, config.pivot_config, symbol=symbol, timeframe=timeframe)
    events = raw[raw["pivot_state"].isin(["confirmed_high", "confirmed_low", "ambiguous_noise"])].copy()
    if events.empty:
        return events
    events = events.reset_index(drop=True)
    events["fixture_id"] = _text(case.get("fixture_id"), "")
    events["market_group"] = _text(case.get("market_group"), "")
    events["group"] = _text(case.get("market_group"), "")
    events["example_id"] = events["fixture_id"]
    events["example_type"] = _text(case.get("structure_family"), "")
    events["pivot_detected_at"] = pd.to_datetime(events["pivot_detected_at"], errors="coerce")
    events["pivot_extreme_time"] = pd.to_datetime(events["pivot_extreme_time"], errors="coerce")
    return events


def _structural_pivots_for_case(case: dict[str, Any], detected: pd.DataFrame, config: WaveCountLiveOhlcConfig) -> pd.DataFrame:
    confirmed = detected[detected["is_confirmed"].astype(bool)].copy() if not detected.empty and "is_confirmed" in detected.columns else pd.DataFrame()
    if confirmed.empty:
        return pd.DataFrame()
    result = build_structural_pivots(confirmed, config.structural_config)
    structural = result["structural_pivots"].copy()
    if structural.empty:
        return structural
    structural["fixture_id"] = _text(case.get("fixture_id"), "")
    structural["market_group"] = _text(case.get("market_group"), "")
    structural["symbol"] = _text(case.get("symbol"), "")
    structural["timeframe"] = _text(case.get("timeframe"), "")
    structural["higher_timeframe"] = _text(case.get("higher_timeframe"), "")
    return structural


def _classification_case(case: dict[str, Any], bars_all: pd.DataFrame, structural: pd.DataFrame, as_of: pd.Timestamp) -> dict[str, Any]:
    pivots = []
    if not structural.empty:
        for index, row in structural.reset_index(drop=True).iterrows():
            pivots.append(
                {
                    "label": f"structural_{index + 1}",
                    "pivot_type": row["pivot_type"],
                    "extreme_time": pd.Timestamp(row["pivot_extreme_time"]).isoformat(),
                    "detected_at": pd.Timestamp(row["pivot_detected_at"]).isoformat(),
                    "price": float(row["pivot_extreme_price"]),
                    "confirmation_lag_bars": _lag_bars(row),
                }
            )
    fixture_case = {
        "fixture_id": _text(case.get("fixture_id"), "unknown_fixture"),
        "symbol": _text(case.get("symbol"), "not_available"),
        "market_group": _text(case.get("market_group"), "not_available"),
        "timeframe": _text(case.get("timeframe"), "not_available"),
        "higher_timeframe": _text(case.get("higher_timeframe"), "not_available"),
        "structure_family": _text(case.get("structure_family"), "impulse"),
        "direction": _text(case.get("direction"), "long"),
        "degree": _text(case.get("degree"), "intermediate"),
        "as_of_bar_time": as_of.isoformat(),
        "expected_structure_phase": _text(case.get("expected_structure_phase"), ""),
        "ambiguous": bool(case.get("ambiguous", False)),
        "no_context": bool(case.get("no_context", False)),
        "bars": _bars_for_classification(bars_all),
        "pivots": pivots,
        "notes": _text(case.get("notes"), "ohlc-cut prototype"),
    }
    if case.get("invalidation_level") not in (None, ""):
        fixture_case["invalidation_level"] = case["invalidation_level"]
    return fixture_case


def _run_meta(
    *,
    generated_at: str,
    contexts: pd.DataFrame,
    fixture_inventory: pd.DataFrame,
    anti_lookahead_audit: pd.DataFrame,
    detected_pivots: pd.DataFrame,
) -> dict[str, Any]:
    phase_distribution = contexts["structure_phase"].value_counts().sort_index().to_dict() if not contexts.empty else {}
    status_distribution = contexts["hypothesis_status"].value_counts().sort_index().to_dict() if not contexts.empty else {}
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_context_v0_ohlc_prototype",
        "fixture_count": int(len(fixture_inventory)),
        "rows": int(len(contexts)),
        "structure_phase_distribution": {str(key): int(value) for key, value in phase_distribution.items()},
        "hypothesis_status_distribution": {str(key): int(value) for key, value in status_distribution.items()},
        "bars_after_as_of_ignored": int(anti_lookahead_audit["bars_after_as_of_ignored"].astype(int).sum()) if not anti_lookahead_audit.empty else 0,
        "confirmed_pivots_used": int(len(detected_pivots[detected_pivots.get("is_confirmed", False).astype(bool)])) if not detected_pivots.empty and "is_confirmed" in detected_pivots.columns else 0,
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
            "OHLC-cut prototype; it uses small synthetic OHLC fixtures, not live market feeds.",
            "Pivot detection reuses the causal WaveCount pivot detector with lenient fixture parameters.",
            "It does not solve full Elliott counting and does not produce operational signals.",
            "No SQL, MT5, backtest, dashboard, Telegram or bot integration is performed.",
        ],
    }


def _inventory_row(prepared: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    expected = _text(prepared["classification_case"].get("expected_structure_phase"), "not_declared")
    return {
        "fixture_id": prepared["fixture_id"],
        "source_path": prepared["source_path"],
        "symbol": row["symbol"],
        "timeframe": row["timeframe"],
        "as_of_bar_time": row["as_of_bar_time"],
        "expected_structure_phase": expected,
        "actual_structure_phase": row["structure_phase"],
        "expected_matches_actual": expected == row["structure_phase"] if expected != "not_declared" else True,
        "bars_total": int(len(prepared["bars_all"])),
        "bars_used": int(len(prepared["bars_used"])),
        "detected_pivots": int(len(prepared["detected_pivots"])),
        "structural_pivots": int(len(prepared["structural_pivots"])),
    }


def _audit_row(prepared: dict[str, Any], base_audit: dict[str, Any]) -> dict[str, Any]:
    structural = prepared["structural_pivots"]
    latest_detected = pd.NaT if structural.empty else pd.to_datetime(structural["pivot_detected_at"], errors="coerce").max()
    latest_extreme = pd.NaT if structural.empty else pd.to_datetime(structural["pivot_extreme_time"], errors="coerce").max()
    as_of = prepared["as_of_bar_time"]
    return {
        **base_audit,
        "bars_total": int(len(prepared["bars_all"])),
        "bars_used": int(len(prepared["bars_used"])),
        "bars_after_as_of_ignored": int(len(prepared["bars_all"]) - len(prepared["bars_used"])),
        "detected_pivots_total": int(len(prepared["detected_pivots"])),
        "structural_pivots_used": int(len(structural)),
        "latest_pivot_detected_at": "" if pd.isna(latest_detected) else pd.Timestamp(latest_detected).isoformat(),
        "latest_pivot_extreme_time": "" if pd.isna(latest_extreme) else pd.Timestamp(latest_extreme).isoformat(),
        "pivot_detected_at_lte_as_of": True if pd.isna(latest_detected) else pd.Timestamp(latest_detected) <= as_of,
        "pivot_extreme_time_used_as_detection": False if pd.isna(latest_detected) or pd.isna(latest_extreme) else pd.Timestamp(latest_detected) == pd.Timestamp(latest_extreme),
    }


def _payload(prepared: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_id": prepared["fixture_id"],
        "expected_structure_phase": prepared["classification_case"].get("expected_structure_phase", ""),
        "actual_structure_phase": row["structure_phase"],
        "bars_total": int(len(prepared["bars_all"])),
        "bars_used": int(len(prepared["bars_used"])),
        "detected_pivots": int(len(prepared["detected_pivots"])),
        "structural_pivots": int(len(prepared["structural_pivots"])),
        "ohlc_cut_prototype": True,
        "operational_use": "forbidden",
    }


def _notes(prepared: dict[str, Any], row: dict[str, Any]) -> str:
    return (
        f"ohlc-cut prototype; fixture_id={prepared['fixture_id']}; "
        f"phase={row['structure_phase']}; no_signal_no_filter_no_execution"
    )


def _normalise_ohlc(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    frame = pd.DataFrame(rows).copy()
    if "time" not in frame.columns or "close" not in frame.columns:
        raise ValueError("OHLC fixture rows require at least time and close")
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if "open" not in frame.columns:
        frame["open"] = frame["close"]
    if "high" not in frame.columns:
        frame["high"] = frame["close"] + 0.1
    if "low" not in frame.columns:
        frame["low"] = frame["close"] - 0.1
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
    return frame[["time", "open", "high", "low", "close"]]


def _bars_for_classification(bars: pd.DataFrame) -> list[dict[str, Any]]:
    if bars.empty:
        return []
    frame = bars[["time", "close"]].copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    return frame.dropna(subset=["time"]).to_dict(orient="records")


def _lag_bars(row: pd.Series) -> int:
    extreme = pd.Timestamp(row["pivot_extreme_time"])
    detected = pd.Timestamp(row["pivot_detected_at"])
    timeframe = _text(row.get("timeframe"), "H4").upper()
    minutes = {"M30": 30, "H1": 60, "H4": 240, "D1": 1440}.get(timeframe, 240)
    return max(0, int(round((detected - extreme).total_seconds() / 60.0 / minutes)))


def _timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build OHLC-cut WaveCount live context v0 artifacts.")
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_OHLC_FIXTURE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OHLC_OUTPUT_DIR)
    parser.add_argument("--as-of-bar-time", default=None)
    parser.add_argument("--ohlc-only", action="store_true", help="Explicit guardrail flag; this command is OHLC-only regardless.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_wavecount_live_ohlc(
        WaveCountLiveOhlcConfig(
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
