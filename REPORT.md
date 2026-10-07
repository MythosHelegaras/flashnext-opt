# flashnext overnight optimization — REPORT
**2026-09-28 23:37 → 2026-09-29 04:30 · Monster · fork SHA `bea3b12d`**

## Verdict

**NO CHANGE.** The config is exactly as shipped. A candidate was found that is **34.6% faster
per agentic turn at identical accuracy and 536 MiB *less* peak VRAM** — and it must not ship,
because raising `-ub` above the shipped 512 makes llama-server **abort with a CUDA illegal
memory access on an ordinary prompt**, reproduced 8 times across three ubatch
values (768/1024/2048) and three ncmoe values (42/43/46). The entire speed win depends on `-ub > 512`, so the entire speed win is blocked.

## Numbers

| metric | baseline (shipped)<br>`ncmoe 42 ub 512` | **best candidate**<br>`ncmoe 46 ub 2048` | runner-up<br>`ncmoe 43 ub 1024` |
|---|---|---|---|
| P4k t/s | 276.9 | 546.4 | 415.0 |
| P32k t/s | 270.1 ±5.7 | 544.5 | 398.6 |
| TTFT32k s | 118.72 ±2.53 | 58.93 | 80.49 |
| D0 t/s | 36.373 ±0.99 | 35.763 (98.3%) | 36.671 (100.8%) |
| D32k t/s | 29.863 ±0.43 | 29.063 (97.3%) | 29.804 (99.8%) |
| **T_turn s** | **168.94 ±2.63** | **110.55 ±2.14 (−34.6%)** | **130.82 ±2.46 (−22.6%)** |
| FULL prefill t/s | 210.58 | 350.37 (166%) | 284.29 (135%) |
| FULL TTFT s | 570.7 | 343.0 | 422.7 |
| FULL decode t/s | 18.810 | 18.503 (98.4%) | 19.532 (103.8%) |
| load VRAM MiB | 12590 | 9558 | 11884 |
| **FULL peak VRAM MiB** | **13020** | **12484** | 13070 |
| needles / finish | 3/3 exact, `stop` | 3/3 exact, `stop` | 3/3 exact, `stop` |
| **sanity gate (Task 02 B)** | **PASS** (probes 1,2,3,5; 4 = expected control) | **SERVER ABORTS** | **SERVER ABORTS** |

Both candidates clear gates 1, 2 and 3 outright. Both fail gate 4 by killing the process.

## ub / ncmoe trade curve (128k, q8/q8, 3 reps)

| b/ub | lowest ncmoe passing load pre-filter | load MiB | P32k | D0 | D32k | T_turn | FULL peak |
|---|---|---|---|---|---|---|---|
| 2048/512 | 42 | 12590 | 270.1 | 36.373 | 29.863 | 168.94 | 13020 |
| 2048/1024 | 42 | 12796 | 402.9 | 36.853 | 29.579 | 130.33 | **13982 ✗** |
| 2048/1024 | 43 | 11884 | 398.6 | 36.671 | 29.804 | 130.82 | 13070 ✓ |
| 2048/2048 | 43 | 12296 | 566.5 | 36.838 | 29.782 | 107.01 | **OOM @92,202 tok** |
| 2048/2048 | 45 | — | — | — | — | — | 13376 ✓ (24 MiB margin) |
| 2048/2048 | 46 | 9558 | 544.5 | 35.763 | 29.063 | 110.55 | **12484 ✓** |
| 4096/4096 | 44 | 12606 | 704.1 | 36.183 | 29.448 | 96.52 | **OOM @61,482 tok** |
| 4096/4096 | 48 (max) | — | — | — | — | — | **14716 ✗ — no ncmoe can fix** |

