# ADR-0004 canary evidence

One original-instruction extraction, not a new optimization or quality study.
See [the report](../../../experiments/contact/FOLLOWUP-RESULTS-2026-10-20.md).

`SHA256SUMS.json` pins the files in this directory. `accounting.json` adds one
receipt to the preserved historical ledger in `../contact-pilot-2026-10-20/`.
`gateway-requests.json` links both readiness and generation to one caller-owned
execution. The runtime source inventory, campaign identity, adoption decision,
raw attempts/result and budget preflights make the canary inspectable offline.

Run `python scripts/contact/verify_followup.py`. It checks answer and accounting
independently of the changed adapter/runtime code; no credentials or model calls
are needed. A green check verifies this recorded canary, not a general benefit.
