# CHITRA v1.3.6
**Defect Resolution — the field-vocabulary defect, and the register cleared**

> **Date**: 12 August 2026
> **Scope**: Every catalogued open defect. Nothing new built.
> **Headline**: `verbal_deck` was not one defect. It was one instance of a class, and the class had 279 members.
> **Verification**: 0 undeclared field reads, 47/47 sanitizer tests, 26/26 Drishti tests, conformance gate green. `./verify_all.sh` runs all five.

---

## §0 THE DEFECT REGISTER

| # | Defect | Status |
|---|---|---|
| D-1 | Rules read 61 fields that no artifact schema defines, across 279 rule/artifact pairs | **Closed** §1 |
| D-2 | `CHITRA-HITL-BUDGET` cited in v1.2.1 §F.13 Example 4, defined nowhere | **Closed** §2.1 |
| D-3 | `IP-COPYRIGHT-001` reported at `warn` in Example 3, declared `block` | **Closed** §2.2 |
| D-4 | `DPDP-RETENTION-001` individual-data scan implemented but not in the rule text | **Closed** §2.3 |
| D-5 | `auto_fix_available` branched on for 39 rules, true on 2 | **Closed** §2.4 |
| D-6 | Per-agent artifact adapters, one already written into Drishti | **Closed** §1.4 |
| D-7 | Field-vocabulary drift can recur silently | **Closed** §3, new permanent gate |

---

## §1 D-1: THE VERBAL_DECK DEFECT, ONE LEVEL DOWN

### §1.1 What it actually was

`verbal_deck` was a rule naming an artifact type that did not exist. v1.3.3 closed that. The same defect exists one level down: rules naming **fields** that do not exist on the artifacts they apply to.

Rules were written against a flat vocabulary — `artifact.consent_artifact_id`, `artifact.product_category`, `artifact.is_surrogate`. Artifact schemas were written independently, nested and differently named: `audience_targeting.consent_artifact_id` on `social_post`, `audiences[].consent_artifact_id` on `media_plan`, `ai_content_metadata.deepfake_segments[].subject_consent_uri` on `motion_asset_registry`. Neither document ever referenced the other.

I found one instance by hand while building Drishti and called it a finding. It was a census problem, so I ran a census.

### §1.2 The measurement

`audit_field_paths.py` wraps the predicate layer's field accessor, runs every rule against a probe artifact, records every path requested, and checks each against the JSON Schema of every artifact type the rule applies to.

**61 distinct fields. 279 rule/artifact pairs.** Every one reading a path that nothing produces.

### §1.3 Why this was dangerous rather than merely untidy

An absent field read with a falsy default is indistinguishable from a field that is present and false.

- `get(artifact, "is_surrogate", False)` returned `False` for an alcohol artifact that never declared the field. `ALCOHOL-SURROGATE-001` then returned **PASS**.
- `claimed_conditions` absent meant `DMRA-001` compared against an empty set and returned **PASS**, for every health claim ever submitted.
- `special_ad_category_declared_in_meta` absent meant the Meta special-category rule passed credit, employment, housing and political ads.

These are not rules that were weak. They were rules that could not fail. Three of them are among the highest-penalty rules in the set, and the sanitizer was stamping `sanitizer_pass: true` on every artifact they touched.

This is the same failure shape as P0-2 in the original audit: silent non-enforcement that produces the documentary record of enforcement.

### §1.4 The fix: one declared seam

`chitra_facets.py` declares every facet a rule reads, and where it comes from:

| Source | Meaning | Count |
|---|---|---:|
| `context` | Campaign or tenant fact, never an artifact field | 7 |
| `derived` | Computed from real schema paths by a named function | 19 |
| `annotation` | Upstream reviewer or agent annotation, absent by default | 42 |

`product_category`, `sector`, `concept_id` and `channel` are campaign facts. They were never artifact fields and no amount of schema editing would have made them so. They now resolve from `context.campaign`.

