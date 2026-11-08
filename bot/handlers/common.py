"""Handler dasar: /start, force-sub, dan keyboard menu utama bersama."""
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

from bot.config import FORCE_SUB_URL
from bot.database import crud
from bot.utils.forcesub import ensure_subscribed

router = Router()


def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel", url=FORCE_SUB_URL)],
        [InlineKeyboardButton(text="✅ Sudah Join", callback_data="check_sub")],
    ])


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Katalog Produk"), KeyboardButton(text="💰 Cek Status")],
            [KeyboardButton(text="ℹ️ Bantuan")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def register_user(event: Message | CallbackQuery) -> None:
    """Simpan/perbarui data user ke DB (dipanggil di awal tiap handler)."""
    user = event.from_user
    if user is None:
        return
    await crud.upsert_user(user_id=user.id, username=user.username, first_name=user.first_name)


import html

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot) -> None:
    await register_user(message)
    name = html.escape(message.from_user.first_name or "Kak") if message.from_user else "Kak"
    from bot.utils.forcesub import is_subscribed
    if not (message.from_user and await is_subscribed(bot, message.from_user.id)):
        await message.answer(
            f"👋 Halo, <b>{name}</b>!\n\n"
            "Selamat datang di <b>Reveuse Space Auto-Order</b> ⚡\n\n"
            "Sebelum mulai melihat katalog dan bertransaksi, silakan bergabung terlebih dahulu "
            "ke channel resmi kami untuk informasi ketersediaan stok, garansi, dan promo spesial:",
            reply_markup=join_keyboard(),
            parse_mode="HTML",
        )
        return
    await message.answer(
        f"👋 Halo, <b>{name}</b>!\n\n"
        "Selamat datang di <b>Reveuse Space Auto-Order</b> ⚡\n\n"
        "🛒 Silakan pilih menu <b>Katalog Produk</b> di bawah untuk mulai berbelanja akun premium "
        "dengan sistem pengiriman otomatis instan.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, bot: Bot) -> None:
    await cmd_start(message, bot)
