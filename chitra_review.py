"""
chitra_review.py — the human step, tooled.

Five cultural rules return inconclusive on every slate because no completed
audit exists per concept. That is correct: nobody has looked. Naming a reviewer
in config does not change it, and writing audits into cultural_audits.json to
make a run go green is the fiction removed on 17 August.

What was missing is the tooling. This does three things:

  brief    assemble the evidence for each concept in a slate: which axes it
           touches, what the register says, what precedent applies, and the
           question the reviewer has to answer. From chitra_cultural_assistant,
           which issues no verdict and adopts no perspective (ADR-001).

  record   write a reviewer's decision into cultural_audits.json, with the
           reviewer's name, the date, the level per axis and their notes, and
           append it to the audit ledger.

  status   which concepts in a slate are audited and which are not.

The reviewer's name is required and is not defaulted. An audit without a name
is the compromise ADR-020 refused for waivers, and the same reasoning holds
here: the difference between a review and a rubber stamp is whether anyone's
name is on it.

USAGE
    python chitra_review.py brief  --slate run_output/<ts>/03-concept-slate.json
    python chitra_review.py record --concept C01 --level low \\
        --reviewer "A Patil" --notes "No religious or regional depiction."
    python chitra_review.py status --slate run_output/<ts>/03-concept-slate.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import chitra_cultural_assistant as CA

HERE = os.path.dirname(os.path.abspath(__file__))
AUDITS = os.path.join(HERE, "cultural_audits.json")

LEVELS = ["low", "medium", "high"]
AXES = list(CA.AXES)


def load_audits(path=None):
    path = path or AUDITS
    if not os.path.exists(path):
        return {}
    return json.load(open(path, encoding="utf-8")).get("audits", {})


def save_audits(audits, path=None):
    path = path or AUDITS
    doc = (json.load(open(path, encoding="utf-8"))
           if os.path.exists(path) else {})
    doc["audits"] = audits
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)


def load_slate(path):
    return json.load(open(path, encoding="utf-8"))


def cmd_brief(args):
    slate = load_slate(args.slate)
    assistant = CA.CulturalAssistant(
        register=_load_register(), precedent=_load_precedent())
    ctx = {"cultural_risk_audits": load_audits(args.audits),
           "cultural_reviewer": args.reviewer}

    out = []
    for c in slate.get("concepts_approved", []):
        payload = dict(c)
        payload["concept_id"] = c["id"]
        rb = assistant.assemble(payload, ctx, concept_id=c["id"])
        out.append(rb)
        print(rb.to_markdown())
        print(f"\n> Concept text under review\n>   title: {c.get('title')}\n"
              f">   proposition: {c.get('proposition')}\n"
              f">   visual: {(c.get('visual_direction') or '')[:300]}\n"
              f">   hook: {(c.get('verbal_hook') or {}).get('primary')}\n")
        print("=" * 72)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for rb in out:
                f.write(rb.to_markdown() + "\n\n---\n\n")
        print(f"\nWritten to {args.out}")
    return 0


def cmd_record(args):
    if not args.reviewer or not args.reviewer.strip():
        print("A reviewer name is required. An audit without a name is a "
              "rubber stamp, not a review.")
        return 2
    if args.level not in LEVELS:
        print(f"level must be one of {LEVELS}")
        return 2

    per_axis = {}
    for pair in (args.axis or []):
        if "=" not in pair:
            print(f"--axis expects axis=level, got {pair!r}")
            return 2
        axis, level = pair.split("=", 1)
        if axis not in AXES:
            print(f"unknown axis {axis!r}; expected one of {AXES}")
            return 2
        if level not in LEVELS:
            print(f"level for {axis} must be one of {LEVELS}")
            return 2
        per_axis[axis] = level

    # The overall level is the worst axis, not the one the reviewer typed, so a
    # high on one axis cannot be averaged away by four lows.
    level = args.level
    if per_axis:
        worst = max(per_axis.values(), key=LEVELS.index)
        if LEVELS.index(worst) > LEVELS.index(level):
            print(f"Overall level raised from {level} to {worst}: the worst "
                  f"axis governs.")
            level = worst

    audits = load_audits(args.audits)
    audits[args.concept] = {
        "completed": True,
        "level": level,
        "per_axis": per_axis or None,
        "reviewer": args.reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "notes": args.notes,
    }
    save_audits(audits, args.audits)

    try:
        import chitra_audit as AUD
        # Honour --ledger. Without it, every test run appended its fixtures to
        # the production ledger: 68 of 112 entries in the first real audit
        # trail were "A Patil" test data. A ledger containing test data is not
        # evidence, and the tests were the ones destroying it.
        AUD.AuditSink(path=args.ledger).append(
            "cultural.review_recorded",
            {"concept_id": args.concept, "level": level, "per_axis": per_axis,
             "reviewer": args.reviewer.strip(), "notes": args.notes})
    except Exception as e:
        print(f"(ledger append failed: {e})")

    print(f"Recorded {args.concept} at {level} by {args.reviewer.strip()}.")
    if level == "high":
        print("High risk: CULTURAL rules with a conditional severity will now "
              "BLOCK rather than warn. That is the intended behaviour.")
    return 0


def cmd_status(args):
    slate = load_slate(args.slate)
    audits = load_audits(args.audits)
    missing = []
    print(f"{'CONCEPT':<10}{'AUDITED':<10}{'LEVEL':<10}{'REVIEWER':<22}TITLE")
    for c in slate.get("concepts_approved", []):
        a = audits.get(c["id"])
        done = bool(a and a.get("completed"))
        if not done:
            missing.append(c["id"])
        print(f"{c['id']:<10}{'yes' if done else 'NO':<10}"
              f"{(a or {}).get('level', '-'):<10}"
              f"{(a or {}).get('reviewer', '-'):<22}{c.get('title', '')}")
    if missing:
        print(f"\n{len(missing)} concept(s) unaudited: {', '.join(missing)}")
        print("The slate stays inconclusive until every one is recorded: a "
              "container is governed only if all of its concepts are.")
        return 1
    print("\nEvery approved concept is audited. Re-run the slice, or "
          "re-sanitize the slate, to clear the cultural queue.")
    return 0


def _load_register():
    p = os.path.join(HERE, "cultural_risk_register.json")
    return json.load(open(p, encoding="utf-8")).get("register", {}) \
        if os.path.exists(p) else {}


def _load_precedent():
    p = os.path.join(HERE, "cultural_precedent.json")
    return json.load(open(p, encoding="utf-8")).get("precedent", {}) \
        if os.path.exists(p) else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description="CHITRA cultural review")
    ap.add_argument("--audits", default=None)
    ap.add_argument("--ledger", default=None,
                    help="Audit ledger path. Tests must pass a temporary one; "
                         "appending fixtures to the production ledger destroys "
                         "the evidence it exists to hold.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("brief", help="assemble evidence for the reviewer")
    b.add_argument("--slate", required=True)
    b.add_argument("--reviewer", default=None)
    b.add_argument("--out", default=None)

    r = sub.add_parser("record", help="record a reviewer's decision")
    r.add_argument("--concept", required=True)
    r.add_argument("--level", required=True, choices=LEVELS)
    r.add_argument("--reviewer", required=True)
    r.add_argument("--notes", default="")
    r.add_argument("--axis", action="append",
                   help="per-axis level, e.g. --axis religion=low "
                        "(repeatable). The worst axis sets the overall level.")

    s = sub.add_parser("status", help="which concepts are audited")
    s.add_argument("--slate", required=True)

    a = ap.parse_args(argv)
    return {"brief": cmd_brief, "record": cmd_record,
            "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
