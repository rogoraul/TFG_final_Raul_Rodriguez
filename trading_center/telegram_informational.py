"""Legacy generic Telegram informational renderer.

The canonical Telegram block for the final TFG closure is
``trading_center.telegram_mt5_bot_informational`` plus ``telegram_sender_gate``
and ``telegram_real_sender``.  This older module remains as reproducible
evidence for the pre-MT5-Bot informational design.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DESIGN_DIR = REPO_ROOT / "artifacts/tfg/telegram_informational_design_v1_2026-05-28"
DEFAULT_SNAPSHOT_CSV = (
    REPO_ROOT
    / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv"
)
DEFAULT_SECURITY_FLAGS_CSV = (
    REPO_ROOT / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/security_flags_check.csv"
)
DEFAULT_DASHBOARD_REVIEW_META = (
    REPO_ROOT / "artifacts/tfg/trading_center_readonly_full_review_v1_2026-05-28/run_meta.json"
)
DEFAULT_WAVECOUNT_PANEL_META = REPO_ROOT / "artifacts/tfg/wavecount_study_panel_v1_2026-05-28/run_meta.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/telegram_informational_v1_2026-05-28"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TELEGRAM_INFORMATIONAL_V1.md"

METHOD_VERSION = "telegram_informational_v1_dry_run"

DEFAULT_MESSAGE_TYPES = [
    "platform_daily_summary",
    "watchlist_status_digest",
    "data_health_alert",
    "riskguard_status_notice",
    "system_audit_notice",
    "pipeline_error_notice",
    "manual_review_reminder",
]

OPTIONAL_WAVECOUNT_TYPE = "wavecount_study_digest"

BLOCKED_WORDING_PATTERNS = [
    r"\bcomprar\b",
    r"\bvender\b",
    r"\bbuy\b",
    r"\bsell\b",
    r"\bexecute\b",
    r"\bejecutar\b",
    r"\baprobar\b",
    r"\borden\b",
    r"entrada\s+recomendada",
    r"senal\s+de\s+compra",
    r"señal\s+de\s+compra",
    r"senal\s+de\s+venta",
    r"señal\s+de\s+venta",
    r"activar\s+bot",
    r"mt5\s+execute",
]


@dataclass(frozen=True)
class TelegramInformationalConfig:
    design_dir: Path = DEFAULT_DESIGN_DIR
    snapshot_csv: Path = DEFAULT_SNAPSHOT_CSV
    security_flags_csv: Path = DEFAULT_SECURITY_FLAGS_CSV
    dashboard_review_meta: Path = DEFAULT_DASHBOARD_REVIEW_META
    wavecount_panel_meta: Path = DEFAULT_WAVECOUNT_PANEL_META
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH


@dataclass(frozen=True)
class TelegramInformationalResult:
    decision: str
    rendered_messages: list[dict[str, Any]]
    source_data_audit: list[dict[str, Any]]
    no_action_audit: list[dict[str, Any]]
    delivery_audit: list[dict[str, Any]]
    delivery_condition_audit: list[dict[str, Any]]
    coverage: list[dict[str, Any]]
    issues_or_risks: list[dict[str, Any]]
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_telegram_informational(
    config: TelegramInformationalConfig | None = None,
    *,
    message_types: list[str] | None = None,
    include_wavecount_study: bool = False,
    max_messages: int | None = None,
    dry_run: bool = True,
    manual_preview: bool = False,
) -> TelegramInformationalResult:
    config = config or TelegramInformationalConfig()
    generated_at = utc_now()
    source_data = read_source_data(config)
    policies = read_policy_tables(config)
    selected_types = select_message_types(message_types, include_wavecount_study)
    rendered = render_messages(
        source_data=source_data,
        policies=policies,
        message_types=selected_types,
        generated_at=generated_at,
    )
    no_action = build_no_action_audit(rendered)
    attach_safety(rendered, no_action)
    delivery = simulate_delivery(
        rendered,
        policies["delivery_policy"],
        max_messages=max_messages,
        dry_run=dry_run,
        manual_preview=manual_preview,
    )
    attach_delivery(rendered, delivery)
    condition_audit = build_delivery_condition_audit(delivery)
    source_audit = build_source_data_audit(source_data)
    coverage = build_message_type_coverage(policies["message_types"], selected_types, rendered)
    issues = build_issues_or_risks(source_audit, no_action, delivery, include_wavecount_study)
    decision = decide_result(source_audit, no_action, dry_run)
    run_meta = build_run_meta(
        generated_at=generated_at,
        decision=decision,
        rendered=rendered,
        delivery=delivery,
        include_wavecount_study=include_wavecount_study,
        max_messages=max_messages,
        dry_run=dry_run,
        manual_preview=manual_preview,
    )
    written = write_outputs(
        config=config,
        rendered=rendered,
        source_audit=source_audit,
        no_action=no_action,
        delivery=delivery,
        condition_audit=condition_audit,
        coverage=coverage,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, rendered, source_audit, no_action, delivery, coverage, issues, run_meta)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "TELEGRAM_INFORMATIONAL_V1.md"
    return TelegramInformationalResult(
        decision=decision,
        rendered_messages=rendered,
        source_data_audit=source_audit,
        no_action_audit=no_action,
        delivery_audit=delivery,
        delivery_condition_audit=condition_audit,
        coverage=coverage,
        issues_or_risks=issues,
        run_meta=run_meta,
        written_files=written,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def select_message_types(message_types: list[str] | None, include_wavecount_study: bool) -> list[str]:
    selected = list(message_types) if message_types else list(DEFAULT_MESSAGE_TYPES)
    if include_wavecount_study and OPTIONAL_WAVECOUNT_TYPE not in selected:
        selected.append(OPTIONAL_WAVECOUNT_TYPE)
    if not include_wavecount_study:
        selected = [message_type for message_type in selected if message_type != OPTIONAL_WAVECOUNT_TYPE]
    return dedupe_preserve_order(selected)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def read_source_data(config: TelegramInformationalConfig) -> dict[str, Any]:
    snapshot_rows = read_csv(config.snapshot_csv)
    security_flags = read_csv(config.security_flags_csv)
    dashboard_meta = read_json(config.dashboard_review_meta)
    wavecount_meta = read_json(config.wavecount_panel_meta)
    return {
        "snapshot_csv": config.snapshot_csv,
        "security_flags_csv": config.security_flags_csv,
        "dashboard_review_meta": config.dashboard_review_meta,
        "wavecount_panel_meta": config.wavecount_panel_meta,
        "snapshot_rows": snapshot_rows,
        "security_flags": security_flags,
        "dashboard_meta": dashboard_meta,
        "wavecount_meta": wavecount_meta,
        "snapshot_summary": summarize_snapshot(snapshot_rows, security_flags),
    }


def read_policy_tables(config: TelegramInformationalConfig) -> dict[str, list[dict[str, str]]]:
    tables_dir = config.design_dir / "tables"
    return {
        "message_types": read_csv(tables_dir / "telegram_message_types.csv"),
        "delivery_policy": read_csv(tables_dir / "telegram_delivery_policy.csv"),
        "future_config": read_csv(tables_dir / "telegram_future_config_contract.csv"),
        "templates": read_csv(tables_dir / "telegram_message_templates.csv"),
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def summarize_snapshot(snapshot_rows: list[dict[str, str]], security_flags: list[dict[str, str]]) -> dict[str, Any]:
    watchlist_rows = [row for row in snapshot_rows if row.get("signal_state") == "watching_setup"]
    freshness_counts = count_by(snapshot_rows, "data_freshness_status")
    riskguard_counts = count_by(snapshot_rows, "riskguard_status")
    groups = count_by(snapshot_rows, "market_group")
    timeframes = count_by(snapshot_rows, "timeframe_ltf")
    security_status = "passed"
    for row in security_flags:
        if str(row.get("status", "")).lower() != "passed":
            security_status = "failed"
            break
    return {
        "snapshot_rows": len(snapshot_rows),
        "watchlist_rows": len(watchlist_rows),
        "snapshot_id": first_value(snapshot_rows, "snapshot_id"),
        "generated_at": first_value(snapshot_rows, "generated_at"),
        "run_kind": first_value(snapshot_rows, "run_kind"),
        "data_origin": first_value(snapshot_rows, "data_origin"),
        "freshness_counts": freshness_counts,
        "riskguard_counts": riskguard_counts,
        "market_groups": groups,
        "timeframes": timeframes,
        "security_flags_status": security_status,
        "can_execute_order_true": count_true(snapshot_rows, "can_execute_order"),
        "wavecount_filter_true": count_true(snapshot_rows, "wavecount_should_filter_trade"),
        "non_read_only_rows": sum(1 for row in snapshot_rows if not boolish(row.get("is_read_only"))),
    }


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def count_true(rows: list[dict[str, str]], key: str) -> int:
    return sum(1 for row in rows if boolish(row.get(key)))


def first_value(rows: list[dict[str, str]], key: str, default: str = "not_available") -> str:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def count_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    return dict(Counter(row.get(key, "not_available") or "not_available" for row in rows))


def render_messages(
    *,
    source_data: dict[str, Any],
    policies: dict[str, list[dict[str, str]]],
    message_types: list[str],
    generated_at: str,
) -> list[dict[str, Any]]:
    message_type_policy = {row.get("message_type", ""): row for row in policies["message_types"]}
    delivery_policy = {row.get("message_type", ""): row for row in policies["delivery_policy"]}
    summary = source_data["snapshot_summary"]
    wavecount_meta = source_data["wavecount_meta"]
    messages: list[dict[str, Any]] = []
    for index, message_type in enumerate(message_types, start=1):
        policy = message_type_policy.get(message_type, {})
        delivery = delivery_policy.get(message_type, {})
        title, body, contains_wavecount, source_artifacts = build_message_body(
            message_type,
            summary,
            source_data,
            wavecount_meta,
        )
        condition = extract_message_condition(
            message_type=message_type,
            summary=summary,
            source_data=source_data,
            wavecount_meta=wavecount_meta,
        )
        cooldown = as_int(delivery.get("cooldown_minutes"), 120)
        dedup_key = make_dedup_key(message_type, summary, body, generated_at)
        messages.append(
            {
                "message_id": f"tginfo_{index:02d}_{safe_slug(message_type)}",
                "message_type": message_type,
                "severity": policy.get("severity", "info") or "info",
                "dedup_key": dedup_key,
                "cooldown_minutes": cooldown,
                "source_artifacts": "|".join(source_artifacts),
                "title": title,
                "body": body,
                "safe_to_send": True,
                "why_safe": "Wording audit pending.",
                "why_not_operational": (
                    "Mensaje informativo: no crea instrucciones, no filtra, no ejecuta y no cambia estado."
                ),
                "contains_wavecount": contains_wavecount,
                "wavecount_study_only": contains_wavecount,
                "condition_status": condition["condition_status"],
                "condition_reason": condition["condition_reason"],
                "manual_preview_required": condition["manual_preview_required"],
                "event_count": condition["event_count"],
                "generated_at": generated_at,
                "send_real": False,
                "method_version": METHOD_VERSION,
            }
        )
    return messages


def build_message_body(
    message_type: str,
    summary: dict[str, Any],
    source_data: dict[str, Any],
    wavecount_meta: dict[str, Any],
) -> tuple[str, str, bool, list[str]]:
    if message_type == "platform_daily_summary":
        body = "\n".join(
            [
                "Trading Center read-only",
                f"Snapshot: {summary['snapshot_id']}",
                f"Run kind: {summary['run_kind']}",
                f"Watchlist: {summary['watchlist_rows']} filas",
                f"Data health: {format_counts(summary['freshness_counts'])}",
                f"Flags duros: {summary['security_flags_status']}",
                "Nota: contexto informativo; revisar dashboard para detalle.",
            ]
        )
        return "Resumen plataforma", body, False, [str(source_data["snapshot_csv"]), str(source_data["security_flags_csv"])]

    if message_type == "watchlist_status_digest":
        body = "\n".join(
            [
                "Watchlist informativa",
                f"Elementos en vigilancia: {summary['watchlist_rows']}",
                f"Grupos: {format_counts(summary['market_groups'])}",
                f"Timeframes: {format_counts(summary['timeframes'])}",
                "Abrir dashboard read-only para revisar contexto.",
            ]
        )
        return "Watchlist", body, False, [str(source_data["snapshot_csv"])]

    if message_type == "data_health_alert":
        issue_count = sum(count for status, count in summary["freshness_counts"].items() if status != "latest_closed_bar")
        body = "\n".join(
            [
                "Estado de datos",
                f"Freshness: {format_counts(summary['freshness_counts'])}",
                f"Incidencias detectadas: {issue_count}",
                "Revision manual solo si aparece stale/missing.",
            ]
        )
        return "Data health", body, False, [str(source_data["snapshot_csv"])]

    if message_type == "riskguard_status_notice":
        body = "\n".join(
            [
                "RiskGuard informativo",
                f"Estados: {format_counts(summary['riskguard_counts'])}",
                "Modo fail-closed; no habilita acciones.",
            ]
        )
        return "RiskGuard", body, False, [str(source_data["snapshot_csv"])]

    if message_type == "system_audit_notice":
        body = "\n".join(
            [
                "Auditoria sistema",
                f"Flags duros: {summary['security_flags_status']}",
                f"Rows snapshot: {summary['snapshot_rows']}",
                "SQL write y DDL permanecen fuera de esta fase.",
            ]
        )
        return "Auditoria sistema", body, False, [str(source_data["security_flags_csv"])]

    if message_type == "pipeline_error_notice":
        dashboard_decision = source_data["dashboard_meta"].get("decision", "not_available")
        body = "\n".join(
            [
                "Estado pipeline",
                f"Revision dashboard: {dashboard_decision}",
                "Errores criticos detectados: 0",
                "Si aparece error, revisar artifacts locales.",
            ]
        )
        return "Pipeline", body, False, [str(source_data["dashboard_review_meta"])]

    if message_type == "manual_review_reminder":
        body = "\n".join(
            [
                "Revision manual",
                "Pendientes criticos: 0",
                "Areas: Telegram real, bot y MT5 siguen aplazados.",
                "Usar dashboard read-only para detalle.",
            ]
        )
        return "Revision manual", body, False, [str(source_data["dashboard_review_meta"])]

    if message_type == OPTIONAL_WAVECOUNT_TYPE:
        body = "\n".join(
            [
                "WaveCount estudio",
                f"Casos: {wavecount_meta.get('wavecount_rows', 'not_available')}",
                f"Buckets: {wavecount_meta.get('wavecount_buckets', 'not_available')}",
                f"Graficos inventariados: {wavecount_meta.get('wavecount_visual_cases', 'not_available')}",
                "Contexto de estudio; no es senal, no es filtro y no es ejecutable.",
            ]
        )
        return "WaveCount estudio", body, True, [str(source_data["wavecount_panel_meta"])]

    body = "\n".join(
        [
            f"Tipo {message_type}",
            "No hay renderer especifico; queda como preview no enviado.",
        ]
    )
    return message_type, body, False, []


def extract_message_condition(
    *,
    message_type: str,
    summary: dict[str, Any],
    source_data: dict[str, Any],
    wavecount_meta: dict[str, Any],
) -> dict[str, Any]:
    if message_type in {"platform_daily_summary", "watchlist_status_digest", "system_audit_notice"}:
        return condition("allowed_digest", "digest_allowed_without_incident", 1, False)

    if message_type == "data_health_alert":
        issue_count = sum(count for status, count in summary["freshness_counts"].items() if status != "latest_closed_bar")
        if issue_count > 0:
            return condition("event_detected", "data_health_issue_detected", issue_count, False)
        return condition("no_condition", "no_data_health_issue", 0, True)

    if message_type == "pipeline_error_notice":
        error_count = count_pipeline_errors(source_data)
        if error_count > 0:
            return condition("event_detected", "pipeline_error_detected", error_count, False)
        return condition("no_condition", "no_pipeline_error", 0, True)

    if message_type == "manual_review_reminder":
        pending_count = count_manual_review_items(source_data)
        if pending_count > 0:
            return condition("event_detected", "manual_review_items_open", pending_count, False)
        return condition("no_condition", "no_manual_review_items", 0, True)

    if message_type == "riskguard_status_notice":
        event_count = count_riskguard_events(summary)
        if event_count > 0:
            return condition("event_detected", "riskguard_event_detected", event_count, False)
        return condition("no_condition", "no_riskguard_event", 0, True)

    if message_type == OPTIONAL_WAVECOUNT_TYPE:
        event_count = as_int(wavecount_meta.get("wavecount_rows"), 0)
        return condition("manual_only", "wavecount_study_digest_requires_manual_preview", event_count, True)

    return condition("manual_only", "unknown_message_type_requires_manual_preview", 0, True)


def condition(status: str, reason: str, event_count: int, manual_preview_required: bool) -> dict[str, Any]:
    return {
        "condition_status": status,
        "condition_reason": reason,
        "event_count": event_count,
        "manual_preview_required": manual_preview_required,
    }


def count_pipeline_errors(source_data: dict[str, Any]) -> int:
    decision = str(source_data["dashboard_meta"].get("decision", "")).lower()
    return 1 if "blocked" in decision or "error" in decision else 0


def count_manual_review_items(source_data: dict[str, Any]) -> int:
    return as_int(source_data["dashboard_meta"].get("manual_review_items"), 0)


def count_riskguard_events(summary: dict[str, Any]) -> int:
    event_count = 0
    for status, count in summary["riskguard_counts"].items():
        normalized = str(status).lower()
        if normalized in {"error", "blocked", "kill_switch", "failed", "fail_closed"}:
            event_count += count
    return event_count


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "not_available"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "item"


def make_dedup_key(message_type: str, summary: dict[str, Any], body: str, generated_at: str) -> str:
    material = f"{message_type}|{summary.get('snapshot_id')}|{generated_at[:10]}|{body}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"{message_type}:{summary.get('snapshot_id')}:{digest}"


def build_no_action_audit(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for message in messages:
        text = f"{message.get('title', '')}\n{message.get('body', '')}"
        hits = find_blocked_wording(text)
        rows.append(
            {
                "message_id": message["message_id"],
                "message_type": message["message_type"],
                "safe_to_send": not hits,
                "blocked_patterns": "|".join(hits),
                "send_real": False,
                "audit_status": "pass" if not hits else "blocked",
                "notes": "No operational wording detected." if not hits else "Blocked by no-action wording policy.",
            }
        )
    return rows


def find_blocked_wording(text: str) -> list[str]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for pattern in BLOCKED_WORDING_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def normalize_text(text: str) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "Á": "a",
        "É": "e",
        "Í": "i",
        "Ó": "o",
        "Ú": "u",
        "ñ": "ñ",
        "Ñ": "ñ",
    }
    normalized = text
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    return normalized.lower()


def attach_safety(messages: list[dict[str, Any]], no_action_audit: list[dict[str, Any]]) -> None:
    audit_by_id = {row["message_id"]: row for row in no_action_audit}
    for message in messages:
        audit = audit_by_id[message["message_id"]]
        safe = bool(audit["safe_to_send"])
        message["safe_to_send"] = safe
        message["why_safe"] = (
            "Pasa validacion no-action; renderizado dry-run; sin sender real." if safe else "Bloqueado por wording operativo."
        )


def simulate_delivery(
    messages: list[dict[str, Any]],
    delivery_policy: list[dict[str, str]],
    *,
    max_messages: int | None,
    dry_run: bool,
    manual_preview: bool = False,
) -> list[dict[str, Any]]:
    policy_by_type = {row.get("message_type", ""): row for row in delivery_policy}
    daily_cap = max_messages if max_messages is not None else read_global_daily_cap(messages, delivery_policy)
    sent_count = 0
    rows: list[dict[str, Any]] = []
    for message in messages:
        policy = policy_by_type.get(message["message_type"], {})
        type_cap = as_int(policy.get("max_per_day"), daily_cap)
        condition_status = str(message.get("condition_status", "manual_only"))
        condition_reason = str(message.get("condition_reason", "not_evaluated"))
        manual_preview_required = bool(message.get("manual_preview_required"))
        event_count = as_int(message.get("event_count"), 0)
        status = "preview_allowed"
        reason = "Dry-run preview only; no real send."
        if not dry_run:
            status = "blocked_no_real_sender"
            reason = "Real sender is intentionally not implemented in v1."
        elif not message["safe_to_send"]:
            status = "blocked_by_no_action"
            reason = "Message failed no-action audit."
        elif condition_status == "no_condition" and not manual_preview:
            status = "omitted_no_condition"
            reason = condition_reason
        elif condition_status == "manual_only" and not manual_preview:
            status = "manual_only"
            reason = condition_reason
        elif sent_count >= daily_cap:
            status = "omitted_by_daily_cap"
            reason = f"Global max_messages={daily_cap} reached."
        elif type_cap <= 0:
            status = "omitted_by_type_cap"
            reason = "Message type max_per_day is 0."
        else:
            sent_count += 1
            if manual_preview and manual_preview_required:
                reason = f"Manual preview explicitly requested; {condition_reason}."
        rows.append(
            {
                "message_id": message["message_id"],
                "message_type": message["message_type"],
                "dedup_key": message["dedup_key"],
                "cooldown_minutes": message["cooldown_minutes"],
                "max_per_day": type_cap,
                "global_max_messages": daily_cap,
                "safe_to_send": message["safe_to_send"],
                "condition_status": condition_status,
                "condition_reason": condition_reason,
                "manual_preview_required": manual_preview_required,
                "manual_preview": manual_preview,
                "event_count": event_count,
                "send_real": False,
                "delivery_status": status,
                "delivery_reason": reason,
                "would_send_in_dry_run": status == "preview_allowed",
            }
        )
    return rows


def read_global_daily_cap(messages: list[dict[str, Any]], delivery_policy: list[dict[str, str]]) -> int:
    caps = [as_int(row.get("max_per_day"), 0) for row in delivery_policy if row.get("message_type") in {m["message_type"] for m in messages}]
    return max(1, min(sum(cap for cap in caps if cap > 0), len(messages)))


def attach_delivery(messages: list[dict[str, Any]], delivery: list[dict[str, Any]]) -> None:
    delivery_by_id = {row["message_id"]: row for row in delivery}
    for message in messages:
        row = delivery_by_id[message["message_id"]]
        message["delivery_status"] = row["delivery_status"]
        message["delivery_reason"] = row["delivery_reason"]
        message["manual_preview"] = row["manual_preview"]
        message["would_send_in_dry_run"] = row["would_send_in_dry_run"]


def build_delivery_condition_audit(delivery: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "message_id": row["message_id"],
            "message_type": row["message_type"],
            "condition_status": row["condition_status"],
            "condition_reason": row["condition_reason"],
            "event_count": row["event_count"],
            "manual_preview_required": row["manual_preview_required"],
            "manual_preview": row["manual_preview"],
            "delivery_status": row["delivery_status"],
            "delivery_reason": row["delivery_reason"],
            "would_send_in_dry_run": row["would_send_in_dry_run"],
        }
        for row in delivery
    ]


def build_source_data_audit(source_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        source_row("snapshot_export", source_data["snapshot_csv"], len(source_data["snapshot_rows"]), "messages_context"),
        source_row("security_flags", source_data["security_flags_csv"], len(source_data["security_flags"]), "hard_safety"),
        source_row(
            "dashboard_review_meta",
            source_data["dashboard_review_meta"],
            1 if source_data["dashboard_meta"] else 0,
            "pipeline_status",
        ),
        source_row(
            "wavecount_panel_meta",
            source_data["wavecount_panel_meta"],
            1 if source_data["wavecount_meta"] else 0,
            "optional_wavecount_study",
        ),
    ]


def source_row(source_id: str, path: Path, rows: int, used_for: str) -> dict[str, Any]:
    exists = path.exists()
    return {
        "source_id": source_id,
        "path": str(path),
        "exists": exists,
        "rows": rows,
        "status": "available" if exists and rows > 0 else "missing_or_empty",
        "used_for": used_for,
        "sql_real_read": False,
        "sql_real_written": False,
    }


def build_message_type_coverage(
    policy_rows: list[dict[str, str]],
    selected_types: list[str],
    rendered: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rendered_types = {message["message_type"] for message in rendered}
    selected = set(selected_types)
    rows: list[dict[str, Any]] = []
    for policy in policy_rows:
        message_type = policy.get("message_type", "")
        rows.append(
            {
                "message_type": message_type,
                "v1_status": policy.get("v1_status", ""),
                "selected": message_type in selected,
                "rendered": message_type in rendered_types,
                "severity": policy.get("severity", ""),
                "requires_deduplication": policy.get("requires_deduplication", ""),
                "notes": "Rendered in dry-run." if message_type in rendered_types else "Not selected for this dry-run.",
            }
        )
    return rows


def build_issues_or_risks(
    source_audit: list[dict[str, Any]],
    no_action: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    include_wavecount_study: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in source_audit:
        if source["status"] != "available" and source["source_id"] not in {"wavecount_panel_meta"}:
            rows.append(
                {
                    "issue_id": f"missing_{source['source_id']}",
                    "severity": "blocker",
                    "area": "source_data",
                    "description": f"Required source is missing or empty: {source['path']}",
                    "recommended_action": "Restore audited artifact before considering Telegram preview reliable.",
                }
            )
    if any(not row["safe_to_send"] for row in no_action):
        rows.append(
            {
                "issue_id": "no_action_wording_block",
                "severity": "blocker",
                "area": "message_safety",
                "description": "At least one message failed the no-action wording audit.",
                "recommended_action": "Rewrite message body before any future sender can use it.",
            }
        )
    if any(row["delivery_status"].startswith("omitted") for row in delivery):
        rows.append(
            {
                "issue_id": "delivery_cap_omitted_messages",
                "severity": "info",
                "area": "delivery_policy",
                "description": "Some dry-run messages were omitted by condition or simulated caps.",
                "recommended_action": "Expected for alert-like messages without a real incident.",
            }
        )
    if not include_wavecount_study:
        rows.append(
            {
                "issue_id": "wavecount_digest_disabled_by_default",
                "severity": "info",
                "area": "wavecount",
                "description": "WaveCount study digest remains disabled unless explicitly requested.",
                "recommended_action": "Keep default off unless a manual study-only digest is desired.",
            }
        )
    if not rows:
        rows.append(
            {
                "issue_id": "none_blocking",
                "severity": "info",
                "area": "closure",
                "description": "No blocking issue detected for dry-run preview.",
                "recommended_action": "Keep real Telegram send blocked until a separate reviewed phase.",
            }
        )
    return rows


def decide_result(source_audit: list[dict[str, Any]], no_action: list[dict[str, Any]], dry_run: bool) -> str:
    required_missing = [
        row for row in source_audit if row["status"] != "available" and row["source_id"] not in {"wavecount_panel_meta"}
    ]
    if required_missing:
        return "telegram_informational_v1_deferred"
    if not dry_run:
        return "telegram_informational_v1_blocked_by_safety"
    if any(not row["safe_to_send"] for row in no_action):
        return "telegram_delivery_policy_fix_blocked_by_safety"
    return "telegram_delivery_policy_fix_ready_for_sender_gate_design"


def build_run_meta(
    *,
    generated_at: str,
    decision: str,
    rendered: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    include_wavecount_study: bool,
    max_messages: int | None,
    dry_run: bool,
    manual_preview: bool,
) -> dict[str, Any]:
    return {
        "phase": "telegram_informational_v1",
        "generated_at": generated_at,
        "decision": decision,
        "method_version": METHOD_VERSION,
        "telegram_implemented": True,
        "telegram_connected": False,
        "telegram_real_messages_sent": 0,
        "telegram_tokens_created": False,
        "telegram_bot_created": False,
        "dry_run_only": True,
        "dry_run_requested": dry_run,
        "manual_preview": manual_preview,
        "sql_real_written": False,
        "ddl_executed": False,
        "bot_implemented": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
        "wavecount_used_as_filter": False,
        "include_wavecount_study": include_wavecount_study,
        "message_count": len(rendered),
        "safe_to_send_count": sum(1 for message in rendered if message["safe_to_send"]),
        "send_real_count": sum(1 for message in rendered if message["send_real"]),
        "preview_allowed_count": sum(1 for row in delivery if row["delivery_status"] == "preview_allowed"),
        "omitted_no_condition_count": sum(1 for row in delivery if row["delivery_status"] == "omitted_no_condition"),
        "manual_only_count": sum(1 for row in delivery if row["delivery_status"] == "manual_only"),
        "max_messages": max_messages,
        "message_type_distribution": dict(Counter(message["message_type"] for message in rendered)),
        "next_recommended_phase": "telegram_informational_v1_review_or_sender_gate",
    }


def write_outputs(
    *,
    config: TelegramInformationalConfig,
    rendered: list[dict[str, Any]],
    source_audit: list[dict[str, Any]],
    no_action: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    condition_audit: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = config.output_dir / "tables"
    write_csv(config.output_dir / "rendered_messages.csv", rendered)
    (config.output_dir / "rendered_messages.json").write_text(
        json.dumps(rendered, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_csv(tables_dir / "source_data_audit.csv", source_audit)
    write_csv(tables_dir / "no_action_message_audit.csv", no_action)
    write_csv(tables_dir / "delivery_simulation_audit.csv", delivery)
    write_csv(tables_dir / "delivery_condition_audit.csv", condition_audit)
    write_csv(tables_dir / "message_type_coverage.csv", coverage)
    write_csv(tables_dir / "issues_or_risks.csv", issues)
    (config.output_dir / "run_meta.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "rendered_messages_csv": config.output_dir / "rendered_messages.csv",
        "rendered_messages_json": config.output_dir / "rendered_messages.json",
        "source_data_audit": tables_dir / "source_data_audit.csv",
        "no_action_message_audit": tables_dir / "no_action_message_audit.csv",
        "delivery_simulation_audit": tables_dir / "delivery_simulation_audit.csv",
        "delivery_condition_audit": tables_dir / "delivery_condition_audit.csv",
        "message_type_coverage": tables_dir / "message_type_coverage.csv",
        "issues_or_risks": tables_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }


def write_docs(
    config: TelegramInformationalConfig,
    rendered: list[dict[str, Any]],
    source_audit: list[dict[str, Any]],
    no_action: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> None:
    safe_count = sum(1 for row in no_action if row["safe_to_send"])
    would_send = sum(1 for row in delivery if row["would_send_in_dry_run"])
    wavecount_count = sum(1 for message in rendered if message["contains_wavecount"])
    omitted_count = sum(1 for row in delivery if row["delivery_status"] == "omitted_no_condition")
    manual_only_count = sum(1 for row in delivery if row["delivery_status"] == "manual_only")
    title = "Telegram Informational V1 Delivery Policy Fix" if "delivery_policy_fix" in config.output_dir.name else "Telegram Informational V1"
    text = f"""# Telegram Informational V1

