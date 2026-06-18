from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd

from backtests.common.position_sizing import (
    SYMBOL_SPEC_COLUMN_MAP,
    apply_risk_position_sizing,
    calculate_lot_size_for_risk,
    extract_symbol_spec_from_row,
)
from backtests.common.trade_analysis import (
    metrics_from_trades,
    generate_result_breakdowns,
    extract_trades_from_result,
    summarize_periods,
)

from backtests.menendez.menendez_config import (
    DEFAULT_GROUP,
    DEFAULT_STRATEGIES,
    DEFAULT_TIMEFRAME_HTF,
    DEFAULT_TIMEFRAME_LTF,
    TEMPORAL_SPLITS,
    get_account_config,
    get_experiment_contract,
    get_strategy_definitions,
    get_variant_specs,
)


SYMBOL_SPEC_COLUMNS = tuple(SYMBOL_SPEC_COLUMN_MAP.values())


def _safe_float(value, default=np.nan):
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool_series(series, index=None):
    series = pd.Series(series, index=index, copy=False)
    return series.where(series.notna(), False).astype(bool)


def _resolve_max_workers(item_count, max_workers=None):
    if item_count <= 1:
        return 1
    if max_workers is not None:
        return max(1, min(int(max_workers), int(item_count)))
    cpu_count = os.cpu_count() or 1
    return max(1, min(int(item_count), int(cpu_count)))


def _is_finite_number(value):
    try:
        return np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _metricas_desde_trades(trades):
    return metrics_from_trades(trades)


def extraer_metricas(trades):
    return metrics_from_trades(trades)


def _trade_book_to_frame(trade_book):
    frames = []
    for strategy_name, trades in (trade_book or {}).items():
        if trades is None or trades.empty:
            continue
        frame = trades.copy()
        if "strategy" not in frame.columns:
            frame["strategy"] = strategy_name
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def generar_desgloses_resultado(resultado, top_n=8):
    return generate_result_breakdowns(resultado, top_n=top_n)


def _normalize_direction_filter(direction):
    if direction is None:
        return None
    if isinstance(direction, str):
        text = direction.strip().lower()
        if text in {"long", "largo", "buy", "compra", "compras"}:
            return 1
        if text in {"short", "corto", "sell", "venta", "ventas"}:
            return -1
    try:
        direction_value = int(direction)
    except (TypeError, ValueError):
        return None
    return direction_value if direction_value in {1, -1} else None


def extraer_trades_resultado(resultado, strategy=None, symbol=None, direction=None, exit_reason=None):
    direction_filter = _normalize_direction_filter(direction)
    return extract_trades_from_result(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction_filter,
        exit_reason=exit_reason,
    )


def resumir_portfolio_cargado(portfolio):
    rows = []
    if not portfolio:
        return pd.DataFrame(columns=[
            "Activo", "Velas", "Inicio", "Fin", "Dias", "VelasVsMax%", "VelasMenosQueMax"
        ])

    max_rows = max(len(df) for df in portfolio.values()) if portfolio else 0
    for symbol, df in portfolio.items():
        if df is None or df.empty:
            rows.append({
                "Activo": symbol,
                "Velas": 0,
                "Inicio": pd.NaT,
                "Fin": pd.NaT,
                "Dias": 0.0,
                "VelasVsMax%": 0.0,
                "VelasMenosQueMax": max_rows,
            })
            continue
        start = pd.Timestamp(df.index.min())
        end = pd.Timestamp(df.index.max())
        n_rows = len(df)
        rows.append({
            "Activo": symbol,
            "Velas": n_rows,
            "Inicio": start,
            "Fin": end,
            "Dias": round((end - start).total_seconds() / 86400.0, 1),
            "VelasVsMax%": round((n_rows / max_rows) * 100.0, 1) if max_rows > 0 else 0.0,
            "VelasMenosQueMax": int(max_rows - n_rows),
        })
    return pd.DataFrame(rows).sort_values(["Velas", "Activo"], ascending=[False, True]).reset_index(drop=True)


def resumir_embudo_senales(portfolio, min_rr=1.0):
    columns = [
        "Activo", "Velas", "H4_BLOCKED", "HTF_OK", "SETUP_ROWS", "RETRACE_OK",
        "FAN_BREAKOUT", "MACD_TRIGGER", "STOCH_TRIGGER", "RR_OK", "ENTRY_READY",
    ]
    rows = []

    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            rows.append({
                "Activo": symbol,
                "Velas": 0,
                "H4_BLOCKED": 0,
                "HTF_OK": 0,
                "SETUP_ROWS": 0,
                "RETRACE_OK": 0,
                "FAN_BREAKOUT": 0,
                "MACD_TRIGGER": 0,
                "STOCH_TRIGGER": 0,
                "RR_OK": 0,
                "ENTRY_READY": 0,
            })
            continue

        h4_ok = _coerce_bool_series(df.get("HTF_GATE_OK", False), index=df.index)
        setup_status = pd.Series(df.get("SETUP_STATUS", "NO_SETUP"), index=df.index).fillna("NO_SETUP").astype(str)
        h4_blocked = _coerce_bool_series(setup_status == "H4_BLOCKED", index=df.index)
        setup_rows = _coerce_bool_series(df.get("SETUP_CANDIDATE", False), index=df.index)
        retrace_ok = _coerce_bool_series(df.get("RETRACE_OK", False), index=df.index)
        fan_breakout = _coerce_bool_series(df.get("FAN_BREAKOUT", False), index=df.index)
        macd_trigger = _coerce_bool_series(df.get("MACD_TRIGGER", False), index=df.index)
        stoch_trigger = _coerce_bool_series(df.get("STOCH_TRIGGER", False), index=df.index)
        rr_ok = _coerce_bool_series(df.get("RR_OK", pd.to_numeric(df.get("RR_RATIO"), errors="coerce") >= float(min_rr)), index=df.index)
        entry_ready = _coerce_bool_series(df.get("ENTRY_READY", False), index=df.index)

        rows.append({
            "Activo": symbol,
            "Velas": int(len(df)),
            "H4_BLOCKED": int(h4_blocked.sum()),
            "HTF_OK": int(h4_ok.sum()),
            "SETUP_ROWS": int(setup_rows.sum()),
            "RETRACE_OK": int((setup_rows & retrace_ok).sum()),
            "FAN_BREAKOUT": int((setup_rows & fan_breakout).sum()),
            "MACD_TRIGGER": int((setup_rows & macd_trigger).sum()),
            "STOCH_TRIGGER": int((setup_rows & stoch_trigger).sum()),
            "RR_OK": int((setup_rows & rr_ok).sum()),
            "ENTRY_READY": int(entry_ready.sum()),
        })

    if not rows:
        return pd.DataFrame(columns=columns)

    summary = pd.DataFrame(rows, columns=columns).sort_values("Activo").reset_index(drop=True)
    total = {"Activo": "TOTAL"}
    for column_name in columns[1:]:
        total[column_name] = int(pd.to_numeric(summary[column_name], errors="coerce").fillna(0).sum())
    return pd.concat([summary, pd.DataFrame([total], columns=columns)], ignore_index=True)


