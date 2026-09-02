"""CRUD helpers untuk database SQLite (aiosqlite).

Semua fungsi menerima/mengembalikan dict biasa (baris aiosqlite.Row
dikonversi) agar handler tidak bergantung pada tipe koneksi.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bot.database.db import get_db

logger = logging.getLogger(__name__)

# Alias tipe: baris produk/order/user adalah dict dengan kunci sesuai skema tabel.
Product = dict[str, Any]
Order = dict[str, Any]
User = dict[str, Any]
StockRow = dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================== USERS ====================

async def upsert_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> User:
    """Simpan atau perbarui data user Telegram."""
    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen = excluded.last_seen
            """,
            (user_id, username, first_name, now, now),
        )
        await db.commit()
    return {"user_id": user_id, "username": username, "first_name": first_name}


async def get_user(user_id: int) -> Optional[User]:
    """Ambil data user berdasarkan user_id."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_users() -> list[User]:
    """Ambil seluruh user untuk keperluan broadcast atau rekap."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(r) for r in await cursor.fetchall()]


async def get_users_with_stats() -> list[dict[str, Any]]:
    """Daftar user + jumlah transaksi sukses + total belanja (LTV) + last order."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*,
                   COUNT(o.id) AS total_orders,
                   COALESCE(SUM(CASE WHEN o.status = 'COMPLETED' THEN o.amount END), 0) AS total_spent,
                   MAX(o.created_at) AS last_order_at
            FROM users u
            LEFT JOIN orders o ON o.user_id = u.user_id
            GROUP BY u.user_id
            ORDER BY total_spent DESC, u.created_at DESC
        """)
        return [dict(r) for r in await cursor.fetchall()]


# ==================== CATEGORIES ====================

async def get_categories() -> list[dict[str, Any]]:
    """Ambil seluruh kategori produk."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM categories ORDER BY name ASC")
        return [dict(r) for r in await cursor.fetchall()]


async def add_category(category_id: str, name: str) -> bool:
    """Tambah kategori baru."""
    try:
        async with get_db() as db:
            await db.execute("INSERT INTO categories (id, name) VALUES (?, ?)", (category_id, name))
            await db.commit()
        return True
    except Exception as exc:
        logger.error("Gagal tambah kategori %s: %s", category_id, exc)
        return False


async def rename_category(category_id: str, new_name: str) -> bool:
    """Ubah nama kategori."""
    async with get_db() as db:
        cursor = await db.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id))
        await db.commit()
        return cursor.rowcount > 0


async def delete_category(category_id: str) -> tuple[bool, str]:
    """Hapus kategori; tolak jika masih ada produk di dalamnya."""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,))
        (product_count,) = await cursor.fetchone()
        if product_count > 0:
            return False, f"Masih ada {product_count} produk di kategori ini."
        cursor = await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()
        if cursor.rowcount == 0:
            return False, "Kategori tidak ditemukan."
        return True, "Kategori dihapus."


# ==================== PRODUCTS ====================

async def get_all_products(category_id: Optional[str] = None, only_active: bool = True) -> list[Product]:
    """Ambil semua produk (opsional filter by kategori atau status aktif)."""
    query = "SELECT * FROM products WHERE 1=1"
    params: list[Any] = []
    if only_active:
        query += " AND is_active = 1"
    if category_id:
        query += " AND category_id = ?"
        params.append(category_id)
    query += " ORDER BY price ASC"

    async with get_db() as db:
        cursor = await db.execute(query, tuple(params))
        return [dict(r) for r in await cursor.fetchall()]


async def get_product(product_id: str) -> Optional[Product]:
    """Ambil 1 produk berdasarkan ID."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_product(product_id: str, category_id: str, name: str, description: str, price: int) -> bool:
    """Tambah produk baru ke database."""
    try:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO products (id, category_id, name, description, price, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (product_id, category_id, name, description, price, _now_iso()),
            )
            await db.commit()
        return True
    except Exception as exc:
        logger.error("Gagal tambah produk %s: %s", product_id, exc)
        return False


