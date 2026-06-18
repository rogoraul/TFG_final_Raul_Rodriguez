from __future__ import annotations

import json
from pathlib import Path

from trading_center.codex_ai_analyst_package_renderer import main
from trading_center.readonly_dashboard import write_csv


def _write_fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    latest_manifest = tmp_path / "latest_manifest.json"
    setups = tmp_path / "screener_setups.csv"
    layers = tmp_path / "screener_chart_layers.csv"
    ohlc = tmp_path / "ohlc_mtf.csv"
    market = tmp_path / "market_radar.csv"
    correlations = tmp_path / "correlation_pairs.csv"
    rolling = tmp_path / "rolling_correlations.csv"
    weave = tmp_path / "weavecount_screener.csv"
    weave_points = tmp_path / "weavecount_structure_points.csv"
    design_doc = tmp_path / "design.md"

    latest_manifest.write_text('{"generated_at":"2026-06-06T10:00:00Z","components":[]}', encoding="utf-8")
    design_doc.write_text("# Design\n", encoding="utf-8")
    write_csv(
        setups,
        [
            {
                "setup_id": "setup-eurusd-h1",
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "setup_type": "macd_breakout",
                "strategy": "macd_breakout",
                "direction": "long",
                "setup_status": "ready_for_chart_review",
                "timing_state": "entry_review",
                "timing_priority": "1",
                "timing_reason": "fixture recent review",
                "setup_quality_score": "4",
                "quality_label": "alta",
                "quality_reason": "fixture quality",
                "confluence_tags": "macd_recent|trend_compatible",
                "risk_tags": "study_only_not_signal",
                "trend_context": "H1/H4/D1 bullish",
                "rsi_context": "neutral",
                "codex_review_status": "revision codex pendiente",
                "is_signal": "False",
                "is_study_only": "True",
                "can_execute_order": "False",
                "would_send_to_mt5": "False",
                "would_send_telegram_order": "False",
                "wavecount_used_as_filter": "False",
            }
        ],
    )
    write_csv(
        layers,
        [
            {
                "chart_layer_id": "layers",
                "setup_id": "setup-eurusd-h1",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "layer_type": "macd_breakout_level",
                "label": "Ruptura estudio",
                "price": "1.106",
                "start_price": "",
                "end_price": "",
                "start_time": "",
                "end_time": "",
                "color": "#5ce0ca",
                "style": "dash",
                "source": "fixture",
                "is_operational": "False",
            },
            {
                "chart_layer_id": "layers",
                "setup_id": "setup-eurusd-h1",
                "symbol": "EURUSD.r",
                "timeframe": "H1",
                "layer_type": "macd_w2_directrix",
                "label": "Directriz estudio",
                "price": "",
                "start_price": "1.102",
                "end_price": "1.106",
                "start_time": "2026-03-17 05:00:00",
                "end_time": "2026-03-17 09:00:00",
                "color": "#d8ede6",
                "style": "dot",
                "source": "fixture",
                "is_operational": "False",
            },
        ],
    )
    ohlc_rows = []
    for index in range(40):
        price = 1.10 + index * 0.0002
        ohlc_rows.append(
            {
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "timeframe": "H1",
                "timestamp": f"2026-03-17 {index % 24:02d}:00:00",
                "open": f"{price:.5f}",
                "high": f"{price + 0.001:.5f}",
                "low": f"{price - 0.001:.5f}",
                "close": f"{price + 0.0003:.5f}",
            }
        )
    write_csv(ohlc, ohlc_rows)
    write_csv(market, [{"symbol": "EURUSD.r", "market_group": "Forex Majors", "h1_trend": "bullish"}])
    write_csv(correlations, [{"asset_1": "EURUSD.r", "asset_2": "GBPUSD.r", "pearson": "0.72"}])
    write_csv(rolling, [{"asset_1": "EURUSD.r", "asset_2": "GBPUSD.r", "pearson": "0.65"}])
    write_csv(weave, [{"symbol": "EURUSD.r", "timeframe": "H1", "count_label": "W2?", "quality_status": "media"}])
    write_csv(weave_points, [{"symbol": "EURUSD.r", "timeframe": "H1", "point_label": "W1"}])
    return {
        "latest_manifest": latest_manifest,
        "setups": setups,
        "layers": layers,
        "ohlc": ohlc,
        "market": market,
        "correlations": correlations,
        "rolling": rolling,
        "weave": weave,
        "weave_points": weave_points,
        "design_doc": design_doc,
    }


def _run_renderer(tmp_path: Path) -> Path:
    paths = _write_fixture_inputs(tmp_path)
    output = tmp_path / "out"
    main(
        [
            "--latest-manifest-json",
            str(paths["latest_manifest"]),
            "--screener-setups-csv",
            str(paths["setups"]),
            "--screener-chart-layers-csv",
            str(paths["layers"]),
            "--ohlc-csv",
            str(paths["ohlc"]),
            "--market-radar-csv",
            str(paths["market"]),
            "--correlation-pairs-csv",
            str(paths["correlations"]),
            "--rolling-correlations-csv",
            str(paths["rolling"]),
            "--weavecount-screener-csv",
            str(paths["weave"]),
            "--weavecount-structure-points-csv",
            str(paths["weave_points"]),
            "--design-doc",
            str(paths["design_doc"]),
            "--output-dir",
            str(output),
            "--setup-id",
            "setup-eurusd-h1",
        ]
    )
    return output


def test_package_renderer_generates_structured_package_and_chart(tmp_path: Path) -> None:
    output = _run_renderer(tmp_path)
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    package_dir = Path(meta["package"]["package_dir"])

    assert meta["package_renderer_implemented"] is True
    assert meta["model_called"] is False
    assert meta["ai_review_generated"] is False
    assert meta["chart_png_generated"] is True
    assert (package_dir / "setup_context.json").exists()
    assert (package_dir / "market_context.json").exists()
    assert (package_dir / "ohlc_window.csv").exists()
    assert (package_dir / "chart_layers.csv").exists()
    assert (package_dir / "source_manifest.json").exists()
    assert (package_dir / "prompt_context.md").exists()
    assert (package_dir / "chart.png").stat().st_size > 1000


def test_package_renderer_keeps_fail_closed_flags(tmp_path: Path) -> None:
    output = _run_renderer(tmp_path)
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    package_dir = Path(meta["package"]["package_dir"])
    setup_context = json.loads((package_dir / "setup_context.json").read_text(encoding="utf-8"))
    prompt_context = (package_dir / "prompt_context.md").read_text(encoding="utf-8")

    assert meta["sql_real_written"] is False
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False
    assert setup_context["safety"]["can_execute_order"] is False
    assert setup_context["safety"]["would_send_to_mt5"] is False
    assert setup_context["safety"]["would_send_telegram_order"] is False
    assert "confidence" not in prompt_context.lower()
    assert "buy now" in prompt_context.lower()


def test_source_manifest_records_hashes(tmp_path: Path) -> None:
    output = _run_renderer(tmp_path)
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    package_dir = Path(meta["package"]["package_dir"])
    manifest = json.loads((package_dir / "source_manifest.json").read_text(encoding="utf-8"))

    assert manifest["model_called"] is False
    assert manifest["is_read_only"] is True
    assert manifest["package_hash_seed"]
    assert any(source["source_id"] == "screener_setups_csv" and source["sha256"] for source in manifest["sources"])
