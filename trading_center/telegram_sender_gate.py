"""Sender gate that keeps Telegram informational and fail-closed by default."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_DIR = REPO_ROOT / "artifacts/tfg/telegram_informational_v1_delivery_policy_fix_2026-05-29"
DEFAULT_DESIGN_DIR = REPO_ROOT / "artifacts/tfg/telegram_sender_gate_design_v1_2026-05-29"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/telegram_sender_gate_v1_2026-05-29"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TELEGRAM_SENDER_GATE_V1.md"

METHOD_VERSION = "telegram_sender_gate_v1"

DEFAULT_ALLOWED_MESSAGE_TYPES = (
    "platform_daily_summary",
    "watchlist_status_digest",
    "data_health_alert",
    "riskguard_status_notice",
    "system_audit_notice",
    "pipeline_error_notice",
    "manual_review_reminder",
    "wavecount_study_digest",
    "mt5_bot_status_digest",
    "mt5_account_snapshot_notice",
    "mt5_positions_digest",
    "riskguard_block_notice",
    "demo_order_event_notice",
    "demo_position_close_notice",
    "refresh_pipeline_notice",
    "ai_review_available_notice",
    "daily_summary",
)

DEFAULT_ALLOWED_SEVERITIES = ("info", "warning", "error", "manual_review", "study", "info_or_warning")

SECRET_FILE_CANDIDATES = (
    ".env",
    ".env.local",
    "telegram_token.txt",
    "telegram_chat_id.txt",
    "telegram_bot_token.txt",
)

SECRET_TEMPLATE_CANDIDATES = (".env.example",)

GATE_DECISION_FIELDS = [
    "message_id",
    "message_type",
    "severity",
    "gate_decision",
    "gate_reason",
    "gate_reasons",
    "safe_to_send",
    "no_action_audit_status",
    "delivery_status",
    "condition_status",
    "condition_reason",
    "contains_wavecount",
    "wavecount_study_only",
    "original_send_real",
    "send_real_requested",
    "send_real_executed",
    "telegram_connected",
    "telegram_real_message_sent",
    "sender_gate_only",
    "source_artifacts",
    "evaluated_at",
    "title",
    "body",
    "dedup_key",
    "cooldown_minutes",
]


@dataclass(frozen=True)
class TelegramSenderGateConfig:
    """Artifact paths for one Telegram gate evaluation."""
    input_dir: Path = DEFAULT_INPUT_DIR
    design_dir: Path = DEFAULT_DESIGN_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    repo_root: Path = REPO_ROOT


@dataclass(frozen=True)
class TelegramSenderGateOptions:
    """Runtime policy flags that decide whether a message may be sent."""
    dry_run: bool = True
    telegram_enabled: bool = False
    telegram_mode: str = "informational_only"
    allow_real_send: bool = False
    send_real: bool = False
    manual_confirmation: bool = False
    allow_wavecount_study: bool = False
    allowed_message_types: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALLOWED_MESSAGE_TYPES)
    allowed_severities: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALLOWED_SEVERITIES)
    check_external_secrets: bool = False
    sender_gate_only: bool = True


@dataclass(frozen=True)
class TelegramSenderGateResult:
    """Allowed/blocked messages and audit rows from the sender gate."""
    decision: str
    allowed_to_send: list[dict[str, Any]]
    blocked_to_send: list[dict[str, Any]]
    gate_decision_audit: list[dict[str, Any]]
    gate_config_audit: list[dict[str, Any]]
    secret_presence_audit: list[dict[str, Any]]
    secret_policy_audit: list[dict[str, Any]]
    gate_policy_options: list[dict[str, Any]]
    no_action_gate_audit: list[dict[str, Any]]
    wavecount_gate_audit: list[dict[str, Any]]
    issues_or_risks: list[dict[str, Any]]
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_telegram_sender_gate(
    config: TelegramSenderGateConfig | None = None,
    options: TelegramSenderGateOptions | None = None,
) -> TelegramSenderGateResult:
    config = config or TelegramSenderGateConfig()
    options = options or TelegramSenderGateOptions()
    generated_at = utc_now()

    input_data = read_input_data(config)
    design_audit = read_design_contracts(config)
    artifact_status = build_artifact_status(config, input_data, design_audit)
    secret_audit = build_secret_presence_audit(config, options)
    global_blocks = build_global_blocks(input_data, artifact_status, secret_audit, options)

    messages = input_data["messages"]
    delivery_by_id = {row.get("message_id", ""): row for row in input_data["delivery_rows"]}
    no_action_by_id = {row.get("message_id", ""): row for row in input_data["no_action_rows"]}

    gate_rows = [
        evaluate_message(
            message=message,
            delivery=delivery_by_id.get(str(message.get("message_id", "")), {}),
            no_action=no_action_by_id.get(str(message.get("message_id", "")), {}),
            options=options,
            global_blocks=global_blocks,
            evaluated_at=generated_at,
        )
        for message in messages
    ]

    allowed = [row for row in gate_rows if row["gate_decision"] == "allowed_to_send"]
    blocked = [row for row in gate_rows if row["gate_decision"] == "blocked_to_send"]
    config_audit = build_gate_config_audit(options)
    secret_policy_audit = build_secret_policy_audit(secret_audit)
    gate_policy_options = build_gate_policy_options()
    no_action_gate = build_no_action_gate_audit(gate_rows, no_action_by_id)
    wavecount_gate = build_wavecount_gate_audit(gate_rows, options)
    issues = build_issues_or_risks(artifact_status, secret_audit, gate_rows, global_blocks, options)
    decision = decide_result(artifact_status, secret_audit)
    run_meta = build_run_meta(
        generated_at=generated_at,
        decision=decision,
        options=options,
        messages=messages,
        gate_rows=gate_rows,
        artifact_status=artifact_status,
    )
    written = write_outputs(
        config=config,
        allowed=allowed,
        blocked=blocked,
        gate_rows=gate_rows,
        config_audit=config_audit,
        secret_audit=secret_audit,
        secret_policy_audit=secret_policy_audit,
        gate_policy_options=gate_policy_options,
        no_action_gate=no_action_gate,
        wavecount_gate=wavecount_gate,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, allowed, blocked, gate_rows, secret_audit, issues, run_meta)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "TELEGRAM_SENDER_GATE_V1.md"

    return TelegramSenderGateResult(
        decision=decision,
        allowed_to_send=allowed,
        blocked_to_send=blocked,
        gate_decision_audit=gate_rows,
        gate_config_audit=config_audit,
        secret_presence_audit=secret_audit,
        secret_policy_audit=secret_policy_audit,
        gate_policy_options=gate_policy_options,
        no_action_gate_audit=no_action_gate,
        wavecount_gate_audit=wavecount_gate,
        issues_or_risks=issues,
        run_meta=run_meta,
        written_files=written,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_input_data(config: TelegramSenderGateConfig) -> dict[str, Any]:
    json_messages = read_json_list(config.input_dir / "rendered_messages.json")
    csv_messages = read_csv(config.input_dir / "rendered_messages.csv")
    messages = json_messages if json_messages else csv_messages
    return {
        "messages": messages,
        "delivery_rows": read_csv(config.input_dir / "tables" / "delivery_simulation_audit.csv"),
        "no_action_rows": read_csv(config.input_dir / "tables" / "no_action_message_audit.csv"),
        "source_data_audit": read_csv(config.input_dir / "tables" / "source_data_audit.csv"),
        "run_meta": read_json(config.input_dir / "run_meta.json"),
    }


def read_design_contracts(config: TelegramSenderGateConfig) -> dict[str, Any]:
    tables = config.design_dir / "tables"
    return {
        "required_conditions": read_csv(tables / "sender_gate_required_conditions.csv"),
        "blocking_conditions": read_csv(tables / "sender_gate_blocking_conditions.csv"),
        "future_config": read_csv(tables / "sender_gate_future_config_contract.csv"),
        "audit_log_contract": read_csv(tables / "sender_gate_audit_log_contract.csv"),
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


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


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


def build_artifact_status(
    config: TelegramSenderGateConfig,
    input_data: dict[str, Any],
    design_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("rendered_messages_csv", config.input_dir / "rendered_messages.csv", len(read_csv(config.input_dir / "rendered_messages.csv"))),
        ("rendered_messages_json", config.input_dir / "rendered_messages.json", len(input_data["messages"])),
        (
            "delivery_simulation_audit",
            config.input_dir / "tables" / "delivery_simulation_audit.csv",
            len(input_data["delivery_rows"]),
        ),
        (
            "no_action_message_audit",
            config.input_dir / "tables" / "no_action_message_audit.csv",
            len(input_data["no_action_rows"]),
        ),
        ("run_meta", config.input_dir / "run_meta.json", 1 if input_data["run_meta"] else 0),
        (
            "sender_gate_required_conditions",
            config.design_dir / "tables" / "sender_gate_required_conditions.csv",
            len(design_audit["required_conditions"]),
        ),
        (
            "sender_gate_blocking_conditions",
            config.design_dir / "tables" / "sender_gate_blocking_conditions.csv",
            len(design_audit["blocking_conditions"]),
        ),
    ]
    return [
        {
            "artifact_id": artifact_id,
            "path": str(path),
            "exists": path.exists(),
            "rows": rows,
            "status": "available" if path.exists() and rows > 0 else "missing_or_empty",
            "blocks_gate": not (path.exists() and rows > 0),
        }
        for artifact_id, path, rows in artifacts
    ]


def build_secret_presence_audit(
    config: TelegramSenderGateConfig,
    options: TelegramSenderGateOptions,
) -> list[dict[str, Any]]:
    token_present = bool(os.environ.get("TELEGRAM_BOT_TOKEN")) if options.check_external_secrets else False
    chat_id_present = bool(os.environ.get("TELEGRAM_CHAT_ID")) if options.check_external_secrets else False
    rows = [
        {
            "check_id": "external_telegram_bot_token",
            "candidate": "TELEGRAM_BOT_TOKEN",
            "category": "external_environment",
            "check_external_secrets": options.check_external_secrets,
            "present": token_present,
            "tracked_by_git": False,
            "ignored_by_git": False,
            "local_only": False,
            "value_printed": False,
            "value_stored": False,
            "status": "present" if token_present else "not_checked" if not options.check_external_secrets else "missing",
            "blocks_gate": options.check_external_secrets and not token_present,
            "matched_files_count": "",
        },
        {
            "check_id": "external_telegram_chat_id",
            "candidate": "TELEGRAM_CHAT_ID",
            "category": "external_environment",
            "check_external_secrets": options.check_external_secrets,
            "present": chat_id_present,
            "tracked_by_git": False,
            "ignored_by_git": False,
            "local_only": False,
            "value_printed": False,
            "value_stored": False,
            "status": "present" if chat_id_present else "not_checked" if not options.check_external_secrets else "missing",
            "blocks_gate": options.check_external_secrets and not chat_id_present,
            "matched_files_count": "",
        },
    ]
    secret_file_rows = [build_secret_file_row(config.repo_root, candidate) for candidate in SECRET_FILE_CANDIDATES]
    rows.extend(secret_file_rows)
    rows.extend(build_secret_template_row(config.repo_root, candidate) for candidate in SECRET_TEMPLATE_CANDIDATES)
    matched_files_count = sum(1 for row in secret_file_rows if row["present"])
    blocking_files_count = sum(1 for row in secret_file_rows if row["blocks_gate"])
    rows.append(
        {
            "check_id": "repo_secret_file_presence",
            "candidate": "|".join(SECRET_FILE_CANDIDATES),
            "category": "aggregate_repo_secret_files",
            "check_external_secrets": options.check_external_secrets,
            "present": matched_files_count > 0,
            "tracked_by_git": any(row["tracked_by_git"] for row in secret_file_rows),
            "ignored_by_git": any(row["ignored_by_git"] for row in secret_file_rows),
            "local_only": any(row["local_only"] for row in secret_file_rows),
            "value_printed": False,
            "value_stored": False,
            "status": "blocking_secret_file_present"
            if blocking_files_count
            else "local_ignored_secret_file_present"
            if matched_files_count
            else "not_found",
            "blocks_gate": blocking_files_count > 0,
            "matched_files_count": matched_files_count,
        }
    )
    return rows


def build_secret_file_row(repo_root: Path, candidate: str) -> dict[str, Any]:
    path = repo_root / candidate
    exists = path.exists()
    tracked = git_path_is_tracked(repo_root, candidate) if exists else False
    ignored = git_path_is_ignored(repo_root, candidate) if exists else False
    local_only = exists and not tracked
    status = "not_found"
    blocks_gate = False
    if exists and tracked:
        status = "tracked_secret_file_present"
        blocks_gate = True
    elif exists and ignored:
        status = "local_ignored_secret_file_present"
    elif exists:
        status = "local_unignored_secret_file_present"
        blocks_gate = True
    return {
        "check_id": f"repo_secret_file:{candidate}",
        "candidate": candidate,
        "category": "repo_secret_file_candidate",
        "check_external_secrets": False,
        "present": exists,
        "tracked_by_git": tracked,
        "ignored_by_git": ignored,
        "local_only": local_only,
        "value_printed": False,
        "value_stored": False,
        "status": status,
        "blocks_gate": blocks_gate,
        "matched_files_count": 1 if exists else 0,
    }


def build_secret_template_row(repo_root: Path, candidate: str) -> dict[str, Any]:
    path = repo_root / candidate
    exists = path.exists()
    return {
        "check_id": f"repo_secret_template:{candidate}",
        "candidate": candidate,
        "category": "repo_secret_template",
        "check_external_secrets": False,
        "present": exists,
        "tracked_by_git": git_path_is_tracked(repo_root, candidate) if exists else False,
        "ignored_by_git": git_path_is_ignored(repo_root, candidate) if exists else False,
        "local_only": exists and not git_path_is_tracked(repo_root, candidate),
        "value_printed": False,
        "value_stored": False,
        "status": "template_present" if exists else "not_found",
        "blocks_gate": False,
        "matched_files_count": 1 if exists else 0,
    }


def git_path_is_tracked(repo_root: Path, relative_path: str) -> bool:
    result = run_git(repo_root, ["ls-files", "--", relative_path])
    if result is None:
        return False
    return bool(result.stdout.strip())


def git_path_is_ignored(repo_root: Path, relative_path: str) -> bool:
    result = run_git(repo_root, ["check-ignore", "--quiet", "--", relative_path])
    if result is None:
        return False
    return result.returncode == 0


def run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None


def build_global_blocks(
    input_data: dict[str, Any],
    artifact_status: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    options: TelegramSenderGateOptions,
) -> list[str]:
    blocks: list[str] = []
    if any(row["blocks_gate"] for row in artifact_status):
        blocks.append("audit_artifacts_missing")
    if any(row["category"] == "repo_secret_file_candidate" and row["blocks_gate"] for row in secret_audit):
        blocks.append("secret_file_blocking_policy")
    if options.check_external_secrets:
        if any(row["check_id"] == "external_telegram_bot_token" and row["blocks_gate"] for row in secret_audit):
            blocks.append("missing_external_token")
        if any(row["check_id"] == "external_telegram_chat_id" and row["blocks_gate"] for row in secret_audit):
            blocks.append("missing_external_chat_id")
    source_meta = input_data.get("run_meta", {})
    if boolish(source_meta.get("telegram_connected")):
        blocks.append("source_telegram_connected_true")
    if as_int(source_meta.get("telegram_real_messages_sent"), 0) != 0:
        blocks.append("source_real_messages_already_sent")
    if boolish(source_meta.get("sql_real_written")) or boolish(source_meta.get("ddl_executed")):
        blocks.append("sql_write_or_ddl_active")
    if boolish(source_meta.get("bot_implemented")) or boolish(source_meta.get("mt5_connected")):
        blocks.append("bot_or_mt5_active")
    if boolish(source_meta.get("signals_generated")):
        blocks.append("signals_generated_active")
    if boolish(source_meta.get("wavecount_used_as_filter")):
        blocks.append("wavecount_filter_active")
    return dedupe_preserve_order(blocks)


def evaluate_message(
    *,
    message: dict[str, Any],
    delivery: dict[str, Any],
    no_action: dict[str, Any],
    options: TelegramSenderGateOptions,
    global_blocks: list[str],
    evaluated_at: str,
) -> dict[str, Any]:
    reasons: list[str] = list(global_blocks)

    if not options.telegram_enabled:
        reasons.append("telegram_disabled")
    if options.telegram_mode != "informational_only":
        reasons.append("wrong_mode")
    if not options.allow_real_send:
        reasons.append("real_send_not_allowed")
    if not options.send_real:
        reasons.append("send_real_flag_missing")
    if not options.manual_confirmation:
        reasons.append("manual_confirmation_missing")

    message_id = str(message.get("message_id", ""))
    message_type = str(message.get("message_type", ""))
    severity = str(message.get("severity", ""))
    delivery_status = str(delivery.get("delivery_status", message.get("delivery_status", "")))
    condition_status = str(delivery.get("condition_status", message.get("condition_status", "")))
    no_action_status = str(no_action.get("audit_status", "missing"))
    safe_to_send = boolish(message.get("safe_to_send")) and boolish(no_action.get("safe_to_send", message.get("safe_to_send")))
    original_send_real = boolish(message.get("send_real"))
    contains_wavecount = boolish(message.get("contains_wavecount"))
    wavecount_study_only = boolish(message.get("wavecount_study_only"))

    if not safe_to_send:
        reasons.append("unsafe_message")
    if no_action_status != "pass":
        reasons.append("blocked_by_no_action")
    if original_send_real:
        reasons.append("send_real_pre_gate_true")
    if delivery_status == "manual_only" and not options.manual_confirmation:
        reasons.append("manual_only_requires_confirmation")
    if delivery_status not in {"preview_allowed", "event_allowed"}:
        reasons.append("delivery_not_preview_allowed")
    if condition_status == "no_condition" and delivery_status not in {"preview_allowed", "event_allowed"}:
        reasons.append("no_condition")
    if message_type not in options.allowed_message_types:
        reasons.append("message_type_not_allowed")
    if severity not in options.allowed_severities:
        reasons.append("severity_not_allowed")
    if contains_wavecount and (not options.allow_wavecount_study or not wavecount_study_only):
        reasons.append("wavecount_not_allowed")

    reasons = dedupe_preserve_order(reasons)
    decision = "blocked_to_send" if reasons else "allowed_to_send"
    primary_reason = reasons[0] if reasons else "allowed_in_gate_dry_run"

    return {
        "message_id": message_id,
        "message_type": message_type,
        "severity": severity,
        "gate_decision": decision,
        "gate_reason": primary_reason,
        "gate_reasons": "|".join(reasons) if reasons else "allowed_in_gate_dry_run",
        "safe_to_send": safe_to_send,
        "no_action_audit_status": no_action_status,
        "delivery_status": delivery_status,
        "condition_status": condition_status,
        "condition_reason": delivery.get("condition_reason", message.get("condition_reason", "")),
        "contains_wavecount": contains_wavecount,
        "wavecount_study_only": wavecount_study_only,
        "original_send_real": original_send_real,
        "send_real_requested": options.send_real,
        "send_real_executed": False,
        "telegram_connected": False,
        "telegram_real_message_sent": False,
        "sender_gate_only": options.sender_gate_only,
        "source_artifacts": message.get("source_artifacts", ""),
        "evaluated_at": evaluated_at,
        "title": message.get("title", ""),
        "body": message.get("body", ""),
        "dedup_key": message.get("dedup_key", delivery.get("dedup_key", "")),
        "cooldown_minutes": message.get("cooldown_minutes", delivery.get("cooldown_minutes", "")),
    }


def build_gate_config_audit(options: TelegramSenderGateOptions) -> list[dict[str, Any]]:
    rows = [
        ("dry_run", options.dry_run, "Gate evaluation only."),
        ("telegram_enabled", options.telegram_enabled, "Global switch; false blocks all by default."),
        ("telegram_mode", options.telegram_mode, "Only informational_only is allowed."),
        ("allow_real_send", options.allow_real_send, "Future real send allowance; false blocks all."),
        ("send_real", options.send_real, "Explicit future CLI intent; still no send in this phase."),
        ("manual_confirmation", options.manual_confirmation, "Human confirmation gate."),
        ("allow_wavecount_study", options.allow_wavecount_study, "Allows WaveCount only as study-only."),
        ("allowed_message_types", "|".join(options.allowed_message_types), "Message type allowlist."),
        ("allowed_severities", "|".join(options.allowed_severities), "Severity allowlist."),
        ("check_external_secrets", options.check_external_secrets, "Checks presence only; never prints values."),
        ("sender_gate_only", options.sender_gate_only, "This phase never sends messages."),
    ]
    return [
        {
            "config_key": key,
            "config_value": value,
            "safe_default": key
            in {
                "dry_run",
                "telegram_enabled",
                "allow_real_send",
                "send_real",
                "manual_confirmation",
                "allow_wavecount_study",
                "check_external_secrets",
                "sender_gate_only",
            },
            "effect": effect,
        }
        for key, value, effect in rows
    ]


def build_secret_policy_audit(secret_audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in secret_audit:
        if row.get("category") not in {"repo_secret_file_candidate", "repo_secret_template"}:
            continue
        if row.get("category") == "repo_secret_template":
            decision = "allowed_template"
            recommendation = "Keep template free of real values."
        elif not row.get("present"):
            decision = "not_present"
            recommendation = "No action."
        elif row.get("tracked_by_git"):
            decision = "block_tracked_secret"
            recommendation = "Remove secret from version control before sender real."
        elif row.get("ignored_by_git"):
            decision = "allow_local_ignored_secret_warning"
            recommendation = "Keep local file ignored; sender still requires environment_only checks."
        else:
            decision = "block_unignored_local_secret"
            recommendation = "Add ignore rule or move secret outside repo before sender real."
        rows.append(
            {
                "candidate": row.get("candidate", ""),
                "category": row.get("category", ""),
                "present": row.get("present", False),
                "tracked_by_git": row.get("tracked_by_git", False),
                "ignored_by_git": row.get("ignored_by_git", False),
                "value_opened": False,
                "value_printed": False,
                "value_stored": False,
                "policy_decision": decision,
                "blocks_gate": row.get("blocks_gate", False),
                "recommendation": recommendation,
            }
        )
    return rows


def build_gate_policy_options() -> list[dict[str, Any]]:
    return [
        {
            "option_id": "block_any_secret_file_presence",
            "description": "Bloquear por cualquier fichero candidato local, aunque este ignorado.",
            "pros": "Maxima cautela.",
            "cons": "Bloquea el flujo normal de desarrollo con .env local ignorado.",
            "decision": "rejected_too_strict",
        },
        {
            "option_id": "block_tracked_or_unignored_secret_files",
            "description": "Bloquear secretos trackeados o locales no ignorados; permitir .env local ignorado como warning.",
            "pros": "Fail-closed ante exposicion real sin penalizar secretos locales ignorados.",
            "cons": "Requiere mantener .gitignore correcto.",
            "decision": "selected",
        },
        {
            "option_id": "allow_all_local_secret_files",
            "description": "Permitir cualquier fichero local y confiar solo en environment_only.",
            "pros": "Menos bloqueos.",
            "cons": "Demasiado permisivo; un fichero no ignorado podria filtrarse.",
            "decision": "rejected_too_permissive",
        },
        {
            "option_id": "require_environment_only_for_real_send",
            "description": "Aunque haya .env local ignorado, sender real futuro solo puede leer secretos desde entorno externo.",
            "pros": "Evita dependencia directa de ficheros del repo.",
            "cons": "Exige configuracion manual externa.",
            "decision": "selected",
        },
    ]


def build_no_action_gate_audit(
    gate_rows: list[dict[str, Any]],
    no_action_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gate in gate_rows:
        source = no_action_by_id.get(gate["message_id"], {})
        rows.append(
            {
                "message_id": gate["message_id"],
                "message_type": gate["message_type"],
                "safe_to_send": gate["safe_to_send"],
                "no_action_audit_status": gate["no_action_audit_status"],
                "blocked_patterns": source.get("blocked_patterns", ""),
                "gate_accepted_no_action": gate["safe_to_send"] and gate["no_action_audit_status"] == "pass",
                "gate_decision": gate["gate_decision"],
                "gate_reason": gate["gate_reason"],
            }
        )
    return rows


def build_wavecount_gate_audit(
    gate_rows: list[dict[str, Any]],
    options: TelegramSenderGateOptions,
) -> list[dict[str, Any]]:
    return [
        {
            "message_id": gate["message_id"],
            "message_type": gate["message_type"],
            "contains_wavecount": gate["contains_wavecount"],
            "wavecount_study_only": gate["wavecount_study_only"],
            "allow_wavecount_study": options.allow_wavecount_study,
            "wavecount_used_as_filter": False,
            "gate_decision": gate["gate_decision"],
            "gate_reason": gate["gate_reason"],
            "notes": "WaveCount allowed only when preview_allowed and explicit study-only permission pass.",
        }
        for gate in gate_rows
        if gate["contains_wavecount"] or gate["message_type"] == "wavecount_study_digest"
    ]


def build_issues_or_risks(
    artifact_status: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    global_blocks: list[str],
    options: TelegramSenderGateOptions,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in artifact_status:
        if artifact["blocks_gate"]:
            rows.append(
                {
                    "issue_id": f"missing_{artifact['artifact_id']}",
                    "severity": "blocker",
                    "area": "artifacts",
                    "description": f"Required sender gate input is missing or empty: {artifact['path']}",
                    "recommended_action": "Regenerate Telegram informational dry-run and sender gate design artifacts.",
                }
            )
    for secret in secret_audit:
        if secret["blocks_gate"]:
            rows.append(
                {
                    "issue_id": secret["check_id"],
                    "severity": "blocker",
                    "area": "secrets",
                    "description": f"Secret presence check blocks gate: {secret['status']}",
                    "recommended_action": "Keep secrets external and do not store or print values.",
                }
            )
    if global_blocks:
        rows.append(
            {
                "issue_id": "global_gate_blocks_active",
                "severity": "info",
                "area": "gate",
                "description": f"Global blocks active: {'|'.join(global_blocks)}",
                "recommended_action": "Expected if source run or config is not ready for future real sender.",
            }
        )
    if not options.telegram_enabled:
        rows.append(
            {
                "issue_id": "telegram_disabled_by_default",
                "severity": "info",
                "area": "config",
                "description": "Default run blocks all messages because telegram_enabled=false.",
                "recommended_action": "Keep this default until a separate sender review approves external configuration.",
            }
        )
    if any(row["gate_decision"] == "allowed_to_send" for row in gate_rows):
        rows.append(
            {
                "issue_id": "gate_has_allowed_candidates",
                "severity": "info",
                "area": "gate",
                "description": "Some messages satisfy sender gate conditions in simulation, but no message was sent.",
                "recommended_action": "Review allowed_to_send.csv before implementing any sender.",
            }
        )
    if not rows:
        rows.append(
            {
                "issue_id": "none_blocking",
                "severity": "info",
                "area": "closure",
                "description": "No blocking implementation issue detected.",
                "recommended_action": "Review sender gate outputs before any future sender implementation.",
            }
        )
    return rows


def decide_result(artifact_status: list[dict[str, Any]], secret_audit: list[dict[str, Any]]) -> str:
    if any(row["blocks_gate"] for row in artifact_status):
        return "telegram_sender_gate_v1_needs_minor_fix"
    if any(row["check_id"] == "repo_secret_file_presence" and row["blocks_gate"] for row in secret_audit):
        return "telegram_sender_gate_v1_blocked_by_safety"
    return "telegram_sender_gate_v1_ready_for_sender_dry_run_review"


def build_run_meta(
    *,
    generated_at: str,
    decision: str,
    options: TelegramSenderGateOptions,
    messages: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    artifact_status: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed_count = sum(1 for row in gate_rows if row["gate_decision"] == "allowed_to_send")
    blocked_count = sum(1 for row in gate_rows if row["gate_decision"] == "blocked_to_send")
    return {
        "phase": "telegram_sender_gate_v1",
        "generated_at": generated_at,
        "decision": decision,
        "method_version": METHOD_VERSION,
        "sender_gate_implemented": True,
        "sender_gate_only": True,
        "telegram_connected": False,
        "telegram_real_messages_sent": 0,
        "telegram_tokens_printed": False,
        "telegram_chat_ids_printed": False,
        "telegram_tokens_stored": False,
        "telegram_chat_ids_stored": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "bot_implemented": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
        "wavecount_used_as_filter": False,
        "dry_run": options.dry_run,
        "telegram_enabled": options.telegram_enabled,
        "allow_real_send": options.allow_real_send,
        "send_real_requested": options.send_real,
        "manual_confirmation": options.manual_confirmation,
        "allow_wavecount_study": options.allow_wavecount_study,
        "check_external_secrets": options.check_external_secrets,
        "input_message_count": len(messages),
        "allowed_to_send_count": allowed_count,
        "blocked_to_send_count": blocked_count,
        "gate_decision_distribution": dict(Counter(row["gate_decision"] for row in gate_rows)),
        "gate_reason_distribution": dict(Counter(row["gate_reason"] for row in gate_rows)),
        "artifact_status_distribution": dict(Counter(row["status"] for row in artifact_status)),
        "next_recommended_phase": "telegram_sender_gate_v1_review_before_sender_real",
    }


def write_outputs(
    *,
    config: TelegramSenderGateConfig,
    allowed: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    config_audit: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    secret_policy_audit: list[dict[str, Any]],
    gate_policy_options: list[dict[str, Any]],
    no_action_gate: list[dict[str, Any]],
    wavecount_gate: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(config.output_dir / "allowed_to_send.csv", allowed, GATE_DECISION_FIELDS)
    write_csv(config.output_dir / "blocked_to_send.csv", blocked, GATE_DECISION_FIELDS)
    write_csv(config.output_dir / "gate_decision_audit.csv", gate_rows, GATE_DECISION_FIELDS)
    write_csv(config.output_dir / "gate_config_audit.csv", config_audit)
    write_csv(config.output_dir / "secret_presence_audit.csv", secret_audit)
    write_csv(config.output_dir / "secret_policy_audit.csv", secret_policy_audit)
    write_csv(config.output_dir / "gate_policy_options.csv", gate_policy_options)
    write_csv(config.output_dir / "no_action_gate_audit.csv", no_action_gate)
    write_csv(config.output_dir / "wavecount_gate_audit.csv", wavecount_gate)
    write_csv(config.output_dir / "issues_or_risks.csv", issues)
    (config.output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "allowed_to_send": config.output_dir / "allowed_to_send.csv",
        "blocked_to_send": config.output_dir / "blocked_to_send.csv",
        "gate_decision_audit": config.output_dir / "gate_decision_audit.csv",
        "gate_config_audit": config.output_dir / "gate_config_audit.csv",
        "secret_presence_audit": config.output_dir / "secret_presence_audit.csv",
        "secret_policy_audit": config.output_dir / "secret_policy_audit.csv",
        "gate_policy_options": config.output_dir / "gate_policy_options.csv",
        "no_action_gate_audit": config.output_dir / "no_action_gate_audit.csv",
        "wavecount_gate_audit": config.output_dir / "wavecount_gate_audit.csv",
        "issues_or_risks": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }


def write_docs(
    config: TelegramSenderGateConfig,
    allowed: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> None:
    allowed_types = sorted({row["message_type"] for row in allowed})
    blocked_reasons = dict(Counter(row["gate_reason"] for row in blocked))
    text = f"""# Telegram Sender Gate V1

