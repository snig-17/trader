"""
strategies.py
=============
The three strategy families from the guide, implemented carefully so there is
NO look-ahead bias (every signal at bar i uses only data up to and including i;
the backtester then trades it at bar i+1).

  1. Mean reversion       (guide: SPY, QQQ)  -- fade moves >z std from a moving avg
  2. Momentum breakout    (guide: BTC)       -- Donchian channel break + vol + ATR trail
  3. Trend following      (guide: GLD, USO)  -- 50/200 EMA crossover

Plus the ONE good idea in the original guide: ATR-based volatility targeting, so
risk per position is roughly constant across instruments (a quiet instrument gets
a bigger position, a wild one gets a smaller position). Notably, the academic
trend-following literature finds a large part of the famed time-series-momentum
premium comes from exactly this vol-scaling, not the entry signal itself.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Volatility / sizing helpers
# ---------------------------------------------------------------------------
def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def vol_target_exposure(
    df: pd.DataFrame,
    signal: pd.Series,
    risk_per_trade: float = 0.01,
    k_stop: float = 2.0,
    atr_n: int = 14,
    max_leverage: float = 2.0,
) -> pd.Series:
    """
    Convert a {-1,0,+1} signal into a signed fraction-of-equity exposure using
    ATR sizing. If the stop sits k_stop*ATR away and we risk `risk_per_trade` of
    equity, then exposure_fraction = risk_per_trade / (k_stop * ATR/price),
    capped at max_leverage. Smaller positions in volatile names; risk held roughly
    constant in dollar terms.
    """
    atr_frac = (atr(df, atr_n) / df["close"]).replace(0, np.nan)
    raw = risk_per_trade / (k_stop * atr_frac)
    raw = raw.clip(upper=max_leverage).fillna(0.0)
    return (signal.astype(float) * raw).rename("exposure")


# ---------------------------------------------------------------------------
# Strategy 1: Mean reversion
# ---------------------------------------------------------------------------
def mean_reversion_signal(
    df: pd.DataFrame,
    lookback: int = 20,
    z_entry: float = 1.5,
    z_exit: float = 0.25,
    allow_short: bool = True,
) -> pd.Series:
    close = df["close"]
    mu = close.rolling(lookback).mean()
    sd = close.rolling(lookback).std(ddof=0)
    z = ((close - mu) / sd).values

    pos = np.zeros(len(df))
    state = 0
    for i in range(len(df)):
        if not np.isfinite(z[i]):
            state = 0
            pos[i] = 0
            continue
        if state == 0:
            if z[i] <= -z_entry:
                state = 1
            elif allow_short and z[i] >= z_entry:
                state = -1
        elif state == 1:                  # long; exit as price reverts up to mean
            if z[i] >= -z_exit:
                state = 0
        elif state == -1:                 # short; exit as price reverts down to mean
            if z[i] <= z_exit:
                state = 0
        pos[i] = state
    return pd.Series(pos, index=df.index, name="signal")


# ---------------------------------------------------------------------------
# Strategy 2: Momentum breakout (Donchian + volume confirm + ATR trailing stop)
# ---------------------------------------------------------------------------
def breakout_signal(
    df: pd.DataFrame,
    lookback: int = 20,
    vol_mult: float = 1.5,
    atr_n: int = 14,
    trail_k: float = 2.0,
    allow_short: bool = True,
) -> pd.Series:
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]
    upper = high.rolling(lookback).max().shift(1)     # prior N-bar high (no look-ahead)
    lower = low.rolling(lookback).min().shift(1)
    avg_vol = volume.rolling(lookback).mean()
    a = atr(df, atr_n)

    c = close.values
    u, l, av, vv, av_atr = upper.values, lower.values, avg_vol.values, volume.values, a.values
    pos = np.zeros(len(df))
    state, trail = 0, np.nan
    for i in range(len(df)):
        if not (np.isfinite(u[i]) and np.isfinite(l[i]) and np.isfinite(av_atr[i])):
            state, trail, pos[i] = 0, np.nan, 0
            continue
        # volume confirmation; if no volume data (==0), don't block the signal
        vol_ok = (av[i] <= 0) or (vv[i] >= vol_mult * av[i])
        if state == 0:
            if c[i] > u[i] and vol_ok:
                state, trail = 1, c[i] - trail_k * av_atr[i]
            elif allow_short and c[i] < l[i] and vol_ok:
                state, trail = -1, c[i] + trail_k * av_atr[i]
        elif state == 1:
            trail = np.nanmax([trail, c[i] - trail_k * av_atr[i]])
            if c[i] < trail or c[i] < l[i]:
                state, trail = 0, np.nan
        elif state == -1:
            trail = np.nanmin([trail, c[i] + trail_k * av_atr[i]])
            if c[i] > trail or c[i] > u[i]:
                state, trail = 0, np.nan
        pos[i] = state
    return pd.Series(pos, index=df.index, name="signal")


# ---------------------------------------------------------------------------
# Strategy 3: Trend following (EMA crossover)
# ---------------------------------------------------------------------------
def trend_signal(
    df: pd.DataFrame,
    fast: int = 50,
    slow: int = 200,
    allow_short: bool = True,
) -> pd.Series:
    close = df["close"]
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    sig = np.where(ef > es, 1.0, -1.0 if allow_short else 0.0)
    sig[:slow] = 0.0                       # discard warm-up where the slow EMA is unreliable
    return pd.Series(sig, index=df.index, name="signal")


# ---------------------------------------------------------------------------
# The guide's exact spec, instrument -> (signal fn, params)
# ---------------------------------------------------------------------------
GUIDE_SPEC = {
    "SPY":     (mean_reversion_signal, dict(lookback=20, z_entry=1.5)),
    "QQQ":     (mean_reversion_signal, dict(lookback=20, z_entry=1.8)),
    "BTC-USD": (breakout_signal,       dict(lookback=20, vol_mult=1.5, trail_k=2.0)),
    "GLD":     (trend_signal,          dict(fast=50, slow=200)),
    "USO":     (trend_signal,          dict(fast=50, slow=200)),
}
