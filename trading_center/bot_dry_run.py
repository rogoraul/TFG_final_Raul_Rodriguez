from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


DEFAULT_SNAPSHOT_CSV = Path(
    "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv"
)
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/bot_dry_run_v1_2026-05-29")
DEFAULT_DOC_PATH = Path("docs/BOT_DRY_RUN_V1.md")

LEDGER_COLUMNS = [
    "dry_run_event_id",
    "generated_at",
    "snapshot_id",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "setup_id",
    "strategy",
    "signal_state",
    "side",
    "entry",
    "sl",
    "tp1",
    "tp2",
    "riskguard_status",
    "riskguard_reason",
    "dry_run_decision",
    "dry_run_reason",
    "would_create_order_intent",
    "would_send_to_mt5",
    "would_send_telegram_order",
    "can_execute_order",
    "is_simulation",
    "wavecount_context_summary",
    "source_artifacts",
    "payload_json",
]

DECISIONS = [
    "dry_run_no_action",
    "dry_run_blocked_by_config",
    "dry_run_blocked_by_data",
    "dry_run_blocked_by_riskguard",
    "dry_run_order_intent",
]

ACCEPTABLE_FRESHNESS = {
    "latest_closed_bar",
    "fresh",
    "current",
    "ok",
    "acceptable",
    "live_observed",
    "bootstrap_current",
}

ENTRY_READY_STATE = "entry_ready_new"


@dataclass(frozen=True)
class BotDryRunOptions:
    bot_enabled: bool = False
    mode: str = "off"
    max_intents: int = 0
    allowed_symbols: tuple[str, ...] = ()
    allowed_market_groups: tuple[str, ...] = ()
    allowed_timeframes: tuple[str, ...] = ()
    mt5_enabled: bool = False
    live_enabled: bool = False
    telegram_command_bot_enabled: bool = False
    fixture_mode: bool = False


@dataclass(frozen=True)
class BotDryRunConfig:
    snapshot_csv: Path = DEFAULT_SNAPSHOT_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_root: Path = Path(".")


@dataclass(frozen=True)
class BotDryRunResult:
    decision: str
    ledger_rows: list[dict[str, Any]]
    source_data_audit: list[dict[str, Any]]
    config_audit: list[dict[str, Any]]
    decision_rule_audit: list[dict[str, Any]]
    safety_flags_audit: list[dict[str, Any]]
    wavecount_non_filter_audit: list[dict[str, Any]]
    issues_or_risks: list[dict[str, Any]]
    run_meta: dict[str, Any]


