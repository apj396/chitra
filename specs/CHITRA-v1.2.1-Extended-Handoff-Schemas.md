# CHITRA v1.2.1
**Extended Handoff Schemas — patch to v1.2 §F**

> **Knowledge horizon**: 16 May 2026 (inherits from v1.2).
> **Status**: Patch release. Drop into the same schema registry as v1.2. No breaking changes to v1.2 §F.1–§F.6 except one (see §F.11 migration note).
> **Scope**: Four schemas that v1.2 referenced as "follow the same shape" but didn't ship at depth, plus `learnings_dossier` promoted to a standalone artifact, plus the rule-to-schema cross-reference matrix the sanitizer needs to run efficiently.

---

## §0 WHAT THIS PATCH ADDS

| Section | Artifact | Producer → Consumer | Status |
|---|---|---|---|
| §F.7 | `motion_asset_registry` | Gati → Lakshya + Lehar | NEW |
| §F.8 | `daily_optimization_log` | Lakshya (rolling) → Pramaan | NEW |
| §F.9 | `content_calendar` | Lehar (rolling) → Lakshya + Pramaan | NEW |
| §F.10 | `social_post` | Lehar (per post) → publishing channels | NEW |
| §F.11 | `learnings_dossier` | Pramaan → Drishti (next cycle) | PROMOTED (was embedded in `performance_report`) |
| §F.12 | Rule-to-schema cross-reference matrix | — | NEW |
| §F.13 | Example sanitizer outputs | — | NEW |
| §F.14 | Implementation notes | — | NEW |

---

## §F.7 MOTION ASSET REGISTRY SCHEMA

