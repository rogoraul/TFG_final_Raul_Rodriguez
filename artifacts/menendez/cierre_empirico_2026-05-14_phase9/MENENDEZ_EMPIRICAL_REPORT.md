# Cierre empirico Menendez

Fecha de ejecucion: `2026-05-14T20:06:14`

## Reproducibilidad

Comando equivalente:

```powershell
python -m backtests.menendez.run_empirical_close --output-dir artifacts\menendez\cierre_empirico_2026-05-14_phase9 --variants faithful_operable_sma200_primary,faithful_operable_trigger_or,experimental_composite_x --group "Forex Majors" --timeframe-ltf M30 --timeframe-htf H4 --limit-symbols 9 --max-workers 4
```

Configuracion:

- grupo: `Forex Majors`
- timeframe: `H4 -> M30`
- variantes: `faithful_operable_sma200_primary, faithful_operable_trigger_or, experimental_composite_x`
- simbolos cargados: `9` de `9`
- cache: `use_cache=True`, `use_disk_cache=True`, `force_rebuild=False`

Alcance:

- Esta fase cierra un bloque acotado de 9 simbolos de `Forex Majors`.
- Se intento antes una ejecucion completa sin `--limit-symbols`; se detuvo tras mas de 20 minutos sin tablas finales escritas.
- La trazabilidad del intento completo y de esta fase esta en `RUN_ATTEMPTS.md`.

## Decision

Clasificacion final: **bloque metodologico sin edge demostrado**.

Menendez queda por debajo de ENBOLSA como eje empirico. La linea es util para el TFG como formalizacion metodologica auditada, pero no demuestra edge robusto con esta corrida.

## Resumen por variante

| Variante | LTF | HTF | Trades | WR% | AvgWin% | AvgLoss% | R:R | PF | Return% | Sharpe | Sortino | MaxDD% | Calmar | Variant | VariantClass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| menendez_core | M30 | H4 | 45 | 26.7 | 1.27 | -1.08 | 1.18 | 0.42 | -18.71 | -2.88 | -53.51 | 17.86 | -0.14 | faithful_operable_sma200_primary | resultado_valido |
| menendez_core | M30 | H4 | 49 | 32.7 | 1.51 | -1.06 | 1.42 | 0.68 | -10.64 | -1.15 | -49.4 | 9.71 | -0.14 | faithful_operable_trigger_or | resultado_valido |
| menendez_core | M30 | H4 | 10 | 20 | 1.06 | -1.04 | 1.02 | 0.26 | -6.03 | -2.32 | -35.31 | 7.99 | -0.13 | experimental_composite_x | resultado_exploratorio |

Trades totales agregados en variantes: `104`.

Variante menos negativa por retorno en esta corrida:

- `experimental_composite_x`: Trades `10`, PF `0.26`, Return% `-6.03`, MaxDD% `7.99`.
- Esta etiqueta no implica edge: solo identifica la menor perdida agregada de la tabla.

## Estabilidad por simbolo

Top filas por retorno dentro de cada variante:

