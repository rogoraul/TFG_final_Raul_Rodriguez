from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, read_json, write_csv


METHOD_VERSION = "codex_ai_analyst_package_renderer_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/codex_ai_analyst_package_renderer_v1_2026-06-06"
DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
DEFAULT_LATEST_MANIFEST_JSON = DEFAULT_LATEST_DIR / "latest_manifest.json"
DEFAULT_SCREENER_SETUPS_CSV = DEFAULT_LATEST_DIR / "screener_unified/screener_setups.csv"
DEFAULT_SCREENER_CHART_LAYERS_CSV = DEFAULT_LATEST_DIR / "screener_unified/screener_chart_layers.csv"
DEFAULT_OHLC_CSV = DEFAULT_LATEST_DIR / "ohlc/ohlc_mtf.csv"
DEFAULT_MARKET_RADAR_CSV = DEFAULT_LATEST_DIR / "market_radar/market_radar.csv"
DEFAULT_CORRELATION_PAIRS_CSV = DEFAULT_LATEST_DIR / "correlations/correlation_pairs.csv"
DEFAULT_ROLLING_CORRELATIONS_CSV = DEFAULT_LATEST_DIR / "correlations/rolling_correlations.csv"
DEFAULT_WEAVECOUNT_SCREENER_CSV = DEFAULT_LATEST_DIR / "weavecount/weavecount_screener.csv"
DEFAULT_WEAVECOUNT_STRUCTURE_POINTS_CSV = DEFAULT_LATEST_DIR / "weavecount/weavecount_structure_points.csv"
DEFAULT_DESIGN_DOC = REPO_ROOT / "docs/CODEX_AI_ANALYST_READONLY_DESIGN_V1.md"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/CODEX_AI_ANALYST_PACKAGE_RENDERER_V1.md"

PACKAGE_FILES = [
    "setup_context.json",
    "market_context.json",
    "ohlc_window.csv",
    "chart_layers.csv",
    "chart.png",
    "source_manifest.json",
    "prompt_context.md",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(value: str, max_len: int = 96) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("._")
    if not slug:
        slug = "review_package"
    return slug[:max_len]


def as_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.replace("Z", ""), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_setup(
    rows: list[dict[str, Any]],
    *,
    setup_id: str = "",
    symbol: str = "",
    timeframe: str = "",
    setup_type: str = "",
) -> dict[str, Any] | None:
    candidates = rows
    if setup_id:
        candidates = [row for row in candidates if str(row.get("setup_id", "")).strip() == setup_id]
    if symbol:
        candidates = [row for row in candidates if str(row.get("symbol", "")).strip().lower() == symbol.lower()]
    if timeframe:
        candidates = [row for row in candidates if str(row.get("timeframe", "")).strip().lower() == timeframe.lower()]
    if setup_type:
        candidates = [row for row in candidates if str(row.get("setup_type", "")).strip().lower() == setup_type.lower()]
    if not candidates:
        return None

    def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        try:
            timing = int(float(str(row.get("timing_priority", "99") or "99")))
        except ValueError:
            timing = 99
        try:
            score = int(float(str(row.get("setup_quality_score", "0") or "0")))
        except ValueError:
            score = 0
        return timing, -score, str(row.get("setup_id", ""))

    return sorted(candidates, key=sort_key)[0]


def rows_for_symbol_timeframe(rows: list[dict[str, Any]], symbol: str, timeframe: str) -> list[dict[str, Any]]:
    filtered = [
        row
        for row in rows
        if str(row.get("symbol", "")).strip() == symbol
        and str(row.get("timeframe", "")).strip().lower() == timeframe.lower()
    ]
    filtered.sort(key=lambda row: str(row.get("timestamp") or row.get("time") or ""))
    return filtered


def ohlc_window(rows: list[dict[str, Any]], symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
    selected = rows_for_symbol_timeframe(rows, symbol, timeframe)
    return selected[-limit:]


def setup_layers(rows: list[dict[str, Any]], setup_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("setup_id", "")).strip() == setup_id]


def market_context_rows(rows: list[dict[str, Any]], symbol: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("symbol", "")).strip() == symbol]


