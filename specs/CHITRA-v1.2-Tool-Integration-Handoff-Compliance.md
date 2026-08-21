# CHITRA v1.2
**Tool Integration Scaffolds + Verifiable Handoff Schemas + Codified Compliance Ruleset**

> **Knowledge horizon**: All dynamic data current as of **16 May 2026**.
> **Builds on**: CHITRA v1.0 (architecture), v1.1 (agent scaffolds + Global Dynamic Resource Pack).
> **What this version adds**: Three things, in this order — (1) verifiable per-agent handoff schemas, (2) a codified compliance ruleset that an output sanitizer can actually run, (3) the MCP-based tool integration layer that turns each agent from a text-generator into an API operator.

---

## §0 WHY THESE THREE THINGS BELONG TOGETHER

Tool integration without verifiable handoff contracts is a leak: a downstream agent will accept malformed work and fail silently. Tool integration without codified compliance rules is a liability: an agent with a Meta Ads API key and no rule engine *will* eventually launch a campaign that breaches ASCI or DPDP. So v1.2 ships all three as one substrate.

```
                ┌──────────────────────────────────────────────┐
                │  v1.1: Agent Scaffolds (text-only prompts)   │
                └──────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        │                          v1.2                                │
        ├──────────────────────────────┬──────────────────────────────┤
        │  §A–E  Tool Integration      │  §F  Verifiable Handoff      │
        │        (MCP, per-agent       │       Schemas (per-artifact   │
        │        manifests, auth)      │       JSON contracts)         │
        ├──────────────────────────────┴──────────────────────────────┤
        │  §G  Codified Compliance Ruleset (predicate functions)       │
        │  §H  Output Sanitizer (consumes G, gates all I/O)            │
        └──────────────────────────────────────────────────────────────┘
```

The order matters. Read §F before §A — knowing what each agent *must emit* tells you what tools it *needs to call*. Read §G before §H — the rules define what the sanitizer checks.

---

## §A TOOL ARCHITECTURE — MCP-FIRST

### A.1 Why MCP

The Model Context Protocol, donated to the Linux Foundation in December 2025, is the de facto standard for AI-tool integration as of 2026. Every major LLM client speaks MCP. 9,400+ public servers exist. The protocol reduces the N×M integration problem to N+M, and the cost of adoption is near zero.

CHITRA agents are MCP **clients**. Every external service (Meta, Google, JioAds, GA4, Adobe, Figma, Bhashini, internal asset DB) is fronted by an MCP **server** — either an official one or a CHITRA-maintained wrapper around a REST/GraphQL/SDK surface.

### A.2 Hub-and-spoke topology

```
                          ┌────────────────────┐
                          │  L0 Security Layer │
                          │   + Audit Sink     │
                          └─────────┬──────────┘
                                    │
   ┌─────────┬─────────┬─────────┬─┴───────┬─────────┬─────────┬─────────┐
   │Drishti  │Disha    │Roop     │Vaani    │Rekha    │Gati     │Lakshya  │  ... Pramaan, Lehar
   │(client) │(client) │(client) │(client) │(client) │(client) │(client) │
   └────┬────┴────┬────┴────┬────┴────┬────┴────┬────┴────┬────┴────┬────┘
        │         │         │         │         │         │         │
        └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                                    │
                          ┌─────────┴──────────┐
                          │   MCP Tool Mesh    │
                          │   (auth + rate +   │
                          │    audit + cost)   │
                          └─────────┬──────────┘
                                    │
   ┌──────┬──────┬──────┬──────┬───┴──┬──────┬──────┬──────┬──────┬──────┐
  Meta   Google  Bhashini Figma Adobe GA4   JioAds Amazon Ads   ... etc.
```

Every tool call passes through the **MCP Tool Mesh** — a single chokepoint that enforces auth, rate limits, audit logging, and cost accounting. Agents never call tools directly. Even if a model "knows" a REST endpoint, calls outside the mesh are dropped by the L0 wrapper.

### A.3 MCP server inventory (CHITRA v1.2 baseline)

| MCP Server | Type | Purpose | Used By |
|---|---|---|---|
| `chitra-search` | Wrapper | Web search (Perplexity / Tavily / Bing) | Drishti, Disha, Lehar |
| `chitra-marketdata` | Wrapper | RedSeer, Kantar, Nielsen, BARC, Comscore APIs | Drishti, Pramaan |
| `chitra-calendar` | Native | Festival + cricket + sports calendar (A.2/A.3 from v1.1) | All |
| `chitra-regdb` | Native | Live regulatory database (A.1 from v1.1) | All |
| `chitra-assetdb` | Native | Tenant-scoped asset registry | Rekha, Gati, Lakshya, Lehar |
| `chitra-history` | Native | Past campaigns within tenant | Drishti, Disha, Pramaan |
| `bhashini-mcp` | Wrapper | Indian-language translation, STT, TTS | Vaani, Gati, Lehar |
| `adobe-firefly` | Official | Generative Fill / Expand / Image | Roop, Rekha |
| `adobe-creative-cloud` | Wrapper | Photoshop, Illustrator, Premiere, AE | Rekha, Gati |
| `figma-mcp` | Official | Figma file CRUD, Dev Mode | Roop, Rekha |
| `canva-mcp` | Official | Templates, Bulk Create, Brand Kit | Rekha |
| `runway-mcp` | Official | Generative video | Gati |
| `elevenlabs-mcp` | Official | Multilingual TTS, voice clones | Gati, Vaani |
| `meta-marketing` | Official | Meta Ads (v25.0+) | Lakshya, Lehar |
| `meta-ads-cli` | Official | Meta Ads CLI for agent workflows (Apr 2026) | Lakshya |
| `google-ads-mcp` | Official | Google Ads API (v23.1+, monthly cadence) | Lakshya |
| `google-analytics-mcp` | Official | GA4 Data API + Admin API | Pramaan |
| `looker-studio-mcp` | Official | Dashboard CRUD, scheduled delivery | Pramaan |
| `bigquery-mcp` | Official | Unsampled GA4 export | Pramaan |
| `jioads-mcp` | Wrapper | JioAds + JioHotstar inventory | Lakshya |
| `amazon-ads-mcp` | Wrapper | Sponsored Products / Brands / Display / DSP | Lakshya |
| `dv360-mcp` | Wrapper | Display & Video 360 | Lakshya |
| `whatsapp-business` | Official | WhatsApp Cloud API templates | Lakshya, Lehar |
| `youtube-mcp` | Official | YouTube Data API + Shorts upload | Gati, Lehar, Pramaan |
| `linkedin-marketing-mcp` | Wrapper | LinkedIn campaigns + Pages | Lakshya, Lehar |
| `x-marketing-mcp` | Wrapper | X (Twitter) Ads + posts | Lakshya, Lehar |
| `sprinklr-mcp` | Wrapper | Social management, listening, response | Lehar |
| `legal-precheck` | Native | Internal trademark + IP clearance lookup | Drishti, Disha, Roop, Vaani |
| `chitra-sanitizer` | Native | The output sanitizer from §H | All (mandatory on every output) |

> **Native** = built and maintained inside CHITRA. **Official** = published by the vendor. **Wrapper** = CHITRA wraps a non-MCP API surface into MCP for uniform invocation.

### A.4 Server versioning policy

External APIs version on their own cadence. Google Ads ships monthly. Meta Marketing ships ~quarterly with periodic breaking versions (v25.0 introduced unified Advantage+ structure). CHITRA pins each MCP server to a tested version and runs a weekly compatibility job:

```
Job: mcp-compatibility-sweep
Cadence: every Monday 06:00 IST
Steps:
  1. For each pinned MCP server, pull latest manifest.
  2. Diff against pinned version.
  3. Flag breaking changes (renamed fields, removed methods, auth changes).
  4. Open ticket to Resource Curator with severity.
  5. Auto-bump non-breaking minor versions only.
```

This is the operational defense against the "monthly Google Ads release silently broke our pipeline" failure mode.

---

## §B PER-AGENT TOOL MANIFESTS

Each agent declares — at runtime, via its system prompt — exactly which tools it may call. Tools outside the manifest are inaccessible. This is least-privilege by construction.

### B.1 Drishti — Strategic Planner

```yaml
agent: drishti
version: 1.2
tools_allowed:
  - chitra-search:
      methods: [web_search, web_fetch]
      scope: market_research_only
  - chitra-marketdata:
      methods: [redseer.query, kantar.query, nielsen.query, barc.query]
      scope: read
  - chitra-calendar:
      methods: [festivals.in_range, sports.in_range]
  - chitra-regdb:
      methods: [rules.by_sector, rules.by_audience_age, rules.by_claim_type]
  - chitra-history:
      methods: [campaigns.by_client, learnings.latest]
      scope: tenant_only
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
tools_denied:
  - any_publishing_tool
  - any_ads_platform
  - any_asset_db_write
budget:
  search_calls_per_brief: 25
  marketdata_calls_per_brief: 15
```

### B.2 Disha — Creative Director

```yaml
agent: disha
version: 1.2
tools_allowed:
  - chitra-search:
      methods: [web_search]
      scope: competitor_intel + cultural_reference
  - chitra-history:
      methods: [campaigns.competitor_archive, concepts.killed_log]
  - chitra-calendar:
      methods: [festivals.in_range, sports.in_range]
  - chitra-regdb:
      methods: [rules.by_sector, rules.cultural_risk_register]
  - legal-precheck:
      methods: [trademark.search, ip.clearance_check]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
tools_denied:
  - any_publishing_tool
  - any_ads_platform
  - any_asset_db_write
budget:
  search_calls_per_slate: 30
  legal_precheck_calls_per_slate: 10
```

