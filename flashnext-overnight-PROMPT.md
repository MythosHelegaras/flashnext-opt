# flashnext overnight optimization — Claude Code mission prompt

You are running unattended with permissions bypassed on Zef's desktop ("Monster":
Ryzen 9 9950X, 96 GB DDR5 / 91 GB usable, RTX 5070 Ti 16 GB sm_120, CachyOS).
Nobody will answer questions until morning. When something is ambiguous, take the
conservative option, log the decision in `DECISIONS.md`, and keep going.

**Mission:** find the `flashnext` llama-swap configuration that is strictly better than
the shipped one for agentic coding use (OpenCode), prove it with measurements taken
tonight under identical conditions, and — only if every gate below passes — apply it
with a backup and verify it through llama-swap. If nothing beats the baseline, change
nothing and say so. "No change" is a valid and respectable result.

**HARD_STOP:** 07:00 local. By HARD_STOP, llama-swap must be running again with a
working flashnext (new or original config). Start the finish phase (§8) no later than
06:15 regardless of what is still pending.

Working directory: `~/flashnext-opt/`. Reference docs are in `~/flashnext-opt/inputs/`
(read all of them first; they are authoritative over your priors).

---

## 1. Hard rules — violating any of these is a failed night

1. **No sudo. Ever.** Nothing tonight needs root. If you think it does, you are wrong;
   log it and skip that item. (sudo would hang on a password prompt anyway.)
2. **Do not touch `/opt/llama.cpp`, `~/build/llama.cpp`, or any other model's config
   block.** `/opt/llama.cpp` links into `~/build/llama.cpp` — a rebuild there silently
   changes production for fim/coder/rag/auditor-gemma.
3. **Do not build, rebuild, git pull, reconfigure or patch `/opt/llama.cpp-qwen4exp`.**
   Use only binaries that already exist there. If `llama-bench` or `llama-perplexity`
   is missing from the fork, fall back to llama-server + API timings. Never use a
   mainline binary against this model (mainline cannot load `qwen4exp`).
4. **Do not download anything.** No models, no pip installs into system Python. If a
   Python package is missing, use a venv under `~/flashnext-opt/venv`.
5. **Do not delete** models, backups, or anything outside `~/flashnext-opt/`.
6. **Ports:** your test servers use **port 9997 only**. 9999 (eval/audit runner) and
   9998 (coder-tune) belong to other tools. Track the PIDs you start; kill only those.
   Before every new load: `pgrep -af llama-server` must show none of yours, and
   `nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv` must show no
   llama-server at all.
7. **The shipped config file is read-only until §8.** Edits happen only through the
   apply script you generate, which takes a timestamped backup first.
8. **Every flashnext invocation MUST carry:** `LLAMA_ATTN_ROT_DISABLE=1` (server aborts
   without it), `-ot per_layer_token_embd=CPU` (instant OOM without it), `-ngl 999`,
   `-fa on` (never bare `-fa`), `-np 1`, `--jinja`. Tools (bench/perplexity) get the
   same env var and `-ot`.
9. **Out of scope, do not test:** q4_0 KV (settled — q8 beat it clearly), MTP /
   speculative decoding (measured slower on this box), sampling params (`--temp 0.3
   --top-p 0.95 --top-k 20` stay exactly as shipped), context < 131072.
10. **Long commands run detached.** Your bash tool will kill anything long-running.
    Launch every load/bench/fill test with `setsid nohup ... > log 2>&1 &`, write the
    PID to a file, and poll with short commands (`sleep 60; tail -5 log`). Never block
    a tool call on a 9-minute prefill.
11. **Resumability.** Keep `~/flashnext-opt/state.json` (current phase, finished runs,
    current best). Update it after every run. If your context is compacted or you are
    restarted, read `state.json`, `results.jsonl`, and `DECISIONS.md` before doing
    anything else. Never redo a finished run; never lose a result.

---

## 2. Known facts — do NOT re-derive, build on them

(Sources: `flashnext-config-2026-09-11.yaml`, `flashnext-measurements-2026-09-14.md`,
`localLLMConfig.md`, `flashnext-eval-python-task02.md`.)

- Binary: `/opt/llama.cpp-qwen4exp/bin/llama-server`. Libs resolve into
  `/opt/llama.cpp-qwen4exp/build/bin/` — look there for `llama-bench` /
  `llama-perplexity`. Check `--help` of each before assuming any flag exists.
- Model: `/mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf`
- Shipped block (baseline) in `~/.config/llama-swap/config.yaml`:
  `-ncmoe 42 -t 16 -c 131072 --cache-type-k q8_0 --cache-type-v q8_0`,
  no `-b`/`-ub` → **defaults 2048/512**. `ttl: 1800`.
