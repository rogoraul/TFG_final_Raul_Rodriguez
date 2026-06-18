"""Utilities for reading market data and symbol metadata from MetaTrader 5."""

from __future__ import annotations

import MetaTrader5 as mt5
import pandas as pd


def connect_mt5() -> bool:
    """Open the MT5 connection and return whether initialization succeeded."""
    conexion = True
    if not mt5.initialize():
        print("No se pudo conectar a MetaTrader 5")
        conexion = False
    return conexion


def disconnect_mt5() -> None:
    """Close the current MT5 session."""
    mt5.shutdown()


def get_data_mt5(symbol: str, timeframe: int, date_from, date_to) -> pd.DataFrame | None:
    """Download candles for one symbol/timeframe between two dates.

    Args:
        symbol: MT5 symbol name.
        timeframe: MT5 timeframe constant.
        date_from: Start date accepted by `copy_rates_range`.
        date_to: End date accepted by `copy_rates_range`.

    Returns:
        DataFrame with normalized `time`, or None when MT5 returns no rows.
    """
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None or len(rates) == 0:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def _safe_float_attr(info, attr_name: str) -> float | None:
    """Read a float-like MT5 attribute defensively."""
    value = getattr(info, attr_name, None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int_attr(info, attr_name: str) -> int | None:
    """Read an int-like MT5 attribute defensively."""
    value = getattr(info, attr_name, None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def get_symbol_specs_mt5(symbol: str) -> dict[str, object] | None:
    """Read precision and sizing metadata for a symbol from MT5.

    Returns:
        Dict with precision/sizing fields, or None when basic metadata is missing.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return None

    digits = getattr(info, 'digits', None)
    point_size = getattr(info, 'point', None)

    if digits is None or point_size is None:
        return None

    try:
        digits = int(digits)
        point_size = float(point_size)
    except (TypeError, ValueError):
        return None

    if digits < 0 or point_size <= 0:
        return None

    return {
        'symbol': symbol,
        'digits': digits,
        'point_size': point_size,
        'trade_tick_size': _safe_float_attr(info, 'trade_tick_size'),
        'trade_tick_value': _safe_float_attr(info, 'trade_tick_value'),
        'trade_tick_value_profit': _safe_float_attr(info, 'trade_tick_value_profit'),
        'trade_tick_value_loss': _safe_float_attr(info, 'trade_tick_value_loss'),
        'trade_contract_size': _safe_float_attr(info, 'trade_contract_size'),
        'volume_min': _safe_float_attr(info, 'volume_min'),
        'volume_max': _safe_float_attr(info, 'volume_max'),
        'volume_step': _safe_float_attr(info, 'volume_step'),
        'currency_base': getattr(info, 'currency_base', None),
        'currency_profit': getattr(info, 'currency_profit', None),
        'currency_margin': getattr(info, 'currency_margin', None),
        'trade_mode': _safe_int_attr(info, 'trade_mode'),
    }


def symbol_specs_to_sql_payload(specs: dict[str, object], *, source: str = "MT5") -> dict[str, object]:
    """Map MT5 symbol metadata to the `upsert_symbol_metadata` keyword contract."""
    return {
        'symbol': specs['symbol'],
        'digits': specs['digits'],
        'point_size': specs['point_size'],
        'source': source,
        'trade_tick_size': specs.get('trade_tick_size'),
        'trade_tick_value': specs.get('trade_tick_value'),
        'trade_tick_value_profit': specs.get('trade_tick_value_profit'),
        'trade_tick_value_loss': specs.get('trade_tick_value_loss'),
        'trade_contract_size': specs.get('trade_contract_size'),
        'volume_min': specs.get('volume_min'),
        'volume_max': specs.get('volume_max'),
        'volume_step': specs.get('volume_step'),
        'currency_base': specs.get('currency_base'),
        'currency_profit': specs.get('currency_profit'),
        'currency_margin': specs.get('currency_margin'),
        'trade_mode': specs.get('trade_mode'),
    }
