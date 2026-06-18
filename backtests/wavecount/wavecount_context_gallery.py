from __future__ import annotations

import argparse
import json
import textwrap
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .wavecount_config import PivotConfig
from .wavecount_context import (
    HTF_MAP,
    WaveContextConfig,
    align_htf_context,
    build_candidate_context,
    calculate_wave_context,
    context_config_to_dict,
)
from .wavecount_counts_gallery import _plot_candles, _plot_structural_chain
from .wavecount_gallery import fetch_recent_ohlc
from .wavecount_plotting import CompressedTimeAxis
from .wavecount_visual_review_gallery import (
    CATEGORY_STYLE,
    DEFAULT_VISUAL_REVIEW_SPECS,
    _build_source_tables,
    _candidate_counts_for_degrees,
    _points_from_count_legs,
    _points_from_degree_window,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h1_m30"


def _build_context_tables(
    context_config: WaveContextConfig,
    htf_rows: int,
    specs=DEFAULT_VISUAL_REVIEW_SPECS,
) -> dict[str, pd.DataFrame]:
    context_frames: list[pd.DataFrame] = []
    source_rows: list[dict[str, Any]] = []
    for spec in specs:
        row = {
            "example_id": spec.example_id,
            "group": spec.group,
            "symbol": spec.symbol,
            "timeframe": spec.timeframe,
            "htf_timeframe": HTF_MAP.get(spec.timeframe, ""),
            "status": "error",
            "ltf_rows": 0,
            "htf_rows": 0,
            "htf_status": "not_available",
            "error": "",
        }
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            if frame.empty or len(frame) < 80:
                raise RuntimeError(f"insufficient SQL rows: {len(frame)}")
            row["ltf_rows"] = len(frame)
            ltf_context = calculate_wave_context(
                frame,
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                example_id=spec.example_id,
                group=spec.group,
                config=context_config,
            )
            htf_timeframe = HTF_MAP.get(spec.timeframe)
            if htf_timeframe:
                try:
                    htf_frame = fetch_recent_ohlc(spec.symbol, htf_timeframe, htf_rows)
                    if htf_frame.empty:
                        raise RuntimeError(f"insufficient HTF SQL rows: {len(htf_frame)}")
                    row["htf_rows"] = len(htf_frame)
                    htf_context = calculate_wave_context(
                        htf_frame,
                        symbol=spec.symbol,
                        timeframe=htf_timeframe,
                        example_id=spec.example_id,
                        group=spec.group,
                        config=context_config,
                    )
                    aligned = align_htf_context(ltf_context, htf_context, htf_timeframe=htf_timeframe)
                    row["htf_status"] = "ok"
                except Exception as htf_exc:
                    aligned = align_htf_context(ltf_context, pd.DataFrame(), htf_timeframe=htf_timeframe)
                    row["htf_status"] = "error"
                    row["htf_error"] = str(htf_exc)
            else:
                aligned = align_htf_context(ltf_context, pd.DataFrame(), htf_timeframe="")
            row["status"] = "ok"
            context_frames.append(aligned)
        except Exception as exc:
            row["error"] = str(exc)
        source_rows.append(row)
    return {
        "wavecount_context": pd.concat(context_frames, ignore_index=True) if context_frames else pd.DataFrame(),
        "source_windows": pd.DataFrame(source_rows),
    }


def _plot_candidate_points(
    ax,
    frame: pd.DataFrame,
    degree_pivots: pd.DataFrame,
    count_legs: pd.DataFrame,
    row: pd.Series,
    time_axis: CompressedTimeAxis,
) -> None:
    if row["source_table"] == "candidate_counts":
        points = _points_from_count_legs(count_legs, row)
    else:
        points = _points_from_degree_window(degree_pivots, row)
    if points.empty:
        return

    points["pivot_extreme_time"] = pd.to_datetime(points["pivot_extreme_time"], errors="coerce")
    xy = []
    for _, point in points.iterrows():
        extreme_time = point["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        xy.append((x_value, float(point["pivot_extreme_price"]), str(point["plot_label"])))
    if not xy:
        return

    style = CATEGORY_STYLE.get(str(row["review_category"]), CATEGORY_STYLE["near_miss"])
    xs = [item[0] for item in xy]
    ys = [item[1] for item in xy]
    ax.plot(xs, ys, color=style["color"], linewidth=2.0, marker="o", markersize=6.5, label=style["label"], zorder=7)
    y_padding = max((max(ys) - min(ys)) * 0.04, abs(ys[-1]) * 0.0002, 1e-8)
    for x_value, y_value, label in xy:
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


def plot_context_candidate(
    frame: pd.DataFrame,
    context: pd.DataFrame,
    degree_pivots: pd.DataFrame,
    count_legs: pd.DataFrame,
    row: pd.Series,
    output_path: Path,
) -> None:
    fig, (ax_price, ax_ewo) = plt.subplots(
        2,
        1,
        figsize=(14, 8.2),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1]},
    )
    fig.patch.set_facecolor("white")

    time_axis = _plot_candles(ax_price, frame)
    plot_context = context[context["example_id"] == row["example_id"]].copy()
    plot_context["timestamp"] = pd.to_datetime(plot_context["timestamp"], errors="coerce")
    plot_context["x_value"] = time_axis.to_x_series(plot_context["timestamp"])
    plot_context = plot_context.dropna(subset=["x_value"]).copy()
    x_values = plot_context["x_value"].to_numpy(dtype=float)
    ax_price.plot(x_values, plot_context["ema_50"], color="#0077BB", linewidth=1.2, label="EMA 50", zorder=5)
    ax_price.plot(x_values, plot_context["ema_150"], color="#CC3311", linewidth=1.2, label="EMA 150", zorder=5)

    example_pivots = degree_pivots[degree_pivots["example_id"] == row["example_id"]]
    _plot_structural_chain(ax_price, frame, example_pivots, "major", "#94A3B8", "major context", time_axis)
    _plot_structural_chain(ax_price, frame, example_pivots, str(row["swing_degree"]), "#111827", f"{row['swing_degree']} swings", time_axis)
    _plot_candidate_points(ax_price, frame, degree_pivots, count_legs, row, time_axis)

    ax_ewo.axhline(0, color="#6B7280", linewidth=0.9, alpha=0.65)
    ewo = pd.to_numeric(plot_context["ewo_5_35"], errors="coerce")
    ax_ewo.plot(x_values, ewo, color="#7C3AED", linewidth=1.05, label="EWO 5-35")
    ax_ewo.fill_between(x_values, 0, ewo, where=ewo >= 0, color="#009988", alpha=0.18)
    ax_ewo.fill_between(x_values, 0, ewo, where=ewo < 0, color="#CC3311", alpha=0.14)

    context_line = (
        f"{row['trend_context_label']} | score={row['context_score']} | "
        f"LTF={row.get('end_ltf_ema_alignment', '')}/{row.get('end_ltf_price_vs_ema_band', '')} | "
        f"HTF={row.get('htf_timeframe', '')}:{row.get('htf_ema_alignment', '')}"
    )
    context_line = textwrap.shorten(context_line, width=86, placeholder="...")
    reason = str(row.get("context_reason", ""))
    reason = textwrap.shorten(reason, width=86, placeholder="...")
    ax_price.set_title(
        f"{row['candidate_id']} | {row['symbol']} {row['timeframe']} {row['swing_degree']}\n"
        f"{context_line}\n"
        f"{reason}",
        fontsize=10.5,
        fontweight="bold",
    )
    ax_price.set_ylabel("Price")
    ax_ewo.set_ylabel("EWO")
    ax_ewo.set_xlabel("Time")
    for axis in [ax_price, ax_ewo]:
        axis.grid(axis="y", alpha=0.22)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)

    time_axis.format_axis(ax_ewo)
    handles, labels = ax_price.get_legend_handles_labels()
    if handles:
        unique = {}
        for handle, label in zip(handles, labels):
            unique.setdefault(label, handle)
        ax_price.legend(unique.values(), unique.keys(), loc="best", fontsize=8.5)
    ax_ewo.legend(loc="best", fontsize=8.5)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _summary(context: pd.DataFrame, candidate_context: pd.DataFrame, source_windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append({"metric": "source_windows_ok", "value": int((source_windows["status"] == "ok").sum())})
    rows.append({"metric": "source_windows_error", "value": int((source_windows["status"] == "error").sum())})
    rows.append({"metric": "htf_windows_ok", "value": int((source_windows["htf_status"] == "ok").sum())})
    rows.append({"metric": "htf_windows_error", "value": int((source_windows["htf_status"] == "error").sum())})
    rows.append({"metric": "wavecount_context_rows", "value": int(len(context))})
    rows.append({"metric": "candidate_context_rows", "value": int(len(candidate_context))})
    if "htf_lookahead_safe" in context.columns:
        rows.append({"metric": "htf_lookahead_violations", "value": int((~context["htf_lookahead_safe"].astype(bool)).sum())})
    if not candidate_context.empty:
        for label, count in candidate_context["trend_context_label"].value_counts().items():
            rows.append({"metric": f"trend_context_{label}", "value": int(count)})
        for category, count in candidate_context["review_category"].value_counts().items():
            rows.append({"metric": f"review_category_{category}", "value": int(count)})
        rows.append({"metric": "mean_context_score", "value": round(float(candidate_context["context_score"].mean()), 4)})
    return pd.DataFrame(rows)


def write_report(
    output_dir: Path,
    candidate_context: pd.DataFrame,
    summary: pd.DataFrame,
    source_windows: pd.DataFrame,
    elapsed_seconds: float,
) -> None:
    label_counts = candidate_context["trend_context_label"].value_counts().to_dict() if not candidate_context.empty else {}
    htf_issues = source_windows[source_windows["htf_status"] == "error"]
    htf_note = "Sin incidencias HTF."
    if not htf_issues.empty:
        htf_note = "; ".join(
            f"{row.symbol} {row.timeframe}->{row.htf_timeframe}: {getattr(row, 'htf_error', '')}"
            for row in htf_issues.itertuples()
        )
    lines = [
        "# WaveCount Phase 2.4 - contexto tecnico HTF/LTF",
        "",
        "Fecha: 2026-05-18",
        "",
        "## Resumen",
        "",
        "Se ha anadido contexto diagnostico con EMAs 50/150, alineacion HTF/LTF y EWO 5-35 a los candidatos visuales de Fase 2.3.",
        "No se han cambiado reglas de conteo, no se generan senales y no se toca ninguna estrategia.",
        "",
        "## Decisiones de implementacion",
        "",
        "- WaveCount 2.4 usa EMAs 50/150 como capa visual propia, aunque ENBOLSA historico usa WMA 50/150 para tendencia estructural.",
        "- El EWO 5-35 se implementa como SMA del precio medio `(high + low) / 2`, coherente con `backtests/enbolsa/GenerarIndicadores.py`.",
        "- La alineacion HTF usa la ultima vela HTF cerrada mediante desplazamiento de una vela antes del merge temporal, siguiendo el criterio anti look-ahead ya documentado en ENBOLSA.",
        "- Los graficos usan eje X comprimido por velas: no hay huecos visuales por fines de semana/cierres, aunque los timestamps reales se conservan en tablas.",
        "- `context_score` es calidad/contexto diagnostico, no probabilidad de ganar ni senal operativa.",
        "",
        "## Cobertura",
        "",
        f"- candidatos enriquecidos: {len(candidate_context)}",
        f"- distribucion de contexto: {label_counts}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        f"- incidencias HTF: {htf_note}",
        "",
        "## Lectura",
        "",
        "- Si muchos impulsos buenos quedan como `impulse_with_htf`, las EMAs/EWO ayudan a explicar estructura.",
        "- Si aparecen como `correction_against_htf`, pueden ser retrocesos o subondas contra regimen superior.",
        "- Si dominan `unclear_context` o `conflict_with_htf`, conviene revisar visualmente antes de usar contexto para busqueda guiada.",
        "",
        "## Decision",
        "",
        "Fase 2.4 queda como capa diagnostica. No debe guiar busqueda de ondas hasta revisar la galeria enriquecida.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_4_CONTEXT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_context_gallery(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    context_config: WaveContextConfig | None = None,
    htf_rows: int = 520,
    specs=DEFAULT_VISUAL_REVIEW_SPECS,
) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    for folder in ["impulses", "partials", "abc", "invalidations"]:
        (charts_dir / folder).mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    context_config = context_config or WaveContextConfig()
    candidates = pd.read_csv(input_dir / "tables" / "visual_review_candidates.csv")
    context_tables = _build_context_tables(context_config, htf_rows, specs=specs)
    context = context_tables["wavecount_context"]
    source_windows = context_tables["source_windows"]
    candidate_context = build_candidate_context(candidates, context)

    source = _build_source_tables(specs, PivotConfig())
    degree_pivots = source["degree_pivots"]
    count_legs = _candidate_counts_for_degrees(degree_pivots)["count_legs"]

    chart_rows: list[dict[str, Any]] = []
    for index, row in candidate_context.iterrows():
        folder = CATEGORY_STYLE.get(str(row["review_category"]), CATEGORY_STYLE["near_miss"])["folder"]
        filename = f"{int(row['candidate_order']):03d}_{row['candidate_id']}.png".replace(":", "-")
        chart_path = charts_dir / folder / filename
        try:
            spec = next(item for item in specs if item.example_id == row["example_id"])
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            plot_context_candidate(frame, context, degree_pivots, count_legs, row, chart_path)
            rel_path = str(chart_path.relative_to(output_dir))
            candidate_context.loc[index, "context_chart_path"] = rel_path
            chart_rows.append({"candidate_id": row["candidate_id"], "chart_path": rel_path, "status": "ok", "error": ""})
        except Exception as exc:
            chart_rows.append({"candidate_id": row["candidate_id"], "chart_path": "", "status": "error", "error": str(exc)})

    summary = _summary(context, candidate_context, source_windows)
    context.to_csv(tables_dir / "wavecount_context.csv", index=False)
    candidate_context.to_csv(tables_dir / "candidate_context.csv", index=False)
    summary.to_csv(tables_dir / "context_summary.csv", index=False)
    source_windows.to_csv(tables_dir / "source_windows.csv", index=False)

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, candidate_context, summary, source_windows, elapsed_seconds)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "input_dir": str(input_dir),
        "context_config": context_config_to_dict(context_config),
        "htf_map": HTF_MAP,
        "htf_rows": htf_rows,
        "specs": [asdict(item) for item in specs],
        "charts": chart_rows,
        "outputs": {
            "wavecount_context": "tables/wavecount_context.csv",
            "candidate_context": "tables/candidate_context.csv",
            "context_summary": "tables/context_summary.csv",
            "source_windows": "tables/source_windows.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE2_4_CONTEXT_REPORT.md",
        },
        "notes": [
            "Diagnostic context only.",
            "Charts use a compressed candle axis for visual review; timestamps remain unchanged in CSV outputs.",
            "No WaveCount counting rules were changed.",
            "No strategies, signals, backtests, MT5, dashboard or Telegram integration are touched.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.4 technical context gallery.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--htf-rows", type=int, default=520)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_context_gallery(input_dir=args.input_dir, output_dir=args.output_dir, htf_rows=args.htf_rows)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
