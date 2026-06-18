# WaveCount Phase 2.2 - diagnostico de impulsos

Fecha: 2026-05-17

## Resumen

Se ha auditado por que Fase 2 no produce `candidate_impulse` limpio sobre `intermediate`.
La revision compara `minor`, `intermediate` y `major`, impulsos completos, near-misses y parciales 1-2-3.

No se generan senales, no se filtran estrategias, no se conecta MT5 y no se ejecutan backtests.

## Resultado global

- impulsos completos por estado: {'hard_invalid_impulse': 106, 'soft_impulse_near_miss': 32, 'strict_candidate_impulse': 5}
- parciales 1-2-3 por estado: {'partial_123_invalid': 114, 'partial_123_candidate': 49, 'partial_123_ambiguous': 4}
- tiempo de ejecucion: 53.86s

## Comparacion por grado

| grado | structural pivots | ventanas completas | impulsos estrictos | near-miss blandos | invalidos duros | parciales 1-2-3 | parciales ambiguos | parciales invalidos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `intermediate` | 60 | 40 | 0 | 11 | 29 | 13 | 2 | 33 |
| `major` | 43 | 23 | 0 | 4 | 19 | 7 | 1 | 23 |
| `minor` | 100 | 80 | 5 | 17 | 58 | 29 | 1 | 58 |

## Diagnostico

El cero de Fase 2 sobre `intermediate` no implica ausencia total: aparecen impulsos estrictos en `minor`, pero ese grado es mas microestructural y no debe sustituir automaticamente al grado base.

- impulsos estrictos por grado: {'intermediate': 0, 'major': 0, 'minor': 5}
- parciales 1-2-3 candidatos por grado: {'intermediate': 13, 'major': 7, 'minor': 29}

## Graficos generados

- `forex_clean_eurusd_h1_minor_impulse_011`: ok - charts\forex_clean_eurusd_h1_minor_impulse_011.png
- `index_gap_aus200_m30_minor_impulse_005`: ok - charts\index_gap_aus200_m30_minor_impulse_005.png
- `metals_ambiguous_xptusd_h1_minor_impulse_014`: ok - charts\metals_ambiguous_xptusd_h1_minor_impulse_014.png
- `forex_clean_eurusd_h1_intermediate_impulse_002`: ok - charts\forex_clean_eurusd_h1_intermediate_impulse_002.png
- `index_gap_aus200_m30_intermediate_impulse_002`: ok - charts\index_gap_aus200_m30_intermediate_impulse_002.png
- `metals_ambiguous_xptusd_h1_intermediate_impulse_001`: ok - charts\metals_ambiguous_xptusd_h1_intermediate_impulse_001.png
- `metals_noisy_xauusd_m30_intermediate_impulse_002`: ok - charts\metals_noisy_xauusd_m30_intermediate_impulse_002.png
- `forex_clean_eurusd_h1_major_impulse_002`: ok - charts\forex_clean_eurusd_h1_major_impulse_002.png
- `index_gap_aus200_m30_major_impulse_005`: ok - charts\index_gap_aus200_m30_major_impulse_005.png
- `forex_clean_eurusd_h1_intermediate_impulse_001`: ok - charts\forex_clean_eurusd_h1_intermediate_impulse_001.png
- `index_gap_aus200_m30_intermediate_impulse_001`: ok - charts\index_gap_aus200_m30_intermediate_impulse_001.png
- `metals_ambiguous_xptusd_h1_intermediate_impulse_002`: ok - charts\metals_ambiguous_xptusd_h1_intermediate_impulse_002.png
- `metals_noisy_xauusd_m30_intermediate_impulse_001`: ok - charts\metals_noisy_xauusd_m30_intermediate_impulse_001.png
- `forex_clean_eurusd_h1_major_impulse_001`: ok - charts\forex_clean_eurusd_h1_major_impulse_001.png
- `index_gap_aus200_m30_major_impulse_001`: ok - charts\index_gap_aus200_m30_major_impulse_001.png
- `forex_clean_eurusd_h1_intermediate_partial123_002`: ok - charts\forex_clean_eurusd_h1_intermediate_partial123_002.png
- `index_gap_aus200_m30_intermediate_partial123_002`: ok - charts\index_gap_aus200_m30_intermediate_partial123_002.png
- `metals_ambiguous_xptusd_h1_intermediate_partial123_001`: ok - charts\metals_ambiguous_xptusd_h1_intermediate_partial123_001.png
- `metals_noisy_xauusd_m30_intermediate_partial123_002`: ok - charts\metals_noisy_xauusd_m30_intermediate_partial123_002.png
- `forex_clean_eurusd_h1_major_partial123_002`: ok - charts\forex_clean_eurusd_h1_major_partial123_002.png
- `index_gap_aus200_m30_major_partial123_002`: ok - charts\index_gap_aus200_m30_major_partial123_002.png
- `index_gap_aus200_m30_intermediate_partial123_014`: ok - charts\index_gap_aus200_m30_intermediate_partial123_014.png
- `metals_noisy_xauusd_m30_intermediate_partial123_011`: ok - charts\metals_noisy_xauusd_m30_intermediate_partial123_011.png
- `index_gap_aus200_m30_major_partial123_010`: ok - charts\index_gap_aus200_m30_major_partial123_010.png

## Decision

Antes de Fase 3 conviene ampliar la revision visual y separar el buscador futuro de conteos estrictamente consecutivos. No se debe relajar la regla para fabricar impulsos.
