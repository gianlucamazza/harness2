# Contact adapter corrections and bounded validation

ADR-0004 was accepted before implementation. Protocol v3 was committed separately
as `cf5a5fd` before the live canary. The completed pilot and its negative result
remain unchanged: frozen 28/36, original 36/36; no prompt was promoted.

## Implemented behavior

- A versioned public specification exposes single-object cardinality, nullable
  fields, explicit primary-contact policy and untrusted source handling. Missions
  and task evidence share the same text; its digest enters campaign identity.
  The runtime's actual schema/reply format are checked for compatibility.
- Opt-in contact eligibility applies at both trivial k=1 and selector adoption
  paths. Repaired/invalid candidates cannot displace an eligible base. No eligible
  instruction fails qualification. Decisions, reasons and execution references
  are persisted. Completion and factual correctness remain separate.
- 44 released regression fixtures (36 old plus eight edge cases) and an independent
  exact-value checker catch wrong contact, arrays, extra keys and invented values.
  Fake-runtime and oracle tests do not imply 44 live-model successes.
- Gateway tracing binds requests to caller-owned session credentials, including
  SDK auxiliary traffic. Each forward has a trace ID; paid calls also have an
  accounting receipt. Catalog requests are traced without monetary liabilities.
  Unknown finer subroles remain explicit. Concurrent journal writes use file locks.
- Preflight verifies the existing accounting prefix and enforces request/output/
  payload bounds. Evaluation also requires a post-freeze manifest and refuses
  development or released regression inputs.

## Live canary

Implementation tested: Harness2 `d715037`, agent-runtime `fccfe2c`; the runtime
source was unchanged. A dedicated KVM guest ran kernel `6.8.0-147-generic`.
Runtime Python source hashes, structural schema and kernel matched before and
after execution. The provider catalog matched the pilot's DeepSeek Flash catalog.
Only a temporary gateway credential entered the guest; the upstream key stayed
on the host.

One original-instruction synthetic extraction completed in one attempt with all
three expected fields. Usage: **92 input / 34 output tokens**, recorded latency
**1,312.6 ms**. The gateway recorded **two attributed HTTP requests**: one catalog
GET and one Chat Completions POST. The latter links uniquely to receipt 1062.
The canary exercised the new adapter, scoped solver routing and eligibility gate;
it did not run a live OpenCode optimizer session or compare candidate quality.

The conservative added liability is **USD 0.000137**. Cumulative retained liability
is **USD 3.990737 / 5**, with **USD 1.009263** remaining. Every original receipt
was preserved. These figures use the preregistered conservative rates and are not
a verified provider invoice. Gateway and VM exited; the VM SSH port is closed.

## Full follow-up disposition

The full-trial worst-case bound is **USD 130.429952**, derived from 1,024 admitted
POSTs, at most 200,000 serialized bytes plus 4,096 framing tokens per call, and
2,048 output tokens. It includes SDK auxiliaries, repairs and unknown outcomes.
This is a conservative upper bound, not an expected price or requested budget.
It exceeds the remaining allowance, so **no full follow-up trial was launched**.
No new held-out set was created and no new improvement claim is made. The original
instruction remains the default. No runtime service or device was deployed.

## Reproduce software/evidence checks

Local validation passed **49 offline tests**, lint/format checks and **47 release
asset checksums**. The independent verifiers reproduce both the unchanged pilot
and the new canary; a test that rehashes forged accounting is still rejected.

```bash
python -m unittest discover -s tests -q
python scripts/contact/check_regressions.py
python scripts/contact/verify_results.py
python scripts/contact/verify_followup.py
python scripts/check_provenance.py
```

The [follow-up evidence bundle](../../docs/evals/contact-followup-2026-10-20/README.md)
contains raw canary attempts/result, model identity, source inventory, adoption
decision, request traces, incremental accounting, preflight and checksums.
`verify_followup.py` independently recomputes the exact answer, usage liability,
trace/receipt links and refusal bound without runtime or adapter imports.
