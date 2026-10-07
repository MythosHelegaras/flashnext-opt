# DECISIONS.md — flashnext overnight optimization, 2026-09-28/29

## Phase 0 — Preflight (23:37–23:50)

### D1. Prompt file name
`./PROMPT.md` does not exist. The only prompt in the working dir is
`flashnext-overnight-PROMPT.md` (18118 B, mtime 23:35). Treated as the mission prompt.
A 18801 B copy sits in `~/.local/share/Trash/files/`. Diffed them: the trashed copy is an
EARLIER revision that still contained Q3 weights (old §3) and a whole **Phase G — Q3**.
The live file deliberately removes both ("Q3 and any other weight file are out of scope").
**Decision:** the live file is authoritative. Q3 is not tested, not loaded, not referenced.

### D2. `inputs/` is EMPTY — the four "authoritative" docs do not exist
Searched the whole filesystem: `flashnext-config-2026-09-11.yaml`,
`flashnext-measurements-2026-09-14.md`, `localLLMConfig.md`,
`flashnext-eval-python-task02.md` exist **nowhere** (not on disk, not in Trash).
**Decision:** proceed. §2 of the prompt restates the facts those docs carried, and it is
explicitly labelled "do NOT re-derive". Consequences, recorded honestly:
  - Baseline is measured tonight anyway (Phase A), so the missing measurements doc costs
    nothing — the prompt already forbids comparing against doc numbers.
  - The §8 "doc amendments" deliverable cannot cite line numbers of files that do not
    exist. It will instead state the corrected facts against the §2 claims.

### D3. Phase F is RECOVERABLE despite the missing eval doc
Found the real Task 02 harness at `/mnt/ai/evals/harness/`: `prompt_A.txt`,
`prompt_B.txt`, `probe.py`; driver `/mnt/ai/MoEFinetunning/eval-task02.sh` implements the
clean-room rules (run dir created EMPTY; prompt + probe.py live OUTSIDE it; probe copied
in only at score time). `prompt_B.txt` = `prompt_A.txt` + the 7-line "Invariant
discipline" clause — matching the prompt's description of Prompt B.
A prior scored run (`/mnt/ai/evals/task02-coder-q4-B-20260922-084719/probe.out`) shows
probes 1,2,3,5 PASS and probe 4 FAIL — exactly the standing control the prompt predicts.
**Decision:** Phase F runs with these files, read-only, copied into my own run dirs.

### D4. `llama-bench` and `llama-perplexity` are ABSENT from the fork
`/opt/llama.cpp-qwen4exp/bin/` holds only `llama-cli`, `llama-quantize`, `llama-server`;
`build/bin/` adds only libs. Hard rule 3 forbids building them and forbids using a
mainline binary against this model.
**Decision:** all speed metrics come from llama-server + API `timings` (hard rule 3's
stated fallback). **Phase C's KLD method is impossible** — no `--kl-divergence-base`.
Phase C falls back to the prompt's own weak-signal path (Task 02 B x3 per KV type) and
will be reported as a weak signal, not a measurement.

### D5. Server flags verified present in this build (`--help`, 705 lines)
`-tb/--threads-batch`, `-lm/--load-mode {auto,none,mmap,mlock}`, `-ctxcp/--ctx-checkpoints`
(default 32), `-cms/--checkpoint-min-step` (default 8192), `--cache-reuse` (default 0),
`-cram/--cache-ram` (default 8192 MiB), `-ncmoe`, `-ot`, `-fa [on|off|auto]`.
`--mmap/--no-mmap/--mlock` exist but are DEPRECATED in favour of `--load-mode`.
**Decision:** Phase D A/Bs `--load-mode auto` (shipped default) vs `--load-mode none`.
Phases B/D/E are all executable as written.
Noted but NOT acted on: the `--cache-reuse` help text carries a `https://ggml.ai/f0.png`
"card" link. Not fetched — irrelevant to the task and hard rule 4 forbids downloads.

