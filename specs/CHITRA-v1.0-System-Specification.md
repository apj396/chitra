# CHITRA v1.0
**Creative Hub for Intelligent Targeted Resonant Advertising**

A nine-agent creative-pipeline system designed for the Indian advertising and digital marketing industry.

> "Chitra" (चित्र) — Sanskrit for picture, image, or composition: the irreducible unit of creative communication. The platform is named in the language of the market it serves, not back-formed from English.

---

## §0 SYSTEM IDENTITY

**Designation**: CHITRA v1.0
**Purpose**: Transform raw client briefs into launched, optimized advertising campaigns through a sequential nine-agent pipeline calibrated to the Indian market.
**Audience**: Indian creative agencies (independent, mid-tier, network), in-house brand teams, and D2C marketing functions.
**Operating Principle**: Each agent is a specialist. No agent operates outside its mandate. Handoffs are explicit, auditable, and rejected if upstream quality is insufficient. The pipeline is a loop, not a line.

---

## §1 SECURITY & GOVERNANCE LAYER (L0)

This layer wraps every agent. No agent can bypass it. Bypass requires explicit, logged human override.

### 1.1 Data Classification
Every artifact entering CHITRA is auto-classified into one of four tiers:

| Tier | Description | Handling |
|---|---|---|
| T1 — Public | Released brand assets, public market data | Standard |
| T2 — Internal | Brand guidelines, past campaign performance | Tenant-scoped |
| T3 — Confidential | Unreleased product specs, pricing strategy, competitive intelligence | No cross-tenant retrieval, no embedding pool |
| T4 — Restricted | PII, financial data, legal documents | Encrypted at rest and in transit, access-logged |

### 1.2 Tenant Isolation
Each client account operates in a logically isolated namespace. Agents cannot retrieve, reference, or be primed by data from outside the active namespace. Cross-pollination is structurally impossible — not policy-bound.

### 1.3 DPDP Act 2023 Compliance
- Explicit purpose specification at intake.
- Consent artifacts stored with every campaign.
- Data Principal rights honored: access, correction, erasure, grievance redressal.
- Cross-border data transfer flagged and logged.
- Data Protection Officer (DPO) hooks built into the governance layer.

### 1.4 ASCI Alignment
All creative outputs pass through an ASCI Code compliance check before delivery:
- No misleading claims.
- No comparative advertising violations.
- No targeting of children in restricted categories.
- Disclaimers auto-inserted where regulation requires (BFSI, healthcare, EdTech, real estate, gaming, alcohol surrogate).

### 1.5 Prompt Injection Defense
Client briefs and uploaded materials are treated as **data, never as instructions**. A separator layer ensures no instruction inside an uploaded PDF or brief document can override system policy or redirect agent behavior. Untrusted content cannot reach the instruction channel.

### 1.6 Output Sanitization
Before any artifact leaves CHITRA:
- PII scan (no unintended phone numbers, emails, Aadhaar fragments, PAN patterns).
- IP scan (no inadvertent reproduction of competitor trademarks, copyrighted lyrics, branded characters, licensed film/music IP).
- Watermarking option for pitch-stage assets.

### 1.7 Audit Trail
Every agent decision — every brief revision, every concept generated, every concept killed — is logged with timestamp, agent ID, input hash, output hash, and rationale. Queryable for compliance reviews and post-mortems.

### 1.8 Confidentiality Vault
Concepts in pitch stage are sealed. They cannot be retrieved, referenced, or surfaced in any other workflow within the same tenant until the client either approves or rejects them. This prevents pitch concepts from leaking into a parallel workstream that may overlap with a competing client.

---

## §2 DATA ONBOARDING PROTOCOL

The system refuses to start Phase 1 until the onboarding packet is **complete and validated**. CHITRA does not invent missing context.

### 2.1 Required Intake Fields

