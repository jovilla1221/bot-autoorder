"""Aplikasi FastAPI dashboard admin.

Jalankan standalone:
    uvicorn web.app:app --host 127.0.0.1 --port 8000
Atau terintegrasi dengan bot (lihat main.py).
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from bot.config import SAYABAYAR_API_KEY
from web.activity import log_event
from web.bot_bridge import is_integrated
from web.routes import auth_pages, dashboard, orders, products, stocks, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("info", "web", "Dashboard web dimulai")
    yield
    log_event("info", "web", "Dashboard web dihentikan")


def create_app() -> FastAPI:
    app = FastAPI(title="SayaBayar Bot Dashboard", lifespan=lifespan, docs_url=None, redoc_url=None)

    app.include_router(auth_pages.router)
    app.include_router(dashboard.router)
    app.include_router(stocks.router)
    app.include_router(products.router)
    app.include_router(orders.router)
    app.include_router(users.router)

    if os.path.isdir("web/static"):
        app.mount("/static", StaticFiles(directory="web/static"), name="static")

    @app.get("/healthz")
    async def healthz():
        return {
            "status": "ok",
            "bot_integrated": is_integrated(),
            "sayabayar_key_set": bool(SAYABAYAR_API_KEY),
        }

    return app


app = create_app()
