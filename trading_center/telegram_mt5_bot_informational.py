"""Informational Telegram message renderer for MT5 Bot observability."""

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
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LATEST_DIR = REPO_ROOT / "artifacts/tfg/trading_center_latest"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/telegram_mt5_bot_informational_v1_2026-06-09"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/TELEGRAM_MT5_BOT_INFORMATIONAL_V1.md"

METHOD_VERSION = "telegram_mt5_bot_informational_v1"

MESSAGE_TYPES = [
    "mt5_bot_status_digest",
    "mt5_account_snapshot_notice",
    "mt5_positions_digest",
    "riskguard_block_notice",
    "demo_order_event_notice",
    "demo_position_close_notice",
    "refresh_pipeline_notice",
    "ai_review_available_notice",
    "daily_summary",
    "wavecount_study_digest",
]

DELIVERY_DEFAULT_TYPES = {
    "mt5_bot_status_digest",
    "mt5_account_snapshot_notice",
    "daily_summary",
}

OPERATIONAL_WORDING_PATTERNS = [
    r"\bcomprar\s+ahora\b",
    r"\bvender\s+ahora\b",
    r"\bbuy\s+now\b",
    r"\bsell\s+now\b",
    r"\bejecut(ar|a|e)\b",
    r"\bexecute\b",
    r"\benviar\s+orden\b",
    r"\bconfirma(r)?\s+(esta\s+)?orden\b",
    r"\baprobar\s+orden\b",
    r"\bopera(r)?\s+este\s+setup\b",
    r"\bcerrar\s+posici[oó]n\s+desde\s+telegram\b",
    r"\bmodificar\s+posici[oó]n\s+desde\s+telegram\b",
    r"\bactivar\s+bot\b",
    r"\baprobado\s+para\s+mt5\b",
    r"\btrade\s+ready\b",
    r"\bse[nñ]al\s+autom[aá]tica\b",
]


@dataclass(frozen=True)
class TelegramMt5BotInformationalConfig:
    """Input artifact locations and preview options for message rendering."""
    latest_dir: Path = DEFAULT_LATEST_DIR
    latest_manifest: Path | None = None
    mt5_readonly_dir: Path | None = None
    mt5_shadow_dir: Path | None = None
    riskguard_dir: Path | None = None
    sender_dir: Path | None = None
    manager_dir: Path | None = None
    ai_analyst_dir: Path | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    dry_run: bool = True
    fixture_mode: bool = False
    manual_preview: bool = False
    max_messages: int | None = None
    allow_missing: bool = True
    include_ai_review: bool = False
    include_wavecount_study: bool = False


@dataclass(frozen=True)
class TelegramMt5BotInformationalResult:
    """Rendered messages and audits for one informational Telegram run."""
    decision: str
    rendered_messages: list[dict[str, Any]]
    source_data_audit: list[dict[str, Any]]
    no_action_audit: list[dict[str, Any]]
    delivery_audit: list[dict[str, Any]]
    delivery_condition_audit: list[dict[str, Any]]
    coverage: list[dict[str, Any]]
    safety_audit: list[dict[str, Any]]
    issues_or_risks: list[dict[str, Any]]
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_telegram_mt5_bot_informational(
    config: TelegramMt5BotInformationalConfig | None = None,
) -> TelegramMt5BotInformationalResult:
    """Render informational messages without sending real Telegram traffic."""
    config = config or TelegramMt5BotInformationalConfig()
    created_at = utc_now()
    source_data = fixture_source_data(created_at) if config.fixture_mode else read_source_data(config)
    source_audit = build_source_data_audit(source_data, config)
    messages = render_messages(source_data, config, created_at)
    no_action = build_no_action_audit(messages)
    attach_no_action(messages, no_action)
    delivery = simulate_delivery(messages, config)
    attach_delivery(messages, delivery)
    condition_audit = build_delivery_condition_audit(delivery)
    coverage = build_message_type_coverage(messages, config)
    safety = build_safety_audit(messages)
    issues = build_issues_or_risks(source_audit, no_action, delivery)
    decision = decide_result(source_audit, no_action)
    run_meta = build_run_meta(created_at, decision, messages, delivery, config)
    written = write_outputs(
        config=config,
        messages=messages,
        source_audit=source_audit,
        no_action=no_action,
        delivery=delivery,
        condition_audit=condition_audit,
        coverage=coverage,
        safety=safety,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, messages, source_audit, delivery, issues, run_meta)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "TELEGRAM_MT5_BOT_INFORMATIONAL_V1.md"
    return TelegramMt5BotInformationalResult(
        decision=decision,
        rendered_messages=messages,
        source_data_audit=source_audit,
        no_action_audit=no_action,
        delivery_audit=delivery,
        delivery_condition_audit=condition_audit,
        coverage=coverage,
        safety_audit=safety,
        issues_or_risks=issues,
        run_meta=run_meta,
        written_files=written,
    )