Fecha: {run_meta['generated_at']}

Decision: `{run_meta['decision']}`.

## Resumen

Se implementa `telegram_informational_v1` como generador dry-run de mensajes
informativos. La fase crea un modulo CLI reproducible, renderiza mensajes desde
artifacts auditados y guarda auditorias de fuentes, wording no-action y
deduplicacion/cooldown. Esta version incluye gates de delivery para omitir
alertas sin incidencia real salvo `--manual-preview`.

No se conecta Telegram real, no se crea bot, no se crean tokens, no se guardan
chat IDs, no se escribe SQL, no hay DDL, no se conecta MT5, no se ejecutan
backtests y no se generan senales.

## Modulo Y CLI

- Modulo: `trading_center/telegram_informational.py`
- CLI dry-run:

```powershell
python -m trading_center.telegram_informational --dry-run --output-dir artifacts/tfg/telegram_informational_v1_2026-05-28
```

El sender real no esta implementado. Todos los mensajes quedan con
`send_real=false`.

## Mensajes Generados

- Mensajes renderizados: {len(rendered)}
- Mensajes que pasan no-action: {safe_count}
- Previews permitidos por simulacion de delivery: {would_send}
- Omitidos por falta de condicion: {omitted_count}
- Manual-only sin preview explicito: {manual_only_count}
- Mensajes WaveCount: {wavecount_count}

