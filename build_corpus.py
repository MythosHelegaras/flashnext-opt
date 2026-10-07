import sys, harness as H
spec = "-ncmoe 42 -t 16 -b 2048 -ub 512 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
s = H.Server("corpusbuild", spec)
try:
    s.start(timeout=1500)
    print(f"server up, {s.load_s:.0f}s, vram {s.load_vram} MiB", flush=True)
    H.build_corpus()
    print("CORPUS DONE", flush=True)
finally:
    s.kill(); print("server killed", flush=True)
