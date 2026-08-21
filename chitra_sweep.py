"""
chitra_sweep.py — the compatibility sweep, running.

Specified in v1.3.1 §1 in May 2026 and never run once. In the interval Meta
shipped Marketing API v26.0, Google shipped Ads API v25, Meta replaced Nielsen
DMA targeting with Comscore Markets and unmigrated campaigns stopped
delivering, and Meta retired three reporting metrics Pramaan reads. All of it
was found by hand months later. This is the mechanism that was supposed to
find it on the Monday after it happened.

WHAT IT IS
    A scheduled internal job, not a CHITRA-callable service. Agents never
    invoke it. It compares each pinned external MCP server against its current
    upstream manifest, classifies what changed, opens curator tickets, puts
    affected agents into degraded mode on a breaking change, and publishes a
    report.

WHERE THE MANIFESTS COME FROM
    Pluggable. FileManifestSource reads curator-maintained snapshots and works
    with no network, which is how the job runs and is tested here.
    HTTPManifestSource fetches live and is what a deployment uses. Swapping one
    for the other is a constructor argument, so the sweep logic is never
    coupled to how a vendor happens to publish.

TWO FIELDS THAT ARE NOT IN v1.3.1
    v1.3.2 §5.2 added them after the audit found the pinning strategy has a
    hole:

      enforcement_date_all_versions   the date a change applies to every
                                      supported version regardless of pin.
                                      Pinning defers; it does not exempt.
      silent_failure_mode             true when a vendor drops or ignores a
                                      value rather than erroring. Meta v26.0
                                      errors on Instagram Explore Feed and
                                      silently strips Messenger Stories. The
                                      second is worse and no error handler
                                      catches it.
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))

NATIVE_SERVERS = {
    "chitra-search", "chitra-marketdata", "chitra-calendar", "chitra-regdb",
    "chitra-assetdb", "chitra-history", "chitra-resourcepack",
    "chitra-sanitizer", "legal-precheck",
}

DIFF_DIMENSIONS = [
    "methods_added", "methods_removed", "methods_renamed",
    "field_added_required", "field_added_optional", "field_removed",
    "field_renamed", "field_type_changed", "enum_values_added",
    "enum_values_removed", "auth_scope_changed", "rate_limit_changed",
    "pricing_changed", "deprecation_notice_present", "sunset_date_announced",
]

BREAKING = {"methods_removed", "methods_renamed", "field_added_required",
            "field_removed", "field_renamed", "field_type_changed",
            "enum_values_removed", "auth_scope_changed"}
SIGNIFICANT = {"deprecation_notice_present", "sunset_date_announced",
               "rate_limit_changed", "pricing_changed"}
MINOR = {"methods_added", "field_added_optional", "enum_values_added"}

SEVERITY_ORDER = {"informational": 0, "non_breaking_minor": 1,
                  "non_breaking_significant": 2, "breaking": 3}


# --------------------------------------------------------------------------
# Manifest sources
# --------------------------------------------------------------------------

class FileManifestSource:
    """Curator-maintained snapshots on disk. Works with no network."""

    def __init__(self, directory=None):
        self.dir = directory or os.path.join(HERE, "vendor_manifests")

    def fetch(self, server_id):
        path = os.path.join(self.dir, f"{server_id}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"no manifest snapshot for {server_id}")
        return json.load(open(path, encoding="utf-8"))


class HTTPManifestSource:
    """Live fetch. What a deployment uses; needs the vendor host allowlisted."""

    def __init__(self, urls, timeout=30):
        self.urls, self.timeout = urls, timeout

    def fetch(self, server_id):
        import urllib.request
        url = self.urls.get(server_id)
        if not url:
            raise KeyError(f"no manifest URL configured for {server_id}")
        with urllib.request.urlopen(url, timeout=self.timeout) as r:
            return json.loads(r.read())


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------

@dataclass
class Finding:
    finding_id: str
    server_id: str
    severity: str
    diff_dimension: str
    summary: str
    affected_methods: list = field(default_factory=list)
    affected_agents: list = field(default_factory=list)
    affected_rule_ids: list = field(default_factory=list)
    estimated_remediation_effort: str = "hours"
    vendor_documentation_url: Optional[str] = None
    deprecation_window_days: Optional[int] = None
    enforcement_date_all_versions: Optional[str] = None
    silent_failure_mode: bool = False

    def to_dict(self):
        # `v not in (None, [], False)` drops 0, because 0 == False in Python.
        # A sunset that lands today has a zero-day window, which is the most
        # urgent value the field can hold, and it was being deleted.
        keep = {"silent_failure_mode"}
        return {k: v for k, v in asdict(self).items()
                if k in keep or (v is not None and v != [] and v is not False)}


def _methods(manifest):
    return {m["name"]: m for m in manifest.get("methods", [])}


def _fields(method):
    return {f["name"]: f for f in method.get("fields", [])}


class DiffEngine:
    """Walks the fifteen diff dimensions from v1.3.1 §1.2."""

    def __init__(self, agent_map=None, rule_map=None):
        self.agent_map = agent_map or {}
        self.rule_map = rule_map or {}

    def diff(self, server_id, pinned, latest, seq_start=1):
        out, n = [], seq_start
        today = date.today().isoformat()

        def add(dim, summary, methods=None, **kw):
            nonlocal n
            sev = ("breaking" if dim in BREAKING else
                   "non_breaking_significant" if dim in SIGNIFICANT else
                   "non_breaking_minor" if dim in MINOR else "informational")
            f = Finding(
                finding_id=f"cs_finding_{today}_{n:03d}", server_id=server_id,
                severity=sev, diff_dimension=dim, summary=summary,
                affected_methods=sorted(methods or []),
                affected_agents=sorted({a for m in (methods or [])
                                        for a in self.agent_map.get(
                                            f"{server_id}.{m}", [])}),
                affected_rule_ids=sorted({r for m in (methods or [])
                                          for r in self.rule_map.get(
                                              f"{server_id}.{m}", [])}),
                vendor_documentation_url=latest.get("changelog_url"), **kw)
            out.append(f)
            n += 1

        pm, lm = _methods(pinned), _methods(latest)
        renamed = {r["from"]: r["to"] for r in latest.get("renamed_methods", [])}

        removed = sorted(set(pm) - set(lm) - set(renamed))
        if removed:
            add("methods_removed", f"{len(removed)} method(s) removed upstream: "
                                   f"{', '.join(removed)}", removed)
        added = sorted(set(lm) - set(pm))
        if added:
            add("methods_added", f"{len(added)} new method(s): "
                                 f"{', '.join(added)}", added)
        if renamed:
            add("methods_renamed",
                "; ".join(f"{a} renamed to {b}" for a, b in renamed.items()),
                sorted(renamed))

        for name in sorted(set(pm) & set(lm)):
            pf, lf = _fields(pm[name]), _fields(lm[name])
            fren = {r["from"]: r["to"]
                    for r in lm[name].get("renamed_fields", [])}
            if fren:
                add("field_renamed",
                    "; ".join(f"{name} field '{a}' renamed to '{b}'"
                              for a, b in fren.items()), [name],
                    silent_failure_mode=bool(lm[name].get("silent_failure_mode")),
                    enforcement_date_all_versions=lm[name].get(
                        "enforcement_date_all_versions"))
            gone = sorted(set(pf) - set(lf) - set(fren))
            if gone:
                add("field_removed", f"{name}: field(s) removed: "
                                     f"{', '.join(gone)}", [name],
                    silent_failure_mode=bool(lm[name].get("silent_failure_mode")),
                    enforcement_date_all_versions=lm[name].get(
                        "enforcement_date_all_versions"))
            rename_targets = set(fren.values())
            for fn in sorted(set(lf) - set(pf) - rename_targets):
                dim = ("field_added_required" if lf[fn].get("required")
                       else "field_added_optional")
                add(dim, f"{name}: new {'required' if lf[fn].get('required') else 'optional'} "
                         f"field '{fn}'", [name])
            for fn in sorted(set(pf) & set(lf)):
                if pf[fn].get("type") != lf[fn].get("type"):
                    add("field_type_changed",
                        f"{name}.{fn} type changed from {pf[fn].get('type')} "
                        f"to {lf[fn].get('type')}", [name])
                pe, le = set(pf[fn].get("enum") or []), set(lf[fn].get("enum") or [])
                if le - pe:
                    add("enum_values_added",
                        f"{name}.{fn} gains {', '.join(sorted(le - pe))}", [name])
                if pe - le:
                    add("enum_values_removed",
                        f"{name}.{fn} drops {', '.join(sorted(pe - le))}", [name],
                        silent_failure_mode=bool(lf[fn].get("silent_failure_mode")),
                        enforcement_date_all_versions=lf[fn].get(
                            "enforcement_date_all_versions"))

        if pinned.get("auth_scopes") and \
                set(pinned["auth_scopes"]) != set(latest.get("auth_scopes", [])):
            add("auth_scope_changed", "Required auth scopes changed upstream")
        if pinned.get("rate_limit") != latest.get("rate_limit") and \
                latest.get("rate_limit"):
            add("rate_limit_changed",
                f"Rate limit {pinned.get('rate_limit')} to {latest['rate_limit']}")
        if pinned.get("pricing") != latest.get("pricing") and latest.get("pricing"):
            add("pricing_changed",
                f"Pricing changed to {latest['pricing']}")

        for d in latest.get("deprecations", []):
            window = None
            if d.get("sunset_date"):
                try:
                    window = (date.fromisoformat(d["sunset_date"]) -
                              date.today()).days
                except ValueError:
                    window = None
            add("sunset_date_announced" if d.get("sunset_date")
                else "deprecation_notice_present",
                d.get("summary", "Deprecation announced"),
                d.get("affected_methods", []),
                deprecation_window_days=window,
                enforcement_date_all_versions=d.get(
                    "enforcement_date_all_versions"))
        return out, n


# --------------------------------------------------------------------------
# Version comparison
# --------------------------------------------------------------------------

def parse_version(v):
    nums = [int(x) for x in re.findall(r"\d+", str(v or ""))]
    return tuple(nums + [0, 0])[:3]


def version_distance(pinned, latest):
    if not pinned or not latest:
        return "unknown"
    p, l = parse_version(pinned), parse_version(latest)
    if p == l:
        return "same"
    if l[0] != p[0]:
        return "major_behind" if l[0] > p[0] else "unknown"
    if l[1] != p[1]:
        return "minor_behind" if l[1] > p[1] else "unknown"
    return "patch_behind" if l[2] > p[2] else "unknown"


# --------------------------------------------------------------------------
# Tickets
# --------------------------------------------------------------------------

SLA_HOURS = {"P0_retroactive": 8, "P0_immediate": 12, "P1_3_days": 72,
             "P2_5_days": 120, "P3_planned": 2160}


def ticket_priority(finding):
    # v1.3.2 §5.2: a retroactive enforcement date outranks ordinary breaking,
    # because the clock runs to a fixed date rather than from detection.
    if finding.enforcement_date_all_versions:
        return "P0_retroactive"
    if finding.severity == "breaking":
        return "P0_immediate"
    if finding.severity == "non_breaking_significant":
        return "P2_5_days"
    return "P3_planned"


@dataclass
class Ticket:
    ticket_id: str
    finding_id: str
    server_id: str
    severity: str
    summary: str
    ticket_priority: str
    assigned_to: str
    sla_breach_at: str
    affected_agents: list = field(default_factory=list)
    affected_rule_ids: list = field(default_factory=list)
    recommended_actions: list = field(default_factory=list)
    already_breached: bool = False

    def to_dict(self):
        return asdict(self)


def make_ticket(finding, now=None):
    now = now or datetime.now(timezone.utc)
    prio = ticket_priority(finding)
    if finding.enforcement_date_all_versions:
        try:
            breach = (datetime.fromisoformat(
                finding.enforcement_date_all_versions)
                .replace(tzinfo=timezone.utc) - timedelta(days=14))
        except ValueError:
            breach = now + timedelta(hours=SLA_HOURS[prio])
    else:
        breach = now + timedelta(hours=SLA_HOURS[prio])

    actions = ["Update the manifest in v1.2 §B",
               "Update the pinned version",
               "Update affected schemas in v1.2 §C"]
    if finding.affected_rule_ids:
        actions += ["Amend affected rules in v1.2 §G",
                    "Re-run sanitizer calibration"]
    if finding.silent_failure_mode:
        actions.append("Add a pre-call predicate: this change fails silently, "
                       "so no error handler will catch it")
    if finding.enforcement_date_all_versions:
        actions.append(f"Pinning does not defer past "
                       f"{finding.enforcement_date_all_versions}; schedule the "
                       f"migration before that date")
    actions += ["Trigger the regression suite",
                "Close the ticket with evidence"]

    return Ticket(
        ticket_id="CS-" + finding.finding_id.replace("cs_finding_", ""), finding_id=finding.finding_id,
        server_id=finding.server_id, severity=finding.severity,
        summary=finding.summary, ticket_priority=prio,
        assigned_to="resource_curator", sla_breach_at=breach.isoformat(),
        affected_agents=finding.affected_agents,
        affected_rule_ids=finding.affected_rule_ids,
        recommended_actions=actions,
        already_breached=breach < now)


# --------------------------------------------------------------------------
# The job
# --------------------------------------------------------------------------

@dataclass
class SweepReport:
    report_id: str
    sweep_run_at: str
    servers_swept: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    auto_bumps_applied: list = field(default_factory=list)
    tickets_opened: list = field(default_factory=list)
    degraded_mode_active: list = field(default_factory=list)
    fetch_failures: list = field(default_factory=list)
    webhook_events: list = field(default_factory=list)
    next_sweep_scheduled: Optional[str] = None

    @property
    def worst_severity(self):
        if not self.findings:
            return "none"
        return max((f["severity"] for f in self.findings),
                   key=lambda s: SEVERITY_ORDER.get(s, 0))

    def to_dict(self):
        d = asdict(self)
        d["worst_severity"] = self.worst_severity
        return d


class SweepRunner:
    """The weekly job. Cron, not a service."""

    def __init__(self, pins_path=None, source=None, agent_map=None,
                 rule_map=None, auto_bump=True):
        pins_path = pins_path or os.path.join(HERE, "pins.json")
        self.pins = json.load(open(pins_path, encoding="utf-8"))
        self.source = source or FileManifestSource()
        self.engine = DiffEngine(agent_map, rule_map)
        self.auto_bump = auto_bump

    def run(self, now=None):
        now = now or datetime.now(timezone.utc)
        report = SweepReport(
            report_id=f"sweep_{now.date().isoformat()}",
            sweep_run_at=now.isoformat(),
            next_sweep_scheduled=(now + timedelta(days=7)).isoformat())

        seq = 1
        for server_id, pin in sorted(self.pins["servers"].items()):
            if server_id in NATIVE_SERVERS:
                continue          # CHITRA-versioned; not a vendor
            try:
                latest = self.source.fetch(server_id)
            except Exception as e:
                report.fetch_failures.append({"server_id": server_id,
                                              "error": str(e)})
                report.servers_swept.append({
                    "server_id": server_id, "pinned_version": pin.get("version"),
                    "latest_version": None, "version_distance": "unknown",
                    "diff_status": "fetch_failed"})
                continue

            findings, seq = self.engine.diff(server_id, pin, latest, seq)
            dist = version_distance(pin.get("version"), latest.get("version"))
            worst = (max((f.severity for f in findings),
                         key=lambda s: SEVERITY_ORDER[s]) if findings
                     else None)
            status = {"breaking": "breaking",
                      "non_breaking_significant": "significant",
                      "non_breaking_minor": "minor_only",
                      "informational": "minor_only"}.get(worst, "no_changes")

            report.servers_swept.append({
                "server_id": server_id, "pinned_version": pin.get("version"),
                "latest_version": latest.get("version"),
                "version_distance": dist, "diff_status": status})

            for f in findings:
                report.findings.append(f.to_dict())
                if f.severity in ("breaking", "non_breaking_significant") or \
                        f.enforcement_date_all_versions:
                    report.tickets_opened.append(make_ticket(f, now).to_dict())
                if f.severity == "breaking":
                    report.degraded_mode_active.append({
                        "server_id": server_id,
                        "affected_methods": f.affected_methods,
                        "mode": "paused" if f.diff_dimension in
                                ("methods_removed", "auth_scope_changed")
                                else "read_only",
                        "active_since": now.isoformat(),
                        "affected_agents": f.affected_agents})
                    report.webhook_events.append({
                        "event_type": "compatibility_sweep.breaking_change_detected",
                        "finding_id": f.finding_id, "server_id": server_id,
                        "severity": "critical",
                        "summary": f.summary[:200]})
                    report.webhook_events.append({
                        "event_type": "tool.degraded_mode_active",
                        "server_id": server_id, "severity": "warn",
                        "summary": f"{server_id} degraded; eval results from this "
                                   f"window must be quarantined"})

            # Auto-bump only on patch and minor. Major always waits for review.
            if self.auto_bump and dist in ("patch_behind", "minor_behind") and \
                    status in ("no_changes", "minor_only"):
                report.auto_bumps_applied.append({
                    "server_id": server_id, "from": pin.get("version"),
                    "to": latest.get("version"), "reason": status})

        return report


def render(report):
    lines = [f"CHITRA compatibility sweep — {report.report_id}",
             f"run at {report.sweep_run_at}",
             f"servers swept: {len(report.servers_swept)}   "
             f"findings: {len(report.findings)}   "
             f"tickets: {len(report.tickets_opened)}   "
             f"worst: {report.worst_severity}", ""]
    for s in report.servers_swept:
        flag = "" if s["diff_status"] in ("no_changes", "minor_only") else "  <<<"
        lines.append(f"  {s['server_id']:<22} {str(s['pinned_version']):>8} -> "
                     f"{str(s['latest_version']):>8}  {s['version_distance']:<14}"
                     f"{s['diff_status']}{flag}")
    if report.findings:
        lines += ["", "FINDINGS"]
        for f in report.findings:
            lines.append(f"  [{f['severity']}] {f['finding_id']} "
                         f"{f['diff_dimension']}")
            lines.append(f"      {f['summary']}")
            if f.get("affected_agents"):
                lines.append(f"      agents: {', '.join(f['affected_agents'])}")
            if f.get("enforcement_date_all_versions"):
                lines.append(f"      applies to ALL versions from "
                             f"{f['enforcement_date_all_versions']} — pinning "
                             f"does not defer past this")
            if f.get("silent_failure_mode"):
                lines.append("      SILENT: vendor drops the value without an "
                             "error; no error handler will catch it")
    if report.tickets_opened:
        lines += ["", "TICKETS"]
        for t in report.tickets_opened:
            flag = "  BREACHED" if t.get("already_breached") else ""
            lines.append(f"  {t['ticket_id']}  {t['ticket_priority']:<15} "
                         f"SLA {t['sla_breach_at'][:10]}  {t['server_id']}{flag}")
    if report.degraded_mode_active:
        lines += ["", "DEGRADED MODE"]
        for d in report.degraded_mode_active:
            lines.append(f"  {d['server_id']} -> {d['mode']}  "
                         f"agents: {', '.join(d['affected_agents']) or 'unmapped'}")
    if report.fetch_failures:
        lines += ["", "FETCH FAILURES"]
        for f in report.fetch_failures:
            lines.append(f"  {f['server_id']}: {f['error']}")
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="CHITRA compatibility sweep")
    ap.add_argument("--manifests", default=None)
    ap.add_argument("--pins", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on", default="breaking",
                    choices=["never", "breaking", "significant"])
    args = ap.parse_args(argv)

    agent_map, rule_map = {}, {}
    m = os.path.join(HERE, "sweep_impact_map.json")
    if os.path.exists(m):
        d = json.load(open(m, encoding="utf-8"))
        agent_map, rule_map = d.get("agents", {}), d.get("rules", {})

    r = SweepRunner(pins_path=args.pins,
                    source=FileManifestSource(args.manifests),
                    agent_map=agent_map, rule_map=rule_map).run()
    print(json.dumps(r.to_dict(), indent=2) if args.json else render(r))

    if args.fail_on == "never":
        return 0
    threshold = "breaking" if args.fail_on == "breaking" \
        else "non_breaking_significant"
    return 1 if SEVERITY_ORDER.get(r.worst_severity, 0) >= \
        SEVERITY_ORDER[threshold] else 0


if __name__ == "__main__":
    raise SystemExit(main())
