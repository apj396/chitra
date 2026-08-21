"""
chitra_cultural_assistant.py — ADR-001. An evidence assembler, not a reviewer.

WHAT IT DOES
    Reads a concept or artifact, identifies which cultural axes it touches,
    pulls the matching entries from the cultural risk register, attaches
    relevant precedent, and drafts a brief for the named human reviewer.

WHAT IT DOES NOT DO, BY DESIGN
    It does not adopt a perspective. It does not claim to speak for a caste, a
    religion, a gender, a region or a language community. It does not issue a
    risk level, a verdict, a score, or a recommendation to approve.

    Those constraints are the whole point. A persona that represents a
    community is a synthetic stand-in for people who are not in the room, and
    a confidence number attached to it reads as consultation when no
    consultation happened. When it is wrong, the record says a perspective was
    consulted, which is worse than no record at all.

    So the split is: the assistant does retrieval and drafting, which is most
    of the reviewer's work and none of the reviewer's authority. The named
    human decides. Escalation to external counsel is unchanged.

RELATIONSHIP TO THE SANITIZER
    The five cultural rules still return INCONCLUSIVE without a completed
    audit for the concept, exactly as before. This does not change any gate.
    It changes how long the human takes to complete one.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))

AXES = {
    "religion": {
        "rule": "CULTURAL-RELIGION-001",
        "markers": ["temple", "mosque", "church", "gurudwara", "puja", "namaz",
                    "prayer", "deity", "idol", "prasad", "festival", "diwali",
                    "eid", "christmas", "holi", "ganesh", "navratri", "ramzan",
                    "priest", "imam", "sacred", "ritual", "tilak", "hijab",
                    "turban", "cross", "om", "crescent"],
        "prompt": "Does the depiction place a religious symbol, practice or "
                  "figure in a commercial or comic frame, and would a "
                  "practising member of that tradition read it as respectful?",
    },
    "caste": {
        "rule": "CULTURAL-CASTE-001",
        "markers": ["surname", "community", "traditional occupation", "sweeper",
                    "cobbler", "barber", "washerman", "manual scavenging",
                    "village hierarchy", "purity", "pollution", "untouchab",
                    "reservation", "quota", "dalit", "adivasi", "tribal"],
        "prompt": "Does the depiction attach an occupation, a living standard "
                  "or a moral quality to a community, and does the casting "
                  "reproduce a hierarchy the ad does not intend?",
    },
    "gender": {
        "rule": "CULTURAL-GENDER-001",
        "markers": ["housewife", "homemaker", "kitchen", "mother-in-law",
                    "bride", "dowry", "fairness", "slim", "figure", "curvy",
                    "manly", "sissy", "girly", "working woman", "career woman",
                    "beauty standard", "body", "weight"],
        "prompt": "Does the humour or the aspiration rest on a gender "
                  "expectation, a body standard, or a role assumption, and who "
                  "is the butt of the joke?",
    },
    "region": {
        "rule": "CULTURAL-REGION-001",
        "markers": ["accent", "dialect", "south indian", "north indian",
                    "bihari", "madrasi", "bhaiya", "punjabi", "bengali",
                    "gujarati", "marathi", "tamil", "malayali", "northeast",
                    "chinky", "village", "small town", "metro", "tier 3"],
        "prompt": "Is a regional accent, language or place used as a marker of "
                  "backwardness, comedy or aspiration, and would a viewer from "
                  "that region recognise themselves or a caricature?",
    },
    "political": {
        "rule": "CULTURAL-POLITICAL-001",
        "markers": ["election", "vote", "party", "minister", "government",
                    "policy", "protest", "flag", "national", "patriotic",
                    "soldier", "border", "army", "freedom fighter"],
        "prompt": "Does the creative take a side on a contested public question, "
                  "or borrow national or military symbolism for a commercial "
                  "claim?",
    },
}


@dataclass
class AxisFinding:
    axis: str
    rule_id: str
    triggered_by: list = field(default_factory=list)
    register_entries: list = field(default_factory=list)
    precedent: list = field(default_factory=list)
    question_for_reviewer: str = ""


@dataclass
class ReviewBrief:
    concept_id: Optional[str]
    axes_touched: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    inherited_audit: Optional[dict] = None
    inheritance_note: str = ""
    reviewer: Optional[str] = None
    escalation_path: str = "external counsel"

    def to_dict(self):
        return {
            "concept_id": self.concept_id,
            "axes_touched": self.axes_touched,
            "inheritance_note": self.inheritance_note,
            "reviewer": self.reviewer,
            "escalation_path": self.escalation_path,
            "findings": [
                {"axis": f.axis, "rule_id": f.rule_id,
                 "triggered_by": f.triggered_by,
                 "register_entries": f.register_entries,
                 "precedent": f.precedent,
                 "question_for_reviewer": f.question_for_reviewer}
                for f in self.findings],
            "verdict": None,
            "verdict_note": "This brief carries no assessment. The named "
                            "reviewer records the risk level and the decision.",
        }

    def to_markdown(self):
        lines = [f"# Cultural review brief — concept {self.concept_id or 'unscoped'}",
                 "",
                 f"Reviewer: {self.reviewer or 'UNASSIGNED'}    "
                 f"Escalation: {self.escalation_path}",
                 f"Inheritance: {self.inheritance_note}", ""]
        if not self.findings:
            lines += ["No cultural axis markers detected. The reviewer should "
                      "still confirm, since marker matching finds surfaces, not "
                      "meaning.", ""]
        for f in self.findings:
            lines += [f"## {f.axis.title()} ({f.rule_id})", "",
                      f"Surfaced by: {', '.join(f.triggered_by) or 'context'}", ""]
            if f.register_entries:
                lines.append("Register entries:")
                lines += [f"- {e}" for e in f.register_entries]
                lines.append("")
            if f.precedent:
                lines.append("Precedent:")
                lines += [f"- {p}" for p in f.precedent]
                lines.append("")
            lines += [f"**Question for you:** {f.question_for_reviewer}", ""]
        lines += ["---", "",
                  "This brief assembles evidence. It does not assess it. "
                  "Record your risk level per axis and sign the register entry."]
        return "\n".join(lines)


# Keys holding creative copy. The scanner reads these and nothing else.
CREATIVE_KEYS = {
    "title", "proposition", "visual_direction", "verbal_hook", "primary",
    "alternates", "target_subsegment", "headline", "tagline", "caption",
    "first_line", "core_message", "insight", "day_in_the_life", "script",
    "copy", "body", "current", "desired", "values", "anxieties", "aspirations",
}

# Keys holding the system's own output. Never scanned.
METADATA_KEYS = {
    "cultural_risk", "register", "concern", "mitigation", "question_for_reviewer",
    "scores", "kill_tag", "rationale", "notes", "provenance", "sanitizer",
    "compliance", "checks_run", "violations", "warnings", "inconclusive",
    "findings", "reviewer", "per_axis", "audit", "envelope",
}


def _strings(node, key=None, inside_creative=False):
    """Creative copy only.

    The assistant used to scan the whole payload. Disha writes the assistant's
    own question into cultural_risk.register[].concern, so the next scan found
    the word 'figure' inside its own question about religious symbols and
    reported a gender axis on two concepts whose copy was clean. A tool that
    reads its own output as evidence will confirm itself indefinitely, and the
    contamination grows with every cycle.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if k in METADATA_KEYS:
                continue
            yield from _strings(v, k, inside_creative or k in CREATIVE_KEYS)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, key, inside_creative)
    elif isinstance(node, str):
        if inside_creative or key in CREATIVE_KEYS:
            yield node