def resumir_bloqueos_senales(portfolio):
    rows = []
    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            continue
        block_series = pd.Series(df.get("BLOCK_REASON", ""), index=df.index).fillna("").astype(str)
        block_series = block_series[block_series != ""]
        if block_series.empty:
            continue
        counts = block_series.value_counts().sort_index()
        for reason, count in counts.items():
            rows.append({
                "Activo": symbol,
                "BLOCK_REASON": str(reason),
                "Rows": int(count),
            })
    if not rows:
        return pd.DataFrame(columns=["Activo", "BLOCK_REASON", "Rows"])

    summary = pd.DataFrame(rows).sort_values(["Activo", "Rows", "BLOCK_REASON"], ascending=[True, False, True]).reset_index(drop=True)
    total = (
        summary.groupby("BLOCK_REASON", as_index=False)["Rows"]
        .sum()
        .assign(Activo="TOTAL")
    )
    return pd.concat([summary, total[["Activo", "BLOCK_REASON", "Rows"]]], ignore_index=True)


def resumir_estados_setup(portfolio):
    rows = []
    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            continue
        status_series = pd.Series(df.get("SETUP_STATUS", "NO_SETUP"), index=df.index).fillna("NO_SETUP").astype(str)
        counts = status_series.value_counts().sort_index()
        for status, count in counts.items():
            rows.append({
                "Activo": symbol,
                "SETUP_STATUS": str(status),
                "Rows": int(count),
            })
    if not rows:
        return pd.DataFrame(columns=["Activo", "SETUP_STATUS", "Rows"])

    summary = pd.DataFrame(rows).sort_values(["Activo", "Rows", "SETUP_STATUS"], ascending=[True, False, True]).reset_index(drop=True)
    total = (
        summary.groupby("SETUP_STATUS", as_index=False)["Rows"]
        .sum()
        .assign(Activo="TOTAL")
    )
    return pd.concat([summary, total[["Activo", "SETUP_STATUS", "Rows"]]], ignore_index=True)


def construir_signal_funnel(portfolio, min_rr=1.0):
    return {
        "stage_counts": resumir_embudo_senales(portfolio, min_rr=min_rr),
        "block_reasons": resumir_bloqueos_senales(portfolio),
        "status_distribution": resumir_estados_setup(portfolio),
    }


def colorear_comparativa(df_comp):
    def _color_row(row):
        styles = [""] * len(row)
        if "PF" in row.index:
            pf_idx = list(row.index).index("PF")
            if row["PF"] >= 1.5:
                styles[pf_idx] = "background-color: #2d5a27; color: white"
            elif row["PF"] >= 1.0:
                styles[pf_idx] = "background-color: #1a4a1a; color: #90ee90"
            else:
                styles[pf_idx] = "background-color: #5a2727; color: white"
        if "Return%" in row.index:
            ret_idx = list(row.index).index("Return%")
            if row["Return%"] > 0:
                styles[ret_idx] = "background-color: #1a4a1a; color: #90ee90"
            else:
                styles[ret_idx] = "background-color: #4a1a1a; color: #ee9090"
        return styles

    compact = [{"selector": "th, td", "props": [
        ("font-size", "11px"),
        ("padding", "3px 6px"),
        ("white-space", "nowrap"),
    ]}]
    formatters = {
        "WR%": "{:.1f}",
        "AvgWin%": "{:+.2f}",
        "AvgLoss%": "{:+.2f}",
        "R:R": "{:.2f}",
        "PF": "{:.2f}",
        "Return%": "{:+.2f}",
        "Sharpe": "{:.2f}",
        "Sortino": "{:.2f}",
        "MaxDD%": "{:.2f}",
        "Calmar": "{:.2f}",
    }
    formatters = {key: value for key, value in formatters.items() if key in df_comp.columns}
    return df_comp.style.apply(_color_row, axis=1).format(formatters).set_table_styles(compact)


def _entry_signal(row, strategy_config):
    min_rr = float(strategy_config.get("min_rr", 1.0))
    return (
        bool(row.get("ENTRY_READY", False)) and
        _safe_int(row.get("ENTRY_DIR"), 0) in {1, -1} and
        _is_finite_number(row.get("SL_PRICE")) and
        _is_finite_number(row.get("TP_PRICE")) and
        _is_finite_number(row.get("RR_RATIO")) and
        float(row.get("RR_RATIO")) >= min_rr
    )


