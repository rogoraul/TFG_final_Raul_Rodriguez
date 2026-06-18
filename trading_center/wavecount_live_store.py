from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from trading_center.wavecount_live_schema import normalize_wavecount_live_frame, schema_frame


def write_wavecount_live_artifacts(
    contexts: pd.DataFrame,
    output_dir: str | Path,
    *,
    run_meta: Mapping[str, Any],
    fixture_inventory: pd.DataFrame,
    anti_lookahead_audit: pd.DataFrame,
    schema: pd.DataFrame | None = None,
) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized = normalize_wavecount_live_frame(contexts)
    csv_path = output_path / "wavecount_live_context.csv"
    json_path = output_path / "wavecount_live_context.json"
    run_meta_path = output_path / "run_meta.json"
    schema_path = output_path / "schema.csv"
    fixture_inventory_path = output_path / "fixture_inventory.csv"
    anti_lookahead_path = output_path / "anti_lookahead_audit.csv"

    normalized.to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(_records_for_json(normalized), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    run_meta_path.write_text(
        json.dumps(dict(run_meta), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (schema if schema is not None else schema_frame()).to_csv(schema_path, index=False)
    fixture_inventory.to_csv(fixture_inventory_path, index=False)
    anti_lookahead_audit.to_csv(anti_lookahead_path, index=False)

    return {
        "csv": csv_path,
        "json": json_path,
        "run_meta": run_meta_path,
        "schema": schema_path,
        "fixture_inventory": fixture_inventory_path,
        "anti_lookahead_audit": anti_lookahead_path,
    }


def _records_for_json(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        records.append({key: _json_value(value) for key, value in record.items()})
    return records


def _json_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
