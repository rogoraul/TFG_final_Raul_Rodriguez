from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

from data.sql.sql_funcs import close_db, connect_db

from .wavecount_config import PivotConfig
from .wavecount_plotting import build_compressed_time_axis, compressed_candle_width
from .wavecount_pivots import detect_causal_pivots, extract_pivot_events


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase1_pivots_2026-05-17"


@dataclass(frozen=True)
class ExampleSpec:
    example_id: str
    group: str
    symbol: str
    timeframe: str
    example_type: str
    rows: int = 240


DEFAULT_EXAMPLES = (
    ExampleSpec("forex_clean_eurusd_h1", "Forex Majors", "EURUSD.r", "H1", "clean", 240),
    ExampleSpec("metals_noisy_xauusd_m30", "Metals", "XAUUSD.r", "M30", "noisy", 240),
    ExampleSpec("index_gap_aus200_m30", "Index", "AUS200", "M30", "gap", 240),
    ExampleSpec("metals_ambiguous_xptusd_h1", "Metals", "XPTUSD", "H1", "ambiguous", 220),
)


def timeframe_to_minutes(timeframe: str) -> int | None:
    mapping = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
    }
    return mapping.get(timeframe.upper())


def fetch_recent_ohlc(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    connection = connect_db()
    if connection is None:
        raise RuntimeError("Could not connect to SQL database")

    query = """
        SELECT time, open, high, low, close, tick_volume AS volume, spread
        FROM (
            SELECT time, open, high, low, close, tick_volume, spread
            FROM price_data
            WHERE symbol = %s AND timeframe = %s
            ORDER BY time DESC
            LIMIT %s
        ) AS recent_rows
        ORDER BY time ASC
    """
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, (symbol, timeframe, int(limit)))
        df = pd.DataFrame(cursor.fetchall())
    finally:
        cursor.close()
        close_db(connection)

    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time")


def count_gap_events(frame: pd.DataFrame, timeframe: str) -> int:
    expected_minutes = timeframe_to_minutes(timeframe)
    if expected_minutes is None or len(frame) < 2:
        return 0
    deltas = frame.index.to_series().diff().dropna()
    threshold = pd.Timedelta(minutes=expected_minutes * 1.5)
    return int((deltas > threshold).sum())


def _candlestick_width(frame: pd.DataFrame) -> float:
    return compressed_candle_width()


