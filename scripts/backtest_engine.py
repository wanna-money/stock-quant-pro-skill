#!/usr/bin/env python3
"""
Quantitative strategy backtesting engine.
Supports: Momentum, Reversal, Mean Reversion, Breakout, Dual MA.
Includes transaction costs (commission + stamp tax + slippage).
"""
import sys
import json
import argparse
import pathlib

import pandas as pd
import numpy as np

SCRIPT_DIR = str(pathlib.Path(__file__).parent)

COMMISSION_RATE = 0.00025
STAMP_TAX_RATE = 0.001
SLIPPAGE_PCT = 0.001


def _apply_costs(df: pd.DataFrame) -> pd.DataFrame:
    """Apply transaction costs on position changes to strategy_return."""
    pos_change = df["position"].diff().fillna(0)
    entry_cost = pos_change.abs() * (COMMISSION_RATE + SLIPPAGE_PCT)
    prev_pos = df["position"].shift(1).fillna(0)
    is_selling = (prev_pos > 0) & (df["position"] < prev_pos)
    sell_amount = (prev_pos - df["position"].clip(lower=0))
    exit_tax = pd.Series(0.0, index=df.index)
    exit_tax[is_selling] = sell_amount[is_selling] * STAMP_TAX_RATE
    df["strategy_return"] = df["position"] * df["close"].pct_change() - entry_cost - exit_tax
    return df


def momentum_strategy(df: pd.DataFrame, lookback: int = 20, **kwargs) -> pd.DataFrame:
    df = df.copy()
    df["momentum"] = df["close"].pct_change(lookback)
    df["signal"] = 0
    df.loc[df["momentum"] > 0, "signal"] = 1
    df.loc[df["momentum"] < 0, "signal"] = -1
    df["position"] = df["signal"].shift(1).fillna(0)
    df["buy_hold_return"] = df["close"].pct_change()
    return _apply_costs(df)


def reversal_strategy(df: pd.DataFrame, lookback: int = 5, threshold: float = 0.03, **kwargs) -> pd.DataFrame:
    df = df.copy()
    df["past_return"] = df["close"].pct_change(lookback)
    df["signal"] = 0
    df.loc[df["past_return"] < -threshold, "signal"] = 1
    df.loc[df["past_return"] > threshold, "signal"] = -1
    df["position"] = df["signal"].shift(1).fillna(0)
    df["buy_hold_return"] = df["close"].pct_change()
    return _apply_costs(df)


def bollinger_mean_reversion(df: pd.DataFrame, lookback: int = 20, std_mult: float = 2.0, **kwargs) -> pd.DataFrame:
    df = df.copy()
    df["mid"] = df["close"].rolling(lookback).mean()
    df["std"] = df["close"].rolling(lookback).std()
    df["upper"] = df["mid"] + std_mult * df["std"]
    df["lower"] = df["mid"] - std_mult * df["std"]
    df["signal"] = 0
    df.loc[df["close"] < df["lower"], "signal"] = 1
    df.loc[df["close"] > df["upper"], "signal"] = -1
    df["position"] = df["signal"].shift(1).fillna(0)
    df["buy_hold_return"] = df["close"].pct_change()
    return _apply_costs(df)


def donchian_breakout(df: pd.DataFrame, lookback: int = 20, **kwargs) -> pd.DataFrame:
    df = df.copy()
    df["upper_channel"] = df["high"].rolling(lookback).max()
    df["lower_channel"] = df["low"].rolling(lookback).min()
    df["signal"] = 0
    df.loc[df["close"] > df["upper_channel"].shift(1), "signal"] = 1
    df.loc[df["close"] < df["lower_channel"].shift(1), "signal"] = -1
    df["position"] = df["signal"].shift(1).fillna(0)
    df["buy_hold_return"] = df["close"].pct_change()
    return _apply_costs(df)


def dual_ma_crossover(df: pd.DataFrame, lookback: int = 20, fast: int = 5, **kwargs) -> pd.DataFrame:
    df = df.copy()
    df["ma_fast"] = df["close"].rolling(fast).mean()
    df["ma_slow"] = df["close"].rolling(lookback).mean()
    df["signal"] = 0
    df.loc[df["ma_fast"] > df["ma_slow"], "signal"] = 1
    df.loc[df["ma_fast"] < df["ma_slow"], "signal"] = -1
    df["position"] = df["signal"].shift(1).fillna(0)
    df["buy_hold_return"] = df["close"].pct_change()
    return _apply_costs(df)


