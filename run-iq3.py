#!/usr/bin/env python3
"""IQ3_XXS phases C -> D -> E -> F, unattended. Ladder with one +1 retry on a FULL bust,
sessions on every passing rung, then cold + task02 on the fastest-session rung."""
import json, subprocess, sys, time
R = "/home/zef/flashnext-opt"
S = "-t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
GATE = 13400
def h(*args):
    print(">>", " ".join(args), flush=True)
    subprocess.run(["python3", f"{R}/harness2.py", *args], cwd=R)
def last(label):
    row = None
    for l in open(f"{R}/results-v2.jsonl"):
        r = json.loads(l)
        if r.get("label") == label: row = r
    return row
def spec(n, ub): return f"-ncmoe {n} -b 2048 -ub {ub} {S}"
passing = []
for ub, n in ((2048, 46), (512, 43), (1024, 44)):
    for attempt in (n, n + 1):
        lab = f"v2-C-iq3-n{attempt}-ub{ub}"
        h("bench", "--model", "iq3", "--full", "--label", lab, "--spec", spec(attempt, ub))
        r = last(lab) or {}
        f = r.get("full") or {}
        ok = bool(r.get("ok") and f.get("needles_ok") and f.get("finish_ok")
                  and (r.get("peak_vram_mib") or 99999) <= GATE)
        print(f"   {lab}: ok={r.get('ok')} peak={r.get('peak_vram_mib')} needles={f.get('needles_ok')} -> {'PASS' if ok else 'FAIL'}", flush=True)
        if ok: passing.append((attempt, ub)); break
print("PASSING", passing, flush=True)
sess = {}
for n, ub in passing:
    lab = f"v2-D-iq3-n{n}-ub{ub}"
    h("session", "--model", "iq3", "--label", lab, "--spec", spec(n, ub))
    r = last(lab) or {}
    if r.get("ok"): sess[(n, ub)] = r["session_s"]
print("SESSIONS", {f"n{k[0]}-ub{k[1]}": v for k, v in sess.items()}, flush=True)
if not sess: print("NO IQ3 SESSION RESULT"); sys.exit(1)
n, ub = min(sess, key=sess.get)
print(f"BEST IQ3 n{n} ub{ub}", flush=True)
h("cold", "--model", "iq3", "--label", f"v2-E-iq3-n{n}-ub{ub}", "--spec", spec(n, ub))
h("task02", "--model", "iq3", "--label", f"v2-F-iq3-n{n}-ub{ub}", "--spec", spec(n, ub))
print("CHAIN_DONE", flush=True)
