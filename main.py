"""Entry point bot Telegram auto-order (SayaBayar) + Web Dashboard.

Mode:
- Default: bot + dashboard web dalam satu proses (dashboard di thread uvicorn).
- WEB_ENABLED=0: bot saja.
"""
import asyncio
import logging
import sys
import threading

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import bot.handlers.admin  # noqa: F401 — pastikan paket admin ter-load
from bot.config import BOT_TOKEN, WEB_ENABLED, WEB_HOST, WEB_PORT
from bot.database.db import init_db
from bot.handlers.callbacks import router as callbacks_router
from bot.handlers.catalog import router as catalog_router
from bot.handlers.common import router as common_router
from bot.handlers.order import router as order_router
from bot.services.poller import start_payment_poller

POLLER_INTERVAL_SECONDS = 15


def build_dispatcher() -> Dispatcher:
    """Susun dispatcher dengan seluruh router (tanpa side effects)."""
    dp = Dispatcher()
    dp.include_routers(common_router, catalog_router, order_router, callbacks_router, bot.handlers.admin.router)
    return dp


def start_web_server() -> threading.Thread | None:
    """Jalankan dashboard FastAPI/uvicorn di background thread.

    Return thread-nya, atau None jika WEB_ENABLED=0 / fastapi tidak terpasang.
    """
    if not WEB_ENABLED:
        return None
    try:
        import uvicorn
        from web.app import app
    except ImportError as exc:
        logging.warning("Dashboard web dilewati (dependensi belum terpasang: %s)", exc)
        return None

    config = uvicorn.Config(app, host=WEB_HOST, port=WEB_PORT, log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)

    def _run() -> None:
        server.run()

    thread = threading.Thread(target=_run, daemon=True, name="web-dashboard")
    thread.start()
    logging.info("Dashboard web: http://%s:%s", WEB_HOST, WEB_PORT)
    return thread


async def run() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN kosong. Isi .env terlebih dahulu.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    # Daftarkan bot ke bridge agar dashboard bisa kirim pesan
    from web.bot_bridge import set_bot
    set_bot(bot)

    await init_db()

    start_web_server()

    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Mulai / Buka Menu Utama"),
            BotCommand(command="katalog", description="Katalog Produk & Beli Akun"),
            BotCommand(command="status", description="Cek Status Pembayaran Invoice"),
            BotCommand(command="bantuan", description="Pusat Bantuan & Panduan"),
            BotCommand(command="admin", description="Panel Admin (Khusus Pengelola)"),
        ])
    except Exception as exc:
        logging.warning("Gagal mendaftarkan bot commands: %s", exc)

    poller_task = asyncio.create_task(start_payment_poller(bot, interval_seconds=POLLER_INTERVAL_SECONDS))
    try:
        await dp.start_polling(bot)
    finally:
        poller_task.cancel()
        await asyncio.gather(poller_task, return_exceptions=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(run())


if __name__ == "__main__":
    main()
