"""Phase B step 3: FULL (120k, 3 needles) on the top-3 candidates by T_turn.
On a VRAM-gate violation, retry once at ncmoe+1 (per prompt §6 B.3)."""
import json, subprocess, sys, time
KV="--cache-type-k q8_0 --cache-type-v q8_0"
CFGS=[("B-FULL-b4096-ub4096-n44","-ncmoe 44 -t 16 -b 4096 -ub 4096",45),
      ("B-FULL-b2048-ub2048-n43","-ncmoe 43 -t 16 -b 2048 -ub 2048",44),
      ("B-FULL-b2048-ub1024-n42","-ncmoe 42 -t 16 -b 2048 -ub 1024",43)]
def run(label, core):
    spec=f"{core} -c 131072 {KV}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}\n{spec}",flush=True)
    return subprocess.run([sys.executable,"harness.py","full","--label",label,
                           "--spec",spec,"--window","128"]).returncode
def peak_of(label):
    best=None
    for l in open("results.jsonl"):
        r=json.loads(l)
        if r.get("label")==label and r.get("kind")=="full" and r.get("ok"): best=r
    return best
for label, core, retry_n in CFGS:
    run(label, core)
    r=peak_of(label)
    if r and r["peak_vram_mib"]>13400:
        print(f"!! {label} peak {r['peak_vram_mib']} > 13400 -> retry at ncmoe {retry_n}",flush=True)
        core2=core.replace(core.split()[1], str(retry_n), 1)
        run(label+f"-retry-n{retry_n}", core2)
    elif r:
        print(f"   {label} peak {r['peak_vram_mib']} MiB, needles_ok={r['needles_ok']}",flush=True)
print("PHASE B FULL DONE",flush=True)
