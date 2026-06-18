# WaveCount Phase 2.5.4 Soft Quality Policy

Generated at: 2026-05-24T17:46:01

## Scope

Formaliza reglas blandas de calidad estructural usando artifacts vigentes bajo `05_guided_profile/`.
No recalcula pivotes, no recalcula conteos, no genera senales y no ejecuta backtests.

## Decisions

- H4/D1 `intermediate` sigue como base principal.
- H1/H4 queda como auxiliar / zoom de subestructura.
- M30/H1 se mantiene como microestructura, no base principal.
- Prominencia/tamano pasa a penalizacion blanda, no invalidacion automatica.
- EWO 5-35 se usa como apoyo relativo de momentum/rol de onda, no como etiqueta autonoma.
- EMAs 50/150 y HTF se usan como contexto blando de regimen/transicion/ambiguedad.
- ABC aislado no entra como regla fuerte; solo correccion contextual con padre razonable.

## Summary

- Candidate rows scored: 108
- High quality structures: 1
- Usable provisional structures: 5
- Auxiliary substructures: 7
- Excluded from guided search: 90

## AUS200 H4

`impulse_exp252_index_aus200_h4_intermediate_impulse_020` queda como `exclude_from_guided_search` con `low_prominence_vs_window` y score 24. Se trata como ejemplo de baja prominencia/contexto conflictivo, no como seed fuerte.

## Next

Fase 2.5.5 puede ampliar de forma descriptiva H4/D1 aplicando esta politica blanda,
con galeria selectiva de altos scores, near-misses y falsos positivos. No debe pasar aun a senales.
