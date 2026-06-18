from __future__ import annotations

import json
import base64
from pathlib import Path

import pytest

from trading_center.dash_readonly_app import (
    DEFAULT_LATEST_MANIFEST_JSON,
    _run_ai_analyst_gateway,
    ai_analyst_download_pdf_path,
    ai_analyst_gateway_status_line,
    build_h1_aux_wavecount_rows,
    build_manifest_refresh_state,
    build_refresh_status_payload,
    build_weavecount_screener_dashboard_rows,
    build_dash_data,
    build_dash_data_from_args,
    ai_analyst_correlation_options,
    ai_analyst_context_options,
    ai_analyst_control_visibility,
    ai_analyst_report_conclusion,
    ai_analyst_setup_options,
    ai_analyst_wave_options,
    correlation_rows_for_asset,
    dash_css,
    default_matrix_assets,
    dynamic_fibonacci_layers,
    lowess_line,
    load_latest_manifest_metadata,
    maybe_refresh_dash_data,
    matrix_assets_for_focus,
    mt5_shadow_state_label,
    mt5_shadow_status_label,
    mt5_shadow_summary,
    latest_or_fallback_dir,
    latest_or_fallback_path,
    normalize_matrix_assets,
    pair_return_points,
    create_app,
    filter_screener_setups,
    filter_universe_rows,
    filter_watchlist_rows,
    filter_wavecount_number_rows,
    filter_wavecount_rows,
    format_dashboard_timestamp,
    market_radar_summary,
    partial_correlation_rows,
    parse_args,
    refresh_decision_label,
    riskguard_decision_index,
    riskguard_decision_detail,
    riskguard_decision_label,
    riskguard_decision_summary,
    riskguard_status_label,
    rolling_correlation_series,
    rolling_rows_for_asset,
    rolling_window_for_timeframe,
    run_ai_analyst_correlation_review,
    run_ai_analyst_controlled_review,
    run_ai_analyst_market_review,
    run_ai_analyst_weavecount_review,
    screener_default_visible_layers,
    screener_layer_price_by_type,
    screener_layer_family,
    screener_layer_options_for,
    screener_score,
    screener_setup_figure,
    selected_wavecount_row,
    sender_status_label,
    manager_status_label,
    telegram_info_result_label,
    telegram_info_sent_label,
    telegram_info_status_label,
    wavecount_chart_data_uri,
    wavecount_chart_figure,
    wavecount_case_id,
    wavecount_direction_label,
    wavecount_number,
    wavecount_number_summary,
    wavecount_quality_status,
    wavecount_status,
    wavecount_structure_points,
    wavecount_wave_label,
    write_ai_analyst_pdf_report,
    write_dash_artifacts,
)

def test_ai_analyst_setup_options_use_reviewable_setups() -> None:
    rows = [
        {
            "setup_id": "late-1",
            "symbol": "EURUSD.r",
            "timeframe": "H1",
            "setup_type": "macd_breakout",
            "setup_quality_score": "2",
            "timing_state": "late",
            "setup_status": "needs_review",
            "is_signal": "false",
        },
        {
            "setup_id": "review-1",
            "symbol": "US100",
            "timeframe": "H4",
            "setup_type": "fib_limit_live_candidate",
            "setup_quality_score": "3",
            "timing_state": "entry_review",
            "setup_status": "ready_for_chart_review",
            "is_signal": "false",
        },
    ]

    options = ai_analyst_setup_options(rows)
    watching_options = ai_analyst_setup_options(rows, "watching")
    all_options = ai_analyst_setup_options(rows, "__all__")

    assert [option["value"] for option in options] == ["review-1"]
    assert [option["value"] for option in watching_options] == ["late-1"]
    assert {option["value"] for option in all_options} == {"late-1", "review-1"}


def test_ai_analyst_context_options_include_non_screener_sections() -> None:
    values = {option["value"] for option in ai_analyst_context_options()}

    assert values == {"screener_setup", "market_summary", "correlation", "weavecount_case"}


def test_ai_analyst_control_visibility_matches_context() -> None:
    assert ai_analyst_control_visibility("screener_setup") == ({"display": "grid"}, {"display": "none"}, {"display": "none"}, {"display": "none"})
    assert ai_analyst_control_visibility("weavecount_case") == ({"display": "none"}, {"display": "grid"}, {"display": "none"}, {"display": "none"})
    assert ai_analyst_control_visibility("correlation") == ({"display": "none"}, {"display": "none"}, {"display": "grid"}, {"display": "none"})
    assert ai_analyst_control_visibility("market_summary") == ({"display": "none"}, {"display": "none"}, {"display": "none"}, {"display": "grid"})