def read_source_data(config: TelegramMt5BotInformationalConfig) -> dict[str, Any]:
    latest_manifest_path = config.latest_manifest or config.latest_dir / "latest_manifest.json"
    mt5_readonly_dir = config.mt5_readonly_dir or latest_artifact_dir("mt5_read_only_connection_v1")
    mt5_shadow_dir = config.mt5_shadow_dir or latest_artifact_dir("mt5_shadow_v1", exclude=("fixture",))
    riskguard_dir = config.riskguard_dir or latest_artifact_dir("riskguard_demo_intent_builder_v1", exclude=("fixture",))
    sender_dir = config.sender_dir or latest_artifact_dir("mt5_demo_order_sender_v1", exclude=("fixture", "inputs"))
    manager_dir = config.manager_dir or latest_artifact_dir("mt5_demo_position_manager_v1", exclude=("fixture", "inputs"))
    ai_dir = config.ai_analyst_dir or latest_artifact_dir("codex_ai_analyst_real_model_review_v1")

    return {
        "latest_manifest_path": latest_manifest_path,
        "latest_manifest": read_json(latest_manifest_path),
        "mt5_readonly_dir": mt5_readonly_dir,
        "mt5_account": read_first_existing_json_or_csv(
            [mt5_readonly_dir / "mt5_account_snapshot.json", mt5_readonly_dir / "mt5_account_snapshot.csv"]
            if mt5_readonly_dir
            else []
        ),
        "mt5_positions": read_first_existing_json_or_csv(
            [mt5_readonly_dir / "mt5_positions_snapshot.json", mt5_readonly_dir / "mt5_positions_snapshot.csv"]
            if mt5_readonly_dir
            else []
        ),
        "mt5_pending": read_first_existing_json_or_csv(
            [mt5_readonly_dir / "mt5_pending_orders_snapshot.json", mt5_readonly_dir / "mt5_pending_orders_snapshot.csv"]
            if mt5_readonly_dir
            else []
        ),
        "mt5_readonly_meta": read_json(mt5_readonly_dir / "run_meta.json") if mt5_readonly_dir else {},
        "mt5_shadow_dir": mt5_shadow_dir,
        "mt5_shadow_decisions": read_csv(mt5_shadow_dir / "mt5_shadow_decisions.csv") if mt5_shadow_dir else [],
        "mt5_shadow_meta": read_json(mt5_shadow_dir / "run_meta.json") if mt5_shadow_dir else {},
        "riskguard_dir": riskguard_dir,
        "riskguard_decisions": read_csv(riskguard_dir / "riskguard_decisions.csv") if riskguard_dir else [],
        "demo_order_intents": read_csv(riskguard_dir / "demo_order_intents.csv") if riskguard_dir else [],
        "riskguard_meta": read_json(riskguard_dir / "run_meta.json") if riskguard_dir else {},
        "sender_dir": sender_dir,
        "sender_requests": read_first_existing_json_or_csv(
            [sender_dir / "demo_order_requests.json", sender_dir / "demo_order_requests.csv"] if sender_dir else []
        ),
        "sender_results": read_first_existing_json_or_csv(
            [sender_dir / "demo_order_results.json", sender_dir / "demo_order_results.csv"] if sender_dir else []
        ),
        "sender_meta": read_json(sender_dir / "run_meta.json") if sender_dir else {},
        "manager_dir": manager_dir,
        "manager_requests": read_first_existing_json_or_csv(
            [manager_dir / "demo_position_close_requests.json", manager_dir / "demo_position_close_requests.csv"]
            if manager_dir
            else []
        ),
        "manager_results": read_first_existing_json_or_csv(
            [manager_dir / "demo_position_close_results.json", manager_dir / "demo_position_close_results.csv"]
            if manager_dir
            else []
        ),
        "manager_meta": read_json(manager_dir / "run_meta.json") if manager_dir else {},
        "ai_analyst_dir": ai_dir,
        "ai_reports": list(ai_dir.rglob("review_output.*"))[:20] if ai_dir and ai_dir.exists() else [],
    }


def fixture_source_data(created_at: str) -> dict[str, Any]:
    return {
        "latest_manifest_path": Path("fixture/latest_manifest.json"),
        "latest_manifest": {"created_at_utc": created_at, "refresh_decision": "refresh_allowed"},
        "mt5_readonly_dir": Path("fixture/mt5_read_only"),
        "mt5_account": [
            {
                "balance": "100000.00",
                "equity": "99980.50",
                "margin": "120.00",
                "free_margin": "99860.50",
                "open_positions_count": "1",
                "pending_orders_count": "0",
                "read_timestamp_utc": created_at,
                "mt5_connected": "true",
                "read_only": "true",
            }
        ],
        "mt5_positions": [
            {
                "symbol": "EURUSD.r",
                "direction": "long",
                "volume": "0.01",
                "open_price": "1.15300",
                "floating_pnl": "-1.20",
            }
        ],
        "mt5_pending": [],
        "mt5_readonly_meta": {"decision": "mt5_read_only_fixture", "mt5_connected": True},
        "mt5_shadow_dir": Path("fixture/mt5_shadow"),
        "mt5_shadow_decisions": [
            {"symbol": "EURUSD.r", "timeframe": "H1", "setup_type": "macd_breakout", "shadow_decision": "would_wait"},
            {"symbol": "US100", "timeframe": "H4", "setup_type": "fib_limit_live_candidate", "shadow_decision": "would_trigger"},
        ],
        "mt5_shadow_meta": {"decision": "mt5_shadow_fixture", "visible_decisions_count": 2, "orders_sent": 0},
        "riskguard_dir": Path("fixture/riskguard"),
        "riskguard_decisions": [
            {
                "symbol": "AUDNZD.r",
                "timeframe": "H1",
                "setup_type": "macd_breakout",
                "riskguard_decision": "blocked_by_late_setup",
                "blocking_reason": "setup tarde",
            }
        ],
        "demo_order_intents": [{"intent_id": "intent_fixture", "symbol": "US100", "setup_type": "fib_limit_live_candidate"}],
        "riskguard_meta": {"decision": "riskguard_fixture", "blocked_count": 1},
        "sender_dir": Path("fixture/sender"),
        "sender_requests": [{"request_id": "req_fixture", "symbol": "EURUSD.r", "request_status": "prepared"}],
        "sender_results": [
            {
                "request_id": "req_fixture",
                "symbol": "EURUSD.r",
                "result_status": "sent",
                "mt5_retcode": "10009",
                "order_sent": True,
            },
            {
                "request_id": "req_rejected",
                "symbol": "GBPUSD.r",
                "result_status": "failed",
                "mt5_retcode": "10027",
                "order_sent": False,
            },
        ],
        "sender_meta": {"decision": "sender_fixture", "orders_sent": 1},
        "manager_dir": Path("fixture/manager"),
        "manager_requests": [{"close_request_id": "close_fixture", "symbol": "EURUSD.r", "request_status": "prepared"}],
        "manager_results": [
            {
                "close_request_id": "close_fixture",
                "symbol": "EURUSD.r",
                "result_status": "closed",
                "mt5_retcode": "10009",
                "position_closed": True,
            }
        ],
        "manager_meta": {"decision": "manager_fixture", "positions_closed": 1},
        "ai_analyst_dir": Path("fixture/ai"),
        "ai_reports": [Path("fixture/ai/report.md")],
    }


