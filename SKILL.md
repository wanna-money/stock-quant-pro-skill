---
name: stock-quant-pro
description: >-
  Professional stock market trading, quantitative analysis, and risk management skill.
  Covers A-share/HK/US markets with real-time quotes, K-line technical analysis (MACD, RSI, KDJ, Bollinger Bands),
  quantitative strategy backtesting (momentum, reversal, multi-factor), risk metrics (VaR, max drawdown, Sharpe ratio),
  sector/industry analysis, financial news aggregation, and company fundamental analysis.
  All data sourced from official APIs (Tencent Finance, Sina Finance, East Money, AKShare) — never fabricated.
  Use when the user asks about stock prices, technical analysis, quantitative trading, portfolio risk, market news,
  or any stock/finance related task.
license: MIT
compatibility: Requires Python 3.10+, pip/uv, and internet access for live market data.
metadata:
  author: stock-quant-pro
  version: "1.0"
  markets: "A-share, HK, US"
  data-sources: "Tencent Finance, Sina Finance, East Money, AKShare, BaoStock"
allowed-tools: Bash(python*) Bash(pip*) Bash(uv*) Read Write Edit
---

# Stock Quant Pro — Professional Stock Market Analysis Skill

## Overview

This skill provides institutional-grade stock market analysis capabilities across A-share, Hong Kong, and US markets. Every data point must come from verified official sources — **never fabricate or guess market data**.

## CRITICAL RULES

1. **Data Integrity**: ALL market data MUST come from official APIs (Tencent Finance, Sina Finance, East Money) or verified Python libraries (AKShare, BaoStock). If an API call fails, report the failure — NEVER invent prices, volumes, or any market data.
2. **No Fabrication**: If you cannot fetch real data, say so explicitly. Do NOT generate fake stock prices, financial statements, or news.
3. **Risk Disclaimer**: Always remind users that quantitative analysis results are for reference only, not investment advice.
4. **Market Hours Awareness**: A-shares trade 9:30-11:30 and 13:00-15:00 Beijing time. HK trades 9:30-12:00 and 13:00-16:00 HKT. US trades 9:30-16:00 ET. Data outside these hours reflects the last close.

## Phase 0: Environment Setup

**This phase is MANDATORY before running any script.** The scripts require `pandas`, `numpy`, and `scipy` as hard top-level imports — missing them causes an immediate `ModuleNotFoundError` crash before any logic runs.

### Step 1 — Locate the Python interpreter

Prefer the project venv if it exists (all dependencies pre-installed). Detect it with:

```bash
SKILL_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || pwd)"
VENV_PY="$SKILL_DIR/.venv/bin/python"
if [ -f "$VENV_PY" ]; then
  PY="$VENV_PY"
else
  PY="$(which python3 2>/dev/null || which python)"
fi
echo "Using: $($PY --version 2>&1) at $PY"
```

Use `$PY` (never bare `python` or `python3`) for **all** script calls in the phases below.

### Step 2 — Check and install missing dependencies

```bash
# Hard dependencies — scripts crash without these
$PY -c "import pandas, numpy, scipy" 2>/dev/null || \
  $PY -m pip install pandas numpy scipy -q

# Primary data source
$PY -c "import akshare" 2>/dev/null || \
  $PY -m pip install akshare -q

# Optional — charts and extended TA (failure is non-fatal)
$PY -c "import matplotlib" 2>/dev/null || \
  $PY -m pip install matplotlib mplfinance -q 2>/dev/null || true
$PY -m pip install pandas-ta quantstats -q 2>/dev/null || true
```

If `ta-lib` fails (requires a C library), the scripts fall back to `pandas-ta` or pure numpy/pandas automatically.

### Step 3 — Set PYTHONPATH

```bash
export PYTHONPATH="$(dirname $PY)/../lib/python$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')/site-packages:$SKILL_DIR/scripts:$PYTHONPATH"
```

Or simply activate the venv: `source $SKILL_DIR/.venv/bin/activate`

## Phase 1: Parse User Request

Classify the request into one or more categories:

