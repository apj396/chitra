"""
chitra_drishti.py — Agent 1, Drishti, as a running process.

The first CHITRA agent to exist as something other than a prompt in a document.
Takes an onboarding packet, produces a creative_brief that validates against
creative_brief.json and passes the sanitizer, or refuses and says why.

WHAT THIS IS
    The full agent loop: L0 security wrapper, the v1.1 §1 scaffold, resource
    pack injection, pre-flight refusal checks, generation, schema validation,
    compliance sanitisation, and a bounded repair cycle that feeds violations
    back rather than failing.

WHAT IS STUBBED
    The model call. AnthropicClient is written and correct but needs a key.
    OfflineClient returns a fixture so the harness runs end to end today and
    the loop can be tested without spend or network. Swapping one for the
    other is a constructor argument.

    That is the honest state: the agent is built, the model is not connected.

REFUSALS AND HALTS ARE OUTCOMES, NOT ERRORS
    v1.1 §1 defines four refusal triggers and an incomplete-packet halt. Both
    are first-class results here. An agent that cannot say "I will not" or
    "I need more" is not implementing the scaffold.
"""

import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from jsonschema import Draft202012Validator

import chitra_sanitizer as S
from chitra_paths import spec_file

HERE = os.path.dirname(os.path.abspath(__file__))


def _note(msg):
    """Progress note for long calls, so a slow run does not look like a hang."""
    sys.stderr.write(f"  [client] {msg}\n")
    sys.stderr.flush()
SCAFFOLD_NAME = "CHITRA-v1_1-Agent-Prompt-Scaffolds.md"

# Categories whose advertising is prohibited outright. Checked before any
# generation, because the cheapest refusal is the one that never calls a model.
PROHIBITED_CATEGORIES = {
    "fantasy_sports_real_money", "rummy_real_money", "poker_real_money",
    "online_real_money_gaming", "gambling_gaming",
    "tobacco", "cigarettes", "tobacco_surrogate",
}

# The eight fields the packet always needed, plus the five the brief schema
# actually requires and the packet never carried. Drishti was halting at turn
# three on the missing five, correctly, and the preflight never caught it
# because it only tested for the eight.
REQUIRED_PACKET_FIELDS = [
    "client_name", "sector", "business_problem", "target_audience_description",
    "geography", "budget_inr", "timeline", "approval_chain",
    "audience_research", "business_metric_targets", "brand_metric_targets",
    "attribution_model", "brand_guidelines",
]

# The model signals an unfillable field rather than inventing one. The scaffold
# tells it to; the schema then rejects the signal because a string is not an
# object. Recognising the signal turns three wasted repair turns into one
# actionable halt.
BLOCK_SENTINELS = ("BLOCKED_PENDING_INPUT", "INSUFFICIENT_DATA",
                   "CANNOT_ASSERT_WITHOUT")


@dataclass
class DrishtiResult:
    status: str                       # brief | refused | clarification_required | failed
    brief: Optional[dict] = None
    envelope: Optional[dict] = None
    reason: Optional[str] = None
    missing_fields: list = field(default_factory=list)
    sanitizer: Optional[dict] = None
    attempts: int = 0
    transcript: list = field(default_factory=list)

    def to_dict(self):
        d = {"status": self.status, "attempts": self.attempts}
        for k in ("reason", "brief", "envelope", "sanitizer"):
            if getattr(self, k):
                d[k] = getattr(self, k)
        if self.missing_fields:
            d["missing_fields"] = self.missing_fields
        return d


# --------------------------------------------------------------------------
# Prompt assembly — read from the specification, never retyped
# --------------------------------------------------------------------------

def _fenced_after(text, heading):
    i = text.index(heading)
    m = re.search(r"```\n(.*?)\n```", text[i:], re.S)
    return m.group(1)


