# ADR-0005: Run the corrected contact campaign with cumulative request admission

Status: Accepted by the operator on 2026-10-20, including the USD 10 cumulative cap.

## Context

ADR-0004 corrected the public contact specification, adoption eligibility and
request attribution. The isolated canary passed, but protocol v3 refused a full
trial because the product of every request's maximum reservation exceeded the
remaining allowance. That USD 130.429952 bound is not an expected spend estimate.

The cumulative ledger contains 1,063 paid requests and retains USD 3.990737
against the approved USD 5 ceiling. Its remaining allowance is USD 1.009263.
The previous qualified optimization and comparisons, excluding failed pilots,
retained USD 2.401141 at the existing conservative rates. This historical
measurement is useful for planning, not a guarantee for the corrected treatment.

The authenticated provider balance was checked read-only; this proposal does not
authorize a payment or account top-up. The key remains host-only. Official prices
were checked on 2026-10-20: Flash peak cache-miss input USD 0.30/M and output
USD 1.20/M. Reservations retain the existing doubled rates, USD 0.60/M and
USD 2.40/M. The fixed solver remains `deepseek-flash`; do not change models after
observing study outcomes.

## Decision

Upon explicit operator acceptance:

1. Increase the existing cumulative conservative-liability ceiling to **USD 10**,
   including all past pilots and canaries. Maximum new admitted liability is
   USD 6.009263 from the recorded starting ledger. Do not create a new allowance,
   reset receipts, recharge an account, or change reservation rates. Preserve the
   exact old ledger in a checksummed migration record. A durable authorization
   record binds the new cap, prior cap, prior ledger hash and operator decision.
   A caller-supplied number alone cannot raise the authorized cap.
2. Supersede ADR-0004 decision 6's full-campaign aggregate-fit prerequisite and
   protocol v3's corresponding preflight for this new campaign. Use durable
   **per-request** admission against the cumulative authorized ceiling. Reserve
   the complete bounded liability before each forward; reconcile only validated
   successful usage under ADR-0003. Failed, unknown or inconsistent usage retains
   the full reservation. Stop before any request would cross USD 10. Keep separate
   hard request-count, payload-size, output, session and timeout limits. Do not
   describe the entire study as guaranteed affordable or guaranteed to finish.
3. Let a trusted host driver own orchestration, accounting, scope issuance,
   snapshots, freezing and evaluation. Execute untrusted OpenCode sessions and
   typed runtime inference in the dedicated disposable VM, reached through SSH.
   Remote model processes receive only their scoped gateway credentials. Do not
   expose an unscoped credential-issuing API or upstream key to model workspaces.
   Reverse forwarding carries requests to the host gateway. Auxiliary SDK calls
   inherit caller attribution; finer subroles remain unknown when unproven.
4. Preregister protocol v4 separately before any new experimental inference:
   12 fixed development cases, k=1 parallel optimization, same fixed model and
   sampling, unchanged baseline instruction, corrected public specification and
   first-attempt eligibility. Freeze the final task's adopted instruction even
   if it retains the baseline. Generate 36 new sealed cases only after freeze,
   nine per original cluster, with independent nullable-string gold fixed before
   evaluation. Reject development and released regression inputs. Compare original,
   frozen and four-sample fixed-instruction majority arms on identical inputs.
5. Run both original 87 dev regressions and the released 44 extraction regressions
   against baseline and frozen instructions. Keep original held-out turns sealed.
   Their released gold is available only to the host's post-selection evaluator,
   never to proposer sessions, reflection or the runtime execution request.
6. Report exact/field correctness, invented non-null values, first-attempt schema,
   rejections, repairs, failures, tokens, latency, adopted-baseline counts and
   per-role/session calls. Preserve incomplete/failing runs rather than silently
   restarting or merging their metrics. Budget exhaustion stops the campaign and
   produces an incomplete report. No automatic prompt promotion, deployment,
   fallback model, tool approval, Xbox/xLlama use or benchmark redesign is added.
7. Verify offline policy/migration/isolation behavior before live work. At every
   boundary check source hashes, protocol, actual model catalog and VM identity.
   Publish raw synthetic evidence with independent verification, documentation
   and reviewable commits; verify exact published heads and remote CI. Shut down
   guest and gateway afterward. Positive, saturated and negative outcomes all
   count as completed experiments if every preregistered phase actually finishes.

## Consequences

This explicitly changes both the authorized monetary ceiling and the admission
policy. It requires operator acceptance, a migration with preserved historical
evidence, and a new preregistration. Accepted ADRs and protocols v1-v3 remain
unchanged. The hard cumulative ceiling remains effective even if historical
cost forecasts are wrong. A run may stop before completion; exhausting a cap
does not establish a research result or permit another allowance.

The host driver adds a remote execution transport. Its credential and artifact
boundaries need tests and real VM verification. Retaining the original baseline
is a valid policy outcome, not evidence of a quality improvement.

## Alternatives

- Keep USD 5: safe, but the remaining allowance is below the historical measured
  cost of a comparable study. Do not spend it on a predictably partial replica.
- Raise the cap to the product of all request maxima: unnecessary for a study
  with durable per-request admission and validated usage reconciliation.
- Lower token reservations or silently shorten the 12/36 study to fit: rejected;
  it would weaken accounting or substitute a different experiment.
- Place the upstream key or a scope-issuing control secret in the optimizer VM:
  rejected; a trusted host owns those capabilities.
- Recharge the provider account first: not needed on current balance evidence;
  recharging also would not authorize increasing the experimental ceiling.

References: [provider prices](https://api-docs.deepseek.com/quick_start/pricing/),
[balance API](https://api-docs.deepseek.com/api/get-user-balance/),
`experiments/contact/CAMPAIGN-V4-PLAN.md`.
