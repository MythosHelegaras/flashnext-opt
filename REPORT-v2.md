# flashnext v2 — quant decision on the patched fork — REPORT
**2026-10-05 11:53 → 16:55 · Monster · fork `bea3b12d` + mmq.cu #27792 fix, built with GCC 16.2.1**
Nothing was applied. llama-swap is running the original config and is unloaded.

## Verdict
**Quant: UD-Q2_K_XL. Config: `-ncmoe 46 -t 16 -b 2048 -ub 2048`.** It passes every gate and is the fastest session config (−8.8% session time vs shipped).
IQ3_XXS at the same config is only 3.0% slower per session, but it failed Task 02 run 1 (NameError on `NOTIFIER`) and passed run 2. That makes it 1/2 on gate 4, so it is not recommended. It's your call (see Option B).

## Comparison (all v2 binary, 128k, q8_0/q8_0 KV, `-t 16`, 3 reps mean ±sd; FULL/session = 1 rep)

| metric | **Q2 n46 ub2048** (best Q2) | **IQ3 n46 ub2048** (best IQ3) | IQ3 vs Q2 | Q2 n42 ub512 (shipped) |
|---|---|---|---|---|
| P4k t/s | 590.4 ±0.5 | 612.2 ±0.5 | +3.7% | 288.0 ±0.1 |
| P32k t/s | 558.8 ±15.9 | 576.9 ±17.5 | no difference (< 2 sd) | 280.0 ±4.5 |
| D0 t/s | 36.42 ±0.16 | 34.83 ±0.19 | **−4.4%** | 37.90 ±0.14 |
| D32k t/s | 29.50 ±0.08 | 28.42 ±0.09 | **−3.7%** | 30.56 ±0.10 |
| T_turn (32k) s | 108.2 | 108.4 | no difference | 163.6 |
| FULL prefill / decode t/s | 351.2 / 18.83 | 371.1 / 19.01 | +5.7% / no diff. | 221.5 / 19.81 |
| FULL TTFT s (120,182 tok) | 342.2 | 323.9 | | 542.5 |
| FULL needles / finish | 3/3 / stop | 3/3 / stop | | 3/3 / stop |
| load → **FULL peak** MiB | 9,558 → **12,486** | 10,150 → **12,978** | +492 | 12,590 → 13,020 |
| **session_s** | **1046.1** | 1077.2 | **1.030×** | 1146.7 |
|  Σ TTFT / Σ 1500/decode | 160.2 / 885.9 | 157.1 / 920.1 | −2% / **+3.9%** | 285.4 / 861.3 |
| last turn: depth / decode t/s | 77,700 / 23.60 | 77,775 / 22.82 | −3.3% | 76,904 / 24.17 |
| cold-start (8 lengths + prompt_B ×3) | **11/11** | **11/11** | | not re-run† |
| Task 02 B gate 4 (probes 1,2,3,5) | **2/2 PASS** | **1/2** (run 1 FAIL) | | not re-run† |
| Task 02 rubric (provisional) | 34, 34 /36 | 33, 34 /36 | | — |

† The shipped ub512 config was never at risk from the ub bug; v1 passed it on Task 02.

**Session test:** one `/v1/chat/completions` conversation. Turn 1 is 20,000 tokens of hand-written fork source; then 15 turns of +3,000 tokens of source plus a short question; generation capped at 800 tokens. Prefix reuse works on both quants with no extra flags: turns 2–16 prefill 3,029–3,040 tokens each, and the previous assistant turn comes from cache. `--reasoning-preserve` was not needed.

**Where the time goes:** decode is 85% of session time. That is why ub2048's 2× prefill buys only 8.8% here, against a 34% T_turn gain on a fresh 32k prompt.