Fecha: {run_meta['generated_at']}

Decision: `{run_meta['decision']}`.

## Resumen

Se implementa `telegram_sender_gate_v1` como puerta fail-closed previa a
cualquier envio real por Telegram. El modulo evalua mensajes informativos ya
renderizados, cruza delivery policy, auditoria no-action, configuracion segura,
secretos externos opcionales y limites de WaveCount, y genera listas
`allowed_to_send` / `blocked_to_send`.

Esta fase no envia nada: `telegram_connected=false`,
`telegram_real_messages_sent=0`, `send_real_executed=false` y
`sender_gate_only=true`.

Frase canonica para memoria: Telegram queda como canal informativo y de
observabilidad del bot demo; no es consola, no confirma ordenes, no ejecuta
operaciones y no habilita live trading.

## Modulo Y CLI

- Modulo: `trading_center/telegram_sender_gate.py`
- CLI:

```powershell
python -m trading_center.telegram_sender_gate --dry-run --output-dir artifacts/tfg/telegram_sender_gate_v1_2026-05-29
```

Por defecto `telegram_enabled=false`, `allow_real_send=false`,
`send_real=false` y `manual_confirmation=false`; por tanto, el run normal
bloquea todos los mensajes.

## Resultado Del Run Actual

- Mensajes evaluados: {len(gate_rows)}
- Permitidos por el gate: {len(allowed)}
- Bloqueados por el gate: {len(blocked)}
- Tipos permitidos en esta simulacion: {', '.join(allowed_types) if allowed_types else 'none'}
- Razones principales de bloqueo: {format_counts(blocked_reasons)}

