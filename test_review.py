"""
test_review.py — the human step.

The claim under test is that a recorded review, and only a recorded review,
clears the cultural block; that a review carries a name; and that a high risk
on one axis cannot be averaged away by lows on the others.

Run: python3 test_review.py
"""

import json
import os
import sys
import tempfile

import chitra_facets as F
import chitra_predicates as P
import chitra_review as R
import chitra_sanitizer as S
import chitra_services as SV

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


REG = S.RuleRegistry.load(schema_path=os.path.join(HERE, "rule_object.schema.json"))

SLATE = {"concepts_approved": [
    {"id": "C01", "title": "The Real Culprit",
     "proposition": "The monsoon is the problem, not the powder",
     "visual_direction": "A family at the table during Diwali week, washing "
                         "draped over chairs behind them",
     "verbal_hook": {"primary": "Blame the sky"}},
    {"id": "C02", "title": "72 Hour Test",
     "proposition": "Three days indoors and everyone can tell",
     "visual_direction": "Time-stamped footage in a Mumbai flat",
     "verbal_hook": {"primary": "Filmed over three days"}}]}


LEDGER = None


def tmp():
    """A throwaway audits file, slate, and ledger.

    The ledger matters: without it every record() call in this suite appended
    to the production audit trail.
    """
    global LEDGER
    d = tempfile.mkdtemp()
    p = os.path.join(d, "audits.json")
    s = os.path.join(d, "slate.json")
    LEDGER = os.path.join(d, "ledger.jsonl")
    json.dump(SLATE, open(s, "w"))
    return p, s


def sanitize(audits):
    ctx = {"tenant": {"tenant_id": "t_001", "dpdp_retention_policy_days": 730},
           "campaign": {"product_category": "home_care",
                        "geography": ["Maharashtra"],
                        "research_coverage": ["Maharashtra"]},
           "services": SV.default_services(),
           "cultural_risk_audits": audits}
    return S.sanitize("concept_slate", SLATE, ctx, REG)


def test_no_test_writes_to_the_production_ledger():
    """The suite itself was the defect: 68 of the first 112 production ledger
    entries were fixtures from this file."""
    prod = os.path.join(HERE, "audit", "chitra-audit.jsonl")
    before = os.path.getsize(prod) if os.path.exists(prod) else 0
    a, s = tmp()
    R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", "C01",
            "--level", "low", "--reviewer", "A Patil", "--notes", "n"])
    after = os.path.getsize(prod) if os.path.exists(prod) else 0
    check("recording under --ledger leaves the production ledger untouched",
          before == after, f"{before} -> {after}")
    check("and the temporary ledger received it",
          os.path.exists(LEDGER) and os.path.getsize(LEDGER) > 0)


def test_review_clears_the_block_and_nothing_else_does():
    a, s = tmp()
    before = sanitize({})
    check("an unreviewed slate is inconclusive on all five cultural rules",
          len([i for i in before.inconclusive
               if i["rule_id"].startswith("CULTURAL-")]) == 5,
          str([i["rule_id"] for i in before.inconclusive]))
    check("and does not pass", not before.passed)

    for cid in ("C01", "C02"):
        R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", cid, "--level", "low",
                "--reviewer", "A Patil", "--notes", "reviewed"])
    after = sanitize(R.load_audits(a))
    check("a recorded review on every concept clears it", after.passed,
          str([i["rule_id"] for i in after.inconclusive]))

    partial = {k: v for k, v in R.load_audits(a).items() if k == "C01"}
    check("reviewing only one concept does not clear the slate",
          not sanitize(partial).passed,
          "a container is governed only if all of its concepts are")


def test_a_review_must_carry_a_name():
    a, s = tmp()
    rc = R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", "C01", "--level", "low",
                 "--reviewer", "   ", "--notes", "x"])
    check("a blank reviewer name is refused", rc == 2, f"exit {rc}")
    check("and nothing was written", not R.load_audits(a))


def test_the_worst_axis_governs():
    a, s = tmp()
    R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", "C01", "--level", "low",
            "--reviewer", "A Patil", "--axis", "religion=high",
            "--axis", "gender=low", "--notes", "festival framing"])
    rec = R.load_audits(a)["C01"]
    check("a high on one axis raises the overall level",
          rec["level"] == "high", rec["level"])
    check("and the per-axis detail is kept, not collapsed",
          rec["per_axis"] == {"religion": "high", "gender": "low"},
          str(rec["per_axis"]))


