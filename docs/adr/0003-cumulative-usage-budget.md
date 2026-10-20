# ADR-0003: Reconcile completed requests within the cumulative campaign budget

Status: Accepted by the operator on 2026-10-20.

## Context

The first pilot stopped before instruction freeze. Its cumulative ledger contains
163 forwarded requests and USD 4.992418 in reservations against the approved USD 5
ceiling. Every request has recorded provider usage. The current protocol reserves
request bytes plus framing allowance and maximum output, and never releases the
unused portion. This protects the ceiling but prevents the remaining evaluation
even when completed requests consumed substantially fewer tokens.

The published protocol and historical reports must remain unchanged. Provider
usage supports conservative accounting; it is not an independently verified bill.

## Decision

After acceptance, preregister a version-two protocol before further inference.
Replace a successful completed request's reservation with the rounded-up cost of
its validated reported input and output tokens at the existing reservation rates:
USD 0.6 and USD 2.4 per million tokens, respectively. These are twice the peak
rates recorded in version one. Treat all input tokens as cache misses.

Keep full reservations for in-flight, failed, interrupted, missing-usage or
malformed-usage requests. Require integer nonnegative counts within the original
token bounds, a successful response and consistent totals. If reported usage
exceeds a bound, fail closed and prevent additional requests pending review.
Repeated completion must be idempotent; contradictory completion must fail closed.

Reconcile the existing ledger under its exclusive lock, preserving its original
bytes, digest and per-request reservations in an audit artifact. Carry every old
request into the cumulative accounting. Never create a fresh USD 5 allowance for
a replacement run. Persist state atomically and durably before admitting another
request. Verify ledger totals and accounting identity on every operation.

Run a new development campaign under a new execution identity; preserve both
incomplete pilots. Keep the accepted selection, freeze, isolation, grading and
regression rules. Generate the 36 new held-out cases only after instruction freeze.
Do not adapt the frozen instruction after grading. The existing USD 5 cumulative
ceiling remains binding. xLlama remains a separate second phase.

## Consequences

Completed requests release unused conservative allowances, making the remaining
pilot feasible without increasing the approved cap. The control depends on
provider usage integrity and the recorded rate bound; it does not prove an invoice.
Unknown liabilities continue to consume their full reservation. A new protocol,
accounting migration, failure/concurrency tests and live evidence are required.
No quality claim or automatic instruction promotion follows from this change.

## Alternatives

- Retain version-one accounting: valid, but the campaign cannot finish within
  its remaining reservation allowance.
- Increase the monetary ceiling: requires new spending authorization and does
  not address unused reservations.
- Reset the ledger or count only a replacement run: rejected because it loses
  cumulative campaign liabilities.
- Release reservations on timeouts or absent usage: rejected because actual
  consumption is unknown.
