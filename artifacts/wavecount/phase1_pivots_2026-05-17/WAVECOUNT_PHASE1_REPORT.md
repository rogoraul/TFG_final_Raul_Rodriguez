# WaveCount Phase 1 - pivotes causales y galeria visual

Fecha: 2026-05-17

## Resumen

Se ha generado una galeria offline de pivotes WaveCount Fase 1 usando datos SQL existentes.
La salida no genera senales, no filtra entradas y no modifica ENBOLSA, Menendez, RiskGuard ni Live Watcher.

## Configuracion

- `left_bars`: 3
- `confirmation_bars`: 3
- `atr_period`: 14
- `min_atr_multiplier`: 0.75
- `min_relative_move_pct`: 0.001
- `min_bars_between_pivots`: 2

## Resultados

- ejemplos procesados correctamente: 4
- eventos confirmados: 152
- eventos ambiguos/ruido: 19
- violaciones `pivot_detected_at < pivot_extreme_time`: 0
- tiempo de ejecucion: 13.56s

## Archivos generados

- `tables/pivots_examples.csv`
- `tables/example_windows.csv`
- `charts/*.png`
- `run_meta.json`

## Lectura anti look-ahead

Un pivote confirmado marca dos tiempos distintos:

- `pivot_extreme_time`: vela donde estuvo el maximo/minimo visual.
- `pivot_detected_at`: vela en la que el algoritmo pudo confirmarlo tras la latencia.

Para cualquier uso futuro en tiempo real debe respetarse `pivot_detected_at`. Usar el extremo como si se conociera antes seria leakage.

## Limitaciones

- Esta fase solo detecta pivotes y ruido/ambiguedad local.
- No implementa conteo 1-2-3-4-5 ni A-B-C.
- No decide si un contexto es operable.
- Los ejemplos son diagnosticos visuales, no una validacion estadistica.
- Los datos SQL usados pueden estar desactualizados para live; aqui no se actualiza MT5.

## Siguiente paso

Implementar conteo candidato completo 1-2-3-4-5 / A-B-C en modulo aislado, usando estos pivotes con estados candidatos y confirmados, todavia sin senales operativas.
