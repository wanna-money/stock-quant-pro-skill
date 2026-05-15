# Technical Indicators Guide — Stock Quant Pro

## Moving Averages (MA)

### Simple Moving Average (SMA)
```
SMA(n) = (P1 + P2 + ... + Pn) / n
```
Standard periods: MA5, MA10, MA20, MA60, MA120, MA250

### Exponential Moving Average (EMA)
```
EMA(t) = alpha * P(t) + (1-alpha) * EMA(t-1)
alpha = 2 / (n + 1)
```

---

## MACD (Moving Average Convergence Divergence)

```
DIF = EMA(close, 12) - EMA(close, 26)
DEA = EMA(DIF, 9)
MACD Histogram = 2 * (DIF - DEA)
```

**Signals:**
- Golden Cross: DIF crosses above DEA -> Bullish
- Death Cross: DIF crosses below DEA -> Bearish
- Histogram > 0 expanding -> Strengthening bullish
- Histogram < 0 expanding -> Strengthening bearish

---

## RSI (Relative Strength Index)

```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain(n) / Average Loss(n)
```

Standard periods: RSI6, RSI12, RSI24

**Zones:** >70 overbought, <30 oversold, 40-60 neutral

---

## KDJ (Stochastic Oscillator)

```
RSV = (Close - Lowest(9)) / (Highest(9) - Lowest(9)) * 100
K = EMA(RSV, 3)
D = EMA(K, 3)
J = 3K - 2D
```

**Zones:** K>80 overbought, K<20 oversold, J>100 extremely overbought

---

## Bollinger Bands

```
Middle = SMA(close, 20)
Upper  = Middle + 2 * StdDev(close, 20)
Lower  = Middle - 2 * StdDev(close, 20)
Width  = (Upper - Lower) / Middle * 100
```

**Signals:**
- Price near Upper -> Resistance / potential reversal down
- Price near Lower -> Support / potential reversal up
- Width contracting -> Low volatility, breakout imminent
- Width expanding -> High volatility

---

## ATR (Average True Range)

```
TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
ATR = SMA(TR, 14)
```

Used for: Stop-loss placement, position sizing, volatility filtering

---

## OBV (On-Balance Volume)

```
If Close > PrevClose: OBV = PrevOBV + Volume
If Close < PrevClose: OBV = PrevOBV - Volume
If Close = PrevClose: OBV = PrevOBV
```

**Signals:** OBV divergence from price indicates potential trend reversal

---

## VWAP (Volume-Weighted Average Price)

```
VWAP = Sum(Typical_Price * Volume) / Sum(Volume)
Typical_Price = (High + Low + Close) / 3
```

---

## Risk Metrics Formulas

### Value at Risk (VaR)
```
Historical:  VaR_alpha = -Percentile(returns, (1-alpha)*100)
Parametric:  VaR_alpha = -(mu + z_alpha * sigma)
Monte Carlo: Simulate N paths, take percentile
```

### Conditional VaR (CVaR / Expected Shortfall)
```
CVaR_alpha = -E[R | R <= -VaR_alpha]
```

### Maximum Drawdown
```
MDD = max((Peak - Trough) / Peak)
Peak = running maximum of cumulative returns
```

### Sharpe Ratio
```
Sharpe = (Rp - Rf) / sigma_p * sqrt(252)
Rp = portfolio daily return mean
Rf = risk-free rate / 252
sigma_p = portfolio daily return std
```

### Sortino Ratio
```
Sortino = (Rp - Rf) / sigma_downside * sqrt(252)
sigma_downside = std of negative returns only
```

### Calmar Ratio
```
Calmar = Annualized Return / |Max Drawdown|
```

### Alpha and Beta (CAPM)
```
Rp - Rf = alpha + beta * (Rm - Rf) + epsilon
beta = Cov(Rp, Rm) / Var(Rm)
alpha = Rp - [Rf + beta * (Rm - Rf)]
```

### Information Ratio
```
IR = (Rp - Rb) / Tracking_Error
Tracking_Error = std(Rp - Rb)
```

---

## Factor Analysis Metrics

### Information Coefficient (IC)
```
IC = Spearman_Rank_Correlation(Factor_Value, Forward_Return)
```

### IC Information Ratio (ICIR)
```
ICIR = Mean(Rolling_IC) / Std(Rolling_IC)
|ICIR| > 0.5 -> Factor is effective
```

### Quintile Analysis
- Sort stocks by factor value into 5 groups
- Calculate annualized return for each quintile
- Long-Short return = Q5 return - Q1 return

---

## Transaction Costs (A-share)

| Item | Rate | Direction |
|------|------|-----------|
| Commission | 0.025% (wan 2.5) | Both buy and sell |
| Stamp Tax | 0.1% (qian 1) | Sell only |
| Transfer Fee | 0.002% (wan 0.2) | Both (Shanghai only) |
| Slippage | ~0.1% estimated | Both |
