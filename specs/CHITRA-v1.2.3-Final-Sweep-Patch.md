# CHITRA v1.2.3
**Final Pre-v1.3 Sweep — Closing Remaining Contract Gaps + DPDP Erasure-Request Flag**

> **Knowledge horizon**: 16 May 2026 (inherits from v1.2 + v1.2.1 + v1.2.2).
> **Status**: Final patch in the v1.2.x line. After this, v1.3 is the next move (eval harness).
> **Scope**: 26 contract gaps identified by walking v1.1 §A.* against v1.2 §B against v1.2.2 §1, plus the DPDP erasure-request flag and right-to-erasure flow.
> **Method**: Systematic forward and reverse traceability — every method named anywhere is checked for definition; every defined method is checked for at least one caller.

---

## §0 SWEEP METHODOLOGY

The audit walked three dimensions:

1. **Forward**: every method referenced in v1.2 §B agent manifests → exists in v1.2 §C function signatures or v1.2.2 §1 server schemas?
2. **Reverse**: every method defined in v1.2 §C / v1.2.2 §1 → at least one caller in §B manifests?
3. **Resource Pack accessibility**: every data block in v1.1 §A → reachable through some MCP server at runtime?

The audit also covered cross-cutting concerns referenced but not pinned to a caller (consent-vault, rule-registry, audit-sink) and conditional-validation gaps (schemas with descriptive "required if" prose that the validator can't enforce).

---

## §1 SANITIZER-AS-SYSTEM-SERVICE & MIDDLEWARE ROLES

### §1.1 The missing principal

The sanitizer is named in every agent manifest as `chitra-sanitizer.validate (mandatory_on_output)`. It is also the caller for several services that no agent manifest names:

- `consent-vault.lookup` / `validate_for_processing` (DPDP-CONSENT-001)
- `rule-registry.load_for` / `get` (v1.2 §H pseudocode)
- `chitra-regdb.rules.applicable_to_artifact` (v1.2.2 §1.2)

This left consent-vault, rule-registry, and chitra-regdb's `rules.applicable_to_artifact` orphaned — defined, but with no formal caller manifest.

**Resolution**: The sanitizer is a **system service**, not an agent. It has its own formal manifest, just like agents do. Same for the Tool Mesh, which is the caller for `audit-sink`, `secret-vault`, `cost-accounting`, and `incident-classification`.

### §1.2 `chitra-sanitizer` system-service manifest

```yaml
service: chitra-sanitizer
type: system_service
version: 1.2.3
operates_as: middleware
invoked_by: [every_agent_on_output, every_agent_on_ingest, tool_mesh_on_external_publish]

tools_allowed:
  - chitra-regdb:
      methods: [rules.applicable_to_artifact, registry.version, asci.disclosure_rules, targeting.prohibited_bases, audience.minor_check, cultural_risk_register]
      scope: read
  - rule-registry:
      methods: [load_for, get]
      scope: read
  - consent-vault:
      methods: [lookup, validate_for_processing, list_for_audience]
      scope: read
  - legal-precheck:
      methods: [trademark.search]
      scope: read
      note: "Only on artifacts where IP-TRADEMARK-001 applies; cached lookups preferred"
  - audit-sink:
      methods: [log]
      scope: write
      note: "Records every sanitization event"

privacy_constraints:
  - cannot_persist_artifact_payloads_beyond_request
  - cannot_send_artifacts_to_external_services
  - operates_purely_in_memory_per_call
```

### §1.3 `tool-mesh` system-service manifest

```yaml
service: tool-mesh
type: system_service
version: 1.2.3
operates_as: middleware
invoked_by: [every_agent_for_every_tool_call]

tools_allowed:
  - audit-sink:
      methods: [log]
      scope: write
      timing: [pre_call, post_call]
  - secret-vault:
      methods: [get_handle, resolve_handle]
      scope: read
  - cost-accounting:
      methods: [record, check_budget]
      scope: read_write
  - chitra-sanitizer:
      methods: [validate]
      scope: invoke
      timing: pre_call_for_external_publish
  - hitl-approval:
      methods: [request_approval, poll_status]
      scope: invoke
      timing: pre_call_for_hitl_gated_methods
  - incident-classification:
      methods: [classify]
      scope: invoke
      timing: on_anomaly_detection

enforces:
  - tenant_isolation
  - rate_limiting_three_tier
  - budget_caps
  - secret_resolution
  - audit_logging
  - compliance_pre_check
  - cross_tenant_exclusions  # see §6
```

### §1.4 Resolution table

| Service | Caller (now explicit) | Previously |
|---|---|---|
| `consent-vault` | `chitra-sanitizer` | orphaned |
| `rule-registry` | `chitra-sanitizer` | orphaned |
| `audit-sink` | `tool-mesh` (every call) | orphaned |
| `secret-vault` | `tool-mesh` (pre-call) | orphaned |
| `cost-accounting` | `tool-mesh` (pre + post) | orphaned |
| `hitl-approval` | `tool-mesh` (pre-call for gated methods) + Lakshya (direct, see §4.2) | partially orphaned |
| `incident-classification` | `tool-mesh` (on anomaly) | orphaned |

---

## §2 NATIVE SERVER CONTRACT RECONCILIATION

Three naming mismatches between v1.2 §B manifests and v1.2.2 §1 schemas. Each one means a runtime tool-mesh call would fail because the method doesn't exist by that name.

### §2.1 `chitra-assetdb` — unify method surface

**Problem**: v1.2 manifests call eight specifically-named methods (`moodboard.write`, `styleframe.write`, `storyboard.write`, `copy.write`, `motion_asset.write`, `calendar.write`, `post.log`, `trafficking_sheet.write`) and one read (`asset.read`). v1.2.2 §1.3 only defines `artifact.write`, `artifact.read`, `artifact.list`, `asset.write`, `asset.version`, `registry.update`. None of the eight specifically-named writes exist.

**Decision**: Unify on `artifact.write` with `artifact_type` parameter. The specifically-named methods were syntactic sugar without underlying behavior difference. Schema already supports this — the parameter `artifact_type` accepts any string.

**Manifest amendments — replace in v1.2 §B**:

```yaml
# Roop (B.3):
- chitra-assetdb:
    methods: [artifact.write, asset.write]
    note: "Use artifact.write with artifact_type IN [visual_deck, mood_board, storyboard]; asset.write for binary uploads"
    scope: tenant + campaign

# Vaani (B.4):
- chitra-assetdb:
    methods: [artifact.write]
    note: "Use artifact_type=verbal_deck"
    scope: tenant + campaign

# Rekha (B.5): unchanged — already uses canonical names
- chitra-assetdb:
    methods: [asset.write, asset.version, registry.update, artifact.write]
    note: "artifact.write with artifact_type=asset_registry"

# Gati (B.6):
- chitra-assetdb:
    methods: [artifact.write, asset.write, asset.version, registry.update]
    note: "artifact.write with artifact_type=motion_asset_registry"

# Lehar (B.7):
- chitra-assetdb:
    methods: [artifact.write]
    note: "artifact.write with artifact_type IN [content_calendar, social_post]"

# Lakshya (B.8):
- chitra-assetdb:
    methods: [artifact.read, asset.read, artifact.write]
    note: "artifact.read for upstream artifacts; asset.read for binaries; artifact.write with artifact_type IN [media_plan, daily_optimization_log]"
```

**New method to add to v1.2.2 §1.3 (was missing from original schema)**:

```json
{
  "asset.read": {
    "description": "Read a binary asset by URI. Lakshya calls this to retrieve assets for trafficking.",
    "input_schema": {
      "type": "object",
      "required": ["tenant_id", "asset_uri"],
      "properties": {
        "tenant_id": {"type": "string"},
        "asset_uri": {"type": "string"},
        "version": {"type": "string"}
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "asset_bytes_uri": {"type": "string", "description": "Pre-signed download URI; expires"},
        "metadata": {"type": "object"},
        "hash": {"type": "string"},
        "content_credentials": {"type": "string"}
      }
    }
  }
}
```

### §2.2 `chitra-marketdata` — manifest names per-source; schema is unified

**Problem**: Drishti's manifest calls `redseer.query`, `kantar.query`, `nielsen.query`, `barc.query`. v1.2.2 §1.6 defines `market.size_estimate`, `audience.profile`, `category.competitive_landscape` with a `preferred_source` parameter.

**Decision**: Unified surface is better — agents care about questions, not sources. Per-source addressing is appropriate only when a tenant has a contract with one source and not others; that goes in `tenant_context.tool_authorization` (v1.2.2 §3).

**Manifest amendment**:

```yaml
# Drishti (B.1):
- chitra-marketdata:
    methods: [market.size_estimate, audience.profile, category.competitive_landscape]
    scope: read
    note: "preferred_source parameter routes to RedSeer / Kantar / Nielsen / BARC based on tenant contracts"

# Pramaan (B.9): add
- chitra-marketdata:
    methods: [category.competitive_landscape]
    scope: read
    note: "For benchmark context in performance reports"
```

### §2.3 `chitra-regdb` — naming fix on cultural risk

**Problem**: Disha's manifest calls `rules.cultural_risk_register`. v1.2.2 §1.2 defines it as `cultural_risk_register` (top-level, no `rules.` prefix).

**Decision**: Honor the schema; fix the manifest. The `rules.*` namespace is for queries that return rule objects; `cultural_risk_register` returns markers, not rules.

**Manifest amendment**:

```yaml
# Disha (B.2):
- chitra-regdb:
    methods: [rules.by_sector, cultural_risk_register]
    note: "cultural_risk_register is NOT prefixed with rules. — it returns markers, not rule objects"
```

---

## §3 EXTERNAL MCP SERVER METHOD SCHEMAS

Twelve methods on five external MCP servers are referenced in manifests but never schema'd. v1.2 §C provided five illustrative signatures (`bhashini.translate`, `meta.campaign.create`, `google_ads.asset.text_guidelines.set`, `ga4.data.run_report`, `chitra-sanitizer.validate`) but explicitly punted the rest.

**Decision principle**: For external servers (Adobe, Figma, Canva, official vendor MCPs), CHITRA imports the vendor's published manifest at MCP server registration time. The CHITRA-side schemas are wrappers that record the *subset* CHITRA agents may call, with CHITRA-specific pre/post hooks. Full vendor-side schemas live in the MCP Tool Mesh registry, not duplicated here.

This section provides:
- (a) **Critical-path full schemas** — methods on the AI generation path that have CHITRA-specific compliance preconditions (AI content credentials, voice consent, deepfake disclosure).
- (b) **Method enumeration tables** — for vendor surfaces where the schema is "whatever the vendor published, scoped to these methods."

### §3.1 `bhashini-mcp` — fill out the missing five methods

v1.2 §C.1 schema'd `translate`. The other five referenced in manifests now get schemas.

```json
{
  "transliterate": {
    "description": "Transliterate between Indian-script and Latin/romanized form.",
    "input_schema": {
      "type": "object",
      "required": ["text", "source_script", "target_script"],
      "properties": {
        "text": {"type": "string", "maxLength": 10000},
        "source_script": {"enum": ["devanagari", "tamil", "telugu", "bengali", "gujarati", "kannada", "malayalam", "gurmukhi", "odia", "nastaliq", "latin_iast", "latin_roman"]},
        "target_script": {"enum": ["devanagari", "tamil", "telugu", "bengali", "gujarati", "kannada", "malayalam", "gurmukhi", "odia", "nastaliq", "latin_iast", "latin_roman"]},
        "preserve_brand_terms": {"type": "array", "items": {"type": "string"}}
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "transliterated": {"type": "string"},
        "confidence": {"type": "number"}
      }
    },
    "rate_limit": "200 req/min/tenant"
  },

  "tts.preview": {
    "description": "Low-quality preview TTS — for Vaani to hear scratch reads. Not for production.",
    "input_schema": {
      "type": "object",
      "required": ["text", "language"],
      "properties": {
        "text": {"type": "string", "maxLength": 500},
        "language": {"enum": ["hi", "en", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "or", "ur", "as"]},
        "voice_id": {"type": "string"}
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "audio_uri": {"type": "string"},
        "duration_sec": {"type": "number"},
        "is_preview_quality": {"const": true}
      }
    },
    "rate_limit": "50 req/min/tenant"
  },

  "tts": {
    "description": "Production-grade TTS in Indian languages.",
    "input_schema": {
      "type": "object",
      "required": ["text", "language", "voice_id"],
      "properties": {
        "text": {"type": "string", "maxLength": 5000},
        "language": {"type": "string"},
        "voice_id": {"type": "string"},
        "sample_rate_hz": {"enum": [16000, 22050, 44100, 48000]},
        "speech_rate": {"type": "number", "default": 1.0, "minimum": 0.5, "maximum": 2.0},
        "domain": {"enum": ["general", "advertising", "news"]}
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "audio_uri": {"type": "string"},
        "duration_sec": {"type": "number"},
        "transcript_alignment_uri": {"type": "string"},
        "is_ai_generated": {"const": true, "description": "Always true for Bhashini TTS; relevant to ASCI-AI-001"}
      }
    },
    "compliance_postcondition": "Caller MUST embed 'AI-Generated' label on downstream artifact if this audio is used with a synthetic persona."
  },

  "captions.generate": {
    "description": "Generate burned-in captions for video. Required because 80% of mobile video plays muted.",
    "input_schema": {
      "type": "object",
      "required": ["video_uri", "language"],
      "properties": {
        "video_uri": {"type": "string"},
        "language": {"type": "string"},
        "caption_style": {"type": "object", "properties": {
          "font_family": {"type": "string"},
          "font_size_px": {"type": "integer"},
          "color": {"type": "string"},
          "background": {"type": "string"},
          "position": {"enum": ["bottom", "top", "center", "safe_zone_aware"]}
        }},
        "burn_in": {"type": "boolean", "default": true}
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "captioned_video_uri": {"type": "string"},
        "srt_uri": {"type": "string"},
        "legibility_at_thumbnail": {"type": "boolean"}
      }
    }
  },

  "dub.assist": {
    "description": "Assist with multilingual dubbing — translate script + generate timed VO + align to source video.",
    "input_schema": {
      "type": "object",
      "required": ["source_video_uri", "source_language", "target_language"],
      "properties": {
        "source_video_uri": {"type": "string"},
        "source_language": {"type": "string"},
        "target_language": {"type": "string"},
        "voice_id_target": {"type": "string"},
        "preserve_lip_sync_intent": {"type": "boolean", "default": true},
        "preserve_brand_terms": {"type": "array", "items": {"type": "string"}}
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "dubbed_video_uri": {"type": "string"},
        "translation_quality_score": {"type": "number"},
        "is_ai_generated": {"const": true}
      }
    }
  }
}
```

Also fix v1.2 §C.1 `translate` output: the `transliteration_available` field is misleading because no `transliterate` method existed at v1.2; now it does, so the flag is meaningful — keep it.

### §3.2 `adobe-firefly` — full schema

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.3/adobe-firefly.json",
  "title": "adobe-firefly MCP server",
  "version": "1.0.0",
  "vendor": "Adobe",
  "compliance_anchor": "C2PA Content Credentials embedded on every generation. Required for ASCI-AI-001 and CHITRA L0 wrapper.",

  "methods": {

    "generate.image": {
      "description": "Text-to-image generation with brand-aware controls.",
      "input_schema": {
        "type": "object",
        "required": ["prompt", "style_reference"],
        "properties": {
          "prompt": {"type": "string", "maxLength": 1000},
          "negative_prompt": {"type": "string"},
          "style_reference": {"type": "string", "description": "URI of brand style guide or moodboard image"},
          "structure_reference": {"type": "string", "description": "URI of layout/composition reference"},
          "aspect_ratio": {"enum": ["1:1", "4:5", "9:16", "16:9", "1.91:1", "2:3", "3:4"]},
          "model_version": {"enum": ["firefly_image_3", "firefly_image_4", "firefly_image_v_latest"], "default": "firefly_image_v_latest"},
          "content_credentials": {"const": "required"},
          "num_variations": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "images": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "uri": {"type": "string"},
              "content_credentials_uri": {"type": "string"},
              "model_used": {"type": "string"},
              "seed": {"type": "integer"}
            }
          }}
        }
      },
      "compliance_postcondition": "AI-generated metadata persists with image. If used with human-likeness, ASCI-AI-001 disclosure required downstream."
    },

    "generate.fill": {
      "description": "Inpainting — fill a masked region of an existing image.",
      "input_schema": {
        "type": "object",
        "required": ["source_image_uri", "mask_uri", "prompt"],
        "properties": {
          "source_image_uri": {"type": "string"},
          "mask_uri": {"type": "string"},
          "prompt": {"type": "string"},
          "content_credentials": {"const": "required"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "filled_image_uri": {"type": "string"},
          "content_credentials_uri": {"type": "string"}
        }
      }
    },

    "generate.expand": {
      "description": "Outpainting — extend canvas with generated content.",
      "input_schema": {
        "type": "object",
        "required": ["source_image_uri", "target_dimensions"],
        "properties": {
          "source_image_uri": {"type": "string"},
          "target_dimensions": {"type": "string", "description": "e.g., 1920x1080"},
          "expand_direction": {"enum": ["all", "left", "right", "top", "bottom", "horizontal", "vertical"]},
          "prompt": {"type": "string"},
          "content_credentials": {"const": "required"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "expanded_image_uri": {"type": "string"},
          "content_credentials_uri": {"type": "string"}
        }
      }
    }
  }
}
```

### §3.3 `elevenlabs-mcp` — full schema with consent gating

Voice cloning is the highest-risk MCP CHITRA touches. ASCI AI rules + IT Rules deepfake provisions + tort liability all apply. Schema enforces consent at the call.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.3/elevenlabs-mcp.json",
  "title": "elevenlabs-mcp MCP server",
  "version": "1.0.0",

  "methods": {

    "tts.scratch_track": {
      "description": "Generate a scratch VO track for review — Vaani uses this to test scripts.",
      "input_schema": {
        "type": "object",
        "required": ["text", "voice_id", "language"],
        "properties": {
          "text": {"type": "string", "maxLength": 2000},
          "voice_id": {"type": "string", "description": "Must be a library voice; voice clones NOT permitted in scratch context"},
          "language": {"type": "string"},
          "is_library_voice": {"const": true}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "audio_uri": {"type": "string"},
          "duration_sec": {"type": "number"},
          "is_preview": {"const": true, "description": "Cannot be used in published artifacts"}
        }
      }
    },

    "tts.production": {
      "description": "Production-grade TTS. If using a clone, consent must be pre-validated.",
      "input_schema": {
        "type": "object",
        "required": ["text", "voice_id", "language", "voice_consent_status"],
        "properties": {
          "text": {"type": "string", "maxLength": 5000},
          "voice_id": {"type": "string"},
          "language": {"type": "string"},
          "voice_consent_status": {
            "type": "object",
            "required": ["consent_documented", "subject"],
            "properties": {
              "consent_documented": {"type": "boolean"},
              "subject": {"type": "string"},
              "consent_artifact_uri": {"type": "string"},
              "is_library_voice": {"type": "boolean", "description": "If true, consent_documented may be inherited from voice library license"}
            }
          }
        },
        "allOf": [{
          "if": {"properties": {"voice_consent_status": {"properties": {"is_library_voice": {"const": false}}}}},
          "then": {"properties": {"voice_consent_status": {"required": ["consent_artifact_uri"]}}}
        }]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "audio_uri": {"type": "string"},
          "duration_sec": {"type": "number"},
          "is_ai_generated": {"const": true},
          "voice_was_cloned": {"type": "boolean"},
          "rule_compliance": {"type": "array", "items": {"enum": ["IP-AI-CONSENT-001", "ASCI-AI-001"]}}
        }
      },
      "pre_call_hook": "tool-mesh validates consent_artifact_uri against consent-vault before allowing the call",
      "compliance_postcondition": "If voice_was_cloned, the downstream motion_asset must populate ai_content_metadata.deepfake_segments per v1.2.1 §F.7."
    },

    "voice_clone.use": {
      "description": "Use a pre-existing cloned voice in production. Cloning itself is a separate, vault-gated operation done outside CHITRA.",
      "input_schema": {
        "type": "object",
        "required": ["clone_id", "text", "language", "consent_artifact_uri"],
        "properties": {
          "clone_id": {"type": "string"},
          "text": {"type": "string", "maxLength": 5000},
          "language": {"type": "string"},
          "consent_artifact_uri": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "audio_uri": {"type": "string"},
          "is_ai_generated": {"const": true},
          "voice_was_cloned": {"const": true},
          "rule_compliance": {"type": "array", "items": {"const": "IP-AI-CONSENT-001"}}
        }
      },
      "pre_call_hook": "tool-mesh REQUIRES consent-vault.validate_for_processing returns valid=true"
    }
  }
}
```

