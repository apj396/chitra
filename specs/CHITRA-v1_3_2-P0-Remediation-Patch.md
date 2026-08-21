# CHITRA v1.3.2
**P0 Remediation Patch — Compliance Correctness, Registry Conformance, and the Conformance Gate**

> **Knowledge horizon**: 12 August 2026. Supersedes the 16 May 2026 horizon for §G, §H.2, §A.4 and the platform spec data.
> **Status**: Deploy-gate patch. Closes the five P0 findings of the 12 August 2026 skeptical-reader audit.
> **Scope**: Six sections. §1 to §5 fix the P0s. §6 ships the mechanism that would have caught four of them.
> **Renumbering note**: v1.3.1 §7 reserved "v1.3.2" for minor-platform spec data. That work is renumbered v1.3.3. A correctness patch takes the nearer number.

---

## §0 WHY THIS PATCH EXISTS

The audit found that the specification set had been growing faster than anything was checking it. Two sweeps closed 51 gaps by verifying that every method had a schema and every schema had a caller. Neither ever ran a rule against the schema that admits it, or a citation against the law it names. Four of the five P0 findings sat in that blind spot, and all four are mechanically detectable.

So this patch has an unusual shape. §1 to §5 are the fixes. §6 is a runnable checker, not a specification of one. Writing a document that describes a validator, in a document set whose defining failure is unvalidated documents, would reproduce the error at one remove.

| Finding | Section | What was wrong |
|---|---|---|
| P0-1 | §1 | A rule permitted advertising that is a criminal offence |
| P0-2 | §2 | 24 of 35 rules fail the registry's own admission schema, and fail open |
| P0-3 | §4 | The highest-frequency rule accepted disclosures ASCI prohibits |
| P0-4 | §3 | Three cultural rules evaluate to silence |
| P0-5 | §5 | Both ad platforms shipped major versions past the pin |

---

## §1 GAMING-RMG-001 — TOTAL PROHIBITION

### §1.1 The defect

v1.2 §G.3 permitted real-money gaming advertising subject to an addiction warning, an age-restriction disclosure, an 18+ audience floor, and `product_certified_by_SRB == true`.

The Promotion and Regulation of Online Gaming Act, 2025 (Act 32 of 2025) received Presidential assent on 22 August 2025 and came into force on 1 October 2025. It prohibits offering, operating, facilitating and advertising online money games. Advertising attracts imprisonment up to two years and a fine up to fifty lakh rupees. Offences relating to offering such services and facilitating financial transactions are cognisable and non-bailable. The self-regulatory body mechanism proposed under the IT Rules in 2023, which is the source of the `SRB` credential the rule tested for, was abandoned.

The rule therefore gated on a credential that cannot be issued, found no reason to block, and passed the artefact. The Act had been in force for over seven months before the specification's own knowledge horizon.

### §1.2 What the Act does not prohibit

The Act promotes and regulates two adjacent categories, and the replacement rule must not sweep them in:

- **E-sports** recognised under the National Sports Governance Act, 2025: competitive events in fixed multiplayer formats under predefined rules, where outcomes depend exclusively on player skill and no bets, wagers or stakes are placed.
- **Online social games** offered without stakes, including free-to-play titles and games monetised by subscription or cosmetic purchase where no monetary return is offered on an outcome.

A subscription fee is not a stake. A prize funded by the operator and not by pooled player entry is the boundary case; route it to legal review rather than deciding it in a predicate.

### §1.3 Category purge

The following `product_category` values are removed from every enum across the document set. They describe a category that cannot lawfully be advertised, and leaving them present invites a tenant to select one:

`fantasy_sports_real_money`, `rummy_real_money`, `poker_real_money`, `online_real_money_gaming`

Two replacements are added, both lawful:

`esports_recognised`, `online_social_gaming_no_stakes`

**Affected sites requiring amendment:**

| Location | Change |
|---|---|
| v1.2 §F.1 `creative_brief.product_category` | Remove four, add two |
| v1.2 §F.5 `media_plan.product_category` | Remove four, add two |
| v1.2.1 §F.10 `social_post.product_category` | Remove four, add two |
| v1.2.2 §8.1 category to Meta `special_ad_categories` | `gambling_gaming` must no longer resolve to a runnable configuration; map to `PROHIBITED_CATEGORY` and fail the tool call at the Mesh |
| v1.2.2 §8.2 category to platform age-floor | Remove the four rows; an age floor on a prohibited category is a category error |
| v1.2 §G.1 `ASCI-AI-002` forbidden-category list | `real_money_gaming` and `fantasy_sports_real_money` become redundant once GAMING-RMG-001 is a total ban, but are retained as defence in depth |

### §1.4 Escalation beyond the artefact

A total ban is a tenant-onboarding question, not only an artefact question. Amend v1.2.2 §4 `onboarding_packet` to reject an intake whose declared sector resolves to online money gaming, at intake rather than at first artefact. A tenant should be told at signup, not after Drishti has written a brief.

---

## §2 REGISTRY CONFORMANCE

### §2.1 The defect

`rule_object.json`, defined at v1.2.2 §1.2 and described there as the formalisation of the §G.0 interface, is what the rule registry validates against at load. Running the 35 authored rules against it produces 46 errors across 24 rules. Eleven rules load; twenty-four do not.

| Cause | Count |
|---|---|
| `citation` missing, schema-required | 16 |
| `source` outside the declared enum | 14 |
| `id` fails `^[A-Z]+-[A-Z]+-[0-9]{3}$` | 11 |
| `severity` outside `{block, warn, info}` | 3 |
| `auto_fix_available` typed string by an inline comment | 1 |
| `applies_to` missing, schema-required | 1 |

