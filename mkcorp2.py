import sys; sys.argv=["x"]; sys.path.insert(0,"/home/zef/flashnext-opt")
import harness2 as h
s=h.Server("mkcorp2","-ncmoe 42 -t 16 -b 2048 -ub 512 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0","q2").start()
try:
    h.build_cold(); h.build_session()
finally:
    s.kill()