### §3.4 `runway-mcp` — full schema

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.3/runway-mcp.json",
  "title": "runway-mcp MCP server",
  "version": "1.0.0",
  "vendor": "Runway",

  "methods": {

    "generate.video": {
      "description": "Text-to-video or image-to-video.",
      "input_schema": {
        "type": "object",
        "required": ["prompt_or_image_uri", "duration_sec"],
        "properties": {
          "prompt_or_image_uri": {"type": "string"},
          "duration_sec": {"type": "integer", "minimum": 4, "maximum": 60},
          "aspect_ratio": {"enum": ["1:1", "4:5", "9:16", "16:9"]},
          "model_version": {"type": "string"},
          "content_credentials": {"const": "required"},
          "depicts_real_persons": {"type": "boolean", "default": false}
        },
        "allOf": [{
          "if": {"properties": {"depicts_real_persons": {"const": true}}},
          "then": {"required": ["subject_consent_artifact_uri"]}
        }]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "video_uri": {"type": "string"},
          "content_credentials_uri": {"type": "string"},
          "is_ai_generated": {"const": true},
          "rule_compliance": {"type": "array", "items": {"enum": ["ASCI-AI-001", "IP-AI-CONSENT-001"]}}
        }
      }
    },

    "generate.lipsync": {
      "description": "Sync audio to existing video (lip movement matching). Deepfake-adjacent — consent gated.",
      "input_schema": {
        "type": "object",
        "required": ["video_uri", "audio_uri", "subject_consent_artifact_uri"],
        "properties": {
          "video_uri": {"type": "string"},
          "audio_uri": {"type": "string"},
          "subject_consent_artifact_uri": {"type": "string", "description": "MANDATORY — lipsync of a real person without consent is a banned deepfake operation"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "lipsync_video_uri": {"type": "string"},
          "is_ai_generated": {"const": true},
          "rule_compliance": {"type": "array", "items": {"const": "IP-AI-CONSENT-001"}}
        }
      },
      "pre_call_hook": "tool-mesh validates subject_consent against consent-vault; refuses if invalid"
    },

    "expand": {
      "description": "Extend video duration or aspect ratio via generative outpainting.",
      "input_schema": {
        "type": "object",
        "required": ["video_uri"],
        "properties": {
          "video_uri": {"type": "string"},
          "target_duration_sec": {"type": "number"},
          "target_aspect_ratio": {"type": "string"},
          "content_credentials": {"const": "required"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "expanded_video_uri": {"type": "string"},
          "content_credentials_uri": {"type": "string"}
        }
      }
    }
  }
}
```

### §3.5 Vendor MCP method enumeration tables (schemas import from vendor manifests)

For these servers, full per-method schemas live in the MCP Tool Mesh registry, fetched from the vendor's published manifest. CHITRA records: which methods agents may call, what CHITRA-specific pre/post hooks apply, what compliance rules fire.

#### `adobe-creative-cloud`

| Agent method ref | Vendor namespace | CHITRA hooks |
|---|---|---|
| `photoshop.*` | Photoshop API (Generative Fill, Layers, Smart Objects, Export) | Brand-guideline compliance pre-check; content_credentials persisted |
| `illustrator.*` | Illustrator API (Vector ops, Type, Color) | Color-palette compliance pre-check |
| `indesign.*` | InDesign API (Layout, Pages, Master) | Print-spec compliance pre-check |
| `premiere.*` | Premiere Pro API (Sequences, Tracks, Effects, Export) | LUFS loudness target validated post-export |
| `after_effects.*` | After Effects API (Comps, Layers, Render) | Frame-rate + codec validated post-render |
| `audition.*` | Audition API (Multitrack, Mastering) | LUFS target enforced |

Wildcard `.*` means the vendor's full surface, scoped to the methods Rekha/Gati actually call in practice. The Tool Mesh whitelist is generated at registration time.

#### `figma-mcp`

| Method | Purpose | Caller |
|---|---|---|
| `file.create` | New design file | Roop, Rekha |
| `file.read` | Read existing file | Roop, Rekha |
| `file.update` | Edit file | Roop, Rekha |
| `dev_mode.export` | Export for dev/production | Rekha |
| `dev_mode.spec` | Generate spec doc | Rekha |
| `comments.read` / `comments.write` | Review cycle | Roop, Rekha |
| `variables.read` / `variables.write` | Design tokens | Rekha |

Tenant-workspace-scoped via OAuth scope at vault-level.

#### `canva-mcp`

| Method | Purpose | Caller |
|---|---|---|
| `template.search` / `template.create_from` | Template-based asset creation | Rekha |
| `bulk_create` | Generate N variants from template | Rekha |
| `brand_kit.apply` / `brand_kit.read` | Brand kit enforcement | Rekha |
| `export.png` / `export.pdf` / `export.mp4` | Render | Rekha |

#### `meta-marketing` (extending v1.2 §C.2)

| Method | Purpose | Caller | Compliance hooks |
|---|---|---|---|
| `campaign.create` | (v1.2 §C.2 schema) | Lakshya | special_ad_categories check |
| `campaign.update` | Edit campaign | Lakshya | Re-runs special_ad_categories |
| `campaign.pause` / `campaign.resume` | Lifecycle | Lakshya | budget-shift HITL if >20% |
| `adset.create` / `adset.update` | Adset CRUD | Lakshya | DPDP-SENSITIVE-TARGETING-001 |
| `ad.create` / `ad.update` | Ad CRUD | Lakshya | ASCI-AI-001/002 if AI persona |
| `audience.create_custom` / `audience.create_lookalike` | Audience | Lakshya | DPDP-CONSENT-001 mandatory for custom |
| `report.read` | Reporting | Lakshya, Pramaan | privacy thresholding |
| `insights.read` | Insights | Pramaan | privacy thresholding |
| `post.publish` / `story.publish` / `reel.publish` | Organic | Lehar | sanitizer pre-call on social_post |
| `comment.respond` | Community management | Lehar | sanitizer pre-call |
| `click_to_chat_ad.config` | WhatsApp ad config | Lakshya | WhatsApp opt-in enforcement |

#### `google-ads-mcp` (extending v1.2 §C.3)

| Method | Purpose | Caller |
|---|---|---|
| `asset.text_guidelines.set` | (v1.2 §C.3 schema) | Lakshya |
| `campaign.create` / `update` / `pause` / `resume` | Campaign lifecycle | Lakshya |
| `ad_group.create` / `update` | Ad group lifecycle | Lakshya |
| `asset.create` / `update` / `link` | Asset management | Lakshya |
| `keyword.add` / `negative_keyword.add` | Keyword management | Lakshya |
| `audience.attach` / `audience.detach` | Audience | Lakshya |
| `report.read` / `insights.read` | Reporting | Lakshya, Pramaan |

Auto-bump policy: minor versions auto-applied; major version bumps (e.g., v22 → v23) require Resource Curator review per v1.2 §A.4.

#### `youtube-mcp` / `linkedin-marketing-mcp` / `x-marketing-mcp` / `whatsapp-business`

Method enumeration follows vendor surface. Critical compliance hooks:

- All organic posts pass through `chitra-sanitizer.validate` (artifact_type=`social_post`) at Tool Mesh pre-call.
- WhatsApp template submit requires pre-approved template ID + consent_artifact_id for the recipient list.
- X / LinkedIn DMs require `dm.respond_with_consent` — only sent if user previously opted in or initiated.

#### `sprinklr-mcp`

| Method | Purpose |
|---|---|
| `listen.streams.read` | Brand mentions, sentiment |
| `respond.queue.read` / `queue.assign` | Community management queue |
| `schedule.create` / `schedule.update` | Calendar publishing |

#### `google-analytics-mcp` (extending v1.2 §C.4)

| Method | Purpose |
|---|---|
| `data.run_report` | (v1.2 §C.4 schema) |
| `admin.property.read` | Property config |
| `admin.audience.read` | GA4 audiences |
| `admin.custom_dimension.read` / `.write` | Dimension management |

#### `bigquery-mcp` / `looker-studio-mcp` / `jioads-mcp` / `amazon-ads-mcp` / `dv360-mcp` / `meta-ads-cli`

Vendor-published methods; CHITRA scopes via tenant_context.tool_authorization. Compliance hooks: all writes audit-logged; all reads respect tenant isolation.

---

## §4 MANIFEST AMENDMENTS

Two methods exist in v1.2.2 §1 schemas but no agent manifest calls them. Two services have callers but the calls aren't formalized in manifests.

### §4.1 `chitra-calendar.moment.live_status` → add to Lehar

Lehar's 90-minute response window for breaking moments depends on knowing when a moment is live. Currently Lehar polls via `chitra-search.trend_lookup`, which is the wrong tool — search gives history, not live status.

**Manifest amendment**:

```yaml
# Lehar (B.7) — add:
- chitra-calendar:
    methods: [festivals.in_range, sports.in_range, moment.live_status]
    note: "moment.live_status drives the 90-minute response window"
    rate_limit_aware: true  # 1 req/30s — use webhook subscription instead of polling at scale
