# Codex AI Analyst Model Call Controlled V1

Decision: `codex_ai_analyst_real_model_review_v1_generated_and_validated`

## Resultado

Se implementa una pasarela controlada para validar paquetes del AI Analyst y ejecutar una llamada real solo cuando todos los gates estan activos. Por defecto no se llama a modelos y no se ejecuta ninguna llamada de red.

## Paquete Validado

- package_id: `correlation_H1_EURO50_FRA40_8a59b672`
- package_dir: `C:\Users\ralr1\Desktop\CD\TFG\TFG-Raul_Rodriguez\artifacts\tfg\codex_ai_analyst_dash_integration_v1_2026-06-07\correlation_package_renderer\packages\correlation_H1_EURO50_FRA40_8a59b672`
- package_validation_decision: `pass`

## Request

- request_decision: `real_model_called`
- call_mode: `real`
- provider_configured: `True`
- network_call_allowed: `True`
- model_called: `True`
- ai_review_generated: `True`
- output_validation_status: `pass`
- real_model_call_error_type: ``
- macro_web_research_requested: `True`

## Seguridad

- sql_real_written=False
- mt5_connected=False
- telegram_connected=False
- orders_sent=0
- signals_generated=False

## Siguiente Paso

Mantener `allow_network_call=false` por defecto en la UI. Para una llamada real se exige proveedor OpenAI, modelo, presupuesto, secreto externo, intencion manual, imagen/datos del paquete y validacion posterior del JSON.
