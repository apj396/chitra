"""
test_services.py — tests for the ADR implementations of 12 August 2026.

Covers ADR-001, 003, 006, 007, 010, 011, 013, 018.
Run: python3 test_services.py
"""

import json
import os
import sys

import chitra_cultural_assistant as CA
import chitra_eval_extras as EX
import chitra_sanitizer as S
import chitra_services as SV

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


REG = S.RuleRegistry.load(schema_path=os.path.join(HERE, "rule_object.schema.json"))


def ctx(product_category=None, **over):
    c = {"tenant": {"tenant_id": "t_001", "dpdp_retention_policy_days": 730},
         "campaign": {"product_category": product_category} if product_category else {},
         "services": SV.default_services(),
         "cultural_risk_audits": {}}
    c.update(over)
    return c


# -------------------------------------------------------------- ADR-003
def test_adr003_no_carve_out():
    art = {"targeting_bases": ["sexual_orientation", "geography"]}
    c = ctx("personal_care")
    c["brand"] = {"lgbtq_affirmative": True}
    r = S.sanitize("media_plan", art, c, REG)
    ids = [v["rule_id"] for v in r.violations]
    check("ADR-003: affirmative brand no longer buys an exception",
          "DPDP-SENSITIVE-TARGETING-001" in ids, str(ids))

    art2 = {"targeting_bases": ["health_condition"]}
    c2 = ctx("healthcare")
    c2["brand"] = {"legitimate_health_service": True}
    r2 = S.sanitize("media_plan", art2, c2, REG)
    check("ADR-003: health-service carve-out also removed",
          "DPDP-SENSITIVE-TARGETING-001" in [v["rule_id"] for v in r2.violations])

    ok = S.sanitize("media_plan", {"targeting_bases": ["geography"]},
                    ctx("personal_care"), REG)
    check("ADR-003: ordinary targeting still passes",
          "DPDP-SENSITIVE-TARGETING-001" not in [v["rule_id"] for v in ok.violations])


# -------------------------------------------------------------- ADR-013
def test_adr013_ca_attestation_override():
    base = {"directly_promotes_alcohol": False, "is_surrogate": True,
            "uses_alcohol_consumption_imagery": False,
            "exports": {"filename": "hero.jpg"}}
    c = ctx("alcohol")

    r = S.sanitize("asset_registry", base, c, REG)
    check("ADR-013: blocks by default with no attestation",
          "ALCOHOL-SURROGATE-001" in [v["rule_id"] for v in r.violations])

    r2 = S.sanitize("asset_registry", dict(base, ca_attestation_id="EXAMPLE-CA-0001"),
                    c, REG)
    check("ADR-013: valid CA attestation lifts the block",
          "ALCOHOL-SURROGATE-001" not in [v["rule_id"] for v in r2.violations],
          str([v["rule_id"] for v in r2.violations]))

    r3 = S.sanitize("asset_registry", dict(base, ca_attestation_id="EXAMPLE-QUAL-0001"),
                    c, REG)
    check("ADR-013: a qualification credential is not a CA attestation",
          "ALCOHOL-SURROGATE-001" in [v["rule_id"] for v in r3.violations])

    r4 = S.sanitize("asset_registry",
                    dict(base, ca_attestation_id="EXAMPLE-CA-0001",
                         uses_alcohol_consumption_imagery=True), c, REG)
    check("ADR-013: attestation does not license consumption imagery",
          "ALCOHOL-SURROGATE-001" in [v["rule_id"] for v in r4.violations])

    r5 = S.sanitize("asset_registry", dict(base, directly_promotes_alcohol=True,
                                           ca_attestation_id="EXAMPLE-CA-0001"), c, REG)
    check("ADR-013: attestation does not license direct promotion",
          "ALCOHOL-SURROGATE-001" in [v["rule_id"] for v in r5.violations])


