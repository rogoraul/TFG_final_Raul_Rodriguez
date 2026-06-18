from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_DIR = REPO_ROOT / "artifacts/tfg/telegram_sender_gate_v1_review_2026-05-29/simulated_enabled_gate"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/telegram_real_sender_v1_2026-05-29"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TELEGRAM_REAL_SENDER_V1.md"

METHOD_VERSION = "telegram_real_sender_v1"

DEFAULT_ALLOWED_MESSAGE_TYPES = (
    "platform_daily_summary",
    "watchlist_status_digest",
    "system_audit_notice",
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
DEFAULT_ALLOWED_SEVERITIES = ("info", "warning", "error")

SECRET_FILE_CANDIDATES = (
    ".env",
    ".env.local",
    "telegram_token.txt",
    "telegram_chat_id.txt",
    "telegram_bot_token.txt",
)
SECRET_TEMPLATE_CANDIDATES = (".env.example",)

BLOCKED_WORDING_PATTERNS = [
    r"\bcomprar\b",
    r"\bvender\b",
    r"\bbuy\b",
    r"\bsell\b",
    r"\bexecute\b",
    r"\bejecutar\b",
    r"\bejecuta(r)?\s+(esta\s+)?orden\b",
    r"\baprobar\b",
    r"\baprobar\s+orden\b",
    r"\bconfirma(r)?\s+(esta\s+)?orden\b",
    r"\bconfirm(ar|acion)\s+operacion\b",
    r"entrada\s+recomendada",
    r"senal\s+de\s+compra",
    r"señal\s+de\s+compra",
    r"senal\s+de\s+venta",
    r"señal\s+de\s+venta",
    r"activar\s+bot",
    r"mt5\s+execute",
]

ATTEMPT_FIELDS = [
    "send_attempt_id",
    "message_id",
    "message_type",
    "severity",
    "gate_decision",
    "pre_send_status",
    "pre_send_reasons",
    "failure_reason",
    "send_real_requested",
    "send_real_executed",
    "telegram_connected",
    "telegram_real_message_sent",
    "telegram_response_status",
    "telegram_message_id_hash",
    "token_printed",
    "chat_id_printed",
    "token_stored",
    "chat_id_stored",
    "safe_to_send",
    "no_action_audit_status",
    "delivery_status",
    "contains_wavecount",
    "wavecount_study_only",
    "dedup_key",
    "cooldown_minutes",
    "source_artifacts",
    "attempted_at",
]


@dataclass(frozen=True)
class TelegramRealSenderConfig:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    repo_root: Path = REPO_ROOT


@dataclass(frozen=True)
class TelegramRealSenderOptions:
    telegram_enabled: bool = False
    telegram_mode: str = "informational_only"
    allow_real_send: bool = False
    send_real: bool = False
    manual_confirmation: bool = False
    allow_wavecount_study: bool = False
    allowed_message_types: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALLOWED_MESSAGE_TYPES)
    allowed_severities: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALLOWED_SEVERITIES)
    max_messages: int = 3
    check_external_secrets: bool = False
    timeout_seconds: int = 10


@dataclass(frozen=True)
class TelegramTransportResult:
    success: bool
    response_status: str
    telegram_message_id_hash: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class TelegramRealSenderResult:
    decision: str
    send_attempts: list[dict[str, Any]]
    sent_messages_audit: list[dict[str, Any]]
    blocked_before_send: list[dict[str, Any]]
    telegram_response_audit: list[dict[str, Any]]
    secret_handling_audit: list[dict[str, Any]]
    rate_limit_audit: list[dict[str, Any]]
    issues_or_risks: list[dict[str, Any]]
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


Transport = Callable[[str, str, str, int], TelegramTransportResult]


