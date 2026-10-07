# Appendix: Methods and Results for the Qwen3.8-Flash-Next Measurement Series

*Zef Escalante · Companion appendix to "The Benchmark Isn't the Whole Story" · Measurement series complete (Runs 1–4)*

This is the engineer's appendix to the two-part paper (Part 1, the narrative; Part 2, the technical write-up). It is published separately and carries the full methods, every results table, the fact ids, and the open caveats. Bracketed ids like [r2-best-q2] trace to `paper/facts.json`, whose `source_file` fields give the repo-root file and line behind each number; `comparison_table.md` is in the same folder. Section references below (§M*n*, §R*n*) point within this appendix.

**Reading rule for every number here:** absolute speeds are only comparable *within* a run. Run 2 used a rebuilt binary; Run 4 changed the driver and added a second engine. No cross-run speedup is claimed anywhere in this appendix.

---

# A. Methods

## M1. What I was actually trying to do

I run **Qwen3.8-Flash-Next** locally as my day-to-day agentic coding model inside OpenCode. Not through a cloud API — on my own desktop, from GGUF files. The question for the whole series was simple and a bit selfish: *which configuration makes my real sessions faster without making the model worse at the work I actually give it?*

That framing matters for everything below. I didn't optimize for a leaderboard. I optimized for my workflow, and I built the measurements around that — then changed them when they turned out not to reflect it.

## M2. Hardware and software

All four completed runs used the same machine, which I call **Monster** [meth-overnight-unattended; METHOD_PROMPTS.md]:

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 9 9950X (32 threads; shipped config used `-t 16`) |
| RAM | 96 GB DDR5 (~91 GiB usable) |
| GPU | NVIDIA RTX 5070 Ti, 16 GB (16303 MiB reported), sm_120 |
| OS | CachyOS |
| Serving | `llama-server` behind llama-swap; tests ran on a separate port (9997) with llama-swap bypassed |

**Inference engines.** Runs 1–3 used a hand-patched **llama.cpp fork** (`llama.cpp-qwen4exp`, commit `bea3b12d`), which I'll call engine **F**. Run 2 onward used that fork *plus* a one-line CUDA `mmq.cu` patch (#27792 / PR #27044), rebuilt with GCC 16.2.1 [r2-patch-fixes-crash]. Run 4 added **mainline** llama.cpp (`llama.cpp-flashnext`, build 11455, `abeada335`), engine **M**, and re-baselined F on the then-current driver (615.71, CUDA 13.4) [r4-engine-m; REPORT-v4.md].

**Model files (GGUF).**

| Quant | On-disk size | Notes |
|---|---|---|
| **UD-Q2_K_XL** ("Q2") | 78.86 GB (3 shards) | Used in all runs |
| **GSQ-RCO IQ3_XXS** ("IQ3") | 75.83 GB (2 shards) | Runs 2–3 only. The name implies a 3.00 bpw whole-file target, but per-layer expert types are mixed [r2-iq3-smaller-disk] |
| MTP draft head (Q4_K_M) | 2,786,204,800 B, sha256 `8087dbb3…a90231` | Run 4 only [r4-mtp-head-hash] |

Yes — the "3-bit" file is *smaller* than the "2-bit" file. Keep that in mind for the results.

**Fixed flags across runs** [METHOD_PROMPTS.md]: `LLAMA_ATTN_ROT_DISABLE=1`, `-ot per_layer_token_embd=CPU`, `-ngl 999`, `-fa on`, `-np 1`, `--jinja`, KV cache `q8_0/q8_0`, context `-c 131072` unless a 256k probe was the point. The main knobs were `-ncmoe` (how many MoE expert layers live on CPU) and `-b/-ub` (batch / micro-batch). On M, the rotation-disable flag was no longer required but I kept it for parity with earlier gates [REPORT-v4.md].

## M3. How the runs were executed: an unattended agent with a short leash

Each run was a written mission brief handed to Claude Code, which then drove the benchmarks **unattended on Monster** [meth-overnight-unattended]. Run 1 was a true overnight session (2026-09-28 23:37 → 09-29 04:30, per the `REPORT.md` header); Runs 2–4 ran unattended during the day (Run 2: 10-05 11:53–16:55; Run 3: 10-05 17:01–22:30; Run 4: 10-06 11:50–15:45, with follow-on 256k rows through ~18:48) [run-1..4.md]. So "overnight" describes the protocol more than the clock.

The leash, in all briefs [METHOD_PROMPTS.md]:

- no `sudo`, no downloads, no rebuilding production binaries (with stated exceptions),
- tests only on port 9997; long jobs detached (`setsid nohup`) with resumable state files,
- a **HARD_STOP** (typically 07:00 local) by which llama-swap had to be restored and working,
- every decision logged in a `DECISIONS` file, a `REPORT`, and raw per-request `results.jsonl` (all in the repo root).

**Apply policy — this changed, on purpose.** In Run 1 the agent was *allowed* to apply a winning config to production if every gate passed (none did). From Run 2 on, the agent **wrote apply scripts but was forbidden to run them**; I made the call the next morning [meth-apply-policy-v2plus]. I'm the one who has to live with the config, so I'm the one who flips the switch.

## M4. The question each run asked

