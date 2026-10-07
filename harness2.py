#!/usr/bin/env python3
"""flashnext overnight harness v2 (quant decision). Derived from harness.py (v1).
Adds: --model q2|iq3, v2 result files, MemAvailable abort, bench+FULL in one load,
session / cold / task02 subcommands.

Usage:
  harness.py corpus                                   build prompt corpus (needs a server up)
  harness.py load   --label L --spec "..."            load only, report VRAM, kill
  harness.py bench  --label L --spec "..." [--reps 3] [--tests p4k,p32,d0] [--full] [--keep]
  harness.py probe  --label L --spec "..." --mode reuse|task02

--spec holds ONLY the varying args, e.g. "-ncmoe 42 -t 16 -b 2048 -ub 512 -c 131072
--cache-type-k q8_0 --cache-type-v q8_0". Mandatory flags are added here, never by caller.
"""
import argparse, json, os, re, signal, subprocess, sys, threading, time, urllib.request, urllib.error

ROOT   = os.path.expanduser("~/flashnext-opt")
BIN    = "/opt/llama.cpp-qwen4exp/bin/llama-server"
MODELS = {"q2": "/mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/"
                "Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf",
          "iq3": "/mnt/ai/llm/models/qwen3.8-flash-next-gsq/IQ3_XXS/"
                 "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"}
MIN_MEMAVAIL_KB = 10 * 1024 * 1024     # v2 rule: abort if MemAvailable after load < 10 GB
PORT   = 9997
BASE   = f"http://127.0.0.1:{PORT}"
RESULTS= os.path.join(ROOT, "results-v2.jsonl")
STATE  = os.path.join(ROOT, "state-v2.json")
CORPUS = os.path.join(ROOT, "corpus")
SEED   = 20260929
# mandatory on every flashnext invocation (prompt hard rule 8) + shipped sampling
MANDATORY = ["-ngl","999","-fa","on","-np","1","--jinja","-ot","per_layer_token_embd=CPU"]
SAMPLING  = ["--temp","0.3","--top-p","0.95","--top-k","20"]

def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()

def mem_avail_kb():
    with open("/proc/meminfo") as f:
        for l in f:
            if l.startswith("MemAvailable"): return int(l.split()[1])
    return -1

def board():
    o = sh("nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits")
    u,f = [int(x) for x in o.split(",")]
    return u,f

def proc_vram(pid):
    o = sh("nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits")
    for line in o.splitlines():
        p = line.split(",")
        if p and p[0].strip().isdigit() and int(p[0]) == pid:
            return int(p[1])
    return 0

def rss(pid):
    try:
        d = {}
        with open(f"/proc/{pid}/status") as f:
            for l in f:
                if l.startswith(("VmRSS","RssAnon","RssFile","RssShmem")):
                    k,v = l.split(":"); d[k.strip()] = int(v.split()[0])
        return d
    except Exception: return {}