def _schema_block(filename, title):
    """Embed the schema the output must satisfy.

    The output contract used to name the schema file and not include it, so the
    model was asked to satisfy ten enum constraints it had never seen:
    income_band wants NCCS_B, attribution_model wants data_driven, and so on.
    Naming a contract is not stating it. This states it.
    """
    path = os.path.join(HERE, filename)
    if not os.path.exists(path):
        return ""
    schema = json.load(open(path, encoding="utf-8"))
    return ("\n[" + title + " — YOUR OUTPUT MUST VALIDATE AGAINST THIS]\n"
            + json.dumps(schema, indent=1, ensure_ascii=False)
            + "\n\nEvery enum is closed. Use the exact strings listed, not "
              "synonyms. Every required field must be present. Arrays with "
              "minItems must meet the minimum.\n")


def load_system_prompt(tenant_id, resource_pack=None):
    """Assemble L0 wrapper + Drishti scaffold from CHITRA v1.1.

    Read out of the document rather than pasted into this file. A prompt copied
    into code is a prompt that drifts from the specification the first time
    either changes, which is the same failure the rule registry had.
    """
    doc = open(spec_file(SCAFFOLD_NAME), encoding="utf-8").read()
    wrapper = _fenced_after(doc, "## §B L0 SECURITY WRAPPER")
    scaffold = _fenced_after(doc, "## §1 AGENT 1 SCAFFOLD")
    wrapper = wrapper.replace("{{tenant_id}}", tenant_id)

    parts = [wrapper, "", scaffold]
    if resource_pack:
        parts += ["", "[RESOURCE A — GLOBAL DYNAMIC RESOURCE PACK]",
                  json.dumps(resource_pack, indent=2, ensure_ascii=False)]
    parts += ["", "[OUTPUT CONTRACT — OVERRIDES THE MARKDOWN FORMAT ABOVE]",
              "Return a single JSON object. No prose, no markdown fence, no "
              "preamble. The markdown headings in the scaffold describe what each "
              "field must contain; the wire format is JSON because the handoff is "
              "machine-verified.",
              _schema_block("creative_brief.schema.json", "CREATIVE BRIEF SCHEMA")]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Model clients
# --------------------------------------------------------------------------

class AnthropicClient:
    """Real model client. Requires ANTHROPIC_API_KEY.

    Keeps what the API tells it. The first version discarded stop_reason, token
    usage and the error body, which made a failed run undiagnosable from the
    outside: three repair turns and no way to tell truncation from a refusal
    from a 400. Everything the API returns is now recorded on last_meta and
    surfaced in the run report.
    """

    def __init__(self, model="claude-sonnet-5", max_tokens=16000,
                 timeout=900, retries=2):
        # 900s because Disha's divergence call asks for twelve complete
        # territories in one response. Drishti averaged 77s for a single brief;
        # a slate is several times that, and the first real run died at 180s
        # with a valid brief already in hand.
        self.model, self.max_tokens = model, max_tokens
        self.timeout, self.retries = timeout, retries
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        self.last_meta = {}
        self.calls = 0

    def available(self):
        return bool(self.key)

    def complete(self, system, messages):
        import urllib.error
        import urllib.request

        self.calls += 1
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens,
                           "system": system, "messages": messages}).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"content-type": "application/json",
                     "x-api-key": self.key,
                     "anthropic-version": "2023-06-01"})
        data = None
        for attempt in range(1, self.retries + 2):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:600]
                if e.code in (429, 500, 529) and attempt <= self.retries:
                    wait = 10 * attempt
                    _note(f"HTTP {e.code}; retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise RuntimeError(
                    f"Anthropic API returned HTTP {e.code}.\n{detail}\n"
                    f"401 means the key is wrong or has quotes around it. "
                    f"400 usually means the model id is not available to your "
                    f"account. 429 means rate limited.") from None
            except (TimeoutError, socket.timeout):
                if attempt <= self.retries:
                    wait = 5 * attempt
                    _note(f"read timed out after {self.timeout}s "
                          f"(attempt {attempt}); retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise RuntimeError(
                    f"Anthropic API did not respond within {self.timeout}s "
                    f"after {attempt} attempt(s). Long generations can exceed "
                    f"this. Raise the timeout, or lower max_tokens.") from None
            except urllib.error.URLError as e:
                if isinstance(getattr(e, "reason", None), (TimeoutError,)) \
                        and attempt <= self.retries:
                    time.sleep(5 * attempt)
                    continue
                raise RuntimeError(
                    f"Could not reach api.anthropic.com: {e.reason}") from None

        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        self.last_meta = {
            "stop_reason": data.get("stop_reason"),
            "usage": data.get("usage", {}),
            "content_block_types": [b.get("type") for b in data.get("content", [])],
            "text_chars": len(text),
        }
        if data.get("stop_reason") == "max_tokens":
            self.last_meta["truncated"] = True
        return text


