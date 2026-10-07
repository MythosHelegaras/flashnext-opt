#!/usr/bin/env bash
# v4b: finish gating M at 256k / ncmoe 48 (no MTP). v4 already passed gates 1-2 (FULL 240k peak 12,366, 3/3 needles).
# Adds: 3-rep speed (D0/D32k), session, gate 3 (11 cold starts), gate 4 (Task 02). ~1 h. Uses the v4 harness.
set -uo pipefail
cd ~/flashnext-opt
SPEC="-ncmoe 48 -t 16 -b 2048 -ub 2048 -c 262144 --cache-type-k q8_0 --cache-type-v q8_0"
systemctl --user stop llama-swap
trap 'systemctl --user start llama-swap; echo "llama-swap restarted"' EXIT
sleep 3
if nvidia-smi --query-compute-apps=name --format=csv,noheader | grep -q llama-server; then
  echo "ABORT: a llama-server still holds the GPU"; exit 1
fi
python3 harness4.py bench   --engine M --label v4b-256-n48       --spec "$SPEC"
python3 harness4.py session --engine M --label v4b-256-n48-session --spec "$SPEC"
python3 harness4.py cold    --engine M --label v4b-256-n48-coldset --spec "$SPEC"
python3 harness4.py task02  --engine M --label v4b-256-n48-task02  --spec "$SPEC"
echo "== v4b summary =="
grep '"v4b-256-n48' results-v4.jsonl | python3 -c '
import json,sys
for l in sys.stdin:
    d=json.loads(l); k=d.get("key") or d.get("label")
    pick={x:d[x] for x in ("D0_ps","D32k_ps","P32k_ps","session_s","passed","total","gate4","finish","peak_vram_mib") if x in d}
    print(k, pick)'
echo "DONE $(date)"
