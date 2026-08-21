# CHITRA v1.3.4
**Enforcement Correction — ending self-certification and narrowing the unconditional judgement rule**

> **Date**: 12 August 2026
> **Closes**: Implementation report §1 (seven self-certifying rules) and §2 item 1 (unconditional `ASCI-DARK-001`).
> **Method**: Predicates rewritten, then measured. 46/46 tests pass, up from 32.
> **Does not close**: the cultural rules. See §5, which explains why that is a deliberate stop rather than an omission.

---

## §0 RESULT

| Measure | Before | After |
|---|---:|---:|
| Rules that genuinely enforce | 23/39 (59%) | **30/39 (77%)** |
| Rules reading a self-declared compliance boolean | 7 | **0** |
| Artifact types sending every instance to human review | 7 of 11 | **5 of 11** |

The self-certification class is gone entirely. Nine judgement rules remain, and eight of those are the cultural rules plus `ASCI-DARK-001`, which now only fires where a dark pattern has somewhere to live.

---

## §1 THE SELF-CERTIFICATION FIX

Seven rules asked the artifact whether it complied, and the artifact was written by the agent under audit. Each has been rewritten to get the answer from somewhere the agent does not control.

| Rule | Was | Now |
|---|---|---|
| `RBI-BFSI-001` | `contains_apr_or_interest_disclosure == true` | Reads the copy for a rate figure alongside APR or interest wording, a terms-apply line, and guarantee language |
| `IRDAI-INSURANCE-001` | `contains_irdai_registration_number == true` | Detects the IRDAI registration number in the copy, same technique as the RERA number |
| `SEBI-MUTUAL-FUND-001` | `contains_market_risk_disclaimer == true` | Detects the statutory market-risk sentence in the copy. Duration and voiceover were already numeric |
| `DPDP-CHILDREN-001` | `verifiable_parental_consent_in_place == true` | Resolves parental consent through consent-vault, and derives behavioural targeting from the plan's own targeting fields |
| `PLATFORM-TOS-WHATSAPP-001` | `recipients_opted_in == true` | Resolves opt-in through consent-vault, and checks the consent is channel-specific |
| `ASCI-BFSI-001` | `influencer_qualification_disclosed == true` | Requires a credential reference that resolves as valid, and the qualification to appear in the copy |
| `ASCI-HEALTH-001` | Same | Same credential treatment |

### §1.1 The general principle

Three techniques, in order of preference:

1. **Read the artifact's own content** rather than a summary field about it. A disclosure either appears in the copy or it does not. This is what `REAL-ESTATE-RERA-001` was already doing and what the other sectoral rules should have been doing from the start.
2. **Resolve through the service that owns the fact.** Consent-vault records opt-in and parental consent. Asking the artifact was always the wrong question asked of the wrong party.
3. **Derive from structured fields the agent must fill in anyway.** `DPDP-CHILDREN-001` now inspects `targeting_bases` and `audience_signals` for behavioural signals rather than asking the planner whether its plan is behavioural. The planner cannot describe a lookalike audience without naming it.

### §1.2 New required fields

| Field | On | Replaces |
|---|---|---|
| `parental_consent_artifact_id` | `media_plan`, `creative_brief` | `verifiable_parental_consent_in_place` |
| `opt_in_consent_artifact_id` | `media_plan`, `social_post`, `content_calendar` | `recipients_opted_in` |
| `influencer_qualification_credential_id` | `social_post`, `motion_asset_registry`, `concept_bible` | `influencer_qualification_disclosed` |

A new `credential-registry` service is required, exposing `lookup(credential_id)` returning `{valid, status, designation, verified_at}`. It sits alongside consent-vault in v1.2.2 §2 and follows the same interface conventions. Until it is live, `ASCI-BFSI-001` and `ASCI-HEALTH-001` return INCONCLUSIVE and route to a human, which is the correct behaviour for an unavailable dependency.

The three replaced booleans are removed from the artifact schemas. Leaving them in place would let an agent keep filling them in while the rule ignores them, which is a worse state than either.

### §1.3 Verified by test

`v134_rbi_reads_copy` submits an artifact whose copy has no rate disclosure but which sets `contains_apr_or_interest_disclosure: true` and `contains_t_and_c_apply_disclosure: true`. Under the old rule this passed. It now fails, because the sanitizer reads the copy instead of the claim about the copy.

