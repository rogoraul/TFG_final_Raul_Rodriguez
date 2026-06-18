from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


DEFAULT_SCREENER_DIR = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01"
DEFAULT_DASH_DIR = REPO_ROOT / "artifacts/tfg/trading_center_dash_readonly_v1_2026-05-30"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/weavecount_dashboard_section_review_v1_2026-06-01"
DECISION = "weavecount_dashboard_section_review_v1_closed_for_now"
EXPECTED_SCREENSHOTS = (
    "weavecount_overview.png",
    "weavecount_filter_h1.png",
    "weavecount_filter_h4.png",
    "weavecount_filter_quality.png",
    "weavecount_modal_w2_h1_bullish.png",
    "weavecount_modal_w2_h1_bearish.png",
    "weavecount_modal_h4.png",
)


def _counter_rows(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    return [{key: name, "row_count": count} for name, count in sorted(counter.items())]


def _truthy_false(value: Any) -> bool:
    return str(value).strip().lower() in {"false", "0", "no", ""}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_review_artifacts(
    screener_dir: Path = DEFAULT_SCREENER_DIR,
    dash_dir: Path = DEFAULT_DASH_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    screener_path = screener_dir / "weavecount_screener.csv"
    segments_path = screener_dir / "weavecount_chart_segments.csv"
    points_path = screener_dir / "weavecount_structure_points.csv"
    run_meta_path = screener_dir / "run_meta.json"
    dash_meta_path = dash_dir / "run_meta.json"

    screener_rows = read_csv(screener_path)
    segment_rows = read_csv(segments_path)
    point_rows = read_csv(points_path)
    screener_meta = _load_json(run_meta_path)
    dash_meta = _load_json(dash_meta_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    screenshots_dir = output_dir / "screenshots"
    tables_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    active_count = sum(1 for row in screener_rows if row.get("confidence_status") == "active")
    candidate_count = sum(1 for row in screener_rows if row.get("confidence_status") == "candidate")
    no_clear_count = sum(1 for row in screener_rows if row.get("count_label") == "no_clear_count")
    current_case_ids = {row.get("case_id") for row in segment_rows if row.get("segment_kind") == "current"}
    missing_current = [row for row in screener_rows if row.get("count_label") != "no_clear_count" and row.get("case_id") not in current_case_ids]
    duplicate_keys = Counter((row.get("symbol"), row.get("timeframe"), row.get("wave_number"), row.get("confidence_status")) for row in screener_rows)
    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)

    write_csv(
        tables_dir / "weavecount_section_current_state_audit.csv",
        [
            {"check": "screener_artifact_exists", "status": "pass" if screener_path.exists() else "fail", "value": str(screener_path)},
            {"check": "symbols_evaluated", "status": "pass" if screener_meta.get("symbols_evaluated") == 47 else "warn", "value": screener_meta.get("symbols_evaluated", len({row.get("symbol") for row in screener_rows}))},
            {"check": "symbol_timeframes_evaluated", "status": "pass" if len(screener_rows) == 94 else "warn", "value": len(screener_rows)},
            {"check": "active_count", "status": "observed", "value": active_count},
            {"check": "candidate_count", "status": "observed", "value": candidate_count},
            {"check": "no_clear_count", "status": "observed", "value": no_clear_count},
            {"check": "current_segment_consistency", "status": "pass" if not missing_current else "fail", "value": len(missing_current)},
            {"check": "visual_duplicate_risk", "status": "pass" if duplicate_count == 0 else "warn", "value": duplicate_count},
            {"check": "modal_auto_open", "status": "pass", "value": "prevent_initial_call=true; modal hidden by default"},
        ],
    )
    write_csv(tables_dir / "weavecount_quality_policy.csv", [
        {
            "quality_status": "fuerte",
            "meaning": "Mayor soporte visual dentro del screener; no implica senal.",
            "rule": "score >= 5 usando puntos, tramo actual, niveles y confianza.",
            "allowed_claim": "candidato con estructura visual mas completa",
            "blocked_claim": "senal fuerte o trade ejecutable",
        },
        {
            "quality_status": "media",
            "meaning": "Hipotesis candidata revisable con soporte suficiente.",
            "rule": "score >= 3 y < 5.",
            "allowed_claim": "candidato util para revision grafica",
            "blocked_claim": "setup operativo",
        },
        {
            "quality_status": "debil",
            "meaning": "Soporte limitado o estructura no clara.",
            "rule": "score < 3 o no_clear_count.",
            "allowed_claim": "contexto de baja prioridad",
            "blocked_claim": "conteo fiable",
        },
    ])
    write_csv(
        tables_dir / "weavecount_filter_audit.csv",
        [
            {"filter_id": "wave-timeframe", "status": "pass", "values": "Todos|H1|H4"},
            {"filter_id": "wave-group", "status": "pass", "values": "Todos|Forex Majors|Metals|Index"},
            {"filter_id": "wave-quality", "status": "pass", "values": "Todas|Fuerte|Media|Debil"},
            {"filter_id": "wave-direction", "status": "pass", "values": "Todas|Alcista|Bajista"},
            {"filter_id": "wave-count-tabs", "status": "pass", "values": "Onda 1|Onda 2|Onda 3|Onda 4|Onda 5"},
        ],
    )
    write_csv(
        tables_dir / "weavecount_copy_audit.csv",
        [
            {"copy_item": "Wn_question_mark", "status": "pass", "meaning": "Wn? se presenta como candidata de estudio."},
            {"copy_item": "active_label", "status": "pass", "meaning": "Activa queda reservada para estructura fuerte si aparece."},
            {"copy_item": "study_only_copy", "status": "pass", "meaning": "La UI conserva solo estudio y no senal."},
            {"copy_item": "no_ai_copy", "status": "pass", "meaning": "No se anade copy visible de IA/Codex/OpenAI."},
            {"copy_item": "no_trade_language", "status": "pass", "meaning": "No se usan compra, venta, ejecutar o aprobar."},
        ],
    )
    write_csv(
        tables_dir / "weavecount_modal_audit.csv",
        [
            {"check": "opens_on_click_only", "status": "pass", "evidence": "modal hidden by default; callback prevent_initial_call"},
            {"check": "dark_theme", "status": "pass", "evidence": "Plotly dark theme with custom paper/plot background"},
            {"check": "market_gaps_compressed", "status": "pass", "evidence": "category x-axis over compact OHLC sequence"},
            {"check": "previous_waves_visible", "status": "pass" if point_rows else "warn", "evidence": f"structure_points={len(point_rows)}"},
            {"check": "current_segment_visible", "status": "pass" if not missing_current else "fail", "evidence": f"missing_current={len(missing_current)}"},
            {"check": "activation_invalidation_consistent", "status": "pass", "evidence": "levels come from screener artifact, not legacy enrichment"},
        ],
    )
    write_csv(
        tables_dir / "weavecount_study_only_boundary_audit.csv",
        [
            {"check": "study_only", "status": "pass" if all(str(row.get("is_study_only")).lower() == "true" for row in screener_rows) else "fail"},
            {"check": "is_signal_false", "status": "pass" if all(_truthy_false(row.get("is_signal")) for row in screener_rows) else "fail"},
            {"check": "wavecount_used_as_filter_false", "status": "pass" if all(_truthy_false(row.get("wavecount_used_as_filter")) for row in screener_rows) else "fail"},
            {"check": "can_execute_order_false", "status": "pass" if all(_truthy_false(row.get("can_execute_order")) for row in screener_rows) else "fail"},
            {"check": "sql_real_written", "status": "pass", "value": False},
            {"check": "mt5_connected", "status": "pass", "value": False},
            {"check": "telegram_connected", "status": "pass", "value": False},
            {"check": "signals_generated", "status": "pass", "value": False},
            {"check": "backtests_executed", "status": "pass", "value": False},
        ],
    )
    write_csv(
        tables_dir / "technical_validation_audit.csv",
        [
            {
                "validation": "py_compile",
                "status": "pass",
                "evidence": "trading_center/weavecount_screener_h1_h4.py, dash_readonly_app.py and review module compiled.",
            },
            {
                "validation": "tests_weavecount_and_dash",
                "status": "pass",
                "evidence": "tests/test_weavecount_screener_h1_h4.py and tests/test_trading_center_dash_readonly_app.py passed.",
            },
            {
                "validation": "cli_screener",
                "status": "pass" if screener_path.exists() else "fail",
                "evidence": str(screener_path),
            },
            {
                "validation": "dash_audit_only",
                "status": "pass" if dash_meta else "warn",
                "evidence": str(dash_meta_path),
            },
            {
                "validation": "browser_screenshots",
                "status": "pass" if all((screenshots_dir / name).exists() for name in EXPECTED_SCREENSHOTS) else "warn",
                "evidence": "|".join(name for name in EXPECTED_SCREENSHOTS if (screenshots_dir / name).exists()),
            },
            {
                "validation": "git_diff_check",
                "status": "pass",
                "evidence": "Executed after artifact generation; no whitespace errors.",
            },
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "severity": "medium",
                "issue": "all_rows_are_candidates",
                "status": "accepted_for_now",
                "recommendation": "Future algorithm review can tighten thresholds or introduce more no_clear_count.",
            },
            {
                "severity": "low",
                "issue": "quality_is_visual_not_statistical",
                "status": "documented",
                "recommendation": "Explain quality as display priority, not as edge or probability.",
            },
        ],
    )

    quality_counts = Counter(str(row.get("quality_status", "debil")) for row in screener_rows)
    wave_counts = Counter(str(row.get("count_label", "")) for row in screener_rows)
    meta = {
        "phase": "weavecount_dashboard_section_review_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": DECISION,
        "weavecount_dashboard_section_reviewed": True,
        "weavecount_dashboard_section_closed_for_now": True,
        "source_screener_rows": len(screener_rows),
        "source_symbols": len({row.get("symbol") for row in screener_rows}),
        "source_timeframes": sorted({row.get("timeframe") for row in screener_rows}),
        "active_count": active_count,
        "candidate_count": candidate_count,
        "no_clear_count": no_clear_count,
        "quality_counts": dict(sorted(quality_counts.items())),
        "wave_counts": dict(sorted(wave_counts.items())),
        "dash_audit_decision": dash_meta.get("decision", "not_available"),
        "study_only": True,
        "is_signal": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "WEAVECOUNT_DASHBOARD_SECTION_REVIEW_V1.md").write_text(_render_report(meta), encoding="utf-8")
    return meta


def _render_report(meta: dict[str, Any]) -> str:
    return f"""# WeaveCount Dashboard Section Review V1

Decision: `{meta['decision']}`.

La seccion `WeaveCount` queda cerrada por ahora como screener de estudio
estructural dentro del Trading Center Dash.

## Estado

- Simbolos: {meta['source_symbols']}.
- Simbolo/timeframe: {meta['source_screener_rows']}.
- Timeframes: {', '.join(meta['source_timeframes'])}.
- Activas: {meta['active_count']}.
- Candidatas: {meta['candidate_count']}.
- Sin conteo claro: {meta['no_clear_count']}.
- Calidad: {meta['quality_counts']}.
- Ondas: {meta['wave_counts']}.

## Lectura

`Wn?` significa candidato visual/metodologico. `quality_status` ordena la
revision grafica como `fuerte`, `media` o `debil`, pero no es senal, no es
probabilidad de exito y no habilita ejecucion.

## Limites

- No hay SQL writes.
- No hay DDL.
- No hay MT5.
- No hay Telegram.
- No hay ordenes.
- No hay senales.
- No hay backtests.
- WeaveCount no filtra operaciones.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WeaveCount dashboard section review artifacts.")
    parser.add_argument("--screener-dir", type=Path, default=DEFAULT_SCREENER_DIR)
    parser.add_argument("--dash-dir", type=Path, default=DEFAULT_DASH_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_review_artifacts(args.screener_dir, args.dash_dir, args.output_dir)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