| Category | Keywords | Action |
|----------|----------|--------|
| **Real-time Quotes** | 实时行情, 股价, 当前价格, quote, price | → Phase 2A |
| **Technical Analysis** | K线, 均线, MACD, RSI, KDJ, 布林带, 技术分析 | → Phase 2B |
| **Quantitative Strategy** | 量化, 回测, 策略, alpha, beta, 因子, 动量, 反转 | → Phase 2C |
| **Risk Analysis** | VaR, 风险, 回撤, 波动率, 夏普比率, 风险指标 | → Phase 2D |
| **Sector/Industry** | 板块, 行业, 热点, 涨跌分布, sector | → Phase 2E |
| **Fundamental Analysis** | 基本面, 财报, 市盈率, ROE, 财务分析 | → Phase 2F |
| **News & Events** | 新闻, 公告, 政策, 央行, 监管, 宏观 | → Phase 2G |
| **Comprehensive Report** | 综合分析, 全面分析, 深度分析 | → Phase 2B + 2D + 2F + 2G |
| **Stock Screening** | 推荐股票, 选股, 哪支有潜力, 买什么, 涨跌情况 | → Phase 2H |

## Phase 2A: Real-time Quotes

When the user asks about stock prices, market indices, or "大盘多少", **immediately run the script** to fetch live data:

```bash
# Single stock real-time quote
python scripts/fetch_quotes.py sh600519

# Market index real-time quote (A股大盘)
python scripts/fetch_quotes.py sh000001 --index          # 上证指数
python scripts/fetch_quotes.py sz399001 --index          # 深证成指
python scripts/fetch_quotes.py sh000300 --index          # 沪深300
python scripts/fetch_quotes.py sz399006 --index          # 创业板指

# Multiple indices at once
python scripts/fetch_quotes.py sh000001 sz399001 sh000300 --index

# Historical data
python scripts/fetch_quotes.py sh600519 --mode history --start 2025-01-01 --format json

# Batch real-time quotes
python scripts/fetch_quotes.py sh600519 sz000001 hk00700
```

**Always run the script first, then interpret the JSON output for the user.** Never guess or fabricate prices.

### Common Query Mapping

| User says | Run this |
|-----------|----------|
| 大盘多少 / 上证指数 / A股行情 | `python scripts/fetch_quotes.py sh000001 sz399001 sh000300 --index` |
| 茅台股价 / 600519行情 | `python scripts/fetch_quotes.py sh600519` |
| 创业板指数 | `python scripts/fetch_quotes.py sz399006 --index` |
| 腾讯股价 | `python scripts/fetch_quotes.py hk00700` |
| 苹果股价 | `python scripts/fetch_quotes.py usAAPL` |
| 今日涨跌 | `python scripts/fetch_quotes.py <symbol>` then check change_pct |

### Stock & Index Code Conventions

| Market | Format | Example |
|--------|--------|---------|
| Shanghai A-share | sh + 6-digit code | sh600519 (贵州茅台) |
| Shenzhen A-share | sz + 6-digit code | sz000001 (平安银行) |
| ChiNext (创业板) | sz + 3xxxxx | sz300750 (宁德时代) |
| STAR Market (科创板) | sh + 688xxx | sh688981 |
| Hong Kong | hk + 5-digit code | hk00700 (腾讯) |
| US Stock | us + ticker | usAAPL (Apple) |
| **上证指数** | sh000001 (--index) | 上证综合指数 |
| **深证成指** | sz399001 (--index) | 深证成份指数 |
| **沪深300** | sh000300 (--index) | 沪深300指数 |
| **创业板指** | sz399006 (--index) | 创业板指数 |
| **上证50** | sh000016 (--index) | 上证50指数 |
| **中证500** | sh000905 (--index) | 中证500指数 |
| **中证1000** | sh000852 (--index) | 中证1000指数 |
| **恒生指数** | hkHSI (--index) | 香港恒生指数 |

### Data Sources (Priority Order)

1. **AKShare** (preferred — most reliable wrapper):
   - `ak.stock_zh_a_spot_em()` — all A-share real-time quotes
   - `ak.stock_zh_index_spot_em()` — all A-share index real-time quotes
   - `ak.stock_hk_spot_em()` — all HK stock quotes
   - `ak.stock_us_spot_em()` — all US stock quotes
   - `ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20250101", adjust="qfq")` — historical K-line

2. **Tencent Finance API** (direct, fast):
   - Real-time: `http://qt.gtimg.cn/q=sh600519,hk00700,usAAPL`
   - K-line: `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,2025-01-01,2025-12-31,250,qfq`

3. **East Money API** (comprehensive):
   - Historical: `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600519&klt=101&fqt=1&beg=20250101&end=20261231&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57`
   - secid: `1.` for Shanghai, `0.` for Shenzhen

