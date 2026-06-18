# WaveCount Fase 2.4.3 - auditoria ABC corregido

Fecha: 2026-05-23

## Alcance

Se revisa solo la linea ABC corregida en `phase2_abc_fix_2026-05-20`.
No se usan ABC legacy de galerias integradas antiguas como evidencia principal.
No se cambian conteos, pivotes, grados, estrategias, senales ni backtests.

## Resultado tecnico

- La geometria corregida queda limpia: los ABC revisados se dibujan como `0 -> A -> B -> C`.
- No quedan etiquetas duplicadas ni varias estructuras ABC superpuestas en los graficos revisados.
- La causalidad se mantiene con latencia de confirmacion: el extremo visual puede quedar atras, pero la lectura depende de pivotes estructurales confirmados.

## Resultado metodologico

- Casos revisados sin contexto/Fase 2.3 incluyendo focus: 29.
- Casos revisados con contexto H4/D1/Fase 2.4: 12.
- Casos `clean_abc`: 7.
- Casos `not_clean_abc` o `visually_forced_abc`: 13.
- Casos aptos solo como contexto blando: 8.
- Casos excluidos de Fase 2.5: 8.
- Casos que quedan experimentales: 13.

## Decision

ABC corregido puede entrar en Fase 2.5 solo como contexto blando/manual y banco experimental.
No debe convertirse en filtro duro, senal, ni criterio automatico de calidad.
Antes de usarlo como modulo fuerte haria falta implementar estados causales especificos: `possible_abc_start`, `abc_in_progress`, `abc_completed`, `ambiguous_correction`, `not_clean_abc` y `retrospective_only`.

## Papel de D1/EMAs/EWO

D1/EMAs/EWO ayudan en algunos casos a explicar correccion contra regimen o transicion.
Pero tambien pueden hacer tentador rescatar estructuras que visualmente parecen impulsivas.
Por eso quedan como lectura contextual y no como validacion de ABC.

## Validacion

- Tiempo de ejecucion: 4.32s.
- Las tablas tienen indices Markdown con imagenes para revision rapida.
- Vease `tables/abc_phase25_policy.csv` para la politica de uso.