def post(path, payload, timeout=3600):
    req = urllib.request.Request(BASE+path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def get(path, timeout=10):
    with urllib.request.urlopen(BASE+path, timeout=timeout) as r:
        return json.loads(r.read().decode())

def ntok(text):
    return len(post("/tokenize", {"content": text}, timeout=600)["tokens"])

# ---------------------------------------------------------------- server mgmt
class Server:
    def __init__(self, label, spec, model="q2"):
        self.label, self.spec, self.model = label, spec, model
        self.cmd = ([BIN,"--port",str(PORT),"-m",MODELS[model]] + MANDATORY
                    + spec.split() + SAMPLING)
        self.pid = None; self.peak = 0; self._stop = False; self.log = None

    def start(self, timeout=1200):
        # rule 6: nothing of ours, and no llama-server at all, may be resident
        left = [l for l in sh("pgrep -af llama-server").splitlines() if "/bin/llama-server" in l]
        if left: raise RuntimeError(f"llama-server already running: {left}")
        if any("llama-server" in l for l in
               sh("nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv,noheader").splitlines()):
            raise RuntimeError("llama-server still holds VRAM")
        os.makedirs(os.path.join(ROOT,"logs"), exist_ok=True)
        self.log = os.path.join(ROOT,"logs",f"{self.label}.server.log")
        env = dict(os.environ); env["LLAMA_ATTN_ROT_DISABLE"] = "1"   # rule 8
        t0 = time.time()
        with open(self.log,"w") as lf:
            self.proc = subprocess.Popen(self.cmd, stdout=lf, stderr=subprocess.STDOUT,
                                         env=env, start_new_session=True)
        self.pid = self.proc.pid
        with open(os.path.join(ROOT,"logs",f"{self.label}.pid"),"w") as f: f.write(str(self.pid))
        while time.time()-t0 < timeout:
            if self.proc.poll() is not None:
                tail = open(self.log).read()[-2500:]
                raise RuntimeError(f"server exited rc={self.proc.returncode}\n{tail}")
            try:
                if get("/health", timeout=5).get("status") == "ok":
                    self.load_s = time.time()-t0
                    time.sleep(3)
                    self.load_vram = proc_vram(self.pid)
                    self.peak = self.load_vram
                    self.rss_load = rss(self.pid)
                    self.mem_load = mem_avail_kb()
                    if self.mem_load < MIN_MEMAVAIL_KB:
                        self.kill()
                        raise RuntimeError(f"ABORT: MemAvailable after load {self.mem_load} kB < 10 GB")
                    self._t = threading.Thread(target=self._watch, daemon=True); self._t.start()
                    return self
            except Exception: pass
            time.sleep(4)
        self.kill(); raise RuntimeError(f"server not ready in {timeout}s")

    def _watch(self):
        while not self._stop:
            v = proc_vram(self.pid)
            if v > self.peak: self.peak = v
            time.sleep(2)

    def kill(self):
        self._stop = True
        for p in (self.pid,):
            if not p: continue
            try: os.killpg(os.getpgid(p), signal.SIGTERM)
            except Exception:
                try: os.kill(p, signal.SIGTERM)
                except Exception: pass
        for _ in range(60):
            if self.proc.poll() is not None: break
            time.sleep(1)
        else:
            try: os.killpg(os.getpgid(self.pid), signal.SIGKILL)
            except Exception: pass
        time.sleep(5)

    def graphs_reused(self):
        try:
            m = re.findall(r"graphs reused\s*=\s*(\d+)", open(self.log).read())
            return int(m[-1]) if m else None
        except Exception: return None

# ---------------------------------------------------------------- corpus
SRC_ROOT = "/opt/llama.cpp-qwen4exp"
def raw_source(nbytes):
    """Distinct, non-repeating real source text (read-only). Skips agent/instruction
    files on purpose: corpus is timing data, not something to be read as guidance."""
    skip = ("AGENTS.md","CLAUDE.md","/skills/","/vendor/")
    out, tot = [], 0
    pat = r'\( -name "*.cpp" -o -name "*.c" -o -name "*.cu" -o -name "*.h" \)'
    files = sh(f'find {SRC_ROOT} {pat} -size +4k -printf "%s %p\\n" | sort -k2').splitlines()
    for line in files:
        try: _, path = line.split(" ",1)
        except ValueError: continue
        if any(s in path for s in skip): continue
        try: t = open(path, encoding="utf-8", errors="ignore").read()
        except Exception: continue
        out.append(f"\n\n// ===== FILE: {path} =====\n{t}")
        tot += len(out[-1])
        if tot >= nbytes: break
    return "".join(out)

def build_corpus():
    os.makedirs(CORPUS, exist_ok=True)
    pool = raw_source(4_000_000)
    print(f"source pool: {len(pool)} bytes", flush=True)
    targets = {"p4k":4000, "p32k":32000, "full128":120000, "full256":240000}
    for name, want in targets.items():
        path = os.path.join(CORPUS, name+".txt")
        if os.path.exists(path):
            print(f"{name}: exists, skip", flush=True); continue
        lo, hi = 0, min(len(pool), int(want*4.2))
        # binary search on byte length for exact token target (never estimate)
        best = None
        while lo < hi:
            mid = (lo+hi)//2
            n = ntok(pool[:mid])
            if n < want: lo = mid+1
            else: hi = mid; best = (mid, n)
        cut = best[0] if best else hi
        text = pool[:cut]; n = ntok(text)
        open(path,"w").write(text)
        print(f"{name}: {len(text)} bytes -> {n} tokens", flush=True)
        json.dump({"tokens":n,"bytes":len(text)}, open(path+".meta","w"))

def corpus(name):
    return open(os.path.join(CORPUS, name+".txt")).read()

# ---------------------------------------------------------------- needles
def needle_text(base, depths):
    """Insert unique 7-digit values at the given relative depths. Returns text+answers."""
    lines = base.split("\n")
    ans = {}
    for i,(tag,d) in enumerate(depths.items()):
        val = str(1000003 + i*337771)[:7]
        ans[tag] = val
        pos = max(1, min(len(lines)-1, int(len(lines)*d)))
        lines.insert(pos, f"// AUDIT_MARKER {tag.upper()} calibration_code = {val}  (do not remove)")
    return "\n".join(lines), ans

# ---------------------------------------------------------------- requests
def chat(prompt, max_tokens, nonce=None, cache=False, timeout=5400):
    """One timed generation. nonce at the START defeats any prefix reuse."""
    content = prompt if nonce is None else f"// run-nonce {nonce}\n{prompt}"
    payload = {"messages":[{"role":"user","content":content}],
               "max_tokens":max_tokens, "temperature":0.3, "top_p":0.95, "top_k":20,
               "seed":SEED, "cache_prompt":cache, "stream":False}
    t0 = time.time()
    r = post("/v1/chat/completions", payload, timeout=timeout)
    wall = time.time()-t0
    ch = r["choices"][0]; msg = ch.get("message",{}) or {}
    tm = r.get("timings",{}) or {}
    return {"wall_s":round(wall,3), "finish_reason":ch.get("finish_reason"),
            "content":msg.get("content") or "", "content_len":len(msg.get("content") or ""),
            "reasoning_len":len(msg.get("reasoning_content") or ""),
            "prompt_n":tm.get("prompt_n"), "prompt_ms":tm.get("prompt_ms"),
            "prompt_ps":tm.get("prompt_per_second"), "predicted_n":tm.get("predicted_n"),
            "predicted_ms":tm.get("predicted_ms"), "predicted_ps":tm.get("predicted_per_second")}

D0_PROMPT = ("Explain, in thorough technical prose, how a B+ tree handles an insert that "
             "overflows a leaf: node split, key promotion, parent overflow cascading to the "
             "root, root split and height increase, sibling pointer maintenance, and how a "
             "concurrent reader can be kept correct with latch coupling. Be exhaustive and "
             "do not stop early; cover at least ten distinct aspects in order.")

def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return None, None
    m = sum(xs)/len(xs)
    if len(xs) < 2: return round(m,3), 0.0
    sd = (sum((x-m)**2 for x in xs)/(len(xs)-1))**0.5
    return round(m,3), round(sd,3)

# ---------------------------------------------------------------- record
def record(row):
    row["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    row["fork_sha"] = FORK_SHA
    with open(RESULTS,"a") as f: f.write(json.dumps(row)+"\n")

FORK_SHA = sh("git -C /opt/llama.cpp-qwen4exp rev-parse HEAD")

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {"phase":"0","done":[],"best":None}

def save_state(**kw):
    s = load_state(); s.update(kw); s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(s, open(STATE,"w"), indent=2)

def mark_done(key, payload):
    s = load_state()
    d = s.get("done", [])
    if key not in [x.get("key") for x in d if isinstance(x,dict)]:
        d.append({"key":key, **payload})
    s["done"] = d; s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(s, open(STATE,"w"), indent=2)

# ---------------------------------------------------------------- phases
def cmd_load(a):
    s = Server(a.label, a.spec, a.model)
    row = {"kind":"load","model":a.model,"label":a.label,"spec":a.spec,"cmd":" ".join(s.cmd)}
    try:
        s.start(timeout=a.timeout)
        bu, bf = board()
        row.update({"ok":True,"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram,
                    "board_used_mib":bu,"board_free_mib":bf,
                    "mem_avail_kb":s.mem_load,"rss":s.rss_load,
                    "graphs_reused":s.graphs_reused()})
        print(json.dumps({k:row[k] for k in ("label","load_s","load_vram_mib","board_free_mib")}))
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:1500]})
        print("LOAD FAIL:", str(e)[:400])
    finally:
        try: s.kill()
        except Exception: pass
    record(row)
    return 0 if row.get("ok") else 1

