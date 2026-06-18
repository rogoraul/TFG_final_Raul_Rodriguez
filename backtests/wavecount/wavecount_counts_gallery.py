from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

from .wavecount_counts import CountConfig, build_candidate_counts, count_config_to_dict
from .wavecount_gallery import DEFAULT_EXAMPLES, fetch_recent_ohlc
from .wavecount_plotting import CompressedTimeAxis, build_compressed_time_axis, compressed_candle_width


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase1_6_swing_degrees_2026-05-17"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_candidate_counts_2026-05-17"

STATE_STYLE = {
    "candidate_impulse": {"color": "#0077BB", "label": "candidate impulse", "linewidth": 1.8},
    "candidate_abc": {"color": "#009988", "label": "candidate ABC", "linewidth": 1.8},
    "invalidated_count": {"color": "#CC3311", "label": "invalidated", "linewidth": 1.5},
    "ambiguous_count": {"color": "#EE7733", "label": "ambiguous", "linewidth": 1.5},
}


def _candlestick_width(frame: pd.DataFrame) -> float:
    return compressed_candle_width()


def _plot_candles(ax, frame: pd.DataFrame) -> CompressedTimeAxis:
    time_axis = build_compressed_time_axis(frame)
    x_values = time_axis.x_values
    width = _candlestick_width(frame)
    for x_value, (_, row) in zip(x_values, frame.iterrows()):
        open_price = float(row["open"])
        high_price = float(row["high"])
        low_price = float(row["low"])
        close_price = float(row["close"])
        color = "#0077BB" if close_price >= open_price else "#CC3311"
        ax.vlines(x_value, low_price, high_price, color=color, linewidth=0.65, alpha=0.55)
        body_low = min(open_price, close_price)
        body_height = abs(close_price - open_price)
        if body_height == 0:
            body_height = max((high_price - low_price) * 0.01, 1e-8)
            color = "#6B7280"
        ax.add_patch(
            Rectangle(
                (x_value - width / 2, body_low),
                width,
                body_height,
                facecolor=color,
                edgecolor=color,
                alpha=0.45,
                linewidth=0.45,
            )
        )
    return time_axis


def _time_to_x(frame: pd.DataFrame) -> dict[pd.Timestamp, float]:
    return build_compressed_time_axis(frame).time_to_x


