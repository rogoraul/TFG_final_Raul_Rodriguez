# MT5 demo order sender v1

## Que implementa

Esta fase implementa un sender demo con preflight fail-closed. Lee intents
demo aceptados por RiskGuard, exige confirmacion manual, comprueba cuenta demo
y solo puede llamar a MT5 si se activan flags CLI y variables de entorno
explicitas. Por defecto no envia nada.

Flujo:

`RiskGuard demo intents -> confirmacion manual -> demo order request -> MT5 demo`

## Modos de ejecucion

Audit-only real actual:

```powershell
python -m trading_center.mt5_demo_order_sender --audit-only
```

Fixture/dry-run:

```powershell
python -m trading_center.mt5_demo_order_sender --fixture-mode --dry-run
```

Envio demo manual futuro, solo si hay intent aceptado, cuenta demo y
confirmacion manual:

```powershell
$env:MT5_DEMO_ORDER_SENDER_ENABLED="1"
$env:MT5_DEMO_TRADING_ENABLED="1"
$env:MT5_LIVE_TRADING_BLOCKED="1"
python -m trading_center.mt5_demo_order_sender --connect --send-demo-orders
```

Sin esos gates, el sender bloquea. Esta fase no ejecuta ese comando.

## Resultado

- Decision: `mt5_demo_order_sender_v1_no_intents_to_send`
- Requests preparados: 0
- Ordenes demo enviadas: 0
- Audit-only: True
- Dry-run: False

## Seguridad

- Live trading: `false`
- Telegram: `false`
- SQL writes: `false`
- Backtests: `false`
- Confirmacion manual requerida: `True`
- Cuenta demo requerida: `true`
- RiskGuard accepted requerido: `true`
- AI Analyst no aprueba ordenes

## Issues

- environment_gates_closed: Demo sending gates are closed; no order can be sent.
- no_demo_requests_prepared: No intent passed sender preflight.
