# ADR-0002: Correct the API description in ADR-0001

Status: Accepted factual correction, 2026-10-20; supersedes the API-absence claim
in ADR-0001. The integration decision is unchanged.

## Context

Further inspection of agent-runtime/api.py found a GET/POST `/v1/{path:path}`
pass-through in the current dirty checkout. ADR-0001 incorrectly described the
absence of a general Chat Completions service. A revision alone did not identify
that checkout's current API; the effective source must be inspected.

## Decision

Record that the raw OpenAI pass-through exists and shares the inference slot,
but does not create recorded runs or apply typed task contracts. It is therefore
unsuitable as the execution path for the accepted contact experiment. Continue
to use the Conductor with typed requests, or its `/runs` endpoint. This correction
does not authorize bypassing validation or changing approval policy.

## Consequences

The adapter does not depend on the raw proxy. Hosted provider authentication must
be consistent in generation, readiness and any explicit raw proxy calls, while
credentials remain operator configuration and are never forwarded from task data.

## Alternatives

Treating endpoint compatibility as equivalent to contract-preserving execution
would invalidate the experiment and is rejected.
