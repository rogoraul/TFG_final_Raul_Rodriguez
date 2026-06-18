from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def load_latest_manifest_metadata(latest_manifest_json: Path) -> dict[str, Any]:
    state: dict[str, Any] = {
        "path": str(latest_manifest_json),
        "exists": latest_manifest_json.exists(),
        "fingerprint": "",
        "mtime_utc": "",
        "manifest_timestamp": "",
        "refresh_decision": "",
        "component_count": 0,
        "parse_status": "missing",
    }
    if not latest_manifest_json.exists():
        return state
    content = latest_manifest_json.read_bytes()
    stat = latest_manifest_json.stat()
    state["fingerprint"] = hashlib.sha256(content).hexdigest()
    state["mtime_utc"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    state["parse_status"] = "raw"
    try:
        payload = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        state["parse_status"] = "invalid_json"
        return state
    if isinstance(payload, dict):
        state["manifest_timestamp"] = str(payload.get("generated_at", "") or "")
        state["refresh_decision"] = str(payload.get("refresh_decision", "") or "")
        components = payload.get("components")
        if isinstance(components, list):
            state["component_count"] = len(components)
        state["parse_status"] = "parsed"
    return state


def build_manifest_refresh_state(
    latest_manifest_json: Path,
    *,
    checked_at: datetime | None = None,
    loaded_at_utc: str = "",
    reload_reason: str = "initial_state",
) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(timezone.utc)
    state = load_latest_manifest_metadata(latest_manifest_json)
    state["checked_at_utc"] = checked_at.isoformat()
    state["loaded_at_utc"] = loaded_at_utc or checked_at.isoformat()
    state["reload_reason"] = reload_reason
    return state


def maybe_refresh_dash_data(
    previous_state: dict[str, Any] | None,
    latest_manifest_json: Path,
    *,
    data_builder: Callable[[], dict[str, Any]],
    checked_at: datetime | None = None,
) -> tuple[bool, dict[str, Any], dict[str, Any] | None]:
    checked_at = checked_at or datetime.now(timezone.utc)
    current = build_manifest_refresh_state(
        latest_manifest_json,
        checked_at=checked_at,
        loaded_at_utc=(previous_state or {}).get("loaded_at_utc", ""),
        reload_reason="unchanged",
    )
    previous_fingerprint = (previous_state or {}).get("fingerprint", "")
    previous_exists = bool((previous_state or {}).get("exists", False))
    if current["fingerprint"] != previous_fingerprint or current["exists"] != previous_exists:
        refreshed = data_builder()
        current["loaded_at_utc"] = checked_at.isoformat()
        current["reload_reason"] = "manifest_changed"
        return True, current, refreshed
    current["loaded_at_utc"] = (previous_state or {}).get("loaded_at_utc", current["loaded_at_utc"])
    return False, current, None


def build_refresh_status_payload(
    manifest_state: dict[str, Any] | None,
    *,
    auto_refresh_enabled: bool,
) -> dict[str, Any]:
    manifest_state = manifest_state or {}
    return {
        "auto_refresh_enabled": auto_refresh_enabled,
        "manifest_exists": bool(manifest_state.get("exists", False)),
        "manifest_timestamp": str(manifest_state.get("manifest_timestamp", "") or ""),
        "refresh_decision": str(manifest_state.get("refresh_decision", "") or ""),
        "checked_at_utc": str(manifest_state.get("checked_at_utc", "") or ""),
        "loaded_at_utc": str(manifest_state.get("loaded_at_utc", "") or ""),
        "reload_reason": str(manifest_state.get("reload_reason", "") or ""),
    }


def refresh_decision_label(value: str) -> tuple[str, str]:
    decision = str(value or "").strip()
    labels = {
        "refresh_allowed": ("Refresh OK", "ok"),
        "refresh_allowed_with_warnings": ("Refresh con avisos", "warning"),
        "use_last_good_artifacts": ("Usando last-good", "warning"),
        "refresh_blocked": ("Refresh bloqueado", "danger"),
        "blocked": ("Refresh bloqueado", "danger"),
    }
    return labels.get(decision, ("Sin estado refresh", "muted"))
