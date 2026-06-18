from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.enbolsa.GenerarIndicadores import GeneradorIndicadores
from backtests.enbolsa.market_context import AnalizadorDeContexto
from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "trading_center_market_radar_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/trading_center_market_radar_v1_2026-05-30"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TRADING_CENTER_MARKET_RADAR_V1.md"
DEFAULT_H1_CONTEXT_CSV = (
    REPO_ROOT
    / "artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/"
    / "diagnostic_phase2_4_h1_h4_aux/tables/wavecount_context.csv"
)
DEFAULT_H4_CONTEXT_CSV = (
    REPO_ROOT
    / "artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/"
    / "diagnostic_phase2_4_h4_d1_expanded/tables/wavecount_context.csv"
)
DEFAULT_SYMBOL_CONTROL_CSV = REPO_ROOT / "artifacts/data-health/sql_mt5_2026-05-17/tables/symbol_control.csv"
DEFAULT_SQL_OHLC_CSV = REPO_ROOT / "artifacts/tfg/trading_center_sql_market_data_readonly_v1_2026-05-31/ohlc_mtf.csv"


@dataclass(frozen=True)
class MarketRadarConfig:
    m15_context_csv: Path | None = None
    h1_context_csv: Path = DEFAULT_H1_CONTEXT_CSV
    h4_context_csv: Path = DEFAULT_H4_CONTEXT_CSV
    source_ohlc_csv: Path | None = DEFAULT_SQL_OHLC_CSV
    symbol_control_csv: Path = DEFAULT_SYMBOL_CONTROL_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    stoch_overbought: float = 80.0
    stoch_oversold: float = 20.0


@dataclass(frozen=True)
class MarketRadarResult:
    market_radar: pd.DataFrame
    source_coverage_audit: pd.DataFrame
    indicator_engine_audit: pd.DataFrame
    trend_alignment_audit: pd.DataFrame
    extreme_condition_audit: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]


def build_market_radar(config: MarketRadarConfig | None = None) -> MarketRadarResult:
    config = config or MarketRadarConfig()
    generated_at = utc_now()
    universe = read_csv(config.symbol_control_csv)
    source_mode = "sql_readonly_ohlc_artifact" if config.source_ohlc_csv and config.source_ohlc_csv.exists() else "context_artifacts"
    if source_mode == "sql_readonly_ohlc_artifact":
        ohlc = load_ohlc_mtf_csv(config.source_ohlc_csv)
        m15 = ohlc[ohlc["timeframe"].astype(str) == "M15"].copy()
        h1 = ohlc[ohlc["timeframe"].astype(str) == "H1"].copy()
        h4 = ohlc[ohlc["timeframe"].astype(str) == "H4"].copy()
        d1 = ohlc[ohlc["timeframe"].astype(str) == "D1"].copy()
        radar_rows = build_radar_rows_from_ohlc(ohlc, config=config, generated_at=generated_at)
    else:
        m15 = load_optional_context_csv(config.m15_context_csv)
        h1 = load_context_csv(config.h1_context_csv)
        h4 = load_context_csv(config.h4_context_csv)
        d1 = empty_context_frame()
        radar_rows = build_radar_rows(m15, h1, h4, config=config, generated_at=generated_at)
    radar = normalize_radar_frame(pd.DataFrame(radar_rows))
    coverage = source_coverage_audit(m15, h1, h4, d1, universe, config, source_mode=source_mode)
    indicator_audit = indicator_engine_audit(config, source_mode=source_mode)
    trend_audit = trend_alignment_audit(radar)
    extreme_audit = extreme_condition_audit(radar)
    issues = issues_or_risks(radar, coverage)
    decision = decide_result(issues)
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": generated_at,
        "decision": decision,
        "market_radar_rows": int(len(radar)),
        "symbols_with_radar": int(radar["symbol"].nunique()) if not radar.empty else 0,
        "trend_aligned_count": trend_aligned_count(radar),
        "counter_extreme_count": rsi_screener_count(radar),
        "artifact_first": True,
        "source_mode": source_mode,
        "source_sql_readonly_artifact": source_mode == "sql_readonly_ohlc_artifact",
        "sql_real_read": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": False,
        "source_m15_context_csv": str(config.m15_context_csv) if config.m15_context_csv else "",
        "source_h1_context_csv": str(config.h1_context_csv),
        "source_h4_context_csv": str(config.h4_context_csv),
        "source_ohlc_csv": str(config.source_ohlc_csv) if config.source_ohlc_csv else "",
    }
    write_outputs(config, radar, coverage, indicator_audit, trend_audit, extreme_audit, issues, run_meta)
    return MarketRadarResult(
        market_radar=radar,
        source_coverage_audit=coverage,
        indicator_engine_audit=indicator_audit,
        trend_alignment_audit=trend_audit,
        extreme_condition_audit=extreme_audit,
        issues_or_risks=issues,
        run_meta=run_meta,
    )


