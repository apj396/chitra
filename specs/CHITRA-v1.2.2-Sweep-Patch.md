# CHITRA v1.2.2
**Sweep Patch — Closing Underspecified Contracts**

> **Knowledge horizon**: 16 May 2026 (inherits from v1.2).
> **Status**: Patch release. No breaking changes to v1.2 or v1.2.1; this is gap-closure for contracts that existed by reference but lacked specification.
> **Scope**: 24 underspecified contracts identified in the v1.2 sweep, grouped into eight sections.

---

## §0 SWEEP INVENTORY

What was missing, and why each item matters:

| # | Gap | Surface | Severity | Section |
|---|---|---|---|---|
| 1 | `legal-precheck` MCP server never schema'd | Tool manifests for Drishti/Disha/Roop/Vaani reference it | High | §1.1 |
| 2 | `chitra-regdb` MCP server never schema'd | Every agent reads from it; rules depend on it | **Critical** | §1.2 |
| 3 | `chitra-assetdb` MCP server never schema'd | Rekha/Gati/Lehar write to it | High | §1.3 |
| 4 | `chitra-history` MCP server never schema'd | Drishti/Disha/Pramaan depend on it | High | §1.4 |
| 5 | `chitra-calendar` MCP server never schema'd | All agents call festival/sports lookups | Medium | §1.5 |
| 6 | `chitra-marketdata` MCP server never schema'd | Drishti/Pramaan call RedSeer/Kantar/Nielsen | Medium | §1.6 |
| 7 | `chitra-search` MCP server never schema'd | Drishti/Disha/Lehar call web/image search | Medium | §1.7 |
| 8 | `consent-vault` interface never defined | DPDP-CONSENT-001 cannot execute without it | **Critical** | §2.1 |
| 9 | `rule-registry` interface never defined | Sanitizer pseudocode calls it; needs API | High | §2.2 |
| 10 | `audit-sink` write API never defined | J.1 specifies log shape but no write path | High | §2.3 |
| 11 | `secret-vault` abstraction never defined | D.2 lists vendors but no agent-facing API | High | §2.4 |
| 12 | `cost-accounting` API never defined | E.2 says calls are recorded but no read/write API | Medium | §2.5 |
| 13 | `tenant_context` schema never defined | Every agent reads tenant config; never specified | **Critical** | §3 |
| 14 | `onboarding_packet` schema never defined | v1.1 lists 12 fields but no JSON Schema | High | §4 |
| 15 | HITL approval interface never defined | §K lists gates but no request/response API | High | §5 |
| 16 | Tool Mesh wire protocol never defined | §A.2 describes chokepoint behavior; never specified | High | §6 |
| 17 | `tone_band` is `{"type": "object"}` with no inner shape | concept_bible.voice_calibration — soft field | Low | §7.1 |
| 18 | `script_typefaces` lacks `additionalProperties` | concept_bible.visual_deck.type_system | Low | §7.2 |
| 19 | `kill_risk_register` items are bare strings | concept_slate — should be structured | Low | §7.3 |
| 20 | CHITRA category → Meta special_ad_categories mapping | Required by PLATFORM-TOS-META-SPECIAL-CAT-001 | Medium | §8.1 |
| 21 | CHITRA category → platform age-floor mapping | Required by GAMING-RMG-001 etc. | Medium | §8.2 |
| 22 | Resource Curator role never specified | Referenced 6+ times; no spec | Medium | §9.1 |
| 23 | Shadow-mode → enforce lifecycle no API | Rules deploy in shadow; how do they graduate? | Medium | §9.2 |
| 24 | Incident classification interface never defined | DPDP-BREACH-NOTIFY-001 depends on it | High | §9.3 |

---

## §1 NATIVE MCP SERVER SCHEMAS

Each native server gets: a one-line purpose, the data model it owns, the methods it exposes, and the input/output schema for each method. Following the same JSON Schema 2020-12 style as v1.2 §F.

### §1.1 `legal-precheck` MCP server

**Purpose**: Trademark, slogan, image-rights, and IP clearance lookup. Returns clearance status; never returns full legal opinions (that requires human counsel).

