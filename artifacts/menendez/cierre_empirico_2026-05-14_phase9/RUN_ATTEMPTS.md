# Intentos de ejecucion Menendez - cierre empirico 2026-05-14

## Objetivo

Cerrar empiricamente la linea Menendez con una suite multi-simbolo controlada
sin optimizar reglas ni cambiar logica de estrategia. Las variantes ejecutadas
son:

- `faithful_operable_sma200_primary`
- `faithful_operable_trigger_or`
- `experimental_composite_x`

## Intento completo

Comando:

```powershell
python -m backtests.menendez.run_empirical_close --output-dir artifacts/menendez/cierre_empirico_2026-05-14 --max-workers 4
```

Resultado:

- iniciado el 2026-05-14 con PID `21736`;
- detenido manualmente tras mas de 20 minutos sin que se escribieran tablas
  finales;
- no se borraron archivos del intento;
- quedaron `run_stdout.log`, `run_stderr.log` y la carpeta `tables/` sin
  resultados finales en `artifacts/menendez/cierre_empirico_2026-05-14/`;
- `run_stderr.log` solo mostraba el warning conocido de pandas/SQLAlchemy.

Lectura:

- la ejecucion completa de todos los simbolos disponibles puede requerir una
  ventana larga;
- para cerrar el objetivo en una fase controlada se ejecuto un bloque acotado
  de 9 simbolos de `Forex Majors`;
- el comando completo sigue siendo reproducible con el runner creado.

## Fase cerrada

Comando:

```powershell
python -m backtests.menendez.run_empirical_close --output-dir artifacts\menendez\cierre_empirico_2026-05-14_phase9 --variants faithful_operable_sma200_primary,faithful_operable_trigger_or,experimental_composite_x --group "Forex Majors" --timeframe-ltf M30 --timeframe-htf H4 --limit-symbols 9 --max-workers 4
```

Resultado:

- completado el 2026-05-14 a las `20:06:14`;
- 9 simbolos cargados de 9 solicitados:
  `AUDUSD.r`, `EURGBP.r`, `EURJPY.r`, `EURUSD.r`, `GBPUSD.r`, `NZDUSD.r`,
  `USDCAD.r`, `USDCHF.r`, `USDJPY`;
- artefactos finales generados en
  `artifacts/menendez/cierre_empirico_2026-05-14_phase9/`;
- no se optimizaron reglas ni parametros durante esta ejecucion.

## Decision reproducible

La fase cerrada permite clasificar Menendez como **bloque metodologico sin edge
demostrado**. No hay evidencia suficiente para presentarlo como eje empirico ni
como bloque empirico secundario positivo. La linea queda formalizada y auditada,
pero empiricamente por debajo de ENBOLSA.
