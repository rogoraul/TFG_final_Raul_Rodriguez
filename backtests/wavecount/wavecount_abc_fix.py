from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from .wavecount_config import PivotConfig
from .wavecount_context import WaveContextConfig, build_candidate_context, context_config_to_dict
from .wavecount_context_gallery import _build_context_tables, plot_context_candidate
from .wavecount_gallery import fetch_recent_ohlc
from .wavecount_h4_d1_gallery import H4_D1_VISUAL_REVIEW_SPECS
from .wavecount_impulse_diagnostics import ImpulseDiagnosticsConfig, build_impulse_diagnostics
from .wavecount_visual_review_gallery import (
    DEFAULT_VISUAL_REVIEW_SPECS,
    VisualReviewSpec,
    _build_source_tables,
    _candidate_counts_for_degrees,
    _select_visual_candidates,
    _standard_candidate,
    plot_visual_review_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_abc_fix_2026-05-20"

LEGACY_PHASE23_H4 = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
LEGACY_PHASE24_H4 = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h4_d1"
LEGACY_PHASE23_H1 = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"

SWING_DEGREES = ("minor", "intermediate", "major")


def _legacy_count_id(count_id: str) -> str:
    value = str(count_id)
    for degree in SWING_DEGREES:
        value = value.replace(f"_{degree}_abc_", "_abc_")
        value = value.replace(f"_{degree}_impulse_", "_impulse_")
    return value


def _ordered_flag(times: list[pd.Timestamp], *, strict: bool) -> bool:
    if any(pd.isna(item) for item in times):
        return False
    if strict:
        return all(times[index] < times[index + 1] for index in range(len(times) - 1))
    return all(times[index] <= times[index + 1] for index in range(len(times) - 1))


def _abc_point_diagnostics(points: pd.DataFrame) -> dict[str, Any]:
    if points.empty:
        return {
            "point_count": 0,
            "labels": "",
            "orders": "",
            "pivot_extreme_time_strictly_increasing": False,
            "structural_detected_at_non_decreasing": False,
            "plot_ready": False,
        }
    points = points.sort_values(["point_order", "swing_degree", "structural_detected_at", "pivot_extreme_time"]).reset_index(drop=True)
    labels = list(points["point_label"]) if "point_label" in points.columns else []
    orders = [int(item) for item in points["point_order"]] if "point_order" in points.columns else []
    extreme_times = pd.to_datetime(points["pivot_extreme_time"], errors="coerce").tolist()
    detected_times = pd.to_datetime(points["structural_detected_at"], errors="coerce").tolist()
    strict_extreme = _ordered_flag(extreme_times, strict=True)
    causal_detection = _ordered_flag(detected_times, strict=False)
    plot_ready = len(points) == 4 and orders == [0, 1, 2, 3] and labels == ["0", "A", "B", "C"] and strict_extreme and causal_detection
    return {
        "point_count": len(points),
        "labels": "|".join(str(item) for item in labels),
        "orders": "|".join(str(item) for item in orders),
        "pivot_extreme_time_strictly_increasing": strict_extreme,
        "structural_detected_at_non_decreasing": causal_detection,
        "first_pivot_extreme_time": extreme_times[0] if extreme_times else pd.NaT,
        "last_pivot_extreme_time": extreme_times[-1] if extreme_times else pd.NaT,
        "last_structural_detected_at": max(detected_times) if detected_times else pd.NaT,
        "plot_ready": plot_ready,
    }


def _build_bundle(specs: tuple[VisualReviewSpec, ...]) -> dict[str, pd.DataFrame]:
    source = _build_source_tables(specs, PivotConfig())
    counts_result = _candidate_counts_for_degrees(source["degree_pivots"])
    diagnostics = build_impulse_diagnostics(source["degree_pivots"], config=ImpulseDiagnosticsConfig())
    candidates = _select_visual_candidates(
        counts_result["candidate_counts"],
        counts_result["count_legs"],
        diagnostics["impulse_diagnostics"],
        diagnostics["partial_impulses"],
    )
    return {
        **source,
        **counts_result,
        "impulse_diagnostics": diagnostics["impulse_diagnostics"],
        "partial_impulses": diagnostics["partial_impulses"],
        "visual_candidates": candidates,
    }


def _legacy_before_diagnostics(
    *,
    label: str,
    legacy_dir: Path,
    fixed_legs: pd.DataFrame,
) -> pd.DataFrame:
    candidates_path = legacy_dir / "tables" / "visual_review_candidates.csv"
    if not candidates_path.exists():
        return pd.DataFrame()
    old_candidates = pd.read_csv(candidates_path)
    old_abc = old_candidates[old_candidates["review_category"] == "abc"].copy()
    rows: list[dict[str, Any]] = []
    for _, row in old_abc.iterrows():
        legacy_id = str(row["source_id"])
        subset = fixed_legs[fixed_legs["count_id"].map(_legacy_count_id) == legacy_id].copy()
        diag = _abc_point_diagnostics(subset)
        matched_ids = sorted(set(str(item) for item in subset["count_id"])) if not subset.empty else []
        problem = "ok"
        if len(matched_ids) > 1:
            problem = "legacy_count_id_matched_multiple_swing_degrees"
        elif not diag["plot_ready"]:
            problem = "abc_not_plot_ready"
        rows.append(
            {
                "phase": label,
                "legacy_candidate_id": row.get("candidate_id", ""),
                "legacy_source_id": legacy_id,
                "legacy_chart_path": row.get("chart_path", ""),
                "legacy_suggested_label": row.get("suggested_initial_label", ""),
                "matched_fixed_count_ids": "|".join(matched_ids),
                "matched_fixed_count_id_count": len(matched_ids),
                "problem": problem,
                **diag,
            }
        )
    return pd.DataFrame(rows)


def _after_diagnostics(label: str, candidates: pd.DataFrame, legs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    abc = candidates[candidates["review_category"] == "abc"].copy()
    for _, row in abc.iterrows():
        subset = legs[legs["count_id"] == row["source_id"]].copy()
        diag = _abc_point_diagnostics(subset)
        rows.append(
            {
                "phase": label,
                "candidate_id": row["candidate_id"],
                "source_id": row["source_id"],
                "example_id": row.get("example_id", ""),
                "symbol": row.get("symbol", ""),
                "timeframe": row.get("timeframe", ""),
                "swing_degree": row.get("swing_degree", ""),
                "diagnostic_status": row.get("diagnostic_status", ""),
                "suggested_initial_label": row.get("suggested_initial_label", ""),
                "reason": row.get("failure_reasons", ""),
                **diag,
            }
        )
    return pd.DataFrame(rows)


def _plot_phase23_abc(
    *,
    label: str,
    specs: tuple[VisualReviewSpec, ...],
    bundle: dict[str, pd.DataFrame],
    output_dir: Path,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    charts_dir = output_dir / "charts" / "after_phase2_3"
    candidates = bundle["visual_candidates"]
    abc = candidates[candidates["review_category"] == "abc"].copy()
    for _, row in abc.iterrows():
        spec = next(item for item in specs if item.example_id == row["example_id"])
        filename = f"{label}_{int(row['candidate_order']):03d}_{row['candidate_id']}.png".replace(":", "-")
        chart_path = charts_dir / filename
        frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
        plot_visual_review_candidate(frame, bundle["degree_pivots"], bundle["count_legs"], row, chart_path)
        rel_path = chart_path.relative_to(output_dir)
        record = row.to_dict()
        record.update({"phase": label, "fixed_chart_path": str(rel_path), "abc_interpretation": "candidate_abc_visual_review_only"})
        rows.append(record)
    return pd.DataFrame(rows)


def _plot_phase24_h4_context(
    *,
    specs: tuple[VisualReviewSpec, ...],
    bundle: dict[str, pd.DataFrame],
    output_dir: Path,
    htf_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    context_tables = _build_context_tables(WaveContextConfig(), htf_rows, specs=specs)
    context = context_tables["wavecount_context"]
    candidates = bundle["visual_candidates"]
    abc = candidates[candidates["review_category"] == "abc"].copy()
    candidate_context = build_candidate_context(abc, context)

    rows: list[dict[str, Any]] = []
    charts_dir = output_dir / "charts" / "after_phase2_4"
    for _, row in candidate_context.iterrows():
        spec = next(item for item in specs if item.example_id == row["example_id"])
        filename = f"h4_{int(row['candidate_order']):03d}_{row['candidate_id']}.png".replace(":", "-")
        chart_path = charts_dir / filename
        frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
        plot_context_candidate(frame, context, bundle["degree_pivots"], bundle["count_legs"], row, chart_path)
        record = row.to_dict()
        record.update({"fixed_context_chart_path": str(chart_path.relative_to(output_dir))})
        rows.append(record)
    return pd.DataFrame(rows), context, context_tables["source_windows"]


def _plot_focus_abc_cases(
    *,
    label: str,
    specs: tuple[VisualReviewSpec, ...],
    bundle: dict[str, pd.DataFrame],
    count_ids: list[str],
    output_dir: Path,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    charts_dir = output_dir / "charts" / "after_phase2_3" / "focus_cases"
    counts = bundle["candidate_counts"]
    for index, count_id in enumerate(count_ids, start=1):
        match = counts[counts["count_id"] == count_id]
        if match.empty:
            rows.append(
                {
                    "phase": label,
                    "source_id": count_id,
                    "status": "missing",
                    "fixed_chart_path": "",
                    "error": "count_id not found",
                }
            )
            continue
        count_row = match.iloc[0]
        candidate = _standard_candidate(
            count_row,
            review_category="abc",
            source_table="candidate_counts",
            source_id=count_id,
            suggested_label="ambiguous_but_interesting",
        )
        candidate["candidate_order"] = 900 + index
        candidate_row = pd.Series(candidate)
        spec = next(item for item in specs if item.example_id == candidate_row["example_id"])
        chart_path = charts_dir / f"{label}_{count_id}.png"
        try:
            frame = fetch_recent_ohlc(spec.symbol, spec.timeframe, spec.rows)
            plot_visual_review_candidate(frame, bundle["degree_pivots"], bundle["count_legs"], candidate_row, chart_path)
            record = candidate.copy()
            record.update(
                {
                    "phase": label,
                    "status": "ok",
                    "fixed_chart_path": str(chart_path.relative_to(output_dir)),
                    "error": "",
                }
            )
            rows.append(record)
        except Exception as exc:
            record = candidate.copy()
            record.update({"phase": label, "status": "error", "fixed_chart_path": "", "error": str(exc)})
            rows.append(record)
    return pd.DataFrame(rows)


def _copy_before_examples(output_dir: Path) -> list[dict[str, str]]:
    examples = [
        (LEGACY_PHASE23_H4, "charts/abc/026_abc_metals_xagusd_h4_abc_003.png"),
        (LEGACY_PHASE24_H4, "charts/abc/026_abc_metals_xagusd_h4_abc_003.png"),
        (LEGACY_PHASE23_H1, "charts/abc/036_abc_forex_gbpusd_h1_abc_003.png"),
        (LEGACY_PHASE23_H1, "charts/abc/030_abc_metals_xagusd_h1_abc_002.png"),
    ]
    copied: list[dict[str, str]] = []
    target_dir = output_dir / "charts" / "before_examples"
    target_dir.mkdir(parents=True, exist_ok=True)
    for source_root, relative in examples:
        source = source_root / relative
        if not source.exists():
            copied.append({"source": str(source), "copied_to": "", "status": "missing"})
            continue
        target = target_dir / f"{source_root.name}_{Path(relative).name}"
        shutil.copy2(source, target)
        copied.append({"source": str(source), "copied_to": str(target.relative_to(output_dir)), "status": "ok"})
    return copied


def _write_report(
    output_dir: Path,
    *,
    before: pd.DataFrame,
    after: pd.DataFrame,
    phase23: pd.DataFrame,
    phase24: pd.DataFrame,
    focus: pd.DataFrame,
    elapsed_seconds: float,
) -> None:
    before_problems = before["problem"].value_counts().to_dict() if not before.empty else {}
    after_not_ready = int((~after["plot_ready"].astype(bool)).sum()) if not after.empty else 0
    lines = [
        "# WaveCount ABC Fix - Fase 2.3/2.4",
        "",
        "Fecha: 2026-05-20",
        "",
        "## Diagnostico",
        "",
        "El fallo principal era metodologico/representacional: los `count_id` de ABC se repetian entre grados `minor`, `intermediate` y `major`.",
        "Las galerias filtraban `count_legs` solo por `count_id`, por lo que un grafico ABC podia dibujar tres candidatos superpuestos con etiquetas `0/A/B/C` repetidas.",
        "",
        f"- problemas antes: {before_problems}",
        f"- ABC corregidos revisados despues: {len(after)}",
        f"- ABC no listos para plot despues: {after_not_ready}",
        "",
        "## Correccion",
        "",
        "- Los `count_id` de Fase 2 ahora incluyen el grado de swing.",
        "- El plotting de ABC filtra tambien por `swing_degree` para ser compatible con artifacts antiguos.",
        "- Un ABC para plot debe tener exactamente cuatro puntos `0 -> A -> B -> C` en orden temporal estricto.",
        "- ABC deja de preetiquetarse como `visually_good_abc`; queda como `ambiguous_but_interesting` hasta revision visual.",
        "- Se anade control causal: `count_detected_at` sigue siendo el maximo `structural_detected_at` usado.",
        "",
        "## Regeneracion",
        "",
        f"- graficos ABC Fase 2.3 corregidos: {len(phase23)}",
        f"- graficos ABC Fase 2.4 H4/D1 corregidos: {len(phase24)}",
        f"- casos problematicos/focus corregidos: {int((focus['status'] == 'ok').sum()) if not focus.empty and 'status' in focus.columns else 0}",
        f"- tiempo de ejecucion: {elapsed_seconds:.2f}s",
        "",
        "## Decision",
        "",
        "ABC queda corregido como candidato visual/estructural, no como senal. La lectura en tiempo real sigue siendo experimental: un extremo A/B/C puede estar atras en el grafico, pero solo se conoce cuando su `structural_detected_at` lo confirma.",
        "Antes de usar ABC para Fase 2.5 hay que revisar la galeria corregida y separar estados futuros como `abc_in_progress`, `abc_completed`, `ambiguous_correction` y `not_clean_abc`.",
    ]
    (output_dir / "WAVECOUNT_ABC_FIX_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_abc_fix_artifacts(output_dir: Path = DEFAULT_OUTPUT_DIR, htf_rows: int = 260) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    h4 = _build_bundle(H4_D1_VISUAL_REVIEW_SPECS)
    h1 = _build_bundle(DEFAULT_VISUAL_REVIEW_SPECS)

    before = pd.concat(
        [
            _legacy_before_diagnostics(label="phase2_3_h4_legacy", legacy_dir=LEGACY_PHASE23_H4, fixed_legs=h4["count_legs"]),
            _legacy_before_diagnostics(label="phase2_3_h1_legacy", legacy_dir=LEGACY_PHASE23_H1, fixed_legs=h1["count_legs"]),
        ],
        ignore_index=True,
    )
    after = pd.concat(
        [
            _after_diagnostics("phase2_3_h4_fixed", h4["visual_candidates"], h4["count_legs"]),
            _after_diagnostics("phase2_3_h1_fixed", h1["visual_candidates"], h1["count_legs"]),
        ],
        ignore_index=True,
    )

    phase23 = pd.concat(
        [
            _plot_phase23_abc(label="h4", specs=H4_D1_VISUAL_REVIEW_SPECS, bundle=h4, output_dir=output_dir),
            _plot_phase23_abc(label="h1", specs=DEFAULT_VISUAL_REVIEW_SPECS, bundle=h1, output_dir=output_dir),
        ],
        ignore_index=True,
    )
    phase24, context, source_windows = _plot_phase24_h4_context(
        specs=H4_D1_VISUAL_REVIEW_SPECS,
        bundle=h4,
        output_dir=output_dir,
        htf_rows=htf_rows,
    )
    focus = pd.concat(
        [
            _plot_focus_abc_cases(
                label="h4",
                specs=H4_D1_VISUAL_REVIEW_SPECS,
                bundle=h4,
                count_ids=["metals_xagusd_h4_intermediate_abc_003"],
                output_dir=output_dir,
            ),
            _plot_focus_abc_cases(
                label="h1",
                specs=DEFAULT_VISUAL_REVIEW_SPECS,
                bundle=h1,
                count_ids=[
                    "forex_gbpusd_h1_minor_abc_002",
                    "forex_gbpusd_h1_intermediate_abc_002",
                    "forex_gbpusd_h1_major_abc_003",
                    "metals_xagusd_h1_minor_abc_002",
                ],
                output_dir=output_dir,
            ),
        ],
        ignore_index=True,
    )
    before_copies = _copy_before_examples(output_dir)

    downgraded = after.copy()
    downgraded["change_type"] = "abc_label_downgraded_from_visually_good_to_manual_review"
    downgraded = downgraded[downgraded["suggested_initial_label"] == "ambiguous_but_interesting"].copy()
    clean = after[after["plot_ready"].astype(bool)].copy()
    clean["clean_scope"] = "plot_clean_candidate_not_trading_signal"

    before.to_csv(tables_dir / "abc_diagnostics_before.csv", index=False)
    after.to_csv(tables_dir / "abc_diagnostics_after.csv", index=False)
    downgraded.to_csv(tables_dir / "abc_rejected_or_downgraded.csv", index=False)
    clean.to_csv(tables_dir / "abc_clean_candidates.csv", index=False)
    phase23.to_csv(tables_dir / "phase2_3_abc_fixed_candidates.csv", index=False)
    phase24.to_csv(tables_dir / "phase2_4_abc_fixed_context.csv", index=False)
    focus.to_csv(tables_dir / "abc_focus_cases.csv", index=False)
    source_windows.to_csv(tables_dir / "phase2_4_h4_context_source_windows.csv", index=False)

    elapsed_seconds = perf_counter() - start
    _write_report(output_dir, before=before, after=after, phase23=phase23, phase24=phase24, focus=focus, elapsed_seconds=elapsed_seconds)

    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "output_dir": str(output_dir),
        "htf_rows": htf_rows,
        "context_config": context_config_to_dict(WaveContextConfig()),
        "h4_specs": [asdict(item) for item in H4_D1_VISUAL_REVIEW_SPECS],
        "h1_specs": [asdict(item) for item in DEFAULT_VISUAL_REVIEW_SPECS],
        "counts": {
            "before_rows": len(before),
            "after_rows": len(after),
            "phase2_3_fixed_charts": len(phase23),
            "phase2_4_fixed_charts": len(phase24),
            "focus_case_charts": int((focus["status"] == "ok").sum()) if not focus.empty and "status" in focus.columns else 0,
            "context_rows": len(context),
        },
        "before_examples": before_copies,
        "outputs": {
            "abc_diagnostics_before": "tables/abc_diagnostics_before.csv",
            "abc_diagnostics_after": "tables/abc_diagnostics_after.csv",
            "abc_rejected_or_downgraded": "tables/abc_rejected_or_downgraded.csv",
            "abc_clean_candidates": "tables/abc_clean_candidates.csv",
            "phase2_3_abc_fixed_candidates": "tables/phase2_3_abc_fixed_candidates.csv",
            "phase2_4_abc_fixed_context": "tables/phase2_4_abc_fixed_context.csv",
            "abc_focus_cases": "tables/abc_focus_cases.csv",
            "report": "WAVECOUNT_ABC_FIX_REPORT.md",
        },
        "notes": [
            "No strategies, signals, MT5, backtests, dashboard or Telegram integration are touched.",
            "ABC remains a visual/structural candidate, not an operative signal.",
            "Phase 2.4 adds diagnostic context only and cannot rescue a bad ABC.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount ABC fix diagnostics and corrected mini galleries.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--htf-rows", type=int, default=260)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_abc_fix_artifacts(output_dir=args.output_dir, htf_rows=args.htf_rows)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
