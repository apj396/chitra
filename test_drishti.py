"""
test_drishti.py — end-to-end tests for Agent 1.

Exercises every branch of the agent loop with the offline client: refusal,
halt on an incomplete packet, schema repair, compliance repair, human-review
hold, and a clean handoff envelope.

Run: python3 test_drishti.py
"""

import json
import os
import sys

import chitra_drishti as D
import chitra_sanitizer as S
import chitra_services as _SV

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


REG = S.RuleRegistry.load(schema_path=os.path.join(HERE, "rule_object.schema.json"))

CTX = {
    "campaign": {"geography": ["Maharashtra", "Karnataka"],
                 "research_coverage": ["Maharashtra", "Karnataka"]},
    "tenant": {"tenant_id": "t_001", "dpdp_retention_policy_days": 730,
               "competitive_exclusions": []},
    "services": {},
    "cultural_risk_audits": {
        "concept_monsoon_01": {"completed": True, "level": "low"},
    },
}

PACKET = {
    "client_name": "Sundara Home Care",
    "campaign_id": "camp_2026_monsoon",
    "concept_id": "concept_monsoon_01",
    "tenant_id": "t_001",
    "sector": "fmcg",
    "product_category": "home_care",
    "business_problem": "Urban households switched to a cheaper rival during the "
                        "last two monsoons and did not switch back.",
    "target_audience_description": {"summary": "Tier 1 and 2 urban households",
                                    "includes_minors": False},
    "geography": ["Maharashtra", "Karnataka", "Tamil Nadu"],
    "budget_inr": 42000000,
    "timeline": {"launch": "2026-09-15", "end": "2026-11-30"},
    "approval_chain": ["brand_manager", "marketing_head"],
    "targeting_bases": ["geography", "household_stage"],
    "audience_research": {"source": "U&A study March 2026",
                          "anxieties": ["sour smell from indoor drying"],
                          "aspirations": ["a home that smells clean"]},
    "business_metric_targets": [{"metric": "volume_share", "target": 2.5,
                                 "unit": "pp"}],
    "brand_metric_targets": [{"metric": "consideration", "target": 8,
                              "unit": "pp"}],
    "attribution_model": "data_driven",
    "brand_guidelines": {"mandatories": [], "prohibitions": []},
}

GOOD_BRIEF = {
    "business_problem": "Households that switched to a cheaper rival during the "
                        "monsoon have not switched back.",
    "target_audience": {
        "demographics": {"age_range": {"min": 25, "max": 45},
                         "income_band": "NCCS_B", "city_tier": ["tier_1", "tier_2"]},
        "psychographics": {"values": ["thrift", "family care"],
                           "anxieties": ["damp clothes smell during monsoon"],
                           "aspirations": ["a home that smells clean"]},
        "day_in_the_life": ("She wakes before the household and checks whether "
                            "yesterday's washing has dried on the balcony rail. It "
                            "has not. She moves it indoors, where it will hang over "
                            "the chairs until evening and the flat will hold that "
                            "faint sourness she cannot name but everyone notices."),
    },
    "perception_gap": {
        "current": "All detergents are the same once the rain starts.",
        "desired": "One of them was built for the rain.",
    },
    "insight": ("During the monsoon the failure is not cleaning, it is drying. "
                "Households blame the detergent for a problem the weather caused, "
                "and switch on price because they believe the category cannot "
                "solve it."),
    "core_message": "Built for clothes that cannot dry outside.",
    "tone_spectrum": {"serious_to_playful": 1, "premium_to_accessible": 3,
                      "traditional_to_modern": 0},
    "mandatories": [{"item": "Show the product pack in the final three seconds",
                     "source": "client_brief"}],
    "prohibitions": [{"item": "No comparative claims naming the rival brand",
                      "source": "client_brief"}],
    "success_metrics": {
        "business_metrics": [{"metric": "volume_share", "target": 2.5, "unit": "pp"}],
        "brand_metrics": [{"metric": "consideration", "target": 8, "unit": "pp"}],
        "attribution_model": "data_driven",
    },
    "cultural_overlay": {
        "festivals_in_window": [{"name": "Ganesh Chaturthi", "date": "2026-09-14",
                                 "marketing_relevance": "high"}],
        "sports_in_window": [],
        "sensitivities": [],
    },
    "open_questions_for_disha": ["Is the rival named anywhere in prior creative?"],
}


