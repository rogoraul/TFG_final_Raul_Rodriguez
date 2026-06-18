from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "enbolsa_strategy_methodology_review_v1"
DEFAULT_BENCHMARK_TABLES_DIR = REPO_ROOT / "artifacts/benchmark-significance/enbolsa/final/tables"
DEFAULT_MATERIALITY_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_swing_materiality_audit_v1_2026-06-02"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_strategy_methodology_review_v1_2026-06-02"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/ENBOLSA_STRATEGY_METHODOLOGY_REVIEW_V1.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def as_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int:
    value_float = as_float(value)
    return int(value_float) if value_float is not None else 0


def pct(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{(numerator / denominator * 100.0):.2f}"


def strategy_rule_contract() -> list[dict[str, Any]]:
    return [
        {
            "strategy": "enbolsa:fib_limit",
            "entry_rule": "fib_limit",
            "entry_trigger": "touch_0_618_retracement",
            "uses_fibonacci_entry": True,
            "uses_macd_cross": False,
            "uses_trendline_break": False,
            "requires_setup_active": True,
            "requires_htf_trend_match": True,
            "requires_not_invalidated": True,
            "requires_w2_valid_80": True,
            "entry_price_model": "FIB_LEVEL_0.618 resting limit proxy",
            "stop_model": "W1_START_PRICE",
            "target_model": "W2 extreme plus W1 projection 1.0/1.618",
            "code_reference": "backtests/enbolsa/backtest_pipeline.py:_entry_signal,_make_position",
            "methodology_note": "Directamente sensible a la calidad/materialidad del W1 porque el nivel de entrada se deriva del Fibonacci W1/W2.",
        },
        {
            "strategy": "enbolsa:macd_breakout",
            "entry_rule": "macd_breakout",
            "entry_trigger": "W2 trendline break and MACD cross within memory window",
            "uses_fibonacci_entry": False,
            "uses_macd_cross": True,
            "uses_trendline_break": True,
            "requires_setup_active": True,
            "requires_htf_trend_match": True,
            "requires_not_invalidated": True,
            "requires_w2_valid_80": False,
            "entry_price_model": "close plus spread for long entries",
            "stop_model": "W2_SWING_PRICE fallback W1_START_PRICE",
            "target_model": "W2 extreme plus W1 projection 1.0/1.618",
            "code_reference": "backtests/enbolsa/backtest_pipeline.py:_macd_breakout_signal_from_arrays,_make_position",
            "methodology_note": "No entra por Fibonacci; hereda W1/W2 para estructura, stop y objetivos.",
        },
    ]


def implementation_audit() -> list[dict[str, Any]]:
    return [
        {
            "check_id": "IMPL01",
            "area": "setup_context",
            "status": "pass_with_caution",
            "finding": "Ambas reglas exigen setup activo, tendencia HTF compatible y setup no invalidado.",
            "evidence": "backtests/enbolsa/backtest_pipeline.py:_entry_signal,_macd_breakout_signal_from_arrays",
            "risk": "La calidad del setup W1/W2 afecta a ambas reglas.",
        },
        {
            "check_id": "IMPL02",
            "area": "fib_limit_entry",
            "status": "pass_with_caution",
            "finding": "fib_limit usa toque OHLC del nivel 0.618 y lo modela como orden resting.",
            "evidence": "docs/BENCHMARKS_ENBOLSA_TFG.md; backtests/enbolsa/backtest_pipeline.py:_entry_signal",
            "risk": "OHLC no reconstruye prioridad intrabar, fill parcial ni slippage de barrido.",
        },
        {
            "check_id": "IMPL03",
            "area": "macd_breakout_entry",
            "status": "pass",
            "finding": "macd_breakout no usa Fibonacci como gatillo; exige directriz W2 rota y cruce MACD reciente.",
            "evidence": "backtests/enbolsa/backtest_pipeline.py:_macd_breakout_signal_from_arrays",
            "risk": "El W1 pequeno puede afectar stop/objetivo aunque no active la entrada.",
        },
        {
            "check_id": "IMPL04",
            "area": "swing_generation",
            "status": "pass_with_caution",
            "finding": "Los swings provienen de pivotes ZigZag dinamicos por ATR mediana expansiva con floor/ceiling por grupo.",
            "evidence": "docs/DOCUMENTACION_BACKTEST_ENBOLSA.md; backtests/common/backtest_matrix_config.py",
            "risk": "Puede aceptar swings validos pero visualmente pequenos, especialmente en Forex Majors.",
        },
        {
            "check_id": "IMPL05",
            "area": "strategy_change",
            "status": "blocked",
            "finding": "No se modifica ningun umbral ni regla de ENBOLSA en esta fase.",
            "evidence": "audit_only",
            "risk": "Cambiar umbrales invalidaria la comparativa canonica y requeriria nueva validacion.",
        },
    ]


def materiality_rows(materiality_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    tables = materiality_dir / "tables"
    return (
        read_csv(tables / "enbolsa_swing_materiality_summary.csv"),
        read_csv(tables / "enbolsa_entry_rule_materiality.csv"),
        read_csv(tables / "enbolsa_timeframe_materiality.csv"),
    )


def materiality_findings(materiality_dir: Path) -> list[dict[str, Any]]:
    summary, by_group, by_timeframe = materiality_rows(materiality_dir)
    rows: list[dict[str, Any]] = []
    for row in summary:
        total = as_int(row.get("rows"))
        small = as_int(row.get("small")) + as_int(row.get("very_small"))
        rows.append(
            {
                "scope": "strategy",
                "strategy": clean(row.get("strategy")),
                "entry_rule": clean(row.get("entry_rule")),
                "group": "",
                "tf_pair": "",
                "rows": total,
                "very_small": as_int(row.get("very_small")),
                "small": as_int(row.get("small")),
                "small_or_very_small_rate_pct": pct(small, total),
                "median_w1_size_pct": clean(row.get("median_w1_size_pct")),
                "finding": (
                    "No very_small; materialidad general mas fuerte que fib_limit."
                    if clean(row.get("entry_rule")) == "macd_breakout"
                    else "No very_small, pero mayor concentracion de W1 small."
                ),
            }
        )
    for row in by_group:
        total = as_int(row.get("rows"))
        small = as_int(row.get("small")) + as_int(row.get("very_small"))
        rows.append(
            {
                "scope": "group",
                "strategy": "",
                "entry_rule": clean(row.get("entry_rule")),
                "group": clean(row.get("group")),
                "tf_pair": "",
                "rows": total,
                "very_small": as_int(row.get("very_small")),
                "small": as_int(row.get("small")),
                "small_or_very_small_rate_pct": pct(small, total),
                "median_w1_size_pct": clean(row.get("median_w1_size_pct")),
                "finding": "Forex Majors concentra la sensibilidad de W1 pequeno." if small else "Sin W1 small detectado en este grupo.",
            }
        )
    for row in by_timeframe:
        total = as_int(row.get("rows"))
        small = as_int(row.get("small")) + as_int(row.get("very_small"))
        rows.append(
            {
                "scope": "timeframe",
                "strategy": "",
                "entry_rule": clean(row.get("entry_rule")),
                "group": "",
                "tf_pair": f"{clean(row.get('timeframe_ltf'))}:{clean(row.get('timeframe_htf'))}",
                "rows": total,
                "very_small": as_int(row.get("very_small")),
                "small": as_int(row.get("small")),
                "small_or_very_small_rate_pct": pct(small, total),
                "median_w1_size_pct": clean(row.get("median_w1_size_pct")),
                "finding": "M30:H1 y H1:H4 son mas sensibles que H4:D1." if small else "Sin W1 small detectado en este timeframe.",
            }
        )
    return rows


def quantile(values: list[float], q: float) -> float | None:
    cleaned = sorted(value for value in values if value is not None and not isinstance(value, str))
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    pos = (len(cleaned) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(cleaned) - 1)
    if lower == upper:
        return cleaned[lower]
    return cleaned[lower] * (upper - pos) + cleaned[upper] * (pos - lower)


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}"


def w1_bar_duration_proxy_audit(materiality_dir: Path) -> list[dict[str, Any]]:
    rows = read_csv(materiality_dir / "enbolsa_swing_materiality_rows.csv")
    by_rule: dict[str, list[float]] = {"fib_limit": [], "macd_breakout": []}
    for row in rows:
        entry_rule = clean(row.get("entry_rule"))
        value = as_float(row.get("w1_size_pct"))
        if entry_rule in by_rule and value is not None:
            by_rule[entry_rule].append(value)

    output = [
        {
            "check_id": "W1BAR01",
            "scope": "artifact_schema",
            "entry_rule": "both",
            "status": "limited",
            "finding": "El trade_log canonico no guarda W1_START_TIME/W1_END_TIME ni barras entre pivotes.",
            "evidence": "trade_log.csv contiene W1_START_PRICE/W1_END_PRICE/W1_SIZE, pero no tiempos del W1.",
            "interpretation": "No se puede demostrar duracion exacta en barras sin regenerar contexto o ampliar schema.",
            "next_step": "Si se revalida ENBOLSA, anadir W1_START_TIME, W1_END_TIME, W1_BARS y PIVOT_DELAY.",
        },
        {
            "check_id": "W1BAR02",
            "scope": "code_path",
            "entry_rule": "both",
            "status": "pass",
            "finding": "W1 se crea desde pivotes ZigZag confirmados, no desde una vela aislada elegida manualmente.",
            "evidence": "market_context.py usa PIVOT_TYPE/PIVOT_VALUE confirmados; setup W1 nace al alternar low/high o high/low.",
            "interpretation": "Una W1 puede ser corta, pero no se fabrica como una barra cualquiera fuera del proceso ZigZag.",
            "next_step": "Mantener esta lectura como evidencia de implementacion, no como prueba de edge.",
        },
        {
            "check_id": "W1BAR03",
            "scope": "zigzag_threshold",
            "entry_rule": "both",
            "status": "pass_with_caution",
            "finding": "El ZigZag usa desviacion dinamica ATR mediana expansiva con floor por grupo.",
            "evidence": "Forex floor 0.35%, Metals floor 0.60%, Index floor 0.50%; shift_bars=1.",
            "interpretation": "Esto reduce el riesgo de pivotes por ruido minimo, aunque no elimina swings pequenos validos.",
            "next_step": "No cambiar thresholds sin nueva validacion.",
        },
    ]

    for entry_rule, values in by_rule.items():
        output.append(
            {
                "check_id": f"W1SIZE_{entry_rule}",
                "scope": "w1_size_distribution",
                "entry_rule": entry_rule,
                "status": "pass_with_caution",
                "finding": (
                    f"min={fmt(min(values) if values else None)}%, p01={fmt(quantile(values, 0.01))}%, "
                    f"p05={fmt(quantile(values, 0.05))}%, p10={fmt(quantile(values, 0.10))}%, "
                    f"median={fmt(quantile(values, 0.50))}%"
                ),
                "evidence": "enbolsa_swing_materiality_rows.csv",
                "interpretation": (
                    "No se observa W1 very_small por precio; fib_limit mantiene mas casos small."
                    if entry_rule == "fib_limit"
                    else "No se observa W1 very_small por precio; macd_breakout presenta menos casos small."
                ),
                "next_step": "Usar como proxy; no sustituye auditoria exacta de duracion en barras.",
            }
        )
    return output


def aggregate_rows(tables_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv(tables_dir / "aggregate_by_strategy.csv"):
        if clean(row.get("Variante")) in {"enbolsa:fib_limit", "enbolsa:macd_breakout"}:
            rows.append(
                {
                    "scope": "strategy",
                    "variant": clean(row.get("Variante")),
                    "group": "",
                    "tf_pair": "",
                    "blocks": clean(row.get("Blocks")),
                    "total_trades": clean(row.get("TotalTrades")),
                    "mean_return_pct": clean(row.get("MeanReturn%")),
                    "median_return_pct": clean(row.get("MedianReturn%")),
                    "min_return_pct": clean(row.get("MinReturn%")),
                    "max_return_pct": clean(row.get("MaxReturn%")),
                    "positive_block_rate_pct": clean(row.get("PositiveBlockRate%")),
                    "median_pf": clean(row.get("MedianPF")),
                    "methodology_note": "Bloques independientes; no equity global.",
                }
            )
    for row in read_csv(tables_dir / "aggregate_by_group.csv"):
        if clean(row.get("Variante")) in {"enbolsa:fib_limit", "enbolsa:macd_breakout"}:
            rows.append(
                {
                    "scope": "group",
                    "variant": clean(row.get("Variante")),
                    "group": clean(row.get("Group")),
                    "tf_pair": "",
                    "blocks": clean(row.get("Blocks")),
                    "total_trades": clean(row.get("TotalTrades")),
                    "mean_return_pct": clean(row.get("MeanReturn%")),
                    "median_return_pct": clean(row.get("MedianReturn%")),
                    "min_return_pct": clean(row.get("MinReturn%")),
                    "max_return_pct": clean(row.get("MaxReturn%")),
                    "positive_block_rate_pct": clean(row.get("PositiveBlockRate%")),
                    "median_pf": clean(row.get("MedianPF")),
                    "methodology_note": "Lectura por grupo; no extrapolar a cartera live.",
                }
            )
    for row in read_csv(tables_dir / "aggregate_by_tf_pair.csv"):
        if clean(row.get("Variante")) in {"enbolsa:fib_limit", "enbolsa:macd_breakout"}:
            rows.append(
                {
                    "scope": "tf_pair",
                    "variant": clean(row.get("Variante")),
                    "group": "",
                    "tf_pair": clean(row.get("TFPair")),
                    "blocks": clean(row.get("Blocks")),
                    "total_trades": clean(row.get("TotalTrades")),
                    "mean_return_pct": clean(row.get("MeanReturn%")),
                    "median_return_pct": clean(row.get("MedianReturn%")),
                    "min_return_pct": clean(row.get("MinReturn%")),
                    "max_return_pct": clean(row.get("MaxReturn%")),
                    "positive_block_rate_pct": clean(row.get("PositiveBlockRate%")),
                    "median_pf": clean(row.get("MedianPF")),
                    "methodology_note": "H4:D1 debe leerse como variante degradada cuando aplique.",
                }
            )
    return rows


def claim_policy() -> list[dict[str, Any]]:
    return [
        {
            "area": "macd_breakout",
            "allowed_claim": "macd_breakout no usa Fibonacci como condicion de entrada; usa rotura W2 y MACD reciente sobre contexto W1/W2.",
            "blocked_claim": "macd_breakout esta validado como sistema live robusto o independiente de la calidad de swings.",
            "recommended_wording": "macd_breakout es la regla mas defendible de ENBOLSA en los artifacts canonicos, con cautela por bloques extremos y modelo de portfolio.",
        },
        {
            "area": "fib_limit",
            "allowed_claim": "fib_limit usa el 0.618 como proxy OHLC de orden resting y es mas sensible a la materialidad de W1.",
            "blocked_claim": "fib_limit demuestra edge robusto o debe cambiarse sin revalidacion.",
            "recommended_wording": "fib_limit queda como regla secundaria/sensible; conviene presentarla por grupo/timeframe y no como conclusion global fuerte.",
        },
        {
            "area": "both",
            "allowed_claim": "La auditoria no detecta W1 very_small y documenta una sensibilidad small concentrada en Forex Majors.",
            "blocked_claim": "No existe ningun riesgo metodologico relacionado con swings pequenos.",
            "recommended_wording": "La sensibilidad no invalida automaticamente los resultados, pero bloquea overclaims y cualquier cambio sin nueva validacion.",
        },
    ]


def risk_register() -> list[dict[str, Any]]:
    return [
        {
            "risk_id": "ENB-STRAT01",
            "severity": "medium",
            "area": "fib_limit",
            "risk": "Al usar 0.618, un W1 valido pero pequeno puede producir niveles poco informativos.",
            "mitigation": "No cambiar regla ahora; documentar sensibilidad y revisar visualmente ejemplos small si se redacta fib_limit.",
        },
        {
            "risk_id": "ENB-STRAT02",
            "severity": "medium",
            "area": "macd_breakout",
            "risk": "El bloque Forex Majors H1:H4 puede dominar la lectura agregada.",
            "mitigation": "Presentar resultados por bloque y bloquear lectura como equity global.",
        },
        {
            "risk_id": "ENB-STRAT03",
            "severity": "low",
            "area": "materiality_audit",
            "risk": "BM_ATR_USED no esta disponible en los rows auditados; se usa fallback W1 porcentual sobre precio.",
            "mitigation": "Indicarlo como limitacion de auditoria, no como prueba definitiva ATR-normalizada.",
        },
        {
            "risk_id": "ENB-STRAT04",
            "severity": "high",
            "area": "strategy_change",
            "risk": "Endurecer umbrales ahora cambiaria la estrategia y romperia comparabilidad de artifacts canonicos.",
            "mitigation": "Mantener ENBOLSA intacto; abrir fase separada si se desea disenar umbral W1/ATR futuro.",
        },
    ]


def recommendation_rows() -> list[dict[str, Any]]:
    return [
        {
            "item": "macd_breakout",
            "decision": "keep_as_primary_strategy_evidence",
            "reason": "No depende de Fibonacci para entrar y los resultados canonicos son mejores, aunque no autorizan claims live.",
            "next_step": "Usar en memoria como evidencia principal ENBOLSA con lectura por bloques.",
        },
        {
            "item": "fib_limit",
            "decision": "keep_as_secondary_sensitive_strategy_evidence",
            "reason": "Es mas sensible a W1 small y sus resultados son mixtos/negativos en Forex Majors.",
            "next_step": "No modificar; tratar como regla sensible y limitar conclusiones.",
        },
        {
            "item": "strategy_modification",
            "decision": "do_not_change_now",
            "reason": "Cambiar reglas exige nuevo diseno, tests y revalidacion completa.",
            "next_step": "Si se reabre, disenar primero un threshold W1/ATR y validarlo en una fase separada.",
        },
    ]


def issues_or_risks() -> list[dict[str, Any]]:
    return [
        {
            "issue_id": "ENB-METH01",
            "severity": "medium",
            "status": "open",
            "description": "fib_limit queda metodologicamente mas delicada por dependencia directa del nivel Fibonacci W1/W2.",
            "mitigation": "No usar fib_limit como conclusion fuerte; documentar por grupo/timeframe.",
        },
        {
            "issue_id": "ENB-METH02",
            "severity": "medium",
            "status": "open",
            "description": "macd_breakout tiene resultados muy superiores pero con bloque extremo que debe aislarse.",
            "mitigation": "Evitar lectura agregada como cartera unica/live.",
        },
    ]


def render_doc(run_meta: dict[str, Any]) -> str:
    return f"""# ENBOLSA Strategy Methodology Review V1

Fecha: 2026-06-02

Decision: `{run_meta['decision']}`.

## Objetivo

Revisar `macd_breakout` y `fib_limit` sin modificar estrategias, sin ejecutar
backtests y sin generar senales. La fase contrasta reglas, dependencia de
swings, resultados canonicos y riesgos metodologicos.

## Lectura principal

- `macd_breakout` no entra por Fibonacci. Usa contexto W1/W2, tendencia HTF,
  rotura de directriz W2 y cruce MACD reciente.
- `fib_limit` si entra por Fibonacci: modela un toque del `0.618` como proxy
  OHLC de orden resting.
- Ambos dependen de que el W1/W2 sea razonable, pero `fib_limit` es el mas
  sensible a swings pequenos.
- No conviene cambiar reglas ahora: hacerlo requeriria nueva validacion y
  romperia la comparabilidad de los artifacts canonicos.

## Resultado de auditoria

- rules_reviewed={run_meta['rules_reviewed']}
- aggregate_rows_reviewed={run_meta['aggregate_rows_reviewed']}
- materiality_rows_reviewed={run_meta['materiality_rows_reviewed']}
- fib_limit_small_w1={run_meta['fib_limit_small_w1']}
- macd_breakout_small_w1={run_meta['macd_breakout_small_w1']}
- very_small_w1_total={run_meta['very_small_w1_total']}
- strategy_modified=false
- backtests_executed=false
- signals_generated=false

## Implicacion metodologica

`macd_breakout` queda separado de Fibonacci en la entrada: no usa el nivel
`0.618` como gatillo. Lo importante para esta regla es que el contexto W1/W2
sea razonable porque de ahi salen la estructura, el swing W2, stop y objetivos;
el disparo lo dan la rotura de directriz y el cruce MACD.

`fib_limit` si queda directamente unido al Fibonacci de W1/W2. Por tanto, si el
W1 es pequeno o poco representativo, el nivel `0.618` puede ser poco
informativo aunque el codigo haya aplicado correctamente la regla.

## W1 y riesgo de "una barra"

El `trade_log` canonico no guarda la duracion exacta del W1 en barras. Por eso
esta fase no afirma que todos los W1 tengan una duracion minima concreta. Lo que
si queda comprobado es que:

- W1 nace de pivotes ZigZag confirmados, no de una vela aislada elegida a mano;
- el ZigZag usa desviacion dinamica por ATR/precio con floors por grupo;
- la auditoria de tamano no detecta W1 `very_small`;
- para comprobar duracion exacta en barras habria que anadir en una fase futura
  `W1_START_TIME`, `W1_END_TIME`, `W1_BARS` y `PIVOT_DELAY` al artifact.

## Decision

Mantener ENBOLSA intacto. Usar `macd_breakout` como evidencia principal con
cautela, tratar `fib_limit` como regla secundaria/sensible y bloquear cualquier
claim de edge robusto, live trading o robustez futura.
"""


def build_outputs(args: argparse.Namespace) -> dict[str, Any]:
    contract = strategy_rule_contract()
    materiality = materiality_findings(args.materiality_dir)
    aggregates = aggregate_rows(args.benchmark_tables_dir)
    return {
        "contract": contract,
        "implementation": implementation_audit(),
        "materiality": materiality,
        "aggregates": aggregates,
        "claims": claim_policy(),
        "w1_bar_duration_proxy": w1_bar_duration_proxy_audit(args.materiality_dir),
        "risks": risk_register(),
        "recommendations": recommendation_rows(),
        "issues": issues_or_risks(),
    }


def write_outputs(args: argparse.Namespace, outputs: dict[str, Any], generated_at: str) -> dict[str, Any]:
    output_dir = args.output_dir
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    write_csv(tables_dir / "enbolsa_strategy_rule_contract.csv", outputs["contract"])
    write_csv(tables_dir / "enbolsa_strategy_implementation_audit.csv", outputs["implementation"])
    write_csv(tables_dir / "enbolsa_strategy_materiality_findings.csv", outputs["materiality"])
    write_csv(tables_dir / "enbolsa_strategy_result_context.csv", outputs["aggregates"])
    write_csv(tables_dir / "enbolsa_strategy_claim_policy.csv", outputs["claims"])
    write_csv(tables_dir / "enbolsa_w1_bar_duration_proxy_audit.csv", outputs["w1_bar_duration_proxy"])
    write_csv(tables_dir / "enbolsa_strategy_methodology_risk_register.csv", outputs["risks"])
    write_csv(tables_dir / "enbolsa_strategy_recommendations.csv", outputs["recommendations"])
    write_csv(tables_dir / "issues_or_risks.csv", outputs["issues"])

    decision = "enbolsa_strategy_methodology_review_v1_keep_strategies_unchanged"
    materiality_summary = [row for row in outputs["materiality"] if row.get("scope") == "strategy"]
    materiality_by_rule = {clean(row.get("entry_rule")): row for row in materiality_summary}
    fib_small = as_int(materiality_by_rule.get("fib_limit", {}).get("small")) + as_int(
        materiality_by_rule.get("fib_limit", {}).get("very_small")
    )
    macd_small = as_int(materiality_by_rule.get("macd_breakout", {}).get("small")) + as_int(
        materiality_by_rule.get("macd_breakout", {}).get("very_small")
    )
    very_small_total = sum(as_int(row.get("very_small")) for row in materiality_summary)
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": generated_at,
        "decision": decision,
        "rules_reviewed": len(outputs["contract"]),
        "aggregate_rows_reviewed": len(outputs["aggregates"]),
        "materiality_rows_reviewed": len(outputs["materiality"]),
        "fib_limit_small_w1": fib_small,
        "macd_breakout_small_w1": macd_small,
        "very_small_w1_total": very_small_total,
        "strategy_modified": False,
        "fib_limit_modified": False,
        "macd_breakout_modified": False,
        "backtests_executed": False,
        "signals_generated": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "wavecount_used_as_filter": False,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")
    report = render_doc(run_meta)
    (output_dir / "ENBOLSA_STRATEGY_METHODOLOGY_REVIEW_V1.md").write_text(report, encoding="utf-8")
    args.doc_path.write_text(report, encoding="utf-8")
    return run_meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit ENBOLSA strategy methodology without changing rules.")
    parser.add_argument("--benchmark-tables-dir", type=Path, default=DEFAULT_BENCHMARK_TABLES_DIR)
    parser.add_argument("--materiality-dir", type=Path, default=DEFAULT_MATERIALITY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    generated_at = utc_now()
    outputs = build_outputs(args)
    return write_outputs(args, outputs, generated_at)


if __name__ == "__main__":
    main()