| Variant | Activo | Trades | WR% | AvgWin% | AvgLoss% | R:R | PF | Return% | Sharpe | Sortino | MaxDD% | Calmar | NetProfit | Expectancy | AvgR | ExpectancyR | Exposure% | ReturnOverDrawdown | Velas | H4_BLOCKED | HTF_OK | SETUP_ROWS | RETRACE_OK | FAN_BREAKOUT | MACD_TRIGGER | STOCH_TRIGGER | RR_OK | ENTRY_READY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| experimental_composite_x | EURUSD.r | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 101654 | 77720 | 23861 | 3490 | 626 | 3484 | 4 | 133 | 95 | 0 |
| experimental_composite_x | GBPUSD.r | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 59818 | 46777 | 12982 | 1884 | 263 | 1882 | 9 | 76 | 39 | 0 |
| experimental_composite_x | USDCHF.r | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 59817 | 46009 | 13758 | 2076 | 319 | 2073 | 0 | 79 | 53 | 0 |
| experimental_composite_x | AUDUSD.r | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 59821 | 46503 | 13262 | 2073 | 385 | 2070 | 0 | 77 | 44 | 0 |
| experimental_composite_x | USDJPY | 2 | 50 | 0.94 | -1.02 | 0.92 | 0.97 | -0.03 | -0.01 | 0 | 0.96 | -0 | -2.69 | -1.35 | -0.039 | -0.039 | 0.06 | -0.03 | 101653 | 76025 | 25507 | 3777 | 748 | 3775 | 1004 | 124 | 76 | 3 |
| experimental_composite_x | USDCAD.r | 1 | 0 | 0 | -1.05 | 0 | 0 | -1.01 | 0 | 0 | 0 | 0 | -100.9 | -100.9 | -1.052 | -1.052 | 100 | inf | 59820 | 45998 | 13779 | 2075 | 332 | 2074 | 0 | 78 | 63 | 3 |
| experimental_composite_x | NZDUSD.r | 1 | 0 | 0 | -1.09 | 0 | 0 | -1.07 | 0 | 0 | 0 | 0 | -107.1 | -107.1 | -1.092 | -1.092 | 100 | inf | 59818 | 46501 | 13250 | 2050 | 427 | 2043 | 4 | 65 | 42 | 1 |
| experimental_composite_x | EURGBP.r | 1 | 0 | 0 | -1.15 | 0 | 0 | -1.12 | 0 | 0 | 0 | 0 | -111.6 | -111.6 | -1.149 | -1.149 | 100 | inf | 59821 | 46506 | 13278 | 1913 | 330 | 1912 | 0 | 80 | 38 | 2 |
| experimental_composite_x | EURJPY.r | 5 | 20 | 1.18 | -0.99 | 1.19 | 0.3 | -2.81 | -1.44 | -106.3 | 3.95 | -0.24 | -280.6 | -56.12 | -0.558 | -0.558 | 2.21 | -0.71 | 101653 | 76961 | 24603 | 3814 | 687 | 3811 | 1154 | 96 | 79 | 9 |
| faithful_operable_sma200_primary | USDCHF.r | 4 | 50 | 1.63 | -1.05 | 1.55 | 1.47 | 0.87 | 0.37 | 47.98 | 0.94 | 0.28 | 87.27 | 21.82 | 0.289 | 0.289 | 0.04 | 0.93 | 59817 | 46009 | 13758 | 2076 | 453 | 2071 | 0 | 79 | 248 | 5 |
| faithful_operable_sma200_primary | NZDUSD.r | 4 | 50 | 1.21 | -1.09 | 1.1 | 1.17 | 0.31 | 0.17 | 7.49 | 1.8 | 0.05 | 31.17 | 7.79 | 0.057 | 0.057 | 0.02 | 0.17 | 59818 | 46501 | 13250 | 2050 | 500 | 2042 | 4 | 65 | 237 | 7 |
| faithful_operable_sma200_primary | USDCAD.r | 3 | 33.3 | 1.03 | -1.06 | 0.97 | 0.48 | -0.97 | -0.64 | -18.44 | 0.9 | -0.57 | -96.58 | -32.19 | -0.366 | -0.366 | 0.09 | -1.07 | 59820 | 45998 | 13779 | 2075 | 415 | 2070 | 0 | 78 | 241 | 6 |
| faithful_operable_sma200_primary | USDJPY | 6 | 33.3 | 1.23 | -1.06 | 1.16 | 0.54 | -1.85 | -0.75 | -12.01 | 2.06 | -0.14 | -184.6 | -30.77 | -0.297 | -0.297 | 0.15 | -0.89 | 101653 | 76025 | 25507 | 3777 | 899 | 3773 | 995 | 124 | 418 | 7 |
| faithful_operable_sma200_primary | GBPUSD.r | 3 | 0 | 0 | -1.04 | 0 | 0 | -2.83 | -51.44 | -51.44 | 1.93 | -0.59 | -283.1 | -94.36 | -1.044 | -1.044 | 0.06 | -1.47 | 59818 | 46777 | 12982 | 1884 | 423 | 1882 | 9 | 76 | 295 | 3 |
| faithful_operable_sma200_primary | AUDUSD.r | 5 | 20 | 1.29 | -1.15 | 1.13 | 0.29 | -2.87 | -1.45 | -11.39 | 2.85 | -0.22 | -286.6 | -57.32 | -0.659 | -0.659 | 0.07 | -1.01 | 59821 | 46503 | 13262 | 2073 | 545 | 2070 | 0 | 77 | 247 | 9 |
| faithful_operable_sma200_primary | EURUSD.r | 8 | 25 | 1.23 | -1.11 | 1.1 | 0.38 | -3.68 | -1.42 | -14.59 | 3.71 | -0.17 | -367.7 | -45.96 | -0.526 | -0.526 | 0.04 | -0.99 | 101654 | 77720 | 23861 | 3490 | 734 | 3481 | 4 | 133 | 479 | 12 |
| faithful_operable_sma200_primary | EURGBP.r | 6 | 16.7 | 1.14 | -1.07 | 1.06 | 0.21 | -3.8 | -2.11 | -54.16 | 2.9 | -0.69 | -380.1 | -63.36 | -0.706 | -0.706 | 0.12 | -1.31 | 59821 | 46506 | 13278 | 1913 | 447 | 1911 | 0 | 80 | 261 | 9 |
| faithful_operable_sma200_primary | EURJPY.r | 6 | 16.7 | 1.2 | -1.05 | 1.14 | 0.22 | -3.91 | -2.03 | -34.52 | 3.08 | -0.23 | -390.8 | -65.13 | -0.673 | -0.673 | 0.05 | -1.27 | 101653 | 76961 | 24603 | 3814 | 945 | 3810 | 1136 | 96 | 426 | 6 |
| faithful_operable_trigger_or | AUDUSD.r | 2 | 50 | 1.3 | -1.07 | 1.21 | 1.25 | 0.24 | 0.17 | 0 | 0.96 | 0.07 | 24.45 | 12.22 | 0.113 | 0.113 | 0.07 | 0.26 | 59821 | 54511 | 5254 | 833 | 220 | 831 | 4 | 26 | 130 | 4 |
| faithful_operable_trigger_or | GBPUSD.r | 2 | 50 | 1.07 | -1.03 | 1.05 | 1.05 | 0.04 | 0.04 | 0 | 0.96 | 0.06 | 4.43 | 2.21 | 0.024 | 0.024 | 0.1 | 0.05 | 59818 | 50502 | 9264 | 1335 | 349 | 1333 | 6 | 58 | 210 | 2 |
| faithful_operable_trigger_or | EURGBP.r | 2 | 50 | 1.14 | -1.1 | 1.04 | 1.03 | 0.03 | 0.03 | 0 | 0 | 0 | 2.75 | 1.37 | 0.021 | 0.021 | 0.12 | inf | 59821 | 57062 | 2728 | 385 | 112 | 385 | 0 | 16 | 76 | 2 |
| faithful_operable_trigger_or | NZDUSD.r | 5 | 40 | 1.21 | -1.07 | 1.13 | 0.73 | -0.81 | -0.33 | -10.09 | 1.98 | -0.11 | -81.33 | -16.27 | -0.16 | -0.16 | 0.03 | -0.41 | 59818 | 55356 | 4397 | 731 | 187 | 731 | 0 | 32 | 110 | 7 |
| faithful_operable_trigger_or | USDCAD.r | 5 | 40 | 1.16 | -1.06 | 1.09 | 0.71 | -0.86 | -0.37 | -11.8 | 2.02 | -0.13 | -86.08 | -17.22 | -0.175 | -0.175 | 0.09 | -0.43 | 59820 | 52120 | 7638 | 1208 | 244 | 1206 | 0 | 47 | 187 | 9 |
| faithful_operable_trigger_or | USDCHF.r | 1 | 0 | 0 | -1.03 | 0 | 0 | -0.98 | 0 | 0 | 0 | 0 | -97.92 | -97.92 | -1.034 | -1.034 | 100 | inf | 59817 | 54388 | 5383 | 783 | 189 | 781 | 0 | 31 | 132 | 1 |
| faithful_operable_trigger_or | EURUSD.r | 11 | 27.3 | 2.49 | -1.06 | 2.36 | 0.87 | -1.04 | -0.15 | -6.13 | 4.02 | -0.05 | -103.8 | -9.43 | -0.089 | -0.089 | 0.45 | -0.26 | 101654 | 89403 | 12160 | 1762 | 414 | 1759 | 5 | 78 | 292 | 20 |
| faithful_operable_trigger_or | USDJPY | 12 | 33.3 | 1.56 | -1.07 | 1.46 | 0.72 | -2.31 | -0.52 | -14.78 | 2.78 | -0.13 | -230.7 | -19.23 | -0.193 | -0.193 | 0.3 | -0.83 | 101653 | 68848 | 32631 | 4865 | 1189 | 4858 | 1335 | 183 | 564 | 17 |
| faithful_operable_trigger_or | EURJPY.r | 9 | 22.2 | 1.08 | -1.05 | 1.03 | 0.29 | -4.96 | -1.95 | -59.24 | 3.97 | -0.17 | -496 | -55.11 | -0.575 | -0.575 | 0.06 | -1.25 | 101653 | 69120 | 32395 | 4959 | 1301 | 4953 | 1488 | 129 | 580 | 9 |

