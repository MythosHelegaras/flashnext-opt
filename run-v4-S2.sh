#!/usr/bin/env bash
# second session rep: M+MTP k2 (n47) and M no-MTP (n46)
cd ~/flashnext-opt
while pgrep -f 'harness4.py' >/dev/null; do sleep 15; done
HEAD=/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf
B="-t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness4.py session --engine M --label v4-S2-n47-k2-session --spec "-ncmoe 47 $B --spec-type draft-mtp --model-draft $HEAD --spec-draft-ngl 999 -ctkd q8_0 -ctvd q8_0 --spec-draft-cpu-moe --metrics --spec-draft-n-max 2"
python3 harness4.py session --engine M --label v4-S2-M-n46-session --spec "-ncmoe 46 $B"
echo "S2 DONE $(date)"
