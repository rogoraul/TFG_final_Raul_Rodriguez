# WaveCount Phase 2.3 - revision visual ampliada

Fecha: 2026-05-17

## Resumen

Se ha generado una galeria visual ampliada para revision humana de WaveCount.
No se han cambiado reglas de conteo, no se generan senales y no se toca ninguna estrategia.

## Cobertura

- ventanas SQL procesadas correctamente: 15
- ventanas SQL omitidas/con error: 1
- candidatos visuales seleccionados: 54
- candidatos por categoria: {'impulse': 12, 'partial_123': 12, 'abc': 12, 'near_miss': 9, 'hard_invalid': 9}
- candidatos por grado: {'minor': 18, 'intermediate': 18, 'major': 18}
- candidatos por grupo: {'Forex Majors': 22, 'Index': 17, 'Metals': 15}
- tiempo de ejecucion: 172.48s

## Lectura

- `minor` aporta impulsos estrictos, pero debe revisarse si son demasiado micro.
- `intermediate` aporta parciales y near-misses utiles para decidir si hace falta busqueda no consecutiva.
- `major` queda como contexto, normalmente mas grueso.
- La plantilla manual permite clasificar cada imagen antes de tocar mas logica.

## Decision

Hay suficientes ejemplos para una primera revision humana. Antes de Fase 3 conviene revisar `manual_review_template.csv` y marcar los casos visualmente defendibles.
