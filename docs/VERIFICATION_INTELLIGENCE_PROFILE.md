# Verification Intelligence producer profile

`verification-intelligence/1` is an opt-in, pre-signing profile for
`AuditedTraceAssuranceEngine` and `assurance-trace-audit evaluate`. It addresses
the two incompatibilities reproduced in Verification Intelligence PR #45:
prefixed signed version labels and producer-selected run IDs. The default legacy
profile remains unchanged. No existing manifest, policy, schema or signed record
is rewritten, and the attestation wire schema remains `agent-trace-attestation/1.2.0`.

## Contract

- Set `consumer_profile="verification-intelligence/1"` on the engine.
- Pass `run_id="<operator-approved-run>"` to `evaluate`; the ID is preserved
  exactly in the audit record, signature and capture. The portable ID format is
  1–256 ASCII letters/digits plus `.`, `_`, `:` and `-`, starting with a letter or
  digit. Missing, empty and malformed IDs are rejected, never replaced with UUIDs.
- Configure a concrete checker, manifest, schema and policy, a full 40-character
  source commit, and an independently enrolled signing identity/key. Only the
  concrete built-in base checker is supported by this profile. Caller-supplied
  commit identity still requires independent checkout verification by the operator.
- Versions must be numeric `X.Y.Z` or exactly `agent-trace-checks/X.Y.Z`, with no
  prerelease suffix, leading zero, whitespace, alternative namespace or oversized
  component. Both configured and manifest identities are validated before
  conversion. Signed version fields contain numeric `X.Y.Z`; original labels
  remain in the audit and digest-bound configuration. Anti-rollback compares
  validated numeric components before signing.
- The nonempty required-check list must be unique and supported by the actual
  base checker. Other control families listed in the manifest are not implicitly
  certified. A failed schema, causal or replay check cannot produce signed PASS
  under this profile.

The producer rejects an already recorded run ID in the same audit store as a
convenience check. This is not a cross-process atomic replay service. The
consumer's protected transactional ledger and operator approval remain necessary.
Fresh IDs do not themselves constitute authorization.

## Captured artifacts

Pass `capture_directory=<new-directory>` (CLI: `--capture-directory`). The
directory must not exist. The producer snapshots concrete file bytes before
evaluation, evaluates a JSON snapshot of the trace, and hashes the same captured
configuration/environment used for export. It does not reopen mutable files to
choose different digest values after evaluation.

The exported fields are `trace_json`, `raw_result_json`, `checker_file`,
`check_manifest_file`, `schema_file`, `policy_file`, `config_json` and
`environment_json`, plus the original `attestation.json` and a final `capture.json`
completion marker with file fingerprints. JSON artifacts use sorted compact
Unicode JSON; file artifacts preserve exact bytes. The environment includes the
producer process's actual Python, implementation, platform and machine values,
not values reconstructed on a review machine. No signing key is exported.

Snapshots are limited to 8 MiB each and 32 MiB total, with JSON depth capped at
64. Partial exports are retained for diagnosis; they must not be consumed without
the completion marker and independent digest/signature validation. The marker is
renamed into place only after its file contents have been flushed. This does not
qualify storage power-loss recovery or hostile filesystem races. Operator-owned
paths/ACLs, immutable code and input capture, source-commit validation, and secure
key custody remain prerequisites. The base-checker hash is not a measurement of
every transitive dependency; validate the complete reviewed checkout separately.

## CLI additions

Use the existing `evaluate` command with these additional arguments:

```text
--consumer-profile verification-intelligence/1
--run-id <operator-approved-run-id>
--capture-directory <new-operator-owned-directory>
```

Also supply `--check-version agent-trace-checks/6.1.0`,
`--minimum-check-version agent-trace-checks/6.1.0`, the concrete manifest/schema/
policy paths, `--signing-key`, `--signer-id` and `--git-commit`. This profile does
not generate production keys or human approvals. Capture data can be sensitive;
it is not automatically safe to publish.

## Verification and deployment limits

Sixteen focused producer tests cover run binding, signed versions, malformed
identities, rollback, artifact completeness, exact snapshot hashes, source changes,
duplicate runs, capture failure and legacy compatibility. The separate
`Verification Intelligence producer contract` workflow checks out consumer commit
`ddfa7893b6b2edca97807ba00f24ebef3ddf644a` and runs six independent integration
tests using an approved **operator-host-only** task that actually invokes the
producer CLI. It then exercises post-capture reviewer approval, successful
consumption, replay alarms, artifact substitution, signature/run tampering,
revocation and expiry. Test producer and reviewer identities are separate,
disposable keys, not production credentials or actual human review.

The workflow retains test-only captures and results for 30 days. Passing these
tests establishes bounded protocol interoperability on a public example, not
production qualification, actual agent trace completeness, all-control coverage,
OS sandboxing of the signing service, or automatic release authorization.
Verification Intelligence must review/pin the merged producer commit and rerun
its qualification/deployment gates before retiring the historical blocked probe.
