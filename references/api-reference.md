# API Reference — Stock Quant Pro

## Data Source Priority

1. **AKShare** (Python library) — Most reliable, wraps multiple sources
2. **East Money API** — Best for historical data and financials
3. **Tencent Finance API** — Fast real-time quotes
4. **Sina Finance API** — News and real-time quotes (requires Referer header)

---

## AKShare Functions

### Real-time Quotes
```python
import akshare as ak

# A-share real-time (all stocks)
df = ak.stock_zh_a_spot_em()
# Columns: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额, 今开, 昨收, 最高, 最低, 换手率, 市盈率-动态, 总市值, 流通市值

# HK stocks
df = ak.stock_hk_spot_em()

# US stocks
df = ak.stock_us_spot_em()
```

### Historical K-line
```python
# Daily K-line with forward adjustment
df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20250101", end_date="20261231", adjust="qfq")
# period: "daily", "weekly", "monthly"
# adjust: "qfq" (forward), "hfq" (backward), "" (no adjust)
# Columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
```

### Industry Sectors
```python
# All industry sectors
df = ak.stock_board_industry_name_em()
# Columns: 板块名称, 涨跌幅, 总市值, 换手率, 领涨股票, 领涨股票-涨跌幅

# Concept/theme sectors
df = ak.stock_board_concept_name_em()

# Sector historical data
df = ak.stock_board_industry_hist_em(symbol="白酒", period="daily", start_date="20250101", end_date="20261231")
```

### Financial Data
```python
# Financial analysis indicators
df = ak.stock_financial_analysis_indicator(symbol="600519")

# Balance sheet / Income / Cash flow
df = ak.stock_financial_report_sina(stock="600519", symbol="资产负债表")
df = ak.stock_financial_report_sina(stock="600519", symbol="利润表")
df = ak.stock_financial_report_sina(stock="600519", symbol="现金流量表")
```

---

## East Money API

### Historical K-line
```
GET https://push2his.eastmoney.com/api/qt/stock/kline/get
Parameters:
  secid     = 1.600519 (1.=Shanghai, 0.=Shenzhen)
  klt       = 101 (101=daily, 102=weekly, 103=monthly, 60=60min)
  fqt       = 1 (1=forward adjust, 2=backward, 0=none)
  beg       = 20250101
  end       = 20261231
  fields1   = f1,f2,f3,f4,f5,f6,f7,f8
  fields2   = f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61
Response: JSON with data.klines[] = ["date,open,close,high,low,volume,amount,amplitude,change_pct,change_amt,turnover"]
```

### Financial Statements
```
GET https://datacenter-web.eastmoney.com/api/data/v1/get
Parameters:
  reportName = RPT_LICO_FN_CPD
  columns    = ALL
  filter     = (SECURITY_CODE="600519")
  pageSize   = 4
  sortColumns = REPORT_DATE
  sortTypes  = -1
Response: JSON with result.data[] containing financial fields
Key fields: REPORT_DATE, TOTAL_OPERATE_INCOME, PARENT_NETPROFIT, BASIC_EPS, WEIGHTAVG_ROE, GROSS_PROFIT_RATIO
```

### Company Announcements
```
GET https://np-anotice-stock.eastmoney.com/api/security/ann
Parameters:
  page_size  = 20
  page_index = 1
  ann_type   = A
  stock_list = 600519
Response: JSON with data.list[] containing title, notice_date, columns
```

### News
```
GET https://np-listapi.eastmoney.com/comm/web/getNewsByColumns
Parameters:
  columns   = 74,467
  pageSize  = 20
  pageIndex = 0
```

---

## Tencent Finance API

### Real-time Quotes
```
GET http://qt.gtimg.cn/q=sh600519,hk00700,usAAPL
Response: GBK-encoded text, fields separated by ~
Key fields: [1]=name, [2]=code, [3]=price, [4]=prev_close, [5]=open, [6]=volume, [32]=change_pct, [33]=high, [34]=low
```

### K-line Data
```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
Parameters:
  param = sh600519,day,2025-01-01,2025-12-31,250,qfq
  Format: {code},{period},{start},{end},{count},{adjust}
  period: day, week, month
  adjust: qfq (forward), hfq (backward)
Response: JSON with data.{code}.qfqday[] = [date, open, close, high, low, volume]
```

---

## Sina Finance API

### Real-time Quotes
```
GET https://hq.sinajs.cn/list=sh600519,hk00700,gb_aapl
Headers: Referer: https://finance.sina.com.cn (REQUIRED)
Stock code formats: sh/sz for A-share, hk for HK, gb_ for US (lowercase ticker)
```

### News Feed
```
GET https://feed.mix.sina.com.cn/api/roll/get
Parameters:
  pageid = 153 (financial news) or 155 (macro news)
  lid    = 2509 (financial) or 2516 (macro)
  num    = 20
  page   = 1
Response: JSON with result.data[] containing title, url, ctime, media_name
```

---

## Stock Code Mapping

| Market | AKShare | Tencent | Sina | East Money secid |
|--------|---------|---------|------|-----------------|
| Shanghai | 600519 | sh600519 | sh600519 | 1.600519 |
| Shenzhen | 000001 | sz000001 | sz000001 | 0.000001 |
| ChiNext | 300750 | sz300750 | sz300750 | 0.300750 |
| STAR | 688981 | sh688981 | sh688981 | 1.688981 |
| HK | — | hk00700 | hk00700 | 116.00700 |
| US | — | usAAPL | gb_aapl | 105.AAPL |
