"""Phase D (load mode A/B) and Phase E (multi-turn prefix reuse) at the leading config."""
import json, subprocess, sys, time
LEAD="-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
def go(mode,label,spec,extra=()):
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {mode} {label}\n{spec}",flush=True)
    rc=subprocess.run([sys.executable,"harness.py",mode,"--label",label,"--spec",spec,*extra]).returncode
    print(f"----- {label} rc={rc}",flush=True)
# Phase D: --load-mode none vs the shipped default (auto/mmap, already measured as B2-ub2048-n46)
go("bench","D-lm-none",f"{LEAD} -lm none",("--reps","3","--timeout","2400"))
# Phase E: prefix reuse, default flags then with --cache-reuse if needed
go("reuse","E-reuse-default",LEAD,("--timeout","2400",))
print("PHASE DE DONE",flush=True)
