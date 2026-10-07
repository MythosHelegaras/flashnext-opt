#!/usr/bin/env bash
# apply-flashnext-v4.sh — v3's script extended for the v4 engine decision.
#
#   usage: [FLASHNEXT_SAMPLING="<line>"] bash apply-flashnext-v4.sh <F|M> "<tuning>" [<mtp-n-max>]
#     bash apply-flashnext-v4.sh M "-ncmoe 46 -t 16 -b 2048 -ub 2048"        # mainline, same flags
#     bash apply-flashnext-v4.sh M "-ncmoe 47 -t 16 -b 2048 -ub 2048" 2      # mainline + MTP n-max 2
#     bash apply-flashnext-v4.sh F "-ncmoe 46 -t 16 -b 2048 -ub 2048"        # back to the fork
#
#   <F|M>        F = /opt/llama.cpp-qwen4exp/bin/llama-server (fork)
#                M = /opt/llama.cpp-flashnext/build/bin/llama-server (mainline abeada335)
#   <tuning>     replaces the single "-ncmoe ..." line of the flashnext block
#   <mtp-n-max>  1|2|3: add (or replace) ONE line, placed right after the "-c ..." line:
#                  --spec-type draft-mtp --model-draft <head> --spec-draft-ngl 999
#                  -ctkd q8_0 -ctvd q8_0 --spec-draft-cpu-moe --spec-draft-n-max <k>
#                omitted: any existing "--spec-type" line is REMOVED (MTP off).
#                MTP requires M; the head must exist with the verified size and sha256.
#   FLASHNEXT_SAMPLING  (as v3) replaces the single "--temp ..." line; unset = untouched.
#
# Guarantees (v1–v3, unchanged): timestamped backup first; the flashnext block is located BY KEY,
# never by line number; only the binary line, the -ncmoe line, the MTP line (and, if asked, the
# --temp line) may change; YAML must parse; every other model block and top-level key must be
# identical; ttl 1800, LLAMA_ATTN_ROT_DISABLE=1 and all mandatory + sampling flags must survive;
# the textual diff must be exactly the planned set of lines. Any failed check restores the backup.
# A run that would change nothing exits 0 without writing a backup.
# FLASHNEXT_CFG overrides the config path (used only to self-test on a copy).
set -euo pipefail

CFG="${FLASHNEXT_CFG:-$HOME/.config/llama-swap/config.yaml}"
ENGINE="${1:?need engine F or M}"
NEW_TUNE="${2:?need the replacement tuning string, e.g. \"-ncmoe 46 -t 16 -b 2048 -ub 2048\"}"
MTP_K="${3:-}"
NEW_SAMP="${FLASHNEXT_SAMPLING:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="$CFG.bak-$STAMP"

BIN_F=/opt/llama.cpp-qwen4exp/bin/llama-server
BIN_M=/opt/llama.cpp-flashnext/build/bin/llama-server
MTP_HEAD=/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf
MTP_SIZE=2786204800
MTP_SHA=8087dbb39fc73f79ac069b1debe4069a44b73ada900c8bd761569d43a5a90231

[[ -f $CFG ]] || { echo "no config at $CFG" >&2; exit 1; }
case $ENGINE in
  F) BIN=$BIN_F ;;
  M) BIN=$BIN_M ;;
  *) echo "engine must be F or M" >&2; exit 1 ;;
esac
[[ -x $BIN ]] || { echo "binary not executable: $BIN" >&2; exit 1; }
ver=$(LLAMA_ATTN_ROT_DISABLE=1 "$BIN" --version 2>&1 | grep -m1 '^version:' || true)
[[ -n $ver ]] || { echo "binary does not run: $BIN" >&2; exit 1; }
echo "binary: $BIN ($ver)"

