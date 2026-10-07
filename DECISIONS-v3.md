# DECISIONS-v3.md — flashnext v3: Task 02 at Qwen's recommended sampling, both quants

## Phase 0 — Preflight (17:01, 2026-10-05)

### W1. Prompt file, clock, rules
`./PROMPT-v3.md` does not exist; the mission prompt is `flashnext-PROMPT-v3-temp.md`
(2835 B, mtime 17:00 today). `PROMPT.md` is, as in v1/v2, `flashnext-overnight-PROMPT.md`;
its §1 hard rules apply. Run started **17:01**. HARD_STOP = min(17:01 + 6 h, 07:00) =
**23:01 today**. Rule: a Task 02 run (worst case 60,000 tok at ~29 t/s ≈ 35 min + load) is
started only if it can end by 22:45, leaving the finish phase (llama-swap restart + probe +
unload + report) before 23:01.

### W2. Sampling is in scope this time, per request only
§1 rule 9 of PROMPT.md puts sampling out of scope *for config tuning*; v3's whole question is
sampling, so v3 overrides it explicitly. Nothing about the server CLI changes: the server is
launched exactly as in v2 (harness2 `Server`, including the shipped `--temp 0.3 --top-p 0.95
--top-k 20`, server-default `--min-p 0.05`). Every request carries `temperature 1.0, top_p 0.95,
top_k 20, min_p 0.0, seed <per run>`. Because the CLI says temp 0.3 / min_p 0.05, the `/slots`
check is a real test of the override (both values differ from the CLI defaults).
`/slots` is read while the first (and only) request is in flight (~30 s in) and again after it
finishes. A mismatch on any of the four values voids the run and kills it early.

### W3. "Probes 1–6"
`/mnt/ai/evals/harness/probe.py` defines **PROBE 1–5 only** (4 = crit-7 control, printed for
threshold 0 and −1). There is no probe 6 anywhere in the harness or the eval doc. I record 1–5;
gate 4 is unchanged from v2 (1, 2, 3, 5 PASS, probe run as written).

### W4. Token accounting
The server reports only `predicted_n` (reasoning + content + template tags). Reasoning and
content tokens are counted by `/tokenize` on the returned `reasoning_content` / `content`
on the same server right after the run (counts are ±a few tokens of the true split; the tag
tokens are the difference to `predicted_n`). v2's four saved texts are tokenized the same way
so v2 and v3 are on one scale. Full raw responses are saved this time (`.meta/raw.json`).

### W5. NOTIFIER location
Recorded by AST over the four extracted files: where `NOTIFIER` is bound (assignment, bare
annotation — which binds nothing, `global`, `from … import NOTIFIER`) and where/how it is read
(bare name in module X, or `breaker_events.NOTIFIER` attribute). If the literal probe dies on
NOTIFIER, a *diagnostic* copy of the probe that also injects `circuit_breaker.NOTIFIER`
is run in a scratch copy (as v2 V19) — it never changes the gate result.

### W6. Run order and seeds
Grouped by model: Q2 ×3 at temp 1.0, then IQ3 ×3 at temp 1.0, then (time permitting) the
temp-0.3 top-up — **IQ3 first** (no model switch, and IQ3 is the quant whose 0.3 result is in
question), then Q2. temp-1.0 seeds: Q2 20261005, 20261006, 20261007; IQ3 20261008, 20261009,
20261010 (re-runs after a `length` void get the next unused seed). temp-0.3 runs use v2's
settings verbatim: temperature 0.3, top_p 0.95, top_k 20, **no min_p in the request** (v2 sent
none, so 0.05 from the server default), seed 20260929 — v2 showed the same seed does not
reproduce a run on this server (55k vs 34k tokens on Q2), so each is still an independent sample.

### W7. Smoke test of the override (17:02–17:03) — throwaway server, not a run
Q2 n46/ub2048, separate process (killed after; every real run still starts its own fresh
server with no warm-up). Request temp 1.0/top_p 0.95/top_k 20/min_p 0.0/seed 4242 against
CLI `--temp 0.3`, default min_p 0.05 → `/slots` during the request (`is_processing: true`) and
after: `temperature 1.0, top_p 0.95, top_k 20, min_p 0.0, seed 4242`. Per-request override is
effective. Load 4.0 s (page cache warm), 9,558 MiB = v2's figure to the MiB.
llama-swap stopped at ~17:02 (`/running` was []), config.yaml mtime 2026-10-01 11:10.