Tipos renderizados:

{bullet_list(sorted({message['message_type'] for message in rendered}))}

## Fuentes

{bullet_list([f"{row['source_id']}: {row['status']} ({row['rows']} filas)" for row in source_audit])}

## Seguridad

La auditoria `no_action_message_audit.csv` bloquea wording operativo como
comprar/vender, comandos de ejecucion, aprobaciones, instrucciones de entrada
o lenguaje que parezca accion de mercado. Las expresiones permitidas son de
contexto informativo, revision manual y estudio.

WaveCount solo aparece si se habilita explicitamente y siempre como
`study_only`; no se usa como filtro.

## Deduplicacion Y Cooldown

Cada mensaje incluye:

- `dedup_key`
- `cooldown_minutes`
- `delivery_status`
- `would_send_in_dry_run`

La fase simula caps y cooldown, pero no envia nada.

## Outputs

- `rendered_messages.csv`
- `rendered_messages.json`
- `tables/source_data_audit.csv`
- `tables/no_action_message_audit.csv`
- `tables/delivery_simulation_audit.csv`
- `tables/delivery_condition_audit.csv`
- `tables/message_type_coverage.csv`
- `tables/issues_or_risks.csv`
- `run_meta.json`

## Riesgos Pendientes

{bullet_list([f"{row['severity']}: {row['description']}" for row in issues])}

