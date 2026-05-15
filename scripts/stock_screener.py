#!/usr/bin/env python3
"""
Quantitative stock screener and recommendation engine.
Multi-stage pipeline: Universe Filter → Technical Signal → Factor Scoring
→ Fundamental Validation → Backtest Validation.
All data from official sources (AKShare/EastMoney/Tencent). Never fabricates.
"""
import sys
import json
import argparse
import pathlib
import urllib.request
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np

SCRIPT_DIR = str(pathlib.Path(__file__).parent)
sys.path.insert(0, SCRIPT_DIR)

from fetch_quotes import get_history, strip_market_prefix

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

DISCLAIMER = (
    "本分析结果基于量化模型和历史数据，仅供参考，不构成投资建议。"
    "股市有风险，投资需谨慎。过往业绩不代表未来表现。"
)


def _tencent_batch_quotes(codes: list[str], batch_size: int = 50) -> list[dict]:
    """Fetch quotes from Tencent Finance HTTP API in batches."""
    results = []
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        url = "http://qt.gtimg.cn/q=" + ",".join(batch)
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("gbk", errors="replace")
            for line in text.strip().split(";"):
                if "~" not in line:
                    continue
                p = line.split("~")
                if len(p) < 47 or not p[3] or float(p[3]) <= 0:
                    continue
                results.append({
                    "code": p[2], "name": p[1],
                    "price": float(p[3]), "prev_close": float(p[4]) if p[4] else 0,
                    "open": float(p[5]) if p[5] else 0,
                    "volume": float(p[6]) if p[6] else 0,
                    "amount": float(p[37]) if p[37] else 0,
                    "high": float(p[33]) if p[33] else 0,
                    "low": float(p[34]) if p[34] else 0,
                    "change_pct": float(p[32]) if p[32] else 0,
                    "turnover_rate": float(p[38]) if p[38] else 0,
                    "pe": float(p[39]) if p[39] else 0,
                    "pb": float(p[46]) if len(p) > 46 and p[46] else 0,
                    "total_mv": float(p[45]) * 1e8 if len(p) > 45 and p[45] else 0,
                })
        except Exception:
            continue
    return results


def _generate_all_a_share_codes() -> list[str]:
    """Generate all possible A-share stock codes for Tencent API."""
    codes = []
    for i in range(600000, 605000):
        codes.append(f"sh{i}")
    for i in range(688000, 689999):
        codes.append(f"sh{i}")
    for i in range(0, 5000):
        codes.append(f"sz{i:06d}")
    for i in range(300000, 302000):
        codes.append(f"sz{i}")
    return codes