### B.3 Roop — Art Director

```yaml
agent: roop
version: 1.2
tools_allowed:
  - chitra-search:
      methods: [image_search, web_fetch]
      scope: visual_reference_only
  - adobe-firefly:
      methods: [generate.image, generate.fill, generate.expand]
      content_credentials: required
  - figma-mcp:
      methods: [file.create, file.read, file.update]
      scope: tenant_workspace_only
  - chitra-assetdb:
      methods: [moodboard.write, styleframe.write, storyboard.write]
      scope: tenant + campaign
  - legal-precheck:
      methods: [trademark.search, image_rights.check]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
tools_denied:
  - any_publishing_tool
  - any_ads_platform
budget:
  firefly_generations_per_concept: 40
  figma_operations_per_concept: 100
```

### B.4 Vaani — Copywriter

```yaml
agent: vaani
version: 1.2
tools_allowed:
  - chitra-search:
      methods: [web_search]
      scope: cultural_idiom + voice_reference
  - bhashini-mcp:
      methods: [translate, transliterate, tts.preview]
      languages: [hi, en, ta, te, bn, mr, gu, kn, ml, pa, or, ur, as]
  - elevenlabs-mcp:
      methods: [tts.scratch_track]
      scope: vo_proof_only
  - legal-precheck:
      methods: [trademark.search, slogan.clearance]
  - chitra-regdb:
      methods: [disclaimers.by_sector, asci.disclosure_rules]
  - chitra-assetdb:
      methods: [copy.write]
      scope: tenant + campaign
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
budget:
  bhashini_calls_per_campaign: 200
  elevenlabs_seconds_per_campaign: 600
```

### B.5 Rekha — Graphic & UI Designer

```yaml
agent: rekha
version: 1.2
tools_allowed:
  - adobe-creative-cloud:
      methods: [photoshop.*, illustrator.*, indesign.*]
  - adobe-firefly:
      methods: [generate.image, generate.fill]
      content_credentials: required
  - figma-mcp:
      methods: [file.*, dev_mode.*]
  - canva-mcp:
      methods: [template.*, bulk_create, brand_kit.*]
  - chitra-assetdb:
      methods: [asset.write, asset.version, registry.update]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
budget:
  cloud_render_minutes_per_campaign: 240
```

### B.6 Gati — Video Editor & Motion Graphics

```yaml
agent: gati
version: 1.2
tools_allowed:
  - adobe-creative-cloud:
      methods: [premiere.*, after_effects.*, audition.*]
  - runway-mcp:
      methods: [generate.video, generate.lipsync, expand]
      content_credentials: required
  - elevenlabs-mcp:
      methods: [tts.production, voice_clone.use]
      consent_required: true
  - bhashini-mcp:
      methods: [tts, captions.generate, dub.assist]
  - youtube-mcp:
      methods: [thumbnail.test, video.upload_draft]
      scope: tenant_channel
  - chitra-assetdb:
      methods: [motion_asset.write, registry.update]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
budget:
  runway_seconds_per_campaign: 300
  elevenlabs_seconds_per_campaign: 1800
```

### B.7 Lehar — Content Creator & Social Media

```yaml
agent: lehar
version: 1.2
tools_allowed:
  - chitra-search:
      methods: [web_search, trend_lookup]
  - meta-marketing:
      methods: [post.publish, story.publish, reel.publish, comment.respond]
      scope: tenant_pages_only
  - youtube-mcp:
      methods: [short.publish, video.publish, comment.respond]
  - linkedin-marketing-mcp:
      methods: [post.publish, comment.respond]
      scope: tenant_pages_only
  - x-marketing-mcp:
      methods: [tweet.publish, reply, dm.respond_with_consent]
  - whatsapp-business:
      methods: [template.send, broadcast.send]
      consent_check: required
  - sprinklr-mcp:
      methods: [listen.*, respond.*, schedule.*]
  - bhashini-mcp:
      methods: [translate, transliterate]
  - chitra-assetdb:
      methods: [calendar.write, post.log]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
budget:
  posts_per_day: 25  # across platforms, tenant
  whatsapp_marketing_msgs_per_day: as_per_opt_in_list
```

### B.8 Lakshya — Performance Marketer & Media Buyer

```yaml
agent: lakshya
version: 1.2
tools_allowed:
  - meta-marketing:
      methods: [campaign.*, adset.*, ad.*, audience.*, report.read]
      version_pin: v25.0
  - meta-ads-cli:
      methods: [agent_workflow.*]
  - google-ads-mcp:
      methods: [campaign.*, ad_group.*, asset.*, keyword.*, audience.*, report.read]
      version_pin: v23.1
      auto_bump: minor_only
  - jioads-mcp:
      methods: [campaign.*, inventory.*, report.read]
  - amazon-ads-mcp:
      methods: [campaign.*, sb.*, sd.*, sp.*, dsp.read]
  - dv360-mcp:
      methods: [io.*, lineitem.*, report.read]
  - linkedin-marketing-mcp:
      methods: [campaign.*]
  - x-marketing-mcp:
      methods: [campaign.*]
  - whatsapp-business:
      methods: [click_to_chat_ad.config, template.submit]
  - chitra-assetdb:
      methods: [asset.read, trafficking_sheet.write]
  - chitra-regdb:
      methods: [targeting.prohibited_bases, audience.minor_check]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
human_in_the_loop_gates:
  - campaign.launch
  - budget.shift > 20%
  - audience.new_segment
  - creative.refresh
budget:
  daily_optimization_actions: 50
```

### B.9 Pramaan — Data Analyst

```yaml
agent: pramaan
version: 1.2
tools_allowed:
  - google-analytics-mcp:
      methods: [data.run_report, admin.*, audience.read]
  - bigquery-mcp:
      methods: [query.run, dataset.read]
      scope: tenant_project_only
  - looker-studio-mcp:
      methods: [dashboard.*, schedule.*, embed.create]
  - meta-marketing:
      methods: [report.read, insights.read]
  - google-ads-mcp:
      methods: [report.read, insights.read]
  - jioads-mcp:
      methods: [report.read]
  - amazon-ads-mcp:
      methods: [report.read]
  - chitra-history:
      methods: [campaigns.write_learnings]
  - chitra-sanitizer:
      methods: [validate]
      mandatory_on_output: true
privacy_constraints:
  individual_level_data: forbidden_in_output
  cohort_minimum: 100  # GA4 thresholding respected
  retention_days: per_dpdp_policy
```

---

## §C TOOL FUNCTION SIGNATURES (illustrative — key methods)

Each MCP method publishes a JSON Schema for inputs and outputs. The five most consequential are detailed here; the rest follow the same shape. Full signatures live in the MCP server registry.

### C.1 `bhashini-mcp.translate`

```json
{
  "name": "translate",
  "description": "Translate text between Indian languages and English via Bhashini DPI.",
  "input_schema": {
    "type": "object",
    "required": ["text", "source_lang", "target_lang"],
    "properties": {
      "text": {"type": "string", "maxLength": 10000},
      "source_lang": {"enum": ["en", "hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "or", "ur", "as"]},
      "target_lang": {"enum": ["en", "hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "or", "ur", "as"]},
      "domain": {"enum": ["general", "advertising", "legal", "healthcare", "finance"], "default": "advertising"},
      "preserve_brand_terms": {"type": "array", "items": {"type": "string"}}
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "translation": {"type": "string"},
      "model_used": {"type": "string"},
      "confidence": {"type": "number", "minimum": 0, "maximum": 1},
      "transliteration_available": {"type": "boolean"}
    }
  },
  "rate_limit": "100 req/min/tenant",
  "cost_band": "free_tier_for_low_volume"
}
```

### C.2 `meta-marketing.campaign.create`

```json
{
  "name": "campaign.create",
  "description": "Create a Meta Marketing campaign (v25.0 unified Advantage+ structure).",
  "input_schema": {
    "type": "object",
    "required": ["account_id", "name", "objective", "status", "special_ad_categories"],
    "properties": {
      "account_id": {"type": "string", "pattern": "^act_[0-9]+$"},
      "name": {"type": "string", "maxLength": 400},
      "objective": {"enum": [
        "OUTCOME_AWARENESS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT",
        "OUTCOME_LEADS", "OUTCOME_APP_PROMOTION", "OUTCOME_SALES"
      ]},
      "status": {"enum": ["PAUSED", "ACTIVE"], "default": "PAUSED"},
      "special_ad_categories": {
        "type": "array",
        "items": {"enum": ["CREDIT", "EMPLOYMENT", "HOUSING", "ISSUES_ELECTIONS_POLITICS", "ONLINE_GAMBLING_AND_GAMING"]},
        "description": "REQUIRED. Empty array if none apply. Misclassification is a compliance violation."
      },
      "buying_type": {"enum": ["AUCTION", "RESERVED"], "default": "AUCTION"},
      "campaign_budget_optimization": {"type": "boolean"},
      "daily_budget": {"type": "integer", "description": "In account currency minor units"}
    }
  },
  "pre_call_hooks": [
    "chitra-sanitizer.validate_targeting",
    "chitra-regdb.check_special_ad_categories",
    "audit.log_intent"
  ],
  "post_call_hooks": [
    "audit.log_result",
    "cost.record"
  ],
  "human_in_the_loop": "required_for_launch"
}
```

### C.3 `google-ads-mcp.asset.text_guidelines.set`

