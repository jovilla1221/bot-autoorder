"""Routes dashboard utama: stats, grafik, health monitor, backup DB."""
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from bot.config import DB_PATH, WEB_ADMIN_PASSWORD
from bot.database import crud
from web.activity import log_event, recent_events
from web.auth import is_logged_in, verify_csrf
from web.bot_bridge import is_integrated
from web.deps import base_context, require_login_page
from web.templating import templates

router = APIRouter()


async def _dashboard_data() -> dict:
    stats = await crud.get_sales_stats()
    status_counts = await crud.get_status_counts()
    daily = await crud.get_daily_sales(days=14)
    stock_summary = await crud.get_stock_summary()
    attention = await crud.list_orders(status="PAID_OUT_OF_STOCK", limit=10)
    return {
        "stats": stats,
        "status_counts": status_counts,
        "daily": daily,
        "stock_summary": stock_summary,
        "attention": attention,
        "activities": recent_events(30),
        "bot_integrated": is_integrated(),
        "password_default": WEB_ADMIN_PASSWORD == "admin123",
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    redirect = require_login_page(request)
    if redirect:
        return redirect
    data = await _dashboard_data()
    return templates.TemplateResponse(request, "dashboard.html", base_context(request, **data))


@router.get("/api/stats")
async def api_stats(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {
        "stats": await crud.get_sales_stats(),
        "status_counts": await crud.get_status_counts(),
        "daily": await crud.get_daily_sales(days=14),
    }


@router.get("/api/activities")
async def api_activities(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"events": recent_events(50)}


@router.get("/download/backup")
async def download_backup(request: Request):
    """Download snapshot database.sqlite3 (admin only)."""
    if not is_logged_in(request) or not verify_csrf(request, request.query_params.get("csrf_token")):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_name = f"database-{stamp}.sqlite3"
    tmp_path = f"/tmp/{backup_name}"
    shutil.copy2(DB_PATH, tmp_path)
    log_event("info", "backup", f"Database diunduh ({backup_name})")
    return FileResponse(tmp_path, filename=backup_name, media_type="application/octet-stream")
