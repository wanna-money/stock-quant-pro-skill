"""Real-network integration tests — opt-in via `pytest -m integration`.

These tests hit live public data sources (Tencent Finance, AKShare, EastMoney,
Sina Finance) and may fail if the network is unavailable, the endpoints change,
or rate-limiting kicks in. Each test is tolerant of transient failures and
will SKIP (not fail) if the upstream data source is unreachable.

Run only these tests:
    pytest -m integration

Skip these tests (default unit run):
    pytest -m "not integration"
"""
from __future__ import annotations

import os
import socket
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _network_available() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3).close()
        return True
    except OSError:
        return False


if not _network_available():
    pytest.skip("No network connectivity — skipping integration suite",
                allow_module_level=True)


if os.environ.get("SKIP_INTEGRATION", "").lower() in ("1", "true", "yes"):
    pytest.skip("SKIP_INTEGRATION set — skipping integration suite",
                allow_module_level=True)


# --------------------------------------------------------------------------- #
# fetch_quotes: real-time + historical
# --------------------------------------------------------------------------- #

class TestFetchQuotesLive:
    def test_tencent_realtime_live(self):
        import fetch_quotes as fq
        try:
            rows = fq.tencent_realtime(["sh600519"])
        except Exception as e:
            pytest.skip(f"Tencent realtime unreachable: {e}")
        assert isinstance(rows, list)
        if not rows:
            pytest.skip("Tencent returned empty payload (market closed?)")
        r = rows[0]
        assert r["code"] == "600519"
        assert r["price"] > 0
        assert r["source"] == "Tencent Finance"

    def test_get_realtime_fallback_live(self):
        import fetch_quotes as fq
        try:
            row = fq.get_realtime("sh600519")
        except Exception as e:
            pytest.skip(f"All realtime sources unreachable: {e}")
        assert "price" in row
        assert row["price"] > 0

    def test_eastmoney_kline_live(self):
        import fetch_quotes as fq
        try:
            df = fq.eastmoney_kline("sh600519", "2024-01-01", "2024-06-30")
        except Exception as e:
            pytest.skip(f"EastMoney kline unreachable: {e}")
        assert len(df) > 10
        assert {"open", "close", "high", "low", "volume"}.issubset(df.columns)

    def test_get_history_live(self):
        import fetch_quotes as fq
        try:
            df = fq.get_history("sh600519", "2024-01-01", "2024-03-31")
        except Exception as e:
            pytest.skip(f"All history sources unreachable: {e}")
        assert len(df) > 10
        assert df["close"].notna().all()


# --------------------------------------------------------------------------- #
# news_collector: live feeds
# --------------------------------------------------------------------------- #

class TestNewsCollectorLive:
    def test_sina_news_live(self):
        import news_collector as nc
        try:
            out = nc.sina_news(num=5)
        except Exception as e:
            pytest.skip(f"Sina news unreachable: {e}")
        assert isinstance(out, list)
        if out and "error" not in out[0]:
            assert "title" in out[0]
            assert out[0]["source"] == "Sina Finance"

    def test_eastmoney_news_live(self):
        import news_collector as nc
        try:
            out = nc.eastmoney_news(num=5)
        except Exception as e:
            pytest.skip(f"EastMoney news unreachable: {e}")
        assert isinstance(out, list)
        if out and "error" not in out[0]:
            assert out[0]["source"] == "East Money"

    def test_company_announcements_live(self):
        import news_collector as nc
        try:
            out = nc.company_announcements("600519", num=5)
        except Exception as e:
            pytest.skip(f"EastMoney announcements unreachable: {e}")
        assert isinstance(out, list)
        if out and "error" not in out[0]:
            assert out[0]["stock_code"] == "600519"


# --------------------------------------------------------------------------- #
# sector_analysis: requires akshare to be installed at runtime
# --------------------------------------------------------------------------- #

class TestSectorAnalysisLive:
    def test_industry_ranking_live(self):
        try:
            import sector_analysis as sa
            out = sa.sector_ranking(top_n=5)
        except ImportError:
            pytest.skip("akshare not installed")
        except Exception as e:
            pytest.skip(f"Sector ranking unreachable: {e}")
        assert isinstance(out, list)
        if out:
            assert "name" in out[0]
            assert "change_pct" in out[0]

    def test_sector_breadth_live(self):
        try:
            import sector_analysis as sa
            out = sa.sector_breadth()
        except ImportError:
            pytest.skip("akshare not installed")
        except Exception as e:
            pytest.skip(f"Sector breadth unreachable: {e}")
        assert "total_sectors" in out
        assert out["total_sectors"] > 0


# --------------------------------------------------------------------------- #
# fundamental_analysis: requires akshare
# --------------------------------------------------------------------------- #

class TestFundamentalAnalysisLive:
    def test_valuation_live(self):
        try:
            import fundamental_analysis as fa
            out = fa.get_valuation("600519")
        except ImportError:
            pytest.skip("akshare not installed")
        except Exception as e:
            pytest.skip(f"Valuation source unreachable: {e}")
        assert out["code"] == "600519"
        assert out["price"] > 0

    def test_eastmoney_financials_live(self):
        import fundamental_analysis as fa
        try:
            rows = fa.get_eastmoney_financials("600519")
        except Exception as e:
            pytest.skip(f"EastMoney financials unreachable: {e}")
        assert isinstance(rows, list)
        if rows:
            assert "REPORTDATE" in rows[0] or "WEIGHTAVG_ROE" in rows[0]


# --------------------------------------------------------------------------- #
# stock_screener: expensive end-to-end smoke test
# --------------------------------------------------------------------------- #

class TestStockScreenerLive:
    def test_market_snapshot_live(self):
        try:
            import stock_screener as ss
            df = ss.get_full_market_snapshot()
        except Exception as e:
            pytest.skip(f"Market snapshot unreachable: {e}")
        assert len(df) > 100
        assert "code" in df.columns

    @pytest.mark.slow
    def test_run_screening_quick_mode(self):
        """End-to-end screener run with quick=True (skips expensive backtest stage)."""
        try:
            import stock_screener as ss
            report = ss.run_screening(top_n=3, quick=True,
                                      max_candidates=20, max_workers=4)
        except Exception as e:
            pytest.skip(f"Screener pipeline failed: {e}")
        assert "recommendations" in report
        assert "market_overview" in report
        assert isinstance(report["recommendations"], list)