**IQ3's extra 31 s per session:** all of it is decode.
- IQ3 is −4.4% D0 and −3.7% D32k, despite keeping 7.7% *fewer* expert bytes on the CPU (38.9 GB vs 42.1 GB at n46).
- That works out to ~11% slower per byte moved. This is CPU dequant cost: the IQ2_XXS/XS/S and IQ3_XXS/S codebook lookups plus the new Q2_0 type, i.e. the lookup-table decode cost ISTA warns about.
- Prefill is 3–6% *faster* on IQ3 (the GPU does it, and the early CPU blocks are lighter).
- 1.030× is under §7's 3% floor, so formally "no difference" on session time. Either way it is far inside your 1.10×.
- I can't measure the accuracy gain locally and don't claim one.

## Task 02: the one thing that separates the quants
IQ3 run 1 declared `NOTIFIER: Notifier` as a bare annotation (which binds nothing) inside `circuit_breaker.py` and called the bare name. The prompt places NOTIFIER in the `breaker_events` section, and the probe assigns `breaker_events.NOTIFIER`. So the probe died at once with `NameError` and gate 4 fails as written.
- I checked the extraction against the raw response; it is faithful.
- A diagnostic copy of the probe that also injects into `circuit_breaker` gives probes 1/2/3/5 PASS and probe 4 FAIL. That is the same logic profile as Q2: mutate-before-notify on both emit paths, `caller_state` verbatim.
- So it is a spec-reading/integration slip, not a re-entrancy regression. Q2 has never made it (v1 baseline, both v2 runs, the 2026-09-08 runs).
- IQ3 run 2 put NOTIFIER in `breaker_events` and passed cleanly.
- I stopped at the prompt's two runs. Re-running until it passes would be cherry-picking.

## IQ3_XXS per-layer VRAM and ncmoe ladder
The expert types are a per-layer mix: gate/up are IQ2_XXS/IQ2_XS/IQ2_S/IQ3_XXS/IQ3_S, down is Q2_0/IQ4_NL (full map in `DECISIONS-v2.md` V4). The late blocks, which stay on the GPU, are the heavy ones.
- **Measured load deltas** (MiB): 42→43 **962**, 43→44 **1138**, 44→46 **1900** (two blocks), 46→47 **962**. Each matches the GGUF expert bytes of that block to the MiB.
- **Average over blocks 42–46:** 992 MiB per layer, vs Q2's flat 912.
- **At equal ncmoe** IQ3 loads +942 MiB at n42 and +592 MiB at n46/ub2048.

| ub | lowest passing ncmoe | load MiB | FULL peak MiB | rung below (predicted) | P32k | D0 | D32k | session_s |
|---|---|---|---|---|---|---|---|---|
| 512 | **43** | 12,570 | 12,906 | n42 ≈ 13,962 ✗ | 291.0 | 36.00 | 29.27 | 1173.1 |
| 1024 | **44** | 11,638 | 12,732 | n43 ≈ 13,962 ✗ | 424.4 | 35.66 | 28.99 | 1105.3 |
| 2048 | **46** | 10,150 | 12,978 | n45 ≈ 13,916 ✗ | 576.9 | 34.83 | 28.42 | **1077.2** |

All three predictions (load + Q2-measured surcharge) passed first time, so no +1 retry was needed. The rungs below were predicted ≥ 500 MiB over the gate, more than 2× allocator noise, and were not loaded.

Q2 for reference: n42/ub512 13,020, n43/ub1024 13,070 and n46/ub2048 12,486 MiB peak. These are identical to v1, so the surcharge law holds on the new binary.

## Other results
- **The ub crash is fixed.** Q2 and IQ3 at ub2048 each went 11/11 on cold starts. Every request was the first one on a fresh server with no warm-up. prompt_n matched every target exactly (300…4061, plus prompt_B 772 ×3). v1 crashed 8/8 on prompt_B at ub ≥ 768.
- **Q2 n43/ub1024** (fallback): P32k 409.9, D0 37.66, D32k 30.34, T_turn 127.7, FULL peak 13,070 (330 margin). It passes but is slower than n46/ub2048 everywhere except decode (+3%). No session run.
- **256k (Phase G, Q2, ub512):** n45 loads at 12,298 MiB. A 240,183-token fill gave 3/3 needles and `stop`.
  - Prefill 167.9 t/s, TTFT 23.8 min, decode 12.80 t/s.
  - Peak 13,348 MiB, which passes by only **52 MiB**. That is inside allocator noise, so I would not use n45. Use **n46** (predicted ≈ 12,436, not measured) if you ever want 256k. It is a context option, not a speed option.
