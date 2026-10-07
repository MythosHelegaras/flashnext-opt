#!/usr/bin/env python3
"""v3: Task 02 Prompt B with per-request sampling, /slots verification, token split,
NOTIFIER placement analysis. Clean-room rules as task02.py (v2): run dir created EMPTY,
prompt and probe.py live outside it, probe.py copied in only at score time."""
import ast, json, os, re, shutil, subprocess, sys, threading, time, urllib.request

import task02                                   # v2: extract(), FILES, HARNESS
BASE = "http://127.0.0.1:9997"
HARNESS = task02.HARNESS
FILES = task02.FILES

def post(path, payload, timeout=5400):
    req = urllib.request.Request(BASE+path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode())

def get(path, timeout=10):
    with urllib.request.urlopen(BASE+path, timeout=timeout) as r: return json.loads(r.read().decode())

def ntok(text):
    if not text: return 0
    return len(post("/tokenize", {"content": text}, timeout=600)["tokens"])

def extract(text):
    """v3 extractor (W9). v2's extract() keeps the FIRST block mapped to a name, so a short
    usage snippet that precedes the real file steals the name. Here: each block gets a name
    (filename comment inside, else nearest preceding mention); among candidates for a name,
    prefer one whose nearest preceding non-blank line is a heading/label naming the file,
    then the longest."""
    cands = {}
    for m in re.finditer(r"```([A-Za-z0-9_+-]*)\n(.*?)```", text, re.S):
        body = m.group(2)
        if not body.strip(): continue
        name = None
        mm = re.search(r"#\s*(?:file:\s*)?([a-z_]+\.py)", body[:200])
        if mm and mm.group(1) in FILES: name = mm.group(1)
        head = text[:m.start()]
        if name is None:
            best = -1
            for f in FILES:
                i = head.rfind(f)
                if i > best: best, name = i, f
            if best == -1: continue
        prev = [l for l in head.splitlines() if l.strip()]
        headed = bool(prev) and name in prev[-1] and len(prev[-1]) < 120
        cands.setdefault(name, []).append((headed, len(body), body))
    return {n: max(c, key=lambda x: (x[0], x[1]))[2] for n, c in cands.items()}

SAMPLING_KEYS = ("temperature", "top_p", "top_k", "min_p", "seed")

def slot_params():
    s = get("/slots")
    s = s[0] if isinstance(s, list) else s
    p = s.get("params", {}) or {}
    return {k: p.get(k) for k in SAMPLING_KEYS} | {"is_processing": s.get("is_processing")}

def matches(got, want):
    bad = {}
    for k, v in want.items():
        g = got.get(k)
        if g is None or abs(float(g) - float(v)) > 1e-4: bad[k] = (g, v)
    return bad

def run(label, outdir, sampling, expect, max_tokens=60000, abort=None):
    """sampling: request params. expect: effective values /slots must show.
    abort(): callback that kills the server if /slots mismatches mid-request."""
    os.makedirs(outdir, exist_ok=True)
    assert not os.listdir(outdir), f"{outdir} must start empty (contamination rule)"
    prompt = open(f"{HARNESS}/prompt_B.txt").read()
    slots = {"during": None, "after": None, "mismatch": None}

    def watch():
        for _ in range(30):                     # first read ~30 s in, while in flight
            time.sleep(10 if slots["during"] is None else 0)
            try:
                p = slot_params()
                if p.get("is_processing"):
                    slots["during"] = p; break
            except Exception as e:
                slots["during_err"] = str(e)
        if slots["during"] is not None:
            bad = matches(slots["during"], expect)
            if bad:
                slots["mismatch"] = bad
                print("SLOTS MISMATCH -> void, aborting:", bad, flush=True)
                if abort: abort()
    th = threading.Thread(target=watch, daemon=True); th.start()

    payload = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
               **sampling, "cache_prompt": False, "stream": False}
    t0 = time.time()
    r = post("/v1/chat/completions", payload)
    wall = time.time() - t0
    th.join(timeout=5)
    try: slots["after"] = slot_params()
    except Exception as e: slots["after_err"] = str(e)
    if slots["after"] is not None and slots["mismatch"] is None:
        bad = matches(slots["after"], expect)
        if bad: slots["mismatch"] = bad

    ch = r["choices"][0]; msg = ch.get("message", {}) or {}
    content = msg.get("content") or ""; reasoning = msg.get("reasoning_content") or ""
    tm = r.get("timings", {}) or {}
    meta = {"label": label, "request_sampling": sampling, "slots": slots,
            "sampling_ok": slots["mismatch"] is None and slots["during"] is not None,
            "wall_s": round(wall, 1), "finish_reason": ch.get("finish_reason"),
            "content_len": len(content), "reasoning_len": len(reasoning),
            "prompt_n": tm.get("prompt_n"), "predicted_n": tm.get("predicted_n"),
            "predicted_ps": tm.get("predicted_per_second"), "prompt_ms": tm.get("prompt_ms"),
            "predicted_ms": tm.get("predicted_ms"),
            "reasoning_tok": ntok(reasoning), "content_tok": ntok(content), "usage": r.get("usage")}
    files = extract(content)
    meta["files_found"] = sorted(files); meta["files_missing"] = [f for f in FILES if f not in files]
    for name, body in files.items():
        open(os.path.join(outdir, name), "w").write(body)
    side = outdir.rstrip("/") + ".meta"
    os.makedirs(side, exist_ok=True)
    open(f"{side}/response.md", "w").write(content)
    open(f"{side}/reasoning.txt", "w").write(reasoning)
    json.dump(r, open(f"{side}/raw.json", "w"))
    json.dump(meta, open(f"{side}/meta.json", "w"), indent=2)
    return meta, side

