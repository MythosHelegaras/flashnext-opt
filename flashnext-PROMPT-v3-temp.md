# flashnext v3 — sampling test: Task 02 at Qwen's recommended temp, both quants

Unattended run in `~/flashnext-opt/`. **All hard rules in `PROMPT.md` §1 apply.** Read
`REPORT-v2.md` and `DECISIONS-v2.md` first. Write `state-v3.json`, `results-v3.jsonl`,
`DECISIONS-v3.md`, `REPORT-v3.md`. **Apply nothing to llama-swap.**
HARD_STOP: 6 hours after start, or 07:00, whichever is first.

## Question

v2 ran every Task 02 at `temp 0.3`. Qwen recommends `temp 1.0, top_p 0.95, top_k 20,
min_p 0` for thinking mode, and its published benchmarks use temp 1.0. Does recommended
sampling change Task 02 outcomes or reasoning length for either quant? In v2, IQ3_XXS failed
gate 4 on a spec-reading deviation (NOTIFIER placed outside `breaker_events`), not a logic
error. This run tests whether sampling is part of that story.

## Configs (fixed, from v2 — do not re-tune)

- **Q2:** UD-Q2_K_XL, `-ncmoe 46 -b 2048 -ub 2048 -c 131072`, q8_0/q8_0 KV
- **IQ3:** GSQ-RCO IQ3_XXS, `-ncmoe 46 -b 2048 -ub 2048 -c 131072`, q8_0/q8_0 KV
- Same mandatory flags and paths as v2. Group the work by model (all Q2 runs, then all IQ3, or the reverse).

## Sampling

Set sampling **per request** in `task02.py` (request parameters override server CLI
defaults): `temperature 1.0, top_p 0.95, top_k 20, min_p 0.0`, `max_tokens 60000`, a
**different seed per run** (log it). After the first request of each server, read `/slots`
and log the effective sampling. If it does not match, the run is void.

## Runs

Task 02 Prompt B, verbatim, cold server, no warm-up, fresh empty directory per run,
`probe.py` from v2. **3 runs per quant at temp 1.0** (6 runs total, ~35 min each).

Per run record:
- finish_reason
- reasoning tokens and content tokens
- wall time and decode t/s
- probes 1–6
- where `NOTIFIER` is assigned and read (module name)

If a run ends with `length` at 60000, it is void, not a failure. Log it and re-run once.

If time remains after the 6 runs, run 2 more for each quant at **temp 0.3**, so each quant has
3 samples at 0.3 when combined with v2's runs. Use v2 seeds/settings.

## Analysis (REPORT-v3.md)

1. A table per quant × temp with:
   - runs that passed gate 4 (probes 1, 2, 3, 5)
   - NOTIFIER module choice per run
   - mean reasoning tokens
   - mean wall time
2. Did temp 1.0 change the pass rate, the NOTIFIER choice, or reasoning length? With n=3
   per cell, say plainly what n=3 can and cannot show. One flip is not a trend.
3. Reasoning length matters for speed: wall time per solved task = reasoning + content
   tokens / decode rate. If one temp solves with markedly fewer tokens, quantify the time
   saved per task.
4. Recommendation, framed as options for Zef, without applying anything:
   - which quant
   - which temp for production (`--temp` in the flashnext block)
   - the apply command for each option
