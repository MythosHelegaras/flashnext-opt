# Blind Code Evaluation — Five Outputs

You are evaluating five anonymous implementations of the same coding task. The implementations were produced by different AI models. You do not know which is which and you must not attempt to identify them. Do not speculate in your output about which model produced which output. Judge the code on its merits.

This is an adversarial evaluation. Assume every output has errors until proven otherwise. Your job is not to be charitable — your job is to be accurate. Judge fatigue is a real risk across five outputs; maintain the same scrutiny on Output E as on Output A.

Some outputs may be split across multiple files. Treat multi-file outputs as a single logical submission and judge the combined code.

---

## The original specification given to all five implementers

All five were given this exact prompt:

---BEGIN ORIGINAL SPEC---

# HealthComponent Implementation

Implement a reusable `HealthComponent` for a 2D action game built in **Godot 4.6.1** using **C# (.NET 10)**.

## Architectural constraints (non-negotiable)

- **Engine:** Godot 4.6.1 mono (.NET / C#). GDScript is forbidden.
- **Architecture:** Event-bus pattern. Components must not reference each other directly. They emit events on a global autoload `EventBus` and subscribe to events they care about. Direct coupling between gameplay systems is forbidden.
- **Code style:** Strictly typed variables. Explicit access modifiers on every member. Properties, not public fields. `PascalCase` for public members, `_camelCase` for private fields. XML doc comments on public members.

## Domain rule (product requirement, not cosmetic)

The game tracks a `PlayerState` enum with three values: `Stable`, `Neutral`, `Compromised`. When an entity takes damage, the state it was in at the moment of impact must be recorded and forwarded with the damage event. Downstream systems depend on this flowing through correctly — it is a load-bearing product requirement, not flavor. The HealthComponent itself does not decide state; it records whatever is passed in and forwards it.

## Requirements

Implement `HealthComponent.cs` as a `Node`-derived component attachable to any entity (player, enemy, NPC).

It must:

1. Expose `MaxHealth` and `CurrentHealth` as exported properties, tunable per-entity in the Godot editor.
2. Provide a public method to apply damage and a public method to apply healing.
3. Take a **damage context** when damaged, not a raw integer. The context must carry at minimum: amount, source entity reference, and the `PlayerState` value describing the receiver's state at the moment of damage.
4. Emit events on the global `EventBus` (assume it exists as an autoload with `public static EventBus Instance`) when:
   - Damage is taken (include the full damage context in the event)
   - Healing is received
   - The entity reaches zero health
5. Not reference any other gameplay system directly. No `GetNode` calls to siblings. No direct calls to `Player`, `Enemy`, or any other system. Only the EventBus.
6. Be safe against negative damage, negative healing, healing past max, and damage past zero.

## Deliverable

Provide:

1. The full `HealthComponent.cs` file.
2. Supporting types: the damage context type, the `PlayerState` enum, and the event signatures on `EventBus` (just the event declarations, not the full EventBus class).
3. A brief (≤10 lines) explanation of any design decisions where the spec was ambiguous.

Do not write tests. Do not write the EventBus class itself. Do not write Godot scene files.

---END ORIGINAL SPEC---

---

## How to handle multi-file outputs

Some outputs are single code blocks. Others are split across multiple files (e.g., `HealthComponent.cs`, `DamageContext.cs`, `PlayerState.cs`, or a separate event-handler file). Treat multi-file outputs as **a single logical submission**. Score the combined code.

Splitting is **neutral by default**. It becomes a **negative signal** (penalize under Code Quality) only when gratuitous: a single-line file, splitting a coherent type across files, or creating files for types that naturally live together. It becomes a **positive signal** only if the split genuinely improves clarity AND the files are substantive.

If an output includes a short design-decisions note (≤10 lines), that is part of the deliverable — do not penalize it under scope.

---

## The five anonymous outputs

### Output A

```
<PASTE OUTPUT A HERE — all files and any explanation text. If multi-file, label each file clearly: "===== HealthComponent.cs =====" etc.>
```

### Output B

```
<PASTE OUTPUT B HERE — same labeling convention>
```

### Output C

```
<PASTE OUTPUT C HERE — this output consists of multiple files. Label each clearly.>
```

### Output D

```
<PASTE OUTPUT D HERE — same labeling convention>
```

### Output E

```
<PASTE OUTPUT E HERE — same labeling convention>
```

---

## Evaluation instructions

Score each output against every criterion. For each score:

1. Assign a value within the stated range.
2. **Quote the specific code snippet** that justifies the score. One snippet, one sentence of reasoning. No essays.
3. If you cannot quote supporting code, you cannot assign credit. "No relevant code" is itself a justification for a zero.

### Hard rules you must follow

- **No pattern-matching.** If a criterion says "XML doc comments on ALL public members," check every public member individually. Presence of *some* comments is not sufficient.
- **No rewarding verbosity.** Longer ≠ better. Over-engineering is penalized under quality and scope.
- **No assuming correctness from plausibility.** If a Godot 4.6 API call looks plausible but you cannot verify it, mark it "uncertain" in your justification and withhold full credit. Do not guess upward.
- **No assuming correctness from structure.** Multi-file organization is not quality. Single-file organization is not a failure. Judge the code itself.
- **Forced rank order.** The final ranking must place all five outputs at ranks 1 through 5 with no ties. If two outputs score identically on total, you must find at least one criterion where they differ and break the tie there.
- **Anti-fatigue rule.** Output E gets the same scrutiny as Output A. If your justifications for E are shorter or thinner than for A without the code being objectively simpler, you are fatigued and must re-read E.
- **No preamble.** Produce the scoring table first. Nothing else before it.
- **Do not speculate about which model produced which output.** Any such speculation in your response is a protocol violation.

### Scoring rubric

| # | Criterion | Range |
|---|---|---|
| 1 | Godot 4.6 C# syntax correct (`[Export]` on properties, proper `Node` lifecycle, event/signal patterns) | 0-3 |
| 2 | Code compiles without modification (no missing usings, no typos, no wrong namespaces, no undefined symbols) | 0-3 |
| 3 | Event-bus pattern respected — no direct sibling references, no `GetNode` to other systems | 0-3 |
| 4 | Damage context is a proper type carrying all three required fields (amount, source, PlayerState) | 0-3 |
| 5 | `PlayerState` enum defined with exactly three values: `Stable`, `Neutral`, `Compromised` | 0-2 |
| 6 | Events emitted on all three required occasions, with full context where required | 0-3 |
| 7 | Defensive against negative damage, negative healing, healing past max, damage past zero | 0-3 |
| 8 | Code style: properties not fields, explicit access modifiers, naming conventions (PascalCase public / _camelCase private) | 0-3 |
| 9 | XML doc comments on every public member (check each one) | 0-2 |
| 10 | Scope discipline: no tests written, no full EventBus class written, no unprompted features (regen, shields, armor, status effects, etc.) | 0-2 |
| 11 | Domain rule honored: `PlayerState` actually flows end-to-end from the damage call through the emitted event, not dropped or substituted mid-pipeline | 0-3 |
| 12 | **Code quality** — THREE structural checks, ALL must pass for full credit: (a) no dead code (unused methods, unread parameters, unwritten fields); (b) no unnecessary abstraction (interfaces with one implementation, unused generic parameters, wrapper classes that only forward calls, gratuitous file splitting); (c) names are meaningful and consistent (no single-letter variables outside trivial loops, no misleading names, no abbreviation inconsistency). Deduct 1 per failed check. | 0-3 |
| 13 | **Concurrency safety** — if damage or healing can be called from multiple signal handlers or sources within the same frame, is the zero-health event guaranteed to fire exactly once? A naive `if (CurrentHealth <= 0) emit` without a `_isDead` flag or equivalent guard will fire the death event multiple times under re-entry and fails. | 0-3 |
|   | **Total** | / 36 |

---

## Required output format

Produce exactly this structure. No other text before or after.

```
## Scoring Table

| # | Criterion | A | B | C | D | E |
|---|---|---|---|---|---|---|
| 1 | Godot 4.6 syntax | x | x | x | x | x |
| 2 | Compiles | x | x | x | x | x |
| 3 | Event-bus pattern | x | x | x | x | x |
| 4 | Damage context type | x | x | x | x | x |
| 5 | PlayerState enum | x | x | x | x | x |
| 6 | Events emitted | x | x | x | x | x |
| 7 | Defensive checks | x | x | x | x | x |
| 8 | Code style | x | x | x | x | x |
| 9 | XML doc comments | x | x | x | x | x |
| 10 | Scope discipline | x | x | x | x | x |
| 11 | Domain rule honored | x | x | x | x | x |
| 12 | Code quality | x | x | x | x | x |
| 13 | Concurrency safety | x | x | x | x | x |
|   | **Total** | x/36 | x/36 | x/36 | x/36 | x/36 |

## Justifications

For each criterion, provide one-line justifications per output. Quote code.

### Criterion 1 — Godot 4.6 syntax
- A: [score] — "quoted snippet" — one sentence of reasoning
- B: [score] — "quoted snippet" — one sentence of reasoning
- C: [score] — "quoted snippet" — one sentence of reasoning
- D: [score] — "quoted snippet" — one sentence of reasoning
- E: [score] — "quoted snippet" — one sentence of reasoning

### Criterion 2 — Compiles
[same format, all 5 outputs]

### Criterion 3 — Event-bus pattern
[same format]

### Criterion 4 — Damage context type
[same format]

### Criterion 5 — PlayerState enum
[same format]

### Criterion 6 — Events emitted
[same format]

### Criterion 7 — Defensive checks
[same format]

### Criterion 8 — Code style
[same format]

### Criterion 9 — XML doc comments
[same format]

### Criterion 10 — Scope discipline
[same format]

### Criterion 11 — Domain rule honored
[same format]

### Criterion 12 — Code quality
For this criterion, list which of (a), (b), (c) failed per output:
- A: [score] — failed: [list a/b/c or "none"] — "quoted snippet showing the failure"
- B: [score] — failed: [list or "none"] — "quoted snippet"
- C: [score] — failed: [list or "none"] — "quoted snippet"
- D: [score] — failed: [list or "none"] — "quoted snippet"
- E: [score] — failed: [list or "none"] — "quoted snippet"

### Criterion 13 — Concurrency safety
Quote the guard (or lack thereof) per output:
- A: [score] — "quoted guard or note that none exists"
- B: [score] — "..."
- C: [score] — "..."
- D: [score] — "..."
- E: [score] — "..."

## Disqualifying Issues (per output)

**Output A:**
- [list any, or "none"]

**Output B:**
- [list any, or "none"]

**Output C:**
- [list any, or "none"]

**Output D:**
- [list any, or "none"]

**Output E:**
- [list any, or "none"]

Examples of disqualifying issues: invented Godot API calls, GDScript present anywhere, public fields instead of properties, direct references to other systems, PlayerState dropped from the pipeline, more than ~250 lines total, zero-health event firing multiple times or not at all under normal use.

## Forced Ranking (1 = best, 5 = worst, no ties)

1. Output [X] — [one sentence explaining the win]
2. Output [Y] — [one sentence explaining second, citing the gap to first]
3. Output [Z] — [one sentence explaining third, citing the gap to second]
4. Output [W] — [one sentence explaining fourth, citing the gap to third]
5. Output [V] — [one sentence explaining last, citing the gap to fourth]

If any ranks have identical totals, explain in one sentence which criterion you used to break the tie and why.

## Confidence

State confidence in this ranking: HIGH / MEDIUM / LOW.

If MEDIUM or LOW, identify the single biggest uncertainty whose resolution would most likely reorder the ranking.
```

Begin.
