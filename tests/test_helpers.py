"""Unit test untuk helper murni (tanpa DB / Telegram)."""
from bot.handlers.admin.products import parse_price
from bot.handlers.admin.stats import format_sales_report
from bot.handlers.catalog import stock_label
from bot.utils.sayabayar import parse_invoice_status
from bot.utils.telegram import payload_after


class TestParsePrice:
    def test_plain_number(self):
        assert parse_price("25000") == 25000

    def test_with_thousand_separators(self):
        assert parse_price("25.000") == 25000
        assert parse_price("25,000") == 25000

    def test_invalid_returns_none(self):
        assert parse_price("abc") is None
        assert parse_price("") is None

    def test_non_positive_returns_none(self):
        assert parse_price("0") is None
        assert parse_price("-5") is None


class TestParseInvoiceStatus:
    def test_status_key(self):
        assert parse_invoice_status({"status": "paid"}) == "PAID"

    def test_payment_status_fallback(self):
        assert parse_invoice_status({"payment_status": "success"}) == "SUCCESS"

    def test_missing_becomes_question_mark(self):
        assert parse_invoice_status({}) == "?"


class TestPayloadAfter:
    class FakeCallback:
        def __init__(self, data):
            self.data = data

    def test_strips_prefix(self):
        assert payload_after(self.FakeCallback("buy:netflix_1"), "buy:") == "netflix_1"

    def test_none_data(self):
        assert payload_after(self.FakeCallback(None), "buy:") == ""


class TestStockLabel:
    def test_in_stock(self):
        assert "✅" in stock_label(3)

    def test_out_of_stock(self):
        assert "❌" in stock_label(0)


class TestFormatSalesReport:
    def test_contains_totals(self):
        stats = {
            "completed": 2,
            "revenue": 50000,
            "pending": 1,
            "paid_oos": 0,
            "stock_ready": 7,
            "top_products": [{"name": "Netflix", "sold": 2}],
        }
        report = format_sales_report(stats)
        assert "Rp 50,000" in report
        assert "Netflix" in report

    def test_without_top_products(self):
        stats = {
            "completed": 0, "revenue": 0, "pending": 0,
            "paid_oos": 0, "stock_ready": 0, "top_products": [],
        }
        assert "Produk terlaris" not in format_sales_report(stats)