## Embudo de senales

| Activo | Velas | H4_BLOCKED | HTF_OK | SETUP_ROWS | RETRACE_OK | FAN_BREAKOUT | MACD_TRIGGER | STOCH_TRIGGER | RR_OK | ENTRY_READY | Variant | VariantClass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AUDUSD.r | 59821 | 46503 | 13262 | 2073 | 545 | 2070 | 0 | 77 | 247 | 9 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | 59821 | 46506 | 13278 | 1913 | 447 | 1911 | 0 | 80 | 261 | 9 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | 101653 | 76961 | 24603 | 3814 | 945 | 3810 | 1136 | 96 | 426 | 6 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | 101654 | 77720 | 23861 | 3490 | 734 | 3481 | 4 | 133 | 479 | 12 | faithful_operable_sma200_primary | resultado_valido |
| GBPUSD.r | 59818 | 46777 | 12982 | 1884 | 423 | 1882 | 9 | 76 | 295 | 3 | faithful_operable_sma200_primary | resultado_valido |
| NZDUSD.r | 59818 | 46501 | 13250 | 2050 | 500 | 2042 | 4 | 65 | 237 | 7 | faithful_operable_sma200_primary | resultado_valido |
| USDCAD.r | 59820 | 45998 | 13779 | 2075 | 415 | 2070 | 0 | 78 | 241 | 6 | faithful_operable_sma200_primary | resultado_valido |
| USDCHF.r | 59817 | 46009 | 13758 | 2076 | 453 | 2071 | 0 | 79 | 248 | 5 | faithful_operable_sma200_primary | resultado_valido |
| USDJPY | 101653 | 76025 | 25507 | 3777 | 899 | 3773 | 995 | 124 | 418 | 7 | faithful_operable_sma200_primary | resultado_valido |
| TOTAL | 663875 | 509000 | 154280 | 23152 | 5361 | 23110 | 2148 | 808 | 2852 | 64 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | 59821 | 54511 | 5254 | 833 | 220 | 831 | 4 | 26 | 130 | 4 | faithful_operable_trigger_or | resultado_valido |
| EURGBP.r | 59821 | 57062 | 2728 | 385 | 112 | 385 | 0 | 16 | 76 | 2 | faithful_operable_trigger_or | resultado_valido |
| EURJPY.r | 101653 | 69120 | 32395 | 4959 | 1301 | 4953 | 1488 | 129 | 580 | 9 | faithful_operable_trigger_or | resultado_valido |
| EURUSD.r | 101654 | 89403 | 12160 | 1762 | 414 | 1759 | 5 | 78 | 292 | 20 | faithful_operable_trigger_or | resultado_valido |
| GBPUSD.r | 59818 | 50502 | 9264 | 1335 | 349 | 1333 | 6 | 58 | 210 | 2 | faithful_operable_trigger_or | resultado_valido |
| NZDUSD.r | 59818 | 55356 | 4397 | 731 | 187 | 731 | 0 | 32 | 110 | 7 | faithful_operable_trigger_or | resultado_valido |
| USDCAD.r | 59820 | 52120 | 7638 | 1208 | 244 | 1206 | 0 | 47 | 187 | 9 | faithful_operable_trigger_or | resultado_valido |
| USDCHF.r | 59817 | 54388 | 5383 | 783 | 189 | 781 | 0 | 31 | 132 | 1 | faithful_operable_trigger_or | resultado_valido |
| USDJPY | 101653 | 68848 | 32631 | 4865 | 1189 | 4858 | 1335 | 183 | 564 | 17 | faithful_operable_trigger_or | resultado_valido |
| TOTAL | 663875 | 551310 | 111850 | 16861 | 4205 | 16837 | 2838 | 600 | 2281 | 71 | faithful_operable_trigger_or | resultado_valido |
| AUDUSD.r | 59821 | 46503 | 13262 | 2073 | 385 | 2070 | 0 | 77 | 44 | 0 | experimental_composite_x | resultado_exploratorio |
| EURGBP.r | 59821 | 46506 | 13278 | 1913 | 330 | 1912 | 0 | 80 | 38 | 2 | experimental_composite_x | resultado_exploratorio |
| EURJPY.r | 101653 | 76961 | 24603 | 3814 | 687 | 3811 | 1154 | 96 | 79 | 9 | experimental_composite_x | resultado_exploratorio |
| EURUSD.r | 101654 | 77720 | 23861 | 3490 | 626 | 3484 | 4 | 133 | 95 | 0 | experimental_composite_x | resultado_exploratorio |
| GBPUSD.r | 59818 | 46777 | 12982 | 1884 | 263 | 1882 | 9 | 76 | 39 | 0 | experimental_composite_x | resultado_exploratorio |
| NZDUSD.r | 59818 | 46501 | 13250 | 2050 | 427 | 2043 | 4 | 65 | 42 | 1 | experimental_composite_x | resultado_exploratorio |
| USDCAD.r | 59820 | 45998 | 13779 | 2075 | 332 | 2074 | 0 | 78 | 63 | 3 | experimental_composite_x | resultado_exploratorio |
| USDCHF.r | 59817 | 46009 | 13758 | 2076 | 319 | 2073 | 0 | 79 | 53 | 0 | experimental_composite_x | resultado_exploratorio |
| USDJPY | 101653 | 76025 | 25507 | 3777 | 748 | 3775 | 1004 | 124 | 76 | 3 | experimental_composite_x | resultado_exploratorio |
| TOTAL | 663875 | 509000 | 154280 | 23152 | 4117 | 23124 | 2175 | 808 | 529 | 18 | experimental_composite_x | resultado_exploratorio |