```json
{
  "name": "asset.text_guidelines.set",
  "description": "Set text guidelines that constrain AI-generated ad copy (v23.1+).",
  "input_schema": {
    "type": "object",
    "required": ["customer_id", "campaign_id", "guidelines"],
    "properties": {
      "customer_id": {"type": "string"},
      "campaign_id": {"type": "string"},
      "guidelines": {
        "type": "object",
        "properties": {
          "must_include": {"type": "array", "items": {"type": "string"}},
          "must_exclude": {"type": "array", "items": {"type": "string"}},
          "tone": {"type": "string"},
          "brand_voice_examples": {"type": "array", "items": {"type": "string"}, "minItems": 3}
        }
      }
    }
  },
  "rationale": "Without text_guidelines, AI Max + automatically created assets can drift off-brand or breach ASCI claim-substantiation. Setting these is mandatory for AI Max campaigns."
}
```

### C.4 `google-analytics-mcp.data.run_report`

```json
{
  "name": "data.run_report",
  "description": "GA4 Data API report run.",
  "input_schema": {
    "type": "object",
    "required": ["property_id", "date_ranges", "dimensions", "metrics"],
    "properties": {
      "property_id": {"type": "string"},
      "date_ranges": {"type": "array", "items": {
        "type": "object",
        "required": ["start_date", "end_date"],
        "properties": {
          "start_date": {"type": "string", "format": "date"},
          "end_date": {"type": "string", "format": "date"}
        }
      }},
      "dimensions": {"type": "array", "items": {"type": "string"}},
      "metrics": {"type": "array", "items": {"type": "string"}},
      "consent_filter": {"enum": ["consented_only", "all"], "default": "consented_only"}
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "rows": {"type": "array"},
      "sampled": {"type": "boolean"},
      "thresholded": {"type": "boolean", "description": "If true, small cohorts redacted per GA4 privacy thresholding"},
      "row_count": {"type": "integer"}
    }
  },
  "privacy_note": "When thresholded=true, individual-level inference is forbidden in Pramaan output."
}
```

### C.5 `chitra-sanitizer.validate`

```json
{
  "name": "validate",
  "description": "Run the full compliance ruleset (§G) against any artifact before handoff.",
  "input_schema": {
    "type": "object",
    "required": ["artifact_type", "artifact_payload", "tenant_id", "campaign_id"],
    "properties": {
      "artifact_type": {"enum": [
        "creative_brief", "concept_slate", "visual_deck", "verbal_deck",
        "asset_registry", "motion_asset_registry", "media_plan",
        "performance_report", "learnings_dossier", "social_post"
      ]},
      "artifact_payload": {"type": "object"},
      "tenant_id": {"type": "string"},
      "campaign_id": {"type": "string"},
      "sector": {"type": "string"},
      "audience_attributes": {"type": "object"}
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["pass", "checks_run", "violations", "warnings"],
    "properties": {
      "pass": {"type": "boolean"},
      "checks_run": {"type": "array", "items": {"type": "string"}},
      "violations": {"type": "array", "items": {"$ref": "#/definitions/violation"}},
      "warnings": {"type": "array", "items": {"$ref": "#/definitions/warning"}},
      "human_review_required": {"type": "boolean"},
      "redacted_payload": {"type": "object", "description": "Payload with auto-fixable issues corrected"}
    }
  },
  "mandatory_on_every_agent_output": true
}
```

---

## §D AUTHENTICATION & SECRETS

### D.1 Token model
- **Per-tenant** OAuth tokens for Meta, Google, LinkedIn, X, JioAds, Amazon Ads, etc.
- **Per-agent-instance** scoped tokens — Lakshya gets ads-write tokens, Pramaan gets read-only.
- **Per-call** signed JWTs from the L0 Security Layer carrying tenant + agent + scope.

### D.2 Secret vault
- HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager (deployment-dependent).
- Tenant secrets siloed at the IAM boundary, not just by namespace prefix.
- Rotation: 90 days for long-lived OAuth refresh tokens, 1 hour for access tokens, 5 minutes for inter-agent JWTs.
- No secret ever appears in agent context. Agents receive opaque handles; the Tool Mesh resolves handles to secrets at call time.

### D.3 Consent recordkeeping (DPDP 2025 alignment)
For any tool that processes Data Principal personal data (uploaded audience lists, CRM segments, WhatsApp opt-in lists), the consent artifact ID is attached to the MCP call as metadata. The Tool Mesh refuses calls without it. This is a hard gate, not an advisory.

---

## §E RATE LIMITING, COST ACCOUNTING, FAIRNESS

### E.1 Three-tier rate limits
1. **Per-tool tier**: matches vendor limits (e.g., Google Ads API quotas).
2. **Per-tenant tier**: prevents one tenant from starving others on shared inference budget.
3. **Per-agent-instance tier**: prevents a runaway agent from exhausting tenant budget in one campaign.

### E.2 Cost accounting
Every MCP call records: timestamp, tenant_id, campaign_id, agent_id, tool_id, method, input_tokens_or_units, output_tokens_or_units, vendor_cost, internal_cost. Daily roll-up to a `campaign_costs` table.

### E.3 Budget caps per phase
| Phase | Compute (LLM) | External Tools | Notes |
|---|---|---|---|
| Drishti (brief) | 200K–500K tokens | Low | Search-heavy, not gen-heavy |
| Disha (slate) | 300K–800K tokens | Low | Comparative thinking |
| Roop + Vaani (concept bible) | 400K–1M tokens | Mid (Firefly, Bhashini) | Joint phase |
| Rekha + Gati (production) | 200K–500K tokens | High (Adobe, Runway, ElevenLabs) | Compute-light, render-heavy |
| Lehar (always-on, monthly) | 100K–300K tokens/week | Mid (publishing APIs) | Continuous |
| Lakshya (media run) | 50K–200K tokens/day | Variable (= ad spend) | Highest external cost |
| Pramaan (reporting) | 100K–300K tokens/cycle | Mid (GA4, BigQuery) | Per reporting cycle |

These are guidance bands; actual budgets sit in the tenant configuration.

---

## §F VERIFIABLE HANDOFF SCHEMAS

This section defines the **exact JSON contract** each agent must emit. The downstream agent's MCP client refuses input that fails its schema. This is what turns "Phase 1 → Phase 2" from aspiration into enforced fact.

All schemas use **JSON Schema Draft 2020-12**. Each schema also has a Markdown rendering for human readers; the JSON is canonical.

