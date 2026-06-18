# TFG final - Raul Rodriguez

Repositorio final del Trabajo de Fin de Grado **Automatizacion de la teoria de
las Ondas de Elliott para trading**.

El proyecto desarrolla un sistema de ciencia de datos aplicado al estudio de
estrategias de trading. El objetivo no es publicar un bot de trading en real,
sino dejar un flujo reproducible para ingerir datos, formalizar reglas, ejecutar
backtests, conservar artifacts y revisar la informacion desde un dashboard
interactivo.

## Alcance

El repositorio contiene:

- codigo Python para ingesta, backtesting, screener, dashboard y auditorias;
- artifacts curados usados por la plataforma y la memoria;
- dashboard Trading Center en modo de revision;
- RiskGuard, MT5 y Telegram limitados al alcance demo/informativo documentado;
- memoria final en PDF, fuentes LaTeX, figuras y anexos de entrega.

Limites importantes:

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
artifacts/              Evidencias y salidas curadas para ejecucion/revision.
docs/                   Memoria final, fuentes LaTeX, figuras y anexos.
docs/Memoria TFG/       Memoria, fuentes LaTeX, figuras y anexos.
tests/                  Tests unitarios y de integracion ligera.
sql/                    Esquemas y material SQL del proyecto.
```

## Memoria y anexos

La memoria final compilada esta en:

```text
docs/Memoria TFG/memoria_tfg.pdf
```

Los anexos de entrega estan en:

```text
docs/Memoria TFG/anexos/paquete_entrega/
```

El archivo `MANIFEST_ARCHIVOS.csv` dentro de esa carpeta resume las evidencias
incluidas.

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
python -m trading_center.dash_readonly_app --audit-only --output-dir artifacts\tfg\dashboard_audit_local
```

El dashboard consume artifacts locales ya generados. Si falta una fuente, el
comportamiento esperado es degradar de forma auditada o bloquear la ruta
correspondiente, no inventar datos.

Nota de rendimiento: el dashboard se entrega como herramienta local de revision
y visualizacion de resultados del TFG. No esta optimizado como producto web para
tiempos de carga minimos ni para uso multiusuario; algunas vistas pueden tardar
al cargar porque leen artifacts curados, tablas y figuras locales.

## Pruebas

Prueba focal del dashboard:

```powershell
python -m pytest tests\test_trading_center_dash_readonly_app.py -q
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
configuracion local explicita. Por defecto, las capas sensibles estan disenadas
para funcionar en modo auditado, informativo o fail-closed.

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
- `trading_center/telegram_sender_gate.py`: gate de envio fail-closed.
- `trading_center/codex_ai_analyst_package_renderer.py`: paquetes de revision.

## Notas de seguridad

Este repositorio no debe usarse como sistema de produccion para operar mercados.
La memoria explica los limites metodologicos, el alcance demo y las cautelas de
interpretacion. Cualquier uso operativo real exigiria validacion adicional,
control de costes, supervision continua, gestion de riesgo mas amplia y
revision externa.
