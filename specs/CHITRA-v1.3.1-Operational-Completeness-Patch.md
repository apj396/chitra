# CHITRA v1.3.1
**Operational Completeness Patch — Compatibility Sweep, Webhook Contracts, Platform Spec Data**

> **Knowledge horizon**: 16 May 2026 (inherits from v1.2.x + v1.3).
> **Status**: Patch release. Three production-blocking operational items deferred from v1.2.3.
> **Scope**: Three sections, three deliverables. Each is operational rather than contractual — these are the things between "the substrate is specified" and "the substrate can deploy."

---

## §0 WHY A SEPARATE PATCH

The three items in this patch were named explicitly in v1.2.3's closing notes as "intentionally deferred — operational, not contract." All three were also referenced as gating production deployment but never formally specified. Putting them in v1.3 (the eval harness) would have mixed two unrelated frameworks under one cover.

Each item answers a question v1.2.x assumed had an answer:

| Item | Question it answers |
|---|---|
| Compatibility sweep job (§1) | What does the weekly job that checks Google Ads / Meta / Adobe / etc. for breaking changes actually look like — schema, output, escalation? |
| Webhook delivery contracts (§2) | When HITL approval is requested or a sanitizer violation fires or a deepfake-consent check fails, how does the notification actually reach a human? |
| Platform spec data (§3) | The `chitra-resourcepack.platform.spec` schema in v1.2.3 §5 is empty — what does it actually return when called for `instagram_reel` on 17 May 2026? |

All three are deploy-blockers. Without §1, the platform silently breaks when vendors ship breaking changes. Without §2, HITL gates exist on paper but never reach humans. Without §3, every agent that queries `platform.spec` gets nothing — and Gati's exports cannot validate against current platform reality.

---

## §1 COMPATIBILITY SWEEP JOB

### §1.1 What it is

A scheduled internal job that runs weekly and checks every pinned external MCP server for upstream changes. v1.2 §A.4 described this in prose ("Job: mcp-compatibility-sweep, Cadence: every Monday 06:00 IST"). v1.3.1 makes it operational: a schema, output format, escalation pathway, and the role-handoff to Resource Curator that turns "breaking change detected" into "rule updated and deployed."

The compatibility sweep is **not** a CHITRA-callable service — agents do not invoke it. It is internal infrastructure that runs on a cron-like schedule. Its outputs are consumed by the Resource Curator role (v1.2.2 §9.1) and feed into the eval regression suite (v1.3 §6) when version bumps trigger re-evaluation.

### §1.2 Job specification

```json
{
  "$id": "https://chitra.ai/jobs/v1.3.1/compatibility-sweep.json",
  "title": "MCP Compatibility Sweep Job",
  "version": "1.0.0",
  "type": "scheduled_internal_job",
  "owner_role": "platform_engineering",
  "invoked_by": ["cron_scheduler", "manual_trigger_by_curator"],

  "schedule": {
    "default_cadence": "weekly",
    "default_time_ist": "06:00 IST Monday",
    "rationale": "Pre-business-hours run gives Resource Curator full Monday to triage findings before Tuesday tenant-facing work.",
    "supplementary_triggers": [
      "On vendor changelog webhook (if vendor publishes)",
      "On manual curator trigger (when a tenant reports a tool failure)",
      "Within 4 hours of a deployed CHITRA version bump"
    ]
  },

  "scope": {
    "covered_servers": [
      "meta-marketing", "meta-ads-cli",
      "google-ads-mcp", "google-analytics-mcp", "looker-studio-mcp", "bigquery-mcp",
      "youtube-mcp", "whatsapp-business",
      "linkedin-marketing-mcp", "x-marketing-mcp", "sprinklr-mcp",
      "adobe-firefly", "adobe-creative-cloud", "figma-mcp", "canva-mcp",
      "runway-mcp", "elevenlabs-mcp", "bhashini-mcp",
      "jioads-mcp", "amazon-ads-mcp", "dv360-mcp"
    ],
    "native_servers_excluded": [
      "chitra-search", "chitra-marketdata", "chitra-calendar",
      "chitra-regdb", "chitra-assetdb", "chitra-history",
      "chitra-resourcepack", "chitra-sanitizer", "legal-precheck"
    ],
    "exclusion_rationale": "Native servers are versioned by CHITRA itself; compatibility is enforced internally via the rule-registry and schema-registry version pins."
  },

  "steps": [
    {
      "step_id": "fetch_manifests",
      "description": "Pull latest manifest from each vendor MCP registry.",
      "input": "list of pinned servers + pinned versions from tenant_context.tool_authorization",
      "output": "raw_manifest_artifacts",
      "timeout_minutes": 15
    },
    {
      "step_id": "diff_against_pinned",
      "description": "Compute structural diff between pinned version manifest and latest manifest.",
      "input": "raw_manifest_artifacts + pinned_versions",
      "output": "diff_report",
      "diff_dimensions": [
        "methods_added",
        "methods_removed",
        "methods_renamed",
        "field_added_required",
        "field_added_optional",
        "field_removed",
        "field_renamed",
        "field_type_changed",
        "enum_values_added",
        "enum_values_removed",
        "auth_scope_changed",
        "rate_limit_changed",
        "pricing_changed",
        "deprecation_notice_present",
        "sunset_date_announced"
      ]
    },
    {
      "step_id": "classify_severity",
      "description": "Classify each diff item by severity.",
      "input": "diff_report",
      "output": "classified_diffs",
      "severity_rubric": {
        "breaking": "Pinned-version calls fail when latest version is honored. Methods or required fields removed/renamed/type-changed.",
        "non_breaking_significant": "Auth or rate-limit changes; deprecation notices; sunset dates within 90 days; pricing changes >20%.",
        "non_breaking_minor": "Methods or optional fields added; enum values added; documentation-only changes.",
        "informational": "Sunset dates >90 days out; preview features announced; documentation reorganized."
      }
    },
    {
      "step_id": "auto_bump_minor",
      "description": "For non_breaking_minor diffs only, auto-bump the pinned version if auto_bump policy permits.",
      "input": "classified_diffs",
      "output": "auto_bump_actions_log",
      "constraint": "auto_bump is permitted only on patch and minor versions; major versions ALWAYS require Resource Curator review."
    },
    {
      "step_id": "open_tickets",
      "description": "For breaking and non_breaking_significant, open tickets to Resource Curator.",
      "input": "classified_diffs",
      "output": "ticket_ids",
      "ticket_template": "see §1.4"
    },
    {
      "step_id": "trigger_regression_if_breaking",
      "description": "Any breaking change blocks production use of affected MCP server until reviewed; agents that call the affected methods enter degraded mode (read-only where possible, paused where not).",
      "input": "classified_diffs",
      "output": "degraded_mode_announcements",
      "additional_action": "v1.3 §6 regression suite scheduled for re-run after Curator resolves the breaking change."
    },
    {
      "step_id": "publish_sweep_report",
      "description": "Write the full sweep report to chitra-history under artifact_type=compatibility_sweep_report.",
      "input": "all prior step outputs",
      "output": "sweep_report_artifact_id"
    }
  ]
}
```