### F.0 Common envelope (wraps every artifact)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chitra.ai/schemas/v1.2/envelope.json",
  "title": "CHITRA Handoff Envelope",
  "type": "object",
  "required": [
    "envelope_version", "tenant_id", "campaign_id", "from_agent", "to_agent",
    "artifact_type", "artifact_uri", "artifact_hash", "phase",
    "timestamp_utc", "version", "compliance", "lock_status"
  ],
  "properties": {
    "envelope_version": {"const": "1.2"},
    "tenant_id": {"type": "string", "format": "uuid"},
    "campaign_id": {"type": "string"},
    "from_agent": {"enum": ["drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan"]},
    "to_agent": {"type": "array", "items": {"enum": ["drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan"]}},
    "artifact_type": {"enum": [
      "creative_brief", "concept_slate", "visual_deck", "verbal_deck",
      "concept_bible", "asset_registry", "motion_asset_registry",
      "media_plan", "daily_optimization_log", "performance_report",
      "learnings_dossier", "content_calendar", "social_post"
    ]},
    "artifact_uri": {"type": "string", "format": "uri"},
    "artifact_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "phase": {"enum": [1, 2, 3, 4]},
    "timestamp_utc": {"type": "string", "format": "date-time"},
    "version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+(\\.[0-9]+)?$"},
    "model": {"type": "string", "description": "Foundation model + version that produced this"},
    "agent_version": {"type": "string", "description": "e.g., drishti-v1.2"},
    "compliance": {
      "type": "object",
      "required": ["sanitizer_run", "sanitizer_pass"],
      "properties": {
        "sanitizer_run": {"type": "boolean"},
        "sanitizer_pass": {"type": "boolean"},
        "checks_passed": {"type": "array", "items": {"type": "string"}},
        "checks_failed": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}}
      }
    },
    "confidence_band": {"enum": ["high", "medium", "low"]},
    "open_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "owner", "description"],
        "properties": {
          "id": {"type": "string"},
          "owner": {"enum": ["client", "drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan", "legal", "human"]},
          "description": {"type": "string"},
          "blocking": {"type": "boolean", "default": false}
        }
      }
    },
    "lock_status": {"enum": ["draft", "locked", "approved", "rejected"]},
    "human_approval_required_next": {"type": "boolean"},
    "human_approver_id": {"type": "string"}
  }
}
```

**Receiver behavior**: a downstream agent's MCP client validates incoming envelopes against this schema before parsing the artifact payload. Schema failure → automatic rejection back to sender with structured error.

### F.1 Creative Brief Schema (Drishti → Disha)

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/creative_brief.json",
  "title": "Creative Brief Artifact",
  "type": "object",
  "required": [
    "business_problem", "target_audience", "perception_gap",
    "insight", "core_message", "tone_spectrum",
    "mandatories", "prohibitions", "success_metrics",
    "cultural_overlay"
  ],
  "properties": {
    "business_problem": {
      "type": "string",
      "minLength": 20,
      "maxLength": 300,
      "description": "One sentence. No jargon."
    },
    "target_audience": {
      "type": "object",
      "required": ["demographics", "psychographics", "day_in_the_life"],
      "properties": {
        "demographics": {
          "type": "object",
          "required": ["age_range", "income_band", "city_tier"],
          "properties": {
            "age_range": {"type": "object", "properties": {
              "min": {"type": "integer", "minimum": 13, "maximum": 99},
              "max": {"type": "integer", "minimum": 13, "maximum": 99}
            }},
            "income_band": {"enum": ["NCCS_A", "NCCS_B", "NCCS_C", "NCCS_D", "NCCS_E", "premium", "mass_premium", "mass", "value"]},
            "city_tier": {"type": "array", "items": {"enum": ["tier_1", "tier_2", "tier_3", "rural", "metro_only"]}},
            "gender": {"type": "array", "items": {"enum": ["female", "male", "non_binary", "all"]}},
            "occupation": {"type": "array", "items": {"type": "string"}},
            "family_stage": {"type": "array", "items": {"enum": ["single", "married_no_kids", "parents_young_kids", "parents_teens", "empty_nest", "retired"]}}
          }
        },
        "psychographics": {
          "type": "object",
          "properties": {
            "values": {"type": "array", "items": {"type": "string"}},
            "anxieties": {"type": "array", "items": {"type": "string"}},
            "aspirations": {"type": "array", "items": {"type": "string"}}
          }
        },
        "day_in_the_life": {"type": "string", "minLength": 150, "maxLength": 400}
      }
    },
    "perception_gap": {
      "type": "object",
      "required": ["current", "desired"],
      "properties": {
        "current": {"type": "string", "maxLength": 300},
        "desired": {"type": "string", "maxLength": 300}
      }
    },
    "insight": {
      "type": "string",
      "minLength": 50,
      "maxLength": 500,
      "description": "Non-obvious truth bridging current and desired perception."
    },
    "core_message": {
      "type": "string",
      "minLength": 5,
      "maxLength": 200,
      "description": "Single-minded proposition. Must pass the Mom Test."
    },
    "tone_spectrum": {
      "type": "object",
      "required": ["serious_to_playful", "premium_to_accessible", "traditional_to_modern"],
      "properties": {
        "serious_to_playful": {"type": "integer", "minimum": -5, "maximum": 5},
        "premium_to_accessible": {"type": "integer", "minimum": -5, "maximum": 5},
        "traditional_to_modern": {"type": "integer", "minimum": -5, "maximum": 5},
        "additional_axes": {"type": "array", "items": {
          "type": "object",
          "properties": {"label": {"type": "string"}, "value": {"type": "integer", "minimum": -5, "maximum": 5}}
        }}
      }
    },
    "mandatories": {"type": "array", "items": {
      "type": "object",
      "required": ["item", "source"],
      "properties": {
        "item": {"type": "string"},
        "source": {"enum": ["client_brief", "regulatory", "brand_guideline", "legal"]},
        "regulation_id": {"type": "string", "description": "If source=regulatory, the rule ID from §G"}
      }
    }},
    "prohibitions": {"type": "array", "items": {"type": "object", "properties": {
      "item": {"type": "string"},
      "source": {"enum": ["client_brief", "regulatory", "brand_guideline", "cultural_risk"]}
    }}},
    "success_metrics": {
      "type": "object",
      "required": ["business_metrics", "brand_metrics", "attribution_model"],
      "properties": {
        "business_metrics": {"type": "array", "items": {"type": "object", "properties": {
          "metric": {"type": "string"},
          "target": {"type": "number"},
          "unit": {"type": "string"}
        }}},
        "brand_metrics": {"type": "array", "items": {"type": "object", "properties": {
          "metric": {"type": "string"},
          "measurement_method": {"type": "string"}
        }}},
        "attribution_model": {"enum": ["last_click", "data_driven", "first_click", "linear", "time_decay", "position_based", "mmm"]},
        "measurement_window_days": {"type": "integer", "minimum": 1}
      }
    },
    "cultural_overlay": {
      "type": "object",
      "required": ["festivals_in_window", "sports_in_window", "sensitivities"],
      "properties": {
        "festivals_in_window": {"type": "array", "items": {"type": "object", "properties": {
          "name": {"type": "string"},
          "date": {"type": "string", "format": "date"},
          "marketing_relevance": {"enum": ["high", "medium", "low", "avoid"]}
        }}},
        "sports_in_window": {"type": "array", "items": {"type": "object", "properties": {
          "event": {"type": "string"},
          "dates": {"type": "string"},
          "marketing_relevance": {"enum": ["high", "medium", "low", "avoid"]}
        }}},
        "sensitivities": {"type": "array", "items": {"type": "object", "properties": {
          "category": {"enum": ["religion", "caste", "gender", "region", "political", "language"]},
          "note": {"type": "string"},
          "mitigation": {"type": "string"}
        }}}
      }
    },
    "open_questions_for_disha": {"type": "array", "items": {"type": "string"}}
  }
}
```

### F.2 Concept Slate Schema (Disha → Roop + Vaani)

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/concept_slate.json",
  "title": "Concept Slate Artifact",
  "type": "object",
  "required": ["concepts_approved", "concepts_killed", "pitch_deck_uri"],
  "properties": {
    "concepts_approved": {
      "type": "array",
      "minItems": 3,
      "maxItems": 5,
      "items": {
        "type": "object",
        "required": ["id", "title", "proposition", "visual_direction", "verbal_hook", "target_subsegment", "scores", "cultural_risk", "production_complexity"],
        "properties": {
          "id": {"type": "string"},
          "title": {"type": "string"},
          "proposition": {"type": "string", "maxLength": 200},
          "visual_direction": {"type": "string", "maxLength": 500},
          "verbal_hook": {"type": "object", "properties": {
            "primary": {"type": "string"},
            "alternates": {"type": "array", "items": {"type": "string"}, "minItems": 2}
          }},
          "target_subsegment": {"type": "string"},
          "scores": {
            "type": "object",
            "required": ["relevance", "distinctiveness", "resonance", "producibility", "cultural_safety"],
            "properties": {
              "relevance": {"type": "integer", "minimum": 1, "maximum": 5},
              "distinctiveness": {"type": "integer", "minimum": 1, "maximum": 5},
              "resonance": {"type": "integer", "minimum": 1, "maximum": 5},
              "producibility": {"type": "integer", "minimum": 1, "maximum": 5},
              "cultural_safety": {"type": "integer", "minimum": 1, "maximum": 5},
              "total": {"type": "integer", "minimum": 16, "maximum": 25}
            }
          },
          "cultural_risk": {
            "type": "object",
            "required": ["level", "register"],
            "properties": {
              "level": {"enum": ["low", "medium", "high"]},
              "register": {"type": "array", "items": {"type": "object", "properties": {
                "category": {"enum": ["religion", "caste", "gender", "region", "political", "language", "child_safety"]},
                "concern": {"type": "string"},
                "mitigation": {"type": "string"}
              }}}
            }
          },
          "production_complexity": {"enum": ["low", "medium", "high"]},
          "kill_risk_register": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "concepts_killed": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "title", "kill_tag", "rationale"],
        "properties": {
          "id": {"type": "string"},
          "title": {"type": "string"},
          "kill_tag": {"enum": [
            "solves_wrong_problem",
            "indistinguishable_from_recent_category_work",
            "insight_borrowed_not_earned",
            "cultural_risk_unmitigable",
            "production_cost_exceeds_envelope",
            "requires_unavailable_talent",
            "regulatory_breach",
            "ip_conflict"
          ]},
          "rationale": {"type": "string"}
        }
      }
    },
    "pitch_deck_uri": {"type": "string", "format": "uri"}
  }
}
```

### F.3 Concept Bible Schema (Roop + Vaani jointly → Rekha + Gati)

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/concept_bible.json",
  "title": "Concept Bible — Visual + Verbal joint artifact",
  "type": "object",
  "required": ["concept_id", "visual_deck", "verbal_deck", "joint_signoff"],
  "properties": {
    "concept_id": {"type": "string"},
    "visual_deck": {
      "type": "object",
      "required": ["mood_board", "style_frames", "type_system", "color_system", "adaptation_matrix"],
      "properties": {
        "mood_board": {
          "type": "array",
          "minItems": 10,
          "maxItems": 15,
          "items": {"type": "object", "required": ["uri", "rationale"], "properties": {
            "uri": {"type": "string", "format": "uri"},
            "rationale": {"type": "string"},
            "license_cleared": {"type": "boolean"}
          }}
        },
        "style_frames": {
          "type": "array",
          "minItems": 3,
          "maxItems": 5,
          "items": {"type": "object", "required": ["uri", "aspect_ratio", "notes"], "properties": {
            "uri": {"type": "string"},
            "aspect_ratio": {"enum": ["1:1", "4:5", "9:16", "16:9", "1.91:1", "3:4", "2:3", "4:3"]},
            "notes": {"type": "string"}
          }}
        },
        "storyboard": {
          "type": "array",
          "description": "Required if concept is video-led",
          "items": {"type": "object", "required": ["beat_number", "description", "duration_sec"], "properties": {
            "beat_number": {"type": "integer"},
            "description": {"type": "string"},
            "key_frame_uri": {"type": "string"},
            "duration_sec": {"type": "number"},
            "camera_notes": {"type": "string"},
            "sound_cue": {"type": "string"}
          }}
        },
        "type_system": {"type": "object", "properties": {
          "primary_typeface": {"type": "string"},
          "script_typefaces": {"type": "object", "description": "Map of script → typeface"},
          "weights": {"type": "array", "items": {"type": "string"}}
        }},
        "color_system": {"type": "object", "properties": {
          "palette": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "hex": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
            "cmyk": {"type": "string"},
            "pantone": {"type": "string"}
          }}}
        }},
        "adaptation_matrix": {"type": "array", "items": {"type": "object", "properties": {
          "format": {"type": "string"},
          "dimensions": {"type": "string"},
          "treatment_notes": {"type": "string"}
        }}}
      }
    },
    "verbal_deck": {
      "type": "object",
      "required": ["voice_calibration", "taglines", "headlines", "scripts", "captions"],
      "properties": {
        "voice_calibration": {"type": "object", "required": ["archetype", "tone_band", "hello_test"], "properties": {
          "archetype": {"enum": ["sage", "hero", "lover", "jester", "caregiver", "rebel", "magician", "innocent", "explorer", "creator", "ruler", "everyman"]},
          "tone_band": {"type": "object"},
          "hello_test": {"type": "string"}
        }},
        "taglines": {"type": "object", "properties": {
          "primary": {"type": "string"},
          "alternates_long": {"type": "array", "items": {"type": "string"}, "minItems": 2},
          "alternates_short": {"type": "array", "items": {"type": "string"}, "minItems": 2},
          "two_word_stamp": {"type": "string"}
        }},
        "headlines": {"type": "array", "minItems": 15, "items": {"type": "object", "properties": {
          "text": {"type": "string"},
          "category": {"enum": ["question", "command", "statement", "story_opener", "twist"]}
        }}},
        "scripts": {"type": "array", "items": {"type": "object", "required": ["duration_sec", "platform", "language", "transcript"], "properties": {
          "duration_sec": {"enum": [6, 15, 30, 60, 90, 180, 360]},
          "platform": {"type": "string"},
          "language": {"type": "string"},
          "transcript": {"type": "string"},
          "timing_marks": {"type": "array", "items": {"type": "object", "properties": {
            "sec": {"type": "number"},
            "event": {"type": "string"}
          }}}
        }}},
        "captions": {"type": "array", "minItems": 10, "items": {"type": "object", "properties": {
          "text": {"type": "string"},
          "platform": {"type": "string"},
          "language": {"type": "string"},
          "asci_disclosure_embedded": {"type": "boolean"}
        }}},
        "voice_tone_guide_uri": {"type": "string", "format": "uri"}
      }
    },
    "joint_signoff": {
      "type": "object",
      "required": ["roop_signed_at", "vaani_signed_at", "alignment_check"],
      "properties": {
        "roop_signed_at": {"type": "string", "format": "date-time"},
        "vaani_signed_at": {"type": "string", "format": "date-time"},
        "alignment_check": {"type": "boolean", "description": "Visual and verbal agreed to align without contradiction"}
      }
    }
  }
}
```

