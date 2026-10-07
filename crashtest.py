"""Isolate the CUDA illegal-memory-access that killed the winner config on Task 02.
Twice reproducible there; never seen in bench/full/probe runs. The one structural
difference: bench/full always issue a 4061-token warm-up first, while task02 makes a
772-token prompt the server's FIRST request after load.
Variables: config x (warm-up or not) x first-prompt size."""
import json, os, sys, time, urllib.request, harness as H
PROMPT=open("/mnt/ai/evals/harness/prompt_B.txt").read()
WIN="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
BAS="-ncmoe 42 -t 16 -b 2048 -ub 512 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
CASES=[("T1-win-nowarm-772",   WIN, False, "task02"),
       ("T2-win-warm-772",     WIN, True,  "task02"),
       ("T3-base-nowarm-772",  BAS, False, "task02"),
       ("T4-win-nowarm-4061",  WIN, False, "p4k"),
       ("T5-win-nowarm-772b",  WIN, False, "task02")]
res={}
for label, spec, warm, kind in CASES:
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label} warmup={warm} first={kind}",flush=True)
    s=H.Server(label,spec); r={"warmup":warm,"first":kind,"spec":spec}
    try:
        s.start(timeout=1200)
        if warm: H.chat(H.corpus("p4k"), 32, nonce="warm"); print("  warm-up ok",flush=True)
        body = PROMPT if kind=="task02" else H.corpus("p4k")
        out=H.chat(body, 2000, nonce=None)
        r.update({"ok":True,"prompt_n":out["prompt_n"],"predicted_n":out["predicted_n"],
                  "finish":out["finish_reason"]})
        print(f"  OK prompt_n={out['prompt_n']} predicted_n={out['predicted_n']}",flush=True)
    except Exception as e:
        log=open(s.log).read() if s.log and os.path.exists(s.log) else ""
        cuda="illegal memory access" in log
        r.update({"ok":False,"err":str(e)[:200],"cuda_illegal":cuda})
        print(f"  CRASH cuda_illegal={cuda} :: {str(e)[:120]}",flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    res[label]=r
json.dump(res,open("crashtest.json","w"),indent=2)
print("\nCRASHTEST DONE",json.dumps({k:{"ok":v["ok"]} for k,v in res.items()},indent=2),flush=True)
