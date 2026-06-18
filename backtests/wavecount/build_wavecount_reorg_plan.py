from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
WAVECOUNT_ARTIFACTS = REPO_ROOT / "artifacts" / "wavecount"
WAVECOUNT_DOCS = REPO_ROOT / "docs"
WAVECOUNT_CODE = REPO_ROOT / "backtests" / "wavecount"
WAVECOUNT_TESTS = REPO_ROOT / "tests"
DEFAULT_OUTPUT_DIR = WAVECOUNT_ARTIFACTS / "reorg_plan_2026-05-24"


ARTIFACT_PROPOSALS: dict[str, tuple[str, str, str, str]] = {
    "_superseded_2026-05-21": (
        "artifacts/wavecount/99_superseded/_superseded_2026-05-21",
        "superseded",
        "historical",
        "legacy material already separated; preserve",
    ),
    "global_audit_2026-05-24": (
        "artifacts/wavecount/90_global_audits/global_audit_2026-05-24",
        "audit",
        "canonical",
        "global audit and current state snapshot",
    ),
    "reorg_plan_2026-05-24": (
        "artifacts/wavecount/90_global_audits/reorg_plan_2026-05-24",
        "reorg_plan",
        "canonical",
        "reorganization audit/proposal; no files moved",
    ),
    "phase1_pivots_2026-05-17": (
        "artifacts/wavecount/01_pivots_and_swings/phase1_pivots_2026-05-17",
        "phase1",
        "canonical",
        "causal pivot base",
    ),
    "phase1_5_structural_swings_2026-05-17": (
        "artifacts/wavecount/01_pivots_and_swings/phase1_5_structural_swings_2026-05-17",
        "phase1_5",
        "canonical",
        "structural swings",
    ),
    "phase1_6_swing_degrees_2026-05-17": (
        "artifacts/wavecount/01_pivots_and_swings/phase1_6_swing_degrees_2026-05-17",
        "phase1_6",
        "canonical",
        "minor/intermediate/major degrees",
    ),
    "phase2_candidate_counts_2026-05-17": (
        "artifacts/wavecount/02_candidate_counts/phase2_base_counts_2026-05-17",
        "phase2",
        "canonical",
        "base candidate counts",
    ),
    "phase2_1_false_negative_review_2026-05-17": (
        "artifacts/wavecount/02_candidate_counts/phase2_1_invalidations_2026-05-17",
        "phase2_1",
        "diagnostic",
        "hard/soft invalidation review",
    ),
    "phase2_2_impulse_diagnostics_2026-05-17": (
        "artifacts/wavecount/02_candidate_counts/phase2_2_impulse_diagnostics_2026-05-17",
        "phase2_2",
        "diagnostic",
        "impulse absence diagnostics",
    ),
    "phase2_3_visual_review_2026-05-17": (
        "artifacts/wavecount/03_visual_review/phase2_3_visual_review_2026-05-17",
        "phase2_3",
        "canonical",
        "count-only visual review, with h1_m30 and h4_d1 subfolders",
    ),
    "phase2_3_manual_feedback_h1_m30_2026-05-21": (
        "artifacts/wavecount/03_visual_review/phase2_3_manual_feedback_h1_m30_2026-05-21",
        "phase2_3_manual",
        "diagnostic",
        "manual feedback integration",
    ),
    "phase2_3_1_wave5_endpoint_2026-05-21": (
        "artifacts/wavecount/03_visual_review/phase2_3_1_wave5_endpoint_2026-05-21",
        "phase2_3_1",
        "diagnostic",
        "wave 5 endpoint uncertainty",
    ),
    "phase2_3_2_partial123_2026-05-21": (
        "artifacts/wavecount/03_visual_review/phase2_3_2_partial123_2026-05-21",
        "phase2_3_2",
        "diagnostic",
        "partial 1-2-3 laxity",
    ),
    "phase2_3_3_degree_calibration_2026-05-23": (
        "artifacts/wavecount/03_visual_review/phase2_3_3_degree_calibration_2026-05-23",
        "phase2_3_3",
        "diagnostic",
        "degree calibration",
    ),
    "phase2_3_4_h4_d1_visual_closure_2026-05-23": (
        "artifacts/wavecount/03_visual_review/phase2_3_4_h4_d1_visual_closure_2026-05-23",
        "phase2_3_4",
        "canonical",
        "H4/D1 visual closure",
    ),
    "phase2_3_2_4_h4_d1_visual_audit_2026-05-20": (
        "artifacts/wavecount/99_superseded/phase2_3_2_4_h4_d1_visual_audit_2026-05-20",
        "phase2_3_legacy",
        "historical",
        "superseded by phase2_3_4 and later audits",
    ),
    "phase2_3_2_4_visual_reaudit_2026-05-19": (
        "artifacts/wavecount/99_superseded/phase2_3_2_4_visual_reaudit_2026-05-19",
        "phase2_3_legacy",
        "historical",
        "compressed-axis re-audit kept for traceability",
    ),
    "phase2_4_context_2026-05-18": (
        "artifacts/wavecount/04_context_and_corrections/phase2_4_context_2026-05-18",
        "phase2_4",
        "canonical",
        "EMA/EWO/HTF context base",
    ),
    "phase2_4_1_context_visual_audit_2026-05-19": (
        "artifacts/wavecount/04_context_and_corrections/phase2_4_1_context_visual_audit_2026-05-19",
        "phase2_4_1",
        "diagnostic",
        "context visual audit",
    ),
    "phase2_4_2_context_quality_audit_2026-05-23": (
        "artifacts/wavecount/04_context_and_corrections/phase2_4_2_context_quality_2026-05-23",
        "phase2_4_2",
        "canonical",
        "context quality closure",
    ),
    "phase2_4_3_abc_quality_audit_2026-05-23": (
        "artifacts/wavecount/04_context_and_corrections/phase2_4_3_abc_quality_2026-05-23",
        "phase2_4_3",
        "experimental",
        "corrected ABC quality audit",
    ),
    "phase2_4_4_contextual_corrections_2026-05-24": (
        "artifacts/wavecount/04_context_and_corrections/phase2_4_4_contextual_corrections_2026-05-24",
        "phase2_4_4",
        "experimental",
        "contextual corrections",
    ),
    "phase2_4_5_pre_phase25_closure_2026-05-24": (
        "artifacts/wavecount/04_context_and_corrections/phase2_4_5_pre_phase25_closure_2026-05-24",
        "phase2_4_5",
        "canonical",
        "pre-2.5 closure",
    ),
    "phase2_abc_fix_2026-05-20": (
        "artifacts/wavecount/04_context_and_corrections/phase2_abc_fix_2026-05-20",
        "phase2_abc_fix",
        "diagnostic",
        "ABC plotting/ordering fix lineage",
    ),
    "phase2_5_0_guided_context_score_2026-05-24": (
        "artifacts/wavecount/05_guided_profile/phase2_5_0_guided_context_score_2026-05-24",
        "phase2_5_0",
        "canonical",
        "guided context scoring",
    ),
    "phase2_5_1_guided_impulse_profile_2026-05-24": (
        "artifacts/wavecount/05_guided_profile/phase2_5_1_guided_impulse_profile_2026-05-24",
        "phase2_5_1",
        "canonical",
        "minimal guided impulse profile",
    ),
    "phase2_5_2_guided_impulse_expansion_2026-05-24": (
        "artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24",
        "phase2_5_2",
        "canonical",
        "controlled H4/D1 expansion",
    ),
    "phase2_5_2b_h1_h4_aux_expansion_2026-05-24": (
        "artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24",
        "phase2_5_2b",
        "auxiliary",
        "H1/H4 auxiliary and prominence",
    ),
    "phase2_5_3_descriptive_stats_2026-05-24": (
        "artifacts/wavecount/05_guided_profile/phase2_5_3_descriptive_stats_2026-05-24",
        "phase2_5_3",
        "canonical",
        "descriptive statistics",
    ),
}

