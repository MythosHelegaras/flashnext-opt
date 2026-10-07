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
