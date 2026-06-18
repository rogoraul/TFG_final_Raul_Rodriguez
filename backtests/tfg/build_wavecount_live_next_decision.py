from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_next_decision_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_NEXT_DECISION.md")
DEFAULT_LAG_RESOLUTION_DIR = Path("artifacts/tfg/wavecount_live_lag_stability_resolution_2026-05-27")
DEFAULT_APPEND_ONLY_DIR = Path("artifacts/tfg/wavecount_live_append_only_stability_design_2026-05-27")
DEFAULT_VISUAL_AUDIT_DIR = Path("artifacts/tfg/wavecount_live_visual_manual_audit_2026-05-27")


@dataclass(frozen=True)
class WaveCountLiveNextDecisionConfig:
    lag_resolution_dir: Path = DEFAULT_LAG_RESOLUTION_DIR
    append_only_dir: Path = DEFAULT_APPEND_ONLY_DIR
    visual_audit_dir: Path = DEFAULT_VISUAL_AUDIT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH


@dataclass(frozen=True)
class WaveCountLiveNextDecisionResult:
    strategic_diagnosis: pd.DataFrame
    continuation_options: pd.DataFrame
    recommendation_matrix: pd.DataFrame
    redesign_path_if_needed: pd.DataFrame
    late_context_path: pd.DataFrame
    park_wavecount_path: pd.DataFrame
    roadmap_implications: pd.DataFrame
    do_not_do_yet: pd.DataFrame
    open_decisions: pd.DataFrame
    run_meta: dict[str, Any]
    recommendation: str
    written_files: dict[str, Path]


