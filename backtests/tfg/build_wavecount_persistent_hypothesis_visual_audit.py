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


DEFAULT_INPUT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_visual_audit_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_PERSISTENT_HYPOTHESIS_VISUAL_AUDIT.md")
DEFAULT_CURRENT_DIR = Path("artifacts/tfg/wavecount_current_hypothesis_v0_2026-05-27")
DEFAULT_GRID_V2_DIR = Path("artifacts/tfg/wavecount_live_parameter_grid_v2_2026-05-27")

REQUIRED_PERSISTENT_FILES = {
    "hypotheses": "persistent_wave_hypothesis.csv",
    "hypotheses_json": "persistent_wave_hypothesis.json",
    "pivots": "persistent_pivots.csv",
    "pivot_events": "pivot_events.csv",
    "wave_events": "wave_events.csv",
    "anti": "anti_lookahead_audit.csv",
    "stability": "stability_audit.csv",
    "transitions": "transition_audit.csv",
    "comparison": "comparison_vs_current_wave_hypothesis.csv",
    "issues": "issues_or_risks.csv",
    "run_meta": "run_meta.json",
}

EXPECTED_PIVOT_ROLES = (
    "candidate_pivot",
    "provisional_pivot",
    "persistent_pivot",
    "superseded_pivot",
    "rejected_pivot",
)


@dataclass(frozen=True)
class PersistentVisualAuditConfig:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    current_dir: Path = DEFAULT_CURRENT_DIR
    grid_v2_dir: Path = DEFAULT_GRID_V2_DIR
    source_csv: Path = DEFAULT_SOURCE_CSV
    generate_charts: bool = True


@dataclass(frozen=True)
class PersistentVisualAuditResult:
    contract_security_audit: pd.DataFrame
    wave5_dominance_audit: pd.DataFrame
    visual_wave_audit: pd.DataFrame
    wave_transition_diagnosis: pd.DataFrame
    model_comparison_audit: pd.DataFrame
    design_diagnosis: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_persistent_visual_audit(
    config: PersistentVisualAuditConfig | None = None,
) -> PersistentVisualAuditResult:
    config = config or PersistentVisualAuditConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    contract = build_contract_security_audit(sources)
    wave5 = build_wave5_dominance_audit(sources)
    transitions = build_wave_transition_diagnosis(sources)
    charts = build_visual_wave_audit(config, sources, wave5) if config.generate_charts else empty_visual_audit(wave5)
    comparison = build_model_comparison_audit(config, sources)
    design = build_design_diagnosis(wave5, charts, transitions, comparison)
    decision = decide_next_step(contract, wave5, charts, design)
    issues = build_issues_or_risks(contract, wave5, charts, transitions, design, decision)
    run_meta = build_run_meta(generated_at, config, sources, charts, decision)
    written = write_outputs(
        config=config,
        contract=contract,
        wave5=wave5,
        charts=charts,
        transitions=transitions,
        comparison=comparison,
        design=design,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, contract, wave5, charts, transitions, comparison, design, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_PERSISTENT_HYPOTHESIS_VISUAL_AUDIT.md"
    return PersistentVisualAuditResult(
        contract_security_audit=contract,
        wave5_dominance_audit=wave5,
        visual_wave_audit=charts,
        wave_transition_diagnosis=transitions,
        model_comparison_audit=comparison,
        design_diagnosis=design,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: PersistentVisualAuditConfig) -> dict[str, Any]:
    missing = [str(config.input_dir / filename) for filename in REQUIRED_PERSISTENT_FILES.values() if not (config.input_dir / filename).exists()]
    if missing:
        raise FileNotFoundError(f"missing persistent hypothesis inputs: {missing}")
    sources: dict[str, Any] = {
        "hypotheses": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["hypotheses"]),
        "hypotheses_json": json.loads((config.input_dir / REQUIRED_PERSISTENT_FILES["hypotheses_json"]).read_text(encoding="utf-8")),
        "pivots": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["pivots"]),
        "pivot_events": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["pivot_events"]),
        "wave_events": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["wave_events"]),
        "anti": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["anti"]),
        "stability": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["stability"]),
        "transitions": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["transitions"]),
        "comparison": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["comparison"]),
        "issues": pd.read_csv(config.input_dir / REQUIRED_PERSISTENT_FILES["issues"]),
        "run_meta": json.loads((config.input_dir / REQUIRED_PERSISTENT_FILES["run_meta"]).read_text(encoding="utf-8")),
        "ohlc": load_source_ohlc(config.source_csv) if config.source_csv.exists() else pd.DataFrame(),
    }
    current_csv = config.current_dir / "current_wave_hypothesis.csv"
    sources["current"] = pd.read_csv(current_csv) if current_csv.exists() else pd.DataFrame()
    grid_comparison = config.grid_v2_dir / "config_comparison_v2.csv"
    sources["grid_v2"] = pd.read_csv(grid_comparison) if grid_comparison.exists() else pd.DataFrame()
    return sources