### F.4 Asset Registry Schema (Rekha → Lakshya)

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/asset_registry.json",
  "title": "Asset Registry Artifact",
  "type": "object",
  "required": ["master_files", "exports", "accessibility_audit", "brand_compliance"],
  "properties": {
    "master_files": {"type": "array", "items": {"type": "object", "required": ["uri", "format", "size_bytes"], "properties": {
      "uri": {"type": "string"},
      "format": {"type": "string"},
      "size_bytes": {"type": "integer"},
      "last_updated": {"type": "string", "format": "date-time"}
    }}},
    "exports": {"type": "array", "items": {
      "type": "object",
      "required": ["filename", "format", "language", "version", "uri", "asci_disclosure_embedded"],
      "properties": {
        "filename": {
          "type": "string",
          "pattern": "^[a-z0-9]+_[a-z0-9-]+_[a-z0-9-]+_[a-z0-9-]+_[a-z]{2}_v[0-9]+\\.(png|jpg|mp4|pdf|gif|webp)$",
          "description": "Naming convention: {client}_{campaign}_{concept}_{format}_{lang}_{version}.{ext}"
        },
        "format": {"type": "string"},
        "language": {"type": "string"},
        "version": {"type": "string"},
        "uri": {"type": "string"},
        "dimensions": {"type": "string"},
        "asci_disclosure_embedded": {"type": "boolean"},
        "ai_generated": {"type": "boolean"},
        "content_credentials": {"type": "string", "description": "C2PA / Firefly content credentials hash"}
      }
    }},
    "accessibility_audit": {"type": "array", "items": {"type": "object", "properties": {
      "asset_filename": {"type": "string"},
      "contrast_ratio_min": {"type": "number"},
      "wcag_aa_pass": {"type": "boolean"},
      "alt_text": {"type": "string"},
      "font_size_compliant": {"type": "boolean"}
    }}},
    "brand_compliance": {"type": "object", "properties": {
      "logo_clear_space_ok": {"type": "boolean"},
      "color_within_palette": {"type": "boolean"},
      "type_compliance": {"type": "boolean"},
      "deviation_notes": {"type": "string"}
    }}
  }
}
```

### F.5 Media Plan Schema (Lakshya → execution)

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/media_plan.json",
  "title": "Media Plan Artifact",
  "type": "object",
  "required": ["channels", "budget_allocation", "audiences", "attribution_model", "test_plan"],
  "properties": {
    "channels": {"type": "array", "items": {"type": "object", "required": ["channel", "objective", "rationale"], "properties": {
      "channel": {"enum": [
        "meta_facebook", "meta_instagram", "meta_whatsapp",
        "google_search", "google_pmax", "google_demand_gen", "youtube",
        "jiohotstar", "jioads_network",
        "amazon_ads", "flipkart_ads",
        "blinkit_ads", "instamart_ads", "zepto_ads",
        "linkedin_ads", "x_ads",
        "sharechat", "moj", "josh", "dailyhunt",
        "dv360_programmatic", "trade_desk",
        "ooh", "print", "tv_linear"
      ]},
      "objective": {"enum": ["awareness", "consideration", "conversion", "loyalty"]},
      "rationale": {"type": "string"}
    }}},
    "budget_allocation": {"type": "array", "items": {"type": "object", "properties": {
      "channel": {"type": "string"},
      "phase": {"enum": ["pre_launch", "launch", "sustain", "peak", "wind_down"]},
      "amount_inr": {"type": "integer"},
      "percent_of_total": {"type": "number"}
    }}},
    "audiences": {"type": "array", "items": {"type": "object", "properties": {
      "name": {"type": "string"},
      "type": {"enum": ["core", "lookalike", "custom", "retargeting", "exclusion"]},
      "lookalike_percentage": {"type": "integer"},
      "size_estimated": {"type": "integer"},
      "consent_artifact_id": {"type": "string", "description": "Required for custom audiences"},
      "targeting_bases_used": {"type": "array", "items": {"type": "string"}}
    }}},
    "attribution_model": {"type": "object", "required": ["primary", "secondary"], "properties": {
      "primary": {"enum": ["last_click", "data_driven", "linear", "time_decay", "position_based"]},
      "secondary": {"type": "array", "items": {"type": "string"}},
      "measurement_window_days": {"type": "integer"}
    }},
    "test_plan": {"type": "array", "items": {"type": "object", "properties": {
      "test_name": {"type": "string"},
      "type": {"enum": ["a_b", "multivariate", "geo_holdout", "audience_holdout"]},
      "cells": {"type": "array", "items": {"type": "string"}},
      "minimum_detectable_lift": {"type": "number"},
      "sample_size_per_cell": {"type": "integer"},
      "expected_duration_days": {"type": "integer"}
    }}},
    "trafficking_sheet_uri": {"type": "string", "format": "uri"}
  }
}
```

### F.6 Performance Report Schema (Pramaan → Drishti, next-cycle input)

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/performance_report.json",
  "title": "Performance Report Artifact",
  "type": "object",
  "required": ["executive_summary", "channel_performance", "creative_scorecard", "attribution_range", "learnings_dossier", "statistical_notes"],
  "properties": {
    "executive_summary": {"type": "object", "required": ["roas", "spend_inr", "revenue_inr", "top_wins", "top_watchouts"], "properties": {
      "roas": {"type": "number"},
      "spend_inr": {"type": "integer"},
      "revenue_inr": {"type": "integer"},
      "cpa_inr": {"type": "number"},
      "brand_lift_pp": {"type": "number", "description": "Percentage points; null if not measured"},
      "top_wins": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
      "top_watchouts": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
      "recommendation_memo": {"type": "string"}
    }},
    "channel_performance": {"type": "array", "items": {"type": "object", "properties": {
      "channel": {"type": "string"},
      "spend": {"type": "integer"},
      "impressions": {"type": "integer"},
      "clicks": {"type": "integer"},
      "ctr": {"type": "number"},
      "conversions": {"type": "integer"},
      "cvr": {"type": "number"},
      "cpa": {"type": "number"},
      "roas": {"type": "number"}
    }}},
    "creative_scorecard": {"type": "array", "items": {"type": "object", "properties": {
      "asset_filename": {"type": "string"},
      "hook_rate_3s": {"type": "number"},
      "ctr": {"type": "number"},
      "vcr": {"type": "number"},
      "conversion_rate": {"type": "number"},
      "roas": {"type": "number"},
      "fatigue_curve_slope": {"type": "number"},
      "rank": {"type": "integer"}
    }}},
    "attribution_range": {"type": "array", "items": {"type": "object", "required": ["model", "roas"], "properties": {
      "model": {"enum": ["last_click", "data_driven", "platform_self_attributed", "mmm", "incrementality_test"]},
      "roas": {"type": "number"},
      "notes": {"type": "string"}
    }}},
    "statistical_notes": {"type": "object", "properties": {
      "sample_sizes": {"type": "object"},
      "confidence_intervals": {"type": "object"},
      "data_caveats": {"type": "array", "items": {"type": "string"}}
    }},
    "learnings_dossier": {
      "type": "object",
      "required": ["what_worked", "what_didnt", "what_surprised", "what_to_test_next", "brief_amendments_recommended"],
      "properties": {
        "what_worked": {"type": "array", "items": {"type": "object", "properties": {
          "observation": {"type": "string"},
          "evidence": {"type": "string"}
        }}},
        "what_didnt": {"type": "array", "items": {"type": "object", "properties": {
          "observation": {"type": "string"},
          "evidence": {"type": "string"}
        }}},
        "what_surprised": {"type": "array", "items": {"type": "string"}},
        "what_to_test_next": {"type": "array", "items": {"type": "string"}},
        "brief_amendments_recommended": {"type": "array", "items": {"type": "string"}}
      }
    },
    "privacy_compliance": {"type": "object", "required": ["individual_level_data_excluded", "dpdp_retention_ok"], "properties": {
      "individual_level_data_excluded": {"const": true},
      "dpdp_retention_ok": {"type": "boolean"},
      "cohort_minimum_respected": {"type": "boolean"}
    }}
  }
}
```

> The remaining four schemas — `motion_asset_registry`, `daily_optimization_log`, `content_calendar`, `social_post` — follow the same shape. Stored in the schema registry at `https://chitra.ai/schemas/v1.2/`.