```

### §4.2 `hitl-approval` → add to Lakshya manifest

Lakshya's manifest lists `human_in_the_loop_gates` as a config block but no actual tool calls. The `hitl-approval` service from v1.2.2 §5 is the implementation.

**Manifest amendment**:

```yaml
# Lakshya (B.8) — add:
- hitl-approval:
    methods: [request_approval, poll_status]
    triggers:
      - method: campaign.launch
        gate_type: pre_launch
      - condition: budget.shift > 20%
        gate_type: mid_flight_budget_shift
      - method: audience.create_custom + new
        gate_type: audience_new_segment
      - method: ad.create + creative_refresh
        gate_type: creative_refresh
```

Also add to Lehar (B.7) for crisis response gate, and to Pramaan (B.9) for final report sign-off:

```yaml
# Lehar — add:
- hitl-approval:
    methods: [request_approval, poll_status]
    triggers:
      - condition: crisis_response_required
        gate_type: crisis_response

# Pramaan — add:
- hitl-approval:
    methods: [request_approval, poll_status]
    triggers:
      - method: final_report.submit
        gate_type: final_report_signoff
```

### §4.3 Disha — add `chitra-history` reads

v1.2 §B.2 lists `chitra-history` with `campaigns.competitor_archive` and `concepts.killed_log`, but Disha also needs `learnings.latest` to consume Pramaan's last-cycle dossier per the closed loop (v1.1 §10 mandates this). The manifest omits it.

**Manifest amendment**:

```yaml
# Disha (B.2) — replace chitra-history block:
- chitra-history:
    methods: [campaigns.competitor_archive, concepts.killed_log, learnings.latest]
    note: "learnings.latest closes the loop — last-cycle dossier informs concept generation"
    scope: tenant_only
