#!/usr/bin/env python3
"""
Sector and industry analysis for A-share market.
Tracks sector rotation, breadth, money flow, and relative strength.
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


def get_industry_list() -> pd.DataFrame:
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed — required for sector analysis")
    return ak.stock_board_industry_name_em()


def get_concept_list() -> pd.DataFrame:
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed")
    return ak.stock_board_concept_name_em()


def get_sector_performance(sector_name: str, period: str = "daily",
                           start: str = None, end: str = None) -> pd.DataFrame:
    if not HAS_AKSHARE:
        raise RuntimeError("akshare not installed")
    return ak.stock_board_industry_hist_em(symbol=sector_name, period=period,
                                           start_date=start, end_date=end)


def sector_ranking(top_n: int = 20) -> list[dict]:
    df = get_industry_list()
    df = df.sort_values("涨跌幅", ascending=False)
    results = []
    for _, row in df.head(top_n).iterrows():
        results.append({
            "name": row["板块名称"],
            "change_pct": float(row["涨跌幅"]),
            "total_mv": float(row.get("总市值", 0)),
            "turnover_rate": float(row.get("换手率", 0)),
            "leading_stock": row.get("领涨股票", ""),
            "leading_stock_change": (lambda v: float(v) if v not in ("", "-", "--", None) else 0.0)(row.get("领涨股票-涨跌幅", 0)),
        })
    return results


def sector_breadth() -> dict:
    df = get_industry_list()
    total = len(df)
    advancing = int((df["涨跌幅"] > 0).sum())
    declining = int((df["涨跌幅"] < 0).sum())
    flat = total - advancing - declining
    return {
        "total_sectors": total,
        "advancing": advancing, "declining": declining, "flat": flat,
        "advance_decline_ratio": round(advancing / max(declining, 1), 2),
        "breadth_pct": round(advancing / max(total, 1) * 100, 2),
        "avg_change_pct": round(float(df["涨跌幅"].mean()), 2),
        "median_change_pct": round(float(df["涨跌幅"].median()), 2),
    }


def hot_sectors(top_n: int = 10) -> dict:
    result = {"industry": [], "concept": []}
    try:
        ind_df = get_industry_list().sort_values("涨跌幅", ascending=False)
        for _, row in ind_df.head(top_n).iterrows():
            result["industry"].append({"name": row["板块名称"], "change_pct": float(row["涨跌幅"])})
    except Exception as e:
        result["industry_error"] = str(e)
    try:
        con_df = get_concept_list().sort_values("涨跌幅", ascending=False)
        for _, row in con_df.head(top_n).iterrows():
            result["concept"].append({"name": row["板块名称"], "change_pct": float(row["涨跌幅"])})
    except Exception as e:
        result["concept_error"] = str(e)
    return result


def sector_rotation_analysis(days: int = 20) -> list[dict]:
    df = get_industry_list()
    results = []
    for _, row in df.iterrows():
        name = row["板块名称"]
        try:
            hist = get_sector_performance(name, period="daily")
            if len(hist) < days:
                continue
            recent = hist.tail(days)
            short_ret = float((recent["收盘"].iloc[-1] / recent["收盘"].iloc[-5] - 1) * 100) if len(recent) >= 5 else 0
            med_ret = float((recent["收盘"].iloc[-1] / recent["收盘"].iloc[0] - 1) * 100)
            scale = max(days / 5, 1)
            results.append({
                "name": name,
                "5d_return_pct": round(short_ret, 2),
                f"{days}d_return_pct": round(med_ret, 2),
                "acceleration": round(short_ret - (med_ret / scale), 2),
            })
        except Exception:
            continue
    results.sort(key=lambda x: x.get("acceleration", 0), reverse=True)
    return results[:20]


def main():
    parser = argparse.ArgumentParser(description="Sector analysis")
    parser.add_argument("--mode", default="ranking", choices=["ranking", "breadth", "hot", "rotation"])
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.mode == "ranking":
            data = sector_ranking(args.top)
        elif args.mode == "breadth":
            data = sector_breadth()
        elif args.mode == "hot":
            data = hot_sectors(args.top)
        elif args.mode == "rotation":
            data = sector_rotation_analysis()
        from json_utils import safe_json_dumps
        print(safe_json_dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
