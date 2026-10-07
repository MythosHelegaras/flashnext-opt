#!/usr/bin/env python3
"""Phase F: Task 02 Prompt B, clean-room, then mechanical scoring with the harness probe.

Clean-room rules come from /mnt/ai/MoEFinetunning/eval-task02.sh: the run dir is created
EMPTY, the prompt and probe.py live OUTSIDE it, and probe.py is copied in only at score
time (a probe.py sitting in the working dir during generation is contamination).
"""
import json, os, re, shutil, subprocess, sys, time, urllib.request

BASE="http://127.0.0.1:9997"
HARNESS="/mnt/ai/evals/harness"
FILES=["breaker_state.py","call_context.py","breaker_events.py","circuit_breaker.py"]

def post(path,payload,timeout=5400):
    req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode(),
                               headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode())

def extract(text):
    """Map fenced blocks to the four target filenames."""
    out={}
    blocks=[(m.start(),m.group(1) or "",m.group(2)) for m in
            re.finditer(r"```([A-Za-z0-9_+-]*)\n(.*?)```", text, re.S)]
    for start,lang,body in blocks:
        name=None
        m=re.search(r"#\s*(?:file:\s*)?([a-z_]+\.py)", body[:200])   # filename comment inside
        if m and m.group(1) in FILES: name=m.group(1)
        if name is None:                                              # nearest mention before
            head=text[:start]; best=-1
            for f in FILES:
                i=head.rfind(f)
                if i>best: best, name = i, f
            if best==-1: name=None
        if name and name not in out and body.strip(): out[name]=body
    return out

def run(label, outdir, max_tokens=60000):
    os.makedirs(outdir, exist_ok=True)                 # created EMPTY
    assert not os.listdir(outdir), f"{outdir} must start empty (contamination rule)"
    prompt=open(f"{HARNESS}/prompt_B.txt").read()      # prompt lives OUTSIDE the run dir
    t0=time.time()
    r=post("/v1/chat/completions",{"messages":[{"role":"user","content":prompt}],
            "max_tokens":max_tokens,"temperature":0.3,"top_p":0.95,"top_k":20,
            "seed":20260929,"cache_prompt":False,"stream":False})
    wall=time.time()-t0
    ch=r["choices"][0]; msg=ch.get("message",{}) or {}
    content=msg.get("content") or ""; reasoning=msg.get("reasoning_content") or ""
    tm=r.get("timings",{}) or {}
    meta={"label":label,"wall_s":round(wall,1),"finish_reason":ch.get("finish_reason"),
          "content_len":len(content),"reasoning_len":len(reasoning),
          "prompt_n":tm.get("prompt_n"),"predicted_n":tm.get("predicted_n"),
          "predicted_ps":tm.get("predicted_per_second")}
    files=extract(content)
    meta["files_found"]=sorted(files); meta["files_missing"]=[f for f in FILES if f not in files]
    for name,body in files.items():
        open(os.path.join(outdir,name),"w").write(body)
    # artefacts kept OUTSIDE the run dir so the dir holds only model output
    side=outdir.rstrip("/")+".meta"
    os.makedirs(side,exist_ok=True)
    open(f"{side}/response.md","w").write(content)
    open(f"{side}/reasoning.txt","w").write(reasoning)
    json.dump(meta,open(f"{side}/meta.json","w"),indent=2)
    return meta, side

def score(outdir, side):
    shutil.copy(f"{HARNESS}/probe.py", outdir)          # copied in only now
    p=subprocess.run([sys.executable,"probe.py"],cwd=outdir,capture_output=True,text=True,timeout=300)
    out=p.stdout+("\n[stderr]\n"+p.stderr if p.stderr.strip() else "")
    open(f"{side}/probe.out","w").write(out)
    res={}
    for n in (1,2,3,5):
        m=re.search(rf"PROBE {n} .*?-> *(PASS|FAIL)", out)
        if m is None:
            m2=re.search(rf"PROBE {n} .*?(PASS|FAIL)", out)
            res[f"probe{n}"]= m2.group(1) if m2 else "NO_OUTPUT"
        else: res[f"probe{n}"]=m.group(1)
    res["probe4_control"]="FAIL_expected" if "crit 7 FAIL" in out or "tripped on first failure" in out else "other"
    return res, out

if __name__=="__main__":
    label=sys.argv[1]
    outdir=os.path.expanduser(f"~/flashnext-opt/runs/task02-{label}")
    meta, side = run(label, outdir)
    print(json.dumps(meta,indent=2),flush=True)
    if meta["files_missing"]:
        print("MISSING FILES -> cannot score:",meta["files_missing"],flush=True)
        json.dump({"label":label,"meta":meta,"scored":False},
                  open(os.path.expanduser(f"~/flashnext-opt/task02-{label}.json"),"w"),indent=2)
        sys.exit(2)
    res,out=score(outdir,side)
    print(out,flush=True); print(json.dumps(res,indent=2),flush=True)
    json.dump({"label":label,"meta":meta,"probes":res,"scored":True},
              open(os.path.expanduser(f"~/flashnext-opt/task02-{label}.json"),"w"),indent=2)
