# CHITRA ARCHITECTURAL DECISION RECORD

**Register opened**: 12 August 2026
**Decisions**: 19, all resolved
**Owner**: Adwait, Shreejan Labs

Each entry records the decision, who made it, the reasoning as given, and what changed in the system. Where I disagreed and was overruled, or disagreed and was upheld, the register says so, because a decision log that only records agreement is a press release.

---

## P0 — blocked a first live tenant

### ADR-001 — Cultural review: evidence assembler, no persona
**Decision**: One named internal reviewer with escalation to external counsel, assisted by an evidence assembler. No AI persona representing a community.
**Path taken**: The first proposal was a project-scoped persona anchored to the caste, religious, gender and regional perspectives a project required. I pushed back: a persona representing a community is a synthetic stand-in for people not in the room, and a confidence score attached to it reads as consultation when none happened. It also contradicted ADR-002, which chose real rulings over synthetic approximations. Accepted.
**What ships**: `chitra_cultural_assistant.py`. It identifies which axes a concept touches, pulls register entries and precedent, and drafts the reviewer's brief. It does not adopt a perspective, issue a risk level, or recommend approval. `to_dict()` returns `verdict: null` by construction.
**Perspective supply**: concept-scoped audits (ADR from v1.3.5) make a small paid per-axis roster affordable, called only when a concept touches that axis.

### ADR-002 — Escalation semantics drafted from real ASCI rulings
**Decision**: I draft a first pass per axis from the ASCI code and published complaint rulings; Adwait edits and owns the final text.
**Reasoning as given**: grounding logic gates in reality, not synthetic approximations. Extracting core principles from actual rulings defines the hard legal parameters.
**Status**: assembler prompts per axis are in place; the graded thresholds await ADR-001's named reviewer.

### ADR-003 — Sexual orientation: prohibited outright, recited
**Decision**: Remove the LGBTQ-affirmative carve-out. Forbid the basis.
**Correction on the record**: the original rationale cited DPDP's strict stance on sensitive personal data. DPDP 2023 deliberately dropped the sensitive-data classification the old SPDI Rules carried and treats personal data uniformly, with special provisions only for children and persons with disabilities. Adwait accepted the correction.
**Rationale as recorded**: (1) rules-engine integrity — a carve-out on self-declared brand posture is the self-certification pattern v1.3.4 stripped everywhere else; (2) platform ToS subservience — Meta and Google prohibit orientation-based targeting, so a locally passed asset fails at the network API anyway.
**Changed**: `DPDP-SENSITIVE-TARGETING-001` carve-outs removed for both orientation and health condition; citation moves off DPDP for this limb.

### ADR-004 — Provision model access now
**Decision**: Provision `ANTHROPIC_API_KEY` and run Drishti against real briefs.
**Reasoning as given**: deterministic stability at the unit level must precede orchestration-level testing; running the foundational node early isolates bugs before they multiply.

### ADR-005 — Vertical slice, compliance engine as the story
**Decision**: Build Drishti, Disha and the sanitizer to a real campaign end to end. Frame the work as a compliance engine.
**Reasoning as given**: the compliance substrate is the strongest and most unusual part; a working slice demonstrates it, eight agents mostly demonstrate persistence.

---

## P1 — blocked correctness or operations within weeks

### ADR-006 — Build `credential-registry`
**Decision**: Minimal file-backed lookup service.
**Reasoning as given**: inconclusive results force mandatory human routing, so accepting human review permanently breaks automated processing for every qualification-dependent asset.
**What ships**: `chitra_services.CredentialRegistry`, `credentials.json`, two families — `qualification` and `ca_attestation`.

### ADR-007 — HITL routing split by rule source
**Decision**: Route by payload metadata, not one queue.
**Reasoning as given**: DPDP consent failures must hit the DPO immediately, leaving the cultural panel to linguistic, regional and demographic risk.
**What ships**: `chitra_services.HITLRouter`. Six queues with distinct SLAs: DPO 4h, ad ops 8h, legal 24h, compliance 24h, brand owner 24h, cultural review 48h. Items sort tightest-SLA-first so the DPO queue is not buried behind typography.

