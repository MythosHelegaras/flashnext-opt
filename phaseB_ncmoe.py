"""Phase B step 1: for each (b,ub) pair find the LOWEST ncmoe whose LOAD-time process
VRAM <= 13050 MiB (= 13400 gate - 350 full-window surcharge allowance), then also
record that value +1 as the safe alternative. Load-only: cheap, no timing."""
import json, sys, time, harness as H

LIMIT = 13050
CTX   = sys.argv[1] if len(sys.argv) > 1 else "131072"
PAIRS = [("2048","512"),("2048","1024"),("2048","2048"),("4096","4096")]
KV    = "--cache-type-k q8_0 --cache-type-v q8_0"
out   = {}

def try_load(b, ub, n):
    label = f"B-load-c{CTX}-b{b}-ub{ub}-n{n}"
    spec  = f"-ncmoe {n} -t 16 -b {b} -ub {ub} -c {CTX} {KV}"
    s = H.Server(label, spec)
    row = {"kind":"load","label":label,"spec":spec,"cmd":" ".join(s.cmd),"ctx":CTX,
           "b":b,"ub":ub,"ncmoe":n}
    try:
        s.start(timeout=900)
        bu, bf = H.board()
        row.update({"ok":True,"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram,
                    "board_used_mib":bu,"board_free_mib":bf,
                    "mem_avail_kb":s.mem_load,"rss":s.rss_load,
                    "graphs_reused":s.graphs_reused()})
        print(f"  ncmoe {n}: load_vram {s.load_vram} MiB  free {bf}  ({s.load_s:.0f}s)"
              f"  {'PASS' if s.load_vram <= LIMIT else 'over'}", flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:1200]})
        print(f"  ncmoe {n}: LOAD FAIL -- {str(e)[:160]}", flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    H.record(row)
    return row

for b, ub in PAIRS:
    print(f"[{time.strftime('%H:%M:%S')}] c={CTX} b={b} ub={ub}", flush=True)
    lowest = None
    for n in range(42, 49):
        r = try_load(b, ub, n)
        if r.get("ok") and r["load_vram_mib"] <= LIMIT:
            lowest = n; break
    if lowest is None:
        out[f"{b}/{ub}"] = None
        print(f"  -> no ncmoe <= 48 fits", flush=True); continue
    safe = try_load(b, ub, lowest+1)          # §3: confirm value+1 as safe alternative
    out[f"{b}/{ub}"] = {"lowest":lowest, "safe":lowest+1,
                        "safe_ok":bool(safe.get("ok") and safe["load_vram_mib"]<=LIMIT)}
    print(f"  -> lowest ncmoe {lowest}, safe {lowest+1}", flush=True)

json.dump(out, open(f"phaseB_ncmoe_c{CTX}.json","w"), indent=2)
print("NCMOE SEARCH DONE", json.dumps(out), flush=True)
