#!/usr/bin/env bash
# v4 C2: MTP draft depth n-max {3,2,1} at -ncmoe 47, head experts on CPU. n-max 3 carries FULL.
cd ~/flashnext-opt
while pgrep -f 'harness4.py' >/dev/null; do sleep 15; done
HEAD=/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf
BASE="-ncmoe 47 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
MTP="--spec-type draft-mtp --model-draft $HEAD --spec-draft-ngl 999 -ctkd q8_0 -ctvd q8_0 --spec-draft-cpu-moe --metrics"
python3 harness4.py bench --engine M --label v4-C2-n47-k3 --spec "$BASE $MTP --spec-draft-n-max 3" --full
for K in 3 2 1; do
  [[ $K != 3 ]] && python3 harness4.py bench --engine M --label v4-C2-n47-k$K --spec "$BASE $MTP --spec-draft-n-max $K"
  python3 harness4.py session --engine M --label v4-C2-n47-k$K-session --spec "$BASE $MTP --spec-draft-n-max $K"
done
echo "PHASE C2 DONE $(date)"
