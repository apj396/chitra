# CHITRA v1.3
**Eval Harness — Measuring Whether Agents Are Good at Their Jobs**

> **Knowledge horizon**: 16 May 2026.
> **Builds on**: v1.0–v1.2.3. The contract substrate is complete; v1.3 measures performance against it.
> **Scope**: How to evaluate each of the nine CHITRA agents, the rubrics that drive scoring, the corpus that grounds the evaluation, the judges that score the work, the calibration that makes judge scores trustworthy, and the regression suite that catches drift over time.

---

## §0 WHAT v1.3 IS, AND WHAT IT IS NOT

v1.2.x answered: *does the pipeline run, do the artifacts pass schema, do the rules enforce, do the handoffs verify?* All binary questions. All answered.

v1.3 answers different questions: *is Drishti's brief defensible in three sentences? Are Disha's three-of-five surviving concepts actually the right ones? Does Vaani's Tamil copy sound Tamil-first or translated? Is Lakshya's ROAS curve trending up because the optimization is good or because the audience was forgiving?*

These are quality questions. Quality is graded, not binary. Quality drifts with model versions, with rubric changes, with corpus changes, and with what the world counts as "good" in mid-2026 vs early-2027. v1.3 makes quality measurable, comparable across time, and resistant to the most common evaluation failures.

**Three things v1.3 is not:**

1. **It is not a substitute for the sanitizer.** Sanitizer enforces what must never happen (compliance, contracts). Eval measures what should usually happen well (quality). A campaign can pass every sanitizer rule and still be mediocre work.
2. **It is not a substitute for human judgment.** It is a tool for human reviewers — surfacing what to look at, where the agents are drifting, when to investigate. The final call on creative quality remains a human call. Forever.
3. **It is not stable.** Rubrics, corpus, judge models, and calibration sets all need refresh cadences. A v1.3 deployment that runs unchanged for 18 months is not measuring 2027's reality; it is measuring stale aesthetics with a stale instrument.

---

## §1 EVAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      EVAL HARNESS LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   GOLDEN CORPUS     →     AGENT UNDER TEST    →     ARTIFACT             │
│   (briefs, prompts,        (Drishti v1.3,            (creative_brief,    │
│    references)              Claude Opus 4.7)          concept_slate,…)   │
│                                                          │                │
│                                                          ▼                │
│                                          ┌─────────────────────┐         │
│                                          │  RUBRIC SCORING     │         │
│                                          │                     │         │
│                                          │  ┌──────────────┐   │         │
│                                          │  │ LLM Judge    │   │         │
│                                          │  │ Panel        │   │         │
│                                          │  └──────┬───────┘   │         │
│                                          │         │           │         │
│                                          │  ┌──────▼───────┐   │         │
│                                          │  │ Calibration  │   │         │
│                                          │  │ Correction   │ ◄────── HUMAN CALIBRATION SET │
│                                          │  └──────┬───────┘   │         │
│                                          │         │           │         │
│                                          │  ┌──────▼───────┐   │         │
│                                          │  │ Bias         │   │         │
│                                          │  │ Mitigation   │   │         │
│                                          │  └──────┬───────┘   │         │
│                                          │         │           │         │
│                                          └─────────┼───────────┘         │
│                                                    ▼                      │
│                                       CALIBRATED SCORE + CI              │
│                                                    │                      │
│                          ┌─────────────────────────┼─────────────────┐   │
│                          ▼                         ▼                  ▼   │
│                  REGRESSION SUITE           DRIFT DETECTOR     HUMAN SPOT-CHECK │
│                  (compare v1.3.0           (output distribution  (sampling) │
│                   vs v1.3.1)                over time)                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Four layers:

1. **Corpus** (§3) — the inputs agents process during eval. Briefs, prompts, reference assets, expected-output ranges. Not "the answer key"; the *envelope of acceptable answers*.
2. **Rubrics** (§2) — per-agent, per-artifact-type scoring criteria with anchored levels. The "what good looks like."
3. **Judge panel + calibration** (§4–§5) — LLMs that score against rubrics, with their imperfect sensitivity/specificity corrected against human-labeled calibration data.
4. **Operationalization** (§6–§9) — regression suite, drift detection, spot-check protocol, governance.

---

## §2 PER-AGENT RUBRICS

Rubrics are the contract between "what the agent produces" and "what the judge evaluates." Each rubric:

- Is criterion-separated (no global "is this good?" score).
- Uses 4-level anchored descriptions (Excellent / Strong / Adequate / Weak) — odd-level scales force a non-committal middle; 4-level scales force a stance.
- Maps each criterion to one or more artifact fields the judge can ground against.
- Distinguishes **mandatory-to-pass** criteria (any "Weak" fails the artifact for that pipeline run) from **graded-quality** criteria (low scores logged but don't fail).

The rubric object schema is unified across agents:

```json
{
  "$id": "https://chitra.ai/eval/v1.3/rubric_object.json",
  "title": "CHITRA Eval Rubric",
  "type": "object",
  "required": ["rubric_id", "applies_to_agent", "applies_to_artifact", "criteria"],
  "properties": {
    "rubric_id": {"type": "string", "pattern": "^EVAL-[A-Z]+-[0-9]{3}$"},
    "applies_to_agent": {"enum": ["drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan"]},
    "applies_to_artifact": {"type": "string"},
    "rubric_version": {"type": "string"},
    "calibration_set_id": {"type": "string"},

    "criteria": {
      "type": "array",
      "minItems": 4,
      "maxItems": 12,
      "items": {
        "type": "object",
        "required": ["criterion_id", "criterion_name", "type", "levels", "field_references"],
        "properties": {
          "criterion_id": {"type": "string"},
          "criterion_name": {"type": "string"},
          "criterion_description": {"type": "string"},
          "type": {"enum": ["mandatory_to_pass", "graded_quality"]},
          "weight": {"type": "number", "minimum": 0, "maximum": 1, "description": "Used only when computing aggregate quality score"},
          "field_references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "JSONPath-like references to fields in the artifact the judge should ground against"
          },
          "levels": {
            "type": "object",
            "required": ["excellent", "strong", "adequate", "weak"],
            "properties": {
              "excellent": {"type": "object", "properties": {"score": {"const": 4}, "anchor": {"type": "string"}}},
              "strong": {"type": "object", "properties": {"score": {"const": 3}, "anchor": {"type": "string"}}},
              "adequate": {"type": "object", "properties": {"score": {"const": 2}, "anchor": {"type": "string"}}},
              "weak": {"type": "object", "properties": {"score": {"const": 1}, "anchor": {"type": "string"}}}
            }
          },
          "common_failure_modes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Patterns judges should specifically watch for"
          },
          "anti_pattern_exemplars": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific phrasings or moves that score Weak"
          }
        }
      }
    }
  }
}
```

The rest of this section instantiates rubrics for each agent. They are not exhaustive — production deployment will iterate — but they cover the quality dimensions each agent's v1.1 quality bar already names.

### §2.1 EVAL-DRISHTI-001 — Creative Brief Quality

**Applies to**: `creative_brief` artifact (v1.2 §F.1).

| # | Criterion | Type | Weight | Anchor for Excellent (4) | Anchor for Weak (1) |
|---|---|---|---|---|---|
| 1 | **Three-sentence defensibility** | mandatory | 0.20 | A judge can write a coherent 3-sentence summary capturing problem, audience, and core message without paraphrasing the brief verbatim. | Cannot summarize in 3 sentences without losing essential content or contradicting another section. |
| 2 | **Insight quality** | graded | 0.20 | Insight names a non-obvious truth that bridges current and desired perception. Surprises a category insider. Generalizable beyond this product. | Insight restates a category truism ("Indians like cricket", "young people are time-poor"). Could apply to any brand in the sector. |
| 3 | **Audience triangulation specificity** | mandatory | 0.15 | Day-in-the-life sketch contains concrete behaviors, time stamps, and choice moments — not adjectives. Persona is recognizable to a member of that audience. | Persona is a string of demographic + adjective stack ("urban millennial, ambitious, digital-first"). |
| 4 | **Two-concept divergence test** | graded | 0.15 | A judge can articulate two materially different concept directions that would both be valid responses to this brief. | Only one concept direction plausibly emerges; brief over-constrains. |
| 5 | **Tone spectrum positioning specificity** | graded | 0.10 | Tone scores are explained with reference to brand archetype + audience evidence, not by axis alone. | Tone scores are present but unjustified or contradict the day-in-the-life sketch. |
| 6 | **Mandatory completeness with traceability** | mandatory | 0.10 | Every mandatory has a `source` and, where regulatory, a `regulation_id` traceable to §G. | Mandatories present but ungrounded; "as per ASCI rules" with no specific rule cited. |
| 7 | **Success metrics measurability** | mandatory | 0.10 | Each metric has target, unit, measurement window, attribution model. Brand metrics have a measurement method. | Targets vague ("increase awareness"), windows missing, attribution undeclared. |

**Common failure modes the judge watches for**:
- Insight is a fact, not a tension.
- Audience defined by exclusion ("not your typical X") rather than positive description.
- Tone spectrum positions all in the middle (-1 to +1 across all axes) — non-commitment dressed as nuance.
- Mandatories list duplicates prohibitions ("don't make claims unsupported by data" twice in both lists).

**Anti-pattern exemplars** (any of these in the brief → Weak on the relevant criterion):
- "Target audience: 18-45 year olds across India."
- "Insight: consumers value quality and trust."
- "Tone: premium yet accessible, traditional yet modern, serious yet playful." (positions everywhere = positions nowhere)

### §2.2 EVAL-DISHA-001 — Concept Slate Quality

**Applies to**: `concept_slate` artifact (v1.2 §F.2).

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **3-of-3 test passage** | mandatory | 0.20 | Every approved concept clearly answers Yes to: solves the business problem? distinctive in category last 24 months? worth defending in pitch? | One or more approved concepts fail one of the three. |
| 2 | **Distinctiveness against category baseline** | graded | 0.20 | Judge cannot find a category campaign in last 24 months that pursues the same insight + execution territory. | At least one concept has a clear category twin or near-twin. |
| 3 | **Kill rationale rigor** | graded | 0.15 | Killed concepts have specific, falsifiable rationales tagged to one of the eight kill-tag categories. No "weak idea" tautologies. | Kill rationales are vague ("not strong enough", "didn't excite us"). |
| 4 | **Cultural risk register completeness** | mandatory | 0.15 | Every approved concept with any cultural touchpoint has its risk register populated. Mitigations are concrete, not "we'll be careful." | Risk register is present but empty for concepts that touch religion/caste/gender/region. |
| 5 | **Slate diversity** | graded | 0.10 | The 3-5 approved concepts pursue materially different propositions / executional territories / target sub-segments. | Slate is variations on the same idea ("rational version", "emotional version", "humorous version" of one concept). |
| 6 | **Production feasibility honesty** | graded | 0.10 | `production_complexity` ratings track real-world complexity (talent, locations, post-production). | All concepts rated "medium" complexity regardless of evident demands. |
| 7 | **Pitch architecture coherence** | graded | 0.10 | Pitch deck leads with insight before execution, has audience anchor before concept presentation, ends with a specific ask. | Pitch deck opens with execution; insight buried mid-deck; ask is generic. |

**Common failure modes**:
- "Distinctive in category" claimed without reference to specific competitor work.
- Cultural risk register populated with `level: low` for concepts that obviously touch religion or gender — risk minimization rather than risk assessment.
- Kill log is suspiciously short — Disha generated 12, killed 7, but the kill rationales are all "score too low" without diagnosis.

### §2.3 EVAL-ROOP-001 — Visual Direction Quality

**Applies to**: `concept_bible.visual_deck` artifact (v1.2 §F.3).

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **Mood board annotation specificity** | mandatory | 0.15 | Every reference has a rationale that names *what about it* applies (lighting register, color choice, composition logic) — not just "the mood." | Rationales are mood-words ("vibrant", "premium", "warm") without referent. |
| 2 | **Style frame production-readiness** | mandatory | 0.20 | Style frames specify aspect ratio, subject placement, lighting direction, color temperature, emotional cue. An external production house could brief crew from these alone. | Style frames are pretty pictures with one-line captions. |
| 3 | **Storyboard cinematic logic** | graded | 0.15 | Beat-to-beat camera and sound choices follow a coherent grammar (rhythm builds, pace varies meaningfully, sound cues align with image cuts). | Storyboard is a list of literal moments; no pacing variation; sound cues missing or generic. |
| 4 | **Type system Indic-script completeness** | mandatory | 0.10 | Required Indic scripts have specified typefaces with documented license. | Indic scripts listed but typeface column blank, or typeface chosen lacks weight range needed. |
| 5 | **Color system specification depth** | mandatory | 0.10 | Palette has hex + CMYK + Pantone where print is in scope. Color application logic stated (primary surfaces, accent rules). | Palette is hex-only; no application logic. |
| 6 | **Adaptation matrix completeness** | mandatory | 0.15 | Every format in §F.5's required list has an adaptation row with treatment notes. Hero idea survives across small surfaces. | Adaptation matrix lists formats but treatment is "shrink to fit." |
| 7 | **Visual-verbal alignment** | mandatory | 0.10 | Joint sign-off with Vaani is documented; visual register matches verbal voice archetype without contradiction. | Visual is moody/cinematic; verbal is bouncy/playful. No reconciliation in deck. |
| 8 | **AI-generated visual disclosure** | mandatory | 0.05 | All AI-generated assets carry C2PA Content Credentials. | AI-generated assets present without content credentials hash. |

### §2.4 EVAL-VAANI-001 — Verbal Direction Quality

**Applies to**: `concept_bible.verbal_deck` artifact (v1.2 §F.3) + tightened in v1.2.2 §7.1 + renamed in v1.2.3 §9.1.

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **Voice archetype consistency** | mandatory | 0.15 | Every script, headline, and caption reads as the same voice; the Hello-test line predicts the rest. | Voice shifts between formats — playful captions vs corporate scripts. |
| 2 | **Read-aloud test** | mandatory | 0.15 | Read aloud, copy sounds like a person, not a model. No tortured constructions, no AI-tells (overuse of "navigating", "in today's world", em-dashes). | Detectable AI-output cadence. Empty intensifiers ("truly", "really", "very"). |
| 3 | **Brand-identification test** | graded | 0.15 | A judge given three random copy lines plus the brand guideline can identify the brand 2-of-3 times. | Copy could fit any brand in the category. |
| 4 | **Indic-language native-speaker pass** | mandatory | 0.20 | Tamil/Hindi/Bengali/etc. copy reads as written-in-language, not translated-from-English. A native judge cannot identify English structural bones. | Copy reads as English sentences with Indic vocabulary. Code-mix is mechanical. |
| 5 | **Script timing fits to second** | mandatory | 0.10 | 6/15/30/60-second scripts read aloud within ±1 second of target. Pause and breath marked. | Scripts over- or under-fit by >3 seconds when read aloud at natural pace. |
| 6 | **Tagline ladder cohesion** | graded | 0.10 | Long/short/six-word/three-word/two-word forms communicate the same proposition, scaling appropriately. | Forms read as unrelated alternates. |
| 7 | **ASCI disclosure presence and integration** | mandatory | 0.10 | Required `#Ad`, AI-persona labels, qualification disclosures are present and read naturally — not retrofitted. | Disclosure tacked at end as separate line; reads as boilerplate. |
| 8 | **Sectoral disclaimer voice fit** | graded | 0.05 | Disclaimers (BFSI risk, SEBI MF, IRDAI, RBI APR) are integrated to brand voice where possible. | Disclaimer is generic legal-template language even when brand voice could accommodate softer phrasing. |

**Common failure modes**:
- Hinglish that reads as English with Hindi nouns swapped in.
- Six-word tagline is the long form truncated rather than re-conceived.
- Voice archetype declared as "Sage" but copy is hectoring (Ruler) or sarcastic (Jester).

### §2.5 EVAL-REKHA-001 — Asset Registry Quality

**Applies to**: `asset_registry` artifact (v1.2 §F.4).

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **Format coverage completeness** | mandatory | 0.20 | Every format Lakshya's media plan needs is exported, named per convention, present in registry. No "find me a 1:1 version" follow-ups possible. | Missing formats; registry lists exports but URIs return 404 on sample. |
| 2 | **Naming convention adherence** | mandatory | 0.10 | Every filename matches `{client}_{campaign}_{concept}_{format}_{lang}_{version}.{ext}`. | Inconsistent capitalization, missing language code, version number omitted. |
| 3 | **WCAG 2.2 AA compliance** | mandatory | 0.15 | Every asset's contrast ratio ≥4.5:1 body / ≥3:1 large text. Alt text present and meaningful (not "image"). Font sizes ≥12pt print / ≥14pt web. | Contrast failures present; alt text generic or absent. |
| 4 | **Brand guideline compliance** | mandatory | 0.15 | Logo clear-space respected. Colors within stated palette (hex match). Type to weight per spec. | Colors drift off-palette; logo at sub-spec clear-space; weight substitutions. |
| 5 | **ASCI disclosure embed quality** | mandatory | 0.10 | `#Ad`, AI-persona labels, qualification disclosures are visible, legible (not light grey on white), placed prominently — not in the dark-pattern zone. | Disclosures present but at minimum size, low contrast, peripheral. |
| 6 | **C2PA Content Credentials on AI assets** | mandatory | 0.05 | Every `ai_generated: true` asset has `content_credentials` hash. | AI-generated assets lack credentials. |
| 7 | **Version control discipline** | graded | 0.05 | Source files preserved at every version. Versions semantic (v1, v1.1, v2). | Source files missing; versions confused. |
| 8 | **Adaptation faithfulness** | graded | 0.10 | Hero idea survives across small surfaces — bus shelter (large, dense) and Story (vertical, single-message) both communicate. | Small surfaces lose the idea entirely. |
| 9 | **Production efficiency** | graded | 0.10 | Number of assets produced matches plan; no over- or under-production. | Over-production: 200 assets generated, 40 used. Under-production: missing platform-cuts. |

### §2.6 EVAL-GATI-001 — Motion Asset Quality

**Applies to**: `motion_asset_registry` artifact (v1.2.1 §F.7).

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **3-second scroll-stop test** | mandatory | 0.20 | First 3 seconds of every mobile cut, played muted in daylight, would stop a scroll. Judge confirms via blind playback. | Hook delayed past sec 3; first 3 sec is brand bug + logo reveal. |
| 2 | **Platform-spec correctness** | mandatory | 0.15 | Every cut matches its target platform's spec (aspect ratio, duration, codec, bitrate, safe zones). Verified against `chitra-resourcepack.platform.spec`. | Reel exported at 16:9; YouTube Short at 60s+ duration. |
| 3 | **Caption legibility at thumbnail** | mandatory | 0.10 | Burned-in captions readable at thumbnail size. Caption styled to brand type. | Captions present but illegible at scale; system font defaults. |
| 4 | **Audio mastering targets met** | mandatory | 0.10 | Loudness matches platform target (-16 LUFS streaming, -23 LUFS broadcast, -14 LUFS YouTube). True peak ≤ -1 dBTP. | Loudness off target; clipping present. |
| 5 | **Cut pacing platform-appropriate** | graded | 0.15 | Cut rhythm matches platform (0.8-2s cuts for Reels, 0.5-1.5s for TikTok/Moj, 3-8s for YouTube long, 2-4s for CTV). | Pacing uniform across platforms; YouTube cut feels like a Reel. |
| 6 | **AI-persona disclosure timing** | mandatory | 0.10 | ASCI-AI-001 timing satisfied: label in first 5 sec, at end, throughout speech if AI speaks. | AI persona used; label appears only at very end or only as a corner bug missing in opening. |
| 7 | **Sectoral disclaimer visibility** | mandatory | 0.05 | Required sectoral disclaimers (SEBI MF ≥5s + VO; BFSI APR; gaming addiction warning) meet visibility duration and VO requirements. | Disclaimer present but visible <3 sec; no VO when required. |
| 8 | **Deepfake / clone consent documented** | mandatory | 0.05 | Where likeness synthesis or voice clone used, `subject_consent_uri` is populated and validates against consent-vault. | Voice clone or face swap with `subject_consent_uri` null or invalid. |
| 9 | **Rights clearance complete** | mandatory | 0.05 | Music, talent, location, product placement, celebrity contract URIs all populated and valid. | Music license documentation missing; one cut uses uncleared track. |
| 10 | **Regional language variant fidelity** | graded | 0.05 | Multilingual variants linked. Each variant's dub aligns to source pacing; no awkward synchronization. | Variants missing for stated language list; dub lags speech. |

### §2.7 EVAL-LEHAR-001 — Content Calendar + Real-Time Response Quality

**Applies to**: `content_calendar` artifact (v1.2.1 §F.9). Also evaluated continuously per published `social_post`.

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **90-minute response window adherence** | mandatory | 0.20 | When a moment broke in the eval window, on-tone post live within 90 min. Backfilled from `chitra-calendar.moment.live_status` start timestamps vs publishing timestamps. | Posts live 4+ hours after moment; or 90-min posts that are off-brand. |
| 2 | **Trend decision rationale quality** | graded | 0.15 | Each trend's ride/observe/skip decision has a defensible rationale. Skipped trends would have damaged brand; ridden trends actually fit. | Decisions are reflexive (ride everything trending) or arbitrary (skip explanations are tautological). |
| 3 | **Cultural risk avoidance on trend rides** | mandatory | 0.10 | No trend ridden that mocks vulnerable groups, exploits tragedy, or rides communal flashpoints. Risk check populated. | Brand voice rode a meme with disability-mocking origin, or a tragedy-aestheticization trend. |
| 4 | **Content calendar diversity** | graded | 0.10 | Theme buckets balanced across the period; no single bucket >40% unless period type explicitly warrants. Platform-native adaptation visible. | Calendar is 70% promotional; same theme bucket dominates weeks. |
| 5 | **Festival/sports overlay alignment** | graded | 0.10 | Festivals/sports moments in window have planned posts tied; regional-only events have regional-language variants. | Festivals in window with no calendar response; or pan-India response to a regional festival. |
| 6 | **Community management SLA adherence** | mandatory | 0.10 | DM ≤2h, comment ≤4h, support mention ≤30min — observed compliance >90% across eval window. | Compliance <70%; high-severity mentions unresponded. |
| 7 | **ASCI disclosure on paid partnerships** | mandatory | 0.10 | Every `paid_partnership.is_paid=true` post has `#Ad` or platform-native label in first caption line. | Paid partnerships without disclosure or with disclosure buried in hashtag tail. |
| 8 | **Crisis-response escalation correctness** | mandatory | 0.10 | Items that should have escalated (mental-health flag, legal threat, child-safety concern) did escalate per protocol. | Issues that should have escalated were handled in-thread by Lehar. |
| 9 | **Brand voice consistency across moments** | graded | 0.05 | Reactive moment posts read as same brand as planned posts. No voice-shift to chase trend tone. | Brand voice abandoned for trend voice; brand becomes generic-trendy. |

### §2.8 EVAL-LAKSHYA-001 — Media Plan + Daily Optimization Quality

**Applies to**: `media_plan` (v1.2 §F.5) + `daily_optimization_log` (v1.2.1 §F.8).

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **Channel mix rationale defensibility** | mandatory | 0.15 | Each channel has a stated reach × cost × intent-fit rationale traceable to brief audience/objectives. | Channel mix is "what we always do"; rationale is generic. |
| 2 | **Andromeda-aware creative volume** | graded | 0.15 | Meta campaigns ship with creative-diversity high enough for Andromeda to match; multiple variants, multiple formats. | One ad per ad set; under-supplied creative starves the system. |
| 3 | **Audience architecture discipline** | mandatory | 0.10 | Lookalike layers tested separately, not stacked. Exclusion logic explicit. Custom audiences carry consent_artifact_id. | Audiences stacked indiscriminately; consent IDs missing on custom audiences. |
| 4 | **A/B test statistical validity** | mandatory | 0.10 | Tests declared with minimum detectable lift, sample sizes, expected duration. Tests aren't ended at "first significant" peek-and-stop. | Tests ended early; sample sizes <100 conversions per cell; "winner" called on noise. |
| 5 | **Attribution model declared and consistent** | mandatory | 0.10 | One attribution model named; all reporting uses it; switches between reports are flagged. | Attribution silently switches to flatter the campaign. |
| 6 | **DPDP-SENSITIVE-TARGETING compliance** | mandatory | 0.10 | No prohibited targeting basis used. Minor-targeting respects age floors. | Prohibited basis present; "religion-only" segmentation; under-18 in BFSI. |
| 7 | **ROAS curve trajectory** | graded | 0.10 | ROAS trends upward across campaign run; plateaus actively defended ("ceiling for this audience") or actioned. | Flat ROAS line passed as "stable"; no plateau diagnosis. |
| 8 | **Optimization log specificity** | graded | 0.10 | Every action has before-state, after-state, rationale, expected effect, and 24h-later measured effect backfilled. | Logs are "increased budget on best adset" without specifics. |
| 9 | **HITL gate adherence** | mandatory | 0.05 | Actions with `budget_shift_percent > 20` carry `hitl_triggered=true` and approver ID. No unilateral large shifts. | >20% shifts logged without HITL approval. |
| 10 | **AI Max text guidelines configured** | graded | 0.05 | For Google AI Max campaigns, `text_guidelines` set with brand voice examples. AI-generated copy stays on-brand. | AI Max campaigns running without text_guidelines; ad copy drifts off-brand. |

### §2.9 EVAL-PRAMAAN-001 — Performance Report + Learnings Dossier Quality

**Applies to**: `performance_report` (v1.2 §F.6) + `learnings_dossier` (v1.2.1 §F.11).

| # | Criterion | Type | Weight | Excellent | Weak |
|---|---|---|---|---|---|
| 1 | **5-minute executive readability** | mandatory | 0.15 | A non-marketer (CFO archetype) reads the executive summary in 5 min and knows what the money bought. Tested with synthetic CFO judge prompt. | Executive summary requires marketing-context to parse. |
| 2 | **Statistical honesty** | mandatory | 0.15 | Confidence intervals reported. "Not enough data" stated when true. Sample sizes explicit. No false precision. | Point estimates without intervals; tiny samples reported as definitive. |
| 3 | **Attribution model triangulation** | mandatory | 0.10 | ROAS reported through 2-3 attribution lenses; range explained. Single-model reporting flagged. | One number, one model, presented as truth. |
| 4 | **Creative scorecard diagnostic depth** | graded | 0.15 | Each asset's hook rate, CTR, VCR, conversion, fatigue slope reported. Top/bottom performers explained with hypothesis. | Scorecard is ranked list without diagnosis. |
| 5 | **Learnings actionability** | graded | 0.15 | What-worked / what-didn't / what-surprised / what-to-test-next all populated with concrete evidence and clear next-cycle actions. | Learnings are descriptive ("creative A did well") not actionable. |
| 6 | **Brief amendment specificity** | graded | 0.10 | Concrete edits proposed to next brief, with field references and evidence. | "Refine audience" with no field reference. |
| 7 | **DPDP privacy compliance** | mandatory | 0.10 | No individual-level data in any output. Cohort minimum ≥100 respected. Aggregations only. | Individual customer IDs, granular behavioral records present. |
| 8 | **Chart interpretability** | graded | 0.05 | Charts need no caption to interpret. Axes labeled. Scales honest. | Charts require text explanation; truncated y-axes mislead. |
| 9 | **Surprises surfaced rather than buried** | graded | 0.05 | `what_surprised` section captures unexpected wins/losses and their implications. Surprises are useful learnings. | Surprises buried in appendix or absent despite obvious anomalies in data. |

---

## §3 GOLDEN CORPUS DESIGN

### §3.1 What goes in the corpus

The corpus is the eval's input substrate — the briefs, prompts, and reference materials each agent sees during eval. Critically, it is **not** "the answer key." A creative brief about a fintech app does not have *the* right Drishti output; it has an envelope of acceptable outputs, plus characteristic failure modes to detect.

The corpus is structured by agent:

```
corpus/
├── drishti/
│   ├── canonical-pass/          # 20+ realistic onboarding packets
│   ├── ambiguity-stress/        # packets with missing/contradictory fields
│   ├── regulatory-edge/         # packets in BFSI, RMG, health, alcohol-surrogate
│   ├── cultural-sensitivity/    # packets touching religion, caste, region, gender
│   ├── multi-language/          # packets requiring regional language work
│   └── adversarial/             # packets that attempt prompt injection or compliance bypass
├── disha/
│   ├── canonical-pass/          # 20+ briefs with expected concept divergence
│   ├── distinctiveness-stress/  # briefs in saturated categories (D2C beauty, fintech, EdTech)
│   ├── cultural-risk/           # briefs that invite risky concept territory
│   └── adversarial/
├── roop/, vaani/, rekha/, gati/, lehar/, lakshya/, pramaan/
│   └── [parallel structure]
└── pipeline-end-to-end/
    ├── synthetic-tenant-A/      # full nine-agent pipeline on one brief
    ├── synthetic-tenant-B/
    └── [10-20 full runs]
```

### §3.2 Corpus item shape

```json
{
  "$id": "https://chitra.ai/eval/v1.3/corpus_item.json",
  "type": "object",
  "required": ["item_id", "agent", "category", "input", "expected_envelope", "failure_modes_to_detect"],
  "properties": {
    "item_id": {"type": "string"},
    "agent": {"enum": ["drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan"]},
    "category": {"enum": ["canonical_pass", "ambiguity_stress", "regulatory_edge", "cultural_sensitivity", "multi_language", "adversarial", "pipeline_end_to_end"]},
    "input": {
      "type": "object",
      "description": "The artifact(s) the agent under test receives — onboarding packet for Drishti, locked brief for Disha, concept bible for Rekha/Gati, etc."
    },
    "expected_envelope": {
      "type": "object",
      "description": "Not a fixed answer. The range of acceptable outputs.",
      "properties": {
        "must_include": {"type": "array", "items": {"type": "string"}, "description": "Things any acceptable output contains"},
        "must_exclude": {"type": "array", "items": {"type": "string"}, "description": "Things no acceptable output contains"},
        "minimum_scores_per_criterion": {"type": "object", "description": "Rubric criterion → minimum acceptable score (1-4)"},
        "qualitative_notes": {"type": "string"}
      }
    },
    "failure_modes_to_detect": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "mode": {"type": "string"},
          "evidence_pattern": {"type": "string", "description": "What an output exhibiting this failure looks like"},
          "severity": {"enum": ["critical", "high", "medium"]}
        }
      }
    },
    "human_calibration_grades": {
      "type": "array",
      "description": "Human-labeled scores for this item's outputs — used for judge calibration",
      "items": {
        "type": "object",
        "properties": {
          "grader_id": {"type": "string"},
          "graded_at": {"type": "string", "format": "date-time"},
          "rubric_scores": {"type": "object"},
          "rationale_notes": {"type": "string"}
        }
      }
    }
  }
}
```

### §3.3 Corpus sizing and balance

For each agent, target:

| Category | Minimum items | Refresh cadence |
|---|---|---|
| canonical_pass | 20 | Annually |
| ambiguity_stress | 8 | Annually |
| regulatory_edge | 10 (covering BFSI, RMG, health, alcohol-surrogate, tobacco, real-estate, EdTech, children-targeting, deepfake-adjacent, environmental-claim) | Quarterly (regulator updates) |
| cultural_sensitivity | 10 (covering religion, caste, region, gender, political, language) | Annually |
| multi_language | 12 (covering Hindi, English, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, plus 2 code-mixed) | Annually |
| adversarial | 6 (prompt injection variants, compliance bypass attempts) | Semi-annually |

Plus 10-20 **pipeline_end_to_end** corpus items that flow through all nine agents as full synthetic campaigns.

### §3.4 Corpus authoring discipline

Corpus items are written by humans, not generated by LLMs (a corpus generated by the same model class you're evaluating produces tautological eval). Authoring panel:

- **Lead author**: Senior strategist / creative director with 10+ years.
- **Sectoral reviewer per regulated sector**: BFSI specialist, healthcare-comms specialist, etc.
- **Cultural reviewer panel**: At minimum one reviewer each for South India, North India, East India, West India linguistic and cultural contexts.
- **DPDP / legal reviewer**: For compliance-edge items.

Items are versioned. When a rubric changes (§2 update), the corpus item's `expected_envelope.minimum_scores_per_criterion` may need re-grading.

### §3.5 Corpus must not leak into training

The corpus is never used to train or fine-tune any CHITRA agent or any LLM judge. Doing so makes the eval measure overfitting, not capability. Items are tagged `do_not_train` and the tag propagates through any data pipeline.

For agents that learn from past campaigns within a tenant (via `chitra-history.learnings.latest`), the corpus uses synthetic tenants with no real history.

---

## §4 LLM JUDGE PANEL

### §4.1 Why a panel, not a single judge

Single-judge eval has documented biases — position bias (favoring whichever output came first), verbosity bias (favoring longer outputs), self-enhancement bias (a model rating its own outputs higher), formality bias (favoring formal language even when the brief calls for casual). These are not edge cases; they're the typical failure mode.

A **judge panel** of 3 LLMs from different model families, with explicit bias-mitigation protocols, reduces each bias substantially. Per the 2026 literature, panel-of-three from independent families achieves >90% agreement with human reviewers on rubric-grounded scoring, versus ~85% for single-judge.

### §4.2 Panel composition (current as of May 2026)

```yaml
judge_panel_default:
  - judge_id: judge_anthropic
    model: claude-opus-4.7
    role: primary
    strengths: [nuanced reasoning, instruction adherence, low self-enhancement]

  - judge_id: judge_openai
    model: gpt-5
    role: secondary
    strengths: [structured output, factual grounding]

  - judge_id: judge_google
    model: gemini-2.5-ultra
    role: secondary
    strengths: [multimodal, multilingual incl. Indic]

aggregation: median_score_across_panel
disagreement_threshold: 1.0
  # If max-min score across panel > 1.0 on any criterion, escalate to human spot-check
self_enhancement_guard:
  # When agent under test was produced by judge_X's model family,
  # judge_X is excluded from that eval run
  active: true
```

The "self-enhancement guard" is non-negotiable. If the Drishti agent is running on Claude Opus 4.7 and the eval includes a Claude-family judge, that judge is excluded for self-evaluation runs. This prevents the family-favoritism failure mode.

### §4.3 Judge prompt structure

```
[JUDGE SYSTEM PROMPT — same template across panel members]

You are a judge evaluating a CHITRA agent's output against a defined rubric.
You are NOT improving the output. You are NOT producing a better version.
You are scoring against criteria, with anchored levels, grounded in the artifact.

For each rubric criterion:
1. Read the criterion description and level anchors.
2. Locate the field_references in the artifact.
3. Decide which level (Excellent=4, Strong=3, Adequate=2, Weak=1) best fits.
4. Cite specific evidence from the artifact for your decision.
5. Note any common_failure_modes you observed.

Bias-mitigation directives:
- Position bias: this is a single-output evaluation, but if comparing, score blind to order.
- Verbosity bias: longer is not better. A succinct strong output should outscore a wordy adequate one.
- Self-enhancement: you are not evaluating your own output; treat the artifact as independent.
- Formality bias: brand voice may call for casual or vernacular; do not penalize informality unless it contradicts the stated voice.

You must output:
- Per-criterion score (1-4)
- Per-criterion evidence (cite exact phrases or field values from the artifact)
- Per-criterion failure-modes-observed (from common_failure_modes list, if any)
- Overall confidence: high / medium / low (medium or low triggers human review)
- Refusal: if the artifact is unsafe to evaluate or you cannot ground a score, refuse — never guess.

Refuse rather than guess. The eval is more useful with honest abstentions than with confident noise.
```

### §4.4 Judge output schema

```json
{
  "$id": "https://chitra.ai/eval/v1.3/judge_output.json",
  "type": "object",
  "required": ["judge_id", "rubric_id", "artifact_id", "scored_at", "criterion_scores", "overall_confidence"],
  "properties": {
    "judge_id": {"type": "string"},
    "judge_model": {"type": "string"},
    "judge_model_version": {"type": "string"},
    "rubric_id": {"type": "string"},
    "rubric_version": {"type": "string"},
    "artifact_id": {"type": "string"},
    "artifact_hash": {"type": "string"},
    "scored_at": {"type": "string", "format": "date-time"},
    "criterion_scores": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["criterion_id", "score", "evidence"],
        "properties": {
          "criterion_id": {"type": "string"},
          "score": {"type": "integer", "minimum": 1, "maximum": 4},
          "evidence": {"type": "string"},
          "failure_modes_observed": {"type": "array", "items": {"type": "string"}},
          "refused": {"type": "boolean", "default": false},
          "refusal_reason": {"type": "string"}
        }
      }
    },
    "overall_confidence": {"enum": ["high", "medium", "low"]},
    "tokens_used": {"type": "integer"},
    "latency_ms": {"type": "integer"}
  }
}
```

---

## §5 CALIBRATION FRAMEWORK

### §5.1 Why calibration is non-optional

LLM judges have imperfect sensitivity (probability of correctly scoring Excellent when output is genuinely Excellent) and imperfect specificity (probability of correctly scoring not-Excellent when output isn't). The naive approach — "report the LLM judge's score" — embeds those errors as if they were truth.

The 2026 framework (Lee et al., arXiv:2511.21140) corrects this with bias-adjusted estimators and confidence intervals computed against a human-labeled calibration set. CHITRA adopts this framework.

### §5.2 Calibration set construction

For each rubric:

1. Sample 30–50 corpus items per rubric.
2. Have 2–3 expert humans score each item against the rubric independently.
3. Resolve disagreements through discussion to produce a "gold" score.
4. Compute inter-rater reliability (Cohen's κ or Krippendorff's α; target ≥0.7).
5. Store the gold-scored set as the calibration corpus.

The calibration set is refreshed:
- Whenever a rubric is amended (§2 changes).
- Whenever a judge model is added or replaced.
- Annually regardless.

### §5.3 Calibration math (operationally)

For each (judge, criterion) pair:

```
Let θ = true score distribution on the calibration set (from human golds)
Let p̂ = naive proportion the judge marks as "Excellent" (or any given level)
Let q₁ = judge sensitivity for that level (P(judge=L | true=L))
Let q₀ = 1 - judge specificity (P(judge=L | true≠L))

Bias-corrected estimator:
θ̂ = (p̂ - q₀) / (q₁ - q₀)

95% confidence interval computed via plug-in variance from the calibration set,
with adaptive sample allocation for tighter intervals on close cases.
```

The Resource Curator role (v1.2.2 §9.1) runs this once per calibration cycle. Every eval report from that calibration set forward reports bias-corrected scores with intervals — not raw judge proportions.

### §5.4 Calibration failure modes

| Failure | Detection | Response |
|---|---|---|
| Judge sensitivity collapses on a criterion (e.g., judge marks nothing as Excellent) | calibration shows q₁ < 0.3 | Rewrite criterion anchor; re-calibrate. Probably the anchor for Excellent is unreachable. |
| Judge has high false-positive rate (q₀ > 0.3) | calibration shows judge over-grades | Tighten judge prompt; add anti-pattern exemplars; consider replacing judge |
| Inter-judge variance > 1.0 on >25% of criteria | panel disagreement frequent | Rubric is ambiguous; criterion needs splitting or clarifying |
| Inter-human variance > 1.0 on calibration | humans disagree | Criterion is genuinely subjective; either refine or accept wider intervals |

---

## §6 REGRESSION SUITE

### §6.1 What it catches

When any of the following changes, run the regression suite:

- Foundation model upgrade (e.g., Claude Opus 4.7 → Claude Opus 5.0).
- Agent scaffold edit (v1.1 §1.1–§9 prompt changes).
- Compliance rule registry update (v1.2 §G changes).
- Resource Pack refresh (v1.1 §A changes).
- Rubric revision (§2 changes).
- Tool MCP server version bump.

Each regression run:

1. Re-executes every corpus item through the affected agent(s).
2. Scores via the calibrated judge panel.
3. Compares per-criterion scores against the prior baseline.
4. Flags regressions (>0.3 mean score drop on any criterion, or >2 corpus items moving from pass to fail).

### §6.2 Regression run schema

```json
{
  "$id": "https://chitra.ai/eval/v1.3/regression_run.json",
  "type": "object",
  "required": ["run_id", "triggered_by", "started_at", "baseline_run_id", "results"],
  "properties": {
    "run_id": {"type": "string"},
    "triggered_by": {"enum": ["model_upgrade", "scaffold_edit", "rule_update", "resource_pack_refresh", "rubric_revision", "tool_version_bump", "scheduled", "manual"]},
    "trigger_detail": {"type": "object"},
    "started_at": {"type": "string", "format": "date-time"},
    "completed_at": {"type": "string", "format": "date-time"},
    "baseline_run_id": {"type": "string"},
    "agents_under_test": {"type": "array", "items": {"type": "string"}},
    "corpus_items_run": {"type": "integer"},
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent": {"type": "string"},
          "rubric_id": {"type": "string"},
          "criterion_id": {"type": "string"},
          "baseline_mean_score": {"type": "number"},
          "current_mean_score": {"type": "number"},
          "score_delta": {"type": "number"},
          "confidence_interval_95": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
          "significance": {"enum": ["improved", "stable", "regressed_minor", "regressed_major"]},
          "items_moved_from_pass_to_fail": {"type": "integer"},
          "items_moved_from_fail_to_pass": {"type": "integer"}
        }
      }
    },
    "overall_verdict": {"enum": ["promote", "investigate", "block_deployment"]}
  }
}
```

### §6.3 Promote vs investigate vs block

- **Promote**: no criterion regressed_major; no >2 corpus items moved pass→fail. New version goes live.
- **Investigate**: 1 criterion regressed_minor OR 1-2 items moved pass→fail. Run more corpus items, human spot-check the regressions, then promote or refine.
- **Block deployment**: any criterion regressed_major OR >2 items moved pass→fail. Roll back or fix before deployment.

The verdict isn't a vote of confidence — it's a guard against silently shipping degradation.

---

## §7 DRIFT DETECTION

### §7.1 The problem regression suite doesn't catch

Regression suite catches sudden changes. Drift is gradual. A creative model that slowly converges on the same hook structure, the same insight shape, the same caption rhythm across all clients — that's catastrophic for an advertising agency, and it produces no per-run regression because each run is fine on its own.

Drift detection runs on **outputs over time**, not against a corpus.

### §7.2 What gets monitored

For each agent, weekly:

| Drift signal | Measurement |
|---|---|
| **Lexical convergence** | Type-token ratio across all outputs in a 4-week rolling window. Drop signals vocabulary narrowing. |
| **Hook pattern convergence** | First-3-second hook structures (for Gati cuts) and first-line caption structures (for Vaani/Lehar) clustered semantically. >40% concentration in one cluster triggers alert. |
| **Insight pattern convergence** | Drishti insights embedded and clustered. >35% concentration in one semantic cluster triggers alert. |
| **Concept territory convergence** | Disha approved concepts clustered by visual_direction + verbal_hook embedding. >40% concentration triggers alert. |
| **Format convergence** | Rekha/Gati output format distribution. If 80%+ of outputs are one format despite varied briefs → flag. |
| **Score plateau** | Mean rubric scores plateau OR creep up suspiciously. Inflation is as concerning as regression. |
| **Refusal rate** | Judge refusal rate. Spikes signal artifact quality degradation; drops signal judge calibration drift. |

### §7.3 Drift response

Drift triggers are alerts, not blocks. Investigations are human-led:

1. Surface the drift to Resource Curator.
2. Sample 10 outputs from the drifting period; spot-check.
3. If genuine drift: hypothesize cause (model update? Resource Pack stale? Rubric encouraging convergence?).
4. Counter-action: introduce diversity-bonus to agent scaffold; refresh corpus; add anti-pattern exemplars to rubric.
5. Re-measure 4 weeks later.

---

## §8 HUMAN SPOT-CHECK PROTOCOL

### §8.1 Sampling rate

Not every agent output is human-reviewed; that defeats the eval's purpose. Sampling rates by stake:

| Output type | Sample rate | Reviewer profile |
|---|---|---|
| `creative_brief` | 5% | Senior strategist |
| `concept_slate` | 10% | Creative director |
| `concept_bible` | 5% | Senior creative |
| `asset_registry` | 2% | Design lead |
| `motion_asset_registry` | 5% | Senior video |
| `media_plan` | 10% | Media director |
| `daily_optimization_log` | 1% | Media planner |
| `content_calendar` | 5% | Social strategist |
| `social_post` (published) | 2% | Social manager |
| `performance_report` | 100% | Brand owner + agency reviewer |
| `learnings_dossier` | 100% | Insights lead |

Performance reports and learnings dossiers are always human-reviewed because they feed the next cycle — letting noise propagate there compounds.

Sampling is **stratified**:
- 60% random.
- 25% flagged by judge panel `overall_confidence: medium|low`.
- 15% flagged by drift detection.

### §8.2 Spot-check task

Reviewer receives:
- The artifact.
- The judge panel's scores per criterion with evidence.
- The rubric.

Reviewer:
- Confirms or overrides each criterion score.
- Notes specific disagreements ("judge marked Strong on insight; I disagree, insight is a category truism — Adequate").
- Flags any rubric ambiguity ("criterion 3 not clear for this case").

### §8.3 Spot-check feeds calibration

Human spot-check scores become the next calibration set. Judge sensitivity/specificity is re-estimated every quarter from accumulated spot-checks. This is how the eval gets better over time without manual rubric edits — calibration tracks reality.

### §8.4 Inter-rater reliability target

Quarterly, sample 20 spot-checks and have a second reviewer independently score the same artifacts. Compute Krippendorff's α. Target ≥0.7. If lower, the rubric needs clarification — humans disagreeing is a rubric problem, not a human problem.

---

## §9 EVAL GOVERNANCE

### §9.1 The "who grades the graders" question

The judge panel evaluates agents. Calibration evaluates the panel. Human spot-checks evaluate calibration. But what evaluates the human spot-checks?

The answer is **inter-rater reliability and meta-review**:

- Quarterly inter-rater reliability check (§8.4).
- Annual external meta-review: bring in an outside creative panel to score 30-50 of the agency's spot-checks. Compare. If outside panel systematically diverges from internal reviewers on creative criteria, that's a sign internal taste has drifted (toward client-pleasing or risk-averse or genre-narrow).
- Continuous: capture cases where rubric scores predicted poor in-market performance correctly, and cases where they didn't. The eval's predictive validity is itself a meta-metric.

### §9.2 Roles in eval governance

| Role | Responsibility |
|---|---|
| **Resource Curator** (v1.2.2 §9.1) | Owns rubrics, corpus, calibration sets. Approves rubric changes. |
| **Eval Lead** | New role. Owns judge panel composition, calibration runs, regression suite operation. |
| **Human Reviewer Panel** | 5-10 senior practitioners (strategist, CD, copy, art, media, social, data) for spot-checks. Rotates annually to prevent calibration ossification. |
| **External Meta-Review Panel** | 3-5 outside practitioners. Convened annually. Independent of CHITRA tenant. |
| **DPO** (existing) | Eval data is corpus data and human spot-check data — both potentially contain personal/commercial information. DPO ensures eval data follows the same DPDP retention and consent posture as production data. |

### §9.3 What never enters eval

- Real client briefs without anonymization.
- Real audience PII (DPDP).
- Real consent artifact contents — only consent-artifact IDs as placeholder strings.
- Real ad spend numbers or ROAS results from live tenants (use synthetic numbers in eval corpora).

Eval cannot become a covert data-extraction channel.

### §9.4 Eval transparency to tenants

Each tenant can request:
- Latest regression run results for the agents they use.
- Drift detection alerts that affected their campaigns.
- Calibration set version and judge panel composition.

Tenants can opt their own anonymized outputs into the corpus authoring panel as case studies. Opt-out is default.

---

## §10 OPERATIONAL CADENCE

| Activity | Frequency | Owner |
|---|---|---|
| Run full corpus through all agents | Monthly | Eval Lead |
| Spot-check sampling | Continuous, weekly summary | Reviewer Panel |
| Drift detection review | Weekly | Eval Lead |
| Calibration set refresh (per rubric) | Quarterly + on rubric edit | Resource Curator |
| Regression run | On any trigger event (§6.1) | Eval Lead |
| Inter-rater reliability check | Quarterly | Eval Lead |
| External meta-review | Annually | Resource Curator + external panel |
| Rubric revision review | Semi-annually + on regulator change | Resource Curator |
| Corpus refresh (per category) | Per §3.3 cadence | Resource Curator + sectoral reviewers |
| Eval-as-meta-metric (predictive validity vs in-market) | Annually | Eval Lead + insights lead |

---

## §11 WHAT v1.3 DOES NOT INCLUDE (deliberate gaps)

1. **Automated rubric generation.** New rubrics for new artifact types are human-authored. LLM-suggested rubrics tend to converge on platitudes ("clarity", "engagement"); humans write better criteria.
2. **Per-tenant rubric customization.** Tenants get the same rubrics across the platform. Customization invites grade inflation by tenants who want softer rubrics. Tenant-specific concerns go in `tenant_context.regulatory_overrides`, not in eval.
3. **Real-time eval gating.** Eval scores do not block production. Compliance sanitizer blocks; eval informs. An agent producing low-eval-score work still ships if compliance passes — humans decide whether to use it.
4. **Single-number agent score.** No "Drishti is a 7.3/10" overall. The rubric is criterion-separated by design; collapsing to a number throws away the signal that matters (which criterion dropped?).
5. **Cross-tenant comparison.** CHITRA does not publish "agency A's Drishti scores higher than agency B's." Eval is per-tenant and per-deployment.
6. **In-market outcome correlation.** Predictive validity (does high eval score predict good ROAS?) is measured (§9.1) but not exposed as a real-time scoring signal — too noisy, too many confounds.

---

## §12 ROADMAP FROM HERE

| Version | What it adds | Earliest |
|---|---|---|
| **v1.3** (this) | Eval harness baseline | Now |
| **v1.3.x** | Rubric refinement; corpus expansion; calibration tightening; judge panel updates | Quarterly patches |
| **v1.4** | Closed-loop tenant learning: Pramaan → Drishti automated within tenant boundary, with eval-validated brief amendments | When v1.3 has 12+ months of calibration data |
| **v2.0** | Federated learning across tenants (the substrate that v1.4 makes safe) | Earliest 2027 H2 |

The eval harness is what makes v1.4 safe to ship. Without eval, automated brief amendments propagate model drift into client work. With eval, every amendment is regression-tested before it lands in production briefs.

---

## §13 SUMMARY

CHITRA v1.0 through v1.2.3 specified the contracts. CHITRA v1.3 measures the work.

The architecture has four layers — corpus, rubrics, calibrated judge panel, and operationalization (regression / drift / spot-check / governance) — and nine per-agent rubrics with 7–10 criteria each, anchored at four levels, with calibration-corrected scoring and confidence intervals.

What you get:
- For every artifact, a score per criterion with confidence interval, not a single number.
- Regression catches sudden degradation; drift catches gradual degradation.
- Calibration keeps judge scores aligned with human reality.
- Spot-checks are stratified — random sampling, judge-flagged sampling, drift-flagged sampling.
- External meta-review checks the internal review panel.
- Tenant transparency without cross-tenant exposure.

What you do not get:
- A magic "agent quality" number.
- Eval that gates production (compliance gates; eval informs).
- An answer key to "what is great creative." The eval is rigorous about quality assessment; it does not claim to know in advance what every excellent brief looks like.

The eval harness is the instrument. The work is still the work. The instrument keeps the instrument honest, the agents honest, and humans in the loop where humans need to be.

---

*End of CHITRA v1.3. Knowledge horizon: 16 May 2026. With v1.0 + v1.1 + v1.2 + v1.2.1 + v1.2.2 + v1.2.3 + v1.3, the platform substrate and the evaluation framework are both complete. The next document (v1.4) requires 12+ months of calibration data and a track record of regression-suite-validated promotions.*