A rule rejected at load is simply absent from what `rule_registry.load_for()` returns. It is not stale, so §H.4's stale-registry block never fires. The sanitizer then reports `checks_run` listing only what loaded, stamps `sanitizer_pass = true`, and signs the envelope. The failure mode is not under-enforcement; it is under-enforcement that produces the documentary record of enforcement.

### §2.2 Design decision: widen the schema, do not renumber the rules

Eleven identifiers fail the pattern because it admits exactly two uppercase segments. `DMRA-001` and `TOBACCO-001` have too few. `PLATFORM-TOS-META-SPECIAL-CAT-001` has too many.

Renumbering eleven rules would invalidate the v1.2.1 §F.12 cross-reference matrix, every `compliance_checks_run` entry already written to the audit trail, the webhook payload examples in v1.3.1 §2.5, and the eval rubric references in v1.3 §2. The pattern was written without being run against the identifiers already in use, so the pattern is the thing that is wrong.

Same reasoning for `source`. Fourteen rules cite compound authority because compliance genuinely is compound; dark patterns sit under both CCPA and ASCI. A scalar enum cannot express that. `source` becomes an array.

### §2.3 Amended `rule_object.json`

```json
{
  "$id": "https://chitra.ai/schemas/v1.3.2/rule_object.json",
  "title": "Compliance Rule Object",
  "version": "2.0.0",
  "supersedes": "https://chitra.ai/schemas/v1.2/rule_object.json",
  "type": "object",
  "required": ["id", "source", "citation", "applies_to", "severity",
               "auto_fix_available", "human_review_on_fail"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-[0-9]{3}$",
      "description": "One or more uppercase segments, then a three-digit ordinal. Admits DMRA-001 and PLATFORM-TOS-META-SPECIAL-CAT-001 alike."
    },
    "source": {
      "type": "array",
      "minItems": 1,
      "items": {
        "enum": ["ASCI", "DPDP", "IT_RULES", "MEITY", "CPA", "CCPA_DARK",
                 "DMRA", "RBI", "SEBI", "IRDAI", "TRAI", "MOHFW",
                 "PLATFORM_TOS", "RERA", "COTPA", "EXCISE",
                 "COPYRIGHT_ACT", "TRADEMARKS_ACT", "ONLINE_GAMING_ACT",
                 "CONSTITUTION", "CULTURAL_REGISTER", "CHITRA_INTERNAL"]
      },
      "description": "Authorities, not instruments. The instrument goes in citation."
    },
    "citation": {"type": "string", "minLength": 8},
    "applies_to": {"type": "array", "items": {"type": "string"}},
    "rule_class": {"enum": ["artifact", "process", "tool_call"], "default": "artifact"},
    "applies_when": {"type": "string", "description": "Predicate as evaluable expression"},
    "check": {"type": "string", "description": "Check logic as evaluable expression"},
    "severity": {"enum": ["block", "warn", "info", "conditional"]},
    "escalation_threshold": {
      "type": "string",
      "description": "Required when severity is conditional. Expression resolving to the risk level at or above which the rule blocks."
    },
    "auto_fix_available": {"type": "boolean"},
    "human_review_on_fail": {"type": "boolean"},
    "failure_message": {"type": "string"},
    "shadow_mode": {"type": "boolean", "default": false},
    "version": {"type": "string"},
    "effective_from": {"type": "string", "format": "date"},
    "sunsets_on": {"type": "string", "format": "date"}
  },
  "allOf": [
    {
      "if": {"properties": {"severity": {"const": "conditional"}},
             "required": ["severity"]},
      "then": {"required": ["escalation_threshold"]}
    }
  ]
}
```

Four changes beyond widening. `applies_when` and `check` replace `applies_when_expression` and `check_expression`, which no authored rule ever used; the old names were invented in v1.2.2 and never propagated back, so the registry had nowhere to store the logic of even the rules that passed. `rule_class` distinguishes process rules from artefact rules so a rule with no artefact type is representable. `auto_fix_available` and `human_review_on_fail` become required, because §H.2 branches on both and 32 rules left them undefined. And `escalation_threshold` becomes conditionally required, which §3 uses.

### §2.4 Reissued rule set

All rules below are reissued at conforming shape. Identifiers are unchanged, so the F.12 matrix, the audit trail and every cross-reference survive. Where the substance changed, the section that changed it is named.

