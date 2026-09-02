"""Shared pytest fixtures: database sementara per-test."""
import asyncio
import os

import pytest

# Set DB_PATH ke file test SEBELUM modul bot dimuat
TEST_DB = "test_database.sqlite3"
os.environ["DB_PATH"] = TEST_DB

from bot.database.db import get_db, init_db  # noqa: E402


@pytest.fixture()
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def fresh_db(event_loop):
    """DB baru untuk tiap test: init schema lalu hapus file setelah selesai."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()
    yield
    await asyncio.sleep(0)  # beri kesempatan koneksi async menutup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