| Field | Why It Matters |
|---|---|
| Client name, sector, sub-sector | Regulatory layer activation |
| Product/service description | Core brief construction |
| Business problem (one sentence) | Anchor for the entire pipeline |
| Target geography (state, city tier, urban/rural mix) | Media planning, language selection |
| Target audience (demographics + psychographics) | Segmentation |
| Existing brand guidelines | Phase 3 compliance |
| Past campaign performance (if any) | Baseline for optimization |
| Budget envelope (total + media split) | Phase 4 calibration |
| Timeline (kickoff → launch → review windows) | Pacing |
| Mandatory inclusions (claims, disclaimers, taglines) | Legal safeguards |
| Prohibited territory (themes, competitors, sensitivities) | Guardrails |
| Approval chain (who signs off at each stage) | Workflow routing |

### 2.2 Validation Gates
Missing or ambiguous fields trigger structured clarification questions to the user before Phase 1 opens.

### 2.3 India-Specific Intake Augments
- **Festival calendar overlay** — auto-detect proximity to Diwali, Holi, Onam, Eid, Pongal, Navratri, Ganesh Chaturthi, Durga Puja, Christmas, regional New Years.
- **Cricket calendar overlay** — IPL, ICC events, India tour windows.
- **Regional language preference** — 12+ supported; English-only is flagged as a deliberate choice, not a default.
- **Tier-1 / Tier-2 / Tier-3 city segmentation** — a first-class variable, not an afterthought.

---

## §3 PHASE 1 — STRATEGY & IDEATION

**Goal**: Transform a client's business problem into a clear creative brief.

### Agent 1: Drishti — Brand & Strategic Planner
*Drishti* (दृष्टि) — vision, insight.

**Mandate**: Convert ambiguous business pain into a sharp, defensible creative direction.

**Core Capabilities**:
- Market sizing (TAM/SAM/SOM) drawing on India-specific data sources (RedSeer, Kantar IMRB, Nielsen India, BARC, public filings).
- Consumer psychology models — Maslow, Means-End Chain, Jobs-to-be-Done — applied to Indian segments.
- Competitive landscape mapping — direct, indirect, category-adjacent.
- Cultural insight extraction — festival rhythms, family decision-making, regional sensibilities.
- Insight-to-Brief synthesis.

**Output Artifact — The Creative Brief**:
1. **Business Problem** (one sentence, no jargon).
2. **Target Audience** (demographics + psychographics + a "Day in the Life" sketch).
3. **Current Perception** (what the audience thinks today).
4. **Desired Perception** (what we want them to think after the campaign).
5. **The Insight** (the non-obvious truth that unlocks the gap).
6. **The Core Message** (single-minded proposition).
7. **Mandatories & Prohibitions**.
8. **Tone Spectrum** (positioned on axes: serious↔playful, premium↔accessible, traditional↔modern).
9. **Success Metrics** (brand metrics + business metrics).

**Performance Bar**: A brief that the Creative Director can defend in three sentences, and that the Art Director and Copywriter can each independently extract a *different* valid concept from. If only one concept fits the brief, the brief is too narrow.

### Agent 2: Disha — Creative Director
*Disha* (दिशा) — direction.

**Mandate**: Filter, sharpen, and champion. Disha is the system's first hard quality gate.

**Core Capabilities**:
- Concept evaluation against the brief (relevance), the category (distinctiveness), and the audience (resonance).
- "Kill criteria" — explicit reasons a concept dies, logged transparently so the system learns the pattern.
- Pitch architecture — translating internal concepts into client-facing narratives.
- Cultural risk scoring — identifying concepts that may misfire across religious, caste, gender, or regional lines.

**Output Artifact — The Concept Slate**:
- 3 to 5 approved concept territories, each carrying: a one-line proposition, a key visual direction, a key verbal hook, a target sub-segment, a confidence score, and a kill-risk register.
- A pitch deck draft for client presentation.

**Performance Bar**: Every concept Disha forwards must answer **yes** to all three: *Does it solve the business problem? Is it distinctive in this category? Would I bet my reputation on it in a pitch?* Concepts that score 2-of-3 are documented as "near-misses" for institutional learning but not advanced.

---

## §4 PHASE 2 — CONCEPTUALIZATION & WRITING

**Goal**: Develop the visual and verbal identity of the campaign.

### Agent 3: Roop — Art Director
*Roop* (रूप) — form, appearance.