def build_wavecount_live_next_decision(
    config: WaveCountLiveNextDecisionConfig | None = None,
) -> WaveCountLiveNextDecisionResult:
    config = config or WaveCountLiveNextDecisionConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source = load_source_tables(config)
    metrics = extract_metrics(source)

    strategic_diagnosis = build_strategic_diagnosis(metrics)
    continuation_options = build_continuation_options(metrics)
    recommendation_matrix = build_recommendation_matrix(metrics)
    recommendation = "hybrid_late_context_plus_enbolsa_platform"
    redesign_path_if_needed = build_redesign_path()
    late_context_path = build_late_context_path(metrics)
    park_wavecount_path = build_park_wavecount_path()
    roadmap_implications = build_roadmap_implications(recommendation)
    do_not_do_yet = build_do_not_do_yet()
    open_decisions = build_open_decisions(source, recommendation)
    run_meta = build_run_meta(generated_at, config, metrics, recommendation)
    written = write_outputs(
        config=config,
        strategic_diagnosis=strategic_diagnosis,
        continuation_options=continuation_options,
        recommendation_matrix=recommendation_matrix,
        redesign_path_if_needed=redesign_path_if_needed,
        late_context_path=late_context_path,
        park_wavecount_path=park_wavecount_path,
        roadmap_implications=roadmap_implications,
        do_not_do_yet=do_not_do_yet,
        open_decisions=open_decisions,
        run_meta=run_meta,
    )
    write_docs(
        config=config,
        strategic_diagnosis=strategic_diagnosis,
        continuation_options=continuation_options,
        recommendation_matrix=recommendation_matrix,
        redesign_path_if_needed=redesign_path_if_needed,
        late_context_path=late_context_path,
        park_wavecount_path=park_wavecount_path,
        roadmap_implications=roadmap_implications,
        open_decisions=open_decisions,
        recommendation=recommendation,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_NEXT_DECISION.md"
    return WaveCountLiveNextDecisionResult(
        strategic_diagnosis=strategic_diagnosis,
        continuation_options=continuation_options,
        recommendation_matrix=recommendation_matrix,
        redesign_path_if_needed=redesign_path_if_needed,
        late_context_path=late_context_path,
        park_wavecount_path=park_wavecount_path,
        roadmap_implications=roadmap_implications,
        do_not_do_yet=do_not_do_yet,
        open_decisions=open_decisions,
        run_meta=run_meta,
        recommendation=recommendation,
        written_files=written,
    )


def load_source_tables(config: WaveCountLiveNextDecisionConfig) -> dict[str, pd.DataFrame]:
    required = {
        "lag_decision": config.lag_resolution_dir / "decision_summary.csv",
        "lag_comparison": config.lag_resolution_dir / "lag_stability_config_comparison.csv",
        "lag_candidate_evaluation": config.lag_resolution_dir / "lag_stability_candidate_evaluation.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required WaveCount live decision inputs: {missing}")
    tables: dict[str, pd.DataFrame] = {name: pd.read_csv(path) for name, path in required.items()}
    optional_paths = {
        "append_only_implications": config.visual_audit_dir / "append_only_implications.csv",
        "append_only_open_decisions": config.append_only_dir / "tables" / "open_decisions.csv",
        "append_only_staging_criteria": config.append_only_dir / "tables" / "staging_entry_criteria.csv",
    }
    for name, path in optional_paths.items():
        tables[name] = pd.read_csv(path) if path.exists() else pd.DataFrame()
    return tables


def extract_metrics(source: dict[str, pd.DataFrame]) -> dict[str, Any]:
    decision = source["lag_decision"].iloc[0].to_dict()
    comparison = source["lag_comparison"].copy()
    best = comparison.sort_values("rank").iloc[0].to_dict()
    baseline = comparison[comparison["config_name"] == "baseline_actual"].iloc[0].to_dict()
    return {
        "decision": str(decision.get("decision", "")),
        "selected_config": str(decision.get("selected_config", best.get("config_name", ""))),
        "late_confirmation_pct": float(decision.get("late_confirmation_pct", best.get("late_cut_pct", 0.0))),
        "unstable_pivots_pct": float(decision.get("unstable_pivots_pct", best.get("unstable_cut_pct", 0.0))),
        "too_noisy_pct": float(decision.get("too_noisy_pct", best.get("noise_cut_pct", 0.0))),
        "best_score": float(decision.get("best_score", best.get("score", 0.0))),
        "best_detected_pivots": int(float(best.get("detected_pivots_total", 0))),
        "best_structural_pivots": int(float(best.get("structural_pivots_total", 0))),
        "baseline_detected_pivots": int(float(baseline.get("detected_pivots_total", 0))),
        "baseline_structural_pivots": int(float(baseline.get("structural_pivots_total", 0))),
        "best_completed_impulse_pct": float(best.get("completed_impulse_pct", 0.0)),
        "best_anti_lookahead": bool(str(best.get("anti_lookahead_passed", "False")).lower() == "true"),
        "best_flags": bool(str(best.get("hard_flags_fail_closed", "False")).lower() == "true"),
    }


def build_strategic_diagnosis(metrics: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "question": "does_parameter_tuning_solve_current_context",
                "answer": "no",
                "evidence": (
                    f"Best config {metrics['selected_config']} remains {metrics['decision']}: "
                    f"late={metrics['late_confirmation_pct']:.1%}, unstable={metrics['unstable_pivots_pct']:.1%}."
                ),
                "classification": "not_solved_by_grid",
            },
            {
                "question": "is_the_pipeline_causal",
                "answer": "yes_for_reviewed_sample",
                "evidence": f"anti_lookahead={metrics['best_anti_lookahead']}, hard_flags={metrics['best_flags']}.",
                "classification": "working_component",
            },
            {
                "question": "does_compresion_structural_need_redesign",
                "answer": "probably_if_current_context_is_required",
                "evidence": "The label still depends on pivot stability and late confirmation; parameter grid did not solve both.",
                "classification": "technical_redesign_candidate",
            },
            {
                "question": "is_late_context_methodologically_usable",
                "answer": "yes_with_warnings",
                "evidence": "Noise is reduced enough for contextual/manual study, but not for fresh dashboard state.",
                "classification": "acceptable_limitation",
            },
            {
                "question": "what_is_the_main_project_risk",
                "answer": "blocking_enbolsa_platform_with_wavecount_live",
                "evidence": "ENBOLSA/SQL/dashboard path is more central to the TFG; WaveCount live has no edge evidence.",
                "classification": "roadmap_risk",
            },
        ]
    )


