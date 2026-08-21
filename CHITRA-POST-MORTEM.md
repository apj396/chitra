# Building a Compliance Engine, and What Executing It Found

**A post-mortem on CHITRA, 12 to 20 August 2026**
Adwait · Shreejan Labs

---

## Summary

CHITRA is a nine-agent AI pipeline for the Indian advertising industry, specified across ten documents in May 2026. In August I ran a skeptical-reader audit of that specification, built the compliance substrate underneath it, and drove one campaign end to end against a live model.

The specification had been reviewed repeatedly and declared complete three separate times. On execution it was found to contain:

- **22 of 33 compliance rules that could not load into the registry that governs them**, failing open, while the system reported the checks as run
- **279 rule-to-artifact field references to fields no schema defines**, causing three rules to be structurally incapable of failing
- **two artifact types with zero compliance coverage**, one of them the artifact carrying every headline and script in a campaign
- **a rule permitting advertising that is a criminal offence** under an Act in force for seven months before the specification's own knowledge horizon
- **an audit ledger recording compliance checks that never ran**
- **a test suite writing fixtures into the production audit trail it existed to verify**

None of these was caught by human review. Every one was caught by execution, or by a mechanical check that runs on every commit.

The finished substrate: 43 rules, 35 genuinely enforcing, 371 tests across 8 suites, 11 gates, 5 backing services, an append-only hash-chained ledger, and a campaign of record cleared by a named human reviewer whose signature is on the chain.

---

## 1. Why this is a security document

The advertising framing is incidental. What CHITRA needed was a policy engine that decides whether an artifact may proceed, backed by evidence a regulator would accept. That is the same problem shape as admission control, policy-as-code, and audit logging, and it fails the same ways.

The Indian regulatory surface it enforces against is genuinely adversarial in the way security controls are adversarial: the DPDP Act 2023 with penalties to ₹250 crore, the Promotion and Regulation of Online Gaming Act 2025 making certain advertising a cognisable offence, ASCI's code, and sectoral regulators for finance, insurance, pharmaceuticals, real estate and tobacco. Getting a rule wrong is not a bug report. It is a liability.

---

## 2. The defect taxonomy

Every defect found fell into one of five classes. The class matters more than the individual defect, because the class determines what kind of check catches it.

### 2.1 Fails open while reporting success

**The worst class, and the most common.**

The rule registry validated rules against a schema. Twenty-two of thirty-three failed validation — wrong ID pattern, missing required citation, source outside the enum. A rule that fails validation is absent from what the registry returns. It is not *stale*, so the stale-registry check never fired. The sanitizer then evaluated whatever loaded, reported `checks_run` listing only those, and stamped `sanitizer_pass = true`.

The system did not under-enforce quietly. It **manufactured the documentary record of enforcement** for checks that were never run. That record is precisely what a Data Protection Board inquiry would later read.

The ID pattern is the clean illustration. It admitted exactly two uppercase segments. `ASCI-DISC-001` passed. `DMRA-001` had too few. `PLATFORM-TOS-META-SPECIAL-CAT-001` had too many. The pattern was written without being run against the identifiers already in use.

**Same class, second instance.** Rules read fields like `artifact.is_surrogate`. Artifact schemas were written independently and define no such field. `get(artifact, "is_surrogate", False)` returns `False` for an alcohol artifact that never declared it, and the surrogate-advertising rule returned PASS. `claimed_conditions` absent meant the Drugs and Magic Remedies rule compared against an empty set and passed every health claim ever submitted. **These were not weak rules. They could not fail.**

**Third instance.** A convenience flag that reused a previously generated brief asserted `pass=True` with zero rules run, and wrote that assertion into the audit ledger. Three false compliance records, in the artifact built to be the accountability record.

**Mitigation.** A required-facet layer where an unresolvable field is a *miss*, not a `False`. A miss converts any PASS to INCONCLUSIVE and names the field. Silence became a question instead of an approval.

