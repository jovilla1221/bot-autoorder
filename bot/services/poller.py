"""Background payment poller: cek invoice PENDING secara berkala."""
import asyncio
import logging

from aiogram import Bot

from bot.constants import PAID_STATUSES, TERMINAL_STATUSES
from bot.database import crud
from bot.services.fulfillment import process_order_fulfillment
from bot.utils.sayabayar import client, parse_invoice_status

logger = logging.getLogger(__name__)


async def check_single_pending_order(bot: Bot, order: dict) -> None:
    """Cek satu invoice PENDING ke gateway dan proses perubahan statusnya."""
    invoice_id = order["invoice_id"]
    try:
        result = await client.check_status(invoice_id)
    except Exception:
        logger.exception("[Poller] Exception saat cek invoice %s", invoice_id)
        return

    if result.get("error"):
        logger.debug("[Poller] Error cek invoice %s: %s", invoice_id, result.get("data"))
        return

    data = result.get("data", {})
    status = parse_invoice_status(data)
    if status in PAID_STATUSES:
        paid_amount = data.get("amount") or data.get("amount_unique")
        logger.info("[Poller] Invoice %s terdeteksi LUNAS (%s). Memproses fulfillment...", invoice_id, status)
        await process_order_fulfillment(bot, invoice_id, paid_amount=paid_amount)
    elif status in TERMINAL_STATUSES:
        logger.info("[Poller] Invoice %s status berubah menjadi %s", invoice_id, status)
        await crud.update_order_status(invoice_id, status)


async def start_payment_poller(bot: Bot, interval_seconds: int = 15) -> None:
    """Worker background yang mengecek invoice berstatus PENDING secara berkala."""
    logger.info("[Poller] Background payment poller dimulai (interval: %ss)", interval_seconds)
    while True:
        try:
            pending_orders = await crud.get_pending_orders()
            if pending_orders:
                logger.debug("[Poller] Memeriksa %d invoice PENDING", len(pending_orders))
                for order in pending_orders:
                    await check_single_pending_order(bot, order)
                    await asyncio.sleep(0.5)  # jeda kecil agar tidak spam request
        except asyncio.CancelledError:
            logger.info("[Poller] Background payment poller dihentikan.")
            break
        except Exception:
            logger.exception("[Poller] Error dalam loop poller")
        await asyncio.sleep(interval_seconds)