def _graded(**axes):
    base = dict(religion="low", caste="low", gender="low", region="low",
                political="low")
    base.update(axes)
    a, s = tmp()
    for c in SLATE["concepts_approved"]:
        args = ["--audits", a, "--ledger", LEDGER, "record",
                "--slate", s, "--concept", c["id"], "--level", "low",
                "--reviewer", "A Patil", "--notes", "n"]
        for axis, lvl in base.items():
            args += ["--axis", f"{axis}={lvl}"]
        R.main(args)
    r = sanitize(R.load_audits(a))
    return ([v["rule_id"] for v in r.violations],
            [w["rule_id"] for w in r.warnings], r.passed, a)


def test_each_axis_governs_only_its_own_rule():
    """A concept graded medium for religion was blocking on caste, because
    every rule read the aggregate level, which is the worst axis."""
    block, warn, passed, _ = _graded()
    check("all axes low passes", passed and not block and not warn,
          f"{block} {warn}")

    block, warn, _, _ = _graded(religion="medium")
    check("a religion grade blocks only the religion rule",
          block == ["CULTURAL-RELIGION-001"], str(block))

    block, warn, _, _ = _graded(caste="medium")
    check("a caste grade blocks only the caste rule",
          block == ["CULTURAL-CASTE-001"], str(block))


def test_the_escalation_threshold_decides_block_versus_warn():
    """Every conditional rule blocked at any level, because the threshold
    regex required a closing quote the rule extractor strips, so _escalates
    fell through to its fail-safe True and the fail-safe hid the bug."""
    block, warn, passed, _ = _graded(region="medium")
    check("region warns at medium, since its threshold is high",
          warn == ["CULTURAL-REGION-001"] and not block, f"{block} {warn}")
    check("and a warning does not fail the artifact", passed)

    block, warn, _, _ = _graded(region="high")
    check("region blocks at high", block == ["CULTURAL-REGION-001"], str(block))

    block, _, _, _ = _graded(religion="medium")
    check("religion blocks at medium, since its threshold is medium",
          block == ["CULTURAL-RELIGION-001"], str(block))


def test_a_grade_is_not_decorative():
    """Any completed audit used to return PASS, so the reviewer's grade had no
    effect and the conditional severity had no path to fire."""
    _, _, passed_low, _ = _graded()
    _, _, passed_high, a = _graded(gender="high")
    check("low passes and high does not", passed_low and not passed_high)
    view = F.FacetView(SLATE, "concept_slate",
                       {"cultural_risk_audits": R.load_audits(a)})
    audit, why = P.resolve_cultural_audit(
        view, {"cultural_risk_audits": R.load_audits(a)})
    check("the aggregate keeps every axis, not just the worst",
          audit and len(audit.get("per_axis") or {}) == 5,
          str((audit or {}).get("per_axis")))
    check("and names the reviewer", audit and audit.get("reviewer"),
          str((audit or {}).get("reviewer")))


def test_invalid_input_is_refused():
    a, s = tmp()
    check("an unknown axis is refused",
          R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", "C01", "--level", "low",
                  "--reviewer", "A", "--axis", "astrology=low"]) == 2)
    check("a bad per-axis level is refused",
          R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", "C01", "--level", "low",
                  "--reviewer", "A", "--axis", "religion=catastrophic"]) == 2)
    check("nothing partial was written", not R.load_audits(a))


def test_status_reports_what_is_outstanding():
    a, s = tmp()
    check("status exits non-zero while concepts are unaudited",
          R.main(["--audits", a, "status", "--slate", s]) == 1)
    for cid in ("C01", "C02"):
        R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s, "--concept", cid, "--level", "low",
                "--reviewer", "A Patil", "--notes", "n"])
    check("and zero once every one is recorded",
          R.main(["--audits", a, "status", "--slate", s]) == 0)


