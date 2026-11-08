"""Integration tests for web API endpoints (products & stocks edit)."""
import json
from starlette.requests import Request

from bot.database import crud
from web.auth import SESSION_COOKIE, _sign, create_session_token
from web.routes.products import api_update_product
from web.routes.stocks import api_update_stock


def _make_auth_request(path: str, data: dict) -> Request:
    token = create_session_token()
    csrf = _sign(f"csrf:{token}")
    body = json.dumps(data).encode()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [
            (b"content-type", b"application/json"),
            (b"x-csrf-token", csrf.encode()),
            (b"cookie", f"{SESSION_COOKIE}={token}".encode()),
        ],
    }
    return Request(scope, receive)


async def test_api_update_product_success():
    req = _make_auth_request(
        "/api/products/update",
        {
            "product_id": "netflix_trial_reg_th",
            "name": "Netflix Updated Via API",
            "price": 28000,
            "category_id": "streaming",
            "description": "Deskripsi baru",
        },
    )
    res = await api_update_product(req)
    assert res.status_code == 200
    data = json.loads(res.body.decode())
    assert data["ok"] is True

    prod = await crud.get_product("netflix_trial_reg_th")
    assert prod["name"] == "Netflix Updated Via API"
    assert prod["price"] == 28000
    assert prod["description"] == "Deskripsi baru"


async def test_api_update_product_validation():
    req = _make_auth_request(
        "/api/products/update",
        {
            "product_id": "netflix_trial_reg_th",
            "name": "   ",
        },
    )
    res = await api_update_product(req)
    assert res.status_code == 200
    data = json.loads(res.body.decode())
    assert data["ok"] is False
    assert "kosong" in data["message"]


async def test_api_update_stock_success():
    stock_id = await crud.add_stock("netflix_trial_reg_th", "original@test.com:pass123")
    req = _make_auth_request(
        "/api/stocks/update",
        {
            "stock_id": stock_id,
            "product_id": "netflix_trial_reg_th",
            "account_data": "edited@test.com:newpass456",
        },
    )
    res = await api_update_stock(req)
    assert res.status_code == 200
    data = json.loads(res.body.decode())
    assert data["ok"] is True

    stocks = await crud.get_stocks("netflix_trial_reg_th")
    s = [x for x in stocks if x["id"] == stock_id][0]
    assert s["account_data"] == "edited@test.com:newpass456"


async def test_api_update_stock_validation():
    stock_id = await crud.add_stock("netflix_trial_reg_th", "val@test.com:pass")
    req = _make_auth_request(
        "/api/stocks/update",
        {
            "stock_id": stock_id,
            "product_id": "netflix_trial_reg_th",
            "account_data": "   ",
        },
    )
    res = await api_update_stock(req)
    assert res.status_code == 200
    data = json.loads(res.body.decode())
    assert data["ok"] is False
    assert "kosong" in data["message"]


async def test_api_category_lifecycle():
    from web.routes.products import api_add_category, api_delete_category, api_rename_category

    # 1. Add category
    req_add = _make_auth_request("/api/categories/add", {"name": "Test Category Lifecycle"})
    res_add = await api_add_category(req_add)
    assert res_add.status_code == 200
    data_add = json.loads(res_add.body.decode())
    assert data_add["ok"] is True
    cat_id = data_add["id"]

    # 2. Rename category
    req_rename = _make_auth_request("/api/categories/rename", {"category_id": cat_id, "name": "Renamed Category"})
    res_rename = await api_rename_category(req_rename)
    assert res_rename.status_code == 200
    data_rename = json.loads(res_rename.body.decode())
    assert data_rename["ok"] is True

    categories = await crud.get_categories()
    c = [x for x in categories if x["id"] == cat_id][0]
    assert c["name"] == "Renamed Category"

    # 3. Delete category
    req_del = _make_auth_request("/api/categories/delete", {"category_id": cat_id, "name": ""})
    res_del = await api_delete_category(req_del)
    assert res_del.status_code == 200
    data_del = json.loads(res_del.body.decode())
    assert data_del["ok"] is True

    categories_after = await crud.get_categories()
    assert not any(x["id"] == cat_id for x in categories_after)
