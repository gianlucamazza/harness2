# Contact extraction pilot

ADR-0001 is accepted. This protocol is an executable preparation artifact, not a
completed experiment or a claim of improved extraction.

Phase one fixes DeepSeek Flash for both hosted execution and OpenCode proposals.
Use synthetic source text only. The editable surface is exactly
`systemprompt.md`; the runtime owns the source rendering, reply format, schema,
repair policy, persistence and approvals. Phase two may use xLlama under a new
campaign identity; no console is contacted by the phase-one adapter.

Prepare the proposer with Node.js 22+ (the VM uses the host's Node 24 binary):
`python scripts/setup_contact_provider.py`. This prints package metadata, installs
`@ai-sdk/deepseek@3.0.69` with `zod@4.3.6` into `dependencies/deepseek-sdk`, and
verifies the provider import. The provider uses that explicit installed entrypoint,
not an incomplete per-user auto-install cache. The lockfile hash enters campaign identity.

The CLI is `python -m harness2.cli.agent_runtime`. `plan` is offline. `canary`
executes one synthetic typed request and never starts OpenCode. `optimize` runs
the actual Harness2 parallel k=1 cycle, and requires a dedicated VM and a
committed protocol. Every paid request passes through a local gateway that reserves a conservative
maximum cost before forwarding. The operator approved a cumulative 5 USD cap.
Reservations use twice the published Flash peak rates and are never refunded.
Input tokens are bounded by serialized request bytes plus 4096 framing tokens;
output tokens have an explicit ceiling. The ceiling assumes the published rates
remain below the pinned price ceilings. Recheck prices before a later campaign.

Public optimization inputs must be a JSON list of objects with exactly `id`,
`input: {"text": "..."}` and `cluster`. Gold answers live in a separate file and
must not be mounted into the optimizer VM. Never feed full eval cases with
`check`, `expected` or `split` fields into the optimizer. The adapter refuses them.

Before any campaign: freeze the public fixture IDs/order/bytes, oracle policy,
case counts, protocol and independent tests in a separate preregistration
commit. This preparation does not invent a private held-out set now. Generate
36 new held-out cases only after freezing the final instruction. Freeze case
counts and cluster allocations before observing outcomes. The 12 development
cases should span four fixed clusters, three cases each: complete explicit
contact, missing fields, primary-contact ambiguity, and source-text instructions.
The 36 final cases use nine new cases per cluster, with new identities and text.

Compare the existing instruction, Harness2 k=1, and four samples of the unchanged
instruction with evidence-free majority selection. Count execution and optimizer
calls separately; equal rollout counts do not mean equal tokens or cost. The
matched baseline chooses the most frequent completed JSON, ties lexicographically
and then by sample order, without gold. Refusals remain failures, not empty correct
records. Freeze the final development task's adopted instruction regardless of
its correctness score; if the task did not finish successfully, stop the pilot.

Primary outcome: exact record accuracy over nullable name/email/phone strings.
Also record each field, unsupported non-null values, missing-field accuracy,
strict first-response JSON/schema validity, final rejection, repair attempts,
transport failures, tokens and latency. Repair is not first-attempt validity.
The independent evaluator never imports the renderer or the runtime validator.

Report paired flips and uncertainty, stratified by shared template cluster.
With four clusters this is exploratory evidence, not a precise small-gain claim.
Report the unchanged 87 dev cases as a regression control using the same DeepSeek
profile; they are not held-out evidence. Existing held-out turn cases remain
sealed and are not read while tuning. Do not edit accepted historical reports.

A readiness/catalog mismatch, source drift, budget exhaustion, interrupted rollout,
missing attempt artifact, hash mismatch or nonterminal run stops that execution.
A new campaign root is required after changing model, inputs or effective code.
No automatic fallback, approval, promotion or production service restart occurs.

The driver stops after the first task with a fallback stage, even if the upstream
core would report a delivered base answer as successful. Such a campaign cannot
freeze an artifact or support an improvement claim. Preserve it separately.
