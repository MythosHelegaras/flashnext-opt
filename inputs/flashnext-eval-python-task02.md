# Local LLM Eval — Python Task 02 (Circuit Breaker)

**Status: COMPLETE. 2026-09-08.** Results in §Results.

**Purpose:** Test whether the re-entrancy/ordering blind spot observed in Task 01
(HealthComponent, C#) is systematic, and whether prompt tuning eliminates it.

**Comparable to:** April 2026 bakeoff + 2026-09-08 flashnext deployment. Same 13
criteria, same 36 points, same weighting.

**Why a circuit breaker:** idiomatic Python, no framework, trivially testable, and a
natural mutate-then-notify sequence — the same structural trap as Task 01 on a different
surface (state-machine transition rather than a boolean guard). A model that only
memorised "set the depleted flag first" will not transfer; one that understands the
invariant will.

---

## RESULTS

| Run | Prompt | Context | Total | Crit 13 | Crit 7 |
|-----|--------|---------|-------|---------|--------|
| Task 01 (C#) — flashnext Q2 | untuned | clean | 34/36 | 1/3 | — |
| Task 01 (C#) — **Opus 4.8** | untuned | clean | **35/36** | **3/3** | — |
| Task 02 A — flashnext Q2 | untuned | clean | 33/36 | **1/3** | 2/3 |
| Task 02 B — flashnext Q2 | **tuned** | contaminated | 35/36 | **3/3** | 2/3 |
| Task 02 B — flashnext Q2 | **tuned** | **clean room** | **35/36** | **3/3** | 2/3 |

**Verdict: the invariant clause closes the gap. Q3 is permanently off the table** —
zero quantization signatures across four runs (no invented APIs, no broken signatures,
no malformed syntax; 33/33 on all mechanical criteria). The failure was reasoning. A
paragraph fixed it; 95GB would not have.

**Caveat that must travel with these numbers:** two tasks, one judge, 1-point spreads
on a 36-point rubric. That is "indistinguishable at this sample size," not parity. The
comparison is against **Opus 4.8**, not Opus 5 / Fable 5.1.

### Finding 1 — the clause GENERALIZES (the important one)

The invariant clause names no specific method. In the **clean-room** run the model
applied it to **`record_success` as well as `record_failure`** — a second method nobody
pointed at, carrying a second instance of the same bug class (reset-after-notify
swallows a failure recorded by a subscriber).

Probe 2 exists because flashnext itself found that bug in its own Prompt A output while
the human/Opus review had scored that method 3/3. It is the **discriminating probe**:
passing it means a principle was applied, not an instruction followed.

### Finding 2 — repairs are NARROW (criterion 7 is the standing control)

Criterion 7 (threshold ≤ 0 unvalidated) failed in **all four runs** — tuned and untuned,
clean and contaminated. No prompt ever mentioned it, so nothing ever fixed it.

A second control fell out by accident. The **contaminated** B run explicitly assigned
`BreakerState.CLOSED.__doc__ = "..."` with a comment noting that CPython discards bare
string literals under enum members. The **clean-room** B run did not — it used the
bare-literal form, so all three members inherit the class docstring. The contaminated
run only fixed it because it had read Prompt A and seen the problem.

**Operating rule:** flashnext fixes what it is pointed at and generalizes *within that
principle*, but does not fix adjacent problems it was never shown. Every invariant you
care about must be named. It will not discover your requirements.

### Finding 3 — review does not catch this bug class, including expert review

Claude Opus scored Prompt A line by line while explicitly hunting re-entrancy bugs and
gave `record_success` 3/3 on criterion 6 — missing a second instance of the exact bug it
was auditing for. It also passed A's enum docstrings at 2/2 without noticing they were
dead text. flashnext found the first of those unprompted.

**The 15-line probe harness caught in one second what careful reading missed twice.**
Mechanical verification is not optional for this bug class. Draft-then-polish is only
safe when the polish step is a probe, not a read.

---

## Run procedure

Run **A first, then B**, in **separate clean directories with fresh sessions**.

> **Contamination warning, learned the hard way.** OpenCode gives the model the working
> directory. If Prompt A's output is present, the B run has both the rule *and* a
> concrete diagnosed instance — which tests code review, not code generation. Run B in
> an empty directory or the result is uninterpretable.

```fish
# Sampling: temp 0.3 for code eval, NOT the 1.0 in the shipped config.
# 1.0 is Qwen's thinking-mode default and is high variance — an ordering slip
# is exactly what sampling noise produces. Measure at low temp; ship what you like.
env LLAMA_ATTN_ROT_DISABLE=1 /opt/llama.cpp-qwen4exp/bin/llama-server --port 9999 \
  -m /mnt/ai/llm/models/qwen3.8-flash-next/UD-Q2_K_XL/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf \
  -ngl 999 -fa on -np 1 --jinja \
  -ot per_layer_token_embd=CPU \
  -ncmoe 40 -t 16 \
  -c 65536 --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.3 --top-p 0.95 --top-k 20
```

---

## PROMPT A — untuned (baseline, matches Task 01 conditions)

Paste verbatim. Do not add hints.

```
You are writing a small, reusable Python module for a production service.

Target: Python 3.14. Standard library only. No third-party packages, no async.

Write four files:

1. breaker_state.py
   An enum `BreakerState` with exactly three members: CLOSED, OPEN, HALF_OPEN.
   This value is authored by the caller's policy layer, never decided inside the
   breaker's failure path. Document each member.

2. call_context.py
   An immutable type `CallContext` describing a single downstream call attempt.
   It carries exactly three fields:
     - duration_ms: int — how long the call took
     - endpoint: str | None — the target, or None for anonymous calls
     - caller_state: BreakerState — the caller's view of breaker state at the
       moment the call was issued
   `caller_state` is a load-bearing product requirement: it must reach every
   subscriber unchanged. The breaker must not filter, remap or reinterpret it.

3. breaker_events.py
   The subscriber contract. Define the callback signatures the notifier must
   support, and document them. Do NOT implement the notifier itself — assume a
   module-level `NOTIFIER` object exists exposing:
       NOTIFIER.emit_call_failed(breaker_name, context, failure_count, threshold)
       NOTIFIER.emit_call_succeeded(breaker_name, context, current_state)
       NOTIFIER.emit_breaker_opened(breaker_name, context)
   Describe the exact guarantees each carries.

4. circuit_breaker.py
   class CircuitBreaker. Constructor takes `name: str` and
   `failure_threshold: int` (default 5).

   Public methods:
     record_failure(context: CallContext) -> None
     record_success(context: CallContext) -> None
     reset() -> None

   Behaviour:
     - record_failure increments an internal failure count and emits
       call_failed with the full context.
     - When the count reaches failure_threshold, the breaker transitions to
       OPEN and emits breaker_opened.
     - breaker_opened must fire exactly once per transition to OPEN. It must
       never fire again while the breaker is already open.
     - record_failure on an already-open breaker is ignored entirely.
     - record_success emits call_succeeded and, if the breaker is not open,
       resets the failure count to zero.
     - reset() returns the breaker to CLOSED with a zero count and emits
       nothing.
     - Invalid input (negative duration_ms) is dropped with a warning via the
       `warnings` module, not an exception.

   The breaker holds NO references to any other system. NOTIFIER is its sole
   point of contact.

Constraints:
  - Full type hints on every signature.
  - Docstrings on every public class, method and enum member.
  - Do not write tests.
  - Do not implement NOTIFIER.
  - Do not add features that were not requested.
```

---

## PROMPT B — tuned (adds the invariant clause only)

Identical to A, with this appended before "Constraints":

```
  Invariant discipline:
    When a method both mutates internal state and notifies subscribers, mutate
    first. Assume any subscriber may synchronously call back into the same
    method that notified it — a retry handler responding to a failure by
    issuing another call is normal. Any guard you write must already be in its
    post-mutation state before the first notification fires.
```

**This clause is now permanent** — see `~/.config/opencode/AGENTS.md`.

---

## Scoring rubric — 13 criteria / 36 points

| # | Criterion | Pts | What earns full marks |
|---|-----------|-----|----------------------|
| 1 | Python 3.14 syntax | 3 | Valid modern syntax. `str \| None` not `Optional[str]`. `enum.Enum` used correctly. No invented stdlib APIs. |
| 2 | Runs clean | 3 | `python -m py_compile` passes on all four files. Every `NOTIFIER.emit_*` call matches the prompt's signature argument-for-argument. |
| 3 | Notifier pattern | 3 | Zero references to any system other than NOTIFIER and stdlib. No global state beyond the breaker's own. |
| 4 | Context type | 3 | Immutable — `@dataclass(frozen=True)` or `NamedTuple`. All three fields, correct types, `endpoint` genuinely optional. |
| 5 | Enum | 2 | Exactly CLOSED, OPEN, HALF_OPEN. No extra members, no renaming. |
| 6 | Events emitted | 3 | All three occasions, full context forwarded, correct arguments. |
| 7 | Defensive checks | 3 | Negative `duration_ms` warned-and-dropped via `warnings`. **Threshold ≤ 0 handled — the standing control; no run has ever passed this.** Already-open path handled. |
| 8 | Code style | 3 | PEP 8. Private attrs `_`-prefixed. Type hints on every signature including `-> None`. |
| 9 | Docstrings | 2 | Every public class, method, and enum member. Args documented. |
| 10 | Scope discipline | 2 | No tests. No NOTIFIER implementation. No unrequested methods, config, or extra event params. |
| 11 | Domain rule | 3 | `caller_state` forwarded verbatim, never inspected for a decision, never remapped. Immutability structural. |
| 12 | Code quality | 3 | Three sub-checks, all must pass: no dead code / no gratuitous abstraction / no naming problems. |
| 13 | **Re-entrancy safety** | 3 | **All emit paths.** State committed before the first notification; guards evaluated post-mutation. Probes 1–3. |

**Total: 36**

---

## The probe harness — DO NOT EYEBALL CRITERION 13

Drop `probe.py` beside the generated files and run it. This caught two bugs that careful
line-by-line review missed.

```python
import breaker_events, circuit_breaker as cb
from call_context import CallContext
from breaker_state import BreakerState
ctx = CallContext(10, "/x", BreakerState.CLOSED)

# ---- PROBE 1: crit 13, re-entry from emit_call_failed ----
opened, failed = [], []
class N1:
    def emit_call_failed(s, name, c, fc, th):
        failed.append(fc)
        if fc < th: b.record_failure(ctx)
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s, name, c): opened.append(name)
breaker_events.NOTIFIER = N1()
b = cb.CircuitBreaker("t", failure_threshold=3)
b.record_failure(ctx)
print("PROBE 1 (crit 13): counts", failed, "| breaker_opened fired", len(opened), "->",
      "PASS" if len(opened)==1 else "FAIL")

# ---- PROBE 2: re-entry from emit_call_succeeded  <-- THE DISCRIMINATING PROBE ----
# Named in no prompt. Passing means the model generalized the principle.
class N2:
    def emit_call_failed(s,*a): pass
    def emit_breaker_opened(s,*a): pass
    def emit_call_succeeded(s, name, c, st): b.record_failure(ctx)
breaker_events.NOTIFIER = N2()
b = cb.CircuitBreaker("t", failure_threshold=5)
b.record_failure(ctx); b.record_failure(ctx)
before = b._failure_count
b.record_success(ctx)
print(f"PROBE 2 (success re-entry): count {before} -> {b._failure_count} ->",
      "PASS (nested failure survived)" if b._failure_count==1 else "FAIL (swallowed)")

# ---- PROBE 3: re-entry from emit_breaker_opened (non-discriminating; A passes too) ----
opened2 = []
class N3:
    def emit_call_failed(s,*a): pass
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s, name, c):
        opened2.append(name); b.record_failure(ctx)
breaker_events.NOTIFIER = N3()
b = cb.CircuitBreaker("t", failure_threshold=1)
b.record_failure(ctx)
print("PROBE 3 (opened re-entry): fired", len(opened2), "->",
      "PASS" if len(opened2)==1 else "FAIL")

# ---- PROBE 4: crit 7 control, threshold <= 0. Expect FAIL on every run so far. ----
class N4:
    def emit_call_failed(s,*a): pass
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s,*a): print("     tripped on first failure -> crit 7 FAIL")
breaker_events.NOTIFIER = N4()
for t in (0, -1):
    print(f"PROBE 4 (threshold={t}):", end=" ")
    x = cb.CircuitBreaker("t", failure_threshold=t)
    x.record_failure(ctx)
    print()

# ---- PROBE 5: crit 11, caller_state forwarded verbatim, same object ----
seen = []
class N5:
    def emit_call_failed(s, name, c, fc, th): seen.append((c.caller_state, c is ctx2))
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s,*a): pass
breaker_events.NOTIFIER = N5()
ctx2 = CallContext(5, None, BreakerState.HALF_OPEN)
cb.CircuitBreaker("t").record_failure(ctx2)
print("PROBE 5 (domain rule):", seen, "->",
      "PASS" if seen==[(BreakerState.HALF_OPEN, True)] else "FAIL")
```

Enum docstring check (catches the CPython bare-literal trap):

```fish
python3 -c "
import breaker_state as bs
for m in bs.BreakerState: print(m.name, repr((m.__doc__ or '')[:50]))
"
# If all three print the same text they inherited the CLASS docstring —
# CPython discards bare string literals written under enum members.
```

---

## Method notes for future tasks

- **Score blind.** Save as `A1.py`, `B1.py`…, shuffle, score without knowing which is which.
- **Probe every emit path, not just the one the rubric names.** Task 02 was accidentally
  a better test than designed because `record_success` carried a second instance.
- **Keep a control criterion** — something never mentioned in any prompt (here, crit 7).
  It distinguishes "the model got better" from "the model was told."
- **One pass is enough for an estimate.** Three at temp 0.3 if the result is close.
- **Frontier control:** run Prompt A once through Claude Code on the same rubric for a
  same-task baseline rather than comparing across a language change.
