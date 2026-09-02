"""Panel admin Telegram bot.

Struktur paket (pemecahan dari admin.py monolitik):
- kb.py          → keyboard, guard, helper bersama
- states.py      → FSM states
- stock.py       → cek & tambah stok massal
- stats.py       → rekap penjualan
- products.py    → kelola produk (tambah, aktif/nonaktif)
- broadcast.py   → broadcast pesan
- navigation.py  → navigasi panel & /cancel
"""
from aiogram import Router

from bot.handlers.admin.broadcast import router as broadcast_router
from bot.handlers.admin.navigation import router as navigation_router
from bot.handlers.admin.products import router as products_router
from bot.handlers.admin.stats import router as stats_router
from bot.handlers.admin.stock import router as stock_router

router = Router()
router.include_routers(stock_router, stats_router, products_router, broadcast_router, navigation_router)

__all__ = ["router"]
