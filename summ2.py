import json
for l in open("/home/zef/flashnext-opt/results-v2.jsonl"):
    r=json.loads(l); k=r["kind"]
    if k=="bench":
        s=r.get("summary",{}); f=r.get("full") or {}
        print(f'{r["label"]:28} ok={r.get("ok")} load={r.get("load_vram_mib")} peakReps={r.get("peak_vram_reps_mib")} peakAll={r.get("peak_vram_mib")} memLoad={round((r.get("mem_avail_after_load_kb") or 0)/2**20,1)}G '
              f'P4k={s.get("P4k_ps")} P32k={s.get("P32k_ps")}±{s.get("P32k_sd")} D0={s.get("D0_ps")}±{s.get("D0_sd")} D32k={s.get("D32k_ps")}±{s.get("D32k_sd")} Tt={s.get("T_turn_s")} '
              f'FULL n={f.get("FULL_prompt_n")} pp={round(f.get("FULL_prefill_ps") or 0,1)} tg={round(f.get("FULL_decode_ps") or 0,2)} needles={f.get("needles_ok")} fin={f.get("finish_ok")} err={(r.get("error") or "")[:200]}')
    elif k=="session":
        print(f'{r["label"]:28} SESSION ok={r.get("ok")} session_s={r.get("session_s")} ttft={r.get("sum_ttft_s")} dec={r.get("sum_decode_s")} last_depth={r.get("last_depth")} last_tg={r.get("last_decode_ps")} broken={r.get("reuse_broken_turns")} peak={r.get("peak_vram_mib")} err={(r.get("error") or "")[:200]}')
    elif k=="cold":
        print(f'{r["label"]:28} COLD {r["passed"]}/{r["total"]} ' + " ".join(f'{i["item"]}:{"ok" if i["ok"] else "FAIL"}({i.get("prompt_n")})' for i in r["items"]))
    elif k=="task02":
        print(f'{r["label"]:28} TASK02 ok={r.get("ok")} probes={r.get("probes")} gate4={r.get("gate4_pass")} meta={ {x:(r.get("meta") or {}).get(x) for x in ("finish_reason","predicted_n","predicted_ps","files_missing")} } crash={r.get("crash")} err={(r.get("error") or "")[:200]}')
    else:
        print(r["label"], k, {x:r.get(x) for x in ("ok","load_vram_mib","peak_vram_mib","completed","reached","oom_alloc_mib","error")})
