#!/usr/bin/env bash
cd ~/flashnext-opt
while kill -0 $(cat logs/v2-q2-AB.pid) 2>/dev/null; do sleep 10; done
python3 harness2.py session --model q2 --label v2-D-q2-n46-ub2048 --spec "-ncmoe 46 -b 2048 -ub 2048 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness2.py session --model q2 --label v2-D-q2-n42-ub512  --spec "-ncmoe 42 -b 2048 -ub 512 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness2.py cold    --model q2 --label v2-E-q2-n46-ub2048 --spec "-ncmoe 46 -b 2048 -ub 2048 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness2.py task02  --model q2 --label v2-F-q2-n46-ub2048 --spec "-ncmoe 46 -b 2048 -ub 2048 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
echo CHAIN_DONE