## Phase 2B: Technical Analysis

### Indicators to Calculate

| Indicator | Parameters | Interpretation |
|-----------|-----------|----------------|
| **MA** (Moving Average) | MA5, MA10, MA20, MA60, MA120, MA250 | Trend direction, support/resistance |
| **MACD** | fast=12, slow=26, signal=9 | Trend momentum, golden/death cross |
| **RSI** | period=6, 12, 24 | Overbought (>70) / Oversold (<30) |
| **KDJ** | period=9, signal=3 | Overbought (>80) / Oversold (<20) |
| **Bollinger Bands** | period=20, std=2 | Volatility, price channels |
| **VWAP** | intraday | Volume-weighted fair price |
| **OBV** | cumulative | Volume-price divergence |
| **ATR** | period=14 | Volatility measurement |

### K-line Pattern Recognition

Identify these patterns when analyzing candlestick charts:
- **Reversal**: 锤子线, 倒锤子, 吞没形态, 十字星, 早晨之星, 黄昏之星
- **Continuation**: 三白兵, 三黑鸦, 上升三法, 下降三法
- **Consolidation**: 三角形整理, 箱体整理, 旗形

Run `scripts/technical_analysis.py` for full technical indicator calculation and charting.

### Output Format

Present technical analysis as:
1. Current price and change
2. Trend assessment (short/medium/long term)
3. Key support and resistance levels
4. Signal summary (buy/sell/hold with confidence level)
5. Chart (if matplotlib/mplfinance available)

## Phase 2C: Quantitative Strategy

### Strategy Framework

All strategies MUST follow this pipeline:

```
Data → Factor Construction → Signal Generation → Backtesting → Performance Evaluation → Risk Analysis
```

### Available Strategies

1. **Momentum Strategy (动量策略)**
   - Rank stocks by past N-day returns
   - Long top decile, short bottom decile
   - Typical lookback: 20/60/120 days

2. **Reversal Strategy (反转策略)**
   - Short-term mean reversion (5-10 days)
   - Pair trading based on cointegration
   - Contrarian signals from RSI extremes

3. **Multi-Factor Strategy (多因子策略)**
   - Value factors: PE, PB, PCF, dividend yield
   - Quality factors: ROE, gross margin, debt ratio
   - Momentum factors: 1M/3M/6M/12M returns
   - Volatility factors: realized vol, idiosyncratic vol
   - Factor scoring → composite rank → portfolio construction

4. **Mean Reversion (均值回归)**
   - Bollinger Band bounce strategy
   - Z-score based entry/exit

5. **Breakout Strategy (突破策略)**
   - Donchian channel breakout
   - Volume-confirmed breakout

### Backtesting Requirements

- **Minimum data**: 2+ years of daily data
- **Walk-forward**: Use expanding or rolling window, NEVER look-ahead
- **Transaction costs**: Include commission (万2.5) + slippage (1-2 ticks) + stamp tax (卖出千1)
- **Position sizing**: Equal weight, risk parity, or Kelly criterion
- **Benchmark**: CSI 300 (沪深300) for A-shares

Run `scripts/backtest_engine.py` for strategy backtesting.

### Performance Metrics (must report ALL)

| Metric | Formula | Good Threshold |
|--------|---------|----------------|
| Annualized Return | (1+total_return)^(252/days) - 1 | > benchmark |
| Sharpe Ratio | (Rp - Rf) / σp × √252 | > 1.0 |
| Sortino Ratio | (Rp - Rf) / σ_downside × √252 | > 1.5 |
| Max Drawdown | max(peak - trough) / peak | < 20% |
| Calmar Ratio | annualized_return / max_drawdown | > 1.0 |
| Win Rate | winning_trades / total_trades | > 50% |
| Profit Factor | gross_profit / gross_loss | > 1.5 |
| Alpha (CAPM) | Rp - [Rf + β(Rm - Rf)] | > 0 |
| Beta | Cov(Rp, Rm) / Var(Rm) | depends on strategy |
| Information Ratio | (Rp - Rb) / tracking_error | > 0.5 |
| Turnover | annual portfolio turnover | monitor |

## Phase 2D: Risk Analysis

### Risk Metrics

