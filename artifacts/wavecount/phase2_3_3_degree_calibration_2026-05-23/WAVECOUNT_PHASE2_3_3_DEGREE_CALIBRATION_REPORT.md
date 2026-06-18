# WaveCount Fase 2.3.3 - calibracion de grados

Fecha: 2026-05-23

## Objetivo

Auditar si `minor`, `intermediate` y `major` estan visualmente diferenciados antes de Fase 2.5. No se cambian umbrales ni artifacts canonicos.

## Configuracion actual

| grado | min ATR | min movimiento relativo | min barras |
|---|---:|---:|---:|
| `minor` | 2.0 | 0.002 | 4 |
| `intermediate` | 3.0 | 0.003 | 6 |
| `major` | 5.0 | 0.005 | 10 |

Los umbrales son globales, no dependen de activo ni timeframe.

## Resultado

- filas metricas grado/ejemplo: 84
- ejemplos con issues: 24
- distribucion de issues: {'degree_not_discriminative_intermediate_vs_minor': 8, 'degree_not_discriminative_major_vs_intermediate': 6, 'degree_too_micro': 6, 'degree_reasonable': 4, 'degree_not_discriminative_intermediate_vs_minor|degree_not_discriminative_major_vs_intermediate': 2, 'degree_too_coarse_major': 2}
- evidencias manuales incorporadas: 9
- tiempo de ejecucion: 12.18s

## Decision

- H1/M30: auxiliary_only; grado recomendado: intermediate_auxiliary.
- H4/D1: preferred_base_with_manual_review; grado recomendado: intermediate.
- Mantener umbrales actuales por ahora. Si se cambian, debe abrirse una fase experimental separada y regenerar Fase 1.6/downstream sin sobrescribir canonico.
- `minor` queda como detalle interno; `intermediate` como mejor base inicial; `major` como contexto superior.

## Cierre

H1/M30 debe quedar como auxiliar/case bank. H4/D1 debe ser la base principal candidata para Fase 2.5, con `intermediate` como grado primario y `major` como contexto.
