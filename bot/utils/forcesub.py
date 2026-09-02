from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from bot.config import FORCE_SUB_CHANNEL

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.RESTRICTED,
        }
    except Exception as e:
        print(f"[forcesub] check fail uid={user_id}: {e}")
        return False

async def require_sub(bot: Bot, user_id: int) -> bool:
    return await is_subscribed(bot, user_id)

async def require_sub_callback(callback, bot: Bot) -> bool:
    if not await is_subscribed(bot, callback.from_user.id):
        await callback.answer("⚠️ Join channel dulu", show_alert=True)
        return False
    await callback.answer()
    return True
