#!/usr/bin/env python3
"""
Fetch real-time and historical stock quotes from official sources.
Data sources: AKShare (primary), Tencent Finance, East Money.
NEVER fabricates data — reports errors when APIs fail.
"""
import sys
import re
import json
import argparse
import pathlib
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

SCRIPT_DIR = str(pathlib.Path(__file__).parent)


def strip_market_prefix(symbol: str) -> str:
    """Remove market prefix (sh/sz/bj/hk/us) to get pure numeric/alpha code."""
    return re.sub(r'^(sh|sz|bj|hk|us)', '', symbol, flags=re.IGNORECASE)

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import urllib.request


def fetch_via_urllib(url: str, headers: dict = None) -> str:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get(url: str, headers: dict = None) -> str:
    if HAS_REQUESTS:
        import requests as req
        import re as _re
        r = req.get(url, headers=headers or {}, timeout=15)
        # apparent_encoding can return None; prefer Content-Type charset header
        ct = r.headers.get("content-type", "")
        m = _re.search(r"charset=([^\s;]+)", ct, _re.IGNORECASE)
        if m:
            r.encoding = m.group(1)
        elif r.apparent_encoding:
            r.encoding = r.apparent_encoding
        else:
            r.encoding = "utf-8"
        return r.text
    return fetch_via_urllib(url, headers)


# ---------------------------------------------------------------------------
# AKShare data fetchers
# ---------------------------------------------------------------------------

def akshare_realtime_a(symbol: str) -> dict:
    """Fetch A-share real-time quote via AKShare (East Money source)."""
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed")
    df = ak.stock_zh_a_spot_em()
    code = strip_market_prefix(symbol)
    row = df[df["代码"] == code]
    if row.empty:
        raise ValueError(f"Stock {symbol} not found in A-share list")
    r = row.iloc[0]
    return {
        "code": r["代码"], "name": r["名称"],
        "price": float(r["最新价"]), "change_pct": float(r["涨跌幅"]),
        "change_amt": float(r["涨跌额"]), "volume": float(r["成交量"]),
        "amount": float(r["成交额"]), "high": float(r["最高"]),
        "low": float(r["最低"]), "open": float(r["今开"]),
        "prev_close": float(r["昨收"]),
        "turnover_rate": float(r.get("换手率", 0)),
        "pe": float(r.get("市盈率-动态", 0)),
        "total_mv": float(r.get("总市值", 0)),
        "source": "AKShare/EastMoney",
    }


def akshare_history(symbol: str, start: str, end: str,
                    period: str = "daily", adjust: str = "qfq") -> pd.DataFrame:
    """Fetch historical K-line via AKShare."""
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed")
    code = strip_market_prefix(symbol)
    df = ak.stock_zh_a_hist(
        symbol=code, period=period,
        start_date=start.replace("-", ""),
        end_date=end.replace("-", ""),
        adjust=adjust,
    )
    expected_cols = ["date", "open", "close", "high", "low", "volume",
                     "amount", "amplitude", "change_pct", "change_amt", "turnover"]
    if len(df.columns) != len(expected_cols):
        raise ValueError(f"AKShare returned {len(df.columns)} columns, expected {len(expected_cols)}. API format may have changed.")
    df.columns = expected_cols
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


# ---------------------------------------------------------------------------
# Tencent Finance fallback
# ---------------------------------------------------------------------------

def tencent_realtime(symbols: list[str]) -> list[dict]:
    """Fetch real-time quotes from Tencent Finance API."""
    codes = ",".join(symbols)
    url = f"http://qt.gtimg.cn/q={codes}"
    text = http_get(url)
    results = []
    for line in text.strip().split("\n"):
        if "~" not in line:
            continue
        parts = line.split("~")
        if len(parts) < 45:
            continue
        results.append({
            "code": parts[2], "name": parts[1],
            "price": float(parts[3]) if parts[3] else 0,
            "prev_close": float(parts[4]) if parts[4] else 0,
            "open": float(parts[5]) if parts[5] else 0,
            "volume": float(parts[6]) if parts[6] else 0,
            "high": float(parts[33]) if parts[33] else 0,
            "low": float(parts[34]) if parts[34] else 0,
            "change_pct": float(parts[32]) if parts[32] else 0,
            "source": "Tencent Finance",
        })
    return results