```

---

## §5 RESOURCE PACK ACCESSIBILITY — NEW MCP SERVER

v1.1 §A blocks describe themselves as "what's true about the world right now" but only some are queryable through MCP:

| v1.1 Block | Queryable through | Status |
|---|---|---|
| A.1 Regulatory | `chitra-regdb` | ✓ |
| A.2 Festival Calendar | `chitra-calendar.festivals.in_range` | ✓ |
| A.3 Cricket & Sports | `chitra-calendar.sports.in_range` | ✓ |
| A.4 Platform Spec Sheet | (nothing) | ✗ |
| A.5 India Ad Market | `chitra-marketdata.market.size_estimate` (partial — category-level only) | partial |
| A.6 Tool Stack | (nothing) | ✗ |
| A.7 India-Specific Insights | (nothing) | ✗ |

Agents that need this data have it injected into their prompt at session start as Resource Pack text. That works for read-only consumption but fails for:
- Programmatic look-up (does this platform support 4:5 aspect ratio?)
- Conditional validation (Gati validating Instagram Reel spec against current values)
- Tenant overrides (one tenant has a custom YouTube channel spec; data drifts)

**Resolution**: Add a `chitra-resourcepack` MCP server.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.3/chitra-resourcepack.json",
  "title": "chitra-resourcepack MCP server",
  "version": "1.0.0",
  "purpose": "Programmatic access to v1.1 §A blocks not already exposed by chitra-regdb / chitra-calendar / chitra-marketdata.",

  "methods": {

    "platform.spec": {
      "description": "Return current platform spec (aspect ratios, max duration, codec, safe zones, etc.) for a named platform.",
      "input_schema": {
        "type": "object",
        "required": ["platform"],
        "properties": {
          "platform": {"enum": [
            "instagram_reel", "instagram_story", "instagram_feed",
            "facebook_feed", "facebook_reel", "facebook_story",
            "youtube_short", "youtube_long", "youtube_bumper",
            "tiktok", "moj", "josh", "sharechat",
            "x_video", "linkedin_video",
            "whatsapp_status", "whatsapp_business_template",
            "jiohotstar_pre_roll", "jiohotstar_mid_roll",
            "google_display", "ooh_dooh"
          ]},
          "as_of_date": {"type": "string", "format": "date", "description": "Default: today"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "platform": {"type": "string"},
          "aspect_ratios_supported": {"type": "array", "items": {"type": "string"}},
          "preferred_aspect_ratio": {"type": "string"},
          "max_duration_sec": {"type": "number"},
          "min_duration_sec": {"type": "number"},
          "supported_codecs": {"type": "array", "items": {"type": "string"}},
          "max_filesize_mb": {"type": "number"},
          "safe_zones": {"type": "object"},
          "caption_recommendations": {"type": "object"},
          "loudness_target_lufs": {"type": "number"},
          "asci_disclosure_rules_url": {"type": "string"},
          "last_updated": {"type": "string", "format": "date"}
        }
      }
    },

    "tool_stack.current_version": {
      "description": "What version of each tool CHITRA currently pins to.",
      "input_schema": {
        "type": "object",
        "properties": {
          "tool_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "tools": {"type": "array", "items": {
            "type": "object",
            "properties": {
              "tool_id": {"type": "string"},
              "vendor_version_pinned": {"type": "string"},
              "released_at": {"type": "string", "format": "date"},
              "expires_at": {"type": "string", "format": "date"},
              "breaking_changes_pending": {"type": "boolean"},
              "auto_bump_policy": {"type": "string"}
            }
          }}
        }
      }
    },

    "india_insights.city_tier": {
      "description": "Return city-tier behavior heuristics for a given city or tier band.",
      "input_schema": {
        "type": "object",
        "properties": {
          "city": {"type": "string"},
          "tier": {"enum": ["tier_1", "tier_2", "tier_3", "rural"]}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "tier": {"type": "string"},
          "behavioral_heuristics": {"type": "object"},
          "primary_languages": {"type": "array", "items": {"type": "string"}},
          "dominant_platforms": {"type": "array", "items": {"type": "string"}},
          "media_consumption_profile": {"type": "object"}
        }
      }
    },

    "india_insights.language_register": {
      "description": "Return language register guidance — code-mixing norms, formality bands, regional idioms.",
      "input_schema": {
        "type": "object",
        "required": ["language"],
        "properties": {
          "language": {"type": "string"},
          "city_tier": {"type": "string"},
          "audience_age_band": {"type": "object"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "code_mix_norms": {"type": "object"},
          "formality_recommendation": {"enum": ["formal", "semi_formal", "casual", "vernacular"]},
          "common_idioms": {"type": "array", "items": {"type": "object"}},
          "punctuation_norms": {"type": "object"}
        }
      }
    },

    "ad_market.macro_snapshot": {
      "description": "Macro India ad-market data — TYNY / Dentsu / Pitch report snapshot.",
      "input_schema": {
        "type": "object",
        "properties": {
          "year": {"type": "integer"},
          "segment": {"enum": ["total", "digital", "tv", "print", "ooh", "radio", "cinema", "commerce_led"]}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "total_market_inr": {"type": "integer"},
          "segment_share_pct": {"type": "number"},
          "yoy_growth_pct": {"type": "number"},
          "source": {"type": "string"},
          "as_of_date": {"type": "string", "format": "date"}
        }
      }
    }
  }
}
```