**Producer**: Gati. **Consumers**: Lakshya (for trafficking), Lehar (for organic adaptation). **Triggers compliance rules**: ASCI-DISC-002 (video disclosure duration), ASCI-AI-001 (AI persona timing), ASCI-AI-002 (AI + children ban), IP-AI-CONSENT-001 (deepfake consent), IP-COPYRIGHT-001 (music + likeness rights).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chitra.ai/schemas/v1.2.1/motion_asset_registry.json",
  "title": "Motion Asset Registry Artifact",
  "type": "object",
  "required": ["concept_id", "cut_list", "source_files", "audio_specs", "ai_content_metadata", "rights_clearance", "quality_audit"],
  "properties": {
    "concept_id": {"type": "string"},

    "cut_list": {
      "type": "array",
      "minItems": 1,
      "description": "Every motion deliverable. Each cut is independently sanitizable and trafficable.",
      "items": {
        "type": "object",
        "required": [
          "cut_id", "filename", "duration_sec", "aspect_ratio",
          "platform_targets", "language", "uri",
          "has_burned_captions", "safe_zone_compliance", "asci_compliance"
        ],
        "properties": {
          "cut_id": {"type": "string"},
          "filename": {
            "type": "string",
            "pattern": "^[a-z0-9]+_[a-z0-9-]+_[a-z0-9-]+_[a-z0-9-]+_[a-z]{2}_v[0-9]+\\.(mp4|mov|webm)$",
            "description": "{client}_{campaign}_{concept}_{format}_{lang}_{version}.{ext}"
          },
          "duration_sec": {"type": "number", "minimum": 0.5},
          "aspect_ratio": {"enum": ["1:1", "4:5", "9:16", "16:9", "1.91:1", "2:3", "3:4"]},
          "platform_targets": {
            "type": "array",
            "minItems": 1,
            "items": {"enum": [
              "instagram_reel", "instagram_story", "instagram_feed",
              "facebook_feed", "facebook_story", "facebook_reel",
              "youtube_short", "youtube_long", "youtube_bumper", "youtube_skippable_in_stream", "youtube_non_skippable",
              "tiktok",
              "moj", "josh", "sharechat_video",
              "x_video", "linkedin_video",
              "whatsapp_status",
              "jiohotstar_pre_roll", "jiohotstar_mid_roll", "jiohotstar_masthead",
              "ctv_generic", "ott_generic",
              "ooh_dooh", "in_store_screen"
            ]}
          },
          "language": {"type": "string"},
          "uri": {"type": "string", "format": "uri"},

          "technical_specs": {
            "type": "object",
            "properties": {
              "codec": {"type": "string", "default": "h264"},
              "bitrate_kbps": {"type": "integer"},
              "fps": {"type": "number", "enum": [24, 25, 29.97, 30, 50, 59.94, 60]},
              "color_space": {"enum": ["rec709", "rec2020", "p3_d65", "srgb"], "default": "rec709"},
              "color_grade_lut": {"type": "string"},
              "resolution": {"type": "string", "examples": ["1080x1920", "1080x1080", "1920x1080", "3840x2160"]},
              "loudness_lufs": {
                "type": "number",
                "minimum": -30,
                "maximum": -10,
                "description": "-16 LUFS for streaming/social; -23 LUFS for broadcast; -14 LUFS for YouTube"
              },
              "true_peak_dbtp": {"type": "number", "maximum": -1}
            }
          },

          "has_burned_captions": {
            "type": "boolean",
            "description": "True is mandatory for mobile-first cuts; 80% of mobile video plays muted."
          },
          "caption_language": {"type": "string"},
          "caption_legibility_at_thumbnail": {"type": "boolean"},

          "safe_zone_compliance": {
            "type": "object",
            "required": ["overall_pass"],
            "properties": {
              "overall_pass": {"type": "boolean"},
              "bottom_20_percent_clear_for_reels_shorts": {"type": "boolean"},
              "right_edge_clear_for_shorts": {"type": "boolean"},
              "ctv_bezel_5_percent_safe": {"type": "boolean"},
              "newspaper_print_video_center_safe": {"type": "boolean"}
            }
          },

          "hook_seconds_designed": {
            "type": "number",
            "minimum": 0.5,
            "maximum": 3,
            "description": "Designed time-to-payoff in opening. <=3 is the bar; otherwise the cut returns to edit per Gati's quality bar."
          },

          "asci_compliance": {
            "type": "object",
            "required": ["paid_partnership_disclosure", "ai_persona_disclosure", "sectoral_disclaimers"],
            "properties": {
              "paid_partnership_disclosure": {
                "type": "object",
                "required": ["required"],
                "properties": {
                  "required": {"type": "boolean"},
                  "label_text": {"type": "string"},
                  "label_visible": {"type": "boolean"},
                  "label_visible_duration_sec": {"type": "number"},
                  "expected_min_duration_sec": {
                    "type": "number",
                    "description": "Computed: <=15s cut → 3s; 15-120s cut → duration/3; >120s → throughout."
                  },
                  "rule_id": {"const": "ASCI-DISC-002"}
                }
              },
              "ai_persona_disclosure": {
                "type": "object",
                "properties": {
                  "required": {"type": "boolean"},
                  "label_text": {"enum": ["AI-Generated", "Virtual Persona", "AI Influencer"]},
                  "label_first_5_sec": {"type": "boolean"},
                  "label_at_end": {"type": "boolean"},
                  "label_visible_throughout_speech": {"type": "boolean"},
                  "rule_id": {"const": "ASCI-AI-001"}
                }
              },
              "ai_minor_audience_check": {
                "type": "object",
                "properties": {
                  "uses_ai_persona": {"type": "boolean"},
                  "audience_includes_under_12": {"type": "boolean"},
                  "product_category_restricted": {"type": "boolean", "description": "Junk food, RMG, fantasy real-money, weight loss"},
                  "rule_id": {"const": "ASCI-AI-002"}
                }
              },
              "sectoral_disclaimers": {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["sector", "disclaimer_text", "rule_id"],
                  "properties": {
                    "sector": {"enum": ["BFSI", "healthcare", "gaming_rmg", "real_estate", "edtech", "alcohol_surrogate", "insurance", "mutual_funds"]},
                    "disclaimer_text": {"type": "string"},
                    "visible_duration_sec": {"type": "number"},
                    "voiceover_present": {"type": "boolean"},
                    "rule_id": {"type": "string", "description": "e.g., RBI-BFSI-001, SEBI-MUTUAL-FUND-001"}
                  }
                }
              }
            }
          },

          "thumbnail_variants": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
              "type": "object",
              "required": ["uri"],
              "properties": {
                "uri": {"type": "string"},
                "designed_for_platform": {"type": "string"},
                "predicted_ctr": {"type": "number"},
                "a_b_test_cell": {"type": "string"}
              }
            }
          },

          "regional_variants_linked": {
            "type": "array",
            "description": "If this cut has dubbed/subtitled regional versions, link them here.",
            "items": {"type": "object", "properties": {
              "language": {"type": "string"},
              "cut_id_of_variant": {"type": "string"}
            }}
          }
        }
      }
    },

    "source_files": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["type", "uri", "archived"],
        "properties": {
          "type": {"enum": ["premiere_project", "after_effects_project", "davinci_resolve_project", "raw_footage", "graded_proxy", "audio_session", "rushes_index"]},
          "uri": {"type": "string"},
          "archived": {"type": "boolean"},
          "archive_uri": {"type": "string"}
        }
      }
    },

    "audio_specs": {
      "type": "object",
      "properties": {
        "music_tracks": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["track_name", "license_type", "license_document_uri"],
            "properties": {
              "track_name": {"type": "string"},
              "artist_or_composer": {"type": "string"},
              "license_type": {"enum": ["original_score", "licensed_library", "production_music", "publishing_master_cleared", "creative_commons_attributed"]},
              "license_document_uri": {"type": "string"},
              "rights_cleared_for_territories": {"type": "array", "items": {"type": "string"}},
              "rights_cleared_until": {"type": "string", "format": "date"},
              "used_in_cut_ids": {"type": "array", "items": {"type": "string"}}
            }
          }
        },
        "voiceovers": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["language", "tts_provider"],
            "properties": {
              "language": {"type": "string"},
              "talent_name": {"type": "string"},
              "is_voice_clone": {"type": "boolean"},
              "clone_consent_document_uri": {"type": "string", "description": "MANDATORY if is_voice_clone=true"},
              "release_form_uri": {"type": "string"},
              "tts_provider": {"enum": ["elevenlabs", "bhashini", "google_tts", "azure_tts", "human_recorded"]},
              "used_in_cut_ids": {"type": "array", "items": {"type": "string"}}
            },
            "allOf": [{
              "if": {"properties": {"is_voice_clone": {"const": true}}},
              "then": {"required": ["clone_consent_document_uri"]}
            }]
          }
        },
        "sfx_library_licensed": {"type": "boolean"},
        "sfx_library_source": {"type": "string"}
      }
    },

    "ai_content_metadata": {
      "type": "object",
      "required": ["any_segment_ai_generated"],
      "properties": {
        "any_segment_ai_generated": {"type": "boolean"},
        "generators_used": {
          "type": "array",
          "items": {"enum": ["runway", "pika", "luma", "sora", "kling", "veo", "firefly_video", "stable_video_diffusion"]}
        },
        "content_credentials_embedded": {
          "type": "boolean",
          "description": "C2PA / Adobe Content Credentials. Required where supported."
        },
        "ai_segments": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["cut_id", "timestamp_range_sec", "generator"],
            "properties": {
              "cut_id": {"type": "string"},
              "timestamp_range_sec": {"type": "object", "properties": {
                "start": {"type": "number"},
                "end": {"type": "number"}
              }},
              "generator": {"type": "string"},
              "prompt_hash": {"type": "string"}
            }
          }
        },
        "deepfake_segments": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["cut_id", "subject", "subject_consent_uri", "deepfake_label_visible"],
            "properties": {
              "cut_id": {"type": "string"},
              "subject": {"type": "string"},
              "subject_consent_uri": {"type": "string"},
              "deepfake_label_visible": {"type": "boolean"},
              "rule_id": {"const": "IP-AI-CONSENT-001"}
            }
          }
        }
      }
    },

    "rights_clearance": {
      "type": "object",
      "required": ["talent_releases_complete", "music_licenses_complete"],
      "properties": {
        "talent_releases_complete": {"type": "boolean"},
        "talent_release_documents": {"type": "array", "items": {"type": "string"}},
        "location_releases_complete": {"type": "boolean"},
        "location_release_documents": {"type": "array", "items": {"type": "string"}},
        "music_licenses_complete": {"type": "boolean"},
        "product_placement_clearances": {"type": "array", "items": {"type": "object"}},
        "trademark_appearances_cleared": {"type": "boolean"},
        "celebrity_contracts_documented": {"type": "boolean"},
        "celebrity_contract_uris": {"type": "array", "items": {"type": "string"}}
      }
    },

    "quality_audit": {
      "type": "object",
      "required": ["scroll_stop_test_passed", "platform_spec_compliance_per_cut"],
      "properties": {
        "scroll_stop_test_passed": {
          "type": "boolean",
          "description": "Reviewed on phone, muted, in daylight (Gati's quality bar)."
        },
        "loudness_target_met_per_cut": {"type": "boolean"},
        "platform_spec_compliance_per_cut": {"type": "boolean"},
        "spec_violations_list": {"type": "array", "items": {"type": "object", "properties": {
          "cut_id": {"type": "string"},
          "violation": {"type": "string"},
          "remediation_status": {"enum": ["pending", "fixed", "waived_with_reason"]}
        }}}
      }
    }
  }
}
```

---

## §F.8 DAILY OPTIMIZATION LOG SCHEMA

**Producer**: Lakshya (one per day per campaign). **Consumer**: Pramaan (rolls up into performance reporting). **Triggers compliance rules**: DPDP-SENSITIVE-TARGETING-001 (no drift into prohibited bases), DPDP-CONSENT-001 (custom audiences still valid), PLATFORM-TOS-WHATSAPP-001 (if applicable), PLATFORM-TOS-META-SPECIAL-CAT-001 (if applicable). **HITL gate**: any single action with `budget_shift_percent > 20`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chitra.ai/schemas/v1.2.1/daily_optimization_log.json",
  "title": "Daily Optimization Log Artifact",
  "type": "object",
  "required": ["date", "campaign_id", "channels", "pacing", "actions_taken", "anomalies", "next_actions", "compliance_check"],
  "properties": {
    "date": {"type": "string", "format": "date"},
    "campaign_id": {"type": "string"},
    "report_run_at": {"type": "string", "format": "date-time"},

    "channels": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": [
          "channel", "spend_yesterday_inr", "impressions_yesterday",
          "clicks_yesterday", "conversions_yesterday", "roas_yesterday",
          "roas_7d_trend"
        ],
        "properties": {
          "channel": {"enum": [
            "meta_facebook", "meta_instagram", "meta_whatsapp", "meta_reels",
            "google_search", "google_search_ai_max", "google_pmax", "google_demand_gen", "google_display", "youtube",
            "jiohotstar", "jioads_network",
            "amazon_ads_sp", "amazon_ads_sb", "amazon_ads_sd", "amazon_dsp",
            "flipkart_ads",
            "blinkit_ads", "instamart_ads", "zepto_ads",
            "linkedin_ads", "x_ads",
            "sharechat", "moj", "josh", "dailyhunt",
            "dv360_programmatic", "trade_desk",
            "myntra_ads", "nykaa_ads"
          ]},
          "spend_yesterday_inr": {"type": "integer", "minimum": 0},
          "impressions_yesterday": {"type": "integer", "minimum": 0},
          "reach_yesterday": {"type": "integer"},
          "clicks_yesterday": {"type": "integer"},
          "ctr": {"type": "number"},
          "conversions_yesterday": {"type": "integer"},
          "conversion_value_inr": {"type": "integer"},
          "cpa_inr": {"type": "number"},
          "roas_yesterday": {"type": "number"},
          "roas_7d_trend": {"enum": ["improving", "flat", "declining", "insufficient_data"]},
          "roas_curve_slope": {"type": "number", "description": "Positive = improving over time; flat plateau triggers defense per Lakshya quality bar"},
          "frequency": {"type": "number"},
          "fatigue_flag": {"type": "boolean"},
          "learning_phase_status": {"enum": ["learning", "active", "limited", "not_applicable"]},
          "attribution_model_used": {"enum": ["last_click", "data_driven", "platform_self_attributed", "first_click", "linear", "time_decay", "position_based"]}
        }
      }
    },

    "pacing": {
      "type": "object",
      "required": ["total_budget_inr", "spent_to_date_inr", "days_elapsed", "days_total", "pacing_status"],
      "properties": {
        "total_budget_inr": {"type": "integer"},
        "spent_to_date_inr": {"type": "integer"},
        "days_elapsed": {"type": "integer"},
        "days_total": {"type": "integer"},
        "ideal_spend_to_date_inr": {"type": "integer"},
        "deviation_percent": {"type": "number"},
        "pacing_status": {"enum": ["on_pace", "over_pace_minor", "over_pace_critical", "under_pace_minor", "under_pace_critical"]},
        "moment_spike_reserve_remaining_inr": {"type": "integer", "description": "The 10% buffer for cricket/festival spikes"},
        "test_budget_reserve_remaining_inr": {"type": "integer", "description": "The 15-20% test reserve"}
      }
    },

    "actions_taken": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["action_id", "action_type", "target", "rationale", "expected_effect"],
        "properties": {
          "action_id": {"type": "string"},
          "action_type": {"enum": [
            "scale_up_budget", "scale_down_budget", "reallocate_budget",
            "pause_campaign", "pause_adset", "pause_ad", "resume",
            "creative_refresh", "creative_pause", "new_creative_test",
            "audience_expand", "audience_narrow", "audience_pause", "audience_new_test", "lookalike_layer_test",
            "exclusion_add", "exclusion_remove",
            "bid_strategy_change", "bid_cap_adjust", "target_cpa_adjust", "target_roas_adjust",
            "placement_add", "placement_remove",
            "landing_page_swap", "url_parameter_fix",
            "negative_keyword_add", "negative_keyword_remove",
            "schedule_change", "dayparting_adjust",
            "ai_max_text_guidelines_update", "advantage_plus_setting_change"
          ]},
          "target": {
            "type": "object",
            "required": ["level", "id"],
            "properties": {
              "level": {"enum": ["account", "campaign", "adset_or_adgroup", "ad", "audience", "creative_asset", "landing_page"]},
              "id": {"type": "string"},
              "platform": {"type": "string"}
            }
          },
          "before_state": {"type": "object", "description": "Snapshot of changed fields before action"},
          "after_state": {"type": "object", "description": "Snapshot of changed fields after action"},
          "budget_shift_percent": {
            "type": "number",
            "description": "If absolute value > 20, hitl_triggered must be true."
          },
          "rationale": {"type": "string", "minLength": 20},
          "expected_effect": {"type": "string"},
          "measured_effect_24h_later": {"type": "object", "description": "Backfilled in subsequent day's log"},
          "hitl_triggered": {"type": "boolean"},
          "human_approver_id": {"type": "string"},
          "human_approved_at": {"type": "string", "format": "date-time"},
          "executed_at": {"type": "string", "format": "date-time"}
        },
        "allOf": [{
          "if": {"properties": {"budget_shift_percent": {"type": "number", "minimum": 20}}},
          "then": {"required": ["hitl_triggered", "human_approver_id"]}
        }]
      }
    },

    "anomalies": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["anomaly_id", "type", "channel", "severity"],
        "properties": {
          "anomaly_id": {"type": "string"},
          "type": {"enum": [
            "cpm_spike", "cpm_drop_unexpected",
            "ctr_drop", "ctr_spike_suspicious",
            "conversion_rate_break", "conversion_tracking_loss",
            "policy_disapproval", "account_restriction",
            "audience_saturation", "frequency_above_threshold",
            "competitor_bid_disruption",
            "creative_fatigue_acute",
            "platform_outage", "api_breaking_change",
            "attribution_model_disagreement_widened",
            "consent_signal_drop"
          ]},
          "channel": {"type": "string"},
          "severity": {"enum": ["low", "medium", "high", "critical"]},
          "magnitude_percent": {"type": "number"},
          "diagnosis": {"type": "string"},
          "action_recommended": {"type": "string"},
          "page_human_on_critical": {"type": "boolean"}
        }
      }
    },

    "next_actions": {
      "type": "array",
      "minItems": 1,
      "maxItems": 5,
      "description": "Top 3-5 priority actions for tomorrow. Lakshya's daily focus, ranked.",
      "items": {
        "type": "object",
        "required": ["priority", "action", "owner"],
        "properties": {
          "priority": {"type": "integer", "minimum": 1, "maximum": 5},
          "action": {"type": "string"},
          "owner": {"enum": ["lakshya", "rekha", "gati", "lehar", "human", "client", "pramaan"]},
          "deadline": {"type": "string", "format": "date"},
          "expected_impact_band": {"enum": ["small", "medium", "large", "unknown"]}
        }
      }
    },

    "compliance_check": {
      "type": "object",
      "required": ["sensitive_targeting_clean", "consent_artifacts_valid"],
      "properties": {
        "sensitive_targeting_clean": {
          "type": "boolean",
          "description": "DPDP-SENSITIVE-TARGETING-001. False if audience definition added prohibited bases overnight."
        },
        "consent_artifacts_valid": {
          "type": "boolean",
          "description": "DPDP-CONSENT-001. False if any custom audience consent has lapsed."
        },
        "whatsapp_opt_in_respected": {"type": "boolean"},
        "special_ad_category_declared": {"type": "boolean"},
        "sectoral_targeting_age_floor_respected": {"type": "boolean", "description": "GAMING-RMG-001 (>=18) etc."},
        "rules_evaluated": {"type": "array", "items": {"type": "string"}}
      }
    }
  }
}
```