def run_speed(s, reps, tests):
    """P4k / P32k+D32k / D0, reps each. Returns per-rep lists."""
    out = {t:[] for t in tests}
    for r in range(reps):
        if "p4k" in tests:
            out["p4k"].append(chat(corpus("p4k"), 64, nonce=f"p4k-{r}"))
        if "p32" in tests:
            out["p32"].append(chat(corpus("p32k"), 1400, nonce=f"p32-{r}"))
        if "d0" in tests:
            out["d0"].append(chat(D0_PROMPT, 1400, nonce=f"d0-{r}"))
        print(f"  rep {r+1}/{reps} done", flush=True)
    return out

def summarize(out):
    sm = {}
    if out.get("p4k"):
        sm["P4k_ps"], sm["P4k_sd"] = mean_sd([x["prompt_ps"] for x in out["p4k"]])
        sm["P4k_n"] = out["p4k"][0]["prompt_n"]
    if out.get("p32"):
        sm["P32k_ps"], sm["P32k_sd"] = mean_sd([x["prompt_ps"] for x in out["p32"]])
        sm["TTFT32k_s"], sm["TTFT32k_sd"] = mean_sd([x["prompt_ms"]/1000 for x in out["p32"]])
        sm["D32k_ps"], sm["D32k_sd"] = mean_sd([x["predicted_ps"] for x in out["p32"]])
        sm["P32k_n"] = out["p32"][0]["prompt_n"]
        sm["D32k_predicted_n"] = [x["predicted_n"] for x in out["p32"]]
    if out.get("d0"):
        sm["D0_ps"], sm["D0_sd"] = mean_sd([x["predicted_ps"] for x in out["d0"]])
        sm["D0_predicted_n"] = [x["predicted_n"] for x in out["d0"]]
    if sm.get("TTFT32k_s") and sm.get("D32k_ps"):
        sm["T_turn_s"] = round(sm["TTFT32k_s"] + 1500.0/sm["D32k_ps"], 3)
        # sd of T_turn by first-order propagation
        dsd = sm.get("D32k_sd") or 0.0
        sm["T_turn_sd"] = round(((sm.get("TTFT32k_sd") or 0.0)**2
                                 + (1500.0*dsd/sm["D32k_ps"]**2)**2)**0.5, 3)
    return sm

