# Contact campaign v4 — 2026-10-20

Completed under accepted ADR-0005 and the cumulative USD 10 admission ceiling.
The frozen instruction was evaluated without further adaptation or automatic promotion.

| Evaluation | Baseline | Frozen | Four-sample baseline majority |
|---|---:|---:|---:|
| New held-out records | 35/36 | 36/36 | 35/36 |
| Development | 12/12 | 12/12 | 12/12 |
| Original runtime regressions | 87/87 | 87/87 | — |
| Previously released extraction regressions | 39/44 | 44/44 | — |

The new cohort has nine cases in each of four template families. There was one
paired gain in ambiguity and no paired losses. This small study does not establish
a general Harness² benefit: public policy clarification and optimization are
confounded, and a manually written full-policy baseline was not tested. Historical
cohorts are different datasets and must not be used as a controlled before/after
comparison. The exploratory cluster interval is [-6.06, 11.62] percentage points.

All held-out first responses satisfy the schema; no repairs or rejections occurred.
The frozen arm used 14,340 input and 1,179 output tokens. Baseline used 3,792 and
1,205; all 144 raw four-sample baseline executions used 15,168 and 4,820.
Recorded mean runtime latency was 1,805.61 ms baseline, 1,761.17 ms frozen and
7,313.08 ms summed across four baseline samples. These are descriptive values,
not controlled performance evidence. The 84 original non-extraction first requests
were unchanged, including messages and token limits.

## Execution and provenance

All 12 development tasks completed qualified sessions without hidden fallback.
The host froze the adopted 1,526-byte instruction at 17:52:48.636712 UTC before
constructing the new cohort at 17:52:49.562500 UTC. Instruction SHA-256:
`ac2661cc134ff0eae9ea7857153b742df891fa307dcf47dd827fd14853456429`.

The execution checkout was commit `929fc92`; agent-runtime was
`52b329169f50e01e08da9cce87ba718ddbdeabf0`, with its ten Python source files
verified before and after inference. Model settings, public policy and fixtures
are pinned in the unchanged [preregistered protocol](protocol-v4.json).
Guest kernel was `6.8.0-147-generic`. Host-owned gold, selection and budget stayed
outside model workspaces; only scoped gateway credentials entered the guest.
The initial v4 bootstrap refused SDK lock metadata before any paid call; that
incomplete root remains separate. The corrected v4b cohort ran once to completion.

The evidence includes 365 typed extraction executions, 174 original regression
executions, 885 new paid requests and all 1,948 cumulative receipts. One adopted
development candidate was the baseline; this was an eligible selection, not an
unqualified fallback. VM and gateway shutdown were verified after driver exit 0.
All 36 newly published inputs are now excluded from future held-out cohorts.

## Cost and interpretation

The cumulative conservative admission liability is **USD 6.468339 / 10**, including
USD 3.990737 retained from earlier work. This campaign added USD 2.477602 of
conservative accounting. The ledger preserves the original 1,063 receipt prefix
and the explicit cap authorization; it was never reset.

This counter deliberately uses conservative cache-miss bounds. It is **not an
invoice**. Cache-aware usage estimates for the new campaign are USD 0.199173–0.398345;
for all retained history, USD 0.468508–0.937015, depending on the price window.
The operator's earlier UI observation (USD 0.28, 1,067 requests, 6,311,015 tokens)
was a different snapshot with an unspecified reporting window; exact reconciliation
has not been established. No top-up was performed. There are no further live calls.

## Reproduction and disposition

Run `python scripts/contact/verify_campaign_v4.py` without credentials or network.
The independent verifier recomputes scores, majority selection, chronology,
receipt joins, conservative costs and regression outcomes from the published
[evidence bundle](../../docs/evals/contact-campaign-v4-2026-10-20/).
The runtime defaults remain unchanged; promotion requires a separate decision.