---

## §F.9 CONTENT CALENDAR SCHEMA

**Producer**: Lehar (rolling monthly + weekly increments). **Consumers**: Lakshya (to decide which organic posts to boost), Pramaan (to correlate organic-paid). **Triggers compliance rules**: ASCI-DISC-001 (per post), CULTURAL-* rules (per trend decision).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chitra.ai/schemas/v1.2.1/content_calendar.json",
  "title": "Content Calendar Artifact",
  "type": "object",
  "required": [
    "period", "platforms_active", "scheduled_posts",
    "festival_and_sports_overlay", "trend_pipeline",
    "real_time_response_library", "community_management_protocol"
  ],
  "properties": {
    "period": {
      "type": "object",
      "required": ["type", "start_date", "end_date"],
      "properties": {
        "type": {"enum": ["weekly", "monthly", "quarterly"]},
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": "string", "format": "date"}
      }
    },

    "platforms_active": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["platform", "frequency", "active"],
        "properties": {
          "platform": {"type": "string"},
          "frequency": {"type": "string", "description": "Free-text but disciplined, e.g., '1/day feed + 3/day stories'"},
          "active": {"type": "boolean"},
          "primary_language": {"type": "string"},
          "secondary_languages": {"type": "array", "items": {"type": "string"}}
        }
      }
    },

    "scheduled_posts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["post_id", "scheduled_at", "platform", "theme", "language", "approval_status"],
        "properties": {
          "post_id": {"type": "string"},
          "scheduled_at": {"type": "string", "format": "date-time"},
          "platform": {"type": "string"},
          "theme": {"enum": [
            "educational", "entertaining", "aspirational", "community",
            "promotional", "celebratory", "service_update",
            "thought_leadership", "behind_the_scenes", "user_generated_repost",
            "tutorial", "myth_busting"
          ]},
          "language": {"type": "string"},
          "asset_uri": {"type": "string"},
          "caption_uri": {"type": "string"},
          "linked_social_post_artifact": {
            "type": "string",
            "description": "URI of the full social_post artifact (§F.10) — calendar holds the slot, social_post holds the substance."
          },
          "campaign_id": {"type": "string", "description": "Null if always-on; non-null if campaign-tied"},
          "festival_or_moment_tie": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "date": {"type": "string", "format": "date"},
              "source": {"enum": ["festival_calendar", "cricket_calendar", "film_release", "civic_event", "brand_anniversary"]}
            }
          },
          "approval_status": {"enum": ["draft", "queued_for_approval", "approved", "scheduled", "published", "withdrawn"]}
        }
      }
    },

    "festival_and_sports_overlay": {
      "type": "array",
      "description": "Live overlay from CHITRA Resource Pack §A.2/§A.3 for the calendar period.",
      "items": {
        "type": "object",
        "required": ["event", "date", "type", "marketing_relevance"],
        "properties": {
          "event": {"type": "string"},
          "date": {"type": "string", "format": "date"},
          "type": {"enum": ["festival", "sports", "civic", "cultural", "trade"]},
          "marketing_relevance": {"enum": ["high", "medium", "low", "avoid"]},
          "planned_content_post_ids": {"type": "array", "items": {"type": "string"}},
          "regional_scope": {"type": "array", "items": {"type": "string"}, "description": "States or regions where this event drives behavior"}
        }
      }
    },

    "trend_pipeline": {
      "type": "array",
      "minItems": 3,
      "maxItems": 7,
      "description": "3-5 hookable trends per week (Lehar quality bar). Cap at 7 to enforce focus.",
      "items": {
        "type": "object",
        "required": ["trend_id", "trend_description", "source_platform", "decision", "cultural_risk_check"],
        "properties": {
          "trend_id": {"type": "string"},
          "trend_description": {"type": "string"},
          "source_platform": {"enum": [
            "instagram_audio", "instagram_format",
            "youtube_shorts", "tiktok_format",
            "moj", "sharechat", "josh",
            "x_topic",
            "cricket_moment", "film_release_weekend",
            "viral_meme", "news_cycle", "industry_event"
          ]},
          "detected_at": {"type": "string", "format": "date-time"},
          "estimated_half_life_hours": {"type": "number"},
          "decision": {"enum": ["ride", "observe", "skip"]},
          "rationale": {"type": "string"},
          "on_brand_adaptation_draft": {"type": "string", "description": "Required if decision=ride"},
          "deadline_for_riding": {"type": "string", "format": "date-time"},
          "linked_post_id": {"type": "string"},
          "cultural_risk_check": {
            "type": "object",
            "required": ["level"],
            "properties": {
              "level": {"enum": ["clear", "yellow", "red"]},
              "concerns": {"type": "array", "items": {"type": "string"}},
              "human_reviewed": {"type": "boolean"}
            }
          },
          "outcome": {
            "type": "object",
            "description": "Backfilled after riding; informs trend-detection learning loop.",
            "properties": {
              "reach": {"type": "integer"},
              "engagement_rate": {"type": "number"},
              "judged_success": {"type": "boolean"}
            }
          }
        },
        "allOf": [{
          "if": {"properties": {"decision": {"const": "ride"}}},
          "then": {"required": ["on_brand_adaptation_draft", "deadline_for_riding"]}
        }]
      }
    },

    "real_time_response_library": {
      "type": "object",
      "required": ["templates"],
      "properties": {
        "templates": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["scenario", "template_text", "max_response_time_minutes"],
            "properties": {
              "scenario": {"enum": [
                "cricket_win_india",
                "cricket_milestone_player",
                "ipl_team_win_partner_brand",
                "film_release_weekend",
                "festival_greeting_generic",
                "festival_greeting_regional",
                "industry_news_positive",
                "customer_compliment_public",
                "customer_complaint_public",
                "competitor_outage_no_gloating",
                "viral_brand_mention_neutral",
                "viral_brand_mention_negative",
                "crisis_response_minor",
                "crisis_response_major",
                "trolling_decision_tree"
              ]},
              "template_text": {"type": "string"},
              "platform_variants": {
                "type": "object",
                "description": "Map of platform → adapted template text",
                "additionalProperties": {"type": "string"}
              },
              "language_variants_available": {"type": "array", "items": {"type": "string"}},
              "requires_human_approval": {"type": "boolean"},
              "max_response_time_minutes": {
                "type": "integer",
                "default": 90,
                "description": "Lehar's 90-minute window for breaking moments"
              },
              "asci_disclosure_already_embedded": {"type": "boolean"}
            }
          }
        }
      }
    },

    "community_management_protocol": {
      "type": "object",
      "required": ["dm_response_sla_hours", "comment_response_sla_hours", "support_mention_sla_minutes", "escalation_tree"],
      "properties": {
        "dm_response_sla_hours": {"type": "number", "default": 2, "maximum": 24},
        "comment_response_sla_hours": {"type": "number", "default": 4, "maximum": 24},
        "support_mention_sla_minutes": {"type": "number", "default": 30, "maximum": 120},
        "escalation_tree": {
          "type": "object",
          "required": ["customer_service_issue", "legal_complaint", "mental_health_flag", "pr_risk"],
          "properties": {
            "customer_service_issue": {"type": "string", "description": "Owner role + contact"},
            "legal_complaint": {"type": "string"},
            "mental_health_flag": {"type": "string", "description": "Including ASCI-aligned crisis-resource handover protocol"},
            "pr_risk": {"type": "string"},
            "child_safety_concern": {"type": "string"}
          }
        }
      }
    },

    "compliance_check": {
      "type": "object",
      "properties": {
        "asci_disclosure_protocol_in_place": {"type": "boolean"},
        "platform_tos_aware": {"type": "boolean"},
        "trend_riding_excludes_sensitive_categories": {
          "type": "boolean",
          "description": "No riding tragedies, communal flashpoints, or politically partisan moments"
        },
        "rules_evaluated": {"type": "array", "items": {"type": "string"}}
      }
    }
  }
}
```

---

## §F.10 SOCIAL POST SCHEMA (the most granular artifact in CHITRA)

**Producer**: Lehar (or, for campaign-paid posts, Lakshya in coordination). **Consumer**: publishing channel via the relevant MCP server (meta-marketing, youtube-mcp, x-marketing-mcp, etc.). **Triggers compliance rules**: many — see cross-reference matrix in §F.12. Every social post passes through the sanitizer (§H of v1.2) before publishing.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chitra.ai/schemas/v1.2.1/social_post.json",
  "title": "Social Post Artifact (per-post unit)",
  "type": "object",
  "required": [
    "post_id", "platform", "language", "scheduled_at",
    "content", "paid_partnership", "ai_persona",
    "cultural_risk_check", "compliance_flags", "lifecycle"
  ],
  "properties": {
    "post_id": {"type": "string"},
    "platform": {"enum": [
      "instagram_feed", "instagram_reel", "instagram_story", "instagram_carousel",
      "facebook_feed", "facebook_reel", "facebook_story",
      "youtube_short", "youtube_long", "youtube_community",
      "x_tweet", "x_thread",
      "linkedin_post", "linkedin_article",
      "moj", "sharechat", "josh",
      "whatsapp_status", "whatsapp_broadcast", "whatsapp_business_template",
      "threads",
      "pinterest_pin"
    ]},
    "language": {"type": "string"},
    "scheduled_at": {"type": "string", "format": "date-time"},
    "campaign_id": {"type": "string", "description": "Null if always-on organic"},
    "theme": {"type": "string"},
    "content_calendar_slot_id": {"type": "string"},

    "content": {
      "type": "object",
      "required": ["caption"],
      "properties": {
        "caption": {"type": "string", "maxLength": 5000},
        "first_line": {
          "type": "string",
          "description": "Materially significant — ASCI-DISC-001 requires #Ad here for paid content."
        },
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "asset_uri": {"type": "string"},
        "asset_type": {"enum": ["image", "video", "carousel", "text_only", "link_card", "poll", "story_card"]},
        "carousel_assets": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "linked_motion_cut_id": {"type": "string", "description": "If asset is video from motion_asset_registry"},
        "alt_text": {"type": "string"},
        "tagged_handles": {"type": "array", "items": {"type": "string"}},
        "geotag": {"type": "string"},
        "cta_button": {
          "type": "object",
          "properties": {
            "text": {"type": "string", "maxLength": 30},
            "url": {"type": "string"},
            "tracking_parameters": {"type": "object"}
          }
        }
      }
    },

    "paid_partnership": {
      "type": "object",
      "required": ["is_paid"],
      "properties": {
        "is_paid": {"type": "boolean"},
        "partner_brand": {"type": "string"},
        "material_connection_type": {"enum": ["cash_payment", "free_product", "free_service", "affiliate_commission", "employment", "equity"]},
        "disclosure_method": {
          "type": "array",
          "items": {"enum": [
            "hashtag_ad_first_line",
            "hashtag_sponsored_first_line",
            "hashtag_paidpartnership_first_line",
            "platform_native_paid_partnership_label",
            "verbal_disclosure_first_10_sec_of_video",
            "in_video_text_label",
            "story_sticker_paid_partnership"
          ]}
        },
        "asci_rule_satisfied": {"const": "ASCI-DISC-001"}
      },
      "allOf": [{
        "if": {"properties": {"is_paid": {"const": true}}},
        "then": {"required": ["partner_brand", "material_connection_type", "disclosure_method"]}
      }]
    },

    "ai_persona": {
      "type": "object",
      "required": ["uses_ai_persona"],
      "properties": {
        "uses_ai_persona": {"type": "boolean"},
        "uses_ai_generated_likeness": {"type": "boolean"},
        "ai_label_text": {"enum": ["AI-Generated", "Virtual Persona", "AI Influencer"]},
        "ai_label_visible": {"type": "boolean"},
        "audience_includes_under_12": {"type": "boolean"},
        "product_category": {"type": "string"},
        "product_category_restricted_for_minors": {
          "type": "boolean",
          "description": "Junk food, RMG, fantasy-real-money, weight loss"
        },
        "asci_rules_satisfied": {"type": "array", "items": {"enum": ["ASCI-AI-001", "ASCI-AI-002"]}}
      },
      "allOf": [{
        "if": {"properties": {"uses_ai_persona": {"const": true}}},
        "then": {"required": ["ai_label_text", "ai_label_visible"]}
      }]
    },

    "sector_overlay": {
      "type": "object",
      "properties": {
        "sector": {"enum": [
          "BFSI", "healthcare", "edtech", "gaming_rmg", "real_estate",
          "alcohol_surrogate", "tobacco_surrogate",
          "fmcg", "tech", "auto", "lifestyle", "retail", "d2c",
          "telecom", "energy", "travel", "other"
        ]},
        "contains_technical_advice": {"type": "boolean"},
        "influencer_qualification_disclosed": {
          "type": "boolean",
          "description": "Required if technical advice in BFSI / health / nutrition (Addendum 2)"
        },
        "qualification_document_uri": {"type": "string"},
        "sectoral_disclaimers_present": {"type": "array", "items": {"type": "string"}},
        "applicable_rule_ids": {
          "type": "array",
          "items": {"enum": [
            "ASCI-BFSI-001", "ASCI-HEALTH-001",
            "RBI-BFSI-001", "SEBI-MUTUAL-FUND-001", "IRDAI-INSURANCE-001",
            "GAMING-RMG-001", "DMRA-001",
            "REAL-ESTATE-RERA-001", "EDTECH-NEP-001",
            "TOBACCO-001", "ALCOHOL-SURROGATE-001",
            "HEALTHCARE-CLAIM-SUB-001"
          ]}
        }
      }
    },

    "claim_substantiation": {
      "type": "object",
      "description": "If post contains performance / health / financial / scientific claims",
      "properties": {
        "contains_substantive_claim": {"type": "boolean"},
        "claims_list": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "claim_text": {"type": "string"},
              "claim_type": {"enum": ["performance", "health", "financial", "scientific", "environmental", "comparative"]},
              "evidence_document_uri": {"type": "string"},
              "evidence_type": {"enum": ["third_party_certification", "peer_reviewed_study", "internal_test", "regulatory_approval", "customer_data_aggregated"]}
            }
          }
        }
      }
    },

    "whatsapp_specifics": {
      "type": "object",
      "description": "Required if platform starts with whatsapp_",
      "properties": {
        "template_id": {"type": "string"},
        "template_category": {"enum": ["marketing", "utility", "authentication"]},
        "recipient_list_id": {"type": "string"},
        "recipient_list_consent_artifact_id": {"type": "string"},
        "respects_24h_utility_window": {"type": "boolean"},
        "opt_out_link_present": {"type": "boolean"},
        "asci_rule_satisfied": {"const": "PLATFORM-TOS-WHATSAPP-001"}
      }
    },

    "audience_targeting": {
      "type": "object",
      "description": "Snapshot if post is boosted/paid",
      "properties": {
        "boost_intent": {"type": "boolean"},
        "estimated_audience_size": {"type": "integer"},
        "targeting_bases_used": {
          "type": "array",
          "items": {"enum": [
            "age", "gender", "location", "language",
            "interest", "behavior", "lookalike",
            "custom_audience", "retargeting",
            "device", "income_proxy", "education_proxy"
          ]}
        },
        "audience_min_age": {"type": "integer", "minimum": 13},
        "consent_artifact_id": {"type": "string"},
        "asci_or_dpdp_rules_evaluated": {"type": "array", "items": {"type": "string"}}
      }
    },

    "cultural_risk_check": {
      "type": "object",
      "required": ["audited", "level"],
      "properties": {
        "audited": {"type": "boolean"},
        "level": {"enum": ["low", "medium", "high"]},
        "register": {"type": "array", "items": {"type": "object", "properties": {
          "category": {"enum": ["religion", "caste", "gender", "region", "political", "language", "child_safety", "body_image", "disability"]},
          "concern": {"type": "string"},
          "mitigation": {"type": "string"}
        }}},
        "human_reviewed": {"type": "boolean"},
        "rules_evaluated": {"type": "array", "items": {"type": "string"}}
      }
    },

    "compliance_flags": {
      "type": "object",
      "required": ["sanitizer_run", "sanitizer_pass"],
      "properties": {
        "sanitizer_run": {"type": "boolean"},
        "sanitizer_pass": {"type": "boolean"},
        "rules_evaluated": {"type": "array", "items": {"type": "string"}},
        "rules_failed": {"type": "array", "items": {"type": "string"}},
        "auto_fixes_applied": {"type": "array", "items": {"type": "string"}},
        "human_review_required": {"type": "boolean"},
        "human_approver_id": {"type": "string"},
        "human_approved_at": {"type": "string", "format": "date-time"}
      }
    },

    "engagement_targets": {
      "type": "object",
      "properties": {
        "predicted_reach": {"type": "integer"},
        "predicted_impressions": {"type": "integer"},
        "predicted_engagement_rate": {"type": "number"},
        "predicted_ctr": {"type": "number"},
        "prediction_model_version": {"type": "string"}
      }
    },

    "lifecycle": {
      "type": "object",
      "required": ["status"],
      "properties": {
        "status": {"enum": [
          "draft", "queued_for_approval", "approved",
          "scheduled", "publishing", "published",
          "boosted", "completed", "withdrawn", "deleted_by_platform"
        ]},
        "approval_chain": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "approver_id": {"type": "string"},
              "role": {"type": "string"},
              "approved_at": {"type": "string", "format": "date-time"},
              "decision": {"enum": ["approved", "rejected", "approved_with_changes"]},
              "comment": {"type": "string"}
            }
          }
        },
        "published_at": {"type": "string", "format": "date-time"},
        "external_post_id": {"type": "string"},
        "external_post_url": {"type": "string"}
      }
    }
  }
}
```