- Architecture: 48 blocks, only 12 carry KV (full_attention_interval 4), 2 KV heads,
  head dim 256, sparse indexer top_k 2048, **native context 262144 — 256k needs no
  RoPE scaling.** Context is cheap in VRAM; compute buffers are not.
- VRAM: ~926 MiB per expert layer at 128k/q8. Load-time process VRAM ~12,700 MiB at
  ncmoe 42. **Full-window prefill adds ~+308 MiB after load** — load-time VRAM is NOT a
  valid predictor at full window. Allocator noise ~230 MiB run to run.
- Decode is bandwidth-bound (~60 GB/s effective for CPU-resident experts); ~1–2% decode
  per expert layer moved to CPU. Prefill is ~flat above 80k (~226 t/s at 124k with
  ub 512). Decode decays ~48% from empty to full window — occupancy, not config.
- On `coder` (same hybrid-attention family), raising ubatch 512→2048 gave **+152%
  prefill**; ub 4096 failed to fit. **flashnext has never been ubatch-tuned.** This is
  the most likely large win tonight. It costs compute-buffer VRAM, which costs
  ncmoe layers, which costs decode. Quantify that trade; don't assume it.
- `-ub` is clamped to `-b`. `-b 2048 -ub 4096` is effectively ub 2048. Only test
  pairs with b ≥ ub.
- Reasoning model: every request needs `max_tokens` ≥ 4000 for generation tasks (500
  for liveness probes). Always record `finish_reason` and `reasoning_content` length.
- Tokenization: ~3.1 bytes/token for code/structured logs. Never estimate — read
  `timings.prompt_n`.
- Page cache: everything tonight is flashnext, so run warm. After any load, one
  discarded warm-up request before timing anything. A "cold load" inside a timed call
  is a void measurement.
- Open threads you may close tonight: `--load-mode none`/no-mmap A/B (loader
  suggests it), `graphs reused = 0` (investigate only, no rebuilds), prefix-cache
  reuse across turns at long context, 256k viability.

---

## 3. Search space

Axes that change the model's math (need an **accuracy** gate):
- **Weights:** UD-Q2_K_XL only. **Q3 and any other weight file are out of scope
  tonight** — do not load, test, or reference them.
- **KV type:** q8_0/q8_0 (incumbent), f16/f16, f16-K/q8_0-V.

Axes that do not change the math (need only the **sanity** gate):
- **Context:** 131072 (default), 262144.
- **Batch/ubatch (`-b`/`-ub`):** 2048/512 (baseline), 2048/1024, 2048/2048, 4096/4096.
- **`-ncmoe`:** derived, not swept blindly — for each combo find the **lowest** value
  that passes the VRAM gate (§5), then confirm that value +1 as the safe alternative.
- **Threads:** `-t` {16, 12}; `-tb` {16, 32} if the binary supports `-tb`.
- **Load mode:** default mmap vs whatever the loader warning recommends
  (`--load-mode none` or `--no-mmap` — check `--help`). RAM gate applies
  (MemAvailable ≥ 12 GB after load).
