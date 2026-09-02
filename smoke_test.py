"""Script Smoke Test End-to-End untuk Bot Auto-Order & Web Dashboard."""
import asyncio
import http.cookiejar
import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse

from bot.config import (
    BOT_TOKEN,
    DB_PATH,
    FORCE_SUB_CHANNEL,
    SAYABAYAR_API_BASE,
    SAYABAYAR_API_KEY,
    WEB_ADMIN_PASSWORD,
    WEB_PORT,
)


class SmokeTester:
    def __init__(self):
        self.results = []
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def log(self, step: str, success: bool, detail: str = ""):
        mark = "✅ PASS" if success else "❌ FAIL"
        msg = f"{mark} | {step}"
        if detail:
            msg += f" -> {detail}"
        print(msg)
        self.results.append((step, success, detail))

    def test_systemd(self):
        try:
            active = subprocess.check_output(["systemctl", "is-active", "bot-autoorder.service"]).decode().strip()
            enabled = subprocess.check_output(["systemctl", "is-enabled", "bot-autoorder.service"]).decode().strip()
            ok = (active == "active" and enabled == "enabled")
            self.log("1. Systemd Service", ok, f"active={active}, enabled={enabled}")
        except Exception as e:
            self.log("1. Systemd Service", False, str(e))

    async def test_telegram_api(self):
        import aiohttp
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    data = await resp.json()
                    ok = data.get("ok", False)
                    user = data.get("result", {})
                    username = user.get("username", "unknown")
                    bot_id = user.get("id", "unknown")
                    self.log("2. Telegram Bot API (getMe)", ok, f"@{username} (id: {bot_id})")

                # Test Force-Sub Channel
                chat_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={FORCE_SUB_CHANNEL}"
                async with session.get(chat_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    chat_data = await resp.json()
                    chat_ok = chat_data.get("ok", False)
                    title = chat_data.get("result", {}).get("title", "")
                    self.log("3. Telegram Force-Sub Channel", chat_ok, f"Channel {FORCE_SUB_CHANNEL} ('{title}')")
        except Exception as e:
            self.log("2. Telegram API", False, str(e))

    async def test_sayabayar_gateway(self):
        import aiohttp
        try:
            headers = {"X-API-Key": SAYABAYAR_API_KEY, "Accept": "application/json"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{SAYABAYAR_API_BASE}/invoices/test-smoke-ping", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    self.log("4. SayaBayar Gateway API", resp.status in (200, 400, 404), f"HTTP {resp.status} endpoint reachability")
        except Exception as e:
            self.log("4. SayaBayar Gateway API", False, str(e))

    def test_database_integrity(self):
        import sqlite3
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            tables = ["categories", "products", "stocks", "orders", "users"]
            counts = {}
            for t in tables:
                cur.execute(f"SELECT count(*) FROM {t}")
                counts[t] = cur.fetchone()[0]
            conn.close()
            self.log("5. Database SQLite Tables", True, ", ".join(f"{k}:{v}" for k, v in counts.items()))
        except Exception as e:
            self.log("5. Database SQLite Tables", False, str(e))

    def test_web_dashboard(self):
        base_url = f"http://127.0.0.1:{WEB_PORT}"
        try:
            # GET /login
            with self.opener.open(f"{base_url}/login", timeout=5) as resp:
                html = resp.read().decode()
                ok = (resp.status == 200 and "SayaBayar Bot" in html)
                self.log("6. Web Dashboard GET /login", ok, f"HTTP {resp.status}")

            # POST /login
            login_data = urllib.parse.urlencode({"password": WEB_ADMIN_PASSWORD}).encode()
            req = urllib.request.Request(f"{base_url}/login", data=login_data, method="POST")
            with self.opener.open(req, timeout=5) as resp:
                self.log("7. Web Dashboard POST /login (Auth)", resp.status in (200, 303), f"HTTP {resp.status}")

            # GET Protected routes
            routes = [
                ("/", "Ringkasan Sistem"),
                ("/stocks", "Manajemen Stok"),
                ("/products", "Katalog & Produk"),
                ("/orders", "Monitor Transaksi"),
                ("/users", "Pengguna & Broadcast"),
            ]
            for path, keyword in routes:
                with self.opener.open(f"{base_url}{path}", timeout=5) as resp:
                    body = resp.read().decode()
                    has_kw = keyword in body
                    self.log(f"8. Web Route '{path}'", (resp.status == 200 and has_kw), f"HTTP {resp.status}")

            # GET API JSON
            with self.opener.open(f"{base_url}/api/stats", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.log("9. Web API /api/stats (JSON)", "stats" in data, f"Total Revenue: Rp {data['stats']['revenue']}")

            with self.opener.open(f"{base_url}/api/activities", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.log("10. Web API /api/activities (JSON)", "events" in data, f"{len(data['events'])} events")

        except Exception as e:
            self.log("6-10. Web Dashboard", False, str(e))

    def test_quicktunnel(self):
        tunnel_url = "https://historical-asin-decades-plaza.trycloudflare.com/login"
        try:
            req = urllib.request.Request(tunnel_url, headers={"User-Agent": "SmokeTest/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode()
                ok = (resp.status == 200 and "SayaBayar" in html)
                self.log("11. Public QuickTunnel URL", ok, f"HTTP {resp.status} -> {tunnel_url}")
        except Exception as e:
            self.log("11. Public QuickTunnel URL", False, str(e))

    def run_unit_tests(self):
        try:
            res = subprocess.run(["venv/bin/pytest", "-q"], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "."})
            passed = (res.returncode == 0)
            summary = res.stdout.strip().split("\n")[-1] if res.stdout else "No output"
            self.log("12. Pytest Unit Test Suite (21 Tests)", passed, summary)
        except Exception as e:
            self.log("12. Pytest Unit Test Suite", False, str(e))

    async def run_all(self):
        print("=" * 65)
        print("🚀 MENJALANKAN SMOKE TEST BOT AUTO-ORDER & DASHBOARD")
        print("=" * 65)
        self.test_systemd()
        await self.test_telegram_api()
        await self.test_sayabayar_gateway()
        self.test_database_integrity()
        self.test_web_dashboard()
        self.test_quicktunnel()
        self.run_unit_tests()
        print("=" * 65)
        passed = sum(1 for _, ok, _ in self.results if ok)
        total = len(self.results)
        print(f"📊 HASIL AKHIR: {passed}/{total} Pengujian Berhasil!")
        print("=" * 65)
        return passed == total


if __name__ == "__main__":
    tester = SmokeTester()
    success = asyncio.run(tester.run_all())
    sys.exit(0 if success else 1)
