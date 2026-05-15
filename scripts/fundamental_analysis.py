#!/usr/bin/env python3
"""
Fundamental analysis: financial statements, valuation, DuPont decomposition.
Data from AKShare (Sina Finance / East Money source).
"""
import sys
import json
import argparse

import pandas as pd
import numpy as np

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


def _safe_float(value, default: float = 0.0) -> float:
    """Coerce mixed-type API values (str, '-', NaN, None) to a finite float."""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(f):
        return default
    return f


def http_get_json(url: str) -> dict:
    if HAS_REQUESTS:
        import requests as req
        r = req.get(url, timeout=15)
        return r.json()
    req_obj = urllib.request.Request(url)
    with urllib.request.urlopen(req_obj, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_financial_indicators(code: str) -> pd.DataFrame:
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed")
    return ak.stock_financial_analysis_indicator(symbol=code)


def get_eastmoney_financials(code: str) -> list[dict]:
    urls = [
        (
            f"https://datacenter-web.eastmoney.com/api/data/v1/get"
            f"?reportName=RPT_LICO_FN_CPD&columns=ALL"
            f"&filter=(SECURITY_CODE=%22{code}%22)"
            f"&pageSize=4&sortColumns=REPORTDATE&sortTypes=-1"
        ),
        (
            f"http://datacenter-web.eastmoney.com/api/data/v1/get"
            f"?reportName=RPT_LICO_FN_CPD&columns=ALL"
            f"&filter=(SECURITY_CODE=%22{code}%22)"
            f"&pageSize=4&sortColumns=REPORTDATE&sortTypes=-1"
        ),
    ]
    for url in urls:
        try:
            data = http_get_json(url)
            if data.get("result") and data["result"].get("data"):
                return data["result"]["data"]
        except Exception:
            continue
    return []


def get_valuation(code: str) -> dict:
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed")
    df = ak.stock_zh_a_spot_em()
    row = df[df["代码"] == code]
    if row.empty:
        raise ValueError(f"Stock {code} not found")
    r = row.iloc[0]
    return {
        "code": code, "name": str(r["名称"]),
        "price": _safe_float(r["最新价"]),
        "pe_ttm": _safe_float(r.get("市盈率-动态", 0)),
        "pb": _safe_float(r.get("市净率", 0)),
        "total_mv_yi": round(_safe_float(r.get("总市值", 0)) / 1e8, 2),
        "circulating_mv_yi": round(_safe_float(r.get("流通市值", 0)) / 1e8, 2),
    }


def dupont_analysis(code: str) -> dict:
    try:
        indicators = get_financial_indicators(code)
        if indicators.empty:
            return {"error": "No financial indicator data available"}
        latest = indicators.iloc[0]
        roe = _safe_float(latest.get("净资产收益率(%)", 0))
        npm = _safe_float(latest.get("销售净利率(%)", 0))
        at = _safe_float(latest.get("总资产周转率(次)", 0))
        em = roe / (npm * at) if abs(npm * at) > 1e-9 else 0
        return {
            "period": str(latest.get("日期", "N/A")),
            "roe_pct": round(roe, 2),
            "net_profit_margin_pct": round(npm, 2),
            "asset_turnover": round(at, 4),
            "equity_multiplier": round(em, 2),
            "decomposition": f"ROE({roe:.1f}%) = NPM({npm:.1f}%) x AT({at:.2f}) x EM({em:.2f})",
        }
    except Exception as e:
        return {"error": str(e)}


def fundamental_report(code: str) -> dict:
    import re as _re
    code = _re.sub(r'^(sh|sz|bj|hk|us)', '', code, flags=_re.IGNORECASE)
    report = {"code": code}
    errors = []
    try:
        report["valuation"] = get_valuation(code)
    except Exception as e:
        errors.append(f"Valuation: {e}")
    try:
        report["dupont"] = dupont_analysis(code)
    except Exception as e:
        errors.append(f"DuPont: {e}")
    try:
        em_data = get_eastmoney_financials(code)
        if em_data:
            latest = em_data[0]
            report["earnings"] = {
                "report_date": str(latest.get("REPORTDATE", ""))[:10],
                "revenue_yi": round(_safe_float(latest.get("TOTAL_OPERATE_INCOME", 0)) / 1e8, 2),
                "net_profit_yi": round(_safe_float(latest.get("PARENT_NETPROFIT", 0)) / 1e8, 2),
                "eps": _safe_float(latest.get("BASIC_EPS", 0)),
                "roe_pct": _safe_float(latest.get("WEIGHTAVG_ROE", 0)),
                "gross_margin_pct": _safe_float(latest.get("XSMLL", 0)),
                "revenue_yoy_pct": _safe_float(latest.get("YSTZ", 0)),
                "profit_yoy_pct": _safe_float(latest.get("SJLTZ", 0)),
            }
    except Exception as e:
        errors.append(f"EastMoney financials: {e}")
    try:
        indicators = get_financial_indicators(code)
        if not indicators.empty:
            latest = indicators.iloc[0]
            report["quality"] = {
                "current_ratio": _safe_float(latest.get("流动比率", 0)),
                "quick_ratio": _safe_float(latest.get("速动比率", 0)),
                "debt_to_asset_pct": _safe_float(latest.get("资产负债率(%)", 0)),
                "inventory_turnover": _safe_float(latest.get("存货周转率(次)", 0)),
                "receivable_turnover": _safe_float(latest.get("应收账款周转率(次)", 0)),
            }
    except Exception as e:
        errors.append(f"Financial indicators: {e}")
    if errors:
        report["data_warnings"] = errors
    return report


def main():
    parser = argparse.ArgumentParser(description="Fundamental analysis")
    parser.add_argument("code", help="Stock code (6 digits), e.g. 600519")
    parser.add_argument("--mode", default="full", choices=["full", "valuation", "dupont", "earnings"])
    args = parser.parse_args()
    try:
        if args.mode == "full":
            data = fundamental_report(args.code)
        elif args.mode == "valuation":
            data = get_valuation(args.code)
        elif args.mode == "dupont":
            data = dupont_analysis(args.code)
        elif args.mode == "earnings":
            data = get_eastmoney_financials(args.code)
        from json_utils import safe_json_dumps
        print(safe_json_dumps(data, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
