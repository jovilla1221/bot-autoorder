"""Keyboard & helper bersama untuk panel admin."""
from typing import Awaitable, Callable, TypeVar

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import ADMIN_IDS

T = TypeVar("T")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Tambah Stok", callback_data="adm:addstock")],
        [InlineKeyboardButton(text="📊 Cek Sisa Stok", callback_data="adm:stock")],
        [InlineKeyboardButton(text="🧾 Rekap Penjualan", callback_data="adm:sales")],
        [InlineKeyboardButton(text="🛍️ Kelola Produk", callback_data="adm:products")],
        [InlineKeyboardButton(text="📣 Broadcast", callback_data="adm:broadcast")],
    ])


def back_to_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Menu Admin", callback_data="adm:back")],
    ])


def back_to_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tambah Produk", callback_data="adm:addprod")],
        [InlineKeyboardButton(text="🛑 Aktif/Nonaktif", callback_data="adm:toggle")],
        [InlineKeyboardButton(text="🔙 Menu Admin", callback_data="adm:back")],
    ])


def admin_panel_text() -> str:
    return "🛠️ <b>Panel Admin</b>\n\nPilih menu di bawah:"


def is_cancel_command(text: str | None) -> bool:
    return bool(text and text.startswith("/cancel"))


async def guarded(target: Message | CallbackQuery, handler: Callable[[], Awaitable[T]]) -> T | None:
    """Jalankan handler admin hanya jika user adalah admin.

    Menggantikan decorator admin_guard: lebih eksplisit, mudah dites,
    dan tetap membalas penolakan lewat callback/message answer.
    """
    user = target.from_user
    if user is not None and is_admin(user.id):
        return await handler()
    if isinstance(target, CallbackQuery):
        await target.answer("⛔ Khusus admin.", show_alert=True)
    elif isinstance(target, Message):
        await target.answer("⛔ Khusus admin.")
    return None
