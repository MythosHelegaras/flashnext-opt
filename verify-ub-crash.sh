#!/usr/bin/env bash
# Cold-start reproducer for the ub>512 illegal-memory-access crash.
# Each rep: fresh llama-server, prompt_B as the FIRST request (no warm-up -> no pool masking).
# Usage: bash verify-ub-crash.sh [reps=5] [ub=2048] [ncmoe=46]
set -uo pipefail
N=${1:-5}; UB=${2:-2048}; NCMOE=${3:-46}
B=$(( UB > 2048 ? UB : 2048 ))
BIN=/opt/llama.cpp-qwen4exp/bin/llama-server
MODEL=/mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
PROMPT=/mnt/ai/evals/harness/prompt_B.txt
PORT=9997
LOGDIR=$HOME/flashnext-opt/logs/ubfix-$(date +%Y%m%d-%H%M%S)
mkdir -p "$LOGDIR"

[[ -f $PROMPT ]] || { echo "ABORT: $PROMPT missing"; exit 1; }
command -v jq >/dev/null || { echo "ABORT: jq missing"; exit 1; }

systemctl --user stop llama-swap
trap 'systemctl --user start llama-swap; echo "llama-swap restarted"' EXIT
sleep 3
if nvidia-smi --query-compute-apps=name --format=csv,noheader | grep -q llama-server; then
  echo "ABORT: a llama-server still holds the GPU"; exit 1
fi

PAYLOAD=$(jq -Rs '{messages:[{role:"user",content:.}],max_tokens:1500,temperature:0.3}' "$PROMPT")
ok=0; bad=0
for i in $(seq 1 "$N"); do
  LOG=$LOGDIR/rep$i.server.log
  LLAMA_ATTN_ROT_DISABLE=1 "$BIN" -m "$MODEL" --host 127.0.0.1 --port $PORT \
    -ngl 999 -ot per_layer_token_embd=CPU -fa on -np 1 --jinja \
    -ncmoe "$NCMOE" -t 16 -b "$B" -ub "$UB" -c 131072 \
    --cache-type-k q8_0 --cache-type-v q8_0 >"$LOG" 2>&1 &
  PID=$!
  for _ in $(seq 1 240); do
    curl -sf http://127.0.0.1:$PORT/health >/dev/null && break
    kill -0 $PID 2>/dev/null || break
    sleep 1
  done
  RESP=$(curl -s -m 900 -H 'Content-Type: application/json' -d "$PAYLOAD" http://127.0.0.1:$PORT/v1/chat/completions)
  sleep 2
  PT=$(echo "$RESP" | jq -r '.usage.prompt_tokens // "?"' 2>/dev/null)
  if kill -0 $PID 2>/dev/null && ! grep -q 'illegal memory access' "$LOG" && echo "$RESP" | jq -e '.choices[0]' >/dev/null 2>&1; then
    ok=$((ok+1)); echo "rep $i: OK    (prompt_tokens=$PT)"
  else
    bad=$((bad+1)); echo "rep $i: CRASH ($(grep -m1 -o 'CUDA error.*' "$LOG" || echo 'server died / no response'))"
  fi
  kill $PID 2>/dev/null; wait $PID 2>/dev/null
  sleep 4
done
echo "== ub=$UB ncmoe=$NCMOE: $ok OK / $bad CRASH  (logs: $LOGDIR)"
