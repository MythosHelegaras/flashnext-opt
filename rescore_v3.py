#!/usr/bin/env python3
"""W9: re-extract a v3 run's saved response with the fixed extractor into runs/task02-<label>.x2
(fresh dir, probe copied in only at score time), score, map NOTIFIER, append a 'rescore' row."""
import json, os, shutil, sys, time
R = os.path.expanduser("~/flashnext-opt"); sys.path.insert(0, R)
import task02, task02_v3 as T
for label in sys.argv[1:]:
    side = f"{R}/runs/task02-{label}.meta"; text = open(f"{side}/response.md").read()
    old, new = task02.extract(text), T.extract(text)
    if all(old.get(f) == new.get(f) for f in T.FILES):
        print(label, "extraction identical -> original score stands"); continue
    d = f"{R}/runs/task02-{label}.x2"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for n, b in new.items(): open(f"{d}/{n}", "w").write(b)
    xs = side + "/x2"; os.makedirs(xs, exist_ok=True)
    res, out = T.score(d, xs)
    row = {"kind": "rescore", "label": label, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "reason": "W9 extractor fix", "changed": [f for f in T.FILES if old.get(f) != new.get(f)],
           "probes": res, "gate4_pass": res["gate4"], "notifier": T.notifier_map(d)}
    if not res["gate4"] and res.get("error") and "NOTIFIER" in res["error"]:
        row["diag_probes"] = T.diag_score(d, xs)[0]
    open(f"{R}/results-v3.jsonl", "a").write(json.dumps(row) + "\n")
    print(json.dumps(row, indent=1))
