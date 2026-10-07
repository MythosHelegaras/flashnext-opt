#!/usr/bin/env bash
# apply-flashnext.sh — swap ONLY the flashnext tuning line in llama-swap's config.
#
#   usage: bash apply-flashnext.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048"
#
# Guarantees: timestamped backup first; the flashnext block is located BY KEY (never by
# line number); only the line carrying -ncmoe is rewritten, so every mandatory flag
# (LLAMA_ATTN_ROT_DISABLE, -ot per_layer_token_embd=CPU, -ngl 999, -fa on, -np 1, --jinja),
# the context, the KV types, the sampling flags and ttl: 1800 are untouched; the result is
# validated by parsing the YAML and proving every other model block is identical.
set -euo pipefail

CFG="$HOME/.config/llama-swap/config.yaml"
NEW_TUNE="${1:?need the replacement tuning string, e.g. \"-ncmoe 46 -t 16 -b 2048 -ub 2048\"}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="$CFG.bak-$STAMP"

[[ -f $CFG ]] || { echo "no config at $CFG" >&2; exit 1; }
cp -p "$CFG" "$BAK"
echo "backup: $BAK"

NEW_TUNE="$NEW_TUNE" BAK="$BAK" CFG="$CFG" python3 - <<'PY'
import os, re, sys, yaml

cfg, bak, tune = os.environ["CFG"], os.environ["BAK"], os.environ["NEW_TUNE"].strip()
lines = open(bak).read().splitlines(keepends=True)

# --- locate the flashnext block BY KEY, and its end as the next key at the same indent ---
start = None
for i, l in enumerate(lines):
    if re.match(r'^  "?flashnext"?\s*:\s*$', l): start = i; break
if start is None: sys.exit("could not find the flashnext key")
end = len(lines)
for j in range(start + 1, len(lines)):
    if re.match(r'^  (?:"[^"]+"|[A-Za-z0-9_-]+)\s*:', lines[j]): end = j; break

# --- inside that block only, rewrite the single line carrying -ncmoe ---
hits = [k for k in range(start, end) if re.match(r'^\s*-ncmoe\s', lines[k])]
if len(hits) != 1: sys.exit(f"expected exactly one -ncmoe line in flashnext, found {len(hits)}")
k = hits[0]
indent = re.match(r'^(\s*)', lines[k]).group(1)
old = lines[k].strip()
lines[k] = f"{indent}{tune}\n"
print(f"  flashnext block: lines {start+1}-{end} (located by key)")
print(f"  -  {old}")
print(f"  +  {tune}")
open(cfg, "w").write("".join(lines))

# --- validation ---
a = yaml.safe_load(open(bak)); b = yaml.safe_load(open(cfg))
if b is None: sys.exit("new config does not parse as YAML")
ma, mb = a.get("models", {}), b.get("models", {})
if set(ma) != set(mb): sys.exit("model key set changed")
for name in ma:
    if name == "flashnext": continue
    if ma[name] != mb[name]: sys.exit(f"block '{name}' changed — refusing")
print(f"  YAML parses; {len(ma)-1} other model blocks byte-identical")
for key in [k for k in a if k != "models"]:
    if a[key] != b[key]: sys.exit(f"top-level '{key}' changed — refusing")
print("  all non-models top-level keys identical")

fa, fb = ma["flashnext"], mb["flashnext"]
if fa.get("ttl") != fb.get("ttl") or fb.get("ttl") != 1800: sys.exit("ttl changed or not 1800")
cmd = " ".join(fb["cmd"].split())
must = ["LLAMA_ATTN_ROT_DISABLE=1", "-ot per_layer_token_embd=CPU", "-ngl 999",
        "-fa on", "-np 1", "--jinja", "--temp 0.3", "--top-p 0.95", "--top-k 20",
        "-c 131072", "--cache-type-k q8_0", "--cache-type-v q8_0"]
missing = [m for m in must if m not in cmd]
if missing: sys.exit(f"mandatory/sampling flags missing after edit: {missing}")
if "-fa on" not in cmd or re.search(r"-fa(?!\s+on)", cmd): sys.exit("-fa must be 'on', never bare")
print("  ttl 1800 kept; all mandatory + sampling flags present")
print(f"  new cmd: {cmd}")

# prove the ONLY textual difference is that one line
da = open(bak).read().splitlines(); db = open(cfg).read().splitlines()
diff = [(x, y) for x, y in zip(da, db) if x != y]
if len(da) != len(db) or len(diff) != 1: sys.exit(f"expected exactly 1 changed line, got {len(diff)}")
print("  diff is exactly one line — every other byte of the file is unchanged")
PY

echo
echo "applied. rollback with:"
echo "  cp $BAK $CFG && systemctl --user restart llama-swap"
