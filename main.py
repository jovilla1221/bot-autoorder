from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio
import logging
import sys

from bot.config import BOT_TOKEN

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from bot.handlers.common import router as common_router
from bot.handlers.order import router as order_router
from bot.handlers.callbacks import router as callbacks_router

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(common_router)
dp.include_router(order_router)
dp.include_router(callbacks_router)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())