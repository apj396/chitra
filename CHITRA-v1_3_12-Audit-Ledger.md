# CHITRA v1.3.12
**The audit ledger — `audit-sink`, built**

> **Date**: 17 August 2026 · 34 tests · ten gates green
> Specified in v1.2.2 §2 as one of five cross-cutting services. It was the one that made "deeply auditable" true rather than aspirational, and it did not exist.

## §1 WHAT WAS ACTUALLY WRONG

Every compliance verdict the system produced landed in a JSON file in a timestamped run folder. That is a record of the last run, not an audit trail. It did not accumulate across campaigns, it could not be searched, and nothing detected a deleted or edited entry.

`DPDP-RETENTION-001` checked retention values against a policy no system held. The HITL router computed queues and SLAs that were written nowhere. Waivers under ADR-020 named an approver and a date, and then the name went into a file that the next run ignored. An accountability ledger with no ledger is a promise.

## §2 HASH-CHAINED, APPEND-ONLY

JSONL, one entry per line. Each entry carries the hash of the entry before it, computed over a canonical serialisation so the same content always hashes the same. Removing, editing or reordering any entry breaks the chain from that point, and `verify()` names the first sequence number that does not hold and says which failure it is.

Tested against three attacks: flipping a verdict from `pass: false` to `pass: true`, deleting an inconvenient failure, and appending a forged entry with fabricated hashes. All three are detected and located.

`run_slice` verifies the chain before it appends and refuses to run on a broken ledger. Discovering tampering after adding to it is worse than not running.

## §3 WHAT IT RECORDS

| Event | Carries |
|---|---|
| `artifact.sanitized` | verdict, rules run, violations, warnings, inconclusive, review flag |
| `artifact.refused` | the refusal and its reason |
| `agent.halted` | a clarification halt and what was missing |
| `waiver.recorded` | the waiver, its approver and its date |
| `hitl.routed` | queue, SLA, the rules that put it there |
| `check.unverifiable` | which check could not run and why |
| `retention.redacted` | a redaction and its authorisation |

Event types are a closed set. `append()` refuses an unknown one, so a future agent cannot invent `artifact.quietly_approved` and have it accepted.

## §4 ERASURE WITHOUT DESTROYING THE PROOF

An append-only store and a right to erasure are in tension, and the obvious resolution is wrong. Deleting the line destroys the evidence that the erasure was honoured, which is the artefact the Data Protection Board actually wants to see.

So erasure is redaction. The payload is replaced with a marker; the SHA-256 of the original payload, the reason, the authorisation reference and the redaction timestamp are retained; and the chain is recomputed so it still verifies. The entry proves something was there, that it was removed, by whose authority and when, without retaining the content. The redaction is itself an entry.

Redaction requires an authorisation reference. Redacting an already-redacted entry is refused.

## §5 THE QUESTION IT HAS TO ANSWER

```
python chitra_audit.py query --unverifiable
python chitra_audit.py query --event waiver.recorded
```

Which artifacts shipped with a check that could not run, and who signed the waiver. That is the question a DPBI auditor asks, and it now answers in one command against the whole history rather than by opening run folders.

Also available: by campaign, by artifact type, by agent, by rule across every event shape, by time window, blocked-only, needs-review-only, and a retention sweep against the tenant policy.

## §6 WHAT THIS DOES AND DOES NOT CLOSE

**Closes**: the gap between the compliance record being produced and the compliance record being kept. `DPDP-RETENTION-001` now has a store to check. ADR-020's waivers now land somewhere permanent.

**Does not close**: the ledger is a local file. Multi-tenant isolation, offsite replication, and write access control are deployment concerns and are not addressed here. A hash chain proves tampering happened; it does not prevent someone with write access from rebuilding the whole file. Countersigning to an external store is the next step and is not taken.

Four of five v1.2.2 §2 services now exist: `rule-registry`, `credential-registry`, `legal-precheck` and `audit-sink`. `consent-vault` remains a test stub; `secret-vault` and `cost-accounting` remain unbuilt.