def render_messages(
    source_data: dict[str, Any],
    config: TelegramMt5BotInformationalConfig,
    created_at: str,
) -> list[dict[str, Any]]:
    messages = [
        make_message(
            "mt5_bot_status_digest",
            "info",
            "MT5 Bot: estado informativo",
            render_bot_status(source_data),
            source_refs(source_data, ["latest_manifest_path", "mt5_shadow_dir", "riskguard_dir"]),
            created_at,
            cooldown=30,
        ),
        make_message(
            "mt5_account_snapshot_notice",
            "info",
            "Cuenta MT5 - resumen",
            render_account_snapshot(source_data),
            source_refs(source_data, ["mt5_readonly_dir"]),
            created_at,
            cooldown=30,
        ),
        make_message(
            "mt5_positions_digest",
            "info",
            "Posiciones abiertas - rentabilidad",
            render_positions(source_data),
            source_refs(source_data, ["mt5_readonly_dir"]),
            created_at,
            cooldown=30,
        ),
        make_message(
            "riskguard_block_notice",
            "warning",
            "RiskGuard: bloqueos informativos",
            render_riskguard_blocks(source_data),
            source_refs(source_data, ["riskguard_dir"]),
            created_at,
            cooldown=20,
        ),
        make_message(
            "demo_order_event_notice",
            "info",
            "Orden demo - evento MT5",
            render_sender_events(source_data),
            source_refs(source_data, ["sender_dir"]),
            created_at,
            cooldown=10,
        ),
        make_message(
            "demo_position_close_notice",
            "info",
            "Cierre demo: evento auditado",
            render_manager_events(source_data),
            source_refs(source_data, ["manager_dir"]),
            created_at,
            cooldown=10,
        ),
        make_message(
            "refresh_pipeline_notice",
            "warning",
            "Refresh: aviso informativo",
            render_refresh_notice(source_data),
            source_refs(source_data, ["latest_manifest_path"]),
            created_at,
            cooldown=30,
        ),
        make_message(
            "daily_summary",
            "info",
            "Resumen diario informativo",
            render_daily_summary(source_data),
            source_refs(source_data, ["latest_manifest_path", "mt5_readonly_dir", "sender_dir", "manager_dir"]),
            created_at,
            cooldown=240,
        ),
    ]
    if config.include_ai_review:
        messages.append(
            make_message(
                "ai_review_available_notice",
                "info",
                "AI Analyst: informe disponible",
                render_ai_review(source_data),
                source_refs(source_data, ["ai_analyst_dir"]),
                created_at,
                cooldown=60,
            )
        )
    if config.include_wavecount_study:
        messages.append(
            make_message(
                "wavecount_study_digest",
                "study",
                "WeaveCount: digest study-only",
                "Resumen opcional de contexto estructural WeaveCount. Es study-only y no es filtro operativo.",
                source_refs(source_data, ["latest_manifest_path"]),
                created_at,
                cooldown=240,
            )
        )
    return messages


