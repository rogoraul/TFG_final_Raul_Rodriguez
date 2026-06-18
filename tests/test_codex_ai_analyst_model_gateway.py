from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from trading_center.codex_ai_analyst_model_gateway import build_plain_review_prompt, main
from tests.test_codex_ai_analyst_package_renderer import _run_renderer


def _package_dir(tmp_path: Path) -> Path:
    renderer_workspace = tmp_path / "renderer"
    renderer_workspace.mkdir(parents=True, exist_ok=True)
    renderer_output = _run_renderer(renderer_workspace)
    meta = json.loads((renderer_output / "run_meta.json").read_text(encoding="utf-8"))
    return Path(meta["package"]["package_dir"])


def _run_gateway(tmp_path: Path, package_dir: Path, *extra_args: str) -> Path:
    output = tmp_path / "gateway"
    main(["--package-dir", str(package_dir), "--output-dir", str(output), *extra_args])
    return output


def _valid_review_output(path: Path, package_id: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "review_id": "review_fixture_1",
                "package_id": package_id,
                "review_status": "reviewed",
                "review_priority": 3,
                "summary": "Setup de estudio para revision humana.",
                "setup_reading": "Contexto acotado sin instruccion operativa.",
                "confluences": ["nivel relevante documentado"],
                "contradictions": ["requiere revision visual"],
                "risk_notes": ["No implica ejecucion ni probabilidad."],
                "human_next_checks": ["Revisar grafico y timing manualmente."],
                "sources": ["setup_context.json", "chart_layers.csv", "chart.png"],
                "macro_context_summary": "No solicitado.",
                "macro_risk_level": "not_requested",
                "macro_sources": [],
                "safety_flags": {
                    "can_execute_order": False,
                    "would_send_to_mt5": False,
                    "would_send_telegram_order": False,
                    "sql_real_written": False,
                    "mt5_connected": False,
                    "telegram_connected": False,
                    "signals_generated": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_gateway_validates_package_but_blocks_network_by_default(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    output = _run_gateway(tmp_path, package_dir)
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["model_gateway_implemented"] is True
    assert meta["package_validation_decision"] == "pass"
    assert meta["request_decision"] == "blocked_by_missing_provider_config"
    assert meta["model_called"] is False
    assert meta["network_call_allowed"] is False
    assert meta["sql_real_written"] is False
    assert meta["mt5_connected"] is False
    assert meta["telegram_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False


def test_gateway_blocks_valid_config_when_network_disabled(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    output = _run_gateway(
        tmp_path,
        package_dir,
        "--provider-id",
        "local_fixture_provider",
        "--model-id",
        "fixture-model",
        "--max-prompt-tokens",
        "8000",
        "--max-output-tokens",
        "1000",
        "--timeout-seconds",
        "30",
        "--max-cost",
        "0.05",
    )
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["provider_configured"] is True
    assert meta["request_decision"] == "blocked_network_disabled"
    assert meta["model_called"] is False


def test_gateway_validates_fixture_output_without_model_call(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    package_manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    fixture_output = _valid_review_output(tmp_path / "review_output.json", package_manifest["package_id"])
    output = _run_gateway(
        tmp_path,
        package_dir,
        "--provider-id",
        "local_fixture_provider",
        "--model-id",
        "fixture-model",
        "--max-prompt-tokens",
        "8000",
        "--max-output-tokens",
        "1000",
        "--timeout-seconds",
        "30",
        "--max-cost",
        "0.05",
        "--call-mode",
        "fixture",
        "--fixture-output-json",
        str(fixture_output),
    )
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["model_call_controlled_implemented"] is True
    assert meta["request_decision"] == "blocked_network_disabled"
    assert meta["output_validation_status"] == "pass"
    assert meta["fixture_output_validated"] is True
    assert meta["model_called"] is False
    assert meta["network_call_allowed"] is False


def test_gateway_blocks_real_mode_without_manual_intent(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    output = _run_gateway(
        tmp_path,
        package_dir,
        "--provider-id",
        "openai",
        "--model-id",
        "controlled-model",
        "--max-prompt-tokens",
        "8000",
        "--max-output-tokens",
        "1000",
        "--timeout-seconds",
        "30",
        "--max-cost",
        "0.05",
        "--call-mode",
        "real",
        "--allow-network-call",
        "--api-key-env-var",
        "MISSING_TEST_KEY",
    )
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["request_decision"] == "blocked_by_missing_manual_intent"
    assert meta["model_called"] is False
    assert meta["real_model_provider_implemented"] is True


def test_gateway_calls_openai_provider_when_all_real_gates_pass(tmp_path: Path, monkeypatch) -> None:
    package_dir = _package_dir(tmp_path)
    package_manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    valid_payload = json.loads(_valid_review_output(tmp_path / "valid_review.json", package_manifest["package_id"]).read_text(encoding="utf-8"))
    fake_response = {
        "id": "resp_test",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(valid_payload)}],
            }
        ],
    }

    class FakeHTTPResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(fake_response).encode("utf-8")

    monkeypatch.setenv("OPENAI_TEST_KEY", "test-secret")
    with patch("trading_center.codex_ai_analyst_model_gateway.request.urlopen", return_value=FakeHTTPResponse()) as urlopen_mock:
        output = _run_gateway(
            tmp_path,
            package_dir,
            "--provider-id",
            "openai",
            "--model-id",
            "gpt-4o-mini",
            "--max-prompt-tokens",
            "8000",
            "--max-output-tokens",
            "1000",
            "--timeout-seconds",
            "30",
            "--max-cost",
            "0.05",
            "--call-mode",
            "real",
            "--allow-network-call",
            "--api-key-env-var",
            "OPENAI_TEST_KEY",
            "--manual-intent",
            "revision humana controlada",
        )

    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    review = json.loads((output / "review_output.json").read_text(encoding="utf-8"))
    call_audit = (output / "tables" / "real_model_call_audit.csv").read_text(encoding="utf-8")

    assert urlopen_mock.called
    assert meta["request_decision"] == "real_model_called"
    assert meta["model_called"] is True
    assert meta["ai_review_generated"] is True
    assert meta["output_validation_status"] == "pass"
    assert review["package_id"] == package_manifest["package_id"]
    assert "openai" in call_audit
    assert "test-secret" not in call_audit


def test_gateway_calls_local_codex_cli_when_all_real_gates_pass(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    package_manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    valid_payload = json.loads(_valid_review_output(tmp_path / "valid_codex_review.json", package_manifest["package_id"]).read_text(encoding="utf-8"))

    def fake_run(command, input, text, encoding, errors, capture_output, timeout, cwd, env, check):
        review_path = Path(command[command.index("--output-last-message") + 1])
        review_path.write_text(json.dumps(valid_payload), encoding="utf-8")
        assert encoding == "utf-8"
        assert errors == "replace"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PYTHONUTF8"] == "1"

        class Completed:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Completed()

    with patch("trading_center.codex_ai_analyst_model_gateway.subprocess.run", side_effect=fake_run) as run_mock:
        output = _run_gateway(
            tmp_path,
            package_dir,
            "--provider-id",
            "codex_cli",
            "--model-id",
            "gpt-5",
            "--max-prompt-tokens",
            "8000",
            "--max-output-tokens",
            "1000",
            "--timeout-seconds",
            "30",
            "--max-cost",
            "0.05",
            "--call-mode",
            "real",
            "--allow-network-call",
            "--manual-intent",
            "revision humana controlada con codex local",
        )

    command = run_mock.call_args.args[0]
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    review = json.loads((output / "review_output.json").read_text(encoding="utf-8"))
    call_audit = (output / "tables" / "real_model_call_audit.csv").read_text(encoding="utf-8")

    assert Path(command[0]).name.lower() in {"codex", "codex.cmd", "codex.exe"}
    assert "exec" in command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "-a" in command
    assert "never" in command
    assert "--image" in command
    assert meta["request_decision"] == "real_model_called"
    assert meta["model_called"] is True
    assert meta["ai_review_generated"] is True
    assert meta["output_validation_status"] == "pass"
    assert review["package_id"] == package_manifest["package_id"]
    assert "codex_cli" in call_audit


def test_gateway_codex_cli_macro_research_is_explicit_and_audited(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    package_manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    valid_payload = json.loads(_valid_review_output(tmp_path / "valid_codex_macro_review.json", package_manifest["package_id"]).read_text(encoding="utf-8"))
    valid_payload["macro_context_summary"] = "No hay evento verificado en el fixture."
    valid_payload["macro_risk_level"] = "unknown"
    valid_payload["macro_sources"] = ["fixture macro source"]

    def fake_run(command, input, text, encoding, errors, capture_output, timeout, cwd, env, check):
        review_path = Path(command[command.index("--output-last-message") + 1])
        review_path.write_text(json.dumps(valid_payload), encoding="utf-8")
        assert encoding == "utf-8"
        assert errors == "replace"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PYTHONUTF8"] == "1"

        class Completed:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Completed()

    with patch("trading_center.codex_ai_analyst_model_gateway.subprocess.run", side_effect=fake_run) as run_mock:
        output = _run_gateway(
            tmp_path,
            package_dir,
            "--provider-id",
            "codex_cli",
            "--model-id",
            "gpt-5",
            "--max-prompt-tokens",
            "8000",
            "--max-output-tokens",
            "1000",
            "--timeout-seconds",
            "30",
            "--max-cost",
            "0.05",
            "--call-mode",
            "real",
            "--allow-network-call",
            "--manual-intent",
            "revision humana controlada con macro",
            "--macro-web-research",
        )

    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    prompt = (output / "codex_cli_prompt_context.md").read_text(encoding="utf-8")
    request_audit = (output / "tables" / "model_request_audit.csv").read_text(encoding="utf-8")

    assert run_mock.called
    assert "MODO MACRO/NOTICIAS ACTIVADO" in prompt
    assert "macro_web_research_requested" in request_audit
    assert meta["macro_web_research_requested"] is True
    assert meta["model_called"] is True
    assert meta["output_validation_status"] == "pass"


def test_plain_codex_prompt_blocks_internet_when_macro_not_requested(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)

    prompt = build_plain_review_prompt(package_dir, max_rows_per_csv=3)

    assert "MODO MACRO/NOTICIAS NO SOLICITADO" in prompt
    assert "No consultes internet" in prompt


def test_gateway_blocks_missing_required_package_file(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    (package_dir / "chart.png").unlink()
    output = _run_gateway(
        tmp_path,
        package_dir,
        "--provider-id",
        "local_fixture_provider",
        "--model-id",
        "fixture-model",
        "--max-prompt-tokens",
        "8000",
        "--max-output-tokens",
        "1000",
        "--timeout-seconds",
        "30",
        "--max-cost",
        "0.05",
    )
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    audit = (output / "tables" / "package_validation_audit.csv").read_text(encoding="utf-8")

    assert meta["package_validation_decision"] == "blocked"
    assert meta["request_decision"] == "blocked_by_package_validation"
    assert "required_file:chart.png" in audit


def test_gateway_blocks_unsafe_output_phrases(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    package_manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    output_json = tmp_path / "unsafe_output.json"
    output_json.write_text(
        json.dumps(
            {
                "review_id": "r1",
                "package_id": package_manifest["package_id"],
                "review_status": "reviewed",
                "review_priority": 4,
                "summary": "buy now because this is strong",
                "setup_reading": "unsafe",
                "confluences": [],
                "contradictions": [],
                "risk_notes": [],
                "human_next_checks": [],
                "sources": ["setup_context.json"],
                "macro_context_summary": "No solicitado.",
                "macro_risk_level": "not_requested",
                "macro_sources": [],
                "safety_flags": {"can_execute_order": False},
            }
        ),
        encoding="utf-8",
    )
    output = _run_gateway(tmp_path, package_dir, "--validate-output-json", str(output_json))
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    response_audit = (output / "tables" / "model_response_audit.csv").read_text(encoding="utf-8")

    assert meta["output_validation_status"] == "blocked"
    assert "blocked_phrase_scan,blocked" in response_audit


def test_gateway_blocks_output_side_effect_flags(tmp_path: Path) -> None:
    package_dir = _package_dir(tmp_path)
    package_manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    output_json = tmp_path / "unsafe_flags.json"
    output_json.write_text(
        json.dumps(
            {
                "review_id": "r2",
                "package_id": package_manifest["package_id"],
                "review_status": "reviewed",
                "review_priority": 3,
                "summary": "study-only review",
                "setup_reading": "bounded",
                "confluences": [],
                "contradictions": [],
                "risk_notes": [],
                "human_next_checks": [],
                "sources": ["setup_context.json"],
                "macro_context_summary": "No solicitado.",
                "macro_risk_level": "not_requested",
                "macro_sources": [],
                "safety_flags": {"would_send_to_mt5": True},
            }
        ),
        encoding="utf-8",
    )
    output = _run_gateway(tmp_path, package_dir, "--validate-output-json", str(output_json))
    meta = json.loads((output / "run_meta.json").read_text(encoding="utf-8"))
    response_audit = (output / "tables" / "model_response_audit.csv").read_text(encoding="utf-8")

    assert meta["output_validation_status"] == "blocked"
    assert "side_effect_flags_false,blocked" in response_audit