```yaml
- id: ASCI-DISC-001
  source: [ASCI]
  citation: "ASCI Influencer Advertising Guidelines 2026, disclosure sufficiency and placement"
  applies_to: [social_post, content_calendar]
  applies_when: "post.paid_partnership == true OR post.material_connection == true"
  check: "post.disclosure_tag in ['#Ad','#Advertisement','#Sponsored','#Promotion','#Paid','#PaidPartnership'] AND post.disclosure_position == 'first_line' AND post.disclosure_in_trailing_hashtag_cluster == false, OR post.platform_native_label == 'paid_partnership_with'"
  severity: block
  auto_fix_available: true
  human_review_on_fail: false
  failure_message: "Paid partnership disclosure missing, ambiguous, or not in the first line."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: ASCI-DISC-002
  source: [ASCI]
  citation: "ASCI Influencer Advertising Guidelines 2026, video and ephemeral disclosure duration"
  applies_to: [motion_asset_registry, social_post]
  applies_when: "artifact.is_video == true AND artifact.paid_partnership == true"
  check: "if artifact.format_is_ephemeral: artifact.disclosure_visible_throughout == true; elif artifact.duration_sec <= 15: artifact.disclosure_visible_duration_sec >= 3; elif artifact.duration_sec <= 120: artifact.disclosure_visible_duration_sec >= artifact.duration_sec / 3; else: artifact.disclosure_visible_throughout == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: ASCI-DISC-003
  source: [ASCI]
  citation: "ASCI Influencer Advertising Guidelines 2026, verbal disclosure requirement"
  applies_to: [motion_asset_registry, social_post, audio_asset_registry]
  applies_when: "artifact.paid_partnership == true AND (artifact.is_video == true OR artifact.is_audio == true)"
  check: "if artifact.is_video: artifact.verbal_disclosure_present == true AND artifact.verbal_disclosure_start_sec <= 10; if artifact.is_audio: artifact.verbal_disclosure_at_segment_start == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  failure_message: "Verbal disclosure required within the first 10 seconds of video, or at the start of an audio brand segment. A text overlay alone is not sufficient."
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: ASCI-AI-001
  source: [ASCI, IT_RULES]
  citation: "ASCI Draft Guidelines for Responsible Labelling of AI-Generated Content in Advertising, 8 May 2026, read with IT (Intermediary Guidelines and Digital Media Ethics Code) Amendment Rules 2026"
  applies_to: [motion_asset_registry, asset_registry, social_post]
  applies_when: "artifact.ai_risk_tier in ['medium','high']"
  check: "artifact.ai_risk_tier != 'high' AND artifact.ai_label_present == true AND artifact.ai_label_accurately_describes_use == true AND artifact.ai_label_meets_disclaimer_prominence == true AND (artifact.is_video == false OR (artifact.ai_label_within_first_5_sec == true AND artifact.ai_label_at_end == true))"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "High-risk AI use is prohibited and labelling does not cure it. Medium-risk use requires a prominent, accurate label."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: ASCI-AI-002
  source: [ASCI]
  citation: "ASCI restrictions on AI personas addressing children, April 2026"
  applies_to: [asset_registry, motion_asset_registry, media_plan, social_post]
  applies_when: "artifact.uses_ai_persona == true AND artifact.audience_includes_under_12 == true"
  check: "artifact.product_category not in ['junk_food','high_sugar_beverage','weight_loss']"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: ASCI-BFSI-001
  source: [ASCI]
  citation: "ASCI Influencer Guidelines Addendum 2, 7 April 2025, BFSI qualification disclosure"
  applies_to: [verbal_deck, social_post, motion_asset_registry]
  applies_when: "artifact.sector == 'BFSI' AND artifact.contains_technical_advice == true"
  check: "artifact.influencer_qualification_disclosed == true AND artifact.qualification_visible_prominently == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: ASCI-HEALTH-001
  source: [ASCI]
  citation: "ASCI Influencer Guidelines Addendum 2, 7 April 2025, health and nutrition qualification disclosure"
  applies_to: [verbal_deck, social_post]
  applies_when: "artifact.sector in ['healthcare','nutrition'] AND artifact.contains_technical_advice == true"
  check: "artifact.influencer_qualification_disclosed == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: ASCI-DARK-001
  source: [CCPA_DARK, ASCI]
  citation: "CCPA Guidelines on Dark Patterns, November 2023, read with ASCI 2026 enforcement focus"
  applies_to: [asset_registry, social_post, media_plan]
  applies_when: "true"
  check: "artifact.dark_patterns_present is empty across ['fake_scarcity_countdown','false_low_stock_indicator','hidden_costs_disclosed_only_at_checkout','confirmshaming_negative_button_text','roach_motel_difficult_unsubscribe','disguised_ad_appearing_organic','forced_consent_no_alternative','interface_interference_misleading_button_layout','bait_and_switch_advertised_vs_delivered','drip_pricing','subscription_trap','rogue_malware_pretending_security','trick_wording_double_negative_optout'] AND artifact.disclosure_legible == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: ASCI-GREENWASH-001
  source: [ASCI]
  citation: "ASCI Guidelines for Advertising of Environmental and Sustainability Claims"
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: "artifact.contains_environmental_claim == true"
  check: "artifact.claim_substantiated_with_third_party_certification == true OR artifact.claim_quantified_with_specific_metric == true OR artifact.claim_qualified_with_scope_disclosure == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: DPDP-CONSENT-001
  source: [DPDP]
  citation: "DPDP Act 2023 read with DPDP Rules 2025, notified 13 November 2025"
  applies_to: [media_plan, social_post]
  applies_when: "artifact.uses_custom_audience == true OR artifact.uses_crm_upload == true OR artifact.uses_whatsapp_marketing == true"
  check: "artifact.consent_artifact_id present AND consent_vault.lookup(artifact.consent_artifact_id).status == 'valid' AND consent_vault.lookup(artifact.consent_artifact_id).purpose matches artifact.processing_purpose"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: DPDP-CHILDREN-001
  source: [DPDP]
  citation: "DPDP Act 2023 section 9, processing of personal data of children"
  applies_to: [media_plan, creative_brief]
  applies_when: "artifact.target_audience.includes_minors == true"
  check: "artifact.uses_behavioral_tracking_of_minors == false AND artifact.uses_targeted_advertising_directed_at_minors == false AND artifact.verifiable_parental_consent_in_place == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: DPDP-RETENTION-001
  source: [DPDP]
  citation: "DPDP Rules 2025, Seventh Schedule, retention ceiling and processing-log floor"
  applies_to: [performance_report, learnings_dossier]
  applies_when: "true"
  check: "artifact.data_retention_period_days <= tenant.dpdp_retention_policy_days AND artifact.processing_log_retention_days >= 365 AND artifact.individual_level_data_present == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  failure_message: "Retention must sit under the tenant ceiling and above the one-year processing-log floor."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: DPDP-BREACH-NOTIFY-001
  source: [DPDP]
  citation: "DPDP Rules 2025, breach notification to the Data Protection Board and affected Data Principals"
  applies_to: [incident_record]
  rule_class: process
  applies_when: "incident.classified_as_breach == true"
  check: "notification.to_dpbi_sent == true AND notification.to_affected_data_principals_sent == true AND notification.elapsed_hours <= 72"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: DPDP-SENSITIVE-TARGETING-001
  source: [DPDP, CONSTITUTION, PLATFORM_TOS]
  citation: "DPDP Act 2023 read with constitutional non-discrimination principles and platform special-category policy"
  applies_to: [media_plan, social_post]
  applies_when: "true"
  check: "artifact.targeting_bases excludes ['religion_alone','caste','political_affiliation','sexual_orientation_unless_brand_is_LGBTQ_affirmative','health_condition_unless_legitimate_health_service','trade_union_membership']"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: DPDP-ERASURE-001
  source: [DPDP]
  citation: "DPDP Act 2023, right to erasure, read with DPDP Rules 2025"
  applies_to: [erasure_request]
  rule_class: process
  applies_when: "request.erasure_request == true"
  check: "request.data_principal_authorization present AND request.reversal_window_bypassed == true AND request.completed_within_hours <= 72 AND request.cascade_to_external_platforms_confirmed == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: DPDP-XBORDER-001
  source: [DPDP, MEITY]
  citation: "DPDP Act 2023 section 16, restriction on transfer outside India, read with MeitY country notifications"
  applies_to: [media_plan, tenant_context, asset_registry]
  applies_when: "artifact.involves_cross_border_transfer == true"
  check: "artifact.destination_country not in meity.restricted_country_list AND artifact.transfer_basis_documented == true"
  severity: warn
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Cross-border transfer flagged. Review against the current MeitY country list before Phase 3 enforcement on 13 May 2027."
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: DPDP-GRIEVANCE-001
  source: [DPDP]
  citation: "DPDP Rules 2025, grievance redressal timelines"
  applies_to: [grievance_record]
  rule_class: process
  applies_when: "grievance.received == true"
  check: "grievance.resolved_within_days <= 90 AND grievance.acknowledgement_sent == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: DMRA-001
  source: [DMRA]
  citation: "Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954, Schedule, all 54 conditions"
  applies_to: [verbal_deck, asset_registry, social_post, motion_asset_registry]
  applies_when: "artifact.contains_health_claim == true"
  check: "artifact.claimed_conditions disjoint from regdb.dmra_schedule_conditions"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Claim addresses a condition listed in the DMRA Schedule."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: RBI-BFSI-001
  source: [RBI]
  citation: "RBI guidelines on advertising of banking, lending and credit products"
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: "artifact.product_category == 'banking_lending_credit'"
  check: "artifact.contains_apr_or_interest_disclosure == true AND artifact.contains_t_and_c_apply_disclosure == true AND artifact.uses_guaranteed_returns_language == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: SEBI-MUTUAL-FUND-001
  source: [SEBI]
  citation: "SEBI Master Circular for Mutual Funds, advertisement code"
  applies_to: [verbal_deck, asset_registry, social_post, motion_asset_registry]
  applies_when: "artifact.product_category == 'mutual_funds_securities'"
  check: "artifact.contains_market_risk_disclaimer == true AND (artifact.is_video == false OR (artifact.market_risk_disclaimer_visible_min_sec >= 5 AND artifact.market_risk_disclaimer_voiceover == true))"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: IRDAI-INSURANCE-001
  source: [IRDAI]
  citation: "IRDAI (Insurance Advertisements and Disclosure) Regulations"
  applies_to: [verbal_deck, asset_registry]
  applies_when: "artifact.product_category == 'insurance'"
  check: "artifact.contains_policy_terms_disclosure == true AND artifact.contains_irdai_registration_number == true AND artifact.uses_misleading_returns_language == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: GAMING-RMG-001
  source: [ONLINE_GAMING_ACT]
  citation: "Promotion and Regulation of Online Gaming Act, 2025 (Act 32 of 2025), sections prohibiting advertisement of online money games, in force 1 October 2025"
  applies_to: [creative_brief, concept_slate, verbal_deck, asset_registry, motion_asset_registry, social_post, media_plan, content_calendar]
  applies_when: "artifact.involves_online_money_game == true OR artifact.product_category in ['fantasy_sports_real_money','rummy_real_money','poker_real_money','online_real_money_gaming','gambling_gaming']"
  check: "false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Advertising online money games is prohibited under Act 32 of 2025. Direct and indirect promotion both attract imprisonment up to 2 years and a fine up to Rs 50 lakh. E-sports recognised under the National Sports Governance Act 2025 and online social games without stakes are outside this prohibition and must be declared under esports_recognised or online_social_gaming_no_stakes."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: TOBACCO-001
  source: [COTPA]
  citation: "Cigarettes and Other Tobacco Products Act, 2003"
  applies_to: [verbal_deck, asset_registry, social_post, motion_asset_registry, media_plan]
  applies_when: "artifact.product_category in ['tobacco','cigarettes','tobacco_surrogate']"
  check: "false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Direct tobacco advertising is banned in India and surrogate advertising is heavily scrutinised."
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: ALCOHOL-SURROGATE-001
  source: [ASCI, EXCISE]
  citation: "ASCI Guidelines for Surrogate Advertising read with state excise advertising restrictions"
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: "artifact.product_category in ['alcohol','alcohol_surrogate']"
  check: "artifact.directly_promotes_alcohol == false AND (artifact.is_surrogate == false OR (artifact.surrogate_product_legitimate_market_presence == true AND artifact.uses_alcohol_consumption_imagery == false))"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: REAL-ESTATE-RERA-001
  source: [RERA]
  citation: "Real Estate (Regulation and Development) Act, 2016, section 11 advertisement disclosure"
  applies_to: [verbal_deck, asset_registry]
  applies_when: "artifact.product_category == 'real_estate'"
  check: "artifact.contains_rera_registration_number == true AND artifact.contains_project_details_disclosure == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: EDTECH-NEP-001
  source: [ASCI]
  citation: "ASCI Guidelines for Advertising of Educational Institutions and Programs"
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: "artifact.product_category == 'edtech'"
  check: "artifact.guarantees_specific_exam_rank_or_marks == false AND artifact.uses_fear_of_failure_appeals_to_parents == false AND artifact.uses_unverified_testimonials_of_minors == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: HEALTHCARE-CLAIM-SUB-001
  source: [CPA, MOHFW]
  citation: "Consumer Protection Act 2019 misleading advertisement provisions read with MoHFW advertising restrictions"
  applies_to: [verbal_deck, asset_registry]
  applies_when: "artifact.product_category in ['healthcare','medical_device','supplements','nutraceutical']"
  check: "artifact.health_claims_have_evidence_id == true AND artifact.uses_doctor_endorsement_for_drug_without_DGCI_approval == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: IP-TRADEMARK-001
  source: [TRADEMARKS_ACT]
  citation: "Trade Marks Act, 1999, sections 29 and 30 on infringement and comparative use"
  applies_to: [concept_slate, verbal_deck, asset_registry]
  applies_when: "true"
  check: "legal_precheck.trademark_clearance_passed == true AND (artifact.references_competitor_mark == false OR artifact.comparative_claim_substantiated == true)"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: IP-COPYRIGHT-001
  source: [COPYRIGHT_ACT]
  citation: "Copyright Act, 1957"
  applies_to: [asset_registry, motion_asset_registry]
  applies_when: "true"
  check: "(artifact.uses_music == false OR artifact.music_license_documented == true) AND (artifact.uses_stock_imagery == false OR artifact.stock_license_documented == true) AND (artifact.uses_celebrity_likeness == false OR artifact.celebrity_contract_documented == true)"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: IP-AI-CONSENT-001
  source: [IT_RULES]
  citation: "IT (Intermediary Guidelines and Digital Media Ethics Code) Amendment Rules, 2026, amended 10 February 2026, synthetic media provisions"
  applies_to: [motion_asset_registry, asset_registry]
  applies_when: "artifact.uses_voice_clone == true OR artifact.uses_face_swap == true OR artifact.uses_likeness_synthesis == true"
  check: "artifact.subject_consent_documented == true AND artifact.deepfake_label_present == true AND artifact.content_credentials_attached == true AND artifact.depicts_fabricated_endorsement == false AND artifact.depicts_fake_authority_figure == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  failure_message: "Fabricated endorsements, unauthorised likenesses and fake authority figures are prohibited outright. Consent and labelling do not cure them."
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: PLATFORM-TOS-WHATSAPP-001
  source: [PLATFORM_TOS]
  citation: "WhatsApp Business Platform Policy, marketing template and opt-in requirements"
  applies_to: [social_post, media_plan]
  applies_when: "artifact.channel == 'whatsapp'"
  check: "artifact.recipients_opted_in == true AND artifact.template_pre_approved == true AND artifact.respects_24h_utility_window == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: PLATFORM-TOS-META-SPECIAL-CAT-001
  source: [PLATFORM_TOS]
  citation: "Meta special ad categories policy"
  applies_to: [media_plan]
  applies_when: "artifact.product_category in ['credit','employment','housing','elections_politics']"
  check: "artifact.special_ad_category_declared_in_meta == true"
  severity: block
  auto_fix_available: false
  human_review_on_fail: false
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: PLATFORM-TOS-META-PLACEMENT-001
  source: [PLATFORM_TOS]
  citation: "Meta Graph and Marketing API v26.0 changelog, 29 July 2026, placement removals"
  applies_to: [media_plan, asset_registry, motion_asset_registry]
  applies_when: "artifact.platform_family == 'meta'"
  check: "artifact.placements disjoint from ['instagram_explore_feed','messenger_stories']"
  severity: block
  auto_fix_available: true
  human_review_on_fail: false
  failure_message: "Instagram Explore Feed returns an API error and Messenger Stories is silently stripped from v26.0. Silent stripping means the campaign runs with targeting the media plan does not describe."
  version: "1.0.0"
  effective_from: "2026-08-12"

- id: CULTURAL-RELIGION-001
  source: [CULTURAL_REGISTER]
  citation: "CHITRA cultural risk register, religious representation markers, curated per v1.2.2 section 9.1"
  applies_to: [concept_slate, asset_registry, verbal_deck, motion_asset_registry]
  applies_when: "artifact.references_religious_symbol == true OR artifact.references_religious_practice == true"
  check: "cultural_risk_audit.completed == true AND artifact.does_not_mock_religion == true"
  severity: conditional
  escalation_threshold: "cultural_risk_audit.level >= 'medium'"
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: CULTURAL-CASTE-001
  source: [CULTURAL_REGISTER, CONSTITUTION]
  citation: "CHITRA cultural risk register read with constitutional non-discrimination principles"
  applies_to: [concept_slate, asset_registry, verbal_deck]
  applies_when: "true"
  check: "artifact.uses_caste_stereotypes == false AND artifact.implies_caste_hierarchy == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: CULTURAL-GENDER-001
  source: [CULTURAL_REGISTER]
  citation: "CHITRA cultural risk register, gender representation markers"
  applies_to: [concept_slate, asset_registry, verbal_deck]
  applies_when: "true"
  check: "artifact.reinforces_harmful_gender_stereotypes == false AND artifact.uses_misogyny_for_humor == false AND artifact.uses_body_shaming == false"
  severity: conditional
  escalation_threshold: "cultural_risk_audit.level >= 'medium'"
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: CULTURAL-REGION-001
  source: [CULTURAL_REGISTER]
  citation: "CHITRA cultural risk register, regional and linguistic representation markers"
  applies_to: [concept_slate, asset_registry, verbal_deck]
  applies_when: "true"
  check: "artifact.mocks_regional_accent_for_humor == false AND artifact.implies_regional_hierarchy == false"
  severity: conditional
  escalation_threshold: "cultural_risk_audit.level >= 'high'"
  auto_fix_available: false
  human_review_on_fail: true
  version: "2.0.0"
  effective_from: "2026-08-12"

- id: CULTURAL-POLITICAL-001
  source: [CULTURAL_REGISTER]
  citation: "CHITRA cultural risk register, political neutrality markers"
  applies_to: [concept_slate, asset_registry, verbal_deck, social_post]
  applies_when: "true"
  check: "artifact.takes_partisan_political_position_unless_brand_is_political == false AND artifact.references_living_political_figure_unflatteringly == false"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"

- id: CHITRA-TENANT-ISOLATION-001
  source: [CHITRA_INTERNAL]
  citation: "CHITRA v1.2.3 section 6, cross-tenant exclusion enforcement"
  applies_to: [creative_brief, concept_slate, learnings_dossier, performance_report]
  applies_when: "true"
  check: "artifact.referenced_tenant_ids subset of [context.tenant_id] AND artifact.competitor_archive_references respect tenant.competitive_exclusions"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  version: "1.1.0"
  effective_from: "2026-08-12"
```

