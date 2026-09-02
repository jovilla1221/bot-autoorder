"""Handler admin: kelola produk (daftar, tambah via FSM, aktif/nonaktif)."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.constants import DEFAULT_CATEGORY_ID
from bot.database import crud
from bot.handlers.admin.kb import admin_keyboard, back_to_admin_keyboard, back_to_products_keyboard, guarded, is_cancel_command
from bot.handlers.admin.states import AddProductFSM

router = Router()


def _product_status_icon(is_active: int) -> str:
    return "✅" if is_active else "⛔"


@router.callback_query(F.data == "adm:products")
async def cb_products(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.clear()
        products = await crud.get_all_products(only_active=False)
        lines = ["🛍️ <b>Daftar Produk</b>\n"]
        if not products:
            lines.append("(kosong)")
        for p in products:
            lines.append(
                f"{_product_status_icon(p['is_active'])} <b>{p['name']}</b>\n"
                f"   <code>{p['id']}</code> — Rp {p['price']:,}"
            )
        await callback.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=back_to_products_keyboard(),
        )
        await callback.answer()

    await guarded(callback, run)


@router.callback_query(F.data == "adm:addprod")
async def cb_addprod(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.set_state(AddProductFSM.input_id)
        await callback.message.edit_text(
            "➕ <b>Tambah Produk Baru</b>\n\n"
            "1️⃣ Kirim <b>ID produk</b> (tanpa spasi, cth: <code>netflix_premium_1bln</code>):\n\n"
            "Kirim /cancel untuk batal.",
            parse_mode="HTML",
        )
        await callback.answer()

    await guarded(callback, run)


@router.message(AddProductFSM.input_id, F.text)
async def prod_input_id(message: Message, state: FSMContext) -> None:
    async def run() -> None:
        if is_cancel_command(message.text):
            await state.clear()
            await message.answer("❌ Dibatalkan.")
            return
        product_id = (message.text or "").strip().replace(" ", "_")
        if await crud.get_product(product_id):
            await message.answer("⚠️ ID produk sudah dipakai. Kirim ID lain atau /cancel.")
            return
        await state.update_data(pid=product_id)
        await state.set_state(AddProductFSM.input_name)
        await message.answer("2️⃣ Kirim <b>nama produk</b> (cth: Netflix Premium 1 Bulan):", parse_mode="HTML")

    await guarded(message, run)


@router.message(AddProductFSM.input_name, F.text)
async def prod_input_name(message: Message, state: FSMContext) -> None:
    async def run() -> None:
        if is_cancel_command(message.text):
            await state.clear()
            await message.answer("❌ Dibatalkan.")
            return
        await state.update_data(name=(message.text or "").strip())
        await state.set_state(AddProductFSM.input_price)
        await message.answer("3️⃣ Kirim <b>harga</b> dalam angka (cth: 25000):", parse_mode="HTML")

    await guarded(message, run)


def parse_price(raw: str) -> int | None:
    """Parse input harga: buang pemisah ribuan; return None jika tidak valid."""
    try:
        price = int(raw.strip().replace(".", "").replace(",", ""))
    except ValueError:
        return None
    return price if price > 0 else None


@router.message(AddProductFSM.input_price, F.text)
async def prod_input_price(message: Message, state: FSMContext) -> None:
    async def run() -> None:
        if is_cancel_command(message.text):
            await state.clear()
            await message.answer("❌ Dibatalkan.")
            return
        price = parse_price(message.text or "")
        if price is None:
            await message.answer("⚠️ Harga harus angka positif. Coba lagi:")
            return
        await state.update_data(price=price)
        await state.set_state(AddProductFSM.input_desc)
        await message.answer("4️⃣ Kirim <b>deskripsi produk</b> (boleh multi-baris):", parse_mode="HTML")

    await guarded(message, run)


@router.message(AddProductFSM.input_desc, F.text)
async def prod_input_desc(message: Message, state: FSMContext, bot: Bot) -> None:
    async def run() -> None:
        if is_cancel_command(message.text):
            await state.clear()
            await message.answer("❌ Dibatalkan.")
            return
        data = await state.get_data()
        ok = await crud.add_product(
            product_id=data["pid"],
            category_id=DEFAULT_CATEGORY_ID,
            name=data["name"],
            description=(message.text or "").strip(),
            price=data["price"],
        )
        await state.clear()
        if ok:
            await message.answer(
                f"✅ Produk <b>{data['name']}</b> ditambahkan!\n"
                f"🆔 <code>{data['pid']}</code> — Rp {data['price']:,}\n\n"
                "Jangan lupa tambah stok agar bisa dibeli.",
                parse_mode="HTML",
                reply_markup=admin_keyboard(),
            )
        else:
            await message.answer("❌ Gagal menambah produk (ID mungkin duplikat).", reply_markup=admin_keyboard())

    await guarded(message, run)


@router.callback_query(F.data == "adm:toggle")
async def cb_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    await _render_toggle_list(callback, state)
    await guarded(callback, lambda: _render_toggle_list(callback, state))


async def _render_toggle_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Tampilkan (atau refresh) daftar toggle aktif/nonaktif produk."""

    async def run() -> None:
        await state.clear()
        products = await crud.get_all_products(only_active=False)
        if not products:
            await callback.answer("Belum ada produk.", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(
            text=f"{_product_status_icon(p['is_active'])} {p['name']}",
            callback_data=f"adm:tgprod:{p['id']}",
        )] for p in products]
        buttons.append([InlineKeyboardButton(text="🔙 Menu Admin", callback_data="adm:back")])
        await callback.message.edit_text(
            "🛑 <b>Aktif/Nonaktif Produk</b>\n\nKlik produk untuk mengubah status:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
        await callback.answer()

    await guarded(callback, run)


@router.callback_query(F.data.startswith("adm:tgprod:"))
async def cb_toggle_prod(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        product_id = (callback.data or "").split(":", 2)[2]
        new_status = await crud.toggle_product_active(product_id)
        prod = await crud.get_product(product_id)
        status_text = "✅ AKTIF" if new_status else "⛔ NONAKTIF"
        await callback.answer(f"{prod['name'] if prod else product_id}: {status_text}", show_alert=True)
        await _render_toggle_list_inner(callback, state)

    await guarded(callback, run)


async def _render_toggle_list_inner(callback: CallbackQuery, state: FSMContext) -> None:
    """Refresh daftar toggle (tanpa double-guard)."""
    products = await crud.get_all_products(only_active=False)
    if not products:
        return
    buttons = [[InlineKeyboardButton(
        text=f"{_product_status_icon(p['is_active'])} {p['name']}",
        callback_data=f"adm:tgprod:{p['id']}",
    )] for p in products]
    buttons.append([InlineKeyboardButton(text="🔙 Menu Admin", callback_data="adm:back")])
    try:
        await callback.message.edit_text(
            "🛑 <b>Aktif/Nonaktif Produk</b>\n\nKlik produk untuk mengubah status:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
    except Exception:
        pass  # pesan sudah dalam kondisi target; abaikan edit yang tidak berubah