Per-CPU-layer VRAM saving is a flat **912 MiB**; each layer costs ~1% decode (42→46 took D0
36.37→35.76). The full-window surcharge over load VRAM is **not constant**: +430 MiB at ub512,
**+1186** at ub1024, **+2926** at ub2048. The transient graph buffer scales as ~ubatch×context
(22.1 and 23.7 bytes per ubatch-token×context-token at the two OOM points), so **load-time VRAM
is worthless as a full-window predictor above ub512** — the prompt's warning was the load-bearing
rule of the night. Prefill also decays with context once ub is raised (ub2048: 566 @32k → 400
@92k; ub4096: 777 @4k → 532 @61k), so the 32k win overstates the full-window win.

## The blocker, in detail

`CUDA error: an illegal memory access was encountered` at `ggml_backend_cuda_synchronize`
← `llama_context::process_ubatch` ← `llama_decode`. Trigger: Task 02 `prompt_B.txt`
(772 tokens of ordinary English + code spec) as the **first inference request after load**.

- **It is `-ub`.** Crashes at ub 768, 1024 and 2048; survives at ub 512 — including at the
  candidate's own `ncmoe 46`. Crashes at `ncmoe 42` with ub 2048. `-ncmoe` is irrelevant.
  **512 (llama.cpp's default) is the only safe ubatch tested.**
- **It is not size.** Source slices of 325, 650, 751, 823, 849, 951, 1352, 2406 and 4051 tokens
  are all fine at ub2048. It is **content-dependent**, so affected prompts cannot be predicted.
- **A ≥4061-token warm-up masks it.** That is why every bench/FULL/probe run tonight passed:
  the harness always warms up first. Without Phase F I would have shipped it.
- Reproducer: `LLAMA_ATTN_ROT_DISABLE=1 llama-server … -ncmoe 42 -t 16 -b 2048 -ub 2048 -c 131072
  --cache-type-k q8_0 --cache-type-v q8_0`, then POST `/mnt/ai/evals/harness/prompt_B.txt` as the
  first request. Logs: `~/flashnext-opt/logs/{T1,T5,T7,W2,W3,V-promptB}*.server.log`.

## Other findings

- **KV type: q8_0 stays.** `llama-perplexity` does not exist in this fork, so KLD was impossible
  (hard rule 3 forbids building it). Instead I measured same-top-token % and KL directly from
  `/completion` logprobs under teacher forcing — 256 positions per KV type, identical contexts.
  Result vs f16/f16: q8_0 **96.88%**, f16-K/q8-V 98.44% — against a **noise floor of 97.66%
  measured between two runs of the identical f16 config**, whose mean KL (0.321) is *higher* than
  q8's (0.256). **The KV types are indistinguishable at this instrument's resolution**, so q8
  stays and the open thread closes: q8 KV cannot be shown to cost anything on this box.
  VRAM at ncmoe 46: q8/q8 9558 · f16/f16 11536 (+1978) · f16-K/q8-V 9700 (+142 — K is nearly free,
  the V side dominates KV memory).
- **Load mode: keep mmap.** `-lm none` is the night's fastest prefill (P32k 727.5, T_turn 98.35)
  but D32k falls to **92.76%** and D0 to 94.75% of baseline — past both the 95% floor and the 5%
  decode ceiling. More importantly it destroys the page-cache story: RssFile 74.82 GB → 0.20 GB,
  so the model's 74 GB stop being shared file-backed cache (flashnext↔coder switching pays full
  disk cost again) and MemAvailable falls from 14.87 GiB after load to **5.47 GiB by end of run**.
- **Prefix reuse: works, no flag needed.** 60,023-token turn = 141.25 s; the follow-up turn on the
  same conversation re-prefilled only **2,218 tokens in 7.39 s** (96.3% reused).
  **Long-context flashnext is interactive, not batch-only.** `--cache-reuse`, `-ctxcp` and `-cram`
  all exist in this build but there is nothing to fix, so nothing was added.
