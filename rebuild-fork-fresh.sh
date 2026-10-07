#!/usr/bin/env bash
# Fresh reconfigure + rebuild of the qwen4exp fork after a toolchain change
# (link failed: /usr/bin/g++-15 gone). Same build dir, same options, patched mmq.cu.
# Touches ONLY /opt/llama.cpp-qwen4exp. Never /opt/llama.cpp.
set -euo pipefail

D=/opt/llama.cpp-qwen4exp
B=$D/build
STAMP=$(date +%Y%m%d-%H%M%S)
SAVE=$HOME/flashnext-opt/build-backups
mkdir -p "$SAVE"

echo "== toolchain now =="
ls /usr/bin/g++-* 2>/dev/null || echo "(no versioned g++)"
pacman -Q gcc cuda 2>/dev/null || true
/opt/cuda/bin/nvcc --version | tail -2
echo "NVCC_CCBIN=${NVCC_CCBIN:-unset}"
echo

# 0. Preconditions
grep -Eq 'ggml_cuda_mmq_get_J_max\(\s*src0->type\s*,\s*fallback\s*,\s*cc\s*,\s*ne12\s*\*\s*n_expert_used\s*\)' \
  "$D/ggml/src/ggml-cuda/mmq.cu" || { echo "ABORT: mmq.cu patch (#27792) not present. Run patch-mmq-ubfix.sh first."; exit 1; }
[[ -f $B/CMakeCache.txt ]] || { echo "ABORT: $B/CMakeCache.txt missing"; exit 1; }

# 1. Backups: cache always; bin only if no earlier backup exists
cp -a "$B/CMakeCache.txt" "$SAVE/CMakeCache.txt.$STAMP"
if ls -d "$B"/bin.bak-* >/dev/null 2>&1; then
  BINBAK=$(ls -dt "$B"/bin.bak-* | head -1)
  echo "Using existing bin backup: $BINBAK"
else
  BINBAK=$B/bin.bak-$STAMP
  cp -a "$B/bin" "$BINBAK"
  echo "Created bin backup: $BINBAK"
fi
BIN_IS_COPY=""
if [[ -e $D/bin/llama-server && $(readlink -f "$D/bin/llama-server") != "$B/bin/"* ]]; then
  BIN_IS_COPY=1
  cp -a "$D/bin/llama-server" "$SAVE/llama-server.$STAMP"
fi

# 2. Carry over every GGML_*/LLAMA_* option + build type + arch from the old cache
mapfile -t OPTS < <(grep -E '^(GGML|LLAMA)_[A-Za-z0-9_]+:(BOOL|STRING)=' "$B/CMakeCache.txt" \
                    | sed -E 's/^([A-Za-z0-9_]+):[A-Z]+=(.*)$/-D\1=\2/')
BT=$(grep -E '^CMAKE_BUILD_TYPE:' "$B/CMakeCache.txt" | cut -d= -f2-)
ARCH=$(grep -E '^CMAKE_CUDA_ARCHITECTURES:' "$B/CMakeCache.txt" | cut -d= -f2-)
OPTS+=("-DCMAKE_BUILD_TYPE=${BT:-Release}" "-DCMAKE_CUDA_ARCHITECTURES=${ARCH:-120}")
echo "Carrying ${#OPTS[@]} options (e.g. $(printf '%s ' "${OPTS[@]}" | grep -oE -- '-DGGML_CUDA=[^ ]+|-DLLAMA_CURL=[^ ]+|-DCMAKE_CUDA_ARCHITECTURES=[^ ]+' | tr '\n' ' '))"

# 3. Stop llama-swap for the duration
systemctl --user stop llama-swap
trap 'systemctl --user start llama-swap; echo "llama-swap restarted"' EXIT

# 4. Fresh configure in place
cmake --fresh -S "$D" -B "$B" "${OPTS[@]}"

LL=$(grep -h 'CMAKE_CUDA_HOST_LINK_LAUNCHER' "$B"/CMakeFiles/*/CMakeCUDACompiler.cmake 2>/dev/null | grep -oE '"[^"]+"' | tr -d '"' | head -1)
echo "Detected CUDA link launcher: ${LL:-<none>}"
if [[ -n $LL && ! -x $LL ]]; then echo "ABORT: detected link launcher $LL does not exist"; exit 1; fi

# 5. Build
cmake --build "$B" --config Release -j"$(nproc)" --target llama-server
[[ -n $BIN_IS_COPY ]] && cp -a "$B/bin/llama-server" "$D/bin/llama-server"

# 6. Sanity
"$D/bin/llama-server" --version 2>&1 | head -3
ldd "$D/bin/llama-server" | grep -E 'ggml-cuda|libllama|cudart' || true
if ldd "$D/bin/llama-server" | grep -q 'not found'; then echo "WARNING: unresolved libraries above"; fi

echo
echo "REBUILT. Next: bash verify-ub-crash.sh 5 2048 46"
echo "ROLLBACK (restores the 8-Sep binaries):"
echo "  rm -rf $B/bin && cp -a $BINBAK $B/bin${BIN_IS_COPY:+ && cp -a $SAVE/llama-server.$STAMP $D/bin/llama-server} && systemctl --user restart llama-swap"
