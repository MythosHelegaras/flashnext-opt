#!/usr/bin/env bash
# Patch the qwen4exp fork for llama.cpp issue #27792 / PR #27044:
# MMQ mul_mat_id src1_q8_1 tail padding sized from ne11 (==1 for MoE) -> OOB read
# -> "CUDA error: an illegal memory access" at some ubatch sizes with host-resident experts.
# Touches ONLY /opt/llama.cpp-qwen4exp. Never /opt/llama.cpp.
set -euo pipefail

D=/opt/llama.cpp-qwen4exp
F=$D/ggml/src/ggml-cuda/mmq.cu
STAMP=$(date +%Y%m%d-%H%M%S)

[[ -f $F ]] || { echo "ABORT: $F not found"; exit 1; }
[[ -d $D/build/bin ]] || { echo "ABORT: $D/build/bin not found"; exit 1; }

SUDO=""
if [[ ! -w $F || ! -w $D/build ]]; then SUDO=sudo; echo "Tree not writable by $USER -> using sudo for file ops/build"; fi

# 1. Locate the buggy expression (ids branch only) and produce the patched file in /tmp
TMP=$(mktemp)
set +e
python3 - "$F" "$TMP" <<'PY'
import re, sys
src, out = sys.argv[1], sys.argv[2]
s = open(src).read()
pat = re.compile(r'(ne12\s*\*\s*n_expert_used\s*\*\s*ne10_padded\s*\*\s*y_block_size\s*/\s*y_values_per_block\s*\+\s*'
                 r'ggml_cuda_mmq_get_J_max\(\s*src0->type\s*,\s*fallback\s*,\s*cc\s*,\s*)ne11(\s*\))')
fixed = re.compile(r'ggml_cuda_mmq_get_J_max\(\s*src0->type\s*,\s*fallback\s*,\s*cc\s*,\s*ne12\s*\*\s*n_expert_used\s*\)')
n = len(pat.findall(s))
if n == 0:
    if fixed.search(s):
        print("ALREADY PATCHED"); sys.exit(3)
    if 'get_mmq_x_max_host' in s:
        print("ABORT: tree uses the pre-regression padding (get_mmq_x_max_host). Bug #27792 is NOT the cause here.")
    else:
        print("ABORT: buggy expression not found in this form. Inspect mmq.cu around 'nbytes_src1_q8_1' manually.")
    sys.exit(2)
if n != 1:
    print(f"ABORT: expected exactly 1 match, found {n}"); sys.exit(2)
open(out, 'w').write(pat.sub(r'\1ne12*n_expert_used\2', s))
print("MATCH OK: ids-branch padding will use ne12*n_expert_used")
PY
rc=$?
set -e
if [[ $rc -eq 3 ]]; then echo "Nothing to do."; rm -f "$TMP"; exit 0; fi
[[ $rc -eq 0 ]] || { rm -f "$TMP"; exit 1; }

echo "--- diff ---"; diff -u "$F" "$TMP" || true

# 2. Stop llama-swap so nothing spawns flashnext mid-build
systemctl --user stop llama-swap
trap 'systemctl --user start llama-swap; echo "llama-swap restarted"' EXIT

# 3. Backups
$SUDO cp -a "$D/build/bin" "$D/build/bin.bak-$STAMP"
$SUDO cp -a "$F" "$F.orig-$STAMP"
BIN_COPY=""
if [[ -e $D/bin/llama-server ]]; then
  REAL=$(readlink -f "$D/bin/llama-server")
  if [[ $REAL != "$D/build/bin/"* ]]; then
    BIN_COPY=1
    $SUDO cp -a "$D/bin/llama-server" "$D/bin/llama-server.bak-$STAMP"
  fi
fi

# 4. Apply + rebuild llama-server only (build dir already configured)
$SUDO cp "$TMP" "$F"; rm -f "$TMP"
$SUDO cmake --build "$D/build" --config Release -j"$(nproc)" --target llama-server
[[ -n $BIN_COPY ]] && $SUDO cp -a "$D/build/bin/llama-server" "$D/bin/llama-server"

# 5. Sanity
"$D/bin/llama-server" --version 2>&1 | head -3
ldd "$D/bin/llama-server" | grep -E 'ggml-cuda|libllama' || true

echo
echo "PATCHED + REBUILT. Next: bash verify-ub-crash.sh 5 2048 46"
echo "ROLLBACK:"
echo "  $SUDO rm -rf $D/build/bin && $SUDO mv $D/build/bin.bak-$STAMP $D/build/bin && $SUDO cp -a $F.orig-$STAMP $F${BIN_COPY:+ && $SUDO cp -a $D/bin/llama-server.bak-$STAMP $D/bin/llama-server} && systemctl --user restart llama-swap"
