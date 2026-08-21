"""
audit_field_paths.py — the verbal_deck defect, generalised.

verbal_deck was a rule naming an artifact type that did not exist. The same
class of defect exists one level down: a rule naming a FIELD that does not
exist on the artifact it applies to. v1.3.5 §2.3 found one instance by hand
while building Drishti. This finds all of them.

METHOD
    Not by reading. The predicate layer's field accessor is wrapped, every rule
    is run against a probe artifact, and every path each rule requests is
    recorded. Those paths are then checked against the JSON Schema of each
    artifact type the rule applies to.

    A path is legitimate if it is (a) in the artifact's schema, (b) supplied by
    the context rather than the artifact, or (c) declared as derived in
    chitra_facets.py. Anything else is a rule reading a field nobody produces,
    which always evaluates falsy and therefore silently mis-enforces.

Run: python3 audit_field_paths.py
"""

import collections
import json
import os
import re
import sys

import chitra_predicates as P
import chitra_sanitizer as S

HERE = os.path.dirname(os.path.abspath(__file__))
from chitra_paths import spec_dir
SPEC_DIR = spec_dir()
SPEC_FILES = [
    "CHITRA-v1_2-Tool-Integration-Handoff-Compliance.md",
    "CHITRA-v1_2_1-Extended-Handoff-Schemas.md",
    "CHITRA-v1_2_2-Sweep-Patch.md",
    "CHITRA-v1_2_3-Final-Sweep-Patch.md",
]

ARTIFACT_TYPES = [
    "creative_brief", "concept_slate", "concept_bible", "asset_registry",
    "motion_asset_registry", "media_plan", "daily_optimization_log",
    "content_calendar", "social_post", "performance_report", "learnings_dossier",
]


def load_artifact_schemas():
    """Pull every artifact schema out of the specification set."""
    schemas = {}
    for fn in SPEC_FILES:
        # Resolve through the separator-tolerant finder. Joining a hardcoded
        # underscore filename onto the spec directory silently found nothing on
        # a machine whose documents use dots, so the census recovered zero
        # schemas, compared every rule against nothing, and reported PASS.
        # A gate that verifies nothing and reports green is the defect class
        # this gate exists to find.
        from chitra_paths import spec_file
        path = spec_file(fn, required=False)
        if path is None:
            continue
        text = open(path, encoding="utf-8").read()
        for block in re.findall(r"```json\n(.*?)\n```", text, re.S):
            m = re.search(r'"\$id"\s*:\s*"[^"]*/(\w+)\.json"', block)
            if not m or m.group(1) not in ARTIFACT_TYPES:
                continue
            try:
                schemas[m.group(1)] = json.loads(block)
            except json.JSONDecodeError:
                pass
    return schemas


def schema_paths(schema, prefix="", depth=0, out=None):
    """Flatten a JSON Schema into the set of dotted paths it defines."""
    out = set() if out is None else out
    if depth > 6 or not isinstance(schema, dict):
        return out
    props = schema.get("properties", {})
    for name, sub in props.items():
        path = f"{prefix}{name}"
        out.add(path)
        if isinstance(sub, dict):
            if sub.get("type") == "object" or "properties" in sub:
                schema_paths(sub, path + ".", depth + 1, out)
            if sub.get("type") == "array" and isinstance(sub.get("items"), dict):
                schema_paths(sub["items"], path + ".", depth + 1, out)
    return out


class Recorder:
    """Wraps chitra_predicates.get and records every path requested."""

    def __init__(self):
        self.original = P.get
        self.current_rule = None
        self.reads = collections.defaultdict(set)

    def __enter__(self):
        rec = self

        def spy(artifact, path, default=None):
            if rec.current_rule:
                rec.reads[rec.current_rule].add(path)
            return rec.original(artifact, path, default)

        P.get = spy
        # Predicates that captured `get` at module level still resolve through
        # the module attribute, so a single rebind covers all of them.
        return self

    def __exit__(self, *a):
        P.get = self.original


def probe_artifact():
    """An artifact that triggers as many branches as possible without
    satisfying anything, so predicates walk their full field list."""
    return {
        "product_category": "__probe__", "sector": "__probe__",
        "is_video": True, "is_audio": True, "duration_sec": 30,
        "format_is_ephemeral": False, "paid_partnership": True,
        "ai_risk_tier": "medium", "ai_label_present": True,
        "ai_persona_speaks": True, "uses_ai_persona": True,
        "uses_music": True, "uses_stock_imagery": True,
        "uses_celebrity_likeness": True, "music_license_territory": "IN",
        "placements": ["youtube_long"], "is_surrogate": True,
        "uses_doctor_endorsement": True, "health_claims_have_evidence_id": True,
        "references_competitor_mark": True, "contains_environmental_claim": True,
        "subject_consent_documented": True, "deepfake_label_present": True,
        "content_credentials_attached": True,
        "contains_market_risk_disclaimer": True,
        "influencer_qualification_credential_id": "probe",
        "consent_artifact_id": "probe", "opt_in_consent_artifact_id": "probe",
        "parental_consent_artifact_id": "probe",
        "targeting_bases": ["__probe__"], "audience_signals": [],
        "dark_patterns_present": [], "offer_mechanics": ["countdown_timer"],
        "referenced_tenant_ids": [], "competitor_archive_references": [],
        "claimed_conditions": [], "destination_country": "XX",
        "involves_cross_border_transfer": True,
        "data_retention_period_days": 1, "processing_log_retention_days": 400,
        "content": {"first_line": "probe", "caption": "probe"},
        "target_audience": {"includes_minors": True},
    }


