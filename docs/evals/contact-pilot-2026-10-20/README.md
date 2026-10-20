# Released contact pilot evidence — 2026-10-20

Outcome: original instruction 36/36 exact records; frozen candidate 28/36.
The candidate was not promoted. See the [full report](../../../experiments/contact/RESULTS-2026-10-20-v2.md).

From the repository root, verify without credentials, network or model calls:

```bash
python scripts/contact/verify_results.py
```

The verifier uses independent JSON/field comparisons, checks all bundle hashes,
recomputes selected outcomes and majority choices from the 276 compact execution
records, checks the 84 unchanged non-extraction request hashes, and recomputes
all 1,062 monetary liabilities. It imports neither the runtime validator nor the
report's grading helper. Unit tests reject an altered quality claim even if the
attacker also updates the file checksum.

- `systemprompt.md`, `freeze.json`: the unmodified frozen candidate and identity.
- `heldout-inputs.json`, `heldout-gold.json`, `heldout-manifest.json`: cases generated
  after freeze, before inspecting the candidate text or responses. They are now
  released evaluation data and must not be reused as fresh held-out evidence.
- `dev-gold.json`: original preregistered oracle, released only after selection.
- `executions.json`, `selection-index.json`, `quality.json`: compact raw completions,
  final results, selections, field/schema metrics and clustered paired differences.
  `original_checksums` refer to files in the full local archive, not compact exports.
- `regression*.json`: 87-case control reports and hashes of first inference messages.
- `accounting.json`, `dollar-budget.json`, `original-budget.json`: totals, the full
  credential-free receipt ledger and its immutable pre-migration predecessor.
- `provenance.json`, `provider-package-lock.json`: actual catalog, guest identities,
  source-byte parity and exact provider dependencies.

All data is synthetic. Upstream API credentials, temporary gateway tokens,
databases and unredacted session workspaces are excluded. Monetary usage is not
an independently verified invoice. Only 251 of 339 proposer-substrate calls have
attributable CLI step events; all calls remain included in accounting.

Keep this post-evaluation directory and `scripts/contact/` out of optimizer VM
source snapshots. The optimizer needs only implementation packages, the pinned
protocol and public development inputs; it must not receive gold or released
post-selection evidence. Full raw archives remain local under `runs/contact-pilot/`.
