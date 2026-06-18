"""
metrics.py
==========
Performance metrics + the statistics that actually tell you whether a backtest
result is real or noise.

The headline functions are the Probabilistic Sharpe Ratio (PSR) and the
Deflated Sharpe Ratio (DSR) from:

    Bailey, D. H. & Lopez de Prado, M. (2014).
    "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest
     Overfitting and Non-Normality." Journal of Portfolio Management 40(5).

A raw Sharpe ratio is almost useless on its own: it ignores how long the track
record is, how fat the tails are, and -- crucially -- how many strategy variants
you tried before reporting this one. PSR/DSR put a probability on the claim
"this Sharpe is greater than some benchmark", correcting for all three.

All the "periodic" Sharpe inputs below are NON-annualized (per-bar). Annualize
for display only.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis, norm

EULER_MASCHERONI = 0.5772156649015329


# ---------------------------------------------------------------------------
# Basic performance stats
# ---------------------------------------------------------------------------
def periodic_sharpe(returns: pd.Series) -> float:
    """Non-annualized Sharpe of a per-bar return series."""
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    if sd == 0 or len(r) < 2:
        return 0.0
    return float(r.mean() / sd)


def annualized_sharpe(returns: pd.Series, periods_per_year: int) -> float:
    return periodic_sharpe(returns) * np.sqrt(periods_per_year)


def sortino(returns: pd.Series, periods_per_year: int) -> float:
    r = pd.Series(returns).dropna()
    downside = r[r < 0]
    dd = downside.std(ddof=1)
    if dd == 0 or len(r) < 2:
        return 0.0
    return float(r.mean() / dd) * np.sqrt(periods_per_year)


def cagr(returns: pd.Series, periods_per_year: int) -> float:
    r = pd.Series(returns).dropna()
    if len(r) == 0:
        return 0.0
    growth = (1 + r).prod()
    years = len(r) / periods_per_year
    if years <= 0 or growth <= 0:
        return float("nan")
    return float(growth ** (1 / years) - 1)


def annualized_vol(returns: pd.Series, periods_per_year: int) -> float:
    return float(pd.Series(returns).dropna().std(ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline of the equity curve (negative number)."""
    r = pd.Series(returns).dropna()
    equity = (1 + r).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min()) if len(dd) else 0.0


def calmar(returns: pd.Series, periods_per_year: int) -> float:
    mdd = max_drawdown(returns)
    if mdd == 0:
        return float("nan")
    return cagr(returns, periods_per_year) / abs(mdd)


def hit_rate(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()
    r = r[r != 0]
    if len(r) == 0:
        return float("nan")
    return float((r > 0).mean())


# ---------------------------------------------------------------------------
# The important part: significance under non-normality and multiple testing
# ---------------------------------------------------------------------------
def probabilistic_sharpe_ratio(
    returns: pd.Series, sr_benchmark_periodic: float = 0.0
) -> float:
    """
    PSR(SR*) = Prob( true SR > SR* ), correcting for sample length, skew, kurtosis.

    Returns a probability in [0, 1]. By convention you want PSR > 0.95 to call a
    result statistically significant at the 5% level.

    Formula (Bailey & Lopez de Prado 2014):
        PSR = Z[ (SR_hat - SR*) * sqrt(n - 1)
                 / sqrt(1 - g3*SR_hat + ((g4 - 1)/4)*SR_hat^2) ]
    where SR_hat, SR* are per-bar Sharpes, g3 = skew, g4 = (Pearson) kurtosis.
    """
    r = pd.Series(returns).dropna()
    n = len(r)
    if n < 3:
        return float("nan")
    sr = periodic_sharpe(r)
    g3 = float(skew(r, bias=False))
    g4 = float(kurtosis(r, fisher=False, bias=False))  # Pearson: normal == 3
    denom = np.sqrt(max(1e-12, 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr ** 2))
    z = (sr - sr_benchmark_periodic) * np.sqrt(n - 1) / denom
    return float(norm.cdf(z))


def expected_max_sharpe(sharpe_variance: float, n_trials: int) -> float:
    """
    Expected MAXIMUM (per-bar) Sharpe across `n_trials` independent strategies
    whose true edge is zero -- i.e. the Sharpe you'd expect to see from the
    luckiest of N coin-flippers. This is the benchmark a real strategy must beat.

        SR0 = sqrt(Var[SR]) * [ (1 - gamma) * Z^-1(1 - 1/N)
                                + gamma     * Z^-1(1 - 1/(N*e)) ]
    """
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    g = EULER_MASCHERONI
    a = norm.ppf(1.0 - 1.0 / n_trials)
    b = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(sharpe_variance) * ((1 - g) * a + g * b))


def deflated_sharpe_ratio(
    winner_returns: pd.Series,
    all_trial_periodic_sharpes: list[float] | np.ndarray,
) -> dict:
    """
    DSR = PSR evaluated against the expected-max-Sharpe benchmark SR0, where SR0
    is derived from the spread of Sharpes across ALL variants you tried.

    Pass the per-bar return series of the selected ("winning") strategy plus the
    list of per-bar Sharpes of every variant tested (including the winner). The
    more variants you tried, the higher the bar SR0 -- so a strategy cherry-picked
    from a big grid has to clear a much higher hurdle to be believed.

    Returns dict with sr0, dsr, n_trials and a plain-English verdict.
    """
    sharpes = np.asarray([s for s in all_trial_periodic_sharpes if np.isfinite(s)])
    n_trials = len(sharpes)
    sr_var = float(np.var(sharpes, ddof=1)) if n_trials > 1 else 0.0
    sr0 = expected_max_sharpe(sr_var, n_trials)
    dsr = probabilistic_sharpe_ratio(winner_returns, sr_benchmark_periodic=sr0)
    return {
        "n_trials": n_trials,
        "sharpe_variance_across_trials": sr_var,
        "sr0_benchmark_periodic": sr0,
        "dsr": dsr,
        "significant_at_95": (dsr is not None and dsr > 0.95),
    }


# ---------------------------------------------------------------------------
# Convenience: full performance summary for one return series
# ---------------------------------------------------------------------------
def summarize(returns: pd.Series, periods_per_year: int, label: str = "") -> dict:
    r = pd.Series(returns).dropna()
    return {
        "label": label,
        "n_bars": len(r),
        "cagr": cagr(r, periods_per_year),
        "ann_vol": annualized_vol(r, periods_per_year),
        "sharpe_ann": annualized_sharpe(r, periods_per_year),
        "sortino_ann": sortino(r, periods_per_year),
        "max_drawdown": max_drawdown(r),
        "calmar": calmar(r, periods_per_year),
        "hit_rate": hit_rate(r),
        "psr_vs_0": probabilistic_sharpe_ratio(r, 0.0),
    }
