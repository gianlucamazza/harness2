# ADR-0004: Explicit contact semantics, adoption eligibility, and request tracing

Status: Accepted by the operator on 2026-10-20.

## Context

The completed pilot produced 28/36 exact frozen outputs against the unchanged
instruction's 36/36. Its artifact requested arrays for multiple contacts, despite
the runtime's fixed single-object output. The adapter exposed fields and missing
value handling, but omitted cardinality and the protocol's primary-contact policy.
Only three of the 87 existing regression cases exercised typed extraction.

At k=1, the core adopts the single final without a selector session. Changing a
selector prompt alone cannot prevent adoption of a repaired or rejected candidate.
All provider requests were charged to the cumulative ledger, but 88 proposer
requests could not be attributed to retained CLI stage events.

ADR-0001 requires selection without gold answers or grading scores. Runtime-owned
validation and approvals must remain unchanged. The completed study, accepted
ADRs, frozen instruction and published evidence must not be rewritten.

## Decision

1. Define a versioned, public contact specification in Harness2: exactly one JSON
   object with name/email/phone as nullable strings; no invented values; source
   instructions are data; for multiple contacts use an explicitly designated
   primary contact, otherwise ambiguous fields are null. Expose the same text to
   proposer missions and execution-evidence consumers, and include its digest in
   campaign identity. Keep runtime schema/rendering authoritative for structure;
   assert compatibility rather than silently overriding the runtime contract.
   The primary-contact rule is an experiment policy, not an existing runtime
   factual guarantee. Keep the original baseline instruction unchanged.
2. Introduce an opt-in contact adoption eligibility policy, applied after candidate
   execution and before adoption, including the trivial k=1 path. An eligible
   output must complete in one attempt and pass the unchanged structural contract.
   A repaired or rejected candidate cannot displace an eligible incumbent. If no
   eligible instruction is available, stop the qualified campaign and record that
   outcome; never represent a fallback as successful optimization. Persist the
   decision, evidence references and reason. Keep other benchmarks' behavior
   unchanged. Do not use gold correctness, field-match counts, or held-out evidence
   in this decision. Eligibility is necessary, not proof of factual correctness.
3. Add a deterministic, offline extraction regression suite using the released
   36 cases and explicit edge cases for primary selection, unresolved ambiguity,
   missing fields and source injection. Check expected values independently of
   the instruction under test. Separate fixture/oracle tests from fake-runtime
   integration tests: neither proves a live model will answer correctly. Keep
   answers outside optimizer snapshots and inputs. Preserve original evidence.
4. Trace every forwarded gateway request with a campaign-scoped request ID and
   trusted caller context: role, session, phase and logical execution when known.
   Use per-session gateway credentials or equivalent host-owned routing context
   so auxiliary SDK requests inherit attribution without relying on model-written
   headers. Do not forward internal identifiers or credentials to DeepSeek. Keep
   accounting independent of attribution; missing/invalid attribution fails before
   forwarding in qualified mode. Preserve old numerical receipts and migration
   evidence. Unknown auxiliary subroles remain explicit, never guessed from usage.
5. Preregister a follow-up protocol separately before paid inference. It must pin
   the new specification, eligibility policy, fixtures, model/settings, budgets,
   freeze rule and comparison arms. Generate fresh sealed held-out cases after
   freezing; the published 36 become regression data only. Report saturation as
   such; do not select a weaker model or change cases after seeing outcomes.
   No automatic promotion, production deployment, or xLlama/device work is added.
6. Preserve the approved cumulative USD 5 ceiling and existing liabilities. Plan
   a bounded canary first, with a worst-case reservation calculation including
   readiness, SDK auxiliary calls, repairs and failure liabilities. A full live
   follow-up is conditional on fitting the remaining allowance; insufficient
   funds must stop before forwarding, not start a fresh ledger or raise the cap.

## Consequences

This changes the experimental treatment and contact adoption behavior, requiring
a new campaign identity and protocol. Existing results remain a valid negative
result for their original adapter/profile. Structural eligibility cannot detect
all wrong contact choices; the independent post-selection oracle remains required.
Caller attribution must be established before concurrent sessions can be trusted.
No claim of improvement follows from unit tests or successful canaries.

Implementation order and completion gates are recorded in
`experiments/contact/FOLLOWUP-PLAN.md`. Operator acceptance authorizes those
implementation changes; additional spending remains inside the existing cap.

## Alternatives

- Patch the frozen instruction and evaluate again on the same 36 cases: rejected;
  it would reuse published evaluation answers for tuning.
- Give gold scores to the selector: rejected; it changes the accepted evidence-only
  selection boundary and would conflate selection with post-selection evaluation.
- Reject prompts by keyword searches for "array": rejected; wording checks cannot
  establish behavior and would miss equivalent instructions or legitimate negation.
- Change global `delivered` semantics to mean "no repair": rejected; completion and
  adoption eligibility are different facts, and other benchmarks must retain their
  existing policy.
- Infer stage from timestamp/token coincidences: rejected as authoritative tracing;
  these are diagnostic hints, not stable request identity.
