# WaveCount Fase 2.3.4 - cierre visual H4/D1

Fecha: 2026-05-23

## Objetivo

Cerrar la revision visual H4/D1 de Fase 2.3 antes de revisar Fase 2.4 con contexto.
No se cambian reglas, umbrales, pivotes, estrategias, ABC base ni senales.

## Diagnostico

- casos H4/D1 revisados: 54
- categorias: {'impulse': 12, 'partial_123': 12, 'abc': 12, 'near_miss': 9, 'hard_invalid': 9}
- estados visuales finales: {'not_usable_for_methodology': 11, 'hard_invalid_correct': 9, 'ambiguous': 9, 'visually_defensible': 6, 'plausible_but_needs_review': 6, 'too_micro': 4, 'excellent_example': 4, 'should_downgrade': 3, 'visually_forced': 2}
- decisiones finales: {'exclude_from_phase25_rules': 27, 'keep_as_ambiguous_example': 10, 'keep_as_negative_example': 9, 'keep_as_good_example': 8}
- feedback manual mapeado desde best_h4_examples: 12
- tiempo de ejecucion: 21.89s

## Decisiones

- H4/D1 queda como escala visual preferente frente a H1/M30.
- `intermediate` queda como grado primario para conteo H4.
- `major` queda como contexto superior, aunque algunos casos major pueden ser operables como grado superior.
- `minor` queda como subestructura, no como base principal.
- Los hard invalid se conservan como ejemplos negativos correctos.
- ABC no se usa para cerrar Fase 2.3; queda experimental y separado en `phase2_abc_fix_2026-05-20/`.
- Los parciales invalidados tras el 3 o demasiado debiles se excluyen de reglas para Fase 2.5.

## Cierre

Fase 2.3 H4/D1 queda defendible como base visual para pasar a Fase 2.4. La siguiente revision debe usar D1/EMAs/EWO solo como contexto, sin rescatar conteos que esta fase haya degradado.
