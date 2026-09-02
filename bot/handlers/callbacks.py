"""Handler callback umum (verifikasi join channel)."""
from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery

from bot.handlers.common import main_keyboard, register_user
from bot.utils.forcesub import is_subscribed

router = Router()


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot) -> None:
    await register_user(callback)
    if not await is_subscribed(bot, callback.from_user.id):
        await callback.answer(
            "⚠️ Belum terdeteksi join. Pastikan sudah join channel lalu coba lagi.",
            show_alert=True,
        )
        return
    import html
    user_name = html.escape(callback.from_user.first_name or "Kak") if callback.from_user else "Kak"
    await callback.answer("✅ Verifikasi Berhasil!")
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Terima kasih sudah bergabung, <b>{user_name}</b>!\n\n"
        "Selamat datang di <b>Reveuse Space Auto-Order</b> ⚡\n\n"
        "🛒 Silakan pilih menu <b>Katalog Produk</b> di bawah untuk melihat daftar akun yang siap dikirim instan:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
