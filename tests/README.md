# Tests

Two-tier test suite for the `stock-quant-pro` skill:

- **Unit tests** — fast, deterministic, no network. Mock all external I/O.
- **Integration tests** — opt-in, hit live public endpoints (Tencent / AKShare / EastMoney / Sina).

## Layout

```
tests/
├── conftest.py                       # shared synthetic OHLCV fixtures
├── test_technical_analysis.py        # unit
├── test_risk_analysis.py             # unit
├── test_backtest_engine.py           # unit
├── test_factor_analysis.py           # unit
├── test_portfolio_optimizer.py       # unit
├── test_fetch_quotes.py              # unit (mocked HTTP)
├── test_news_collector.py            # unit (mocked HTTP)
├── test_fundamental_analysis.py      # unit (mocked akshare + HTTP)
├── test_sector_analysis.py           # unit (mocked akshare)
├── test_stock_screener.py            # unit (mocked pipeline)
└── test_integration_live.py          # integration — real network
```

Every unit test module is marked `pytestmark = pytest.mark.unit`.
The integration module is marked `pytestmark = [pytest.mark.integration, pytest.mark.slow]`.

## Setup

Create a venv and install the skill dependencies plus pytest:

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install pandas numpy scipy akshare requests pytest
```

Then make the `scripts/` directory importable (the tests do `import technical_analysis`, etc.):

```bash
export PYTHONPATH="$PWD/scripts:$PYTHONPATH"
```

## Running

### Unit only (default, fast, no network)

```bash
pytest -m "not integration"
```

or:

```bash
pytest -m unit
```

### Integration only (live network required)

```bash
pytest -m integration
```

Integration tests **SKIP** rather than fail if:
- no network connectivity (DNS probe fails),
- `SKIP_INTEGRATION=1` env var is set,
- `akshare` is not installed (for akshare-dependent tests),
- the upstream endpoint is unreachable or rate-limited.

### Both

```bash
pytest
```

### A single module

```bash
pytest tests/test_factor_analysis.py -v
```

### A single test

```bash
pytest tests/test_portfolio_optimizer.py::TestRiskParity::test_risk_parity_equalizes_risk_contrib -v
```

## Markers

Declared in `pytest.ini`:

| Marker        | Meaning                                           |
|---------------|---------------------------------------------------|
| `unit`        | Pure logic, no network, fast                      |
| `integration` | Hits live public data sources — opt-in only       |
| `slow`        | Takes more than a few seconds (screener pipeline) |

## Coverage Map

| Module                          | Unit tests                            | Integration tests                    |
|---------------------------------|---------------------------------------|--------------------------------------|
| `scripts/technical_analysis.py` | MA/EMA/MACD/RSI/Bollinger/signals     | —                                    |
| `scripts/risk_analysis.py`      | VaR, CVaR, drawdown, Sharpe/Sortino   | —                                    |
| `scripts/backtest_engine.py`    | strategy generators, metrics          | —                                    |
| `scripts/factor_analysis.py`    | IC/ICIR, quintile, full_analysis      | —                                    |
| `scripts/portfolio_optimizer.py`| equal/min-var/max-Sharpe/risk-parity  | —                                    |
| `scripts/fetch_quotes.py`       | Tencent/EastMoney parsers + fallback  | Live quotes + K-line                 |
| `scripts/news_collector.py`     | Sina/EM/macro/announcement parsers    | Live news feeds                      |
| `scripts/fundamental_analysis.py`| valuation, DuPont, report aggregation| Live valuation + EM financials       |
| `scripts/sector_analysis.py`    | ranking, breadth, rotation, hot       | Live industry ranking + breadth      |
| `scripts/stock_screener.py`     | filter/score/validate/report          | Market snapshot + quick screening    |

## Tips

- If an integration test is flaky in CI, export `SKIP_INTEGRATION=1` to bypass the whole suite.
- Integration tests intentionally assert loosely (e.g. `price > 0`, `len(df) > 10`) because live data fluctuates.
- When a real endpoint changes shape, the unit test mock also needs updating — the two sides of each module's suite are meant to be edited together.
