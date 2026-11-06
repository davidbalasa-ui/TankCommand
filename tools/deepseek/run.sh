#!/bin/bash
# run.sh WP-03 [MAX_FIX_ROUNDS=8] [EXTRA_FEEDBACK_FILE]
# With EXTRA_FEEDBACK_FILE (for example a CI log or review notes), it resumes the package's latest
# DeepSeek conversation with that feedback instead of starting over.
# Round 1 builds the package from its spec; then fix rounds feed real check output back until
# everything passes or MAX_FIX_ROUNDS is reached. When green, one or two visual rounds send
# phone screenshots. Stops early if the same failures repeat 3 rounds running.
# Everything lands in .deepseek-runs/<pkg>/; the final line of SUMMARY.txt is GREEN or STUCK.
# Nothing is committed or pushed: a reviewer does that.
set -u
PKG=$1; MAX=${2:-8}; EXTRA=${3:-}
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
T=$ROOT/tools/deepseek; D=$ROOT/.deepseek-runs/$PKG; mkdir -p "$D"
S=$D/SUMMARY.txt; [ -z "$EXTRA" ] && : > "$S"
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$S"; }
sig() { grep -E "^\s+[0-9]+\) |error TS|FAIL |✗|×" "$1" | sed -E 's/[0-9]+ms|\([0-9.]+m?s\)//g' | sort | md5sum | cut -c1-8; }

if [ -n "$EXTRA" ]; then
  R=$(ls "$D"/r*.txt.convo.json 2>/dev/null | sed -E 's/.*\/r([0-9]+)\.txt\.convo\.json/\1/' | sort -n | tail -1)
  [ -z "$R" ] && { echo "no earlier run for $PKG"; exit 2; }
  CONVO=$D/r$R.txt.convo.json; R=$((R+1))
  cat "$T/fixhead.txt" "$EXTRA" > "$D/prompt_r$R.txt"
  log "round $R (extra feedback $EXTRA): $(python3 "$T/ds.py" cont "$CONVO" "$D/prompt_r$R.txt" "$D/r$R.txt")"
  log "round $R applied: $(python3 "$T/apply.py" "$D/r$R.txt" . "$D/report_r$R.md")"
  CONVO=$D/r$R.txt.convo.json; MAX=$((R+MAX-1))
else
  python3 "$T/pack.py" "$PKG" "$D/prompt_r1.txt" | tee -a "$S"
  log "round 1: $(python3 "$T/ds.py" new "$D/prompt_r1.txt" "$D/r1.txt")"
  log "round 1 applied: $(python3 "$T/apply.py" "$D/r1.txt" . "$D/report_r1.md")"
  CONVO=$D/r1.txt.convo.json; R=1
fi
LAST=""; SAME=0
while true; do
  ST=$("$T/check.sh" "$D/fb_r$R.txt"); OK=$?
  log "round $R checks:$ST"
  [ $OK -eq 0 ] && break
  if [ $R -gt "$MAX" ]; then log "STUCK: still failing after $MAX fix rounds"; echo STUCK >> "$S"; exit 1; fi
  SG=$(sig "$D/fb_r$R.txt"); if [ "$SG" = "$LAST" ]; then SAME=$((SAME+1)); else SAME=0; fi; LAST=$SG
  if [ $SAME -ge 2 ]; then log "STUCK: same failures 3 rounds running"; echo STUCK >> "$S"; exit 1; fi
  R=$((R+1))
  cat "$T/fixhead.txt" "$D/fb_r$((R-1)).txt" > "$D/prompt_r$R.txt"
  log "round $R: $(python3 "$T/ds.py" cont "$CONVO" "$D/prompt_r$R.txt" "$D/r$R.txt")"
  log "round $R applied: $(python3 "$T/apply.py" "$D/r$R.txt" . "$D/report_r$R.md")"
  CONVO=$D/r$R.txt.convo.json
done

# Visual rounds: phone screenshots the package's screens.spec wrote.
for V in 1 2; do
  P=$(echo "$PKG" | tr -d "-" | tr "A-Z" "a-z")
  mapfile -t SHOTS < <(ls test-results/shots/$P-*.png 2>/dev/null | sort -V | head -8)
  if [ ${#SHOTS[@]} -eq 0 ]; then log "visual: no screenshots in test-results/shots/ (package must add them)"; break; fi
  mkdir -p "$D/shots_v$V"; cp "${SHOTS[@]}" "$D/shots_v$V/"
  R=$((R+1))
  { cat "$T/visualhead.txt"; printf '\nScreenshots, in order: %s\n' "$(for s in "${SHOTS[@]}"; do basename "$s"; done | tr '\n' ' ')"; } > "$D/prompt_r$R.txt"
  log "round $R (visual $V): $(python3 "$T/ds.py" cont "$CONVO" "$D/prompt_r$R.txt" "$D/r$R.txt" "${SHOTS[@]}")"
  APPLIED=$(python3 "$T/apply.py" "$D/r$R.txt" . "$D/report_r$R.md"); log "round $R applied: $APPLIED"
  CONVO=$D/r$R.txt.convo.json
  case "$APPLIED" in 0\ files*) log "visual: DeepSeek reports nothing to fix"; break;; esac
  # Visual fixes must not break anything: re-run checks, and give it two tries to repair.
  for k in 1 2 3; do
    ST=$("$T/check.sh" "$D/fb_r$R.txt"); OK=$?; log "round $R checks:$ST"
    [ $OK -eq 0 ] && break
    [ $k -eq 3 ] && { log "STUCK: visual fixes broke checks"; echo STUCK >> "$S"; exit 1; }
    R=$((R+1)); cat "$T/fixhead.txt" "$D/fb_r$((R-1)).txt" > "$D/prompt_r$R.txt"
    log "round $R: $(python3 "$T/ds.py" cont "$CONVO" "$D/prompt_r$R.txt" "$D/r$R.txt")"
    log "round $R applied: $(python3 "$T/apply.py" "$D/r$R.txt" . "$D/report_r$R.md")"
    CONVO=$D/r$R.txt.convo.json
  done
done
for f in $(ls "$D"/report_r*.md | sort -V); do echo "## $(basename $f)"; cat "$f"; echo; done > "$D/REPORTS.md"
echo GREEN >> "$S"
