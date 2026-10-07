# Rubric: 13 criteria, 36 points

**Source:** copied verbatim from the judge prompt of 2026-04-21 (`judge-prompt.md`, "Scoring rubric").
The same 13 criteria and point weights were used for the September 2026 Task 01 and Task 02 scoring;
Task 02 re-worded each criterion for Python (see `../inputs/flashnext-eval-python-task02.md`).

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

## How it got here (all on 2026-04-21, from the same transcript)

1. **First version: 11 criteria, 30 points.** Criteria 1–11 as above, except that criterion 11 was
   worded for the implementers' copy of the spec. It also set decision thresholds on the /30 scale,
   which were not carried over to /36.
2. **Judge version.** The spec was rewritten for external judges (`task01-prompt.md`), and criteria 4,
   5 and 11 were re-worded to match. "Cite line numbers" became "quote the code", and the framing
   changed from "senior reviewer" to adversarial ("assume every output has errors").
3. **Criteria 12 and 13 added** after the author asked whether code quality was covered. Criterion 12
   was made structural (three checkable sub-questions) so judges could not score it on impression.
   Criterion 13 was flagged at the time as possibly unfair, since the spec never asked for re-entrancy
   safety, and kept on purpose.
4. **Five-output layout.** Score-only table, per-criterion justifications, forced 1–5 ranking with no
   ties, an anti-fatigue rule, and rules for multi-file outputs.

**Criterion 2 was meant to be overridden by a human `dotnet build`** (0 errors and 0 warnings = 3,
1–3 warnings = 2, 4+ warnings = 1, any error = 0). The transcript does not record that override being
applied to the judges' scores.

**Criterion 13's wording admits two readings.** Its test is "guaranteed to fire exactly once under
re-entry", but its example only names the case with no guard flag at all. A guard flag that is set too
late passes the example and fails the test. See `scores.md`.
