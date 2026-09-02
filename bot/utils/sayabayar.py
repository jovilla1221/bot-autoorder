"""Async client untuk API SayaBayar (kontrak terverifikasi 2 Sep 2026).

Kontrak API (live-tested):
- Auth: header `X-API-Key`
- Create : POST {base}/invoices        → data.{id, invoice_number, amount, payment_url, status(pending), expired_at}
- Status : GET  {base}/invoices/{id}   → data.{status(lowercase), amount, paid_at, payment_url, transactions[]}
- Cancel : DELETE {base}/invoices/{id}
- Envelope: {"success": bool, "data": ..., "error": {"code", "message"}|null, "meta": {...}}
"""
import logging
from typing import Any, Mapping

import aiohttp

from bot.config import SAYABAYAR_API_BASE, SAYABAYAR_API_KEY

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
# Bentuk hasil: {"error": bool, "status": int, "data": Any}
GatewayResult = dict[str, Any]

# Status invoice gateway (lowercase) → ternormalisasi uppercase saat diparse
PENDING_STATUS = "pending"
PAID_STATUS = "paid"


def parse_invoice_status(payload: Mapping[str, Any]) -> str:
    """Ambil status invoice dari response gateway (dinormalisasi ke uppercase)."""
    raw = payload.get("status") or payload.get("payment_status") or "?"
    return str(raw).upper()


def extract_invoice_fields(data: Mapping[str, Any]) -> dict[str, str]:
    """Ekstrak field standar dari response create/get invoice gateway."""
    return {
        "invoice_id": str(data.get("id") or data.get("invoice_id") or "?"),
        "payment_url": str(data.get("payment_url") or ""),
        "qris_data": str(data.get("qris") or ""),
    }


class SayaBayarClient:
    """Wrapper aiohttp untuk endpoint invoice SayaBayar.

    Satu session dibuat per call (sederhana & cukup untuk skala bot ini);
    timeout mencegah poller menggantung kalau gateway lambat.
    """

    def __init__(self) -> None:
        self.base_url: str = SAYABAYAR_API_BASE
        self.api_key: str = SAYABAYAR_API_KEY

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> GatewayResult:
        url = f"{self.base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, headers=self._headers(), **kwargs) as resp:
                    try:
                        data: Any = await resp.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError) as exc:
                        logger.error("SayaBayar %s %s → %s: response bukan JSON (%s)", method, path, resp.status, exc)
                        return {"error": True, "status": resp.status, "data": f"invalid json: {exc}"}
        except aiohttp.ClientError as exc:
            logger.error("SayaBayar %s %s: koneksi gagal (%s)", method, path, exc)
            return {"error": True, "status": 0, "data": f"connection error: {exc}"}

        # Envelope gateway: {"success": bool, ...} — perlakukan success=false sebagai error
        is_envelope = isinstance(data, dict) and "success" in data
        failed = resp.status >= 400 or (is_envelope and not data["success"])
        if failed:
            logger.error("SayaBayar %s %s → %s: %s", method, path, resp.status, data)
            return {"error": True, "status": resp.status, "data": data}
        return {"error": False, "status": resp.status, "data": data.get("data", data) if is_envelope else data}

    async def create_invoice(
        self,
        amount: int,
        description: str,
        customer_name: str | None = None,
    ) -> GatewayResult:
        payload: dict[str, Any] = {"amount": amount, "description": description}
        if customer_name:
            payload["customer_name"] = customer_name
        return await self._request("POST", "/invoices", json=payload)

    async def check_status(self, invoice_id: str) -> GatewayResult:
        return await self._request("GET", f"/invoices/{invoice_id}")

    async def cancel_invoice(self, invoice_id: str) -> GatewayResult:
        """Hapus/batalkan invoice (DELETE /invoices/{id}, butuh body JSON)."""
        return await self._request("DELETE", f"/invoices/{invoice_id}", json={"confirm": True})


client = SayaBayarClient()
