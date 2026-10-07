#!/usr/bin/env python3
"""v3 summary: quant x temp cells, v2's temp-0.3 Task 02 runs folded in (W4 token scale)."""
import json, os, sys, statistics as st
R = os.path.expanduser("~/flashnext-opt")
V2MAP = {"task02-v2-F-q2-n46-ub2048": ("q2", "v2-F (r1)"), "task02-v2-F2-q2-n46-ub2048": ("q2", "v2-F2 (r2)"),
         "task02-v2-F-iq3-n46-ub2048": ("iq3", "v2-F (r1)"), "task02-v2-F2-iq3-n46-ub2048": ("iq3", "v2-F2 (r2)")}
V2GATE = {"task02-v2-F-q2-n46-ub2048": True, "task02-v2-F2-q2-n46-ub2048": True,
          "task02-v2-F-iq3-n46-ub2048": False, "task02-v2-F2-iq3-n46-ub2048": True}

def rows():
    out = []
    v2 = json.load(open(f"{R}/v2-tokens-v3.json")) if os.path.exists(f"{R}/v2-tokens-v3.json") else {}
    for d, t in v2.items():
        q, lab = V2MAP[d]
        out.append({"src": "v2", "label": lab, "model": q, "temp": 0.3, "seed": 20260929, "status": "SCORED",
                    "gate4": V2GATE[d], "finish": t["finish_reason"], "rtok": t["reasoning_tok"],
                    "ctok": t["content_tok"], "pred": t["predicted_n"], "tps": t["predicted_ps"],
                    "wall": t["wall_s"], "notifier": t["notifier"], "probes": None})
    resc = {}
    for l in open(f"{R}/results-v3.jsonl"):
        r = json.loads(l)
        if r.get("kind") == "rescore": resc[r["label"]] = r
    for l in open(f"{R}/results-v3.jsonl"):
        r = json.loads(l); m = r.get("meta") or {}
        if r.get("kind") == "rescore": continue
        if r["label"] in resc:
            x = resc[r["label"]]
            r = dict(r, probes=x["probes"], gate4_pass=x["gate4_pass"], notifier=x["notifier"],
                     diag_probes=x.get("diag_probes"), label=r["label"] + " (W9 re-extract)")
        out.append({"src": "v3", "label": r["label"], "model": r["model"], "temp": r["temp"], "seed": r["seed"],
                    "status": r["status"], "gate4": r.get("gate4_pass"), "finish": m.get("finish_reason"),
                    "rtok": m.get("reasoning_tok"), "ctok": m.get("content_tok"), "pred": m.get("predicted_n"),
                    "tps": m.get("predicted_ps"), "wall": m.get("wall_s"),
                    "notifier": (r.get("notifier") or {}).get("summary"), "probes": r.get("probes"),
                    "diag": r.get("diag_probes"), "sampling_ok": m.get("sampling_ok")})
    return out

def nmod(summary):
    """Module NOTIFIER is effectively read from: breaker_events if every read goes through
    breaker_events.NOTIFIER (or is a bare read inside breaker_events), else the bare-read module(s)."""
    import re
    rd = re.sub(r"getattr\(([^,]*),[^)]*\)", r"getattr(\1)", (summary or "").split("read: ", 1)[-1])
    parts = [x.strip() for x in rd.split(",") if x.strip()]
    if parts and all("breaker_events.NOTIFIER" in x or x.startswith("breaker_events(")
                     or ("getattr(" in x and "breaker_events" in x) for x in parts):
        return "breaker_events"
    return "+".join(sorted({x.split("(")[0].split("\u2192")[0].split("→")[0] for x in parts})) or "NONE"

def ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return "—"
    return f"{st.mean(xs):,.0f}" + (f" ±{st.stdev(xs):,.0f}" if len(xs) > 1 else "")

def main():
    rs = rows()
    print("| run | quant | temp | seed | finish | gate4 | P1 P2 P3 P5 | reasoning tok | content tok | predicted_n | decode t/s | wall s | NOTIFIER |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rs:
        p = r["probes"]; ps = " ".join(p[f"probe{n}"][0] for n in (1, 2, 3, 5)) if p else ("P P P P" if r["gate4"] else "(v2 V19: NameError)" if r["src"]=="v2" else "—")
        print(f"| {r['src']} {r['label']} | {r['model']} | {r['temp']} | {r['seed']} | {r['finish']} | "
              f"{'PASS' if r['gate4'] else 'FAIL' if r['gate4'] is False else '—'} | {ps} | {r['rtok']} | {r['ctok']} | "
              f"{r['pred']} | {r['tps'] and round(r['tps'],2)} | {r['wall']} | {r['notifier']} |")
    print()
    print("| quant | temp | n scored | gate 4 pass | NOTIFIER bound/read in breaker_events | mean reasoning tok | mean content tok | mean wall s | mean decode t/s | tokens/decode (s) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for q in ("q2", "iq3"):
        for t in (0.3, 1.0):
            c = [r for r in rs if r["model"] == q and r["temp"] == t and r["status"] in ("SCORED", "SCORED_MISSING_FILES")]
            if not c: continue
            be = sum(1 for r in c if nmod(r["notifier"]) == "breaker_events")
            tt = [(r["rtok"] + r["ctok"]) / r["tps"] for r in c if r["rtok"] is not None and r["tps"]]
            print(f"| {q} | {t} | {len(c)} | {sum(1 for r in c if r['gate4'])}/{len(c)} | {be}/{len(c)} | "
                  f"{ms([r['rtok'] for r in c])} | {ms([r['ctok'] for r in c])} | {ms([r['wall'] for r in c])} | "
                  f"{ms([r['tps'] for r in c]) if False else round(st.mean([r['tps'] for r in c]),2)} | {ms(tt)} |")
    voids = [r for r in rs if r["status"] not in ("SCORED", "SCORED_MISSING_FILES")]
    if voids:
        print("\nvoid/error:", [(r["label"], r["status"], r["finish"], r["pred"]) for r in voids])

if __name__ == "__main__" and len(sys.argv) == 1:
    main()

def cost():
    """Expected decode time per *gate-4-passing* task, counting voids (60k wasted) and fails."""
    rs = rows()
    print("\n| quant | temp | attempts (v3+v2) | voids @60k | scored | pass | mean tok/attempt | decode t/s | s/attempt | s per passing task |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for q in ("q2", "iq3"):
        for t in (0.3, 1.0):
            c = [r for r in rs if r["model"] == q and r["temp"] == t and r["status"] in ("SCORED", "VOID_LENGTH")]
            if not c: continue
            v = [r for r in c if r["status"] == "VOID_LENGTH"]; sc = [r for r in c if r["status"] == "SCORED"]
            p = sum(1 for r in sc if r["gate4"])
            tok = st.mean(r["pred"] for r in c); tps = st.mean(r["tps"] for r in c)
            spa = st.mean(r["pred"] / r["tps"] for r in c)
            print(f"| {q} | {t} | {len(c)} | {len(v)} | {len(sc)} | {p} | {tok:,.0f} | {tps:.2f} | {spa:,.0f} | "
                  f"{(spa*len(c)/p):,.0f} |" if p else "| — |")

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "cost":
    cost()