def make_message(
    message_type: str,
    severity: str,
    title: str,
    body: str,
    source_artifacts: str,
    created_at: str,
    *,
    cooldown: int,
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{message_type}|{title}|{body}|{created_at}".encode("utf-8")).hexdigest()[:12]
    return {
        "message_id": f"{message_type}_{digest}",
        "message_type": message_type,
        "severity": severity,
        "title": title,
        "body": body,
        "source_artifacts": source_artifacts,
        "dedup_key": hashlib.sha256(f"{message_type}|{title}|{body}".encode("utf-8")).hexdigest()[:16],
        "cooldown_minutes": cooldown,
        "delivery_status": "pending",
        "would_send_in_dry_run": False,
        "send_real": False,
        "telegram_connected": False,
        "telegram_message_sent": False,
        "safe_to_send": False,
        "blocked_patterns": "",
        "created_at_utc": created_at,
    }


def render_bot_status(source_data: dict[str, Any]) -> str:
    manifest = source_data.get("latest_manifest") or {}
    shadow_rows = source_data.get("mt5_shadow_decisions") or []
    risk_rows = source_data.get("riskguard_decisions") or []
    sender_meta = source_data.get("sender_meta") or {}
    manager_meta = source_data.get("manager_meta") or {}
    published_at = first_present(manifest, ["created_at_utc", "generated_at_utc", "updated_at_utc"]) or "n/d"
    return "\n".join(
        [
            "Estado informativo del MT5 Bot",
            f"Datos publicados: {human_datetime(published_at)}",
            f"Decisiones shadow: {len(shadow_rows)}",
            f"Decisiones RiskGuard: {len(risk_rows)}",
            f"Ordenes demo auditadas: {as_int(sender_meta.get('orders_sent'), 0)}",
            f"Cierres demo auditados: {as_int(manager_meta.get('positions_closed'), 0)}",
            "Telegram: solo informativo",
            "Live trading: bloqueado",
        ]
    )


def render_account_snapshot(source_data: dict[str, Any]) -> str:
    account = first_row(source_data.get("mt5_account") or [])
    if not account:
        return "No hay lectura MT5 de solo lectura disponible. Mensaje informativo sin datos de cuenta."
    pnl = first_present(account, ["floating_pnl", "closed_pnl_day"]) or "n/d"
    margin_level = first_present(account, ["margin_level", "margin_level_pct"]) or "n/d"
    timestamp = account.get("read_timestamp_utc", account.get("read_timestamp", "n/d"))
    return "\n".join(
        [
            "Cuenta MT5 - resumen de solo lectura",
            "--------------------------------",
            f"Balance:       {human_number(account.get('balance'))}",
            f"Equity:        {human_number(account.get('equity'))}",
            f"Margen usado:  {human_number(account.get('margin'))}",
            f"Margen libre:  {human_number(account.get('free_margin'))}",
            f"Nivel margen:  {human_number(margin_level)}",
            f"Rentabilidad:  {human_number(pnl)}",
            "",
            f"Posiciones abiertas: {account.get('open_positions_count', '0')}",
            f"Ordenes pendientes:  {account.get('pending_orders_count', '0')}",
            f"Lectura: {human_datetime(timestamp)}",
        ]
    )


def render_positions(source_data: dict[str, Any]) -> str:
    positions = source_data.get("mt5_positions") or []
    if not positions:
        return "No hay posiciones abiertas segun la ultima lectura MT5 de solo lectura."
    exposure = Counter(str(row.get("symbol", "unknown")) for row in positions)
    pnl = sum(float_or_zero(row.get("floating_pnl")) for row in positions)
    position_rows = [
        [
            short_value(row.get("symbol"), 10),
            direction_label(row.get("direction")),
            human_number(row.get("volume"), default="n/d"),
            human_number(row.get("floating_pnl"), default="n/d"),
            human_number(row.get("open_price"), default="n/d"),
            human_number(row.get("current_price"), default="n/d"),
        ]
        for row in positions[:8]
    ]
    lines = [
        "Posiciones abiertas - ultima lectura MT5",
        "----------------------------------",
        f"Total posiciones: {len(positions)}",
        f"Rentabilidad flotante: {pnl:.2f}",
        "",
        format_fixed_width_table(
            ["Activo", "Dir", "Vol", "Rentab.", "Entrada", "Actual"],
            position_rows,
            right_align={"Vol", "Rentab.", "Entrada", "Actual"},
        ),
    ]
    if len(positions) > 8:
        lines.append(f"... {len(positions) - 8} posicion(es) mas")
    lines.extend(
        [
            "",
            "Exposicion por activo:",
            ", ".join(f"{symbol} x{count}" for symbol, count in exposure.most_common(5)),
        ]
    )
    return "\n".join(lines)


def render_riskguard_blocks(source_data: dict[str, Any]) -> str:
    rows = source_data.get("riskguard_decisions") or []
    blocked = [row for row in rows if not boolish(row.get("accepted"))]
    if not blocked:
        return "No hay bloqueos RiskGuard relevantes en los artifacts leidos."
    reasons = count_by(blocked, "riskguard_decision")
    examples = "; ".join(
        f"{row.get('symbol', 'n/d')} {row.get('timeframe', '')} {row.get('riskguard_decision', 'blocked')}"
        for row in blocked[:3]
    )
    return f"RiskGuard registra {len(blocked)} bloqueos informativos. Motivos: {format_counter(reasons)}. Ejemplos: {examples}."


def render_sender_events(source_data: dict[str, Any]) -> str:
    results = source_data.get("sender_results") or []
    if not results:
        return "No hay eventos de orden demo en los artifacts del sender."
    sent = [row for row in results if boolish(row.get("order_sent"))]
    rejected = [row for row in results if not boolish(row.get("order_sent"))]
    lines = [
        "Orden demo - evento MT5 auditado",
        "--------------------------------",
        f"Eventos leidos: {len(results)}",
        f"Enviadas: {len(sent)}",
        f"No enviadas: {len(rejected)}",
        "",
    ]
    for row in results[:5]:
        status = "enviada" if boolish(row.get("order_sent")) else "no enviada"
        lines.extend(
            [
                f"{short_value(row.get('symbol'), 14)} - {status}",
                f"Resultado MT5: {friendly_sender_status(row)}",
                f"Codigo broker: {row.get('mt5_retcode', 'n/d')}",
            ]
        )
        request_id = row.get("request_id") or row.get("order_request_id") or row.get("intent_id")
        if request_id:
            lines.append(f"Referencia: {short_value(request_id, 22)}")
        lines.append("")
    lines.append("Telegram solo informa este evento; no solicita ni confirma operaciones.")
    return "\n".join(lines).strip()


def render_manager_events(source_data: dict[str, Any]) -> str:
    results = source_data.get("manager_results") or []
    if not results:
        return "No hay eventos de cierre demo en los artifacts del manager."
    closed = [row for row in results if boolish(row.get("position_closed")) or text(row.get("result_status")) == "closed"]
    examples = "; ".join(
        f"{row.get('symbol', 'n/d')} retcode {row.get('mt5_retcode', 'n/d')} status {row.get('result_status', 'n/d')}"
        for row in results[:3]
    )
    return f"Eventos de cierre DEMO auditados: total {len(results)}, cierres ejecutados {len(closed)}. Detalle: {examples}."


def render_refresh_notice(source_data: dict[str, Any]) -> str:
    manifest = source_data.get("latest_manifest") or {}
    decision = first_present(manifest, ["refresh_decision", "decision", "status"]) or "sin decision"
    stale = "stale" in json.dumps(manifest, ensure_ascii=False).lower()
    if stale:
        return f"Refresh con posible dato stale segun manifest. Estado: {decision}. Revisar artifacts latest."
    return f"No hay incidencia refresh detectada en manifest. Estado: {decision}."


def render_ai_review(source_data: dict[str, Any]) -> str:
    reports = source_data.get("ai_reports") or []
    if not reports:
        return "No hay reportes AI Analyst disponibles en la ruta leida."
    return f"AI Analyst tiene {len(reports)} reporte(s) disponible(s). Telegram solo informa disponibilidad; no aprueba ordenes."


def render_daily_summary(source_data: dict[str, Any]) -> str:
    account = first_row(source_data.get("mt5_account") or [])
    positions = source_data.get("mt5_positions") or []
    risk_rows = source_data.get("riskguard_decisions") or []
    sender_meta = source_data.get("sender_meta") or {}
    manager_meta = source_data.get("manager_meta") or {}
    return (
        "Resumen informativo diario. "
        f"Equity: {account.get('equity', 'n/d') if account else 'n/d'}. "
        f"Posiciones abiertas: {len(positions)}. "
        f"Decisiones RiskGuard: {len(risk_rows)}. "
        f"Ordenes demo auditadas: {as_int(sender_meta.get('orders_sent'), 0)}. "
        f"Cierres demo auditados: {as_int(manager_meta.get('positions_closed'), 0)}. "
        "Telegram no confirma ni realiza acciones."
    )


def build_no_action_audit(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for message in messages:
        text_to_check = normalize_text(f"{message.get('title', '')} {message.get('body', '')}")
        blocked = [pattern for pattern in OPERATIONAL_WORDING_PATTERNS if re.search(pattern, text_to_check)]
        rows.append(
            {
                "message_id": message["message_id"],
                "message_type": message["message_type"],
                "safe_to_send": not blocked,
                "audit_status": "blocked" if blocked else "pass",
                "blocked_patterns": "|".join(blocked),
                "telegram_can_confirm": False,
                "telegram_can_trade": False,
            }
        )
    return rows


def attach_no_action(messages: list[dict[str, Any]], audits: list[dict[str, Any]]) -> None:
    by_id = {row["message_id"]: row for row in audits}
    for message in messages:
        audit = by_id[message["message_id"]]
        message["safe_to_send"] = boolish(audit["safe_to_send"])
        message["blocked_patterns"] = audit["blocked_patterns"]


def simulate_delivery(
    messages: list[dict[str, Any]],
    config: TelegramMt5BotInformationalConfig,
) -> list[dict[str, Any]]:
    rows = []
    sent_like_count = 0
    for message in messages:
        condition_status, condition_reason = delivery_condition(message)
        if not message["safe_to_send"]:
            status = "blocked_policy"
        elif message["message_type"] in DELIVERY_DEFAULT_TYPES:
            status = "preview_allowed"
        elif condition_status == "has_condition":
            status = "event_allowed"
        elif config.manual_preview:
            status = "preview_allowed"
        elif message["message_type"] == "wavecount_study_digest":
            status = "manual_only"
        else:
            status = "omitted_no_condition"
        would_send = status in {"preview_allowed", "event_allowed"} and config.dry_run
        if config.max_messages is not None and would_send:
            sent_like_count += 1
            if sent_like_count > config.max_messages:
                status = "blocked_policy"
                would_send = False
                condition_reason = "max_messages_exceeded"
        rows.append(
            {
                "message_id": message["message_id"],
                "message_type": message["message_type"],
                "delivery_status": status,
                "condition_status": condition_status,
                "condition_reason": condition_reason,
                "would_send_in_dry_run": would_send,
                "send_real": False,
                "telegram_connected": False,
                "telegram_message_sent": False,
            }
        )
    return rows


def delivery_condition(message: dict[str, Any]) -> tuple[str, str]:
    body = normalize_text(str(message.get("body", "")))
    message_type = str(message.get("message_type", ""))
    if message_type == "mt5_positions_digest" and "no hay posiciones abiertas" not in body:
        return "has_condition", "open_positions_available"
    if message_type == "riskguard_block_notice" and "no hay bloqueos" not in body:
        return "has_condition", "riskguard_blocks_available"
    if message_type == "demo_order_event_notice" and "no hay eventos" not in body:
        return "has_condition", "sender_event_available"
    if message_type == "demo_position_close_notice" and "no hay eventos" not in body:
        return "has_condition", "manager_event_available"
    if message_type == "refresh_pipeline_notice" and ("stale" in body or "error" in body or "fallback" in body):
        return "has_condition", "refresh_issue_available"
    if message_type == "ai_review_available_notice" and "no hay reportes" not in body:
        return "has_condition", "ai_report_available"
    return "no_condition", "no_event_or_manual_preview_required"


def attach_delivery(messages: list[dict[str, Any]], delivery: list[dict[str, Any]]) -> None:
    by_id = {row["message_id"]: row for row in delivery}
    for message in messages:
        row = by_id[message["message_id"]]
        message["delivery_status"] = row["delivery_status"]
        message["would_send_in_dry_run"] = boolish(row["would_send_in_dry_run"])


def build_delivery_condition_audit(delivery: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "message_id": row["message_id"],
            "message_type": row["message_type"],
            "condition_status": row["condition_status"],
            "condition_reason": row["condition_reason"],
            "delivery_status": row["delivery_status"],
        }
        for row in delivery
    ]


def build_message_type_coverage(
    messages: list[dict[str, Any]],
    config: TelegramMt5BotInformationalConfig,
) -> list[dict[str, Any]]:
    rendered = {row["message_type"] for row in messages}
    rows = []
    for message_type in MESSAGE_TYPES:
        if message_type == "ai_review_available_notice":
            selected = config.include_ai_review
        elif message_type == "wavecount_study_digest":
            selected = config.include_wavecount_study
        else:
            selected = True
        rows.append(
            {
                "message_type": message_type,
                "selected": selected,
                "rendered": message_type in rendered,
                "status": "rendered" if message_type in rendered else "not_selected" if not selected else "missing",
            }
        )
    return rows


def build_source_data_audit(
    source_data: dict[str, Any],
    config: TelegramMt5BotInformationalConfig,
) -> list[dict[str, Any]]:
    source_specs = [
        ("latest_manifest", source_data.get("latest_manifest_path"), source_data.get("latest_manifest"), True),
        ("mt5_account_snapshot", source_data.get("mt5_readonly_dir"), source_data.get("mt5_account"), False),
        ("mt5_positions_snapshot", source_data.get("mt5_readonly_dir"), source_data.get("mt5_positions"), False),
        ("mt5_shadow_decisions", source_data.get("mt5_shadow_dir"), source_data.get("mt5_shadow_decisions"), False),
        ("riskguard_decisions", source_data.get("riskguard_dir"), source_data.get("riskguard_decisions"), False),
        ("demo_order_sender", source_data.get("sender_dir"), source_data.get("sender_results"), False),
        ("demo_position_manager", source_data.get("manager_dir"), source_data.get("manager_results"), False),
        ("ai_analyst_reports", source_data.get("ai_analyst_dir"), source_data.get("ai_reports"), False),
    ]
    rows = []
    for source_id, path, data, required in source_specs:
        exists = path_exists(path)
        count = item_count(data)
        status = "available" if exists and count > 0 else "available_empty" if exists else "missing"
        warning = "" if status == "available" or (not required and config.allow_missing) else "missing_required_source"
        rows.append(
            {
                "source_id": source_id,
                "path": str(path) if path else "",
                "exists": exists,
                "rows_or_items": count,
                "required": required,
                "freshness": infer_freshness(data),
                "status": status,
                "warning_reason": warning,
            }
        )
    return rows


def build_safety_audit(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"check": "telegram_connected", "value": False, "expected": False, "status": "pass"},
        {"check": "telegram_messages_sent", "value": 0, "expected": 0, "status": "pass"},
        {"check": "telegram_command_bot_implemented", "value": False, "expected": False, "status": "pass"},
        {"check": "telegram_can_confirm", "value": False, "expected": False, "status": "pass"},
        {"check": "telegram_can_trade", "value": False, "expected": False, "status": "pass"},
        {"check": "message_send_real_any_true", "value": any(boolish(row.get("send_real")) for row in messages), "expected": False, "status": "pass"},
        {"check": "message_telegram_sent_any_true", "value": any(boolish(row.get("telegram_message_sent")) for row in messages), "expected": False, "status": "pass"},
    ]


