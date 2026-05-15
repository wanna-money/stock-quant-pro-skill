#!/usr/bin/env python3
"""
Technical indicator calculation and charting.
Supports: MA, MACD, RSI, KDJ, Bollinger Bands, OBV, ATR, VWAP.
Uses ta-lib if available, otherwise pure pandas/numpy.
"""
import sys
import argparse
import json
import pathlib

import pandas as pd
import numpy as np

SCRIPT_DIR = str(pathlib.Path(__file__).parent)

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

try:
    import pandas_ta as pta
    HAS_PTA = True
except ImportError:
    HAS_PTA = False


# ---------------------------------------------------------------------------
# Pure pandas/numpy indicator implementations (no external TA lib needed)
# ---------------------------------------------------------------------------

def calc_ma(close: pd.Series, periods: list[int] = None) -> pd.DataFrame:
    periods = periods or [5, 10, 20, 60, 120, 250]
    result = pd.DataFrame(index=close.index)
    for p in periods:
        if len(close) >= p:
            result[f"MA{p}"] = close.rolling(p).mean()
    return result


def calc_ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    if HAS_TALIB:
        macd, signal_line, hist = talib.MACD(close.values, fast, slow, signal)
        return pd.DataFrame({"DIF": macd, "DEA": signal_line, "MACD_Hist": hist}, index=close.index)
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    histogram = 2 * (dif - dea)
    return pd.DataFrame({"DIF": dif, "DEA": dea, "MACD_Hist": histogram}, index=close.index)


def calc_rsi(close: pd.Series, periods: list[int] = None) -> pd.DataFrame:
    periods = periods or [6, 12, 24]
    result = pd.DataFrame(index=close.index)
    delta = close.diff()
    for p in periods:
        gain = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rs = rs.fillna(float('inf'))
        result[f"RSI{p}"] = 100 - (100 / (1 + rs))
    return result


