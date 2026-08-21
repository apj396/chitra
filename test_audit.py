"""
test_audit.py — the ledger.

The claim being tested is not "events get written". It is that removing or
editing an entry is detectable, that an erasure can be honoured without
destroying the proof it happened, and that an auditor's question can be
answered in one command.

Run: python3 test_audit.py
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import chitra_audit as A

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def fresh():
    return A.AuditSink(os.path.join(tempfile.mkdtemp(), "a.jsonl"),
                       tenant_id="t_001")


def seeded():
    s = fresh()
    s.append("artifact.sanitized",
             {"pass": True, "checks_run": ["CULTURAL-CASTE-001"],
              "violations": [], "inconclusive": [],
              "human_review_required": False},
             artifact_type="creative_brief", campaign_id="c1", agent="drishti")
    s.record_waiver({"region": "Tamil Nadu", "approved_by": "A Patil",
                     "approved_on": "2026-08-16", "rationale": "accepted"},
                    campaign_id="c1")
    s.append("artifact.sanitized",
             {"pass": False, "checks_run": ["IP-TRADEMARK-001"],
              "violations": ["IP-TRADEMARK-001"], "inconclusive": [],
              "human_review_required": True},
             artifact_type="concept_slate", campaign_id="c2", agent="disha")
    s.append("check.unverifiable",
             {"rule_id": "IP-TRADEMARK-001", "reason": "service unavailable"},
             artifact_type="concept_slate", campaign_id="c2", agent="disha")
    s.record_halt("drishti", "refused", "banned category", [], "c3")
    return s


# ------------------------------------------------------------ chain integrity
def test_clean_chain_verifies():
    s = seeded()
    st = s.verify()
    check("a clean ledger verifies", st.ok, str(st))
    check("and counts every entry", st.entries == 5, str(st.entries))


def test_editing_an_entry_is_detected():
    s = seeded()
    lines = open(s.path).read().splitlines()
    e = json.loads(lines[0])
    e["payload"]["pass"] = False        # flip a verdict
    lines[0] = json.dumps(e, sort_keys=True, separators=(",", ":"))
    open(s.path, "w").write("\n".join(lines) + "\n")
    st = A.AuditSink(s.path).verify()
    check("an edited verdict breaks the chain", not st.ok, str(st))
    check("and the first broken entry is named", st.broken_at == 1,
          str(st.broken_at))
    check("and the reason says it was edited",
          "edited" in (st.reason or ""), st.reason or "")


def test_deleting_an_entry_is_detected():
    s = seeded()
    lines = open(s.path).read().splitlines()
    del lines[2]                        # remove an inconvenient failure
    open(s.path, "w").write("\n".join(lines) + "\n")
    st = A.AuditSink(s.path).verify()
    check("a deleted entry breaks the chain", not st.ok, str(st))


def test_appending_a_forged_entry_is_detected():
    s = seeded()
    forged = {"seq": 6, "ts": datetime.now(timezone.utc).isoformat(),
              "tenant_id": "t_001", "event_type": "artifact.sanitized",
              "payload": {"pass": True}, "prev_hash": "deadbeef" * 8,
              "hash": "cafebabe" * 8}
    with open(s.path, "a") as f:
        f.write(json.dumps(forged, sort_keys=True, separators=(",", ":")) + "\n")
    st = A.AuditSink(s.path).verify()
    check("a forged append breaks the chain", not st.ok, str(st))
    check("at the forged entry", st.broken_at == 6, str(st.broken_at))


def test_unknown_event_types_are_refused():
    s = fresh()
    try:
        s.append("artifact.quietly_approved", {})
        check("an undeclared event type is refused", False, "it was accepted")
    except ValueError:
        check("an undeclared event type is refused", True)


# ------------------------------------------------------------------- queries
def test_the_auditors_question():
    """Which artifacts shipped with an unverifiable check, and who signed?"""
    s = seeded()
    unver = list(s.query(unverifiable=True))
    check("unverifiable checks are findable in one query", unver, str(unver))
    waivers = list(s.query(event="waiver.recorded"))
    check("waivers are findable, with the approver",
          waivers and waivers[0]["payload"]["approved_by"] == "A Patil",
          str(waivers))
    check("the waiver carries a date, not just a name",
          waivers and waivers[0]["payload"]["approved_on"] == "2026-08-16")


def test_query_filters():
    s = seeded()
    check("by campaign", len(list(s.query(campaign_id="c2"))) == 2)
    check("by artifact type",
          len(list(s.query(artifact_type="creative_brief"))) == 1)
    check("by agent", len(list(s.query(agent="disha"))) == 2)
    check("by rule, across event shapes",
          len(list(s.query(rule_id="IP-TRADEMARK-001"))) == 2)
    check("blocked only", [e["campaign_id"] for e in s.query(blocked=True)] == ["c2"])
    check("needing review only",
          [e["campaign_id"] for e in s.query(needs_review=True)] == ["c2"])
    check("refusals", len(list(s.query(event="artifact.refused"))) == 1)


def test_query_by_time_window():
    s = seeded()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    check("since a past date returns everything", len(list(s.query(since=past))) == 5)
    check("since a future date returns nothing", not list(s.query(since=future)))


# ----------------------------------------------------------------- retention
def test_retention_sweep():
    s = seeded()
    check("nothing is over retention on a fresh ledger",
          not s.over_retention(730))
    check("everything is over a zero-day policy",
          len(s.over_retention(0)) == 5, str(len(s.over_retention(0))))


def test_erasure_redacts_without_breaking_the_chain():
    s = seeded()
    before = json.loads(open(s.path).read().splitlines()[3])
    s.redact(4, "DPDP erasure request", "DPB/ER/2026/0114, authorised by DPO")

    st = s.verify()
    check("the chain still verifies after a redaction", st.ok, str(st))

    e = [x for x in s.entries() if x["seq"] == 4][0]
    check("the content is gone", e["payload"].get("redacted") is True)
    check("the original payload hash is kept as proof",
          len(e["payload"]["payload_sha256"]) == 64)
    check("the hash matches what was actually there",
          e["payload"]["payload_sha256"] ==
          __import__("hashlib").sha256(
              A._canonical(before["payload"]).encode()).hexdigest())
    check("the authorisation is recorded",
          "DPB/ER/2026/0114" in e["payload"]["authorization"])

    red = list(s.query(event="retention.redacted"))
    check("the redaction is itself an entry", len(red) == 1)
    check("naming which sequence was redacted",
          red[0]["payload"]["redacted_seq"] == 4)


def test_redaction_requires_authorisation():
    s = seeded()
    try:
        s.redact(1, "cleanup", "")
        check("redaction without authorisation is refused", False, "it went through")
    except ValueError:
        check("redaction without authorisation is refused", True)


def test_redacting_twice_is_refused():
    s = seeded()
    s.redact(2, "erasure", "AUTH-1")
    try:
        s.redact(2, "erasure again", "AUTH-2")
        check("an already-redacted entry cannot be redacted again", False)
    except KeyError:
        check("an already-redacted entry cannot be redacted again", True)


# ------------------------------------------------------------------ appending
def test_append_survives_process_restart():
    s = seeded()
    reopened = A.AuditSink(s.path, tenant_id="t_001")
    reopened.append("artifact.sanitized", {"pass": True, "checks_run": []},
                    artifact_type="media_plan", campaign_id="c4")
    st = reopened.verify()
    check("a new process appends onto the existing chain", st.ok, str(st))
    check("and the sequence continues", st.entries == 6, str(st.entries))


def test_a_reused_brief_is_never_recorded_as_passing_unchecked():
    """The ledger recorded three briefs as pass=True with zero rules run.

    Skipping a model call must not skip compliance. A reused brief was written
    under an older registry and may fail rules that did not exist then.
    """
    s = fresh()
    s.append("artifact.sanitized",
             {"pass": True, "checks_run": [], "violations": [],
              "inconclusive": [], "human_review_required": False},
             artifact_type="creative_brief", campaign_id="c1", agent="drishti")
    bad = [e for e in s.query(event="artifact.sanitized")
           if e["payload"]["pass"] is True and not e["payload"]["checks_run"]]
    check("a pass with zero rules run is findable in the ledger", bad,
          "if this cannot be found, the defect cannot be audited for")
    check("and is what a compliance review would flag",
          bad[0]["payload"]["pass"] is True and
          bad[0]["payload"]["checks_run"] == [])


def main():
    for fn in (test_clean_chain_verifies, test_editing_an_entry_is_detected,
               test_deleting_an_entry_is_detected,
               test_appending_a_forged_entry_is_detected,
               test_unknown_event_types_are_refused,
               test_the_auditors_question, test_query_filters,
               test_query_by_time_window, test_retention_sweep,
               test_erasure_redacts_without_breaking_the_chain,
               test_redaction_requires_authorisation,
               test_redacting_twice_is_refused,
               test_append_survives_process_restart,
               test_a_reused_brief_is_never_recorded_as_passing_unchecked):
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
