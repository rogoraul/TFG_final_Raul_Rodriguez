from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_center.market_radar import DEFAULT_SQL_OHLC_CSV, load_ohlc_mtf_csv
from trading_center.readonly_dashboard import REPO_ROOT, write_csv


METHOD_VERSION = "trading_center_market_correlations_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/trading_center_market_correlations_v1_2026-05-31"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TRADING_CENTER_MARKET_CORRELATIONS_V1.md"
DEFAULT_TIMEFRAMES = ("M15", "H1", "H4", "D1")
DEFAULT_ROLLING_WINDOWS = {"M15": 96, "H1": 120, "H4": 90, "D1": 60}
METRICS = ("pearson", "spearman", "kendall", "dcor")


@dataclass(frozen=True)
class MarketCorrelationConfig:
    source_ohlc_csv: Path = DEFAULT_SQL_OHLC_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES
    min_observations: int = 40
    dcor_max_observations: int = 260
    returns_sample_size: int = 700
    rolling_windows: dict[str, int] | None = None


@dataclass(frozen=True)
class MarketCorrelationResult:
    pair_correlations: pd.DataFrame
    rolling_correlations: pd.DataFrame
    timeframe_summary: pd.DataFrame
    source_audit: pd.DataFrame
    methodology_audit: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]


def build_market_correlations(config: MarketCorrelationConfig | None = None) -> MarketCorrelationResult:
    config = config or MarketCorrelationConfig()
    generated_at = utc_now()
    ohlc = load_ohlc_mtf_csv(config.source_ohlc_csv)
    windows = config.rolling_windows or DEFAULT_ROLLING_WINDOWS
    returns_by_tf = {
        timeframe: compute_returns(ohlc, timeframe)
        for timeframe in config.timeframes
    }
    pairs = pd.concat(
        [
            compute_pair_rows(
                returns,
                timeframe=timeframe,
                min_observations=config.min_observations,
                dcor_max_observations=config.dcor_max_observations,
            )
            for timeframe, returns in returns_by_tf.items()
        ],
        ignore_index=True,
    )
    rolling = pd.concat(
        [
            compute_rolling_rows(
                returns,
                timeframe=timeframe,
                window=int(windows.get(timeframe, 96)),
                min_observations=config.min_observations,
                dcor_max_observations=config.dcor_max_observations,
            )
            for timeframe, returns in returns_by_tf.items()
        ],
        ignore_index=True,
    )
    summary = timeframe_summary(returns_by_tf, pairs)
    returns_sample = returns_sample_rows(returns_by_tf, sample_size=config.returns_sample_size)
    source_audit = build_source_audit(config, ohlc, returns_by_tf)
    methodology = methodology_audit(config)
    issues = issues_or_risks(summary)
    decision = decide_result(issues)
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": generated_at,
        "decision": decision,
        "source_ohlc_csv": str(config.source_ohlc_csv),
        "timeframes": list(config.timeframes),
        "pair_rows": int(len(pairs)),
        "rolling_rows": int(len(rolling)),
        "min_observations": int(config.min_observations),
        "dcor_max_observations": int(config.dcor_max_observations),
        "returns_sample_rows": int(len(returns_sample)),
        "returns_sample_size_per_symbol_timeframe": int(config.returns_sample_size),
        "artifact_first": True,
        "returns_based": True,
        "price_based_correlation": False,
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
    }
    write_outputs(config, pairs, rolling, returns_sample, summary, source_audit, methodology, issues, run_meta)
    return MarketCorrelationResult(
        pair_correlations=pairs,
        rolling_correlations=rolling,
        timeframe_summary=summary,
        source_audit=source_audit,
        methodology_audit=methodology,
        issues_or_risks=issues,
        run_meta=run_meta,
    )