**Data sources**: Indian Trade Marks Registry (TMR), USPTO TESS (international scope), WIPO Global Brand Database, internal tenant clearance log, music-rights libraries.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/legal-precheck.json",
  "title": "legal-precheck MCP server",
  "version": "1.0.0",
  "methods": {

    "trademark.search": {
      "description": "Search Indian and international trademark registries for conflicts.",
      "input_schema": {
        "type": "object",
        "required": ["query", "jurisdiction"],
        "properties": {
          "query": {"type": "string", "minLength": 2, "maxLength": 200, "description": "Word mark, slogan, or device description"},
          "jurisdiction": {"type": "array", "items": {"enum": ["IN", "IN-CLASS-9", "IN-CLASS-35", "IN-CLASS-38", "IN-CLASS-41", "IN-CLASS-42", "INTL_GLOBAL", "US", "EU", "UK"]}, "minItems": 1},
          "nice_classes": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 45}, "description": "Nice Classification classes relevant to the product/service"},
          "fuzzy_match": {"type": "boolean", "default": true},
          "phonetic_match": {"type": "boolean", "default": true}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["clearance_status", "conflicts_found", "search_run_at"],
        "properties": {
          "clearance_status": {"enum": ["clear", "conflicts_present", "review_required", "inconclusive"]},
          "conflicts_found": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["mark", "jurisdiction", "status", "owner_name", "match_strength"],
              "properties": {
                "mark": {"type": "string"},
                "jurisdiction": {"type": "string"},
                "registration_number": {"type": "string"},
                "nice_class": {"type": "integer"},
                "status": {"enum": ["registered", "pending", "abandoned", "opposed", "expired"]},
                "owner_name": {"type": "string"},
                "match_strength": {"enum": ["exact", "high_phonetic", "high_semantic", "moderate", "weak"]},
                "registered_at": {"type": "string", "format": "date"}
              }
            }
          },
          "search_run_at": {"type": "string", "format": "date-time"},
          "search_id": {"type": "string", "description": "Stable ID for audit retrieval"},
          "human_review_required": {"type": "boolean"},
          "disclaimer": {"const": "This is automated clearance, not legal opinion. High-conflict results require human counsel review."}
        }
      },
      "rate_limit": "60 req/min/tenant",
      "audit_required": true
    },

    "slogan.clearance": {
      "description": "Clearance check for a tagline/slogan including phonetic and semantic similarity.",
      "input_schema": {
        "type": "object",
        "required": ["slogan", "jurisdiction", "product_category"],
        "properties": {
          "slogan": {"type": "string", "minLength": 2, "maxLength": 300},
          "jurisdiction": {"type": "array", "items": {"type": "string"}, "minItems": 1},
          "product_category": {"type": "string"},
          "languages_to_check": {"type": "array", "items": {"type": "string"}, "description": "ISO 639-1 codes for transliteration/translation conflict check"}
        }
      },
      "output_schema": {
        "$ref": "#/methods/trademark.search/output_schema"
      }
    },

    "ip.clearance_check": {
      "description": "Holistic IP check — trademark + copyright + design + IP-conflict patterns.",
      "input_schema": {
        "type": "object",
        "required": ["artifact_reference", "checks"],
        "properties": {
          "artifact_reference": {"type": "string", "description": "URI or hash of artifact under review"},
          "checks": {
            "type": "array",
            "items": {"enum": [
              "trademark", "copyright_text", "copyright_image", "copyright_audio",
              "design_registration", "celebrity_likeness", "branded_character",
              "competitor_trademark_reference"
            ]},
            "minItems": 1
          }
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["overall_clearance", "per_check_results"],
        "properties": {
          "overall_clearance": {"enum": ["clear", "conflicts_present", "review_required"]},
          "per_check_results": {"type": "array", "items": {
            "type": "object",
            "required": ["check_type", "status"],
            "properties": {
              "check_type": {"type": "string"},
              "status": {"enum": ["clear", "flagged", "blocked"]},
              "evidence": {"type": "string"},
              "human_review_required": {"type": "boolean"}
            }
          }},
          "clearance_id": {"type": "string", "description": "Referenced by rule IP-TRADEMARK-001 as `legal_precheck.trademark_clearance_passed`"}
        }
      }
    },

    "image_rights.check": {
      "description": "Check stock-image, photographer, model-release rights for a referenced image.",
      "input_schema": {
        "type": "object",
        "required": ["image_uri"],
        "properties": {
          "image_uri": {"type": "string"},
          "intended_use": {"type": "array", "items": {"enum": ["editorial", "commercial", "social_organic", "social_paid", "broadcast", "ooh", "print", "merchandise"]}},
          "intended_territories": {"type": "array", "items": {"type": "string"}}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "rights_cleared": {"type": "boolean"},
          "license_documentation_uri": {"type": "string"},
          "restrictions": {"type": "array", "items": {"type": "string"}},
          "expires_at": {"type": "string", "format": "date"}
        }
      }
    }
  },

  "audit_trail": "Every call writes to audit-sink with input_hash, output_hash, search_id. Clearance results retain for 5 years (matches DPDP cold-store retention)."
}
```

**Rule dependency resolved**: `IP-TRADEMARK-001` (`legal_precheck.trademark_clearance_passed == true`) now resolves to `ip.clearance_check.output.per_check_results[where check_type='trademark'].status == 'clear'`.

### §1.2 `chitra-regdb` MCP server

**Purpose**: Live regulatory database — single source of truth for rules, disclaimers, sectoral codes, prohibited targeting bases, cultural risk register. Every agent reads from this. **The most-called native server in CHITRA.**

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/chitra-regdb.json",
  "title": "chitra-regdb MCP server",
  "version": "1.0.0",
  "data_model_owned": [
    "compliance_rules (the §G ruleset)",
    "sectoral_disclaimers",
    "prohibited_targeting_bases",
    "cultural_risk_register",
    "banned_claim_conditions (DMRA Schedule)",
    "asci_disclosure_rules",
    "platform_special_ad_categories"
  ],
  "methods": {

    "rules.by_sector": {
      "description": "Return all compliance rules applicable to a sector.",
      "input_schema": {
        "type": "object",
        "required": ["sector"],
        "properties": {
          "sector": {"enum": [
            "BFSI", "healthcare", "nutrition", "edtech", "gaming_rmg",
            "real_estate", "alcohol_surrogate", "tobacco_surrogate",
            "fmcg", "tech", "auto", "lifestyle", "retail", "d2c",
            "telecom", "energy", "travel", "insurance", "mutual_funds",
            "pharma", "ayurveda_traditional", "other"
          ]},
          "artifact_types": {"type": "array", "items": {"type": "string"}, "description": "Restrict to rules for these artifact types"}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["rules"],
        "properties": {
          "rules": {"type": "array", "items": {"$ref": "https://chitra.ai/schemas/v1.2/rule_object.json"}},
          "version": {"type": "string", "description": "Rule registry version at query time"},
          "fetched_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "rules.by_audience_age": {
      "description": "Return rules that apply when audience includes minors or a specific age band.",
      "input_schema": {
        "type": "object",
        "required": ["min_age"],
        "properties": {
          "min_age": {"type": "integer", "minimum": 0},
          "max_age": {"type": "integer", "minimum": 0}
        }
      },
      "output_schema": {"$ref": "#/methods/rules.by_sector/output_schema"}
    },

    "rules.by_claim_type": {
      "description": "Return rules triggered by a claim category — performance, health, financial, environmental, comparative.",
      "input_schema": {
        "type": "object",
        "required": ["claim_type"],
        "properties": {
          "claim_type": {"enum": ["performance", "health", "financial", "scientific", "environmental", "comparative", "testimonial"]}
        }
      },
      "output_schema": {"$ref": "#/methods/rules.by_sector/output_schema"}
    },

    "rules.applicable_to_artifact": {
      "description": "The primary entry point used by the sanitizer. Returns the full set of rules that apply to a given artifact + context.",
      "input_schema": {
        "type": "object",
        "required": ["artifact_type", "context"],
        "properties": {
          "artifact_type": {"type": "string"},
          "context": {
            "type": "object",
            "properties": {
              "sector": {"type": "string"},
              "audience_attributes": {"type": "object"},
              "product_category": {"type": "string"},
              "uses_ai_persona": {"type": "boolean"},
              "is_paid_partnership": {"type": "boolean"},
              "is_video": {"type": "boolean"},
              "channel": {"type": "string"}
            }
          },
          "shadow_mode": {"type": "boolean", "description": "If true, returns shadow-mode rules too; default false in production"}
        }
      },
      "output_schema": {"$ref": "#/methods/rules.by_sector/output_schema"}
    },

    "disclaimers.by_sector": {
      "description": "Return mandatory disclaimer texts for a sector + product. Approved canonical strings.",
      "input_schema": {
        "type": "object",
        "required": ["sector"],
        "properties": {
          "sector": {"type": "string"},
          "product_category": {"type": "string"},
          "language": {"type": "string", "default": "en"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "disclaimers": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["disclaimer_id", "text", "min_visible_duration_sec", "voiceover_required"],
              "properties": {
                "disclaimer_id": {"type": "string"},
                "text": {"type": "string"},
                "rule_id_source": {"type": "string", "description": "Rule that mandates this disclaimer"},
                "min_visible_duration_sec": {"type": "number"},
                "voiceover_required": {"type": "boolean"},
                "min_font_size_pt": {"type": "number"},
                "min_contrast_ratio": {"type": "number"}
              }
            }
          }
        }
      }
    },

    "asci.disclosure_rules": {
      "description": "Return ASCI disclosure rules (paid partnership labels, AI persona timing, etc.) keyed by post type.",
      "input_schema": {
        "type": "object",
        "required": ["content_type"],
        "properties": {
          "content_type": {"enum": ["static_post", "story", "reel", "long_video", "carousel", "live"]},
          "duration_sec": {"type": "number"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "paid_partnership_disclosure": {"type": "object"},
          "ai_persona_disclosure": {"type": "object"},
          "qualification_disclosure": {"type": "object"}
        }
      }
    },

    "targeting.prohibited_bases": {
      "description": "Return the current list of prohibited targeting bases under DPDP and constitutional principles.",
      "input_schema": {
        "type": "object",
        "properties": {
          "platform": {"type": "string", "description": "Optional; returns platform-specific additions if specified"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "prohibited_bases": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["basis", "rationale", "rule_id"],
              "properties": {
                "basis": {"type": "string"},
                "rationale": {"type": "string"},
                "rule_id": {"type": "string"},
                "exception_conditions": {"type": "array", "items": {"type": "string"}}
              }
            }
          }
        }
      }
    },

    "audience.minor_check": {
      "description": "Given an audience definition, return whether it includes minors (legally under 18 in India under DPDP).",
      "input_schema": {
        "type": "object",
        "required": ["audience_definition"],
        "properties": {
          "audience_definition": {"type": "object"}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["includes_minors", "min_age_floor"],
        "properties": {
          "includes_minors": {"type": "boolean"},
          "min_age_floor": {"type": "integer"},
          "verifiable_parental_consent_required": {"type": "boolean"},
          "restricted_categories_blocked": {"type": "array", "items": {"type": "string"}}
        }
      }
    },

    "cultural_risk_register": {
      "description": "Return cultural-risk markers relevant to a concept/asset for human-review escalation.",
      "input_schema": {
        "type": "object",
        "required": ["concept_text"],
        "properties": {
          "concept_text": {"type": "string"},
          "languages": {"type": "array", "items": {"type": "string"}},
          "target_geographies": {"type": "array", "items": {"type": "string"}}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "overall_risk": {"enum": ["low", "medium", "high"]},
          "markers_detected": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "category": {"enum": ["religion", "caste", "gender", "region", "political", "language", "child_safety", "body_image", "disability"]},
                "severity": {"enum": ["low", "medium", "high"]},
                "marker": {"type": "string"},
                "rule_id_triggered": {"type": "string"}
              }
            }
          }
        }
      }
    },

    "registry.version": {
      "description": "Returns current rule registry version and last-updated timestamp. Cheap call for cache-busting.",
      "input_schema": {"type": "object"},
      "output_schema": {
        "type": "object",
        "required": ["version", "last_updated"],
        "properties": {
          "version": {"type": "string"},
          "last_updated": {"type": "string", "format": "date-time"},
          "rule_count": {"type": "integer"}
        }
      }
    }
  }
}
```

The `rule_object.json` schema referenced is the TypeScript `ComplianceRule` interface from v1.2 §G.0, formalized:

```json
{
  "$id": "https://chitra.ai/schemas/v1.2/rule_object.json",
  "title": "Compliance Rule Object",
  "type": "object",
  "required": ["id", "source", "citation", "applies_to", "severity"],
  "properties": {
    "id": {"type": "string", "pattern": "^[A-Z]+-[A-Z]+-[0-9]{3}$"},
    "source": {"enum": ["ASCI", "DPDP", "IT_RULES", "CPA", "DMRA", "RBI", "SEBI", "IRDAI", "TRAI", "MOHFW", "CCPA_DARK", "PLATFORM_TOS", "RERA", "COTPA", "CHITRA_INTERNAL"]},
    "citation": {"type": "string"},
    "applies_to": {"type": "array", "items": {"type": "string"}},
    "applies_when_expression": {"type": "string", "description": "Predicate as evaluable expression"},
    "check_expression": {"type": "string", "description": "Check logic as evaluable expression"},
    "severity": {"enum": ["block", "warn", "info"]},
    "auto_fix_available": {"type": "boolean"},
    "human_review_on_fail": {"type": "boolean"},
    "failure_message_template": {"type": "string"},
    "shadow_mode": {"type": "boolean", "default": false},
    "version": {"type": "string"},
    "effective_from": {"type": "string", "format": "date"},
    "sunsets_on": {"type": "string", "format": "date"}
  }
}
```

### §1.3 `chitra-assetdb` MCP server

