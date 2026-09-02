"""Handler admin: rekap penjualan & inventori."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.database import crud
from bot.handlers.admin.kb import back_to_admin_keyboard, guarded

router = Router()


def format_sales_report(stats: dict) -> str:
    """Susun teks rekap penjualan dari hasil crud.get_sales_stats()."""
    lines = [
        "🧾 <b>Rekap Penjualan</b>\n",
        f"✅ Transaksi sukses: <b>{stats['completed']}</b>",
        f"💰 Total omzet: <b>Rp {stats['revenue']:,}</b>",
        f"⏳ Pending: <b>{stats['pending']}</b>",
        f"⚠️ Lunas tapi stok habis: <b>{stats['paid_oos']}</b>",
        f"📦 Total stok ready: <b>{stats['stock_ready']}</b>",
    ]
    if stats.get("top_products"):
        lines.append("\n<b>Produk terlaris:</b>")
        lines.extend(f"• {row['name']} — {row['sold']}x terjual" for row in stats["top_products"])
    return "\n".join(lines)


@router.callback_query(F.data == "adm:sales")
async def cb_sales(callback: CallbackQuery, state: FSMContext) -> None:
    async def run() -> None:
        await state.clear()
        stats = await crud.get_sales_stats()
        await callback.message.edit_text(
            format_sales_report(stats), parse_mode="HTML", reply_markup=back_to_admin_keyboard(),
        )
        await callback.answer()

    await guarded(callback, run)
