"""
test_sweep.py — the compatibility sweep.

Fixtures are the real vendor state as of 12 August 2026: Meta Marketing API
v26.0 against a v25.0 pin, Google Ads v25 against a v23.1 pin. The job's whole
justification is that it would have caught these on the Monday after they
shipped, so the tests assert it catches exactly them.

Run: python3 test_sweep.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import chitra_sweep as SW

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


IMPACT = json.load(open(os.path.join(HERE, "sweep_impact_map.json"),
                        encoding="utf-8"))
NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def run():
    return SW.SweepRunner(agent_map=IMPACT["agents"],
                          rule_map=IMPACT["rules"]).run(now=NOW)


def findings(report, dim=None, server=None):
    return [f for f in report.findings
            if (dim is None or f["diff_dimension"] == dim)
            and (server is None or f["server_id"] == server)]


# ------------------------------------------------------- the real regressions
def test_catches_the_meta_v26_placement_removal():
    r = run()
    f = [x for x in findings(r, "enum_values_removed", "meta-marketing")
         if "instagram_explore_feed" in x["summary"]]
    check("Instagram Explore Feed removal detected", f, "not found")
    check("classified breaking", f and f[0]["severity"] == "breaking")
    check("flagged as failing silently", f and f[0]["silent_failure_mode"] is True,
          "Messenger Stories is stripped without an error; no error handler "
          "catches it")
    check("carries the all-version enforcement date",
          f and f[0]["enforcement_date_all_versions"] == "2026-10-27",
          "pinning defers to this date and no further")
    check("scoped to the agents that call it",
          f and set(f[0]["affected_agents"]) == {"gati", "lakshya"},
          str(f[0]["affected_agents"]) if f else "")
    check("names the rule that guards it",
          f and "PLATFORM-TOS-META-PLACEMENT-001" in f[0]["affected_rule_ids"],
          str(f[0]["affected_rule_ids"]) if f else "")


def test_catches_the_dma_to_comscore_rename():
    r = run()
    f = [x for x in findings(r, "field_renamed", "meta-marketing")
         if "dma_codes" in x["summary"]]
    check("dma_codes to comscore_market_codes rename detected", f)
    check("breaking, because unmigrated campaigns stopped delivering",
          f and f[0]["severity"] == "breaking")
    t = [t for t in r.tickets_opened if t["finding_id"] == f[0]["finding_id"]]
    check("ticket is P0_retroactive, not merely P0",
          t and t[0]["ticket_priority"] == "P0_retroactive",
          t[0]["ticket_priority"] if t else "")
    check("SLA already breached, since the date has passed",
          t and t[0]["already_breached"] is True,
          "enforcement was 2026-06-22 and the sweep never ran")


def test_catches_the_pramaan_metric_retirement():
    r = run()
    f = [x for x in findings(r, "enum_values_removed", "meta-marketing")
         if "post_reach" in x["summary"]]
    check("retired reporting metrics detected", f, str(findings(r, "enum_values_removed")))
    check("scoped to Pramaan", f and f[0]["affected_agents"] == ["pramaan"],
          "the eval harness would otherwise read this as a Pramaan regression")


def test_catches_the_google_rename_and_new_required_field():
    r = run()
    ren = [x for x in findings(r, "field_renamed", "google-ads-mcp")]
    check("must_include to required_phrases rename detected", ren)
    req = [x for x in findings(r, "field_added_required", "google-ads-mcp")]
    check("new required synthetic content attestation detected", req,
          str(findings(r, server="google-ads-mcp")))
    check("a new required field is breaking",
          req and req[0]["severity"] == "breaking")


def test_content_api_sunset_surfaces_with_a_window():
    r = run()
    f = [x for x in findings(r, "sunset_date_announced")
         if "Content API" in x["summary"]]
    check("Content API for Shopping sunset surfaces", f)
    check("window is computed, not asserted",
          f and isinstance(f[0].get("deprecation_window_days"), int),
          str(f[0].get("deprecation_window_days")) if f else "")


# ------------------------------------------------------- job behaviour
def test_version_distance_and_auto_bump():
    check("major behind detected",
          SW.version_distance("v25.0", "v26.0") == "major_behind")
    check("minor behind detected",
          SW.version_distance("2.4.0", "2.5.0") == "minor_behind")
    check("same version detected", SW.version_distance("v25.0", "v25.0") == "same")

    r = run()
    bumped = {b["server_id"] for b in r.auto_bumps_applied}
    check("minor version with only minor changes is auto-bumped",
          "bhashini-mcp" in bumped, str(bumped))
    check("major versions are never auto-bumped",
          not {"meta-marketing", "google-ads-mcp"} & bumped, str(bumped))


def test_breaking_change_triggers_degraded_mode_and_webhooks():
    r = run()
    check("degraded mode raised on a breaking change",
          any(d["server_id"] == "meta-marketing" for d in r.degraded_mode_active))
    events = {e["event_type"] for e in r.webhook_events}
    check("breaking-change webhook emitted",
          "compatibility_sweep.breaking_change_detected" in events, str(events))
    check("degraded-mode webhook emitted so eval quarantines the window",
          "tool.degraded_mode_active" in events, str(events))


def test_native_servers_are_excluded():
    r = run()
    swept = {s["server_id"] for s in r.servers_swept}
    check("CHITRA-versioned servers are not swept as vendors",
          not swept & SW.NATIVE_SERVERS, str(swept & SW.NATIVE_SERVERS))


def test_fetch_failure_is_reported_not_silent():
    class Broken:
        def fetch(self, server_id):
            raise ConnectionError("vendor unreachable")

    r = SW.SweepRunner(source=Broken()).run(now=NOW)
    check("an unreachable vendor is recorded as a failure",
          len(r.fetch_failures) >= 1, str(r.fetch_failures))
    check("and its row says fetch_failed rather than no_changes",
          all(s["diff_status"] == "fetch_failed" for s in r.servers_swept),
          str([s["diff_status"] for s in r.servers_swept]))


def test_no_changes_is_a_clean_sweep():
    import tempfile
    d = tempfile.mkdtemp()
    pins = json.load(open(os.path.join(HERE, "pins.json"), encoding="utf-8"))
    for sid, pin in pins["servers"].items():
        if sid in SW.NATIVE_SERVERS:
            continue
        json.dump(pin, open(os.path.join(d, f"{sid}.json"), "w"))
    r = SW.SweepRunner(source=SW.FileManifestSource(d)).run(now=NOW)
    check("an unchanged vendor set produces no findings", not r.findings,
          str(r.findings[:1]))
    check("and no tickets", not r.tickets_opened)
    check("worst severity is none", r.worst_severity == "none")


def test_rename_is_not_also_reported_as_a_new_field():
    r = run()
    added = [x for x in findings(r, "field_added_optional", "meta-marketing")
             if "comscore_market_codes" in x["summary"]]
    check("a rename target is not double-reported as a new field", not added,
          str(added))


def test_exit_code_gates_a_build():
    check("breaking findings exit non-zero",
          SW.main(["--fail-on", "breaking"]) == 1)
    check("never mode always exits zero",
          SW.main(["--fail-on", "never"]) == 0)


def main():
    for fn in (test_catches_the_meta_v26_placement_removal,
               test_catches_the_dma_to_comscore_rename,
               test_catches_the_pramaan_metric_retirement,
               test_catches_the_google_rename_and_new_required_field,
               test_content_api_sunset_surfaces_with_a_window,
               test_version_distance_and_auto_bump,
               test_breaking_change_triggers_degraded_mode_and_webhooks,
               test_native_servers_are_excluded,
               test_fetch_failure_is_reported_not_silent,
               test_no_changes_is_a_clean_sweep,
               test_rename_is_not_also_reported_as_a_new_field,
               test_exit_code_gates_a_build):
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
