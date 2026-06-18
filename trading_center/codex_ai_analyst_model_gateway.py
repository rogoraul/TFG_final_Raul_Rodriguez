from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, read_json, write_csv


METHOD_VERSION = "codex_ai_analyst_model_call_controlled_v1"
DEFAULT_PACKAGE_ROOT = REPO_ROOT / "artifacts/tfg/codex_ai_analyst_package_renderer_v1_2026-06-06/packages"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/codex_ai_analyst_model_call_controlled_v1_2026-06-07"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

REQUIRED_PACKAGE_FILES = [
    "package_manifest.json",
    "setup_context.json",
    "market_context.json",
    "ohlc_window.csv",
    "chart_layers.csv",
    "chart.png",
    "source_manifest.json",
    "prompt_context.md",
]

REQUIRED_OUTPUT_FIELDS = [
    "review_id",
    "package_id",
    "review_status",
    "review_priority",
    "summary",
    "setup_reading",
    "confluences",
    "contradictions",
    "risk_notes",
    "human_next_checks",
    "sources",
    "macro_context_summary",
    "macro_risk_level",
    "macro_sources",
    "safety_flags",
]

BLOCKED_PHRASES = [
    "buy now",
    "sell now",
    "compra ahora",
    "vende ahora",
    "operacion segura",
    "safe trade",
    "guaranteed",
    "garantizada",
    "approved for mt5",
    "aprobado para mt5",
    "execute order",
    "ejecutar orden",
    "automatic signal",
    "senal automatica",
    "confidence",
]

