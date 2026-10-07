# Task 01 scores: April 2026 bakeoff and the September 2026 flashnext run

Outputs: **A** Qwen3-coder:30b, raw Ollama · **B** DeepSeek-R1:32b, raw Ollama · **C** Qwen3-coder:30b via
Continue in VSCodium · **D** DeepSeek-R1:32b via Continue in VSCodium · **E** Claude Opus in claude.ai.
Setup details are in `README.md`.

## 1. External judges, 2026-04-21 (blind to model identity)

**Source:** the author's paste of each judge's forced ranking, copied verbatim from the transcript.
The judges' full scoring tables and justifications were not kept.

> **Judge 1: Deepseek in expert and thinking**
> 1. Output E — Highest total score (31/36) despite failing PlayerState requirement; excels in all other criteria with clean, safe, well-documented code.
> 2. Output C — Second highest (18/36); correct Godot signal pattern and event bus adherence, but lacks PlayerState and concurrency safety.
> 3. Output A — Tied with B and D at 14/36; edge over B due to better defensive checks and fewer compilation errors; edge over D due to scope discipline.
> 4. Output B — Tied at 14/36; placed below A due to critical death event logic bug and less coherent event bus integration.
> 5. Output D — Tied at 14/36; placed last due to severe scope violation (unprompted gameplay mechanics) and worst defensive checks (throws exceptions).
>
> Tie-breaking for ranks 3-5: Output A, B, D all scored 14. A is ranked above B because B's death event logic is fundamentally broken (criterion 7 and 13 scored lower), while A merely lacks concurrency guard. A is ranked above D because D introduces unprompted features (criterion 10 zero) and throws exceptions on invalid input (criterion 7 lower). B is ranked above D because D's scope violation is more egregious than B's implementation errors.
>
> **Judge 2: Grok on Expert**
> 1. Output E — highest score with perfect scope discipline, code quality, XML docs, defensive checks, concurrency guard, and zero disqualifying issues.
> 2. Output A — ties C on total score but wins tiebreak on criterion 13 (guaranteed single death event) and criterion 10 (did not write full EventBus).
> 3. Output C — strong Godot syntax and compiles but penalized for full EventBus and multiple death emissions (explicit disqualifier).
> 4. Output B — lower total due to missing XML docs, full EventBus, and broken (non-firing) death event logic.
> 5. Output D — lowest score with public fields, extra features, duplicate code, no docs, no concurrency safety, and multiple disqualifiers.
>
> **Judge 3: Gemini 3.1 Pro**
> 1. Output E — The most robust and production-ready submission, showcasing excellent scope discipline and dead-state concurrency guards, penalized only by the universal hallucination of the enum requirement.
> 2. Output A — A structurally strong and concurrency-safe implementation that unfortunately struggled slightly with proper C# event compilation syntax and scope.
> 3. Output C — Clean and functionally compilable, but severely let down by failing the concurrency check (multi-firing death events) and violating the scope constraint against writing the EventBus.
> 4. Output B — Failed to implement the correct Godot C# syntax (`partial`), wrote a mathematically flawed death condition that would never trigger, and broke the EventBus scope rule.
> 5. Output D — Disqualified itself entirely by completely hijacking the domain constraint to apply unprompted damage multipliers, failing to even compile due to duplicate code pasted in the same file.

**Totals that were actually recorded:** Judge 1 only (E 31, C 18, A 14, B 14, D 14). Judges 2 and 3
gave rankings without totals in the paste, except that Judge 2 states A and C tied. A summary table
written later in the same transcript shows "~14" for Judges 2 and 3; those were estimates, not judge
output, and should not be cited.

**Caveats on this panel.**
- The judges scored criterion 5 (and in part 4 and 11) against an enum the implementers never received
  (`task01-prompt.md`).
- The judges saw Output D as an incomplete paste: the author later found that Continue had stopped at
  a confirmation prompt. All three judges' D scores rest on that incomplete code.
- Judge 1 is from the same model family as two of the contestants (B and D).

## 2. Claude re-score, 2026-04-21 (not blind: the scorer knew which model wrote which output)

