"""Routes manajemen pesanan: monitor, sync gateway, manual fulfillment, force cancel."""
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from bot.constants import PAID_STATUSES
from bot.database import crud
from bot.services.fulfillment import deliver_account_manually, process_order_fulfillment
from bot.utils.sayabayar import client, parse_invoice_status
from web.activity import log_event
from web.bot_bridge import get_bot
from web.deps import base_context, require_login_page
from web.routes.stocks import _json_guard
from web.templating import templates

router = APIRouter()

STATUS_FILTERS = ["ALL", "PENDING", "PAID", "COMPLETED", "PAID_OUT_OF_STOCK", "AMOUNT_MISMATCH", "CANCELLED", "EXPIRED"]


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, status: str = "ALL", q: str = ""):
    redirect = require_login_page(request)
    if redirect:
        return redirect
    orders = await crud.list_orders(status=status if status != "ALL" else None, search=q or None, limit=200)
    counts = await crud.get_status_counts()
    return templates.TemplateResponse(request, "orders.html", base_context(
        request, orders=orders, status_filters=STATUS_FILTERS,
        selected_status=status, query=q, counts=counts,
    ))


@router.get("/api/orders")
async def api_orders(request: Request, status: str = "ALL", q: str = ""):
    from web.auth import is_logged_in

    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    orders = await crud.list_orders(status=status if status != "ALL" else None, search=q or None, limit=200)
    return {"orders": orders}


class SyncPayload(BaseModel):
    invoice_id: str


@router.post("/api/orders/sync")
async def api_sync_order(request: Request):
    """Sinkronkan status order dengan SayaBayar + verifikasi nominal."""
    async def run(p: SyncPayload) -> dict:
        order = await crud.get_order_by_invoice(p.invoice_id)
        if not order:
            return {"ok": False, "message": "Order tidak ditemukan di DB."}
        result = await client.check_status(p.invoice_id)
        if result["error"]:
            return {"ok": False, "message": f"Gateway error: {result['data']}"}
        data = result["data"]
        status = parse_invoice_status(data)
        if status in PAID_STATUSES:
            paid_amount = data.get("amount") or data.get("amount_unique")
            if paid_amount is not None and int(paid_amount) != int(order["amount"]):
                await crud.update_order_status(p.invoice_id, "AMOUNT_MISMATCH")
                log_event("error", "order", f"Nominal tidak cocok {p.invoice_id}: order={order['amount']} paid={paid_amount}")
                return {"ok": False, "message": f"NOMINAL TIDAK COCOK! order=Rp {order['amount']:,} vs paid=Rp {int(paid_amount):,}. Order ditandai AMOUNT_MISMATCH."}
            await process_order_fulfillment(get_bot(), p.invoice_id, paid_amount=paid_amount)
            fresh = await crud.get_order_by_invoice(p.invoice_id)
            log_event("info", "order", f"Invoice {p.invoice_id} lunas & difulfill")
            return {"ok": True, "order": fresh, "message": "Pembayaran terverifikasi & fulfillment diproses."}
        await crud.update_order_status(p.invoice_id, status)
        fresh = await crud.get_order_by_invoice(p.invoice_id)
        return {"ok": True, "order": fresh, "message": f"Status gateway: {status}"}

    result = await _json_guard(request, SyncPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


class FulfillPayload(BaseModel):
    order_id: int
    stock_id: Optional[int] = None
    account_data: Optional[str] = None


@router.post("/api/orders/fulfill")
async def api_fulfill_order(request: Request):
    """Manual fulfillment untuk PAID_OUT_OF_STOCK: kirim akun pilihan/manual."""
    async def run(p: FulfillPayload) -> dict:
        if p.stock_id is None and not (p.account_data or "").strip():
            return {"ok": False, "message": "Pilih stok ATAU isi data akun manual."}
        ok, message = await deliver_account_manually(
            get_bot(), p.order_id, p.account_data or "", stock_id=p.stock_id,
        )
        if ok:
            log_event("info", "order", f"Manual fulfillment order #{p.order_id}")
        return {"ok": ok, "message": message}

    result = await _json_guard(request, FulfillPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


class CancelPayload(BaseModel):
    invoice_id: str
    note: str = ""


@router.post("/api/orders/cancel")
async def api_cancel_order(request: Request):
    """Force cancel order lokal + coba hapus invoice di gateway."""
    async def run(p: CancelPayload) -> dict:
        order = await crud.get_order_by_invoice(p.invoice_id)
        if not order:
            return {"ok": False, "message": "Order tidak ditemukan."}
        if order["status"] == "COMPLETED":
            return {"ok": False, "message": "Order COMPLETED tidak bisa dibatalkan."}
        gateway_result = await client.cancel_invoice(p.invoice_id)
        await crud.update_order_status(p.invoice_id, "CANCELLED")
        log_event("warning", "order", f"Order {p.invoice_id} di-cancel admin. Note: {p.note or '-'}")
        gateway_msg = "Invoice gateway dihapus." if not gateway_result["error"] else f"Gateway: {gateway_result['data'].get('error', {}).get('message', 'gagal cancel')}"
        return {"ok": True, "message": f"Order di-CANCELLED. {gateway_msg}"}

    result = await _json_guard(request, CancelPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


@router.get("/api/orders/{order_id}/available-stocks")
async def api_available_stocks(request: Request, order_id: int):
    """Daftar stok tersedia untuk produk order tertentu (untuk dropdown fulfillment)."""
    from web.auth import is_logged_in

    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    order = await crud.get_order_by_id(order_id)
    if not order:
        return JSONResponse({"error": "not_found"}, status_code=404)
    stocks = await crud.get_stocks(product_id=order["product_id"], only_available=True, limit=100)
    return {"stocks": stocks}
