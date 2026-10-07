#!/usr/bin/env bash
cd ~/flashnext-opt
python3 harness2.py bench --model q2 --full --label v2-A-q2-n42-ub512  --spec "-ncmoe 42 -b 2048 -ub 512 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness2.py bench --model q2 --full --label v2-B-q2-n46-ub2048 --spec "-ncmoe 46 -b 2048 -ub 2048 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness2.py bench --model q2 --full --label v2-B-q2-n43-ub1024 --spec "-ncmoe 43 -b 2048 -ub 1024 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
echo CHAIN_DONE