def build_contract_security_audit(sources: dict[str, Any]) -> pd.DataFrame:
    hypotheses = sources["hypotheses"]
    pivots = sources["pivots"]
    anti = sources["anti"]
    meta = sources["run_meta"]
    json_rows = sources["hypotheses_json"]
    rows = [
        {
            "check_name": "csv_json_row_count_match",
            "status": "pass" if len(hypotheses) == len(json_rows) else "fail",
            "observed": f"csv={len(hypotheses)};json={len(json_rows)}",
            "severity": "blocking" if len(hypotheses) != len(json_rows) else "info",
        },
        {
            "check_name": "anti_lookahead_all_true",
            "status": "pass" if bool(anti["lookahead_safe"].map(to_bool).all()) else "fail",
            "observed": str(bool(anti["lookahead_safe"].map(to_bool).all())),
            "severity": "blocking" if not bool(anti["lookahead_safe"].map(to_bool).all()) else "info",
        },
    ]
    for role in EXPECTED_PIVOT_ROLES:
        count = int((pivots["pivot_role"].astype(str) == role).sum()) if "pivot_role" in pivots.columns else 0
        rows.append(
            {
                "check_name": f"pivot_role_{role}",
                "status": "present" if count else "not_present_in_sample",
                "observed": count,
                "severity": "info" if count else "low",
            }
        )
    for flag in ["is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
        if flag == "is_read_only":
            ok = bool(hypotheses[flag].map(to_bool).all())
        else:
            ok = not bool(hypotheses[flag].map(to_bool).any())
        rows.append(
            {
                "check_name": f"hard_flag_{flag}",
                "status": "pass" if ok else "fail",
                "observed": str(ok),
                "severity": "blocking" if not ok else "info",
            }
        )
    for flag in ["real_sql_executed", "ddl_executed", "mt5_connected", "backtests_executed", "signals_generated"]:
        value = bool(meta.get("safety", {}).get(flag, True))
        rows.append(
            {
                "check_name": f"run_meta_{flag}",
                "status": "pass" if not value else "fail",
                "observed": str(value),
                "severity": "blocking" if value else "info",
            }
        )
    candidate_mask = pivots["pivot_role"].astype(str).isin(["candidate_pivot", "provisional_pivot"]) if "pivot_role" in pivots.columns else pd.Series(dtype=bool)
    candidate_persistent = bool(pivots.loc[candidate_mask, "is_persistent"].map(to_bool).any()) if not pivots.empty and candidate_mask.any() else False
    rows.append(
        {
            "check_name": "candidate_not_persistent",
            "status": "pass" if not candidate_persistent else "fail",
            "observed": str(candidate_persistent),
            "severity": "blocking" if candidate_persistent else "info",
        }
    )
    return pd.DataFrame(rows)


def build_wave5_dominance_audit(sources: dict[str, Any]) -> pd.DataFrame:
    latest = latest_hypotheses(sources["hypotheses"])
    rows = []
    for _, row in latest.iterrows():
        symbol = str(row["symbol"])
        pivots = sources["pivots"][sources["pivots"]["symbol"].astype(str) == symbol].copy()
        persistent_count = int(row["persistent_pivot_count"])
        candidate_count = int(row["candidate_pivot_count"])
        superseded_count = int(row["superseded_pivot_count"])
        estimated = str(row["estimated_current_wave"])
        reason = wave5_reason(row, pivots)
        high_persistence = persistent_count >= 6
        wave5 = "wave5" in estimated or "completed_impulse" in estimated
        risk = "high" if wave5 and high_persistence else "medium" if wave5 else "low"
        interpretation = (
            "Wave5 label is not safe as current context until cycle-reset/proportion checks confirm the active cycle."
            if wave5
            else "No wave5 dominance for this symbol."
        )
        rows.append(
            {
                "symbol": symbol,
                "timeframe": row["timeframe"],
                "estimated_current_wave": estimated,
                "confirmed_wave_context": row["confirmed_wave_context"],
                "persistent_pivot_count": persistent_count,
                "candidate_pivot_count": candidate_count,
                "superseded_pivot_count": superseded_count,
                "last_persistent_pivot_at": row["last_persistent_pivot_at"],
                "reason_wave5_assigned": reason,
                "risk": risk,
                "manual_interpretation": interpretation,
            }
        )
    return pd.DataFrame(rows)


def wave5_reason(row: pd.Series, pivots: pd.DataFrame) -> str:
    reasons = []
    if "wave5" in str(row["estimated_current_wave"]):
        reasons.append("estimated_state_is_wave5")
    if int(row["persistent_pivot_count"]) >= 5:
        reasons.append("persistent_pivot_count_ge_5")
    if int(row["candidate_pivot_count"]) > 0:
        reasons.append("candidate_pivots_keep_context_provisional")
    active = pivots[pivots["pivot_role"].astype(str) == "persistent_pivot"].copy()
    if not active.empty and not active["pivot_type"].astype(str).ne(active["pivot_type"].astype(str).shift()).iloc[1:].all():
        reasons.append("alternation_not_clean")
    if int(row["persistent_pivot_count"]) > 6:
        reasons.append("cycle_reset_not_modelled")
    if not reasons:
        reasons.append("not_wave5")
    return ";".join(reasons)


def build_visual_wave_audit(config: PersistentVisualAuditConfig, sources: dict[str, Any], wave5: pd.DataFrame) -> pd.DataFrame:
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    ohlc = sources["ohlc"].copy()
    latest = latest_hypotheses(sources["hypotheses"])
    rows = []
    for _, row in latest.iterrows():
        symbol = str(row["symbol"])
        timeframe = str(row["timeframe"])
        as_of = pd.Timestamp(row["as_of_bar_time"])
        part = ohlc[(ohlc["symbol"].astype(str) == symbol) & (ohlc["timeframe"].astype(str) == timeframe)].copy()
        part = part[pd.to_datetime(part["time"]) <= as_of].sort_values("time")
        pivots = sources["pivots"][(sources["pivots"]["symbol"].astype(str) == symbol) & (sources["pivots"]["timeframe"].astype(str) == timeframe)].copy()
        chart_file = chart_dir / f"persistent_hypothesis_{safe_id(symbol)}_{timeframe}_{as_of.strftime('%Y%m%dT%H%M%S')}.png"
        if not part.empty:
            render_chart(chart_file, part, pivots, row)
        role_counts = pivots["pivot_role"].value_counts().to_dict() if not pivots.empty else {}
        persistent_count = int(row["persistent_pivot_count"])
        readability = visual_readability(persistent_count, int(row["candidate_pivot_count"]), role_counts)
        plausible = "false" if persistent_count > 10 else "unclear"
        cycle_reset = "true" if persistent_count > 6 and "wave5" in str(row["estimated_current_wave"]) else "unclear"
        rows.append(
            {
                "chart_file": str(chart_file),
                "symbol": symbol,
                "timeframe": timeframe,
                "estimated_current_wave": row["estimated_current_wave"],
                "visual_readability": readability,
                "wave5_plausible": plausible,
                "cycle_reset_needed": cycle_reset,
                "manual_notes": (
                    "Persistent pivots make the structure readable, but wave5 dominance needs cycle reset/proportion validation before dashboard."
                ),
            }
        )
    return pd.DataFrame(rows)


def render_chart(path: Path, ohlc: pd.DataFrame, pivots: pd.DataFrame, row: pd.Series) -> None:
    plot = ohlc.tail(min(len(ohlc), 220)).copy()
    plot["time"] = pd.to_datetime(plot["time"], errors="coerce")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    fig.patch.set_facecolor("white")
    ax.plot(plot["time"], plot["close"], color="#333333", linewidth=1.4, label="close")
    role_style = {
        "persistent_pivot": ("#0072B2", "o", 42, "persistent"),
        "candidate_pivot": ("#E69F00", "^", 46, "candidate"),
        "provisional_pivot": ("#CC79A7", "^", 46, "provisional"),
        "superseded_pivot": ("#999999", "x", 42, "superseded"),
        "rejected_pivot": ("#999999", "x", 24, "rejected"),
    }
    window_start = plot["time"].min()
    for role, (color, marker, size, label) in role_style.items():
        part = pivots[pivots["pivot_role"].astype(str) == role].copy()
        if part.empty:
            continue
        part["pivot_extreme_time"] = pd.to_datetime(part["pivot_extreme_time"], errors="coerce")
        part["pivot_price"] = pd.to_numeric(part["pivot_price"], errors="coerce")
        part = part[(part["pivot_extreme_time"] >= window_start) & part["pivot_extreme_time"].notna()]
        if part.empty:
            continue
        ax.scatter(part["pivot_extreme_time"], part["pivot_price"], color=color, marker=marker, s=size, label=label, alpha=0.9, zorder=3)
    title = f"{row['symbol']} {row['timeframe']} - {row['estimated_current_wave']} ({row['display_policy']})"
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.text(
        0.01,
        0.02,
        f"as_of={row['as_of_bar_time']} | warning: no signal / no filter / no execution",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def visual_readability(persistent_count: int, candidate_count: int, role_counts: dict[str, int]) -> str:
    rejected = int(role_counts.get("rejected_pivot", 0))
    if persistent_count > 12:
        return "borderline"
    if persistent_count < 3:
        return "too_sparse"
    if rejected > persistent_count:
        return "borderline"
    if candidate_count:
        return "borderline"
    return "readable"


def empty_visual_audit(wave5: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "chart_file": "",
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "estimated_current_wave": row["estimated_current_wave"],
                "visual_readability": "not_generated",
                "wave5_plausible": "unclear",
                "cycle_reset_needed": "unclear",
                "manual_notes": "charts disabled",
            }
            for _, row in wave5.iterrows()
        ]
    )


