"""Isolate the variable: is it -ub, or is it the raised -ncmoe? prompt_B is the trigger."""
import json, time, harness as H
PB=open("/mnt/ai/evals/harness/prompt_B.txt").read()
KV="--cache-type-k q8_0 --cache-type-v q8_0"
CASES=[("W1-ub512-n46",  f"-ncmoe 46 -t 16 -b 2048 -ub 512  -c 131072 {KV}","ub512 at the winner's ncmoe"),
       ("W2-ub2048-n42", f"-ncmoe 42 -t 16 -b 2048 -ub 2048 -c 131072 {KV}","ub2048 at the baseline's ncmoe"),
       ("W3-ub768-n46",  f"-ncmoe 46 -t 16 -b 2048 -ub 768  -c 131072 {KV}","ub768: is 512 special?")]
res={}
for label,spec,note in CASES:
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label} ({note})",flush=True)
    s=H.Server(label,spec); r={"note":note}
    try:
        s.start(timeout=1200)
        out=H.chat(PB,150,nonce=None)
        r.update({"ok":True,"prompt_n":out["prompt_n"]}); print(f"  OK prompt_n={out['prompt_n']}",flush=True)
    except Exception as e:
        r.update({"ok":False,"cuda":"illegal memory access" in open(s.log).read()})
        print(f"  CRASH cuda={r['cuda']}",flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    res[label]=r
json.dump(res,open("crashtest5.json","w"),indent=2)
print("\nCRASHTEST5 DONE",flush=True)
for k,v in res.items(): print(f"  {k:14s} {v['note']:32s} -> {'OK' if v['ok'] else 'CRASH'}",flush=True)
