"""
backtest.py
===========
A small, transparent, vectorized backtester.

Key discipline: the exposure decided using data through bar i is applied to the
return from bar i to bar i+1 (we .shift(1) the exposure). That single line is
what stops a backtester from "trading on information it could not have had",
the most common way people fool themselves.

Costs are charged on turnover = |change in exposure| each bar.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from costs import cost_per_turnover
from strategies import vol_target_exposure, GUIDE_SPEC
import metrics as M


def run_backtest(
    df: pd.DataFrame,
    exposure: pd.Series,
    symbol: str,
    cost_override_bps: float | None = None,
) -> pd.DataFrame:
    """Return a DataFrame with asset returns, lagged exposure, gross & net returns."""
    asset_ret = df["close"].pct_change().fillna(0.0)
    expo = exposure.reindex(df.index).fillna(0.0).shift(1).fillna(0.0)
    turnover = expo.diff().abs()
    turnover.iloc[0] = expo.iloc[0].__abs__()
    c = cost_per_turnover(symbol, cost_override_bps)

    gross = expo * asset_ret
    net = gross - turnover * c
    out = pd.DataFrame(
        {
            "asset_ret": asset_ret,
            "exposure": expo,
            "turnover": turnover,
            "gross_ret": gross,
            "net_ret": net,
        },
        index=df.index,
    )
    out["equity"] = (1 + out["net_ret"]).cumprod()
    return out


def run_guide_strategy(
    df: pd.DataFrame,
    symbol: str,
    risk_per_trade: float = 0.01,
    k_stop: float = 2.0,
    max_leverage: float = 2.0,
    allow_short: bool = True,
    cost_override_bps: float | None = None,
) -> dict:
    """Build the guide's signal for `symbol`, size it by ATR, backtest it."""
    signal_fn, params = GUIDE_SPEC[symbol]
    params = dict(params)
    if "allow_short" in signal_fn.__code__.co_varnames:
        params.setdefault("allow_short", allow_short)
    signal = signal_fn(df, **params)
    exposure = vol_target_exposure(
        df, signal, risk_per_trade=risk_per_trade, k_stop=k_stop,
        max_leverage=max_leverage,
    )
    return {"signal": signal, "exposure": exposure,
            "result": run_backtest(df, exposure, symbol, cost_override_bps)}


def buy_and_hold(df: pd.DataFrame) -> pd.Series:
    """The baseline every active strategy must beat: just own the thing."""
    return df["close"].pct_change().fillna(0.0)