def build_continuation_options(metrics: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "option_id": "A",
                "option_name": "redesign_pivot_compression_before_sql",
                "description": "Redesign causal pivot persistence, compression and wave maturation before any WaveCount SQL staging.",
                "benefit": "Only path that could eventually support fresh current_context.",
                "cost": "High; touches core experimental logic and may still fail because Elliott live is inherently unstable.",
                "risk": "Over-engineering and delaying ENBOLSA dashboard.",
                "recommended_now": False,
            },
            {
                "option_id": "B",
                "option_name": "wavecount_live_late_context_only",
                "description": "Accept WaveCount live as confirmed-late/manual context, never current operational state.",
                "benefit": "Preserves useful structural reading without pretending it is fresh.",
                "cost": "Limited immediate dashboard value; needs warning semantics.",
                "risk": "Could confuse users if displayed without late/manual labels.",
                "recommended_now": False,
            },
            {
                "option_id": "C",
                "option_name": "park_wavecount_live_and_advance_enbolsa_platform",
                "description": "Stop investing in WaveCount live for now and advance SQL/dashboard around ENBOLSA/RiskGuard.",
                "benefit": "Protects the main empirical TFG path.",
                "cost": "WaveCount live remains a documented future/research line.",
                "risk": "Loses near-term structural visual context.",
                "recommended_now": False,
            },
            {
                "option_id": "D",
                "option_name": "hybrid_late_context_plus_enbolsa_platform",
                "description": "Freeze current_context attempts, keep WaveCount as late/manual/research, and advance ENBOLSA platform.",
                "benefit": "Best balance: does not waste prior WaveCount work and does not block the platform.",
                "cost": "Requires discipline in dashboard wording and SQL boundaries.",
                "risk": "Future scope creep if late context is promoted without new evidence.",
                "recommended_now": True,
            },
        ]
    )


def build_recommendation_matrix(metrics: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "criterion": "protect_main_tfg_axis",
                "redesign_now": "medium",
                "late_context_only": "high",
                "park": "high",
                "hybrid": "high",
                "winner": "hybrid",
            },
            {
                "criterion": "avoid_false_current_context",
                "redesign_now": "medium",
                "late_context_only": "high",
                "park": "high",
                "hybrid": "high",
                "winner": "late_context_or_hybrid",
            },
            {
                "criterion": "reuse_existing_work",
                "redesign_now": "medium",
                "late_context_only": "high",
                "park": "low",
                "hybrid": "high",
                "winner": "hybrid",
            },
            {
                "criterion": "implementation_risk_now",
                "redesign_now": "high",
                "late_context_only": "low",
                "park": "low",
                "hybrid": "low",
                "winner": "hybrid",
            },
            {
                "criterion": "recommendation",
                "redesign_now": "not_recommended_before_dashboard",
                "late_context_only": "valid_but_too_narrow",
                "park": "safe_but_loses_context",
                "hybrid": "recommended",
                "winner": "hybrid_late_context_plus_enbolsa_platform",
            },
        ]
    )


