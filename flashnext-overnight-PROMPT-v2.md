# flashnext overnight v2 — quant decision (UD-Q2_K_XL vs GSQ-RCO IQ3_XXS) on the patched fork

Unattended run. Same machine, same working dir `~/flashnext-opt/`. **Every hard rule in
`PROMPT.md` §1 still applies** (no sudo, no builds, no downloads, port 9997 only, detached
long jobs, `state.json` resumability, mandatory flags). Read `PROMPT.md`, last night's
`REPORT.md` and `DECISIONS.md` first — they are prior data, not current truth.

**HARD_STOP 07:00. Start the finish phase by 06:15. Apply NOTHING to llama-swap tonight.**
Write the report and an apply command for each option; Zef decides in the morning.

Use `state-v2.json`, `results-v2.jsonl`, `DECISIONS-v2.md`, `REPORT-v2.md` (do not overwrite
last night's files). Reuse `harness.py` / `task02.py` where they fit.

---

## 1. What changed since last night

- The fork was patched for llama.cpp #27792 / PR #27044 (MMQ `mul_mat_id` tail padding) and
  **rebuilt from a fresh configure on a new toolchain** (the old g++-15 link launcher is gone).
  Verified: `prompt_B` as first request on a cold server at `-ub 2048 -ncmoe 46` → 5/5 OK
  (was 8/8 crash). ub 512 also OK.
- **Consequence: every speed number from last night is on a different binary.** Re-baseline.
  Do not mix v1 and v2 numbers in any comparison.
- `inputs/flashnext-eval-python-task02.md` is now present. Task 02 needs **max_tokens 60000**
  (last night the baseline needed 58,765 to reach `stop`).
- Zef uses flashnext for **growing OpenCode sessions** (start small, grow until the fix is
  done), not single huge prompts. Prefix reuse works (96% at 60k). The primary metric tonight
  is **session time**, not a fresh 32k prefill.

## 2. Models

- **Q2 (incumbent):** `/mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf`
- **IQ3_XXS (challenger):** `/mnt/ai/llm/models/qwen3.8-flash-next-gsq/IQ3_XXS/` — first shard
  `*-00001-of-00002.gguf`. Preflight: both shards present, shard 1 ≈ 47.0 GB, shard 2 ≈ 28.8 GB,
  no `.incomplete` files. **If incomplete, run the Q2 phases only and say so.**
  Check `tensor-allocation/` for the IQ3_XXS type map and record the per-layer expert types.
- Same mandatory flags for both (`LLAMA_ATTN_ROT_DISABLE=1`, `-ot per_layer_token_embd=CPU`,
  `-ngl 999 -fa on -np 1 --jinja`, q8_0/q8_0 KV, sampling unchanged). Before the first IQ3_XXS
  load, confirm the n-gram tensor is still named `per_layer_token_embd` in that GGUF; if not,
  find its name and log it.
- The two models together (~155 GB) do not fit in page cache. **Group work by model** (all Q2
  phases, then all IQ3_XXS phases, or the reverse), warm each model with one discarded request
  after switching, and record MemAvailable after every load. Abort any run where MemAvailable
  after load < 10 GB.

## 3. Gates (a config must pass all to be eligible)

1. **VRAM:** peak process VRAM **after a full-window fill** ≤ 13,400 MiB. Load-time VRAM is a
   pre-filter only; last night's surcharge was +430 / +1,186 / +2,926 MiB at ub 512 / 1024 /
   2048 on Q2 (~22–24 bytes per ubatch-token × context-token). IQ3_XXS per-layer VRAM is
   unknown — measure it (load at two ncmoe values, divide).
2. **Context:** 131072, FULL fill at ≥ 90%, 3/3 needles exact, `finish_reason: stop`.
3. **Cold-start robustness (replaces last night's single sanity run):** fresh server,
   **no warm-up**, first request = each of these prompt lengths, one cold start each:
   {300, 508, 777, 1016, 1500, 2044, 3000, 4061} tokens (real source/prose, exact counts via
   `/tokenize` + template) **plus** `prompt_B` ×3 cold. Any abort = config fails. This is ~11
   cold starts per finalist; budget for it.
4. **Task 02 Prompt B** (cold server, no warm-up, max_tokens 60000): probes 1, 2, 3, 5 pass;
   probe 4 is the standing control. Score the rubric too, marked provisional.

## 4. Metrics

Per config, 3 reps: P4k, P32k, D0, D32k (as v1). FULL ×1 for finalists.

**Primary: session time.** Simulate a growing session through `/v1/chat/completions` on one
conversation: turn 1 = 20k tokens of real source; then 15 turns, each appending ~3k new tokens
of real source plus a short question. Per turn record `prompt_n` (tokens actually prefilled),
TTFT, and decode t/s over the first ≥ 500 generated tokens (cap generation with max_tokens so
turns stay comparable; record `finish_reason`, a `length` stop is expected here).
`session_s = Σ TTFT + Σ (1500 / decode_tps_turn)`. Also report the last turn's depth and
decode t/s. If `prompt_n` on turns 2–16 is not ≈ the appended tokens, prefix reuse broke —
log it and investigate `--reasoning-preserve` once before continuing.

## 5. Phases (priority order; drop from the end if time runs short)

- **0 — Preflight (≤ 15 min).** Binary `--version`; `git -C /opt/llama.cpp-qwen4exp diff --stat`
  must show `mmq.cu` changed; model presence; stop llama-swap; GPU empty.
- **A — Q2 re-baseline (≤ 40 min).** Shipped config `-ncmoe 42 -b 2048 -ub 512`: 3 reps + FULL.
- **B — Q2 challenger (≤ 60 min).** `-ncmoe 46 -b 2048 -ub 2048`: 3 reps + FULL. If FULL busts
  the gate, try 47 once. Also `-ncmoe 43 -ub 1024` (3 reps + FULL) as the fallback.
- **C — IQ3_XXS ladder (≤ 90 min).** Measure per-layer VRAM. For ub ∈ {512, 1024, 2048} find the
  lowest ncmoe whose FULL peak passes (predict from the surcharge model, verify with FULL; one
  retry at +1). 3 reps each at the passing ncmoe.
- **D — Session test (≤ 75 min).** Best Q2 config and best IQ3_XXS config. If time allows, also
  Q2 shipped (ub 512) so Zef sees what ub is worth in real sessions.
- **E — Cold-start robustness (≤ 60 min).** Gate 3 on the best Q2 and best IQ3_XXS configs.
- **F — Task 02 (≤ 60 min).** Gate 4 on the same two, one run each; a second run each only if
  time remains before 05:30.
- **G — optional, only if ≥ 60 min remain before 06:15:** 256k at ub 512 for the session winner
  (lowest ncmoe with a 240k-fill peak ≤ 13,400 MiB, needles).

## 6. Decision rule (for the report — do not apply)

- **Best Q2:** the fastest-session Q2 config passing all gates (shipped config if none).
- **IQ3_XXS is recommended** if its best config passes all gates **and** its `session_s` is
  ≤ **1.10×** best Q2's. Zef accepts up to 10% slower sessions for higher precision (published
  evidence: Unsloth top-1 +2.7 for IQ3_XXS-class over Q2_K_XL-class; ISTA LiveCodeBench v6
  86.29 vs 81.14–83.43 for its 2-bit builds). You cannot measure the accuracy gain locally;
  do not claim one. Task 02 can only detect a regression.
- If IQ3_XXS is > 10% slower, report by how much and where the time goes (prefill vs decode,
  and the lookup-table decode cost ISTA warns about) and recommend Q2.
- Noise rules from `PROMPT.md` §7 apply: < 3% or < 2× sd is "no difference".

## 7. Finish (by 06:15)

Kill test servers, verify GPU empty, `systemctl --user start llama-swap`, probe flashnext
through `:9292` (current config, max_tokens 500), unload it. Write `REPORT-v2.md`: verdict in
two lines (quant + config), a comparison table (P4k, P32k, D0, D32k, FULL prefill/decode/peak,
session_s, last-turn decode, cold-start 11/11, Task 02), the IQ3_XXS per-layer VRAM and ncmoe
ladder, anything that crashed or was skipped, and the exact command to apply each option with
`apply-flashnext.sh` (which needs a model-path argument added for IQ3_XXS — write that
variant, self-validating like the original, but do not run it).
