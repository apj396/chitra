"""
test_disha.py — end-to-end tests for Agent 2.

Exercises the four things the scaffold asks for that no implementation had:
brief interrogation as a real return path, divergence enforced rather than
requested, scoring separated from generating, and missing dependencies
declared rather than skipped.

Run: python3 test_disha.py
"""

import json
import os
import sys

import chitra_disha as D
import chitra_drishti as DR
import chitra_sanitizer as S
import chitra_services as SV
from test_drishti import GOOD_BRIEF, PACKET
from test_variance import DIVERGENT, PADDED

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


REG = S.RuleRegistry.load(schema_path=os.path.join(HERE, "rule_object.schema.json"))

CTX = {
    "tenant": {"tenant_id": "t_001", "dpdp_retention_policy_days": 730},
    "campaign": {"budget_inr": 42000000, "sector": "fmcg"},
    "services": SV.default_services(),
    "cultural_risk_audits": {f"C{i:02d}": {"completed": True, "level": "low"}
                             for i in range(1, 13)},
}

COSTS = D.ProductionCostModel(bands={"low": (800000, 2500000),
                                     "medium": (2500000, 9000000),
                                     "high": (9000000, 30000000)})


def territories(source, complexity="medium"):
    out = []
    for i, c in enumerate(source):
        out.append({"id": f"C{i + 1:02d}", "title": c["title"],
                    "proposition": c["proposition"],
                    "visual_direction": c["visual_direction"],
                    "verbal_hook": {"primary": c["verbal_hook"],
                                    "alternates": [c["verbal_hook"] + " (b)",
                                                   c["verbal_hook"] + " (c)"]},
                    "target_subsegment": "urban households, tier 1 and 2",
                    "lens": c["lens"], "production_complexity": complexity})
    return out


class SlateClient:
    """Returns territories on the first call, scores on the scoring call.

    Optionally returns a padded batch first and a clean batch on repair, which
    is what a real agent does after the divergence gate rejects indices.
    """

    def __init__(self, first, repair=None, scores=None):
        self.first, self.repair, self.scores = first, repair, scores or {}
        self.calls = 0

    def available(self):
        return True

    def complete(self, system, messages):
        self.calls += 1
        last = messages[-1]["content"]
        if "Score every territory" in last:
            ids = [t["id"] for t in json.loads(last[last.index("["):])]
            return json.dumps({"scores": {i: self.scores.get(
                i, {"relevance": 4, "distinctiveness": 4, "resonance": 4,
                    "producibility": 4, "cultural_safety": 4}) for i in ids}})
        if "Divergence gate" in last and self.repair is not None:
            return json.dumps({"territories": self.repair})
        return json.dumps({"territories": self.first})


# ---------------------------------------------------------------- happy path
def test_happy_path():
    c = SlateClient(territories(DIVERGENT))
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("produces a slate", r.status == "slate", r.reason or "")
    check("three to five approved",
          3 <= len(r.slate["concepts_approved"]) <= 5,
          str(len(r.slate["concepts_approved"])))
    check("everything else is killed with a tag and rationale",
          all(k.get("kill_tag") and k.get("rationale")
              for k in r.slate["concepts_killed"]),
          str(r.slate["concepts_killed"][:1]))
    check("approved plus killed accounts for all twelve",
          len(r.slate["concepts_approved"]) + len(r.slate["concepts_killed"]) == 12)
    check("slate validates against concept_slate.json", r.slate is not None)
    env = r.envelope
    check("handoff goes to Roop and Vaani jointly",
          env["to_agent"] == ["roop", "vaani"], str(env["to_agent"]))
    check("Lakshya cc'd for media feasibility", env["cc_agent"] == ["lakshya"])
    check("confidentiality vault flag set", env["confidentiality_vault"] is True)
    check("not marked accepted by Disha itself",
          env["status"] == "PENDING_JOINT_ACCEPTANCE")


# ---------------------------------------------------------------- divergence
def test_divergence_gate_runs_before_scoring():
    padded = territories(PADDED)
    clean = territories(DIVERGENT)[:8]
    c = SlateClient(padded, repair=clean)
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("padded divergence is rejected before the kill pass",
          r.transcript[0]["gate"]["passed"] is False,
          str(r.transcript[0]["gate"]["report"]["verdict"]))
    check("gate feedback names the collapse",
          "same territory" in r.transcript[0]["gate"]["feedback"] or
          "lens" in r.transcript[0]["gate"]["feedback"])
    check("recovers on the repair turn and ships a slate",
          r.status == "slate", r.reason or "")
    check("took more than one divergence turn", len(r.transcript) >= 2,
          str(len(r.transcript)))