def build_redesign_path() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "phase": "wavecount_live_pivot_compression_redesign_v0",
                "step": "define_persistent_pivots",
                "purpose": "Separate raw pivots from persistent structural pivots and avoid full reclassification at each cut.",
                "code_to_review": "trading_center/wavecount_live_ohlc.py; backtests/wavecount/wavecount_pivots.py; backtests/wavecount/wavecount_structure.py",
                "stop_condition": "If instability remains above 25% after a bounded review, keep late/manual only.",
            },
            {
                "phase": "wavecount_live_pivot_compression_redesign_v0",
                "step": "event_based_maturation",
                "purpose": "Model forming/current/confirmed_late separately instead of promoting by pivot count alone.",
                "code_to_review": "trading_center/wavecount_live_context.py",
                "stop_condition": "If completed_impulse_candidate remains dominant, stop current_context attempt.",
            },
            {
                "phase": "wavecount_live_pivot_compression_redesign_v0",
                "step": "append_only_fixture_tests",
                "purpose": "Prove older hypotheses are not overwritten and can be reconstructed by as_of_bar_time.",
                "code_to_review": "new tests only; no SQL real",
                "stop_condition": "No SQL staging until no-overwrite tests pass.",
            },
            {
                "phase": "wavecount_live_pivot_compression_redesign_v0",
                "step": "bounded_real_ohlc_review",
                "purpose": "Run a small non-operative review; no PnL and no strategy metrics.",
                "code_to_review": "backtests/tfg review scripts",
                "stop_condition": "Do not allow the redesign to delay ENBOLSA dashboard indefinitely.",
            },
        ]
    )


def build_late_context_path(metrics: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "field_or_policy": "context_mode",
                "value": "late_wave_context",
                "description": "WaveCount live is shown only as delayed structural context.",
            },
            {
                "field_or_policy": "context_freshness_status",
                "value": "late",
                "description": f"Because best lag remains {metrics['late_confirmation_pct']:.1%} late-confirmed.",
            },
            {
                "field_or_policy": "display_policy",
                "value": "show_with_warning_or_manual_review_only",
                "description": "Dashboard can show warnings later, but not as fresh current context.",
            },
            {
                "field_or_policy": "bot_policy",
                "value": "read_context_only",
                "description": "Bot cannot accept/reject or size trades with WaveCount.",
            },
            {
                "field_or_policy": "statistics_policy",
                "value": "study_variable_only",
                "description": "May be joined by as_of_bar_time for research, never as optimized filter.",
            },
        ]
    )


def build_park_wavecount_path() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "park_item": "wavecount_live_current_context",
                "status": "parked_until_redesign_or_manual_review",
                "reopen_condition": "A bounded redesign proposal is accepted, or dashboard needs a manual/research WaveCount tab.",
            },
            {
                "park_item": "wavecount_methodological_block",
                "status": "closed",
                "reopen_condition": "Only for documentation corrections; not for edge claims.",
            },
            {
                "park_item": "enbolsa_platform",
                "status": "continue",
                "reopen_condition": "Next phase should focus on SQL/dashboard around existing live_context_snapshot.",
            },
        ]
    )


def build_roadmap_implications(recommendation: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "area": "ENBOLSA",
                "implication": "remains_primary_path",
                "next_action": "Continue toward dashboard/read-only platform from SQL/live_context_snapshot.",
            },
            {
                "area": "WaveCount live",
                "implication": recommendation,
                "next_action": "Do not attempt current_context in platform v1; reserve late/manual/research lane.",
            },
            {
                "area": "SQL",
                "implication": "do_not_stage_wavecount_live_current_context",
                "next_action": "Keep operational SQL focused on stable snapshot and ENBOLSA/RiskGuard.",
            },
            {
                "area": "Dashboard",
                "implication": "can_exist_without_fresh_wavecount",
                "next_action": "Design dashboard so WaveCount live is optional/contextual, not a blocker.",
            },
            {
                "area": "Telegram/Bot",
                "implication": "wavecount_not_actionable",
                "next_action": "No WaveCount alerts or bot decisions in v0.",
            },
        ]
    )