## Gestion De Secretos

El gate no pide tokens, no crea `.env`, no guarda chat IDs y no imprime valores
de variables de entorno. Si se activa `--check-external-secrets`, solo se
registra presencia booleana de `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.

{bullet_list([f"{row['check_id']}: {row['status']}" for row in secret_audit])}

Politica aplicada: los ficheros candidatos trackeados o locales no ignorados
bloquean el gate. Un `.env` local ignorado se audita como warning, pero no
bloquea por si solo; un sender real futuro seguiria exigiendo secretos externos
por entorno y confirmacion explicita.

## Seguridad

- No hay import de librerias Telegram.
- No hay llamadas de red.
- No hay SQL writes ni DDL.
- No hay bot, MT5, backtests ni senales.
- Solo cruza mensajes informativos con `delivery_status=preview_allowed` o
  `event_allowed` y auditoria no-action en `pass`.
- Cualquier tipo operativo, comando o confirmacion queda bloqueado por tipo,
  wording o ausencia de condicion.
- WaveCount solo puede cruzar el gate si esta explicitamente permitido,
  `delivery_status=preview_allowed` y `wavecount_study_only=true`.

## Outputs

- `allowed_to_send.csv`
- `blocked_to_send.csv`
- `gate_decision_audit.csv`
- `gate_config_audit.csv`
- `secret_presence_audit.csv`
- `no_action_gate_audit.csv`
- `wavecount_gate_audit.csv`
- `issues_or_risks.csv`
- `run_meta.json`

## Estado De Cierre

Para el alcance del TFG, el gate queda cerrado como pieza fail-closed de
validacion previa. Que algunos mensajes satisfagan condiciones en simulacion no
implica envio real ni operacion continua; solo demuestra que el contrato puede
separar mensajes informativos permitidos y bloqueados.

## Uso Posterior

Cualquier uso posterior debe permanecer informativo, pasar por el gate, usar
flags explicitos y secretos externos, y mantenerse fuera de consola Telegram,
confirmacion de ordenes, MT5 live y automatizacion autonoma.
"""
    (config.output_dir / "TELEGRAM_SENDER_GATE_V1.md").write_text(text, encoding="utf-8")
    if "secret_policy_review" in config.output_dir.name:
        (config.output_dir / "TELEGRAM_SENDER_GATE_SECRET_POLICY_REVIEW.md").write_text(text, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(text, encoding="utf-8")
    if "secret_policy_review" in config.output_dir.name:
        (config.doc_path.parent / "TELEGRAM_SENDER_GATE_SECRET_POLICY_REVIEW.md").write_text(text, encoding="utf-8")


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def bullet_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def parse_csv_tuple(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    parsed = tuple(part.strip() for part in value.split(",") if part.strip())
    return parsed or default


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Telegram informational messages through a fail-closed sender gate.")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--design-dir", type=Path, default=DEFAULT_DESIGN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--telegram-enabled", action="store_true", default=False)
    parser.add_argument("--allow-real-send", action="store_true", default=False)
    parser.add_argument("--send-real", action="store_true", default=False)
    parser.add_argument("--manual-confirmation", action="store_true", default=False)
    parser.add_argument("--allow-wavecount-study", action="store_true", default=False)
    parser.add_argument("--allowed-message-types", default=None)
    parser.add_argument("--allowed-severities", default=None)
    parser.add_argument("--check-external-secrets", action="store_true", default=False)
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    config = TelegramSenderGateConfig(
        input_dir=args.input_dir,
        design_dir=args.design_dir,
        output_dir=args.output_dir,
        doc_path=source_root / "docs/TELEGRAM_SENDER_GATE_V1.md",
        repo_root=source_root,
    )
    options = TelegramSenderGateOptions(
        dry_run=True,
        telegram_enabled=args.telegram_enabled,
        allow_real_send=args.allow_real_send,
        send_real=args.send_real,
        manual_confirmation=args.manual_confirmation,
        allow_wavecount_study=args.allow_wavecount_study,
        allowed_message_types=parse_csv_tuple(args.allowed_message_types, DEFAULT_ALLOWED_MESSAGE_TYPES),
        allowed_severities=parse_csv_tuple(args.allowed_severities, DEFAULT_ALLOWED_SEVERITIES),
        check_external_secrets=args.check_external_secrets,
        sender_gate_only=True,
    )
    result = build_telegram_sender_gate(config, options)
    print(
        json.dumps(
            {
                "decision": result.decision,
                "allowed_to_send": len(result.allowed_to_send),
                "blocked_to_send": len(result.blocked_to_send),
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
