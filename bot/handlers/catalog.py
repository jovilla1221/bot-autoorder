"""Katalog dinamis: kategori → daftar produk (+stok) → slide detail → checkout."""
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import crud
from bot.database.crud import Product
from bot.utils.forcesub import ensure_subscribed
from bot.utils.telegram import payload_after

router = Router()

# ---------- label & text helpers ----------

STOCK_OK_ICON = "✅"
STOCK_EMPTY_ICON = "❌"


def stock_label(count: int) -> str:
    return f"{STOCK_OK_ICON} Stok tersedia: {count}" if count > 0 else f"{STOCK_EMPTY_ICON} Stok habis"


def _format_price(amount: int) -> str:
    return f"Rp {amount:,}"


# ---------- shared product list ----------

async def product_list_keyboard(products: list[Product], back_cb: str = "cat:root") -> InlineKeyboardMarkup:
    """Keyboard daftar produk; ikon menandakan ketersediaan stok."""
    buttons: list[list[InlineKeyboardButton]] = []
    for p in products:
        stock = await crud.get_stock_count(p["id"])
        icon = STOCK_OK_ICON if stock > 0 else STOCK_EMPTY_ICON
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {p['name']} — {_format_price(p['price'])}",
            callback_data=f"prod:{p['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Kategori", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_product_list(target: Message, title: str, products: list[Product], back_cb: str) -> None:
    await target.edit_text(
        f"{title}\n\nPilih produk untuk lihat detail ({STOCK_OK_ICON} = ada stok, {STOCK_EMPTY_ICON} = habis):",
        parse_mode="HTML",
        reply_markup=await product_list_keyboard(products, back_cb),
    )


async def _catalog_root_keyboard() -> InlineKeyboardMarkup:
    categories = await crud.get_categories()
    buttons = [[InlineKeyboardButton(text=c["name"], callback_data=f"cat:{c['id']}")] for c in categories]
    buttons.append([InlineKeyboardButton(text="🗂️ Semua Produk", callback_data="cat:all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------- entry points ----------

@router.message(F.text == "🛒 Katalog Produk")
@router.message(Command("katalog"))
async def show_catalog(message: Message, bot: Bot) -> None:
    if not await ensure_subscribed(bot, message):
        return
    await message.answer(
        "🛒 <b>Katalog Produk</b>\n\nPilih kategori:",
        parse_mode="HTML",
        reply_markup=await _catalog_root_keyboard(),
    )


@router.callback_query(F.data == "cat:root")
async def cb_catalog_root(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_subscribed(bot, callback):
        return
    await callback.message.edit_text(
        "🛒 <b>Katalog Produk</b>\n\nPilih kategori:",
        parse_mode="HTML",
        reply_markup=await _catalog_root_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_show_category(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_subscribed(bot, callback):
        return
    category_id = payload_after(callback, "cat:")
    if category_id == "all":
        products = await crud.get_all_products(only_active=True)
        title = "🗂️ <b>Semua Produk</b>"
    else:
        products = await crud.get_all_products(category_id=category_id, only_active=True)
        categories = await crud.get_categories()
        cat_name = next((c["name"] for c in categories if c["id"] == category_id), category_id)
        title = f"{cat_name}"
    if not products:
        await callback.answer("Tidak ada produk di kategori ini.", show_alert=True)
        return
    await send_product_list(callback.message, title, products, back_cb="cat:root")
    await callback.answer()


# ---------- product detail slides ----------

def slide_keyboard(product_id: str, slide: int, stock: int = 1) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if slide == 0:
        buttons.append([InlineKeyboardButton(text="Lihat Harga ➡️", callback_data=f"slide:{product_id}:1")])
    else:
        if stock > 0:
            buttons.append([InlineKeyboardButton(text="💳 Beli Sekarang", callback_data=f"buy:{product_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="❌ Stok Habis (Sedang Kosong)", callback_data=f"nostock:{product_id}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data=f"slide:{product_id}:0")])
    buttons.append([InlineKeyboardButton(text="🔙 Katalog", callback_data="back_catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def format_slide(product_id: str, slide: int) -> tuple[str, int]:
    prod = await crud.get_product(product_id)
    if not prod:
        return "Produk tidak ditemukan.", 0
    stock = await crud.get_stock_count(product_id)
    if slide == 0:
        return (
            f"📦 <b>{prod['name']}</b>\n\n{prod['description']}\n\n"
            f"📂 Kategori: {prod.get('category_id', '-')}\n"
            f"📊 {stock_label(stock)}"
        ), stock
    
    status_stok = "✅ <b>Stok Ready</b> (Siap Kirim Instan)" if stock > 0 else "❌ <b>Stok Habis</b> (Sedang Kosong)"
    petunjuk = (
        "Klik tombol 💳 <b>Beli Sekarang</b> di bawah untuk proses pembayaran QRIS otomatis."
        if stock > 0 else
        "⚠️ <i>Mohon maaf, saat ini produk sedang kehabisan stok dan belum dapat dipesan.</i>"
    )
    return (
        f"💰 <b>Harga: {_format_price(prod['price'])}</b>\n\n"
        f"📦 Produk: <b>{prod['name']}</b>\n"
        f"📊 Status: {status_stok}\n\n"
        f"{petunjuk}"
    ), stock


@router.callback_query(F.data.startswith("nostock:"))
async def cb_nostock(callback: CallbackQuery) -> None:
    await callback.answer(
        "⚠️ Maaf, stok akun untuk produk ini sedang kosong!\n\n"
        "Admin akan segera melakukan restock. Silakan cek produk lain atau hubungi admin.",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("slide:"))
async def cb_slide(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_subscribed(bot, callback):
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Bad request", show_alert=True)
        return
    product_id, slide = parts[1], int(parts[2])
    caption, stock = await format_slide(product_id, slide)
    if caption == "Produk tidak ditemukan.":
        await callback.answer("Produk tidak ditemukan", show_alert=True)
        return
    await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=slide_keyboard(product_id, slide, stock=stock))
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_show_product(callback: CallbackQuery, bot: Bot) -> None:
    """Klik produk dari daftar → tampilkan slide detail (slide 0)."""
    if not await ensure_subscribed(bot, callback):
        return
    product_id = payload_after(callback, "prod:")
    prod = await crud.get_product(product_id) if product_id else None
    if not prod or not prod.get("is_active"):
        await callback.answer("Produk tidak ditemukan / tidak aktif", show_alert=True)
        return
    caption, stock = await format_slide(product_id, 0)
    await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=slide_keyboard(product_id, 0, stock=stock))
    await callback.answer()


# ---------- navigation ----------

@router.callback_query(F.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_subscribed(bot, callback):
        return
    from bot.handlers.common import main_keyboard  # lokal: hindari import siklik modul utama
    await callback.message.delete()
    await callback.message.answer("✅ Menu utama", reply_markup=main_keyboard())
    await callback.answer()
