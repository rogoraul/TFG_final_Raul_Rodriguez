"""Database configuration loader for local SQL access.

The loader prefers process environment variables and falls back to `.env` /
`.env.local` files in the repository root. It never prints secret values.
"""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "trading_data",
}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_CANDIDATE_FILES = (
    _REPO_ROOT / ".env",
    _REPO_ROOT / ".env.local",
)

_ENV_TO_CONFIG = {
    "TRADING_DB_HOST": "host",
    "TRADING_DB_PORT": "port",
    "TRADING_DB_USER": "user",
    "TRADING_DB_PASSWORD": "password",
    "TRADING_DB_DATABASE": "database",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines from an env file."""
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_env_candidates() -> tuple[dict[str, str], list[str]]:
    """Merge supported env files in precedence order."""
    merged = {}
    used_files = []
    for path in _ENV_CANDIDATE_FILES:
        file_values = _parse_env_file(path)
        if file_values:
            merged.update(file_values)
            used_files.append(path.name)
    return merged, used_files


def _coerce_port(raw_value) -> int:
    """Return a valid DB port, falling back to the default on invalid input."""
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_DB_CONFIG["port"]


def load_db_config() -> tuple[dict[str, object], str]:
    """Load DB config and a non-secret source summary for audit messages."""
    env_file_values, used_files = _load_env_candidates()
    config = DEFAULT_DB_CONFIG.copy()
    sources = []

    for env_name, config_key in _ENV_TO_CONFIG.items():
        raw_value = os.getenv(env_name)
        source = "environment"
        if raw_value is None:
            raw_value = env_file_values.get(env_name)
            source = ",".join(used_files) if used_files else "defaults"

        if raw_value is None:
            continue

        config[config_key] = (
            _coerce_port(raw_value) if config_key == "port" else raw_value
        )
        sources.append(f"{config_key}:{source}")

    source_text = "; ".join(sources) if sources else "defaults"
    return config, source_text


def get_db_config() -> dict[str, object]:
    """Return only the resolved DB config dictionary."""
    config, _ = load_db_config()
    return config
