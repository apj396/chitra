# CHITRA v1.3.14
**The divergence contradiction, and three spec conflicts a model found**

> **Date**: 18 August 2026 · 66 Disha tests · ten gates green

## §1 I FIXED THE WRONG THING TWICE

Divergence turn 1 has now failed in 5 of 5 real runs. Round one I blamed the model. Round two I blamed the concept_slate schema I had embedded under **YOUR OUTPUT MUST VALIDATE AGAINST THIS**, removed it, and the next run still returned `concepts_approved`.

The cause was never mine to add or remove. The v1.1 Disha scaffold's own `[OUTPUT FORMAT]` section defines the output as a Concept Slate with a Killed Concepts Log and a pitch deck. Divergence asks for a flat territories array. Appending "return territories" after ten thousand characters of "your output is a slate" loses, and had been losing since Disha was built.

**Fix**: the divergence turn strips `[OUTPUT FORMAT]` from the scaffold and says so to the model. The scoring turn keeps it, because that section carries the kill-tag vocabulary. Two phases, two prompts.

This is the same class of defect as `verbal_deck` and the field census: two documents written independently, each internally coherent, contradicting each other in a place nothing checked. The scaffold predates the v1.3.8 decision to separate scoring from generating, and nobody reconciled it.

## §2 THREE CONFLICTS THE MODEL FOUND THAT I HAD NOT

Drishti reported all three unprompted, in `open_questions_for_disha`.

**`day_in_the_life` cannot hold what the methodology asks for.** The v1.1 scaffold calls for a 200-word sketch. The v1.2 schema caps the field at `maxLength: 400`, roughly sixty words. The model complied with the schema, used the shorter version, and flagged the conflict rather than silently truncating. Recorded here; the schema and the scaffold need reconciling and neither is obviously wrong.

**The source enums are asymmetric.** `mandatories.source` allows `legal` and not `cultural_risk`. `prohibitions.source` allows `cultural_risk` and not `legal`. My reference packet used `legal` for a prohibition, the model mapped it to `regulatory` to pass validation, and told me it had done so. Packet corrected; the asymmetry is documented in it rather than papered over.

**Escalation with a stated default.** Not a defect, worth recording. Drishti converted four open questions into `DECISION NEEDED` items each carrying a `DEFAULT IN EFFECT` and a `CONSEQUENCE OF NO RESPONSE` — for example, no festival-adjacent creative may be locked until a cultural reviewer is named, while non-festival work proceeds. Nothing in the scaffold asks for that structure. It is a better handling of an unanswered question than blocking or ignoring, and it is worth writing back into the scaffold.

## §3 THE CAVEAT WAS LYING

The run report closed with "Cultural risk audits were seeded as completed at low risk" for a run where I had removed the seeding the day before. The text outlived the behaviour it described.

It now reports what is actually in `cultural_audits.json`: with none, it says no audit exists, the cultural rules returned inconclusive, and the slate is queued for `cultural_review` and not cleared for production.

## §4 STILL UNEXPLAINED

`stop_reason=max_tokens` with `chars=1996`. A 16,000-token budget produced under two thousand characters of text, so the budget went somewhere other than the text block. `run_slice` now prints `usage` and `content_block_types` on a failed turn, which will name it on the next run. Recorded as open rather than guessed at.