---

## §F.11 LEARNINGS DOSSIER (PROMOTED TO STANDALONE)

### Migration note
In v1.2 §F.6, `learnings_dossier` was nested inside `performance_report`. In v1.2.1, it is promoted to its own artifact.

**Why**: different consumer (Drishti, next cycle vs current-cycle stakeholders), different lifecycle (accumulates across campaigns vs point-in-time snapshot), different access pattern (read by next-cycle planning vs read by reporting). Embedding it created a coupling that made cross-campaign learning awkward.

**Migration**: `performance_report.learnings_dossier` becomes `performance_report.learnings_dossier_uri` — a pointer. The dossier itself is a separate artifact with its own envelope. Existing v1.2 deployments retain backward compatibility for 90 days; the inline object is still accepted but flagged as deprecated.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chitra.ai/schemas/v1.2.1/learnings_dossier.json",
  "title": "Learnings Dossier — standalone artifact",
  "type": "object",
  "required": [
    "dossier_id", "source_campaigns",
    "what_worked", "what_didnt", "what_surprised",
    "what_to_test_next", "brief_amendments",
    "privacy_compliance"
  ],
  "properties": {
    "dossier_id": {"type": "string"},
    "tenant_id": {"type": "string"},
    "created_at": {"type": "string", "format": "date-time"},
    "supersedes_dossier_id": {"type": "string", "description": "Pointer to prior dossier; chain captures evolution of tenant learning"},

    "source_campaigns": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["campaign_id", "campaign_name", "date_range", "final_roas"],
        "properties": {
          "campaign_id": {"type": "string"},
          "campaign_name": {"type": "string"},
          "date_range": {
            "type": "object",
            "required": ["start", "end"],
            "properties": {
              "start": {"type": "string", "format": "date"},
              "end": {"type": "string", "format": "date"}
            }
          },
          "final_roas": {"type": "number"},
          "performance_report_uri": {"type": "string"}
        }
      }
    },

    "what_worked": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["observation", "evidence", "confidence", "generalizability"],
        "properties": {
          "observation": {"type": "string", "minLength": 30},
          "evidence": {"type": "string", "description": "Specific metric or test result citation"},
          "metric_basis": {
            "type": "object",
            "properties": {
              "metric_name": {"type": "string"},
              "value": {"type": "number"},
              "baseline": {"type": "number"},
              "lift_percent": {"type": "number"},
              "p_value": {"type": "number"},
              "sample_size": {"type": "integer"}
            }
          },
          "confidence": {"enum": ["high", "medium", "low"]},
          "generalizability": {"enum": ["this_brand_only", "this_category", "this_audience", "broadly_applicable", "unknown"]},
          "tags": {"type": "array", "items": {"enum": ["creative", "audience", "channel", "timing", "offer", "format", "language", "festival_tie", "sports_tie"]}}
        }
      }
    },

    "what_didnt": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["observation", "evidence"],
        "properties": {
          "observation": {"type": "string"},
          "evidence": {"type": "string"},
          "hypothesized_reason": {"type": "string"},
          "actionable_fix": {"type": "string"},
          "do_not_repeat_tag": {"type": "boolean", "description": "If true, flagged for Disha's kill-criteria reference"}
        }
      }
    },

    "what_surprised": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["surprise"],
        "properties": {
          "surprise": {"type": "string"},
          "evidence": {"type": "string"},
          "implication_for_future_strategy": {"type": "string"},
          "warrants_dedicated_test": {"type": "boolean"}
        }
      }
    },

    "what_to_test_next": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["hypothesis", "proposed_test_design", "priority"],
        "properties": {
          "hypothesis": {"type": "string"},
          "proposed_test_design": {"type": "string"},
          "test_type": {"enum": ["a_b", "multivariate", "geo_holdout", "audience_holdout", "incrementality", "creative_fatigue", "format_swap"]},
          "expected_lift_percent": {"type": "number"},
          "minimum_detectable_lift": {"type": "number"},
          "priority": {"enum": ["P0", "P1", "P2"]},
          "estimated_cost_inr": {"type": "integer"}
        }
      }
    },

    "brief_amendments": {
      "type": "array",
      "description": "Concrete edits Drishti should make to next brief. The closed loop runs here.",
      "items": {
        "type": "object",
        "required": ["brief_section", "amendment_proposed", "supporting_evidence"],
        "properties": {
          "brief_section": {"enum": [
            "business_problem", "target_audience", "perception_gap",
            "insight", "core_message", "tone_spectrum",
            "mandatories", "prohibitions", "success_metrics", "cultural_overlay"
          ]},
          "current_state": {"type": "string"},
          "amendment_proposed": {"type": "string"},
          "supporting_evidence": {"type": "string"},
          "confidence": {"enum": ["high", "medium", "low"]}
        }
      }
    },

    "creative_pattern_library": {
      "type": "array",
      "description": "Concrete creative patterns proven within this tenant — Roop and Vaani consume this in their next concept work.",
      "items": {
        "type": "object",
        "required": ["pattern_name", "description"],
        "properties": {
          "pattern_name": {"type": "string"},
          "description": {"type": "string"},
          "category": {"enum": ["hook", "narrative_arc", "visual_treatment", "tagline_structure", "format_choice", "music_register", "color_register"]},
          "example_asset_uris": {"type": "array", "items": {"type": "string"}},
          "performance_basis": {"type": "object"},
          "do_not_use_for": {"type": "array", "items": {"type": "string"}, "description": "Sub-segments or formats where this pattern underperformed"}
        }
      }
    },

    "audience_pattern_library": {
      "type": "array",
      "description": "Audience definitions proven to convert within this tenant — Lakshya consumes this in next media plan.",
      "items": {
        "type": "object",
        "required": ["audience_name", "definition"],
        "properties": {
          "audience_name": {"type": "string"},
          "definition": {"type": "string"},
          "platform": {"type": "string"},
          "performance_track_record": {
            "type": "object",
            "properties": {
              "campaigns_used_in": {"type": "integer"},
              "avg_roas": {"type": "number"},
              "avg_ctr": {"type": "number"},
              "fatigue_observed_after_days": {"type": "integer"}
            }
          }
        }
      }
    },

    "channel_pattern_library": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "channel": {"type": "string"},
          "observation": {"type": "string"},
          "objective_fit": {"enum": ["strong", "moderate", "weak", "context_dependent"]}
        }
      }
    },

    "festival_and_sports_learnings": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "moment": {"type": "string"},
          "observation": {"type": "string"},
          "recommendation_for_next_cycle": {"type": "string"}
        }
      }
    },

    "privacy_compliance": {
      "type": "object",
      "required": ["individual_level_data_present", "cohort_minimum_respected", "dpdp_retention_ok"],
      "properties": {
        "individual_level_data_present": {"const": false},
        "cohort_minimum_respected": {"const": true},
        "dpdp_retention_ok": {"type": "boolean"},
        "minimum_cohort_size_used": {"type": "integer", "minimum": 100}
      }
    }
  }
}
```

---

## §F.12 RULE-TO-SCHEMA CROSS-REFERENCE MATRIX

This is what makes §H (the sanitizer) efficient at runtime. Without this matrix, the sanitizer would evaluate every rule's `applies_when` against every artifact. With it, the sanitizer pre-filters rules by `artifact_type` and runs only the relevant ones.

The matrix is the canonical reverse index of v1.2 §G's `applies_to` declarations.

| Rule ID | creative_brief | concept_slate | concept_bible | asset_registry | motion_asset_registry | media_plan | daily_optimization_log | content_calendar | social_post | performance_report | learnings_dossier |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **ASCI-DISC-001** | | | | | | | | ● | ● | | |
| **ASCI-DISC-002** | | | | | ● | | | | ● | | |
| **ASCI-AI-001** | | | | ● | ● | | | | ● | | |
| **ASCI-AI-002** | | | | ● | ● | ● | | | ● | | |
| **ASCI-BFSI-001** | | | ● | ● | ● | | | | ● | | |
| **ASCI-HEALTH-001** | | | ● | ● | ● | | | | ● | | |
| **ASCI-DARK-001** | | | | ● | | ● | | | ● | | |
| **ASCI-GREENWASH-001** | | | ● | ● | ● | | | | ● | | |
| **DPDP-CONSENT-001** | | | | | | ● | ● | | ● | | |
| **DPDP-CHILDREN-001** | ● | ● | | | | ● | | | ● | | |
| **DPDP-RETENTION-001** | | | | | | | | | | ● | ● |
| **DPDP-SENSITIVE-TARGETING-001** | | | | | | ● | ● | | ● | | |
| **DMRA-001** | | ● | ● | ● | ● | | | | ● | | |
| **RBI-BFSI-001** | | | ● | ● | ● | | | | ● | | |
| **SEBI-MUTUAL-FUND-001** | | | ● | ● | ● | | | | ● | | |
| **IRDAI-INSURANCE-001** | | | ● | ● | | | | | ● | | |
| **GAMING-RMG-001** | ● | ● | ● | ● | ● | ● | ● | | ● | | |
| **TOBACCO-001** | ● | ● | ● | ● | ● | ● | | | ● | | |
| **ALCOHOL-SURROGATE-001** | | ● | ● | ● | ● | | | | ● | | |
| **REAL-ESTATE-RERA-001** | | | ● | ● | | | | | ● | | |
| **EDTECH-NEP-001** | | | ● | ● | ● | | | | ● | | |
| **HEALTHCARE-CLAIM-SUB-001** | | | ● | ● | ● | | | | ● | | |
| **IP-TRADEMARK-001** | | ● | ● | ● | ● | | | | ● | | |
| **IP-COPYRIGHT-001** | | | | ● | ● | | | | ● | | |
| **IP-AI-CONSENT-001** | | | | | ● | | | | ● | | |
| **PLATFORM-TOS-WHATSAPP-001** | | | | | | ● | ● | ● | ● | | |
| **PLATFORM-TOS-META-SPECIAL-CAT-001** | | | | | | ● | ● | | ● | | |
| **CULTURAL-RELIGION-001** | ● | ● | ● | ● | ● | | | ● | ● | | |
| **CULTURAL-CASTE-001** | ● | ● | ● | ● | ● | | | ● | ● | | |
| **CULTURAL-GENDER-001** | ● | ● | ● | ● | ● | | | ● | ● | | |
| **CULTURAL-REGION-001** | ● | ● | ● | ● | ● | | | ● | ● | | |
| **CULTURAL-POLITICAL-001** | | ● | ● | ● | ● | | | ● | ● | | |

### Reading the matrix

- **Each ● is an enforcement point.** When an artifact of that type is presented to the sanitizer, that rule runs.
- **The `social_post` column is dense** because it is the final publishing artifact — every regulatory and cultural concern surfaces here at the latest.
- **The `learnings_dossier` and `performance_report` columns are sparse** because they're reflective, not publishing, artifacts; privacy and retention are the active concerns.
- **The `daily_optimization_log` column is moderate**: targeting and consent checks run daily to catch drift after launch.
- **No rule from §G is missing from this matrix.** If a new rule is added to §G in a future patch, it must declare its `applies_to` and this matrix updates in lockstep.

### Sanitizer pre-filter pseudocode

```python
def sanitize(artifact_type, artifact, context):
    applicable_rule_ids = RULE_MATRIX[artifact_type]  # O(1) lookup
    rules = [rule_registry.get(rid) for rid in applicable_rule_ids]
    rules = [r for r in rules if r.applies_when(artifact, context)]
    # ... evaluate each ...
