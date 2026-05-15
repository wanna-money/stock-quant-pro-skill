#!/usr/bin/env python3
"""
Risk analysis: VaR, CVaR, Max Drawdown, Volatility, Sharpe/Sortino/Calmar ratios.
Implements three VaR methods: Historical Simulation, Parametric, Monte Carlo.
"""
import sys
import argparse
import json
import pathlib
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from scipy import stats

SCRIPT_DIR = str(pathlib.Path(__file__).parent)


def calc_returns(prices: pd.Series, method: str = "log") -> pd.Series:
    if method == "log":
        return np.log(prices / prices.shift(1)).dropna()
    return prices.pct_change().dropna()


# ---------------------------------------------------------------------------
# Value at Risk
# ---------------------------------------------------------------------------

def var_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    return float(-np.percentile(returns, (1 - confidence) * 100))


def var_parametric(returns: pd.Series, confidence: float = 0.95) -> float:
    mu = returns.mean()
    sigma = returns.std()
    z = stats.norm.ppf(1 - confidence)
    return float(-(mu + z * sigma))


def var_montecarlo(returns: pd.Series, confidence: float = 0.95,
                   n_simulations: int = 10000, horizon: int = 1) -> float:
    mu = returns.mean()
    sigma = returns.std()
    rng = np.random.default_rng(42)
    simulated = rng.normal(mu * horizon, sigma * np.sqrt(horizon), n_simulations)
    return float(-np.percentile(simulated, (1 - confidence) * 100))


def cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall)."""
    var = var_historical(returns, confidence)
    tail = returns[returns <= -var]
    return float(-tail.mean()) if len(tail) > 0 else var


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------

def max_drawdown(prices: pd.Series) -> dict:
    if len(prices) < 2 or prices.iloc[0] == 0:
        return {
            "max_drawdown": 0, "max_drawdown_pct": 0,
            "peak_date": None, "trough_date": None,
            "recovery_date": None, "drawdown_duration_days": None,
        }
    cumulative = prices / prices.iloc[0]
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    mdd = float(drawdown.min())
    trough_idx = drawdown.idxmin()
    peak_candidates = cumulative[:trough_idx]
    peak_idx = peak_candidates.idxmax() if not peak_candidates.empty else cumulative.index[0]
    recovery_candidates = cumulative[trough_idx:]
    recovery_vals = recovery_candidates[recovery_candidates >= cumulative[peak_idx]]
    recovery_idx = recovery_vals.index[0] if len(recovery_vals) > 0 else None
    return {
        "max_drawdown": round(mdd, 4),
        "max_drawdown_pct": round(mdd * 100, 2),
        "peak_date": str(peak_idx.date()) if hasattr(peak_idx, "date") else str(peak_idx),
        "trough_date": str(trough_idx.date()) if hasattr(trough_idx, "date") else str(trough_idx),
        "recovery_date": str(recovery_idx.date()) if recovery_idx is not None and hasattr(recovery_idx, "date") else None,
        "drawdown_duration_days": (trough_idx - peak_idx).days if hasattr(peak_idx, "date") else None,
    }


def drawdown_series(prices: pd.Series) -> pd.Series:
    running_max = prices.cummax()
    return (prices - running_max) / running_max


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------

def historical_volatility(returns: pd.Series, window: int = 20, annualize: bool = True) -> pd.Series:
    vol = returns.rolling(window).std()
    if annualize:
        vol = vol * np.sqrt(252)
    return vol


def ewma_volatility(returns: pd.Series, lam: float = 0.94, annualize: bool = True) -> pd.Series:
    vol = returns.ewm(alpha=1 - lam, adjust=False).std()
    if annualize:
        vol = vol * np.sqrt(252)
    return vol


# ---------------------------------------------------------------------------
# Performance ratios
# ---------------------------------------------------------------------------

def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.03, periods: int = 252) -> float:
    excess_return = returns.mean() - risk_free_rate / periods
    return float(excess_return / returns.std() * np.sqrt(periods)) if returns.std() > 0 else 0


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.03, periods: int = 252) -> float:
    excess_daily = returns - risk_free_rate / periods
    downside_diff = np.minimum(excess_daily, 0)
    downside_dev = float(np.sqrt((downside_diff ** 2).mean()) * np.sqrt(periods))
    if downside_dev <= 0:
        return 0.0
    ann_return = float(returns.mean() * periods)
    return float((ann_return - risk_free_rate) / downside_dev)


def calmar_ratio(returns: pd.Series, prices: pd.Series) -> float:
    n_days = len(returns)
    total_return = float(prices.iloc[-1] / prices.iloc[0] - 1)
    ann_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
    mdd = abs(max_drawdown(prices)["max_drawdown"])
    return float(ann_return / mdd) if mdd > 0 else 0


def information_ratio(returns: pd.Series, benchmark_returns: pd.Series, periods: int = 252) -> float:
    active = returns - benchmark_returns
    tracking_error = active.std()
    return float(active.mean() / tracking_error * np.sqrt(periods)) if tracking_error > 0 else 0


def alpha_beta(returns: pd.Series, benchmark_returns: pd.Series, risk_free_rate: float = 0.03) -> dict:
    """CAPM alpha and beta via OLS regression."""
    aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 30:
        return {"alpha": None, "beta": None, "r_squared": None, "error": "Insufficient data"}
    y = aligned.iloc[:, 0] - risk_free_rate / 252
    x = aligned.iloc[:, 1] - risk_free_rate / 252
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "alpha_daily": round(float(intercept), 6),
        "alpha_annualized": round(float(intercept * 252), 4),
        "beta": round(float(slope), 4),
        "r_squared": round(float(r_value ** 2), 4),
        "p_value": round(float(p_value), 6),
    }


# ---------------------------------------------------------------------------
# Tail risk
# ---------------------------------------------------------------------------

def tail_risk_metrics(returns: pd.Series) -> dict:
    skew = float(returns.skew())
    kurt = float(returns.kurtosis())
    jb_stat, jb_pvalue = stats.jarque_bera(returns.dropna())
    gain_95 = float(np.percentile(returns, 95))
    loss_5 = float(abs(np.percentile(returns, 5)))
    tail_ratio = gain_95 / loss_5 if loss_5 > 0 else float("inf")
    return {
        "skewness": round(skew, 4),
        "kurtosis": round(kurt, 4),
        "jarque_bera_stat": round(float(jb_stat), 4),
        "jarque_bera_pvalue": round(float(jb_pvalue), 6),
        "is_normal": bool(jb_pvalue > 0.05),
        "tail_ratio": round(tail_ratio, 4),
    }


# ---------------------------------------------------------------------------
# Full risk report
# ---------------------------------------------------------------------------

def full_risk_report(prices: pd.Series, benchmark_prices: pd.Series = None,
                     risk_free_rate: float = 0.03) -> dict:
    """Generate comprehensive risk report from price series."""
    returns = calc_returns(prices, "simple")
    report = {}

    for conf in [0.95, 0.99]:
        label = f"{int(conf * 100)}%"
        report[f"VaR_{label}"] = {
            "historical": round(var_historical(returns, conf) * 100, 4),
            "parametric": round(var_parametric(returns, conf) * 100, 4),
            "montecarlo": round(var_montecarlo(returns, conf) * 100, 4),
            "CVaR": round(cvar(returns, conf) * 100, 4),
            "unit": "% daily",
        }

    report["max_drawdown"] = max_drawdown(prices)

    vol_20 = historical_volatility(returns, 20)
    vol_60 = historical_volatility(returns, 60)
    report["volatility"] = {
        "daily": round(float(returns.std()) * 100, 4),
        "annualized_20d": round(float(vol_20.iloc[-1]) * 100, 2) if not np.isnan(vol_20.iloc[-1]) else None,
        "annualized_60d": round(float(vol_60.iloc[-1]) * 100, 2) if not np.isnan(vol_60.iloc[-1]) else None,
        "ewma": round(float(ewma_volatility(returns).iloc[-1]) * 100, 2),
        "unit": "%",
    }

    total_return = float(prices.iloc[-1] / prices.iloc[0] - 1)
    n_days = len(returns)
    ann_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
    report["performance"] = {
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(ann_return * 100, 2),
        "sharpe_ratio": round(sharpe_ratio(returns, risk_free_rate), 4),
        "sortino_ratio": round(sortino_ratio(returns, risk_free_rate), 4),
        "calmar_ratio": round(calmar_ratio(returns, prices), 4),
    }

    report["tail_risk"] = tail_risk_metrics(returns)

    if benchmark_prices is not None:
        bench_returns = calc_returns(benchmark_prices, "simple")
        report["alpha_beta"] = alpha_beta(returns, bench_returns, risk_free_rate)
        report["information_ratio"] = round(information_ratio(returns, bench_returns), 4)

    report["data_info"] = {
        "start_date": str(prices.index[0].date()) if hasattr(prices.index[0], "date") else str(prices.index[0]),
        "end_date": str(prices.index[-1].date()) if hasattr(prices.index[-1], "date") else str(prices.index[-1]),
        "trading_days": len(prices),
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Risk analysis")
    parser.add_argument("symbol", help="Stock code, e.g. sh600519")
    parser.add_argument("--benchmark", help="Benchmark code, e.g. sh000300 for CSI300")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--rf", type=float, default=0.03, help="Risk-free rate (annual)")
    args = parser.parse_args()

    sys.path.insert(0, SCRIPT_DIR)
    from fetch_quotes import get_history
    df = get_history(args.symbol, args.start, args.end)

    bench_prices = None
    if args.benchmark:
        bench_df = get_history(args.benchmark, args.start, args.end)
        bench_prices = bench_df["close"]

    report = full_risk_report(df["close"], bench_prices, args.rf)
    from json_utils import safe_json_dumps
    print(safe_json_dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