# -------------------------------------------------------------- ADR-010
def test_adr010_dmra():
    db = SV.RegDB()
    terms = db.dmra_schedule_conditions()
    check("ADR-010: Schedule loaded with all 54 conditions",
          len([t for t in terms]) > 54, f"{len(terms)} terms")
    check("ADR-010: Schedule flagged unverified against the Gazette",
          not db.dmra_verified())

    art = {"contains_health_claim": True, "health_claims_have_evidence_id": True,
           "content": {"caption": "Our capsule cures diabetes in 30 days."}}
    r = S.sanitize("asset_registry", art, ctx("supplements"), REG)
    check("ADR-010: catches a Schedule condition in the copy, not just a field",
          "DMRA-001" in [v["rule_id"] for v in r.violations] or
          "DMRA-001" in [w["rule_id"] for w in r.warnings] or
          any(e["rule_id"] == "DMRA-001" for e in r.skipped_shadow),
          str([v["rule_id"] for v in r.violations]))

    art2 = {"contains_health_claim": True, "health_claims_have_evidence_id": True,
            "content": {"caption": "Grow taller in six weeks, guaranteed."}}
    r2 = S.sanitize("asset_registry", art2, ctx("supplements"), REG)
    found = ([v["rule_id"] for v in r2.violations] +
             [e["rule_id"] for e in r2.skipped_shadow])
    check("ADR-010: synonym expansion catches 'grow taller' for stature",
          "DMRA-001" in found, str(found))


# -------------------------------------------------------------- ADR-018
def test_adr018_real_person_likeness():
    art = {"identifiable_real_persons": [{"name": "passer-by in frame 4"}],
           "exports": {"filename": "hero.jpg"}}
    r = S.sanitize("asset_registry", art, ctx("personal_care"), REG)
    check("ADR-018: identifiable person without a release blocks",
          "IP-REAL-PERSON-LIKENESS-001" in [v["rule_id"] for v in r.violations],
          str([v["rule_id"] for v in r.violations]))

    ok = {"identifiable_real_persons": [
        {"name": "passer-by", "release_document_uri": "s3://releases/1.pdf"}],
        "exports": {"filename": "hero.jpg"}}
    r2 = S.sanitize("asset_registry", ok, ctx("personal_care"), REG)
    check("ADR-018: a signed release clears it",
          "IP-REAL-PERSON-LIKENESS-001" not in [v["rule_id"] for v in r2.violations])

    pub = {"identifiable_real_persons": [
        {"name": "a minister", "is_public_figure": True, "editorial_context": True}],
        "exports": {"filename": "hero.jpg"}}
    r3 = S.sanitize("asset_registry", pub, ctx("personal_care"), REG)
    check("ADR-018: public figure in editorial context is exempt",
          "IP-REAL-PERSON-LIKENESS-001" not in [v["rule_id"] for v in r3.violations])


# -------------------------------------------------------------- ADR-007
def test_adr007_hitl_routing():
    router = SV.HITLRouter(REG)
    check("ADR-007: DPDP routes to the DPO",
          router.queue_for("DPDP-CONSENT-001") == "dpo",
          router.queue_for("DPDP-CONSENT-001"))
    check("ADR-007: cultural routes to cultural review",
          router.queue_for("CULTURAL-CASTE-001") == "cultural_review")
    check("ADR-007: IP routes to legal",
          router.queue_for("IP-REAL-PERSON-LIKENESS-001") == "legal",
          router.queue_for("IP-REAL-PERSON-LIKENESS-001"))
    check("ADR-007: platform ToS routes to ad ops",
          router.queue_for("PLATFORM-TOS-META-PLACEMENT-001") == "ad_ops")

    art = {"targeting_bases": ["caste"], "channel": "whatsapp"}
    r = S.sanitize("media_plan", art, ctx("personal_care"), REG)
    items = router.route(r, "media_plan", "camp_1")
    queues = [i.queue for i in items]
    check("ADR-007: one result splits across queues", len(set(queues)) >= 2,
          str(queues))
    check("ADR-007: tightest SLA first",
          items == sorted(items, key=lambda i: i.sla_hours),
          str([(i.queue, i.sla_hours) for i in items]))
    check("ADR-007: a consent-class failure is not in the cultural queue",
          all("DPDP-CONSENT-001" not in i.rule_ids
              for i in items if i.queue == "cultural_review"))