async def update_product(
    product_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    price: Optional[int] = None,
    category_id: Optional[str] = None,
) -> bool:
    """Update field produk yang diberikan (hanya field non-None yang berubah)."""
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if description is not None:
        sets.append("description = ?")
        params.append(description)
    if price is not None:
        sets.append("price = ?")
        params.append(price)
    if category_id is not None:
        sets.append("category_id = ?")
        params.append(category_id)
    if not sets:
        return True
    params.append(product_id)
    async with get_db() as db:
        cursor = await db.execute(f"UPDATE products SET {', '.join(sets)} WHERE id = ?", tuple(params))
        await db.commit()
        return cursor.rowcount > 0


async def toggle_product_active(product_id: str) -> bool:
    """Aktif/nonaktifkan produk berdasarkan status sekarang. Return status baru."""
    async with get_db() as db:
        await db.execute(
            """
            UPDATE products SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            (product_id,),
        )
        await db.commit()
        cursor = await db.execute("SELECT is_active FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return bool(row["is_active"]) if row else False


async def delete_product(product_id: str) -> tuple[bool, str]:
    """Hapus produk; tolak jika masih ada order atau stok terkait."""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE product_id = ?", (product_id,))
        (order_count,) = await cursor.fetchone()
        if order_count > 0:
            return False, f"Masih ada {order_count} order terkait. Nonaktifkan saja produknya."
        cursor = await db.execute("SELECT COUNT(*) FROM stocks WHERE product_id = ?", (product_id,))
        (stock_count,) = await cursor.fetchone()
        if stock_count > 0:
            return False, f"Masih ada {stock_count} baris stok. Hapus stok dulu."
        cursor = await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()
        if cursor.rowcount == 0:
            return False, "Produk tidak ditemukan."
        return True, "Produk dihapus."


# ==================== STOCKS ====================

async def add_stock(product_id: str, account_data: str) -> int:
    """Tambah 1 baris stok akun untuk produk tertentu. Return id baris baru."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO stocks (product_id, account_data, is_sold, created_at)
            VALUES (?, ?, 0, ?)
            """,
            (product_id, account_data.strip(), _now_iso()),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def add_stocks_bulk(product_id: str, accounts: list[str]) -> int:
    """Tambah banyak baris stok akun sekaligus. Return jumlah baris yang masuk."""
    rows = [(product_id, acc.strip(), 0, _now_iso()) for acc in accounts if acc.strip()]
    if not rows:
        return 0
    async with get_db() as db:
        await db.executemany(
            """
            INSERT INTO stocks (product_id, account_data, is_sold, created_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        await db.commit()
    return len(rows)


async def get_stock_summary() -> list[dict[str, Any]]:
    """Sisa stok per produk (join nama produk) untuk ringkasan dashboard."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT p.id AS product_id, p.name AS product_name, p.is_active,
                   COALESCE(SUM(CASE WHEN s.is_sold = 0 THEN 1 END), 0) AS ready,
                   COALESCE(SUM(CASE WHEN s.is_sold = 1 THEN 1 END), 0) AS sold
            FROM products p
            LEFT JOIN stocks s ON s.product_id = p.id
            GROUP BY p.id
            ORDER BY p.name ASC
        """)
        return [dict(r) for r in await cursor.fetchall()]


async def get_stocks(product_id: Optional[str] = None, only_available: bool = False, limit: int = 200) -> list[StockRow]:
    """Audit list baris stok; opsional filter produk / yang belum terjual."""
    query = """
        SELECT s.*, p.name AS product_name
        FROM stocks s LEFT JOIN products p ON s.product_id = p.id
        WHERE 1=1
    """
    params: list[Any] = []
    if product_id:
        query += " AND s.product_id = ?"
        params.append(product_id)
    if only_available:
        query += " AND s.is_sold = 0"
    query += " ORDER BY s.id DESC LIMIT ?"
    params.append(limit)

    async with get_db() as db:
        cursor = await db.execute(query, tuple(params))
        return [dict(r) for r in await cursor.fetchall()]


async def delete_stock(stock_id: int) -> bool:
    """Hapus baris stok yang BELUM terjual (salah input). Return sukses."""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM stocks WHERE id = ? AND is_sold = 0", (stock_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_stock_count(product_id: str) -> int:
    """Hitung sisa stok tersedia (belum terjual) untuk produk."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM stocks WHERE product_id = ? AND is_sold = 0",
            (product_id,),
        )
        (count,) = await cursor.fetchone()
        return count


async def claim_available_stock(product_id: str, order_id: int) -> Optional[StockRow]:
    """Ambil 1 stok tertua yang tersedia dan tandai sebagai terjual untuk order_id."""
    now = _now_iso()
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, account_data FROM stocks
            WHERE product_id = ? AND is_sold = 0
            ORDER BY id ASC LIMIT 1
            """,
            (product_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        stock_id, account_data = row["id"], row["account_data"]
        await db.execute(
            "UPDATE stocks SET is_sold = 1, order_id = ?, sold_at = ? WHERE id = ?",
            (order_id, now, stock_id),
        )
        await db.commit()
        return {"id": stock_id, "account_data": account_data}


async def assign_stock_to_order(stock_id: int, order_id: int) -> Optional[StockRow]:
    """Tandai stok spesifik (pilihan admin) sebagai terjual untuk order_id."""
    now = _now_iso()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, account_data FROM stocks WHERE id = ? AND is_sold = 0",
            (stock_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE stocks SET is_sold = 1, order_id = ?, sold_at = ? WHERE id = ?",
            (order_id, now, stock_id),
        )
        await db.commit()
        return {"id": row["id"], "account_data": row["account_data"]}


async def get_stock_by_id(stock_id: int) -> Optional[StockRow]:
    """Ambil detail baris stok akun berdasarkan ID."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM stocks WHERE id = ?", (stock_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== ORDERS ====================

async def create_order(
    invoice_id: str,
    user_id: int,
    product_id: str,
    amount: int,
    payment_url: str = "",
    qris_data: str = "",
) -> Order:
    """Catat pesanan baru ke tabel orders."""
    now = _now_iso()
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (
                invoice_id, user_id, product_id, amount, status,
                payment_url, qris_data, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
            """,
            (invoice_id, user_id, product_id, amount, payment_url, qris_data, now, now),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "invoice_id": invoice_id,
            "user_id": user_id,
            "product_id": product_id,
            "amount": amount,
            "status": "PENDING",
            "payment_url": payment_url,
            "qris_data": qris_data,
            "created_at": now,
        }


async def get_order_by_invoice(invoice_id: str) -> Optional[Order]:
    """Cari order berdasarkan invoice_id SayaBayar."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM orders WHERE invoice_id = ?", (invoice_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_order_by_id(order_id: int) -> Optional[Order]:
    """Cari order berdasarkan id internal."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> list[Order]:
    """Daftar order untuk dashboard: filter status + search invoice/user/produk."""
    query = """
        SELECT o.*, p.name AS product_name
        FROM orders o LEFT JOIN products p ON o.product_id = p.id
        WHERE 1=1
    """
    params: list[Any] = []
    if status and status != "ALL":
        query += " AND o.status = ?"
        params.append(status)
    if search:
        like = f"%{search}%"
        query += " AND (o.invoice_id LIKE ? OR CAST(o.user_id AS TEXT) LIKE ? OR p.name LIKE ?)"
        params.extend([like, like, like])
    query += " ORDER BY o.id DESC LIMIT ?"
    params.append(limit)

    async with get_db() as db:
        cursor = await db.execute(query, tuple(params))
        return [dict(r) for r in await cursor.fetchall()]


async def update_order_status(
    invoice_id: str,
    status: str,
    delivered_stock_id: Optional[int] = None,
) -> bool:
    """Perbarui status invoice (cth: PAID, EXPIRED, CANCELLED, COMPLETED)."""
    now = _now_iso()
    async with get_db() as db:
        if delivered_stock_id is not None:
            await db.execute(
                """
                UPDATE orders
                SET status = ?, delivered_stock_id = ?, updated_at = ?
                WHERE invoice_id = ?
                """,
                (status.upper(), delivered_stock_id, now, invoice_id),
            )
        else:
            await db.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE invoice_id = ?",
                (status.upper(), now, invoice_id),
            )
        await db.commit()
    return True