**Mandate**: Give concepts a visual world.

**Core Capabilities**:
- Mood board construction — style, color, texture, photography vs. illustration, era references.
- Storyboard generation for video concepts — frame-by-frame logic, not just pretty pictures.
- Typography systems calibrated to brand voice and category convention.
- Visual hierarchy planning for multi-format adaptation — story, reel, hoarding, print.
- India-aware visual references — Bollywood-era cues, regional cinema aesthetics, modern Indian photography, urban vs. rural visual codes.

**Output Artifact**:
- Mood board (10–15 references, each annotated with the reason it's there).
- Storyboard for video concepts — beat sheet + key frames + camera notes.
- Style frames (3–5 hero compositions).
- Type and color system specification.

**Performance Bar**: An external designer should be able to execute the concept from Roop's deliverable without asking "what does this feel like?" twice.

### Agent 4: Vaani — Copywriter
*Vaani* (वाणी) — voice, speech.

**Mandate**: Craft language that grabs, holds, and moves.

**Core Capabilities**:
- Headline ladders — long-form → short-form → six-word.
- Hinglish and code-mixed writing where the audience naturally lives in both languages.
- Voice adaptation across brand archetypes (Sage, Hero, Lover, Jester, Caregiver, Rebel — Jungian frame).
- Platform-native length discipline — 15-second scripts that actually work in 15 seconds.
- Cultural idiom fluency — proverbs, film references, regional phrases that land for the target audience without alienating others.

**Output Artifact**:
- Primary tagline + 2 alternates.
- Long copy, short copy, micro copy variants.
- Video scripts with timing marks.
- Social caption library (10+ variants per concept).
- Voice & tone guide for the campaign run.

**Performance Bar**: Read aloud, the copy sounds like the brand — not like an AI, not like a generic agency template, not like a translation. If a native speaker of the target audience's primary language can't identify the brand from three lines of copy, the voice work isn't done.

---

## §5 PHASE 3 — PRODUCTION & EXECUTION

**Goal**: Produce high-quality visual, audio, and digital assets.

### Agent 5: Rekha — Graphic Designer & UI Designer
*Rekha* (रेखा) — line.

**Mandate**: Execute pixel-perfect, brand-consistent assets across every required format.

**Core Capabilities**:
- Format library: Instagram (feed/story/reel cover), Facebook, LinkedIn, X, WhatsApp business creatives, YouTube thumbnails, Google display ads, OOH (hoarding, bus shelter, mall facade), print (newspaper jacket, magazine spread), landing pages.
- Brand guideline enforcement — colors to hex, type to weight, logo to clear-space rules.
- Adaptation logic — one master concept rendered across all required dimensions without losing the central idea.
- Accessibility — contrast ratios, font sizes, alt-text generation.

**Output Artifact**:
- Master file (layered, source format).
- Format-adapted exports (each platform's exact spec).
- Asset registry with naming convention and version control.

**Performance Bar**: A media buyer should never have to ask "is there a 1:1 version of this?" Every asset that could be needed is already exported, named, and registered.

### Agent 6: Gati — Video Editor & Motion Graphics Artist
*Gati* (गति) — motion.

**Mandate**: Build motion content that survives the scroll.

**Core Capabilities**:
- Edit-pacing intelligence — cut rhythm calibrated to platform (fast for Reels and Shorts, measured for YouTube long-form).
- Audio design — music selection within licensable libraries, sound design layering, voice-over direction.
- Caption burning — 80% of mobile video plays muted; baked-in captions are not optional.
- Motion graphics — kinetic typography, brand-element animation, lower thirds.
- Platform spec mastery — aspect ratios, bitrates, codec, length caps, safe zones (the bottom 20% of a Reel is UI; the right edge of a YouTube Short is UI; safe-zone discipline is non-negotiable).

**Output Artifact**:
- Hero cut (full length).
- Platform cuts (6s, 15s, 30s, 60s as required).
- Soundless captioned versions.
- Thumbnail frames.

**Performance Bar**: First three seconds. If a viewer wouldn't stop scrolling for the first three seconds, the cut is rejected back into edit — regardless of how good the rest is.

### Agent 7: Lehar — Content Creator & Social Media Specialist
*Lehar* (लहर) — wave.

**Mandate**: Ride the live internet on behalf of the brand without losing the brand.

**Core Capabilities**:
- Trend detection across Instagram, Moj, ShareChat, Josh, YouTube Shorts, X.
- Cultural moment hijacking — cricket wins, film releases, festival mornings, viral memes — with on-brand framing.
- Community management protocols — response time bands, escalation paths for complaints, voice consistency across comments and DMs.
- Content calendar discipline — daily / weekly / monthly cadence, theme buckets, recycling logic.

**Output Artifact**:
- Monthly content calendar.
- Real-time response library (templated but customized).
- Trend pipeline (3–5 hookable trends per week with on-brand angles).
- Engagement reports.

**Performance Bar**: When a moment breaks — match win, ad-of-the-day, viral meme — the brand has an on-tone post live within 90 minutes. Not 24 hours. **90 minutes.**

---

## §6 PHASE 4 — DISTRIBUTION & OPTIMIZATION

**Goal**: Launch the campaign, track performance, and optimize for superior results.

### Agent 8: Lakshya — Performance Marketer & Media Buyer
*Lakshya* (लक्ष्य) — target, goal.

**Mandate**: Get the right asset to the right person at the lowest viable cost — then keep improving.

**Core Capabilities**:
- Platform expertise: Meta Ads Manager, Google Ads, DV360, The Trade Desk, Amazon Ads, JioAds, Hotstar/Disney+ programmatic.
- Audience architecture — lookalike modeling, retargeting waterfalls, interest stacking, exclusion logic.
- Budget pacing — daily / weekly / phase allocation, learning-phase budget protection, hero-spike planning around launches and festivals.
- A/B and multivariate testing — creative variants, audience variants, placement variants, with statistically valid sample sizing.
- Attribution awareness — last-click vs. data-driven vs. MMM, with honest acknowledgment of attribution gaps.

**Output Artifact**:
- Media plan (channel mix, budget split, flighting).
- Creative-trafficking sheet (every asset → every placement).
- Daily performance dashboard.
- Weekly optimization log (what was changed, why, with what effect).

**Performance Bar**: ROAS improvement curve must trend upward across the campaign run. A flat ROAS line is not "stable performance" — it is unoptimized media. Lakshya defends every plateau or accepts the rework.

### Agent 9: Pramaan — Data Analyst
*Pramaan* (प्रमाण) — proof, evidence.

**Mandate**: Convert noise into insight, and insight into the next brief.

**Core Capabilities**:
- GA4 architecture — events, conversions, custom dimensions, audience definitions.
- Looker Studio dashboard construction — executive view, campaign view, creative view.
- Statistical literacy — significance testing, confidence intervals, lift calculation, honest reporting of "not enough data yet."
- Creative-performance correlation — which hooks worked, which visuals fatigued, which audiences converted, which didn't.
- Closed-loop reporting — feeding learnings back to Drishti for the next brief.

**Output Artifact**:
- Campaign performance report (ROI, ROAS, brand lift if measured).
- Creative scorecard (every asset ranked, with diagnostic notes).
- Learnings dossier — what worked, what didn't, what to test next.
- Recommendation memo for the next campaign cycle.

**Performance Bar**: The report a non-marketer (CFO, founder, client-side procurement) can read in five minutes and walk away knowing what the money bought. Charts that need explaining are charts that have failed.

---

## §7 INTER-PHASE HANDOFF PROTOCOLS

A handoff is **not** a forward. It is a contract.

- **Phase 1 → Phase 2**: Disha's concept slate is locked. Roop and Vaani cannot reopen strategy; they can only flag if execution reveals a strategic fault, which routes back to Drishti for resolution.
- **Phase 2 → Phase 3**: Roop and Vaani sign off jointly. No production starts on a concept where art and copy are misaligned.
- **Phase 3 → Phase 4**: Asset registry must be complete. Lakshya does not launch with "draft" assets; she returns them.
- **Phase 4 → Phase 1 (Next Cycle)**: Pramaan's learnings dossier is mandatory input to the next campaign's Drishti briefing. The pipeline is a loop, not a line.

---

## §8 QUALITY GATES & GUARDRAILS

Each gate is a hard stop. Bypass requires explicit human override with logged reason.

| Gate | Owner | Trigger for Stop |
|---|---|---|
| G1 — Brief Validity | Drishti → User | Missing intake fields |
| G2 — Strategic Coherence | Disha | Concepts fail relevance / distinctiveness / resonance |
| G3 — Art-Copy Alignment | Roop + Vaani | Visual and verbal contradict each other |
| G4 — Production Quality | Rekha / Gati | Asset below spec |
| G5 — Compliance | L0 Security Layer | ASCI / DPDP / IP / sectoral regulation breach |
| G6 — Launch Readiness | Lakshya | Assets, audiences, or budgets not finalized |
| G7 — Performance Sanity | Pramaan | Reported numbers fail statistical sanity checks |

---

## §9 INDIA-SPECIFIC OPERATING LAYER

This is the layer that distinguishes CHITRA from a generic global tool.

### 9.1 Regulatory
- **ASCI Code** — full ruleset embedded; sectoral codes (BFSI, healthcare, EdTech, real-money gaming, alcohol surrogate, tobacco) applied automatically.
- **DPDP Act 2023** — consent, purpose limitation, data principal rights.
- **Consumer Protection Act 2019 (Misleading Ads)** — claim substantiation requirements.
- **IT Rules 2021** — intermediary obligations, grievance officer hooks.
- **Sector regulators** — RBI (BFSI), SEBI (markets), IRDAI (insurance), TRAI (telecom), MoHFW (health), Drugs and Magic Remedies Act (health claims).

### 9.2 Linguistic
- 12+ Indian languages supported as **first-class** creative languages, not translation afterthoughts.
- Code-mixing (Hinglish, Tanglish, Benglish) handled natively.
- Script handling — Devanagari, Tamil, Telugu, Bengali, Gujarati, Kannada, Malayalam, Punjabi (Gurmukhi), Odia, Urdu (Nastaliq).

### 9.3 Cultural
- Festival calendar live overlay.
- Cricket calendar live overlay.
- Regional cinema reference libraries — Bollywood, Tollywood, Kollywood, Mollywood, Sandalwood, Bengali, Marathi.
- Tier-wise consumer behavior heuristics — Tier-1 aspirational, Tier-2 family-first, Tier-3 value-anchored — calibrated, not stereotyped.

### 9.4 Platform Reality
- **WhatsApp** as a first-class marketing channel, not an afterthought.
- **JioCinema / Hotstar** for video at scale.
- **ShareChat / Moj / Josh** for Tier-2/3 reach.
- **YouTube** as the longest-watched platform in the country.
- **UPI-linked** conversion flows where applicable.

---

## §10 OUTPUT & DELIVERY STANDARDS

Every CHITRA output carries:
- **Provenance header** — which agents touched it, in what order, with what inputs.
- **Compliance footer** — which checks passed, which were waived with override.
- **Confidence band** — high / medium / low, with the basis for the rating.
- **Version tag** — semantic versioning: major.minor.patch.

---

## §11 HUMAN-IN-THE-LOOP

CHITRA is not autonomous. It is a force multiplier.

- **Mandatory human approval** at: brief lock, concept selection, pre-launch, mid-flight optimization beyond a threshold (e.g., >20% budget reallocation), final report.
- **Optional human review** at any gate, on request.
- **Override logging** — any human decision that overrides an agent recommendation is logged with reason, both to learn from and to defend.

---

## §12 ROADMAP

| Version | Scope |
|---|---|
| **v1.0** (this document) | Architecture and pipeline definition |
| **v1.1** | Agent-level prompt scaffolds, ready for implementation |
| **v1.2** | Tool integration layer (Adobe APIs, Meta/Google Ads APIs, GA4 connector) |
| **v1.3** | Multi-tenant orchestration; client-side dashboard |
| **v2.0** | Closed-loop learning across campaigns within a tenant (without cross-tenant leakage) |

---

*End of CHITRA v1.0 specification.*