### §1.3 Sweep report output schema

```json
{
  "$id": "https://chitra.ai/artifacts/v1.3.1/compatibility_sweep_report.json",
  "title": "Compatibility Sweep Report",
  "type": "object",
  "required": [
    "report_id", "sweep_run_at", "servers_swept",
    "findings", "auto_bumps_applied", "tickets_opened",
    "degraded_mode_active", "next_sweep_scheduled"
  ],
  "properties": {
    "report_id": {"type": "string"},
    "sweep_run_at": {"type": "string", "format": "date-time"},
    "sweep_duration_minutes": {"type": "number"},
    "trigger": {"enum": ["scheduled", "vendor_webhook", "manual_curator", "post_deployment"]},

    "servers_swept": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["server_id", "pinned_version", "latest_version", "diff_status"],
        "properties": {
          "server_id": {"type": "string"},
          "pinned_version": {"type": "string"},
          "latest_version": {"type": "string"},
          "version_distance": {"enum": ["same", "patch_behind", "minor_behind", "major_behind", "unknown"]},
          "diff_status": {"enum": ["no_changes", "minor_only", "significant", "breaking", "fetch_failed"]},
          "diff_artifact_uri": {"type": "string"}
        }
      }
    },

    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["finding_id", "server_id", "severity", "summary"],
        "properties": {
          "finding_id": {"type": "string"},
          "server_id": {"type": "string"},
          "severity": {"enum": ["breaking", "non_breaking_significant", "non_breaking_minor", "informational"]},
          "diff_dimension": {"type": "string"},
          "summary": {"type": "string"},
          "affected_methods": {"type": "array", "items": {"type": "string"}},
          "affected_agents": {"type": "array", "items": {"enum": ["drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan"]}},
          "affected_rule_ids": {"type": "array", "items": {"type": "string"}, "description": "Compliance rules that reference the affected surface"},
          "estimated_remediation_effort": {"enum": ["minutes", "hours", "days", "requires_design"]},
          "vendor_documentation_url": {"type": "string"},
          "deprecation_window_days": {"type": "integer", "description": "If vendor announced sunset, days until enforcement"}
        }
      }
    },

    "auto_bumps_applied": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "server_id": {"type": "string"},
          "from_version": {"type": "string"},
          "to_version": {"type": "string"},
          "applied_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "tickets_opened": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ticket_id": {"type": "string"},
          "finding_id": {"type": "string"},
          "assigned_to": {"type": "string", "description": "Resource Curator id"},
          "sla_breach_at": {"type": "string", "format": "date-time"},
          "ticket_priority": {"enum": ["P0_immediate", "P1_3_days", "P2_5_days", "P3_planned"]}
        }
      }
    },

    "degraded_mode_active": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "server_id": {"type": "string"},
          "affected_methods": {"type": "array", "items": {"type": "string"}},
          "mode": {"enum": ["read_only", "paused", "fallback_to_secondary"]},
          "active_since": {"type": "string", "format": "date-time"},
          "estimated_resolution": {"type": "string", "format": "date-time"}
        }
      }
    },

    "next_sweep_scheduled": {"type": "string", "format": "date-time"}
  }
}
```

### §1.4 Curator ticket template

When the sweep classifies a finding as `breaking` or `non_breaking_significant`, it opens a ticket. Templates are version-controlled so curator triage is consistent:

```yaml
ticket_template: compatibility-sweep-finding
fields:
  ticket_id: {auto-generated}
  finding_id: {from sweep report}
  severity: {breaking | non_breaking_significant}
  server_id: {affected MCP server}
  summary: {one-line description}

  affected_surface:
    methods: [list]
    agents_calling_methods: [list]
    compliance_rules_referencing_methods: [list]

  vendor_context:
    changelog_url: {if available}
    deprecation_notice: {if present}
    sunset_date: {if announced}
    migration_guide_url: {if available}

  recommended_actions:
    - {curator decides — examples below}

  sla:
    P0_immediate: "Same-day diagnosis; degraded mode active until resolved"
    P1_3_days: "Resolution within 3 business days"
    P2_5_days: "Resolution within 5 business days; no degraded mode required"
    P3_planned: "Add to quarterly review queue"

  resolution_required:
    - update_manifest_in_v1.2_section_B
    - update_pinned_version
    - update_affected_schemas_in_v1.2_section_C
    - update_compliance_rules_in_v1.2_section_G_if_affected
    - update_rule_to_schema_matrix_in_v1.2.1_section_F.12_if_rule_changed
    - trigger_regression_suite_run
    - notify_affected_tenants_if_user_visible_change
    - close_ticket_with_evidence
```

### §1.5 Example sweep findings

To make the format concrete, here are example findings from a hypothetical 19 May 2026 sweep:

**Example A — Breaking (Google Ads API v23.1 → v23.2)**:

```yaml
finding_id: cs_finding_2026-05-19_001
server_id: google-ads-mcp
severity: breaking
diff_dimension: field_renamed
summary: "asset.text_guidelines field 'must_include' renamed to 'required_phrases' in v23.2"
affected_methods:
  - asset.text_guidelines.set
affected_agents:
  - lakshya
affected_rule_ids: []
recommended_actions:
  - Update Lakshya manifest in v1.2 §B.8 to use 'required_phrases'
  - Update v1.2 §C.3 schema for asset.text_guidelines.set
  - Coordinate with tenants currently running AI Max campaigns
ticket_priority: P0_immediate
sla_breach_at: 2026-05-19T18:00:00Z
```

**Example B — Significant (Meta v25.0 deprecation notice)**:

```yaml
finding_id: cs_finding_2026-05-19_002
server_id: meta-marketing
severity: non_breaking_significant
diff_dimension: deprecation_notice_present
summary: "Meta announces v25.0 sunset 15 February 2027; advertisers must migrate to v26.0"
deprecation_window_days: 273
affected_methods: [campaign.create, campaign.update, ad.create]
affected_agents: [lakshya]
recommended_actions:
  - Add v26.0 to test pipeline within 30 days
  - Schedule migration coordination with tenants Q4 2026
  - Update tool-stack.current_version in chitra-resourcepack
ticket_priority: P2_5_days
```

**Example C — Minor (Adobe Firefly model_version update)**:

```yaml
finding_id: cs_finding_2026-05-19_003
server_id: adobe-firefly
severity: non_breaking_minor
diff_dimension: enum_values_added
summary: "model_version enum gains 'firefly_image_5' option; existing 'firefly_image_v_latest' unchanged"
auto_bump_applied: true
ticket_opened: false
```

### §1.6 Where the sweep job lives operationally

- **Repository**: CHITRA platform engineering repo (separate from agent and tenant code).
- **Runtime**: Containerized scheduled job (Kubernetes CronJob or equivalent).
- **Permissions**: Read-only access to vendor MCP registries; write access to chitra-history (for sweep reports); write access to ticket system; trigger access to regression suite.
- **Observability**: Sweep job emits its own audit events to `audit-sink.log` with `agent_id: "system_sweep_job"` and `tool_id: "compatibility_sweep"`.
- **Failure handling**: If a sweep step fails (e.g., a vendor registry is unreachable), the job retries with exponential backoff up to 3 times, then emits a degraded-mode warning and a P1 ticket for partial-sweep investigation.

---

## §2 WEBHOOK DELIVERY CONTRACTS FOR HITL NOTIFICATIONS

### §2.1 What this addresses

v1.2.2 §5 defined `hitl-approval.request_approval` — when an agent or system service requests human approval, the service returns a `request_id` and lists approvers_notified. But the actual mechanism by which the approver gets notified was left as "per-tenant integration."

That's still true — different tenants integrate with different notification systems (Slack, Teams, email, PagerDuty, in-app dashboards, mobile push). But the **contract between CHITRA and the tenant's notification stack** needs specification. Without it, every tenant onboards by reinventing the integration, and CHITRA has no guarantee the notification arrived.

### §2.2 Webhook contract model

CHITRA publishes notifications via outbound webhooks to tenant-configured endpoints. Each tenant declares one or more webhook destinations in `tenant_context.notification_endpoints`. CHITRA POSTs a structured payload to each endpoint and expects an acknowledgment.

```
CHITRA Notification Producer  →  HTTPS POST  →  Tenant Webhook Endpoint
                              ←  HTTP 200 ack  ←
```

Three production-grade requirements:

1. **At-least-once delivery** with idempotency keys; tenants must handle duplicates.
2. **Signed payloads** (HMAC-SHA-256); tenants verify the signature.
3. **Acknowledgment within 5 seconds** or CHITRA retries with exponential backoff; after 5 failed attempts in 30 minutes, the endpoint is marked unhealthy and the tenant's `incident_response_email` is notified.

### §2.3 Endpoint configuration schema (extension to tenant_context)

Adds to `tenant_context.notification_endpoints`:

```json
{
  "$id": "https://chitra.ai/schemas/v1.3.1/notification_endpoints.json",
  "type": "object",
  "properties": {
    "notification_endpoints": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["endpoint_id", "url", "events_subscribed", "signing_secret_handle"],
        "properties": {
          "endpoint_id": {"type": "string"},
          "url": {"type": "string", "format": "uri", "pattern": "^https://"},
          "description": {"type": "string"},

          "events_subscribed": {
            "type": "array",
            "minItems": 1,
            "items": {"enum": [
              "hitl.approval_requested",
              "hitl.approval_decided",
              "hitl.sla_breached",
              "sanitizer.violation_blocked",
              "sanitizer.warning_logged",
              "compliance.consent_withdrawal_received",
              "compliance.erasure_request_received",
              "incident.classified_as_breach",
              "compatibility_sweep.breaking_change_detected",
              "drift_detection.alert",
              "regression_suite.degradation_detected",
              "budget.cap_threshold_reached",
              "tool.degraded_mode_active",
              "audit.suspicious_access_pattern"
            ]}
          },

          "signing_secret_handle": {
            "type": "string",
            "description": "Handle to secret in secret-vault; CHITRA resolves at delivery time"
          },

          "delivery_config": {
            "type": "object",
            "properties": {
              "timeout_seconds": {"type": "integer", "default": 5, "maximum": 30},
              "retry_attempts": {"type": "integer", "default": 5},
              "retry_backoff": {"enum": ["linear", "exponential"], "default": "exponential"},
              "max_retry_window_minutes": {"type": "integer", "default": 30}
            }
          },

          "filters": {
            "type": "object",
            "description": "Optional filters on which events to deliver",
            "properties": {
              "min_severity": {"enum": ["info", "warn", "block", "critical"]},
              "campaign_id_filter": {"type": "array", "items": {"type": "string"}},
              "agent_filter": {"type": "array", "items": {"type": "string"}}
            }
          },

          "transformations": {
            "type": "object",
            "description": "Format transformations for specific tools",
            "properties": {
              "format": {"enum": ["chitra_canonical", "slack_block_kit", "teams_adaptive_card", "pagerduty_event_v2", "email_html", "email_text", "raw_json"], "default": "chitra_canonical"},
              "include_artifact_preview": {"type": "boolean", "default": false}
            }
          },

          "health_status": {
            "type": "object",
            "properties": {
              "healthy": {"type": "boolean"},
              "last_successful_delivery": {"type": "string", "format": "date-time"},
              "last_failed_delivery": {"type": "string", "format": "date-time"},
              "consecutive_failures": {"type": "integer"},
              "marked_unhealthy_at": {"type": "string", "format": "date-time"}
            }
          }
        }
      }
    }
  }
}
```

