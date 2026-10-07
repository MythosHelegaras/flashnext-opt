"""Phase F, attempt 2. Winner FIRST (it must clear the gate, and I need to know whether the
03:24 CUDA illegal-access crash recurs on this exact config). max_tokens 60000: the 16000-token
attempt died with finish_reason=length, content_len=0, reasoning_len=74976 -- a void run by
§7, not a model failure. One retry per config if the server dies."""
import os, shutil, subprocess, sys, time, harness as H
CFGS=[("winner",  "-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"),
      ("baseline","-ncmoe 42 -t 16 -b 2048 -ub 512 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0")]
def attempt(name, spec, tag):
    for d in (f"runs/task02-{name}", f"runs/task02-{name}.meta"):
        if os.path.exists(d): shutil.rmtree(d)       # run dir must start EMPTY
    print(f"\n===== [{time.strftime('%H:%M:%S')}] task02 {name} ({tag})\n{spec}",flush=True)
    s=H.Server(f"F2-{name}-{tag}",spec)
    try:
        s.start(timeout=1500); print(f"  loaded {s.load_vram} MiB",flush=True)
        rc=subprocess.run([sys.executable,"task02.py",name]).returncode
        alive = s.proc.poll() is None
        print(f"----- task02 {name} rc={rc} server_alive={alive}",flush=True)
        return rc, alive
    except Exception as e:
        print("  FAIL:",str(e)[:400],flush=True); return 99, False
    finally:
        try: s.kill()
        except Exception: pass
for name, spec in CFGS:
    rc, alive = attempt(name, spec, "a")
    if not alive:
        print(f"  !! server died during {name}; retrying once",flush=True)
        attempt(name, spec, "b")
print("PHASE F2 DONE",flush=True)