- MemAvailable was 86–87 GiB after every load and never below 69 GiB at the end of any run. No run came near the 10 GB abort.

## Crashed / skipped / changed
| item | what happened |
|---|---|
| `PROMPT-v2.md`, `PROMPT.md` | Neither exists. I used `flashnext-overnight-PROMPT-v2.md` and v1's `flashnext-overnight-PROMPT.md`. |
| Run timing | Started at 11:53 in the daytime, not overnight; you asked for it now. I treated HARD_STOP as 07:00 tomorrow. Done by 16:55. |
| First cold/session corpus | Rejected on inspection: hex-dump arrays, llama-bench tables, preprocessed libstdc++ (~2 B/token). Rebuilt from curated `src/ common/ tools/server` source and prose docs. Kept in `corpus/rejected-v2/`. |
| IQ3 Task 02 run 1 | Gate 4 FAIL (NameError, above). No server crashes anywhere tonight. |
| Not run | Q2 n47 (n46 passed). IQ3 n45/ub2048 and n42/ub512 (predicted ≥ 500 MiB over). Q2 ub1024 session. 256k at n46. Cold-start/Task 02 on the shipped ub512 config. |
| Rubric | Provisional: single judge (me), not blind, one sample per run. |

## Apply commands (written, self-tested on a scratch copy, NOT run)
`apply-flashnext-v2.sh` takes the tuning line and optionally a model path. Before writing, it checks that every shard exists and that there are no `.incomplete` files. It then:
- takes a timestamped backup;
- finds the block by key;
- rewrites only the `-ncmoe` line (and the `-m` line, if given);
- proves YAML parses, every other block is identical, ttl 1800 and all mandatory/sampling flags are intact, and the diff is exactly 1 or 2 lines;
- restores the backup on any failure, and prints the rollback command.

**Option A — recommended (Q2, ub2048):** session −8.8% vs shipped; FULL peak 12,486 (534 MiB *below* today's 13,020)
```
bash ~/flashnext-opt/apply-flashnext-v2.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048" && systemctl --user restart llama-swap
```
**Option B — IQ3_XXS, ub2048:** session +3.0% vs A (−6.1% vs shipped), FULL peak 12,978, and Task 02 1/2. Take it if you weigh ISTA's published precision above one NOTIFIER-placement slip in two samples.
```
bash ~/flashnext-opt/apply-flashnext-v2.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048" \
  /mnt/ai/llm/models/qwen3.8-flash-next-gsq/IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf \
  && systemctl --user restart llama-swap
```
**Option C — keep shipped:** do nothing.

Rollback for A/B: the script prints `cp ~/.config/llama-swap/config.yaml.bak-<stamp> ~/.config/llama-swap/config.yaml && systemctl --user restart llama-swap`.
Note: the two models (155 GB) don't fit in page cache together. Switching quant means one cold read of ~76 GB on the first load.

## Finish-phase verification (16:52–16:55)
| check | result |
|---|---|
| test servers | none left; GPU 527 MiB (desktop) / 15,404 free |
| llama-swap | started, active |
| flashnext via `:9292`, max_tokens 500 | `PROBE_OK`, `stop` |
| `/running` | the original shipped cmd (Q2, `-ncmoe 42 -t 16 -b 2048 -ub 512`) |
| `GET /unload` | `OK`, `/running` = [] |
| config.yaml | untouched, mtime 2026-10-01 11:10 |

Raw data:
- `results-v2.jsonl`: every run, full cmd, VRAM, MemAvailable, timings, per-turn session data.
- `DECISIONS-v2.md`: V1–V23.
- `logs/v2-*`, plus `runs/task02-v2-*` with probe outputs.
- `layer-sizes-v2.json`, `session-analysis.py`.