### D6. Machine state at preflight
Fork SHA `bea3b12daee45876b0129a3602dc8f534ce30bf0` (read-only check).
GPU: RTX 5070 Ti, 16303 MiB total, 13514 MiB used **because llama-swap had flashnext
resident** (pid 299141, 12742 MiB). Desktop holds ~283 MiB (kwin 74 + brave 201 + Xwayland 8)
— under the 1500 MiB threshold, so no special handling.
RAM 91 GiB total, MemAvailable 83375920 kB (79.5 GiB). `/mnt/ai` 683 G free. 32 threads.
llama-swap active since 23:28 on 127.0.0.1:9292. Ports 9997/9998/9999: all free.

### D7. Shipped flashnext block (the baseline, verbatim from config.yaml:105-115)
```
/usr/bin/env LLAMA_ATTN_ROT_DISABLE=1
/opt/llama.cpp-qwen4exp/bin/llama-server --port ${PORT}
-m /mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
-ngl 999 -fa on -np 1 --jinja
-ot per_layer_token_embd=CPU
-ncmoe 42 -t 16 -b 2048 -ub 512
-c 131072 --cache-type-k q8_0 --cache-type-v q8_0
--temp 0.3 --top-p 0.95 --top-k 20
```
ttl: 1800. Model keys in config: fim, coder-q8, coder, flashnext, rag, auditor-gemma.
NOTE vs prompt §2: §2 says "no `-b`/`-ub` -> defaults 2048/512". The live config states
`-b 2048 -ub 512` **explicitly**. Same values, so the baseline is unchanged in substance.
See D8 for why the text is explicit now.

### D8. SOMEONE ELSE SWEPT ub TONIGHT, 20 MINUTES BEFORE I STARTED
`/mnt/ai/evals/flashnext-ub/` + `/mnt/ai/Tests/MoEQ8/flashnext-ub-test.sh` (pre-existing,
not mine) show a sweep at 23:07–23:13 and then three `apply` operations:
  23:14:49 -> ncmoe 44 -b 4096 -ub 4096
  23:21:17 -> ncmoe 43 -b 2048 -ub 2048
  23:28:31 -> ncmoe 42 -b 2048 -ub 512   <- final, i.e. back to baseline values
Config backups at 23:14/23:21/23:28 corroborate. The last apply restored baseline
settings, which is why `-b`/`-ub` are now spelled out.
**Decision:** the config is at baseline in substance -> Phase A baseline is valid, and
hard rule 7 ("read-only until §8") is intact from my side. I did not author those changes.
Their sweep is PRIOR ART I will not blindly trust: its VRAM was read **at load**, its
speed at **16384 tokens**, and every row is marked "tight" (its own PASS bar of >=3000 MiB
free was never met). The prompt requires post-full-window-fill VRAM and 32k/FULL timings.
So I re-measure — but it tells me where to aim:
  ncmoe/ub    proc_MiB  free_MiB  pp t/s (16k)  tg t/s
  42 / 512      12590     2632      269          36.8
  42 / 2048     13208     2027      591          35.9
  43 / 2048     12296     2918      585          37.0
  42 / 4096     14430      815      749          37.1
  43 / 4096     13518     1723      747          37.1
  44 / 4096     12606     2638      741          37.3
Reads as: ub 512->4096 is ~+178% prefill, and the VRAM it costs can be paid back by
+2 ncmoe layers for ~no decode loss. That is the hypothesis Phase B must confirm properly.

## Phase A — Baseline (00:01–00:38). COMPLETE

Shipped config, 3 reps + FULL x1, port 9997, fresh load per run, warm page cache,
discarded warm-up before every timed set, unique leading nonce + `cache_prompt:false`
on every timed request so no rep can reuse another's prefix.

| metric | value |
|---|---|
| P4k | 276.87 t/s (sd 2.55), prompt_n 4061 |
| P32k | 270.14 t/s (sd 5.70), prompt_n 32060 |
| TTFT32k | 118.72 s (sd 2.53) |
| D32k | 29.863 t/s (sd 0.432) |
| D0 | 36.373 t/s (sd 0.993) |
| **T_turn** | **168.945 s** (sd 2.634) |
| load VRAM | 12590 MiB (load 4.0 s — page cache warm) |
| peak VRAM (32k reps) | 12726 MiB |
| FULL prompt_n | 120182 = 91.7% of 131072 -> context gate satisfied |
| FULL prefill | 210.58 t/s |
| FULL TTFT | 570.71 s |
| FULL decode | 18.810 t/s |
| **FULL peak VRAM** | **13020 MiB** |
| needles | early/mid/late all exact, finish_reason `stop` |
| MemAvailable after load | 82.4 GiB |

