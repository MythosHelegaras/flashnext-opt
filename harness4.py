#!/usr/bin/env python3
"""v4 harness: engine decision (F = fork, M = mainline). Thin wrapper over harness2.py so the
v2 methodology (corpus, nonces, seed, session, cold, FULL) is byte-identical.

Adds, per run:
  --engine F|M        binary
  --rot on|off        LLAMA_ATTN_ROT_DISABLE=1 set (on) or absent (off)
  --ple ot|lazy|none  per_layer_token_embd handling: -ot ...=CPU (v2), --lazy-mode on, or nothing
  --fitoff            append --fit off (M only; M defaults to --fit on)
Subcommands: load, bench, session, cold, task02, sanity (500-token probe), full (window 128/256)

Usage examples:
  harness4.py bench   --engine F --label v4-A-F --spec "$SPEC" --full
  harness4.py session --engine F --label v4-A-F-session --spec "$SPEC"
"""
import argparse, json, os, re, subprocess, sys, time
ROOT = os.path.expanduser("~/flashnext-opt"); sys.path.insert(0, ROOT)
import harness2 as H

BINS = {"F": "/opt/llama.cpp-qwen4exp/bin/llama-server",
        "M": "/opt/llama.cpp-flashnext/build/bin/llama-server"}
H.RESULTS = os.path.join(ROOT, "results-v4.jsonl")
H.STATE   = os.path.join(ROOT, "state-v4.json")
BASE_MANDATORY = ["-ngl", "999", "-fa", "on", "-np", "1", "--jinja"]
PLE = {"ot": ["-ot", "per_layer_token_embd=CPU"], "lazy": ["--lazy-mode", "on"], "none": []}
OPT = {"engine": "F", "rot": "on", "ple": "ot", "fitoff": False, "nongl": False}

def git_sha(engine):
    d = "/opt/llama.cpp-qwen4exp" if engine == "F" else "/opt/llama.cpp-flashnext"
    return H.sh(f"git -C {d} rev-parse --short=10 HEAD")

class Server4(H.Server):
    """Same lifecycle as harness2.Server; binary, env and mandatory set come from OPT."""
    def __init__(self, label, spec, model="q2"):
        super().__init__(label, spec, model)
        base = [x for x in BASE_MANDATORY if x not in ("-ngl", "999")] if OPT["nongl"] else BASE_MANDATORY
        mand = base + PLE[OPT["ple"]]
        tail = ["--fit", "off"] if OPT["fitoff"] else []
        self.cmd = ([BINS[OPT["engine"]], "--port", str(H.PORT), "-m", H.MODELS[model]] + mand
                    + spec.split() + tail + H.SAMPLING)
        self.env_desc = "LLAMA_ATTN_ROT_DISABLE=1" if OPT["rot"] == "on" else "(unset)"

    def start(self, timeout=1200):
        # harness2.Server.start always sets LLAMA_ATTN_ROT_DISABLE=1 in the child env;
        # for rot=off the child is wrapped in `env -u` so the server never sees it.
        if OPT["rot"] == "off":
            self.cmd = ["/usr/bin/env", "-u", "LLAMA_ATTN_ROT_DISABLE"] + self.cmd
        return super().start(timeout)

H.Server = Server4

_record = H.record
def record4(row):
    row.update({"engine": OPT["engine"], "engine_sha": git_sha(OPT["engine"]),
                "env_rot_disable": OPT["rot"] == "on", "ple": OPT["ple"], "fitoff": OPT["fitoff"],
                "nongl": OPT["nongl"]})
    _record(row)
H.record = record4

def fit_lines(log):
    try: t = open(log).read()
    except Exception: return []
    return [l for l in t.splitlines() if re.search(r"\bfit|fitting|llama_params_fit", l)][:40]

# ------------------------------------------------------------------ sanity (B1)
SANITY_Q = ("Write a Python function `merge_intervals(intervals)` that merges overlapping "
            "closed intervals and returns them sorted. Include a short docstring and two "
            "doctest examples. Keep the answer brief.")

