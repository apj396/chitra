"""
run_slice.py — the vertical slice, end to end, against a real model.

Drishti reads an onboarding packet and writes a creative_brief.
Disha interrogates that brief, diverges, gates for variance, scores, kills, and
writes a concept_slate. Both artifacts pass a schema gate and the compliance
sanitizer before anything moves.

USAGE
    python run_slice.py                    real model, needs ANTHROPIC_API_KEY
    python run_slice.py --offline          fixtures only, no key, no spend
    python run_slice.py --packet mine.json a different client
    python run_slice.py --model <id>       override the model id
    python run_slice.py --ledger <path>    write the audit trail elsewhere

The key is read from the ANTHROPIC_API_KEY environment variable and is never
written to disk, never printed, and never included in the run output.

OUTPUT
    ./run_output/<timestamp>/
        01-creative-brief.json      the artifact Drishti produced
        02-drishti-envelope.json    handoff to Disha, with the compliance record
        03-concept-slate.json       the artifact Disha produced
        04-disha-envelope.json      handoff to Roop and Vaani
        05-run-report.json          every gate, every turn, every finding
        transcript.json             what happened at each step
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import chitra_disha as DI
import chitra_drishti as DR
import chitra_sanitizer as S
import chitra_audit as AUD
import chitra_services as SV
from chitra_paths import check_specs, spec_dir

HERE = os.path.dirname(os.path.abspath(__file__))

GREEN, RED, YELLOW, DIM, RESET = ("\033[32m", "\033[31m", "\033[33m",
                                  "\033[2m", "\033[0m")
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    GREEN = RED = YELLOW = DIM = RESET = ""


def say(sym, text, colour=""):
    print(f"{colour}{sym}{RESET} {text}", flush=True)


def head(text):
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}", flush=True)


def load_packet(path):
    path = path or os.path.join(HERE, "onboarding_packet.json")
    if not os.path.exists(path):
        say("x", f"No onboarding packet at {path}", RED)
        sys.exit(2)
    return json.load(open(path, encoding="utf-8"))


def build_context(packet, audits=None):
    """Tenant, campaign and services context for the run.

    Cultural audits are not read here. They arrive as the `audits` argument,
    which only the re-judge path supplies, after binding each one to a digest
    of the creative it was recorded on. A generated slate is unreviewed by
    definition, so the cultural rules go inconclusive and the run routes to
    the cultural_review queue. That is the truth rather than a stall.
    """
    return {
        "tenant": {
            "tenant_id": packet.get("tenant_id", "t_001"),
            "dpdp_retention_policy_days": 730,
            "competitive_exclusions": packet.get("competitive_exclusions", []),
            "hitl_budget_shift_threshold_pct": 20,
        },
        "campaign": {
            "product_category": packet.get("product_category"),
            "sector": packet.get("sector"),
            "budget_inr": packet.get("budget_inr"),
            "campaign_id": packet.get("campaign_id"),
            "geography": packet.get("geography"),
            "research_coverage": (packet.get("audience_research") or {})
                                 .get("coverage"),
            "research_coverage_waivers": packet.get("research_coverage_waivers"),
        },
        "services": SV.default_services(),
        # No audits here, ever. Earlier runs pre-filled C01..C12 as reviewed at
        # low risk, which was a fiction, and once the ledger existed it became
        # a recorded fiction. Reading cultural_audits.json from disk was the
        # same fiction arriving by a different door: concept ids are
        # slate-local and reset to C01 every run, so a review of one campaign's
        # first concept presented as the cultural risk level of a different
        # campaign's first concept. A slate that does not exist yet cannot have
        # been reviewed. Audits enter through _rejudge, against the slate that
        # was actually read, matched on a digest of its creative.
        "cultural_risk_audits": dict(audits or {}),
        "cultural_reviewer": packet.get("cultural_reviewer"),
    }


class SliceOfflineClient:
    """Serves both stages from fixtures, so --offline exercises the whole slice.

    Drishti's OfflineClient only ever returns a brief. Disha asks for
    territories and then for scores, so a single-fixture client stalls the
    divergence gate at zero territories, which is a property of the stub and
    not of the pipeline.
    """

    def __init__(self):
        from test_disha import territories
        from test_drishti import GOOD_BRIEF
        from test_variance import DIVERGENT
        self.brief = GOOD_BRIEF
        self.territories = territories(DIVERGENT)
        self.calls = 0

    def available(self):
        return True

    def complete(self, system, messages):
        self.calls += 1
        last = messages[-1]["content"]
        if "Score every territory" in last:
            ids = [t["id"] for t in json.loads(last[last.index("["):])]
            return json.dumps({"scores": {
                i: {"relevance": 4, "distinctiveness": 4, "resonance": 4,
                    "producibility": 4, "cultural_safety": 4} for i in ids}})
        if "territories" in last.lower() or "LOCKED CREATIVE BRIEF" in last:
            return json.dumps({"territories": self.territories})
        return json.dumps(self.brief)


def make_client(args):
    if args.offline:
        say("!", "Offline mode: fixture client, no model call, no spend.", YELLOW)
        return SliceOfflineClient(), None

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        say("x", "ANTHROPIC_API_KEY is not set in this shell.", RED)
        print("\n  Windows PowerShell:  $env:ANTHROPIC_API_KEY = \"sk-ant-...\"")
        print("  Windows cmd.exe:     set ANTHROPIC_API_KEY=sk-ant-...")
        print("  macOS or Linux:      export ANTHROPIC_API_KEY=sk-ant-...")
        print("\n  Then run this script again in the same shell.")
        print("  Or run with --offline to exercise the pipeline without a key.\n")
        sys.exit(2)
    if not key.startswith("sk-ant-"):
        say("!", "Key does not start with sk-ant-. Continuing, but check it.", YELLOW)
    say("+", f"Model: {args.model}", DIM)
    return DR.AnthropicClient(model=args.model), args.model


def main():
    ap = argparse.ArgumentParser(description="Run the CHITRA vertical slice")
    ap.add_argument("--packet", default=None)
    ap.add_argument("--model", default=os.environ.get("CHITRA_MODEL",
                                                      "claude-sonnet-5"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "run_output"))
    ap.add_argument("--audits", default=None,
                    help="Cultural audits file. Read only by --slate, which "
                         "matches each audit against a digest of the creative "
                         "it was recorded on. A generated run never reads it: "
                         "a slate that does not exist yet cannot have been "
                         "reviewed.")
    ap.add_argument("--ledger", default=None,
                    help="Audit ledger path. Anything automated must pass a "
                         "temporary one. chitra_review.py grew this flag after "
                         "68 of the first 112 entries in the real ledger turned "
                         "out to be test fixtures; a scheduled offline run of "
                         "this script is the same hazard by a different route.")
    ap.add_argument("--slate", default=None,
                    help="Path to an existing 03-concept-slate.json. Re-judges "
                         "that slate against the current registry and the "
                         "cultural audits on file, records the verdict to the "
                         "ledger, and makes no model call at all. This is how "
                         "you close the loop after a human review.")
    ap.add_argument("--brief", default=None,
                    help="Path to an existing 01-creative-brief.json. Skips "
                         "Stage 1 and re-runs Disha only, so a Stage 2 retry "
                         "does not pay for a brief you already have.")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%d-%H%M%S")
    outdir = os.path.join(args.out, stamp)
    os.makedirs(outdir, exist_ok=True)

    missing = check_specs(["CHITRA-v1_1-Agent-Prompt-Scaffolds.md"])
    if missing:
        say("x", "Specification document not found: " + ", ".join(missing), RED)
        print("\n  Drishti and Disha read the L0 security wrapper and their")
        print("  scaffolds out of the v1.1 specification at runtime, rather than")
        print("  having the prompt pasted into the source.")
        print("\n  Create a specs folder beside this script and copy the document in:")
        print("      mkdir specs")
        print("      copy \"..\\CHITRA-v1_1-Agent-Prompt-Scaffolds.md\" specs\\")
        print("\n  Or point CHITRA_SPEC_DIR at the folder that already holds it:")
        print("      set CHITRA_SPEC_DIR=C:\\path\\to\\your\\spec\\folder\n")
        return 2
    say("+", f"Specs found in {spec_dir()}", DIM)

    packet = load_packet(args.packet)
    context = build_context(packet)

    audits_path = args.audits or os.path.join(HERE, "cultural_audits.json")
    if not args.slate and os.path.exists(audits_path):
        say("!", "cultural_audits.json exists and is deliberately not read for "
                 "a generated slate. These concepts are new; nobody has "
                 "reviewed them. Close the loop with --slate after recording "
                 "a review.", YELLOW)

    if args.slate:
        return _rejudge(args, packet, context, outdir,
                        {"started_at": started.isoformat(), "model": None,
                         "mode": "rejudge", "offline": True,
                         "packet": packet.get("campaign_id"), "stages": []})

    # cultural_overlay requires festivals_in_window and sports_in_window. No
    # agent can know them without the Resource Pack, and the first real run
    # halted partly on that. Passing None was silently asking the model to
    # invent a festival calendar.
    rp_path = os.path.join(HERE, "resource_pack.json")
    resource_pack = (json.load(open(rp_path, encoding="utf-8"))
                     if os.path.exists(rp_path) else None)
    if resource_pack:
        say("+", f"Resource pack loaded: "
                 f"{len(resource_pack.get('A2_festival_calendar', []))} festivals "
                 f"in window", DIM)
    else:
        say("!", "No resource_pack.json; cultural_overlay will be unfillable.",
            YELLOW)
    client, model = make_client(args)

    registry = S.RuleRegistry.load(
        schema_path=os.path.join(HERE, "rule_object.schema.json"))
    say("+", f"Rule registry loaded: {len(registry.rules)} rules", DIM)

    sink = AUD.AuditSink(path=args.ledger, tenant_id=packet.get("tenant_id"))
    st = sink.verify()
    say("+" if st.ok else "x", f"Audit ledger: {st}", GREEN if st.ok else RED)
    if not st.ok:
        say("x", "Refusing to append to a broken ledger. Investigate before "
                 "running anything else.", RED)
        return 3
    for w in (packet.get("research_coverage_waivers") or []):
        sink.record_waiver(w, campaign_id=packet.get("campaign_id"))

    report = {"started_at": started.isoformat(), "model": model,
              "offline": args.offline, "packet": packet.get("campaign_id"),
              "stages": []}

    # ---------------------------------------------------------------- Drishti
    head("STAGE 1 — DRISHTI (Brand and Strategic Planner)")
    drishti = DR.Drishti(client, registry)

    if args.brief:
        brief = json.load(open(args.brief, encoding="utf-8"))
        say("+", f"Reusing the brief at {args.brief}. No model call, no spend.",
            GREEN)
        # Sanitize it. Skipping the model call does not skip compliance: a
        # reused brief was written under an older registry and may fail rules
        # that did not exist when it was produced. Asserting pass=True with
        # zero checks put three false compliance records into the ledger.
        reused = S.sanitize("creative_brief", brief,
                            DR._with_campaign(context, packet), registry)
        say("+" if reused.passed else "x",
            f"  re-sanitized against the current registry: "
            f"{len(reused.checks_run)} rules run, pass={reused.passed}",
            DIM if reused.passed else RED)
        if reused.violations:
            for v in reused.violations:
                print(f"      {v['rule_id']}: {v['message'][:120]}")
            say("x", "The reused brief does not pass the current rules. "
                     "Regenerate it rather than building on it.", RED)
            sink.record_sanitizer("creative_brief", reused,
                                  campaign_id=packet.get("campaign_id"),
                                  agent="drishti")
            _save(outdir, "05-run-report.json", report)
            return 1
        d = DR.DrishtiResult(status="brief", brief=brief, attempts=0,
                             sanitizer=reused.to_dict(),
                             envelope={"artifact_type": "creative_brief",
                                       "reused_from": args.brief,
                                       "sanitizer_pass": reused.passed,
                                       "compliance_checks_run": reused.checks_run})
        report["stages"].append({"agent": "drishti", "status": "reused",
                                 "source": args.brief})
        _save(outdir, "01-creative-brief.json", brief)
        t0 = time.time()
        elapsed = 0.0
    else:
        t0 = time.time()
        d = drishti.run(packet, context, resource_pack=resource_pack)
        elapsed = round(time.time() - t0, 1)

    if not args.brief:
        report["stages"].append({"agent": "drishti", "status": d.status,
                                 "attempts": d.attempts, "seconds": elapsed,
                                 "transcript": d.transcript,
                                 "reason": d.reason,
                                 "missing_fields": d.missing_fields})

    if d.status == "clarification_required":
        sink.record_halt("drishti", d.status, d.reason,
                         d.missing_fields,
                         packet.get("campaign_id"))
        say("x", f"Halted: incomplete packet. Missing: "
                 f"{', '.join(d.missing_fields)}", RED)
        _save(outdir, "05-run-report.json", report)
        return 1
    if d.status == "refused":
        sink.record_halt("drishti", "refused", d.reason, [],
                         packet.get("campaign_id"))
        say("x", f"Refused: {d.reason}", RED)
        _save(outdir, "05-run-report.json", report)
        return 1
    if d.status != "brief":
        say("x", f"Failed after {d.attempts} attempt(s): {d.reason}", RED)
        # Print the detail rather than making anyone go and find the report.
        for t in d.transcript:
            print(f"\n  --- turn {t['turn']} ---")
            print(f"  response: {t.get('raw_len')} chars, "
                  f"stop_reason={t.get('stop_reason')}, "
                  f"usage={t.get('usage')}")
            if t.get("truncated"):
                say("!", "  TRUNCATED. Raise max_tokens.", YELLOW)
            if t.get("parse_failed"):
                say("!", "  Response did not parse as JSON.", YELLOW)
                print(f"  starts: {t.get('raw_head', '')[:300]!r}")
                print(f"  ends:   {t.get('raw_tail', '')[:150]!r}")
            for e in (t.get("schema_errors") or [])[:8]:
                print(f"  schema: {e[:160]}")
            san = t.get("sanitizer") or {}
            if san.get("violations"):
                print(f"  sanitizer violations: {san['violations']}")
            if san.get("inconclusive"):
                print(f"  sanitizer inconclusive: {san['inconclusive']}")
        _save(outdir, "05-run-report.json", report)
        return 1

    if not args.brief:
        say("+", f"Brief produced in {d.attempts} model turn(s), {elapsed}s", GREEN)
    for t in d.transcript:
        if t.get("schema_errors"):
            say("!", f"  turn {t['turn']}: schema repair "
                     f"({len(t['schema_errors'])} error(s))", YELLOW)
        if t.get("sanitizer", {}).get("violations"):
            say("!", f"  turn {t['turn']}: compliance repair "
                     f"({', '.join(t['sanitizer']['violations'])})", YELLOW)
    say("+", f"  sanitizer: {len(d.sanitizer['checks_run'])} rules run, "
             f"pass={d.sanitizer['pass']}", DIM)
    oq = d.brief.get("open_questions_for_disha") or []
    if oq:
        say("!", f"Drishti raised {len(oq)} open question(s) for Disha:", YELLOW)
        for q in oq:
            print(f"      {q if isinstance(q, str) else q}")
    print(f"\n  core message: {d.brief.get('core_message')}")
    print(f"  insight: {(d.brief.get('insight') or '')[:150]}")

    sink.record_sanitizer("creative_brief", d.sanitizer,
                          campaign_id=packet.get("campaign_id"),
                          agent="drishti")
    _save(outdir, "01-creative-brief.json", d.brief)
    _save(outdir, "02-drishti-envelope.json", d.envelope)

    # ------------------------------------------------------------------ Disha
    head("STAGE 2 — DISHA (Creative Director)")
    t0 = time.time()
    say("+", "Divergence asks for 12 territories in one response. This is the "
             "long call; allow several minutes.", DIM)
    disha = DI.Disha(client, registry,
                     competitor_archive=DI.CompetitorArchive(
                         packet.get("competitor_archive", [])),
                     cost_model=DI.ProductionCostModel(
                         packet.get("production_cost_bands")))
    try:
        di = disha.run(d.brief, packet, context, drishti=drishti,
                       resource_pack=resource_pack)
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        say("x", f"Disha failed after {elapsed}s: {type(e).__name__}: {e}", RED)
        say("+", "Stage 1 output is intact and already written to disk. "
                 "Re-running resumes from a fresh brief; the completed one is "
                 "in 01-creative-brief.json.", DIM)
        report["stages"].append({"agent": "disha", "status": "error",
                                 "seconds": elapsed,
                                 "error": f"{type(e).__name__}: {e}"})
        report["outcome"] = "stage_2_failed"
        _save(outdir, "05-run-report.json", report)
        _save(outdir, "transcript.json", {"drishti": d.transcript})
        return 1
    elapsed = round(time.time() - t0, 1)

    report["stages"].append({"agent": "disha", "status": di.status,
                             "attempts": di.attempts, "seconds": elapsed,
                             "vulnerabilities": di.vulnerabilities,
                             "unverifiable": di.unverifiable,
                             "review_items": di.review_items,
                             "reason": di.reason,
                             "transcript": di.transcript})

    if di.vulnerabilities:
        say("!", f"Brief interrogation raised {len(di.vulnerabilities)} "
                 f"unresolved vulnerability(ies):", YELLOW)
        for v in di.vulnerabilities:
            who = v.get("raised_by", "disha")
            print(f"      [{who}] {v['field']}: {v['issue']}")
    else:
        say("+", "Brief interrogation: no structural vulnerabilities", GREEN)

    for t in di.transcript:
        g = t.get("gate")
        if g and not g["passed"]:
            reason = (g["report"]["verdict"] if g.get("report")
                      else "unreadable response" if t.get("parse_failed")
                      else f"returned keys {t['unexpected_keys']}"
                      if t.get("unexpected_keys")
                      else "truncated" if t.get("truncated") else "short")
            say("!", f"  turn {t['turn']}: divergence gate rejected ({reason})",
                YELLOW)
            if t.get("parse_failed"):
                print(f"      response began: {t.get('raw_head','')[:200]!r}")
            if t.get("stop_reason"):
                print(f"      stop_reason={t['stop_reason']} "
                      f"chars={t.get('raw_len')} "
                      f"territories={t.get('territories_returned')} "
                      f"usage={t.get('usage')} "
                      f"blocks={t.get('content_block_types')}")
            print(f"      {g['feedback'][:180]}")
        elif g:
            say("+", f"  turn {t['turn']}: divergence gate passed "
                     f"({t['n']} territories)", GREEN)

    if di.status == "refused":
        sink.record_halt("disha", "refused", di.reason, [],
                         packet.get("campaign_id"))
        say("x", f"Refused: {di.reason}", RED)
        _save(outdir, "05-run-report.json", report)
        return 1
    if di.status != "slate":
        say("x", f"Failed: {di.reason}", RED)
        _save(outdir, "05-run-report.json", report)
        return 1

    say("+", f"Slate produced in {elapsed}s", GREEN)
    print(f"\n  {'APPROVED':<12}{'SCORE':<8}{'CULTURAL':<10}TITLE")
    for a in di.slate["concepts_approved"]:
        print(f"  {a['id']:<12}{a['scores']['total']}/25   "
              f"{a['cultural_risk']['level']:<10}{a['title']}")
    print(f"\n  {'KILLED':<12}{'TAG'}")
    for k in di.slate["concepts_killed"]:
        print(f"  {k['id']:<12}{k['kill_tag']}")

    if di.unverifiable:
        say("!", "Unverifiable checks (dependency not connected):", YELLOW)
        for u in di.unverifiable:
            print(f"      {u['concept']}: {u['check']} — {u['reason']}")
    if di.review_items:
        say("!", "Human review queued:", YELLOW)
        for r in di.review_items:
            print(f"      {r['queue']} (SLA {r['sla_hours']}h): "
                  f"{', '.join(r['rule_ids'])}")

    sink.record_sanitizer("concept_slate", di.sanitizer,
                          campaign_id=packet.get("campaign_id"), agent="disha")
    sink.record_routing(di.review_items, campaign_id=packet.get("campaign_id"))
    for u in di.unverifiable:
        sink.append("check.unverifiable",
                    {"rule_id": u.get("check"), "reason": u.get("reason"),
                     "evidence": f"concept {u.get('concept')}"},
                    artifact_type="concept_slate", agent="disha",
                    campaign_id=packet.get("campaign_id"))
    _save(outdir, "03-concept-slate.json", di.slate)
    _save(outdir, "04-disha-envelope.json", di.envelope)

    # ----------------------------------------------------------------- report
    head("RESULT")
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["outcome"] = "slice_complete"
    audits = context.get("cultural_risk_audits") or {}
    report["caveats"] = []
    if not audits:
        report["caveats"].append(
            "No cultural risk audit exists for any concept. The cultural rules "
            "returned inconclusive and the slate is queued for cultural_review. "
            "It is not cleared for production.")
    else:
        report["caveats"].append(
            f"Cultural audits present for {len(audits)} concept(s), from "
            f"cultural_audits.json. Verify a named reviewer signed them.")
    if di.unverifiable:
        report["caveats"].append(
            "Competitor archive or production cost model not populated; the "
            "derivative and budget kill checks did not run.")
    _save(outdir, "05-run-report.json", report)
    _save(outdir, "transcript.json",
          {"drishti": d.transcript, "disha": di.transcript})

    say("+", f"Drishti to Disha to sanitizer completed.", GREEN)
    say("+", f"Artifacts written to {outdir}", GREEN)
    say("+", f"Ledger: {sink.verify()} at {sink.path}", GREEN)
    for c in report["caveats"]:
        say("!", c, YELLOW)
    return 0


def _rejudge(args, packet, context, outdir, report):
    """Re-judge an existing slate. No model call, no spend.

    A cultural review attaches to concept ids, and every generated slate has
    new ones, so re-running the pipeline to see the effect of a review discards
    the review. This judges the slate that was actually reviewed.
    """
    import chitra_sanitizer as _S

    registry = S.RuleRegistry.load(
        schema_path=os.path.join(HERE, "rule_object.schema.json"))
    sink = AUD.AuditSink(path=args.ledger, tenant_id=packet.get("tenant_id"))
    st = sink.verify()
    say("+" if st.ok else "x", f"Audit ledger: {st}", GREEN if st.ok else RED)
    if not st.ok:
        return 3

    slate = json.load(open(args.slate, encoding="utf-8"))
    head(f"RE-JUDGING {os.path.basename(os.path.dirname(args.slate))}")
    say("+", f"{len(slate.get('concepts_approved', []))} approved concept(s), "
             f"no model call", DIM)

    import chitra_review as _R
    raw = _R.load_audits(args.audits)
    audits, dropped = _R.bind_audits(raw, slate)
    for cid, why in dropped:
        say("!", f"Ignoring the audit filed under {cid}: {why}. That concept "
                 f"counts as unreviewed.", YELLOW)
    context["cultural_risk_audits"] = audits
    ids = [c["id"] for c in slate.get("concepts_approved", [])]
    reviewed = [i for i in ids if audits.get(i, {}).get("completed")]
    say("+" if len(reviewed) == len(ids) else "!",
        f"Cultural audits on file: {len(reviewed)}/{len(ids)} concept(s)",
        GREEN if len(reviewed) == len(ids) else YELLOW)
    for c in slate.get("concepts_approved", []):
        a = audits.get(c["id"]) or {}
        mark = "reviewed" if a.get("completed") else "NOT REVIEWED"
        print(f"      {c['id']:<8}{mark:<14}{a.get('level', '-'):<8}"
              f"{a.get('reviewer', '-')}")

    result = _S.sanitize("concept_slate", slate, context, registry)
    sink.record_sanitizer("concept_slate", result,
                          campaign_id=packet.get("campaign_id"), agent="disha")
    items = []
    try:
        import chitra_services as _SV
        items = [i.to_dict() for i in _SV.HITLRouter(registry).route(
            result, "concept_slate", packet.get("campaign_id"))]
        sink.record_routing(items, campaign_id=packet.get("campaign_id"))
    except Exception:
        pass

    head("VERDICT")
    say("+" if result.passed else "x",
        f"sanitizer_pass={result.passed}   "
        f"{len(result.checks_run)} rules run",
        GREEN if result.passed else RED)
    for v in result.violations:
        print(f"      BLOCK  {v['rule_id']}: {v['message'][:110]}")
    for w in result.warnings:
        print(f"      WARN   {w['rule_id']}: {w['message'][:110]}")
    for i in result.inconclusive:
        print(f"      REVIEW {i['rule_id']}: {i['message'][:110]}")
    for it in items:
        print(f"      queue  {it['queue']} (SLA {it['sla_hours']}h): "
              f"{', '.join(it['rule_ids'])}")

    report["stages"].append({"agent": "rejudge", "slate": args.slate,
                             "sanitizer": result.to_dict(),
                             "review_items": items,
                             "audits_on_file": len(reviewed), "concepts": len(ids)})
    report["outcome"] = ("slate_cleared" if result.passed
                         else "slate_held")
    _save(outdir, "03-concept-slate.json", slate)
    _save(outdir, "05-run-report.json", report)
    say("+", f"Ledger: {sink.verify()}", GREEN)
    say("+", f"Report written to {outdir}", GREEN)
    return 0 if result.passed else 1


def _save(outdir, name, obj):
    with open(os.path.join(outdir, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