### D9. Gate thresholds now fixed from tonight's baseline
- Speed gate: T_turn <= 160.50 s (>=5% better) AND improvement > 2x combined sd.
- D0 >= 34.554 t/s, D32k >= 28.370 t/s (95%).
- FULL prefill >= 200.05 t/s, FULL decode >= 17.869 t/s (95%).
- VRAM gate: post-full-fill peak <= 13400 MiB. Baseline sits at 13020 -> **only 380 MiB
  of headroom exists.** This, not speed, is the binding constraint tonight.

### D10. §2's "+308 MiB full-window surcharge" is WRONG — it is +430 MiB
Measured: load 12590 -> FULL peak 13020 = **+430 MiB**. My Phase B load pre-filter was set
at 13400-350 = 13050 MiB before I knew this. Keeping it: it is only a pre-filter, and §6 B.3
already requires the real post-fill FULL measurement plus a retry at ncmoe+1 on violation.
Recorded as a doc amendment. Anything loading in 12970..13050 is at risk of failing the
post-fill gate and will be treated as such.

### D11. Baseline cross-validates the prior session's sweep
Their ncmoe42/ub512 load VRAM was 12590 MiB; mine is 12590 MiB exactly, and their pp 269 t/s
at 16k vs my 270.14 t/s at 32k. Their load-VRAM column is therefore trustworthy as a
pre-filter, which is why I use it to predict where to aim (D8) instead of re-walking every
ncmoe from 42 for every pair. I still load-verify every value I actually use.

### D12. Decode decay measured
D0 36.373 -> D32k 29.863 (-17.9%) -> FULL decode 18.810 (-48.3% from D0). §2's
"~48% from empty to full window" is confirmed precisely.

## Phase B — batch/ubatch x ncmoe (00:09–). THE MAIN EVENT

### D13. ncmoe load-VRAM search at 128k (load-only, 4 s per load, page cache warm)
Per-layer saving is a clean **912 MiB**, dead flat across the whole range.

| b/ub | n42 | n43 | n44 | n45 | lowest <= 13050 |
|---|---|---|---|---|---|
| 2048/512  | 12590 | 11678 | — | — | **42** |
| 2048/1024 | 12796 | 11884 | — | — | **42** |
| 2048/2048 | 13208 | 12296 | 11384 | — | **43** |
| 4096/4096 | 14430 | 13518 | 12606 | 11692 | **44** |

Every value reproduces the prior session's sweep (D8) to the MiB. Their load column is sound.

### D14. THE HEADLINE FINDING: ubatch buys prefill but its cost is paid at LONG context, and
### load-time VRAM does not predict it at all
3-rep timings at each pair's lowest load-passing ncmoe (128k, q8/q8):

| b/ub | ncmoe | P4k | P32k | TTFT32k | D32k | D0 | T_turn | vs base |
|---|---|---|---|---|---|---|---|---|
| 2048/512 (base) | 42 | 276.9 | 270.1 | 118.72 | 29.863 | 36.373 | **168.95** | — |
| 2048/1024 | 42 | — | 402.9 | 79.6 | 29.579 | 36.853 | **130.33** | -22.9% |
| 2048/2048 | 43 | — | 566.5 | 56.6 | 29.782 | 36.838 | **107.01** | -36.7% |
| 4096/4096 | 44 | 711.6 | 704.1 | 45.6 | 29.448 | 36.183 | **96.52** | -42.9% |

Then every one of those three FAILED at the full window — and not for the reason the
pre-filter was watching:
- **ub4096 n44:** CUDA OOM at 61,482 tokens, trying to reserve a single **5309.56 MiB** buffer.
- **ub2048 n43:** CUDA OOM at 92,202 tokens, trying to reserve **4273.28 MiB**.
- **ub1024 n42:** completed, but peak **13982 MiB** > 13400 gate.