# -------------------------------------------------------------- ADR-001
def test_adr001_assembler_has_no_verdict():
    a = CA.CulturalAssistant(
        register={"religion": ["Festival depictions: avoid deity as product mascot"]},
        precedent={"religion": ["ASCI upheld complaint, 2024, deity in a discount ad"]})
    art = {"concept_id": "c1",
           "insight": "A family lights diyas at the temple before the festival meal."}
    brief = a.assemble(art, ctx("personal_care"))
    d = brief.to_dict()
    check("ADR-001: detects the religion axis from content",
          "religion" in brief.axes_touched, str(brief.axes_touched))
    check("ADR-001: carries register entries and precedent",
          d["findings"][0]["register_entries"] and d["findings"][0]["precedent"])
    check("ADR-001: issues no verdict", d["verdict"] is None)
    check("ADR-001: emits a question, not an assessment",
          d["findings"][0]["question_for_reviewer"].endswith("?"))
    text = json.dumps(d).lower()
    for word in ("acceptable", "approved", "low risk", "high risk", "safe to"):
        check(f"ADR-001: never says '{word}'", word not in text)
    check("ADR-001: names no persona or perspective",
          "as a" not in text and "perspective of" not in text)

    clean = a.assemble({"concept_id": "c1", "insight": "A detergent dries faster."},
                       ctx("personal_care"))
    check("ADR-001: no axes on neutral content", not clean.axes_touched)


# -------------------------------------------------------------- ADR-011/014
def test_adr014_variance_and_adr011_panel():
    sc = EX.HeadlineVarianceScorer()
    padded = [f"Built for clothes that cannot dry {x}" for x in
              ["outside", "outdoors", "in the rain", "on the balcony", "in monsoon",
               "in the wet", "without sun", "indoors", "in humidity", "in damp",
               "in the damp air", "without sunlight", "in wet weather",
               "in the rains", "in monsoon season"]]
    varied = ["Built for clothes that cannot dry outside",
              "The monsoon is the problem, not the powder",
              "Your balcony has been out of service since June",
              "Rain does not wash out. It settles in.",
              "Four days indoors and everyone can tell",
              "We made a detergent for weather, not for stains",
              "Sourness has a season", "When the sun clocks off, we clock in",
              "Some smells are the sky's fault", "Dry season logic fails in July",
              "A clean shirt should not smell like a cupboard",
              "Monsoon: the only stain you cannot see",
              "Chairs are not clotheslines", "Humidity keeps the score",
              "Your washing is fine. Your air is not."]
    check("ADR-014: padding scores weak",
          sc.rubric_entry(padded)["level"] == "weak")
    check("ADR-014: genuine spread scores excellent",
          sc.rubric_entry(varied)["level"] == "excellent")
    check("ADR-014: both arrays satisfy the schema minimum",
          len(padded) == 15 and len(varied) == 15,
          "the point: the minimum alone cannot tell them apart")

    panel = [{"model": "m-a", "family": "fam1"}, {"model": "m-b", "family": "fam2"},
             {"model": "m-c", "family": "fam3"}]
    try:
        EX.JudgePanelHealthCheck(panel).gate()
        check("ADR-011: refuses to run unverified", False, "gate passed with no prober")
    except RuntimeError:
        check("ADR-011: refuses to run unverified", True)
    try:
        EX.JudgePanelHealthCheck(panel, prober=lambda m: m != "m-b").gate()
        check("ADR-011: refuses on a retired model", False)
    except RuntimeError:
        check("ADR-011: refuses on a retired model", True)
    two = [{"model": "m-a", "family": "fam1"}, {"model": "m-b", "family": "fam1"},
           {"model": "m-c", "family": "fam2"}]
    try:
        EX.JudgePanelHealthCheck(two, prober=lambda m: True).gate()
        check("ADR-011: enforces three independent families", False)
    except RuntimeError:
        check("ADR-011: enforces three independent families", True)
    h = EX.JudgePanelHealthCheck(panel, prober=lambda m: True).gate()
    check("ADR-011: a healthy verified panel passes", h.healthy)


