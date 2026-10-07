# flashnext v4 — engine decision (mainline vs fork) and MTP on mainline — REPORT
**2026-10-06 11:50 → 15:45 · Monster · Q2 (UD-Q2_K_XL) only · driver 615.71 / CUDA 13.4 / GCC 16.2.1**
Nothing was applied. llama-swap is running the unchanged config (F, n46/ub2048) and is unloaded.

## Verdict
- **Engine: M** (mainline `abeada335`). It passes gates 1–4. Its session time is **−23%** vs the fork (815 vs 1056 s), and its full-window VRAM peak is 2 GB lower.
- **MTP: yes, n-max 2.** Session **−3.9%** vs M without MTP (782.8 ±8.5 vs 814.9 ±1.9 s, 3 reps each), which is beyond noise. It passes gates 1–4.
  - The gain is modest and depends on the workload.
  - It costs one CPU expert layer (n47), 2.2 GB of VRAM margin, −7% short-context decode and −7% prefill.
  - If you value margin and simplicity over ~32 s per session, take **Option B**.
- **Recommended llama-swap cmd** (Option A):
```
/usr/bin/env LLAMA_ATTN_ROT_DISABLE=1
/opt/llama.cpp-flashnext/build/bin/llama-server --port ${PORT}
-m /mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
-ngl 999 -fa on -np 1 --jinja
-ot per_layer_token_embd=CPU
-ncmoe 47 -t 16 -b 2048 -ub 2048
-c 131072 --cache-type-k q8_0 --cache-type-v q8_0
--spec-type draft-mtp --model-draft /mnt/ai/llm/models/qwen3.8-flash-next/MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf --spec-draft-ngl 999 -ctkd q8_0 -ctvd q8_0 --spec-draft-cpu-moe --spec-draft-n-max 2
--temp 0.3 --top-p 0.95 --top-k 20          (ttl: 1800)
```
(Tests also passed `--metrics` to read acceptance. It only enables an endpoint, so it is left out of production.)

