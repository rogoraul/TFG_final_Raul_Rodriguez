from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARTIAL123_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_partial123_2026-05-21"


LATEST_MANUAL_REVIEW: dict[str, dict[str, Any]] = {
    "partial_123_index_aus200_h1_intermediate_partial123_001": {
        "latest_user_interpretation": "No deberia entrar un conteo Elliott: senales cortas, debiles y sin continuacion.",
        "manual_visual_label": "no_elliott_count_weak_no_continuation",
        "should_keep_as_methodology_example": True,
        "example_role": "negative_example",
        "recommended_action_after_latest_review": "do_not_use_as_partial123_positive_case",
        "methodological_note": "No basta con cuatro pivotes alternantes si el tramo es corto, debil y no deja continuacion hacia 4-5.",
        "external_context_note": "",
    },
    "partial_123_forex_audjpy_h1_minor_partial123_007": {
        "latest_user_interpretation": "Podria considerarse decente, pero no gusta demasiado porque cuenta ondas en un mercado lateral de correccion.",
        "manual_visual_label": "ambiguous_partial_in_corrective_range",
        "should_keep_as_methodology_example": True,
        "example_role": "ambiguous_example",
        "recommended_action_after_latest_review": "keep_as_ambiguous_not_positive_case",
        "methodological_note": "Un parcial en rango/correccion lateral puede ser geometricamente plausible, pero no debe usarse como ejemplo positivo claro.",
        "external_context_note": "",
    },
    "partial_123_metals_xagusd_h1_minor_partial123_002": {
        "latest_user_interpretation": (
            "Mismo problema que 015: no deberia entrar conteo Elliott por debilidad/falta de continuacion. "
            "A favor del caso, alrededor del 1 de marzo empezo la guerra de Iran y genero oscilacion drastica de precios."
        ),
        "manual_visual_label": "no_elliott_count_event_volatility",
        "should_keep_as_methodology_example": True,
        "example_role": "negative_example_with_event_context",
        "recommended_action_after_latest_review": "do_not_use_as_partial123_positive_case",
        "methodological_note": "La volatilidad/evento puede explicar oscilaciones bruscas, pero no convierte una estructura debil en conteo Elliott limpio.",
        "external_context_note": "Contexto aportado por el usuario: entorno de guerra de Iran alrededor del 1 de marzo; tratar como posible distorsion de volatilidad, no como regla.",
    },
}


def build_partial123_manual_update(partial123_dir: Path = DEFAULT_PARTIAL123_DIR) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    tables_dir = partial123_dir / "tables"
    manual_path = tables_dir / "partial123_manual_cases_review.csv"
    if not manual_path.exists():
        raise FileNotFoundError(manual_path)
    manual = pd.read_csv(manual_path)
    rows: list[dict[str, Any]] = []
    for candidate_id, update in LATEST_MANUAL_REVIEW.items():
        matches = manual[manual["candidate_id"] == candidate_id]
        if matches.empty:
            raise ValueError(f"manual partial case not found: {candidate_id}")
        row = matches.iloc[0].to_dict()
        row.update(update)
        rows.append(row)
    update_df = pd.DataFrame(rows).sort_values("candidate_order").reset_index(drop=True)
    rules = pd.DataFrame(
        [
            {
                "rule_area": "weak_no_continuation",
                "manual_basis": "015 and 018",
                "interpretation": "do not force Elliott count on short/weak structures with no continuation",
                "future_use": "negative examples for visual quality filter",
                "hard_or_soft": "soft_visual_rule",
            },
            {
                "rule_area": "corrective_range_context",
                "manual_basis": "017",
                "interpretation": "partial may be geometrically plausible but should remain ambiguous inside lateral/corrective market",
                "future_use": "context/scoring penalty, not hard invalidation",
                "hard_or_soft": "soft_context_rule",
            },
            {
                "rule_area": "event_volatility_context",
                "manual_basis": "018",
                "interpretation": "external volatility can explain swings but should not rescue weak Elliott structure",
                "future_use": "document as limitation when using event-distorted examples",
                "hard_or_soft": "documentation_guard",
            },
        ]
    )
    update_path = tables_dir / "partial123_latest_manual_update_2026-05-22.csv"
    rules_path = tables_dir / "partial123_latest_manual_rules_2026-05-22.csv"
    update_df.to_csv(update_path, index=False)
    rules.to_csv(rules_path, index=False)

    report_path = partial123_dir / "WAVECOUNT_PHASE2_3_2_PARTIAL123_MANUAL_UPDATE_2026-05-22.md"
    lines = [
        "# WaveCount Fase 2.3.2 - Actualizacion manual",
        "",
        "Fecha: 2026-05-22",
        "",
        "Esta actualizacion incorpora la revision manual del usuario sobre los tres parciales clave. No cambia reglas, pivotes, grados, ABC, estrategias ni senales.",
        "",
        "## Casos",
        "",
    ]
    for _, row in update_df.iterrows():
        lines.extend(
            [
                f"### {row['candidate_id']}",
                "",
                f"- lectura: {row['latest_user_interpretation']}",
                f"- etiqueta manual: `{row['manual_visual_label']}`",
                f"- rol: `{row['example_role']}`",
                f"- accion: `{row['recommended_action_after_latest_review']}`",
                f"- nota: {row['methodological_note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Decision",
            "",
            "015 y 018 quedan como ejemplos negativos de estructuras debiles/sin continuacion. 017 queda como ejemplo ambiguo: puede ser decente geometricamente, pero esta en rango/correccion lateral y no debe usarse como caso positivo claro.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": perf_counter() - start,
        "partial123_dir": str(partial123_dir),
        "rows": {
            "latest_manual_update": len(update_df),
            "latest_manual_rules": len(rules),
        },
        "outputs": {
            "latest_manual_update": str(update_path),
            "latest_manual_rules": str(rules_path),
            "report": str(report_path),
        },
        "notes": [
            "Manual interpretation update only.",
            "No WaveCount rules, strategies, signals, ABC or degree calibration were changed.",
        ],
    }
    (partial123_dir / "manual_update_2026-05-22_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.3.2 latest manual update.")
    parser.add_argument("--partial123-dir", type=Path, default=DEFAULT_PARTIAL123_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_partial123_manual_update(args.partial123_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