def test_ai_analyst_correlation_options_are_pair_specific() -> None:
    rows = [
        {"timeframe": "H1", "asset_1": "EURUSD.r", "asset_2": "GBPUSD.r", "pearson": "0.82"},
        {"timeframe": "H4", "asset_1": "US100", "asset_2": "US500", "pearson": "0.91"},
    ]

    options = ai_analyst_correlation_options(rows)

    assert options[0]["value"] == "H1|EURUSD.r|GBPUSD.r"
    assert "Pearson +0.82" in options[0]["label"]


def test_ai_analyst_wave_options_select_specific_wave_cases() -> None:
    rows = [
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H4",
            "count_label": "W3?",
            "wave_number": "3",
            "confidence_status": "candidate",
            "direction": "bullish",
            "quality_status": "media",
            "study_status": "candidate_wave_watch",
        }
    ]

    options = ai_analyst_wave_options(rows)

    assert len(options) == 1
    assert options[0]["value"]
    assert "EURUSD.r H4" in options[0]["label"]
    assert "W3?" in options[0]["label"]


def test_selected_wavecount_row_uses_ai_case_id() -> None:
    rows = [
        {
            "symbol": "EURUSD.r",
            "market_group": "Forex Majors",
            "timeframe": "H4",
            "count_label": "W3?",
            "wave_number": "3",
            "confidence_status": "candidate",
            "direction": "bullish",
            "quality_status": "media",
            "study_status": "candidate_wave_watch",
        }
    ]
    case_id = wavecount_case_id(rows[0])

    assert selected_wavecount_row(case_id, rows) == rows[0]
    assert selected_wavecount_row("missing", rows) is None


def test_ai_analyst_controlled_review_blocks_missing_setup(tmp_path: Path) -> None:
    result = run_ai_analyst_controlled_review("", output_dir=tmp_path)

    assert result["status"] == "blocked"
    assert result["reason"] == "missing_setup_id"


def test_ai_analyst_weavecount_review_blocks_missing_case(tmp_path: Path) -> None:
    result = run_ai_analyst_weavecount_review("", output_dir=tmp_path)

    assert result["status"] == "blocked"
    assert result["reason"] == "missing_wavecount_case_id"


def test_ai_analyst_weavecount_pdf_adds_elliott_reading(tmp_path: Path) -> None:
    data = build_dash_data()
    options = ai_analyst_wave_options(data.get("wavecount_rows", []))
    assert options

    result = run_ai_analyst_weavecount_review(options[0]["value"], output_dir=tmp_path)

    assert result["status"] == "prepared"
    report_pdf = Path(result["report_pdf"])
    assert report_pdf.exists()
    tex = report_pdf.with_suffix(".tex").read_text(encoding="utf-8")
    assert "\\section*{Lectura Elliott / WeaveCount}" in tex
    assert "hipotesis estructural" in tex
    assert "no como orden automatica ni como filtro operativo" in tex


def test_ai_analyst_download_pdf_path_accepts_absolute_repo_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-demo")
    repo_pdf = Path("artifacts/tfg/test_ai_download_path.pdf")
    repo_pdf.parent.mkdir(parents=True, exist_ok=True)
    repo_pdf.write_bytes(pdf_path.read_bytes())
    try:
        resolved = ai_analyst_download_pdf_path(str(repo_pdf.resolve()))
        assert resolved == repo_pdf.resolve()
    finally:
        repo_pdf.unlink(missing_ok=True)


def test_ai_analyst_correlation_review_blocks_missing_pair(tmp_path: Path) -> None:
    result = run_ai_analyst_correlation_review("missing", output_dir=tmp_path)

    assert result["status"] == "blocked"
    assert result["reason"] == "missing_correlation_pair"