def build_do_not_do_yet() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"item": "redesign_engine_immediately", "reason": "Needs explicit bounded phase; do not mix with roadmap decision."},
            {"item": "wavecount_sql_staging_current_context", "reason": "No current_context candidate exists."},
            {"item": "dashboard_wavecount_current_state", "reason": "Would overstate late/unstable hypotheses."},
            {"item": "telegram_wavecount_signals", "reason": "Would look like operational signal generation."},
            {"item": "bot_uses_wavecount", "reason": "WaveCount remains read-only context."},
            {"item": "backtest_or_optimize_wavecount", "reason": "This phase is not edge validation."},
            {"item": "mt5_connection", "reason": "MT5 remains blocked."},
        ]
    )


def build_open_decisions(source: dict[str, pd.DataFrame], recommendation: str) -> pd.DataFrame:
    rows = [
        {
            "decision_id": "accept_hybrid_recommendation",
            "question": "Confirm whether WaveCount live should stop blocking ENBOLSA SQL/dashboard.",
            "recommended_answer": recommendation,
            "needed_before": "dashboard_design",
        },
        {
            "decision_id": "late_context_visibility",
            "question": "Should late WaveCount appear in dashboard v1 or stay hidden until a manual/research tab exists?",
            "recommended_answer": "hide_from_main_v1_or_show_with_warning_only",
            "needed_before": "dashboard_wavecount_tab",
        },
        {
            "decision_id": "redesign_budget",
            "question": "How much more time should be spent on pivot compression before platform work resumes?",
            "recommended_answer": "bounded_future_phase_only",
            "needed_before": "wavecount_redesign",
        },
    ]
    append_open = source.get("append_only_open_decisions", pd.DataFrame())
    if not append_open.empty:
        for record in append_open.head(5).to_dict(orient="records"):
            rows.append(
                {
                    "decision_id": str(record.get("decision_id", "append_only_open_decision")),
                    "question": str(record.get("question", "")),
                    "recommended_answer": "defer_until_wavecount_staging",
                    "needed_before": "wavecount_sql_staging",
                }
            )
    return pd.DataFrame(rows)


def build_run_meta(
    generated_at: str,
    config: WaveCountLiveNextDecisionConfig,
    metrics: dict[str, Any],
    recommendation: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_next_decision",
        "recommendation": recommendation,
        "source_dirs": {
            "lag_resolution_dir": str(config.lag_resolution_dir),
            "append_only_dir": str(config.append_only_dir),
            "visual_audit_dir": str(config.visual_audit_dir),
        },
        "key_metrics": metrics,
        "safety": {
            "real_sql_executed": False,
            "ddl_executed": False,
            "mt5_connected": False,
            "backtests_executed": False,
            "signals_generated": False,
            "dashboard_implemented": False,
            "telegram_implemented": False,
            "bot_implemented": False,
        },
        "limitations": [
            "Documentary decision only; no motor changes.",
            "No edge, PnL or strategy validation is claimed.",
            "WaveCount live remains non-operative and cannot filter ENBOLSA.",
        ],
    }