class OfflineClient:
    """Deterministic stand-in so the loop is testable without a key.

    Returns a fixture brief, and on a repair turn applies the fix the sanitizer
    asked for. That is enough to exercise every branch of the agent loop.
    """

    def __init__(self, fixture, repair=None):
        self.fixture, self.repair = fixture, repair or {}
        self.calls = 0

    def available(self):
        return True

    def complete(self, system, messages):
        self.calls += 1
        brief = json.loads(json.dumps(self.fixture))
        if self.calls > 1:
            _deep_update(brief, self.repair)
        return json.dumps(brief)


def _deep_update(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _deep_update(a[k], v)
        else:
            a[k] = v
    return a


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------

class Drishti:
    VERSION = "1.1"

    def __init__(self, client, registry=None, max_repairs=2):
        self.client = client
        self.registry = registry or S.RuleRegistry.load(
            schema_path=os.path.join(HERE, "rule_object.schema.json"))
        self.max_repairs = max_repairs
        self.schema = json.load(open(os.path.join(HERE, "creative_brief.schema.json"),
                                     encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)

    # -- pre-flight ------------------------------------------------------
    def preflight(self, packet):
        """v1.1 §1 refusal triggers and the incomplete-packet halt."""
        cat = packet.get("product_category")
        if cat in PROHIBITED_CATEGORIES:
            return DrishtiResult(
                status="refused",
                reason=f"Product category {cat!r} is in a banned advertising "
                       "category. No brief will be produced. Advertising online "
                       "money games is prohibited under Act 32 of 2025; tobacco "
                       "advertising is prohibited under COTPA 2003.")

        if packet.get("requires_misleading_claim"):
            return DrishtiResult(
                status="refused",
                reason="The packet requires a misleading claim as a mandatory. "
                       "The ASCI Code cannot be encoded away by a client "
                       "instruction.")

        aud = packet.get("target_audience_description", {})
        if isinstance(aud, dict) and aud.get("includes_minors") and \
                cat in {"alcohol", "alcohol_surrogate", "junk_food",
                        "high_sugar_beverage", "weight_loss"}:
            return DrishtiResult(
                status="refused",
                reason=f"The objective requires targeting minors with "
                       f"restricted-category content ({cat}).")

        prohibited_bases = {"caste", "religion_alone", "political_affiliation"}
        bases = {str(b).lower() for b in (packet.get("targeting_bases") or [])}
        hit = bases & prohibited_bases
        if hit:
            return DrishtiResult(
                status="refused",
                reason=f"The packet defines the audience using a prohibited "
                       f"targeting basis: {sorted(hit)[0]}.")

        # ADR-020: an uncovered region halts before any model call. Paying to
        # generate a brief for a market that cannot ship is waste, not safety.
        geo = {str(g).strip().lower() for g in (packet.get("geography") or [])}
        cov = {str(c).strip().lower()
               for c in ((packet.get("audience_research") or {})
                         .get("coverage") or [])}
        waived = {str(w.get("region", "")).strip().lower()
                  for w in (packet.get("research_coverage_waivers") or [])
                  if isinstance(w, dict) and w.get("approved_by")
                  and w.get("approved_on")}
        if geo and cov:
            gap = sorted(g for g in geo if g not in cov and g not in waived)
            if gap:
                return DrishtiResult(
                    status="clarification_required",
                    missing_fields=[f"audience_research.coverage: {g}"
                                    for g in gap],
                    reason=(f"Campaign geography includes {', '.join(gap)}, "
                            f"which the audience research does not cover. "
                            f"Remove the region from geography, extend the "
                            f"research, or record a waiver in "
                            f"research_coverage_waivers naming the approver "
                            f"and date."))

        # Completeness last. A campaign that will be refused outright should be
        # refused before anyone is asked to go and find missing research.
        missing = [f for f in REQUIRED_PACKET_FIELDS if not packet.get(f)]
        if missing:
            return DrishtiResult(
                status="clarification_required",
                reason="Onboarding Packet is incomplete. The scaffold halts rather "
                       "than inferring missing fields, so these must come from "
                       "the client before a brief exists.",
                missing_fields=missing)
        return None

    # -- main loop -------------------------------------------------------
    def run(self, packet, context, resource_pack=None):
        halt = self.preflight(packet)
        if halt:
            return halt

        system = load_system_prompt(context.get("tenant", {}).get("tenant_id", "unknown"),
                                    resource_pack)
        messages = [{"role": "user", "content":
                     "[ONBOARDING PACKET]\n" + json.dumps(packet, indent=2,
                                                          ensure_ascii=False)}]
        transcript, attempts = [], 0

        while attempts <= self.max_repairs:
            attempts += 1
            raw = self.client.complete(system, messages)
            entry = {"turn": attempts, "raw_len": len(raw)}
            entry.update(getattr(self.client, "last_meta", {}) or {})
            transcript.append(entry)

            brief = _parse_json(raw)
            if brief is None:
                entry["parse_failed"] = True
                entry["raw_head"] = raw[:400]
                entry["raw_tail"] = raw[-200:]
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content":
                              "That was not parseable JSON. Return only the JSON "
                              "object, starting with { and ending with }. No "
                              "preamble, no markdown fence, no explanation."}]
                continue

            blocked = _blocked_fields(brief)
            if blocked:
                return DrishtiResult(
                    status="clarification_required", attempts=attempts,
                    transcript=transcript, missing_fields=sorted(blocked),
                    reason=("Drishti refused to fabricate fields the Onboarding "
                            "Packet does not support. The scaffold forbids "
                            "inventing audience or performance data, so these "
                            "must come from the client before a brief exists."))

            schema_errors = []
            for e in sorted(self.validator.iter_errors(brief),
                            key=lambda x: str(x.path)):
                where = ".".join(str(x) for x in e.path) or "(root)"
                line = f"{where}: {e.message}"
                # Name the allowed values inline. "is not one of [...]" already
                # carries them, but a truncated message loses the tail, and the
                # tail is the part the model needs.
                allowed = (e.schema or {}).get("enum")
                if allowed:
                    line += f"  ALLOWED: {allowed}"
                schema_errors.append(line)
            if schema_errors:
                transcript[-1]["schema_errors"] = schema_errors
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content":
                              "The brief failed creative_brief.json validation. Fix "
                              "these and return the corrected JSON only:\n- " +
                              "\n- ".join(schema_errors)}]
                continue

            # Compliance. The brief is an artifact like any other, and the
            # facet layer resolves rule vocabulary against it, so no agent-local
            # adapter is needed. v1.3.5 §2.3 had one here; it is gone.
            result = S.sanitize("creative_brief", brief,
                                _with_campaign(context, packet), self.registry)
            transcript[-1]["sanitizer"] = {
                "pass": result.passed,
                "violations": [v["rule_id"] for v in result.violations],
                "inconclusive": [i["rule_id"] for i in result.inconclusive],
            }

            if result.passed:
                return DrishtiResult(
                    status="brief", brief=brief, attempts=attempts,
                    envelope=self._envelope(brief, packet, context, result),
                    sanitizer=result.to_dict(), transcript=transcript)

            if result.violations:
                feedback = "\n- ".join(
                    f"{v['rule_id']}: {v['message']} Fix: {v['suggested_fix']}"
                    for v in result.violations)
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content":
                              "The brief was blocked by the compliance sanitizer. "
                              "Correct these and return the JSON only:\n- " + feedback}]
                continue

            # Inconclusive only: nothing the model can fix. Route to a human.
            return DrishtiResult(
                status="brief", brief=brief, attempts=attempts,
                envelope=self._envelope(brief, packet, context, result),
                sanitizer=result.to_dict(), transcript=transcript,
                reason="Brief produced, held for human review: " +
                       "; ".join(i["rule_id"] for i in result.inconclusive))

        return DrishtiResult(status="failed", attempts=attempts,
                             transcript=transcript,
                             reason="Exhausted repair attempts without a brief that "
                                    "both validates and sanitises.")

    def revise(self, brief, vulnerabilities, packet=None, context=None):
        """Return path for Disha's brief interrogation.

        Disha's first methodology step is to surface three vulnerabilities in
        the brief before proceeding. That only means anything if Drishti can
        act on them, so this is the other half of that loop. Returns a revised
        brief that still validates and still sanitises, or None if the model
        cannot produce one, which lets Disha proceed on the record rather than
        stall.
        """
        system = load_system_prompt(
            (context or {}).get("tenant", {}).get("tenant_id", "unknown"))
        messages = [
            {"role": "user", "content":
             "[YOUR PREVIOUS BRIEF]\n" + json.dumps(brief, indent=2,
                                                    ensure_ascii=False)},
            {"role": "user", "content":
             "[DISHA HAS RETURNED THE BRIEF]\nThese are structural "
             "vulnerabilities, not taste notes. Fix them and return the "
             "corrected brief as JSON only:\n" +
             json.dumps(vulnerabilities, indent=2)}]
        raw = self.client.complete(system, messages)
        revised = _parse_json(raw)
        if revised is None:
            return None
        if list(self.validator.iter_errors(revised)):
            return None
        if packet is not None and context is not None:
            result = S.sanitize("creative_brief", revised,
                                _with_campaign(context, packet), self.registry)
            if result.violations:
                return None
        return revised

    def _envelope(self, brief, packet, context, result):
        """v1.2 §F.0 handoff envelope."""
        return {
            "artifact_type": "creative_brief",
            "artifact_version": "1.0",
            "from_agent": "drishti",
            "to_agent": "disha",
            "tenant_id": context.get("tenant", {}).get("tenant_id"),
            "campaign_id": packet.get("campaign_id"),
            "produced_by_version": f"Drishti v{self.VERSION}",
            "sanitizer_pass": result.passed,
            "compliance_checks_run": result.checks_run,
            "human_review_required": result.human_review_required,
            "status": "PENDING_DISHA_SIGNOFF",
        }


