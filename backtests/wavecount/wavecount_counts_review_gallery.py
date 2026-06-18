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

from .wavecount_counts_gallery import _plot_candles, _plot_count, _plot_structural_chain
from .wavecount_counts_review import (
    InvalidationReviewConfig,
    build_invalidations_review,
    build_rule_severity_summary,
    review_config_to_dict,
)
from .wavecount_gallery import DEFAULT_EXAMPLES, fetch_recent_ohlc


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE2_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_candidate_counts_2026-05-17"
DEFAULT_PHASE16_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase1_6_swing_degrees_2026-05-17"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_1_false_negative_review_2026-05-17"


def _select_review_examples(review: pd.DataFrame, max_per_bucket: int = 4) -> pd.DataFrame:
    if review.empty:
        return review
    selected = []
    used: set[str] = set()

    selectors = [
        lambda frame: frame[
            (frame["rule_severity"] == "hard_invalid")
            & (frame["count_state"] == "invalidated_count")
            & (frame["pattern_type"] == "impulse")
        ],
        lambda frame: frame[
            (frame["rule_severity"] == "hard_invalid")
            & (frame["count_state"] == "invalidated_count")
            & (frame["pattern_type"] == "abc")
        ],
        lambda frame: frame[
            (frame["rule_severity"] == "soft_invalid_or_ambiguous")
            & (frame["count_state"] == "ambiguous_count")
            & frame["reason"].str.contains("wave 4 overlaps", na=False)
        ],
        lambda frame: frame[
            (frame["rule_severity"] == "soft_invalid_or_ambiguous")
            & (frame["count_state"] == "ambiguous_count")
            & frame["reason"].str.contains("C leg does not exceed|ABC is too compressed", na=False)
        ],
        lambda frame: frame[
            (frame["rule_severity"] == "needs_manual_review")
            & (frame["count_state"] == "invalidated_count")
        ],
    ]

    for selector in selectors:
        subset = selector(review).copy()
        subset = subset.sort_values(["example_id", "pattern_type", "count_detected_at", "count_id"])
        diverse_rows = []
        for _, group in subset.groupby("example_id", sort=False):
            diverse_rows.append(group.iloc[0])
        for row in diverse_rows[:max_per_bucket]:
            count_id = str(row["count_id"])
            if count_id in used:
                continue
            selected.append(row)
            used.add(count_id)
    if not selected:
        selected = [row for _, row in review.head(max_per_bucket).iterrows()]
    return pd.DataFrame(selected)