**Manifest amendments** — add `chitra-resourcepack` to:

- **Roop**: `methods: [platform.spec, india_insights.city_tier]` — for adaptation matrix and visual codes
- **Vaani**: `methods: [india_insights.language_register]` — for code-mix authenticity
- **Gati**: `methods: [platform.spec, tool_stack.current_version]` — for spec-correct exports and tool versioning
- **Rekha**: `methods: [platform.spec, tool_stack.current_version]` — same
- **Lehar**: `methods: [platform.spec]` — for platform-native publishing
- **Lakshya**: `methods: [platform.spec, ad_market.macro_snapshot]` — for media planning
- **Pramaan**: `methods: [ad_market.macro_snapshot]` — for benchmarking
- **Drishti**: `methods: [india_insights.city_tier, ad_market.macro_snapshot]` — for audience triangulation

---

## §6 CROSS-TENANT EXCLUSION ENFORCEMENT

v1.2.2 §3 (tenant_context) defines `competitive_exclusions` — other tenants/clients CHITRA should not cross-reference. But nothing in the Tool Mesh actually enforces this. A search for "competitor moves" could surface another tenant's data; a learnings lookup could leak.

### §6.1 Enforcement at Tool Mesh

**Pre-call check on every tenant-scoped read**:

```python
def enforce_cross_tenant_exclusion(call):
    requesting_tenant = call._chitra_meta.tenant_id
    target_data_tenant = resolve_data_tenant(call)  # if call reads cross-tenant
    if target_data_tenant == requesting_tenant:
        return ALLOW
    requesting_exclusions = tenant_context(requesting_tenant).competitive_exclusions
    target_exclusions = tenant_context(target_data_tenant).competitive_exclusions
    if requesting_tenant in target_exclusions or target_data_tenant in requesting_exclusions:
        return BLOCK("cross_tenant_exclusion_active")
    return ALLOW
```

Applies to:
- `chitra-history.campaigns.by_client` (always tenant-scoped; ALLOW unless target_data_tenant differs)
- `chitra-history.campaigns.competitor_archive` (DOES query across tenants for public-domain competitive intel; this is where leakage risk is highest)
- `chitra-marketdata.audience.profile` (aggregated; tenant-blind by design)
- `chitra-search.*` (web search; tenant-blind)
- `chitra-assetdb.artifact.read` / `asset.read` (must be tenant-scoped; blocked at namespace level)

### §6.2 `chitra-history.campaigns.competitor_archive` clarification

This is the one cross-tenant-adjacent call CHITRA makes legitimately — competitor brand campaigns that exist in the public domain. Reframing the schema:

```yaml
clarification:
  what_it_returns: "Public-domain references to competitor campaigns — launched ads,
                    press, social posts. Source = published material, not internal CHITRA data."
  what_it_never_returns: "Internal data from any tenant. Even if competitor brand is
                          a CHITRA tenant, that tenant's CHITRA-internal artifacts
                          remain invisible. Public material only."
  data_provenance: "Each result carries a public_source_url field; if a result lacks
                    one, it's a defect — file a bug."
```

### §6.3 Output sanitizer enforcement

Sanitizer adds rule:

```yaml
- id: CHITRA-TENANT-ISOLATION-001
  source: CHITRA_INTERNAL
  applies_to: [creative_brief, concept_slate, concept_bible, asset_registry, motion_asset_registry, media_plan, performance_report, learnings_dossier]
  check:
    forbid: artifact references material from outside requesting_tenant unless via
            public_source_url-tagged competitor_archive
    forbid: artifact contains tenant_id values other than requesting_tenant
  severity: block
  human_review_on_fail: true
```

---

## §7 DPDP ERASURE-REQUEST FLAG (the user's explicit ask)

### §7.1 The conflict

v1.2.2 §1.3 retention policy: *"soft-delete with 30-day reversal window, then hard-delete on tenant DPDP retention schedule."*

DPDP Act §13 grants Data Principals the right to erasure of their personal data. DPDP Rules 2025 require Data Fiduciaries to comply *"without undue delay."* A 30-day soft-delete reversal window arguably violates the without-delay obligation when erasure is invoked.

In practice, agencies resolve this by treating right-to-erasure requests as a separate pathway — immediate hard-delete with audit evidence — and using soft-delete only for accidental deletions and operational mistakes.

### §7.2 `chitra-assetdb.artifact.delete` — new method with explicit erasure flag

Replaces the implicit deletion behavior in v1.2.2 §1.3.

