"""Phase B step 2: 3-rep P4k/P32k/D0 at each (b,ub) pair's lowest passing ncmoe.
b2048/ub512@42 is the baseline and is NOT re-run (rule 11: never redo a finished run)."""
import subprocess, sys, time
KV = "--cache-type-k q8_0 --cache-type-v q8_0"
CFGS = [("B-c128-b2048-ub1024-n42", "-ncmoe 42 -t 16 -b 2048 -ub 1024"),
        ("B-c128-b2048-ub2048-n43", "-ncmoe 43 -t 16 -b 2048 -ub 2048"),
        ("B-c128-b4096-ub4096-n44", "-ncmoe 44 -t 16 -b 4096 -ub 4096")]
for label, core in CFGS:
    spec = f"{core} -c 131072 {KV}"
    print(f"\n===== [{time.strftime('%H:%M:%S')}] {label}\n{spec}", flush=True)
    rc = subprocess.run([sys.executable,"harness.py","bench","--label",label,
                         "--spec",spec,"--reps","3"]).returncode
    print(f"----- {label} rc={rc}", flush=True)
print("PHASE B BENCH DONE", flush=True)