REVIEW_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": REQUIRED_OUTPUT_FIELDS,
    "properties": {
        "review_id": {"type": "string"},
        "package_id": {"type": "string"},
        "review_status": {"type": "string", "enum": ["reviewed", "blocked", "needs_human_review"]},
        "review_priority": {"type": "integer", "minimum": 1, "maximum": 5},
        "summary": {"type": "string"},
        "setup_reading": {"type": "string"},
        "confluences": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "risk_notes": {"type": "array", "items": {"type": "string"}},
        "human_next_checks": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}},
        "macro_context_summary": {"type": "string"},
        "macro_risk_level": {"type": "string", "enum": ["not_requested", "low", "medium", "high", "unknown"]},
        "macro_sources": {"type": "array", "items": {"type": "string"}},
        "safety_flags": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "can_execute_order",
                "would_send_to_mt5",
                "would_send_telegram_order",
                "sql_real_written",
                "mt5_connected",
                "telegram_connected",
                "signals_generated",
            ],
            "properties": {
                "can_execute_order": {"type": "boolean"},
                "would_send_to_mt5": {"type": "boolean"},
                "would_send_telegram_order": {"type": "boolean"},
                "sql_real_written": {"type": "boolean"},
                "mt5_connected": {"type": "boolean"},
                "telegram_connected": {"type": "boolean"},
                "signals_generated": {"type": "boolean"},
            },
        },
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def limited_rows(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = read_csv(path)
    if limit <= 0:
        return rows
    return rows[-limit:]


def chart_data_url(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def codex_executable() -> str:
    return shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex") or "codex"


def codex_local_config() -> dict[str, str]:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        return {"model": "", "model_reasoning_effort": "", "config_path": str(config_path)}
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"model": "", "model_reasoning_effort": "", "config_path": str(config_path)}
    return {
        "model": str(payload.get("model", "")),
        "model_reasoning_effort": str(payload.get("model_reasoning_effort", "")),
        "config_path": str(config_path),
    }


def latest_package_dir(root: Path) -> Path | None:
    if root.is_file():
        return root.parent
    if (root / "package_manifest.json").exists():
        return root
    if not root.exists():
        return None
    packages = [path for path in root.iterdir() if path.is_dir() and (path / "package_manifest.json").exists()]
    if not packages:
        return None
    return max(packages, key=lambda path: path.stat().st_mtime)


def scan_blocked_phrases(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for phrase in BLOCKED_PHRASES:
        if phrase in lowered:
            found.append(phrase)
    return sorted(set(found))


def validate_package(package_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    package_info: dict[str, Any] = {"package_dir": str(package_dir), "package_id": "", "safe_to_prepare_request": False}
    for file_name in REQUIRED_PACKAGE_FILES:
        path = package_dir / file_name
        size = path.stat().st_size if path.exists() and path.is_file() else 0
        status = "pass" if size > 0 else "blocked"
        rows.append({"check": f"required_file:{file_name}", "status": status, "evidence": str(path), "size": size})

    manifest = read_json(package_dir / "package_manifest.json")
    setup_context = read_json(package_dir / "setup_context.json")
    package_info["package_id"] = str(manifest.get("package_id", ""))
    package_info["setup_id"] = str(manifest.get("setup_id", ""))
    package_info["symbol"] = str(manifest.get("symbol", ""))
    package_info["timeframe"] = str(manifest.get("timeframe", ""))
    package_info["setup_type"] = str(manifest.get("setup_type", ""))

    safety = setup_context.get("safety", {}) if isinstance(setup_context, dict) else {}
    safety_checks = {
        "is_signal_false": not boolish(safety.get("is_signal")),
        "is_study_only_true": boolish(safety.get("is_study_only", True)),
        "can_execute_order_false": not boolish(safety.get("can_execute_order")),
        "would_send_to_mt5_false": not boolish(safety.get("would_send_to_mt5")),
        "would_send_telegram_order_false": not boolish(safety.get("would_send_telegram_order")),
        "package_model_called_false": not boolish(manifest.get("model_called")),
        "package_sql_real_written_false": not boolish(manifest.get("sql_real_written")),
        "package_mt5_connected_false": not boolish(manifest.get("mt5_connected")),
        "package_telegram_connected_false": not boolish(manifest.get("telegram_connected")),
        "package_orders_sent_zero": str(manifest.get("orders_sent", 0)) in {"0", "0.0"},
        "package_signals_generated_false": not boolish(manifest.get("signals_generated")),
    }
    for check, passed in safety_checks.items():
        rows.append({"check": check, "status": "pass" if passed else "blocked", "evidence": str(passed), "size": ""})

    ohlc_rows = read_csv(package_dir / "ohlc_window.csv")
    layer_rows = read_csv(package_dir / "chart_layers.csv")
    rows.append({"check": "ohlc_window_non_empty", "status": "pass" if ohlc_rows else "blocked", "evidence": len(ohlc_rows), "size": ""})
    rows.append({"check": "chart_layers_exists", "status": "pass", "evidence": len(layer_rows), "size": ""})

    blocked_count = sum(1 for row in rows if row["status"] == "blocked")
    package_info["safe_to_prepare_request"] = blocked_count == 0
    package_info["blocked_count"] = blocked_count
    package_info["ohlc_rows"] = len(ohlc_rows)
    package_info["chart_layer_rows"] = len(layer_rows)
    return rows, package_info


def build_request_audit(
    *,
    package_info: dict[str, Any],
    provider_id: str,
    model_id: str,
    allow_network_call: bool,
    max_prompt_tokens: int,
    max_output_tokens: int,
    timeout_seconds: int,
    max_cost: str,
    call_mode: str,
    api_key_env_var: str,
    manual_intent: str,
    macro_web_research: bool,
) -> dict[str, Any]:
    provider_normalized = provider_id.strip().lower()
    model_required = provider_normalized not in {"codex", "codex_cli", "codex-local"}
    config_complete = all(
        [
            provider_id.strip(),
            model_id.strip() or not model_required,
            max_prompt_tokens > 0,
            max_output_tokens > 0,
            timeout_seconds > 0,
            str(max_cost).strip(),
        ]
    )
    secret_required = call_mode == "real" and provider_normalized == "openai"
    secret_present = bool(api_key_env_var.strip()) and bool(os.environ.get(api_key_env_var.strip()))
    manual_intent_confirmed = bool(manual_intent.strip())
    if not package_info.get("safe_to_prepare_request"):
        decision = "blocked_by_package_validation"
    elif not config_complete:
        decision = "blocked_by_missing_provider_config"
    elif call_mode == "real" and not manual_intent_confirmed:
        decision = "blocked_by_missing_manual_intent"
    elif not allow_network_call:
        decision = "blocked_network_disabled"
    elif call_mode == "real" and secret_required and not secret_present:
        decision = "blocked_by_missing_secret"
    elif call_mode == "fixture":
        decision = "fixture_output_validation_only"
    elif call_mode == "real" and provider_normalized in {"openai", "codex", "codex_cli", "codex-local"}:
        decision = "ready_for_real_model_call"
    elif call_mode == "real":
        decision = "blocked_real_provider_not_implemented"
    else:
        decision = "no_model_call_requested"
    return {
        "request_id": f"{METHOD_VERSION}|{package_info.get('package_id', 'package')}",
        "package_id": package_info.get("package_id", ""),
        "provider_id": provider_id,
        "model_id": model_id,
        "allow_network_call": allow_network_call,
        "max_prompt_tokens": max_prompt_tokens,
        "max_output_tokens": max_output_tokens,
        "timeout_seconds": timeout_seconds,
        "max_cost": max_cost,
        "call_mode": call_mode,
        "api_key_env_var": api_key_env_var,
        "secret_present_boolean": secret_present,
        "manual_intent_confirmed": manual_intent_confirmed,
        "macro_web_research_requested": macro_web_research,
        "config_complete": config_complete,
        "model_called": False,
        "request_decision": decision,
        "request_reason": "controlled_gateway_no_network_call_executed",
    }


def package_prompt_material(package_dir: Path, *, max_rows_per_csv: int = 80) -> dict[str, Any]:
    manifest = read_json(package_dir / "package_manifest.json")
    setup_context = read_json(package_dir / "setup_context.json")
    market_context = read_json(package_dir / "market_context.json")
    source_manifest = read_json(package_dir / "source_manifest.json")
    prompt_context = read_text(package_dir / "prompt_context.md")
    chart_layers = limited_rows(package_dir / "chart_layers.csv", max_rows_per_csv)
    ohlc_window = limited_rows(package_dir / "ohlc_window.csv", max_rows_per_csv)
    return {
        "package_manifest": manifest,
        "setup_context": setup_context,
        "market_context": market_context,
        "source_manifest": source_manifest,
        "prompt_context": prompt_context[:6000],
        "chart_layers_tail": chart_layers,
        "ohlc_window_tail": ohlc_window,
        "row_limits": {
            "max_rows_per_csv": max_rows_per_csv,
            "chart_layers_rows_sent": len(chart_layers),
            "ohlc_window_rows_sent": len(ohlc_window),
        },
    }


def build_model_messages(package_dir: Path, *, include_chart_image: bool, max_rows_per_csv: int) -> list[dict[str, Any]]:
    material = package_prompt_material(package_dir, max_rows_per_csv=max_rows_per_csv)
    manifest = material["package_manifest"]
    system_text = (
        "Eres AI Analyst read-only del Trading Center. Analiza paquetes reproducibles de mercado "
        "sin asesorar financieramente, sin dar ordenes, sin aprobar ejecucion y sin mencionar probabilidades "
        "de exito. Devuelve solo JSON valido con el schema requerido. Usa lenguaje prudente: setup para revisar, "
        "riesgos, contradicciones, confluencias y siguientes comprobaciones humanas. No uses la palabra confidence."
    )
    user_text = (
        "Genera un reporte de revision humana para este paquete. La imagen del grafico es apoyo visual; "
        "los CSV/JSON son la fuente principal. No inventes niveles ni ejecucion. Si falta evidencia, dilo.\n\n"
        "No consultes internet en este modo. Devuelve macro_context_summary='No solicitado', "
        "macro_risk_level='not_requested' y macro_sources=[] salvo que el paquete ya contenga contexto macro.\n\n"
        f"PACKAGE_ID: {manifest.get('package_id', '')}\n"
        "MATERIAL_JSON:\n"
        f"{json.dumps(material, ensure_ascii=False, indent=2)}"
    )
    content: list[dict[str, Any]] = [{"type": "input_text", "text": user_text}]
    if include_chart_image:
        data_url = chart_data_url(package_dir / "chart.png")
        if data_url:
            content.append({"type": "input_image", "image_url": data_url})
    return [
        {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
        {"role": "user", "content": content},
    ]


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        for content in item.get("content", []) if isinstance(item, dict) and isinstance(item.get("content"), list) else []:
            if isinstance(content, dict):
                if isinstance(content.get("text"), str):
                    chunks.append(content["text"])
                elif isinstance(content.get("output_text"), str):
                    chunks.append(content["output_text"])
    return "\n".join(chunks).strip()


def call_openai_responses(
    *,
    package_dir: Path,
    api_key: str,
    model_id: str,
    max_output_tokens: int,
    timeout_seconds: int,
    include_chart_image: bool,
    max_rows_per_csv: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {
        "model": model_id,
        "input": build_model_messages(package_dir, include_chart_image=include_chart_image, max_rows_per_csv=max_rows_per_csv),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ai_analyst_review_output",
                "strict": True,
                "schema": REVIEW_OUTPUT_SCHEMA,
            }
        },
        "max_output_tokens": max_output_tokens,
    }
    req = request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started_at = utc_now()
    local_config = codex_local_config()
    effective_model_id = model_id or local_config.get("model", "")
    effective_reasoning_effort = local_config.get("model_reasoning_effort", "")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            response_payload = json.loads(raw)
            text = extract_response_text(response_payload)
            parsed = json.loads(text) if text else {}
            return parsed, {
                "model_provider": "openai",
                "model_id": model_id,
                "model_called": True,
                "http_status": getattr(response, "status", ""),
                "started_at": started_at,
                "completed_at": utc_now(),
                "response_id": response_payload.get("id", ""),
                "output_text_chars": len(text),
                "include_chart_image": include_chart_image,
                "max_rows_per_csv": max_rows_per_csv,
                "error_type": "",
                "error_message": "",
            }
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:1200]
        return {}, {
            "model_provider": "openai",
            "model_id": model_id,
            "model_called": True,
            "http_status": exc.code,
            "started_at": started_at,
            "completed_at": utc_now(),
            "response_id": "",
            "output_text_chars": 0,
            "include_chart_image": include_chart_image,
            "max_rows_per_csv": max_rows_per_csv,
            "error_type": "HTTPError",
            "error_message": body_text,
        }
    except Exception as exc:
        return {}, {
            "model_provider": "openai",
            "model_id": model_id,
            "model_called": True,
            "http_status": "",
            "started_at": started_at,
            "completed_at": utc_now(),
            "response_id": "",
            "output_text_chars": 0,
            "include_chart_image": include_chart_image,
            "max_rows_per_csv": max_rows_per_csv,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:1200],
        }


def build_plain_review_prompt(package_dir: Path, *, max_rows_per_csv: int, macro_web_research: bool = False) -> str:
    material = package_prompt_material(package_dir, max_rows_per_csv=max_rows_per_csv)
    manifest = material["package_manifest"]
    macro_block = ""
    if macro_web_research:
        macro_block = (
            "\nMODO MACRO/NOTICIAS ACTIVADO POR EL USUARIO.\n"
            "- Puedes consultar internet desde Codex local solo para contexto macroeconomico, noticias, calendario economico o riesgos de evento relacionados con el simbolo/activo.\n"
            "- Usa fuentes primarias o reconocibles cuando sea posible y cita URLs o nombres de fuente en macro_sources.\n"
            "- No inventes noticias: si no puedes verificar, usa macro_risk_level='unknown' y explica la limitacion.\n"
            "- Separa lectura tecnica del setup y riesgo macro/noticias. El contexto macro solo sirve para cautela de revision humana.\n"
            "- Redacta macro_context_summary en lenguaje financiero claro y serio, con al menos dos parrafos interpretativos: no listes eventos uno detras de otro; explica que implica cada evento o noticia para el activo y para el riesgo de revision.\n"
            "- No conviertas ninguna noticia en recomendacion operativa ni permiso de ejecucion.\n"
        )
    else:
        macro_block = (
            "\nMODO MACRO/NOTICIAS NO SOLICITADO.\n"
            "- No consultes internet. Devuelve macro_context_summary='No solicitado', macro_risk_level='not_requested' y macro_sources=[] salvo que el propio paquete ya contenga contexto macro.\n"
        )
    return (
        "Eres el AI Analyst read-only del Trading Center.\n"
        "Debes devolver exclusivamente JSON valido con el schema indicado por --output-schema.\n"
        "No des asesoramiento financiero, no recomiendes comprar/vender, no apruebes MT5, no generes senales y no uses la palabra confidence.\n"
        "Analiza el paquete como revision humana con lenguaje financiero serio y entendible: resumen, lectura del setup/contexto, confluencias, contradicciones, riesgos y siguientes comprobaciones.\n"
        "Evita nombres internos de codigo en la redaccion cuando puedas usar etiquetas humanas: por ejemplo, escribe 'rango 24h en H1' en vez de 'range_pct_h1_24'.\n"
        "La imagen adjunta chart.png es apoyo visual; los datos estructurados son la fuente principal.\n\n"
        "Campos macro obligatorios: macro_context_summary, macro_risk_level y macro_sources.\n"
        f"{macro_block}\n"
        f"PACKAGE_ID: {manifest.get('package_id', '')}\n"
        "MATERIAL_JSON:\n"
        f"{json.dumps(material, ensure_ascii=False, indent=2)}\n"
    )


def call_codex_cli(
    *,
    package_dir: Path,
    output_dir: Path,
    model_id: str,
    timeout_seconds: int,
    include_chart_image: bool,
    max_rows_per_csv: int,
    macro_web_research: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = utc_now()
    local_config = codex_local_config()
    effective_model_id = model_id or local_config.get("model", "")
    effective_reasoning_effort = local_config.get("model_reasoning_effort", "")
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path = output_dir / "review_output_schema.json"
    prompt_path = output_dir / "codex_cli_prompt_context.md"
    review_path = output_dir / "review_output.json"
    write_json(schema_path, REVIEW_OUTPUT_SCHEMA)
    prompt = build_plain_review_prompt(package_dir, max_rows_per_csv=max_rows_per_csv, macro_web_research=macro_web_research)
    prompt_path.write_text(prompt, encoding="utf-8")
    command = [
        codex_executable(),
        "--sandbox",
        "read-only",
        "-a",
        "never",
        "--cd",
        str(REPO_ROOT),
        "exec",
        "--ephemeral",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(review_path),
    ]
    if model_id:
        command.extend(["--model", model_id])
    chart_path = package_dir / "chart.png"
    if include_chart_image and chart_path.exists():
        command.extend(["--image", str(chart_path)])
    command.append("-")
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        payload = read_json(review_path)
        return payload, {
            "model_provider": "codex_cli",
            "model_id": model_id,
            "model_id_effective": effective_model_id,
            "reasoning_effort_effective": effective_reasoning_effort,
            "codex_config_path": local_config.get("config_path", ""),
            "model_called": completed.returncode == 0,
            "http_status": "",
            "started_at": started_at,
            "completed_at": utc_now(),
            "response_id": "",
            "output_text_chars": len(json.dumps(payload, ensure_ascii=False)) if payload else 0,
            "include_chart_image": include_chart_image,
            "max_rows_per_csv": max_rows_per_csv,
            "macro_web_research_requested": macro_web_research,
            "command": "codex --sandbox read-only -a never --cd <repo> exec --ephemeral",
            "returncode": completed.returncode,
            "error_type": "" if completed.returncode == 0 and payload else "CodexCliError",
            "error_message": (completed.stderr or completed.stdout)[-1200:],
        }
    except Exception as exc:
        return {}, {
            "model_provider": "codex_cli",
            "model_id": model_id,
            "model_id_effective": effective_model_id,
            "reasoning_effort_effective": effective_reasoning_effort,
            "codex_config_path": local_config.get("config_path", ""),
            "model_called": False,
            "http_status": "",
            "started_at": started_at,
            "completed_at": utc_now(),
            "response_id": "",
            "output_text_chars": 0,
            "include_chart_image": include_chart_image,
            "max_rows_per_csv": max_rows_per_csv,
            "macro_web_research_requested": macro_web_research,
            "command": "codex --sandbox read-only -a never --cd <repo> exec --ephemeral",
            "returncode": "",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:1200],
        }


def validate_model_output(path: Path | None, package_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary = {"output_validation_status": "not_provided", "blocked_phrases_count": 0, "schema_valid": False}
    if path is None:
        rows.append({"check": "model_output_optional", "status": "not_run", "evidence": "no output supplied"})
        return rows, summary
    payload = read_json(path)
    if not payload:
        rows.append({"check": "model_output_parse", "status": "blocked", "evidence": str(path)})
        summary["output_validation_status"] = "blocked"
        return rows, summary
    missing = [field for field in REQUIRED_OUTPUT_FIELDS if field not in payload]
    rows.append({"check": "required_fields", "status": "pass" if not missing else "blocked", "evidence": "|".join(missing)})
    rows.append({"check": "package_id_match", "status": "pass" if str(payload.get("package_id", "")) == package_id else "blocked", "evidence": payload.get("package_id", "")})
    rows.append({"check": "review_priority_range", "status": "pass" if str(payload.get("review_priority", "")).isdigit() and 1 <= int(payload["review_priority"]) <= 5 else "blocked", "evidence": payload.get("review_priority", "")})
    sources = payload.get("sources", [])
    rows.append({"check": "sources_present", "status": "pass" if isinstance(sources, list) and sources else "blocked", "evidence": len(sources) if isinstance(sources, list) else "not_list"})
    macro_risk_level = str(payload.get("macro_risk_level", "")).strip()
    macro_sources = payload.get("macro_sources", [])
    rows.append({"check": "macro_risk_level_valid", "status": "pass" if macro_risk_level in {"not_requested", "low", "medium", "high", "unknown"} else "blocked", "evidence": macro_risk_level})
    rows.append({"check": "macro_sources_list", "status": "pass" if isinstance(macro_sources, list) else "blocked", "evidence": len(macro_sources) if isinstance(macro_sources, list) else "not_list"})
    text = json.dumps(payload, ensure_ascii=False)
    blocked = scan_blocked_phrases(text)
    rows.append({"check": "blocked_phrase_scan", "status": "pass" if not blocked else "blocked", "evidence": "|".join(blocked)})
    safety_flags = payload.get("safety_flags", {})
    side_effects = []
    if isinstance(safety_flags, dict):
        for flag in ("can_execute_order", "would_send_to_mt5", "would_send_telegram_order", "sql_real_written", "mt5_connected", "telegram_connected", "signals_generated"):
            if boolish(safety_flags.get(flag)):
                side_effects.append(flag)
    else:
        side_effects.append("safety_flags_not_object")
    rows.append({"check": "side_effect_flags_false", "status": "pass" if not side_effects else "blocked", "evidence": "|".join(side_effects)})
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    summary["output_validation_status"] = "pass" if not blocked_rows else "blocked"
    summary["blocked_phrases_count"] = len(blocked)
    summary["schema_valid"] = not missing
    return rows, summary


def run_gateway(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = latest_package_dir(args.package_dir)
    if package_dir is None:
        raise SystemExit(f"No package_manifest.json found under {args.package_dir}")
    package_rows, package_info = validate_package(package_dir)
    request = build_request_audit(
        package_info=package_info,
        provider_id=args.provider_id,
        model_id=args.model_id,
        allow_network_call=args.allow_network_call,
        max_prompt_tokens=args.max_prompt_tokens,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        max_cost=args.max_cost,
        call_mode=args.call_mode,
        api_key_env_var=args.api_key_env_var,
        manual_intent=args.manual_intent,
        macro_web_research=bool(args.macro_web_research),
    )
    model_call_audit: dict[str, Any] = {"model_called": False, "model_provider": args.provider_id, "model_id": args.model_id}
    generated_output_path: Path | None = None
    if request["request_decision"] == "ready_for_real_model_call":
        provider_normalized = args.provider_id.strip().lower()
        if provider_normalized in {"codex", "codex_cli", "codex-local"}:
            generated_payload, model_call_audit = call_codex_cli(
                package_dir=package_dir,
                output_dir=args.output_dir,
                model_id=args.model_id,
                timeout_seconds=args.timeout_seconds,
                include_chart_image=bool(args.include_chart_image),
                max_rows_per_csv=args.max_rows_per_csv,
                macro_web_research=bool(args.macro_web_research),
            )
        else:
            api_key = os.environ.get(args.api_key_env_var.strip(), "")
            generated_payload, model_call_audit = call_openai_responses(
                package_dir=package_dir,
                api_key=api_key,
                model_id=args.model_id,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
                include_chart_image=bool(args.include_chart_image),
                max_rows_per_csv=args.max_rows_per_csv,
            )
        generated_output_path = args.output_dir / "review_output.json"
        if generated_output_path.exists() and provider_normalized in {"codex", "codex_cli", "codex-local"}:
            generated_payload = read_json(generated_output_path)
        else:
            write_json(generated_output_path, generated_payload)
        request["model_called"] = bool(model_call_audit.get("model_called"))
        request["request_decision"] = "real_model_called" if generated_payload else "real_model_call_failed"
        request["request_reason"] = model_call_audit.get("error_message") or "real_model_call_executed_and_pending_validation"
    output_path = args.validate_output_json or args.fixture_output_json or generated_output_path
    output_rows, output_summary = validate_model_output(output_path, package_info.get("package_id", ""))
    return {
        "package_dir": str(package_dir),
        "package_validation_rows": package_rows,
        "package_info": package_info,
        "request": request,
        "model_call_audit": model_call_audit,
        "output_validation_rows": output_rows,
        "output_summary": output_summary,
    }


def write_report(run_meta: dict[str, Any]) -> str:
    return f"""# Codex AI Analyst Model Call Controlled V1

Decision: `{run_meta['decision']}`

## Resultado

Se implementa una pasarela controlada para validar paquetes del AI Analyst y ejecutar una llamada real solo cuando todos los gates estan activos. Por defecto no se llama a modelos y no se ejecuta ninguna llamada de red.

## Paquete Validado

- package_id: `{run_meta.get('package_id', '')}`
- package_dir: `{run_meta.get('package_dir', '')}`
- package_validation_decision: `{run_meta.get('package_validation_decision', '')}`

## Request

- request_decision: `{run_meta.get('request_decision', '')}`
- call_mode: `{run_meta.get('call_mode', '')}`
- provider_configured: `{run_meta.get('provider_configured')}`
- network_call_allowed: `{run_meta.get('network_call_allowed')}`
- model_called: `{run_meta.get('model_called')}`
- ai_review_generated: `{run_meta.get('ai_review_generated')}`
- output_validation_status: `{run_meta.get('output_validation_status')}`
- real_model_call_error_type: `{run_meta.get('real_model_call_error_type')}`
- macro_web_research_requested: `{run_meta.get('macro_web_research_requested')}`

## Seguridad

- sql_real_written={run_meta['sql_real_written']}
- mt5_connected={run_meta['mt5_connected']}
- telegram_connected={run_meta['telegram_connected']}
- orders_sent={run_meta['orders_sent']}
- signals_generated={run_meta['signals_generated']}

## Siguiente Paso

Mantener `allow_network_call=false` por defecto en la UI. Para una llamada real se exige proveedor OpenAI, modelo, presupuesto, secreto externo, intencion manual, imagen/datos del paquete y validacion posterior del JSON.
"""


def write_artifacts(args: argparse.Namespace, result: dict[str, Any]) -> dict[str, Any]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_csv(tables_dir / "package_validation_audit.csv", result["package_validation_rows"])
    write_csv(tables_dir / "model_request_audit.csv", [result["request"]])
    write_csv(tables_dir / "model_response_audit.csv", result["output_validation_rows"])
    write_csv(tables_dir / "real_model_call_audit.csv", [result.get("model_call_audit", {})])
    write_csv(
        tables_dir / "safety_language_audit.csv",
        [
            {"check": "network_call_disabled_by_default", "status": "pass" if not args.allow_network_call else "warning", "evidence": args.allow_network_call},
            {"check": "model_not_called_by_default", "status": "pass" if not args.allow_network_call else "warning", "evidence": result["request"].get("model_called", False)},
            {"check": "blocked_phrases_configured", "status": "pass", "evidence": len(BLOCKED_PHRASES)},
            {"check": "real_provider_gated", "status": "pass", "evidence": "openai provider requires allow-network-call, secret and manual intent"},
            {"check": "macro_web_research_explicit_only", "status": "pass" if not args.macro_web_research or (args.allow_network_call and args.call_mode == "real") else "blocked", "evidence": args.macro_web_research},
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "issue_id": "MG-FC-01",
                "severity": "none" if result["request"]["request_decision"] in {"blocked_network_disabled", "blocked_by_missing_provider_config", "blocked_by_missing_manual_intent", "blocked_by_missing_secret"} else "medium",
                "status": "closed_fail_closed" if not args.allow_network_call else "review_required",
                "description": result["request"]["request_decision"],
                "mitigation": "Review real_model_call_audit and model_response_audit before trusting any generated report.",
            }
        ],
    )
    package_info = result["package_info"]
    fixture_output_validated = bool(args.fixture_output_json) and result["output_summary"]["output_validation_status"] == "pass"
    request_decision = result["request"]["request_decision"]
    if request_decision == "real_model_called" and result["output_summary"]["output_validation_status"] == "pass":
        decision = "codex_ai_analyst_real_model_review_v1_generated_and_validated"
    elif request_decision == "blocked_by_missing_secret":
        decision = "codex_ai_analyst_real_model_review_v1_ready_when_secret_configured"
    elif request_decision == "real_model_call_failed":
        decision = "codex_ai_analyst_real_model_review_v1_needs_provider_fix"
    else:
        decision = "codex_ai_analyst_model_call_controlled_v1_ready_for_dash_integration_design"
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": utc_now(),
        "decision": decision,
        "model_gateway_implemented": True,
        "model_call_controlled_implemented": True,
        "real_model_provider_implemented": True,
        "model_called": bool(result["request"].get("model_called")),
        "ai_review_generated": bool(result["request"].get("model_called")) and result["output_summary"]["output_validation_status"] == "pass",
        "fixture_output_validated": fixture_output_validated,
        "package_id": package_info.get("package_id", ""),
        "package_dir": result["package_dir"],
        "package_validation_decision": "pass" if package_info.get("safe_to_prepare_request") else "blocked",
        "request_decision": result["request"]["request_decision"],
        "call_mode": args.call_mode,
        "provider_configured": bool(result["request"]["config_complete"]),
        "api_key_env_var_configured": bool(args.api_key_env_var.strip()),
        "secret_present_boolean": bool(result["request"]["secret_present_boolean"]),
        "manual_intent_confirmed": bool(result["request"]["manual_intent_confirmed"]),
        "network_call_allowed": bool(args.allow_network_call),
        "macro_web_research_requested": bool(args.macro_web_research),
        "macro_web_research_default": False,
        "output_validation_status": result["output_summary"]["output_validation_status"],
        "real_model_call_error_type": result.get("model_call_audit", {}).get("error_type", ""),
        "real_model_call_http_status": result.get("model_call_audit", {}).get("http_status", ""),
        "model_id_effective": result.get("model_call_audit", {}).get("model_id_effective", args.model_id),
        "reasoning_effort_effective": result.get("model_call_audit", {}).get("reasoning_effort_effective", ""),
        "include_chart_image": bool(args.include_chart_image),
        "max_rows_per_csv": args.max_rows_per_csv,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    (args.output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=True), encoding="utf-8")
    (args.output_dir / "CODEX_AI_ANALYST_MODEL_CALL_CONTROLLED_V1.md").write_text(write_report(run_meta), encoding="utf-8")
    return run_meta


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AI Analyst packages through a controlled model-call gateway.")
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider-id", default="")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--max-prompt-tokens", type=int, default=0)
    parser.add_argument("--max-output-tokens", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--max-cost", default="")
    parser.add_argument("--allow-network-call", action="store_true")
    parser.add_argument("--call-mode", choices=["none", "fixture", "real"], default="none")
    parser.add_argument("--api-key-env-var", default="")
    parser.add_argument("--manual-intent", default="")
    parser.add_argument("--fixture-output-json", type=Path, default=None)
    parser.add_argument("--validate-output-json", type=Path, default=None)
    parser.add_argument("--include-chart-image", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-rows-per-csv", type=int, default=80)
    parser.add_argument("--macro-web-research", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = run_gateway(args)
    run_meta = write_artifacts(args, result)
    print(json.dumps({"decision": run_meta["decision"], "request_decision": run_meta["request_decision"]}, indent=2))


if __name__ == "__main__":
    main()
