"""Mock-based unit tests for scripts/fundamental_analysis.py — no real network calls."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

import fundamental_analysis as fa


pytestmark = pytest.mark.unit


def _fake_indicator_df():
    return pd.DataFrame([{
        "日期": "2025-09-30",
        "净资产收益率(%)": 20.0,
        "销售净利率(%)": 40.0,
        "总资产周转率(次)": 0.5,
        "流动比率": 2.5,
        "速动比率": 1.8,
        "资产负债率(%)": 25.0,
        "存货周转率(次)": 1.2,
        "应收账款周转率(次)": 4.5,
    }])


def _fake_spot_df():
    return pd.DataFrame([{
        "代码": "600519",
        "名称": "贵州茅台",
        "最新价": 1800.0,
        "市盈率-动态": 25.5,
        "市净率": 8.2,
        "总市值": 2.25e12,
        "流通市值": 2.25e12,
    }])


class TestGetValuation:
    def test_valuation_schema(self):
        with patch.object(fa, "HAS_AKSHARE", True), \
             patch.object(fa, "ak", MagicMock(stock_zh_a_spot_em=lambda: _fake_spot_df()), create=True):
            out = fa.get_valuation("600519")
        for k in ("code", "name", "price", "pe_ttm", "pb", "total_mv_yi", "circulating_mv_yi"):
            assert k in out
        assert out["code"] == "600519"
        assert out["price"] == 1800.0
        assert out["total_mv_yi"] == round(2.25e12 / 1e8, 2)

    def test_valuation_missing_stock_raises(self):
        empty = pd.DataFrame(columns=["代码", "名称", "最新价"])
        with patch.object(fa, "HAS_AKSHARE", True), \
             patch.object(fa, "ak", MagicMock(stock_zh_a_spot_em=lambda: empty), create=True):
            with pytest.raises(ValueError, match="not found"):
                fa.get_valuation("000000")

    def test_valuation_no_akshare_raises(self):
        with patch.object(fa, "HAS_AKSHARE", False):
            with pytest.raises(RuntimeError, match="akshare not installed"):
                fa.get_valuation("600519")


class TestDupontAnalysis:
    def test_dupont_decomposition(self):
        df = _fake_indicator_df()
        with patch.object(fa, "get_financial_indicators", return_value=df):
            out = fa.dupont_analysis("600519")
        assert out["roe_pct"] == 20.0
        assert out["net_profit_margin_pct"] == 40.0
        assert out["asset_turnover"] == 0.5
        # equity_multiplier = roe / (npm * at) = 20 / (40 * 0.5) = 1.0
        assert out["equity_multiplier"] == 1.0
        assert "decomposition" in out

    def test_dupont_empty_df(self):
        with patch.object(fa, "get_financial_indicators", return_value=pd.DataFrame()):
            out = fa.dupont_analysis("600519")
        assert "error" in out

    def test_dupont_exception_captured(self):
        with patch.object(fa, "get_financial_indicators", side_effect=RuntimeError("boom")):
            out = fa.dupont_analysis("600519")
        assert "error" in out


class TestEastMoneyFinancials:
    def test_eastmoney_financials_returns_rows(self):
        payload = {"result": {"data": [
            {"REPORTDATE": "2025-09-30 00:00:00",
             "TOTAL_OPERATE_INCOME": 1.2e11, "PARENT_NETPROFIT": 5.0e10,
             "BASIC_EPS": 3.5, "WEIGHTAVG_ROE": 15.2, "XSMLL": 90.0,
             "YSTZ": 12.0, "SJLTZ": 20.0},
        ]}}
        with patch.object(fa, "http_get_json", return_value=payload):
            rows = fa.get_eastmoney_financials("600519")
        assert len(rows) == 1
        assert rows[0]["WEIGHTAVG_ROE"] == 15.2

    def test_eastmoney_financials_empty_on_failures(self):
        with patch.object(fa, "http_get_json", side_effect=RuntimeError("x")):
            rows = fa.get_eastmoney_financials("600519")
        assert rows == []

    def test_eastmoney_financials_skips_missing_data(self):
        with patch.object(fa, "http_get_json", return_value={"result": None}):
            rows = fa.get_eastmoney_financials("600519")
        assert rows == []


class TestFundamentalReport:
    def test_report_aggregates_all_sources(self):
        ind_df = _fake_indicator_df()
        spot_df = _fake_spot_df()
        em_data = [{
            "REPORTDATE": "2025-09-30 00:00:00",
            "TOTAL_OPERATE_INCOME": 1.2e11, "PARENT_NETPROFIT": 5.0e10,
            "BASIC_EPS": 3.5, "WEIGHTAVG_ROE": 15.2, "XSMLL": 90.0,
            "YSTZ": 12.0, "SJLTZ": 20.0,
        }]
        with patch.object(fa, "HAS_AKSHARE", True), \
             patch.object(fa, "ak", MagicMock(stock_zh_a_spot_em=lambda: spot_df), create=True), \
             patch.object(fa, "get_financial_indicators", return_value=ind_df), \
             patch.object(fa, "get_eastmoney_financials", return_value=em_data):
            report = fa.fundamental_report("600519")
        assert report["code"] == "600519"
        assert "valuation" in report
        assert "dupont" in report
        assert "earnings" in report
        assert report["earnings"]["report_date"] == "2025-09-30"
        assert report["earnings"]["roe_pct"] == 15.2
        assert "quality" in report
        assert report["quality"]["current_ratio"] == 2.5

    def test_report_records_warnings_on_failures(self):
        with patch.object(fa, "HAS_AKSHARE", True), \
             patch.object(fa, "ak", MagicMock(stock_zh_a_spot_em=MagicMock(side_effect=RuntimeError("api"))), create=True), \
             patch.object(fa, "get_financial_indicators", side_effect=RuntimeError("ind")), \
             patch.object(fa, "get_eastmoney_financials", return_value=[]):
            report = fa.fundamental_report("600519")
        assert report["code"] == "600519"
        assert "data_warnings" in report
        assert any("Valuation" in w for w in report["data_warnings"])


class TestSafeFloat:
    def test_dash_string_returns_default(self):
        assert fa._safe_float("-") == 0.0
        assert fa._safe_float("--") == 0.0
        assert fa._safe_float("N/A", default=-1.0) == -1.0

    def test_none_returns_default(self):
        assert fa._safe_float(None) == 0.0

    def test_nan_returns_default(self):
        assert fa._safe_float(float("nan")) == 0.0
        assert fa._safe_float(float("inf")) == 0.0
        assert fa._safe_float(float("-inf")) == 0.0

    def test_numeric_passthrough(self):
        assert fa._safe_float(3.14) == 3.14
        assert fa._safe_float("2.5") == 2.5
        assert fa._safe_float(0) == 0.0

    def test_valuation_handles_dash_pe(self):
        df = pd.DataFrame([{
            "代码": "600519", "名称": "贵州茅台",
            "最新价": 1800.0,
            "市盈率-动态": "-",
            "市净率": float("nan"),
            "总市值": 2.25e12, "流通市值": 2.25e12,
        }])
        with patch.object(fa, "HAS_AKSHARE", True), \
             patch.object(fa, "ak", MagicMock(stock_zh_a_spot_em=lambda: df), create=True):
            out = fa.get_valuation("600519")
        assert out["pe_ttm"] == 0.0
        assert out["pb"] == 0.0
        assert out["price"] == 1800.0
