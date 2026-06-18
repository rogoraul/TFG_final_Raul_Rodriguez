"""Incremental MT5 data updater for enabled symbols and timeframes."""

from __future__ import annotations

from datetime import datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd

from data.mt5.closed_candles import remove_open_candles_with_server_time
from data.mt5.func_utils import (
    connect_mt5,
    disconnect_mt5,
    get_data_mt5,
    get_symbol_specs_mt5,
    symbol_specs_to_sql_payload,
)
from data.sql.sql_funcs import (
    get_enabled_symbols,
    insertar_datos,
    obtener_ultima_fecha,
    upsert_symbol_metadata,
)

TIMEFRAMES_INV = {
    mt5.TIMEFRAME_M15: "M15",
    mt5.TIMEFRAME_M30: "M30",
    mt5.TIMEFRAME_H1: "H1",
    mt5.TIMEFRAME_H4: "H4",
    mt5.TIMEFRAME_D1: "D1",
}

TIMEFRAME_MINUTES = {
    mt5.TIMEFRAME_M15: 15,
    mt5.TIMEFRAME_M30: 30,
    mt5.TIMEFRAME_H1: 60,
    mt5.TIMEFRAME_H4: 240,
    mt5.TIMEFRAME_D1: 1440,
}


def sync_symbol_metadata(symbol: str) -> None:
    """Persist MT5 symbol metadata needed by downstream sizing/audit code."""
    specs = get_symbol_specs_mt5(symbol)
    if specs is None:
        print(f"[WARN] No se pudo leer metadata MT5 para {symbol}")
        return

    ok = upsert_symbol_metadata(**symbol_specs_to_sql_payload(specs))
    if not ok:
        print(f"[WARN] No se pudo guardar metadata SQL para {symbol}")


def remove_open_candles(df, timeframe_value: int, symbol: str):
    """Remove the current open candle using MT5 server time when available.

    Args:
        df: DataFrame with a `time` column.
        timeframe_value: MT5 timeframe constant.
        symbol: Symbol used to read current server tick time.

    Returns:
        DataFrame containing only closed candles when tick data is available.
    """
    if df is None or len(df) == 0:
        return df

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"[!] No se pudo obtener tick de {symbol}, no se filtrara ultima vela")
        return df

    timeframe_name = TIMEFRAMES_INV.get(timeframe_value, str(timeframe_value))
    return remove_open_candles_with_server_time(
        df,
        timeframe_value,
        tick.time,
        symbol=symbol,
        timeframe_label=timeframe_name,
        timeframe_minutes_map=TIMEFRAME_MINUTES,
    )


def update_data(symbol: str, timeframe_value: int) -> None:
    """Update one symbol/timeframe from the last stored date to current MT5 data."""
    timeframe_name = TIMEFRAMES_INV.get(timeframe_value, None)
    last_date = obtener_ultima_fecha(symbol, timeframe_name)

    if last_date is None:
        print(f"[!] No hay datos previos de {symbol}-{timeframe_name}, descarga completa.")
        date_from = datetime(2020, 1, 1)
    else:
        date_from = pd.to_datetime(last_date) - timedelta(days=1)

    date_to = datetime.now() + timedelta(days=1)

    df_new = get_data_mt5(symbol, timeframe_value, date_from, date_to)
    df_new = remove_open_candles(df_new, timeframe_value, symbol)

    if df_new is not None and len(df_new) > 0:
        insertar_datos(df_new, symbol, timeframe_name)
        print(f"[OK] Actualizados {len(df_new)} registros de {symbol}-{timeframe_name}.")
    else:
        print(f"[-] Sin nuevos datos para {symbol}-{timeframe_name}.")


def update_batch(timeframes_list: list[int]) -> None:
    """Connect to MT5 and update all enabled symbols for the requested timeframes."""
    if not connect_mt5():
        print("[X] Error al conectar a MT5 para update_batch")
        return

    active_symbols = get_enabled_symbols()
    print(f"[INFO] Iniciando actualizacion masiva para {len(active_symbols)} simbolos en {len(timeframes_list)} timeframes.")

    for symbol in active_symbols:
        sync_symbol_metadata(symbol)
        for tf_val in timeframes_list:
            update_data(symbol, tf_val)

    disconnect_mt5()
    print("[OK] Actualizacion masiva completada.")
