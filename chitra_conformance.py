#!/usr/bin/env python3
"""
chitra_conformance.py — CI conformance gate for the CHITRA specification set.

Runs four checks that the v1.2.2 and v1.2.3 sweeps did not:

  1. RULE CONFORMANCE  Every compliance rule authored in a spec document is
                       validated against rule_object.json, the schema the rule
                       registry uses to admit it. A rule that fails here is a
                       rule the registry silently drops at load time.
  2. SEVERITY HANDLING Every severity value used by a rule is one the output
                       sanitizer actually branches on. A value outside the set
                       falls through §H.2 without blocking or warning.
  3. DANGLING $REF     Every $ref in the document set resolves to a $id that
                       exists in the document set.
  4. CITATION FRESHNESS Every rule citation is checked against a curator-owned
                       register of superseded and repealed instruments.

Rules are data, the checker is code — matching the design decision that keeps
the rule registry separate from the sanitizer. Check 4 is driven entirely by
instruments.json, which the Resource Curator edits without touching this file.

Usage:
    python3 chitra_conformance.py <spec-dir-or-files>...
    python3 chitra_conformance.py --json <paths>     machine-readable output
    python3 chitra_conformance.py --check 1,4 <paths>  run a subset

Exit status: 0 clean, 1 findings, 2 harness error.
"""

import argparse
import json
import os
import re
import sys

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.stderr.write("chitra_conformance: pip install jsonschema\n")
    sys.exit(2)

FENCE = re.compile(r"^```(\w*)\s*$")
RULE_START = re.compile(r"^-\s+(?:id|rule_id):\s*(\S+)\s*$", re.M)
SCALAR = re.compile(r"^\s{2,}([a-z_]+):\s*(.*)$")
KEY_ANY = re.compile(r"^\s{2,}([a-z_]+):")

# Severity values the sanitizer at v1.2 §H.2 actually branches on.
# Anything outside this set is dropped without appearing in violations or
# warnings. Extend only in step with the sanitizer implementation.
SANITIZER_SEVERITIES = {"block", "warn", "info", "conditional"}

DEFAULT_INSTRUMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "instruments.json")


def read_blocks(path):
    """Yield (language, text, start_line) for each fenced block in a file."""
    lines = open(path, encoding="utf-8").read().splitlines()
    lang, buf, start = None, [], 0
    for n, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m and lang is None:
            lang, buf, start = m.group(1) or "text", [], n
        elif m and lang is not None:
            yield lang, "\n".join(buf), start
            lang = None
        elif lang is not None:
            buf.append(line)


def parse_rules(text, path, block_line):
    """Extract rule objects from a YAML-ish block.

    Deliberately tolerant. The check expressions in §G are pseudocode, not
    valid YAML, so a strict loader rejects the whole block and the rules with
    it. This reads top-level scalar fields and records which structural keys
    are present, which is exactly what conformance needs.
    """
    rules, cur = [], None
    for offset, line in enumerate(text.splitlines()):
        m = RULE_START.match(line)
        if m:
            if cur:
                rules.append(cur)
            cur = {"id": m.group(1), "_line": block_line + offset + 1,
                   "_file": os.path.basename(path), "_keys": set()}
            continue
        if cur is None:
            continue
        k = KEY_ANY.match(line)
        if k and len(line) - len(line.lstrip()) == 2:
            cur["_keys"].add(k.group(1))
        s = SCALAR.match(line)
        if s and len(line) - len(line.lstrip()) == 2:
            key, val = s.group(1), s.group(2).strip()
            if not val or key in cur:
                continue
            if val in ("true", "false"):
                cur[key] = val == "true"
            elif val.startswith("["):
                cur[key] = [v.strip().strip("\"'")
                            for v in val[1:-1].split(",") if v.strip()]
            else:
                cur[key] = val.strip("\"'")
    if cur:
        rules.append(cur)
    return rules