# -------------------------------------------------------------- legal-precheck
def test_legal_precheck_clears_the_permanent_review_item():
    art = {"concepts_approved": [{"title": "The Weather Did It"}],
           "exports": {"filename": "hero.jpg"}}
    r = S.sanitize("asset_registry", art, ctx("personal_care"), REG)
    incl = [i["rule_id"] for i in r.inconclusive]
    check("IP-TRADEMARK-001 no longer goes inconclusive by default",
          "IP-TRADEMARK-001" not in incl, str(incl))

    colliding = {"concepts_approved": [{"title": "Rain Ready"}],
                 "exports": {"filename": "hero.jpg"}}
    r2 = S.sanitize("asset_registry", colliding, ctx("personal_care"), REG)
    v = next((x for x in r2.violations if x["rule_id"] == "IP-TRADEMARK-001"), None)
    check("a registered rival mark is caught", v is not None,
          str([x["rule_id"] for x in r2.violations]))
    check("the violation names the mark and its owner",
          v and "Rain Ready" in v["message"] and "RivalCo" in v["message"],
          v["message"] if v else "")

    own = {"concepts_approved": [{"title": "Sundara Monsoon"}],
           "exports": {"filename": "hero.jpg"}}
    r3 = S.sanitize("asset_registry", own, ctx("personal_care"), REG)
    check("a tenant's own mark is not a collision",
          "IP-TRADEMARK-001" not in [x["rule_id"] for x in r3.violations])

    near = {"concepts_approved": [{"title": "monsoon-fresh!"}],
            "exports": {"filename": "hero.jpg"}}
    r4 = S.sanitize("asset_registry", near, ctx("personal_care"), REG)
    check("near matches are caught through punctuation and spacing",
          "IP-TRADEMARK-001" in [x["rule_id"] for x in r4.violations],
          str([x["rule_id"] for x in r4.violations]))

    check("an absent service still fails closed",
          "IP-TRADEMARK-001" in [i["rule_id"] for i in
                                 S.sanitize("asset_registry", art,
                                            dict(ctx("personal_care"),
                                                 services={}), REG).inconclusive])


def test_kill_tag_enum_records_rank_outs_honestly():
    import json as _j
    d = _j.load(open(os.path.join(HERE, "concept_slate.schema.json"), encoding="utf-8"))
    enum = d["properties"]["concepts_killed"]["items"]["properties"]["kill_tag"]["enum"]
    check("ranked_out_of_slate added to the enum", "ranked_out_of_slate" in enum,
          str(enum))


def test_adr020_research_coverage_invariant():
    """ADR-020. A region the research does not cover cannot ship."""
    def c(geo, cov, w=None):
        x = ctx()
        x["campaign"] = {"geography": geo, "research_coverage": cov,
                         "research_coverage_waivers": w or []}
        return x

    def blocked(geo, cov, w=None):
        r = S.sanitize("creative_brief", {}, c(geo, cov, w), REG)
        return next((v for v in r.violations
                     if v["rule_id"] == "CHITRA-RESEARCH-COVERAGE-001"), None)

    v = blocked(["Maharashtra", "Tamil Nadu"], ["Maharashtra"])
    check("ADR-020: an uncovered region blocks", v is not None)
    check("ADR-020: the uncovered region is named",
          v and "tamil nadu" in v["message"].lower(), v["message"] if v else "")
    check("ADR-020: it routes to the brand owner, who owns the call",
          SV.HITLRouter(REG).queue_for("CHITRA-RESEARCH-COVERAGE-001")
          == "brand_owner")

    check("ADR-020: full coverage passes",
          blocked(["Maharashtra", "Karnataka"],
                  ["Maharashtra", "Karnataka"]) is None)

    v2 = blocked(["Maharashtra", "Tamil Nadu"], ["Maharashtra"],
                 [{"region": "Tamil Nadu", "rationale": "client wants reach"}])
    check("ADR-020: an unsigned waiver does not lift the block", v2 is not None)
    check("ADR-020: and says why a waiver needs a name",
          v2 and "names no approver" in v2["message"], v2["message"] if v2 else "")

    check("ADR-020: a waiver naming an approver and a date lifts it",
          blocked(["Maharashtra", "Tamil Nadu"], ["Maharashtra"],
                  [{"region": "Tamil Nadu", "approved_by": "A Patil",
                    "approved_on": "2026-08-16",
                    "rationale": "accepted risk"}]) is None)

    check("ADR-020: a campaign with no geography is not blocked",
          blocked([], []) is None)


