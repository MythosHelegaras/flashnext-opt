import json
rows=[json.loads(l) for l in open("/home/zef/flashnext-opt/results-v2.jsonl")]
S=[r for r in rows if r["kind"]=="session" and r.get("ok")]
for r in S:
    t=r["turns"]; short=[x["turn"] for x in t if (x["predicted_n"] or 0)<500]
    dec=[]
    for i,x in enumerate(t):
        if (x["predicted_n"] or 0)>=500: dec.append(x["decode_ps"])
        else:
            nb=[t[j]["decode_ps"] for j in (i-1,i+1) if 0<=j<len(t) and (t[j]["predicted_n"] or 0)>=500]
            dec.append(sum(nb)/len(nb))
    adj=sum(x["ttft_s"] for x in t)+sum(1500/d for d in dec)
    pp_late=[round(x["prompt_ps"]) for x in t[1:]]
    print(f'{r["label"]:22} session_s={r["session_s"]:8.1f} adj={adj:8.1f} ({(adj/r["session_s"]-1)*100:+.2f}%) short_turns={short} '
          f'T1 ttft={t[0]["ttft_s"]:.1f} turns2-16 ttft={sum(x["ttft_s"] for x in t[1:]):.1f} '
          f'dec t1={t[0]["decode_ps"]:.2f} t16={t[-1]["decode_ps"]:.2f} pp t2={pp_late[0]} t16={pp_late[-1]}')