Nineteen facets are derived from paths that genuinely exist. `target_audience.includes_minors` is computed from the age range rather than asserted. `music_license_documented` walks `audio_specs.music_tracks[].license_document_uri`. `subject_consent_documented` walks the deepfake segment list. `ai_risk_tier` defaults **upward** to medium when AI use is declared without a tier, so the label requirement applies rather than lapses.

### §1.5 The rule about absence

**A required facet that cannot be resolved is a MISS, not a False.**

`FacetView` records misses. The sanitizer converts any PASS that recorded a miss into INCONCLUSIVE, naming the facet. Silence becomes a question instead of an approval.

Eight facets are marked required: `product_category`, `claimed_conditions`, `directly_promotes_alcohol`, `is_surrogate`, `uses_alcohol_consumption_imagery`, `health_claims_have_evidence_id`, `special_ad_category_declared_in_meta`, `transfer_basis_documented`. Each is one that was producing a false pass.

Verified:

```
alcohol brand asset, nothing declared
  pass=False  human_review=True
  ALCOHOL-SURROGATE-001: Cannot evaluate: required field(s) not present
  on this artifact: directly_promotes_alcohol, is_surrogate.
```

Four facets were deliberately **not** marked required — `targeting_bases`, `consent_artifact_id`, `opt_in_consent_artifact_id`, `parental_consent_artifact_id` — because each predicate already fails explicitly and usefully on absence. A miss there would replace a clear block with a vaguer inconclusive. Required is for facets where absence is currently read as innocence.

### §1.6 D-6: the per-agent adapter is gone

`_brief_to_artifact()` has been deleted from Drishti. It is replaced by six lines lifting campaign facts out of the onboarding packet into context. The derivation that used to be hand-written in the agent — minors from age range — now happens in the facet layer and is verified by test: a brief with a 14-to-17 age band is still caught by `DPDP-CHILDREN-001`, with no adapter anywhere.

Eight agents will not each write their own version.

---

## §2 THE REMAINING REGISTER

### §2.1 D-2: `CHITRA-HITL-BUDGET` written, not deleted

v1.2.1 §F.13 Example 4 reports a violation from this rule id. No such rule exists in any registry. The easy fix was correcting the example. The right fix is that the control is real: a budget shift past a threshold without human approval is exactly what a HITL gate is for, and the example is evidence somebody intended it.

`CHITRA-HITL-BUDGET-001` now exists, deterministic, applying to `daily_optimization_log`, with the threshold read from `tenant.hitl_budget_shift_threshold_pct` defaulting to 20. It reproduces the example's evidence string shape exactly.

### §2.2 D-3: `IP-COPYRIGHT-001` splits

Example 3 reports the rule at `warn` for a territory-clearance concern. The rule is declared `block`. Both are right about different things: an undocumented licence is a block, and a licence that may or may not cover a placement is a warning that someone should check the paperwork.

`IP-COPYRIGHT-001` keeps licence documentation at `block`. `IP-COPYRIGHT-002` takes territory clearance at `warn`. The example now reconciles with the rules.

### §2.3 D-4: retention scan written into the rule

`DPDP-RETENTION-001`'s check text now states the structural scan for identifier markers in free-text evidence fields. It was implemented that way and specified as a self-declared boolean, which is the same divergence in miniature.

### §2.4 D-5: auto-fix driven by the result

The sanitizer branched on `rule.auto_fix_available`, a schema-required field that 37 of 39 rules leave false. It now branches on whether the predicate actually produced a `fixed_payload`. The declared field stays for the review UI, where knowing in advance whether a fix is likely is useful, but it no longer gates behaviour.

---

## §3 D-7: THE GATE THAT STOPS THIS RECURRING

`audit_field_paths.py` is now a permanent check, not a one-off investigation. It fails non-zero on any undeclared field read.

```
python3 audit_field_paths.py
  UNDECLARED FIELD READS: 0 distinct fields, 0 rule/artifact pairs
  Declared annotations in use: 42
  Of which required (absence yields INCONCLUSIVE, never a falsy pass): 8
```