class CulturalAssistant:
    def __init__(self, register=None, precedent=None):
        self.register = register or {}
        self.precedent = precedent or {}

    @staticmethod
    def _matches(marker, text):
        """Whole-word matching.

        Substring matching found 'om' inside from, some, comfort and custom,
        and 'figure' inside 'figures out'. A reviewer sent to assess religious
        depiction because the copy said "hanging from the rail" learns to
        distrust the brief, and a brief nobody trusts is worse than no brief.
        Multi-word markers match as a phrase; the boundary is on the ends.
        """
        return re.search(r"(?<!\w)" + re.escape(marker) + r"(?!\w)",
                         text) is not None

    def assemble(self, artifact, context, concept_id=None):
        import chitra_predicates as P
        payload = artifact.payload if hasattr(artifact, "payload") else artifact
        text = " ".join(_strings(payload)).lower()
        concept_id = concept_id or payload.get("concept_id") or \
            context.get("campaign", {}).get("concept_id")

        audit, note = P.resolve_cultural_audit(payload, context)

        findings = []
        for axis, spec in AXES.items():
            hits = sorted({m for m in spec["markers"]
                           if self._matches(m, text)})
            declared = context.get("declared_axes", [])
            if not hits and axis not in declared:
                continue
            findings.append(AxisFinding(
                axis=axis,
                rule_id=spec["rule"],
                triggered_by=hits or ["declared in context"],
                register_entries=self.register.get(axis, []),
                precedent=self.precedent.get(axis, []),
                question_for_reviewer=spec["prompt"]))

        return ReviewBrief(
            concept_id=concept_id,
            axes_touched=[f.axis for f in findings],
            findings=findings,
            inherited_audit=audit,
            inheritance_note=note,
            reviewer=context.get("cultural_reviewer"))
