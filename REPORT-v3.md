# flashnext v3 — Task 02 at Qwen's recommended sampling — REPORT
**2026-10-05 17:01 → 22:30 · Monster · same fork/binary as v2 · both quants at `-ncmoe 46 -b 2048 -ub 2048`, 128k, q8_0/q8_0**
Nothing was applied. llama-swap is running the original config and is unloaded.

## Verdict
**Temperature 1.0 did not help. Q2 is still the quant. Keep `--temp 0.3`.**
- **Pass rate:** temp 1.0 passed gate 4 in 3 of 6 runs; temp 0.3 passed in 5 of 6.
- **Reasoning length:** at temp 1.0 the model wrote 12% fewer tokens on Q2 and 19% fewer on IQ3. Neither difference is outside the noise.
- **All 4 gate-4 failures are the same thing:** NOTIFIER put in the wrong module. That is a misreading of an ambiguous prompt; the logic in those runs is correct (the diagnostic probe passes it).
- **Temp 1.0 made the misreading more often:** 3 of 6 runs vs 1 of 6, and **Q2 made it for the first time on record**.
- **IQ3 overthinks.** 4 of its 10 attempts hit the 60k cap; Q2 hit it 0 times in 6.
- **None of these differences is statistically significant** (Fisher p = 0.23–0.55).

## 1. Results per quant × temp (Task 02 Prompt B, cold server, no warm-up, `max_tokens 60000`)
temp 1.0 = `temperature 1.0, top_p 0.95, top_k 20, min_p 0.0`, a new seed per run.
temp 0.3 = v2's request verbatim (min_p is the server default 0.05, seed 20260929). The 0.3 cells combine v2 F/F2 with the v3 top-up.
`/slots` confirmed the effective sampling on **every** run, both during and after the request. No run was voided for sampling.

| quant | temp | gate 4 pass (P1,2,3,5) | NOTIFIER read from | void @60k / attempts | mean reasoning tok | mean content tok | mean wall s |
|---|---|---|---|---|---|---|---|
| Q2 | 0.3 | **3/3** | be, be, be | 0 / 3 | 42,649 ±10,405 | 1,884 ±271 | 1,520 ±411 ‡ |
| Q2 | 1.0 | **2/3** | be, be†, **cb** | 0 / 3 | 36,688 ±7,505 | 2,497 ±226 | 1,236 ±272 |
| IQ3 | 0.3 | **2/3** | **cb**(v2 r1), be, be | 3 / 6 | 43,371 ±8,126 | 1,717 ±55 | 1,513 ±306 |
| IQ3 | 1.0 | **1/3** | **cb**, **cb**, be | 1 / 4 | 34,424 ±1,810 | 1,998 ±236 | 1,196 ±37 |

Notes on the table:
- **Means:** taken over scored runs only. Void runs are excluded.
- **be / cb:** be = `breaker_events.NOTIFIER`, which is what `probe.py` sets. cb = a bare annotation plus bare reads inside `circuit_breaker.py`, which raises `NameError` when the probe runs.
- **Diagnostic probe:** a copy of the probe that also injects `circuit_breaker.NOTIFIER`. Every cb run passes it on 1, 2, 3 and 5, with probe 4 tripping as the control. That is the same logic profile as every passing run.
- **Probes 1–6:** `probe.py` only defines probes 1–5. There is no probe 6 (W3).
- **† Q2 t1.0 r2 hedges:** it reads `getattr(breaker_events, "NOTIFIER")`, falls back to its own global, and silently skips the event if neither is set.
- **‡ Q2 t0.3 v3 r3 ran slower:** 26.9 t/s for the whole run, against Q2's usual 31–32, while the desktop was busy (Brave ~70% CPU, load average 14–16). This affects its wall time only. That is why §3 compares tokens, not wall time.

Per-run detail:

| run | seed | finish | gate 4 | reasoning / content tok | t/s | wall s |
|---|---|---|---|---|---|---|
| Q2 0.3 v2-F / v2-F2 / v3-r3 | 20260929 | stop ×3 | P / P / P | 53,142/1,941 · 32,335/1,589 · 42,470/2,122 | 29.9 / 32.1 / 26.9‡ | 1844 / 1058 / 1658 |
| Q2 1.0 r1 / r2 / r3 | 20261005–07 | stop ×3 | P / P / **F (cb)** | 35,553/2,359 · 44,696/2,757 · 29,816/2,374 | 32.0 / 31.1 / 32.5 | 1187 / 1529 / 993 |
| IQ3 0.3 v2-F / v2-F2 / v3-r3-rerun | 20260929 | stop ×3 | **F (cb)** / P / P | 34,149/1,654 · 46,480/1,738 · 49,484/1,758 | 30.9 / 29.7 / 29.7 | 1163 / 1645 / 1731 |
| IQ3 0.3 v3-r3, r4, r4-rerun | 20260929 | **length ×3** | void | 60,000/0 · 59,999/0 · 59,998/0 | 28.5–28.9 | ~2,090 each |
| IQ3 1.0 r1 / r2 / r3-rerun | 20261008/09/11 | stop ×3 | **F (cb)** / **F (cb)** / P | 32,775/2,222 · 36,360/1,752 · 34,138/2,021 | 30.7 / 30.9 / 31.1 | 1187 / 1237 / 1164 |
| IQ3 1.0 r3 | 20261010 | **length** | void | 58,086/1,912 (cut mid-answer) | 28.9 | 2078 |