**Purpose**: Tenant-scoped, version-controlled asset registry. Owns the canonical record of every brief, concept, asset, motion cut, social post, and report.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/chitra-assetdb.json",
  "title": "chitra-assetdb MCP server",
  "version": "1.0.0",
  "tenancy": "strict — namespace is tenant_id; no cross-tenant read or write",
  "methods": {

    "artifact.write": {
      "description": "Write or update an artifact. Idempotent on artifact_id + version.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id", "artifact_type", "artifact_payload", "envelope"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "artifact_type": {"type": "string"},
          "artifact_id": {"type": "string", "description": "If absent, server generates"},
          "version": {"type": "string"},
          "artifact_payload": {"type": "object"},
          "envelope": {"type": "object", "description": "v1.2 §F.0 envelope"},
          "supersedes_artifact_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["artifact_id", "version", "uri", "hash"],
        "properties": {
          "artifact_id": {"type": "string"},
          "version": {"type": "string"},
          "uri": {"type": "string", "format": "uri"},
          "hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
          "written_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "artifact.read": {
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "artifact_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "artifact_id": {"type": "string"},
          "version": {"type": "string", "description": "If absent, returns latest"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "artifact_payload": {"type": "object"},
          "envelope": {"type": "object"},
          "version": {"type": "string"},
          "all_versions": {"type": "array", "items": {"type": "string"}}
        }
      }
    },

    "artifact.list": {
      "input_schema": {
        "type": "object",
        "required": ["tenant_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "artifact_type": {"type": "string"},
          "lock_status": {"type": "string"},
          "limit": {"type": "integer", "default": 50, "maximum": 500},
          "cursor": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "artifacts": {"type": "array", "items": {"type": "object"}},
          "next_cursor": {"type": "string"}
        }
      }
    },

    "asset.write": {
      "description": "Write a binary asset (image, video, source file) to tenant blob storage.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id", "filename", "content_or_uri"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "filename": {"type": "string"},
          "content_or_uri": {"type": "string", "description": "Base64 content or pre-signed upload URI"},
          "metadata": {"type": "object"},
          "content_credentials": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "asset_uri": {"type": "string"},
          "hash": {"type": "string"},
          "version": {"type": "string"}
        }
      }
    },

    "asset.version": {
      "description": "Bump version of an asset; preserves prior version per audit policy.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "asset_uri", "new_content_or_uri"],
        "properties": {
          "tenant_id": {"type": "string"},
          "asset_uri": {"type": "string"},
          "new_content_or_uri": {"type": "string"},
          "change_notes": {"type": "string"}
        }
      },
      "output_schema": {"$ref": "#/methods/asset.write/output_schema"}
    },

    "registry.update": {
      "description": "Update the registry index (which artifacts/assets belong to which campaign).",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id", "updates"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "updates": {"type": "array", "items": {"type": "object"}}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "registry_version": {"type": "string"},
          "updated_count": {"type": "integer"}
        }
      }
    }
  },

  "retention_policy": {
    "artifact_records": "5 years cold storage (DPDP-aligned)",
    "binary_assets": "per tenant policy, default 3 years",
    "deletions": "soft-delete with 30-day reversal window, then hard-delete on tenant DPDP retention schedule"
  }
}
```

### §1.4 `chitra-history` MCP server

**Purpose**: Cross-campaign learning store within a tenant. Owns the `learnings_dossier` lineage and the killed-concepts log.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/chitra-history.json",
  "title": "chitra-history MCP server",
  "version": "1.0.0",
  "methods": {

    "campaigns.by_client": {
      "description": "All past campaigns for a tenant, with summary metrics.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "client_id": {"type": "string"},
          "date_range": {"type": "object", "properties": {
            "start": {"type": "string", "format": "date"},
            "end": {"type": "string", "format": "date"}
          }},
          "include_summary_metrics": {"type": "boolean", "default": true}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "campaigns": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "campaign_id": {"type": "string"},
              "campaign_name": {"type": "string"},
              "date_range": {"type": "object"},
              "final_roas": {"type": "number"},
              "learnings_dossier_uri": {"type": "string"},
              "performance_report_uri": {"type": "string"}
            }
          }}
        }
      }
    },

    "learnings.latest": {
      "description": "Most recent learnings_dossier for a client. The closed-loop input to Drishti's next brief.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "client_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "client_id": {"type": "string"},
          "category_match": {"type": "boolean", "default": true, "description": "Restrict to learnings from same product category"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "dossier_uri": {"type": "string"},
          "dossier_payload": {"type": "object"},
          "dossier_age_days": {"type": "integer"}
        }
      }
    },

    "campaigns.competitor_archive": {
      "description": "Pre-curated competitor campaign archive for a sector (last 24 months). Public-domain references; no proprietary intelligence.",
      "input_schema": {
        "type": "object",
        "required": ["sector"],
        "properties": {
          "sector": {"type": "string"},
          "competitor_brands": {"type": "array", "items": {"type": "string"}},
          "since_date": {"type": "string", "format": "date"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "campaigns": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "brand": {"type": "string"},
              "campaign_name": {"type": "string"},
              "launched_at": {"type": "string", "format": "date"},
              "creative_synopsis": {"type": "string"},
              "key_visual_uris": {"type": "array", "items": {"type": "string"}},
              "estimated_reach": {"type": "integer"}
            }
          }}
        }
      }
    },

    "concepts.killed_log": {
      "description": "All concepts Disha has killed for a client, with kill tags. Prevents re-pitching dead horses.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "client_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "client_id": {"type": "string"},
          "kill_tag_filter": {"type": "array", "items": {"type": "string"}}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "killed_concepts": {"type": "array", "items": {"type": "object"}}
        }
      }
    },

    "campaigns.write_learnings": {
      "description": "Pramaan writes a new learnings_dossier; updates the lineage chain.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "client_id", "dossier_payload"],
        "properties": {
          "tenant_id": {"type": "string"},
          "client_id": {"type": "string"},
          "dossier_payload": {"type": "object", "description": "Conforms to learnings_dossier schema (v1.2.1 §F.11)"},
          "supersedes_dossier_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "dossier_id": {"type": "string"},
          "dossier_uri": {"type": "string"}
        }
      }
    }
  }
}
```

### §1.5 `chitra-calendar` MCP server

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/chitra-calendar.json",
  "title": "chitra-calendar MCP server",
  "version": "1.0.0",
  "data_source": "Global Dynamic Resource Pack §A.2 and §A.3 (v1.1)",
  "methods": {

    "festivals.in_range": {
      "input_schema": {
        "type": "object",
        "required": ["start_date", "end_date"],
        "properties": {
          "start_date": {"type": "string", "format": "date"},
          "end_date": {"type": "string", "format": "date"},
          "regions": {"type": "array", "items": {"type": "string"}, "description": "Filter by state or 'pan_india'"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "festivals": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "date": {"type": "string", "format": "date"},
              "regions_primary": {"type": "array", "items": {"type": "string"}},
              "marketing_window_days_before": {"type": "integer"},
              "marketing_window_days_after": {"type": "integer"},
              "category_relevance": {"type": "object", "description": "Map of category → relevance level"}
            }
          }}
        }
      }
    },

    "sports.in_range": {
      "input_schema": {
        "type": "object",
        "required": ["start_date", "end_date"],
        "properties": {
          "start_date": {"type": "string", "format": "date"},
          "end_date": {"type": "string", "format": "date"},
          "sport_types": {"type": "array", "items": {"enum": ["cricket", "football", "kabaddi", "olympics", "asian_games", "tennis", "f1"]}}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "events": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "event_name": {"type": "string"},
              "sport": {"type": "string"},
              "start_date": {"type": "string", "format": "date"},
              "end_date": {"type": "string", "format": "date"},
              "broadcast_platforms": {"type": "array", "items": {"type": "string"}},
              "expected_reach": {"type": "integer"}
            }
          }}
        }
      }
    },

    "moment.live_status": {
      "description": "Real-time poll: is there an active cricket/film/cultural moment to potentially hijack? Used by Lehar for 90-min response window.",
      "input_schema": {"type": "object"},
      "output_schema": {
        "type": "object",
        "properties": {
          "active_moments": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "moment_type": {"type": "string"},
              "description": {"type": "string"},
              "started_at": {"type": "string", "format": "date-time"},
              "estimated_half_life_hours": {"type": "number"},
              "trend_velocity": {"type": "number"}
            }
          }}
        }
      },
      "rate_limit": "1 req/30s/tenant (intentionally low to discourage polling; use webhooks)"
    }
  }
}
```

### §1.6 `chitra-marketdata` MCP server

**Purpose**: Wraps third-party market research APIs (RedSeer, Kantar IMRB, Nielsen India, BARC, Comscore) into a uniform query interface.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/chitra-marketdata.json",
  "title": "chitra-marketdata MCP server",
  "version": "1.0.0",
  "methods": {

    "market.size_estimate": {
      "input_schema": {
        "type": "object",
        "required": ["category", "geography"],
        "properties": {
          "category": {"type": "string"},
          "geography": {"type": "string"},
          "year": {"type": "integer", "minimum": 2020, "maximum": 2030},
          "preferred_source": {"enum": ["redseer", "kantar", "nielsen", "any"], "default": "any"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "tam_inr": {"type": "integer"},
          "sam_inr": {"type": "integer"},
          "som_inr": {"type": "integer"},
          "source": {"type": "string"},
          "source_url": {"type": "string"},
          "confidence": {"enum": ["high", "medium", "low"]},
          "methodology_notes": {"type": "string"}
        }
      }
    },

    "audience.profile": {
      "description": "Demographic + psychographic profile for a defined segment.",
      "input_schema": {
        "type": "object",
        "required": ["segment_definition"],
        "properties": {
          "segment_definition": {"type": "object"},
          "geography": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "segment_size_estimate": {"type": "integer"},
          "demographic_profile": {"type": "object"},
          "psychographic_indicators": {"type": "object"},
          "media_consumption_profile": {"type": "object"},
          "source": {"type": "string"}
        }
      }
    },

    "category.competitive_landscape": {
      "input_schema": {
        "type": "object",
        "required": ["category"],
        "properties": {
          "category": {"type": "string"},
          "geography": {"type": "string", "default": "IN"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "competitors": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "brand": {"type": "string"},
              "market_share_percent": {"type": "number"},
              "positioning": {"type": "string"},
              "share_of_voice_percent": {"type": "number"}
            }
          }}
        }
      }
    }
  },

  "data_freshness_policy": {
    "redseer_reports": "quarterly refresh",
    "kantar_data": "monthly refresh for syndicated, on-demand for custom",
    "nielsen_barc": "weekly refresh",
    "comscore": "monthly refresh"
  }
}
```