def plot_candles_with_pivots(
    frame: pd.DataFrame,
    pivots: pd.DataFrame,
    spec: ExampleSpec,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = build_compressed_time_axis(frame)
    x_values = time_axis.x_values
    width = _candlestick_width(frame)

    up_color = "#0077BB"
    down_color = "#CC3311"
    neutral_color = "#6B7280"

    for x_value, (_, row) in zip(x_values, frame.iterrows()):
        open_price = float(row["open"])
        high_price = float(row["high"])
        low_price = float(row["low"])
        close_price = float(row["close"])
        color = up_color if close_price >= open_price else down_color
        ax.vlines(x_value, low_price, high_price, color=color, linewidth=0.8, alpha=0.85)
        body_low = min(open_price, close_price)
        body_height = abs(close_price - open_price)
        if body_height == 0:
            body_height = max((high_price - low_price) * 0.01, 1e-8)
            color = neutral_color
        ax.add_patch(
            Rectangle(
                (x_value - width / 2, body_low),
                width,
                body_height,
                facecolor=color,
                edgecolor=color,
                alpha=0.8,
                linewidth=0.6,
            )
        )

    expected_minutes = timeframe_to_minutes(spec.timeframe)
    if expected_minutes is not None and len(frame) >= 2:
        threshold = pd.Timedelta(minutes=expected_minutes * 1.5)
        times = frame.index.to_series()
        for current_time, delta in times.diff().dropna().items():
            if delta > threshold:
                x_gap = time_axis.to_x(current_time)
                if x_gap is not None:
                    ax.axvline(x_gap, color="#9CA3AF", linestyle=":", linewidth=0.8, alpha=0.35)

    events = extract_pivot_events(pivots)
    confirmed = events[events["pivot_state"].isin(["confirmed_high", "confirmed_low"])]
    price_padding = max(float(frame["high"].max() - frame["low"].min()) * 0.015, 1e-8)

    for _, event in confirmed.iterrows():
        extreme_time = event["pivot_extreme_time"]
        detection_time = event["pivot_detected_at"]
        extreme_x = time_axis.to_x(extreme_time)
        if extreme_x is None:
            continue
        detection_x = time_axis.to_x(detection_time)
        if detection_x is None:
            detection_x = extreme_x
        price = float(event["pivot_extreme_price"])
        if event["pivot_state"] == "confirmed_high":
            marker = "v"
            color = "#EE7733"
            y_value = price + price_padding
        else:
            marker = "^"
            color = "#009988"
            y_value = price - price_padding
        ax.scatter(
            [extreme_x],
            [y_value],
            marker=marker,
            s=64,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            zorder=5,
            label=event["pivot_state"],
        )
        if detection_x != extreme_x:
            ax.plot(
                [extreme_x, detection_x],
                [y_value, y_value],
                color=color,
                linestyle=":",
                linewidth=0.9,
                alpha=0.65,
            )

    ambiguous = events[events["pivot_state"] == "ambiguous_noise"]
    if not ambiguous.empty:
        ambiguous_x = [time_axis.to_x(timestamp) for timestamp in ambiguous.index if time_axis.to_x(timestamp) is not None]
        ambiguous_y = [float(frame.loc[timestamp, "close"]) for timestamp in ambiguous.index if timestamp in frame.index]
        if ambiguous_x and ambiguous_y:
            ax.scatter(
                ambiguous_x,
                ambiguous_y,
                marker="x",
                s=34,
                color="#6B7280",
                linewidth=1.0,
                alpha=0.7,
                zorder=4,
                label="ambiguous_noise",
            )

    ax.set_title(
        f"{spec.symbol} {spec.timeframe} - WaveCount Phase 1 pivots ({spec.example_type})",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_ylabel("Price")
    ax.grid(axis="y", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    time_axis.format_axis(ax)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        unique = {}
        for handle, label in zip(handles, labels):
            unique.setdefault(label, handle)
        ax.legend(unique.values(), unique.keys(), loc="best", fontsize=9)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _events_for_export(events: pd.DataFrame, spec: ExampleSpec) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(
            columns=[
                "example_id",
                "group",
                "symbol",
                "timeframe",
                "example_type",
                "timestamp",
                "pivot_state",
                "pivot_type",
                "pivot_extreme_time",
                "pivot_detected_at",
                "pivot_extreme_price",
                "confirmation_lag_bars",
                "visibility_score",
                "atr",
                "lookahead_safe",
                "is_candidate",
                "is_confirmed",
                "is_ambiguous",
                "reason",
            ]
        )
    export = events.reset_index(drop=True).copy()
    export["example_id"] = spec.example_id
    export["group"] = spec.group
    export["example_type"] = spec.example_type
    ordered = [
        "example_id",
        "group",
        "symbol",
        "timeframe",
        "example_type",
        "timestamp",
        "pivot_state",
        "pivot_type",
        "pivot_extreme_time",
        "pivot_detected_at",
        "pivot_extreme_price",
        "confirmation_lag_bars",
        "visibility_score",
        "atr",
        "lookahead_safe",
        "is_candidate",
        "is_confirmed",
        "is_ambiguous",
        "reason",
    ]
    return export[[column for column in ordered if column in export.columns]]


def write_report(
    output_dir: Path,
    config: PivotConfig,
    examples_df: pd.DataFrame,
    pivots_df: pd.DataFrame,
    elapsed_seconds: float,
) -> None:
    report_path = output_dir / "WAVECOUNT_PHASE1_REPORT.md"
    successful_examples = examples_df[examples_df["status"] == "ok"] if not examples_df.empty else examples_df
    total_confirmed = int(pivots_df["is_confirmed"].sum()) if not pivots_df.empty and "is_confirmed" in pivots_df else 0
    total_ambiguous = int(pivots_df["is_ambiguous"].sum()) if not pivots_df.empty and "is_ambiguous" in pivots_df else 0
    lookahead_violations = 0
    if not pivots_df.empty and {"is_confirmed", "pivot_detected_at", "pivot_extreme_time"}.issubset(pivots_df.columns):
        confirmed = pivots_df[pivots_df["is_confirmed"]].copy()
        if not confirmed.empty:
            detected = pd.to_datetime(confirmed["pivot_detected_at"], errors="coerce")
            extreme = pd.to_datetime(confirmed["pivot_extreme_time"], errors="coerce")
            lookahead_violations = int((detected < extreme).sum())

    lines = [
        "# WaveCount Phase 1 - pivotes causales y galeria visual",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha generado una galeria offline de pivotes WaveCount Fase 1 usando datos SQL existentes.",
        "La salida no genera senales, no filtra entradas y no modifica ENBOLSA, Menendez, RiskGuard ni Live Watcher.",
        "",
        "## Configuracion",
        "",
        f"- `left_bars`: {config.left_bars}",
        f"- `confirmation_bars`: {config.confirmation_bars}",
        f"- `atr_period`: {config.atr_period}",
        f"- `min_atr_multiplier`: {config.min_atr_multiplier}",
        f"- `min_relative_move_pct`: {config.min_relative_move_pct}",
        f"- `min_bars_between_pivots`: {config.min_bars_between_pivots}",
        "",
        "## Resultados",
        "",
        f"- ejemplos procesados correctamente: {len(successful_examples)}",
        f"- eventos confirmados: {total_confirmed}",
        f"- eventos ambiguos/ruido: {total_ambiguous}",
        f"- violaciones `pivot_detected_at < pivot_extreme_time`: {lookahead_violations}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Archivos generados",
        "",
        "- `tables/pivots_examples.csv`",
        "- `tables/example_windows.csv`",
        "- `charts/*.png`",
        "- `run_meta.json`",
        "",
        "## Lectura anti look-ahead",
        "",
        "Un pivote confirmado marca dos tiempos distintos:",
        "",
        "- `pivot_extreme_time`: vela donde estuvo el maximo/minimo visual.",
        "- `pivot_detected_at`: vela en la que el algoritmo pudo confirmarlo tras la latencia.",
        "",
        "Para cualquier uso futuro en tiempo real debe respetarse `pivot_detected_at`. Usar el extremo como si se conociera antes seria leakage.",
        "",
        "## Limitaciones",
        "",
        "- Esta fase solo detecta pivotes y ruido/ambiguedad local.",
        "- No implementa conteo 1-2-3-4-5 ni A-B-C.",
        "- No decide si un contexto es operable.",
        "- Los ejemplos son diagnosticos visuales, no una validacion estadistica.",
        "- Los datos SQL usados pueden estar desactualizados para live; aqui no se actualiza MT5.",
        "",
        "## Siguiente paso",
        "",
        "Implementar conteo candidato completo 1-2-3-4-5 / A-B-C en modulo aislado, usando estos pivotes con estados candidatos y confirmados, todavia sin senales operativas.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_gallery(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: PivotConfig | None = None,
    examples: tuple[ExampleSpec, ...] = DEFAULT_EXAMPLES,
) -> dict:
    config = config or PivotConfig()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()

    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    all_events = []
    window_rows = []

    for spec in examples:
        chart_path = charts_dir / f"{spec.example_id}.png"
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            if frame.empty:
                raise RuntimeError("no rows returned from SQL")
            pivots = detect_causal_pivots(
                frame,
                config=config,
                symbol=spec.symbol,
                timeframe=spec.timeframe,
            )
            events = extract_pivot_events(pivots)
            plot_candles_with_pivots(frame, pivots, spec, chart_path)
            all_events.append(_events_for_export(events, spec))
            window_rows.append(
                {
                    "example_id": spec.example_id,
                    "group": spec.group,
                    "symbol": spec.symbol,
                    "timeframe": spec.timeframe,
                    "example_type": spec.example_type,
                    "status": "ok",
                    "rows": len(frame),
                    "first_time": frame.index.min().isoformat(),
                    "last_time": frame.index.max().isoformat(),
                    "gap_events": count_gap_events(frame, spec.timeframe),
                    "confirmed_highs": int((events["pivot_state"] == "confirmed_high").sum()) if not events.empty else 0,
                    "confirmed_lows": int((events["pivot_state"] == "confirmed_low").sum()) if not events.empty else 0,
                    "ambiguous_count": int((events["pivot_state"] == "ambiguous_noise").sum()) if not events.empty else 0,
                    "chart_path": str(chart_path.relative_to(output_dir)),
                    "error": "",
                }
            )
        except Exception as exc:
            window_rows.append(
                {
                    "example_id": spec.example_id,
                    "group": spec.group,
                    "symbol": spec.symbol,
                    "timeframe": spec.timeframe,
                    "example_type": spec.example_type,
                    "status": "error",
                    "rows": 0,
                    "first_time": "",
                    "last_time": "",
                    "gap_events": 0,
                    "confirmed_highs": 0,
                    "confirmed_lows": 0,
                    "ambiguous_count": 0,
                    "chart_path": "",
                    "error": str(exc),
                }
            )

    pivots_df = pd.concat(all_events, ignore_index=True) if all_events else _events_for_export(pd.DataFrame(), DEFAULT_EXAMPLES[0])
    examples_df = pd.DataFrame(window_rows)
    pivots_df.to_csv(tables_dir / "pivots_examples.csv", index=False)
    examples_df.to_csv(tables_dir / "example_windows.csv", index=False)

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, config, examples_df, pivots_df, elapsed_seconds)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "config": asdict(config),
        "examples": [asdict(item) for item in examples],
        "outputs": {
            "pivots_examples": str((tables_dir / "pivots_examples.csv").relative_to(output_dir)),
            "example_windows": str((tables_dir / "example_windows.csv").relative_to(output_dir)),
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE1_REPORT.md",
        },
        "notes": [
            "No MT5 update was executed.",
            "No strategy/backtest/riskguard/live watcher files are modified by the gallery.",
            "Confirmed pivots must be consumed from pivot_detected_at, not pivot_extreme_time.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 1 offline pivot gallery.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--left-bars", type=int, default=PivotConfig.left_bars)
    parser.add_argument("--confirmation-bars", type=int, default=PivotConfig.confirmation_bars)
    parser.add_argument("--atr-period", type=int, default=PivotConfig.atr_period)
    parser.add_argument("--min-atr-multiplier", type=float, default=PivotConfig.min_atr_multiplier)
    parser.add_argument("--min-relative-move-pct", type=float, default=PivotConfig.min_relative_move_pct)
    parser.add_argument("--min-bars-between-pivots", type=int, default=PivotConfig.min_bars_between_pivots)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PivotConfig(
        left_bars=args.left_bars,
        confirmation_bars=args.confirmation_bars,
        atr_period=args.atr_period,
        min_atr_multiplier=args.min_atr_multiplier,
        min_relative_move_pct=args.min_relative_move_pct,
        min_bars_between_pivots=args.min_bars_between_pivots,
    )
    meta = build_gallery(output_dir=args.output_dir, config=config)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
