from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.forcesub import require_sub
from bot.data.products import get_product
from bot.utils.sayabayar import client

router = Router()

@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, bot: Bot):
    if not await require_sub(bot, callback.from_user.id):
        await callback.answer("⚠️ Join dulu!", show_alert=True)
        return
    pid = callback.data[4:]  # after "buy:"
    prod = get_product(pid)
    if not prod:
        await callback.answer("Produk tidak ditemukan", show_alert=True)
        return
    result = await client.create_invoice(
        amount=prod["price"],
        description=prod["name"],
        customer_name=callback.from_user.first_name,
    )
    if result["error"]:
        await callback.answer("❌ Gagal buat invoice", show_alert=True)
        await callback.message.answer(f"❌ Gagal: {result['data']}")
        return
    data = result["data"]
    invoice_id = data.get("invoice_id") or data.get("id") or "?"
    payment_url = data.get("payment_url") or data.get("url") or data.get("link") or ""
    
    # Cek apakah response berisi QRIS (cek tipe data)
    qris_data = data.get("qris") or data.get("qrcode") or data.get("image") or data.get("qris_image")
    
    await callback.message.edit_text(
        f"✅ <b>Invoice dibuat!</b>\n\n"
        f"📦 {prod['name']}\n"
        f"💰 Harga: Rp {prod['price']:,}\n"
        f"🆔 ID: <code>{invoice_id}</code>\n\n"
        f"Silakan bayar melalui metode yang tersedia di bawah ini:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Buka Pembayaran", url=payment_url or "https://sayabayar.com")],
            [InlineKeyboardButton(text="💳 QRIS", callback_data=f"qris:{invoice_id}")],
            [InlineKeyboardButton(text="🔙 Katalog", callback_data="back_catalog")],
        ])
    )
    await callback.answer("Invoice created!")

@router.callback_query(F.data.startswith("qris:"))
async def cb_qris(callback: CallbackQuery, bot: Bot):
    """Tampilkan QRIS image langsung"""
    invoice_id = callback.data[5:]
    # Cek status terlebih dahulu
    result = await client.check_status(invoice_id)
    if result["error"]:
        await callback.answer("❌ Gagal cek invoice", show_alert=True)
        return
    data = result["data"]
    
    # Ambil QRIS URL atau base64 image dari response
    qris_image = data.get("qris_image") or data.get("qr_code_image") or data.get("image") or ""
    
    if qris_image:
        # Kirim sebagai foto dengan keterangan
        await callback.message.answer_photo(
            qris_image,
            caption=f"💳 <b>QRIS Payment</b>\n\n"
                    f"📦 Produk: Pembayaran Invoice\n"
                    f"🆔 Invoice ID: <code>{invoice_id}</code>\n"
                    f"💰 Nominal: Sesuai invoice di atas\n\n"
                    f"Silakan scan QRIS di atas untuk membayar.",
            parse_mode="HTML"
        )
    else:
        # Kalau gak punya image URL, fallback ke link pembayaran
        payment_url = data.get("payment_url") or data.get("url") or ""
        await callback.message.answer(
            f"📋 <b>Invoice Status</b>\n\n"
            f"🆔 ID: <code>{invoice_id}</code>\n"
            f"💰 Nominal: Rp {data.get('amount', '?')}\n"
            f"📊 Status: <b>{data.get('status') or data.get('payment_status') or '?'}</b>\n"
            f"🔗 Bayar: {payment_url}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Cek Ulang", callback_data=f"check:{invoice_id}")],
                [InlineKeyboardButton(text="🔙 Kembali", callback_data="back_catalog")],
            ])
        )
    await callback.answer()

@router.callback_query(F.data == "back_catalog")
async def cb_back_catalog(callback: CallbackQuery, bot: Bot):
    if not await require_sub(bot, callback.from_user.id):
        await callback.answer("⚠️ Join dulu!", show_alert=True)
        return
    pid = "netflix_trial_reg_th"
    from bot.handlers.common import format_slide, slide_keyboard
    await callback.message.edit_text(
        format_slide(pid, 0),
        parse_mode="HTML",
        reply_markup=slide_keyboard(pid, 0)
    )
    await callback.answer()

@router.message(F.text == "💰 Cek Status")
async def check_status_prompt(message: Message, bot: Bot):
    if not await require_sub(bot, message.from_user.id):
        await message.answer("⚠️ Join @reveuseress dulu ya!")
        return
    await message.answer("🔍 Kirim ID invoice untuk cek status:")

@router.message(F.text == "ℹ️ Bantuan")
async def help_cmd(message: Message, bot: Bot):
    if not await require_sub(bot, message.from_user.id):
        await message.answer("⚠️ Join @reveuseress dulu ya!")
        return
    await message.answer(
        "📖 <b>Bantuan</b>\n\n"
        "<b>🛒 Katalog Produk</b> — lihat dan beli produk\n"
        "<b>💰 Cek Status</b> — cek status invoice via ID\n"
        "<b>ℹ️ Bantuan</b> — tampilkan pesan ini\n\n"
        "Bot butuh join @reveuseress dulu.",
        parse_mode="HTML"
    )

@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{6,}$"))
async def check_status_by_id(message: Message, bot: Bot):
    if not await require_sub(bot, message.from_user.id):
        return
    invoice_id = message.text.strip()
    result = await client.check_status(invoice_id)
    if result["error"]:
        await message.answer(f"❌ Gagal cek: {result['data']}")
        return
    data = result["data"]
    status = data.get("status") or data.get("payment_status") or "?"
    await message.answer(
        f"📋 <b>Invoice</b> <code>{invoice_id}</code>\n"
        f"Status: <b>{status}</b>\n"
        f"Data: {data}",
        parse_mode="HTML"
    )