## Runs

### W8. Q2 temp 1.0, runs 1–2 (17:04–17:49): both PASS gate 4
- r1 (seed 20261005): `stop`, 37,915 tok (35,553 reasoning / 2,359 content), 32.0 t/s, 1,187 s.
  `NOTIFIER = None`-style binding in breaker_events; circuit_breaker reads `breaker_events.NOTIFIER`.
- r2 (seed 20261006): `stop`, 47,456 tok (44,696 / 2,757), 31.1 t/s, 1,529 s. **A hedge, not a slip:**
  circuit_breaker does `import breaker_events as _breaker_events`, annotates its own
  `NOTIFIER: Notifier | None` (binds nothing), and resolves the notifier per call with
  `getattr(_breaker_events, "NOTIFIER", None)` then falls back to `globals().get("NOTIFIER")`,
  skipping the event if neither is bound. The primary read is breaker_events, so it is counted
  as "breaker_events" (summ3 classifier updated to treat getattr on breaker_events as such).
  Silently skipping an unbound notifier is a design choice the rubric could dock; the probes
  bind it, so gate 4 is unaffected.
v2 reasoning/content tokens re-counted on the v3 server (W4): Q2 r1 53,142/1,941, r2 32,335/1,589;
IQ3 r1 34,149/1,654, r2 46,480/1,738.

### W9. Harness bug found and fixed: v2 extractor let a usage snippet steal `circuit_breaker.py`
Q2 t1.0 r3's response opens with a 3-line integration example (`circuit_breaker.NOTIFIER =
some_notifier`) right after mentioning `circuit_breaker.py`; v2's `extract()` keeps the *first*
block mapped to a name, so the real 151-line module under `## circuit_breaker.py` was dropped and
probe.py died on `some_notifier` at import. That is my harness, not the model. Fix
(`task02_v3.extract`): among blocks mapped to a name, prefer one directly under a heading/label
naming the file, then the longest. **Verified byte-identical output to v2's extractor on every
earlier run** (v1 baseline, v2 F/F2 × Q2/IQ3, v3 Q2 r1/r2); only r3's circuit_breaker.py changes.
The running chain had already imported the old module, so affected runs are re-extracted
offline from the saved `response.md` by `rescore_v3.py` into `runs/task02-<label>.x2/` (original
dir kept for audit) and a `kind: rescore` row is appended to results-v3.jsonl; summ3 uses it.
Every later run is checked the same way.

### W10. Q2 t1.0 r3 (seed 20261007, 17:50–18:06): gate 4 FAIL — the IQ3-r1 NOTIFIER slip, on Q2
`stop`, 32,193 tok (29,816 reasoning / 2,374 content), 32.5 t/s, 993 s. After the W9 re-extract:
`NOTIFIER: BreakerNotifier` is a bare annotation **in circuit_breaker.py** (binds nothing) and
read bare there (`_notifier()` → `return NOTIFIER`); breaker_events.py only documents "a
module-level NOTIFIER". The response's own preamble says the application must set
`circuit_breaker.NOTIFIER`. Probe → `NameError: name 'NOTIFIER' is not defined` → gate 4 FAIL
as written. Diagnostic probe (also injects `cb.NOTIFIER`, W5): 1, 2, 3, 5 PASS, 4 trips (control)
— same logic profile as every other run. **This is the first time Q2 has made this slip on
record** (v1 baseline, v2 ×2, v3 r1/r2 all used breaker_events). The slip is therefore not
IQ3-specific; it is a model-level ambiguity reading of the prompt that sampling can surface.

### W11. IQ3 t1.0 r1 (seed 20261008, 18:07–18:26): gate 4 FAIL — same NOTIFIER slip
`stop`, 35,000 tok (32,775 / 2,222), 30.7 t/s, 1,187 s. Extraction identical under the W9
extractor. `NOTIFIER: CircuitBreakerNotifier` bare annotation in circuit_breaker.py, bare reads
there (lines 98/110/135) → NameError. Diagnostic: 1, 2, 3, 5 PASS, 4 control. Logic sound.

