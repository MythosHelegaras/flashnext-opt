# flashnext v5: Q2 reasoning settings + frozen Q2 baseline

Unattended run in `~/flashnext-opt/`. **All hard rules in `flashnext-overnight-PROMPT.md` §1 apply**
(no sudo, no builds, no downloads, port 9997 only, detached long jobs, resumable state, kill only your
own PIDs). Read `REPORT-v4.md`, `DECISIONS-v4.md` and `harness4.py` first. Reuse `harness4.py`;
extend it, do not rewrite it.

Write these files: `state-v5.json`, `results-v5.jsonl`, `DECISIONS-v5.md`, `REPORT-v5.md`, and the frozen
baseline `BASELINE-Q2.md` + `baseline-q2.json` (see §5). **Apply nothing to llama-swap. Do not edit
OpenCode config.**

HARD_STOP: 9 hours after start, or 07:00, whichever comes first. Start the finish phase 30 min before it.

## 0. Fixed setup (do not tune)

- **Engine:** `/opt/llama.cpp-flashnext/build/bin/llama-server` (mainline `abeada335`).
- **Model:** UD-Q2_K_XL, same path as v4.
- **Server flags:** exactly the live llama-swap flashnext block. Read it from
  `~/.config/llama-swap/config.yaml` and log it:
  `LLAMA_ATTN_ROT_DISABLE=1`, `-ngl 999 -fa on -np 1 --jinja -ot per_layer_token_embd=CPU`,
  `-ncmoe 48 -t 16 -b 2048 -ub 2048 -c 262144`, q8_0/q8_0, `--temp 0.3 --top-p 0.95 --top-k 20`.
  If the live block differs from this, stop and log the difference. Do not run.
- Gates 1-3 (VRAM, FULL needles, 11 cold starts) already passed for this exact server config in v4b.
  Do not rerun them. This run changes **request-side sampling only**.

## 1. What is being tested

Two request-side knobs, set per request, never on the server command line:

- **`reasoning_effort`** via `"chat_template_kwargs": {"reasoning_effort": "<level>"}`.
  - Valid values: `low`, `medium`, `xhigh` only. llama.cpp accepts other names (`high`, `max`), but the
    template errors on every request with them.
  - Test `xhigh` (template default, what every run so far used) and `medium`.
- **`presence_penalty`**: `0.0` (current) and `1.0`. Qwen's model card recommends 0-2 against endless
  repetition, which is the runaway pattern seen in v2/v3.

Cells:

| Cell | effort | presence |
|---|---|---|
| X0 | xhigh | 0.0 (current production, the control) |
| X1 | xhigh | 1.0 |
| M0 | medium | 0.0 |
| M1 | medium | 1.0 |

**Verification, before any measured run:**
1. Render the chat template with `/apply-template` for `medium` and `xhigh`. Log the effort line the
   template injects. If `medium` and `xhigh` render identically, effort does nothing on this build:
   stop the M cells and log it.
2. On the first request of each cell, read `/slots` and log the effective `presence_penalty`,
   `temperature`, `top_p`, `top_k`, `min_p`. A mismatch voids the cell.

## 2. Task 02, spec-fixed version (new baseline task)

Every v2-v4 gate failure was the same ambiguity: the spec never says which module holds `NOTIFIER`.
v5 fixes it, so a failure from now on means a real error.

- Build **Prompt B2** = Prompt B (from `inputs/flashnext-eval-python-task02.md`) with one sentence
  added to the `breaker_events.py` section, right after the `NOTIFIER` methods list:
  > `NOTIFIER` is a module-level name in `breaker_events`. `circuit_breaker.py` must access it as
  > `breaker_events.NOTIFIER` at call time, never import or redeclare it.
- Save it as `inputs/prompt_B2.txt` and log its sha256. Change nothing else in the prompt.
- Same `probe.py` as v4. Gate 4 = probes 1, 2, 3, 5 pass; probe 4 is the standing control.
- Each run: cold server, no warm-up, `max_tokens 60000`, a distinct seed per run (log it).
- `length` at 60000 = a **runaway**. It counts as a failure for the cell. Do not re-run it away.

**3 runs per cell = 12 runs.** Order: interleave the cells (X0, M0, X1, M1, X0, ...), so drift or
thermal state does not land on one cell.

Per run, record:
- `finish_reason`, reasoning tokens, content tokens, total generated tokens;
- wall time and decode t/s;
- probes 1-6;
- where `NOTIFIER` is bound and read.

## 3. Session test per cell

Same v2 session harness and corpus (20k start + 15 turns of +3k, 800-token cap per turn), with each
cell's request settings. 1 rep per cell; a 2nd rep for X0 and the best other cell if time allows.

Record:
- `session_s`;
- per-turn reasoning length;
- how many turns reached `content` before the 800 cap.

Effort changes how much of each turn is spent reasoning, so content-reached turns matter as much as
time.

## 4. Decision rule (report only)

The production cell is chosen in this order:
1. Highest Task 02 pass count out of 3.
2. Tie: fewest runaways.
3. Tie: lowest mean generated tokens per passing run.

Constraints:
- **`medium` may only win if its pass count is at least X0's.** Zef defaults to the highest precision
  the rig can run, so medium needs to be as reliable as xhigh, not just faster.
- With 3 runs per cell, a 1-run difference is not a trend. Say so in the report.
- Also report the **output budget**: the max and mean generated tokens of passing runs in the
  winning cell. That decides OpenCode's output cap (`OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX`).

## 5. Frozen Q2 baseline (the point of this run)

After the cells, write `BASELINE-Q2.md` and `baseline-q2.json`. This is the reference that every future
candidate (UD-IQ4_XS next, then IQ3_S) is compared against without re-measuring Q2.

Contents:
- **Identity:** exact server command, engine path and commit, model path and shard sha256s (compute them),
  driver and CUDA versions, date.
- **Speed and VRAM** (copy from v4/v4b with their labels): D0, D32k, P4k, P32k, session_s, FULL 240k
  prefill / decode / TTFT / peak VRAM, load VRAM, MemAvailable after load.
- **Gates 1-3:** results from v4b.
- **Gate 4 and quality:** the winning cell's Task 02 B2 results (pass count, runaways, tokens per solve,
  wall per solve), plus X0's.
- **Request settings** of the winning cell, verbatim, as the JSON a client would send.
- **How to compare:** the candidate must use the same harness version (log `harness4.py` sha256), the same
  corpus, the same Prompt B2 sha256, the same request settings, and the same noise rule (< 3% or < 2× sd
  is no difference).

## 6. Finish

1. Kill your servers and confirm the GPU is empty.
2. `systemctl --user start llama-swap`, probe flashnext (max_tokens 500), `GET /unload`.

Write `REPORT-v5.md`:
- verdict (cell, settings);
- a cell table (pass, runaways, mean/max tokens, wall per solve, session_s, content-reached turns);
- the output budget;
- what failed or was skipped.

Do not write any config. If the winning cell is not X0, print the exact client-side settings to apply.
llama-swap does not take `reasoning_effort` in the server command for this run's purposes.
