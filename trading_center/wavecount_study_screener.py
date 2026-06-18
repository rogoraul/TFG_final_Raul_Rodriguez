from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table, safe_id
from trading_center.wavecount_current_hypothesis import to_bool, validate_payload


DEFAULT_LIVE_ESTIMATE_DIR = Path("artifacts/tfg/wavecount_live_estimate_v0_2026-05-27")
DEFAULT_VISUAL_AUDIT_DIR = Path("artifacts/tfg/wavecount_live_estimate_visual_audit_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_study_screener_v0_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_STUDY_SCREENER_V0.md")

SCREENER_COLUMNS = [
    "screener_id",
    "generated_at",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "as_of_bar_time",
    "source",
    "screener_bucket",
    "screener_rank",
    "screener_score",
    "live_estimated_wave",
    "confirmed_wave_context",
    "structure_family",
    "direction",
    "current_leg_status",
    "confidence_bucket",
    "freshness_status",
    "display_policy",
    "visual_readability",
    "label_plausible",
    "latest_close",
    "activation_level",
    "invalidation_level",
    "distance_to_activation_pct",
    "distance_to_invalidation_pct",
    "display_badge",
    "required_warning",
    "recommended_study_action",
    "show_in_study_screener",
    "show_in_main_dashboard",
    "why_in_screener",
    "why_not_signal",
    "is_read_only",
    "study_only",
    "telegram_allowed",
    "bot_allowed",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
    "method_version",
    "payload_json",
]


@dataclass(frozen=True)
class StudyScreenerConfig:
    live_estimate_dir: Path = DEFAULT_LIVE_ESTIMATE_DIR
    visual_audit_dir: Path = DEFAULT_VISUAL_AUDIT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH


@dataclass(frozen=True)
class StudyScreenerResult:
    screener: pd.DataFrame
    scoring_audit: pd.DataFrame
    display_contract: pd.DataFrame
    screener_sections: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_study_screener(config: StudyScreenerConfig | None = None) -> StudyScreenerResult:
    config = config or StudyScreenerConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    rows: list[dict[str, Any]] = []
    scoring_rows: list[dict[str, Any]] = []

    for _, row in sources["estimate"].iterrows():
        visual = matching_visual_row(sources["visual"], row)
        screener_row, scoring_row = build_screener_row(generated_at, row, visual)
        rows.append(screener_row)
        scoring_rows.append(scoring_row)

    screener = normalize_screener(pd.DataFrame(rows))
    scoring = pd.DataFrame(scoring_rows)
    display_contract = build_display_contract()
    sections = build_screener_sections(screener)
    decision = decide_next_step(screener)
    issues = build_issues_or_risks(screener, sources)
    run_meta = build_run_meta(generated_at, config, screener, decision)
    written = write_outputs(config, screener, scoring, display_contract, sections, issues, run_meta)
    write_docs(config, screener, scoring, display_contract, sections, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_STUDY_SCREENER_V0.md"
    return StudyScreenerResult(
        screener=screener,
        scoring_audit=scoring,
        display_contract=display_contract,
        screener_sections=sections,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: StudyScreenerConfig) -> dict[str, Any]:
    required = {
        "estimate": config.live_estimate_dir / "live_wave_estimate.csv",
        "estimate_json": config.live_estimate_dir / "live_wave_estimate.json",
        "run_meta": config.live_estimate_dir / "run_meta.json",
        "visual": config.visual_audit_dir / "visual_live_estimate_audit.csv",
        "decision": config.visual_audit_dir / "decision_summary.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing study screener inputs: {missing}")
    return {
        "estimate": pd.read_csv(required["estimate"]),
        "estimate_json": json.loads(required["estimate_json"].read_text(encoding="utf-8")),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
        "visual": pd.read_csv(required["visual"]),
        "decision": pd.read_csv(required["decision"]),
    }


def matching_visual_row(visual: pd.DataFrame, row: pd.Series) -> pd.Series:
    match = visual[
        (visual["symbol"].astype(str) == str(row["symbol"]))
        & (visual["timeframe"].astype(str) == str(row["timeframe"]))
    ]
    return match.iloc[0] if not match.empty else pd.Series(dtype=object)


def build_screener_row(generated_at: str, row: pd.Series, visual: pd.Series) -> tuple[dict[str, Any], dict[str, Any]]:
    bucket, rank, score, badge, action, warning, why, why_not_signal = classify_for_screener(row, visual)
    symbol = str(row["symbol"])
    timeframe = str(row["timeframe"])
    payload = {
        "visual_readability": visual.get("visual_readability", "unknown"),
        "label_plausible": visual.get("label_plausible", "unknown"),
        "why_this_label": row.get("why_this_label", ""),
        "why_not_higher_confidence": row.get("why_not_higher_confidence", ""),
        "operational_use": "forbidden",
    }
    screener_row = {
        "screener_id": f"wavecount_study_screener_v0_{safe_id(symbol)}_{timeframe}_{pd.Timestamp(row['as_of_bar_time']).strftime('%Y%m%dT%H%M%S')}",
        "generated_at": generated_at,
        "symbol": symbol,
        "market_group": row.get("market_group", ""),
        "timeframe": timeframe,
        "higher_timeframe": row.get("higher_timeframe", ""),
        "as_of_bar_time": row.get("as_of_bar_time", ""),
        "source": "wavecount_study_screener_v0",
        "screener_bucket": bucket,
        "screener_rank": rank,
        "screener_score": score,
        "live_estimated_wave": row.get("live_estimated_wave", ""),
        "confirmed_wave_context": row.get("confirmed_wave_context", ""),
        "structure_family": row.get("structure_family", ""),
        "direction": row.get("direction", ""),
        "current_leg_status": row.get("current_leg_status", ""),
        "confidence_bucket": row.get("confidence_bucket", ""),
        "freshness_status": row.get("freshness_status", ""),
        "display_policy": row.get("display_policy", ""),
        "visual_readability": visual.get("visual_readability", "unknown"),
        "label_plausible": visual.get("label_plausible", "unknown"),
        "latest_close": row.get("latest_close", ""),
        "activation_level": row.get("activation_level", ""),
        "invalidation_level": row.get("invalidation_level", ""),
        "distance_to_activation_pct": row.get("distance_to_activation_pct", ""),
        "distance_to_invalidation_pct": row.get("distance_to_invalidation_pct", ""),
        "display_badge": badge,
        "required_warning": warning,
        "recommended_study_action": action,
        "show_in_study_screener": bucket in {"active_wave_study_candidate", "candidate_wave_watch", "invalidated_old_context"},
        "show_in_main_dashboard": False,
        "why_in_screener": why,
        "why_not_signal": why_not_signal,
        "is_read_only": True,
        "study_only": True,
        "telegram_allowed": False,
        "bot_allowed": False,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "method_version": "wavecount_study_screener_v0",
        "payload_json": json.dumps(payload, sort_keys=True, default=str),
    }
    scoring_row = {
        "symbol": symbol,
        "timeframe": timeframe,
        "live_estimated_wave": row.get("live_estimated_wave", ""),
        "screener_bucket": bucket,
        "screener_rank": rank,
        "screener_score": score,
        "confidence_bucket": row.get("confidence_bucket", ""),
        "visual_readability": visual.get("visual_readability", "unknown"),
        "label_plausible": visual.get("label_plausible", "unknown"),
        "display_policy": row.get("display_policy", ""),
        "score_reason": why,
    }
    return screener_row, scoring_row


def classify_for_screener(row: pd.Series, visual: pd.Series) -> tuple[str, int, int, str, str, str, str, str]:
    wave = str(row.get("live_estimated_wave", "not_available"))
    display_policy = str(row.get("display_policy", ""))
    confidence = str(row.get("confidence_bucket", "low"))
    label_plausible = str(visual.get("label_plausible", "unknown"))
    readability = str(visual.get("visual_readability", "unknown"))
    base_warning = "Study context only; not a signal, not a filter, not executable."
    why_not_signal = "WaveCount is informational; ENBOLSA/RiskGuard remain the operational path."

    if wave == "invalidated":
        return (
            "invalidated_old_context",
            70,
            20,
            "old context invalidated",
            "hide_from_live_candidates_but_keep_audit",
            "Old WaveCount context is invalidated; do not read as fresh bearish setup.",
            "Latest close invalidated a stale context; useful to explain why the asset is not a live wave candidate.",
            why_not_signal,
        )

    if display_policy == "show_live_estimate_with_warning" and "active" in wave and label_plausible == "true":
        score = 72 if confidence == "medium" else 62
        return (
            "active_wave_study_candidate",
            10,
            score,
            "active hypothesis",
            "open_chart_and_review_levels",
            f"{base_warning} Confirmed context is late; display only with warning.",
            "Live close supports the active/candidate distinction and visual audit marks the label plausible.",
            why_not_signal,
        )

    if display_policy == "show_live_estimate_with_warning" and "candidate" in wave:
        score = 48 if readability in {"borderline", "too_ambiguous"} or label_plausible != "true" else 58
        return (
            "candidate_wave_watch",
            20,
            score,
            "candidate watch",
            "watch_activation_and_review_chart",
            f"{base_warning} Activation is not confirmed; confidence remains low.",
            "The leg is visible enough for a watchlist-style study row, but not enough for active context.",
            why_not_signal,
        )

    if display_policy == "manual_review_only":
        return (
            "manual_review_only",
            80,
            10,
            "manual only",
            "manual_review_before_display",
            base_warning,
            "The visual or state context is not suitable for a screener candidate.",
            why_not_signal,
        )

    return (
        "not_displayable",
        90,
        0,
        "not displayable",
        "do_not_show",
        base_warning,
        "Insufficient context for study screener.",
        why_not_signal,
    )


def normalize_screener(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in SCREENER_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=SCREENER_COLUMNS)
    bool_columns = [
        "show_in_study_screener",
        "show_in_main_dashboard",
        "is_read_only",
        "study_only",
        "telegram_allowed",
        "bot_allowed",
        "can_generate_signal",
        "can_filter_trade",
        "can_execute_order",
    ]
    for column in bool_columns:
        normalized[column] = normalized[column].map(to_bool)
    normalized["is_read_only"] = True
    normalized["study_only"] = True
    normalized["show_in_main_dashboard"] = False
    normalized["telegram_allowed"] = False
    normalized["bot_allowed"] = False
    normalized["can_generate_signal"] = False
    normalized["can_filter_trade"] = False
    normalized["can_execute_order"] = False
    normalized["payload_json"] = normalized["payload_json"].map(validate_payload)
    validate_safety(normalized)
    return normalized.sort_values(["screener_rank", "screener_score", "symbol"], ascending=[True, False, True]).reset_index(drop=True)


def validate_safety(frame: pd.DataFrame) -> None:
    if not frame["is_read_only"].map(to_bool).all():
        raise ValueError("is_read_only=false is forbidden")
    if not frame["study_only"].map(to_bool).all():
        raise ValueError("study_only=false is forbidden")
    for column in ["show_in_main_dashboard", "telegram_allowed", "bot_allowed", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
        if frame[column].map(to_bool).any():
            raise ValueError(f"{column}=true is forbidden")


def build_display_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "screener_bucket": "active_wave_study_candidate",
                "meaning": "Most interesting study rows; active hypothesis but provisional and late-context-aware.",
                "main_dashboard_allowed": False,
                "telegram_allowed": False,
                "bot_allowed": False,
            },
            {
                "screener_bucket": "candidate_wave_watch",
                "meaning": "Watchlist-style study row; activation not confirmed or confidence low.",
                "main_dashboard_allowed": False,
                "telegram_allowed": False,
                "bot_allowed": False,
            },
            {
                "screener_bucket": "invalidated_old_context",
                "meaning": "Old context invalidated; useful for audit/exclusion, not a current bearish signal.",
                "main_dashboard_allowed": False,
                "telegram_allowed": False,
                "bot_allowed": False,
            },
            {
                "screener_bucket": "manual_review_only",
                "meaning": "Do not show as candidate; manual interpretation required.",
                "main_dashboard_allowed": False,
                "telegram_allowed": False,
                "bot_allowed": False,
            },
            {
                "screener_bucket": "not_displayable",
                "meaning": "No useful WaveCount study context.",
                "main_dashboard_allowed": False,
                "telegram_allowed": False,
                "bot_allowed": False,
            },
        ]
    )