### §2.4 Canonical webhook payload

```json
{
  "$id": "https://chitra.ai/schemas/v1.3.1/webhook_payload.json",
  "type": "object",
  "required": [
    "delivery_id", "event_type", "event_id", "tenant_id",
    "produced_at", "payload_version",
    "signature_algorithm", "signature"
  ],
  "properties": {
    "delivery_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique per delivery attempt; duplicates indicate retries"
    },
    "event_id": {
      "type": "string",
      "format": "uuid",
      "description": "Idempotent key. Tenants MUST deduplicate by event_id."
    },
    "event_type": {"type": "string"},
    "tenant_id": {"type": "string"},
    "campaign_id": {"type": "string"},
    "produced_at": {"type": "string", "format": "date-time"},
    "payload_version": {"const": "1.3.1"},

    "signature_algorithm": {"const": "HMAC-SHA-256"},
    "signature": {
      "type": "string",
      "description": "Hex-encoded HMAC of (event_id + tenant_id + produced_at + payload) using endpoint's signing secret"
    },

    "severity": {"enum": ["info", "warn", "block", "critical"]},

    "summary": {"type": "string", "maxLength": 200, "description": "Human-readable one-line"},

    "payload": {
      "type": "object",
      "description": "Event-type-specific payload; see §2.5"
    },

    "actions": {
      "type": "array",
      "description": "Suggested actions for the recipient",
      "items": {
        "type": "object",
        "properties": {
          "action_id": {"type": "string"},
          "label": {"type": "string"},
          "url": {"type": "string", "description": "Tenant-facing dashboard URL to take the action"},
          "is_primary": {"type": "boolean"}
        }
      }
    },

    "links": {
      "type": "object",
      "properties": {
        "artifact_uri": {"type": "string"},
        "audit_trail_uri": {"type": "string"},
        "dashboard_uri": {"type": "string"}
      }
    },

    "retry_metadata": {
      "type": "object",
      "description": "Present only on retries",
      "properties": {
        "attempt_number": {"type": "integer", "minimum": 2},
        "original_produced_at": {"type": "string", "format": "date-time"},
        "previous_failure_reason": {"type": "string"}
      }
    }
  }
}
```

### §2.5 Event-type-specific payloads

Each event type defines what goes in `payload`. The most consequential ones:

#### `hitl.approval_requested`

```json
{
  "request_id": "uuid",
  "gate_type": "pre_launch",
  "requesting_agent": "lakshya",
  "artifact_type": "media_plan",
  "artifact_uri": "https://chitra.ai/artifacts/{tenant}/{campaign}/media_plan_v3",
  "rationale": "Launch ready for the diwali_2026 campaign with ₹2.4cr media budget across Meta, Google PMax, and JioHotstar.",
  "approvers_required": [
    {"approver_id": "u_jane_brand_owner", "role": "brand_owner"},
    {"approver_id": "u_amit_media_director", "role": "media_director"}
  ],
  "decision_logic": "all_must_approve",
  "sla_hours": 24,
  "sla_breach_at": "2026-05-20T10:30:00Z",
  "supporting_evidence_uris": [
    "https://chitra.ai/artifacts/.../concept_bible_v2",
    "https://chitra.ai/artifacts/.../asset_registry_v4"
  ]
}
```

#### `sanitizer.violation_blocked`

```json
{
  "violation_id": "uuid",
  "artifact_type": "social_post",
  "artifact_uri": "https://chitra.ai/artifacts/...",
  "agent_emitting": "lehar",
  "rules_failed": [
    {
      "rule_id": "ASCI-DISC-001",
      "rule_source": "ASCI",
      "message": "Paid partnership disclosure missing.",
      "evidence": "first_line does not start with #Ad",
      "auto_fix_available": true,
      "suggested_fix": "Prepend '#Ad ' to first_line"
    }
  ],
  "human_review_required": false
}
```

#### `compliance.erasure_request_received`

```json
{
  "incident_id": "uuid",
  "data_principal_id_hash": "sha256:...",
  "request_received_at": "2026-05-19T08:30:00Z",
  "compliance_deadline": "2026-05-22T08:30:00Z",
  "evidence_uri": "https://chitra.ai/incidents/...",
  "auto_cascade_jobs_scheduled": [
    "consent-vault.honor_withdrawal",
    "chitra-assetdb.artifact.delete (erasure path)",
    "external_platform_cascade (Meta + Google + WhatsApp lists)"
  ],
  "dpo_notification_required": true
}
```

#### `compatibility_sweep.breaking_change_detected`

```json
{
  "finding_id": "cs_finding_2026-05-19_001",
  "server_id": "google-ads-mcp",
  "summary": "Breaking field rename in asset.text_guidelines",
  "affected_agents": ["lakshya"],
  "degraded_mode_active": true,
  "estimated_resolution_at": "2026-05-19T18:00:00Z",
  "curator_ticket_id": "ticket_..."
}
```

### §2.6 Signature verification (tenant side)

Tenants must verify the signature before trusting the payload. Reference implementation:

```python
import hmac, hashlib

def verify_chitra_webhook(headers, body, signing_secret):
    signature_header = headers.get('X-Chitra-Signature')
    if not signature_header:
        return False, "missing signature"

    payload = body  # raw bytes
    expected = hmac.new(
        signing_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        return False, "signature mismatch"

    return True, "verified"
```

Tenants who skip verification accept the security consequences. CHITRA logs all delivery attempts; a tenant whose endpoint accepts unsigned-or-misverified payloads will be flagged on the quarterly security review.