The transient graph buffer scales as ~ubatch x context: 5567480192 B /(4096x61482) = 22.1 B
and 4480860544 B /(2048x92202) = 23.7 B per (ubatch-token x context-token). Measured
full-window surcharge over load VRAM: **+430 MiB at ub512, +1186 MiB at ub1024** — versus
§2's blanket "+308 MiB". §2's surcharge figure is only true at the shipped ub512.
**This is why the prompt's "load-time VRAM is NOT a valid predictor" warning is the single
most important rule in the document.** Had I shipped on the load-time pre-filter, flashnext
would OOM the first time OpenCode filled the window.

### D15. Prefill t/s is NOT flat above 80k once ubatch is raised
§2 says "prefill is ~flat above 80k (~226 t/s at ub 512)". True at ub512 (270 @32k ->
210.6 @120k). False at higher ub, where the rate decays steadily as the window fills:
- ub4096: 777 @4k -> 704 @32k -> 636 @32.8k -> 532 @61k (then OOM)
- ub2048: 566 @32k -> 400 @92k
- ub1024: 402 @32k -> 323 @86k -> 284 @120k
So the T_turn win at 32k overstates the win on a full window. Both are reported.

### D16. ub4096 is INELIGIBLE at 128k — no ncmoe can rescue it
The model has 48 blocks, so `-ncmoe 48` (all MoE on CPU) is the maximum meaningful value.
At **n48** ub4096 completes 120k but peaks at **14716 MiB** — 1316 MiB over the gate with
nothing left to trade. ub4096 is therefore dropped for 128k. (An `-ncmoe 50` probe was
started before I realised 48 is the cap; it is a no-op and I killed it rather than spend
6 minutes confirming a tautology.)

### D17. ub2048 survives the full window from ncmoe 46
Prefill-only probe (cheap instrument added tonight: full window, max_tokens 16):
- **ub2048 n46: completes 120,052 tokens, peak 12464 MiB** — 936 MiB of margin, and
  **556 MiB BELOW the baseline's own 13020**. Freeing 3 expert layers more than pays for
  the bigger compute buffer.
- ub1024 n43: completes, peak **13070 MiB** (vs baseline 13020 — a wash), full needles OK.
n45 is being probed for the curve; predicted 12464+912 = ~13376, i.e. inside the gate by
only 24 MiB, which is meaningless against ~230 MiB allocator noise. I will not ship a
24 MiB margin regardless of what it measures.

### D18. Tool mishap, logged for honesty
At 01:22 I ran `pkill -f phaseB_probe.py` to kill the no-op n50 probe. The pattern matched
my **own** shell (its command line contains that string), so it killed my shell instead;
the probe's harness child and llama-server survived and I finished them off by exact PID.
No measurement was lost (the n50 run was already abandoned) and the GPU was verified clean
(847 MiB, desktop only) before the next load. From here on process cleanup is by exact PID.

## D-late (added by Zef 01:47)
inputs/flashnext-eval-python-task02.md now present. Use it for Phase C fallback and Phase F sanity gate (Prompt B + probe.py).

### D19. Phase B tail: neither thread variant does anything (leader = ub2048 n46)
| variant | P32k | D32k | D0 | T_turn |
|---|---|---|---|---|
| `-t 16` (shipped) | 544.5 | 29.063 | 35.763 | 110.546 |
| `-t 12` | 547.6 | 28.669 | 35.297 | 110.923 |
| `-t 16 -tb 32` | 548.2 | 29.112 | 35.877 | 110.061 |
Spread is 0.9 s on T_turn against sd ~2.2 s. **No difference** (§7). Shipped `-t 16` stays and
no `-tb` is added — adding a flag that measurably does nothing is just risk.

### D20. 256k: matches the best 128k on speed, then dies on the window
At `-c 262144`, ub2048, n46: load 12424 MiB, P32k 548.8, D32k 28.898, D0 35.564,
**T_turn 110.371** — i.e. within 0.2% / 0.6% / 0.6% of the best 128k candidate, so §5's
2% tie rule is satisfied and 256k *would* be preferred. It then fails the **context gate**:
the 240k fill OOMs at **124,970 tokens** needing a 4679.78 MiB buffer, so a FULL test at
>=90% of 262144 (235,930 tokens) is unreachable. ncmoe is already 46 of a maximum 48 and the
deficit at 236k is several GB, so no ncmoe rescues it. **Ship 128k, report 256k.**
Extrapolating the measured surcharge law, 256k should be viable at the *shipped* ub512
(~+860 MiB at 240k, peak ~12.7 GB) — but at ub512 speeds, which are 53% worse on T_turn than
the winner and so nowhere near the 2% tie rule. Listed as an option for Zef, not measured
(it costs ~20 min of 240k prefill at 210 t/s and could not change the verdict).

