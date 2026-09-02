"""Konfigurasi Jinja2 templates + custom filters."""
from datetime import datetime

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="web/templates")


def fmt_rupiah(value) -> str:
    try:
        return f"Rp {int(value):,}"
    except (TypeError, ValueError):
        return "Rp 0"


def fmt_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d %b %Y %H:%M")
    except (ValueError, TypeError):
        return str(value)


templates.env.filters["rupiah"] = fmt_rupiah
templates.env.filters["tgdate"] = fmt_date
