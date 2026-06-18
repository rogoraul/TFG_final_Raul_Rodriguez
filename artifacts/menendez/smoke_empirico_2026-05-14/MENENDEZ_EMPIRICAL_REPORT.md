# Cierre empirico Menendez

Fecha de ejecucion: `2026-05-14T19:09:26`

## Reproducibilidad

Comando equivalente:

```powershell
python -m backtests.menendez.run_empirical_close --output-dir artifacts/menendez/smoke_empirico_2026-05-14 --variants faithful_operable_sma200_primary,faithful_operable_trigger_or,experimental_composite_x --group "Forex Majors" --timeframe-ltf M30 --timeframe-htf H4 --symbols EURUSD.r --no-parallel
```

Configuracion:

- grupo: `Forex Majors`
- timeframe: `H4 -> M30`
- variantes: `faithful_operable_sma200_primary, faithful_operable_trigger_or, experimental_composite_x`
- simbolos cargados: `1` de `1`
- cache: `use_cache=True`, `use_disk_cache=True`, `force_rebuild=False`

## Decision

Clasificacion final: **bloque metodologico sin edge demostrado**.

Menendez queda por debajo de ENBOLSA como eje empirico. La linea es util para el TFG como formalizacion metodologica auditada, pero no demuestra edge robusto con esta corrida.

## Resumen por variante

| Variante | LTF | HTF | Trades | WR% | AvgWin% | AvgLoss% | R:R | PF | Return% | Sharpe | Sortino | MaxDD% | Calmar | Variant | VariantClass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| menendez_core | M30 | H4 | 8 | 25 | 1.23 | -1.11 | 1.11 | 0.37 | -4.16 | -1.46 | -22.81 | 4.25 | -0.17 | faithful_operable_sma200_primary | resultado_valido |
| menendez_core | M30 | H4 | 11 | 27.3 | 2.48 | -1.06 | 2.35 | 0.86 | -1.2 | -0.16 | -7.43 | 4.19 | -0.05 | faithful_operable_trigger_or | resultado_valido |
| menendez_core | M30 | H4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | experimental_composite_x | resultado_exploratorio |

Trades totales agregados en variantes: `19`.

Mejor variante por retorno/PF/trades:

- `experimental_composite_x`: Trades `0`, PF `0.0`, Return% `0.0`, MaxDD% `0.0`.

## Estabilidad por simbolo

Top filas por retorno dentro de cada variante:

| Variant | Activo | Trades | WR% | AvgWin% | AvgLoss% | R:R | PF | Return% | Sharpe | Sortino | MaxDD% | Calmar | NetProfit | Expectancy | AvgR | ExpectancyR | Exposure% | ReturnOverDrawdown | Velas | H4_BLOCKED | HTF_OK | SETUP_ROWS | RETRACE_OK | FAN_BREAKOUT | MACD_TRIGGER | STOCH_TRIGGER | RR_OK | ENTRY_READY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| experimental_composite_x | EURUSD.r | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 101654 | 77720 | 23861 | 3490 | 626 | 3484 | 4 | 133 | 95 | 0 |
| faithful_operable_sma200_primary | EURUSD.r | 8 | 25 | 1.23 | -1.11 | 1.11 | 0.37 | -4.16 | -1.46 | -22.81 | 4.25 | -0.17 | -416.4 | -52.04 | -0.525 | -0.525 | 0.04 | -0.98 | 101654 | 77720 | 23861 | 3490 | 734 | 3481 | 4 | 133 | 479 | 12 |
| faithful_operable_trigger_or | EURUSD.r | 11 | 27.3 | 2.48 | -1.06 | 2.35 | 0.86 | -1.2 | -0.16 | -7.43 | 4.19 | -0.05 | -119.7 | -10.88 | -0.092 | -0.092 | 0.45 | -0.29 | 101654 | 89403 | 12160 | 1762 | 414 | 1759 | 5 | 78 | 292 | 20 |

## Embudo de senales

| Activo | Velas | H4_BLOCKED | HTF_OK | SETUP_ROWS | RETRACE_OK | FAN_BREAKOUT | MACD_TRIGGER | STOCH_TRIGGER | RR_OK | ENTRY_READY | Variant | VariantClass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD.r | 101654 | 77720 | 23861 | 3490 | 734 | 3481 | 4 | 133 | 479 | 12 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | 101654 | 77720 | 23861 | 3490 | 734 | 3481 | 4 | 133 | 479 | 12 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | 101654 | 89403 | 12160 | 1762 | 414 | 1759 | 5 | 78 | 292 | 20 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | 101654 | 89403 | 12160 | 1762 | 414 | 1759 | 5 | 78 | 292 | 20 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | 101654 | 77720 | 23861 | 3490 | 626 | 3484 | 4 | 133 | 95 | 0 | experimental_composite_x | resultado_exploratorio |
| TOTAL | 101654 | 77720 | 23861 | 3490 | 626 | 3484 | 4 | 133 | 95 | 0 | experimental_composite_x | resultado_exploratorio |

