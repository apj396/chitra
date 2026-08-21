"""
chitra_facets.py — the single seam between artifact schemas and rule vocabulary.

THE DEFECT THIS CLOSES
    Rules were written against a flat vocabulary (`artifact.consent_artifact_id`,
    `artifact.product_category`). Artifact schemas were written independently
    and are nested and differently named (`audience_targeting.consent_artifact_id`
    on social_post, `audiences[].consent_artifact_id` on media_plan). Neither
    document ever referenced the other.

    The census in audit_field_paths.py measured the gap: 61 distinct fields,
    279 rule/artifact pairs, every one of them reading a path nothing produces.

    This is verbal_deck one level down. verbal_deck was a rule naming an
    artifact type that did not exist; these are rules naming fields that do not
    exist. Same cause, same silence.

WHY IT WAS DANGEROUS RATHER THAN MERELY WRONG
    An absent field read with a falsy default is indistinguishable from a
    field that is present and false. `get(artifact, "is_surrogate", False)`
    returns False for an alcohol artifact that never declared the field, so
    ALCOHOL-SURROGATE-001 returned PASS. `claimed_conditions` absent meant
    DMRA-001 compared an empty set and returned PASS. Rules were passing
    artifacts because the fields they check do not exist.

THE FIX
    One declaration per facet, saying where it comes from:

      schema      a real path in that artifact type's schema, mapped per type
      context     a campaign-level or tenant-level fact, not an artifact field
      derived     computed from schema paths by a named function
      annotation  an upstream reviewer or agent annotation, absent by default

    And one rule about absence: a facet marked `required` that cannot be
    resolved is a MISS, not a False. A rule that reads a missing required facet
    cannot return PASS — the sanitizer converts it to INCONCLUSIVE and names
    the facet. Silence becomes a question instead of an approval.

    Agents no longer write their own adapters. There was one in Drishti; there
    would have been nine, each subtly different.
"""

import os
import re

SCHEMA, CONTEXT, DERIVED_SRC, ANNOTATION = "schema", "context", "derived", "annotation"


class Facet:
    __slots__ = ("name", "source", "paths", "derive", "required", "note")

    def __init__(self, name, source, paths=None, derive=None, required=False, note=""):
        self.name, self.source = name, source
        self.paths = paths or {}
        self.derive, self.required, self.note = derive, required, note


# --------------------------------------------------------------------------
# Derivations
# --------------------------------------------------------------------------

def _first(payload, *paths):
    for p in paths:
        v = _raw(payload, p)
        if v is not None:
            return v
    return None


def _raw(node, path):
    """Read a dotted path, stepping into single-element arrays where the schema
    nests a list (audiences[].consent_artifact_id and friends)."""
    cur = node
    for part in path.split("."):
        if isinstance(cur, list):
            vals = [c.get(part) for c in cur if isinstance(c, dict) and part in c]
            vals = [v for v in vals if v is not None]
            if not vals:
                return None
            cur = vals[0] if len(vals) == 1 else vals
            continue
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _flat_strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _flat_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _flat_strings(v)
    elif isinstance(node, str):
        yield node


def d_is_video(p, ctx, t):
    if t == "motion_asset_registry":
        return True
    if t == "social_post":
        return _raw(p, "content.asset_type") in ("video", "reel", "story_video")
    return None


def d_is_audio(p, ctx, t):
    if t == "motion_asset_registry":
        return bool(_raw(p, "audio_specs.voiceovers")) and not _raw(p, "cut_list")
    return False


def d_duration(p, ctx, t):
    return _first(p, "delivery_specs.duration_sec", "content.duration_sec",
                  "verbal_deck.scripts.duration_sec", "duration_sec")


def d_includes_minors(p, ctx, t):
    lo = _first(p, "target_audience.demographics.age_range.min",
                "audience_targeting.audience_min_age")
    if lo is None:
        lo = _raw(ctx.get("campaign", {}), "audience_min_age")
    return None if lo is None else lo < 18


def d_first_line(p, ctx, t):
    cap = _first(p, "content.first_line", "content.caption",
                 "verbal_deck.captions.text")
    if not cap:
        return None
    return cap.split("\n")[0] if isinstance(cap, str) else None


def d_caption(p, ctx, t):
    return _first(p, "content.caption", "verbal_deck.captions.text")


def d_referenced_tenants(p, ctx, t):
    v = _raw(p, "referenced_tenant_ids")
    if v is not None:
        return v
    tid = _raw(p, "tenant_id") or ctx.get("tenant", {}).get("tenant_id")
    return [tid] if tid else []


