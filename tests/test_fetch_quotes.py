"""Mock-based unit tests for scripts/fetch_quotes.py — no real network calls.

Real-network fallback paths for these functions are exercised in
tests/test_integration_live.py (marked @pytest.mark.integration).
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest

import fetch_quotes as fq


pytestmark = pytest.mark.unit


class TestStripMarketPrefix:
    @pytest.mark.parametrize("raw,expected", [
        ("sh600519", "600519"),
        ("sz000001", "000001"),
        ("SH600519", "600519"),
        ("hk00700", "00700"),
        ("600519", "600519"),
        ("bj408001", "408001"),
        ("BJ830799", "830799"),
    ])
    def test_prefix_stripped(self, raw, expected):
        assert fq.strip_market_prefix(raw) == expected


class TestTencentRealtime:
    def test_tencent_realtime_parses_45plus_fields(self):
        # ~-delimited line with 50 fields (real Tencent payload has ~60+).
        parts = ["v_sh600519=\"1", "贵州茅台", "600519", "1800.00", "1790.00",
                 "1795.00", "10000"]
        parts += ["0"] * 25  # pad through index 31
        parts += ["1.50"]    # idx 32 = change_pct
        parts += ["1810.00", "1780.00"]  # idx 33 high, 34 low
        parts += ["0"] * 15
        text = "~".join(parts) + "\";"
        with patch.object(fq, "http_get", return_value=text):
            results = fq.tencent_realtime(["sh600519"])
        assert len(results) == 1
        r = results[0]
        assert r["code"] == "600519"
        assert r["name"] == "贵州茅台"
        assert r["price"] == 1800.00
        assert r["high"] == 1810.00
        assert r["low"] == 1780.00
        assert r["change_pct"] == 1.50
        assert r["source"] == "Tencent Finance"

    def test_tencent_realtime_skips_short_lines(self):
        with patch.object(fq, "http_get", return_value="no-tilde-here\n"):
            results = fq.tencent_realtime(["sh600519"])
        assert results == []


class TestTencentKline:
    def test_tencent_kline_parses_qfqday(self):
        payload = {
            "data": {
                "600519": {
                    "qfqday": [
                        ["2025-12-01", "1800.0", "1820.0", "1830.0", "1790.0", "12345"],
                        ["2025-12-02", "1820.0", "1810.0", "1835.0", "1800.0", "10000"],
                    ]
                }
            }
        }
        with patch.object(fq, "http_get", return_value=json.dumps(payload)):
            df = fq.tencent_kline("sh600519", "2025-12-01", "2025-12-02")
        assert list(df.columns) == ["open", "close", "high", "low", "volume"]
        assert len(df) == 2
        assert df["close"].iloc[-1] == 1810.0
        assert pd.api.types.is_datetime64_any_dtype(df.index)

    def test_tencent_kline_no_data_raises(self):
        with patch.object(fq, "http_get", return_value=json.dumps({"data": {}})):
            with pytest.raises(ValueError, match="No K-line"):
                fq.tencent_kline("sh600519", "2025-12-01", "2025-12-02")


class TestEastMoneyKline:
    def test_eastmoney_kline_parses_klines(self):
        payload = {
            "data": {
                "klines": [
                    "2025-12-01,1800.0,1820.0,1830.0,1790.0,12345,2.2e10,2.0,1.1,20.0,0.5",
                    "2025-12-02,1820.0,1810.0,1835.0,1800.0,10000,1.8e10,1.9,-0.5,-10.0,0.4",
                ]
            }
        }
        with patch.object(fq, "http_get", return_value=json.dumps(payload)):
            df = fq.eastmoney_kline("sh600519", "2025-12-01", "2025-12-02")
        assert {"open", "close", "high", "low", "volume", "amount"}.issubset(df.columns)
        assert len(df) == 2
        assert df["close"].iloc[0] == 1820.0
        assert df.index.is_monotonic_increasing

    def test_eastmoney_secid_prefix(self):
        """sh / 6xx codes must use prefix 1, otherwise 0."""
        captured = {}

        def fake_http_get(url, headers=None):
            captured["url"] = url
            return json.dumps({"data": {"klines": [
                "2025-12-01,1,1,1,1,1,1,1,1,1,1"
            ]}})

        with patch.object(fq, "http_get", side_effect=fake_http_get):
            fq.eastmoney_kline("sh600519", "2025-12-01", "2025-12-02")
        assert "secid=1.600519" in captured["url"]

        with patch.object(fq, "http_get", side_effect=fake_http_get):
            fq.eastmoney_kline("sz000001", "2025-12-01", "2025-12-02")
        assert "secid=0.000001" in captured["url"]

    def test_eastmoney_no_data_raises(self):
        with patch.object(fq, "http_get", return_value=json.dumps({"data": {"klines": []}})):
            with pytest.raises(ValueError, match="No data"):
                fq.eastmoney_kline("sh600519", "2025-12-01", "2025-12-02")


class TestGetRealtimeFallback:
    def test_falls_back_to_tencent_when_akshare_fails(self):
        tencent_row = {"code": "600519", "name": "Test", "price": 100.0,
                       "prev_close": 99, "open": 99.5, "volume": 1,
                       "high": 101, "low": 98, "change_pct": 1.0,
                       "source": "Tencent Finance"}
        with patch.object(fq, "HAS_AKSHARE", True), \
             patch.object(fq, "akshare_realtime_a", side_effect=RuntimeError("boom")), \
             patch.object(fq, "tencent_realtime", return_value=[tencent_row]):
            out = fq.get_realtime("sh600519")
        assert out["source"] == "Tencent Finance"
        assert out["price"] == 100.0

    def test_all_sources_fail_raises(self):
        with patch.object(fq, "HAS_AKSHARE", True), \
             patch.object(fq, "akshare_realtime_a", side_effect=RuntimeError("a")), \
             patch.object(fq, "tencent_realtime", side_effect=RuntimeError("b")):
            with pytest.raises(RuntimeError, match="All data sources failed"):
                fq.get_realtime("sh600519")


class TestGetHistoryFallback:
    def _fake_df(self):
        idx = pd.bdate_range(end="2025-12-31", periods=5)
        return pd.DataFrame({
            "open": [1.0] * 5, "close": [1.0] * 5,
            "high": [1.0] * 5, "low": [1.0] * 5, "volume": [1.0] * 5,
        }, index=idx)

    def test_uses_akshare_first_when_available(self):
        df = self._fake_df()
        with patch.object(fq, "HAS_AKSHARE", True), \
             patch.object(fq, "akshare_history", return_value=df) as m_ak, \
             patch.object(fq, "eastmoney_kline") as m_em:
            out = fq.get_history("sh600519", "2025-01-01", "2025-12-31")
        assert m_ak.called
        assert not m_em.called
        assert len(out) == 5

    def test_falls_back_to_eastmoney_then_tencent(self):
        df = self._fake_df()
        with patch.object(fq, "HAS_AKSHARE", True), \
             patch.object(fq, "akshare_history", side_effect=RuntimeError("ak")), \
             patch.object(fq, "eastmoney_kline", side_effect=RuntimeError("em")), \
             patch.object(fq, "tencent_kline", return_value=df) as m_tc:
            out = fq.get_history("sh600519", "2025-01-01", "2025-12-31")
        assert m_tc.called
        assert len(out) == 5
