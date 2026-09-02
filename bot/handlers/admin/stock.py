"""Handler admin: cek sisa stok dan tambah stok massal."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import crud
from bot.handlers.admin.kb import admin_keyboard, back_to_admin_keyboard, guarded, is_cancel_command
from bot.handlers.admin.states import AddStockFSM

router = Router()


@router.callback_query(F.data == "adm:stock")
async def cb_stock(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.clear()
        products = await crud.get_all_products(only_active=False)
        if not products:
            await callback.message.edit_text("Belum ada produk terdaftar.")
            await callback.answer()
            return
        lines = ["📊 <b>Sisa Stok per Produk</b>\n"]
        for p in products:
            count = await crud.get_stock_count(p["id"])
            lines.append(f"• <b>{p['name']}</b> (<code>{p['id']}</code>) — <b>{count}</b> ready")
        lines.append("\n<i>Stok ready = belum terjual.</i>")
        await callback.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=back_to_admin_keyboard(),
        )
        await callback.answer()

    await guarded(callback, run)


@router.callback_query(F.data == "adm:addstock")
async def cb_addstock_start(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        products = await crud.get_all_products(only_active=False)
        if not products:
            await callback.answer("Belum ada produk. Tambahkan produk dulu.", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(text=p["name"], callback_data=f"adm:stkprod:{p['id']}")] for p in products]
        buttons.append([InlineKeyboardButton(text="🔙 Menu Admin", callback_data="adm:back")])
        await callback.message.edit_text(
            "📦 <b>Tambah Stok</b>\n\nPilih produk:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
        await callback.answer()

    await guarded(callback, run)


@router.callback_query(F.data.startswith("adm:stkprod:"))
async def cb_addstock_pick(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        product_id = (callback.data or "").split(":", 2)[2]
        prod = await crud.get_product(product_id)
        if not prod:
            await callback.answer("Produk tidak ditemukan", show_alert=True)
            return
        await state.set_state(AddStockFSM.input_stock)
        await state.update_data(pid=product_id)
        await callback.message.edit_text(
            f"📦 Produk: <b>{prod['name']}</b>\n\n"
            "Kirim stok akun sekarang.\n"
            "<b>Format:</b> 1 akun per baris, contoh:\n"
            "<code>email@x.com:pass123</code>\n"
            "<code>user2:pass456</code>\n\n"
            "Kirim /cancel untuk batal.",
            parse_mode="HTML",
        )
        await callback.answer()

    await guarded(callback, run)


@router.message(AddStockFSM.input_stock, F.text)
async def process_stock_input(message: Message, state: FSMContext, bot: Bot) -> None:
    async def run() -> None:
        if is_cancel_command(message.text):
            await state.clear()
            await message.answer("❌ Dibatalkan.")
            return
        data = await state.get_data()
        product_id = data.get("pid", "")
        accounts = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
        if not accounts:
            await message.answer("⚠️ Tidak ada baris valid. Coba lagi atau /cancel.")
            return
        added = await crud.add_stocks_bulk(product_id, accounts)
        total = await crud.get_stock_count(product_id)
        prod = await crud.get_product(product_id)
        await state.clear()
        await message.answer(
            f"✅ <b>Stok ditambahkan!</b>\n\n"
            f"📦 {prod['name'] if prod else product_id}\n"
            f"➕ Baru: <b>{added}</b> akun\n"
            f"📊 Total ready: <b>{total}</b> akun",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

    await guarded(message, run)
