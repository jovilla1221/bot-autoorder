"""Routes manajemen produk & kategori (CRUD lengkap)."""
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from bot.database import crud
from web.activity import log_event
from web.deps import base_context, require_login_page
from web.routes.stocks import _json_guard
from web.templating import templates

router = APIRouter()


@router.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    redirect = require_login_page(request)
    if redirect:
        return redirect
    products = await crud.get_all_products(only_active=False)
    categories = await crud.get_categories()
    summary = {s["product_id"]: s for s in await crud.get_stock_summary()}
    return templates.TemplateResponse(request, "products.html", base_context(
        request, products=products, categories=categories, summary=summary,
    ))


class ProductPayload(BaseModel):
    product_id: Optional[str] = None
    category_id: str = "streaming"
    name: str
    description: str = ""
    price: int


@router.post("/api/products/add")
async def api_add_product(request: Request):
    async def run(p: ProductPayload) -> dict:
        if not p.product_id:
            return {"ok": False, "message": "ID produk wajib diisi."}
        created = await crud.add_product(
            product_id=p.product_id.strip().replace(" ", "_").lower(),
            category_id=p.category_id,
            name=p.name.strip(),
            description=p.description.strip(),
            price=p.price,
        )
        if created:
            log_event("info", "product", f"Produk baru: {p.name} (Rp {p.price:,})")
            return {"ok": True}
        return {"ok": False, "message": "Gagal tambah produk (ID duplikat / kategori tidak ada)."}

    result = await _json_guard(request, ProductPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


class ProductUpdatePayload(BaseModel):
    product_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    category_id: Optional[str] = None


@router.post("/api/products/update")
async def api_update_product(request: Request):
    async def run(p: ProductUpdatePayload) -> dict:
        name_val = p.name.strip() if p.name is not None else None
        if name_val is not None and not name_val:
            return {"ok": False, "message": "Nama produk tidak boleh kosong."}
        if p.price is not None and p.price < 0:
            return {"ok": False, "message": "Harga produk tidak boleh negatif."}
        desc_val = p.description.strip() if p.description is not None else None
        cat_val = p.category_id.strip() if p.category_id is not None else None

        ok = await crud.update_product(
            product_id=p.product_id,
            name=name_val,
            description=desc_val,
            price=p.price,
            category_id=cat_val,
        )
        if ok:
            log_event("info", "product", f"Produk {p.product_id} diupdate")
            return {"ok": True}
        return {"ok": False, "message": "Produk tidak ditemukan."}

    result = await _json_guard(request, ProductUpdatePayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


class TogglePayload(BaseModel):
    product_id: str


@router.post("/api/products/toggle")
async def api_toggle_product(request: Request):
    async def run(p: TogglePayload) -> dict:
        new_status = await crud.toggle_product_active(p.product_id)
        log_event("info", "product", f"Produk {p.product_id} → {'AKTIF' if new_status else 'NONAKTIF'}")
        return {"ok": True, "is_active": new_status}

    result = await _json_guard(request, TogglePayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


@router.post("/api/products/delete")
async def api_delete_product(request: Request):
    async def run(p: TogglePayload) -> dict:
        ok, message = await crud.delete_product(p.product_id)
        if ok:
            log_event("warning", "product", f"Produk {p.product_id} dihapus")
        return {"ok": ok, "message": message}

    result = await _json_guard(request, TogglePayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


# ==================== KATEGORI ====================

class CategoryPayload(BaseModel):
    category_id: Optional[str] = None
    name: str


@router.post("/api/categories/add")
async def api_add_category(request: Request):
    async def run(p: CategoryPayload) -> dict:
        cid = (p.category_id or p.name).strip().lower().replace(" ", "_")
        ok = await crud.add_category(cid, p.name.strip())
        if ok:
            log_event("info", "category", f"Kategori baru: {p.name}")
            return {"ok": True, "id": cid}
        return {"ok": False, "message": "Gagal tambah kategori (ID duplikat?)."}

    result = await _json_guard(request, CategoryPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


@router.post("/api/categories/rename")
async def api_rename_category(request: Request):
    async def run(p: CategoryPayload) -> dict:
        if not p.category_id:
            return {"ok": False, "message": "category_id wajib."}
        ok = await crud.rename_category(p.category_id, p.name.strip())
        return {"ok": ok, "message": "" if ok else "Kategori tidak ditemukan."}

    result = await _json_guard(request, CategoryPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])


@router.post("/api/categories/delete")
async def api_delete_category(request: Request):
    async def run(p: CategoryPayload) -> dict:
        if not p.category_id:
            return {"ok": False, "message": "category_id wajib."}
        ok, message = await crud.delete_category(p.category_id)
        if ok:
            log_event("warning", "category", f"Kategori {p.category_id} dihapus")
        return {"ok": ok, "message": message}

    result = await _json_guard(request, CategoryPayload, run)
    return JSONResponse(result["json"], status_code=result["status"])
