# WaveCount Phase 1.5 - structural pivots / major swings

Fecha: 2026-05-17

## Resumen

Se ha construido una capa aislada que comprime pivotes locales confirmados de Fase 1 en swings estructurales mayores.
No implementa conteo Elliott, no genera senales y no toca ENBOLSA, Menendez, RiskGuard ni Live Watcher.

## Configuracion

- `min_leg_atr_multiplier`: 3.0
- `min_leg_relative_move_pct`: 0.003
- `min_leg_bars`: 6

## Resultado global

- raw pivots confirmados: 152
- structural pivots: 60
- ratio de compresion: 0.395
- tiempo de ejecucion: 9.57s

## Lectura metodologica

Los structural pivots son la entrada futura para conteo candidato. Los raw pivots siguen siendo la capa causal base.
Cualquier conteo futuro debe usar `structural_detected_at`, nunca anticipar el extremo visual.

## Decision

Fase 1.5 queda apta como base inicial para Fase 2, con revision visual previa de los graficos comparativos.
