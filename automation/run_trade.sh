#!/bin/zsh
# Runs one daily rebalance pass (paper). Safe to fire even when the US market is
# closed — bot.py logs SKIP_MARKET_CLOSED and places nothing. Invoked by launchd.
set -e
cd "$HOME/trader"
source .venv/bin/activate
set -a; source .env; set +a
mkdir -p logs
echo "----- $(date '+%Y-%m-%d %H:%M:%S %Z') run_trade -----" >> "logs/trade-$(date +%Y-%m).log"
python bot.py once >> "logs/trade-$(date +%Y-%m).log" 2>&1
