"""Writers for normalized Trading Center snapshot artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from trading_center.snapshot_schema import normalize_snapshot_frame


def write_snapshot_artifacts(
    snapshot: pd.DataFrame,
    output_dir: str | Path,
    *,
    run_meta: Mapping[str, Any],
    schema: pd.DataFrame | None = None,
    source_inventory: pd.DataFrame | None = None,
) -> dict[str, Path]:
    """Write CSV/JSON snapshot artifacts plus optional schema and inventory files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized = normalize_snapshot_frame(snapshot)
    csv_path = output_path / "live_context_snapshot.csv"
    json_path = output_path / "live_context_snapshot.json"
    run_meta_path = output_path / "run_meta.json"
    schema_path = output_path / "schema.csv"
    source_inventory_path = output_path / "source_inventory.csv"

    normalized.to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(_records_for_json(normalized), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    run_meta_path.write_text(
        json.dumps(dict(run_meta), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    if schema is not None:
        schema.to_csv(schema_path, index=False)
    if source_inventory is not None:
        source_inventory.to_csv(source_inventory_path, index=False)

    written = {
        "csv": csv_path,
        "json": json_path,
        "run_meta": run_meta_path,
    }
    if schema is not None:
        written["schema"] = schema_path
    if source_inventory is not None:
        written["source_inventory"] = source_inventory_path
    return written


def _records_for_json(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into JSON-safe row dictionaries."""
    records: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        records.append({key: _json_value(value) for key, value in record.items()})
    return records


def _json_value(value: object) -> object:
    """Normalize pandas/null timestamp values before JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
