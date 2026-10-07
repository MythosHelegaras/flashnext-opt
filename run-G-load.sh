#!/usr/bin/env bash
cd ~/flashnext-opt
while kill -0 $(cat logs/v2-iq3.pid) 2>/dev/null; do sleep 10; done
for n in 42 43 44 45 46; do
python3 harness2.py load --model q2 --label v2-G-q2-c256-load-n$n-ub512 --timeout 2400 --spec "-ncmoe $n -b 2048 -ub 512 -t 16 -c 262144 --cache-type-k q8_0 --cache-type-v q8_0"
done
echo CHAIN_DONE
