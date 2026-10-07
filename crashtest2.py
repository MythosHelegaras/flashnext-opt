"""Is 'first prompt smaller than -ub aborts the server' a property of ub2048 only, or a
latent bug in the fork that the shipped ub512 merely hides (772 > 512)?
Probe each ub with a first prompt deliberately BELOW its ubatch."""
import json, time, harness as H
SMALL = H.corpus("p4k")[:1000]            # ~300 tokens, below every ub tested
MED   = open("/mnt/ai/evals/harness/prompt_B.txt").read()   # 772 tokens
CASES=[("T6-ub512-n42-small",  "-ncmoe 42 -t 16 -b 2048 -ub 512  -c 131072", SMALL, "~300 < ub512"),
       ("T7-ub1024-n43-772",   "-ncmoe 43 -t 16 -b 2048 -ub 1024 -c 131072", MED,   "772 < ub1024"),
       ("T8-ub1024-n43-small", "-ncmoe 43 -t 16 -b 2048 -ub 1024 -c 131072", SMALL, "~300 < ub1024"),
       ("T9-ub2048-n46-small", "-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072", SMALL, "~300 < ub2048")]
KV="--cache-type-k q8_0 --cache-type-v q8_0"
res={}
for label, core, body, note in CASES:
    spec=f"{core} {KV}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}  ({note})",flush=True)
    s=H.Server(label,spec); r={"note":note,"spec":spec}
    try:
        s.start(timeout=1200)
        out=H.chat(body, 300, nonce=None)      # FIRST request after load, no warm-up
        r.update({"ok":True,"prompt_n":out["prompt_n"],"predicted_n":out["predicted_n"]})
        print(f"  OK prompt_n={out['prompt_n']}",flush=True)
    except Exception as e:
        log=open(s.log).read()
        r.update({"ok":False,"cuda_illegal":"illegal memory access" in log,"err":str(e)[:150]})
        print(f"  CRASH cuda_illegal={r['cuda_illegal']}",flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    res[label]=r
json.dump(res,open("crashtest2.json","w"),indent=2)
print("\nCRASHTEST2 DONE",flush=True)
for k,v in res.items(): print(f"  {k:22s} {v['note']:16s} -> {'OK' if v['ok'] else 'CRASH'}",flush=True)
