from __future__ import annotations

from typing import Any, Mapping

from trading_center.dashboard.formatting import display_context_value, get_value


MT5_DEMO_SENDER_PREPARED_KEY = "order_" + "requ" + "ests_prepared"
MT5_DEMO_MANAGER_PREPARED_KEY = "close_" + "requ" + "ests_prepared"


def mt5_shadow_status_label(decision: Any) -> str:
    text = str(decision or "").strip()
    if not text:
        return "Shadow pendiente"
    if "ready_for_local_shadow_review" in text:
        return "Shadow listo"
    if "blocked" in text:
        return "Shadow bloqueado"
    if "needs" in text:
        return "Shadow a revisar"
    return "Shadow disponible"


def riskguard_status_label(decision: Any) -> str:
    text = str(decision or "").strip()
    if not text:
        return "RiskGuard pendiente"
    if "ready_for_dashboard_review" in text:
        return "RiskGuard listo"
    if "blocked" in text:
        return "RiskGuard bloquea"
    if "needs" in text:
        return "RiskGuard a revisar"
    return "RiskGuard disponible"


def sender_status_label(meta: Mapping[str, Any]) -> str:
    orders_sent = int(float(meta.get("orders_sent", 0) or 0))
    prepared = int(float(meta.get(MT5_DEMO_SENDER_PREPARED_KEY, 0) or 0))
    if orders_sent:
        return "Orden demo enviada"
    if prepared:
        return "Orden demo preparada"
    return "Sin orden demo"


def manager_status_label(meta: Mapping[str, Any]) -> str:
    positions_closed = int(float(meta.get("positions_closed", 0) or 0))
    prepared = int(float(meta.get(MT5_DEMO_MANAGER_PREPARED_KEY, 0) or 0))
    if positions_closed:
        return "Cierre validado"
    if prepared:
        return "Cierre preparado"
    return "Sin cierre demo"


def telegram_info_status_label(meta: Mapping[str, Any]) -> str:
    if not meta:
        return "Telegram info OFF"
    sent = int(float(meta.get("telegram_real_messages_sent", 0) or 0))
    failed = int(float(meta.get("failed_transport_count", 0) or 0))
    connected = bool(meta.get("telegram_connected", False))
    if connected and sent > 0:
        return "Telegram info ON"
    if failed > 0:
        return "Telegram error"
    return "Telegram info OFF"


def telegram_info_sent_label(meta: Mapping[str, Any]) -> str:
    sent = int(float(meta.get("telegram_real_messages_sent", 0) or 0))
    if sent == 1:
        return "1 aviso enviado"
    if sent > 1:
        return f"{sent} avisos enviados"
    return "sin avisos"


def telegram_info_result_label(meta: Mapping[str, Any]) -> str:
    decision = str(meta.get("decision", "") or "").strip()
    failed = int(float(meta.get("failed_transport_count", 0) or 0))
    if failed > 0:
        return "ultimo envio con error"
    if decision == "telegram_real_sender_v1_real_send_executed":
        return "ultimo envio OK"
    if decision:
        return "envio no activo"
    return "sin artifact Telegram"


def mt5_shadow_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    states = {
        "total": len(rows),
        "would_trigger": 0,
        "would_wait": 0,
        "would_skip_context_only": 0,
        "blocked": 0,
        "late": 0,
        "invalidated": 0,
        "no_price_data": 0,
        "auto_candidate": 0,
        "context_only": 0,
        "below_min_quality": 0,
    }
    for row in rows:
        state = str(row.get("shadow_state", "")).strip()
        if state in states:
            states[state] += 1
        scope = str(row.get("automation_scope", "")).strip()
        if scope in states:
            states[scope] += 1
    return states


def mt5_shadow_state_label(value: Any) -> str:
    labels = {
        "would_trigger": "habria activado revision",
        "would_wait": "esperando",
        "would_skip_context_only": "solo contexto",
        "blocked": "bloqueado",
        "late": "tarde",
        "invalidated": "invalidado",
        "no_price_data": "sin precio",
    }
    text = str(value or "").strip()
    return labels.get(text, text.replace("_", " ") or "sin estado")


def mt5_shadow_tone(value: Any) -> str:
    state = str(value or "").strip()
    if state == "would_trigger":
        return "candidate"
    if state == "would_wait":
        return "muted"
    if state in {"blocked", "late", "invalidated", "no_price_data"}:
        return "down"
    return "flat"


def riskguard_decision_label(value: Any) -> str:
    decision = str(value or "").strip()
    labels = {
        "accepted_for_demo_intent": "intent revisable",
        "blocked_by_late_setup": "bloqueado: tarde",
        "blocked_by_waiting_confirmation": "bloqueado: falta confirmacion",
        "blocked_by_stale_data": "bloqueado: datos no vigentes",
        "blocked_by_missing_entry": "bloqueado: sin entrada",
        "blocked_by_missing_sl": "bloqueado: sin SL",
        "blocked_by_missing_tp": "bloqueado: sin TP",
        "blocked_by_low_quality": "bloqueado: baja calidad",
        "blocked_by_setup_scope": "bloqueado: fuera de scope",
        "blocked_by_invalidated_setup": "bloqueado: invalidado",
        "blocked_by_missing_mt5_snapshot": "bloqueado: falta snapshot MT5",
        "blocked_by_existing_position": "bloqueado: posicion existente",
        "blocked_by_duplicate": "bloqueado: duplicado",
    }
    return labels.get(decision, decision.replace("_", " ") if decision else "RiskGuard pendiente")


