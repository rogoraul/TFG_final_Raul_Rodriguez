from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from trading_center.snapshot_schema import SNAPSHOT_COLUMNS, normalize_snapshot_frame
from trading_center.sql_schema import RUN_KIND_POLICY
from trading_center.sql_store import InMemoryOperationalStore, OperationalStore


DEFAULT_SNAPSHOT_DIR = Path("artifacts/tfg/live_context_snapshot_v0")

STABLE_ROW_COLUMNS = [
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
    "has_order_intent",
    "order_intent_id",
    "intent_status",
    "riskguard_status",
    "riskguard_reason",
    "riskguard_detail",
    "wavecount_available",
    "wavecount_policy_bucket",
    "wavecount_context_status",
    "dry_run_eligible",
    "is_read_only",
    "can_execute_order",
    "wavecount_should_filter_trade",
]

DEFAULT_STRATEGY = {
    "strategy_id": "enbolsa:macd_breakout",
    "family": "enbolsa",
    "status": "active_read_only",
    "can_generate_signals": True,
    "can_enter_dry_run": False,
    "can_execute_live": False,
    "description": "ENBOLSA MACD breakout, initial operational integration strategy.",
    "payload_json": json.dumps({"source": "sql_operational_core_v0", "execution_blocked": True}, ensure_ascii=False),
}

DEFAULT_RISK_CONFIG = {
    "version": "risk_config_v0_fail_closed",
    "is_active": True,
    "risk_per_trade_pct": 0.0,
    "max_total_open_risk_pct": 0.0,
    "max_symbol_open_risk_pct": 0.0,
    "max_currency_gross_risk_pct": 0.0,
    "max_currency_net_risk_pct": 0.0,
    "max_open_trades": 0,
    "kill_switch_enabled": True,
    "notes": "Fail-closed default. Dashboard editing is not enabled in v0 core.",
    "payload_json": json.dumps({"can_execute_order": False}, ensure_ascii=False),
}

DEFAULT_BOT_CONFIG = {
    "version": "bot_config_v0_off",
    "is_active": True,
    "bot_enabled": False,
    "mode": "off",
    "allowed_strategies_json": json.dumps(["enbolsa:macd_breakout"], ensure_ascii=False),
    "allowed_symbols_json": json.dumps([], ensure_ascii=False),
    "requires_manual_approval": True,
    "mt5_enabled": False,
    "live_enabled": False,
    "notes": "Fail-closed default. Bot runtime is not implemented in v0 core.",
    "payload_json": json.dumps({"shadow_demo_live_blocked": True}, ensure_ascii=False),
}


@dataclass(frozen=True)
class SqlCoreLoadResult:
    snapshot_id: str
    run_kind: str
    data_origin: str
    is_operational: bool
    snapshot_rows: int
    source_inventory_rows: int
    signal_events: int
    data_health_rows: int
    inserted: dict[str, int]
    hard_flags_validated: bool


