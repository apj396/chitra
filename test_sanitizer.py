"""
test_sanitizer.py — the v1.2.1 §F.13 worked examples, executed.

Those five examples were written as illustrations of the sanitizer contract.
They are the only place in the specification set where an expected output was
ever written down, which makes them the natural first test suite. Running them
is also the first time anything has checked whether they are internally
consistent with the rules they claim to invoke.

Run: python3 test_sanitizer.py
"""

import json
import os
import sys

import chitra_predicates as P
import chitra_sanitizer as S

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "rule_object.schema.json")

RESULTS = []
DIVERGENCES = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    return bool(condition)


def diverge(where, claim, observed):
    """Record a place where the specification and the running system disagree.

    Not a test failure. The specification is what is wrong in each case, and
    the divergence is the deliverable.
    """
    DIVERGENCES.append((where, claim, observed))


# --------------------------------------------------------------------------
# Stub services. Real deployments inject the MCP-backed versions.
# --------------------------------------------------------------------------

# The real vault, seeded with test records. A stub that implements lookup but
# not is_authorised passes tests the production path would fail, which is the
# whole reason stubs outlive their usefulness.
import chitra_services as _SV
ConsentVault = _SV.ConsentVault


class RegDB:
    def __init__(self, schedule=None, restricted=None, approved=None):
        self._schedule = schedule or []
        self._restricted = restricted or []
        self._approved = set(approved or [])
    def dmra_schedule_conditions(self): return self._schedule
    def restricted_countries(self): return self._restricted
    def dgci_approved(self, pid): return pid in self._approved


class CredentialRegistry:
    def __init__(self, records): self.records = records
    def lookup(self, cid): return self.records.get(cid)


class LegalPrecheck:
    def __init__(self, passes=True): self.passes = passes
    def trademark_clearance_passed(self, artifact): return self.passes


BASE_CTX = {
    "tenant": {"tenant_id": "t_001", "dpdp_retention_policy_days": 730,
               "competitive_exclusions": ["rival_co"]},
    "services": {
        "consent_vault": ConsentVault(records={
            "consent_ok": {"status": "valid", "purpose": "retargeting"},
            "consent_expired": {"status": "expired", "purpose": "retargeting"},
            "wa_optin": {"status": "valid", "purpose": "marketing", "channel": "whatsapp"},
            "wa_email": {"status": "valid", "purpose": "marketing", "channel": "email"},
            "parental_ok": {"status": "valid", "purpose": "marketing",
                            "consent_type": "verifiable_parental"},
        }),
        "regdb": RegDB(restricted=["XX"], approved=["prod_approved"]),
        "legal_precheck": LegalPrecheck(True),
        "credential_registry": CredentialRegistry({
            "cred_cfa": {"valid": True, "status": "active", "designation": "CFA"},
            "cred_lapsed": {"valid": False, "status": "lapsed", "designation": "CFA"},
        }),
    },
    "cultural_risk_audit": {"completed": True, "level": "low"},
}


def ctx(**over):
    c = json.loads(json.dumps({k: v for k, v in BASE_CTX.items()
                               if k != "services"}))
    c["services"] = BASE_CTX["services"]
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(c.get(k), dict):
            c[k].update(v)
        else:
            c[k] = v
    return c


REG = S.RuleRegistry.load(schema_path=SCHEMA)


# --------------------------------------------------------------------------
# Example 1 — social_post passes cleanly
# --------------------------------------------------------------------------

def example_1():
    art = {
        "paid_partnership": True,
        "content": {"first_line": "#Ad Loving this new shampoo!",
                    "caption": "#Ad Loving this new shampoo! Soft hair all week."},
        "ai_risk_tier": "none",
        "uses_custom_audience": True,
        "consent_artifact_id": "consent_ok",
        "processing_purpose": "retargeting",
        "product_category": "personal_care",
        "referenced_tenant_ids": ["t_001"],
    }
    r = S.sanitize("social_post", art, ctx(), REG)
    check("ex1: no violations", not r.violations,
          str([v["rule_id"] for v in r.violations]))
    check("ex1: ASCI-DISC-001 ran", "ASCI-DISC-001" in r.checks_run)
    check("ex1: DPDP-CONSENT-001 ran", "DPDP-CONSENT-001" in r.checks_run)
    if not r.passed:
        diverge("v1.2.1 §F.13 Example 1",
                "a social_post can pass cleanly with no human review",
                "cannot pass: " + ", ".join(i["rule_id"] for i in r.inconclusive) +
                " applies to every social_post and is a judgement call, so every "
                "post routes to human review")
    if "ASCI-DARK-001" in r.checks_run:
        diverge("v1.2.1 §F.13 Example 1 vs §F.12 matrix",
                "Example 1 checks_run lists 7 rules and omits ASCI-DARK-001",
                "the rule fires on this artifact, so the worked example and the "
                "canonical matrix disagree")
    return r