def evaluate_strategy(df: pd.DataFrame, risk_free_rate: float = 0.03) -> dict:
    strat_ret = df["strategy_return"].dropna()
    bh_ret = df["buy_hold_return"].dropna()
    if len(strat_ret) == 0:
        return {"error": "No returns to evaluate"}

    strat_cumulative = (1 + strat_ret).cumprod()
    bh_cumulative = (1 + bh_ret).cumprod()
    n_days = len(strat_ret)

    total_return = float(strat_cumulative.iloc[-1] - 1)
    ann_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
    ann_vol = float(strat_ret.std() * np.sqrt(252))
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0

    excess_daily = strat_ret - risk_free_rate / 252
    downside_diff = np.minimum(excess_daily, 0)
    downside_dev = float(np.sqrt((downside_diff ** 2).mean()) * np.sqrt(252))
    sortino = (ann_return - risk_free_rate) / downside_dev if downside_dev > 0 else 0

    running_max = strat_cumulative.cummax()
    drawdowns = (strat_cumulative - running_max) / running_max
    max_dd = float(drawdowns.min())
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0

    position_changes = df["position"].diff().fillna(0)
    trades = int((position_changes != 0).sum())

    trade_returns = []
    current_side = 0
    trade_pnl = 0.0
    strat_full = df["strategy_return"].fillna(0.0)
    for i in range(len(df)):
        pos = df["position"].iloc[i]
        if pos != current_side:
            if current_side != 0:
                trade_returns.append(trade_pnl)
                trade_pnl = 0.0
            current_side = pos
        if current_side != 0:
            trade_pnl += float(strat_full.iloc[i])
    if current_side != 0:
        trade_returns.append(trade_pnl)

    winning_trades = sum(1 for t in trade_returns if t > 0)
    losing_trades = sum(1 for t in trade_returns if t <= 0)
    win_rate = winning_trades / len(trade_returns) if trade_returns else 0
    gross_profit = sum(t for t in trade_returns if t > 0)
    gross_loss = abs(sum(t for t in trade_returns if t < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    bh_total = float(bh_cumulative.iloc[-1] - 1)
    bh_ann = (1 + bh_total) ** (252 / n_days) - 1 if n_days > 0 else 0
    turnover = float(position_changes.abs().sum()) / n_days * 252

    return {
        "strategy": {
            "total_return_pct": round(total_return * 100, 2),
            "annualized_return_pct": round(ann_return * 100, 2),
            "annualized_volatility_pct": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 4),
            "win_rate_pct": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 4),
            "total_trades": len(trade_returns),
            "annual_turnover": round(turnover, 2),
        },
        "benchmark": {
            "total_return_pct": round(bh_total * 100, 2),
            "annualized_return_pct": round(bh_ann * 100, 2),
        },
        "excess_return_pct": round((ann_return - bh_ann) * 100, 2),
        "trading_days": n_days,
        "period": {
            "start": str(df.index[0].date()) if hasattr(df.index[0], "date") else str(df.index[0]),
            "end": str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1]),
        },
        "costs_applied": {
            "commission": f"{COMMISSION_RATE*10000:.1f}‱",
            "stamp_tax": f"{STAMP_TAX_RATE*1000:.1f}‰ (sell only)",
            "slippage": f"{SLIPPAGE_PCT*100:.1f}%",
        },
    }


STRATEGIES = {
    "momentum": momentum_strategy,
    "reversal": reversal_strategy,
    "bollinger": bollinger_mean_reversion,
    "breakout": donchian_breakout,
    "dual_ma": dual_ma_crossover,
}


def main():
    parser = argparse.ArgumentParser(description="Strategy backtesting")
    parser.add_argument("symbol", help="Stock code, e.g. sh600519")
    parser.add_argument("--strategy", default="momentum", choices=list(STRATEGIES.keys()))
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--rf", type=float, default=0.03)
    args = parser.parse_args()

    sys.path.insert(0, SCRIPT_DIR)
    from fetch_quotes import get_history
    from json_utils import safe_json_dumps
    df = get_history(args.symbol, args.start, args.end)
    result_df = STRATEGIES[args.strategy](df, lookback=args.lookback)
    metrics = evaluate_strategy(result_df, args.rf)
    metrics["strategy_name"] = args.strategy
    metrics["parameters"] = {"lookback": args.lookback}
    print(safe_json_dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
