"""Historical MT5 candle loader into the local SQL store."""

from __future__ import annotations

import MetaTrader5 as mt5

from data.mt5.closed_candles import remove_open_candles_with_server_time
from data.mt5.func_utils import (
    connect_mt5,
    disconnect_mt5,
    get_symbol_specs_mt5,
    symbol_specs_to_sql_payload,
)
from data.mt5.historical import get_all_available_data
from data.sql.sql_funcs import get_enabled_symbols, insertar_datos, upsert_symbol_metadata

TIMEFRAMES = {
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def sync_symbol_metadata(symbol: str) -> None:
    """Persist MT5 symbol metadata needed for sizing and auditability."""
    specs = get_symbol_specs_mt5(symbol)
    if specs is None:
        print(f"[WARN] No se pudo leer metadata MT5 para {symbol}")
        return

    ok = upsert_symbol_metadata(**symbol_specs_to_sql_payload(specs))
    if not ok:
        print(f"[WARN] No se pudo guardar metadata SQL para {symbol}")


def remove_open_candles(df, timeframe_name: str, symbol: str):
    """Remove the current open candle using MT5 server time when available."""
    if df is None or len(df) == 0:
        return df

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"[!] No se pudo obtener tick de {symbol}, no se filtrara ultima vela")
        return df

    return remove_open_candles_with_server_time(
        df,
        timeframe_name,
        tick.time,
        symbol=symbol,
        timeframe_label=timeframe_name,
    )


def main() -> None:
    """Run the full historical loader for all enabled SQL symbols/timeframes."""
    if not connect_mt5():
        print("[X] No se pudo conectar a MetaTrader 5.")
        return

    symbols = get_enabled_symbols()
    print(f"[INFO] Simbolos habilitados: {symbols}")

    for symbol in symbols:
        sync_symbol_metadata(symbol)
        for tf_name, tf_value in TIMEFRAMES.items():
            print(f"[DOWN] Descargando {symbol} - {tf_name}")
            df = get_all_available_data(symbol, tf_value, days_per_chunk=30)
            df = remove_open_candles(df, tf_name, symbol)
            if df is not None:
                insertar_datos(df, symbol, tf_name)
            else:
                print(f"[WARN] No se obtuvieron datos para {symbol}-{tf_name}")

    disconnect_mt5()


if __name__ == "__main__":
    main()