## Comparison (128k, q8_0/q8_0, `-t 16 -b 2048 -ub 2048`; 3 reps mean ±sd; FULL = 1 rep)
| metric | **F today** (fork, n46) | **M** (n46, F's flags) | **M + MTP k=2** (n47, head experts on CPU) |
|---|---|---|---|
| P4k t/s | 587.6 ±9.1 | 688.7 ±0.1 | 642.4 ±2.5 |
| P32k t/s | 554.1 ±13.7 | **728.6 ±0.6** | 677.1 ±5.0 |
| D0 t/s | 35.77 ±0.36 | **40.13 ±0.49** | 37.17 ±0.49 |
| D32k t/s | 29.36 ±0.16 | 35.52 ±0.55 | 36.54 ±1.72 |
| FULL prefill / decode t/s (120,182 tok) | 357.0 / 19.22 | **723.5** / 28.13 | 671.8 / **35.53** |
| FULL TTFT | 336.6 s | 166.1 s | 178.9 s |
| load → **FULL peak** MiB | 9,558 → 12,486 | 9,996 → **10,482** | 11,706 → 12,686 |
| **session_s** | 1056.4 (1 rep) | 814.9 ±1.9 (3 reps) | **782.8 ±8.5** (3 reps) |
|  Σ TTFT / Σ 1500/decode | 162.3 / 894.1 | 106.4 / 706.7 (rep 1) | 116.8 / 675.6 (rep 1) |
|  turn-16 decode at ~78k | 23.31 | 31.15 | 33.56 |
| MTP acceptance (mean len) | — | — | session 66.9% (2.33) · D0 52.8% · D32k 61.9% · Task 02 70.8% · FULL answer 85.4% |
| gate 1 (FULL peak ≤ 13,400) | PASS (914 margin) | PASS (2,918) | PASS (714) |
| gate 2 (FULL 3/3, stop) | PASS | PASS | PASS |
| gate 3 (11 cold starts) | 11/11 (v2; same binary) | **11/11** | **11/11** |
| gate 4 (Task 02, probes 1,2,3,5) | PASS ×3 (v2/v3; same binary) | **PASS** (34,014 tok, 37.9 t/s) | **PASS** (49,744 tok, 37.5 t/s) |

- **Phase A, driver change:** today's F is within noise of v2 on every metric: D0 −1.8%, session +1.0%, FULL peak identical to the MiB. F's numbers above are the comparison base.
- **Why M is faster:**
  - On F, the CUDA0 compute buffer grows during the full fill to 4,469 MiB (1,722 expected), with 11.8 GB of host compute buffer. M's buffers are fixed at load: +486 MiB load→peak at both 128k and 256k.
  - M's advantage grows with depth: decode +12% at 0 tokens, +21% at 32k, +46% at 120k. Prefill is 2× at 120k.
- **Session per turn:** M's prefill stays flat at ~5.2 s per +3k turn, where F's grows from 6.9 to 11.0 s. Prefix reuse is identical on both (prompt_n 3,028–3,040 per turn).
- **Where MTP's session gain comes from:** MTP adds ~9–10 s of prefill per session (the draft runs over every prompt token, plus one more CPU layer) and saves ~45 s of decode at depth.
- **n-max sweep, session_s (rep 1):**

| n-max | session_s | vs no-MTP | D0 t/s |
|---|---|---|---|
| 3 | 814.4 | +0.2% | 34.17 (−15%; prose acceptance 43%) |
| **2** | **792.4** | −2.5% | 37.17 |
| 1 | 839.9 | +3.3% | 39.51 |

  n-max 2 got the extra reps: 776.5 and 779.4.
- **Acceptance by content:** ~62–75% per drafted token on code, ~43–53% on technical prose.
- **Determinism:** generation is deterministic for the fixed seed. All three k=2 sessions drafted and accepted exactly 10,288 / 6,881 tokens, so the spread between reps is timing noise.
- **Losslessness:** MTP passed Task 02 with the same logic profile as every passing run. The draft is greedy and the target verifies with its own sampler, so the output distribution is the target's.

## MTP placement and ncmoe (C1)
The ~2.6 GiB head file breaks down as:
- experts 1,750 MiB;
- output.weight 497 MiB;
- token_embd 341 MiB (this one stays on the CPU).

On the GPU, the draft context also needs:
- KV for 131k cells, 1 layer (170 MiB at q8_0);
- a **1,672 MiB compute buffer**, sized by the shared `-ub 2048`. No draft-only ubatch flag exists.

| head placement | n46 load | predicted FULL peak | outcome |
|---|---|---|---|
| all on GPU | 14,482 | needs n48 → ≈ 13,490 | ✗ infeasible at 128k |
| experts on CPU (`--spec-draft-cpu-moe`), n46 | 12,732 | ≈ 13,560 | ✗ (not run) |
| experts on CPU, **n47** | 11,820 (k3) / 11,706 (k2) | ≈ 12,650 | ✓ measured 12,800 (k3) / 12,686 (k2) |

Head placement does not change acceptance. All MTP runs used draft KV q8_0 (`-ctkd/-ctvd`; the default is f16), `--spec-draft-ngl 999`, greedy draft sampling and `p-min 0`.

## Flag findings (B1, B3)
- **Env var:** M accepts `LLAMA_ATTN_ROT_DISABLE=1` and no longer *needs* it. Without it, M loads and answers sanely at the same speed (D0 40.18 vs 40.37).
  - The text differs, because attention rotation of the q8_0 KV is then active, which is a math change.
  - **The env var is kept**, so the math stays the one gates 2–4 have always been measured on.
  - Whether rotation improves q8 KV fidelity is an open KLD question for a later run.
- **`-ot per_layer_token_embd=CPU` vs `--lazy-mode on`:** no difference.
  - Load VRAM 9,996 for both, the same RSS (27.8 GiB file-backed at load) and the same MemAvailable (86.3 GiB).
  - D0 40.37 vs 40.53, and the output is byte-identical.
  - M's default `--lazy-mode auto` already covers that 28.8 GB tensor. `-ot` is kept because it keeps the apply diff to one line.
- **`--fit` (default on in M)** silently aborts if `-ngl` or any tensor override (`-ot`, `-ncmoe`) is set by the user. So with F's flags it does nothing: identical VRAM and output.
- **`--fit on --fit-target 3000`** (no `-ngl`/`-ot`/`-ncmoe`; `--lazy-mode on`):
  - load 12,138, FULL peak 12,624 (pass);
  - D0 +2.4%, D32k +2.7%, P32k +3.9%;
  - **session 799.7 vs 813.2 = −1.65%: noise, so rejected.**
  - Fit also sizes against the *free* VRAM at load time, so its layout moves with whatever the desktop holds. `-ncmoe` is deterministic.
- **`--reasoning-preserve`:** M enables it by default; F uses the template default. In the session test this made no difference to per-turn prefill.

## 256k (Phase D, report only; M, no MTP, ub 2048)
- **Load ladder:** n44 fails to load, n45 14,616, n46 13,704, n47 12,792, n48 11,880 MiB.
- **240,183-token fill:**
  - **n47:** peak 13,278 (122 MiB margin, inside allocator noise).
  - **n48:** peak **12,366** (1,034 margin).
  - Both: 3/3 needles, `stop`, prefill ~690 t/s (TTFT 5.8 min; F at ub512 in v2 took 23.8 min), decode 21.3 t/s.
- **Use n48 if you want 256k.** That puts every routed expert on the CPU. D0/D32k at n48 were not measured; expect ~2% below n46.
- **256k + MTP is impossible on this card at ub 2048:** n48 + MTP fails with OOM on a 2,510 MiB draft compute buffer.

## What failed, was skipped, or changed
| item | what happened |
|---|---|
| MTP head preflight | At 11:51 the named file did not exist. The only file had a hash name and sha256 `8087dbb3…`, not the prompt's `b646ef60…`, so Phase C was set to skip. At ~12:03 you said the prompt's hash came from a stale page and that you had renamed the file. I re-verified size 2,786,204,800 B and sha256 `8087dbb3…a90231` at the expected path, and Phase C ran (X3, X7). |
| `-ngl 999` / `-ot` (rule 8) | B3 had to drop them, because `--fit` aborts otherwise. That run only; it was rejected anyway. |
| Harness slip | B2's cold-start call reused the bench label and the resume guard skipped it. It was re-run as `v4-B2-M-n46-coldset`. No data lost. |
| Not run | F gates 3/4 today (same binary as v2, which passed). B3's gates 3/4 (rejected first). MTP n46 with head experts on CPU (predicted 13,560 ✗). D0/D32k at 256k. KLD of rotation on/off. |
| Crashes | None at runtime. The only load failures were the predicted ones: 256k n44, and MTP at 256k. |
| Extra work | Second and third session reps for M and M+MTP k=2, because −2.55% on one rep was marginal against the 3% floor. |

## Apply (written, self-tested on scratch copies, **not run**)
`apply-flashnext-v4.sh <F|M> "<tuning>" [<mtp n-max>]` is v3's script with these changes:
- it rewrites the binary line;
- it adds, replaces or removes one `--spec-type draft-mtp …` line;
- it checks that the binary runs and that the MTP head's size and sha256 match;
- it keeps all of v3's checks: backup, block located by key, YAML parses, other blocks identical, ttl/env/mandatory flags kept, exact diff, auto-restore on failure.

Scratch-copy tests: 1-, 3- and 4-line diffs applied as expected; a round trip back to F was byte-identical; refusals left the file unchanged; a forced validation failure was restored (DECISIONS X16).

**Option A — recommended: M + MTP n-max 2** (3-line diff: binary, `-ncmoe 47`, MTP line)
```
bash ~/flashnext-opt/apply-flashnext-v4.sh M "-ncmoe 47 -t 16 -b 2048 -ub 2048" 2 && systemctl --user restart llama-swap
```
**Option B — M, same flags as today, no MTP** (1-line diff: binary). Session −23% vs today, and 2.9 GB of VRAM margin.
```
bash ~/flashnext-opt/apply-flashnext-v4.sh M "-ncmoe 46 -t 16 -b 2048 -ub 2048" && systemctl --user restart llama-swap
```
**Option C — keep F:** do nothing.

**Rollback** (either option) — the script also prints the exact `cp` of its timestamped backup:
```
bash ~/flashnext-opt/apply-flashnext-v4.sh F "-ncmoe 46 -t 16 -b 2048 -ub 2048" && systemctl --user restart llama-swap
# or: cp ~/.config/llama-swap/config.yaml.bak-<stamp> ~/.config/llama-swap/config.yaml && systemctl --user restart llama-swap
```
**256k** is not covered by the script, because it doesn't touch `-c`. If you want it, use Option B's binary with `-ncmoe 48` and `-c 262144`, without MTP.

## Finish-phase verification (15:38–15:39)
- **Test servers and GPU:** no test servers left; GPU at 532 MiB (desktop only).
- **llama-swap:** started and `active`.
- **Probe via `:9292`:** `PROBE_OK`, `stop`, 34 tokens, 8 s.
- **`/running`:** the unchanged F cmd (n46/ub2048).
- **`GET /unload`:** `OK`, and `/running` is [].
- **config.yaml:** untouched (sha256 `248c2cf3…`, mtime 11:41 today, your own edit).

Raw data:
- `results-v4.jsonl`: every row carries the engine, its SHA and the flags.
- `DECISIONS-v4.md`: X1–X23.
- `logs/v4-*.server.log`: per-request MTP acceptance; parse with `accept_v4.py`.
- `runs/task02-v4-*`.
- Scripts: `harness4.py`, `run-v4-*.sh`.
