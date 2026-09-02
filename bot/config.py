import os
from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str) -> tuple[int, ...]:
    """Parse '1,2,3' menjadi tuple int; abaikan bagian kosong/non-numerik."""
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return tuple(ids)


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
FORCE_SUB_CHANNEL: str = os.getenv("FORCE_SUB_CHANNEL", "@reveuseress")
SAYABAYAR_API_KEY: str = os.getenv("SAYABAYAR_API_KEY", "")
SAYABAYAR_API_BASE: str = os.getenv("SAYABAYAR_API_BASE", "https://api.sayabayar.com/v1")
ADMIN_IDS: tuple[int, ...] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
DB_PATH: str = os.getenv("DB_PATH", "database.sqlite3")

# URL publik channel untuk tombol "Join Channel"
FORCE_SUB_URL: str = f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}"

# Fallback saat gateway tidak mengembalikan payment_url
FALLBACK_PAYMENT_URL: str = "https://sayabayar.com"

# ==================== WEB DASHBOARD ====================
WEB_ENABLED: bool = os.getenv("WEB_ENABLED", "1") == "1"
WEB_HOST: str = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))

# Password login dashboard (WAJIB diganti di produksi)
WEB_ADMIN_PASSWORD: str = os.getenv("WEB_ADMIN_PASSWORD", "admin123")

# Secret untuk signing session cookie (HMAC). Auto-generate & persist ke .web_secret
WEB_SECRET: str = os.getenv("WEB_SECRET", "")

# Login rate-limit: max percobaan gagal per window per IP
WEB_LOGIN_MAX_ATTEMPTS: int = int(os.getenv("WEB_LOGIN_MAX_ATTEMPTS", "5"))
WEB_LOGIN_WINDOW_SECONDS: int = int(os.getenv("WEB_LOGIN_WINDOW_SECONDS", "300"))
