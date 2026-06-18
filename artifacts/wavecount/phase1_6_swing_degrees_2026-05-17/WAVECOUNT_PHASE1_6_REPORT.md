# WaveCount Phase 1.6 - grados de swing

Fecha: 2026-05-17

## Resumen

Se ha generado una comparacion multi-escala de structural pivots: minor, intermediate y major.
No hay conteo Elliott, no hay senales, no hay filtros operativos y no se toca ninguna estrategia.

## Grados

- minor: 2 ATR / 0.2% / 4 barras
- intermediate: 3 ATR / 0.3% / 6 barras
- major: 5 ATR / 0.5% / 10 barras

## Resultado global

- pivotes por grado: {'intermediate': 60, 'major': 43, 'minor': 100}
- monotonia minor >= intermediate >= major por ejemplo: True
- ventanas con major demasiado escaso (<8 pivotes): []
- tiempo de ejecucion: 10.32s

## Decision

Grado recomendado para iniciar Fase 2: `intermediate`.

Motivo: `minor` sigue siendo util para microestructura, `major` es mas limpio pero queda escaso en algunas ventanas, e `intermediate` mantiene una lectura visual suficiente sin estar tan denso como los raw pivots.

Fase 2 puede avanzar solo como conteo candidato aislado sobre `intermediate`, comparando contra `major` como contexto superior y sin generar senales.
