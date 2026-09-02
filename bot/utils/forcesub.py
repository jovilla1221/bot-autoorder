"""Verifikasi force-subscribe: user wajib join channel sebelum memakai bot."""
import logging
from typing import Union

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, Message

from bot.config import FORCE_SUB_CHANNEL

logger = logging.getLogger(__name__)

TelegramEvent = Union[Message, CallbackQuery]

_MEMBER_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.RESTRICTED,
}


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Cek keanggotaan user di channel force-sub."""
    try:
        member = await bot.get_chat_member(FORCE_SUB_CHANNEL, user_id)
    except Exception:
        logger.warning("[forcesub] Gagal cek keanggotaan user_id=%s", user_id, exc_info=True)
        return False
    return member.status in _MEMBER_STATUSES


async def ensure_subscribed(bot: Bot, event: TelegramEvent) -> bool:
    """Pastikan user sudah join channel; kirim pengingat jika belum.

    Return True jika lolos, False jika belum join (pesan pengingat sudah dikirim).
    """
    user = event.from_user
    if user is not None and await is_subscribed(bot, user.id):
        return True
    if isinstance(event, CallbackQuery):
        await event.answer("⚠️ Join channel dulu ya!", show_alert=True)
    else:
        await event.answer(f"⚠️ Join {FORCE_SUB_CHANNEL} dulu ya!")
    return False