def load_context_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, low_memory=False)
    required = {"group", "symbol", "timeframe", "timestamp", "open", "high", "low", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")
    frame = frame.rename(columns={"group": "market_group"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["timestamp", "symbol", "timeframe", "open", "high", "low", "close"]).sort_values(
        ["symbol", "timeframe", "timestamp"]
    )


def load_ohlc_mtf_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, low_memory=False)
    if "time" in frame.columns and "timestamp" not in frame.columns:
        frame = frame.rename(columns={"time": "timestamp"})
    if "group" in frame.columns and "market_group" not in frame.columns:
        frame = frame.rename(columns={"group": "market_group"})
    required = {"symbol", "timeframe", "timestamp", "open", "high", "low", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")
    if "market_group" not in frame.columns:
        frame["market_group"] = "not_available"
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["timestamp", "symbol", "timeframe", "open", "high", "low", "close"]).sort_values(
        ["symbol", "timeframe", "timestamp"]
    )


def empty_context_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["market_group", "symbol", "timeframe", "timestamp", "open", "high", "low", "close", "trend_state", "htf_trend_state"]
    )


def load_optional_context_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return empty_context_frame()
    return load_context_csv(path)


def build_radar_rows_from_ohlc(
    ohlc: pd.DataFrame,
    *,
    config: MarketRadarConfig,
    generated_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if ohlc.empty:
        return rows
    by_symbol_tf = {
        (str(symbol), str(timeframe)): part.sort_values("timestamp")
        for (symbol, timeframe), part in ohlc.groupby(["symbol", "timeframe"], dropna=False)
    }
    symbols = sorted({str(value) for value in ohlc["symbol"].dropna().unique()})
    for symbol in symbols:
        frames = {timeframe: by_symbol_tf.get((symbol, timeframe), empty_context_frame()) for timeframe in ("M15", "H1", "H4", "D1")}
        latest = {timeframe: latest_row(frames[timeframe]) for timeframe in frames}
        trends = {timeframe: latest_trend(frames[timeframe]) for timeframe in frames}
        indicators = {timeframe: latest_indicators(frames[timeframe]) if not frames[timeframe].empty else empty_indicators() for timeframe in frames}
        m15_trend = trends["M15"]
        h1_trend = trends["H1"]
        h4_trend = trends["H4"]
        d1_trend = trends["D1"]
        m15_h1_h4_alignment = alignment_state(m15_trend, h1_trend, h4_trend, label="m15_h1_h4")
        h1_h4_d1_alignment = alignment_state(h1_trend, h4_trend, d1_trend, label="h1_h4_d1")
        alignment = primary_alignment_state(m15_h1_h4_alignment, h1_h4_d1_alignment)
        h1_extreme = extreme_state(indicators["H1"], config)
        h4_extreme = extreme_state(indicators["H4"], config)
        m15_rsi_signal = rsi_context_signal(indicators["M15"].get("RSI"), [m15_trend, h1_trend, h4_trend])
        h1_rsi_signal = rsi_context_signal(indicators["H1"].get("RSI"), [h1_trend, h4_trend, d1_trend])
        h4_rsi_signal = rsi_context_signal(indicators["H4"].get("RSI"), [h4_trend, d1_trend])
        rsi_signal_value = first_signal_rsi(
            ("M15", m15_rsi_signal, indicators["M15"].get("RSI")),
            ("H1", h1_rsi_signal, indicators["H1"].get("RSI")),
            ("H4", h4_rsi_signal, indicators["H4"].get("RSI")),
        )
        dashboard_bucket = dashboard_bucket_for(alignment, m15_rsi_signal, h1_rsi_signal, h4_rsi_signal)
        rows.append(
            {
                "symbol": symbol,
                "market_group": first_market_group(frames),
                "as_of": timestamp_text(first_present(latest["M15"].get("timestamp") if latest["M15"] is not None else "", latest["H1"].get("timestamp") if latest["H1"] is not None else "")),
                "m15_trend": m15_trend,
                "h1_trend": h1_trend,
                "h4_trend": h4_trend,
                "d1_trend": d1_trend,
                "alignment_state": alignment,
                "m15_h1_h4_alignment": m15_h1_h4_alignment,
                "h1_h4_d1_alignment": h1_h4_d1_alignment,
                "rsi_m15": indicators["M15"].get("RSI", ""),
                "rsi_h1": indicators["H1"].get("RSI", ""),
                "rsi_h4": indicators["H4"].get("RSI", ""),
                "atr_pct_m15": indicators["M15"].get("ATR_PCT", ""),
                "atr_pct_h1": indicators["H1"].get("ATR_PCT", ""),
                "atr_pct_h4": indicators["H4"].get("ATR_PCT", ""),
                "atr_pct_m15_median": indicators["M15"].get("ATR_PCT_MEDIAN", ""),
                "atr_pct_h1_median": indicators["H1"].get("ATR_PCT_MEDIAN", ""),
                "atr_pct_h4_median": indicators["H4"].get("ATR_PCT_MEDIAN", ""),
                "atr_pct_m15_ratio": indicators["M15"].get("ATR_PCT_RATIO", ""),
                "atr_pct_h1_ratio": indicators["H1"].get("ATR_PCT_RATIO", ""),
                "atr_pct_h4_ratio": indicators["H4"].get("ATR_PCT_RATIO", ""),
                "atr_pct_h1_sample_count": indicators["H1"].get("ATR_PCT_SAMPLE_COUNT", ""),
                "range_pct_h1_24": recent_range_pct(frames["H1"], bars=24),
                "range_pct_h4_12": recent_range_pct(frames["H4"], bars=12),
                "stoch_k_h1": indicators["H1"].get("STOCH_K", ""),
                "stoch_d_h1": indicators["H1"].get("STOCH_D", ""),
                "extreme_state": h1_extreme,
                "h4_extreme_state": h4_extreme,
                "m15_rsi_signal": m15_rsi_signal,
                "h1_rsi_signal": h1_rsi_signal,
                "h4_rsi_signal": h4_rsi_signal,
                "d1_rsi_signal": "",
                "rsi_signal_value": rsi_signal_value,
                "radar_case": radar_case(alignment, m15_rsi_signal, h1_rsi_signal, h4_rsi_signal),
                "dashboard_bucket": dashboard_bucket,
                "icon": icon_for(alignment, dashboard_bucket),
                "note": note_for(alignment, dashboard_bucket),
                "m15_source_time": timestamp_text(latest["M15"].get("timestamp") if latest["M15"] is not None else ""),
                "h1_source_time": timestamp_text(latest["H1"].get("timestamp") if latest["H1"] is not None else ""),
                "h4_source_time": timestamp_text(latest["H4"].get("timestamp") if latest["H4"] is not None else ""),
                "d1_source_time": timestamp_text(latest["D1"].get("timestamp") if latest["D1"] is not None else ""),
                "source_artifacts": str(config.source_ohlc_csv) if config.source_ohlc_csv else "",
                "is_read_only": True,
                "can_execute_order": False,
                "signals_generated": False,
                "wavecount_used_as_filter": False,
                "method_version": METHOD_VERSION,
                "generated_at": generated_at,
            }
        )
    return rows


def build_radar_rows(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    *,
    config: MarketRadarConfig,
    generated_at: str,
) -> list[dict[str, Any]]:
    latest_h1 = latest_by_symbol(h1)
    m15_by_symbol = {symbol: part.sort_values("timestamp") for symbol, part in m15.groupby("symbol", dropna=False)}
    h4_by_symbol = {symbol: part.sort_values("timestamp") for symbol, part in h4.groupby("symbol", dropna=False)}
    rows: list[dict[str, Any]] = []
    for _, h1_row in latest_h1.iterrows():
        symbol = str(h1_row["symbol"])
        m15_row = latest_at_or_before(m15_by_symbol.get(symbol), pd.Timestamp(h1_row["timestamp"]))
        h4_row = latest_at_or_before(h4_by_symbol.get(symbol), pd.Timestamp(h1_row["timestamp"]))
        m15_indicators = latest_indicators(m15[m15["symbol"].astype(str) == symbol]) if not m15.empty else empty_indicators()
        h1_indicators = latest_indicators(h1[h1["symbol"].astype(str) == symbol])
        h4_indicators = latest_indicators(h4[h4["symbol"].astype(str) == symbol]) if h4_row is not None else empty_indicators()
        m15_trend = normalize_alignment(m15_row.get("trend_state") if m15_row is not None else "")
        h1_trend = normalize_alignment(h1_row.get("trend_state"))
        h4_trend = normalize_alignment(first_present(h1_row.get("htf_trend_state"), h4_row.get("trend_state") if h4_row is not None else ""))
        d1_trend = normalize_alignment(h4_row.get("htf_trend_state") if h4_row is not None else "")
        m15_h1_h4_alignment = alignment_state(m15_trend, h1_trend, h4_trend, label="m15_h1_h4")
        h1_h4_d1_alignment = alignment_state(h1_trend, h4_trend, d1_trend, label="h1_h4_d1")
        alignment = primary_alignment_state(m15_h1_h4_alignment, h1_h4_d1_alignment)
        h1_extreme = extreme_state(h1_indicators, config)
        h4_extreme = extreme_state(h4_indicators, config)
        m15_rsi_signal = rsi_context_signal(m15_indicators.get("RSI"), [m15_trend, h1_trend, h4_trend])
        h1_rsi_signal = rsi_context_signal(h1_indicators.get("RSI"), [h1_trend, h4_trend, d1_trend])
        h4_rsi_signal = rsi_context_signal(h4_indicators.get("RSI"), [h4_trend, d1_trend])
        rsi_signal_value = first_signal_rsi(
            ("M15", m15_rsi_signal, m15_indicators.get("RSI")),
            ("H1", h1_rsi_signal, h1_indicators.get("RSI")),
            ("H4", h4_rsi_signal, h4_indicators.get("RSI")),
        )
        dashboard_bucket = dashboard_bucket_for(alignment, m15_rsi_signal, h1_rsi_signal, h4_rsi_signal)
        rows.append(
            {
                "symbol": symbol,
                "market_group": str(h1_row.get("market_group", "")),
                "as_of": timestamp_text(h1_row.get("timestamp")),
                "m15_trend": m15_trend,
                "h1_trend": h1_trend,
                "h4_trend": h4_trend,
                "d1_trend": d1_trend,
                "alignment_state": alignment,
                "m15_h1_h4_alignment": m15_h1_h4_alignment,
                "h1_h4_d1_alignment": h1_h4_d1_alignment,
                "rsi_m15": m15_indicators.get("RSI", ""),
                "rsi_h1": h1_indicators.get("RSI", ""),
                "rsi_h4": h4_indicators.get("RSI", ""),
                "atr_pct_m15": m15_indicators.get("ATR_PCT", ""),
                "atr_pct_h1": h1_indicators.get("ATR_PCT", ""),
                "atr_pct_h4": h4_indicators.get("ATR_PCT", ""),
                "atr_pct_m15_median": m15_indicators.get("ATR_PCT_MEDIAN", ""),
                "atr_pct_h1_median": h1_indicators.get("ATR_PCT_MEDIAN", ""),
                "atr_pct_h4_median": h4_indicators.get("ATR_PCT_MEDIAN", ""),
                "atr_pct_m15_ratio": m15_indicators.get("ATR_PCT_RATIO", ""),
                "atr_pct_h1_ratio": h1_indicators.get("ATR_PCT_RATIO", ""),
                "atr_pct_h4_ratio": h4_indicators.get("ATR_PCT_RATIO", ""),
                "atr_pct_h1_sample_count": h1_indicators.get("ATR_PCT_SAMPLE_COUNT", ""),
                "range_pct_h1_24": recent_range_pct(h1[h1["symbol"].astype(str) == symbol], bars=24),
                "range_pct_h4_12": recent_range_pct(h4[h4["symbol"].astype(str) == symbol], bars=12),
                "stoch_k_h1": h1_indicators.get("STOCH_K", ""),
                "stoch_d_h1": h1_indicators.get("STOCH_D", ""),
                "extreme_state": h1_extreme,
                "h4_extreme_state": h4_extreme,
                "m15_rsi_signal": m15_rsi_signal,
                "h1_rsi_signal": h1_rsi_signal,
                "h4_rsi_signal": h4_rsi_signal,
                "d1_rsi_signal": "",
                "rsi_signal_value": rsi_signal_value,
                "radar_case": radar_case(alignment, m15_rsi_signal, h1_rsi_signal, h4_rsi_signal),
                "dashboard_bucket": dashboard_bucket,
                "icon": icon_for(alignment, dashboard_bucket),
                "note": note_for(alignment, dashboard_bucket),
                "m15_source_time": timestamp_text(m15_row.get("timestamp") if m15_row is not None else ""),
                "h4_source_time": timestamp_text(h1_row.get("htf_context_source_time")),
                "d1_source_time": timestamp_text(h4_row.get("htf_context_source_time") if h4_row is not None else ""),
                "source_artifacts": ";".join(str(path) for path in [config.m15_context_csv, config.h1_context_csv, config.h4_context_csv] if path),
                "is_read_only": True,
                "can_execute_order": False,
                "signals_generated": False,
                "wavecount_used_as_filter": False,
                "method_version": METHOD_VERSION,
                "generated_at": generated_at,
            }
        )
    return rows


def empty_indicators() -> dict[str, Any]:
    return {
        "RSI": "",
        "STOCH_K": "",
        "STOCH_D": "",
        "ATR": "",
        "ATR_PCT": "",
        "ATR_PCT_MEDIAN": "",
        "ATR_PCT_RATIO": "",
        "ATR_PCT_SAMPLE_COUNT": "",
    }


def latest_indicators(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return empty_indicators()
    work = frame.sort_values("timestamp").set_index("timestamp")[["open", "high", "low", "close"]].copy()
    indicators = GeneradorIndicadores(rsi_len=14, stoch_k=14, stoch_d=3, stoch_smooth=3, ma_type="wma").aplicar_todo(work)
    latest = indicators.iloc[-1]
    stoch_d_column = next((column for column in indicators.columns if str(column).startswith("STOCHd")), "STOCH_D")
    atr_pct_series = atr_pct_history(indicators, work)
    latest_atr_pct = latest_valid(atr_pct_series)
    median_atr_pct = float(atr_pct_series.median()) if not atr_pct_series.empty else None
    return {
        "RSI": rounded(latest.get("RSI")),
        "STOCH_K": rounded(latest.get("STOCH_K")),
        "STOCH_D": rounded(latest.get(stoch_d_column)),
        "ATR": rounded(latest.get("ATR")),
        "ATR_PCT": rounded(latest_atr_pct),
        "ATR_PCT_MEDIAN": rounded(median_atr_pct),
        "ATR_PCT_RATIO": rounded_ratio(latest_atr_pct, median_atr_pct),
        "ATR_PCT_SAMPLE_COUNT": str(int(len(atr_pct_series))),
    }


def atr_pct_history(indicators: pd.DataFrame, source: pd.DataFrame) -> pd.Series:
    if "ATR" not in indicators:
        return pd.Series(dtype=float)
    atr = pd.to_numeric(indicators["ATR"], errors="coerce")
    if "close" in indicators:
        close = pd.to_numeric(indicators["close"], errors="coerce")
    else:
        close = pd.to_numeric(source["close"], errors="coerce")
    pct = (atr / close.replace(0, pd.NA)) * 100.0
    return pct.replace([float("inf"), float("-inf")], pd.NA).dropna()


def latest_valid(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.iloc[-1])


def recent_range_pct(frame: pd.DataFrame, *, bars: int) -> str:
    if frame.empty:
        return ""
    work = frame.sort_values("timestamp").tail(max(int(bars), 1)).copy()
    if work.empty:
        return ""
    high = pd.to_numeric(work["high"], errors="coerce").max()
    low = pd.to_numeric(work["low"], errors="coerce").min()
    close = numeric(work.iloc[-1].get("close"))
    if close in (None, 0) or pd.isna(high) or pd.isna(low):
        return ""
    return f"{((float(high) - float(low)) / close) * 100.0:.2f}"


def latest_trend(frame: pd.DataFrame) -> str:
    if frame.empty or len(frame) < 160:
        return "mixed_or_unclear"
    work = frame.sort_values("timestamp").set_index("timestamp")[["open", "high", "low", "close"]].copy()
    try:
        trend_frame = AnalizadorDeContexto(trend_fast=50, trend_slow=150, trend_type="wma").calcular_tendencia(work)
    except Exception:
        return "mixed_or_unclear"
    trend = pd.to_numeric(trend_frame.get("TENDENCIA_ESTRUCTURAL"), errors="coerce").dropna()
    if trend.empty:
        return "mixed_or_unclear"
    latest = float(trend.iloc[-1])
    if latest > 0:
        return "bullish"
    if latest < 0:
        return "bearish"
    return "mixed_or_unclear"


def latest_row(frame: pd.DataFrame) -> pd.Series | None:
    if frame.empty:
        return None
    return frame.sort_values("timestamp").iloc[-1]


def first_market_group(frames: dict[str, pd.DataFrame]) -> str:
    for frame in frames.values():
        if frame.empty or "market_group" not in frame:
            continue
        values = frame["market_group"].dropna().astype(str)
        if not values.empty:
            return values.iloc[-1]
    return "not_available"


def latest_by_symbol(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    idx = frame.sort_values("timestamp").groupby("symbol", dropna=False)["timestamp"].idxmax()
    return frame.loc[idx].sort_values("symbol").reset_index(drop=True)


def latest_at_or_before(frame: pd.DataFrame | None, timestamp: pd.Timestamp) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    part = frame[frame["timestamp"] <= timestamp]
    if part.empty:
        return None
    return part.sort_values("timestamp").iloc[-1]


def normalize_alignment(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"bullish", "bullish_alignment", "bullish_trend", "alcista", "1", "+1"}:
        return "bullish"
    if text in {"bearish", "bearish_alignment", "bearish_trend", "bajista", "-1"}:
        return "bearish"
    return "mixed_or_unclear"


def alignment_state(first: str, second: str, third: str, *, label: str = "h1_h4_d1") -> str:
    if {first, second, third} == {"bullish"}:
        return f"bullish_aligned_{label}"
    if {first, second, third} == {"bearish"}:
        return f"bearish_aligned_{label}"
    return f"not_aligned_{label}"


def primary_alignment_state(m15_h1_h4: str, h1_h4_d1: str) -> str:
    if h1_h4_d1.startswith("bullish_aligned") or h1_h4_d1.startswith("bearish_aligned"):
        return h1_h4_d1
    if m15_h1_h4.startswith("bullish_aligned") or m15_h1_h4.startswith("bearish_aligned"):
        return m15_h1_h4
    return "not_aligned"


def extreme_state(indicators: dict[str, Any], config: MarketRadarConfig) -> str:
    rsi = numeric(indicators.get("RSI"))
    stoch_k = numeric(indicators.get("STOCH_K"))
    stoch_d = numeric(indicators.get("STOCH_D"))
    overbought = (
        (rsi is not None and rsi >= config.rsi_overbought)
        or (stoch_k is not None and stoch_d is not None and stoch_k >= config.stoch_overbought and stoch_d >= config.stoch_overbought)
    )
    oversold = (
        (rsi is not None and rsi <= config.rsi_oversold)
        or (stoch_k is not None and stoch_d is not None and stoch_k <= config.stoch_oversold and stoch_d <= config.stoch_oversold)
    )
    if overbought and oversold:
        return "mixed_extreme"
    if overbought:
        return "overbought"
    if oversold:
        return "oversold"
    return "neutral"


def rsi_context_signal(rsi_value: Any, trends: list[str]) -> str:
    rsi = numeric(rsi_value)
    trend_set = set(trends)
    if rsi is None or "mixed_or_unclear" in trend_set:
        return ""
    if trend_set == {"bearish"} and rsi >= 70:
        return "bearish_overbought"
    if trend_set == {"bullish"} and rsi <= 30:
        return "bullish_oversold"
    return ""


def first_signal_rsi(*items: tuple[str, str, Any]) -> str:
    for timeframe, signal, value in items:
        if signal:
            rendered = rounded(value)
            return f"{timeframe} {rendered}" if rendered else timeframe
    return ""


def has_rsi_screener_signal(*signals: str) -> bool:
    return any(bool(signal) for signal in signals)


def radar_case(alignment: str, m15_signal: str, h1_signal: str, h4_signal: str) -> str:
    if has_rsi_screener_signal(m15_signal, h1_signal, h4_signal):
        return "rsi_screener"
    if alignment.startswith("bullish_aligned") or alignment.startswith("bearish_aligned"):
        return "trend_aligned"
    return "not_aligned"


def dashboard_bucket_for(alignment: str, m15_signal: str, h1_signal: str, h4_signal: str) -> str:
    case = radar_case(alignment, m15_signal, h1_signal, h4_signal)
    if case == "rsi_screener":
        return "counter_extreme"
    if case == "trend_aligned":
        return "trend_aligned"
    return "not_shown_in_summary"


def icon_for(alignment: str, bucket: str) -> str:
    if alignment.startswith("bullish_aligned"):
        return "↑"
    if alignment.startswith("bearish_aligned"):
        return "↓"
    return ""


def note_for(alignment: str, bucket: str) -> str:
    if bucket == "trend_aligned":
        return "alineado; no senal"
    if bucket == "counter_extreme":
        return "rsi extremo en contexto"
    return "fuera del resumen principal"


RADAR_COLUMNS = [
    "symbol",
    "market_group",
    "as_of",
    "m15_trend",
    "h1_trend",
    "h4_trend",
    "d1_trend",
    "alignment_state",
    "m15_h1_h4_alignment",
    "h1_h4_d1_alignment",
    "rsi_m15",
    "rsi_h1",
    "rsi_h4",
    "atr_pct_m15",
    "atr_pct_h1",
    "atr_pct_h4",
    "atr_pct_m15_median",
    "atr_pct_h1_median",
    "atr_pct_h4_median",
    "atr_pct_m15_ratio",
    "atr_pct_h1_ratio",
    "atr_pct_h4_ratio",
    "atr_pct_h1_sample_count",
    "range_pct_h1_24",
    "range_pct_h4_12",
    "stoch_k_h1",
    "stoch_d_h1",
    "extreme_state",
    "h4_extreme_state",
    "m15_rsi_signal",
    "h1_rsi_signal",
    "h4_rsi_signal",
    "d1_rsi_signal",
    "rsi_signal_value",
    "radar_case",
    "dashboard_bucket",
    "icon",
    "note",
    "m15_source_time",
    "h1_source_time",
    "h4_source_time",
    "d1_source_time",
    "source_artifacts",
    "is_read_only",
    "can_execute_order",
    "signals_generated",
    "wavecount_used_as_filter",
    "method_version",
    "generated_at",
]


def normalize_radar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=RADAR_COLUMNS)
    return frame.reindex(columns=RADAR_COLUMNS)


def trend_aligned_count(radar: pd.DataFrame) -> int:
    if radar.empty or "alignment_state" not in radar:
        return 0
    return int(radar["alignment_state"].astype(str).str.startswith(("bullish_aligned", "bearish_aligned")).sum())


def rsi_screener_count(radar: pd.DataFrame) -> int:
    if radar.empty:
        return 0
    signal_columns = [column for column in ("m15_rsi_signal", "h1_rsi_signal", "h4_rsi_signal", "d1_rsi_signal") if column in radar]
    if not signal_columns:
        return 0
    return int((radar[signal_columns].fillna("").astype(str) != "").any(axis=1).sum())


def source_coverage_audit(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    d1: pd.DataFrame,
    universe: list[dict[str, Any]],
    config: MarketRadarConfig,
    *,
    source_mode: str,
) -> pd.DataFrame:
    m15_symbols = {str(value) for value in m15.get("symbol", pd.Series(dtype=str)).dropna().unique()}
    h1_symbols = {str(value) for value in h1.get("symbol", pd.Series(dtype=str)).dropna().unique()}
    h4_symbols = {str(value) for value in h4.get("symbol", pd.Series(dtype=str)).dropna().unique()}
    d1_symbols = {str(value) for value in d1.get("symbol", pd.Series(dtype=str)).dropna().unique()}
    universe_symbols = {str(row.get("symbol")) for row in universe if row.get("symbol")}
    common = h1_symbols & h4_symbols
    if source_mode == "sql_readonly_ohlc_artifact":
        common = m15_symbols & h1_symbols & h4_symbols & d1_symbols
    m15_status = "available" if m15_symbols else ("not_configured" if config.m15_context_csv is None and source_mode != "sql_readonly_ohlc_artifact" else "missing")
    return pd.DataFrame(
        [
            {"check": "source_mode", "value": source_mode, "status": "configured"},
            {"check": "m15_context_symbols", "value": len(m15_symbols), "status": m15_status},
            {"check": "h1_context_symbols", "value": len(h1_symbols), "status": "available" if h1_symbols else "missing"},
            {"check": "h4_context_symbols", "value": len(h4_symbols), "status": "available" if h4_symbols else "missing"},
            {"check": "d1_context_symbols", "value": len(d1_symbols), "status": "available" if d1_symbols else ("not_applicable" if source_mode != "sql_readonly_ohlc_artifact" else "missing")},
            {"check": "common_radar_symbols", "value": len(common), "status": "available" if common else "missing"},
            {"check": "universe_symbols", "value": len(universe_symbols), "status": "available" if universe_symbols else "missing"},
            {
                "check": "coverage_vs_universe",
                "value": f"{len(common)}/{len(universe_symbols)}",
                "status": "partial" if len(common) < len(universe_symbols) else "complete",
            },
        ]
    )


def indicator_engine_audit(config: MarketRadarConfig, *, source_mode: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"item": "indicator_engine", "value": "backtests.enbolsa.GenerarIndicadores", "status": "reused"},
            {"item": "trend_engine", "value": "backtests.enbolsa.market_context.AnalizadorDeContexto", "status": "reused"},
            {"item": "source_mode", "value": source_mode, "status": "configured"},
            {"item": "rsi_len", "value": 14, "status": "configured"},
            {"item": "stoch_k_d_smooth", "value": "14/3/3", "status": "configured"},
            {"item": "rsi_overbought_oversold", "value": f"{config.rsi_overbought}/{config.rsi_oversold}", "status": "configured"},
            {"item": "stoch_overbought_oversold", "value": f"{config.stoch_overbought}/{config.stoch_oversold}", "status": "configured"},
            {"item": "source_sql_readonly_artifact", "value": source_mode == "sql_readonly_ohlc_artifact", "status": "source_artifact"},
            {"item": "sql_real_read", "value": False, "status": "passed"},
            {"item": "signals_generated", "value": False, "status": "passed"},
        ]
    )


