# Stock Quant Pro

Professional stock market analysis and quantitative trading skill for AI coding agents.

Covers A-share, Hong Kong, and US markets with real-time quotes, technical analysis, quantitative backtesting, risk metrics, factor analysis, portfolio optimization, sector analysis, fundamental analysis, financial news aggregation, and full-market quantitative stock screening.

## Features

| Module | Description |
|--------|-------------|
| **Real-time Quotes** | Live price data from Tencent Finance, East Money, AKShare with automatic failover |
| **Technical Analysis** | MA, MACD (DIF/DEA/MACD_Hist), RSI (Wilder's SMMA), KDJ, Bollinger Bands, ATR (Wilder's SMMA), OBV, VWAP, candlestick pattern recognition |
| **Quantitative Backtesting** | Momentum, reversal, mean reversion, breakout, dual-MA strategies with realistic transaction costs (commission + stamp tax + slippage) |
| **Risk Analysis** | VaR (historical/parametric/Monte Carlo), CVaR, max drawdown, Sharpe/Sortino/Calmar ratios, tail risk metrics |
| **Factor Analysis** | IC/ICIR evaluation, momentum/volatility/volume/technical factors, quintile long-short analysis with compound annualization |
| **Portfolio Optimization** | Equal weight, min variance, max Sharpe, risk parity allocation with risk contribution decomposition |
| **Sector Analysis** | Industry/concept sector ranking, breadth, rotation analysis, hot sector detection (requires AKShare) |
| **Fundamental Analysis** | East Money financials (ROE, revenue/profit YoY, gross margin), DuPont decomposition, valuation multiples |
| **News Aggregation** | Sina Finance news, East Money announcements, macro/policy events |
| **Stock Screening** | Full-market quantitative screening: universe filter → technical signal → multi-factor scoring → fundamental validation → backtest verification |

## Directory Structure

```
stock-quant-pro-skill/
├── SKILL.md                          # Skill metadata and instructions for AI agents
├── README.md                         # This file
├── scripts/
│   ├── setup_env.py                  # Environment setup and dependency check
│   ├── fetch_quotes.py               # Real-time and historical data fetching
│   ├── technical_analysis.py         # Technical indicator calculation
│   ├── backtest_engine.py            # Strategy backtesting engine
│   ├── risk_analysis.py              # Risk metrics (VaR, drawdown, ratios)
│   ├── factor_analysis.py            # Alpha/beta factor mining and IC/ICIR
│   ├── portfolio_optimizer.py        # Portfolio allocation optimization
│   ├── sector_analysis.py            # Industry/sector analysis
│   ├── fundamental_analysis.py       # Financial statement analysis
│   ├── news_collector.py             # News and announcement aggregation
│   └── stock_screener.py             # Quantitative stock screening & recommendation
└── references/
    ├── api-reference.md              # API endpoints for all data sources
    └── indicators-guide.md           # Technical indicator and risk metric formulas
```

## Requirements

- Python 3.10+
- Internet access for live market data

### Dependencies

```
akshare pandas numpy scipy matplotlib mplfinance
```

Optional: `ta-lib` (C library) or `pandas-ta` for extended technical indicators.

Install all dependencies:

```bash
pip install akshare pandas numpy scipy matplotlib mplfinance
```

Or use `uv` (no global install required):

```bash
uv run --with akshare --with pandas --with numpy --with scipy -- python scripts/<script>.py <args>
```

Or run the setup script:

```bash
python scripts/setup_env.py
```

## Quick Start

### Real-time Quote

```bash
# Single stock
python scripts/fetch_quotes.py sh600519

# Market indices
python scripts/fetch_quotes.py sh000001 sz399001 sh000300 --index

# Multiple stocks
python scripts/fetch_quotes.py sh600519 sz000001 sh601318
```

### Historical Data

```bash
python scripts/fetch_quotes.py sh600519 --mode history --start 2025-01-01 --format json
python scripts/fetch_quotes.py sh600519 --mode history --start 2025-01-01 --format csv
python scripts/fetch_quotes.py sh600519 --mode history --start 2025-01-01 --format table
```

### Technical Analysis

```bash
python scripts/technical_analysis.py sh600519 --start 2025-01-01
python scripts/technical_analysis.py sh600519 --start 2025-01-01 --chart   # Save chart PNG
```

Output includes: MA (5/10/20/60/120/250), MACD (DIF/DEA/MACD_Hist), RSI (6/12/24), KDJ, Bollinger Bands, ATR, OBV trend, support/resistance levels, candlestick patterns, and an overall BUY/HOLD/SELL signal.

### Backtest a Strategy

```bash
python scripts/backtest_engine.py sh600519 --strategy momentum --lookback 20 --start 2024-01-01
python scripts/backtest_engine.py sh600519 --strategy bollinger --lookback 20
python scripts/backtest_engine.py sh600519 --strategy dual_ma --lookback 20
python scripts/backtest_engine.py sh600519 --strategy reversal --lookback 5
python scripts/backtest_engine.py sh600519 --strategy breakout --lookback 20
```

Available strategies: `momentum`, `reversal`, `bollinger`, `breakout`, `dual_ma`

Output includes: total/annualized return, Sharpe/Sortino/Calmar ratios, max drawdown, win rate, profit factor, trade count, annual turnover, and benchmark comparison.

### Risk Analysis

```bash
python scripts/risk_analysis.py sh600519 --start 2024-01-01
```

Output includes: VaR at 95%/99% (historical, parametric, Monte Carlo), CVaR, max drawdown with peak/trough dates, daily/annual volatility, Sharpe/Sortino ratios, and tail risk metrics.

### Factor Analysis

