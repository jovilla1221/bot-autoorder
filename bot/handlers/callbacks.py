from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery

from bot.utils.forcesub import is_subscribed
from bot.handlers.common import main_keyboard

router = Router()

@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot):
    if not await is_subscribed(bot, callback.from_user.id):
        await callback.answer("⚠️ Belum kedetect join. Pastikan sudah join @reveuseress lalu coba lagi.", show_alert=True)
        return
    await callback.answer("✅ Verified!")
    await callback.message.delete()
    await callback.message.answer(
        "✅ Terima kasih sudah join channel!\n\nSelamat datang di bot order auto.",
        reply_markup=main_keyboard()
    )