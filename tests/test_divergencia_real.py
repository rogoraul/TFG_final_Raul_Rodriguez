"""Optional SQL-backed comparison between legacy and numba divergence logic."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from backtests.enbolsa.GenerarIndicadores import GeneradorIndicadores
from backtests.enbolsa.market_context import AnalizadorDeContexto
from data.sql.sql_funcs import close_db, connect_db


pytestmark = pytest.mark.integration_sql


def detectar_divergencias_old(df, col_indicador, nombre_salida_base="DIV", tolerance=0.003):
    """Legacy pure-Python divergence implementation kept for parity checks."""
    ind_tolerance = 0.0
    if "RSI" in col_indicador or "STOCH_K" in col_indicador:
        ind_tolerance = 1.0
    elif "EWO" in col_indicador or "MACD_HISTOGRAMA" in col_indicador:
        ind_tolerance = 0.0001

    tipos = ["REGULAR_A", "REGULAR_B", "OCULTA_A", "OCULTA_B"]
    for kind in tipos:
        df[f"{nombre_salida_base}_{col_indicador}_{kind}_OLD"] = 0

    pivot_indices = df.index[df["PIVOT_TYPE"] != 0].tolist()
    if len(pivot_indices) < 3:
        return df

    for index in range(2, len(pivot_indices)):
        curr_idx = pivot_indices[index]
        prev_idx = pivot_indices[index - 2]
        pivot_type = df.loc[curr_idx, "PIVOT_TYPE"]
        if pivot_type != df.loc[prev_idx, "PIVOT_TYPE"]:
            continue

        current_price = df.loc[curr_idx, "close"]
        previous_price = df.loc[prev_idx, "close"]
        current_indicator = df.loc[curr_idx, col_indicador]
        previous_indicator = df.loc[prev_idx, col_indicador]

        price_diff = (current_price - previous_price) / previous_price
        same_level = abs(price_diff) <= tolerance
        indicator_down = current_indicator < (previous_indicator - ind_tolerance)
        indicator_up = current_indicator > (previous_indicator + ind_tolerance)

        if pivot_type == 1:
            if indicator_down:
                if same_level:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_REGULAR_B_OLD"] = -1
                elif price_diff > tolerance:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_REGULAR_A_OLD"] = -1
            elif indicator_up:
                if same_level:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_OCULTA_B_OLD"] = -1
                elif price_diff < -tolerance:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_OCULTA_A_OLD"] = -1
        elif pivot_type == -1:
            if indicator_up:
                if same_level:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_REGULAR_B_OLD"] = 1
                elif price_diff < -tolerance:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_REGULAR_A_OLD"] = 1
            elif indicator_down:
                if same_level:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_OCULTA_B_OLD"] = 1
                elif price_diff > tolerance:
                    df.loc[curr_idx, f"{nombre_salida_base}_{col_indicador}_OCULTA_A_OLD"] = 1

    return df


def _load_sample(symbol: str = "EURUSD.r", timeframe: str = "M15", limit: int = 10000) -> pd.DataFrame:
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
def test_numba_divergence_matches_legacy_on_real_sql_sample() -> None:
    """Compare the optimized divergence engine against the legacy reference."""
    frame = _load_sample()
    frame = GeneradorIndicadores().aplicar_todo(frame)

    analyzer = AnalizadorDeContexto(zigzag_deviation=0.002, tolerance=0.001)
    frame = analyzer.calcular_tendencia(frame)
    frame = analyzer.calcular_zigzag(frame)

    if int((frame["PIVOT_TYPE"] != 0).sum()) < 10:
        pytest.skip("Not enough pivots in the local SQL sample")

    indicator = "RSI"
    old_frame = detectar_divergencias_old(frame.copy(), indicator, tolerance=analyzer.tolerance)
    new_frame = analyzer.detectar_divergencias(frame.copy(), indicator)

    for kind in ["REGULAR_A", "REGULAR_B", "OCULTA_A", "OCULTA_B"]:
        new_values = new_frame[f"DIV_{indicator}_{kind}"].fillna(0).values
        old_values = old_frame[f"DIV_{indicator}_{kind}_OLD"].fillna(0).values
        np.testing.assert_array_equal(new_values, old_values)