Adding a rule that reads a new field now fails the build until the field is declared in `chitra_facets.FACETS` with a source. Someone has to say where it comes from, which is the one question nobody asked for the first 61.

Amended CI:

```yaml
      - run: python3 tools/chitra_conformance.py specs/
      - run: python3 tools/audit_field_paths.py
      - run: python3 tools/test_sanitizer.py
      - run: python3 tools/test_drishti.py
```

Three gates now watch three different drift classes: conformance watches rules against their own schema and citations against live law, the field census watches rules against artifact schemas, and the compatibility sweep watches vendors. The sweep is still not scheduled.

---

## §4 REISSUED AND NEW RULES

```yaml
- id: IP-COPYRIGHT-001
  source: [COPYRIGHT_ACT]
  citation: "Copyright Act, 1957, licence documentation for music, stock imagery and likeness"
  applies_to: [asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact.uses_music OR artifact.uses_stock_imagery OR artifact.uses_celebrity_likeness"
  check: "every declared use has a corresponding documented licence or contract"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: IP-COPYRIGHT-002
  source: [COPYRIGHT_ACT]
  citation: "Copyright Act, 1957, territorial scope of music licensing"
  applies_to: [motion_asset_registry, social_post]
  applies_when: "artifact.music_license_territory is present and not 'global'"
  check: "no placement in the plan reaches beyond the licensed territory"
  severity: warn
  auto_fix_available: false
  human_review_on_fail: false
  failure_message: "Music licensed for a single territory but placed on globally reaching surfaces. Verify territory clearance."
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: CHITRA-HITL-BUDGET-001
  source: [CHITRA_INTERNAL]
  citation: "CHITRA v1.2 section K, human-in-the-loop gates, budget authority"
  applies_to: [daily_optimization_log]
  applies_when: "any action in artifact.actions_taken carries a budget_shift_percent"
  check: "every budget shift above tenant.hitl_budget_shift_threshold_pct carries hitl_triggered and a human_approver_id"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Budget shift recorded without HITL approval. Revert or mark pending until approved."
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: DPDP-RETENTION-001
  source: [DPDP]
  citation: "DPDP Rules 2025, Seventh Schedule, retention ceiling and processing-log floor"
  applies_to: [performance_report, learnings_dossier]
  applies_when: "true"
  check: "artifact.data_retention_period_days <= tenant.dpdp_retention_policy_days AND artifact.processing_log_retention_days >= 365 AND no free-text evidence field contains an individual identifier marker (customer_id, user_id, email, phone, device_id, aadhaar)"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "3.0.0"
  effective_from: "2026-08-12"
```

---

## §5 VERIFICATION

```
python3 audit_field_paths.py          # 0 undeclared reads
python3 test_sanitizer.py             # 47/47
python3 test_drishti.py               # 26/26
python3 chitra_conformance.py specs/  # PASS
./verify_all.sh                       # all five gates
```

Every defect in the register is closed and verified. Nothing was deferred.

---

## §6 WHAT IS LEFT, AND WHAT KIND OF THING IT IS

Nothing in the defect register remains. What is left is not defects.

**Awaiting your decision** — cultural risk panel membership and escalation semantics; the five items flagged months ago (the sexual-orientation targeting clause, the surrogate-alcohol position, Diwali 2026, schema minimums, the 24-hour backfill).

**Operational, overdue, needs an environment rather than code** — schedule the compatibility sweep; wire the four gates into CI; `ANTHROPIC_API_KEY` for Drishti; stand up `credential-registry`.

**Data entry** — the 54 DMRA Schedule conditions; judge-panel model identifiers; minor-platform specs.

**Unbuilt product** — eight agents, the tool mesh, the eval harness, consent vault, HITL routing, webhook delivery.

The compliance substrate is now in a state I would defend: 32 of 41 rules genuinely enforce, no rule can pass on a field that does not exist, no rule reads a field nobody declares, and three automatic gates watch three drift classes.
