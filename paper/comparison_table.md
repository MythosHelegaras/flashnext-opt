# Comparison tables (verified numbers only)

> **Do not mix Run 1 speed numbers into later-run comparisons** — Run 2+ use a patched/rebuilt binary (and Run 4 adds a new driver + mainline engine). Within-run deltas are fair; cross-run absolute t/s are annotated.

## A. Config evolution (what was live / recommended)

| Stage | Engine | Quant | ncmoe | ub | temp | Status |
|---|---|---|---|---|---|---|
| Pre-Run 1 shipped | F fork | Q2 | 42 | 512 | 0.3 | Live |
| Run 1 end | F | Q2 | 42 | 512 | 0.3 | **NO CHANGE** (ub crash) |
| Run 2 recommend | F patched | Q2 | 46 | 2048 | 0.3 | Recommended, not applied that night |
| Run 3 recommend | F patched | Q2 | 46 | 2048 | **0.3** (not 1.0) | Confirmed sampling |
| Run 4 start | F | Q2 | 46 | 2048 | 0.3 | Zef had applied Run 2 Option A |
| Run 4 recommend A | **M mainline** | Q2 | **47** | 2048 | 0.3 | **+ MTP n-max 2** |
| Run 4 recommend B | M | Q2 | 46 | 2048 | 0.3 | No MTP |
| Runs 5–6 | — | — | — | — | — | **PENDING** |

## B. Run 1 — ubatch ladder (F, Q2, unpatched for crash)

| Config | T_turn s | FULL peak MiB | FULL / ship? |
|---|---|---|---|
| n42 ub512 (base) | 168.95 | 13020 | PASS / live |
| n42 ub1024 | 130.33 (−22.9%) | 13982 | FAIL gate |
| n43 ub2048 | 107.01 (−36.7%) | OOM @92k | FAIL |
| n44 ub4096 | 96.52 (−42.9%) | OOM @61k | FAIL |
| **n46 ub2048** | **110.55 (−34.6%)** | **12484** | numeric PASS / **sanity FAIL (crash)** |

## C. Run 2 — Q2 vs IQ3 (patched F, 128k)

| metric | Q2 n46/ub2048 | IQ3 n46/ub2048 | Q2 n42/ub512 |
|---|---|---|---|
| T_turn s | 108.2 | 108.4 | 163.6 |
| session_s | **1046.1** | 1077.2 (1.030×) | 1146.7 |
| FULL peak MiB | 12486 | 12978 | 13020 |
| D0 t/s | 36.42 | 34.83 (−4.4%) | 37.90 |
| cold | 11/11 | 11/11 | — |
| Task 02 | **2/2** | **1/2** | — |

## D. Run 3 — Task 02 sampling (n46/ub2048 both quants)

| cell | gate4 | voids | notes |
|---|---|---|---|
| Q2 temp 0.3 | **3/3** | 0/3 | recommended |
| Q2 temp 1.0 | 2/3 | 0/3 | first Q2 NOTIFIER slip |
| IQ3 temp 0.3 | 2/3 | 3/6 attempts | overthink voids |
| IQ3 temp 1.0 | 1/3 | 1/4 | |

Pooled pass: 5/6 @0.3 vs 3/6 @1.0 (n.s.).

## E. Run 4 — Engine + MTP (Q2, 128k)

| metric | F n46 | M n46 | M+MTP k=2 n47 |
|---|---|---|---|
| P32k t/s | 554.1 | **728.6** | 677.1 |
| D0 t/s | 35.77 | **40.13** | 37.17 |
| FULL pref/dec | 357 / 19.22 | **723.5 / 28.13** | 671.8 / 35.53 |
| FULL peak MiB | 12486 | **10482** | 12686 |
| session_s | 1056.4 | **814.9 ±1.9** | **782.8 ±8.5** |
| cold / Task02 | prior OK | 11/11 / PASS | 11/11 / PASS |

MTP n-max (session rep1): k3 814.4 · **k2 792.4** · k1 839.9.

## F. 256k snapshots

| Run | Engine | ub | ncmoe | FULL peak | Notes |
|---|---|---|---|---|---|
| 1 | F | 2048 | 46 | OOM before 90% | Not shippable |
| 2 | F | 512 | 45 | 13348 (52 margin) | Prefer n46; slow prefill 168 t/s |
| 4 | M | 2048 | 47 | 13278 (122 margin) | Prefer **n48** 12366 |
| 4 | M | 2048 | 48 | **12366** | Prefer; MTP incompatible |

## G. Key deltas

| Claim | Numbers | First proven in |
|---|---|---|
| Raised ubatch wins ~35% T_turn but crashed | −34.6% → blocked | Run 1 |
| Patch unlocks the win | 11/11 cold @ ub2048 | Run 2 |
| Real-use session gain smaller than T_turn | −8.8% session vs −34% T_turn | Run 2 |
| Q2 > IQ3 on reliability | Task02 2/2 vs 1/2; later voids | Run 2–3 |
| Temp 1.0 no free lunch | 3/6 vs 5/6 gate4 | Run 3 |
| Mainline beats fork hard | −23% session, −2 GB peak VRAM | Run 4 |
| MTP adds modest extra | −3.9% session (3 reps) | Run 4 |