DOC_PROPOSAL_ROOT = "docs/wavecount"


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _resolve_image(value: str, csv_path: Path) -> bool:
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [
        REPO_ROOT / raw,
        csv_path.parent / raw,
        csv_path.parent.parent / raw,
    ]
    return any(path.exists() for path in candidates)


def _image_refs(frame: pd.DataFrame) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for column in [c for c in frame.columns if "path" in c.lower()]:
        for value in frame[column].dropna().astype(str):
            if value.lower().endswith(".png"):
                refs.append((column, value))
    return refs


def _counts(path: Path) -> dict[str, int | bool]:
    if not path.exists():
        return {
            "contains_csv": False,
            "contains_png": False,
            "contains_report": False,
            "contains_run_meta": False,
            "csv_count": 0,
            "png_count": 0,
            "md_count": 0,
        }
    files = [p for p in path.rglob("*") if p.is_file()]
    csv_count = sum(1 for p in files if p.suffix.lower() == ".csv")
    png_count = sum(1 for p in files if p.suffix.lower() == ".png")
    md_count = sum(1 for p in files if p.suffix.lower() == ".md")
    report_count = sum(1 for p in files if p.name.upper().startswith("WAVECOUNT") and p.suffix.lower() == ".md")
    return {
        "contains_csv": csv_count > 0,
        "contains_png": png_count > 0,
        "contains_report": report_count > 0,
        "contains_run_meta": (path / "run_meta.json").exists(),
        "csv_count": csv_count,
        "png_count": png_count,
        "md_count": md_count,
    }


