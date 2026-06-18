from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "artifacts" / "wavecount"
SUPERSEDED_DIR_NAME = "_superseded_2026-05-21"


@dataclass(frozen=True)
class ImageRef:
    row_number: int
    row_label: str
    column: str
    source_value: str
    target: Path


def _is_image_path_column(name: str) -> bool:
    lowered = name.lower()
    return "path" in lowered and any(token in lowered for token in ("chart", "image", "png"))


def _is_png_value(value: str) -> bool:
    return value.strip().lower().endswith(".png")


def _artifact_root_for_csv(csv_path: Path) -> Path:
    if csv_path.parent.name == "tables":
        return csv_path.parent.parent
    return csv_path.parent


def _candidate_search_roots(root: Path) -> list[Path]:
    roots = [REPO_ROOT, root]
    for path in root.rglob("*"):
        if not path.is_dir():
            continue
        if SUPERSEDED_DIR_NAME in path.parts:
            continue
        roots.append(path)
    # Preserve order while removing duplicates.
    unique: list[Path] = []
    seen: set[Path] = set()
    for item in roots:
        resolved = item.resolve()
        if resolved not in seen:
            unique.append(item)
            seen.add(resolved)
    return unique


def _absolute_pair_columns(column: str) -> tuple[str, ...]:
    candidates = [
        f"{column}_absolute",
        f"{column}_absolute_out",
        column.replace("_relative", "_absolute"),
        column.replace("_relative", "_absolute_out"),
    ]
    if column == "chart_path":
        candidates.extend(["chart_path_absolute", "chart_path_absolute_out"])
    if column == "context_chart_path":
        candidates.append("context_chart_path_absolute")
    if column == "fixed_chart_path":
        candidates.append("fixed_chart_path_absolute")
    if column == "fixed_context_chart_path":
        candidates.append("fixed_context_chart_path_absolute")
    return tuple(dict.fromkeys(candidates))


def _resolve_image_path(
    *,
    value: str,
    row: dict[str, str],
    column: str,
    csv_path: Path,
    artifact_root: Path,
    search_roots: Iterable[Path],
) -> Path | None:
    raw = value.strip()
    if not raw:
        return None

    path = Path(raw)
    if path.is_absolute() and path.exists():
        return path

    for abs_col in _absolute_pair_columns(column):
        abs_value = (row.get(abs_col) or "").strip()
        if abs_value and _is_png_value(abs_value):
            abs_path = Path(abs_value)
            if abs_path.is_absolute() and abs_path.exists():
                return abs_path

    candidates = [artifact_root / raw, csv_path.parent / raw, REPO_ROOT / raw]
    candidates.extend(base / raw for base in search_roots)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _row_label(row: dict[str, str], row_number: int) -> str:
    parts = []
    for col in (
        "candidate_order",
        "candidate_id",
        "example_id",
        "symbol",
        "timeframe",
        "swing_degree",
        "review_category",
        "phase",
        "review_phase",
    ):
        value = (row.get(col) or "").strip()
        if value:
            parts.append(f"{col}={value}")
    return " | ".join(parts) if parts else f"row={row_number}"


def _markdown_link(target: Path, from_dir: Path) -> str:
    rel = os.path.relpath(target, from_dir)
    return rel.replace(os.sep, "/")


def build_index_for_csv(csv_path: Path, *, root: Path, search_roots: Iterable[Path]) -> dict[str, object] | None:
    artifact_root = _artifact_root_for_csv(csv_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError(f"CSV has duplicate headers: {csv_path}")
        path_columns = [name for name in fieldnames if _is_image_path_column(name)]
        if not path_columns:
            return None

        refs: list[ImageRef] = []
        unresolved: list[dict[str, object]] = []
        seen: set[tuple[int, Path]] = set()
        for row_number, row in enumerate(reader, start=2):
            label = _row_label(row, row_number)
            for column in path_columns:
                value = (row.get(column) or "").strip()
                if not value or not _is_png_value(value):
                    continue
                target = _resolve_image_path(
                    value=value,
                    row=row,
                    column=column,
                    csv_path=csv_path,
                    artifact_root=artifact_root,
                    search_roots=search_roots,
                )
                if target is None:
                    unresolved.append({"row": row_number, "column": column, "value": value})
                    continue
                resolved = target.resolve()
                key = (row_number, resolved)
                if key in seen:
                    continue
                seen.add(key)
                refs.append(
                    ImageRef(
                        row_number=row_number,
                        row_label=label,
                        column=column,
                        source_value=value,
                        target=target,
                    )
                )

    if not refs and not unresolved:
        return None

    output_path = csv_path.with_suffix(".md")
    generated_at = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"# Image index: {csv_path.name}",
        "",
        f"Generado: {generated_at}",
        "",
        f"CSV fuente: [{csv_path.name}]({csv_path.name})",
        "",
        f"- filas con imagen/enlace resuelto: {len({ref.row_number for ref in refs})}",
        f"- imagenes enlazadas: {len(refs)}",
        f"- imagenes no resueltas: {len(unresolved)}",
        "",
        "Este indice solo facilita abrir graficos desde los CSV. No cambia datos,",
        "conteos, reglas, EMAs/EWO ni resultados.",
        "",
    ]

    if refs:
        lines.extend(
            [
                "## Imagenes",
                "",
                "| fila CSV | referencia | columna | imagen |",
                "| --- | --- | --- | --- |",
            ]
        )
        for ref in refs:
            link = _markdown_link(ref.target, output_path.parent)
            safe_label = ref.row_label.replace("|", "\\|")
            lines.append(
                f"| {ref.row_number} | `{safe_label}` | `{ref.column}` | [abrir imagen](<{link}>) |"
            )
        lines.append("")

    if unresolved:
        lines.extend(
            [
                "## No resueltas",
                "",
                "| fila CSV | columna | valor |",
                "| --- | --- | --- |",
            ]
        )
        for item in unresolved:
            lines.append(f"| {item['row']} | `{item['column']}` | `{item['value']}` |")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "csv": str(csv_path.relative_to(REPO_ROOT)),
        "markdown": str(output_path.relative_to(REPO_ROOT)),
        "image_links": len(refs),
        "unresolved": len(unresolved),
    }


def build_indexes(root: Path = DEFAULT_ROOT) -> dict[str, object]:
    root = root.resolve()
    search_roots = _candidate_search_roots(root)
    outputs = []
    for csv_path in sorted(root.rglob("*.csv")):
        if SUPERSEDED_DIR_NAME in csv_path.parts:
            continue
        result = build_index_for_csv(csv_path, root=root, search_roots=search_roots)
        if result:
            outputs.append(result)
    return {
        "root": str(root),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "indexes_created": len(outputs),
        "image_links": sum(int(item["image_links"]) for item in outputs),
        "unresolved": sum(int(item["unresolved"]) for item in outputs),
        "outputs": outputs,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Markdown image indexes for WaveCount CSV artifacts.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--summary-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = build_indexes(args.root)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