def _blocked_fields(node, path=""):
    """Find fields the model explicitly declined to invent."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += _blocked_fields(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _blocked_fields(v, f"{path}[{i}]")
    elif isinstance(node, str):
        if any(sent in node for sent in BLOCK_SENTINELS):
            out.append(path)
    return out


def _parse_json(raw):
    """Parse a model response, recovering from fences and truncation.

    Turn-1 divergence failed in four of four real runs, and two of them were a
    markdown fence around JSON the model never got to close. Salvaging the
    complete elements of a truncated array turns a wasted call into a partial
    one, and the divergence gate is already built to ask for the remainder.
    """
    raw = (raw or "").strip()
    raw = re.sub(r"^```(json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return _salvage_truncated(raw)


def _salvage_truncated(raw):
    """Recover the complete objects from an array that was cut off mid-write."""
    m = re.search(r'"(\w+)"\s*:\s*\[', raw)
    if not m:
        return None
    key, start = m.group(1), m.end()
    items, depth, buf, in_str, esc = [], 0, [], False, False
    for ch in raw[start:]:
        if in_str:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            buf.append(ch)
            continue
        if ch == "{":
            depth += 1
        if depth:
            buf.append(ch)
        if ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    items.append(json.loads("".join(buf)))
                except json.JSONDecodeError:
                    pass
                buf = []
    return {key: items} if items else None


def _with_campaign(context, packet):
    """Lift campaign-level facts out of the onboarding packet into context.

    product_category, sector, concept_id and channel are campaign facts, not
    artifact fields, and chitra_facets declares them as context-sourced. This
    is the whole of what used to be a per-agent adapter.
    """
    ctx = dict(context)
    campaign = dict(ctx.get("campaign", {}))
    for k in ("product_category", "sector", "concept_id", "channel",
              "platform_family", "campaign_id"):
        if packet.get(k) is not None:
            campaign[k] = packet[k]
    if packet.get("targeting_bases"):
        campaign["targeting_bases"] = packet["targeting_bases"]
    ctx["campaign"] = campaign
    return ctx