### §2.5 Rules requiring data, not predicates

`DMRA-001` previously listed 7 of 54 Schedule conditions with the remainder as a comment. It now delegates to `regdb.dmra_schedule_conditions`, a list owned by the Resource Curator in `chitra-regdb`. The 54 conditions are data on the same footing as the rule registry, and the Curator maintains them without a code deployment. Populating that list is a v1.3.3 work item and `DMRA-001` runs in `shadow_mode` until it is complete.

### §2.6 Cross-reference updates

- v1.2.1 §F.12 matrix gains rows for `ASCI-DISC-003`, `DPDP-XBORDER-001`, `DPDP-GRIEVANCE-001`, `PLATFORM-TOS-META-PLACEMENT-001`.
- `DPDP-BREACH-NOTIFY-001`, `DPDP-ERASURE-001` and `DPDP-GRIEVANCE-001` carry `rule_class: process` and are invoked by the v1.2.2 §9.3 incident-classification interface rather than by artefact type. Amend §9.3 to call `rule_registry.load_for(rule_class='process', context)`. This closes audit finding P1-12, where `DPDP-BREACH-NOTIFY-001` had no caller at all.

---

## §3 SEVERITY MODEL AND THE SANITIZER LOOP

### §3.1 The silent-drop defect

`CULTURAL-RELIGION-001` and `CULTURAL-GENDER-001` declared `severity: block_if_high_risk`; `CULTURAL-REGION-001` declared `warn_or_block_by_severity`. None existed in any enum. §H.2 branches `if severity == "block"` then `elif severity == "warn"`, with no else. The three rules ran, failed, and appended to neither list. They did not block, did not warn, and did not appear in the sanitizer output.

