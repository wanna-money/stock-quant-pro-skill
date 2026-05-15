#!/usr/bin/env python3
"""
Portfolio optimization and allocation.
Supports: Equal Weight, Min Variance, Max Sharpe, Risk Parity.
"""
import sys
import json
import argparse
import pathlib

import pandas as pd
import numpy as np
from scipy.optimize import minimize

SCRIPT_DIR = str(pathlib.Path(__file__).parent)


def equal_weight(n_assets: int) -> np.ndarray:
    return np.ones(n_assets) / n_assets


def min_variance(cov_matrix: np.ndarray) -> np.ndarray:
    n = cov_matrix.shape[0]
    w0 = np.ones(n) / n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0, 1) for _ in range(n)]
    result = minimize(lambda w: w @ cov_matrix @ w, w0, method="SLSQP", bounds=bounds, constraints=constraints)
    return result.x if result.success else w0


def max_sharpe(mean_returns: np.ndarray, cov_matrix: np.ndarray,
               risk_free_rate: float = 0.03 / 252) -> np.ndarray:
    n = len(mean_returns)
    w0 = np.ones(n) / n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0, 1) for _ in range(n)]
    def neg_sharpe(w):
        port_return = w @ mean_returns
        port_vol = np.sqrt(w @ cov_matrix @ w)
        if port_vol < 1e-10:
            return float('-inf') if port_return > risk_free_rate else 0.0
        return -(port_return - risk_free_rate) / port_vol
    result = minimize(neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=constraints)
    return result.x if result.success else w0


def risk_parity(cov_matrix: np.ndarray) -> np.ndarray:
    n = cov_matrix.shape[0]
    w0 = np.ones(n) / n
    def objective(w):
        port_vol = np.sqrt(w @ cov_matrix @ w)
        if port_vol < 1e-10:
            return 0.0
        marginal_contrib = cov_matrix @ w
        risk_contrib = w * marginal_contrib / port_vol
        target = port_vol / n
        return np.sum((risk_contrib - target) ** 2)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.01, 1) for _ in range(n)]
    result = minimize(objective, w0, method="SLSQP", bounds=bounds, constraints=constraints)
    return result.x if result.success else w0


def evaluate_portfolio(weights: np.ndarray, returns_df: pd.DataFrame,
                       names: list[str], risk_free_rate: float = 0.03) -> dict:
    port_returns = (returns_df * weights).sum(axis=1)
    cum_returns = (1 + port_returns).cumprod()
    total_return = float(cum_returns.iloc[-1] - 1)
    n_days = len(port_returns)
    ann_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
    ann_vol = float(port_returns.std() * np.sqrt(252))
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0
    running_max = cum_returns.cummax()
    drawdowns = (cum_returns - running_max) / running_max
    max_dd = float(drawdowns.min())
    allocation = {names[i]: round(float(weights[i]) * 100, 2) for i in range(len(names))}
    cov_matrix = returns_df.cov().values * 252
    port_vol = float(np.sqrt(weights @ cov_matrix @ weights))
    if port_vol > 1e-10:
        marginal_contrib = cov_matrix @ weights
        risk_contrib = weights * marginal_contrib / port_vol
        rc_sum = risk_contrib.sum()
        risk_allocation = {names[i]: round(float(risk_contrib[i] / rc_sum) * 100, 2) if rc_sum > 0 else 0 for i in range(len(names))}
    else:
        risk_allocation = {names[i]: round(float(weights[i]) * 100, 2) for i in range(len(names))}
    return {
        "allocation_pct": allocation,
        "risk_contribution_pct": risk_allocation,
        "performance": {
            "total_return_pct": round(total_return * 100, 2),
            "annualized_return_pct": round(ann_return * 100, 2),
            "annualized_volatility_pct": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown_pct": round(max_dd * 100, 2),
        },
        "diversification_ratio": round(float((weights * np.sqrt(np.diag(cov_matrix))).sum() / port_vol), 4) if port_vol > 1e-10 else 1.0,
        "hhi_concentration": round(float(np.sum(weights ** 2)), 4),
    }


def optimize_portfolio(symbols: list[str], method: str = "max_sharpe",
                       start: str = None, end: str = None) -> dict:
    sys.path.insert(0, SCRIPT_DIR)
    from fetch_quotes import get_history
    all_prices = {}
    for sym in symbols:
        try:
            df = get_history(sym, start, end)
            all_prices[sym] = df["close"]
        except Exception as e:
            return {"error": f"Failed to fetch {sym}: {e}"}
    prices_df = pd.DataFrame(all_prices).dropna()
    if len(prices_df) < 60:
        return {"error": f"Insufficient overlapping data: {len(prices_df)} days (need 60+)"}
    returns_df = prices_df.pct_change().dropna()
    mean_returns = returns_df.mean().values
    cov_matrix = returns_df.cov().values
    methods_map = {
        "equal_weight": lambda: equal_weight(len(symbols)),
        "min_variance": lambda: min_variance(cov_matrix),
        "max_sharpe": lambda: max_sharpe(mean_returns, cov_matrix),
        "risk_parity": lambda: risk_parity(cov_matrix),
    }
    if method == "compare_all":
        results = {}
        for m_name, m_fn in methods_map.items():
            weights = m_fn()
            results[m_name] = evaluate_portfolio(weights, returns_df, symbols)
        return results
    weights = methods_map.get(method, methods_map["equal_weight"])()
    result = evaluate_portfolio(weights, returns_df, symbols)
    result["method"] = method
    result["data_period"] = {
        "start": str(prices_df.index[0].date()),
        "end": str(prices_df.index[-1].date()),
        "trading_days": len(prices_df),
    }
    corr_matrix = returns_df.corr()
    result["correlation_matrix"] = {
        symbols[i]: {symbols[j]: round(float(corr_matrix.iloc[i, j]), 4) for j in range(len(symbols))}
        for i in range(len(symbols))
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Portfolio optimization")
    parser.add_argument("symbols", nargs="+", help="Stock codes, e.g. sh600519 sh000300")
    parser.add_argument("--method", default="max_sharpe",
                        choices=["equal_weight", "min_variance", "max_sharpe", "risk_parity", "compare_all"])
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    args = parser.parse_args()
    result = optimize_portfolio(args.symbols, args.method, args.start, args.end)
    from json_utils import safe_json_dumps
    print(safe_json_dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
