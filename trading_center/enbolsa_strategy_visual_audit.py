from __future__ import annotations

import argparse
import json
import math
import pickle
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "enbolsa_strategy_visual_audit_v1"
DEFAULT_TRADE_LOG_CSV = REPO_ROOT / "artifacts/benchmark-significance/enbolsa/final/tables/trade_log.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_strategy_visual_audit_v1_2026-06-02"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/ENBOLSA_STRATEGY_VISUAL_AUDIT_V1.md"
DEFAULT_CACHE_DIR = REPO_ROOT / "backtests/.cache/portfolios"

CACHE_BY_PARTIAL_SOURCE = {
    "partial-forex-majors-m30-h1": "5dcc75136d7da38010d708ad0e2750e038d45c0d8ad1bcc7d62368d566999824.pkl",
    "partial-forex-majors-h1-h4": "87ceb321e6baa64270d850679e7ac2955f939b28b4bc38a125c838758575c73a.pkl",
    "partial-forex-majors-h4-d1": "9ef8da92423fc3fd6930292e8596529683e86426bc5594f67dd17bcb27c776ee.pkl",
    "partial-metals-m30-h1": "aa45a97bf0a5406cd2a2f6a6fce51ca5f0a2a8b63fca32b4651eaa0a4846b4e4.pkl",
    "partial-metals-h1-h4": "8be03b231d444c45df8367811de8009892676c493d89b1266e1bb08d335d8e71.pkl",
    "partial-metals-h4-d1": "d0b6d48900b528596e35b2f686dd7ff387f0fa0b363f33767bbd2c1a894f178b.pkl",
    "partial-index-m30-h1": "b40577fcc691fb7ad075e0c1ca3d479ba74b507744864f010e9675d5260fadc7.pkl",
    "partial-index-h1-h4": "270d6bae15dc8fb9b3e32e143212e171451de0235e127a3f05b7ec086f079292.pkl",
    "partial-index-h4-d1": "a122b7361740c8476ef720584db373cfcdaba224806d094f6b89465a7d4c96b3.pkl",
}

