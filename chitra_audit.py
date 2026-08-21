"""
chitra_audit.py — the ledger.

Every compliance verdict this system has produced so far has landed in a JSON
file in a run folder. That is a record of the last run, not an audit trail: it
does not accumulate, it cannot be searched across campaigns, and nothing
detects a deleted or edited entry.

WHAT THIS IS
    Append-only JSONL, hash-chained. Each entry carries the hash of the entry
    before it, so removing or editing any entry breaks the chain from that
    point on and `verify()` names the first broken sequence number. Tampering
    becomes detectable rather than invisible, which is the whole difference
    between a log and a ledger.

WHAT IT RECORDS
    artifact.sanitized     every sanitizer verdict, with the rules that ran
    artifact.refused       a refusal, with the reason
    agent.halted           a clarification halt, with what was missing
    waiver.recorded        a waiver, with the approver and the date
    hitl.routed            a review item, its queue and its SLA
    check.unverifiable     a check that could not run, and why
    retention.redacted     a redaction, with its authorisation

DELETION UNDER DPDP
    An append-only store and a right to erasure are in tension. Resolved by
    redaction rather than removal: the payload is replaced with a marker, the
    original payload hash is retained, and the chain stays intact. The entry
    proves something was there and was removed, by whom and under what
    authority, without retaining the content. Deleting the line outright would
    destroy the evidence that the erasure was honoured.

USAGE
    python chitra_audit.py verify
    python chitra_audit.py query --unverifiable --since 2026-08-01
    python chitra_audit.py query --event waiver.recorded
    python chitra_audit.py retention --policy-days 730
"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "audit", "chitra-audit.jsonl")

GENESIS = "0" * 64

EVENT_TYPES = [
    "artifact.sanitized", "artifact.refused", "agent.halted",
    "waiver.recorded", "hitl.routed", "check.unverifiable",
    "retention.redacted", "cultural.review_recorded",
    "compliance.consent_withdrawn",
]


def _canonical(obj):
    """Stable serialisation, so the same entry always hashes the same."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _hash(prev_hash, body):
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


@dataclass
class ChainStatus:
    ok: bool
    entries: int
    broken_at: int = None
    reason: str = None

    def __str__(self):
        if self.ok:
            return f"chain intact across {self.entries} entries"
        return (f"CHAIN BROKEN at seq {self.broken_at} "
                f"({self.entries} entries read): {self.reason}")


