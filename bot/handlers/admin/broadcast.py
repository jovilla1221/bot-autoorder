"""Handler admin: broadcast pesan ke seluruh user."""
import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import crud
from bot.handlers.admin.kb import guarded, is_cancel_command
from bot.handlers.admin.states import BroadcastFSM

logger = logging.getLogger(__name__)

router = Router()

# Jeda antar kirim untuk menghindari flood limit Telegram
BROADCAST_DELAY_SECONDS = 0.05


async def broadcast_to_users(bot: Bot, users: list[dict], text: str) -> tuple[int, int]:
    """Kirim pesan ke semua user. Return (terkirim, gagal)."""
    sent = failed = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            logger.warning("Broadcast gagal ke user_id=%s", u.get("user_id"), exc_info=True)
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY_SECONDS)
    return sent, failed


@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.set_state(BroadcastFSM.input_message)
        await callback.message.edit_text(
            "📣 <b>Broadcast</b>\n\n"
            "Kirim pesan yang mau disebar ke semua user "
            "(boleh teks biasa atau format HTML).\n\n"
            "Kirim /cancel untuk batal.",
            parse_mode="HTML",
        )
        await callback.answer()

    await guarded(callback, run)


@router.message(BroadcastFSM.input_message, F.text)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    async def run() -> None:
        if is_cancel_command(message.text):
            await state.clear()
            await message.answer("❌ Dibatalkan.")
            return
        users = await crud.get_all_users()
        await state.clear()
        status_msg = await message.answer(f"📡 Mengirim ke {len(users)} user...")
        sent, failed = await broadcast_to_users(bot, users, message.text or "")
        try:
            await status_msg.edit_text(
                f"📡 <b>Broadcast selesai</b>\n\n✅ Terkirim: {sent}\n❌ Gagal: {failed}",
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("Gagal update pesan status broadcast", exc_info=True)

    await guarded(message, run)