def cmd_bench(a):
    tests = a.tests.split(",")
    s = Server(a.label, a.spec, a.model)
    row = {"kind":"bench","model":a.model,"label":a.label,"spec":a.spec,"cmd":" ".join(s.cmd),
           "reps":a.reps,"tests":tests}
    try:
        s.start(timeout=a.timeout)
        row.update({"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram,
                    "mem_avail_after_load_kb":s.mem_load,"rss_load":s.rss_load,
                    "graphs_reused":s.graphs_reused()})
        print(f"loaded in {s.load_s:.0f}s, vram {s.load_vram} MiB", flush=True)
        # discarded warm-up (page cache + CUDA graph warm)
        w = chat(corpus("p4k"), 32, nonce="warmup")
        row["warmup_prompt_n"] = w["prompt_n"]
        out = run_speed(s, a.reps, tests)
        row["runs"] = out
        row["summary"] = summarize(out)
        row["peak_vram_reps_mib"] = s.peak
        if a.full:
            print("FULL in the same load", flush=True)
            row["full"] = full_on(s, 128)
            print(json.dumps({k:row["full"].get(k) for k in ("FULL_prompt_n","FULL_prefill_ps",
                  "FULL_TTFT_s","FULL_decode_ps","retrieved","needles_ok","finish_ok")}), flush=True)
        bu, bf = board()
        row.update({"peak_vram_mib":s.peak,"board_used_mib":bu,"board_free_mib":bf,
                    "mem_avail_end_kb":mem_avail_kb(),"ok":True})
        print(json.dumps(row["summary"], indent=2), flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:2000]})
        print("BENCH FAIL:", str(e)[:600], flush=True)
    finally:
        if not a.keep:
            try: s.kill()
            except Exception: pass
    record(row)
    mark_done(a.label, {"T_turn": (row.get("summary") or {}).get("T_turn_s"),
                        "ok": row.get("ok"), "kind":"bench"})
    return 0 if row.get("ok") else 1

FULL_Q = ("Three AUDIT_MARKER lines are hidden in the source above, tagged EARLY, MID and "
          "LATE. Report each calibration_code exactly.\n"
          "Answer on three lines, nothing else:\nEARLY=<code>\nMID=<code>\nLATE=<code>")

def full_on(s, window):
    """FULL needle test on an already-running server (no extra warm-up)."""
    base = corpus("full256" if window == 256 else "full128")
    text, ans = needle_text(base, {"early":0.10, "mid":0.50, "late":0.90})
    r = chat(text + "\n\n" + FULL_Q, 4000, nonce="full")
    got = {}
    for tag in ans:
        m = re.search(rf"{tag.upper()}\s*=\s*([0-9]{{7}})", r["content"] or "")
        got[tag] = m.group(1) if m else None
    r.pop("content", None)
    return {"run":r, "needles":ans, "retrieved":got,
            "needles_ok": all(got[t]==ans[t] for t in ans),
            "finish_ok": r["finish_reason"]=="stop",
            "FULL_prefill_ps": r["prompt_ps"], "FULL_TTFT_s": (r["prompt_ms"] or 0)/1000,
            "FULL_decode_ps": r["predicted_ps"], "FULL_prompt_n": r["prompt_n"],
            "peak_vram_after_full_mib": s.peak}

def cmd_full(a):
    base = corpus("full256" if a.window == 256 else "full128")
    text, ans = needle_text(base, {"early":0.10, "mid":0.50, "late":0.90})
    s = Server(a.label, a.spec, a.model)
    row = {"kind":"full","model":a.model,"label":a.label,"spec":a.spec,"cmd":" ".join(s.cmd),
           "window":a.window,"needles":ans}
    try:
        s.start(timeout=a.timeout)
        row.update({"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram,
                    "mem_avail_after_load_kb":s.mem_load})
        print(f"loaded {s.load_vram} MiB; full prompt going in", flush=True)
        chat(corpus("p4k"), 32, nonce="warmup")      # discarded warm-up
        r = chat(text + "\n\n" + FULL_Q, 4000, nonce="full")
        got = {}
        for tag in ans:
            m = re.search(rf"{tag.upper()}\s*=\s*([0-9]{{7}})", r["content"] or "")
            got[tag] = m.group(1) if m else None
        row.update({"run":r, "retrieved":got,
                    "needles_ok": all(got[t]==ans[t] for t in ans),
                    "finish_ok": r["finish_reason"]=="stop",
                    "FULL_prefill_ps": r["prompt_ps"], "FULL_TTFT_s": (r["prompt_ms"] or 0)/1000,
                    "FULL_decode_ps": r["predicted_ps"], "FULL_prompt_n": r["prompt_n"],
                    "peak_vram_mib": s.peak, "mem_avail_end_kb": mem_avail_kb(), "ok":True})
        bu, bf = board(); row["board_used_mib"], row["board_free_mib"] = bu, bf
        print(json.dumps({k:row[k] for k in ("FULL_prompt_n","FULL_prefill_ps","FULL_TTFT_s",
              "FULL_decode_ps","peak_vram_mib","retrieved","needles_ok","finish_ok")}, indent=2),
              flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:2000]})
        print("FULL FAIL:", str(e)[:600], flush=True)
    finally:
        if not a.keep:
            try: s.kill()
            except Exception: pass
    record(row)
    mark_done(a.label, {"kind":"full","ok":row.get("ok"),"peak":row.get("peak_vram_mib"),
                        "needles_ok":row.get("needles_ok")})
    return 0 if row.get("ok") else 1

