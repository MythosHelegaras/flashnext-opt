# Methodology prompts — Claude overnight missions

**Role:** Process/source material for how Zef ran the work. **Not** numbered result runs.
**Raw copies:** repo root (`flashnext-overnight-PROMPT.md`, `flashnext-overnight-PROMPT-v2.md`, `flashnext-PROMPT-v3-temp.md`, `flashnext-PROMPT-v4-mainline-mtp.md`, `flashnext-PROMPT-v5-q2-baseline.md`)
**Related fixture:** `paper/TASK02_GATE.md` + repo-root `task02.py` / `task02_v3.py` (Prompt B harness)
**Updated:** 2026-10-07

These are the mission briefs Claude Code ran unattended on Zef’s desktop (“Monster”).
Each maps 1:1 to a run’s REPORT/DECISIONS. Campaign use: transparency / process posts —
summarize gates and rules; **do not dump full prompts**.

---

## Machine / process frame (all prompts)

| Element | Spec |
|---|---|
| Host | “Monster”: Ryzen 9 9950X, 96 GB DDR5 (~91 usable), RTX 5070 Ti 16 GB sm_120, CachyOS |
| Workdir | `~/flashnext-opt/` |
| Mode | Unattended overnight; HARD_STOP (typically 07:00 local); start finish phase early |
| Hard rules | No sudo; no downloads; no rebuilds of production binaries (with stated exceptions); port **9997** only for tests; long jobs via `setsid nohup`; resumable `state*.json` |
| Mandatory flags | `LLAMA_ATTN_ROT_DISABLE=1`, `-ot per_layer_token_embd=CPU`, `-ngl 999`, `-fa on`, `-np 1`, `--jinja` |
| Apply policy | v1 could apply if all gates passed; **v2+ write apply scripts but do not run them** — Zef decides |
| Noise rule | < 3% or < 2× combined sd ⇒ “no difference” (from v1 §7; reused later) |

---

## Prompt → run map

| Prompt file | Run | Question asked | Primary metric | Apply? |
|---|---|---|---|---|
| `flashnext-overnight-PROMPT.md` | **1** | Best flashnext llama-swap config vs shipped | `T_turn = TTFT32k + 1500/D32k` | Yes if all gates |
| `flashnext-overnight-PROMPT-v2.md` | **2** | Q2 vs IQ3_XXS on patched fork; session-first | `session_s` (growing chat) | **No** — report only |
| `flashnext-PROMPT-v3-temp.md` | **3** | Does Qwen temp 1.0 beat temp 0.3 on Task 02? | Gate-4 pass rate + reasoning length | **No** |
| `flashnext-PROMPT-v4-mainline-mtp.md` | **4** | Fork F vs mainline M; MTP on M (Q2 only) | `session_s` | **No** |
| `flashnext-PROMPT-v5-q2-baseline.md` | **5** (results pending) | `reasoning_effort` × `presence_penalty`; freeze Q2 baseline | Task 02 B2 pass count, then runaways, then tokens | **No** |

Run **6** has no prompt in this batch yet.

---

## What each prompt instructed

### v1 — overnight optimization (Run 1)

- **Mission:** Find a config strictly better than shipped for agentic OpenCode use; prove with same-night measurements; apply only if every gate passes. “No change” is valid.
- **Search space:** ubatch/batch × ncmoe × context (128k/256k); optional KV f16 vs q8; load-mode; prefix reuse. **Weights:** Q2 only. **Out of scope that night:** q4_0 KV, MTP (“measured slower”), sampling changes, context < 131072.
- **Phases:** Preflight → baseline → batch/ubatch×ncmoe → KV accuracy → load mode → multi-turn prefix → Task 02 sanity → finish/apply.
- **Gates:** (1) FULL peak VRAM ≤ **13,400 MiB**; (2) context ≥ 131072 + FULL needles; (3) speed: `T_turn` ≥ **5%** better and > 2× sd, D0/D32k and FULL ≥ **95%** of baseline; (4) Task 02 Prompt B probes 1,2,3,5; (5) accuracy if KV/weights change; (6) 256k tie rule within 2%.
- **Assumption baked in:** Load-time VRAM is only a pre-filter; post-fill peak decides eligibility.

### v2 — quant decision (Run 2)