def get_full_market_snapshot() -> pd.DataFrame:
    if HAS_AKSHARE:
        try:
            df = ak.stock_zh_a_spot_em()
            col_map = {
                "代码": "code", "名称": "name", "最新价": "price",
                "涨跌幅": "change_pct", "涨跌额": "change_amt",
                "成交量": "volume", "成交额": "amount",
                "今开": "open", "最高": "high", "最低": "low", "昨收": "prev_close",
                "换手率": "turnover_rate", "市盈率-动态": "pe",
                "市净率": "pb", "总市值": "total_mv", "流通市值": "circ_mv",
            }
            rename = {k: v for k, v in col_map.items() if k in df.columns}
            df = df.rename(columns=rename)
            for col in ["price", "change_pct", "pe", "pb", "total_mv", "turnover_rate"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as e:
            print(f"  AKShare failed ({e}), falling back to Tencent...", file=sys.stderr)

    print("  Using Tencent Finance HTTP API (batch mode)...", file=sys.stderr)
    all_codes = _generate_all_a_share_codes()
    records = _tencent_batch_quotes(all_codes)
    if not records:
        raise RuntimeError("All data sources failed for market snapshot")
    df = pd.DataFrame(records)
    for col in ["price", "change_pct", "pe", "pb", "total_mv", "turnover_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def filter_universe(df: pd.DataFrame, min_pe: float = 0, max_pe: float = 100,
                    min_mcap: float = 50, sector: str = None) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if "name" in df.columns:
        mask &= ~df["name"].str.contains("ST", na=False)
    if "price" in df.columns:
        mask &= df["price"].between(2, 500)
    if "change_pct" in df.columns:
        mask &= df["change_pct"].abs() < 9.8
    if "pe" in df.columns:
        mask &= df["pe"].between(min_pe + 0.01, max_pe)
    if "total_mv" in df.columns:
        mask &= df["total_mv"] >= min_mcap * 1e8
    if "turnover_rate" in df.columns:
        mask &= df["turnover_rate"] >= 0.3
    result = df[mask].copy()
    if sector and HAS_AKSHARE:
        try:
            sector_df = ak.stock_board_industry_cons_em(symbol=sector)
            if "代码" in sector_df.columns:
                sector_codes = set(sector_df["代码"].tolist())
                result = result[result["code"].isin(sector_codes)]
        except Exception:
            pass
    return result


def _analyze_one_stock(code: str, name: str, start: str) -> dict | None:
    from technical_analysis import full_analysis
    from factor_analysis import (calc_factor_momentum, calc_factor_volatility,
                                 calc_factor_volume, calc_factor_technical)
    try:
        if code.startswith("6"):
            prefix = "sh"
        elif code.startswith(("0", "3")):
            prefix = "sz"
        elif code.startswith(("8", "4")):
            prefix = "bj"
        else:
            prefix = "sz"
        symbol = prefix + code
        df = get_history(symbol, start=start)
        if df is None or len(df) < 60:
            return None

        ta = full_analysis(df)
        signal = ta.get("overall_signal", "HOLD")
        strength = ta.get("signal_strength", 0)
        if signal == "SELL" and strength > 0.5:
            return None

        mom = calc_factor_momentum(df)
        vol = calc_factor_volatility(df)
        volume_f = calc_factor_volume(df)
        tech = calc_factor_technical(df)

        def _safe_last(series):
            vals = series.dropna()
            return float(vals.iloc[-1]) if len(vals) > 0 else 0.0

        factors = {
            "mom_5d": _safe_last(mom.get("mom_5d", pd.Series())),
            "mom_20d": _safe_last(mom.get("mom_20d", pd.Series())),
            "vol_20d": _safe_last(vol.get("vol_20d", pd.Series())),
            "vol_ma_ratio": _safe_last(volume_f.get("vol_ma_ratio", pd.Series())),
            "rsi_14": _safe_last(tech.get("rsi_14", pd.Series())),
            "bb_position": _safe_last(tech.get("bb_position", pd.Series())),
            "price_to_ma20": _safe_last(tech.get("price_to_ma20", pd.Series())),
        }

        key_factors = []
        macd_signal = ta.get("macd", {}).get("signal", "")
        if "golden" in macd_signal:
            key_factors.append("MACD金叉")
        rsi_signal = ta.get("rsi", {}).get("signal", "")
        if "oversold" in rsi_signal:
            key_factors.append("RSI超卖回升")
        if factors["price_to_ma20"] > 0:
            key_factors.append("站上MA20")
        if factors["vol_ma_ratio"] > 1.5:
            key_factors.append("放量突破")
        trend_short = ta.get("trend", {}).get("short", "")
        if trend_short == "bullish":
            key_factors.append("短期趋势向上")

        return {
            "code": code, "name": name, "symbol": prefix + code,
            "signal": signal, "signal_strength": strength,
            "factors": factors, "key_factors": key_factors,
            "history_df": df,
        }
    except Exception:
        return None


def score_technical(candidates: pd.DataFrame, max_workers: int = 8) -> list[dict]:
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    results = []
    items = list(candidates[["code", "name"]].itertuples(index=False))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_analyze_one_stock, row.code, row.name, start): row
            for row in items
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    return results


def score_factors(candidates: list[dict], market_df: pd.DataFrame) -> list[dict]:
    if not candidates:
        return candidates

    records = []
    for c in candidates:
        f = c["factors"]
        code = c["code"]
        market_row = market_df[market_df["code"] == code]
        pe = float(market_row["pe"].iloc[0]) if not market_row.empty and "pe" in market_row else 50
        pb = float(market_row["pb"].iloc[0]) if not market_row.empty and "pb" in market_row else 5
        records.append({
            "momentum": (f["mom_5d"] + f["mom_20d"]) / 2,
            "volume": min(f["vol_ma_ratio"], 5),
            "technical": (50 - f["rsi_14"]) / 50 if f["rsi_14"] is not None else 0,
            "volatility": f["vol_20d"],
            "pe": pe, "pb": pb,
        })

    score_df = pd.DataFrame(records)

    def _zscore(s: pd.Series) -> pd.Series:
        s = s.astype(float)
        if len(s) < 2:
            return pd.Series(0.0, index=s.index)
        mean = s.mean()
        std = s.std()
        if not pd.notna(std) or std < 1e-10:
            return pd.Series(0.0, index=s.index)
        z = (s - mean) / std
        return z.fillna(0.0)

    z_mom = _zscore(score_df["momentum"])
    z_vol_signal = _zscore(score_df["volume"])
    z_tech = _zscore(score_df["technical"])
    z_volatility = -_zscore(score_df["volatility"])
    z_pe = -_zscore(score_df["pe"])
    z_pb = -_zscore(score_df["pb"])
    z_valuation = (z_pe + z_pb) / 2

    composite = (0.30 * z_mom + 0.20 * z_vol_signal + 0.20 * z_tech
                 + 0.15 * z_volatility + 0.15 * z_valuation)

    for i, c in enumerate(candidates):
        c["scores"] = {
            "momentum": round(float(z_mom.iloc[i]), 3),
            "volume": round(float(z_vol_signal.iloc[i]), 3),
            "technical": round(float(z_tech.iloc[i]), 3),
            "volatility": round(float(z_volatility.iloc[i]), 3),
            "valuation": round(float(z_valuation.iloc[i]), 3),
        }
        c["composite_score"] = round(float(composite.iloc[i]), 4)

    candidates.sort(key=lambda x: x["composite_score"], reverse=True)
    return candidates


