#!/usr/bin/env bash
# v4 Phase A: F production config, 3 reps + FULL in one load, then the session test.
cd ~/flashnext-opt
SPEC="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness4.py bench   --engine F --label v4-A-F-n46 --spec "$SPEC" --full
python3 harness4.py session --engine F --label v4-A-F-n46-session --spec "$SPEC"
echo "PHASE A DONE $(date)"
