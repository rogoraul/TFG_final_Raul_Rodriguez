# Backtests

Esta carpeta contiene el codigo usado para las pruebas historicas del TFG. Los
resultados que se comentan en la memoria ya estan guardados en `artifacts/` y en
los anexos, por lo que importar estos modulos no recalcula automaticamente los
experimentos.

## Estructura

- `common/`: configuracion, sizing, metricas y utilidades comunes.
- `enbolsa/`: nombre de paquete conservado por compatibilidad con el desarrollo
  original. En la memoria las estrategias se nombran como `macd_breakout`,
  `fib_limit` y otras etiquetas descriptivas.
- `benchmarks/`: comparacion frente a estrategias de referencia y generacion de
  tablas/figuras agregadas.
- `menendez/`: linea Elliott/Menendez y variantes metodologicas.
- `wavecount/`: conteos, auditorias visuales y analisis estructural.
- `tfg/`: scripts usados para preparar revisiones tecnicas y material de cierre.
- `PruebasComportamiento/`: notebooks ligeros sin outputs guardados, mantenidos
  como material auxiliar de comportamiento.

## Notas de uso

- No ejecutar backtests pesados salvo que se quiera regenerar resultados.
- No interpretar salidas historicas como promesa de rentabilidad futura.
- Los scripts de datos externos requieren configuracion local explicita.