## Siguiente Paso

Antes de cualquier envio real hace falta una fase separada de gate/sender con
configuracion externa, revision manual, no-action reforzado y confirmacion
explicita. Bot dry-run y MT5 siguen bloqueados.
"""
    text = text.replace("# Telegram Informational V1", f"# {title}", 1)
    (config.output_dir / "TELEGRAM_INFORMATIONAL_V1.md").write_text(text, encoding="utf-8")
    if "delivery_policy_fix" in config.output_dir.name:
        (config.output_dir / "TELEGRAM_INFORMATIONAL_V1_DELIVERY_POLICY_FIX.md").write_text(text, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(text, encoding="utf-8")
    if "delivery_policy_fix" in config.output_dir.name:
        (config.doc_path.parent / "TELEGRAM_INFORMATIONAL_V1_DELIVERY_POLICY_FIX.md").write_text(text, encoding="utf-8")


def bullet_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def parse_message_types(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render Telegram informational v1 messages in dry-run mode.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Render messages without sending.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--message-types", default=None, help="Comma-separated message types to render.")
    parser.add_argument("--include-wavecount-study", action="store_true", default=False)
    parser.add_argument("--max-messages", type=int, default=None)
    parser.add_argument("--manual-preview", action="store_true", default=False)
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--no-send", action="store_true", default=True, help="Keep real sending disabled.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    config = TelegramInformationalConfig(
        design_dir=source_root / "artifacts/tfg/telegram_informational_design_v1_2026-05-28",
        snapshot_csv=source_root
        / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv",
        security_flags_csv=source_root
        / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/security_flags_check.csv",
        dashboard_review_meta=source_root
        / "artifacts/tfg/trading_center_readonly_full_review_v1_2026-05-28/run_meta.json",
        wavecount_panel_meta=source_root / "artifacts/tfg/wavecount_study_panel_v1_2026-05-28/run_meta.json",
        output_dir=args.output_dir,
        doc_path=source_root / "docs/TELEGRAM_INFORMATIONAL_V1.md",
    )
    result = build_telegram_informational(
        config,
        message_types=parse_message_types(args.message_types),
        include_wavecount_study=args.include_wavecount_study,
        max_messages=args.max_messages,
        dry_run=True,
        manual_preview=args.manual_preview,
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "messages": len(result.rendered_messages),
                "output_dir": str(config.output_dir),
                "telegram_connected": False,
                "telegram_real_messages_sent": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
