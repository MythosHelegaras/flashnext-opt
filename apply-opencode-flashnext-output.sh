#!/usr/bin/env bash
# Raise OpenCode's output cap for the flashnext model (limit.output 32768 -> 65536 by default).
# Touches only the flashnext entry's limit.output. Backup + jq validation + diff + rollback line.
# Usage: bash apply-opencode-flashnext-output.sh [new_limit]
set -euo pipefail
OC=${OC:-$HOME/.config/opencode/opencode.json}
NEW=${1:-65536}
TS=$(date +%Y%m%d-%H%M%S)

[[ -f $OC ]] || { echo "ABORT: $OC not found"; exit 1; }
command -v jq >/dev/null || { echo "ABORT: jq missing"; exit 1; }
[[ $NEW =~ ^[0-9]+$ && $NEW -ge 4096 && $NEW -le 131072 ]] || { echo "ABORT: limit must be 4096..131072"; exit 1; }
jq -e . "$OC" >/dev/null || { echo "ABORT: $OC is not valid JSON (comments?)"; exit 1; }

N=$(jq '[.provider // {} | to_entries[] | select(.value.models.flashnext != null)] | length' "$OC")
[[ $N -eq 1 ]] || { echo "ABORT: expected exactly 1 provider with a flashnext model, found $N"; exit 1; }
OLD=$(jq -r '.provider[] | select(.models.flashnext != null) | .models.flashnext.limit.output // "unset"' "$OC")
echo "flashnext limit.output: $OLD -> $NEW"
[[ $OLD == "$NEW" ]] && { echo "Already set. Nothing to do."; exit 0; }

cp -a "$OC" "$OC.bak-$TS"
TMP=$(mktemp)
jq --argjson n "$NEW" '(.provider[] | select(.models.flashnext != null) | .models.flashnext.limit.output) = $n' "$OC" > "$TMP"
jq -e . "$TMP" >/dev/null
# Prove nothing else changed
if ! diff <(jq -S 'del(.provider[].models.flashnext.limit.output)' "$OC") \
          <(jq -S 'del(.provider[].models.flashnext.limit.output)' "$TMP") >/dev/null; then
  rm -f "$TMP"; echo "ABORT: change touched more than limit.output (original untouched)"; exit 1
fi
cp "$TMP" "$OC"; rm -f "$TMP"
diff <(jq -S . "$OC.bak-$TS") <(jq -S . "$OC") || true
echo "Done. Restart OpenCode to pick it up."
echo "ROLLBACK: cp $OC.bak-$TS $OC"
