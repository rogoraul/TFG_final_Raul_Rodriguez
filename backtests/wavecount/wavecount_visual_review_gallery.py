from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .wavecount_config import PivotConfig
from .wavecount_counts import CountConfig, build_candidate_counts
from .wavecount_counts_gallery import _plot_candles, _plot_structural_chain
from .wavecount_degrees import build_swing_degrees
from .wavecount_gallery import fetch_recent_ohlc
from .wavecount_impulse_diagnostics import ImpulseDiagnosticsConfig, build_impulse_diagnostics
from .wavecount_pivots import detect_causal_pivots, extract_pivot_events


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"


@dataclass(frozen=True)
class VisualReviewSpec:
    example_id: str
    group: str
    symbol: str
    timeframe: str
    rows: int = 320


DEFAULT_VISUAL_REVIEW_SPECS = (
    VisualReviewSpec("forex_eurusd_h1", "Forex Majors", "EURUSD.r", "H1", 320),
    VisualReviewSpec("forex_gbpusd_h1", "Forex Majors", "GBPUSD.r", "H1", 320),
    VisualReviewSpec("forex_usdjpy_h1", "Forex Majors", "USDJPY.r", "H1", 320),
    VisualReviewSpec("forex_audjpy_h1", "Forex Majors", "AUDJPY.r", "H1", 320),
    VisualReviewSpec("forex_eurjpy_m30", "Forex Majors", "EURJPY.r", "M30", 320),
    VisualReviewSpec("forex_gbpjpy_m30", "Forex Majors", "GBPJPY.r", "M30", 320),
    VisualReviewSpec("metals_xauusd_m30", "Metals", "XAUUSD.r", "M30", 320),
    VisualReviewSpec("metals_xauusd_h1", "Metals", "XAUUSD.r", "H1", 320),
    VisualReviewSpec("metals_xagusd_h1", "Metals", "XAGUSD.r", "H1", 320),
    VisualReviewSpec("metals_xptusd_h1", "Metals", "XPTUSD", "H1", 300),
    VisualReviewSpec("metals_xpdusd_h1", "Metals", "XPDUSD", "H1", 300),
    VisualReviewSpec("index_aus200_m30", "Index", "AUS200", "M30", 320),
    VisualReviewSpec("index_aus200_h1", "Index", "AUS200", "H1", 320),
    VisualReviewSpec("index_hk50_m30", "Index", "HK50", "M30", 320),
    VisualReviewSpec("index_us500_m30", "Index", "US500", "M30", 320),
    VisualReviewSpec("index_us30_m30", "Index", "US30", "M30", 320),
)


REVIEW_LABEL_OPTIONS = [
    "visually_good_impulse",
    "visually_good_partial_123",
    "visually_good_abc",
    "ambiguous_but_interesting",
    "too_noisy",
    "too_micro",
    "too_coarse",
    "false_candidate",
    "hard_invalid_correct",
]


GROUP_REVIEW_ORDER = ["Forex Majors", "Metals", "Index"]


CATEGORY_STYLE = {
    "impulse": {"color": "#0077BB", "folder": "impulses", "label": "impulse"},
    "partial_123": {"color": "#009988", "folder": "partials", "label": "partial 1-2-3"},
    "abc": {"color": "#7C3AED", "folder": "abc", "label": "ABC"},
    "near_miss": {"color": "#EE7733", "folder": "impulses", "label": "near miss"},
    "hard_invalid": {"color": "#CC3311", "folder": "invalidations", "label": "hard invalid"},
}


def _events_for_spec(frame: pd.DataFrame, spec: VisualReviewSpec, config: PivotConfig) -> pd.DataFrame:
    pivots = detect_causal_pivots(frame, config=config, symbol=spec.symbol, timeframe=spec.timeframe)
    events = extract_pivot_events(pivots).reset_index(drop=True)
    if events.empty:
        return events
    events["example_id"] = spec.example_id
    events["group"] = spec.group
    events["example_type"] = "phase2_3_visual_review"
    return events


