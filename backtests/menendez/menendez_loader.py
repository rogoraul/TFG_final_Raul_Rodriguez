from __future__ import annotations

import os
import hashlib
import json
import pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from backtests.common.position_sizing import attach_symbol_spec_columns
from data.sql.sql_funcs import (
    cargar_datos_ohlc_batch,
    get_symbol_metadata_map,
    get_symbols_by_group_normalized,
)

from backtests.menendez.menendez_config import (
    DEFAULT_GROUP,
    DEFAULT_TIMEFRAME_HTF,
    DEFAULT_TIMEFRAME_LTF,
    get_context_config,
    get_indicator_config,
)
from backtests.menendez.menendez_context import MenendezContextAnalyzer
from backtests.menendez.menendez_indicators import MenendezIndicatorEngine


PORTFOLIO_CACHE_VERSION = "menendez_portfolio_cache_v1"
PORTFOLIO_CACHE_DIR = (
    Path(__file__).resolve().parents[1] / ".cache" / "menendez_portfolios"
)
_MEMORY_PORTFOLIO_CACHE = {}


def _normalize_for_cache(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _normalize_for_cache(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_cache(item) for item in value]
    return value


def _coerce_bool_series(series):
    series = pd.Series(series, copy=False)
    return series.where(series.notna(), False).astype(bool)


def _resolve_max_workers(item_count, max_workers=None):
    if item_count <= 1:
        return 1
    if max_workers is not None:
        return max(1, min(int(max_workers), int(item_count)))
    cpu_count = os.cpu_count() or 1
    return max(1, min(int(item_count), int(cpu_count)))


def _build_portfolio_cache_key(symbols, timeframe_ltf, timeframe_htf, context_config, indicator_config):
    payload = {
        "version": PORTFOLIO_CACHE_VERSION,
        "symbols": sorted(symbols),
        "ltf": timeframe_ltf,
        "htf": timeframe_htf,
        "context_config": _normalize_for_cache(context_config),
        "indicator_config": _normalize_for_cache(indicator_config),
    }
    payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _portfolio_cache_path(cache_key):
    return PORTFOLIO_CACHE_DIR / f"{cache_key}.pkl"


def clear_portfolio_cache(memory_only=False):
    _MEMORY_PORTFOLIO_CACHE.clear()
    if memory_only:
        return
    if PORTFOLIO_CACHE_DIR.exists():
        for cache_file in PORTFOLIO_CACHE_DIR.glob("*.pkl"):
            cache_file.unlink(missing_ok=True)


def _load_portfolio_from_cache(cache_key, use_disk_cache):
    if cache_key in _MEMORY_PORTFOLIO_CACHE:
        return _MEMORY_PORTFOLIO_CACHE[cache_key]
    if not use_disk_cache:
        return None
    cache_path = _portfolio_cache_path(cache_key)
    if not cache_path.exists():
        return None
    with cache_path.open("rb") as fh:
        portfolio = pickle.load(fh)
    _MEMORY_PORTFOLIO_CACHE[cache_key] = portfolio
    return portfolio


def _save_portfolio_to_cache(cache_key, portfolio, use_disk_cache):
    _MEMORY_PORTFOLIO_CACHE[cache_key] = portfolio
    if not use_disk_cache:
        return
    PORTFOLIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _portfolio_cache_path(cache_key).open("wb") as fh:
        pickle.dump(portfolio, fh, protocol=pickle.HIGHEST_PROTOCOL)


def _clean_processed_df(df):
    df = df.copy()
    df["spread_price"] = pd.to_numeric(df.get("spread_price", 0.0), errors="coerce").fillna(0.0)
    bool_columns = [
        "H4_MACD_NEUTRAL", "H4_STANDBY",
        "H4_PSAR_FLIP_EVENT", "H4_PSAR_LATERAL",
        "H4_MACD_ZLR_BULL", "H4_MACD_ZLR_BEAR", "H4_MACD_ZLR_RELEVANT",
        "H4_ATTRACTOR_PSAR_OK", "H4_ATTRACTOR_FAN_OK",
        "H4_ATTRACTOR_SLOPE_OK", "H4_ATTRACTOR_TREND_OK", "H4_ATTRACTOR_MACD_OK",
        "PSAR_FLIP_LONG", "PSAR_FLIP_SHORT",
        "BULLISH_FAN", "BEARISH_FAN",
        "SMA_5_8_CROSS_UP", "SMA_5_8_CROSS_DOWN",
        "SMA_8_13_CROSS_UP", "SMA_8_13_CROSS_DOWN",
        "SMA_13_21_CROSS_UP", "SMA_13_21_CROSS_DOWN",
        "SMA_50_200_CROSS_UP", "SMA_50_200_CROSS_DOWN",
        "H4_SMA_5_8_CROSS_UP", "H4_SMA_5_8_CROSS_DOWN",
        "H4_SMA_8_13_CROSS_UP", "H4_SMA_8_13_CROSS_DOWN",
        "H4_SMA_13_21_CROSS_UP", "H4_SMA_13_21_CROSS_DOWN",
        "H4_SMA_50_200_CROSS_UP", "H4_SMA_50_200_CROSS_DOWN",
        "STOCH_CROSS_UP", "STOCH_CROSS_DOWN",
        "HTF_GATE_OK", "SETUP_CANDIDATE", "RETRACE_OK",
        "FAN_BREAKOUT", "MACD_TRIGGER", "STOCH_TRIGGER", "PSAR_TRIGGER",
        "PRIMARY_TRIGGER", "MOMENTUM_CONFIRM", "SESSION_OK", "RR_OK", "ENTRY_READY",
        "X_TOUCH_SMA21", "X_TOUCH_SMA50", "X_POSSIBLE_COMPOSITE",
    ]
    for column_name in bool_columns:
        if column_name in df.columns:
            df[column_name] = _coerce_bool_series(df[column_name])

    int_columns = [
        "PSAR_POLARITY", "M30_PSAR_POLARITY",
        "H4_ATTRACTOR_DIR", "H4_PSAR_POLARITY", "H4_PSAR_FLIP_COUNT_WINDOW",
        "FRACTAL_SEGMENT_COUNT", "BASE_CHANNEL_STATE", "DECEL_CHANNEL_STATE",
        "ENTRY_DIR", "SETUP_DIR", "X_END_CLOSE_VS_SMA21", "X_END_CLOSE_VS_SMA50",
        "X_SEGMENT_COUNT",
    ]
    for column_name in int_columns:
        if column_name in df.columns:
            df[column_name] = pd.to_numeric(df[column_name], errors="coerce").fillna(0).astype(int)

    if "H4_ATTRACTOR_DIR" in df.columns:
        df = df.dropna(subset=["H4_ATTRACTOR_DIR"])
    return df


def _default_point_size_from_symbol(symbol):
    if not symbol:
        return 0.00001

    raw_symbol = str(symbol)
    clean_symbol = raw_symbol.split(".")[0]

    if len(clean_symbol) >= 6 and clean_symbol[:6].isalpha():
        quote = clean_symbol[3:6]
        if quote == "JPY":
            return 0.001
        if quote == "CNH":
            return 0.0001
        return 0.00001

    if raw_symbol.endswith("JPY.r") or raw_symbol.endswith("JPY"):
        return 0.001
    return 0.00001


def _resolve_point_size(df, symbol=None, symbol_meta=None):
    if symbol_meta:
        point_size = symbol_meta.get("point_size")
        if point_size is not None:
            try:
                point_size = float(point_size)
                if point_size > 0:
                    return point_size
            except (TypeError, ValueError):
                pass

        digits = symbol_meta.get("digits")
        if digits is not None:
            try:
                digits = int(digits)
                if digits >= 0:
                    return 10.0 ** (-digits)
            except (TypeError, ValueError):
                pass

    max_decimals = 0
    for column_name in ("open", "high", "low", "close"):
        if column_name not in df.columns:
            continue
        series = pd.to_numeric(df[column_name], errors="coerce").dropna()
        if series.empty:
            continue
        sample = series.iloc[: min(len(series), 500)]
        for value in sample:
            text = f"{float(value):.10f}".rstrip("0").rstrip(".")
            decimals = len(text.split(".")[-1]) if "." in text else 0
            if decimals > max_decimals:
                max_decimals = decimals

    if max_decimals > 0:
        return 10.0 ** (-max_decimals)
    return _default_point_size_from_symbol(symbol)


def _attach_spread_price(df, symbol=None, symbol_meta=None):
    df = df.copy()
    if "spread" not in df.columns:
        df["spread_price"] = 0.0
        return df

    spread_points = pd.to_numeric(df["spread"], errors="coerce").fillna(0.0)
    point_size = _resolve_point_size(df, symbol=symbol, symbol_meta=symbol_meta)
    df["spread_price"] = spread_points * point_size
    return df


def _build_symbol_artifacts(symbol, df_ltf, df_htf, symbol_meta, indicator_kwargs, context_kwargs):
    if df_ltf is None or df_htf is None or df_ltf.empty or df_htf.empty:
        raise ValueError("Datos incompletos")

    engine = MenendezIndicatorEngine(**indicator_kwargs)
    analyzer = MenendezContextAnalyzer(**context_kwargs)

    ltf_raw = _attach_spread_price(df_ltf, symbol=symbol, symbol_meta=symbol_meta)
    ltf_with_specs = attach_symbol_spec_columns(ltf_raw, symbol_meta)
    ltf_indicators = engine.aplicar_todo(ltf_with_specs)

    htf_raw = _attach_spread_price(df_htf, symbol=symbol, symbol_meta=symbol_meta)
    htf_indicators = engine.aplicar_todo(htf_raw)
    htf_context = analyzer.calcular_atractor_htf(htf_indicators)

    merged = analyzer.sincronizar_contexto_htf(ltf_indicators, htf_context)
    processed = analyzer.procesar_contexto_m30(merged)
    processed = _clean_processed_df(processed)
    return {
        "symbol": symbol,
        "ltf_raw": ltf_raw,
        "ltf_with_specs": ltf_with_specs,
        "ltf_indicators": ltf_indicators,
        "htf_raw": htf_raw,
        "htf_indicators": htf_indicators,
        "htf_context": htf_context,
        "merged": merged,
        "processed": processed,
    }


def cargar_bundle_menendez_symbol(
    symbol,
    timeframe_ltf=DEFAULT_TIMEFRAME_LTF,
    timeframe_htf=DEFAULT_TIMEFRAME_HTF,
    context_config=None,
    indicator_config=None,
):
    indicator_kwargs = get_indicator_config(indicator_config)
    context_kwargs = get_context_config(context_config)
    ltf_map = cargar_datos_ohlc_batch([symbol], timeframe_ltf)
    htf_map = cargar_datos_ohlc_batch([symbol], timeframe_htf)
    symbol_meta = get_symbol_metadata_map([symbol]).get(symbol)
    return _build_symbol_artifacts(
        symbol=symbol,
        df_ltf=ltf_map.get(symbol),
        df_htf=htf_map.get(symbol),
        symbol_meta=symbol_meta,
        indicator_kwargs=indicator_kwargs,
        context_kwargs=context_kwargs,
    )


def cargar_portfolio_menendez(
    symbols=None,
    group_name=DEFAULT_GROUP,
    timeframe_ltf=DEFAULT_TIMEFRAME_LTF,
    timeframe_htf=DEFAULT_TIMEFRAME_HTF,
    context_config=None,
    indicator_config=None,
    verbose=True,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
    parallel=True,
    max_workers=None,
):
    selected_symbols = list(symbols or get_symbols_by_group_normalized([group_name]).get(group_name, []))
    if not selected_symbols:
        return {}

    indicator_kwargs = get_indicator_config(indicator_config)
    context_kwargs = get_context_config(context_config)
    cache_key = _build_portfolio_cache_key(
        selected_symbols,
        timeframe_ltf,
        timeframe_htf,
        context_kwargs,
        indicator_kwargs,
    )

    if use_cache and not force_rebuild:
        cached = _load_portfolio_from_cache(cache_key, use_disk_cache)
        if cached is not None:
            if verbose:
                print(
                    f"=== Portfolio Menendez cacheado "
                    f"({len(cached)} activos, {timeframe_htf}->{timeframe_ltf}) ==="
                )
            return cached

    if verbose:
        print(
            f"=== Cargando portfolio Menendez ({len(selected_symbols)} activos, "
            f"{timeframe_htf}->{timeframe_ltf}) ==="
        )

    ltf_map = cargar_datos_ohlc_batch(selected_symbols, timeframe_ltf)
    htf_map = cargar_datos_ohlc_batch(selected_symbols, timeframe_htf)
    symbol_metadata_map = get_symbol_metadata_map(selected_symbols)

    portfolio = {}
    resolved_workers = _resolve_max_workers(len(selected_symbols), max_workers) if parallel else 1

    def _run_symbol(symbol):
        symbol_meta = symbol_metadata_map.get(symbol)
        return _build_symbol_artifacts(
            symbol=symbol,
            df_ltf=ltf_map.get(symbol),
            df_htf=htf_map.get(symbol),
            symbol_meta=symbol_meta,
            indicator_kwargs=indicator_kwargs,
            context_kwargs=context_kwargs,
        )

    if resolved_workers <= 1:
        for symbol in selected_symbols:
            try:
                artifacts = _run_symbol(symbol)
                portfolio[symbol] = artifacts["processed"]
                if verbose:
                    print(f">> {symbol}... OK ({len(artifacts['processed'])} velas)")
            except Exception as exc:
                if verbose:
                    print(f">> {symbol}... [ERROR] {exc}")
    else:
        completed = {}
        with ThreadPoolExecutor(max_workers=resolved_workers, thread_name_prefix="menendez-load") as executor:
            future_map = {executor.submit(_run_symbol, symbol): symbol for symbol in selected_symbols}
            for future in as_completed(future_map):
                symbol = future_map[future]
                try:
                    artifacts = future.result()
                    completed[symbol] = artifacts["processed"]
                    if verbose:
                        print(f">> {symbol}... OK ({len(artifacts['processed'])} velas)")
                except Exception as exc:
                    if verbose:
                        print(f">> {symbol}... [ERROR] {exc}")
        for symbol in selected_symbols:
            if symbol in completed:
                portfolio[symbol] = completed[symbol]

    if verbose:
        print(
            f"=== Portfolio Menendez listo: {len(portfolio)}/{len(selected_symbols)} activos ==="
        )

    if use_cache:
        _save_portfolio_to_cache(cache_key, portfolio, use_disk_cache)
    return portfolio
