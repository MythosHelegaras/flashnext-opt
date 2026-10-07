# flashnext v4 — engine decision (mainline vs fork) and MTP on mainline, Q2 only

Unattended run in `~/flashnext-opt/`. **All hard rules in `flashnext-overnight-PROMPT.md` §1
apply**, with the two exceptions in §0 below. Read `REPORT-v2.md`, `REPORT-v3.md` and both
DECISIONS files first: they hold the harness, the gates and every baseline number.

Write these files: `state-v4.json`, `results-v4.jsonl`, `DECISIONS-v4.md`, `REPORT-v4.md`.
**Apply nothing to llama-swap.**

HARD_STOP: 10 hours after start, or 07:00, whichever comes first.

## 0. Scope, engines, files

**Two exceptions to §1:**
- Hard rule 2 still forbids touching `/opt/llama.cpp`.
- `/opt/llama.cpp-flashnext` is a second engine under test, read-only like the fork. Do not build, pull or patch it.

**Engines:**
- **F (fork, current production):** `/opt/llama.cpp-qwen4exp/bin/llama-server`, patched for #27792 and verified in v2/v3.
- **M (mainline):** `/opt/llama.cpp-flashnext/build/bin/llama-server`, commit `abeada335`. It contains the qwen4exp arch (`6c84c7d`), MTP (`c061df1`) and the MMQ padding fix (`dd26678`).

**Model:** Q2 only, `UD-Q2_K_XL`, same path as v2/v3. IQ3_XXS is out of scope.

**MTP head:** `/mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf`
- Expected: 2,786,204,800 bytes, sha256 `b646ef60…5a1575`.
- Verify both in preflight. If either is missing or wrong, skip Phase C and say so.

**Production config:** `-ncmoe 46 -t 16 -b 2048 -ub 2048 -c 131072`, q8_0/q8_0 KV, `-fa on -np 1 --jinja`, `--temp 0.3 --top-p 0.95 --top-k 20`.

**Out of scope tonight** (the next run covers these):
- Sampling, `--reasoning-effort`, `--reasoning-budget`, `--presence-penalty`.
- Keep all of them at the server defaults v2/v3 used: effort unset (template default, xhigh), presence 0.

**Gates** (unchanged from v2):
1. FULL-window peak VRAM ≤ 13,400 MiB.
2. Context 131072, FULL fill to ≥ 90%, 3/3 needles, `stop`.
3. 11/11 cold starts: {300, 508, 777, 1016, 1500, 2044, 3000, 4061} + `prompt_B` ×3, no warm-up.
4. Task 02 Prompt B cold, `max_tokens 60000`: probes 1, 2, 3, 5 pass.
   - One run per config that reaches this gate.
   - A `length` void gets one re-run.
   - A NOTIFIER-placement failure is reported with its diagnostic-probe result, as in v3.

**Primary metric:** `session_s` (v2 §4 harness, unchanged). Use the same corpus and the same rules for reading noise.

## 1. Phases (priority order; drop from the end if time runs short)

### Phase 0 — Preflight
Record both binaries' `--version`, the MTP file check, and the toolchain (gcc, cuda, driver).
Stop llama-swap. Confirm the GPU is empty.

### Phase A — F re-baseline on today's driver (~45 min)
F, production config: 3 reps (P4k, P32k, D0, D32k) + FULL in the same load, then the session test.

The driver/CUDA changed since v2 (now 615 / 13.4). Report how far this moved from v2 (V9/V12), then use these numbers, not v2's, as the comparison base.

### Phase B — M parity (~2 h)

**B1. Flag compatibility.**
- M with the exact F command line. If it refuses a flag or the env var, log it.
- Test M with and without `LLAMA_ATTN_ROT_DISABLE=1`. Does it load? Does output stay sane on a 500-token probe?
- Test `-ot per_layer_token_embd=CPU` vs `--lazy-mode on` (ISTA/llama.cpp recommend lazy mode for per-layer embeddings): load VRAM, RSS, MemAvailable, D0.
- Keep the combination that loads and is fastest.

**B2. M at production settings.** Same measurements as Phase A, plus:
- gate 3 (11 cold starts);
- gate 4 (Task 02 ×1).

**B3. Optional, only if B2 passes:** `--fit on` instead of `-ncmoe`.
- Use `--fit-target` so that the **post-FULL** peak lands ≤ 13,400 MiB.
- Measure the FULL peak; load VRAM is not a valid predictor here (v1).
- Reject it if the peak exceeds the gate, or if it does not beat manual ncmoe on session_s by more than noise.

**Engine verdict.** M wins if it passes gates 1–4 and its session_s is ≤ F's (noise rule: < 3% or < 2× sd is "no difference"). A tie also goes to M, because it removes the hand-patched fork. Phase C runs only if M passes B2.

### Phase C — MTP on M (~3 h)

The 7.6% MTP slowdown in our notes was measured on a different, experimental MTP patch. This is the merged implementation (PR 29761); treat the old result as not applicable.

**C1. Launch.** `--spec-type draft-mtp` with `--model-draft <MTP head>`.
- Check `--help` for the draft-side flags: `--spec-draft-n-max`, `--spec-draft-p-min`, `--spec-draft-ncmoe`, draft GPU layers, draft KV type.
- Log the full command line. The draft head needs VRAM (~2.8 GB file), so expect to raise `-ncmoe` to stay under the gate.
- Find the lowest ncmoe whose FULL peak passes. Predict it from the 912 MiB/layer table, then verify.

**C2. Draft depth.** n-max ∈ {1, 2, 3} at the passing ncmoe. For each, record:
- 3 reps of D0 and D32k;
- the acceptance rate, from the server log or `/metrics`;
- the session test.

Pick the best n-max by session_s.

**C3. Best MTP config:** gates 1–4. MTP must be lossless at the sampler. If gate 4 fails, report the diagnostic-probe logic profile so a NOTIFIER slip is not mistaken for MTP corruption.

**C4. Report the trade honestly.** Decode is ~85% of session time (v2 V12), so MTP's decode gain is what matters. The cost is extra `-ncmoe` layers (~1% decode each) and VRAM margin. A win needs session_s better than M-without-MTP by more than noise.

### Phase D — Only if ≥ 60 min remain before the finish
256k context on M at the best config: lowest ncmoe with a 240k-fill peak ≤ 13,400 MiB, plus needles.

Report only: Zef's sessions grow, so this is an option, not a default.

## 2. Finish (start ≥ 30 min before HARD_STOP)

1. Kill the test servers and confirm the GPU is empty.
2. `systemctl --user start llama-swap`.
3. Probe flashnext via `:9292` (current config, F), then `GET /unload`.

Write `REPORT-v4.md`:
- **Verdict:**
  - Engine: F or M.
  - MTP: yes/no, with n-max.
  - The full recommended llama-swap cmd.
- **Comparison table:** F (today) vs M vs M+MTP. Columns:
  - P4k, P32k, D0, D32k;
  - FULL prefill / decode / peak;
  - session_s;
  - acceptance rate;
  - gates 1–4.
- **Flag findings:** env var, `-ot` vs `--lazy-mode`, `--fit`.
- **What failed or was skipped, and why.**
- **`apply-flashnext-v4.sh`:** v3's script extended to change the binary path and add or remove flags in the flashnext block. It must be self-validating and self-tested on scratch copies, and **not run**. Print the exact apply and rollback commands for each option.