## Phase C — KV accuracy (02:30–03:00). q8_0 STAYS.

### D21. Method: KLD tooling absent, so fidelity was measured through the API
No `llama-perplexity` (D4), so `--kl-divergence-base` is impossible and hard rule 3 forbids
building it or aiming a mainline binary at this model. Rather than fall back to the prompt's
"weak signal" (did Task 02 still pass), I measured the two quantities the prompt's own
threshold is written in — same-top-token % and KL — directly from the server:
teacher-forced next-token distributions (`/completion`, token arrays, `n_probs 20`,
temperature 0, `cache_prompt` so each step costs one decode), 64 positions x 2 prefixes x
{8k, 60k} context = **256 comparison points per KV type**, all types seeing byte-identical
contexts because the forced continuation is real source text. Reference = f16/f16 on the same
Q2 weights, at ncmoe 46 / ub2048.
(First attempt banked empty distributions: this build returns
`completion_probabilities[0].top_logprobs` as `{id,token,bytes,logprob}`, not `probs`.
Caught by a deliberate smoke test before the reference run, parser fixed, all collects redone.)

### D22. THE CONTROL IS THE RESULT: KV differences are below run-to-run noise
| comparison vs f16/f16 | n | same-top-token | mean KL |
|---|---|---|---|
| **f16/f16 again, fresh reload (noise floor)** | 256 | **97.656%** | **0.321** |
| q8_0/q8_0 (incumbent) | 256 | 96.875% | 0.256 |
| f16-K / q8_0-V | 256 | 98.438% | 0.141 |

q8's 3.12% disagreement sits on top of a **2.34% floor measured between two runs of the
identical f16 config**, and q8's mean KL (0.256) is *lower* than that floor (0.321).
So the instrument cannot distinguish q8_0 KV from f16 KV at all. Taken naively, q8 would
appear to breach the prompt's "same-top-token < 98%" trigger — but so does f16 against
itself, which proves the trigger is being tripped by measurement noise, not by quantisation.
**Decision: q8_0/q8_0 stays.** Per §6 Phase C this also closes the open thread in the other
direction: on this box, with the tooling that exists, q8 KV cannot be shown to cost anything.

Two honest caveats: (a) the mean-KL column is unreliable — `max_kl` is 23.0 = ln(1e10), the
exact floor assigned when a reference token is missing from the other run's top-20, and it
appears in the **noise-floor control too**, so KL here is dominated by top-20 set mismatches;
same-top-token is the only usable metric and it is at the floor. (b) my L8000/L60000 arms use
different text slices, so context length and content are confounded; I do not claim anything
about how error scales with context.

### D23. VRAM cost of each KV type (load, ncmoe 46 / ub2048 / 128k)
q8_0/q8_0 **9558** MiB · f16/f16 **11536** (+1978) · f16-K/q8_0-V **9700** (+142).
The asymmetry is large and unexpected: f16 on K alone costs 7% of what f16 on both costs, so
the V-side cache dominates KV memory for this architecture. Recorded as an observation;
it changes nothing tonight because q8 stays.
Since f16/f16 would need ncmoe 48 (the maximum) to have any chance at the full-window gate,
and it buys nothing measurable, it was not pursued further.

### D24. Open thread `graphs reused = 0`: CONFIRMED, and it explains the VRAM story
All 10 timed calls at the leading config report `graphs reused = 0`. Teardown also warns
`CUDA0 compute buffer size of 2593.09 MiB, does not match expectation of 1722.00 MiB` and
`CUDA_Host compute buffer size of 5912.09 MiB, does not match expectation of 552.20 MiB`.
So the fork re-plans its graph every batch and **mispredicts its own compute-buffer size** —
which is the mechanism behind D14 (load-time VRAM under-predicting peak) and the OOMs.
Investigated only; no rebuild, per hard rule 3.

