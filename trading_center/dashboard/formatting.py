from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


DISPLAY_TIMEZONE = ZoneInfo("Europe/Madrid")


def format_dashboard_timestamp(value: str, *, empty: str = "sin datos") -> str:
    raw = str(value or "").strip()
    if not raw:
        return empty
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(DISPLAY_TIMEZONE)
    return local.strftime("%d %b %H:%M")


def safe_float(value: Any) -> float | None:
    text = str(value).strip().split()[-1] if str(value).strip() else ""
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed


def safe_int(value: Any) -> int | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def pct(value: float | int, total: float | int) -> int:
    if not total:
        return 0
    return int(round((float(value) / float(total)) * 100))


def table_columns(keys: list[str]) -> list[dict[str, str]]:
    return [{"name": key, "id": key} for key in keys]


def select_columns(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    return [{key: row.get(key, "") for key in keys} for row in rows]


def get_value(row: dict[str, Any] | None, key: str, default: str = "not_available") -> str:
    if not row:
        return default
    value = row.get(key, default)
    if value in (None, ""):
        return default
    return str(value)


def display_context_value(value: Any, *, empty_label: str = "sin contexto") -> str:
    text = str(value or "").strip()
    replacements = {
        "no_context": empty_label,
        "not_available": "revision codex pendiente",
        "pending_source": "pendiente de fuente",
        "future_phase": "fase futura",
        "context_only": "solo contexto",
        "auto_candidate": "candidato bot",
        "below_min_quality": "baja nota",
        "setup_type_not_in_automatic_bot_scope": "fuera del ambito automatico",
        "context_or_level_candidate_not_operational_setup": "contexto, no setup operativo",
        "setup_quality_below_min_auto_quality_4": "calidad por debajo del minimo 4/5",
        "entry_review": "revision de entrada",
        "short": "bajista",
        "long": "alcista",
    }
    return replacements.get(text, text.replace("_", " "))