### W12. Why this slip exists: prompt B never names NOTIFIER's module
prompt_B.txt line 25 (inside the `breaker_events.py` item): "assume a **module-level** `NOTIFIER`
object exists"; line 55 (inside the `circuit_breaker.py` item): "NOTIFIER is its sole point of
contact"; line 69: "Do not implement NOTIFIER". No line says which module holds it. probe.py
hard-codes `breaker_events.NOTIFIER`. Placing it in breaker_events is the better reading (it is
introduced there, next to the contract), but placing it in circuit_breaker is a defensible
reading of an underspecified prompt, not a logic error. So gate 4 is, in part, a measurement of
how the model resolves this ambiguity, and that is exactly the kind of choice sampling
temperature can flip. Gate 4 is still scored as written (the prompt's rule); the report states
both the literal result and the diagnostic logic result for every run.

### W13. IQ3 t1.0 r2 (seed 20261009, 18:27–18:47): gate 4 FAIL — same NOTIFIER slip
`stop`, 38,116 tok (36,360 / 1,752), 30.9 t/s, 1,237 s. Extraction identical under W9.
Bare annotation + bare reads in circuit_breaker.py → NameError. Diagnostic: 1, 2, 3, 5 PASS, 4 control.

### W14. IQ3 t1.0 r3 (seed 20261010, 18:48–19:22): VOID (`length` at 60,000)
58,086 reasoning + 1,912 content tokens, 28.9 t/s, 2,078 s; the content was cut mid-answer.
Void per the v3 prompt, not a failure; not scored. Re-run once with spare seed **20261011**
(label `v3-iq3-t10-r3-rerun`, started 19:22). It counts toward "where reasoning length goes":
the void run's 60k is reported separately, not averaged into the scored cell.

### W15. IQ3 t1.0 r3-rerun (seed 20261011, 19:22–19:42): PASS
`stop`, 36,161 tok (34,138 / 2,021), 31.1 t/s, 1,164 s; breaker_events annotation, read as
`breaker_events.NOTIFIER`; 1, 2, 3, 5 PASS, 4 control. **temp 1.0 block done:** Q2 2/3, IQ3 1/3
(all three failures = the W12 placement slip, logic PASS on the diagnostic). temp-0.3 top-up
started 19:42 (IQ3 r3, r4, then Q2 r3, r4), well inside the 22:45 cutoff.

### W16. "2 more … so each quant has 3 samples at 0.3" does not add up
v2 ran Task 02 **twice** per quant at n46/ub2048 (F and F2), so 2 more makes **4** at temp 0.3,
not 3. Time allows the explicit count, and more samples never hurt, so 2 more are run per quant
(n = 4 at 0.3 vs n = 3 at 1.0). The report also shows the 0.3 cell restricted to the first 3
samples, so a like-for-like n = 3 reading is available.

### W17. IQ3 t0.3 r3 (seed 20260929, v2 settings, 19:42–20:16): VOID (`length`, 60,000 reasoning, 0 content)
/slots confirmed temp 0.30 / top_p 0.95 / top_k 20 / min_p 0.05 / seed 20260929. 28.9 t/s, 2,077 s.
Not a hard repetition loop (377 distinct of the last 400 non-blank lines), but the tail is an
open-ended self-audit spiral ("Need maybe if `CircuitBreaker` should pass `threshold` in …? No."),
i.e. overthinking that never commits. Compare the t1.0 void (W14): it had written "Now, let's
prepare final answer" and was cut ~1,900 tokens into content. Re-run once (same v2 seed, per the
prompt's "use v2 seeds/settings"; v2 showed the seed does not reproduce a run), started 20:16.
Void count so far: IQ3 1 at t1.0, 1 at t0.3; Q2 0.

### W18. IQ3 t0.3 r3-rerun (seed 20260929, 20:17–20:46): PASS
`stop`, 51,246 tok (49,484 / 1,758), 29.7 t/s, 1,731 s; breaker_events, read as
`breaker_events.NOTIFIER`; 1, 2, 3, 5 PASS, 4 control. IQ3 r4 (t0.3) started 20:46.

### W19. IQ3 t0.3 r4 (seed 20260929, 20:46–21:21): VOID (`length`, 59,999 reasoning, 0 content)
28.5 t/s, 2,106 s. Same never-commit self-audit spiral as W17 ("Potential issue: If
`circuit_breaker.py` should not use `warnings.warn` with `module`? Not." — enumerating every
kwarg of warnings.warn); 359 distinct of the last 400 lines. Re-run once (same seed), 21:21.
**IQ3 at temp 0.3 has now hit the 60k cap 2 of 4 attempts in v3**; IQ3 at 1.0 1 of 4;
Q2 0 of 3 (v2: 0 of 4 total). Time consequence: the rerun ends ≤ 21:58, so Q2 gets **one**
t0.3 top-up (ends ≤ 22:35); Q2 r4 cannot start before the 22:45 cutoff (W1) and is skipped
for time. Q2 at 0.3 is then n = 3 (v2 ×2 + v3 ×1), which is what the prompt's "3 samples" asked.

### W20. Apply script and the OpenCode side (read-only checks, 21:22)
`apply-flashnext-v3.sh` = v2's script + optional `FLASHNEXT_SAMPLING="--temp …"` that rewrites the
single `--temp` line of the flashnext block (must keep `--top-p 0.95 --top-k 20`). Self-tested on
scratch copies: Q2 tuning only → 1-line diff; + temp 1.0 → 2 lines; + IQ3 model → 3 lines, shards
2/2; malformed sampling → refused, config restored byte-identical. Real config not touched.
`~/.config/opencode/opencode.json` (read only): the llamaswap provider sets **no temperature**
for flashnext, so the server's `--temp` is what OpenCode traffic gets — very likely; OpenCode's
built-in per-model defaults are keyed on model ID, and "flashnext" is not a qwen ID, but I did not
capture a live OpenCode request. **It also sets `limit.output: 32768`** for flashnext. Task 02
used 32–55k generated tokens in 4 of 5 v2/v3 Q2 runs, so in OpenCode this task would be cut
at 32,768 most of the time regardless of quant or temperature (not changed — out of scope).

### W21. IQ3 t0.3 r4-rerun (seed 20260929, 21:21–21:56): VOID again (`length`, 59,998 reasoning, 0 content)
28.7 t/s, 2,095 s. Same combinatorial "Potential issue: If `context.duration_ms` is negative and
`warnings.warn` called in record_X on Y and state unchanged. Good." enumeration (382 distinct of
the last 400 lines). The prompt allows one re-run, so **IQ3 t0.3 r4 has no scored sample**.
IQ3 in v3: t0.3 **3 of 4 attempts hit the 60k cap** (1 scored), t1.0 1 of 4 (3 scored).
Q2 in v3: 0 of 3 so far. Final run, Q2 t0.3 r3, started 21:56 (must end ≤ 22:33; cutoff 22:45).
Q2 t0.3 r4 will be skipped for time.

### W22. Q2 t0.3 r3 (seed 20260929, 21:56–22:24): PASS; chain done; Q2 r4 skipped for time
`stop`, 44,595 tok (42,470 / 2,122), **26.9 t/s** for the whole run (34.7 → 29.9 at 12k vs Q2 r2's
34.7 → 33.5 at the same depth). Brave at ~70% CPU and load avg 14–16 during the run: desktop
contention, so §3 of the report uses tokens ÷ a common rate, not wall time. breaker_events;
1, 2, 3, 5 PASS. `TIME: not starting v3-q2-t03-r4` (would end after 22:45).

## Finish (22:25–22:30)
No test server left; GPU 835 MiB (desktop) → `systemctl --user start llama-swap` → flashnext via
:9292 max_tokens 500 → `PROBE_OK`, `stop`, 34 tok, 4 s; `/running` = shipped cmd (Q2 n42/ub512,
--temp 0.3) → `GET /unload` → `OK`, `/running` = []. MemAvailable 85.7 GiB. config.yaml untouched
(mtime 2026-10-01 11:10). Nothing applied. Report: REPORT-v3.md.
