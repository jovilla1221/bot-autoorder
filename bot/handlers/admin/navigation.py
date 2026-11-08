"""Handler admin: navigasi panel (kembali ke menu, /cancel)."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.admin.kb import admin_keyboard, admin_panel_text, guarded, is_admin

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    """Entry point panel admin via command /admin."""
    async def run() -> None:
        await state.clear()
        await message.answer(admin_panel_text(), parse_mode="HTML", reply_markup=admin_keyboard())

    await guarded(message, run)


@router.callback_query(F.data == "adm:back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.clear()
        await callback.message.edit_text(admin_panel_text(), parse_mode="HTML", reply_markup=admin_keyboard())
        await callback.answer()

    await guarded(callback, run)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user and is_admin(message.from_user.id):
        await message.answer("❌ Dibatalkan. Kembali ke panel admin: /admin")
    else:
        await message.answer("❌ Operasi dibatalkan.")
