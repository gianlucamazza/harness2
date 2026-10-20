# ADR-0001: Use Harness2 as an offline optimizer for agent-runtime

Status: Accepted by the operator on 2026-10-20.

## Context

Harness2 separates recursive optimization from execution through `BenchmarkAdapter`
and substrate interfaces. Its proposer currently runs through OpenCode or Claude CLI.
The local DeepSeek-backed OpenCode proposer has passed a live smoke test.

agent-runtime is a bounded inference runtime, not a general coding executor. Its
Conductor owns persistence, concurrency, contract validation, bounded repair, and
human approval. Accepted runtime ADRs 0001, 0003, 0004, and 0006 define those
boundaries. Its HTTP `/runs` endpoint accepts either messages or a typed task;
typed tasks currently render their instructions from code, without a harness override.
It does not expose a general `/v1/chat/completions` inference service to OpenCode.
Its XllamaBackend also assumes `/health` and currently sends no provider API key,
so pointing its base URL at DeepSeek alone would not integrate that provider.

The runtime checkout contains substantial uncommitted work. This proposal lives
in Harness2 and does not modify that checkout or its accepted ADRs.

## Decision

Propose an opt-in offline integration owned by an adapter in Harness2:

1. DeepSeek Flash through the existing OpenCode proposer produces candidate
   instruction artifacts. It does not edit or execute runtime source code.
2. The adapter sends candidate executions through agent-runtime's Conductor,
   retaining its validation, lifecycle, concurrency and approval rules.
3. Start with the typed task `extract_contact`. Add a bounded, opt-in instruction
   artifact seam in agent-runtime, recorded in a new runtime ADR before code.
   The built-in instruction remains the default when no artifact is selected.
4. Only the extraction instruction is editable. Validators, verification, output
   schema, reply format, repair bounds, tool registry and approval policy remain
   runtime-owned and immutable to the optimizer. Do not convert typed tasks to
   free-form messages to bypass gates. Input text is always supplied separately
   from editable instruction text, with a fixed runtime-owned rendering template.
5. Candidate surfaces are restricted to supported instruction text. Other Harness2
   surfaces (scripts, plugins, tools, subagents, guardrails) cannot be enabled by
   a candidate. Do not represent ignored components as effective changes.
6. Preserve Harness2's separation between selection and grading: the proposer and
   selector receive execution evidence without expected answers, grading rules or
   scores. Grade only after selection is committed. Keep all held-out cases outside
   optimization inputs and memory.
7. Keep each campaign in a separate artifact root and database. Record task IDs,
   runtime run IDs, instruction hashes, actual backend/model, sampling parameters,
   both checkout revisions and dirty-tree content digests. A revision alone does
   not identify either current checkout. Resume refuses changed execution identity.
8. No automatic tool approval, fallback, backend swap, live service configuration
   change, or deployment of optimized instructions. An optimized artifact remains
   experimental until explicitly promoted.

DeepSeek Flash is both optimizer and execution backend for phase one. Implement
an authenticated hosted backend with provider-appropriate readiness checks,
explicitly selected for this experiment; retain the existing local backend default.
Record the served model ID and catalog metadata at each campaign boundary.
xLlama is phase two, with a capable hosted proposer and a fixed local execution
model. Do not contact or swap the Xbox model in phase one. API compatibility
alone is not provider readiness.

## Validation before any improvement claim

- Unit tests with an independent fake runtime verify request mapping, terminal
  failures, awaiting-approval handling, unchanged contract gates, and resume identity.
- An explicit live canary runs a bounded task with the declared backend and captures
  a recorded runtime result. No device/service is contacted during design work.
- Baseline and candidate use the same task inputs, backend, sampling and budgets;
  report tokens, failures, latency and request counts separately from quality.
- Freeze the experiment protocol before running it. Existing dev cases remain dev;
  held-out data is not reused for tuning. A canary success is not an improvement claim.

## Consequences

This preserves a small deterministic runtime and puts recursive optimization in
an optional external workflow. It requires an adapter and a declared instruction
surface; configuring a URL is insufficient. The first slice requires a typed instruction seam, an authenticated hosted
backend, and the experiment adapter. Those changes need a new runtime ADR;
accepted runtime ADRs are not rewritten.
A chat/TUI can later consume a promoted artifact through `/runs`, but is a separate
product interface and is not delivered by this integration.

## Alternatives

- Embed Harness2 in the Conductor: rejected because optimization and privileged
  runtime execution would share ownership and dependencies.
- Route OpenCode directly to agent-runtime as an OpenAI server: unsupported by the
  current API and would not preserve typed task/approval semantics by itself.
- Run OpenCode as a privileged runtime tool: rejected for this scope; it requires
  a general execution gateway and sandbox policy beyond the accepted runtime ADRs.
- Only point agent-runtime at DeepSeek: useful provider work, but does not add
  recursive harness optimization or its evidence/selection workflow.

## First experiment: extract_contact

This is a pilot, not a powered claim of a small improvement. Before the first
experimental inference, commit an executable protocol and fixed fixtures
separately from run artifacts. The protocol must pin the following:

- Synthetic development inputs containing missing fields, clearly defined
  ambiguity policies and instructions embedded in the source text. Define the
  expected name/email/phone and normalization rules independently of candidates.
  Do not use customer data. Freeze case counts, IDs, order, clusters and hashes.
- Three comparisons on identical inputs: the existing instruction, Harness2
  `k=1`, and a fixed-instruction repeated-inference baseline with a declared
  evidence-only selection rule and comparable execution budget. Measure actual
  calls and tokens; do not describe call-count matching as equal compute. Count
  proposer, probe, composer, selector, repair and reflection calls separately.
- Fixed solver model, sampling, token ceilings, timeout, retry policy and total
  campaign spend cap across arms. Record optimizer overhead separately from
  execution cost and the later cost of using a frozen instruction.
- Per-field correctness and exact-record accuracy, unsupported non-null fields,
  missing-field null accuracy, raw first-attempt schema validity, final contract
  rejection, repair attempts, backend failures, tokens and latency. The current
  extraction contract validates structure/email shape, not factual grounding.
  Its unchanged checks are not a factual correctness oracle. If first-attempt
  output is not currently retained, add experiment-scoped capture rather than
  infer first-attempt validity from the final repaired result.
- Selection sees no gold fields or correctness scores. Seal an evaluation set
  and do not disclose its inputs to the optimizer. After optimizing on development
  tasks, freeze one instruction artifact by a preregistered rule and evaluate
  it on the new cases without per-task adaptation or reflection.
- Keep all existing 87 dev cases as a regression control, not fresh held-out
  evidence. The extraction override must not affect classify or tool-call tasks.
  Preserve existing held-out turn cases; do not read them while tuning.
- Report paired changes, discordant cases and uncertainty; account for shared
  input-template clusters. Define inconclusive/saturated outcomes and stop rules
  before observing results. No automatic prompt promotion based on a pilot.

VM/isolation setup is an explicit prerequisite to the experimental campaign.
The optimizer receives synthetic task evidence and a narrow artifact workspace;
it does not receive the runtime database, device credentials or a tool approval
channel. The hosted backend receives only synthetic experiment inputs.
