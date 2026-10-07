"""Phase B step 4: 3-rep timings at the ncmoe values that actually survive the FULL
window, then a proper FULL (needles+decode) on the leader, then the n45 curve point."""
import subprocess, sys, time
KV="--cache-type-k q8_0 --cache-type-v q8_0"
def go(mode, label, core, extra=()):
    spec=f"{core} -c 131072 {KV}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {mode} {label}\n{spec}",flush=True)
    rc=subprocess.run([sys.executable,"harness.py",mode,"--label",label,"--spec",spec,*extra]).returncode
    print(f"----- {label} rc={rc}",flush=True)
go("bench","B2-ub2048-n46","-ncmoe 46 -t 16 -b 2048 -ub 2048",("--reps","3"))
go("bench","B2-ub1024-n43","-ncmoe 43 -t 16 -b 2048 -ub 1024",("--reps","3"))
go("full","B2-FULL-ub2048-n46","-ncmoe 46 -t 16 -b 2048 -ub 2048",("--window","128"))
go("fullprobe","B2-probe-ub2048-n45","-ncmoe 45 -t 16 -b 2048 -ub 2048",("--window","128"))
print("PB2 DONE",flush=True)
