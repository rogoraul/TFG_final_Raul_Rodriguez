"""Async scheduler for periodic MT5 ingestion and Trading Center refresh hooks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import MetaTrader5 as mt5

from data.mt5.trading_center_refresh_hook import maybe_run_trading_center_refresh_after_ingest
from data.mt5.updater import update_batch

TF_MINUTES = {
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


async def wait_until_next_minute_multiple(minutes_interval: int) -> None:
    """Sleep until the next wall-clock minute multiple for a timeframe cadence."""
    now = datetime.now()
    next_minute = (now.minute // minutes_interval + 1) * minutes_interval
    target_time = now.replace(second=0, microsecond=0) + timedelta(minutes=next_minute - now.minute)

    seconds_to_wait = (target_time - now).total_seconds()
    if seconds_to_wait <= 0:
        seconds_to_wait += minutes_interval * 60

    print(f"[WAIT] Sincronizando: Proxima ejecucion en {int(seconds_to_wait)}s (a las {target_time.strftime('%H:%M:%S')})")
    await asyncio.sleep(seconds_to_wait)


async def loop_15m() -> None:
    """Continuously update M15 data and refresh Trading Center short-timeframe artifacts."""
    while True:
        await wait_until_next_minute_multiple(15)

        print("[>] Ejecutando actualizacion de M15...")
        try:
            update_batch([mt5.TIMEFRAME_M15])
            maybe_run_trading_center_refresh_after_ingest(["M15"])
        except Exception as e:
            print(f"[X] Error en ciclo M15: {e}")


async def loop_30m() -> None:
    """Continuously update M30 data."""
    while True:
        await wait_until_next_minute_multiple(30)

        print("[>] Ejecutando actualizacion de M30...")
        try:
            update_batch([mt5.TIMEFRAME_M30])
        except Exception as e:
            print(f"[X] Error en ciclo M30: {e}")


async def loop_1h() -> None:
    """Continuously update H1/H4/D1 data and refresh higher-timeframe artifacts."""
    while True:
        await wait_until_next_minute_multiple(60)

        print("[>] Ejecutando actualizacion de H1, H4, D1...")
        try:
            update_batch([mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1])
            maybe_run_trading_center_refresh_after_ingest(["H1", "H4", "D1"])
        except Exception as e:
            print(f"[X] Error en ciclo 1H: {e}")


async def main() -> None:
    """Start all ingestion loops and keep them running until interrupted."""
    print("[START] Iniciando Scheduler Asincrono...")

    task15 = asyncio.create_task(loop_15m())
    task30 = asyncio.create_task(loop_30m())
    task60 = asyncio.create_task(loop_1h())

    await asyncio.gather(task15, task30, task60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[STOP] Scheduler detenido manualmente.")
