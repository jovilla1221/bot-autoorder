"""Dependencies & helper bersama untuk routes dashboard."""
from typing import Any, Awaitable, Callable

from fastapi import Request
from fastapi.responses import RedirectResponse

from web.auth import is_logged_in, verify_csrf
from web.templating import templates


def require_login_page(request: Request) -> RedirectResponse | None:
    """Untuk halaman HTML: redirect ke /login jika belum login."""
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def require_login_api(request: Request) -> dict | None:
    """Untuk endpoint API: 401 JSON jika belum login."""
    if not is_logged_in(request):
        return {"error": "unauthorized"}
    return None


async def guard_api(request: Request, handler: Callable[[], Awaitable[Any]]) -> Any:
    """Cek login + CSRF (form POST) lalu jalankan handler.

    Return unauthorized response tuple jika gagal, hasil handler jika lolos.
    """
    if not is_logged_in(request):
        return {"json": {"error": "unauthorized"}, "status": 401}
    form = None
    if request.method == "POST":
        form = await request.form()
        if not verify_csrf(request, form.get("csrf_token") or request.headers.get("x-csrf-token")):
            return {"json": {"error": "csrf_invalid"}, "status": 403}
    result = await handler(form)
    return {"json": result, "status": 200}


def base_context(request: Request, **extra: Any) -> dict:
    ctx = {
        "request": request,
        "csrf_token": None,
    }
    from web.auth import get_csrf_token

    if is_logged_in(request):
        ctx["csrf_token"] = get_csrf_token(request)
    ctx.update(extra)
    return ctx
