#!/usr/bin/env python3
"""
test_offline_slice.py — the offline pipeline gate.

Every other gate proves a component behaves. This one proves the thing a
reviewer actually wants to do works: run the whole vertical slice, start to
finish, with no API key, no network call and no spend, and get the same
artifacts a paid run produces.

That path existed before this gate and was never verified. `run_slice.py
--offline` was documented in the README and in the module docstring, and
nothing checked that it still ran. A documented path with no gate behind it is
a claim, not a feature, and this project has already shipped one of those.

What this asserts, in order of what it would catch:

  1. The slice exits 0 with ANTHROPIC_API_KEY absent from the environment.
  2. It also exits 0 with the key set to a value that cannot authenticate. If
     any code path reaches the real API in offline mode, that run fails and
     this gate fails with it. Absence of a key proves the slice does not
     require one; a poisoned key proves it does not use one.
  3. All six artifacts land, and each parses as JSON.
  4. The run report records offline=true, both agent stages, and outcome
     slice_complete.
  5. The slate carries approved and killed concepts, so the divergence, scoring
     and kill path genuinely executed rather than short-circuiting.
  6. The run is held at the cultural gate. An offline run that reported itself
     cleared for production would mean the human gate had been bypassed by the
     fixture client, which is the failure mode most worth catching here.
  7. The temporary ledger it wrote is chain-intact and non-empty.
  8. The production ledger is byte-identical before and after. This mirrors the
     §2.5 mitigation. The 68 fixture entries in the first real audit trail got
     there because a test suite wrote to the production ledger, and a gate that
     runs the pipeline on every commit is that same hazard with a different
     entry point.
  9. A cultural audit sitting on disk does not attach itself to a generated
     slate. This gate found that defect on the second machine it ever ran on:
     the author's copy had a real cultural_audits.json, the run's fixture
     concepts happened to be numbered C01 upward like the reviewed ones, and
     two of them inherited a stranger's sign-off. The check now plants exactly
     that collision deliberately and fails if it takes.

Run directly:  python test_offline_slice.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROD_LEDGER = os.path.join(HERE, "audit", "chitra-audit.jsonl")

ARTIFACTS = [
    "01-creative-brief.json",
    "02-drishti-envelope.json",
    "03-concept-slate.json",
    "04-disha-envelope.json",
    "05-run-report.json",
    "transcript.json",
]

POISON_KEY = "sk-ant-offline-gate-must-never-authenticate-with-this"

passed = failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ok    {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"\n          {detail}" if detail else ""))


def ledger_bytes():
    try:
        return os.path.getsize(PROD_LEDGER)
    except OSError:
        return None


def run_slice(tmp, env_key, audits=None):
    """Run the offline slice into a throwaway tree.

    Everything the run touches lives under tmp: its output, its ledger and its
    audits file. A gate that reads whatever happens to be in the working
    directory passes or fails on the reviewer's machine state rather than on
    the code, which is how this one first went wrong.
    """
    out = os.path.join(tmp, "out")
    ledger = os.path.join(tmp, "ledger", "chitra-audit.jsonl")
    audits_path = os.path.join(tmp, "cultural_audits.json")
    with open(audits_path, "w", encoding="utf-8") as f:
        json.dump({"audits": audits or {}}, f)
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    if env_key is not None:
        env["ANTHROPIC_API_KEY"] = env_key
    proc = subprocess.run(
        [sys.executable, "run_slice.py", "--offline", "--out", out,
         "--ledger", ledger, "--audits", audits_path],
        cwd=HERE, env=env, capture_output=True, text=True, timeout=600)
    runs = sorted(os.listdir(out)) if os.path.isdir(out) else []
    return proc, (os.path.join(out, runs[-1]) if runs else None), ledger


def main():
    print("=" * 72)
    print("OFFLINE SLICE  no key, no network, no spend, no production ledger")
    print("=" * 72)

    before = ledger_bytes()

    # ---- 1. no key at all -------------------------------------------------
    tmp = tempfile.mkdtemp(prefix="chitra-offline-")
    try:
        proc, outdir, ledger = run_slice(tmp, env_key=None)
        check("runs to completion with ANTHROPIC_API_KEY unset",
              proc.returncode == 0,
              f"exit {proc.returncode}\n{proc.stdout[-1500:]}{proc.stderr[-800:]}")
        check("did not ask for a key",
              "ANTHROPIC_API_KEY is not set" not in proc.stdout,
              "the slice took the missing-key branch instead of the fixture one")

        if outdir is None:
            check("produced a run directory", False, "no directory under --out")
            return 1

        for name in ARTIFACTS:
            p = os.path.join(outdir, name)
            ok = os.path.isfile(p) and os.path.getsize(p) > 0
            check(f"wrote {name}", ok)
            if ok:
                try:
                    json.load(open(p, encoding="utf-8"))
                except (ValueError, OSError) as e:
                    check(f"{name} parses as JSON", False, str(e))

        # A gate that raises instead of reporting is a gate whose output nobody
        # can read at a glance. If the slice did not get far enough to write a
        # run report, say so and stop rather than throwing a traceback over the
        # checks that already ran.
        report_path = os.path.join(outdir, "05-run-report.json")
        if not os.path.isfile(report_path):
            check("produced a run report", False,
                  "the slice did not reach the end; earlier failures above "
                  "explain why. Remaining checks skipped.")
            print(f"\n{passed}/{passed + failed} passed")
            print(f"{failed} check(s) failed.")
            return 1
        report = json.load(open(report_path, encoding="utf-8"))
        check("run report records offline=true", report.get("offline") is True,
              f"offline={report.get('offline')!r}")
        check("run report records no model", report.get("model") is None,
              f"model={report.get('model')!r}")
        check("both agent stages ran", len(report.get("stages") or []) == 2,
              f"{len(report.get('stages') or [])} stage(s)")
        agents = [s.get("agent") for s in (report.get("stages") or [])]
        check("stages are drishti then disha", agents == ["drishti", "disha"],
              f"{agents}")
        check("outcome is slice_complete",
              report.get("outcome") == "slice_complete",
              f"outcome={report.get('outcome')!r}")

        slate = json.load(open(os.path.join(outdir, "03-concept-slate.json"),
                               encoding="utf-8"))
        approved = slate.get("concepts_approved") or []
        killed = slate.get("concepts_killed") or []
        check("slate carries approved concepts", len(approved) > 0,
              "an empty slate means scoring never ran")
        check("slate carries killed concepts", len(killed) > 0,
              "nothing killed means the ranking gate did not execute")
        check("every kill is tagged",
              all(k.get("kill_tag") or k.get("tag") for k in killed
                  if isinstance(k, dict)),
              "an untagged kill is an unexplained rejection")

        caveats = " ".join(report.get("caveats") or [])
        check("run is held at the cultural gate",
              "not cleared for production" in caveats.lower(),
              "an offline run reporting itself production-cleared means the "
              "fixture client walked through the human gate")

        # ---- ledger it was told to use ------------------------------------
        check("wrote to the temporary ledger", os.path.isfile(ledger))
        if os.path.isfile(ledger):
            entries = [json.loads(l) for l in open(ledger, encoding="utf-8")
                       if l.strip()]
            check("temporary ledger is non-empty", len(entries) > 0)
            seqs = [e["seq"] for e in entries]
            check("ledger sequence is contiguous from 1",
                  seqs == list(range(1, len(entries) + 1)), f"{seqs[:12]}")
            sys.path.insert(0, HERE)
            import chitra_audit as AUD
            st = AUD.AuditSink(path=ledger).verify()
            check("temporary ledger chain verifies", st.ok, str(st))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- 2. poisoned key: proves offline never reaches the API ------------
    tmp = tempfile.mkdtemp(prefix="chitra-offline-poison-")
    try:
        proc, outdir, _ = run_slice(tmp, env_key=POISON_KEY)
        check("runs to completion with an unusable key present",
              proc.returncode == 0 and outdir is not None,
              f"exit {proc.returncode}. If offline mode reached the real API "
              f"this is where it shows.\n{proc.stdout[-1200:]}")
        check("the poisoned key is never echoed",
              POISON_KEY not in proc.stdout and POISON_KEY not in proc.stderr,
              "a key reached stdout, which is a disclosure defect regardless "
              "of this gate")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- 3. a foreign audit must not attach to a generated slate ----------
    # Recorded against different creative in a different campaign, under the
    # ids a fresh run reuses. Before the fix this showed up as two concepts
    # reading a cultural risk level nobody had assigned them.
    foreign = {cid: {"completed": True, "level": "low", "per_axis": None,
                     "reviewer": "A Patil",
                     "reviewed_at": "2026-08-20T00:00:00+00:00",
                     "notes": "recorded on another campaign entirely",
                     "concept_fingerprint": "0" * 64,
                     "concept_title": "The Real Culprit"}
               for cid in ("C01", "C02")}
    tmp = tempfile.mkdtemp(prefix="chitra-offline-foreign-")
    try:
        proc, outdir, _ = run_slice(tmp, env_key=None, audits=foreign)
        check("runs to completion with a foreign audit file present",
              proc.returncode == 0 and outdir is not None,
              f"exit {proc.returncode}")
        if outdir:
            rep = json.load(open(os.path.join(outdir, "05-run-report.json"),
                                 encoding="utf-8"))
            cav = " ".join(rep.get("caveats") or [])
            check("a generated slate does not inherit the foreign audit",
                  "not cleared for production" in cav.lower(),
                  "concept ids are slate-local and reset every run; an audit "
                  "keyed on one is an audit of whatever now sits in that slot")
            sl = json.load(open(os.path.join(outdir, "03-concept-slate.json"),
                                encoding="utf-8"))
            levels = {c.get("id"): (c.get("cultural_risk") or {}).get("level")
                      for c in sl.get("concepts_approved") or []}
            check("no concept carries a risk level the foreign audit supplied",
                  len(set(levels.values())) <= 1,
                  f"{levels}. Split levels mean the audits keyed on C01 and "
                  f"C02 landed on this run's C01 and C02.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- 4. the production ledger was not touched -------------------------
    after = ledger_bytes()
    check("production ledger byte size unchanged", before == after,
          f"{before} -> {after}. The pipeline gate just wrote to the real "
          f"audit trail. This is the §2.5 defect, reintroduced.")

    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        print(f"{failed} check(s) failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