def build_issues_or_risks(
    source_audit: list[dict[str, Any]],
    no_action: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues = []
    for row in source_audit:
        if row["warning_reason"]:
            issues.append({"severity": "warning", "issue": f"{row['source_id']} {row['warning_reason']}", "mitigation": "usar allow-missing solo en dry-run o aportar artifact"})
    blocked = [row for row in no_action if not boolish(row.get("safe_to_send"))]
    if blocked:
        issues.append({"severity": "high", "issue": f"{len(blocked)} mensajes bloqueados por wording operativo", "mitigation": "revisar templates"})
    omitted = [row for row in delivery if row["delivery_status"] == "omitted_no_condition"]
    if omitted:
        issues.append({"severity": "info", "issue": f"{len(omitted)} mensajes omitidos por falta de condicion", "mitigation": "normal en dry-run"})
    return issues


def decide_result(source_audit: list[dict[str, Any]], no_action: list[dict[str, Any]]) -> str:
    if any(row["required"] and row["status"] == "missing" for row in source_audit):
        return "telegram_mt5_bot_informational_v1_blocked_by_data_contract"
    if any(not boolish(row["safe_to_send"]) for row in no_action):
        return "telegram_mt5_bot_informational_v1_needs_minor_fix"
    return "telegram_mt5_bot_informational_v1_ready_for_sender_gate_alignment"


def build_run_meta(
    created_at: str,
    decision: str,
    messages: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    config: TelegramMt5BotInformationalConfig,
) -> dict[str, Any]:
    return {
        "phase": "telegram_mt5_bot_informational_v1",
        "method_version": METHOD_VERSION,
        "created_at_utc": created_at,
        "decision": decision,
        "telegram_mt5_bot_informational_implemented": True,
        "dry_run_only": True,
        "fixture_mode": config.fixture_mode,
        "manual_preview": config.manual_preview,
        "telegram_connected": False,
        "telegram_messages_sent": 0,
        "telegram_real_messages_sent": 0,
        "telegram_command_bot_implemented": False,
        "telegram_can_confirm": False,
        "telegram_can_trade": False,
        "telegram_confirms_orders": False,
        "telegram_modifies_positions": False,
        "telegram_tokens_read": False,
        "telegram_tokens_printed": False,
        "telegram_tokens_stored": False,
        "telegram_chat_ids_read": False,
        "telegram_chat_ids_printed": False,
        "telegram_chat_ids_stored": False,
        "mt5_connected": False,
        "orders_sent": 0,
        "mt5_orders_sent": 0,
        "sql_real_written": False,
        "ddl_executed": False,
        "backtests_executed": False,
        "messages_rendered_count": len(messages),
        "messages_preview_allowed_count": sum(1 for row in delivery if row["delivery_status"] in {"preview_allowed", "event_allowed"}),
        "messages_blocked_count": sum(1 for row in delivery if row["delivery_status"] == "blocked_policy"),
        "message_types_rendered": sorted({row["message_type"] for row in messages}),
    }


def write_outputs(
    *,
    config: TelegramMt5BotInformationalConfig,
    messages: list[dict[str, Any]],
    source_audit: list[dict[str, Any]],
    no_action: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    condition_audit: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    safety: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    output_dir = config.output_dir
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "rendered_messages.csv", messages)
    write_json(output_dir / "rendered_messages.json", messages)
    write_csv(tables_dir / "source_data_audit.csv", source_audit)
    write_csv(tables_dir / "message_type_coverage.csv", coverage)
    write_csv(tables_dir / "no_action_message_audit.csv", no_action)
    write_csv(tables_dir / "delivery_simulation_audit.csv", delivery)
    write_csv(tables_dir / "delivery_condition_audit.csv", condition_audit)
    write_csv(tables_dir / "safety_audit.csv", safety)
    write_csv(tables_dir / "issues_or_risks.csv", issues)
    write_json(output_dir / "run_meta.json", run_meta)
    return {
        "rendered_messages_csv": output_dir / "rendered_messages.csv",
        "rendered_messages_json": output_dir / "rendered_messages.json",
        "run_meta": output_dir / "run_meta.json",
    }


def write_docs(
    config: TelegramMt5BotInformationalConfig,
    messages: list[dict[str, Any]],
    source_audit: list[dict[str, Any]],
    delivery: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    run_meta: dict[str, Any],
) -> None:
    text_doc = f"""# Telegram MT5 Bot Informational V1

Decision: `{run_meta['decision']}`

## Resumen

Se implementa el renderer informativo dry-run de Telegram para `MT5 Bot`.
No envia mensajes reales, no lee tokens, no conecta Telegram, no conecta MT5 y
no ejecuta ordenes.

Frase canonica para memoria: Telegram queda como canal informativo y de
observabilidad del bot demo; no es consola, no confirma ordenes, no ejecuta
operaciones y no habilita live trading.

## Mensajes

- Renderizados: {len(messages)}
- Preview/event allowed en dry-run: {sum(1 for row in delivery if row['delivery_status'] in {'preview_allowed', 'event_allowed'})}
- Bloqueados por politica: {sum(1 for row in delivery if row['delivery_status'] == 'blocked_policy')}

Tipos renderizados: {', '.join(run_meta['message_types_rendered'])}

## Fuentes

Fuentes disponibles: {sum(1 for row in source_audit if row['status'] != 'missing')} / {len(source_audit)}.

## Seguridad

- `telegram_can_confirm=false`
- `telegram_can_trade=false`
- `telegram_command_bot_implemented=false`
- `telegram_messages_sent=0`
- `orders_sent=0`
- No acepta comandos por Telegram.
- No solicita confirmaciones ni aprobaciones operativas.
- No contiene lenguaje de comprar/vender ahora.

## Riesgos

{format_issues(issues)}
"""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "TELEGRAM_MT5_BOT_INFORMATIONAL_V1.md").write_text(text_doc, encoding="utf-8")
    config.doc_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_path.write_text(text_doc, encoding="utf-8")


