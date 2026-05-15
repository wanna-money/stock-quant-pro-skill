"""Unit tests for scripts/backtest_engine.py — pure-logic, no network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest_engine as be


pytestmark = pytest.mark.unit


class TestStrategies:
    @pytest.mark.parametrize("strategy_name", list(be.STRATEGIES.keys()))
    def test_strategy_produces_expected_columns(self, synthetic_ohlcv, strategy_name):
        strat = be.STRATEGIES[strategy_name]
        result = strat(synthetic_ohlcv, lookback=20)
        for col in ("signal", "position", "strategy_return", "buy_hold_return"):
            assert col in result.columns, f"{strategy_name} missing {col}"
        assert result["signal"].isin([-1, 0, 1]).all()
        assert result["position"].isin([-1, 0, 1]).all()

    def test_momentum_position_starts_at_zero(self, synthetic_ohlcv):
        result = be.momentum_strategy(synthetic_ohlcv, lookback=20)
        assert result["position"].iloc[0] == 0

    def test_dual_ma_generates_trades(self, synthetic_ohlcv):
        result = be.dual_ma_crossover(synthetic_ohlcv, lookback=20, fast=5)
        pos_changes = result["position"].diff().fillna(0)
        assert (pos_changes != 0).sum() > 0


class TestCosts:
    def test_apply_costs_reduces_net_return_on_trade(self, synthetic_ohlcv):
        df = synthetic_ohlcv.copy()
        df["position"] = 0.0
        df.loc[df.index[50]:, "position"] = 1.0
        df["buy_hold_return"] = df["close"].pct_change()
        df = be._apply_costs(df)
        naive = df["position"] * df["close"].pct_change()
        assert df["strategy_return"].iloc[50] < naive.iloc[50]

    def test_stamp_tax_on_sell_only(self, synthetic_ohlcv):
        df = synthetic_ohlcv.head(100).copy()
        df["position"] = 0.0
        df.loc[df.index[20]:df.index[40], "position"] = 1.0
        df["buy_hold_return"] = df["close"].pct_change()
        df = be._apply_costs(df)
        naive_ret = df["position"] * df["close"].pct_change()
        entry_cost = naive_ret.iloc[20] - df["strategy_return"].iloc[20]
        exit_cost = naive_ret.iloc[41] - df["strategy_return"].iloc[41]
        assert exit_cost > entry_cost


class TestEvaluate:
    def test_evaluate_schema(self, synthetic_ohlcv):
        result = be.momentum_strategy(synthetic_ohlcv, lookback=20)
        metrics = be.evaluate_strategy(result)
        for k in ("strategy", "benchmark", "excess_return_pct", "trading_days", "period", "costs_applied"):
            assert k in metrics
        s = metrics["strategy"]
        for k in ("total_return_pct", "annualized_return_pct", "sharpe_ratio",
                  "sortino_ratio", "max_drawdown_pct", "calmar_ratio",
                  "win_rate_pct", "profit_factor", "total_trades", "annual_turnover"):
            assert k in s

    def test_evaluate_empty_returns(self):
        df = pd.DataFrame({
            "close": [100.0] * 5, "high": [100.0] * 5, "low": [100.0] * 5,
            "open": [100.0] * 5, "volume": [0.0] * 5,
            "position": [0] * 5,
            "strategy_return": [np.nan] * 5,
            "buy_hold_return": [np.nan] * 5,
        }, index=pd.bdate_range(end="2025-12-31", periods=5))
        out = be.evaluate_strategy(df)
        assert "error" in out

    def test_max_drawdown_non_positive(self, synthetic_ohlcv):
        result = be.momentum_strategy(synthetic_ohlcv, lookback=20)
        m = be.evaluate_strategy(result)
        assert m["strategy"]["max_drawdown_pct"] <= 0

    def test_back_to_back_flip_counted_as_two_trades(self):
        """Regression: -1 -> +1 without passing through 0 must count as two trades."""
        idx = pd.bdate_range(end="2025-12-31", periods=10)
        df = pd.DataFrame({
            "open": [10.0] * 10, "high": [11.0] * 10, "low": [9.0] * 10,
            "close": [10.0, 11, 12, 11, 10, 9, 10, 11, 12, 13],
            "volume": [100.0] * 10,
        }, index=idx)
        df["position"] = [-1, -1, -1, 1, 1, 1, 1, 1, 1, 0]
        df["buy_hold_return"] = df["close"].pct_change()
        df = be._apply_costs(df)
        m = be.evaluate_strategy(df)
        assert m["strategy"]["total_trades"] == 2


class TestRegistry:
    def test_all_strategies_present(self):
        assert set(be.STRATEGIES.keys()) == {"momentum", "reversal", "bollinger", "breakout", "dual_ma"}