def cmd_reuse(a):
    """Phase E: 60k turn, then a +500 token follow-up on the same conversation."""
    pool = corpus("full128")
    # cut to ~60k tokens
    s = Server(a.label, a.spec, a.model)
    row = {"kind":"reuse","model":a.model,"label":a.label,"spec":a.spec,"cmd":" ".join(s.cmd)}
    try:
        s.start(timeout=a.timeout)
        lo, hi, cut = 0, len(pool), len(pool)
        while lo < hi:
            mid=(lo+hi)//2
            if ntok(pool[:mid]) < 60000: lo=mid+1
            else: hi=mid; cut=mid
        first = pool[:cut]
        n1 = ntok(first); row["first_tokens"] = n1
        chat(corpus("p4k"), 32, nonce="warmup")
        m1 = {"role":"user","content":first+"\n\nSummarise the role of the first file in one sentence."}
        p1 = {"messages":[m1],"max_tokens":600,"temperature":0.3,"seed":SEED,"cache_prompt":True}
        t0=time.time(); r1 = post("/v1/chat/completions", p1, timeout=5400); w1=time.time()-t0
        a1 = r1["choices"][0]["message"]
        t1 = r1.get("timings",{})
        filler = "\n".join(f"// follow-up context line {i} varying text {i*7919}" for i in range(120))
        m3 = {"role":"user","content":filler+"\n\nNow name the second file. One line."}
        p2 = {"messages":[m1,{"role":"assistant","content":a1.get("content") or "ok"},m3],
              "max_tokens":600,"temperature":0.3,"seed":SEED,"cache_prompt":True}
        t0=time.time(); r2 = post("/v1/chat/completions", p2, timeout=5400); w2=time.time()-t0
        t2 = r2.get("timings",{})
        row.update({"turn1":{"prompt_n":t1.get("prompt_n"),"prompt_ms":t1.get("prompt_ms"),
                             "prompt_ps":t1.get("prompt_per_second"),"wall_s":round(w1,2)},
                    "turn2":{"prompt_n":t2.get("prompt_n"),"prompt_ms":t2.get("prompt_ms"),
                             "prompt_ps":t2.get("prompt_per_second"),"wall_s":round(w2,2)},
                    "reuse_ratio": (t2.get("prompt_n") or 0)/max(1,(t1.get("prompt_n") or 1)),
                    "peak_vram_mib":s.peak,"ok":True})
        print(json.dumps({"turn1":row["turn1"],"turn2":row["turn2"],
                          "reuse_ratio":round(row["reuse_ratio"],4)}, indent=2), flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:2000]}); print("REUSE FAIL:",str(e)[:600],flush=True)
    finally:
        if not a.keep:
            try: s.kill()
            except Exception: pass
    record(row)
    return 0 if row.get("ok") else 1

def cmd_fullprobe(a):
    """Cheap VRAM instrument: drive the full window with prefill only (max_tokens 16).
    Records peak VRAM and, on OOM, how far the prefill actually got."""
    base = corpus("full256" if a.window == 256 else "full128")
    s = Server(a.label, a.spec, a.model)
    row = {"kind":"fullprobe","model":a.model,"label":a.label,"spec":a.spec,"cmd":" ".join(s.cmd),"window":a.window}
    try:
        s.start(timeout=a.timeout)
        row.update({"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram})
        print(f"loaded {s.load_vram} MiB; prefill probe", flush=True)
        chat(corpus("p4k"), 32, nonce="warmup")
        try:
            r = chat(base, 16, nonce="probe")
            row.update({"run":r,"reached":r["prompt_n"],"completed":True,
                        "FULL_prefill_ps":r["prompt_ps"],"FULL_TTFT_s":(r["prompt_ms"] or 0)/1000})
        except Exception as e:
            row.update({"completed":False,"req_error":str(e)[:300]})
        log = open(s.log).read()
        m = re.findall(r"n_tokens =\s*(\d+), progress", log)
        row["max_tokens_seen"] = int(m[-1]) if m else None
        o = re.findall(r"allocating ([0-9.]+) MiB on device 0: cudaMalloc failed", log)
        row["oom_alloc_mib"] = float(o[-1]) if o else None
        row.update({"peak_vram_mib":s.peak,"mem_avail_end_kb":mem_avail_kb(),
                    "ok":bool(row.get("completed"))})
        print(json.dumps({k:row.get(k) for k in ("load_vram_mib","peak_vram_mib","completed",
              "reached","max_tokens_seen","oom_alloc_mib","FULL_prefill_ps")}, indent=2), flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:2000]}); print("PROBE FAIL:",str(e)[:400],flush=True)
    finally:
        if not a.keep:
            try: s.kill()
            except Exception: pass
    record(row)
    return 0 if row.get("ok") else 1

# ================================================================ v2 additions
COLD_LENS = [300, 508, 777, 1016, 1500, 2044, 3000, 4061]
COLD_DIR  = os.path.join(CORPUS, "cold")
SESSION_F = os.path.join(CORPUS, "session.json")
PROMPT_B  = "/mnt/ai/evals/harness/prompt_B.txt"