def d_targeting_bases(p, ctx, t):
    return _first(p, "audience_targeting.targeting_bases_used",
                  "audiences.targeting_bases_used", "targeting_bases")


def d_uses_music(p, ctx, t):
    return bool(_raw(p, "audio_specs.music_tracks")) or None


def d_music_licensed(p, ctx, t):
    tracks = _raw(p, "audio_specs.music_tracks")
    if tracks is None:
        return None
    tracks = tracks if isinstance(tracks, list) else [tracks]
    return all(bool(x.get("license_document_uri")) for x in tracks
               if isinstance(x, dict))


def d_music_territory(p, ctx, t):
    """Territory from the track list. 'global' only if every track is global."""
    tracks = _raw(p, "audio_specs.music_tracks")
    if tracks is None:
        return _raw(p, "music_license_territory")
    tracks = tracks if isinstance(tracks, list) else [tracks]
    terrs = set()
    for x in tracks:
        if isinstance(x, dict):
            v = x.get("rights_cleared_for_territories")
            terrs.update(v if isinstance(v, list) else [v] if v else [])
    if not terrs:
        return None
    return "global" if terrs == {"global"} else sorted(terrs)[0]


def d_contained_concepts(p, ctx, t):
    """Concepts held by a container artifact, whatever it calls the list.

    Cultural audits are concept-scoped, so a container has to resolve as the
    aggregate of what it holds. Different containers name the list differently,
    and that difference is a schema detail the rules should not carry.
    """
    for key in ("concepts_approved", "concepts", "concept_variants"):
        v = _raw(p, key)
        if isinstance(v, list) and v:
            return v
    return None


def d_subject_consent(p, ctx, t):
    segs = _raw(p, "ai_content_metadata.deepfake_segments")
    if segs is None:
        return None
    segs = segs if isinstance(segs, list) else [segs]
    return all(bool(x.get("subject_consent_uri")) for x in segs
               if isinstance(x, dict))


def d_deepfake_label(p, ctx, t):
    segs = _raw(p, "ai_content_metadata.deepfake_segments")
    if segs is None:
        return None
    segs = segs if isinstance(segs, list) else [segs]
    return all(bool(x.get("deepfake_label_visible")) for x in segs
               if isinstance(x, dict))


def d_content_credentials(p, ctx, t):
    return _first(p, "ai_content_metadata.content_credentials_embedded",
                  "exports.content_credentials")


def d_ai_label_present(p, ctx, t):
    return _first(p, "ai_persona.ai_label_visible",
                  "exports.asci_disclosure_embedded")


def d_ai_risk_tier(p, ctx, t):
    tier = _raw(p, "ai_risk_tier")
    if tier is not None:
        return tier
    ai = _first(p, "ai_persona.uses_ai_generated_likeness",
                "ai_content_metadata.any_segment_ai_generated",
                "exports.ai_generated")
    if ai is None:
        return None
    # Defaulting upward: an artifact that declares AI use without a tier is
    # treated as medium, so the label requirement applies rather than lapses.
    return "medium" if ai else "none"


def d_consent_artifact_id(p, ctx, t):
    return _first(p, "audience_targeting.consent_artifact_id",
                  "audiences.consent_artifact_id", "consent_artifact_id")


def d_placements(p, ctx, t):
    return _first(p, "delivery_specs.placements", "channels.channel", "placements")


def d_copy_text(p, ctx, t):
    return " ".join(_flat_strings(p)).lower()


# --------------------------------------------------------------------------
# The register
# --------------------------------------------------------------------------

def _f(*a, **k):
    f = Facet(*a, **k)
    return f


