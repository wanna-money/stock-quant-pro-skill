"""Unit tests for scripts/risk_analysis.py — pure-logic, no network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import risk_analysis as ra


pytestmark = pytest.mark.unit


class TestReturns:
    def test_log_vs_simple_returns_close(self, synthetic_ohlcv):
        log_ret = ra.calc_returns(synthetic_ohlcv["close"], "log")
        simple_ret = ra.calc_returns(synthetic_ohlcv["close"], "simple")
        assert len(log_ret) == len(simple_ret) == len(synthetic_ohlcv) - 1
        assert (simple_ret - log_ret).abs().mean() < 0.001


class TestVaR:
    def test_var_values_are_positive(self, synthetic_returns):
        for fn in (ra.var_historical, ra.var_parametric, ra.var_montecarlo):
            v = fn(synthetic_returns, 0.95)
            assert v > 0, f"{fn.__name__} returned non-positive VaR: {v}"

    def test_var_99_greater_than_var_95(self, synthetic_returns):
        assert ra.var_historical(synthetic_returns, 0.99) >= ra.var_historical(synthetic_returns, 0.95)
        assert ra.var_parametric(synthetic_returns, 0.99) >= ra.var_parametric(synthetic_returns, 0.95)

    def test_cvar_ge_var(self, synthetic_returns):
        var95 = ra.var_historical(synthetic_returns, 0.95)
        c95 = ra.cvar(synthetic_returns, 0.95)
        assert c95 >= var95 - 1e-9


class TestDrawdown:
    def test_max_drawdown_bounds(self, synthetic_ohlcv):
        md = ra.max_drawdown(synthetic_ohlcv["close"])
        assert -1.0 <= md["max_drawdown"] <= 0.0
        assert md["peak_date"] <= md["trough_date"]

    def test_monotonic_series_zero_drawdown(self):
        prices = pd.Series(np.linspace(100, 200, 100),
                           index=pd.bdate_range(end="2025-12-31", periods=100))
        md = ra.max_drawdown(prices)
        assert md["max_drawdown"] == 0.0


class TestVolatility:
    def test_historical_vol_annualized_reasonable(self, synthetic_returns):
        vol = ra.historical_volatility(synthetic_returns, 20, annualize=True).dropna()
        assert (vol > 0).all()
        assert 0.05 < vol.iloc[-1] < 2.0

    def test_ewma_non_nan_tail(self, synthetic_returns):
        vol = ra.ewma_volatility(synthetic_returns)
        assert not np.isnan(vol.iloc[-1])


class TestPerformanceRatios:
    def test_sharpe_runs_on_constant_returns(self):
        # On identical returns, std() is effectively 0 (floating noise only),
        # so the function may return 0 or a large finite value depending on
        # the guard. Just check it does not raise.
        const_returns = pd.Series([0.001] * 252)
        result = ra.sharpe_ratio(const_returns)
        assert isinstance(result, float)

    def test_sortino_runs(self, synthetic_returns):
        s = ra.sortino_ratio(synthetic_returns)
        assert isinstance(s, float)

    def test_calmar_is_float(self, synthetic_ohlcv):
        returns = synthetic_ohlcv["close"].pct_change().dropna()
        calmar = ra.calmar_ratio(returns, synthetic_ohlcv["close"])
        assert isinstance(calmar, float)

    def test_information_ratio_zero_tracking_error(self):
        r = pd.Series([0.01] * 100)
        assert ra.information_ratio(r, r) == 0

    def test_alpha_beta_schema(self, synthetic_ohlcv, synthetic_ohlcv_bear):
        r = synthetic_ohlcv["close"].pct_change().dropna()
        b = synthetic_ohlcv_bear["close"].pct_change().dropna()
        out = ra.alpha_beta(r, b)
        assert set(out.keys()) >= {"alpha_daily", "alpha_annualized", "beta", "r_squared", "p_value"}
        assert isinstance(out["beta"], float)

    def test_alpha_beta_insufficient_data(self):
        r = pd.Series(np.random.rand(10))
        b = pd.Series(np.random.rand(10))
        out = ra.alpha_beta(r, b)
        assert out["beta"] is None
        assert "error" in out


class TestTailRisk:
    def test_tail_risk_schema(self, synthetic_returns):
        tr = ra.tail_risk_metrics(synthetic_returns)
        for k in ("skewness", "kurtosis", "jarque_bera_stat", "jarque_bera_pvalue",
                  "is_normal", "tail_ratio"):
            assert k in tr
        assert isinstance(tr["is_normal"], bool)


class TestFullRiskReport:
    def test_full_report_schema(self, synthetic_ohlcv):
        report = ra.full_risk_report(synthetic_ohlcv["close"])
        assert "VaR_95%" in report and "VaR_99%" in report
        assert set(report["VaR_95%"].keys()) >= {"historical", "parametric", "montecarlo", "CVaR"}
        assert "max_drawdown" in report
        assert "volatility" in report
        assert "performance" in report
        perf = report["performance"]
        assert "sharpe_ratio" in perf and "sortino_ratio" in perf and "calmar_ratio" in perf
        assert "tail_risk" in report
        assert "data_info" in report

    def test_full_report_with_benchmark(self, synthetic_ohlcv, synthetic_ohlcv_bear):
        report = ra.full_risk_report(synthetic_ohlcv["close"], synthetic_ohlcv_bear["close"])
        assert "alpha_beta" in report
        assert "information_ratio" in report


class TestMaxDrawdownEdgeCases:
    def test_monotonically_declining_prices(self):
        # Trough is at index 0 → peak_candidates is empty — must not raise ValueError
        prices = pd.Series([100.0, 90.0, 80.0, 70.0, 60.0],
                           index=pd.bdate_range(end="2025-12-31", periods=5))
        md = ra.max_drawdown(prices)
        assert md["max_drawdown"] <= 0.0
        assert md["max_drawdown_pct"] <= 0.0

    def test_zero_start_price_returns_safe_dict(self):
        prices = pd.Series([0.0, 10.0, 20.0],
                           index=pd.bdate_range(end="2025-12-31", periods=3))
        md = ra.max_drawdown(prices)
        assert md["max_drawdown"] == 0
        assert md["max_drawdown_pct"] == 0

    def test_single_price_returns_safe_dict(self):
        prices = pd.Series([100.0], index=pd.bdate_range(end="2025-12-31", periods=1))
        md = ra.max_drawdown(prices)
        assert md["max_drawdown"] == 0