```

---

## §F.13 EXAMPLE SANITIZER OUTPUTS

What a sanitizer result looks like in practice. These examples show the contract between sanitizer and agents — the agent knows exactly what to fix.

### Example 1: `social_post` passes cleanly

```json
{
  "pass": true,
  "checks_run": [
    "ASCI-DISC-001",
    "ASCI-AI-001",
    "DPDP-CONSENT-001",
    "CULTURAL-RELIGION-001",
    "CULTURAL-GENDER-001",
    "CULTURAL-REGION-001",
    "PLATFORM-TOS-META-SPECIAL-CAT-001"
  ],
  "violations": [],
  "warnings": [],
  "human_review_required": false,
  "redacted_payload": null
}
```

### Example 2: `social_post` blocked on missing `#Ad`

```json
{
  "pass": false,
  "checks_run": [
    "ASCI-DISC-001",
    "ASCI-AI-001",
    "DPDP-CONSENT-001",
    "CULTURAL-RELIGION-001",
    "CULTURAL-GENDER-001",
    "CULTURAL-REGION-001"
  ],
  "violations": [
    {
      "rule_id": "ASCI-DISC-001",
      "source": "ASCI",
      "message": "Paid partnership disclosure missing. ASCI requires #Ad in first caption line.",
      "evidence": "social_post.content.first_line == 'Loving this new shampoo!' — no qualifying hashtag",
      "suggested_fix": "Prepend '#Ad ' to first_line and re-validate.",
      "severity": "block",
      "auto_fix_available": true
    }
  ],
  "warnings": [],
  "human_review_required": false,
  "redacted_payload": {
    "post_id": "post_abc123",
    "content": {
      "caption": "#Ad Loving this new shampoo!...",
      "first_line": "#Ad Loving this new shampoo!"
    }
  }
}
```