def load_snapshot_artifacts_to_store(
    snapshot_dir: str | Path = DEFAULT_SNAPSHOT_DIR,
    store: OperationalStore | None = None,
    *,
    run_kind: str = "bootstrap_current",
    data_origin: str = "live_context_snapshot_v0",
    cutover_at: str | None = None,
    source_snapshot_id: str | None = None,
) -> SqlCoreLoadResult:
    snapshot_path = Path(snapshot_dir)
    active_store = store or InMemoryOperationalStore()
    validate_run_kind(run_kind)

    frame = _load_snapshot_frame(snapshot_path / "live_context_snapshot.csv")
    run_meta = _load_json(snapshot_path / "run_meta.json")
    source_inventory = _load_source_inventory(snapshot_path / "source_inventory.csv")

    validate_hard_flags(frame)

    snapshot_id = _snapshot_id(frame, run_meta)
    inserted = {
        "strategy_registry": 0,
        "risk_config": 0,
        "bot_config": 0,
        "snapshot_runs": 0,
        "live_context_snapshot_rows": 0,
        "snapshot_source_inventory": 0,
        "signal_events": 0,
        "data_health_snapshot": 0,
    }
    inserted["strategy_registry"] += int(active_store.upsert_strategy(DEFAULT_STRATEGY))
    inserted["risk_config"] += int(active_store.upsert_risk_config(DEFAULT_RISK_CONFIG))
    inserted["bot_config"] += int(active_store.upsert_bot_config(DEFAULT_BOT_CONFIG))

    snapshot_run = build_snapshot_run(
        frame,
        run_meta,
        run_kind=run_kind,
        data_origin=data_origin,
        cutover_at=cutover_at,
        source_snapshot_id=source_snapshot_id,
    )
    inserted["snapshot_runs"] += int(active_store.upsert_snapshot_run(snapshot_run))

    snapshot_rows = build_live_context_rows(frame)
    for row in snapshot_rows:
        inserted["live_context_snapshot_rows"] += int(active_store.upsert_snapshot_row(row))

    source_rows = build_source_inventory_rows(source_inventory, snapshot_id=snapshot_id)
    for row in source_rows:
        inserted["snapshot_source_inventory"] += int(active_store.upsert_source_inventory(row))

    signal_events = build_signal_events(frame)
    for row in signal_events:
        inserted["signal_events"] += int(active_store.upsert_signal_event(row))

    data_health = build_data_health_rows(frame)
    for row in data_health:
        inserted["data_health_snapshot"] += int(active_store.upsert_data_health(row))

    return SqlCoreLoadResult(
        snapshot_id=snapshot_id,
        run_kind=run_kind,
        data_origin=data_origin,
        is_operational=snapshot_run["is_operational"],
        snapshot_rows=len(snapshot_rows),
        source_inventory_rows=len(source_rows),
        signal_events=len(signal_events),
        data_health_rows=len(data_health),
        inserted=inserted,
        hard_flags_validated=True,
    )


def build_snapshot_run(
    frame: pd.DataFrame,
    run_meta: Mapping[str, Any],
    *,
    run_kind: str = "bootstrap_current",
    data_origin: str = "live_context_snapshot_v0",
    cutover_at: str | None = None,
    source_snapshot_id: str | None = None,
) -> dict[str, Any]:
    validate_run_kind(run_kind)
    snapshot_id = _snapshot_id(frame, run_meta)
    generated_at = _first_non_empty(run_meta.get("generated_at"), frame["generated_at"].iloc[0] if not frame.empty else "")
    is_operational = is_operational_run_kind(run_kind)
    return {
        "snapshot_id": snapshot_id,
        "generated_at": _datetime_text(generated_at),
        "snapshot_version": str(run_meta.get("version") or "live_context_snapshot_v0"),
        "producer": "trading_center.sql_loader",
        "status": "completed",
        "run_kind": run_kind,
        "data_origin": data_origin,
        "is_operational": is_operational,
        "cutover_at": _nullable_datetime_text(cutover_at),
        "source_snapshot_id": source_snapshot_id or snapshot_id,
        "row_count": int(len(frame)),
        "order_intent_count": int(_bool_series(frame.get("has_order_intent")).sum()) if not frame.empty else 0,
        "riskguard_count": int((frame.get("riskguard_status", pd.Series(dtype=str)).astype(str) != "not_evaluated").sum()) if not frame.empty else 0,
        "wavecount_available_count": int(_bool_series(frame.get("wavecount_available")).sum()) if not frame.empty else 0,
        "is_read_only": True,
        "can_execute_order": False,
        "wavecount_should_filter_trade": False,
        "notes": "; ".join(run_meta.get("limitations", [])) if isinstance(run_meta.get("limitations"), list) else "",
        "payload_json": _json_text(
            {
                "run_meta": run_meta,
                "load_policy": {
                    "run_kind": run_kind,
                    "data_origin": data_origin,
                    "is_operational": is_operational,
                    "cutover_at": cutover_at,
                    "source_snapshot_id": source_snapshot_id or snapshot_id,
                },
            }
        ),
    }


def build_live_context_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        stable = {column: _value(record.get(column)) for column in STABLE_ROW_COLUMNS}
        stable["generated_at"] = _datetime_text(stable["generated_at"])
        stable["last_closed_bar_time"] = _nullable_datetime_text(stable["last_closed_bar_time"])
        for price_column in ("entry", "sl", "tp1", "tp2"):
            stable[price_column] = _nullable_float(stable[price_column])
        for bool_column in (
            "has_order_intent",
            "wavecount_available",
            "dry_run_eligible",
            "is_read_only",
            "can_execute_order",
            "wavecount_should_filter_trade",
        ):
            stable[bool_column] = _to_bool(stable[bool_column])
        payload = {
            column: _json_value(record.get(column))
            for column in SNAPSHOT_COLUMNS
            if column not in STABLE_ROW_COLUMNS
        }
        stable["payload_json"] = _json_text(payload)
        rows.append(stable)
    return rows