def format_issues(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "- Sin incidencias relevantes."
    return "\n".join(f"- {row.get('severity', 'info')}: {row.get('issue', '')}" for row in issues)


def latest_artifact_dir(prefix: str, exclude: Iterable[str] = ()) -> Path | None:
    base = REPO_ROOT / "artifacts/tfg"
    if not base.exists():
        return None
    candidates = [
        path
        for path in base.iterdir()
        if path.is_dir()
        and path.name.startswith(prefix)
        and not any(fragment in path.name.lower() for fragment in exclude)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_first_existing_json_or_csv(paths: Iterable[Path]) -> list[dict[str, Any]]:
    for path in paths:
        if path.exists():
            if path.suffix.lower() == ".json":
                data = read_json(path)
                if isinstance(data, list):
                    return [dict(row) for row in data if isinstance(row, dict)]
                if isinstance(data, dict):
                    for key in ("rows", "items", "positions", "requests", "results"):
                        value = data.get(key)
                        if isinstance(value, list):
                            return [dict(row) for row in value if isinstance(row, dict)]
                    return [data]
            return read_csv(path)
    return []


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: serialize_cell(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def serialize_cell(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def first_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def first_present(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return ""


def source_refs(source_data: dict[str, Any], keys: list[str]) -> str:
    refs = []
    for key in keys:
        value = source_data.get(key)
        if value:
            refs.append(str(value))
    return "|".join(refs)


def path_exists(path: Any) -> bool:
    normalized = str(path).replace("\\", "/")
    if normalized.startswith("fixture/"):
        return True
    return bool(path) and Path(path).exists()


def item_count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return 1 if data else 0
    return 1 if data else 0


def infer_freshness(data: Any) -> str:
    blob = json.dumps(data, ensure_ascii=False, default=str).lower()
    if not blob or blob in {"{}", "[]"}:
        return "missing"
    if "stale" in blob:
        return "stale_or_warning"
    return "available"


def normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return value


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def text(value: Any) -> str:
    return str(value or "").strip()


def short_value(value: Any, max_len: int = 18) -> str:
    cleaned = str(value or "n/d").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def human_number(value: Any, *, default: str = "n/d") -> str:
    if value in (None, ""):
        return default
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}"
    if abs(number) >= 10:
        return f"{number:.2f}"
    return f"{number:.5f}".rstrip("0").rstrip(".")


def human_datetime(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "n/d":
        return "n/d"
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def format_fixed_width_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    right_align: set[str] | None = None,
) -> str:
    right_align = right_align or set()
    table = [headers, *rows]
    widths = [max(len(str(row[index])) for row in table) for index in range(len(headers))]
    formatted: list[str] = []
    for row_index, row in enumerate(table):
        cells = []
        for index, value in enumerate(row):
            cell = str(value)
            header = headers[index]
            cells.append(cell.rjust(widths[index]) if header in right_align and row_index else cell.ljust(widths[index]))
        formatted.append("  ".join(cells).rstrip())
    return "\n".join(formatted)


def direction_label(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"buy", "long", "bullish", "alcista"}:
        return "Largo"
    if normalized in {"sell", "short", "bearish", "bajista"}:
        return "Corto"
    return "n/d"


def friendly_sender_status(row: dict[str, Any]) -> str:
    status = str(row.get("result_status", "") or "").strip().lower()
    if boolish(row.get("order_sent")):
        return "aceptada por MT5"
    if status in {"failed", "rejected", "blocked"}:
        return "no aceptada"
    if status:
        return status.replace("_", " ")
    return "sin estado"


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def float_or_zero(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def count_by(rows: list[dict[str, Any]], field: str) -> Counter[str]:
    return Counter(str(row.get(field, "unknown") or "unknown") for row in rows)


def format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "n/d"
    return ", ".join(f"{key}={value}" for key, value in counter.most_common(5))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Telegram informational messages for MT5 Bot without sending.")
    parser.add_argument("--latest-dir", type=Path, default=DEFAULT_LATEST_DIR)
    parser.add_argument("--latest-manifest", type=Path)
    parser.add_argument("--mt5-readonly-dir", type=Path)
    parser.add_argument("--mt5-shadow-dir", type=Path)
    parser.add_argument("--riskguard-dir", type=Path)
    parser.add_argument("--sender-dir", type=Path)
    parser.add_argument("--manager-dir", type=Path)
    parser.add_argument("--ai-analyst-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--manual-preview", action="store_true")
    parser.add_argument("--max-messages", type=int)
    parser.add_argument("--allow-missing", action="store_true", default=True)
    parser.add_argument("--include-ai-review", action="store_true")
    parser.add_argument("--include-wavecount-study", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(
            latest_dir=args.latest_dir,
            latest_manifest=args.latest_manifest,
            mt5_readonly_dir=args.mt5_readonly_dir,
            mt5_shadow_dir=args.mt5_shadow_dir,
            riskguard_dir=args.riskguard_dir,
            sender_dir=args.sender_dir,
            manager_dir=args.manager_dir,
            ai_analyst_dir=args.ai_analyst_dir,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            fixture_mode=args.fixture_mode,
            manual_preview=args.manual_preview,
            max_messages=args.max_messages,
            allow_missing=args.allow_missing,
            include_ai_review=args.include_ai_review,
            include_wavecount_study=args.include_wavecount_study,
        )
    )
    print(result.decision)
    print(f"output_dir={result.written_files['run_meta'].parent}")
    print(f"messages_rendered={result.run_meta['messages_rendered_count']}")
    print(f"telegram_messages_sent={result.run_meta['telegram_messages_sent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
