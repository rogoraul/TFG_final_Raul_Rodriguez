from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from .wavecount_context_gallery import build_context_gallery
from .wavecount_visual_review_gallery import VisualReviewSpec, build_visual_review_gallery


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE23_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
DEFAULT_PHASE24_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h4_d1"


H4_D1_VISUAL_REVIEW_SPECS = (
    VisualReviewSpec("forex_eurusd_h4", "Forex Majors", "EURUSD.r", "H4", 420),
    VisualReviewSpec("forex_gbpusd_h4", "Forex Majors", "GBPUSD.r", "H4", 420),
    VisualReviewSpec("forex_usdjpy_h4", "Forex Majors", "USDJPY.r", "H4", 420),
    VisualReviewSpec("forex_audjpy_h4", "Forex Majors", "AUDJPY.r", "H4", 420),
    VisualReviewSpec("forex_eurjpy_h4", "Forex Majors", "EURJPY.r", "H4", 420),
    VisualReviewSpec("forex_gbpjpy_h4", "Forex Majors", "GBPJPY.r", "H4", 420),
    VisualReviewSpec("metals_xauusd_h4", "Metals", "XAUUSD.r", "H4", 420),
    VisualReviewSpec("metals_xagusd_h4", "Metals", "XAGUSD.r", "H4", 420),
    VisualReviewSpec("metals_xptusd_h4", "Metals", "XPTUSD", "H4", 420),
    VisualReviewSpec("metals_xpdusd_h4", "Metals", "XPDUSD", "H4", 420),
    VisualReviewSpec("index_aus200_h4", "Index", "AUS200", "H4", 420),
    VisualReviewSpec("index_hk50_h4", "Index", "HK50", "H4", 420),
    VisualReviewSpec("index_us500_h4", "Index", "US500", "H4", 420),
    VisualReviewSpec("index_us30_h4", "Index", "US30", "H4", 420),
)


def build_h4_d1_galleries(
    phase23_output_dir: Path = DEFAULT_PHASE23_OUTPUT_DIR,
    phase24_output_dir: Path = DEFAULT_PHASE24_OUTPUT_DIR,
    htf_rows: int = 260,
) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()

    phase23_meta = build_visual_review_gallery(
        output_dir=phase23_output_dir,
        specs=H4_D1_VISUAL_REVIEW_SPECS,
    )
    phase24_meta = build_context_gallery(
        input_dir=phase23_output_dir,
        output_dir=phase24_output_dir,
        htf_rows=htf_rows,
        specs=H4_D1_VISUAL_REVIEW_SPECS,
    )

    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": perf_counter() - start,
        "phase2_3_output_dir": str(phase23_output_dir),
        "phase2_4_output_dir": str(phase24_output_dir),
        "htf_timeframe": "D1",
        "htf_rows": htf_rows,
        "specs": [asdict(item) for item in H4_D1_VISUAL_REVIEW_SPECS],
        "phase2_3": {
            "charts": len([row for row in phase23_meta.get("charts", []) if row.get("status") == "ok"]),
            "outputs": phase23_meta.get("outputs", {}),
        },
        "phase2_4": {
            "charts": len([row for row in phase24_meta.get("charts", []) if row.get("status") == "ok"]),
            "outputs": phase24_meta.get("outputs", {}),
        },
        "notes": [
            "H4/D1 diagnostic extension only.",
            "Phase 2.3 plots H4 candidate counts without indicators.",
            "Phase 2.4 adds D1 context with EMAs 50/150 and EWO 5-35.",
            "No WaveCount rules, strategies, signals, backtests, MT5, dashboard or Telegram integration were changed.",
        ],
    }
    summary_path = phase24_output_dir / "h4_d1_run_meta.json"
    summary_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount H4/D1 Phase 2.3 and 2.4 galleries.")
    parser.add_argument("--phase2-3-output-dir", type=Path, default=DEFAULT_PHASE23_OUTPUT_DIR)
    parser.add_argument("--phase2-4-output-dir", type=Path, default=DEFAULT_PHASE24_OUTPUT_DIR)
    parser.add_argument("--htf-rows", type=int, default=260)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_h4_d1_galleries(
        phase23_output_dir=args.phase2_3_output_dir,
        phase24_output_dir=args.phase2_4_output_dir,
        htf_rows=args.htf_rows,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