### 2.2 Two documents, each internally coherent, contradicting where nothing checked

Nineteen rules declared they applied to `verbal_deck`. No such artifact type exists; it is a sub-object inside `concept_bible`. A cross-reference matrix silently translated it when that matrix was authored, and the translation was never written back. Result: **`concept_bible` had zero applicable rules.** The artifact carrying every headline, script and visual concept in a campaign passed the sanitizer with nothing running.

The same class produced: a divergence prompt that failed on **five of five** live runs because the agent scaffold's own output section defined a different output format than the instruction appended after it; a field the methodology specifies as a 200-word sketch and the schema caps at 400 characters; and two enums for the same concept that admit different values.

**Mitigation.** Derived indexes are generated, never authored. A field census walks every rule's actual field reads against every artifact schema and fails the build on an undeclared one.

### 2.3 Stale authority

`GAMING-RMG-001` permitted real-money gaming advertising subject to an addiction warning, an age floor, and certification by a self-regulatory body. The Promotion and Regulation of Online Gaming Act 2025 came into force on 1 October 2025, prohibits that advertising outright, and abolished the self-regulatory mechanism the rule tested for. **The rule gated on a credential that cannot be issued, found no reason to block, and passed the artifact.** Publication would have been a cognisable, non-bailable offence, documented end to end in the client's name.

This was not drift. The Act was in force for seven months before the specification's own knowledge horizon.

**Mitigation.** A citation-freshness gate driven by a curator-maintained register of superseded instruments, matching on citation text only, running monthly on a schedule as well as on commit. A rule whose citation names a superseded instrument now raises a finding the way a renamed API field does.

### 2.4 Controls that cannot enforce, dressed as controls

Seven rules read a boolean the producing agent set on its own output. `RBI-BFSI-001` required `contains_apr_or_interest_disclosure == true`; nothing computed it; the agent that wrote the copy also set the flag. The agent under audit supplied the audit result.

**Mitigation.** Five became genuinely enforcing by reading the artifact's own copy instead of a claim about it, or by resolving through the service that owns the fact. A test submits an artifact whose copy contains no rate disclosure but which asserts compliance; it now fails.

Eight rules remain unenforceable by software, all judgement calls on cultural representation. Those were given a workflow rather than a fake predicate. See §4.

### 2.5 The verification destroying what it verifies

The test suite for the review tool called the production audit ledger. **68 of the first 112 ledger entries were test fixtures.** The suite built to prove the audit trail was correct was filling it with synthetic data.

An append-only ledger cannot be cleaned. The contaminated one was archived rather than deleted, and the campaign evidence rebuilt on a fresh chain.

**Mitigation.** A test asserting the production ledger's byte size is unchanged after a recording operation. A second leak surfaced in a helper after the first fix; the new test caught it.

---

## 3. Controls built

### 3.1 Four automatic gates, three drift classes

| Gate | Watches | First-run result |
|---|---|---|
| Conformance | Rules against their admission schema; citations against live law | 52 findings across 25 sites |
| Field census | Rule field reads against artifact schemas | 61 fields, 279 rule/artifact pairs |
| Compatibility sweep | Pinned vendor APIs against upstream | 11 changes, 7 tickets, 1 SLA already breached |
| Test suites | 371 tests, 8 suites | — |

The sweep was specified in May and never scheduled. In the interval Meta shipped Marketing API v26.0, Google shipped Ads API v25, Meta replaced Nielsen DMA targeting with Comscore Markets and unmigrated campaigns silently stopped delivering, and three metrics the reporting agent reads were retired. All were found by hand, months late. The sweep now finds all of them on a first run, and one ticket opens already breached because enforcement passed while nothing was watching.

**The sweep surfaced an architectural finding, not just vendor changes.** Meta's v26.0 restrictions extend to *every supported version* on a fixed date. Pinning buys roughly ninety days; it is a deferral mechanism, not an isolation mechanism. The finding schema gained an `enforcement_date_all_versions` field distinct from a sunset date, and a ticket class whose SLA counts backward from that date rather than forward from detection.

