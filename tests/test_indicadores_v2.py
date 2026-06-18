"""Optional SQL-backed integration check for the classic indicator/context stack."""

from __future__ import annotations

import os

import pandas as pd
import pytest

from backtests.enbolsa.GenerarIndicadores import GeneradorIndicadores
from backtests.enbolsa.market_context import AnalizadorDeContexto
from data.sql.sql_funcs import close_db, connect_db


pytestmark = pytest.mark.integration_sql


def _load_sample(symbol: str = "EURUSD.r", timeframe: str = "M15", limit: int = 5000) -> pd.DataFrame:
    connection = connect_db()
    if connection is None:
        pytest.skip("Local SQL database is not available")

    query = """
        SELECT time, open, high, low, close, tick_volume as volume
        FROM price_data
        WHERE symbol = %s AND timeframe = %s
        ORDER BY time DESC
        LIMIT %s
    """
    try:
        frame = pd.read_sql(query, connection, params=(symbol, timeframe, limit))
    finally:
        close_db(connection)

    if frame.empty:
        pytest.skip(f"No SQL candles available for {symbol}-{timeframe}")
    return frame.sort_values("time").reset_index(drop=True)


@pytest.mark.skipif(os.getenv("RUN_REAL_SQL_TESTS") != "1", reason="set RUN_REAL_SQL_TESTS=1 to run SQL integration tests")
def test_indicator_and_context_stack_with_real_sql_sample() -> None:
    """Validate indicators/context on a real local SQL sample when explicitly enabled."""
    frame = _load_sample()

    indicators = GeneradorIndicadores(
        rsi_len=14,
        atr_len=14,
        ewo_fast=5,
        ewo_slow=35,
        stoch_k=14,
        stoch_d=3,
        ma_short=50,
        ma_long=150,
        ma_type="wma",
    )
    enriched = indicators.aplicar_todo(frame)

    required_indicator_columns = {"RSI", "ATR", "EWO", "MACD_LINE", "MACD_SIGNAL", "STOCH_K"}
    assert required_indicator_columns.issubset(enriched.columns)

    context = AnalizadorDeContexto(
        trend_fast=50,
        trend_slow=150,
        trend_type="wma",
        zigzag_deviation=0.005,
        tolerance=0.001,
    )
    contextual = context.procesar_contexto_completo(enriched, lista_indicadores=["RSI", "EWO", "STOCH_K"])

    required_context_columns = {
        "TENDENCIA_ESTRUCTURAL",
        "PIVOT_TYPE",
        "DIV_RSI_REGULAR_A",
        "DIV_RSI_OCULTA_A",
    }
    assert required_context_columns.issubset(contextual.columns)
    assert len(contextual) == len(frame)
