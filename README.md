# TFG final - Raul Rodriguez

Repositorio del Trabajo de Fin de Grado **Automatizacion de la teoria de las
Ondas de Elliott para trading**.

El proyecto aplica tecnicas de ciencia de datos al estudio de estrategias de
trading. Reune codigo de ingesta, backtesting, analisis estructural y
visualizacion en un flujo reproducible. El resultado principal es el Trading
Center Dashboard, una herramienta local para revisar datos, candidatos de
estudio, resultados y material de apoyo del proyecto.

## Alcance

El repositorio contiene:

- codigo Python para ingesta, backtesting, screener, dashboard y auditorias;
- artifacts seleccionados usados por la plataforma y la memoria;
- dashboard Trading Center en modo de revision;
- nucleo SQL de apoyo para snapshots, vistas y controles de seguridad;
- RiskGuard, MT5 y Telegram dentro del alcance demo e informativo documentado;
- memoria final en PDF, fuentes LaTeX, figuras y anexos de entrega.

El alcance esta acotado:

- no habilita live trading;
- no ejecuta ordenes reales desde el dashboard;
- Telegram es informativo, no consola ni confirmador de ordenes;
- AI Analyst se usa como apoyo de revision, no como decisor operativo;
- MT5 queda limitado a lectura, shadow y ciclo demo controlado.

## Estructura del repositorio

```text
backtests/              Motores, helpers y estrategias de backtesting.
data/                   Acceso a datos, SQL/MT5 y utilidades de carga.
trading_center/         Dashboard, screener, refresh, RiskGuard, MT5 y Telegram.
zigzag/                 Implementacion local usada para pivotes y estructura.
artifacts/              Salidas seleccionadas para ejecucion y revision.
docs/                   Memoria final, fuentes LaTeX, figuras y anexos.
docs/Memoria TFG/       Memoria, fuentes LaTeX, figuras y anexos.
tests/                  Tests unitarios y de integracion ligera.
sql/                    Esquemas SQL de apoyo para snapshots y vistas.
```

## Artifacts incluidos

La carpeta `artifacts/` incluida en este repositorio no es el historial completo
de ejecuciones del TFG. Se ha dejado una seleccion reducida, de unas 850 piezas
y unos 234 MB, con:

- datos necesarios para abrir el dashboard con el estado publicado;
- salidas principales de benchmarks, Menendez, Screener y WeaveCount;
- material tecnico de MT5 demo, RiskGuard y Telegram informativo;
- fuentes de apoyo necesarias para interpretar la memoria y los anexos.

Se han dejado fuera ejecuciones exploratorias, carpetas superadas y material de
trabajo que no ayuda a revisar la version final.

Los anexos incluyen una seleccion adicional reducida en
`docs/Memoria TFG/anexos/paquete_entrega/`, pensada para acompanar la lectura
del PDF sin depender del historial completo de ejecuciones.

## Memoria y anexos

La memoria final compilada esta en:

```text
docs/Memoria TFG/memoria_tfg.pdf
```

Los anexos de entrega estan en:

```text
docs/Memoria TFG/anexos/paquete_entrega/
```

El archivo `MANIFEST_ARCHIVOS.csv` dentro de esa carpeta resume los archivos
incluidos.

## Instalacion local

Se recomienda usar Python 3.12 en Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para comprobar que el entorno importa los modulos principales:

```powershell
python -m py_compile trading_center\dash_readonly_app.py
```

## Ejecutar el dashboard

El punto de entrada publico del Trading Center es:

```powershell
python -m trading_center.dash_readonly_app --port 8050
```

Despues, abrir:

```text
http://127.0.0.1:8050
```

Tambien se puede ejecutar una validacion sin abrir servidor:

```powershell
python -m trading_center.dash_readonly_app --audit-only --output-dir .tmp\dashboard_audit_local
```

El dashboard consume artifacts locales ya generados. Si falta una fuente, el
comportamiento esperado es degradar de forma auditada o bloquear la ruta
correspondiente, no inventar datos.

Nota de rendimiento: el dashboard se entrega como herramienta local de revision
y visualizacion de resultados del TFG. No esta optimizado como producto web para
tiempos de carga minimos ni para uso multiusuario; algunas vistas pueden tardar
al cargar porque leen artifacts, tablas y figuras locales.

## Pruebas

Prueba focal del dashboard:

```powershell
python -m pytest tests\test_trading_center_dash_readonly_app.py -q
```

Pruebas focales del nucleo SQL:

```powershell
python -m pytest tests\test_sql_operational_core.py -q
```

Suite completa:

```powershell
python -m pytest tests -q
```

La suite completa puede tardar mas y depende del entorno local, por lo que para
una comprobacion rapida se recomienda empezar por los tests focales del
dashboard y los modulos que se vayan a revisar.

## Variables de entorno

El archivo `.env` real no se publica. Se incluye `.env.example` como referencia.

Los componentes que puedan usar SQL, MT5, Telegram o llamadas externas requieren
configuracion local explicita. En una instalacion nueva no envian mensajes, no
operan ni se conectan a servicios externos sin activar esas piezas de forma
manual.

## Componentes principales

- `trading_center/dash_readonly_app.py`: fachada publica del dashboard.
- `trading_center/dashboard/`: modulos internos del dashboard.
- `trading_center/screener_unified.py`: construccion del screener.
- `trading_center/riskguard_demo_intent_builder.py`: validacion de riesgo demo.
- `trading_center/mt5_read_only.py`: lectura de MT5 sin ejecucion operativa.
- `trading_center/mt5_shadow.py`: decisiones shadow sin envio de ordenes.
- `trading_center/mt5_demo_order_sender.py`: envio demo condicionado por gates.
- `trading_center/mt5_demo_position_manager.py`: gestion demo controlada.
- `trading_center/telegram_mt5_bot_informational.py`: mensajes informativos.
- `trading_center/telegram_sender_gate.py`: control previo de envio.
- `trading_center/codex_ai_analyst_package_renderer.py`: paquetes de revision.
- `sql/ops/`: DDL del nucleo SQL usado para snapshots y vistas.
- `tests/fixtures/`: fixtures pequenos para validar piezas de WaveCount.

## Notas de seguridad

Este repositorio no esta pensado como sistema de produccion para operar
mercados. La memoria explica el alcance, los supuestos de backtesting y las
limitaciones de la parte demo. Cualquier uso operativo real exigiria validacion
adicional, control de costes, supervision continua y una gestion de riesgo mas
amplia.