def test_markers_match_whole_words_only():
    """Found in review: 'om' matched from, some, comfort and custom; 'figure'
    matched 'figures out'. Two of five concepts were sent to religious and
    gender review on syllables. A brief nobody trusts is worse than none."""
    import chitra_cultural_assistant as CA
    a = CA.CulturalAssistant()
    ctx = {"cultural_risk_audits": {}}

    innocent = {"concept_id": "X", "title": "Time, Not Technique",
                "proposition": "Drying time, not detergent technique",
                "visual_direction": "A shirt hanging from the rail, some "
                                    "comfort in the routine, a custom blend",
                "verbal_hook": {"primary": "She figures out the timing"}}
    rb = a.assemble(innocent, ctx)
    check("from/some/comfort/custom no longer surface religion",
          "religion" not in rb.axes_touched, str(rb.axes_touched))
    check("'figures out' no longer surfaces gender",
          "gender" not in rb.axes_touched, str(rb.axes_touched))

    real = {"concept_id": "Y", "title": "Ganpati Whites",
            "proposition": "Festival clothes cannot wait for sunshine",
            "visual_direction": "Ganesh Chaturthi morning at the temple",
            "verbal_hook": {"primary": "Ready before the pandal is"}}
    rb2 = a.assemble(real, ctx)
    check("a genuine religious reference still surfaces",
          "religion" in rb2.axes_touched, str(rb2.axes_touched))
    check("and names which markers matched",
          "temple" in rb2.findings[0].triggered_by,
          str(rb2.findings[0].triggered_by))

    check("multi-word markers still match as phrases",
          CA.CulturalAssistant._matches("mother-in-law",
                                        "a mother-in-law inspects the collar"))
    check("and are not matched inside longer words",
          not CA.CulturalAssistant._matches("om", "comfort"))


def test_the_scanner_does_not_read_its_own_output():
    """Found in review, 19 Aug. Disha wrote the assistant's question into
    cultural_risk.register[].concern; the next scan found 'figure' inside its
    own question about religious symbols and reported a gender axis on two
    concepts whose copy was clean. A tool that reads its own output as
    evidence confirms itself indefinitely."""
    import chitra_cultural_assistant as CA
    a = CA.CulturalAssistant()
    ctx = {"cultural_risk_audits": {}}

    contaminated = {
        "id": "C13", "concept_id": "C13", "title": "Time, Not Technique",
        "proposition": "Reframe freshness as a formula achievement "
                       "independent of how or where clothes dry.",
        "visual_direction": "Minimalist product-hero shots intercut with "
                            "clock and calendar motifs.",
        "verbal_hook": {"primary": "Freshness built in, not dried in."},
        "cultural_risk": {"level": "medium", "register": [
            {"category": "religion",
             "concern": "Does the depiction place a religious symbol, "
                        "practice or figure in a commercial or comic frame?"}]},
        "scores": {"total": 22}}
    rb = a.assemble(contaminated, ctx)
    check("metadata no longer surfaces an axis", not rb.axes_touched,
          str(rb.axes_touched))

    real = dict(contaminated,
                visual_direction="Ganesh Chaturthi morning at the temple")
    check("creative copy still does",
          "religion" in a.assemble(real, ctx).axes_touched)

    check("metadata keys are excluded by name",
          "concern" in CA.METADATA_KEYS and "register" in CA.METADATA_KEYS
          and "scores" in CA.METADATA_KEYS)


def test_disha_writes_no_questions_into_the_artifact():
    """The root cause, not just the symptom. The register holds a reviewer's
    findings; the tool's prompts do not belong in the artifact."""
    import chitra_disha as DI
    import json as _j
    from test_disha import SlateClient, territories, CTX, COSTS
    from test_variance import DIVERGENT
    from test_drishti import GOOD_BRIEF, PACKET

    r = DI.Disha(SlateClient(territories(DIVERGENT)), REG,
                 competitor_archive=DI.CompetitorArchive([]),
                 cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    blob = _j.dumps(r.slate)
    check("no reviewer question reaches the artifact",
          "Question for you" not in blob and "question_for_reviewer" not in blob)
    check("the register ships empty for a reviewer to fill",
          all(c["cultural_risk"]["register"] == []
              for c in r.slate["concepts_approved"]))


def test_the_brief_surfaces_only_the_axes_the_concept_touches():
    import chitra_cultural_assistant as CA
    a, s = tmp()
    assistant = CA.CulturalAssistant(register=R._load_register(),
                                     precedent=R._load_precedent())
    ctx = {"cultural_risk_audits": {}}

    c01 = dict(SLATE["concepts_approved"][0], concept_id="C01")
    rb = assistant.assemble(c01, ctx, concept_id="C01")
    check("the Diwali reference surfaces the religion axis",
          "religion" in rb.axes_touched, str(rb.axes_touched))
    check("and register entries are attached", rb.findings[0].register_entries)

    c02 = dict(SLATE["concepts_approved"][1], concept_id="C02")
    rb2 = assistant.assemble(c02, ctx, concept_id="C02")
    check("a concept touching nothing surfaces nothing",
          not rb2.axes_touched, str(rb2.axes_touched))

    check("the brief still issues no verdict", rb.to_dict()["verdict"] is None)


def test_an_audit_is_bound_to_the_creative_it_reviewed():
    """The defect this exists to prevent, in its observed form.

    Concept ids are slate-local and reset to C01 on every run. Before audits
    carried a fingerprint, a review recorded against one campaign's first
    concept presented as the cultural risk level of a different campaign's
    first concept, in a different category, that no human had read.
    """
    a, s = tmp()
    R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s,
            "--concept", "C01", "--level", "low", "--reviewer", "A Patil",
            "--notes", "n"])
    rec = R.load_audits(a)["C01"]
    check("a recorded audit carries a fingerprint",
          bool(rec.get("concept_fingerprint")))
    check("and names the concept it reviewed, for a human reading the file",
          rec.get("concept_title") == "The Real Culprit",
          str(rec.get("concept_title")))

    # A different campaign whose first concept is also called C01.
    other = {"concepts_approved": [
        {"id": "C01", "title": "The Weather Did It",
         "proposition": "Built for clothes that cannot dry outside",
         "visual_direction": "Split screen: sky above, laundry below",
         "verbal_hook": {"primary": "Blame the sky, not the soap"}}]}
    bound, dropped = R.bind_audits(R.load_audits(a), other)
    check("an audit does not follow a concept id onto other creative",
          bound == {}, str(list(bound)))
    check("and the reason names the mismatch, rather than failing silently",
          dropped and "mismatch" in dropped[0][1], str(dropped))

    bound, dropped = R.bind_audits(R.load_audits(a), {"concepts_approved": [
        c for c in SLATE["concepts_approved"] if c["id"] == "C01"]})
    check("the audit still binds to the concept it was recorded on",
          list(bound) == ["C01"], str(list(bound)))
    check("and nothing is dropped in that case", not dropped, str(dropped))


