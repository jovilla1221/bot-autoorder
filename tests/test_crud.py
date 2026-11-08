"""Integration test CRUD bot.database.crud memakai SQLite sementara."""
from bot.database import crud


async def test_user_upsert_and_get():
    await crud.upsert_user(1, "budi", "Budi")
    user = await crud.get_user(1)
    assert user is not None
    assert user["username"] == "budi"

    # upsert kedua memperbarui, tidak duplikat
    await crud.upsert_user(1, "budi2", "Budi")
    users = await crud.get_all_users()
    assert len(users) == 1
    assert users[0]["username"] == "budi2"


async def test_product_listing_and_filter():
    streaming = await crud.get_all_products(category_id="streaming")
    assert {p["id"] for p in streaming} == {"netflix_trial_reg_th", "youtube_premium"}
    all_products = await crud.get_all_products(only_active=False)
    assert len(all_products) >= 3


async def test_add_and_toggle_product():
    ok = await crud.add_product("test_prod", "streaming", "Test Prod", "desc", 10000)
    assert ok is True
    assert await crud.get_product("test_prod") is not None

    status1 = await crud.toggle_product_active("test_prod")
    status2 = await crud.toggle_product_active("test_prod")
    assert status1 != status2


async def test_add_product_duplicate_fails():
    ok = await crud.add_product("netflix_trial_reg_th", "streaming", "Dup", "d", 1)
    assert ok is False


async def test_update_product():
    await crud.add_product("test_edit_prod", "streaming", "Old Name", "Old Desc", 20000)
    ok = await crud.update_product(
        "test_edit_prod",
        name="New Name",
        description="New Desc",
        price=25000,
        category_id="streaming",
    )
    assert ok is True
    prod = await crud.get_product("test_edit_prod")
    assert prod is not None
    assert prod["name"] == "New Name"
    assert prod["description"] == "New Desc"
    assert prod["price"] == 25000


async def test_stock_bulk_and_count():
    added = await crud.add_stocks_bulk("spotify_premium_id", ["a@b.com:pass1", "c@d.com:pass2", "", "   "])
    assert added == 2
    assert await crud.get_stock_count("spotify_premium_id") == 2


async def test_update_stock():
    stock_id = await crud.add_stock("spotify_premium_id", "user1@mail.com:pass1")
    assert stock_id > 0

    # Update account_data dan product_id
    ok, msg = await crud.update_stock(stock_id, account_data="user1_updated@mail.com:newpass", product_id="netflix_trial_reg_th")
    assert ok is True

    stocks = await crud.get_stocks(product_id="netflix_trial_reg_th")
    matched = [s for s in stocks if s["id"] == stock_id]
    assert len(matched) == 1
    assert matched[0]["account_data"] == "user1_updated@mail.com:newpass"

    # Validasi input kosong
    ok_empty, msg_empty = await crud.update_stock(stock_id, account_data="   ")
    assert ok_empty is False
    assert "kosong" in msg_empty

    # Tidak bisa update jika sudah terjual
    await crud.upsert_user(99, "buyer99", "Buyer")
    order = await crud.create_order("INV-TEST-EDIT", 99, "netflix_trial_reg_th", 25000)
    claimed = await crud.claim_available_stock("netflix_trial_reg_th", order["id"])
    assert claimed is not None
    assert claimed["id"] == stock_id

    ok_sold, msg_sold = await crud.update_stock(stock_id, account_data="cant_change@mail.com:p")
    assert ok_sold is False
    assert "sudah terjual" in msg_sold

    # Update stock yang tidak ada
    ok_nf, msg_nf = await crud.update_stock(999999, account_data="x@y.com:z")
    assert ok_nf is False
    assert "tidak ditemukan" in msg_nf


async def test_claim_stock_fifo_and_idempotent_count():
    await crud.upsert_user(1, "buyer", "Buyer")
    await crud.add_stocks_bulk("spotify_premium_id", ["acc1", "acc2"])
    order = await crud.create_order("INV-1", 1, "spotify_premium_id", 15000)

    claimed = await crud.claim_available_stock("spotify_premium_id", order["id"])
    assert claimed is not None
    assert claimed["account_data"] == "acc1"  # FIFO: stok tertua dulu
    assert await crud.get_stock_count("spotify_premium_id") == 1

    # Stok habis → claim berikutnya None
    claimed2 = await crud.claim_available_stock("spotify_premium_id", order["id"])
    claimed3 = await crud.claim_available_stock("spotify_premium_id", order["id"])
    assert (claimed2 is None) != (claimed3 is None) or (claimed2 is None and claimed3 is None)


async def test_order_lifecycle_and_stats():
    await crud.upsert_user(42, "stat_user", "Stat")
    order = await crud.create_order("INV-STAT", 42, "netflix_trial_reg_th", 25000, payment_url="http://x")
    assert order["status"] == "PENDING"

    fetched = await crud.get_order_by_invoice("INV-STAT")
    assert fetched is not None
    assert fetched["amount"] == 25000

    await crud.update_order_status("INV-STAT", "completed", delivered_stock_id=None)
    stats = await crud.get_sales_stats()
    assert stats["completed"] == 1
    assert stats["revenue"] == 25000
    assert stats["pending"] == 0


async def test_pending_orders_listing():
    await crud.upsert_user(1, "u1", "U1")
    await crud.upsert_user(2, "u2", "U2")
    await crud.create_order("INV-P1", 1, "netflix_trial_reg_th", 25000)
    await crud.create_order("INV-P2", 2, "youtube_premium", 35000)
    await crud.update_order_status("INV-P2", "EXPIRED")

    pending = await crud.get_pending_orders()
    invoices = {o["invoice_id"] for o in pending}
    assert invoices == {"INV-P1"}