def test_refuses_prohibited_category():
    agent = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG)
    r = agent.run(dict(PACKET, product_category="fantasy_sports_real_money"), CTX)
    check("refuses real-money gaming before calling the model",
          r.status == "refused" and "Act 32 of 2025" in (r.reason or ""), r.reason or "")
    check("no model call was made on refusal", agent.client.calls == 0,
          f"calls={agent.client.calls}")


def test_refuses_tobacco():
    agent = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG)
    r = agent.run(dict(PACKET, product_category="tobacco"), CTX)
    check("refuses tobacco", r.status == "refused", r.reason or "")


def test_refuses_prohibited_targeting_basis():
    agent = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG)
    r = agent.run(dict(PACKET, targeting_bases=["geography", "caste"]), CTX)
    check("refuses a caste targeting basis",
          r.status == "refused" and "caste" in (r.reason or ""), r.reason or "")


def test_refuses_minors_restricted_category():
    p = dict(PACKET, product_category="junk_food",
             target_audience_description={"includes_minors": True})
    r = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG).run(p, CTX)
    check("refuses restricted-category content aimed at minors",
          r.status == "refused", r.reason or "")


def test_halts_on_incomplete_packet():
    p = {k: v for k, v in PACKET.items()
         if k not in ("budget_inr", "approval_chain")}
    r = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG).run(p, CTX)
    check("halts rather than inferring a missing packet field",
          r.status == "clarification_required")
    check("names exactly what is missing",
          set(r.missing_fields) == {"budget_inr", "approval_chain"},
          str(r.missing_fields))


def test_refusal_precedes_completeness():
    """A banned category is refused even from an incomplete packet."""
    bare = {"client_name": "X", "product_category": "tobacco"}
    r = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG).run(bare, CTX)
    check("prohibited category refused without demanding missing fields",
          r.status == "refused", f"{r.status}: {r.reason}")


def test_halts_when_the_model_refuses_to_fabricate():
    """The scaffold forbids inventing audience data; the schema requires it."""
    blocked = json.loads(json.dumps(GOOD_BRIEF))
    blocked["target_audience"]["psychographics"] = \
        "BLOCKED_PENDING_INPUT: no research supplied"
    r = D.Drishti(D.OfflineClient(blocked), REG).run(PACKET, CTX)
    check("a refusal to fabricate halts instead of burning repair turns",
          r.status == "clarification_required", f"{r.status}: {r.reason}")
    check("one turn, not three", r.attempts == 1, f"attempts={r.attempts}")
    check("names the field the model declined to invent",
          "target_audience.psychographics" in r.missing_fields,
          str(r.missing_fields))


def test_uncovered_region_halts_before_any_model_call():
    """ADR-020. Paying to write a brief for a market that cannot ship is waste."""
    p = json.loads(json.dumps(PACKET))
    p["geography"] = ["Maharashtra", "Tamil Nadu"]
    p["audience_research"]["coverage"] = ["Maharashtra"]
    client = D.OfflineClient(GOOD_BRIEF)
    r = D.Drishti(client, REG).run(p, CTX)
    check("uncovered region halts at preflight",
          r.status == "clarification_required", f"{r.status}: {r.reason}")
    check("no model call was made", client.calls == 0, f"calls={client.calls}")
    check("the reason offers all three resolutions",
          all(w in (r.reason or "") for w in ("Remove", "extend", "waiver")),
          r.reason or "")

    p["research_coverage_waivers"] = [
        {"region": "Tamil Nadu", "approved_by": "A Patil",
         "approved_on": "2026-08-16", "rationale": "accepted risk"}]
    r2 = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG).run(p, CTX)
    check("a signed waiver lets the run proceed", r2.status == "brief",
          f"{r2.status}: {r2.reason}")


def test_happy_path():
    agent = D.Drishti(D.OfflineClient(GOOD_BRIEF), REG)
    r = agent.run(PACKET, CTX)
    check("produces a brief on a clean packet", r.status == "brief", r.reason or "")
    check("one model call, no repair needed", r.attempts == 1, f"attempts={r.attempts}")
    check("brief validates against creative_brief.json", r.brief is not None)
    check("sanitizer passed", r.sanitizer and r.sanitizer["pass"],
          json.dumps(r.sanitizer)[:200] if r.sanitizer else "")
    env = r.envelope
    check("envelope addresses Disha",
          env["from_agent"] == "drishti" and env["to_agent"] == "disha")
    check("envelope carries the compliance record",
          env["sanitizer_pass"] is True and len(env["compliance_checks_run"]) > 0,
          str(env.get("compliance_checks_run")))
    check("envelope is not marked locked before signoff",
          env["status"] == "PENDING_DISHA_SIGNOFF", env["status"])


