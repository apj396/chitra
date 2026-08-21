"""
chitra_services.py — the small services the rules depend on.

Three of them, all decided in the ADR register of 12 August 2026:

  CredentialRegistry   ADR-006. Replaces permanent human review on the two ASCI
                       qualification rules, and carries the CA attestation that
                       lifts the alcohol block under ADR-013.
  RegDB                Serves the DMRA Schedule (ADR-010) and the MeitY
                       restricted-country list.
  HITLRouter           ADR-007. Routes a review item to the queue that owns the
                       rule's source, instead of sending every human_review_on_fail
                       rule to the cultural reviewer.

File-backed on purpose. These are lookup tables with a lookup method, and a
database would be ceremony around a dictionary.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# ADR-006 / ADR-013 — credential registry
# --------------------------------------------------------------------------

class CredentialRegistry:
    """Resolves credential ids to a validity record.

    Two credential families so far:

      qualification   an influencer's professional qualification, for
                      ASCI-BFSI-001 and ASCI-HEALTH-001
      ca_attestation  an independent CA firm's certificate that a brand
                      extension meets the ASCI Brand Extension Guidelines
                      thresholds, which is what lifts the alcohol block

    The point of the CA family is that CHITRA never evaluates the financial
    criteria. ASCI already requires the evidence to be certified by an
    independent CA firm, so the qualifying test is whether that certificate
    exists and resolves, not whether a turnover ratio clears a threshold.
    A creative classifier has no business parsing a balance sheet.
    """

    def __init__(self, path=None, records=None):
        if records is not None:
            self.records = records
        else:
            path = path or os.path.join(HERE, "credentials.json")
            self.records = (json.load(open(path, encoding="utf-8"))["credentials"]
                            if os.path.exists(path) else {})

    def lookup(self, credential_id):
        if not credential_id:
            return None
        rec = self.records.get(credential_id)
        if rec is None:
            return None
        return dict(rec)

    def ca_attestation(self, attestation_id):
        """Return a CA attestation only if it is one, is valid, and is current."""
        rec = self.lookup(attestation_id)
        if rec is None or rec.get("family") != "ca_attestation":
            return None
        if not rec.get("valid"):
            return None
        return rec


# --------------------------------------------------------------------------
# ADR-010 — regulatory data
# --------------------------------------------------------------------------

class RegDB:
    def __init__(self, dmra_path=None, restricted_countries=None, dgci_approved=None):
        dmra_path = dmra_path or os.path.join(HERE, "dmra_schedule.json")
        self._dmra = (json.load(open(dmra_path, encoding="utf-8"))
                      if os.path.exists(dmra_path) else None)
        self._restricted = restricted_countries or []
        self._dgci = set(dgci_approved or [])

    def dmra_schedule_conditions(self):
        if not self._dmra:
            return []
        terms = list(self._dmra["conditions"])
        for base, alts in self._dmra.get("synonyms", {}).items():
            terms.extend(alts)
        terms.extend(self._dmra.get("section_3_prohibitions", []))
        return terms

    def dmra_verified(self):
        return bool(self._dmra and self._dmra.get("verified"))

    def restricted_countries(self):
        return self._restricted

    def dgci_approved(self, product_id):
        return product_id in self._dgci


# --------------------------------------------------------------------------
# consent-vault — DPDP consent of record
# --------------------------------------------------------------------------

class ConsentUnavailable(Exception):
    """The vault could not be reached or read.

    Distinct from "no consent on record", and the distinction matters: one is
    a verified absence, the other is an unverified anything. Both block.
    """


class ConsentVault:
    """The consent of record for DPDP-CONSENT-001, DPDP-CHILDREN-001 and
    PLATFORM-TOS-WHATSAPP-001.

    File-backed, like the credential registry and the mark register. It does
    not need to be a database to prove the gate logic works.

    DESIGN POINTS THAT ARE NOT INCIDENTAL

    Identifiers are never stored raw. A record holds `principal_hash`, the
    SHA-256 of the phone number or account id. A consent vault that holds a
    million phone numbers is itself the breach it exists to prevent, and DPDP
    does not exempt the compliance system from DPDP.

    Consent is bound, not global. A record carries a purpose, a channel and a
    consent type, and a lookup that ignores any of the three is not checking
    consent, it is checking that a row exists. Retargeting consent does not
    authorise a WhatsApp broadcast.

    Expiry is computed at read time. A record that was valid when written and
    has since lapsed reads as expired, because nothing sweeps the file.

    Withdrawal is a state, not a deletion. DPDP gives a right to withdraw and
    a separate right to erase, and collapsing them loses the record that
    consent was once given and then taken back, which is the thing a Board
    inquiry asks about.
    """

    STATUSES = {"valid", "withdrawn", "expired", "superseded"}

    def __init__(self, path=None, records=None, audit=None, available=True):
        self.audit = audit
        self._available = available
        if records is not None:
            self.records = records
            self.path = None
            return
        self.path = path or os.path.join(HERE, "consent_records.json")
        try:
            self.records = (json.load(open(self.path, encoding="utf-8"))
                            ["consents"] if os.path.exists(self.path) else {})
        except (OSError, ValueError, KeyError) as e:
            raise ConsentUnavailable(f"consent vault unreadable: {e}") from None

    @staticmethod
    def hash_identifier(raw):
        """Callers hash before they hand anything over. Never store the raw."""
        return hashlib.sha256(str(raw).strip().lower().encode()).hexdigest()

    def _effective(self, rec, now=None):
        now = now or datetime.now(timezone.utc)
        if rec.get("status") in ("withdrawn", "superseded"):
            return rec["status"]
        exp = rec.get("expires_at")
        if exp:
            try:
                if datetime.fromisoformat(exp).replace(
                        tzinfo=timezone.utc) <= now:
                    return "expired"
            except ValueError:
                return "expired"
        return rec.get("status", "valid")

    def lookup(self, consent_id, now=None):
        """Return the record with its status computed, or None if unknown.

        Raises ConsentUnavailable when the vault itself cannot answer. A caller
        must be able to tell "no consent" from "cannot say".
        """
        if not self._available:
            raise ConsentUnavailable("consent vault unreachable")
        if not consent_id:
            return None
        rec = self.records.get(consent_id)
        if rec is None:
            return None
        out = dict(rec)
        out["status"] = self._effective(rec, now)
        out.pop("principal_identifier", None)   # defence in depth
        return out

    def is_authorised(self, consent_id, purpose=None, channel=None,
                      consent_type=None, now=None):
        """Bound check. Returns (ok, reason)."""
        rec = self.lookup(consent_id, now)
        if rec is None:
            return False, "no consent on record for this artifact"
        if rec["status"] != "valid":
            return False, f"consent is {rec['status']}"
        if purpose and rec.get("purpose") != purpose:
            return False, (f"consent covers purpose {rec.get('purpose')!r}, "
                           f"artifact processes for {purpose!r}")
        if channel and rec.get("channel") != channel:
            return False, (f"consent is for the {rec.get('channel')!r} channel, "
                           f"not {channel!r}")
        if consent_type and rec.get("consent_type") != consent_type:
            return False, (f"consent type is {rec.get('consent_type')!r}, "
                           f"{consent_type!r} required")
        return True, "valid"

    def withdraw(self, consent_id, reason="data principal withdrawal", now=None):
        """DPDP right to withdraw. A state change, not a deletion."""
        rec = self.records.get(consent_id)
        if rec is None:
            raise KeyError(f"unknown consent id {consent_id!r}")
        rec["status"] = "withdrawn"
        rec["withdrawn_at"] = (now or datetime.now(timezone.utc)).isoformat()
        rec["withdrawal_reason"] = reason
        self._persist()
        if self.audit:
            self.audit.append("compliance.consent_withdrawn",
                              {"consent_id": consent_id, "reason": reason,
                               "principal_hash": rec.get("principal_hash")})
        return rec

    def _persist(self):
        if not self.path:
            return
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"consents": self.records}, f, indent=2,
                      ensure_ascii=False)


# --------------------------------------------------------------------------
# Trademark and IP pre-clearance
# --------------------------------------------------------------------------

class LegalPrecheck:
    """Minimal mark-register lookup for IP-TRADEMARK-001.

    Fails closed by construction: an unavailable service returns None from the
    sanitizer's perspective and the rule goes inconclusive, which routes to
    legal. That is the correct posture for a GRC engine and it is also the
    reason this service is worth building — every artifact was hitting that
    path, so the rule was a permanent human-review item rather than a control.

    Two checks:
      exact and near collision against a register of marks the tenant does not
      own, scoped by Nice class where the artifact declares one; and
      descriptive-use detection, so a competitor mark used comparatively is
      flagged for substantiation rather than treated as infringement.

    File-backed, like the credential registry. A trademark register is a table.
    """

    def __init__(self, path=None, marks=None):
        if marks is not None:
            self.marks = marks
        else:
            path = path or os.path.join(HERE, "mark_register.json")
            self.marks = (json.load(open(path, encoding="utf-8"))["marks"]
                          if os.path.exists(path) else [])

    @staticmethod
    def _normalise(text):
        return re.sub(r"[^a-z0-9]+", "", (text or "").lower())

    def _candidate_strings(self, artifact):
        payload = getattr(artifact, "payload", artifact)
        out = []

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ("title", "verbal_hook", "primary", "core_message",
                             "proposition", "caption", "first_line", "headline",
                             "tagline"):
                        if isinstance(v, str):
                            out.append(v)
                        else:
                            walk(v)
                    else:
                        walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(payload)
        return out

    def collisions(self, artifact, tenant_id=None, nice_classes=None):
        hits = []
        strings = self._candidate_strings(artifact)
        blob = " ".join(strings).lower()
        norm_blob = self._normalise(blob)
        for m in self.marks:
            if tenant_id and m.get("owner_tenant_id") == tenant_id:
                continue
            if nice_classes and m.get("nice_class") and \
                    m["nice_class"] not in nice_classes:
                continue
            mark = m.get("mark", "")
            if not mark:
                continue
            exact = mark.lower() in blob
            near = self._normalise(mark) in norm_blob
            if exact or near:
                hits.append({"mark": mark, "owner": m.get("owner"),
                             "nice_class": m.get("nice_class"),
                             "status": m.get("status", "registered"),
                             "match": "exact" if exact else "near"})
        return hits

    def trademark_clearance_passed(self, artifact, tenant_id=None,
                                   nice_classes=None):
        return not self.collisions(artifact, tenant_id, nice_classes)


# --------------------------------------------------------------------------
# ADR-007 — HITL routing
# --------------------------------------------------------------------------

QUEUE_BY_SOURCE = {
    "DPDP": "dpo",
    "MEITY": "dpo",
    "CULTURAL_REGISTER": "cultural_review",
    "CONSTITUTION": "cultural_review",
    "COPYRIGHT_ACT": "legal",
    "TRADEMARKS_ACT": "legal",
    "IT_RULES": "legal",
    "ONLINE_GAMING_ACT": "legal",
    "ASCI": "compliance",
    "CCPA_DARK": "compliance",
    "CPA": "compliance",
    "DMRA": "compliance",
    "MOHFW": "compliance",
    "RBI": "compliance",
    "SEBI": "compliance",
    "IRDAI": "compliance",
    "TRAI": "compliance",
    "RERA": "compliance",
    "COTPA": "compliance",
    "EXCISE": "compliance",
    "PLATFORM_TOS": "ad_ops",
    "CHITRA_INTERNAL": "brand_owner",
}

# Hours. A DPDP consent failure and a typography nitpick do not share an SLA.
SLA_BY_QUEUE = {
    "dpo": 4,
    "legal": 24,
    "compliance": 24,
    "cultural_review": 48,
    "ad_ops": 8,
    "brand_owner": 24,
    "unrouted": 24,
}


@dataclass
class ReviewItem:
    queue: str
    sla_hours: int
    rule_ids: list = field(default_factory=list)
    reason: str = ""
    artifact_type: Optional[str] = None
    campaign_id: Optional[str] = None

    def to_dict(self):
        return {"queue": self.queue, "sla_hours": self.sla_hours,
                "rule_ids": self.rule_ids, "reason": self.reason,
                "artifact_type": self.artifact_type, "campaign_id": self.campaign_id}


class HITLRouter:
    """Splits a sanitizer result into per-queue review items.

    Before ADR-007 there was one gate labelled cultural risk whose trigger was
    "any rule with human_review_on_fail fires". Nine rules set that flag,
    including DPDP-CONSENT-001, so consent failures landed in a DEI reviewer's
    queue under a 24-hour SLA. Approvers learn to rubber-stamp a queue whose
    contents do not match its name.
    """

    def __init__(self, registry, queue_map=None, sla_map=None):
        self.registry = registry
        self.queues = queue_map or QUEUE_BY_SOURCE
        self.slas = sla_map or SLA_BY_QUEUE

    def queue_for(self, rule_id):
        rule = self.registry.get(rule_id)
        if rule is None:
            return "unrouted"
        # An explicit hitl_queue wins. Inferring the queue from the citation
        # means re-citing a rule silently re-routes it: ADR-003 recited
        # DPDP-SENSITIVE-TARGETING-001 to platform policy, which moved caste
        # targeting from a rights queue to ad ops. Routing is now declared.
        explicit = (rule.raw or {}).get("hitl_queue")
        if explicit:
            return explicit
        for src in (rule.source or []):
            if src in self.queues:
                return self.queues[src]
        return "unrouted"

    def route(self, result, artifact_type=None, campaign_id=None):
        entries = list(result.violations) + list(result.inconclusive)
        by_queue = {}
        for e in entries:
            rid = e["rule_id"]
            q = self.queue_for(rid)
            by_queue.setdefault(q, []).append(e)

        items = []
        for q, es in sorted(by_queue.items()):
            rule_ids = [e["rule_id"] for e in es]
            inconclusive = [e for e in es if e.get("reason") == "inconclusive"]
            reason = (f"{len(es)} finding(s); {len(inconclusive)} could not be "
                      f"evaluated automatically") if inconclusive else \
                     f"{len(es)} blocking finding(s)"
            items.append(ReviewItem(queue=q, sla_hours=self.slas.get(q, 24),
                                    rule_ids=rule_ids, reason=reason,
                                    artifact_type=artifact_type,
                                    campaign_id=campaign_id))
        # Tightest SLA first, so the DPO queue is not buried behind typography.
        items.sort(key=lambda i: i.sla_hours)
        return items


def default_services(credentials=None, marks=None, consents=None, audit=None):
    return {
        "credential_registry": CredentialRegistry(records=credentials),
        "regdb": RegDB(),
        "legal_precheck": LegalPrecheck(marks=marks),
        "consent_vault": ConsentVault(records=consents, audit=audit),
    }
