# CHITRA v1.3.13
**consent-vault — the last stub, built**

> **Date**: 17 August 2026 · 84 service tests · ten gates green
> Five of five v1.2.2 §2 cross-cutting services now exist.

## §1 CONSENT IS BOUND, NOT PRESENT

The stub answered one question: does a row exist. That is not a consent check, and three of the highest-penalty rules in the set depended on it.

A record now carries a purpose, a channel, a consent type and an expiry, and every lookup is bound against them. Retargeting consent does not authorise a WhatsApp broadcast. Self consent does not cover a minor. A record that was valid when written and has since lapsed reads as expired, computed at read time, because nothing sweeps the file.

Withdrawal is a state, not a deletion. DPDP gives a right to withdraw and a separate right to erase, and collapsing them destroys the record that consent was given and then taken back, which is what a Board inquiry asks about.

## §2 THE VAULT MUST NOT BE THE BREACH

Identifiers are stored as SHA-256 only. A consent vault holding a million raw phone numbers is itself the breach it exists to prevent, and DPDP does not exempt the compliance system from DPDP. `hash_identifier()` normalises before digesting so the same number in two formats resolves to one record, and `lookup()` strips any raw identifier field as defence in depth. A test scans the records for `phone`, `email`, `aadhaar`, `msisdn` and `account_number` and fails the build on any of them.

## §3 FAIL-CLOSED, AND ONE STEP FURTHER THAN THE REST OF THE SYSTEM

Every other service dependency returns INCONCLUSIVE when it cannot answer, which routes to human review and blocks the pass. That is fail-closed and it is right for trademark clearance: a reviewer can go and read the register.

The three consent rules **block outright instead**. A reviewer looking at unverifiable consent cannot conjure consent that may never have been given. Routing it to a queue offers a decision nobody is entitled to make, and a queue under pressure will make it. The suggested fix says so in as many words: *this does not go to human review, a reviewer cannot supply consent that was never given.*

This applies to both failure shapes, tested separately: no vault configured, and a vault that raises `ConsentUnavailable` mid-call. The vault distinguishes "no consent on record" from "cannot say", because a caller must be able to tell a verified absence from an unverified anything, but both block.

## §4 A DEFECT THE STUBS WERE HIDING

Replacing the stub broke five tests across three suites, all with the same error: the stubs implemented `lookup` and not `is_authorised`. They had been passing tests that the production path would fail.

The fix was not to add the method to five stubs. All of them now use the real `ConsentVault` seeded with test records, including an empty one where every lookup is a verified absence. A stub that outlives the service it stands in for stops being a test double and starts being a second implementation that nothing checks.

## §5 STATE

| Service | Status |
|---|---|
| `rule-registry` | built |
| `credential-registry` | built |
| `legal-precheck` | built |
| `audit-sink` | built |
| `consent-vault` | **built** |
| `secret-vault` | not built |
| `cost-accounting` | not built |

`secret-vault` and `cost-accounting` are deployment concerns rather than gate logic: one holds credentials the runtime needs, the other meters spend. Neither gates an artifact.