def tencent_kline(symbol: str, start: str, end: str, count: int = 500) -> pd.DataFrame:
    """Fetch K-line from Tencent Finance API."""
    url = (
        f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={symbol},day,{start},{end},{count},qfq"
    )
    text = http_get(url)
    data = json.loads(text)
    code = symbol[2:] if len(symbol) > 2 else symbol
    klines = data.get("data", {}).get(code, {}).get("qfqday", [])
    if not klines:
        klines = data.get("data", {}).get(symbol, {}).get("qfqday", [])
    if not klines:
        klines = data.get("data", {}).get(code, {}).get("day", [])
    if not klines:
        klines = data.get("data", {}).get(symbol, {}).get("day", [])
    if not klines:
        raise ValueError(f"No K-line data returned for {symbol}")
    klines = [row[:6] for row in klines]
    df = pd.DataFrame(klines, columns=["date", "open", "close", "high", "low", "volume"])
    for col in ["open", "close", "high", "low", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


# ---------------------------------------------------------------------------
# East Money fallback
# ---------------------------------------------------------------------------

def eastmoney_kline(symbol: str, start: str, end: str, klt: int = 101) -> pd.DataFrame:
    """
    Fetch K-line from East Money API.
    klt: 101=daily, 102=weekly, 103=monthly
    """
    code = strip_market_prefix(symbol)
    if symbol.startswith("sh") or code.startswith("6"):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&klt={klt}&fqt=1"
        f"&beg={start.replace('-', '')}&end={end.replace('-', '')}"
        f"&fields1=f1,f2,f3,f4,f5,f6,f7,f8"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    )
    text = http_get(url)
    data = json.loads(text)
    klines = data.get("data", {}).get("klines", [])
    if not klines:
        raise ValueError(f"No data from East Money for {symbol}")
    rows = [k.split(",") for k in klines]
    df = pd.DataFrame(rows, columns=[
        "date", "open", "close", "high", "low", "volume", "amount",
        "amplitude", "change_pct", "change_amt", "turnover",
    ])
    for col in ["open", "close", "high", "low", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


# ---------------------------------------------------------------------------
# Unified interface with fallback
# ---------------------------------------------------------------------------

def get_realtime(symbol: str) -> dict:
    """Get real-time quote with automatic fallback."""
    errors = []
    if HAS_AKSHARE and (symbol.startswith("sh") or symbol.startswith("sz")):
        try:
            return akshare_realtime_a(symbol)
        except Exception as e:
            errors.append(f"AKShare: {e}")
    try:
        results = tencent_realtime([symbol])
        if results:
            return results[0]
    except Exception as e:
        errors.append(f"Tencent: {e}")
    raise RuntimeError(f"All data sources failed for {symbol}: {'; '.join(errors)}")


def get_index_realtime(symbol: str) -> dict:
    """Get real-time index quote (上证指数, 深证成指, 沪深300 etc.)."""
    errors = []
    code = strip_market_prefix(symbol)
    if HAS_AKSHARE:
        try:
            for category in ["上证系列指数", "深证系列指数", "中证系列指数"]:
                df = ak.stock_zh_index_spot_em(symbol=category)
                row = df[df["代码"] == code]
                if not row.empty:
                    r = row.iloc[0]
                    return {
                        "code": r["代码"], "name": r["名称"],
                        "price": float(r["最新价"]), "change_pct": float(r["涨跌幅"]),
                        "change_amt": float(r["涨跌额"]),
                        "open": float(r.get("今开", 0)),
                        "high": float(r.get("最高", 0)),
                        "low": float(r.get("最低", 0)),
                        "prev_close": float(r.get("昨收", 0)),
                        "volume": float(r.get("成交量", 0)),
                        "amount": float(r.get("成交额", 0)),
                        "source": "AKShare/EastMoney",
                        "type": "index",
                    }
        except Exception as e:
            errors.append(f"AKShare index: {e}")
    try:
        results = tencent_realtime([symbol])
        if results:
            result = results[0]
            result["type"] = "index"
            return result
    except Exception as e:
        errors.append(f"Tencent: {e}")
    raise RuntimeError(f"All index data sources failed for {symbol}: {'; '.join(errors)}")


def get_history(symbol: str, start: str = None, end: str = None,
                period: str = "daily") -> pd.DataFrame:
    """Get historical K-line with automatic fallback."""
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    errors = []
    if HAS_AKSHARE and (symbol.startswith("sh") or symbol.startswith("sz") or symbol[:1].isdigit()):
        try:
            return akshare_history(symbol, start, end, period=period)
        except Exception as e:
            errors.append(f"AKShare: {e}")
    try:
        return eastmoney_kline(symbol, start, end)
    except Exception as e:
        errors.append(f"EastMoney: {e}")
    try:
        return tencent_kline(symbol, start, end)
    except Exception as e:
        errors.append(f"Tencent: {e}")
    raise RuntimeError(f"All data sources failed for {symbol}: {'; '.join(errors)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch stock quotes")
    parser.add_argument("symbol", nargs="+", help="Stock/index code(s), e.g. sh600519 sz000001 sh000001")
    parser.add_argument("--mode", choices=["realtime", "history"], default="realtime")
    parser.add_argument("--index", action="store_true", help="Treat symbols as market indices (上证指数, 沪深300 etc.)")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--period", default="daily", choices=["daily", "weekly", "monthly"])
    parser.add_argument("--format", default="table", choices=["table", "json", "csv"])
    args = parser.parse_args()

    try:
        from json_utils import safe_json_dumps
        if args.mode == "realtime":
            fetch_fn = get_index_realtime if args.index else get_realtime
            if len(args.symbol) == 1:
                data = fetch_fn(args.symbol[0])
                print(safe_json_dumps(data, ensure_ascii=False, indent=2))
            else:
                results = []
                for sym in args.symbol:
                    try:
                        results.append(fetch_fn(sym))
                    except Exception as e:
                        results.append({"code": sym, "error": str(e)})
                print(safe_json_dumps(results, ensure_ascii=False, indent=2))
        else:
            symbol = args.symbol[0]
            df = get_history(symbol, args.start, args.end, args.period)
            if args.format == "json":
                print(df.to_json(orient="index", date_format="iso", force_ascii=False))
            elif args.format == "csv":
                print(df.to_csv())
            else:
                print(df.tail(30).to_string())
            print(f"\n[Data source: AKShare/EastMoney/Tencent | Records: {len(df)}]")
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
