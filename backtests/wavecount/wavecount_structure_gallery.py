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

from .wavecount_gallery import DEFAULT_EXAMPLES, DEFAULT_OUTPUT_DIR as PHASE1_OUTPUT_DIR, fetch_recent_ohlc
from .wavecount_plotting import build_compressed_time_axis, compressed_candle_width
from .wavecount_structure import StructuralPivotConfig, build_structural_pivots_by_group


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase1_5_structural_swings_2026-05-17"


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
        ax.vlines(x_value, low_price, high_price, color=color, linewidth=0.7, alpha=0.65)
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
                alpha=0.55,
                linewidth=0.5,
            )
        )
    return time_axis


def plot_raw_vs_structural(
    frame: pd.DataFrame,
    raw_confirmed: pd.DataFrame,
    structural: pd.DataFrame,
    output_path: Path,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(ax, frame)
    price_padding = max(float(frame["high"].max() - frame["low"].min()) * 0.012, 1e-8)

    for _, row in raw_confirmed.iterrows():
        extreme_time = row["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        price = float(row["pivot_extreme_price"])
        if row["pivot_type"] == "high":
            marker = "v"
            y_value = price + price_padding
        else:
            marker = "^"
            y_value = price - price_padding
        ax.scatter([x_value], [y_value], marker=marker, s=28, color="#9CA3AF", alpha=0.45, zorder=3)

    structural_points = []
    for _, row in structural.sort_values("structural_detected_at").iterrows():
        extreme_time = row["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        price = float(row["pivot_extreme_price"])
        structural_points.append((x_value, price))
        if row["pivot_type"] == "high":
            marker = "v"
            color = "#EE7733"
            y_value = price + price_padding * 2
        else:
            marker = "^"
            color = "#009988"
            y_value = price - price_padding * 2
        ax.scatter([x_value], [y_value], marker=marker, s=92, color=color, edgecolor="white", linewidth=0.9, zorder=5)

    if len(structural_points) >= 2:
        xs, ys = zip(*structural_points)
        ax.plot(xs, ys, color="#111827", linewidth=1.15, alpha=0.72, zorder=4, label="structural swing chain")

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Price")
    ax.grid(axis="y", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    time_axis.format_axis(ax)
    ax.scatter([], [], marker="^", s=30, color="#9CA3AF", alpha=0.45, label="raw pivots")
    ax.scatter([], [], marker="^", s=92, color="#009988", label="structural lows")
    ax.scatter([], [], marker="v", s=92, color="#EE7733", label="structural highs")
    ax.legend(loc="best", fontsize=9)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _summary_by_example(raw: pd.DataFrame, structural: pd.DataFrame, discarded: pd.DataFrame, config: StructuralPivotConfig) -> pd.DataFrame:
    rows = []
    for example_id, raw_group in raw.groupby("example_id", sort=False):
        structural_group = structural[structural["example_id"] == example_id] if not structural.empty else pd.DataFrame()
        discarded_group = discarded[discarded["example_id"] == example_id] if not discarded.empty else pd.DataFrame()
        ambiguous = int((discarded_group["structure_state"] == "ambiguous_structure").sum()) if not discarded_group.empty else 0
        minor = int((discarded_group["structure_state"] == "discarded_minor_pivot").sum()) if not discarded_group.empty else 0
        first = raw_group.iloc[0]
        rows.append(
            {
                "example_id": example_id,
                "group": first.get("group", ""),
                "symbol": first.get("symbol", ""),
                "timeframe": first.get("timeframe", ""),
                "raw_confirmed_pivots": len(raw_group),
                "structural_pivots": len(structural_group),
                "discarded_minor_pivots": minor,
                "ambiguous_structure": ambiguous,
                "compression_ratio": len(structural_group) / len(raw_group) if len(raw_group) else None,
                "min_leg_atr_multiplier": config.min_leg_atr_multiplier,
                "min_leg_relative_move_pct": config.min_leg_relative_move_pct,
                "min_leg_bars": config.min_leg_bars,
            }
        )
    return pd.DataFrame(rows)


def write_report(output_dir: Path, summary: pd.DataFrame, elapsed_seconds: float, config: StructuralPivotConfig) -> None:
    total_raw = int(summary["raw_confirmed_pivots"].sum()) if not summary.empty else 0
    total_structural = int(summary["structural_pivots"].sum()) if not summary.empty else 0
    ratio = total_structural / total_raw if total_raw else 0.0
    lines = [
        "# WaveCount Phase 1.5 - structural pivots / major swings",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha construido una capa aislada que comprime pivotes locales confirmados de Fase 1 en swings estructurales mayores.",
        "No implementa conteo Elliott, no genera senales y no toca ENBOLSA, Menendez, RiskGuard ni Live Watcher.",
        "",
        "## Configuracion",
        "",
        f"- `min_leg_atr_multiplier`: {config.min_leg_atr_multiplier}",
        f"- `min_leg_relative_move_pct`: {config.min_leg_relative_move_pct}",
        f"- `min_leg_bars`: {config.min_leg_bars}",
        "",
        "## Resultado global",
        "",
        f"- raw pivots confirmados: {total_raw}",
        f"- structural pivots: {total_structural}",
        f"- ratio de compresion: {ratio:.3f}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Lectura metodologica",
        "",
        "Los structural pivots son la entrada futura para conteo candidato. Los raw pivots siguen siendo la capa causal base.",
        "Cualquier conteo futuro debe usar `structural_detected_at`, nunca anticipar el extremo visual.",
        "",
        "## Decision",
        "",
        "Fase 1.5 queda apta como base inicial para Fase 2, con revision visual previa de los graficos comparativos.",
    ]
    (output_dir / "WAVECOUNT_PHASE1_5_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_structural_gallery(
    phase1_dir: Path = PHASE1_OUTPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: StructuralPivotConfig | None = None,
) -> dict:
    config = config or StructuralPivotConfig()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(phase1_dir / "tables" / "pivots_examples.csv")
    result = build_structural_pivots_by_group(raw, config=config, group_columns=["example_id"])
    structural = result["structural_pivots"]
    discarded = result["discarded_minor_pivots"]
    confirmed = raw[raw["is_confirmed"].astype(str).str.lower() == "true"].copy()
    for column in ["timestamp", "pivot_extreme_time", "pivot_detected_at"]:
        confirmed[column] = pd.to_datetime(confirmed[column], errors="coerce")
    summary = _summary_by_example(confirmed, structural, discarded, config)

    structural.to_csv(tables_dir / "structural_pivots.csv", index=False)
    discarded.to_csv(tables_dir / "discarded_minor_pivots.csv", index=False)
    summary.to_csv(tables_dir / "structure_summary.csv", index=False)

    chart_rows = []
    for spec in DEFAULT_EXAMPLES:
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            raw_example = confirmed[confirmed["example_id"] == spec.example_id].copy()
            structural_example = structural[structural["example_id"] == spec.example_id].copy()
            chart_path = charts_dir / f"{spec.example_id}_structural.png"
            plot_raw_vs_structural(
                frame,
                raw_example,
                structural_example,
                chart_path,
                f"{spec.symbol} {spec.timeframe} - WaveCount Phase 1.5 structural swings",
            )
            chart_rows.append({"example_id": spec.example_id, "chart_path": str(chart_path.relative_to(output_dir)), "status": "ok", "error": ""})
        except Exception as exc:
            chart_rows.append({"example_id": spec.example_id, "chart_path": "", "status": "error", "error": str(exc)})

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, summary, elapsed_seconds, config)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "phase1_dir": str(phase1_dir),
        "config": asdict(config),
        "charts": chart_rows,
        "outputs": {
            "structural_pivots": "tables/structural_pivots.csv",
            "discarded_minor_pivots": "tables/discarded_minor_pivots.csv",
            "structure_summary": "tables/structure_summary.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE1_5_REPORT.md",
        },
        "notes": [
            "No Elliott count is implemented.",
            "No MT5 update or backtest was executed.",
            "structural_detected_at must be respected by future phases.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 1.5 structural swing gallery.")
    parser.add_argument("--phase1-dir", type=Path, default=PHASE1_OUTPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-leg-atr-multiplier", type=float, default=StructuralPivotConfig.min_leg_atr_multiplier)
    parser.add_argument("--min-leg-relative-move-pct", type=float, default=StructuralPivotConfig.min_leg_relative_move_pct)
    parser.add_argument("--min-leg-bars", type=int, default=StructuralPivotConfig.min_leg_bars)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = StructuralPivotConfig(
        min_leg_atr_multiplier=args.min_leg_atr_multiplier,
        min_leg_relative_move_pct=args.min_leg_relative_move_pct,
        min_leg_bars=args.min_leg_bars,
    )
    meta = build_structural_gallery(args.phase1_dir, args.output_dir, config)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