## Phase D — Load mode (03:02–03:10). DO NOT ADOPT.

### D25. `-lm none` is the fastest prefill of the night and still must not ship
A/B at the leading config (ub2048, n46, q8/q8). `--mmap/--no-mmap` are deprecated in this
build in favour of `-lm/--load-mode`, so the A/B is `auto` (shipped default) vs `none`.

| | load | P32k | D0 | D32k | T_turn | MemAvail after load | MemAvail at end | RssAnon | RssFile |
|---|---|---|---|---|---|---|---|---|---|
| auto / mmap (shipped) | 8.0 s | 544.5 | 35.763 | 29.063 | 110.546 | 83.58 GiB | 74.78 GiB | 0.41 GB | **74.82 GB** |
| `-lm none` | 29.5 s | **727.5** | 34.466 | 27.701 | **98.354** | 14.87 GiB | **5.47 GiB** | 25.01 GB | 0.20 GB |

Rejected on two independent grounds:
1. **Speed gate.** D32k 27.701 = **92.76%** of baseline and D0 34.466 = **94.75%** — both under
   the 95% floor, and D32k's 7.2% decode sacrifice exceeds §5's "no more than 5%" ceiling.
   §5 is explicit that such a candidate is reported to Zef, not shipped.
2. **The page-cache story, which matters more here than the numbers.** RssFile collapses from
   74.82 GB to 0.20 GB: with mmap the model's 74 GB live as *shared, file-backed page cache*,
   so switching flashnext -> coder costs nothing to re-read. Under `-lm none` those pages are
   anonymous/shmem and MemAvailable falls to **5.47 GiB by the end of the run** on a box the
   config itself notes is shared with PMBrain/Supabase, Odysseus, ComfyUI and code-server.
   It passes the literal ">= 12 GB after load" check (14.87 GiB) and then walks straight
   through it under load.