def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series,
             period: int = 9, signal: int = 3) -> pd.DataFrame:
    lowest = low.rolling(period).min()
    highest = high.rolling(period).max()
    rsv = (close - lowest) / (highest - lowest).replace(0, np.nan) * 100
    k = rsv.ewm(com=signal - 1, adjust=False).mean()
    d = k.ewm(com=signal - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return pd.DataFrame({"K": k, "D": d, "J": j}, index=close.index)


def calc_bollinger(close: pd.Series, period: int = 20, std: int = 2) -> pd.DataFrame:
    mid = close.rolling(period).mean()
    rolling_std = close.rolling(period).std()
    upper = mid + std * rolling_std
    lower = mid - std * rolling_std
    width = (upper - lower) / mid * 100
    return pd.DataFrame({
        "BB_Upper": upper, "BB_Mid": mid, "BB_Lower": lower, "BB_Width": width,
    }, index=close.index)


def calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def calc_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    cumulative_tp_vol = (typical_price * volume).cumsum()
    cumulative_vol = volume.cumsum()
    return cumulative_tp_vol / cumulative_vol


# ---------------------------------------------------------------------------
# Pattern recognition helpers
# ---------------------------------------------------------------------------

def detect_patterns(df: pd.DataFrame) -> list[dict]:
    """Detect common K-line patterns from OHLCV data."""
    patterns = []
    if len(df) < 3:
        return patterns

    for i in range(2, len(df)):
        o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
        po, ph, pl, pc = df.iloc[i - 1][["open", "high", "low", "close"]]
        body = abs(c - o)
        prev_body = abs(pc - po)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        rng = h - l if h != l else 0.001

        if lower_shadow > 2 * body and upper_shadow < body * 0.3 and c > o:
            patterns.append({"date": str(df.index[i].date()), "pattern": "Hammer/锤子线", "signal": "bullish"})

        if c > o and pc < po and c > po and o < pc and body > prev_body:
            patterns.append({"date": str(df.index[i].date()), "pattern": "Bullish Engulfing/看涨吞没", "signal": "bullish"})
        elif c < o and pc > po and c < po and o > pc and body > prev_body:
            patterns.append({"date": str(df.index[i].date()), "pattern": "Bearish Engulfing/看跌吞没", "signal": "bearish"})

        if body < rng * 0.1:
            patterns.append({"date": str(df.index[i].date()), "pattern": "Doji/十字星", "signal": "neutral"})

    return patterns[-10:]


# ---------------------------------------------------------------------------
# Full technical analysis
# ---------------------------------------------------------------------------

def full_analysis(df: pd.DataFrame) -> dict:
    """Run all indicators on OHLCV DataFrame. Returns dict of results."""
    if len(df) < 2:
        return {"error": f"Insufficient data ({len(df)} rows, need 2+)"}
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    results = {}
    latest = df.iloc[-1]
    results["latest"] = {
        "date": str(df.index[-1].date()),
        "open": float(latest["open"]), "high": float(latest["high"]),
        "low": float(latest["low"]), "close": float(latest["close"]),
        "volume": float(latest["volume"]),
    }

    ma_df = calc_ma(close)
    ma_latest = {col: round(float(ma_df[col].iloc[-1]), 2) for col in ma_df.columns if not np.isnan(ma_df[col].iloc[-1])}
    results["moving_averages"] = ma_latest

    price = float(close.iloc[-1])
    trend = {"short": "neutral", "medium": "neutral", "long": "neutral"}
    if "MA5" in ma_latest and "MA10" in ma_latest:
        trend["short"] = "bullish" if price > ma_latest["MA5"] > ma_latest["MA10"] else "bearish" if price < ma_latest["MA5"] < ma_latest["MA10"] else "neutral"
    if "MA20" in ma_latest and "MA60" in ma_latest:
        trend["medium"] = "bullish" if price > ma_latest["MA20"] > ma_latest["MA60"] else "bearish" if price < ma_latest["MA20"] < ma_latest["MA60"] else "neutral"
    if "MA120" in ma_latest and "MA250" in ma_latest:
        trend["long"] = "bullish" if price > ma_latest["MA120"] > ma_latest["MA250"] else "bearish" if price < ma_latest["MA120"] < ma_latest["MA250"] else "neutral"
    results["trend"] = trend

    macd_df = calc_macd(close)
    macd_latest = {col: round(float(macd_df[col].iloc[-1]), 4) for col in macd_df.columns if not np.isnan(macd_df[col].iloc[-1])}
    macd_prev = {col: round(float(macd_df[col].iloc[-2]), 4) for col in macd_df.columns if not np.isnan(macd_df[col].iloc[-2])}
    macd_signal = "golden_cross" if macd_latest.get("MACD_Hist", 0) > 0 and macd_prev.get("MACD_Hist", 0) <= 0 else \
                  "death_cross" if macd_latest.get("MACD_Hist", 0) < 0 and macd_prev.get("MACD_Hist", 0) >= 0 else \
                  "bullish" if macd_latest.get("MACD_Hist", 0) > 0 else "bearish"
    results["macd"] = {**macd_latest, "signal": macd_signal}

    rsi_df = calc_rsi(close)
    rsi_latest = {col: round(float(rsi_df[col].iloc[-1]), 2) for col in rsi_df.columns if not np.isnan(rsi_df[col].iloc[-1])}
    rsi6 = rsi_latest.get("RSI6", 50)
    rsi_signal = "overbought" if rsi6 > 70 else "oversold" if rsi6 < 30 else "neutral"
    results["rsi"] = {**rsi_latest, "signal": rsi_signal}

    kdj_df = calc_kdj(high, low, close)
    kdj_latest = {col: round(float(kdj_df[col].iloc[-1]), 2) for col in kdj_df.columns if not np.isnan(kdj_df[col].iloc[-1])}
    kdj_signal = "overbought" if kdj_latest.get("K", 50) > 80 else "oversold" if kdj_latest.get("K", 50) < 20 else "neutral"
    results["kdj"] = {**kdj_latest, "signal": kdj_signal}

    bb_df = calc_bollinger(close)
    bb_latest = {col: round(float(bb_df[col].iloc[-1]), 2) for col in bb_df.columns if not np.isnan(bb_df[col].iloc[-1])}
    bb_signal = "near_upper" if price > bb_latest.get("BB_Upper", price * 1.1) * 0.98 else \
                "near_lower" if price < bb_latest.get("BB_Lower", price * 0.9) * 1.02 else "in_channel"
    results["bollinger"] = {**bb_latest, "signal": bb_signal}

    atr = calc_atr(high, low, close)
    results["atr"] = round(float(atr.iloc[-1]), 4) if not np.isnan(atr.iloc[-1]) else None

    obv = calc_obv(close, volume)
    if len(obv) >= 5:
        results["obv_trend"] = "rising" if obv.iloc[-1] > obv.iloc[-5] else "falling"
    else:
        results["obv_trend"] = "insufficient_data"

    pivot = (float(latest["high"]) + float(latest["low"]) + float(latest["close"])) / 3
    results["support_resistance"] = {
        "pivot": round(pivot, 2),
        "R1": round(2 * pivot - float(latest["low"]), 2),
        "S1": round(2 * pivot - float(latest["high"]), 2),
        "R2": round(pivot + (float(latest["high"]) - float(latest["low"])), 2),
        "S2": round(pivot - (float(latest["high"]) - float(latest["low"])), 2),
    }

    results["patterns"] = detect_patterns(df.tail(30))

    signals = []
    if trend["short"] == "bullish":
        signals.append(1)
    elif trend["short"] == "bearish":
        signals.append(-1)
    if macd_signal in ("golden_cross", "bullish"):
        signals.append(1)
    elif macd_signal in ("death_cross", "bearish"):
        signals.append(-1)
    if rsi_signal == "oversold":
        signals.append(1)
    elif rsi_signal == "overbought":
        signals.append(-1)

    avg_signal = np.mean(signals) if signals else 0
    results["overall_signal"] = "BUY" if avg_signal > 0.3 else "SELL" if avg_signal < -0.3 else "HOLD"
    results["signal_strength"] = round(abs(avg_signal), 2)

    return results


def main():
    parser = argparse.ArgumentParser(description="Technical analysis")
    parser.add_argument("symbol", help="Stock code, e.g. sh600519")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--chart", action="store_true", help="Generate chart")
    args = parser.parse_args()

    sys.path.insert(0, SCRIPT_DIR)
    from fetch_quotes import get_history
    from json_utils import safe_json_dumps
    df = get_history(args.symbol, args.start, args.end)
    results = full_analysis(df)

    print(safe_json_dumps(results, ensure_ascii=False, indent=2))

    if args.chart:
        try:
            import mplfinance as mpf
            ap = []
            macd_df = calc_macd(df["close"])
            ap.append(mpf.make_addplot(macd_df["MACD_Hist"], panel=1, type="bar", ylabel="MACD"))
            rsi_df = calc_rsi(df["close"], [14])
            ap.append(mpf.make_addplot(rsi_df["RSI14"], panel=2, ylabel="RSI"))
            mpf.plot(df.tail(120), type="candle", mav=(5, 20, 60),
                     volume=True, addplot=ap, style="charles",
                     title=f"{args.symbol} Technical Analysis",
                     savefig=f"{args.symbol}_chart.png")
            print(f"\n[Chart saved: {args.symbol}_chart.png]")
        except ImportError:
            print("\n[WARN] mplfinance not installed, chart skipped]")


if __name__ == "__main__":
    main()
