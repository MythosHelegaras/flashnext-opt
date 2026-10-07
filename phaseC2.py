"""Phase C control: re-collect the f16 reference after a FRESH reload of the SAME config.
f16-vs-f16b is the run-to-run noise floor. Without it, q8-vs-f16 agreement means nothing."""
import subprocess, sys, time, harness as H
spec="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k f16  --cache-type-v f16"
print(f"===== [{time.strftime('%H:%M:%S')}] C-f16b (identical config, fresh load)",flush=True)
s=H.Server("C-f16b",spec)
try:
    s.start(timeout=1500); print(f"  loaded {s.load_vram} MiB",flush=True)
    rc=subprocess.run([sys.executable,"kvfidelity.py","collect","f16b"]).returncode
    print(f"  collect rc={rc}",flush=True)
finally:
    try: s.kill()
    except Exception: pass
subprocess.run([sys.executable,"kvfidelity.py","compare","f16","f16b","q8","f16kq8v"])
print("PHASE C2 DONE",flush=True)
