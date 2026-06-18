from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from trading_center import sql_market_data_readonly as readonly


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.rows: list[tuple] = []
        self.description: list[tuple[str]] = []
        self.executed_query = ""
        self.params = ()
        self.closed = False

    def execute(self, query: str, params=()) -> None:
        self.executed_query = query
        self.params = tuple(params)
        if "FROM symbol_control" in query and "price_data" not in query:
            self.rows = self.connection.symbol_rows
            self.description = [(column,) for column in self.connection.symbol_columns]
        else:
            timeframe = self.params[1] if len(self.params) > 1 else None
            self.rows = [row for row in self.connection.ohlc_rows if timeframe is None or row[2] == timeframe]
            self.description = [(column,) for column in self.connection.ohlc_columns]

    def fetchall(self) -> list[tuple]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, symbol_rows: list[tuple], symbol_columns: list[str], ohlc_rows: list[tuple], ohlc_columns: list[str]) -> None:
        self.symbol_rows = symbol_rows
        self.symbol_columns = symbol_columns
        self.ohlc_rows = ohlc_rows
        self.ohlc_columns = ohlc_columns
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.closed = True


def test_query_guard_allows_only_select() -> None:
    config = readonly.SqlMarketDataReadonlyConfig()
    query, params = readonly.build_enabled_symbols_query(config)
    pair_query = readonly.build_pair_ohlc_query()

    assert readonly.is_select_only_query(query)
    assert readonly.is_select_only_query(pair_query)
    assert not readonly.is_select_only_query("DELETE FROM price_data")
    assert not readonly.is_select_only_query("SELECT * FROM price_data; DROP TABLE price_data")
    assert len(params) == 0


def test_sql_readonly_extractor_writes_sanitized_artifacts(tmp_path: Path, monkeypatch) -> None:
    columns = [
        "market_group",
        "symbol",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    ]
    ohlc_rows = [
        ("Forex Majors", "EURUSD.r", "M15", pd.Timestamp("2026-01-01 00:00:00"), 1.1, 1.2, 1.0, 1.15, 100, 1, 0),
        ("Forex Majors", "EURUSD.r", "H1", pd.Timestamp("2026-01-01 01:00:00"), 1.1, 1.2, 1.0, 1.16, 100, 1, 0),
    ]
    fake_connection = FakeConnection(
        symbol_rows=[("EURUSD.r", "Forex Majors")],
        symbol_columns=["symbol", "market_group"],
        ohlc_rows=ohlc_rows,
        ohlc_columns=columns,
    )
    monkeypatch.setattr(
        readonly,
        "load_db_config",
        lambda: ({"host": "localhost", "port": 3306, "user": "tester", "password": "secret", "database": "trading_data"}, "test"),
    )

    result = readonly.extract_sql_market_data(
        readonly.SqlMarketDataReadonlyConfig(output_dir=tmp_path),
        connection_factory=lambda _: fake_connection,
    )

    run_meta = json.loads((tmp_path / "run_meta.json").read_text(encoding="utf-8"))
    query_audit = (tmp_path / "tables/sql_readonly_query_audit.csv").read_text(encoding="utf-8")
    config_audit = (tmp_path / "tables/sql_readonly_config_audit.csv").read_text(encoding="utf-8")

    assert result.run_meta["sql_real_read"] is True
    assert run_meta["sql_real_written"] is False
    assert run_meta["ddl_executed"] is False
    assert run_meta["db_connected"] is True
    assert run_meta["db_config_values_printed"] is False
    assert run_meta["db_credentials_stored"] is False
    assert len(result.ohlc) == 2
    assert (tmp_path / "ohlc_mtf.csv").exists()
    assert "secret" not in query_audit
    assert "secret" not in config_audit
    assert fake_connection.closed is True


def test_sql_readonly_refuses_nonlocal_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        readonly,
        "load_db_config",
        lambda: ({"host": "192.168.1.15", "port": 3306, "user": "tester", "password": "", "database": "trading_data"}, "test"),
    )

    result = readonly.extract_sql_market_data(readonly.SqlMarketDataReadonlyConfig(output_dir=tmp_path))

    assert result.run_meta["db_connected"] is False
    assert result.run_meta["sql_real_read"] is False
    assert result.run_meta["decision"] == "sql_market_data_readonly_blocked_by_safety"