def test_schema_repair_loop():
    broken = {k: v for k, v in GOOD_BRIEF.items() if k != "core_message"}
    agent = D.Drishti(D.OfflineClient(broken, repair={"core_message":
                                                      "Built for clothes that "
                                                      "cannot dry outside."}), REG)
    r = agent.run(PACKET, CTX)
    check("recovers from a schema violation rather than failing",
          r.status == "brief", r.reason or "")
    check("took a repair turn", r.attempts == 2, f"attempts={r.attempts}")
    check("first turn recorded the schema error",
          "schema_errors" in r.transcript[0], str(r.transcript[0]))


def test_compliance_repair_loop():
    """A brief for a minor audience without parental consent is blocked, and the
    repair turn supplies it."""
    p = dict(PACKET, product_category="edtech")
    minors = json.loads(json.dumps(GOOD_BRIEF))
    minors["target_audience"]["demographics"]["age_range"] = {"min": 14, "max": 17}
    ctx = json.loads(json.dumps({k: v for k, v in CTX.items() if k != "services"}))
    ctx["services"] = {"consent_vault": _Vault()}
    agent = D.Drishti(
        D.OfflineClient(minors, repair={"target_audience": {"demographics":
                        {"age_range": {"min": 18, "max": 34}}}}), REG)
    r = agent.run(p, ctx)
    check("blocked brief is repaired rather than returned",
          r.status == "brief" and r.attempts == 2,
          f"status={r.status} attempts={r.attempts} reason={r.reason}")
    check("first turn recorded a compliance violation",
          r.transcript[0]["sanitizer"]["violations"], str(r.transcript[0]))


class _Vault(_SV.ConsentVault):
    """Empty real vault: every lookup is a verified absence, not a stub.

    A stub implementing lookup but not is_authorised passed tests the
    production path would fail. That is the failure mode stubs have.
    """
    def __init__(self):
        super().__init__(records={})


def test_cultural_audit_inheritance():
    """v1.3.5 scoping: an asset inherits its concept's audit unless it introduces
    a new cultural surface."""
    import chitra_predicates as P
    a1, why1 = P.resolve_cultural_audit({"concept_id": "concept_monsoon_01"}, CTX)
    check("artifact inherits its concept's audit", a1 is not None, why1)

    a2, why2 = P.resolve_cultural_audit(
        {"concept_id": "concept_monsoon_01", "introduces_new_language": True}, CTX)
    check("inheritance breaks when a new cultural surface appears",
          a2 is None and "inheritance broken" in why2, why2)

    a3, why3 = P.resolve_cultural_audit({"concept_id": "concept_unaudited"}, CTX)
    check("an unaudited concept does not inherit", a3 is None, why3)


def test_prompt_is_read_from_the_specification():
    sysprompt = D.load_system_prompt("t_001")
    check("L0 wrapper present and tenant-substituted",
          "[SECURITY HEADER" in sysprompt and "t_001" in sysprompt
          and "{{tenant_id}}" not in sysprompt)
    check("Drishti scaffold present",
          "You are Drishti" in sysprompt and "[METHODOLOGY]" in sysprompt)
    check("output contract overrides the markdown format",
          "[OUTPUT CONTRACT" in sysprompt and "wire format is JSON" in sysprompt)
    # The contract must STATE the schema, not name it. Naming a file the model
    # cannot open is how the first real run burned three repair turns.
    check("the schema itself is embedded, not merely referenced",
          "MUST VALIDATE AGAINST THIS" in sysprompt)
    for value in ("NCCS_B", "data_driven", "parents_young_kids"):
        check(f"closed enum value {value} is visible to the model",
              value in sysprompt)


def test_real_client_reports_availability():
    c = D.AnthropicClient()
    check("Anthropic client reports whether it can run",
          c.available() == bool(os.environ.get("ANTHROPIC_API_KEY")),
          f"available={c.available()}")


def main():
    for fn in (test_refuses_prohibited_category, test_refuses_tobacco,
               test_refuses_prohibited_targeting_basis,
               test_refuses_minors_restricted_category,
               test_halts_on_incomplete_packet, test_refusal_precedes_completeness,
               test_uncovered_region_halts_before_any_model_call,
               test_halts_when_the_model_refuses_to_fabricate, test_happy_path,
               test_schema_repair_loop, test_compliance_repair_loop,
               test_cultural_audit_inheritance,
               test_prompt_is_read_from_the_specification,
               test_real_client_reports_availability):
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
