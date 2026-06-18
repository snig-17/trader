"""
validation.py
=============
This module demonstrates, on real data, why the original guide's instruction --
"if any strategy has a negative Sharpe, adjust the parameters" -- is the single
most dangerous sentence in it. That instruction IS overfitting: you keep tuning
knobs until the backtest looks good, then deploy a curve fit to history that has
no future.

The demo:
  1. Take ONE instrument + strategy family.
  2. Try a grid of parameter combinations (each is a separate "trial").
  3. Pick the combo with the best IN-SAMPLE Sharpe (first half of history).
  4. Look at how that exact combo does OUT-OF-SAMPLE (second half it never saw).
  5. Compute the Deflated Sharpe Ratio, which asks: given that we cherry-picked
     the best of N trials, is the winner's Sharpe distinguishable from luck?

Almost invariably: the in-sample Sharpe looks great, the out-of-sample Sharpe
collapses, and the DSR is far below 0.95. That gap is the cost of self-deception.
"""

from __future__ import annotations
import itertools
import numpy as np
import pandas as pd

from strategies import mean_reversion_signal, vol_target_exposure
from backtest import run_backtest
import metrics as M


def _periodic_sharpe_segment(net_ret: pd.Series, idx_slice: slice) -> float:
    return M.periodic_sharpe(net_ret.iloc[idx_slice])


def walk_forward_overfit_demo(
    df: pd.DataFrame,
    symbol: str,
    ppy: int,
    split: float = 0.5,
    lookbacks=(10, 15, 20, 30, 40, 50, 60),
    z_entries=(1.0, 1.25, 1.5, 1.75, 2.0, 2.5),
    z_exits=(0.0, 0.25, 0.5),
) -> dict:
    """Grid-search mean reversion on `symbol`; report IS vs OOS + Deflated Sharpe."""
    n = len(df)
    split_idx = int(n * split)
    is_slice = slice(0, split_idx)
    oos_slice = slice(split_idx, n)

    grid = list(itertools.product(lookbacks, z_entries, z_exits))
    rows = []
    is_periodic_sharpes = []
    net_by_combo = {}

    for (lb, ze, zx) in grid:
        sig = mean_reversion_signal(df, lookback=lb, z_entry=ze, z_exit=zx, allow_short=True)
        expo = vol_target_exposure(df, sig)
        res = run_backtest(df, expo, symbol)
        net = res["net_ret"]
        net_by_combo[(lb, ze, zx)] = net
        is_s = _periodic_sharpe_segment(net, is_slice)
        oos_s = _periodic_sharpe_segment(net, oos_slice)
        is_periodic_sharpes.append(is_s)
        rows.append({
            "lookback": lb, "z_entry": ze, "z_exit": zx,
            "is_sharpe_ann": is_s * np.sqrt(ppy),
            "oos_sharpe_ann": oos_s * np.sqrt(ppy),
            "_is_periodic": is_s,
        })

    table = pd.DataFrame(rows)

    # In-sample winner (what an overfitter would proudly deploy)
    best = table.sort_values("is_sharpe_ann", ascending=False).iloc[0]
    best_key = (int(best["lookback"]), float(best["z_entry"]), float(best["z_exit"]))
    winner_net = net_by_combo[best_key]

    # Deflated Sharpe: hold the winner to a bar raised by the number of trials.
    dsr = M.deflated_sharpe_ratio(
        winner_returns=winner_net.iloc[is_slice],
        all_trial_periodic_sharpes=is_periodic_sharpes,
    )

    # Mini-PBO flavour: is the IS winner even above the median strategy OOS?
    oos_median_ann = float(table["oos_sharpe_ann"].median())

    return {
        "symbol": symbol,
        "n_trials": len(grid),
        "split_date": str(df.index[split_idx].date()),
        "winner_params": {"lookback": best_key[0], "z_entry": best_key[1], "z_exit": best_key[2]},
        "winner_is_sharpe_ann": float(best["is_sharpe_ann"]),
        "winner_oos_sharpe_ann": float(best["oos_sharpe_ann"]),
        "oos_median_sharpe_ann": oos_median_ann,
        "deflated_sharpe": dsr,
        "table": table.drop(columns="_is_periodic"),
    }