def build_screener_sections(screener: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for bucket, label in [
        ("active_wave_study_candidate", "Prioridad de estudio"),
        ("candidate_wave_watch", "Watchlist de activacion"),
        ("invalidated_old_context", "Contextos descartados/invalidos"),
        ("manual_review_only", "Revision manual"),
        ("not_displayable", "Oculto"),
    ]:
        count = int((screener["screener_bucket"].astype(str) == bucket).sum())
        rows.append({"screener_bucket": bucket, "section_label": label, "row_count": count})
    return pd.DataFrame(rows)


def build_issues_or_risks(screener: pd.DataFrame, sources: dict[str, Any]) -> pd.DataFrame:
    active = int((screener["screener_bucket"].astype(str) == "active_wave_study_candidate").sum())
    candidate = int((screener["screener_bucket"].astype(str) == "candidate_wave_watch").sum())
    invalidated = int((screener["screener_bucket"].astype(str) == "invalidated_old_context").sum())
    decision = ""
    if not sources["decision"].empty and "decision" in sources["decision"].columns:
        decision = str(sources["decision"].iloc[0]["decision"])
    return pd.DataFrame(
        [
            {
                "severity": "info",
                "risk": "study_screener_only",
                "description": "The screener orders assets for human study, not trading action.",
                "recommendation": "Keep wording as study/context; never signal/filter/order.",
            },
            {
                "severity": "medium" if active or candidate else "low",
                "risk": "hypothesis_can_look_actionable",
                "description": f"{active + candidate} rows are visible wave candidates.",
                "recommendation": "Show warnings, levels and why_not_signal next to every row.",
            },
            {
                "severity": "medium" if invalidated else "low",
                "risk": "invalidated_context_wording",
                "description": f"{invalidated} rows are invalidated old contexts.",
                "recommendation": "Label as invalidated_old_context, not fresh bearish context.",
            },
            {
                "severity": "info",
                "risk": "upstream_visual_audit_decision",
                "description": f"Upstream visual audit decision: {decision}.",
                "recommendation": "Do not promote to SQL/dashboard main view before broader review.",
            },
        ]
    )


def decide_next_step(screener: pd.DataFrame) -> str:
    if screener[["telegram_allowed", "bot_allowed", "can_generate_signal", "can_filter_trade", "can_execute_order"]].map(to_bool).any().any():
        return "blocked_security_flags"
    visible = int(screener["show_in_study_screener"].map(to_bool).sum())
    active = int((screener["screener_bucket"].astype(str) == "active_wave_study_candidate").sum())
    candidate = int((screener["screener_bucket"].astype(str) == "candidate_wave_watch").sum())
    if visible and (active or candidate):
        return "study_screener_v0_ready_for_broader_review"
    if visible:
        return "study_screener_v0_audit_only"
    return "study_screener_v0_no_visible_candidates"


def build_run_meta(generated_at: str, config: StudyScreenerConfig, screener: pd.DataFrame, decision: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_study_screener_v0",
        "decision": decision,
        "source_live_estimate_dir": str(config.live_estimate_dir),
        "source_visual_audit_dir": str(config.visual_audit_dir),
        "symbols": sorted(screener["symbol"].dropna().astype(str).unique().tolist()),
        "timeframes": sorted(screener["timeframe"].dropna().astype(str).unique().tolist()),
        "screener_bucket_distribution": screener["screener_bucket"].value_counts().sort_index().to_dict(),
        "visible_study_rows": int(screener["show_in_study_screener"].map(to_bool).sum()),
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
    }


def write_outputs(
    config: StudyScreenerConfig,
    screener: pd.DataFrame,
    scoring: pd.DataFrame,
    display_contract: pd.DataFrame,
    sections: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": config.output_dir / "wavecount_study_screener.csv",
        "json": config.output_dir / "wavecount_study_screener.json",
        "scoring": config.output_dir / "screener_scoring_audit.csv",
        "display_contract": config.output_dir / "display_contract.csv",
        "sections": config.output_dir / "screener_sections.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    screener.to_csv(paths["csv"], index=False)
    paths["json"].write_text(json.dumps(screener.to_dict(orient="records"), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    scoring.to_csv(paths["scoring"], index=False)
    display_contract.to_csv(paths["display_contract"], index=False)
    sections.to_csv(paths["sections"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    config: StudyScreenerConfig,
    screener: pd.DataFrame,
    scoring: pd.DataFrame,
    display_contract: pd.DataFrame,
    sections: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    visible = screener[screener["show_in_study_screener"].map(to_bool)].copy()
    doc = f"""# WaveCount Study Screener v0

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta capa convierte `wavecount_live_estimate_v0` en un screener de estudio: una
lista ordenada de activos que merecen revision visual por contexto de onda. No
es una senal, no es un filtro, no alimenta bot ni Telegram y no toca SQL real.

## Screener Visible

{markdown_table(visible[["symbol", "timeframe", "screener_bucket", "screener_score", "live_estimated_wave", "display_badge", "recommended_study_action", "required_warning"]])}

## Screener Completo

{markdown_table(screener[["symbol", "timeframe", "screener_bucket", "screener_rank", "screener_score", "live_estimated_wave", "confirmed_wave_context", "show_in_study_screener"]])}

## Scoring

{markdown_table(scoring)}

## Secciones

{markdown_table(sections)}

## Contrato De Display

{markdown_table(display_contract)}

## Riesgos

{markdown_table(issues)}

## Lectura

- `active_wave_study_candidate` va arriba del screener, pero sigue siendo solo
  contexto para abrir grafico y revisar niveles.
- `candidate_wave_watch` sirve para vigilar activacion, no para actuar.
- `invalidated_old_context` explica por que un activo queda descartado del
  screener vivo; no es una senal contraria.
- Todo queda `study_only=true`, `telegram_allowed=false`, `bot_allowed=false`,
  `can_generate_signal=false`, `can_filter_trade=false` y
  `can_execute_order=false`.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_STUDY_SCREENER_V0.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a non-operative WaveCount study screener.")
    parser.add_argument("--live-estimate-dir", type=Path, default=DEFAULT_LIVE_ESTIMATE_DIR)
    parser.add_argument("--visual-audit-dir", type=Path, default=DEFAULT_VISUAL_AUDIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_study_screener(
        StudyScreenerConfig(
            live_estimate_dir=args.live_estimate_dir,
            visual_audit_dir=args.visual_audit_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "rows": int(len(result.screener)),
                "output_dir": str(args.output_dir),
                "real_sql_executed": False,
                "mt5_connected": False,
                "backtests_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
