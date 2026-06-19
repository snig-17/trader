#!/bin/zsh
# Runs the local account health check after the US close. Invoked by launchd.
set -e
cd "$HOME/trader"
source .venv/bin/activate
set -a; source .env; set +a
mkdir -p logs
python monitor.py >> "logs/monitor-run-$(date +%Y-%m).log" 2>&1
