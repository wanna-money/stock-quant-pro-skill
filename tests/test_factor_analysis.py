"""Unit tests for scripts/factor_analysis.py — pure-logic, no network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import factor_analysis as fa


pytestmark = pytest.mark.unit


@pytest.fixture
def long_ohlcv():
    """Factor module needs 252+ rows for 52w highs and 60d rolling IC — extend the fixture."""
    rng = np.random.default_rng(2024)
    n = 400
    dates = pd.bdate_range(end=pd.Timestamp("2025-12-31"), periods=n)
    log_returns = rng.normal(0.0005, 0.02, n)
    close = 100.0 * np.exp(np.cumsum(log_returns))
    open_ = np.concatenate([[100.0], close[:-1] * (1 + rng.normal(0, 0.003, n - 1))])
    amp = np.abs(rng.normal(0, 0.012, n))
    high = np.maximum(open_, close) * (1 + amp)
    low = np.minimum(open_, close) * (1 - amp)
    volume = rng.lognormal(14.0, 0.4, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestRSIHelper:
    def test_rsi_bounded_and_shape(self, long_ohlcv):
        r = fa._rsi(long_ohlcv["close"], 14).dropna()
        assert (r >= 0).all() and (r <= 100).all()
        assert len(r) > 0

    def test_rsi_all_gains_approaches_100(self):
        # Strongly up-trending with occasional small pullbacks so the loss
        # leg is non-zero (Wilder RSI divides by loss). RSI should saturate high.
        rng = np.random.default_rng(0)
        steps = rng.normal(1.5, 0.8, 300)  # mean +1.5, ~5% chance of negative
        close = pd.Series(100 + np.cumsum(steps))
        r = fa._rsi(close, 14).dropna()
        assert len(r) > 0
        assert r.iloc[-1] > 75


class TestFactorMomentum:
    def test_momentum_columns(self, long_ohlcv):
        f = fa.calc_factor_momentum(long_ohlcv)
        for col in ("mom_5d", "mom_10d", "mom_20d", "mom_60d", "mom_120d"):
            assert col in f.columns

    def test_momentum_matches_pct_change(self, long_ohlcv):
        f = fa.calc_factor_momentum(long_ohlcv, periods=[10])
        expected = long_ohlcv["close"].pct_change(10)
        pd.testing.assert_series_equal(f["mom_10d"], expected, check_names=False)


class TestFactorVolatility:
    def test_volatility_positive(self, long_ohlcv):
        f = fa.calc_factor_volatility(long_ohlcv).dropna()
        assert (f["vol_20d"] > 0).all()
        assert (f["vol_60d"] > 0).all()

    def test_vol_ratio_present(self, long_ohlcv):
        f = fa.calc_factor_volatility(long_ohlcv)
        assert "vol_ratio" in f.columns


class TestFactorVolume:
    def test_volume_schema(self, long_ohlcv):
        f = fa.calc_factor_volume(long_ohlcv)
        for col in ("vol_ma_ratio", "vol_change", "price_volume_corr",
                    "amihud_illiquidity", "amihud_20d"):
            assert col in f.columns

    def test_volume_no_infinities(self, long_ohlcv):
        f = fa.calc_factor_volume(long_ohlcv)
        assert not np.isinf(f["amihud_illiquidity"].dropna()).any()


class TestFactorTechnical:
    def test_technical_schema(self, long_ohlcv):
        f = fa.calc_factor_technical(long_ohlcv)
        for col in ("rsi_14", "price_to_ma20", "price_to_ma60", "ma20_slope",
                    "bb_position", "high_52w_pct", "range_52w_position"):
            assert col in f.columns

    def test_range_52w_position_within_bounds(self, long_ohlcv):
        f = fa.calc_factor_technical(long_ohlcv)
        vals = f["range_52w_position"].dropna()
        assert (vals >= -0.01).all() and (vals <= 1.01).all()

    def test_high_52w_pct_non_positive(self, long_ohlcv):
        f = fa.calc_factor_technical(long_ohlcv)
        vals = f["high_52w_pct"].dropna()
        assert (vals <= 1e-9).all()


class TestRollingSpearman:
    def test_rolling_spearman_monotonic_is_one(self):
        n = 100
        x = pd.Series(np.arange(n, dtype=float))
        y = pd.Series(np.arange(n, dtype=float) ** 2)
        r = fa._rolling_spearman(x, y, 30)
        assert len(r) > 0
        assert np.allclose(r.values, 1.0)


class TestEvaluateFactor:
    def test_insufficient_data(self):
        f = pd.Series(np.random.rand(20))
        r = pd.Series(np.random.rand(20))
        out = fa.evaluate_factor(f, r, name="tiny")
        assert "error" in out

    def test_evaluate_factor_schema(self, long_ohlcv):
        close = long_ohlcv["close"]
        mom = close.pct_change(10)
        forward = close.pct_change(5).shift(-5)
        out = fa.evaluate_factor(mom, forward, name="mom_10d")
        for k in ("name", "rank_ic", "rolling_ic_mean", "rolling_ic_std",
                  "icir", "quintile_returns_ann_pct", "long_short_return_ann_pct",
                  "is_effective"):
            assert k in out
        assert isinstance(out["is_effective"], bool)
        assert isinstance(out["quintile_returns_ann_pct"], dict)

    def test_perfect_factor_is_effective(self, long_ohlcv):
        """A factor strongly correlated with forward returns must pass is_effective.

        Note: using the identical series for both inputs produces constant
        rolling IC = 1.0 (zero std → icir = 0), so we add tiny noise so that
        rolling IC has non-zero variance and ICIR is well-defined.
        """
        rng = np.random.default_rng(7)
        forward = long_ohlcv["close"].pct_change(5).shift(-5)
        noise = pd.Series(rng.normal(0, 1e-4, len(forward)), index=forward.index)
        factor = forward + noise  # near-perfect correlation but non-degenerate
        out = fa.evaluate_factor(factor, forward, name="oracle")
        assert out["is_effective"] is True
        assert abs(out["rank_ic"]) > 0.9


class TestFullFactorAnalysis:
    def test_full_analysis_schema(self, long_ohlcv):
        r = fa.full_factor_analysis(long_ohlcv, forward_days=5)
        assert r["forward_period_days"] == 5
        assert set(r["factors"].keys()) == {"momentum", "volatility", "volume", "technical"}
        assert isinstance(r["effective_factors"], list)
        assert r["total_factors_tested"] > 0
        assert r["effective_count"] == len(r["effective_factors"])
        assert r["effective_count"] <= r["total_factors_tested"]

    def test_effective_factors_sorted_by_abs_icir(self, long_ohlcv):
        r = fa.full_factor_analysis(long_ohlcv, forward_days=5)
        eff = r["effective_factors"]
        if len(eff) >= 2:
            abs_icirs = [abs(e["icir"]) for e in eff]
            assert abs_icirs == sorted(abs_icirs, reverse=True)
