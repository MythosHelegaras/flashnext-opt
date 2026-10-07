#!/usr/bin/env python3
"""Phase C without llama-perplexity: measure KV-quantisation fidelity through the API.

llama-perplexity (and so --kl-divergence-base) does not exist in this fork, and hard rule 3
forbids building it or pointing a mainline binary at this model. So instead of a weak
"did the eval still pass" signal, this measures the two quantities the prompt's own
threshold is written in terms of -- same-top-token % and KL divergence -- directly.

Method (teacher forcing, so every KV type sees byte-identical contexts):
  * take a real source prefix P of L tokens, and the NEXT 64 real tokens as continuation C
  * for i in 0..63: ask for the next-token distribution at P+C[:i] (n_predict 1, n_probs 20)
  * prompts are TOKEN ARRAYS and grow by one token, so cache_prompt makes each step ~1 decode
  * the forced continuation is real text, identical for all KV types -> no divergence drift
Run at two context lengths, because KV quantisation error accumulates over cached entries.
Reference is f16/f16; q8/q8 and f16-K/q8-V are scored against it.
"""
import json, math, os, sys, urllib.request

BASE="http://127.0.0.1:9997"
NPROBS=20; NPOS=64
LENS=[8000, 60000]          # context lengths to probe
NTRIALS=2                   # distinct prefixes per length

def post(path,payload,timeout=3600):
    req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode(),
                               headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode())

def tokenize(text): return post("/tokenize",{"content":text},timeout=900)["tokens"]

def dist_at(tokens):
    """Next-token distribution for an exact token-array context.
    This build returns completion_probabilities[0].top_logprobs as
    [{id, token, bytes, logprob}, ...]. Distributions are keyed by token id."""
    r=post("/completion",{"prompt":tokens,"n_predict":1,"n_probs":NPROBS,
                          "temperature":0.0,"cache_prompt":True},timeout=1800)
    cp=r.get("completion_probabilities")
    if not cp: raise RuntimeError("server returned no completion_probabilities")
    tl=cp[0].get("top_logprobs") or []
    return [(e["id"], math.exp(e["logprob"])) for e in tl if e.get("logprob") is not None]

def collect(label):
    """Walk the trials and record each position's top-20 distribution."""
    pool=open(os.path.expanduser("~/flashnext-opt/corpus/full256.txt")).read()
    toks=tokenize(pool[:1_200_000])
    print(f"  pool tokenised: {len(toks)} tokens",flush=True)
    out={}
    for L in LENS:
        for t in range(NTRIALS):
            start=t*(L+4000)
            if start+L+NPOS+8 > len(toks): break
            ctx=toks[start:start+L]; cont=toks[start+L:start+L+NPOS]
            key=f"L{L}-t{t}"; rows=[]
            for i in range(NPOS):
                d=dist_at(ctx+cont[:i])
                if not d: raise RuntimeError("empty distribution - parser/API mismatch")
                rows.append({"pos":i,"forced":cont[i],"dist":d})
            out[key]={"ctx_len":L,"rows":rows}
            print(f"  {label} {key}: {len(rows)} positions",flush=True)
    return out

def kl_and_agree(ref,cmp_):
    """KL(ref||cmp) over ref's top-20 (renormalised) + top-1 agreement."""
    kls=[]; agree=0; n=0
    for key in ref:
        for a,b in zip(ref[key]["rows"], cmp_[key]["rows"]):
            da={k:v for k,v in a["dist"] if v}; db={k:v for k,v in b["dist"] if v}
            if not da or not db: continue
            ta=max(da,key=da.get); tb=max(db,key=db.get)
            n+=1; agree += (ta==tb)
            Z=sum(da.values())
            kl=0.0
            for tok,p in da.items():
                p/=Z; q=db.get(tok, 1e-10)
                if p>0: kl += p*math.log(p/max(q,1e-10))
            kls.append(kl)
    return {"n_positions":n,"same_top_token_pct":round(100.0*agree/max(1,n),3),
            "mean_kl":round(sum(kls)/max(1,len(kls)),6),
            "max_kl":round(max(kls),6) if kls else None}

if __name__=="__main__":
    mode=sys.argv[1]
    if mode=="collect":
        label=sys.argv[2]
        json.dump(collect(label),open(f"kvfid-{label}.json","w"))
        print(f"COLLECT DONE {label}",flush=True)
    elif mode=="compare":
        ref=json.load(open(f"kvfid-{sys.argv[2]}.json"))
        res={}
        for lab in sys.argv[3:]:
            cmp_=json.load(open(f"kvfid-{lab}.json"))
            keys=set(ref)&set(cmp_)
            res[lab]=kl_and_agree({k:ref[k] for k in keys},{k:cmp_[k] for k in keys})
            # also split by context length
            for L in LENS:
                ks={k for k in keys if ref[k]["ctx_len"]==L}
                if ks: res[f"{lab}@L{L}"]=kl_and_agree({k:ref[k] for k in ks},{k:cmp_[k] for k in ks})
        json.dump(res,open("kvfid-compare.json","w"),indent=2)
        print(json.dumps(res,indent=2))