Religion, gender and region are the three axes on which an Indian campaign most often generates a reputational incident.

### §3.2 `conditional` severity

`severity: conditional` requires `escalation_threshold`, an expression resolving against the risk level the check produces. Below the threshold the finding is recorded as a warning; at or above it, it blocks. Both paths always produce an entry, which is the property the old values lacked.

### §3.3 Amended §H.2

```python
def sanitize(artifact_type: str, artifact: dict, context: dict) -> SanitizerResult:
    rules = rule_registry.load_for(artifact_type, context)
    violations, warnings, human_review = [], [], False

    applicable = [r for r in rules if r.applies_when(artifact, context)]
    for rule in applicable:
        result = rule.check(artifact, context)      # evaluated exactly once
        if result.pass:
            continue
        entry = {
            "rule_id": rule.id,
            "source": rule.source,
            "message": result.message,
            "evidence": result.evidence,
            "suggested_fix": result.suggested_fix,
        }
        severity = rule.severity
        if severity == "conditional":
            severity = "block" if rule.escalates(result, context) else "warn"
            entry["resolved_severity"] = severity
        if severity == "block":
            violations.append(entry)
        elif severity == "warn":
            warnings.append(entry)
        elif severity == "info":
            pass
        else:
            raise SanitizerConfigurationError(
                f"rule {rule.id} declares unhandled severity {rule.severity!r}"
            )
        if rule.human_review_on_fail:
            human_review = True

    return SanitizerResult(
        pass=(len(violations) == 0),
        checks_run=[r.id for r in applicable],
        violations=violations,
        warnings=warnings,
        human_review_required=human_review,
    )
```