### §1.7 `chitra-search` MCP server

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.2/chitra-search.json",
  "title": "chitra-search MCP server",
  "version": "1.0.0",
  "underlying_providers": ["perplexity_api", "tavily", "bing_search_api", "google_custom_search"],
  "methods": {

    "web_search": {
      "input_schema": {
        "type": "object",
        "required": ["query"],
        "properties": {
          "query": {"type": "string", "maxLength": 200},
          "scope": {"enum": ["general", "market_research", "competitor_intel", "cultural_reference", "trend_lookup", "regulatory_check"]},
          "max_results": {"type": "integer", "default": 10, "maximum": 25},
          "freshness": {"enum": ["any", "past_year", "past_month", "past_week", "past_day"]},
          "geography_bias": {"type": "string", "default": "IN"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "results": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "title": {"type": "string"},
              "url": {"type": "string"},
              "snippet": {"type": "string"},
              "published_at": {"type": "string", "format": "date-time"},
              "source_credibility": {"enum": ["primary", "established_secondary", "aggregator", "unknown"]}
            }
          }}
        }
      }
    },

    "web_fetch": {
      "input_schema": {
        "type": "object",
        "required": ["url"],
        "properties": {
          "url": {"type": "string"},
          "extract_markdown": {"type": "boolean", "default": true},
          "max_tokens": {"type": "integer", "default": 8000}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "content": {"type": "string"},
          "title": {"type": "string"},
          "published_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "image_search": {
      "input_schema": {
        "type": "object",
        "required": ["query"],
        "properties": {
          "query": {"type": "string"},
          "max_results": {"type": "integer", "default": 10, "maximum": 30},
          "license_filter": {"enum": ["any", "creative_commons", "public_domain", "commercial_use"]},
          "scope": {"enum": ["visual_reference", "competitor_intel", "trend_lookup"]}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "images": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "url": {"type": "string"},
              "source_url": {"type": "string"},
              "dimensions": {"type": "string"},
              "license": {"type": "string"}
            }
          }}
        }
      }
    },

    "trend_lookup": {
      "description": "Trend feed across platforms — Lehar's primary intake.",
      "input_schema": {
        "type": "object",
        "properties": {
          "platforms": {"type": "array", "items": {"type": "string"}},
          "geography": {"type": "string", "default": "IN"},
          "min_velocity": {"type": "number"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "trends": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "trend_id": {"type": "string"},
              "description": {"type": "string"},
              "platform": {"type": "string"},
              "velocity": {"type": "number"},
              "estimated_half_life_hours": {"type": "number"}
            }
          }}
        }
      }
    }
  }
}
```

---

## §2 CROSS-CUTTING SERVICE INTERFACES

### §2.1 `consent-vault` interface

**Purpose**: Source of truth for Data Principal consent under DPDP Act 2023 / DPDP Rules 2025. Every consent artifact has a stable ID; every consent has a defined purpose, scope, and lifecycle. **DPDP-CONSENT-001 and DPDP-CHILDREN-001 cannot execute without this.**

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/consent-vault.json",
  "title": "consent-vault service interface",
  "version": "1.0.0",
  "compliance_anchor": "DPDP Act 2023 + DPDP Rules 2025 (notified 13 Nov 2025)",

  "data_model": {
    "ConsentArtifact": {
      "type": "object",
      "required": [
        "consent_artifact_id", "data_principal_id_hash", "data_fiduciary_id",
        "purpose", "data_categories", "status",
        "collected_at", "lawful_basis", "consent_evidence_uri"
      ],
      "properties": {
        "consent_artifact_id": {"type": "string", "format": "uuid"},
        "data_principal_id_hash": {
          "type": "string",
          "description": "SHA-256 of identifier — never store identifier directly in artifact references"
        },
        "data_fiduciary_id": {"type": "string", "description": "Tenant or sub-tenant"},
        "consent_manager_id": {"type": "string", "description": "Registered Consent Manager per DPDP Rule 4 (operational from 14 Nov 2026)"},
        "purpose": {
          "type": "array",
          "items": {"type": "object", "required": ["purpose_id", "description"], "properties": {
            "purpose_id": {"type": "string"},
            "description": {"type": "string"},
            "is_targeted_advertising": {"type": "boolean"},
            "is_profiling": {"type": "boolean"}
          }}
        },
        "data_categories": {
          "type": "array",
          "items": {"enum": [
            "name", "email", "phone", "address",
            "behavioral", "location", "device", "purchase_history",
            "financial", "health", "biometric",
            "demographic", "psychographic"
          ]}
        },
        "status": {"enum": ["valid", "withdrawn", "expired", "superseded"]},
        "collected_at": {"type": "string", "format": "date-time"},
        "expires_at": {"type": "string", "format": "date-time"},
        "withdrawn_at": {"type": "string", "format": "date-time"},
        "lawful_basis": {"enum": ["consent", "legitimate_use_certain_uses", "legal_obligation"]},
        "consent_evidence_uri": {
          "type": "string",
          "description": "Pointer to signed consent record — form snapshot, voice recording, click trail with timestamps"
        },
        "is_minor": {"type": "boolean"},
        "verifiable_parental_consent_artifact_id": {
          "type": "string",
          "description": "REQUIRED if is_minor=true"
        },
        "withdrawal_method": {"type": "string", "description": "How the Data Principal can withdraw"},
        "grievance_officer_contact": {"type": "string"},
        "cross_border_transfer_permitted": {"type": "boolean"},
        "retention_period_days": {"type": "integer"}
      },
      "allOf": [{
        "if": {"properties": {"is_minor": {"const": true}}},
        "then": {"required": ["verifiable_parental_consent_artifact_id"]}
      }]
    }
  },

  "methods": {

    "lookup": {
      "description": "Lookup a consent artifact by ID. The primary call made by DPDP-CONSENT-001.",
      "input_schema": {
        "type": "object",
        "required": ["consent_artifact_id"],
        "properties": {
          "consent_artifact_id": {"type": "string"},
          "purpose_filter": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["found", "consent"],
        "properties": {
          "found": {"type": "boolean"},
          "consent": {"$ref": "#/data_model/ConsentArtifact"},
          "purpose_match": {"type": "boolean", "description": "If purpose_filter provided, whether stored purpose covers the requested purpose"}
        }
      },
      "audit_required": true
    },

    "validate_for_processing": {
      "description": "Compound check: consent exists + status=valid + purpose matches + not expired + (if minor) parental consent valid.",
      "input_schema": {
        "type": "object",
        "required": ["consent_artifact_id", "processing_purpose", "data_categories"],
        "properties": {
          "consent_artifact_id": {"type": "string"},
          "processing_purpose": {"type": "string"},
          "data_categories": {"type": "array", "items": {"type": "string"}}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["valid"],
        "properties": {
          "valid": {"type": "boolean"},
          "reasons": {"type": "array", "items": {"enum": [
            "consent_not_found",
            "status_not_valid",
            "purpose_mismatch",
            "data_category_not_covered",
            "expired",
            "withdrawn",
            "minor_without_parental_consent",
            "cross_border_restriction"
          ]}}
        }
      }
    },

    "list_for_audience": {
      "description": "Given an audience definition (custom audience, CRM upload, etc.), return whether every member has valid consent.",
      "input_schema": {
        "type": "object",
        "required": ["audience_id", "processing_purpose"],
        "properties": {
          "audience_id": {"type": "string"},
          "processing_purpose": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["coverage_percent", "all_valid"],
        "properties": {
          "coverage_percent": {"type": "number", "minimum": 0, "maximum": 100},
          "all_valid": {"type": "boolean"},
          "invalid_count": {"type": "integer"},
          "invalid_reasons_breakdown": {"type": "object"}
        }
      }
    },

    "honor_withdrawal": {
      "description": "Process a Data Principal's withdrawal of consent. Triggers downstream purge across tenant systems.",
      "input_schema": {
        "type": "object",
        "required": ["consent_artifact_id", "withdrawal_evidence_uri"],
        "properties": {
          "consent_artifact_id": {"type": "string"},
          "withdrawal_evidence_uri": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "withdrawal_processed_at": {"type": "string", "format": "date-time"},
          "downstream_purge_jobs": {"type": "array", "items": {"type": "string"}, "description": "Job IDs for asset-DB, audience purge, ad-platform list deletion"}
        }
      }
    },

    "log_grievance": {
      "description": "Record a Data Principal grievance; starts the 90-day resolution clock per DPDP Rules.",
      "input_schema": {
        "type": "object",
        "required": ["grievance_text", "data_principal_id_hash"],
        "properties": {
          "grievance_text": {"type": "string"},
          "data_principal_id_hash": {"type": "string"},
          "related_consent_artifact_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "grievance_id": {"type": "string"},
          "received_at": {"type": "string", "format": "date-time"},
          "resolution_deadline": {"type": "string", "format": "date-time"}
        }
      }
    }
  },

  "rule_resolution": {
    "DPDP-CONSENT-001": "`consent_vault.lookup(consent_artifact_id).status == 'valid'` resolves to `consent-vault.validate_for_processing` returning `valid=true`."
  }
}
```

### §2.2 `rule-registry` interface

