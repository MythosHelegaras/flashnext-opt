"""Phase B tail: thread variants at the leading point, then the 262144 context arm."""
import json, subprocess, sys, time
KV="--cache-type-k q8_0 --cache-type-v q8_0"
def go(mode,label,core,ctx="131072",extra=()):
    spec=f"{core} -c {ctx} {KV}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {mode} {label}\n{spec}",flush=True)
    rc=subprocess.run([sys.executable,"harness.py",mode,"--label",label,"--spec",spec,*extra]).returncode
    print(f"----- {label} rc={rc}",flush=True); return rc
def last(label,kind):
    r=None
    for l in open("results.jsonl"):
        j=json.loads(l)
        if j.get("label")==label and j.get("kind")==kind: r=j
    return r
# --- threads at the leader (ub2048 n46) ---
go("bench","B3-ub2048-n46-t12","-ncmoe 46 -t 12 -b 2048 -ub 2048",extra=("--reps","3"))
go("bench","B3-ub2048-n46-tb32","-ncmoe 46 -t 16 -tb 32 -b 2048 -ub 2048",extra=("--reps","3"))
# --- 256k arm: load search first (KV doubles, so expect ncmoe to rise) ---
low=None
for n in (46,47,48):
    go("load",f"B3-load-c256-n{n}",f"-ncmoe {n} -t 16 -b 2048 -ub 2048",ctx="262144")
    r=last(f"B3-load-c256-n{n}","load")
    print(f"   c256 n{n}: ok={r and r.get('ok')} load_vram={r and r.get('load_vram_mib')}",flush=True)
    if r and r.get("ok") and r["load_vram_mib"]<=13050: low=n; break
if low is None:
    print("256k: no ncmoe <= 48 passes the load pre-filter",flush=True)
else:
    print(f"256k lowest load-passing ncmoe = {low}",flush=True)
    go("bench",f"B3-c256-n{low}",f"-ncmoe {low} -t 16 -b 2048 -ub 2048",ctx="262144",extra=("--reps","3"))
    go("fullprobe",f"B3-c256-probe-n{low}",f"-ncmoe {low} -t 16 -b 2048 -ub 2048",ctx="262144",
       extra=("--window","256","--timeout","2400"))
print("PB3 DONE",flush=True)
