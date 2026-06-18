"""
config.py
=========
Central configuration. The single most important default in this whole project:

    MODE = "PAPER"

Live trading is OFF unless you deliberately change three separate things (see
preflight.py). That is on purpose. Everything else here is risk limits and the
instrument universe.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a local .env file into the environment.

    Plain text only, no dependency required. Real environment variables that are
    already set take precedence (so `set -a; source .env` still works too).
    Lines starting with # and blank lines are ignored.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()  # makes `.env` work without manually sourcing it

# ---------------------------------------------------------------------------
# Mode: PAPER (fake money, the default and where you should live for months)
#       LIVE  (real money; gated behind three independent checks)
# ---------------------------------------------------------------------------
MODE = os.getenv("BOT_MODE", "PAPER").upper()

# Alpaca credentials come from the environment only -- never hard-code keys.
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")


@dataclass
class RiskConfig:
    # ATR-based sizing: a position risks this fraction of equity if the stop hits
    max_risk_per_trade: float = 0.01          # 1%
    k_stop: float = 3.0                       # stop sits k_stop * ATR away (trend = wide)
    atr_n: int = 14
    # Hard ceilings enforced regardless of what the strategy wants
    max_position_pct: float = 0.25            # no single name > 25% of equity
    max_gross_leverage: float = 1.5           # sum of |exposures| <= 1.5x equity
    per_group_gross_cap: float = 0.60         # correlated cluster combined exposure cap
    # Circuit breakers
    daily_loss_limit_pct: float = 0.03        # halt + flatten if day P&L <= -3%
    max_drawdown_pct: float = 0.10            # halt + flatten if equity <= peak * (1-10%)


@dataclass
class Instrument:
    name: str            # display
    yf: str              # yfinance symbol (for signal/bar data)
    alpaca: str          # Alpaca trading symbol
    asset_class: str     # 'equity' | 'crypto'
    group: str           # correlation group label


# A genuinely cross-asset trend universe -- more honest than five risk-on names,
# though real diversified trend uses dozens of futures (see README).
UNIVERSE: list[Instrument] = [
    Instrument("US equity",    "SPY",     "SPY", "equity", "equity"),
    Instrument("Intl equity",  "EFA",     "EFA", "equity", "equity"),
    Instrument("Treasuries",   "IEF",     "IEF", "equity", "rates"),
    Instrument("Gold",         "GLD",     "GLD", "equity", "metals"),
    Instrument("Commodities",  "DBC",     "DBC", "equity", "commodity"),
    # Crypto trades 24/7; uncomment to include (needs crypto enabled on the account):
    # Instrument("Bitcoin",    "BTC-USD", "BTC/USD", "crypto", "crypto"),
]

# Strategy: 'trend' is the default because it is the only family with deep
# out-of-sample academic support. 'mean_reversion' and 'breakout' are available
# for experimentation but the validation gate will (correctly) refuse to let them
# go live until they actually pass.
STRATEGY = os.getenv("BOT_STRATEGY", "trend")
STRATEGY_PARAMS = {
    "trend":          dict(fast=50, slow=200, allow_short=False),
    "mean_reversion": dict(lookback=20, z_entry=1.5, allow_short=False),
    "breakout":       dict(lookback=20, vol_mult=1.5, trail_k=2.0, allow_short=False),
}

RISK = RiskConfig()

# ---------------------------------------------------------------------------
# Paths (state, journals, validation reports, manual safety files)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, "state")
JOURNAL_DIR = os.path.join(BASE_DIR, "journal")
VALIDATION_DIR = os.path.join(BASE_DIR, "validation_reports")
for _d in (STATE_DIR, JOURNAL_DIR, VALIDATION_DIR):
    os.makedirs(_d, exist_ok=True)

STATE_FILE = os.path.join(STATE_DIR, "bot_state.json")
KILL_FILE = os.path.join(BASE_DIR, "KILL")            # touch this file to halt instantly
LIVE_TOKEN_FILE = os.path.join(BASE_DIR, "LIVE_AUTHORIZED")  # must be created by hand for live
HALT_FILE = os.path.join(STATE_DIR, "HALTED")          # written when a breaker trips

# Live-gate: a validation report must be this fresh (days) and must pass.
VALIDATION_MAX_AGE_DAYS = 30
VALIDATION_MIN_DSR = 0.95
