# DECISIONS-v2.md — flashnext v2: quant decision (UD-Q2_K_XL vs GSQ-RCO IQ3_XXS), patched fork

## Phase 0 — Preflight (11:53–12:10, 2026-10-05)

### V1. Prompt file and clock
`./PROMPT-v2.md` does not exist; the mission prompt is `flashnext-overnight-PROMPT-v2.md`
(7461 B, mtime 2026-10-05 11:44). It references `PROMPT.md`, which (as last night, D1) is
`flashnext-overnight-PROMPT.md`; its §1 hard rules apply.
**The run started at 11:53 local, not overnight.** HARD_STOP 07:00 is therefore read as
07:00 on 2026-10-06 (finish phase by 06:15 then). The phase time budgets (~6.7 h) are kept
as written, so the run should end long before that. Zef asked for this run now, so stopping
llama-swap during the day is intended.

### V2. Binary and patch
`llama-server --version`: `0.3.0-dev (build 10654, commit bea3b12da)`, **built with GNU 16.2.1**
(new toolchain), binary mtime 2026-09-29 08:57. Fork HEAD unchanged at `bea3b12d`.
`git diff --stat` shows `ggml/src/ggml-cuda/mmq.cu | 2 +-` (the #27792 / PR #27044 one-liner),
plus the fork's own uncommitted qwen4exp model files. The latest pre-run cold check
(`logs/ubfix-20261005-114619`, 11:46 today) completed prompt_B at ub2048 with no error.
All v1 speed numbers are from a different binary — none are reused in any v2 comparison.

### V3. Models
- Q2: 3 shards present (10.9 MB + 49.98 GB + 28.88 GB = 78.86 GB).
- IQ3_XXS: 2 shards, **shard 1 = 47,039,860,096 B (47.0 GB), shard 2 = 28,800,138,432 B (28.8 GB)**,
  no `.incomplete` files. Complete -> both models are tested. Total 75.83 GB — *smaller* than Q2.
- `per_layer_token_embd.weight` is present in IQ3_XXS shard 2 under that exact name (IQ4_NL,
  28,800,138,240 B — byte-identical size to Q2's). `-ot per_layer_token_embd=CPU` works unchanged.

### V4. IQ3_XXS per-layer expert types (from `tensor-allocation/*IQ3_XXS*.rco-allocation.txt`,
cross-checked against the GGUF headers; full table in `layer-sizes-v2.json`)
The name is a whole-file target (3.00 bpw); experts are a per-layer mix:
| blocks | gate/up | down |
|---|---|---|
| 0,2,4 | IQ2_XS | IQ4_NL |
| 1,3,6,7,11,13,16,27 | IQ2_XXS | Q2_0 |
| 5,9,10,14,19,25 | IQ2_XS | Q2_0 |
| 12,15,17,21,26,40 | IQ2_S | Q2_0 |
| 29,38,42,46 | IQ2_S | IQ4_NL |
| 39 | IQ2_XS | IQ4_NL |
| 31 | IQ2_XXS | IQ4_NL |
| 8,18,20,22,23,24,33 | IQ3_S | Q2_0 |
| 28,30,32,34,37,43 | IQ3_S | IQ4_NL |
| 36,41,45 | IQ3_XXS | Q2_0 |
| 35,44,47 | IQ3_XXS | IQ4_NL |
Q2_K_XL by contrast is IQ2_XS gate/up + IQ4_NL down in every block (block 2: IQ3_XXS gate/up).
Non-expert tensors: IQ4_XS/IQ3_S/Q6_K attention, Q5_K output, BF16 hyper-connection weights.

### V5. Per-layer expert bytes — IQ3_XXS is NOT flat, and the heavy layers are the GPU ones
Q2: 912.5 MiB per block (1062.5 for block 2). IQ3_XXS: 637.5–1137.5 MiB, and the late blocks
(which `-ncmoe N` leaves on GPU: N..47) are the heavy ones. GPU-resident expert MiB:
| ncmoe | 42 | 43 | 44 | 45 | 46 | 47 |
|---|---|---|---|---|---|---|
| Q2 | 5475 | 4563 | 3650 | 2738 | 1825 | 913 |
| IQ3_XXS | 6025 | 5063 | 3925 | 2863 | 2025 | 1063 |
| Δ | +550 | +500 | +275 | +125 | +200 | +150 |
Non-expert GPU-side weights: IQ3 +136 MiB vs Q2. So "per-layer VRAM" for IQ3 must be
quoted per layer, not as one number; the two-load measurement (C) gives the mean over the
moved layers and is checked against this table.
Prediction from v1 Q2 peaks (to be verified, different binary): IQ3 needs ncmoe 43 @ub512,
44 @ub1024, 46 @ub2048.

### V6. Machine state
GPU 442 MiB used (kwin 64 + claude-desktop 51), 15489 MiB free. MemAvailable 87.1 GiB, 85 GB
buff/cache (Q2 warm from the 11:46 check). /mnt/ai 673 G free. Uptime 14 min.
llama-swap was active with nothing loaded (`/running` = []); **stopped at ~11:56**. Ports
9997/9998/9999 free. Shipped config unchanged: `-ncmoe 42 -t 16 -b 2048 -ub 512`, ttl 1800,
config.yaml mtime 2026-10-01 11:10.

### V7. Harness
`harness2.py` = v1 `harness.py` + `--model q2|iq3`, v2 result/state files, a hard abort when
MemAvailable after load < 10 GB, optional FULL in the same load as the 3 reps (`bench --full`,
saves a load per config; peak VRAM is the max over the whole session incl. the full fill),
and new `session`, `cold`, `task02` subcommands. Methodology for P4k/P32k/D0/D32k/FULL is
byte-identical to v1 (same corpus files, nonces, cache_prompt:false, seed).
Session TTFT = server `timings.prompt_ms` (prefill time of the tokens actually processed).

### V8. Corpora for the new tests (built on a Q2 baseline server, exact counts)
First build was rejected by inspection: the generic source pool landed on a hex-dump array
(4061 tokens from 4477 B) and llama-bench result tables, and the session pool on preprocessed
libstdc++ special-function code (~2 B/token). None of that resembles OpenCode traffic. Moved to
`corpus/rejected-v2/`. Rebuilt from curated pools (`src/`, `common/`, `tools/server/` C/C++;
prose from `docs/*.md`, server README), rejecting files with >15% table lines, hex or
line-marker content. Result:
- cold prompts {300, 508, 777, 1016, 1500, 2044, 3000, 4061} templated tokens **exactly**
  (verified through `/apply-template` + `/tokenize`), alternating prose/source, 2.5–3.7 B/token;
  prompt_B templated = 772 tokens (matches v1).
- session: turn 1 = 20,000 tokens, turns 2–16 = 3,000 tokens each, 3.3–4.6 B/token, distinct
  slices of hand-written fork source; one short question per turn (5 rotating).

## Phase A — Q2 re-baseline, new binary (11:59–12:19). COMPLETE
`-ncmoe 42 -b 2048 -ub 512`, 3 reps + FULL in the same load.
P4k 288.0 ±0.1 · P32k 280.0 ±4.5 · TTFT32k 114.5 · D0 37.90 ±0.14 · D32k 30.56 ±0.10 ·
T_turn 163.6 · FULL 120,182 tok, prefill 221.5, decode 19.81, 3/3 needles, stop ·
load 12,590 MiB, **FULL peak 13,020 MiB** (to the MiB what v1 measured) · MemAvail after load 86.4 GiB.
New binary is ~3–5% faster on prefill and decode than v1's (not compared further, per the prompt).

## Phase B — Q2 challenger (12:19–)
### V9. n46 / ub2048 passes the VRAM gate on the patched binary — no n47 retry needed
P4k 590.4 · P32k 558.8 ±15.9 · D0 36.42 ±0.16 · D32k 29.50 ±0.08 · T_turn 108.2 (−33.8% vs A) ·
FULL prefill 351.2, decode 18.83, 3/3 needles, stop · load 9,558 · **FULL peak 12,486 MiB**
(914 MiB margin; v1: 12,484). The surcharge model from v1 holds on the new binary.
D0 96.1% / D32k 96.6% of A — the ~1%/layer cost of 4 more CPU layers, as v1 found.
### V10. n43 / ub1024 (fallback) also passes
P4k 426.8 · P32k 409.9 ±10.5 · D0 37.66 ±0.18 · D32k 30.34 ±0.02 · T_turn 127.7 (−22.0%) ·
FULL 297.8 / 19.86, 3/3, stop · load 11,884 · **FULL peak 13,070 MiB** (330 margin; v1: 13,070).

## Phase D — session test
### V11. Prefix reuse holds in the growing session — no `--reasoning-preserve` needed
Q2 n46/ub2048, turns 2–4: prompt_n 3036 / 3032 / 3036 for 3,000 appended tokens + question;
depth grows by prompt_n + 800 generated each turn, i.e. the previous assistant turn
(reasoning included) is served from cache, not re-prefilled. Turns stop on `length` at the
800-token cap as designed (turn 1 reached content; later turns are all reasoning at 800).
### V12. Q2 sessions: ub2048 is worth 8.8% of session time, not 34%
| Q2 config | session_s | Σ TTFT | Σ 1500/decode | turn-16 depth | turn-16 decode | peak MiB |
|---|---|---|---|---|---|---|
| n46 / ub2048 | **1046.1** | 160.2 | 885.9 | 77,700 | 23.60 | 11,058 |
| n42 / ub512 (shipped) | 1146.7 | 285.4 | 861.3 | 76,904 | 24.17 | 12,728 |
In a growing session prefill is only ~3k tokens per turn, so the decode term dominates
(85% of session_s at ub2048). ub2048 buys −125 s of prefill and pays +25 s of decode
(4 more CPU expert layers). The 34% T_turn figure describes a fresh 32k prompt, which is not
how Zef uses flashnext. Net: −100.6 s = −8.8% — real (>3%), but a quarter of the T_turn story.
Caveat: generation length is capped at 800 but a few turns stopped early (`stop` at 140–769
tokens), so their decode rate is measured over < 500 tokens. Different models/configs stop at
different turns; effect on session_s is < 1% (checked in the report).

## Phase E — cold-start robustness
### V13. Q2 n46 / ub2048: 11/11 cold starts OK — the ub crash is fixed on this binary
Fresh server, no warm-up, first request = {300, 508, 777, 1016, 1500, 2044, 3000, 4061} tokens
(prompt_n matched every target exactly) + prompt_B ×3 (772 tok, the v1 crasher). No abort, no
CUDA error in any log, server alive after each request. v1's 8/8 crash on prompt_B at ub ≥ 768
does not reproduce.

## Phase F — Task 02
### V14. Q2 n46 / ub2048 passes gate 4 (cold server, no warm-up, max_tokens 60000)
`stop` after 55,086 generated tokens (29.9 t/s, 1844 s), all four files extracted.
PROBE 1 PASS · 2 PASS · 3 PASS · 5 PASS · 4 FAIL (threshold 0 / −1 trip on first failure — the
standing crit-7 control). Same probe profile as v1's ub512 baseline. No crash.
**Best Q2 = n46 / ub2048** (passes gates 1–4, fastest Q2 session).

## Phase C — IQ3_XXS ladder (13:48–)
### V15. IQ3_XXS per-layer VRAM: measured = GGUF expert bytes, to the MiB
Load VRAM at ub512 (MiB): n42 13532 · n43 12570 · n44 11432 · n46 9532 · n47 8570.
Steps: 42→43 **962** (block 42 = 962.5) · 43→44 **1138** (block 43 = 1137.5) · 44→46 **1900**
(blocks 44+45 = 1062.5+837.5) · 46→47 **962** (block 46 = 962.5). Mean over blocks 42–46 =
992 MiB/layer vs Q2's flat 912. First IQ3 load (cold page cache) took 24 s; MemAvailable before
it 87.8 GiB. At equal ncmoe IQ3 loads +942 MiB vs Q2 at n42 (+550 expert, +392 non-expert/
buffers), +592 at n46/ub2048 (10150 vs 9558). Also measured: n44/ub1024 11638, n46/ub2048 10150.
Prediction (load + v2-measured Q2 surcharge +430/+1186/+2928):
ub512 → **n43** (≈13,000; n42 ≈13,962 ✗) · ub1024 → **n44** (≈12,824; n43 ≈13,962 ✗) ·
ub2048 → **n46** (≈13,078; n45 ≈13,916 ✗). Verified by FULL below, one retry at +1 each.
Same CUDA0 compute-buffer misprediction warning as v1 on IQ3 (1398 vs 1105 MiB expected).
### V16. IQ3 ladder results (FULL in the same load as the 3 reps)
- **ub2048 n46: PASS**, FULL peak 12,978 (predicted 13,078). P4k 612.2 · P32k 576.9 ±17.5 ·
  D0 34.83 ±0.19 · D32k 28.42 ±0.09 · T_turn 108.4 · FULL 371.1 / 19.01, 3/3, stop.
- **ub512 n43: PASS**, FULL peak 12,906 (predicted 13,000). P4k 297.6 · P32k 291.0 ±5.2 ·
  D0 36.00 ±0.13 · D32k 29.27 ±0.01 · T_turn 161.4 · FULL 227.9 / 19.21, 3/3, stop.
n45/ub2048 and n42/ub512 were not run: predicted 13,916 / 13,962 (≥ 500 MiB over the gate,
more than 2× allocator noise), so "lowest passing" is established by prediction + the passing
rung, consistent with the per-layer table being exact.
Observation: IQ3 prefill is *faster* than Q2 at the same ub (ub2048: 576.9 vs 558.8 P32k,
371 vs 351 FULL) — the GPU-resident layers do the prefill matmuls and IQ3's CPU-resident early
blocks are lighter (637–912 MiB vs 912), so less CPU→GPU weight traffic per ubatch.
Decode is slower at short context (D0 −4.4% at n46/ub2048) but the gap closes at depth
(FULL decode 19.01 vs 18.83) — attention cost, which is quant-independent, dominates there.
- **ub1024 n44: PASS**, FULL peak 12,732 (predicted 12,824). P4k 442.6 · P32k 424.4 ±12.7 · D0 35.66 ±0.11 · D32k 28.99 ±0.10 · T_turn 127.3 · FULL 307.5 / 19.26, 3/3, stop.
- IQ3 sessions: n46/ub2048 **1077.2** · n44/ub1024 1105.3 · n43/ub512 1173.1 → **best IQ3 = n46/ub2048**.

### V17. Session comparison, best vs best
| | session_s | Σ TTFT | Σ decode term | turn-1 TTFT (20k) | turn-16 decode | peak |
|---|---|---|---|---|---|---|
| Q2 n46/ub2048 | 1046.1 | 160.2 | 885.9 | 35.0 | 23.60 | 11,058 |
| IQ3 n46/ub2048 | 1077.2 | 157.1 | 920.1 | 33.7 | 22.82 | 11,568 |
| ratio | **1.030** | 0.98 | 1.039 | 0.96 | 0.967 | |
+2.97% — under §7's 3% floor, so formally "no difference" on one rep each; the decode term
(+3.9%) is consistent with D0/D32k (−4.4% / −3.7%, both ≫ 2 sd) and is where all of IQ3's
extra time goes; prefill is 2% *faster*. Either reading is far inside the 1.10× threshold, so
no second session rep was run (it could not change the decision).
Early-stopped turns (< 500 generated tokens) change session_s by ≤ 0.13% when their decode
rate is replaced by the neighbours' mean (`session-analysis.py`).

### V18. IQ3 n46 / ub2048 cold-start: 11/11 OK, prompt_n exact on every item (same tokenizer).

### V19. IQ3 n46 / ub2048 Task 02 run 1: gate 4 FAILS as written — on module placement, not logic
`stop` after 35,806 tokens (30.9 t/s, 1163 s), all four files extracted (verified against the
raw response: extraction is faithful). `probe.py` dies at PROBE 1 with
`NameError: name 'NOTIFIER' is not defined` (circuit_breaker.py:73).
Cause: the model declared `NOTIFIER: Notifier` — a bare annotation, which binds nothing —
**inside circuit_breaker.py** and calls the bare name there, whereas the prompt introduces
NOTIFIER in the breaker_events.py section and the probe (and Q2, in every run on record)
assigns `breaker_events.NOTIFIER`. Its breaker_events.py docstring says only "the deployment
must provide a module-level NOTIFIER" without naming the module.
Diagnostic only (scratch copy, NOT the gate): a probe that also assigns `cb.NOTIFIER` gives
PROBE 1 PASS · 2 PASS · 3 PASS · 5 PASS · 4 FAIL (control) — the identical logic profile to Q2:
mutate-before-notify on both emit paths, caller_state forwarded verbatim.
So: one real spec-reading deviation (code that would raise NameError against the documented
integration point), zero re-entrancy/logic regressions. Gate 4 per the letter = FAIL.
Since time remains well before 05:30, the prompt's optional second run is taken for BOTH models.

## Phase G — 256k at ub512 for the session winner (Q2) (15:41–16:06)
### V20. 256k is reachable at ub512, but only with a 52 MiB margin at the lowest ncmoe
Load VRAM at `-c 262144 -ub 512` (MiB): n42 15036 · n43 14124 · n44 13212 · n45 12298 · n46 11386
(+2446 vs 128k at n42: the KV cache doubles and the compute buffer grows).
FULL at **n45**: 240,183 tokens (91.6% of 262144) · prefill 167.9 t/s · TTFT 1430.6 s (23.8 min)
· decode 12.80 t/s · 3/3 needles exact · `stop` · **peak 13,348 MiB** (surcharge +1050).
Passes the 13,400 gate by **52 MiB** — inside the ~230 MiB allocator noise, so I would not ship
n45; **n46** (predicted peak ≈ 12,436, not measured) is the sane 256k choice if Zef ever wants
it. n44 predicted ≈ 14,262 ✗. ub512 only — it is not a speed option (FULL prefill 168 vs 351
t/s for ub2048 at 128k), it is a context option.

## Phase F — second runs (16:06–16:52)
### V21. Second Task 02 run each (cold, no warm-up, max_tokens 60000)
- **Q2 n46/ub2048 run 2: PASS** — `stop` at 33,928 tokens; probes 1,2,3,5 PASS, 4 FAIL (control).
  Q2: **2/2**.
- **IQ3 n46/ub2048 run 2: PASS** — `stop` at 48,221 tokens; probes 1,2,3,5 PASS, 4 FAIL (control);
  NOTIFIER correctly read from `breaker_events`. IQ3: **1/2** literal passes.
No third run: the prompt's protocol is one run, a second if time allows. Running until IQ3
passes again would be cherry-picking, and a 2-of-3 would not erase run 1's failure.
(Same seed, very different lengths — 55k vs 34k on Q2 — so the server is not deterministic
run to run; each run is an independent sample.)

### V22. Provisional rubric (single judge = me, not blind, 1 sample per run)
Convention: as in the eval doc's own 35/36 clean-room score, dead enum-member docstrings are
noted but not docked (they are the doc's "accidental control"). crit 7 = 2/3 in every run (control).
| run | total | deductions |
|---|---|---|
| Q2 r1 | **34/36** | crit 7 −1 (control); crit 9 −1 (`__init__` args undocumented). Dead enum docstrings. |
| Q2 r2 | **34/36** | crit 7 −1; crit 9 −1 (dataclass fields undocumented). |
| IQ3 r1 | **33/36** | crit 7 −1; crit 2 −1 (NameError against the documented integration point); crit 9 −1 (fields undocumented). Dead enum docstrings. |
| IQ3 r2 | **34/36** | crit 7 −1; crit 12 −1 (`emit_call_failed` duplicated in both branches). |
No invented APIs, no broken signatures, no syntax errors in any of the four. On this evidence the
quants are indistinguishable apart from IQ3 r1's NOTIFIER placement.

### V23. Where IQ3's extra decode time goes
At n46 IQ3 keeps **38,900 MiB** of experts on the CPU vs Q2's **42,125 MiB** (−7.7% bytes), yet
D0 is −4.4% and D32k −3.7%. A pure bandwidth model would predict IQ3 ≈ +7% *faster*; it is ~11%
slower per byte moved. That is CPU dequant cost — the IQ2_XXS/IQ2_XS/IQ2_S/IQ3_XXS/IQ3_S codebook
(grid) lookups and the new Q2_0 type — i.e. the lookup-table decode cost ISTA warns about. Prefill
is unaffected (it runs on GPU-resident copies per ubatch) and is 3–6% *faster* on IQ3.

## Decision (no change applied)
- **Best Q2 = n46 / b2048 / ub2048**: gates 1–4 pass (Task 02 2/2), session 1046.1 s.
- **Best IQ3 = n46 / b2048 / ub2048**: gates 1–3 pass, session 1077.2 s = **1.030×** (inside 1.10×),
  but **gate 4 failed on run 1** (1/2). Under §6 ("passes all gates") IQ3 is **not recommended**;
  it is reported as the closest option for Zef with the exact trade-off.

## Finish (16:52–16:55)
GPU empty (527 MiB desktop) → `systemctl --user start llama-swap` → flashnext via :9292,
max_tokens 500 → `PROBE_OK`, `stop`, 34 tokens; `/running` = shipped cmd (Q2, n42/ub512) →
`GET /unload` → `OK`, `/running` = []. No llama-server left. MemAvailable 87.8 GiB.
config.yaml untouched (mtime 2026-10-01 11:10). Nothing applied.
