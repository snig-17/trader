"""
data.py
=======
Pull real daily OHLCV from Yahoo Finance.

Why daily, when the original guide used 15-minute / 1-hour / 4-hour bars?
Because honesty requires a long sample. Free intraday history is capped at ~60
days (sub-hourly) to ~730 days (hourly) -- nowhere near enough to say anything
statistically. Daily bars give ~10+ years and hundreds-to-thousands of trades,
which is the bare minimum for the significance tests in metrics.py to mean
anything. The strategy *logic* (revert-to-mean, channel breakout, MA crossover)
transfers directly; the intraday versions face the SAME overfitting risk, only
worse, because more bars = more chances to fit noise and higher turnover = more
cost drag.
"""

from __future__ import annotations
import pandas as pd
import yfinance as yf

# BTC trades 365 days/yr; equities/ETFs ~252.
PERIODS_PER_YEAR = {
    "SPY": 252, "QQQ": 252, "GLD": 252, "USO": 252, "BTC-USD": 365,
}


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance sometimes returns MultiIndex columns even for one ticker."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    return df


def load(symbol: str, period: str = "max") -> pd.DataFrame:
    """Return a clean DataFrame indexed by date with open/high/low/close/volume."""
    raw = yf.download(
        symbol, period=period, interval="1d",
        auto_adjust=True, progress=False,
    )
    if raw is None or len(raw) == 0:
        raise RuntimeError(f"No data returned for {symbol}")
    df = _flatten(raw)[["open", "high", "low", "close", "volume"]].dropna()
    df = df[df["close"] > 0]
    return df


def periods_per_year(symbol: str) -> int:
    return PERIODS_PER_YEAR.get(symbol, 252)