FACETS = {f.name: f for f in [
    # ---- campaign-level facts. Not artifact fields, and never were. --------
    _f("product_category", CONTEXT, required=True,
       note="Campaign-level. Read from context.campaign, not the artifact."),
    _f("sector", CONTEXT, required=True, note="Campaign-level."),
    _f("concept_id", CONTEXT,
       note="Present on concept_bible and motion_asset_registry; campaign "
            "context supplies it for the rest."),
    _f("channel", CONTEXT, note="Campaign-level delivery channel."),
    _f("platform_family", CONTEXT),
    _f("product_id", CONTEXT),
    _f("destination_country", CONTEXT),
    # ADR-020. Campaign-level, like every other geography fact.
    # Neither is a required facet: the requirement is conditional, and a facet
    # flag cannot express "required only when geography is present". Marking
    # geography required sent every artifact without one to human review.
    # CHITRA-RESEARCH-COVERAGE-001 raises the question itself instead.
    _f("geography", CONTEXT, note="Regions the campaign runs in."),
    _f("research_coverage", CONTEXT,
       note="Regions the audience research covers. Absence is a question when "
            "geography is present, which the predicate raises."),
    _f("research_coverage_waivers", CONTEXT,
       note="Named, dated acceptances of an uncovered region."),

    # ---- derived from real schema paths -----------------------------------
    _f("is_video", DERIVED_SRC, derive=d_is_video),
    _f("is_audio", DERIVED_SRC, derive=d_is_audio),
    _f("duration_sec", DERIVED_SRC, derive=d_duration),
    _f("target_audience.includes_minors", DERIVED_SRC, derive=d_includes_minors),
    _f("content.first_line", DERIVED_SRC, derive=d_first_line),
    _f("content.caption", DERIVED_SRC, derive=d_caption),
    _f("referenced_tenant_ids", DERIVED_SRC, derive=d_referenced_tenants),
    # Not required: DPDP-SENSITIVE-TARGETING-001 is a presence test for
    # forbidden bases, and an artifact with no targeting genuinely has none.
    _f("targeting_bases", DERIVED_SRC, derive=d_targeting_bases),
    _f("uses_music", DERIVED_SRC, derive=d_uses_music),
    _f("music_license_documented", DERIVED_SRC, derive=d_music_licensed),
    _f("music_license_territory", DERIVED_SRC, derive=d_music_territory),
    _f("subject_consent_documented", DERIVED_SRC, derive=d_subject_consent),
    _f("deepfake_label_present", DERIVED_SRC, derive=d_deepfake_label),
    _f("content_credentials_attached", DERIVED_SRC, derive=d_content_credentials),
    _f("ai_label_present", DERIVED_SRC, derive=d_ai_label_present),
    _f("ai_risk_tier", DERIVED_SRC, derive=d_ai_risk_tier),
    # Not required: DPDP-CONSENT-001 already fails explicitly and usefully on
    # an absent consent id. A miss here would replace a clear block with a
    # vaguer inconclusive.
    _f("consent_artifact_id", DERIVED_SRC, derive=d_consent_artifact_id),
    _f("placements", DERIVED_SRC, derive=d_placements),
    _f("contained_concepts", DERIVED_SRC, derive=d_contained_concepts,
       note="Container artifacts aggregate their contained concept audits."),
    _f("copy_text", DERIVED_SRC, derive=d_copy_text),

    # ---- required annotations. Absence is a question, never a negative. ----
    # Each of these was silently returning False and passing artifacts.
    _f("claimed_conditions", ANNOTATION, required=True,
       note="DMRA-001 passed every health claim because this was always absent."),
    _f("directly_promotes_alcohol", ANNOTATION, required=True,
       note="ALCOHOL-SURROGATE-001 passed every alcohol artifact on this."),
    _f("is_surrogate", ANNOTATION, required=True),
    _f("uses_alcohol_consumption_imagery", ANNOTATION, required=True),
    _f("health_claims_have_evidence_id", ANNOTATION, required=True),
    _f("uses_doctor_endorsement", ANNOTATION),
    _f("special_ad_category_declared_in_meta", ANNOTATION, required=True),
    _f("transfer_basis_documented", ANNOTATION, required=True),
    # ADR-013. Not required: ALCOHOL-SURROGATE-001 fails explicitly and
    # usefully on absence, which is the whole point of a default block.
    _f("ca_attestation_id", ANNOTATION,
       note="Independent CA certificate id lifting the alcohol block."),
    # ADR-018. Deliberately NOT required, after measurement.
    # Marking it required sent every artifact with no declared people to human
    # review, which is every artifact, and defeats the rule. The residual gap
    # is real and is recorded rather than hidden: IP-REAL-PERSON-LIKENESS-001
    # enforces on DECLARED people only. An undeclared face in a crowd shot is
    # not caught by the sanitizer and is covered at asset review instead.
    _f("identifiable_real_persons", ANNOTATION,
       note="Enforces on declared people only. Undeclared faces are an asset-"
            "review responsibility, not a sanitizer one. See ADR-018."),
    # Same reasoning: each predicate fails explicitly on absence, which is a
    # better answer than a miss.
    _f("opt_in_consent_artifact_id", ANNOTATION),
    _f("parental_consent_artifact_id", ANNOTATION),
    _f("influencer_qualification_credential_id", ANNOTATION),
    _f("uses_targeted_advertising_directed_at_minors", ANNOTATION),
    _f("audience_signals", ANNOTATION),
    _f("data_retention_period_days", ANNOTATION),
    _f("processing_log_retention_days", ANNOTATION),
    _f("competitor_archive_references", ANNOTATION),
    _f("contains_rera_registration_number", ANNOTATION),
    _f("platform_native_label", ANNOTATION),
    _f("dark_patterns_present", ANNOTATION),
    _f("disclosure_visible_duration_sec", ANNOTATION),
    _f("disclosure_visible_throughout", ANNOTATION),
    _f("format_is_ephemeral", ANNOTATION),
    _f("verbal_disclosure_at_segment_start", ANNOTATION),
    _f("ai_label_accurately_describes_use", ANNOTATION),
    _f("depicts_fabricated_endorsement", ANNOTATION),
    _f("depicts_fake_authority_figure", ANNOTATION),
    _f("claim_substantiated_with_third_party_certification", ANNOTATION),
    _f("claim_quantified_with_specific_metric", ANNOTATION),
    _f("claim_qualified_with_scope_disclosure", ANNOTATION),
    _f("guarantees_specific_exam_rank_or_marks", ANNOTATION),
    _f("uses_fear_of_failure_appeals_to_parents", ANNOTATION),
    _f("uses_unverified_testimonials_of_minors", ANNOTATION),

    # ---- cultural annotations ---------------------------------------------
    # Not required: the cultural risk audit is the gate (v1.3.5 §1), and these
    # are escalation hints from a reviewer. Absent means "the audit decides",
    # which is already the behaviour.
    _f("mocks_religion", ANNOTATION),
    _f("uses_caste_stereotypes", ANNOTATION),
    _f("implies_caste_hierarchy", ANNOTATION),
    _f("reinforces_harmful_gender_stereotypes", ANNOTATION),
    _f("uses_misogyny_for_humor", ANNOTATION),
    _f("uses_body_shaming", ANNOTATION),
    _f("mocks_regional_accent_for_humor", ANNOTATION),
    _f("implies_regional_hierarchy", ANNOTATION),
    _f("takes_partisan_political_position", ANNOTATION),
    _f("references_living_political_figure_unflatteringly", ANNOTATION),
]}

