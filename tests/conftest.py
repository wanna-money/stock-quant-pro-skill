"""
Shared pytest fixtures for stock-quant-pro-skill tests.

Adds scripts/ to sys.path and provides synthetic OHLCV / returns data
so unit tests run without any network access.
"""
from __future__ import annotations

import sys
import pathlib

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _make_ohlcv(n: int = 250, seed: int = 42, start_price: float = 100.0,
                drift: float = 0.0005, vol: float = 0.018) -> pd.DataFrame:
    """Generate a deterministic synthetic OHLCV frame with realistic structure."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp("2025-12-31"), periods=n)
    log_returns = rng.normal(drift, vol, n)
    close = start_price * np.exp(np.cumsum(log_returns))
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1] * (1 + rng.normal(0, 0.003, n - 1))
    intraday_amp = np.abs(rng.normal(0, 0.012, n))
    high = np.maximum(open_, close) * (1 + intraday_amp)
    low = np.minimum(open_, close) * (1 - intraday_amp)
    volume = rng.lognormal(mean=14.0, sigma=0.4, size=n)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "date"
    return df


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    return _make_ohlcv(n=250, seed=42, drift=0.0006, vol=0.018)


@pytest.fixture
def synthetic_ohlcv_bear() -> pd.DataFrame:
    return _make_ohlcv(n=250, seed=7, drift=-0.0008, vol=0.022)


@pytest.fixture
def synthetic_ohlcv_short() -> pd.DataFrame:
    return _make_ohlcv(n=40, seed=1)


@pytest.fixture
def synthetic_returns(synthetic_ohlcv) -> pd.Series:
    return synthetic_ohlcv["close"].pct_change().dropna()


@pytest.fixture
def multi_asset_prices() -> pd.DataFrame:
    rng = np.random.default_rng(123)
    n = 252
    dates = pd.bdate_range(end=pd.Timestamp("2025-12-31"), periods=n)
    base = rng.normal(0.0004, 0.012, n)
    a = base + rng.normal(0, 0.006, n)
    b = 0.7 * base + rng.normal(0, 0.010, n)
    c = -0.3 * base + rng.normal(0.0002, 0.014, n)
    prices = pd.DataFrame(
        {
            "AAA": 100 * np.exp(np.cumsum(a)),
            "BBB": 50 * np.exp(np.cumsum(b)),
            "CCC": 200 * np.exp(np.cumsum(c)),
        },
        index=dates,
    )
    return prices