class _Svc:
    def lookup(self, cid): return {"status": "probe", "valid": False,
                                   "designation": "probe"}
    def dmra_schedule_conditions(self): return ["probe"]
    def restricted_countries(self): return []
    def dgci_approved(self, pid): return False
    def trademark_clearance_passed(self, a): return False


def main():
    reg = S.RuleRegistry.load(
        schema_path=os.path.join(HERE, "rule_object.schema.json"))
    schemas = load_artifact_schemas()
    ctx = {"tenant": {"tenant_id": "t_probe", "dpdp_retention_policy_days": 730},
           "services": {k: _Svc() for k in ("consent_vault", "regdb",
                                            "legal_precheck", "credential_registry")},
           "cultural_risk_audits": {}, "brand": {}}

    print("=" * 78)
    print("FIELD-PATH CENSUS — the verbal_deck defect, one level down")
    print("=" * 78)
    print(f"\nArtifact schemas recovered from the specification: {len(schemas)}/"
          f"{len(ARTIFACT_TYPES)}")
    if not schemas:
        print("\n  FAIL: no artifact schemas were found, so this gate checked "
              "nothing.\n  A vacuous pass is worse than a failure. Ensure the "
              "specification documents\n  are in specs/ and re-run.")
        return 2
    missing_schemas = [t for t in ARTIFACT_TYPES if t not in schemas]
    if missing_schemas:
        print(f"  no schema found for: {', '.join(missing_schemas)}")

    paths = {t: schema_paths(s) for t, s in schemas.items()}

    art = probe_artifact()
    with Recorder() as rec:
        for rule in reg.rules:
            fn = rule.predicate
            rec.current_rule = rule.id
            try:
                fn(art, ctx)
            except Exception:
                pass
    rec.current_rule = None

    # Context-supplied and derived fields are legitimate non-schema reads.
    try:
        import chitra_facets as F
        declared = set(F.FACETS)
        required = set(F.REQUIRED)
        annotations = set(F.ANNOTATIONS)
        have_facets = True
    except ImportError:
        declared, required, annotations, have_facets = set(), set(), set(), False

    print(f"\nchitra_facets.py present: {have_facets}")
    print(f"Rules instrumented: {len(rec.reads)}")

    findings = collections.defaultdict(list)
    for rule in reg.rules:
        if rule.rule_class == "process":
            continue
        read = rec.reads.get(rule.id, set())
        for t in rule.applies_to:
            if t not in paths:
                continue
            for p in sorted(read):
                root = p.split(".")[0]
                if p in paths[t] or root in paths[t]:
                    continue
                if p in declared:
                    continue
                findings[p].append((rule.id, t))

    total = sum(len(v) for v in findings.values())
    print(f"\n{'-' * 78}")
    print(f"UNDECLARED FIELD READS: {len(findings)} distinct fields, "
          f"{total} rule/artifact pairs")
    print(f"{'-' * 78}\n")
    if not findings:
        print("  none. Every field a rule reads is either in the artifact schema "
              "or\n  declared in chitra_facets.FACETS.\n")
        read_all = set().union(*rec.reads.values()) if rec.reads else set()
        ann = sorted(read_all & annotations)
        req = sorted(read_all & required)
        print(f"  Declared annotations in use: {len(ann)}")
        print(f"  Of which required (absence yields INCONCLUSIVE, never a "
              f"falsy pass): {len(req)}")
        for a in req:
            print(f"      {a}")
        print()
        return 0

    print("  Every one of these is read by a rule and declared nowhere. Add it to")
    print("  chitra_facets.FACETS with a source, or stop reading it.\n")
    for p in sorted(findings, key=lambda x: (-len(findings[x]), x)):
        pairs = findings[p]
        rules = sorted({r for r, _ in pairs})
        types = sorted({t for _, t in pairs})
        print(f"  {p}")
        print(f"      read by {len(rules)} rule(s): {', '.join(rules[:5])}"
              f"{' ...' if len(rules) > 5 else ''}")
        print(f"      absent from {len(types)} artifact schema(s): "
              f"{', '.join(types[:5])}{' ...' if len(types) > 5 else ''}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
