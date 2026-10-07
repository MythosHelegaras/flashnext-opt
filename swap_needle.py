"""Verify the SHIPPED config end-to-end through llama-swap at the full window."""
import json, re, time, urllib.request, harness as H
BASE="http://127.0.0.1:9292"
text, ans = H.needle_text(H.corpus("full128"), {"early":0.10,"mid":0.50,"late":0.90})
payload={"model":"flashnext","messages":[{"role":"user","content":text+"\n\n"+H.FULL_Q}],
         "max_tokens":4000,"temperature":0.3,"top_p":0.95,"top_k":20,"seed":20260929}
req=urllib.request.Request(BASE+"/v1/chat/completions",data=json.dumps(payload).encode(),
                           headers={"Content-Type":"application/json"})
t0=time.time()
r=json.loads(urllib.request.urlopen(req,timeout=5400).read().decode())
wall=time.time()-t0
ch=r["choices"][0]; c=ch.get("message",{}).get("content") or ""; tm=r.get("timings",{})
got={t:(re.search(rf"{t.upper()}\s*=\s*([0-9]{{7}})",c).group(1)
        if re.search(rf"{t.upper()}\s*=\s*([0-9]{{7}})",c) else None) for t in ans}
out={"via":"llama-swap:9292","wall_s":round(wall,1),"finish_reason":ch.get("finish_reason"),
     "prompt_n":tm.get("prompt_n"),"prefill_ps":tm.get("prompt_per_second"),
     "TTFT_s":round((tm.get("prompt_ms") or 0)/1000,2),"decode_ps":tm.get("predicted_per_second"),
     "expected":ans,"retrieved":got,"needles_ok":all(got[t]==ans[t] for t in ans)}
json.dump(out,open("swap_needle.json","w"),indent=2); print(json.dumps(out,indent=2),flush=True)
