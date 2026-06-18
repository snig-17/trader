"""
risk.py
=======
The risk layer sits BETWEEN the strategy's wishes and the broker, and it has the
final say. The strategy proposes a direction (+1/0/-1) per instrument; the risk
manager decides how big, subject to hard limits the strategy cannot override:

  * ATR volatility targeting   -- constant risk per position across instruments
  * Per-name cap               -- no single position dominates the book
  * Per-cluster cap            -- correlated names (e.g. SPY+EFA) can't secretly
                                  become one giant bet (the SPY~QQQ lesson)
  * Gross leverage cap         -- total |exposure| is bounded
  * Daily-loss killswitch      -- halt + flatten if the day goes badly enough
  * Max-drawdown circuit breaker -- halt + flatten on a peak-to-trough threshold
"""

from __future__ import annotations
import datetime as dt
from config import RiskConfig


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    # --- sizing ---------------------------------------------------------
    def target_exposures(
        self,
        signals: dict[str, float],      # name -> {-1, 0, +1}
        atr_frac: dict[str, float],     # name -> ATR/price (daily)
        groups: dict[str, str],         # name -> correlation group label
    ) -> dict[str, float]:
        """Return name -> signed target exposure as a fraction of equity."""
        c = self.cfg
        expo: dict[str, float] = {}
        for name, sig in signals.items():
            a = atr_frac.get(name)
            if not sig or a is None or a <= 0:
                expo[name] = 0.0
                continue
            raw = c.max_risk_per_trade / (c.k_stop * a)     # vol-target fraction
            expo[name] = float(sig) * min(raw, c.max_position_pct)

        # Cap each correlated cluster's combined gross exposure
        by_group: dict[str, list[str]] = {}
        for name in expo:
            by_group.setdefault(groups.get(name, name), []).append(name)
        for grp, names in by_group.items():
            gross = sum(abs(expo[n]) for n in names)
            if gross > c.per_group_gross_cap and gross > 0:
                scale = c.per_group_gross_cap / gross
                for n in names:
                    expo[n] *= scale

        # Cap total gross leverage
        total = sum(abs(v) for v in expo.values())
        if total > c.max_gross_leverage and total > 0:
            scale = c.max_gross_leverage / total
            expo = {k: v * scale for k, v in expo.items()}
        return expo

    # --- circuit breakers ----------------------------------------------
    def breaker_check(self, equity: float, state: dict) -> tuple[bool, list[str]]:
        """
        Inspect equity against day-start and peak. Mutates `state` (peak/day start)
        and returns (should_halt, reasons). A True here means: cancel, flatten, stop.
        """
        c = self.cfg
        today = dt.date.today().isoformat()
        reasons: list[str] = []

        if state.get("day") != today or "day_start_equity" not in state:
            state["day"] = today
            state["day_start_equity"] = equity
        state["peak_equity"] = max(state.get("peak_equity", equity), equity)

        day_start = state["day_start_equity"] or equity
        peak = state["peak_equity"] or equity
        day_pl = (equity / day_start - 1.0) if day_start else 0.0
        drawdown = (equity / peak - 1.0) if peak else 0.0

        if day_pl <= -c.daily_loss_limit_pct:
            reasons.append(f"daily loss {day_pl:+.1%} <= -{c.daily_loss_limit_pct:.0%}")
        if drawdown <= -c.max_drawdown_pct:
            reasons.append(f"drawdown {drawdown:+.1%} <= -{c.max_drawdown_pct:.0%}")

        state["day_pl"] = day_pl
        state["drawdown"] = drawdown
        return (len(reasons) > 0, reasons)