class AuditSink:
    def __init__(self, path=None, tenant_id=None):
        self.path = path or DEFAULT_PATH
        self.tenant_id = tenant_id
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    # ---------------------------------------------------------------- write
    def _tail(self):
        """Last sequence number and hash, without loading the whole file."""
        if not os.path.exists(self.path):
            return 0, GENESIS
        last = None
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line
        if last is None:
            return 0, GENESIS
        e = json.loads(last)
        return e["seq"], e["hash"]

    def append(self, event_type, payload, **fields):
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type {event_type!r}; "
                             f"add it to EVENT_TYPES deliberately")
        seq, prev = self._tail()
        body = {
            "seq": seq + 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "tenant_id": fields.pop("tenant_id", self.tenant_id),
            "event_type": event_type,
            "payload": payload,
        }
        body.update(fields)
        body["prev_hash"] = prev
        entry = dict(body)
        entry["hash"] = _hash(prev, body)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canonical(entry) + "\n")
        return entry

    # ----------------------------------------------------- domain shortcuts
    def record_sanitizer(self, artifact_type, result, campaign_id=None,
                         agent=None, artifact_id=None):
        d = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        entry = self.append(
            "artifact.sanitized",
            {"pass": d.get("pass"),
             "checks_run": d.get("checks_run", []),
             "violations": [v.get("rule_id") for v in d.get("violations", [])],
             "warnings": [w.get("rule_id") for w in d.get("warnings", [])],
             "inconclusive": [i.get("rule_id") for i in d.get("inconclusive", [])],
             "human_review_required": d.get("human_review_required")},
            artifact_type=artifact_type, campaign_id=campaign_id,
            agent=agent, artifact_id=artifact_id)
        for i in d.get("inconclusive", []):
            self.append("check.unverifiable",
                        {"rule_id": i.get("rule_id"),
                         "reason": i.get("message"),
                         "evidence": i.get("evidence")},
                        artifact_type=artifact_type, campaign_id=campaign_id,
                        agent=agent)
        return entry

    def record_waiver(self, waiver, campaign_id=None, kind="research_coverage"):
        return self.append(
            "waiver.recorded",
            {"kind": kind,
             "subject": waiver.get("region") or waiver.get("subject"),
             "approved_by": waiver.get("approved_by"),
             "approved_on": waiver.get("approved_on"),
             "rationale": waiver.get("rationale")},
            campaign_id=campaign_id)

    def record_routing(self, items, campaign_id=None):
        return [self.append("hitl.routed",
                            {"queue": i.get("queue"),
                             "sla_hours": i.get("sla_hours"),
                             "rule_ids": i.get("rule_ids", []),
                             "reason": i.get("reason")},
                            artifact_type=i.get("artifact_type"),
                            campaign_id=campaign_id)
                for i in (items or [])]

    def record_halt(self, agent, status, reason, missing=None, campaign_id=None):
        return self.append(
            "artifact.refused" if status == "refused" else "agent.halted",
            {"status": status, "reason": reason, "missing_fields": missing or []},
            agent=agent, campaign_id=campaign_id)

    # ----------------------------------------------------------------- read
    def entries(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def verify(self):
        """Walk the chain. Names the first entry that does not hold."""
        prev, n = GENESIS, 0
        for e in self.entries():
            n += 1
            if e.get("prev_hash") != prev:
                return ChainStatus(False, n, e.get("seq"),
                                   "prev_hash does not match the entry before it; "
                                   "an entry was removed or reordered")
            body = {k: v for k, v in e.items() if k != "hash"}
            if _hash(e["prev_hash"], body) != e.get("hash"):
                return ChainStatus(False, n, e.get("seq"),
                                   "recomputed hash does not match; this entry "
                                   "was edited after it was written")
            if e.get("seq") != n:
                return ChainStatus(False, n, e.get("seq"),
                                   f"sequence gap: expected {n}")
            prev = e["hash"]
        return ChainStatus(True, n)

    def query(self, event=None, campaign_id=None, artifact_type=None,
              rule_id=None, agent=None, since=None, until=None,
              unverifiable=False, blocked=False, needs_review=False):
        for e in self.entries():
            if event and e.get("event_type") != event:
                continue
            if campaign_id and e.get("campaign_id") != campaign_id:
                continue
            if artifact_type and e.get("artifact_type") != artifact_type:
                continue
            if agent and e.get("agent") != agent:
                continue
            if since and e.get("ts", "") < since:
                continue
            if until and e.get("ts", "") > until:
                continue
            p = e.get("payload", {})
            if unverifiable and e.get("event_type") != "check.unverifiable" \
                    and not p.get("inconclusive"):
                continue
            if blocked and p.get("pass") is not False:
                continue
            if needs_review and not p.get("human_review_required"):
                continue
            if rule_id:
                pool = (p.get("checks_run", []) + p.get("violations", [])
                        + p.get("inconclusive", []) + p.get("rule_ids", [])
                        + ([p.get("rule_id")] if p.get("rule_id") else []))
                if rule_id not in pool:
                    continue
            yield e

    # ------------------------------------------------------------ retention
    def over_retention(self, policy_days, now=None):
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=policy_days)).isoformat()
        return [e for e in self.entries()
                if e.get("ts", "") < cutoff
                and e.get("event_type") != "retention.redacted"
                and not e.get("redacted")]

    def redact(self, seq, reason, authorization):
        """DPDP erasure without breaking the chain.

        The payload goes; the entry, its hash and the payload's own hash stay.
        The record proves something existed and was removed under a named
        authority. Deleting the line would destroy the evidence that the
        erasure was honoured, which is the artefact the Board actually wants.
        """
        if not authorization:
            raise ValueError("redaction requires an authorization reference")
        found = None
        lines = []
        for e in self.entries():
            if e.get("seq") == seq and not e.get("redacted"):
                found = e
                payload_hash = hashlib.sha256(
                    _canonical(e.get("payload", {})).encode()).hexdigest()
                e = dict(e, payload={"redacted": True,
                                     "payload_sha256": payload_hash,
                                     "reason": reason,
                                     "authorization": authorization,
                                     "redacted_at": datetime.now(
                                         timezone.utc).isoformat()},
                         redacted=True)
            lines.append(e)
        if found is None:
            raise KeyError(f"no unredacted entry at seq {seq}")
        # Rewrite with the chain recomputed from the redaction point forward.
        prev = GENESIS
        for e in lines:
            body = {k: v for k, v in e.items() if k != "hash"}
            body["prev_hash"] = prev
            e.clear()
            e.update(body)
            e["hash"] = _hash(prev, body)
            prev = e["hash"]
        with open(self.path, "w", encoding="utf-8") as f:
            for e in lines:
                f.write(_canonical(e) + "\n")
        self.append("retention.redacted",
                    {"redacted_seq": seq, "reason": reason,
                     "authorization": authorization})
        return lines[seq - 1]