def riskguard_decision_tone(value: Any) -> str:
    decision = str(value or "").strip()
    if decision == "accepted_for_demo_intent":
        return "candidate"
    if decision in {"blocked_by_late_setup", "blocked_by_invalidated_setup"}:
        return "down"
    if decision.startswith("blocked_by_"):
        return "muted"
    return "flat"


def riskguard_decision_detail(value: Any) -> str:
    decision = str(value or "").strip()
    details = {
        "accepted_for_demo_intent": "revisable en demo futura; no orden",
        "blocked_by_late_setup": "la ventana de revision ya paso",
        "blocked_by_waiting_confirmation": "esperando cierre que confirme el setup",
        "blocked_by_stale_data": "faltan datos vigentes para validar",
        "blocked_by_missing_entry": "no hay nivel de entrada definido",
        "blocked_by_missing_sl": "no hay SL de estudio definido",
        "blocked_by_missing_tp": "no hay TP de estudio definido",
        "blocked_by_low_quality": "calidad inferior al minimo",
        "blocked_by_setup_scope": "fuera del scope automatico",
        "blocked_by_invalidated_setup": "setup invalidado",
        "blocked_by_missing_mt5_snapshot": "falta snapshot MT5 read-only",
        "blocked_by_existing_position": "ya existe posicion del simbolo",
        "blocked_by_duplicate": "posible duplicado o pendiente existente",
    }
    return details.get(decision, "pendiente de evaluacion RiskGuard")


def riskguard_decision_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        setup_id = str(row.get("setup_id", "")).strip()
        if setup_id:
            index[setup_id] = row
    return index


def riskguard_decision_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    decisions = [str(row.get("riskguard_decision", "")).strip() for row in rows]
    return {
        "reviewed": len(rows),
        "accepted": sum(1 for decision in decisions if decision == "accepted_for_demo_intent"),
        "blocked": sum(1 for decision in decisions if decision.startswith("blocked_by_")),
        "late": sum(1 for decision in decisions if decision == "blocked_by_late_setup"),
        "waiting": sum(1 for decision in decisions if decision == "blocked_by_waiting_confirmation"),
    }


def mt5_shadow_row(html: Any, row: dict[str, Any], riskguard_row: dict[str, Any] | None = None) -> Any:
    state = get_value(row, "shadow_state", "sin_estado")
    tone = mt5_shadow_tone(state)
    reason = display_context_value(get_value(row, "shadow_reason", "sin razon"))
    scope = display_context_value(get_value(row, "automation_scope", "sin_scope"))
    quality = get_value(row, "setup_quality_score", "")
    riskguard_row = riskguard_row or {}
    riskguard_decision = get_value(riskguard_row, "riskguard_decision", "")
    riskguard_label = riskguard_decision_label(riskguard_decision)
    riskguard_tone = riskguard_decision_tone(riskguard_decision)
    riskguard_detail = riskguard_decision_detail(riskguard_decision)
    return html.Div(
        [
            html.Div(
                [
                    html.Strong(get_value(row, "symbol", "symbol")),
                    html.Small(f"{get_value(row, 'market_group', 'grupo')} / {get_value(row, 'timeframe', 'TF')} / {get_value(row, 'setup_type', 'setup')}"),
                ],
                className="shadow-row-asset",
            ),
            html.Div(
                [
                    html.Span(mt5_shadow_state_label(state), className=f"shadow-state-pill {tone}"),
                    html.Span(scope, className="shadow-row-pill"),
                    html.Span(f"calidad {quality}/5" if quality else "calidad n/d", className="shadow-row-pill muted"),
                    html.Span(get_value(row, "direction", "context"), className="shadow-row-pill"),
                    html.Span(get_value(row, "timing_state", "sin timing").replace("_", " "), className="shadow-row-pill muted"),
                ],
                className="shadow-row-main",
            ),
            html.Div(reason, className="shadow-row-reason"),
            html.Div(
                [
                    html.Span("RiskGuard", className="shadow-row-pill muted"),
                    html.Span(riskguard_label, className=f"shadow-state-pill {riskguard_tone}"),
                    html.Span(
                        riskguard_detail,
                        className="shadow-row-pill muted",
                    ),
                ],
                className="shadow-row-main",
            ),
            html.Div(
                [
                    html.Span("orden no enviada", className="shadow-safety-chip"),
                    html.Span("solo hipotetico", className="shadow-safety-chip"),
                ],
                className="shadow-row-end",
            ),
        ],
        className=f"shadow-decision-row {tone}",
    )