**Purpose**: Storage and lifecycle management for the §G rule set. Read by the sanitizer; written by the Resource Curator workflow.

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/rule-registry.json",
  "title": "rule-registry service interface",
  "version": "1.0.0",
  "methods": {

    "load_for": {
      "description": "Used by sanitizer pseudocode in v1.2 §H.2. Returns rules applicable to an artifact_type and context.",
      "input_schema": {
        "type": "object",
        "required": ["artifact_type", "context"],
        "properties": {
          "artifact_type": {"type": "string"},
          "context": {"type": "object"},
          "include_shadow_mode": {"type": "boolean", "default": false}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "rules": {"type": "array", "items": {"$ref": "https://chitra.ai/schemas/v1.2/rule_object.json"}},
          "registry_version": {"type": "string"}
        }
      }
    },

    "get": {
      "input_schema": {
        "type": "object",
        "required": ["rule_id"],
        "properties": {
          "rule_id": {"type": "string"}
        }
      },
      "output_schema": {"$ref": "https://chitra.ai/schemas/v1.2/rule_object.json"}
    },

    "propose": {
      "description": "Resource Curator submits a new or amended rule. Enters two-person review queue.",
      "input_schema": {
        "type": "object",
        "required": ["rule", "rationale", "curator_id"],
        "properties": {
          "rule": {"$ref": "https://chitra.ai/schemas/v1.2/rule_object.json"},
          "rationale": {"type": "string"},
          "curator_id": {"type": "string"},
          "deploys_to_shadow_mode": {"type": "boolean", "default": true},
          "shadow_period_days": {"type": "integer", "default": 14}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "proposal_id": {"type": "string"},
          "review_required_from": {"type": "array", "items": {"type": "string"}}
        }
      }
    },

    "approve": {
      "description": "Second reviewer approves a proposal. Activates in shadow mode by default.",
      "input_schema": {
        "type": "object",
        "required": ["proposal_id", "reviewer_id"],
        "properties": {
          "proposal_id": {"type": "string"},
          "reviewer_id": {"type": "string", "description": "MUST differ from proposer"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "rule_id": {"type": "string"},
          "deployed_at": {"type": "string", "format": "date-time"},
          "shadow_until": {"type": "string", "format": "date-time"}
        }
      }
    },

    "graduate_to_enforce": {
      "description": "Move a rule from shadow_mode to enforcement after its observation period.",
      "input_schema": {
        "type": "object",
        "required": ["rule_id", "curator_id"],
        "properties": {
          "rule_id": {"type": "string"},
          "curator_id": {"type": "string"},
          "shadow_observation_summary": {"type": "object"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "enforced_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "sunset": {
      "description": "Retire a rule (regulator superseded, rule subsumed by another, etc.).",
      "input_schema": {
        "type": "object",
        "required": ["rule_id", "reason", "curator_id"],
        "properties": {
          "rule_id": {"type": "string"},
          "reason": {"type": "string"},
          "curator_id": {"type": "string"},
          "replacement_rule_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "sunsetted_at": {"type": "string", "format": "date-time"}
        }
      }
    }
  }
}
```

### §2.3 `audit-sink` interface

**Purpose**: Write path for the audit log shape defined in v1.2 §J.1. Adds query API.

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/audit-sink.json",
  "title": "audit-sink service interface",
  "version": "1.0.0",
  "methods": {

    "log": {
      "description": "Append-only log write. Fire-and-forget from caller's perspective; durability guaranteed by the sink.",
      "input_schema": {
        "type": "object",
        "required": ["trace_id", "tenant_id", "agent_id", "tool_id", "status", "timestamp"],
        "properties": {
          "trace_id": {"type": "string"},
          "span_id": {"type": "string"},
          "parent_span_id": {"type": "string"},
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "agent_id": {"type": "string"},
          "agent_version": {"type": "string"},
          "model": {"type": "string"},
          "tool_id": {"type": "string"},
          "tool_version": {"type": "string"},
          "input_hash": {"type": "string"},
          "output_hash": {"type": "string"},
          "tokens_in": {"type": "integer"},
          "tokens_out": {"type": "integer"},
          "vendor_cost_usd": {"type": "number"},
          "internal_cost_usd": {"type": "number"},
          "latency_ms": {"type": "integer"},
          "status": {"enum": ["success", "error", "blocked"]},
          "error_class": {"type": "string"},
          "compliance_checks_run": {"type": "array", "items": {"type": "string"}},
          "compliance_violations": {"type": "array", "items": {"type": "object"}},
          "human_in_the_loop_triggered": {"type": "boolean"},
          "timestamp": {"type": "string", "format": "date-time"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "log_id": {"type": "string"},
          "accepted_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "query": {
      "description": "Hot-store query (last 90 days). Cold-store queries route to a different endpoint with higher latency.",
      "input_schema": {
        "type": "object",
        "properties": {
          "tenant_id": {"type": "string", "description": "REQUIRED for tenant-scoped queries"},
          "campaign_id": {"type": "string"},
          "agent_id": {"type": "string"},
          "tool_id": {"type": "string"},
          "status_filter": {"type": "array", "items": {"type": "string"}},
          "rule_id_filter": {"type": "string", "description": "Find every call where this rule fired"},
          "date_range": {"type": "object"},
          "limit": {"type": "integer", "default": 100, "maximum": 10000}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "entries": {"type": "array", "items": {"type": "object"}},
          "total_matching": {"type": "integer"},
          "query_latency_ms": {"type": "integer"}
        }
      }
    },

    "lineage": {
      "description": "Reconstruct the full chain for a campaign — brief → slate → bible → assets → media plan → reports. Hash-verified.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "chain": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "phase": {"type": "integer"},
              "artifact_type": {"type": "string"},
              "artifact_id": {"type": "string"},
              "agent": {"type": "string"},
              "timestamp": {"type": "string", "format": "date-time"},
              "hash": {"type": "string"},
              "hash_verified": {"type": "boolean"}
            }
          }},
          "chain_complete": {"type": "boolean"},
          "hash_chain_valid": {"type": "boolean"}
        }
      }
    }
  },

  "retention": {
    "hot_store": "90 days, OpenSearch/Elasticsearch",
    "cold_store": "5 years, S3/GCS with object lock — DPDP-aligned"
  }
}
```

### §2.4 `secret-vault` abstraction

**Purpose**: Agent-facing abstraction over HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager. Agents never see secrets; they get handles.

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/secret-vault.json",
  "title": "secret-vault service interface",
  "version": "1.0.0",
  "principle": "Agents request handles; Tool Mesh resolves handles to secrets at call time. Secrets never enter agent context.",

  "methods": {

    "get_handle": {
      "description": "Agent requests a handle for a tenant's credential to a specific service.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "agent_id", "service", "scope"],
        "properties": {
          "tenant_id": {"type": "string"},
          "agent_id": {"type": "string"},
          "service": {"enum": ["meta", "google_ads", "ga4", "bigquery", "adobe", "figma", "canva", "runway", "elevenlabs", "youtube", "whatsapp", "linkedin", "x", "jioads", "amazon_ads", "dv360", "bhashini", "sprinklr"]},
          "scope": {"enum": ["read", "write", "admin"]},
          "ttl_seconds": {"type": "integer", "maximum": 3600, "default": 300}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["handle", "expires_at"],
        "properties": {
          "handle": {"type": "string", "description": "Opaque short-lived handle"},
          "expires_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "rotate": {
      "description": "Force rotation of a tenant credential.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "service"],
        "properties": {
          "tenant_id": {"type": "string"},
          "service": {"type": "string"},
          "reason": {"enum": ["scheduled", "compromise_suspected", "tenant_request"]}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "rotated_at": {"type": "string", "format": "date-time"},
          "new_secret_id": {"type": "string"}
        }
      }
    }
  },

  "rotation_policy": {
    "oauth_refresh_tokens": "90 days",
    "access_tokens": "1 hour",
    "inter_agent_jwts": "5 minutes",
    "tenant_master_keys": "1 year"
  }
}
```

### §2.5 `cost-accounting` interface

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/cost-accounting.json",
  "title": "cost-accounting service interface",
  "version": "1.0.0",
  "methods": {

    "record": {
      "description": "Called by Tool Mesh after every external API call. Append-only.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id", "agent_id", "tool_id", "units", "vendor_cost_usd"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "agent_id": {"type": "string"},
          "tool_id": {"type": "string"},
          "units": {"type": "object", "description": "Token counts, API calls, seconds of audio, etc."},
          "vendor_cost_usd": {"type": "number"},
          "internal_cost_usd": {"type": "number"},
          "timestamp": {"type": "string", "format": "date-time"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "record_id": {"type": "string"}
        }
      }
    },

    "current_burn": {
      "description": "How much has this campaign spent so far, by category.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "total_compute_usd": {"type": "number"},
          "total_tools_usd": {"type": "number"},
          "total_media_inr": {"type": "integer"},
          "by_agent": {"type": "object"},
          "by_tool": {"type": "object"},
          "budget_envelope_remaining_pct": {"type": "number"}
        }
      }
    },

    "check_budget": {
      "description": "Pre-call check. Tool Mesh calls this before allowing expensive calls.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id", "estimated_cost_usd"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "estimated_cost_usd": {"type": "number"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "allow": {"type": "boolean"},
          "reason": {"type": "string"},
          "remaining_budget_usd": {"type": "number"}
        }
      }
    }
  }
}
```

---

## §3 TENANT CONTEXT SCHEMA

**Purpose**: Single canonical record of what defines a tenant. Every agent's "context" parameter resolves through this. The thing that's been implicitly assumed in every `context` object across v1.2.

```json
{
  "$id": "https://chitra.ai/schemas/v1.2.2/tenant_context.json",
  "title": "Tenant Context — canonical tenant configuration",
  "type": "object",
  "required": [
    "tenant_id", "tenant_name", "tenant_type",
    "data_fiduciary_id", "dpdp_retention_policy",
    "brand_guidelines_uri", "approval_chain",
    "active_clients", "deployment_region"
  ],
  "properties": {
    "tenant_id": {"type": "string", "format": "uuid"},
    "tenant_name": {"type": "string"},
    "tenant_type": {"enum": ["agency_independent", "agency_network", "in_house_brand", "in_house_d2c", "consultancy"]},
    "deployment_region": {"enum": ["IN", "IN_SDF"], "description": "IN_SDF = Significant Data Fiduciary per DPDP Rule 12"},

    "data_fiduciary_id": {"type": "string", "description": "Tenant's DPDP-registered Data Fiduciary ID"},
    "dpo_contact": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"}
      }
    },
    "dpdp_retention_policy": {
      "type": "object",
      "required": ["default_retention_days", "log_retention_days"],
      "properties": {
        "default_retention_days": {"type": "integer", "default": 365},
        "log_retention_days": {"type": "integer", "default": 1825, "description": "5 years cold storage"},
        "audience_consent_retention_days": {"type": "integer"},
        "creative_asset_retention_days": {"type": "integer"}
      }
    },
    "is_significant_data_fiduciary": {"type": "boolean", "description": "Per DPDP §10 / Rule 12 — additional obligations apply"},

    "brand_guidelines_uri": {"type": "string"},
    "brand_voice_archetypes": {"type": "array", "items": {"type": "string"}, "description": "Preferred Jungian archetypes for the brand"},
    "approved_typeface_library": {"type": "array", "items": {"type": "string"}},
    "approved_color_palette": {"type": "array", "items": {"type": "object"}},

    "approval_chain": {
      "type": "object",
      "required": ["brief_lock", "concept_selection", "pre_launch", "final_report"],
      "properties": {
        "brief_lock": {"type": "array", "items": {"$ref": "#/definitions/approver"}},
        "concept_selection": {"type": "array", "items": {"$ref": "#/definitions/approver"}},
        "pre_launch": {"type": "array", "items": {"$ref": "#/definitions/approver"}},
        "mid_flight_budget_shift_gt_20pct": {"type": "array", "items": {"$ref": "#/definitions/approver"}},
        "crisis_response": {"type": "array", "items": {"$ref": "#/definitions/approver"}},
        "final_report": {"type": "array", "items": {"$ref": "#/definitions/approver"}},
        "cultural_risk_review": {"type": "array", "items": {"$ref": "#/definitions/approver"}}
      }
    },

    "active_clients": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["client_id", "client_name", "sector"],
        "properties": {
          "client_id": {"type": "string"},
          "client_name": {"type": "string"},
          "sector": {"type": "string"},
          "sub_sectors": {"type": "array", "items": {"type": "string"}},
          "competitive_exclusions": {"type": "array", "items": {"type": "string"}, "description": "Other tenants/clients CHITRA should not cross-reference"}
        }
      }
    },

    "tool_authorization": {
      "type": "object",
      "description": "Which connected services this tenant has authorized",
      "properties": {
        "meta": {"type": "boolean"},
        "google_ads": {"type": "boolean"},
        "ga4": {"type": "boolean"},
        "jioads": {"type": "boolean"},
        "bhashini": {"type": "boolean", "default": true},
        "_others": {"type": "object", "additionalProperties": {"type": "boolean"}}
      }
    },

    "budget_envelope": {
      "type": "object",
      "properties": {
        "monthly_compute_usd_cap": {"type": "number"},
        "monthly_tools_usd_cap": {"type": "number"},
        "per_campaign_media_inr_cap": {"type": "integer"}
      }
    },

    "regulatory_overrides": {
      "type": "object",
      "description": "Tenant-specific overlays on top of default §G rules",
      "properties": {
        "additional_rule_ids_active": {"type": "array", "items": {"type": "string"}},
        "tenant_custom_rules": {"type": "array", "items": {"$ref": "https://chitra.ai/schemas/v1.2/rule_object.json"}}
      }
    },

    "incident_response": {
      "type": "object",
      "properties": {
        "incident_response_email": {"type": "string"},
        "dpdp_breach_notification_template_uri": {"type": "string"},
        "comms_lead_contact": {"type": "string"}
      }
    },

    "created_at": {"type": "string", "format": "date-time"},
    "updated_at": {"type": "string", "format": "date-time"},
    "version": {"type": "string"}
  },

  "definitions": {
    "approver": {
      "type": "object",
      "required": ["approver_id", "role"],
      "properties": {
        "approver_id": {"type": "string"},
        "role": {"type": "string"},
        "email": {"type": "string"},
        "default_sla_hours": {"type": "number"},
        "delegation_to": {"type": "string"}
      }
    }
  }
}
```

---

## §4 ONBOARDING PACKET SCHEMA

**Purpose**: Formalize v1.1 §2.1's 12 intake fields as a single schema. This is what the Data Onboarding phase actually produces and Drishti accepts.

```json
{
  "$id": "https://chitra.ai/schemas/v1.2.2/onboarding_packet.json",
  "title": "Onboarding Packet",
  "type": "object",
  "required": [
    "client_id", "client_name", "sector", "sub_sector",
    "product_or_service_description", "business_problem",
    "target_geography", "target_audience",
    "budget_envelope", "timeline",
    "mandatory_inclusions", "prohibited_territory",
    "approval_chain_reference"
  ],
  "properties": {
    "packet_id": {"type": "string"},
    "client_id": {"type": "string"},
    "client_name": {"type": "string"},
    "sector": {"type": "string", "description": "From regdb sector enumeration"},
    "sub_sector": {"type": "string"},

    "product_or_service_description": {"type": "string", "minLength": 30, "maxLength": 2000},
    "business_problem": {"type": "string", "minLength": 20, "maxLength": 500, "description": "One sentence; no jargon"},

    "target_geography": {
      "type": "object",
      "required": ["scope"],
      "properties": {
        "scope": {"enum": ["pan_india", "metro_only", "tier_1", "tier_1_and_2", "specific_states", "specific_cities", "rural", "diaspora"]},
        "states_included": {"type": "array", "items": {"type": "string"}},
        "cities_included": {"type": "array", "items": {"type": "string"}},
        "urban_rural_mix": {"type": "object", "properties": {
          "urban_pct": {"type": "number"},
          "rural_pct": {"type": "number"}
        }}
      }
    },

    "target_audience": {
      "type": "object",
      "required": ["demographics_hint", "psychographics_hint"],
      "properties": {
        "demographics_hint": {"type": "object"},
        "psychographics_hint": {"type": "object"},
        "audience_size_estimate": {"type": "integer"},
        "languages_to_address": {"type": "array", "items": {"type": "string"}}
      }
    },

    "existing_brand_guidelines_uri": {"type": "string"},
    "past_campaign_performance_uri": {"type": "string", "description": "If returning client; resolved via chitra-history"},

    "budget_envelope": {
      "type": "object",
      "required": ["total_inr", "media_split_pct", "production_split_pct"],
      "properties": {
        "total_inr": {"type": "integer", "minimum": 0},
        "media_split_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "production_split_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "agency_fees_split_pct": {"type": "number"},
        "tools_compute_split_pct": {"type": "number"}
      }
    },

    "timeline": {
      "type": "object",
      "required": ["kickoff_date", "target_launch_date"],
      "properties": {
        "kickoff_date": {"type": "string", "format": "date"},
        "target_launch_date": {"type": "string", "format": "date"},
        "review_windows": {"type": "array", "items": {"type": "object"}},
        "campaign_duration_days": {"type": "integer"}
      }
    },

    "mandatory_inclusions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["item", "source"],
        "properties": {
          "item": {"type": "string"},
          "source": {"enum": ["client_brief", "regulatory_pre_known", "legal_pre_known", "brand_guideline"]},
          "rule_id": {"type": "string"}
        }
      }
    },

    "prohibited_territory": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["item", "rationale"],
        "properties": {
          "item": {"type": "string"},
          "rationale": {"enum": ["client_instruction", "regulatory_pre_known", "competitive_sensitivity", "cultural_sensitivity"]}
        }
      }
    },

    "approval_chain_reference": {"type": "string", "description": "Reference into tenant_context.approval_chain — typically a campaign-specific override"},

    "audience_consent_artifacts": {
      "type": "array",
      "description": "Existing consent artifact IDs if reusing CRM/audience lists",
      "items": {"type": "string"}
    },

    "ai_persona_intent": {
      "type": "object",
      "properties": {
        "uses_ai_persona": {"type": "boolean"},
        "audience_includes_under_12": {"type": "boolean"}
      }
    },

    "completeness": {
      "type": "object",
      "required": ["all_required_fields_present"],
      "properties": {
        "all_required_fields_present": {"type": "boolean"},
        "ambiguous_fields": {"type": "array", "items": {"type": "string"}},
        "clarification_questions_pending": {"type": "array", "items": {"type": "object"}}
      }
    }
  }
}
```

**Validation gate behavior**: Drishti refuses to start brief generation until `completeness.all_required_fields_present == true AND completeness.ambiguous_fields == [] AND completeness.clarification_questions_pending == []`.

---

## §5 HITL APPROVAL INTERFACE

**Purpose**: Make v1.2 §K's approval gates operationally executable.

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/hitl-approval.json",
  "title": "HITL Approval Service",
  "version": "1.0.0",

  "data_model": {
    "ApprovalRequest": {
      "type": "object",
      "required": [
        "request_id", "tenant_id", "campaign_id", "gate_type",
        "requesting_agent", "artifact_uri", "rationale",
        "approvers_required", "sla_hours", "created_at", "status"
      ],
      "properties": {
        "request_id": {"type": "string", "format": "uuid"},
        "tenant_id": {"type": "string"},
        "campaign_id": {"type": "string"},
        "gate_type": {"enum": [
          "brief_lock", "concept_selection", "cultural_risk_review",
          "pre_launch", "mid_flight_budget_shift", "creative_refresh",
          "crisis_response", "final_report_signoff",
          "regulatory_review", "ip_clearance_review"
        ]},
        "requesting_agent": {"type": "string"},
        "artifact_uri": {"type": "string"},
        "rationale": {"type": "string"},
        "supporting_evidence_uris": {"type": "array", "items": {"type": "string"}},
        "approvers_required": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "approver_id": {"type": "string"},
              "role": {"type": "string"},
              "decision": {"enum": ["pending", "approved", "rejected", "approved_with_changes"]},
              "decided_at": {"type": "string", "format": "date-time"},
              "comment": {"type": "string"}
            }
          }
        },
        "decision_logic": {"enum": ["all_must_approve", "any_can_approve", "majority"], "default": "all_must_approve"},
        "sla_hours": {"type": "number"},
        "sla_breach_at": {"type": "string", "format": "date-time"},
        "on_sla_breach": {"enum": ["halt_pipeline", "escalate_to_backup", "notify_only"], "default": "halt_pipeline"},
        "created_at": {"type": "string", "format": "date-time"},
        "status": {"enum": ["pending", "approved", "rejected", "withdrawn", "sla_breached_halted"]}
      }
    }
  },

  "methods": {

    "request_approval": {
      "description": "Agent requests HITL approval. Returns request_id; agent's pipeline halts until status resolves.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "campaign_id", "gate_type", "requesting_agent", "artifact_uri"],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "gate_type": {"type": "string"},
          "requesting_agent": {"type": "string"},
          "artifact_uri": {"type": "string"},
          "rationale": {"type": "string"},
          "supporting_evidence_uris": {"type": "array", "items": {"type": "string"}}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["request_id", "approvers_notified", "sla_breach_at"],
        "properties": {
          "request_id": {"type": "string"},
          "approvers_notified": {"type": "array", "items": {"type": "string"}},
          "sla_breach_at": {"type": "string", "format": "date-time"}
        }
      }
    },

    "submit_decision": {
      "description": "Human approver submits decision (typically via UI; this is the API path).",
      "input_schema": {
        "type": "object",
        "required": ["request_id", "approver_id", "decision"],
        "properties": {
          "request_id": {"type": "string"},
          "approver_id": {"type": "string"},
          "decision": {"enum": ["approved", "rejected", "approved_with_changes"]},
          "comment": {"type": "string"},
          "changes_required": {"type": "array", "items": {"type": "object"}}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "request_overall_status": {"type": "string"},
          "pipeline_resumed": {"type": "boolean"}
        }
      }
    },

    "poll_status": {
      "input_schema": {
        "type": "object",
        "required": ["request_id"],
        "properties": {
          "request_id": {"type": "string"}
        }
      },
      "output_schema": {"$ref": "#/data_model/ApprovalRequest"}
    },

    "withdraw": {
      "description": "Requesting agent withdraws request (artifact changed, no longer needed).",
      "input_schema": {
        "type": "object",
        "required": ["request_id", "agent_id", "reason"],
        "properties": {
          "request_id": {"type": "string"},
          "agent_id": {"type": "string"},
          "reason": {"type": "string"}
        }
      },
      "output_schema": {"type": "object", "properties": {"withdrawn_at": {"type": "string", "format": "date-time"}}}
    }
  },

  "default_sla_hours_by_gate": {
    "brief_lock": 48,
    "concept_selection": 120,
    "cultural_risk_review": 24,
    "pre_launch": 24,
    "mid_flight_budget_shift": 4,
    "crisis_response": 0.5,
    "final_report_signoff": 48
  }
}
```

---

## §6 TOOL MESH WIRE PROTOCOL

**Purpose**: Specify what an agent's request to the Tool Mesh actually looks like on the wire. The chokepoint is described in v1.2 §A.2 but never specified.

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/tool-mesh.json",
  "title": "Tool Mesh wire protocol",
  "version": "1.0.0",
  "transport": "MCP over JSON-RPC 2.0; HTTP/SSE for remote servers, stdio for local",

  "request_envelope": {
    "type": "object",
    "required": [
      "jsonrpc", "method", "params", "id",
      "_chitra_meta"
    ],
    "properties": {
      "jsonrpc": {"const": "2.0"},
      "method": {"type": "string", "description": "{mcp_server}.{method_name}"},
      "params": {"type": "object", "description": "Method-specific parameters per server schema"},
      "id": {"type": "string", "format": "uuid"},
      "_chitra_meta": {
        "type": "object",
        "required": [
          "tenant_id", "campaign_id", "agent_id", "agent_version",
          "trace_id", "span_id", "secret_handle"
        ],
        "properties": {
          "tenant_id": {"type": "string"},
          "campaign_id": {"type": "string"},
          "agent_id": {"type": "string"},
          "agent_version": {"type": "string"},
          "trace_id": {"type": "string"},
          "span_id": {"type": "string"},
          "parent_span_id": {"type": "string"},
          "secret_handle": {"type": "string", "description": "From secret-vault; Tool Mesh resolves to actual credential"},
          "idempotency_key": {"type": "string"},
          "estimated_cost_usd": {"type": "number"},
          "compliance_pre_check_required": {"type": "boolean", "default": true}
        }
      }
    }
  },

  "response_envelope": {
    "type": "object",
    "properties": {
      "jsonrpc": {"const": "2.0"},
      "id": {"type": "string"},
      "result": {"type": "object"},
      "error": {
        "type": "object",
        "properties": {
          "code": {"type": "integer"},
          "message": {"type": "string"},
          "data": {"type": "object"}
        }
      },
      "_chitra_meta": {
        "type": "object",
        "properties": {
          "latency_ms": {"type": "integer"},
          "rate_limit_remaining": {"type": "integer"},
          "rate_limit_reset_at": {"type": "string", "format": "date-time"},
          "vendor_cost_usd": {"type": "number"},
          "compliance_checks_run": {"type": "array", "items": {"type": "string"}},
          "audit_log_id": {"type": "string"}
        }
      }
    }
  },

  "error_codes": {
    "-32000": "Application error (vendor-specific)",
    "-33001": "Tenant unauthorized for this tool",
    "-33002": "Agent unauthorized for this method",
    "-33003": "Rate limit exceeded (per-tool tier)",
    "-33004": "Rate limit exceeded (per-tenant tier)",
    "-33005": "Rate limit exceeded (per-agent-instance tier)",
    "-33006": "Budget cap exceeded — see cost-accounting",
    "-33007": "Compliance pre-check blocked the call",
    "-33008": "Secret handle expired or invalid",
    "-33009": "Idempotency key conflict — different params with same key",
    "-33010": "HITL approval required and pending",
    "-33011": "Tool version mismatch — Resource Curator action required"
  },

  "pre_call_hooks": [
    "auth_resolve (secret-vault.get_handle)",
    "rate_limit_check (three-tier)",
    "budget_check (cost-accounting.check_budget)",
    "compliance_pre_check (chitra-sanitizer.validate if writing external)",
    "audit_log_intent (audit-sink.log status=intent)"
  ],

  "post_call_hooks": [
    "audit_log_result (audit-sink.log status=success|error|blocked)",
    "cost_record (cost-accounting.record)",
    "rate_limit_decrement"
  ]
}
```