CASE_FIELDNAMES = [
    "case_id",
    "strategy",
    "entry_rule",
    "materiality_bucket",
    "symbol",
    "group",
    "direction",
    "setup_id",
    "entry_time",
    "timeframe_ltf",
    "timeframe_htf",
    "partial_source",
    "w1_size_pct",
    "w1_to_bm_atr",
    "entry_price",
    "stop_price",
    "fib_0_618",
    "cache_file",
    "chart_file",
    "visual_status",
    "w1_start_point_found",
    "w1_end_point_found",
    "w2_point_found",
    "macd_available",
    "rsi_available",
    "methodology_note",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def as_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def format_float(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def unique_setup_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        clean(row.get("symbol")),
        clean(row.get("strategy")),
        clean(row.get("entry_rule")),
        clean(row.get("direction")),
        clean(row.get("setup_id")),
        clean(row.get("entry_time")),
        clean(row.get("timeframe_ltf")),
        clean(row.get("timeframe_htf")),
        clean(row.get("partial_source")),
    )


def classify_materiality(row: dict[str, Any]) -> tuple[str, float | None, float | None]:
    w1_size = as_float(row.get("W1_SIZE"))
    w1_start = as_float(row.get("W1_START_PRICE"))
    bm_atr = as_float(row.get("BM_ATR_USED"))
    w1_pct = abs(w1_size) / abs(w1_start) * 100.0 if w1_size is not None and w1_start not in {None, 0.0} else None
    w1_to_atr = abs(w1_size) / bm_atr if w1_size is not None and bm_atr and bm_atr > 0 else None
    if w1_to_atr is not None:
        if w1_to_atr < 1.5:
            return "very_small", w1_pct, w1_to_atr
        if w1_to_atr < 2.5:
            return "small", w1_pct, w1_to_atr
        if w1_to_atr < 5.0:
            return "normal", w1_pct, w1_to_atr
        return "large", w1_pct, w1_to_atr
    if w1_pct is not None:
        if w1_pct < 0.25:
            return "very_small", w1_pct, w1_to_atr
        if w1_pct < 0.60:
            return "small", w1_pct, w1_to_atr
        if w1_pct < 1.50:
            return "normal", w1_pct, w1_to_atr
        return "large", w1_pct, w1_to_atr
    return "not_available", w1_pct, w1_to_atr


def load_trade_rows(path: Path) -> list[dict[str, Any]]:
    rows = read_csv(path)
    seen: set[tuple[str, ...]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        entry_rule = clean(row.get("entry_rule")).lower()
        if entry_rule not in {"fib_limit", "macd_breakout"}:
            continue
        key = unique_setup_key(row)
        if key in seen:
            continue
        seen.add(key)
        bucket, w1_pct, w1_to_atr = classify_materiality(row)
        row = dict(row)
        row["_materiality_bucket"] = bucket
        row["_w1_size_pct"] = w1_pct
        row["_w1_to_bm_atr"] = w1_to_atr
        output.append(row)
    return output


def select_cases(rows: list[dict[str, Any]], max_small_per_rule: int, max_normal_per_rule: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for entry_rule in ["fib_limit", "macd_breakout"]:
        eligible = [row for row in rows if clean(row.get("entry_rule")).lower() == entry_rule and clean(row.get("partial_source")) in CACHE_BY_PARTIAL_SOURCE]
        small = [row for row in eligible if clean(row.get("_materiality_bucket")) in {"small", "very_small"}]
        normal = [row for row in eligible if clean(row.get("_materiality_bucket")) in {"normal", "large"}]
        small.sort(key=lambda row: (as_float(row.get("_w1_to_bm_atr")) is None, as_float(row.get("_w1_to_bm_atr")) or 999.0, clean(row.get("entry_time"))))
        normal.sort(key=lambda row: (clean(row.get("symbol")), clean(row.get("entry_time"))))
        selected.extend(small[:max_small_per_rule])
        selected.extend(normal[:max_normal_per_rule])
    return selected


def load_portfolio_cache(cache_dir: Path, partial_source: str) -> dict[str, pd.DataFrame] | None:
    cache_name = CACHE_BY_PARTIAL_SOURCE.get(partial_source)
    if not cache_name:
        return None
    cache_path = cache_dir / cache_name
    if not cache_path.exists():
        return None
    with cache_path.open("rb") as handle:
        return pickle.load(handle)


def get_window(df: pd.DataFrame, entry_time: pd.Timestamp, before: int, after: int) -> tuple[pd.DataFrame, int | None]:
    index = pd.DatetimeIndex(df.index)
    positions = index.get_indexer([entry_time], method="nearest")
    pos = int(positions[0]) if len(positions) else -1
    if pos < 0:
        return df.iloc[0:0].copy(), None
    start = max(0, pos - before)
    end = min(len(df), pos + after + 1)
    return df.iloc[start:end].copy(), pos - start


def price_tolerance(price: float | None, row: dict[str, Any]) -> float:
    if price is None:
        return 0.0
    point_size = as_float(row.get("SYMBOL_POINT_SIZE")) or as_float(row.get("SYMBOL_TRADE_TICK_SIZE")) or 0.0
    return max(abs(price) * 0.0008, point_size * 20.0, 1e-9)


def find_price_point(window: pd.DataFrame, price: float | None, row: dict[str, Any], before_entry_pos: int | None) -> tuple[int | None, float | None]:
    if price is None or window.empty:
        return None, None
    end = before_entry_pos + 1 if before_entry_pos is not None else len(window)
    search = window.iloc[: max(1, end)]
    tolerance = price_tolerance(price, row)
    candidates: list[tuple[float, int, float]] = []
    if "PIVOT_VALUE" in search.columns:
        pivots = search[search.get("PIVOT_VALUE").notna()]
        for idx, value in enumerate(pivots["PIVOT_VALUE"].tolist()):
            value_float = as_float(value)
            if value_float is None:
                continue
            diff = abs(value_float - price)
            if diff <= tolerance:
                candidates.append((diff, int(search.index.get_loc(pivots.index[idx])), value_float))
    for idx, (_, candle) in enumerate(search.iterrows()):
        for col in ["high", "low", "close", "open"]:
            value_float = as_float(candle.get(col))
            if value_float is None:
                continue
            diff = abs(value_float - price)
            if diff <= tolerance:
                candidates.append((diff + 0.000001, idx, value_float))
    if not candidates:
        return None, None
    _, pos, value = sorted(candidates, key=lambda item: (item[0], -item[1]))[0]
    return pos, value


def draw_candles(ax: plt.Axes, window: pd.DataFrame) -> None:
    width = 0.58
    for i, (_, row) in enumerate(window.iterrows()):
        open_price = as_float(row.get("open"))
        high = as_float(row.get("high"))
        low = as_float(row.get("low"))
        close = as_float(row.get("close"))
        if None in {open_price, high, low, close}:
            continue
        color = "#51e888" if close >= open_price else "#ff6464"
        ax.vlines(i, low, high, color=color, linewidth=1.2, alpha=0.95)
        body_low = min(open_price, close)
        body_height = max(abs(close - open_price), max(abs(close) * 0.00008, 1e-8))
        ax.add_patch(Rectangle((i - width / 2, body_low), width, body_height, edgecolor=color, facecolor=color, alpha=0.42, linewidth=1.1))


def annotate_level(ax: plt.Axes, x: int, y: float, label: str, color: str) -> None:
    ax.text(
        x,
        y,
        label,
        color="#f2fff8",
        fontsize=7.5,
        va="center",
        ha="left",
        bbox={"boxstyle": "square,pad=0.18", "facecolor": "#071312", "edgecolor": color, "linewidth": 0.8},
    )


def plot_case(row: dict[str, Any], symbol_df: pd.DataFrame, charts_dir: Path, case_id: str) -> dict[str, Any]:
    entry_time = pd.Timestamp(clean(row.get("entry_time")))
    window, entry_pos = get_window(symbol_df, entry_time, before=260, after=70)
    if window.empty or entry_pos is None:
        return {"chart_file": "", "visual_status": "missing_ohlc_window", "w1_start_point_found": False, "w1_end_point_found": False, "w2_point_found": False, "macd_available": False, "rsi_available": False}

    w1_start = as_float(row.get("W1_START_PRICE"))
    w1_end = as_float(row.get("W1_END_PRICE"))
    w2_swing = as_float(row.get("W2_SWING_PRICE"))
    entry_price = as_float(row.get("entry_price"))
    stop_price = as_float(row.get("stop_price"))
    fib_618 = as_float(row.get("FIB_LEVEL_0.618"))
    target_1 = as_float(row.get("TARGET_1.0"))
    target_1618 = as_float(row.get("TARGET_1.618"))

    p_w1_start, y_w1_start = find_price_point(window, w1_start, row, entry_pos)
    p_w1_end, y_w1_end = find_price_point(window, w1_end, row, entry_pos)
    p_w2, y_w2 = find_price_point(window, w2_swing, row, entry_pos)
    macd_available = {"MACD_LINE", "MACD_SIGNAL"}.issubset(set(window.columns))
    rsi_available = "RSI" in window.columns

    has_indicator = macd_available
    fig_height = 8.2 if has_indicator else 6.4
    if has_indicator:
        fig, (ax, ax_macd) = plt.subplots(2, 1, figsize=(14.5, fig_height), gridspec_kw={"height_ratios": [4.2, 1.2], "hspace": 0.08})
    else:
        fig, ax = plt.subplots(1, 1, figsize=(14.5, fig_height))
        ax_macd = None
    fig.patch.set_facecolor("#071312")
    ax.set_facecolor("#071312")
    draw_candles(ax, window)

    x_right = len(window) + 7
    ax.set_xlim(-1, x_right)
    low = float(window["low"].min())
    high = float(window["high"].max())
    plotted_levels = [value for value in [entry_price, stop_price, fib_618, target_1, target_1618] if value is not None]
    if plotted_levels:
        low = min(low, min(plotted_levels))
        high = max(high, max(plotted_levels))
    pad = max((high - low) * 0.12, abs(high) * 0.001)
    ax.set_ylim(low - pad, high + pad)

    title = f"{clean(row.get('symbol'))} {clean(row.get('timeframe_ltf'))}:{clean(row.get('timeframe_htf'))}  {clean(row.get('entry_rule'))}  W1 {format_float(as_float(row.get('_w1_size_pct')), 3)}%"
    ax.set_title(title, color="#eafff7", fontsize=14, fontweight="bold", pad=16)
    ax.axvline(entry_pos, color="#f4b740", linewidth=1.6, alpha=0.9)
    if entry_price is not None:
        ax.scatter([entry_pos], [entry_price], color="#f4b740", s=36, zorder=6)
        annotate_level(ax, x_right - 5, entry_price, "entry", "#f4b740")
    for price, label, color, style in [
        (stop_price, "stop", "#ff6464", "--"),
        (target_1, "target 1.0", "#57d7ff", ":"),
        (target_1618, "target 1.618", "#57d7ff", ":"),
    ]:
        if price is not None:
            ax.hlines(price, 0, x_right - 4, color=color, linestyles=style, linewidth=1.1, alpha=0.9)
            annotate_level(ax, x_right - 5, price, label, color)

    if clean(row.get("entry_rule")) == "fib_limit" and fib_618 is not None:
        ax.hlines(fib_618, 0, x_right - 4, color="#b987ff", linestyles="-.", linewidth=1.3, alpha=0.95)
        annotate_level(ax, x_right - 5, fib_618, "Fib 0.618", "#b987ff")

    if p_w1_start is not None and p_w1_end is not None and y_w1_start is not None and y_w1_end is not None:
        ax.plot([p_w1_start, p_w1_end], [y_w1_start, y_w1_end], color="#41e6d0", linewidth=2.4, marker="o", markersize=4, label="W1")
        ax.text(p_w1_start, y_w1_start, "W1 inicio", color="#41e6d0", fontsize=8, va="bottom")
        ax.text(p_w1_end, y_w1_end, "W1 fin", color="#41e6d0", fontsize=8, va="bottom")
    if p_w1_end is not None and p_w2 is not None and y_w1_end is not None and y_w2 is not None:
        ax.plot([p_w1_end, p_w2], [y_w1_end, y_w2], color="#f4b740", linewidth=1.8, linestyle="--", marker="o", markersize=4, label="W2")
        ax.text(p_w2, y_w2, "W2", color="#f4b740", fontsize=8, va="bottom")

    if rsi_available:
        latest_rsi = as_float(window["RSI"].iloc[min(entry_pos, len(window) - 1)])
        if latest_rsi is not None:
            ax.text(0.01, 0.02, f"RSI entrada {latest_rsi:.1f}", transform=ax.transAxes, color="#a7c7c0", fontsize=8)

    label_positions = list(range(0, len(window), max(1, len(window) // 6)))
    labels = [pd.Timestamp(window.index[pos]).strftime("%b %d\n%H:%M") for pos in label_positions]
    ax.set_xticks(label_positions)
    ax.set_xticklabels(labels, color="#d9fff5", fontsize=8)
    ax.tick_params(axis="y", colors="#d9fff5", labelsize=8)
    ax.grid(False)
    for pos in label_positions:
        ax.axvline(pos, color="#233431", linewidth=0.6, alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color("#264944")

    if ax_macd is not None:
        ax_macd.set_facecolor("#071312")
        xs = list(range(len(window)))
        ax_macd.plot(xs, window["MACD_LINE"].astype(float), color="#41e6d0", linewidth=1.2, label="MACD")
        ax_macd.plot(xs, window["MACD_SIGNAL"].astype(float), color="#ff8a5c", linewidth=1.2, label="Signal")
        ax_macd.axhline(0, color="#667c79", linewidth=0.8)
        ax_macd.axvline(entry_pos, color="#f4b740", linewidth=1.0, alpha=0.8)
        ax_macd.set_xlim(-1, x_right)
        ax_macd.set_xticks(label_positions)
        ax_macd.set_xticklabels(labels, color="#d9fff5", fontsize=8)
        ax_macd.tick_params(axis="y", colors="#d9fff5", labelsize=8)
        ax_macd.legend(loc="upper left", fontsize=8, facecolor="#071312", edgecolor="#264944", labelcolor="#eafff7")
        for spine in ax_macd.spines.values():
            spine.set_color("#264944")

    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_file = charts_dir / f"{case_id}_{clean(row.get('entry_rule'))}_{clean(row.get('symbol')).replace('.', '')}_{clean(row.get('timeframe_ltf'))}_{clean(row.get('timeframe_htf'))}.png"
    fig.savefig(chart_file, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return {
        "chart_file": str(chart_file),
        "visual_status": "chart_created",
        "w1_start_point_found": p_w1_start is not None,
        "w1_end_point_found": p_w1_end is not None,
        "w2_point_found": p_w2 is not None,
        "macd_available": macd_available,
        "rsi_available": rsi_available,
    }


def build_cache_coverage_rows(selected: list[dict[str, Any]], cache_dir: Path) -> list[dict[str, Any]]:
    counts = Counter(clean(row.get("partial_source")) for row in selected)
    output = []
    for partial_source, count in sorted(counts.items()):
        cache_file = CACHE_BY_PARTIAL_SOURCE.get(partial_source, "")
        output.append(
            {
                "partial_source": partial_source,
                "selected_cases": count,
                "cache_file": cache_file,
                "cache_exists": bool(cache_file and (cache_dir / cache_file).exists()),
                "note": "Se carga cache pickle existente; no se recalcula portfolio ni backtest.",
            }
        )
    return output


def build_outputs(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_trade_rows(Path(args.trade_log_csv))
    selected = select_cases(rows, args.max_small_per_rule, args.max_normal_per_rule)
    output_dir = Path(args.output_dir)
    charts_dir = output_dir / "charts"
    cache_dir = Path(args.cache_dir)
    cache_by_source: dict[str, dict[str, pd.DataFrame] | None] = {}
    case_rows: list[dict[str, Any]] = []
    reconstruction_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(selected, start=1):
        case_id = f"case_{idx:03d}"
        partial_source = clean(row.get("partial_source"))
        if partial_source not in cache_by_source:
            cache_by_source[partial_source] = load_portfolio_cache(cache_dir, partial_source)
        portfolio = cache_by_source.get(partial_source) or {}
        symbol = clean(row.get("symbol"))
        symbol_df = portfolio.get(symbol) if isinstance(portfolio, dict) else None
        if symbol_df is None:
            chart_result = {"chart_file": "", "visual_status": "missing_symbol_cache", "w1_start_point_found": False, "w1_end_point_found": False, "w2_point_found": False, "macd_available": False, "rsi_available": False}
        else:
            chart_result = plot_case(row, symbol_df, charts_dir, case_id)

        case_row = {
            "case_id": case_id,
            "strategy": clean(row.get("strategy")),
            "entry_rule": clean(row.get("entry_rule")),
            "materiality_bucket": clean(row.get("_materiality_bucket")),
            "symbol": symbol,
            "group": clean(row.get("Group"), clean(row.get("group"))),
            "direction": clean(row.get("direction")),
            "setup_id": clean(row.get("setup_id")),
            "entry_time": clean(row.get("entry_time")),
            "timeframe_ltf": clean(row.get("timeframe_ltf")),
            "timeframe_htf": clean(row.get("timeframe_htf")),
            "partial_source": partial_source,
            "w1_size_pct": format_float(as_float(row.get("_w1_size_pct")), 4),
            "w1_to_bm_atr": format_float(as_float(row.get("_w1_to_bm_atr")), 4),
            "entry_price": clean(row.get("entry_price")),
            "stop_price": clean(row.get("stop_price")),
            "fib_0_618": clean(row.get("FIB_LEVEL_0.618")),
            "cache_file": CACHE_BY_PARTIAL_SOURCE.get(partial_source, ""),
            "methodology_note": "Imagen de auditoria visual; no cambia la estrategia ni prueba edge.",
            **chart_result,
        }
        case_rows.append(case_row)
        reconstruction_rows.append(
            {
                "case_id": case_id,
                "symbol": symbol,
                "entry_rule": clean(row.get("entry_rule")),
                "status": chart_result["visual_status"],
                "w1_start_point_found": chart_result["w1_start_point_found"],
                "w1_end_point_found": chart_result["w1_end_point_found"],
                "w2_point_found": chart_result["w2_point_found"],
                "limitation": "El trade_log no guarda tiempos W1/W2; se reconstruyen puntos visuales por precio desde cache OHLC/pivotes.",
            }
        )

    return {
        "trade_rows_total": len(rows),
        "selected_cases": selected,
        "case_rows": case_rows,
        "cache_coverage": build_cache_coverage_rows(selected, cache_dir),
        "reconstruction_rows": reconstruction_rows,
    }


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# ENBOLSA Strategy Visual Audit V1

Fecha: 2026-06-02

Decision: `{run_meta['decision']}`.

## Objetivo

Crear una galeria visual pequena para revisar los swings W1/W2 que alimentan
`fib_limit` y `macd_breakout` en el `trade_log` canonico de ENBOLSA.

## Resultado

- charts_created={run_meta['charts_created']}
- fib_limit_charts={run_meta['fib_limit_charts']}
- macd_breakout_charts={run_meta['macd_breakout_charts']}
- strategy_modified=false
- backtests_executed=false
- signals_generated=false

## Lectura

Las imagenes son una auditoria visual. Sirven para comprobar si el W1/W2 parece
razonable en casos concretos, especialmente en ejemplos con W1 pequeno. No son
una nueva validacion estadistica y no modifican los resultados canonicos.

## Limitacion

El `trade_log.csv` no guarda `W1_START_TIME`, `W1_END_TIME` ni `W2_TIME`.
Por eso los puntos se reconstruyen visualmente desde las caches OHLC/pivotes
existentes usando coincidencia por precio. Si un punto no se encuentra, queda
marcado en `w1_visual_reconstruction_audit.csv`.
"""


def write_outputs(output_dir: Path, result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    case_rows = result["case_rows"]
    write_csv(tables_dir / "visual_case_inventory.csv", case_rows, CASE_FIELDNAMES)
    write_csv(tables_dir / "cache_coverage_audit.csv", result["cache_coverage"])
    write_csv(tables_dir / "w1_visual_reconstruction_audit.csv", result["reconstruction_rows"])
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "risk_id": "VIS01",
                "risk": "Los tiempos exactos W1/W2 no estan en el trade_log canonico.",
                "impact": "La reconstruccion visual puede no ubicar exactamente el mismo pivote si hay precios repetidos.",
                "mitigation": "Marcar puntos encontrados/no encontrados y no usar esta galeria como prueba de edge.",
            },
            {
                "risk_id": "VIS02",
                "risk": "Una imagen individual puede inducir a generalizar.",
                "impact": "La galeria es diagnostica, no estadistica.",
                "mitigation": "Mantener la lectura junto a la auditoria cuantitativa de materialidad.",
            },
        ],
    )
    counts = Counter(clean(row.get("entry_rule")) for row in case_rows if clean(row.get("visual_status")) == "chart_created")
    run_meta = {
        "method_version": METHOD_VERSION,
        "generated_at": utc_now(),
        "trade_log_csv": str(Path(args.trade_log_csv)),
        "output_dir": str(output_dir),
        "visual_audit_created": True,
        "charts_created": sum(1 for row in case_rows if clean(row.get("visual_status")) == "chart_created"),
        "fib_limit_charts": counts.get("fib_limit", 0),
        "macd_breakout_charts": counts.get("macd_breakout", 0),
        "selected_cases_count": len(case_rows),
        "strategy_modified": False,
        "backtests_executed": False,
        "signals_generated": False,
        "sql_real_written": False,
        "db_connected": False,
        "ddl_executed": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "decision": "enbolsa_strategy_visual_audit_v1_ready_for_manual_review",
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    report = render_report(run_meta)
    (output_dir / "ENBOLSA_STRATEGY_VISUAL_AUDIT_V1.md").write_text(report, encoding="utf-8")
    Path(args.doc_path).write_text(report, encoding="utf-8")
    return run_meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create ENBOLSA visual swing audit gallery without running backtests.")
    parser.add_argument("--trade-log-csv", default=str(DEFAULT_TRADE_LOG_CSV))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    parser.add_argument("--max-small-per-rule", type=int, default=10)
    parser.add_argument("--max-normal-per-rule", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    result = build_outputs(args)
    return write_outputs(Path(args.output_dir), result, args)


if __name__ == "__main__":
    main()
