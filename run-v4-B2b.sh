#!/usr/bin/env bash
# v4 B2 follow-up: gate 3 (cold set). The first chain's cold call collided with the bench label.
cd ~/flashnext-opt
while pgrep -f run-v4-B2.sh >/dev/null; do sleep 15; done
SPEC="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness4.py cold --engine M --label v4-B2-M-n46-coldset --spec "$SPEC"
echo "PHASE B2b DONE $(date)"