## Principales bloqueos

| Activo | BLOCK_REASON | Rows | Variant | VariantClass |
| --- | --- | --- | --- | --- |
| EURUSD.r | H4_BEARISH_FAN_MISSING | 35837 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_BULLISH_FAN_MISSING | 33660 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_SMA200_BULL_FILTER_MISSING | 4471 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_SMA200_BEAR_FILTER_MISSING | 3752 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | RETRACE_TOO_DEEP | 1752 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | RETRACE_BELOW_MIN | 1004 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | MOMENTUM_CONFIRM_MISSING | 705 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | RR_BELOW_MIN | 17 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | H4_BEARISH_FAN_MISSING | 35837 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | H4_BULLISH_FAN_MISSING | 33660 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | H4_SMA200_BEAR_FILTER_MISSING | 3752 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | H4_SMA200_BULL_FILTER_MISSING | 4471 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | MOMENTUM_CONFIRM_MISSING | 705 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | RETRACE_BELOW_MIN | 1004 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | RETRACE_TOO_DEEP | 1752 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | RR_BELOW_MIN | 17 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_MACD_NEUTRAL | 70469 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | H4_BEARISH_FAN_MISSING | 9748 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | H4_BULLISH_FAN_MISSING | 9186 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | RETRACE_BELOW_MIN | 681 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | RETRACE_TOO_DEEP | 667 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | MOMENTUM_CONFIRM_MISSING | 391 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | RR_BELOW_MIN | 3 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | H4_BEARISH_FAN_MISSING | 9748 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | H4_BULLISH_FAN_MISSING | 9186 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | H4_MACD_NEUTRAL | 70469 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | MOMENTUM_CONFIRM_MISSING | 391 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | RETRACE_BELOW_MIN | 681 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | RETRACE_TOO_DEEP | 667 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | RR_BELOW_MIN | 3 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | H4_BEARISH_FAN_MISSING | 35837 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | H4_BULLISH_FAN_MISSING | 33660 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | H4_SMA200_BULL_FILTER_MISSING | 4471 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | H4_SMA200_BEAR_FILTER_MISSING | 3752 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | RETRACE_TOO_DEEP | 2251 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | RETRACE_BELOW_MIN | 613 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | MOMENTUM_CONFIRM_MISSING | 603 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | RR_BELOW_MIN | 23 | experimental_composite_x | resultado_exploratorio |
| TOTAL | H4_BEARISH_FAN_MISSING | 35837 | experimental_composite_x | resultado_exploratorio |
| TOTAL | H4_BULLISH_FAN_MISSING | 33660 | experimental_composite_x | resultado_exploratorio |

## Comparacion conceptual con ENBOLSA

Referencia canonica ENBOLSA `macd_breakout` tomada de `artifacts/benchmark-significance/enbolsa/final/tables/aggregate_by_strategy.csv`:

| Variante | Family | MetricScope | Blocks | TotalTrades | TotalNetProfit | MeanReturn% | MedianReturn% | MinReturn% | MaxReturn% | StdReturn% | PositiveBlocks | PositiveBlockRate% | MeanPF | MedianPF | MeanMaxDD% | MedianMaxDD% | MeanSharpe | MedianSharpe | MeanSortino | MedianSortino | MeanCalmar | MedianCalmar | MeanExposure% | MedianExposure% | MeanReturnOverDrawdown | MedianReturnOverDrawdown | MeanAvgR | MedianAvgR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| enbolsa:macd_breakout | enbolsa | block_aggregate | 9 | 20216 | 1.774e+05 | 197.1 | 36.28 | -7.37 | 1405 | 430 | 8 | 88.9 | 1.15 | 1.08 | 33.06 | 34.54 | 1.49 | 1.41 | 5.11 | 5.32 | 0.19 | 0.16 | 190.1 | 145.4 | 5.91 | 2.51 | 0.093 | 0.075 |

Lectura: ENBOLSA ya tiene un benchmark por bloques y evidencia positiva documentada. Menendez, en cambio, genera pocas senales y no muestra estabilidad suficiente como para sostenerlo como eje empirico principal.

## Archivos generados

- `tables/summary_by_variant.csv`
- `tables/symbol_stability.csv`
- `tables/stage_counts_by_variant.csv`
- `tables/block_reasons_by_variant.csv`
- `tables/status_distribution_by_variant.csv`
- `tables/period_metrics_by_variant.csv`
- `tables/exit_breakdown_by_variant.csv`
- `tables/trade_log_all.csv`
- `tables/risk_audit_all.csv`
- `tables/current_screener_rows.csv`
- `run_meta.json`

## Limitaciones

- No se han optimizado reglas ni parametros.
- No hay simulacion tick a tick ni swap.
- El resultado depende de los datos SQL/MT5 locales y de la cache indicada.
- `experimental_composite_x` es metodologicamente relevante, pero sigue sin edge demostrado.