def _make_position(symbol, timestamp, row, row_pos, strategy_name, strategy_config, timeframe_ltf, timeframe_htf):
    direction = _safe_int(row.get("ENTRY_DIR"), 0)
    spread_price = _safe_float(row.get("spread_price"), 0.0)
    entry_close = _safe_float(row.get("close"))
    entry_price = entry_close + spread_price if direction == 1 else entry_close
    stop_price = _safe_float(row.get("SL_PRICE"))
    target_price = _safe_float(row.get("TP_PRICE"))

    if not np.isfinite(entry_price) or not np.isfinite(stop_price) or not np.isfinite(target_price):
        return None
    if direction == 1 and stop_price >= entry_price:
        return None
    if direction == -1 and stop_price <= entry_price:
        return None

    position = {
        "strategy": strategy_name,
        "entry_rule": str(strategy_config.get("entry_rule", "menendez_core")),
        "symbol": symbol,
        "direction": direction,
        "setup_id": _safe_int(row.get("SETUP_ID"), 0),
        "entry_time": timestamp,
        "entry_price": float(entry_price),
        "stop_price": float(stop_price),
        "target_price": float(target_price),
        "target_extension": _safe_float(row.get("TARGET_EXTENSION")),
        "tp_mult": _safe_float(row.get("TARGET_EXTENSION"), 0.0),
        "target_source": str(row.get("TP_SOURCE", "") or ""),
        "size_fraction": float(strategy_config.get("risk_fraction", 1.0)),
        "spread_price": float(spread_price),
        "timeframe_ltf": timeframe_ltf,
        "timeframe_htf": timeframe_htf,
        "active_from_pos": row_pos + 1,
        "W_ID": _safe_float(row.get("W_ID")),
        "X_ID": _safe_float(row.get("X_ID")),
        "W_START": row.get("W_START"),
        "W_END": row.get("W_END"),
        "X_END": row.get("X_END"),
        "W_EP_TIME": row.get("W_EP_TIME"),
        "X_EP_TIME": row.get("X_EP_TIME"),
        "RETRACE_RATIO": _safe_float(row.get("RETRACE_RATIO")),
        "FAN_BREAKOUT": bool(row.get("FAN_BREAKOUT", False)),
        "BASE_CHANNEL_STATE": _safe_int(row.get("BASE_CHANNEL_STATE"), 0),
        "DECEL_CHANNEL_STATE": _safe_int(row.get("DECEL_CHANNEL_STATE"), 0),
        "MACD_TRIGGER": bool(row.get("MACD_TRIGGER", False)),
        "STOCH_TRIGGER": bool(row.get("STOCH_TRIGGER", False)),
        "PSAR_TRIGGER": bool(row.get("PSAR_TRIGGER", False)),
        "PRIMARY_TRIGGER": bool(row.get("PRIMARY_TRIGGER", False)),
        "MOMENTUM_CONFIRM": bool(row.get("MOMENTUM_CONFIRM", False)),
        "SESSION_OK": bool(row.get("SESSION_OK", False)),
        "RR_OK": bool(row.get("RR_OK", False)),
        "SETUP_STATUS": str(row.get("SETUP_STATUS", "") or ""),
        "BLOCK_REASON": str(row.get("BLOCK_REASON", "") or ""),
        "LAST_PASSED_STAGE": str(row.get("LAST_PASSED_STAGE", "") or ""),
        "H4_ATTRACTOR_DIR": _safe_int(row.get("H4_ATTRACTOR_DIR"), 0),
        "H4_ATTRACTOR_TREND_OK": bool(row.get("H4_ATTRACTOR_TREND_OK", False)),
        "H4_ATTRACTOR_MACD_OK": bool(row.get("H4_ATTRACTOR_MACD_OK", False)),
        "H4_MACD_NEUTRAL": bool(row.get("H4_MACD_NEUTRAL", False)),
        "H4_STANDBY": bool(row.get("H4_STANDBY", False)),
        "H4_PSAR_FLIP_EVENT": bool(row.get("H4_PSAR_FLIP_EVENT", False)),
        "H4_PSAR_LATERAL": bool(row.get("H4_PSAR_LATERAL", False)),
        "H4_PSAR_FLIP_COUNT_WINDOW": _safe_int(row.get("H4_PSAR_FLIP_COUNT_WINDOW"), 0),
        "H4_MACD_ZLR_BULL": bool(row.get("H4_MACD_ZLR_BULL", False)),
        "H4_MACD_ZLR_BEAR": bool(row.get("H4_MACD_ZLR_BEAR", False)),
        "H4_MACD_ZLR_RELEVANT": bool(row.get("H4_MACD_ZLR_RELEVANT", False)),
        "H4_ATTRACTOR_STAGE": str(row.get("H4_ATTRACTOR_STAGE", "") or ""),
        "H4_ATTRACTOR_BLOCK_REASON": str(row.get("H4_ATTRACTOR_BLOCK_REASON", "") or ""),
        "FRACTAL_SEGMENT_COUNT": _safe_int(row.get("FRACTAL_SEGMENT_COUNT"), 0),
        "FRACTAL_EQUIVALENT_CLASS": str(row.get("FRACTAL_EQUIVALENT_CLASS", "") or ""),
        "X_SEGMENT_COUNT": _safe_int(row.get("X_SEGMENT_COUNT"), 0),
        "X_POSSIBLE_COMPOSITE": bool(row.get("X_POSSIBLE_COMPOSITE", False)),
        "X_TOUCH_SMA21": bool(row.get("X_TOUCH_SMA21", False)),
        "X_TOUCH_SMA50": bool(row.get("X_TOUCH_SMA50", False)),
        "X_END_CLOSE_VS_SMA21": _safe_int(row.get("X_END_CLOSE_VS_SMA21"), 0),
        "X_END_CLOSE_VS_SMA50": _safe_int(row.get("X_END_CLOSE_VS_SMA50"), 0),
        "SL_PRICE": float(stop_price),
        "TP_PRICE": float(target_price),
        "TP_SOURCE": str(row.get("TP_SOURCE", "") or ""),
        "RR_RATIO": _safe_float(row.get("RR_RATIO")),
        "PLANNED_ENTRY_PRICE": _safe_float(row.get("PLANNED_ENTRY_PRICE")),
        "TARGET_0.854": _safe_float(row.get("TARGET_0.854")),
        "TARGET_1.0": _safe_float(row.get("TARGET_1.0")),
        "TARGET_1.236": _safe_float(row.get("TARGET_1.236")),
        "TARGET_1.618": _safe_float(row.get("TARGET_1.618")),
        "W_START_PRICE": _safe_float(row.get("W_START_PRICE")),
        "W_END_PRICE": _safe_float(row.get("W_END_PRICE")),
        "X_EXTREME_PRICE": _safe_float(row.get("X_EXTREME_PRICE")),
        "X_EP_DISTANCE_SMA21": _safe_float(row.get("X_EP_DISTANCE_SMA21")),
        "X_EP_DISTANCE_SMA50": _safe_float(row.get("X_EP_DISTANCE_SMA50")),
        "CORRECTION_LINE_PRICE": _safe_float(row.get("CORRECTION_LINE_PRICE")),
        "BASE_CHANNEL_LIMIT": _safe_float(row.get("BASE_CHANNEL_LIMIT")),
    }
    for column_name in SYMBOL_SPEC_COLUMNS:
        position[column_name] = row.get(column_name, np.nan)
    return position


def _close_position(position, timestamp, exit_price, exit_reason):
    closed = dict(position)
    closed["exit_time"] = pd.Timestamp(timestamp)
    closed["exit_price"] = float(exit_price)
    closed["exit_reason"] = str(exit_reason)
    return closed


def _exit_price_for_last_bar(position, row):
    spread_price = _safe_float(row.get("spread_price"), 0.0)
    close_price = _safe_float(row.get("close"))
    if position["direction"] == 1:
        return close_price
    return close_price + spread_price


def _check_exit(position, row, timestamp):
    if position["direction"] == 1:
        stop_hit = _safe_float(row.get("low")) <= position["stop_price"]
        target_hit = _safe_float(row.get("high")) >= position["target_price"]
        if stop_hit:
            return _close_position(position, timestamp, position["stop_price"], "SL")
        if target_hit:
            return _close_position(position, timestamp, position["target_price"], "TP")
        return None

    spread_price = _safe_float(row.get("spread_price"), 0.0)
    ask_high = _safe_float(row.get("high")) + spread_price
    ask_low = _safe_float(row.get("low")) + spread_price
    stop_hit = ask_high >= position["stop_price"]
    target_hit = ask_low <= position["target_price"]
    if stop_hit:
        return _close_position(position, timestamp, position["stop_price"], "SL")
    if target_hit:
        return _close_position(position, timestamp, position["target_price"], "TP")
    return None


def _simular_trades_symbol(
    symbol,
    df,
    strategy_name,
    strategy_settings,
    timeframe_ltf,
    timeframe_htf,
):
    raw_trades = []
    if df is None or df.empty:
        return raw_trades

    position = None
    consumed_setup_ids = set()
    for row_pos, (timestamp, row) in enumerate(df.iterrows()):
        if position is not None and row_pos >= int(position["active_from_pos"]):
            closed = _check_exit(position, row, timestamp)
            if closed is not None:
                raw_trades.append(closed)
                position = None

        setup_id = _safe_int(row.get("SETUP_ID"), 0)
        if (
            position is None and
            row_pos < (len(df) - 1) and
            setup_id not in consumed_setup_ids and
            _entry_signal(row, strategy_settings)
        ):
            position = _make_position(
                symbol=symbol,
                timestamp=timestamp,
                row=row,
                row_pos=row_pos,
                strategy_name=strategy_name,
                strategy_config=strategy_settings,
                timeframe_ltf=timeframe_ltf,
                timeframe_htf=timeframe_htf,
            )
            if position is not None and setup_id != 0:
                consumed_setup_ids.add(setup_id)

    if position is not None:
        last_timestamp = df.index[-1]
        last_row = df.iloc[-1]
        raw_trades.append(
            _close_position(position, last_timestamp, _exit_price_for_last_bar(position, last_row), "EOD")
        )
    return raw_trades


