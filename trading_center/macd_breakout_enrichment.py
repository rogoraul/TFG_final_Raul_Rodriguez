from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtests.common.backtest_matrix_config import get_context_config
from backtests.enbolsa.GenerarIndicadores import GeneradorIndicadores
from backtests.enbolsa.market_context import AnalizadorDeContexto


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WATCHER_DIR = REPO_ROOT / "artifacts/live-signal-watcher/enbolsa_macd_breakout_v0"
DEFAULT_SNAPSHOT_CSV = DEFAULT_WATCHER_DIR / "snapshot.csv"
DEFAULT_WATCHLIST_CSV = DEFAULT_WATCHER_DIR / "watchlist.csv"
DEFAULT_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/macd_breakout_watcher_enrichment_v1_2026-06-03"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/MACD_BREAKOUT_WATCHER_ENRICHMENT_V1.md"

ENRICHED_COLUMNS = [
    "enrichment_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "setup_id",
    "side",
    "signal_state",
    "watcher_reason",
    "setup_active",
    "setup_age",
    "w1_start_time",
    "w1_end_time",
    "w1_start_price",
    "w1_end_price",
    "w2_swing_time",
    "w2_swing_price",
    "breakout_level",
    "breakout_level_type",
    "directrix_start_time",
    "directrix_end_time",
    "directrix_start_price",
    "directrix_end_price",
    "last_breakout_time",
    "bars_since_breakout",
    "macd_cross_state",
    "last_macd_cross_time",
    "bars_since_macd_cross",
    "macd_memory_bars",
    "sl_study",
    "tp1_study",
    "tp2_study",
    "invalidated",
    "late",
    "timing_state",
    "timing_priority",
    "timing_reason",
    "missing_context_reason",
    "source_snapshot",
    "source_watchlist",
    "source_ohlc",
    "is_signal",
    "is_study_only",
    "can_execute_order",
    "would_send_to_mt5",
    "would_send_telegram_order",
]

LAYER_COLUMNS = [
    "layer_id",
    "enrichment_id",
    "symbol",
    "timeframe",
    "layer_type",
    "label",
    "x0",
    "x1",
    "y0",
    "y1",
    "price",
    "timestamp",
    "style",
    "source_field",
    "is_study_only",
]

TIMING_PRIORITY = {
    "entry_review": 1,
    "macd_recent": 2,
    "breakout_recent": 3,
    "macd_pending": 4,
    "watching": 5,
    "late": 6,
    "missing_context": 7,
    "invalidated": 8,
}


@dataclass(frozen=True)
class EnrichmentConfig:
    watcher_dir: Path
    snapshot_csv: Path
    watchlist_csv: Path | None
    ohlc_csv: Path
    output_dir: Path
    doc_path: Path
    memory_bars: int = 5
    allow_missing_watchlist: bool = False
    fixture_mode: bool = False
    allow_empty: bool = False


def _resolve_path(path_value: str | Path, *, base: Path = REPO_ROOT) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (base / path).resolve()


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _safe_timestamp(value: Any) -> pd.Timestamp | pd.NaT:
    if value in ("", None):
        return pd.NaT
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return pd.NaT
    return ts if not pd.isna(ts) else pd.NaT


def _fmt_ts(value: Any) -> str:
    ts = _safe_timestamp(value)
    if pd.isna(ts):
        return ""
    return ts.isoformat(sep=" ")


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return str(value)


def _first_finite(*values: Any) -> float:
    for value in values:
        result = _safe_float(value)
        if np.isfinite(result):
            return result
    return np.nan


def load_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required CSV: {path}")
    return pd.read_csv(path)


