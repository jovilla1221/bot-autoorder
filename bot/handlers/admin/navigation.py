"""Handler admin: navigasi panel (kembali ke menu, /cancel)."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.admin.kb import admin_keyboard, admin_panel_text, guarded

router = Router()


@router.callback_query(F.data == "adm:back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.clear()
        await callback.message.edit_text(admin_panel_text(), parse_mode="HTML", reply_markup=admin_keyboard())
        await callback.answer()

    await guarded(callback, run)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    async def run() -> None:
        await state.clear()
        await message.answer("❌ Dibatalkan. Kembali ke panel admin: /admin")

    await guarded(message, run)
