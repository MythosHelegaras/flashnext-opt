#!/usr/bin/env bash
# Step 1: build mainline llama.cpp into a THIRD, separate tree for flashnext evaluation.
# Never touches /opt/llama.cpp (production fim/forge/rag) or /opt/llama.cpp-qwen4exp (current flashnext).
# Usage: bash build-mainline-flashnext.sh [git-ref=master]
set -euo pipefail
REF=${1:-master}
D=/opt/llama.cpp-flashnext
B=$D/build
LOG=$HOME/flashnext-opt/logs/mainline-build-$(date +%Y%m%d-%H%M%S).log
mkdir -p "$(dirname "$LOG")"

for p in /opt/llama.cpp /opt/llama.cpp-qwen4exp; do
  [[ $D != "$p" ]] || { echo "ABORT: target collides with $p"; exit 1; }
done

echo "== toolchain =="; ls /usr/bin/g++-* 2>/dev/null || true; pacman -Q gcc cuda 2>/dev/null || true
/opt/cuda/bin/nvcc --version | tail -1; nvidia-smi --query-gpu=driver_version --format=csv,noheader

# 1. Tree (one-time sudo only to create the dir and hand it to you)
if [[ ! -d $D ]]; then
  sudo mkdir -p "$D" && sudo chown "$USER:$USER" "$D"; sudo -k
  git clone https://github.com/ggml-org/llama.cpp.git "$D"
fi
[[ -w $D ]] || { echo "ABORT: $D not writable by $USER"; exit 1; }
git -C "$D" fetch --quiet origin
git -C "$D" checkout --quiet "$REF"
[[ $REF == master ]] && git -C "$D" pull --quiet --ff-only origin master
SHA=$(git -C "$D" rev-parse --short=10 HEAD)
echo "== mainline at $SHA ($(git -C "$D" log -1 --format=%cd --date=short)) =="

# 2. Required upstream changes must be present (short SHAs from research; verified here)
need() { # name sha
  if git -C "$D" cat-file -e "$2^{commit}" 2>/dev/null; then
    git -C "$D" merge-base --is-ancestor "$2" HEAD && echo "  OK   $1 ($2)" || { echo "  MISSING $1 ($2) not in HEAD"; return 1; }
  else
    echo "  ?    $1: commit $2 not found — check the PR manually"; return 2
  fi
}
rc=0
need "qwen4exp arch (PR 27742)"      6c84c7d || rc=1
need "MTP draft (PR 29761)"          c061df1 || rc=1
need "MMQ padding fix (PR 29941)"    dd26678 || rc=1
if [[ $rc -ne 0 ]]; then
  echo "Verifying by grep instead:"
  grep -rqs 'qwen4exp\|QWEN4EXP' "$D/src" && echo "  grep: qwen4exp present" || echo "  grep: qwen4exp NOT found"
  grep -Eqs 'ggml_cuda_mmq_get_J_max\([^)]*ne12\s*\*\s*n_expert_used' "$D/ggml/src/ggml-cuda/mmq.cu" \
    && echo "  grep: MMQ padding fix present" || echo "  grep: MMQ padding fix NOT found (do not use ub>512 until it is)"
fi

# 3. Configure + build (same arch/flags as the fork)
cmake -S "$D" -B "$B" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_BUILD_TYPE=Release 2>&1 | tee "$LOG" | tail -3
cmake --build "$B" --config Release -j"$(nproc)" --target llama-server 2>&1 | tee -a "$LOG" | tail -3

# 4. What this build offers that matters for flashnext
BIN=$B/bin/llama-server
"$BIN" --version 2>&1 | head -2
echo "== flags of interest =="
"$BIN" --help 2>&1 | grep -E -- '--spec-type|draft-mtp|--fit|--lazy|--load-mode|--reasoning-budget|--reasoning-effort|--reasoning-preserve|--presence-penalty|--n-cpu-moe|-ncmoe' \
  | sed 's/^/  /' || true
echo
echo "BUILT: $BIN  (log: $LOG)"
echo "Nothing in llama-swap points here. Production is unchanged."
