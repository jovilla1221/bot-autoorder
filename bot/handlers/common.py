from aiogram import Bot, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

from bot.utils.forcesub import require_sub
from bot.data.products import get_product

router = Router()

JOIN_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/reveuseress")],
    [InlineKeyboardButton(text="✅ Sudah Join", callback_data="check_sub")],
])

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Katalog Produk"), KeyboardButton(text="💰 Cek Status")],
            [KeyboardButton(text="ℹ️ Bantuan")],
        ],
        resize_keyboard=True,
    )

def slide_keyboard(pid: str, slide: int):
    buttons = []
    if slide == 0:
        buttons.append([InlineKeyboardButton(text="Lihat Harga ➡️", callback_data=f"slide:{pid}:1")])
    else:
        buttons.append([InlineKeyboardButton(text="💳 Beli Sekarang", callback_data=f"buy:{pid}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data=f"slide:{pid}:0")])
    buttons.append([InlineKeyboardButton(text="🔙 Menu", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_slide(pid: str, slide: int) -> str:
    prod = get_product(pid)
    if not prod:
        return "Produk tidak ditemukan."
    name = prod['name']
    if slide == 0:
        desc = prod['description']
        cat = prod['category']
        return "📦 <b>" + name + "</b>\n\n" + desc + "\n\n📂 Kategori: " + cat
    price_fmt = "{:,}".format(prod['price'])
    return "💰 <b>Harga: Rp " + price_fmt + "</b>\n\nProduk: " + name + "\n\nKlik tombol di bawah untuk bayar via SayaBayar."

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    if not await require_sub(bot, message.from_user.id):
        await message.answer(
            "⚠️ Harus join @reveuseress dulu.\nJoin lalu klik tombol di bawah:",
            reply_markup=JOIN_KEYBOARD
        )
        return
    await message.answer(
        "✅ Terima kasih sudah join!\n\nSelamat datang di bot order auto.",
        reply_markup=main_keyboard()
    )

@router.message(lambda m: m.text == "🛒 Katalog Produk")
async def show_catalog(message: Message, bot: Bot):
    if not await require_sub(bot, message.from_user.id):
        await message.answer("⚠️ Join @reveuseress dulu!")
        return
    pid = "netflix_trial_reg_th"
    await message.answer(
        format_slide(pid, 0),
        parse_mode="HTML",
        reply_markup=slide_keyboard(pid, 0)
    )

@router.callback_query(lambda c: c.data and c.data.startswith("slide:"))
async def cb_slide(callback: CallbackQuery, bot: Bot):
    if not await require_sub(bot, callback.from_user.id):
        await callback.answer("⚠️ Join dulu!", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Bad request", show_alert=True)
        return
    pid, slide_str = parts[1], parts[2]
    slide = int(slide_str)
    if not get_product(pid):
        await callback.answer("Produk tidak ditemukan", show_alert=True)
        return
    await callback.message.edit_text(
        format_slide(pid, slide),
        parse_mode="HTML",
        reply_markup=slide_keyboard(pid, slide)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery, bot: Bot):
    if not await require_sub(bot, callback.from_user.id):
        await callback.answer("⚠️ Join dulu!", show_alert=True)
        return
    await callback.message.delete()
    await callback.message.answer(
        "✅ Menu utama",
        reply_markup=main_keyboard()
    )
    await callback.answer()