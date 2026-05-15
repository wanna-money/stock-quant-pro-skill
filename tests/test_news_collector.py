"""Mock-based unit tests for scripts/news_collector.py — no real network calls."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import news_collector as nc


pytestmark = pytest.mark.unit


class TestSinaNews:
    def test_sina_news_parses(self):
        payload = {
            "result": {
                "data": [
                    {"title": "T1", "url": "https://a.example/1",
                     "ctime": "2025-12-01 09:00:00", "media_name": "Example"},
                    {"title": "T2", "url": "https://a.example/2",
                     "ctime": "2025-12-01 10:00:00", "media_name": "Example2"},
                ]
            }
        }
        with patch.object(nc, "http_get_json", return_value=payload):
            out = nc.sina_news(num=2)
        assert len(out) == 2
        assert out[0]["title"] == "T1"
        assert out[0]["source"] == "Sina Finance"
        assert out[0]["category"] == "Example"

    def test_sina_news_empty(self):
        with patch.object(nc, "http_get_json", return_value={"result": {"data": []}}):
            out = nc.sina_news(num=5)
        assert out == []


class TestEastMoneyNews:
    def test_eastmoney_news_parses(self):
        payload = {"data": {"list": [
            {"title": "E1", "url": "https://em.example/1",
             "showtime": "2025-12-01 09:00:00", "columnName": "Market"},
        ]}}
        with patch.object(nc, "http_get_json", return_value=payload):
            out = nc.eastmoney_news(num=5)
        assert len(out) == 1
        assert out[0]["source"] == "East Money"
        assert out[0]["title"] == "E1"

    def test_eastmoney_news_returns_error_record(self):
        with patch.object(nc, "http_get_json", side_effect=RuntimeError("boom")):
            out = nc.eastmoney_news(num=5)
        assert len(out) == 1 and "error" in out[0]
        assert out[0]["source"] == "East Money"


class TestCompanyAnnouncements:
    def test_announcements_parses(self):
        payload = {"data": {"list": [
            {"title": "Ann1", "art_code": "A0001", "notice_date": "2025-12-01",
             "columns": [{"column_name": "定期报告"}]},
        ]}}
        with patch.object(nc, "http_get_json", return_value=payload):
            out = nc.company_announcements("600519", num=5)
        assert out[0]["stock_code"] == "600519"
        assert out[0]["ann_title"] == "Ann1"
        assert out[0]["columns"] == ["定期报告"]

    def test_announcements_error_record(self):
        with patch.object(nc, "http_get_json", side_effect=RuntimeError("x")):
            out = nc.company_announcements("600519")
        assert "error" in out[0]


class TestMacroNews:
    def test_macro_news_parses(self):
        payload = {"result": {"data": [
            {"title": "M1", "url": "https://m.example/1", "ctime": "2025-12-01"},
        ]}}
        with patch.object(nc, "http_get_json", return_value=payload):
            out = nc.macro_news(num=5)
        assert out[0]["source"] == "Sina Macro"
        assert out[0]["category"] == "macro/policy"

    def test_macro_news_error_record(self):
        with patch.object(nc, "http_get_json", side_effect=RuntimeError("x")):
            out = nc.macro_news(num=5)
        assert "error" in out[0]


class TestCollectAll:
    def test_collect_all_schema(self):
        with patch.object(nc, "sina_news", return_value=[{"title": "s", "source": "Sina Finance"}]), \
             patch.object(nc, "eastmoney_news", return_value=[{"title": "e", "source": "East Money"}]), \
             patch.object(nc, "macro_news", return_value=[{"title": "m", "source": "Sina Macro"}]), \
             patch.object(nc, "company_announcements", return_value=[{"title": "a"}]):
            result = nc.collect_all(stock_code="600519", num=5)
        assert "timestamp" in result
        assert "financial_news" in result
        assert "macro_news" in result
        assert "company_announcements" in result
        assert len(result["financial_news"]) == 2

    def test_collect_all_without_code_skips_announcements(self):
        with patch.object(nc, "sina_news", return_value=[]), \
             patch.object(nc, "eastmoney_news", return_value=[]), \
             patch.object(nc, "macro_news", return_value=[]):
            result = nc.collect_all(stock_code=None)
        assert "company_announcements" not in result

    def test_collect_all_tolerates_source_failures(self):
        with patch.object(nc, "sina_news", side_effect=RuntimeError("sina down")), \
             patch.object(nc, "eastmoney_news", return_value=[]), \
             patch.object(nc, "macro_news", return_value=[]):
            result = nc.collect_all()
        assert any("error" in item for item in result["financial_news"])