def simular_estrategia_portfolio(
    portfolio,
    strategy_name="menendez_core",
    strategy_config=None,
    timeframe_ltf=DEFAULT_TIMEFRAME_LTF,
    timeframe_htf=DEFAULT_TIMEFRAME_HTF,
    account_config=None,
    parallel=True,
    max_workers=None,
):
    strategy_settings = dict(DEFAULT_STRATEGIES.get(strategy_name, {}))
    if strategy_config:
        strategy_settings.update(strategy_config)

    portfolio_items = [(symbol, df) for symbol, df in (portfolio or {}).items() if df is not None and not df.empty]
    resolved_workers = _resolve_max_workers(len(portfolio_items), max_workers) if parallel else 1

    raw_trades = []
    if resolved_workers <= 1:
        for symbol, df in portfolio_items:
            raw_trades.extend(
                _simular_trades_symbol(
                    symbol=symbol,
                    df=df,
                    strategy_name=strategy_name,
                    strategy_settings=strategy_settings,
                    timeframe_ltf=timeframe_ltf,
                    timeframe_htf=timeframe_htf,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=resolved_workers, thread_name_prefix="menendez-bt") as executor:
            futures = [
                executor.submit(
                    _simular_trades_symbol,
                    symbol,
                    df,
                    strategy_name,
                    strategy_settings,
                    timeframe_ltf,
                    timeframe_htf,
                )
                for symbol, df in portfolio_items
            ]
            for future in as_completed(futures):
                raw_trades.extend(future.result())

    if not raw_trades:
        return pd.DataFrame(columns=[
            "strategy", "entry_rule", "symbol", "direction", "setup_id",
            "entry_time", "exit_time", "entry_price", "exit_price",
            "stop_price", "target_price", "tp_mult", "size_fraction",
        ])

    trades = pd.DataFrame(raw_trades).sort_values(
        ["entry_time", "exit_time", "symbol"],
        ascending=[True, True, True],
    ).reset_index(drop=True)
    sized = apply_risk_position_sizing(trades, account_config=get_account_config(account_config))
    return sized


def resumir_periodos(trades, splits=None):
    return summarize_periods(trades, splits or TEMPORAL_SPLITS)


def ejecutar_comparativa(
    portfolio_base,
    estrategias=None,
    timeframe_ltf=DEFAULT_TIMEFRAME_LTF,
    timeframe_htf=DEFAULT_TIMEFRAME_HTF,
    account_config=None,
    return_details=False,
    parallel=True,
    max_workers=None,
):
    strategy_defs = get_strategy_definitions(estrategias or DEFAULT_STRATEGIES)
    account_settings = get_account_config(account_config)
    summary_rows = []
    trade_book = {}
    split_rows = []

    for strategy_name, strategy_config in strategy_defs.items():
        print(f"\n{'=' * 50}")
        print(f"  {strategy_name}")
        print(f"{'=' * 50}")

        trades = simular_estrategia_portfolio(
            portfolio_base,
            strategy_name=strategy_name,
            strategy_config=strategy_config,
            timeframe_ltf=timeframe_ltf,
            timeframe_htf=timeframe_htf,
            account_config=account_settings,
            parallel=parallel,
            max_workers=max_workers,
        )
        trade_book[strategy_name] = trades

        metricas = extraer_metricas(trades)
        metricas["Variante"] = strategy_name
        metricas["LTF"] = timeframe_ltf
        metricas["HTF"] = timeframe_htf
        summary_rows.append(metricas)

        period_df = resumir_periodos(trades)
        if not period_df.empty:
            period_df["Variante"] = strategy_name
            period_df["LTF"] = timeframe_ltf
            period_df["HTF"] = timeframe_htf
            split_rows.append(period_df)

        print(
            f"  Trades: {metricas['Trades']} | WR: {metricas['WR%']}% | "
            f"PF: {metricas['PF']} | Ret: {metricas['Return%']:+.2f}%"
        )

    summary = pd.DataFrame(summary_rows)
    if summary.empty:
        summary = pd.DataFrame(columns=[
            "Variante", "LTF", "HTF", "Trades", "WR%", "AvgWin%", "AvgLoss%",
            "R:R", "PF", "Return%", "Sharpe", "Sortino", "MaxDD%", "Calmar",
        ])
    else:
        summary = summary[[
            "Variante", "LTF", "HTF", "Trades", "WR%", "AvgWin%", "AvgLoss%",
            "R:R", "PF", "Return%", "Sharpe", "Sortino", "MaxDD%", "Calmar",
        ]]

    if not return_details:
        return summary
    return {
        "summary": summary,
        "summary_metrics": summary.copy(),
        "splits": pd.concat(split_rows, ignore_index=True) if split_rows else pd.DataFrame(),
        "trades": trade_book,
        "trade_log": _trade_book_to_frame(trade_book),
    }


def cargar_y_ejecutar_menendez(
    symbols=None,
    estrategias=None,
    context_config=None,
    indicator_config=None,
    account_config=None,
    verbose=True,
    return_details=False,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
    parallel=True,
    max_workers=None,
):
    from backtests.menendez.menendez_loader import cargar_portfolio_menendez

    portfolio = cargar_portfolio_menendez(
        symbols=symbols,
        context_config=context_config,
        indicator_config=indicator_config,
        verbose=verbose,
        use_cache=use_cache,
        force_rebuild=force_rebuild,
        use_disk_cache=use_disk_cache,
        parallel=parallel,
        max_workers=max_workers,
    )
    return ejecutar_comparativa(
        portfolio,
        estrategias=estrategias,
        timeframe_ltf=DEFAULT_TIMEFRAME_LTF,
        timeframe_htf=DEFAULT_TIMEFRAME_HTF,
        account_config=account_config,
        return_details=return_details,
        parallel=parallel,
        max_workers=max_workers,
    )


def _merge_strategy_overrides(strategy_overrides=None):
    strategy_defs = get_strategy_definitions(DEFAULT_STRATEGIES)
    for strategy_name, overrides in (strategy_overrides or {}).items():
        if strategy_name not in strategy_defs:
            strategy_defs[strategy_name] = dict(overrides)
            continue
        strategy_defs[strategy_name].update(overrides or {})
    return strategy_defs


def construir_run_meta_menendez(
    portfolio,
    variant_name="ad_hoc",
    classification="resultado_valido",
    notes="",
    context_config=None,
    indicator_config=None,
    account_config=None,
    contract_overrides=None,
    use_cache=True,
    use_disk_cache=True,
    force_rebuild=False,
):
    contract = get_experiment_contract(contract_overrides)
    account_settings = get_account_config(account_config)
    return {
        "run_timestamp": pd.Timestamp.utcnow().isoformat(),
        "variant_name": variant_name,
        "classification": classification,
        "notes": notes,
        "group_name": contract.get("group_name", DEFAULT_GROUP),
        "timeframe_ltf": contract.get("timeframe_ltf", DEFAULT_TIMEFRAME_LTF),
        "timeframe_htf": contract.get("timeframe_htf", DEFAULT_TIMEFRAME_HTF),
        "symbols": sorted((portfolio or {}).keys()),
        "symbol_count": int(len(portfolio or {})),
        "use_cache": bool(use_cache),
        "use_disk_cache": bool(use_disk_cache),
        "force_rebuild": bool(force_rebuild),
        "context_config": dict(context_config or {}),
        "indicator_config": dict(indicator_config or {}),
        "account_config": account_settings,
        "contract": contract,
    }


def generar_indicator_snapshot_portfolio(portfolio, only_key_rows=True):
    snapshot_cols = [
        "symbol", "timestamp", "close", "spread_price",
        "PSAR", "PSAR_POLARITY", "PSAR_FLIP_LONG", "PSAR_FLIP_SHORT",
        "SMA_5", "SMA_8", "SMA_13", "SMA_21", "SMA_50", "SMA_200", "SMA_21_SLOPE",
        "SMA_5_8_CROSS_UP", "SMA_5_8_CROSS_DOWN",
        "SMA_8_13_CROSS_UP", "SMA_8_13_CROSS_DOWN",
        "SMA_13_21_CROSS_UP", "SMA_13_21_CROSS_DOWN",
        "SMA_50_200_CROSS_UP", "SMA_50_200_CROSS_DOWN",
        "BULLISH_FAN", "BEARISH_FAN",
        "MACD_LINE", "MACD_SIGNAL", "MACD_HIST",
        "STOCH_K", "STOCH_D", "STOCH_CROSS_UP", "STOCH_CROSS_DOWN",
        "BB_MID", "BB_UPPER", "BB_LOWER",
        "D_PIVOT", "D_R1", "D_R2", "D_S1", "D_S2",
        "W_PIVOT", "W_R1", "W_R2", "W_S1", "W_S2",
        "H4_SOURCE_TIME", "H4_ATTRACTOR_DIR", "H4_ATTRACTOR_STAGE",
        "H4_ATTRACTOR_BLOCK_REASON", "H4_ATTRACTOR_PSAR_OK", "H4_ATTRACTOR_FAN_OK",
        "H4_ATTRACTOR_SLOPE_OK", "H4_ATTRACTOR_TREND_OK", "H4_ATTRACTOR_MACD_OK",
        "H4_MACD_NEUTRAL", "H4_STANDBY", "H4_PSAR_FLIP_EVENT", "H4_PSAR_FLIP_COUNT_WINDOW",
        "H4_PSAR_LATERAL", "H4_MACD_ZLR_BULL", "H4_MACD_ZLR_BEAR",
        "H4_MACD_ZLR_RELEVANT", "H4_SMA_50", "H4_SMA_200",
        "H4_SMA_5_8_CROSS_UP", "H4_SMA_5_8_CROSS_DOWN",
        "H4_SMA_8_13_CROSS_UP", "H4_SMA_8_13_CROSS_DOWN",
        "H4_SMA_13_21_CROSS_UP", "H4_SMA_13_21_CROSS_DOWN",
        "H4_SMA_50_200_CROSS_UP", "H4_SMA_50_200_CROSS_DOWN",
        "SETUP_CANDIDATE", "SETUP_STATUS", "BLOCK_REASON", "LAST_PASSED_STAGE",
        "W_ID", "X_ID", "W_START", "W_END", "X_END", "W_EP_TIME", "X_EP_TIME", "RETRACE_RATIO", "RETRACE_OK",
        "FAN_BREAKOUT", "MACD_TRIGGER", "STOCH_TRIGGER", "PSAR_TRIGGER",
        "PRIMARY_TRIGGER", "MOMENTUM_CONFIRM", "SESSION_OK", "RR_OK", "ENTRY_READY",
        "X_SEGMENT_COUNT", "X_POSSIBLE_COMPOSITE",
        "X_TOUCH_SMA21", "X_TOUCH_SMA50", "X_END_CLOSE_VS_SMA21", "X_END_CLOSE_VS_SMA50",
        "PLANNED_ENTRY_PRICE", "SL_PRICE", "TP_PRICE", "TP_SOURCE", "RR_RATIO",
        "FRACTAL_SEGMENT_COUNT", "FRACTAL_EQUIVALENT_CLASS",
        "W_START_PRICE", "W_END_PRICE", "X_EXTREME_PRICE", "X_EP_DISTANCE_SMA21", "X_EP_DISTANCE_SMA50",
    ]
    frames = []
    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            continue
        frame = df.copy()
        if only_key_rows:
            key_mask = (
                _coerce_bool_series(frame.get("SETUP_CANDIDATE", False), index=frame.index) |
                _coerce_bool_series(frame.get("ENTRY_READY", False), index=frame.index)
            )
            frame = frame.loc[key_mask]
        if frame.empty:
            continue
        frame = frame.copy()
        frame["symbol"] = symbol
        frame["timestamp"] = frame.index
        present_cols = [col for col in snapshot_cols if col in frame.columns]
        frames.append(frame[present_cols])
    if not frames:
        return pd.DataFrame(columns=snapshot_cols)
    return pd.concat(frames, ignore_index=True)


def extraer_indicator_snapshot(
    portfolio,
    symbol,
    timestamp=None,
    setup_id=None,
    bars_before=10,
    bars_after=10,
):
    df = (portfolio or {}).get(symbol)
    if df is None or df.empty:
        return pd.DataFrame()

    anchor_pos = None
    if timestamp is not None:
        anchor_time = pd.Timestamp(timestamp)
        anchor_pos = df.index.get_indexer([anchor_time], method="nearest")[0]
    elif setup_id is not None and "SETUP_ID" in df.columns:
        setup_rows = df[pd.to_numeric(df["SETUP_ID"], errors="coerce") == float(setup_id)]
        if not setup_rows.empty:
            anchor_pos = int(df.index.get_loc(setup_rows.index[0]))
    if anchor_pos is None:
        entry_rows = df[_coerce_bool_series(df.get("ENTRY_READY", False), index=df.index)]
        anchor_pos = int(df.index.get_loc(entry_rows.index[0])) if not entry_rows.empty else max(len(df) - 1, 0)

    start_pos = max(0, anchor_pos - int(bars_before))
    end_pos = min(len(df), anchor_pos + int(bars_after) + 1)
    window = df.iloc[start_pos:end_pos].copy()
    window["symbol"] = symbol
    window["timestamp"] = window.index
    present_cols = [col for col in generar_indicator_snapshot_portfolio({symbol: df}).columns if col in window.columns]
    result = window[present_cols].reset_index(drop=True)
    result.attrs["symbol"] = symbol
    result.attrs["anchor_time"] = pd.Timestamp(df.index[anchor_pos])
    return result


def construir_screener_rows(portfolio, only_active=False, current_only=False):
    rows = []
    for symbol, df in (portfolio or {}).items():
        if df is None or df.empty:
            continue
        frame = df.copy()
        latest_timestamp = pd.Timestamp(df.index[-1])
        if current_only:
            frame = frame.iloc[[-1]]
        elif only_active:
            active_mask = (
                _coerce_bool_series(frame.get("SETUP_CANDIDATE", False), index=frame.index) |
                _coerce_bool_series(frame.get("ENTRY_READY", False), index=frame.index) |
                _coerce_bool_series(frame.get("HTF_GATE_OK", False), index=frame.index)
            )
            frame = frame.loc[active_mask]
        row = frame.iloc[-1] if not frame.empty else df.iloc[-1]
        row_timestamp = pd.Timestamp(frame.index[-1] if not frame.empty else df.index[-1])
        direction = _safe_int(row.get("ENTRY_DIR"), 0)
        if direction == 0:
            direction = _safe_int(row.get("SETUP_DIR"), 0)
        rows.append({
            "symbol": symbol,
            "timestamp": row_timestamp,
            "latest_timestamp": latest_timestamp,
            "is_current": bool(row_timestamp == latest_timestamp),
            "setup_state": str(row.get("SETUP_STATUS", "") or ""),
            "last_passed_stage": str(row.get("LAST_PASSED_STAGE", "") or ""),
            "entry_ready": bool(row.get("ENTRY_READY", False)),
            "reason_block": str(row.get("BLOCK_REASON", "") or ""),
            "dir": int(direction),
            "entry": _safe_float(row.get("PLANNED_ENTRY_PRICE")),
            "sl": _safe_float(row.get("SL_PRICE")),
            "tp": _safe_float(row.get("TP_PRICE")),
            "rr": _safe_float(row.get("RR_RATIO")),
            "h4_attractor_dir": _safe_int(row.get("H4_ATTRACTOR_DIR"), 0),
            "h4_stage": str(row.get("H4_ATTRACTOR_STAGE", "") or ""),
            "h4_trend_ok": bool(row.get("H4_ATTRACTOR_TREND_OK", False)),
            "h4_macd_neutral": bool(row.get("H4_MACD_NEUTRAL", False)),
            "h4_psar_lateral": bool(row.get("H4_PSAR_LATERAL", False)),
            "h4_psar_flip_count_window": _safe_int(row.get("H4_PSAR_FLIP_COUNT_WINDOW"), 0),
            "h4_macd_zlr_relevant": bool(row.get("H4_MACD_ZLR_RELEVANT", False)),
            "fan_breakout": bool(row.get("FAN_BREAKOUT", False)),
            "psar_trigger": bool(row.get("PSAR_TRIGGER", False)),
            "primary_trigger": bool(row.get("PRIMARY_TRIGGER", False)),
            "macd_trigger": bool(row.get("MACD_TRIGGER", False)),
            "stoch_trigger": bool(row.get("STOCH_TRIGGER", False)),
            "momentum_confirm": bool(row.get("MOMENTUM_CONFIRM", False)),
            "session_ok": bool(row.get("SESSION_OK", False)),
            "retrace_ratio": _safe_float(row.get("RETRACE_RATIO")),
            "x_segment_count": _safe_int(row.get("X_SEGMENT_COUNT"), 0),
            "x_possible_composite": bool(row.get("X_POSSIBLE_COMPOSITE", False)),
            "fractal_eq_class": str(row.get("FRACTAL_EQUIVALENT_CLASS", "") or ""),
        })
    return pd.DataFrame(rows).sort_values(["entry_ready", "symbol"], ascending=[False, True]).reset_index(drop=True) if rows else pd.DataFrame()


def construir_order_intents(portfolio, account_config=None, screener_rows=None):
    account_settings = get_account_config(account_config)
    rows = screener_rows if screener_rows is not None else construir_screener_rows(portfolio, current_only=True)
    if rows is None or rows.empty:
        return pd.DataFrame(columns=[
            "symbol", "timestamp", "side", "order_type", "entry", "sl", "tp",
            "risk_pct", "volume", "source_run_id",
        ])

    intents = rows[(rows["entry_ready"] == True) & (rows.get("is_current", True) == True)].copy()
    if intents.empty:
        return pd.DataFrame(columns=[
            "symbol", "timestamp", "side", "order_type", "entry", "sl", "tp",
            "risk_pct", "volume", "source_run_id",
        ])
    intents["side"] = np.where(intents["dir"] == 1, "BUY", "SELL")
    intents["order_type"] = "MARKET"
    intents["risk_pct"] = float(account_settings.get("risk_per_trade", 0.01)) * 100.0
    volumes = []
    for _, row in intents.iterrows():
        symbol = row["symbol"]
        symbol_df = (portfolio or {}).get(symbol)
        if symbol_df is None or symbol_df.empty:
            volumes.append(np.nan)
            continue
        symbol_row = symbol_df.iloc[-1]
        symbol_spec = extract_symbol_spec_from_row(symbol_row)
        sizing = calculate_lot_size_for_risk(
            balance=float(account_settings.get("initial_capital", 10000.0)),
            risk_per_trade=float(account_settings.get("risk_per_trade", 0.01)),
            leg_fraction=1.0,
            entry_price=_safe_float(row.get("entry")),
            stop_price=_safe_float(row.get("sl")),
            symbol_spec=symbol_spec,
            skip_if_below_min_volume=bool(account_settings.get("skip_if_below_min_volume", True)),
        )
        volumes.append(_safe_float(sizing.get("lots")))
    intents["volume"] = volumes
    intents["source_run_id"] = ""
    return intents[[
        "symbol", "timestamp", "side", "order_type", "entry", "sl", "tp",
        "risk_pct", "volume", "source_run_id",
    ]].reset_index(drop=True)


def construir_bundle_experimental_menendez(
    portfolio,
    resultado,
    variant_name="ad_hoc",
    classification="resultado_valido",
    notes="",
    context_config=None,
    indicator_config=None,
    account_config=None,
    contract_overrides=None,
    use_cache=True,
    use_disk_cache=True,
    force_rebuild=False,
):
    summary = resultado.get("summary", pd.DataFrame()) if isinstance(resultado, dict) else pd.DataFrame()
    trade_log = extraer_trades_resultado(resultado)
    risk_audit = generar_auditoria_riesgo(resultado)
    bundle = {
        "run_meta": construir_run_meta_menendez(
            portfolio=portfolio,
            variant_name=variant_name,
            classification=classification,
            notes=notes,
            context_config=context_config,
            indicator_config=indicator_config,
            account_config=account_config,
            contract_overrides=contract_overrides,
            use_cache=use_cache,
            use_disk_cache=use_disk_cache,
            force_rebuild=force_rebuild,
        ),
        "context_df": portfolio,
        "signal_funnel": construir_signal_funnel(portfolio),
        "summary_metrics": summary.copy(),
        "trade_log": trade_log,
        "risk_audit": risk_audit,
        "indicator_snapshot": generar_indicator_snapshot_portfolio(portfolio, only_key_rows=True),
        "screener_rows": construir_screener_rows(portfolio, only_active=True),
        "screener_rows_current": construir_screener_rows(portfolio, current_only=True),
        "order_intents": construir_order_intents(portfolio, account_config=account_config),
        "raw_result": resultado,
    }
    return bundle


def ejecutar_suite_experimental_menendez(
    symbols=None,
    variant_names=None,
    context_config=None,
    indicator_config=None,
    account_config=None,
    verbose=True,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
    parallel=True,
    max_workers=None,
    contract_overrides=None,
):
    from backtests.menendez.menendez_loader import cargar_portfolio_menendez

    variant_specs = get_variant_specs(variant_names)
    variants = {}
    summary_rows = []
    contract = get_experiment_contract(contract_overrides)

    for variant_name, spec in variant_specs.items():
        merged_context = dict(context_config or {})
        merged_context.update(spec.get("context_overrides", {}))
        strategy_defs = _merge_strategy_overrides(spec.get("strategy_overrides"))
        portfolio = cargar_portfolio_menendez(
            symbols=symbols,
            group_name=contract.get("group_name", DEFAULT_GROUP),
            timeframe_ltf=contract.get("timeframe_ltf", DEFAULT_TIMEFRAME_LTF),
            timeframe_htf=contract.get("timeframe_htf", DEFAULT_TIMEFRAME_HTF),
            context_config=merged_context,
            indicator_config=indicator_config,
            verbose=verbose,
            use_cache=use_cache,
            force_rebuild=force_rebuild,
            use_disk_cache=use_disk_cache,
            parallel=parallel,
            max_workers=max_workers,
        )
        result = ejecutar_comparativa(
            portfolio,
            estrategias=strategy_defs,
            timeframe_ltf=contract.get("timeframe_ltf", DEFAULT_TIMEFRAME_LTF),
            timeframe_htf=contract.get("timeframe_htf", DEFAULT_TIMEFRAME_HTF),
            account_config=account_config,
            return_details=True,
            parallel=parallel,
            max_workers=max_workers,
        )
        bundle = construir_bundle_experimental_menendez(
            portfolio=portfolio,
            resultado=result,
            variant_name=variant_name,
            classification=spec.get("classification", "resultado_valido"),
            notes=spec.get("notes", ""),
            context_config=merged_context,
            indicator_config=indicator_config,
            account_config=account_config,
            contract_overrides=contract,
            use_cache=use_cache,
            use_disk_cache=use_disk_cache,
            force_rebuild=force_rebuild,
        )
        variants[variant_name] = bundle
        variant_summary = bundle["summary_metrics"].copy()
        if not variant_summary.empty:
            variant_summary["Variant"] = variant_name
            variant_summary["VariantClass"] = spec.get("classification", "resultado_valido")
            summary_rows.append(variant_summary)

    return {
        "variants": variants,
        "summary_table": pd.concat(summary_rows, ignore_index=True) if summary_rows else pd.DataFrame(),
    }


def extraer_operaciones_resultado(
    resultado,
    strategy=None,
    symbol=None,
    direction=None,
    exit_reason=None,
):
    trades = extraer_trades_resultado(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction,
        exit_reason=exit_reason,
    )
    columns = [
        "strategy", "symbol", "entry_rule", "direction", "setup_id",
        "entry_time", "exit_time", "entry_price", "exit_price",
        "stop_price", "target_price", "target_source", "tp_mult",
        "W_ID", "X_ID", "W_START", "W_END", "X_END", "W_EP_TIME", "X_EP_TIME",
        "RETRACE_RATIO", "FAN_BREAKOUT", "BASE_CHANNEL_STATE", "DECEL_CHANNEL_STATE",
        "MACD_TRIGGER", "STOCH_TRIGGER", "PSAR_TRIGGER", "PRIMARY_TRIGGER", "MOMENTUM_CONFIRM",
        "SESSION_OK", "X_SEGMENT_COUNT", "X_POSSIBLE_COMPOSITE",
        "X_TOUCH_SMA21", "X_TOUCH_SMA50", "X_END_CLOSE_VS_SMA21", "X_END_CLOSE_VS_SMA50",
        "RR_OK", "SETUP_STATUS", "BLOCK_REASON",
        "LAST_PASSED_STAGE", "H4_ATTRACTOR_DIR", "H4_ATTRACTOR_STAGE",
        "H4_ATTRACTOR_BLOCK_REASON", "H4_ATTRACTOR_TREND_OK", "H4_ATTRACTOR_MACD_OK",
        "H4_MACD_NEUTRAL", "H4_STANDBY", "H4_PSAR_FLIP_EVENT", "H4_PSAR_FLIP_COUNT_WINDOW",
        "H4_PSAR_LATERAL", "H4_MACD_ZLR_BULL", "H4_MACD_ZLR_BEAR",
        "H4_MACD_ZLR_RELEVANT",
        "FRACTAL_SEGMENT_COUNT", "FRACTAL_EQUIVALENT_CLASS",
        "SL_PRICE", "TP_PRICE", "TP_SOURCE", "RR_RATIO", "PLANNED_ENTRY_PRICE",
        "TARGET_0.854", "TARGET_1.0", "TARGET_1.236", "TARGET_1.618",
        "W_START_PRICE", "W_END_PRICE", "X_EXTREME_PRICE", "X_EP_DISTANCE_SMA21", "X_EP_DISTANCE_SMA50",
        "CORRECTION_LINE_PRICE", "BASE_CHANNEL_LIMIT",
        "lots", "risk_amount", "pnl_money", "exit_reason",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    present_cols = [col for col in columns if col in trades.columns]
    return trades[present_cols].reset_index(drop=True)


def generar_auditoria_riesgo(
    resultado,
    strategy=None,
    symbol=None,
    direction=None,
    exit_reason=None,
    max_rows=None,
):
    trades = extraer_trades_resultado(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction,
        exit_reason=exit_reason,
    )
    if trades.empty:
        return pd.DataFrame()

    audit = trades.copy()
    audit["direction_label"] = np.where(audit["direction"] == 1, "LONG", "SHORT")
    balance = pd.to_numeric(audit.get("balance_before_entry"), errors="coerce")
    risk_amount = pd.to_numeric(audit.get("risk_amount"), errors="coerce")
    audit["risk_pct_real"] = np.where(balance > 0, (risk_amount / balance) * 100.0, np.nan)

    stop_distance = pd.to_numeric(audit.get("stop_distance"), errors="coerce")
    tick_size = pd.to_numeric(audit.get("SYMBOL_TRADE_TICK_SIZE"), errors="coerce")
    audit["stop_ticks"] = np.where(tick_size > 0, stop_distance / tick_size, np.nan)
    lots = pd.to_numeric(audit.get("lots"), errors="coerce")
    loss_per_lot = pd.to_numeric(audit.get("loss_per_lot"), errors="coerce")
    audit["expected_loss_at_sl"] = loss_per_lot * lots
    audit["risk_gap"] = audit["expected_loss_at_sl"] - risk_amount

    pnl_money_gross = pd.to_numeric(audit.get("pnl_money_gross"), errors="coerce")
    pnl_money_net = pd.to_numeric(audit.get("pnl_money"), errors="coerce")
    commission_total = pd.to_numeric(audit.get("commission_total"), errors="coerce").fillna(0.0)
    ticks_moved = pd.to_numeric(audit.get("ticks_moved"), errors="coerce")
    tick_value_used = pd.to_numeric(audit.get("tick_value_used"), errors="coerce")
    audit["pnl_formula_money"] = ticks_moved * tick_value_used * lots
    audit["pnl_formula_diff"] = pnl_money_gross - audit["pnl_formula_money"]
    audit["pnl_net_diff"] = pnl_money_net - (audit["pnl_formula_money"] - commission_total)

    columns = [
        "strategy", "symbol", "direction_label", "entry_rule", "setup_id", "exit_reason",
        "entry_time", "exit_time", "entry_price", "stop_price", "exit_price",
        "W_ID", "X_ID", "W_START", "W_END", "X_END", "RETRACE_RATIO",
        "FAN_BREAKOUT", "BASE_CHANNEL_STATE", "DECEL_CHANNEL_STATE",
        "MACD_TRIGGER", "STOCH_TRIGGER", "PSAR_TRIGGER", "PRIMARY_TRIGGER", "MOMENTUM_CONFIRM",
        "SESSION_OK", "X_SEGMENT_COUNT", "X_POSSIBLE_COMPOSITE",
        "RR_OK", "SETUP_STATUS", "BLOCK_REASON",
        "LAST_PASSED_STAGE", "H4_ATTRACTOR_DIR", "H4_ATTRACTOR_STAGE",
        "H4_ATTRACTOR_BLOCK_REASON", "H4_ATTRACTOR_TREND_OK", "H4_ATTRACTOR_MACD_OK",
        "H4_MACD_NEUTRAL", "H4_STANDBY", "H4_PSAR_FLIP_EVENT", "H4_PSAR_FLIP_COUNT_WINDOW",
        "H4_PSAR_LATERAL", "H4_MACD_ZLR_BULL", "H4_MACD_ZLR_BEAR",
        "H4_MACD_ZLR_RELEVANT",
        "FRACTAL_SEGMENT_COUNT", "FRACTAL_EQUIVALENT_CLASS",
        "SL_PRICE", "TP_PRICE", "TP_SOURCE", "RR_RATIO", "PLANNED_ENTRY_PRICE",
        "size_fraction", "balance_before_entry", "risk_amount", "risk_pct_real",
        "stop_distance", "stop_ticks", "loss_per_lot", "lots_raw", "lots",
        "expected_loss_at_sl", "risk_gap", "ticks_moved", "tick_value_used",
        "commission_per_side_per_lot", "commission_entry", "commission_exit", "commission_total",
        "pnl_money_gross", "pnl_money", "pnl_formula_money", "pnl_formula_diff", "pnl_net_diff",
    ]
    present_cols = [col for col in columns if col in audit.columns]
    audit = audit[present_cols].reset_index(drop=True)
    if max_rows is not None:
        audit = audit.head(int(max_rows))
    return audit


def extraer_ventana_trade(
    portfolio,
    resultado,
    trade_index=0,
    strategy=None,
    symbol=None,
    direction=None,
    bars_before=25,
    bars_after=25,
):
    trades = extraer_trades_resultado(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction,
    )
    if trades.empty:
        return pd.DataFrame()

    trade_row = trades.iloc[int(trade_index)]
    symbol_name = trade_row["symbol"]
    df = portfolio.get(symbol_name)
    if df is None or df.empty:
        return pd.DataFrame()

    entry_time = pd.Timestamp(trade_row["entry_time"])
    exit_time = pd.Timestamp(trade_row["exit_time"])
    entry_pos = df.index.get_indexer([entry_time], method="nearest")[0]
    exit_pos = df.index.get_indexer([exit_time], method="nearest")[0]
    start_pos = max(0, entry_pos - int(bars_before))
    end_pos = min(len(df), exit_pos + int(bars_after) + 1)

    candidate_columns = [
        "open", "high", "low", "close", "spread", "spread_price",
        "PSAR", "PSAR_POLARITY", "PSAR_FLIP_LONG", "PSAR_FLIP_SHORT",
        "SMA_5", "SMA_8", "SMA_13", "SMA_21", "SMA_50", "SMA_200", "SMA_21_SLOPE",
        "SMA_5_8_CROSS_UP", "SMA_5_8_CROSS_DOWN",
        "SMA_8_13_CROSS_UP", "SMA_8_13_CROSS_DOWN",
        "SMA_13_21_CROSS_UP", "SMA_13_21_CROSS_DOWN",
        "SMA_50_200_CROSS_UP", "SMA_50_200_CROSS_DOWN",
        "BULLISH_FAN", "BEARISH_FAN",
        "MACD_LINE", "MACD_SIGNAL", "MACD_HIST",
        "STOCH_K", "STOCH_D", "STOCH_CROSS_UP", "STOCH_CROSS_DOWN",
        "BB_MID", "BB_UPPER", "BB_LOWER",
        "D_PIVOT", "D_R1", "D_R2", "D_S1", "D_S2",
        "W_PIVOT", "W_R1", "W_R2", "W_S1", "W_S2",
        "H4_SOURCE_TIME", "H4_ATTRACTOR_DIR", "H4_ATTRACTOR_STAGE",
        "H4_ATTRACTOR_BLOCK_REASON", "H4_ATTRACTOR_PSAR_OK", "H4_ATTRACTOR_FAN_OK",
        "H4_ATTRACTOR_SLOPE_OK", "H4_ATTRACTOR_TREND_OK", "H4_ATTRACTOR_MACD_OK",
        "H4_MACD_NEUTRAL", "H4_STANDBY", "H4_PSAR_FLIP_EVENT", "H4_PSAR_FLIP_COUNT_WINDOW",
        "H4_PSAR_LATERAL", "H4_MACD_ZLR_BULL", "H4_MACD_ZLR_BEAR", "H4_MACD_ZLR_RELEVANT",
        "H4_SMA_50", "H4_SMA_200",
        "H4_SMA_5_8_CROSS_UP", "H4_SMA_5_8_CROSS_DOWN",
        "H4_SMA_8_13_CROSS_UP", "H4_SMA_8_13_CROSS_DOWN",
        "H4_SMA_13_21_CROSS_UP", "H4_SMA_13_21_CROSS_DOWN",
        "H4_SMA_50_200_CROSS_UP", "H4_SMA_50_200_CROSS_DOWN",
        "M30_PSAR_POLARITY", "W_ID", "X_ID", "W_START", "W_END", "X_END", "W_EP_TIME", "X_EP_TIME",
        "RETRACE_RATIO", "RETRACE_OK", "FAN_BREAKOUT",
        "BASE_CHANNEL_STATE", "DECEL_CHANNEL_STATE",
        "MACD_TRIGGER", "STOCH_TRIGGER", "PSAR_TRIGGER", "PRIMARY_TRIGGER", "MOMENTUM_CONFIRM", "SESSION_OK", "RR_OK", "ENTRY_READY",
        "X_SEGMENT_COUNT", "X_POSSIBLE_COMPOSITE",
        "X_TOUCH_SMA21", "X_TOUCH_SMA50", "X_END_CLOSE_VS_SMA21", "X_END_CLOSE_VS_SMA50",
        "SETUP_STATUS", "BLOCK_REASON", "LAST_PASSED_STAGE",
        "FRACTAL_SEGMENT_COUNT", "FRACTAL_EQUIVALENT_CLASS",
        "PLANNED_ENTRY_PRICE", "SL_PRICE", "TP_PRICE", "TP_SOURCE", "RR_RATIO",
        "TARGET_0.854", "TARGET_1.0", "TARGET_1.236", "TARGET_1.618",
        "W_START_PRICE", "W_END_PRICE", "X_EXTREME_PRICE", "X_EP_DISTANCE_SMA21", "X_EP_DISTANCE_SMA50",
        "CORRECTION_LINE_PRICE", "BASE_CHANNEL_LIMIT",
    ]
    columns = [col for col in candidate_columns if col in df.columns]
    window = df.iloc[start_pos:end_pos][columns].copy()
    window["TRADE_ENTRY"] = window.index == entry_time
    window["TRADE_EXIT"] = window.index == exit_time
    window["TRADE_ENTRY_PRICE"] = np.where(window["TRADE_ENTRY"], float(trade_row["entry_price"]), np.nan)
    window["TRADE_STOP_PRICE"] = float(trade_row["stop_price"])
    window["TRADE_TARGET_PRICE"] = float(trade_row["target_price"])
    window["TRADE_EXIT_PRICE"] = np.where(window["TRADE_EXIT"], float(trade_row["exit_price"]), np.nan)
    window.attrs["trade"] = trade_row.to_dict()
    return window
