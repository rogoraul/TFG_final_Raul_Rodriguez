from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .wavecount_counts_gallery import _plot_candles, _plot_structural_chain
from .wavecount_gallery import DEFAULT_EXAMPLES, fetch_recent_ohlc
from .wavecount_impulse_diagnostics import (
    ImpulseDiagnosticsConfig,
    build_impulse_diagnostics,
    diagnostics_config_to_dict,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE16_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase1_6_swing_degrees_2026-05-17"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_2_impulse_diagnostics_2026-05-17"

STATUS_STYLE = {
    "strict_candidate_impulse": {"color": "#0077BB", "label": "strict impulse"},
    "soft_impulse_near_miss": {"color": "#EE7733", "label": "soft near miss"},
    "hard_invalid_impulse": {"color": "#CC3311", "label": "hard invalid"},
    "partial_123_candidate": {"color": "#009988", "label": "partial 1-2-3"},
    "partial_123_ambiguous": {"color": "#EE7733", "label": "partial ambiguous"},
    "partial_123_invalid": {"color": "#CC3311", "label": "partial invalid"},
}


def _select_examples(impulses: pd.DataFrame, partials: pd.DataFrame, max_per_bucket: int = 2) -> pd.DataFrame:
    selected = []
    used: set[str] = set()

    def add_rows(frame: pd.DataFrame, id_column: str, status_column: str, statuses: list[str]) -> None:
        nonlocal selected
        for status in statuses:
            subset = frame[frame[status_column] == status].copy()
            if subset.empty:
                continue
            subset = subset.sort_values(["swing_degree", "example_id", "count_detected_at" if "count_detected_at" in subset.columns else "partial_detected_at"])
            for _, group in subset.groupby(["swing_degree", "example_id"], sort=False):
                row = group.iloc[0].copy()
                row["chart_source"] = id_column
                row["chart_status_column"] = status_column
                key = str(row[id_column])
                if key in used:
                    continue
                selected.append(row)
                used.add(key)
                if len([item for item in selected if item.get(status_column) == status]) >= max_per_bucket * 3:
                    break

    add_rows(impulses, "window_id", "diagnostic_status", ["strict_candidate_impulse", "soft_impulse_near_miss", "hard_invalid_impulse"])
    add_rows(partials, "partial_id", "partial_status", ["partial_123_candidate", "partial_123_ambiguous"])
    if not selected and not impulses.empty:
        for _, row in impulses.head(8).iterrows():
            row = row.copy()
            row["chart_source"] = "window_id"
            row["chart_status_column"] = "diagnostic_status"
            selected.append(row)
    return pd.DataFrame(selected[:24])


def _window_points(pivots: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    subset = pivots[
        (pivots["example_id"] == row["example_id"])
        & (pivots["swing_degree"] == row["swing_degree"])
        & (pd.to_numeric(pivots["structural_pivot_id"], errors="coerce") >= int(row["start_pivot_id"]))
        & (pd.to_numeric(pivots["structural_pivot_id"], errors="coerce") <= int(row["end_pivot_id"]))
    ].copy()
    return subset.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"])


def plot_diagnostic_window(
    frame: pd.DataFrame,
    pivots: pd.DataFrame,
    row: pd.Series,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(ax, frame)
    _plot_structural_chain(ax, frame, pivots[pivots["example_id"] == row["example_id"]], "major", "#94A3B8", "major context", time_axis)
    _plot_structural_chain(ax, frame, pivots[pivots["example_id"] == row["example_id"]], str(row["swing_degree"]), "#111827", f"{row['swing_degree']} swings", time_axis)

    points = _window_points(pivots, row)
    points["pivot_extreme_time"] = pd.to_datetime(points["pivot_extreme_time"], errors="coerce")
    xy = []
    for _, point in points.iterrows():
        extreme_time = point["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        xy.append((x_value, float(point["pivot_extreme_price"])))

    status_column = str(row.get("chart_status_column", "diagnostic_status"))
    status = str(row.get(status_column, row.get("diagnostic_status", "")))
    style = STATUS_STYLE.get(status, STATUS_STYLE["soft_impulse_near_miss"])
    labels = ["0", "1", "2", "3", "4", "5"] if len(xy) >= 6 else ["0", "1", "2", "3"]
    if xy:
        xs, ys = zip(*xy)
        ax.plot(xs, ys, color=style["color"], linewidth=1.9, marker="o", markersize=6.5, label=style["label"], zorder=7)
        y_padding = max((max(ys) - min(ys)) * 0.04, abs(ys[-1]) * 0.0002, 1e-8)
        for (x_value, y_value), label in zip(xy, labels):
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

    reasons = str(row.get("failure_reasons", ""))
    if len(reasons) > 120:
        reasons = reasons[:117] + "..."
    title = (
        f"{row.get('symbol', '')} {row.get('timeframe', '')} {row.get('swing_degree', '')} - {status}\n"
        f"{reasons or 'no failure'}"
    )
    ax.set_title(title, fontsize=12, fontweight="bold")
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


def write_report(
    output_dir: Path,
    impulses: pd.DataFrame,
    partials: pd.DataFrame,
    comparison: pd.DataFrame,
    elapsed_seconds: float,
    chart_rows: list[dict[str, str]],
) -> None:
    full_status = impulses["diagnostic_status"].value_counts().to_dict() if not impulses.empty else {}
    partial_status = partials["partial_status"].value_counts().to_dict() if not partials.empty else {}
    degree_summary = pd.DataFrame()
    if not comparison.empty:
        degree_summary = (
            comparison.groupby("swing_degree", dropna=False)[
                [
                    "structural_pivots",
                    "full_impulse_windows",
                    "strict_candidate_impulse",
                    "soft_impulse_near_miss",
                    "hard_invalid_impulse",
                    "partial_123_candidate",
                    "partial_123_ambiguous",
                    "partial_123_invalid",
                ]
            ]
            .sum()
            .reset_index()
            .sort_values("swing_degree")
        )
    strict_total = int((impulses["diagnostic_status"] == "strict_candidate_impulse").sum()) if not impulses.empty else 0
    partial_total = int((partials["partial_status"] == "partial_123_candidate").sum()) if not partials.empty else 0
    soft_total = int((impulses["diagnostic_status"] == "soft_impulse_near_miss").sum()) if not impulses.empty else 0
    strict_by_degree = (
        degree_summary.set_index("swing_degree")["strict_candidate_impulse"].to_dict()
        if not degree_summary.empty
        else {}
    )
    partial_by_degree = (
        degree_summary.set_index("swing_degree")["partial_123_candidate"].to_dict()
        if not degree_summary.empty
        else {}
    )

    if strict_by_degree.get("intermediate", 0):
        diagnosis = "El cero original era un efecto de configuracion previa; `intermediate` ya contiene impulsos estrictos."
    elif strict_total:
        diagnosis = (
            "El cero de Fase 2 sobre `intermediate` no implica ausencia total: aparecen impulsos estrictos en `minor`, "
            "pero ese grado es mas microestructural y no debe sustituir automaticamente al grado base."
        )
    elif partial_total or soft_total:
        diagnosis = (
            "El cero de `candidate_impulse` es esperable en esta muestra pequena: hay parciales y near-misses, "
            "pero no impulsos completos limpios."
        )
    else:
        diagnosis = "El cero es preocupante para esta muestra: no aparecen ni impulsos completos ni parciales claros."

    lines = [
        "# WaveCount Phase 2.2 - diagnostico de impulsos",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha auditado por que Fase 2 no produce `candidate_impulse` limpio sobre `intermediate`.",
        "La revision compara `minor`, `intermediate` y `major`, impulsos completos, near-misses y parciales 1-2-3.",
        "",
        "No se generan senales, no se filtran estrategias, no se conecta MT5 y no se ejecutan backtests.",
        "",
        "## Resultado global",
        "",
        f"- impulsos completos por estado: {full_status}",
        f"- parciales 1-2-3 por estado: {partial_status}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Comparacion por grado",
        "",
        "| grado | structural pivots | ventanas completas | impulsos estrictos | near-miss blandos | invalidos duros | parciales 1-2-3 | parciales ambiguos | parciales invalidos |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if not degree_summary.empty:
        for _, row in degree_summary.iterrows():
            lines.append(
                f"| `{row['swing_degree']}` | {int(row['structural_pivots'])} | {int(row['full_impulse_windows'])} | "
                f"{int(row['strict_candidate_impulse'])} | {int(row['soft_impulse_near_miss'])} | "
                f"{int(row['hard_invalid_impulse'])} | {int(row['partial_123_candidate'])} | "
                f"{int(row['partial_123_ambiguous'])} | {int(row['partial_123_invalid'])} |"
            )
    lines.extend(
        [
        "",
        "## Diagnostico",
        "",
        diagnosis,
        "",
        f"- impulsos estrictos por grado: {strict_by_degree}",
        f"- parciales 1-2-3 candidatos por grado: {partial_by_degree}",
        "",
        "## Graficos generados",
        "",
        ]
    )
    for row in chart_rows:
        lines.append(f"- `{row['diagnostic_id']}`: {row['status']} - {row.get('chart_path', '')}")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Antes de Fase 3 conviene ampliar la revision visual y separar el buscador futuro de conteos estrictamente consecutivos. No se debe relajar la regla para fabricar impulsos.",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_2_IMPULSE_DIAGNOSTICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_impulse_diagnostics_gallery(
    phase16_dir: Path = DEFAULT_PHASE16_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: ImpulseDiagnosticsConfig | None = None,
) -> dict:
    config = config or ImpulseDiagnosticsConfig()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    phase16_dir = Path(phase16_dir)
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    pivots = pd.read_csv(phase16_dir / "tables" / "swing_degrees_pivots.csv")
    result = build_impulse_diagnostics(pivots, config=config)
    impulses = result["impulse_diagnostics"]
    failures = result["impulse_failure_reasons"]
    comparison = result["degree_impulse_comparison"]
    partials = result["partial_impulses"]

    impulses.to_csv(tables_dir / "impulse_diagnostics.csv", index=False)
    failures.to_csv(tables_dir / "impulse_failure_reasons.csv", index=False)
    comparison.to_csv(tables_dir / "degree_impulse_comparison.csv", index=False)
    partials.to_csv(tables_dir / "partial_impulses.csv", index=False)

    selected = _select_examples(impulses, partials)
    chart_rows: list[dict[str, str]] = []
    example_lookup = {item.example_id: item for item in DEFAULT_EXAMPLES}
    for _, row in selected.iterrows():
        source_column = str(row.get("chart_source", "window_id"))
        diagnostic_id = str(row.get(source_column, "diagnostic"))
        if not diagnostic_id or diagnostic_id.lower() == "nan":
            diagnostic_id = str(row.get("partial_id", row.get("window_id", "diagnostic")))
        try:
            spec = example_lookup[str(row["example_id"])]
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            chart_path = charts_dir / f"{diagnostic_id}.png"
            plot_diagnostic_window(frame, pivots, row, chart_path)
            chart_rows.append(
                {
                    "diagnostic_id": diagnostic_id,
                    "chart_path": str(chart_path.relative_to(output_dir)),
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            chart_rows.append({"diagnostic_id": diagnostic_id, "chart_path": "", "status": "error", "error": str(exc)})

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, impulses, partials, comparison, elapsed_seconds, chart_rows)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "phase16_dir": str(phase16_dir),
        "config": diagnostics_config_to_dict(config),
        "charts": chart_rows,
        "outputs": {
            "impulse_diagnostics": "tables/impulse_diagnostics.csv",
            "impulse_failure_reasons": "tables/impulse_failure_reasons.csv",
            "degree_impulse_comparison": "tables/degree_impulse_comparison.csv",
            "partial_impulses": "tables/partial_impulses.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE2_2_IMPULSE_DIAGNOSTICS.md",
        },
        "notes": [
            "Diagnostic only.",
            "No strategies, signals, backtests, MT5, dashboard or Telegram integration are touched.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.2 impulse diagnostics gallery.")
    parser.add_argument("--phase16-dir", type=Path, default=DEFAULT_PHASE16_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_impulse_diagnostics_gallery(args.phase16_dir, args.output_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
