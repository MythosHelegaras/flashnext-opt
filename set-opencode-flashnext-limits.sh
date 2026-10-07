#!/usr/bin/env bash
# Set flashnext's limit.context (and optionally limit.output) in OpenCode. Backup, jq-validated, diff-proven.
# Usage: bash set-opencode-flashnext-limits.sh <context> [output]
set -euo pipefail
OC=${OC:-$HOME/.config/opencode/opencode.json}
CTX=${1:?usage: set-opencode-flashnext-limits.sh <context> [output]}; OUT=${2:-}
TS=$(date +%Y%m%d-%H%M%S)
command -v jq >/dev/null || { echo "ABORT: jq missing"; exit 1; }
jq -e . "$OC" >/dev/null || { echo "ABORT: $OC not valid JSON"; exit 1; }
N=$(jq '[.provider // {} | to_entries[] | select(.value.models.flashnext != null)] | length' "$OC")
[[ $N -eq 1 ]] || { echo "ABORT: expected 1 provider with flashnext, found $N"; exit 1; }
FILTER='(.provider[] | select(.models.flashnext != null) | .models.flashnext.limit.context) = ($c|tonumber)'
[[ -n $OUT ]] && FILTER="$FILTER | (.provider[] | select(.models.flashnext != null) | .models.flashnext.limit.output) = (\$o|tonumber)"
TMP=$(mktemp)
jq --arg c "$CTX" --arg o "${OUT:-0}" "$FILTER" "$OC" > "$TMP"
if ! diff <(jq -S 'del(.provider[].models.flashnext.limit)' "$OC") <(jq -S 'del(.provider[].models.flashnext.limit)' "$TMP") >/dev/null; then
  rm -f "$TMP"; echo "ABORT: change touched more than flashnext.limit"; exit 1; fi
if cmp -s "$OC" "$TMP"; then rm -f "$TMP"; echo "Already set."; exit 0; fi
cp -a "$OC" "$OC.bak-$TS"; cp "$TMP" "$OC"; rm -f "$TMP"
diff <(jq -S . "$OC.bak-$TS") <(jq -S . "$OC") || true
echo "Done. Restart OpenCode.  ROLLBACK: cp $OC.bak-$TS $OC"