def raw_prose(nbytes):
    """Real prose: llama.cpp docs/READMEs (read-only), skipping agent/instruction files."""
    skip = ("AGENTS.md","CLAUDE.md","/skills/","/vendor/",".github")
    files = sh(f'find {SRC_ROOT} -name "*.md" -size +3k -printf "%p\\n" | sort').splitlines()
    out, tot = [], 0
    for path in files:
        if any(k in path for k in skip): continue
        try: t = open(path, encoding="utf-8", errors="ignore").read()
        except Exception: continue
        out.append(f"\n\n# {os.path.basename(path)}\n{t}"); tot += len(out[-1])
        if tot >= nbytes: break
    return "".join(out)

def _looks_real(t):
    """Reject hex dumps, data tables and preprocessed headers: not what OpenCode sends."""
    lines = [l for l in t.splitlines() if l.strip()] or [""]
    tab = sum(l.lstrip().startswith("|") for l in lines) / len(lines)
    hexr = t.count("0x") / max(1, len(t)) * 100
    pre = sum(l.startswith("# ") and l[2:3].isdigit() for l in lines) / len(lines)
    return tab < 0.15 and hexr < 0.3 and pre < 0.05

def curated_source():
    """Hand-written C/C++ of the fork (read-only): llama core, common, server."""
    D = SRC_ROOT
    pat = r'\( -name "*.cpp" -o -name "*.h" \)'
    files = sh(f'find {D}/src {D}/common {D}/tools/server -maxdepth 1 {pat} -size +4k -printf "%p\\n" | sort').splitlines()
    out = []
    for path in files:
        if "unicode-data" in path: continue
        t = open(path, encoding="utf-8", errors="ignore").read()
        if _looks_real(t): out.append(f"\n\n// ===== FILE: {path} =====\n{t}")
    return "".join(out)

def curated_prose():
    D = SRC_ROOT
    files = sh(f'find {D}/docs {D}/tools/server {D}/README.md -maxdepth 1 -name "*.md" -size +3k -printf "%p\\n" | sort').splitlines()
    out = []
    for path in files:
        if any(k in path for k in ("AGENTS.md","CLAUDE.md")): continue
        t = open(path, encoding="utf-8", errors="ignore").read()
        if _looks_real(t): out.append(f"\n\n# {os.path.basename(path)}\n{t}")
    return "".join(out)

def templated_n(messages):
    """Exact prompt tokens the server will prefill for this conversation."""
    prompt = post("/apply-template", {"messages": messages}, timeout=600)["prompt"]
    return len(post("/tokenize", {"content": prompt, "add_special": True,
                                  "parse_special": True}, timeout=600)["tokens"])

def fit_exact(text, target, wrap):
    """Prefix of text such that templated_n(wrap(prefix)) == target exactly."""
    n_of = lambda cut: templated_n(wrap(text[:cut]))
    lo, hi = 0, min(len(text), target*8)
    while lo < hi:
        mid = (lo+hi)//2
        if n_of(mid) < target: lo = mid+1
        else: hi = mid
    for d in range(0, 30):
        for cut in (lo-d, lo+d):
            if 0 < cut <= len(text) and n_of(cut) == target: return text[:cut]
    raise RuntimeError(f"cannot hit {target} exactly")

def build_cold():
    """Needs a server on :9997. Alternates prose / source so both content kinds are covered."""
    os.makedirs(COLD_DIR, exist_ok=True)
    src = curated_source()[1_200_000:]          # session corpus uses the first 1.2 MB
    prose = curated_prose()
    off = 0
    for i, L in enumerate(COLD_LENS):
        kind = "prose" if i % 2 == 0 else "source"
        pool = (prose if kind == "prose" else src)[off:]
        q = ("Read the following and summarise its purpose in three sentences."
             if kind == "prose" else "Review the following code and name its riskiest function.")
        wrap = lambda t, q=q: [{"role":"user","content": f"{q}\n\n{t}"}]
        for shift in range(40):          # token count can jump by 2 at a cut; shift start a line
            try: t = fit_exact(pool, L, wrap); break
            except RuntimeError:
                nl = pool.find("\n", 1); pool = pool[nl+1:]; off += nl+1
        else: raise RuntimeError(f"cold {L}: no exact fit")
        msgs = wrap(t)
        json.dump({"target":L, "kind":kind, "n":templated_n(msgs), "messages":msgs},
                  open(os.path.join(COLD_DIR, f"{L}.json"), "w"))
        print(f"cold {L}: {kind} {len(t)} bytes -> {templated_n(msgs)} templated tokens", flush=True)
        off += len(t) + 1000
    pb = [{"role":"user","content": open(PROMPT_B).read()}]
    json.dump({"target":None, "kind":"prompt_B", "n":templated_n(pb), "messages":pb},
              open(os.path.join(COLD_DIR, "B.json"), "w"))
    print("prompt_B templated tokens:", templated_n(pb), flush=True)

SESSION_QS = [
    "Which function in the code just added is the most complex, and why?",
    "Is there any resource that the newly added code could leak? Point to the line.",
    "Summarise how the new code handles errors.",
    "What would you rename in the new code to make it clearer?",
    "Which part of the new code would you unit-test first, and with what inputs?",
]