**About the IQ3 voids:**
- None of them is a hard repetition loop: 342–382 of the last 400 lines are distinct in each.
- The three temp-0.3 voids never start the answer. They end in a self-audit list that keeps growing, e.g. "Potential issue: if `circuit_breaker.py` should not use `warnings.warn` with `module`? Not.", run across every kwarg × method × state.
- The temp-1.0 void had already decided to answer and was cut 1,912 tokens into it.

## 2. Did temp 1.0 change anything? What n = 3 can and cannot show
- **Pass rate.** Fails were 3/6 at temp 1.0 vs 1/6 at 0.3, pooled over both quants. Fisher p = 0.55.
  - This *could* be a real effect. It is equally consistent with chance.
  - n = 3 per cell can only detect a near-total collapse, such as 0/3 against 3/3. Even that gives p = 0.1.
  - One flip per cell is not a trend, and that is all there is here.
- **NOTIFIER choice.** This is the one effect with a plausible mechanism, and v3 found why the slip exists at all (W12).
  - Prompt B says "assume a **module-level** `NOTIFIER` object exists" inside the `breaker_events.py` item and never names the module. The `circuit_breaker.py` item then says "NOTIFIER is its sole point of contact".
  - Both readings are available. A flatter sampling distribution (temp 1.0, min_p 0) picks the less likely one more often: 3/6 vs 1/6.
  - **The slip is not IQ3-specific.** Q2 made it at temp 1.0 (r3), so v2's "Q2 has never made it" is now false.
  - Treat it as a prompt ambiguity that sampling can surface, not as a quality difference between quants.
- **Reasoning length.** Temp 1.0 used fewer tokens per scored run: Q2 −12% (39.2k vs 44.5k) and IQ3 −19% (36.4k vs 45.1k).
  - Both differences are under 2 sd: Q2 sd ≈ 8–11k, IQ3 at 0.3 sd ≈ 8k. That makes them **noise** under §7.
  - The direction does match the void pattern. IQ3 at 0.3 never committed in 3 of 6 attempts; at 1.0 that happened in 1 of 4.
- **Quant.** The only signal is IQ3's tendency to overthink: 4 of 10 attempts hit the cap vs Q2's 0 of 6 (p = 0.23). v2 saw no voids, so this is new and not yet significant.

## 3. Speed: decode time per *passing* task (tokens ÷ decode rate)
I used a common rate here (Q2 31.0 t/s, IQ3 30.0 t/s; see the ‡ note), because one run's wall time was hit by desktop contention.

| quant | temp | mean tok per scored run | s per scored run | attempts per pass (incl. voids) | **s per passing task** |
|---|---|---|---|---|---|
| Q2 | 0.3 | 44,533 | 1,437 | 3/3 → 1.0 | **1,437** (24 min) |
| Q2 | 1.0 | 39,185 | 1,264 | 3/2 → 1.5 | **1,896** (32 min) |
| IQ3 | 0.3 | 45,088 | 1,503 | 6/2 → 3.0 (3 voids × 2,000 s) | **~5,500** (92 min) |
| IQ3 | 1.0 | 36,423 | 1,214 | 4/1 → 4.0 | **~5,640** (94 min) |

- **Q2:** temp 1.0 saves about 170 s (−12%) per *run*, but that is noise (above). Because it passed one run fewer, it *costs* about 460 s per *passing* task at these counts.
- **IQ3:** about 3× Q2 per passing task, at either temp. The cost comes from voids and fails, not decode speed.
- **None of this is precise.** One flip in any cell moves its last column by 1.5–3×. The honest summary is "no measurable time saving from temp 1.0".

## 4. Options for you (nothing applied)
`apply-flashnext-v3.sh` is v2's script plus an optional `FLASHNEXT_SAMPLING` that rewrites only the `--temp` line.
- It keeps the same backup / by-key / diff-exactness / auto-restore checks.
- I self-tested it on scratch copies: diffs of 1, 2 and 3 lines, and a malformed input was refused and restored (W20).
- It prints its rollback command, which is `cp <backup> ~/.config/llama-swap/config.yaml && systemctl --user restart llama-swap`.

