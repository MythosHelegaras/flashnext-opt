# DECISIONS-v4.md — flashnext v4: engine decision (F fork vs M mainline) and MTP on M, Q2 only

## Phase 0 — Preflight (11:50–12:05, 2026-10-06)

### X1. Prompt, clock, rules
Mission prompt `flashnext-PROMPT-v4-mainline-mtp.md` (6518 B, mtime 11:48). §1 hard rules of
`flashnext-overnight-PROMPT.md` apply, with v4's two exceptions (`/opt/llama.cpp-flashnext` is a
second engine under test, read-only; hard rule 2 still protects `/opt/llama.cpp`). Rule 3's
"never use a mainline binary against this model" is superseded for M by v4 §0.
Run started **11:50**. HARD_STOP = min(11:50 + 10 h, 07:00 tomorrow) = **21:50 today**.
Finish phase starts by **21:20** at the latest.

### X2. Engines
- **F**: `/opt/llama.cpp-qwen4exp/bin/llama-server` — `0.3.0-dev (build 10654, commit bea3b12da)`,
  GNU 16.2.1 (same binary as v2/v3).
- **M**: `/opt/llama.cpp-flashnext/build/bin/llama-server` — `0.6.0-dev (build 11455, commit abeada335)`,
  GNU 16.2.1, built 11:46 today; libs resolve into `/opt/llama.cpp-flashnext/build/bin/` (ldd checked).
  `git merge-base --is-ancestor` confirms 6c84c7d (qwen4exp, #27742), c061df1 (MTP, #29761) and
  dd26678 (MMQ padding fix, #29941) are all in HEAD. Working tree clean.
- Toolchain: gcc 16.2.1, CUDA 13.4 (V13.4.92), driver **615.71.09**.

### X3. MTP head: WRONG -> Phase C skipped
- Expected `/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf`:
  **does not exist**.
- The `MTP/` directory holds one file named `57dd5d91c3097f26801557c089c9ad899c2bb5537092c6209a2a3f79235ec52b`
  (mtime 11:50:05 today, i.e. written while this run was starting). Size **2,786,204,800 B** — matches.
  GGUF v3 header, 34 tensors, 51 KV. Size was stable over 20 s; no downloader process running.
- **sha256 = `8087dbb39fc73f79ac069b1debe4069a44b73ada900c8bd761569d43a5a90231`** (hashed twice,
  identical). Expected `b646ef60…5a1575`. **Mismatch.** The filename is not its own sha256 either
  (so it is not an intact HF blob named by content hash).
- Per v4 §0 ("If either is missing or wrong, skip Phase C and say so"): **Phase C is skipped.**
  I did not rename, copy or link the file, and did not try it "just to see" — a head with the wrong
  bytes would give acceptance numbers that mean nothing.
- The older `mtp/Qwen3.8-Flash-Next-MTP-Q4_K_M.gguf` (2,622,313,344 B, 2026-09-08) is the head for
  the old experimental patch; v4 says that result is not applicable, and it is not the file named.
- For the record (read-only source check): M's `draft-mtp` accepts a separate head via
  `--model-draft` (`common_speculative_init_result`, `has_dft()` branch) or, without it, builds the
  MTP context on the main model's NextN layers. Draft-side flags present in `--help`:
  `--spec-draft-n-max` (default 3), `--spec-draft-n-min`, `--spec-draft-p-min` (0.00),
  `--spec-draft-p-split`, `--spec-draft-ncmoe`, `--spec-draft-ngl`, `-ctkd/-ctvd` (draft KV, default f16),
  `--spec-draft-sampling greedy|probabilistic`. `--metrics` exists.
- Freed time goes to B3 (`--fit`) and Phase D (256k), which v4 lists after C.

### X4. Machine state, llama-swap
llama-swap was **active with flashnext loaded** (F, `-ncmoe 46 -t 16 -b 2048 -ub 2048`, 9,666 MiB) —
config.yaml was changed to n46/ub2048 at 11:41 today (v2 Option A applied by Zef).
`systemctl --user stop llama-swap` at ~11:53 -> inactive, no llama-server left, GPU 489 MiB used
(kwin 72 + claude-desktop 78), 15,442 MiB free. MemAvailable 87.4 GiB, buff/cache 53 GiB.
So "production config" in v4 §0 = the live block. The live flashnext block:
```
/usr/bin/env LLAMA_ATTN_ROT_DISABLE=1 /opt/llama.cpp-qwen4exp/bin/llama-server --port ${PORT}
-m …/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
-ngl 999 -fa on -np 1 --jinja -ot per_layer_token_embd=CPU
-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0
--temp 0.3 --top-p 0.95 --top-k 20      ttl: 1800
```

### X5. M flag surface (from `--help`, logs/v4/M-help.txt)
- `--fit [on|off]` **defaults to on** in M ("adjust unset arguments to fit in device memory"),
  `--fit-target` default 1024 MiB, `--fit-ctx`. F has no `--fit`.
- `-lzm/--lazy-mode on|auto|off` (default auto = on only for tensors > 4 GiB; per_layer_token_embd
  is 28.8 GB, so **auto already makes it lazy** unless `-ot` overrides placement — measured in B1).
- `-lm/--load-mode auto|none|mmap|mlock|mmap+mlock|dio`. `-ngl` default `auto`.
- `LLAMA_ATTN_ROT_DISABLE` is still read in M (`src/llama-kv-cache.cpp:315`).

### X6. Harness
`harness4.py` wraps `harness2.py` unchanged (same corpus files, nonces, seed 20260929,
cache_prompt false for speed tests, session = 20k + 15×3k turns, 800-token cap, cold set,
FULL needles) and adds `--engine F|M`, `--rot on|off`, `--ple ot|lazy|none`, `--fitoff`,
a `sanity` subcommand (B1: load VRAM/RSS/MemAvailable, 500-token probe, D0×3), and Task 02 via
`task02_v3` (W9 extractor, /slots check, NOTIFIER map, diagnostic probe). Results in
`results-v4.jsonl`, state in `state-v4.json`; every row carries engine, engine SHA and flags.

### X7. MTP head re-verified -> Phase C UN-SKIPPED (12:04)
Zef (mid-run message, ~12:03): the `b646ef60…` hash in the prompt came from a stale third-party
page; the Hugging Face API lists `mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf` at sha256 `8087dbb3…a90231`,
2,786,204,800 B. **Zef renamed the file himself** to the expected path (I did not touch it).
Re-verified at 12:04: `/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf`
— size **2,786,204,800 B**, sha256 **`8087dbb39fc73f79ac069b1debe4069a44b73ada900c8bd761569d43a5a90231`**
(content mtime unchanged, 11:50:05; the rename is the only change). Both match the corrected
reference. X3's skip is withdrawn: **Phase C runs after Phase B as planned** (only if M passes B2).
(Zef also renamed the old head dir mtp/ -> mtp-oldpatch-20260908/.)

## Phase A — F re-baseline on driver 615.71 / CUDA 13.4 (11:58–12:19). COMPLETE
F, `-ncmoe 46 -t 16 -b 2048 -ub 2048`, 3 reps + FULL in one load, then session (separate load).
| metric | v4 today (F) | v2 V9/V12 (F, old driver) | Δ |
|---|---|---|---|
| P4k t/s | 587.6 ±9.1 | 590.4 ±0.5 | −0.5% (noise) |
| P32k t/s | 554.1 ±13.7 | 558.8 ±15.9 | −0.8% (noise) |
| D0 t/s | 35.77 ±0.36 | 36.42 ±0.16 | −1.8% (< 3%: noise) |
| D32k t/s | 29.36 ±0.16 | 29.50 ±0.08 | −0.5% (noise) |
| T_turn s | 108.97 | 108.2 | +0.7% |
| FULL prefill / decode | 357.0 / 19.22 | 351.2 / 18.83 | +1.6% / +2.1% |
| FULL needles / finish | 3/3 / stop (120,182 tok) | 3/3 / stop | |
| load → FULL peak MiB | 9,558 → **12,486** | 9,558 → 12,486 | identical |
| session_s | **1056.4** (Σ TTFT 162.3 + Σ decode 894.1) | 1046.1 (160.2 + 885.9) | +1.0% (noise) |
| last turn depth / decode | 78,419 / 23.31 | 77,700 / 23.60 | |
The driver/CUDA change moved nothing beyond noise. **Phase A numbers are the comparison base from here.**
Prefix reuse intact (no broken turns). Session peak 11,078 MiB.

## Phase B1 — M flag compatibility (12:19–12:28). COMPLETE
Four loads of M at `-ncmoe 46 -t 16 -b 2048 -ub 2048`, each: load metrics, 500-token sanity probe
(merge_intervals prompt, seed 20260929), D0 ×3.
| variant | loads | load / peak MiB | RSS at load (anon / file) | MemAvail after load | D0 t/s | probe |
|---|---|---|---|---|---|---|
| exact F cmd (env on, `-ot`, fit default on) | yes, 4 s | 9,996 / 10,170 | 0.44 / 27.8 GiB | 86.4 GiB | 40.37 ±0.15 | sane (all reasoning at 500, `length`) |
| env **unset** (`LLAMA_ATTN_ROT_DISABLE` absent) | **yes** | 9,996 / 10,170 | 0.44 / 27.8 | 86.3 | 40.18 ±0.03 | sane, *different text* |
| `--lazy-mode on`, no `-ot` | yes | 9,996 / 10,170 | 0.44 / 27.8 | 86.3 | 40.53 ±0.02 | byte-identical to exact F |
| exact F + `--fit off` | yes | 9,996 / 10,170 | 0.44 / 27.8 | 86.3 | 40.35 ±0.12 | byte-identical to exact F |
Findings:
- **M accepts every F flag and the env var.** No refusal, no warning beyond the generic
  "tensor overrides to CPU are used with mmap enabled - consider --load-mode none" (printed in every
  variant, also lazy — `-ncmoe` is itself a CPU override).
- **The env var is no longer required on M**: without it M loads and answers sanely (F aborted).
  The text differs from the env-on runs because KV attention rotation is then active — that changes
  the attention math on the q8_0 KV cache. Speed: 40.18 vs 40.37 (−0.5%, noise).
  **Kept the env var** for every later M run: it reproduces F's math, which is what gates 2–4 and
  every Task 02 result on record were measured on. Whether rotation *improves* q8 KV fidelity is an
  accuracy question (KLD), not tested tonight — logged as an option.
- **`-ot per_layer_token_embd=CPU` vs `--lazy-mode on`: no difference** in load VRAM, RSS
  (RssFile 27.8 GiB at load, ~55 GiB after D0 in both — mmap'd pages of the CPU experts/embedding,
  page-cache backed), MemAvailable, or D0; output byte-identical. Lazy-mode's default `auto`
  would already cover this 28.8 GB tensor. **Kept `-ot`** (identical, and the apply diff stays minimal).
- **`--fit` (default on) does nothing** when `-ngl/-ncmoe/-c` are all set: same VRAM, identical
  output, no fit lines at verbosity 3. No `--fit off` needed in the production line.
- M loads **+438 MiB** more VRAM than F at the same flags (9,996 vs 9,558). FULL peak decides (B2).
- **M decodes faster**: D0 40.4 vs F 35.77 (**+12.9%**, ≫ 2 sd). Prefill on the warm-up 4k: 648 vs ~588.
- **Different default:** M enables `--reasoning-preserve` by default ("preserve reasoning in the full
  history"); F's default is the template default and its log says "consider enabling it". The
  session test sends `reasoning_content` back on every assistant turn, so this can change what M
  prefills per turn. Checked in B2 via per-turn prompt_n and depth.
B1 winner = **exact F command line** on M binary.

## Phase B2 — M at production settings (12:29–)
### X8. Speed + FULL (one load): M is much faster and uses far less VRAM at full window
| metric | F (Phase A) | M | M vs F |
|---|---|---|---|
| P4k t/s | 587.6 ±9.1 | 688.7 ±0.1 | +17.2% |
| P32k t/s | 554.1 ±13.7 | 728.6 ±0.6 | **+31.5%** |
| TTFT32k s | 57.89 | 44.00 | −24.0% |
| D0 t/s | 35.77 ±0.36 | 40.13 ±0.49 | **+12.2%** |
| D32k t/s | 29.36 ±0.16 | 35.52 ±0.55 | **+21.0%** |
| T_turn s | 108.97 | 86.24 | −20.9% |
| FULL prefill / decode | 357.0 / 19.22 | **723.5 / 28.13** | +103% / +46% |
| FULL TTFT s (120,182 tok) | 336.6 | 166.1 | |
| FULL needles / finish | 3/3 / stop | **3/3 / stop** | gate 2 PASS |
| load → **FULL peak** MiB | 9,558 → 12,486 | 9,996 → **10,482** | **−2,004 MiB** — gate 1 PASS, 2,918 margin |
Why: F's log at the end of the FULL run warns `CUDA0 compute buffer size of 4469.4 MiB, does not match
expectation of 1722.0 MiB` and `CUDA_Host compute buffer 11783.9 MiB (expected 552.2)` — the fork's
graph (sparse indexer / attention at long context) grows its buffers with depth. M's surcharge from
load to FULL peak is +486 MiB vs F's +2,928. The decode gain growing with depth (+12% at 0,
+21% at 32k, +46% at 120k) points the same way: M's long-context attention path is cheaper.
### X9. Session: M −23.0%
| | session_s | Σ TTFT | Σ decode term | turn-16 depth | turn-16 decode | peak MiB |
|---|---|---|---|---|---|---|
| F | 1056.39 | 162.32 | 894.07 | 78,419 | 23.31 | 11,078 |
| M | **813.15** | 106.43 | 706.72 | 77,362 | 31.15 | 10,482 |
- Prefix reuse identical: prompt_n per turn 3,028–3,040 on both (turn 16 on M = 3,318 because turn 15
  stopped early at 282 tokens with content, which is then re-templated). No broken turns.
  **M's default `--reasoning-preserve` does not change per-turn prefill here** — same prompt_n as F.
- M turns 7/12/15/16 ended `stop` before 800 tokens (620/574/282/685). F hit `length` every turn.
  Per-turn decode rates are measured over ≥ 282 tokens; v2 V17 showed such early stops move
  session_s by < 0.2%. Even replacing M's four early-stop turns' decode rates by their neighbours'
  cannot close a 23% gap.
- Per-turn prefill on M stays flat (~5.2 s per +3k turn at 24k → 74k depth); on F it grows 6.9 → 11.0 s.
(Harness note: the B2 chain's `cold` call reused label v4-B2-M-n46 and was skipped by the resume guard; re-queued as v4-B2-M-n46-coldset after Task 02. No data lost.)
### X10. Gate 4 on M: PASS (Task 02 Prompt B, cold, no warm-up, max_tokens 60000, temp 0.3, seed 20260929)
`stop` at 34,014 generated tokens, **37.9 t/s** for the whole run (F's v2/v3 Q2 runs: 26.9–32.1),
wall 900 s. /slots confirmed temp 0.3 / top_p 0.95 / top_k 20 / min_p 0.05 / seed. Probes 1, 2, 3, 5
PASS; probe 4 trips at threshold 0 and −1 (standing control). NOTIFIER: annotation in breaker_events,
read as `breaker_events.NOTIFIER` (the probe's reading). No crash.
### X11. `--fit` on M aborts silently whenever `-ngl` or any tensor override is user-set
`common/fit.cpp:463` throws "n_gpu_layers already set by user", `:485` "tensor_buft_overrides already
set by user" (`-ot` and `-ncmoe` are both overrides), logged at TRACE only. That is why B1's fit-on and
fit-off runs were identical. B3 therefore has to drop `-ngl 999`, `-ot …=CPU` and `-ncmoe` (rule 8
names `-ngl 999` and `-ot` as mandatory; v4 §B3 explicitly asks for `--fit on`, which cannot work with
them, so B3 runs without them; `--lazy-mode on` replaces `-ot`, shown equivalent in B1). The fit
decision itself is only printed at debug verbosity; the measured VRAM is the record.
### X12. Gate 3 on M: 11/11 (13:01–13:06)
Fresh M server per item, no warm-up: {300, 508, 777, 1016, 1500, 2044, 3000, 4061} + prompt_B ×3.
prompt_n matched every target exactly (same tokenizer as F); no abort, no CUDA error, alive after each.

### X13. ENGINE VERDICT: **M**
M passes gates 1–4 (FULL peak 10,482 ≤ 13,400; 128k FULL 3/3 needles `stop`; 11/11 cold; Task 02 PASS)
and session_s 813.15 vs F 1056.39 = **−23.0%** (far beyond the 3% / 2 sd noise rule). Phase C is unlocked.

## Phase B3 — `--fit on` instead of `-ncmoe` (13:07–13:40). REJECTED (noise)
Spec: `-t 16 -b 2048 -ub 2048 -c 131072 q8_0/q8_0 --fit on --fit-target 3000 --lazy-mode on`, no `-ngl`,
no `-ot`, no `-ncmoe` (X11). Board before load: 538 MiB used / 15,393 MiB free.
fit-target chosen as: free 15,393 − 3,000 ≈ 12,400 process at load, + M's measured +486 FULL surcharge
≈ 12,9xx worst case, below 13,400 with > 2× allocator noise.
| | manual n46 (B2) | fit 3000 | Δ |
|---|---|---|---|
| load → FULL peak MiB | 9,996 → 10,482 | 12,138 → **12,624** (gate 1 PASS, 776 margin) | |
| P4k / P32k | 688.7 / 728.6 | 721.7 / 757.0 | +4.8% / +3.9% |
| D0 / D32k | 40.13 ±0.49 / 35.52 ±0.55 | 41.11 ±0.10 / 36.46 ±0.09 | +2.4% / +2.7% |
| FULL prefill / decode | 723.5 / 28.13 | 750.1 / 28.31 | +3.7% / +0.6% |
| FULL needles / finish | 3/3 stop | 3/3 stop | |
| **session_s** | **813.15** | 799.72 | **−1.65%** |
fit placed ≈ 2.3 layers' worth (+2,142 MiB) more experts on the GPU, i.e. roughly ncmoe 43–44 equivalent.
**Rejected:** session gain 1.65% < 3% (noise rule). Also a robustness cost: fit sizes against the
*free* VRAM at load time, so the layout (and the peak) moves with whatever the desktop holds when
llama-swap loads flashnext; manual `-ncmoe` is deterministic. Gates 3/4 not run for it (rejected first).

## Phase C — MTP on M (13:15–)
### X14. C1 launch: flags, acceptance, VRAM breakdown
Command (M, B1 flags + MTP): `… -ncmoe N -t 16 -b 2048 -ub 2048 -c 131072 q8_0/q8_0
--spec-type draft-mtp --model-draft …/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf --spec-draft-ngl 999
-ctkd q8_0 -ctvd q8_0 --spec-draft-n-max K [--spec-draft-cpu-moe] --metrics` (+ env, -ngl 999, -fa on,
-np 1, --jinja, -ot per_layer_token_embd=CPU, sampling). Draft sampling left at default `greedy`
(target verifies; output distribution = target's), `--spec-draft-p-min` default 0.00.
Loads/probes at n46, n-max 3 (sanity routine: 500-tok code probe + D0 ×3):
| head placement | load MiB | peak (short ctx) | code probe t/s (acc, mean len) | D0 t/s (acc) |
|---|---|---|---|---|
| no MTP (B2) | 9,996 | 10,170 | ~40 | 40.13 ±0.49 |
| all on GPU | 14,482 (+4,486) | 14,820 | 51.8 (74.7%, 3.24) | 36.24 ±1.24 (40.7–45.3%, 2.22–2.36) |
| experts on CPU (`-cmoed`) | 12,732 (+2,736) | 13,070 | 49.4 (74.7%, 3.24) | 34.30 ±0.95 (same) |
- **Acceptance is content-dependent**: code ~75% per drafted token, technical prose ~41–45%. At n-max 3
  on prose the 4-token verify costs more than it saves (D0 *below* no-MTP).
- Verbose load (`-lv 4`, `-cmoed`): draft = model 556 MiB (output.weight Q6_K 497 + attn/hc/nextn;
  token_embd on CPU) + KV 136+34 MiB (131k cells, 1 layer, q8_0) + **compute 1,672 MiB** (sized by the
  shared `-ub 2048`; no draft-only ubatch flag exists) ≈ 2,400 MiB. Head experts (1,750 MiB) on GPU add
  the rest. The draft context is sized to the full 131,072 window (`cparams.n_ctx = llama_n_ctx(ctx_tgt)`).
- Placement does not change acceptance (identical counts). GPU-head D0 36.2 vs CPU-head 34.3: 1.6 sd, noise.
### X15. ncmoe prediction (912 MiB/layer) — lowest passing
Surcharge model: M FULL = load + 486 (B2); MTP adds ~+340 over load already at short context (13,070−12,732).
- `-cmoed` n46: 12,732 + 486 + ~340 ≈ **13,560 ✗** (predicted over by ~160 — inside 2× allocator noise
  of the gate, but over it; not used).
- `-cmoed` **n47**: 11,820 + 486 + ~340 ≈ **12,650 ✓** → C2 runs here, FULL verifies.
- head on GPU needs n48 (the max, every expert on CPU): 12,658 + ~830 ≈ 13,490 ✗ — infeasible at 128k.

### X16. `apply-flashnext-v4.sh` written and self-tested on scratch copies (13:32). NOT run.
`bash apply-flashnext-v4.sh <F|M> "<tuning>" [<mtp-n-max 1|2|3>]` (+ optional `FLASHNEXT_SAMPLING` as v3).
Rewrites the binary line, the `-ncmoe` line, and adds/replaces/removes ONE `--spec-type draft-mtp …` line
(after `-c`). Checks the binary runs (`--version`), MTP only on M, MTP head size + sha256 `8087dbb3…`.
Plans into a temp file, writes nothing on a no-op, backup before any write, YAML/other-blocks/top-level
identity, ttl 1800, env var + every mandatory/sampling flag, exactly one binary/`-m`, no leftover MTP
flags when off, difflib proof that exactly the planned lines changed. Scratch tests (copies of the live
config): M same flags → 1 line; M n47 + MTP k2 → 3 lines; k2→k3 → 1 line; back to F with MTP off from
the k2 file → 3 lines and **byte-identical to the original**; no-op → nothing written; MTP on F, two
`-ncmoe` lines, bad tuning, k=5 → refused rc 1, file unchanged; M + MTP + sampling → 4 lines; a copy with
ttl 900 → write, validation fails, **restored byte-identical**. Live config sha256 unchanged after all tests.
### X17. C2 n-max 3 at n47 (`-cmoed`): FULL passes; session = no difference
- Load 11,820 MiB (predicted 11,820), **FULL peak 12,800** (predicted ≈ 12,650; gate 1 PASS, 600 margin).
  FULL 120,182 tok: prefill 674.3 t/s, decode **38.50** (acc 85.1%, mean len 3.55 — the 3-line needle
  answer is very predictable), 3/3 needles, `stop`.
- 3 reps: P4k 620.2 ±40.0, P32k 671.2 ±19.3, D0 **34.17 ±1.06** (acc 42.8%, len 2.29), D32k 35.73 ±2.62
  (acc 53.7%, len 2.62). vs M no-MTP n46: P32k −7.9%, D0 **−14.9%**, D32k +0.6% (noise; sd 2.6).
  The draft also runs over every prompt token (prefill cost) and n47 moves one more expert layer to CPU.
- **Session 814.44** (Σ TTFT 114.1 + Σ decode 700.3) vs M no-MTP n46 813.15: **+0.16% = no difference**.
  Session acceptance 56.5% (per-turn 43–73%), mean len 2.68. MTP decode is flat with depth (31–40 t/s,
  turn 16 at 78k: 36.9) while no-MTP decays 37.1 → 31.2; the shallow-turn loss and deep-turn gain cancel.
  Prefill per turn +0.4 s (5.6 vs 5.2 s).
### X18. C2 draft depth at n47 (`-cmoed`), n-max ∈ {3, 2, 1} — n-max 2 best, but inside noise
| | M no-MTP n46 (B2) | k=3 | **k=2** | k=1 |
|---|---|---|---|---|
| P4k t/s | 688.7 ±0.1 | 620.2 ±40.0 | 642.4 ±2.5 | 639.2 ±0.3 |
| P32k t/s | 728.6 ±0.6 | 671.2 ±19.3 | 677.1 ±5.0 | 677.8 ±1.7 |
| D0 t/s | **40.13 ±0.49** | 34.17 ±1.06 | 37.17 ±0.49 | 39.51 ±0.49 |
| D32k t/s | 35.52 ±0.55 | 35.73 ±2.62 | **36.54 ±1.72** | 35.91 ±0.24 |
| acceptance D0 / D32k (mean len) | — | 42.8% / 53.7% (2.29 / 2.62) | 52.8% / 61.9% (2.05 / 2.24) | 66.5% / 75.4% (1.67 / 1.75) |
| **session_s** | **813.15** | 814.44 (+0.2%) | **792.43 (−2.55%)** | 839.87 (+3.3%) |
| Σ TTFT / Σ decode | 106.4 / 706.7 | 114.1 / 700.3 | 116.8 / 675.6 | 115.4 / 724.5 |
| session acceptance (mean len) | — | 56.5% (2.68) | 66.9% (2.33) | 77.3% (1.77) |
| session peak MiB | 10,482 | 12,796 | 12,686 | 12,570 |
- Every MTP config pays ~+9–10 s of prefill per session (draft runs over every prompt token; one more
  CPU expert layer at n47) and must win it back in decode. Only k=2 does, by 31 s net.
- **Best n-max = 2** (session 792.43). vs M without MTP: **−2.55%**, which is under §7's 3% floor →
  **"no difference"** on one session rep each. The per-request decode spread at k=2 (D32k sd 1.72, per-turn
  decode 32.9–39.3) is also much wider than without MTP — acceptance varies with content.
- k=1 is decode-neutral at best (D0 −1.5%) and loses the prefill cost; k=3 loses on prose (D0 −15%).
- C3 (gates 1–4) runs on k=2 regardless, as the prompt asks, to settle losslessness and VRAM.
### X19. C3 gates on MTP k=2 (n47, `-cmoed`): all PASS (14:22–14:51)
- Gate 1: load 11,706 MiB (k=3 was 11,820 — draft buffers scale slightly with n-max), **FULL peak 12,686** (714 margin).
- Gate 2: FULL 120,182 tok, prefill 671.8, decode 35.53, 3/3 needles, `stop`.
- Gate 3: 11/11 cold, prompt_n exact, no crash.
- Gate 4: **PASS** — `stop` at 49,744 tokens, 37.50 t/s, 1,329 s; probes 1, 2, 3, 5 PASS, probe 4 control trips;
  NOTIFIER read from `breaker_events`. Acceptance over the run 70.8% (29,154 / 41,178 drafted), mean len 2.42.
  "Lossless at the sampler" holds as far as Task 02 can show: same logic profile as every passing run. (Greedy
  draft + target-sampled verification is distribution-exact by construction; the text differs from a no-MTP run
  because the RNG stream is consumed differently, as B1-vs-C1 probe text showed.)
- Note: whole-run decode 37.50 t/s ≈ M no-MTP's 37.89 on its Task 02 (different samples: 49.7k vs 34.0k tokens).
### X20. Second session reps (decisive and marginal: −2.55% vs a 3% floor) — started 14:52
Rep 2: MTP k=2 **776.53** (Σ TTFT 115.0 + Σ decode 661.5); M no-MTP n46 **816.87** (106.8 + 710.1).
Two reps: MTP k=2 784.48 ±11.24, no-MTP 815.01 ±2.63 → **−3.75%**, diff 30.5 s > 2× combined sd (23.1 s).
Beyond noise on both criteria at n=2, but the MTP sd is 4× the no-MTP sd (content-dependent acceptance).
A third rep of each is cheap (time is ample), so it is run before deciding (X22).

## Phase D — 256k on M (15:05–)
### X21. 256k load ladder at ub 2048 (no MTP)
Load MiB at `-c 262144`: n44 **load FAIL** (exit 1, OOM at load) · n45 14,616 · n46 13,704 · n47 12,792 · n48 11,880
(912/layer exactly). n46 at 256k = 128k + 3,708: KV 3,264 + 816 (= 2× of 128k, +2,040) and CUDA0 compute
buffer 4,047 vs 2,380 (+1,667 — sized by ctx at ub 2048). n45/n46 are over the gate at load already.
Prediction with M's 128k surcharge (+486): n47 ≈ 13,278 (marginal, 122 under), n48 ≈ 12,366. FULL 240k at
n47 and n48 queued after the third session reps.

### X22. Third session reps (alternated order: no-MTP first) and the MTP verdict
Rep 3: M no-MTP n46 **814.60**; MTP k=2 n47 **779.39**.
| | rep 1 | rep 2 | rep 3 | mean ±sd |
|---|---|---|---|---|
| M no-MTP n46 | 813.15 | 816.87 | 814.60 | **814.87 ±1.88** |
| M + MTP k=2 n47 | 792.43 | 776.53 | 779.39 | **782.78 ±8.48** |
Δ = −32.1 s = **−3.94%**; 2× combined sd = 17.4 s; Welch t ≈ 6.4. Beyond noise on both §7 criteria.
Σ TTFT: MTP +8–10 s per session (draft prefill + 1 CPU layer); Σ decode −45 s. All of the gain is
decode at depth: no-MTP decays 37 → 31 t/s over the session, MTP k=2 holds 33–39 t/s.
**MTP verdict: YES, n-max 2** — it passes gates 1–4 (X19) and beats M-without-MTP beyond noise.
The trade (C4): VRAM margin after a full fill 714 MiB (vs 2,918 without MTP); D0 −7.4% (37.17 vs 40.13);
P32k −7.1% (677 vs 729); D32k +2.9% (noise); one session ≈ 32 s (−3.9%) faster; acceptance is
content-dependent (code ~62–75%, prose ~53%), so the gain is workload-dependent and modest.
Rep-to-rep note: all three MTP k=2 sessions drafted/accepted the identical 10,288 / 6,881 tokens (66.9%,
mean len 2.33) — generation is deterministic for the fixed seed, so the 776–792 s spread is timing noise only.

### X23. 256k FULL on M (no MTP), 240,183-token fill (15:25–15:38)
| ncmoe | load | **FULL peak** | margin | prefill t/s | TTFT | decode t/s | needles | finish |
|---|---|---|---|---|---|---|---|---|
| 47 | 12,792 | **13,278** | 122 (inside ~230 allocator noise) | 684.7 | 350.8 s | 21.44 | 3/3 | stop |
| **48** | 11,880 | **12,366** | 1,034 | 690.8 | 347.7 s | 21.34 | 3/3 | stop |
Surcharge load → peak = +486 MiB at both windows (same as 128k): M's compute buffers are sized at load and do
not grow with the fill. Prediction (X21) hit to the MiB at n47. Lowest passing = n47, but with 122 MiB it is the
same situation as v2's n45 (52 MiB): **use n48 for 256k**. n48 = every routed expert on the CPU.
vs F at 256k (v2 V20, ub512 n45): prefill 168 → 691 t/s (TTFT 23.8 → 5.8 min), decode 12.80 → 21.34.
Cost vs M 128k n46: D0/D32k not measured at n48 — expect ~2% lower decode (2 more CPU layers) at short depth.
**MTP + 256k is impossible at ub 2048:** n48 + MTP k=2 fails to load (`cudaMalloc failed` for a 2,509.7 MiB
draft compute buffer; "failed to create MTP context"). 256k and MTP are mutually exclusive on this card.
Report-only, per v4 §D.

## Finish (15:38–15:45)
No test server left; GPU 532 MiB (desktop). `systemctl --user start llama-swap` → active → flashnext via :9292,
max_tokens 500 → `PROBE_OK`, `stop`, 34 tok, 8 s; `/running` = unchanged F cmd (n46/ub2048) → `GET /unload` → `OK`,
`/running` = []. MemAvailable 87.2 GiB. config.yaml untouched (sha256 248c2cf3…, mtime 11:41, Zef's edit).
Nothing applied. Verdict: engine **M**, MTP **yes, n-max 2** (Option A); Option B = M without MTP. REPORT-v4.md.