# -------------------------------------------------------------- consent vault
def cctx(vault=True, **over):
    c = ctx(**over)
    if vault:
        c["services"] = SV.default_services()
    else:
        c["services"] = {}
    return c


def consent_result(art, vault=True, artifact_type="media_plan", rule="DPDP-CONSENT-001"):
    r = S.sanitize(artifact_type, art, cctx(vault), REG)
    return (next((v for v in r.violations if v["rule_id"] == rule), None),
            next((i for i in r.inconclusive if i["rule_id"] == rule), None))


def test_consent_is_bound_not_merely_present():
    base = {"uses_custom_audience": True,
            "consent_artifact_id": "EXAMPLE-CONSENT-0001",
            "processing_purpose": "retargeting"}
    v, i = consent_result(base)
    check("valid, purpose-matched consent passes", v is None and i is None,
          str(v or i))

    v, _ = consent_result(dict(base, processing_purpose="lookalike"))
    check("consent for one purpose does not authorise another", v is not None)
    check("and the message names both purposes",
          v and "retargeting" in v["message"] and "lookalike" in v["message"],
          v["message"] if v else "")


def test_withdrawn_and_expired_consent_block():
    for cid, word in (("EXAMPLE-CONSENT-0004-WITHDRAWN", "withdrawn"),
                      ("EXAMPLE-CONSENT-0005-EXPIRED", "expired")):
        v, _ = consent_result({"uses_custom_audience": True,
                               "consent_artifact_id": cid,
                               "processing_purpose": "retargeting"})
        check(f"{word} consent blocks", v is not None)
        check(f"and says it is {word}", v and word in v["message"],
              v["message"] if v else "")


def test_expiry_is_computed_at_read_time():
    """Nothing sweeps the file, so a lapsed record must read as expired."""
    vault = SV.ConsentVault(records={
        "c": {"status": "valid", "purpose": "p",
              "expires_at": "2026-01-01T00:00:00"}})
    check("a lapsed record reads as expired",
          vault.lookup("c")["status"] == "expired",
          vault.lookup("c")["status"])


def test_unverifiable_consent_blocks_rather_than_routing_to_a_human():
    """Stricter than every other service dependency, deliberately.

    A reviewer looking at an inconclusive trademark check can go and read the
    register. A reviewer looking at unverifiable consent cannot conjure
    consent that may never have been given.
    """
    art = {"uses_custom_audience": True,
           "consent_artifact_id": "EXAMPLE-CONSENT-0001",
           "processing_purpose": "retargeting"}
    v, i = consent_result(art, vault=False)
    check("no vault configured blocks", v is not None, str(v))
    check("and does not route to human review", i is None, str(i))
    check("and says why a human cannot resolve it",
          v and "cannot supply consent" in (v["suggested_fix"] or ""),
          v["suggested_fix"] if v else "")

    class Down(SV.ConsentVault):
        def __init__(self):
            super().__init__(records={})
        def is_authorised(self, *a, **k):
            raise SV.ConsentUnavailable("consent vault unreachable")

    c = cctx()
    c["services"]["consent_vault"] = Down()
    r = S.sanitize("media_plan", art, c, REG)
    v2 = next((x for x in r.violations if x["rule_id"] == "DPDP-CONSENT-001"), None)
    check("an unreachable vault blocks too", v2 is not None)
    check("and is not sent to review",
          not any(x["rule_id"] == "DPDP-CONSENT-001" for x in r.inconclusive))


