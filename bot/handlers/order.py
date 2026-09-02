"""Handler order & pembayaran: buat invoice, QRIS, cek status."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import FALLBACK_PAYMENT_URL
from bot.constants import PAID_STATUSES
from bot.database import crud
from bot.handlers.common import register_user
from bot.services.fulfillment import process_order_fulfillment
from bot.utils.forcesub import ensure_subscribed
from bot.utils.sayabayar import client, extract_invoice_fields, parse_invoice_status
from bot.utils.telegram import payload_after

logger = logging.getLogger(__name__)

router = Router()


# ---------- helpers ----------

def _first_present(data: dict, *keys: str) -> str:
    """Ambil nilai string pertama yang ada (tidak None/kosong) dari dict response gateway."""
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


async def _sync_and_fulfill(bot: Bot, invoice_id: str, status: str, paid_amount: int | None = None) -> None:
    """Simpan status terbaru ke DB lokal, lalu proses fulfillment jika lunas."""
    if status in PAID_STATUSES:
        # Status PAID + nominal diverifikasi di dalam process_order_fulfillment
        await process_order_fulfillment(bot, invoice_id, paid_amount=paid_amount)
    else:
        await crud.update_order_status(invoice_id, status)


# ---------- buat invoice ----------

@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, bot: Bot) -> None:
    await register_user(callback)
    if not await ensure_subscribed(bot, callback):
        return
    product_id = payload_after(callback, "buy:")
    prod = await crud.get_product(product_id)
    if not prod:
        await callback.answer("Produk tidak ditemukan", show_alert=True)
        return

    stock = await crud.get_stock_count(product_id)
    if stock <= 0:
        await callback.answer(
            "⚠️ Maaf, stok akun untuk produk ini baru saja habis!\nInvoice tidak dapat dibuat.",
            show_alert=True,
        )
        return

    result = await client.create_invoice(
        amount=prod["price"],
        description=prod["name"],
        customer_name=callback.from_user.first_name,
    )
    if result["error"]:
        logger.error("Gagal buat invoice untuk produk %s: %s", product_id, result["data"])
        await callback.answer("❌ Gagal buat invoice", show_alert=True)
        await callback.message.answer(f"❌ Gagal: {result['data']}")
        return

    fields = extract_invoice_fields(result["data"])
    invoice_id = fields["invoice_id"]
    payment_url = fields["payment_url"]

    await crud.create_order(
        invoice_id=invoice_id,
        user_id=callback.from_user.id,
        product_id=product_id,
        amount=prod["price"],
        payment_url=payment_url,
    )

    await callback.message.edit_text(
        f"✅ <b>Invoice Pembayaran Dibuat!</b>\n\n"
        f"📦 <b>Produk:</b> {prod['name']}\n"
        f"💰 <b>Total Bayar:</b> Rp {prod['price']:,}\n"
        f"🆔 <b>ID Invoice:</b> <code>{invoice_id}</code>\n\n"
        f"⏳ <i>Invoice aktif selama 15 menit.</i>\n"
        f"🤖 <b>Auto-Delivery:</b> Sistem otomatis mengirimkan data akun dalam &lt;15 detik begitu pembayaran terverifikasi.\n"
        f"💡 <i>Anda tidak perlu menekan tombol cek status berkali-kali.</i>\n\n"
        f"Silakan klik tombol di bawah untuk melanjutkan pembayaran:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Bayar Sekarang (QRIS)", url=payment_url or FALLBACK_PAYMENT_URL)],
            [InlineKeyboardButton(text="🔄 Cek Status Pembayaran", callback_data=f"check:{invoice_id}")],
            [InlineKeyboardButton(text="🔙 Batal / Kembali ke Katalog", callback_data="back_catalog")],
        ]),
    )
    await callback.answer("Invoice created!")


# ---------- cek status via tombol ----------

@router.callback_query(F.data.startswith("check:"))
async def cb_check_invoice(callback: CallbackQuery, bot: Bot) -> None:
    """Cek status invoice via tombol callback."""
    invoice_id = payload_after(callback, "check:")
    result = await client.check_status(invoice_id)
    if result["error"]:
        local_order = await crud.get_order_by_invoice(invoice_id)
        if local_order and local_order["status"] in PAID_STATUSES:
            await callback.answer("✅ Invoice sudah lunas sebelumnya!", show_alert=True)
            return
        await callback.answer(f"Gagal cek: {result['data']}", show_alert=True)
        return

    data = result["data"]
    status = parse_invoice_status(data)
    paid_amount = data.get("amount") or data.get("amount_unique")
    if status in PAID_STATUSES:
        await callback.answer("✅ Pembayaran Berhasil!", show_alert=True)
        await _sync_and_fulfill(bot, invoice_id, status, paid_amount)
        await callback.message.edit_text(
            f"🎉 <b>Pembayaran Berhasil!</b>\n\n"
            f"Invoice: <code>{invoice_id}</code> telah lunas.\n"
            f"Data pesanan Anda telah dikirimkan ke chat ini.",
            parse_mode="HTML",
        )
    else:
        await crud.update_order_status(invoice_id, status)
        await callback.answer(f"Status saat ini: {status}", show_alert=True)


# ---------- navigasi & menu ----------

@router.callback_query(F.data == "back_catalog")
async def cb_back_catalog(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_subscribed(bot, callback):
        return
    from bot.handlers.catalog import send_product_list  # lokal: hindari siklus import

    products = await crud.get_all_products(only_active=True)
    if not products:
        await callback.message.edit_text("Tidak ada produk tersedia.")
        await callback.answer()
        return
    await send_product_list(callback.message, "🗂️ <b>Semua Produk</b>", products, back_cb="cat:root")
    await callback.answer()


@router.message(F.text == "💰 Cek Status")
@router.message(Command("status"))
async def check_status_prompt(message: Message, bot: Bot) -> None:
    await register_user(message)
    if not await ensure_subscribed(bot, message):
        return
    await message.answer("🔍 Kirim ID invoice untuk cek status:")


@router.message(F.text == "ℹ️ Bantuan")
@router.message(Command("bantuan"))
@router.message(Command("help"))
async def help_cmd(message: Message, bot: Bot) -> None:
    await register_user(message)
    if not await ensure_subscribed(bot, message):
        return
    await message.answer(
        "📖 <b>Pusat Bantuan & Panduan Pembelian</b>\n\n"
        "⚡ <b>Cara Berbelanja:</b>\n"
        "1. Klik menu <b>🛒 Katalog Produk</b> dan pilih kategori yang diinginkan.\n"
        "2. Pilih produk yang memiliki stok ready (bertanda ✅).\n"
        "3. Klik tombol 💳 <b>Beli Sekarang</b> untuk membuat invoice QRIS.\n"
        "4. Selesaikan pembayaran sebelum batas waktu 15 menit habis.\n"
        "5. <b>Selesai!</b> Akun akan otomatis dikirimkan ke chat ini dalam hitungan detik.\n\n"
        "💰 <b>Pengecekan Status Manual:</b>\n"
        "Ketik atau klik menu <b>💰 Cek Status</b> lalu kirimkan ID invoice jika ingin menyinkronkan status pembayaran secara manual.\n\n"
        "💬 <b>Kendala & Garansi Akun:</b>\n"
        "Seluruh transaksi diproses otomatis 24/7. Jika mengalami kendala stok atau butuh bantuan admin, silakan hubungi customer service kami di channel resmi.",
        parse_mode="HTML",
    )


# ---------- cek status via ID invoice (input manual) ----------

def _local_order_text(invoice_id: str, order: dict, sync_error: str) -> str:
    return (
        f"📋 <b>Invoice Terdaftar di Database</b>\n"
        f"ID: <code>{invoice_id}</code>\n"
        f"Produk ID: <code>{order['product_id']}</code>\n"
        f"Nominal: Rp {order['amount']:,}\n"
        f"Status: <b>{order['status']}</b>\n\n"
        f"<i>Catatan: Gagal sinkronisasi live ke SayaBayar ({sync_error})</i>"
    )


@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{6,}$"))
async def check_status_by_id(message: Message, bot: Bot) -> None:
    await register_user(message)
    if not await ensure_subscribed(bot, message):
        return
    invoice_id = (message.text or "").strip()
    result = await client.check_status(invoice_id)
    if result["error"]:
        local_order = await crud.get_order_by_invoice(invoice_id)
        if local_order:
            await message.answer(
                _local_order_text(invoice_id, local_order, str(result["data"])),
                parse_mode="HTML",
            )
        else:
            await message.answer(f"❌ Gagal cek: {result['data']}")
        return

    data = result["data"]
    status = parse_invoice_status(data)
    paid_amount = data.get("amount") or data.get("amount_unique")
    await _sync_and_fulfill(bot, invoice_id, status, paid_amount)
    await message.answer(
        f"📋 <b>Invoice</b> <code>{invoice_id}</code>\n"
        f"Status: <b>{status}</b>\n"
        f"Data: {data}",
        parse_mode="HTML",
    )
