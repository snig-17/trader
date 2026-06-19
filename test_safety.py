"""
test_safety.py
==============
Proves the safety machinery works, with zero credentials and zero risk, using the
MockBroker and synthetic data. Run:  python test_safety.py

It exercises:
  1. Position sizing + hard caps (per-name, per-cluster, gross leverage)
  2. Daily-loss killswitch
  3. Max-drawdown circuit breaker
  4. The three-gate LIVE authorization refusing an un-validated strategy
  5. The KILL file halting instantly
  6. End-to-end: a normal paper rebalance, then a crash that trips the breaker
     and auto-flattens the book
"""

from __future__ import annotations
import os
import numpy as np
import pandas as pd

import config
import journal as J
import preflight
from preflight import TradingHalted
from risk import RiskManager
from broker import MockBroker
import data as engine_data
import bot


def _clean():
    for f in (config.KILL_FILE, config.HALT_FILE, config.LIVE_TOKEN_FILE, config.STATE_FILE):
        if os.path.exists(f):
            os.remove(f)


def _synthetic_uptrend(n=420, start=100.0, drift=0.0015, vol=0.006, seed=1):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = start * np.cumprod(1 + rets)
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="B")
    high = close * (1 + np.abs(rng.normal(0, vol / 2, n)))
    low = close * (1 - np.abs(rng.normal(0, vol / 2, n)))
    return pd.DataFrame({"open": close, "high": high, "low": low,
                         "close": close, "volume": 1e6}, index=idx)


def ok(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    assert cond, msg


def test_sizing_and_caps():
    print("\n[1] Position sizing + hard caps")
    rm = RiskManager(config.RISK)
    # Two equity names both long, plus gold long. ATR/price ~1.5% daily.
    signals = {"US equity": 1, "Intl equity": 1, "Gold": 1}
    atr = {"US equity": 0.015, "Intl equity": 0.015, "Gold": 0.012}
    groups = {"US equity": "equity", "Intl equity": "equity", "Gold": "metals"}
    expo = rm.target_exposures(signals, atr, groups)

    ok(all(abs(v) <= config.RISK.max_position_pct + 1e-9 for v in expo.values()),
       f"every position <= max_position_pct ({config.RISK.max_position_pct:.0%})")
    eq_gross = abs(expo["US equity"]) + abs(expo["Intl equity"])
    ok(eq_gross <= config.RISK.per_group_gross_cap + 1e-9,
       f"equity cluster gross {eq_gross:.2f} <= per_group_gross_cap ({config.RISK.per_group_gross_cap})")
    total = sum(abs(v) for v in expo.values())
    ok(total <= config.RISK.max_gross_leverage + 1e-9,
       f"total gross {total:.2f} <= max_gross_leverage ({config.RISK.max_gross_leverage})")


def test_daily_loss_killswitch():
    print("\n[2] Daily-loss killswitch")
    rm = RiskManager(config.RISK)
    state = {}
    halt, _ = rm.breaker_check(100_000, state)          # establishes day-start
    ok(not halt, "no halt at start of day")
    halt, reasons = rm.breaker_check(96_000, state)     # -4% on the day
    ok(halt and any("daily loss" in r for r in reasons), f"halts on -4% day: {reasons}")


def test_drawdown_breaker():
    print("\n[3] Max-drawdown circuit breaker")
    rm = RiskManager(config.RISK)
    # Same-day, small daily move but 11% below the peak -> drawdown breaker only.
    import datetime as dt
    state = {"day": dt.date.today().isoformat(), "day_start_equity": 90_000, "peak_equity": 100_000}
    halt, reasons = rm.breaker_check(89_000, state)
    ok(halt and any("drawdown" in r for r in reasons), f"halts at -11% from peak: {reasons}")


def test_live_gate_refuses():
    print("\n[4] LIVE gate refuses an un-validated strategy")
    _clean()
    os.environ.pop("I_UNDERSTAND_LIVE_RISK", None)
    saved = config.MODE
    config.MODE = "LIVE"
    try:
        # 'breakout' has no validation report -> validation gate must also fail
        preflight.require_live_authorization("breakout")
        ok(False, "should have refused live")
    except TradingHalted as e:
        msg = str(e)
        ok("validation gate" in msg and "token file" in msg,
           "refuses: missing token + missing passing validation report")
    finally:
        config.MODE = saved


def test_kill_file():
    print("\n[5] KILL file halts instantly")
    _clean()
    open(config.KILL_FILE, "w").close()
    try:
        preflight.assert_can_trade(config.STRATEGY)
        ok(False, "should have halted on KILL file")
    except TradingHalted as e:
        ok("KILL file" in str(e), "KILL file blocks trading")
    finally:
        _clean()


def test_end_to_end_then_crash():
    print("\n[6] End-to-end paper rebalance, then crash trips the breaker")
    _clean()
    config.MODE = "PAPER"
    # Deterministic synthetic data so the trend signal is reliably long.
    engine_data.load = lambda symbol, period="2y": _synthetic_uptrend()
    prices = {i.alpaca: 100.0 for i in config.UNIVERSE}
    mb = MockBroker(equity=100_000.0, prices=prices, market_open=True)

    r1 = bot.run_once(mb, dry_run=False)
    invested = any(abs(p.qty) > 0 for p in mb.get_positions().values())
    ok(r1.get("orders_placed", 0) > 0 and invested,
       f"normal run placed {r1.get('orders_placed')} orders, book is invested")
    # targets are reported rounded to 4 dp, so summing N of them can drift up to
    # N*5e-5 above the true (correctly-capped) gross. Tolerate display rounding only.
    rounding_tol = len(r1["targets"]) * 5e-5
    ok(sum(abs(v) for v in r1["targets"].values()) <= config.RISK.max_gross_leverage + rounding_tol,
       "targets respected the gross-leverage cap")

    # Crash all prices 15%; force day-start high so the daily-loss breaker fires.
    for s in prices:
        mb.set_price(s, 85.0)
    st = J.load_state()
    st["day_start_equity"] = 100_000.0
    st["peak_equity"] = 100_000.0
    J.save_state(st)

    r2 = bot.run_once(mb, dry_run=False)
    flat = len(mb.get_positions()) == 0
    ok("halted" in r2 and flat and os.path.exists(config.HALT_FILE),
       f"breaker halted + flattened book; HALT file written ({r2.get('halted')})")
    _clean()


if __name__ == "__main__":
    print("=" * 70)
    print(" SAFETY TEST SUITE (MockBroker, no credentials, no network)")
    print("=" * 70)
    test_sizing_and_caps()
    test_daily_loss_killswitch()
    test_drawdown_breaker()
    test_live_gate_refuses()
    test_kill_file()
    test_end_to_end_then_crash()
    print("\nAll safety checks passed.\n")
