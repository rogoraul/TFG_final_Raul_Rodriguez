from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE231_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_1_wave5_endpoint_2026-05-21"


MANUAL_INTERPRETATIONS: dict[str, dict[str, Any]] = {
    "impulse_forex_audjpy_h1_minor_impulse_013": {
        "latest_user_interpretation": (
            "Se ve bien como conteo local. La onda 5 podria terminar algo mas arriba, "
            "y las cinco ondas podrian ser una onda 1 mayor o parte de una 1-2-3 mayor."
        ),
        "visual_validity_after_review": "valid_local_count",
        "endpoint_interpretation": "endpoint_uncertain_not_bad_count",
        "higher_degree_substructure_possible": True,
        "possible_higher_degree_read": "possible_wave_1_or_part_of_wave_3",
        "should_not_downgrade_visual_quality": True,
        "final_methodological_label": "candidate_impulse_provisional_with_endpoint_uncertainty",
        "recommended_action": "keep_as_local_example_with_higher_degree_note",
    },
    "impulse_index_aus200_h1_minor_impulse_006": {
        "latest_user_interpretation": (
            "Podria estar bien como minor. Visualmente tambien encaja como onda 1-2 "
            "y arranque de una tercera mayor; no debe tratarse como conteo malo automaticamente."
        ),
        "visual_validity_after_review": "valid_local_or_higher_degree_setup",
        "endpoint_interpretation": "endpoint_uncertain_not_bad_count",
        "higher_degree_substructure_possible": True,
        "possible_higher_degree_read": "possible_wave_1_2_then_wave_3_start",
        "should_not_downgrade_visual_quality": True,
        "final_methodological_label": "possible_higher_degree_subwave",
        "recommended_action": "keep_as_ambiguous_higher_degree_example",
    },
    "impulse_forex_audjpy_h1_intermediate_impulse_009": {
        "latest_user_interpretation": "Esta bien y debe mantenerse como buen ejemplo.",
        "visual_validity_after_review": "good_example",
        "endpoint_interpretation": "clean_or_unresolved_endpoint",
        "higher_degree_substructure_possible": False,
        "possible_higher_degree_read": "",
        "should_not_downgrade_visual_quality": True,
        "final_methodological_label": "candidate_impulse_provisional_good_example",
        "recommended_action": "keep_as_good_example",
    },
    "near_miss_forex_audjpy_h1_intermediate_impulse_011": {
        "latest_user_interpretation": (
            "Visualmente gusta. Puede no exceder onda 3 porque el grafico se corta; "
            "no debe etiquetarse como truncamiento definitivo sin esa limitacion."
        ),
        "visual_validity_after_review": "visually_good_near_miss",
        "endpoint_interpretation": "truncation_uncertain_due_to_window_cut",
        "higher_degree_substructure_possible": True,
        "possible_higher_degree_read": "possible_continuation_outside_window",
        "should_not_downgrade_visual_quality": True,
        "final_methodological_label": "near_miss_with_window_cut_uncertainty",
        "recommended_action": "keep_as_near_miss_with_limitation",
    },
    "near_miss_index_aus200_h1_intermediate_impulse_008": {
        "latest_user_interpretation": "Esta bien / aceptable como near-miss.",
        "visual_validity_after_review": "acceptable_near_miss",
        "endpoint_interpretation": "near_miss_not_clean_impulse",
        "higher_degree_substructure_possible": False,
        "possible_higher_degree_read": "",
        "should_not_downgrade_visual_quality": True,
        "final_methodological_label": "acceptable_near_miss",
        "recommended_action": "keep_as_near_miss_example",
    },
    "impulse_forex_eurjpy_m30_intermediate_impulse_005": {
        "latest_user_interpretation": (
            "Se ve bien. Puede considerarse que la onda 5 termina ahi o que recoge "
            "toda la bajada; no debe penalizarse agresivamente."
        ),
        "visual_validity_after_review": "valid_local_count",
        "endpoint_interpretation": "endpoint_uncertain_not_bad_count",
        "higher_degree_substructure_possible": True,
        "possible_higher_degree_read": "possible_extended_wave_5_or_larger_leg",
        "should_not_downgrade_visual_quality": True,
        "final_methodological_label": "candidate_impulse_provisional_with_endpoint_uncertainty",
        "recommended_action": "keep_as_valid_but_provisional",
    },
}


