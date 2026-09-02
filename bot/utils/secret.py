"""Secret key management untuk signing session dashboard web."""
import os
import secrets

SECRET_FILE = ".web_secret"


def get_or_create_web_secret() -> str:
    """Ambil WEB_SECRET dari env, atau generate & simpan ke file .web_secret."""
    from bot.config import WEB_SECRET

    if WEB_SECRET:
        return WEB_SECRET
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "r", encoding="utf-8") as f:
            secret = f.read().strip()
            if secret:
                return secret
    secret = secrets.token_hex(32)
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(secret)
    return secret
