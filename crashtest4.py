"""Is the trigger the token COUNT (~772) or prompt_B's CONTENT?
Per case: fresh load, tokenize-only to cut real source to an exact token count (/tokenize
runs no graph, so it does not count as the first inference request), then send it as the
FIRST inference request with no warm-up. prompt_B is the positive control."""
import json, time, urllib.request, harness as H
POOL=H.corpus("full128"); PB=open("/mnt/ai/evals/harness/prompt_B.txt").read()
SPEC="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
def cut_to(n):
    lo,hi,best=0,min(len(POOL),int(n*6)),None
    while lo<hi:
        mid=(lo+hi)//2
        t=H.ntok(POOL[:mid])
        if t<n: lo=mid+1
        else: hi=mid; best=mid
    return POOL[:(best or hi)]
CASES=[("V-src-600",600,None),("V-src-700",700,None),("V-src-772",772,None),
       ("V-src-800",800,None),("V-src-900",900,None),("V-promptB",None,PB)]
res={}
for label,n,body in CASES:
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}",flush=True)
    s=H.Server(label,SPEC); r={}
    try:
        s.start(timeout=1200)
        text = body if body is not None else cut_to(n)   # tokenize-only, no graph built
        out=H.chat(text,150,nonce=None)                  # FIRST inference request
        r.update({"ok":True,"prompt_n":out["prompt_n"]}); print(f"  OK prompt_n={out['prompt_n']}",flush=True)
    except Exception as e:
        r.update({"ok":False,"cuda":"illegal memory access" in open(s.log).read()})
        print(f"  CRASH cuda={r['cuda']}",flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    res[label]=r
json.dump(res,open("crashtest4.json","w"),indent=2)
print("\nCRASHTEST4 DONE",flush=True)
for k,v in res.items(): print(f"  {k:14s} prompt_n={v.get('prompt_n','-'):>6} -> {'OK' if v['ok'] else 'CRASH'}",flush=True)
