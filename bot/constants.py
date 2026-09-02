"""Konstanta bersama untuk seluruh aplikasi.

Pusat definisi status pembayaran dan konstanta domain lain,
agar tidak ada duplikasi antar modul.
"""

# Status yang dianggap "lunas" oleh gateway SayaBayar
PAID_STATUSES: frozenset[str] = frozenset({"PAID", "SUCCESS", "SETTLED", "COMPLETED"})

# Status akhir (invoice tidak akan berubah lagi)
TERMINAL_STATUSES: frozenset[str] = frozenset({"EXPIRED", "CANCELLED", "FAILED"})

# Kategori default untuk produk baru yang dibuat lewat panel admin
DEFAULT_CATEGORY_ID: str = "streaming"