Three changes. The result is captured once, closing audit finding P1-6, where the original re-ran `rule.check()` for every applicable rule to compute `human_review`; that doubled every `consent_vault.lookup()` and `legal_precheck` round trip at all three invocation points in §H.3, and could return `pass: true` with `human_review_required: true` if external state moved between calls. The `conditional` branch resolves before aggregation. And the final `else` raises rather than dropping, so an unrecognised severity becomes a loud configuration error at the boundary instead of silence in production.

### §3.4 Load-time strictness

`rule_registry.load_for` must reject the whole registry version if any rule fails `rule_object.json`, rather than returning the subset that parsed. Partial load is what turned P0-2 from a specification error into silent under-enforcement. Amend v1.2.2 §2.2 `load_for` to return `registry_status: complete | rejected` and have the sanitizer fail closed on `rejected`, consistent with §H.4's existing posture that a sanitizer error blocks rather than passes.

---

## §4 ASCI DISCLOSURE CORRECTIONS

The substance sits in the reissued `ASCI-DISC-001`, `ASCI-DISC-002` and new `ASCI-DISC-003` above. What changed and why:

| Change | Reason |
|---|---|
| `#Collab` and `#PartnerOf` removed from the accepted set | The 2026 guidelines prohibit ambiguous terms like #collab or #partnership standing alone without #Ad. CHITRA was passing precisely what ASCI names as non-compliant, on the highest-frequency rule in the system |
| First-line position now tested, not just tag presence | Presence alone passes a tag buried at the end of a caption |
| Trailing hashtag cluster explicitly rejected | Named as a prohibited placement |
| Ephemeral formats require full-duration disclosure | A 15-second story previously satisfied the rule with 3 seconds |
| `ASCI-DISC-003` added for verbal disclosure | Video now requires a verbal disclosure within the first 10 seconds in addition to the text overlay, and audio requires it at the start of the brand segment. No verbal predicate existed anywhere in §G |
| `audio_asset_registry` added to `applies_to` | Podcast and audio placements had no compliance surface at all |
| `ASCI-AI-001` label enum replaced with an accuracy-and-prominence predicate | ASCI has not mandated a single label format; a closed enum blocks compliant work, and over-blocking is how a rule gets disabled by tenants |
| `ASCI-AI-001` and `IP-AI-CONSENT-001` gained a prohibited high-risk tier | Under the risk-tiered draft, deepfakes, fabricated endorsements, unauthorised likenesses and fake authority figures are prohibited outright and a label does not cure them. Both rules previously treated disclosure as sufficient |

