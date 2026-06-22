# Tablas para la memoria

Fecha de preparacion: 2026-06-11.

Esta carpeta contiene fragmentos LaTeX listos para incluir con `\input{...}`
desde los capitulos de la memoria. Las tablas no recalculan resultados; son una
version reducida de las salidas usadas durante el trabajo.

## Notas

- No interpretar agregados de benchmark como una cartera unica.
- No convertir resultados de backtesting en promesas de rentabilidad futura.
- No presentar MT5, RiskGuard, Telegram ni AI Analyst como sistema live o
  autonomo.
- Mantener captions y fuentes coherentes con la memoria.
- Si se cambia un CSV fuente, regenerar o revisar manualmente la tabla afectada.

## Inventario

| Tabla | Archivo LaTeX | Fuente principal | Uso recomendado | Nota |
| --- | --- | --- | --- | --- |
| Resumen benchmark W2 | `tabla_benchmarks_w2_resumen_estrategia.tex` | `../04_fuentes_csv/benchmark_w2/aggregate_by_strategy.csv` | Cuerpo de resultados cuantitativos. | Agregados sobre 9 bloques independientes. |
| Bloques benchmark W2 | `tabla_benchmarks_w2_bloques_seleccionados.tex` | `../04_fuentes_csv/benchmark_w2/block_metrics.csv` | Preferiblemente anexo o discusion extendida. | Tabla larga; H4:D1 se marca como degradado. |
| Menendez/Elliott | `tabla_menendez_variantes.tex` | `../04_fuentes_csv/menendez/summary_by_variant.csv` | Cuerpo metodologico o anexo. | Resultado acotado, no edge operativo. |
| WaveCount/WeaveCount | `tabla_wavecount_contexto.tex` | `../04_fuentes_csv/wavecount/context_quality_summary.csv` | Cuerpo/anexo de estudio estructural. | Contexto de revision; no filtro automatico. |
| MT5, RiskGuard y Telegram | `tabla_mt5_riskguard_telegram_cierre.tex` | Docs de cierre y artifacts MT5/Telegram/RiskGuard | Cierre tecnico de plataforma. | Demo, control y observabilidad; no live. |
| AI Analyst safety | `tabla_ai_analyst_safety.tex` | `../04_fuentes_csv/ai_analyst/ai_analyst_safety_audit.csv` | Cuerpo/anexo de seguridad. | Asistente de revision, no decisor. |

## Comandos de verificacion sugeridos

```powershell
python -m py_compile trading_center\dash_readonly_app.py
pdflatex -interaction=nonstopmode -halt-on-error memoria_tfg.tex
```

El segundo comando debe ejecutarse desde `docs/Memoria TFG` cuando las tablas se
incluyan realmente en los capitulos.