### ADR-008 — Gates run in CI on a schedule
**Decision**: GitHub Actions on push, plus a scheduled monthly run.
**Reasoning**: the compatibility sweep and citation-freshness check need a schedule, not a hook. A hook only fires when you happen to be working.

### ADR-009 — Content API for Shopping: defer, recorded
**Decision**: Do not migrate before the 18 August sunset.
**Reasoning as given**: servicing an API update for an unused feature set days before a deadline creates negative operational yield.
**Recorded so it is a decision rather than an oversight.** Revisit when a tenant has Shopping inventory.

### ADR-010 — DMRA Schedule transcribed in-house
**Decision**: Transcribe rather than license a regulatory feed.
**Reasoning as given**: commercial feeds are designed for volatile environments, not a static schedule from 1954; transcription keeps the platform self-contained and dependency-free.
**What ships**: `dmra_schedule.json`, 54 conditions plus synonym expansion and the four section 3 prohibitions, 97 match terms total. `DMRA-001` now matches the copy as well as any declared list, so a caption claiming to cure diabetes is caught whether or not the agent declared it.
**Caveat on the record**: the India Code PDF was not retrievable at compile time, so the list is compiled from the India Code text cross-checked against two secondary sources. `verified: false`, and `DMRA-001` stays in shadow mode until a curator checks it against the Gazette.

### ADR-011 — Judge panel: verify pins, re-select only on failure
**Decision**: Health check before any calibration run; targeted re-selection only if an endpoint fails.
**Reasoning as given**: in evaluation environments stability supersedes novelty; changing panel models invalidates prior benchmarks and forces full rubric recalibration.
**What ships**: `chitra_eval_extras.JudgePanelHealthCheck`. `gate()` refuses to run with no prober configured, refuses on any unavailable model, and refuses if the panel spans fewer than three model families, which is the self-enhancement guard.

---

## P2 — quality and scope

### ADR-012 — Diwali 2026 locked to 8 November
**Decision**: 8 November 2026, Kartik Amavasya, Pradosh Kaal evening window. The 20 October conflict is discarded as a Dussehra conflation.
**Addition**: the resource pack stores the five-day window, Dhanteras 6 November to Bhai Dooj 10 November, not the single day, because media planning runs on the window. One panchang places Kartik Amavasya on 9 November on the tithi boundary, which the Pradosh Kaal reasoning resolves.

### ADR-013 — Alcohol: block by default, CA attestation override
**Decision**: Hard block on alcohol-adjacent categories, lifted only by a `ca_attestation_id` that resolves in the credential registry.
**Path taken**: the initial choice was outright prohibition, on the ground that automating ASCI's financial criteria inside a creative classifier is an architectural mismatch. That reasoning is right. But ASCI requires the brand-extension evidence to be certified by an independent CA firm, which makes the qualifying test a document lookup rather than a financial evaluation. Adwait moved to the override on seeing that.
**Verified thresholds**: net sales turnover of Rs 20 lakh per month, fixed asset investment of not less than Rs 10 crore, ad spend capped at 200% of turnover in years one and two, 100% in year three, 50% in year four, 30% thereafter.
**What ships**: `ALCOHOL-SURROGATE-001` rewritten. CHITRA never parses a balance sheet. A valid attestation does not license consumption imagery, which is separately tested.

### ADR-014 — Schema minimums kept, and instrumented
**Decision**: Keep the minimums (15 headlines, 10 to 15 mood board frames) as a forcing function. **I recommended relaxing them and was overruled.**
**Reasoning as given**: for a portfolio piece or sellable product the output must be undeniably creative, not adequate; minimums are a prompt-engineering forcing function and the latency cost is justified.
**Instrumentation agreed**: measure whether the forcing function works. `chitra_eval_extras.HeadlineVarianceScorer` scores lexical spread, near-duplicate pairs and structural clustering across the array. Measured locally rather than judged, so it cannot drift with a model version. On test data it separates cleanly: a padded array of 15 scores `weak` at 0.761 mean similarity with 96 near-duplicate pairs; a genuinely varied array scores `excellent` at 0.044 with none.

### ADR-015 — Backfill as a linked follow-up record
**Decision**: Append a correlation-linked record rather than mutating the log entry.
**Reasoning as given**: mutating historical entries violates core audit invariants; appending preserves immutability while retaining closed-loop telemetry.

