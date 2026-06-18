# WaveCount Phase 2.4 - contexto tecnico HTF/LTF

Fecha: 2026-05-18

## Resumen

Se ha anadido contexto diagnostico con EMAs 50/150, alineacion HTF/LTF y EWO 5-35 a los candidatos visuales de Fase 2.3.
No se han cambiado reglas de conteo, no se generan senales y no se toca ninguna estrategia.

## Decisiones de implementacion

- WaveCount 2.4 usa EMAs 50/150 como capa visual propia, aunque ENBOLSA historico usa WMA 50/150 para tendencia estructural.
- El EWO 5-35 se implementa como SMA del precio medio `(high + low) / 2`, coherente con `backtests/enbolsa/GenerarIndicadores.py`.
- La alineacion HTF usa la ultima vela HTF cerrada mediante desplazamiento de una vela antes del merge temporal, siguiendo el criterio anti look-ahead ya documentado en ENBOLSA.
- Los graficos usan eje X comprimido por velas: no hay huecos visuales por fines de semana/cierres, aunque los timestamps reales se conservan en tablas.
- `context_score` es calidad/contexto diagnostico, no probabilidad de ganar ni senal operativa.

## Cobertura

- candidatos enriquecidos: 54
- distribucion de contexto: {'impulse_with_htf': 30, 'correction_against_htf': 16, 'conflict_with_htf': 8}
- tiempo de ejecucion: 181.01s
- incidencias HTF: Sin incidencias HTF.

## Lectura

- Si muchos impulsos buenos quedan como `impulse_with_htf`, las EMAs/EWO ayudan a explicar estructura.
- Si aparecen como `correction_against_htf`, pueden ser retrocesos o subondas contra regimen superior.
- Si dominan `unclear_context` o `conflict_with_htf`, conviene revisar visualmente antes de usar contexto para busqueda guiada.

## Decision

Fase 2.4 queda como capa diagnostica. No debe guiar busqueda de ondas hasta revisar la galeria enriquecida.