def build_source_inventory_rows(frame: pd.DataFrame, *, snapshot_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return rows
    for record in frame.to_dict(orient="records"):
        source_name = _text(_first_non_empty(record.get("source_name"), record.get("name")), "unknown_source")
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "source_name": source_name,
                "source_path": _text(_first_non_empty(record.get("source_path"), record.get("path")), ""),
                "source_role": _text(_first_non_empty(record.get("source_role"), record.get("role")), "unknown"),
                "exists_flag": _to_bool(_first_non_empty(record.get("exists_flag"), record.get("exists"))),
                "row_count": int(_nullable_float(_first_non_empty(record.get("row_count"), record.get("rows"))) or 0),
                "checksum": _text(record.get("checksum"), ""),
                "payload_json": _json_text(record),
            }
        )
    return rows


def build_signal_events(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        signal_state = _text(record.get("signal_state"), "no_signal")
        if signal_state == "no_signal":
            continue
        snapshot_id = _text(record.get("snapshot_id"), "")
        event_key = _event_key(record)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "event_key": event_key,
                "dedup_key": event_key,
                "symbol": _text(record.get("symbol"), "not_available"),
                "strategy": _text(record.get("strategy"), "not_available"),
                "side": _text(record.get("side"), "not_available"),
                "signal_state": signal_state,
                "order_intent_id": _text(record.get("order_intent_id"), "not_applicable"),
                "event_status": _event_status(signal_state),
                "payload_json": _json_text(
                    {
                        "setup_id": _json_value(record.get("setup_id")),
                        "intent_status": _json_value(record.get("intent_status")),
                        "riskguard_status": _json_value(record.get("riskguard_status")),
                    }
                ),
            }
        )
    return rows


def build_data_health_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in frame.to_dict(orient="records"):
        snapshot_id = _text(record.get("snapshot_id"), "")
        symbol = _text(record.get("symbol"), "not_available")
        timeframe = _text(record.get("timeframe_ltf"), "not_available")
        if timeframe == "not_available":
            continue
        key = (snapshot_id, symbol, timeframe)
        rows_by_key[key] = {
            "snapshot_id": snapshot_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "last_closed_bar_time": _nullable_datetime_text(record.get("last_closed_bar_time")),
            "freshness_status": _text(record.get("data_freshness_status"), "unknown"),
            "source_name": "live_context_snapshot_v0",
            "missing_bars_count": 0,
            "notes": "Derived from live_context_snapshot_v0; detailed gap audit deferred.",
            "payload_json": _json_text(
                {
                    "timeframe_htf": _json_value(record.get("timeframe_htf")),
                    "market_group": _json_value(record.get("market_group")),
                }
            ),
        }
    return list(rows_by_key.values())


def validate_hard_flags(frame: pd.DataFrame) -> None:
    if "is_read_only" in frame.columns and not frame["is_read_only"].map(_to_bool).all():
        raise ValueError("SQL core loader blocks snapshots with is_read_only != true.")
    if "can_execute_order" in frame.columns and frame["can_execute_order"].map(_to_bool).any():
        raise ValueError("SQL core loader blocks snapshots with can_execute_order=true.")
    if "wavecount_should_filter_trade" in frame.columns and frame["wavecount_should_filter_trade"].map(_to_bool).any():
        raise ValueError("SQL core loader blocks snapshots with wavecount_should_filter_trade=true.")


def validate_run_kind(run_kind: str) -> None:
    if run_kind not in RUN_KIND_POLICY:
        allowed = ", ".join(RUN_KIND_POLICY)
        raise ValueError(f"Unknown run_kind '{run_kind}'. Allowed values: {allowed}.")


def is_operational_run_kind(run_kind: str) -> bool:
    validate_run_kind(run_kind)
    return bool(RUN_KIND_POLICY[run_kind]["is_operational"])