def score(outdir, side, probe_src=None, outname="probe.out"):
    shutil.copy(probe_src or f"{HARNESS}/probe.py", os.path.join(outdir, "probe.py"))
    p = subprocess.run([sys.executable, "probe.py"], cwd=outdir, capture_output=True, text=True, timeout=300)
    out = p.stdout + ("\n[stderr]\n" + p.stderr if p.stderr.strip() else "")
    open(f"{side}/{outname}", "w").write(out)
    res = {}
    for n in (1, 2, 3, 5):
        m = re.search(rf"PROBE {n} .*?-> *(PASS|FAIL)", out)
        if m is None:
            m2 = re.search(rf"PROBE {n} .*?(PASS|FAIL)", out)
            res[f"probe{n}"] = m2.group(1) if m2 else "NO_OUTPUT"
        else: res[f"probe{n}"] = m.group(1)
    p4 = re.findall(r"PROBE 4 \(threshold=(-?\d)\):\s*(.*?)(?=\nPROBE|\Z)", out, re.S)
    res["probe4"] = {t: ("trips (crit 7 FAIL, control)" if "tripped" in s else
                         ("raises" if "raised" in s else (s.strip()[:80] or "no trip")))
                     for t, s in p4} or "NO_OUTPUT"
    err = re.search(r"(\w+Error: .*)", p.stderr)
    res["error"] = err.group(1)[:200] if err else None
    res["gate4"] = all(res[f"probe{n}"] == "PASS" for n in (1, 2, 3, 5))
    return res, out

def diag_score(outdir, side):
    """Diagnostic only (v2 V19): also inject circuit_breaker.NOTIFIER. Never the gate."""
    d = outdir.rstrip("/") + ".diag"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(outdir, d, ignore=shutil.ignore_patterns("probe.py", "__pycache__"))
    src = open(f"{HARNESS}/probe.py").read()
    src = re.sub(r"breaker_events\.NOTIFIER = ", "breaker_events.NOTIFIER = cb.NOTIFIER = ", src)
    pth = os.path.join(side, "probe_diag.py"); open(pth, "w").write(src)
    return score(d, side, probe_src=pth, outname="probe_diag.out")

def notifier_map(outdir):
    """Where NOTIFIER is bound and how it is read, per module (AST)."""
    rep = {"bound": [], "annot_only": [], "read": [], "imported": [], "raw": []}
    for f in FILES:
        path = os.path.join(outdir, f); mod = f[:-3]
        if not os.path.exists(path): continue
        src = open(path).read()
        for i, line in enumerate(src.splitlines(), 1):
            if "NOTIFIER" in line: rep["raw"].append(f"{mod}:{i}: {line.strip()[:120]}")
        try: tree = ast.parse(src)
        except SyntaxError as e:
            rep["raw"].append(f"{mod}: SyntaxError {e}"); continue
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "NOTIFIER":
                (rep["bound"] if node.value is not None else rep["annot_only"]).append(f"{mod}:{node.lineno}")
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "NOTIFIER": rep["bound"].append(f"{mod}:{node.lineno}")
                    if isinstance(t, ast.Attribute) and t.attr == "NOTIFIER":
                        rep["bound"].append(f"{mod}:{node.lineno} ({ast.unparse(t)})")
            elif isinstance(node, ast.ImportFrom) and any(a.name == "NOTIFIER" for a in node.names):
                rep["imported"].append(f"{mod}:{node.lineno} from {node.module}")
            elif isinstance(node, ast.Name) and node.id == "NOTIFIER" and isinstance(node.ctx, ast.Load):
                rep["read"].append(f"{mod}:{node.lineno} bare")
            elif isinstance(node, ast.Attribute) and node.attr == "NOTIFIER" and isinstance(node.ctx, ast.Load):
                rep["read"].append(f"{mod}:{node.lineno} {ast.unparse(node)}")
            elif (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "getattr"
                  and any(isinstance(a, ast.Constant) and a.value == "NOTIFIER" for a in node.args)):
                rep["read"].append(f"{mod}:{node.lineno} {ast.unparse(node)[:80]}")
    bm = sorted({b.split(":")[0] for b in rep["bound"] if "(" not in b})
    rm = sorted({r.split(":")[0] + ("→" + r.split(" ", 1)[1] if " " in r and "bare" not in r else "(bare)")
                 for r in rep["read"]})
    rep["summary"] = (f"bound in {','.join(bm) or 'NONE'}"
                      + (f"; annotation-only in {','.join(sorted({a.split(':')[0] for a in rep['annot_only']}))}" if rep["annot_only"] else "")
                      + (f"; from-import in {','.join(sorted({a.split(':')[0] for a in rep['imported']}))}" if rep["imported"] else "")
                      + f"; read: {', '.join(rm) or 'NONE'}")
    return rep

if __name__ == "__main__":                       # offline: NOTIFIER map of an existing run dir
    print(json.dumps(notifier_map(sys.argv[1]), indent=2))
