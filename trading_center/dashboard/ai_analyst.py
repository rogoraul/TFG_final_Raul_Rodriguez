from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from trading_center.dashboard.charting import normalized_timestamp
from trading_center.dashboard.correlations import corr_float, pair_key, pair_return_points
from trading_center.dashboard.formatting import safe_float
from trading_center.dashboard.paths import latest_or_fallback_dir, latest_or_fallback_path
from trading_center.dashboard.refresh import load_latest_manifest_metadata
from trading_center.dashboard.screener import filter_screener_setups
from trading_center.dashboard.weavecount import (
    canonical_wavecount_rows,
    unique_wavecount_visible_rows,
    wavecount_number,
    wavecount_quality_label,
    wavecount_status_label,
    wavecount_wave_label,
)
from trading_center.market_correlations import corr_pair, distance_correlation
from trading_center.readonly_dashboard import REPO_ROOT, read_json, write_csv


DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/codex_ai_analyst_dash_integration_v1_2026-06-07"
DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
DEFAULT_LATEST_MANIFEST_JSON = DEFAULT_LATEST_DIR / "latest_manifest.json"
CANONICAL_MARKET_RADAR_CSV = REPO_ROOT / "artifacts/tfg/trading_center_market_radar_v1_2026-05-31/market_radar.csv"
CANONICAL_MARKET_CORRELATIONS_DIR = REPO_ROOT / "artifacts/tfg/trading_center_market_correlations_v1_2026-05-31"
CANONICAL_SQL_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
CANONICAL_WEAVECOUNT_SCREENER_DIR = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01"
DEFAULT_MARKET_RADAR_CSV = latest_or_fallback_path(DEFAULT_LATEST_DIR / "market_radar/market_radar.csv", CANONICAL_MARKET_RADAR_CSV)
DEFAULT_MARKET_CORRELATIONS_DIR = latest_or_fallback_dir(
    DEFAULT_LATEST_DIR / "correlations",
    CANONICAL_MARKET_CORRELATIONS_DIR,
    "correlation_pairs.csv",
)
DEFAULT_CORRELATION_PAIRS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "correlation_pairs.csv"
DEFAULT_ROLLING_CORRELATIONS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "rolling_correlations.csv"
DEFAULT_CORRELATION_RETURNS_CSV = DEFAULT_MARKET_CORRELATIONS_DIR / "correlation_returns_sample.csv"
ACTIVE_SQL_OHLC_CSV = latest_or_fallback_path(DEFAULT_LATEST_DIR / "ohlc/ohlc_mtf.csv", CANONICAL_SQL_OHLC_CSV)
DEFAULT_WEAVECOUNT_SCREENER_DIR = latest_or_fallback_dir(
    DEFAULT_LATEST_DIR / "weavecount",
    CANONICAL_WEAVECOUNT_SCREENER_DIR,
    "weavecount_screener.csv",
)
DEFAULT_WEAVECOUNT_SCREENER_CSV = DEFAULT_WEAVECOUNT_SCREENER_DIR / "weavecount_screener.csv"
ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV = DEFAULT_WEAVECOUNT_SCREENER_DIR / "weavecount_structure_points.csv"


def _dash_app() -> Any:
    from trading_center import dash_readonly_app

    return dash_readonly_app


