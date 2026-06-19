# Automation

Three layers, split by where each one *can* run.

## Trade loop → GitHub Actions (the sole trader)
The daily rebalance runs on GitHub Actions, NOT locally — see
`.github/workflows/daily-trade.yml`. A daily-bar bot only needs to fire once a day,
so an ephemeral scheduled runner is the right model (no 24/7 box, free, and it works
even with your Mac off). It is the **only** thing that places orders.

> Do NOT also schedule the trade loop locally — two schedulers on one Alpaca account
> double-trade. That is why there is no `com.trader.trade` agent here anymore.

Setup: add `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` as repo Actions secrets
(Settings → Secrets and variables → Actions). The workflow is PAPER-only.

## Monthly re-validation → GitHub Actions
`.github/workflows/monthly-validate.yml` runs `validate_for_live.py` on the 1st of each
month (GitHub runners have open internet, so yfinance works — the Claude cloud sandbox
does not). It COMMITS the refreshed `validation_reports/trend.json` so the daily-trade
workflow actually picks up new winner params + live-gate freshness, and files the
PASS / EDGE-DEGRADED result as a GitHub issue. No Alpaca keys needed.

## Cloud research digest → Claude scheduled routine
Manage at https://claude.ai/code/routines. Monthly (1st, 09:00 UTC, Opus): web-
researches trend-following developments and files a cited GitHub issue (human-review
input only). Reports via a GitHub issue, not email (Gmail connector only drafts).

## Local (this folder — launchd, non-trading helper)
Only the monitor runs locally now; it does NOT place orders, so it is safe alongside
the cloud trader. (Trade + re-validation moved to GitHub Actions.)

- `run_monitor.sh` → `monitor.py` — after-close account snapshot (equity, positions,
  day P&L, drawdown, HALT/KILL), logs to `logs/` + a macOS notification.

### Install
```bash
chmod +x ~/trader/automation/run_monitor.sh
# (if your macOS username is NOT "snigdhatiwari", edit the plist's absolute paths)
cp ~/trader/automation/com.trader.monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.trader.monitor.plist
launchctl list | grep com.trader
```

### Test / uninstall
```bash
~/trader/automation/run_monitor.sh && tail -n 30 ~/trader/logs/monitor-run-*.log
launchctl unload ~/Library/LaunchAgents/com.trader.monitor.plist && rm ~/Library/LaunchAgents/com.trader.monitor.plist
```
