"""
chitra_disha.py — Agent 2, Disha, the Creative Director.

Takes a locked creative_brief from Drishti and produces a concept_slate: three
to five approved territories plus a transparent log of everything killed.

FOUR THINGS THIS DOES THAT THE SCAFFOLD ASKS FOR AND NO IMPLEMENTATION HAD

  1. Brief interrogation as a real return path. The scaffold's first
     methodology step is to find three vulnerabilities in Drishti's brief and
     surface them before proceeding. That is a loop between two agents, and
     nothing implemented it. It is bounded here: two round trips, then Disha
     proceeds on the record with the unresolved vulnerabilities attached.

  2. Divergence enforced, not requested. Twelve territories is a schema
     minimum, and a minimum can be satisfied by one idea twelve times. The
     ADR-014 variance gate runs before the kill pass, so a padded slate is
     regenerated rather than scored, ranked and shipped.

  3. Scoring separated from generating. The scaffold's five dimensions and the
     16/25 bar are declared before generation and applied afterwards by code,
     not by the model marking its own homework. The model supplies scores; the
     arithmetic, the threshold and the kill tag are Disha's.

  4. Missing dependencies declared, not skipped. Two refusal triggers need
     inputs that do not exist yet: the competitor archive for the derivative
     check, and a production cost model for the budget envelope. Both are
     declared dependencies that return UNVERIFIABLE when absent and put the
     concept in front of a human, rather than passing quietly.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from jsonschema import Draft202012Validator

import chitra_cultural_assistant as CA
import chitra_sanitizer as S
from chitra_paths import spec_file
from chitra_drishti import (AnthropicClient, OfflineClient, _parse_json,
                            _schema_block, _with_campaign)
from chitra_eval_extras import CONCEPT_LENSES, VarianceGate

HERE = os.path.dirname(os.path.abspath(__file__))
SCAFFOLD_NAME = "CHITRA-v1_1-Agent-Prompt-Scaffolds.md"

SCORE_DIMENSIONS = ["relevance", "distinctiveness", "resonance",
                    "producibility", "cultural_safety"]
KILL_THRESHOLD = 16          # scaffold: concepts scoring under 16/25 are killed
MIN_DIVERGENT = 12
MIN_APPROVED, MAX_APPROVED = 3, 5

UNVERIFIABLE = "unverifiable"


@dataclass
class DishaResult:
    status: str          # slate | refused | interrogation | failed
    slate: Optional[dict] = None
    envelope: Optional[dict] = None
    reason: Optional[str] = None
    vulnerabilities: list = field(default_factory=list)
    unverifiable: list = field(default_factory=list)
    review_items: list = field(default_factory=list)
    sanitizer: Optional[dict] = None
    attempts: int = 0
    transcript: list = field(default_factory=list)

    def to_dict(self):
        d = {"status": self.status, "attempts": self.attempts}
        for k in ("reason", "slate", "envelope", "sanitizer"):
            if getattr(self, k):
                d[k] = getattr(self, k)
        for k in ("vulnerabilities", "unverifiable", "review_items"):
            if getattr(self, k):
                d[k] = getattr(self, k)
        return d


# --------------------------------------------------------------------------
# Declared dependencies
# --------------------------------------------------------------------------

class CompetitorArchive:
    """24-month category work, for the derivative-risk kill tag.

    Absent, the derivative check returns UNVERIFIABLE. It does not return
    'not derivative', which is what skipping it would silently mean.
    """

    def __init__(self, entries=None):
        self.entries = entries or []

    def similar(self, proposition, sector, threshold=0.45):
        from chitra_eval_extras import _bag, _cosine
        a = _bag(proposition)
        out = []
        for e in self.entries:
            if sector and e.get("sector") and e["sector"] != sector:
                continue
            s = _cosine(a, _bag(e.get("proposition", "")))
            if s >= threshold:
                out.append({"brand": e.get("brand"), "year": e.get("year"),
                            "similarity": round(s, 3),
                            "proposition": e.get("proposition", "")[:80]})
        return sorted(out, key=lambda x: -x["similarity"])


class ProductionCostModel:
    """Rough cost bands per production complexity, for the budget envelope.

    The scaffold kills a concept whose production cost exceeds 40% of the
    budget envelope. Absent a model, that check is UNVERIFIABLE.
    """

    ENVELOPE_SHARE = 0.40

    def __init__(self, bands=None):
        self.bands = bands or {}

    def estimate(self, complexity, campaign_budget_inr):
        band = self.bands.get(complexity)
        if band is None or not campaign_budget_inr:
            return None
        lo, hi = band
        return {"low_inr": lo, "high_inr": hi,
                "share_of_budget": round(hi / campaign_budget_inr, 3),
                "exceeds_envelope": hi > campaign_budget_inr * self.ENVELOPE_SHARE}


# --------------------------------------------------------------------------
# Prompt assembly
# --------------------------------------------------------------------------

def _fenced_after(text, heading):
    i = text.index(heading)
    return re.search(r"```\n(.*?)\n```", text[i:], re.S).group(1)


def _strip_output_format(scaffold):
    """Remove the scaffold's own OUTPUT FORMAT section for the divergence turn.

    The v1.1 scaffold defines Disha's output as a Concept Slate with a Killed
    Concepts Log. Divergence asks for a flat territories array. Appending
    "return territories" after ten thousand characters of "your output is a
    slate" loses, and did: a real run still returned concepts_approved after
    the contradicting schema block was removed, because the contradiction was
    never the schema block. It was the scaffold.

    The slate is still what Disha produces. It is assembled outside the model
    from scored territories, per the v1.3.8 decision to separate scoring from
    generating. The scaffold predates that decision.
    """
    m = re.search(r"\n\[OUTPUT FORMAT.*?(?=\n\[[A-Z][A-Z ]+|\Z)", scaffold, re.S)
    if not m:
        return scaffold, False
    return scaffold[:m.start()] + scaffold[m.end():], True


def load_system_prompt(tenant_id, resource_pack=None, phase="divergence"):
    doc = open(spec_file(SCAFFOLD_NAME), encoding="utf-8").read()
    wrapper = _fenced_after(doc, "## §B L0 SECURITY WRAPPER").replace(
        "{{tenant_id}}", tenant_id)
    scaffold = _fenced_after(doc, "## §2 AGENT 2 SCAFFOLD")
    stripped = False
    if phase == "divergence":
        scaffold, stripped = _strip_output_format(scaffold)
    parts = [wrapper, "", scaffold]
    if stripped:
        parts += ["", "[NOTE] The scaffold's OUTPUT FORMAT section has been "
                      "removed for this turn. The concept slate it describes is "
                      "assembled outside you from the territories you return "
                      "and the scores you give them. You do not write a slate."]
    if resource_pack:
        parts += ["", "[RESOURCE A — GLOBAL DYNAMIC RESOURCE PACK]",
                  json.dumps(resource_pack, indent=2, ensure_ascii=False)]
    parts += ["", "[OUTPUT CONTRACT — OVERRIDES THE MARKDOWN FORMAT ABOVE]",
              "Return a single JSON object. No prose, no fence, no preamble.",
              "During divergence return {\"territories\": [...]} with at least "
              f"{MIN_DIVERGENT} objects, each carrying title, proposition, "
              "visual_direction, verbal_hook, target_subsegment, lens, "
              "production_complexity.",
              f"lens must be one of: {', '.join(CONCEPT_LENSES)}.",
              "During scoring return {\"scores\": {\"<territory id>\": "
              "{relevance, distinctiveness, resonance, producibility, "
              "cultural_safety}}} with each dimension an integer 1 to 5.",
              "You do not decide which concepts are killed. You supply scores; "
              "the threshold and the kill tags are applied outside you.",
              "",
              "DO NOT return concepts_approved, concepts_killed, provenance, or "
              "any wrapper object. Those are assembled outside you from what "
              "you return. Your entire response is one object with one key.",
              "",
              "Correct: {\"territories\": [{\"title\": ..., \"proposition\": ..., "
              "\"visual_direction\": ..., \"verbal_hook\": ..., "
              "\"target_subsegment\": ..., \"lens\": ..., "
              "\"production_complexity\": ...}, ...]}",
              "",
              "Keep each field to one or two sentences. Twelve terse territories "
              "beat six elaborate ones that exhaust the response budget."]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------

class Disha:
    VERSION = "1.1"
    MAX_INTERROGATION_ROUNDS = 2

    def __init__(self, client, registry=None, variance_gate=None,
                 competitor_archive=None, cost_model=None,
                 cultural_assistant=None, max_repairs=2):
        self.client = client
        self.registry = registry or S.RuleRegistry.load(
            schema_path=os.path.join(HERE, "rule_object.schema.json"))
        self.gate = variance_gate or VarianceGate(min_items=MIN_DIVERGENT)
        self.archive = competitor_archive
        self.costs = cost_model
        self.cultural = cultural_assistant or CA.CulturalAssistant()
        self.max_repairs = max_repairs
        self.schema = json.load(open(os.path.join(HERE,
                                                  "concept_slate.schema.json"),
                                     encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)

    # -- step 1: interrogate the brief ------------------------------------
    def interrogate(self, brief, drishti=None, packet=None, context=None,
                    rounds=None):
        """Surface vulnerabilities to Drishti before proceeding.

        Returns (brief, vulnerabilities_outstanding). If a Drishti instance is
        supplied, unresolved vulnerabilities are sent back for a revised brief,
        bounded so two agents that can each demand revisions do not ping-pong.
        """
        rounds = self.MAX_INTERROGATION_ROUNDS if rounds is None else rounds
        outstanding = self._vulnerabilities(brief, packet)
        if not outstanding or drishti is None:
            return brief, outstanding

        for _ in range(rounds):
            if not outstanding:
                break
            revised = drishti.revise(brief, outstanding, packet, context)
            if revised is None:
                break
            brief = revised
            outstanding = self._vulnerabilities(brief, packet)
        return brief, outstanding

    def _vulnerabilities(self, brief, packet=None):
        """Structural interrogation. Deliberately not a model call.

        These are checks on whether the brief is decidable, not on whether it
        is good. A model asked to find three vulnerabilities will always find
        three, including in a brief that has none.

        The first real run exposed the gap this now closes: Drishti raised six
        open_questions_for_disha, the schema requires that field and addresses
        it to Disha by name, and Disha reported "no structural vulnerabilities"
        because it only ever ran checks of its own devising. A channel nobody
        reads is not a channel.
        """
        v = []

        # The brief's own questions come first. Drishti has read the packet and
        # written the brief; its questions outrank anything inferred here.
        for q in (brief.get("open_questions_for_disha") or []):
            text = q if isinstance(q, str) else (q.get("question") or str(q))
            v.append({"field": "open_questions_for_disha",
                      "issue": text,
                      "raised_by": "drishti"})

        # Research coverage against campaign geography. Drishti caught this on
        # the first real run by reading the packet; making it structural means
        # it is caught even when the model does not mention it.
        if packet:
            geo = {str(g).strip().lower() for g in (packet.get("geography") or [])}
            cov = {str(c).strip().lower()
                   for c in ((packet.get("audience_research") or {})
                             .get("coverage") or [])}
            if geo and cov:
                gap = sorted(g for g in geo if g not in cov)
                if gap:
                    v.append({"field": "audience_research.coverage",
                              "issue": f"Campaign geography includes "
                                       f"{', '.join(gap)} but the audience "
                                       f"research covers only "
                                       f"{', '.join(sorted(cov))}. Territories "
                                       f"for the uncovered market would rest on "
                                       f"insight that was never tested there.",
                              "raised_by": "disha"})
        insight = brief.get("insight", "") or ""
        if len(insight.split()) < 15:
            v.append({"raised_by": "disha", "field": "insight", "issue":
                      "Insight is too thin to build territories from. It reads "
                      "as an observation rather than a tension."})
        gap = brief.get("perception_gap", {}) or {}
        if gap.get("current") and gap.get("current") == gap.get("desired"):
            v.append({"raised_by": "disha", "field": "perception_gap", "issue":
                      "Current and desired perception are identical; there is "
                      "no gap to close."})
        if not (brief.get("success_metrics", {}) or {}).get("business_metrics"):
            v.append({"raised_by": "disha", "field": "success_metrics", "issue":
                      "No business metric, so distinctiveness cannot be traded "
                      "off against relevance."})
        aud = (brief.get("target_audience", {}) or {}).get("psychographics", {})
        if not aud.get("anxieties") and not aud.get("aspirations"):
            v.append({"raised_by": "disha",
                      "field": "target_audience.psychographics", "issue":
                      "Audience is demographic only. Resonance is unscoreable "
                      "without a stated anxiety or aspiration."})
        if len(brief.get("mandatories", []) or []) > 6:
            v.append({"raised_by": "disha", "field": "mandatories", "issue":
                      "More than six mandatories leaves no room for a concept "
                      "to be a concept."})
        return v

    # -- step 2: divergence, gated ---------------------------------------
    def diverge(self, brief, system, messages):
        territories, attempts, transcript = [], 0, []
        while attempts <= self.max_repairs:
            attempts += 1
            raw = self.client.complete(system, messages)

            # Diagnostics, carried over from Drishti. Without these a failed
            # divergence reports "0 territories supplied", which is true and
            # useless: it cannot distinguish a truncated response from an
            # unparseable one from a model that answered under a different key.
            entry = {"turn": attempts, "raw_len": len(raw)}
            entry.update(getattr(self.client, "last_meta", {}) or {})

            parsed = _parse_json(raw)
            if parsed is None:
                entry["parse_failed"] = True
                entry["raw_head"] = raw[:400]
                entry["raw_tail"] = raw[-200:]
                parsed = {}
            elif "territories" not in parsed:
                entry["unexpected_keys"] = sorted(parsed)[:8]
            batch = parsed.get("territories", [])
            entry["territories_returned"] = len(batch)

            if not territories:
                territories = batch
            elif len(batch) >= MIN_DIVERGENT:
                # The model regenerated the whole slate rather than the
                # replacements asked for. Both behaviours are reasonable
                # readings of the instruction, so handle both: a full-size
                # batch replaces, a partial batch tops up. Accumulating a full
                # batch onto survivors produced 18 then 24 territories, every
                # one of them a duplicate of something already there.
                territories = batch
            else:
                territories = territories + batch
            for i, t in enumerate(territories):
                t.setdefault("id", f"C{i + 1:02d}")

            res = self.gate.enforce(territories)
            entry["n"] = len(territories)
            entry["gate"] = res.to_dict()
            transcript.append(entry)
            if res.passed:
                return territories, transcript, None
            territories = [territories[i] for i in res.keep]
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                 f"Divergence gate: {res.feedback} Return only the replacement "
                 f"territories as {{\"territories\": [...]}}."}]
        last = transcript[-1] if transcript else {}
        if last.get("parse_failed"):
            why = ("the model's response never parsed as JSON. "
                   f"It began: {last.get('raw_head', '')[:160]!r}")
        elif last.get("unexpected_keys"):
            why = ("the model returned JSON without a 'territories' key. "
                   f"Keys present: {last['unexpected_keys']}")
        elif last.get("truncated"):
            why = "the response was truncated at max_tokens"
        else:
            why = "the divergence gate was not satisfied after repair turns"
        return territories, transcript, why

    # -- step 3: score and kill -------------------------------------------
    def score_and_kill(self, territories, model_scores, brief, context):
        approved, killed, unverifiable = [], [], []
        budget = (context.get("campaign", {}) or {}).get("budget_inr")
        sector = (context.get("campaign", {}) or {}).get("sector")

        for t in territories:
            tid = t["id"]
            raw = (model_scores or {}).get(tid, {})
            scores = {}
            for d in SCORE_DIMENSIONS:
                try:
                    scores[d] = max(1, min(5, int(raw.get(d, 3))))
                except (TypeError, ValueError):
                    scores[d] = 3
            total = sum(scores.values())
            scores["total"] = total

            # Hard kills, applied by code and before the score threshold.
            tag = rationale = None

            if self.archive is None:
                unverifiable.append({"concept": tid, "check": "derivative_risk",
                                     "reason": "competitor archive not connected"})
            else:
                hits = self.archive.similar(t.get("proposition", ""), sector)
                if hits:
                    tag = "indistinguishable_from_recent_category_work"
                    rationale = (f"Close to {hits[0]['brand']} {hits[0]['year']} "
                                 f"(similarity {hits[0]['similarity']}).")

            if tag is None:
                est = (self.costs.estimate(t.get("production_complexity"), budget)
                       if self.costs else None)
                if est is None:
                    unverifiable.append({"concept": tid, "check": "budget_envelope",
                                         "reason": "production cost model not "
                                                   "connected"})
                elif est["exceeds_envelope"]:
                    tag = "production_cost_exceeds_envelope"
                    rationale = (f"Estimated at {est['share_of_budget']:.0%} of "
                                 f"budget; envelope is "
                                 f"{ProductionCostModel.ENVELOPE_SHARE:.0%}.")

            if tag is None and total < KILL_THRESHOLD:
                tag = self._tag_from_scores(scores)
                rationale = (f"Scored {total}/25, below the {KILL_THRESHOLD} bar. "
                             f"Weakest: {min(SCORE_DIMENSIONS, key=lambda d: scores[d])}.")

            if tag:
                killed.append({"id": tid, "title": t.get("title", tid),
                               "kill_tag": tag, "rationale": rationale})
            else:
                approved.append((t, scores))

        approved.sort(key=lambda p: -p[1]["total"])
        for t, sc in approved[MAX_APPROVED:]:
            # v1.3.9: not a substantive failure. Tagging a 20/25 concept as
            # solves_wrong_problem poisons the killed log, which is the one
            # place institutional memory of near-misses lives. A later query
            # for "good ideas that did not fit" would find them filed as
            # structurally flawed and bury them permanently.
            killed.append({"id": t["id"], "title": t.get("title", t["id"]),
                           "kill_tag": "ranked_out_of_slate",
                           "rationale": f"Scored {sc['total']}/25, clearing the "
                                        f"{KILL_THRESHOLD} bar, but ranked outside "
                                        f"the top {MAX_APPROVED}. Revivable."})
        return approved[:MAX_APPROVED], killed, unverifiable

    @staticmethod
    def _tag_from_scores(scores):
        weakest = min(SCORE_DIMENSIONS, key=lambda d: scores[d])
        return {"relevance": "solves_wrong_problem",
                "distinctiveness": "insight_borrowed_not_earned",
                "resonance": "solves_wrong_problem",
                "producibility": "production_cost_exceeds_envelope",
                "cultural_safety": "cultural_risk_unmitigable"}[weakest]

    # -- step 4: cultural audit per surviving concept ---------------------
    def cultural_audit(self, approved, context):
        out, briefs = [], []
        for t, scores in approved:
            payload = dict(t)
            payload.setdefault("concept_id", t["id"])
            rb = self.cultural.assemble(payload, context, concept_id=t["id"])
            audits = context.get("cultural_risk_audits", {})
            audit = audits.get(t["id"])
            level = audit.get("level") if audit and audit.get("completed") else None
            # The register holds a REVIEWER'S findings, not the tool's
            # prompts. Writing the assistant's question into the artifact put
            # the tool's own text into the next scan's input: "figure", inside
            # a question about religious symbols, surfaced a gender axis on
            # concepts whose copy was clean. The register stays empty until a
            # human records something, and chitra_review.py fills it.
            #
            # No mitigation key until a reviewer records one either. An absent
            # mitigation is not the string "none", and asserting null where a
            # string is required is how a slate claims a mitigation it has not
            # got.
            register = []
            axes_flagged = [f.axis for f in rb.findings]
            out.append((t, scores, level, register, axes_flagged))
            if rb.findings:
                briefs.append(rb.to_dict())
        return out, briefs

    # -- main --------------------------------------------------------------
    def run(self, brief, packet, context, drishti=None, resource_pack=None):
        ctx = _with_campaign(context, packet)
        tenant = ctx.get("tenant", {}).get("tenant_id", "unknown")

        brief, vulns = self.interrogate(brief, drishti, packet, ctx)

        system = load_system_prompt(tenant, resource_pack, phase="divergence")
        messages = [{"role": "user", "content":
                     "[LOCKED CREATIVE BRIEF]\n" +
                     json.dumps(brief, indent=2, ensure_ascii=False) +
                     ("\n\n[OUTSTANDING VULNERABILITIES — proceed on the record]\n" +
                      json.dumps(vulns, indent=2) if vulns else "")}]

        territories, transcript, err = self.diverge(brief, system, messages)
        if err:
            return DishaResult(status="failed", reason=err, transcript=transcript,
                               vulnerabilities=vulns, attempts=len(transcript))

        score_msg = messages + [
            {"role": "user", "content":
             "Score every territory on the five dimensions, 1 to 5.\n" +
             json.dumps([{"id": t["id"], "title": t.get("title"),
                          "proposition": t.get("proposition")}
                         for t in territories], indent=2)}]
        raw = self.client.complete(
            load_system_prompt(tenant, resource_pack, phase="scoring"), score_msg)
        model_scores = (_parse_json(raw) or {}).get("scores", {})

        approved, killed, unverifiable = self.score_and_kill(
            territories, model_scores, brief, ctx)

        if len(approved) < MIN_APPROVED:
            return DishaResult(
                status="refused", vulnerabilities=vulns, unverifiable=unverifiable,
                transcript=transcript, attempts=len(transcript),
                reason=(f"Only {len(approved)} territories cleared the "
                        f"{KILL_THRESHOLD}/25 bar; the slate requires "
                        f"{MIN_APPROVED}. Returning to divergence rather than "
                        f"forwarding a weak slate."))

        audited, cultural_briefs = self.cultural_audit(approved, ctx)

        slate = {
            "concepts_approved": [
                {"id": t["id"], "title": t.get("title", t["id"]),
                 "proposition": (t.get("proposition") or "")[:200],
                 "visual_direction": (t.get("visual_direction") or "")[:500],
                 "verbal_hook": self._hook(t),
                 "target_subsegment": t.get("target_subsegment", "unspecified"),
                 "scores": sc,
                 "cultural_risk": {"level": level or "medium", "register": reg,
                                   "axes_to_review": axes or None},
                 "production_complexity": t.get("production_complexity", "medium")}
                for t, sc, level, reg, axes in audited],
            "concepts_killed": killed,
            "pitch_deck_uri": f"s3://chitra/{tenant}/pitch/"
                              f"{packet.get('campaign_id', 'campaign')}.pdf",
        }

        errors = ["{}: {}".format(".".join(str(p) for p in e.path) or "(root)",
                                  e.message)
                  for e in self.validator.iter_errors(slate)]
        if errors:
            return DishaResult(status="failed", transcript=transcript,
                               vulnerabilities=vulns, unverifiable=unverifiable,
                               attempts=len(transcript),
                               reason="Slate failed concept_slate.json: " +
                                      "; ".join(errors[:4]))

        result = S.sanitize("concept_slate", slate, ctx, self.registry)
        review = []
        try:
            import chitra_services as SV
            review = [i.to_dict()
                      for i in SV.HITLRouter(self.registry).route(
                          result, "concept_slate", packet.get("campaign_id"))]
        except Exception:
            pass

        return DishaResult(
            status="slate", slate=slate, attempts=len(transcript),
            vulnerabilities=vulns, unverifiable=unverifiable,
            review_items=review, sanitizer=result.to_dict(),
            transcript=transcript + [{"cultural_briefs": cultural_briefs}],
            envelope=self._envelope(slate, packet, ctx, result, unverifiable),
            reason=("Slate produced with unverifiable checks; see unverifiable"
                    if unverifiable else None))

    @staticmethod
    def _hook(t):
        h = t.get("verbal_hook")
        if isinstance(h, dict):
            return h
        alts = t.get("hook_alternates") or []
        return {"primary": str(h or t.get("title", "")),
                "alternates": (alts + ["", ""])[:2] if len(alts) < 2 else alts}

    def _envelope(self, slate, packet, ctx, result, unverifiable):
        return {
            "artifact_type": "concept_slate",
            "artifact_version": "1.0",
            "from_agent": "disha",
            "to_agent": ["roop", "vaani"],
            "cc_agent": ["lakshya"],
            "cc_purpose": "media feasibility cross-check per concept",
            "tenant_id": ctx.get("tenant", {}).get("tenant_id"),
            "campaign_id": packet.get("campaign_id"),
            "produced_by_version": f"Disha v{self.VERSION}",
            "sanitizer_pass": result.passed,
            "compliance_checks_run": result.checks_run,
            "human_review_required": result.human_review_required or
                                     bool(unverifiable),
            "unverifiable_checks": unverifiable,
            "confidentiality_vault": True,
            "status": "PENDING_JOINT_ACCEPTANCE",
        }