def build_dash_data(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _dash_app().build_dash_data(*args, **kwargs)


def wavecount_case_id(row: dict[str, Any]) -> str:
    return _dash_app().wavecount_case_id(row)


def wavecount_enriched_row(row: dict[str, Any]) -> dict[str, Any]:
    return _dash_app().wavecount_enriched_row(row)


def wavecount_ohlc_index() -> dict[tuple[str, str], list[dict[str, Any]]]:
    return _dash_app().wavecount_ohlc_index()


def wavecount_structure_points(row: dict[str, Any]) -> list[dict[str, Any]]:
    return _dash_app().wavecount_structure_points(row)


def wavecount_direction_label(row: dict[str, Any]) -> str:
    return _dash_app().wavecount_direction_label(row)


def ai_analyst_context_options() -> list[dict[str, str]]:
    return [
        {"label": "Setup Screener", "value": "screener_setup"},
        {"label": "Onda WeaveCount", "value": "weavecount_case"},
        {"label": "Correlacion", "value": "correlation"},
        {"label": "Mercado general", "value": "market_summary"},
    ]


def ai_analyst_control_visibility(context_value: str | None) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    context = str(context_value or "screener_setup")
    visible = {"display": "grid"}
    hidden = {"display": "none"}
    if context == "screener_setup":
        return visible, hidden, hidden, hidden
    if context == "weavecount_case":
        return hidden, visible, hidden, hidden
    if context == "correlation":
        return hidden, hidden, visible, hidden
    if context == "market_summary":
        return hidden, hidden, hidden, visible
    return hidden, hidden, hidden, hidden


def ai_analyst_setup_options(rows: list[dict[str, Any]], review_state: str | None = "reviewable", limit: int = 80) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for row in filter_screener_setups(rows, None, "__all__", "__all__", "__all__", 1, "__all__", review_state)[:limit]:
        setup_id = str(row.get("setup_id", "")).strip()
        if not setup_id:
            continue
        label = f"{row.get('symbol', '')} {row.get('timeframe', '')} - {row.get('setup_type', '')} - {row.get('setup_quality_score', '-')}/5"
        options.append({"label": label, "value": setup_id})
    return options


def ai_analyst_wave_options(rows: list[dict[str, Any]], limit: int = 80) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for row in unique_wavecount_visible_rows(canonical_wavecount_rows(rows))[:limit]:
        case_id = wavecount_case_id(row)
        if not case_id:
            continue
        label = (
            f"{row.get('symbol', '')} {row.get('timeframe', '')} / "
            f"{wavecount_wave_label(row)} / {wavecount_direction_label(row)} / "
            f"{wavecount_quality_label(row)}"
        )
        options.append({"label": label, "value": case_id})
    return options


def ai_analyst_correlation_options(rows: list[dict[str, Any]], limit: int = 80) -> list[dict[str, str]]:
    candidates = [row for row in rows if str(row.get("timeframe", "")).strip() == "H1"]
    if not candidates:
        candidates = list(rows)

    def sort_key(row: dict[str, Any]) -> float:
        return abs(corr_float(row.get("pearson")) or corr_float(row.get("value")) or 0.0)

    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in sorted(candidates, key=sort_key, reverse=True):
        timeframe = str(row.get("timeframe", "")).strip()
        asset_1 = str(row.get("asset_1", "")).strip()
        asset_2 = str(row.get("asset_2", "")).strip()
        if not timeframe or not asset_1 or not asset_2:
            continue
        value = f"{timeframe}|{asset_1}|{asset_2}"
        if value in seen:
            continue
        seen.add(value)
        pearson = corr_float(row.get("pearson"))
        metric = "n/d" if pearson is None else f"{pearson:+.2f}"
        options.append({"label": f"{asset_1} / {asset_2} - {timeframe} - Pearson {metric}", "value": value})
        if len(options) >= limit:
            break
    return options


def ai_analyst_fixture_review_payload(package_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": "dash_fixture_review",
        "package_id": package_manifest.get("package_id", ""),
        "review_status": "reviewed",
        "review_priority": 3,
        "summary": "Revision fixture generada desde el Dash; no hay llamada real a modelo.",
        "setup_reading": "Paquete validado para comprobar schema, fuentes y lenguaje antes de una fase con proveedor real.",
        "confluences": ["paquete reproducible disponible", "grafico y capas exportadas"],
        "contradictions": ["sin review IA real todavia"],
        "risk_notes": ["No usar como instruccion operativa ni autorizacion."],
        "human_next_checks": ["Revisar manualmente grafico, timing y contexto antes de cualquier decision humana."],
        "sources": ["setup_context.json", "market_context.json", "ohlc_window.csv", "chart_layers.csv", "chart.png"],
        "macro_context_summary": "No solicitado en modo fixture.",
        "macro_risk_level": "not_requested",
        "macro_sources": [],
        "safety_flags": {
            "can_execute_order": False,
            "would_send_to_mt5": False,
            "would_send_telegram_order": False,
            "sql_real_written": False,
            "mt5_connected": False,
            "telegram_connected": False,
            "signals_generated": False,
        },
    }


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_package_slug(value: str, max_len: int = 96) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("._")
    return (slug or "review_package")[:max_len]


def selected_wavecount_row(case_id: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = str(case_id or "").strip()
    if not target:
        return None
    for row in unique_wavecount_visible_rows(canonical_wavecount_rows(rows)):
        if wavecount_case_id(row) == target:
            return row
    return None


def wavecount_package_ohlc_window(row: dict[str, Any], limit: int = 320) -> list[dict[str, Any]]:
    symbol = str(row.get("symbol", "")).strip()
    timeframe = str(row.get("timeframe", "")).strip()
    if not symbol or not timeframe:
        return []
    enriched = wavecount_enriched_row(row)
    as_of = normalized_timestamp(enriched.get("latest_close_time") or enriched.get("as_of_bar_time") or enriched.get("timestamp"))
    rows = wavecount_ohlc_index().get((symbol, timeframe), [])
    if as_of:
        rows = [item for item in rows if normalized_timestamp(item.get("timestamp")) <= as_of]
    structure_points = wavecount_structure_points(enriched)
    if structure_points:
        first_structure_time = structure_points[0]["x"]
        first_index = next(
            (
                index
                for index, item in enumerate(rows)
                if normalized_timestamp(item.get("timestamp")) >= first_structure_time
            ),
            0,
        )
        return rows[max(0, first_index - 18) :][-limit:]
    return rows[-limit:]


def wavecount_package_chart_layers(row: dict[str, Any]) -> list[dict[str, Any]]:
    enriched = wavecount_enriched_row(row)
    case_id = wavecount_case_id(enriched)
    symbol = str(enriched.get("symbol", "")).strip()
    timeframe = str(enriched.get("timeframe", "")).strip()
    points = wavecount_structure_points(enriched)
    layers: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        layers.append(
            {
                "case_id": case_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "layer_type": "wavecount_point",
                "label": point.get("label", ""),
                "x": point.get("x", ""),
                "price": point.get("y", ""),
                "point_kind": point.get("kind", ""),
                "sequence": index,
                "is_operational": False,
            }
        )
    for index in range(max(0, len(points) - 1)):
        start = points[index]
        end = points[index + 1]
        layers.append(
            {
                "case_id": case_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "layer_type": "wavecount_segment",
                "label": f"{end.get('label', '')} tramo",
                "start_time": start.get("x", ""),
                "end_time": end.get("x", ""),
                "start_price": start.get("y", ""),
                "end_price": end.get("y", ""),
                "sequence": index,
                "is_current": index == len(points) - 2,
                "is_operational": False,
            }
        )
    for key, label in [("activation_level", "activacion"), ("invalidation_level", "invalidacion")]:
        level = safe_float(enriched.get(key))
        if level is None:
            continue
        layers.append(
            {
                "case_id": case_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "layer_type": key,
                "label": label,
                "price": level,
                "is_operational": False,
            }
        )
    return layers


def render_wavecount_package_chart(path: Path, row: dict[str, Any], candles: list[dict[str, Any]], layers: list[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not candles:
        return {"chart_rendered": False, "chart_path": str(path), "reason": "no_ohlc_rows", "ohlc_rows": 0, "layer_rows": len(layers)}
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except (ImportError, ModuleNotFoundError) as exc:
        return {"chart_rendered": False, "chart_path": str(path), "reason": f"matplotlib_unavailable:{exc}", "ohlc_rows": len(candles), "layer_rows": len(layers)}

    x_values = list(range(len(candles)))
    time_to_index = {normalized_timestamp(item.get("timestamp")): index for index, item in enumerate(candles)}
    fig, ax = plt.subplots(figsize=(14, 7), dpi=130)
    fig.patch.set_facecolor("#050909")
    ax.set_facecolor("#050909")
    for spine in ax.spines.values():
        spine.set_color("#284944")
    ax.tick_params(colors="#d4ebe4", labelsize=8)
    ax.grid(axis="y", color="#203936", linewidth=0.7, alpha=0.45)
    for index, candle in enumerate(candles):
        open_price = safe_float(candle.get("open"))
        high_price = safe_float(candle.get("high"))
        low_price = safe_float(candle.get("low"))
        close_price = safe_float(candle.get("close"))
        if None in (open_price, high_price, low_price, close_price):
            continue
        color = "#68e28f" if close_price >= open_price else "#ff6b65"
        ax.vlines(index, low_price, high_price, color=color, linewidth=1.0, alpha=0.95)
        body_low = min(open_price, close_price)
        body_height = max(abs(close_price - open_price), 1e-9)
        ax.add_patch(Rectangle((index - 0.32, body_low), 0.64, body_height, edgecolor=color, facecolor=color, alpha=0.38, linewidth=1.1))

    segment_layers = [layer for layer in layers if layer.get("layer_type") == "wavecount_segment"]
    for layer in segment_layers:
        start_index = time_to_index.get(normalized_timestamp(layer.get("start_time")))
        end_index = time_to_index.get(normalized_timestamp(layer.get("end_time")))
        start_price = safe_float(layer.get("start_price"))
        end_price = safe_float(layer.get("end_price"))
        if start_index is None or end_index is None or start_price is None or end_price is None:
            continue
        is_current = bool(layer.get("is_current"))
        color = "#d7a84b" if is_current else "#83aaa3"
        ax.plot([start_index, end_index], [start_price, end_price], color=color, linewidth=2.2 if is_current else 1.6, linestyle="-" if is_current else ":", marker="o", markersize=4)

    for layer in layers:
        if layer.get("layer_type") not in {"activation_level", "invalidation_level"}:
            continue
        price = safe_float(layer.get("price"))
        if price is None:
            continue
        color = "#5ce0ca" if layer.get("layer_type") == "activation_level" else "#d7a84b"
        ax.axhline(price, color=color, linewidth=1.1, linestyle="--", alpha=0.85)
        ax.text(len(candles) - 1, price, f" {layer.get('label', '')}", color="#f2fff9", va="center", fontsize=8, bbox={"facecolor": "#050909", "edgecolor": color, "alpha": 0.9})

    tick_step = max(1, len(candles) // 6)
    tick_indices = x_values[::tick_step]
    if tick_indices and tick_indices[-1] != x_values[-1]:
        tick_indices.append(x_values[-1])
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([normalized_timestamp(candles[index].get("timestamp"))[5:16] for index in tick_indices], color="#d4ebe4")
    title = f"{row.get('symbol', '')} {row.get('timeframe', '')} {wavecount_wave_label(row)} {wavecount_direction_label(row)}"
    ax.set_title(title, color="#f2fff9", fontsize=13, pad=14)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return {"chart_rendered": True, "chart_path": str(path), "ohlc_rows": len(candles), "layer_rows": len(layers)}


def write_wavecount_prompt_context(path: Path, *, wave_context: dict[str, Any], source_manifest: dict[str, Any]) -> None:
    text = f"""# AI Analyst WeaveCount Review Context

Analysis type: `weavecount_case`

## Selected Case

- symbol: `{wave_context.get('symbol', '')}`
- timeframe: `{wave_context.get('timeframe', '')}`
- wave: `{wave_context.get('wave_label', '')}`
- direction: `{wave_context.get('direction_label', '')}`
- quality: `{wave_context.get('quality_label', '')}`
- status: `{wave_context.get('status_label', '')}`

## Boundaries

- This is structural study context only.
- Do not describe it as a trading signal.
- Do not approve execution, MT5, Telegram, or order placement.

## Sources

Package hash seed: `{source_manifest.get('package_hash_seed', '')}`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_wavecount_source_manifest(package_dir: Path, row: dict[str, Any], package_slug: str) -> dict[str, Any]:
    sources = {
        "latest_manifest_json": DEFAULT_LATEST_MANIFEST_JSON,
        "ohlc_csv": ACTIVE_SQL_OHLC_CSV,
        "market_radar_csv": DEFAULT_MARKET_RADAR_CSV,
        "weavecount_screener_csv": DEFAULT_WEAVECOUNT_SCREENER_CSV,
        "weavecount_structure_points_csv": ACTIVE_WEAVECOUNT_STRUCTURE_POINTS_CSV,
        "dash_app": REPO_ROOT / "trading_center/dash_readonly_app.py",
        "design_doc": REPO_ROOT / "docs/CODEX_AI_ANALYST_READONLY_DESIGN_V1.md",
    }
    source_rows = []
    for source_id, path in sources.items():
        source_path = Path(path)
        source_rows.append(
            {
                "source_id": source_id,
                "path": str(source_path),
                "exists": source_path.exists(),
                "sha256": _sha256_file(source_path),
            }
        )
    seed = "|".join(f"{item['source_id']}={item['sha256']}" for item in source_rows)
    return {
        "package_id": package_slug,
        "package_dir": str(package_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_version": "codex_ai_analyst_weavecount_package_from_dash_v1",
        "analysis_type": "weavecount_case",
        "case_id": wavecount_case_id(row),
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "sources": source_rows,
        "package_hash_seed": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "model_called": False,
        "is_read_only": True,
    }


def run_ai_analyst_weavecount_review(
    case_id: str,
    *,
    output_dir: Path = DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR,
    gateway_mode: str = "fixture",
) -> dict[str, Any]:
    case_id = str(case_id or "").strip()
    if not case_id:
        return {"status": "blocked", "reason": "missing_wavecount_case_id", "model_called": False}

    data = build_dash_data()
    row = selected_wavecount_row(case_id, data.get("wavecount_rows", []))
    if row is None:
        return {"status": "blocked", "reason": "wavecount_case_not_found", "model_called": False}

    package_root = output_dir / "weavecount_package_renderer"
    gateway_output = _gateway_output_dir(output_dir, "model_gateway_weavecount", gateway_mode)
    package_slug = _safe_package_slug(
        f"{row.get('symbol', '')}_{row.get('timeframe', '')}_{wavecount_wave_label(row)}_{hashlib.sha1(case_id.encode()).hexdigest()[:8]}"
    )
    package_dir = package_root / "packages" / package_slug
    package_dir.mkdir(parents=True, exist_ok=True)

    candles = wavecount_package_ohlc_window(row)
    layers = wavecount_package_chart_layers(row)
    market_context = {
        "market_radar": [item for item in data.get("market_radar_rows", []) if str(item.get("symbol", "")).strip() == str(row.get("symbol", "")).strip()],
        "latest_manifest": load_latest_manifest_metadata(DEFAULT_LATEST_MANIFEST_JSON),
        "market_summary": data.get("market_summary", {}),
    }
    wave_context = {
        "analysis_type": "weavecount_case",
        "case_id": case_id,
        "symbol": row.get("symbol", ""),
        "market_group": row.get("market_group", ""),
        "timeframe": row.get("timeframe", ""),
        "wave_label": wavecount_wave_label(row),
        "wave_number": wavecount_number(row),
        "direction_label": wavecount_direction_label(row),
        "status_label": wavecount_status_label(row),
        "quality_label": wavecount_quality_label(row),
        "classification_reason": row.get("classification_reason", ""),
        "activation_level": row.get("activation_level", ""),
        "invalidation_level": row.get("invalidation_level", ""),
        "source_row": row,
        "safety": {
            "is_signal": False,
            "is_study_only": True,
            "can_execute_order": False,
            "would_send_to_mt5": False,
            "would_send_telegram_order": False,
            "model_called": False,
        },
    }
    source_manifest = build_wavecount_source_manifest(package_dir, row, package_slug)
    chart_audit = render_wavecount_package_chart(package_dir / "chart.png", row, candles, layers)

    _write_json_file(package_dir / "setup_context.json", {"setup": wave_context, "selected_at": datetime.now(timezone.utc).isoformat(), "safety": wave_context["safety"]})
    _write_json_file(package_dir / "market_context.json", market_context)
    write_csv(package_dir / "ohlc_window.csv", candles)
    write_csv(package_dir / "chart_layers.csv", layers)
    _write_json_file(package_dir / "source_manifest.json", source_manifest)
    write_wavecount_prompt_context(package_dir / "prompt_context.md", wave_context=wave_context, source_manifest=source_manifest)

    package_files = {
        name: str(package_dir / name)
        for name in ["setup_context.json", "market_context.json", "ohlc_window.csv", "chart_layers.csv", "chart.png", "source_manifest.json", "prompt_context.md"]
    }
    package_manifest = {
        "package_id": package_slug,
        "package_dir": str(package_dir),
        "files": package_files,
        "analysis_type": "weavecount_case",
        "setup_id": case_id,
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "setup_type": "weavecount_case",
        "chart_audit": chart_audit,
        "model_called": False,
        "sql_real_written": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
    }
    _write_json_file(package_dir / "package_manifest.json", package_manifest)

    gateway_meta = _run_ai_analyst_gateway(
        package_manifest,
        gateway_output,
        gateway_mode=gateway_mode,
        fixture_overrides={
            "summary": "Revision fixture de caso WeaveCount generada desde el Dash; no hay llamada real a modelo.",
            "setup_reading": "Paquete estructural WeaveCount validado para revisar onda, puntos y contexto de mercado sin convertirlo en senal.",
            "confluences": ["caso WeaveCount seleccionado", "velas y puntos estructurales exportados"],
            "human_next_checks": ["Revisar que la hipotesis de onda tenga tamano, direccion y niveles coherentes."],
        },
    )
    return {
        "status": "prepared",
        "analysis_type": "weavecount_case",
        "package_dir": str(package_dir),
        "gateway_dir": str(gateway_output),
        "package_id": gateway_meta.get("package_id", package_manifest.get("package_id", "")),
        "request_decision": gateway_meta.get("request_decision", ""),
        "output_validation_status": gateway_meta.get("output_validation_status", ""),
        "model_called": bool(gateway_meta.get("model_called", False)),
        "network_call_allowed": bool(gateway_meta.get("network_call_allowed", False)),
        "ai_review_generated": bool(gateway_meta.get("ai_review_generated", False)),
        "macro_web_research_requested": bool(gateway_meta.get("macro_web_research_requested", False)),
        "report_pdf": gateway_meta.get("report_pdf", ""),
        "chart_rendered": bool(chart_audit.get("chart_rendered", False)),
        "ohlc_rows": len(candles),
        "layer_rows": len(layers),
    }


def _run_ai_analyst_gateway(
    package_manifest: dict[str, Any],
    gateway_output: Path,
    *,
    gateway_mode: str = "fixture",
    fixture_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from trading_center.codex_ai_analyst_model_gateway import main as gateway_main

    package_dir = Path(str(package_manifest.get("package_dir", "")))
    gateway_output.mkdir(parents=True, exist_ok=True)
    if gateway_mode in {"codex_cli", "codex_cli_macro"}:
        manual_intent = "revision humana controlada desde el panel AI Analyst read-only con Codex local"
        if gateway_mode == "codex_cli_macro":
            manual_intent = "revision humana controlada con Codex local y contexto macro/noticias verificado en internet"
        argv = [
            "--package-dir",
            str(package_dir),
            "--output-dir",
            str(gateway_output),
            "--provider-id",
            "codex_cli",
            "--max-prompt-tokens",
            "8000",
            "--max-output-tokens",
            "1200",
            "--timeout-seconds",
            "300",
            "--max-cost",
            "0.05",
            "--call-mode",
            "real",
            "--allow-network-call",
            "--manual-intent",
            manual_intent,
        ]
        if gateway_mode == "codex_cli_macro":
            argv.append("--macro-web-research")
        gateway_main(argv)
        meta = read_json(gateway_output / "run_meta.json")
        report_pdf = write_ai_analyst_pdf_report(package_manifest, gateway_output)
        if report_pdf:
            meta["report_pdf"] = report_pdf
        return meta

    fixture_path = gateway_output / "fixture_review_output.json"
    fixture_payload = ai_analyst_fixture_review_payload(package_manifest)
    if fixture_overrides:
        fixture_payload.update(fixture_overrides)
    fixture_path.write_text(json.dumps(fixture_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    gateway_main(
        [
            "--package-dir",
            str(package_dir),
            "--output-dir",
            str(gateway_output),
            "--provider-id",
            "dash_fixture_provider",
            "--model-id",
            "fixture-model",
            "--max-prompt-tokens",
            "8000",
            "--max-output-tokens",
            "1200",
            "--timeout-seconds",
            "30",
            "--max-cost",
            "0.05",
            "--call-mode",
            "fixture",
            "--fixture-output-json",
            str(fixture_path),
        ]
    )
    meta = read_json(gateway_output / "run_meta.json")
    report_pdf = write_ai_analyst_pdf_report(package_manifest, gateway_output)
    if report_pdf:
        meta["report_pdf"] = report_pdf
    return meta


def _gateway_output_dir(output_dir: Path, stem: str, gateway_mode: str) -> Path:
    suffix = ""
    if gateway_mode == "codex_cli":
        suffix = "_codex_cli"
    elif gateway_mode == "codex_cli_macro":
        suffix = "_codex_cli_macro"
    return output_dir / f"{stem}{suffix}"


def ai_analyst_gateway_status_line(result: dict[str, Any]) -> str:
    model_called = str(bool(result.get("model_called", False))).lower()
    network_allowed = str(bool(result.get("network_call_allowed", False))).lower()
    macro_requested = str(bool(result.get("macro_web_research_requested", False))).lower()
    review_generated = str(bool(result.get("ai_review_generated", False))).lower()
    return f"model_called={model_called} - network_call_allowed={network_allowed} - macro={macro_requested} - review={review_generated}"


def ai_analyst_pdf_report_path(gateway_output: Path) -> Path:
    return gateway_output / "ai_analyst_review_report.pdf"


def ai_analyst_download_pdf_path(path_value: str) -> Path | None:
    if not str(path_value or "").strip():
        return None
    try:
        resolved = Path(str(path_value)).resolve()
        repo_resolved = REPO_ROOT.resolve()
        if repo_resolved not in [resolved, *resolved.parents]:
            return None
    except Exception:
        return None
    if not resolved.exists() or resolved.suffix.lower() != ".pdf":
        return None
    return resolved


def latex_escape(value: Any) -> str:
    text = humanize_report_text(value)
    return latex_escape_raw(text)


def latex_escape_raw(value: Any) -> str:
    text = str(value or "")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def humanize_report_text(value: Any) -> str:
    text = str(value or "")
    replacements = {
        "range_pct_h1_24": "rango 24h en H1",
        "atr_pct_h1_ratio": "ATR H1 frente a su mediana",
        "bars_since_touch": "velas desde el ultimo toque",
        "reaction_detected": "reaccion detectada",
        "reaction_direction": "direccion de la reaccion",
        "setup_quality_score": "puntuacion de calidad visual",
        "study_only": "solo estudio",
        "is_signal": "es senal",
        "can_execute_order": "puede ejecutar orden",
        "would_send_to_mt5": "enviaria a MT5",
        "would_send_telegram_order": "enviaria orden por Telegram",
        "fib_limit_live_candidate": "candidato fib_limit",
        "macd_breakout": "ruptura MACD",
        "market_radar": "radar de mercado",
        "source_manifest": "manifiesto de fuentes",
        "ohlc_window": "ventana OHLC",
        "chart_layers": "capas del grafico",
        "prompt_context": "contexto del prompt",
        "macro_sources": "fuentes macro",
        "macro_risk_level": "riesgo macro",
    }
    for raw, label in replacements.items():
        text = text.replace(raw, label)
    return text.replace("_", " ")


def latex_paragraph(value: Any) -> str:
    return latex_escape(value).replace("\n", "\n\n")


def latex_itemize(items: Any) -> str:
    if not isinstance(items, list):
        items = [items] if str(items or "").strip() else []
    clean_items = [str(item).strip() for item in items if str(item).strip()]
    if not clean_items:
        return r"\textit{Sin elementos relevantes documentados.}"
    body = "\n".join(f"  \\item {latex_escape(item)}" for item in clean_items)
    return "\\begin{itemize}\n" + body + "\n\\end{itemize}"


LOCAL_SOURCE_LABELS = {
    "setup_context.json": "Datos estructurados del setup",
    "market_context.json": "Contexto agregado de mercado",
    "source_manifest.json": "Trazabilidad del paquete",
    "chart_layers.csv": "Capas dibujadas en el grafico",
    "ohlc_window.csv": "Ventana de velas OHLC",
    "prompt_context.md": "Contexto enviado a Codex",
    "chart.png": "Imagen renderizada del grafico",
    "screener_setups.csv": "Setups del Screener",
    "screener_chart_layers.csv": "Capas del Screener",
    "market_radar.csv": "Radar de tendencia y volatilidad",
}


def latex_href(url: str, label: str) -> str:
    safe_url = str(url or "").strip().replace("}", "").replace("{", "")
    return f"\\href{{\\detokenize{{{safe_url}}}}}{{{latex_escape_raw(label)}}}"


def short_source_label(label: str, url: str, *, max_chars: int = 72) -> str:
    clean = humanize_report_text(label).strip()
    if not clean or clean.startswith("http"):
        clean = re.sub(r"^https?://(www\.)?", "", str(url or "").strip()).split("/")[0] or "Fuente externa"
    clean = clean.replace("_", " ")
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip(" .,-") + "..."


def split_source_entry(source: Any) -> tuple[str, str]:
    text = str(source or "").strip()
    match = re.search(r"(https?://\S+)", text)
    if not match:
        return text, ""
    url = match.group(1).rstrip(".,);]")
    label = text[: match.start()].strip(" :-")
    return label or url, url


def latex_sources_block(sources: Any) -> str:
    if not isinstance(sources, list):
        sources = [sources] if str(sources or "").strip() else []
    local_rows: list[str] = []
    external_rows: list[str] = []
    for source in sources:
        label, url = split_source_entry(source)
        if url:
            short_label = short_source_label(label, url)
            external_rows.append(
                "\\item "
                + latex_href(url, short_label)
                + r"\\[-0.15em] {\footnotesize "
                + latex_escape("Fuente externa consultada para contexto macro/noticias.")
                + "}"
            )
            continue
        clean_label = str(label or "").strip()
        if not clean_label:
            continue
        description = LOCAL_SOURCE_LABELS.get(clean_label, "Fuente local del paquete de revision")
        local_rows.append(f"{latex_escape_raw(clean_label)} & {latex_escape(description)} \\\\")
    if not local_rows and not external_rows:
        return r"\textit{Sin fuentes documentadas.}"
    blocks: list[str] = []
    if local_rows:
        blocks.append(
            "\\textbf{Fuentes locales}\\par\n"
            "\\begin{tabularx}{\\textwidth}{p{4.2cm}X}\n"
            + "\n".join(local_rows)
            + "\n\\end{tabularx}"
        )
    if external_rows:
        blocks.append(
            "\\vspace{0.45em}\n\\textbf{Enlaces externos}\\par\n"
            "\\begin{itemize}\n"
            + "\n".join(external_rows)
            + "\n\\end{itemize}"
        )
    return "\n\n".join(blocks)


def latex_compact_clause(items: Any, *, empty: str) -> str:
    if not isinstance(items, list):
        items = [items] if str(items or "").strip() else []
    clean_items = [humanize_report_text(item).strip().rstrip(".") for item in items if str(item).strip()]
    if not clean_items:
        return latex_escape(empty)
    if len(clean_items) == 1:
        return latex_escape(clean_items[0] + ".")
    sentence = "; ".join(clean_items[:-1]) + "; y " + clean_items[-1] + "."
    return latex_escape(sentence)


def macro_context_for_report(review: dict[str, Any]) -> str:
    raw = humanize_report_text(review.get("macro_context_summary", "")).strip()
    risk_level = str(review.get("macro_risk_level", "not_requested") or "not_requested")
    risk_label = {
        "not_requested": "no solicitado",
        "unknown": "no verificado",
        "low": "bajo",
        "medium": "medio",
        "high": "alto",
    }.get(risk_level, risk_level)
    if not raw or raw.lower().startswith("no solicitado"):
        return latex_escape("No se solicito lectura macro para este paquete. El informe se limita al contexto tecnico y a los datos estructurados del Trading Center.")
    sentences = re.split(r"(?<=[.!?])\s+", raw)
    midpoint = max(1, len(sentences) // 2)
    first = " ".join(sentences[:midpoint]).strip()
    second = " ".join(sentences[midpoint:]).strip()
    if not second:
        second = raw
    interpretation = (
        "Desde una lectura financiera, este contexto no cambia por si solo el setup tecnico, "
        "pero si condiciona la prudencia de la revision: aumenta el peso de comprobar calendario, "
        "liquidez y confirmacion posterior antes de extraer conclusiones. "
    )
    if risk_level in {"medium", "high"}:
        interpretation += "Con riesgo macro marcado como " + risk_label + ", la lectura debe tratarse como sensible a evento y no como una validacion aislada del grafico."
    else:
        interpretation += "Si el riesgo macro no queda verificado, debe constar como incertidumbre, no como evidencia favorable."
    return latex_escape(first) + "\n\n" + latex_escape(second) + "\n\n" + latex_escape(interpretation)


def ai_analyst_report_conclusion(review: dict[str, Any], package_manifest: dict[str, Any]) -> str:
    symbol = package_manifest.get("symbol", "el activo")
    setup_type = humanize_report_text(package_manifest.get("setup_type", "setup"))
    analysis_type = str(package_manifest.get("analysis_type", "screener_setup") or "screener_setup")
    priority = review.get("review_priority", "")
    macro_risk = {
        "not_requested": "no solicitado",
        "unknown": "no verificado",
        "low": "bajo",
        "medium": "medio",
        "high": "alto",
    }.get(str(review.get("macro_risk_level", "not_requested") or "not_requested"), str(review.get("macro_risk_level", "not_requested")))
    priority_label = f"{priority}/5" if str(priority).strip() else "no especificada"
    common_limit = "En todos los casos, el informe documenta seguimiento y revision humana; no autoriza ejecucion, MT5 ni envio de ordenes."
    if analysis_type == "weavecount_case":
        text = (
            f"Conclusion operativa y financiera: {symbol} queda como hipotesis WeaveCount de estudio, no como senal. "
            f"La prioridad de revision AI es {priority_label} y el riesgo macro figura como {macro_risk}. "
            "La lectura debe centrarse en si la secuencia de ondas, los puntos estructurales y los niveles de activacion/invalidation mantienen coherencia visual con el ultimo tramo. "
            "Si la onda queda demasiado corta, contradice el contexto superior o pierde sus niveles clave, debe tratarse como candidato descartable o pendiente de nueva estructura. "
            f"{common_limit}"
        )
    elif analysis_type == "market_summary":
        text = (
            f"Conclusion operativa y financiera: el mercado queda resumido con prioridad de revision AI {priority_label} y riesgo macro {macro_risk}. "
            "La utilidad principal es ordenar el mapa de fuerza, volatilidad, extremos y dispersion del universo para decidir que activos revisar primero. "
            "No debe leerse como seleccion automatica de operaciones: una lectura de mercado cargada, tranquila o divergente solo cambia la prioridad de vigilancia y la cautela del analisis posterior. "
            f"{common_limit}"
        )
    elif analysis_type == "correlation":
        text = (
            f"Conclusion operativa y financiera: el analisis de correlacion queda como lectura de relacion entre activos, con prioridad de revision AI {priority_label} y riesgo macro {macro_risk}. "
            "La conclusion debe usarse para detectar dependencia, diversificacion aparente o concentracion de riesgo entre instrumentos, no para validar un setup por si sola. "
            "Si la relacion es inestable, cambia por timeframe o se apoya en una ventana corta, debe tratarse como contexto auxiliar antes de revisar exposicion o pares comparables. "
            f"{common_limit}"
        )
    else:
        text = (
            f"Conclusion operativa y financiera: {symbol} queda como {setup_type} de revision, no como instruccion de mercado. "
            f"La prioridad de revision AI es {priority_label} y el riesgo macro figura como {macro_risk}. "
            "La lectura debe comprobar si el timing, los niveles, la tendencia y las contradicciones descritas sostienen una revision grafica razonable. "
            "Si falta confirmacion de precio, si el setup llega tarde o si el contexto macro es incierto, el caso debe permanecer como vigilancia o documentacion, no como accion. "
            f"{common_limit}"
        )
    return latex_escape(text)


def ai_analyst_weavecount_elliott_paragraph(package_manifest: dict[str, Any]) -> str:
    if str(package_manifest.get("analysis_type", "")).strip() != "weavecount_case":
        return ""
    package_dir = Path(str(package_manifest.get("package_dir", "")))
    context = read_json(package_dir / "setup_context.json")
    setup = context.get("setup", {}) if isinstance(context.get("setup"), dict) else {}
    wave_label = humanize_report_text(setup.get("wave_label", package_manifest.get("setup_type", "WeaveCount")))
    direction = humanize_report_text(setup.get("direction_label", ""))
    status_label = humanize_report_text(setup.get("status_label", ""))
    quality = humanize_report_text(setup.get("quality_label", ""))
    activation = setup.get("activation_level", "")
    invalidation = setup.get("invalidation_level", "")
    paragraph = (
        f"Lectura Elliott / WeaveCount: el caso se interpreta como una hipotesis estructural {wave_label}"
        f"{' de sesgo ' + direction if direction else ''}, con estado {status_label or 'candidato'}"
        f"{' y calidad ' + quality if quality else ''}. En terminos de Elliott, lo relevante no es tomar la etiqueta de onda como senal, "
        "sino comprobar si la secuencia previa conserva proporcionalidad, alternancia y continuidad interna suficientes para sostener el conteo. "
        "La activacion debe entenderse como nivel de confirmacion visual de la hipotesis, y la invalidacion como frontera metodologica para descartarla, "
        "no como orden automatica ni como filtro operativo."
    )
    if activation not in {"", None} or invalidation not in {"", None}:
        paragraph += f" En este paquete, la referencia de activacion es {activation or 'no definida'} y la de invalidacion es {invalidation or 'no definida'}."
    return latex_escape(paragraph)


def ai_analyst_report_chart_path(package_manifest: dict[str, Any], gateway_output: Path) -> str:
    files = package_manifest.get("files", {}) if isinstance(package_manifest.get("files"), dict) else {}
    chart_path = Path(str(files.get("chart.png", "")))
    if not chart_path.exists():
        package_dir = Path(str(package_manifest.get("package_dir", "")))
        chart_path = package_dir / "chart.png"
    if not chart_path.exists():
        return ""
    target = gateway_output / "ai_analyst_report_chart.png"
    try:
        shutil.copyfile(chart_path, target)
    except Exception:
        return ""
    return target.name


def write_ai_analyst_latex_report(package_manifest: dict[str, Any], gateway_output: Path, review: dict[str, Any], run_meta: dict[str, Any]) -> str:
    compiler = shutil.which("xelatex") or shutil.which("pdflatex")
    if not compiler:
        return ""
    pdf_path = ai_analyst_pdf_report_path(gateway_output)
    tex_path = gateway_output / "ai_analyst_review_report.tex"
    error_log_path = gateway_output / "ai_analyst_review_report_latex_error.log"
    if error_log_path.exists():
        error_log_path.unlink()
    chart_name = ai_analyst_report_chart_path(package_manifest, gateway_output)
    setup_line = " ".join(
        part
        for part in [
            str(package_manifest.get("symbol", "")).strip(),
            str(package_manifest.get("timeframe", "")).strip(),
            str(package_manifest.get("setup_type", "")).strip(),
        ]
        if part
    )
    title = f"Informe AI Analyst: {setup_line or review.get('package_id', '')}"
    sources = list(review.get("sources", [])) + list(review.get("macro_sources", []))
    chart_block = ""
    if chart_name:
        chart_block = (
            "\\section*{Grafico de referencia}\n"
            "\\begin{center}\n"
            f"\\includegraphics[width=0.96\\textwidth]{{\\detokenize{{{chart_name}}}}}\n"
            "\\end{center}\n"
        )
    weavecount_block = ""
    weavecount_paragraph = ai_analyst_weavecount_elliott_paragraph(package_manifest)
    if weavecount_paragraph:
        weavecount_block = "\\section*{Lectura Elliott / WeaveCount}\n" + weavecount_paragraph + "\n"
    tex = rf"""
\documentclass[11pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage[spanish]{{babel}}
\usepackage{{geometry}}
\usepackage{{graphicx}}
\usepackage{{hyperref}}
\usepackage{{xcolor}}
\usepackage{{tabularx}}
\geometry{{margin=2cm}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.55em}}
\sloppy
\definecolor{{tcTeal}}{{HTML}}{{0E7C74}}
\definecolor{{tcDark}}{{HTML}}{{101817}}
\definecolor{{tcMuted}}{{HTML}}{{526A65}}
\definecolor{{tcWarnBg}}{{HTML}}{{FFF7E5}}
\definecolor{{tcWarnBorder}}{{HTML}}{{C99123}}
\hypersetup{{colorlinks=true, urlcolor=tcTeal, linkcolor=tcTeal}}
\begin{{document}}

\begin{{center}}
{{\huge\bfseries {latex_escape(title)}}}\\[0.25em]
{{\large Reporte read-only para revision humana}}
\end{{center}}

\vspace{{0.2em}}
\hrule height 0.7pt
\vspace{{0.9em}}

\begin{{tabularx}}{{\textwidth}}{{>{{\bfseries}}p{{3.2cm}}X}}
Paquete & {latex_escape(review.get("package_id", package_manifest.get("package_id", "")))} \\
Setup & {latex_escape(setup_line)} \\
Modelo & {latex_escape(run_meta.get("model_id_effective", "") or "heredado de Codex")} \\
Thinking & {latex_escape(run_meta.get("reasoning_effort_effective", "") or "n/d")} \\
Macro & {latex_escape(review.get("macro_risk_level", "not_requested"))} \\
Estado & {latex_escape(review.get("review_status", ""))} \\
\end{{tabularx}}

\vspace{{0.75em}}
\fcolorbox{{tcWarnBorder}}{{tcWarnBg}}{{%
\begin{{minipage}}{{0.94\textwidth}}
\textbf{{Limite de uso.}} Este informe no es una senal, no autoriza MT5 y no ejecuta ordenes. Sirve para priorizar revision humana y documentar el contexto.
\end{{minipage}}}}

\vspace{{0.4em}}

\section*{{Resumen}}
{latex_paragraph(review.get("summary", ""))}

\section*{{Lectura tecnica}}
{latex_paragraph(review.get("setup_reading", ""))}

{weavecount_block}

{chart_block}

\section*{{Lectura de confluencias}}
{latex_compact_clause(review.get("confluences", []), empty="No hay confluencias relevantes documentadas en el paquete.")}

\section*{{Contradicciones y cautelas}}
{latex_compact_clause(review.get("contradictions", []), empty="No hay contradicciones relevantes documentadas en el paquete.")}

\section*{{Riesgos principales}}
{latex_compact_clause(review.get("risk_notes", []), empty="No hay riesgos adicionales documentados en el paquete.")}

\section*{{Contexto macro y noticias}}
{macro_context_for_report(review)}

\section*{{Conclusion operativa y financiera}}
{ai_analyst_report_conclusion(review, package_manifest)}

\section*{{Comprobaciones humanas}}
{latex_itemize(review.get("human_next_checks", []))}

\section*{{Fuentes}}
{latex_sources_block(sources)}

\end{{document}}
"""
    tex_path.write_text(tex, encoding="utf-8")
    try:
        completed = subprocess.run(
            [compiler, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=gateway_output,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except Exception:
        return ""
    if completed.returncode != 0 or not pdf_path.exists():
        error_log_path.write_text((completed.stdout or "") + "\n" + (completed.stderr or ""), encoding="utf-8")
        return ""
    return str(pdf_path)


def write_ai_analyst_matplotlib_report(package_manifest: dict[str, Any], gateway_output: Path, review: dict[str, Any], run_meta: dict[str, Any]) -> str:
    pdf_path = ai_analyst_pdf_report_path(gateway_output)
    try:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception:
        return ""
    sections = [
        ("Resumen", review.get("summary", "")),
        ("Lectura tecnica", review.get("setup_reading", "")),
        ("Confluencias", "; ".join(str(item) for item in review.get("confluences", []))),
        ("Contradicciones", "; ".join(str(item) for item in review.get("contradictions", []))),
        ("Riesgos", "; ".join(str(item) for item in review.get("risk_notes", []))),
        ("Contexto macro y noticias", review.get("macro_context_summary", "")),
        ("Comprobaciones humanas", "; ".join(str(item) for item in review.get("human_next_checks", []))),
    ]
    with PdfPages(pdf_path) as pdf:
        lines = [
            f"Informe AI Analyst",
            f"Paquete: {review.get('package_id', package_manifest.get('package_id', ''))}",
            f"Setup: {package_manifest.get('symbol', '')} {package_manifest.get('timeframe', '')} {package_manifest.get('setup_type', '')}",
            f"Modelo: {run_meta.get('model_id_effective', '') or 'heredado de Codex'} | Thinking: {run_meta.get('reasoning_effort_effective', '') or 'n/d'}",
            "Uso: revision humana. No es senal ni autoriza ejecucion.",
            "",
        ]
        for title, content in sections:
            lines.append(title.upper())
            lines.extend(textwrap.wrap(str(content or ""), width=105) or ["Sin contenido."])
            lines.append("")
        for chunk_start in range(0, len(lines), 48):
            chunk = lines[chunk_start : chunk_start + 48]
            fig = plt.figure(figsize=(8.27, 11.69), facecolor="#ffffff")
            fig.text(0.08, 0.95, "\n".join(chunk), ha="left", va="top", fontsize=9.2, family="DejaVu Sans", color="#101817")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    return str(pdf_path)


def ai_analyst_fallback_review_from_meta(package_manifest: dict[str, Any], run_meta: dict[str, Any]) -> dict[str, Any]:
    request_decision = str(run_meta.get("request_decision", "unknown"))
    output_status = str(run_meta.get("output_validation_status", "blocked"))
    error_summary = str(run_meta.get("error_message", "") or run_meta.get("provider_error", "") or "").strip()
    if not error_summary:
        error_summary = "El proveedor no devolvio una salida validable para el schema del AI Analyst."
    return {
        "review_id": f"diagnostic_{package_manifest.get('package_id', 'package')}",
        "package_id": package_manifest.get("package_id", ""),
        "review_status": "blocked_gateway_diagnostic",
        "review_priority": "",
        "summary": (
            "El paquete se preparo correctamente, pero no hay una revision analitica validada porque la llamada a Codex o la validacion de salida quedo bloqueada. "
            "Este PDF documenta el estado del intento para que puedas revisar el paquete y repetir el analisis sin perder trazabilidad."
        ),
        "setup_reading": (
            f"Gateway: {request_decision}. Validacion de salida: {output_status}. "
            f"Diagnostico: {error_summary}"
        ),
        "confluences": [],
        "contradictions": ["No existe lectura AI validada para este intento."],
        "risk_notes": [
            "No interpretar este PDF como analisis del setup.",
            "Repetir la ejecucion de Codex o usar Preparar paquete si solo se necesita el paquete reproducible.",
        ],
        "human_next_checks": [
            "Abrir el paquete reproducible y comprobar chart.png, setup_context.json y market_context.json.",
            "Revisar logs del gateway antes de repetir Codex + macro.",
        ],
        "sources": ["setup_context.json", "market_context.json", "source_manifest.json", "chart_layers.csv", "ohlc_window.csv", "chart.png"],
        "macro_context_summary": "No hay lectura macro validada en este intento porque el gateway no produjo una salida aceptada.",
        "macro_risk_level": "unknown",
        "macro_sources": [],
    }


def write_ai_analyst_pdf_report(package_manifest: dict[str, Any], gateway_output: Path) -> str:
    review_path = gateway_output / "review_output.json"
    if not review_path.exists():
        review_path = gateway_output / "fixture_review_output.json"
    review = read_json(review_path)
    run_meta = read_json(gateway_output / "run_meta.json")
    if not review:
        review = ai_analyst_fallback_review_from_meta(package_manifest, run_meta)

    gateway_output.mkdir(parents=True, exist_ok=True)
    latex_pdf = write_ai_analyst_latex_report(package_manifest, gateway_output, review, run_meta)
    if latex_pdf:
        return latex_pdf
    return write_ai_analyst_matplotlib_report(package_manifest, gateway_output, review, run_meta)


def market_package_chart_layers(market_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for timeframe in ["M15", "H1", "H4", "D1"]:
        up = sum(1 for row in market_rows if str(row.get(f"{timeframe.lower()}_trend", "")).lower() == "bullish")
        down = sum(1 for row in market_rows if str(row.get(f"{timeframe.lower()}_trend", "")).lower() == "bearish")
        mixed = max(0, len(market_rows) - up - down)
        rows.extend(
            [
                {"layer_type": "market_trend_distribution", "timeframe": timeframe, "side": "bullish", "value": up, "is_operational": False},
                {"layer_type": "market_trend_distribution", "timeframe": timeframe, "side": "bearish", "value": down, "is_operational": False},
                {"layer_type": "market_trend_distribution", "timeframe": timeframe, "side": "mixed", "value": mixed, "is_operational": False},
            ]
        )
    high_vol = sum(1 for row in market_rows if (safe_float(row.get("atr_pct_h1_ratio")) or 0.0) >= 1.5)
    low_vol = sum(1 for row in market_rows if (safe_float(row.get("atr_pct_h1_ratio")) or 0.0) <= 0.75)
    rows.extend(
        [
            {"layer_type": "market_volatility_summary", "bucket": "high_vs_median", "value": high_vol, "is_operational": False},
            {"layer_type": "market_volatility_summary", "bucket": "low_vs_median", "value": low_vol, "is_operational": False},
        ]
    )
    return rows


def render_market_package_chart(path: Path, market_rows: list[dict[str, Any]], layers: list[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except (ImportError, ModuleNotFoundError) as exc:
        return {"chart_rendered": False, "chart_path": str(path), "reason": f"matplotlib_unavailable:{exc}", "ohlc_rows": len(market_rows), "layer_rows": len(layers)}
    timeframes = ["M15", "H1", "H4", "D1"]
    bullish = [int(next((row["value"] for row in layers if row.get("timeframe") == tf and row.get("side") == "bullish"), 0)) for tf in timeframes]
    bearish = [int(next((row["value"] for row in layers if row.get("timeframe") == tf and row.get("side") == "bearish"), 0)) for tf in timeframes]
    fig, ax = plt.subplots(figsize=(12, 6), dpi=130)
    fig.patch.set_facecolor("#050909")
    ax.set_facecolor("#050909")
    x = np.arange(len(timeframes))
    ax.bar(x - 0.18, bullish, width=0.36, color="#68e28f", alpha=0.75, label="alcista")
    ax.bar(x + 0.18, bearish, width=0.36, color="#ff6b65", alpha=0.72, label="bajista")
    ax.set_xticks(x)
    ax.set_xticklabels(timeframes, color="#d4ebe4")
    ax.tick_params(colors="#d4ebe4")
    ax.grid(axis="y", color="#203936", linewidth=0.7, alpha=0.45)
    for spine in ax.spines.values():
        spine.set_color("#284944")
    ax.set_title("Mercado general: distribucion de tendencia", color="#f2fff9", fontsize=13, pad=12)
    ax.legend(facecolor="#07100f", edgecolor="#284944", labelcolor="#d4ebe4")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return {"chart_rendered": True, "chart_path": str(path), "ohlc_rows": len(market_rows), "layer_rows": len(layers)}


def correlation_pair_from_value(value: str | None, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if text:
        parts = text.split("|")
        if len(parts) != 3:
            return None
        timeframe, asset_1, asset_2 = parts
        for row in rows:
            if str(row.get("timeframe", "")) == timeframe and pair_key(str(row.get("asset_1", "")), str(row.get("asset_2", ""))) == pair_key(asset_1, asset_2):
                return row
        return None
    options = ai_analyst_correlation_options(rows, limit=1)
    if not options:
        return None
    return correlation_pair_from_value(options[0]["value"], rows)


def correlation_package_layers(row: dict[str, Any], rolling_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeframe = str(row.get("timeframe", "")).strip()
    asset_1 = str(row.get("asset_1", "")).strip()
    asset_2 = str(row.get("asset_2", "")).strip()
    layers = [
        {"layer_type": "correlation_metric", "metric": metric, "value": row.get(metric, ""), "timeframe": timeframe, "asset_1": asset_1, "asset_2": asset_2, "is_operational": False}
        for metric in ["pearson", "spearman", "kendall", "dcor"]
    ]
    for item in rolling_rows:
        if str(item.get("timeframe", "")) == timeframe and pair_key(str(item.get("asset_1", "")), str(item.get("asset_2", ""))) == pair_key(asset_1, asset_2):
            layers.append({"layer_type": "rolling_correlation_metric", **item, "is_operational": False})
    return layers


def render_correlation_package_chart(path: Path, pair_row: dict[str, Any], returns_points: list[dict[str, Any]], layers: list[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except (ImportError, ModuleNotFoundError) as exc:
        return {"chart_rendered": False, "chart_path": str(path), "reason": f"matplotlib_unavailable:{exc}", "ohlc_rows": len(returns_points), "layer_rows": len(layers)}
    fig, (ax_scatter, ax_metrics) = plt.subplots(1, 2, figsize=(13, 5.8), dpi=130, gridspec_kw={"width_ratios": [1.45, 1]})
    fig.patch.set_facecolor("#050909")
    for ax in (ax_scatter, ax_metrics):
        ax.set_facecolor("#050909")
        ax.tick_params(colors="#d4ebe4", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#284944")
    xs = [float(point["x"]) for point in returns_points]
    ys = [float(point["y"]) for point in returns_points]
    if xs and ys:
        ax_scatter.scatter(xs, ys, s=15, color="#5ce0ca", alpha=0.60, edgecolors="#07100f", linewidths=0.35)
    ax_scatter.axhline(0, color="#284944", linewidth=0.8)
    ax_scatter.axvline(0, color="#284944", linewidth=0.8)
    ax_scatter.grid(color="#203936", linewidth=0.7, alpha=0.35)
    ax_scatter.set_title(f"{pair_row.get('asset_1', '')} vs {pair_row.get('asset_2', '')}", color="#f2fff9", fontsize=12, pad=10)
    metrics = ["pearson", "spearman", "kendall", "dcor"]
    values = [corr_float(pair_row.get(metric)) or 0.0 for metric in metrics]
    colors = ["#5ce0ca", "#68e28f", "#d7a84b", "#8f6bd1"]
    ax_metrics.barh(metrics, values, color=colors, alpha=0.82)
    ax_metrics.set_xlim(-1, 1 if max(values or [0]) <= 1 else max(values))
    ax_metrics.grid(axis="x", color="#203936", linewidth=0.7, alpha=0.35)
    ax_metrics.set_title("Coeficientes", color="#f2fff9", fontsize=12, pad=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return {"chart_rendered": True, "chart_path": str(path), "ohlc_rows": len(returns_points), "layer_rows": len(layers)}


def build_ai_source_manifest(package_dir: Path, package_slug: str, analysis_type: str, sources: dict[str, Path], fields: dict[str, Any]) -> dict[str, Any]:
    source_rows = []
    for source_id, path in sources.items():
        source_path = Path(path)
        source_rows.append({"source_id": source_id, "path": str(source_path), "exists": source_path.exists(), "sha256": _sha256_file(source_path)})
    seed = "|".join(f"{item['source_id']}={item['sha256']}" for item in source_rows)
    return {
        "package_id": package_slug,
        "package_dir": str(package_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_version": f"codex_ai_analyst_{analysis_type}_package_from_dash_v1",
        "analysis_type": analysis_type,
        "sources": source_rows,
        "package_hash_seed": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "model_called": False,
        "is_read_only": True,
        **fields,
    }


def write_ai_prompt_context(path: Path, *, analysis_type: str, title: str, source_manifest: dict[str, Any]) -> None:
    text = f"""# AI Analyst Review Context

Analysis type: `{analysis_type}`

## Selected Context

{title}

## Boundaries

- Read-only analytical context.
- Do not describe this as a trading signal.
- Do not approve execution, MT5, Telegram, or order placement.

## Sources

Package hash seed: `{source_manifest.get('package_hash_seed', '')}`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_package_manifest(
    package_dir: Path,
    *,
    package_id: str,
    analysis_type: str,
    setup_id: str,
    symbol: str = "",
    timeframe: str = "",
    setup_type: str = "",
    chart_audit: dict[str, Any],
) -> dict[str, Any]:
    files = {
        name: str(package_dir / name)
        for name in ["setup_context.json", "market_context.json", "ohlc_window.csv", "chart_layers.csv", "chart.png", "source_manifest.json", "prompt_context.md"]
    }
    return {
        "package_id": package_id,
        "package_dir": str(package_dir),
        "files": files,
        "analysis_type": analysis_type,
        "setup_id": setup_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "setup_type": setup_type or analysis_type,
        "chart_audit": chart_audit,
        "model_called": False,
        "sql_real_written": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
    }


def run_ai_analyst_market_review(*, output_dir: Path = DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR, gateway_mode: str = "fixture") -> dict[str, Any]:
    data = build_dash_data()
    market_rows = data.get("market_radar_rows", [])
    if not market_rows:
        return {"status": "blocked", "reason": "missing_market_radar_rows", "model_called": False}
    package_slug = _safe_package_slug(f"market_summary_{hashlib.sha1(str(len(market_rows)).encode()).hexdigest()[:8]}")
    package_dir = output_dir / "market_package_renderer" / "packages" / package_slug
    package_dir.mkdir(parents=True, exist_ok=True)
    layers = market_package_chart_layers(market_rows)
    chart_audit = render_market_package_chart(package_dir / "chart.png", market_rows, layers)
    source_manifest = build_ai_source_manifest(
        package_dir,
        package_slug,
        "market_summary",
        {
            "latest_manifest_json": DEFAULT_LATEST_MANIFEST_JSON,
            "market_radar_csv": DEFAULT_MARKET_RADAR_CSV,
            "ohlc_csv": ACTIVE_SQL_OHLC_CSV,
        },
        {"symbol": "MARKET", "timeframe": "multi"},
    )
    context = {
        "setup": {"analysis_type": "market_summary", "symbol": "MARKET", "timeframe": "multi", "rows": len(market_rows)},
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "safety": {"is_signal": False, "is_study_only": True, "can_execute_order": False, "would_send_to_mt5": False, "would_send_telegram_order": False, "model_called": False},
    }
    _write_json_file(package_dir / "setup_context.json", context)
    _write_json_file(package_dir / "market_context.json", {"market_radar": market_rows, "latest_manifest": load_latest_manifest_metadata(DEFAULT_LATEST_MANIFEST_JSON)})
    write_csv(package_dir / "ohlc_window.csv", market_rows)
    write_csv(package_dir / "chart_layers.csv", layers)
    _write_json_file(package_dir / "source_manifest.json", source_manifest)
    write_ai_prompt_context(package_dir / "prompt_context.md", analysis_type="market_summary", title="Mercado general multi-timeframe.", source_manifest=source_manifest)
    package_manifest = build_package_manifest(package_dir, package_id=package_slug, analysis_type="market_summary", setup_id="market_summary", symbol="MARKET", timeframe="multi", setup_type="market_summary", chart_audit=chart_audit)
    _write_json_file(package_dir / "package_manifest.json", package_manifest)
    gateway_meta = _run_ai_analyst_gateway(
        package_manifest,
        _gateway_output_dir(output_dir, "model_gateway_market", gateway_mode),
        gateway_mode=gateway_mode,
        fixture_overrides={
            "summary": "Revision fixture de mercado general generada desde el Dash; no hay llamada real a modelo.",
            "setup_reading": "Paquete de mercado validado para revisar tendencia, dispersion y volatilidad sin convertirlo en senal.",
            "confluences": ["radar de mercado exportado", "grafico de distribucion generado"],
        },
    )
    return {
        "status": "prepared",
        "analysis_type": "market_summary",
        "package_dir": str(package_dir),
        "gateway_dir": str(_gateway_output_dir(output_dir, "model_gateway_market", gateway_mode)),
        "package_id": gateway_meta.get("package_id", package_slug),
        "request_decision": gateway_meta.get("request_decision", ""),
        "output_validation_status": gateway_meta.get("output_validation_status", ""),
        "model_called": bool(gateway_meta.get("model_called", False)),
        "network_call_allowed": bool(gateway_meta.get("network_call_allowed", False)),
        "ai_review_generated": bool(gateway_meta.get("ai_review_generated", False)),
        "macro_web_research_requested": bool(gateway_meta.get("macro_web_research_requested", False)),
        "report_pdf": gateway_meta.get("report_pdf", ""),
        "chart_rendered": bool(chart_audit.get("chart_rendered")),
        "ohlc_rows": len(market_rows),
        "layer_rows": len(layers),
    }


def run_ai_analyst_correlation_review(correlation_value: str, *, output_dir: Path = DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR, gateway_mode: str = "fixture") -> dict[str, Any]:
    data = build_dash_data()
    pair_rows = data.get("correlation_pair_rows", [])
    pair_row = correlation_pair_from_value(correlation_value, pair_rows)
    if pair_row is None:
        return {"status": "blocked", "reason": "missing_correlation_pair", "model_called": False}
    timeframe = str(pair_row.get("timeframe", "")).strip()
    asset_1 = str(pair_row.get("asset_1", "")).strip()
    asset_2 = str(pair_row.get("asset_2", "")).strip()
    package_slug = _safe_package_slug(f"correlation_{timeframe}_{asset_1}_{asset_2}_{hashlib.sha1((timeframe + asset_1 + asset_2).encode()).hexdigest()[:8]}")
    package_dir = output_dir / "correlation_package_renderer" / "packages" / package_slug
    package_dir.mkdir(parents=True, exist_ok=True)
    returns_points = pair_return_points(data.get("correlation_returns_rows", []), timeframe, asset_1, asset_2, limit=420)
    layers = correlation_package_layers(pair_row, data.get("rolling_correlation_rows", []))
    chart_audit = render_correlation_package_chart(package_dir / "chart.png", pair_row, returns_points, layers)
    source_manifest = build_ai_source_manifest(
        package_dir,
        package_slug,
        "correlation",
        {
            "latest_manifest_json": DEFAULT_LATEST_MANIFEST_JSON,
            "correlation_pairs_csv": DEFAULT_CORRELATION_PAIRS_CSV,
            "rolling_correlations_csv": DEFAULT_ROLLING_CORRELATIONS_CSV,
            "correlation_returns_csv": DEFAULT_CORRELATION_RETURNS_CSV,
            "market_radar_csv": DEFAULT_MARKET_RADAR_CSV,
        },
        {"symbol": f"{asset_1}|{asset_2}", "timeframe": timeframe},
    )
    setup_context = {
        "setup": {"analysis_type": "correlation", "symbol": f"{asset_1}|{asset_2}", "timeframe": timeframe, "pair": pair_row.get("pair", ""), "metrics": {metric: pair_row.get(metric, "") for metric in ["pearson", "spearman", "kendall", "dcor"]}},
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "safety": {"is_signal": False, "is_study_only": True, "can_execute_order": False, "would_send_to_mt5": False, "would_send_telegram_order": False, "model_called": False},
    }
    _write_json_file(package_dir / "setup_context.json", setup_context)
    _write_json_file(package_dir / "market_context.json", {"market_radar": data.get("market_radar_rows", []), "correlation_pair": pair_row, "latest_manifest": load_latest_manifest_metadata(DEFAULT_LATEST_MANIFEST_JSON)})
    write_csv(package_dir / "ohlc_window.csv", returns_points)
    write_csv(package_dir / "chart_layers.csv", layers)
    _write_json_file(package_dir / "source_manifest.json", source_manifest)
    write_ai_prompt_context(package_dir / "prompt_context.md", analysis_type="correlation", title=f"Par {asset_1} / {asset_2} en {timeframe}.", source_manifest=source_manifest)
    package_manifest = build_package_manifest(package_dir, package_id=package_slug, analysis_type="correlation", setup_id=f"{timeframe}|{asset_1}|{asset_2}", symbol=f"{asset_1}|{asset_2}", timeframe=timeframe, setup_type="correlation", chart_audit=chart_audit)
    _write_json_file(package_dir / "package_manifest.json", package_manifest)
    gateway_meta = _run_ai_analyst_gateway(
        package_manifest,
        _gateway_output_dir(output_dir, "model_gateway_correlation", gateway_mode),
        gateway_mode=gateway_mode,
        fixture_overrides={
            "summary": "Revision fixture de correlacion generada desde el Dash; no hay llamada real a modelo.",
            "setup_reading": "Paquete de correlacion validado para revisar relacion estadistica y rolling sin convertirlo en senal.",
            "confluences": ["metricas de correlacion exportadas", "retornos alineados incluidos"],
        },
    )
    return {
        "status": "prepared",
        "analysis_type": "correlation",
        "package_dir": str(package_dir),
        "gateway_dir": str(_gateway_output_dir(output_dir, "model_gateway_correlation", gateway_mode)),
        "package_id": gateway_meta.get("package_id", package_slug),
        "request_decision": gateway_meta.get("request_decision", ""),
        "output_validation_status": gateway_meta.get("output_validation_status", ""),
        "model_called": bool(gateway_meta.get("model_called", False)),
        "network_call_allowed": bool(gateway_meta.get("network_call_allowed", False)),
        "ai_review_generated": bool(gateway_meta.get("ai_review_generated", False)),
        "macro_web_research_requested": bool(gateway_meta.get("macro_web_research_requested", False)),
        "report_pdf": gateway_meta.get("report_pdf", ""),
        "chart_rendered": bool(chart_audit.get("chart_rendered")),
        "ohlc_rows": len(returns_points),
        "layer_rows": len(layers),
    }


def run_ai_analyst_controlled_review(
    setup_id: str,
    *,
    output_dir: Path = DEFAULT_AI_ANALYST_DASH_OUTPUT_DIR,
    gateway_mode: str = "fixture",
) -> dict[str, Any]:
    setup_id = str(setup_id or "").strip()
    if not setup_id:
        return {"status": "blocked", "reason": "missing_setup_id", "model_called": False}

    from trading_center.codex_ai_analyst_package_renderer import build_parser as build_package_parser
    from trading_center.codex_ai_analyst_package_renderer import generate_package, write_phase_artifacts

    package_output = output_dir / "package_renderer"
    gateway_output = _gateway_output_dir(output_dir, "model_gateway", gateway_mode)
    package_args = build_package_parser().parse_args(
        [
            "--output-dir",
            str(package_output),
            "--setup-id",
            setup_id,
        ]
    )
    package_result = generate_package(package_args)
    package_meta = write_phase_artifacts(package_args, package_result)
    package_manifest = package_meta.get("package", {})
    package_dir = Path(str(package_manifest.get("package_dir", "")))
    if not package_dir.exists():
        return {"status": "blocked", "reason": "package_not_created", "model_called": False}

    gateway_meta = _run_ai_analyst_gateway(package_manifest, gateway_output, gateway_mode=gateway_mode)
    return {
        "status": "prepared",
        "package_dir": str(package_dir),
        "gateway_dir": str(gateway_output),
        "package_id": gateway_meta.get("package_id", package_manifest.get("package_id", "")),
        "request_decision": gateway_meta.get("request_decision", ""),
        "output_validation_status": gateway_meta.get("output_validation_status", ""),
        "model_called": bool(gateway_meta.get("model_called", False)),
        "network_call_allowed": bool(gateway_meta.get("network_call_allowed", False)),
        "ai_review_generated": bool(gateway_meta.get("ai_review_generated", False)),
        "macro_web_research_requested": bool(gateway_meta.get("macro_web_research_requested", False)),
        "report_pdf": gateway_meta.get("report_pdf", ""),
    }