def collect(paths):
    """Walk the spec set once, returning rules, schemas, refs."""
    rules, schemas, refs = [], {}, []
    for path in paths:
        for lang, text, line in read_blocks(path):
            if lang in ("yaml", "yml") and RULE_START.search(text):
                rules.extend(parse_rules(text, path, line))
            if lang == "json":
                for sid in re.findall(r'"\$id"\s*:\s*"([^"]+)"', text):
                    schemas.setdefault(sid, (os.path.basename(path), line))
                    try:
                        schemas[sid] = (os.path.basename(path), line,
                                        json.loads(text))
                    except json.JSONDecodeError:
                        pass
            for ref in re.findall(r'"\$ref"\s*:\s*"([^"]+)"', text):
                refs.append((ref, os.path.basename(path), line))
    return rules, schemas, refs


def get_schema(schemas, sid):
    entry = schemas.get(sid)
    if entry and len(entry) == 3:
        return entry[2]
    return None


def resolve_rule_schema(schemas):
    """Return the effective rule_object schema.

    Several versions of rule_object.json may be present across the document
    set. The effective one is whichever is not superseded by another, declared
    via the "supersedes" keyword. Validating against a superseded schema would
    report findings against rules that conform to the current one.
    """
    candidates = {sid: get_schema(schemas, sid) for sid in schemas
                  if sid.endswith("/rule_object.json")}
    candidates = {k: v for k, v in candidates.items() if v is not None}
    if not candidates:
        return None, None
    superseded = {v.get("supersedes") for v in candidates.values() if v.get("supersedes")}
    live = [k for k in candidates if k not in superseded]
    if len(live) != 1:
        return None, sorted(live) or sorted(candidates)
    return candidates[live[0]], live[0]


def check_rule_conformance(rules, schemas):
    """Check 1 — validate every rule against the effective rule_object.json."""
    schema, sid = resolve_rule_schema(schemas)
    if schema is None:
        detail = (f"ambiguous rule_object schema: {sid}" if sid
                  else "rule_object.json not found in the document set")
        return [("HARNESS", "-", detail)]
    validator = Draft202012Validator(schema)
    findings = []
    for r in rules:
        payload = {k: v for k, v in r.items() if not k.startswith("_")}
        # Structural keys carry pseudocode, not schema-typed values. Presence
        # is what conformance needs; the sanitizer compiles the bodies.
        for k in ("applies_to", "applies_when", "check", "applies_when_expression",
                  "check_expression"):
            if k in r["_keys"] and k not in payload:
                payload[k] = [] if k == "applies_to" else ""
        errs = sorted(validator.iter_errors(payload), key=lambda e: str(e.path))
        for e in errs:
            field = ".".join(str(p) for p in e.path) or "(root)"
            findings.append((r["_file"], r["id"], f"{field}: {e.message}"))
    return findings


def check_severity_handling(rules):
    """Check 2 — every severity value is one the sanitizer branches on."""
    findings = []
    for r in rules:
        sev = r.get("severity")
        if sev is None:
            continue
        if sev not in SANITIZER_SEVERITIES:
            findings.append((r["_file"], r["id"],
                             f"severity '{sev}' is not handled by the sanitizer; "
                             f"the rule evaluates to silence"))
    return findings


def check_dangling_refs(refs, schemas):
    """Check 3 — every absolute $ref resolves to a defined $id."""
    findings = []
    for ref, fname, line in refs:
        if not ref.startswith("http"):
            continue
        if ref.split("#")[0] not in schemas:
            findings.append((fname, f"line {line}", f"$ref does not resolve: {ref}"))
    return findings