### ADR-016 — Predictive validity deferred to three campaigns
**Decision**: Defer explicitly. It cannot be answered without outcome data.

### ADR-017 — Minor-platform specs deferred
**Decision**: Defer until a client asks. v1.3.1 already said "if usage warrants" and nothing warrants it.

### ADR-018 — Orphan v1.2 rules: split
**Decision**: Codify `ip.real_person_likeness`; deprecate the Meta and Google migration rules.
**Reasoning as given**: the likeness rule hardens automated legal-liability gating; the migration rules dilute focus and introduce tech debt.
**What ships**: `IP-REAL-PERSON-LIKENESS-001`, blocking, routed to the legal queue by ADR-007. Distinct from `IP-COPYRIGHT-001`'s celebrity contract test, which covers contracted talent; this covers any identifiable real person, with a narrow public-figure-in-editorial-context exception.
**Deprecated**: the Meta and Google migration rules are dropped. The compatibility sweep is the right mechanism for that class, and both were already stale.
**Residual gap, recorded**: the rule enforces on declared people only. Making the field required was tried and reverted: it sent every artifact with no declared people to human review, which is every artifact. An undeclared face in a crowd shot is therefore not caught by the sanitizer. That is an asset-review responsibility and is written into the facet declaration so the next reader finds it there rather than discovering it in production.

### ADR-019 — Disha next
**Decision**: Build Disha before Pramaan.
**Reasoning as given**: it completes the primary execution flow and tests whether strategy converts into a creative payload the rules engine can validate.

---

## Register discipline

Three entries record a position changing under argument: ADR-001 (persona dropped), ADR-003 (conclusion held, rationale corrected), ADR-013 (prohibition upgraded to an override). One records me being overruled and the decision standing: ADR-014.

One entry carries a live caveat: ADR-010's Schedule is unverified against the Gazette, and `DMRA-001` runs in shadow mode until it is. That is tracked in `dmra_schedule.json` as `verified: false` rather than in prose here, so the code knows about it too.

---

## ADR-020 — Research coverage is an invariant, not a warning
**Date**: 16 August 2026. Raised by the first real model run, decided by Adwait.

**Decision**: A campaign region the audience research does not cover is denied execution. Tamil Nadu removed from the reference packet.

**Reasoning as given**: three options were on the table. Commissioning research is a valid business choice but an architectural dead end for a vertical slice, since it halts pipeline velocity waiting on external human operations. Accepting the untested insight is the classic agency compromise: it prioritises reach over data integrity and introduces a known vulnerability into the strategy. Denial is the zero-trust choice, and if the platform is a GRC engine it must enforce hard boundaries rather than merely flag them. The architecture should actively prevent the execution of unsubstantiated logic.

**Implemented as a rule, not a check.** Disha's structural interrogation already flagged the gap, but a warning at one point in one agent is a thing someone clicks past. `CHITRA-RESEARCH-COVERAGE-001` blocks on every artifact type carrying a geography, and routes to `brand_owner`, who owns the call. Drishti also halts at preflight before any model call, because paying to write a brief for a market that cannot ship is waste rather than safety. Verified: zero model calls on an uncovered region.

**Waiver, following ADR-013's shape.** A hard block with no override makes a legitimate business decision impossible rather than accountable. `research_coverage_waivers` lifts the block only for an entry naming an approver and a date. An unsigned waiver is itself a violation, with the message "a waiver without a name is a compromise, not a decision". The difference from the agency compromise is not whether the campaign runs in Tamil Nadu; it is whether anyone's name is on it.

**Three defects found while implementing it**, each recorded because each survived review:
1. `spec_dir()` returned the first candidate that *exists* rather than the first that *contains* specification documents. The code directory always exists, so it always won.
2. That crash was masked because the calling command used `;` instead of `&&`, so a stale registry file was copied over the top and the new rule silently never loaded.
3. `geography` was first declared a required facet. The requirement is conditional — required only when geography is present — which a facet flag cannot express, and marking it required sent every artifact without a geography to human review. The condition now lives in the predicate, which returns inconclusive when a geography is declared with no coverage stated.