### F.7 Validator behavior

```
function validate_handoff(envelope, artifact_payload):
    if not json_schema_validate(envelope, ENVELOPE_SCHEMA):
        return REJECT("envelope_malformed", details)
    if envelope.artifact_hash != sha256(artifact_payload):
        return REJECT("hash_mismatch")
    schema = SCHEMA_REGISTRY[envelope.artifact_type]
    if not json_schema_validate(artifact_payload, schema):
        return REJECT("artifact_schema_violation", details)
    if not envelope.compliance.sanitizer_run:
        return REJECT("sanitizer_not_run")
    if not envelope.compliance.sanitizer_pass:
        return REJECT("sanitizer_failed", envelope.compliance.checks_failed)
    if envelope.lock_status != "locked":
        return REJECT("artifact_not_locked")
    return ACCEPT
```

Receiver is required to run this before consuming any artifact. No exceptions.

---

## §G CODIFIED COMPLIANCE RULESET

Prose regulations from v1.1 §A.1 are now **predicate functions** with explicit signatures, deterministic outputs, and machine-readable failure messages. The sanitizer (§H) is the consumer.

### G.0 Rule object shape

```typescript
interface ComplianceRule {
  id: string;                      // e.g., "ASCI-DISC-001"
  source: "ASCI" | "DPDP" | "IT_RULES" | "CPA" | "DMRA" | "RBI" | "SEBI" | "IRDAI" | "TRAI" | "MOHFW" | "CCPA_DARK" | "PLATFORM_TOS";
  citation: string;                // e.g., "ASCI Influencer Guidelines Addendum 2, 7 April 2025"
  applies_to: ArtifactType[];      // which artifact types this rule checks
  applies_when: (ctx: Context) => boolean;
  check: (artifact: any, ctx: Context) => RuleResult;
  severity: "block" | "warn" | "info";
  auto_fix_available: boolean;
  human_review_on_fail: boolean;
}

interface RuleResult {
  pass: boolean;
  message?: string;
  evidence?: string;       // pointer into artifact for the failing element
  suggested_fix?: string;
}
```

### G.1 ASCI rules (codified)

```yaml
- id: ASCI-DISC-001
  source: ASCI
  citation: "ASCI Influencer Guidelines Addendum 2, 7 April 2025"
  applies_to: [social_post, content_calendar]
  applies_when: post.paid_partnership == true OR post.material_connection == true
  check:
    require: post.caption_starts_with_hashtag in ["#Ad", "#Advertisement", "#Sponsored", "#Promotion", "#Paid", "#PaidPartnership", "#Collab", "#PartnerOf"]
    OR: post.platform_native_label == "paid_partnership_with"
  severity: block
  auto_fix_available: true   # can prepend #Ad
  human_review_on_fail: false
  failure_message: "Paid partnership disclosure missing. ASCI requires #Ad in first caption line."

- id: ASCI-DISC-002
  source: ASCI
  citation: "ASCI Influencer Guidelines, video disclosure duration"
  applies_to: [motion_asset_registry, social_post]
  applies_when: artifact.is_video == true AND artifact.paid_partnership == true
  check:
    if artifact.duration_sec <= 15:
      require: artifact.disclosure_visible_duration_sec >= 3
    elif artifact.duration_sec <= 120:
      require: artifact.disclosure_visible_duration_sec >= artifact.duration_sec / 3
    else:
      require: artifact.disclosure_visible_throughout == true
  severity: block

- id: ASCI-AI-001
  source: ASCI
  citation: "ASCI AI Influencer Disclosure, April 2026"
  applies_to: [motion_asset_registry, asset_registry, social_post]
  applies_when: artifact.uses_ai_persona == true OR artifact.uses_ai_generated_human_likeness == true
  check:
    require: artifact.ai_label_present == true
    AND: artifact.ai_label_text in ["AI-Generated", "Virtual Persona", "AI Influencer"]
    if artifact.is_video:
      require: artifact.ai_label_within_first_5_sec == true
      AND: artifact.ai_label_at_end == true
      if artifact.ai_persona_speaks:
        require: artifact.ai_label_visible_throughout_speech == true
  severity: block
  human_review_on_fail: true

- id: ASCI-AI-002
  source: ASCI
  citation: "ASCI AI Influencer + Children Ban, April 2026"
  applies_to: [asset_registry, motion_asset_registry, media_plan, social_post]
  applies_when: artifact.uses_ai_persona == true AND artifact.audience_includes_under_12 == true
  check:
    require: artifact.product_category NOT IN ["junk_food", "high_sugar_beverage", "real_money_gaming", "fantasy_sports_real_money", "weight_loss"]
  severity: block
  human_review_on_fail: true

- id: ASCI-BFSI-001
  source: ASCI
  citation: "ASCI Influencer Guidelines Addendum 2 (BFSI), 7 April 2025"
  applies_to: [verbal_deck, social_post, motion_asset_registry]
  applies_when: artifact.sector == "BFSI" AND artifact.contains_technical_advice == true
  check:
    require: artifact.influencer_qualification_disclosed == true
    AND: artifact.qualification_visible_prominently == true
  severity: block
  human_review_on_fail: true

- id: ASCI-HEALTH-001
  source: ASCI
  citation: "ASCI Influencer Guidelines Addendum 2 (Health/Nutrition), 7 April 2025"
  applies_to: [verbal_deck, social_post]
  applies_when: artifact.sector IN ["healthcare", "nutrition"] AND artifact.contains_technical_advice == true
  check:
    require: artifact.influencer_qualification_disclosed == true
  severity: block

- id: ASCI-DARK-001
  source: CCPA_DARK + ASCI 2026 focus
  citation: "CCPA Guidelines on Dark Patterns (Nov 2023) + ASCI 2026 dark-pattern campaign"
  applies_to: [asset_registry, social_post, media_plan]
  check:
    forbid_any: [
      "fake_scarcity_countdown",
      "false_low_stock_indicator",
      "hidden_costs_disclosed_only_at_checkout",
      "confirmshaming_negative_button_text",
      "roach_motel_difficult_unsubscribe",
      "disguised_ad_appearing_organic",
      "forced_consent_no_alternative",
      "interface_interference_misleading_button_layout",
      "bait_and_switch_advertised_vs_delivered",
      "drip_pricing",
      "subscription_trap",
      "rogue_malware_pretending_security",
      "trick_wording_double_negative_optout"
    ]
  severity: block
  human_review_on_fail: true

- id: ASCI-GREENWASH-001
  source: ASCI
  citation: "ASCI Greenwashing Guidelines + 2026 enforcement campaign"
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: artifact.contains_environmental_claim == true
  check:
    require_any: [
      "claim_substantiated_with_third_party_certification",
      "claim_quantified_with_specific_metric",
      "claim_qualified_with_scope_disclosure"
    ]
    forbid: "vague_green_claim_without_evidence"
  severity: block
```

### G.2 DPDP Act rules (codified)

```yaml
- id: DPDP-CONSENT-001
  source: DPDP
  citation: "DPDP Act 2023 + DPDP Rules 2025 (notified 13 Nov 2025)"
  applies_to: [media_plan, social_post]
  applies_when: artifact.uses_custom_audience == true OR artifact.uses_crm_upload == true OR artifact.uses_whatsapp_marketing == true
  check:
    require: artifact.consent_artifact_id present
    AND: consent_vault.lookup(artifact.consent_artifact_id).status == "valid"
    AND: consent_vault.lookup(artifact.consent_artifact_id).purpose matches artifact.processing_purpose
  severity: block
  human_review_on_fail: true

- id: DPDP-CHILDREN-001
  source: DPDP
  citation: "DPDP Act §9 — Processing of personal data of children"
  applies_to: [media_plan, creative_brief]
  applies_when: artifact.target_audience.includes_minors == true
  check:
    forbid: artifact.uses_behavioral_tracking_of_minors
    forbid: artifact.uses_targeted_advertising_directed_at_minors
    require: artifact.verifiable_parental_consent_in_place == true
  severity: block
  human_review_on_fail: true

- id: DPDP-RETENTION-001
  source: DPDP
  citation: "DPDP Rules 2025, Seventh Schedule"
  applies_to: [performance_report, learnings_dossier]
  check:
    require: artifact.data_retention_period_days <= tenant.dpdp_retention_policy_days
    require: artifact.individual_level_data_present == false
  severity: block

- id: DPDP-BREACH-NOTIFY-001
  source: DPDP
  citation: "DPDP Rules 2025 — breach notification"
  applies_when: incident.classified_as_breach == true
  check:
    require: notification.to_dpbi_sent == true (without delay)
    AND: notification.to_affected_data_principals_sent == true (without delay)
  severity: block
  human_review_on_fail: true
  note: "Not an artifact-level rule; this is a process rule that runs on incident classification."

- id: DPDP-SENSITIVE-TARGETING-001
  source: DPDP + Constitutional principles + Platform ToS
  applies_to: [media_plan, social_post]
  check:
    forbid_targeting_bases: [
      "religion_alone",
      "caste",
      "political_affiliation",
      "sexual_orientation_unless_brand_is_LGBTQ_affirmative",
      "health_condition_unless_legitimate_health_service",
      "trade_union_membership"
    ]
  severity: block
  human_review_on_fail: true
```