- **Prefix/context checkpoint flags** (`--ctx-checkpoints`, `--cache-reuse`,
  `--cache-ram` or equivalents — **only if present in this build's `--help`**):
  tested in §6 phase E for multi-turn reuse, not swept.

Do not explore a full cross product. Follow the phase order in §6 and carry forward
only winners.

---

## 4. Metrics (one harness, same for every candidate)

Write one harness script (`bench.py` or bash, your choice) and use it for every run
including the baseline. Record every run as one JSON line in `results.jsonl` with: full
command line, fork git SHA (`git -C /opt/llama.cpp-qwen4exp rev-parse HEAD`, read-only),
timestamp, process VRAM at load, process VRAM at peak, board free, MemAvailable,
prompt_n, prefill t/s, decode t/s, TTFT, finish_reason, reasoning length, pass/fail
flags.

Core speed metrics (3 reps each, report mean and sd; drop nothing silently):
- **P4k** — prefill t/s on a fresh ~4k-token code prompt.
- **P32k / TTFT32k** — prefill on a fresh ~32k-token code prompt (real source code,
  e.g. a slice of `/opt/llama.cpp-qwen4exp` `.c`/`.cpp` files, read-only). This is the
  representative OpenCode turn.
- **D0** — decode t/s at short context (≥ 1000 generated tokens).
- **D32k** — decode t/s immediately after the 32k prefill (≥ 1000 generated tokens).
- **FULL** (1 rep, finalists only) — ~120k prompt for 128k configs, ~240k for 256k
  configs: prefill t/s, TTFT, decode t/s, peak VRAM, needle result.

**Primary score (lower is better):**
`T_turn = TTFT32k + 1500 / D32k` (seconds for a typical agentic coding turn).

Use a fixed seed and `temperature 0.3` for all timed generations. Use distinct,
non-repeating haystack text for needle tests (repeated text is trivially compressible
and does not exercise long-range attention). Needle = unique 7-digit value placed
mid-context; plus two more at ~10% and ~90% depth for finalists.

---

## 5. Gates — a candidate must pass ALL of them to be eligible

1. **VRAM gate:** peak process VRAM measured **after a full-window fill** ≤
   **13,400 MiB** (baseline measured 13,046). Load-time VRAM is only a pre-filter;
   final eligibility requires the post-fill number. This preserves the reload margin
   that `-ncmoe 42` was chosen for — do not trade it away for speed.
2. **Context gate:** `-c` ≥ 131072, and a FULL test at ≥ 90% of the window with all
   needles retrieved exactly and `finish_reason: stop`.
3. **Speed gate ("only better than what we have"):**
   - `T_turn` improves by **≥ 5%** vs tonight's baseline, AND the improvement exceeds
     2× the combined sd; and
   - D0 and D32k each ≥ **95%** of baseline; and
   - FULL prefill and FULL decode each ≥ **95%** of baseline FULL.
   (Decode may give up ≤5% only if prefill buys more than that back in `T_turn`. If the
   best candidate needs more than a 5% decode sacrifice, it is not eligible — report
   it as an option for Zef, don't ship it.)
4. **Sanity gate (math-neutral changes):** Task 02 Prompt B (see §6 phase F), 1 run,
   probes 1, 2, 3, 5 pass; probe 4 expected to fail (standing control). Any
   syntax/API error, broken signature or truncated output = fail.
5. **Accuracy gate (KV or weight changes):** see §6 phase C. A KV change ships only if
   it clears its threshold AND passes the speed gate.
6. **256k tie rule:** 262144 is preferred over 131072 only if it passes every gate AND
   its `T_turn`, D0 and D32k are each within **2%** of the best 128k candidate.
   Otherwise ship 128k and report the 256k numbers.

---

## 6. Phases (in priority order — if time runs short, later phases are dropped)

**Phase 0 — Preflight (≤ 15 min).**
Read all inputs. Record: `nvidia-smi` (board used/free, compute apps), `free -g`,
`/proc/meminfo` MemAvailable, `df -h /mnt/ai`, `systemctl --user status llama-swap`.
Verify binaries and flags (`--help` of server, bench, perplexity) and write what exists
to `DECISIONS.md`. Stop llama-swap: `systemctl --user stop llama-swap` (it must not
load models underneath you; OpenCode or other agents may hit it overnight). Confirm the
GPU is empty. If desktop apps hold > 1,500 MiB VRAM, log it and continue — your VRAM
gate uses process VRAM, not board free.

**Phase A — Baseline (≤ 45 min).**
Run the exact shipped command (on port 9997) through the full harness: P4k, P32k, D0,
D32k ×3, plus FULL ×1 with needles. This is the only baseline you compare against —
not the numbers in the docs (different sessions, different conditions). If your
baseline differs from the docs by > 10%, log it and proceed anyway.

**Phase B — Batch/ubatch × ncmoe × context (≤ 2.5 h). The main event.**
For each (context ∈ {131072, 262144}) × (b/ub pairs from §3) at q8/q8:
1. Find the lowest `-ncmoe` whose **load-time** process VRAM ≤ 13,400 − 350 MiB
   (full-window surcharge allowance). Start from 42 and move one layer at a time;
   ub 4096 may need to go up, not down. A load failure (`cudaMalloc failed`, "failed
   to create context") = that ncmoe is too low; move up.
2. Run P4k, P32k, D0, D32k ×3 at that ncmoe.
3. Keep the top 3 by `T_turn` that meet the D0/D32k ≥ 95% rule. Run FULL on each.
   Any FULL VRAM violation → retry at ncmoe +1 once.
Also, at the best b/ub point, try `-t 12` and (if supported) `-tb 32`; keep only if
they improve `T_turn` beyond noise.

**Phase C — KV accuracy (≤ 1.5 h).**
Question: does f16 KV (or f16-K) measurably beat q8 KV on output fidelity, and at what
cost?
- If `llama-perplexity` with `--kl-divergence-base` exists in the fork: build a code
  corpus (real source files, read-only sources) of enough tokens for ≥ 4 chunks at
  `-c 16384`. Compute the base logits file size first (scored tokens × vocab size from
  GGUF × 2 bytes); abort this method if > 20 GB. Generate the base with **f16/f16 KV**
  on Q2 weights, then KLD + same-top-token % for q8/q8 and f16-K/q8-V against it.
  Use the best Phase B non-KV settings (ncmoe may need to rise for f16 — measure it).
- If KLD tooling is missing: run Task 02 Prompt B ×3 per KV type, compare probe
  results and rubric-relevant failures. Log that this is a weak signal.
- **Threshold to switch away from q8/q8:** q8's mean KLD vs f16 ≥ 0.01 **or**
  same-top-token < 98%, **and** the alternative still passes all speed/VRAM gates.
  If q8's KLD is below that, q8 stays — log the numbers; that closes the open thread
  "does q8 KV actually improve anything" in the other direction too.
- Record VRAM cost of each KV type at the chosen ncmoe.

**Phase D — Load mode (≤ 30 min).**
A/B default mmap vs the recommended no-mmap / load-mode flag at the leading config:
load wall time, D0, D32k, MemAvailable after load, RssAnon vs RssFile
(`grep -E 'VmRSS|RssAnon|RssFile' /proc/<pid>/status`). Adopt only if it passes all
gates and MemAvailable ≥ 12 GB. Note that no-mmap changes the page-cache story for
coder switching — record it, it matters to Zef.

**Phase E — Multi-turn prefix reuse (≤ 45 min).**
At the leading config: send a ~60k prompt, then a follow-up turn that appends ~500
tokens to the same conversation. Record the second turn's `prompt_n` and TTFT. If
reuse fails (second turn re-prefills most of the context), check `--help` for
checkpoint/cache-reuse flags and test them once. This decides whether long-context
flashnext is interactive or batch-only. Adopt a flag only if it fixes reuse without
breaking any gate.

**Phase F — Sanity/accuracy on the final candidate (≤ 45 min).**
Task 02 **Prompt B** from `flashnext-eval-python-task02.md`, verbatim, in a fresh empty
directory per run (contamination rule in that doc), temp 0.3, max_tokens ≥ 16000.
Extract the four files, run the doc's `probe.py` against them. Record probe results
and your own rubric scoring, marked **provisional** (single judge, single sample).
Run on baseline and final candidate, same conditions. Candidate must not score below
baseline on probes 1, 2, 3, 5.

---

## 7. Noise and honesty rules

- A difference smaller than 3% or smaller than 2× sd is **noise**. Say "no difference",
  not "slightly better".
- One run is an anecdote. Anything that decides shipping needs ≥ 3 reps (FULL tests
  excepted — they are 1 rep by cost; if a FULL result is decisive and marginal, run a
  second rep).
- If a harness result has empty `content`, check `finish_reason` and
  `reasoning_content` before calling it anything. `length` + long reasoning = your
  `max_tokens` was too low; the run is void, not a model failure.
- Never report chunks/sec as tokens/sec. Use server `timings`.
- Write down every surprise in `DECISIONS.md` with the numbers that caused it.

---

## 8. Finish phase (start by 06:15 at the latest)

1. Kill all your test servers; verify GPU empty.
2. Decide: winner = best eligible candidate by `T_turn` that passed **all** gates, or
   "no change".
3. If there is a winner, write `apply-flashnext.sh` (bash) that:
   - copies `~/.config/llama-swap/config.yaml` to
     `~/.config/llama-swap/config.yaml.bak-$(date +%Y%m%d-%H%M%S)`;
   - replaces **only** the `"flashnext":` block's `cmd` (locate by key, never by line
     number — line numbers drift);
   - keeps `ttl: 1800`, all mandatory flags, and sampling flags unchanged;
   - validates YAML parses, and proves via diff that every other block is
     byte-identical;
   - prints the rollback command.
   Run it. Then `systemctl --user start llama-swap`, probe flashnext through
   `http://127.0.0.1:9292` (max_tokens 500, expect `PROBE_OK`), confirm `/running`
   shows the new cmd, and run one FULL-window needle test **through llama-swap**.
   If any step fails: restore the backup, restart llama-swap, verify the original
   config probes OK, and report the failure.
4. If no winner: `systemctl --user start llama-swap`, probe flashnext, leave the config
   untouched.
5. Unload flashnext at the end (`curl -s http://127.0.0.1:9292/unload` — GET, not POST)
   so the morning starts clean.
6. Write `REPORT.md` (≤ 2 pages, numbers first):
   - Verdict in one line: shipped config (full block) or "no change" and why.
   - Table: baseline vs winner vs runner-up on P4k, P32k, TTFT32k, D0, D32k, FULL
     prefill/decode/TTFT, load VRAM, peak VRAM, `T_turn`.
   - Ub/ncmoe trade curve (the numbers, not adjectives).
   - KV finding (KLD numbers or why unavailable), load-mode finding, prefix-reuse
     finding, 256k finding.
   - Everything that failed, crashed, or was skipped, and why.
   - Rollback command.
   - Doc amendments: which lines of `flashnext-config-2026-09-11.yaml` /
     `flashnext-measurements-2026-09-14.md` are now wrong, with the replacement numbers.
   - Options Zef should decide himself (e.g. a faster config that failed a gate by a
     small margin), each with its exact trade-off.