def cmd_sanity(a):
    """B1: load, record VRAM/RSS/MemAvailable, D0 x3 (short), one 500-token sanity probe."""
    s = H.Server(a.label, a.spec, a.model)
    row = {"kind": "sanity", "model": a.model, "label": a.label, "spec": a.spec,
           "cmd": " ".join(s.cmd), "env": s.env_desc}
    try:
        s.start(timeout=a.timeout)
        row.update({"load_s": round(s.load_s, 1), "load_vram_mib": s.load_vram,
                    "rss_load": s.rss_load, "mem_avail_after_load_kb": s.mem_load})
        print(f"loaded {s.load_s:.0f}s vram {s.load_vram} MemAvail {s.mem_load//1024} MiB "
              f"rss {s.rss_load}", flush=True)
        H.chat(H.corpus("p4k"), 32, nonce="warmup")
        p = {"messages": [{"role": "user", "content": SANITY_Q}], "max_tokens": 500,
             "temperature": 0.3, "top_p": 0.95, "top_k": 20, "seed": H.SEED,
             "cache_prompt": False, "stream": False}
        r = H.post("/v1/chat/completions", p, timeout=900)
        m = r["choices"][0]["message"]; tm = r.get("timings", {})
        row["probe"] = {"finish_reason": r["choices"][0].get("finish_reason"),
                        "content": (m.get("content") or "")[:3000],
                        "reasoning_head": (m.get("reasoning_content") or "")[:1500],
                        "reasoning_len": len(m.get("reasoning_content") or ""),
                        "predicted_n": tm.get("predicted_n"), "decode_ps": tm.get("predicted_per_second")}
        out = {"d0": [H.chat(H.D0_PROMPT, 1400, nonce=f"d0-{i}") for i in range(a.reps)]}
        row["runs"] = out; row["summary"] = H.summarize(out)
        row.update({"peak_vram_mib": s.peak, "rss_end": H.rss(s.pid),
                    "mem_avail_end_kb": H.mem_avail_kb(), "fit_log": fit_lines(s.log),
                    "crash": H.crash_in_log(s.log), "ok": True})
        print(json.dumps({"D0": row["summary"], "probe_finish": row["probe"]["finish_reason"],
                          "probe_tok": row["probe"]["predicted_n"]}), flush=True)
        print("---- probe content ----\n" + row["probe"]["content"][:1500], flush=True)
    except Exception as e:
        row.update({"ok": False, "error": str(e)[:2500]})
        print("SANITY FAIL:", str(e)[:1500], flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    row["fit_log"] = row.get("fit_log") or fit_lines(s.log or "")
    H.record(row)
    H.mark_done(a.label, {"kind": "sanity", "ok": row.get("ok"), "load_vram": row.get("load_vram_mib")})
    return 0 if row.get("ok") else 1

# ------------------------------------------------------------------ task02 (v3 harness)
def cmd_task02(a):
    import task02_v3 as T
    sampling = {"temperature": 0.3, "top_p": 0.95, "top_k": 20, "seed": 20260929}
    expect = {"temperature": 0.3, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "seed": 20260929}
    s = H.Server(a.label, a.spec, a.model)
    row = {"kind": "task02", "model": a.model, "label": a.label, "spec": a.spec,
           "cmd": " ".join(s.cmd), "temp": 0.3, "seed": 20260929}
    try:
        s.start(timeout=a.timeout)                          # cold: NO warm-up
        row.update({"load_s": round(s.load_s, 1), "load_vram_mib": s.load_vram,
                    "mem_avail_after_load_kb": s.mem_load})
        outdir = os.path.join(ROOT, "runs", f"task02-{a.label}")
        meta, side = T.run(a.label, outdir, sampling, expect, max_tokens=a.max_tokens, abort=s.kill)
        row["meta"] = meta
        row["alive_after"] = s.proc.poll() is None; row["crash"] = H.crash_in_log(s.log)
        row["notifier"] = T.notifier_map(outdir)
        if not meta["sampling_ok"]:
            row.update({"status": "VOID_SAMPLING", "ok": False})
        elif meta["finish_reason"] == "length":
            row.update({"status": "VOID_LENGTH", "ok": False})
        elif meta["files_missing"]:
            row.update({"status": "SCORED_MISSING_FILES", "ok": True, "gate4_pass": False})
        else:
            res, _ = T.score(outdir, side)
            row.update({"status": "SCORED", "ok": True, "probes": res, "gate4_pass": res["gate4"]})
            if not res["gate4"] and "NOTIFIER" in (res.get("error") or ""):
                row["diag_probes"] = T.diag_score(outdir, side)[0]
        row["peak_vram_mib"] = s.peak
        print(json.dumps({k: row.get(k) for k in ("status", "probes", "gate4_pass", "diag_probes", "crash")}
                         | {"finish": meta["finish_reason"], "predicted_n": meta["predicted_n"],
                            "tps": meta["predicted_ps"], "wall": meta["wall_s"],
                            "notifier": row["notifier"]["summary"]}, indent=2), flush=True)
    except Exception as e:
        row.update({"status": "ERROR", "ok": False, "error": str(e)[:2000], "crash": H.crash_in_log(s.log)})
        print("TASK02 ERROR:", str(e)[:600], flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    H.record(row)
    H.mark_done(a.label, {"kind": "task02", "status": row.get("status"), "gate4": row.get("gate4_pass")})
    return 0 if row.get("ok") else 1

def cmd_full(a):
    return H.cmd_full(a)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("load", "bench", "session", "cold", "task02", "sanity", "full"):
        p = sub.add_parser(name)
        p.add_argument("--label", required=True); p.add_argument("--spec", required=True)
        p.add_argument("--engine", choices=["F", "M"], required=True)
        p.add_argument("--rot", choices=["on", "off"], default="on")
        p.add_argument("--ple", choices=list(PLE), default="ot")
        p.add_argument("--fitoff", action="store_true")
        p.add_argument("--nongl", action="store_true", help="drop -ngl 999 (B3: --fit aborts if ngl is user-set)")
        p.add_argument("--timeout", type=int, default=1500)
        p.add_argument("--keep", action="store_true")
        p.add_argument("--model", choices=["q2"], default="q2")
        if name == "bench":
            p.add_argument("--full", action="store_true")
            p.add_argument("--reps", type=int, default=3)
            p.add_argument("--tests", default="p4k,p32,d0")
        if name == "sanity":
            p.add_argument("--reps", type=int, default=3)
        if name == "session":
            p.add_argument("--gen", type=int, default=800)
            p.add_argument("--extra", default="")
        if name == "cold":
            p.add_argument("--which", default="all")
        if name == "task02":
            p.add_argument("--max-tokens", type=int, default=60000)
        if name == "full":
            p.add_argument("--window", type=int, default=128)
    a = ap.parse_args()
    OPT.update(engine=a.engine, rot=a.rot, ple=a.ple, fitoff=a.fitoff, nongl=a.nongl)
    if a.engine == "F" and a.fitoff: sys.exit("F has no --fit")
    if H.load_state().get("done") and a.label in [d.get("key") for d in H.load_state()["done"]]:
        print(f"SKIP: {a.label} already done (state-v4.json)"); return 0
    return {"load": H.cmd_load, "bench": H.cmd_bench, "session": H.cmd_session,
            "cold": H.cmd_cold, "task02": cmd_task02, "sanity": cmd_sanity,
            "full": cmd_full}[a.cmd](a)

if __name__ == "__main__":
    sys.exit(main())
