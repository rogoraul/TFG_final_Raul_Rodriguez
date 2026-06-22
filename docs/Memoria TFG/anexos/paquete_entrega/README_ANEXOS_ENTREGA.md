# Paquete de anexos de entrega

Fecha de preparacion: 2026-06-15.

Esta carpeta acompana a `memoria_tfg.pdf`. Incluye capturas, tablas, informes y
CSV ligeros usados para documentar los resultados sin tener que revisar todo el
directorio `artifacts/`, donde hay mas salidas intermedias.

Repositorio del proyecto:

https://github.com/rogoraul/TFG_final_Raul_Rodriguez

## Como leer este paquete

La memoria principal es el documento de referencia. Este paquete sirve para
consultar el material de apoyo: figuras, tablas, CSV resumidos y ejemplos de
salida del sistema. Las tablas de backtesting se leen por bloques
independientes, no como una cartera unica. Las piezas de Telegram, MT5 y AI
Analyst se incluyen para documentar el alcance demo/informativo del sistema,
no como prueba de operativa real.

`MANIFEST_ARCHIVOS.csv` lista los archivos incluidos y su tamano. Las copias de
Telegram estan revisadas para no incluir tokens ni identificadores sensibles.

## Estructura

### `01_informe_ai_analyst/`

Contiene un informe PDF generado por la capa AI Analyst y su README de contexto.
El informe ilustra el tipo de salida que puede producir el asistente a partir de
un paquete de revision, pero no aprueba operaciones ni sustituye al usuario.

### `02_figuras/`

Contiene figuras y capturas organizadas por bloque:

- `introduccion_metodologia/`: flujo general, esquema Elliott, formalizacion de
  setups, capas Menendez y arquitectura de archivos y refresco.
- `benchmarks_menendez/`: graficos de benchmark W2 final y linea Menendez.
- `wavecount/`: composiciones y ejemplos de conteos WaveCount/WeaveCount.
- `plataforma/`: capturas del Trading Center Dashboard, Screener, MT5 Bot y AI
  Analyst.
- `telegram/`: capturas de mensajes informativos recibidos en Telegram.

### `03_tablas_latex/`

Contiene fragmentos LaTeX de tablas usadas o preparadas para la memoria.
Incluye tambien `README_TABLAS.md`, con la fuente de cada tabla.

### `04_fuentes_csv/`

Contiene CSV agregados y ligeros que respaldan las tablas y figuras principales:

- `benchmark_w2/`: tablas agregadas del benchmark W2 final. No se incluye
  `trade_log.csv` por tamano y porque no es necesario para la lectura final.
- `menendez/`: resumen y conteos por variante de la linea Menendez.
- `wavecount/`: resumen de calidad de contexto y casos de auditoria
  seleccionados.
- `ai_analyst/`: auditorias de seguridad, limites y capacidades del AI Analyst.

### `05_artifacts_tecnicos_demo/`

Contiene archivos pequenos relacionados con el cierre tecnico demo:

- `riskguard/`: auditorias de sizing, exposicion, decisiones y gates RiskGuard.
- `telegram/informational_fixture/`: mensajes renderizados y auditorias del
  canal informativo en fixture/dry-run.
- `telegram/real_sender_audit/`: auditorias sanitizadas del envio real
  controlado usado para documentar la recepcion.

## Archivos no incluidos

No se incluye el directorio completo `artifacts/` ni logs de operaciones grandes.
La idea es mantener el paquete manejable y conservar solo el material necesario
para revisar la memoria.