`ASCI-AI-001` depends on `artifact.ai_risk_tier`, a new required field on any artefact declaring AI generation. Add it to `asset_registry`, `motion_asset_registry` and `social_post` with enum `none | low | medium | high`, defaulting to `medium` when AI use is declared but the tier is not. Defaulting upward is deliberate: an unclassified AI artefact should require a label rather than skip the rule.

The ASCI AI framework was in draft with consultation closing 13 June 2026. The instrument register in §6 carries it as `under_revision` so the gate raises a finding until the final text is checked and the entry is updated.

---

## §5 PLATFORM RE-PIN

### §5.1 Pins

| Server | Old pin | New pin | Note |
|---|---|---|---|
| `meta-marketing` | v25.0 | v26.0 | Released 29 July 2026, effective same day |
| `google-ads-mcp` | v23.x | v25 | Released 22 July 2026; v24 and v25 were both major releases with breaking changes |

### §5.2 The pinning strategy needs a second date field

v1.2 §A.4 rests on pinning each server to a tested version, with the weekly sweep as the safety net. Meta's v26.0 restrictions extend to every supported version on 27 October 2026, and the 47 blocked commerce endpoints are removed from all versions entirely on that date. Pinning buys about ninety days, not exemption.

The v1.3.1 §1.3 sweep finding schema has `deprecation_window_days` and `sunset_date_announced`, both of which measure to the retirement of a version. Neither expresses a date on which a change applies retroactively across versions. Add:

```json
{
  "enforcement_date_all_versions": {
    "type": "string",
    "format": "date",
    "description": "Date on which a vendor change applies to every supported version regardless of pin. Pinning does not defer past this date."
  },
  "silent_failure_mode": {
    "type": "boolean",
    "description": "True when the vendor drops or ignores a value rather than returning an error. Silent stripping cannot be caught by error handling and needs a pre-call predicate."
  }
}
```

`silent_failure_mode` exists because Meta's v26.0 handles the two removed placements in opposite ways: Instagram Explore Feed returns an error, Messenger Stories is stripped without one. §I.1's error-class table has no row for a call that succeeds while doing something other than what was asked. `PLATFORM-TOS-META-PLACEMENT-001` catches both before the call.

Add a ticket class `P0_retroactive` to the v1.3.1 §1.4 curator template, triggered by any finding carrying `enforcement_date_all_versions`, with SLA measured backward from that date rather than forward from detection.

### §5.3 Already-landed breakage

The sweep job was specified in v1.3.1 §1 and never scheduled, so nothing was watching between 16 May and today. Four changes landed in that window:

| Date | Change | CHITRA impact |
|---|---|---|
| 19 May 2026 | Legacy Advantage+ Shopping and App campaign creation blocked on every Marketing API version | Lakshya's `media_plan` can emit a campaign type that cannot be created. Four days after the knowledge horizon |
| 22 June 2026 | Nielsen DMA targeting replaced by Comscore Markets for automotive model ads; `dma_codes` becomes `comscore_market_codes` | Unmigrated campaigns stopped delivering. Structurally identical to v1.3.1 §1.5's own worked example |
| June 2026 | Post and Page reach, video impressions and story impressions retired from the Graph API, replaced by Media Views and Media Viewers | Pramaan reads retired metric names and gets blanks. The eval harness would score this as a Pramaan quality regression rather than a platform change |
| 29 July 2026 | Marketing API v26.0; Explore Feed errors, Messenger Stories stripped, 47 commerce endpoints blocked, WhatsApp Status gains carousels | Placement and commerce paths break |

**Remediation:** repoint Pramaan's metric references in v1.1 §9 and v1.2 §F.6 to Media Views and Media Viewers, retaining the old names as read-only historical fields so pre-June comparisons remain possible and are labelled as non-comparable. Rename `dma_codes` to `comscore_market_codes` in the Lakshya manifest and §C. Add `whatsapp_status.carousel` to the platform spec data.

### §5.4 Eval quarantine

v1.3.1 §4.2 subscribes the eval system to `tool.degraded_mode_active` so degraded-mode runs do not pollute the regression baseline. Metric retirement is not degraded mode; the tool is healthy and returning a correct empty answer to a question about a field that no longer exists. Add `platform.metric_retired` to the v1.3.1 §2.3 `events_subscribed` enum and quarantine eval results the same way. Without this, the first eval run after any metric retirement reads as an agent regression.

---

## §6 THE CONFORMANCE GATE

### §6.1 Why this ships as code

Four of the five P0 findings were mechanically detectable, and none was detected by two sweeps that each described themselves as complete. Both sweeps checked referential integrity: every method has a schema, every schema has a caller. Neither checked whether a rule satisfies the schema that admits it, or whether a citation names live law.

`chitra_conformance.py` accompanies this document. It is not a specification of a checker. It runs.

### §6.2 What it checks

