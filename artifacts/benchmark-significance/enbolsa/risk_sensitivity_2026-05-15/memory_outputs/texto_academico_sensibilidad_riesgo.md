# Texto academico - sensibilidad de riesgo ENBOLSA

## Lectura propuesta para la memoria

El bloque `enbolsa:macd_breakout / Forex Majors / H1:H4` presenta en el benchmark canonico un retorno del 1405.24%. La cifra se reconstruye desde el `trade_log` del propio bloque, por lo que no procede de una mezcla incorrecta de bloques independientes ni de una pseudo-cartera global.

La interpretacion metodologica requiere, sin embargo, separar dos efectos. En primer lugar, el escenario observado es compuesto: cada nueva operacion se dimensiona sobre el balance ya actualizado por las operaciones cerradas. En segundo lugar, el bloque no impone un limite operativo fuerte de exposicion agregada por divisa o correlacion.

Cuando se elimina el compounding y se recalcula el mismo conjunto de operaciones con riesgo fijo sobre el capital inicial, el retorno del bloque baja a 340.07%. La reduccion es grande, lo que confirma que el 1405% no debe presentarse como rentabilidad live esperable. Aun asi, el resultado sigue siendo positivo, con PF 1.22 y MaxDD 14.52%.

La comparacion con `compuesto cap 10%` ayuda a aislar el factor principal: con compounding y cap 10%, el bloque queda en 1409.33%, muy cerca del escenario observado. En cambio, con riesgo fijo y cap 10%, el resultado es 341.45%. Por tanto, la caida principal se explica por quitar reinversion del balance, no por el cap del 10%.

En el agregado de 9 bloques, `macd_breakout` tambien conserva una lectura favorable: con riesgo fijo sin cap mantiene MeanReturn% 84.32, MedianReturn% 43.20, bloques positivos 100.0% y MedianPF 1.12. Esto permite defender la estrategia como empiricamente superior a los benchmarks simples dentro del protocolo actual, aunque no permite defender la cifra extrema como expectativa realista.

## Definiciones breves

- `Sin cap`: no se bloquean nuevas operaciones por superar un limite de riesgo abierto agregado.
- `Riesgo fijo`: cada operacion se recalcula como si el capital base siguiera siendo el inicial.
- `Compuesto`: el tamano de nuevas operaciones crece o decrece con el balance liquidado.
- `Cap`: restriccion que impide aceptar nuevas operaciones si el riesgo abierto supera un umbral.

## Conclusion de uso

La salida correcta para la memoria es que `macd_breakout` sigue siendo defendible, pero la rentabilidad extrema debe explicarse como resultado de compounding y de un modelo multi-simbolo sin `RiskGuard` completo. El siguiente paso operativo no es optimizar caps sobre estos resultados, sino implementar una capa de `RiskGuard` con exposicion por divisa, correlacion y riesgo total abierto.
