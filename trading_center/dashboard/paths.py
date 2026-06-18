from __future__ import annotations

from pathlib import Path

from trading_center.readonly_dashboard import REPO_ROOT


def latest_or_fallback_path(latest_path: Path, fallback_path: Path) -> Path:
    return latest_path if latest_path.exists() else fallback_path


def latest_or_fallback_dir(latest_dir: Path, fallback_dir: Path, required_file: str) -> Path:
    return latest_dir if (latest_dir / required_file).exists() else fallback_dir


def latest_matching_file(
    pattern: str,
    fallback_path: Path,
    *,
    exclude_name_fragments: tuple[str, ...] = (),
    repo_root: Path = REPO_ROOT,
) -> Path:
    matches = [
        path
        for path in repo_root.glob(pattern)
        if path.is_file()
        and not any(fragment.lower() in str(path).lower() for fragment in exclude_name_fragments)
    ]
    if not matches:
        return fallback_path
    return max(matches, key=lambda path: path.stat().st_mtime)