def weavecount_context_rows(rows: list[dict[str, Any]], symbol: str, timeframe: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("symbol", "")).strip() == symbol
        and str(row.get("timeframe", "")).strip().lower() == timeframe.lower()
    ]


def correlation_context_rows(rows: list[dict[str, Any]], symbol: str, limit: int = 8) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if str(row.get("asset_1", row.get("symbol_1", ""))).strip() == symbol
        or str(row.get("asset_2", row.get("symbol_2", ""))).strip() == symbol
        or str(row.get("base_symbol", "")).strip() == symbol
    ]

    def strength(row: dict[str, Any]) -> float:
        for key in ("pearson", "spearman", "kendall", "correlation", "value"):
            value = as_float(row.get(key))
            if value is not None:
                return abs(value)
        return 0.0

    return sorted(selected, key=strength, reverse=True)[:limit]


def close_values(candles: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in candles:
        close = as_float(row.get("close"))
        if close is not None:
            values.append(close)
    return values


def ema(values: list[float], period: int) -> list[float | None]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    output: list[float | None] = []
    current: float | None = None
    for value in values:
        current = value if current is None else alpha * value + (1 - alpha) * current
        output.append(current)
    return output


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    if len(values) < 2:
        return [None for _ in values]
    gains: list[float] = []
    losses: list[float] = []
    output: list[float | None] = [None]
    avg_gain: float | None = None
    avg_loss: float | None = None
    for index in range(1, len(values)):
        diff = values[index] - values[index - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
        if index < period:
            output.append(None)
            continue
        if index == period:
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
        else:
            assert avg_gain is not None and avg_loss is not None
            avg_gain = ((avg_gain * (period - 1)) + gains[-1]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[-1]) / period
        if not avg_loss:
            output.append(100.0)
        else:
            rs = (avg_gain or 0.0) / avg_loss
            output.append(100.0 - (100.0 / (1.0 + rs)))
    return output


def macd(values: list[float]) -> tuple[list[float | None], list[float | None]]:
    fast = ema(values, 12)
    slow = ema(values, 26)
    macd_line: list[float | None] = []
    for fast_value, slow_value in zip(fast, slow):
        if fast_value is None or slow_value is None:
            macd_line.append(None)
        else:
            macd_line.append(fast_value - slow_value)
    signal_source = [value if value is not None else 0.0 for value in macd_line]
    signal = ema(signal_source, 9)
    return macd_line, signal


def nearest_index(timestamps: list[str], value: Any) -> int | None:
    target = parse_time(value)
    if target is None:
        return None
    parsed = [parse_time(item) for item in timestamps]
    distances = [
        (abs((item - target).total_seconds()), index)
        for index, item in enumerate(parsed)
        if item is not None
    ]
    if not distances:
        return None
    return min(distances)[1]


def render_chart_png(
    path: Path,
    *,
    setup: dict[str, Any],
    candles: list[dict[str, Any]],
    layers: list[dict[str, Any]],
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not candles:
        raise ValueError("No OHLC rows available for chart rendering.")
    timestamps = [str(row.get("timestamp") or row.get("time") or "") for row in candles]
    x_values = list(range(len(candles)))
    closes = close_values(candles)
    rsi_values = rsi(closes)
    macd_values, signal_values = macd(closes)

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(14.5, 9.2),
        dpi=150,
        sharex=True,
        gridspec_kw={"height_ratios": [5.2, 1.35, 1.35], "hspace": 0.18},
    )
    bg = "#06100f"
    panel_bg = "#050909"
    ink = "#d8ede6"
    muted = "#8da8a1"
    fig.patch.set_facecolor(bg)
    for axis in axes:
        axis.set_facecolor(panel_bg)
        axis.tick_params(colors=ink, labelsize=8)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#27413c")
        axis.spines["bottom"].set_color("#27413c")
        axis.grid(False)

    price_ax, rsi_ax, macd_ax = axes
    candle_width = 0.54
    for index, row in enumerate(candles):
        open_ = as_float(row.get("open"))
        high = as_float(row.get("high"))
        low = as_float(row.get("low"))
        close = as_float(row.get("close"))
        if None in (open_, high, low, close):
            continue
        assert open_ is not None and high is not None and low is not None and close is not None
        color = "#60e68f" if close >= open_ else "#ff6b65"
        price_ax.vlines(index, low, high, color=color, linewidth=1.0, alpha=0.95)
        body_low = min(open_, close)
        body_height = max(abs(close - open_), 1e-9)
        price_ax.add_patch(
            Rectangle(
                (index - candle_width / 2, body_low),
                candle_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.9,
                alpha=0.36,
            )
        )

    label_x = len(candles) + max(8, min(22, len(candles) // 8))
    layer_count = 0
    for layer in layers:
        layer_type = str(layer.get("layer_type", "")).strip()
        label = str(layer.get("label") or layer_type or "layer")
        color = str(layer.get("color") or "#5ce0ca")
        style = str(layer.get("style") or "dash").lower()
        linestyle = ":" if style == "dot" else "-" if style == "solid" else "--"
        price = as_float(layer.get("price"))
        start_price = as_float(layer.get("start_price"))
        end_price = as_float(layer.get("end_price"))
        start_index = nearest_index(timestamps, layer.get("start_time"))
        end_index = nearest_index(timestamps, layer.get("end_time"))
        if start_price is not None and end_price is not None and start_index is not None and end_index is not None:
            price_ax.plot(
                [start_index, end_index],
                [start_price, end_price],
                color=color,
                linestyle=linestyle,
                linewidth=1.7 if "swing" in layer_type or "directrix" in layer_type else 1.2,
                alpha=0.92,
            )
            price_ax.scatter([start_index, end_index], [start_price, end_price], color=color, s=14, zorder=5)
            price_ax.text(end_index + 0.45, end_price, label, color=ink, fontsize=7, va="center")
            layer_count += 1
            continue
        if price is not None:
            price_ax.hlines(price, 0, label_x - 1.0, colors=color, linestyles=linestyle, linewidth=1.0, alpha=0.92)
            if not label.lower().startswith("nivel redondo"):
                price_ax.text(
                    label_x - 0.6,
                    price,
                    label,
                    color=ink,
                    fontsize=7,
                    va="center",
                    ha="left",
                    bbox={"facecolor": panel_bg, "edgecolor": color, "linewidth": 0.6, "pad": 2},
                )
            layer_count += 1

    price_ax.set_title(
        f"{setup.get('symbol')} {setup.get('timeframe')} - {setup.get('setup_type')} ({setup.get('setup_quality_score', '-')}/5)",
        color="#f2fff9",
        fontsize=12,
        pad=12,
    )
    price_ax.set_xlim(-1, label_x + 1)
    price_ax.set_ylabel("Precio", color=muted, fontsize=8)

    rsi_plot = [float("nan") if value is None else value for value in rsi_values]
    rsi_ax.plot(x_values[: len(rsi_plot)], rsi_plot, color="#d7a84b", linewidth=1.1)
    rsi_ax.axhline(70, color="#d7a84b", linestyle="--", linewidth=0.75, alpha=0.55)
    rsi_ax.axhline(30, color="#5ce0ca", linestyle="--", linewidth=0.75, alpha=0.45)
    rsi_ax.set_ylim(0, 100)
    rsi_ax.set_ylabel("RSI", color=muted, fontsize=8)

    macd_plot = [float("nan") if value is None else value for value in macd_values]
    signal_plot = [float("nan") if value is None else value for value in signal_values]
    macd_ax.plot(x_values[: len(macd_plot)], macd_plot, color="#5ce0ca", linewidth=1.05, label="MACD")
    macd_ax.plot(x_values[: len(signal_plot)], signal_plot, color="#ff8a65", linewidth=0.95, label="Senal")
    macd_ax.axhline(0, color="#8da8a1", linestyle="-", linewidth=0.6, alpha=0.45)
    macd_ax.set_ylabel("MACD", color=muted, fontsize=8)

    tick_count = min(7, max(2, len(candles) // 20))
    tick_indices = sorted(set(round(index * (len(candles) - 1) / max(tick_count - 1, 1)) for index in range(tick_count)))
    tick_labels = []
    for index in tick_indices:
        stamp = timestamps[index]
        parsed = parse_time(stamp)
        tick_labels.append(parsed.strftime("%b %d\n%H:%M") if parsed else stamp[-11:])
    macd_ax.set_xticks(tick_indices)
    macd_ax.set_xticklabels(tick_labels, color=ink, fontsize=8)

    fig.text(
        0.01,
        0.01,
        "AI package chart - study-only, no signal, no execution",
        color=muted,
        fontsize=7,
    )
    fig.savefig(path, facecolor=bg, bbox_inches="tight")
    plt.close(fig)
    return {"chart_path": str(path), "chart_rendered": True, "ohlc_rows": len(candles), "layer_rows": len(layers), "layers_drawn": layer_count}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def write_prompt_context(path: Path, *, setup: dict[str, Any], source_manifest: dict[str, Any]) -> None:
    text = f"""# AI Analyst Prompt Context

## Scope

Read-only chart/setup review package. Do not provide financial advice, do not approve orders, do not call MT5 or Telegram, and do not describe this as an automatic signal.

## Selected Setup

- setup_id: `{setup.get('setup_id', '')}`
- symbol: `{setup.get('symbol', '')}`
- timeframe: `{setup.get('timeframe', '')}`
- setup_type: `{setup.get('setup_type', '')}`
- timing_state: `{setup.get('timing_state', '')}`
- setup_quality_score: `{setup.get('setup_quality_score', '')}`
- is_signal: `{setup.get('is_signal', '')}`
- is_study_only: `{setup.get('is_study_only', '')}`

## Allowed Language

Use: setup for review, visual risk, confluence, contradiction, timing context, requires human review.

## Blocked Language

Do not use: buy now, sell now, safe trade, guaranteed return, approved for MT5, execute order, automatic signal, probability label, certainty label.

## Sources

See `source_manifest.json`. The chart image is only a companion to structured CSV/JSON data.

## Source Manifest Digest

`{source_manifest.get('package_hash_seed', '')}`
"""
    path.write_text(text, encoding="utf-8")


def build_source_manifest(
    *,
    args: argparse.Namespace,
    package_dir: Path,
    setup: dict[str, Any],
    package_slug: str,
) -> dict[str, Any]:
    sources = {
        "latest_manifest_json": args.latest_manifest_json,
        "screener_setups_csv": args.screener_setups_csv,
        "screener_chart_layers_csv": args.screener_chart_layers_csv,
        "ohlc_csv": args.ohlc_csv,
        "market_radar_csv": args.market_radar_csv,
        "correlation_pairs_csv": args.correlation_pairs_csv,
        "rolling_correlations_csv": args.rolling_correlations_csv,
        "weavecount_screener_csv": args.weavecount_screener_csv,
        "weavecount_structure_points_csv": args.weavecount_structure_points_csv,
        "design_doc": args.design_doc,
    }
    source_rows = []
    for source_id, path in sources.items():
        path = Path(path)
        source_rows.append(
            {
                "source_id": source_id,
                "path": str(path),
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
        )
    seed = "|".join(f"{row['source_id']}={row['sha256']}" for row in source_rows)
    return {
        "package_id": package_slug,
        "package_dir": str(package_dir),
        "generated_at": utc_now(),
        "method_version": METHOD_VERSION,
        "setup_id": setup.get("setup_id", ""),
        "symbol": setup.get("symbol", ""),
        "timeframe": setup.get("timeframe", ""),
        "sources": source_rows,
        "package_hash_seed": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "model_called": False,
        "is_read_only": True,
    }


def generate_package(args: argparse.Namespace) -> dict[str, Any]:
    setups = read_csv(args.screener_setups_csv)
    layers = read_csv(args.screener_chart_layers_csv)
    ohlc = read_csv(args.ohlc_csv)
    market = read_csv(args.market_radar_csv)
    correlations = read_csv(args.correlation_pairs_csv)
    rolling = read_csv(args.rolling_correlations_csv)
    weave = read_csv(args.weavecount_screener_csv)
    weave_points = read_csv(args.weavecount_structure_points_csv)
    latest_manifest = read_json(args.latest_manifest_json)

    setup = select_setup(
        setups,
        setup_id=args.setup_id,
        symbol=args.symbol,
        timeframe=args.timeframe,
        setup_type=args.setup_type,
    )
    if setup is None:
        if args.allow_empty:
            return {"package_created": False, "reason": "no_setup_selected", "setups_rows": len(setups)}
        raise SystemExit("No matching setup found for package renderer.")

    setup_id = str(setup.get("setup_id", ""))
    symbol = str(setup.get("symbol", ""))
    timeframe = str(setup.get("timeframe", ""))
    package_slug = safe_slug(f"{symbol}_{timeframe}_{setup.get('setup_type', 'setup')}_{hashlib.sha1(setup_id.encode()).hexdigest()[:8]}")
    package_dir = args.output_dir / "packages" / package_slug
    package_dir.mkdir(parents=True, exist_ok=True)

    package_layers = setup_layers(layers, setup_id)
    package_ohlc = ohlc_window(ohlc, symbol, timeframe, args.ohlc_limit)
    package_market_rows = market_context_rows(market, symbol)
    package_weave_rows = weavecount_context_rows(weave, symbol, timeframe)
    package_correlation_rows = correlation_context_rows(correlations, symbol)
    package_rolling_rows = correlation_context_rows(rolling, symbol)
    package_weave_points = [
        row for row in weave_points if str(row.get("symbol", "")).strip() == symbol and str(row.get("timeframe", "")).strip().lower() == timeframe.lower()
    ]

    source_manifest = build_source_manifest(args=args, package_dir=package_dir, setup=setup, package_slug=package_slug)
    setup_context = {
        "setup": setup,
        "selected_at": utc_now(),
        "safety": {
            "is_signal": boolish(setup.get("is_signal")),
            "is_study_only": boolish(setup.get("is_study_only", "true")),
            "can_execute_order": boolish(setup.get("can_execute_order")),
            "would_send_to_mt5": boolish(setup.get("would_send_to_mt5")),
            "would_send_telegram_order": boolish(setup.get("would_send_telegram_order")),
            "model_called": False,
        },
    }
    market_context = {
        "market_radar": package_market_rows,
        "correlations": package_correlation_rows,
        "rolling_correlations": package_rolling_rows,
        "weavecount": package_weave_rows,
        "weavecount_structure_points": package_weave_points,
        "latest_manifest": latest_manifest,
    }

    write_json(package_dir / "setup_context.json", setup_context)
    write_json(package_dir / "market_context.json", market_context)
    write_csv(package_dir / "ohlc_window.csv", package_ohlc)
    write_csv(package_dir / "chart_layers.csv", package_layers)
    write_json(package_dir / "source_manifest.json", source_manifest)
    write_prompt_context(package_dir / "prompt_context.md", setup=setup, source_manifest=source_manifest)
    chart_audit = render_chart_png(package_dir / "chart.png", setup=setup, candles=package_ohlc, layers=package_layers)

    package_files = {name: str(package_dir / name) for name in PACKAGE_FILES}
    package_manifest = {
        "package_id": package_slug,
        "package_dir": str(package_dir),
        "files": package_files,
        "setup_id": setup_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "setup_type": setup.get("setup_type", ""),
        "chart_audit": chart_audit,
        "model_called": False,
        "sql_real_written": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
    }
    write_json(package_dir / "package_manifest.json", package_manifest)
    return {
        "package_created": True,
        "package": package_manifest,
        "source_manifest": source_manifest,
        "setups_rows": len(setups),
        "layers_rows": len(layers),
        "ohlc_rows": len(ohlc),
        "market_rows": len(market),
        "correlation_rows": len(correlations),
        "rolling_rows": len(rolling),
        "weavecount_rows": len(weave),
    }


def render_phase_report(run_meta: dict[str, Any]) -> str:
    package = run_meta.get("package", {})
    return f"""# Codex AI Analyst Package Renderer V1

Decision: `{run_meta['decision']}`

## Resultado

Se implementa un renderer artifact-first para crear paquetes reproducibles de revision del AI Analyst sin llamar a modelos.

Paquete generado:

- package_id: `{package.get('package_id', 'not_created')}`
- symbol: `{package.get('symbol', '')}`
- timeframe: `{package.get('timeframe', '')}`
- setup_type: `{package.get('setup_type', '')}`
- package_dir: `{package.get('package_dir', '')}`

## Archivos Del Paquete

- `setup_context.json`
- `market_context.json`
- `ohlc_window.csv`
- `chart_layers.csv`
- `chart.png`
- `source_manifest.json`
- `prompt_context.md`
- `package_manifest.json`

## Seguridad

- model_called={run_meta['model_called']}
- ai_review_generated={run_meta['ai_review_generated']}
- is_read_only={run_meta['is_read_only']}
- sql_real_written={run_meta['sql_real_written']}
- mt5_connected={run_meta['mt5_connected']}
- telegram_connected={run_meta['telegram_connected']}
- orders_sent={run_meta['orders_sent']}
- signals_generated={run_meta['signals_generated']}

## Siguiente Paso

Revisar visualmente el paquete y, despues, disenar la capa de llamada a modelo con gates de prompts, coste, lenguaje bloqueado y validacion de salida.
"""


def write_phase_artifacts(args: argparse.Namespace, result: dict[str, Any]) -> dict[str, Any]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    package = result.get("package", {})
    source_manifest = result.get("source_manifest", {})
    write_csv(
        tables_dir / "package_generation_audit.csv",
        [
            {
                "check": "package_created",
                "status": "pass" if result.get("package_created") else "warning",
                "evidence": package.get("package_dir", result.get("reason", "")),
            },
            {
                "check": "structured_data_present",
                "status": "pass" if package.get("package_dir") else "warning",
                "evidence": "setup_context.json|market_context.json|ohlc_window.csv|chart_layers.csv",
            },
            {
                "check": "model_not_called",
                "status": "pass",
                "evidence": "model_called=false",
            },
        ],
    )
    chart_audit = package.get("chart_audit", {})
    write_csv(
        tables_dir / "chart_render_audit.csv",
        [
            {
                "check": "chart_png",
                "status": "pass" if chart_audit.get("chart_rendered") else "warning",
                "evidence": chart_audit.get("chart_path", ""),
                "ohlc_rows": chart_audit.get("ohlc_rows", 0),
                "layer_rows": chart_audit.get("layer_rows", 0),
            }
        ],
    )
    write_csv(
        tables_dir / "source_manifest_audit.csv",
        source_manifest.get("sources", []),
    )
    write_csv(
        tables_dir / "safety_flags_audit.csv",
        [
            {"flag": "model_called", "value": False, "expected": False, "status": "pass"},
            {"flag": "sql_real_written", "value": False, "expected": False, "status": "pass"},
            {"flag": "mt5_connected", "value": False, "expected": False, "status": "pass"},
            {"flag": "telegram_connected", "value": False, "expected": False, "status": "pass"},
            {"flag": "orders_sent", "value": 0, "expected": 0, "status": "pass"},
            {"flag": "signals_generated", "value": False, "expected": False, "status": "pass"},
        ],
    )
    issues = []
    if not result.get("package_created"):
        issues.append({"issue_id": "P21-01", "severity": "medium", "status": "open", "description": result.get("reason", "package not created")})
    if chart_audit.get("layer_rows", 0) == 0:
        issues.append({"issue_id": "P21-02", "severity": "low", "status": "watch", "description": "Package has no chart layers for selected setup"})
    if not issues:
        issues.append({"issue_id": "P21-OK", "severity": "none", "status": "closed", "description": "No blocking issues detected"})
    write_csv(tables_dir / "issues_or_risks.csv", issues)

    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": utc_now(),
        "decision": "codex_ai_analyst_package_renderer_v1_ready_for_model_gateway_design",
        "package_renderer_implemented": True,
        "ai_analyst_implemented": False,
        "ai_review_generated": False,
        "model_called": False,
        "is_read_only": True,
        "chart_png_generated": bool(chart_audit.get("chart_rendered")),
        "structured_package_generated": bool(result.get("package_created")),
        "package": package,
        "setups_rows": result.get("setups_rows", 0),
        "layers_rows": result.get("layers_rows", 0),
        "ohlc_rows": result.get("ohlc_rows", 0),
        "market_rows": result.get("market_rows", 0),
        "correlation_rows": result.get("correlation_rows", 0),
        "rolling_rows": result.get("rolling_rows", 0),
        "weavecount_rows": result.get("weavecount_rows", 0),
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    write_json(args.output_dir / "run_meta.json", run_meta)
    (args.output_dir / "CODEX_AI_ANALYST_PACKAGE_RENDERER_V1.md").write_text(render_phase_report(run_meta), encoding="utf-8")
    return run_meta


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create reproducible read-only AI Analyst review packages.")
    parser.add_argument("--latest-manifest-json", type=Path, default=DEFAULT_LATEST_MANIFEST_JSON)
    parser.add_argument("--screener-setups-csv", type=Path, default=DEFAULT_SCREENER_SETUPS_CSV)
    parser.add_argument("--screener-chart-layers-csv", type=Path, default=DEFAULT_SCREENER_CHART_LAYERS_CSV)
    parser.add_argument("--ohlc-csv", type=Path, default=DEFAULT_OHLC_CSV)
    parser.add_argument("--market-radar-csv", type=Path, default=DEFAULT_MARKET_RADAR_CSV)
    parser.add_argument("--correlation-pairs-csv", type=Path, default=DEFAULT_CORRELATION_PAIRS_CSV)
    parser.add_argument("--rolling-correlations-csv", type=Path, default=DEFAULT_ROLLING_CORRELATIONS_CSV)
    parser.add_argument("--weavecount-screener-csv", type=Path, default=DEFAULT_WEAVECOUNT_SCREENER_CSV)
    parser.add_argument("--weavecount-structure-points-csv", type=Path, default=DEFAULT_WEAVECOUNT_STRUCTURE_POINTS_CSV)
    parser.add_argument("--design-doc", type=Path, default=DEFAULT_DESIGN_DOC)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--setup-id", default="")
    parser.add_argument("--symbol", default="")
    parser.add_argument("--timeframe", default="")
    parser.add_argument("--setup-type", default="")
    parser.add_argument("--ohlc-limit", type=int, default=220)
    parser.add_argument("--allow-empty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = generate_package(args)
    run_meta = write_phase_artifacts(args, result)
    print(json.dumps({"decision": run_meta["decision"], "package": run_meta.get("package", {}).get("package_dir", "")}, indent=2))


if __name__ == "__main__":
    main()