def build_session():
    """Turn 1 = 20k tokens of real source, turns 2..16 = ~3k tokens each (raw-token counts)."""
    pool = curated_source()
    def cut_tokens(off, want):
        lo, hi = off, min(len(pool), off + want*8)
        while lo < hi:
            mid = (lo+hi)//2
            if ntok(pool[off:mid]) < want: lo = mid+1
            else: hi = mid
        return lo
    turns, off = [], 0
    for k, want in enumerate([20000] + [3000]*15):
        end = cut_tokens(off, want)
        txt = pool[off:end]; off = end
        q = ("Here is the source of the module we are working on. Read it; I will add more "
             "files next. " if k == 0 else f"Here is the next file. ") + SESSION_QS[k % len(SESSION_QS)]
        turns.append({"text": txt, "q": q, "raw_tokens": ntok(txt)})
        print(f"turn {k+1}: {turns[-1]['raw_tokens']} tokens", flush=True)
    json.dump(turns, open(SESSION_F, "w"))

def cmd_session(a):
    turns = json.load(open(SESSION_F))
    spec = (a.spec + " " + a.extra).strip()
    s = Server(a.label, spec, a.model)
    row = {"kind":"session","model":a.model,"label":a.label,"spec":spec,"cmd":" ".join(s.cmd),
           "gen_cap":a.gen}
    try:
        s.start(timeout=a.timeout)
        row.update({"load_s":round(s.load_s,1),"load_vram_mib":s.load_vram,
                    "mem_avail_after_load_kb":s.mem_load})
        print(f"loaded {s.load_vram} MiB, MemAvail {s.mem_load//1024} MiB", flush=True)
        chat(corpus("p4k"), 32, nonce="warmup")                 # discarded warm-up
        msgs, per, reuse_broken = [], [], []
        for k, t in enumerate(turns):
            msgs.append({"role":"user","content": t["text"] + "\n\n" + t["q"]})
            payload = {"messages":msgs, "max_tokens":a.gen, "temperature":0.3, "top_p":0.95,
                       "top_k":20, "seed":SEED, "cache_prompt":True, "stream":False}
            t0 = time.time(); r = post("/v1/chat/completions", payload, timeout=5400)
            wall = time.time()-t0
            ch = r["choices"][0]; m = ch.get("message",{}) or {}; tm = r.get("timings",{}) or {}
            content = m.get("content") or ""; reasoning = m.get("reasoning_content") or ""
            amsg = {"role":"assistant","content":content}
            if reasoning: amsg["reasoning_content"] = reasoning
            msgs.append(amsg)
            prev_gen = per[-1]["predicted_n"] if per else 0
            appended = t["raw_tokens"] + (prev_gen or 0)
            rec = {"turn":k+1, "prompt_n":tm.get("prompt_n"), "ttft_s":round((tm.get("prompt_ms") or 0)/1000,3),
                   "prompt_ps":tm.get("prompt_per_second"), "predicted_n":tm.get("predicted_n"),
                   "decode_ps":tm.get("predicted_per_second"), "finish_reason":ch.get("finish_reason"),
                   "content_len":len(content), "reasoning_len":len(reasoning),
                   "depth": (r.get("usage") or {}).get("total_tokens"),
                   "appended_est":appended, "wall_s":round(wall,2), "peak_mib":s.peak}
            if k > 0 and (rec["prompt_n"] or 0) > 2*appended + 1000:
                rec["reuse_broken"] = True; reuse_broken.append(k+1)
            per.append(rec)
            print(json.dumps(rec), flush=True)
        ttft = sum(x["ttft_s"] for x in per)
        dec  = sum(1500.0/x["decode_ps"] for x in per if x["decode_ps"])
        row.update({"turns":per, "sum_ttft_s":round(ttft,2), "sum_decode_s":round(dec,2),
                    "session_s":round(ttft+dec,2), "last_depth":per[-1]["depth"],
                    "last_decode_ps":per[-1]["decode_ps"], "reuse_broken_turns":reuse_broken,
                    "peak_vram_mib":s.peak, "mem_avail_end_kb":mem_avail_kb(),
                    "graphs_reused":s.graphs_reused(), "ok":True})
        print(json.dumps({k:row[k] for k in ("session_s","sum_ttft_s","sum_decode_s","last_depth",
              "last_decode_ps","reuse_broken_turns","peak_vram_mib")}), flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:2000]}); print("SESSION FAIL:",str(e)[:600],flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    record(row)
    mark_done(a.label, {"kind":"session","ok":row.get("ok"),"session_s":row.get("session_s")})
    return 0 if row.get("ok") else 1

def crash_in_log(path):
    try: t = open(path).read()
    except Exception: return None
    m = re.search(r"(CUDA error[^\n]*|illegal memory access[^\n]*|GGML_ASSERT[^\n]*|Segmentation fault)", t)
    return m.group(1) if m else None

def cmd_cold(a):
    items = [str(x) for x in COLD_LENS] + ["B1","B2","B3"] if a.which == "all" else a.which.split(",")
    results, fails = [], 0
    for it in items:
        f = os.path.join(COLD_DIR, ("B" if it.startswith("B") else it) + ".json")
        spec = json.load(open(f))
        lab = f"{a.label}-cold-{it}"
        s = Server(lab, a.spec, a.model)
        rec = {"item":it, "target":spec["target"], "templated_n":spec["n"], "kind":spec["kind"]}
        try:
            s.start(timeout=a.timeout)
            rec["load_vram_mib"] = s.load_vram; rec["mem_avail_kb"] = s.mem_load
            payload = {"messages":spec["messages"], "max_tokens":300, "temperature":0.3,
                       "top_p":0.95, "top_k":20, "seed":SEED, "cache_prompt":False, "stream":False}
            try:
                r = post("/v1/chat/completions", payload, timeout=1200)
                tm = r.get("timings",{}) or {}
                rec.update({"prompt_n":tm.get("prompt_n"), "finish_reason":r["choices"][0].get("finish_reason"),
                            "predicted_n":tm.get("predicted_n")})
            except Exception as e:
                rec["req_error"] = str(e)[:300]
            time.sleep(2)
            alive = s.proc.poll() is None
            crash = crash_in_log(s.log)
            rec.update({"alive_after":alive, "crash":crash})
            rec["ok"] = alive and not crash and "req_error" not in rec
        except Exception as e:
            rec.update({"ok":False, "start_error":str(e)[:600]})
        finally:
            try: s.kill()
            except Exception: pass
        if not rec["ok"]: fails += 1
        results.append(rec); print(json.dumps(rec), flush=True)
    row = {"kind":"cold","model":a.model,"label":a.label,"spec":a.spec,"items":results,
           "passed":sum(1 for r in results if r["ok"]), "total":len(results), "ok": fails == 0}
    record(row)
    mark_done(a.label, {"kind":"cold","ok":row["ok"],"passed":row["passed"],"total":row["total"]})
    print(f"COLD {a.label}: {row['passed']}/{row['total']}", flush=True)
    return 0 if row["ok"] else 1

def cmd_task02(a):
    sys.path.insert(0, ROOT); import task02
    s = Server(a.label, a.spec, a.model)
    row = {"kind":"task02","model":a.model,"label":a.label,"spec":a.spec,"cmd":" ".join(s.cmd)}
    try:
        s.start(timeout=a.timeout)                              # cold: NO warm-up
        row.update({"load_vram_mib":s.load_vram, "mem_avail_after_load_kb":s.mem_load})
        outdir = os.path.join(ROOT, "runs", f"task02-{a.label}")
        meta, side = task02.run(a.label, outdir, max_tokens=a.max_tokens)
        row["meta"] = meta
        row["alive_after"] = s.proc.poll() is None; row["crash"] = crash_in_log(s.log)
        if meta["files_missing"]:
            row.update({"scored":False, "ok":False})
        else:
            res, out = task02.score(outdir, side)
            row.update({"scored":True, "probes":res,
                        "gate4_pass": all(res[f"probe{n}"]=="PASS" for n in (1,2,3,5)), "ok":True})
        row["peak_vram_mib"] = s.peak
        print(json.dumps({k:row.get(k) for k in ("meta","probes","gate4_pass","crash")}, indent=2), flush=True)
    except Exception as e:
        row.update({"ok":False,"error":str(e)[:2000], "crash":crash_in_log(s.log)})
        print("TASK02 FAIL:", str(e)[:600], flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    record(row)
    mark_done(a.label, {"kind":"task02","ok":row.get("ok"),"gate4":row.get("gate4_pass")})
    return 0 if row.get("ok") else 1

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("corpus","load","bench","full","fullprobe","reuse",
                 "session","cold","task02","mkcold","mksession"):
        p = sub.add_parser(name)
        if name not in ("corpus","mkcold","mksession"):
            p.add_argument("--label", required=True); p.add_argument("--spec", required=True)
            p.add_argument("--timeout", type=int, default=1500)
            p.add_argument("--keep", action="store_true")
        if name not in ("corpus","mkcold","mksession"):
            p.add_argument("--model", choices=["q2","iq3"], default="q2")
        if name == "bench":
            p.add_argument("--full", action="store_true")
            p.add_argument("--reps", type=int, default=3)
            p.add_argument("--tests", default="p4k,p32,d0")
        if name in ("full","fullprobe"):
            p.add_argument("--window", type=int, default=128)
        if name == "session":
            p.add_argument("--gen", type=int, default=800)
            p.add_argument("--extra", default="", help="extra server args, e.g. --reasoning-preserve")
        if name == "cold":
            p.add_argument("--which", default="all", help="comma list of lengths and/or B1,B2,B3")
        if name == "task02":
            p.add_argument("--max-tokens", type=int, default=60000)
    a = ap.parse_args()
    if a.cmd == "corpus": build_corpus(); return 0
    if a.cmd == "mkcold": build_cold(); return 0
    if a.cmd == "mksession": build_session(); return 0
    return {"load":cmd_load,"bench":cmd_bench,"full":cmd_full,
            "fullprobe":cmd_fullprobe,"reuse":cmd_reuse,"session":cmd_session,
            "cold":cmd_cold,"task02":cmd_task02}[a.cmd](a)

if __name__ == "__main__":
    sys.exit(main())
