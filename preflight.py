"""
preflight.py
============
Safety checks that run before any trading, and the live-trading gate.

Going LIVE requires THREE independent things to all be true. Any one missing and
the bot refuses to start in live mode (paper always works). This makes "oops I
flipped it to live on an untested strategy" structurally hard rather than one
config flag away:

  1. BOT_MODE=LIVE  AND  env I_UNDERSTAND_LIVE_RISK=YES
  2. A hand-created token file `LIVE_AUTHORIZED` exists in the project folder
  3. A fresh, PASSING validation report exists for the configured strategy
     (Deflated Sharpe >= threshold, positive out-of-sample Sharpe, recent)

Plus two manual stops that apply in every mode:
  * `KILL` file present  -> halt immediately
  * `HALTED` file present -> a breaker tripped earlier; refuses to resume until
    you delete it (forces a human to look before restarting)
"""

from __future__ import annotations
import os
import json
import datetime as dt
import config


class TradingHalted(RuntimeError):
    pass


def kill_file_present() -> bool:
    return os.path.exists(config.KILL_FILE)


def halt_file_present() -> bool:
    return os.path.exists(config.HALT_FILE)


def write_halt(reasons: list[str]) -> None:
    with open(config.HALT_FILE, "w") as f:
        f.write(f"HALTED {dt.datetime.now().isoformat()}\n")
        for r in reasons:
            f.write(f"- {r}\n")


def validation_passed(strategy: str) -> tuple[bool, str]:
    """A strategy may go live only if a recent, passing validation report exists."""
    path = os.path.join(config.VALIDATION_DIR, f"{strategy}.json")
    if not os.path.exists(path):
        return False, f"no validation report at {os.path.relpath(path, config.BASE_DIR)}"
    try:
        with open(path) as f:
            rep = json.load(f)
    except Exception as e:
        return False, f"unreadable validation report: {e}"

    dsr = rep.get("deflated_sharpe")
    oos = rep.get("oos_sharpe")
    gen = rep.get("generated_at")
    try:
        age_days = (dt.datetime.now() - dt.datetime.fromisoformat(gen)).days
    except Exception:
        return False, "validation report missing/invalid 'generated_at'"

    if dsr is None or dsr < config.VALIDATION_MIN_DSR:
        return False, f"deflated Sharpe {dsr} < {config.VALIDATION_MIN_DSR} (edge not significant)"
    if oos is None or oos <= 0:
        return False, f"out-of-sample Sharpe {oos} is not positive"
    if age_days > config.VALIDATION_MAX_AGE_DAYS:
        return False, f"validation report is {age_days}d old (> {config.VALIDATION_MAX_AGE_DAYS}d)"
    return True, f"passed (DSR={dsr:.2f}, OOS Sharpe={oos:.2f}, age={age_days}d)"


def require_live_authorization(strategy: str) -> None:
    missing: list[str] = []
    if config.MODE != "LIVE":
        missing.append("BOT_MODE is not LIVE")
    if os.getenv("I_UNDERSTAND_LIVE_RISK", "").upper() != "YES":
        missing.append("env I_UNDERSTAND_LIVE_RISK!=YES")
    if not os.path.exists(config.LIVE_TOKEN_FILE):
        missing.append(f"missing token file {os.path.basename(config.LIVE_TOKEN_FILE)}")
    ok, detail = validation_passed(strategy)
    if not ok:
        missing.append(f"validation gate: {detail}")
    if missing:
        raise TradingHalted(
            "LIVE trading refused. Unmet conditions:\n  - " + "\n  - ".join(missing)
        )


def assert_can_trade(strategy: str) -> None:
    """Run all gates appropriate to the current mode. Raises TradingHalted to stop."""
    if kill_file_present():
        raise TradingHalted("KILL file present -> manual halt. Delete it to resume.")
    if halt_file_present():
        raise TradingHalted("HALTED file present (a breaker tripped). Review, then delete it.")
    if config.MODE == "LIVE":
        require_live_authorization(strategy)
    elif config.MODE != "PAPER":
        raise TradingHalted(f"Unknown BOT_MODE={config.MODE!r}; use PAPER or LIVE.")
