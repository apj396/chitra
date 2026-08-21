# CHITRA v1.3.15
**The human step, tooled — and three bugs it exposed**

> **Date**: 18 August 2026 · 27 review tests · eleven gates green

## §1 NAMING A REVIEWER DOES NOT UNBLOCK ANYTHING

The cultural rules return inconclusive because no *completed audit* exists per concept, not because a config field is null. Writing a name into the packet changes nothing. Writing audits into `cultural_audits.json` to make a run go green is the fiction removed on 17 August.

What was missing was tooling to make the human step take fifteen minutes.

`chitra_review.py` does three things. **brief** assembles the evidence for each concept: which axes it touches, the register entries for those axes, any precedent, and the question the reviewer has to answer. **record** writes a decision with the reviewer's name, the date, a level per axis and their notes, and appends it to the audit ledger. **status** says which concepts are still outstanding.

The reviewer's name is required and never defaulted, on ADR-020's reasoning: the difference between a review and a rubber stamp is whether anyone's name is on it.

On a real slate the assistant surfaced only the religion axis for a concept set during Diwali week, and nothing at all for a documentary-format concept in a Mumbai flat. It issues no verdict and adopts no perspective, per ADR-001.

## §2 THE GRADE WAS DECORATIVE

Writing the tool exposed it. `_cultural` returned PASS whenever any completed audit existed, at any level. A reviewer could grade a concept **high** on caste and the artifact passed silently. The conditional severity introduced in v1.3.4, with its `escalation_threshold`, had no path to fire.

A reviewer's grade now governs. Low passes; medium and high fail the check and the rule's severity decides what that means.

## §3 TWO MORE BUGS UNDERNEATH THAT

**Every rule read the aggregate level.** The aggregate is the worst axis, so a concept graded medium for religion blocked on caste, gender, region and political as well. Each rule now reads its own axis, and the container aggregation carries a per-axis map rather than a single number. Aggregating only the worst axis is what made a five-axis judgement into one.

A related slip inside that fix: the first version recorded only axes above `low`, so a rule whose axis was graded low found nothing and fell back to the overall level. Lows must be recorded to be read.

**Every conditional rule blocked at any level.** The threshold parser required a closing quote that the rule extractor strips, so it never matched, `_escalates` fell through to its fail-safe `True`, and everything blocked. The fail-safe was correct — failing closed on an unparseable threshold is right — and it hid the bug for six days.

With it fixed, the rules behave as they were always written:

| Grade | religion | caste | gender | region | political |
|---|---|---|---|---|---|
| low | pass | pass | pass | pass | pass |
| medium | **block** | **block** | **block** | warn | **block** |
| high | **block** | **block** | **block** | **block** | **block** |

Region warns at medium because its threshold is high. That asymmetry was in the spec since v1.3.2 and has never once been exercised.

## §4 WHERE THIS LEAVES THE PIPELINE

A slate with every concept reviewed at low passes the sanitizer outright, with no cultural queue raised. That is the first configuration in which a slate can clear Phase 1 cleanly, and it requires a named human to have looked at every concept and said so on the record.

Eight rules still cannot enforce without a human: the five cultural ones now have a workflow rather than a wall, and `ASCI-DARK-001`, `ASCI-GREENWASH-001` and `EDTECH-NEP-001` remain judgement calls with no tooling.
