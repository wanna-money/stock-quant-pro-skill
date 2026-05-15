#!/usr/bin/env python3
"""
Financial news and announcement collector.
Sources: Sina Finance, East Money, 10jqka.
"""
import sys
import json
import argparse
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import urllib.request


def http_get(url: str, headers: dict = None) -> str:
    if HAS_REQUESTS:
        import requests as req
        r = req.get(url, headers=headers or {}, timeout=15)
        r.encoding = r.apparent_encoding
        return r.text
    req_obj = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req_obj, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_json(url: str, headers: dict = None) -> dict:
    return json.loads(http_get(url, headers))


def sina_news(num: int = 20, page: int = 1) -> list[dict]:
    url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&num={num}&page={page}"
    data = http_get_json(url)
    results = []
    for item in data.get("result", {}).get("data", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "time": item.get("ctime", ""),
            "source": "Sina Finance",
            "category": item.get("media_name", ""),
        })
    return results


def eastmoney_news(num: int = 20) -> list[dict]:
    url = f"https://np-listapi.eastmoney.com/comm/web/getNewsByColumns?columns=74,467&pageSize={num}&pageIndex=0"
    try:
        data = http_get_json(url)
        results = []
        for item in (data.get("data") or {}).get("list", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "time": item.get("showtime", ""),
                "source": "East Money",
                "category": item.get("columnName", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e), "source": "East Money"}]


def company_announcements(stock_code: str, num: int = 20) -> list[dict]:
    url = (
        f"https://np-anotice-stock.eastmoney.com/api/security/ann"
        f"?page_size={num}&page_index=1&ann_type=A&stock_list={stock_code}"
    )
    try:
        data = http_get_json(url)
        results = []
        for item in (data.get("data") or {}).get("list", []):
            results.append({
                "title": item.get("art_code", "") or item.get("title", ""),
                "ann_title": item.get("title", ""),
                "time": item.get("notice_date", ""),
                "source": "East Money Announcements",
                "stock_code": stock_code,
                "columns": [c.get("column_name", "") for c in item.get("columns", [])],
            })
        return results
    except Exception as e:
        return [{"error": str(e), "source": "East Money Announcements"}]


def macro_news(num: int = 20) -> list[dict]:
    url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=155&lid=2516&num={num}&page=1"
    try:
        data = http_get_json(url)
        results = []
        for item in data.get("result", {}).get("data", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "time": item.get("ctime", ""),
                "source": "Sina Macro",
                "category": "macro/policy",
            })
        return results
    except Exception as e:
        return [{"error": str(e), "source": "Sina Macro"}]


def collect_all(stock_code: str = None, num: int = 10) -> dict:
    result = {"timestamp": datetime.now().isoformat(), "financial_news": [], "macro_news": []}
    try:
        result["financial_news"].extend(sina_news(num))
    except Exception as e:
        result["financial_news"].append({"error": str(e), "source": "Sina"})
    try:
        result["financial_news"].extend(eastmoney_news(num))
    except Exception as e:
        result["financial_news"].append({"error": str(e), "source": "EastMoney"})
    try:
        result["macro_news"] = macro_news(num)
    except Exception as e:
        result["macro_news"].append({"error": str(e), "source": "Macro"})
    if stock_code:
        try:
            result["company_announcements"] = company_announcements(stock_code, num)
        except Exception as e:
            result["company_announcements"] = [{"error": str(e)}]
    return result


def main():
    parser = argparse.ArgumentParser(description="Financial news collector")
    parser.add_argument("--mode", default="all", choices=["all", "sina", "eastmoney", "announcements", "macro"])
    parser.add_argument("--code", help="Stock code for company-specific news, e.g. 600519")
    parser.add_argument("--num", type=int, default=10)
    args = parser.parse_args()
    try:
        if args.mode == "all":
            data = collect_all(args.code, args.num)
        elif args.mode == "sina":
            data = sina_news(args.num)
        elif args.mode == "eastmoney":
            data = eastmoney_news(args.num)
        elif args.mode == "announcements":
            if not args.code:
                print("[ERROR] --code required for announcements", file=sys.stderr)
                sys.exit(1)
            data = company_announcements(args.code, args.num)
        elif args.mode == "macro":
            data = macro_news(args.num)
        from json_utils import safe_json_dumps
        print(safe_json_dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