### §2.7 Retry and dead-letter behavior

```yaml
delivery_lifecycle:
  attempt_1:
    timeout: 5s
    on_failure: schedule attempt_2 in 30s
  attempt_2:
    timeout: 5s
    on_failure: schedule attempt_3 in 2m
  attempt_3:
    timeout: 5s
    on_failure: schedule attempt_4 in 8m
  attempt_4:
    timeout: 5s
    on_failure: schedule attempt_5 in 20m
  attempt_5:
    timeout: 5s
    on_failure: mark endpoint UNHEALTHY; route to dead-letter queue

dead_letter_handling:
  - Endpoint marked unhealthy in tenant_context.notification_endpoints[].health_status
  - Tenant's incident_response_email receives a notification (via separate fallback channel)
  - Events queued in dead-letter for 7 days (Resource Curator can replay after fix)
  - HITL events with degraded delivery cause campaign halt at the gate (no silent pass)
```

The last bullet is the critical one. If a `hitl.approval_requested` event cannot be delivered, the gate does not silently auto-approve — it remains pending until either delivery succeeds or a curator intervenes. The HITL contract is preserved even when the notification channel breaks.

### §2.8 Multiple endpoints per tenant

A tenant can register multiple endpoints with overlapping event subscriptions. CHITRA delivers to all of them in parallel; the tenant's internal logic dedupes via `event_id`. Common configurations:

- **Production endpoint** (Slack workspace) + **Backup endpoint** (PagerDuty for SLA-breach events).
- **Per-team endpoint** (creative team Slack channel for sanitizer warnings, media team Slack for media-plan HITL).
- **Audit endpoint** (write-only sink for compliance recordkeeping).

The `filters` field on each endpoint lets a tenant route different event types to different consumers without CHITRA needing to understand the routing logic.

---

## §3 PLATFORM SPEC DATA — POPULATED CONTENT FOR `chitra-resourcepack.platform.spec`

### §3.1 What this is

The schema in v1.2.3 §5 defined the shape of `chitra-resourcepack.platform.spec`. v1.3.1 populates it with the actual data current as of 16 May 2026. Gati cannot validate Instagram Reel exports against safe zones without this data; Rekha cannot adapt to current YouTube thumbnail specs without it; Lakshya cannot brief PMax campaigns with current asset specifications without it.

This data has its own refresh cadence (quarterly per the v1.1 §A.4 refresh schedule), but the May 2026 baseline is critical to ship.

**Note on recent changes — these are post v1.1 knowledge horizon:**
- **March 2026**: Meta consolidated Facebook Stories, Facebook Reels, Instagram Stories, Instagram Reels into a unified 9:16 safe zone. One correctly-sized vertical asset now serves all four placements.
- **January 2026**: Instagram Explore merged into the Reels viewer; Explore-specific specs no longer exist as a separate placement.
- **Throughout 2026**: Meta now recommends 1440x2560 export for vertical placements (vs the older 1080x1920 minimum) for high-density screens; 1080x1920 still works.
- **YouTube Shorts ads**: Traditional ad units in Shorts feed now supported (was not previously).

### §3.2 Platform spec data — Meta family

