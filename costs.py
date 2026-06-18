"""
costs.py
========
Transaction costs are where most paper-profitable strategies go to die,
especially high-turnover ones like 15-minute mean reversion. "Commission-free"
is not "cost-free": you still pay the bid/ask spread, slippage, and (for crypto)
exchange fees and funding.

We charge a one-way cost in basis points on every unit of *turnover*
(|change in exposure|). A round trip therefore costs ~2x the one-way figure.

The defaults below are deliberately moderate -- a careful retail trader on liquid
instruments. They are still enough to neutralise the thin edges in the textbook
strategies, which is the point.
"""

from __future__ import annotations

# One-way cost in basis points (1 bp = 0.01%). Spread + slippage + fees.
DEFAULT_COST_BPS = {
    "SPY": 1.5,   # ultra-liquid, penny spreads
    "QQQ": 1.5,
    "GLD": 2.0,
    "USO": 4.0,   # thinner, contango-prone oil ETF
    "BTC-USD": 10.0,  # crypto spreads + fees + slippage are materially higher
}
FALLBACK_COST_BPS = 5.0


def cost_per_turnover(symbol: str, override_bps: float | None = None) -> float:
    """Return the per-unit-turnover cost as a decimal fraction (one-way)."""
    if override_bps is not None:
        bps = override_bps
    else:
        bps = DEFAULT_COST_BPS.get(symbol, FALLBACK_COST_BPS)
    return bps / 10_000.0
