"""Auto-fulfillment: klaim stok & kirim akun saat invoice lunas."""
import logging

from aiogram import Bot

from bot.config import ADMIN_IDS
from bot.database import crud

logger = logging.getLogger(__name__)


def _format_rupiah(amount: int) -> str:
    return f"Rp {amount:,}"


def _delivery_message(invoice_id: str, product_name: str, amount: int, account_data: str) -> str:
    return (
        "🎉 <b>Pembayaran Berhasil & Akun Terkirim!</b>\n\n"
        f"📦 <b>Produk:</b> {product_name}\n"
        f"🆔 <b>Invoice ID:</b> <code>{invoice_id}</code>\n"
        f"💰 <b>Nominal:</b> {_format_rupiah(amount)}\n\n"
        "🔑 <b>Data Akun / Kredensial:</b>\n"
        f"<code>{account_data}</code>\n\n"
        "📌 <b>Panduan & Ketentuan:</b>\n"
        "• Klik teks kredensial di atas untuk menyalin otomatis (1-tap copy).\n"
        "• Segera lakukan login dan amankan akun sesuai ketentuan.\n"
        "• Dilarang mengubah profil bersama atau melanggar batas device.\n\n"
        "💬 <i>Jika ada kendala akun atau butuh garansi, silakan hubungi admin kami. Terima kasih atas pembelian Anda!</i>"
    )


def _out_of_stock_message(invoice_id: str, product_name: str, amount: int) -> str:
    return (
        "⚠️ <b>Pembayaran Diterima (Stok Sedang Habis)</b>\n\n"
        f"📦 <b>Produk:</b> {product_name}\n"
        f"🆔 <b>Invoice ID:</b> <code>{invoice_id}</code>\n"
        f"💰 <b>Nominal:</b> {_format_rupiah(amount)}\n\n"
        "Status pembayaran Anda telah <b>LUNAS</b>, namun stok akun untuk produk ini baru saja habis.\n"
        "👨‍💻 Admin telah diberitahu dan akan segera mengirimkan akun Anda secara manual / melakukan restock.\n\n"
        "Silakan hubungi customer service kami jika membutuhkan bantuan."
    )


def _admin_alert_message(invoice_id: str, user_id: int, product_name: str, product_id: str, amount: int) -> str:
    return (
        "🚨 <b>ALERT: Order Lunas tapi STOK KOSONG!</b>\n\n"
        f"🆔 <b>Invoice:</b> <code>{invoice_id}</code>\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📦 <b>Produk:</b> {product_name} (<code>{product_id}</code>)\n"
        f"💰 <b>Nominal:</b> {_format_rupiah(amount)}\n\n"
        "⚠️ Segera lakukan restock atau kirim akun secara manual kepada user."
    )


async def _notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        return True
    except Exception:
        logger.error("[Fulfillment] Gagal kirim pesan ke user %s", user_id, exc_info=True)
        return False


async def _notify_admins(bot: Bot, text: str) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception:
            logger.error("[Fulfillment] Gagal kirim alert ke admin %s", admin_id, exc_info=True)


async def _deliver_stock(bot: Bot, invoice_id: str, order: dict, account_data: str, stock_id: int) -> bool:
    """Kirim akun ke pembeli dan tandai order COMPLETED."""
    product = await crud.get_product(order["product_id"])
    product_name = product["name"] if product else order["product_id"]

    await crud.update_order_status(invoice_id, "COMPLETED", delivered_stock_id=stock_id)
    sent = await _notify_user(bot, order["user_id"], _delivery_message(
        invoice_id, product_name, order["amount"], account_data,
    ))
    if sent:
        logger.info("[Fulfillment] Sukses kirim akun ke user %s untuk invoice %s", order["user_id"], invoice_id)
    return sent


async def _handle_out_of_stock(bot: Bot, invoice_id: str, order: dict) -> None:
    """Pembayaran lunas tapi stok kosong: beri tahu user & admin."""
    product_id = order["product_id"]
    product = await crud.get_product(product_id)
    product_name = product["name"] if product else product_id

    logger.warning("[Fulfillment] Stok habis untuk produk %s, order invoice %s", product_id, invoice_id)
    await crud.update_order_status(invoice_id, "PAID_OUT_OF_STOCK")
    await _notify_user(bot, order["user_id"], _out_of_stock_message(invoice_id, product_name, order["amount"]))
    await _notify_admins(bot, _admin_alert_message(
        invoice_id, order["user_id"], product_name, product_id, order["amount"],
    ))


async def process_order_fulfillment(bot: Bot, invoice_id: str, paid_amount: int | None = None) -> bool:
    """Proses pemenuhan pesanan (auto-delivery) untuk invoice yang lunas.

    Idempoten: aman dipanggil berulang tanpa risiko double delivery.
    `paid_amount`: nominal terverifikasi dari gateway — jika diberikan dan
    tidak sama dengan amount order, fulfillment DITOLAK (anti underpayment).
    """
    order = await crud.get_order_by_invoice(invoice_id)
    if not order:
        logger.warning("[Fulfillment] Invoice %s tidak ditemukan di database", invoice_id)
        return False

    # Verifikasi nominal: tolak jika pembayaran tidak persis sama
    if paid_amount is not None and int(paid_amount) != int(order["amount"]):
        logger.error(
            "[Fulfillment] NOMINAL TIDAK COCOK untuk invoice %s: order=%s paid=%s. Fulfillment ditolak.",
            invoice_id, order["amount"], paid_amount,
        )
        await crud.update_order_status(invoice_id, "AMOUNT_MISMATCH")
        return False

    if order.get("delivered_stock_id") is not None or order.get("status") == "COMPLETED":
        logger.info("[Fulfillment] Invoice %s sudah selesai dikirimkan sebelumnya", invoice_id)
        return True

    claimed = await crud.claim_available_stock(order["product_id"], order["id"])
    if claimed:
        await _deliver_stock(bot, invoice_id, order, claimed["account_data"], claimed["id"])
    else:
        await _handle_out_of_stock(bot, invoice_id, order)
    return True


async def deliver_account_manually(
    bot: Bot,
    order_id: int,
    account_data: str,
    stock_id: int | None = None,
) -> tuple[bool, str]:
    """Kirim akun secara manual oleh admin (dari dashboard web) ke pembeli order.

    - `stock_id` diberikan → stok DB ditandai terjual untuk order ini.
    - `account_data` saja → teks akun manual dikirim, order COMPLETED.
    Return (sukses, pesan).
    """
    order = await crud.get_order_by_id(order_id)
    if not order:
        return False, "Order tidak ditemukan."
    if order.get("status") == "COMPLETED":
        return False, "Order sudah COMPLETED sebelumnya."
    if not account_data.strip():
        return False, "Data akun kosong."

    bot_instance = bot
    sent = await _notify_user(bot_instance, order["user_id"], _delivery_message(
        order["invoice_id"],
        order.get("product_name") or order["product_id"],
        order["amount"],
        account_data.strip(),
    ))

    if stock_id is not None:
        stock = await crud.assign_stock_to_order(stock_id, order_id)
        if not stock:
            return False, "Stok tidak ditemukan / sudah terjual."
        await crud.update_order_status(order["invoice_id"], "COMPLETED", delivered_stock_id=stock_id)
    else:
        await crud.update_order_status(order["invoice_id"], "COMPLETED")

    logger.info("[Fulfillment] Manual delivery order %s oleh admin (sent=%s)", order_id, sent)
    if sent:
        return True, "Akun terkirim ke pembeli, order COMPLETED."
    return True, "Order COMPLETED, tapi pesan gagal terkirim ke user (bot mungkin diblokir)."