> Note: when `auto_fix_available=true` and the agent's policy permits auto-fix, the sanitizer returns the `redacted_payload` for the agent to verify and re-submit. Auto-fix never silently rewrites and publishes — re-validation is mandatory.

### Example 3: `motion_asset_registry` blocked on missing AI disclosure timing

```json
{
  "pass": false,
  "checks_run": [
    "ASCI-DISC-002",
    "ASCI-AI-001",
    "ASCI-AI-002",
    "IP-COPYRIGHT-001",
    "IP-AI-CONSENT-001",
    "CULTURAL-RELIGION-001",
    "CULTURAL-GENDER-001"
  ],
  "violations": [
    {
      "rule_id": "ASCI-AI-001",
      "source": "ASCI",
      "message": "AI persona used but label not visible in first 5 seconds.",
      "evidence": "cut_list[2].asci_compliance.ai_persona_disclosure.label_first_5_sec == false",
      "suggested_fix": "Re-edit cut to surface 'AI-Generated' label at 0:00-0:05. Then re-submit.",
      "severity": "block",
      "auto_fix_available": false
    },
    {
      "rule_id": "ASCI-AI-001",
      "source": "ASCI",
      "message": "AI persona speaks but label not visible throughout speech.",
      "evidence": "cut_list[2].asci_compliance.ai_persona_disclosure.label_visible_throughout_speech == false",
      "suggested_fix": "Add persistent corner-bug 'AI-Generated' overlay for duration of synthetic-voice dialogue (00:08-00:24).",
      "severity": "block",
      "auto_fix_available": false
    }
  ],
  "warnings": [
    {
      "rule_id": "IP-COPYRIGHT-001",
      "message": "Music license cleared for India only; cut_list[0] is tagged for jiohotstar_pre_roll which is India-bound — OK. cut_list[3] is tagged for youtube_long which has global reach — verify territory cleared.",
      "severity": "warn"
    }
  ],
  "human_review_required": true,
  "human_review_reason": "ASCI-AI-001 has human_review_on_fail=true."
}
```

