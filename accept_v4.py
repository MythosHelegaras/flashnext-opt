#!/usr/bin/env python3
"""v4: per-request MTP draft acceptance from an M server log.
Each finished request prints 'prompt eval time = … / N tokens', 'eval time = … / G tokens' and,
with speculative decoding, 'draft acceptance = R (A accepted / D generated), mean len = L'.
Requests are classed by prompt size: d0 (< 1k), p4k (1k–10k), p32 (10k–60k), full (> 60k).
For session logs every request is a turn (prompt_n is the appended part only).
usage: accept_v4.py <server.log> [--session]"""
import json, re, sys

def parse(path):
    reqs, cur = [], {}
    for line in open(path, errors="ignore"):
        m = re.search(r"prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens", line)
        if m: cur = {"prompt_n": int(m.group(2))}; continue
        m = re.search(r"\s eval time =\s*([\d.]+) ms /\s*(\d+) tokens", line)
        if m and cur is not None: cur["gen_n"] = int(m.group(2)); continue
        m = re.search(r"draft acceptance = ([\d.]+) \(\s*(\d+) accepted /\s*(\d+) generated\), mean len =\s*([\d.]+)", line)
        if m:
            cur.update(rate=float(m.group(1)), accepted=int(m.group(2)), drafted=int(m.group(3)),
                       mean_len=float(m.group(4)))
            reqs.append(cur); cur = {}
    return reqs

def klass(n):
    return "d0" if n < 1000 else "p4k" if n < 10000 else "p32" if n < 60000 else "full"

def summary(reqs, session=False):
    groups = {}
    for i, r in enumerate(reqs):
        k = "turn" if session else klass(r.get("prompt_n", 0))
        if not session and i == 0: k = "warmup"
        groups.setdefault(k, []).append(r)
    out = {}
    for k, rs in groups.items():
        a = sum(r["accepted"] for r in rs); d = sum(r["drafted"] for r in rs)
        out[k] = {"n_req": len(rs), "accepted": a, "drafted": d,
                  "rate": round(a / d, 4) if d else None,
                  "mean_len": round(sum(r["mean_len"] for r in rs) / len(rs), 3),
                  "rates": [r["rate"] for r in rs]}
    a = sum(r["accepted"] for r in reqs); d = sum(r["drafted"] for r in reqs)
    out["all"] = {"n_req": len(reqs), "rate": round(a / d, 4) if d else None}
    return out

if __name__ == "__main__":
    print(json.dumps(summary(parse(sys.argv[1]), "--session" in sys.argv), indent=1))