def _build_source_tables(
    specs: tuple[VisualReviewSpec, ...],
    pivot_config: PivotConfig,
) -> dict[str, pd.DataFrame]:
    raw_frames = []
    degree_frames = []
    window_rows = []
    for spec in specs:
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            if frame.empty or len(frame) < 80:
                raise RuntimeError(f"insufficient SQL rows: {len(frame)}")
            raw = _events_for_spec(frame, spec, pivot_config)
            if raw.empty:
                raise RuntimeError("no pivot events")
            degrees = build_swing_degrees(raw, group_columns=["example_id"])
            degree_pivots = degrees["swing_degrees_pivots"]
            raw_frames.append(raw)
            degree_frames.append(degree_pivots)
            window_rows.append(
                {
                    "example_id": spec.example_id,
                    "group": spec.group,
                    "symbol": spec.symbol,
                    "timeframe": spec.timeframe,
                    "status": "ok",
                    "rows": len(frame),
                    "first_time": frame.index.min().isoformat(),
                    "last_time": frame.index.max().isoformat(),
                    "raw_confirmed_pivots": len(raw[raw["is_confirmed"].astype(bool)]) if "is_confirmed" in raw.columns else len(raw),
                    "degree_pivots": len(degree_pivots),
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
                    "status": "error",
                    "rows": 0,
                    "first_time": "",
                    "last_time": "",
                    "raw_confirmed_pivots": 0,
                    "degree_pivots": 0,
                    "error": str(exc),
                }
            )
    return {
        "raw_pivots": pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame(),
        "degree_pivots": pd.concat(degree_frames, ignore_index=True) if degree_frames else pd.DataFrame(),
        "source_windows": pd.DataFrame(window_rows),
    }


def _candidate_counts_for_degrees(degree_pivots: pd.DataFrame) -> dict[str, pd.DataFrame]:
    count_frames = []
    leg_frames = []
    for degree in ["minor", "intermediate", "major"]:
        result = build_candidate_counts(
            degree_pivots,
            config=CountConfig(primary_degree=degree, context_degree="major"),
            group_columns=["example_id"],
        )
        counts = result["candidate_counts"]
        legs = result["count_legs"]
        if not counts.empty:
            counts["review_source_degree"] = degree
            count_frames.append(counts)
        if not legs.empty:
            legs["review_source_degree"] = degree
            leg_frames.append(legs)
    return {
        "candidate_counts": pd.concat(count_frames, ignore_index=True) if count_frames else pd.DataFrame(),
        "count_legs": pd.concat(leg_frames, ignore_index=True) if leg_frames else pd.DataFrame(),
    }