```yaml
platform_id: instagram_feed
as_of_date: 2026-05-16
data_source: Meta Ads Help Center + Vizup 2026 Guide + Quickframe 2026 Guide

aspect_ratios_supported: ["4:5", "1:1", "1.91:1"]
preferred_aspect_ratio: "4:5"
preferred_rationale: |
  4:5 occupies more vertical screen real estate on mobile feeds — currently
  the dominant Instagram consumption surface. Meta's own placement guidance
  recommends 4:5 for Feed despite legacy emphasis on 1:1.

resolution_recommendations:
  preferred: "1080x1350 (4:5)"
  high_density: "1440x1800 (4:5)"
  square_fallback: "1080x1080 (1:1)"

max_duration_sec_video: 14460  # 241 minutes
min_duration_sec_video: 1
preferred_duration_sec_video: 30
preferred_duration_rationale: "Engagement drops sharply past 30s on Feed."

supported_codecs: ["h264", "h265"]
container_formats: ["mp4", "mov"]
max_filesize_mb_video: 4096   # 4GB hard, 1024 (1GB) for reliable processing
max_filesize_mb_image: 30
loudness_target_lufs: -16
caption_recommendations:
  burned_in: "strongly recommended (sound-off consumption ~80%)"
  primary_text_chars: 125
  headline_chars: 40

safe_zones:
  meta_unified_9_16: not_applicable
  feed_safe_zone:
    note: "Feed UI is less invasive than full-screen formats; primary concern is CTA button area at bottom."
    keep_critical_content_above_bottom_pixels: 220
last_updated: "2026-05-16"

---

platform_id: instagram_story
as_of_date: 2026-05-16
unified_safe_zone_with: [facebook_story, facebook_reel, instagram_reel]
unified_safe_zone_effective_date: "2026-03-15"

aspect_ratios_supported: ["9:16"]
preferred_aspect_ratio: "9:16"

resolution_recommendations:
  preferred: "1440x2560"
  minimum: "1080x1920"
  rationale: "1440-base is Meta's 2026 high-density recommendation; 1080-base still works without artifacts."

max_duration_sec_video: 120
min_duration_sec_video: 1
preferred_duration_sec_video: 15
delivered_as: "story_cards"
note_on_delivery: "Videos longer than 15s delivered as multiple Story cards; viewer chooses to continue."

supported_codecs: ["h264"]
container_formats: ["mp4", "mov"]
max_filesize_mb_video: 4096
loudness_target_lufs: -16

safe_zones:
  unified_9_16_safe_zone:
    canvas_basis: "1440x2560 (recommended) or 1080x1920 (minimum)"
    top_clear_pct: 14
    top_clear_pixels_at_1440: 358
    top_clear_pixels_at_1080: 250
    bottom_clear_pct: 20_to_35
    bottom_clear_pixels_at_1440_min: 512
    bottom_clear_pixels_at_1440_max: 896
    bottom_clear_pixels_at_1080_min: 340
    bottom_clear_pixels_at_1080_max: 504
    side_clear_pct: 6
    side_clear_pixels_at_1440: 87
    rationale: "Bottom zone variance: Reels captions expand depending on length and device; conservative export keeps the full 35% clear."
    effective_safe_zone_at_1440: "approximately 1267x1154 centered"

caption_recommendations:
  burned_in: "recommended; Stories have higher sound-on rate but captions help accessibility"
  primary_text_chars: 125

last_updated: "2026-05-16"

---

platform_id: instagram_reel
as_of_date: 2026-05-16
unified_safe_zone_with: [facebook_story, facebook_reel, instagram_story]
unified_safe_zone_effective_date: "2026-03-15"

aspect_ratios_supported: ["9:16"]
preferred_aspect_ratio: "9:16"

resolution_recommendations:
  preferred: "1440x2560"
  minimum: "1080x1920"

max_duration_sec_video: 900   # 15 minutes (newer ceiling)
min_duration_sec_video: 1
preferred_duration_sec_video: 20
preferred_duration_rationale: |
  Performance sweet spot is 15-30s. Algorithm increasingly penalizes "dragged-out" content even within the 15-minute ceiling. 7-15s shows highest retention and rewatch rates.

hook_window_seconds: 3
hook_window_rationale: "First 3 seconds determine swipe-or-watch. Required visual movement or text hook."

supported_codecs: ["h264"]
container_formats: ["mp4", "mov"]
max_filesize_mb_video: 4096
loudness_target_lufs: -16

safe_zones:
  unified_9_16_safe_zone:
    inherits_from: "instagram_story"
    additional_note: "Caption text at bottom of Reels can take more vertical space than Stories; the full 35% bottom zone is the safer ceiling."

caption_recommendations:
  burned_in: "strongly recommended"
  primary_text_chars: 125

last_updated: "2026-05-16"

---

platform_id: facebook_feed
as_of_date: 2026-05-16

aspect_ratios_supported: ["4:5", "1:1", "1.91:1", "16:9"]
preferred_aspect_ratio: "4:5"

resolution_recommendations:
  preferred: "1080x1350 (4:5)"
  high_density: "1440x1800 (4:5)"

max_duration_sec_video: 14460
preferred_duration_sec_video: 30

caption_recommendations:
  burned_in: "strongly recommended"
  primary_text_chars: 125
  headline_chars: 40

last_updated: "2026-05-16"

---

platform_id: facebook_story
unified_safe_zone_with: [facebook_reel, instagram_story, instagram_reel]
inherits_from: instagram_story
note: "Identical specs post-March 2026 consolidation."

---

platform_id: facebook_reel
unified_safe_zone_with: [facebook_story, instagram_story, instagram_reel]
inherits_from: instagram_reel
note: "Identical specs post-March 2026 consolidation."

---

platform_id: whatsapp_business_template
as_of_date: 2026-05-16

template_categories: ["marketing", "utility", "authentication"]
opt_in_required: true
twenty_four_hour_utility_window_applies: true
pre_approval_required_per_template: true

aspect_ratios_supported_media:
  image: ["1:1", "1.91:1"]
  video: ["16:9", "9:16", "1:1"]
  document: ["pdf"]

max_filesize_mb:
  image: 5
  video: 16
  document: 100

text_limits:
  body_chars: 1024
  header_chars: 60
  footer_chars: 60

asci_disclosure_required_for_marketing_template: true
last_updated: "2026-05-16"
```

### §3.3 Platform spec data — Google / YouTube family

```yaml
platform_id: youtube_long
as_of_date: 2026-05-16

aspect_ratios_supported: ["16:9", "9:16", "1:1"]
preferred_aspect_ratio: "16:9"
preferred_rationale: "Watch-page experience; CTV consumption growing."

resolution_recommendations:
  preferred: "1920x1080"
  high_density: "3840x2160"
  minimum: "1280x720"

max_duration_sec_video: 43200   # 12 hours
min_duration_sec_video: 1
preferred_duration_sec_video: variable
preferred_duration_rationale: "Length depends on format; 8-12 min for tutorials, 15-25 min for long-form."

supported_codecs: ["h264", "h265", "vp9", "av1"]
container_formats: ["mp4", "mov", "webm"]
max_filesize_mb_video: 262144  # 256GB
loudness_target_lufs: -14

caption_recommendations:
  burned_in: "optional; YouTube auto-caption + manual SRT preferred"
  description_chars: 5000
  title_chars: 100

last_updated: "2026-05-16"

---

platform_id: youtube_short
as_of_date: 2026-05-16
traditional_ads_supported_in_feed: true
traditional_ads_effective_date: "2026 (Q1)"

aspect_ratios_supported: ["9:16"]
preferred_aspect_ratio: "9:16"

resolution_recommendations:
  preferred: "1080x1920"
  minimum: "720x1280"

max_duration_sec_video: 180   # 3 minutes
min_duration_sec_video: 1
preferred_duration_sec_video: 30
preferred_duration_rationale: "Algorithm rewards high completion; 7-15s for virality, 30-60s for engagement."

supported_codecs: ["h264", "h265"]
container_formats: ["mp4", "mov"]
loudness_target_lufs: -14

safe_zones:
  top_clear_pixels: 180
  bottom_clear_pixels: 390
  bottom_clear_pixels_rationale: "Channel info + CTA buttons + caption area at bottom"
  right_clear_pixels: 60
  right_clear_rationale: "Engagement icons (like, comment, share, subscribe)"
  effective_safe_area: "approximately 960x1350 centered"

hook_window_seconds: 3
caption_recommendations:
  burned_in: "strongly recommended"

last_updated: "2026-05-16"

---

platform_id: youtube_bumper
as_of_date: 2026-05-16

aspect_ratios_supported: ["16:9", "9:16", "1:1"]
preferred_aspect_ratio: "16:9"

duration_sec_video: 6
duration_sec_video_constraint: "fixed (non-skippable)"

resolution_recommendations:
  preferred: "1920x1080"

text_limits:
  headline_chars: 15
  cta_chars: 10

last_updated: "2026-05-16"

---

platform_id: youtube_skippable_in_stream
as_of_date: 2026-05-16

aspect_ratios_supported: ["16:9", "9:16", "1:1"]
preferred_aspect_ratio: "16:9"

min_duration_sec_video: 6
preferred_duration_sec_video: 15
preferred_duration_rationale: "Sweet spot before skip prompt (5s); 15s gives a clean second half post-skip-window."

resolution_recommendations:
  preferred: "1920x1080"

last_updated: "2026-05-16"

---

platform_id: youtube_non_skippable
as_of_date: 2026-05-16

aspect_ratios_supported: ["16:9", "9:16", "1:1"]
duration_sec_video_options: [15, 20]
duration_regional_variance: "15s in most regions; 20s in select markets including India"

resolution_recommendations:
  preferred: "1920x1080"

last_updated: "2026-05-16"

---

platform_id: google_display
as_of_date: 2026-05-16

asset_groups_required_for_pmax: true
text_limits:
  short_headline_chars: 30
  long_headline_chars: 90
  description_chars: 90
  business_name_chars: 25

image_aspect_ratios_required:
  - "1.91:1 (1200x628)"
  - "1:1 (1200x1200)"
  - "4:5 (960x1200)"
image_min_resolution_short_side: 600

video_aspect_ratios_supported: ["16:9", "9:16", "1:1"]
video_min_duration_sec: 10

last_updated: "2026-05-16"
```