def _load_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def build_manual_interpretation_update(phase231_dir: Path = DEFAULT_PHASE231_DIR) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    tables_dir = phase231_dir / "tables"
    manual = _load_required(tables_dir / "manual_cases_wave5_review.csv")
    diagnostics = _load_required(tables_dir / "wave5_endpoint_diagnostics.csv")

    rows: list[dict[str, Any]] = []
    for candidate_id, interpretation in MANUAL_INTERPRETATIONS.items():
        manual_match = manual[manual["candidate_id"] == candidate_id]
        diagnostic_match = diagnostics[diagnostics["candidate_id"] == candidate_id]
        if manual_match.empty:
            raise ValueError(f"manual case not found: {candidate_id}")
        row = manual_match.iloc[0].to_dict()
        if not diagnostic_match.empty:
            diagnostic = diagnostic_match.iloc[0].to_dict()
            for column in [
                "wave5_endpoint_status",
                "proposed_endpoint_classification",
                "future_more_extreme_found",
                "post_wave5_extreme_time",
                "post_wave5_extension_vs_wave5",
                "post_wave5_extension_vs_wave1",
                "causal_note",
            ]:
                row[column] = diagnostic.get(column, row.get(column, ""))
        row.update(interpretation)
        rows.append(row)

    update = pd.DataFrame(rows).sort_values("candidate_order").reset_index(drop=True)
    rules = pd.DataFrame(
        [
            {
                "concept": "premature_wave5_completion",
                "old_risk": "could be read as bad count or downgrade",
                "new_interpretation": "endpoint uncertainty; local count can remain visually valid",
                "preferred_live_state": "candidate_impulse_provisional_with_endpoint_uncertainty",
                "when_to_use": "later same-direction structural extreme appears, or user sees a natural endpoint slightly beyond wave 5",
                "should_downgrade_visual_quality": False,
                "higher_degree_note": "may be a full minor/intermediate impulse inside wave 1 or wave 3 of a higher degree",
            },
            {
                "concept": "truncated_fifth_candidate",
                "old_risk": "could be read as definitive failed impulse",
                "new_interpretation": "near-miss or possible truncation; not clean impulse, but not automatically bad",
                "preferred_live_state": "near_miss_with_truncation_or_window_uncertainty",
                "when_to_use": "wave 5 does not exceed wave 3, especially near the end of the visible window",
                "should_downgrade_visual_quality": False,
                "higher_degree_note": "needs more bars/context before calling truncation definitive",
            },
            {
                "concept": "possible_higher_degree_subwave",
                "old_risk": "local five-wave structure overinterpreted as completed Elliott impulse",
                "new_interpretation": "valid local count that may be one leg of a higher-degree impulse",
                "preferred_live_state": "possible_higher_degree_subwave",
                "when_to_use": "minor/intermediate five-wave count sits inside a broader leg or continuation",
                "should_downgrade_visual_quality": False,
                "higher_degree_note": "requires future multi-degree state machine before firm labelling",
            },
            {
                "concept": "visually_bad_count",
                "old_risk": "mixed with endpoint uncertainty",
                "new_interpretation": "separate category for forced shape, wrong pivots, incoherent structure",
                "preferred_live_state": "ambiguous_count_or_negative_example",
                "when_to_use": "shape is visually forced independent of wave-5 endpoint uncertainty",
                "should_downgrade_visual_quality": True,
                "higher_degree_note": "do not rescue poor local geometry with higher-degree language",
            },
        ]
    )

    update_path = tables_dir / "wave5_manual_interpretation_update.csv"
    rules_path = tables_dir / "wave5_endpoint_interpretation_rules.csv"
    update.to_csv(update_path, index=False)
    rules.to_csv(rules_path, index=False)

    report_path = phase231_dir / "WAVECOUNT_PHASE2_3_1_INTERPRETATION_UPDATE.md"
    lines = [
        "# WaveCount Fase 2.3.1 - Ajuste de interpretacion",
        "",
        "Fecha: 2026-05-21",
        "",
        "Esta actualizacion no cambia reglas, pivotes, conteos ni estrategias. Solo corrige la lectura metodologica del diagnostico de endpoint de onda 5.",
        "",
        "## Decision",
        "",
        "`premature_wave5_completion` no significa automaticamente conteo malo. Debe leerse como incertidumbre de endpoint, provisionalidad o posible subestructura de grado superior.",
        "",
        "## Casos revisados",
        "",
    ]
    for _, row in update.iterrows():
        lines.extend(
            [
                f"### {row['candidate_id']}",
                "",
                f"- interpretacion: {row['latest_user_interpretation']}",
                f"- etiqueta metodologica final: `{row['final_methodological_label']}`",
                f"- posible subonda de grado mayor: {row['higher_degree_substructure_possible']}",
                f"- accion: `{row['recommended_action']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Regla de lectura",
            "",
            "La fase queda como capa de incertidumbre sobre endpoint de onda 5, no como detector agresivo de conteos malos. Los conteos visualmente validos pueden mantenerse como ejemplos locales/provisionales aunque el endpoint sea incierto.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": perf_counter() - start,
        "phase231_dir": str(phase231_dir),
        "outputs": {
            "manual_interpretation_update": str(update_path),
            "endpoint_interpretation_rules": str(rules_path),
            "report": str(report_path),
        },
        "rows": {
            "manual_interpretation_update": len(update),
            "endpoint_interpretation_rules": len(rules),
        },
        "notes": [
            "Interpretation-only update.",
            "No WaveCount count rules, strategies, signals, backtests or canonical benchmark artifacts were changed.",
        ],
    }
    meta_path = phase231_dir / "interpretation_update_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.3.1 wave-5 interpretation update tables.")
    parser.add_argument("--phase2-3-1-dir", type=Path, default=DEFAULT_PHASE231_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_manual_interpretation_update(args.phase2_3_1_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