1. **Value at Risk (VaR)**
   - Historical Simulation: Sort returns, take α-percentile
   - Parametric (Gaussian): μ - z_α × σ
   - Monte Carlo: Simulate 10,000+ paths
   - Report at 95% and 99% confidence levels
   - Always report CVaR (Expected Shortfall) alongside VaR

2. **Maximum Drawdown (MDD)**
   - Calculate running peak
   - MDD = max((peak - value) / peak)
   - Report drawdown duration (peak to trough, trough to recovery)

3. **Volatility**
   - Historical volatility (20-day, 60-day rolling)
   - EWMA volatility (λ = 0.94 for daily, RiskMetrics)
   - Annualized: σ_daily × √252

4. **Tail Risk**
   - Skewness and Kurtosis of return distribution
   - Jarque-Bera test for normality
   - Tail ratio (95th percentile gain / 5th percentile loss)

5. **Correlation & Diversification**
   - Correlation matrix across holdings
   - Portfolio concentration (HHI index)
   - Diversification ratio

Run `scripts/risk_analysis.py` for comprehensive risk assessment.

## Phase 2E: Sector & Industry Analysis

### Data Sources

- `ak.stock_board_industry_name_em()` — list all industry sectors
- `ak.stock_board_industry_hist_em(symbol="板块名称")` — sector historical data
- `ak.stock_board_concept_name_em()` — concept/theme sectors
- East Money sector API: `https://push2.eastmoney.com/api/qt/clist/get?fid=f3&po=1&pz=50&np=1&fs=m:90+t:2`

### Analysis Framework

1. **Sector Rotation**: Track 申万一级行业 performance across timeframes
2. **Breadth Analysis**: Advancing vs declining stocks per sector
3. **Money Flow**: Net capital inflow/outflow by sector
4. **Relative Strength**: Sector RS vs CSI 300 benchmark
5. **Correlation**: Cross-sector correlation matrix

## Phase 2F: Fundamental Analysis

### Financial Statements

Fetch via AKShare or East Money API:
- `ak.stock_financial_report_sina(stock="600519", symbol="资产负债表")` — Balance sheet
- `ak.stock_financial_analysis_indicator(symbol="600519")` — Key financial ratios
- East Money: `https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD&filter=(SECURITY_CODE="600519")`

### Key Metrics

| Category | Metrics |
|----------|---------|
| Valuation | PE (TTM), PB, PS, PEG, EV/EBITDA |
| Profitability | ROE, ROA, gross margin, net margin, ROIC |
| Growth | Revenue growth (YoY/QoQ), EPS growth, operating profit growth |
| Quality | Free cash flow, debt-to-equity, current ratio, interest coverage |
| Dividend | Dividend yield, payout ratio, dividend growth rate |

### Analysis Output

1. Valuation assessment (cheap/fair/expensive vs industry median)
2. DuPont decomposition of ROE
3. Earnings quality check (operating CF vs net income)
4. Growth sustainability assessment
5. Peer comparison table

## Phase 2G: News & Events

### Sources

1. **Sina Finance News**:
   - Feed API: `https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&num=20&page=1`
   - Returns JSON with title, url, create_time

2. **East Money Announcements**:
   - Company announcements: `https://np-anotice-stock.eastmoney.com/api/security/ann?page_size=20&page_index=1&ann_type=A&stock_list=600519`
   - Returns JSON with announcement title, date, PDF url

3. **East Money News**:
   - Financial news: `https://np-listapi.eastmoney.com/comm/web/getNewsByColumns?columns=74,467&pageSize=20&pageIndex=0`

4. **10jqka (同花顺)**:
   - `http://basic.10jqka.com.cn/{code}/notice.html`

### Event Categories

- **Corporate**: Earnings releases, dividends, share buybacks, insider trading, M&A
- **Regulatory**: CSRC (证监会) policies, exchange notices, IPO/delisting
- **Macro**: PBOC (央行) interest rate decisions, RRR changes, GDP/CPI/PMI releases
- **Industry**: Sector policy changes, subsidy announcements, trade disputes

Run `scripts/news_collector.py` for automated news aggregation.

## Phase 3: Output Formatting

### Standard Report Structure

