"""
analyse_implementability.py — what the rule set can actually enforce.

Reports three things the specification does not:

  1. Implementability class per rule. How much of the compliance surface
     genuinely enforces, versus reads back a boolean the audited agent set.
  2. Human-review load per artifact type, which determines whether the
     sanitizer is operable at production volume.
  3. Divergence between the three places rule applicability is declared:
     §G applies_to, the §F.12 matrix, and the canonical artifact type list.

Run: python3 analyse_implementability.py
"""

import collections
import json
import os
import re
import sys

import chitra_predicates as P
import chitra_sanitizer as S

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_DIR = "/mnt/user-data/uploads"

CANONICAL_TYPES = [
    "creative_brief", "concept_slate", "concept_bible", "asset_registry",
    "motion_asset_registry", "media_plan", "daily_optimization_log",
    "content_calendar", "social_post", "performance_report", "learnings_dossier",
]

LABELS = {
    P.DETERMINISTIC: "DETERMINISTIC  computable from the artifact itself",
    P.SERVICE: "SERVICE        needs an external lookup",
    P.SELF_DECLARED: "SELF_DECLARED  reads a boolean the producing agent set",
    P.JUDGMENT: "JUDGMENT       needs a model or a human",
}


def load_matrix():
    """Parse the §F.12 matrix out of v1.2.1."""
    path = os.path.join(SPEC_DIR, "CHITRA-v1_2_1-Extended-Handoff-Schemas.md")
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    start = text.index("§F.12 RULE-TO-SCHEMA CROSS-REFERENCE MATRIX")
    end = text.index("### Reading the matrix")
    rows = {}
    header = None
    for line in text[start:end].splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None and "creative_brief" in line:
            header = cells[1:]
            continue
        if header is None or set("".join(cells)) <= set(":- "):
            continue
        rid = cells[0].strip("* ")
        rows[rid] = {header[i] for i, c in enumerate(cells[1:])
                     if i < len(header) and c == "●"}
    return rows


def main():
    reg = S.RuleRegistry.load(
        schema_path=os.path.join(HERE, "rule_object.schema.json"))
    rules = reg.rules

    print("=" * 78)
    print("1. WHAT EACH RULE CAN ENFORCE")
    print("=" * 78)
    by_class = collections.defaultdict(list)
    for r in rules:
        by_class[r.implementability].append(r)

    total = len(rules)
    for klass in (P.DETERMINISTIC, P.SERVICE, P.SELF_DECLARED, P.JUDGMENT):
        group = sorted(by_class[klass], key=lambda r: r.id)
        pct = round(100 * len(group) / total)
        print(f"\n{LABELS[klass]}   {len(group)}/{total} ({pct}%)")
        for r in group:
            note = P.REGISTRY[r.id]["note"]
            print(f"    {r.id:<34} {note}")

    enforcing = len(by_class[P.DETERMINISTIC]) + len(by_class[P.SERVICE])
    weak = len(by_class[P.SELF_DECLARED]) + len(by_class[P.JUDGMENT])
    print(f"\n  Genuinely enforcing: {enforcing}/{total} "
          f"({round(100 * enforcing / total)}%)")
    print(f"  Cannot enforce as written: {weak}/{total} "
          f"({round(100 * weak / total)}%)")

    print()
    print("=" * 78)
    print("2. HUMAN-REVIEW LOAD BY ARTIFACT TYPE (MEASURED)")
    print("=" * 78)
    print("\nMeasured, not assumed: a minimal artifact of each type is run through")
    print("the sanitizer. Any rule returning INCONCLUSIVE on an artifact with no")
    print("triggering content is a rule that sends every instance to a human.\n")

    minimal_ctx = {
        "tenant": {"tenant_id": "t_probe", "dpdp_retention_policy_days": 730},
        "services": {},
        "cultural_risk_audit": {"completed": True, "level": "low"},
    }
    print(f"  {'artifact type':<26}{'rules':>6}{'always reviewed':>18}")
    print("  " + "-" * 50)
    forced_total = 0
    for t in CANONICAL_TYPES:
        probe = {"referenced_tenant_ids": ["t_probe"], "product_category": "generic"}
        res = S.sanitize(t, probe, minimal_ctx, reg)
        forced = [i["rule_id"] for i in res.inconclusive]
        forced_total += bool(forced)
        label = f"{len(forced)}  {'YES' if forced else ''}"
        print(f"  {t:<26}{len(reg.for_artifact(t)):>6}{label:>18}")
        if forced:
            print(f"      {', '.join(sorted(forced))}")
    print(f"\n  With a completed cultural risk audit in context: {forced_total} of "
          f"{len(CANONICAL_TYPES)} artifact types always reviewed.")

    no_audit = dict(minimal_ctx, cultural_risk_audit={})
    forced_no_audit = 0
    detail = {}
    for t in CANONICAL_TYPES:
        probe = {"referenced_tenant_ids": ["t_probe"], "product_category": "generic"}
        res = S.sanitize(t, probe, no_audit, reg)
        ids = sorted(i["rule_id"] for i in res.inconclusive)
        if ids:
            forced_no_audit += 1
            detail[t] = ids
    print(f"  Without one:                                       {forced_no_audit} of "
          f"{len(CANONICAL_TYPES)} artifact types always reviewed.")
    print("\n  The cultural risk audit is therefore the real gate. It is a per-campaign")
    print("  human step, not a per-artifact one, so the review load depends on whether")
    print("  the audit is scoped to the campaign or repeated for every asset. That")
    print("  scoping decision is not made anywhere in the specification set.")

    print()
    print("=" * 78)
    print("3. WHERE APPLICABILITY IS DECLARED THREE TIMES AND DISAGREES")
    print("=" * 78)
    matrix = load_matrix()
    declared = {t for r in rules for t in r.applies_to}
    unknown = sorted(declared - set(CANONICAL_TYPES))
    print(f"\napplies_to values that are not canonical artifact types: {len(unknown)}")
    for t in unknown:
        users = sorted(r.id for r in rules if t in r.applies_to)
        print(f"    {t:<24} used by {len(users)} rule(s): "
              f"{', '.join(users[:4])}{' ...' if len(users) > 4 else ''}")

    if matrix:
        print(f"\nrule-by-rule comparison of §G applies_to against the §F.12 matrix:")
        diffs = 0
        for r in sorted(rules, key=lambda r: r.id):
            if r.id not in matrix:
                continue
            g = set(r.applies_to) & set(CANONICAL_TYPES)
            m = matrix[r.id]
            if g != m:
                diffs += 1
                only_g = sorted(g - m)
                only_m = sorted(m - g)
                print(f"    {r.id}")
                if only_g:
                    print(f"        in §G only:     {', '.join(only_g)}")
                if only_m:
                    print(f"        in matrix only: {', '.join(only_m)}")
        print(f"\n    {diffs} of {len(matrix)} matrix rules disagree with §G applies_to.")
        missing = sorted({r.id for r in rules} - set(matrix))
        print(f"    {len(missing)} rule(s) absent from the matrix entirely: "
              f"{', '.join(missing)}")
    else:
        print("\n  §F.12 matrix not available for comparison.")

    print()
    print("=" * 78)
    print("4. AUTO-FIX COVERAGE")
    print("=" * 78)
    fixable = [r.id for r in rules if r.auto_fix_available]
    print(f"\n  {len(fixable)}/{total} rules declare auto_fix_available: "
          f"{', '.join(fixable)}")
    print("  §H.2 step 7 branches on this field for every rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