def _phase_from_name(name: str) -> str:
    if name.startswith("phase1_5"):
        return "1.5"
    if name.startswith("phase1_6"):
        return "1.6"
    if name.startswith("phase1"):
        return "1"
    if name.startswith("phase2_5_2b"):
        return "2.5.2b"
    if name.startswith("phase2_5_"):
        return name.split("_")[0].replace("phase", "") + "." + name.split("_")[1] + "." + name.split("_")[2]
    if name.startswith("phase2_4_"):
        return "2.4." + name.split("_")[2]
    if name.startswith("phase2_3_"):
        return "2.3." + name.split("_")[2]
    if name.startswith("phase2_"):
        return "2." + name.split("_")[1]
    if name.startswith("phase2"):
        return "2"
    if "global_audit" in name:
        return "global_audit"
    if "reorg_plan" in name:
        return "reorg_plan"
    if "superseded" in name:
        return "superseded"
    return "unknown"


def build_artifact_inventory() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted([p for p in WAVECOUNT_ARTIFACTS.iterdir() if p.is_dir()], key=lambda p: p.name):
        counts = _counts(path)
        current_refs = current_missing = nested_refs = nested_missing = 0
        for csv_path in path.rglob("*.csv"):
            frame = _read_csv(csv_path)
            refs = _image_refs(frame)
            is_current_table = csv_path.parent == path / "tables"
            if is_current_table:
                current_refs += len(refs)
                current_missing += sum(1 for _, ref in refs if not _resolve_image(ref, csv_path))
            else:
                nested_refs += len(refs)
                nested_missing += sum(1 for _, ref in refs if not _resolve_image(ref, csv_path))
        proposal = ARTIFACT_PROPOSALS.get(path.name)
        proposed_path, phase, status, purpose = proposal or (
            f"artifacts/wavecount/99_superseded/{path.name}",
            _phase_from_name(path.name),
            "needs_manual_classification",
            "not recognized by proposal map",
        )
        is_historical = status in {"historical", "superseded"}
        rows.append(
            {
                "current_name": path.name,
                "current_path": _rel(path),
                "phase_or_subphase": phase,
                "purpose": purpose,
                "is_current": status in {"canonical", "auxiliary", "diagnostic", "experimental"},
                "is_historical_or_superseded": is_historical,
                "is_diagnostic": status in {"diagnostic", "experimental", "auxiliary"},
                **counts,
                "current_table_image_refs": current_refs,
                "current_table_missing_image_refs": current_missing,
                "nested_image_refs": nested_refs,
                "nested_missing_image_refs": nested_missing,
                "recommended_status": status,
                "proposed_path": proposed_path,
                "path_risk": "has broken current-table image refs"
                if current_missing
                else "nested refs need rewrite"
                if nested_missing
                else "ok",
                "conservation_policy": "preserve; no deletion",
            }
        )
    return pd.DataFrame(rows)


def _doc_type(name: str, text: str) -> str:
    lower = name.lower()
    if "manifest" in lower or "artifacts" in lower:
        return "indice/manifest"
    if "formalizacion" in lower:
        return "formalizacion"
    if "auditoria" in lower or "audit" in lower:
        return "auditoria"
    if "revision" in lower or "visual" in lower:
        return "revision visual"
    if "cierre" in lower:
        return "cierre"
    if "fase" in lower:
        return "reporte de fase"
    if "h4_d1" in lower:
        return "metodologia"
    return "metodologia"


