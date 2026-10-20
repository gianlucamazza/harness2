# Contact extraction regression fixtures v1

44 cases: the 36 released pilot cases, plus eight explicit primary-contact,
ambiguity, missing-field and source-injection cases. `manifest.json` pins inputs
and independent expected nullable strings. These are regression data, not sealed
evaluation data. Never copy this directory into optimizer snapshots.

Run `python scripts/contact/check_regressions.py` to verify fixtures without model
calls. Pass `--executions recorded.json` to grade exactly one recorded execution
per case. The checker uses expected values directly, independently of candidate
instructions and runtime validators. Its raw-object diagnostic checks shape and
types, not the runtime's email validation or factual correctness.

Fixture/oracle tests and fake-runtime adoption tests are software verification.
They do not constitute a live-model pass on these 44 inputs.
