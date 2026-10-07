# flashnext-opt

Raw measurements, harness code and decision logs from tuning **Qwen3.8-Flash-Next 125B-A6B**
(MoE, GGUF) for agentic coding on one consumer GPU with llama.cpp. Published as the evidence
behind the accompanying paper. Every run was carried out by an unattended coding agent working from
the prompt files in this repo. Each run's decisions were logged as they were made
(`DECISIONS*.md`) and summarised afterwards (`REPORT*.md`).

## Test system

| | |
|---|---|
| CPU / RAM | AMD Ryzen 9 9950X, 96 GB DDR5 |
| GPU | NVIDIA RTX 5070 Ti 16 GB (sm_120) |
| OS | CachyOS (Arch-based) |
| Engines | llama.cpp `qwen4exp` fork `bea3b12d` (v1–v3); mainline llama.cpp `abeada335` (v4) |
| Quants | Unsloth UD-Q2_K_XL; ISTA-DASLab GSQ-RCO IQ3_XXS (v2–v3) |

Exact driver, CUDA and compiler versions for each run are in the report headers and `logs/v4/preflight.txt`.

## Runs

| Run | Dates | Question | Prompt | Report | Decision log | Results |
|---|---|---|---|---|---|---|
| v1 | 2026-09-28/29 | Best `-ncmoe`/batch/KV config on the fork | `flashnext-overnight-PROMPT.md` | `REPORT.md` | `DECISIONS.md` | `results.jsonl` |
| v2 | 2026-10-05 | Q2 vs IQ3_XXS on the patched fork | `flashnext-overnight-PROMPT-v2.md` | `REPORT-v2.md` | `DECISIONS-v2.md` | `results-v2.jsonl` |
| v3 | 2026-10-05 | Sampling temperature 0.3 vs 1.0 (Task 02) | `flashnext-PROMPT-v3-temp.md` | `REPORT-v3.md` | `DECISIONS-v3.md` | `results-v3.jsonl` |
| v4 / v4b | 2026-10-06 | Fork vs mainline, MTP, 128k vs 256k | `flashnext-PROMPT-v4-mainline-mtp.md` | `REPORT-v4.md` | `DECISIONS-v4.md` | `results-v4.jsonl` |

`flashnext-PROMPT-v5-q2-baseline.md` is the prompt for the next run. No results for it are in this repo yet.

## Layout

- `harness*.py`, `phase*.py`, `run*.{py,sh}`: benchmark harness and per-phase drivers (llama-server + HTTP API timings).
- `task02*.py`, `inputs/flashnext-eval-python-task02.md`: the Task 02 coding eval (circuit breaker) and its spec.
- `runs/task02-*/`: code the model wrote in each Task 02 attempt. `runs/*.meta/`: its reasoning, raw API response, and the probe output used for scoring.
- `logs/`: every llama-server log and phase log, named by run and config (`n46` = `-ncmoe 46`, `ub2048` = `-ub 2048`).
- `corpus/`: prompts used for prefill, session and cold-start tests. See `REDACTIONS.md` for the files that are not included and `corpus/SHA256SUMS` for their hashes.
- `crashtest*.py`, `verify-ub-crash.sh`, `patch-mmq-ubfix.sh`: reproduction of the `-ub > 512` CUDA crash and its fix (llama.cpp #27792).
- `apply-*.sh`, `set-opencode-*.sh`: the scripts that applied each accepted config to the serving stack.
- `state*.json`: run state used to resume after interruptions.

## Acceptance gates (v2 onward)

1. Peak VRAM, measured after a full-window fill, at or below 13,400 MiB.
2. Fill to at least 90% of the window, 3 of 3 needles retrieved exactly, `finish_reason: stop`.
3. 11 of 11 cold starts with no warm-up request.
4. Task 02 cold run, `max_tokens 60000`: probes 1, 2, 3 and 5 pass.

Noise rule: a difference under 3%, or under 2× the standard deviation, counts as no difference.

Paths in the logs (`/opt/...`, `/mnt/ai/...`) are the test machine's and are kept as recorded.

## Repetitions and how far each claim holds

Throughput metrics (P4k, P32k, D0, D32k) are 3 reps. Full-window fills and session runs are 1 rep
unless a table says otherwise. The single-rep claims stand for these reasons:

| Claim | Reps | Why it holds |
|---|---|---|
| Mainline vs fork session time, −23% (v4) | M: 3 (813.2 / 816.9 / 814.6 s). F: 1 | F was measured twice on separate days and driver versions: 1,046.1 s (v2) and 1,056.4 s (v4), 1% apart. The gap is 230+ s, against a run-to-run sd of 1.9 s. |
| `-ub 2048` vs `-ub 512` session time, −8.8% (v2) | 1 each | The largest session sd observed in any 3-rep set is 8.5 s (1.1%). The gap is 101 s. |
| MTP session time, −3.9% (v4) | 3 each | 782.8 ±8.5 vs 814.9 ±1.9 s. Welch t ≈ 6.4. |
| Full-window VRAM peak under the 13,400 MiB gate | 1 | Shipped 256k config peaks at 12,366 MiB: a 1,034 MiB margin, about 4.5× the ~230 MiB allocator noise seen across runs. Configs inside that noise (ncmoe 47 at 256k: 122 MiB margin) were rejected. |
| Full-window decode/prefill, fork vs mainline | 1 each | Differences are 46% (decode) and 2× (prefill), against 1–2% sd on the 3-rep throughput metrics. |

Two claims are weaker than the reports' wording suggests:
- **IQ3_XXS is 3.0% slower per session than Q2 (v2).** One rep each, and below the 3% noise floor. Treat it as no established speed difference. The quant decision rests on Task 02 reliability (v3), not speed.
- **256k costs nothing vs 128k (v4b).** 825.4 s (1 rep) vs 814.9 ±1.9 s. That is +1.3%, under the 3% floor but about 5 sd from the 128k mean. Report it as "at most ~1.3% slower", not as identical.

Task 02 pass rates (v3) are 6 runs per arm. None of the differences are significant (Fisher p = 0.23–0.55), and `REPORT-v3.md` says so.

## Task 01 and the April 2026 bakeoff

`inputs/flashnext-eval-python-task02.md` cites a Task 01 eval (C#, Opus 35/36 vs flashnext Q2 34/36)
and an April 2026 bakeoff. Their evidence is in `april/`: the prompt, the rubric, the judge prompt, the
judges' rankings, the score sheets, Opus's and flashnext's Task 01 code, and a re-entrancy probe.
`april/README.md` gives the provenance of every file.

**Correction to the Task 02 write-up:** the probe shows Opus's Task 01 output has the same re-entrancy
bug flashnext was marked down for. The 35 vs 34 comparison does not hold; see `april/scores.md`, section 4.

## License

- **Code** (the `.py` and `.sh` files in the repo root, and `april/probe/`): MIT, see `LICENSE`.
- **Everything else** (reports, decision logs, results, logs, model outputs under `runs/` and `april/outputs/`): CC BY 4.0, see `LICENSE-DATA`.
- **Third-party text** keeps its own license: `corpus/` holds excerpts of llama.cpp source and docs (MIT, © the ggml authors),
  and `logs/v4/*-help.txt` is llama-server's own `--help` output.
