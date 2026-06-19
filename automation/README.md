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

## Cloud research digest → Claude scheduled routine
Manage at https://claude.ai/code/routines. Monthly (1st, 09:00 UTC, Opus): web-
researches trend-following developments and files a cited GitHub issue (human-review
input only). Reports via a GitHub issue, not email (Gmail connector only drafts).

## Local (this folder — launchd, non-trading helpers)
These do NOT place orders, so they are safe to run locally alongside the cloud trader.

- `run_monitor.sh` → `monitor.py` — after-close account snapshot (equity, positions,
  day P&L, drawdown, HALT/KILL), logs to `logs/` + a macOS notification.
- `run_validate.sh` → `validate_for_live.py` — monthly walk-forward re-validation;
  logs + macOS notification (PASS / EDGE DEGRADED). yfinance works locally (the Claude
  cloud sandbox blocks Yahoo Finance, which is why this is not a cloud routine).

> NOTE: `run_validate.sh` writes `validation_reports/trend.json` LOCALLY. The GitHub
> Actions trader reads the *committed* report, so to push new validated params to the
> cloud trader you must commit + push the updated `trend.json`.

### Install
```bash
# 1. make the wrappers executable
chmod +x ~/trader/automation/run_monitor.sh ~/trader/automation/run_validate.sh

# 2. (if your macOS username is NOT "snigdhatiwari") fix the absolute paths:
#    edit the two .plist files and replace /Users/snigdhatiwari with your $HOME

# 3. copy the LaunchAgents into place and load them
cp ~/trader/automation/com.trader.monitor.plist  ~/Library/LaunchAgents/
cp ~/trader/automation/com.trader.validate.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.trader.monitor.plist
launchctl load ~/Library/LaunchAgents/com.trader.validate.plist

# verify
launchctl list | grep com.trader
```

### Schedule (Europe/London local time)
- Monitor: weekdays **21:15** (~16:15 ET, just after the close).
- Re-validation: **1st of each month, 09:00**.

### Test without waiting
```bash
~/trader/automation/run_monitor.sh && tail -n 30 ~/trader/logs/monitor-run-*.log
launchctl start com.trader.monitor   # fire the agent immediately
```

### Uninstall
```bash
launchctl unload ~/Library/LaunchAgents/com.trader.monitor.plist
launchctl unload ~/Library/LaunchAgents/com.trader.validate.plist
rm ~/Library/LaunchAgents/com.trader.{monitor,validate}.plist
```
