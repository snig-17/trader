"""
journal.py
==========
Persistent state (peak equity, day-start equity, error counters) and append-only
journals. Every trading decision is written WITH its rationale before the order is
sent, so when something misbehaves you can read exactly why each trade happened.
"""

from __future__ import annotations
import csv
import json
import os
import datetime as dt
import config


def load_state() -> dict:
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _append_csv(path: str, header: list[str], row: dict) -> None:
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in header})


def journal_decision(rows: list[dict]) -> None:
    path = os.path.join(config.JOURNAL_DIR, f"decisions_{dt.date.today():%Y}.csv")
    header = ["timestamp", "mode", "symbol", "signal", "current_expo",
              "target_expo", "delta_notional", "action", "price", "rationale"]
    ts = dt.datetime.now().isoformat(timespec="seconds")
    for r in rows:
        r = {**r, "timestamp": ts, "mode": config.MODE}
        _append_csv(path, header, r)


def journal_pnl(equity: float, day_pl: float, drawdown: float) -> None:
    path = os.path.join(config.JOURNAL_DIR, "pnl.csv")
    header = ["date", "mode", "equity", "day_pl", "drawdown"]
    _append_csv(path, header, {
        "date": dt.date.today().isoformat(), "mode": config.MODE,
        "equity": round(equity, 2), "day_pl": round(day_pl, 5),
        "drawdown": round(drawdown, 5),
    })
