# Agent Trace Assurance V5 — Evaluation and Check-Update Audit Trail

V5 adds an append-only logical audit chain around Agent Trace Assurance without changing the deterministic V4 property semantics.

## Evaluation records

Every run through `AuditedTraceAssuranceEngine` records:

- unique `run_id`,
- SHA-256 trace fingerprint rather than a duplicate raw trace,
- event count,
- check-set version and fingerprint,
- event-schema version,
- policy version,
- PASS / FAIL / INCONCLUSIVE result,
- violations with property name and event index,
- covered and uncovered properties,
- UTC record time,
- sequence number,
- previous-record hash, and
- current-record hash.

Example:

```bash
assurance-trace-audit \
  --audit-log artifacts/trace-audit/audit.jsonl \
  evaluate examples/agent_trace.json \
  --check-version agent-trace-checks/5.0.0
```

## Check-update records

The same chain records check/schema/policy changes. An update includes:

- from/to versions,
- change type,
- rationale,
- source field issue or evaluation run where available,
- checks added/removed/modified,
- schema and policy updates,
- proposer,
- approver, and
- lifecycle status.

An `APPROVED` update requires a named approver different from the proposer.

```bash
assurance-trace-audit \
  --audit-log artifacts/trace-audit/audit.jsonl \
  check-update examples/check_update.json
```

This makes it possible to answer questions such as:

- Which check version evaluated this trace?
- Which field issue motivated a check change?
- Which evaluation run exposed the gap?
- Who proposed and approved the update?
- Did a later run use the updated check set?

## Integrity verification

```bash
assurance-trace-audit \
  --audit-log artifacts/trace-audit/audit.jsonl \
  verify
```

Verification checks sequence continuity, `previous_hash` linkage, and each record's canonical SHA-256 hash. A modified, deleted/reordered-without-rechaining, or corrupted record makes verification fail at the first inconsistent position.

## Trust boundary

This is **tamper-evident logical chaining**, not a claim of tamper-proof storage. An actor with write access to the entire file and implementation could rebuild the chain. Production deployment should anchor records in an independently protected system such as signed attestations, WORM/object-lock storage, a transparency log, or an external audit service.

The audit trail also records the declared check/schema/policy versions; it does not by itself prove that a deployed binary actually corresponds to those identifiers. A later milestone should bind versions to signed artifacts or release digests.

## Relationship to field-issue feedback

The audit structure is designed for the closed-loop assurance workflow:

`field issue → failing/escaped evaluation → proposed check update → independent approval → updated evaluation → regression evidence`

`source_issue` and `source_evaluation_run` fields provide explicit provenance between operational feedback and check evolution.
