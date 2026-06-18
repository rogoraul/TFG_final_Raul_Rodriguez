# WaveCount Phase 2.4.1 - visual audit context

Fecha: 2026-05-19

## Resumen

Se revisaron visualmente los 54 graficos vigentes referenciados por `candidate_context.csv` / `run_meta.json`.
No se cambiaron reglas de conteo, no se generaron senales y no se avanzo a Fase 2.5.

## Resultados

- casos revisados: 54
- distribucion visual: {'visually_defensible': 13, 'visually_forced': 12, 'plausible_but_needs_review': 11, 'ambiguous': 9, 'hard_invalid_correct': 8, 'likely_false_candidate': 1}
- calidad media por categoria: {'abc': 2.42, 'hard_invalid': 3.89, 'impulse': 3.92, 'near_miss': 2.89, 'partial_123': 4.17}
- evaluacion EWO: {'usable_soft_rule': 17, 'promising_but_needs_review': 15, 'too_noisy': 13, 'not_supported': 9}
- casos para revision obligatoria del usuario: 26

## Lectura metodologica

- Los impulsos y parciales 1-2-3 tienen varios ejemplos visualmente defendibles.
- El EWO 5-35 parece util para inferir onda 3, descarga de onda 4 y posibles quintas debiles o fallidas.
- Los ABC actuales son la parte mas debil: muchos graficos parecen impulsos o subondas etiquetadas como correcciones.
- Las invalidaciones duras son buenos ejemplos negativos: el contexto puede explicar, pero no rescatar, un conteo estructuralmente invalido.

## Decision

EMAs/HTF/EWO son aptos como reglas blandas para una futura Fase 2.5, pero no como reglas duras.
Antes de implementar busqueda guiada conviene revisar `user_must_review.csv`, especialmente los conflictos HTF y los ABC forzados.