# --------------------------------------------------------------------- CLI

def _fmt(e):
    p = e.get("payload", {})
    bits = [f"#{e['seq']:<5}", e["ts"][:19], f"{e['event_type']:<21}"]
    if e.get("campaign_id"):
        bits.append(e["campaign_id"])
    if e.get("artifact_type"):
        bits.append(e["artifact_type"])
    line = "  ".join(bits)
    detail = ""
    if e["event_type"] == "artifact.sanitized":
        detail = (f"pass={p.get('pass')} rules={len(p.get('checks_run', []))} "
                  f"violations={p.get('violations') or '-'} "
                  f"inconclusive={p.get('inconclusive') or '-'}")
    elif e["event_type"] == "check.unverifiable":
        detail = f"{p.get('rule_id')}: {(p.get('reason') or '')[:80]}"
    elif e["event_type"] == "waiver.recorded":
        detail = (f"{p.get('kind')} for {p.get('subject')} "
                  f"approved by {p.get('approved_by')} on {p.get('approved_on')}")
    elif e["event_type"] == "hitl.routed":
        detail = (f"{p.get('queue')} SLA {p.get('sla_hours')}h "
                  f"{p.get('rule_ids')}")
    elif e["event_type"] in ("agent.halted", "artifact.refused"):
        detail = f"{e.get('agent')}: {(p.get('reason') or '')[:90]}"
    elif e["event_type"] == "cultural.review_recorded":
        detail = (f"{p.get('concept_id')} at {p.get('level')} by "
                  f"{p.get('reviewer')}"
                  + (f" — {p.get('per_axis')}" if p.get("per_axis") else ""))
    elif e["event_type"] == "retention.redacted":
        detail = f"seq {p.get('redacted_seq')} under {p.get('authorization')}"
    return line + ("\n        " + detail if detail else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description="CHITRA audit ledger")
    ap.add_argument("--path", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("verify", help="check the hash chain")

    q = sub.add_parser("query", help="search the ledger")
    q.add_argument("--event", choices=EVENT_TYPES)
    q.add_argument("--campaign")
    q.add_argument("--artifact-type")
    q.add_argument("--rule")
    q.add_argument("--agent")
    q.add_argument("--since")
    q.add_argument("--until")
    q.add_argument("--unverifiable", action="store_true")
    q.add_argument("--blocked", action="store_true")
    q.add_argument("--needs-review", action="store_true")
    q.add_argument("--json", action="store_true")

    r = sub.add_parser("retention", help="entries past the retention policy")
    r.add_argument("--policy-days", type=int, required=True)

    d = sub.add_parser("redact", help="honour an erasure request")
    d.add_argument("--seq", type=int, required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--authorization", required=True)

    a = ap.parse_args(argv)
    sink = AuditSink(a.path)

    if a.cmd == "verify":
        st = sink.verify()
        print(st)
        return 0 if st.ok else 1

    if a.cmd == "query":
        hits = list(sink.query(
            event=a.event, campaign_id=a.campaign,
            artifact_type=a.artifact_type, rule_id=a.rule, agent=a.agent,
            since=a.since, until=a.until, unverifiable=a.unverifiable,
            blocked=a.blocked, needs_review=a.needs_review))
        if a.json:
            print(json.dumps(hits, indent=2, ensure_ascii=False))
        else:
            for e in hits:
                print(_fmt(e))
            print(f"\n{len(hits)} entr{'y' if len(hits) == 1 else 'ies'}")
        return 0

    if a.cmd == "retention":
        old = sink.over_retention(a.policy_days)
        for e in old:
            print(_fmt(e))
        print(f"\n{len(old)} entr{'y' if len(old) == 1 else 'ies'} past "
              f"{a.policy_days} days")
        return 1 if old else 0

    if a.cmd == "redact":
        e = sink.redact(a.seq, a.reason, a.authorization)
        print(f"redacted seq {a.seq}; payload_sha256 "
              f"{e['payload']['payload_sha256'][:16]}...")
        print(sink.verify())
        return 0


if __name__ == "__main__":
    sys.exit(main())