- **Mission:** Re-baseline after mmq patch (#27792 / PR #27044); compare **UD-Q2_K_XL** vs **GSQ-RCO IQ3_XXS**; **do not apply**.
- **Metric shift:** Primary = **session time** (20k start + 15× ~3k turns), not fresh 32k prefill — matches growing OpenCode sessions; notes 96% prefix reuse at 60k from v1.
- **Gates tightened:** Cold-start robustness = **11 cold starts** (8 lengths + prompt_B ×3); Task 02 max_tokens **60000**.
- **Decision rule:** IQ3 recommended only if all gates pass **and** `session_s` ≤ **1.10×** best Q2 (Zef accepts ≤10% slower for published precision). Cannot measure accuracy gain locally; Task 02 only detects regression.
- **Explicit:** Do not mix v1 and v2 speed numbers (different binary).

### v3 — sampling (Run 3)

- **Mission:** Fixed v2 configs (Q2 and IQ3 at n46/ub2048); test **temp 1.0** (Qwen recommended) vs standing **0.3** on Task 02 Prompt B.
- **Design:** 3 runs/quant @1.0; optional more @0.3 to combine with v2. Different seed per run; verify `/slots` matches or void.
- **Analysis rules:** n=3 — one flip is not a trend; quantify wall time if token counts differ; recommend without applying.
- **Assumption:** IQ3’s v2 gate-4 miss might be sampling-related (NOTIFIER placement), not pure logic.

### v4 — engine + MTP (Run 4)

- **Mission:** Compare fork **F** (`llama.cpp-qwen4exp`) vs mainline **M** (`llama.cpp-flashnext` `abeada335`); if M passes, test **MTP** draft on M. Q2 only; IQ3 out of scope.
- **Exceptions:** May read `/opt/llama.cpp-flashnext` (still no build/patch). Still must not touch `/opt/llama.cpp`.
- **Gates:** Same as v2 (VRAM, FULL, 11 cold, Task 02). Engine verdict: M wins if gates pass and session_s ≤ F (tie → M, to drop hand-patched fork).
- **MTP:** Treat prior “MTP slower” note as **not applicable** (old experimental patch vs merged PR 29761). Try n-max ∈ {1,2,3}; win needs session_s better than M alone by more than noise.
- **Driver note:** Re-baseline F on today’s driver (615 / 13.4); do not use v2 numbers as comparison base.

### v5 — reasoning + frozen baseline (Run 5, prompt only)

- **Mission:** On **fixed** live server config, sweep request-side **`reasoning_effort`** (`xhigh` vs `medium`) × **`presence_penalty`** (0.0 vs 1.0) = cells X0/X1/M0/M1. Freeze a reusable **BASELINE-Q2** for future quants (IQ4_XS, IQ3_S).
- **Prompt asserts live block:** mainline `abeada335`, `-ncmoe 48 -b 2048 -ub 2048 -c 262144`, temp 0.3 — **see contradiction flag below**.
- **Task change:** Prompt **B2** = Prompt B + explicit sentence that `NOTIFIER` lives in `breaker_events` (fixes ambiguity that caused v2–v4 gate fails). `length` at 60k = runaway = failure (no re-run-away).
- **Decision order:** highest Task 02 pass count → fewest runaways → lowest mean tokens. `medium` may only win if pass count ≥ X0’s.
- **Results:** not in package yet — do not claim outcomes.

---

## Gates & metrics cheat sheet (campaign-safe)

| Gate / rule | Definition | Introduced |
|---|---|---|
| VRAM | Peak process VRAM **after full-window fill** ≤ **13,400 MiB** | v1 (kept) |
| Context | `-c` ≥ 131072; FULL ≥ 90% fill; 3/3 needles; `finish_reason: stop` | v1 |
| Cold-start | 11/11 cold: lengths {300…4061} + prompt_B ×3, no warm-up | v2 (replaced v1 single sanity) |
| Task 02 / Gate 4 | Probes **1, 2, 3, 5** pass; probe 4 = standing control; clean-room 4-file Prompt B (see TASK02_GATE) | v1+ |
| Speed (v1) | `T_turn` ≥ 5% better & > 2× sd; decode ≥ 95% baseline | v1 only |
| Session (v2+) | `session_s = Σ TTFT + Σ (1500 / decode_tps_turn)` | v2+ |
| Noise | < 3% or < 2× sd = no difference | v1 §7 |
| IQ3 accept | session ≤ 1.10× best Q2 **and** all gates | v2 |
| Engine M accept | gates 1–4 + session ≤ F (tie → M) | v4 |

---

## Assumptions baked into the process (not measured results)

1. Agentic OpenCode sessions grow; prefix reuse matters → session metric over synthetic first-prompt.
2. Post-fill VRAM, not load-time, is the real constraint.
3. “No change” / “not recommended” are respectable outcomes.
4. Published IQ3 accuracy gains are external; local Task 02 only catches regressions.
5. NOTIFIER placement failures may be prompt ambiguity (addressed in v5 B2), not model stupidity.
6. Overnight agent must not leave llama-swap broken (HARD_STOP restore).

---

## Contradiction / caveat flags (vs earlier curated claims)

| Topic | Prompt says | Earlier curated | Action for campaign |
|---|---|---|---|
| MTP | v1: out of scope, “measured slower on this box” | Run 4: MTP k=2 **recommended** on mainline | Say the old slowdown was a **different experimental patch**; v4 retested merged MTP |
| Sampling | v1: leave temp 0.3 fixed | Run 3 tested 1.0 | Process evolved; not a data contradiction |
| Live production after Run 4 | Campaign: “still F n46/ub2048; M+MTP recommended not applied” | **v5 prompt asserts** live block is already **mainline + ncmoe 48 + c 262144** | **FLAG:** prompt-asserted live state as of v5 briefing. Do **not** claim M/256k applied until Run 5 REPORT/status confirms. Update “do-not-claim” if/when results land |
| Gate-4 NOTIFIER | v2–4 treated slip as model/quant issue | v5: spec never said which module holds NOTIFIER; B2 fixes it | Prefer “prompt ambiguity” framing going forward; prior fails not pure capability fails |
| Cross-run speeds | v2/v4 prompts forbid mixing binaries/drivers | Already in brief | Keep |

---

## Campaign process hooks (optional posts)

Use these without pasting prompt text:

1. **Agent-driven overnight benches** — Claude Code unattended on the desktop box; HARD_STOP morning restore.
2. **Gates before glory** — VRAM 13.4 GB, 11 cold starts, Task 02 probes; fail any → no ship.
3. **Metric matured** — night 1 optimized `T_turn`; night 2+ optimized real multi-turn `session_s`.
4. **Honesty rules** — noise floor, “no change is valid,” apply scripts written but not auto-run (v2+).
5. **Spec fix mid-series** — v5 Prompt B2 closes the NOTIFIER ambiguity that muddied earlier gate-4 stories.