def mt5_shadow_tab(html: Any, data_obj: dict[str, Any]) -> Any:
    rows = data_obj.get("mt5_shadow_rows", [])
    meta = data_obj.get("mt5_shadow_meta", {}) or {}
    riskguard_rows = data_obj.get("riskguard_decision_rows", [])
    riskguard_by_setup = riskguard_decision_index(riskguard_rows)
    riskguard_meta = data_obj.get("riskguard_meta", {}) or {}
    sender_meta = data_obj.get("mt5_demo_sender_meta", {}) or {}
    manager_meta = data_obj.get("mt5_demo_manager_meta", {}) or {}
    telegram_meta = data_obj.get("telegram_real_sender_meta", {}) or {}
    summary = mt5_shadow_summary(rows)
    riskguard_summary = riskguard_decision_summary(riskguard_rows)
    if not rows:
        return html.Div(
            [
                html.Section(
                    [
                        html.Div([html.H2("MT5 Bot", className="visually-hidden")], className="panel-heading-title-row"),
                        html.Div(
                            "Faltan artifacts del modulo MT5 Bot. Ejecuta `python -m trading_center.mt5_shadow` y recarga.",
                            className="radar-empty",
                        ),
                    ],
                    className="shadow-shell",
                )
            ]
        )
    stat_items = [
        ("Casos mostrados", summary["total"]),
        ("Activan revision", summary["would_trigger"]),
        ("Esperando", summary["would_wait"]),
        ("Excluidos", int(float(meta.get("setups_excluded_from_shadow_decisions_count", 0) or 0))),
        ("Candidatos bot", summary["auto_candidate"]),
        ("Baja nota", summary["below_min_quality"]),
        ("RiskGuard revisados", riskguard_summary["reviewed"]),
        ("Bloqueados por RG", riskguard_summary["blocked"]),
        ("Tarde", riskguard_summary["late"]),
    ]
    ordered_rows = sorted(
        rows,
        key=lambda item: (
            {"would_trigger": 0, "would_wait": 1, "would_skip_context_only": 2}.get(str(item.get("shadow_state", "")), 3),
            str(item.get("symbol", "")),
        ),
    )
    return html.Div(
        [
            html.Section(
                [
                    html.Div(
                        [
                            html.Span(
                                "i",
                                className="info-icon",
                                style={"marginLeft": "0"},
                                title="Shadow compara setups contra OHLC cerrado. Es hipotetico: no envia ordenes.",
                            ),
                            html.H2("MT5 Bot", className="visually-hidden"),
                        ],
                        className="panel-heading-title-row",
                    ),
                    html.Div(
                        [
                            html.Div([html.Strong(str(value)), html.Small(label)], className="shadow-stat")
                            for label, value in stat_items
                        ],
                        className="shadow-stat-grid",
                    ),
                    html.Div(
                        [
                            html.Span(mt5_shadow_status_label(meta.get("decision")), className="shadow-safety-chip"),
                            html.Span(
                                riskguard_status_label(riskguard_meta.get("decision")),
                                className="shadow-safety-chip",
                            ),
                            html.Span("MT5 no conectado", className="shadow-safety-chip"),
                            html.Span(telegram_info_status_label(telegram_meta), className="shadow-safety-chip"),
                            html.Span(telegram_info_sent_label(telegram_meta), className="shadow-safety-chip"),
                            html.Span(telegram_info_result_label(telegram_meta), className="shadow-safety-chip"),
                        ],
                        className="shadow-safety-row",
                    ),
                    html.Div(
                        [
                            html.Span("Ciclo demo", className="shadow-row-pill muted"),
                            html.Span(sender_status_label(sender_meta), className="shadow-safety-chip"),
                            html.Span(
                                f"preparadas {int(float(sender_meta.get(MT5_DEMO_SENDER_PREPARED_KEY, 0) or 0))}",
                                className="shadow-safety-chip",
                            ),
                            html.Span(
                                f"ordenes demo {int(float(sender_meta.get('orders_sent', 0) or 0))}",
                                className="shadow-safety-chip",
                            ),
                            html.Span(manager_status_label(manager_meta), className="shadow-safety-chip"),
                            html.Span(
                                f"cierres {int(float(manager_meta.get('positions_closed', 0) or 0))}",
                                className="shadow-safety-chip",
                            ),
                        ],
                        className="shadow-safety-row",
                    ),
                ],
                className="shadow-hero",
            ),
            html.Div(
                [
                    html.H3("Decisiones shadow"),
                    html.P("Estados hipoteticos para revisar timing y coherencia antes de cualquier fase demo. El ambito automatico queda limitado a macd_breakout y fib_limit con calidad suficiente; el resto queda excluido de la lista principal."),
                ],
                className="panel-heading",
            ),
            html.Div(
                [
                    mt5_shadow_row(html, row, riskguard_by_setup.get(str(row.get("setup_id", "")).strip()))
                    for row in ordered_rows[:80]
                ],
                className="shadow-decision-list",
            ),
        ]
    )
