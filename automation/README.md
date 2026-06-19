# Automation

Two layers, split by where they *can* run:

## Cloud (already set up — Claude scheduled routines)
These run in Anthropic's cloud from the GitHub repo. They do **not** touch your Mac,
keys, or account; they only need the public code + internet. Manage/disable at
https://claude.ai/code/routines

- **Monthly re-validation** — 1st of month, 08:00 UTC. Clones the repo, runs
  `validate_for_live.py` (public yfinance data, no keys), emails PASS / ⚠️ EDGE
  DEGRADED to your Gmail.
- **Monthly research digest** — 1st of month, 09:00 UTC. Web-researches trend-
  following developments and emails a cited digest (input to human review only).

## Local (this folder — launchd, needs your keys)
The **trade loop** and **daily monitor** need the Alpaca keys in `.env` and the
local venv/journal, so they cannot run in the cloud. They run on this Mac via
`launchd`.

- `run_trade.sh` → `bot.py once` — one daily rebalance (paper). Safe when the
  market is closed (logs SKIP, places nothing).
- `run_monitor.sh` → `monitor.py` — after-close account snapshot (equity,
  positions, day P&L, drawdown, HALT/KILL), logs to `logs/` + a macOS notification.

### Install
```bash
# 1. make the wrappers executable
chmod +x ~/trader/automation/run_trade.sh ~/trader/automation/run_monitor.sh

# 2. (if your macOS username is NOT "snigdhatiwari") fix the absolute paths:
#    edit the two .plist files and replace /Users/snigdhatiwari with your $HOME

# 3. copy the LaunchAgents into place and load them
cp ~/trader/automation/com.trader.trade.plist   ~/Library/LaunchAgents/
cp ~/trader/automation/com.trader.monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.trader.trade.plist
launchctl load ~/Library/LaunchAgents/com.trader.monitor.plist

# verify
launchctl list | grep com.trader
```

### Schedule (Europe/London local time)
- Trade: weekdays **15:00** (~10:00 ET, mid US session).
- Monitor: weekdays **21:15** (~16:15 ET, just after the close).

Adjust the `Hour`/`Minute` in each plist if you prefer. (Daily-bar trend signals
barely change intraday, so exact timing is not critical — the bot also checks the
Alpaca market clock and skips when closed.)

### Test without waiting
```bash
~/trader/automation/run_monitor.sh && tail -n 30 ~/trader/logs/monitor-run-*.log
launchctl start com.trader.monitor   # fire the agent immediately
```

### Uninstall
```bash
launchctl unload ~/Library/LaunchAgents/com.trader.trade.plist
launchctl unload ~/Library/LaunchAgents/com.trader.monitor.plist
rm ~/Library/LaunchAgents/com.trader.{trade,monitor}.plist
```

### ⚠️ Reliability caveat
`launchd` only fires while the Mac is **awake**; a missed weekday slot runs once on
the next wake, which may be hours late or skipped. A closed laptop = no trades. For
dependable daily execution, run the trade loop on a small always-on **VPS** instead
(copy the repo, create the venv, add `.env`, and use `cron`:
`0 14 * * 1-5 cd ~/trader && . .venv/bin/activate && set -a; . .env; set +a; python bot.py once`).
The cloud routines above are unaffected by your Mac being off.