### G.3 Sectoral rules (codified)

```yaml
- id: DMRA-001
  source: DMRA
  citation: "Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954 — Schedule"
  applies_to: [verbal_deck, asset_registry, social_post, motion_asset_registry]
  check:
    forbid_claims_for_conditions:
      - "cure_of_diabetes"
      - "cure_of_cancer"
      - "improvement_of_sexual_function_with_drug_claim"
      - "weight_loss_by_drug"
      - "cure_of_AIDS"
      - "increase_of_height_in_adults"
      - "cure_of_premature_aging"
      # ... 54 conditions total per Schedule
  severity: block
  human_review_on_fail: true

- id: RBI-BFSI-001
  source: RBI
  citation: "RBI guidelines on financial product advertising"
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: artifact.product_category == "banking_lending_credit"
  check:
    require: artifact.contains_apr_or_interest_disclosure == true
    require: artifact.contains_t_and_c_apply_disclosure == true
    forbid: artifact.uses_guaranteed_returns_language
  severity: block

- id: SEBI-MUTUAL-FUND-001
  source: SEBI
  applies_to: [verbal_deck, asset_registry, social_post, motion_asset_registry]
  applies_when: artifact.product_category == "mutual_funds_securities"
  check:
    require: artifact.contains_market_risk_disclaimer == true
    if artifact.is_video:
      require: artifact.market_risk_disclaimer_visible_min_sec >= 5
      AND: artifact.market_risk_disclaimer_voiceover == true
  severity: block

- id: IRDAI-INSURANCE-001
  source: IRDAI
  applies_to: [verbal_deck, asset_registry]
  applies_when: artifact.product_category == "insurance"
  check:
    require: artifact.contains_policy_terms_disclosure == true
    require: artifact.contains_irdai_registration_number == true
    forbid: artifact.uses_misleading_returns_language
  severity: block

- id: GAMING-RMG-001
  source: IT_RULES + MeitY
  citation: "IT Rules 2023 amendment — real-money gaming"
  applies_to: [verbal_deck, asset_registry, social_post, media_plan]
  applies_when: artifact.product_category IN ["fantasy_sports_real_money", "rummy_real_money", "poker_real_money", "online_real_money_gaming"]
  check:
    require: artifact.contains_addiction_warning == true
    require: artifact.contains_age_restriction_disclosure == true
    require: artifact.audience_min_age >= 18
    forbid: artifact.audience_includes_minors
    require: artifact.product_certified_by_SRB == true
  severity: block
  human_review_on_fail: true

- id: TOBACCO-001
  source: COTPA
  citation: "Cigarettes and Other Tobacco Products Act, 2003"
  applies_to: [verbal_deck, asset_registry, social_post, motion_asset_registry, media_plan]
  applies_when: artifact.product_category IN ["tobacco", "cigarettes", "tobacco_surrogate"]
  check:
    forbid_all: true
  severity: block
  failure_message: "Direct tobacco advertising is banned in India. Surrogate advertising is heavily scrutinized."

- id: ALCOHOL-SURROGATE-001
  source: ASCI + Excise
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: artifact.product_category IN ["alcohol", "alcohol_surrogate"]
  check:
    forbid: artifact.directly_promotes_alcohol
    if artifact.is_surrogate:
      require: artifact.surrogate_product_legitimate_market_presence == true
      forbid: artifact.uses_alcohol_consumption_imagery
  severity: block
  human_review_on_fail: true

- id: REAL-ESTATE-RERA-001
  source: RERA
  applies_to: [verbal_deck, asset_registry]
  applies_when: artifact.product_category == "real_estate"
  check:
    require: artifact.contains_rera_registration_number == true
    require: artifact.contains_project_details_disclosure == true
  severity: block

- id: EDTECH-NEP-001
  source: ASCI Education Code
  applies_to: [verbal_deck, asset_registry, social_post]
  applies_when: artifact.product_category == "edtech"
  check:
    forbid: artifact.guarantees_specific_exam_rank_or_marks
    forbid: artifact.uses_fear_of_failure_appeals_to_parents
    forbid: artifact.uses_unverified_testimonials_of_minors
  severity: block

- id: HEALTHCARE-CLAIM-SUB-001
  source: CPA + MoHFW
  applies_to: [verbal_deck, asset_registry]
  applies_when: artifact.product_category IN ["healthcare", "medical_device", "supplements", "nutraceutical"]
  check:
    require: artifact.health_claims_have_evidence_id == true
    forbid: artifact.uses_doctor_endorsement_for_drug_without_DGCI_approval
  severity: block
```

### G.4 IP, copyright, and platform rules

```yaml
- id: IP-TRADEMARK-001
  source: Trade Marks Act 1999
  applies_to: [concept_slate, verbal_deck, asset_registry]
  check:
    require: legal_precheck.trademark_clearance_passed == true
  severity: block

- id: IP-COPYRIGHT-001
  source: Copyright Act 1957
  applies_to: [asset_registry, motion_asset_registry]
  check:
    if artifact.uses_music: require: artifact.music_license_documented == true
    if artifact.uses_stock_imagery: require: artifact.stock_license_documented == true
    if artifact.uses_celebrity_likeness: require: artifact.celebrity_contract_documented == true
  severity: block

- id: IP-AI-CONSENT-001
  source: IT Rules + emerging deepfake regulation
  applies_to: [motion_asset_registry]
  applies_when: artifact.uses_voice_clone == true OR artifact.uses_face_swap == true OR artifact.uses_likeness_synthesis == true
  check:
    require: artifact.subject_consent_documented == true
    require: artifact.deepfake_label_present == true
  severity: block
  human_review_on_fail: true

- id: PLATFORM-TOS-WHATSAPP-001
  source: PLATFORM_TOS
  citation: "WhatsApp Business Platform Policy"
  applies_to: [social_post, media_plan]
  applies_when: artifact.channel == "whatsapp"
  check:
    require: artifact.recipients_opted_in == true
    require: artifact.template_pre_approved == true
    require: artifact.respects_24h_utility_window == true
  severity: block

- id: PLATFORM-TOS-META-SPECIAL-CAT-001
  source: PLATFORM_TOS
  citation: "Meta special ad categories"
  applies_to: [media_plan]
  applies_when: artifact.product_category IN ["credit", "employment", "housing", "elections_politics", "gambling_gaming"]
  check:
    require: artifact.special_ad_category_declared_in_meta == true
  severity: block
```

### G.5 Cultural risk rules (heuristic-driven, human-reviewed)

```yaml
- id: CULTURAL-RELIGION-001
  source: cultural_risk_register
  applies_to: [concept_slate, asset_registry, verbal_deck, motion_asset_registry]
  check:
    if artifact.references_religious_symbol OR artifact.references_religious_practice:
      require: cultural_risk_audit.completed == true
      require: cultural_risk_audit.level != "high" OR human_review_on_fail
      require: artifact.does_not_mock_religion == true
  severity: block_if_high_risk

- id: CULTURAL-CASTE-001
  source: cultural_risk_register + Constitution
  applies_to: [concept_slate, asset_registry, verbal_deck]
  check:
    forbid: artifact.uses_caste_stereotypes
    forbid: artifact.implies_caste_hierarchy
  severity: block
  human_review_on_fail: true

- id: CULTURAL-GENDER-001
  source: cultural_risk_register
  applies_to: [concept_slate, asset_registry, verbal_deck]
  check:
    forbid: artifact.reinforces_harmful_gender_stereotypes
    forbid: artifact.uses_misogyny_for_humor
    forbid: artifact.uses_body_shaming
  severity: block_if_high_risk

- id: CULTURAL-REGION-001
  source: cultural_risk_register
  applies_to: [concept_slate, asset_registry, verbal_deck]
  check:
    forbid: artifact.mocks_regional_accent_for_humor
    forbid: artifact.implies_regional_hierarchy
  severity: warn_or_block_by_severity

- id: CULTURAL-POLITICAL-001
  source: cultural_risk_register
  applies_to: [concept_slate, asset_registry, verbal_deck, social_post]
  check:
    forbid: artifact.takes_partisan_political_position_unless_brand_is_political
    forbid: artifact.references_living_political_figure_unflatteringly
  severity: block
  human_review_on_fail: true
```

### G.6 Rule registry mechanics

- Rules live in `chitra-regdb` MCP server.
- Each rule has a version number; rule changes are versioned.
- Rule registry refreshes on the same cadence as v1.1 §A.1 (monthly + on-notification).
- The Resource Curator owns rule updates; a new rule cannot deploy without two-person review.
- Rules can be in `shadow_mode` for 14 days after introduction — they log but don't block — to surface false positives before enforcement.

---

## §H OUTPUT SANITIZER (the runtime that consumes §G)

### H.1 What it does

For every artifact an agent emits, before the handoff envelope is signed:

1. Load the rule set applicable to `artifact_type` and `context`.
2. Run every rule's `applies_when` predicate.
3. For rules that apply, run `check`.
4. Aggregate violations, warnings, and info.
5. If any `severity == "block"` rule fails → reject artifact; return to agent with structured error.
6. If any rule with `human_review_on_fail == true` fails → halt, escalate to human.
7. If `auto_fix_available == true` and the agent's policy permits → apply fix, re-validate.
8. On pass → stamp `envelope.compliance.sanitizer_pass = true`, sign envelope.

### H.2 Sanitizer API

```python
def sanitize(artifact_type: str, artifact: dict, context: dict) -> SanitizerResult:
    rules = rule_registry.load_for(artifact_type, context)
    violations, warnings = [], []
    applicable = [r for r in rules if r.applies_when(artifact, context)]
    for rule in applicable:
        result = rule.check(artifact, context)
        if not result.pass:
            entry = {
                "rule_id": rule.id,
                "source": rule.source,
                "message": result.message,
                "evidence": result.evidence,
                "suggested_fix": result.suggested_fix,
            }
            if rule.severity == "block":
                violations.append(entry)
            elif rule.severity == "warn":
                warnings.append(entry)
    human_review = any(rule.human_review_on_fail for rule in applicable if not rule.check(artifact, context).pass)
    return SanitizerResult(
        pass=(len(violations) == 0),
        checks_run=[r.id for r in applicable],
        violations=violations,
        warnings=warnings,
        human_review_required=human_review,
    )
```

### H.3 Sanitizer placement

The sanitizer is invoked at **three points**:

1. **On agent output** — before signing the handoff envelope.
2. **On receiver ingest** — before consuming an incoming artifact (defense in depth: the sender ran it, but the receiver verifies again).
3. **On tool call** — pre-call hook for any tool that publishes externally (Meta, Google, JioAds, WhatsApp, YouTube, Sprinklr). A tool call that would breach a rule is blocked at the Tool Mesh.

### H.4 Sanitizer failure modes (handled)

- **Rule registry stale** → block + page Resource Curator.
- **Context insufficient to evaluate rule** → return `inconclusive`; default to human review.
- **Agent loops on auto-fix** (rare but possible) → max 3 fix iterations, then escalate.
- **Sanitizer itself errors** → fail closed (block, never silently pass).

---

## §I ERROR HANDLING, RETRIES, FALLBACKS

### I.1 Tool call error classes

| Class | Example | Behavior |
|---|---|---|
| Transient | 429 rate-limited, 503 unavailable | Exponential backoff, max 5 retries |
| Auth | 401, expired token | Refresh token, retry once; else escalate |
| Bad request | 400, schema error | Fail fast, do not retry; surface to agent |
| Quota exhausted | Account spend cap, plan limit | Fail, surface to budget owner |
| Compliance block | Sanitizer rejection | Fail, return structured violations to agent |
| Vendor API breaking change | Method removed | Fail, page Resource Curator |

### I.2 Fallback chains

- **Bhashini unavailable** → fall back to internal IndicBERT/IndicTrans model (cached). Never silently fall back to a non-Indian-trained translator for regional languages.
- **Adobe Firefly unavailable** → fall back to internal Stable Diffusion XL with brand LoRA. Never fall back to a model without content credentials.
- **Meta API breaking change mid-campaign** → freeze writes; reads continue; alert.
- **GA4 thresholding cohort too small** → switch to BigQuery export pathway for unsampled data.

### I.3 Idempotency

All write operations (campaign creation, post publishing, budget changes) carry an `idempotency_key`. Retries with the same key do not create duplicates. This is non-negotiable; without it, network retries become double-posts and budget over-spend.

---

## §J OBSERVABILITY & AUDIT TRAIL

### J.1 What is logged (every call)

```json
{
  "trace_id": "uuid",
  "span_id": "uuid",
  "parent_span_id": "uuid",
  "tenant_id": "uuid",
  "campaign_id": "string",
  "agent_id": "drishti|disha|...",
  "agent_version": "1.2",
  "model": "claude-opus-4.7|gpt-5|gemini-2.5-ultra|...",
  "tool_id": "mcp_server.method",
  "tool_version": "v25.0",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "tokens_in": 1234,
  "tokens_out": 567,
  "vendor_cost_usd": 0.04,
  "latency_ms": 1245,
  "status": "success|error|blocked",
  "error_class": "string",
  "compliance_checks_run": ["ASCI-DISC-001", "DPDP-CONSENT-001"],
  "compliance_violations": [],
  "human_in_the_loop_triggered": false,
  "timestamp": "2026-05-17T00:00:00Z"
}
```

### J.2 Audit destinations

- **Hot store**: OpenSearch / Elasticsearch — for queryable, 90-day retention.
- **Cold store**: S3 / GCS with object lock — for 5-year retention (DPDP-aligned).
- **Real-time alerts**: PagerDuty / Slack for `status=blocked`, sanitizer-violation rate spikes, and tool-version breaking changes.

### J.3 What you can ask the trail

- "Show me every Meta campaign Lakshya launched in last 30 days, with sanitizer-violation history."
- "Which concept did Disha kill on this client, and why?"
- "Did Vaani use Bhashini for the Tamil version, or did it fall back?"
- "Reconstruct the full chain from brief lock → final report for campaign X." (full lineage, hash-verified)

This isn't just operational hygiene. Under DPDP, when the DPBI eventually audits, the auditable trail is the difference between a fine and a clean bill.

---

## §K HUMAN-IN-THE-LOOP GATES (codified)

| Gate | Trigger | Who Approves | Default SLA |
|---|---|---|---|
| Brief lock | Drishti signals lock | Client AOR + brand owner | 48h |
| Concept selection | Disha presents slate | Client + creative lead | 5 business days |
| Cultural-risk medium-or-high | Any rule with `human_review_on_fail` fires | DEI + legal | 24h |
| Pre-launch | Lakshya signals launch-ready | Brand owner + media director | 24h |
| Mid-flight budget shift > 20% | Lakshya proposes | Brand owner | 4h |
| Crisis response | Lehar flags PR risk | Comms lead | 30 min |
| Final report sign-off | Pramaan delivers report | Brand owner + finance | 48h |

Each gate has a default escalation chain. If approver SLA breaches, the campaign halts at that gate. No silent waits.

---

## §L DEPLOYMENT RUNBOOK (Day-0 → Day-30)

**Day 0–3 — Infrastructure**
- Stand up MCP Tool Mesh (auth, rate limit, audit, cost).
- Provision tenant namespace.
- Wire HashiCorp Vault / Secrets Manager.
- Spin up `chitra-regdb`, `chitra-calendar`, `chitra-history`, `chitra-assetdb`, `chitra-sanitizer` (native MCP servers).
- Load rule registry from §G; mark all rules `shadow_mode: true` for first 14 days.

**Day 3–7 — External MCP servers**
- Install official servers: Meta, Google Ads, GA4, BigQuery, Adobe, Figma, Canva, Runway, ElevenLabs, YouTube, WhatsApp Business, LinkedIn, X.
- Install wrappers: JioAds, Amazon Ads, DV360, Bhashini, Sprinklr, market-data sources.
- Tenant-scope OAuth flows for each.
- Pin versions per A.4.

**Day 7–10 — Agent deployment**
- Load v1.1 scaffolds with v1.2 tool manifests (§B).
- Wire each agent's MCP client to the Tool Mesh.
- Validate each agent against its handoff schema (§F) using a dry-run brief.

**Day 10–14 — Schema and sanitizer validation**
- Run a synthetic brief through Drishti → Disha → Roop+Vaani → Rekha+Gati → Lakshya → Pramaan.
- Verify every envelope, every artifact passes schema check.
- Verify sanitizer in shadow mode is correctly flagging seeded violations.

**Day 14–30 — Shadow to enforce**
- Lift `shadow_mode` on rules in batches by severity.
- Run two real campaigns end-to-end under full enforcement.
- Tune rule false-positive rates.
- Establish monthly Resource Curator cadence per v1.1 §A.

**Day 30+ — Production**
- New tenants onboard via templated provisioning.
- Resource Pack refresh runs on schedule.
- Compliance rule registry updates flow through the two-person review.

---

## §M WHAT'S DELIBERATELY OUT OF SCOPE FOR v1.2

- **Multi-tenant federated learning** — earliest at v2.0.
- **Agent-to-agent direct messaging** — all inter-agent traffic still flows through MCP Tool Mesh + envelope; A2A protocols are too immature in May 2026 to bet on.
- **Real-time creative generation in-stream** during ad serving — out of scope; CHITRA produces assets, the platforms serve them.
- **MMM integration** — referenced as an attribution lens, but the MMM model itself sits outside CHITRA; v1.3 will add a connector.
- **Brand-safety partner integrations** (IAS, DV) at the Lakshya layer — v1.3.

---

## §N VERSION SUMMARY

| Version | Delivered | What's In |
|---|---|---|
| v1.0 | Architecture | Nine roles, four phases, security wrapper, India-specific layer |
| v1.1 | Agent scaffolds + Global Dynamic Resource Pack | Deployable system prompts; refreshable resource pack |
| **v1.2** | **This document** | **MCP tool integration; verifiable per-agent JSON Schema handoffs; codified §G ruleset; runtime sanitizer; deployment runbook** |
| v1.3 (planned) | Tool deepening + brand-safety + MMM connector | IAS/DV; MMM input layer; Looker Studio Pro templates |
| v1.4 (planned) | Closed-loop tenant learning | Pramaan → Drishti automated feedback within tenant boundary |
| v2.0 (planned) | Federated learning | Cross-tenant pattern learning without leakage |

---

*End of CHITRA v1.2 specification. Knowledge horizon: 16 May 2026. Next scheduled refresh: 16 June 2026 (regulatory + cricket + Google Ads API).*