def test_ai_analyst_market_review_prepares_fixture_package(tmp_path: Path) -> None:
    result = run_ai_analyst_market_review(output_dir=tmp_path)

    assert result["status"] == "prepared"
    assert result["analysis_type"] == "market_summary"
    assert result["chart_rendered"] is True
    assert result["model_called"] is False
    assert result["network_call_allowed"] is False
    assert result["output_validation_status"] == "pass"
    package_dir = Path(result["package_dir"])
    assert (package_dir / "chart.png").exists()
    assert (package_dir / "setup_context.json").exists()
    assert (package_dir / "market_context.json").exists()
    report_pdf = Path(result["report_pdf"])
    assert report_pdf.exists()
    assert report_pdf.read_bytes()[:4] == b"%PDF"
    report_tex = report_pdf.with_suffix(".tex")
    if report_tex.exists():
        tex_source = report_tex.read_text(encoding="utf-8")
        assert "\\section*{Resumen}" in tex_source
        assert "Este informe no es una senal" in tex_source
        assert "- Revision fixture" not in tex_source


def test_ai_analyst_correlation_review_prepares_fixture_package(tmp_path: Path) -> None:
    data = build_dash_data()
    options = ai_analyst_correlation_options(data.get("correlation_pair_rows", []), limit=1)
    assert options

    result = run_ai_analyst_correlation_review(options[0]["value"], output_dir=tmp_path)

    assert result["status"] == "prepared"
    assert result["analysis_type"] == "correlation"
    assert result["chart_rendered"] is True
    assert result["model_called"] is False
    assert result["network_call_allowed"] is False
    assert result["output_validation_status"] == "pass"
    package_dir = Path(result["package_dir"])
    assert (package_dir / "chart.png").exists()
    assert (package_dir / "setup_context.json").exists()
    assert (package_dir / "market_context.json").exists()
    report_pdf = Path(result["report_pdf"])
    assert report_pdf.exists()
    assert report_pdf.read_bytes()[:4] == b"%PDF"


def test_ai_analyst_pdf_report_humanizes_sources_and_metrics(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    gateway_dir = tmp_path / "gateway"
    gateway_dir.mkdir()
    (package_dir / "chart.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    package_manifest = {
        "package_id": "demo_package",
        "symbol": "EURUSD.r",
        "timeframe": "H1",
        "setup_type": "macd_breakout",
        "package_dir": str(package_dir),
        "files": {"chart.png": str(package_dir / "chart.png")},
    }
    (gateway_dir / "review_output.json").write_text(
        json.dumps(
            {
                "package_id": "demo_package",
                "review_status": "reviewed",
                "review_priority": 2,
                "summary": "El rango range_pct_h1_24 exige revision humana.",
                "setup_reading": "Lectura de macd_breakout sin ejecucion.",
                "confluences": ["atr_pct_h1_ratio favorable"],
                "contradictions": [],
                "risk_notes": [],
                "human_next_checks": ["Revisar calendario."],
                "sources": ["setup_context.json"],
                "macro_context_summary": "Evento macro verificado. Puede elevar la volatilidad de la divisa.",
                "macro_risk_level": "medium",
                "macro_sources": [
                    "Example Central Bank: https://example.com/macro-calendar",
                    "Very Long News Source Label That Should Be Shortened In The Visible PDF Sources Section Because Otherwise It Overlaps The Description: https://apnews.com/article/b9d2661cbba6cc32f06ff0e6f0d891",
                ],
            }
        ),
        encoding="utf-8",
    )
    (gateway_dir / "run_meta.json").write_text(json.dumps({"model_id_effective": "gpt-demo", "reasoning_effort_effective": "medium"}), encoding="utf-8")

    report_pdf = Path(write_ai_analyst_pdf_report(package_manifest, gateway_dir))

    assert report_pdf.exists()
    assert report_pdf.read_bytes()[:4] == b"%PDF"
    tex = report_pdf.with_suffix(".tex").read_text(encoding="utf-8")
    assert "rango 24h en H1" in tex
    assert "range_pct_h1_24" not in tex
    assert "setup\\_context.json & Datos estructurados del setup" in tex
    assert "\\href{\\detokenize{https://example.com/macro-calendar}}{Example Central Bank}" in tex
    assert "\\begin{tabularx}{\\textwidth}{p{7.4cm}X}" not in tex
    assert "\\begin{itemize}" in tex
    assert "Very Long News Source Label That Should Be Shortened In The Visible PDF..." in tex
    assert "{https://apnews.com/article/b9d2661cbba6cc32f06ff0e6f0d891}}" in tex
    assert "\\section*{Conclusion operativa y financiera}" in tex


def test_ai_analyst_report_conclusion_is_context_specific() -> None:
    review = {"review_priority": 2, "macro_risk_level": "unknown"}

    screener = ai_analyst_report_conclusion(review, {"symbol": "US30", "setup_type": "rsi_extreme_with_context", "analysis_type": "screener_setup"})
    weavecount = ai_analyst_report_conclusion(review, {"symbol": "AUDJPY.r", "setup_type": "W3?", "analysis_type": "weavecount_case"})
    market = ai_analyst_report_conclusion(review, {"analysis_type": "market_summary"})
    correlation = ai_analyst_report_conclusion(review, {"analysis_type": "correlation"})

    assert "prioridad de revision AI es 2/5" in screener
    assert "hipotesis WeaveCount" in weavecount
    assert "mapa de fuerza" in market
    assert "relacion entre activos" in correlation
    for text in (screener, weavecount, market, correlation):
        assert "tres filtros humanos" not in text
        assert "no autoriza ejecucion" in text


def test_ai_analyst_pdf_report_exists_when_gateway_fails(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "chart.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    gateway_dir = tmp_path / "gateway_failed"
    gateway_dir.mkdir()
    package_manifest = {
        "package_id": "failed_package",
        "symbol": "US30",
        "timeframe": "H1",
        "setup_type": "rsi_extreme_with_context",
        "package_dir": str(package_dir),
        "analysis_type": "screener_setup",
        "files": {"chart.png": str(package_dir / "chart.png")},
    }
    (gateway_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "package_id": "failed_package",
                "request_decision": "real_model_call_failed",
                "output_validation_status": "blocked",
                "model_called": True,
                "network_call_allowed": True,
            }
        ),
        encoding="utf-8",
    )

    report_pdf = Path(write_ai_analyst_pdf_report(package_manifest, gateway_dir))

    assert report_pdf.exists()
    assert report_pdf.read_bytes()[:4] == b"%PDF"
    tex = report_pdf.with_suffix(".tex").read_text(encoding="utf-8")
    assert "blocked gateway diagnostic" in tex
    assert "no hay una revision analitica validada" in tex