MTP_LINE=""
if [[ -n $MTP_K ]]; then
  [[ $MTP_K =~ ^[123]$ ]] || { echo "mtp-n-max must be 1, 2 or 3" >&2; exit 1; }
  [[ $ENGINE == M ]] || { echo "MTP needs engine M (the fork has no draft-mtp)" >&2; exit 1; }
  [[ -f $MTP_HEAD ]] || { echo "MTP head missing: $MTP_HEAD" >&2; exit 1; }
  sz=$(stat -c %s "$MTP_HEAD")
  [[ $sz == "$MTP_SIZE" ]] || { echo "MTP head size $sz != $MTP_SIZE" >&2; exit 1; }
  echo "checking MTP head sha256 ..."
  sha=$(sha256sum "$MTP_HEAD" | cut -d' ' -f1)
  [[ $sha == "$MTP_SHA" ]] || { echo "MTP head sha256 $sha != $MTP_SHA" >&2; exit 1; }
  echo "MTP head: size and sha256 OK"
  MTP_LINE="--spec-type draft-mtp --model-draft $MTP_HEAD --spec-draft-ngl 999 -ctkd q8_0 -ctvd q8_0 --spec-draft-cpu-moe --spec-draft-n-max $MTP_K"
fi

# plan + write a candidate into a temp file first; the real config is touched only if it differs
TMP=$(mktemp "${CFG}.v4tmp.XXXXXX")
trap 'rm -f "$TMP"' EXIT
NEW_TUNE="$NEW_TUNE" NEW_SAMP="$NEW_SAMP" BIN="$BIN" MTP_LINE="$MTP_LINE" SRC="$CFG" OUT="$TMP" \
python3 - <<'PY'
import os, re, sys
src, out = os.environ["SRC"], os.environ["OUT"]
tune, binp, mtp = os.environ["NEW_TUNE"].strip(), os.environ["BIN"], os.environ["MTP_LINE"].strip()
samp = " ".join(os.environ["NEW_SAMP"].split())
lines = open(src).read().splitlines(keepends=True)

start = next((i for i, l in enumerate(lines) if re.match(r'^  "?flashnext"?\s*:\s*$', l)), None)
if start is None: sys.exit("could not find the flashnext key")
end = next((j for j in range(start + 1, len(lines))
            if re.match(r'^  (?:"[^"]+"|[A-Za-z0-9_-]+)\s*:', lines[j])), len(lines))
print(f"  flashnext block: lines {start+1}-{end} (located by key)")

def one(pattern, what, allow_zero=False):
    hits = [k for k in range(start, end) if re.match(pattern, lines[k])]
    if len(hits) > 1 or (not hits and not allow_zero):
        sys.exit(f"expected exactly one {what} line in flashnext, found {len(hits)}")
    return hits[0] if hits else None

def indent_of(k): return re.match(r'^(\s*)', lines[k]).group(1)
plan = []
def put(k, text):
    new = f"{indent_of(k)}{text}\n"
    if lines[k] != new:
        plan.append(f"  -  {lines[k].strip()}\n  +  {text}"); lines[k] = new

# binary line: "<path>/llama-server --port ${PORT}"
kb = one(r'^\s*/\S+/llama-server\s+--port\s+\$\{PORT\}\s*$', "llama-server binary")
put(kb, f"{binp} --port ${{PORT}}")
if not re.match(r'^-ncmoe \d+( |$)', tune): sys.exit("tuning string must start with -ncmoe <n>")
put(one(r'^\s*-ncmoe\s', "-ncmoe"), tune)
if samp:
    if not re.match(r'^--temp [0-9.]+ ', samp) or "--top-p 0.95" not in samp or "--top-k 20" not in samp:
        sys.exit("sampling line must start with --temp <x> and keep --top-p 0.95 --top-k 20")
    put(one(r'^\s*--temp\s', "--temp"), samp)
km = one(r'^\s*--spec-type\s', "--spec-type", allow_zero=True)
if mtp and km is not None:
    put(km, mtp)
elif mtp:
    kc = one(r'^\s*-c\s+\d+', "-c <ctx>")
    lines.insert(kc + 1, f"{indent_of(kc)}{mtp}\n"); plan.append(f"  +  {mtp}   (new line after -c)")
elif km is not None:
    plan.append(f"  -  {lines[km].strip()}   (MTP line removed)"); del lines[km]