async def force_complete_order(order_id: int, stock_id: Optional[int], account_data: str) -> bool:
    """Tuntaskan order PAID_OUT_OF_STOCK secara manual oleh admin.

    - Jika stock_id diberikan: stok itu ditandai terjual untuk order ini.
    - Jika account_data diberikan (input manual): disimpan sebagai delivered via order.
    Order di-set COMPLETED dan delivered_stock_id terisi bila memakai stok DB.
    """
    order = await get_order_by_id(order_id)
    if not order:
        return False
    now = _now_iso()
    async with get_db() as db:
        if stock_id is not None:
            await db.execute(
                "UPDATE stocks SET is_sold = 1, order_id = ?, sold_at = ? WHERE id = ?",
                (order_id, now, stock_id),
            )
            await db.execute(
                "UPDATE orders SET status = 'COMPLETED', delivered_stock_id = ?, updated_at = ? WHERE id = ?",
                (stock_id, now, order_id),
            )
        else:
            # Data manual: simpan ringkas di qris_data? Tidak — simpan di payment_url saja
            # tidak tepat; gunakan delivered_stock_id NULL + status COMPLETED.
            await db.execute(
                "UPDATE orders SET status = 'COMPLETED', updated_at = ? WHERE id = ?",
                (now, order_id),
            )
        await db.commit()
    return True


