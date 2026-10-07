"""Phase C: KV fidelity + cost. KLD tooling is absent (D4), so fidelity is measured through
the API with teacher forcing (kvfidelity.py). Reference = f16/f16 on the same Q2 weights."""
import json, subprocess, sys, time, harness as H
CORE="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072"
KVS=[("f16",     "--cache-type-k f16  --cache-type-v f16"),
     ("q8",      "--cache-type-k q8_0 --cache-type-v q8_0"),
     ("f16kq8v", "--cache-type-k f16  --cache-type-v q8_0")]
costs={}
for name, kv in KVS:
    label=f"C-{name}"
    spec=f"{CORE} {kv}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}\n{spec}",flush=True)
    s=H.Server(label,spec)
    row={"kind":"kvfid","label":label,"spec":spec,"cmd":" ".join(s.cmd)}
    try:
        s.start(timeout=1500)
        row.update({"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram,
                    "mem_avail_after_load_kb":s.mem_load})
        print(f"  loaded {s.load_vram} MiB in {s.load_s:.0f}s",flush=True)
        if name=="f16":   # smoke-test the logprob path once before spending an hour on it
            import kvfidelity as K
            d=K.dist_at(K.tokenize("int main(void) { return")[:8])
            print("  logprob smoke test ->",d[:3],flush=True)
            if not d: raise RuntimeError("no logprobs from /completion; phase C method invalid")
        rc=subprocess.run([sys.executable,"kvfidelity.py","collect",name]).returncode
        row.update({"collect_rc":rc,"peak_vram_mib":s.peak,"ok":rc==0})
        costs[name]={"load_vram_mib":s.load_vram,"peak_vram_mib":s.peak}
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:1500]}); print("  FAIL:",str(e)[:400],flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    H.record(row)
json.dump(costs,open("phaseC_costs.json","w"),indent=2)
print("\n=== KV VRAM cost at ncmoe 46 / ub2048 ===",json.dumps(costs,indent=2),flush=True)
subprocess.run([sys.executable,"kvfidelity.py","compare","f16","q8","f16kq8v"])
print("PHASE C DONE",flush=True)
