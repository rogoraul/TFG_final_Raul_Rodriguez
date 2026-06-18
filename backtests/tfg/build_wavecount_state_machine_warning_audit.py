from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table, safe_id
from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import DEFAULT_SOURCE_CSV, load_source_ohlc
from trading_center.wavecount_current_hypothesis import to_bool


DEFAULT_STATE_MACHINE_DIR = Path("artifacts/tfg/wavecount_state_machine_v0_2026-05-27")
DEFAULT_PERSISTENT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_state_machine_warning_audit_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_STATE_MACHINE_WARNING_AUDIT.md")


@dataclass(frozen=True)
class WarningAuditConfig:
    state_machine_dir: Path = DEFAULT_STATE_MACHINE_DIR
    persistent_dir: Path = DEFAULT_PERSISTENT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_csv: Path = DEFAULT_SOURCE_CSV
    max_main_dashboard_lag_bars: int = 60
    max_study_panel_lag_bars: int = 240
    generate_charts: bool = True


@dataclass(frozen=True)
class WarningAuditResult:
    warning_case_audit: pd.DataFrame
    warning_visual_audit: pd.DataFrame
    freshness_gate_audit: pd.DataFrame
    dashboard_policy_decision: pd.DataFrame
    model_limitations: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_warning_audit(config: WarningAuditConfig | None = None) -> WarningAuditResult:
    config = config or WarningAuditConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    warning_cases = build_warning_case_audit(config, sources)
    freshness = build_freshness_gate_audit(config, warning_cases)
    visual = build_warning_visual_audit(config, sources, warning_cases, freshness) if config.generate_charts else empty_visual_audit(warning_cases, freshness)
    policy = build_dashboard_policy_decision(warning_cases, freshness, visual)
    limitations = build_model_limitations(warning_cases, freshness, visual, policy)
    issues = build_issues_or_risks(warning_cases, freshness, visual, policy)
    decision = decide_next_step(policy, issues)
    run_meta = build_run_meta(generated_at, config, sources, warning_cases, visual, decision)
    written = write_outputs(
        config=config,
        warning_cases=warning_cases,
        visual=visual,
        freshness=freshness,
        policy=policy,
        limitations=limitations,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, warning_cases, visual, freshness, policy, limitations, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_STATE_MACHINE_WARNING_AUDIT.md"
    return WarningAuditResult(
        warning_case_audit=warning_cases,
        warning_visual_audit=visual,
        freshness_gate_audit=freshness,
        dashboard_policy_decision=policy,
        model_limitations=limitations,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: WarningAuditConfig) -> dict[str, Any]:
    required = {
        "hypotheses": config.state_machine_dir / "wave_state_machine_hypothesis.csv",
        "transitions": config.state_machine_dir / "wave_state_transitions.csv",
        "guard": config.state_machine_dir / "state_guard_audit.csv",
        "freshness": config.state_machine_dir / "freshness_invalidation_audit.csv",
        "comparison": config.state_machine_dir / "comparison_vs_cycle_state.csv",
        "run_meta": config.state_machine_dir / "run_meta.json",
        "pivots": config.persistent_dir / "persistent_pivots.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing warning audit inputs: {missing}")
    return {
        "hypotheses": pd.read_csv(required["hypotheses"]),
        "transitions": pd.read_csv(required["transitions"]),
        "guard": pd.read_csv(required["guard"]),
        "freshness": pd.read_csv(required["freshness"]),
        "comparison": pd.read_csv(required["comparison"]),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
        "pivots": pd.read_csv(required["pivots"]),
        "ohlc": load_source_ohlc(config.source_csv) if config.source_csv.exists() else pd.DataFrame(),
    }


def build_warning_case_audit(config: WarningAuditConfig, sources: dict[str, Any]) -> pd.DataFrame:
    hypotheses = sources["hypotheses"]
    guard = sources["guard"]
    freshness = sources["freshness"]
    warnings = hypotheses[hypotheses["display_policy"].astype(str) == "show_with_warning"].copy()
    rows = []
    for _, row in warnings.iterrows():
        symbol = str(row["symbol"])
        guard_row = guard[(guard["symbol"].astype(str) == symbol) & (guard["timeframe"].astype(str) == str(row["timeframe"]))].iloc[0]
        fresh_row = freshness[(freshness["symbol"].astype(str) == symbol) & (freshness["timeframe"].astype(str) == str(row["timeframe"]))].iloc[0]
        payload = safe_payload(row.get("payload_json", "{}"))
        direction = str(payload.get("direction", "unknown"))
        latest_close = float(row["latest_close"])
        activation = float(row["activation_level"]) if str(row["activation_level"]) else None
        invalidation = float(row["invalidation_level"]) if str(row["invalidation_level"]) else None
        rows.append(
            {
                "symbol": symbol,
                "market_group": row["market_group"],
                "timeframe": row["timeframe"],
                "as_of_bar_time": row["as_of_bar_time"],
                "estimated_current_wave": row["estimated_current_wave"],
                "state_machine_state": row["state_machine_state"],
                "direction": direction,
                "latest_close": latest_close,
                "activation_level": activation,
                "invalidation_level": invalidation,
                "activation_margin_pct": activation_margin_pct(latest_close, activation, direction),
                "distance_to_invalidation_pct": row["distance_to_invalidation_pct"],
                "lag_h4_bars_since_last_cycle_pivot": float(fresh_row["lag_h4_bars_since_last_cycle_pivot"]),
                "context_freshness_status": fresh_row["context_freshness_status"],
                "cycle_start_valid": guard_row["cycle_start_valid"],
                "latest_close_confirms_active": guard_row["latest_close_confirms_active"],
                "invalidated": guard_row["invalidated"],
                "transition_blockers": row["transition_blockers"],
                "warning_reason": warning_reason(row, fresh_row, guard_row),
                "can_be_current_context": False,
                "can_be_study_context": can_be_study_context(config, fresh_row, guard_row),
                "telegram_allowed": False,
                "bot_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def safe_payload(value: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def activation_margin_pct(close: float, activation: float | None, direction: str) -> float | str:
    if activation is None or activation == 0:
        return ""
    if direction == "short":
        return round(((activation - close) / abs(activation)) * 100.0, 4)
    return round(((close - activation) / abs(activation)) * 100.0, 4)


def warning_reason(row: pd.Series, fresh_row: pd.Series, guard_row: pd.Series) -> str:
    reasons = []
    if str(fresh_row["context_freshness_status"]) == "late":
        reasons.append("late_cycle_context")
    if to_bool(guard_row["latest_close_confirms_active"]):
        reasons.append("latest_close_confirms_activation")
    else:
        reasons.append("latest_close_does_not_confirm_activation")
    return ";".join(reasons)


def can_be_study_context(config: WarningAuditConfig, fresh_row: pd.Series, guard_row: pd.Series) -> bool:
    lag = float(fresh_row["lag_h4_bars_since_last_cycle_pivot"])
    return bool(lag <= config.max_study_panel_lag_bars and to_bool(guard_row["cycle_start_valid"]) and not to_bool(guard_row["invalidated"]))


def build_freshness_gate_audit(config: WarningAuditConfig, warning_cases: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in warning_cases.iterrows():
        lag = float(row["lag_h4_bars_since_last_cycle_pivot"])
        if lag <= config.max_main_dashboard_lag_bars:
            gate = "main_dashboard_candidate"
        elif lag <= config.max_study_panel_lag_bars:
            gate = "study_panel_candidate"
        else:
            gate = "too_stale_for_display"
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "estimated_current_wave": row["estimated_current_wave"],
                "lag_h4_bars_since_last_cycle_pivot": lag,
                "max_main_dashboard_lag_bars": config.max_main_dashboard_lag_bars,
                "max_study_panel_lag_bars": config.max_study_panel_lag_bars,
                "freshness_gate": gate,
                "interpretation": freshness_interpretation(gate),
            }
        )
    return pd.DataFrame(rows)


def freshness_interpretation(gate: str) -> str:
    return {
        "main_dashboard_candidate": "Fresh enough for a future dashboard context column, still non-operational.",
        "study_panel_candidate": "Too late for main current-wave context; acceptable only in a study panel with warning.",
        "too_stale_for_display": "Too stale even for default study display; keep in audit artifacts/manual review.",
    }.get(gate, "Unknown freshness gate.")


def build_warning_visual_audit(
    config: WarningAuditConfig,
    sources: dict[str, Any],
    warning_cases: pd.DataFrame,
    freshness: pd.DataFrame,
) -> pd.DataFrame:
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, row in warning_cases.iterrows():
        chart_file = chart_dir / f"warning_case_{safe_id(str(row['symbol']))}_{row['timeframe']}.png"
        if not sources["ohlc"].empty:
            render_warning_chart(chart_file, sources, row)
        gate = freshness[freshness["symbol"].astype(str) == str(row["symbol"])].iloc[0]["freshness_gate"]
        rows.append(
            {
                "chart_file": str(chart_file),
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "estimated_current_wave": row["estimated_current_wave"],
                "visual_readability": visual_readability(row, gate),
                "activation_visually_supported": row["latest_close_confirms_active"],
                "invalidation_visually_clear": not to_bool(row["invalidated"]),
                "freshness_gate": gate,
                "display_recommendation": display_recommendation(row, gate),
                "manual_notes": visual_notes(row, gate),
            }
        )
    return pd.DataFrame(rows)


def render_warning_chart(path: Path, sources: dict[str, Any], row: pd.Series) -> None:
    symbol = str(row["symbol"])
    timeframe = str(row["timeframe"])
    as_of = pd.Timestamp(row["as_of_bar_time"])
    prices = sources["ohlc"][
        (sources["ohlc"]["symbol"].astype(str) == symbol) & (sources["ohlc"]["timeframe"].astype(str) == timeframe)
    ].copy()
    prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
    prices = prices[prices["time"] <= as_of].sort_values("time").tail(280)
    pivots = sources["pivots"][
        (sources["pivots"]["symbol"].astype(str) == symbol)
        & (sources["pivots"]["timeframe"].astype(str) == timeframe)
        & (sources["pivots"]["pivot_role"].astype(str) == "persistent_pivot")
    ].copy()
    pivots["pivot_extreme_time"] = pd.to_datetime(pivots["pivot_extreme_time"], errors="coerce")
    pivots["pivot_price"] = pd.to_numeric(pivots["pivot_price"], errors="coerce")
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.patch.set_facecolor("white")
    ax.plot(prices["time"], prices["close"], color="#333333", linewidth=1.3, label="close")
    if not pivots.empty:
        ax.scatter(pivots["pivot_extreme_time"], pivots["pivot_price"], color="#999999", s=28, label="persistent pivots", zorder=3)
    ax.axvline(as_of, color="#000000", linestyle=":", linewidth=1.0, label="as_of")
    ax.axvspan(pd.Timestamp(row["as_of_bar_time"]) - pd.Timedelta(hours=4 * float(row["lag_h4_bars_since_last_cycle_pivot"])), as_of, color="#E69F00", alpha=0.10, label="lag window")
    ax.axhline(float(row["activation_level"]), color="#0072B2", linestyle="--", linewidth=1.0, label="activation")
    ax.axhline(float(row["invalidation_level"]), color="#D55E00", linestyle="--", linewidth=1.0, label="invalidation")
    ax.scatter([as_of], [float(row["latest_close"])], color="#009988", s=52, label="latest close", zorder=4)
    ax.set_title(f"{symbol} {timeframe}: {row['estimated_current_wave']} ({row['warning_reason']})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.text(0.01, 0.02, "warning audit | read-only | no signal / no filter / no execution", transform=ax.transAxes, fontsize=8, color="#555555")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def visual_readability(row: pd.Series, gate: str) -> str:
    if gate == "too_stale_for_display":
        return "too_stale"
    if not to_bool(row["latest_close_confirms_active"]):
        return "borderline"
    return "late_but_readable"


def display_recommendation(row: pd.Series, gate: str) -> str:
    if gate == "main_dashboard_candidate":
        return "future_dashboard_with_warning"
    if gate == "study_panel_candidate":
        return "study_panel_only"
    return "manual_review_only"


def visual_notes(row: pd.Series, gate: str) -> str:
    notes = [freshness_interpretation(gate)]
    if to_bool(row["latest_close_confirms_active"]):
        notes.append("latest_close supports active/candidate distinction")
    else:
        notes.append("latest_close does not support active state")
    notes.append("never usable for bot, Telegram signal, or trade filter")
    return ";".join(notes)


def empty_visual_audit(warning_cases: pd.DataFrame, freshness: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in warning_cases.iterrows():
        gate = freshness[freshness["symbol"].astype(str) == str(row["symbol"])].iloc[0]["freshness_gate"]
        rows.append(
            {
                "chart_file": "",
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "estimated_current_wave": row["estimated_current_wave"],
                "visual_readability": "not_reviewed",
                "activation_visually_supported": row["latest_close_confirms_active"],
                "invalidation_visually_clear": not to_bool(row["invalidated"]),
                "freshness_gate": gate,
                "display_recommendation": display_recommendation(row, gate),
                "manual_notes": "Charts disabled.",
            }
        )
    return pd.DataFrame(rows)


def build_dashboard_policy_decision(
    warning_cases: pd.DataFrame,
    freshness: pd.DataFrame,
    visual: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for _, row in warning_cases.iterrows():
        gate = freshness[freshness["symbol"].astype(str) == str(row["symbol"])].iloc[0]["freshness_gate"]
        visual_row = visual[visual["symbol"].astype(str) == str(row["symbol"])].iloc[0]
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "estimated_current_wave": row["estimated_current_wave"],
                "main_dashboard_current_wave_allowed": False,
                "study_panel_allowed": gate == "study_panel_candidate",
                "manual_review_required": gate != "study_panel_candidate",
                "telegram_allowed": False,
                "bot_allowed": False,
                "sql_staging_allowed_now": False,
                "recommended_label": recommended_label(row, gate),
                "required_warning": required_warning(row, visual_row, gate),
            }
        )
    return pd.DataFrame(rows)


def recommended_label(row: pd.Series, gate: str) -> str:
    if gate == "study_panel_candidate":
        return f"late {row['estimated_current_wave']} (study only)"
    return "manual review only"


def required_warning(row: pd.Series, visual_row: pd.Series, gate: str) -> str:
    warning = [freshness_interpretation(gate)]
    if not to_bool(row["latest_close_confirms_active"]):
        warning.append("latest close does not confirm activation")
    warning.append("not a signal, not a filter, not executable")
    return ";".join(warning)


def build_model_limitations(
    warning_cases: pd.DataFrame,
    freshness: pd.DataFrame,
    visual: pd.DataFrame,
    policy: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "limitation": "late_context",
                "evidence": f"{int((freshness['freshness_gate'] != 'main_dashboard_candidate').sum())}/{len(freshness)} warning cases are too late for main dashboard current-wave display.",
                "impact": "WaveCount cannot yet be shown as fresh wave context.",
                "next_action": "Require fresher pivots or progressive state update before dashboard.",
            },
            {
                "limitation": "study_only",
                "evidence": f"{int(policy['study_panel_allowed'].map(to_bool).sum())}/{len(policy)} warning cases can be kept as study-panel context.",
                "impact": "Useful for manual inspection, not operation.",
                "next_action": "Design a study-only display contract if needed.",
            },
            {
                "limitation": "no_operational_consumers",
                "evidence": "telegram_allowed=false and bot_allowed=false for all cases.",
                "impact": "No trading automation can depend on WaveCount.",
                "next_action": "Keep ENBOLSA/RiskGuard path independent.",
            },
        ]
    )


def build_issues_or_risks(
    warning_cases: pd.DataFrame,
    freshness: pd.DataFrame,
    visual: pd.DataFrame,
    policy: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "severity": "high",
                "risk": "freshness_not_current",
                "description": f"{int((freshness['freshness_gate'] != 'main_dashboard_candidate').sum())} warning cases fail main dashboard freshness.",
                "recommendation": "Do not show as current wave.",
            },
            {
                "severity": "medium",
                "risk": "manual_interpretation_needed",
                "description": f"{int(policy['manual_review_required'].map(to_bool).sum())} warning cases still require manual review.",
                "recommendation": "Keep outside default dashboard if not study-panel eligible.",
            },
            {
                "severity": "info",
                "risk": "non_operational_guard",
                "description": "All warning cases keep Telegram and bot disabled.",
                "recommendation": "Preserve fail-closed policy.",
            },
        ]
    )


