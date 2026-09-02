"""Koneksi & inisialisasi database SQLite (aiosqlite)."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import aiosqlite

from bot.config import DB_PATH
from bot.data.products import PRODUCTS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Buka koneksi SQLite sebagai async context manager.

    Cara pakai: `async with get_db() as db:`
    Koneksi otomatis ditutup saat keluar blok.
    """
    conn: aiosqlite.Connection = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    """Inisialisasi tabel SQLite dan data awal (seeding)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # 1. Users
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        # 2. Kategori
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)

        # 3. Produk
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                category_id TEXT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
        """)

        # 4. Stok akun
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                account_data TEXT NOT NULL,
                is_sold INTEGER DEFAULT 0,
                order_id INTEGER,
                created_at TEXT NOT NULL,
                sold_at TEXT,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        """)

        # 5. Orders
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'PENDING',
                payment_url TEXT,
                qris_data TEXT,
                delivered_stock_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(delivered_stock_id) REFERENCES stocks(id)
            )
        """)

        # Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_invoice_id ON orders(invoice_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stocks_product_sold ON stocks(product_id, is_sold)")

        await _seed_categories(db)
        await _seed_products(db)
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def _seed_categories(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("SELECT COUNT(*) FROM categories")
    (count,) = await cursor.fetchone()
    if count == 0:
        categories = [
            ("streaming", "🎬 Streaming & Video"),
            ("music", "🎵 Music & Audio"),
        ]
        await db.executemany("INSERT INTO categories (id, name) VALUES (?, ?)", categories)


async def _seed_products(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("SELECT COUNT(*) FROM products")
    (count,) = await cursor.fetchone()
    if count > 0:
        return
    now = _utc_now_iso()
    for p in PRODUCTS:
        await db.execute(
            """
            INSERT OR IGNORE INTO products (id, category_id, name, description, price, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (p["id"], p.get("category", "streaming"), p["name"], p["description"], p["price"], now),
        )
    logger.info("Seeded %d default products into database.", len(PRODUCTS))
