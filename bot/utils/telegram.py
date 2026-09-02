"""Helper kecil untuk objek Telegram aiogram."""
from aiogram.types import CallbackQuery


def payload_after(callback: CallbackQuery, prefix: str) -> str:
    """Ambil bagian setelah prefix pada callback_data (mis. 'buy:<pid>')."""
    return (callback.data or "").removeprefix(prefix)
