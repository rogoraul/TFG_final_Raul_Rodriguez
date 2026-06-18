# Auditoria operativa RiskGuard ENBOLSA

Fecha de ejecucion: `2026-05-15T12:09:32`

## Reproducibilidad

```powershell
python -m backtests.benchmarks.run_enbolsa_riskguard_audit --trade-log artifacts\benchmark-significance\enbolsa\final\tables\trade_log.csv --output-dir artifacts\benchmark-significance\enbolsa\riskguard_audit_2026-05-15 --strategy enbolsa:macd_breakout --max-total-open-risk-pct 5 --max-symbol-open-risk-pct 1 --max-currency-gross-risk-pct 3 --max-currency-net-risk-pct 3 --initial-capital 10000 --risk-mode fixed_initial --risk-per-trade-pct 1
```

Esta auditoria no reejecuta senales ni modifica la estrategia original. Reutiliza el `trade_log` canonico y simula una capa operativa first-come-first-served.

## Politica aplicada

- estrategia: `enbolsa:macd_breakout`
- risk_mode: `fixed_initial`
- risk_per_trade_pct: `1.0`
- max_total_open_risk_pct: `5.0`
- max_symbol_open_risk_pct: `1.0`
- max_currency_gross_risk_pct: `3.0`
- max_currency_net_risk_pct: `3.0`
- granularidad: cada setup completo se acepta o rechaza de forma atomica; el riesgo se libera por pata cuando cada TP/SL sale del mercado.
- diversificacion: exposicion por divisa base/quote y direccion; no correlacion estadistica.

## Comparacion por bloque

| Group | TFPair | OriginalTrades | RiskGuardTrades | OriginalReturn% | RiskGuardReturn% | OriginalPF | RiskGuardPF | OriginalMaxDD% | RiskGuardMaxDD% | AcceptanceRate% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Forex Majors | H1:H4 | 4670 | 3744 | 1405 | 290.5 | 1.13 | 1.24 | 37 | 17.33 | 80.17 |
| Forex Majors | H4:D1 | 1282 | 1140 | 21.62 | 30.1 | 1.04 | 1.08 | 39.8 | 30.47 | 88.92 |
| Forex Majors | M30:H1 | 6072 | 4404 | -7.37 | 6.08 | 1 | 1 | 69.72 | 46.04 | 72.53 |
| Index | H1:H4 | 1608 | 1304 | 86.51 | 48.41 | 1.15 | 1.12 | 34.54 | 34.37 | 81.09 |
| Index | H4:D1 | 396 | 306 | 6 | 19 | 1.05 | 1.2 | 17.15 | 11.7 | 77.27 |
| Index | M30:H1 | 3582 | 2788 | 165.9 | 143.5 | 1.08 | 1.16 | 42.94 | 15.89 | 77.83 |
| Metals | H1:H4 | 844 | 690 | 44.17 | 51.83 | 1.15 | 1.27 | 15.51 | 11.35 | 81.75 |
| Metals | H4:D1 | 242 | 202 | 36.28 | 30.44 | 1.73 | 1.82 | 7.61 | 6.27 | 83.47 |
| Metals | M30:H1 | 1520 | 1172 | 15.87 | 46.29 | 1.04 | 1.14 | 33.24 | 26.6 | 77.11 |

## Bloque extremo Forex Majors H1:H4

| OriginalTrades | RiskGuardTrades | OriginalReturn% | RiskGuardReturn% | OriginalPF | RiskGuardPF | OriginalMaxDD% | RiskGuardMaxDD% | AcceptanceRate% | TopRejectionReasons | MaxCurrencyExposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4670 | 3744 | 1405 | 290.5 | 1.13 | 1.24 | 37 | 17.33 | 80.17 | {"total_open_risk_cap": 389, "currency_gross_cap": 53, "symbol_open_risk_cap": 21} | AUD gross 3.00% |

## Motivos de rechazo

| rejection_reason | Setups |
| --- | --- |
| total_open_risk_cap | 1141 |
| currency_gross_cap | 904 |
| symbol_open_risk_cap | 188 |

## Exposicion maxima por divisa

| BlockId | Currency | MaxLongRisk% | MaxShortRisk% | MaxGrossRisk% | MaxAbsNetRisk% |
| --- | --- | --- | --- | --- | --- |
| forex-majors-h1-h4 | AUD | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | CAD | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | CHF | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | EUR | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | GBP | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | JPY | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | NZD | 3 | 3 | 3 | 3 |
| forex-majors-h1-h4 | USD | 3 | 3 | 3 | 3 |
| forex-majors-h4-d1 | AUD | 3 | 2.5 | 3 | 3 |
| forex-majors-h4-d1 | CAD | 3 | 3 | 3 | 3 |
| forex-majors-h4-d1 | CHF | 3 | 2 | 3 | 3 |
| forex-majors-h4-d1 | EUR | 3 | 3 | 3 | 3 |
| forex-majors-h4-d1 | GBP | 2 | 3 | 3 | 3 |
| forex-majors-h4-d1 | JPY | 3 | 3 | 3 | 3 |
| forex-majors-h4-d1 | NZD | 2 | 3 | 3 | 3 |
| forex-majors-h4-d1 | USD | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | AUD | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | CAD | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | CHF | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | EUR | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | GBP | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | JPY | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | NZD | 3 | 3 | 3 | 3 |
| forex-majors-m30-h1 | USD | 3 | 3 | 3 | 3 |
| index-h1-h4 | EUR | 1.5 | 1.5 | 3 | 0 |
| index-h1-h4 | USD | 1.5 | 1.5 | 3 | 0 |
| index-h4-d1 | EUR | 1.5 | 1.5 | 3 | 0 |
| metals-h4-d1 | EUR | 1.5 | 1.5 | 3 | 0 |
| metals-m30-h1 | EUR | 1.5 | 1.5 | 3 | 0 |
| metals-h4-d1 | USD | 1.5 | 1.5 | 3 | 0 |

## Lectura

- Esta salida no sustituye al benchmark canonico; es una subfase operativa.
- Si la rentabilidad cae, la lectura no es que la estrategia original estuviera mal, sino que un bot real necesita limitar exposicion agregada.
- La correlacion queda para una posible v1.5; en v1 se mide concentracion por divisa y direccion.
