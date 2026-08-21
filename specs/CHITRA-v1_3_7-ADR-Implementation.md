# CHITRA v1.3.7
**ADR Implementation — the decision register, executed**

> **Date**: 12 August 2026
> **Implements**: ADR-001, 003, 006, 007, 010, 011, 013, 014, 018.
> **Companion**: `CHITRA-ADR-Register.md` carries all nineteen decisions and their reasoning.

## §1 REISSUED AND NEW RULES

```yaml
- id: DPDP-SENSITIVE-TARGETING-001
  source: [PLATFORM_TOS, CHITRA_INTERNAL, CONSTITUTION]
  citation: "Meta and Google prohibited targeting-attribute policies, read with CHITRA rules-engine integrity policy ADR-003 and constitutional non-discrimination principles"
  applies_to: [creative_brief, concept_slate, media_plan, social_post]
  applies_when: "true"
  check: "artifact.targeting_bases excludes religion_alone, caste, political_affiliation, sexual_orientation, health_condition and trade_union_membership, with no brand-declared exception"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  hitl_queue: dpo
  failure_message: "Targeting on a protected attribute. Reach the audience through content and context instead."
  version: "3.0.0"
  effective_from: "2026-08-12"

- id: ALCOHOL-SURROGATE-001
  source: [CCPA_DARK, ASCI, EXCISE]
  citation: "CCPA Guidelines for Prevention of Misleading Advertisements 2022 read with the ASCI Guidelines for Qualification of Brand Extension, as updated 14 December 2023"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post, media_plan]
  applies_when: "artifact.product_category in alcohol or alcohol_surrogate"
  check: "no direct promotion, AND a ca_attestation_id resolving as a valid brand-extension certificate in the credential registry, AND no alcohol consumption imagery"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Alcohol-adjacent advertising is blocked by default. Only a genuine brand extension certified by an independent CA firm against the ASCI thresholds may proceed."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: IP-REAL-PERSON-LIKENESS-001
  source: [CHITRA_INTERNAL, CONSTITUTION]
  citation: "Personality and publicity rights as recognised by Indian courts, read with CHITRA legal-liability gating policy ADR-018"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact declares any identifiable real person"
  check: "every identifiable real person carries a release_document_uri, unless a public figure depicted in editorial context"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  hitl_queue: legal
  failure_message: "Identifiable real person depicted without a signed release."
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: DMRA-001
  source: [DMRA]
  citation: "Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954, Schedule and section 3"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact.contains_health_claim == true"
  check: "no Schedule condition or section 3 prohibition appears in the declared claim list or in the artifact copy"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  shadow_mode: true
  failure_message: "Claim addresses a condition in the DMRA Schedule."
  version: "3.0.0"
  effective_from: "2026-08-12"
```

`DMRA-001` carries `shadow_mode: true` until the Schedule is verified against the Gazette, per ADR-010.

## §2 NEW COMPONENTS

| File | ADR | What it is |
|---|---|---|
| `chitra_services.py` | 006, 007, 010 | Credential registry, regulatory data, HITL router |
| `credentials.json` | 006, 013 | Curator-maintained credential table |
| `dmra_schedule.json` | 010 | 54 Schedule conditions, synonyms, section 3 prohibitions |
| `chitra_cultural_assistant.py` | 001 | Evidence assembler. No persona, no verdict |
| `chitra_eval_extras.py` | 011, 014 | Array variance scorer, judge panel health gate |
| `.github/workflows/chitra-gates.yml` | 008 | Gates on push and on schedule |

## §3 HITL QUEUES

| Queue | SLA | Sources routed |
|---|---:|---|
| `dpo` | 4h | DPDP, MEITY |
| `ad_ops` | 8h | PLATFORM_TOS |
| `legal` | 24h | COPYRIGHT_ACT, TRADEMARKS_ACT, IT_RULES, ONLINE_GAMING_ACT |
| `compliance` | 24h | ASCI, CCPA_DARK, CPA, DMRA, MOHFW, RBI, SEBI, IRDAI, TRAI, RERA, COTPA, EXCISE |
| `brand_owner` | 24h | CHITRA_INTERNAL |
| `cultural_review` | 48h | CULTURAL_REGISTER, CONSTITUTION |

Items sort tightest-SLA-first, so a consent failure is not queued behind a typography warning.

An optional `hitl_queue` on a rule overrides source-based routing. This was added
during implementation, after a test caught that ADR-003's recitation of
`DPDP-SENSITIVE-TARGETING-001` to platform policy had silently moved caste-based
targeting violations from a rights queue to ad ops. Routing that rides on the
citation changes whenever the citation changes, which is the wrong coupling.
`DPDP-SENSITIVE-TARGETING-001` declares `dpo`; `IP-REAL-PERSON-LIKENESS-001`
declares `legal`.

## §4 WHAT ADR-014 MEASURED

The variance scorer separates padding from exploration cleanly on test arrays of fifteen:

| Array | Level | Mean similarity | Structural clusters | Near-duplicate pairs |
|---|---|---:|---:|---:|
| Padded (one idea, fifteen rewordings) | weak | 0.761 | 2 | 96 |
| Varied | excellent | 0.044 | 0 | 0 |

Measured locally rather than judged, so the metric cannot drift when a judge model changes.

## §5 VERIFICATION

```
./verify_all.sh
```

---

## §6 ADR-014 AT GENERATION TIME (addendum)

The variance scorer was extended from flat arrays to concept slates and moved
from eval into the generation loop, where it is cheapest. Disha's divergent
phase produces at least twelve territories; the schema minimum can count them
but cannot tell twelve ideas from one idea twelve times.

### §6.1 Three ways a slate collapses

| Measure | Catches |
|---|---|
| Per-field similarity, proposition weighted at 0.5 | Twelve distinct titles over three propositions |
| Lens coverage against the six lenses in the scaffold | One lens twelve times, however varied the wording |
| Largest mutually-similar cluster | A slate that looks fine on the mean while eight of twelve sit on each other |

The mean alone is a weak signal here. A slate of three tight clusters averages
low, because within-group similarity is high and across-group similarity is
near zero. Clustering is what catches that shape, so the verdict does not rest
on the mean.

### §6.2 The gate rejects indices, not slates

`VarianceGate.enforce()` keeps the first member of each collapsed group and
returns the rest for regeneration, with feedback naming which territories
merged and which lenses are unused. Regenerating four of twelve is cheaper
than a full retry and gives the agent an instruction instead of "try again".

### §6.3 Calibration, and what it cannot do

Collapse is detected on the proposition matrix rather than the blended one: an
idea lives in its proposition, and a distinct title on a duplicated idea was
dragging genuinely collapsed pairs under the bar.

The threshold sits at 0.45, above the bottom of the measured within-idea band
(0.31 to 0.67), because a false positive makes an agent discard good work
while a false negative lets one duplicate through. Two short propositions
sharing only "clothes" and "cannot" scored 0.34 while being genuinely
different territories, and that false positive is what set the bar.

The consequence is stated rather than hidden: on the padded test slate the
gate collapses twelve territories to four, where three is the true answer. One
synonym-level rewording survives. Lexical similarity cannot see an agent
expressing one idea in genuinely different vocabulary. That is what the
injectable `embedder` hook and the v1.3 judge panel are for, and the gate
takes an embedder without any other change.