```bash
python scripts/factor_analysis.py sh600519 --start 2023-01-01 --forward 5
```

Tests 20 factors across 4 groups (momentum, volatility, volume, technical), evaluates each with Rank IC, ICIR, and quintile long-short returns.

### Portfolio Optimization

```bash
python scripts/portfolio_optimizer.py sh600519 sh601318 sz000858 --method max_sharpe
python scripts/portfolio_optimizer.py sh600519 sh601318 sz000858 --method compare_all
```

Available methods: `equal_weight`, `min_variance`, `max_sharpe`, `risk_parity`, `compare_all`

Output includes: weight allocation, risk contribution decomposition, Sharpe ratio, max drawdown, diversification ratio, HHI concentration, and correlation matrix.

### Sector Analysis

```bash
python scripts/sector_analysis.py --mode ranking --top 20
python scripts/sector_analysis.py --mode hot
python scripts/sector_analysis.py --mode breadth
```

> Note: requires AKShare with HTTPS access to East Money.

### Fundamental Analysis

```bash
python scripts/fundamental_analysis.py 600519 --mode full
python scripts/fundamental_analysis.py 600519 --mode dupont
python scripts/fundamental_analysis.py 600519 --mode earnings
python scripts/fundamental_analysis.py 600519 --mode valuation
```

Output includes: DuPont decomposition (ROE = NPM x AT x EM), earnings (revenue, net profit, EPS, ROE, gross margin, YoY growth), valuation (PE, PB, market cap), and financial quality metrics (current ratio, debt ratio, turnover).

### News Collection

```bash
python scripts/news_collector.py --mode all
python scripts/news_collector.py --mode stock --code 600519
```

### Stock Screening & Recommendation

```bash
# Full market scan — top 10 recommendations
python scripts/stock_screener.py

# Quick mode (skip backtest validation, faster)
python scripts/stock_screener.py --quick

# Top 20, large-cap only (市值 > 200亿)
python scripts/stock_screener.py --top 20 --min-mcap 200

# Sector-focused
python scripts/stock_screener.py --sector "半导体" --quick

# Custom PE range
python scripts/stock_screener.py --min-pe 5 --max-pe 25

# Control parallel workers and candidate pool size
python scripts/stock_screener.py --workers 4 --max-candidates 100
```

Pipeline: 5420 stocks → basic filter (PE, market cap, turnover, exclude ST) → technical signal (full_analysis BUY/HOLD) → multi-factor Z-score (momentum 30% + volume 20% + technical 20% + volatility 15% + valuation 15%) → fundamental validation (ROE, revenue growth) → optional backtest verification (Sharpe, drawdown).

## Stock Code Conventions

| Market | Format | Example |
|--------|--------|---------|
| Shanghai A-share | `sh` + 6 digits | `sh600519` (Kweichow Moutai) |
| Shenzhen A-share | `sz` + 6 digits | `sz000001` (Ping An Bank) |
| ChiNext (创业板) | `sz` + 3xxxxx | `sz300750` (CATL) |
| STAR Market (科创板) | `sh` + 688xxx | `sh688981` |
| Beijing SE (北交所) | `bj` + 8xxxxx | `bj830799` |
| Hong Kong | `hk` + 5 digits | `hk00700` (Tencent) |
| US Stock | `us` + ticker | `usAAPL` (Apple) |

## Data Sources

All market data is fetched from official, publicly available APIs. The system never fabricates data.

| Source | Usage | Protocol | Reliability |
|--------|-------|----------|-------------|
| **AKShare** | Primary — wraps East Money, Sina, others | HTTPS | High |
| **East Money API** | Historical K-line, financials, announcements | HTTPS/HTTP | High |
| **Tencent Finance API** | Real-time quotes, K-line, full market snapshot | HTTP | High |
| **Sina Finance API** | News feeds | HTTP | Medium |

Each data-fetching function implements automatic failover: if the primary source (AKShare HTTPS) fails, East Money and Tencent HTTP APIs are tried transparently. This ensures the system works even in network environments where HTTPS is restricted.

## Transaction Cost Model

Backtesting applies realistic A-share transaction costs:

| Item | Rate | Direction |
|------|------|-----------|
| Commission | 0.025% (2.5 bps) | Buy and sell |
| Stamp Tax | 0.1% | Sell only |
| Slippage | 0.1% (estimated) | Buy and sell |

Stamp tax is correctly applied only on actual sell transactions (not on short entry signals).

## Technical Implementation Notes

- **MACD**: Unified column names `DIF/DEA/MACD_Hist` across both ta-lib and pandas paths
- **RSI**: Uses Wilder's SMMA (`ewm(alpha=1/period)`) matching industry-standard platforms (TradingView, Wind)
- **ATR**: Uses Wilder's SMMA smoothing instead of simple moving average
- **Factor Analysis**: Quintile returns use compound annualization `((1 + mean_daily)^252 - 1)`, Amihud illiquidity guarded against `inf`
- **Stock Screener**: Random sampling (not top-N by change_pct) avoids momentum bias in candidate selection; RSI factor uses `(50 - RSI) / 50` so oversold stocks score higher
- **Tencent K-line**: Handles variable-length rows (6 or 7 fields on ex-dividend dates) by truncating to first 6 columns
- **East Money Financials**: API field mapping updated for current schema (`REPORTDATE`, `YSTZ`, `SJLTZ`, `XSMLL`)

## Agent Skills Specification

This skill follows the [Agent Skills Specification](https://agentskills.io/specification). The `SKILL.md` file contains YAML frontmatter with metadata and Markdown instructions for AI agents to understand capabilities and execution phases.

## License

MIT
