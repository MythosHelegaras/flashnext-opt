#!/usr/bin/env bash
# Change ONLY the -c value inside the flashnext block of llama-swap's config.yaml.
# Usage: bash apply-flashnext-ctx.sh 262144     (backup, block located by key, exact 1-line diff, rollback printed)
set -euo pipefail
CFG=${CFG:-$HOME/.config/llama-swap/config.yaml}
NEW=${1:?usage: apply-flashnext-ctx.sh <ctx>}
[[ $NEW =~ ^[0-9]+$ && $NEW -ge 32768 && $NEW -le 262144 ]] || { echo "ABORT: ctx must be 32768..262144"; exit 1; }
TS=$(date +%Y%m%d-%H%M%S); TMP=$(mktemp)
set +e
python3 - "$CFG" "$TMP" "$NEW" <<'PY'
import re, sys
src, out, new = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(src).read().split("\n")
starts = [i for i,l in enumerate(lines) if re.match(r'^(\s+)["\']?flashnext["\']?\s*:\s*$', l)]
if len(starts) != 1: sys.exit(f"ABORT: expected 1 flashnext key, found {len(starts)}")
s = starts[0]; ind = len(lines[s]) - len(lines[s].lstrip())
e = s + 1
while e < len(lines) and (not lines[e].strip() or len(lines[e]) - len(lines[e].lstrip()) > ind): e += 1
hits = [i for i in range(s, e) if re.search(r'(?<![\w-])-c\s+\d+', lines[i])]
if len(hits) != 1: sys.exit(f"ABORT: expected 1 '-c N' in flashnext block (lines {s+1}-{e}), found {len(hits)}")
i = hits[0]; old = lines[i]
lines[i] = re.sub(r'((?<![\w-])-c\s+)\d+', r'\g<1>' + new, old)
if lines[i] == old: print("NOOP"); sys.exit(3)
open(out, "w").write("\n".join(lines))
print(f"flashnext block lines {s+1}-{e}\n  - {old.strip()}\n  + {lines[i].strip()}")
PY
rc=$?; set -e; [[ $rc -eq 3 ]] && { echo "Already set."; rm -f "$TMP"; exit 0; }
[[ $rc -eq 0 ]] || { rm -f "$TMP"; exit 1; }
python3 -c 'import yaml,sys; yaml.safe_load(open(sys.argv[1]))' "$TMP" 2>/dev/null && echo "  YAML parses" || echo "  (pyyaml not available — YAML parse not checked)"
N=$(diff "$CFG" "$TMP" | grep -c '^[<>]' || true)
[[ $N -eq 2 ]] || { rm -f "$TMP"; echo "ABORT: diff is not exactly one line ($N)"; exit 1; }
cp -a "$CFG" "$CFG.bak-$TS"; cp "$TMP" "$CFG"; rm -f "$TMP"
echo "applied. Restart: systemctl --user restart llama-swap"
echo "rollback: cp $CFG.bak-$TS $CFG && systemctl --user restart llama-swap"