---

## §7 TIGHTENED SCHEMAS

### §7.1 `tone_band` (was `{"type": "object"}`)

Replaces the soft field in `concept_bible.verbal_deck.voice_calibration.tone_band`:

```json
{
  "tone_band": {
    "type": "object",
    "required": ["serious_to_playful", "premium_to_accessible", "traditional_to_modern"],
    "properties": {
      "serious_to_playful": {"type": "integer", "minimum": -5, "maximum": 5},
      "premium_to_accessible": {"type": "integer", "minimum": -5, "maximum": 5},
      "traditional_to_modern": {"type": "integer", "minimum": -5, "maximum": 5},
      "additional_axes": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["label", "value"],
          "properties": {
            "label": {"type": "string"},
            "value": {"type": "integer", "minimum": -5, "maximum": 5}
          }
        }
      }
    }
  }
}
```

This matches `creative_brief.tone_spectrum` in v1.2 §F.1 — they should be structurally identical.

### §7.2 `script_typefaces` with `additionalProperties`

```json
{
  "script_typefaces": {
    "type": "object",
    "description": "Map of Indic script → primary typeface for that script",
    "propertyNames": {"enum": ["devanagari", "tamil", "telugu", "bengali", "gujarati", "kannada", "malayalam", "gurmukhi", "odia", "nastaliq", "latin"]},
    "additionalProperties": {
      "type": "object",
      "required": ["typeface_name"],
      "properties": {
        "typeface_name": {"type": "string"},
        "weights_available": {"type": "array", "items": {"type": "string"}},
        "license_documented": {"type": "boolean"}
      }
    }
  }
}
```

