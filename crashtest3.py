"""Confirm the window: at ub2048 a first prompt of ~1500 (partial first ubatch, >512)
should abort; ~2500 (full first ubatch of 2048, then 452) should be fine."""
import json, time, harness as H
p=H.corpus("full128")
def slice_to(n):     # ~3.36 bytes/token in this corpus
    return p[:int(n*3.36)]
CASES=[("U1-ub2048-1500", slice_to(1500), "~1500 partial first ubatch, >512 -> predict CRASH"),
       ("U2-ub2048-2500", slice_to(2500), "~2500 full first ubatch -> predict OK")]
res={}
for label, body, note in CASES:
    spec="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}  ({note})",flush=True)
    s=H.Server(label,spec); r={"note":note}
    try:
        s.start(timeout=1200)
        out=H.chat(body, 200, nonce=None)
        r.update({"ok":True,"prompt_n":out["prompt_n"]}); print(f"  OK prompt_n={out['prompt_n']}",flush=True)
    except Exception as e:
        r.update({"ok":False,"cuda_illegal":"illegal memory access" in open(s.log).read()})
        print(f"  CRASH cuda_illegal={r['cuda_illegal']}",flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    res[label]=r
json.dump(res,open("crashtest3.json","w"),indent=2)
print("CRASHTEST3 DONE",json.dumps({k:v.get("ok") for k,v in res.items()}),flush=True)
