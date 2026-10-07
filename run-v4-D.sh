#!/usr/bin/env bash
# v4 Phase D: 256k on M (no MTP). Load ladder, then FULL 240k at the ncmoe given as $1 (default: decide later).
cd ~/flashnext-opt
while pgrep -f 'harness4.py|run-v4-S2.sh' >/dev/null; do sleep 15; done
B="-t 16 -b 2048 -ub 2048 -c 262144 --cache-type-k q8_0 --cache-type-v q8_0"
for N in 46 45 44; do python3 harness4.py load --engine M --label v4-D-load-n$N --spec "-ncmoe $N $B"; done
echo "D LOADS DONE $(date)"
