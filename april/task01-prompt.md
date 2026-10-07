# Task 01 prompt (HealthComponent, Godot 4.6.1 C#)

**Source:** copied verbatim from the author's chat transcript of 2026-04-21. This is the spec block
embedded in the judge prompt (`judge-prompt.md`), i.e. the exact text the three judges were told all
five implementers received.

---

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


---

## How the implementers' copy differed

The five implementers (2026-04-21) were given an earlier draft of this spec. The text above is a later
rewrite of that draft, made for the judges. The differences:

1. **Title and intro line** were worded differently.
2. The constraints section had a different heading and **one extra bullet of context**. There was no
   separate "Domain rule" section; the state requirement lived only in requirement 3.
3. **The enum had a different type name and different member names** (still three members; the middle
   one was also `Neutral`). The context field was named after that type.
4. **Requirement 3** said the context "should carry" (not "must carry") the amount, source and the
   receiver's state, and added that the component does not decide the state, only records and forwards it.
5. **Requirement 5** named one additional system in its list of forbidden direct calls.
6. Minor wording only: "Never GDScript" vs "GDScript is forbidden", "do not" vs "must not", and small
   rephrasings of the Requirements intro, requirement 1 and Deliverable items 2–3.

**Consequence (the "scrub artifact").** The judge prompt says all five implementers were given the
text above, so the judges scored criterion 5 (and in part 4 and 11) against an enum name none of the
implementers had seen. Judge 3 called this a "universal hallucination"; Judge 1 cited it for Output E.
It is a flaw in the April judge setup, not in the outputs.

**September 2026.** The flashnext Q2 Task 01 run (2026-09-08) used this judge-version wording: its enum
is `PlayerState { Stable, Neutral, Compromised }`. The exact prompt file used in September was not saved.
