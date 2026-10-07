# april/: Task 01 and the April 2026 bakeoff

The first evaluation behind this repo: a blind five-way comparison (2026-04-21/22) of local models
against Claude Opus on one Godot 4.6.1 C# task, `HealthComponent`. It is scored on the same 13-criterion,
36-point rubric that the September 2026 Task 01 and Task 02 runs reuse.

## Where each file comes from

Nothing in this folder was written from memory. Each file is one of three kinds:

- **Transcript:** copied from the author's chat transcripts of 2026-04-21/22 and 2026-09-08.
- **Original file:** an output file kept on the author's disk.
- **Written 2026-10-07:** new material, labelled as such.

| File | Contents | Provenance |
|---|---|---|
| `task01-prompt.md` | The Task 01 spec as the judges received it, plus how the implementers' copy differed | Spec: transcript, verbatim. Difference note: written 2026-10-07 from the transcript |
| `rubric.md` | The 13-criterion, 36-point rubric and how it evolved that day | Table: transcript, verbatim. History: written 2026-10-07 from the transcript |
| `judge-prompt.md` | The complete prompt sent to the three judges | Transcript, verbatim |
| `scores.md` | Judges' rankings, Claude's April re-score, the September flashnext score, and the probe result | Rankings and scores: transcript, verbatim. Probe result and notes: written 2026-10-07 |
| `outputs/E-opus-2026-04-22/` | Output E (Opus): `HealthComponent.cs`, `HealthEvents.cs` | Original files dated 2026-04-22. The `namespace` and `using` lines were normalized to `ReferenceProject`; nothing else was changed. `SHA256SUMS.original` lists the hashes of the files before that change. E's `DamageContext` and enum files are not published; the probe uses a stand-in. |
| `outputs/flashnext-q2-2026-09-08/` | flashnext Q2's Task 01 output | Original files dated 2026-09-08, unmodified (`SHA256SUMS`) |
| `probe/` | Re-entrancy probe for both outputs | Written 2026-10-07 |

**Not preserved:** outputs A–D (only fragments quoted in the transcript survive), the judges' full
scoring tables and justifications, and the Continue agent logs.

## Setup (2026-04-21)

| Output | Model | How it was run |
|---|---|---|
| A | qwen3-coder:30b (Ollama, 18 GB) | Plain `ollama run` with the prompt; no system prompt, no context |
| B | deepseek-r1:32b (Ollama, 19 GB) | Plain `ollama run` with the prompt; no system prompt, no context |
| C | qwen3-coder:30b | Continue in VSCodium, chat panel |
| D | deepseek-r1:32b | Continue in VSCodium, chat panel |
| E | Claude Opus | claude.ai, in a workspace with reference documents the local models did not have |

- **Hardware.** The local models ran on a 16 GB RTX 5070 Ti, so both spilled into system RAM.
- **The setup change.** The first design ran the local models only through plain `ollama run`, with no
  context. The author objected that this was not how he would use them, so each model was also run in
  its real deployment: Continue + VSCodium for the local models. A and B are the plain runs; C and D are
  the Continue runs.
- **Continue configuration.** Both models were given the same one-line system prompt: senior C#
  developer, Godot 4.6.1, follow the spec exactly, no scope creep. Neither got role-specific framing.
  DeepSeek-R1 rejected Continue's tool payloads ("does not support tools"), so its entry was set to
  `capabilities: []`. Output D's own agent log nonetheless shows it writing files and running
  `dotnet build`. How that configuration relates to the run is not recorded.
- **E was not run through Claude Code.** No `CLAUDE.md` existed at the time; one was written after the
  bakeoff. E's context advantage was known and deliberately not disclosed to the judges.
- **Judges.** Judge 1 was DeepSeek (expert + thinking mode), Judge 2 Grok (Expert), Judge 3 Gemini 3.1
  Pro, all run online. The author chose them and kept their identities from Claude while the judge
  prompt was being written, then disclosed them with the results. Output E was in no judge's family.
  Judge 1 shares a family with B and D.
- **Not recorded:**
  - whether the recommended per-judge rotation of output letters was applied;
  - how many runs per model were made (the protocol suggested three, keeping one);
  - whether the human `dotnet build` override for criterion 2 was applied.
- **Model version for E.** The output file does not record it. The April conversation refers to its own
  model as Claude Opus 4.7. The September Task 02 write-up labels this run "Opus 4.8".

## What the record supports, and what it doesn't

- **Supported:** all three judges ranked E first, and Judge 1 scored it 31/36 against at most 18 for the
  local outputs. Claude's non-blind re-score had E at 35 and the local outputs at 15–24. The April
  decision (Opus writes production code) rests on that gap, and the gap survives every correction below.
- **"Locals scored 14–24"** mixes two sources. The judges' recorded totals are 14–18 (Judge 1 only); the
  re-score is 15–24.
- **Not supported: "Opus 35/36 vs flashnext 34/36, and the point is re-entrancy."** E and flashnext's
  `HealthComponent` set `_isDepleted` after firing `DamageTaken`, and both fire `HealthDepleted` twice
  under a re-entrant hit (`probe/RESULT.txt`). E was scored 3/3 on criterion 13 in April; flashnext got
  1/3 in September for the same ordering. On a consistent reading of criteria 10 and 13 their totals are
  equal (`scores.md`, section 4).
- **The method lesson.** Three external judges, a careful non-blind re-score in April and a second one
  in September all read E's guard as correct. A probe a few lines long showed in under a second that it
  was not. That is the same finding Task 02 later made on its own (`../inputs/flashnext-eval-python-task02.md`,
  "review does not catch this bug class").

## Run the probe

Needs the .NET 8 SDK:

```bash
dotnet run --project april/probe/E          # Output E (Opus, 2026-04-22)
dotnet run --project april/probe/flashnext  # flashnext Q2 (2026-09-08)
```

Each project compiles the published output files as they are, plus minimal stand-ins for the Godot
types they use (`GodotStubs.cs`). No Godot install is needed.
