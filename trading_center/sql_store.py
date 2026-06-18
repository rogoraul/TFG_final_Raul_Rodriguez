"""Operational SQL store abstractions plus an in-memory test implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class OperationalStore(Protocol):
    """Persistence contract used by SQL loader/review code."""
    def upsert_strategy(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_risk_config(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_bot_config(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_snapshot_run(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_snapshot_row(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_source_inventory(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_signal_event(self, row: Mapping[str, Any]) -> bool: ...
    def upsert_data_health(self, row: Mapping[str, Any]) -> bool: ...


@dataclass
class InMemoryOperationalStore:
    """Dictionary-backed store used by tests and dry-run simulations."""
    strategies: dict[str, dict[str, Any]] = field(default_factory=dict)
    risk_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    bot_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshot_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshot_rows: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = field(default_factory=dict)
    source_inventory: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    signal_events: dict[str, dict[str, Any]] = field(default_factory=dict)
    data_health: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)

    def upsert_strategy(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.strategies, row["strategy_id"], row)

    def upsert_risk_config(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.risk_configs, row["version"], row)

    def upsert_bot_config(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.bot_configs, row["version"], row)

    def upsert_snapshot_run(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.snapshot_runs, row["snapshot_id"], row)

    def upsert_snapshot_row(self, row: Mapping[str, Any]) -> bool:
        key = (
            row["snapshot_id"],
            row["symbol"],
            row["strategy"],
            row["timeframe_ltf"],
            row["timeframe_htf"],
            row["side"],
            row["setup_id"],
        )
        return _upsert(self.snapshot_rows, key, row)

    def upsert_source_inventory(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.source_inventory, (row["snapshot_id"], row["source_name"]), row)

    def upsert_signal_event(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.signal_events, row["dedup_key"], row)

    def upsert_data_health(self, row: Mapping[str, Any]) -> bool:
        return _upsert(self.data_health, (row["snapshot_id"], row["symbol"], row["timeframe"]), row)


class MySqlOperationalStore:
    """Thin DB-API store. It does not open connections or manage credentials."""

    def __init__(self, connection: Any):
        self.connection = connection

    def upsert_strategy(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("strategy_registry", row, ["strategy_id"])

    def upsert_risk_config(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("risk_config", row, ["version"])

    def upsert_bot_config(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("bot_config", row, ["version"])

    def upsert_snapshot_run(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("snapshot_runs", row, ["snapshot_id"])

    def upsert_snapshot_row(self, row: Mapping[str, Any]) -> bool:
        return self._upsert(
            "live_context_snapshot_rows",
            row,
            ["snapshot_id", "symbol", "strategy", "timeframe_ltf", "timeframe_htf", "side", "setup_id"],
        )

    def upsert_source_inventory(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("snapshot_source_inventory", row, ["snapshot_id", "source_name"])

    def upsert_signal_event(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("signal_events", row, ["dedup_key"])

    def upsert_data_health(self, row: Mapping[str, Any]) -> bool:
        return self._upsert("data_health_snapshot", row, ["snapshot_id", "symbol", "timeframe"])

    def _upsert(self, table: str, row: Mapping[str, Any], identity_columns: list[str]) -> bool:
        payload = {key: value for key, value in row.items() if value is not None}
        columns = list(payload)
        placeholders = ", ".join(["%s"] * len(columns))
        updates = [
            f"{column} = VALUES({column})"
            for column in columns
            if column not in identity_columns and not column.endswith("_id")
        ]
        query = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {', '.join(updates) if updates else identity_columns[0] + ' = ' + identity_columns[0]}"
        )
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, [payload[column] for column in columns])
            return bool(getattr(cursor, "rowcount", 0))
        finally:
            cursor.close()


def _upsert(target: dict[Any, dict[str, Any]], key: Any, row: Mapping[str, Any]) -> bool:
    existed = key in target
    target[key] = dict(row)
    return not existed
