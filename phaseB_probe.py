"""Find, for the high-ubatch pairs, an ncmoe that survives the FULL window at all.
Cheap prefill-only probe (max_tokens 16). Walks ncmoe up until the window completes
with peak <= 13400 MiB."""
import json, subprocess, sys, time
KV="--cache-type-k q8_0 --cache-type-v q8_0"
def probe(label, core, window=128):
    spec=f"{core} -c {131072 if window==128 else 262144} {KV}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}  {spec}",flush=True)
    subprocess.run([sys.executable,"harness.py","fullprobe","--label",label,
                    "--spec",spec,"--window",str(window)])
    last=None
    for l in open("results.jsonl"):
        r=json.loads(l)
        if r.get("label")==label and r.get("kind")=="fullprobe": last=r
    return last
PLAN=[("2048","2048",[46,47,48]), ("4096","4096",[48,50,52])]
res={}
for b,ub,ns in PLAN:
    for n in ns:
        r=probe(f"B-probe-b{b}-ub{ub}-n{n}", f"-ncmoe {n} -t 16 -b {b} -ub {ub}")
        ok = bool(r and r.get("completed") and (r.get("peak_vram_mib") or 9e9)<=13400)
        print(f"  -> b{b}/ub{ub} n{n}: completed={r and r.get('completed')} "
              f"peak={r and r.get('peak_vram_mib')} reached={r and r.get('max_tokens_seen')} "
              f"oom_alloc={r and r.get('oom_alloc_mib')} => {'PASS' if ok else 'fail'}",flush=True)
        res[f"{b}/{ub}/{n}"]={"ok":ok,"peak":r and r.get("peak_vram_mib"),
                              "reached":r and r.get("max_tokens_seen"),
                              "prefill":r and r.get("FULL_prefill_ps")}
        if ok: break
json.dump(res,open("phaseB_probe.json","w"),indent=2)
print("PROBE PLAN DONE",json.dumps(res),flush=True)