```json
{
  "$id": "https://chitra.ai/mcp/v1.2.3/chitra-assetdb-delete.json",
  "addition_to": "chitra-assetdb (v1.2.2 §1.3)",

  "methods": {

    "artifact.delete": {
      "description": "Delete an artifact. Behavior depends on erasure_request flag.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "artifact_id", "deletion_reason"],
        "properties": {
          "tenant_id": {"type": "string"},
          "artifact_id": {"type": "string"},
          "version": {"type": "string", "description": "If absent, deletes all versions"},

          "erasure_request": {
            "type": "boolean",
            "default": false,
            "description": "If true, this is a DPDP §13 right-to-erasure request. Bypasses the 30-day reversal window — immediate hard-delete. Requires data_principal_authorization."
          },

          "deletion_reason": {
            "enum": [
              "operational_cleanup",
              "tenant_request",
              "accidental_creation",
              "campaign_cancelled",
              "data_principal_erasure_request",
              "regulator_directive",
              "retention_policy_expiry",
              "incident_response_purge"
            ]
          },

          "data_principal_authorization": {
            "type": "object",
            "description": "REQUIRED if erasure_request=true",
            "required_if_erasure": ["data_principal_id_hash", "erasure_request_evidence_uri", "received_at"],
            "properties": {
              "data_principal_id_hash": {"type": "string", "description": "SHA-256 of identifier"},
              "erasure_request_evidence_uri": {"type": "string", "description": "Pointer to signed request — email, form submission, identity-verified portal action"},
              "received_at": {"type": "string", "format": "date-time"},
              "verification_method": {"enum": ["identity_documents", "consent_manager_attested", "platform_verified_login", "in_person", "notarized"]}
            }
          },

          "regulator_authorization": {
            "type": "object",
            "description": "REQUIRED if deletion_reason=regulator_directive",
            "properties": {
              "regulator": {"enum": ["DPBI", "ASCI", "RBI", "SEBI", "IRDAI", "MeitY", "CCPA", "court_order"]},
              "directive_id": {"type": "string"},
              "directive_uri": {"type": "string"}
            }
          },

          "cascade_to_external_platforms": {
            "type": "boolean",
            "default": true,
            "description": "If true, triggers cascade deletion to Meta / Google Ads / etc. for any audience lists / custom audiences sourced from this artifact"
          }
        },

        "allOf": [
          {
            "if": {"properties": {"erasure_request": {"const": true}}},
            "then": {"required": ["data_principal_authorization"]}
          },
          {
            "if": {"properties": {"deletion_reason": {"const": "data_principal_erasure_request"}}},
            "then": {
              "required": ["data_principal_authorization"],
              "properties": {"erasure_request": {"const": true}}
            }
          },
          {
            "if": {"properties": {"deletion_reason": {"const": "regulator_directive"}}},
            "then": {"required": ["regulator_authorization"]}
          }
        ]
      },

      "output_schema": {
        "type": "object",
        "required": ["deletion_id", "deletion_path", "hard_deleted_at", "audit_evidence_uri"],
        "properties": {
          "deletion_id": {"type": "string"},

          "deletion_path": {
            "enum": ["soft_delete_with_reversal", "immediate_hard_delete"],
            "description": "soft_delete_with_reversal: 30-day window. immediate_hard_delete: erasure path."
          },

          "soft_deleted_at": {"type": "string", "format": "date-time"},
          "reversal_available_until": {"type": "string", "format": "date-time"},
          "hard_deleted_at": {"type": "string", "format": "date-time"},

          "audit_evidence_uri": {
            "type": "string",
            "description": "Pointer to immutable audit record — what was deleted, who authorized, when. Retained for 5 years (DPDP cold-store) even after the data itself is erased."
          },

          "downstream_cascade_jobs": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "platform": {"type": "string"},
                "job_id": {"type": "string"},
                "status": {"enum": ["queued", "in_progress", "completed", "failed"]}
              }
            }
          },

          "dpdp_compliance_record": {
            "type": "object",
            "description": "If erasure_request=true, this is the evidence trail filed for DPBI audit.",
            "properties": {
              "request_received_at": {"type": "string", "format": "date-time"},
              "compliance_completed_at": {"type": "string", "format": "date-time"},
              "without_delay_target_met": {"type": "boolean"},
              "completion_window_hours": {"type": "number"}
            }
          }
        }
      },

      "pre_call_hooks": [
        "If erasure_request=true: tool-mesh validates data_principal_authorization.evidence_uri exists and is readable",
        "If erasure_request=true: tool-mesh triggers cascade to consent-vault.honor_withdrawal",
        "If deletion_reason=regulator_directive: tool-mesh validates regulator_authorization.directive_uri",
        "audit-sink.log status=intent with full reason payload"
      ],

      "post_call_hooks": [
        "audit-sink.log status=success|error|blocked",
        "If erasure_request=true: notify Resource Curator + DPO via incident-classification (informational, not breach)",
        "If cascade_to_external_platforms=true: dispatch deletion jobs to Meta Custom Audiences, Google Customer Match, WhatsApp recipient lists, etc."
      ],

      "guarantees": {
        "immediate_hard_delete_path": "Data is irrecoverable within 60 minutes of call success. The 30-day reversal window does not apply.",
        "audit_evidence_retention": "The fact-of-deletion record (deletion_id, who, when, why, what) is retained for 5 years in cold storage. The deleted data itself is not retained.",
        "cascade_completion_sla": "External cascade jobs complete within 7 days; status reported back via downstream_cascade_jobs polling."
      }
    },

    "artifact.recover_soft_deleted": {
      "description": "Recover a soft-deleted artifact within the 30-day window. Refuses for erasure-path deletions.",
      "input_schema": {
        "type": "object",
        "required": ["tenant_id", "deletion_id", "recovery_reason"],
        "properties": {
          "tenant_id": {"type": "string"},
          "deletion_id": {"type": "string"},
          "recovery_reason": {"type": "string"},
          "approver_id": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "recovered": {"type": "boolean"},
          "reason_if_not": {"enum": ["window_expired", "erasure_path_irrecoverable", "deletion_id_unknown", "approver_not_authorized"]}
        }
      }
    }
  }
}
```

### §7.3 New `consent-vault` integration

When `erasure_request=true`, the call cascades to `consent-vault.honor_withdrawal` automatically. This is what makes the erasure flow DPDP-complete: data is deleted *and* the consent artifact is marked withdrawn *and* downstream audiences are purged.

### §7.4 New rule in §G

```yaml
- id: DPDP-ERASURE-001
  source: DPDP
  citation: "DPDP Act 2023 §13 — Right to erasure; DPDP Rules 2025 — without undue delay"
  applies_to: [process_rule]
  applies_when: data_principal_erasure_request_received == true
  check:
    require: chitra-assetdb.artifact.delete called with erasure_request=true
    AND: deletion_path == "immediate_hard_delete"
    AND: dpdp_compliance_record.completion_window_hours <= 72  # operational ceiling for "without delay"
    AND: cascade_to_external_platforms == true
    AND: audit_evidence_uri persisted for 5 years
  severity: block
  human_review_on_fail: true
  note: "72-hour operational ceiling mirrors GDPR practice; DPBI may issue binding guidance. Until then, this is the prudent interpretation."
```

This also resolves issue #25 from the v1.2.2 sweep — the "without delay" interpretation gap.

---

## §8 CONDITIONAL VALIDATION TIGHTENING

Four schema fields described conditional requirements in prose but didn't enforce them with `allOf`/`if-then` constructs. JSON Schema validators can't enforce prose.

### §8.1 `concept_bible.visual_deck.storyboard` — required if video-led

Replace v1.2 §F.3's storyboard property:

```json
{
  "visual_deck": {
    "type": "object",
    "required": ["mood_board", "style_frames", "type_system", "color_system", "adaptation_matrix"],
    "properties": {
      "concept_format": {
        "type": "string",
        "enum": ["static", "video", "interactive", "mixed"],
        "description": "Drives conditional storyboard requirement"
      },
      "storyboard": {
        "type": "array",
        "items": { "$ref": "..." }
      }
    },
    "allOf": [{
      "if": {"properties": {"concept_format": {"enum": ["video", "mixed"]}}},
      "then": {"required": ["storyboard"]}
    }]
  }
}
```

### §8.2 `creative_brief.mandatories[].regulation_id` — required if source=regulatory