# --------------------------------------------------------------------------
# Example 2 — social_post blocked on missing #Ad, with auto-fix
# --------------------------------------------------------------------------

def example_2():
    art = {
        "paid_partnership": True,
        "content": {"first_line": "Loving this new shampoo!",
                    "caption": "Loving this new shampoo! Soft hair all week."},
        "ai_risk_tier": "none",
        "product_category": "personal_care",
        "referenced_tenant_ids": ["t_001"],
    }
    r = S.sanitize("social_post", art, ctx(), REG, apply_auto_fix=True)
    ids = [v["rule_id"] for v in r.violations]
    check("ex2: blocked", not r.passed)
    check("ex2: ASCI-DISC-001 is the violation", ids == ["ASCI-DISC-001"], str(ids))
    check("ex2: auto-fix offered", r.violations[0]["auto_fix_available"] is True)
    check("ex2: redacted payload prepends #Ad",
          r.redacted_payload["content"]["first_line"] == "#Ad Loving this new shampoo!",
          str(r.redacted_payload))
    fixed = dict(art)
    fixed["content"] = dict(art["content"], **r.redacted_payload["content"])
    r2 = S.sanitize("social_post", fixed, ctx(), REG)
    check("ex2: no violations after auto-fix", not r2.violations,
          str([v["rule_id"] for v in r2.violations]))
    return r


# --------------------------------------------------------------------------
# Example 2b — the ASCI 2026 correction that v1.2 got wrong
# --------------------------------------------------------------------------

def example_2b():
    art = {
        "paid_partnership": True,
        "content": {"first_line": "#Collab with GlowCo!",
                    "caption": "#Collab with GlowCo! Soft hair all week."},
        "ai_risk_tier": "none",
        "product_category": "personal_care",
        "referenced_tenant_ids": ["t_001"],
    }
    r = S.sanitize("social_post", art, ctx(), REG)
    ids = [v["rule_id"] for v in r.violations]
    check("ex2b: #Collab alone is blocked", "ASCI-DISC-001" in ids, str(ids))
    check("ex2b: message names the ambiguity",
          "Ambiguous" in (r.violations[0]["message"] or ""),
          r.violations[0]["message"] if r.violations else "")
    return r


# --------------------------------------------------------------------------
# Example 3 — motion asset blocked on AI disclosure timing
# --------------------------------------------------------------------------

def example_3():
    art = {
        "paid_partnership": True,
        "is_video": True,
        "duration_sec": 30,
        "disclosure_visible_duration_sec": 12,
        "verbal_disclosure_present": True,
        "verbal_disclosure_start_sec": 4,
        "ai_risk_tier": "medium",
        "ai_label_present": True,
        "ai_label_accurately_describes_use": True,
        "ai_label_within_first_5_sec": False,
        "ai_label_at_end": True,
        "ai_persona_speaks": True,
        "ai_label_visible_throughout_speech": False,
        "uses_music": True,
        "music_license_documented": True,
        "music_license_territory": "IN",
        "placements": ["jiohotstar_pre_roll", "youtube_long"],
        "product_category": "personal_care",
        "referenced_tenant_ids": ["t_001"],
    }
    r = S.sanitize("motion_asset_registry", art, ctx(), REG)
    ids = [v["rule_id"] for v in r.violations]
    check("ex3: blocked", not r.passed)
    check("ex3: ASCI-AI-001 violation present", "ASCI-AI-001" in ids, str(ids))
    warn_ids = [w["rule_id"] for w in r.warnings]
    check("ex3: IP-COPYRIGHT-002 catches territory mismatch as a warning",
          "IP-COPYRIGHT-002" in warn_ids, f"violations={ids} warnings={warn_ids}")
    check("ex3: territory concern does not block on its own",
          "IP-COPYRIGHT-002" not in ids, str(ids))
    check("ex3: human review required", r.human_review_required)
    return r


