#!/usr/bin/env python3
"""v3 driver: Task 02 Prompt B, cold server per run, per-request sampling.
Resumable: skips labels already in state-v3.json; a `length` run is void and re-run once."""
import json, os, sys, time, datetime
R = os.path.expanduser("~/flashnext-opt"); sys.path.insert(0, R)
import harness2 as H, task02_v3 as T

H.RESULTS = os.path.join(R, "results-v3.jsonl")
H.STATE = os.path.join(R, "state-v3.json")
SPEC = "-ncmoe 46 -b 2048 -ub 2048 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0"
LAST_END = datetime.datetime(2026, 10, 5, 22, 45)      # W1: run must end by then
EST = datetime.timedelta(minutes=37)                    # load + 60k tok worst case
T10 = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0}
T03 = {"temperature": 0.3, "top_p": 0.95, "top_k": 20}  # v2 request verbatim (no min_p)
E03 = {"temperature": 0.3, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "seed": 20260929}
V2DIRS = ["task02-v2-F-q2-n46-ub2048", "task02-v2-F2-q2-n46-ub2048",
          "task02-v2-F-iq3-n46-ub2048", "task02-v2-F2-iq3-n46-ub2048"]

# (label, model, temp, seed) in W6 order
QUEUE = ([(f"v3-q2-t10-r{i+1}", "q2", 1.0, 20261005+i) for i in range(3)] +
         [(f"v3-iq3-t10-r{i+1}", "iq3", 1.0, 20261008+i) for i in range(3)] +
         [(f"v3-iq3-t03-r{i+3}", "iq3", 0.3, 20260929) for i in range(2)] +
         [(f"v3-q2-t03-r{i+3}", "q2", 0.3, 20260929) for i in range(2)])
SPARE_SEEDS = iter(range(20261011, 20261030))

def done_keys():
    return {d["key"] for d in H.load_state().get("done", [])}

def v2_tokens():
    """W4: put v2's saved runs on the same token scale (once, on a live server)."""
    p = os.path.join(R, "v2-tokens-v3.json")
    if os.path.exists(p): return
    out = {}
    for d in V2DIRS:
        side = os.path.join(R, "runs", d + ".meta")
        out[d] = {"reasoning_tok": T.ntok(open(f"{side}/reasoning.txt").read()),
                  "content_tok": T.ntok(open(f"{side}/response.md").read()),
                  **{k: json.load(open(f"{side}/meta.json")).get(k) for k in
                     ("predicted_n", "predicted_ps", "wall_s", "finish_reason")},
                  "notifier": T.notifier_map(os.path.join(R, "runs", d))["summary"]}
    json.dump(out, open(p, "w"), indent=2)
    print("v2 tokens:", json.dumps(out), flush=True)

def one(label, model, temp, seed, attempt=1):
    sampling = dict(T10 if temp == 1.0 else T03, seed=seed)
    expect = dict(T10, seed=seed) if temp == 1.0 else E03
    s = H.Server(label, SPEC, model)
    row = {"kind": "task02", "model": model, "label": label, "temp": temp, "seed": seed,
           "attempt": attempt, "spec": SPEC, "cmd": " ".join(s.cmd)}
    try:
        s.start(timeout=1500)                              # cold: NO warm-up
        row.update({"load_s": round(s.load_s, 1), "load_vram_mib": s.load_vram,
                     "mem_avail_after_load_kb": s.mem_load})
        outdir = os.path.join(R, "runs", f"task02-{label}")
        meta, side = T.run(label, outdir, sampling, expect, abort=s.kill)
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
            if not res["gate4"] and res.get("error") and "NOTIFIER" in (res["error"] or ""):
                row["diag_probes"] = T.diag_score(outdir, side)[0]
        try: v2_tokens()
        except Exception as e: print("v2 tokenize failed:", e, flush=True)
        row["peak_vram_mib"] = s.peak
    except Exception as e:
        row.update({"status": "ERROR", "ok": False, "error": str(e)[:2000], "crash": H.crash_in_log(s.log)})
        print("RUN ERROR:", str(e)[:600], flush=True)
    finally:
        try: s.kill()
        except Exception: pass
    H.record(row)
    H.mark_done(label, {"kind": "task02", "model": model, "temp": temp, "seed": seed,
                        "status": row["status"], "gate4": row.get("gate4_pass"),
                        "finish": (row.get("meta") or {}).get("finish_reason"),
                        "notifier": (row.get("notifier") or {}).get("summary")})
    print(f"== {label} {row['status']} gate4={row.get('gate4_pass')} "
          f"{json.dumps({k: (row.get('meta') or {}).get(k) for k in ('finish_reason','predicted_n','reasoning_tok','content_tok','wall_s','predicted_ps')})} "
          f"| {(row.get('notifier') or {}).get('summary')}", flush=True)
    return row

def main():
    H.save_state(phase="runs", started="2026-10-05T17:01", hard_stop="2026-10-05T23:01")
    for label, model, temp, seed in QUEUE:
        if label in done_keys(): print("skip (done):", label, flush=True); continue
        attempt = 1
        while True:
            if datetime.datetime.now() + EST > LAST_END:
                print(f"TIME: not starting {label} (would end after {LAST_END:%H:%M})", flush=True)
                H.save_state(skipped_for_time=H.load_state().get("skipped_for_time", []) + [label])
                print("CHAIN_DONE", flush=True); return
            print(f">> {datetime.datetime.now():%H:%M:%S} {label} model={model} temp={temp} seed={seed} attempt={attempt}", flush=True)
            row = one(label if attempt == 1 else f"{label}-rerun", model, temp, seed, attempt)
            if row["status"] == "VOID_SAMPLING" or row["status"] == "ERROR":
                print("STOP: sampling void or error — needs a look", flush=True)
                print("CHAIN_DONE", flush=True); return
            if row["status"] == "VOID_LENGTH" and attempt == 1:
                attempt = 2
                if temp == 1.0: seed = next(SPARE_SEEDS)
                continue
            break
    print("CHAIN_DONE", flush=True)

if __name__ == "__main__":
    main()