- **256k: no.** At ub2048/ncmoe 46 it matches the best 128k candidate within 0.2%/0.6%/0.6% on
  T_turn/D0/D32k (so §5's 2% tie rule *is* met) then fails the context gate: the 240k fill OOMs at
  **124,970 tokens** needing 4679.78 MiB, and ncmoe is already 46 of a maximum 48. 256k should be
  viable at the shipped ub512 (~+860 MiB surcharge → ~12.7 GB peak) but only at ub512 speeds.
- **`graphs reused = 0` confirmed** on all 10 timed calls, alongside
  `CUDA0 compute buffer size of 2593.09 MiB, does not match expectation of 1722.00 MiB`. The fork
  re-plans its graph every batch and mispredicts its own compute buffer — the mechanism behind both
  the load-vs-peak VRAM gap and the OOMs. Investigated only; no rebuild (hard rule 3).
- **Threads do nothing.** `-t 12` → T_turn 110.92; `-t 16 -tb 32` → 110.06; shipped `-t 16` → 110.55.
  Spread 0.9 s against sd ~2.2 s: no difference. Nothing added.

## Failed / crashed / skipped

| item | why |
|---|---|
| `inputs/` was **empty** | The four "authoritative" docs exist nowhere on disk or in Trash. Proceeded on prompt §2, which restates their facts. Task 02 recovered from `/mnt/ai/evals/harness/` + `eval-task02.sh`. |
| `llama-bench`, `llama-perplexity` | Absent from the fork. All metrics via llama-server + API `timings` (hard rule 3's stated fallback). Forced the Phase C method above. |
| Phase C first attempt | Banked empty distributions: this build returns `completion_probabilities[0].top_logprobs`, not `probs`. Caught by a deliberate smoke test **before** the reference run; parser fixed, all collects redone. |
| Task 02 at `max_tokens 16000` | Void per §7: `finish_reason length`, `content_len 0`, `reasoning_len 74976`. Re-run at 60000; baseline needed **58,765** tokens to reach `stop`. Budget ~60k for this model. |
| ub4096, 256k, `-lm none`, f16 KV, `-t 12`, `-tb 32` | Measured, all rejected on the gates above. |
| `-ncmoe 50` probe | Killed: 48 blocks means `-ncmoe 48` is the maximum, so 50 is a tautology. |
| 256k at ub512 | Not measured — ~20 min of 240k prefill that could not change the verdict (gate 6 needs within 2% of the best 128k; ub512 is 53% off). |
| Tool mishap | `pkill -f <script>` twice matched my own shell and killed it. No measurement lost; GPU verified clean before the next load. Cleanup is by exact PID since. |

## Rollback

**Nothing to roll back.** `~/.config/llama-swap/config.yaml` still has mtime **2026-09-28 23:28:27**
(before this session began at 23:37) and line 112 still reads `-ncmoe 42 -t 16 -b 2048 -ub 512`.
`apply-flashnext.sh` was written and self-validates (backup → edit located by key, never line
number → YAML parse → proves every other model block identical → proves exactly one changed line
→ asserts ttl 1800 and all mandatory/sampling flags), but was **deliberately not run**.
If you ever apply it: `bash apply-flashnext.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048"`, and it prints
`cp ~/.config/llama-swap/config.yaml.bak-<stamp> ~/.config/llama-swap/config.yaml && systemctl --user restart llama-swap`.

## Doc amendments

The named docs do not exist, so these correct the claims as restated in the mission prompt §2:

| claim | replace with |
|---|---|
| "Full-window prefill adds ~+308 MiB after load" | True only at ub512, where it is **+430 MiB**. It is **+1186** at ub1024 and **+2926** at ub2048 — the surcharge scales ~ubatch×context (~22–24 B per ubatch-token×context-token). |
| "Prefill is ~flat above 80k (~226 t/s at 124k with ub 512)" | Flat **only at ub512** (270 @32k → 210.6 @120k). At raised ub it decays steadily: ub2048 566 @32k → 400 @92k; ub4096 777 @4k → 532 @61k. |
| "~1–2% decode per expert layer moved to CPU" | Confirmed at ~**1%**/layer: ncmoe 42→46 moved D0 36.373→35.763 and D32k 29.863→29.063. |
| "~926 MiB per expert layer at 128k/q8" | **912 MiB**, flat from ncmoe 42 to 48. |
| "Tokenization: ~3.1 bytes/token for code" | **2.78** B/token measured on this corpus (89,074 B = 32,000 tokens). |
| "baseline measured 13,046" peak VRAM | **13,020 MiB** tonight — agrees within allocator noise. |
| "Decode decays ~48% from empty to full window" | Confirmed exactly: 36.373 → 18.810 = **−48.3%**. |
| shipped block "no `-b`/`-ub` → defaults 2048/512" | The live config now spells out `-b 2048 -ub 512` (same values). Another session edited flashnext three times at 23:14/23:21/23:28 before this run and restored baseline values; backups corroborate. |
| **new** | `-ub > 512` is unsafe on this fork — see "The blocker". Treat ubatch as pinned at 512 until fixed upstream. |

## For Zef to decide

1. **Chase the ub bug — it is worth 34.6%.** `ncmoe 46 / b 2048 / ub 2048` is faster on every
   speed metric, passes needles and the VRAM gate with 916 MiB to spare (12484 vs 13400), and uses
   **less** VRAM than what ships today. Only the CUDA abort blocks it. Two routes: report it
   upstream with the reproducer above, or make llama-swap fire a ≥4061-token warm-up on load —
   which masked it in 100% of my runs. llama-swap 226 has no warm-up flag (`-config`, `-listen`,
   `-tls-*`, `-watch-config` only), so that would mean wrapping `cmd` in a script. **Untested as a
   fix, and I would not trust a warm-up to *cure* an illegal memory access — it only hid it.**
2. **A prefill-first flashnext exists if you want it.** `-lm none` gives T_turn 98.35 s (−41.8%)
   and P32k 727.5, for 7.2% decode and the page cache. Sensible only if flashnext stops sharing
   the box with coder.
3. **256k is reachable at ub512** if you ever need a 262k window more than speed — predicted
   ~12.7 GB peak at ncmoe 46, unmeasured, and it would keep today's prefill numbers.
4. **`-ncmoe 45 / ub 2048` clears the gate by 24 MiB** (peak 13376 ≤ 13400) against ~230 MiB
   allocator noise, and buys nothing over n46 in prefill (356.0 vs 350.4). I rejected it; flagging
   it only so you know it was measured, not overlooked.

## Finish-phase verification (04:24–04:37)

| check | result |
|---|---|
| llama-swap restarted | active |
| flashnext probe via `:9292`, max_tokens 500 | `PROBE_OK`, `finish_reason: stop` |
| `/running` cmd | the original shipped block, `ttl 1800` |
| full-window needle test **through llama-swap** | 120,134 tokens · 3/3 needles exact · `stop` · prefill 211.10 t/s (vs 210.58 direct — llama-swap adds no overhead) |
| `curl :9292/unload` (GET) | `OK`, `/running` now `[]` |
| llama-server processes | none |
| GPU at handover | 840 MiB (desktop only), 15091 MiB free |
| MemAvailable at handover | 83.2 GiB |
| config.yaml | mtime `2026-09-28 23:28:27`, line 112 `-ncmoe 42 -t 16 -b 2048 -ub 512` — untouched |

Finished 04:37, well inside HARD_STOP 07:00. All six phases (0, A–F) ran; nothing was dropped
for time. Raw data: `results.jsonl` (every run, full command line, VRAM, timings, pass/fail),
`DECISIONS.md` (D1–D30, every decision and surprise with its numbers), `logs/` (server logs
incl. the six crash backtraces), `crashtest{,2,3,4,5}.json`, `kvfid-compare.json`.
