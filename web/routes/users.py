"""Routes manajemen user & broadcast engine."""
from aiogram.exceptions import TelegramForbiddenError

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from bot.database import crud
from web.activity import log_event
from web.bot_bridge import get_bot
from web.deps import base_context, require_login_page
from web.routes.stocks import _json_guard
from web.templating import templates

router = APIRouter()


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    redirect = require_login_page(request)
    if redirect:
        return redirect
    users = await crud.get_users_with_stats()
    return templates.TemplateResponse(request, "users.html", base_context(request, users=users))


# ==================== BROADCAST ====================

async def _broadcast_target_users(target: str) -> list[dict]:
    if target == "buyers":
        users = await crud.get_users_with_stats()
        return [u for u in users if (u.get("total_spent") or 0) > 0]
    return await crud.get_all_users()


class BroadcastPayload(BaseModel):
    message: str
    target: str = "all"  # all | buyers
    button_text: str = ""
    button_url: str = ""
    dry_run: bool = False


@router.post("/api/broadcast/preview")
async def api_broadcast_preview(request: Request):
    """Render preview HTML pesan (tanpa mengirim) — dipakai iframe inline."""
    async def run(p: BroadcastPayload) -> dict:
        return {"html": p.message}

    result = await _json_guard(request, BroadcastPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


@router.post("/api/broadcast/send")
async def api_broadcast_send(request: Request):
    """Kirim broadcast via bot. Return rekap terkirim/gagal."""
    async def run(p: BroadcastPayload) -> dict:
        if not p.message.strip():
            return {"ok": False, "message": "Pesan kosong."}
        users = await _broadcast_target_users(p.target)
        if p.dry_run:
            return {"ok": True, "dry_run": True, "recipients": len(users), "message": f"Preview: akan terkirim ke {len(users)} user."}

        bot = get_bot()
        sent = failed = 0
        errors: list[str] = []
        for u in users:
            try:
                if p.button_text and p.button_url:
                    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                    await bot.send_message(
                        u["user_id"], p.message, parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text=p.button_text, url=p.button_url)],
                        ]),
                    )
                else:
                    await bot.send_message(u["user_id"], p.message, parse_mode="HTML")
                sent += 1
            except TelegramForbiddenError:
                failed += 1
                errors.append(f"user {u['user_id']}: blocked bot")
            except Exception as exc:
                failed += 1
                errors.append(f"user {u['user_id']}: {exc}")
            import asyncio
            await asyncio.sleep(0.05)  # flood control
        log_event("info", "broadcast", f"Broadcast '{p.target}': {sent} terkirim, {failed} gagal")
        return {"ok": True, "sent": sent, "failed": failed, "errors": errors[:10]}

    result = await _json_guard(request, BroadcastPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])