def check_citation_freshness(rules, instruments_path):
    """Check 4 — flag citations naming superseded or repealed instruments."""
    if not os.path.exists(instruments_path):
        return [("HARNESS", "-", f"instrument register not found: {instruments_path}")]
    register = json.load(open(instruments_path, encoding="utf-8"))
    findings = []
    for entry in register.get("instruments", []):
        if entry.get("status") == "current":
            continue
        pat = re.compile(entry["match"], re.I)
        # exempt_ids covers an instrument amended only in part: the entry still
        # fires for rules relying on the amended portion, and stays silent for
        # rules relying on a portion that survived.
        exempt = set(entry.get("exempt_ids", []))
        for r in rules:
            if r["id"] in exempt:
                continue
            # Match the citation only. Matching the id or source would fire on
            # a rule that has been correctly rewritten but kept its identifier.
            hay = str(r.get("citation", ""))
            if pat.search(hay):
                findings.append((r["_file"], r["id"],
                                 f"{entry['status']}: {entry['name']} — "
                                 f"{entry['note']}"))
    return findings


CHECKS = {
    1: ("rule conformance against rule_object.json", None),
    2: ("severity values handled by the sanitizer", None),
    3: ("dangling $ref", None),
    4: ("citation freshness", None),
}


def main():
    ap = argparse.ArgumentParser(description="CHITRA specification conformance gate")
    ap.add_argument("paths", nargs="+", help="spec files or directories")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", default="1,2,3,4", help="comma-separated check numbers")
    ap.add_argument("--instruments", default=DEFAULT_INSTRUMENTS,
                    help="path to the instrument register")
    args = ap.parse_args()

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p))
                      if f.endswith(".md")]
        else:
            files.append(p)
    if not files:
        sys.stderr.write("chitra_conformance: no markdown files found\n")
        return 2

    selected = {int(c) for c in args.check.split(",") if c.strip()}
    rules, schemas, refs = collect(files)

    # A rule reissued in a later document supersedes its earlier definition.
    # Files are processed in sorted order, so the last definition of an id wins.
    # This is what the registry does at load time; the gate must match it or it
    # reports findings against text that no longer governs anything.
    effective, superseded = {}, []
    for r in rules:
        if r["id"] in effective:
            superseded.append((r["id"], effective[r["id"]]["_file"], r["_file"]))
        effective[r["id"]] = r
    rules = list(effective.values())

    results = {}
    if 1 in selected:
        results[1] = check_rule_conformance(rules, schemas)
    if 2 in selected:
        results[2] = check_severity_handling(rules)
    if 3 in selected:
        results[3] = check_dangling_refs(refs, schemas)
    if 4 in selected:
        results[4] = check_citation_freshness(rules, args.instruments)

    total = sum(len(v) for v in results.values())
    bad_rules = {f[1] for v in results.values() for f in v if f[0] != "HARNESS"}

    if args.json:
        print(json.dumps({
            "files": len(files), "rules": len(rules), "schemas": len(schemas),
            "findings": total,
            "checks": {str(k): [{"file": a, "subject": b, "detail": c}
                                for a, b, c in v] for k, v in results.items()},
        }, indent=2))
        return 1 if total else 0

    print(f"CHITRA conformance gate — {len(files)} files, {len(rules)} effective "
          f"rules, {len(schemas)} schemas")
    if superseded:
        print(f"  {len(superseded)} rule(s) superseded by a later reissue:")
        for rid, old, new in superseded:
            print(f"    {rid}: {old} -> {new}")
    print()
    for num in sorted(results):
        label = CHECKS[num][0]
        found = results[num]
        status = f"{len(found)} finding(s)" if found else "clean"
        print(f"[check {num}] {label}: {status}")
        last = None
        for fname, subject, detail in found:
            if subject != last:
                print(f"    {subject}  ({fname})")
                last = subject
            print(f"        {detail}")
        print()

    if total:
        print(f"FAIL — {total} finding(s) across {len(bad_rules)} rule(s)/site(s).")
        if 1 in results and results[1]:
            print("       Rules failing check 1 are dropped by the registry at "
                  "load time and never run.")
        return 1
    print("PASS — specification set is conformant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