**Option A — recommended: Q2, ub2048, keep temp 0.3** (= v2 Option A). 3/3 at 0.3, no voids, −8.8% session time vs shipped.
```
bash ~/flashnext-opt/apply-flashnext-v3.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048" && systemctl --user restart llama-swap
```
**Option B — Q2, ub2048, Qwen's recommended temp 1.0.** Take this if you weigh Qwen's guidance and the published-benchmark setting over 2/3 vs 3/3 here. Expect the NOTIFIER-style reading of an underspecified spec more often, and slightly shorter reasoning (not proven).
```
FLASHNEXT_SAMPLING="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0" \
  bash ~/flashnext-opt/apply-flashnext-v3.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048" && systemctl --user restart llama-swap
```
**Option C — IQ3_XXS at temp 1.0.** Not recommended: 1/3 pass, 1 of 4 attempts voided, 3.0% slower sessions (v2). Temp 1.0 does cut IQ3's overthinking (1 of 4 voids vs 3 of 6 at 0.3), so if you ever run IQ3, run it at 1.0.
```
FLASHNEXT_SAMPLING="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0" \
  bash ~/flashnext-opt/apply-flashnext-v3.sh "-ncmoe 46 -t 16 -b 2048 -ub 2048" \
  /mnt/ai/llm/models/qwen3.8-flash-next-gsq/IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf \
  && systemctl --user restart llama-swap
```
**Option D — keep shipped** (Q2, n42/ub512, temp 0.3): do nothing.

**Two OpenCode facts that matter more than temp** (read-only, from `~/.config/opencode/opencode.json`):
1. **No `temperature` is set for flashnext.** So the server's `--temp` very likely governs. I didn't capture a live OpenCode request; to confirm, read `/slots` during one.
2. **`limit.output: 32768`.** Four of the five Q2 Task 02 runs on record generated 33–55k tokens. In OpenCode, a task like this would mostly be cut off before the answer, at any temperature, on either quant. Raising that limit (or giving flashnext a reasoning budget) is likely a bigger lever than `--temp`. This was out of scope, so I didn't touch it.

## Crashed / skipped / changed
| item | what happened |
|---|---|
| `PROMPT-v3.md`, `PROMPT.md` | Neither exists. I used `flashnext-PROMPT-v3-temp.md` and v1's `flashnext-overnight-PROMPT.md` (W1). |
| HARD_STOP | 17:01 + 6 h = 23:01 (earlier than 07:00). Runs had to end by 22:45. Done 22:30. |
| **Harness bug (mine)** | v2's extractor took the *first* code block naming a file. Q2 t1.0 r3 starts with a 3-line usage snippet, which stole `circuit_breaker.py`. I fixed the extractor to prefer the block under the file's heading, then the longest. It gives byte-identical output on every earlier run (v1, v2 ×4, v3). I re-extracted r3 offline from its saved response; it still fails, on the NOTIFIER placement (W9/W10). |
| Voids | 4 × `length` at 60k, all IQ3. Each void was re-run once. IQ3 t0.3 r4 voided twice, so it has no scored sample. |
| Sample counts | "2 more at 0.3 → 3 samples" doesn't add up, since v2 already has 2. IQ3 got 2 more attempts (1 scored). Q2 got 1 (r3); Q2 r4 was **skipped for time**. Each 0.3 cell ends at n = 3 scored (W16, W19). |
| Rubric | Not re-scored. v3's question is gates, NOTIFIER and length. |
| Crashes | None. Every server was alive after its run, with no CUDA errors. VRAM was 9,558→9,680 (Q2) and 10,150→10,176 (IQ3), identical to v2. MemAvailable was ≥ 85.5 GiB after every load. |

## Finish-phase verification (22:25)
- **Test servers:** none left. The GPU held 835 MiB (desktop).
- **llama-swap:** started and active.
- **flashnext via `:9292`, max_tokens 500:** returned `PROBE_OK` with `stop`, 34 tokens, in 4 s.
- **`/running`:** shows the original shipped cmd (Q2, `-ncmoe 42 … -ub 512 … --temp 0.3`).
- **`GET /unload`:** returned `OK`, and `/running` is now [].
- **config.yaml:** untouched (mtime 2026-10-01 11:10).

Raw data:
- `results-v3.jsonl`: every run, with request sampling, `/slots` during and after, token split and NOTIFIER map, plus `kind: rescore` rows.
- `DECISIONS-v3.md`: W1–W22.
- `runs/task02-v3-*` and their `.meta/`: raw response JSON, `probe.out`, `probe_diag.out`.
- Scripts: `task02_v3.py`, `run_v3.py`, `rescore_v3.py`, `summ3.py` (with a `cost` mode).
- `v2-tokens-v3.json`: v2's runs re-counted on the same token scale.