def build_bot_dry_run(
    config: BotDryRunConfig | None = None,
    options: BotDryRunOptions | None = None,
) -> BotDryRunResult:
    config = config or BotDryRunConfig()
    options = options or BotDryRunOptions()
    generated_at = datetime.now().isoformat(timespec="seconds")
    snapshot_path = _resolve(config.source_root, config.snapshot_csv)
    output_dir = _resolve(config.source_root, config.output_dir)
    doc_path = _resolve(config.source_root, config.doc_path)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    frame = _read_snapshot_csv(snapshot_path)
    source_audit = build_source_data_audit(snapshot_path, frame)
    issues = build_initial_issues(snapshot_path, frame)
    ledger_rows = evaluate_snapshot(
        frame,
        options=options,
        generated_at=generated_at,
        source_artifacts=str(config.snapshot_csv),
    )
    config_audit = build_config_audit(options)
    decision_audit = build_decision_rule_audit(ledger_rows)
    safety_audit = build_safety_flags_audit(ledger_rows, options)
    wavecount_audit = build_wavecount_non_filter_audit(frame, ledger_rows)
    issues.extend(build_runtime_issues(frame, ledger_rows, options))
    decision = "bot_dry_run_v1_artifact_ledger_ready_for_review"
    run_meta = build_run_meta(generated_at, decision, frame, ledger_rows, options)

    _write_csv(output_dir / "dry_run_decision_ledger.csv", ledger_rows, LEDGER_COLUMNS)
    (output_dir / "dry_run_decision_ledger.json").write_text(
        json.dumps(ledger_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_csv(tables_dir / "source_data_audit.csv", source_audit)
    _write_csv(tables_dir / "config_audit.csv", config_audit)
    _write_csv(tables_dir / "decision_rule_audit.csv", decision_audit)
    _write_csv(tables_dir / "safety_flags_audit.csv", safety_audit)
    _write_csv(tables_dir / "wavecount_non_filter_audit.csv", wavecount_audit)
    _write_csv(tables_dir / "issues_or_risks.csv", issues)
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    artifact_doc = render_markdown(result_decision=decision, run_meta=run_meta, ledger_rows=ledger_rows, issues=issues)
    (output_dir / "BOT_DRY_RUN_V1.md").write_text(artifact_doc, encoding="utf-8")
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(artifact_doc, encoding="utf-8")

    return BotDryRunResult(
        decision=decision,
        ledger_rows=ledger_rows,
        source_data_audit=source_audit,
        config_audit=config_audit,
        decision_rule_audit=decision_audit,
        safety_flags_audit=safety_audit,
        wavecount_non_filter_audit=wavecount_audit,
        issues_or_risks=issues,
        run_meta=run_meta,
    )


def evaluate_snapshot(
    frame: pd.DataFrame,
    *,
    options: BotDryRunOptions,
    generated_at: str,
    source_artifacts: str,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    created_intents = 0
    for index, row in frame.fillna("").iterrows():
        row_dict = {str(key): value for key, value in row.to_dict().items()}
        decision, reason, checks, create_intent, created_intents = decide_row(
            row_dict,
            options=options,
            created_intents=created_intents,
        )
        payload = {
            "row_index": int(index),
            "checks": checks,
            "source_row": _jsonable_mapping(row_dict),
            "options": {
                "bot_enabled": options.bot_enabled,
                "mode": options.mode,
                "max_intents": options.max_intents,
                "allowed_symbols": list(options.allowed_symbols),
                "allowed_market_groups": list(options.allowed_market_groups),
                "allowed_timeframes": list(options.allowed_timeframes),
                "mt5_enabled": options.mt5_enabled,
                "live_enabled": options.live_enabled,
                "telegram_command_bot_enabled": options.telegram_command_bot_enabled,
                "fixture_mode": options.fixture_mode,
            },
            "safety_flags": {
                "would_send_to_mt5": False,
                "would_send_telegram_order": False,
                "can_execute_order": False,
                "is_simulation": True,
                "wavecount_used_as_filter": False,
            },
        }
        ledger = {
            "dry_run_event_id": dry_run_event_id(row_dict, index),
            "generated_at": generated_at,
            "snapshot_id": _text(row_dict.get("snapshot_id"), "not_available"),
            "symbol": _text(row_dict.get("symbol"), "not_available"),
            "market_group": _text(row_dict.get("market_group"), "not_available"),
            "timeframe": _text(row_dict.get("timeframe_ltf") or row_dict.get("timeframe"), "not_available"),
            "higher_timeframe": _text(row_dict.get("timeframe_htf") or row_dict.get("higher_timeframe"), "not_available"),
            "setup_id": _text(row_dict.get("setup_id"), "not_available"),
            "strategy": _text(row_dict.get("strategy"), "enbolsa:macd_breakout"),
            "signal_state": _text(row_dict.get("signal_state"), "no_signal"),
            "side": _text(row_dict.get("side"), "not_available"),
            "entry": _number_or_empty(row_dict.get("entry")),
            "sl": _number_or_empty(row_dict.get("sl")),
            "tp1": _number_or_empty(row_dict.get("tp1")),
            "tp2": _number_or_empty(row_dict.get("tp2")),
            "riskguard_status": _text(row_dict.get("riskguard_status"), "not_evaluated"),
            "riskguard_reason": _text(row_dict.get("riskguard_reason"), "not_available"),
            "dry_run_decision": decision,
            "dry_run_reason": reason,
            "would_create_order_intent": create_intent,
            "would_send_to_mt5": False,
            "would_send_telegram_order": False,
            "can_execute_order": False,
            "is_simulation": True,
            "wavecount_context_summary": wavecount_summary(row_dict),
            "source_artifacts": source_artifacts,
            "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        }
        rows.append(ledger)
    return rows


def decide_row(
    row: Mapping[str, Any],
    *,
    options: BotDryRunOptions,
    created_intents: int,
) -> tuple[str, str, dict[str, Any], bool, int]:
    checks: dict[str, Any] = {
        "config_pass": False,
        "signal_state_pass": False,
        "freshness_pass": False,
        "riskguard_pass": False,
        "filters_pass": False,
        "max_intents_pass": False,
        "wavecount_used_as_filter": False,
    }
    config_reason = config_block_reason(options)
    if config_reason:
        return "dry_run_blocked_by_config", config_reason, checks, False, created_intents
    checks["config_pass"] = True

    signal_state = _text(row.get("signal_state"), "no_signal")
    if signal_state != ENTRY_READY_STATE:
        return "dry_run_no_action", f"{signal_state}_not_entry_ready", checks, False, created_intents
    checks["signal_state_pass"] = True

    filter_reason = row_filter_block_reason(row, options)
    if filter_reason:
        return "dry_run_blocked_by_config", filter_reason, checks, False, created_intents
    checks["filters_pass"] = True

    data_reason = data_block_reason(row)
    if data_reason:
        return "dry_run_blocked_by_data", data_reason, checks, False, created_intents
    checks["freshness_pass"] = True

    riskguard_status = _text(row.get("riskguard_status"), "not_evaluated")
    if riskguard_status != "riskguard_accepted":
        return "dry_run_blocked_by_riskguard", f"riskguard_status={riskguard_status}", checks, False, created_intents
    checks["riskguard_pass"] = True

    if options.max_intents <= 0:
        return "dry_run_blocked_by_config", "max_intents_zero", checks, False, created_intents
    if created_intents >= options.max_intents:
        return "dry_run_blocked_by_config", "max_intents_exceeded", checks, False, created_intents
    checks["max_intents_pass"] = True
    return "dry_run_order_intent", "riskguard_accepted_dry_run_simulation_only", checks, True, created_intents + 1


def config_block_reason(options: BotDryRunOptions) -> str:
    if not options.bot_enabled:
        return "bot_enabled_false"
    if options.mode != "dry_run":
        return f"mode_not_dry_run:{options.mode}"
    if options.mt5_enabled:
        return "mt5_enabled_true"
    if options.live_enabled:
        return "live_enabled_true"
    if options.telegram_command_bot_enabled:
        return "telegram_command_bot_enabled_true"
    return ""


def row_filter_block_reason(row: Mapping[str, Any], options: BotDryRunOptions) -> str:
    symbol = _text(row.get("symbol"))
    group = _text(row.get("market_group"))
    timeframe = _text(row.get("timeframe_ltf") or row.get("timeframe"))
    if options.allowed_symbols and symbol not in options.allowed_symbols:
        return f"symbol_not_allowed:{symbol}"
    if options.allowed_market_groups and group not in options.allowed_market_groups:
        return f"market_group_not_allowed:{group}"
    if options.allowed_timeframes and timeframe not in options.allowed_timeframes:
        return f"timeframe_not_allowed:{timeframe}"
    return ""


def data_block_reason(row: Mapping[str, Any]) -> str:
    freshness = _text(row.get("data_freshness_status")).lower()
    if freshness not in ACCEPTABLE_FRESHNESS:
        return f"freshness_not_acceptable:{freshness or 'missing'}"
    missing = [field for field in ("entry", "sl", "tp1", "tp2") if not _is_number(row.get(field))]
    if missing:
        return "missing_or_invalid_levels:" + ",".join(missing)
    return ""


def build_source_data_audit(snapshot_path: Path, frame: pd.DataFrame) -> list[dict[str, Any]]:
    signal_counts = _count_by(frame, "signal_state")
    riskguard_counts = _count_by(frame, "riskguard_status")
    return [
        {
            "source_id": "snapshot_csv",
            "path": str(snapshot_path),
            "exists": snapshot_path.exists(),
            "rows": int(len(frame)),
            "signal_state_distribution": json.dumps(signal_counts, sort_keys=True),
            "riskguard_distribution": json.dumps(riskguard_counts, sort_keys=True),
            "read_mode": "artifact_csv_read_only",
            "sql_real_written": False,
        }
    ]


def build_config_audit(options: BotDryRunOptions) -> list[dict[str, Any]]:
    values = {
        "bot_enabled": options.bot_enabled,
        "mode": options.mode,
        "max_intents": options.max_intents,
        "allowed_symbols": "|".join(options.allowed_symbols) or "all",
        "allowed_market_groups": "|".join(options.allowed_market_groups) or "all",
        "allowed_timeframes": "|".join(options.allowed_timeframes) or "all",
        "mt5_enabled": options.mt5_enabled,
        "live_enabled": options.live_enabled,
        "telegram_command_bot_enabled": options.telegram_command_bot_enabled,
        "fixture_mode": options.fixture_mode,
    }
    return [
        {
            "config_field": key,
            "value": value,
            "fail_closed_default": key in {"bot_enabled", "mode", "max_intents", "mt5_enabled", "live_enabled"},
            "notes": "CLI/in-memory config only; no SQL write and no secret file.",
        }
        for key, value in values.items()
    ]


def build_decision_rule_audit(ledger_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = {decision: 0 for decision in DECISIONS}
    for row in ledger_rows:
        counts[_text(row.get("dry_run_decision"))] = counts.get(_text(row.get("dry_run_decision")), 0) + 1
    return [
        {
            "decision": decision,
            "rows": count,
            "rule_summary": rule_summary(decision),
        }
        for decision, count in counts.items()
    ]


def build_safety_flags_audit(
    ledger_rows: Sequence[Mapping[str, Any]],
    options: BotDryRunOptions,
) -> list[dict[str, Any]]:
    any_can_execute = any(_to_bool(row.get("can_execute_order")) for row in ledger_rows)
    any_mt5 = any(_to_bool(row.get("would_send_to_mt5")) for row in ledger_rows)
    any_telegram_order = any(_to_bool(row.get("would_send_telegram_order")) for row in ledger_rows)
    all_simulation = all(_to_bool(row.get("is_simulation")) for row in ledger_rows) if ledger_rows else True
    checks = [
        ("can_execute_order_any_true", any_can_execute, False),
        ("would_send_to_mt5_any_true", any_mt5, False),
        ("would_send_telegram_order_any_true", any_telegram_order, False),
        ("is_simulation_all_true", all_simulation, True),
        ("mt5_enabled_option", options.mt5_enabled, False),
        ("live_enabled_option", options.live_enabled, False),
        ("telegram_command_bot_enabled_option", options.telegram_command_bot_enabled, False),
        ("sql_real_written", False, False),
        ("signals_generated", False, False),
        ("backtests_executed", False, False),
        ("wavecount_used_as_filter", False, False),
    ]
    return [
        {
            "check_name": name,
            "value": value,
            "expected": expected,
            "status": "passed" if value == expected else "failed",
        }
        for name, value, expected in checks
    ]


def build_wavecount_non_filter_audit(
    frame: pd.DataFrame,
    ledger_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, ledger in enumerate(ledger_rows):
        source_row = frame.iloc[index].to_dict() if index < len(frame) else {}
        rows.append(
            {
                "dry_run_event_id": ledger.get("dry_run_event_id", ""),
                "symbol": ledger.get("symbol", ""),
                "wavecount_available": _to_bool(source_row.get("wavecount_available")),
                "wavecount_context_status": _text(source_row.get("wavecount_context_status"), "not_available"),
                "wavecount_should_filter_trade": False,
                "decision_uses_wavecount": False,
                "dry_run_decision": ledger.get("dry_run_decision", ""),
                "audit_status": "passed",
            }
        )
    if not rows:
        rows.append(
            {
                "dry_run_event_id": "not_applicable",
                "symbol": "not_applicable",
                "wavecount_available": False,
                "wavecount_context_status": "not_available",
                "wavecount_should_filter_trade": False,
                "decision_uses_wavecount": False,
                "dry_run_decision": "empty_snapshot",
                "audit_status": "passed",
            }
        )
    return rows


def build_initial_issues(snapshot_path: Path, frame: pd.DataFrame) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not snapshot_path.exists():
        issues.append(
            {
                "issue_id": "snapshot_missing",
                "severity": "high",
                "status": "documented",
                "description": "Snapshot CSV was not found; no dry-run rows were evaluated.",
            }
        )
    if frame.empty:
        issues.append(
            {
                "issue_id": "snapshot_empty",
                "severity": "medium",
                "status": "documented",
                "description": "Snapshot is empty; generated empty ledger without side effects.",
            }
        )
    return issues


def build_runtime_issues(
    frame: pd.DataFrame,
    ledger_rows: Sequence[Mapping[str, Any]],
    options: BotDryRunOptions,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    signal_counts = _count_by(frame, "signal_state")
    if signal_counts and set(signal_counts) == {"watching_setup"}:
        issues.append(
            {
                "issue_id": "current_snapshot_watch_only",
                "severity": "info",
                "status": "expected",
                "description": "Current real snapshot has only watching_setup rows; no simulated order intent should be created.",
            }
        )
    if not options.fixture_mode and any(row["dry_run_decision"] == "dry_run_order_intent" for row in ledger_rows):
        issues.append(
            {
                "issue_id": "real_snapshot_created_simulated_intent",
                "severity": "warning",
                "status": "review_required",
                "description": "A non-fixture run created simulated intents; review source freshness and RiskGuard status.",
            }
        )
    if not options.bot_enabled:
        issues.append(
            {
                "issue_id": "bot_disabled_default",
                "severity": "info",
                "status": "expected",
                "description": "Default bot_enabled=false keeps the artifact run fail-closed.",
            }
        )
    return issues


def build_run_meta(
    generated_at: str,
    decision: str,
    frame: pd.DataFrame,
    ledger_rows: Sequence[Mapping[str, Any]],
    options: BotDryRunOptions,
) -> dict[str, Any]:
    decision_counts = _count_by(pd.DataFrame(ledger_rows), "dry_run_decision")
    return {
        "generated_at": generated_at,
        "decision": decision,
        "bot_dry_run_implemented": True,
        "bot_enabled": options.bot_enabled,
        "bot_mode": options.mode,
        "default_bot_enabled": False,
        "default_bot_mode": "off",
        "snapshot_rows": int(len(frame)),
        "ledger_rows": int(len(ledger_rows)),
        "decision_distribution": decision_counts,
        "simulated_intents": int(decision_counts.get("dry_run_order_intent", 0)),
        "mt5_connected": False,
        "mt5_orders_sent": 0,
        "telegram_connected": False,
        "telegram_orders_sent": 0,
        "telegram_command_bot_implemented": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "signals_generated": False,
        "backtests_executed": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": any(_to_bool(row.get("can_execute_order")) for row in ledger_rows),
        "would_send_to_mt5_any_true": any(_to_bool(row.get("would_send_to_mt5")) for row in ledger_rows),
        "would_send_telegram_order_any_true": any(_to_bool(row.get("would_send_telegram_order")) for row in ledger_rows),
        "artifact_first": True,
        "sql_runtime_ledger_implemented": False,
        "mt5_adapter_implemented": False,
        "dry_run_only": True,
    }


def render_markdown(
    *,
    result_decision: str,
    run_meta: Mapping[str, Any],
    ledger_rows: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
) -> str:
    decision_distribution = run_meta.get("decision_distribution", {})
    return f"""# Bot Dry-Run V1

Fecha: 2026-05-29

Decision: `{result_decision}`.

## Resumen

`bot_dry_run_v1` implementa un simulador artifact-first. Lee un snapshot CSV/export ya validado, evalua reglas de configuracion, datos y RiskGuard, y genera un ledger local con decisiones dry-run.

No conecta MT5, no envia ordenes, no conecta Telegram, no escribe SQL real, no crea DDL, no ejecuta backtests y no genera senales nuevas.

## Resultado Del Run Actual

- Snapshot rows: `{run_meta.get("snapshot_rows")}`
- Ledger rows: `{run_meta.get("ledger_rows")}`
- Distribucion de decisiones: `{json.dumps(decision_distribution, sort_keys=True)}`
- Simulated intents: `{run_meta.get("simulated_intents")}`
- `can_execute_order_any_true={str(run_meta.get("can_execute_order_any_true")).lower()}`
- `wavecount_used_as_filter={str(run_meta.get("wavecount_used_as_filter")).lower()}`

Con la configuracion por defecto, `bot_enabled=false` y `mode=off`, el sistema queda fail-closed. Si se habilita explicitamente `--bot-enabled --mode dry_run`, las filas `watching_setup` siguen siendo `dry_run_no_action`.

## Decisiones Soportadas

- `dry_run_blocked_by_config`: bot deshabilitado, modo incorrecto, MT5/live activado, filtros no permitidos o max intents superado.
- `dry_run_no_action`: contexto de vigilancia o sin `entry_ready_new`.
- `dry_run_blocked_by_data`: datos stale/missing o niveles invalidos en una fila `entry_ready_new`.
- `dry_run_blocked_by_riskguard`: fila `entry_ready_new` sin `riskguard_accepted`.
- `dry_run_order_intent`: simulacion permitida por config, datos frescos y RiskGuard aceptado.

## Ledger

El ledger se guarda en:

- `dry_run_decision_ledger.csv`
- `dry_run_decision_ledger.json`

Todos los registros mantienen:

- `can_execute_order=false`
- `would_send_to_mt5=false`
- `would_send_telegram_order=false`
- `is_simulation=true`

## WaveCount

WaveCount solo se copia como contexto informativo en `wavecount_context_summary`. No participa en filtros, RiskGuard, seleccion de filas ni decision final.

## Telegram Y MT5

Telegram command bot queda pendiente y no existe en esta fase. Telegram outbound podria consumir resumenes futuros, pero no recibe ordenes ni aprobaciones. MT5 sigue fuera de alcance: no hay adapter, conexion, cuenta ni broker.

## Riesgos Documentados

{_markdown_issue_list(issues)}

## Siguiente Paso

Revisar `bot_dry_run_v1` con foco en ledger, defaults fail-closed, fixtures positivos y separacion frente a MT5/Telegram/SQL runtime. No avanzar a SQL ledger runtime, Telegram command bot ni MT5 sin fases separadas.
"""


def dry_run_event_id(row: Mapping[str, Any], index: int) -> str:
    raw = "|".join(
        [
            _text(row.get("snapshot_id")),
            _text(row.get("symbol")),
            _text(row.get("strategy")),
            _text(row.get("timeframe_ltf") or row.get("timeframe")),
            _text(row.get("timeframe_htf") or row.get("higher_timeframe")),
            _text(row.get("side")),
            _text(row.get("setup_id")),
            str(index),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"dryrun_{digest}"


def wavecount_summary(row: Mapping[str, Any]) -> str:
    parts = []
    for field in ("wavecount_context_status", "wavecount_policy_bucket", "wavecount_notes"):
        value = _text(row.get(field))
        if value:
            parts.append(f"{field}={value}")
    return "; ".join(parts) if parts else "not_available"


def rule_summary(decision: str) -> str:
    return {
        "dry_run_no_action": "signal_state is not entry_ready_new",
        "dry_run_blocked_by_config": "bot config or allow-list blocks the row",
        "dry_run_blocked_by_data": "freshness or levels block an entry_ready_new row",
        "dry_run_blocked_by_riskguard": "RiskGuard is not riskguard_accepted",
        "dry_run_order_intent": "config, data and RiskGuard pass; simulation only",
    }.get(decision, "unknown")


def _read_snapshot_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _count_by(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    return {str(key): int(value) for key, value in frame[column].fillna("not_available").value_counts().to_dict().items()}


def _jsonable_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            result[str(key)] = None
        else:
            result[str(key)] = value.item() if hasattr(value, "item") else value
    return result


def _number_or_empty(value: Any) -> float | str:
    if not _is_number(value):
        return ""
    return float(value)


def _is_number(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "not_available", "null"}:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "si", "accepted"}


def _parse_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _markdown_issue_list(issues: Sequence[Mapping[str, Any]]) -> str:
    if not issues:
        return "- No issues registered."
    return "\n".join(
        f"- `{issue.get('issue_id')}` ({issue.get('severity')}): {issue.get('description')}"
        for issue in issues
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bot_dry_run_v1 artifact-first ledger.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Artifact-only mode; always true in v1.")
    parser.add_argument("--snapshot-csv", type=Path, default=DEFAULT_SNAPSHOT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--bot-enabled", action="store_true", default=False)
    parser.add_argument("--mode", default="off")
    parser.add_argument("--max-intents", type=int, default=0)
    parser.add_argument("--allow-symbols", default="")
    parser.add_argument("--allow-market-groups", default="")
    parser.add_argument("--allow-timeframes", default="")
    parser.add_argument("--fixture-mode", action="store_true", default=False)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    options = BotDryRunOptions(
        bot_enabled=bool(args.bot_enabled),
        mode=str(args.mode),
        max_intents=int(args.max_intents),
        allowed_symbols=_parse_list(args.allow_symbols),
        allowed_market_groups=_parse_list(args.allow_market_groups),
        allowed_timeframes=_parse_list(args.allow_timeframes),
        mt5_enabled=False,
        live_enabled=False,
        telegram_command_bot_enabled=False,
        fixture_mode=bool(args.fixture_mode),
    )
    result = build_bot_dry_run(
        BotDryRunConfig(
            snapshot_csv=args.snapshot_csv,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        ),
        options,
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "ledger_rows": len(result.ledger_rows),
                "decision_distribution": result.run_meta["decision_distribution"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