def validate_fundamentals(candidates: list[dict], top_n: int = 30) -> list[dict]:
    from fundamental_analysis import get_eastmoney_financials
    validated = []
    for c in candidates[:top_n]:
        code = c["code"]
        try:
            fin = get_eastmoney_financials(code)
            if not fin:
                c["fundamental"] = {"status": "no_data"}
                validated.append(c)
                continue
            latest = fin[0]
            def _sf(v, default=0.0):
                try:
                    return float(v) if v not in (None, "", "-", "--") else default
                except (ValueError, TypeError):
                    return default
            roe = _sf(latest.get("WEIGHTAVG_ROE"))
            rev_yoy = _sf(latest.get("YSTZ"))
            profit_yoy = _sf(latest.get("SJLTZ"))
            gross_margin = _sf(latest.get("XSMLL"))

            c["fundamental"] = {
                "roe_pct": round(roe, 2),
                "revenue_yoy_pct": round(rev_yoy, 2),
                "profit_yoy_pct": round(profit_yoy, 2),
                "gross_margin_pct": round(gross_margin, 2),
            }

            risk_warnings = list(c.get("risk_warnings", []))
            if roe < 8:
                risk_warnings.append(f"ROE偏低({roe:.1f}%)")
            if rev_yoy < 0:
                risk_warnings.append(f"营收同比下降({rev_yoy:.1f}%)")
            if profit_yoy < -20:
                risk_warnings.append(f"利润大幅下滑({profit_yoy:.1f}%)")
            c["risk_warnings"] = risk_warnings

            c["fundamental_pass"] = roe >= 8 and rev_yoy > -10
            validated.append(c)
        except Exception:
            c["fundamental"] = {"status": "fetch_error"}
            c["fundamental_pass"] = True
            validated.append(c)

    passed = [c for c in validated if c.get("fundamental_pass", True)]
    failed = [c for c in validated if not c.get("fundamental_pass", True)]
    return passed + failed


def validate_backtest(candidates: list[dict], top_n: int = 15) -> list[dict]:
    from backtest_engine import STRATEGIES, evaluate_strategy
    for c in candidates[:top_n]:
        try:
            df = c.get("history_df")
            if df is None or len(df) < 120:
                continue
            result_df = STRATEGIES["momentum"](df, lookback=20)
            metrics = evaluate_strategy(result_df)
            strat = metrics.get("strategy", {})
            c["backtest"] = {
                "sharpe": strat.get("sharpe_ratio", 0),
                "max_drawdown_pct": strat.get("max_drawdown_pct", 0),
                "annualized_return_pct": strat.get("annualized_return_pct", 0),
                "win_rate_pct": strat.get("win_rate_pct", 0),
            }
            if strat.get("sharpe_ratio", 0) < 0.3:
                c.setdefault("risk_warnings", []).append(
                    f"动量策略夏普比率偏低({strat.get('sharpe_ratio', 0):.2f})")
        except Exception:
            pass
    return candidates


