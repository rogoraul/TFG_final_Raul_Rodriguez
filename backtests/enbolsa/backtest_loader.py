import hashlib
import json
import pickle
from pathlib import Path

import pandas as pd

from backtests.enbolsa.GenerarIndicadores import GeneradorIndicadores
from backtests.common.backtest_matrix_config import (
    DEFAULT_ASSET_GROUPS,
    get_context_config,
    get_selected_groups,
    get_timeframe_pairs,
)
from backtests.enbolsa.market_context import AnalizadorDeContexto
from backtests.common.position_sizing import attach_symbol_spec_columns
from data.sql.sql_funcs import (
    cargar_datos_close_batch,
    cargar_datos_ohlc_batch,
    get_symbol_metadata_map,
    get_symbols_by_group_normalized,
)


PORTFOLIO_CACHE_VERSION = "enbolsa_portfolio_cache_v6"
PORTFOLIO_CACHE_DIR = (
    Path(__file__).resolve().parents[1] / ".cache" / "portfolios"
)
_MEMORY_PORTFOLIO_CACHE = {}


def _normalize_for_cache(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _normalize_for_cache(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_cache(v) for v in value]
    return value


def _build_portfolio_cache_key(
    lista_activos,
    timeframe_ltf,
    timeframe_htf,
    context_config,
    indicator_config,
):
    payload = {
        "version": PORTFOLIO_CACHE_VERSION,
        "symbols": sorted(lista_activos),
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
    cache_path = _portfolio_cache_path(cache_key)
    with cache_path.open("wb") as fh:
        pickle.dump(portfolio, fh, protocol=pickle.HIGHEST_PROTOCOL)


def _clean_processed_df(df, timeframe_htf):
    df = df.copy()

    if 'PIVOT_TYPE' in df.columns:
        df['PIVOT_TYPE'] = df['PIVOT_TYPE'].fillna(0)

    fib_cols = [col for col in df.columns if col.startswith('FIB_')]
    if fib_cols:
        df[fib_cols] = df[fib_cols].ffill()

    trend_col = f'TENDENCIA_ESTRUCTURAL_{timeframe_htf}'
    if trend_col in df.columns:
        df = df.dropna(subset=[trend_col])
    elif 'TENDENCIA_ESTRUCTURAL' in df.columns:
        df = df.dropna(subset=['TENDENCIA_ESTRUCTURAL'])

    if 'spread_price' in df.columns:
        df['spread_price'] = pd.to_numeric(df['spread_price'], errors='coerce').fillna(0.0)

    return df


def _default_point_size_from_symbol(symbol):
    if not symbol:
        return 0.00001

    raw_symbol = str(symbol)
    clean_symbol = raw_symbol.split('.')[0]

    if len(clean_symbol) >= 6 and clean_symbol[:6].isalpha():
        quote = clean_symbol[3:6]
        if quote == "JPY":
            return 0.001
        if quote == "CNH":
            return 0.0001
        return 0.00001

    if clean_symbol in {"WTI", "BRENT"}:
        return 0.001
    if clean_symbol.startswith("XAU") or clean_symbol.startswith("XAG"):
        return 0.01
    if clean_symbol in {"US500", "US100", "GER40", "EURO50", "HK50", "SPA35"}:
        return 0.1
    if raw_symbol.endswith("JPY.r") or raw_symbol.endswith("JPY"):
        return 0.001
    return 0.00001


def _resolve_point_size(df, symbol=None, symbol_meta=None):
    if symbol_meta:
        point_size = symbol_meta.get('point_size')
        if point_size is not None:
            try:
                point_size = float(point_size)
                if point_size > 0:
                    return point_size
            except (TypeError, ValueError):
                pass

        digits = symbol_meta.get('digits')
        if digits is not None:
            try:
                digits = int(digits)
                if digits >= 0:
                    return 10.0 ** (-digits)
            except (TypeError, ValueError):
                pass

    price_cols = [col for col in ('open', 'high', 'low', 'close') if col in df.columns]
    max_decimals = 0

    for col in price_cols:
        series = pd.to_numeric(df[col], errors='coerce').dropna()
        if series.empty:
            continue

        sample = series.iloc[: min(len(series), 500)]
        for value in sample:
            text = f"{float(value):.10f}".rstrip('0').rstrip('.')
            decimals = len(text.split('.')[-1]) if '.' in text else 0
            if decimals > max_decimals:
                max_decimals = decimals

    if max_decimals > 0:
        return 10.0 ** (-max_decimals)
    return _default_point_size_from_symbol(symbol)


def _attach_spread_price(df, symbol=None, symbol_meta=None):
    df = df.copy()

    if 'spread' not in df.columns:
        df['spread_price'] = 0.0
        return df

    spread_points = pd.to_numeric(df['spread'], errors='coerce').fillna(0.0)
    point_size = _resolve_point_size(df, symbol=symbol, symbol_meta=symbol_meta)
    df['spread_price'] = spread_points * point_size
    return df


def cargar_portfolio_multiactivo(
    lista_activos,
    timeframe_ltf='H1',
    timeframe_htf='H4',
    group_name=None,
    context_config=None,
    indicator_config=None,
    verbose=True,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
):
    datos_procesados = {}
    context_kwargs = get_context_config(
        group_name=group_name,
        timeframe_ltf=timeframe_ltf,
        context_config=context_config,
    )
    divergence_indicators = tuple(context_kwargs.pop('divergence_indicators', ()))
    allow_full_sample_zigzag_calibration = bool(
        context_kwargs.pop('full_sample_zigzag_calibration', False)
    )
    cache_key = _build_portfolio_cache_key(
        lista_activos=lista_activos,
        timeframe_ltf=timeframe_ltf,
        timeframe_htf=timeframe_htf,
        context_config={
            **context_kwargs,
            'divergence_indicators': divergence_indicators,
        },
        indicator_config=indicator_config or {},
    )

    if use_cache and not force_rebuild:
        cached_portfolio = _load_portfolio_from_cache(cache_key, use_disk_cache)
        if cached_portfolio is not None:
            if verbose:
                print(
                    f"=== Portfolio ENBOLSA cacheado "
                    f"({len(cached_portfolio)} activos, {timeframe_ltf}->{timeframe_htf}) ==="
                )
            return cached_portfolio

    contexto = AnalizadorDeContexto(**context_kwargs)
    generador = GeneradorIndicadores(**(indicator_config or {}))

    if verbose:
        print(
            f"=== Cargando portfolio ENBOLSA ({len(lista_activos)} activos, "
            f"{timeframe_ltf}->{timeframe_htf}) ==="
        )

    ltf_map = cargar_datos_ohlc_batch(lista_activos, timeframe_ltf)
    htf_map = cargar_datos_close_batch(lista_activos, timeframe_htf)
    symbol_metadata_map = get_symbol_metadata_map(lista_activos)

    for symbol in lista_activos:
        if verbose:
            print(f">> {symbol}...", end=" ")

        contexto.zigzag_deviation = context_kwargs.get('zigzag_deviation', 0.005)

        df_ltf = ltf_map.get(symbol)
        df_htf = htf_map.get(symbol)

        if df_ltf is None or df_htf is None:
            if verbose:
                print("[SKIP] Datos incompletos")
            continue

        try:
            df_ltf = _attach_spread_price(
                df_ltf,
                symbol=symbol,
                symbol_meta=symbol_metadata_map.get(symbol),
            )
            df_ltf = attach_symbol_spec_columns(
                df_ltf,
                symbol_metadata_map.get(symbol),
            )
            df_ltf = generador.aplicar_todo(df_ltf)
            if (
                allow_full_sample_zigzag_calibration and
                getattr(contexto, 'zigzag_mode', 'fixed') == 'fixed' and
                'ATR' in df_ltf.columns
            ):
                atr_pct = (df_ltf['ATR'] / df_ltf['close']).median()
                if pd.notna(atr_pct) and atr_pct > 0:
                    contexto.zigzag_deviation = float(atr_pct * 5.0)

            df_ltf = contexto.procesar_contexto_completo(
                df_ltf,
                lista_indicadores=list(divergence_indicators)
            )
            df_ltf = contexto.sincronizar_tendencia_htf(
                df_ltf,
                df_htf,
                suffix=f'_{timeframe_htf}'
            )
            df_ltf = _clean_processed_df(df_ltf, timeframe_htf)
            datos_procesados[symbol] = df_ltf

            if verbose:
                print(f"OK ({len(df_ltf)} velas)")
        except Exception as exc:
            if verbose:
                print(f"[ERROR] {exc}")

    if verbose:
        print(
            f"=== Portfolio listo: {len(datos_procesados)}/{len(lista_activos)} activos ==="
        )

    if use_cache:
        _save_portfolio_to_cache(cache_key, datos_procesados, use_disk_cache)

    return datos_procesados


def cargar_portfolios_matriz(
    groups=None,
    tf_pairs=None,
    context_config=None,
    indicator_config=None,
    verbose=True,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
):
    selected_groups = get_selected_groups(groups or DEFAULT_ASSET_GROUPS)
    portfolios = {}
    groups_map = get_symbols_by_group_normalized(selected_groups)

    for group_name, symbols in groups_map.items():
        if not symbols:
            continue
        for timeframe_ltf, timeframe_htf in get_timeframe_pairs(tf_pairs).items():
            key = (group_name, timeframe_ltf, timeframe_htf)
            portfolios[key] = cargar_portfolio_multiactivo(
                symbols,
                timeframe_ltf=timeframe_ltf,
                timeframe_htf=timeframe_htf,
                group_name=group_name,
                context_config=context_config,
                indicator_config=indicator_config,
                verbose=verbose,
                use_cache=use_cache,
                force_rebuild=force_rebuild,
                use_disk_cache=use_disk_cache,
            )

    return portfolios

