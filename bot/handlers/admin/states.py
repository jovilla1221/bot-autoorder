"""Definisi FSM states untuk seluruh flow admin."""
from aiogram.fsm.state import State, StatesGroup


class AddStockFSM(StatesGroup):
    """Flow tambah stok massal: pilih produk → input daftar akun."""
    input_stock = State()


class AddProductFSM(StatesGroup):
    """Flow tambah produk baru: id → nama → harga → deskripsi."""
    input_id = State()
    input_name = State()
    input_price = State()
    input_desc = State()


class BroadcastFSM(StatesGroup):
    """Flow broadcast: tulis pesan."""
    input_message = State()
