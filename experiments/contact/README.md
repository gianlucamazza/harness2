# Contact extraction pilot

The [completed DeepSeek pilot](RESULTS-2026-10-20-v2.md) found no improvement:
the frozen candidate scored 28/36 exact records against the original's 36/36.
It was not promoted. The original [incomplete-pilot record](RESULTS-2026-10-20.md)
is retained separately. Protocol version two and ADR-0003 govern the completed run.

Phase one fixes DeepSeek Flash for both hosted execution and OpenCode proposals.
Use synthetic source text only. The editable surface is exactly
`systemprompt.md`; the runtime owns the source rendering, reply format, schema,
repair policy, persistence and approvals. Phase two may use xLlama under a new
campaign identity; no console is contacted by the phase-one adapter.

Prepare the proposer with Node.js 22+ (the VM uses the host's Node 24 binary):
`python scripts/setup_contact_provider.py`. It prepares the pinned OpenCode and
Bun runtime without downloading any benchmark data, then prints package metadata and installs
`@ai-sdk/deepseek@3.0.69` with `zod@4.3.6` into `dependencies/deepseek-sdk`, and
verifies the provider import. The provider uses that explicit installed entrypoint,
not an incomplete per-user auto-install cache. The lockfile hash enters campaign identity.

The CLI is `python -m harness2.cli.agent_runtime`. `plan` is offline. `canary`
executes one synthetic typed request and never starts OpenCode. `optimize` runs
the actual Harness2 parallel k=1 cycle, and requires a dedicated VM and a
committed protocol. Every paid request passes through a local gateway that reserves a conservative
maximum cost before forwarding. The operator approved a cumulative 5 USD cap.
The current follow-up preregistration is `protocol-v3.json` (ADR-0004).
`protocol-v2.json` (ADR-0003) and `protocol.json` preserve the completed pilot
rules. Reservations use twice the published Flash
peak rates. Successful requests with valid bounded usage retain only their
rounded-up usage cost at those conservative rates. Unknown or failed requests
retain the full reservation. Migration preserves the old ledger and every prior
request; a replacement run does not receive a fresh monetary allowance.
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
That does not mean a new budget root: always supply `--budget-root` pointing to
the operator's existing cumulative ledger. The v3 preflight verifies the original
1,062-receipt prefix and rejects an empty/replaced ledger. The published ledger
is historical evidence, not permission to create another monetary allowance.
No automatic fallback, approval, promotion or production service restart occurs.

## ADR-0004 follow-up

The public task specification in `harness2/contact_policy.py` is shared by
missions and task evidence, and its hash enters campaign identity. The baseline
instruction is unchanged. Before inference, runtime schema and reply format are
checked for structural compatibility; runtime gates remain authoritative.

Contact CLI runs opt into `contact-first-attempt-v1`. Only a completed, structurally
valid first attempt is eligible for adoption. An ineligible final retains one
eligible base deterministically, recording `incumbent-retained`; it is not a
selector fallback or a quality improvement. If none is eligible, qualification
fails and the driver stops. Both k=1 and selector paths, parallel and sequential,
apply the policy. Other benchmarks retain their finals-only selection behavior.
This technical gate cannot detect every wrong contact or invented field.

Caller-owned scoped credentials bind solver/proposer/selector sessions to the
gateway. SDK auxiliary requests inherit the session; their finer subrole remains
`unknown`. Each forwarded HTTP request has a stable trace ID; paid POSTs link to
one accounting receipt, while unbilled catalog GETs have trace records without
monetary receipts. Unattributed or revoked credentials are refused. Internal
context headers and scoped credentials are not forwarded upstream. The legacy
standalone gateway is not a qualified follow-up entry point.

`plan` computes bounds without model calls. v3 bounds cap POST count, serialized
payload bytes and output tokens, including auxiliary calls, repairs and failures;
catalog GETs are capped separately. The full-trial upper bound is USD 130.429952,
which does not fit the remaining USD 1.009263 after the canary. This upper bound
is not a prediction of likely spend. No full new optimization/evaluation ran.

The host-side canary command requires an already running disposable VM with the
matching runtime source and Python environment, authenticated SSH and reverse
forwarding. Its upstream API key stays in the host `.env`; the VM receives only
a session credential through SSH stdin. The output directory must be new:

```bash
python scripts/contact/run_isolated_canary.py \
  --runtime ../agent-runtime --budget-root runs/contact-pilot \
  --output runs/contact-followup-canary-new \
  --ssh-key ~/.cache/harness2-vm/id_ed25519 \
  --known-hosts ~/.cache/harness2-vm/known_hosts
```

This is a paid command, bounded by the existing ledger and preflight, not an
offline demonstration. The completed run is recorded in
[FOLLOWUP-RESULTS-2026-10-20.md](FOLLOWUP-RESULTS-2026-10-20.md).

The [44 released regression cases](../../docs/evals/contact-regressions-v1/README.md)
have an independent offline checker. Do not copy their gold into optimizer
snapshots. These fixtures were not all rerun live in the follow-up. Any future
`evaluate` needs a `--heldout-manifest` with exactly `generated_at`,
`inputs_sha256` (SHA256 of sorted-key JSON encoding of public cases), and
`instruction_sha256`. It must bind inputs generated after `frozen_at`; released
case hashes and development inputs are refused. No new held-out set is generated
until a new instruction can actually be frozen.

The driver stops after the first task with a fallback stage, even if the upstream
core would report a delivered base answer as successful. Such a campaign cannot
freeze an artifact or support an improvement claim. Preserve it separately.

Released post-selection evidence lives in `docs/evals/contact-pilot-2026-10-20/`.
Keep that directory and `scripts/contact/` out of optimizer VM snapshots. Include
only implementation packages, protocol files and public development inputs;
never copy gold, evaluation output or the full repository into an optimizer VM.
The released 36 cases cannot be reused as fresh held-out evidence.

Verify the released result without model calls:

```bash
python scripts/contact/verify_results.py
```

## Completed contact campaign v4

[Results](CAMPAIGN-V4-RESULTS-2026-10-20.md) report 36/36 fresh held-out records versus 35/36 baseline, with all original regressions passing. This is a small observed gain; no automatic promotion was performed.

Offline admission planning (no model calls):

```sh
python -m harness2.contact_campaign --plan --runtime ../agent-runtime --budget-root runs/contact-pilot --output runs/contact-next
```

ADR-0005 authorizes the cumulative USD 10 ceiling. Earlier v3 commands and USD 5 limits describe historical cohorts.