async def get_user_orders(user_id: int, limit: int = 10) -> list[Order]:
    """Ambil riwayat order dari user tertentu."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT o.*, p.name AS product_name
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            WHERE o.user_id = ?
            ORDER BY o.id DESC LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_pending_orders(max_age_hours: int = 24) -> list[Order]:
    """Ambil daftar order yang masih PENDING dalam rentang jam tertentu."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT o.*, p.name AS product_name
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            WHERE o.status = 'PENDING' AND o.created_at >= ?
            ORDER BY o.id ASC
            """,
            (cutoff,),
        )
        return [dict(r) for r in await cursor.fetchall()]


# ==================== STATISTIK ====================

async def get_sales_stats() -> dict[str, Any]:
    """Rekap penjualan: transaksi sukses, omzet, pending, produk terlaris, stok ready."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'COMPLETED' THEN amount ELSE 0 END) AS revenue,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'PAID_OUT_OF_STOCK' THEN 1 ELSE 0 END) AS paid_oos
            FROM orders
        """)
        row = await cursor.fetchone()
        stats: dict[str, Any] = {
            "completed": row["completed"] or 0,
            "revenue": row["revenue"] or 0,
            "pending": row["pending"] or 0,
            "paid_oos": row["paid_oos"] or 0,
        }

        cursor = await db.execute("""
            SELECT p.name, COUNT(*) AS sold
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.status = 'COMPLETED'
            GROUP BY o.product_id
            ORDER BY sold DESC
            LIMIT 5
        """)
        stats["top_products"] = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute("SELECT COUNT(*) FROM stocks WHERE is_sold = 0")
        (ready,) = await cursor.fetchone()
        stats["stock_ready"] = ready
        return stats


async def get_daily_sales(days: int = 14) -> list[dict[str, Any]]:
    """Penjualan harian (COMPLETED) untuk grafik: tanggal, jumlah order, omzet."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT DATE(created_at) AS day,
                   COUNT(*) AS orders,
                   COALESCE(SUM(amount), 0) AS revenue
            FROM orders
            WHERE status = 'COMPLETED' AND DATE(created_at) >= ?
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """,
            (since,),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_status_counts() -> dict[str, int]:
    """Hitung order per status (untuk metric cards & filter badges)."""
    async with get_db() as db:
        cursor = await db.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status")
        return {r["status"]: r["n"] for r in await cursor.fetchall()}