def _doc_phase(name: str) -> str:
    stem = name.replace("WAVECOUNT_", "").replace(".md", "")
    if "FASE1_5" in stem:
        return "1.5"
    if "FASE1_6" in stem:
        return "1.6"
    if "FASE1" in stem:
        return "1"
    if "FASE2_5_2B" in stem:
        return "2.5.2b"
    if "FASE2_5_3" in stem:
        return "2.5.3"
    if "FASE2_5_2" in stem:
        return "2.5.2"
    if "FASE2_5_1" in stem:
        return "2.5.1"
    if "FASE2_5_0" in stem:
        return "2.5.0"
    if "FASE2_4_5" in stem:
        return "2.4.5"
    if "FASE2_4_4" in stem:
        return "2.4.4"
    if "FASE2_4_3" in stem:
        return "2.4.3"
    if "FASE2_4_2" in stem:
        return "2.4.2"
    if "FASE2_4_1" in stem:
        return "2.4.1"
    if "FASE2_4" in stem:
        return "2.4"
    if "FASE2_3_4" in stem:
        return "2.3.4"
    if "FASE2_3_3" in stem:
        return "2.3.3"
    if "FASE2_3_2" in stem:
        return "2.3.2"
    if "FASE2_3_1" in stem:
        return "2.3.1"
    if "FASE2_3" in stem:
        return "2.3"
    if "FASE2_2" in stem:
        return "2.2"
    if "FASE2_1" in stem:
        return "2.1"
    if "FASE2" in stem:
        return "2"
    if "AUDITORIA_GLOBAL" in stem:
        return "global_audit"
    if "REORGANIZACION" in stem:
        return "reorg_plan"
    return "general"


def _proposed_doc_path(name: str, phase: str, doc_type: str) -> str:
    if name == "WAVECOUNT_ARTIFACTS_MANIFEST.md":
        return f"{DOC_PROPOSAL_ROOT}/INDEX.md"
    if phase in {"1", "1.5", "1.6"}:
        return f"{DOC_PROPOSAL_ROOT}/02_pivots_and_swings/{name}"
    if phase.startswith("2.3") or phase in {"2", "2.1", "2.2"}:
        return f"{DOC_PROPOSAL_ROOT}/03_counts_and_visual_review/{name}"
    if phase.startswith("2.4"):
        return f"{DOC_PROPOSAL_ROOT}/04_context_and_corrections/{name}"
    if phase.startswith("2.5"):
        return f"{DOC_PROPOSAL_ROOT}/05_guided_profile/{name}"
    if phase in {"global_audit", "reorg_plan"} or doc_type == "auditoria":
        return f"{DOC_PROPOSAL_ROOT}/90_audits/{name}"
    if "FORMALIZACION" in name:
        return f"{DOC_PROPOSAL_ROOT}/01_formalizacion/{name}"
    return f"{DOC_PROPOSAL_ROOT}/99_legacy/{name}"


def build_docs_inventory() -> pd.DataFrame:
    rows = []
    for path in sorted(WAVECOUNT_DOCS.glob("WAVECOUNT_*.md"), key=lambda p: p.name):
        text = _text(path)
        phase = _doc_phase(path.name)
        doc_type = _doc_type(path.name, text)
        contains_old_refs = any(token in text for token in ["_compressed_axis", "phase2_3_2_4_visual_reaudit", "phase2_3_2_4_h4_d1_visual_audit"])
        contains_abc_legacy = "abc legacy" in text.lower() or ("phase2_abc_fix" not in text and "ABC" in text and "legacy" in text.lower())
        is_root_keeper = path.name in {"WAVECOUNT_ARTIFACTS_MANIFEST.md", "WAVECOUNT_AUDITORIA_GLOBAL_2026-05-24.md"}
        current_status = "current" if phase in {"2.5.3", "global_audit", "reorg_plan"} or is_root_keeper else "historical_or_phase_doc"
        rows.append(
            {
                "doc_name": path.name,
                "current_path": _rel(path),
                "topic": path.stem.replace("WAVECOUNT_", "").lower(),
                "phase": phase,
                "doc_type": doc_type,
                "is_current": current_status == "current",
                "superseded_by": "later phase docs / WAVECOUNT_ARTIFACTS_MANIFEST.md" if current_status != "current" else "",
                "keep_in_docs_root": is_root_keeper,
                "future_proposed_path": _proposed_doc_path(path.name, phase, doc_type),
                "contains_old_folder_refs": contains_old_refs,
                "contains_compressed_axis_refs": "_compressed_axis" in text,
                "contains_abc_legacy_refs": contains_abc_legacy,
                "recommendation": "keep root index/audit" if is_root_keeper else "move only after creating redirects or index",
            }
        )
    return pd.DataFrame(rows)