### §7.3 `kill_risk_register` items structured

Replaces the bare-string array in `concept_slate.concepts_approved[].kill_risk_register`:

```json
{
  "kill_risk_register": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["risk", "stage"],
      "properties": {
        "risk": {"type": "string", "description": "What could kill this concept"},
        "stage": {"enum": ["pre_production", "production", "approval", "in_market", "post_launch"]},
        "mitigation": {"type": "string"},
        "probability": {"enum": ["low", "medium", "high"]}
      }
    }
  }
}
```

---

## §8 MAPPING TABLES

### §8.1 CHITRA `product_category` → Meta `special_ad_categories`

Required by `PLATFORM-TOS-META-SPECIAL-CAT-001`. Lakshya must declare correctly; this mapping is the source of truth.

```yaml
mapping:
  banking_lending_credit:           [CREDIT]
  insurance:                         []   # Not Meta-special, but RBI/IRDAI rules still apply
  mutual_funds_securities:           []
  hr_jobs_recruitment:               [EMPLOYMENT]
  real_estate:                       [HOUSING]
  rental_listings:                   [HOUSING]
  political_advocacy:                [ISSUES_ELECTIONS_POLITICS]
  fantasy_sports_real_money:         [ONLINE_GAMBLING_AND_GAMING]
  rummy_real_money:                  [ONLINE_GAMBLING_AND_GAMING]
  poker_real_money:                  [ONLINE_GAMBLING_AND_GAMING]
  online_real_money_gaming:          [ONLINE_GAMBLING_AND_GAMING]
  fmcg:                              []
  edtech:                            []
  healthcare:                        []
  tech_saas:                         []
  d2c_general:                       []
  auto:                              []
  tobacco:                           []   # Banned outright — TOBACCO-001 blocks
  alcohol_surrogate:                 []   # Heavy scrutiny — ALCOHOL-SURROGATE-001
```