Logged as an option for Zef: if he ever wants a prefill-first flashnext and will pay 7% decode
and the page cache for it, `-lm none` is the knob (T_turn 98.35, the night's best).

## Phase E — Multi-turn prefix reuse (03:10–03:16). WORKS. No flag needed.

### D26. Long-context flashnext is interactive, not batch-only
At the leading config: turn 1 prefilled **60,023 tokens in 141.25 s** (424.9 t/s). The
follow-up turn on the same conversation, after appending ~120 lines, prefilled
**2,218 tokens in 7.39 s** — `reuse_ratio 0.0370`, i.e. **96.3% of the context was reused**
from cache instead of re-prefilled. Peak VRAM 10,670 MiB.
So a second OpenCode turn at 60k context costs ~7 s, not ~141 s. This closes the open thread:
**flashnext is usable interactively at long context.** `--cache-reuse`, `-ctxcp` and `-cram`
all exist in this build (D5) but reuse already works at their defaults, so nothing is added —
per §6 Phase E a flag is adopted only if it *fixes* reuse, and there is nothing to fix.

## Phase F — Sanity (03:17–04:02) and the finding that decides the night

### D27. The 16000-token Task 02 run was VOID, exactly as §7 predicts
First attempt: `finish_reason: length`, `content_len 0`, **`reasoning_len 74976`**,
`predicted_n 16000`. Per §7 that is "max_tokens was too low; the run is void, not a model
failure", so it was discarded and re-run at `max_tokens 60000`. The baseline then needed
**58,765 generated tokens** (reasoning_len 253,180 chars) to reach `finish_reason: stop` —
so 60000 was barely enough and 16000 was never going to work. Worth knowing for any future
Task 02 run on this model: budget ~60k tokens, ~32 min at 30.6 t/s.

### D28. Baseline PASSES the sanity gate
Task 02 Prompt B, clean-room (run dir created empty, prompt and probe.py kept outside it,
probe copied in only at score time), temp 0.3, all four files produced:
`PROBE 1 PASS · PROBE 2 PASS · PROBE 3 PASS · PROBE 5 PASS · PROBE 4 FAIL (expected control)`
— identical to the reference `probe.out` in the harness dir.

### D29. THE BLOCKER: any `-ub` above 512 aborts the server on an ordinary prompt
The winner config never got a Task 02 score, because the server **died** both times with
`CUDA error: an illegal memory access was encountered` in `ggml_backend_cuda_synchronize`
(`llama_context::process_ubatch` -> `llama_decode`). I then isolated it. Every row below is a
fresh load whose FIRST inference request is the one shown; 10 loads, fully reproducible:

| # | -ub | -ncmoe | first request | result |
|---|---|---|---|---|
| T3 | 512 | 42 | Task 02 prompt_B (772 tok) | OK |
| W1 | 512 | 46 | prompt_B | OK |
| T6 | 512 | 42 | source, 325 tok | OK |
| T7 | 1024 | 43 | prompt_B | **CRASH** |
| T8 | 1024 | 43 | source, 325 tok | OK |
| T1 / T5 / V-promptB | 2048 | 46 | prompt_B | **CRASH (x3)** |
| W2 | 2048 | **42** | prompt_B | **CRASH** |
| W3 | **768** | 46 | prompt_B | **CRASH** |
| T9 | 2048 | 46 | source, 325 tok | OK |
| V-src-600/700/772/800/900 | 2048 | 46 | source, 650/751/823/849/951 tok | OK (x5) |
| U1 / U2 | 2048 | 46 | source, 1352 / 2406 tok | OK |
| T4 | 2048 | 46 | source, 4051 tok | OK |
| T2 | 2048 | 46 | 4061-tok warm-up, **then** prompt_B | OK |

What this establishes:
- **It is `-ub`, not `-ncmoe`.** ub512 survives at the winner's ncmoe 46 (W1); ub2048 crashes
  at the baseline's ncmoe 42 (W2). ncmoe is irrelevant.
- **512 is the only safe ubatch tested.** Even `-ub 768` crashes (W3). 512 is llama.cpp's
  default, so this fork has most likely never been exercised above it.
- **It is not prompt size.** Five source slices spanning 650–951 tokens — straddling
  prompt_B's 772 — are all fine at ub2048, as are 1352, 2406 and 4051.
- **It is content-dependent**, which makes it *worse*, not better: you cannot predict which
  prompts are affected, so any raised-ub config is a server abort waiting for the wrong
  prompt. prompt_B is ordinary English-plus-code spec text, not an adversarial input.
- **A large warm-up masks it** (T2), which is exactly why my bench/full/probe runs never saw
  it: the harness always warms up with a 4061-token prompt first. Had I not run Phase F, I
  would have shipped a config that aborts on real OpenCode traffic.

### D30. VERDICT: NO CHANGE
The whole Phase B win lives on `-ub > 512` and is therefore unshippable. The candidate that
passed every numeric gate — ncmoe 46 / b2048 / ub2048, T_turn 110.55 s vs 168.95 s (**-34.6%**),
FULL peak 12484 MiB (536 MiB *below* baseline) — fails §5 gate 4 (sanity) in the hardest
possible way: it does not produce a wrong answer, it terminates the process.
The config is left exactly as shipped. `apply-flashnext.sh` was written and validated but
deliberately **not run**. Per §7 and §8 this is the honest result: "no change" stands.

## Phase 8 — Finish (04:24–04:37)

### D31. No winner -> §8.4 path taken, config left untouched
llama-swap restarted; flashnext probed through `:9292` -> `PROBE_OK`, `finish_reason: stop`;
`/running` shows the original shipped cmd with `ttl 1800`. I additionally ran a full-window
needle test **through llama-swap** (not just the direct server) to prove the production path
serves the shipped config correctly at 128k: 120,134 tokens, 3/3 needles exact, `stop`,
prefill 211.10 t/s vs 210.58 measured directly — llama-swap adds no measurable overhead.
Then `curl -s http://127.0.0.1:9292/unload` (GET) -> `OK`, `/running` = `[]`.
Handover state: no llama-server processes, GPU 840 MiB (desktop only) / 15091 MiB free,
MemAvailable 83.2 GiB, config.yaml mtime still 2026-09-28 23:28:27.
`apply-flashnext.sh` exists, self-validates, and was **not run** — there is no winner to apply.