# --------------------------------------------------------------------------
# Example 5 — learnings_dossier blocked on individual-level data
# --------------------------------------------------------------------------

def example_5():
    art = {
        "data_retention_period_days": 365,
        "processing_log_retention_days": 400,
        "what_worked": [
            {"evidence": "Hindi creative outperformed English by 22% on CTR"},
            {"evidence": "customer_id=A8C9F2 converted at INR 4,200"},
        ],
        "referenced_tenant_ids": ["t_001"],
    }
    r = S.sanitize("learnings_dossier", art, ctx(), REG)
    ids = [v["rule_id"] for v in r.violations]
    check("ex5: blocked", not r.passed)
    check("ex5: DPDP-RETENTION-001 fires", "DPDP-RETENTION-001" in ids, str(ids))
    check("ex5: evidence points at the record",
          "customer_id" in (r.violations[0]["evidence"] or ""),
          r.violations[0]["evidence"] if r.violations else "")
    clean = dict(art, what_worked=[{"evidence": "Hindi creative outperformed English"}])
    check("ex5: aggregated version passes",
          S.sanitize("learnings_dossier", clean, ctx(), REG).passed)
    return r


# --------------------------------------------------------------------------
# P0 regression tests
# --------------------------------------------------------------------------

def p0_1_gaming():
    art = {"product_category": "fantasy_sports_real_money",
           "contains_addiction_warning": True, "contains_age_restriction_disclosure": True,
           "audience_min_age": 21, "product_certified_by_SRB": True,
           "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("media_plan", art, ctx(), REG)
    ids = [v["rule_id"] for v in r.violations]
    check("P0-1: RMG blocked even with every old condition satisfied",
          "GAMING-RMG-001" in ids and not r.passed, str(ids))
    check("P0-1: message cites Act 32 of 2025",
          "Act 32 of 2025" in (r.violations[0]["message"] or ""))
    ok = S.sanitize("media_plan", dict(art, product_category="esports_recognised"),
                    ctx(), REG)
    check("P0-1: recognised e-sports is not swept in",
          "GAMING-RMG-001" not in [v["rule_id"] for v in ok.violations])


def p0_4_cultural():
    art = {"uses_caste_stereotypes": False, "mocks_religion": False,
           "reinforces_harmful_gender_stereotypes": True,
           "referenced_tenant_ids": ["t_001"], "product_category": "personal_care"}
    r = S.sanitize("concept_slate", art, ctx(cultural_risk_audit={"completed": True,
                                                                  "level": "high"}), REG)
    ids = [v["rule_id"] for v in r.violations] + [w["rule_id"] for w in r.warnings]
    check("P0-4: CULTURAL-GENDER-001 produces an entry rather than silence",
          "CULTURAL-GENDER-001" in ids, str(ids))
    entry = next((v for v in r.violations if v["rule_id"] == "CULTURAL-GENDER-001"), None)
    check("P0-4: conditional severity resolved to block",
          entry and entry.get("resolved_severity") == "block", str(entry))


def p0_4_severity_guard():
    bad = dict(REG.get("CULTURAL-REGION-001").raw, severity="block_if_high_risk")
    d = {"registry_version": "test", "rules": [bad]}
    import tempfile
    p = tempfile.mktemp(suffix=".json")
    json.dump(d, open(p, "w"))
    try:
        S.RuleRegistry.load(rules_path=p, schema_path=None)
        check("P0-4: unhandled severity raises at load", False, "loaded silently")
    except S.SanitizerConfigurationError:
        check("P0-4: unhandled severity raises at load", True)
    finally:
        os.unlink(p)


def p0_5_placement():
    art = {"platform_family": "meta",
           "placements": ["instagram_reel", "messenger_stories", "instagram_explore_feed"],
           "product_category": "personal_care", "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("media_plan", art, ctx(), REG, apply_auto_fix=True)
    ids = [v["rule_id"] for v in r.violations]
    check("P0-5: removed placements blocked", "PLATFORM-TOS-META-PLACEMENT-001" in ids,
          str(ids))
    check("P0-5: auto-fix strips both",
          r.redacted_payload and r.redacted_payload["placements"] == ["instagram_reel"],
          str(r.redacted_payload))


def p1_6_single_evaluation():
    """Each rule's check must run exactly once per sanitize call."""
    calls = []
    original = P.REGISTRY["DPDP-CONSENT-001"]["fn"]

    def counting(artifact, c):
        calls.append(1)
        return original(artifact, c)

    P.REGISTRY["DPDP-CONSENT-001"]["fn"] = counting
    try:
        art = {"uses_custom_audience": True, "consent_artifact_id": "consent_expired",
               "processing_purpose": "retargeting", "product_category": "personal_care",
               "referenced_tenant_ids": ["t_001"]}
        r = S.sanitize("media_plan", art, ctx(), REG)
        check("P1-6: check evaluated exactly once", len(calls) == 1,
              f"evaluated {len(calls)} times")
        check("P1-6: still reports human review",
              r.human_review_required and not r.passed)
    finally:
        P.REGISTRY["DPDP-CONSENT-001"]["fn"] = original


def inconclusive_never_passes():
    art = {"contains_environmental_claim": True,
           "claim_quantified_with_specific_metric": True,
           "product_category": "personal_care", "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("asset_registry", art, ctx(), REG)
    check("inconclusive blocks the pass", not r.passed)
    check("inconclusive routes to human review", r.human_review_required)
    check("inconclusive is reported separately",
          any(i["rule_id"] == "ASCI-GREENWASH-001" for i in r.inconclusive))


def tenant_isolation():
    art = {"referenced_tenant_ids": ["t_001", "t_999"],
           "product_category": "personal_care"}
    r = S.sanitize("learnings_dossier", art, ctx(), REG)
    check("tenant isolation blocks cross-tenant reference",
          "CHITRA-TENANT-ISOLATION-001" in [v["rule_id"] for v in r.violations])


# --------------------------------------------------------------------------
# v1.3.4 — narrowed judgement rule and eliminated self-certification
# --------------------------------------------------------------------------

def v134_dark_pattern_narrowing():
    plain = {"paid_partnership": True,
             "content": {"first_line": "#Ad Nice shampoo", "caption": "#Ad Nice shampoo"},
             "ai_risk_tier": "none", "product_category": "personal_care",
             "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("social_post", plain, ctx(), REG)
    check("v1.3.4: plain post no longer triggers ASCI-DARK-001",
          "ASCI-DARK-001" not in r.checks_run, str(r.checks_run))
    check("v1.3.4: plain post now passes with no human review",
          r.passed and not r.human_review_required,
          f"incl={[i['rule_id'] for i in r.inconclusive]}")

    offer = dict(plain, offer_mechanics=["countdown_timer"])
    r2 = S.sanitize("social_post", offer, ctx(), REG)
    check("v1.3.4: a countdown still reaches ASCI-DARK-001",
          "ASCI-DARK-001" in r2.checks_run, str(r2.checks_run))
    check("v1.3.4: offer post routes to human review", r2.human_review_required)


def v134_no_self_declaration():
    import chitra_predicates as _P
    selfdec = [rid for rid, v in _P.REGISTRY.items() if v["class"] == _P.SELF_DECLARED]
    check("v1.3.4: no rule reads a self-declared compliance boolean",
          not selfdec, str(selfdec))


def v134_rbi_reads_copy():
    bad = {"product_category": "banking_lending_credit",
           "content": {"caption": "Get a personal loan today. Guaranteed returns!"},
           "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("asset_registry", bad, ctx(), REG)
    ids = [v["rule_id"] for v in r.violations]
    check("v1.3.4: RBI rule catches guarantee language in the copy",
          "RBI-BFSI-001" in ids, str(ids))

    # An artifact that lies about itself no longer passes.
    liar = dict(bad, content={"caption": "Get a personal loan today."},
                contains_apr_or_interest_disclosure=True,
                contains_t_and_c_apply_disclosure=True)
    r2 = S.sanitize("asset_registry", liar, ctx(), REG)
    check("v1.3.4: self-asserted disclosure flags no longer buy a pass",
          "RBI-BFSI-001" in [v["rule_id"] for v in r2.violations],
          str([v["rule_id"] for v in r2.violations]))

    ok = dict(bad, content={"caption": "Personal loan at 10.5% p.a. T&C apply."})
    r3 = S.sanitize("asset_registry", ok, ctx(), REG)
    check("v1.3.4: compliant credit copy passes the RBI rule",
          "RBI-BFSI-001" not in [v["rule_id"] for v in r3.violations],
          str([v["rule_id"] for v in r3.violations]))


def v134_whatsapp_optin_from_vault():
    art = {"channel": "whatsapp", "template_pre_approved": True,
           "respects_24h_utility_window": True, "recipients_opted_in": True,
           "opt_in_consent_artifact_id": "wa_email",
           "product_category": "personal_care", "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("media_plan", art, ctx(), REG)
    check("v1.3.4: WhatsApp opt-in on the wrong channel is caught by the vault",
          "PLATFORM-TOS-WHATSAPP-001" in [v["rule_id"] for v in r.violations],
          str([v["rule_id"] for v in r.violations]))
    ok = dict(art, opt_in_consent_artifact_id="wa_optin")
    r2 = S.sanitize("media_plan", ok, ctx(), REG)
    check("v1.3.4: valid WhatsApp opt-in passes",
          "PLATFORM-TOS-WHATSAPP-001" not in [v["rule_id"] for v in r2.violations])


def v134_children_derived_from_targeting():
    art = {"target_audience": {"includes_minors": True},
           "targeting_bases": ["lookalike"],
           "verifiable_parental_consent_in_place": True,
           "parental_consent_artifact_id": "parental_ok",
           "product_category": "personal_care", "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("media_plan", art, ctx(), REG)
    check("v1.3.4: behavioural targeting of minors caught from the plan itself",
          "DPDP-CHILDREN-001" in [v["rule_id"] for v in r.violations],
          str([v["rule_id"] for v in r.violations]))
    ok = dict(art, targeting_bases=["geography"])
    r2 = S.sanitize("media_plan", ok, ctx(), REG)
    check("v1.3.4: contextual targeting with parental consent passes",
          "DPDP-CHILDREN-001" not in [v["rule_id"] for v in r2.violations],
          str([v["rule_id"] for v in r2.violations]))


def v134_credential_must_resolve():
    art = {"sector": "BFSI", "contains_technical_advice": True,
           "influencer_qualification_credential_id": "cred_lapsed",
           "content": {"caption": "Certified advice on mutual funds"},
           "product_category": "personal_care", "referenced_tenant_ids": ["t_001"]}
    r = S.sanitize("social_post", art, ctx(), REG)
    check("v1.3.4: lapsed credential fails ASCI-BFSI-001",
          "ASCI-BFSI-001" in [v["rule_id"] for v in r.violations],
          str([v["rule_id"] for v in r.violations]))
    ok = dict(art, influencer_qualification_credential_id="cred_cfa")
    r2 = S.sanitize("social_post", ok, ctx(), REG)
    check("v1.3.4: valid credential stated in copy passes",
          "ASCI-BFSI-001" not in [v["rule_id"] for v in r2.violations],
          str([v["rule_id"] for v in r2.violations]))


def main():
    for fn in (example_1, example_2, example_2b, example_3, example_5,
               v134_dark_pattern_narrowing, v134_no_self_declaration,
               v134_rbi_reads_copy, v134_whatsapp_optin_from_vault,
               v134_children_derived_from_targeting, v134_credential_must_resolve,
               p0_1_gaming, p0_4_cultural, p0_4_severity_guard, p0_5_placement,
               p1_6_single_evaluation, inconclusive_never_passes, tenant_isolation):
        try:
            fn()
        except Exception as e:
            RESULTS.append((f"{fn.__name__} raised", False, f"{type(e).__name__}: {e}"))

    width = max(len(n) for n, _, _ in RESULTS)
    failed = 0
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {'' if ok else detail}")
        failed += not ok
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    if DIVERGENCES:
        print(f"\n{len(DIVERGENCES)} specification divergence(s) recorded:")
        for where, claim, observed in DIVERGENCES:
            print(f"  {where}")
            print(f"    specification: {claim}")
            print(f"    running system: {observed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