| Check | Question | P0 it would have caught |
|---|---|---|
| 1 | Does every rule validate against `rule_object.json`? | P0-2, P0-4 |
| 2 | Is every severity value one the sanitizer branches on? | P0-4 |
| 3 | Does every `$ref` resolve to a defined `$id`? | none yet, prevents a known class |
| 4 | Does every citation name a current instrument? | P0-1, P0-3 |

Check 4 is driven entirely by `instruments.json`, a curator-owned register of superseded, amended and repealed instruments. Entries match on the citation text only, never on a rule id, so a rule that has been correctly rewritten stops being flagged while keeping its identifier. An `exempt_ids` list handles an instrument amended only in part: ASCI Addendum 2 is amended on disclosure sufficiency but still governs BFSI and health qualification disclosure, so `ASCI-BFSI-001` and `ASCI-HEALTH-001` are exempt from that entry and every other rule citing Addendum 2 is not. Adding an entry is a data edit, not a code change, matching the v1.2 §G.6 decision to keep rules as data and the sanitizer as code. The register is on the same monthly-plus-on-notification cadence as v1.1 §A.1, which already declared that cadence for regulatory data and had nothing enforcing it.

The gate honours supersession: a rule reissued under the same id in a later document overrides the earlier definition, matching what the registry does at load. Without this the gate would report findings against text that no longer governs anything.

### §6.3 Result before this patch

Run against v1.0 to v1.3.1, the gate reports 52 findings across 25 sites: 46 conformance errors spanning 24 rules, 3 unhandled severities, 3 stale citations. It independently reproduced the audit's manual findings and located two the audit missed by hand: `ASCI-DISC-001` typed `auto_fix_available` as a string because of an inline comment, and `CHITRA-TENANT-ISOLATION-001` in v1.2.3 fails both the id pattern and the citation requirement.

It also caught one defect in this patch during drafting. The first draft of the widened id pattern required two or more segments, which would have excluded `DMRA-001` and `TOBACCO-001` — the same class of error as the original, made while fixing the original. The gate failed the run and the pattern was corrected before this document was finished.

### §6.4 Result after this patch

Run against v1.0 to v1.3.2, the gate passes: 39 effective rules, zero findings, exit status 0. Twenty-three rules are reported as superseded by their reissue here, which is the gate resolving the same supersession the registry resolves at load.

### §6.5 CI wiring

```yaml
name: chitra-spec-conformance
on: [push, pull_request]
jobs:
  conformance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install jsonschema pyyaml
      - run: python3 tools/chitra_conformance.py specs/
```

Non-zero exit fails the build. No specification change merges while any rule is unloadable, any severity unhandled, any `$ref` dangling, or any citation stale.

### §6.6 Operational placement

- **Repository**: CHITRA platform engineering repo, alongside the compatibility sweep job from v1.3.1 §1.6.
- **Ownership**: the checker is platform engineering; `instruments.json` is the Resource Curator, under the same two-person review as rule changes per v1.2 §G.6.
- **Cadence**: on every commit, plus a scheduled monthly run so a citation can go stale without anyone touching the repo. This is the gap that let P0-1 survive: the rule never changed, the law did.
- **Relationship to the sweep**: the compatibility sweep watches vendors, this gate watches regulators and the documents themselves. Between them, neither drift class is unobserved.

---

## §7 WHAT THIS PATCH DOES NOT CLOSE

Deliberately out of scope, carried forward:

1. **The 54 DMRA Schedule conditions.** `DMRA-001` now delegates to `regdb.dmra_schedule_conditions` and runs in `shadow_mode` until that list is populated. v1.3.3.
2. **Minor-platform spec data.** Telegram, Pinterest, Snapchat, Discord, Reddit. Renumbered from v1.3.2 to v1.3.3.
3. **P1-10, HITL gate routing.** §K's cultural-risk gate still catches every `human_review_on_fail` rule and routes DPDP consent failures to a DEI reviewer. The webhook `events_subscribed` enum already has the granularity to split it. Next patch.
4. **Judge panel model identifiers.** v1.3 §4.2 pins three model names labelled current as of May 2026. Verify each is still served before the first calibration run, because a silent substitution invalidates the calibration set the §5.3 estimator depends on.
5. **Predictive validity.** Whether eval scores predict in-market ROAS remains named in v1.3 §9.1 and unoperationalised.
6. **Content API for Shopping.** Sunsets 18 August 2026. No manifest references the migration. Six days.
7. **The ASCI AI final text.** Consultation closed 13 June 2026. The register carries the draft as `under_revision`, so the gate will keep raising it until someone checks and updates the entry. That is the intended behaviour.

---

## §8 VERSION SUMMARY

| Version | Adds | Status |
|---|---|---|
| v1.0 | Architecture | Released |
| v1.1 | Agent scaffolds and Global Dynamic Resource Pack | Released |
| v1.2 | MCP tool integration, handoff schemas, ruleset, sanitizer | Released |
| v1.2.1 | Extended handoff schemas, rule-to-schema matrix | Released |
| v1.2.2 | 24 underspecified contracts closed | Released |
| v1.2.3 | 27 final contract gaps, DPDP erasure flow | Released |
| v1.3 | Eval harness | Released |
| v1.3.1 | Compatibility sweep, webhook contracts, platform spec data | Released |
| v1.3.2 | Five P0 fixes, 39-rule conforming registry, conformance gate | This document |
| v1.3.3 (planned) | DMRA Schedule data, minor-platform specs, HITL gate split | Planned |
| v1.4 (planned) | Closed-loop tenant learning | Gated on 12 months of calibration data from a corrected substrate |

---

*End of CHITRA v1.3.2. The deploy gate identified by the 12 August 2026 audit is closed. The mechanism that would have caught four of the five findings now runs on every commit, which matters more than the five fixes: the next defect of this class fails a build instead of reaching a tenant.*