def build_report(candidates: list[dict], market_df: pd.DataFrame,
                 hot_sectors: dict, filter_counts: dict) -> dict:
    advancing = int((market_df["change_pct"] > 0).sum()) if "change_pct" in market_df else 0
    declining = int((market_df["change_pct"] < 0).sum()) if "change_pct" in market_df else 0

    hot_names = [item.get("name", "") for item in hot_sectors.get("industry", [])]

    recommendations = []
    for i, c in enumerate(candidates):
        market_row = market_df[market_df["code"] == c["code"]]
        pe = float(market_row["pe"].iloc[0]) if not market_row.empty and "pe" in market_row else None
        pb = float(market_row["pb"].iloc[0]) if not market_row.empty and "pb" in market_row else None
        mcap = float(market_row["total_mv"].iloc[0]) / 1e8 if not market_row.empty and "total_mv" in market_row else None
        price = float(market_row["price"].iloc[0]) if not market_row.empty and "price" in market_row else None
        chg = float(market_row["change_pct"].iloc[0]) if not market_row.empty and "change_pct" in market_row else None

        rec = {
            "rank": i + 1,
            "code": c["code"],
            "name": c["name"],
            "price": price,
            "change_pct": chg,
            "composite_score": c.get("composite_score", 0),
            "signal": c.get("signal", "HOLD"),
            "signal_strength": round(c.get("signal_strength", 0), 3),
            "pe": round(pe, 2) if pe else None,
            "pb": round(pb, 2) if pb else None,
            "market_cap_yi": round(mcap, 1) if mcap else None,
            "scores": c.get("scores", {}),
            "key_factors": c.get("key_factors", []),
            "risk_warnings": c.get("risk_warnings", []),
        }
        if "fundamental" in c:
            rec["fundamental"] = c["fundamental"]
        if "backtest" in c:
            rec["backtest"] = c["backtest"]
        recommendations.append(rec)

    return {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_overview": {
            "total_stocks": len(market_df),
            "advancing": advancing,
            "declining": declining,
            "hot_sectors": hot_names[:5],
        },
        "filter_summary": filter_counts,
        "recommendations": recommendations,
        "disclaimer": DISCLAIMER,
    }


def run_screening(min_pe: float = 0, max_pe: float = 100, min_mcap: float = 50,
                  sector: str = None, top_n: int = 10, quick: bool = False,
                  max_candidates: int = 200, max_workers: int = 8) -> dict:
    print("[1/5] 获取全市场快照...", file=sys.stderr)
    market_df = get_full_market_snapshot()
    filter_counts = {"universe": len(market_df)}

    print("[2/5] 基础筛选...", file=sys.stderr)
    filtered = filter_universe(market_df, min_pe, max_pe, min_mcap, sector)
    if len(filtered) > max_candidates:
        filtered = filtered.sample(n=max_candidates, random_state=42)
    filter_counts["after_basic_filter"] = len(filtered)
    print(f"       基础筛选后: {len(filtered)} 只", file=sys.stderr)

    print(f"[3/5] 技术面分析 ({len(filtered)} 只)...", file=sys.stderr)
    tech_results = score_technical(filtered, max_workers=max_workers)
    filter_counts["after_technical"] = len(tech_results)
    print(f"       技术面通过: {len(tech_results)} 只", file=sys.stderr)

    print("[4/5] 多因子打分...", file=sys.stderr)
    scored = score_factors(tech_results, market_df)
    scored = scored[:max(top_n * 3, 30)]
    filter_counts["after_factor_scoring"] = len(scored)

    print("[5/5] 基本面验证...", file=sys.stderr)
    validated = validate_fundamentals(scored, top_n=max(top_n * 2, 20))
    filter_counts["after_fundamental"] = len([c for c in validated if c.get("fundamental_pass", True)])

    if not quick and len(validated) > 0:
        print("[bonus] 回测验证...", file=sys.stderr)
        validated = validate_backtest(validated, top_n=min(top_n + 5, len(validated)))

    validated.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    final = validated[:top_n]
    filter_counts["final_recommendations"] = len(final)

    hot = {}
    try:
        from sector_analysis import hot_sectors
        hot = hot_sectors(10)
    except Exception:
        pass

    for c in final:
        c.pop("history_df", None)
        c.pop("factors", None)
        c.pop("fundamental_pass", None)

    return build_report(final, market_df, hot, filter_counts)


def main():
    parser = argparse.ArgumentParser(description="Quantitative stock screener")
    parser.add_argument("--min-pe", type=float, default=0, help="Minimum PE ratio")
    parser.add_argument("--max-pe", type=float, default=100, help="Maximum PE ratio")
    parser.add_argument("--min-mcap", type=float, default=50, help="Min market cap (亿)")
    parser.add_argument("--sector", help="Sector name filter, e.g. 半导体")
    parser.add_argument("--top", type=int, default=10, help="Number of recommendations")
    parser.add_argument("--quick", action="store_true", help="Skip backtest validation")
    parser.add_argument("--max-candidates", type=int, default=200,
                        help="Max stocks for technical analysis stage")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    args = parser.parse_args()

    try:
        report = run_screening(
            min_pe=args.min_pe, max_pe=args.max_pe, min_mcap=args.min_mcap,
            sector=args.sector, top_n=args.top, quick=args.quick,
            max_candidates=args.max_candidates, max_workers=args.workers,
        )
        from json_utils import safe_json_dumps
        print(safe_json_dumps(report, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
