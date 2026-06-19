"""
monitor.py
==========
Local, read-only health check for the bot. Run after the US close (or anytime).
It connects to the SAME Alpaca account the bot uses (paper by default), reports
equity / positions / day P&L / drawdown, and surfaces any halt condition.

This is intentionally LOCAL: it needs the .env Alpaca keys and the local journal/
state, which Claude's cloud routines cannot see. The cloud routines cover
re-validation and the research digest; this covers the daily account snapshot.

Run:  python monitor.py
Exit code is non-zero if a halt/kill condition is active, so a scheduler/log makes
problems obvious.
"""

from __future__ import annotations
import os
import sys
import json
import datetime as dt
import subprocess

import config
import journal as J


def _notify(title: str, message: str) -> None:
    """Best-effort macOS notification; silently no-ops elsewhere."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification {json.dumps(message, ensure_ascii=False)} '
             f'with title {json.dumps(title, ensure_ascii=False)}'],
            check=False, capture_output=True, timeout=5,
        )
    except Exception:
        pass


def main() -> int:
    now = dt.datetime.now().isoformat(timespec="seconds")
    kill = os.path.exists(config.KILL_FILE)
    halted = os.path.exists(config.HALT_FILE)
    state = J.load_state()

    lines = [f"=== Trader monitor {now} ===", f"mode: {config.MODE}"]
    problem = kill or halted

    # Account snapshot (best-effort; never crash the monitor on a broker hiccup)
    equity = None
    positions = {}
    broker_err = None
    try:
        from broker import AlpacaBroker
        b = AlpacaBroker(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY,
                         paper=(config.MODE == "PAPER"))
        equity = b.get_equity()
        positions = b.get_positions()
    except Exception as e:
        broker_err = str(e)
        problem = True

    if equity is not None:
        lines.append(f"equity: ${equity:,.2f}")
    if broker_err:
        lines.append(f"BROKER ERROR: {broker_err}")

    day_pl = state.get("day_pl")
    dd = state.get("drawdown")
    if day_pl is not None:
        lines.append(f"day P&L: {day_pl:+.2%}")
    if dd is not None:
        lines.append(f"drawdown from peak: {dd:+.2%}")

    if positions:
        inv = sum(abs(p.market_value) for p in positions.values())
        lines.append(f"positions ({len(positions)}, gross ${inv:,.0f}):")
        for sym, p in sorted(positions.items()):
            w = (p.market_value / equity) if equity else 0.0
            lines.append(f"  {sym:<6} qty {p.qty:>10.3f}  ${p.market_value:>12,.2f}  {w:+.1%}")
    elif equity is not None:
        lines.append("positions: none (flat)")

    if halted:
        lines.append("** HALTED file present — breaker tripped; book should be flat. Review before re-enabling. **")
    if kill:
        lines.append("** KILL file present — trading is manually disabled. **")
    if not problem:
        lines.append("status: OK")

    report = "\n".join(lines)
    print(report)

    # Append to a dated log
    try:
        log_dir = os.path.join(config.BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, f"monitor-{dt.date.today():%Y-%m}.log"), "a") as f:
            f.write(report + "\n\n")
    except Exception:
        pass

    headline = "Trader: attention needed" if problem else "Trader: OK"
    summary = (f"${equity:,.0f}" if equity is not None else "no equity") + \
              (f", {len(positions)} positions" if positions else ", flat")
    if problem:
        summary = "HALT/KILL/error — check logs"
    _notify(headline, summary)

    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
