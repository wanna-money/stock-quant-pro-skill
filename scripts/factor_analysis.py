#!/usr/bin/env python3
"""
Alpha/Beta factor analysis and multi-factor model construction.
Discovers effective factors from price-volume data using IC/ICIR evaluation.
"""
import sys
import json
import argparse
import pathlib

import pandas as pd
import numpy as np
from scipy import stats

SCRIPT_DIR = str(pathlib.Path(__file__).parent)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI using Wilder's smoothing (SMMA), matching industry-standard platforms."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rs = rs.fillna(float('inf'))
    return 100 - (100 / (1 + rs))


def calc_factor_momentum(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
    periods = periods or [5, 10, 20, 60, 120]
    factors = pd.DataFrame(index=df.index)
    for p in periods:
        factors[f"mom_{p}d"] = df["close"].pct_change(p)
    return factors


def calc_factor_volatility(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
    periods = periods or [20, 60]
    factors = pd.DataFrame(index=df.index)
    returns = df["close"].pct_change()
    for p in periods:
        factors[f"vol_{p}d"] = returns.rolling(p).std() * np.sqrt(252)
    if f"vol_{periods[0]}d" in factors and f"vol_{periods[-1]}d" in factors:
        factors["vol_ratio"] = factors[f"vol_{periods[0]}d"] / factors[f"vol_{periods[-1]}d"].replace(0, np.nan)
    return factors


def calc_factor_volume(df: pd.DataFrame) -> pd.DataFrame:
    factors = pd.DataFrame(index=df.index)
    factors["vol_ma_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    factors["vol_change"] = df["volume"].pct_change(5)
    factors["price_volume_corr"] = df["close"].pct_change().rolling(20).corr(df["volume"].pct_change())
    factors["amihud_illiquidity"] = abs(df["close"].pct_change()) / (df["volume"] * df["close"] / 1e8).replace(0, np.nan)
    factors["amihud_illiquidity"] = factors["amihud_illiquidity"].replace([np.inf, -np.inf], np.nan)
    factors["amihud_20d"] = factors["amihud_illiquidity"].rolling(20).mean()
    return factors


def calc_factor_technical(df: pd.DataFrame) -> pd.DataFrame:
    factors = pd.DataFrame(index=df.index)
    factors["rsi_14"] = _rsi(df["close"], 14)
    ma20 = df["close"].rolling(20).mean()
    ma60 = df["close"].rolling(60).mean()
    factors["price_to_ma20"] = df["close"] / ma20 - 1
    factors["price_to_ma60"] = df["close"] / ma60 - 1
    factors["ma20_slope"] = ma20.pct_change(5)
    bb_std = df["close"].rolling(20).std()
    factors["bb_position"] = (df["close"] - ma20) / (2 * bb_std).replace(0, np.nan)
    high_52w = df["high"].rolling(252).max()
    low_52w = df["low"].rolling(252).min()
    factors["high_52w_pct"] = df["close"] / high_52w - 1
    factors["range_52w_position"] = (df["close"] - low_52w) / (high_52w - low_52w).replace(0, np.nan)
    return factors


def _rolling_spearman(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    """Compute rolling Spearman rank correlation (pandas rolling.corr only does Pearson)."""
    result = pd.Series(index=x.index, dtype=float)
    for i in range(window - 1, len(x)):
        x_win = x.iloc[i - window + 1:i + 1]
        y_win = y.iloc[i - window + 1:i + 1]
        valid = x_win.notna() & y_win.notna()
        if valid.sum() >= 10:
            corr, _ = stats.spearmanr(x_win[valid], y_win[valid])
            result.iloc[i] = corr
    return result.dropna()


def evaluate_factor(factor: pd.Series, forward_returns: pd.Series, name: str = "factor") -> dict:
    aligned = pd.concat([factor, forward_returns], axis=1).dropna()
    if len(aligned) < 60:
        return {"name": name, "error": "Insufficient data (need 60+ observations)"}
    fac = aligned.iloc[:, 0]
    ret = aligned.iloc[:, 1]
    ic = float(stats.spearmanr(fac, ret)[0])
    rolling_ic = _rolling_spearman(fac, ret, 60)
    ic_mean = float(rolling_ic.mean()) if len(rolling_ic) > 0 else 0
    ic_std = float(rolling_ic.std()) if len(rolling_ic) > 1 else 0.0
    icir = ic_mean / ic_std if ic_std > 0 else 0
    fac_clean = fac.dropna()
    ret_clean = ret.loc[fac_clean.index]
    quintiles = pd.qcut(fac_clean, 5, labels=False, duplicates="drop")
    q_returns = {}
    for q in sorted(quintiles.dropna().unique()):
        q_mean_daily = float(ret_clean[quintiles == q].mean())
        q_ann = ((1 + q_mean_daily) ** 252 - 1) * 100
        q_returns[f"Q{int(q)+1}"] = round(q_ann, 2)
    long_short = q_returns.get("Q5", 0) - q_returns.get("Q1", 0)
    return {
        "name": name, "rank_ic": round(ic, 4),
        "rolling_ic_mean": round(ic_mean, 4), "rolling_ic_std": round(ic_std, 4),
        "icir": round(icir, 4),
        "quintile_returns_ann_pct": q_returns,
        "long_short_return_ann_pct": round(long_short, 2),
        "is_effective": abs(ic) > 0.03 and abs(icir) > 0.5,
    }


def full_factor_analysis(df: pd.DataFrame, forward_days: int = 5) -> dict:
    forward_returns = df["close"].pct_change(forward_days).shift(-forward_days)
    factor_groups = {
        "momentum": calc_factor_momentum(df),
        "volatility": calc_factor_volatility(df),
        "volume": calc_factor_volume(df),
        "technical": calc_factor_technical(df),
    }
    results = {"forward_period_days": forward_days, "factors": {}}
    for group_name, factors_df in factor_groups.items():
        results["factors"][group_name] = []
        for col in factors_df.columns:
            results["factors"][group_name].append(evaluate_factor(factors_df[col], forward_returns, col))
    effective = []
    for group_name, evals in results["factors"].items():
        for e in evals:
            if e.get("is_effective"):
                effective.append({"name": e["name"], "group": group_name, "icir": e["icir"]})
    effective.sort(key=lambda x: abs(x["icir"]), reverse=True)
    results["effective_factors"] = effective
    results["total_factors_tested"] = sum(len(v) for v in results["factors"].values())
    results["effective_count"] = len(effective)
    return results


def main():
    parser = argparse.ArgumentParser(description="Factor analysis")
    parser.add_argument("symbol", help="Stock code, e.g. sh600519")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--forward", type=int, default=5)
    args = parser.parse_args()
    sys.path.insert(0, SCRIPT_DIR)
    from fetch_quotes import get_history
    from json_utils import safe_json_dumps
    df = get_history(args.symbol, args.start, args.end)
    results = full_factor_analysis(df, args.forward)
    print(safe_json_dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