def _take_diverse(
    frame: pd.DataFrame,
    *,
    limit: int,
    sort_columns: list[str],
    group_columns: list[str] | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame
    group_columns = group_columns or ["group", "symbol", "timeframe", "swing_degree"]
    selected = []
    used: set[str] = set()
    ordered = frame.sort_values(sort_columns)
    for _, group in ordered.groupby(group_columns, dropna=False, sort=False):
        row = group.iloc[0]
        key = _candidate_key(row)
        if key in used:
            continue
        selected.append(row)
        used.add(key)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        for _, row in ordered.iterrows():
            key = _candidate_key(row)
            if key in used:
                continue
            selected.append(row)
            used.add(key)
            if len(selected) >= limit:
                break
    return pd.DataFrame(selected)


def _candidate_key(row: pd.Series) -> str:
    for column in ["source_id", "window_id", "count_id", "partial_id"]:
        value = row.get(column, "")
        if pd.notna(value) and str(value) != "":
            return f"{column}:{value}"
    return "|".join(
        str(row.get(column, ""))
        for column in ["example_id", "swing_degree", "start_pivot_id", "end_pivot_id", "diagnostic_status", "partial_status", "count_state"]
    )


def _take_balanced_by_degree(
    frame: pd.DataFrame,
    *,
    limit: int,
    sort_columns: list[str],
    degree_order: list[str],
    per_degree: int,
) -> pd.DataFrame:
    if frame.empty:
        return frame

    selected = []
    used: set[str] = set()
    for degree in degree_order:
        subset = frame[frame["swing_degree"] == degree].copy()
        degree_count = 0
        for group in GROUP_REVIEW_ORDER:
            group_subset = subset[subset["group"] == group].copy()
            batch = _take_diverse(
                group_subset,
                limit=1,
                sort_columns=sort_columns,
                group_columns=["symbol", "timeframe"],
            )
            for _, row in batch.iterrows():
                key = _candidate_key(row)
                if key in used:
                    continue
                selected.append(row)
                used.add(key)
                degree_count += 1
                if len(selected) >= limit or degree_count >= per_degree:
                    break
            if len(selected) >= limit or degree_count >= per_degree:
                break

        if len(selected) >= limit:
            return pd.DataFrame(selected)

        if degree_count < per_degree:
            remainder = subset[~subset.apply(lambda item: _candidate_key(item) in used, axis=1)].copy()
            batch = _take_diverse(
                remainder,
                limit=per_degree - degree_count,
                sort_columns=sort_columns,
                group_columns=["group", "symbol", "timeframe"],
            )
            for _, row in batch.iterrows():
                key = _candidate_key(row)
                if key in used:
                    continue
                selected.append(row)
                used.add(key)
                degree_count += 1
                if len(selected) >= limit or degree_count >= per_degree:
                    break
        if len(selected) >= limit:
            return pd.DataFrame(selected)

    if len(selected) < limit:
        remainder = frame[~frame.apply(lambda item: _candidate_key(item) in used, axis=1)].copy()
        batch = _take_diverse(remainder, limit=limit - len(selected), sort_columns=sort_columns)
        for _, row in batch.iterrows():
            key = _candidate_key(row)
            if key in used:
                continue
            selected.append(row)
            used.add(key)
            if len(selected) >= limit:
                break

    return pd.DataFrame(selected)


def _standard_candidate(row: pd.Series, *, review_category: str, source_table: str, source_id: str, suggested_label: str) -> dict[str, Any]:
    return {
        "candidate_id": f"{review_category}_{source_id}",
        "review_category": review_category,
        "source_table": source_table,
        "source_id": source_id,
        "example_id": row.get("example_id", ""),
        "group": row.get("group", ""),
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "swing_degree": row.get("swing_degree", row.get("review_source_degree", "")),
        "direction": row.get("direction", ""),
        "diagnostic_status": row.get("diagnostic_status", row.get("partial_status", row.get("count_state", ""))),
        "pattern_type": row.get("pattern_type", row.get("diagnostic_type", "")),
        "start_pivot_id": row.get("start_pivot_id", ""),
        "end_pivot_id": row.get("end_pivot_id", ""),
        "start_time": row.get("start_time", ""),
        "end_time": row.get("end_time", ""),
        "failure_reasons": row.get("failure_reasons", row.get("reason", "")),
        "suggested_initial_label": suggested_label,
        "review_options": "|".join(REVIEW_LABEL_OPTIONS),
        "chart_path": "",
    }


def _select_visual_candidates(
    counts: pd.DataFrame,
    legs: pd.DataFrame,
    impulses: pd.DataFrame,
    partials: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    strict = impulses[impulses["diagnostic_status"] == "strict_candidate_impulse"].copy()
    strict = _take_balanced_by_degree(
        strict,
        limit=12,
        sort_columns=["example_id", "count_detected_at"],
        degree_order=["minor", "intermediate", "major"],
        per_degree=4,
    )
    for _, row in strict.iterrows():
        rows.append(
            _standard_candidate(
                row,
                review_category="impulse",
                source_table="impulse_diagnostics",
                source_id=str(row["window_id"]),
                suggested_label="visually_good_impulse",
            )
        )

    partial_candidates = partials[partials["partial_status"] == "partial_123_candidate"].copy()
    partial_candidates = _take_balanced_by_degree(
        partial_candidates,
        limit=12,
        sort_columns=["example_id", "partial_detected_at"],
        degree_order=["intermediate", "minor", "major"],
        per_degree=4,
    )
    for _, row in partial_candidates.iterrows():
        rows.append(
            _standard_candidate(
                row,
                review_category="partial_123",
                source_table="partial_impulses",
                source_id=str(row["partial_id"]),
                suggested_label="visually_good_partial_123",
            )
        )

    abc = counts[counts["count_state"] == "candidate_abc"].copy()
    abc = _take_balanced_by_degree(
        abc,
        limit=12,
        sort_columns=["example_id", "count_detected_at"],
        degree_order=["intermediate", "minor", "major"],
        per_degree=4,
    )
    for _, row in abc.iterrows():
        rows.append(
            _standard_candidate(
                row,
                review_category="abc",
                source_table="candidate_counts",
                source_id=str(row["count_id"]),
                suggested_label="ambiguous_but_interesting",
            )
        )

    near = impulses[impulses["diagnostic_status"] == "soft_impulse_near_miss"].copy()
    near = _take_balanced_by_degree(
        near,
        limit=9,
        sort_columns=["example_id", "count_detected_at"],
        degree_order=["intermediate", "minor", "major"],
        per_degree=3,
    )
    for _, row in near.iterrows():
        rows.append(
            _standard_candidate(
                row,
                review_category="near_miss",
                source_table="impulse_diagnostics",
                source_id=str(row["window_id"]),
                suggested_label="ambiguous_but_interesting",
            )
        )

    invalid = impulses[impulses["diagnostic_status"] == "hard_invalid_impulse"].copy()
    invalid = _take_balanced_by_degree(
        invalid,
        limit=9,
        sort_columns=["example_id", "count_detected_at"],
        degree_order=["intermediate", "minor", "major"],
        per_degree=3,
    )
    for _, row in invalid.iterrows():
        rows.append(
            _standard_candidate(
                row,
                review_category="hard_invalid",
                source_table="impulse_diagnostics",
                source_id=str(row["window_id"]),
                suggested_label="hard_invalid_correct",
            )
        )

    candidates = pd.DataFrame(rows)
    if candidates.empty:
        return candidates
    candidates["candidate_order"] = range(1, len(candidates) + 1)
    return candidates


def _points_from_degree_window(pivots: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    subset = pivots[
        (pivots["example_id"] == row["example_id"])
        & (pivots["swing_degree"] == row["swing_degree"])
        & (pd.to_numeric(pivots["structural_pivot_id"], errors="coerce") >= int(float(row["start_pivot_id"])))
        & (pd.to_numeric(pivots["structural_pivot_id"], errors="coerce") <= int(float(row["end_pivot_id"])))
    ].copy()
    labels = ["0", "1", "2", "3", "4", "5"] if len(subset) >= 6 else ["0", "1", "2", "3"]
    subset = subset.sort_values(["structural_detected_at", "pivot_extreme_time", "structural_pivot_id"]).reset_index(drop=True)
    subset["plot_label"] = labels[: len(subset)]
    return subset


def _points_from_count_legs(legs: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    subset = legs[legs["count_id"] == row["source_id"]].copy()
    if not subset.empty and "swing_degree" in subset.columns and "swing_degree" in row:
        degree_subset = subset[subset["swing_degree"] == row["swing_degree"]].copy()
        if not degree_subset.empty:
            subset = degree_subset
    if subset.empty:
        return subset
    subset = subset.sort_values("point_order").reset_index(drop=True)
    if row.get("review_category", "") == "abc":
        labels = list(subset["point_label"])
        orders = [int(item) for item in subset["point_order"]]
        if len(subset) != 4 or orders != [0, 1, 2, 3] or labels != ["0", "A", "B", "C"]:
            raise ValueError(f"invalid ABC plot points for {row['source_id']}: labels={labels}, orders={orders}")
        times = pd.to_datetime(subset["pivot_extreme_time"], errors="coerce").tolist()
        if any(pd.isna(item) for item in times) or not all(times[index] < times[index + 1] for index in range(3)):
            raise ValueError(f"ABC plot points are not in strict time order for {row['source_id']}")
    subset["plot_label"] = subset["point_label"]
    return subset


def plot_visual_review_candidate(
    frame: pd.DataFrame,
    degree_pivots: pd.DataFrame,
    count_legs: pd.DataFrame,
    row: pd.Series,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")
    time_axis = _plot_candles(ax, frame)
    example_pivots = degree_pivots[degree_pivots["example_id"] == row["example_id"]]
    _plot_structural_chain(ax, frame, example_pivots, "major", "#94A3B8", "major context", time_axis)
    _plot_structural_chain(ax, frame, example_pivots, str(row["swing_degree"]), "#111827", f"{row['swing_degree']} swings", time_axis)

    if row["source_table"] == "candidate_counts":
        points = _points_from_count_legs(count_legs, row)
    else:
        points = _points_from_degree_window(degree_pivots, row)

    points["pivot_extreme_time"] = pd.to_datetime(points["pivot_extreme_time"], errors="coerce")
    xy = []
    for _, point in points.iterrows():
        extreme_time = point["pivot_extreme_time"]
        x_value = time_axis.to_x(extreme_time)
        if x_value is None:
            continue
        xy.append((x_value, float(point["pivot_extreme_price"]), str(point["plot_label"])))

    style = CATEGORY_STYLE.get(str(row["review_category"]), CATEGORY_STYLE["near_miss"])
    if xy:
        xs = [item[0] for item in xy]
        ys = [item[1] for item in xy]
        ax.plot(xs, ys, color=style["color"], linewidth=1.9, marker="o", markersize=6.5, label=style["label"], zorder=7)
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

    reason = str(row.get("failure_reasons", ""))
    if len(reason) > 120:
        reason = reason[:117] + "..."
    title = (
        f"{row['candidate_id']} | {row['symbol']} {row['timeframe']} {row['swing_degree']}\n"
        f"{row['review_category']} / {row['diagnostic_status']} / {row['suggested_initial_label']} | {reason or 'no failure'}"
    )
    ax.set_title(title, fontsize=11, fontweight="bold")
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


def _manual_template(candidates: pd.DataFrame) -> pd.DataFrame:
    template = candidates.copy()
    template["review_label"] = ""
    template["reviewer_notes"] = ""
    template["visual_quality_score"] = ""
    template["should_keep_for_methodology"] = ""
    template["suggested_action"] = ""
    ordered = [
        "candidate_order",
        "candidate_id",
        "review_category",
        "suggested_initial_label",
        "review_label",
        "reviewer_notes",
        "visual_quality_score",
        "should_keep_for_methodology",
        "suggested_action",
        "review_options",
        "chart_path",
        "group",
        "symbol",
        "timeframe",
        "swing_degree",
        "direction",
        "diagnostic_status",
        "pattern_type",
        "failure_reasons",
        "source_table",
        "source_id",
        "example_id",
        "start_time",
        "end_time",
    ]
    return template[[column for column in ordered if column in template.columns]]


def _summary(candidates: pd.DataFrame, source_windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if not source_windows.empty:
        rows.append({"metric": "source_windows_ok", "value": int((source_windows["status"] == "ok").sum())})
        rows.append({"metric": "source_windows_error", "value": int((source_windows["status"] == "error").sum())})
    if not candidates.empty:
        for category, count in candidates["review_category"].value_counts().items():
            rows.append({"metric": f"candidates_{category}", "value": int(count)})
        for degree, count in candidates["swing_degree"].value_counts().items():
            rows.append({"metric": f"degree_{degree}", "value": int(count)})
        for group, count in candidates["group"].value_counts().items():
            rows.append({"metric": f"group_{group}", "value": int(count)})
    return pd.DataFrame(rows)


def write_report(output_dir: Path, candidates: pd.DataFrame, source_windows: pd.DataFrame, elapsed_seconds: float) -> None:
    category_counts = candidates["review_category"].value_counts().to_dict() if not candidates.empty else {}
    degree_counts = candidates["swing_degree"].value_counts().to_dict() if not candidates.empty else {}
    group_counts = candidates["group"].value_counts().to_dict() if not candidates.empty else {}
    ok_windows = int((source_windows["status"] == "ok").sum()) if not source_windows.empty else 0
    error_windows = int((source_windows["status"] == "error").sum()) if not source_windows.empty else 0
    lines = [
        "# WaveCount Phase 2.3 - revision visual ampliada",
        "",
        "Fecha: 2026-05-17",
        "",
        "## Resumen",
        "",
        "Se ha generado una galeria visual ampliada para revision humana de WaveCount.",
        "No se han cambiado reglas de conteo, no se generan senales y no se toca ninguna estrategia.",
        "",
        "## Cobertura",
        "",
        f"- ventanas SQL procesadas correctamente: {ok_windows}",
        f"- ventanas SQL omitidas/con error: {error_windows}",
        f"- candidatos visuales seleccionados: {len(candidates)}",
        f"- candidatos por categoria: {category_counts}",
        f"- candidatos por grado: {degree_counts}",
        f"- candidatos por grupo: {group_counts}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Lectura",
        "",
        "- `minor` aporta impulsos estrictos, pero debe revisarse si son demasiado micro.",
        "- `intermediate` aporta parciales y near-misses utiles para decidir si hace falta busqueda no consecutiva.",
        "- `major` queda como contexto, normalmente mas grueso.",
        "- La plantilla manual permite clasificar cada imagen antes de tocar mas logica.",
        "",
        "## Decision",
        "",
        "Hay suficientes ejemplos para una primera revision humana. Antes de Fase 3 conviene revisar `manual_review_template.csv` y marcar los casos visualmente defendibles.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_3_VISUAL_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_visual_review_gallery(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    specs: tuple[VisualReviewSpec, ...] = DEFAULT_VISUAL_REVIEW_SPECS,
    pivot_config: PivotConfig | None = None,
) -> dict:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    charts_dir = output_dir / "charts"
    for folder in ["impulses", "partials", "abc", "invalidations"]:
        (charts_dir / folder).mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    pivot_config = pivot_config or PivotConfig()
    source = _build_source_tables(specs, pivot_config)
    degree_pivots = source["degree_pivots"]
    counts_result = _candidate_counts_for_degrees(degree_pivots)
    counts = counts_result["candidate_counts"]
    legs = counts_result["count_legs"]
    diagnostics = build_impulse_diagnostics(degree_pivots, config=ImpulseDiagnosticsConfig())
    impulses = diagnostics["impulse_diagnostics"]
    partials = diagnostics["partial_impulses"]

    candidates = _select_visual_candidates(counts, legs, impulses, partials)
    chart_rows: list[dict[str, Any]] = []
    for index, row in candidates.iterrows():
        spec_row = source["source_windows"][source["source_windows"]["example_id"] == row["example_id"]]
        if spec_row.empty or spec_row.iloc[0]["status"] != "ok":
            continue
        spec = next(item for item in specs if item.example_id == row["example_id"])
        folder = CATEGORY_STYLE.get(str(row["review_category"]), CATEGORY_STYLE["near_miss"])["folder"]
        filename = f"{int(row['candidate_order']):03d}_{row['candidate_id']}.png".replace(":", "-")
        chart_path = charts_dir / folder / filename
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            plot_visual_review_candidate(frame, degree_pivots, legs, row, chart_path)
            rel_path = str(chart_path.relative_to(output_dir))
            candidates.loc[index, "chart_path"] = rel_path
            chart_rows.append({"candidate_id": row["candidate_id"], "chart_path": rel_path, "status": "ok", "error": ""})
        except Exception as exc:
            chart_rows.append({"candidate_id": row["candidate_id"], "chart_path": "", "status": "error", "error": str(exc)})

    summary = _summary(candidates, source["source_windows"])
    manual = _manual_template(candidates)
    source["source_windows"].to_csv(tables_dir / "source_windows.csv", index=False)
    candidates.to_csv(tables_dir / "visual_review_candidates.csv", index=False)
    manual.to_csv(tables_dir / "manual_review_template.csv", index=False)
    summary.to_csv(tables_dir / "visual_review_summary.csv", index=False)

    elapsed_seconds = perf_counter() - start
    write_report(output_dir, candidates, source["source_windows"], elapsed_seconds)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "pivot_config": asdict(pivot_config),
        "specs": [asdict(item) for item in specs],
        "charts": chart_rows,
        "outputs": {
            "visual_review_candidates": "tables/visual_review_candidates.csv",
            "manual_review_template": "tables/manual_review_template.csv",
            "visual_review_summary": "tables/visual_review_summary.csv",
            "source_windows": "tables/source_windows.csv",
            "charts_dir": "charts",
            "report": "WAVECOUNT_PHASE2_3_VISUAL_REVIEW.md",
        },
        "notes": [
            "Diagnostic visual review only.",
            "No WaveCount counting rules were changed.",
            "No strategies, signals, backtests, MT5, dashboard or Telegram integration are touched.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.3 manual visual review gallery.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_visual_review_gallery(output_dir=args.output_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