def test_ai_analyst_gateway_can_call_codex_cli_with_explicit_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    package_manifest = {
        "package_id": "demo_package",
        "package_dir": str(package_dir),
    }
    captured: dict[str, list[str]] = {}

    def fake_gateway_main(argv: list[str]) -> None:
        captured["argv"] = argv
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "package_id": "demo_package",
                    "request_decision": "real_model_called",
                    "model_called": True,
                    "network_call_allowed": True,
                    "ai_review_generated": True,
                    "output_validation_status": "pass",
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr("trading_center.codex_ai_analyst_model_gateway.main", fake_gateway_main)

    meta = _run_ai_analyst_gateway(package_manifest, tmp_path / "gateway", gateway_mode="codex_cli")

    assert meta["request_decision"] == "real_model_called"
    assert "--provider-id" in captured["argv"]
    assert "codex_cli" in captured["argv"]
    assert "--allow-network-call" in captured["argv"]
    assert "--manual-intent" in captured["argv"]
    assert "fixture_review_output.json" not in captured["argv"]
    status_line = ai_analyst_gateway_status_line(meta)
    assert "model_called=true" in status_line
    assert "network_call_allowed=true" in status_line
    assert "macro=false" in status_line
    assert "review=true" in status_line


def test_ai_analyst_gateway_can_call_codex_cli_macro_with_explicit_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    package_manifest = {
        "package_id": "demo_package",
        "package_dir": str(package_dir),
    }
    captured: dict[str, list[str]] = {}

    def fake_gateway_main(argv: list[str]) -> None:
        captured["argv"] = argv
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "package_id": "demo_package",
                    "request_decision": "real_model_called",
                    "model_called": True,
                    "network_call_allowed": True,
                    "macro_web_research_requested": True,
                    "ai_review_generated": True,
                    "output_validation_status": "pass",
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr("trading_center.codex_ai_analyst_model_gateway.main", fake_gateway_main)

    meta = _run_ai_analyst_gateway(package_manifest, tmp_path / "gateway", gateway_mode="codex_cli_macro")

    assert meta["request_decision"] == "real_model_called"
    assert "codex_cli" in captured["argv"]
    assert "--allow-network-call" in captured["argv"]
    assert "--manual-intent" in captured["argv"]
    assert "--macro-web-research" in captured["argv"]
    assert "contexto macro/noticias" in " ".join(captured["argv"])
    assert "fixture_review_output.json" not in captured["argv"]
    assert "macro=true" in ai_analyst_gateway_status_line(meta)