def _plot_structural_chain(
    ax,
    frame: pd.DataFrame,
    pivots: pd.DataFrame,
    degree: str,
    color: str,
    label: str,
    time_axis: CompressedTimeAxis | None = None,
) -> None:
    subset = pivots[pivots["swing_degree"] == degree].copy()
    if subset.empty:
        return
    subset["pivot_extreme_time"] = pd.to_datetime(subset["pivot_extreme_time"], errors="coerce")
    subset = subset.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"])
    time_axis = time_axis or build_compressed_time_axis(frame)
    points = []
    for _, row in subset.iterrows():
        extreme_time = row["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        points.append((x_value, float(row["pivot_extreme_price"])))
    if not points:
        return
    xs, ys = zip(*points)
    ax.plot(xs, ys, color=color, linewidth=1.0, alpha=0.38, marker="o", markersize=3.5, label=label, zorder=3)


def _candidate_rank(row: pd.Series) -> int:
    state = row["count_state"]
    if state.startswith("candidate"):
        return 0
    if state == "ambiguous_count":
        return 1
    if state == "invalidated_count":
        return 2
    return 3


def _select_chart_count(counts: pd.DataFrame, pattern_type: str) -> pd.Series | None:
    subset = counts[counts["pattern_type"] == pattern_type].copy()
    if subset.empty:
        return None
    subset["_rank"] = subset.apply(_candidate_rank, axis=1)
    subset["count_detected_at"] = pd.to_datetime(subset["count_detected_at"], errors="coerce")
    subset = subset.sort_values(["_rank", "count_detected_at"], ascending=[True, False])
    return subset.iloc[0]


def _plot_count(
    ax,
    frame: pd.DataFrame,
    legs: pd.DataFrame,
    count_row: pd.Series,
    time_axis: CompressedTimeAxis | None = None,
) -> None:
    count_id = count_row["count_id"]
    subset = legs[legs["count_id"] == count_id].copy()
    if subset.empty:
        return
    subset["pivot_extreme_time"] = pd.to_datetime(subset["pivot_extreme_time"], errors="coerce")
    subset = subset.sort_values("point_order")
    time_axis = time_axis or build_compressed_time_axis(frame)
    points = []
    for _, row in subset.iterrows():
        extreme_time = row["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        points.append((x_value, float(row["pivot_extreme_price"]), str(row["point_label"])))
    if len(points) < 2:
        return
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    labels = [item[2] for item in points]
    style = STATE_STYLE.get(count_row["count_state"], STATE_STYLE["ambiguous_count"])
    ax.plot(
        xs,
        ys,
        color=style["color"],
        linewidth=style["linewidth"],
        alpha=0.92,
        marker="o",
        markersize=6,
        label=f"{style['label']} {count_row['direction']}",
        zorder=7,
    )
    y_padding = max((max(ys) - min(ys)) * 0.04, abs(ys[-1]) * 0.0002, 1e-8)
    for x_value, y_value, label in points:
        ax.text(
            x_value,
            y_value + y_padding,
            label,
            color=style["color"],
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="bottom",
            zorder=8,
        )


def plot_counts_example(
    frame: pd.DataFrame,
    pivots: pd.DataFrame,
    counts: pd.DataFrame,
    legs: pd.DataFrame,
    output_path: Path,
    title: str,
) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(ax, frame)
    _plot_structural_chain(ax, frame, pivots, "major", "#94A3B8", "major context", time_axis)
    _plot_structural_chain(ax, frame, pivots, "intermediate", "#111827", "intermediate swings", time_axis)

    selected: dict[str, str] = {}
    for pattern_type in ["impulse", "abc"]:
        row = _select_chart_count(counts, pattern_type)
        if row is None:
            continue
        selected[pattern_type] = str(row["count_id"])
        _plot_count(ax, frame, legs, row, time_axis)

    ax.set_title(title, fontsize=14, fontweight="bold")
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
    return selected


def write_report(
    output_dir: Path,
    counts: pd.DataFrame,
    summary: pd.DataFrame,
    elapsed_seconds: float,
    chart_rows: list[dict[str, str]],
) -> None:
    state_counts = counts["count_state"].value_counts().to_dict() if not counts.empty else {}
    pattern_counts = counts.groupby(["pattern_type", "count_state"]).size().to_dict() if not counts.empty else {}
    lookahead_violations = int((~counts["lookahead_safe"].astype(bool)).sum()) if not counts.empty else 0
    candidate_impulses = int((counts["count_state"] == "candidate_impulse").sum()) if not counts.empty else 0
    candidate_abcs = int((counts["count_state"] == "candidate_abc").sum()) if not counts.empty else 0
    if lookahead_violations:
        decision = "La Fase 2 no queda apta: hay incidencias anti look-ahead que deben corregirse antes de avanzar."
    elif candidate_impulses:
        decision = (
            "La Fase 2 queda apta como prototipo metodologico de conteo candidato, "
            "pero requiere revision visual manual antes de dashboard o estadistica."
        )
    elif candidate_abcs:
        decision = (
            "La Fase 2 queda implementada de forma conservadora, pero la muestra visual no contiene impulsos 1-2-3-4-5 limpios; "
            "antes de dashboard o estadistica conviene revisar mas ventanas y confirmar si el grado `intermediate` es suficiente para impulsos completos."
        )
    else:
        decision = (
            "La Fase 2 necesita ajuste antes de avanzar: la muestra no produce conteos candidatos limpios y debe revisarse el grado o la ventana visual."
        )
    lines = [
        "# WaveCount Phase 2 - conteo Elliott candidato",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha generado un conteo candidato aislado `1-2-3-4-5 / A-B-C` sobre structural swings `intermediate`.",
        "El grado `major` se usa solo como contexto superior. No se usan raw pivots directamente.",
        "",
        "No se generan senales, no se filtran entradas, no se toca ninguna estrategia, no se conecta MT5 y no se ejecutan backtests.",
        "",
        "## Resultado global",
        "",
        f"- estados: {state_counts}",
        f"- patron/estado: {pattern_counts}",
        f"- violaciones `count_detected_at < max(structural_detected_at usadas)`: {lookahead_violations}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Graficos",
        "",
    ]
    for row in chart_rows:
        lines.append(f"- `{row['example_id']}`: {row['status']} - {row.get('chart_path', '')}")
    lines.extend(
        [
            "",
            "## Lectura metodologica",
            "",
            "- `candidate_impulse` significa que la ventana cumple las invalidaciones basicas de impulso.",
            "- `candidate_abc` significa que la ventana cumple una lectura ABC basica.",
            "- `invalidated_count` conserva la ventana y explica por que no debe aceptarse.",
            "- `ambiguous_count` evita forzar numeracion en estructuras poco claras.",
            "",
            "La salida es diagnostica. No debe interpretarse como senal ni como filtro operativo.",
            "",
            "## Decision",
            "",
            decision,
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_counts_gallery(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: CountConfig | None = None,
) -> dict:
    config = config or CountConfig()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    pivots = pd.read_csv(input_dir / "tables" / "swing_degrees_pivots.csv")
    result = build_candidate_counts(pivots, config=config, group_columns=["example_id"])
    counts = result["candidate_counts"]
    legs = result["count_legs"]
    summary = result["count_summary"]

    counts.to_csv(tables_dir / "candidate_counts.csv", index=False)
    legs.to_csv(tables_dir / "count_legs.csv", index=False)
    summary.to_csv(tables_dir / "count_summary.csv", index=False)

    chart_rows: list[dict[str, str]] = []
    for spec in DEFAULT_EXAMPLES:
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            subset_pivots = pivots[pivots["example_id"] == spec.example_id].copy()
            subset_counts = counts[counts["example_id"] == spec.example_id].copy()
            subset_legs = legs[legs["example_id"] == spec.example_id].copy()
            chart_path = charts_dir / f"{spec.example_id}_counts.png"
            selected = plot_counts_example(
                frame,
                subset_pivots,
                subset_counts,
                subset_legs,
                chart_path,
                f"{spec.symbol} {spec.timeframe} - WaveCount Phase 2 candidate counts",
            )
            chart_rows.append(
                {
                    "example_id": spec.example_id,
                    "chart_path": str(chart_path.relative_to(output_dir)),
                    "status": "ok",
                    "selected_impulse": selected.get("impulse", ""),
                    "selected_abc": selected.get("abc", ""),
                    "error": "",
                }
            )
        except Exception as exc:
            chart_rows.append(
                {
                    "example_id": spec.example_id,
                    "chart_path": "",
                    "status": "error",
                    "selected_impulse": "",
                    "selected_abc": "",
                    "error": str(exc),
                }
            )

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, counts, summary, elapsed_seconds, chart_rows)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "input_dir": str(input_dir),
        "config": count_config_to_dict(config),
        "charts": chart_rows,
        "outputs": {
            "candidate_counts": "tables/candidate_counts.csv",
            "count_legs": "tables/count_legs.csv",
            "count_summary": "tables/count_summary.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE2_REPORT.md",
        },
        "notes": [
            "No raw pivots are consumed directly for counts.",
            "No trading signals, filters, MT5 connection or backtests are produced.",
            "count_detected_at is the max structural_detected_at of the swings used.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2 candidate count gallery.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--primary-degree", default=CountConfig.primary_degree)
    parser.add_argument("--context-degree", default=CountConfig.context_degree)
    parser.add_argument("--major-conflict-mode", choices=["soft", "invalidate"], default=CountConfig.major_conflict_mode)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CountConfig(
        primary_degree=args.primary_degree,
        context_degree=args.context_degree,
        major_conflict_mode=args.major_conflict_mode,
    )
    meta = build_counts_gallery(args.input_dir, args.output_dir, config=config)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
