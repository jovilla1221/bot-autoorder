# Bot Auto Order - SayaBayar

Bot Telegram buat auto-order via API SayaBayar dengan **force subscribe** ke @reveuseress.

## Struktur

```
bot_autoorder/
├── bot/
│   ├── config.py          # Env config loader
│   ├── handlers/
│   │   ├── common.py      # /start, force-sub check, main menu
│   │   ├── order.py       # Buat invoice FSM
│   │   └── callbacks.py   # Inline button handlers
│   └── utils/
│       ├── forcesub.py    # Force-sub channel check
│       └── sayabayar.py   # SayaBayar API client
├── main.py                # Entry point
├── .env.example           # Template env
├── .env                   # Real env (gitignored)
└── requirements.txt
```

## Setup

```bash
cd ~/bot_autoorder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: isi BOT_TOKEN + SAYABAYAR_API_KEY
```

## Run

```bash
source venv/bin/activate
python3 main.py
```

## Force-Sub

User wajib join **@reveuseress** dulu sebelum pake bot.
Bot harus **admin** di channel itu (utk `get_chat_member`).

## API Endpoints yg dipake

- `POST /v1/invoices/create` — buat invoice baru
- `GET /v1/invoices/{id}` — cek status
- `POST /v1/invoices/{id}/cancel` — cancel

**Belum terverifikasi** — sayabayar ga publish public docs. Lo perlu login ke dashboard merchant atau minta docs ke support buat konfirmasi path/field exact.

## Bot Token

Token bot yg lo kasih udah gw test via `getMe`:
- Bot: `@autoorderrvspcbot` (id 8751758948)
- Name: "auto order reveuse space"
- Channel @reveuseress valid (id -1004318213815)

**PENTING**: token ditulis di `.env`, jangan di-commit. File `.env` udah di-gitignore-style (private).

## Flow User

1. `/start` → bot cek subscription
2. Belum join → muncul tombol Join + "Sudah Join"
3. User klik "Sudah Join" → bot re-check → show main menu
4. Main menu: Buat Invoice | Cek Status | Bantuan
5. Buat Invoice → FSM 3 step: nominal → deskripsi → customer
6. Hit API sayabayar → return payment URL
