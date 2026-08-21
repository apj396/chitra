# CHITRA v1.3.11
**Research Coverage Invariant — ADR-020**

> **Date**: 16 August 2026
> **Origin**: the first real model run flagged that campaign geography listed Tamil Nadu while the audience research covered only Maharashtra and Karnataka.
> **Decision**: deny execution in a region the research does not cover. Not a warning.

## §1 WHY THIS IS A RULE AND NOT A CHECK

Disha's structural interrogation already flagged the gap. That is a warning at one point in one agent, and a warning is a thing a tired person clicks past at 7pm on a Friday.

An artifact carrying an unsubstantiated region should not be able to move at all. So the invariant lives in the rule registry, where the sanitizer enforces it on every artifact of every type that carries a geography, rather than in one agent's preflight. Rules are data; gates are code. This is a rule.

Drishti also halts at preflight, before any model call, because paying to generate a brief for a market that cannot ship is waste rather than safety.

## §2 THE WAIVER, AND WHY IT EXISTS

A hard block with no override makes a legitimate business decision impossible rather than accountable. A client may knowingly extend to an uncovered market and accept the risk; that is their call to make, not the platform's to forbid.

So this follows ADR-013's shape exactly. Blocked by default, lifted only by an explicit waiver naming the region, the approver, and the date. The waiver is not a boolean the packet asserts about itself; it names a person who owns the decision, and it lands in the audit trail.

The difference between this and the classic agency compromise is not whether the campaign runs in Tamil Nadu. It is whether anyone's name is on it.

## §3 RULE

```yaml
- id: CHITRA-RESEARCH-COVERAGE-001
  source: [CHITRA_INTERNAL]
  citation: "CHITRA research substantiation policy ADR-020, 16 August 2026"
  applies_to: [creative_brief, concept_slate, concept_bible, media_plan, content_calendar]
  applies_when: "campaign.geography is present"
  check: "every region in campaign.geography appears in campaign.research_coverage, or carries a waiver in campaign.research_coverage_waivers naming an approver"
  severity: block
  auto_fix_available: false
  human_review_on_fail: true
  hitl_queue: brand_owner
  failure_message: "Campaign geography includes a region the audience research does not cover. Territories for that market would rest on insight never tested there. Remove the region, extend the research, or record a waiver naming the approver."
  version: "1.0.0"
  effective_from: "2026-08-16"
```

## §4 PACKET CHANGE

Tamil Nadu is dropped from `geography` in the reference packet, per ADR-020. The waiver structure is documented in the packet rather than used, so the mechanism is visible without being exercised by default:

```json
"research_coverage_waivers": [
  {"region": "Tamil Nadu",
   "approved_by": "name of the person accepting the risk",
   "approved_on": "2026-08-16",
   "rationale": "why the campaign proceeds without tested insight there"}
]
```

## §5 WHAT THIS DEMONSTRATES

The catch itself is the point. A misaligned human workflow put a state into a campaign brief that no research supported, and the system found it in 185 seconds without being asked to look. A creative slate is a matter of judgement. An unsubstantiated multi-market allocation is not.