def _code_category(path: Path) -> str:
    name = path.name
    if name.startswith("wavecount_") and not name.endswith("_gallery.py"):
        if name in {"wavecount_pivots.py", "wavecount_structure.py", "wavecount_degrees.py", "wavecount_counts.py", "wavecount_context.py", "wavecount_plotting.py", "wavecount_config.py"}:
            return "core logic"
    if "gallery" in name:
        return "gallery"
    if name.startswith("build_"):
        if "audit" in name or "closure" in name or "feedback" in name or "readiness" in name or "reorg" in name:
            return "audit/builder"
        return "artifact builder"
    if "fix" in name or "reaudit" in name or "endpoint" in name or "partial" in name:
        return "fix/diagnostic"
    if name == "__init__.py":
        return "package"
    return "utility/other"


def build_code_inventory() -> pd.DataFrame:
    rows = []
    for path in sorted(WAVECOUNT_CODE.glob("*.py"), key=lambda p: p.name):
        tests = [p.name for p in sorted(WAVECOUNT_TESTS.glob("test_wavecount*.py")) if path.stem.replace("build_", "") in p.stem or path.stem in p.stem]
        category = _code_category(path)
        if category == "core logic":
            proposed_group = "backtests/wavecount/core/"
            safe = False
        elif category in {"artifact builder", "audit/builder"}:
            proposed_group = "backtests/wavecount/builders_or_audits/"
            safe = False
        elif category == "gallery":
            proposed_group = "backtests/wavecount/galleries/"
            safe = False
        else:
            proposed_group = "backtests/wavecount/utils_or_legacy/"
            safe = False
        rows.append(
            {
                "file_name": path.name,
                "current_path": _rel(path),
                "category": category,
                "line_count": len(_text(path).splitlines()),
                "tests_associated": "|".join(tests),
                "future_group_proposal": proposed_group,
                "move_now": False,
                "safe_to_move_without_import_rewrite": safe,
                "recommendation": "do not move code in first migration; imports/tests are stable",
            }
        )
    return pd.DataFrame(rows)


def build_current_organization_issues(artifact_inventory: pd.DataFrame, docs_inventory: pd.DataFrame) -> pd.DataFrame:
    rows = []
    long_names = artifact_inventory[artifact_inventory["current_name"].str.len() > 48]
    if not long_names.empty:
        rows.append(("long_artifact_names", "medium", int(len(long_names)), "group by numbered folders to reduce visual noise"))
    broken = artifact_inventory[artifact_inventory["current_table_missing_image_refs"].astype(int) > 0]
    if not broken.empty:
        rows.append(("broken_current_table_image_refs", "high", int(broken["current_table_missing_image_refs"].sum()), "rewrite chart_path during migration"))
    old_docs = docs_inventory[docs_inventory["contains_old_folder_refs"].astype(bool)]
    if not old_docs.empty:
        rows.append(("old_folder_refs_in_docs", "medium", int(len(old_docs)), "update docs or route via index"))
    rows.append(("too_many_wavecount_docs_in_root", "medium", int(len(docs_inventory)), "create docs/wavecount/INDEX.md and group docs later"))
    rows.append(("code_flat_but_stable", "low", int(len(build_code_inventory())), "do not move code until artifact/doc migration is finished"))
    return pd.DataFrame(rows, columns=["issue_id", "severity", "count", "recommendation"])


def build_proposed_artifact_structure() -> pd.DataFrame:
    rows = [
        ("artifacts/wavecount/00_manifest", "indices/manifests generated after migration", "create"),
        ("artifacts/wavecount/01_pivots_and_swings", "phase 1 to 1.6 base structures", "create"),
        ("artifacts/wavecount/02_candidate_counts", "phase 2 base counts and invalidation diagnostics", "create"),
        ("artifacts/wavecount/03_visual_review", "phase 2.3 visual review and manual diagnostics", "create"),
        ("artifacts/wavecount/04_context_and_corrections", "EMA/EWO/HTF and correction/ABC work", "create"),
        ("artifacts/wavecount/05_guided_profile", "phase 2.5 guided profile and stats", "create"),
        ("artifacts/wavecount/90_global_audits", "global audits and reorg plans", "create"),
        ("artifacts/wavecount/99_superseded", "historical or superseded artifacts", "create"),
    ]
    return pd.DataFrame(rows, columns=["proposed_path", "purpose", "action"])


