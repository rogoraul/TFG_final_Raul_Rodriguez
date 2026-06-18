# WaveCount Phase 2.1 - revision de invalidaciones

Fecha: 2026-05-17

## Resumen

Se ha auditado la Fase 2 para separar invalidaciones duras de reglas blandas/ambiguas.
La revision no genera senales, no modifica estrategias y no conecta MT5.

## Resultado

- estados originales revisados: {'invalidated_count': 50, 'ambiguous_count': 24}
- severidades: {'hard_invalid': 50, 'soft_invalid_or_ambiguous': 24}
- estados recomendados: {'invalidated_count': 50, 'ambiguous_count': 24}
- posibles falsos negativos que siguen como `invalidated_count`: 0
- casos blandos ya reclasificados como `ambiguous_count`: 24
- cambios de estado recomendados: 0
- tiempo de ejecucion: 36.84s

## Lectura

- Las reglas duras siguen invalidando.
- El solape onda 4 / onda 1 se trata como ambiguedad si aparece solo, no como invalidacion dura.
- Las estructuras con B rompiendo origen siguen invalidadas para el ABC basico tipo zigzag; pueden ser extension futura de flats/expanded flats, no Fase 2.

## Graficos generados

- `forex_clean_eurusd_h1_impulse_001`: ok - charts\forex_clean_eurusd_h1_impulse_001.png
- `index_gap_aus200_m30_impulse_001`: ok - charts\index_gap_aus200_m30_impulse_001.png
- `metals_ambiguous_xptusd_h1_impulse_002`: ok - charts\metals_ambiguous_xptusd_h1_impulse_002.png
- `metals_noisy_xauusd_m30_impulse_001`: ok - charts\metals_noisy_xauusd_m30_impulse_001.png
- `forex_clean_eurusd_h1_abc_003`: ok - charts\forex_clean_eurusd_h1_abc_003.png
- `index_gap_aus200_m30_abc_003`: ok - charts\index_gap_aus200_m30_abc_003.png
- `metals_ambiguous_xptusd_h1_abc_002`: ok - charts\metals_ambiguous_xptusd_h1_abc_002.png
- `metals_noisy_xauusd_m30_abc_003`: ok - charts\metals_noisy_xauusd_m30_abc_003.png
- `forex_clean_eurusd_h1_impulse_002`: ok - charts\forex_clean_eurusd_h1_impulse_002.png
- `index_gap_aus200_m30_impulse_002`: ok - charts\index_gap_aus200_m30_impulse_002.png
- `metals_ambiguous_xptusd_h1_impulse_001`: ok - charts\metals_ambiguous_xptusd_h1_impulse_001.png
- `metals_noisy_xauusd_m30_impulse_002`: ok - charts\metals_noisy_xauusd_m30_impulse_002.png
- `forex_clean_eurusd_h1_abc_001`: ok - charts\forex_clean_eurusd_h1_abc_001.png
- `index_gap_aus200_m30_abc_001`: ok - charts\index_gap_aus200_m30_abc_001.png
- `metals_ambiguous_xptusd_h1_abc_007`: ok - charts\metals_ambiguous_xptusd_h1_abc_007.png
- `metals_noisy_xauusd_m30_abc_001`: ok - charts\metals_noisy_xauusd_m30_abc_001.png

## Decision

Las 59 invalidaciones iniciales no eran todas equivalentes: la mayoria eran reglas duras, pero varias invalidaciones por solape de onda 4 eran falsos negativos metodologicos y deben quedar como `ambiguous_count`.

Fase 2 queda mejor calibrada, aunque sigue necesitando revision visual ampliada antes de Fase 3.
