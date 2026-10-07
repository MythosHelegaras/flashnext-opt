#!/usr/bin/env bash
# apply-flashnext-v2.sh — swap the flashnext tuning line and, optionally, its model file.
#
#   usage: bash apply-flashnext-v2.sh "<tuning>" [<model-path>]
#     bash apply-flashnext-v2.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048"
#     bash apply-flashnext-v2.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048" \
#          /mnt/ai/llm/models/qwen3.8-flash-next-gsq/IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf
#
# Same guarantees as apply-flashnext.sh (v1): timestamped backup first; the flashnext block is
# located BY KEY (never by line number); only the -ncmoe line (and, if a model path is given,
# the single "-m" line) are rewritten; YAML must parse; every other model block and top-level
# key must be identical; ttl 1800 and all mandatory + sampling flags must survive; the textual
# diff must be exactly the expected 1 or 2 lines. Any failed check restores the backup.
# The model path is checked before anything is written: file exists, every shard of a split
# GGUF is present and non-empty, and no *.incomplete file sits next to it.
# FLASHNEXT_CFG overrides the config path (used only to self-test on a copy).
set -euo pipefail

CFG="${FLASHNEXT_CFG:-$HOME/.config/llama-swap/config.yaml}"
NEW_TUNE="${1:?need the replacement tuning string, e.g. \"-ncmoe 46 -t 16 -b 2048 -ub 2048\"}"
NEW_MODEL="${2:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="$CFG.bak-$STAMP"

[[ -f $CFG ]] || { echo "no config at $CFG" >&2; exit 1; }

if [[ -n $NEW_MODEL ]]; then
  [[ $NEW_MODEL == /* ]] || { echo "model path must be absolute" >&2; exit 1; }
  [[ -s $NEW_MODEL ]] || { echo "model file missing or empty: $NEW_MODEL" >&2; exit 1; }
  dir=$(dirname "$NEW_MODEL")
  if compgen -G "$dir/*.incomplete" >/dev/null; then echo "incomplete download in $dir" >&2; exit 1; fi
  if [[ $NEW_MODEL =~ ^(.*)-00001-of-([0-9]{5})\.gguf$ ]]; then
    stem=${BASH_REMATCH[1]}; n=$((10#${BASH_REMATCH[2]}))
    for i in $(seq 1 "$n"); do
      shard=$(printf '%s-%05d-of-%05d.gguf' "$stem" "$i" "$n")
      [[ -s $shard ]] || { echo "missing shard: $shard" >&2; exit 1; }
    done
    echo "model: $n/$n shards present"
  fi
fi

cp -p "$CFG" "$BAK"
echo "backup: $BAK"

restore() { cp -p "$BAK" "$CFG"; echo "FAILED — original config restored from $BAK" >&2; }
trap restore ERR

NEW_TUNE="$NEW_TUNE" NEW_MODEL="$NEW_MODEL" BAK="$BAK" CFG="$CFG" python3 - <<'PY'
import os, re, sys, yaml

cfg, bak = os.environ["CFG"], os.environ["BAK"]
tune, model = os.environ["NEW_TUNE"].strip(), os.environ["NEW_MODEL"].strip()
lines = open(bak).read().splitlines(keepends=True)

# --- locate the flashnext block BY KEY, and its end as the next key at the same indent ---
start = None
for i, l in enumerate(lines):
    if re.match(r'^  "?flashnext"?\s*:\s*$', l): start = i; break
if start is None: sys.exit("could not find the flashnext key")
end = len(lines)
for j in range(start + 1, len(lines)):
    if re.match(r'^  (?:"[^"]+"|[A-Za-z0-9_-]+)\s*:', lines[j]): end = j; break
print(f"  flashnext block: lines {start+1}-{end} (located by key)")

def rewrite(pattern, new_text, what):
    hits = [k for k in range(start, end) if re.match(pattern, lines[k])]
    if len(hits) != 1: sys.exit(f"expected exactly one {what} line in flashnext, found {len(hits)}")
    k = hits[0]
    indent = re.match(r'^(\s*)', lines[k]).group(1)
    print(f"  -  {lines[k].strip()}")
    lines[k] = f"{indent}{new_text}\n"
    print(f"  +  {new_text}")

if not re.match(r'^-ncmoe \d+( |$)', tune): sys.exit("tuning string must start with -ncmoe <n>")
rewrite(r'^\s*-ncmoe\s', tune, "-ncmoe")
expected_changes = 1
if model:
    rewrite(r'^\s*-m\s+\S+\.gguf\s*$', f"-m {model}", "-m <model>")
    expected_changes = 2
open(cfg, "w").write("".join(lines))

# --- validation ---
a = yaml.safe_load(open(bak)); b = yaml.safe_load(open(cfg))
if b is None: sys.exit("new config does not parse as YAML")
ma, mb = a.get("models", {}), b.get("models", {})
if set(ma) != set(mb): sys.exit("model key set changed")
for name in ma:
    if name == "flashnext": continue
    if ma[name] != mb[name]: sys.exit(f"block '{name}' changed — refusing")
print(f"  YAML parses; {len(ma)-1} other model blocks identical")
for key in [k for k in a if k != "models"]:
    if a[key] != b[key]: sys.exit(f"top-level '{key}' changed — refusing")
print("  all non-models top-level keys identical")

fa, fb = ma["flashnext"], mb["flashnext"]
if set(fa) != set(fb): sys.exit("flashnext keys changed")
for key in fa:
    if key != "cmd" and fa[key] != fb[key]: sys.exit(f"flashnext '{key}' changed")
if fb.get("ttl") != 1800: sys.exit("ttl is not 1800")
cmd = " ".join(fb["cmd"].split())
must = ["LLAMA_ATTN_ROT_DISABLE=1", "-ot per_layer_token_embd=CPU", "-ngl 999",
        "-fa on", "-np 1", "--jinja", "--temp 0.3", "--top-p 0.95", "--top-k 20",
        "-c 131072", "--cache-type-k q8_0", "--cache-type-v q8_0", tune]
if model: must.append(f"-m {model}")
missing = [m for m in must if m not in cmd]
if missing: sys.exit(f"mandatory/sampling flags missing after edit: {missing}")
if re.search(r"-fa(?!\s+on)", cmd): sys.exit("-fa must be 'on', never bare")
if len(re.findall(r"(?:^|\s)-m\s", cmd)) != 1: sys.exit("expected exactly one -m in cmd")
print("  ttl 1800 kept; all mandatory + sampling flags present")
print(f"  new cmd: {cmd}")

# prove the ONLY textual differences are the expected lines
da = open(bak).read().splitlines(); db = open(cfg).read().splitlines()
diff = [(x, y) for x, y in zip(da, db) if x != y]
if len(da) != len(db) or len(diff) != expected_changes:
    sys.exit(f"expected exactly {expected_changes} changed line(s), got {len(diff)}")
print(f"  diff is exactly {expected_changes} line(s) — every other byte of the file is unchanged")
PY

trap - ERR
echo
echo "applied. Restart to pick it up:  systemctl --user restart llama-swap"
echo "rollback with:"
echo "  cp $BAK $CFG && systemctl --user restart llama-swap"