## Principales bloqueos

| Activo | BLOCK_REASON | Rows | Variant | VariantClass |
| --- | --- | --- | --- | --- |
| AUDUSD.r | H4_BULLISH_FAN_MISSING | 20879 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | H4_BEARISH_FAN_MISSING | 20818 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | H4_SMA200_BEAR_FILTER_MISSING | 2215 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | H4_SMA200_BULL_FILTER_MISSING | 1999 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | RETRACE_TOO_DEEP | 1105 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | H4_SMA200_UNAVAILABLE | 584 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | MOMENTUM_CONFIRM_MISSING | 526 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | RETRACE_BELOW_MIN | 423 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | RR_BELOW_MIN | 10 | faithful_operable_sma200_primary | resultado_valido |
| AUDUSD.r | H4_NO_ATTRACTOR | 8 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | H4_BEARISH_FAN_MISSING | 21513 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | H4_BULLISH_FAN_MISSING | 20225 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | H4_SMA200_BEAR_FILTER_MISSING | 2384 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | H4_SMA200_BULL_FILTER_MISSING | 2080 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | RETRACE_TOO_DEEP | 1120 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | MOMENTUM_CONFIRM_MISSING | 435 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | RETRACE_BELOW_MIN | 346 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | H4_SMA200_UNAVAILABLE | 296 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | H4_NO_ATTRACTOR | 8 | faithful_operable_sma200_primary | resultado_valido |
| EURGBP.r | RR_BELOW_MIN | 3 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | H4_BULLISH_FAN_MISSING | 35276 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | H4_BEARISH_FAN_MISSING | 33829 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | H4_SMA200_BEAR_FILTER_MISSING | 4408 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | H4_SMA200_BULL_FILTER_MISSING | 3448 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | RETRACE_TOO_DEEP | 2146 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | RETRACE_BELOW_MIN | 723 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | MOMENTUM_CONFIRM_MISSING | 694 | faithful_operable_sma200_primary | resultado_valido |
| EURJPY.r | RR_BELOW_MIN | 245 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_BEARISH_FAN_MISSING | 35837 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_BULLISH_FAN_MISSING | 33660 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_SMA200_BULL_FILTER_MISSING | 4471 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | H4_SMA200_BEAR_FILTER_MISSING | 3752 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | RETRACE_TOO_DEEP | 1752 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | RETRACE_BELOW_MIN | 1004 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | MOMENTUM_CONFIRM_MISSING | 705 | faithful_operable_sma200_primary | resultado_valido |
| EURUSD.r | RR_BELOW_MIN | 17 | faithful_operable_sma200_primary | resultado_valido |
| GBPUSD.r | H4_BULLISH_FAN_MISSING | 20795 | faithful_operable_sma200_primary | resultado_valido |
| GBPUSD.r | H4_BEARISH_FAN_MISSING | 20484 | faithful_operable_sma200_primary | resultado_valido |
| GBPUSD.r | H4_SMA200_BULL_FILTER_MISSING | 2636 | faithful_operable_sma200_primary | resultado_valido |
| GBPUSD.r | H4_SMA200_BEAR_FILTER_MISSING | 2392 | faithful_operable_sma200_primary | resultado_valido |

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