def load_csv_optional(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_ohlc(path: Path) -> pd.DataFrame:
    frame = load_csv_required(path).copy()
    required = {"market_group", "symbol", "timeframe", "timestamp", "open", "high", "low", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"OHLC CSV missing columns: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    for col in ("open", "high", "low", "close", "spread"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


class ContextCache:
    def __init__(self, ohlc: pd.DataFrame):
        self.ohlc = ohlc
        self._cache: dict[tuple[str, str, str, str], pd.DataFrame | None] = {}

    def get(self, symbol: str, group: str, timeframe_ltf: str, timeframe_htf: str) -> pd.DataFrame | None:
        key = (symbol, group, timeframe_ltf, timeframe_htf)
        if key in self._cache:
            return self._cache[key]

        ltf = self.ohlc[(self.ohlc["symbol"] == symbol) & (self.ohlc["timeframe"] == timeframe_ltf)].copy()
        htf = self.ohlc[(self.ohlc["symbol"] == symbol) & (self.ohlc["timeframe"] == timeframe_htf)].copy()
        if ltf.empty or htf.empty:
            self._cache[key] = None
            return None

        ltf = ltf.sort_values("timestamp").set_index("timestamp")
        htf = htf.sort_values("timestamp").set_index("timestamp")
        for frame in (ltf, htf):
            for col in ("open", "high", "low", "close"):
                frame[col] = pd.to_numeric(frame[col], errors="coerce")

        try:
            indicators = GeneradorIndicadores(ma_type="wma")
            ltf = indicators.aplicar_todo(ltf)
            htf = indicators.aplicar_todo(htf)
            context = AnalizadorDeContexto(**get_context_config(group_name=group, timeframe_ltf=timeframe_ltf))
            ltf = context.procesar_contexto_completo(ltf)
            ltf = context.sincronizar_tendencia_htf(ltf, htf, suffix=f"_{timeframe_htf}")
        except Exception:
            self._cache[key] = None
            return None
        self._cache[key] = ltf
        return ltf


def _row_prefix(side: str) -> str:
    return "LONG" if str(side).upper() == "BUY" else "SHORT"


def _find_change_start(series: pd.Series, pos: int, current_value: float) -> int | None:
    if pos < 0 or np.isnan(current_value):
        return None
    start = pos
    while start > 0:
        prev = _safe_float(series.iloc[start - 1])
        now = _safe_float(series.iloc[start])
        if np.isnan(prev) or np.isnan(now) or abs(prev - current_value) > 1e-9 or abs(now - current_value) > 1e-9:
            break
        start -= 1
    return start


def _latest_true_pos(series: pd.Series, start_pos: int, end_pos: int) -> int | None:
    if start_pos > end_pos:
        return None
    subset = series.iloc[start_pos : end_pos + 1]
    true_positions = np.where(subset.fillna(False).astype(bool).to_numpy())[0]
    if len(true_positions) == 0:
        return None
    return start_pos + int(true_positions[-1])


def _latest_true_pos_before(series: pd.Series, start_pos: int, end_pos: int) -> int | None:
    return _latest_true_pos(series, start_pos, end_pos)


def _compute_breakout_trendline(
    trendline_values: pd.Series,
    anchor_pos: int,
    breakout_pos: int,
    direction: int,
    projection_pos: int | None = None,
) -> tuple[float, float, float]:
    if breakout_pos <= anchor_pos:
        return np.nan, np.nan, np.nan
    window = trendline_values.iloc[anchor_pos:breakout_pos].astype(float).to_numpy()
    n = len(window)
    if n < 3 or np.isnan(window).any():
        return np.nan, np.nan, np.nan
    x = np.arange(n, dtype=float)
    sum_x = float(x.sum())
    sum_x2 = float((x * x).sum())
    sum_y = float(window.sum())
    sum_xy = float((x * window).sum())
    denom = (n * sum_x2) - (sum_x * sum_x)
    if abs(denom) < 1e-12:
        return np.nan, np.nan, np.nan
    slope = ((n * sum_xy) - (sum_x * sum_y)) / denom
    intercept = (sum_y - (slope * sum_x)) / n
    if direction == 1 and slope >= 0:
        return np.nan, np.nan, np.nan
    if direction == -1 and slope <= 0:
        return np.nan, np.nan, np.nan
    projection_x = n if projection_pos is None else max(n, projection_pos - anchor_pos)
    return (
        float(intercept),
        float(intercept + (slope * n)),
        float(intercept + (slope * projection_x)),
    )


def _compute_breakout_level(trendline_values: pd.Series, anchor_pos: int, breakout_pos: int, direction: int) -> float:
    _, breakout_level, _ = _compute_breakout_trendline(trendline_values, anchor_pos, breakout_pos, direction)
    return breakout_level


def _valid_line_points(*values: Any) -> bool:
    return all(np.isfinite(_safe_float(value)) for value in values)


def _directrix_style(record: Mapping[str, Any]) -> tuple[str, str]:
    side = str(record.get("side", "")).strip().upper()
    source = "highs" if side == "BUY" else "lows" if side == "SELL" else "high/low"
    if str(record.get("timing_state", "")).strip() == "late":
        return f"Reg W2 {source} tardia", "dot:#8aa8a3"
    return f"Reg W2 {source} estudio", "dash:#5ce0ca"


def _timing_from_fields(
    *,
    invalidated: bool,
    missing_context_reason: str,
    breakout_pos: int | None,
    macd_cross_pos: int | None,
    current_pos: int,
    memory_bars: int,
    raw_condition_ready: bool,
    setup_active: bool,
    breakout_level: float,
    current_close: float,
) -> tuple[str, int, str, bool]:
    if invalidated:
        return "invalidated", TIMING_PRIORITY["invalidated"], "setup invalidado; no revisar como oportunidad vigente", False
    if missing_context_reason:
        return "missing_context", TIMING_PRIORITY["missing_context"], f"faltan datos: {missing_context_reason}", False

    bars_since_breakout = current_pos - breakout_pos if breakout_pos is not None else None
    bars_since_macd = current_pos - macd_cross_pos if macd_cross_pos is not None else None
    breakout_recent = bars_since_breakout is not None and bars_since_breakout <= memory_bars
    macd_recent = bars_since_macd is not None and bars_since_macd <= memory_bars
    late = False
    if breakout_pos is not None and not breakout_recent:
        late = True
    if macd_cross_pos is not None and not macd_recent:
        late = True

    if breakout_recent and macd_recent and not late:
        return "entry_review", TIMING_PRIORITY["entry_review"], "ruptura y cruce MACD recientes dentro de memoria; revisar el grafico ahora", False
    if late:
        return "late", TIMING_PRIORITY["late"], "hay confirmaciones antiguas fuera de la ventana de memoria", True
    if breakout_recent:
        return "breakout_recent", TIMING_PRIORITY["breakout_recent"], "ruptura reciente detectada; falta confirmar MACD reciente", False
    if macd_recent:
        return "macd_recent", TIMING_PRIORITY["macd_recent"], "cruce MACD reciente detectado; falta confirmar la ruptura reciente", False
    if setup_active and not raw_condition_ready:
        if np.isfinite(breakout_level) and np.isfinite(current_close):
            return "macd_pending", TIMING_PRIORITY["macd_pending"], "setup activo; falta ruptura o cruce MACD dentro de memoria", False
        return "watching", TIMING_PRIORITY["watching"], "setup activo sin confirmacion reciente suficiente", False
    return "watching", TIMING_PRIORITY["watching"], "setup activo sin timing inmediato", False


def _record_to_layer(
    enrichment_id: str,
    symbol: str,
    timeframe: str,
    layer_type: str,
    label: str,
    *,
    x0: Any = "",
    x1: Any = "",
    y0: Any = np.nan,
    y1: Any = np.nan,
    price: Any = np.nan,
    timestamp: Any = "",
    style: str = "",
    source_field: str = "",
) -> dict[str, Any]:
    return {
        "layer_id": f"{enrichment_id}|{layer_type}",
        "enrichment_id": enrichment_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "layer_type": layer_type,
        "label": label,
        "x0": _fmt_ts(x0),
        "x1": _fmt_ts(x1),
        "y0": y0,
        "y1": y1,
        "price": price,
        "timestamp": _fmt_ts(timestamp),
        "style": style,
        "source_field": source_field,
        "is_study_only": True,
    }


def _build_layers(record: Mapping[str, Any], current_close: float) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    enrichment_id = str(record["enrichment_id"])
    symbol = str(record["symbol"])
    timeframe = str(record["timeframe"])
    if record.get("w1_start_time") and record.get("w1_end_time") and np.isfinite(_safe_float(record.get("w1_start_price"))) and np.isfinite(_safe_float(record.get("w1_end_price"))):
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_w1_leg",
                "W1 estudio",
                x0=record["w1_start_time"],
                x1=record["w1_end_time"],
                y0=_safe_float(record["w1_start_price"]),
                y1=_safe_float(record["w1_end_price"]),
                style="line:#58e6d3",
                source_field="w1_start_price|w1_end_price",
            )
        )
    if record.get("w1_end_time") and record.get("w2_swing_time") and np.isfinite(_safe_float(record.get("w1_end_price"))) and np.isfinite(_safe_float(record.get("w2_swing_price"))):
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_w2_retracement",
                "W2 estudio",
                x0=record["w1_end_time"],
                x1=record["w2_swing_time"],
                y0=_safe_float(record["w1_end_price"]),
                y1=_safe_float(record["w2_swing_price"]),
                style="line:#f4b740",
                source_field="w1_end_price|w2_swing_price",
            )
        )
    if (
        record.get("directrix_start_time")
        and record.get("directrix_end_time")
        and _valid_line_points(record.get("directrix_start_price"), record.get("directrix_end_price"))
    ):
        label, style = _directrix_style(record)
        side = str(record.get("side", "")).strip().upper()
        source_field = "w2_high_regression_projected" if side == "BUY" else "w2_low_regression_projected" if side == "SELL" else "w2_high_low_regression_projected"
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_w2_directrix",
                label,
                x0=record["directrix_start_time"],
                x1=record["directrix_end_time"],
                y0=_safe_float(record["directrix_start_price"]),
                y1=_safe_float(record["directrix_end_price"]),
                style=style,
                source_field=source_field,
            )
        )
    breakout_level = _safe_float(record.get("breakout_level"))
    if record.get("w1_end_time") and record.get("generated_at") and np.isfinite(breakout_level):
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_breakout_level",
                "Ruptura estudio",
                x0=record["w1_end_time"],
                x1=record["generated_at"],
                y0=breakout_level,
                y1=breakout_level,
                price=breakout_level,
                style="dash:#ffd166",
                source_field="breakout_level",
            )
        )
    for field_name, layer_type, label, style in (
        ("sl_study", "macd_sl_study", "SL estudio", "dot:#ff6b6b"),
        ("tp1_study", "macd_tp1_study", "TP1 estudio", "dot:#75d7ff"),
        ("tp2_study", "macd_tp2_study", "TP2 estudio", "dot:#75d7ff"),
    ):
        value = _safe_float(record.get(field_name))
        if np.isfinite(value):
            layers.append(
                _record_to_layer(
                    enrichment_id,
                    symbol,
                    timeframe,
                    layer_type,
                    label,
                    x0=record.get("w1_end_time") or record.get("generated_at"),
                    x1=record.get("generated_at"),
                    y0=value,
                    y1=value,
                    price=value,
                    style=style,
                    source_field=field_name,
                )
            )
    if record.get("last_macd_cross_time"):
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_cross_marker",
                "Cruce MACD",
                price=current_close,
                timestamp=record["last_macd_cross_time"],
                style="marker:#ffe082",
                source_field="last_macd_cross_time",
            )
        )
    if record.get("last_breakout_time") and np.isfinite(breakout_level):
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_recent_breakout_marker",
                "Ruptura reciente",
                price=breakout_level,
                timestamp=record["last_breakout_time"],
                style="marker:#f6c90e",
                source_field="last_breakout_time|breakout_level",
            )
        )
    if np.isfinite(current_close):
        layers.append(
            _record_to_layer(
                enrichment_id,
                symbol,
                timeframe,
                "macd_current_price_marker",
                "Precio actual",
                price=current_close,
                timestamp=record.get("generated_at"),
                style="marker:#f7f7f7",
                source_field="close",
            )
        )
    return layers


