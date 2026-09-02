"""Bridge antara dashboard web dan instance aiogram Bot.

Saat dashboard dijalankan dalam proses bot yang sama, bot instance
di-set lewat `set_bot()`. Saat standalone, dashboard bisa membuat
instance Bot sendiri (token sama) hanya untuk mengirim pesan.
"""
import logging
from typing import Optional

from aiogram import Bot

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def set_bot(bot: Bot) -> None:
    """Daftarkan instance Bot dari proses utama (mode terintegrasi)."""
    global _bot
    _bot = bot
    logger.info("[Bridge] Bot instance terdaftar (mode terintegrasi).")


def get_bot() -> Bot:
    """Ambil Bot instance; buat sendiri jika standalone.

    Instance buatan sendiri tidak mem-polling (hanya kirim pesan),
    jadi aman berjalan berdampingan dengan proses bot utama.
    """
    global _bot
    if _bot is None:
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from bot.config import BOT_TOKEN

        _bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        logger.info("[Bridge] Bot instance standalone dibuat (kirim saja).")
    return _bot


def is_integrated() -> bool:
    """True jika dashboard berjalan dalam proses bot utama."""
    return _bot is not None
