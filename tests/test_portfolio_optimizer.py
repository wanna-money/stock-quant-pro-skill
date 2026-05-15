"""Unit tests for scripts/portfolio_optimizer.py — pure-logic, no network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import portfolio_optimizer as po


pytestmark = pytest.mark.unit


TOL = 1e-6


class TestEqualWeight:
    def test_equal_weight_sums_to_one(self):
        w = po.equal_weight(5)
        assert w.shape == (5,)
        assert abs(w.sum() - 1.0) < TOL
        assert np.allclose(w, 0.2)


class TestMinVariance:
    def test_weights_sum_to_one_and_non_negative(self, multi_asset_prices):
        cov = multi_asset_prices.pct_change().dropna().cov().values
        w = po.min_variance(cov)
        assert abs(w.sum() - 1.0) < 1e-4
        assert (w >= -1e-6).all()

    def test_min_variance_prefers_low_vol_asset(self):
        # 3 uncorrelated assets with very different variances.
        cov = np.diag([0.0001, 0.01, 0.04])
        w = po.min_variance(cov)
        assert w[0] > w[1] > w[2]


class TestMaxSharpe:
    def test_max_sharpe_weights_valid(self, multi_asset_prices):
        returns = multi_asset_prices.pct_change().dropna()
        w = po.max_sharpe(returns.mean().values, returns.cov().values)
        assert abs(w.sum() - 1.0) < 1e-4
        assert (w >= -1e-6).all() and (w <= 1 + 1e-6).all()

    def test_max_sharpe_favors_higher_return_when_cov_equal(self):
        mean_ret = np.array([0.0002, 0.0010, 0.0020])
        cov = np.eye(3) * 0.0004
        w = po.max_sharpe(mean_ret, cov, risk_free_rate=0.0)
        assert w[2] > w[0]


class TestRiskParity:
    def test_risk_parity_weights_sum_to_one(self, multi_asset_prices):
        cov = multi_asset_prices.pct_change().dropna().cov().values
        w = po.risk_parity(cov)
        assert abs(w.sum() - 1.0) < 1e-4
        assert (w >= 0.01 - 1e-6).all()

    def test_risk_parity_equalizes_risk_contrib(self):
        # For a diagonal cov, risk parity should yield inverse-vol weights.
        cov = np.diag([0.01, 0.04, 0.09])
        w = po.risk_parity(cov)
        port_vol = np.sqrt(w @ cov @ w)
        rc = w * (cov @ w) / port_vol
        # each asset contributes roughly the same risk (within SLSQP tolerance)
        assert rc.std() / rc.mean() < 0.05


class TestEvaluatePortfolio:
    def test_evaluate_schema(self, multi_asset_prices):
        returns = multi_asset_prices.pct_change().dropna()
        weights = np.array([1 / 3] * 3)
        names = list(returns.columns)
        result = po.evaluate_portfolio(weights, returns, names)
        for k in ("allocation_pct", "risk_contribution_pct", "performance",
                 "diversification_ratio", "hhi_concentration"):
            assert k in result
        for k in ("total_return_pct", "annualized_return_pct",
                  "annualized_volatility_pct", "sharpe_ratio", "max_drawdown_pct"):
            assert k in result["performance"]

    def test_allocation_pct_sums_to_100(self, multi_asset_prices):
        returns = multi_asset_prices.pct_change().dropna()
        weights = np.array([0.5, 0.3, 0.2])
        result = po.evaluate_portfolio(weights, returns, list(returns.columns))
        assert abs(sum(result["allocation_pct"].values()) - 100.0) < 0.05

    def test_max_drawdown_non_positive(self, multi_asset_prices):
        returns = multi_asset_prices.pct_change().dropna()
        weights = np.array([1 / 3] * 3)
        result = po.evaluate_portfolio(weights, returns, list(returns.columns))
        assert result["performance"]["max_drawdown_pct"] <= 0

    def test_hhi_matches_formula(self, multi_asset_prices):
        returns = multi_asset_prices.pct_change().dropna()
        weights = np.array([0.6, 0.3, 0.1])
        result = po.evaluate_portfolio(weights, returns, list(returns.columns))
        expected_hhi = round(float(np.sum(weights ** 2)), 4)
        assert result["hhi_concentration"] == expected_hhi
