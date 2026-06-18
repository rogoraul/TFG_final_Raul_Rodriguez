# Auditoria Menendez 2026-05-14

Artifact acotado de la auditoria metodologica Menendez.

No es una salida canonica multi-simbolo. Resume la reproduccion sobre
`EURUSD.r` usada para verificar el embudo despues de corregir la X compuesta
para que no use 5 segmentos por defecto.

## Lectura

- `faithful_operable_trigger_or`: genera 11 trades, pero no demuestra edge.
- `faithful_operable_sma200_primary`: es la linea operable principal, pero en
  EURUSD queda con 8 trades, PF 0.37 y retorno negativo.
- `experimental_composite_x`: usa `X_SEGMENT_COUNT=3` tras la auditoria, no 5,
  pero no completa ninguna entrada en EURUSD.

Conclusion: Menendez queda como bloque secundario/metodologico defendible hasta
ejecutar una suite multi-simbolo canonica.