def decide_next_step(policy: pd.DataFrame, issues: pd.DataFrame) -> str:
    if policy.empty:
        return "no_warning_cases_to_review"
    study = int(policy["study_panel_allowed"].map(to_bool).sum())
    current = int(policy["main_dashboard_current_wave_allowed"].map(to_bool).sum())
    if current:
        return "warning_cases_ready_for_dashboard_context_review"
    if study:
        return "late_wave_context_study_panel_only"
    return "warning_cases_manual_review_only"


def build_run_meta(
    generated_at: str,
    config: WarningAuditConfig,
    sources: dict[str, Any],
    warning_cases: pd.DataFrame,
    visual: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_state_machine_warning_audit",
        "decision": decision,
        "state_machine_dir": str(config.state_machine_dir),
        "warning_cases": int(len(warning_cases)),
        "symbols": sorted(warning_cases["symbol"].dropna().astype(str).unique().tolist()) if not warning_cases.empty else [],
        "charts_reviewed": int(len(visual)),
        "visual_readability_distribution": visual["visual_readability"].value_counts().sort_index().to_dict() if not visual.empty else {},
        "display_recommendation_distribution": visual["display_recommendation"].value_counts().sort_index().to_dict() if not visual.empty else {},
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
    *,
    config: WarningAuditConfig,
    warning_cases: pd.DataFrame,
    visual: pd.DataFrame,
    freshness: pd.DataFrame,
    policy: pd.DataFrame,
    limitations: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "warning_cases": config.output_dir / "warning_case_audit.csv",
        "visual": config.output_dir / "warning_visual_audit.csv",
        "freshness": config.output_dir / "freshness_gate_audit.csv",
        "policy": config.output_dir / "dashboard_policy_decision.csv",
        "limitations": config.output_dir / "model_limitations.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    warning_cases.to_csv(paths["warning_cases"], index=False)
    visual.to_csv(paths["visual"], index=False)
    freshness.to_csv(paths["freshness"], index=False)
    policy.to_csv(paths["policy"], index=False)
    limitations.to_csv(paths["limitations"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    config: WarningAuditConfig,
    warning_cases: pd.DataFrame,
    visual: pd.DataFrame,
    freshness: pd.DataFrame,
    policy: pd.DataFrame,
    limitations: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    doc = f"""# WaveCount State Machine Warning Audit

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta auditoria revisa solo los casos que `wavecount_state_machine_v0` dejo como
`show_with_warning`. La pregunta es si pueden mostrarse como contexto de onda
por activo o si siguen siendo demasiado tardios/manuales.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Casos Warning

{markdown_table(warning_cases)}

## Frescura

{markdown_table(freshness)}

## Revision Visual

{markdown_table(visual)}

## Politica De Display

{markdown_table(policy)}

## Limitaciones

{markdown_table(limitations)}

## Riesgos

{markdown_table(issues)}

## Lectura

- Ningun caso queda aprobado para columna principal de `onda actual`.
- Los casos con lag moderadamente tolerable solo pueden ser `study_panel_only`.
- Telegram y bot siguen prohibidos.
- Si se quiere mostrar WaveCount en dashboard, la forma prudente es una zona de
  estudio/manual con warning fuerte, no un estado fresco operativo.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_STATE_MACHINE_WARNING_AUDIT.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit WaveCount state-machine warning cases.")
    parser.add_argument("--state-machine-dir", type=Path, default=DEFAULT_STATE_MACHINE_DIR)
    parser.add_argument("--persistent-dir", type=Path, default=DEFAULT_PERSISTENT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--max-main-dashboard-lag-bars", type=int, default=60)
    parser.add_argument("--max-study-panel-lag-bars", type=int, default=240)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_warning_audit(
        WarningAuditConfig(
            state_machine_dir=args.state_machine_dir,
            persistent_dir=args.persistent_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            source_csv=args.source_csv,
            max_main_dashboard_lag_bars=args.max_main_dashboard_lag_bars,
            max_study_panel_lag_bars=args.max_study_panel_lag_bars,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "warning_cases": int(len(result.warning_case_audit)),
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