def test_unreadable_divergence_is_distinguished_from_short():
    """A response that does not parse is not the same as too few territories.

    The first real run reported "0 territories supplied. Generate 12 more",
    which was true and useless: it could not tell an unparseable response from
    a truncated one from a model answering under a different key.
    """
    class Prose:
        def available(self): return True
        def complete(self, system, messages):
            if "Score every territory" in messages[-1]["content"]:
                return json.dumps({"scores": {}})
            return "Here are twelve territories for your consideration:\n\n1. ..."

    r = D.Disha(Prose(), REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("an unparseable response is recorded as such",
          r.transcript[0].get("parse_failed") is True, str(r.transcript[0])[:160])
    check("the raw response head is captured for diagnosis",
          "Here are twelve" in (r.transcript[0].get("raw_head") or ""),
          str(r.transcript[0].get("raw_head"))[:80])
    check("the failure reason names the parse failure, not a count",
          "never parsed as JSON" in (r.reason or ""), r.reason or "")

    class WrongKey:
        def available(self): return True
        def complete(self, system, messages):
            if "Score every territory" in messages[-1]["content"]:
                return json.dumps({"scores": {}})
            return json.dumps({"concepts": [], "notes": "used the wrong key"})

    r2 = D.Disha(WrongKey(), REG, competitor_archive=D.CompetitorArchive([]),
                 cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("a wrong top-level key is named rather than counted as zero",
          "territories" in (r2.reason or "") and "concepts" in str(
              r2.transcript[0].get("unexpected_keys")),
          f"{r2.reason} / {r2.transcript[0].get('unexpected_keys')}")


def test_divergence_prompt_does_not_ask_for_a_slate():
    """Two rounds of this. v1.3.9 embedded the slate schema under 'YOUR OUTPUT
    MUST VALIDATE AGAINST THIS'; removing it did not help, because the v1.1
    scaffold's own OUTPUT FORMAT section defines a Concept Slate with a Killed
    Concepts Log. A real run returned concepts_approved from the scaffold
    alone."""
    prompt = D.load_system_prompt("t_001", phase="divergence")
    check("the slate schema is not in the divergence prompt",
          "CONCEPT SLATE SCHEMA" not in prompt)
    check("nor is the scaffold's own slate format",
          "Killed Concepts Log" not in prompt and "Concept Slate:" not in prompt)
    check("and the removal is explained to the model",
          "You do not write a slate" in prompt)

    scoring = D.load_system_prompt("t_001", phase="scoring")
    check("the scoring phase keeps the scaffold intact",
          "Killed Concepts Log" in scoring,
          "stripping it everywhere would lose the kill-tag vocabulary")
    check("wrapper keys are named and forbidden",
          "DO NOT return concepts_approved" in prompt)
    check("the correct shape is shown literally",
          '{"territories": [{"title"' in prompt)
    check("and brevity is asked for, since two runs hit max_tokens",
          "exhaust the response budget" in prompt)


def test_truncated_divergence_is_salvaged():
    """Two of four real turn-1 failures were a fence around unclosed JSON."""
    class Truncating:
        def __init__(self): self.calls = 0
        def available(self): return True
        def complete(self, system, messages):
            self.calls += 1
            last = messages[-1]["content"]
            if "Score every territory" in last:
                ids = [t["id"] for t in json.loads(last[last.index("["):])]
                return json.dumps({"scores": {
                    i: {"relevance": 4, "distinctiveness": 4, "resonance": 4,
                        "producibility": 4, "cultural_safety": 4} for i in ids}})
            if self.calls == 1:
                whole = json.dumps({"territories": territories(DIVERGENT)})
                return "```json\n" + whole[:len(whole) // 2]
            return json.dumps({"territories": territories(DIVERGENT)})

    c = Truncating()
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("a truncated fenced response yields partial territories",
          r.transcript[0].get("territories_returned", 0) > 0,
          str(r.transcript[0].get("territories_returned")))
    check("and the run still completes", r.status == "slate", r.reason or "")


def test_short_divergence_rejected():
    c = SlateClient(territories(DIVERGENT)[:7])
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("fewer than twelve territories does not proceed",
          r.status == "failed", r.status)
    check("failure names the divergence gate",
          "divergence" in (r.reason or "").lower(), r.reason or "")


# ---------------------------------------------------------------- scoring
def test_scoring_is_applied_by_code_not_the_model():
    low = {f"C{i:02d}": {"relevance": 2, "distinctiveness": 2, "resonance": 2,
                         "producibility": 3, "cultural_safety": 3}
           for i in range(1, 13)}
    c = SlateClient(territories(DIVERGENT), scores=low)
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("a slate that cannot clear 16/25 is refused, not shipped",
          r.status == "refused", f"{r.status}: {r.reason}")
    check("refusal names the bar", "16/25" in (r.reason or ""), r.reason or "")

    mixed = dict(low)
    for i in range(1, 5):
        mixed[f"C{i:02d}"] = {"relevance": 5, "distinctiveness": 5, "resonance": 4,
                              "producibility": 4, "cultural_safety": 4}
    c2 = SlateClient(territories(DIVERGENT), scores=mixed)
    r2 = D.Disha(c2, REG, competitor_archive=D.CompetitorArchive([]),
                 cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("only concepts above the bar are approved",
          all(a["scores"]["total"] >= 16 for a in r2.slate["concepts_approved"]),
          str([a["scores"]["total"] for a in r2.slate["concepts_approved"]]))
    check("kill tag is derived from the weakest dimension",
          any(k["kill_tag"] in ("solves_wrong_problem",
                                "insight_borrowed_not_earned")
              for k in r2.slate["concepts_killed"]))


def test_model_cannot_self_approve_out_of_range_scores():
    absurd = {f"C{i:02d}": {"relevance": 99, "distinctiveness": 99,
                            "resonance": 99, "producibility": 99,
                            "cultural_safety": 99} for i in range(1, 13)}
    c = SlateClient(territories(DIVERGENT), scores=absurd)
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("out-of-range model scores are clamped, not trusted",
          all(all(1 <= a["scores"][d] <= 5 for d in D.SCORE_DIMENSIONS)
              for a in r.slate["concepts_approved"]),
          str(r.slate["concepts_approved"][0]["scores"]))
    check("clamping still caps the slate at five",
          len(r.slate["concepts_approved"]) <= 5)


# ---------------------------------------------------------------- dependencies
def test_missing_dependencies_are_declared_not_skipped():
    c = SlateClient(territories(DIVERGENT))
    r = D.Disha(c, REG).run(GOOD_BRIEF, PACKET, CTX)   # no archive, no costs
    checks = {u["check"] for u in r.unverifiable}
    check("derivative check reported unverifiable without the archive",
          "derivative_risk" in checks, str(checks))
    check("budget check reported unverifiable without a cost model",
          "budget_envelope" in checks, str(checks))
    check("unverifiable checks force human review",
          r.envelope["human_review_required"] is True)
    check("envelope carries the unverifiable list",
          bool(r.envelope["unverifiable_checks"]))
    check("the slate is still produced, not blocked", r.status == "slate")


def test_competitor_archive_kills_derivative_work():
    archive = D.CompetitorArchive([
        {"brand": "RivalCo", "year": 2025, "sector": "fmcg",
         "proposition": "The monsoon is the problem, not the powder"}])
    c = SlateClient(territories(DIVERGENT))
    r = D.Disha(c, REG, competitor_archive=archive, cost_model=COSTS).run(
        GOOD_BRIEF, PACKET, CTX)
    tags = {k["kill_tag"] for k in r.slate["concepts_killed"]}
    check("derivative concept killed against the archive",
          "indistinguishable_from_recent_category_work" in tags, str(tags))
    rat = next(k["rationale"] for k in r.slate["concepts_killed"]
               if k["kill_tag"] == "indistinguishable_from_recent_category_work")
    check("rationale names the brand and year", "RivalCo" in rat and "2025" in rat, rat)


def test_budget_envelope_kills_expensive_concepts():
    c = SlateClient(territories(DIVERGENT, complexity="high"))
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("high-complexity concepts exceed a 42 lakh envelope and are killed",
          r.status == "refused" or
          any(k["kill_tag"] == "production_cost_exceeds_envelope"
              for k in (r.slate or {}).get("concepts_killed", [])),
          f"{r.status}: {r.reason}")


# ---------------------------------------------------------------- interrogation
def test_brief_interrogation_finds_structural_vulnerabilities():
    thin = json.loads(json.dumps(GOOD_BRIEF))
    thin["insight"] = "People want cleaner clothes."
    thin["target_audience"]["psychographics"] = {}
    d = D.Disha(SlateClient(territories(DIVERGENT)), REG)
    _, vulns = d.interrogate(thin)
    fields = {v["field"] for v in vulns}
    check("thin insight surfaced", "insight" in fields, str(fields))
    check("demographic-only audience surfaced",
          "target_audience.psychographics" in fields, str(fields))
    # GOOD_BRIEF carries one open_questions_for_disha entry, so a structurally
    # sound brief is not a silent one: Drishti's question still comes through.
    sound = d.interrogate(GOOD_BRIEF)[1]
    check("a structurally sound brief raises nothing of Disha's own",
          not [x for x in sound if x.get("raised_by") == "disha"], str(sound))
    check("but Drishti's open question still comes through",
          [x for x in sound if x.get("raised_by") == "drishti"], str(sound))

    silent = json.loads(json.dumps(GOOD_BRIEF))
    silent["open_questions_for_disha"] = []
    check("a sound brief with no open questions surfaces nothing",
          not d.interrogate(silent)[1], str(d.interrogate(silent)[1]))


def test_disha_reads_the_briefs_own_open_questions():
    """The channel the schema built for this was never opened.

    The first real run: Drishti raised six open_questions_for_disha and the
    console reported "no structural vulnerabilities" in the same breath.
    """
    b = json.loads(json.dumps(GOOD_BRIEF))
    b["open_questions_for_disha"] = [
        "Is Tamil Nadu in scope? No research covers it.",
        "Is the rival named anywhere in prior creative?"]
    d = D.Disha(SlateClient(territories(DIVERGENT)), REG)
    _, v = d.interrogate(b)
    raised = [x for x in v if x["field"] == "open_questions_for_disha"]
    check("every open question becomes a vulnerability", len(raised) == 2,
          str(v))
    check("and is attributed to Drishti, not invented by Disha",
          all(x["raised_by"] == "drishti" for x in raised))


def test_research_coverage_gap_is_structural():
    p = json.loads(json.dumps(PACKET))
    p["geography"] = ["Maharashtra", "Karnataka", "Tamil Nadu"]
    p["audience_research"]["coverage"] = ["Maharashtra", "Karnataka"]
    d = D.Disha(SlateClient(territories(DIVERGENT)), REG)
    _, v = d.interrogate(GOOD_BRIEF, packet=p)
    gap = [x for x in v if x["field"] == "audience_research.coverage"]
    check("an uncovered market is flagged without the model mentioning it",
          gap, str(v))
    check("the uncovered market is named", gap and "tamil nadu" in gap[0]["issue"],
          gap[0]["issue"] if gap else "")

    p["audience_research"]["coverage"] = ["Maharashtra", "Karnataka", "Tamil Nadu"]
    _, v2 = d.interrogate(GOOD_BRIEF, packet=p)
    check("full coverage raises nothing",
          not [x for x in v2 if x["field"] == "audience_research.coverage"])


def test_interrogation_loop_is_bounded_and_returns_to_drishti():
    thin = json.loads(json.dumps(GOOD_BRIEF))
    thin["insight"] = "People want cleaner clothes."

    class StubbornDrishti:
        """Returns the brief unchanged, which is the ping-pong case."""
        def __init__(self):
            self.calls = 0

        def revise(self, brief, vulns, packet=None, context=None):
            self.calls += 1
            return brief

    dr = StubbornDrishti()
    d = D.Disha(SlateClient(territories(DIVERGENT)), REG)
    brief, vulns = d.interrogate(thin, drishti=dr, rounds=None)
    check("loop is bounded rather than infinite",
          dr.calls == D.Disha.MAX_INTERROGATION_ROUNDS, f"{dr.calls} calls")
    check("unresolved vulnerabilities are carried, not dropped", bool(vulns))

    class HelpfulDrishti:
        def revise(self, brief, vulns, packet=None, context=None):
            fixed = json.loads(json.dumps(brief))
            fixed["insight"] = GOOD_BRIEF["insight"]
            return fixed

    _, vulns2 = d.interrogate(thin, drishti=HelpfulDrishti())
    check("a resolved vulnerability clears",
          not any(v["field"] == "insight" for v in vulns2), str(vulns2))


def test_drishti_revise_rejects_an_invalid_revision():
    broken = {k: v for k, v in GOOD_BRIEF.items() if k != "core_message"}
    agent = DR.Drishti(DR.OfflineClient(broken), REG)
    out = agent.revise(GOOD_BRIEF, [{"field": "insight", "issue": "thin"}])
    check("a revision that fails the schema is refused, not returned",
          out is None)


# ---------------------------------------------------------------- compliance
def test_slate_is_sanitised_and_routed():
    c = SlateClient(territories(DIVERGENT))
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, CTX)
    check("concept_slate rules actually ran",
          len(r.sanitizer["checks_run"]) > 0, str(r.sanitizer["checks_run"]))
    check("cultural rules are among them",
          any(x.startswith("CULTURAL-") for x in r.sanitizer["checks_run"]),
          str(r.sanitizer["checks_run"]))
    check("review items are routed by queue when findings exist",
          isinstance(r.review_items, list))


def test_cultural_audit_uses_concept_scoped_audits():
    ctx = json.loads(json.dumps({k: v for k, v in CTX.items() if k != "services"}))
    ctx["services"] = CTX["services"]
    ctx["cultural_risk_audits"] = {}          # nothing audited
    c = SlateClient(territories(DIVERGENT))
    r = D.Disha(c, REG, competitor_archive=D.CompetitorArchive([]),
                cost_model=COSTS).run(GOOD_BRIEF, PACKET, ctx)
    check("unaudited concepts do not claim a low cultural risk",
          all(a["cultural_risk"]["level"] != "low"
              for a in r.slate["concepts_approved"]),
          str([a["cultural_risk"]["level"] for a in r.slate["concepts_approved"]]))
    check("unaudited slate requires human review",
          r.envelope["human_review_required"] is True)


def test_slate_aggregates_contained_concept_audits():
    """A slate has no concept_id of its own; it inherits from what it holds."""
    def run(audits):
        ctx = json.loads(json.dumps({k: v for k, v in CTX.items()
                                     if k != "services"}))
        ctx["services"] = CTX["services"]
        ctx["cultural_risk_audits"] = audits
        return D.Disha(SlateClient(territories(DIVERGENT)), REG,
                       competitor_archive=D.CompetitorArchive([]),
                       cost_model=COSTS).run(GOOD_BRIEF, PACKET, ctx)

    full = {f"C{i:02d}": {"completed": True, "level": "low"} for i in range(1, 13)}
    r = run(full)
    check("a fully audited slate passes the sanitizer outright",
          r.envelope["sanitizer_pass"] is True,
          str([i["rule_id"] for i in r.sanitizer.get("inconclusive", [])]))
    check("and raises no review queue", not r.review_items)

    partial = {k: v for k, v in full.items() if k != "C03"}
    r2 = run(partial)
    check("one unaudited concept blocks the whole slate",
          r2.envelope["sanitizer_pass"] is False)
    ev = " ".join(i.get("evidence") or "" for i in
                  r2.sanitizer.get("inconclusive", []))
    check("and the evidence names which concept is missing", "C03" in ev, ev)

    # Facet derivation lives in the FacetView, so a direct predicate call has
    # to go through one. Passing a raw dict resolves literal paths only, which
    # is correct and is why the sanitizer always wraps.
    import chitra_facets as F
    import chitra_predicates as P
    audits = {"C01": {"completed": True, "level": "low"},
              "C02": {"completed": True, "level": "high"}}
    view = F.FacetView({"concepts_approved": [{"id": "C01"}, {"id": "C02"}]},
                       "concept_slate", {"cultural_risk_audits": audits})
    audit, why = P.resolve_cultural_audit(view, {"cultural_risk_audits": audits})
    check("the aggregate takes the worst level, not the average",
          audit and audit["level"] == "high", f"{audit} ({why})")


def main():
    for fn in (test_slate_aggregates_contained_concept_audits,
               test_happy_path, test_divergence_gate_runs_before_scoring,
               test_unreadable_divergence_is_distinguished_from_short,
               test_divergence_prompt_does_not_ask_for_a_slate,
               test_truncated_divergence_is_salvaged,
               test_short_divergence_rejected,
               test_scoring_is_applied_by_code_not_the_model,
               test_model_cannot_self_approve_out_of_range_scores,
               test_missing_dependencies_are_declared_not_skipped,
               test_competitor_archive_kills_derivative_work,
               test_budget_envelope_kills_expensive_concepts,
               test_brief_interrogation_finds_structural_vulnerabilities,
               test_disha_reads_the_briefs_own_open_questions,
               test_research_coverage_gap_is_structural,
               test_interrogation_loop_is_bounded_and_returns_to_drishti,
               test_drishti_revise_rejects_an_invalid_revision,
               test_slate_is_sanitised_and_routed,
               test_cultural_audit_uses_concept_scoped_audits):
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