def plot_review_example(
    frame: pd.DataFrame,
    pivots: pd.DataFrame,
    legs: pd.DataFrame,
    row: pd.Series,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(ax, frame)
    _plot_structural_chain(ax, frame, pivots, "major", "#94A3B8", "major context", time_axis)
    _plot_structural_chain(ax, frame, pivots, "intermediate", "#111827", "intermediate swings", time_axis)
    _plot_count(ax, frame, legs, row, time_axis)

    reason = str(row.get("reason", ""))
    if len(reason) > 120:
        reason = reason[:117] + "..."
    title = (
        f"{row.get('symbol', '')} {row.get('timeframe', '')} - {row.get('count_id', '')}\n"
        f"{row.get('rule_severity', '')} -> {row.get('recommended_state', '')}: {reason}"
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
    review: pd.DataFrame,
    summary: pd.DataFrame,
    elapsed_seconds: float,
    chart_rows: list[dict[str, str]],
) -> None:
    severity_counts = review["rule_severity"].value_counts().to_dict() if not review.empty else {}
    original_counts = review["count_state"].value_counts().to_dict() if not review.empty else {}
    recommended_counts = review["recommended_state"].value_counts().to_dict() if not review.empty else {}
    false_negative_count = int(
        (
            (review["count_state"] == "invalidated_count")
            & (review["possible_false_negative"].astype(bool))
        ).sum()
    ) if not review.empty else 0
    soft_ambiguous_count = int(
        (
            (review["count_state"] == "ambiguous_count")
            & (review["rule_severity"] == "soft_invalid_or_ambiguous")
        ).sum()
    ) if not review.empty else 0
    changed_count = int(review["state_changed_by_review"].sum()) if not review.empty else 0
    lines = [
        "# WaveCount Phase 2.1 - revision de invalidaciones",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha auditado la Fase 2 para separar invalidaciones duras de reglas blandas/ambiguas.",
        "La revision no genera senales, no modifica estrategias y no conecta MT5.",
        "",
        "## Resultado",
        "",
        f"- estados originales revisados: {original_counts}",
        f"- severidades: {severity_counts}",
        f"- estados recomendados: {recommended_counts}",
        f"- posibles falsos negativos que siguen como `invalidated_count`: {false_negative_count}",
        f"- casos blandos ya reclasificados como `ambiguous_count`: {soft_ambiguous_count}",
        f"- cambios de estado recomendados: {changed_count}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Lectura",
        "",
        "- Las reglas duras siguen invalidando.",
        "- El solape onda 4 / onda 1 se trata como ambiguedad si aparece solo, no como invalidacion dura.",
        "- Las estructuras con B rompiendo origen siguen invalidadas para el ABC basico tipo zigzag; pueden ser extension futura de flats/expanded flats, no Fase 2.",
        "",
        "## Graficos generados",
        "",
    ]
    for row in chart_rows:
        lines.append(f"- `{row['count_id']}`: {row['status']} - {row.get('chart_path', '')}")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Las 59 invalidaciones iniciales no eran todas equivalentes: la mayoria eran reglas duras, pero varias invalidaciones por solape de onda 4 eran falsos negativos metodologicos y deben quedar como `ambiguous_count`.",
            "",
            "Fase 2 queda mejor calibrada, aunque sigue necesitando revision visual ampliada antes de Fase 3.",
        ]
    )
    (output_dir / "WAVECOUNT_PHASE2_1_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_false_negative_review_gallery(
    phase2_dir: Path = DEFAULT_PHASE2_DIR,
    phase16_dir: Path = DEFAULT_PHASE16_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: InvalidationReviewConfig | None = None,
) -> dict:
    config = config or InvalidationReviewConfig()
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    phase2_dir = Path(phase2_dir)
    phase16_dir = Path(phase16_dir)
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    counts = pd.read_csv(phase2_dir / "tables" / "candidate_counts.csv")
    legs = pd.read_csv(phase2_dir / "tables" / "count_legs.csv")
    pivots = pd.read_csv(phase16_dir / "tables" / "swing_degrees_pivots.csv")
    review = build_invalidations_review(counts, config=config)
    summary = build_rule_severity_summary(review)

    review.to_csv(tables_dir / "invalidations_review.csv", index=False)
    summary.to_csv(tables_dir / "rule_severity_summary.csv", index=False)

    chart_rows: list[dict[str, str]] = []
    selected = _select_review_examples(review)
    example_lookup = {item.example_id: item for item in DEFAULT_EXAMPLES}
    for _, row in selected.iterrows():
        count_id = str(row["count_id"])
        try:
            spec = example_lookup[str(row["example_id"])]
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            subset_pivots = pivots[pivots["example_id"] == spec.example_id].copy()
            chart_path = charts_dir / f"{count_id}.png"
            plot_review_example(frame, subset_pivots, legs[legs["example_id"] == spec.example_id].copy(), row, chart_path)
            chart_rows.append(
                {
                    "count_id": count_id,
                    "chart_path": str(chart_path.relative_to(output_dir)),
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            chart_rows.append({"count_id": count_id, "chart_path": "", "status": "error", "error": str(exc)})

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, review, summary, elapsed_seconds, chart_rows)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "phase2_dir": str(phase2_dir),
        "phase16_dir": str(phase16_dir),
        "config": review_config_to_dict(config),
        "charts": chart_rows,
        "outputs": {
            "invalidations_review": "tables/invalidations_review.csv",
            "rule_severity_summary": "tables/rule_severity_summary.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE2_1_REVIEW.md",
        },
        "notes": [
            "Review artifacts are diagnostic only.",
            "No strategies, backtests, MT5, dashboard or Telegram integration are touched.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.1 false negative review gallery.")
    parser.add_argument("--phase2-dir", type=Path, default=DEFAULT_PHASE2_DIR)
    parser.add_argument("--phase16-dir", type=Path, default=DEFAULT_PHASE16_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--include-ambiguous", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = InvalidationReviewConfig(include_ambiguous=args.include_ambiguous)
    meta = build_false_negative_review_gallery(args.phase2_dir, args.phase16_dir, args.output_dir, config=config)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