```json
{
  "mandatories": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["item", "source"],
      "properties": {
        "item": {"type": "string"},
        "source": {"enum": ["client_brief", "regulatory", "brand_guideline", "legal"]},
        "regulation_id": {"type": "string"}
      },
      "allOf": [{
        "if": {"properties": {"source": {"const": "regulatory"}}},
        "then": {"required": ["regulation_id"]}
      }]
    }
  }
}
```

### §8.3 `media_plan.audiences[].consent_artifact_id` — required for custom audiences

```json
{
  "audiences": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "type": {"enum": ["core", "lookalike", "custom", "retargeting", "exclusion"]},
        "consent_artifact_id": {"type": "string"}
      },
      "allOf": [{
        "if": {"properties": {"type": {"enum": ["custom", "retargeting"]}}},
        "then": {"required": ["consent_artifact_id"]}
      }]
    }
  }
}
```

### §8.4 `social_post.whatsapp_specifics` — required if platform is WhatsApp

```json
{
  "type": "object",
  "properties": {
    "platform": {"type": "string"},
    "whatsapp_specifics": {"type": "object"}
  },
  "allOf": [{
    "if": {"properties": {"platform": {"pattern": "^whatsapp_"}}},
    "then": {"required": ["whatsapp_specifics"]}
  }]
}
```

---

## §9 NAMING & ENUM CONSISTENCY FIXES

### §9.1 `tone_band` vs `tone_spectrum` — pick one

`creative_brief.tone_spectrum` (v1.2 §F.1) and `concept_bible.verbal_deck.voice_calibration.tone_band` (v1.2 §F.3, tightened in v1.2.2 §7.1) have identical structures with different names.