### §8.2 CHITRA `product_category` → platform age-floor

Required by `GAMING-RMG-001` and similar rules.

```yaml
age_floor:
  fantasy_sports_real_money:         18
  rummy_real_money:                  18
  poker_real_money:                  18
  online_real_money_gaming:          18
  banking_lending_credit:            18
  insurance:                         18
  alcohol_surrogate:                 21
  tobacco_surrogate:                 21
  edtech_k12:                        13  # And requires verifiable parental consent per DPDP
  edtech_higher_ed:                  16
  fmcg_kids:                         child-targeted disallowed for restricted categories
  default:                           13  # Indian platform-base floor
```

---

## §9 OPERATIONAL CONTRACTS

### §9.1 Resource Curator role

**Definition**: Designated human role per tenant (and one cross-tenant Master Curator at the CHITRA-platform layer). Owns the Global Dynamic Resource Pack (v1.1 §A) and the rule registry (v1.2 §G).

**Responsibilities**:
- Monthly refresh cycle for regulatory updates (A.1, §G rules).
- Quarterly refresh for platform specs, tool stack, festival/sports calendars.
- Two-person review approval for new rule deployments.
- Monitoring shadow-mode rules for false-positive rates.
- Triaging tool-version breaking changes from the weekly compatibility sweep.

**SLAs**:
- Regulatory notification → rule update proposed: 5 business days.
- Tool API breaking change → mitigation deployed: 3 business days.
- Shadow-mode observation → graduate-or-revise decision: at end of 14-day window.

**Handoff artifact when role transitions**:

```json
{
  "$id": "https://chitra.ai/schemas/v1.2.2/curator_handoff.json",
  "type": "object",
  "required": ["outgoing_curator_id", "incoming_curator_id", "transferred_at", "open_items"],
  "properties": {
    "outgoing_curator_id": {"type": "string"},
    "incoming_curator_id": {"type": "string"},
    "transferred_at": {"type": "string", "format": "date-time"},
    "open_items": {"type": "array", "items": {"type": "object"}},
    "pending_proposals": {"type": "array", "items": {"type": "string"}},
    "shadow_mode_rules_in_observation": {"type": "array", "items": {"type": "string"}},
    "tool_version_pins_at_handoff": {"type": "object"}
  }
}
```

### §9.2 Shadow-mode → enforce lifecycle

Resolved by `rule-registry.graduate_to_enforce` in §2.2. The decision criteria:

```yaml
graduation_criteria:
  observation_period: 14_days_minimum
  required_metrics:
    - false_positive_rate: <= 5%
    - true_positive_count: >= 3   # Rule has actually caught something
    - no_unresolved_curator_concerns: true
  human_signoff: required from Resource Curator + one peer

graduation_blockers:
  - observed_false_positive_rate > 5%   # → revise rule predicate, restart shadow
  - rule_never_triggered                # → either rule is unnecessary or applies_when is wrong
  - regulator_amendment_landed_during_observation   # → restart observation with updated rule
```

### §9.3 Incident classification interface

Required by `DPDP-BREACH-NOTIFY-001`.

```json
{
  "$id": "https://chitra.ai/services/v1.2.2/incident-classification.json",
  "title": "Incident Classification Service",
  "version": "1.0.0",

  "methods": {

    "classify": {
      "input_schema": {
        "type": "object",
        "required": ["incident_description", "detected_at", "tenant_id"],
        "properties": {
          "incident_description": {"type": "string"},
          "detected_at": {"type": "string", "format": "date-time"},
          "tenant_id": {"type": "string"},
          "data_categories_potentially_affected": {"type": "array", "items": {"type": "string"}},
          "approximate_data_principals_affected": {"type": "integer"},
          "automated_classification_input": {"type": "object"}
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["classification", "is_dpdp_breach", "notification_required"],
        "properties": {
          "classification": {"enum": [
            "operational_only",
            "security_event_no_breach",
            "data_breach_minor",
            "data_breach_significant",
            "data_breach_significant_with_children_data",
            "service_disruption_no_data"
          ]},
          "is_dpdp_breach": {"type": "boolean"},
          "notification_required": {
            "type": "object",
            "properties": {
              "dpbi_notification": {"type": "boolean"},
              "data_principals_notification": {"type": "boolean"},
              "deadline": {"const": "without_delay"}
            }
          },
          "incident_id": {"type": "string"},
          "human_review_required": {"const": true, "description": "Always — incident classification is never fully automated"}
        }
      }
    },

    "record_notification_sent": {
      "input_schema": {
        "type": "object",
        "required": ["incident_id", "notification_type", "sent_at"],
        "properties": {
          "incident_id": {"type": "string"},
          "notification_type": {"enum": ["dpbi", "data_principals", "consent_manager", "regulator_sectoral"]},
          "sent_at": {"type": "string", "format": "date-time"},
          "evidence_uri": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "recorded_at": {"type": "string", "format": "date-time"}
        }
      }
    }
  },

  "trigger_sources": [
    "audit-sink anomaly detection",
    "consent-vault.honor_withdrawal downstream failure",
    "asset-db cross-tenant access alert",
    "manual report from incident_response.incident_response_email",
    "external researcher disclosure"
  ]
}
```

---

## §10 SUMMARY OF GAPS CLOSED

| # | Gap | Section | Resolution |
|---|---|---|---|
| 1 | `legal-precheck` schema | §1.1 | 4 methods specified |
| 2 | `chitra-regdb` schema | §1.2 | 9 methods specified; rule_object.json formalized |
| 3 | `chitra-assetdb` schema | §1.3 | 6 methods; tenancy + retention policy |
| 4 | `chitra-history` schema | §1.4 | 5 methods including closed-loop dossier write |
| 5 | `chitra-calendar` schema | §1.5 | 3 methods including live moment polling |
| 6 | `chitra-marketdata` schema | §1.6 | 3 methods over RedSeer/Kantar/Nielsen |
| 7 | `chitra-search` schema | §1.7 | 4 methods including trend lookup |
| 8 | `consent-vault` interface | §2.1 | Full DPDP-aligned data model + 5 methods |
| 9 | `rule-registry` interface | §2.2 | 6 methods including two-person review workflow |
| 10 | `audit-sink` interface | §2.3 | log + query + lineage methods |
| 11 | `secret-vault` abstraction | §2.4 | Handle-based; rotation policy |
| 12 | `cost-accounting` interface | §2.5 | record + current_burn + check_budget |
| 13 | `tenant_context` schema | §3 | Full canonical tenant configuration |
| 14 | `onboarding_packet` schema | §4 | Formal 12-field schema with validation gate |
| 15 | HITL approval interface | §5 | Request/decide/poll/withdraw; default SLAs |
| 16 | Tool Mesh wire protocol | §6 | JSON-RPC envelope + error codes + hooks |
| 17 | `tone_band` tightened | §7.1 | Structured 3+ axes |
| 18 | `script_typefaces` tightened | §7.2 | additionalProperties; license tracking |
| 19 | `kill_risk_register` tightened | §7.3 | Structured per-risk objects |
| 20 | CHITRA→Meta special_ad_categories | §8.1 | Mapping table |
| 21 | CHITRA→platform age-floor | §8.2 | Mapping table |
| 22 | Resource Curator role | §9.1 | Responsibilities + SLAs + handoff artifact |
| 23 | Shadow → enforce lifecycle | §9.2 | Graduation criteria + blockers |
| 24 | Incident classification | §9.3 | classify + record_notification_sent |

---

## §11 VERSION SUMMARY

| Version | Adds | Status |
|---|---|---|
| v1.0 | Architecture | Released |
| v1.1 | Agent scaffolds + Global Dynamic Resource Pack | Released |
| v1.2 | MCP tool integration + 6 handoff schemas + codified ruleset + sanitizer | Released |
| v1.2.1 | 4 additional handoff schemas + promoted learnings_dossier + matrix | Released |
| **v1.2.2** | **24 underspecified contracts closed: 7 native MCP schemas, 5 cross-cutting service interfaces, tenant_context, onboarding_packet, HITL approval, Tool Mesh wire protocol, 3 schema tightenings, 2 mapping tables, 3 operational contracts** | **This document** |
| v1.3 (planned) | Eval harness; brand-safety partners; MMM connector | Planned |
| v1.4 (planned) | Closed-loop tenant learning automation | Planned |
| v2.0 (planned) | Federated learning across tenants | Planned |

---

*End of CHITRA v1.2.2 sweep patch. With v1.2 + v1.2.1 + v1.2.2 in hand, every interface CHITRA touches is now defined or has an explicit handoff to a human role. No more "referenced but never specified." Next scheduled refresh: 16 June 2026 — same cadence as v1.2.*
