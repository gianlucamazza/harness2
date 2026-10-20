# Corrected contact campaign v4 plan

Status: In progress; ADR-0005 and the USD 10 cumulative cap accepted on 2026-10-20.
No new experimental inference or payment has been initiated.

## Outcome and fixed scope

Complete a new experiment on the corrected adapter, whether its result is
positive, saturated or negative. Keep 12 development tasks, freeze once, then
36 new held-out cases and original/frozen/four-sample comparison arms. Run the
87 original dev regressions and 44 released extraction regressions in both arms.
Do not use the existing released 36 as fresh held-out evidence. Do not promote
an instruction automatically or contact xLlama/Xbox.

## Cost basis

Measured conservative liabilities from the completed qualified pilot:

| Phase                                             | Paid requests | Conservative USD |
| ------------------------------------------------- | ------------: | ---------------: |
| Optimization, including probes and proposer calls |           395 |         2.346828 |
| Four-sample development baseline                  |            48 |         0.005196 |
| Held-out comparisons and repairs                  |           189 |         0.038931 |
| Original regression comparisons                   |           174 |         0.010186 |
| Total qualified study                             |           806 |         2.401141 |

The current retained cumulative liability is USD 3.990737. A total cap of USD 10
leaves at most USD 6.009263 newly admissible. A planning range of approximately
USD 2.4-4.8 additional conservative liability is one to two times the old measured
study, not a confidence interval, provider invoice or completion guarantee. The
44 added extraction regressions and corrected prompt can change consumption.
Retain doubled peak rates and full bounds for unknown liabilities. Do not top up
the provider account automatically. Recheck availability before live admission.

## Execution order and completion gates

1. Obtain explicit acceptance of ADR-0005 and the cumulative USD 10 ceiling.
2. Add and test an authorization-bound ledger migration; preserve original bytes,
   receipt identities, liabilities, idempotence, locks and fail-closed behavior.
3. Add a trusted host driver with SSH transport for remote OpenCode workspaces
   and runtime executions. Test scope isolation, artifact transfer, failed
   sessions, uncertain outcomes and absence of real credentials from guest data.
4. Commit protocol v4 independently. Pin source identities, public specification,
   model/catalog, fixtures, session and call limits, freeze/selection rules,
   regression phases and budget admission/stop behavior.
5. Boot the dedicated VM and verify actual source/kernel/dependency identity.
   Run only the controlled canary needed to verify the new transport. Charge it
   to the same ledger and keep it separate from study outcomes.
6. Execute all 12 development tasks without hidden fallback; capture every
   proposer/selector/solver request and adoption decision. Stop on unqualified
   failure. Freeze the final adopted instruction before generating held-out data.
7. Generate and seal 36 genuinely new cases and independent gold on the host.
   Pin the post-freeze manifest before any held-out inference; send only inputs
   to the runtime. Evaluate all three arms without adaptation or reflection.
8. Run the two regression suites in both arms, retaining the original checks,
   model/settings and held-out-turn exclusion. Report quality separately from
   schema success, repairs and compute. Keep gold out of model workspaces.
9. Export raw attempts, decisions, trace/receipt links, catalog/source identities,
   freeze/sealed manifests and full cumulative accounting. Independently verify
   quality, selection, provenance and spend. Preserve any failure separately.
10. Update documentation, prepare separate commits, publish to the personal
    repositories and verify exact-head CI. Audit every phase against evidence,
    then shut down VM/gateway and report the measured result and remaining cap.

If no request can be admitted without exceeding the approved ceiling, stop
before forwarding and report the campaign incomplete. Do not relabel a partial
run, offline tests or a single canary as a completed quality study.
