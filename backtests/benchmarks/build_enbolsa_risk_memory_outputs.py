from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_INPUT_DIR = Path("artifacts/benchmark-significance/enbolsa/risk_sensitivity_2026-05-15")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "memory_outputs"

SCENARIOS = [
    ("observed_compounded_uncapped", "Observado\ncompuesto"),
    ("compounded_cap_10pct", "Compuesto\ncap 10%"),
    ("fixed_initial_uncapped", "Riesgo fijo\nsin cap"),
    ("fixed_initial_cap_3pct", "Riesgo fijo\ncap 3%"),
    ("fixed_initial_cap_5pct", "Riesgo fijo\ncap 5%"),
    ("fixed_initial_cap_10pct", "Riesgo fijo\ncap 10%"),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_tables(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tables = input_dir / "tables"
    extreme = pd.read_csv(tables / "extreme_block_focus.csv")
    aggregate = pd.read_csv(tables / "aggregate_by_strategy_sensitivity.csv")
    return extreme, aggregate


def _scenario_order(frame: pd.DataFrame) -> pd.DataFrame:
    order = {scenario: idx for idx, (scenario, _) in enumerate(SCENARIOS)}
    result = frame[frame["Scenario"].isin(order)].copy()
    result["scenario_order"] = result["Scenario"].map(order)
    return result.sort_values("scenario_order").drop(columns=["scenario_order"])


def _build_memory_table(extreme: pd.DataFrame, aggregate: pd.DataFrame) -> pd.DataFrame:
    extreme = _scenario_order(extreme)
    macd_agg = aggregate[aggregate["Variante"] == "enbolsa:macd_breakout"].copy()
    macd_agg = _scenario_order(macd_agg)
    labels = dict(SCENARIOS)

    rows = []
    for _, extreme_row in extreme.iterrows():
        scenario = extreme_row["Scenario"]
        agg_row = macd_agg[macd_agg["Scenario"] == scenario].iloc[0]
        rows.append({
            "Escenario": labels[scenario].replace("\n", " "),
            "Bloque extremo Return%": round(float(extreme_row["Return%"]), 2),
            "Bloque extremo PF": round(float(extreme_row["PF"]), 2),
            "Bloque extremo MaxDD%": round(float(extreme_row["MaxDD%"]), 2),
            "Bloques MeanReturn%": round(float(agg_row["MeanReturn%"]), 2),
            "Bloques MedianReturn%": round(float(agg_row["MedianReturn%"]), 2),
            "Bloques positivos%": round(float(agg_row["PositiveBlockRate%"]), 1),
            "Bloques MedianPF": round(float(agg_row["MedianPF"]), 2),
            "Max riesgo abierto micro%": round(float(agg_row["MaxOpenRiskMicro%"]), 2),
        })
    return pd.DataFrame(rows)


def _write_markdown_table(table: pd.DataFrame, output_path: Path) -> None:
    def markdown_table(frame: pd.DataFrame) -> str:
        cols = list(frame.columns)
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join(["---"] * len(cols)) + " |",
        ]
        for _, row in frame.iterrows():
            values = []
            for col in cols:
                value = row[col]
                if isinstance(value, float):
                    text = f"{value:.2f}"
                else:
                    text = str(value)
                values.append(text.replace("|", "\\|"))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    lines = [
        "# Tabla de memoria - sensibilidad de riesgo ENBOLSA",
        "",
        "La tabla resume `enbolsa:macd_breakout` usando el bloque extremo y la agregacion por 9 bloques.",
        "",
        markdown_table(table),
        "",
        "Lectura: el escenario observado explica el resultado canonico; los escenarios de riesgo fijo muestran que la ventaja disminuye, pero no desaparece.",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_academic_text(table: pd.DataFrame, output_path: Path) -> None:
    rows = table.set_index("Escenario")
    observed = rows.loc["Observado compuesto"]
    fixed = rows.loc["Riesgo fijo sin cap"]
    cap10_comp = rows.loc["Compuesto cap 10%"]
    cap10_fixed = rows.loc["Riesgo fijo cap 10%"]

    lines = [
        "# Texto academico - sensibilidad de riesgo ENBOLSA",
        "",
        "## Lectura propuesta para la memoria",
        "",
        (
            "El bloque `enbolsa:macd_breakout / Forex Majors / H1:H4` presenta en el "
            f"benchmark canonico un retorno del {observed['Bloque extremo Return%']:.2f}%. "
            "La cifra se reconstruye desde el `trade_log` del propio bloque, por lo que no "
            "procede de una mezcla incorrecta de bloques independientes ni de una pseudo-cartera global."
        ),
        "",
        (
            "La interpretacion metodologica requiere, sin embargo, separar dos efectos. "
            "En primer lugar, el escenario observado es compuesto: cada nueva operacion se dimensiona "
            "sobre el balance ya actualizado por las operaciones cerradas. En segundo lugar, el bloque "
            "no impone un limite operativo fuerte de exposicion agregada por divisa o correlacion."
        ),
        "",
        (
            "Cuando se elimina el compounding y se recalcula el mismo conjunto de operaciones con "
            f"riesgo fijo sobre el capital inicial, el retorno del bloque baja a {fixed['Bloque extremo Return%']:.2f}%. "
            "La reduccion es grande, lo que confirma que el 1405% no debe presentarse como rentabilidad "
            "live esperable. Aun asi, el resultado sigue siendo positivo, con PF "
            f"{fixed['Bloque extremo PF']:.2f} y MaxDD {fixed['Bloque extremo MaxDD%']:.2f}%."
        ),
        "",
        (
            "La comparacion con `compuesto cap 10%` ayuda a aislar el factor principal: con compounding "
            f"y cap 10%, el bloque queda en {cap10_comp['Bloque extremo Return%']:.2f}%, muy cerca del "
            "escenario observado. En cambio, con riesgo fijo y cap 10%, el resultado es "
            f"{cap10_fixed['Bloque extremo Return%']:.2f}%. Por tanto, la caida principal se explica por "
            "quitar reinversion del balance, no por el cap del 10%."
        ),
        "",
        (
            "En el agregado de 9 bloques, `macd_breakout` tambien conserva una lectura favorable: con "
            f"riesgo fijo sin cap mantiene MeanReturn% {fixed['Bloques MeanReturn%']:.2f}, "
            f"MedianReturn% {fixed['Bloques MedianReturn%']:.2f}, bloques positivos "
            f"{fixed['Bloques positivos%']:.1f}% y MedianPF {fixed['Bloques MedianPF']:.2f}. "
            "Esto permite defender la estrategia como empiricamente superior a los benchmarks simples "
            "dentro del protocolo actual, aunque no permite defender la cifra extrema como expectativa realista."
        ),
        "",
        "## Definiciones breves",
        "",
        "- `Sin cap`: no se bloquean nuevas operaciones por superar un limite de riesgo abierto agregado.",
        "- `Riesgo fijo`: cada operacion se recalcula como si el capital base siguiera siendo el inicial.",
        "- `Compuesto`: el tamano de nuevas operaciones crece o decrece con el balance liquidado.",
        "- `Cap`: restriccion que impide aceptar nuevas operaciones si el riesgo abierto supera un umbral.",
        "",
        "## Conclusion de uso",
        "",
        (
            "La salida correcta para la memoria es que `macd_breakout` sigue siendo defendible, pero "
            "la rentabilidad extrema debe explicarse como resultado de compounding y de un modelo "
            "multi-simbolo sin `RiskGuard` completo. El siguiente paso operativo no es optimizar caps "
            "sobre estos resultados, sino implementar una capa de `RiskGuard` con exposicion por divisa, "
            "correlacion y riesgo total abierto."
        ),
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _plot_memory_figure(table: pd.DataFrame, output_path: Path) -> None:
    labels = table["Escenario"].tolist()
    labels = [label.replace(" ", "\n", 1) for label in labels]
    extreme_return = table["Bloque extremo Return%"].astype(float).to_numpy()
    median_return = table["Bloques MedianReturn%"].astype(float).to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.4), constrained_layout=True)
    colors = ["#0077BB", "#3B82F6", "#64748B", "#33BBEE", "#009988", "#EE7733"]

    axes[0].bar(labels, extreme_return, color=colors, width=0.68)
    axes[0].set_title("El factor decisivo es quitar compounding", fontsize=13, fontweight="bold")
    axes[0].set_ylabel("Return% bloque Forex Majors H1:H4")
    axes[0].set_ylim(0, max(extreme_return) * 1.15)
    axes[0].grid(axis="y", alpha=0.2)
    for idx, value in enumerate(extreme_return):
        axes[0].text(idx, value + max(extreme_return) * 0.025, f"{value:.0f}%", ha="center", fontsize=9)

    axes[1].bar(labels, median_return, color=colors, width=0.68)
    axes[1].set_title("La ventaja mediana se mantiene", fontsize=13, fontweight="bold")
    axes[1].set_ylabel("MedianReturn% en 9 bloques")
    axes[1].set_ylim(0, max(median_return) * 1.30)
    axes[1].grid(axis="y", alpha=0.2)
    for idx, value in enumerate(median_return):
        axes[1].text(idx, value + max(median_return) * 0.035, f"{value:.1f}%", ha="center", fontsize=9)

    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", labelsize=9)

    fig.suptitle("Sensibilidad de riesgo: macd_breakout sigue positivo, pero el extremo se modera", fontsize=15, fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, facecolor="white")
    plt.close(fig)


def run(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not input_dir.is_absolute():
        input_dir = repo_root / input_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    extreme, aggregate = _read_tables(input_dir)
    table = _build_memory_table(extreme, aggregate)
    table.to_csv(output_dir / "tabla_memoria_sensibilidad_riesgo.csv", index=False)
    _write_markdown_table(table, output_dir / "tabla_memoria_sensibilidad_riesgo.md")
    _write_academic_text(table, output_dir / "texto_academico_sensibilidad_riesgo.md")
    _plot_memory_figure(table, output_dir / "figura_sensibilidad_riesgo_macd_breakout.png")
    print(f"Salidas de memoria escritas en: {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera tabla y figura de memoria para sensibilidad de riesgo ENBOLSA.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