def _load_snapshot_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    raw = pd.read_csv(path, low_memory=False)
    validate_hard_flags(raw)
    return normalize_snapshot_frame(raw)


def _load_source_inventory(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["name", "path", "exists", "rows", "role"])
    return pd.read_csv(path, low_memory=False)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot_id(frame: pd.DataFrame, run_meta: Mapping[str, Any]) -> str:
    snapshot_id = _first_non_empty(run_meta.get("snapshot_id"), frame["snapshot_id"].iloc[0] if not frame.empty else "")
    if not snapshot_id:
        raise ValueError("Snapshot id is required for SQL core load.")
    return str(snapshot_id)


def _event_key(record: Mapping[str, Any]) -> str:
    existing = _text(_first_non_empty(record.get("telegram_dedup_key"), record.get("order_intent_id")), "")
    if existing and existing != "not_applicable":
        return existing
    parts = [
        record.get("snapshot_id"),
        record.get("symbol"),
        record.get("strategy"),
        record.get("timeframe_ltf"),
        record.get("timeframe_htf"),
        record.get("side"),
        record.get("setup_id"),
        record.get("signal_state"),
    ]
    return "|".join(_text(part, "not_available") for part in parts)


def _event_status(signal_state: str) -> str:
    if signal_state == "entry_ready_new":
        return "entry_ready_new"
    if signal_state in {"ready_stale", "ready_already_seen", "blocked"}:
        return signal_state
    return "watching_setup"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_value(value: object) -> object:
    if _is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _value(value: object) -> object:
    return None if _is_missing(value) else value


def _text(value: object, default: str = "") -> str:
    if _is_missing(value):
        return default
    text = str(value)
    return text if text else default


def _first_non_empty(*values: object) -> object:
    for value in values:
        if not _is_missing(value) and str(value) != "":
            return value
    return ""


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if _is_missing(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "accepted", "si"}


def _bool_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=bool)
    return series.map(_to_bool)


def _nullable_float(value: object) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime_text(value: object) -> str:
    if _is_missing(value):
        return ""
    return str(value).replace("T", " ")


def _nullable_datetime_text(value: object) -> str | None:
    text = _datetime_text(value)
    if not text or text in {"not_available", "none", "None"}:
        return None
    return text


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load live_context_snapshot_v0 into the SQL operational core store.")
    parser.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR))
    parser.add_argument("--dry-run", action="store_true", help="Use an in-memory store and print the load summary.")
    parser.add_argument(
        "--apply-local-db",
        action="store_true",
        help="Explicitly load into the local MySQL trading_ops schema using existing TRADING_DB_* config.",
    )
    parser.add_argument(
        "--run-kind",
        default="bootstrap_current",
        choices=list(RUN_KIND_POLICY),
        help="Classify the load for operational views and history boundaries.",
    )
    parser.add_argument("--data-origin", default="live_context_snapshot_v0")
    parser.add_argument("--cutover-at", default=None, help="Optional SQL cutover timestamp for this load.")
    parser.add_argument("--source-snapshot-id", default=None, help="Optional upstream snapshot/artifact id.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.dry_run and args.apply_local_db:
        raise SystemExit("Use either --dry-run or --apply-local-db, not both.")
    if args.apply_local_db:
        from trading_center.sql_admin import connect_local_mysql, use_schema
        from trading_center.sql_store import MySqlOperationalStore

        connection = connect_local_mysql(use_config_database=True)
        try:
            use_schema(connection)
            result = load_snapshot_artifacts_to_store(
                args.snapshot_dir,
                MySqlOperationalStore(connection),
                run_kind=args.run_kind,
                data_origin=args.data_origin,
                cutover_at=args.cutover_at,
                source_snapshot_id=args.source_snapshot_id,
            )
            connection.commit()
        finally:
            connection.close()
    else:
        if not args.dry_run:
            raise SystemExit("No DB connection is opened unless --apply-local-db is passed. Use --dry-run for in-memory validation.")
        store = InMemoryOperationalStore()
        result = load_snapshot_artifacts_to_store(
            args.snapshot_dir,
            store,
            run_kind=args.run_kind,
            data_origin=args.data_origin,
            cutover_at=args.cutover_at,
            source_snapshot_id=args.source_snapshot_id,
        )
    print(json.dumps(result.__dict__, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