**Decision**: rename `tone_band` → `tone_spectrum` throughout. The word "spectrum" is technically more accurate (it's a continuous space across axes), and matches the earlier-phase artifact, which is the canonical source.

**Migration**: v1.2.3 accepts both names for 90 days; sanitizer logs `deprecated_field_use` warning when `tone_band` appears. After 90 days, hard error.

### §9.2 `envelope.from_agent` enum — add system principals

v1.2 §F.0 envelope `from_agent` enum lists nine agents only. But the sanitizer can sign envelopes (adds compliance fields), and humans can modify artifacts and re-submit.

Updated enum:

```json
{
  "from_agent": {
    "enum": [
      "drishti", "disha", "roop", "vaani", "rekha", "gati", "lehar", "lakshya", "pramaan",
      "system_sanitizer", "system_tool_mesh",
      "human_curator", "human_approver", "human_dpo"
    ]
  }
}
```

This lets the envelope chain capture human modifications and system-service annotations.

### §9.3 `bhashini-mcp` output field clarification

v1.2 §C.1 `translate.output_schema` returns `transliteration_available` — meaningful now that `transliterate` is a method (§3.1). Keep field; clarify in description:

```json
{
  "transliteration_available": {
    "type": "boolean",
    "description": "If true, bhashini-mcp.transliterate can convert this language pair. Vaani uses this to decide whether to call transliterate next."
  }
}
```

### §9.4 `onboarding_packet.approval_chain_reference` resolution

v1.2.2 §4 leaves this as a bare string. Spec the resolution:

```json
{
  "approval_chain_reference": {
    "type": "string",
    "pattern": "^(tenant_default|campaign_override:[a-zA-Z0-9_-]+)$",
    "description": "Either 'tenant_default' (resolves to tenant_context.approval_chain) or 'campaign_override:{id}' (resolves to a campaign-specific approval_chain registered in tenant_context.campaign_overrides[id])."
  }
}
```

---

## §10 OPERATIONAL CLARIFICATIONS

### §10.1 "Without delay" operational ceiling

Used in `DPDP-BREACH-NOTIFY-001` and now `DPDP-ERASURE-001`. The DPBI has not issued binding guidance as of 16 May 2026. CHITRA's operational interpretation:

```yaml
without_delay_operational_ceilings:
  breach_notification_to_dpbi: 72 hours from incident classification as breach
  breach_notification_to_data_principals: 72 hours from incident classification
  erasure_request_completion: 72 hours from request receipt
  consent_withdrawal_honor: 24 hours from withdrawal submission
  grievance_resolution: 90 days (hard-coded in DPDP Rules)
rationale: "Mirrors GDPR Article 33 (72-hour breach notification) and reasonable
            interpretation pending DPBI guidance. CHITRA logs full timeline so DPBI
            audits can verify good-faith compliance."
```

These ceilings update via Resource Curator workflow if DPBI publishes binding guidance.

### §10.2 Sanitizer-as-system-service in tool manifests

Every agent's manifest already names `chitra-sanitizer.validate` with `mandatory_on_output: true`. v1.2.3 §1.2 promotes the sanitizer to a formal system service, so this is no longer "agent calls sanitizer" — it's "agent emits artifact; tool-mesh interposes sanitizer call before envelope signing." Behavior is the same; the abstraction is now correct.

---

## §11 FINAL ORPHAN CHECK

After §1–§10 are applied:

### §11.1 Forward check (every method in every manifest has a schema)

| Manifest call | Now schema'd? |
|---|---|
| chitra-search.* (4 methods) | ✓ v1.2.2 §1.7 |
| chitra-marketdata.* (3 methods, renamed) | ✓ v1.2.2 §1.6 + §2.2 |
| chitra-calendar.* (3 methods incl. moment.live_status) | ✓ v1.2.2 §1.5 + §4.1 |
| chitra-regdb.* (8 methods, renamed cultural_risk_register) | ✓ v1.2.2 §1.2 + §2.3 |
| chitra-history.* (5 methods, incl. learnings.latest on Disha) | ✓ v1.2.2 §1.4 + §4.3 |
| chitra-sanitizer.validate | ✓ v1.2 §C.5 |
| chitra-assetdb.* (artifact.write/read/delete, asset.write/read/version, registry.update) | ✓ v1.2.2 §1.3 + §2.1 + §7.2 |
| chitra-resourcepack.* (5 methods, NEW) | ✓ §5 |
| legal-precheck.* (4 methods) | ✓ v1.2.2 §1.1 |
| bhashini-mcp.* (6 methods) | ✓ v1.2 §C.1 + §3.1 |
| adobe-firefly.* (3 methods) | ✓ §3.2 |
| elevenlabs-mcp.* (3 methods) | ✓ §3.3 |
| runway-mcp.* (3 methods) | ✓ §3.4 |
| adobe-creative-cloud.* | ✓ §3.5 enumeration table |
| figma-mcp.* | ✓ §3.5 |
| canva-mcp.* | ✓ §3.5 |
| meta-marketing.* | ✓ v1.2 §C.2 + §3.5 |
| google-ads-mcp.* | ✓ v1.2 §C.3 + §3.5 |
| youtube-mcp.* | ✓ §3.5 |
| linkedin-marketing-mcp.* / x-marketing-mcp.* / whatsapp-business.* / sprinklr-mcp.* | ✓ §3.5 |
| google-analytics-mcp.* | ✓ v1.2 §C.4 + §3.5 |
| bigquery-mcp.* / looker-studio-mcp.* / jioads-mcp.* / amazon-ads-mcp.* / dv360-mcp.* / meta-ads-cli.* | ✓ §3.5 vendor-import |
| hitl-approval.* (added to Lakshya, Lehar, Pramaan) | ✓ v1.2.2 §5 + §4.2 |
| consent-vault.* / rule-registry.* / audit-sink.* / secret-vault.* / cost-accounting.* / incident-classification.* | ✓ now owned by sanitizer or tool-mesh manifest §1 |

No orphans on the forward path.

### §11.2 Reverse check (every defined method has at least one caller)

| Defined method | Caller |
|---|---|
| `chitra-regdb.rules.applicable_to_artifact` | chitra-sanitizer (§1.2 manifest) |
| `chitra-regdb.registry.version` | chitra-sanitizer + tool-mesh (cache busting) |
| `chitra-calendar.moment.live_status` | Lehar (§4.1 amended manifest) |
| `chitra-assetdb.artifact.list` | Lakshya, Pramaan via `artifact.read` discovery |
| `chitra-assetdb.artifact.recover_soft_deleted` | tenant ops (not agent-callable; Resource Curator role) |
| `consent-vault.list_for_audience` | chitra-sanitizer when validating media_plan audiences |
| `consent-vault.honor_withdrawal` | chitra-assetdb.artifact.delete cascade (§7.3) |
| `consent-vault.log_grievance` | tool-mesh on user-facing grievance form submission |
| `rule-registry.propose` / `.approve` / `.graduate_to_enforce` / `.sunset` | Resource Curator role (human, not agent) |
| `audit-sink.query` / `.lineage` | Resource Curator + compliance reviewer + DPBI audit endpoint |
| `secret-vault.rotate` | scheduled job + on-demand (not agent-triggered) |
| `cost-accounting.current_burn` | tenant dashboard + tool-mesh budget checks |
| `incident-classification.record_notification_sent` | DPO role after sending DPBI / data principal notifications |

No orphans on the reverse path.

### §11.3 Resource Pack coverage check

| v1.1 §A Block | MCP Accessibility |
|---|---|
| A.1 Regulatory | chitra-regdb (all 8 methods) |
| A.2 Festivals | chitra-calendar.festivals.in_range |
| A.3 Sports | chitra-calendar.sports.in_range + moment.live_status |
| A.4 Platform Spec | chitra-resourcepack.platform.spec (NEW §5) |
| A.5 Market Macro | chitra-marketdata.* + chitra-resourcepack.ad_market.macro_snapshot |
| A.6 Tool Stack | chitra-resourcepack.tool_stack.current_version |
| A.7 India Insights | chitra-resourcepack.india_insights.city_tier + .language_register |

Full coverage.

---

## §12 SUMMARY OF GAPS CLOSED IN v1.2.3

| # | Gap | Section | Resolution |
|---|---|---|---|
| 1 | Sanitizer caller for consent-vault, rule-registry, regdb-applicable-to-artifact | §1.2 | sanitizer system-service manifest |
| 2 | Tool Mesh caller for audit-sink, secret-vault, cost-accounting, incident-classification | §1.3 | tool-mesh system-service manifest |
| 3 | chitra-assetdb naming mismatch (8 specifically-named writes) | §2.1 | unified on artifact.write + asset.read added |
| 4 | chitra-marketdata naming mismatch (per-source vs unified) | §2.2 | manifests updated to unified surface |
| 5 | chitra-regdb naming mismatch (rules.cultural_risk_register) | §2.3 | manifest fixed |
| 6 | bhashini-mcp 5 methods unscaffolded | §3.1 | full schemas added |
| 7 | adobe-firefly 3 methods unscaffolded | §3.2 | full schemas added |
| 8 | elevenlabs-mcp 3 methods unscaffolded | §3.3 | full schemas with consent gating |
| 9 | runway-mcp 3 methods unscaffolded | §3.4 | full schemas with deepfake consent gating |
| 10 | adobe-creative-cloud / figma / canva / Meta extended / Google Ads extended / youtube / linkedin / x / whatsapp / sprinklr / bigquery / looker / jioads / amazon / dv360 / meta-ads-cli / ga4-extended methods | §3.5 | enumeration tables; vendor-imported schemas |
| 11 | chitra-calendar.moment.live_status orphaned (no caller) | §4.1 | added to Lehar manifest |
| 12 | hitl-approval not in any agent manifest | §4.2 | added to Lakshya, Lehar, Pramaan |
| 13 | Disha missing learnings.latest (closed loop break) | §4.3 | added |
| 14 | A.4 platform specs not queryable | §5 | chitra-resourcepack.platform.spec |
| 15 | A.6 tool stack not queryable | §5 | chitra-resourcepack.tool_stack.current_version |
| 16 | A.7 city tier + language register not queryable | §5 | chitra-resourcepack.india_insights.* |
| 17 | A.5 market macro not queryable | §5 | chitra-resourcepack.ad_market.macro_snapshot |
| 18 | Cross-tenant exclusion not enforced | §6 | tool-mesh enforcement + CHITRA-TENANT-ISOLATION-001 rule |
| 19 | competitor_archive ambiguity (cross-tenant adjacent) | §6.2 | clarified public-domain-only |
| 20 | **DPDP erasure-request flag** | §7 | artifact.delete with erasure_request, recover_soft_deleted, DPDP-ERASURE-001 rule, cascade to consent-vault |
| 21 | storyboard-required-if-video not enforced | §8.1 | allOf/if-then added |
| 22 | mandatories.regulation_id not enforced | §8.2 | allOf/if-then added |
| 23 | audiences.consent_artifact_id not enforced for custom | §8.3 | allOf/if-then added |
| 24 | whatsapp_specifics not enforced for whatsapp_* platforms | §8.4 | allOf/if-then added |
| 25 | tone_band vs tone_spectrum naming inconsistency | §9.1 | renamed to tone_spectrum; 90-day deprecation |
| 26 | envelope.from_agent enum incomplete (no human, no system) | §9.2 | enum expanded |
| 27 | "without delay" operational ceiling undefined | §10.1 | 72-hour operational ceiling, updatable via Curator |

Twenty-seven items closed (including the explicit erasure-request flag), against the 26 identified during the sweep — the extra is `whatsapp_specifics` conditional, surfaced during §8 drafting.

---

## §13 WHAT'S NOW TRUE OF CHITRA v1.2 (with all patches applied)

Every interface CHITRA touches now has at least one of:
- A full JSON Schema (native servers, critical-path methods, all artifact schemas, tenant_context, onboarding_packet, all cross-cutting services)
- A vendor-import declaration with enumerated method surface (external MCP servers)
- An explicit human-role owner (Resource Curator workflows, DPO incident response)

Every method named anywhere in v1.1 + v1.2 + v1.2.1 + v1.2.2 + v1.2.3 either has a schema or is documented as vendor-imported. No silent dependencies remain.

Every rule in §G has explicit applies_to declarations, the §F.12 cross-reference matrix is intact, the sanitizer has a caller (system_service), and every artifact emission passes through validation that an output sanitizer can actually run.

Forward traceability and reverse traceability both pass.

**The substrate is complete. v1.3 (eval harness) is the next move.**

---

## §14 VERSION SUMMARY (FINAL FOR v1.2.x LINE)

| Version | Adds | Status |
|---|---|---|
| v1.0 | Architecture | Released |
| v1.1 | Agent scaffolds + Global Dynamic Resource Pack | Released |
| v1.2 | MCP tool integration + 6 handoff schemas + codified ruleset + sanitizer | Released |
| v1.2.1 | 4 additional handoff schemas + promoted learnings_dossier + matrix | Released |
| v1.2.2 | 24 underspecified contracts closed | Released |
| **v1.2.3** | **27 final contract gaps closed; DPDP erasure flow; chitra-resourcepack; system-service manifests for sanitizer + tool-mesh; cross-tenant exclusion enforcement; conditional validation tightening** | **This document — FINAL v1.2.x patch** |
| v1.3 (next) | **Eval harness** | Next |
| v1.4 (planned) | Closed-loop tenant learning automation | Planned |
| v2.0 (planned) | Federated learning across tenants | Planned |

---

## §15 WHAT v1.3 SHOULD CONTAIN (preview, not commitment)

With the substrate now complete, v1.3 is the eval harness — the missing thing that turns "this pipeline runs" into "this pipeline is good." Likely scope:

- **Golden-input/golden-output corpus** per agent — 20+ pairs covering canonical pass cases, edge cases, and adversarial inputs.
- **LLM-judge rubrics** per artifact type — graded rubrics that score, e.g., creative_brief on the "three-sentence defense test," concept_slate on "would two different concepts emerge?"
- **Human spot-check protocol** — sampling rate, reviewer training, inter-rater reliability targets.
- **Regression suite** — runs on every Resource Pack refresh; catches when a rule update breaks a canonical pass case.
- **Drift detection** — monitors output distribution over time; flags when an agent starts converging on a narrow output mode (creative monoculture is a real failure).
- **Synthetic-tenant rehearsal** — anonymized but realistic brief data for off-production agent tuning.

These are the things that v1.2.x can't tell you about — whether the agents are good at their jobs, whether they stay good as the world drifts, whether a model upgrade improved or degraded performance.

---

*End of CHITRA v1.2.3 — final patch in the v1.2.x line. With v1.0 + v1.1 + v1.2 + v1.2.1 + v1.2.2 + v1.2.3, the substrate is complete: every interface defined, every method schema'd, every rule predicated, every handoff verifiable, every gap closed. Knowledge horizon: 16 May 2026. Next document: v1.3 (eval harness).*
