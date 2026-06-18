from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

from .wavecount_degrees import DEFAULT_SWING_DEGREES, build_swing_degrees, degree_count_table, is_monotonic_by_degree
from .wavecount_gallery import DEFAULT_EXAMPLES, DEFAULT_OUTPUT_DIR as PHASE1_OUTPUT_DIR, fetch_recent_ohlc
from .wavecount_plotting import build_compressed_time_axis, compressed_candle_width


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase1_6_swing_degrees_2026-05-17"

DEGREE_STYLE = {
    "minor": {"color": "#94A3B8", "linewidth": 0.9, "alpha": 0.55, "marker": "o", "size": 34},
    "intermediate": {"color": "#0077BB", "linewidth": 1.25, "alpha": 0.75, "marker": "s", "size": 46},
    "major": {"color": "#CC3311", "linewidth": 1.7, "alpha": 0.9, "marker": "D", "size": 58},
}


def _candlestick_width(frame: pd.DataFrame) -> float:
    return compressed_candle_width()


def _plot_candles(ax, frame: pd.DataFrame) -> None:
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


def plot_degree_comparison(
    frame: pd.DataFrame,
    degree_pivots: pd.DataFrame,
    output_path: Path,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(ax, frame)

    for degree in ["minor", "intermediate", "major"]:
        subset = degree_pivots[degree_pivots["swing_degree"] == degree].copy()
        if subset.empty:
            continue
        subset["pivot_extreme_time"] = pd.to_datetime(subset["pivot_extreme_time"], errors="coerce")
        points = []
        for _, row in subset.sort_values("structural_detected_at").iterrows():
            extreme_time = row["pivot_extreme_time"]
            x_value = time_axis.to_x(extreme_time)
            if x_value is None:
                continue
            points.append((x_value, float(row["pivot_extreme_price"])))
        if not points:
            continue
        xs, ys = zip(*points)
        style = DEGREE_STYLE[degree]
        ax.plot(
            xs,
            ys,
            color=style["color"],
            linewidth=style["linewidth"],
            alpha=style["alpha"],
            marker=style["marker"],
            markersize=style["size"] ** 0.5,
            label=f"{degree} ({len(points)})",
            zorder=3 if degree == "minor" else 4 if degree == "intermediate" else 5,
        )

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Price")
    ax.grid(axis="y", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    time_axis.format_axis(ax)
    ax.legend(loc="best", fontsize=9)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _degree_specs_to_dict() -> list[dict]:
    return [
        {
            "name": spec.name,
            "config": asdict(spec.config),
        }
        for spec in DEFAULT_SWING_DEGREES
    ]


def write_report(output_dir: Path, summary: pd.DataFrame, elapsed_seconds: float, monotonic: bool) -> None:
    counts = degree_count_table(summary)
    total_by_degree = summary.groupby("swing_degree")["structural_pivots"].sum().to_dict() if not summary.empty else {}
    suggested_degree = "intermediate"
    major_sparse = []
    if not counts.empty and "major" in counts.columns:
        major_sparse = [idx for idx, value in counts["major"].items() if int(value) < 8]
    lines = [
        "# WaveCount Phase 1.6 - grados de swing",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha generado una comparacion multi-escala de structural pivots: minor, intermediate y major.",
        "No hay conteo Elliott, no hay senales, no hay filtros operativos y no se toca ninguna estrategia.",
        "",
        "## Grados",
        "",
        "- minor: 2 ATR / 0.2% / 4 barras",
        "- intermediate: 3 ATR / 0.3% / 6 barras",
        "- major: 5 ATR / 0.5% / 10 barras",
        "",
        "## Resultado global",
        "",
        f"- pivotes por grado: {total_by_degree}",
        f"- monotonia minor >= intermediate >= major por ejemplo: {monotonic}",
        f"- ventanas con major demasiado escaso (<8 pivotes): {major_sparse}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Decision",
        "",
        f"Grado recomendado para iniciar Fase 2: `{suggested_degree}`.",
        "",
        "Motivo: `minor` sigue siendo util para microestructura, `major` es mas limpio pero queda escaso en algunas ventanas, e `intermediate` mantiene una lectura visual suficiente sin estar tan denso como los raw pivots.",
        "",
        "Fase 2 puede avanzar solo como conteo candidato aislado sobre `intermediate`, comparando contra `major` como contexto superior y sin generar senales.",
    ]
    (output_dir / "WAVECOUNT_PHASE1_6_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_degrees_gallery(
    phase1_dir: Path = PHASE1_OUTPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(phase1_dir / "tables" / "pivots_examples.csv")
    result = build_swing_degrees(raw, group_columns=["example_id"])
    pivots = result["swing_degrees_pivots"]
    discarded = result["swing_degrees_discarded"]
    summary = result["swing_degrees_summary"]

    pivots.to_csv(tables_dir / "swing_degrees_pivots.csv", index=False)
    discarded.to_csv(tables_dir / "swing_degrees_discarded.csv", index=False)
    summary.to_csv(tables_dir / "swing_degrees_summary.csv", index=False)

    chart_rows = []
    for spec in DEFAULT_EXAMPLES:
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            subset = pivots[pivots["example_id"] == spec.example_id].copy()
            chart_path = charts_dir / f"{spec.example_id}_degrees.png"
            plot_degree_comparison(
                frame,
                subset,
                chart_path,
                f"{spec.symbol} {spec.timeframe} - WaveCount Phase 1.6 swing degrees",
            )
            chart_rows.append({"example_id": spec.example_id, "chart_path": str(chart_path.relative_to(output_dir)), "status": "ok", "error": ""})
        except Exception as exc:
            chart_rows.append({"example_id": spec.example_id, "chart_path": "", "status": "error", "error": str(exc)})

    elapsed_seconds = perf_counter() - start
    monotonic = is_monotonic_by_degree(summary)
    write_report(output_dir, summary, elapsed_seconds, monotonic)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "phase1_dir": str(phase1_dir),
        "degree_specs": _degree_specs_to_dict(),
        "monotonic_minor_intermediate_major": monotonic,
        "charts": chart_rows,
        "outputs": {
            "swing_degrees_pivots": "tables/swing_degrees_pivots.csv",
            "swing_degrees_summary": "tables/swing_degrees_summary.csv",
            "swing_degrees_discarded": "tables/swing_degrees_discarded.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE1_6_REPORT.md",
        },
        "notes": [
            "No Elliott count is implemented.",
            "No MT5 update or backtest was executed.",
            "Fase 2 should consume a selected swing_degree, not raw pivots.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 1.6 swing degree gallery.")
    parser.add_argument("--phase1-dir", type=Path, default=PHASE1_OUTPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_degrees_gallery(args.phase1_dir, args.output_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
