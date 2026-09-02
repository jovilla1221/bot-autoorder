"""Autentikasi dashboard: password login, session HMAC, CSRF, brute-force guard."""
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Request, Response

from bot.config import WEB_ADMIN_PASSWORD, WEB_LOGIN_MAX_ATTEMPTS, WEB_LOGIN_WINDOW_SECONDS
from bot.utils.secret import get_or_create_web_secret

SESSION_COOKIE = "dash_session"
CSRF_SESSION_KEY = "csrf_token"
SESSION_TTL_SECONDS = 12 * 3600  # 12 jam

# ==================== BRUTE FORCE GUARD ====================

_failed_attempts: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=50))


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_rate_limited(request: Request) -> bool:
    """True jika IP melewati batas percobaan login gagal."""
    ip = _client_ip(request)
    now = time.time()
    attempts = _failed_attempts[ip]
    while attempts and now - attempts[0] > WEB_LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    return len(attempts) >= WEB_LOGIN_MAX_ATTEMPTS


def record_failed_attempt(request: Request) -> None:
    _failed_attempts[_client_ip(request)].append(time.time())


def reset_attempts(request: Request) -> None:
    _failed_attempts.pop(_client_ip(request), None)


# ==================== SESSION (HMAC-signed token) ====================

def _sign(payload: str) -> str:
    key = get_or_create_web_secret().encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    """Token format: {random}.{expiry_epoch}.{hmac}"""
    nonce = secrets.token_hex(16)
    expiry = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{nonce}.{expiry}"
    return f"{payload}.{_sign(payload)}"


def verify_session_token(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        nonce, expiry_str, signature = token.split(".")
    except ValueError:
        return False
    payload = f"{nonce}.{expiry_str}"
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    try:
        expiry = int(expiry_str)
    except ValueError:
        return False
    return expiry > time.time()


def set_session_cookie(response: Response) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def is_logged_in(request: Request) -> bool:
    return verify_session_token(request.cookies.get(SESSION_COOKIE))


# ==================== CSRF ====================

def get_csrf_token(request: Request) -> str:
    """CSRF token deterministik per session: HMAC(secret, session_token)."""
    session = request.cookies.get(SESSION_COOKIE, "")
    return _sign(f"csrf:{session}")


def verify_csrf(request: Request, submitted: Optional[str]) -> bool:
    if not submitted:
        return False
    expected = get_csrf_token(request)
    return hmac.compare_digest(submitted, expected)


def check_password(password: str) -> bool:
    return hmac.compare_digest(password, WEB_ADMIN_PASSWORD)
