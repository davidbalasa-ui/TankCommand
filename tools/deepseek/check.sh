#!/bin/bash
# check.sh FEEDBACK_OUT -> runs every check, writes trimmed real failures to FEEDBACK_OUT,
# prints one status line. Exit 0 only when everything (including e2e) passes.
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
OUT=$1; : > "$OUT"; STATUS=""; FAIL=0; LOG=$(mktemp -d)
npm install --no-audit --no-fund > "$LOG/install.log" 2>&1 || { echo "=== npm install FAILED ===" >> "$OUT"; tail -40 "$LOG/install.log" >> "$OUT"; FAIL=1; }
for s in typecheck lint test credits:check coverage:req build; do
  npm run -s $s > "$LOG/$s.log" 2>&1; rc=$?
  STATUS="$STATUS $s=$rc"
  if [ $rc -ne 0 ]; then
    FAIL=1
    echo "=== npm run $s FAILED (exit $rc) ===" >> "$OUT"
    grep -vE "^\s*$" "$LOG/$s.log" | grep -E "error|Error|FAIL|✗|×|expected|Expected|Received|AssertionError|TypeError|›|❯" | head -150 >> "$OUT"
    tail -30 "$LOG/$s.log" >> "$OUT"
  fi
done
# Only run the browser tests when the static checks pass; their failures would just be noise.
if [ $FAIL -eq 0 ]; then
  pkill -f "vite preview" 2>/dev/null; rm -rf test-results/shots
  CI=1 timeout 1800 npx playwright test --reporter=line > "$LOG/e2e.log" 2>&1; rc=$?
  STATUS="$STATUS e2e=$rc($(grep -E '^\s+[0-9]+ (passed|failed|flaky|skipped)' "$LOG/e2e.log" | tr -s ' \n' ' '))"
  if [ $rc -ne 0 ]; then
    FAIL=1
    echo "=== npm run test:e2e FAILED ===" >> "$OUT"
    awk '/^  [0-9]+\) /{p=1} p' "$LOG/e2e.log" | grep -vE "trace|show-trace|attachment|─|Usage|^\s*$" | head -250 >> "$OUT"
    tail -15 "$LOG/e2e.log" >> "$OUT"
  fi
  pkill -f "vite preview" 2>/dev/null
else
  STATUS="$STATUS e2e=skipped"
fi
rm -rf "$LOG"
echo "$STATUS"
exit $FAIL