---

## §2 NARROWING `ASCI-DARK-001`

The rule fired on every artifact of its type, could not be evaluated by software, and therefore sent every artifact to human review. It was the single largest contributor to the review queue.

A dark pattern needs a surface. `applies_when` now requires one:

```yaml
applies_when: "artifact.offer_mechanics or artifact.ui_elements intersects
  [countdown_timer, stock_indicator, scarcity_badge, subscription_flow,
   checkout_path, free_trial_auto_renew, drip_pricing, consent_gate,
   unsubscribe_flow, pre_ticked_option, urgency_banner]
  OR artifact.has_commercial_flow == true
  OR artifact.dark_patterns_present is non-empty"
```

A brand post with a photograph and a caption has no countdown, no stock indicator and no checkout path, so the rule no longer reaches it. A post carrying a countdown timer still does, and still routes to a human, which is correct: whether a countdown is fake is a judgement call.

**This closed one of the two recorded specification divergences.** v1.2.1 §F.13 Example 1 illustrates a `social_post` passing cleanly with `human_review_required: false`. Since the implementation report that example was impossible, because `ASCI-DARK-001` reached every post. It now passes exactly as the specification always claimed it would.

---

## §3 WHAT THE MEASUREMENT SHOWED THAT THE SPECIFICATION DOES NOT SAY

The review-load figures in the implementation report were derived from a hand-written list of rules I judged unconditional. That was the same mistake the specification makes throughout, so the analysis tool now measures instead: it runs a minimal artifact of each type through the sanitizer and counts what comes back INCONCLUSIVE.

The measurement changed the picture.

| Context | Artifact types always reviewed |
|---|---:|
| With a completed cultural risk audit | 5 of 11 |
| Without one | 7 of 11 |

**The cultural risk audit is the real gate, not the cultural rules.** The five cultural rules pass when a completed audit is present in context and return INCONCLUSIVE when it is not. So the human step is the audit, and it happens once per whatever scope the audit covers.

Nowhere in the specification set is that scope defined. If the audit is scoped to a campaign, the review load is one human review per campaign and the system is operable today. If it is scoped per asset, it is one per artifact and the system is not. Two orders of magnitude of operational difference rest on a decision nobody has made, and the documents read the same either way.

**This is now the most consequential open question in the project**, and it is a policy decision rather than an engineering one.

The remaining always-reviewed rule in the measurement is `IP-TRADEMARK-001`, which returns INCONCLUSIVE only because legal-precheck is absent from the probe context. With the service connected it resolves normally. It is a dependency question, not a design one.

---

## §4 REISSUED RULES

Changed rules only. All other rules from v1.3.2 §2.4 and v1.3.3 stand unchanged.