def trend_alignment_audit(radar: pd.DataFrame) -> pd.DataFrame:
    if radar.empty:
        return pd.DataFrame([{"alignment_state": "not_available", "rows": 0}])
    return radar.groupby("alignment_state", dropna=False).size().reset_index(name="rows")


def extreme_condition_audit(radar: pd.DataFrame) -> pd.DataFrame:
    if radar.empty:
        return pd.DataFrame([{"extreme_state": "not_available", "rows": 0}])
    return radar.groupby(["extreme_state", "radar_case", "dashboard_bucket"], dropna=False).size().reset_index(name="rows")


def issues_or_risks(radar: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    rows = []
    coverage_row = coverage[coverage["check"] == "coverage_vs_universe"]
    if not coverage_row.empty and str(coverage_row.iloc[0]["status"]) == "partial":
        rows.append(
            {
                "issue_id": "R01",
                "severity": "medium",
                "status": "open",
                "description": "Radar coverage is partial versus the full Trading Center universe.",
                "mitigation": "Add a broader OHLC artifact or read-only source before claiming full-market radar.",
            }
        )
    if radar.empty:
        rows.append(
            {
                "issue_id": "R02",
                "severity": "high",
                "status": "open",
                "description": "No market radar rows were generated.",
                "mitigation": "Provide H1/H4 and H4/D1 context artifacts with OHLC and trend fields.",
            }
        )
    if not rows:
        rows.append(
            {
                "issue_id": "R00",
                "severity": "low",
                "status": "closed",
                "description": "No blocking issue found for artifact-first radar generation.",
                "mitigation": "Keep radar informational and non-operational.",
            }
        )
    return pd.DataFrame(rows)


def decide_result(issues: pd.DataFrame) -> str:
    if (issues.get("severity", pd.Series(dtype=str)) == "high").any():
        return "market_radar_v1_blocked_by_missing_source"
    return "market_radar_v1_ready_for_dashboard_summary"


def write_outputs(
    config: MarketRadarConfig,
    radar: pd.DataFrame,
    coverage: pd.DataFrame,
    indicator_audit: pd.DataFrame,
    trend_audit: pd.DataFrame,
    extreme_audit: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> None:
    output = config.output_dir
    tables = output / "tables"
    output.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    radar.to_csv(output / "market_radar.csv", index=False)
    (output / "market_radar.json").write_text(radar.to_json(orient="records", indent=2, force_ascii=False), encoding="utf-8")
    write_csv(tables / "source_coverage_audit.csv", coverage.to_dict(orient="records"))
    write_csv(tables / "indicator_engine_audit.csv", indicator_audit.to_dict(orient="records"))
    write_csv(tables / "trend_alignment_audit.csv", trend_audit.to_dict(orient="records"))
    write_csv(tables / "extreme_condition_audit.csv", extreme_audit.to_dict(orient="records"))
    write_csv(tables / "issues_or_risks.csv", issues.to_dict(orient="records"))
    (output / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    report = render_report(run_meta)
    (output / "MARKET_RADAR_V1.md").write_text(report, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(report, encoding="utf-8")


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Market Radar V1

Fecha: 2026-05-31

Decision: `{run_meta['decision']}`.

## Resultado

Se genera `market_radar.csv` como artifact informativo para alimentar el
Resumen del Trading Center Dash.

El radar cruza:

- tendencia M15/H1/H4 y H1/H4/D1 cuando existe fuente para cada timeframe;
- RSI y Stoch calculados con `backtests.enbolsa.GenerarIndicadores`;
- ATR% actual y mediana propia por activo para ranking de exceso/carencia de
  volatilidad;
- alineacion de tendencia para el radar visual;
- `Screener RSI` para RSI extremo dentro del contexto de timeframes superiores.

## Datos

- filas radar: {run_meta['market_radar_rows']}
- simbolos con radar: {run_meta['symbols_with_radar']}
- alineados: {run_meta['trend_aligned_count']}
- lecturas Screener RSI: {run_meta['counter_extreme_count']}
- source_mode: `{run_meta['source_mode']}`

Campos de volatilidad:

- `atr_pct_h1`: ATR H1 actual en porcentaje sobre precio.
- `atr_pct_h1_median`: mediana de ATR% H1 del propio activo en la ventana
  disponible.
- `atr_pct_h1_ratio`: `atr_pct_h1 / atr_pct_h1_median`; se usa para rankear
  exceso o carencia de volatilidad sin comparar familias por escala bruta.
- `atr_pct_h1_sample_count`: numero de lecturas validas usadas.

El radar puede consumir el artifact SQL read-only `ohlc_mtf.csv` con M15/H1/H4/D1
para cubrir todo el universo disponible en `price_data`. Si ese artifact no existe,
mantiene fallback a los contextos H1/H4 y H4/D1 ya auditados sin inventar lecturas
para los timeframes que falten.

## Seguridad

- No conecta SQL.
- No escribe SQL.
- No conecta MT5.
- No conecta Telegram.
- No genera senales.
- No ejecuta backtests.
- No usa WaveCount como filtro.

## Uso

```powershell
python -m trading_center.market_radar
```
"""


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "") and str(value).lower() not in {"nan", "none"}:
            return value
    return ""


def numeric(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def rounded(value: Any) -> str:
    parsed = numeric(value)
    return "" if parsed is None else f"{parsed:.2f}"


def rounded_pct(numerator: Any, denominator: Any) -> str:
    top = numeric(numerator)
    bottom = numeric(denominator)
    if top is None or bottom in (None, 0):
        return ""
    return f"{(top / bottom) * 100.0:.2f}"


def rounded_ratio(numerator: Any, denominator: Any) -> str:
    top = numeric(numerator)
    bottom = numeric(denominator)
    if top is None or bottom in (None, 0):
        return ""
    return f"{top / bottom:.2f}"


def timestamp_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build artifact-first market radar for Trading Center Dash.")
    parser.add_argument("--source-ohlc-csv", type=Path, default=DEFAULT_SQL_OHLC_CSV)
    parser.add_argument("--m15-context-csv", type=Path, default=None)
    parser.add_argument("--h1-context-csv", type=Path, default=DEFAULT_H1_CONTEXT_CSV)
    parser.add_argument("--h4-context-csv", type=Path, default=DEFAULT_H4_CONTEXT_CSV)
    parser.add_argument("--symbol-control-csv", type=Path, default=DEFAULT_SYMBOL_CONTROL_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_market_radar(
        MarketRadarConfig(
            source_ohlc_csv=args.source_ohlc_csv,
            m15_context_csv=args.m15_context_csv,
            h1_context_csv=args.h1_context_csv,
            h4_context_csv=args.h4_context_csv,
            symbol_control_csv=args.symbol_control_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        )
    )


if __name__ == "__main__":
    main()