It also gained `silent_failure_mode`, because Meta *errors* on one removed placement and *silently strips* another. The second is worse and no error handler catches it. That finding's ticket carries an action no other ticket gets: add a pre-call predicate.

### 3.2 Fail-closed, calibrated per control

Not every control fails the same way, and treating them uniformly is a design error in both directions.

Most service dependencies return INCONCLUSIVE when unavailable, routing to human review. Correct for trademark clearance: a reviewer can go and read the register.

**The three consent rules block outright, with no review path.** A reviewer looking at unverifiable consent cannot conjure consent that may never have been given. Routing it to a queue offers a decision nobody is entitled to make, and a queue under pressure makes it. The suggested-fix text says so explicitly rather than leaving it implicit.

### 3.3 Hard blocks with named overrides

Two controls block by default and lift only on an override that names a person and a date.

**Research coverage.** A campaign region the audience research does not cover is denied execution. Found because a live model flagged that campaign geography listed three states while the research covered two — a multi-market allocation error caused by a misaligned human workflow, caught in 185 seconds by an agent nobody asked to look. The waiver requires an approver and a date; an unsigned waiver is itself a violation, with the message *a waiver without a name is a compromise, not a decision.*

**Surrogate alcohol.** Prohibited by default, lifted only by a Chartered Accountant attestation resolving in the credential registry. ASCI already requires the brand-extension thresholds to be certified by an independent CA firm, so the qualifying test is a document lookup rather than a financial evaluation. The engine never parses a balance sheet.

The design principle: a hard block with no override is not stricter, it is more brittle. Business reality eventually routes around it. An override that requires a signature converts a technical barrier into an accountability ledger.

### 3.4 The ledger

Append-only JSONL, hash-chained over a canonical serialisation. Tested against three attacks: flipping a verdict from fail to pass, deleting an inconvenient failure, and appending a forged entry. All three are detected and the first broken sequence number is named. The runner verifies the chain *before* it appends and refuses to run on a broken one.

**Erasure was the interesting problem.** Append-only and a right to erasure are in tension, and the obvious resolution is wrong: deleting the record destroys the evidence that the erasure was honoured, which is the artefact the regulator actually wants. So erasure is redaction — payload replaced, SHA-256 of the original retained, authorisation reference and timestamp recorded, chain recomputed so it still verifies. The redaction is itself an entry.

**Stated limit.** The ledger is a local file. A hash chain proves tampering occurred; it does not prevent an actor with write access rebuilding the whole file. Countersigning to append-only external storage is the standard mitigation and was not implemented.

---

## 4. Where a human is the control, and why

Eight rules cannot be enforced by software: five on cultural representation, plus dark patterns, greenwashing and educational advertising. These are judgement calls on meaning.

**I declined to build a classifier for the cultural rules**, and the reasoning is the part of this project I would most want discussed.

The proposal on the table was a per-project AI persona carrying the caste, religious, gender and regional perspectives a campaign required. I argued against it: a persona representing a community is a synthetic stand-in for people not in the room, and a confidence score attached to it reads as consultation when none occurred. When it is wrong, the record says a perspective was consulted, which is worse than no record. It also contradicted a decision made minutes earlier to ground the same thresholds in real published rulings rather than synthetic approximations.

What shipped instead is an **evidence assembler**: it identifies which axes a concept touches, pulls the register entries and precedent, and drafts the reviewer's brief. It adopts no perspective, issues no verdict, and returns `verdict: null` by construction. It cuts the reviewer's work from assessing cold to checking a brief, which is most of the leverage and none of the authority.