### Example 4: `daily_optimization_log` blocked on un-approved >20% budget shift

```json
{
  "pass": false,
  "checks_run": [
    "DPDP-CONSENT-001",
    "DPDP-SENSITIVE-TARGETING-001",
    "PLATFORM-TOS-META-SPECIAL-CAT-001"
  ],
  "violations": [
    {
      "rule_id": "CHITRA-HITL-BUDGET",
      "source": "CHITRA process rule",
      "message": "Budget shift of 34% recorded without HITL approval.",
      "evidence": "actions_taken[1].budget_shift_percent == 34.2; hitl_triggered == false; human_approver_id is null",
      "suggested_fix": "Route action to brand owner for approval. Until approved, action must be reverted or marked pending.",
      "severity": "block",
      "auto_fix_available": false
    }
  ],
  "warnings": [],
  "human_review_required": true
}
```

### Example 5: `learnings_dossier` blocked on individual-level data leak

```json
{
  "pass": false,
  "checks_run": [
    "DPDP-RETENTION-001"
  ],
  "violations": [
    {
      "rule_id": "DPDP-RETENTION-001",
      "source": "DPDP",
      "message": "Individual-level data found in learnings dossier.",
      "evidence": "what_worked[3].evidence contains 'customer_id=A8C9F2 converted at INR 4,200' — individual record, forbidden in next-cycle artifact.",
      "suggested_fix": "Aggregate to cohort. Replace 'customer_id=A8C9F2' with cohort statistic. Minimum cohort size: 100.",
      "severity": "block",
      "auto_fix_available": false
    }
  ],
  "warnings": [],
  "human_review_required": true
}
```