def test_children_require_verifiable_parental_consent():
    art = {"target_audience": {"includes_minors": True},
           "targeting_bases": ["geography"],
           "parental_consent_artifact_id": "EXAMPLE-CONSENT-0003"}
    v, i = consent_result(art, rule="DPDP-CHILDREN-001")
    check("verifiable parental consent passes", v is None and i is None,
          str(v or i))

    art2 = dict(art, parental_consent_artifact_id="EXAMPLE-CONSENT-0001")
    v2, _ = consent_result(art2, rule="DPDP-CHILDREN-001")
    check("ordinary self consent does not cover a minor", v2 is not None)
    check("and the message names the required type",
          v2 and "verifiable_parental" in v2["message"], v2["message"] if v2 else "")


def test_whatsapp_optin_is_channel_bound():
    art = {"channel": "whatsapp", "template_pre_approved": True,
           "respects_24h_utility_window": True,
           "opt_in_consent_artifact_id": "EXAMPLE-CONSENT-0002"}
    v, _ = consent_result(art, rule="PLATFORM-TOS-WHATSAPP-001")
    check("whatsapp-channel opt-in passes", v is None, str(v))

    v2, _ = consent_result(dict(art, opt_in_consent_artifact_id="EXAMPLE-CONSENT-0001"),
                           rule="PLATFORM-TOS-WHATSAPP-001")
    check("a meta-channel consent does not authorise a whatsapp send",
          v2 is not None)


def test_identifiers_are_never_stored_raw():
    import json as _j
    raw = _j.load(open(os.path.join(HERE, "consent_records.json"),
                       encoding="utf-8"))
    # Scope the scan to the records. The file's own explanatory note mentions
    # phone numbers, and a test that fails on documentation teaches people to
    # stop documenting.
    blob = _j.dumps(raw["consents"]).lower()
    forbidden = ("principal_identifier", "phone", "email", "aadhaar",
                 "msisdn", "account_number")
    hits = [w for w in forbidden if w in blob]
    check("no record carries a raw identifier field", not hits, str(hits))
    for cid, rec in raw["consents"].items():
        if rec.get("principal_hash"):
            check(f"{cid} stores a 64-char hash",
                  len(rec["principal_hash"]) == 64, rec["principal_hash"][:12])
    h = SV.ConsentVault.hash_identifier("+91 98765 43210")
    check("hashing normalises before digesting",
          h == SV.ConsentVault.hash_identifier("+91 98765 43210 "))


def test_withdrawal_is_a_state_not_a_deletion():
    v = SV.ConsentVault(records={"c": {"status": "valid", "purpose": "p",
                                       "principal_hash": "x" * 64}})
    v.withdraw("c", "data principal request")
    rec = v.lookup("c")
    check("the record survives withdrawal", rec is not None)
    check("marked withdrawn", rec["status"] == "withdrawn")
    check("with a timestamp", bool(rec.get("withdrawn_at")))
    check("and the reason kept, because a Board inquiry asks",
          rec.get("withdrawal_reason") == "data principal request")


def main():
    for fn in (test_consent_is_bound_not_merely_present,
               test_withdrawn_and_expired_consent_block,
               test_expiry_is_computed_at_read_time,
               test_unverifiable_consent_blocks_rather_than_routing_to_a_human,
               test_children_require_verifiable_parental_consent,
               test_whatsapp_optin_is_channel_bound,
               test_identifiers_are_never_stored_raw,
               test_withdrawal_is_a_state_not_a_deletion,
               test_adr020_research_coverage_invariant,
               test_legal_precheck_clears_the_permanent_review_item,
               test_kill_tag_enum_records_rank_outs_honestly,
               test_adr003_no_carve_out, test_adr013_ca_attestation_override,
               test_adr010_dmra, test_adr018_real_person_likeness,
               test_adr007_hitl_routing, test_adr001_assembler_has_no_verdict,
               test_adr014_variance_and_adr011_panel):
        try:
            fn()
        except Exception as e:
            RESULTS.append((f"{fn.__name__} raised", False, f"{type(e).__name__}: {e}"))

    w = max(len(n) for n, _, _ in RESULTS)
    failed = sum(not ok for _, ok, _ in RESULTS)
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{w}}  {'' if ok else detail}")
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
