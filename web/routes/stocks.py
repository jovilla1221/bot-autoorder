"""Routes manajemen stok: ringkasan, bulk restock, audit list, hapus, export."""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from bot.database import crud
from web.activity import log_event
from web.deps import base_context, guard_api, require_login_page
from web.templating import templates

router = APIRouter()


def mask_account(data: str) -> str:
    """Samarkan isi akun untuk tampilan audit (mis. abcd:****)."""
    if ":" in data:
        head, _, tail = data.partition(":")
        return f"{head[:2]}{'*' * max(len(head) - 2, 2)}:{tail[:1]}{'*' * max(len(tail) - 1, 2)}"
    return f"{data[:3]}{'*' * max(len(data) - 3, 2)}"


@router.get("/stocks", response_class=HTMLResponse)
async def stocks_page(request: Request, product: Optional[str] = None):
    redirect = require_login_page(request)
    if redirect:
        return redirect
    products = await crud.get_all_products(only_active=False)
    summary = await crud.get_stock_summary()
    stocks = await crud.get_stocks(product_id=product, limit=300)
    return templates.TemplateResponse(request, "stocks.html", base_context(
        request, products=products, summary=summary, stocks=stocks, mask=mask_account,
        selected_product=product,
    ))


class BulkStockPayload(BaseModel):
    product_id: str
    accounts: str  # textarea: 1 akun per baris
    dedup: bool = True


@router.post("/api/stocks/bulk")
async def api_bulk_stock(request: Request):
    async def run(form_data: BulkStockPayload) -> dict:
        lines = [ln.strip() for ln in form_data.accounts.splitlines() if ln.strip()]
        skipped = 0
        if form_data.dedup:
            existing = {s["account_data"] for s in await crud.get_stocks(
                product_id=form_data.product_id, only_available=True, limit=100000,
            )}
            unique_lines: list[str] = []
            seen: set[str] = set()
            for ln in lines:
                if ln in existing or ln in seen:
                    skipped += 1
                    continue
                seen.add(ln)
                unique_lines.append(ln)
            lines = unique_lines
        added = await crud.add_stocks_bulk(form_data.product_id, lines)
        total = await crud.get_stock_count(form_data.product_id)
        log_event("info", "stock", f"Restock {added} akun untuk {form_data.product_id} (skip duplikat {skipped})")
        return {"added": added, "skipped_duplicates": skipped, "total_ready": total}

    result = await guard_api_json(request, run)
    return JSONResponse(result["json"], status_code=result["status"])


async def guard_api_json(request: Request, handler):
    """guard_api dengan parse JSON body + CSRF dari header."""
    from web.auth import is_logged_in, verify_csrf
    import json as _json

    if not is_logged_in(request):
        return {"json": {"error": "unauthorized"}, "status": 401}
    raw = await request.body()
    payload = _json.loads(raw) if raw else {}
    if not verify_csrf(request, request.headers.get("x-csrf-token")):
        return {"json": {"error": "csrf_invalid"}, "status": 403}
    result = await handler(BulkStockPayload(**payload))
    return {"json": result, "status": 200}


class DeleteStockPayload(BaseModel):
    stock_id: int


@router.post("/api/stocks/delete")
async def api_delete_stock(request: Request):
    async def run(payload: DeleteStockPayload) -> dict:
        ok = await crud.delete_stock(payload.stock_id)
        if ok:
            log_event("info", "stock", f"Stok #{payload.stock_id} dihapus admin")
            return {"ok": True}
        return {"ok": False, "message": "Stok tidak ditemukan / sudah terjual (tidak bisa dihapus)."}

    result = await _json_guard(request, payload_model=DeleteStockPayload, handler=lambda p: run(p))
    return JSONResponse(result["json"], status_code=result["status"])


class UpdateStockPayload(BaseModel):
    stock_id: int
    account_data: str
    product_id: str


@router.post("/api/stocks/update")
async def api_update_stock(request: Request):
    async def run(payload: UpdateStockPayload) -> dict:
        ok, message = await crud.update_stock(
            stock_id=payload.stock_id,
            account_data=payload.account_data,
            product_id=payload.product_id,
        )
        if ok:
            log_event("info", "stock", f"Stok #{payload.stock_id} diupdate admin")
            return {"ok": True, "message": message}
        return {"ok": False, "message": message}

    result = await _json_guard(request, payload_model=UpdateStockPayload, handler=run)
    return JSONResponse(result["json"], status_code=result["status"])


async def _json_guard(request: Request, payload_model, handler):
    """Generic JSON POST guard: login + CSRF + parse body ke pydantic model."""
    import json as _json
    from web.auth import is_logged_in, verify_csrf

    if not is_logged_in(request):
        return {"json": {"error": "unauthorized"}, "status": 401}
    raw = await request.body()
    try:
        data = _json.loads(raw) if raw else {}
        payload = payload_model(**data)
    except Exception:
        return {"json": {"error": "bad_request"}, "status": 400}
    if not verify_csrf(request, request.headers.get("x-csrf-token")):
        return {"json": {"error": "csrf_invalid"}, "status": 403}
    result = await handler(payload)
    return {"json": result, "status": 200}


@router.get("/export/stocks")
async def export_stocks(request: Request, product: Optional[str] = None, fmt: str = "csv"):
    """Export sisa stok (belum terjual) ke txt/csv."""
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    stocks = await crud.get_stocks(product_id=product, only_available=True, limit=100000)
    filename = f"stocks-{product or 'all'}.{fmt}"
    if fmt == "txt":
        content = "\n".join(s["account_data"] for s in stocks)
        return StreamingResponse(
            io.StringIO(content),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["stock_id", "product_id", "product_name", "account_data", "created_at"])
    for s in stocks:
        writer.writerow([s["id"], s["product_id"], s.get("product_name", ""), s["account_data"], s["created_at"]])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
