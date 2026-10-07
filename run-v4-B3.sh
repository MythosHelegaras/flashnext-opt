#!/usr/bin/env bash
# v4 B3: --fit on instead of -ncmoe. fit aborts if -ngl or any tensor override is user-set
# (common/fit.cpp), so -ngl 999, -ot and -ncmoe are dropped; --lazy-mode on replaces -ot (B1: identical).
cd ~/flashnext-opt
while pgrep -f 'run-v4-B2(b)?\.sh' >/dev/null; do sleep 15; done
T=${1:-3000}
SPEC="-t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0 --fit on --fit-target $T"
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader
python3 harness4.py bench --engine M --nongl --ple lazy --label v4-B3-M-fit$T --spec "$SPEC" --full
echo "PHASE B3 fit$T DONE $(date)"