DERIVED = {n for n, f in FACETS.items() if f.source == DERIVED_SRC}
CONTEXT_SUPPLIED = {n for n, f in FACETS.items() if f.source == CONTEXT}
ANNOTATIONS = {n for n, f in FACETS.items() if f.source == ANNOTATION}
REQUIRED = {n for n, f in FACETS.items() if f.required}


class FacetView:
    """Read-through view over an artifact payload that resolves rule vocabulary.

    Records a miss whenever a rule reads a required facet that cannot be
    resolved from the payload, the context, or a derivation. The sanitizer
    turns a miss into INCONCLUSIVE rather than letting a falsy default pass.
    """

    def __init__(self, payload, artifact_type, context):
        self.payload = payload or {}
        self.artifact_type = artifact_type
        self.context = context or {}
        self.misses = set()

    def resolve(self, path, default=None):
        # 1. literal path on the payload always wins, so hand-built artifacts
        #    and test fixtures keep working.
        v = _raw(self.payload, path)
        if v is not None:
            return v

        facet = FACETS.get(path)
        if facet is None:
            return default

        if facet.source == CONTEXT:
            v = _raw(self.context.get("campaign", {}), path) \
                or _raw(self.context.get("tenant", {}), path)
            if v is not None:
                return v
        elif facet.source == DERIVED_SRC and facet.derive:
            try:
                v = facet.derive(self.payload, self.context, self.artifact_type)
            except Exception:
                v = None
            if v is not None:
                return v

        if facet.required:
            self.misses.add(path)
        return default

    def take_misses(self):
        m, self.misses = set(self.misses), set()
        return m

    # dict-ish surface so predicates that touch the artifact directly still work
    def __contains__(self, k):
        return k in self.payload

    def get(self, k, default=None):
        return self.resolve(k, default)

    def items(self):
        return self.payload.items()

    def values(self):
        return self.payload.values()

    def keys(self):
        return self.payload.keys()

    def __getitem__(self, k):
        return self.payload[k]

    def __iter__(self):
        return iter(self.payload)
