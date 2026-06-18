# WaveCount Phase 2 - conteo Elliott candidato

Fecha: 2026-05-17

## Resumen

Se ha generado un conteo candidato aislado `1-2-3-4-5 / A-B-C` sobre structural swings `intermediate`.
El grado `major` se usa solo como contexto superior. No se usan raw pivots directamente.

No se generan senales, no se filtran entradas, no se toca ninguna estrategia, no se conecta MT5 y no se ejecutan backtests.

## Resultado global

- estados: {'invalidated_count': 50, 'ambiguous_count': 24, 'candidate_abc': 14}
- patron/estado: {('abc', 'ambiguous_count'): 13, ('abc', 'candidate_abc'): 14, ('abc', 'invalidated_count'): 21, ('impulse', 'ambiguous_count'): 11, ('impulse', 'invalidated_count'): 29}
- violaciones `count_detected_at < max(structural_detected_at usadas)`: 0
- tiempo de ejecucion: 10.07s

## Graficos

- `forex_clean_eurusd_h1`: ok - charts\forex_clean_eurusd_h1_counts.png
- `metals_noisy_xauusd_m30`: ok - charts\metals_noisy_xauusd_m30_counts.png
- `index_gap_aus200_m30`: ok - charts\index_gap_aus200_m30_counts.png
- `metals_ambiguous_xptusd_h1`: ok - charts\metals_ambiguous_xptusd_h1_counts.png

## Lectura metodologica

- `candidate_impulse` significa que la ventana cumple las invalidaciones basicas de impulso.
- `candidate_abc` significa que la ventana cumple una lectura ABC basica.
- `invalidated_count` conserva la ventana y explica por que no debe aceptarse.
- `ambiguous_count` evita forzar numeracion en estructuras poco claras.

La salida es diagnostica. No debe interpretarse como senal ni como filtro operativo.

## Decision

La Fase 2 queda implementada de forma conservadora, pero la muestra visual no contiene impulsos 1-2-3-4-5 limpios; antes de dashboard o estadistica conviene revisar mas ventanas y confirmar si el grado `intermediate` es suficiente para impulsos completos.