| Run | Brief | Question | Primary metric | Agent may apply? |
|---|---|---|---|---|
| 1 | v1 | Best flashnext config vs. shipped (Q2 only) | `T_turn` | Yes, if all gates pass |
| 2 | v2 | Q2 vs IQ3 on the patched fork | `session_s` | No |
| 3 | v3 | Does Qwen's recommended temp 1.0 beat my temp 0.3 on Task 02? | Gate-4 pass rate + reasoning length | No |
| 4 | v4 | Fork F vs mainline M; then MTP on M (Q2 only) | `session_s` | No |

Source: METHOD_PROMPTS.md prompt→run map.

## M5. Speed metrics: from `T_turn` to `session_s`

All speed numbers come from `llama-server` API timings. The fork shipped no `llama-bench` or `llama-perplexity`, and the brief forbade building them [r1-method-api-timings]. Timed requests used a unique nonce and `cache_prompt:false` so nothing got a free ride from the cache; each config got 3 reps plus a **FULL** window fill (≥ 90% of the context, ~120k tokens at 128k) in the same load [REPORT.md].

Shorthand used throughout: **P4k / P32k** = prefill t/s at 4k / 32k prompt; **D0 / D32k** = decode t/s at empty / 32k context; **FULL pref/dec** = prefill/decode at the full-window fill; **TTFT32k** = time to first token on a 32k prompt.

**Run 1 metric — `T_turn`.** A synthetic "one agentic turn":

```
T_turn = TTFT32k + 1500 / D32k
```

i.e., prefill a fresh 32k prompt, then decode 1,500 tokens.

**Run 2+ metric — `session_s`.** After Run 1 I realized `T_turn` doesn't look like how I work. My OpenCode sessions *grow*: each turn adds a few thousand tokens to a long context that's mostly reused (Run 1 measured 96.30% prefix reuse on a follow-up after a 60k turn [r1-prefix-reuse]). So from Run 2 the primary metric became a growing multi-turn session — a 20k-token start followed by 15 turns of ~3k tokens each [meth-metric-shift-session; METHOD_PROMPTS.md v2]:

```
session_s = Σ TTFT_turn + Σ (1500 / decode_tps_turn)
```

Honest caveat: `session_s` is still a *model* of a session — measured TTFT and decode rates per turn, combined with an assumed 1,500 output tokens per turn. It's much closer to real use than `T_turn`, but it is not a stopwatch on a real OpenCode session.

**Don't compare across binaries.** Run 2 used a rebuilt binary, and Run 4 a new driver and a second engine. The briefs explicitly forbade comparing absolute t/s across those boundaries; I only compare *within* a run [comparison_table.md header]. Run 4 re-measured F on the new driver so the engine comparison has a same-day base.

## M6. Gates: what a config had to survive before speed counted at all

A config was only *eligible* if it cleared every gate. Speed came after.

