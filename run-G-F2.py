#!/usr/bin/env python3
import json, subprocess
R = "/home/zef/flashnext-opt"
def h(*a):
    print(">>", " ".join(a), flush=True); subprocess.run(["python3", f"{R}/harness2.py", *a], cwd=R)
def last(label):
    row = None
    for l in open(f"{R}/results-v2.jsonl"):
        r = json.loads(l)
        if r.get("label") == label: row = r
    return row
K = "-t 16 --cache-type-k q8_0 --cache-type-v q8_0"
for n in (45, 46):
    lab = f"v2-G-q2-c256-n{n}-ub512-FULL240"
    h("full", "--model", "q2", "--window", "256", "--timeout", "2400", "--label", lab,
      "--spec", f"-ncmoe {n} -b 2048 -ub 512 -c 262144 {K}")
    r = last(lab) or {}
    ok = bool(r.get("ok") and r.get("needles_ok") and r.get("finish_ok") and (r.get("peak_vram_mib") or 99999) <= 13400)
    print(f"   {lab}: ok={r.get('ok')} peak={r.get('peak_vram_mib')} needles={r.get('needles_ok')} -> {'PASS' if ok else 'FAIL'}", flush=True)
    if ok: break
h("task02", "--model", "q2",  "--label", "v2-F2-q2-n46-ub2048",  "--spec", f"-ncmoe 46 -b 2048 -ub 2048 -c 131072 {K}")
h("task02", "--model", "iq3", "--label", "v2-F2-iq3-n46-ub2048", "--spec", f"-ncmoe 46 -b 2048 -ub 2048 -c 131072 {K}")
print("CHAIN_DONE", flush=True)