def write_outputs(
    *,
    config: WaveCountLiveNextDecisionConfig,
    strategic_diagnosis: pd.DataFrame,
    continuation_options: pd.DataFrame,
    recommendation_matrix: pd.DataFrame,
    redesign_path_if_needed: pd.DataFrame,
    late_context_path: pd.DataFrame,
    park_wavecount_path: pd.DataFrame,
    roadmap_implications: pd.DataFrame,
    do_not_do_yet: pd.DataFrame,
    open_decisions: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    tables_dir = config.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "strategic_diagnosis": tables_dir / "strategic_diagnosis.csv",
        "continuation_options": tables_dir / "continuation_options.csv",
        "recommendation_matrix": tables_dir / "recommendation_matrix.csv",
        "redesign_path_if_needed": tables_dir / "redesign_path_if_needed.csv",
        "late_context_path": tables_dir / "late_context_path.csv",
        "park_wavecount_path": tables_dir / "park_wavecount_path.csv",
        "roadmap_implications": tables_dir / "roadmap_implications.csv",
        "do_not_do_yet": tables_dir / "do_not_do_yet.csv",
        "open_decisions": tables_dir / "open_decisions.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    strategic_diagnosis.to_csv(paths["strategic_diagnosis"], index=False)
    continuation_options.to_csv(paths["continuation_options"], index=False)
    recommendation_matrix.to_csv(paths["recommendation_matrix"], index=False)
    redesign_path_if_needed.to_csv(paths["redesign_path_if_needed"], index=False)
    late_context_path.to_csv(paths["late_context_path"], index=False)
    park_wavecount_path.to_csv(paths["park_wavecount_path"], index=False)
    roadmap_implications.to_csv(paths["roadmap_implications"], index=False)
    do_not_do_yet.to_csv(paths["do_not_do_yet"], index=False)
    open_decisions.to_csv(paths["open_decisions"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    *,
    config: WaveCountLiveNextDecisionConfig,
    strategic_diagnosis: pd.DataFrame,
    continuation_options: pd.DataFrame,
    recommendation_matrix: pd.DataFrame,
    redesign_path_if_needed: pd.DataFrame,
    late_context_path: pd.DataFrame,
    park_wavecount_path: pd.DataFrame,
    roadmap_implications: pd.DataFrame,
    open_decisions: pd.DataFrame,
    recommendation: str,
) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    doc = f"""# WaveCount Live Next Decision

Fecha: 2026-05-27

## Recomendacion

Recomendacion: `{recommendation}`.

La decision prudente es no seguir intentando que `wavecount_live_context_v0`
entre como `current_context` antes del dashboard. WaveCount live conserva valor
como contexto tardio/manual/de estudio, pero no debe bloquear la plataforma
ENBOLSA + RiskGuard + SQL snapshot.

Esta fase no cambia motor, no crea DDL, no escribe SQL real, no ejecuta
backtests, no genera senales, no toca dashboard/Telegram/bot y no conecta MT5.

## Diagnostico Estrategico

{markdown_table(strategic_diagnosis)}

## Opciones Evaluadas

{markdown_table(continuation_options)}

## Matriz De Recomendacion

{markdown_table(recommendation_matrix)}

## Si Se Redisenara Mas Adelante

{markdown_table(redesign_path_if_needed)}

## Camino Late/Manual Context

{markdown_table(late_context_path)}

## Camino De Aparcar Temporalmente

{markdown_table(park_wavecount_path)}

## Impacto En Roadmap

{markdown_table(roadmap_implications)}

## Decisiones Abiertas

{markdown_table(open_decisions)}

## Cierre

- Los parametros no han bastado para `current_context`.
- Redisenar pivotes puede tener sentido, pero no antes de desbloquear la
  plataforma ENBOLSA si el objetivo es avanzar el TFG.
- WaveCount live queda como contexto tardio/manual/research, no como senal.
- Dashboard/SQL deben poder avanzar sin WaveCount live fresco.
- Cualquier reintento de current context debe ser una fase acotada, con stop
  condition y sin mezclarlo con implementacion de dashboard.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_NEXT_DECISION.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build WaveCount live next-decision design artifacts.")
    parser.add_argument("--lag-resolution-dir", type=Path, default=DEFAULT_LAG_RESOLUTION_DIR)
    parser.add_argument("--append-only-dir", type=Path, default=DEFAULT_APPEND_ONLY_DIR)
    parser.add_argument("--visual-audit-dir", type=Path, default=DEFAULT_VISUAL_AUDIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_wavecount_live_next_decision(
        WaveCountLiveNextDecisionConfig(
            lag_resolution_dir=args.lag_resolution_dir,
            append_only_dir=args.append_only_dir,
            visual_audit_dir=args.visual_audit_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        )
    )
    print(
        json.dumps(
            {
                "recommendation": result.recommendation,
                "output_dir": str(args.output_dir),
                "real_sql_executed": False,
                "backtests_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
