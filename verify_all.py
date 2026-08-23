#!/usr/bin/env python3
"""
verify_all.py — every gate, one command, any platform.

Replaces verify_all.sh so a reviewer on Windows, macOS or Linux runs the same
thing. Exits non-zero if any gate fails.

Each gate answers a different question:

  conformance      Do the compliance rules satisfy the schema that admits them,
                   and do their citations name law that is still in force?
  field census     Does every field a rule reads exist on the artifacts it
                   applies to, or is it declared as derived?
  sanitizer        Does the policy engine enforce, fail closed, and refuse to
                   pass on fields that do not exist?
  agents           Do the two built agents refuse, halt, repair and hand off
                   as specified?
  services         Do consent, credentials, trademark and routing behave?
  variance         Can padding be told from exploration?
  sweep            Are the pinned vendor APIs still what we think they are?
  ledger           Is the audit chain tamper-evident, and can erasure be
                   honoured without destroying the proof?
  review           Does a named human review actually gate the pipeline?
  offline slice    Does the whole slice still run end to end with no API key,
                   no network call and no spend, without writing to the
                   production audit ledger?

Usage:
    python verify_all.py           run everything
    python verify_all.py --quick   skip the vendor sweep
    python verify_all.py --list    show the gates without running them
"""

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

GATES = [
    ("conformance", "rules vs their admission schema; citations vs live law",
     ["chitra_conformance.py", "--instruments", "instruments.json", "specs"]),
    ("field census", "rule field reads vs artifact schemas",
     ["audit_field_paths.py"]),
    ("sanitizer", "policy engine: enforcement and fail-closed behaviour",
     ["test_sanitizer.py"]),
    ("drishti", "agent 1: refusals, halts, schema and compliance repair",
     ["test_drishti.py"]),
    ("services", "consent vault, credentials, trademark, HITL routing, ADRs",
     ["test_services.py"]),
    ("variance", "padding versus genuine exploration",
     ["test_variance.py"]),
    ("disha", "agent 2: divergence gating, scoring, kill tags, handoff",
     ["test_disha.py"]),
    ("sweep", "pinned vendor APIs vs upstream", ["test_sweep.py"]),
    ("ledger", "audit chain: tamper evidence and DPDP erasure",
     ["test_audit.py"]),
    ("review", "the human gate: named cultural review", ["test_review.py"]),
    ("offline slice", "the whole pipeline, no key, no network, no spend",
     ["test_offline_slice.py"]),
    ("implementability", "how much of the rule set genuinely enforces",
     ["analyse_implementability.py"]),
]

QUICK_SKIP = {"sweep"}

GREEN, RED, YELLOW, DIM, RESET = (
    ("\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m")
    if sys.stdout.isatty() and os.name != "nt" else ("", "", "", "", ""))


def run(name, why, argv):
    print(f"\n{'=' * 72}\n{name.upper()}  {DIM}{why}{RESET}\n{'=' * 72}")
    t0 = time.time()
    p = subprocess.run([sys.executable] + argv, cwd=HERE)
    return p.returncode == 0, round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser(description="Run every CHITRA gate")
    ap.add_argument("--quick", action="store_true",
                    help="skip the vendor compatibility sweep")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name, why, _ in GATES:
            print(f"  {name:<18}{why}")
        return 0

    missing = [f for f in ("chitra_rules.json", "rule_object.schema.json")
               if not os.path.exists(os.path.join(HERE, f))]
    if missing:
        print(f"{RED}Missing required file(s): {', '.join(missing)}{RESET}")
        return 2

    results, failed = [], 0
    for name, why, argv in GATES:
        if args.quick and name in QUICK_SKIP:
            results.append((name, None, 0.0))
            continue
        ok, secs = run(name, why, argv)
        results.append((name, ok, secs))
        failed += not ok

    print(f"\n{'=' * 72}\nSUMMARY\n{'=' * 72}")
    for name, ok, secs in results:
        mark = ("SKIP" if ok is None else "PASS" if ok else "FAIL")
        colour = YELLOW if ok is None else GREEN if ok else RED
        print(f"  {colour}{mark}{RESET}  {name:<18}{secs:>6}s")

    if failed:
        print(f"\n{RED}{failed} gate(s) failed.{RESET}")
        return 1
    print(f"\n{GREEN}All gates pass.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
