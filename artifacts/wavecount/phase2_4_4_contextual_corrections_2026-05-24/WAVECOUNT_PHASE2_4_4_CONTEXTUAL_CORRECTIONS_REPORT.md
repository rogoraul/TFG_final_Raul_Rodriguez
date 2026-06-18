# WaveCount Fase 2.4.4 - correcciones contextuales

Fecha: 2026-05-24

## Alcance

Se auditan los ABC corregidos como correcciones contextuales.
No se cambian conteos, pivotes, grados, estrategias, senales ni backtests.

## Resultado

- ABC revisados: 29.
- Correcciones contextuales usables como contexto blando: 4.
- Solo revision manual contextual: 8.
- Experimentales por padre desconocido: 5.
- Excluidos por no comportarse como correccion: 12.

## Decision metodologica

ABC ya no se evalua aislado. Un `0-A-B-C` limpio solo puede mejorar su estado si existe padre razonable o contexto HTF que explique que corrige.
La alternancia se registra como nota blanda y queda `unknown` o `not_applicable` cuando no hay una pareja onda 2/onda 4 comparable.
Esta fase no implementa una taxonomia completa de zigzags, flats, triangulos o combinaciones.

## Lectura para Fase 2.5

Fase 2.5 puede consumir solo los casos `usable_contextual_correction` como contexto blando.
Los casos `manual_contextual_review_only` y `experimental_unknown_parent` no deben automatizarse.
Los casos `exclude_not_correction` no deben alimentar reglas.

## Validacion

- Tiempo de ejecucion: 4.00s.
- Las tablas tienen indices Markdown para abrir imagenes rapidamente.