### §3.4 Platform spec data — Indian platforms

```yaml
platform_id: jiohotstar_pre_roll
as_of_date: 2026-05-16

ownership: "JioHotstar (Reliance + Disney consolidated)"
total_subscribers_mn: 450
paying_subscribers_mn: 100
indian_ott_market_share_pct: 75

aspect_ratios_supported: ["16:9", "9:16", "1:1"]
preferred_aspect_ratio: "16:9"
preferred_rationale: "Pre-roll on long-form content; CTV growing share."

resolution_recommendations:
  preferred: "1920x1080"
  ctv_preferred: "3840x2160"

duration_sec_options: [6, 10, 15, 20, 30]
preferred_duration_sec_video: 15

supported_codecs: ["h264"]
container_formats: ["mp4"]
loudness_target_lufs: -23   # broadcast standard for OTT pre-roll

caption_recommendations:
  burned_in: "recommended; sound-on rate higher than social but variable"
  multilingual: "Hindi + English commonly required; regional language variants strongly recommended for regional content"

ad_inventory_types: ["pre_roll", "mid_roll", "banner", "masthead", "sponsored_content", "branded_property"]
targeting_capabilities: ["geographic", "language", "content_genre", "device", "demographic", "household"]
ipl_2026_reach_mn: 600
last_updated: "2026-05-16"

---

platform_id: sharechat
as_of_date: 2026-05-16

aspect_ratios_supported: ["9:16", "1:1", "16:9"]
preferred_aspect_ratio: "9:16"

resolution_recommendations:
  preferred: "1080x1920"

audience_profile:
  monthly_active_users_mn: 350
  languages: 15
  tier_2_3_4_strength: "dominant"
  consumption_in_local_language_pct: 90

content_recommendations:
  vernacular_native_required: true
  english_first_content_underperforms: true

last_updated: "2026-05-16"

---

platform_id: moj
as_of_date: 2026-05-16

aspect_ratios_supported: ["9:16"]
preferred_aspect_ratio: "9:16"

resolution_recommendations:
  preferred: "1080x1920"

max_duration_sec_video: 90
preferred_duration_sec_video: 30
cut_pacing_recommendation_sec_per_cut: "0.5-1.5"

monthly_active_users_mn: 160
regional_first: true

last_updated: "2026-05-16"

---

platform_id: josh
as_of_date: 2026-05-16

aspect_ratios_supported: ["9:16"]
preferred_aspect_ratio: "9:16"

resolution_recommendations:
  preferred: "1080x1920"

max_duration_sec_video: 60
preferred_duration_sec_video: 25
competitive_strength: "Hindi, Tamil, Telugu, Marathi"

last_updated: "2026-05-16"
```

### §3.5 Platform spec data — Other key surfaces

```yaml
platform_id: x_video
as_of_date: 2026-05-16

aspect_ratios_supported: ["16:9", "1:1", "9:16"]
preferred_aspect_ratio: "16:9"

max_duration_sec_video: 140
preferred_duration_sec_video: 30
text_limits:
  tweet_chars: 280
last_updated: "2026-05-16"

---

platform_id: linkedin_video
as_of_date: 2026-05-16

aspect_ratios_supported: ["1:1", "16:9", "9:16"]
preferred_aspect_ratio: "1:1"
preferred_rationale: "Square performs best in LinkedIn Feed"

max_duration_sec_video: 600   # 10 minutes
preferred_duration_sec_video: 90
last_updated: "2026-05-16"

---

platform_id: ooh_dooh
as_of_date: 2026-05-16

aspect_ratios_supported: "site_dependent"
common_canvas_sizes:
  - "highway_hoarding_40x20_ft"
  - "bus_shelter_6x4_ft"
  - "mall_facade_variable"
  - "transit_screen_16:9"
  - "transit_screen_9:16"
  - "elevator_screen_9:16"

resolution_minimums_per_site_type:
  highway_hoarding: "min 100 DPI at final size"
  bus_shelter: "min 150 DPI at final size"
  digital_ooh: "match site's native panel resolution"

text_legibility_distance_meters:
  highway: ">50m readability required"
  bus_shelter: "5-10m"
  mall: "3-8m"

last_updated: "2026-05-16"

---

platform_id: whatsapp_status
as_of_date: 2026-05-16

aspect_ratios_supported: ["9:16"]
preferred_aspect_ratio: "9:16"
max_duration_sec_video: 60   # post-2024 increase
last_updated: "2026-05-16"
```

### §3.6 Data refresh cadence

This data is stored in `chitra-resourcepack.platform.spec` and refreshed:

