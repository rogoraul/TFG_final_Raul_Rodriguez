# Telegram Real Sender V1

Fecha: 2026-06-09T08:56:36Z

Decision: `telegram_real_sender_v1_real_send_executed`.

## Resumen

Se implementa `telegram_real_sender_v1` como sender informativo real con
defaults fail-closed. El modulo consume `allowed_to_send.csv` producido por
`telegram_sender_gate_v1`, revalida seguridad, secretos, rate limits y wording,
y registra intentos de envio.

En el run actual no se envia nada salvo que se hayan activado explicitamente
`--telegram-enabled`, `--allow-real-send`, `--send-real`, confirmacion manual y
secretos externos por entorno.

## Modulo Y CLI

- Modulo: `trading_center/telegram_real_sender.py`
- CLI segura por defecto:

```powershell
python -m trading_center.telegram_real_sender --input-dir artifacts/tfg/telegram_sender_gate_v1_review_2026-05-29/simulated_enabled_gate --output-dir artifacts/tfg/telegram_real_sender_v1_2026-05-29
```

## Resultado Del Run Actual

- Intentos evaluados: 7
- Mensajes enviados: 1
- Mensajes bloqueados antes de enviar: 6
- Tipos enviados: mt5_bot_status_digest
- Razones principales de bloqueo: delivery_not_preview_allowed=4, max_messages_exceeded=2
- `telegram_connected=true`
- `telegram_real_messages_sent=1`

## Seguridad

- Token y chat ID solo pueden venir de entorno externo en ejecucion real.
- No se imprimen ni guardan tokens/chat IDs.
- No se lee `.env` directamente.
- `.env` local ignorado se audita como warning, no como fuente.
- Ficheros candidatos trackeados o locales no ignorados bloquean.
- No hay SQL writes, DDL, bot, MT5, backtests ni senales.
- WaveCount queda bloqueado por defecto y nunca se usa como filtro.

## Credenciales Auditadas

- Credenciales externas de Telegram disponibles durante la validacion local.
- Archivo `.env` local presente e ignorado por Git.
- No se imprimen ni guardan valores sensibles.
- Las plantillas publicas no contienen secretos reales.

## Outputs

- `send_attempts.csv`
- `send_attempts.json`
- `sent_messages_audit.csv`
- `blocked_before_send.csv`
- `telegram_response_audit.csv`
- `secret_handling_audit.csv`
- `rate_limit_audit.csv`
- `issues_or_risks.csv`
- `run_meta.json`

## Riesgos Pendientes

- warning: At least one real Telegram message was sent.

## Siguiente Paso

Auditar `telegram_real_sender_v1` antes de cualquier uso real manual. Bot y MT5
siguen fuera de alcance.