| Gate | Definition | Introduced |
|---|---|---|
| **VRAM** | Peak process VRAM **after a full-window fill** ≤ **13,400 MiB**. Load-time VRAM is only a pre-filter. | v1, kept through v4 [meth-vram-gate-13400] |
| **Context / needles** | `-c` ≥ 131072; FULL fill ≥ 90%; 3/3 needle retrievals; `finish_reason: stop` | v1 |
| **Cold starts** | **11/11** cold starts with no warm-up: prompt lengths {300, 508, 777, 1016, 1500, 2044, 3000, 4061} plus Task 02 `prompt_B` ×3 | v2 (replaced v1's single sanity check) [meth-coldstart-11] |
| **Task 02 / Gate 4** | Probes 1, 2, 3, 5 all PASS (§M7) | v1 onward [meth-task02-gate4] |
| **Speed (v1)** | `T_turn` ≥ 5% better than baseline *and* > 2× sd; D0/D32k and FULL ≥ 95% of baseline | v1 only |
| **IQ3 acceptance (v2)** | All gates pass *and* `session_s` ≤ **1.10×** best Q2 | v2 [meth-iq3-accept-110] |
| **Engine M acceptance (v4)** | Gates pass *and* `session_s` ≤ F; a tie goes to M (to retire the hand-patched fork) | v4 |
| **256k tie rule (v1)** | 256k preferred only within 2% of 128k | v1 |

Why 13,400 MiB on a 16 GB card: it leaves room for the desktop and everything else running on the GPU. In Run 1, the shipped baseline peaked at 13,020 MiB — just **380 MiB** of headroom [r1-assumption-vram-gate]. That gate was the binding constraint of the first night.

Why cold starts: the Run 1 failure (§R2) only appeared when Task 02's prompt was the *first* request into a fresh server. A warm-up request hid it. So from Run 2, no warm-ups [meth-coldstart-11].

## M7. Task 02: the quality gate

I don't use a quiz to judge quality. I use **Task 02**: one prompt (**Prompt B**) asks the model to write a **four-file Python circuit-breaker package** — `breaker_state.py`, `call_context.py`, `breaker_events.py`, `circuit_breaker.py` — and then a separate `probe.py` scores what it wrote, mechanically [meth-task02-what; TASK02_GATE.md]. Prompt B is Prompt A plus a short "invariant discipline" clause. The full text of Prompts A and B is in `inputs/flashnext-eval-python-task02.md`; Prompt B exactly as sent is in `corpus/cold/B.json`.

**Clean room.** The run directory starts empty. Prompt and probe live outside it during generation, and the probe is copied in only at score time; a probe sitting in the working directory during generation counts as contamination. Response, reasoning and timings go to a sibling `.meta` directory [meth-task02-cleanroom].

**Probes and Gate 4.** Probes 1, 2, 3 and 5 are scored; **Gate 4 passes only if all four PASS**. Probe 4 is a standing control that is *supposed* to trip, and it's recorded as `FAIL_expected` [meth-task02-gate4].

**Budget.** The Run 1 baseline scored run took **58,765** generated tokens, **1,921.3 s** wall (~32 min), a 772-token templated prompt, and ended on `stop` with all probes as expected [meth-task02-baseline-budget]. An earlier attempt at `max_tokens` 16k voided on length. So the budget became **60,000** tokens, and from v2 it's written into the brief.

**NOTIFIER: the ambiguity I didn't know I'd written.** Prompt B introduces a `NOTIFIER` symbol in the `breaker_events` *section* of the spec, but it never explicitly says which module must bind it. The probe expects `breaker_events.NOTIFIER`. A model that puts a bare annotation in `circuit_breaker.py` and calls the bare name gets a `NameError` → Gate 4 FAIL [TASK02_GATE.md].

To tell "wrong logic" apart from "right logic, wrong module," the Run 3 harness (`task02_v3.py`) added:
- a **diagnostic score** that also injects `circuit_breaker.NOTIFIER`. Its docstring says "Diagnostic only … Never the gate," and I stuck to that [meth-notifier-diag-not-gate];
- an AST-based **NOTIFIER map** that classifies each output as bound / annotation-only / imported / read;
- `/slots` checks during and after every request, to confirm the sampling settings actually applied (otherwise the run is void);
- a fixed code-block extractor (W9; §R4.4).

**Prompt caveat.** Every Gate-4 result in this paper used Prompt B. A clearer prompt would add one explicit sentence that NOTIFIER lives in `breaker_events`, so a Gate-4 failure means a real error rather than my spec being vague. Read every Gate-4 number here with that in mind.

## M8. The noise rule and how I read small numbers

From v1 on: **a difference under 3%, or under 2× the combined sd, gets reported as "no difference"** [meth-noise-rule]. "No change" counts as a legitimate result for a night. For Task 02 cells with n = 3, the v3 brief says it plainly: one flip is not a trend. Where pass/void counts are compared, I report two-sided Fisher exact p-values, and I'm not claiming significance for any of them.

## M9. Experiment designs by run

**Run 1 — config search (Q2 only, F unpatched).** Phases: preflight → baseline → batch/ubatch × ncmoe ladder (plus threads and a 256k probe) → KV fidelity (q8 vs f16 vs f16-K/q8-V, 256 points each against an f16 reference with an f16-reload noise floor) → load mode (`mmap` vs `-lm none`) → multi-turn prefix reuse → Task 02 sanity and crash isolation → finish [REPORT.md]. Out of scope that night: q4_0 KV, MTP, sampling, context < 131072, and Q3 weights.

**Run 2 — quant decision (patched F).** Q2 re-baseline → Q2 challengers → session → 11 cold starts → Task 02 → IQ3 ladder and sessions → 256k at ub512 → a second Task 02 per quant (so 2 scored Task 02 runs per quant) [REPORT-v2.md]. Decision rule: IQ3 only if it passes every gate *and* lands within 1.10× of Q2's `session_s`. I'd have accepted up to 10% slower for IQ3's *published* precision. I couldn't measure that precision locally, though; Task 02 can only catch a regression.

**Run 3 — sampling.** Both quants were fixed at n46/b2048/ub2048 on the Run 2 binary. I compared Qwen's recommended **temp 1.0 (min_p 0)** with my standing **temp 0.3**, with sampling overridden per request and verified via `/slots`. That's 3 scored runs per quant at temp 1.0 with a different seed each; temp 0.3 used seed 20260929 [REPORT-v3.md]. Cold server, `max_tokens` 60000. **Design caveat:** the temp 0.3 cells *pooled in* Run 2's two Task 02 runs per quant (Run 2 phases F/F2), so they aren't independent of Run 2. Some attempts voided (hit the 60k cap); voids count as attempts, not scored samples. The Q2 t0.3 4th run was skipped for HARD_STOP.

**Run 4 — engine + MTP (Q2 only).**
- *Engine:* F vs M with identical flags (n46/b2048/ub2048, 128k), F re-baselined same-day. M wins if it passes gates and `session_s` ≤ F; ties go to M.
- *MTP:* only on M. The v1 note that "MTP was measured slower" came from an older experimental patch, not the merged PR 29761, so it was treated as not applicable. I swept draft `n-max` ∈ {1, 2, 3} (draft depth, sometimes written k; rep 1 each), then gave the winner extra reps (3 total). To make room for the draft head, the MTP config moved one expert layer to CPU (**n47**) and put the draft experts on CPU (`--spec-draft-cpu-moe`). To be accepted, MTP had to beat M alone on `session_s` by more than noise [r4-mtp-yes; REPORT-v4.md].
- *256k on M:* ncmoe 47 vs 48 at ub2048, with and without MTP.
- *`--fit`:* tested `--fit on --fit-target 3000` against manual n46 [r4-fit-rejected].

## M10. What I could *not* measure (on purpose or otherwise)

- **No standard accuracy benchmarks** (MMLU or similar) were run. Quality evidence in this paper = Task 02, needle retrieval, and the Run 1 KV top-token agreement check. That's it.
- **No KLD tooling** on the fork. The KV fidelity check used API top-token agreement, and mean KL from that is unreliable (top-20 set mismatches inflate it) [r1-kv-q8-stays].
- **No local check of IQ3's published precision advantage**, and no check of accuracy with attention rotation off.
- All runs are **one machine, one model family, my workload.** Treat it as a case study, not a general law.


---

# B. Results

Absolute speeds are **only comparable within a run**: Run 2 used a rebuilt binary, and Run 4 added a new driver and a second engine. Numbers trace to `facts.json` ids [brackets] or `comparison_table.md`.

## R1. Summary

| Run | What I asked | What I found | What changed in production |
|---|---|---|---|
| 1 | Best config vs. shipped | A **−34.56% `T_turn`** candidate that crashed the server on a normal prompt | **Nothing.** NO CHANGE |
| 2 | Q2 vs IQ3 (patched fork) | The patch fixed the crash (11/11 cold). In sessions the ub2048 win was **−8.77%**, not the −34.56% `T_turn` suggested. Q2 won on the gate | Nothing that night. I applied it myself later (before Run 4) |
| 3 | Temp 1.0 vs 0.3 | 1.0 didn't help (3/6 vs 5/6, n.s.). IQ3 hit the 60k cap 4/10 times | Nothing. Keep 0.3 |
| 4 | Fork vs mainline; MTP; 256k | Mainline **−22.86% session**, **−2,004 MiB** peak VRAM; MTP n-max 2 another **−3.94%**; 256k fits at n48 but not together with MTP | Nothing by the agent. After the v4b gating run I applied M, n48, 256k, no MTP myself |

**Table T0. Config evolution: what was live vs. recommended** (comparison_table.md §A)

| Stage | Engine | Quant | ncmoe | ub | temp | Status |
|---|---|---|---|---|---|---|
| Pre-Run 1 shipped | F fork | Q2 | 42 | 512 | 0.3 | Live |
| Run 1 end | F | Q2 | 42 | 512 | 0.3 | **NO CHANGE** (ub crash) |
| Run 2 recommend | F patched | Q2 | 46 | 2048 | 0.3 | Recommended, not applied that night |
| Run 3 recommend | F patched | Q2 | 46 | 2048 | **0.3** (not 1.0) | Sampling confirmed |
| Run 4 start | F | Q2 | 46 | 2048 | 0.3 | Live (Zef applied Run 2 recommendation) [r4-live-already-n46] |
| Run 4 recommend A | **M mainline** | Q2 | **47** | 2048 | 0.3 | **+ MTP n-max 2** — recommended, not applied |
| Run 4 recommend B | M | Q2 | 46 | 2048 | 0.3 | No MTP — recommended, not applied |
| **What I applied (2026-10-06/07)** | **M mainline** | Q2 | **48** | 2048 | 0.3 | **256k context, no MTP.** Applied by me after the v4b gating run passed (`session_s` 825.44 s, 11/11 cold, Task 02 PASS, FULL peak 12,366 MiB). MTP and 256k could not load together at ub 2048, so I chose twice the context over MTP's −3.94% [r4-applied-256k-n48] |

This table is the full config story for the paper: what was live, what each run recommended, and what I applied myself. The series ends with the 256k n48 config running, not with the Run 4 recommendation.

## R2. Run 1 — the −34.56% win I couldn't ship

**Baseline** (shipped: F, Q2, n42/b2048/ub512, 128k): `T_turn` **168.945 s**, P32k 270.14 t/s, D32k 29.863 t/s, FULL peak **13,020 MiB** [r1-baseline-tturn]. Decode fell off a cliff with depth: D0 36.373 → D32k 29.863 (−17.90%) → FULL 18.810 t/s (−48.29% from D0) [r1-decode-decay].

**Table T1. ubatch × ncmoe ladder** (F unpatched, Q2, 128k; comparison_table.md §B)

| Config | P32k t/s | `T_turn` s | vs base | FULL peak MiB | Outcome |
|---|---|---|---|---|---|
| n42 ub512 (shipped) | 270.1 | 168.95 | — | 13,020 | PASS / live |
| n42 ub1024 | 402.9 | 130.33 | −22.86% | 13,982 | FAIL VRAM gate |
| n43 ub1024 (runner-up) | 398.6 | 130.82 | −22.57% | 13,070 | Numbers PASS → **sanity FAIL (crash)** |
| n43 ub2048 | 566.5 | 107.01 | −36.66% | OOM @ 92,202 tok | FAIL |
| n44 ub4096 | 704.1 | 96.52 | −42.87% | OOM @ 61,482 tok | FAIL |
| **n46 ub2048** | 544.5 | **110.55** | **−34.56%** | **12,484** | Numbers PASS → **sanity FAIL (crash)** |

So, on paper: n46/ub2048 was a third faster *and* used 536 MiB *less* peak VRAM than what I was shipping [r1-candidate-blocked]. Then it crashed.

**The blocker.** Any `-ub` above 512 caused a **CUDA illegal memory access** when Task 02's `prompt_B` (772 tokens) was the first request into the server. It reproduced at ub 768/1024/2048 and at ncmoe 42/43/46. Source slices of 650–4,051 tokens ran fine at ub2048, so prompt size wasn't the trigger; it was content-dependent. A 4,061-token warm-up request masked it completely [r1-ub-crash]. Without a cold, real-content first request, the candidate would have passed every numeric gate and shipped.

**Other Run 1 findings:**
- **Load-time VRAM lies.** The full-window surcharge over load was **+430 MiB at ub512** and **+1,186 MiB at ub1024**, not the blanket +308 MiB I'd been assuming [r1-vram-surcharge]. One likely contributor: the fork re-planned the graph every batch (`graphs reused = 0`) and mispredicted its compute buffer (REPORT.md; mechanism inferred, not isolated).
- **KV q8 stays.** q8_0 KV matched the f16 reference top token 96.875% of the time (248 of 256 points). An f16 *reload of itself* only scored 97.656% (250 of 256). That's within noise, so q8 stays [r1-kv-q8-stays].
- **Prefix reuse already works.** After a 60,023-token turn, the follow-up reused **96.30%** of the context (reuse_ratio 0.037) [r1-prefix-reuse]. This is the number that pushed me to the session metric.
- **`-lm none`** got P32k up to 727.5 t/s, but decode fell below the 95% floor and MemAvailable dropped to 5.47 GiB. Rejected. Thread variants had no effect, and 256k at ub2048 n46 OOM'd before 90% fill (REPORT.md).

**Verdict: NO CHANGE.** Config stayed at n42/ub512. The apply script was written and never run [r1-verdict-no-change].

## R3. Run 2 — the patch, the session reality check, and Q2 vs IQ3

**The patch fixed the crash.** With the `mmq.cu` one-liner, Q2 n46/ub2048 went **11/11** on cold starts, including `prompt_B` ×3 [r2-patch-fixes-crash].

**Table T2. Q2 vs IQ3** (patched F, 128k, q8/q8; comparison_table.md §C, REPORT-v2.md)

| Metric | Q2 n46/ub2048 | IQ3 n46/ub2048 | Q2 n42/ub512 (shipped) |
|---|---|---|---|
| P32k t/s | 558.8 | 576.9 | 280.0 |
| D0 t/s | 36.42 | 34.83 (−4.37%) | 37.90 |
| D32k t/s | 29.50 | 28.42 (−3.66%) | 30.56 |
| `T_turn` s | 108.2 | 108.4 | 163.6 |
| FULL pref / dec t/s | 351.2 / 18.83 | 371.1 / 19.01 | 221.5 / 19.81 |
| FULL peak MiB | **12,486** | 12,978 | 13,020 |
| **`session_s`** | **1,046.14** | 1,077.22 (**+2.97%**) | 1,146.73 |
| Cold starts | 11/11 | 11/11 | — |
| Task 02 Gate 4 | **2/2** | **1/2** | — |

### R3.1 The gap between `T_turn` and `session_s`

Same change (n42/ub512 → n46/ub2048), two metrics:

| Metric | Shipped | n46/ub2048 | Δ |
|---|---|---|---|
| `T_turn` (synthetic fresh 32k) | 163.6 s | 108.2 s | **−33.86%** |
| `session_s` (growing session) | 1,146.73 s | 1,046.14 s | **−8.77%** |

[r2-session-vs-tturn; r2-best-q2]

The big ubatch is basically a *prefill* win. In a growing session most of the context is reused, so prefill barely matters and decode makes up ~85% of `session_s`. The win is real, but it's roughly a quarter of what the headline metric said. If I'd kept optimizing `T_turn`, I'd have been optimizing for a workload I don't have.

### R3.2 Q2 vs IQ3

On speed, IQ3 came in at +2.97% vs Q2 on `session_s` (one rep each). That's inside my 3% noise floor (so "no difference"), and well inside the 1.10× I'd agreed to accept for IQ3 [r2-iq3-close-but-gate4]. It had faster prefill, slower decode (−4.37% D0), and 492 MiB more peak VRAM. Its per-layer VRAM also wasn't flat (637.5–1,137.5 MiB per layer vs a flat 912 MiB for Q2 in Run 1), with the late GPU layers heavier (REPORT.md, REPORT-v2.md).

On the gate, it went **1/2**. The failed run put a bare `NOTIFIER` annotation in `circuit_breaker.py` → `NameError`. The diagnostic probe passed it, so the logic was right and the placement was wrong [r2-iq3-notifier].

The decision rule requires *all* gates, so IQ3 wasn't recommended. **Verdict: Q2, n46/b2048/ub2048**, recommended, not applied by the agent [r2-verdict-q2]. (I applied it myself before Run 4 [r4-live-already-n46].)

**256k on the patched fork:** at ub512 n45, a 240,183-token fill peaked at **13,348 MiB**, a 52 MiB margin, with prefill at 167.9 t/s. Reachable, but I wouldn't ship it [r2-256k-ub512].

> Provisional rubric scores in the Run 2 REPORT (Q2 34/36, 34/36; IQ3 33/36, 34/36) are not part of the gate and are not used here.

## R4. Run 3 — Does the vendor's temperature help? Not here

**Table T3. Task 02 by quant × temperature** (F patched, n46/ub2048; REPORT-v3.md)

| Quant | Temp | Gate 4 pass | Voids @60k / attempts | Mean reasoning tok (±sd) | Mean content tok |
|---|---|---|---|---|---|
| Q2 | 0.3 | **3/3** | 0/3 | 42,649 ±10,405 | 1,884 |
| Q2 | 1.0 | 2/3 | 0/3 | 36,688 ±7,505 | 2,497 |
| IQ3 | 0.3 | 2/3 | **3/6** | 43,371 ±8,126 | 1,717 |
| IQ3 | 1.0 | 1/3 | 1/4 | 34,424 ±1,810 | 1,998 |

Note: the t0.3 cells include Run 2's two Task 02 runs per quant (§M9).

### R4.1 Pass rate

Pooled across quants: **temp 0.3 = 5/6**, **temp 1.0 = 3/6**. Fisher exact p ≈ 0.55. **Not statistically significant**, and with n = 3 per cell it can't be [r3-temp10-no-help]. What I *can* say is that every comparison pointed the same way, and nothing suggested that 1.0 helps. So I'm staying at 0.3. It's a "no evidence of benefit" call, not a "proven worse" claim.

Temp 1.0 produced shorter reasoning on average in both quants. Shorter thinking didn't buy more passes.

### R4.2 Every failure was the same failure

All **4** Gate-4 failures were the same thing: NOTIFIER bound in the wrong module. The diagnostic probe passed the logic **every time** [r3-notifier-all-fails]. This is also where **Q2 made its first NOTIFIER slip on record** (temp 1.0, run 3). That retires Run 2's "Q2 never makes this mistake" observation. My best read is that this is my prompt's ambiguity interacting with sampling, not one quant being dumber than the other. A clearer prompt would name the binding module; every Gate-4 number here should be read under the prompt I actually used.

### R4.3 IQ3 overthinks

IQ3 hit the 60k length cap on **4/10** attempts, vs Q2 **0/6** (Fisher p ≈ 0.23, n.s.) [r3-iq3-overthink]. Reading the voids, they're self-audit spirals, not hard repetition loops. Not significant, but it's expensive in practice:

**Table T4. Time cost per *passing* Task 02, counting voided attempts** (tokens ÷ a common decode rate; not measured wall-clock) [r3-cost-per-pass]

| Cell | Seconds per pass |
|---|---|
| Q2 temp 0.3 | **~1,437** (~24 min) |
| Q2 temp 1.0 | ~1,896 (~32 min) |
| IQ3 either temp | ~5,500–5,640 (~92–94 min) |

Caveat: with this few passes, a single flip moves these numbers a lot. Read them as orders of magnitude.

### R4.4 A bug in my harness, not the model

The code extractor took the *first* code block that named a file. In one run, a 3-line usage snippet "stole" `circuit_breaker.py`. I fixed it and re-scored that run offline. It still FAILED, on NOTIFIER, and earlier runs were byte-identical after the fix [r3-harness-bug].

**Side finding:** my OpenCode config had `limit.output: 32768`. Typical Task 02 answers run 32–55k tokens, so that cap would cut most of them off. That's probably a bigger lever than temperature, and it was out of scope here [r3-opencode-limit].

**Verdict:** keep Q2 n46/ub2048 at temp 0.3; nothing applied [r3-verdict].

## R5. Run 4 — same model, same flags, different engine

At the start of Run 4, production was already F n46/ub2048 (I'd applied the Run 2 recommendation) [r4-live-already-n46]. On the new driver, F re-measured within noise of Run 2 F (`session_s` +0.98%, FULL peak identical) (REPORT-v4.md).

**Table T5. Engine F vs M, and MTP on M** (Q2, 128k, ub2048; comparison_table.md §E, REPORT-v4.md)

| Metric | F n46 | M n46 | M + MTP n-max 2, n47 |
|---|---|---|---|
| P32k t/s | 554.1 | **728.6** (+31.49%) | 677.1 (−7.07% vs M) |
| D0 t/s | 35.77 | **40.13** (+12.19%) | 37.17 (−7.38% vs M) |
| D32k t/s | 29.36 | 35.52 (+20.98%) | 36.54 |
| FULL pref / dec t/s | 357 / 19.22 | 723.5 / 28.13 | 671.8 / **35.53** |
| FULL peak MiB | 12,486 | **10,482** (−2,004) | 12,686 |
| Margin to 13,400 gate | 914 | **2,918** | 714 |
| **`session_s`** | 1,056.39 | **814.87 ±1.9** (−22.86%) | **782.78 ±8.48** (−3.94% vs M) |
| Cold starts | (11/11 in Run 2) | 11/11 | 11/11 |
| Task 02 Gate 4 | (PASS in Run 2) | PASS | PASS |

### R5.1 Engine M

Same weights and same flags, and mainline was **22.86% faster per session** with **~2 GB less peak VRAM** at full window [r4-engine-m]. The gap widened with depth: decode was +12.19% at D0, +20.98% at D32k, and +46.36% at full fill [r4-why-m-faster]. The mechanism looks like memory planning. F's CUDA0 compute buffer grew to **4,469 MiB** at full fill against an expected 1,722, while M's surcharge was fixed at load (**+486 MiB**, the same at 128k and 256k) [r4-why-m-faster]. On Task 02, M read NOTIFIER from `breaker_events` and passed.

That's the biggest single win in the series, and it came from swapping the engine, not from tuning a flag.

### R5.2 MTP

**Table T6. MTP n-max sweep** (rep 1 each; M no-MTP rep 1 = 813.15 s) [r4-mtp-nmax]

| n-max | `session_s` | vs M |
|---|---|---|
| 1 | 839.87 | +3.29% |
| **2** | **792.43** | **−2.55%** |
| 3 | 814.44 | +0.16% |

n-max 2 then got extra reps: **782.78 ±8.48 s** vs M **814.87 ±1.9 s**, i.e. **−3.94%** over 3 reps. That's above the 3% floor, and the 32.1 s gap is larger than 2× the combined sd (~17.4 s). Gates 1–4 passed [r4-mtp-yes].

How to read it:
- **Modest and content-dependent.** Acceptance ran ~62–75% on code and ~43–53% on prose, 66.9% across the session (REPORT-v4.md).
- **It costs you shallow and pays you deep.** −7.38% on D0 and −7.07% on P32k, but FULL decode 35.53 vs 28.13 t/s.
- **Confound:** the MTP config ran at **n47** (one more expert layer on CPU to fit the draft head), and the M baseline ran at n46. The −3.94% is "M+MTP n47 vs M n46," not a pure MTP effect.
- **Tighter on VRAM:** 714 MiB margin vs 2,918.
- Earlier "MTP is slower" folklore on this box came from a different, older experimental patch. This was the merged implementation.

**`--fit`** (`--fit on --fit-target 3000`) came in −1.65% vs manual n46. That's below noise, it's non-deterministic against free VRAM, and it silently aborts when `-ngl/-ot/-ncmoe` are set by hand. Rejected [r4-fit-rejected].

### R5.3 256k on M

**Table T7. 256k context on M, ub2048, no MTP** [r4-256k]

| ncmoe | FULL peak MiB | Margin | FULL pref / dec t/s |
|---|---|---|---|
| 47 | 13,278 | 122 (inside noise, don't ship) | 684.7 / 21.44 |
| **48** | **12,366** | **1,034** | 690.8 / 21.34 |

n48 means all routed experts on CPU. In a follow-on, n48 at 256k measured `session_s` 825.44 s, 11/11 cold, Task 02 PASS (status `v4b-256-n48*`; **at most ~1.30% slower** than M n46 at 128k — under the 3% noise rule, but not identical: 825 s vs 815 ±1.9 s). **MTP + 256k ran out of memory**: n48 + MTP at ub 2048 failed to load (`cudaMalloc` out of memory on a 2,509.67 MiB draft compute buffer; `REPORT-v4.md` line 105, `logs/v4-D-load-n48-mtpk2-256k.server.log`) [r4-256k]. No later test in the repo shows MTP and 256k fitting together.

**Table T7b. 256k snapshots across runs** (comparison_table.md §F; within-run only, different binaries/engines)

| Run | Engine | ub | ncmoe | FULL peak MiB | Notes |
|---|---|---|---|---|---|
| 1 | F | 2048 | 46 | OOM before 90% fill | Not shippable |
| 2 | F patched | 512 | 45 | 13,348 (52 margin) | Reachable, not shippable; prefill 167.9 t/s [r2-256k-ub512] |
| 4 | M | 2048 | 47 | 13,278 (122 margin) | Inside noise; don't ship |
| 4 | M | 2048 | 48 | **12,366** (1,034 margin) | Preferred 256k option; MTP incompatible (OOM) |

**Verdict:** Option A = M + MTP n-max 2 (n47); Option B = M n46 without MTP. The apply script was written, **not run**. llama-swap was still F n46/ub2048 when the run finished [r4-verdict].

**What I applied.** After the v4b gating run passed, I moved llama-swap to M, Q2, n48, ub 2048, `-c 262144`, temp 0.3, no MTP (`apply-flashnext-ctx.sh`, `set-opencode-flashnext-limits.sh`; confirmed live on 2026-10-07) [r4-applied-256k-n48]. MTP and 256k couldn't load together at ub 2048, and I chose twice the context over MTP's −3.94% `session_s`.

## R6. Why Q2 beat IQ3 *here*

The intuition: a "3-bit" quant should be better than a "2-bit" one. Here's what I measured on this box and this task:

| Evidence | Q2 (UD-Q2_K_XL) | IQ3 (GSQ-RCO IQ3_XXS) | Source |
|---|---|---|---|
| File size | 78.86 GB | **75.83 GB** (smaller) | r2-iq3-smaller-disk |
| `session_s` (Run 2) | 1,046.14 s | 1,077.22 s (+2.97%, one rep each: no difference shown) | r2-iq3-close-but-gate4 |
| D0 decode | 36.42 | 34.83 (−4.37%) | Table T2 |
| FULL peak MiB | 12,486 | 12,978 | Table T2 |
| Gate 4, all Prompt B runs | Run 2 2/2; Run 3 t0.3 3/3 (pooled with Run 2), t1.0 2/3 | Run 2 1/2; Run 3 t0.3 2/3 (pooled with Run 2), t1.0 1/3 | Tables T2, T3 |
| 60k voids (Run 3) | 0/6 | 4/10 (p ≈ 0.23) | r3-iq3-overthink |
| Seconds per passing task (voided attempts included) | ~1,437 (t0.3) | ~5,500–5,640 | r3-cost-per-pass |
| Diagnostic (logic) probe on failures | PASS | PASS | r3-notifier-all-fails |

What this does and doesn't mean:
1. **The labels don't tell you much.** "IQ3_XXS" is a whole-file 3.00 bpw *target* with a mix of expert types. It's the smaller file of the two. "Q2 vs Q3" isn't a clean precision ladder for these two files.
2. **IQ3 didn't fail on logic.** Its Gate-4 failures were NOTIFIER placement, and Q2 eventually made the same slip. The difference that actually cost me time was **voids**: running into the 60k cap.
3. **Q2 won on reliability and time-to-a-working-answer, not on statistically proven quality.** None of the quality differences are significant at these sample sizes.
4. I couldn't measure IQ3's published precision gains locally. They may well be real. My gate just can't see them, and it did see the voids.

## R7. Being honest about "no change"

Across four runs the agent changed production **zero** times. Run 1 had the authority to and declined because a gate failed. Runs 2–4 weren't allowed to. Every production change from this series, I applied myself after reading the report. The Run 1 "NO CHANGE" is the result I'm proudest of: a 34.56% win that would have crashed the server on the first real request. The series for this paper ends with what I applied after Run 4: M, Q2, n48, 256k, no MTP. Q2 is the winning path, and the dials that earned it are above.

## R8. Caveats

1. **Don't chain run-to-run speedups.** Run 1 absolute numbers are on an unpatched binary; Run 2 rebuilt it; Run 4 changed the driver and added an engine. "Night 1 → night 4 = X% faster" is not a claim this paper makes.
2. **Sampling results are not significant** (p ≈ 0.55 pass rate; p ≈ 0.23 voids). Direction only.
3. **IQ3 is not "broken."** Logic passed on the diagnostic every time; the failures were integration/placement and voids, under a prompt I've since found to be ambiguous.
4. **M + MTP is not live.** Option A (M + MTP n-max 2 at n47) and Option B (M at n46 without MTP) were the Run 4 recommendations; the agent did not apply them. What I applied is M, Q2, n48, 256k, no MTP, because MTP and 256k could not load together at ub 2048. A future test that fits both would have to be added to the repo before this changes.
5. **`session_s` is a modeled session** (measured TTFT/decode + an assumed 1,500 output tokens per turn), not a stopwatch on real OpenCode use.
6. **Task 02 is one task.** No MMLU or other standard benchmarks were run, and no KLD measurement either.
7. **One box, one model, one workload.** Gate-4 numbers were scored under Prompt B, which I've since recognized as ambiguous on NOTIFIER placement.
8. **Rep counts.** Run 4 M and M+MTP `session_s` are 3-rep means ±sd. Every other `session_s` cell is 1 rep: Run 2 (Q2 and IQ3 at n46/ub2048, Q2 n42/ub512), Run 4 F n46, and the 256k n48 follow-on. The repo README's repetitions table explains how far each single-rep claim holds.

## R9. Fact-id index

| Area | Fact ids |
|---|---|
| Method / gates | meth-overnight-unattended, meth-apply-policy-v2plus, meth-vram-gate-13400, meth-coldstart-11, meth-noise-rule, meth-metric-shift-session, meth-iq3-accept-110, meth-task02-what, meth-task02-gate4, meth-task02-cleanroom, meth-task02-baseline-budget, meth-notifier-diag-not-gate, r1-method-api-timings, r1-assumption-vram-gate |
| Run 1 | r1-baseline-tturn, r1-decode-decay, r1-candidate-blocked, r1-ub-crash, r1-vram-surcharge, r1-kv-q8-stays, r1-prefix-reuse, r1-verdict-no-change |
| Run 2 | r2-patch-fixes-crash, r2-best-q2, r2-session-vs-tturn, r2-iq3-close-but-gate4, r2-iq3-notifier, r2-iq3-smaller-disk, r2-256k-ub512, r2-verdict-q2 |
| Run 3 | r3-temp10-no-help, r3-notifier-all-fails, r3-iq3-overthink, r3-cost-per-pass, r3-harness-bug, r3-opencode-limit, r3-verdict |
| Run 4 | r4-live-already-n46, r4-engine-m, r4-why-m-faster, r4-mtp-nmax, r4-mtp-yes, r4-fit-rejected, r4-256k, r4-mtp-head-hash, r4-verdict, r4-applied-256k-n48 |

Raw files at the root of the [flashnext-opt repo](https://github.com/MythosHelegaras/flashnext-opt) take precedence if any number here is disputed.