- **Quarterly default**: 16 Aug 2026, 16 Nov 2026, 16 Feb 2027, etc.
- **Event-triggered**: any time the compatibility sweep (§1) detects platform-spec-relevant changes.
- **Curator-on-demand**: when a tenant or agent reports a spec mismatch.

Each entry carries `last_updated`. Agents that call `platform.spec` get the most recent data and should not cache beyond 7 days locally.

### §3.7 Backward compatibility note

Pre-March-2026 specs treated Facebook Stories, Facebook Reels, Instagram Stories, Instagram Reels as four independent specs. The unified safe zone (post-March 2026) means one correctly-sized 9:16 asset (1440x2560 preferred, 1080x1920 minimum) with the unified safe zone (Top 14% / Bottom 20-35% / Side 6%) works across all four.

Tenants migrating from earlier production should:
1. Re-export vertical assets at 1440x2560 if not already.
2. Validate against unified safe zone (Bottom 35% conservative ceiling).
3. Run the v1.3 §6 regression suite on Gati outputs to confirm no degradation.

### §3.8 What this data does not cover

- **Programmatic / DSP specs** (DV360, Trade Desk, JioAds, Amazon DSP) — these are vendor-mediated and vary by inventory. Data lives in the respective vendor MCP server schemas rather than centralized.
- **Print specifications** — newspaper jacket sizes, magazine spread specs — these are per-publication (Times of India ≠ The Hindu ≠ Hindustan Times) and live in `tenant_context.print_publication_specs`.
- **Email creative specs** — outside CHITRA's current scope; v1.4 may add.

---

## §4 INTEGRATION WITH PRIOR PATCHES

### §4.1 Compatibility sweep ↔ rule registry

When the sweep detects a breaking change affecting a compliance rule (e.g., a Meta API field referenced by `PLATFORM-TOS-META-SPECIAL-CAT-001`), the curator ticket includes the affected rule IDs. Curator workflow:

1. Update the manifest in v1.2 §B.
2. Update the schema in v1.2 §C if affected.
3. Amend the rule predicate in v1.2 §G if affected.
4. Re-run `chitra-sanitizer` calibration via v1.3 §5 because predicate changes can shift judge calibration.

### §4.2 Webhook contracts ↔ eval harness

The eval harness in v1.3 needs to know when agents are entering degraded mode (because regression scores from degraded-mode runs are not directly comparable to normal-mode runs). The `tool.degraded_mode_active` webhook event subscribes the eval system to these state changes; eval results from those windows are tagged so they don't pollute the regression baseline.

### §4.3 Platform spec data ↔ Gati eval

EVAL-GATI-001 criterion 2 ("Platform-spec correctness") in v1.3 §2.6 validates Gati's exports against `chitra-resourcepack.platform.spec`. Without §3.2–§3.5 populated, this criterion always returns "inconclusive" because there's no spec to compare against. v1.3.1 §3 unblocks Gati eval.

---

## §5 OPERATIONAL READINESS CHECKLIST

With v1.3.1 deployed, the following can now run:

- [ ] Weekly compatibility sweep — schedule cron job
- [ ] Sweep findings reach Resource Curator — ticket system integration live
- [ ] Tenant webhook endpoints registered — at minimum one per active tenant
- [ ] Webhook signing secrets provisioned in secret-vault
- [ ] Tenant verifies signatures (verified via sample HMAC test)
- [ ] Platform spec data loaded into `chitra-resourcepack.platform.spec` for May 2026 baseline
- [ ] First quarterly refresh of platform spec scheduled (16 Aug 2026)
- [ ] Gati eval rubric criterion 2 now testable against live data
- [ ] HITL approval routing tested end-to-end (request → notification → human decision → CHITRA receives decision)
- [ ] Compatibility sweep dead-letter dashboard accessible to Resource Curator

All ten items are operational prerequisites to deploying v1.0–v1.3.x in production.

---

## §6 VERSION SUMMARY

| Version | Adds | Status |
|---|---|---|
| v1.0 | Architecture | Released |
| v1.1 | Agent scaffolds + Global Dynamic Resource Pack | Released |
| v1.2 | MCP tool integration + handoff schemas + ruleset + sanitizer | Released |
| v1.2.1 | Extended handoff schemas + rule-to-schema matrix | Released |
| v1.2.2 | 24 underspecified contracts closed | Released |
| v1.2.3 | 27 final contract gaps + DPDP erasure flow + chitra-resourcepack schema | Released |
| v1.3 | Eval harness — calibrated rubric scoring, golden corpus, regression suite, drift detection, governance | Released |
| **v1.3.1** | **Compatibility sweep job + webhook contracts + populated platform spec data — three production-blocking operational items deferred from v1.2.3** | **This document** |
| v1.4 (planned) | Closed-loop tenant learning automation | Planned (requires 12+ months of v1.3 calibration data) |
| v2.0 (planned) | Federated learning across tenants | Planned (earliest 2027 H2) |

---

## §7 WHAT v1.3.1 DELIBERATELY DOES NOT INCLUDE

Three things I considered including and deferred:

1. **Webhook payload examples for every event type.** Showed the 4 most consequential in §2.5; the remaining ~10 follow the same shape. Documenting all 14 inline would mostly be repetition. The schema in §2.4 is sufficient for tenant implementation.

2. **Platform spec data for every minor platform.** Covered Meta family, Google/YouTube family, Indian platforms, and the most-used adjacent surfaces (X, LinkedIn, OOH/DOOH, WhatsApp Status). Telegram, Pinterest, Snapchat, Discord, Reddit, and emerging platforms are not yet in scope for Indian advertising's center of gravity; will be added in v1.3.2 if usage warrants.

3. **Compatibility sweep historical data.** No retrospective sweep of breaking changes since v1.0; the sweep operates forward from deployment day. Tenants migrating from earlier versions follow the §3.7 unified-safe-zone migration note as a manual one-time exercise.

---

*End of CHITRA v1.3.1 — operational completeness patch. With v1.0 through v1.3 + v1.3.1, the platform is contract-complete, eval-complete, and operationally-ready for production deployment. The next document (v1.4) is gated by 12+ months of v1.3 calibration data accumulating from live operation.*