def compute_returns(ohlc: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    subset = ohlc[ohlc["timeframe"].astype(str).str.upper() == timeframe.upper()].copy()
    if subset.empty:
        return pd.DataFrame()
    frames: list[pd.Series] = []
    for symbol, part in subset.groupby("symbol", dropna=False):
        ordered = part.sort_values("timestamp")
        close = pd.to_numeric(ordered["close"], errors="coerce")
        returns = np.log(close / close.shift(1))
        series = pd.Series(returns.to_numpy(), index=pd.to_datetime(ordered["timestamp"], errors="coerce"), name=str(symbol))
        frames.append(series.replace([np.inf, -np.inf], np.nan).dropna())
    if not frames:
        return pd.DataFrame()
    output = pd.concat(frames, axis=1).sort_index()
    return output.dropna(axis=1, how="all")


def compute_pair_rows(
    returns: pd.DataFrame,
    *,
    timeframe: str,
    min_observations: int,
    dcor_max_observations: int,
) -> pd.DataFrame:
    tickers = sorted(str(column) for column in returns.columns)
    rows: list[dict[str, Any]] = []
    if len(tickers) < 2:
        return pd.DataFrame(rows)
    for left_index, asset_1 in enumerate(tickers):
        for asset_2 in tickers[left_index + 1 :]:
            pair = returns[[asset_1, asset_2]].dropna()
            obs = int(len(pair))
            if obs < min_observations:
                continue
            values_1 = pair[asset_1].to_numpy(dtype=float)
            values_2 = pair[asset_2].to_numpy(dtype=float)
            pearson = corr_pair(values_1, values_2, "pearson")
            spearman = corr_pair(values_1, values_2, "spearman")
            kendall = corr_pair(values_1, values_2, "kendall")
            dcor = distance_correlation(values_1[-dcor_max_observations:], values_2[-dcor_max_observations:])
            rows.append(
                {
                    "timeframe": timeframe,
                    "asset_1": asset_1,
                    "asset_2": asset_2,
                    "pair": f"{asset_1} | {asset_2}",
                    "obs": obs,
                    "pearson": round_float(pearson),
                    "spearman": round_float(spearman),
                    "kendall": round_float(kendall),
                    "dcor": round_float(dcor),
                    "pearson_abs": round_abs(pearson),
                    "spearman_abs": round_abs(spearman),
                    "kendall_abs": round_abs(kendall),
                    "dcor_abs": round_abs(dcor),
                    "sample_start": str(pair.index.min()),
                    "sample_end": str(pair.index.max()),
                    "return_type": "log_return_close_to_close",
                    "is_read_only": True,
                    "can_execute_order": False,
                    "signals_generated": False,
                }
            )
    return pd.DataFrame(rows)


def returns_sample_rows(returns_by_tf: dict[str, pd.DataFrame], *, sample_size: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for timeframe, returns in returns_by_tf.items():
        if returns.empty:
            continue
        for symbol in sorted(str(column) for column in returns.columns):
            series = returns[symbol].dropna().tail(sample_size)
            for timestamp, value in series.items():
                rows.append(
                    {
                        "timeframe": timeframe,
                        "symbol": symbol,
                        "timestamp": str(timestamp),
                        "log_return": round_float(value, 10),
                        "return_type": "log_return_close_to_close",
                        "is_read_only": True,
                        "can_execute_order": False,
                        "signals_generated": False,
                    }
                )
    return pd.DataFrame(rows)


def compute_rolling_rows(
    returns: pd.DataFrame,
    *,
    timeframe: str,
    window: int,
    min_observations: int,
    dcor_max_observations: int,
) -> pd.DataFrame:
    tickers = sorted(str(column) for column in returns.columns)
    rows: list[dict[str, Any]] = []
    if len(tickers) < 2:
        return pd.DataFrame(rows)
    min_periods = max(min_observations, window // 2)
    for left_index, asset_1 in enumerate(tickers):
        for asset_2 in tickers[left_index + 1 :]:
            pair = returns[[asset_1, asset_2]].dropna()
            if len(pair) < min_periods:
                continue
            for metric in METRICS:
                latest, previous, mean_value, obs = latest_previous_window_corr(
                    pair[asset_1],
                    pair[asset_2],
                    window=window,
                    metric=metric,
                    min_periods=min_periods,
                    dcor_max_observations=dcor_max_observations,
                )
                rows.append(
                    {
                        "timeframe": timeframe,
                        "asset_1": asset_1,
                        "asset_2": asset_2,
                        "pair": f"{asset_1} | {asset_2}",
                        "metric": metric,
                        "window": int(window),
                        "latest_corr": round_float(latest),
                        "previous_corr": round_float(previous),
                        "delta_prev": round_float(latest - previous) if np.isfinite(latest) and np.isfinite(previous) else "",
                        "mean_corr": round_float(mean_value),
                        "latest_abs": round_abs(latest),
                        "obs": obs,
                        "is_read_only": True,
                        "can_execute_order": False,
                        "signals_generated": False,
                    }
                )
    return pd.DataFrame(rows)


def latest_previous_window_corr(
    series_1: pd.Series,
    series_2: pd.Series,
    *,
    window: int,
    metric: str,
    min_periods: int,
    dcor_max_observations: int,
) -> tuple[float, float, float, int]:
    pair = pd.DataFrame({"a": series_1, "b": series_2}).replace([np.inf, -np.inf], np.nan).dropna()
    sample = min(window, dcor_max_observations) if metric == "dcor" else window
    if len(pair) < min_periods:
        return float("nan"), float("nan"), float("nan"), 0
    latest_frame = pair.tail(sample)
    previous_frame = pair.iloc[max(0, len(pair) - sample * 2) : max(0, len(pair) - sample)]
    latest = corr_window_frame(latest_frame, metric) if len(latest_frame) >= min_periods else float("nan")
    previous = corr_window_frame(previous_frame, metric) if len(previous_frame) >= min_periods else float("nan")
    mean_value = float(np.nanmean([latest, previous])) if np.isfinite(latest) or np.isfinite(previous) else float("nan")
    return latest, previous, mean_value, int(len(latest_frame))


def corr_window_frame(frame: pd.DataFrame, metric: str) -> float:
    if frame.empty:
        return float("nan")
    values_1 = frame["a"].to_numpy(dtype=float)
    values_2 = frame["b"].to_numpy(dtype=float)
    if metric == "dcor":
        return distance_correlation(values_1, values_2)
    return corr_pair(values_1, values_2, metric)


def corr_pair(values_1: np.ndarray, values_2: np.ndarray, method: str) -> float:
    frame = pd.DataFrame({"a": values_1, "b": values_2}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 2:
        return float("nan")
    return float(frame["a"].corr(frame["b"], method=method))


def rolling_corr(series_1: pd.Series, series_2: pd.Series, window: int, method: str, min_periods: int) -> pd.Series:
    if method == "pearson":
        return series_1.rolling(window, min_periods=min_periods).corr(series_2)
    values: list[float] = []
    index = series_1.index
    for end in range(len(series_1)):
        start = max(0, end - window + 1)
        part = pd.DataFrame({"a": series_1.iloc[start : end + 1], "b": series_2.iloc[start : end + 1]}).dropna()
        if len(part) < min_periods:
            values.append(float("nan"))
        else:
            values.append(float(part["a"].corr(part["b"], method=method)))
    return pd.Series(values, index=index)


def dcor_window_values(series_1: pd.Series, series_2: pd.Series, window: int, dcor_max_observations: int) -> tuple[float, float]:
    pair = pd.DataFrame({"a": series_1, "b": series_2}).dropna()
    sample = min(window, dcor_max_observations)
    if len(pair) < max(4, sample // 2):
        return float("nan"), float("nan")
    latest = pair.tail(sample)
    previous = pair.iloc[max(0, len(pair) - sample * 2) : max(0, len(pair) - sample)]
    latest_value = distance_correlation(latest["a"].to_numpy(dtype=float), latest["b"].to_numpy(dtype=float))
    previous_value = (
        distance_correlation(previous["a"].to_numpy(dtype=float), previous["b"].to_numpy(dtype=float))
        if len(previous) >= max(4, sample // 2)
        else float("nan")
    )
    return latest_value, previous_value


def distance_correlation(values_1: np.ndarray, values_2: np.ndarray) -> float:
    mask = np.isfinite(values_1) & np.isfinite(values_2)
    x = np.asarray(values_1[mask], dtype=float)
    y = np.asarray(values_2[mask], dtype=float)
    if x.size < 4 or y.size < 4:
        return float("nan")
    a = np.abs(x[:, None] - x[None, :])
    b = np.abs(y[:, None] - y[None, :])
    a_centered = a - a.mean(axis=0)[None, :] - a.mean(axis=1)[:, None] + a.mean()
    b_centered = b - b.mean(axis=0)[None, :] - b.mean(axis=1)[:, None] + b.mean()
    dcov2 = float(np.mean(a_centered * b_centered))
    dvar_x = float(np.mean(a_centered * a_centered))
    dvar_y = float(np.mean(b_centered * b_centered))
    if dvar_x <= 1e-18 or dvar_y <= 1e-18:
        return float("nan")
    return float(np.sqrt(max(dcov2, 0.0)) / np.sqrt(np.sqrt(dvar_x * dvar_y)))


def timeframe_summary(returns_by_tf: dict[str, pd.DataFrame], pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for timeframe, returns in returns_by_tf.items():
        frame_pairs = pairs[pairs["timeframe"] == timeframe] if not pairs.empty else pd.DataFrame()
        rows.append(
            {
                "timeframe": timeframe,
                "symbols": int(len(returns.columns)) if not returns.empty else 0,
                "return_rows": int(len(returns)) if not returns.empty else 0,
                "pair_rows": int(len(frame_pairs)),
                "strong_spearman_abs_ge_0_7": int((pd.to_numeric(frame_pairs.get("spearman_abs", pd.Series(dtype=float)), errors="coerce") >= 0.7).sum()) if not frame_pairs.empty else 0,
                "strong_inverse_spearman_le_minus_0_7": int((pd.to_numeric(frame_pairs.get("spearman", pd.Series(dtype=float)), errors="coerce") <= -0.7).sum()) if not frame_pairs.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def build_source_audit(config: MarketCorrelationConfig, ohlc: pd.DataFrame, returns_by_tf: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = [
        {
            "check_id": "CORR_SRC_01",
            "check": "source_ohlc_artifact_exists",
            "status": "passed" if config.source_ohlc_csv.exists() else "failed",
            "evidence": str(config.source_ohlc_csv),
        },
        {
            "check_id": "CORR_SRC_02",
            "check": "source_rows",
            "status": "passed" if len(ohlc) else "failed",
            "value": int(len(ohlc)),
        },
    ]
    for timeframe, returns in returns_by_tf.items():
        rows.append(
            {
                "check_id": f"CORR_TF_{timeframe}",
                "check": "timeframe_returns_available",
                "status": "passed" if not returns.empty else "missing",
                "timeframe": timeframe,
                "symbols": int(len(returns.columns)) if not returns.empty else 0,
                "return_rows": int(len(returns)) if not returns.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def methodology_audit(config: MarketCorrelationConfig) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_id": "CORR_METH_01",
                "check": "returns_not_prices",
                "status": "passed",
                "evidence": "Correlations are computed on close-to-close log returns, not raw prices.",
            },
            {
                "check_id": "CORR_METH_02",
                "check": "distance_correlation_scope",
                "status": "passed",
                "evidence": f"dCor is computed on the latest {config.dcor_max_observations} aligned returns per pair to keep the artifact reproducible.",
            },
            {
                "check_id": "CORR_METH_03",
                "check": "read_only_boundary",
                "status": "passed",
                "evidence": "The module only reads OHLC artifacts and writes audit artifacts; it does not connect SQL/MT5/Telegram.",
            },
        ]
    )


def issues_or_risks(summary: pd.DataFrame) -> pd.DataFrame:
    issues: list[dict[str, Any]] = []
    for row in summary.to_dict(orient="records"):
        if int(row.get("symbols", 0)) < 2:
            issues.append(
                {
                    "issue_id": f"CORR_{row.get('timeframe')}_NO_SYMBOLS",
                    "severity": "medium",
                    "status": "open",
                    "description": f"No enough symbols for timeframe {row.get('timeframe')}.",
                    "mitigation": "Regenerate OHLC MTF artifact with that timeframe.",
                }
            )
    if not issues:
        issues.append(
            {
                "issue_id": "CORR_R01",
                "severity": "low",
                "status": "closed",
                "description": "Correlations can be misread as trading signals.",
                "mitigation": "Dash labels this section as risk/context only; no orders or signals are generated.",
            }
        )
    return pd.DataFrame(issues)


def decide_result(issues: pd.DataFrame) -> str:
    blocking = issues[(issues.get("severity") == "high") & (issues.get("status") == "open")] if not issues.empty else pd.DataFrame()
    if not blocking.empty:
        return "trading_center_market_correlations_v1_blocked"
    return "trading_center_market_correlations_v1_ready_for_dashboard"


def write_outputs(
    config: MarketCorrelationConfig,
    pairs: pd.DataFrame,
    rolling: pd.DataFrame,
    returns_sample: pd.DataFrame,
    summary: pd.DataFrame,
    source_audit: pd.DataFrame,
    methodology: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> None:
    output = config.output_dir
    tables = output / "tables"
    output.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(output / "correlation_pairs.csv", index=False)
    (output / "correlation_pairs.json").write_text(pairs.to_json(orient="records", indent=2, force_ascii=False), encoding="utf-8")
    rolling.to_csv(output / "rolling_correlations.csv", index=False)
    returns_sample.to_csv(output / "correlation_returns_sample.csv", index=False)
    write_csv(tables / "correlation_timeframe_summary.csv", summary.to_dict(orient="records"))
    write_csv(tables / "correlation_source_audit.csv", source_audit.to_dict(orient="records"))
    write_csv(tables / "correlation_methodology_audit.csv", methodology.to_dict(orient="records"))
    write_csv(tables / "issues_or_risks.csv", issues.to_dict(orient="records"))
    (output / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    report = render_report(run_meta)
    (output / "MARKET_CORRELATIONS_V1.md").write_text(report, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(report, encoding="utf-8")


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Market Correlations V1

Fecha: 2026-05-31

Decision: `{run_meta['decision']}`.

## Resultado

Se genera una capa artifact-first de correlacion para el Trading Center Dash.
La correlacion se calcula sobre retornos logaritmicos close-to-close, no sobre
precios brutos.

Artifacts principales:

- `correlation_pairs.csv`
- `correlation_pairs.json`
- `rolling_correlations.csv`
- `correlation_returns_sample.csv`
- `tables/correlation_timeframe_summary.csv`

## Metricas

- Pearson: relacion lineal de retornos.
- Spearman: relacion monotona por rangos; recomendada por defecto.
- Kendall: concordancia ordinal conservadora.
- dCor: dependencia general no lineal, sin signo direccional.

## Seguridad

- No conecta SQL.
- No escribe SQL.
- No conecta MT5.
- No conecta Telegram.
- No genera senales.
- No ejecuta ordenes.
- No ejecuta backtests.

## Datos

- timeframes: `{', '.join(run_meta['timeframes'])}`
- pair_rows: {run_meta['pair_rows']}
- rolling_rows: {run_meta['rolling_rows']}
- returns_sample_rows: {run_meta['returns_sample_rows']}
- source: `{run_meta['source_ohlc_csv']}`
"""


def round_float(value: Any, digits: int = 6) -> float | str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return ""
    if not np.isfinite(parsed):
        return ""
    return round(parsed, digits)


def round_abs(value: Any, digits: int = 6) -> float | str:
    rounded = round_float(value, digits)
    return abs(float(rounded)) if rounded != "" else ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build artifact-first market correlation layer for Trading Center Dash.")
    parser.add_argument("--source-ohlc-csv", type=Path, default=DEFAULT_SQL_OHLC_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument("--min-observations", type=int, default=40)
    parser.add_argument("--dcor-max-observations", type=int, default=260)
    parser.add_argument("--returns-sample-size", type=int, default=700)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timeframes = tuple(part.strip().upper() for part in str(args.timeframes).split(",") if part.strip())
    build_market_correlations(
        MarketCorrelationConfig(
            source_ohlc_csv=args.source_ohlc_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            timeframes=timeframes or DEFAULT_TIMEFRAMES,
            min_observations=args.min_observations,
            dcor_max_observations=args.dcor_max_observations,
            returns_sample_size=args.returns_sample_size,
        )
    )


if __name__ == "__main__":
    main()
