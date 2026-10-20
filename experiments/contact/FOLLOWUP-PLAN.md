# Contact follow-up implementation plan

Status: Implemented and locally verified; remote publication checks in progress.
ADR-0004 was accepted by the operator on 2026-10-20.

## Scope and invariants

Complete the four improvements identified in the pilot review: public task
semantics, extraction regression coverage, adoption eligibility and request
attribution. Preserve the original study and default runtime behavior. No model
calls are needed for implementation and offline verification. A paid follow-up
requires a separately committed protocol, isolation checks and sufficient existing
cumulative budget; it is not implied by a green test suite.

## Ordered work and evidence

| Step | Deliverable                                                                          | Completion evidence                                                                                                                                                                                                                           |
| ---- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Accept ADR-0004; retain accepted ADRs unchanged                                      | Operator acceptance recorded before structural code edits                                                                                                                                                                                     |
| 2    | Versioned public contact specification, shared mission text and identity digest      | Tests cover cardinality/primary policy visibility, unchanged baseline, runtime structural compatibility and resume refusal on specification drift                                                                                             |
| 3    | Explicit contact adoption eligibility at all adoption paths, including k=1           | Fake-runtime tests prove repaired/rejected candidates cannot displace an eligible incumbent, no eligible result stops qualification, and non-contact behavior is preserved                                                                    |
| 4    | Released extraction fixtures with independent expected values and diagnostic metrics | Offline oracle tests catch wrong contact, extra fields, arrays and invented values; released frozen artifact's failures remain reproducible from original evidence                                                                            |
| 5    | Caller-owned request attribution and stable receipt links                            | Local fake-upstream tests cover solver, proposer, auxiliary requests, concurrent sessions, missing context, retries and unknown outcomes; each forwarded request has exactly one receipt and attribution; no internal secret reaches upstream |
| 6    | New preregistration and run preflight                                                | Protocol committed independently, identity/source/catalog checks, sealed-data boundary, conservative cost feasibility calculation, cumulative original ledger retained                                                                        |
| 7    | Documentation and publication                                                        | Full offline suite, original evidence verifier, lint/format, clean secret-safe diff, separate reviewable commits and remote CI for the published head                                                                                         |
| 8    | Conditional live validation                                                          | Isolated canary/full trial only if reservations fit the existing USD 5 ceiling; otherwise record the exact budget blocker without paid forwarding. Fresh held-out data and independent scoring are required for any new improvement claim     |

## Budget and scientific limits

The published final ledger retained USD 3.990600 out of USD 5. Re-read the actual
ledger before planning live work; USD 1.009400 is a historical remaining allowance,
not permission to reset accounting or assurance that another full trial fits.
Do not lower reservation bounds simply to fit a run. Successful offline work may
be published while the live experiment remains explicitly incomplete or blocked.

The original baseline scored 36/36. A further saturated comparison does not prove
equivalence or benefit. Define new case families and decision rules before observing
model outputs; do not iterate the benchmark until an improvement appears.

## Read-only pre-implementation verification (2026-10-20)

- Baseline: `python -m unittest discover -s tests -q`, 30 tests passed.
- Published evidence: `python scripts/contact/verify_results.py`, passed; 276
  physical executions, held-out exact records 36 original / 28 frozen, 87
  regression cases per arm and 84 identical non-extraction first requests.
- Local cumulative ledger matches the published ledger byte for byte:
  SHA256 `890664c1d73f47b01959277330f60fc24e2e6d981124f20aee4db73237ea618f`.
  It contains 1,062 requests, no unknown usage, USD 3.990600 retained and
  USD 1.009400 remaining. No request was forwarded during these checks.
- The largest historical single-request reservation was USD 0.058256. That
  observation is not a bound for future prompts or a full-campaign cost estimate.
  A new run needs an explicit payload-size bound, request-count allowance and
  auxiliary/readiness accounting before a feasibility decision.
- Harness2 and agent-runtime had clean tracked worktrees before the proposal;
  only ADR-0004 and this plan were added. No structural implementation has begun.

## Implementation evidence

- ADR acceptance: commit `39853f6`; separate v3 preregistration: `cf5a5fd`.
- Public specification and eligibility: `harness2/contact_policy.py`, adapter
  identity, the optional adoption-pool hook and `tests/test_contact_followup.py`.
  Runtime schema compatibility was checked against the actual installed runtime;
  parallel, sequential, k=1, k=2, incumbent retention, candidate adoption and
  no-eligible-result paths have software coverage. Existing non-contact core
  tests pass with the hook absent. Cached raw artifacts are checksum-verified.
- Regression fixtures: `docs/evals/contact-regressions-v1`, 44 cases; independent
  checker `scripts/contact/check_regressions.py`. Oracle tests detect wrong
  contact, arrays, extra fields, invention, missing/duplicate records and rejection.
  These are not 44 live inference successes.
- Attribution: `RequestAttribution` and `RequestLimits` in `runtime_budget.py`;
  real local HTTP tests cover concurrent roles, scoped proposer environment,
  auxiliary requests, catalog GETs, revoked/missing credentials, retries and
  retained unknown liabilities. Multiple registry instances share a file lock.
- New data boundary: `check_heldout` binds post-freeze input manifests and refuses
  development/released case hashes. Gold remains outside optimizer snapshots.
- Offline validation: 49 tests, lint/format and 47 release checksums passed;
  both published evidence verifiers passed.
- Conditional live branch: the isolated canary passed exactly at the first
  attempt; source/kernel/catalog invariants held and both HTTP requests were
  attributed. The cumulative original 1,062 receipts were preserved; one paid
  receipt added USD 0.000137 conservative liability, total USD 3.990737.
- Full-trial branch: the USD 130.429952 worst-case bound exceeds USD 1.009263
  remaining, so the full follow-up was not launched. No fresh held-out set,
  prompt promotion or device deployment occurred. This satisfies the conditional
  stop rule, not a new demonstration of optimizer benefit.

See `FOLLOWUP-RESULTS-2026-10-20.md` and the checksummed follow-up bundle for
raw attempts, trace/receipt links, incremental accounting and independent checks.
