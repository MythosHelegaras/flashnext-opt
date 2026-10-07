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
breaker_events.NOTIFIER = cb.NOTIFIER = N1()
b = cb.CircuitBreaker("t", failure_threshold=3)
b.record_failure(ctx)
print("PROBE 1 (crit 13): counts", failed, "| breaker_opened fired", len(opened), "->",
      "PASS" if len(opened)==1 else "FAIL")

# ---- PROBE 2: re-entry from emit_call_succeeded  <-- THE DISCRIMINATING PROBE ----
class N2:
    def emit_call_failed(s,*a): pass
    def emit_breaker_opened(s,*a): pass
    def emit_call_succeeded(s, name, c, st): b.record_failure(ctx)
breaker_events.NOTIFIER = cb.NOTIFIER = N2()
b = cb.CircuitBreaker("t", failure_threshold=5)
b.record_failure(ctx); b.record_failure(ctx)
before = b._failure_count
b.record_success(ctx)
print(f"PROBE 2 (success re-entry): count {before} -> {b._failure_count} ->",
      "PASS (nested failure survived)" if b._failure_count==1 else "FAIL (swallowed)")

# ---- PROBE 3: re-entry from emit_breaker_opened (non-discriminating) ----
opened2 = []
class N3:
    def emit_call_failed(s,*a): pass
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s, name, c):
        opened2.append(name); b.record_failure(ctx)
breaker_events.NOTIFIER = cb.NOTIFIER = N3()
b = cb.CircuitBreaker("t", failure_threshold=1)
b.record_failure(ctx)
print("PROBE 3 (opened re-entry): fired", len(opened2), "->",
      "PASS" if len(opened2)==1 else "FAIL")

# ---- PROBE 4: crit 7 control, threshold <= 0 ----
class N4:
    def emit_call_failed(s,*a): pass
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s,*a): print("     tripped on first failure -> crit 7 FAIL")
breaker_events.NOTIFIER = cb.NOTIFIER = N4()
for t in (0, -1):
    print(f"PROBE 4 (threshold={t}):", end=" ")
    try:
        x = cb.CircuitBreaker("t", failure_threshold=t)
        x.record_failure(ctx)
        print()
    except Exception as e:
        print(f"raised {type(e).__name__}: {e} -> crit 7 handled (check it's deliberate)")

# ---- PROBE 5: crit 11, caller_state forwarded verbatim, same object ----
seen = []
class N5:
    def emit_call_failed(s, name, c, fc, th): seen.append((c.caller_state, c is ctx2))
    def emit_call_succeeded(s,*a): pass
    def emit_breaker_opened(s,*a): pass
breaker_events.NOTIFIER = cb.NOTIFIER = N5()
ctx2 = CallContext(5, None, BreakerState.HALF_OPEN)
cb.CircuitBreaker("t").record_failure(ctx2)
print("PROBE 5 (domain rule):", seen, "->",
      "PASS" if seen==[(BreakerState.HALF_OPEN, True)] else "FAIL")