Scoping made it affordable. Audits attach to the **concept**, not the campaign and not the asset. Per campaign is too coarse — one campaign carries concepts with entirely different cultural surfaces. Per asset is too fine — twenty resizes of one approved key visual carry one risk between them. Derived artifacts inherit, and inheritance breaks when the artifact introduces new talent, language, setting or festival reference. A Tamil dub of an approved film is not the approved film.

### 4.1 What the human found that no gate did

The reviewer caught three defects during the first real review session.

**Substring matching.** The marker scanner matched `om` inside *from*, *some*, *comfort* and *custom*, and `figure` inside *figures out*. Two clean concepts were routed to religious and gender review on syllables.

**Self-referential contamination.** After the whole-word fix, two concepts still surfaced a gender axis. The scanner was reading the entire concept JSON, including a metadata block containing **the assistant's own question** — *"religious symbol, practice or figure in a commercial or comic frame"*. The tool was reading its own output back as evidence, and it would have compounded every cycle.

**The contaminated ledger.** Found by querying the audit trail and noticing 68 entries under a name that was not his.

A reviewer who cannot be bothered would have graded five concepts low and moved on. The system would have cleared and the defects would have shipped. **The control is a person paying attention, and the tooling exists to make that attention affordable, not to replace it.**

---

## 5. Governance

Twenty architectural decisions are recorded with the reasoning as given, including three where a position changed under argument and one where I was overruled and the decision stands. A decision log that only records agreement is a press release.

The register also carries live caveats rather than burying them: a regulatory schedule compiled from secondary sources and marked `verified: false`, with its rule held in shadow mode until Gazette-checked; a personality-rights rule that enforces on declared subjects only, with the residual gap written into the code where the next reader will find it; and an unexplained API anomaly recorded as open rather than guessed at.

---

## 6. Result

One campaign, generated by two agents, blocked by the compliance engine on a gate no software could clear, escalated to a named human, reviewed across five axes, and released on that signature.

The evidence chain is six entries: five cultural reviews under the reviewer's name with per-axis grades, then one sanitizer verdict recording `pass=true` across eight rules. The chain verifies.

**What is not built**, because a post-mortem that omits it is marketing: seven of nine agents; the entire evaluation harness, which was specified in the document the version number belongs to; multi-tenant isolation, replication and write-access control on the ledger; and a classifier for the eight judgement rules, deliberately.

---

## 7. What I would carry into a security team

**Reviewing a specification is not verifying it.** Ten documents, three completeness declarations, and 52 conformance findings on the first mechanical check. The finding that mattered most — a rule authorising a criminal offence — required reading one rule against one statute, and no human did it in three months.

**Fail-open is the default failure mode of policy engines, and it looks like success.** Every serious defect here reported green. The pattern to look for is not "did the check fail" but "did the check run, and on what."

**Calibrate fail-closed per control.** Uniform strictness produces queues nobody reads; uniform leniency produces the first class of defect. The question is whether a human receiving this exception can actually resolve it.

**A hard block with no override is brittle.** Signed overrides convert barriers into accountability, and the signature is the control.

**Test doubles that outlive their service become a second implementation nothing checks.** Replacing one stub here broke five tests that had been passing while the production path would have failed.

**Instrument your own tooling first.** I spent two rounds guessing at a failure because my API client discarded `stop_reason`, token usage and the error body. Three defects were invisible until the client kept what the API was already telling it.

---

## Verify it yourself

Every figure in this document is reproducible on your machine in three commands, with no API key, no network and no account.

```bash
git clone https://github.com/apj396/chitra.git
cd chitra && pip install -r requirements.txt
python verify_all.py
```

Two seconds. Eleven gates, 371 tests, one dependency.

The repository contains the specification documents, the rules as executable code, the audit ledger implementation, the twenty architectural decisions with their reasoning, and the gates that found everything in §2. To watch a gate fail on purpose, empty any `citation` field in `chitra_rules.json` and run it again: the registry rejects wholesale rather than loading the subset that parsed, because partial load is exactly what turned a schema error into silent under-enforcement.

**github.com/apj396/chitra**
