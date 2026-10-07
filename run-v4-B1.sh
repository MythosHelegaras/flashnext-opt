#!/usr/bin/env bash
# v4 Phase B1: M flag compatibility. Waits for Phase A to finish first.
cd ~/flashnext-opt
while pgrep -f run-v4-A.sh >/dev/null; do sleep 15; done
SPEC="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness4.py sanity --engine M --label v4-B1-M-exactF         --spec "$SPEC"
python3 harness4.py sanity --engine M --label v4-B1-M-rotoff --rot off --spec "$SPEC"
python3 harness4.py sanity --engine M --label v4-B1-M-lazy   --ple lazy --spec "$SPEC"
python3 harness4.py sanity --engine M --label v4-B1-M-fitoff --fitoff  --spec "$SPEC"
echo "PHASE B1 DONE $(date)"