```
═══════════════════════════════════════
  [Stock Name] ([Code]) Analysis Report
  Generated: YYYY-MM-DD HH:MM
  Data Source: [API Source]
═══════════════════════════════════════

1. Market Overview
   - Current Price / Change / Volume
   - 52-week High/Low

2. Technical Analysis
   - Trend Assessment
   - Key Indicators Table
   - Support/Resistance Levels
   - Signal Summary

3. Risk Metrics (if requested)
   - VaR / CVaR
   - Volatility / Max Drawdown
   - Sharpe / Sortino Ratio

4. Fundamental Snapshot (if requested)
   - Valuation Multiples
   - Profitability Metrics
   - Growth Metrics

5. Recent News & Events

⚠ Disclaimer: This analysis is for reference only,
  not investment advice. Past performance does not
  guarantee future results.
═══════════════════════════════════════
```

## Phase 2H: Stock Screening & Recommendation

When the user asks about stock recommendations, potential stocks, or which stocks to buy/sell, **immediately run the screener**:

```bash
# Full market scan — top 10 recommendations
python scripts/stock_screener.py

# Quick mode (skip backtest, faster)
python scripts/stock_screener.py --quick

# Top 20 results
python scripts/stock_screener.py --top 20

# Filter by PE range
python scripts/stock_screener.py --min-pe 5 --max-pe 40

# Large-cap only (市值 > 200亿)
python scripts/stock_screener.py --min-mcap 200

# Sector-focused screening
python scripts/stock_screener.py --sector "半导体"
```

### Common Query Mapping

| User says | Run this |
|-----------|----------|
| 推荐股票 / 哪支有潜力 / 选股 | `python scripts/stock_screener.py --quick` |
| 低估值选股 | `python scripts/stock_screener.py --max-pe 20` |
| 大盘蓝筹推荐 | `python scripts/stock_screener.py --min-mcap 500` |
| 半导体板块选股 | `python scripts/stock_screener.py --sector "半导体"` |
| 详细回测验证 | `python scripts/stock_screener.py` (without --quick) |

### Pipeline Overview

```
Stage 1: Universe Filter — ak.stock_zh_a_spot_em() (~5000 → ~500)
    ↓  Exclude ST, price outliers, limit-up/down, low market cap/turnover
Stage 2: Technical Signal — full_analysis() per stock (parallel)
    ↓  Keep BUY signals and moderate+ strength
Stage 3: Multi-Factor Score — momentum/volume/technical/volatility/valuation
    ↓  Z-score composite ranking
Stage 4: Fundamental Validation — ROE, revenue growth, profit growth
    ↓  Flag risk warnings
Stage 5: Backtest Validation (optional) — momentum strategy Sharpe check
    ↓
Output: Ranked JSON with scores, signals, key factors, and risk warnings
```

### Output Interpretation

Each recommendation includes:
- **composite_score**: Overall ranking score (higher = better)
- **signal / signal_strength**: Technical signal (BUY/HOLD) with confidence 0-1
- **scores**: Breakdown by momentum, volume, technical, volatility, valuation
- **key_factors**: Plain-language reasons (e.g. "MACD金叉", "放量突破", "站上MA20")
- **risk_warnings**: Concerns from fundamental validation (e.g. "ROE偏低", "营收下降")
- **fundamental**: ROE, revenue/profit growth, gross margin
- **backtest**: Sharpe ratio, max drawdown, annualized return (if --quick not used)

### Error Handling

When data fetch fails:
1. Log the specific API error
2. Try the next data source in priority order
3. If all sources fail, report: "无法获取 [数据类型] 数据，原因：[错误信息]。请稍后重试。"
4. **NEVER** fill in fake data as a substitute

## Script Reference

| Script | Purpose |
|--------|---------|
| `scripts/setup_env.py` | Environment setup and dependency check |
| `scripts/fetch_quotes.py` | Real-time and historical data fetching |
| `scripts/technical_analysis.py` | Technical indicator calculation and charting |
| `scripts/backtest_engine.py` | Quantitative strategy backtesting |
| `scripts/risk_analysis.py` | VaR, drawdown, volatility, and risk metrics |
| `scripts/sector_analysis.py` | Industry/sector rotation and heat analysis |
| `scripts/fundamental_analysis.py` | Financial statement analysis and valuation |
| `scripts/news_collector.py` | News and announcement aggregation |
| `scripts/factor_analysis.py` | Alpha/beta factor mining and evaluation |
| `scripts/portfolio_optimizer.py` | Portfolio optimization and allocation |
| `scripts/stock_screener.py` | Quantitative stock screening and recommendation |

See [references/api-reference.md](references/api-reference.md) for complete API documentation.
See [references/indicators-guide.md](references/indicators-guide.md) for indicator calculation details.