```yaml
- id: ASCI-DARK-001
  source: [CCPA_DARK, ASCI]
  citation: "CCPA Guidelines on Dark Patterns, November 2023, read with ASCI 2026 enforcement focus"
  applies_to: [asset_registry, media_plan, social_post]
  applies_when: "artifact.offer_mechanics or artifact.ui_elements intersects [countdown_timer, stock_indicator, scarcity_badge, subscription_flow, checkout_path, free_trial_auto_renew, drip_pricing, consent_gate, unsubscribe_flow, pre_ticked_option, urgency_banner] OR artifact.has_commercial_flow == true OR artifact.dark_patterns_present is non-empty"
  check: "artifact carries no pattern from the CCPA dark-pattern list and disclosure_legible == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "3.0.0"
  effective_from: "2026-08-12"

- id: ASCI-BFSI-001
  source: [ASCI]
  citation: "ASCI Influencer Guidelines Addendum 2, 7 April 2025, BFSI qualification disclosure"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact.sector == 'BFSI' AND artifact.contains_technical_advice == true"
  check: "credential_registry.lookup(artifact.influencer_qualification_credential_id).valid == true AND the qualification appears in the artifact copy"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: ASCI-HEALTH-001
  source: [ASCI]
  citation: "ASCI Influencer Guidelines Addendum 2, 7 April 2025, health and nutrition qualification disclosure"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact.sector in ['healthcare','nutrition'] AND artifact.contains_technical_advice == true"
  check: "credential_registry.lookup(artifact.influencer_qualification_credential_id).valid == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: DPDP-CHILDREN-001
  source: [DPDP]
  citation: "DPDP Act 2023 section 9, processing of personal data of children"
  applies_to: [creative_brief, concept_slate, media_plan, social_post]
  applies_when: "artifact.target_audience.includes_minors == true"
  check: "artifact.targeting_bases and artifact.audience_signals contain no behavioural signal AND consent_vault.lookup(artifact.parental_consent_artifact_id).consent_type == 'verifiable_parental' AND status == 'valid'"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: PLATFORM-TOS-WHATSAPP-001
  source: [PLATFORM_TOS]
  citation: "WhatsApp Business Platform Policy, marketing template and opt-in requirements"
  applies_to: [media_plan, daily_optimization_log, content_calendar, social_post]
  applies_when: "artifact.channel == 'whatsapp'"
  check: "consent_vault.lookup(artifact.opt_in_consent_artifact_id).status == 'valid' AND channel == 'whatsapp' AND artifact.template_pre_approved == true AND artifact.respects_24h_utility_window == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: RBI-BFSI-001
  source: [RBI]
  citation: "RBI guidelines on advertising of banking, lending and credit products"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact.product_category == 'banking_lending_credit'"
  check: "artifact copy contains a rate figure alongside APR or interest wording AND a terms-apply line AND no guaranteed-returns phrase"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: IRDAI-INSURANCE-001
  source: [IRDAI]
  citation: "IRDAI (Insurance Advertisements and Disclosure) Regulations"
  applies_to: [concept_bible, asset_registry, social_post]
  applies_when: "artifact.product_category == 'insurance'"
  check: "artifact copy contains an IRDAI registration number AND a policy terms disclosure AND no misleading returns phrase"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: SEBI-MUTUAL-FUND-001
  source: [SEBI]
  citation: "SEBI Master Circular for Mutual Funds, advertisement code"
  applies_to: [concept_bible, asset_registry, motion_asset_registry, social_post]
  applies_when: "artifact.product_category == 'mutual_funds_securities'"
  check: "artifact copy contains the statutory market-risk sentence AND if video, disclaimer visible at least 5s with voiceover"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"
```

---

## §5 WHY THE CULTURAL RULES ARE NOT IN THIS PATCH

Nine judgement rules remain and five are the cultural rules: caste, religion, gender, region, political. Putting them on the v1.3 judge panel is technically straightforward. The panel, the calibration framework and the bias-corrected estimator all exist in v1.3 §4 and §5 and are currently aimed only at eval scoring.

The blocker is not technical. Building the classifier means deciding what counts as disrespectful to a religion, what counts as a caste stereotype, and where the line falls on regional accent humour, for the Indian market, and then encoding those thresholds behind a confidence score that will make them look measured and neutral.

v1.3 §8 already flagged this: the cultural reviewer panel needs native speakers per language and recognised caste, religion, gender and regional voices. That was raised as a gap and never answered. It is still open.

Writing those thresholds without that panel would bake one perspective into a compliance gate and hide it behind a number. That is a worse failure than the review queue, because the review queue is at least visibly broken.

**Required before the cultural classifier is built:**

1. Who sits on the cultural risk panel and who signs off on the register.
2. What the escalation levels mean in operational terms, with worked examples per axis.
3. The scoping decision from §3 above: is the cultural risk audit per campaign or per asset.

Item 3 is required regardless, and is the cheapest of the three to answer.

---

## §6 VERIFICATION

```
python3 test_sanitizer.py             # 46/46 pass
python3 analyse_implementability.py   # 30/39 enforcing, 0 self-declared
```

New tests in this patch: dark-pattern narrowing on and off, a registry-wide assertion that no rule reads a self-declared compliance boolean, copy-detection for the RBI rule including the case where the artifact asserts compliance it does not have, channel-specific WhatsApp opt-in, behavioural-targeting derivation for minors, and credential resolution including the lapsed case.

---

## §7 WHAT REMAINS

1. **Scope the cultural risk audit** — per campaign or per asset. One decision, two orders of magnitude of operational difference. Cheapest and most consequential item open.
2. **Name the cultural risk panel** (§5), then build the classifier.
3. Stand up `credential-registry`, or accept human review on the two ASCI qualification rules.
4. DMRA 54-condition Schedule data.
5. HITL gate routing split by rule source.
6. Judge-panel model identifiers verified as still served.
7. Minor-platform spec data.

Items 1 and 2 are what stands between here and a first live tenant.
