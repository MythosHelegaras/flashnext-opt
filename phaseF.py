"""Phase F: Task 02 Prompt B, clean-room, on baseline and on the final candidate."""
import subprocess, sys, time, harness as H
CFGS=[("baseline","-ncmoe 42 -t 16 -b 2048 -ub 512 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"),
      ("winner",  "-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0")]
for name, spec in CFGS:
    print(f"\n===== [{time.strftime('%H:%M:%S')}] task02 {name}\n{spec}",flush=True)
    s=H.Server(f"F-{name}",spec)
    try:
        s.start(timeout=1500)
        print(f"  loaded {s.load_vram} MiB",flush=True)
        rc=subprocess.run([sys.executable,"task02.py",name]).returncode
        print(f"----- task02 {name} rc={rc}",flush=True)
    except Exception as e:
        print("  FAIL:",str(e)[:400],flush=True)
    finally:
        try: s.kill()
        except Exception: pass
print("PHASE F DONE",flush=True)
