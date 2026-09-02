import aiohttp
import logging

from bot.config import SAYABAYAR_API_BASE, SAYABAYAR_API_KEY

logger = logging.getLogger(__name__)

class SayaBayarClient:
    def __init__(self):
        self.base_url = SAYABAYAR_API_BASE
        self.api_key = SAYABAYAR_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=self.headers, **kwargs) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    logger.error(f"SayaBayar {method} {path} → {resp.status}: {data}")
                    return {"error": True, "status": resp.status, "data": data}
                return {"error": False, "status": resp.status, "data": data}

    async def create_invoice(self, amount: int, description: str, customer_name: str = None) -> dict:
        payload = {"amount": amount, "description": description}
        if customer_name:
            payload["customer_name"] = customer_name
        return await self._request("POST", "/invoices/create", json=payload)

    async def check_status(self, invoice_id: str) -> dict:
        return await self._request("GET", f"/invoices/{invoice_id}")

    async def cancel_invoice(self, invoice_id: str) -> dict:
        return await self._request("POST", f"/invoices/{invoice_id}/cancel")

client = SayaBayarClient()