def build_proposed_docs_structure() -> pd.DataFrame:
    rows = [
        ("docs/wavecount/INDEX.md", "single entry point, current status and review instructions", "create first"),
        ("docs/wavecount/01_formalizacion", "formalization and methodological overview", "future"),
        ("docs/wavecount/02_pivots_and_swings", "phase 1 to 1.6 docs", "future"),
        ("docs/wavecount/03_counts_and_visual_review", "phase 2 and 2.3 docs", "future"),
        ("docs/wavecount/04_context_and_corrections", "phase 2.4 docs", "future"),
        ("docs/wavecount/05_guided_profile", "phase 2.5 docs", "future"),
        ("docs/wavecount/90_audits", "global/reorg audits", "future"),
        ("docs/wavecount/99_legacy", "old docs kept for traceability", "future"),
    ]
    return pd.DataFrame(rows, columns=["proposed_path", "purpose", "action"])


def build_migration_mapping(artifact_inventory: pd.DataFrame, docs_inventory: pd.DataFrame, code_inventory: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in artifact_inventory.iterrows():
        rows.append(
            {
                "current_path": row["current_path"],
                "proposed_path": row["proposed_path"],
                "item_type": "artifact_dir",
                "status": row["recommended_status"],
                "migration_priority": "high" if row["recommended_status"] in {"canonical", "auxiliary"} else "medium",
                "risk": "high" if int(row["current_table_missing_image_refs"]) else "medium",
                "requires_csv_path_rewrite": bool(int(row["current_table_image_refs"]) or int(row["nested_image_refs"])),
                "requires_md_update": True,
                "requires_run_meta_update": bool(row["contains_run_meta"]),
                "safe_to_move": False,
                "notes": row["purpose"],
            }
        )
    for _, row in docs_inventory.iterrows():
        rows.append(
            {
                "current_path": row["current_path"],
                "proposed_path": row["future_proposed_path"],
                "item_type": "doc",
                "status": "root_keep" if row["keep_in_docs_root"] else "phase_doc",
                "migration_priority": "low" if row["keep_in_docs_root"] else "medium",
                "risk": "medium",
                "requires_csv_path_rewrite": False,
                "requires_md_update": True,
                "requires_run_meta_update": False,
                "safe_to_move": False,
                "notes": row["recommendation"],
            }
        )
    for _, row in code_inventory.iterrows():
        rows.append(
            {
                "current_path": row["current_path"],
                "proposed_path": row["future_group_proposal"] + row["file_name"],
                "item_type": "code",
                "status": "stable_flat_code",
                "migration_priority": "defer",
                "risk": "high",
                "requires_csv_path_rewrite": False,
                "requires_md_update": False,
                "requires_run_meta_update": False,
                "safe_to_move": False,
                "notes": "defer code movement; imports/tests would need rewrite",
            }
        )
    return pd.DataFrame(rows)


def build_migration_risks() -> pd.DataFrame:
    rows = [
        ("chart_path_breakage", "high", "CSV/Markdown image refs can break when artifact dirs move", "rewrite paths and regenerate .md indexes"),
        ("run_meta_traceability", "medium", "run_meta paths will point to old dirs", "update or add migration_note without pretending data was regenerated"),
        ("docs_link_rot", "medium", "root docs link to old artifacts", "create index/redirect docs and update only current references"),
        ("canonical_confusion", "high", "historical artifacts may look current", "use 99_superseded and status labels"),
        ("code_import_breakage", "high", "moving Python files breaks imports/tests", "do not move code in first migration"),
        ("git_diff_size", "medium", "moving images creates large diffs", "prefer copy/move only vigentes; leave historical documented"),
    ]
    return pd.DataFrame(rows, columns=["risk_id", "severity", "description", "mitigation"])


def build_reorg_execution_plan() -> pd.DataFrame:
    rows = [
        ("A1", "create target artifact folders", "future_migration", "no data changes"),
        ("A2", "move/copy only current canonical and auxiliary artifacts first", "future_migration", "preserve old paths until validated"),
        ("A3", "rewrite CSV chart_path fields to new locations", "future_migration", "required before using moved artifacts"),
        ("A4", "regenerate Markdown image indexes", "future_migration", "use existing index builder or new reorg helper"),
        ("A5", "move historical material to 99_superseded or leave documented", "future_migration", "no deletion"),
        ("B1", "create docs/wavecount/INDEX.md", "future_migration", "safe first docs step"),
        ("B2", "move docs only after index/redirect plan", "future_migration", "avoid breaking current references"),
        ("C1", "validate all image refs and run_meta paths", "future_validation", "must be zero broken current refs"),
        ("C2", "run py_compile and WaveCount tests if code/docs helpers touched", "future_validation", "no backtests"),
        ("C3", "git diff --check", "future_validation", "final hygiene"),
    ]
    return pd.DataFrame(rows, columns=["step_id", "action", "phase", "notes"])


def _write_report(output_dir: Path, meta: dict[str, Any]) -> None:
    lines = [
        "# WaveCount Reorganization Plan 2026-05-24",
        "",
        "## Scope",
        "",
        "This is an audit and design plan only. No files or folders were moved, renamed or deleted.",
        "",
        "## Main Findings",
        "",
        f"- Artifact directories inventoried: {meta['artifact_dirs']}",
        f"- WaveCount docs inventoried: {meta['docs']}",
        f"- WaveCount code files inventoried: {meta['code_files']}",
        f"- Current-table image refs broken: {meta['current_table_missing_image_refs']}",
        f"- Proposed mapping duplicate destinations: {meta['duplicate_proposed_paths']}",
        "",
        "The main organization problem is not code. It is artifact/doc navigation and path traceability after many phases.",
        "",
        "## Recommendation",
        "",
        "- Reorganize artifacts by phase group.",
        "- Create a docs/wavecount index before moving docs.",
        "- Do not move Python code in the first migration.",
        "- Rewrite CSV image paths and regenerate Markdown indexes during the actual migration.",
        "- Keep historical material; do not delete.",
        "",
        "## Next Real Migration",
        "",
        "Run a separate controlled migration phase after reviewing `tables/migration_mapping.csv`.",
    ]
    (output_dir / "WAVECOUNT_REORG_PLAN_2026-05-24.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_reorg_plan(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    start = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    artifact_inventory = build_artifact_inventory()
    docs_inventory = build_docs_inventory()
    code_inventory = build_code_inventory()
    issues = build_current_organization_issues(artifact_inventory, docs_inventory)
    artifact_structure = build_proposed_artifact_structure()
    docs_structure = build_proposed_docs_structure()
    migration_mapping = build_migration_mapping(artifact_inventory, docs_inventory, code_inventory)
    risks = build_migration_risks()
    execution_plan = build_reorg_execution_plan()

    tables = {
        "artifact_inventory": artifact_inventory,
        "docs_inventory": docs_inventory,
        "code_inventory": code_inventory,
        "current_organization_issues": issues,
        "proposed_artifact_structure": artifact_structure,
        "proposed_docs_structure": docs_structure,
        "migration_mapping": migration_mapping,
        "migration_risks": risks,
        "reorg_execution_plan": execution_plan,
    }
    for name, frame in tables.items():
        frame.to_csv(tables_dir / f"{name}.csv", index=False)

    duplicate_paths = migration_mapping[
        migration_mapping["proposed_path"].duplicated(keep=False)
        & migration_mapping["item_type"].ne("code")
    ]
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": _rel(Path(__file__)),
        "output_dir": _rel(output_dir),
        "artifact_dirs": int(len(artifact_inventory)),
        "docs": int(len(docs_inventory)),
        "code_files": int(len(code_inventory)),
        "current_table_missing_image_refs": int(artifact_inventory["current_table_missing_image_refs"].sum()),
        "nested_missing_image_refs": int(artifact_inventory["nested_missing_image_refs"].sum()),
        "duplicate_proposed_paths": int(len(duplicate_paths)),
        "no_files_moved": True,
        "no_files_deleted": True,
        "no_rules_changed": True,
        "elapsed_seconds": round(perf_counter() - start, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, meta)
    return meta


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount reorganization plan without moving files.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta = build_reorg_plan(output_dir=args.output_dir)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