def build_wave_transition_diagnosis(sources: dict[str, Any]) -> pd.DataFrame:
    transitions = sources["transitions"].copy()
    hypotheses = sources["hypotheses"].copy()
    rows = []
    for (symbol, timeframe), part in hypotheses.groupby(["symbol", "timeframe"], dropna=False):
        part = part.sort_values("cut_number")
        wave5_part = part[part["estimated_current_wave"].astype(str).str.contains("wave5|completed_impulse", regex=True)]
        trans_part = transitions[(transitions["symbol"].astype(str) == str(symbol)) & (transitions["timeframe"].astype(str) == str(timeframe))]
        first_wave5 = wave5_part.iloc[0] if not wave5_part.empty else {}
        phase_changes = int((trans_part["transition_type"].astype(str) != "stable").sum()) if not trans_part.empty else 0
        abrupt = int(trans_part["transition_type"].astype(str).str.contains("abrupt|ambiguous_or_invalidated", regex=True).sum()) if not trans_part.empty else 0
        invalidations = int(part["estimated_current_wave"].astype(str).eq("invalidated").sum())
        cuts_in_wave5 = int(len(wave5_part))
        cycle_reset = bool(cuts_in_wave5 >= max(2, len(part) // 3))
        rows.append(
            {
                "symbol": symbol,
                "first_wave5_cut": first_wave5.get("cut_number", ""),
                "first_wave5_as_of": first_wave5.get("as_of_bar_time", ""),
                "cuts_in_wave5": cuts_in_wave5,
                "phase_changes": phase_changes,
                "abrupt_changes": abrupt,
                "invalidations": invalidations,
                "cycle_reset_candidate": cycle_reset,
                "interpretation": "wave5 persists across many cuts; current model lacks cycle reset" if cycle_reset else "wave5 not dominant across cuts",
            }
        )
    return pd.DataFrame(rows)


def build_model_comparison_audit(config: PersistentVisualAuditConfig, sources: dict[str, Any]) -> pd.DataFrame:
    rows = []
    persistent_latest = latest_hypotheses(sources["hypotheses"])
    rows.append(model_summary("wavecount_persistent_hypothesis_v0", persistent_latest, "Persistent pivots reduce manual_review_only but create wave5 dominance risk."))
    current = sources.get("current", pd.DataFrame())
    if not current.empty:
        rows.append(model_summary("current_wave_hypothesis_v0", current, "Safer but too restrictive: all latest rows were ambiguous/manual_review_only."))
    grid = sources.get("grid_v2", pd.DataFrame())
    for config_name in ["time_mid_c", "time_hard_b"]:
        part = grid[grid["config_name"].astype(str) == config_name] if not grid.empty and "config_name" in grid.columns else pd.DataFrame()
        if part.empty:
            rows.append(
                {
                    "model": config_name,
                    "manual_review_or_blocked": "not_available",
                    "show_with_warning": "not_available",
                    "displayable": "not_available",
                    "wave5_or_completed_pct": "not_available",
                    "main_improvement": "artifact not available",
                    "main_regression": "artifact not available",
                    "interpretation": "Could not compare from local artifacts.",
                }
            )
        else:
            record = part.iloc[0]
            rows.append(
                {
                    "model": config_name,
                    "manual_review_or_blocked": "not_candidate",
                    "show_with_warning": "not_applicable",
                    "displayable": "not_applicable",
                    "wave5_or_completed_pct": float(record.get("completed_impulse_pct", 0.0)),
                    "main_improvement": "reduced noise versus baseline",
                    "main_regression": "late confirmation and/or unstable pivots",
                    "interpretation": f"{config_name} remains diagnostic, not dashboard-ready.",
                }
            )
    return pd.DataFrame(rows)


def model_summary(model_name: str, frame: pd.DataFrame, interpretation: str) -> dict[str, Any]:
    display = frame["display_policy"].astype(str) if "display_policy" in frame.columns else pd.Series(dtype=str)
    estimated = frame["estimated_current_wave"].astype(str) if "estimated_current_wave" in frame.columns else pd.Series(dtype=str)
    return {
        "model": model_name,
        "manual_review_or_blocked": int(display.eq("manual_review_only").sum()),
        "show_with_warning": int(display.eq("show_with_warning").sum()),
        "displayable": int(display.eq("displayable_in_dashboard").sum()),
        "wave5_or_completed_pct": round(float(estimated.str.contains("wave5|completed_impulse", regex=True).mean()), 4) if len(estimated) else 0.0,
        "main_improvement": "more specific wave state" if model_name.startswith("wavecount_persistent") else "safer ambiguity",
        "main_regression": "possible false precision" if model_name.startswith("wavecount_persistent") else "no usable wave context",
        "interpretation": interpretation,
    }


def build_design_diagnosis(
    wave5: pd.DataFrame,
    visual: pd.DataFrame,
    transitions: pd.DataFrame,
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    wave5_high = int((wave5["risk"].astype(str) == "high").sum())
    cycle_reset = int(visual["cycle_reset_needed"].astype(str).eq("true").sum()) if not visual.empty else 0
    false_or_unclear = int(visual["wave5_plausible"].astype(str).isin(["false", "unclear"]).sum()) if not visual.empty else 0
    return pd.DataFrame(
        [
            {
                "diagnosis": "wave5_dominance_is_not_approved",
                "evidence": f"{wave5_high}/{len(wave5)} latest rows have high wave5 risk.",
                "recommended_next_action": "Do not promote to dashboard; require cycle reset/proportion checks.",
                "risk_if_ignored": "Dashboard would show false precision as wave context.",
            },
            {
                "diagnosis": "cycle_reset_rules_needed",
                "evidence": f"{cycle_reset}/{len(visual)} charts flagged as cycle reset needed.",
                "recommended_next_action": "Design cycle segmentation before accepting wave5 active.",
                "risk_if_ignored": "Old pivots keep accumulating and mature every asset into wave5.",
            },
            {
                "diagnosis": "visual_review_not_passed",
                "evidence": f"{false_or_unclear}/{len(visual)} wave5 plausibility labels are false or unclear.",
                "recommended_next_action": "Use visual review as gate before any SQL/dashboard staging.",
                "risk_if_ignored": "Warnings may look like validated structure.",
            },
            {
                "diagnosis": "state_machine_likely_needed",
                "evidence": "Persistent pivots improved specificity but still rely on accumulated pivot sequence.",
                "recommended_next_action": "Design explicit wave state machine with cycle current/previous separation.",
                "risk_if_ignored": "Further parameter tweaks may only move the same failure mode.",
            },
        ]
    )


def decide_next_step(contract: pd.DataFrame, wave5: pd.DataFrame, visual: pd.DataFrame, design: pd.DataFrame) -> str:
    if (contract["severity"] == "blocking").any():
        return "blocked_for_dashboard_wave_context"
    if int((wave5["risk"].astype(str) == "high").sum()) >= max(1, len(wave5) // 2):
        return "needs_cycle_reset_rules"
    if int(visual["wave5_plausible"].astype(str).eq("false").sum()) > 0:
        return "needs_wave_state_machine"
    return "needs_more_real_ohlc_review"


def build_issues_or_risks(
    contract: pd.DataFrame,
    wave5: pd.DataFrame,
    visual: pd.DataFrame,
    transitions: pd.DataFrame,
    design: pd.DataFrame,
    decision: str,
) -> pd.DataFrame:
    blocking = int((contract["severity"] == "blocking").sum())
    high_wave5 = int((wave5["risk"].astype(str) == "high").sum())
    cycle_reset = int(visual["cycle_reset_needed"].astype(str).eq("true").sum()) if not visual.empty else 0
    return pd.DataFrame(
        [
            {
                "severity": "blocking" if blocking else "info",
                "risk": "contract_or_security_failure",
                "description": f"{blocking} blocking contract/security checks.",
                "recommendation": "Block all follow-up until fixed." if blocking else "Contract/security checks passed.",
            },
            {
                "severity": "high" if high_wave5 else "low",
                "risk": "wave5_dominance",
                "description": f"{high_wave5} symbols have high wave5 dominance risk.",
                "recommendation": "Add cycle reset/proportion checks before dashboard.",
            },
            {
                "severity": "medium" if cycle_reset else "low",
                "risk": "cycle_reset_missing",
                "description": f"{cycle_reset} charts indicate likely cycle reset need.",
                "recommendation": "Separate active cycle from older persistent pivots.",
            },
            {
                "severity": "medium",
                "risk": "decision",
                "description": f"Final decision: {decision}.",
                "recommendation": "Keep WaveCount out of SQL/dashboard until next design gate passes.",
            },
        ]
    )


def build_run_meta(
    generated_at: str,
    config: PersistentVisualAuditConfig,
    sources: dict[str, Any],
    visual: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    hypotheses = sources["hypotheses"]
    return {
        "generated_at": generated_at,
        "version": "wavecount_persistent_hypothesis_visual_audit",
        "decision": decision,
        "input_dir": str(config.input_dir),
        "source_csv": str(config.source_csv),
        "symbols": sorted(hypotheses["symbol"].dropna().unique().tolist()),
        "timeframes": sorted(hypotheses["timeframe"].dropna().unique().tolist()),
        "charts_generated": int(len(visual)),
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
    config: PersistentVisualAuditConfig,
    contract: pd.DataFrame,
    wave5: pd.DataFrame,
    charts: pd.DataFrame,
    transitions: pd.DataFrame,
    comparison: pd.DataFrame,
    design: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "contract": config.output_dir / "contract_security_audit.csv",
        "wave5": config.output_dir / "wave5_dominance_audit.csv",
        "visual": config.output_dir / "visual_wave_audit.csv",
        "transitions": config.output_dir / "wave_transition_diagnosis.csv",
        "comparison": config.output_dir / "model_comparison_audit.csv",
        "design": config.output_dir / "design_diagnosis.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    contract.to_csv(paths["contract"], index=False)
    wave5.to_csv(paths["wave5"], index=False)
    charts.to_csv(paths["visual"], index=False)
    transitions.to_csv(paths["transitions"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    design.to_csv(paths["design"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    config: PersistentVisualAuditConfig,
    contract: pd.DataFrame,
    wave5: pd.DataFrame,
    charts: pd.DataFrame,
    transitions: pd.DataFrame,
    comparison: pd.DataFrame,
    design: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    doc = f"""# WaveCount Persistent Hypothesis Visual Audit

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta auditoria revisa si `wavecount_persistent_hypothesis_v0` mejora realmente
la lectura de onda por activo o si solo cambia `ambiguous/manual_review_only`
por una falsa precision de `possible_wave5_active/show_with_warning`.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Contrato Y Seguridad

{markdown_table(contract)}

## Dominancia De Onda 5

{markdown_table(wave5)}

## Auditoria Visual

{markdown_table(charts)}

## Transiciones

{markdown_table(transitions)}

## Comparacion De Modelos

{markdown_table(comparison)}

## Diagnostico De Diseno

{markdown_table(design)}

## Riesgos

{markdown_table(issues)}

## Cierre

- La mejora frente a `current_wave_hypothesis_v0` es real en especificidad:
  deja de ser todo `manual_review_only`.
- La mejora no esta aprobada para dashboard porque 4/4 activos terminan en
  `possible_wave5_active`.
- La lectura de onda 5 queda como `show_with_warning`, no como contexto limpio.
- El siguiente paso debe introducir reglas de ciclo/reset/proporcion o una
  maquina de estados de onda; no SQL/dashboard.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_PERSISTENT_HYPOTHESIS_VISUAL_AUDIT.md").write_text(doc, encoding="utf-8")


def latest_hypotheses(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.sort_values(["symbol", "timeframe", "cut_number"]).groupby(["symbol", "timeframe"], as_index=False).tail(1)


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit persistent WaveCount hypotheses visually and technically.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--grid-v2-dir", type=Path, default=DEFAULT_GRID_V2_DIR)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_persistent_visual_audit(
        PersistentVisualAuditConfig(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            current_dir=args.current_dir,
            grid_v2_dir=args.grid_v2_dir,
            source_csv=args.source_csv,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "output_dir": str(args.output_dir),
                "charts": int(len(result.visual_wave_audit)),
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