def test_editing_a_reviewed_concept_revokes_its_clearance():
    a, s = tmp()
    R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s,
            "--concept", "C01", "--level", "low", "--reviewer", "A Patil",
            "--notes", "n"])
    edited = {"concepts_approved": [
        dict(SLATE["concepts_approved"][0],
             proposition="Now says something the reviewer never read")]}
    bound, dropped = R.bind_audits(R.load_audits(a), edited)
    check("a rewritten proposition loses the sign-off", bound == {},
          "the reviewer approved what they read, not the slot it sat in")
    check("and the concept counts as unreviewed downstream",
          not sanitize(bound).passed)


def test_an_unbound_audit_clears_nothing():
    a, s = tmp()
    R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s,
            "--concept", "C01", "--level", "low", "--reviewer", "A Patil",
            "--notes", "n"])
    legacy = R.load_audits(a)
    legacy["C01"].pop("concept_fingerprint")
    bound, dropped = R.bind_audits(legacy, SLATE)
    check("an audit with no fingerprint is treated as absent", bound == {},
          "fail closed: it cannot prove what it reviewed")
    check("and says so rather than passing quietly",
          dropped and "no fingerprint" in dropped[0][1], str(dropped))


def test_recording_without_a_slate_is_refused():
    a, s = tmp()
    rc = R.main(["--audits", a, "--ledger", LEDGER, "record", "--concept",
                 "C01", "--level", "low", "--reviewer", "A Patil",
                 "--notes", "n"])
    check("a review that names no slate is refused", rc == 2, f"exit {rc}")
    check("and nothing was written", not R.load_audits(a))

    rc = R.main(["--audits", a, "--ledger", LEDGER, "record", "--slate", s,
                 "--concept", "C99", "--level", "low", "--reviewer",
                 "A Patil", "--notes", "n"])
    check("a concept absent from that slate is refused", rc == 2, f"exit {rc}")
    check("and still nothing was written", not R.load_audits(a))


def main():
    for fn in (test_no_test_writes_to_the_production_ledger,
               test_review_clears_the_block_and_nothing_else_does,
               test_a_review_must_carry_a_name,
               test_the_worst_axis_governs,
               test_each_axis_governs_only_its_own_rule,
               test_the_escalation_threshold_decides_block_versus_warn,
               test_a_grade_is_not_decorative,
               test_invalid_input_is_refused,
               test_status_reports_what_is_outstanding,
               test_markers_match_whole_words_only,
               test_the_scanner_does_not_read_its_own_output,
               test_disha_writes_no_questions_into_the_artifact,
               test_an_audit_is_bound_to_the_creative_it_reviewed,
               test_editing_a_reviewed_concept_revokes_its_clearance,
               test_an_unbound_audit_clears_nothing,
               test_recording_without_a_slate_is_refused,
               test_the_brief_surfaces_only_the_axes_the_concept_touches):
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
