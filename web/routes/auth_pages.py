"""Routes auth dashboard: login page, login action, logout."""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.activity import log_event
from web.auth import (
    check_password,
    clear_session_cookie,
    is_rate_limited,
    record_failed_attempt,
    reset_attempts,
    set_session_cookie,
)
from web.deps import base_context
from web.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if check_password("") is False and request.cookies.get("dash_session"):
        pass  # tetap tampilkan login; verify dilakukan di POST
    return templates.TemplateResponse(request, "login.html", base_context(request, error=None))


@router.post("/login")
async def login_action(request: Request, password: str = Form(...)):
    if is_rate_limited(request):
        log_event("warning", "auth", f"Login diblokir rate-limit dari IP {request.client.host if request.client else '?'}")
        return templates.TemplateResponse(
            request, "login.html",
            base_context(request, error="Terlalu banyak percobaan gagal. Coba lagi dalam beberapa menit."),
            status_code=429,
        )
    if not check_password(password):
        record_failed_attempt(request)
        log_event("warning", "auth", "Percobaan login gagal")
        return templates.TemplateResponse(
            request, "login.html",
            base_context(request, error="Password salah."),
            status_code=401,
        )
    reset_attempts(request)
    response = RedirectResponse(url="/", status_code=303)
    set_session_cookie(response)
    log_event("info", "auth", "Login dashboard berhasil")
    return response


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response)
    return response
