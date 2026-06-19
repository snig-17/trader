#!/bin/zsh
# Monthly walk-forward re-validation, run LOCALLY (the cloud sandbox blocks Yahoo
# Finance egress, so validation must run where yfinance works). Logs the result and
# fires a macOS notification with PASS/FAIL. Invoked by launchd.
set -e
cd "$HOME/trader"
source .venv/bin/activate
set -a; source .env; set +a
mkdir -p logs
LOG="logs/validate-$(date +%Y-%m).log"
echo "----- $(date '+%Y-%m-%d %H:%M:%S %Z') re-validation -----" >> "$LOG"
python validate_for_live.py >> "$LOG" 2>&1 || true

# Parse the report and notify (PASS only if the gate is cleared).
python - >> "$LOG" 2>&1 <<'PY'
import json, subprocess
try:
    r = json.load(open("validation_reports/trend.json"))
    ok = bool(r.get("passing"))
    msg = (("PASS" if ok else "FAIL") +
           f" - IS {r.get('is_sharpe')} / OOS {r.get('oos_sharpe')} / DSR {r.get('deflated_sharpe')}")
    title = "Trader re-validation: PASS" if ok else "Trader re-validation: EDGE DEGRADED"
except Exception as e:
    msg, title = f"validation error: {e}", "Trader re-validation: RUN ERROR"
subprocess.run(["osascript", "-e",
                f'display notification {json.dumps(msg, ensure_ascii=False)} '
                f'with title {json.dumps(title, ensure_ascii=False)}'],
               check=False)
print(msg)
PY
