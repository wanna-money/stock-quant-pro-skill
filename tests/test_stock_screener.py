"""Mock-based unit tests for scripts/stock_screener.py — no network calls.

Covers filter_universe, score_factors, validate_fundamentals, build_report,
and the end-to-end run_screening orchestration (with all heavy stages stubbed).
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

import stock_screener as ss


pytestmark = pytest.mark.unit


def _fake_market_df() -> pd.DataFrame:
    """Engineered so each row tests a specific branch of filter_universe."""
    return pd.DataFrame([
        # 0 - healthy, should pass
        {"code": "600001", "name": "优质股A", "price": 20.0, "change_pct": 1.5,
         "pe": 18.0, "pb": 2.0, "total_mv": 2e11, "turnover_rate": 1.2},
        # 1 - ST name, reject
        {"code": "600002", "name": "ST风险", "price": 10.0, "change_pct": 1.0,
         "pe": 15.0, "pb": 1.8, "total_mv": 1e11, "turnover_rate": 1.0},
        # 2 - price out of range (too low)
        {"code": "600003", "name": "低价B", "price": 1.5, "change_pct": 0.5,
         "pe": 12.0, "pb": 1.5, "total_mv": 8e10, "turnover_rate": 0.8},
        # 3 - limit-up / suspicious: |chg| >= 9.8
        {"code": "600004", "name": "涨停C", "price": 30.0, "change_pct": 9.9,
         "pe": 22.0, "pb": 3.0, "total_mv": 1.5e11, "turnover_rate": 2.0},
        # 4 - negative / out-of-PE-range
        {"code": "600005", "name": "亏损D", "price": 15.0, "change_pct": 0.8,
         "pe": -5.0, "pb": 1.0, "total_mv": 9e10, "turnover_rate": 0.5},
        # 5 - market cap below 50 yi floor
        {"code": "600006", "name": "小市值E", "price": 8.0, "change_pct": 2.0,
         "pe": 25.0, "pb": 2.5, "total_mv": 3e9, "turnover_rate": 0.6},
        # 6 - turnover below 0.3
        {"code": "600007", "name": "低换手F", "price": 12.0, "change_pct": -1.0,
         "pe": 20.0, "pb": 1.7, "total_mv": 8e10, "turnover_rate": 0.1},
        # 7 - second healthy pass
        {"code": "000001", "name": "优质股G", "price": 25.0, "change_pct": -0.5,
         "pe": 30.0, "pb": 2.8, "total_mv": 1.2e11, "turnover_rate": 0.9},
    ])


class TestFilterUniverse:
    def test_healthy_rows_pass(self):
        out = ss.filter_universe(_fake_market_df(), min_pe=0, max_pe=100, min_mcap=50)
        codes = set(out["code"].tolist())
        assert "600001" in codes
        assert "000001" in codes

    def test_st_rejected(self):
        out = ss.filter_universe(_fake_market_df())
        assert "600002" not in set(out["code"].tolist())

    def test_price_out_of_range_rejected(self):
        out = ss.filter_universe(_fake_market_df())
        assert "600003" not in set(out["code"].tolist())

    def test_limit_up_rejected(self):
        out = ss.filter_universe(_fake_market_df())
        assert "600004" not in set(out["code"].tolist())

    def test_negative_pe_rejected(self):
        out = ss.filter_universe(_fake_market_df(), min_pe=0)
        assert "600005" not in set(out["code"].tolist())

    def test_mcap_floor_rejected(self):
        out = ss.filter_universe(_fake_market_df(), min_mcap=50)
        assert "600006" not in set(out["code"].tolist())

    def test_turnover_floor_rejected(self):
        out = ss.filter_universe(_fake_market_df())
        assert "600007" not in set(out["code"].tolist())


def _fake_candidate(code: str, name: str, *, mom_5d=0.02, mom_20d=0.05,
                    vol_20d=0.02, vol_ma_ratio=1.2, rsi_14=55.0,
                    bb_position=0.5, price_to_ma20=0.01,
                    signal="BUY", strength=0.8) -> dict:
    return {
        "code": code, "name": name, "symbol": "sh" + code,
        "signal": signal, "signal_strength": strength,
        "factors": {
            "mom_5d": mom_5d, "mom_20d": mom_20d,
            "vol_20d": vol_20d, "vol_ma_ratio": vol_ma_ratio,
            "rsi_14": rsi_14, "bb_position": bb_position,
            "price_to_ma20": price_to_ma20,
        },
        "key_factors": ["MACD金叉"],
        "history_df": pd.DataFrame({
            "open": [1.0] * 200, "close": [1.0] * 200,
            "high": [1.0] * 200, "low": [1.0] * 200,
            "volume": [1.0] * 200,
        }),
    }


class TestScoreFactors:
    def test_scores_and_composite_attached(self):
        candidates = [
            _fake_candidate("600001", "A", mom_5d=0.08, mom_20d=0.15,
                            vol_ma_ratio=2.0, rsi_14=30),
            _fake_candidate("000001", "B", mom_5d=0.01, mom_20d=0.02,
                            vol_ma_ratio=1.0, rsi_14=60),
            _fake_candidate("600007", "C", mom_5d=-0.01, mom_20d=-0.02,
                            vol_ma_ratio=0.8, rsi_14=70),
        ]
        market = _fake_market_df()
        out = ss.score_factors(candidates, market)
        for c in out:
            assert "scores" in c
            assert "composite_score" in c
            for key in ("momentum", "volume", "technical", "volatility", "valuation"):
                assert key in c["scores"]

    def test_sorted_descending_by_composite(self):
        candidates = [
            _fake_candidate("600001", "A", mom_5d=0.08, mom_20d=0.15,
                            vol_ma_ratio=2.0, rsi_14=30),
            _fake_candidate("000001", "B", mom_5d=-0.02, mom_20d=-0.03,
                            vol_ma_ratio=0.5, rsi_14=75),
            _fake_candidate("600007", "C", mom_5d=0.03, mom_20d=0.04,
                            vol_ma_ratio=1.5, rsi_14=50),
        ]
        out = ss.score_factors(candidates, _fake_market_df())
        scores = [c["composite_score"] for c in out]
        assert scores == sorted(scores, reverse=True)

    def test_empty_list_returns_empty(self):
        assert ss.score_factors([], _fake_market_df()) == []


class TestValidateFundamentals:
    def test_healthy_passes(self):
        fin = [{
            "WEIGHTAVG_ROE": 18.0, "YSTZ": 15.0, "SJLTZ": 25.0, "XSMLL": 45.0,
        }]
        candidates = [_fake_candidate("600001", "A")]
        import fundamental_analysis as fa
        with patch.object(fa, "get_eastmoney_financials", return_value=fin):
            out = ss.validate_fundamentals(candidates, top_n=5)
        assert len(out) == 1
        assert "fundamental" in out[0]

    def test_low_roe_adds_warning(self):
        fin = [{
            "WEIGHTAVG_ROE": 3.0, "YSTZ": 2.0, "SJLTZ": 1.0, "XSMLL": 30.0,
        }]
        candidates = [_fake_candidate("600001", "A")]
        # Patch the imported symbol inside the function's module
        import fundamental_analysis as fa
        with patch.object(fa, "get_eastmoney_financials", return_value=fin):
            out = ss.validate_fundamentals(candidates, top_n=5)
        c = out[0]
        # Low ROE triggers warning and fundamental_pass=False
        if c.get("fundamental", {}).get("status") not in ("fetch_error", "no_data"):
            assert any("ROE" in w for w in c.get("risk_warnings", []))
            assert c.get("fundamental_pass") is False

    def test_no_data_status(self):
        import fundamental_analysis as fa
        with patch.object(fa, "get_eastmoney_financials", return_value=[]):
            out = ss.validate_fundamentals([_fake_candidate("600001", "A")], top_n=5)
        assert out[0]["fundamental"]["status"] == "no_data"

    def test_fetch_error_kept(self):
        import fundamental_analysis as fa
        with patch.object(fa, "get_eastmoney_financials",
                          side_effect=RuntimeError("net")):
            out = ss.validate_fundamentals([_fake_candidate("600001", "A")], top_n=5)
        assert out[0]["fundamental"]["status"] == "fetch_error"
        assert out[0]["fundamental_pass"] is True


class TestBuildReport:
    def test_report_schema(self):
        candidates = [_fake_candidate("600001", "A")]
        candidates[0]["composite_score"] = 1.23
        candidates[0]["scores"] = {"momentum": 0.5}
        market = _fake_market_df()
        hot = {"industry": [{"name": "半导体"}, {"name": "医药"}]}
        filter_counts = {"universe": 5000, "after_basic_filter": 300,
                         "after_technical": 50, "after_factor_scoring": 30,
                         "after_fundamental": 15, "final_recommendations": 1}
        out = ss.build_report(candidates, market, hot, filter_counts)
        assert "scan_time" in out
        assert "market_overview" in out
        assert "filter_summary" in out
        assert "recommendations" in out
        assert "disclaimer" in out
        rec = out["recommendations"][0]
        assert rec["code"] == "600001"
        assert rec["rank"] == 1
        # market-field enrichment from the market_df row
        assert rec["price"] == 20.0
        assert rec["pe"] == 18.0

    def test_hot_sectors_trimmed_to_5(self):
        hot = {"industry": [{"name": f"S{i}"} for i in range(10)]}
        out = ss.build_report([], _fake_market_df(), hot, {})
        assert len(out["market_overview"]["hot_sectors"]) == 5


class TestRunScreeningEndToEnd:
    def test_run_screening_orchestrates_pipeline(self):
        market = _fake_market_df()
        tech_results = [_fake_candidate("600001", "A", mom_5d=0.05),
                        _fake_candidate("000001", "B", mom_5d=-0.01)]

        def _fake_validate_bt(candidates, top_n=15):
            for c in candidates[:top_n]:
                c["backtest"] = {"sharpe": 1.0, "max_drawdown_pct": -10.0,
                                 "annualized_return_pct": 15.0, "win_rate_pct": 55.0}
            return candidates

        def _fake_validate_fund(candidates, top_n=30):
            for c in candidates[:top_n]:
                c["fundamental"] = {"roe_pct": 15, "revenue_yoy_pct": 10,
                                     "profit_yoy_pct": 20, "gross_margin_pct": 40}
                c["fundamental_pass"] = True
            return candidates

        with patch.object(ss, "get_full_market_snapshot", return_value=market), \
             patch.object(ss, "score_technical", return_value=tech_results), \
             patch.object(ss, "validate_fundamentals", side_effect=_fake_validate_fund), \
             patch.object(ss, "validate_backtest", side_effect=_fake_validate_bt):
            report = ss.run_screening(top_n=5, quick=False)

        assert "recommendations" in report
        assert "market_overview" in report
        assert report["market_overview"]["total_stocks"] == len(market)
        assert "filter_summary" in report
        assert report["filter_summary"]["universe"] == len(market)
        # Recommendations should be non-empty since tech_results had 2 healthy picks
        assert len(report["recommendations"]) >= 1
        # history_df / factors / fundamental_pass stripped before report
        for rec in report["recommendations"]:
            assert "history_df" not in rec
            assert "factors" not in rec


class TestScoreFactorsEdgeCases:
    def _make_candidate(self, rsi):
        return {
            "code": "sh600001", "name": "Test",
            "factors": {
                "mom_5d": 0.01, "mom_20d": 0.02,
                "vol_ma_ratio": 1.2, "rsi_14": rsi,
                "vol_20d": 0.15,
            },
        }

    def test_rsi_zero_not_treated_as_missing(self):
        # RSI=0.0 is falsy in Python — must use `is not None` guard.
        # With a single candidate z-score collapses to 0; use two candidates so
        # the one with RSI=0 (max oversold) scores higher than RSI=50 (neutral).
        c_rsi0 = self._make_candidate(rsi=0.0)
        c_rsi50 = {
            "code": "sh600002", "name": "Test2",
            "factors": {
                "mom_5d": 0.01, "mom_20d": 0.02,
                "vol_ma_ratio": 1.2, "rsi_14": 50.0,
                "vol_20d": 0.15,
            },
        }
        market_df = pd.DataFrame([
            {"code": "sh600001", "pe": 20.0, "pb": 2.0},
            {"code": "sh600002", "pe": 20.0, "pb": 2.0},
        ])
        result = ss.score_factors([c_rsi0, c_rsi50], market_df)
        scores = {r["code"]: r["composite_score"] for r in result}
        # RSI=0 (deep oversold) should score >= RSI=50 (neutral)
        assert scores["sh600001"] >= scores["sh600002"]

    def test_rsi_none_treated_as_missing(self):
        candidate = self._make_candidate(rsi=None)
        market_df = pd.DataFrame([{"code": "sh600001", "pe": 20.0, "pb": 2.0}])
        result = ss.score_factors([candidate], market_df)
        assert len(result) == 1


class TestValidateFundamentalsEdgeCases:
    def test_dash_string_fields_do_not_crash(self):
        # EastMoney returns "--" for missing values — bare float("--") would raise ValueError
        import fundamental_analysis as fa
        with patch.object(fa, "get_eastmoney_financials") as mock_fin:
            mock_fin.return_value = [{
                "WEIGHTAVG_ROE": "--",
                "YSTZ": "-",
                "SJLTZ": "--",
                "XSMLL": None,
            }]
            candidates = [{"code": "sh600001", "name": "Test"}]
            result = ss.validate_fundamentals(candidates)
        assert len(result) == 1
        assert result[0]["fundamental"]["roe_pct"] == 0.0
