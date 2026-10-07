#!/usr/bin/env bash
# v4 Phase B2: M at production settings with F's exact flags (B1 winner).
cd ~/flashnext-opt
SPEC="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness4.py bench   --engine M --label v4-B2-M-n46 --spec "$SPEC" --full
python3 harness4.py session --engine M --label v4-B2-M-n46-session --spec "$SPEC"
python3 harness4.py cold    --engine M --label v4-B2-M-n46 --spec "$SPEC"
python3 harness4.py task02  --engine M --label v4-B2-M-n46-task02 --spec "$SPEC"
echo "PHASE B2 DONE $(date)"
