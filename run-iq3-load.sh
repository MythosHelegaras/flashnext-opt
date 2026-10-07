#!/usr/bin/env bash
cd ~/flashnext-opt
while kill -0 $(cat logs/v2-q2-DEF.pid) 2>/dev/null; do sleep 10; done
grep MemAvailable /proc/meminfo
python3 harness2.py load --model iq3 --label v2-C-iq3-load-n42-ub512 --timeout 2400 --spec "-ncmoe 42 -b 2048 -ub 512 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
for n in 43 44 46 47; do
python3 harness2.py load --model iq3 --label v2-C-iq3-load-n$n-ub512 --spec "-ncmoe $n -b 2048 -ub 512 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
done
python3 harness2.py load --model iq3 --label v2-C-iq3-load-n44-ub1024 --spec "-ncmoe 44 -b 2048 -ub 1024 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
python3 harness2.py load --model iq3 --label v2-C-iq3-load-n46-ub2048 --spec "-ncmoe 46 -b 2048 -ub 2048 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
echo CHAIN_DONE
