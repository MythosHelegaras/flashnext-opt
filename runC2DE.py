import subprocess, sys
for scr in ("phaseC2.py","phaseDE.py"):
    print(f"\n######## {scr}",flush=True)
    subprocess.run([sys.executable,scr])
print("C2+DE ALL DONE",flush=True)