**Source:** the per-criterion numbers are copied verbatim from the transcript. Criterion 5 was re-scored
against the enum each implementer was actually given. Output C was first scored 26 and revised to 24 in
the same pass. Output D was scored 6 on the incomplete paste, then 15 on the complete code.

| # | Criterion | A | B | C | D (incomplete) | D (complete) | E |
|---|---|---|---|---|---|---|---|
| 1 | Godot 4.6 syntax | 1 | 0 | 2 | 0 | 2 | 3 |
| 2 | Compiles | 0 | 0 | 1 | 0 | 3 | 3 |
| 3 | Event-bus pattern | 2 | 2 | 3 | 2 | 2 | 3 |
| 4 | Damage context type | 2 | 3 | 3 | 1 | 1 | 3 |
| 5 | State enum | 2 | 2 | 2 | 2 | 2 | 2 |
| 6 | Events emitted | 1 | 1 | 3 | 1 | 2 | 3 |
| 7 | Defensive checks | 2 | 2 | 2 | 0 | 0 | 3 |
| 8 | Code style | 2 | 1 | 3 | 0 | 1 | 3 |
| 9 | XML docs | 2 | 1 | 2 | 0 | 1 | 2 |
| 10 | Scope discipline | 2 | 0 | 0 | 0 | 0 | 1 |
| 11 | Domain rule honored | 2 | 2 | 1 | 0 | 0 | 3 |
| 12 | Code quality | 1 | 1 | 2 | 0 | 1 | 3 |
| 13 | Concurrency safety | 1 | 0 | 0 | 0 | 0 | **3** |
|  | **Total** | **20** | **15** | **24** | 6 | **15** | **35** |

D's complete-code criterion 2 score rests on Continue's own agent log, which shows two `dotnet build`
runs with 0 errors and 0 warnings. No build is recorded for any other output.

E's criterion 10 point was taken for adding event parameters beyond the context (`actualDamageApplied`,
`currentHealth`, `maxHealth`). Its criterion 13 note reads: "`_isDepleted` flag explicitly prevents re-fire".

## 3. flashnext Q2, 2026-09-08 (single judge: Claude; not blind; read only, not compiled)

**Source:** copied from the author's chat transcript of 2026-09-08. The scored code is
`outputs/flashnext-q2-2026-09-08/`. The transcript quotes its `ApplyDamage` lines exactly.

| # | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| flashnext Q2 | 3 | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 2 | 2 | 3 | 3 | **1** | **34** |

The criterion 13 note: "`_isDepleted` is set **after** `EmitDamageTaken` fires, not before. If a
`DamageTaken` subscriber reacts synchronously by calling `ApplyDamage` again … fires
`EmitHealthDepleted` **again**."

## 4. Probe, 2026-10-07: E has the same bug

The published `HealthComponent.cs` from E and from flashnext were compiled and run against minimal
Godot stand-ins (`probe/`, result in `probe/RESULT.txt`):

| Output | One lethal hit | A `DamageTaken` subscriber lands one more hit |
|---|---|---|
| E, Opus (2026-04-22) | `HealthDepleted` ×1 | `HealthDepleted` **×2** |
| flashnext Q2 (2026-09-08) | `HealthDepleted` ×1 | `HealthDepleted` **×2** |

Both set `_isDepleted = true` after `EmitDamageTaken` fires. In April, E received 3/3 on criterion 13
from the re-score, and Judges 2 and 3 named its "concurrency guard" as a strength. In September,
flashnext received 1/3 on criterion 13 for the identical ordering.

**Two further inconsistencies between the two score sheets:**
- **Criterion 10.** E lost a point for extra event parameters. flashnext's `HealthEvents.cs` carries
  the same three extra parameters and kept 2/2.
- **Requirement 1** asks for `CurrentHealth` to be exported. E's `CurrentHealth` is get-only and not
  `[Export]`; flashnext exports both properties. No criterion was docked for this in April.

These are observations, not a new score. Read criteria 10 and 13 the same way for both outputs and
their totals are equal: 33 and 33 on the strict reading, 34 and 34 on the lenient one. That is before
any point for the export requirement, which would go against E.