---

## §F.14 IMPLEMENTATION NOTES

### F.14.1 Schema hosting and resolution

- All schemas resolve from `https://chitra.ai/schemas/v1.2/` and `https://chitra.ai/schemas/v1.2.1/`.
- Use a JSON Schema validator that supports Draft 2020-12 with `$ref` resolution (Ajv for JS/TS, `jsonschema` 4.x+ for Python, gojsonschema for Go).
- Cache compiled schemas at MCP server startup. Re-fetch on `Last-Modified` change, not on every call.

### F.14.2 Schema versioning policy

- **v1.2.x** = additive patches. v1.2.1 introduces new artifact schemas and promotes one; existing v1.2 schemas unchanged except for the documented `performance_report` migration.
- **v1.3.x** = next minor release. Schema changes that are non-breaking can ship; breaking changes wait for v2.0.
- **Deprecation cycle**: 90-day grace on any field marked deprecated. Sanitizer warns for 60 days, blocks at 90.

### F.14.3 Cross-cutting concerns

- **Idempotency**: every artifact carries a stable `*_id`. Re-submitting the same artifact with the same hash is a no-op, not a duplicate.
- **Hashing**: `artifact_hash` in the envelope (v1.2 §F.0) is SHA-256 over the canonicalized JSON (sorted keys, no whitespace, UTF-8). Mismatched hash → reject.
- **Time**: all timestamps are ISO 8601 UTC. Local-time displays are presentation concerns, not contract concerns.
- **Currency**: all monetary fields are `_inr` suffixed and stored as integers (minor units where applicable for some platforms; full units otherwise — be explicit in field description).
- **Language codes**: ISO 639-1 two-letter where possible (`hi`, `ta`, `bn`); fall back to ISO 639-3 for languages without a two-letter code.

### F.14.4 Sanitizer performance

The Rule Matrix (§F.12) collapses sanitizer cost from O(rules × artifacts) to O(applicable_rules) per call. With ~30 rules across CHITRA today and an average artifact triggering 6–8 rules, a sanitizer call is consistently <200ms wall-clock for medium artifacts (under 100KB JSON), and <600ms for `motion_asset_registry` which is the heaviest.

If a tenant adds custom rules (deployment-specific brand-safety overlays, vertical-specific regulations like Pharma), they extend the same shape and slot into the matrix. The performance budget tolerates 100+ rules before it becomes a concern.

### F.14.5 Test strategy

- **Schema test corpus**: per-artifact, a set of canonical pass cases + canonical fail cases.
- **Sanitizer regression suite**: run on every rule registry update. Catches rule changes that flip a previously-passing canonical case.
- **Round-trip test**: an agent produces an artifact → envelope generated → receiver validates → sanitizer runs → all green. End-to-end on a synthetic brief, daily.

### F.14.6 What is intentionally **not** in v1.2.1

- A schema for `pitch_deck` — pitch decks are slide presentations, not data artifacts. They are referenced as `pitch_deck_uri` in `concept_slate`; their visual content is governed by `asset_registry` if individual assets are generated within CHITRA.
- A schema for `crisis_response_playbook` — referenced inside `content_calendar.community_management_protocol.escalation_tree`; promoting to a standalone schema is deferred to v1.3 when crisis-response gets dedicated tooling.
- A schema for `brand_guidelines` — these are tenant configuration, not handoff artifacts. They are input to many agents but not produced by any.

---

## §F.15 VERSION SUMMARY

| Version | Adds | Status |
|---|---|---|
| v1.0 | Architecture | Released |
| v1.1 | Agent scaffolds + Global Dynamic Resource Pack | Released |
| v1.2 | MCP tool integration + 6 handoff schemas + codified compliance ruleset + sanitizer | Released |
| **v1.2.1** | **4 additional handoff schemas + promoted `learnings_dossier` + rule-to-schema matrix + sanitizer examples** | **This document** |
| v1.3 (planned) | Eval harness; brand-safety partners; MMM connector | Planned |
| v1.4 | Closed-loop tenant learning automation | Planned |
| v2.0 | Federated learning across tenants | Planned |

---

*End of CHITRA v1.2.1 patch. Inherits v1.2 envelope, security wrapper, tool architecture, and §G rule definitions. Next scheduled refresh: 16 June 2026 — regulatory updates may add new rule IDs to §G and propagate through §F.12.*