def _enrich_snapshot_row(
    row: Mapping[str, Any],
    *,
    generated_at: str,
    config: EnrichmentConfig,
    context_cache: ContextCache,
    watchlist_lookup: set[tuple[str, str, str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    group = str(row.get("Group") or row.get("market_group") or "")
    symbol = str(row.get("symbol") or "")
    timeframe = str(row.get("timeframe_ltf") or "H1")
    timeframe_htf = str(row.get("timeframe_htf") or "H4")
    side = str(row.get("side") or "")
    prefix = _row_prefix(side)
    signal_time = _safe_timestamp(row.get("timestamp"))
    signal_state = str(row.get("signal_state") or "")
    watcher_reason = str(row.get("reason") or "")
    setup_id = _safe_int(row.get("setup_id"))
    setup_age = _safe_int(row.get("setup_age"))
    setup_active = _safe_bool(row.get("setup_active"))
    raw_condition_ready = _safe_bool(row.get("raw_condition_ready"))
    enrichment_id = f"macd_breakout_enrichment_v1|{symbol}|{timeframe}|{side}|{setup_id}"

    result = {
        "enrichment_id": enrichment_id,
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": group,
        "timeframe": timeframe,
        "setup_id": setup_id,
        "side": side,
        "signal_state": signal_state,
        "watcher_reason": watcher_reason,
        "setup_active": setup_active,
        "setup_age": setup_age,
        "w1_start_time": "",
        "w1_end_time": "",
        "w1_start_price": np.nan,
        "w1_end_price": np.nan,
        "w2_swing_time": "",
        "w2_swing_price": _safe_float(row.get("w2_swing")),
        "breakout_level": np.nan,
        "breakout_level_type": "",
        "directrix_start_time": "",
        "directrix_end_time": "",
        "directrix_start_price": np.nan,
        "directrix_end_price": np.nan,
        "last_breakout_time": "",
        "bars_since_breakout": np.nan,
        "macd_cross_state": "",
        "last_macd_cross_time": "",
        "bars_since_macd_cross": np.nan,
        "macd_memory_bars": int(config.memory_bars),
        "sl_study": _first_finite(row.get("sl"), row.get("w2_swing")),
        "tp1_study": _first_finite(row.get("tp1"), row.get("target_1_0")),
        "tp2_study": _first_finite(row.get("tp2"), row.get("target_1_618")),
        "invalidated": watcher_reason == "setup_invalidated",
        "late": False,
        "timing_state": "",
        "timing_priority": np.nan,
        "timing_reason": "",
        "missing_context_reason": "",
        "source_snapshot": str(config.snapshot_csv),
        "source_watchlist": str(config.watchlist_csv) if config.watchlist_csv else "",
        "source_ohlc": str(config.ohlc_csv),
        "is_signal": False,
        "is_study_only": True,
        "can_execute_order": False,
        "would_send_to_mt5": False,
        "would_send_telegram_order": False,
    }
    cross_audit = {
        "enrichment_id": enrichment_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "last_macd_cross_time": "",
        "bars_since_macd_cross": np.nan,
        "macd_cross_state": "",
        "reconstruction_status": "missing_context",
    }
    breakout_audit = {
        "enrichment_id": enrichment_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "last_breakout_time": "",
        "bars_since_breakout": np.nan,
        "breakout_level": np.nan,
        "breakout_level_type": "",
        "reconstruction_status": "missing_context",
    }

    context_frame = context_cache.get(symbol, group, timeframe, timeframe_htf)
    if context_frame is None:
        result["missing_context_reason"] = "missing_ohlc_context"
        state, priority, reason, late = _timing_from_fields(
            invalidated=result["invalidated"],
            missing_context_reason=result["missing_context_reason"],
            breakout_pos=None,
            macd_cross_pos=None,
            current_pos=0,
            memory_bars=config.memory_bars,
            raw_condition_ready=raw_condition_ready,
            setup_active=setup_active,
            breakout_level=np.nan,
            current_close=np.nan,
        )
        result["timing_state"] = state
        result["timing_priority"] = priority
        result["timing_reason"] = reason
        result["late"] = late
        result["macd_cross_state"] = "missing"
        return result, _build_layers(result, np.nan), cross_audit, breakout_audit

    if pd.isna(signal_time) or signal_time not in context_frame.index:
        result["missing_context_reason"] = "timestamp_not_found_in_ohlc"
        state, priority, reason, late = _timing_from_fields(
            invalidated=result["invalidated"],
            missing_context_reason=result["missing_context_reason"],
            breakout_pos=None,
            macd_cross_pos=None,
            current_pos=max(len(context_frame) - 1, 0),
            memory_bars=config.memory_bars,
            raw_condition_ready=raw_condition_ready,
            setup_active=setup_active,
            breakout_level=np.nan,
            current_close=np.nan,
        )
        result["timing_state"] = state
        result["timing_priority"] = priority
        result["timing_reason"] = reason
        result["late"] = late
        result["macd_cross_state"] = "missing"
        return result, _build_layers(result, np.nan), cross_audit, breakout_audit

    current_pos = int(context_frame.index.get_loc(signal_time))
    current = context_frame.iloc[current_pos]
    current_close = _safe_float(current.get("close"))

    setup_active_calc = _safe_bool(current.get(f"{prefix}_SETUP_ACTIVE"))
    setup_age_calc = _safe_int(current.get(f"{prefix}_SETUP_AGE"), setup_age)
    w1_bars = _safe_int(current.get(f"{prefix}_W1_BARS"))
    result["setup_active"] = setup_active
    result["setup_age"] = setup_age
    if np.isnan(result["sl_study"]):
        result["sl_study"] = _safe_float(row.get("w2_swing"))

    w2_swing_calc = _safe_float(current.get(f"{prefix}_W2_SWING_PRICE"))
    if np.isfinite(w2_swing_calc):
        result["w2_swing_price"] = w2_swing_calc
    if watcher_reason == "missing_w2_swing" or not np.isfinite(_safe_float(result["w2_swing_price"])):
        result["missing_context_reason"] = "missing_w2_swing"

    result["invalidated"] = bool(result["invalidated"] or _safe_bool(current.get(f"{prefix}_W2_INVALIDATED")))

    created_pos = current_pos - setup_age_calc if setup_age_calc >= 0 else current_pos
    if created_pos < 0:
        created_pos = 0
    w1_start_pos = created_pos - w1_bars if w1_bars >= 0 else created_pos
    if w1_start_pos < 0:
        w1_start_pos = 0

    w1_start_price = _safe_float(current.get(f"{prefix}_W1_START_PRICE"))
    w1_end_price = _safe_float(current.get(f"{prefix}_W1_END_PRICE"))
    result["w1_start_price"] = w1_start_price
    result["w1_end_price"] = w1_end_price
    if np.isfinite(w1_start_price) and created_pos < len(context_frame.index):
        result["w1_start_time"] = _fmt_ts(context_frame.index[w1_start_pos])
    if np.isfinite(w1_end_price) and created_pos < len(context_frame.index):
        result["w1_end_time"] = _fmt_ts(context_frame.index[created_pos])

    w2_series = context_frame[f"{prefix}_W2_SWING_PRICE"]
    w2_swing_pos = _find_change_start(w2_series, current_pos, _safe_float(result["w2_swing_price"]))
    if w2_swing_pos is not None:
        result["w2_swing_time"] = _fmt_ts(context_frame.index[w2_swing_pos])

    macd_col = "MACD_CROSS_LONG" if prefix == "LONG" else "MACD_CROSS_SHORT"
    macd_pos = _latest_true_pos_before(context_frame[macd_col], created_pos, current_pos)
    if macd_pos is not None:
        result["last_macd_cross_time"] = _fmt_ts(context_frame.index[macd_pos])
        result["bars_since_macd_cross"] = current_pos - macd_pos
        result["macd_cross_state"] = "recent" if (current_pos - macd_pos) <= config.memory_bars else "stale"
        cross_audit.update(
            {
                "last_macd_cross_time": result["last_macd_cross_time"],
                "bars_since_macd_cross": result["bars_since_macd_cross"],
                "macd_cross_state": result["macd_cross_state"],
                "reconstruction_status": "reconstructed",
            }
        )
    elif (symbol, side, str(setup_id), timeframe) in watchlist_lookup:
        result["macd_cross_state"] = "pending"
        cross_audit["reconstruction_status"] = "watchlist_pending"
    else:
        result["macd_cross_state"] = "missing"

    breakout_col = f"{prefix}_W2_TRENDLINE_BROKEN"
    breakout_pos = _latest_true_pos_before(context_frame[breakout_col], created_pos, current_pos)
    if breakout_pos is not None:
        trendline_source = context_frame["high"] if prefix == "LONG" else context_frame["low"]
        directrix_start, breakout_level, directrix_projection = _compute_breakout_trendline(
            trendline_source,
            created_pos,
            breakout_pos,
            1 if prefix == "LONG" else -1,
            projection_pos=current_pos,
        )
        result["breakout_level"] = breakout_level
        result["breakout_level_type"] = "regression_w2_high_low_close_confirmed"
        result["last_breakout_time"] = _fmt_ts(context_frame.index[breakout_pos])
        result["bars_since_breakout"] = current_pos - breakout_pos
        if np.isfinite(directrix_start) and np.isfinite(directrix_projection):
            result["directrix_start_time"] = _fmt_ts(context_frame.index[created_pos])
            result["directrix_end_time"] = _fmt_ts(context_frame.index[current_pos])
            result["directrix_start_price"] = directrix_start
            result["directrix_end_price"] = directrix_projection
        breakout_audit.update(
            {
                "last_breakout_time": result["last_breakout_time"],
                "bars_since_breakout": result["bars_since_breakout"],
                "breakout_level": breakout_level,
                "breakout_level_type": result["breakout_level_type"],
                "reconstruction_status": "reconstructed",
            }
        )
    elif raw_condition_ready:
        breakout_audit["reconstruction_status"] = "raw_ready_without_breakout_timestamp"
    else:
        breakout_audit["reconstruction_status"] = "not_detected"

    if np.isnan(result["sl_study"]):
        result["sl_study"] = _safe_float(result["w2_swing_price"])
    if np.isnan(result["sl_study"]):
        result["sl_study"] = w1_start_price

    if not result["missing_context_reason"] and not setup_active_calc and not setup_active:
        result["missing_context_reason"] = "inactive_in_reconstruction"
    if not result["missing_context_reason"] and (not np.isfinite(w1_start_price) or not np.isfinite(w1_end_price)):
        result["missing_context_reason"] = "missing_w1_structure"

    timing_state, timing_priority, timing_reason, late = _timing_from_fields(
        invalidated=result["invalidated"],
        missing_context_reason=result["missing_context_reason"],
        breakout_pos=breakout_pos,
        macd_cross_pos=macd_pos,
        current_pos=current_pos,
        memory_bars=config.memory_bars,
        raw_condition_ready=raw_condition_ready,
        setup_active=setup_active_calc or setup_active,
        breakout_level=_safe_float(result["breakout_level"]),
        current_close=current_close,
    )
    result["timing_state"] = timing_state
    result["timing_priority"] = timing_priority
    result["timing_reason"] = timing_reason
    result["late"] = late

    layers = _build_layers(result, current_close)
    return result, layers, cross_audit, breakout_audit


def build_outputs(config: EnrichmentConfig) -> dict[str, Any]:
    snapshot = load_csv_required(config.snapshot_csv)
    watchlist = load_csv_optional(config.watchlist_csv)
    if snapshot.empty and not config.allow_empty:
        raise ValueError("Snapshot CSV is empty and --allow-empty was not provided.")

    ohlc = load_ohlc(config.ohlc_csv)
    generated_at = datetime.now(timezone.utc).isoformat()
    context_cache = ContextCache(ohlc)
    watchlist_lookup = {
        (str(row.get("symbol") or ""), str(row.get("side") or ""), str(_safe_int(row.get("setup_id"))), str(row.get("timeframe_ltf") or ""))
        for _, row in watchlist.iterrows()
    }

    enriched_rows: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    macd_cross_audit: list[dict[str, Any]] = []
    breakout_audit: list[dict[str, Any]] = []

    for _, row in snapshot.iterrows():
        enriched, layer_rows, cross_row, breakout_row = _enrich_snapshot_row(
            row.to_dict(),
            generated_at=generated_at,
            config=config,
            context_cache=context_cache,
            watchlist_lookup=watchlist_lookup,
        )
        enriched_rows.append(enriched)
        layers.extend(layer_rows)
        macd_cross_audit.append(cross_row)
        breakout_audit.append(breakout_row)

    enriched_frame = pd.DataFrame(enriched_rows).reindex(columns=ENRICHED_COLUMNS)
    layers_frame = pd.DataFrame(layers).reindex(columns=LAYER_COLUMNS)

    source_audit = pd.DataFrame(
        [
            {"source_id": "snapshot_csv", "path": str(config.snapshot_csv), "exists": config.snapshot_csv.exists(), "rows": int(len(snapshot)), "required": True},
            {"source_id": "watchlist_csv", "path": str(config.watchlist_csv) if config.watchlist_csv else "", "exists": bool(config.watchlist_csv and config.watchlist_csv.exists()), "rows": int(len(watchlist)), "required": not config.allow_missing_watchlist},
            {"source_id": "ohlc_csv", "path": str(config.ohlc_csv), "exists": config.ohlc_csv.exists(), "rows": int(len(ohlc)), "required": True},
        ]
    )

    field_coverage_rows = []
    for field in (
        "w1_start_time",
        "w1_end_time",
        "w1_start_price",
        "w1_end_price",
        "w2_swing_time",
        "w2_swing_price",
        "breakout_level",
        "directrix_start_price",
        "directrix_end_price",
        "last_breakout_time",
        "last_macd_cross_time",
        "sl_study",
        "tp1_study",
        "tp2_study",
    ):
        if field in enriched_frame.columns:
            series = enriched_frame[field]
            non_null = int(series.mask(series.eq(""), np.nan).notna().sum())
        else:
            non_null = 0
        field_coverage_rows.append({"field_name": field, "non_null_rows": non_null, "total_rows": int(len(enriched_frame)), "coverage_pct": round((non_null / len(enriched_frame)) * 100.0, 2) if len(enriched_frame) else 0.0})
    field_coverage = pd.DataFrame(field_coverage_rows)

    timing_state_audit = (
        enriched_frame.groupby("timing_state", dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["rows", "timing_state"], ascending=[False, True])
        if not enriched_frame.empty
        else pd.DataFrame(columns=["timing_state", "rows"])
    )

    chart_layer_audit = (
        layers_frame.groupby("layer_type", dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["rows", "layer_type"], ascending=[False, True])
        if not layers_frame.empty
        else pd.DataFrame(columns=["layer_type", "rows"])
    )

    safety_flags_audit = pd.DataFrame(
        [
            {"flag": "is_signal_any_true", "value": bool(enriched_frame["is_signal"].fillna(False).any()) if not enriched_frame.empty else False},
            {"flag": "is_study_only_all_true", "value": bool(enriched_frame["is_study_only"].fillna(False).all()) if not enriched_frame.empty else True},
            {"flag": "can_execute_order_any_true", "value": bool(enriched_frame["can_execute_order"].fillna(False).any()) if not enriched_frame.empty else False},
            {"flag": "would_send_to_mt5_any_true", "value": bool(enriched_frame["would_send_to_mt5"].fillna(False).any()) if not enriched_frame.empty else False},
            {"flag": "would_send_telegram_order_any_true", "value": bool(enriched_frame["would_send_telegram_order"].fillna(False).any()) if not enriched_frame.empty else False},
        ]
    )

    issue_rows = []
    for reason, count in (
        enriched_frame["missing_context_reason"].replace("", np.nan).dropna().value_counts().to_dict().items()
        if not enriched_frame.empty
        else {}
    ):
        issue_rows.append({"issue_id": f"missing_context::{reason}", "severity": "medium", "issue": reason, "count": int(count), "status": "open"})
    if not issue_rows:
        issue_rows.append({"issue_id": "no_open_issues", "severity": "low", "issue": "no additional issues detected beyond documented limitations", "count": 0, "status": "observed"})
    issues = pd.DataFrame(issue_rows)

    timing_distribution = {str(row["timing_state"]): int(row["rows"]) for _, row in timing_state_audit.iterrows()}
    run_meta = {
        "generated_at": generated_at,
        "artifact_id": "macd_breakout_watcher_enrichment_v1_2026-06-03",
        "decision": "macd_breakout_watcher_enrichment_v1_ready_for_screener_integration",
        "memory_bars": int(config.memory_bars),
        "fixture_mode": bool(config.fixture_mode),
        "allow_missing_watchlist": bool(config.allow_missing_watchlist),
        "allow_empty": bool(config.allow_empty),
        "enriched_rows": int(len(enriched_frame)),
        "chart_layers_count": int(len(layers_frame)),
        "missing_context_count": int((enriched_frame["timing_state"] == "missing_context").sum()) if not enriched_frame.empty else 0,
        "entry_review_count": int((enriched_frame["timing_state"] == "entry_review").sum()) if not enriched_frame.empty else 0,
        "late_count": int((enriched_frame["timing_state"] == "late").sum()) if not enriched_frame.empty else 0,
        "invalidated_count": int((enriched_frame["timing_state"] == "invalidated").sum()) if not enriched_frame.empty else 0,
        "timing_state_distribution": timing_distribution,
        "macd_breakout_strategy_modified": False,
        "fib_limit_modified": False,
        "backtests_executed": False,
        "sql_real_written": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "is_signal_any_true": bool(enriched_frame["is_signal"].fillna(False).any()) if not enriched_frame.empty else False,
        "can_execute_order_any_true": bool(enriched_frame["can_execute_order"].fillna(False).any()) if not enriched_frame.empty else False,
        "is_study_only_all_true": bool(enriched_frame["is_study_only"].fillna(False).all()) if not enriched_frame.empty else True,
        "would_send_to_mt5_any_true": bool(enriched_frame["would_send_to_mt5"].fillna(False).any()) if not enriched_frame.empty else False,
        "would_send_telegram_order_any_true": bool(enriched_frame["would_send_telegram_order"].fillna(False).any()) if not enriched_frame.empty else False,
        "watcher_dir": str(config.watcher_dir),
        "snapshot_csv": str(config.snapshot_csv),
        "watchlist_csv": str(config.watchlist_csv) if config.watchlist_csv else "",
        "ohlc_csv": str(config.ohlc_csv),
        "notes": [
            "artifact_first_read_only",
            "no_strategy_rules_modified",
            "breakout_level_reconstructed_from_internal_trendline_logic_when_possible",
            "directrix_visual_layer_reconstructed_from_same_breakout_trendline_logic",
            "watcher_setup_id_preserved_as_identity",
        ],
    }
    return {
        "enriched": enriched_frame,
        "layers": layers_frame,
        "source_audit": source_audit,
        "field_coverage": field_coverage,
        "timing_state_audit": timing_state_audit,
        "macd_cross_audit": pd.DataFrame(macd_cross_audit),
        "breakout_audit": pd.DataFrame(breakout_audit),
        "chart_layer_audit": chart_layer_audit,
        "safety_flags_audit": safety_flags_audit,
        "issues": issues,
        "run_meta": run_meta,
    }


def render_report(run_meta: Mapping[str, Any], field_coverage: pd.DataFrame) -> str:
    return f"""# MACD Breakout Watcher Enrichment V1

Fecha: {str(run_meta["generated_at"])[:10]}

Decision: `{run_meta["decision"]}`.

## Resultado

Se implementa `macd_breakout_watcher_enrichment_v1` como capa artifact-first
entre el watcher ENBOLSA y el futuro timing/capas del Screener. La fase no
modifica la estrategia, no ejecuta backtests y mantiene todas las flags
fail-closed.

## Conteos

- enriched_rows={run_meta["enriched_rows"]}
- chart_layers_count={run_meta["chart_layers_count"]}
- missing_context_count={run_meta["missing_context_count"]}
- entry_review_count={run_meta["entry_review_count"]}
- late_count={run_meta["late_count"]}
- invalidated_count={run_meta["invalidated_count"]}

## Cobertura orientativa

- w1_start_time={int(field_coverage.loc[field_coverage["field_name"] == "w1_start_time", "non_null_rows"].iloc[0]) if not field_coverage.empty else 0}
- w2_swing_time={int(field_coverage.loc[field_coverage["field_name"] == "w2_swing_time", "non_null_rows"].iloc[0]) if not field_coverage.empty else 0}
- breakout_level={int(field_coverage.loc[field_coverage["field_name"] == "breakout_level", "non_null_rows"].iloc[0]) if not field_coverage.empty else 0}
- last_breakout_time={int(field_coverage.loc[field_coverage["field_name"] == "last_breakout_time", "non_null_rows"].iloc[0]) if not field_coverage.empty else 0}
- last_macd_cross_time={int(field_coverage.loc[field_coverage["field_name"] == "last_macd_cross_time", "non_null_rows"].iloc[0]) if not field_coverage.empty else 0}

## Lectura visual

- `breakout_level` y `last_breakout_time` mantienen el punto real de ruptura
  reconstruido con la logica interna de ENBOLSA.
- La capa `macd_w2_directrix` proyecta esa misma regresion hasta la ultima vela
  del snapshot para que el modal sea legible. Es regresion sobre `highs` en
  largos y sobre `lows` en cortos; no es una directriz manual que una mechas
  exactas. Esta proyeccion es visual y study-only; no modifica el disparador, no
  genera senal y no habilita operativa.
- Si el timing queda `late`, la linea se muestra como `Reg W2 highs/lows tardia`
  para separar una ruptura antigua de una revision fresca.

## Seguridad

- `strategy_modified={str(run_meta["macd_breakout_strategy_modified"]).lower()}`
- `fib_limit_modified={str(run_meta["fib_limit_modified"]).lower()}`
- `backtests_executed={str(run_meta["backtests_executed"]).lower()}`
- `sql_real_written={str(run_meta["sql_real_written"]).lower()}`
- `db_connected={str(run_meta["db_connected"]).lower()}`
- `mt5_connected={str(run_meta["mt5_connected"]).lower()}`
- `telegram_connected={str(run_meta["telegram_connected"]).lower()}`
- `orders_sent={run_meta["orders_sent"]}`
- `signals_generated={str(run_meta["signals_generated"]).lower()}`
"""


def write_outputs(config: EnrichmentConfig, result: Mapping[str, Any]) -> None:
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    enriched = result["enriched"].copy()
    layers = result["layers"].copy()
    enriched.to_csv(output_dir / "macd_breakout_enriched_setups.csv", index=False)
    (output_dir / "macd_breakout_enriched_setups.json").write_text(
        json.dumps(enriched.to_dict(orient="records"), indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    layers.to_csv(output_dir / "macd_breakout_chart_layers.csv", index=False)
    result["source_audit"].to_csv(tables_dir / "source_artifact_audit.csv", index=False)
    result["field_coverage"].to_csv(tables_dir / "field_coverage_audit.csv", index=False)
    result["timing_state_audit"].to_csv(tables_dir / "timing_state_audit.csv", index=False)
    result["macd_cross_audit"].to_csv(tables_dir / "macd_cross_reconstruction_audit.csv", index=False)
    result["breakout_audit"].to_csv(tables_dir / "breakout_reconstruction_audit.csv", index=False)
    result["chart_layer_audit"].to_csv(tables_dir / "chart_layer_audit.csv", index=False)
    result["safety_flags_audit"].to_csv(tables_dir / "safety_flags_audit.csv", index=False)
    result["issues"].to_csv(tables_dir / "issues_or_risks.csv", index=False)
    (output_dir / "run_meta.json").write_text(json.dumps(result["run_meta"], indent=2, ensure_ascii=False), encoding="utf-8")

    report = render_report(result["run_meta"], result["field_coverage"])
    (output_dir / "MACD_BREAKOUT_WATCHER_ENRICHMENT_V1.md").write_text(report, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(report, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build artifact-first macd_breakout watcher enrichment.")
    parser.add_argument("--watcher-dir", default=str(DEFAULT_WATCHER_DIR))
    parser.add_argument("--snapshot-csv", default="")
    parser.add_argument("--watchlist-csv", default="")
    parser.add_argument("--ohlc-csv", default=str(DEFAULT_OHLC_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--memory-bars", type=int, default=5)
    parser.add_argument("--allow-missing-watchlist", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> EnrichmentConfig:
    watcher_dir = _resolve_path(args.watcher_dir)
    snapshot_csv = _resolve_path(args.snapshot_csv) if args.snapshot_csv else watcher_dir / "snapshot.csv"
    watchlist_csv = _resolve_path(args.watchlist_csv) if args.watchlist_csv else watcher_dir / "watchlist.csv"
    if not watchlist_csv.exists() and args.allow_missing_watchlist:
        watchlist_csv = None
    return EnrichmentConfig(
        watcher_dir=watcher_dir,
        snapshot_csv=snapshot_csv,
        watchlist_csv=watchlist_csv,
        ohlc_csv=_resolve_path(args.ohlc_csv),
        output_dir=_resolve_path(args.output_dir),
        doc_path=_resolve_path(args.doc_path),
        memory_bars=max(int(args.memory_bars), 1),
        allow_missing_watchlist=bool(args.allow_missing_watchlist),
        fixture_mode=bool(args.fixture_mode),
        allow_empty=bool(args.allow_empty),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_config(args)
    result = build_outputs(config)
    write_outputs(config, result)
    print(
        json.dumps(
            {
                "decision": result["run_meta"]["decision"],
                "enriched_rows": result["run_meta"]["enriched_rows"],
                "chart_layers_count": result["run_meta"]["chart_layers_count"],
                "timing_state_distribution": result["run_meta"]["timing_state_distribution"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