def build_telegram_real_sender(
    config: TelegramRealSenderConfig | None = None,
    options: TelegramRealSenderOptions | None = None,
    *,
    transport: Transport | None = None,
) -> TelegramRealSenderResult:
    config = config or TelegramRealSenderConfig()
    options = options or TelegramRealSenderOptions()
    generated_at = utc_now()
    transport = transport or send_telegram_message

    input_data = read_input_data(config)
    source_audit = build_source_artifact_audit(config, input_data)
    secret_audit = build_secret_handling_audit(config, options)
    global_blocks = build_global_blocks(input_data, source_audit, secret_audit, options)
    rate_audit = build_rate_limit_audit(input_data["allowed_rows"], options)
    rate_by_id = {row["message_id"]: row for row in rate_audit}

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "") if options.send_real else ""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "") if options.send_real else ""
    attempts: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []

    for index, message in enumerate(input_data["allowed_rows"], start=1):
        attempt = evaluate_pre_send(
            message=message,
            options=options,
            global_blocks=global_blocks,
            rate_row=rate_by_id.get(str(message.get("message_id", "")), {}),
            attempted_at=generated_at,
            index=index,
        )
        if attempt["pre_send_status"] == "ready_to_send":
            text = build_message_text(message)
            result = transport(token, chat_id, text, options.timeout_seconds)
            attempt["send_real_executed"] = result.success
            attempt["telegram_connected"] = result.success
            attempt["telegram_real_message_sent"] = result.success
            attempt["telegram_response_status"] = result.response_status
            attempt["telegram_message_id_hash"] = result.telegram_message_id_hash
            if result.success:
                attempt["pre_send_status"] = "sent"
            else:
                attempt["pre_send_status"] = "failed_transport"
                attempt["failure_reason"] = result.failure_reason or result.response_status
        attempts.append(attempt)
        responses.append(build_response_audit_row(attempt))

    sent = [row for row in attempts if boolish(row["send_real_executed"])]
    blocked = [row for row in attempts if row["pre_send_status"] not in {"sent"}]
    issues = build_issues_or_risks(source_audit, secret_audit, attempts, global_blocks, options)
    decision = decide_result(attempts, source_audit)
    run_meta = build_run_meta(
        generated_at=generated_at,
        decision=decision,
        options=options,
        source_audit=source_audit,
        attempts=attempts,
    )
    written = write_outputs(
        config=config,
        attempts=attempts,
        sent=sent,
        blocked=blocked,
        responses=responses,
        secret_audit=secret_audit,
        rate_audit=rate_audit,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, attempts, sent, blocked, secret_audit, issues, run_meta)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "TELEGRAM_REAL_SENDER_V1.md"
    return TelegramRealSenderResult(
        decision=decision,
        send_attempts=attempts,
        sent_messages_audit=sent,
        blocked_before_send=blocked,
        telegram_response_audit=responses,
        secret_handling_audit=secret_audit,
        rate_limit_audit=rate_audit,
        issues_or_risks=issues,
        run_meta=run_meta,
        written_files=written,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_input_data(config: TelegramRealSenderConfig) -> dict[str, Any]:
    return {
        "allowed_rows": read_csv(config.input_dir / "allowed_to_send.csv"),
        "blocked_rows": read_csv(config.input_dir / "blocked_to_send.csv"),
        "gate_decision_rows": read_csv(config.input_dir / "gate_decision_audit.csv"),
        "gate_config_rows": read_csv(config.input_dir / "gate_config_audit.csv"),
        "secret_policy_rows": read_csv(config.input_dir / "secret_policy_audit.csv"),
        "run_meta": read_json(config.input_dir / "run_meta.json"),
    }


def build_source_artifact_audit(config: TelegramRealSenderConfig, input_data: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = [
        ("allowed_to_send", config.input_dir / "allowed_to_send.csv", len(input_data["allowed_rows"]), True),
        ("blocked_to_send", config.input_dir / "blocked_to_send.csv", len(input_data["blocked_rows"]), False),
        ("gate_decision_audit", config.input_dir / "gate_decision_audit.csv", len(input_data["gate_decision_rows"]), True),
        ("gate_config_audit", config.input_dir / "gate_config_audit.csv", len(input_data["gate_config_rows"]), True),
        ("secret_policy_audit", config.input_dir / "secret_policy_audit.csv", len(input_data["secret_policy_rows"]), True),
        ("gate_run_meta", config.input_dir / "run_meta.json", 1 if input_data["run_meta"] else 0, True),
    ]
    return [
        {
            "artifact_id": artifact_id,
            "path": str(path),
            "exists": path.exists(),
            "rows": rows,
            "required": required,
            "status": "available" if path.exists() and (rows > 0 or not required) else "missing_or_empty",
            "blocks_sender": required and not (path.exists() and rows > 0),
        }
        for artifact_id, path, rows, required in artifacts
    ]


def build_secret_handling_audit(
    config: TelegramRealSenderConfig,
    options: TelegramRealSenderOptions,
) -> list[dict[str, Any]]:
    check_secrets = options.check_external_secrets or options.send_real
    token_present = bool(os.environ.get("TELEGRAM_BOT_TOKEN")) if check_secrets else False
    chat_id_present = bool(os.environ.get("TELEGRAM_CHAT_ID")) if check_secrets else False
    rows = [
        {
            "check_id": "external_telegram_bot_token",
            "candidate": "TELEGRAM_BOT_TOKEN",
            "category": "external_environment",
            "checked": check_secrets,
            "present": token_present,
            "value_opened": False,
            "value_printed": False,
            "value_stored": False,
            "source_policy": "environment_only",
            "status": "present" if token_present else "not_checked" if not check_secrets else "missing",
            "blocks_sender": check_secrets and not token_present,
        },
        {
            "check_id": "external_telegram_chat_id",
            "candidate": "TELEGRAM_CHAT_ID",
            "category": "external_environment",
            "checked": check_secrets,
            "present": chat_id_present,
            "value_opened": False,
            "value_printed": False,
            "value_stored": False,
            "source_policy": "environment_only",
            "status": "present" if chat_id_present else "not_checked" if not check_secrets else "missing",
            "blocks_sender": check_secrets and not chat_id_present,
        },
    ]
    rows.extend(build_secret_file_row(config.repo_root, candidate) for candidate in SECRET_FILE_CANDIDATES)
    rows.extend(build_secret_template_row(config.repo_root, candidate) for candidate in SECRET_TEMPLATE_CANDIDATES)
    return rows


def build_secret_file_row(repo_root: Path, candidate: str) -> dict[str, Any]:
    path = repo_root / candidate
    exists = path.exists()
    tracked = git_path_is_tracked(repo_root, candidate) if exists else False
    ignored = git_path_is_ignored(repo_root, candidate) if exists else False
    if not exists:
        status = "not_found"
        blocks = False
    elif tracked:
        status = "tracked_secret_file_present"
        blocks = True
    elif ignored:
        status = "local_ignored_secret_file_present"
        blocks = False
    else:
        status = "local_unignored_secret_file_present"
        blocks = True
    return {
        "check_id": f"repo_secret_file:{candidate}",
        "candidate": candidate,
        "category": "repo_secret_file_candidate",
        "checked": True,
        "present": exists,
        "tracked_by_git": tracked,
        "ignored_by_git": ignored,
        "local_only": exists and not tracked,
        "value_opened": False,
        "value_printed": False,
        "value_stored": False,
        "source_policy": "not_a_sender_source",
        "status": status,
        "blocks_sender": blocks,
    }


def build_secret_template_row(repo_root: Path, candidate: str) -> dict[str, Any]:
    exists = (repo_root / candidate).exists()
    return {
        "check_id": f"repo_secret_template:{candidate}",
        "candidate": candidate,
        "category": "repo_secret_template",
        "checked": True,
        "present": exists,
        "tracked_by_git": git_path_is_tracked(repo_root, candidate) if exists else False,
        "ignored_by_git": git_path_is_ignored(repo_root, candidate) if exists else False,
        "local_only": exists and not git_path_is_tracked(repo_root, candidate),
        "value_opened": False,
        "value_printed": False,
        "value_stored": False,
        "source_policy": "safe_template_only",
        "status": "template_present" if exists else "not_found",
        "blocks_sender": False,
    }


def build_global_blocks(
    input_data: dict[str, Any],
    source_audit: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    options: TelegramRealSenderOptions,
) -> list[str]:
    blocks: list[str] = []
    if any(row["blocks_sender"] for row in source_audit):
        blocks.append("required_gate_artifact_missing")
    if any(row["category"] == "repo_secret_file_candidate" and row["blocks_sender"] for row in secret_audit):
        blocks.append("secret_file_blocking_policy")
    if any(row["check_id"] == "external_telegram_bot_token" and row["blocks_sender"] for row in secret_audit):
        blocks.append("missing_external_token")
    if any(row["check_id"] == "external_telegram_chat_id" and row["blocks_sender"] for row in secret_audit):
        blocks.append("missing_external_chat_id")

    source_meta = input_data.get("run_meta", {})
    if not boolish(source_meta.get("sender_gate_only")):
        blocks.append("source_not_sender_gate_only")
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

    if not options.telegram_enabled:
        blocks.append("telegram_disabled")
    if options.telegram_mode != "informational_only":
        blocks.append("wrong_mode")
    if not options.allow_real_send:
        blocks.append("real_send_not_allowed")
    if not options.send_real:
        blocks.append("send_real_flag_missing")
    if not options.manual_confirmation:
        blocks.append("manual_confirmation_missing")
    return dedupe_preserve_order(blocks)


def build_rate_limit_audit(rows: list[dict[str, str]], options: TelegramRealSenderOptions) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        dedup_key = str(row.get("dedup_key", ""))
        duplicate = bool(dedup_key and dedup_key in seen)
        if dedup_key:
            seen.add(dedup_key)
        within_cap = index <= options.max_messages
        result.append(
            {
                "message_id": row.get("message_id", ""),
                "message_type": row.get("message_type", ""),
                "dedup_key": dedup_key,
                "row_index": index,
                "max_messages_per_run": options.max_messages,
                "within_max_messages": within_cap,
                "duplicate_dedup_key": duplicate,
                "cooldown_minutes": row.get("cooldown_minutes", ""),
                "rate_limit_status": "pass" if within_cap and not duplicate else "blocked",
                "rate_limit_reason": ""
                if within_cap and not duplicate
                else "max_messages_exceeded"
                if not within_cap
                else "duplicate_dedup_key",
            }
        )
    return result


def evaluate_pre_send(
    *,
    message: dict[str, Any],
    options: TelegramRealSenderOptions,
    global_blocks: list[str],
    rate_row: dict[str, Any],
    attempted_at: str,
    index: int,
) -> dict[str, Any]:
    reasons: list[str] = list(global_blocks)
    title = str(message.get("title", "")).strip()
    body = str(message.get("body", "")).strip()
    message_type = str(message.get("message_type", ""))
    severity = str(message.get("severity", ""))
    delivery_status = str(message.get("delivery_status", ""))
    no_action_status = str(message.get("no_action_audit_status", ""))
    safe_to_send = boolish(message.get("safe_to_send"))
    contains_wavecount = boolish(message.get("contains_wavecount"))
    wavecount_study_only = boolish(message.get("wavecount_study_only"))

    if str(message.get("gate_decision", "")) != "allowed_to_send":
        reasons.append("message_not_allowed_by_gate")
    if boolish(message.get("send_real_executed")):
        reasons.append("send_real_already_executed")
    if boolish(message.get("telegram_connected")) or boolish(message.get("telegram_real_message_sent")):
        reasons.append("message_already_connected_or_sent")
    if not boolish(message.get("sender_gate_only")):
        reasons.append("message_not_sender_gate_only")
    if not safe_to_send:
        reasons.append("unsafe_message")
    if no_action_status != "pass":
        reasons.append("blocked_by_no_action")
    if delivery_status not in {"preview_allowed", "event_allowed"}:
        reasons.append("delivery_not_preview_allowed")
    if message_type not in options.allowed_message_types:
        reasons.append("message_type_not_allowed")
    if severity not in options.allowed_severities:
        reasons.append("severity_not_allowed")
    if contains_wavecount and (not options.allow_wavecount_study or not wavecount_study_only):
        reasons.append("wavecount_not_allowed")
    if not title or not body:
        reasons.append("message_content_missing")
    blocked_patterns = find_blocked_wording(f"{title}\n{body}")
    if blocked_patterns:
        reasons.append("operational_wording_detected")
    if str(rate_row.get("rate_limit_status", "")) == "blocked":
        reasons.append(str(rate_row.get("rate_limit_reason", "rate_limit_blocked")))

    reasons = dedupe_preserve_order(reasons)
    status = "blocked_before_send" if reasons else "ready_to_send"
    return {
        "send_attempt_id": f"send_attempt_{index:03d}_{message.get('message_id', '')}",
        "message_id": message.get("message_id", ""),
        "message_type": message_type,
        "severity": severity,
        "gate_decision": message.get("gate_decision", ""),
        "pre_send_status": status,
        "pre_send_reasons": "|".join(reasons) if reasons else "all_pre_send_checks_passed",
        "failure_reason": reasons[0] if reasons else "",
        "send_real_requested": options.send_real,
        "send_real_executed": False,
        "telegram_connected": False,
        "telegram_real_message_sent": False,
        "telegram_response_status": "not_attempted" if reasons else "pending_transport",
        "telegram_message_id_hash": "",
        "token_printed": False,
        "chat_id_printed": False,
        "token_stored": False,
        "chat_id_stored": False,
        "safe_to_send": safe_to_send,
        "no_action_audit_status": no_action_status,
        "delivery_status": delivery_status,
        "contains_wavecount": contains_wavecount,
        "wavecount_study_only": wavecount_study_only,
        "dedup_key": message.get("dedup_key", ""),
        "cooldown_minutes": message.get("cooldown_minutes", ""),
        "source_artifacts": message.get("source_artifacts", ""),
        "attempted_at": attempted_at,
        "title": title,
        "body": body,
        "blocked_wording_patterns": "|".join(blocked_patterns),
    }


def send_telegram_message(token: str, chat_id: str, text: str, timeout_seconds: int) -> TelegramTransportResult:
    import urllib.error
    import urllib.request

    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        return TelegramTransportResult(False, f"telegram_http_error_{exc.code}", failure_reason="telegram_http_error")
    except (urllib.error.URLError, TimeoutError):
        return TelegramTransportResult(False, "telegram_network_error", failure_reason="telegram_network_error")
    except (json.JSONDecodeError, OSError, ValueError):
        return TelegramTransportResult(False, "telegram_unexpected_response", failure_reason="telegram_unexpected_response")

    if not data.get("ok"):
        return TelegramTransportResult(False, "telegram_api_rejected", failure_reason="telegram_api_rejected")
    message_id = str(data.get("result", {}).get("message_id", ""))
    return TelegramTransportResult(True, "telegram_api_ok", hash_value(message_id))


def build_message_text(message: dict[str, Any]) -> str:
    title = str(message.get("title", "")).strip()
    body = str(message.get("body", "")).strip()
    text = f"{title}\n\n{body}".strip()
    if len(text) > 3900:
        return text[:3890].rstrip() + "\n[truncated]"
    return text


def build_response_audit_row(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "send_attempt_id": attempt["send_attempt_id"],
        "message_id": attempt["message_id"],
        "message_type": attempt["message_type"],
        "telegram_connected": attempt["telegram_connected"],
        "send_real_executed": attempt["send_real_executed"],
        "telegram_response_status": attempt["telegram_response_status"],
        "telegram_message_id_hash": attempt["telegram_message_id_hash"],
        "token_printed": False,
        "chat_id_printed": False,
        "token_stored": False,
        "chat_id_stored": False,
        "failure_reason": attempt["failure_reason"],
    }


def build_issues_or_risks(
    source_audit: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    global_blocks: list[str],
    options: TelegramRealSenderOptions,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in source_audit:
        if artifact["blocks_sender"]:
            rows.append(
                {
                    "issue_id": f"missing_{artifact['artifact_id']}",
                    "severity": "blocker",
                    "area": "input",
                    "description": f"Required sender input missing or empty: {artifact['path']}",
                    "recommended_action": "Regenerate telegram_sender_gate_v1 outputs.",
                }
            )
    for secret in secret_audit:
        if secret["blocks_sender"]:
            rows.append(
                {
                    "issue_id": secret["check_id"],
                    "severity": "blocker",
                    "area": "secrets",
                    "description": f"Secret policy blocks sender: {secret['status']}",
                    "recommended_action": "Use external environment secrets and keep repo secret files ignored/untracked.",
                }
            )
    if global_blocks:
        rows.append(
            {
                "issue_id": "global_sender_blocks_active",
                "severity": "info",
                "area": "sender",
                "description": f"Global blocks active: {'|'.join(global_blocks)}",
                "recommended_action": "Expected for fail-closed/default runs.",
            }
        )
    if not options.send_real:
        rows.append(
            {
                "issue_id": "real_send_not_requested",
                "severity": "info",
                "area": "config",
                "description": "No real send requested in this run.",
                "recommended_action": "Keep this default unless user explicitly enables real sender.",
            }
        )
    if any(row["pre_send_status"] == "sent" for row in attempts):
        rows.append(
            {
                "issue_id": "real_messages_sent",
                "severity": "warning",
                "area": "transport",
                "description": "At least one real Telegram message was sent.",
                "recommended_action": "Review sent_messages_audit and Telegram response audit.",
            }
        )
    if not rows:
        rows.append(
            {
                "issue_id": "none_blocking",
                "severity": "info",
                "area": "closure",
                "description": "No blocking issue detected.",
                "recommended_action": "Review send_attempts before any repeated run.",
            }
        )
    return rows


def decide_result(attempts: list[dict[str, Any]], source_audit: list[dict[str, Any]]) -> str:
    if any(row["blocks_sender"] for row in source_audit):
        return "telegram_real_sender_v1_blocked_missing_gate_artifacts"
    if any(row["pre_send_status"] == "sent" for row in attempts):
        return "telegram_real_sender_v1_real_send_executed"
    if any(row["pre_send_status"] == "failed_transport" for row in attempts):
        return "telegram_real_sender_v1_transport_failed"
    return "telegram_real_sender_v1_implemented_fail_closed"


def build_run_meta(
    *,
    generated_at: str,
    decision: str,
    options: TelegramRealSenderOptions,
    source_audit: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    sent_count = sum(1 for row in attempts if boolish(row["send_real_executed"]))
    connected = sent_count > 0
    return {
        "phase": "telegram_real_sender_v1",
        "generated_at": generated_at,
        "decision": decision,
        "method_version": METHOD_VERSION,
        "real_sender_implemented": True,
        "real_sender_design_source": "docs/TELEGRAM_REAL_SENDER_DESIGN_V1.md",
        "telegram_connected": connected,
        "telegram_real_messages_sent": sent_count,
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
        "telegram_enabled": options.telegram_enabled,
        "allow_real_send": options.allow_real_send,
        "send_real_requested": options.send_real,
        "manual_confirmation": options.manual_confirmation,
        "allow_wavecount_study": options.allow_wavecount_study,
        "max_messages": options.max_messages,
        "input_artifact_status_distribution": dict(Counter(row["status"] for row in source_audit)),
        "attempt_count": len(attempts),
        "sent_count": sent_count,
        "blocked_before_send_count": sum(1 for row in attempts if row["pre_send_status"] == "blocked_before_send"),
        "failed_transport_count": sum(1 for row in attempts if row["pre_send_status"] == "failed_transport"),
        "pre_send_status_distribution": dict(Counter(row["pre_send_status"] for row in attempts)),
        "failure_reason_distribution": dict(Counter(row["failure_reason"] for row in attempts if row["failure_reason"])),
        "next_recommended_phase": "review_telegram_real_sender_v1_before_any_manual_real_send",
    }


def write_outputs(
    *,
    config: TelegramRealSenderConfig,
    attempts: list[dict[str, Any]],
    sent: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    rate_audit: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(config.output_dir / "send_attempts.csv", attempts, ATTEMPT_FIELDS)
    (config.output_dir / "send_attempts.json").write_text(json.dumps(attempts, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(config.output_dir / "sent_messages_audit.csv", sent, ATTEMPT_FIELDS)
    write_csv(config.output_dir / "blocked_before_send.csv", blocked, ATTEMPT_FIELDS)
    write_csv(config.output_dir / "telegram_response_audit.csv", responses)
    write_csv(config.output_dir / "secret_handling_audit.csv", secret_audit)
    write_csv(config.output_dir / "rate_limit_audit.csv", rate_audit)
    write_csv(config.output_dir / "issues_or_risks.csv", issues)
    (config.output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "send_attempts_csv": config.output_dir / "send_attempts.csv",
        "send_attempts_json": config.output_dir / "send_attempts.json",
        "sent_messages_audit": config.output_dir / "sent_messages_audit.csv",
        "blocked_before_send": config.output_dir / "blocked_before_send.csv",
        "telegram_response_audit": config.output_dir / "telegram_response_audit.csv",
        "secret_handling_audit": config.output_dir / "secret_handling_audit.csv",
        "rate_limit_audit": config.output_dir / "rate_limit_audit.csv",
        "issues_or_risks": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }


def write_docs(
    config: TelegramRealSenderConfig,
    attempts: list[dict[str, Any]],
    sent: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    secret_audit: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> None:
    sent_types = sorted({row["message_type"] for row in sent})
    blocked_counts = Counter(row["failure_reason"] for row in blocked if row["failure_reason"])
    text = f"""# Telegram Real Sender V1

Fecha: {run_meta['generated_at']}

Decision: `{run_meta['decision']}`.

## Resumen

Se implementa `telegram_real_sender_v1` como sender informativo real con
defaults fail-closed. El modulo consume `allowed_to_send.csv` producido por
`telegram_sender_gate_v1`, revalida seguridad, secretos, rate limits y wording,
y registra intentos de envio.

Frase canonica para memoria: Telegram queda como canal informativo y de
observabilidad del bot demo; no es consola, no confirma ordenes, no ejecuta
operaciones y no habilita live trading.

En el run actual no se envia nada salvo que se hayan activado explicitamente
`--telegram-enabled`, `--allow-real-send`, `--send-real`, confirmacion manual y
secretos externos por entorno.

## Modulo Y CLI

- Modulo: `trading_center/telegram_real_sender.py`
- CLI segura por defecto:

```powershell
python -m trading_center.telegram_real_sender --input-dir artifacts/tfg/telegram_sender_gate_v1_review_2026-05-29/simulated_enabled_gate --output-dir artifacts/tfg/telegram_real_sender_v1_2026-05-29
```

## Resultado Del Run Actual

- Intentos evaluados: {len(attempts)}
- Mensajes enviados: {len(sent)}
- Mensajes bloqueados antes de enviar: {len(blocked)}
- Tipos enviados: {', '.join(sent_types) if sent_types else 'none'}
- Razones principales de bloqueo: {format_counts(dict(blocked_counts))}
- `telegram_connected={str(run_meta['telegram_connected']).lower()}`
- `telegram_real_messages_sent={run_meta['telegram_real_messages_sent']}`

## Seguridad

- Token y chat ID solo pueden venir de entorno externo en ejecucion real.
- No se imprimen ni guardan tokens/chat IDs.
- No se lee `.env` directamente.
- `.env` local ignorado se audita como warning, no como fuente.
- Ficheros candidatos trackeados o locales no ignorados bloquean.
- No hay SQL writes, DDL, bot, MT5, backtests ni senales.
- El sender real solo reutiliza mensajes informativos ya permitidos por el
  gate; no implementa comandos entrantes ni confirmaciones.
- Acepta `delivery_status=preview_allowed` y `event_allowed` cuando el gate ya
  los ha permitido.
- Se permite notificar una orden demo ya auditada, pero se bloquea lenguaje de
  confirmar, ejecutar, aprobar, comprar o vender.
- WaveCount queda bloqueado por defecto y nunca se usa como filtro.

## Secretos Auditados

{bullet_list([f"{row['check_id']}: {row['status']}" for row in secret_audit])}

## Outputs

- `send_attempts.csv`
- `send_attempts.json`
- `sent_messages_audit.csv`
- `blocked_before_send.csv`
- `telegram_response_audit.csv`
- `secret_handling_audit.csv`
- `rate_limit_audit.csv`
- `issues_or_risks.csv`
- `run_meta.json`

## Estado De Cierre

Se ejecuto una prueba real limitada anterior con 1 mensaje informativo de
estado. Para la memoria, esa evidencia se interpreta como validacion controlada
puntual del canal informativo, no como Telegram operativo continuo ni como
consola de trading.

## Uso Posterior

Para el cierre del TFG, `telegram_real_sender_v1` queda como pieza reutilizable
pero no operativa por defecto. Cualquier uso real posterior debe ser manual,
informativo, con flags explicitos y secretos externos. Bot conversacional,
confirmacion de operaciones, consola Telegram, MT5 live y automatizacion
autonoma siguen fuera de alcance.
"""
    (config.output_dir / "TELEGRAM_REAL_SENDER_V1.md").write_text(text, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(text, encoding="utf-8")


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
        return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return None


def find_blocked_wording(text: str) -> list[str]:
    lowered = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return [pattern for pattern in BLOCKED_WORDING_PATTERNS if re.search(pattern, lowered, flags=re.IGNORECASE)]


def hash_value(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


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


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def bullet_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send gate-approved Telegram informational messages with fail-closed defaults.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--telegram-enabled", action="store_true", default=False)
    parser.add_argument("--allow-real-send", action="store_true", default=False)
    parser.add_argument("--send-real", action="store_true", default=False)
    parser.add_argument("--manual-confirmation", action="store_true", default=False)
    parser.add_argument("--allow-wavecount-study", action="store_true", default=False)
    parser.add_argument("--allowed-message-types", default=None)
    parser.add_argument("--allowed-severities", default=None)
    parser.add_argument("--max-messages", type=int, default=3)
    parser.add_argument("--check-external-secrets", action="store_true", default=False)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    config = TelegramRealSenderConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        doc_path=source_root / "docs/TELEGRAM_REAL_SENDER_V1.md",
        repo_root=source_root,
    )
    options = TelegramRealSenderOptions(
        telegram_enabled=args.telegram_enabled,
        allow_real_send=args.allow_real_send,
        send_real=args.send_real,
        manual_confirmation=args.manual_confirmation,
        allow_wavecount_study=args.allow_wavecount_study,
        allowed_message_types=parse_csv_tuple(args.allowed_message_types, DEFAULT_ALLOWED_MESSAGE_TYPES),
        allowed_severities=parse_csv_tuple(args.allowed_severities, DEFAULT_ALLOWED_SEVERITIES),
        max_messages=args.max_messages,
        check_external_secrets=args.check_external_secrets,
        timeout_seconds=args.timeout_seconds,
    )
    result = build_telegram_real_sender(config, options)
    print(
        json.dumps(
            {
                "decision": result.decision,
                "send_attempts": len(result.send_attempts),
                "sent_messages": len(result.sent_messages_audit),
                "blocked_before_send": len(result.blocked_before_send),
                "output_dir": str(config.output_dir),
                "telegram_connected": result.run_meta["telegram_connected"],
                "telegram_real_messages_sent": result.run_meta["telegram_real_messages_sent"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
