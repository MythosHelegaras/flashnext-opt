#!/usr/bin/env bash
# v4 C1: MTP launch on M. Load + 500-tok probe + D0 x3 at n46, draft experts on GPU vs on CPU.
cd ~/flashnext-opt
while pgrep -f 'harness4.py' >/dev/null; do sleep 15; done
HEAD=/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf
BASE="-t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
MTP="--spec-type draft-mtp --model-draft $HEAD --spec-draft-ngl 999 -ctkd q8_0 -ctvd q8_0 --metrics"
python3 harness4.py sanity --engine M --label v4-C1-n46-mtp3-gpu   --spec "-ncmoe 46 $BASE $MTP --spec-draft-n-max 3"
python3 harness4.py sanity --engine M --label v4-C1-n46-mtp3-cmoed --spec "-ncmoe 46 $BASE $MTP --spec-draft-n-max 3 --spec-draft-cpu-moe"
echo "PHASE C1 DONE $(date)"
