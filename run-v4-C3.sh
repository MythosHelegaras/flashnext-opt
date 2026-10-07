#!/usr/bin/env bash
# v4 C3: gates 1-4 on the best MTP config (n-max 2 by session_s, n47, head experts on CPU).
cd ~/flashnext-opt
while pgrep -f 'harness4.py' >/dev/null; do sleep 15; done
HEAD=/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf
SPEC="-ncmoe 47 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0 --spec-type draft-mtp --model-draft $HEAD --spec-draft-ngl 999 -ctkd q8_0 -ctvd q8_0 --spec-draft-cpu-moe --metrics --spec-draft-n-max 2"
python3 harness4.py bench  --engine M --label v4-C3-n47-k2-full --spec "$SPEC" --tests d0 --reps 1 --full
python3 harness4.py cold   --engine M --label v4-C3-n47-k2-coldset --spec "$SPEC"
python3 harness4.py task02 --engine M --label v4-C3-n47-k2-task02 --spec "$SPEC"
echo "PHASE C3 DONE $(date)"
