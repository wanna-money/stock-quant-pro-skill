"""Unit tests for scripts/technical_analysis.py — pure-logic, no network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import technical_analysis as ta


pytestmark = pytest.mark.unit


class TestMovingAverages:
    def test_ma_columns_present_for_short_periods(self, synthetic_ohlcv):
        ma = ta.calc_ma(synthetic_ohlcv["close"], periods=[5, 10, 20])
        assert list(ma.columns) == ["MA5", "MA10", "MA20"]
        assert ma["MA5"].iloc[:4].isna().all()
        assert not np.isnan(ma["MA5"].iloc[-1])

    def test_ma_skips_periods_longer_than_data(self, synthetic_ohlcv_short):
        ma = ta.calc_ma(synthetic_ohlcv_short["close"], periods=[5, 60, 250])
        assert "MA5" in ma.columns
        assert "MA60" not in ma.columns
        assert "MA250" not in ma.columns

    def test_ma_numerically_matches_rolling_mean(self, synthetic_ohlcv):
        close = synthetic_ohlcv["close"]
        ma = ta.calc_ma(close, periods=[20])
        expected = close.rolling(20).mean()
        pd.testing.assert_series_equal(ma["MA20"], expected, check_names=False)


class TestMACD:
    def test_macd_shape_and_histogram_formula(self, synthetic_ohlcv):
        macd = ta.calc_macd(synthetic_ohlcv["close"])
        assert set(macd.columns) == {"DIF", "DEA", "MACD_Hist"}
        assert len(macd) == len(synthetic_ohlcv)
        tail = macd.dropna().tail(5)
        assert np.allclose(tail["MACD_Hist"], 2 * (tail["DIF"] - tail["DEA"]))


class TestRSI:
    def test_rsi_bounded_0_100(self, synthetic_ohlcv):
        rsi = ta.calc_rsi(synthetic_ohlcv["close"])
        vals = rsi.dropna().values
        assert (vals >= 0).all() and (vals <= 100).all()

    def test_rsi_all_gains_approaches_100(self):
        # Strongly up-trending with occasional small pullbacks (Wilder RSI
        # divides by loss, so we need some non-zero downside).
        rng = np.random.default_rng(0)
        steps = rng.normal(1.5, 0.8, 300)
        close = pd.Series(100 + np.cumsum(steps))
        rsi = ta.calc_rsi(close, periods=[14])["RSI14"].dropna()
        assert len(rsi) > 0
        assert rsi.iloc[-1] > 75


class TestKDJ:
    def test_kdj_j_equals_3k_minus_2d(self, synthetic_ohlcv):
        kdj = ta.calc_kdj(synthetic_ohlcv["high"], synthetic_ohlcv["low"], synthetic_ohlcv["close"])
        tail = kdj.dropna().tail(10)
        assert np.allclose(tail["J"], 3 * tail["K"] - 2 * tail["D"])


class TestBollinger:
    def test_bollinger_band_ordering(self, synthetic_ohlcv):
        bb = ta.calc_bollinger(synthetic_ohlcv["close"])
        tail = bb.dropna().tail(20)
        assert (tail["BB_Upper"] >= tail["BB_Mid"]).all()
        assert (tail["BB_Mid"] >= tail["BB_Lower"]).all()
        assert (tail["BB_Width"] >= 0).all()


class TestOBVATRVWAP:
    def test_obv_is_cumulative(self, synthetic_ohlcv):
        obv = ta.calc_obv(synthetic_ohlcv["close"], synthetic_ohlcv["volume"])
        assert len(obv) == len(synthetic_ohlcv)
        assert not np.isnan(obv.iloc[-1])

    def test_atr_non_negative(self, synthetic_ohlcv):
        atr = ta.calc_atr(synthetic_ohlcv["high"], synthetic_ohlcv["low"], synthetic_ohlcv["close"])
        assert (atr.dropna() >= 0).all()

    def test_vwap_within_price_envelope(self, synthetic_ohlcv):
        vwap = ta.calc_vwap(synthetic_ohlcv["high"], synthetic_ohlcv["low"],
                            synthetic_ohlcv["close"], synthetic_ohlcv["volume"])
        assert vwap.iloc[-1] <= synthetic_ohlcv["high"].max()
        assert vwap.iloc[-1] >= synthetic_ohlcv["low"].min()


class TestFullAnalysis:
    def test_full_analysis_schema(self, synthetic_ohlcv):
        result = ta.full_analysis(synthetic_ohlcv)
        for key in ("latest", "moving_averages", "trend", "macd", "rsi", "kdj",
                    "bollinger", "atr", "obv_trend", "support_resistance",
                    "patterns", "overall_signal", "signal_strength"):
            assert key in result, f"missing key: {key}"
        assert result["overall_signal"] in {"BUY", "SELL", "HOLD"}
        assert result["macd"]["signal"] in {"golden_cross", "death_cross", "bullish", "bearish"}
        assert result["rsi"]["signal"] in {"overbought", "oversold", "neutral"}
        assert 0 <= result["signal_strength"] <= 1
        sr = result["support_resistance"]
        assert sr["R2"] > sr["R1"] > sr["pivot"] > sr["S1"] > sr["S2"]

    def test_full_analysis_on_bearish_data(self, synthetic_ohlcv_bear):
        result = ta.full_analysis(synthetic_ohlcv_bear)
        bearish_hits = [result["trend"]["short"], result["macd"]["signal"]]
        assert any("bear" in str(s) for s in bearish_hits)

    def test_patterns_structure(self, synthetic_ohlcv):
        patterns = ta.detect_patterns(synthetic_ohlcv.tail(50))
        assert isinstance(patterns, list)
        for p in patterns:
            assert {"date", "pattern", "signal"} <= set(p.keys())
            assert p["signal"] in {"bullish", "bearish", "neutral"}


class TestRSIEdgeCases:
    def test_rsi_all_gains_equals_100(self):
        # When every price change is positive, loss EWMA = 0 → RS = inf → RSI = 100
        close = pd.Series([float(i) for i in range(1, 101)])
        rsi = ta.calc_rsi(close, periods=[14])["RSI14"].dropna()
        assert len(rsi) > 0
        assert (rsi == 100.0).any(), "RSI should reach 100 when all changes are gains"

    def test_rsi_no_nan_when_all_gains(self):
        close = pd.Series([float(i) for i in range(1, 101)])
        rsi = ta.calc_rsi(close, periods=[14])["RSI14"].dropna()
        assert not rsi.isna().any(), "RSI must not be NaN when all price changes are gains"
