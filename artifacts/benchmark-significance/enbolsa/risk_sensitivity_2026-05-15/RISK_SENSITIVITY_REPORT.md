# Sensibilidad de riesgo ENBOLSA

Fecha de ejecucion: `2026-05-15T10:55:40`

## Reproducibilidad

```powershell
python -m backtests.benchmarks.analyze_enbolsa_risk_sensitivity --trade-log artifacts\benchmark-significance\enbolsa\final\tables\trade_log.csv --output-dir artifacts\benchmark-significance\enbolsa\risk_sensitivity_2026-05-15 --strategies enbolsa:fib_limit,enbolsa:macd_breakout --caps 3,5,10 --initial-capital 10000 --risk-per-trade 0.01
```

Estrategias procesadas: `enbolsa:fib_limit, enbolsa:macd_breakout`.

La prueba reutiliza el `trade_log` canonico y no cambia reglas de entrada, salida, TP, SL ni filtros.

## Bloque extremo

| Scenario | Trades | SetupsAccepted | SetupsSkipped | Return% | PF | MaxDD% | NetProfit | AvgR | MaxOpenRiskMicro% | MaxOpenRiskSetup% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| compounded_cap_10pct | 4650 | 2325 | 10 | 1409 | 1.14 | 37 | 1.409e+05 | 0.146 | 9.94 | 15.34 |
| compounded_cap_3pct | 2784 | 1392 | 943 | 992.6 | 1.26 | 27.22 | 9.926e+04 | 0.195 | 3 | 5.3 |
| compounded_cap_5pct | 3738 | 1869 | 466 | 1837 | 1.22 | 30.45 | 1.837e+05 | 0.186 | 5 | 9.56 |
| fixed_initial_cap_10pct | 4652 | 2326 | 9 | 341.4 | 1.22 | 14.52 | 3.414e+04 | 0.147 | 3.95 | 4.84 |
| fixed_initial_cap_3pct | 2952 | 1476 | 859 | 273.5 | 1.28 | 14.62 | 2.735e+04 | 0.185 | 2.53 | 3.09 |
| fixed_initial_cap_5pct | 3814 | 1907 | 428 | 323.8 | 1.26 | 14.52 | 3.238e+04 | 0.17 | 3.46 | 4.12 |
| fixed_initial_uncapped | 4670 | 2335 | 0 | 340.1 | 1.22 | 14.52 | 3.401e+04 | 0.146 | 4.35 | 5.19 |
| observed_compounded_uncapped | 4670 | 2335 | 0 | 1405 | 1.13 | 37 | 1.405e+05 | 0.146 | 11.77 | 16.69 |

## Agregado macd_breakout

| Scenario | Blocks | TotalTrades | TotalNetProfit | MeanReturn% | MedianReturn% | PositiveBlockRate% | MedianPF | MedianMaxDD% | MaxOpenRiskMicro% | MaxOpenRiskSetup% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| compounded_cap_10pct | 9 | 20076 | 1.786e+05 | 198.5 | 36.28 | 100 | 1.08 | 34.54 | 9.99 | 15.34 |
| compounded_cap_3pct | 9 | 13176 | 1.361e+05 | 151.2 | 31.86 | 88.9 | 1.13 | 28.64 | 3 | 5.3 |
| compounded_cap_5pct | 9 | 17098 | 2.201e+05 | 244.6 | 36.28 | 88.9 | 1.08 | 33.24 | 5 | 9.56 |
| fixed_initial_cap_10pct | 9 | 20092 | 7.636e+04 | 84.84 | 43.2 | 100 | 1.12 | 25.48 | 10.3 | 13.7 |
| fixed_initial_cap_3pct | 9 | 13926 | 5.864e+04 | 65.16 | 32.82 | 88.9 | 1.14 | 20.54 | 5.47 | 7.57 |
| fixed_initial_cap_5pct | 9 | 17474 | 7.481e+04 | 83.12 | 43.2 | 100 | 1.13 | 22.31 | 7.84 | 9.91 |
| fixed_initial_uncapped | 9 | 20216 | 7.588e+04 | 84.32 | 43.2 | 100 | 1.12 | 25.48 | 12.68 | 16.86 |
| observed_compounded_uncapped | 9 | 20216 | 1.774e+05 | 197.1 | 36.28 | 88.9 | 1.08 | 34.54 | 16.19 | 18.34 |

## Lectura

- El bloque `Forex Majors / H1:H4` sigue siendo positivo en escenarios de riesgo fijo y caps, pero el retorno cae mucho frente al compuesto sin cap.
- Los caps se aplican sobre riesgo abierto de micro-patas; el diagnostico por setup completo puede superar el cap porque conserva el riesgo teorico del setup hasta la ultima salida.
- Los escenarios con cap son path-dependent: si el cap salta operaciones perdedoras, puede mejorar el resultado. No deben interpretarse como optimizacion de cap.
- El resultado canonico no parece un error de calculo; refleja un modelo operativo agresivo.
- Para la memoria conviene presentar `macd_breakout` como estrategia con evidencia favorable, condicionada por riesgo agregado y no como rentabilidad live esperable.
- Para bot o screener operativo, el siguiente requisito es un `RiskGuard` con cap de riesgo abierto y control de correlaciones.

## Archivos

- `tables/scenario_block_metrics.csv`
- `tables/aggregate_by_strategy_sensitivity.csv`
- `tables/extreme_block_focus.csv`
- `run_meta.json`
