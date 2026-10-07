# Task 02 — the gate that breaks local LLMs

**Role:** Gate / fixture source material. **Not** a numbered result run.
**Raw copies:** repo root (`task02.py`, `task02_v3.py`, `task02-baseline.json`, `runs/task02-*`)
**Updated:** 2026-10-07

What Zef measures quality with, and why it is hard: the probes, NOTIFIER, and Prompt B vs B2.
Prompts A and B are in `inputs/flashnext-eval-python-task02.md`; Prompt B as sent is in `corpus/cold/B.json`.

---

## What Task 02 is

A **clean-room coding gate**: the model must implement a four-file Python circuit-breaker
package from a single user prompt (`prompt_B.txt`), then a separate `probe.py` scores the
artifacts mechanically.

| Target file | Role (from harness) |
|---|---|
| `breaker_state.py` | State types |
| `call_context.py` | Call context |
| `breaker_events.py` | Events + **NOTIFIER** binding (probe’s expected home) |
| `circuit_breaker.py` | Breaker logic that must *read* NOTIFIER correctly |

Harness lives on-box at `/mnt/ai/evals/harness/` (`prompt_A.txt`, `prompt_B.txt`, `probe.py`);
driver notes in `eval-task02.sh`. Prompt B = Prompt A + a short “Invariant discipline”
clause (per Run 1 DECISIONS D3).

### Clean-room rules (contamination)

From the harness / `task02.py` docstring:

1. Run directory is created **EMPTY**.
2. Prompt and `probe.py` live **outside** the run dir during generation.
3. `probe.py` is copied in **only at score time** — a probe sitting in the cwd during
   generation is contamination.

Meta artifacts (response, reasoning, timings) go to a sibling `*.meta` dir so the run dir
holds only model-written `.py` files until score.

---

## Why it breaks (or stresses) local LLMs

These are observed properties of the gate, not judgments of the model:

1. **Long agentic generation.** Baseline scored run: `predicted_n` **58,765** tokens,
   wall **~1921 s** (~32 min), `finish_reason: stop`, all four files present. Budget is
   `max_tokens` **60,000**; 16k voids (length, empty content).
2. **Multi-file integration.** Logic can be right and still FAIL if one symbol is bound in
   the wrong module (see NOTIFIER).
3. **Cold first request.** Gate runs with **no warm-up**. That is also how Run 1 discovered
   the ubatch CUDA abort: `prompt_B` as the *first* request killed ub>512 servers that
   looked fine after a warm-up.
4. **Prefill footprint.** Templated Prompt B ≈ **772** tokens (`prompt_n`); used in the
   11/11 cold-start suite (prompt_B ×3).
5. **Sampling + extraction sensitivity.** Wrong temp → more NOTIFIER slips / overthink;
   harness extractor bugs can steal a filename from a usage snippet (Run 3 W9 fix).

---

## Probes and Gate 4

| Probe | Role |
|---|---|
| **1, 2, 3, 5** | Scored. All must **PASS** → **Gate 4** passes. |
| **4** | Standing **control** — expected to trip / FAIL (threshold / “crit 7”). Not a capability fail. |

`task02.py` records probe 4 as `probe4_control: FAIL_expected` when the control text appears.
`task02_v3.py` sets `gate4 = all(probe{n} == PASS for n in 1,2,3,5)` and richer probe-4 parsing.

### Diagnostic vs gate (critical)

`task02_v3.diag_score` injects `circuit_breaker.NOTIFIER` as well as `breaker_events.NOTIFIER`.
Docstring: **“Diagnostic only … Never the gate.”**

Many IQ3 / temp-1.0 “fails” are **placement** fails: diagnostic logic PASS (same profile as
passing Q2), literal gate FAIL (`NameError` on bare `NOTIFIER`). They read as
**prompt ambiguity / integration** failures, not quant capability failures.

---

## NOTIFIER, Prompt B, Prompt B2

**Prompt B (runs 1–4):** Spec introduces NOTIFIER in the `breaker_events` *section* but does
**not** explicitly name which module must bind it. The probe assigns
`breaker_events.NOTIFIER`. Models that put a bare annotation in `circuit_breaker.py` and call
the bare name → NameError → Gate 4 FAIL.

**Prompt B2 (Run 5 planned):** Same task + explicit sentence that NOTIFIER lives in
`breaker_events`, so remaining fails mean real errors, not spec ambiguity
(see `meth-v5-prompt-b2`, METHOD_PROMPTS v5).

`task02_v3.notifier_map` (AST) classifies bound / annotation-only / imported / read — used in
Run 3–4 writeups to explain slips without re-running as a pass.

---

## Harness files in this repo

| File | What it is |
|---|---|
| `task02.py` | v2 Phase F runner: clean-room gen + extract + score |
| `task02_v3.py` | v3: W9 extractor, `/slots` sampling verify, NOTIFIER map, diag score |
| `task02-baseline.json` | Example **PASS** result (`label: baseline`) |

### Baseline snapshot (verifiable from JSON)

| Field | Value |
|---|---|
| wall_s | 1921.3 |
| finish_reason | stop |
| prompt_n | 772 |
| predicted_n | 58765 |
| predicted_ps | ~30.64 |
| files | all four present |
| probes 1/2/3/5 | PASS |
| probe4_control | FAIL_expected |
| scored | true |

Matches Run 1 REPORT note that baseline needed **58,765** tokens to reach `stop`.

---

## How runs 1–5 used Task 02

| Run | Use of Task 02 |
|---|---|
| **1** | Sanity / Gate 4 on shipped ub512 (PASS). Candidates at ub>512 **abort** on cold `prompt_B`. Void at max_tokens 16k; re-run at 60k. |
| **2** | Gate 4: Q2 **2/2** PASS; IQ3 **1/2** (run1 NOTIFIER NameError, diag PASS). Cold suite includes prompt_B ×3. |
| **3** | Primary experiment surface: temp 0.3 vs 1.0 × Q2/IQ3. All gate fails = NOTIFIER wrong module. Extractor bug fixed (W9). |
| **4** | Gate 4 on mainline M and MTP k=2 — both PASS; NOTIFIER read from `breaker_events`. |
| **5** | Planned: Prompt **B2** + reasoning_effort × presence_penalty sweep. **Results pending.** |

---

## Notes

| Topic | Notes |
|---|---|
| Prompt text | Prompts A and B: `inputs/flashnext-eval-python-task02.md`. Prompt B as sent: `corpus/cold/B.json`. |
| Baseline JSON vs Run 1 | Aligns (`predicted_n` 58765). Treat as the Run 1 baseline Task 02 artifact, not a new night. |
| “Breaks local LLMs” | Describes how demanding the gate is. IQ3’s logic passed the diagnostic probe on its gate failures; models are not generally broken. |
| B vs B2 | B2 is planned for Run 5 (METHOD_PROMPTS, `meth-v5-prompt-b2`); the harness keeps the diagnostic score separate from the gate. |
| Rubric /36 | The 13-criterion rubric is in `april/rubric.md`. Run 2’s provisional rubric scores (34/36 etc.) are in `REPORT-v2.md`. |