open(out, "w").write("".join(lines))
print("\n".join(plan) if plan else "  (no change)")
open(out + ".n", "w").write(str(len(plan)))
PY
NPLAN=$(cat "$TMP.n"); rm -f "$TMP.n"
if [[ $NPLAN == 0 ]]; then echo "config already matches — nothing written"; exit 0; fi

cp -p "$CFG" "$BAK"
echo "backup: $BAK"
restore() { cp -p "$BAK" "$CFG"; echo "FAILED — original config restored from $BAK" >&2; }
trap 'rm -f "$TMP"; restore' ERR
cat "$TMP" > "$CFG"

NEW_TUNE="$NEW_TUNE" NEW_SAMP="$NEW_SAMP" BIN="$BIN" MTP_LINE="$MTP_LINE" NPLAN="$NPLAN" \
BAK="$BAK" CFG="$CFG" BIN_F="$BIN_F" BIN_M="$BIN_M" python3 - <<'PY'
import difflib, os, re, sys, yaml
cfg, bak = os.environ["CFG"], os.environ["BAK"]
tune, binp, mtp = os.environ["NEW_TUNE"].strip(), os.environ["BIN"], os.environ["MTP_LINE"].strip()
samp = " ".join(os.environ["NEW_SAMP"].split()); nplan = int(os.environ["NPLAN"])

a = yaml.safe_load(open(bak)); b = yaml.safe_load(open(cfg))
if b is None: sys.exit("new config does not parse as YAML")
ma, mb = a.get("models", {}), b.get("models", {})
if set(ma) != set(mb): sys.exit("model key set changed")
for name in ma:
    if name != "flashnext" and ma[name] != mb[name]: sys.exit(f"block '{name}' changed — refusing")
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
must = ["/usr/bin/env LLAMA_ATTN_ROT_DISABLE=1", f"{binp} --port ${{PORT}}",
        "-ot per_layer_token_embd=CPU", "-ngl 999", "-fa on", "-np 1", "--jinja",
        "--top-p 0.95", "--top-k 20", samp or "--temp", "-c 131072",
        "--cache-type-k q8_0", "--cache-type-v q8_0", tune] + ([mtp] if mtp else [])
missing = [m for m in must if m not in cmd]
if missing: sys.exit(f"mandatory/sampling flags missing after edit: {missing}")
if re.search(r"-fa(?!\s+on)", cmd): sys.exit("-fa must be 'on', never bare")
if len(re.findall(r"(?:^|\s)-m\s", cmd)) != 1: sys.exit("expected exactly one -m in cmd")
if len(re.findall(r"llama-server", cmd)) != 1: sys.exit("expected exactly one llama-server in cmd")
other = os.environ["BIN_F"] if binp == os.environ["BIN_M"] else os.environ["BIN_M"]
if other in cmd: sys.exit("both binaries present in cmd")
if not mtp and "--spec-type" in cmd: sys.exit("MTP flags still present although MTP is off")
print("  ttl 1800 kept; env var, binary, all mandatory + sampling flags present")
print(f"  new cmd: {cmd}")

da = open(bak).read().splitlines(); db = open(cfg).read().splitlines()
changed = 0
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, da, db, autojunk=False).get_opcodes():
    if tag == "equal": continue
    changed += max(i2 - i1, j2 - j1)
    for l in db[j1:j2]:
        s = l.strip()
        if not (s.startswith(binp) or s.startswith("-ncmoe ") or s.startswith("--spec-type ")
                or (samp and s.startswith("--temp "))):
            sys.exit(f"unexpected changed line: {s!r}")
if changed != nplan: sys.exit(f"expected exactly {nplan} changed line(s), got {changed}")
print(f"  diff is exactly {nplan} line(s) — every other byte of the file is unchanged")
PY

trap - ERR
echo
echo "applied. Restart to pick it up:  systemctl --user restart llama-swap"
echo "rollback with:"
echo "  cp $BAK $CFG && systemctl --user restart llama-swap"
